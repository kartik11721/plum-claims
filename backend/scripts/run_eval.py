#!/usr/bin/env python3
"""
Eval runner: processes all 12 test cases from test_cases.json and produces
docs/eval_report.md with decision, trace, and expected vs actual comparison.
"""
from __future__ import annotations
import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import load_policy
from app.orchestrator import ClaimOrchestrator
from app.models.claim import ClaimSubmission, ClaimCategory, UploadedDoc, PreParsedContent, ClaimHistoryEntry, DocumentType
from app.models.decision import DecisionType


def _parse_doc(doc_data: dict) -> UploadedDoc:
    actual_type_str = doc_data.get("actual_type")
    actual_type = DocumentType(actual_type_str) if actual_type_str else None

    content_data = doc_data.get("content")
    content = None
    if content_data:
        line_items = content_data.get("line_items", [])
        diagnosis_raw = content_data.get("diagnosis")
        content = PreParsedContent(
            doctor_name=content_data.get("doctor_name"),
            doctor_registration=content_data.get("doctor_registration"),
            patient_name=content_data.get("patient_name"),
            date=content_data.get("date"),
            diagnosis=diagnosis_raw if isinstance(diagnosis_raw, str) else None,
            treatment=content_data.get("treatment"),
            medicines=content_data.get("medicines", []),
            tests_ordered=content_data.get("tests_ordered", []),
            hospital_name=content_data.get("hospital_name"),
            line_items=line_items,
            total=content_data.get("total"),
            test_name=content_data.get("test_name"),
            net_amount=content_data.get("net_amount"),
        )

    return UploadedDoc(
        file_id=doc_data["file_id"],
        file_name=doc_data.get("file_name"),
        actual_type=actual_type,
        quality=doc_data.get("quality"),
        patient_name_on_doc=doc_data.get("patient_name_on_doc"),
        content=content,
    )


def _parse_submission(tc: dict) -> ClaimSubmission:
    inp = tc["input"]
    docs = [_parse_doc(d) for d in inp.get("documents", [])]
    history = [
        ClaimHistoryEntry(**h) for h in inp.get("claims_history", [])
    ]
    return ClaimSubmission(
        member_id=inp["member_id"],
        policy_id=inp["policy_id"],
        claim_category=ClaimCategory(inp["claim_category"]),
        treatment_date=inp["treatment_date"],
        claimed_amount=inp["claimed_amount"],
        hospital_name=inp.get("hospital_name"),
        ytd_claims_amount=inp.get("ytd_claims_amount", 0.0),
        claims_history=history,
        documents=docs,
        simulate_component_failure=inp.get("simulate_component_failure", False),
    )


def _check_match(tc: dict, result) -> tuple[bool, str]:
    expected = tc["expected"]
    exp_decision = expected.get("decision")

    # Early stop cases (TC001, TC002, TC003) expect decision=null
    if exp_decision is None:
        is_needs_docs = result.decision == DecisionType.NEEDS_DOCUMENTS
        if is_needs_docs:
            return True, "PASS — early stop triggered correctly"
        return False, f"FAIL — expected early stop (NEEDS_DOCUMENTS), got {result.decision.value}"

    if result.decision.value != exp_decision:
        return False, f"FAIL — expected {exp_decision}, got {result.decision.value}"

    # Amount check
    exp_amount = expected.get("approved_amount")
    if exp_amount is not None:
        if abs(result.approved_amount - exp_amount) > 1.0:
            return False, f"FAIL — amount mismatch: expected ₹{exp_amount}, got ₹{result.approved_amount}"

    # Confidence check
    exp_conf = expected.get("confidence_score")
    if exp_conf and "above" in str(exp_conf):
        threshold = float(str(exp_conf).split("above")[1].strip())
        if result.confidence < threshold:
            return False, f"FAIL — confidence {result.confidence:.2f} < threshold {threshold}"

    return True, f"PASS"


def _format_trace(trace) -> str:
    lines = []
    for event in trace.events:
        status_icon = "✓" if event.status == "OK" else ("⚠" if event.status == "DEGRADED" else "⏹")
        lines.append(f"  {status_icon} {event.step} [{event.status.value}] {event.duration_ms:.0f}ms")
        if event.error:
            lines.append(f"    ⚠ Error: {event.error[:120]}")
    return "\n".join(lines)


async def run_eval():
    tc_path = Path(__file__).parent.parent.parent / "test_cases.json"
    with open(tc_path) as f:
        data = json.load(f)

    policy = load_policy()
    orchestrator = ClaimOrchestrator(policy)

    results = []
    passed = 0
    failed = 0

    print(f"Running {len(data['test_cases'])} test cases...\n")

    for tc in data["test_cases"]:
        case_id = tc["case_id"]
        case_name = tc["case_name"]
        print(f"  [{case_id}] {case_name}...", end=" ", flush=True)

        submission = _parse_submission(tc)

        result, trace = await orchestrator.process(submission, claim_id=case_id)
        match, match_msg = _check_match(tc, result)

        if match:
            passed += 1
            print(f"✓ PASS")
        else:
            failed += 1
            print(f"✗ FAIL — {match_msg}")

        results.append({
            "tc": tc,
            "result": result,
            "trace": trace,
            "match": match,
            "match_msg": match_msg,
        })

    print(f"\nResults: {passed}/{len(data['test_cases'])} passed\n")

    # Generate markdown report
    _write_report(results, passed, data["test_cases"])


def _write_report(results: list, passed: int, test_cases: list):
    report_path = Path(__file__).parent.parent.parent / "docs" / "eval_report.md"
    report_path.parent.mkdir(exist_ok=True)

    lines = [
        "# Eval Report — Plum Claims Processing System",
        f"\n**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Result:** {passed}/{len(test_cases)} test cases matched expected outcome\n",
        "---\n",
    ]

    for r in results:
        tc = r["tc"]
        result = r["result"]
        trace = r["trace"]
        match = r["match"]
        match_msg = r["match_msg"]
        expected = tc["expected"]

        status = "✅ PASS" if match else "❌ FAIL"
        lines.append(f"## {tc['case_id']} — {tc['case_name']} {status}\n")
        lines.append(f"**Description:** {tc['description']}\n")

        lines.append("**Expected:**")
        lines.append(f"- Decision: `{expected.get('decision', 'NEEDS_DOCUMENTS (early stop)')}`")
        if "approved_amount" in expected:
            lines.append(f"- Approved Amount: ₹{expected['approved_amount']:,}")
        if "rejection_reasons" in expected:
            lines.append(f"- Rejection Reasons: {expected['rejection_reasons']}")
        lines.append("")

        lines.append("**Actual:**")
        lines.append(f"- Decision: `{result.decision.value}`")
        lines.append(f"- Approved Amount: ₹{result.approved_amount:,}")
        lines.append(f"- Confidence: {result.confidence:.3f}")
        if result.rejection_reasons:
            lines.append(f"- Rejection Reasons: {[r.value for r in result.rejection_reasons]}")
        if result.degraded_components:
            lines.append(f"- Degraded Components: {result.degraded_components}")
        lines.append("")

        lines.append(f"**Match:** {match_msg}\n")

        if result.member_message:
            lines.append(f"**Member Message:**\n> {result.member_message}\n")

        if result.line_item_breakdown:
            lines.append("**Line Items:**")
            for item in result.line_item_breakdown:
                lines.append(f"- {item.description}: claimed ₹{item.claimed_amount:,} → approved ₹{item.approved_amount:,} [{item.status}]{' — ' + item.reason if item.reason else ''}")
            lines.append("")

        lines.append("**Trace:**")
        lines.append("```")
        lines.append(_format_trace(trace))
        lines.append("```\n")

        if not match:
            lines.append(f"**Why it didn't match:** {match_msg}\n")

        lines.append("---\n")

    report_path.write_text("\n".join(lines))
    print(f"Eval report written to: {report_path}")


if __name__ == "__main__":
    asyncio.run(run_eval())
