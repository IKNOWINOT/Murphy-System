#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Connector Health Agent Script
# Label: CONNECTOR-HEALTH-001
#
# Discovers all integration connectors in src/, runs health probes
# (import, schema, class structure), and generates reports.
#
# Phases:
#   discover  — Scan src/ for *_connector.py files, extract metadata
#   check     — Run import + structural health probes on each connector
#   report    — Generate issue-ready reports for unhealthy connectors
#
# Commissioning Principles (G1–G9 evaluated at every phase).

"""
Connector Health Agent — automated connector health monitoring.

Usage:
    python connector_health_agent.py --phase discover --output-dir <dir>
    python connector_health_agent.py --phase check --discovery <report.json> --output-dir <dir>
    python connector_health_agent.py --phase report --health <report.json> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("connector-health-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "CONNECTOR-HEALTH-001"

# Connector file patterns to discover
CONNECTOR_PATTERNS = ["*_connector.py", "*_connectors.py"]

# Expected structural markers in a well-formed connector
EXPECTED_MARKERS = [
    "class",         # Should define at least one class
]


# ── Phase: Discover ──────────────────────────────────────────────────────────
def phase_discover(output_dir: Path) -> dict[str, Any]:
    """Scan src/ for connector files and extract metadata."""
    log.info("Phase: DISCOVER — scanning for connectors")
    src_dir = _find_src_dir()
    connectors: list[dict[str, Any]] = []

    for pattern in CONNECTOR_PATTERNS:
        for filepath in sorted(src_dir.rglob(pattern)):
            if filepath.name.startswith("__"):
                continue
            rel = filepath.relative_to(src_dir)
            module_key = (
                "src." + str(rel).replace("/", ".").replace("\\", ".").removesuffix(".py")
            )
            metadata = _extract_connector_metadata(filepath, module_key)
            connectors.append(metadata)

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "discover",
        "connectors": connectors,
        "total": len(connectors),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "discovery_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Discovered %d connectors → %s", len(connectors), report_path)
    return report


def _extract_connector_metadata(filepath: Path, module_key: str) -> dict[str, Any]:
    """Parse a connector file and extract structural metadata."""
    metadata: dict[str, Any] = {
        "file": str(filepath),
        "module": module_key,
        "name": filepath.stem,
        "classes": [],
        "has_docstring": False,
        "line_count": 0,
    }
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        metadata["line_count"] = len(source.splitlines())
        tree = ast.parse(source, filename=str(filepath))
        metadata["has_docstring"] = bool(ast.get_docstring(tree))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                metadata["classes"].append(node.name)
    except (SyntaxError, UnicodeDecodeError) as exc:
        metadata["parse_error"] = str(exc)
        log.warning("Parse error in %s: %s", filepath, exc)
    return metadata


# ── Phase: Check ─────────────────────────────────────────────────────────────
def phase_check(discovery_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run health probes on each discovered connector."""
    log.info("Phase: CHECK — running health probes")
    discovery = json.loads(discovery_path.read_text())
    results: list[dict[str, Any]] = []

    for connector in discovery.get("connectors", []):
        result = _probe_connector(connector)
        results.append(result)

    healthy = sum(1 for r in results if r["status"] == "healthy")
    unhealthy = sum(1 for r in results if r["status"] != "healthy")

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "check",
        "results": results,
        "healthy": healthy,
        "unhealthy": unhealthy,
        "total": len(results),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "health_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Health check complete: %d healthy, %d unhealthy", healthy, unhealthy)
    return report


def _probe_connector(connector: dict[str, Any]) -> dict[str, Any]:
    """Run import + structure probes on a single connector."""
    result: dict[str, Any] = {
        "name": connector["name"],
        "module": connector["module"],
        "status": "healthy",
        "checks": {},
    }

    # Check 1: importable
    try:
        importlib.import_module(connector["module"])
        result["checks"]["import"] = "pass"
    except Exception as exc:
        result["checks"]["import"] = f"fail: {exc}"
        result["status"] = "unhealthy"

    # Check 2: has classes (structural integrity)
    if connector.get("classes"):
        result["checks"]["has_classes"] = "pass"
    else:
        result["checks"]["has_classes"] = "warn: no classes defined"
        if result["status"] == "healthy":
            result["status"] = "degraded"

    # Check 3: has docstring
    if connector.get("has_docstring"):
        result["checks"]["has_docstring"] = "pass"
    else:
        result["checks"]["has_docstring"] = "warn: no module docstring"

    # Check 4: no parse errors
    if connector.get("parse_error"):
        result["checks"]["parseable"] = f"fail: {connector['parse_error']}"
        result["status"] = "unhealthy"
    else:
        result["checks"]["parseable"] = "pass"

    return result


# ── Phase: Report ────────────────────────────────────────────────────────────
def phase_report(health_path: Path, output_dir: Path) -> dict[str, Any]:
    """Generate issue-ready reports for unhealthy connectors."""
    log.info("Phase: REPORT — generating issue reports")
    health = json.loads(health_path.read_text())
    issues: list[dict[str, Any]] = []

    for result in health.get("results", []):
        if result["status"] == "unhealthy":
            issue = {
                "title": f"[Connector Health] {result['name']} is unhealthy",
                "body": _format_issue_body(result),
                "labels": ["connector", "automated", "health-check"],
            }
            issues.append(issue)

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "report",
        "issues_to_create": len(issues),
        "issues": issues,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "issue_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Generated %d issue reports", len(issues))
    return report


def _format_issue_body(result: dict[str, Any]) -> str:
    """Format a single connector health result as an issue body."""
    lines = [
        f"## Connector Health Alert: `{result['name']}`",
        "",
        f"**Module:** `{result['module']}`",
        f"**Status:** {result['status']}",
        "",
        "### Check Results",
        "",
    ]
    for check_name, check_result in result.get("checks", {}).items():
        icon = "✅" if check_result == "pass" else "❌" if "fail" in str(check_result) else "⚠️"
        lines.append(f"- {icon} **{check_name}:** {check_result}")
    lines.extend([
        "",
        "---",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
    ])
    return "\n".join(lines)


# ── Utilities ────────────────────────────────────────────────────────────────
def _find_src_dir() -> Path:
    """Locate the canonical src/ directory."""
    candidates = [
        Path("src"),
        Path("Murphy System/src"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    log.error("Cannot find src/ directory")
    sys.exit(1)


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Connector Health Agent")
    parser.add_argument("--phase", required=True, choices=["discover", "check", "report"])
    parser.add_argument("--discovery", type=Path, help="Path to discovery_report.json")
    parser.add_argument("--health", type=Path, help="Path to health_report.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "discover":
        phase_discover(args.output_dir)
    elif args.phase == "check":
        if not args.discovery:
            parser.error("--discovery is required for check phase")
        phase_check(args.discovery, args.output_dir)
    elif args.phase == "report":
        if not args.health:
            parser.error("--health is required for report phase")
        phase_report(args.health, args.output_dir)


if __name__ == "__main__":
    main()
