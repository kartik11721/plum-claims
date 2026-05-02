from __future__ import annotations
from ..models.decision import LineItemDecision
from .exclusions import filter_excluded_line_items


def apply_network_discount_then_copay(
    amount: float,
    hospital_name: str | None,
    category: str,
    policy: dict,
) -> tuple[float, float, float]:
    """
    Returns (approved_amount, discount_deducted, copay_deducted).

    ORDER IS CRITICAL (TC010): network discount FIRST, then copay on discounted amount.
    """
    network_hospitals = [h.lower() for h in policy.get("network_hospitals", [])]
    cat_cfg = policy.get("opd_categories", {}).get(category.lower(), {})

    # Step 1: Network discount
    discount_pct = 0.0
    if hospital_name and any(nh in hospital_name.lower() for nh in network_hospitals):
        discount_pct = cat_cfg.get("network_discount_percent", 0) / 100

    discounted = amount * (1 - discount_pct)
    discount_deducted = amount - discounted

    # Step 2: Co-pay on the discounted amount
    copay_pct = cat_cfg.get("copay_percent", 0) / 100
    copay_deducted = discounted * copay_pct
    approved = discounted - copay_deducted

    return (round(approved, 2), round(discount_deducted, 2), round(copay_deducted, 2))


def check_per_claim_limit(
    claimed_amount: float,
    policy: dict,
) -> tuple[bool, str | None]:
    """Returns (within_limit, reason_if_exceeded)."""
    limit = policy.get("coverage", {}).get("per_claim_limit", float("inf"))
    if claimed_amount > limit:
        return (
            False,
            f"Claimed amount ₹{claimed_amount:,.0f} exceeds the per-claim limit of ₹{limit:,.0f}.",
        )
    return (True, None)


def check_sub_limit(
    amount_after_deductions: float,
    category: str,
    ytd_amount: float,
    policy: dict,
) -> tuple[float, str | None]:
    """
    Returns (capped_amount, note_if_capped).

    Sub-limit caps this individual claim's approved amount.
    Annual OPD limit caps based on remaining annual budget (ytd_amount tracks total spending).
    These are independent caps — both may apply.
    """
    cat_cfg = policy.get("opd_categories", {}).get(category.lower(), {})
    sub_limit = cat_cfg.get("sub_limit", float("inf"))
    annual_limit = policy.get("coverage", {}).get("annual_opd_limit", float("inf"))

    # Sub-limit caps this individual claim
    claim_cap = min(amount_after_deductions, sub_limit)

    # Annual limit caps based on remaining annual budget
    remaining_annual = max(0.0, annual_limit - ytd_amount)
    final_amount = min(claim_cap, remaining_annual)

    notes = []
    if claim_cap < amount_after_deductions:
        notes.append(f"category sub-limit ₹{sub_limit:,.0f}")
    if remaining_annual < amount_after_deductions:
        notes.append(f"annual OPD limit remaining ₹{remaining_annual:,.0f} (YTD: ₹{ytd_amount:,.0f})")

    if notes:
        return (
            round(final_amount, 2),
            f"Approved amount capped at ₹{final_amount:,.0f} due to: {', '.join(notes)}.",
        )
    return (round(amount_after_deductions, 2), None)


def compute_line_item_coverage(
    line_items: list[dict],
    category: str,
    hospital_name: str | None,
    policy: dict,
) -> tuple[list[LineItemDecision], float]:
    """
    Returns (line_item_decisions, total_approved_amount).
    Handles category-specific exclusions at the line-item level (TC006 dental).
    """
    covered_items, excluded_items = filter_excluded_line_items(line_items, category)
    decisions: list[LineItemDecision] = []

    total_covered_amount = sum(item.get("amount", 0) for item in covered_items)

    # Apply discount/copay to covered total
    if total_covered_amount > 0:
        approved, discount, copay = apply_network_discount_then_copay(
            total_covered_amount, hospital_name, category, policy
        )
    else:
        approved = 0.0

    # Scale approved proportionally across line items
    for item in covered_items:
        item_amount = item.get("amount", 0)
        ratio = item_amount / total_covered_amount if total_covered_amount else 0
        item_approved = round(approved * ratio, 2)
        decisions.append(LineItemDecision(
            description=item.get("description", ""),
            claimed_amount=item_amount,
            approved_amount=item_approved,
            status="APPROVED",
        ))

    for item, reason in excluded_items:
        decisions.append(LineItemDecision(
            description=item.get("description", ""),
            claimed_amount=item.get("amount", 0),
            approved_amount=0.0,
            status="REJECTED",
            reason=f"Excluded under policy: {reason}",
        ))

    return decisions, round(approved, 2)
