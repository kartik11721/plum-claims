from __future__ import annotations
"""
Six policy sub-agents: pure rule evaluation, no LLM calls, no async.
Used by PolicyOrchestratorAgent (with trace emission) and by
PolicyDecisionEngine (synchronous, for unit tests).
"""
from ..models.claim import ClaimSubmission
from ..models.decision import (
    DecisionType,
    LineItemDecision,
    PolicyDecision,
    RejectionReason,
)
from .exclusions import check_exclusions
from .waiting_period import check_waiting_period
from .pre_auth import check_pre_auth
from .calculator import (
    apply_network_discount_then_copay,
    check_per_claim_limit,
    compute_line_item_coverage,
)


def _docs_to_dicts(extracted_docs: list) -> list[dict]:
    result = []
    for doc in extracted_docs:
        if doc is None:
            continue
        if hasattr(doc, "model_dump"):
            result.append(doc.model_dump())
        elif isinstance(doc, dict):
            result.append(doc)
    return result


def _get_diagnoses(docs: list[dict]) -> list[str]:
    out: list[str] = []
    for d in docs:
        out.extend(d.get("diagnosis", []))
        t = d.get("treatment")
        if t:
            out.append(t)
    return [x for x in out if x]


def _get_treatment(docs: list[dict]) -> str | None:
    for d in docs:
        if isinstance(d, dict) and d.get("treatment"):
            return d["treatment"]
    return None


def _get_line_items(docs: list[dict]) -> list[dict]:
    items: list[dict] = []
    for d in docs:
        if isinstance(d, dict):
            items.extend(d.get("line_items", []))
    return items


class MemberValidationAgent:
    """Verifies member exists in roster, policy is active, and minimum amount met."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def validate(
        self, member_id: str, claimed_amount: float
    ) -> tuple[bool, RejectionReason | None, list[str]]:
        member = next(
            (m for m in self.policy.get("members", []) if m["member_id"] == member_id),
            None,
        )
        if not member:
            return False, RejectionReason.MEMBER_NOT_FOUND, [
                "Member lookup failed — member_id not found in policy roster."
            ]

        if self.policy.get("policy_holder", {}).get("renewal_status") != "ACTIVE":
            return False, RejectionReason.POLICY_INACTIVE, ["Policy is not active."]

        sub_rules = self.policy.get("submission_rules", {})
        min_amount = sub_rules.get("minimum_claim_amount", 0)
        if claimed_amount < min_amount:
            return False, RejectionReason.MINIMUM_AMOUNT_NOT_MET, [
                f"Claimed amount ₹{claimed_amount} is below minimum ₹{min_amount}."
            ]

        return True, None, [
            f"Member '{member_id}' ({member.get('name', 'unknown')}) validated.",
            "Policy status: ACTIVE.",
            f"Claimed amount ₹{claimed_amount:,.0f} meets minimum ₹{min_amount:,.0f}.",
        ]


class ExclusionCheckerAgent:
    """Checks whether diagnoses or treatments are excluded under the policy."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def check(
        self, extracted_dicts: list[dict], category: str
    ) -> tuple[list, str]:
        diagnoses = _get_diagnoses(extracted_dicts)
        treatment = _get_treatment(extracted_dicts)
        line_items = _get_line_items(extracted_dicts)

        exclusions = check_exclusions(diagnoses, treatment, line_items, category, self.policy)

        if exclusions and category not in ("DENTAL", "VISION"):
            names = [e[0] for e in exclusions]
            return exclusions, f"Exclusion check: matched — {', '.join(names)}"

        rule = (
            "Exclusion check: PASSED"
            if not exclusions
            else "Partial exclusions found (handled at line-item level)"
        )
        return exclusions, rule


class WaitingPeriodAgent:
    """Checks whether the treatment date falls within a waiting period."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def check(
        self,
        extracted_dicts: list[dict],
        submission: ClaimSubmission,
        join_date: str,
    ) -> tuple[bool, str, str | None]:
        diagnoses = _get_diagnoses(extracted_dicts)
        treatment = _get_treatment(extracted_dicts)

        eligible, reason, eligibility_date = check_waiting_period(
            join_date, submission.treatment_date, diagnoses, treatment, self.policy
        )
        rule = f"Waiting period check: {reason}" if not eligible else "Waiting period check: PASSED"
        return eligible, rule, eligibility_date


class PreAuthCheckerAgent:
    """Checks whether pre-authorisation is required and present."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def check(
        self,
        extracted_dicts: list[dict],
        submission: ClaimSubmission,
        has_pre_auth: bool,
    ) -> tuple[bool, str]:
        line_items = _get_line_items(extracted_dicts)
        ok, reason = check_pre_auth(
            line_items, submission.claimed_amount, has_pre_auth, self.policy
        )
        rule = f"Pre-auth check: {reason}" if not ok else "Pre-auth check: PASSED"
        return ok, rule


class PerClaimLimitAgent:
    """Checks per-claim financial cap (CONSULTATION only)."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def check(self, submission: ClaimSubmission) -> tuple[bool, str]:
        category = submission.claim_category.value
        if category != "CONSULTATION":
            return True, f"Per-claim limit check: N/A for {category}"

        ok, reason = check_per_claim_limit(submission.claimed_amount, self.policy)
        rule = f"Per-claim limit check: {reason}" if not ok else "Per-claim limit check: PASSED"
        return ok, rule


class BenefitCalculatorAgent:
    """Computes line-item coverage, network discounts, co-pay, and annual OPD cap."""

    def __init__(self, policy: dict) -> None:
        self.policy = policy

    def calculate(
        self,
        extracted_dicts: list[dict],
        submission: ClaimSubmission,
        exclusions: list,
    ) -> tuple[list[LineItemDecision], float, float, float, list[str]]:
        category = submission.claim_category.value
        line_items = _get_line_items(extracted_dicts)
        rules: list[str] = []
        network_discount = 0.0
        copay = 0.0

        if line_items and category in ("DENTAL", "VISION"):
            item_decisions, base_approved = compute_line_item_coverage(
                line_items, category, submission.hospital_name, self.policy
            )
            rules.append(
                f"Line-item coverage computed for {category}: {len(item_decisions)} items."
            )
        else:
            base_approved, network_discount, copay = apply_network_discount_then_copay(
                submission.claimed_amount, submission.hospital_name, category, self.policy
            )
            if network_discount > 0:
                rules.append(
                    f"Network discount applied: ₹{network_discount:,.2f} "
                    f"({network_discount / submission.claimed_amount * 100:.0f}%)"
                )
            if copay > 0:
                rules.append(f"Co-pay deducted: ₹{copay:,.2f}")

            item_decisions = [
                LineItemDecision(
                    description="Total claim",
                    claimed_amount=submission.claimed_amount,
                    approved_amount=base_approved,
                    status="APPROVED",
                )
            ]

        annual_limit = self.policy.get("coverage", {}).get("annual_opd_limit", float("inf"))
        remaining = max(0.0, annual_limit - submission.ytd_claims_amount)
        candidate = (
            base_approved
            if not (line_items and category in ("DENTAL", "VISION"))
            else sum(d.approved_amount for d in item_decisions)
        )
        final = min(candidate, remaining)
        if final < candidate:
            rules.append(
                f"Approved amount capped at ₹{final:,.0f} — annual OPD limit remaining "
                f"₹{remaining:,.0f} (YTD: ₹{submission.ytd_claims_amount:,.0f} of ₹{annual_limit:,.0f})."
            )

        return item_decisions, final, network_discount, copay, rules
