from __future__ import annotations
"""
PolicyOrchestratorAgent — delegates policy rule evaluation to six specialised
sub-agents, each independently traceable:

  1. MemberValidationAgent   — member exists? policy active? minimum amount met?
  2. ExclusionCheckerAgent   — diagnoses / treatments excluded under policy?
  3. WaitingPeriodAgent      — treatment within a waiting period?
  4. PreAuthCheckerAgent     — pre-authorisation required and present?
  5. PerClaimLimitAgent      — per-claim financial cap exceeded?
  6. BenefitCalculatorAgent  — network discounts, co-pay, annual OPD cap.
"""
from ..models.claim import ClaimSubmission
from ..models.decision import PolicyDecision, RejectionReason, DecisionType
from ..models.trace import TraceStatus
from ..policy_engine.subagents import (
    MemberValidationAgent,
    ExclusionCheckerAgent,
    WaitingPeriodAgent,
    PreAuthCheckerAgent,
    PerClaimLimitAgent,
    BenefitCalculatorAgent,
    _docs_to_dicts,
)

__all__ = [
    "PolicyOrchestratorAgent",
    "MemberValidationAgent",
    "ExclusionCheckerAgent",
    "WaitingPeriodAgent",
    "PreAuthCheckerAgent",
    "PerClaimLimitAgent",
    "BenefitCalculatorAgent",
    "_docs_to_dicts",
]


class PolicyOrchestratorAgent:
    """
    Orchestrates policy rule evaluation by sequentially delegating to six
    specialised sub-agents, each of which emits its own trace event.

    Runs concurrently with FraudSignalAgent in the main graph (see ClaimGraph).
    Fraud-based routing (MANUAL_REVIEW) is applied by DecisionAggregatorNode
    after both branches complete.
    """

    def __init__(self, policy: dict) -> None:
        self.policy = policy
        self.member_validator = MemberValidationAgent(policy)
        self.exclusion_checker = ExclusionCheckerAgent(policy)
        self.wp_agent = WaitingPeriodAgent(policy)
        self.preauth_checker = PreAuthCheckerAgent(policy)
        self.limit_checker = PerClaimLimitAgent(policy)
        self.benefit_calculator = BenefitCalculatorAgent(policy)

    async def decide(
        self,
        submission: ClaimSubmission,
        extracted_docs: list,
        join_date: str,
        recorder,
        progress_queue,
    ) -> PolicyDecision:
        def _emit(agent: str, status: str) -> None:
            if progress_queue:
                try:
                    progress_queue.put_nowait({"type": "step", "step": agent, "status": status})
                except Exception:
                    pass

        def _record(agent: str, ok: bool, rules: list[str]) -> None:
            status = TraceStatus.OK if ok else TraceStatus.DEGRADED
            recorder.record(agent, status, 0.0, {}, {"rules_applied": rules})

        dicts = _docs_to_dicts(extracted_docs)
        applied_rules: list[str] = []
        rejection_reasons: list[RejectionReason] = []

        # ── Sub-agent 1: MemberValidationAgent ────────────────────────────
        _emit("MemberValidationAgent", "started")
        ok, reject_reason, rules = self.member_validator.validate(
            submission.member_id, submission.claimed_amount
        )
        applied_rules.extend(rules)
        _record("MemberValidationAgent", ok, rules)
        _emit("MemberValidationAgent", "done" if ok else "degraded")

        if not ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[reject_reason],
                applied_rules=applied_rules,
            )

        category = submission.claim_category.value

        # ── Sub-agent 2: ExclusionCheckerAgent ────────────────────────────
        _emit("ExclusionCheckerAgent", "started")
        exclusions, excl_rule = self.exclusion_checker.check(dicts, category)
        applied_rules.append(excl_rule)
        _record("ExclusionCheckerAgent", True, [excl_rule])
        _emit("ExclusionCheckerAgent", "done")

        if exclusions and category not in ("DENTAL", "VISION"):
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.EXCLUDED_CONDITION],
                applied_rules=applied_rules,
            )

        # ── Sub-agent 3: WaitingPeriodAgent ───────────────────────────────
        _emit("WaitingPeriodAgent", "started")
        wp_ok, wp_rule, eligibility_date = self.wp_agent.check(dicts, submission, join_date)
        applied_rules.append(wp_rule)
        _record("WaitingPeriodAgent", wp_ok, [wp_rule])
        _emit("WaitingPeriodAgent", "done" if wp_ok else "degraded")

        if not wp_ok:
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.WAITING_PERIOD],
                applied_rules=applied_rules,
                eligibility_date=eligibility_date,
            )

        # ── Sub-agent 4: PreAuthCheckerAgent ──────────────────────────────
        _emit("PreAuthCheckerAgent", "started")
        preauth_ok, preauth_rule = self.preauth_checker.check(dicts, submission, False)
        applied_rules.append(preauth_rule)
        _record("PreAuthCheckerAgent", preauth_ok, [preauth_rule])
        _emit("PreAuthCheckerAgent", "done" if preauth_ok else "degraded")

        if not preauth_ok:
            detail = preauth_rule.replace("Pre-auth check: ", "")
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.PRE_AUTH_MISSING],
                applied_rules=applied_rules,
                rejection_detail=detail,
            )

        # ── Sub-agent 5: PerClaimLimitAgent ───────────────────────────────
        _emit("PerClaimLimitAgent", "started")
        limit_ok, limit_rule = self.limit_checker.check(submission)
        applied_rules.append(limit_rule)
        _record("PerClaimLimitAgent", limit_ok, [limit_rule])
        _emit("PerClaimLimitAgent", "done" if limit_ok else "degraded")

        if not limit_ok:
            detail = limit_rule.replace("Per-claim limit check: ", "")
            return PolicyDecision(
                decision=DecisionType.REJECTED,
                approved_amount=0.0,
                rejection_reasons=[RejectionReason.PER_CLAIM_EXCEEDED],
                applied_rules=applied_rules,
                rejection_detail=detail,
            )

        # ── Sub-agent 6: BenefitCalculatorAgent ───────────────────────────
        _emit("BenefitCalculatorAgent", "started")
        item_decisions, final_approved, net_discount, copay_val, calc_rules = (
            self.benefit_calculator.calculate(dicts, submission, exclusions)
        )
        applied_rules.extend(calc_rules)
        _record("BenefitCalculatorAgent", True, calc_rules)
        _emit("BenefitCalculatorAgent", "done")

        approved_items = [d for d in item_decisions if d.status == "APPROVED"]
        rejected_items = [d for d in item_decisions if d.status == "REJECTED"]

        if rejected_items and approved_items:
            decision_type = DecisionType.PARTIAL
        elif rejected_items and not approved_items:
            decision_type = DecisionType.REJECTED
            rejection_reasons.append(RejectionReason.EXCLUDED_CONDITION)
        else:
            decision_type = DecisionType.APPROVED

        return PolicyDecision(
            decision=decision_type,
            approved_amount=final_approved,
            line_item_breakdown=item_decisions,
            rejection_reasons=rejection_reasons,
            applied_rules=applied_rules,
            network_discount_applied=net_discount,
            copay_deducted=copay_val,
        )
