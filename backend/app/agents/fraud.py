from __future__ import annotations
from ..models.claim import ClaimSubmission
from ..models.agents import FraudSignals


class FraudSignalAgent:
    def __init__(self, policy: dict):
        self.thresholds = policy.get("fraud_thresholds", {})

    def analyze(self, submission: ClaimSubmission) -> FraudSignals:
        flags: list[str] = []
        same_day_limit = self.thresholds.get("same_day_claims_limit", 2)
        monthly_limit = self.thresholds.get("monthly_claims_limit", 6)
        high_value_threshold = self.thresholds.get("high_value_claim_threshold", 25_000)
        fraud_score_threshold = self.thresholds.get("fraud_score_manual_review_threshold", 0.80)

        # Same-day claims count (includes history entries)
        same_day = [
            h for h in submission.claims_history
            if h.date == submission.treatment_date
        ]
        same_day_count = len(same_day)

        # Monthly count
        treat_month = submission.treatment_date[:7]  # YYYY-MM
        monthly = [h for h in submission.claims_history if h.date.startswith(treat_month)]
        monthly_count = len(monthly)

        high_value = submission.claimed_amount > high_value_threshold

        fraud_score = 0.0
        if same_day_count >= same_day_limit:
            flags.append(
                f"Unusual same-day claim pattern: {same_day_count + 1} claims on {submission.treatment_date} "
                f"(limit: {same_day_limit}). Previous same-day claims: "
                + ", ".join(f"{h.claim_id} at {h.provider}" for h in same_day)
            )
            fraud_score = max(fraud_score, 0.85)

        if monthly_count >= monthly_limit:
            flags.append(f"Monthly claim count {monthly_count + 1} exceeds limit {monthly_limit}.")
            fraud_score = max(fraud_score, 0.75)

        if high_value:
            flags.append(f"High-value claim ₹{submission.claimed_amount:,.0f} exceeds threshold ₹{high_value_threshold:,.0f}.")
            fraud_score = max(fraud_score, 0.40)

        requires_manual = fraud_score >= fraud_score_threshold or bool(flags)

        return FraudSignals(
            same_day_count=same_day_count,
            monthly_count=monthly_count,
            high_value=high_value,
            fraud_score=fraud_score,
            flags=flags,
            requires_manual_review=requires_manual,
        )
