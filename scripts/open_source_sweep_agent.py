#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Open Source Sweep Agent Script
# Label: OSS-SWEEP-001
#
# Monthly sweep of the entire Murphy System codebase to enforce the
# dual-license boundary defined in strategic/open_source/.  Classifies
# every module as "community" (Apache-2.0) or "proprietary" (BSL-1.1 /
# commercial), audits copyright headers and license references, detects
# accidental IP leakage across the boundary, and generates a compliance
# report with actionable issues.
#
# Phases:
#   classify  — Walk src/ and classify each module into community / proprietary
#   audit     — Check copyright headers, license refs, and boundary leaks
#   report    — Produce a dated JSON + Markdown compliance report
#
# Commissioning Principles (evaluated at every phase):
#   G1: Does the module do what it was designed to do?
#   G2: What exactly is the module supposed to do?
#   G3: What conditions are possible based on the module?
#   G4: Does the test profile reflect the full range of capabilities?
#   G5: What is the expected result at all points of operation?
#   G6: What is the actual result?
#   G7: If problems persist, restart from symptoms → validation.
#   G8: Has all ancillary code and documentation been updated?
#   G9: Has hardening been applied and the module recommissioned?

"""
Open Source Sweep Agent — monthly dual-license compliance audit.

Scans every module in Murphy System/src/ to enforce the dual-license
boundary (Apache-2.0 community vs. BSL-1.1/commercial proprietary)
defined in strategic/open_source/OPEN_SOURCE_STRATEGY.md.

Usage:
    python open_source_sweep_agent.py --phase classify --output-dir <dir>
    python open_source_sweep_agent.py --phase audit --classification <report.json> --output-dir <dir>
    python open_source_sweep_agent.py --phase report --audit <report.json> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("oss-sweep-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "OSS-SWEEP-001"

# Repo structure
REPO_ROOT = Path(os.environ.get("MURPHY_REPO_ROOT", Path.cwd()))
MURPHY_SYSTEM = REPO_ROOT / "Murphy System"
MURPHY_SRC = MURPHY_SYSTEM / "src"

# ── Module classification ─────────────────────────────────────────────────────
# Modules explicitly designated as community / Apache-2.0 per the strategy doc.
COMMUNITY_MODULES: list[str] = [
    "murphy_confidence",
    "langchain_safety",
    "confidence_types",
    "confidence_engine",
    "confidence_gates",
    "confidence_compiler",
    "eu_ai_act",
]

# Modules explicitly designated as proprietary / commercial per the strategy doc.
PROPRIETARY_MODULES: list[str] = [
    "runtime",
    "hitl",
    "siem_audit",
    "crypto_integrity",
    "compliance_reports",
    "multi_tenant",
    "deployment_readiness",
    "security_hardening_config",
    "auth_middleware",
    "billing",
    "gate_bypass_controller",
    "aionmind",
]

# Valid copyright holders
VALID_COPYRIGHT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Copyright\s*[©(c)]\s*\d{4}.*Inoni", re.IGNORECASE),
    re.compile(r"Copyright\s*\(C\)\s*\d{4}.*Inoni", re.IGNORECASE),
]

# Valid license identifiers
COMMUNITY_LICENSE_MARKERS: list[str] = [
    "Apache-2.0",
    "Apache License",
    "apache 2.0",
]
PROPRIETARY_LICENSE_MARKERS: list[str] = [
    "BSL-1.1",
    "Boost Software License",
    "Commercial License",
    "Proprietary",
]

# Sensitive patterns that must not appear in community modules
PROPRIETARY_LEAK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"MURPHY_SECRET_KEY", re.IGNORECASE),
    re.compile(r"SIEM|siem_audit", re.IGNORECASE),
    re.compile(r"crypto_integrity", re.IGNORECASE),
    re.compile(r"hitl.*gate|HITL.*Gate", re.IGNORECASE),
    re.compile(r"multi.?tenant", re.IGNORECASE),
    re.compile(r"billing.*engine|BillingEngine", re.IGNORECASE),
]


# ── Phase: Classify ──────────────────────────────────────────────────────────


def _read_file_head(path: Path, max_lines: int = 30) -> str:
    """Read the first *max_lines* lines of a file, returning empty on error."""
    try:
        lines: list[str] = []
        with open(path, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= max_lines:
                    break
                lines.append(line)
        return "".join(lines)
    except OSError:
        return ""


def _classify_single(name: str) -> str:
    """
    Return 'community', 'proprietary', or 'unclassified' for a module name.

    G2: A module is community if it appears in COMMUNITY_MODULES.  It is
    proprietary if it appears in PROPRIETARY_MODULES.  Otherwise it defaults
    to 'unclassified' (assumed proprietary until explicitly opted-in).
    """
    lower = name.lower()
    for cm in COMMUNITY_MODULES:
        if lower == cm or lower.startswith(cm):
            return "community"
    for pm in PROPRIETARY_MODULES:
        if lower == pm or lower.startswith(pm):
            return "proprietary"
    return "unclassified"


def phase_classify(output_dir: Path) -> dict[str, Any]:
    """
    G1/G2: Walk src/ and classify each module as community or proprietary.

    Returns a classification report dict and writes it to *output_dir*.
    """
    log.info("Phase: CLASSIFY — walking %s", MURPHY_SRC)

    modules: list[dict[str, Any]] = []
    if not MURPHY_SRC.exists():
        log.warning("Source directory %s does not exist", MURPHY_SRC)
    else:
        for item in sorted(MURPHY_SRC.iterdir()):
            if item.name.startswith(("__", ".")):
                continue
            if item.is_dir() and (item / "__init__.py").exists():
                modules.append({
                    "name": item.name,
                    "type": "package",
                    "classification": _classify_single(item.name),
                    "path": str(item),
                })
            elif item.is_file() and item.suffix == ".py":
                modules.append({
                    "name": item.stem,
                    "type": "module",
                    "classification": _classify_single(item.stem),
                    "path": str(item),
                })

    community = [m for m in modules if m["classification"] == "community"]
    proprietary = [m for m in modules if m["classification"] == "proprietary"]
    unclassified = [m for m in modules if m["classification"] == "unclassified"]

    report: dict[str, Any] = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "classify",
        "total_modules": len(modules),
        "community_count": len(community),
        "proprietary_count": len(proprietary),
        "unclassified_count": len(unclassified),
        "modules": modules,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "classification_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    log.info("Classification report → %s  (community=%d  proprietary=%d  unclassified=%d)",
             report_path, len(community), len(proprietary), len(unclassified))
    return report


# ── Phase: Audit ─────────────────────────────────────────────────────────────


def _has_copyright_header(head: str) -> bool:
    """Check if the file head contains a valid Inoni copyright line."""
    for pat in VALID_COPYRIGHT_PATTERNS:
        if pat.search(head):
            return True
    return False


def _detect_license_marker(head: str) -> str | None:
    """Return the first license identifier found in the file head, or None."""
    for marker in COMMUNITY_LICENSE_MARKERS:
        if marker.lower() in head.lower():
            return marker
    for marker in PROPRIETARY_LICENSE_MARKERS:
        if marker.lower() in head.lower():
            return marker
    return None


def _detect_leaks(path: Path, classification: str) -> list[dict[str, Any]]:
    """
    G3: If *classification* is 'community', scan the file for proprietary
    patterns that must not appear.

    Returns a list of leak findings (empty if clean or not community).
    """
    if classification != "community":
        return []

    leaks: list[dict[str, Any]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return leaks

    for pat in PROPRIETARY_LEAK_PATTERNS:
        for match in pat.finditer(content):
            leaks.append({
                "pattern": pat.pattern,
                "match": match.group(),
                "file": str(path),
            })
    return leaks


def _audit_module(module: dict[str, Any]) -> dict[str, Any]:
    """
    Audit a single module for copyright header, license marker, and leaks.

    G5: Expected — every module should have a copyright header and a license
    marker consistent with its classification.
    """
    path = Path(module["path"])
    classification = module["classification"]

    # For packages, audit __init__.py
    if module["type"] == "package":
        init_path = path / "__init__.py"
        head = _read_file_head(init_path)
        audit_path = init_path
    else:
        head = _read_file_head(path)
        audit_path = path

    has_copyright = _has_copyright_header(head)
    license_marker = _detect_license_marker(head)

    # Determine expected license family
    if classification == "community":
        expected_family = "Apache"
    elif classification == "proprietary":
        expected_family = "BSL"
    else:
        expected_family = None  # unclassified — any header is acceptable

    license_mismatch = False
    if expected_family and license_marker:
        if expected_family == "Apache" and not any(
            m.lower() in license_marker.lower() for m in COMMUNITY_LICENSE_MARKERS
        ):
            license_mismatch = True
        elif expected_family == "BSL" and not any(
            m.lower() in license_marker.lower() for m in PROPRIETARY_LICENSE_MARKERS
        ):
            license_mismatch = True

    leaks = _detect_leaks(audit_path, classification)

    return {
        "name": module["name"],
        "classification": classification,
        "has_copyright": has_copyright,
        "license_marker": license_marker,
        "license_mismatch": license_mismatch,
        "leak_count": len(leaks),
        "leaks": leaks,
        "path": str(audit_path),
    }


def phase_audit(
    classification_report: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """
    G1/G5/G6: Audit every classified module for compliance issues.

    Returns an audit report dict and writes it to *output_dir*.
    """
    log.info("Phase: AUDIT — checking headers, licenses, and boundary leaks")
    modules = classification_report.get("modules", [])
    results: list[dict[str, Any]] = []

    for mod in modules:
        results.append(_audit_module(mod))

    missing_copyright = [r for r in results if not r["has_copyright"]]
    no_license = [r for r in results if r["license_marker"] is None]
    mismatched = [r for r in results if r["license_mismatch"]]
    with_leaks = [r for r in results if r["leak_count"] > 0]
    total_leaks = sum(r["leak_count"] for r in results)

    report: dict[str, Any] = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "audit",
        "total_audited": len(results),
        "missing_copyright_count": len(missing_copyright),
        "no_license_count": len(no_license),
        "license_mismatch_count": len(mismatched),
        "leak_count": total_leaks,
        "modules_with_leaks": len(with_leaks),
        "results": results,
        "missing_copyright": [r["name"] for r in missing_copyright],
        "no_license": [r["name"] for r in no_license],
        "license_mismatches": [r["name"] for r in mismatched],
        "boundary_leaks": [
            {"module": r["name"], "leaks": r["leaks"]} for r in with_leaks
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "audit_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    log.info("Audit report → %s  (missing_cr=%d  no_lic=%d  mismatch=%d  leaks=%d)",
             report_path,
             len(missing_copyright), len(no_license), len(mismatched), total_leaks)
    return report


# ── Phase: Report ────────────────────────────────────────────────────────────


def _severity(issue_type: str) -> str:
    """Map issue type to severity label."""
    return {
        "boundary_leak": "CRITICAL",
        "license_mismatch": "HIGH",
        "missing_copyright": "MEDIUM",
        "no_license": "LOW",
    }.get(issue_type, "INFO")


def _build_issues(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """
    G7: Build an actionable issue list from the audit report.
    """
    issues: list[dict[str, Any]] = []

    # Boundary leaks (most severe)
    for entry in audit.get("boundary_leaks", []):
        for leak in entry.get("leaks", []):
            issues.append({
                "id": f"LEAK-{entry['module']}",
                "severity": _severity("boundary_leak"),
                "type": "boundary_leak",
                "module": entry["module"],
                "detail": f"Proprietary pattern '{leak.get('match', '')}' found in community module",
                "file": leak.get("file", ""),
                "commissioning": "G3: Community modules must not reference proprietary internals",
            })

    # License mismatches
    for name in audit.get("license_mismatches", []):
        issues.append({
            "id": f"LIC-MISMATCH-{name}",
            "severity": _severity("license_mismatch"),
            "type": "license_mismatch",
            "module": name,
            "detail": "License marker does not match module classification",
            "commissioning": "G8: License headers must match the dual-license strategy",
        })

    # Missing copyright
    for name in audit.get("missing_copyright", []):
        issues.append({
            "id": f"CR-MISSING-{name}",
            "severity": _severity("missing_copyright"),
            "type": "missing_copyright",
            "module": name,
            "detail": "No Inoni copyright header found",
            "commissioning": "G8: Every source file must carry a copyright header",
        })

    # No license marker
    for name in audit.get("no_license", []):
        issues.append({
            "id": f"LIC-ABSENT-{name}",
            "severity": _severity("no_license"),
            "type": "no_license",
            "module": name,
            "detail": "No license identifier in file header",
            "commissioning": "G8: Every source file should reference its license",
        })

    return issues


def _render_markdown(
    classification: dict[str, Any],
    audit: dict[str, Any],
    issues: list[dict[str, Any]],
) -> str:
    """Render the sweep report as Markdown."""
    ts = datetime.now(timezone.utc).isoformat()
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    critical = [i for i in issues if i["severity"] == "CRITICAL"]
    high = [i for i in issues if i["severity"] == "HIGH"]
    medium = [i for i in issues if i["severity"] == "MEDIUM"]
    low = [i for i in issues if i["severity"] == "LOW"]

    lines: list[str] = [
        "# Murphy System — Open Source Sweep Report",
        "",
        f"**Date:** {date_str}",
        f"**Agent:** {AGENT_LABEL} v{AGENT_VERSION}",
        f"**Generated:** {ts}",
        "",
        "---",
        "",
        "## Classification Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Modules | {classification.get('total_modules', 0)} |",
        f"| Community (Apache-2.0) | {classification.get('community_count', 0)} |",
        f"| Proprietary (BSL-1.1) | {classification.get('proprietary_count', 0)} |",
        f"| Unclassified | {classification.get('unclassified_count', 0)} |",
        "",
        "---",
        "",
        "## Audit Summary",
        "",
        "| Check | Count |",
        "|-------|-------|",
        f"| Missing Copyright | {audit.get('missing_copyright_count', 0)} |",
        f"| No License Marker | {audit.get('no_license_count', 0)} |",
        f"| License Mismatch | {audit.get('license_mismatch_count', 0)} |",
        f"| Boundary Leaks | {audit.get('leak_count', 0)} |",
        "",
        "---",
        "",
        "## Commissioning Assessment (G1–G9)",
        "",
    ]

    g_checks = {
        "G1": audit.get("leak_count", 1) == 0,
        "G2": classification.get("unclassified_count", 1) == 0,
        "G3": audit.get("leak_count", 1) == 0,
        "G8": audit.get("missing_copyright_count", 1) == 0
            and audit.get("no_license_count", 1) == 0,
        "G9": audit.get("license_mismatch_count", 1) == 0,
    }
    g_labels = {
        "G1": "Modules respect dual-license boundary",
        "G2": "All modules are classified",
        "G3": "No proprietary leaks in community code",
        "G8": "Copyright and license headers present",
        "G9": "License markers match classification",
    }
    for key in ("G1", "G2", "G3", "G8", "G9"):
        ok = g_checks[key]
        status = "✅" if ok else "❌"
        chk = "x" if ok else " "
        lines.append(f"- [{chk}] {g_labels[key]} {status}")

    lines.extend(["", "---", ""])

    if critical:
        lines.append("## 🔴 Critical Issues (Boundary Leaks)")
        lines.append("")
        for issue in critical:
            lines.append(f"- **{issue['id']}** — {issue['detail']}  ")
            lines.append(f"  File: `{issue.get('file', 'N/A')}`  ")
            lines.append(f"  Commissioning: {issue['commissioning']}")
            lines.append("")

    if high:
        lines.append("## 🟠 High Issues (License Mismatches)")
        lines.append("")
        for issue in high:
            lines.append(f"- **{issue['id']}** — {issue['detail']}")
            lines.append("")

    if medium:
        lines.append("## 🟡 Medium Issues (Missing Copyright)")
        lines.append("")
        for issue in medium:
            lines.append(f"- **{issue['id']}** — {issue['detail']}")
            lines.append("")

    if low:
        lines.append("## 🔵 Low Issues (No License Marker)")
        lines.append("")
        for issue in low:
            lines.append(f"- **{issue['id']}** — {issue['detail']}")
            lines.append("")

    if not issues:
        lines.append("## ✅ All Clear")
        lines.append("")
        lines.append("No compliance issues detected — dual-license boundary is intact.")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
        "",
    ])

    return "\n".join(lines)


def phase_report(
    classification: dict[str, Any],
    audit: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """
    G7/G8: Produce the final dated JSON + Markdown compliance report.
    """
    log.info("Phase: REPORT — generating compliance report")
    issues = _build_issues(audit)
    timestamp = datetime.now(timezone.utc)
    date_str = timestamp.strftime("%Y-%m-%d")

    critical = [i for i in issues if i["severity"] == "CRITICAL"]
    high = [i for i in issues if i["severity"] == "HIGH"]
    medium = [i for i in issues if i["severity"] == "MEDIUM"]
    low = [i for i in issues if i["severity"] == "LOW"]

    report: dict[str, Any] = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": timestamp.isoformat(),
        "date": date_str,
        "phase": "report",
        "classification_summary": {
            "total": classification.get("total_modules", 0),
            "community": classification.get("community_count", 0),
            "proprietary": classification.get("proprietary_count", 0),
            "unclassified": classification.get("unclassified_count", 0),
        },
        "audit_summary": {
            "missing_copyright": audit.get("missing_copyright_count", 0),
            "no_license": audit.get("no_license_count", 0),
            "license_mismatch": audit.get("license_mismatch_count", 0),
            "boundary_leaks": audit.get("leak_count", 0),
        },
        "issue_count": len(issues),
        "critical_count": len(critical),
        "high_count": len(high),
        "medium_count": len(medium),
        "low_count": len(low),
        "issues": issues,
        "commissioning_assessment": {
            "G1_boundary_intact": audit.get("leak_count", 1) == 0,
            "G2_all_classified": classification.get("unclassified_count", 1) == 0,
            "G3_no_leaks": audit.get("leak_count", 1) == 0,
            "G8_headers_present": (
                audit.get("missing_copyright_count", 1) == 0
                and audit.get("no_license_count", 1) == 0
            ),
            "G9_licenses_match": audit.get("license_mismatch_count", 1) == 0,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON report (dated + latest)
    json_path = output_dir / f"sweep_report_{date_str}.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    latest_path = output_dir / "sweep_report_latest.json"
    latest_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Markdown report
    md_path = output_dir / f"sweep_report_{date_str}.md"
    md_content = _render_markdown(classification, audit, issues)
    md_path.write_text(md_content, encoding="utf-8")

    log.info("Report → %s  (issues=%d  critical=%d  high=%d  medium=%d  low=%d)",
             json_path, len(issues), len(critical), len(high), len(medium), len(low))
    return report


# ── Full Sweep Orchestrator ──────────────────────────────────────────────────


def run_sweep(output_dir: str) -> dict[str, Any]:
    """
    Execute all three phases sequentially and return the final report.

    G2: This function is the single entry-point for CI and manual invocation
    when no per-phase control is needed.
    """
    out = Path(output_dir)
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║   MURPHY OPEN SOURCE SWEEP AGENT — v%s              ║", AGENT_VERSION)
    log.info("╠══════════════════════════════════════════════════════════╣")
    log.info("║  Output Dir: %-40s  ║", str(out)[:40])
    log.info("╚══════════════════════════════════════════════════════════╝")

    classification = phase_classify(out)
    audit = phase_audit(classification, out)
    report = phase_report(classification, audit, out)

    log.info("═══════════════════════════════════════════════════════════")
    log.info("  Sweep complete: %d issues  (critical=%d)",
             report["issue_count"], report["critical_count"])
    log.info("═══════════════════════════════════════════════════════════")
    return report


# ── CLI Entrypoint ────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Murphy Open Source Sweep Agent — monthly dual-license compliance audit",
    )
    parser.add_argument("--output-dir", required=True,
                        help="Directory for output artifacts")
    parser.add_argument("--phase", choices=["classify", "audit", "report", "all"],
                        default="all",
                        help="Phase to run (default: all)")
    parser.add_argument("--classification", default=None,
                        help="Path to classification_report.json (for audit phase)")
    parser.add_argument("--audit", default=None,
                        help="Path to audit_report.json (for report phase)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {AGENT_VERSION}")

    args = parser.parse_args()
    out = Path(args.output_dir)

    if args.phase == "all":
        run_sweep(args.output_dir)
    elif args.phase == "classify":
        phase_classify(out)
    elif args.phase == "audit":
        if not args.classification:
            parser.error("--classification is required for the audit phase")
        cls_data = json.loads(Path(args.classification).read_text(encoding="utf-8"))
        phase_audit(cls_data, out)
    elif args.phase == "report":
        if not args.audit:
            parser.error("--audit is required for the report phase")
        audit_data = json.loads(Path(args.audit).read_text(encoding="utf-8"))
        # We also need classification for the report
        cls_path = out / "classification_report.json"
        if cls_path.exists():
            cls_data = json.loads(cls_path.read_text(encoding="utf-8"))
        else:
            cls_data = {"total_modules": 0, "community_count": 0,
                        "proprietary_count": 0, "unclassified_count": 0}
        phase_report(cls_data, audit_data, out)


if __name__ == "__main__":
    main()
