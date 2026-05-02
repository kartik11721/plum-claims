from __future__ import annotations
from typing import Annotated, Literal
from pydantic import BaseModel, Field


class FieldConfidence(BaseModel):
    value: str | float | None
    confidence: float = 1.0  # 0.0 – 1.0
    flagged: bool = False
    flag_reason: str | None = None


class LineItem(BaseModel):
    description: str
    amount: float
    quantity: float = 1.0
    batch: str | None = None
    expiry: str | None = None


class ExtractedPrescription(BaseModel):
    doc_type: Literal["PRESCRIPTION"] = "PRESCRIPTION"
    doctor_name: str | None = None
    doctor_registration: str | None = None
    doctor_specialization: str | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    patient_gender: str | None = None
    date: str | None = None
    hospital_clinic: str | None = None
    diagnosis: list[str] = []
    medicines: list[str] = []
    tests_ordered: list[str] = []
    treatment: str | None = None
    overall_confidence: float = 1.0
    quality_flags: list[str] = []  # e.g. HANDWRITTEN, STAMP_OVER_TEXT, PARTIAL_DOC


class ExtractedHospitalBill(BaseModel):
    doc_type: Literal["HOSPITAL_BILL"] = "HOSPITAL_BILL"
    hospital_name: str | None = None
    hospital_address: str | None = None
    gstin: str | None = None
    bill_number: str | None = None
    date: str | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    referring_doctor: str | None = None
    line_items: list[LineItem] = []
    subtotal: float | None = None
    gst_amount: float = 0.0
    total: float | None = None
    overall_confidence: float = 1.0
    quality_flags: list[str] = []


class ExtractedLabReport(BaseModel):
    doc_type: Literal["LAB_REPORT"] = "LAB_REPORT"
    lab_name: str | None = None
    nabl_accredited: bool | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    referring_doctor: str | None = None
    sample_date: str | None = None
    report_date: str | None = None
    tests: list[dict] = []  # [{name, result, unit, normal_range}]
    pathologist_name: str | None = None
    remarks: str | None = None
    overall_confidence: float = 1.0
    quality_flags: list[str] = []


class ExtractedPharmacyBill(BaseModel):
    doc_type: Literal["PHARMACY_BILL"] = "PHARMACY_BILL"
    pharmacy_name: str | None = None
    drug_license: str | None = None
    bill_number: str | None = None
    date: str | None = None
    patient_name: str | None = None
    prescribing_doctor: str | None = None
    line_items: list[LineItem] = []
    subtotal: float | None = None
    discount: float = 0.0
    net_amount: float | None = None
    overall_confidence: float = 1.0
    quality_flags: list[str] = []


class ExtractedGenericDoc(BaseModel):
    doc_type: Literal["OTHER"] = "OTHER"
    patient_name: str | None = None
    date: str | None = None
    raw_text_summary: str | None = None
    overall_confidence: float = 0.5
    quality_flags: list[str] = []


ExtractedDocument = Annotated[
    ExtractedPrescription
    | ExtractedHospitalBill
    | ExtractedLabReport
    | ExtractedPharmacyBill
    | ExtractedGenericDoc,
    Field(discriminator="doc_type"),
]
