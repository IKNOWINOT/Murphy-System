#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Triage Agent Script
# Label: TRIAGE-AGENT-001
#
# Scans open issues/PRs, applies labels based on content analysis,
# adds staleness warnings, and auto-closes stale issues.
#
# Phases:
#   (single-phase) — Runs full triage cycle

"""
Triage Agent — automated issue/PR lifecycle management.

Usage:
    python triage_agent.py --output-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("triage-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "TRIAGE-AGENT-001"

# Label classification rules: (pattern, label)
LABEL_RULES: list[tuple[str, str]] = [
    (r"\b(bug|crash|error|exception|traceback|broken)\b", "bug"),
    (r"\b(feature|enhancement|request|add support)\b", "feature"),
    (r"\b(connector|integration|adapter|webhook)\b", "connector"),
    (r"\b(doc|documentation|readme|typo|spelling)\b", "docs"),
    (r"\b(security|vulnerability|CVE|exploit|injection|XSS|SSRF)\b", "security"),
    (r"\b(performance|slow|latency|memory leak|timeout)\b", "performance"),
    (r"\b(test|testing|coverage|pytest)\b", "testing"),
    (r"\b(deploy|deployment|CI|CD|workflow|action)\b", "infrastructure"),
]

# Priority keywords: (pattern, priority_label)
PRIORITY_RULES: list[tuple[str, str]] = [
    (r"\b(security|vulnerability|CVE|data loss|crash|production down)\b", "P0-critical"),
    (r"\b(broken|regression|blocking|urgent)\b", "P1-high"),
    (r"\b(bug|error|incorrect|wrong)\b", "P2-medium"),
]


# ── Main Triage ──────────────────────────────────────────────────────────────
def run_triage(output_dir: Path) -> dict[str, Any]:
    """Execute the full triage cycle."""
    log.info("Running triage cycle")
    now = datetime.now(timezone.utc)
    stale_warning_days = int(os.environ.get("STALE_WARNING_DAYS", "14"))
    stale_close_days = int(os.environ.get("STALE_CLOSE_DAYS", "30"))

    # In CI, this would use the GitHub API via GH_TOKEN
    # For now, generate a report of what actions would be taken
    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": now.isoformat(),
        "config": {
            "stale_warning_days": stale_warning_days,
            "stale_close_days": stale_close_days,
        },
        "issues_scanned": 0,
        "prs_scanned": 0,
        "labels_applied": 0,
        "stale_warnings": 0,
        "auto_closed": 0,
        "priority_labels": 0,
        "actions": [],
    }

    # Demonstrate classification logic on sample data
    sample_issues = [
        {"number": 1, "title": "Slack connector broken after API update", "body": "The Slack integration throws an error", "updated_at": (now - timedelta(days=20)).isoformat()},
        {"number": 2, "title": "Add support for Google Calendar connector", "body": "Feature request for calendar integration", "updated_at": now.isoformat()},
        {"number": 3, "title": "Security vulnerability in auth module", "body": "Potential XSS in login page", "updated_at": (now - timedelta(days=35)).isoformat()},
    ]

    for issue in sample_issues:
        actions = _classify_issue(issue, now, stale_warning_days, stale_close_days)
        report["actions"].extend(actions)
        report["issues_scanned"] += 1
        for action in actions:
            if action["type"] == "label":
                report["labels_applied"] += 1
            elif action["type"] == "priority":
                report["priority_labels"] += 1
            elif action["type"] == "stale_warning":
                report["stale_warnings"] += 1
            elif action["type"] == "auto_close":
                report["auto_closed"] += 1

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "triage_report.json").write_text(json.dumps(report, indent=2))
    log.info("Triage complete: %d issues scanned", report["issues_scanned"])
    return report


def _classify_issue(
    issue: dict[str, Any],
    now: datetime,
    warning_days: int,
    close_days: int,
) -> list[dict[str, Any]]:
    """Classify a single issue and return actions to take."""
    actions: list[dict[str, Any]] = []
    text = f"{issue.get('title', '')} {issue.get('body', '')}".lower()

    # Apply category labels
    for pattern, label in LABEL_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            actions.append({
                "type": "label",
                "issue": issue["number"],
                "label": label,
            })

    # Apply priority labels
    for pattern, priority in PRIORITY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            actions.append({
                "type": "priority",
                "issue": issue["number"],
                "label": priority,
            })
            break  # Only apply highest priority

    # Check staleness
    updated = datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00"))
    age_days = (now - updated).days

    if age_days >= close_days:
        actions.append({
            "type": "auto_close",
            "issue": issue["number"],
            "message": (
                f"This issue has been inactive for {age_days} days. "
                "Closing automatically. Please reopen if still relevant."
            ),
        })
    elif age_days >= warning_days:
        actions.append({
            "type": "stale_warning",
            "issue": issue["number"],
            "message": (
                f"This issue has been inactive for {age_days} days. "
                f"It will be auto-closed after {close_days} days of inactivity."
            ),
        })

    return actions


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Triage Agent")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run_triage(args.output_dir)


if __name__ == "__main__":
    main()
