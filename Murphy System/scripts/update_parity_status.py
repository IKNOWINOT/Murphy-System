#!/usr/bin/env python3
"""
scripts/update_parity_status.py
================================

Runs all ``pytest.mark.parity`` acceptance tests for Management Parity
Phases 2–8 and auto-updates the acceptance criteria checkboxes in
``STATUS.md``.

Usage::

    python scripts/update_parity_status.py [--dry-run] [--status-file PATH]

Options:
    --dry-run         Print what would be written without modifying STATUS.md
    --status-file     Path to STATUS.md (default: STATUS.md relative to repo root)

Exit codes:
    0 – all parity tests passed and STATUS.md updated successfully
    1 – one or more parity tests failed
    2 – runtime error (import failure, file not found, etc.)

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

PARITY_TESTS: List[Dict[str, Any]] = [
    {
        "phase": 2,
        "name": "Real-Time Collaboration",
        "test_file": "tests/test_mgmt_parity_phase2.py",
        "status_key": "Phase 2",
    },
    {
        "phase": 3,
        "name": "Dashboards",
        "test_file": "tests/test_mgmt_parity_phase3.py",
        "status_key": "Phase 3",
    },
    {
        "phase": 4,
        "name": "Portfolio Management",
        "test_file": "tests/test_mgmt_parity_phase4.py",
        "status_key": "Phase 4",
    },
    {
        "phase": 5,
        "name": "WorkDocs",
        "test_file": "tests/test_mgmt_parity_phase5.py",
        "status_key": "Phase 5",
    },
    {
        "phase": 6,
        "name": "Time Tracking",
        "test_file": "tests/test_mgmt_parity_phase6.py",
        "status_key": "Phase 6",
    },
    {
        "phase": 7,
        "name": "Advanced Automations",
        "test_file": "tests/test_mgmt_parity_phase7.py",
        "status_key": "Phase 7",
    },
    {
        "phase": 8,
        "name": "CRM",
        "test_file": "tests/test_mgmt_parity_phase8.py",
        "status_key": "Phase 8",
    },
]

# Marker used by all parity tests
PARITY_MARKER = "parity"


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


def run_parity_tests(repo_root: Path, verbose: bool = False) -> Dict[str, Any]:
    """Run all parity-marked tests with pytest and return a parsed result dict.

    Returns::

        {
            "passed": bool,
            "total": int,
            "passed_count": int,
            "failed_count": int,
            "error_count": int,
            "phases": {
                2: {"passed": True, "tests": 42, "failed": 0},
                ...
            },
            "raw_output": str,
        }
    """
    test_paths = [
        str(repo_root / entry["test_file"])
        for entry in PARITY_TESTS
    ]

    cmd = [
        sys.executable, "-m", "pytest",
        f"-m", PARITY_MARKER,
        "--tb=short",
        "--no-cov",
        "--json-report",
        "--json-report-file=-",  # write JSON to stdout
        "-q",
    ] + test_paths

    if verbose:
        cmd.append("-v")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
            timeout=300,
        )
    except FileNotFoundError:
        # pytest-json-report may not be installed; fall back to plain pytest
        return _run_parity_tests_plain(repo_root, test_paths, verbose)
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "total": 0,
            "passed_count": 0,
            "failed_count": 0,
            "error_count": 1,
            "phases": {entry["phase"]: {"passed": False, "tests": 0, "failed": 0}
                       for entry in PARITY_TESTS},
            "raw_output": "Test run timed out after 300 seconds.",
        }

    raw_output = result.stdout + result.stderr

    # Try to parse JSON report from stdout (pytest-json-report writes to stdout
    # when --json-report-file=-)
    try:
        json_start = raw_output.index("{")
        json_data = json.loads(raw_output[json_start:])
        return _parse_json_report(json_data)
    except (ValueError, json.JSONDecodeError):
        pass

    # Fall back to plain-text parsing
    return _parse_plain_output(result.returncode, raw_output)


def _run_parity_tests_plain(
    repo_root: Path,
    test_paths: List[str],
    verbose: bool,
) -> Dict[str, Any]:
    """Run pytest without the JSON report plugin."""
    cmd = [
        sys.executable, "-m", "pytest",
        f"-m", PARITY_MARKER,
        "--tb=short",
        "--no-cov",
        "-v",
    ] + test_paths

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src") + os.pathsep + env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "total": 0, "passed_count": 0,
            "failed_count": 0, "error_count": 1,
            "phases": {e["phase"]: {"passed": False, "tests": 0, "failed": 0}
                       for e in PARITY_TESTS},
            "raw_output": "Timed out.",
        }

    raw_output = result.stdout + result.stderr
    return _parse_plain_output(result.returncode, raw_output)


def _parse_json_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a pytest-json-report output dict."""
    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed_count = summary.get("passed", 0)
    failed_count = summary.get("failed", 0)
    error_count = summary.get("error", 0)

    # Build per-phase results from test node IDs
    phase_results: Dict[int, Dict[str, Any]] = {
        entry["phase"]: {"passed": True, "tests": 0, "failed": 0}
        for entry in PARITY_TESTS
    }

    for test in data.get("tests", []):
        node_id: str = test.get("nodeid", "")
        outcome: str = test.get("outcome", "failed")
        for entry in PARITY_TESTS:
            phase_file = f"test_mgmt_parity_phase{entry['phase']}"
            if phase_file in node_id:
                phase_results[entry["phase"]]["tests"] += 1
                if outcome != "passed":
                    phase_results[entry["phase"]]["failed"] += 1
                    phase_results[entry["phase"]]["passed"] = False
                break

    return {
        "passed": failed_count == 0 and error_count == 0,
        "total": total,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "error_count": error_count,
        "phases": phase_results,
        "raw_output": "",
    }


def _parse_plain_output(returncode: int, output: str) -> Dict[str, Any]:
    """Parse plain pytest text output for summary counts."""
    passed_count = 0
    failed_count = 0
    error_count = 0

    # Match: "N passed, M failed, K errors" summary line
    summary_match = re.search(
        r"(\d+) passed",
        output,
    )
    if summary_match:
        passed_count = int(summary_match.group(1))

    failed_match = re.search(r"(\d+) failed", output)
    if failed_match:
        failed_count = int(failed_match.group(1))

    error_match = re.search(r"(\d+) error", output)
    if error_match:
        error_count = int(error_match.group(1))

    # Per-phase: check for PASSED/FAILED lines per test file
    phase_results: Dict[int, Dict[str, Any]] = {}
    for entry in PARITY_TESTS:
        phase = entry["phase"]
        file_tag = f"test_mgmt_parity_phase{phase}"
        file_lines = [line for line in output.splitlines() if file_tag in line]
        phase_tests = len([l for l in file_lines if "PASSED" in l or "FAILED" in l or "ERROR" in l])
        phase_failed = len([l for l in file_lines if "FAILED" in l or "ERROR" in l])
        phase_results[phase] = {
            "passed": phase_failed == 0,
            "tests": phase_tests,
            "failed": phase_failed,
        }

    return {
        "passed": returncode == 0,
        "total": passed_count + failed_count + error_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "error_count": error_count,
        "phases": phase_results,
        "raw_output": output,
    }


# ---------------------------------------------------------------------------
# STATUS.md updater
# ---------------------------------------------------------------------------


def update_status_md(
    status_path: Path,
    results: Dict[str, Any],
    dry_run: bool = False,
) -> str:
    """Read STATUS.md, update parity acceptance criteria, and write it back.

    Returns the updated content (or what would be written in dry-run mode).
    """
    if not status_path.exists():
        raise FileNotFoundError(f"STATUS.md not found at {status_path}")

    content = status_path.read_text(encoding="utf-8")

    # Locate the G-009 row and update its status column (per-phase)
    for entry in PARITY_TESTS:
        phase = entry["phase"]
        name = entry["name"]
        phase_result = results["phases"].get(phase, {})
        passed = phase_result.get("passed", False)
        tests = phase_result.get("tests", 0)
        failed = phase_result.get("failed", 0)

        status_icon = "✅" if passed else "❌"
        test_summary = f"{tests - failed}/{tests} tests passing" if tests > 0 else "0 tests run"

        # Match table rows referencing this phase number, e.g.:
        #   | G-NNN | ... Phase N ... | priority | action path |
        # Group 1 captures everything up to and including the last "|" before the
        # action-path column; group 2 captures the rest of the row up to the next "|".
        phase_pattern = re.compile(
            rf"(\|\s*(?:G-\d+|PARITY-{phase})\s*\|[^|]*Phase\s+{phase}[^|]*\|[^|]*\|)([^|]*\|)",
            re.IGNORECASE,
        )
        replacement = rf"\1 {status_icon} Phase {phase} ({name}): {test_summary} |"
        new_content, n = phase_pattern.subn(replacement, content)
        if n > 0:
            content = new_content

    overall_passed = results.get("passed", False)
    overall_icon = "✅" if overall_passed else "❌"
    total = results.get("total", 0)
    passed_count = results.get("passed_count", 0)

    # Update the G-009 overall row.
    # The row uses strikethrough (~~G-009~~) because the gap was previously
    # marked resolved; we overwrite the action-path column with the latest
    # automated test result so the status always reflects real evidence.
    # Pattern: captures (prefix up to last "|"), (action-path text), (closing "|").
    g009_pattern = re.compile(
        r"(\|\s*~~G-009~~\s*\|[^|]*\|[^|]*\|)(.*?)(\|)",
        re.DOTALL,
    )
    g009_replacement = (
        rf"\1 {overall_icon} **Acceptance tests run** — "
        rf"{passed_count}/{total} tests passing "
        rf"(Phases 2–8: collaboration, dashboards, portfolio, workdocs, "
        rf"time tracking, automations, CRM) \3"
    )
    new_content, n = g009_pattern.subn(g009_replacement, content)
    if n > 0:
        content = new_content

    # Also ensure the parity test marker section exists
    parity_section = _build_parity_section(results)
    if "## Parity Acceptance Test Results" in content:
        # Replace the existing section
        section_pattern = re.compile(
            r"## Parity Acceptance Test Results.*?(?=\n## |\Z)",
            re.DOTALL,
        )
        content = section_pattern.sub(parity_section, content)
    else:
        # Append the section before "## Infrastructure Deferred Items"
        insert_before = "## Infrastructure Deferred Items"
        if insert_before in content:
            content = content.replace(
                insert_before,
                parity_section + "\n\n" + insert_before,
            )
        else:
            content = content.rstrip() + "\n\n" + parity_section + "\n"

    if not dry_run:
        status_path.write_text(content, encoding="utf-8")

    return content


def _build_parity_section(results: Dict[str, Any]) -> str:
    """Build a Markdown section summarising parity test results."""
    lines = [
        "## Parity Acceptance Test Results",
        "",
        f"*Last run by `scripts/update_parity_status.py` — "
        f"{results.get('passed_count', 0)}/{results.get('total', 0)} tests passing*",
        "",
        "| Phase | Feature | Tests | Status |",
        "|-------|---------|-------|--------|",
    ]
    for entry in PARITY_TESTS:
        phase = entry["phase"]
        name = entry["name"]
        pr = results["phases"].get(phase, {})
        passed = pr.get("passed", False)
        tests = pr.get("tests", 0)
        failed = pr.get("failed", 0)
        icon = "✅" if passed else ("❌" if tests > 0 else "⬜")
        passing = tests - failed
        lines.append(f"| {phase} | {name} | {passing}/{tests} | {icon} |")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Management Parity acceptance tests and update STATUS.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying STATUS.md",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help="Path to STATUS.md (default: <repo_root>/STATUS.md)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Pass -v to pytest for detailed output",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    status_file: Path = args.status_file or (REPO_ROOT / "STATUS.md")

    print("=" * 60)
    print("Murphy System — Management Parity Acceptance Tests")
    print("=" * 60)
    print(f"Repo root : {REPO_ROOT}")
    print(f"Status MD : {status_file}")
    print()

    # 1. Run parity tests
    print("Running parity tests …")
    results = run_parity_tests(REPO_ROOT, verbose=args.verbose)

    # 2. Print per-phase summary
    print()
    print(f"{'Phase':<8} {'Feature':<28} {'Tests':<10} Status")
    print("-" * 60)
    for entry in PARITY_TESTS:
        phase = entry["phase"]
        name = entry["name"]
        pr = results["phases"].get(phase, {})
        passed = pr.get("passed", False)
        tests = pr.get("tests", 0)
        failed = pr.get("failed", 0)
        icon = "✅ PASS" if passed else ("❌ FAIL" if tests > 0 else "⬜ NO TESTS")
        print(f"{phase:<8} {name:<28} {tests - failed}/{tests:<9} {icon}")

    print("-" * 60)
    print(
        f"Total: {results['passed_count']}/{results['total']} passing, "
        f"{results['failed_count']} failed, "
        f"{results['error_count']} errors"
    )
    print()

    # 3. Update STATUS.md
    if args.dry_run:
        print("[dry-run] Would update STATUS.md — no file changes made.")
        updated = update_status_md(status_file, results, dry_run=True)
        # Show diff excerpt
        print("--- Updated STATUS.md parity section preview ---")
        if "## Parity Acceptance Test Results" in updated:
            start = updated.index("## Parity Acceptance Test Results")
            end = updated.find("\n## ", start + 1)
            print(updated[start: end if end != -1 else start + 1000])
    else:
        try:
            update_status_md(status_file, results, dry_run=False)
            print(f"✅ STATUS.md updated: {status_file}")
        except FileNotFoundError as exc:
            print(f"⚠️  {exc} — STATUS.md not updated.")

    # 4. Exit with appropriate code
    if not results["passed"]:
        print("\n❌ Some parity tests failed — see output above.")
        return 1

    print("\n✅ All parity tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
