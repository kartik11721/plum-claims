# Eval Report — Plum Claims Processing System

**Generated:** 2026-05-02 15:46 UTC
**Result:** 12/12 test cases matched expected outcome

---

## Scope & Coverage

This eval runs in **eval mode**: test cases supply ground-truth hints (`actual_type`, `quality`, `content`) that short-circuit the three vision-dependent agents. The 12/12 pass rate validates the pipeline's business logic, not its ability to read real documents.

| Agent | Exercised in this eval? | What would exercise it? |
|-------|------------------------|-------------------------|
| IntakeValidator | ✅ Yes — full logic | — |
| DocumentClassifierAgent | ⚠️ Bypassed — `actual_type` hint used | Real image upload via `/api/claims` |
| DocumentQualityAgent | ⚠️ Bypassed — `quality` hint used | Real image upload via `/api/claims` |
| ExtractionAgent (per doc) | ⚠️ Bypassed — `content` hint used | Real image upload via `/api/claims` |
| CrossDocValidator | ✅ Yes — full identity check | — |
| FraudSignalAgent | ✅ Yes — full rule logic | — |
| PolicyOrchestratorAgent + 6 sub-agents | ✅ Yes — full deterministic engine | — |
| DecisionAggregator / DecisionSynthesizer | ✅ Yes | — |

**Vision pipeline validation** requires uploading real scanned documents (see `sample_docs/`) to `/api/claims` and confirming that the classifier, quality check, and OCR extraction produce the same ground-truth values used here. The spec notes 'expect handwritten prescriptions, rubber stamps' — those failure modes are outside the scope of this eval.

---

## TC001 — Wrong Document Uploaded ✅ PASS

**Description:** Member submits two prescriptions for a consultation claim that requires a prescription and a hospital bill.

**Expected:**
- Decision: `None`

**Actual:**
- Decision: `NEEDS_DOCUMENTS`
- Approved Amount: ₹0.0
- Confidence: 0.000

**Match:** PASS — early stop triggered correctly

**Member Message:**
> We couldn't process your Consultation claim. You uploaded 2 copies of Prescription — only one is needed. Please also upload Hospital Bill and resubmit.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP001"}
    out: {"ok": true, "member_name": "Rajesh Kumar", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 388ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F001", "file_name": "dr_sharma_prescription.jpg", "quality": "GOOD"}, {"file_id": "F002", "file_name": "another_prescription.jpg", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": false, "classifications": [{"file_id": "F001", "file_name": "dr_sharma_prescription.jpg", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F002", "file_name": "another_prescription.jpg", "classified_type": "PRESCRIPTION", "confidence": 1.0}], "missing_required": ["HOSPITAL_BILL"], "unexpected": [], "member_message": "We couldn't process your Consultation claim. You uploaded 2 copies of Prescription \u2014 only one is needed. Please also upload Hospital Bill and resubmit."}
  ⏹ EARLY_STOP:DocumentMismatch [EARLY_STOP] 0ms
    out: {"reason": "DOCUMENT_TYPE_MISMATCH"}
```

---

## TC002 — Unreadable Document ✅ PASS

**Description:** Member uploads a valid prescription but a blurry, unreadable photo of their pharmacy bill.

**Expected:**
- Decision: `None`

**Actual:**
- Decision: `NEEDS_DOCUMENTS`
- Approved Amount: ₹0.0
- Confidence: 0.000

**Match:** PASS — early stop triggered correctly

**Member Message:**
> We weren't able to read "blurry_bill.jpg". Please re-upload a clearer version — make sure the document is well-lit and flat with all text visible.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP004"}
    out: {"ok": true, "member_name": "Sneha Reddy", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 20ms
    in:  {"doc_count": 2}
    out: {"ok": false, "per_doc": [{"file_id": "F003", "file_name": "prescription.jpg", "quality": "GOOD"}, {"file_id": "F004", "file_name": "blurry_bill.jpg", "quality": "UNREADABLE"}], "unreadable_files": ["blurry_bill.jpg"], "member_message": "We weren't able to read \"blurry_bill.jpg\". Please re-upload a clearer version \u2014 make sure the document is well-lit and flat with all text visible."}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F003", "file_name": "prescription.jpg", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F004", "file_name": "blurry_bill.jpg", "classified_type": "PHARMACY_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ⏹ EARLY_STOP:UnreadableDocument [EARLY_STOP] 0ms
    out: {"reason": "UNREADABLE_DOCUMENT"}
```

---

## TC003 — Documents Belong to Different Patients ✅ PASS

**Description:** The prescription is for Rajesh Kumar but the hospital bill is for a different patient, Arjun Mehta.

**Expected:**
- Decision: `None`

**Actual:**
- Decision: `NEEDS_DOCUMENTS`
- Approved Amount: ₹0.0
- Confidence: 0.000

**Match:** PASS — early stop triggered correctly

**Member Message:**
> The documents don't all belong to the same patient. This claim is for "Rajesh Kumar", but some documents show "Arjun Mehta" instead. Please re-upload documents that all belong to the same patient.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP001"}
    out: {"ok": true, "member_name": "Rajesh Kumar", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 18ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F005", "file_name": "prescription_rajesh.jpg", "quality": "GOOD"}, {"file_id": "F006", "file_name": "bill_arjun.jpg", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F005", "file_name": "prescription_rajesh.jpg", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F006", "file_name": "bill_arjun.jpg", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 20ms
    in:  {"doc_index": 0}
    out: {"doc_type": "OTHER", "patient_name": "Rajesh Kumar", "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 16ms
    in:  {"doc_index": 1}
    out: {"doc_type": "OTHER", "patient_name": "Arjun Mehta", "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Rajesh Kumar"}
    out: {"ok": false, "names_found": ["Rajesh Kumar", "Arjun Mehta"], "mismatch_pairs": [{"file_id": "doc_1", "name_on_doc": "Arjun Mehta"}], "member_message": "The documents don't all belong to the same patient. This claim is for \"Rajesh Kumar\", but some documents show \"Arjun Mehta\" instead. Please re-upload documents that all belong to the same patient."}
  ⏹ EARLY_STOP:IdentityMismatch [EARLY_STOP] 0ms
    out: {"reason": "IDENTITY_MISMATCH"}
```

---

## TC004 — Clean Consultation — Full Approval ✅ PASS

**Description:** Complete, valid consultation claim with correct documents, valid member, covered treatment, within all limits.

**Expected:**
- Decision: `APPROVED`
- Approved Amount: ₹1,350

**Actual:**
- Decision: `APPROVED`
- Approved Amount: ₹1,350.0
- Confidence: 1.000

**Match:** PASS

**Member Message:**
> Your claim has been approved for ₹1,350.

**Line Items:**
- Total claim: claimed ₹1,500.0 → approved ₹1,350.0 [APPROVED]

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP001"}
    out: {"ok": true, "member_name": "Rajesh Kumar", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F007", "quality": "GOOD"}, {"file_id": "F008", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F007", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F008", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. Arun Sharma", "doctor_registration": "KA/45678/2015", "patient_name": "Rajesh Kumar", "date": "2024-11-01", "diagnosis": ["Viral Fever"], "medicines": ["Paracetamol 650mg", "Vitamin C 500mg"], "tests_ordered": [], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 16ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "hospital_name": "City Clinic, Bengaluru", "date": "2024-11-01", "patient_name": "Rajesh Kumar", "line_items": [{"description": "Consultation Fee", "amount": 1000.0, "quantity": 1.0}, {"description": "CBC Test", "amount": 300.0, "quantity": 1.0}, {"description": "Dengue NS1 Test", "amount": 200.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 1500.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Rajesh Kumar"}
    out: {"ok": true, "names_found": ["Rajesh Kumar", "Rajesh Kumar"], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP001' (Rajesh Kumar) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b91,500 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ✓ PerClaimLimitAgent [OK] 0ms
    out: {"rules_applied": ["Per-claim limit check: PASSED"]}
  ✓ BenefitCalculatorAgent [OK] 0ms
    out: {"rules_applied": ["Co-pay deducted: \u20b9150.00"]}
  ✓ PolicyOrchestratorAgent [OK] 1ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "APPROVED", "approved_amount": 1350.0, "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 1500.0, "approved_amount": 1350.0, "status": "APPROVED"}], "rejection_reasons": [], "applied_rules": ["Member 'EMP001' (Rajesh Kumar) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b91,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Co-pay deducted: \u20b9150.00"], "network_discount_applied": 0.0, "copay_deducted": 150.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 1500.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "APPROVED"}
  ✓ DecisionSynthesizer [OK] 43ms
    in:  {"decision": "APPROVED"}
    out: {"claim_id": "TC004", "decision": "APPROVED", "approved_amount": 1350.0, "confidence": 1.0, "member_message": "Your claim has been approved for \u20b91,350.", "ops_summary": "Decision: APPROVED. Rules: Member 'EMP001' (Rajesh Kumar) validated.; Policy status: ACTIVE.; Claimed amount \u20b91,500 meets minimum \u20b9500.", "rejection_reasons": [], "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 1500.0, "approved_amount": 1350.0, "status": "APPROVED"}], "applied_rules": ["Member 'EMP001' (Rajesh Kumar) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b91,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Co-pay deducted: \u20b9150.00"], "degraded_components": [], "trace_id": "ba92bd1c-c2e5-4a37-84fb-654fb00c97a3"}
```

---

## TC005 — Waiting Period — Diabetes ✅ PASS

**Description:** Member joined 2024-09-01. Claims for diabetes treatment on 2024-10-15, which is within the 90-day waiting period for diabetes.

**Expected:**
- Decision: `REJECTED`
- Rejection Reasons: ['WAITING_PERIOD']

**Actual:**
- Decision: `REJECTED`
- Approved Amount: ₹0.0
- Confidence: 1.000
- Rejection Reasons: ['WAITING_PERIOD']

**Match:** PASS

**Member Message:**
> Your claim has been rejected because this treatment falls within a waiting period. You will be eligible for this condition from 2024-11-30.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP005"}
    out: {"ok": true, "member_name": "Vikram Joshi", "join_date": "2024-09-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 18ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F009", "quality": "GOOD"}, {"file_id": "F010", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F009", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F010", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. Sunil Mehta", "doctor_registration": "GJ/56789/2014", "patient_name": "Vikram Joshi", "diagnosis": ["Type 2 Diabetes Mellitus"], "medicines": ["Metformin 500mg", "Glimepiride 1mg"], "tests_ordered": [], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "date": "2024-10-15", "patient_name": "Vikram Joshi", "line_items": [], "gst_amount": 0.0, "total": 3000.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Vikram Joshi"}
    out: {"ok": true, "names_found": ["Vikram Joshi", "Vikram Joshi"], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP005' (Vikram Joshi) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b93,000 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ⚠ WaitingPeriodAgent [DEGRADED] 0ms
    out: {"rules_applied": ["Waiting period check: Diagnosis falls under the 90-day waiting period for 'diabetes'. Member joined 2024-09-01; eligible from 2024-11-30."]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "REJECTED", "approved_amount": 0.0, "line_item_breakdown": [], "rejection_reasons": ["WAITING_PERIOD"], "applied_rules": ["Member 'EMP005' (Vikram Joshi) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b93,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: Diagnosis falls under the 90-day waiting period for 'diabetes'. Member joined 2024-09-01; eligible from 2024-11-30."], "eligibility_date": "2024-11-30", "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 3000.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "REJECTED"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "REJECTED"}
    out: {"claim_id": "TC005", "decision": "REJECTED", "approved_amount": 0.0, "confidence": 1.0, "member_message": "Your claim has been rejected because this treatment falls within a waiting period. You will be eligible for this condition from 2024-11-30.", "ops_summary": "Decision: REJECTED. Rules: Member 'EMP005' (Vikram Joshi) validated.; Policy status: ACTIVE.; Claimed amount \u20b93,000 meets minimum \u20b9500.", "rejection_reasons": ["WAITING_PERIOD"], "line_item_breakdown": [], "applied_rules": ["Member 'EMP005' (Vikram Joshi) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b93,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: Diagnosis falls under the 90-day waiting period for 'diabetes'. Member joined 2024-09-01; eligible from 2024-11-30."], "degraded_components": [], "trace_id": "55938a13-0204-4c4a-aa19-a8bc6831018d"}
```

---

## TC006 — Dental Partial Approval — Cosmetic Exclusion ✅ PASS

**Description:** Bill includes root canal treatment (covered) and teeth whitening (cosmetic, excluded). System must approve only the covered procedure.

**Expected:**
- Decision: `PARTIAL`
- Approved Amount: ₹8,000

**Actual:**
- Decision: `PARTIAL`
- Approved Amount: ₹8,000.0
- Confidence: 1.000

**Match:** PASS

**Member Message:**
> Your claim has been partially approved for ₹8,000. Some items were not covered under your policy.

**Line Items:**
- Root Canal Treatment: claimed ₹8,000.0 → approved ₹8,000.0 [APPROVED]
- Teeth Whitening: claimed ₹4,000.0 → approved ₹0.0 [REJECTED] — Excluded under policy: Teeth Whitening

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP002"}
    out: {"ok": true, "member_name": "Priya Singh", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 1}
    out: {"ok": true, "per_doc": [{"file_id": "F011", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 1}
    out: {"ok": true, "classifications": [{"file_id": "F011", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "HOSPITAL_BILL", "hospital_name": "Smile Dental Clinic", "patient_name": "Priya Singh", "line_items": [{"description": "Root Canal Treatment", "amount": 8000.0, "quantity": 1.0}, {"description": "Teeth Whitening", "amount": 4000.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 12000.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Priya Singh"}
    out: {"ok": true, "names_found": ["Priya Singh"], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP002' (Priya Singh) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b912,000 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Partial exclusions found (handled at line-item level)"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ✓ PerClaimLimitAgent [OK] 0ms
    out: {"rules_applied": ["Per-claim limit check: N/A for DENTAL"]}
  ✓ BenefitCalculatorAgent [OK] 0ms
    out: {"rules_applied": ["Line-item coverage computed for DENTAL: 2 items."]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "DENTAL"}
    out: {"decision": "PARTIAL", "approved_amount": 8000.0, "line_item_breakdown": [{"description": "Root Canal Treatment", "claimed_amount": 8000.0, "approved_amount": 8000.0, "status": "APPROVED"}, {"description": "Teeth Whitening", "claimed_amount": 4000.0, "approved_amount": 0.0, "status": "REJECTED", "reason": "Excluded under policy: Teeth Whitening"}], "rejection_reasons": [], "applied_rules": ["Member 'EMP002' (Priya Singh) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b912,000 meets minimum \u20b9500.", "Partial exclusions found (handled at line-item level)", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: N/A for DENTAL", "Line-item coverage computed for DENTAL: 2 items."], "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 12000.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "PARTIAL"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "PARTIAL"}
    out: {"claim_id": "TC006", "decision": "PARTIAL", "approved_amount": 8000.0, "confidence": 1.0, "member_message": "Your claim has been partially approved for \u20b98,000. Some items were not covered under your policy.", "ops_summary": "Decision: PARTIAL. Rules: Member 'EMP002' (Priya Singh) validated.; Policy status: ACTIVE.; Claimed amount \u20b912,000 meets minimum \u20b9500.", "rejection_reasons": [], "line_item_breakdown": [{"description": "Root Canal Treatment", "claimed_amount": 8000.0, "approved_amount": 8000.0, "status": "APPROVED"}, {"description": "Teeth Whitening", "claimed_amount": 4000.0, "approved_amount": 0.0, "status": "REJECTED", "reason": "Excluded under policy: Teeth Whitening"}], "applied_rules": ["Member 'EMP002' (Priya Singh) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b912,000 meets minimum \u20b9500.", "Partial exclusions found (handled at line-item level)", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: N/A for DENTAL", "Line-item coverage computed for DENTAL: 2 items."], "degraded_components": [], "trace_id": "e32874fa-eac9-42ab-a42f-6bc0bc14694b"}
```

---

## TC007 — MRI Without Pre-Authorization ✅ PASS

**Description:** MRI scan costing ₹15,000 submitted without pre-authorization. Policy requires pre-auth for MRI above ₹10,000.

**Expected:**
- Decision: `REJECTED`
- Rejection Reasons: ['PRE_AUTH_MISSING']

**Actual:**
- Decision: `REJECTED`
- Approved Amount: ₹0.0
- Confidence: 1.000
- Rejection Reasons: ['PRE_AUTH_MISSING']

**Match:** PASS

**Member Message:**
> Your claim has been rejected. Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds ₹10,000. Claimed amount: ₹15,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP007"}
    out: {"ok": true, "member_name": "Suresh Patil", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 18ms
    in:  {"doc_count": 3}
    out: {"ok": true, "per_doc": [{"file_id": "F012", "quality": "GOOD"}, {"file_id": "F013", "quality": "GOOD"}, {"file_id": "F014", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 18ms
    in:  {"doc_count": 3}
    out: {"ok": true, "classifications": [{"file_id": "F012", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F013", "classified_type": "LAB_REPORT", "confidence": 1.0}, {"file_id": "F014", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 21ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. Venkat Rao", "doctor_registration": "AP/67890/2017", "diagnosis": ["Suspected Lumbar Disc Herniation"], "medicines": [], "tests_ordered": ["MRI Lumbar Spine"], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "LAB_REPORT", "tests": [{"name": "MRI Lumbar Spine"}], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_2] [OK] 18ms
    in:  {"doc_index": 2}
    out: {"doc_type": "HOSPITAL_BILL", "line_items": [{"description": "MRI Lumbar Spine", "amount": 15000.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 15000.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Suresh Patil"}
    out: {"ok": true, "names_found": [], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP007' (Suresh Patil) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b915,000 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ⚠ PreAuthCheckerAgent [DEGRADED] 0ms
    out: {"rules_applied": ["Pre-auth check: Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds \u20b910,000. Claimed amount: \u20b915,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim."]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "DIAGNOSTIC"}
    out: {"decision": "REJECTED", "approved_amount": 0.0, "line_item_breakdown": [], "rejection_reasons": ["PRE_AUTH_MISSING"], "applied_rules": ["Member 'EMP007' (Suresh Patil) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b915,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds \u20b910,000. Claimed amount: \u20b915,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim."], "rejection_detail": "Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds \u20b910,000. Claimed amount: \u20b915,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim.", "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 15000.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "REJECTED"}
  ✓ DecisionSynthesizer [OK] 17ms
    in:  {"decision": "REJECTED"}
    out: {"claim_id": "TC007", "decision": "REJECTED", "approved_amount": 0.0, "confidence": 1.0, "member_message": "Your claim has been rejected. Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds \u20b910,000. Claimed amount: \u20b915,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim.", "ops_summary": "Decision: REJECTED. Rules: Member 'EMP007' (Suresh Patil) validated.; Policy status: ACTIVE.; Claimed amount \u20b915,000 meets minimum \u20b9500.", "rejection_reasons": ["PRE_AUTH_MISSING"], "line_item_breakdown": [], "applied_rules": ["Member 'EMP007' (Suresh Patil) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b915,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: Pre-authorization is required for 'MRI Lumbar Spine' when amount exceeds \u20b910,000. Claimed amount: \u20b915,000. To resubmit: obtain pre-authorization from your insurer before the procedure, then include the pre-auth reference number with your claim."], "degraded_components": [], "trace_id": "180dc275-d5f0-47d1-bde5-4a9ee6d843e4"}
```

---

## TC008 — Per-Claim Limit Exceeded ✅ PASS

**Description:** Claimed amount of ₹7,500 exceeds the per-claim limit of ₹5,000.

**Expected:**
- Decision: `REJECTED`
- Rejection Reasons: ['PER_CLAIM_EXCEEDED']

**Actual:**
- Decision: `REJECTED`
- Approved Amount: ₹0.0
- Confidence: 1.000
- Rejection Reasons: ['PER_CLAIM_EXCEEDED']

**Match:** PASS

**Member Message:**
> Your claim has been rejected. Claimed amount ₹7,500 exceeds the per-claim limit of ₹5,000.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP003"}
    out: {"ok": true, "member_name": "Amit Verma", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F015", "quality": "GOOD"}, {"file_id": "F016", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 18ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F015", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F016", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. R. Gupta", "doctor_registration": "DL/34567/2016", "diagnosis": ["Gastroenteritis"], "medicines": ["Antibiotics", "Probiotics", "ORS"], "tests_ordered": [], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "line_items": [{"description": "Consultation Fee", "amount": 2000.0, "quantity": 1.0}, {"description": "Medicines", "amount": 5500.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 7500.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Amit Verma"}
    out: {"ok": true, "names_found": [], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP003' (Amit Verma) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b97,500 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ⚠ PerClaimLimitAgent [DEGRADED] 0ms
    out: {"rules_applied": ["Per-claim limit check: Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000."]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "REJECTED", "approved_amount": 0.0, "line_item_breakdown": [], "rejection_reasons": ["PER_CLAIM_EXCEEDED"], "applied_rules": ["Member 'EMP003' (Amit Verma) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b97,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000."], "rejection_detail": "Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000.", "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 7500.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "REJECTED"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "REJECTED"}
    out: {"claim_id": "TC008", "decision": "REJECTED", "approved_amount": 0.0, "confidence": 1.0, "member_message": "Your claim has been rejected. Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000.", "ops_summary": "Decision: REJECTED. Rules: Member 'EMP003' (Amit Verma) validated.; Policy status: ACTIVE.; Claimed amount \u20b97,500 meets minimum \u20b9500.", "rejection_reasons": ["PER_CLAIM_EXCEEDED"], "line_item_breakdown": [], "applied_rules": ["Member 'EMP003' (Amit Verma) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b97,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: Claimed amount \u20b97,500 exceeds the per-claim limit of \u20b95,000."], "degraded_components": [], "trace_id": "78f48096-3cc0-47d7-a307-d3fc94d67036"}
```

---

## TC009 — Fraud Signal — Multiple Same-Day Claims ✅ PASS

**Description:** Member EMP008 has already submitted 3 claims today before this one arrives. This is the 4th claim from the same member on the same day.

**Expected:**
- Decision: `MANUAL_REVIEW`

**Actual:**
- Decision: `MANUAL_REVIEW`
- Approved Amount: ₹4,320.0
- Confidence: 1.000

**Match:** PASS

**Member Message:**
> Your claim requires manual review by our operations team.

**Line Items:**
- Total claim: claimed ₹4,800.0 → approved ₹4,320.0 [APPROVED]

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP008"}
    out: {"ok": true, "member_name": "Ravi Menon", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F017", "quality": "GOOD"}, {"file_id": "F018", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F017", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F018", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. S. Khan", "diagnosis": ["Migraine"], "medicines": [], "tests_ordered": [], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "line_items": [], "gst_amount": 0.0, "total": 4800.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Ravi Menon"}
    out: {"ok": true, "names_found": [], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP008' (Ravi Menon) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,800 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ✓ PerClaimLimitAgent [OK] 0ms
    out: {"rules_applied": ["Per-claim limit check: PASSED"]}
  ✓ BenefitCalculatorAgent [OK] 0ms
    out: {"rules_applied": ["Co-pay deducted: \u20b9480.00"]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "APPROVED", "approved_amount": 4320.0, "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4800.0, "approved_amount": 4320.0, "status": "APPROVED"}], "rejection_reasons": [], "applied_rules": ["Member 'EMP008' (Ravi Menon) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,800 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Co-pay deducted: \u20b9480.00"], "network_discount_applied": 0.0, "copay_deducted": 480.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 4800.0}
    out: {"same_day_count": 3, "monthly_count": 3, "high_value": false, "document_alteration": false, "fraud_score": 0.85, "flags": ["Unusual same-day claim pattern: 4 claims on 2024-10-30 (limit: 2). Previous same-day claims: CLM_0081 at City Clinic A, CLM_0082 at City Clinic B, CLM_0083 at Wellness Center"], "requires_manual_review": true}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "MANUAL_REVIEW"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "MANUAL_REVIEW"}
    out: {"claim_id": "TC009", "decision": "MANUAL_REVIEW", "approved_amount": 4320.0, "confidence": 1.0, "member_message": "Your claim requires manual review by our operations team.", "ops_summary": "Decision: MANUAL_REVIEW. Rules: Member 'EMP008' (Ravi Menon) validated.; Policy status: ACTIVE.; Claimed amount \u20b94,800 meets minimum \u20b9500.", "rejection_reasons": [], "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4800.0, "approved_amount": 4320.0, "status": "APPROVED"}], "applied_rules": ["Member 'EMP008' (Ravi Menon) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,800 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Co-pay deducted: \u20b9480.00", "Manual review triggered: Unusual same-day claim pattern: 4 claims on 2024-10-30 (limit: 2). Previous same-day claims: CLM_0081 at City Clinic A, CLM_0082 at City Clinic B, CLM_0083 at Wellness Center; Fraud score 0.85 \u2265 threshold 0.8."], "degraded_components": [], "trace_id": "6e0fcfa6-2803-4467-afd1-9ab14e71eb49"}
```

---

## TC010 — Network Hospital — Discount Applied ✅ PASS

**Description:** Valid claim at Apollo Hospitals, a network hospital. Network discount must be applied before co-pay.

**Expected:**
- Decision: `APPROVED`
- Approved Amount: ₹3,240

**Actual:**
- Decision: `APPROVED`
- Approved Amount: ₹3,240.0
- Confidence: 1.000

**Match:** PASS

**Member Message:**
> Your claim has been approved for ₹3,240.

**Line Items:**
- Total claim: claimed ₹4,500.0 → approved ₹3,240.0 [APPROVED]

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP010"}
    out: {"ok": true, "member_name": "Deepak Shah", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F019", "quality": "GOOD"}, {"file_id": "F020", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F019", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F020", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. S. Iyer", "doctor_registration": "TN/56789/2013", "patient_name": "Deepak Shah", "diagnosis": ["Acute Bronchitis"], "medicines": ["Amoxicillin 500mg", "Salbutamol Inhaler"], "tests_ordered": [], "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "hospital_name": "Apollo Hospitals", "patient_name": "Deepak Shah", "line_items": [{"description": "Consultation Fee", "amount": 1500.0, "quantity": 1.0}, {"description": "Medicines", "amount": 3000.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 4500.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Deepak Shah"}
    out: {"ok": true, "names_found": ["Deepak Shah", "Deepak Shah"], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP010' (Deepak Shah) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,500 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ✓ PerClaimLimitAgent [OK] 0ms
    out: {"rules_applied": ["Per-claim limit check: PASSED"]}
  ✓ BenefitCalculatorAgent [OK] 0ms
    out: {"rules_applied": ["Network discount applied: \u20b9900.00 (20%)", "Co-pay deducted: \u20b9360.00"]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "APPROVED", "approved_amount": 3240.0, "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4500.0, "approved_amount": 3240.0, "status": "APPROVED"}], "rejection_reasons": [], "applied_rules": ["Member 'EMP010' (Deepak Shah) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Network discount applied: \u20b9900.00 (20%)", "Co-pay deducted: \u20b9360.00"], "network_discount_applied": 900.0, "copay_deducted": 360.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 4500.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "APPROVED"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "APPROVED"}
    out: {"claim_id": "TC010", "decision": "APPROVED", "approved_amount": 3240.0, "confidence": 1.0, "member_message": "Your claim has been approved for \u20b93,240.", "ops_summary": "Decision: APPROVED. Rules: Member 'EMP010' (Deepak Shah) validated.; Policy status: ACTIVE.; Claimed amount \u20b94,500 meets minimum \u20b9500.", "rejection_reasons": [], "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4500.0, "approved_amount": 3240.0, "status": "APPROVED"}], "applied_rules": ["Member 'EMP010' (Deepak Shah) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,500 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: PASSED", "Network discount applied: \u20b9900.00 (20%)", "Co-pay deducted: \u20b9360.00"], "degraded_components": [], "trace_id": "b8cc6564-911c-4254-a189-5aba7e00b589"}
```

---

## TC011 — Component Failure — Graceful Degradation ✅ PASS

**Description:** One component of your system fails mid-processing (simulate with the flag below). The overall pipeline must continue, produce a decision, and make the failure visible in the output with an appropriately reduced confidence score.

**Expected:**
- Decision: `APPROVED`

**Actual:**
- Decision: `APPROVED`
- Approved Amount: ₹4,000.0
- Confidence: 0.147
- Degraded Components: ['ExtractionAgent[doc_0]', 'ExtractionAgent[simulated]']

**Match:** PASS

**Member Message:**
> Your claim has been approved for ₹4,000. Note: Some processing steps encountered errors (ExtractionAgent[doc_0], ExtractionAgent[simulated]); manual review is recommended.

**Line Items:**
- Total claim: claimed ₹4,000.0 → approved ₹4,000.0 [APPROVED]

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP006"}
    out: {"ok": true, "member_name": "Kavita Nair", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F021", "quality": "GOOD"}, {"file_id": "F022", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F021", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F022", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ⚠ ExtractionAgent[doc_0] [DEGRADED] 0ms
    out: {"error": "SimulatedFailure: graceful-degradation test triggered by submission flag"}
    ⚠ Error: SimulatedFailure: graceful-degradation test triggered by submission flag
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "hospital_name": "Ayur Wellness Centre", "line_items": [{"description": "Panchakarma Therapy (5 sessions)", "amount": 3000.0, "quantity": 1.0}, {"description": "Consultation", "amount": 1000.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 4000.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Kavita Nair"}
    out: {"ok": true, "names_found": [], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP006' (Kavita Nair) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,000 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: PASSED"]}
  ✓ WaitingPeriodAgent [OK] 0ms
    out: {"rules_applied": ["Waiting period check: PASSED"]}
  ✓ PreAuthCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Pre-auth check: PASSED"]}
  ✓ PerClaimLimitAgent [OK] 0ms
    out: {"rules_applied": ["Per-claim limit check: N/A for ALTERNATIVE_MEDICINE"]}
  ✓ BenefitCalculatorAgent [OK] 0ms
    out: {"rules_applied": []}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "ALTERNATIVE_MEDICINE"}
    out: {"decision": "APPROVED", "approved_amount": 4000.0, "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4000.0, "approved_amount": 4000.0, "status": "APPROVED"}], "rejection_reasons": [], "applied_rules": ["Member 'EMP006' (Kavita Nair) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: N/A for ALTERNATIVE_MEDICINE"], "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 4000.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "APPROVED"}
  ✓ DecisionSynthesizer [OK] 18ms
    in:  {"decision": "APPROVED"}
    out: {"claim_id": "TC011", "decision": "APPROVED", "approved_amount": 4000.0, "confidence": 0.147, "member_message": "Your claim has been approved for \u20b94,000. Note: Some processing steps encountered errors (ExtractionAgent[doc_0], ExtractionAgent[simulated]); manual review is recommended.", "ops_summary": "Decision: APPROVED. Rules: Member 'EMP006' (Kavita Nair) validated.; Policy status: ACTIVE.; Claimed amount \u20b94,000 meets minimum \u20b9500. Degraded: ExtractionAgent[doc_0], ExtractionAgent[simulated].", "rejection_reasons": [], "line_item_breakdown": [{"description": "Total claim", "claimed_amount": 4000.0, "approved_amount": 4000.0, "status": "APPROVED"}], "applied_rules": ["Member 'EMP006' (Kavita Nair) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b94,000 meets minimum \u20b9500.", "Exclusion check: PASSED", "Waiting period check: PASSED", "Pre-auth check: PASSED", "Per-claim limit check: N/A for ALTERNATIVE_MEDICINE"], "degraded_components": ["ExtractionAgent[doc_0]", "ExtractionAgent[simulated]"], "trace_id": "9edfd07a-cb88-42d6-808d-14d5cef96c69"}
```

---

## TC012 — Excluded Treatment ✅ PASS

**Description:** Member claims for bariatric consultation and a diet program. Obesity treatment is explicitly excluded under the policy.

**Expected:**
- Decision: `REJECTED`
- Rejection Reasons: ['EXCLUDED_CONDITION']

**Actual:**
- Decision: `REJECTED`
- Approved Amount: ₹0.0
- Confidence: 1.000
- Rejection Reasons: ['EXCLUDED_CONDITION']

**Match:** PASS

**Member Message:**
> Your claim has been rejected because the treatment or condition is not covered under your policy.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
    in:  {"member_id": "EMP009"}
    out: {"ok": true, "member_name": "Anita Desai", "join_date": "2024-04-01", "reasons": []}
  ✓ DocumentQualityAgent [OK] 17ms
    in:  {"doc_count": 2}
    out: {"ok": true, "per_doc": [{"file_id": "F023", "quality": "GOOD"}, {"file_id": "F024", "quality": "GOOD"}], "unreadable_files": []}
  ✓ DocumentClassifierAgent [OK] 18ms
    in:  {"doc_count": 2}
    out: {"ok": true, "classifications": [{"file_id": "F023", "classified_type": "PRESCRIPTION", "confidence": 1.0}, {"file_id": "F024", "classified_type": "HOSPITAL_BILL", "confidence": 1.0}], "missing_required": [], "unexpected": []}
  ✓ ExtractionAgent[doc_0] [OK] 17ms
    in:  {"doc_index": 0}
    out: {"doc_type": "PRESCRIPTION", "doctor_name": "Dr. P. Banerjee", "doctor_registration": "WB/34567/2015", "diagnosis": ["Morbid Obesity \u2014 BMI 37"], "medicines": [], "tests_ordered": [], "treatment": "Bariatric Consultation and Customised Diet Plan", "overall_confidence": 1.0, "quality_flags": []}
  ✓ ExtractionAgent[doc_1] [OK] 17ms
    in:  {"doc_index": 1}
    out: {"doc_type": "HOSPITAL_BILL", "line_items": [{"description": "Bariatric Consultation", "amount": 3000.0, "quantity": 1.0}, {"description": "Personalised Diet and Nutrition Program", "amount": 5000.0, "quantity": 1.0}], "gst_amount": 0.0, "total": 8000.0, "overall_confidence": 1.0, "quality_flags": []}
  ✓ CrossDocValidator [OK] 0ms
    in:  {"member_name": "Anita Desai"}
    out: {"ok": true, "names_found": [], "mismatch_pairs": []}
  ✓ MemberValidationAgent [OK] 0ms
    out: {"rules_applied": ["Member 'EMP009' (Anita Desai) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b98,000 meets minimum \u20b9500."]}
  ✓ ExclusionCheckerAgent [OK] 0ms
    out: {"rules_applied": ["Exclusion check: matched \u2014 Obesity and weight loss programs"]}
  ✓ PolicyOrchestratorAgent [OK] 0ms
    in:  {"category": "CONSULTATION"}
    out: {"decision": "REJECTED", "approved_amount": 0.0, "line_item_breakdown": [], "rejection_reasons": ["EXCLUDED_CONDITION"], "applied_rules": ["Member 'EMP009' (Anita Desai) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b98,000 meets minimum \u20b9500.", "Exclusion check: matched \u2014 Obesity and weight loss programs"], "network_discount_applied": 0.0, "copay_deducted": 0.0, "requires_manual_review": false, "manual_review_reasons": []}
  ✓ FraudSignalAgent [OK] 0ms
    in:  {"claimed_amount": 8000.0}
    out: {"same_day_count": 0, "monthly_count": 0, "high_value": false, "document_alteration": false, "fraud_score": 0.0, "flags": [], "requires_manual_review": false}
  ✓ DecisionAggregator [OK] 0ms
    in:  {"decision": "REJECTED"}
  ✓ DecisionSynthesizer [OK] 17ms
    in:  {"decision": "REJECTED"}
    out: {"claim_id": "TC012", "decision": "REJECTED", "approved_amount": 0.0, "confidence": 1.0, "member_message": "Your claim has been rejected because the treatment or condition is not covered under your policy.", "ops_summary": "Decision: REJECTED. Rules: Member 'EMP009' (Anita Desai) validated.; Policy status: ACTIVE.; Claimed amount \u20b98,000 meets minimum \u20b9500.", "rejection_reasons": ["EXCLUDED_CONDITION"], "line_item_breakdown": [], "applied_rules": ["Member 'EMP009' (Anita Desai) validated.", "Policy status: ACTIVE.", "Claimed amount \u20b98,000 meets minimum \u20b9500.", "Exclusion check: matched \u2014 Obesity and weight loss programs"], "degraded_components": [], "trace_id": "9b5720cc-c894-484f-8cc9-e92a72a11ff8"}
```

---
