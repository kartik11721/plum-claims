from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime


class TraceStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    SKIPPED = "SKIPPED"
    EARLY_STOP = "EARLY_STOP"


class TraceEvent(BaseModel):
    step: str
    status: TraceStatus
    duration_ms: float
    input_summary: dict[str, Any] = {}
    output_summary: dict[str, Any] = {}
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ClaimTrace(BaseModel):
    trace_id: str
    claim_id: str
    events: list[TraceEvent] = []
    total_duration_ms: float = 0.0
    degradation_factor: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
