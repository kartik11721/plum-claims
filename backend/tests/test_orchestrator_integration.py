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
    # Message must name the uploaded type (prescription) AND the required missing type (hospital bill)
    msg_upper = result.member_message.upper()
    assert "PRESCRIPTION" in msg_upper, "message must name the uploaded document type"
    assert "HOSPITAL" in msg_upper, "message must name the required missing type"

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

    # All key pipeline steps must appear in trace (agent names reflect new multi-agent graph)
    step_names = [e.step for e in trace.events]
    assert "IntakeValidator" in step_names
    assert "DocumentClassifierAgent" in step_names
    assert "DocumentQualityAgent" in step_names
    # Per-document extraction agents are named ExtractionAgent[doc_N]
    assert any(s.startswith("ExtractionAgent[doc_") for s in step_names), "No extraction step found"
    assert "CrossDocValidator" in step_names
    assert "FraudSignalAgent" in step_names
    # Policy is now handled by PolicyOrchestratorAgent + sub-agents
    assert "PolicyOrchestratorAgent" in step_names
    assert "DecisionSynthesizer" in step_names

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


# ── TC005: waiting period → rejection with eligibility date ──────────────────

@pytest.mark.asyncio
async def test_tc005_waiting_period_member_message_includes_eligibility_date(orchestrator, test_cases):
    """
    TC005: Vikram Joshi claims for diabetes on 2024-10-15, within the 90-day
    waiting period (joined 2024-09-01; eligible 2024-11-30).

    system_must: message must state the date from which the member will be eligible.

    The synthesizer LLM is forced to fail so we exercise the fallback path,
    which is now responsible for guaranteeing the eligibility date appears.
    This also covers the case where the LLM itself is degraded at runtime.
    """
    tc = _load_test_case(test_cases, "TC005")
    submission = _parse_submission(tc)

    from app.models.decision import RejectionReason, DecisionType

    # Force the LLM to fail → exercises _fallback_member_message
    with patch("app.llm.client.structured_completion", side_effect=Exception("LLM unavailable")):
        result, trace = await orchestrator.process(submission, claim_id="test-tc005")

    assert result.decision == DecisionType.REJECTED
    assert RejectionReason.WAITING_PERIOD in result.rejection_reasons

    # The assignment requires the message to name the date from which the member is eligible
    assert "2024-11-30" in result.member_message, (
        f"member_message must include the eligibility date '2024-11-30', got: {result.member_message!r}"
    )


# ── TC002: unreadable document → early stop naming the specific file ──────────

@pytest.mark.asyncio
async def test_tc002_unreadable_document_names_file(orchestrator, test_cases):
    """
    TC002: PHARMACY claim — prescription is readable, pharmacy bill photo is blurry.

    system_must: identify that the pharmacy bill cannot be read and ask the member
    to re-upload that specific document (not a generic 'missing document' message).
    No LLM calls — quality hint bypasses vision pipeline.
    """
    tc = _load_test_case(test_cases, "TC002")
    submission = _parse_submission(tc)

    result, trace = await orchestrator.process(submission, claim_id="test-tc002")

    assert result.decision == DecisionType.NEEDS_DOCUMENTS
    assert result.early_stop is not None

    msg_lower = result.member_message.lower()
    # Must identify the specific unreadable file, not just say "missing"
    assert "blurry_bill.jpg" in result.member_message or "unreadable" in msg_lower, (
        f"message must reference the unreadable file or say 'unreadable', got: {result.member_message!r}"
    )
    # Must ask for re-upload, not outright reject
    assert "re-upload" in msg_lower or "upload" in msg_lower, (
        f"message must ask member to re-upload, got: {result.member_message!r}"
    )

    # Pipeline must not have run extraction
    step_names = [e.step for e in trace.events]
    assert "ExtractionAgent" not in step_names


# ── TC006: dental partial — cosmetic exclusion at line-item level ─────────────

@pytest.mark.asyncio
async def test_tc006_dental_partial_cosmetic_excluded(orchestrator, test_cases):
    """
    TC006: Priya Singh — root canal (₹8,000, covered) + teeth whitening (₹4,000, excluded).

    system_must: itemize which line items were approved/rejected and state the reason
    for each rejection at line-item level. Expected: PARTIAL ₹8,000.
    """
    tc = _load_test_case(test_cases, "TC006")
    submission = _parse_submission(tc)

    stub_response = _synthesizer_stub("PARTIAL")
    with patch("app.llm.client.structured_completion", new=AsyncMock(return_value=stub_response)):
        result, trace = await orchestrator.process(submission, claim_id="test-tc006")

    assert result.decision == DecisionType.PARTIAL
    assert result.approved_amount == pytest.approx(8000.0, abs=1.0)

    # Must have line-item breakdown with at least one approved and one rejected
    approved_items = [li for li in result.line_item_breakdown if li.status == "APPROVED"]
    rejected_items = [li for li in result.line_item_breakdown if li.status == "REJECTED"]
    assert approved_items, "Expected at least one approved line item"
    assert rejected_items, "Expected at least one rejected line item (cosmetic exclusion)"

    # The rejected item should be teeth whitening
    rejected_desc = " ".join(li.description.lower() for li in rejected_items)
    assert "whiten" in rejected_desc or "cosmetic" in rejected_desc or "teeth" in rejected_desc, (
        f"rejected item should reference whitening/cosmetic, got descriptions: {[li.description for li in rejected_items]}"
    )


# ── TC009: fraud signal — multiple same-day claims → manual review ────────────

@pytest.mark.asyncio
async def test_tc009_fraud_signal_routes_to_manual_review(orchestrator, test_cases):
    """
    TC009: EMP008 has 3 same-day claims in history; this is the 4th.

    system_must: flag the unusual pattern, route to manual review (not auto-reject),
    and include the specific signals in the output.
    """
    tc = _load_test_case(test_cases, "TC009")
    submission = _parse_submission(tc)

    stub_response = _synthesizer_stub("MANUAL_REVIEW")
    with patch("app.llm.client.structured_completion", new=AsyncMock(return_value=stub_response)):
        result, trace = await orchestrator.process(submission, claim_id="test-tc009")

    assert result.decision == DecisionType.MANUAL_REVIEW

    # Must not auto-reject — approved_amount should be non-zero or decision must be MANUAL_REVIEW
    assert result.decision != DecisionType.REJECTED, "Fraud signal must route to manual review, not auto-reject"

    # Applied rules must mention the same-day pattern
    rules_text = " ".join(result.applied_rules).lower()
    assert "same" in rules_text or "manual" in rules_text or "fraud" in rules_text, (
        f"applied_rules must reference the fraud/same-day signal, got: {result.applied_rules}"
    )


# ── TC010: network hospital discount applied before copay ─────────────────────

@pytest.mark.asyncio
async def test_tc010_network_discount_before_copay(orchestrator, test_cases):
    """
    TC010: EMP010 (Deepak Shah) claims ₹4,500 at Apollo Hospitals (network).
    Network discount (20%) → ₹3,600; copay (10%) → ₹360 deducted; final ₹3,240.

    system_must: apply network discount before copay, show breakdown in output.
    """
    tc = _load_test_case(test_cases, "TC010")
    submission = _parse_submission(tc)

    stub_response = _synthesizer_stub("APPROVED")
    with patch("app.llm.client.structured_completion", new=AsyncMock(return_value=stub_response)):
        result, trace = await orchestrator.process(submission, claim_id="test-tc010")

    assert result.decision == DecisionType.APPROVED
    assert result.approved_amount == pytest.approx(3240.0, abs=1.0)

    # applied_rules must show both the discount and copay entries
    rules_text = " ".join(result.applied_rules)
    assert "discount" in rules_text.lower(), "applied_rules must mention the network discount"
    assert "co-pay" in rules_text.lower() or "copay" in rules_text.lower(), "applied_rules must mention the co-pay"


# ── TC012: excluded treatment → rejection ────────────────────────────────────

@pytest.mark.asyncio
async def test_tc012_excluded_treatment_rejected(orchestrator, test_cases):
    """
    TC012: EMP009 claims for bariatric consultation and diet program — obesity
    treatment is explicitly excluded under the policy.

    Expected: REJECTED with EXCLUDED_CONDITION.
    """
    tc = _load_test_case(test_cases, "TC012")
    submission = _parse_submission(tc)

    with patch("app.llm.client.structured_completion", side_effect=Exception("LLM unavailable")):
        result, trace = await orchestrator.process(submission, claim_id="test-tc012")

    assert result.decision == DecisionType.REJECTED

    from app.models.decision import RejectionReason
    assert RejectionReason.EXCLUDED_CONDITION in result.rejection_reasons

    # Pipeline must have run through policy analysis
    step_names = [e.step for e in trace.events]
    assert "PolicyOrchestratorAgent" in step_names or any(
        "Exclusion" in s or "WaitingPeriod" in s for s in step_names
    )


# ── TC007: pre-auth missing → rejection with resubmission instructions ────────

@pytest.mark.asyncio
async def test_tc007_pre_auth_missing_message_includes_resubmission_instructions(orchestrator, test_cases):
    """
    TC007: MRI Lumbar Spine ₹15,000 without pre-auth. Policy requires pre-auth
    for imaging above ₹10,000.

    system_must: message must tell the member what to do to resubmit with pre-auth.

    LLM forced to fail so fallback path is exercised — fallback must include
    the resubmission instructions from rejection_detail.
    """
    tc = _load_test_case(test_cases, "TC007")
    submission = _parse_submission(tc)

    from app.models.decision import RejectionReason, DecisionType

    with patch("app.llm.client.structured_completion", side_effect=Exception("LLM unavailable")):
        result, trace = await orchestrator.process(submission, claim_id="test-tc007")

    assert result.decision == DecisionType.REJECTED
    assert RejectionReason.PRE_AUTH_MISSING in result.rejection_reasons

    msg_lower = result.member_message.lower()
    # Must tell member to obtain pre-authorization and resubmit
    assert "pre-auth" in msg_lower or "pre-authorization" in msg_lower, (
        f"message must mention pre-authorization, got: {result.member_message!r}"
    )
    assert "resubmit" in msg_lower, (
        f"message must include resubmission instructions, got: {result.member_message!r}"
    )


# ── TC008: per-claim limit exceeded → rejection with amounts ─────────────────

@pytest.mark.asyncio
async def test_tc008_per_claim_limit_message_includes_amounts(orchestrator, test_cases):
    """
    TC008: EMP003 claims ₹7,500 for CONSULTATION; policy per-claim limit is ₹5,000.

    system_must: message must state both the claimed amount and the per-claim limit.

    LLM forced to fail so fallback path is exercised — fallback must include
    the amounts from rejection_detail.
    """
    tc = _load_test_case(test_cases, "TC008")
    submission = _parse_submission(tc)

    from app.models.decision import RejectionReason, DecisionType

    with patch("app.llm.client.structured_completion", side_effect=Exception("LLM unavailable")):
        result, trace = await orchestrator.process(submission, claim_id="test-tc008")

    assert result.decision == DecisionType.REJECTED
    assert RejectionReason.PER_CLAIM_EXCEEDED in result.rejection_reasons

    # Must state the claimed amount (₹7,500) and the per-claim limit (₹5,000)
    assert "7,500" in result.member_message, (
        f"message must include the claimed amount ₹7,500, got: {result.member_message!r}"
    )
    assert "5,000" in result.member_message, (
        f"message must include the per-claim limit ₹5,000, got: {result.member_message!r}"
    )
