from __future__ import annotations
from ..models.claim import ClaimSubmission
from ..models.agents import FraudSignals
from ..models.decision import (
    DecisionType,
    PolicyDecision,
    RejectionReason,
)
from .subagents import (
    MemberValidationAgent,
    ExclusionCheckerAgent,
    WaitingPeriodAgent,
    PreAuthCheckerAgent,
    PerClaimLimitAgent,
    BenefitCalculatorAgent,
    _docs_to_dicts,
)


class PolicyDecisionEngine:
    """
    Synchronous wrapper around the sub-agents used by PolicyOrchestratorAgent.
    Delegates every rule check to the same sub-agent instances so unit tests
    exercise the same code path as the production graph.

    Fraud routing is applied here (after benefit calculation); in the graph
    this is done by aggregate_decision_node after the parallel fraud + policy
    branches both complete.
    """

    def __init__(self, policy: dict):
        self.policy = policy
        self._member_validator = MemberValidationAgent(policy)
        self._exclusion_checker = ExclusionCheckerAgent(policy)
        self._wp_agent = WaitingPeriodAgent(policy)
        self._preauth_checker = PreAuthCheckerAgent(policy)
        self._limit_checker = PerClaimLimitAgent(policy)
        self._benefit_calculator = BenefitCalculatorAgent(policy)

    def decide(
        self,
        submission: ClaimSubmission,
        extracted_docs: list[dict],
        fraud_signals: FraudSignals,
        has_pre_auth: bool = False,
    ) -> PolicyDecision:
        dicts = _docs_to_dicts(extracted_docs)
        applied_rules: list[str] = []
        rejection_reasons: list[RejectionReason] = []

        # 1. Member validation
        ok, reject_reason, rules = self._member_validator.validate(
            submission.member_id, submission.claimed_amount
        )
        applied_rules.extend(rules)
        if not ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[reject_reason],
                applied_rules=applied_rules,
            )

        member = next(
            (m for m in self.policy.get("members", []) if m["member_id"] == submission.member_id),
            {},
        )
        join_date = member.get("join_date", "2024-04-01")
        category = submission.claim_category.value

        # 2. Exclusions
        exclusions, excl_rule = self._exclusion_checker.check(dicts, category)
        applied_rules.append(excl_rule)
        if exclusions and category not in ("DENTAL", "VISION"):
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.EXCLUDED_CONDITION],
                applied_rules=applied_rules,
            )

        # 3. Waiting period
        wp_ok, wp_rule, eligibility_date = self._wp_agent.check(dicts, submission, join_date)
        applied_rules.append(wp_rule)
        if not wp_ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.WAITING_PERIOD],
                applied_rules=applied_rules,
                eligibility_date=eligibility_date,
            )

        # 4. Pre-auth
        preauth_ok, preauth_rule = self._preauth_checker.check(dicts, submission, has_pre_auth)
        applied_rules.append(preauth_rule)
        if not preauth_ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.PRE_AUTH_MISSING],
                applied_rules=applied_rules,
                rejection_detail=preauth_rule.replace("Pre-auth check: ", ""),
            )

        # 5. Per-claim limit
        limit_ok, limit_rule = self._limit_checker.check(submission)
        applied_rules.append(limit_rule)
        if not limit_ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.PER_CLAIM_EXCEEDED],
                applied_rules=applied_rules,
                rejection_detail=limit_rule.replace("Per-claim limit check: ", ""),
            )

        # 6. Benefit calculation
        item_decisions, final_approved, net_discount, copay_val, calc_rules = (
            self._benefit_calculator.calculate(dicts, submission, exclusions)
        )
        applied_rules.extend(calc_rules)

        # Fraud routing
        manual_review_reasons: list[str] = []
        fraud_thresholds = self.policy.get("fraud_thresholds", {})
        if fraud_signals.requires_manual_review:
            manual_review_reasons.extend(fraud_signals.flags)
        auto_threshold = fraud_thresholds.get("auto_manual_review_above", 25_000)
        if submission.claimed_amount > auto_threshold:
            manual_review_reasons.append(
                f"High-value claim ₹{submission.claimed_amount:,.0f} exceeds auto-review threshold ₹{auto_threshold:,.0f}."
            )
        score_threshold = fraud_thresholds.get("fraud_score_manual_review_threshold", 0.80)
        if fraud_signals.fraud_score >= score_threshold:
            manual_review_reasons.append(
                f"Fraud score {fraud_signals.fraud_score:.2f} ≥ threshold {score_threshold}."
            )

        approved_items = [d for d in item_decisions if d.status == "APPROVED"]
        rejected_items = [d for d in item_decisions if d.status == "REJECTED"]

        if manual_review_reasons:
            applied_rules.append(f"Manual review triggered: {'; '.join(manual_review_reasons)}")
            decision = DecisionType.MANUAL_REVIEW
        elif rejected_items and approved_items:
            decision = DecisionType.PARTIAL
        elif rejected_items and not approved_items:
            decision = DecisionType.REJECTED
            rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
        else:
            decision = DecisionType.APPROVED

        return PolicyDecision(
            decision=decision,
            approved_amount=final_approved,
            line_item_breakdown=item_decisions,
            rejection_reasons=rejection_reasons,
            applied_rules=applied_rules,
            requires_manual_review=bool(manual_review_reasons),
            manual_review_reasons=manual_review_reasons,
            network_discount_applied=net_discount,
            copay_deducted=copay_val,
        )
