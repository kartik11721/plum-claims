from __future__ import annotations
"""
ClaimGraph — LangGraph-based multi-agent orchestrator.

Architecture:

  START → IntakeAgent
    │
    ├─(fail)──────────────────────────────────────────────► EarlyStop → END
    │
    └─(ok)─► DocumentClassifierAgent ──┐   (parallel)
             DocumentQualityAgent ─────┤
                                       └─► DocumentGate
                                             │
                                             ├─(fail)──────► EarlyStop → END
                                             │
                                             └─(ok)─► ExtractionAgent[0]  ┐
                                                      ExtractionAgent[1]  ├ Send fan-out
                                                      ...                 ┘
                                                      ExtractionAgent[N-1] ──► CrossDocValidator
                                                                               │
                                                                               ├─(fail)──► EarlyStop → END
                                                                               │
                                                                               └─(ok)─► FraudSignalAgent ──┐  (parallel)
                                                                                        PolicyOrchestrator ─┤
                                                                                          ├ MemberValidation │
                                                                                          ├ ExclusionCheck   │
                                                                                          ├ WaitingPeriod    │
                                                                                          ├ PreAuth          │
                                                                                          ├ PerClaimLimit    │
                                                                                          └ BenefitCalc      │
                                                                                                             └─► DecisionAggregator
                                                                                                                   │
                                                                                                                   └─► DecisionSynthesizer → END
"""
import asyncio
import uuid

from langgraph.graph import StateGraph, START, END

from ..models.claim import ClaimSubmission
from ..models.decision import FinalDecision
from ..models.trace import ClaimTrace
from .trace_recorder import TraceRecorder
from .graph_state import ClaimGraphState
from .graph_nodes import (
    intake_node, route_after_intake,
    classify_doc_types_node,
    check_doc_quality_node,
    document_gate_node, route_after_document_gate,
    extract_single_doc_node,
    identity_check_node, route_after_identity,
    analyze_fraud_node,
    analyze_policy_node,
    aggregate_decision_node,
    synthesize_node,
    early_stop_node,
)


class ClaimGraph:
    """
    Compiles and runs the multi-agent claim processing graph.

    Genuine concurrency:
    - DocumentClassifierAgent and DocumentQualityAgent run in parallel.
    - N ExtractionAgents run in parallel (one per uploaded document) via LangGraph Send.
    - FraudSignalAgent and PolicyOrchestratorAgent run in parallel.

    PolicyOrchestratorAgent is itself a multi-agent component that delegates to:
    MemberValidationAgent → ExclusionCheckerAgent → WaitingPeriodAgent →
    PreAuthCheckerAgent → PerClaimLimitAgent → BenefitCalculatorAgent.
    """

    def __init__(self, policy: dict) -> None:
        self.policy = policy
        self._compiled = self._build()

    def _build(self):
        builder = StateGraph(ClaimGraphState)

        # ── Register all agent nodes ──────────────────────────────────────
        builder.add_node("intake",              intake_node)
        builder.add_node("classify_doc_types",  classify_doc_types_node)
        builder.add_node("check_doc_quality",   check_doc_quality_node)
        builder.add_node("document_gate",       document_gate_node)
        builder.add_node("extract_single_doc",  extract_single_doc_node)
        builder.add_node("identity_check",      identity_check_node)
        builder.add_node("analyze_fraud",       analyze_fraud_node)
        builder.add_node("analyze_policy",      analyze_policy_node)
        builder.add_node("aggregate_decision",  aggregate_decision_node)
        builder.add_node("synthesize",          synthesize_node)
        builder.add_node("early_stop",          early_stop_node)

        # ── Entry ─────────────────────────────────────────────────────────
        builder.add_edge(START, "intake")

        # ── After intake: fan-out to classify ∥ quality, or early stop ───
        builder.add_conditional_edges(
            "intake",
            route_after_intake,
            ["classify_doc_types", "check_doc_quality", "early_stop"],
        )

        # ── Fan-in: both doc agents must complete before gate ─────────────
        builder.add_edge("classify_doc_types", "document_gate")
        builder.add_edge("check_doc_quality",  "document_gate")

        # ── After gate: Send fan-out to per-doc extractors, or early stop ─
        builder.add_conditional_edges(
            "document_gate",
            route_after_document_gate,
            ["extract_single_doc", "identity_check", "early_stop"],
        )

        # ── Fan-in: all extractors must complete before identity check ────
        builder.add_edge("extract_single_doc", "identity_check")

        # ── After identity: fan-out to fraud ∥ policy, or early stop ─────
        builder.add_conditional_edges(
            "identity_check",
            route_after_identity,
            ["analyze_fraud", "analyze_policy", "early_stop"],
        )

        # ── Fan-in: both analyses must complete before aggregation ────────
        builder.add_edge("analyze_fraud",   "aggregate_decision")
        builder.add_edge("analyze_policy",  "aggregate_decision")

        # ── Final path ────────────────────────────────────────────────────
        builder.add_edge("aggregate_decision", "synthesize")
        builder.add_edge("synthesize",  END)
        builder.add_edge("early_stop",  END)

        return builder.compile()

    async def process(
        self,
        submission: ClaimSubmission,
        claim_id: str | None = None,
        progress_queue: asyncio.Queue | None = None,
    ) -> tuple[FinalDecision, ClaimTrace]:
        claim_id = claim_id or str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        recorder = TraceRecorder(trace_id=trace_id, claim_id=claim_id)

        # Simulated component failure (TC011) — pre-degrade before graph runs
        initial_factors: list[float] = []
        initial_degraded: list[str] = []
        if submission.simulate_component_failure:
            from ..models.trace import TraceStatus
            initial_factors = [0.7]
            initial_degraded = ["ExtractionAgent[simulated]"]
            recorder.record(
                "ExtractionAgent[simulated_failure]",
                TraceStatus.DEGRADED, 0.0, {},
                {"note": "Simulated component failure as requested by test case"},
                error="SimulatedFailure: component failure injected by test flag",
            )

        initial_state: ClaimGraphState = {
            "submission":            submission,
            "claim_id":              claim_id,
            "trace_id":              trace_id,
            "policy":                self.policy,
            "progress_queue":        progress_queue,
            "recorder":              recorder,
            "degradation_factors":   initial_factors,
            "degraded_components":   initial_degraded,
            "intake_ok":             False,
            "intake_member_name":    None,
            "intake_join_date":      "2024-04-01",
            "intake_reasons":        [],
            "classification_result": None,
            "quality_result":        None,
            "extracted_docs":        [],
            "doc_index":             None,
            "identity_ok":           True,
            "identity_message":      None,
            "identity_mismatch_pairs": [],
            "fraud_signals":         None,
            "policy_decision":       None,
            "final_decision":        None,
            "early_stop":            None,
        }

        final_state = await self._compiled.ainvoke(initial_state)

        # Compute final degradation factor for trace finalization
        factors = final_state.get("degradation_factors") or []
        degradation_factor = 1.0
        for f in factors:
            degradation_factor *= f

        trace = recorder.finalize(degradation_factor)
        final_decision = final_state.get("final_decision")
        return final_decision, trace
