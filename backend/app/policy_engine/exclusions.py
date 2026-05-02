from __future__ import annotations


# Maps policy exclusion strings → normalized keywords for matching
EXCLUSION_KEYWORD_MAP: dict[str, list[str]] = {
    "Self-inflicted injuries": ["self-inflicted", "self inflicted"],
    "Substance abuse treatment": ["substance abuse", "alcohol", "drug addiction", "detox"],
    "Experimental treatments": ["experimental", "clinical trial"],
    "Infertility and assisted reproduction": ["infertility", "ivf", "iui", "assisted reproduction"],
    "Obesity and weight loss programs": [
        "obesity", "weight loss", "bariatric", "morbid obesity", "bmi", "diet program",
        "nutrition program", "weight management",
    ],
    "Bariatric surgery": ["bariatric surgery", "gastric bypass", "sleeve gastrectomy"],
    "Cosmetic or aesthetic procedures": [
        "cosmetic", "aesthetic", "rhinoplasty", "liposuction", "facelift",
        "breast augmentation",
    ],
    "Vaccination (non-medically necessary)": ["vaccination", "vaccine", "immunization"],
    "Health supplements and tonics": ["supplement", "tonic", "multivitamin", "protein powder"],
}

DENTAL_EXCLUSION_MAP: dict[str, list[str]] = {
    "Teeth Whitening": ["teeth whitening", "whitening", "bleaching"],
    "Orthodontic Treatment (Braces)": ["orthodontic", "braces", "aligner", "invisalign"],
    "Cosmetic dental procedures": ["cosmetic dental", "veneers", "dental veneer"],
    "Implants (Cosmetic)": ["implant", "dental implant"],
}

VISION_EXCLUSION_MAP: dict[str, list[str]] = {
    "LASIK Surgery": ["lasik", "refractive surgery", "laser eye"],
    "Cosmetic Eye Surgery": ["cosmetic eye"],
}


def _norm(text: str) -> str:
    return text.lower().strip()


def _matches_any(text: str, keywords: list[str]) -> bool:
    n = _norm(text)
    return any(k in n for k in keywords)


def check_exclusions(
    diagnoses: list[str],
    treatment: str | None,
    line_items: list[dict],
    category: str,
    policy: dict,
) -> list[tuple[str, str]]:
    """
    Returns list of (exclusion_name, matched_text) tuples for all matched exclusions.
    Empty list means nothing is excluded.
    """
    all_clinical_text = " ".join(diagnoses + ([treatment] if treatment else []))
    item_texts = [item.get("description", "") for item in line_items]
    all_text = all_clinical_text + " " + " ".join(item_texts)

    matched: list[tuple[str, str]] = []

    # General policy exclusions
    for exclusion_name, keywords in EXCLUSION_KEYWORD_MAP.items():
        if _matches_any(all_text, keywords):
            matched.append((exclusion_name, all_text[:100]))

    # Category-specific
    if category == "DENTAL":
        for excl, keywords in DENTAL_EXCLUSION_MAP.items():
            if _matches_any(all_text, keywords):
                matched.append((excl, all_text[:100]))

    if category == "VISION":
        for excl, keywords in VISION_EXCLUSION_MAP.items():
            if _matches_any(all_text, keywords):
                matched.append((excl, all_text[:100]))

    return matched


def filter_excluded_line_items(
    line_items: list[dict],
    category: str,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """
    Returns (covered_items, [(excluded_item, reason)]).
    Operates at the line-item level for dental partial approvals (TC006).
    """
    covered = []
    excluded = []

    excl_map = {}
    if category == "DENTAL":
        excl_map = DENTAL_EXCLUSION_MAP
    elif category == "VISION":
        excl_map = VISION_EXCLUSION_MAP

    for item in line_items:
        desc = item.get("description", "")
        hit = None
        for excl_name, keywords in excl_map.items():
            if _matches_any(desc, keywords):
                hit = excl_name
                break
        if hit:
            excluded.append((item, hit))
        else:
            covered.append(item)

    return covered, excluded
