from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from .claim import DocumentType


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    UNREADABLE = "UNREADABLE"


class IntakeResult(BaseModel):
    ok: bool
    member_name: str | None = None
    join_date: str | None = None
    reasons: list[str] = []


class DocClassification(BaseModel):
    file_id: str
    file_name: str | None = None
    classified_type: DocumentType
    confidence: float = 1.0


class ClassificationResult(BaseModel):
    ok: bool
    classifications: list[DocClassification] = []
    missing_required: list[DocumentType] = []
    unexpected: list[DocClassification] = []
    member_message: str | None = None  # populated when ok=False


class DocQualityResult(BaseModel):
    file_id: str
    file_name: str | None = None
    quality: DocumentQuality
    issue: str | None = None


class QualityResult(BaseModel):
    ok: bool
    per_doc: list[DocQualityResult] = []
    unreadable_files: list[str] = []
    member_message: str | None = None  # populated when ok=False


class IdentityCheckResult(BaseModel):
    ok: bool
    names_found: list[str] = []
    mismatch_pairs: list[dict] = []  # [{file_id, name_on_doc}]
    member_message: str | None = None  # populated when ok=False


class FraudSignals(BaseModel):
    same_day_count: int = 0
    monthly_count: int = 0
    high_value: bool = False
    document_alteration: bool = False
    fraud_score: float = 0.0
    flags: list[str] = []
    requires_manual_review: bool = False
