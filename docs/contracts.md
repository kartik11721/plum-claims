# Component Contracts — Plum Claims Processing System

Every component in the pipeline has a typed input, typed output, and a defined failure mode. Inputs and outputs are Pydantic v2 models; failure modes are either `ok=False` returns or recorded degradations via `GuardedExecutor`.

---

## 1. IntakeValidator

**Role**: First gate. Verifies the member exists and the policy is active before any document processing.

**Input**: `ClaimSubmission`
```
member_id: str
policy_id: str
claim_category: ClaimCategory
treatment_date: str (YYYY-MM-DD)
claimed_amount: float
documents: list[UploadedDoc]
claims_history: list[ClaimHistoryEntry]
```

**Output**: `IntakeResult`
```
ok: bool
member_name: str | None       — populated on success
join_date: str | None         — member join date from policy
reasons: list[str]            — non-empty only when ok=False
```

**Failure modes**:
- `ok=False, reasons=["Member '...' not found"]` — unknown member_id
- `ok=False, reasons=["Policy is not currently active"]` — renewal_status != ACTIVE
- `ok=False, reasons=["Policy ID '...' does not match"]` — wrong policy_id

**Invariants**:
- Never throws. Always returns `IntakeResult`.
- Does not call any LLM.
- Does not inspect document content.

---

## 2. DocumentClassifierAgent

**Role**: Gate. Classifies each uploaded document and verifies the correct document types are present for the claim category.

**Input**: `ClaimSubmission` (reads `documents` and `claim_category`)

**Output**: `ClassificationResult`
```
ok: bool
classifications: list[DocClassification]
  file_id: str
  file_name: str
  classified_type: DocumentType   — PRESCRIPTION | HOSPITAL_BILL | PHARMACY_BILL |
                                     LAB_REPORT | DIAGNOSTIC_REPORT | DENTAL_REPORT |
                                     DISCHARGE_SUMMARY | OTHER | UNREADABLE
  confidence: float (0.0–1.0)
missing_required: list[DocumentType]   — non-empty only when ok=False
member_message: str | None             — names uploaded type AND required type
```

**LLM usage**:
- One vision call per document (Claude vision with JSON schema prompt).
- Eval mode: if `doc.actual_type` is set, skips LLM and uses ground truth directly.
- Falls back to text-only `structured_completion` if no image bytes present.

**Early-stop trigger**: `ok=False` when any required document type is missing.

**Member message contract**: Message explicitly names both what was uploaded and what is required:
> "You uploaded: Prescription. However, for a Consultation claim you must provide: Prescription, Hospital Bill. Missing: Hospital Bill."

**Required document types per category** (policy + hardcoded defaults):
| Category | Required |
|----------|----------|
| CONSULTATION | PRESCRIPTION, HOSPITAL_BILL |
| DIAGNOSTIC | PRESCRIPTION, LAB_REPORT, HOSPITAL_BILL |
| PHARMACY | PRESCRIPTION, PHARMACY_BILL |
| DENTAL | HOSPITAL_BILL |
| VISION | PRESCRIPTION, HOSPITAL_BILL |
| ALTERNATIVE_MEDICINE | PRESCRIPTION, HOSPITAL_BILL |

---

## 3. DocumentQualityAgent

**Role**: Gate. Checks that every uploaded document is legible before incurring extraction cost.

**Input**: `list[UploadedDoc]`

**Output**: `QualityResult`
```
ok: bool
per_doc: list[DocQualityResult]
  file_id: str
  file_name: str
  quality: DocumentQuality   — GOOD | DEGRADED | UNREADABLE
  issue: str | None
unreadable_files: list[str]   — file names of UNREADABLE docs
member_message: str | None
```

**LLM usage**:
- One vision call per document.
- Eval mode: if `doc.quality` hint is set (`"GOOD"`, `"DEGRADED"`, `"UNREADABLE"`), skips LLM.
- If no image bytes, returns GOOD (can't assess).

**Early-stop trigger**: `ok=False` when any document is UNREADABLE.

**Member message contract**: Names the specific unreadable file(s):
> "We could not read the following document(s): "prescription_blurry.jpg". Please re-upload a clearer version..."

---

## 4. ExtractionAgent

**Role**: Extracts structured data from each document via vision AI. Runs all documents in parallel.

**Input** (per document): `UploadedDoc`, `classified_type: DocumentType`

**Output** (per document): Typed `ExtractedDocument` — discriminated union on `doc_type` literal:
```
ExtractedPrescription:
  doc_type: "prescription"
  doctor_name, doctor_registration, doctor_specialization
  patient_name, patient_age, patient_gender
  date, hospital_clinic
  diagnosis: list[str]
  medicines: list[str]
  tests_ordered: list[str]
  treatment: str | None
  overall_confidence: float
  quality_flags: list[str]

ExtractedHospitalBill:
  doc_type: "hospital_bill"
  hospital_name, hospital_address, gstin
  bill_number, date
  patient_name, patient_age, referring_doctor
  line_items: list[LineItem]    — description, amount, quantity
  subtotal, gst_amount, total
  overall_confidence: float

ExtractedLabReport:
  doc_type: "lab_report"
  lab_name, nabl_accredited
  patient_name, patient_age, referring_doctor
  sample_date, report_date
  tests: list[{name, result, unit, normal_range}]
  pathologist_name, remarks
  overall_confidence: float

ExtractedPharmacyBill:
  doc_type: "pharmacy_bill"
  pharmacy_name, drug_license
  bill_number, date, patient_name, prescribing_doctor
  line_items: list[LineItem]    — description, amount, batch, expiry, quantity
  subtotal, discount, net_amount
  overall_confidence: float

ExtractedGenericDoc:
  doc_type: "generic"
  patient_name: str | None
  overall_confidence: float
```

**LLM usage**:
- One vision call per document (schema-guided extraction).
- Eval mode: if `doc.content` (pre-parsed JSON) is set, skips vision pipeline entirely.
- Special case: if `doc.patient_name_on_doc` is set with no content/bytes, returns `ExtractedGenericDoc` with that name (supports TC003 test harness).

**Parallelism**: All documents extracted concurrently via `asyncio.gather`.

**Confidence**: Each field carries confidence. `overall_confidence` is the per-document summary score used downstream.

---

## 5. CrossDocValidator

**Role**: Gate. Verifies all extracted documents belong to the same patient as the claim member.

**Input**: `list[ExtractedDocument]`, `member_name: str | None`

**Output**: `IdentityCheckResult`
```
ok: bool
names_found: list[str]         — all patient names extracted across docs
mismatch_pairs: list[dict]     — [{file_id, name_on_doc}] for mismatched docs
member_message: str | None
```

**Logic**: Pure Python. No LLM.
- Normalizes names (lowercase + strip).
- Match: exact or one name is a substring of the other (handles "Rajesh Kumar" vs "Mr. Rajesh Kumar").
- Reference name: member_name from intake, or first name found if member_name unavailable.

**Early-stop trigger**: `ok=False` when any doc name doesn't match member name.

**Member message contract**: Names both the member and the mismatched name:
> "The member on this claim is "Rajesh Kumar", but we found different patient names: "Priya Singh" (doc doc_1). All documents must belong to the same patient."

---

## 6. FraudSignalAgent

**Role**: Computes fraud signals from claims history. Routes to MANUAL_REVIEW if thresholds exceeded.

**Input**: `ClaimSubmission` (reads `claimed_amount`, `treatment_date`, `claims_history`)

**Output**: `FraudSignals`
```
same_day_count: int           — prior claims on the same treatment_date
monthly_count: int            — prior claims in the same calendar month
high_value: bool              — claimed_amount > high_value_threshold
fraud_score: float (0.0–1.0)
flags: list[str]              — human-readable descriptions of each signal
requires_manual_review: bool
```

**Logic**: Pure Python. Reads thresholds from `policy.fraud_thresholds`:
```json
{
  "same_day_claims_limit": 2,
  "monthly_claims_limit": 6,
  "high_value_claim_threshold": 25000,
  "fraud_score_manual_review_threshold": 0.80
}
```

**Score assignment**:
- same_day_count ≥ limit → fraud_score = 0.85
- monthly_count ≥ limit → fraud_score = max(current, 0.75)
- high_value → fraud_score = max(current, 0.40)
- `requires_manual_review = fraud_score >= 0.80`

**LLM usage**: None.

---

## 7. PolicyDecisionEngine

**Role**: Applies all policy rules deterministically and produces the final coverage decision.

**Input**:
- `ClaimSubmission`
- `extracted_docs: list[ExtractedDocument]`
- `fraud_signals: FraudSignals`
- `has_pre_auth: bool` (not currently wired; reserved)
- `policy: dict` (loaded from policy_terms.json)

**Output**: `PolicyDecision`
```
decision: DecisionType   — APPROVED | PARTIAL | REJECTED | MANUAL_REVIEW
approved_amount: float
line_item_breakdown: list[LineItemDecision]
  description: str
  claimed_amount: float
  approved_amount: float
  status: str   — APPROVED | REJECTED | PARTIAL
  reason: str | None
rejection_reasons: list[RejectionReason]
applied_rules: list[str]        — human-readable list of every rule evaluated
eligibility_date: str | None    — for waiting period rejections, the date the member becomes eligible
```

**Rule execution order** (each is a short-circuit except where noted):
1. Member active check (redundant safety check after intake)
2. Minimum claim amount (< ₹100 → reject)
3. **Exclusions** — checked before waiting period. Categorical exclusion takes precedence.
4. **Waiting period** — word-boundary keyword matching. Returns eligibility date when rejected.
5. **Pre-authorization** — required for procedures above threshold (MRI/CT/PET > ₹5,000).
6. **Per-claim limit** — applies only to CONSULTATION (₹5,000 limit); other categories use sub-limits.
7. **Fraud routing** — MANUAL_REVIEW if `fraud_signals.requires_manual_review`.
8. **Line-item coverage** — DENTAL/VISION: per-item exclusion filtering; others: whole-claim.
9. **Network discount → copay** (in this order — discount applied to base, copay applied to discounted amount).
10. **Annual OPD limit cap** — final approved amount capped at remaining annual OPD budget.

**Sub-components** (each independently testable):
- `check_waiting_period(diagnoses, treatment, join_date, treatment_date, policy)` — uses `re.search(r'\b' + keyword + r'\b')` to prevent substring false positives (e.g., "herniation" must not trigger "hernia" waiting period).
- `check_exclusions(diagnoses, treatment, line_items, category, policy)` — returns matched exclusion names.
- `check_pre_auth(line_items, policy)` — returns `(ok, reason)`.
- `check_per_claim_limit(amount, policy)` — returns `(ok, reason)`.
- `compute_line_item_coverage(line_items, category, policy)` — returns per-item decisions.
- `apply_network_discount_then_copay(amount, hospital_name, category, policy)` — returns `(approved, discount_deducted, copay_deducted)`.
- `check_sub_limit(amount, category, ytd_amount, policy)` — caps against sub-limit and annual OPD remaining.

**Invariants**:
- Never calls any LLM. All decisions are deterministic functions of policy JSON + claim facts.
- Never throws. Returns `REJECTED` with reason on any unexpected state.

---

## 8. DecisionSynthesizer

**Role**: Produces the final `FinalDecision` record with member-facing message and ops summary.

**Input**:
- `claim_id: str`, `trace_id: str`
- `submission: ClaimSubmission`
- `policy_decision: PolicyDecision`
- `extraction_confidence: float`
- `degradation_factor: float`
- `degraded_components: list[str]`

**Output**: `FinalDecision`
```
claim_id: str
trace_id: str
decision: DecisionType
approved_amount: float
confidence: float            — min(extraction_confidence, 1.0) × degradation_factor
member_message: str          — member-facing explanation (LLM-generated or templated fallback)
ops_summary: str             — ops team summary
rejection_reasons: list[str]
line_item_breakdown: list[LineItemDecision]
applied_rules: list[str]
degraded_components: list[str]
early_stop: EarlyStopResult | None
```

**LLM usage**:
- One `structured_completion` call (no vision) to generate `member_message` and `ops_summary`.
- Prompt includes: claim category, claimed amount, decision, approved amount, applied rules, rejection reasons, eligibility date, degraded components, confidence.

**Fallback**: If LLM call fails (caught by GuardedExecutor), uses a template-generated message. Pipeline does not crash.

---

## 9. TraceRecorder

**Role**: Captures a faithful audit trail of every pipeline step for observability and reconstruction.

**Input** (per step): `step: str`, `status: TraceStatus`, `duration_ms: float`, `input_summary: dict`, `output_summary: dict`, `error: str | None`

**Output**: `ClaimTrace`
```
trace_id: str
claim_id: str
events: list[TraceEvent]
  step: str
  status: TraceStatus   — OK | DEGRADED | EARLY_STOP | SKIPPED
  duration_ms: float
  input_summary: dict
  output_summary: dict
  error: str | None
  timestamp: str (ISO 8601)
total_duration_ms: float
degradation_factor: float
```

**Invariants**:
- Events are appended in real time as each agent step completes.
- `finalize()` is called once after all agents complete; sets `total_duration_ms` and `degradation_factor`.
- Persisted to disk at `{UPLOAD_DIR}/{claim_id}/trace.json`. Retrievable via `GET /api/claims/{id}/trace`.

---

## 10. GuardedExecutor

**Role**: Wraps every agent call so that exceptions produce recorded degradations rather than pipeline crashes (TC011 compliance).

**Input**: `step: str`, `fn: Callable[[], Awaitable[T]]`, `input_summary: dict`, `default: Any`

**Behavior**:
- On success: records `TraceStatus.OK` event, returns result.
- On exception: records `TraceStatus.DEGRADED` event with error message and truncated traceback, multiplies `degradation_factor × 0.7`, appends step to `degraded_components`, returns `default`.

**State**:
```
degradation_factor: float   — starts at 1.0; each failure multiplies by 0.7
degraded_components: list[str]
```

**Invariants**:
- Supports both async (`run()`) and sync (`run_sync()`) callables.
- `degradation_factor` is propagated to `DecisionSynthesizer` to produce the final confidence score.
- Any claim with `degradation_factor < 1.0` surfaces a "manual review recommended" note in the UI.

---

## Cross-Cutting Concerns

### Eval Mode
The `/api/claims/eval` endpoint accepts `ClaimSubmission` as JSON (not multipart). Documents may carry:
- `actual_type` — bypasses DocumentClassifierAgent LLM call
- `quality` — bypasses DocumentQualityAgent LLM call
- `content` — bypasses ExtractionAgent vision pipeline
- `patient_name_on_doc` — used by CrossDocValidator when no content/bytes present

This allows all 12 test cases to run deterministically without real image files.

### Prompt Caching
All LLM system prompts use Anthropic's ephemeral prompt caching (`cache_control: {"type": "ephemeral"}`). The policy JSON is embedded in extraction prompts and cached. This reduces cost on repeated claims of the same category.

### Error Propagation
No agent throws to the orchestrator. All errors are one of:
- `ok=False` return (intake validator, gate agents)
- `GuardedExecutor` catches exception → DEGRADED trace event + default return

The orchestrator only sees typed return values, never raw exceptions.
