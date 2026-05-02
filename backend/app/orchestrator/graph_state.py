from __future__ import annotations
import operator
from typing import TypedDict, Annotated, Any

from ..models.claim import ClaimSubmission
from ..models.agents import ClassificationResult, QualityResult, FraudSignals
from ..models.decision import PolicyDecision, FinalDecision, EarlyStopResult


class ClaimGraphState(TypedDict):
    # ── Immutable inputs (set once at graph entry) ────────────────────────
    submission: ClaimSubmission
    claim_id: str
    trace_id: str
    policy: dict
    progress_queue: Any   # asyncio.Queue | None
    recorder: Any         # TraceRecorder (shared reference across all nodes)

    # ── Parallel-safe degradation tracking ────────────────────────────────
    # Each failed node appends 0.7; product is computed at synthesis time.
    degradation_factors: Annotated[list[float], operator.add]
    degraded_components: Annotated[list[str], operator.add]

    # ── IntakeAgent ────────────────────────────────────────────────────────
    intake_ok: bool
    intake_member_name: str | None
    intake_join_date: str
    intake_reasons: list[str]

    # ── DocumentClassifierAgent + DocumentQualityAgent (run in parallel) ──
    classification_result: ClassificationResult | None
    quality_result: QualityResult | None

    # ── ExtractionAgent × N (per-document fan-out via Send) ───────────────
    # operator.add accumulates results from N parallel extraction nodes.
    extracted_docs: Annotated[list, operator.add]
    doc_index: int | None  # populated by each Send; not meaningful in main state

    # ── CrossDocValidatorAgent ─────────────────────────────────────────────
    identity_ok: bool
    identity_message: str | None
    identity_mismatch_pairs: list

    # ── FraudSignalAgent + PolicyOrchestratorAgent (run in parallel) ──────
    fraud_signals: FraudSignals | None
    policy_decision: PolicyDecision | None

    # ── Final outputs ──────────────────────────────────────────────────────
    final_decision: FinalDecision | None
    early_stop: EarlyStopResult | None
