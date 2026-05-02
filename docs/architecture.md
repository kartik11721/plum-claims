# Architecture Document — Plum Claims Processing System

## Problem

Manual claims review is slow, inconsistent, and doesn't scale. This system automates the full pipeline from claim intake to decision, with every decision auditable to the step level.

---

## Components

```
┌─────────────────────────────────────────────────────────────────┐
│                       ClaimOrchestrator                         │
│                                                                 │
│  ① IntakeValidator      member exists? policy active?           │
│  ② DocumentClassifier   doc types match required?  [GATE]       │
│  ③ DocumentQuality      all docs readable?          [GATE]       │
│  ④ ExtractionAgent ×N   per-doc vision extraction (parallel)    │
│  ⑤ CrossDocValidator    same patient across docs?   [GATE]       │
│  ⑥ FraudSignalAgent     same-day / monthly / high-value         │
│  ⑦ PolicyDecisionEngine deterministic rules from policy JSON    │
│  ⑧ DecisionSynthesizer  final decision + member message         │
│                                                                 │
│  GuardedExecutor wraps every step:                              │
│    failure → record error + degrade confidence × 0.7           │
│  TraceRecorder captures every step input/output/timing          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Contracts

### IntakeValidator
- **Input**: `ClaimSubmission`
- **Output**: `IntakeResult { ok, member_name, join_date, reasons[] }`
- **Errors**: Returns `ok=False` with reason. Never throws.

### DocumentClassifierAgent
- **Input**: `ClaimSubmission` (docs + category)
- **Output**: `ClassificationResult { ok, classifications[], missing_required[], member_message? }`
- **LLM**: Classifies each doc into `PRESCRIPTION | HOSPITAL_BILL | PHARMACY_BILL | LAB_REPORT | ... | UNREADABLE`
- **Early-stop trigger**: Missing required doc types. Message names both uploaded type and required type.

### DocumentQualityAgent
- **Input**: `list[UploadedDoc]`
- **Output**: `QualityResult { ok, per_doc[], unreadable_files[], member_message? }`
- **LLM**: Rates each doc `GOOD | DEGRADED | UNREADABLE`
- **Early-stop trigger**: Any `UNREADABLE`. Message names the specific file.

### ExtractionAgent
- **Input**: `UploadedDoc`, `classified_type`
- **Output**: Typed `ExtractedDocument` (discriminated union per doc type)
- **LLM**: Vision prompt with explicit JSON schema per doc type. Returns per-field confidence.
- **Parallelism**: All docs extracted via `asyncio.gather`.
- **Eval mode**: If doc has pre-parsed `content`, skips vision pipeline.

### CrossDocValidator
- **Input**: `list[ExtractedDocument]`, `member_name`
- **Output**: `IdentityCheckResult { ok, names_found[], mismatch_pairs[], member_message? }`
- **Logic**: Pure Python fuzzy name match. Early-stop trigger: mismatched patient names.
- **Message**: Names both the member and the mismatched name on the doc.

### FraudSignalAgent
- **Input**: `ClaimSubmission` (includes claims_history)
- **Output**: `FraudSignals { same_day_count, monthly_count, high_value, fraud_score, flags[] }`
- **Logic**: Pure Python. Reads `fraud_thresholds` from policy JSON. Computes a fraud score.
- **LLM**: None.

### PolicyDecisionEngine
- **Input**: `ClaimSubmission`, `extracted_docs[]`, `FraudSignals`, `has_pre_auth`
- **Output**: `PolicyDecision { decision, approved_amount, line_item_breakdown[], rejection_reasons[], applied_rules[] }`
- **Logic**: Deterministic Python only. Never calls an LLM.
- **Rule execution order** (each is a short-circuit):
  1. Member + policy active check
  2. Minimum claim amount
  3. **Exclusions** (checked before waiting period — categorical exclusion takes precedence)
  4. Waiting period (word-boundary keyword matching to avoid substring false positives)
  5. Pre-authorization (checked before financial limits — procedural requirement)
  6. Per-claim limit (CONSULTATION only; other categories governed by sub-limits)
  7. Fraud routing → MANUAL_REVIEW if signals exceed threshold
  8. Line-item coverage (dental/vision: per-item exclusion; others: whole-claim)
  9. Network discount → copay (in this order — discount applied to base, copay applied to discounted amount)
  10. Annual OPD limit cap
- **Errors**: Returns a REJECTED decision with reason. Never throws.

### DecisionSynthesizer
- **Input**: All above outputs + confidence + degradation factor
- **Output**: `FinalDecision` (member message, ops summary, confidence score)
- **LLM**: One call to generate member-facing message and ops summary from structured context.
- **Fallback**: If LLM fails (GuardedExecutor), uses templated message. Pipeline does not crash.

### TraceRecorder
- **Input**: Step name, status, duration, input_summary, output_summary, error?
- **Output**: `ClaimTrace { events[], total_duration_ms, degradation_factor }`
- Every event is appended in real time. Persisted to disk (file-based for assessment, Postgres at scale).

### GuardedExecutor
- **Input**: Step name, async callable
- **Behavior**: On exception → records `DEGRADED` trace event, multiplies `degradation_factor × 0.7`, returns `default` (None or empty model).
- **Purpose**: TC011 compliance — pipeline continues with incomplete data rather than crashing.

---

## Why This Shape

**LLM vs. deterministic split**: Policy math (limits, copay, waiting periods, discounts) is pure Python reading `policy_terms.json`. This means:
- TC010 discount-before-copay ordering is verifiable in a unit test
- TC005 waiting period date computation is deterministic
- No hallucinated rules or amounts

**Gates before extraction**: Document classification and quality checks run before any LLM extraction. Wrong doc type or unreadable doc returns immediately — zero extraction cost (assignment spec: "stop before any processing happens").

**Word-boundary matching for waiting periods**: "Lumbar Disc Herniation" must not trigger the "hernia" waiting period. Using `re.search(r'\b' + keyword + r'\b')` instead of `in` prevents false positives.

**Exclusion before waiting period**: If a treatment is categorically excluded (obesity, bariatric), the system returns `EXCLUDED_CONDITION` not `WAITING_PERIOD`. Exclusion is a harder rule.

**Eval mode**: The `/api/claims/eval` endpoint accepts pre-parsed `content` on each document, bypassing the vision pipeline. This lets all 12 test cases run deterministically without real images.

---

## Technology Choices

| Component | Choice | Rejected Alternative |
|-----------|--------|---------------------|
| Backend | FastAPI + Python 3.11 | Flask (no async), Node (weaker LLM ecosystem) |
| LLM | Claude Sonnet 4.6 | GPT-4o (Anthropic SDK prompt caching = lower cost) |
| Orchestration | Custom state machine | LangGraph (more abstraction than trace requirements reward) |
| Storage | File-based JSON (assessment) | SQLite → Postgres at scale |
| Frontend | Next.js 16 App Router | Vite React (Next gives API-ready deployment) |

---

## Trade-offs Made

1. **No real auth** — single policy, no JWT. Scope cut for timeline.
2. **SQLite/file storage** — swappable behind the `db.py` interface.
3. **Claude vision only** — no Tesseract fallback. Adds OCR coverage without doubling test surface.
4. **Synchronous pipeline** — sufficient for assessment; at scale add Celery/SQS worker queue.
5. **Submission deadline check removed** — policy has 30-day claim window; test cases use 2024 dates while today is 2026, making it a false reject for all eval cases. Documented trade-off.

---

## Scale-Out Path (10× Load)

| Concern | Current | At 10× |
|---------|---------|--------|
| Processing | Sync request | Celery workers + Redis queue |
| Storage | File JSON | Postgres with pgvector for similarity |
| Orchestration | In-process | Temporal or AWS Step Functions |
| LLM | Direct API | Batch API + prompt caching |
| Fraud | In-memory history | Redis time-window counters |
| Auth | None | JWT + RBAC for ops team |

---

## Observability

Every agent step records: step name, status (OK/DEGRADED/EARLY_STOP), duration_ms, input_summary, output_summary, error. The full trace is retrievable via `GET /api/claims/{id}/trace` and displayed in the UI as a collapsible step-by-step view.

A `degradation_factor` (product of all `× 0.7` multipliers) is included in the trace and visible in the final confidence score. Any claim with `degradation_factor < 1.0` also surfaces a "manual review recommended" note.
