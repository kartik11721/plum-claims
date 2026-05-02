from __future__ import annotations
import asyncio
import uuid
from ..models.claim import ClaimSubmission
from ..models.decision import FinalDecision, EarlyStopResult, DecisionType
from ..models.trace import TraceStatus, ClaimTrace
from ..agents import (
    IntakeValidator,
    FraudSignalAgent,
    DocumentClassifierAgent,
    DocumentQualityAgent,
    ExtractionAgent,
    CrossDocValidator,
    DecisionSynthesizer,
)
from ..policy_engine import PolicyDecisionEngine
from .trace_recorder import TraceRecorder
from .guarded_executor import GuardedExecutor


def _get_extraction_confidence(extracted_docs: list) -> float:
    if not extracted_docs:
        return 0.5
    confs = [getattr(d, "overall_confidence", 1.0) for d in extracted_docs if d is not None]
    return min(confs) if confs else 0.5


def _docs_to_dicts(extracted_docs: list) -> list[dict]:
    result = []
    for doc in extracted_docs:
        if doc is None:
            continue
        if hasattr(doc, "model_dump"):
            result.append(doc.model_dump())
        elif isinstance(doc, dict):
            result.append(doc)
    return result


class ClaimOrchestrator:
    def __init__(self, policy: dict):
        self.policy = policy
        self.intake = IntakeValidator(policy)
        self.fraud = FraudSignalAgent(policy)
        self.classifier = DocumentClassifierAgent(policy)
        self.quality = DocumentQualityAgent()
        self.extractor = ExtractionAgent()
        self.cross_doc = CrossDocValidator()
        self.decision_engine = PolicyDecisionEngine(policy)
        self.synthesizer = DecisionSynthesizer()

    async def process(
        self,
        submission: ClaimSubmission,
        claim_id: str | None = None,
        progress_queue: asyncio.Queue | None = None,
    ) -> tuple[FinalDecision | EarlyStopResult, ClaimTrace]:
        claim_id = claim_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        recorder = TraceRecorder(trace_id=trace_id, claim_id=claim_id)
        executor = GuardedExecutor(recorder, progress_queue=progress_queue)

        # Simulate component failure for TC011
        if submission.simulate_component_failure:
            executor.degraded_components.append("ExtractionAgent[simulated]")
            executor.degradation_factor *= 0.7
            recorder.record(
                "ExtractionAgent[simulated_failure]",
                TraceStatus.DEGRADED,
                0.0,
                {},
                {"note": "Simulated component failure as requested by test case"},
                error="SimulatedFailure: component failure injected by test flag",
            )

        # ── Step 1: Intake validation ──────────────────────────────────────
        intake_result = executor.run_sync(
            "IntakeValidator",
            lambda: self.intake.validate(submission),
            input_summary={"member_id": submission.member_id, "policy_id": submission.policy_id},
        )
        if intake_result and not intake_result.ok:
            trace = recorder.finalize(executor.degradation_factor)
            early_stop = EarlyStopResult(
                stop_reason="INTAKE_FAILED",
                member_message=f"Claim submission failed: {'; '.join(intake_result.reasons)}",
            )
            return _wrap_early_stop(early_stop, claim_id, trace_id), trace

        member_name = intake_result.member_name if intake_result else None
        join_date = intake_result.join_date if intake_result else "2024-04-01"

        # ── Step 2: Document classification (GATE) ──────────────────────────
        classification_result = await executor.run(
            "DocumentClassifierAgent",
            lambda: self.classifier.classify(submission),
            input_summary={"doc_count": len(submission.documents), "category": submission.claim_category.value},
        )
        if classification_result and not classification_result.ok:
            trace = recorder.finalize(executor.degradation_factor)
            early_stop = EarlyStopResult(
                stop_reason="DOCUMENT_TYPE_MISMATCH",
                member_message=classification_result.member_message or "Wrong document types uploaded.",
                details={"missing": [m.value for m in (classification_result.missing_required or [])]},
            )
            recorder.record("EARLY_STOP:DocumentMismatch", TraceStatus.EARLY_STOP, 0.0, {}, {"reason": early_stop.stop_reason})
            return _wrap_early_stop(early_stop, claim_id, trace_id), trace

        # ── Step 3: Document quality (GATE) ─────────────────────────────────
        quality_result = await executor.run(
            "DocumentQualityAgent",
            lambda: self.quality.check(submission.documents),
            input_summary={"doc_count": len(submission.documents)},
        )
        if quality_result and not quality_result.ok:
            trace = recorder.finalize(executor.degradation_factor)
            early_stop = EarlyStopResult(
                stop_reason="UNREADABLE_DOCUMENT",
                member_message=quality_result.member_message or "One or more documents could not be read.",
                details={"unreadable_files": quality_result.unreadable_files},
            )
            recorder.record("EARLY_STOP:UnreadableDocument", TraceStatus.EARLY_STOP, 0.0, {}, {"reason": early_stop.stop_reason})
            return _wrap_early_stop(early_stop, claim_id, trace_id), trace

        # ── Step 4: Extraction (parallel per doc) ───────────────────────────
        classifications = classification_result.classifications if classification_result else []
        extracted_docs = await executor.run(
            "ExtractionAgent",
            lambda: self.extractor.extract_all(submission.documents, classifications),
            input_summary={"doc_count": len(submission.documents)},
        )
        if not extracted_docs:
            extracted_docs = []

        # ── Step 5: Cross-document identity validation (GATE) ───────────────
        identity_result = executor.run_sync(
            "CrossDocValidator",
            lambda: self.cross_doc.validate(extracted_docs or [], member_name),
            input_summary={"member_name": member_name},
        )
        if identity_result and not identity_result.ok:
            trace = recorder.finalize(executor.degradation_factor)
            early_stop = EarlyStopResult(
                stop_reason="IDENTITY_MISMATCH",
                member_message=identity_result.member_message or "Documents belong to different patients.",
                details={"mismatch_pairs": identity_result.mismatch_pairs},
            )
            recorder.record("EARLY_STOP:IdentityMismatch", TraceStatus.EARLY_STOP, 0.0, {}, {"reason": early_stop.stop_reason})
            return _wrap_early_stop(early_stop, claim_id, trace_id), trace

        # ── Step 6: Fraud signals ────────────────────────────────────────────
        fraud_signals = executor.run_sync(
            "FraudSignalAgent",
            lambda: self.fraud.analyze(submission),
            input_summary={"claimed_amount": submission.claimed_amount, "history_count": len(submission.claims_history)},
        )
        from ..models.agents import FraudSignals as _FS
        if not fraud_signals:
            fraud_signals = _FS()

        # ── Step 7: Policy decision engine ──────────────────────────────────
        extracted_dicts = _docs_to_dicts(extracted_docs)
        policy_decision = executor.run_sync(
            "PolicyDecisionEngine",
            lambda: self.decision_engine.decide(submission, extracted_dicts, fraud_signals),
            input_summary={
                "category": submission.claim_category.value,
                "claimed_amount": submission.claimed_amount,
                "diagnoses": [d.get("diagnosis", []) for d in extracted_dicts[:1]],
            },
        )

        # ── Step 8: Decision synthesizer ────────────────────────────────────
        extraction_confidence = _get_extraction_confidence(extracted_docs)
        final_decision = await executor.run(
            "DecisionSynthesizer",
            lambda: self.synthesizer.synthesize(
                claim_id=claim_id,
                trace_id=trace_id,
                submission=submission,
                policy_decision=policy_decision,
                extraction_confidence=extraction_confidence,
                degradation_factor=executor.degradation_factor,
                degraded_components=executor.degraded_components,
            ),
            input_summary={"decision": policy_decision.decision.value if policy_decision else "UNKNOWN"},
        )

        trace = recorder.finalize(executor.degradation_factor)
        return final_decision, trace


def _wrap_early_stop(early_stop: EarlyStopResult, claim_id: str, trace_id: str) -> FinalDecision:
    return FinalDecision(
        claim_id=claim_id,
        decision=DecisionType.NEEDS_DOCUMENTS,
        approved_amount=0.0,
        confidence=0.0,
        member_message=early_stop.member_message,
        ops_summary=f"Early stop: {early_stop.stop_reason}. {early_stop.member_message}",
        early_stop=early_stop,
        trace_id=trace_id,
    )
