"""
Unit tests for the deterministic PolicyDecisionEngine.
Each test maps to a specific test case from test_cases.json.
No LLM calls are made — all inputs are pre-structured.
"""
import pytest
from app.policy_engine import PolicyDecisionEngine
from app.policy_engine.calculator import apply_network_discount_then_copay, check_per_claim_limit
from app.policy_engine.waiting_period import check_waiting_period
from app.policy_engine.exclusions import check_exclusions, filter_excluded_line_items
from app.policy_engine.pre_auth import check_pre_auth
from app.models.claim import ClaimSubmission, ClaimCategory
from app.models.agents import FraudSignals
from app.models.decision import DecisionType, RejectionReason


# ── calculator.py ─────────────────────────────────────────────────────────────

class TestNetworkDiscountBeforeCopay:
    """TC010: Network discount must be applied BEFORE copay."""

    def test_apollo_discount_then_copay(self, policy):
        # Apollo is a network hospital: 20% discount first, then 10% copay
        approved, discount, copay = apply_network_discount_then_copay(
            4500.0, "Apollo Hospitals", "CONSULTATION", policy
        )
        # Step 1: 4500 * (1 - 0.20) = 3600
        # Step 2: 3600 * (1 - 0.10) = 3240 → copay = 360
        assert discount == pytest.approx(900.0)
        assert copay == pytest.approx(360.0)
        assert approved == pytest.approx(3240.0)

    def test_non_network_no_discount(self, policy):
        # Non-network hospital: only copay
        approved, discount, copay = apply_network_discount_then_copay(
            1500.0, "City Clinic, Bengaluru", "CONSULTATION", policy
        )
        assert discount == 0.0
        assert copay == pytest.approx(150.0)
        assert approved == pytest.approx(1350.0)

    def test_discount_order_is_not_reversed(self, policy):
        """Wrong order would give: 4500 - copay_first(450) = 4050 * 0.80 = 3240 — same number!
        But with a different split. Verify copay is on DISCOUNTED amount."""
        approved, discount, copay = apply_network_discount_then_copay(
            4500.0, "Apollo Hospitals", "CONSULTATION", policy
        )
        # copay should be 360 (10% of 3600), not 450 (10% of 4500)
        assert copay == pytest.approx(360.0)


class TestPerClaimLimit:
    """TC008: Per-claim limit check."""

    def test_exceeds_limit(self, policy):
        ok, reason = check_per_claim_limit(7500.0, policy)
        assert not ok
        assert "7,500" in reason
        assert "5,000" in reason

    def test_within_limit(self, policy):
        ok, reason = check_per_claim_limit(1500.0, policy)
        assert ok
        assert reason is None

    def test_at_limit(self, policy):
        ok, reason = check_per_claim_limit(5000.0, policy)
        assert ok  # at limit is fine


# ── waiting_period.py ─────────────────────────────────────────────────────────

class TestWaitingPeriod:
    """TC005: Diabetes waiting period for Vikram Joshi (joined 2024-09-01)."""

    def test_diabetes_within_waiting_period(self, policy):
        eligible, reason, eligibility_date = check_waiting_period(
            join_date_str="2024-09-01",
            treatment_date_str="2024-10-15",
            diagnoses=["Type 2 Diabetes Mellitus"],
            treatment=None,
            policy=policy,
        )
        assert not eligible
        assert "diabetes" in reason.lower() or "90" in reason
        # Joined Sep 1, 90-day wait → eligible Nov 29
        assert eligibility_date == "2024-11-30"

    def test_initial_waiting_period(self, policy):
        eligible, reason, eligibility_date = check_waiting_period(
            join_date_str="2024-04-01",
            treatment_date_str="2024-04-15",
            diagnoses=["Viral Fever"],
            treatment=None,
            policy=policy,
        )
        assert not eligible
        assert "30" in reason or "initial" in reason.lower()

    def test_after_waiting_period(self, policy):
        eligible, reason, eligibility_date = check_waiting_period(
            join_date_str="2024-04-01",
            treatment_date_str="2024-11-01",
            diagnoses=["Viral Fever"],
            treatment=None,
            policy=policy,
        )
        assert eligible
        assert reason is None

    def test_diabetes_after_waiting_period(self, policy):
        eligible, reason, eligibility_date = check_waiting_period(
            join_date_str="2024-09-01",
            treatment_date_str="2024-12-15",
            diagnoses=["Type 2 Diabetes Mellitus"],
            treatment=None,
            policy=policy,
        )
        assert eligible


# ── exclusions.py ─────────────────────────────────────────────────────────────

class TestExclusions:
    """TC006 and TC012."""

    def test_bariatric_excluded(self, policy):
        excl = check_exclusions(
            diagnoses=["Morbid Obesity — BMI 37"],
            treatment="Bariatric Consultation and Customised Diet Plan",
            line_items=[],
            category="CONSULTATION",
            policy=policy,
        )
        assert len(excl) > 0
        excl_names = [e[0] for e in excl]
        assert any("obesity" in n.lower() or "bariatric" in n.lower() for n in excl_names)

    def test_teeth_whitening_dental_excluded(self, policy):
        covered, excluded = filter_excluded_line_items(
            line_items=[
                {"description": "Root Canal Treatment", "amount": 8000},
                {"description": "Teeth Whitening", "amount": 4000},
            ],
            category="DENTAL",
        )
        assert len(covered) == 1
        assert covered[0]["description"] == "Root Canal Treatment"
        assert len(excluded) == 1
        assert excluded[0][0]["description"] == "Teeth Whitening"

    def test_root_canal_not_excluded(self, policy):
        covered, excluded = filter_excluded_line_items(
            line_items=[{"description": "Root Canal Treatment", "amount": 8000}],
            category="DENTAL",
        )
        assert len(covered) == 1
        assert len(excluded) == 0


# ── pre_auth.py ───────────────────────────────────────────────────────────────

class TestPreAuth:
    """TC007: MRI without pre-auth."""

    def test_mri_above_threshold_no_preauth(self, policy):
        ok, reason = check_pre_auth(
            line_items=[{"description": "MRI Lumbar Spine", "amount": 15000}],
            claimed_amount=15000,
            has_pre_auth=False,
            policy=policy,
        )
        assert not ok
        assert "pre-authorization" in reason.lower()
        assert "resubmit" in reason.lower() or "obtain" in reason.lower()

    def test_mri_with_preauth(self, policy):
        ok, reason = check_pre_auth(
            line_items=[{"description": "MRI Lumbar Spine", "amount": 15000}],
            claimed_amount=15000,
            has_pre_auth=True,
            policy=policy,
        )
        assert ok

    def test_consultation_no_preauth_needed(self, policy):
        ok, reason = check_pre_auth(
            line_items=[{"description": "Consultation Fee", "amount": 1000}],
            claimed_amount=1000,
            has_pre_auth=False,
            policy=policy,
        )
        assert ok


# ── PolicyDecisionEngine (integration of all subroutines) ────────────────────

class TestPolicyDecisionEngine:

    def _make_submission(self, member_id, category, treatment_date, claimed_amount, hospital_name=None, ytd=0.0, history=None):
        from app.models.claim import ClaimSubmission, ClaimCategory
        return ClaimSubmission(
            member_id=member_id,
            policy_id="PLUM_GHI_2024",
            claim_category=ClaimCategory(category),
            treatment_date=treatment_date,
            claimed_amount=claimed_amount,
            hospital_name=hospital_name,
            ytd_claims_amount=ytd,
            claims_history=history or [],
        )

    def test_tc004_clean_consultation_approved(self, policy):
        """TC004: Clean consultation with copay."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP001", "CONSULTATION", "2024-11-01", 1500.0, ytd=5000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "PRESCRIPTION", "diagnosis": ["Viral Fever"], "medicines": ["Paracetamol"], "overall_confidence": 0.95},
            {"doc_type": "HOSPITAL_BILL", "patient_name": "Rajesh Kumar", "total": 1500, "line_items": [{"description": "Consultation Fee", "amount": 1000}, {"description": "CBC Test", "amount": 500}], "overall_confidence": 0.95},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.APPROVED
        assert decision.approved_amount == pytest.approx(1350.0)  # 10% copay

    def test_tc005_waiting_period_rejected(self, policy):
        """TC005: Vikram Joshi diabetes within 90-day waiting period."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP005", "CONSULTATION", "2024-10-15", 3000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "PRESCRIPTION", "diagnosis": ["Type 2 Diabetes Mellitus"], "overall_confidence": 0.9},
            {"doc_type": "HOSPITAL_BILL", "patient_name": "Vikram Joshi", "total": 3000, "overall_confidence": 0.9},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.REJECTED
        assert RejectionReason.WAITING_PERIOD in decision.rejection_reasons
        assert decision.eligibility_date is not None

    def test_tc006_dental_partial(self, policy):
        """TC006: Root canal approved, teeth whitening excluded."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP002", "DENTAL", "2024-10-15", 12000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "HOSPITAL_BILL", "patient_name": "Priya Singh", "total": 12000,
             "line_items": [
                 {"description": "Root Canal Treatment", "amount": 8000},
                 {"description": "Teeth Whitening", "amount": 4000},
             ], "overall_confidence": 0.95},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.PARTIAL
        assert decision.approved_amount == pytest.approx(8000.0)
        approved_items = [d for d in decision.line_item_breakdown if d.status == "APPROVED"]
        rejected_items = [d for d in decision.line_item_breakdown if d.status == "REJECTED"]
        assert len(approved_items) >= 1
        assert len(rejected_items) >= 1
        assert any("Root Canal" in d.description for d in approved_items)
        assert any("Whitening" in d.description for d in rejected_items)

    def test_tc007_mri_no_preauth(self, policy):
        """TC007: MRI without pre-auth → REJECTED."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP007", "DIAGNOSTIC", "2024-11-02", 15000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "PRESCRIPTION", "diagnosis": ["Suspected Lumbar Disc Herniation"], "tests_ordered": ["MRI Lumbar Spine"], "overall_confidence": 0.9},
            {"doc_type": "LAB_REPORT", "overall_confidence": 0.9},
            {"doc_type": "HOSPITAL_BILL", "total": 15000, "line_items": [{"description": "MRI Lumbar Spine", "amount": 15000}], "overall_confidence": 0.9},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.REJECTED
        assert RejectionReason.PRE_AUTH_MISSING in decision.rejection_reasons

    def test_tc008_per_claim_limit(self, policy):
        """TC008: ₹7,500 > ₹5,000 per-claim limit."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP003", "CONSULTATION", "2024-10-20", 7500.0, ytd=10000.0)
        fraud = FraudSignals()
        extracted = [{"doc_type": "PRESCRIPTION", "diagnosis": ["Gastroenteritis"], "overall_confidence": 0.9}]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.REJECTED
        assert RejectionReason.PER_CLAIM_EXCEEDED in decision.rejection_reasons

    def test_tc009_fraud_manual_review(self, policy):
        """TC009: 4 same-day claims → MANUAL_REVIEW."""
        from app.models.claim import ClaimHistoryEntry
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission(
            "EMP008", "CONSULTATION", "2024-10-30", 4800.0,
            history=[
                ClaimHistoryEntry(claim_id="CLM_0081", date="2024-10-30", amount=1200, provider="City Clinic A"),
                ClaimHistoryEntry(claim_id="CLM_0082", date="2024-10-30", amount=1800, provider="City Clinic B"),
                ClaimHistoryEntry(claim_id="CLM_0083", date="2024-10-30", amount=2100, provider="Wellness Center"),
            ]
        )
        fraud_agent = __import__("app.agents.fraud", fromlist=["FraudSignalAgent"]).FraudSignalAgent(policy)
        fraud = fraud_agent.analyze(submission)
        assert fraud.requires_manual_review
        assert fraud.same_day_count >= 3

        extracted = [{"doc_type": "PRESCRIPTION", "diagnosis": ["Migraine"], "overall_confidence": 0.9}]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.MANUAL_REVIEW

    def test_tc010_network_discount_approved(self, policy):
        """TC010: Apollo Hospitals → 20% discount then 10% copay → ₹3,240."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP010", "CONSULTATION", "2024-11-03", 4500.0, hospital_name="Apollo Hospitals", ytd=8000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "PRESCRIPTION", "diagnosis": ["Acute Bronchitis"], "overall_confidence": 0.95},
            {"doc_type": "HOSPITAL_BILL", "hospital_name": "Apollo Hospitals", "patient_name": "Deepak Shah", "total": 4500,
             "line_items": [{"description": "Consultation Fee", "amount": 1500}, {"description": "Medicines", "amount": 3000}],
             "overall_confidence": 0.95},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.APPROVED
        assert decision.approved_amount == pytest.approx(3240.0)

    def test_tc012_excluded_treatment(self, policy):
        """TC012: Bariatric consultation → REJECTED (excluded condition)."""
        engine = PolicyDecisionEngine(policy)
        submission = self._make_submission("EMP009", "CONSULTATION", "2024-10-18", 8000.0)
        fraud = FraudSignals()
        extracted = [
            {"doc_type": "PRESCRIPTION", "diagnosis": ["Morbid Obesity — BMI 37"], "treatment": "Bariatric Consultation and Customised Diet Plan", "overall_confidence": 0.95},
            {"doc_type": "HOSPITAL_BILL", "total": 8000,
             "line_items": [{"description": "Bariatric Consultation", "amount": 3000}, {"description": "Personalised Diet and Nutrition Program", "amount": 5000}],
             "overall_confidence": 0.95},
        ]
        decision = engine.decide(submission, extracted, fraud)
        assert decision.decision == DecisionType.REJECTED
        assert RejectionReason.EXCLUDED_CONDITION in decision.rejection_reasons
