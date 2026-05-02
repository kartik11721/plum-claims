from __future__ import annotations
from collections import Counter
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

        # Check required documents — policy JSON is the source of truth; hardcoded dict is fallback only
        category = submission.claim_category.value
        policy_doc_reqs = self.policy.get("document_requirements", {}).get(category, {}).get("required", None)
        if policy_doc_reqs is not None:
            required = set(policy_doc_reqs)
        else:
            required = set(REQUIRED_DOCS_FOR_CATEGORY.get(category, []))

        found_types = {c.classified_type.value for c in classifications if c.classified_type != DocumentType.UNREADABLE}
        missing = [DocumentType(r) for r in required if r not in found_types]

        ok = len(missing) == 0
        member_message = None

        if not ok:
            uploaded_display = [
                _type_display(c.classified_type.value) for c in classifications
                if c.classified_type != DocumentType.UNREADABLE
            ]
            missing_type_names = [_type_display(m.value) for m in missing]
            required_display = [_type_display(r) for r in required]

            # Documents that could not be read
            unreadable_docs = [c for c in classifications if c.classified_type == DocumentType.UNREADABLE]

            # Docs whose type is not in required at all (and not UNREADABLE/OTHER)
            wrong_type_docs = [
                c for c in classifications
                if c.classified_type.value not in required
                and c.classified_type not in (DocumentType.OTHER, DocumentType.UNREADABLE)
            ]

            # Same required type submitted more than once (e.g. 2 prescriptions)
            type_counts = Counter(
                c.classified_type.value for c in classifications
                if c.classified_type not in (DocumentType.UNREADABLE, DocumentType.OTHER)
            )
            redundant_types = {t: cnt for t, cnt in type_counts.items() if t in required and cnt > 1}

            if unreadable_docs or wrong_type_docs or redundant_types:
                issue_sentences = []
                if unreadable_docs:
                    names = [c.file_name or c.file_id for c in unreadable_docs]
                    quoted = ", ".join(f'"{n}"' for n in names)
                    issue_sentences.append(f"{quoted} could not be read — please re-upload a clearer copy.")
                if wrong_type_docs:
                    wrong_names = [_type_display(c.classified_type.value) for c in wrong_type_docs]
                    joined = " and ".join(wrong_names) if len(wrong_names) <= 2 else ", ".join(wrong_names[:-1]) + f", and {wrong_names[-1]}"
                    verb = "is" if len(wrong_type_docs) == 1 else "are"
                    issue_sentences.append(f"{joined} {verb} not required for a {_type_display(category)} claim.")
                for t, cnt in redundant_types.items():
                    issue_sentences.append(f"You uploaded {cnt} copies of {_type_display(t)} — only one is needed.")

                issues_joined = " ".join(issue_sentences)

                if missing_type_names:
                    missing_joined = " and ".join(missing_type_names) if len(missing_type_names) <= 2 else ", ".join(missing_type_names[:-1]) + f", and {missing_type_names[-1]}"
                    action = f"Please also upload {missing_joined} and resubmit."
                else:
                    action = "Please correct the above and resubmit."

                member_message = (
                    f"We couldn't process your {_type_display(category)} claim. "
                    f"{issues_joined} "
                    f"{action}"
                )
            else:
                missing_joined = " and ".join(missing_type_names) if len(missing_type_names) <= 2 else ", ".join(missing_type_names[:-1]) + f", and {missing_type_names[-1]}"
                required_joined = " and ".join(required_display) if len(required_display) <= 2 else ", ".join(required_display[:-1]) + f", and {required_display[-1]}"
                was_were = "was" if len(missing_type_names) == 1 else "were"
                if not uploaded_display:
                    member_message = (
                        f"No readable documents were found. "
                        f"Your {_type_display(category)} claim requires a {required_joined}. "
                        "Please upload the required documents and resubmit."
                    )
                else:
                    member_message = (
                        f"Your {_type_display(category)} claim requires a {required_joined}, "
                        f"but {missing_joined} {was_were} not included. "
                        "Please upload the missing document(s) and resubmit."
                    )

        return ClassificationResult(
            ok=ok,
            classifications=classifications,
            missing_required=missing,
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
