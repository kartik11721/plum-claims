from __future__ import annotations
import time
from ..models.trace import TraceEvent, TraceStatus, ClaimTrace


class TraceRecorder:
    def __init__(self, trace_id: str, claim_id: str):
        self.trace = ClaimTrace(trace_id=trace_id, claim_id=claim_id)
        self._start = time.monotonic()

    def record(
        self,
        step: str,
        status: TraceStatus,
        duration_ms: float,
        input_summary: dict = {},
        output_summary: dict = {},
        error: str | None = None,
    ) -> None:
        event = TraceEvent(
            step=step,
            status=status,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            error=error,
        )
        self.trace.events.append(event)

    def finalize(self, degradation_factor: float) -> ClaimTrace:
        self.trace.total_duration_ms = (time.monotonic() - self._start) * 1000
        self.trace.degradation_factor = degradation_factor
        return self.trace
