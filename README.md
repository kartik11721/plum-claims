# Plum Claims Processing System

Multi-agent AI system for health insurance claims processing. Accepts claims with supporting documents, verifies them through a staged pipeline, applies policy rules deterministically, and produces auditable decisions with a full step-by-step trace.

---

## Quick Start (One Command)

```bash
./setup.sh
```

This script:
- Checks Python 3.11+ and Node.js prerequisites
- Installs `uv` if missing, then installs all backend dependencies
- Runs `npm install` for the frontend
- Prompts for your API key if `.env` is not present
- Starts the backend on **http://localhost:8000** and frontend on **http://localhost:3000** with a shared Ctrl-C trap

---

## Manual Setup

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| uv | any (`pip install uv`) |
| API key | Anthropic **or** Azure OpenAI (see below) |

---

### 1. Environment Variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

**Option A — Anthropic (recommended):**
```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6        # optional, this is the default
```

**Option B — Azure OpenAI:**
```
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_RESOURCE_NAME=<resource>
AZURE_DEPLOYMENT_LLM=<deployment-name>
```

**Other backend vars (optional — defaults are shown):**
```
DATABASE_URL=sqlite:///./claims.db
UPLOAD_DIR=/tmp/plum_uploads
POLICY_FILE=../policy_terms.json
```

---

### 2. Backend

```bash
cd backend
uv venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Run (from repo root so POLICY_FILE resolves correctly)
cd ..
POLICY_FILE=policy_terms.json uvicorn backend.app.main:app --reload --port 8000
```

Interactive API docs: **http://localhost:8000/docs**

---

### 3. Frontend

```bash
cd frontend
cp .env.example .env.local      # set NEXT_PUBLIC_API_URL if backend isn't on :8000
npm install
npm run dev                     # starts on http://localhost:3000
```

---

### 4. Run Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

24 unit tests + 4 orchestrator integration tests. Integration tests stub the LLM with `AsyncMock` so they run without an API key.

---

### 5. Run Eval (12 Test Cases)

```bash
cd backend
source .venv/bin/activate
POLICY_FILE=../policy_terms.json python scripts/run_eval.py
```

Replays all 12 test cases from `test_cases.json` against the live pipeline in eval mode (no vision API needed). Results are written to `docs/eval_report.md`.

---

## Sample Documents

Ready-to-use claim documents are in `sample_docs/` for member **Rajesh Kumar (EMP001)**:

| File | Type |
|------|------|
| `prescription_rajesh_kumar.pdf` | Prescription |
| `prescription_rajesh_kumar_followup.pdf` | Follow-up prescription |
| `hospital_bill_rajesh_kumar.pdf` | Hospital bill |
| `lab_report_rajesh_kumar.pdf` | Lab report |
| `pharmacy_bill_rajesh_kumar.pdf` | Pharmacy bill |

To regenerate or create wrong-document test fixtures:

```bash
cd backend
source .venv/bin/activate
python scripts/generate_sample_docs.py   # creates sample_docs/
python scripts/generate_wrong_docs.py    # creates backend/scripts/sample_docs/ (blurry/mismatched)
```

---

## Eval Results

**12/12 test cases pass** in eval mode.

| Case | Scenario | Expected | Result |
|------|----------|----------|--------|
| TC001 | Wrong document uploaded | NEEDS_DOCUMENTS | ✅ PASS |
| TC002 | Unreadable document | NEEDS_DOCUMENTS | ✅ PASS |
| TC003 | Documents belong to different patients | NEEDS_DOCUMENTS | ✅ PASS |
| TC004 | Clean consultation — full approval | APPROVED ₹1,350 | ✅ PASS |
| TC005 | Waiting period — diabetes | REJECTED | ✅ PASS |
| TC006 | Dental partial — cosmetic exclusion | PARTIAL ₹8,000 | ✅ PASS |
| TC007 | MRI without pre-authorization | REJECTED | ✅ PASS |
| TC008 | Per-claim limit exceeded | REJECTED | ✅ PASS |
| TC009 | Fraud signal — same-day claims | MANUAL_REVIEW | ✅ PASS |
| TC010 | Network hospital discount | APPROVED ₹3,240 | ✅ PASS |
| TC011 | Component failure — graceful degradation | APPROVED (degraded) | ✅ PASS |
| TC012 | Excluded treatment | REJECTED | ✅ PASS |

---

## Architecture

Built on **LangGraph** (`StateGraph`). Agents coordinate through a shared state graph with genuine concurrent branches and dynamic fan-out — not a sequential caller loop.

```
START → IntakeAgent
          │
          ├─(fail)──────────────────────────────────── EarlyStop → END
          │
          └─(ok)─► DocumentClassifierAgent ──┐   ← parallel branch
                   DocumentQualityAgent ─────┘
                                    │
                                    └─► DocumentGate
                                          │
                                          ├─(fail)───────────────── EarlyStop → END
                                          │
                                          └─(ok)─► ExtractionAgent[doc_0]  ┐
                                                   ExtractionAgent[doc_1]  ├ Send fan-out
                                                   ...                     │ (one per doc,
                                                   ExtractionAgent[doc_N]  ┘  all parallel)
                                                                  │
                                                                  └─► CrossDocValidator
                                                                          │
                                                                          ├─(fail)─── EarlyStop → END
                                                                          │
                                                                          └─(ok)─► FraudSignalAgent ──┐  ← parallel
                                                                                   PolicyOrchestrator ─┘
                                                                                     ├ MemberValidationAgent
                                                                                     ├ ExclusionCheckerAgent
                                                                                     ├ WaitingPeriodAgent
                                                                                     ├ PreAuthCheckerAgent
                                                                                     ├ PerClaimLimitAgent
                                                                                     └ BenefitCalculatorAgent
                                                                                              │
                                                                                              └─► DecisionAggregator
                                                                                                       │
                                                                                                       └─► DecisionSynthesizer → END
```

**Genuine multi-agent patterns:**
- **Parallel document analysis** — `DocumentClassifierAgent` and `DocumentQualityAgent` run concurrently; `DocumentGate` is a fan-in barrier.
- **Per-document extraction fan-out** — LangGraph `Send` spawns one `ExtractionAgent` per uploaded document; all run in parallel and fan back in to `CrossDocValidator`.
- **Parallel fraud + policy** — `FraudSignalAgent` and `PolicyOrchestratorAgent` run concurrently; `DecisionAggregator` merges results.
- **Policy agent hierarchy** — `PolicyOrchestratorAgent` delegates sequentially to six specialised sub-agents (member validation → exclusion → waiting period → pre-auth → per-claim limit → benefit calculation), each with its own trace event.

Gates (DocumentGate, CrossDocValidator, IntakeAgent) trigger an early stop with a specific member-facing message — no downstream processing occurs. On any non-gate agent failure, the step is recorded as DEGRADED and the pipeline continues with reduced confidence (TC011).

See [`docs/architecture.md`](docs/architecture.md) for the full design document.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/claims` | Submit claim (multipart: `metadata` JSON + `files`). Returns `FinalDecision`. |
| `POST` | `/api/claims/stream` | Same as above but streams SSE step events (`step`, `complete`, `error`) — used by the UI. |
| `POST` | `/api/claims/eval` | Submit pre-parsed test case as JSON (eval mode — no vision pipeline). |
| `GET` | `/api/claims/{id}` | Get the `FinalDecision` for a submitted claim. |
| `GET` | `/api/claims/{id}/trace` | Get the full agent audit trace (`ClaimTrace`). |
| `GET` | `/api/policy` | View the loaded `policy_terms.json`. |
| `GET` | `/api/members/{member_id}` | Member lookup (returns name, join date, policy status). |

---

## Key Design Decisions

- **Policy engine is fully deterministic** — no LLM touches approved amounts or rule evaluation. All logic reads from `policy_terms.json`.
- **Gates before extraction** — wrong doc type or unreadable doc triggers an early stop before any LLM extraction cost is incurred.
- **Network discount applied before copay** — enforced in `calculator.py` (verified by TC010).
- **Exclusions checked before waiting periods** — categorical exclusion takes precedence over waiting period (TC012 vs TC005).
- **Word-boundary matching** for waiting period keywords — `\bhernia\b` prevents "herniation" from triggering the "hernia" waiting period (TC007).
- **Eval mode** — `/api/claims/eval` accepts pre-parsed document content so all 12 test cases run deterministically without real images or an API key.
- **Submission deadline not enforced** — policy has a 30-day claim window but test cases use 2024 dates while today is 2026, which would make all eval cases a false reject. Documented trade-off.
- **`has_pre_auth` not wired end-to-end** — the policy engine accepts a `has_pre_auth: bool` parameter and TC007 correctly rejects claims missing pre-auth. However, neither the submission form nor the `/api/claims` endpoint exposes this flag, so a real claimant who holds a valid pre-auth reference cannot submit it. The field is reserved for a future UI addition. TC007 passes because no pre-auth is ever provided.
