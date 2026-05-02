from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    PHARMACY_BILL = "PHARMACY_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    OTHER = "OTHER"
    UNREADABLE = "UNREADABLE"


class PreParsedContent(BaseModel):
    """Pre-parsed document content for eval mode (skips vision pipeline)."""
    doctor_name: str | None = None
    doctor_registration: str | None = None
    patient_name: str | None = None
    date: str | None = None
    diagnosis: str | None = None
    treatment: str | None = None
    medicines: list[str] = []
    tests_ordered: list[str] = []
    hospital_name: str | None = None
    line_items: list[dict[str, Any]] = []
    total: float | None = None
    test_name: str | None = None
    # pharmacy-specific
    net_amount: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class UploadedDoc(BaseModel):
    file_id: str
    file_name: str | None = None
    actual_type: DocumentType | None = None  # ground truth in eval mode
    quality: str | None = None               # GOOD | DEGRADED | UNREADABLE (eval hint)
    patient_name_on_doc: str | None = None   # TC003 hint
    content: PreParsedContent | None = None  # populated in eval mode
    # Runtime: base64-encoded bytes when uploaded via multipart
    file_bytes: bytes | None = Field(default=None, exclude=True)
    mime_type: str | None = None


class ClaimHistoryEntry(BaseModel):
    claim_id: str
    date: str
    amount: float
    provider: str | None = None


class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: str  # ISO date string YYYY-MM-DD
    claimed_amount: float
    hospital_name: str | None = None
    ytd_claims_amount: float = 0.0
    claims_history: list[ClaimHistoryEntry] = []
    documents: list[UploadedDoc] = []
    # Eval flags
    simulate_component_failure: bool = False
