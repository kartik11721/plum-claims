from __future__ import annotations
from ..models.claim import UploadedDoc
from ..models.agents import QualityResult, DocQualityResult, DocumentQuality
from ..llm.client import get_client, vision_completion, structured_completion

QUALITY_SCHEMA = {
    "quality": "string: GOOD | DEGRADED | UNREADABLE",
    "issue": "string or null: brief description if quality is DEGRADED or UNREADABLE",
}


class DocumentQualityAgent:
    async def check(self, documents: list[UploadedDoc]) -> QualityResult:
        client = get_client()
        per_doc: list[DocQualityResult] = []

        for doc in documents:
            quality, issue = await self._check_single(doc, client)
            per_doc.append(DocQualityResult(
                file_id=doc.file_id,
                file_name=doc.file_name,
                quality=quality,
                issue=issue,
            ))

        unreadable = [d.file_name or d.file_id for d in per_doc if d.quality == DocumentQuality.UNREADABLE]
        ok = len(unreadable) == 0

        member_message = None
        if not ok:
            file_list = ", ".join(f'"{f}"' for f in unreadable)
            member_message = (
                f"We could not read the following document(s): {file_list}. "
                "Please re-upload a clearer version — ensure good lighting, the document is flat, "
                "and all text is visible. Your claim cannot be processed until legible documents are provided."
            )

        return QualityResult(ok=ok, per_doc=per_doc, unreadable_files=unreadable, member_message=member_message)

    async def _check_single(self, doc: UploadedDoc, client) -> tuple[DocumentQuality, str | None]:
        # Eval mode quality hint
        if doc.quality:
            q_map = {"GOOD": DocumentQuality.GOOD, "DEGRADED": DocumentQuality.DEGRADED, "UNREADABLE": DocumentQuality.UNREADABLE}
            return q_map.get(doc.quality.upper(), DocumentQuality.GOOD), None

        if not doc.file_bytes:
            return DocumentQuality.GOOD, None

        system = "You are assessing the readability of an uploaded medical document image."
        user = "Rate the readability of this document. Is it GOOD (all text readable), DEGRADED (some text unclear), or UNREADABLE (too blurry/dark to extract meaningful content)?"

        result = await vision_completion(
            system=system,
            user_text=user,
            image_bytes=doc.file_bytes,
            mime_type=doc.mime_type or "image/jpeg",
            response_schema=QUALITY_SCHEMA,
            client=client,
        )
        q_str = result.get("quality", "GOOD").upper()
        try:
            quality = DocumentQuality(q_str)
        except ValueError:
            quality = DocumentQuality.GOOD
        return quality, result.get("issue")
