from __future__ import annotations
from ..models.agents import IntakeResult
from ..models.claim import ClaimSubmission


class IntakeValidator:
    def __init__(self, policy: dict):
        self.policy = policy

    def validate(self, submission: ClaimSubmission) -> IntakeResult:
        members = {m["member_id"]: m for m in self.policy.get("members", [])}
        member = members.get(submission.member_id)
        if not member:
            return IntakeResult(ok=False, reasons=[f"Member '{submission.member_id}' not found in policy roster."])

        if self.policy.get("policy_holder", {}).get("renewal_status") != "ACTIVE":
            return IntakeResult(ok=False, reasons=["Policy is not currently active."])

        if submission.policy_id != self.policy.get("policy_id"):
            return IntakeResult(ok=False, reasons=[f"Policy ID '{submission.policy_id}' does not match active policy."])

        return IntakeResult(
            ok=True,
            member_name=member.get("name"),
            join_date=member.get("join_date"),
        )
