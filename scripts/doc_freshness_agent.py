#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Documentation Freshness Agent Script
# Label: DOC-FRESHNESS-001
#
# Checks that documentation stays in sync with code changes.
# Scans for undocumented public APIs and validates capability baseline.
#
# Phases:
#   check      — Compare changed source files against doc updates
#   scan-apis  — Scan for public functions/classes without docstrings
#   baseline   — Validate capability_baseline.json reflects current modules

"""
Documentation Freshness Agent — enforces documentation currency.

Usage:
    python doc_freshness_agent.py --phase check --output-dir <dir>
    python doc_freshness_agent.py --phase scan-apis --output-dir <dir>
    python doc_freshness_agent.py --phase baseline --output-dir <dir>
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("doc-freshness-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "DOC-FRESHNESS-001"

DOC_DIRS = [
    Path("Murphy System/docs"),
    Path("docs"),
]
API_DOC_FILES = [
    Path("API_DOCUMENTATION.md"),
    Path("API_ROUTES.md"),
]
BASELINE_PATH = Path("Murphy System/docs/capability_baseline.json")


# ── Phase: Check ─────────────────────────────────────────────────────────────
def phase_check(output_dir: Path) -> dict[str, Any]:
    """Compare changed source files against documentation updates."""
    log.info("Phase: CHECK — analyzing documentation freshness")

    # Get recently changed Python files (git diff against main)
    changed_py = _get_changed_python_files()
    changed_docs = _get_changed_doc_files()

    # Identify source files changed without corresponding doc updates
    doc_debts: list[dict[str, str]] = []
    for py_file in changed_py:
        # Check if any doc file was also changed
        has_doc_update = len(changed_docs) > 0
        if not has_doc_update:
            doc_debts.append({
                "file": str(py_file),
                "reason": "Source changed without documentation update",
            })

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "check",
        "files_changed": len(changed_py),
        "docs_changed": len(changed_docs),
        "doc_debts": len(doc_debts),
        "debts": doc_debts[:50],  # Cap for readability
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "freshness_check.json").write_text(json.dumps(report, indent=2))
    log.info("Check complete: %d source changes, %d doc debts", len(changed_py), len(doc_debts))
    return report


def _get_changed_python_files() -> list[Path]:
    """Get Python files changed relative to main branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "--", "*.py"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return [Path(f) for f in result.stdout.strip().splitlines() if f.startswith("src/")]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.debug("git diff failed: %s", exc)
    return []


def _get_changed_doc_files() -> list[Path]:
    """Get documentation files changed relative to main branch."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "--", "*.md"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return [Path(f) for f in result.stdout.strip().splitlines()]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.debug("git diff failed: %s", exc)
    return []


# ── Phase: Scan APIs ────────────────────────────────────────────────────────
def phase_scan_apis(output_dir: Path) -> dict[str, Any]:
    """Scan for public functions/classes without docstrings."""
    log.info("Phase: SCAN-APIS — finding undocumented public APIs")
    src_dir = Path("src")
    if not src_dir.exists():
        src_dir = Path("Murphy System/src")

    missing: list[dict[str, Any]] = []
    total_public = 0

    for py_file in sorted(src_dir.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name.startswith("_"):
                    continue
                total_public += 1
                docstring = ast.get_docstring(node)
                if not docstring:
                    missing.append({
                        "file": str(py_file),
                        "name": node.name,
                        "type": type(node).__name__,
                        "line": node.lineno,
                    })

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "scan-apis",
        "total_public_apis": total_public,
        "missing_docstrings": len(missing),
        "coverage_pct": round(
            ((total_public - len(missing)) / max(total_public, 1)) * 100, 1
        ),
        "undocumented": missing[:100],  # Cap for readability
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "api_scan.json").write_text(json.dumps(report, indent=2))
    log.info(
        "API scan: %d public APIs, %d missing docstrings (%.1f%% coverage)",
        total_public, len(missing), report["coverage_pct"],
    )
    return report


# ── Phase: Baseline ──────────────────────────────────────────────────────────
def phase_baseline(output_dir: Path) -> dict[str, Any]:
    """Validate capability_baseline.json reflects current module set."""
    log.info("Phase: BASELINE — checking capability baseline")
    src_dir = Path("src")
    if not src_dir.exists():
        src_dir = Path("Murphy System/src")

    current_modules = set()
    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        rel = py_file.relative_to(src_dir)
        module_key = str(rel).replace("/", ".").replace("\\", ".").removesuffix(".py")
        current_modules.add(module_key)

    baseline_modules: set[str] = set()
    drift_count = 0
    if BASELINE_PATH.exists():
        try:
            data = json.loads(BASELINE_PATH.read_text())
            if isinstance(data, dict):
                raw = data.get("modules", [])
                if isinstance(raw, dict):
                    baseline_modules = set(raw.keys())
                elif isinstance(raw, list):
                    baseline_modules = {
                        (item if isinstance(item, str) else item.get("module", ""))
                        for item in raw
                    }
            elif isinstance(data, list):
                baseline_modules = {
                    (item if isinstance(item, str) else item.get("module", ""))
                    for item in data
                }
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Failed to parse baseline: %s", exc)

    missing_from_baseline = current_modules - baseline_modules
    removed_from_source = baseline_modules - current_modules
    drift_count = len(missing_from_baseline) + len(removed_from_source)

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "baseline",
        "current_module_count": len(current_modules),
        "baseline_module_count": len(baseline_modules),
        "baseline_drift": drift_count,
        "missing_from_baseline": sorted(list(missing_from_baseline))[:50],
        "removed_from_source": sorted(list(removed_from_source))[:50],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "baseline_check.json").write_text(json.dumps(report, indent=2))

    # Merge all phases into combined report
    _merge_reports(output_dir)

    log.info("Baseline check: %d drift items", drift_count)
    return report


def _merge_reports(output_dir: Path) -> None:
    """Merge all phase reports into a single freshness report."""
    combined: dict[str, Any] = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    for name in ["freshness_check", "api_scan", "baseline_check"]:
        path = output_dir / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            combined.update({
                k: v for k, v in data.items()
                if k not in ("agent", "version", "timestamp", "phase")
            })

    (output_dir / "freshness_report.json").write_text(json.dumps(combined, indent=2))

    # Generate markdown report for PR comments
    md_lines = [
        "## 📄 Documentation Freshness Report",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Files changed | {combined.get('files_changed', 'N/A')} |",
        f"| Doc debts | {combined.get('doc_debts', 'N/A')} |",
        f"| Missing docstrings | {combined.get('missing_docstrings', 'N/A')} |",
        f"| Docstring coverage | {combined.get('coverage_pct', 'N/A')}% |",
        f"| Baseline drift | {combined.get('baseline_drift', 'N/A')} |",
        "",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
    ]
    (output_dir / "freshness_report.md").write_text("\n".join(md_lines))


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Documentation Freshness Agent")
    parser.add_argument("--phase", required=True, choices=["check", "scan-apis", "baseline"])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "check":
        phase_check(args.output_dir)
    elif args.phase == "scan-apis":
        phase_scan_apis(args.output_dir)
    elif args.phase == "baseline":
        phase_baseline(args.output_dir)


if __name__ == "__main__":
    main()
