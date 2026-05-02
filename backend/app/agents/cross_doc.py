from __future__ import annotations
from ..models.agents import IdentityCheckResult


def _normalize_name(name: str) -> str:
    return name.lower().strip()


def _names_match(a: str, b: str) -> bool:
    """Fuzzy name match: exact or one is a substring of the other."""
    na, nb = _normalize_name(a), _normalize_name(b)
    return na == nb or na in nb or nb in na


class CrossDocValidator:
    def validate(self, extracted_docs: list, member_name: str | None) -> IdentityCheckResult:
        names: list[tuple[str, str]] = []  # (file_id, name)

        for i, doc in enumerate(extracted_docs):
            patient_name = getattr(doc, "patient_name", None)
            if patient_name:
                file_id = f"doc_{i}"
                names.append((file_id, patient_name))

        if not names:
            # No names extractable — can't validate but don't block
            return IdentityCheckResult(ok=True, names_found=[], mismatch_pairs=[])

        all_names = [n for _, n in names]
        reference_name = member_name or all_names[0]

        mismatches = [
            {"file_id": fid, "name_on_doc": name}
            for fid, name in names
            if not _names_match(name, reference_name)
        ]

        if mismatches:
            names_str = "; ".join(f'"{n["name_on_doc"]}" (doc {n["file_id"]})' for n in mismatches)
            member_name_str = f'"{reference_name}"'
            member_message = (
                f"Document identity mismatch detected. "
                f"The member on this claim is {member_name_str}, but we found different patient names on your documents: {names_str}. "
                "All documents must belong to the same patient. "
                "Please re-upload documents for the correct patient."
            )
            return IdentityCheckResult(
                ok=False,
                names_found=all_names,
                mismatch_pairs=mismatches,
                member_message=member_message,
            )

        return IdentityCheckResult(ok=True, names_found=all_names, mismatch_pairs=[])
