from __future__ import annotations
"""
ClaimOrchestrator — thin entry-point that delegates to ClaimGraph.

All orchestration logic now lives in ClaimGraph (claim_graph.py). This class
preserves the public interface used by the API layer and tests.
"""
import asyncio

from ..models.claim import ClaimSubmission
from ..models.decision import FinalDecision
from ..models.trace import ClaimTrace
from .claim_graph import ClaimGraph


class ClaimOrchestrator:
    """Entry point for the claims processing pipeline.

    Delegates to ClaimGraph, which implements a true multi-agent graph via
    LangGraph with parallel document analysis, per-document extraction fan-out,
    parallel fraud and policy analysis, and a policy orchestrator that further
    delegates to six specialised sub-agents.
    """

    def __init__(self, policy: dict) -> None:
        self._graph = ClaimGraph(policy)

    async def process(
        self,
        submission: ClaimSubmission,
        claim_id: str | None = None,
        progress_queue: asyncio.Queue | None = None,
    ) -> tuple[FinalDecision, ClaimTrace]:
        return await self._graph.process(submission, claim_id, progress_queue)
