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
from ..models.decision import (
    DecisionType,
    LineItemDecision,
    PolicyDecision,
    RejectionReason,
)
from ..models.trace import TraceStatus
from ..policy_engine.exclusions import check_exclusions
from ..policy_engine.waiting_period import check_waiting_period
from ..policy_engine.pre_auth import check_pre_auth
from ..policy_engine.calculator import (
    apply_network_discount_then_copay,
    check_per_claim_limit,
    compute_line_item_coverage,
)


# ── Helpers (shared by sub-agents) ────────────────────────────────────────────

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


# ── Sub-agents ────────────────────────────────────────────────────────────────

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

        # Annual OPD cap
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


# ── PolicyOrchestratorAgent ───────────────────────────────────────────────────

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

        # Assemble final decision type from line-item results
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
