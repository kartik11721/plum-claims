from __future__ import annotations
from enum import Enum
from pydantic import BaseModel


class DecisionType(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    NEEDS_DOCUMENTS = "NEEDS_DOCUMENTS"  # early-stop result


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    SUB_LIMIT_EXCEEDED = "SUB_LIMIT_EXCEEDED"
    ANNUAL_LIMIT_EXCEEDED = "ANNUAL_LIMIT_EXCEEDED"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    POLICY_INACTIVE = "POLICY_INACTIVE"
    DOCUMENT_MISMATCH = "DOCUMENT_MISMATCH"
    MINIMUM_AMOUNT_NOT_MET = "MINIMUM_AMOUNT_NOT_MET"
    SUBMISSION_DEADLINE_EXCEEDED = "SUBMISSION_DEADLINE_EXCEEDED"


class LineItemDecision(BaseModel):
    description: str
    claimed_amount: float
    approved_amount: float
    status: str  # APPROVED | REJECTED | REDUCED
    reason: str | None = None


class PolicyDecision(BaseModel):
    decision: DecisionType
    approved_amount: float
    line_item_breakdown: list[LineItemDecision] = []
    rejection_reasons: list[RejectionReason] = []
    applied_rules: list[str] = []  # human-readable rule descriptions for trace
    eligibility_date: str | None = None  # for waiting period rejections
    network_discount_applied: float = 0.0
    copay_deducted: float = 0.0
    requires_manual_review: bool = False
    manual_review_reasons: list[str] = []


class EarlyStopResult(BaseModel):
    """Returned when pipeline stops before making a claim decision."""
    stop_reason: str  # DOCUMENT_TYPE_MISMATCH | UNREADABLE_DOCUMENT | IDENTITY_MISMATCH
    member_message: str
    details: dict = {}


class FinalDecision(BaseModel):
    claim_id: str
    decision: DecisionType
    approved_amount: float
    confidence: float
    member_message: str
    ops_summary: str  # one-paragraph summary for ops team
    rejection_reasons: list[RejectionReason] = []
    line_item_breakdown: list[LineItemDecision] = []
    applied_rules: list[str] = []
    degraded_components: list[str] = []  # components that failed (TC011)
    early_stop: EarlyStopResult | None = None
    trace_id: str
