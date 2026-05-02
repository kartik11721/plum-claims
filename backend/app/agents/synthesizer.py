from __future__ import annotations
from ..models.claim import ClaimSubmission
from ..models.decision import PolicyDecision, FinalDecision, DecisionType, RejectionReason
from ..models.agents import FraudSignals
from ..llm.client import get_client, structured_completion

SYNTHESIZER_SYSTEM = """You are an insurance claims decision summarizer.
Given a structured claims decision with all the rules that were applied,
write a clear, specific, empathetic member-facing message and a concise ops-team summary.
Be specific about amounts, dates, and rule names — do not be vague.

MANDATORY RULES:
- If rejection reason is WAITING_PERIOD and an Eligibility Date is given, you MUST state that exact date \
in the member message (e.g. "You will be eligible for this condition from <date>.").
- If rejection reason is PRE_AUTH_MISSING and a Rejection Detail is given, you MUST include the \
resubmission instructions from that detail verbatim in the member message.
- If rejection reason is PER_CLAIM_EXCEEDED and a Rejection Detail is given, you MUST state both the \
claimed amount and the per-claim limit from that detail in the member message.
- Never omit the eligibility date, resubmission instructions, or limit amounts when they are provided.
"""

MESSAGE_SCHEMA = {
    "member_message": "string: 2-4 sentences for the member explaining the decision and what to do next",
    "ops_summary": "string: 1-2 sentences for the operations team explaining what was checked and why the decision was made",
}


class DecisionSynthesizer:
    def __init__(self):
        self.client = get_client()

    async def synthesize(
        self,
        claim_id: str,
        trace_id: str,
        submission: ClaimSubmission,
        policy_decision: PolicyDecision,
        extraction_confidence: float,
        degradation_factor: float,
        degraded_components: list[str],
    ) -> FinalDecision:
        confidence = min(extraction_confidence, 1.0) * degradation_factor

        # Generate member message and ops summary via LLM
        try:
            decision_context = (
                f"Claim: {submission.claim_category.value} for member {submission.member_id}\n"
                f"Claimed: ₹{submission.claimed_amount:,.0f}\n"
                f"Decision: {policy_decision.decision.value}\n"
                f"Approved Amount: ₹{policy_decision.approved_amount:,.0f}\n"
                f"Rules Applied: {chr(10).join(policy_decision.applied_rules)}\n"
                f"Rejection Reasons: {[r.value for r in policy_decision.rejection_reasons]}\n"
                f"Eligibility Date: {policy_decision.eligibility_date or 'N/A'}\n"
                f"Rejection Detail: {policy_decision.rejection_detail or 'N/A'}\n"
                f"Degraded Components: {degraded_components or 'None'}\n"
                f"Confidence: {confidence:.2f}\n"
            )
            msgs = await structured_completion(
                system=SYNTHESIZER_SYSTEM,
                user=f"Generate messages for this claim decision:\n\n{decision_context}",
                response_schema=MESSAGE_SCHEMA,
                client=self.client,
            )
            member_message = msgs.get("member_message", "")
            ops_summary = msgs.get("ops_summary", "")
        except Exception:
            member_message = self._fallback_member_message(policy_decision)
            ops_summary = f"Decision: {policy_decision.decision.value}. Rules: {'; '.join(policy_decision.applied_rules[:3])}"

        if degraded_components:
            member_message += (
                f" Note: Some processing steps encountered errors ({', '.join(degraded_components)}); "
                "manual review is recommended."
            )
            ops_summary += f" Degraded: {', '.join(degraded_components)}."

        return FinalDecision(
            claim_id=claim_id,
            decision=policy_decision.decision,
            approved_amount=policy_decision.approved_amount,
            confidence=round(confidence, 3),
            member_message=member_message,
            ops_summary=ops_summary,
            rejection_reasons=policy_decision.rejection_reasons,
            line_item_breakdown=policy_decision.line_item_breakdown,
            applied_rules=policy_decision.applied_rules,
            degraded_components=degraded_components,
            trace_id=trace_id,
        )

    def _fallback_member_message(self, decision: PolicyDecision) -> str:
        if decision.decision == DecisionType.APPROVED:
            return f"Your claim has been approved for ₹{decision.approved_amount:,.0f}."
        elif decision.decision == DecisionType.PARTIAL:
            return f"Your claim has been partially approved for ₹{decision.approved_amount:,.0f}. Some items were not covered."
        elif decision.decision == DecisionType.REJECTED:
            reasons = ", ".join(r.value for r in decision.rejection_reasons)
            msg = f"Your claim has been rejected. Reason(s): {reasons}."
            if RejectionReason.WAITING_PERIOD in decision.rejection_reasons and decision.eligibility_date:
                msg += f" You will be eligible for this condition from {decision.eligibility_date}."
            elif decision.rejection_detail:
                msg += f" {decision.rejection_detail}"
            return msg
        else:
            return "Your claim requires manual review by our operations team."
