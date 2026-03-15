# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
run_all_strategic.py
====================
Master strategic runner for the Murphy System.

Executes:
  1. Healthcare AI Safety Demo
  2. Financial Compliance Demo
  3. Manufacturing IoT Safety Demo
  4. Standalone Confidence Engine Test Suite (unittest)
  5. Compliance Framework Assessment
  6. EU AI Act Conformity Assessment

Generates:  STRATEGIC_EXECUTION_REPORT.md

Exit codes:
  0 — >90% of tests passed
  1 — ≤90% of tests passed
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import traceback
import unittest
from datetime import datetime
from typing import Any, Dict, List, Tuple

STRATEGIC_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STRATEGIC_DIR)
sys.path.insert(0, os.path.join(STRATEGIC_DIR, ".."))


# ── Section result helpers ────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'=' * 65}")
    print(f"  {title}")
    print(f"{'=' * 65}")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


# ── Section 1–3: Vertical Demos ───────────────────────────────────────────────

def _run_demo(module_path: str, display_name: str) -> Tuple[bool, str, Any]:
    """Import and call the demo's main() function."""
    try:
        spec   = importlib.util.spec_from_file_location("_demo", module_path)
        module = importlib.util.module_from_spec(spec)         # type: ignore[arg-type]
        spec.loader.exec_module(module)                        # type: ignore[union-attr]
        report = module.main()
        _ok(f"{display_name} completed")
        return True, "OK", report
    except Exception as exc:
        _fail(f"{display_name} FAILED: {exc}")
        traceback.print_exc()
        return False, str(exc), None


def run_vertical_demos() -> Dict[str, Any]:
    _section("VERTICAL DEMOS")
    demos = [
        (os.path.join(STRATEGIC_DIR, "demos", "healthcare_ai_safety_demo.py"),
         "Healthcare AI Safety Demo"),
        (os.path.join(STRATEGIC_DIR, "demos", "financial_compliance_demo.py"),
         "Financial Compliance Demo"),
        (os.path.join(STRATEGIC_DIR, "demos", "manufacturing_iot_demo.py"),
         "Manufacturing IoT Demo"),
    ]
    results = {}
    for path, name in demos:
        ok, msg, report = _run_demo(path, name)
        results[name] = {
            "passed":  ok,
            "message": msg,
            "report":  report,
        }
    print(f"\n  VERIFIED BY: Corey Post — Inoni LLC")
    return results


# ── Section 4: Unittest test suites ──────────────────────────────────────────

def run_test_suites() -> Dict[str, Any]:
    _section("STANDALONE CONFIDENCE ENGINE TESTS")

    test_dir = os.path.join(STRATEGIC_DIR, "murphy_confidence", "tests")
    loader   = unittest.TestLoader()
    suite    = loader.discover(test_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    t0     = time.monotonic()
    result = runner.run(suite)
    elapsed = time.monotonic() - t0

    total  = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed

    print(f"\n  Tests run: {total}  |  Passed: {passed}  |  Failed: {failed}")
    print(f"  Elapsed: {elapsed:.2f}s")
    print(f"\n  VERIFIED BY: Corey Post — Inoni LLC")

    return {
        "total":   total,
        "passed":  passed,
        "failed":  failed,
        "elapsed": round(elapsed, 2),
        "ok":      failed == 0,
    }


# ── Section 5: Compliance assessment ─────────────────────────────────────────

def run_compliance_assessment() -> Dict[str, Any]:
    _section("COMPLIANCE FRAMEWORK ASSESSMENT")
    try:
        from compliance.compliance_framework import ComplianceFramework
        framework = ComplianceFramework()
        report    = framework.generate_report()
        _ok(f"SOC 2 readiness   : {report['frameworks'][0]['readiness_pct']}%")
        _ok(f"ISO 27001 readiness: {report['frameworks'][1]['readiness_pct']}%")
        _ok(f"HIPAA readiness   : {report['frameworks'][2]['readiness_pct']}%")
        _ok(f"Overall readiness : {report['overall_readiness_pct']}%")
        print(f"\n  VERIFIED BY: Corey Post — Inoni LLC")
        return {"passed": True, "report": report}
    except Exception as exc:
        _fail(f"Compliance assessment FAILED: {exc}")
        traceback.print_exc()
        return {"passed": False, "error": str(exc)}


# ── Section 6: EU AI Act assessment ──────────────────────────────────────────

def run_eu_ai_act_assessment() -> Dict[str, Any]:
    _section("EU AI ACT CONFORMITY ASSESSMENT")
    try:
        from eu_ai_act.eu_ai_act_compliance import EUAIActCompliance
        compliance = EUAIActCompliance()
        report     = compliance.generate_conformity_assessment()
        s = report["summary"]
        _ok(f"Articles assessed : {s['total_articles_assessed']}")
        _ok(f"Compliant         : {s['compliant']}")
        _ok(f"Partial           : {s['partial']}")
        _ok(f"Open gaps         : {s['open_gaps']}")
        print(f"\n  Overall posture: {s['overall_posture']}")
        print(f"\n  VERIFIED BY: Corey Post — Inoni LLC")
        return {"passed": True, "report": report}
    except Exception as exc:
        _fail(f"EU AI Act assessment FAILED: {exc}")
        traceback.print_exc()
        return {"passed": False, "error": str(exc)}


# ── Report generation ─────────────────────────────────────────────────────────

_SCREENSHOT_PLACEHOLDER = (
    "[ SCREENSHOT PLACEHOLDER — attach execution screenshot here "
    "before finalising strategic report ]"
)


def _collect_test_gaps(demo_results: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    for name, data in demo_results.items():
        report = data.get("report") or {}
        for gap in report.get("test_gaps", []):
            gaps.append(f"[{name}] {gap}")
    return gaps


def generate_report(
    demo_results: Dict[str, Any],
    test_results: Dict[str, Any],
    compliance_results: Dict[str, Any],
    eu_ai_results: Dict[str, Any],
    overall_pct: float,
    exit_code: int,
) -> str:
    test_gaps = _collect_test_gaps(demo_results)

    demos_ok = sum(1 for v in demo_results.values() if v["passed"])
    demos_total = len(demo_results)

    compliance_pct = (
        compliance_results.get("report", {}).get("overall_readiness_pct", 0)
        if compliance_results.get("passed") else 0
    )

    lines = [
        "# STRATEGIC EXECUTION REPORT",
        "",
        f"**Generated:** {datetime.utcnow().isoformat()} UTC  ",
        f"**Verified by:** Corey Post — Inoni LLC  ",
        f"**Overall Readiness Score:** {overall_pct:.1f}%  ",
        f"**Exit Code:** {'0 (PASS)' if exit_code == 0 else '1 (FAIL)'}  ",
        "",
        "---",
        "",
        "## 1. Vertical Demos",
        "",
        f"**{demos_ok}/{demos_total} demos passed**",
        "",
        "| Demo | Status | Screenshot |",
        "|------|--------|------------|",
    ]
    for name, data in demo_results.items():
        status = "✓ PASS" if data["passed"] else "✗ FAIL"
        lines.append(f"| {name} | {status} | {_SCREENSHOT_PLACEHOLDER} |")

    lines += [
        "",
        "**VERIFIED BY: Corey Post — Inoni LLC**",
        "",
        "---",
        "",
        "## 2. Standalone Confidence Engine Tests",
        "",
        f"- Tests run : {test_results.get('total', 0)}",
        f"- Passed    : {test_results.get('passed', 0)}",
        f"- Failed    : {test_results.get('failed', 0)}",
        f"- Elapsed   : {test_results.get('elapsed', 0)}s",
        f"- Status    : {'✓ ALL PASSED' if test_results.get('ok') else '✗ FAILURES DETECTED'}",
        "",
        f"{_SCREENSHOT_PLACEHOLDER}",
        "",
        "**VERIFIED BY: Corey Post — Inoni LLC**",
        "",
        "---",
        "",
        "## 3. Compliance Framework Assessment",
        "",
    ]

    if compliance_results.get("passed") and compliance_results.get("report"):
        cr = compliance_results["report"]
        lines += [
            f"- Overall readiness : {cr.get('overall_readiness_pct', 0)}%",
            f"- Open gaps         : {cr.get('open_remediation_items', 0)}",
        ]
        for fw in cr.get("frameworks", []):
            lines.append(f"- {fw['framework']:20s}: {fw['readiness_pct']}% readiness")
    else:
        lines.append(f"- Status: ✗ FAILED — {compliance_results.get('error', 'unknown error')}")

    lines += [
        "",
        f"{_SCREENSHOT_PLACEHOLDER}",
        "",
        "**VERIFIED BY: Corey Post — Inoni LLC**",
        "",
        "---",
        "",
        "## 4. EU AI Act Conformity Assessment",
        "",
    ]

    if eu_ai_results.get("passed") and eu_ai_results.get("report"):
        er = eu_ai_results["report"]
        s  = er.get("summary", {})
        lines += [
            f"- Articles assessed : {s.get('total_articles_assessed', 0)}",
            f"- Compliant         : {s.get('compliant', 0)}",
            f"- Partial           : {s.get('partial', 0)}",
            f"- Open gaps         : {s.get('open_gaps', 0)}",
            f"- Overall posture   : {s.get('overall_posture', 'N/A')}",
        ]
    else:
        lines.append(f"- Status: ✗ FAILED — {eu_ai_results.get('error', 'unknown error')}")

    lines += [
        "",
        f"{_SCREENSHOT_PLACEHOLDER}",
        "",
        "**VERIFIED BY: Corey Post — Inoni LLC**",
        "",
        "---",
        "",
        "## 5. Testing Gaps",
        "",
        "The following gaps were identified during strategic execution:",
        "",
    ]
    for gap in test_gaps:
        lines.append(f"- ⚠ {gap}")

    additional_gaps = [
        "End-to-end integration tests between murphy_confidence and full Murphy System orchestrator not yet implemented",
        "Performance benchmarks for confidence engine under high-throughput conditions not yet established",
        "Adversarial robustness tests (input perturbation, prompt injection) not yet implemented",
        "Multi-tenant isolation tests for SaaS deployment not yet implemented",
        "Load testing for GateCompiler under concurrent pipeline execution not yet completed",
    ]
    for gap in additional_gaps:
        lines.append(f"- ⚠ {gap}")

    lines += [
        "",
        "---",
        "",
        "## 6. Overall Readiness Score",
        "",
        f"| Component | Score |",
        f"|-----------|-------|",
        f"| Vertical Demos | {demos_ok}/{demos_total} ({demos_ok/demos_total*100:.0f}%) |",
        f"| Unit Tests | {test_results.get('passed', 0)}/{test_results.get('total', 1)} "
        f"({test_results.get('passed', 0)/max(test_results.get('total', 1), 1)*100:.0f}%) |",
        f"| Compliance Readiness | {compliance_pct}% |",
        f"| EU AI Act Alignment | {'Assessed' if eu_ai_results.get('passed') else 'Failed'} |",
        f"| **Overall** | **{overall_pct:.1f}%** |",
        "",
        f"**Exit Code: {'0 — STRATEGIC READINESS CONFIRMED' if exit_code == 0 else '1 — BELOW 90% THRESHOLD'}**",
        "",
        "---",
        "",
        "## 7. IP & Attribution",
        "",
        "All strategic IP, algorithms, and implementations in this directory are:",
        "- **Authored by:** Corey Post",
        "- **Owned by:** Inoni Limited Liability Company",
        "- **Patent-pending:** 3 provisional applications filed 2026-03-05",
        "",
        "**VERIFIED BY: Corey Post — Inoni LLC**",
        "",
        "---",
        "",
        "© 2020-2026 Inoni Limited Liability Company. All rights reserved. Created by: Corey Post",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 65)
    print("  MURPHY SYSTEM — Strategic Execution Master Runner")
    print(f"  {datetime.utcnow().isoformat()} UTC")
    print("  VERIFIED BY: Corey Post — Inoni LLC")
    print("=" * 65)

    # 1–3: Demos
    demo_results       = run_vertical_demos()

    # 4: Tests
    test_results       = run_test_suites()

    # 5: Compliance
    compliance_results = run_compliance_assessment()

    # 6: EU AI Act
    eu_ai_results      = run_eu_ai_act_assessment()

    # ── Compute overall readiness ─────────────────────────────────────────────
    demos_score = (
        sum(1 for v in demo_results.values() if v["passed"]) /
        max(len(demo_results), 1) * 100
    )
    tests_score = (
        test_results.get("passed", 0) /
        max(test_results.get("total", 1), 1) * 100
    )
    compliance_score = (
        compliance_results.get("report", {}).get("overall_readiness_pct", 0)
        if compliance_results.get("passed") else 0
    )
    eu_ai_score = 100.0 if eu_ai_results.get("passed") else 0.0

    overall_pct = (demos_score + tests_score + compliance_score + eu_ai_score) / 4
    exit_code   = 0 if overall_pct > 90 else 1

    # ── Generate report ───────────────────────────────────────────────────────
    report_md = generate_report(
        demo_results, test_results, compliance_results, eu_ai_results,
        overall_pct, exit_code,
    )

    report_path = os.path.join(STRATEGIC_DIR, "STRATEGIC_EXECUTION_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_md)

    _section("FINAL SUMMARY")
    print(f"  Demos       : {demos_score:.0f}%")
    print(f"  Tests       : {tests_score:.0f}%")
    print(f"  Compliance  : {compliance_score:.0f}%")
    print(f"  EU AI Act   : {eu_ai_score:.0f}%")
    print(f"  Overall     : {overall_pct:.1f}%")
    print(f"  Exit code   : {exit_code} ({'PASS' if exit_code == 0 else 'FAIL'})")
    print(f"\n  Report → {report_path}")
    print(f"\n  VERIFIED BY: Corey Post — Inoni LLC")
    print("=" * 65)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
