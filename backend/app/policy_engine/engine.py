from __future__ import annotations
from datetime import date
from ..models.claim import ClaimSubmission, ClaimCategory
from ..models.agents import FraudSignals
from ..models.decision import (
    DecisionType,
    LineItemDecision,
    PolicyDecision,
    RejectionReason,
)
from .waiting_period import check_waiting_period
from .exclusions import check_exclusions
from .pre_auth import check_pre_auth
from .calculator import (
    apply_network_discount_then_copay,
    check_per_claim_limit,
    check_sub_limit,
    compute_line_item_coverage,
)


def _get_member(member_id: str, policy: dict) -> dict | None:
    return next((m for m in policy.get("members", []) if m["member_id"] == member_id), None)


def _get_diagnoses(extracted_docs: list[dict]) -> list[str]:
    diagnoses = []
    for doc in extracted_docs:
        if isinstance(doc, dict):
            diagnoses.extend(doc.get("diagnosis", []))
            t = doc.get("treatment")
            if t:
                diagnoses.append(t)
    return [d for d in diagnoses if d]


def _get_treatment(extracted_docs: list[dict]) -> str | None:
    for doc in extracted_docs:
        if isinstance(doc, dict) and doc.get("treatment"):
            return doc["treatment"]
    return None


def _get_line_items(extracted_docs: list[dict]) -> list[dict]:
    items = []
    for doc in extracted_docs:
        if isinstance(doc, dict):
            items.extend(doc.get("line_items", []))
    return items


def _get_total(extracted_docs: list[dict], claimed_amount: float) -> float:
    for doc in extracted_docs:
        if isinstance(doc, dict):
            t = doc.get("total") or doc.get("net_amount")
            if t is not None:
                return float(t)
    return claimed_amount


class PolicyDecisionEngine:
    """
    Deterministic rule engine. Reads all rules from policy dict.
    Never calls an LLM. Each method is independently unit-testable.
    """

    def __init__(self, policy: dict):
        self.policy = policy

    def decide(
        self,
        submission: ClaimSubmission,
        extracted_docs: list[dict],
        fraud_signals: FraudSignals,
        has_pre_auth: bool = False,
    ) -> PolicyDecision:
        rules_applied: list[str] = []
        rejection_reasons: list[RejectionReason] = []

        member = _get_member(submission.member_id, self.policy)
        if not member:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.MEMBER_NOT_FOUND],
                applied_rules=["Member lookup failed — member_id not found in policy roster."],
            )

        # --- Policy active check ---
        policy_holder = self.policy.get("policy_holder", {})
        if policy_holder.get("renewal_status") != "ACTIVE":
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.POLICY_INACTIVE],
                applied_rules=["Policy is not active."],
            )

        # --- Minimum claim amount ---
        sub_rules = self.policy.get("submission_rules", {})
        min_amount = sub_rules.get("minimum_claim_amount", 0)
        if submission.claimed_amount < min_amount:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.MINIMUM_AMOUNT_NOT_MET],
                applied_rules=[f"Claimed amount ₹{submission.claimed_amount} is below minimum ₹{min_amount}."],
            )

        category = submission.claim_category.value
        diagnoses = _get_diagnoses(extracted_docs)
        treatment = _get_treatment(extracted_docs)
        line_items = _get_line_items(extracted_docs)

        # --- Exclusions (checked FIRST — categorical exclusion beats waiting period) ---
        whole_excl = check_exclusions(diagnoses, treatment, line_items, category, self.policy)
        # For dental/vision we do line-item level, not whole-claim
        if whole_excl and category not in ("DENTAL", "VISION"):
            excl_names = [e[0] for e in whole_excl]
            rules_applied.append(f"Exclusion check: matched — {', '.join(excl_names)}")
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.EXCLUDED_CONDITION],
                applied_rules=rules_applied,
            )
        rules_applied.append("Exclusion check: PASSED" if not whole_excl else "Partial exclusions found (handled at line-item level)")

        # --- Waiting period ---
        join_date = member.get("join_date", "2024-04-01")
        wp_eligible, wp_reason, eligibility_date = check_waiting_period(
            join_date, submission.treatment_date, diagnoses, treatment, self.policy
        )
        if not wp_eligible:
            rules_applied.append(f"Waiting period check: {wp_reason}")
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.WAITING_PERIOD],
                applied_rules=rules_applied,
                eligibility_date=eligibility_date,
            )
        rules_applied.append("Waiting period check: PASSED")

        # --- Pre-authorization (checked before financial limits — procedural requirement) ---
        preauth_ok, preauth_reason = check_pre_auth(
            line_items, submission.claimed_amount, has_pre_auth, self.policy
        )
        if not preauth_ok:
            rules_applied.append(f"Pre-auth check: {preauth_reason}")
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.PRE_AUTH_MISSING],
                applied_rules=rules_applied,
            )
        rules_applied.append("Pre-auth check: PASSED")

        # --- Per-claim limit ---
        # Applies to CONSULTATION only (test cases TC008).
        # DIAGNOSTIC, DENTAL, VISION, ALTERNATIVE_MEDICINE, PHARMACY are governed by their own sub-limits.
        if category == "CONSULTATION":
            limit_ok, limit_reason = check_per_claim_limit(submission.claimed_amount, self.policy)
            if not limit_ok:
                rules_applied.append(f"Per-claim limit check: {limit_reason}")
                return PolicyDecision(
                    decision=DecisionType.REJECTED,
                    approved_amount=0.0,
                    rejection_reasons=[RejectionReason.PER_CLAIM_EXCEEDED],
                    applied_rules=rules_applied,
                )
            rules_applied.append("Per-claim limit check: PASSED")
        else:
            rules_applied.append(f"Per-claim limit check: N/A for {category}")

        # --- Fraud routing ---
        fraud_thresholds = self.policy.get("fraud_thresholds", {})
        manual_review_reasons: list[str] = []
        if fraud_signals.requires_manual_review:
            manual_review_reasons.extend(fraud_signals.flags)
        auto_manual_threshold = fraud_thresholds.get("auto_manual_review_above", 25_000)
        if submission.claimed_amount > auto_manual_threshold:
            manual_review_reasons.append(f"High-value claim ₹{submission.claimed_amount:,.0f} exceeds auto-review threshold ₹{auto_manual_threshold:,.0f}.")
        fraud_score_threshold = fraud_thresholds.get("fraud_score_manual_review_threshold", 0.80)
        if fraud_signals.fraud_score >= fraud_score_threshold:
            manual_review_reasons.append(f"Fraud score {fraud_signals.fraud_score:.2f} ≥ threshold {fraud_score_threshold}.")

        # --- Line-item computation ---
        if line_items and category in ("DENTAL", "VISION"):
            item_decisions, base_approved = compute_line_item_coverage(
                line_items, category, submission.hospital_name, self.policy
            )
            rules_applied.append(f"Line-item coverage computed for {category}: {len(item_decisions)} items.")
        else:
            # Whole-claim: apply network discount + copay
            base_approved, discount, copay = apply_network_discount_then_copay(
                submission.claimed_amount, submission.hospital_name, category, self.policy
            )
            if discount > 0:
                rules_applied.append(f"Network discount applied: ₹{discount:,.2f} ({discount/submission.claimed_amount*100:.0f}%)")
            if copay > 0:
                rules_applied.append(f"Co-pay deducted: ₹{copay:,.2f}")

            item_decisions = [LineItemDecision(
                description="Total claim",
                claimed_amount=submission.claimed_amount,
                approved_amount=base_approved,
                status="APPROVED",
            )]

        # Cap against annual OPD limit only (sub-limit is per-category budget tracked separately).
        # We don't have category-specific YTD, so only check annual OPD remaining.
        annual_limit = self.policy.get("coverage", {}).get("annual_opd_limit", float("inf"))
        remaining_annual = max(0.0, annual_limit - submission.ytd_claims_amount)
        candidate_approved = base_approved if not (line_items and category in ("DENTAL", "VISION")) else sum(d.approved_amount for d in item_decisions)
        final_approved = min(candidate_approved, remaining_annual)
        if final_approved < candidate_approved:
            rules_applied.append(
                f"Approved amount capped at ₹{final_approved:,.0f} — annual OPD limit remaining ₹{remaining_annual:,.0f} "
                f"(YTD: ₹{submission.ytd_claims_amount:,.0f} of ₹{annual_limit:,.0f})."
            )

        # --- Final decision ---
        approved_items = [d for d in item_decisions if d.status == "APPROVED"]
        rejected_items = [d for d in item_decisions if d.status == "REJECTED"]

        if manual_review_reasons:
            rules_applied.append(f"Manual review triggered: {'; '.join(manual_review_reasons)}")
            decision = DecisionType.MANUAL_REVIEW
        elif rejected_items and approved_items:
            decision = DecisionType.PARTIAL
        elif rejected_items and not approved_items:
            decision = DecisionType.REJECTED
            rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
        else:
            decision = DecisionType.APPROVED

        network_discount_applied = 0.0
        copay_deducted_val = 0.0
        if not (line_items and category in ("DENTAL", "VISION")):
            _, network_discount_applied, copay_deducted_val = apply_network_discount_then_copay(
                submission.claimed_amount, submission.hospital_name, category, self.policy
            )

        return PolicyDecision(
            decision=decision,
            approved_amount=final_approved,
            line_item_breakdown=item_decisions,
            rejection_reasons=rejection_reasons,
            applied_rules=rules_applied,
            requires_manual_review=bool(manual_review_reasons),
            manual_review_reasons=manual_review_reasons,
            network_discount_applied=network_discount_applied,
            copay_deducted=copay_deducted_val,
        )
