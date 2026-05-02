from __future__ import annotations
import asyncio
import time
import traceback
from typing import TypeVar, Callable, Awaitable, Any
from ..models.trace import TraceStatus
from .trace_recorder import TraceRecorder

T = TypeVar("T")

DEGRADATION_MULTIPLIER = 0.7


def _summarise(result: Any) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump(exclude_none=True)
    if isinstance(result, list):
        return {"documents": [_summarise(item) for item in result]}
    if isinstance(result, dict):
        return result
    return {}


class GuardedExecutor:
    """
    Wraps agent calls so that failures are recorded in the trace
    and degrade confidence rather than crashing the pipeline (TC011).
    """

    def __init__(self, recorder: TraceRecorder, progress_queue: asyncio.Queue | None = None):
        self.recorder = recorder
        self.degradation_factor = 1.0
        self.degraded_components: list[str] = []
        self._progress_queue = progress_queue

    def _emit(self, step: str, status: str) -> None:
        if self._progress_queue:
            try:
                self._progress_queue.put_nowait({"type": "step", "step": step, "status": status})
            except asyncio.QueueFull:
                pass

    async def run(
        self,
        step: str,
        fn: Callable[[], Awaitable[T]],
        input_summary: dict = {},
        default: Any = None,
    ) -> T | Any:
        self._emit(step, "started")
        t0 = time.monotonic()
        try:
            result = await fn()
            duration = (time.monotonic() - t0) * 1000
            out_summary = _summarise(result)
            self.recorder.record(step, TraceStatus.OK, duration, input_summary, out_summary)
            self._emit(step, "done")
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            err_msg = f"{type(exc).__name__}: {exc}"
            tb = traceback.format_exc()
            self.recorder.record(
                step,
                TraceStatus.DEGRADED,
                duration,
                input_summary,
                {"error": err_msg, "traceback": tb[:500]},
                error=err_msg,
            )
            self.degradation_factor *= DEGRADATION_MULTIPLIER
            self.degraded_components.append(step)
            self._emit(step, "degraded")
            return default

    def run_sync(
        self,
        step: str,
        fn: Callable[[], T],
        input_summary: dict = {},
        default: Any = None,
    ) -> T | Any:
        self._emit(step, "started")
        t0 = time.monotonic()
        try:
            result = fn()
            duration = (time.monotonic() - t0) * 1000
            out_summary = _summarise(result)
            self.recorder.record(step, TraceStatus.OK, duration, input_summary, out_summary)
            self._emit(step, "done")
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            err_msg = f"{type(exc).__name__}: {exc}"
            self.recorder.record(
                step,
                TraceStatus.DEGRADED,
                duration,
                input_summary,
                {"error": err_msg},
                error=err_msg,
            )
            self.degradation_factor *= DEGRADATION_MULTIPLIER
            self.degraded_components.append(step)
            self._emit(step, "degraded")
            return default
