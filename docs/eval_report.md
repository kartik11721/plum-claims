# Eval Report — Plum Claims Processing System

**Generated:** 2026-04-30 10:10 UTC
**Result:** 12/12 test cases matched expected outcome

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
> Document verification failed. For a Consultation claim, you must provide: Prescription, Hospital Bill. Missing: Hospital Bill. Please upload the missing documents.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 9ms
  ⏹ EARLY_STOP:DocumentMismatch [EARLY_STOP] 0ms
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
> We could not read the following document(s): "blurry_bill.jpg". Please re-upload a clearer version — ensure good lighting, the document is flat, and all text is visible. Your claim cannot be processed until legible documents are provided.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 9ms
  ✓ DocumentQualityAgent [OK] 9ms
  ⏹ EARLY_STOP:UnreadableDocument [EARLY_STOP] 0ms
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
> Document identity mismatch detected. The member on this claim is "Rajesh Kumar", but we found different patient names on your documents: "Arjun Mehta" (doc doc_1). All documents must belong to the same patient. Please re-upload documents for the correct patient.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 9ms
  ✓ DocumentQualityAgent [OK] 11ms
  ✓ ExtractionAgent [OK] 4ms
  ✓ CrossDocValidator [OK] 0ms
  ⏹ EARLY_STOP:IdentityMismatch [EARLY_STOP] 0ms
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
  ✓ DocumentClassifierAgent [OK] 9ms
  ✓ DocumentQualityAgent [OK] 9ms
  ✓ ExtractionAgent [OK] 0ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 973ms
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
> Your claim has been rejected. Reason(s): WAITING_PERIOD.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 23ms
  ✓ DocumentQualityAgent [OK] 21ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 373ms
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
> Your claim has been partially approved for ₹8,000. Some items were not covered.

**Line Items:**
- Root Canal Treatment: claimed ₹8,000.0 → approved ₹8,000.0 [APPROVED]
- Teeth Whitening: claimed ₹4,000.0 → approved ₹0.0 [REJECTED] — Excluded under policy: Teeth Whitening

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 9ms
  ✓ DocumentQualityAgent [OK] 11ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 374ms
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
> Your claim has been rejected. Reason(s): PRE_AUTH_MISSING.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 15ms
  ✓ DocumentQualityAgent [OK] 12ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 332ms
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
> Your claim has been rejected. Reason(s): PER_CLAIM_EXCEEDED.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 13ms
  ✓ DocumentQualityAgent [OK] 11ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 418ms
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
  ✓ DocumentClassifierAgent [OK] 10ms
  ✓ DocumentQualityAgent [OK] 9ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 414ms
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
  ✓ DocumentClassifierAgent [OK] 16ms
  ✓ DocumentQualityAgent [OK] 13ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 669ms
```

---

## TC011 — Component Failure — Graceful Degradation ✅ PASS

**Description:** One component of your system fails mid-processing (simulate with the flag below). The overall pipeline must continue, produce a decision, and make the failure visible in the output with an appropriately reduced confidence score.

**Expected:**
- Decision: `APPROVED`

**Actual:**
- Decision: `APPROVED`
- Approved Amount: ₹4,000.0
- Confidence: 0.700
- Degraded Components: ['ExtractionAgent[simulated]']

**Match:** PASS

**Member Message:**
> Your claim has been approved for ₹4,000. Note: Some processing steps encountered errors (ExtractionAgent[simulated]); manual review is recommended.

**Line Items:**
- Total claim: claimed ₹4,000.0 → approved ₹4,000.0 [APPROVED]

**Trace:**
```
  ⚠ ExtractionAgent[simulated_failure] [DEGRADED] 0ms
    ⚠ Error: SimulatedFailure: component failure injected by test flag
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 13ms
  ✓ DocumentQualityAgent [OK] 12ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 354ms
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
> Your claim has been rejected. Reason(s): EXCLUDED_CONDITION.

**Trace:**
```
  ✓ IntakeValidator [OK] 0ms
  ✓ DocumentClassifierAgent [OK] 15ms
  ✓ DocumentQualityAgent [OK] 12ms
  ✓ ExtractionAgent [OK] 1ms
  ✓ CrossDocValidator [OK] 0ms
  ✓ FraudSignalAgent [OK] 0ms
  ✓ PolicyDecisionEngine [OK] 0ms
  ✓ DecisionSynthesizer [OK] 557ms
```

---
