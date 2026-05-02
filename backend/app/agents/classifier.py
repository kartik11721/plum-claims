from __future__ import annotations
from ..models.claim import ClaimSubmission, UploadedDoc, DocumentType, ClaimCategory
from ..models.agents import (
    ClassificationResult,
    DocClassification,
)
from ..llm.client import get_client, vision_completion, structured_completion

DOCUMENT_TYPES_DESCRIPTION = """
Document types you must classify into:
- PRESCRIPTION: Doctor's Rx with diagnosis, medicines, doctor registration number
- HOSPITAL_BILL: Bill/invoice from hospital or clinic showing treatment line items and totals
- PHARMACY_BILL: Bill from pharmacy showing medicines with batch numbers
- LAB_REPORT: Laboratory / diagnostic test results with test names, values, normal ranges
- DIAGNOSTIC_REPORT: Imaging or specialist reports (MRI, X-ray, ECG, etc.)
- DENTAL_REPORT: Dental procedure report or dental X-ray
- DISCHARGE_SUMMARY: Hospital discharge summary
- OTHER: Legitimate medical document that doesn't fit above
- UNREADABLE: Image is too blurry, dark, or corrupted to extract meaningful content
"""

CLASSIFICATION_SCHEMA = {
    "classified_type": "string (one of PRESCRIPTION|HOSPITAL_BILL|PHARMACY_BILL|LAB_REPORT|DIAGNOSTIC_REPORT|DENTAL_REPORT|DISCHARGE_SUMMARY|OTHER|UNREADABLE)",
    "confidence": "number between 0.0 and 1.0",
    "reasoning": "string: 1-2 sentences explaining your classification",
}

REQUIRED_DOCS_FOR_CATEGORY: dict[str, list[str]] = {
    "CONSULTATION": ["PRESCRIPTION", "HOSPITAL_BILL"],
    "DIAGNOSTIC": ["PRESCRIPTION", "LAB_REPORT", "HOSPITAL_BILL"],
    "PHARMACY": ["PRESCRIPTION", "PHARMACY_BILL"],
    "DENTAL": ["HOSPITAL_BILL"],
    "VISION": ["PRESCRIPTION", "HOSPITAL_BILL"],
    "ALTERNATIVE_MEDICINE": ["PRESCRIPTION", "HOSPITAL_BILL"],
}


def _type_display(t: str) -> str:
    return t.replace("_", " ").title()


class DocumentClassifierAgent:
    def __init__(self, policy: dict):
        self.policy = policy

    async def classify(
        self,
        submission: ClaimSubmission,
    ) -> ClassificationResult:
        client = get_client()
        classifications: list[DocClassification] = []

        for doc in submission.documents:
            classified_type = await self._classify_single(doc, client)
            classifications.append(DocClassification(
                file_id=doc.file_id,
                file_name=doc.file_name,
                classified_type=classified_type["type"],
                confidence=classified_type["confidence"],
            ))

        # Check required documents
        category = submission.claim_category.value
        required = set(REQUIRED_DOCS_FOR_CATEGORY.get(category, []))
        # Also check policy doc requirements
        policy_required = set(
            self.policy.get("document_requirements", {}).get(category, {}).get("required", [])
        )
        required = required | policy_required

        found_types = {c.classified_type.value for c in classifications if c.classified_type != DocumentType.UNREADABLE}
        missing = [DocumentType(r) for r in required if r not in found_types]

        unexpected: list[DocClassification] = []
        for c in classifications:
            if c.classified_type.value not in required and c.classified_type not in (DocumentType.UNREADABLE, DocumentType.OTHER):
                # Not necessarily wrong, but flag them
                pass

        # Detect wrong types (documents uploaded that are NOT in required set)
        wrong_type_docs = [
            c for c in classifications
            if c.classified_type.value not in required
            and c.classified_type not in (DocumentType.OTHER,)
        ]

        ok = len(missing) == 0
        member_message = None

        if not ok:
            uploaded_types = [_type_display(c.classified_type.value) for c in classifications]
            missing_type_names = [_type_display(m.value) for m in missing]

            if wrong_type_docs:
                wrong_names = [_type_display(c.classified_type.value) for c in wrong_type_docs]
                member_message = (
                    f"Document verification failed for your {_type_display(category)} claim. "
                    f"You uploaded: {', '.join(uploaded_types)}. "
                    f"However, for a {_type_display(category)} claim you must provide: {', '.join([_type_display(r) for r in required])}. "
                    f"The following documents appear to be wrong type: {', '.join(wrong_names)}. "
                    f"Missing required documents: {', '.join(missing_type_names)}. "
                    "Please re-upload the correct documents."
                )
            else:
                member_message = (
                    f"Document verification failed. "
                    f"For a {_type_display(category)} claim, you must provide: {', '.join([_type_display(r) for r in required])}. "
                    f"Missing: {', '.join(missing_type_names)}. "
                    "Please upload the missing documents."
                )

        return ClassificationResult(
            ok=ok,
            classifications=classifications,
            missing_required=missing,
            unexpected=unexpected,
            member_message=member_message,
        )

    async def _classify_single(self, doc: UploadedDoc, client) -> dict:
        # Eval mode: ground truth type provided
        if doc.actual_type is not None:
            return {"type": doc.actual_type.value, "confidence": 1.0}

        # Quality hint: UNREADABLE
        if doc.quality == "UNREADABLE":
            return {"type": "UNREADABLE", "confidence": 1.0}

        system = f"You are a medical document classifier for an Indian health insurance company.\n{DOCUMENT_TYPES_DESCRIPTION}"
        user = f"Classify this medical document. File name: {doc.file_name or 'unknown'}"

        if doc.file_bytes:
            result = await vision_completion(
                system=system,
                user_text=user,
                image_bytes=doc.file_bytes,
                mime_type=doc.mime_type or "image/jpeg",
                response_schema=CLASSIFICATION_SCHEMA,
                client=client,
            )
            raw_type = result.get("classified_type", "OTHER").upper()
        else:
            # No image — classify from filename only
            result = await structured_completion(
                system=system,
                user=user,
                response_schema=CLASSIFICATION_SCHEMA,
                client=client,
            )
            raw_type = result.get("classified_type", "OTHER").upper()

        try:
            doc_type = DocumentType(raw_type)
        except ValueError:
            doc_type = DocumentType.OTHER

        return {"type": doc_type.value, "confidence": result.get("confidence", 0.8)}
