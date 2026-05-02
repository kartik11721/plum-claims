from __future__ import annotations
"""
Node functions for the LangGraph-based multi-agent claims pipeline.

Each node is an independent agent that reads from and writes to ClaimGraphState.
Parallel branches are wired in claim_graph.py:
  - classify_doc_types ∥ check_doc_quality       (converge at document_gate)
  - extract_single_doc × N  via Send fan-out       (converge at identity_check)
  - analyze_fraud ∥ analyze_policy               (converge at aggregate_decision)
"""
import asyncio
import time
from typing import Any

from langgraph.types import Send

from ..models.agents import FraudSignals
from ..models.decision import (
    DecisionType,
    EarlyStopResult,
    FinalDecision,
    PolicyDecision,
)
from ..models.extraction import ExtractedGenericDoc
from ..models.trace import TraceStatus
from ..agents.classifier import DocumentClassifierAgent
from ..agents.cross_doc import CrossDocValidator
from ..agents.extractor import ExtractionAgent
from ..agents.fraud import FraudSignalAgent
from ..agents.intake import IntakeValidator
from ..agents.quality import DocumentQualityAgent
from ..agents.synthesizer import DecisionSynthesizer
from .graph_state import ClaimGraphState
from .policy_subgraph import PolicyOrchestratorAgent


# ── Shared helpers ────────────────────────────────────────────────────────────

def _emit(queue: Any, step: str, status: str) -> None:
    if queue:
        try:
            queue.put_nowait({"type": "step", "step": step, "status": status})
        except (asyncio.QueueFull, Exception):
            pass


def _summarise(result: Any) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump(exclude_none=True)
    if isinstance(result, list):
        return {"count": len(result)}
    if isinstance(result, dict):
        return result
    return {}


def _degrade(step: str) -> dict:
    return {"degradation_factors": [0.7], "degraded_components": [step]}


# ── IntakeAgent ───────────────────────────────────────────────────────────────

def intake_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    policy = state["policy"]

    _emit(q, "IntakeValidator", "started")
    t0 = time.monotonic()
    try:
        result = IntakeValidator(policy).validate(submission)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "IntakeValidator", TraceStatus.OK, duration,
            {"member_id": submission.member_id}, _summarise(result),
        )
        _emit(q, "IntakeValidator", "done")

        if not result.ok:
            early_stop = EarlyStopResult(
                stop_reason="INTAKE_FAILED",
                member_message=f"Claim submission failed: {'; '.join(result.reasons)}",
            )
            return {
                "intake_ok": False,
                "intake_reasons": result.reasons,
                "early_stop": early_stop,
            }

        return {
            "intake_ok": True,
            "intake_member_name": result.member_name,
            "intake_join_date": result.join_date or "2024-04-01",
            "intake_reasons": [],
        }
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "IntakeValidator", TraceStatus.DEGRADED, duration,
            {}, {"error": str(exc)}, error=str(exc),
        )
        _emit(q, "IntakeValidator", "degraded")
        return {
            **_degrade("IntakeValidator"),
            "intake_ok": False,
            "intake_reasons": [str(exc)],
            "early_stop": EarlyStopResult(
                stop_reason="INTAKE_FAILED",
                member_message=f"Claim intake error: {exc}",
            ),
        }


def route_after_intake(state: ClaimGraphState) -> list[str] | str:
    if state.get("early_stop"):
        return "early_stop"
    # Fan-out: classification and quality run in parallel
    return ["classify_doc_types", "check_doc_quality"]


# ── DocumentClassifierAgent ───────────────────────────────────────────────────

async def classify_doc_types_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    policy = state["policy"]

    _emit(q, "DocumentClassifierAgent", "started")
    t0 = time.monotonic()
    try:
        result = await DocumentClassifierAgent(policy).classify(submission)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DocumentClassifierAgent", TraceStatus.OK, duration,
            {"doc_count": len(submission.documents)}, _summarise(result),
        )
        _emit(q, "DocumentClassifierAgent", "done")
        return {"classification_result": result}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DocumentClassifierAgent", TraceStatus.DEGRADED, duration,
            {}, {"error": str(exc)}, error=str(exc),
        )
        _emit(q, "DocumentClassifierAgent", "degraded")
        return {**_degrade("DocumentClassifierAgent"), "classification_result": None}


# ── DocumentQualityAgent ──────────────────────────────────────────────────────

async def check_doc_quality_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]

    _emit(q, "DocumentQualityAgent", "started")
    t0 = time.monotonic()
    try:
        result = await DocumentQualityAgent().check(submission.documents)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DocumentQualityAgent", TraceStatus.OK, duration,
            {"doc_count": len(submission.documents)}, _summarise(result),
        )
        _emit(q, "DocumentQualityAgent", "done")
        return {"quality_result": result}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DocumentQualityAgent", TraceStatus.DEGRADED, duration,
            {}, {"error": str(exc)}, error=str(exc),
        )
        _emit(q, "DocumentQualityAgent", "degraded")
        return {**_degrade("DocumentQualityAgent"), "quality_result": None}


# ── DocumentGate (fan-in barrier: runs after both classifier + quality done) ──

def document_gate_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    clsf = state.get("classification_result")
    qual = state.get("quality_result")

    _emit(q, "DocumentGate", "started")

    if clsf and not clsf.ok:
        early_stop = EarlyStopResult(
            stop_reason="DOCUMENT_TYPE_MISMATCH",
            member_message=clsf.member_message or "Wrong document types uploaded.",
            details={"missing": [m.value for m in (clsf.missing_required or [])]},
        )
        recorder.record(
            "EARLY_STOP:DocumentMismatch", TraceStatus.EARLY_STOP, 0.0, {},
            {"reason": early_stop.stop_reason},
        )
        _emit(q, "DocumentGate", "early_stop")
        return {"early_stop": early_stop}

    if qual and not qual.ok:
        early_stop = EarlyStopResult(
            stop_reason="UNREADABLE_DOCUMENT",
            member_message=qual.member_message or "One or more documents could not be read.",
            details={"unreadable_files": qual.unreadable_files},
        )
        recorder.record(
            "EARLY_STOP:UnreadableDocument", TraceStatus.EARLY_STOP, 0.0, {},
            {"reason": early_stop.stop_reason},
        )
        _emit(q, "DocumentGate", "early_stop")
        return {"early_stop": early_stop}

    _emit(q, "DocumentGate", "done")

    # Pre-signal the extraction step so the UI shows it as started.
    # The fan-out dispatches N parallel ExtractionAgent[doc_N] instances; this
    # wrapper event lets the frontend track a single "Extracting information" row.
    clsf2 = state.get("classification_result")
    if clsf2 and clsf2.classifications and state["submission"].documents:
        _emit(q, "ExtractionAgent", "started")

    return {}


def route_after_document_gate(state: ClaimGraphState) -> list[Send] | str:
    if state.get("early_stop"):
        return "early_stop"

    clsf = state.get("classification_result")
    docs = state["submission"].documents

    if not clsf or not clsf.classifications or not docs:
        # Nothing to extract — skip directly to identity check
        return "identity_check"

    # Fan-out: one ExtractionAgent per document, running in parallel via Send
    return [
        Send("extract_single_doc", {**state, "doc_index": i})
        for i in range(len(docs))
    ]


# ── ExtractionAgent (one instance per document, all run in parallel) ──────────

async def extract_single_doc_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    doc_index: int = state.get("doc_index") or 0

    doc = submission.documents[doc_index]
    clsf = state.get("classification_result")
    classification = (
        clsf.classifications[doc_index]
        if clsf and doc_index < len(clsf.classifications)
        else None
    )

    step = f"ExtractionAgent[doc_{doc_index}]"
    _emit(q, step, "started")
    t0 = time.monotonic()
    try:
        agent = ExtractionAgent()
        if classification:
            result = await agent._extract_single(doc, classification)
        else:
            result = ExtractedGenericDoc(overall_confidence=0.5)

        duration = (time.monotonic() - t0) * 1000
        recorder.record(step, TraceStatus.OK, duration, {"doc_index": doc_index}, _summarise(result))
        _emit(q, step, "done")
        return {"extracted_docs": [result]}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(step, TraceStatus.DEGRADED, duration, {}, {"error": str(exc)}, error=str(exc))
        _emit(q, step, "degraded")
        return {**_degrade(step), "extracted_docs": [ExtractedGenericDoc(overall_confidence=0.3)]}


# ── CrossDocValidatorAgent ────────────────────────────────────────────────────

def identity_check_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    member_name = state.get("intake_member_name")
    extracted_docs = state.get("extracted_docs") or []

    # Close the ExtractionAgent wrapper event (opened in document_gate_node).
    if extracted_docs:
        _emit(q, "ExtractionAgent", "done")

    _emit(q, "CrossDocValidator", "started")
    t0 = time.monotonic()
    try:
        result = CrossDocValidator().validate(extracted_docs, member_name)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "CrossDocValidator", TraceStatus.OK, duration,
            {"member_name": member_name}, _summarise(result),
        )
        _emit(q, "CrossDocValidator", "done")

        if not result.ok:
            early_stop = EarlyStopResult(
                stop_reason="IDENTITY_MISMATCH",
                member_message=result.member_message or "Documents belong to different patients.",
                details={"mismatch_pairs": result.mismatch_pairs},
            )
            recorder.record(
                "EARLY_STOP:IdentityMismatch", TraceStatus.EARLY_STOP, 0.0, {},
                {"reason": early_stop.stop_reason},
            )
            return {"early_stop": early_stop}

        return {}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record("CrossDocValidator", TraceStatus.DEGRADED, duration, {}, {"error": str(exc)}, error=str(exc))
        _emit(q, "CrossDocValidator", "degraded")
        return _degrade("CrossDocValidator")


def route_after_identity(state: ClaimGraphState) -> list[str] | str:
    if state.get("early_stop"):
        return "early_stop"
    # Fan-out: fraud and policy analysis run concurrently
    return ["analyze_fraud", "analyze_policy"]


# ── FraudSignalAgent ──────────────────────────────────────────────────────────

def analyze_fraud_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    policy = state["policy"]

    _emit(q, "FraudSignalAgent", "started")
    t0 = time.monotonic()
    try:
        result = FraudSignalAgent(policy).analyze(submission)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "FraudSignalAgent", TraceStatus.OK, duration,
            {"claimed_amount": submission.claimed_amount}, _summarise(result),
        )
        _emit(q, "FraudSignalAgent", "done")
        return {"fraud_signals": result}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record("FraudSignalAgent", TraceStatus.DEGRADED, duration, {}, {"error": str(exc)}, error=str(exc))
        _emit(q, "FraudSignalAgent", "degraded")
        return {**_degrade("FraudSignalAgent"), "fraud_signals": FraudSignals()}


# ── PolicyOrchestratorAgent (delegates to 6 policy sub-agents internally) ─────

async def analyze_policy_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    policy = state["policy"]
    extracted_docs = state.get("extracted_docs") or []
    join_date = state.get("intake_join_date") or "2024-04-01"

    _emit(q, "PolicyOrchestratorAgent", "started")
    t0 = time.monotonic()
    try:
        agent = PolicyOrchestratorAgent(policy)
        result = await agent.decide(submission, extracted_docs, join_date, recorder, q)
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "PolicyOrchestratorAgent", TraceStatus.OK, duration,
            {"category": submission.claim_category.value}, _summarise(result),
        )
        _emit(q, "PolicyOrchestratorAgent", "done")
        return {"policy_decision": result}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "PolicyOrchestratorAgent", TraceStatus.DEGRADED, duration,
            {}, {"error": str(exc)}, error=str(exc),
        )
        _emit(q, "PolicyOrchestratorAgent", "degraded")
        fallback = PolicyDecision(
            decision=DecisionType.APPROVED,
            approved_amount=submission.claimed_amount * 0.5,
            applied_rules=["Policy analysis degraded — manual review recommended."],
        )
        return {**_degrade("PolicyOrchestratorAgent"), "policy_decision": fallback}


# ── DecisionAggregator (fan-in: runs after fraud ∥ policy both complete) ─────

def aggregate_decision_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    fraud = state.get("fraud_signals") or FraudSignals()
    policy_dec = state.get("policy_decision")
    submission = state["submission"]
    policy = state["policy"]

    if not policy_dec:
        return {}

    _emit(q, "DecisionAggregator", "started")

    # Overlay fraud-based manual review routing onto the policy decision.
    # (FraudSignalAgent ran in parallel; this node merges the two results.)
    thresholds = policy.get("fraud_thresholds", {})
    manual_reasons: list[str] = list(policy_dec.manual_review_reasons or [])

    if fraud.requires_manual_review:
        manual_reasons.extend(fraud.flags)

    auto_threshold = thresholds.get("auto_manual_review_above", 25_000)
    if submission.claimed_amount > auto_threshold:
        manual_reasons.append(
            f"High-value claim ₹{submission.claimed_amount:,.0f} exceeds auto-review "
            f"threshold ₹{auto_threshold:,.0f}."
        )

    score_threshold = thresholds.get("fraud_score_manual_review_threshold", 0.80)
    if fraud.fraud_score >= score_threshold:
        manual_reasons.append(
            f"Fraud score {fraud.fraud_score:.2f} ≥ threshold {score_threshold}."
        )

    if manual_reasons and policy_dec.decision != DecisionType.REJECTED:
        updated_rules = list(policy_dec.applied_rules) + [
            f"Manual review triggered: {'; '.join(manual_reasons)}"
        ]
        policy_dec = policy_dec.model_copy(update={
            "decision": DecisionType.MANUAL_REVIEW,
            "requires_manual_review": True,
            "manual_review_reasons": manual_reasons,
            "applied_rules": updated_rules,
        })

    recorder.record(
        "DecisionAggregator", TraceStatus.OK, 0.0,
        {"decision": policy_dec.decision.value}, {},
    )
    _emit(q, "DecisionAggregator", "done")
    return {"policy_decision": policy_dec}


# ── DecisionSynthesizer ────────────────────────────────────────────────────────

async def synthesize_node(state: ClaimGraphState) -> dict:
    recorder = state["recorder"]
    q = state.get("progress_queue")
    submission = state["submission"]
    claim_id = state["claim_id"]
    trace_id = state["trace_id"]
    policy_dec = state.get("policy_decision")
    extracted_docs = state.get("extracted_docs") or []

    # Compute degradation factor from all accumulated factors
    factors = state.get("degradation_factors") or []
    degradation_factor = 1.0
    for f in factors:
        degradation_factor *= f
    if submission.simulate_component_failure:
        degradation_factor *= 0.7

    degraded_components = list(state.get("degraded_components") or [])
    if submission.simulate_component_failure and "ExtractionAgent[simulated]" not in degraded_components:
        degraded_components.append("ExtractionAgent[simulated]")

    _emit(q, "DecisionSynthesizer", "started")
    t0 = time.monotonic()
    try:
        confs = [getattr(d, "overall_confidence", 1.0) for d in extracted_docs if d is not None]
        extraction_confidence = min(confs) if confs else 0.5

        result = await DecisionSynthesizer().synthesize(
            claim_id=claim_id,
            trace_id=trace_id,
            submission=submission,
            policy_decision=policy_dec,
            extraction_confidence=extraction_confidence,
            degradation_factor=degradation_factor,
            degraded_components=degraded_components,
        )
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DecisionSynthesizer", TraceStatus.OK, duration,
            {"decision": policy_dec.decision.value if policy_dec else "UNKNOWN"},
            _summarise(result),
        )
        _emit(q, "DecisionSynthesizer", "done")
        return {"final_decision": result}
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        recorder.record(
            "DecisionSynthesizer", TraceStatus.DEGRADED, duration,
            {}, {"error": str(exc)}, error=str(exc),
        )
        _emit(q, "DecisionSynthesizer", "degraded")
        return _degrade("DecisionSynthesizer")


# ── EarlyStop ─────────────────────────────────────────────────────────────────

def early_stop_node(state: ClaimGraphState) -> dict:
    early_stop = state.get("early_stop")
    claim_id = state["claim_id"]
    trace_id = state["trace_id"]

    if early_stop:
        final = FinalDecision(
            claim_id=claim_id,
            decision=DecisionType.NEEDS_DOCUMENTS,
            approved_amount=0.0,
            confidence=0.0,
            member_message=early_stop.member_message,
            ops_summary=f"Early stop: {early_stop.stop_reason}. {early_stop.member_message}",
            early_stop=early_stop,
            trace_id=trace_id,
        )
        return {"final_decision": final}

    return {}
