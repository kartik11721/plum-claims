# Plum Claims Processing System

Multi-agent AI system for health insurance claims processing. Accepts claims, verifies documents, extracts information via vision AI, applies policy rules deterministically, and produces auditable decisions with full trace.

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- `uv` (Python package manager): `pip install uv`
- Anthropic API key (for vision extraction and message synthesis)

### Backend

```bash
cd backend
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

export ANTHROPIC_API_KEY=sk-ant-...
export POLICY_FILE=../policy_terms.json

uvicorn app.main:app --reload --port 8000
```

API docs at http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install   # or pnpm install
npm run dev   # starts on http://localhost:3000
```

### Run Tests

```bash
cd backend
pytest tests/ -v
```

### Run Eval (12 Test Cases)

```bash
cd backend
POLICY_FILE=../policy_terms.json python scripts/run_eval.py
# Output: docs/eval_report.md
```

## Results

**12/12 test cases pass** in eval mode (pre-parsed content, no vision pipeline needed).

| Case | Name | Expected | Result |
|------|------|----------|--------|
| TC001 | Wrong Document Uploaded | NEEDS_DOCUMENTS | ✅ PASS |
| TC002 | Unreadable Document | NEEDS_DOCUMENTS | ✅ PASS |
| TC003 | Documents Belong to Different Patients | NEEDS_DOCUMENTS | ✅ PASS |
| TC004 | Clean Consultation — Full Approval | APPROVED ₹1,350 | ✅ PASS |
| TC005 | Waiting Period — Diabetes | REJECTED | ✅ PASS |
| TC006 | Dental Partial — Cosmetic Exclusion | PARTIAL ₹8,000 | ✅ PASS |
| TC007 | MRI Without Pre-Authorization | REJECTED | ✅ PASS |
| TC008 | Per-Claim Limit Exceeded | REJECTED | ✅ PASS |
| TC009 | Fraud Signal — Same-Day Claims | MANUAL_REVIEW | ✅ PASS |
| TC010 | Network Hospital Discount | APPROVED ₹3,240 | ✅ PASS |
| TC011 | Component Failure — Graceful Degradation | APPROVED (degraded) | ✅ PASS |
| TC012 | Excluded Treatment | REJECTED | ✅ PASS |

## Architecture

See `docs/architecture.md` for full design document.

```
ClaimOrchestrator
 ├── IntakeValidator          (member + policy check)
 ├── DocumentClassifierAgent  (LLM: classify doc types) ── GATE
 ├── DocumentQualityAgent     (LLM: readability check)  ── GATE
 ├── ExtractionAgent ×N       (LLM vision: parallel per doc)
 ├── CrossDocValidator        (identity match)           ── GATE
 ├── FraudSignalAgent         (pure Python: thresholds)
 ├── PolicyDecisionEngine     (pure Python: all rules from policy_terms.json)
 └── DecisionSynthesizer      (LLM: member message + ops summary)
```

Every step is wrapped by `GuardedExecutor` — failures degrade confidence rather than crash the pipeline.

## Key Design Decisions

- **Policy engine is fully deterministic** — no LLM computes approved amounts. All rules read from `policy_terms.json`.
- **Network discount applied before copay** (TC010) — enforced in `calculator.py`.
- **Exclusions checked before waiting periods** — categorical exclusion takes precedence (TC012).
- **Word-boundary matching** for waiting period keywords — prevents "herniation" matching "hernia" (TC007).
- **Early-stop gates** before heavy processing — wrong doc type, unreadable, or identity mismatch returns immediately with a specific user-facing message.

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/claims` | Submit claim (multipart: metadata + files) |
| GET | `/api/claims/{id}` | Get decision |
| GET | `/api/claims/{id}/trace` | Get full audit trace |
| POST | `/api/claims/eval` | Submit pre-parsed test case (eval mode) |
| GET | `/api/policy` | View active policy |
| GET | `/api/members/{id}` | Member lookup |
