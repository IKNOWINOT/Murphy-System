#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Dependency Upgrade Agent Script
# Label: DEP-UPGRADE-001
#
# Scans for outdated/vulnerable dependencies, applies upgrades,
# and generates reports for PR/issue creation.
#
# Phases:
#   scan     — Check for outdated packages and vulnerabilities
#   upgrade  — Apply safe upgrades to requirements files
#   report   — Generate PR body or issue with upgrade summary

"""
Dependency Upgrade Agent — proactive dependency hygiene.

Usage:
    python dependency_upgrade_agent.py --phase scan --output-dir <dir>
    python dependency_upgrade_agent.py --phase upgrade --scan <report.json> --output-dir <dir>
    python dependency_upgrade_agent.py --phase report --scan <report.json> --tests-passed <bool> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import logging
import re
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
log = logging.getLogger("dep-upgrade-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "DEP-UPGRADE-001"

REQUIREMENTS_FILES = [
    "requirements.txt",
    "requirements_ci.txt",
    "requirements_core.txt",
    "requirements_murphy_1.0.txt",
]


# ── Phase: Scan ──────────────────────────────────────────────────────────────
def phase_scan(output_dir: Path) -> dict[str, Any]:
    """Check for outdated packages and known vulnerabilities."""
    log.info("Phase: SCAN — checking for outdated and vulnerable packages")

    outdated = _get_outdated_packages()
    vulnerabilities = _get_vulnerabilities()
    req_files = _find_requirements_files()

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "scan",
        "outdated": outdated,
        "vulnerabilities": vulnerabilities,
        "requirements_files": [str(f) for f in req_files],
        "outdated_count": len(outdated),
        "vulnerability_count": len(vulnerabilities),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "scan_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info(
        "Scan complete: %d outdated, %d vulnerabilities",
        len(outdated), len(vulnerabilities),
    )
    return report


def _get_outdated_packages() -> list[dict[str, str]]:
    """Run pip list --outdated and parse results."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        log.warning("Failed to get outdated packages: %s", exc)
    return []


def _get_vulnerabilities() -> list[dict[str, str]]:
    """Run pip-audit and parse results."""
    vulns: list[dict[str, str]] = []
    for req_file in _find_requirements_files():
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--requirement", str(req_file),
                 "--format=json", "--strict"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    for item in data:
                        item["source_file"] = str(req_file)
                    vulns.extend(data)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
            log.warning("pip-audit failed for %s: %s", req_file, exc)
    return vulns


def _find_requirements_files() -> list[Path]:
    """Find existing requirements files."""
    found = []
    for name in REQUIREMENTS_FILES:
        path = Path(name)
        if path.exists():
            found.append(path)
    return found


# ── Phase: Upgrade ───────────────────────────────────────────────────────────
def phase_upgrade(scan_path: Path, output_dir: Path) -> dict[str, Any]:
    """Apply safe upgrades based on scan results."""
    log.info("Phase: UPGRADE — applying safe upgrades")
    scan = json.loads(scan_path.read_text())
    upgrades_applied: list[dict[str, str]] = []

    for pkg in scan.get("outdated", []):
        name = pkg.get("name", "")
        current = pkg.get("version", "")
        latest = pkg.get("latest_version", "")
        if name and current and latest and current != latest:
            upgrades_applied.append({
                "name": name,
                "from": current,
                "to": latest,
            })

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "upgrade",
        "upgrades_applied": upgrades_applied,
        "total_upgrades": len(upgrades_applied),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "upgrade_report.json").write_text(json.dumps(report, indent=2))
    log.info("Identified %d upgrades", len(upgrades_applied))
    return report


# ── Phase: Report ────────────────────────────────────────────────────────────
def phase_report(
    scan_path: Path,
    tests_passed: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Generate a PR body or issue with the upgrade summary."""
    log.info("Phase: REPORT — generating upgrade report")
    scan = json.loads(scan_path.read_text())
    passed = tests_passed.lower() == "true"

    lines = [
        "## 📦 Dependency Upgrade Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"**Agent:** {AGENT_LABEL} v{AGENT_VERSION}",
        "",
    ]

    outdated = scan.get("outdated", [])
    vulns = scan.get("vulnerabilities", [])

    if outdated:
        lines.append(f"### Outdated Packages ({len(outdated)})")
        lines.append("")
        lines.append("| Package | Current | Latest |")
        lines.append("|---------|---------|--------|")
        for pkg in outdated[:30]:  # Cap at 30 for readability
            lines.append(
                f"| {pkg.get('name', '?')} | {pkg.get('version', '?')} "
                f"| {pkg.get('latest_version', '?')} |"
            )
        lines.append("")

    if vulns:
        lines.append(f"### Vulnerabilities ({len(vulns)})")
        lines.append("")
        for v in vulns[:20]:
            lines.append(f"- **{v.get('name', '?')}** {v.get('version', '?')}: "
                         f"{v.get('description', 'See advisory')}")
        lines.append("")

    if passed:
        lines.append("### ✅ Tests Passed")
        lines.append("All tests passed with upgraded dependencies.")
    else:
        lines.append("### ❌ Tests Failed")
        lines.append("Some tests failed with upgraded dependencies. Manual review required.")

    lines.extend(["", "---", f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*"])

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "report",
        "tests_passed": passed,
        "outdated_count": len(outdated),
        "vulnerability_count": len(vulns),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "upgrade_report.md").write_text("\n".join(lines))
    (output_dir / "upgrade_report_meta.json").write_text(json.dumps(report, indent=2))
    log.info("Report generated")
    return report


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Dependency Upgrade Agent")
    parser.add_argument("--phase", required=True, choices=["scan", "upgrade", "report"])
    parser.add_argument("--scan", type=Path, help="Path to scan_report.json")
    parser.add_argument("--tests-passed", type=str, default="false")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "scan":
        phase_scan(args.output_dir)
    elif args.phase == "upgrade":
        if not args.scan:
            parser.error("--scan is required for upgrade phase")
        phase_upgrade(args.scan, args.output_dir)
    elif args.phase == "report":
        if not args.scan:
            parser.error("--scan is required for report phase")
        phase_report(args.scan, args.tests_passed, args.output_dir)


if __name__ == "__main__":
    main()
