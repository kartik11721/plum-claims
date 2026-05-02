from __future__ import annotations


HIGH_VALUE_TESTS_REQUIRING_PRE_AUTH = {"MRI", "CT Scan", "PET Scan"}

# Threshold above which imaging requires pre-auth
IMAGING_PRE_AUTH_THRESHOLD = 10_000.0


def _norm(text: str) -> str:
    return text.lower()


def check_pre_auth(
    line_items: list[dict],
    claimed_amount: float,
    has_pre_auth: bool,
    policy: dict,
) -> tuple[bool, str | None]:
    """
    Returns (pre_auth_ok, reason_if_missing).
    pre_auth_ok=True  → no pre-auth issue
    pre_auth_ok=False → pre-auth was required but not present
    """
    if has_pre_auth:
        return (True, None)

    pre_auth_cfg = policy.get("pre_authorization", {})
    required_for = pre_auth_cfg.get("required_for", [])
    threshold = policy.get("opd_categories", {}).get("diagnostic", {}).get("pre_auth_threshold", 10_000)

    item_descriptions = [item.get("description", "") for item in line_items]
    all_desc = " ".join(item_descriptions)

    for trigger in required_for:
        trigger_lower = _norm(trigger)
        # Check if any line item matches a pre-auth trigger
        for desc in item_descriptions:
            if _norm(desc) in trigger_lower or any(
                kw in _norm(desc) for kw in ["mri", "ct scan", "pet scan"]
            ):
                # Amount-based gate
                item_amount = next(
                    (i.get("amount", 0) for i in line_items if _norm(i.get("description", "")) in trigger_lower),
                    claimed_amount,
                )
                if item_amount > threshold or claimed_amount > threshold:
                    return (
                        False,
                        f"Pre-authorization is required for '{desc}' when amount exceeds ₹{threshold:,.0f}. "
                        f"Claimed amount: ₹{claimed_amount:,.0f}. "
                        "To resubmit: obtain pre-authorization from your insurer before the procedure, "
                        "then include the pre-auth reference number with your claim.",
                    )

    return (True, None)
