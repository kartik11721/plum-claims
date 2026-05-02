"""
Integration tests: run the full ClaimOrchestrator pipeline end-to-end.

Uses eval-mode submissions (pre-parsed content / doc hints) so no real
document images are needed. The only LLM call remaining is DecisionSynthesizer
→ structured_completion; that is patched with a minimal stub so the tests
run without an ANTHROPIC_API_KEY.

Covered cases:
  TC001 — wrong document type (early stop at classification gate)
  TC003 — identity mismatch  (early stop at cross-doc gate)
  TC004 — clean consultation, full approval
  TC011 — simulated component failure, graceful degradation
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from app.config import load_policy
from app.orchestrator import ClaimOrchestrator
from app.models.claim import (
    ClaimSubmission, ClaimCategory, UploadedDoc,
    PreParsedContent, ClaimHistoryEntry, DocumentType,
)
from app.models.decision import DecisionType


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_test_case(test_cases: list[dict], case_id: str) -> dict:
    for tc in test_cases:
        if tc["case_id"] == case_id:
            return tc
    raise KeyError(f"Test case {case_id} not found")


def _parse_doc(doc_data: dict) -> UploadedDoc:
    actual_type_str = doc_data.get("actual_type")
    actual_type = DocumentType(actual_type_str) if actual_type_str else None
    content_data = doc_data.get("content")
    content = None
    if content_data:
        diagnosis_raw = content_data.get("diagnosis")
        content = PreParsedContent(
            doctor_name=content_data.get("doctor_name"),
            doctor_registration=content_data.get("doctor_registration"),
            patient_name=content_data.get("patient_name"),
            date=content_data.get("date"),
            diagnosis=diagnosis_raw if isinstance(diagnosis_raw, str) else None,
            treatment=content_data.get("treatment"),
            medicines=content_data.get("medicines", []),
            tests_ordered=content_data.get("tests_ordered", []),
            hospital_name=content_data.get("hospital_name"),
            line_items=content_data.get("line_items", []),
            total=content_data.get("total"),
            test_name=content_data.get("test_name"),
            net_amount=content_data.get("net_amount"),
        )
    return UploadedDoc(
        file_id=doc_data["file_id"],
        file_name=doc_data.get("file_name"),
        actual_type=actual_type,
        quality=doc_data.get("quality"),
        patient_name_on_doc=doc_data.get("patient_name_on_doc"),
        content=content,
    )


def _parse_submission(tc: dict) -> ClaimSubmission:
    inp = tc["input"]
    docs = [_parse_doc(d) for d in inp.get("documents", [])]
    history = [ClaimHistoryEntry(**h) for h in inp.get("claims_history", [])]
    return ClaimSubmission(
        member_id=inp["member_id"],
        policy_id=inp["policy_id"],
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=inp["treatment_date"],
        claimed_amount=inp["claimed_amount"],
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=inp.get("ytd_claims_amount", 0.0),
        claims_history=history,
        documents=docs,
        simulate_component_failure=inp.get("simulate_component_failure", False),
    )


def _synthesizer_stub(decision_str: str) -> dict:
    """Minimal stub response for DecisionSynthesizer structured_completion call."""
    return {
        "member_message": f"Test stub: decision is {decision_str}.",
        "ops_summary": f"Integration test stub — no real LLM call.",
    }


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def policy():
    policy_path = Path(__file__).parent.parent.parent / "policy_terms.json"
    with open(policy_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def test_cases():
    tc_path = Path(__file__).parent.parent.parent / "test_cases.json"
    with open(tc_path) as f:
        return json.load(f)["test_cases"]


@pytest.fixture
def orchestrator(policy):
    return ClaimOrchestrator(policy)


# ── TC001: wrong document type → early stop ──────────────────────────────────

@pytest.mark.asyncio
async def test_tc001_wrong_doc_type_early_stop(orchestrator, test_cases):
    """
    TC001: A prescription is uploaded for a CONSULTATION claim that requires
    a hospital bill. Should stop at DocumentClassifierAgent gate and return
    NEEDS_DOCUMENTS with a message naming both uploaded and required types.
    No LLM calls needed — eval-mode actual_type bypasses classifier LLM.
    """
    tc = _load_test_case(test_cases, "TC001")
    submission = _parse_submission(tc)

    result, trace = await orchestrator.process(submission, claim_id="test-tc001")

    assert result.decision == DecisionType.NEEDS_DOCUMENTS
    assert result.early_stop is not None
    assert result.early_stop.stop_reason == "DOCUMENT_TYPE_MISMATCH"
    assert result.member_message  # non-empty
    # Message must reference the required type (hospital bill)
    assert "HOSPITAL" in result.member_message.upper() or "hospital" in result.member_message.lower()

    # Trace must record DocumentClassifierAgent step
    step_names = [e.step for e in trace.events]
    assert "DocumentClassifierAgent" in step_names

    # ExtractionAgent must NOT appear — gate stopped pipeline before extraction
    assert "ExtractionAgent" not in step_names


# ── TC003: identity mismatch → early stop ────────────────────────────────────

@pytest.mark.asyncio
async def test_tc003_identity_mismatch_early_stop(orchestrator, test_cases):
    """
    TC003: Documents belong to different patients. CrossDocValidator should
    detect the mismatch and return NEEDS_DOCUMENTS. No LLM calls — eval-mode
    patient_name_on_doc provides names directly to the validator.
    """
    tc = _load_test_case(test_cases, "TC003")
    submission = _parse_submission(tc)

    result, trace = await orchestrator.process(submission, claim_id="test-tc003")

    assert result.decision == DecisionType.NEEDS_DOCUMENTS
    assert result.early_stop is not None
    assert result.early_stop.stop_reason == "IDENTITY_MISMATCH"
    assert result.member_message

    step_names = [e.step for e in trace.events]
    assert "CrossDocValidator" in step_names
    # PolicyDecisionEngine must NOT run — stopped at identity gate
    assert "PolicyDecisionEngine" not in step_names


# ── TC004: clean consultation → full approval ────────────────────────────────

@pytest.mark.asyncio
async def test_tc004_clean_consultation_approved(orchestrator, test_cases):
    """
    TC004: EMP001 submits a clean CONSULTATION claim for ₹1,500 at Apollo
    (network hospital). Expected: APPROVED ₹1,350 (10% copay applied).
    DecisionSynthesizer LLM call is stubbed.
    """
    tc = _load_test_case(test_cases, "TC004")
    submission = _parse_submission(tc)

    stub_response = _synthesizer_stub("APPROVED")
    with patch("app.llm.client.structured_completion", new=AsyncMock(return_value=stub_response)):
        result, trace = await orchestrator.process(submission, claim_id="test-tc004")

    assert result.decision == DecisionType.APPROVED
    assert result.approved_amount == pytest.approx(1350.0, abs=1.0)
    assert result.confidence > 0.0

    # All 8 pipeline steps must appear in trace
    step_names = [e.step for e in trace.events]
    for expected_step in [
        "IntakeValidator", "DocumentClassifierAgent", "DocumentQualityAgent",
        "ExtractionAgent", "CrossDocValidator", "FraudSignalAgent",
        "PolicyDecisionEngine", "DecisionSynthesizer",
    ]:
        assert expected_step in step_names, f"Missing trace step: {expected_step}"

    # No degradation on a clean run
    assert trace.degradation_factor == pytest.approx(1.0)
    assert result.degraded_components == []


# ── TC011: simulated failure → graceful degradation ──────────────────────────

@pytest.mark.asyncio
async def test_tc011_graceful_degradation(orchestrator, test_cases):
    """
    TC011: simulate_component_failure=True injects a DEGRADED trace event.
    Pipeline must still complete (not crash) and return a decision.
    Confidence must be degraded (< 1.0). DecisionSynthesizer stubbed.
    """
    tc = _load_test_case(test_cases, "TC011")
    submission = _parse_submission(tc)

    stub_response = _synthesizer_stub("APPROVED")
    with patch("app.llm.client.structured_completion", new=AsyncMock(return_value=stub_response)):
        result, trace = await orchestrator.process(submission, claim_id="test-tc011")

    # Pipeline must not crash — returns a real decision
    assert result.decision in {DecisionType.APPROVED, DecisionType.PARTIAL, DecisionType.MANUAL_REVIEW}

    # Degradation factor must be < 1.0 (0.7 applied for simulated failure)
    assert trace.degradation_factor == pytest.approx(0.7, abs=0.01)

    # Degraded components list must be non-empty
    assert result.degraded_components  # e.g. ["ExtractionAgent[simulated]"]

    # Confidence must reflect degradation
    assert result.confidence < 1.0

    # Trace must contain at least one DEGRADED event
    from app.models.trace import TraceStatus
    degraded_events = [e for e in trace.events if e.status == TraceStatus.DEGRADED]
    assert degraded_events, "Expected at least one DEGRADED trace event"
