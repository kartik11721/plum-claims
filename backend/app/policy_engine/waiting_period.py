from __future__ import annotations
import re
from datetime import date, timedelta


# Maps diagnosis keywords → policy waiting period keys
DIAGNOSIS_KEYWORD_MAP: dict[str, str] = {
    "diabetes": "diabetes",
    "diabetic": "diabetes",
    "t2dm": "diabetes",
    "type 2 diabetes": "diabetes",
    "hyperglycemia": "diabetes",
    "hypertension": "hypertension",
    "htn": "hypertension",
    "high blood pressure": "hypertension",
    "thyroid": "thyroid_disorders",
    "hypothyroidism": "thyroid_disorders",
    "hyperthyroidism": "thyroid_disorders",
    "joint replacement": "joint_replacement",
    "knee replacement": "joint_replacement",
    "hip replacement": "joint_replacement",
    "maternity": "maternity",
    "pregnancy": "maternity",
    "delivery": "maternity",
    "mental health": "mental_health",
    "depression": "mental_health",
    "anxiety disorder": "mental_health",
    "psychiatric": "mental_health",
    "obesity": "obesity_treatment",
    "bariatric": "obesity_treatment",
    "morbid obesity": "obesity_treatment",
    "hernia": "hernia",
    "cataract": "cataract",
}


def _normalize(text: str) -> str:
    return text.lower().strip()


def _find_waiting_period_key(diagnoses: list[str], treatment: str | None) -> str | None:
    all_text = " ".join(diagnoses + ([treatment] if treatment else []))
    norm = _normalize(all_text)
    for keyword, policy_key in DIAGNOSIS_KEYWORD_MAP.items():
        # Use word-boundary matching to avoid "herniation" matching "hernia"
        if re.search(r'\b' + re.escape(keyword) + r'\b', norm):
            return policy_key
    return None


def check_waiting_period(
    join_date_str: str,
    treatment_date_str: str,
    diagnoses: list[str],
    treatment: str | None,
    policy: dict,
) -> tuple[bool, str | None, str | None]:
    """
    Returns (is_eligible, rejection_reason, eligibility_date_str).

    is_eligible=True  → no waiting period issue
    is_eligible=False → rejection_reason describes the waiting period
                        eligibility_date_str is when the member becomes eligible
    """
    join_date = date.fromisoformat(join_date_str)
    treatment_date = date.fromisoformat(treatment_date_str)
    wp = policy.get("waiting_periods", {})

    # 1. Initial waiting period
    initial_days = wp.get("initial_waiting_period_days", 30)
    initial_end = join_date + timedelta(days=initial_days)
    if treatment_date < initial_end:
        return (
            False,
            f"Treatment date {treatment_date_str} falls within the {initial_days}-day initial waiting period "
            f"(joined {join_date_str}).",
            initial_end.isoformat(),
        )

    # 2. Condition-specific waiting periods
    policy_key = _find_waiting_period_key(diagnoses, treatment)
    if policy_key:
        specific_days = wp.get("specific_conditions", {}).get(policy_key)
        if specific_days:
            eligibility_date = join_date + timedelta(days=specific_days)
            if treatment_date < eligibility_date:
                return (
                    False,
                    f"Diagnosis falls under the {specific_days}-day waiting period for '{policy_key}'. "
                    f"Member joined {join_date_str}; eligible from {eligibility_date.isoformat()}.",
                    eligibility_date.isoformat(),
                )

    return (True, None, None)
