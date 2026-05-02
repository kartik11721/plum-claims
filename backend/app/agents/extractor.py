from __future__ import annotations
import asyncio
from ..models.claim import UploadedDoc, DocumentType
from ..models.extraction import (
    ExtractedPrescription,
    ExtractedHospitalBill,
    ExtractedLabReport,
    ExtractedPharmacyBill,
    ExtractedGenericDoc,
    LineItem,
)
from ..llm.client import get_client, vision_completion, structured_completion

PRESCRIPTION_SCHEMA = {
    "doctor_name": "string or null",
    "doctor_registration": "string or null (format: STATE/XXXXX/YYYY)",
    "doctor_specialization": "string or null",
    "patient_name": "string or null",
    "patient_age": "string or null",
    "patient_gender": "string or null",
    "date": "string or null (YYYY-MM-DD if parseable)",
    "hospital_clinic": "string or null",
    "diagnosis": ["list of diagnosis strings"],
    "medicines": ["list of medicine name + dosage strings"],
    "tests_ordered": ["list of test names"],
    "treatment": "string or null",
    "overall_confidence": "number 0.0-1.0",
    "quality_flags": ["HANDWRITTEN | STAMP_OVER_TEXT | PARTIAL_DOC | MULTILINGUAL | DOCUMENT_ALTERATION"],
}

HOSPITAL_BILL_SCHEMA = {
    "hospital_name": "string or null",
    "hospital_address": "string or null",
    "gstin": "string or null",
    "bill_number": "string or null",
    "date": "string or null (YYYY-MM-DD if parseable)",
    "patient_name": "string or null",
    "patient_age": "string or null",
    "referring_doctor": "string or null",
    "line_items": [{"description": "string", "amount": "number", "quantity": "number"}],
    "subtotal": "number or null",
    "gst_amount": "number (0 if not applicable)",
    "total": "number or null",
    "overall_confidence": "number 0.0-1.0",
    "quality_flags": ["HANDWRITTEN | STAMP_OVER_TEXT | PARTIAL_DOC | DOCUMENT_ALTERATION"],
}

LAB_REPORT_SCHEMA = {
    "lab_name": "string or null",
    "nabl_accredited": "boolean or null",
    "patient_name": "string or null",
    "patient_age": "string or null",
    "referring_doctor": "string or null",
    "sample_date": "string or null",
    "report_date": "string or null",
    "tests": [{"name": "string", "result": "string", "unit": "string or null", "normal_range": "string or null"}],
    "pathologist_name": "string or null",
    "remarks": "string or null",
    "overall_confidence": "number 0.0-1.0",
    "quality_flags": [],
}

PHARMACY_BILL_SCHEMA = {
    "pharmacy_name": "string or null",
    "drug_license": "string or null",
    "bill_number": "string or null",
    "date": "string or null",
    "patient_name": "string or null",
    "prescribing_doctor": "string or null",
    "line_items": [{"description": "string", "amount": "number", "batch": "string or null", "expiry": "string or null", "quantity": "number"}],
    "subtotal": "number or null",
    "discount": "number",
    "net_amount": "number or null",
    "overall_confidence": "number 0.0-1.0",
    "quality_flags": [],
}

SCHEMA_MAP = {
    DocumentType.PRESCRIPTION: (PRESCRIPTION_SCHEMA, "prescription"),
    DocumentType.HOSPITAL_BILL: (HOSPITAL_BILL_SCHEMA, "hospital bill"),
    DocumentType.LAB_REPORT: (LAB_REPORT_SCHEMA, "lab report"),
    DocumentType.PHARMACY_BILL: (PHARMACY_BILL_SCHEMA, "pharmacy bill"),
}

EXTRACTION_SYSTEM = """You are a medical document information extractor for an Indian health insurance claims processor.
Extract information precisely. For fields you cannot read or find, use null.
For Indian doctor registration numbers, the format is STATE_CODE/NNNNN/YYYY (e.g. KA/45678/2015).
Diagnoses may use medical shorthand: HTN=Hypertension, T2DM=Type 2 Diabetes Mellitus, etc.
Dates should be converted to YYYY-MM-DD format where possible.
For overall_confidence: 0.9+ means high quality, 0.6-0.9 means some fields unclear, below 0.6 means many fields unreadable.
"""


def _pre_parsed_to_prescription(content) -> ExtractedPrescription:
    return ExtractedPrescription(
        doctor_name=content.doctor_name,
        doctor_registration=content.doctor_registration,
        patient_name=content.patient_name,
        date=content.date,
        diagnosis=([content.diagnosis] if isinstance(content.diagnosis, str) else []) if content.diagnosis else [],
        medicines=content.medicines,
        tests_ordered=content.tests_ordered,
        treatment=content.treatment,
        overall_confidence=1.0,
    )


def _pre_parsed_to_hospital_bill(content) -> ExtractedHospitalBill:
    line_items = [
        LineItem(description=item.get("description", ""), amount=item.get("amount", 0))
        for item in content.line_items
    ]
    return ExtractedHospitalBill(
        hospital_name=content.hospital_name,
        patient_name=content.patient_name,
        date=content.date,
        line_items=line_items,
        total=content.total,
        overall_confidence=1.0,
    )


def _pre_parsed_to_pharmacy_bill(content) -> ExtractedPharmacyBill:
    line_items = [
        LineItem(description=item.get("description", ""), amount=item.get("amount", 0))
        for item in content.line_items
    ]
    return ExtractedPharmacyBill(
        patient_name=content.patient_name,
        line_items=line_items,
        net_amount=content.net_amount or content.total,
        overall_confidence=1.0,
    )


def _pre_parsed_to_lab_report(content) -> ExtractedLabReport:
    return ExtractedLabReport(
        patient_name=content.patient_name,
        tests=[{"name": content.test_name}] if content.test_name else [],
        overall_confidence=1.0,
    )


class ExtractionAgent:
    def __init__(self):
        self.client = get_client()

    async def extract_all(self, documents: list[UploadedDoc], classifications: list) -> list:
        tasks = [
            self._extract_single(doc, cls)
            for doc, cls in zip(documents, classifications)
        ]
        return await asyncio.gather(*tasks)

    async def _extract_single(self, doc: UploadedDoc, classification) -> object:
        doc_type = classification.classified_type

        # Eval mode: patient_name hint from test case metadata
        if doc.patient_name_on_doc and doc.content is None and not doc.file_bytes:
            return ExtractedGenericDoc(
                patient_name=doc.patient_name_on_doc,
                overall_confidence=1.0,
            )

        # Eval mode: pre-parsed content available
        if doc.content is not None:
            c = doc.content
            if doc_type == DocumentType.PRESCRIPTION:
                return _pre_parsed_to_prescription(c)
            elif doc_type == DocumentType.HOSPITAL_BILL:
                return _pre_parsed_to_hospital_bill(c)
            elif doc_type == DocumentType.PHARMACY_BILL:
                return _pre_parsed_to_pharmacy_bill(c)
            elif doc_type in (DocumentType.LAB_REPORT, DocumentType.DIAGNOSTIC_REPORT):
                return _pre_parsed_to_lab_report(c)

        if doc_type not in SCHEMA_MAP or not doc.file_bytes:
            return ExtractedGenericDoc(patient_name=None, overall_confidence=0.5)

        schema, doc_label = SCHEMA_MAP[doc_type]
        user = f"Extract all information from this {doc_label}. Follow Indian medical document conventions."

        try:
            if doc.file_bytes:
                result = await vision_completion(
                    system=EXTRACTION_SYSTEM,
                    user_text=user,
                    image_bytes=doc.file_bytes,
                    mime_type=doc.mime_type or "image/jpeg",
                    response_schema=schema,
                    client=self.client,
                )
            else:
                result = await structured_completion(
                    system=EXTRACTION_SYSTEM,
                    user=user,
                    response_schema=schema,
                    client=self.client,
                )
        except Exception:
            return ExtractedGenericDoc(overall_confidence=0.3, quality_flags=["EXTRACTION_FAILED"])

        return self._parse_result(doc_type, result)

    def _parse_result(self, doc_type: DocumentType, result: dict) -> object:
        try:
            if doc_type == DocumentType.PRESCRIPTION:
                return ExtractedPrescription(**{k: result.get(k) for k in ExtractedPrescription.model_fields if k != "doc_type"})
            elif doc_type == DocumentType.HOSPITAL_BILL:
                raw_items = result.get("line_items", [])
                items = [LineItem(**{k: v for k, v in item.items() if k in LineItem.model_fields}) for item in raw_items if isinstance(item, dict)]
                data = {k: result.get(k) for k in ExtractedHospitalBill.model_fields if k not in ("doc_type", "line_items")}
                return ExtractedHospitalBill(line_items=items, **data)
            elif doc_type == DocumentType.LAB_REPORT:
                return ExtractedLabReport(**{k: result.get(k) for k in ExtractedLabReport.model_fields if k != "doc_type"})
            elif doc_type == DocumentType.PHARMACY_BILL:
                raw_items = result.get("line_items", [])
                items = [LineItem(**{k: v for k, v in item.items() if k in LineItem.model_fields}) for item in raw_items if isinstance(item, dict)]
                data = {k: result.get(k) for k in ExtractedPharmacyBill.model_fields if k not in ("doc_type", "line_items")}
                return ExtractedPharmacyBill(line_items=items, **data)
        except Exception:
            pass
        return ExtractedGenericDoc(overall_confidence=0.4, quality_flags=["PARSE_ERROR"])
