#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
#
# Murphy System — Release Notes Generator Agent Script
# Label: RELEASE-NOTES-001
#
# Collects commits since last tag, categorizes them, and generates
# structured CHANGELOG entries and GitHub Release notes.
#
# Phases:
#   collect   — Gather commits since previous tag
#   generate  — Categorize and produce release notes
#   release   — Create or update GitHub Release

"""
Release Notes Generator Agent — automated release documentation.

Usage:
    python release_notes_agent.py --phase collect --tag <tag> --output-dir <dir>
    python release_notes_agent.py --phase generate --commits <file> --tag <tag> --output-dir <dir>
    python release_notes_agent.py --phase release --notes <file> --tag <tag> --output-dir <dir>
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
log = logging.getLogger("release-notes-agent")

# ── Constants ─────────────────────────────────────────────────────────────────
AGENT_VERSION = "1.0.0"
AGENT_LABEL = "RELEASE-NOTES-001"

# Conventional commit patterns
CATEGORY_PATTERNS: list[tuple[str, str, str]] = [
    (r"^feat[\(:]", "features", "✨ Features"),
    (r"^fix[\(:]", "fixes", "🐛 Bug Fixes"),
    (r"^security[\(:]|^vuln[\(:]", "security", "🔒 Security"),
    (r"^docs?[\(:]", "docs", "📄 Documentation"),
    (r"^refactor[\(:]", "refactors", "♻️ Refactoring"),
    (r"^perf[\(:]", "performance", "⚡ Performance"),
    (r"^test[\(:]", "tests", "🧪 Tests"),
    (r"^ci[\(:]|^build[\(:]", "infrastructure", "🏗️ Infrastructure"),
    (r"^chore[\(:]", "chores", "🔧 Chores"),
]

# Keyword-based fallback classification
KEYWORD_CATEGORIES: list[tuple[str, str]] = [
    (r"\b(add|new|feature|implement|support)\b", "features"),
    (r"\b(fix|bug|patch|repair|resolve|close)\b", "fixes"),
    (r"\b(security|CVE|vulnerability|auth)\b", "security"),
    (r"\b(doc|readme|comment|typo)\b", "docs"),
    (r"\b(refactor|rename|move|reorganize|clean)\b", "refactors"),
    (r"\b(perf|speed|optimize|fast)\b", "performance"),
    (r"\b(test|spec|coverage)\b", "tests"),
]


# ── Phase: Collect ───────────────────────────────────────────────────────────
def phase_collect(tag: str, output_dir: Path) -> dict[str, Any]:
    """Gather commits since previous tag."""
    log.info("Phase: COLLECT — gathering commits for tag %s", tag)
    prev_tag = _get_previous_tag(tag)
    commits = _get_commits_between(prev_tag, "HEAD")

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "collect",
        "tag": tag,
        "previous_tag": prev_tag,
        "commits": commits,
        "total_commits": len(commits),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "commits.json").write_text(json.dumps(report, indent=2))
    log.info("Collected %d commits (from %s to %s)", len(commits), prev_tag or "beginning", tag)
    return report


def _get_previous_tag(current_tag: str) -> str | None:
    """Find the tag immediately before the current one."""
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
            if current_tag in tags:
                idx = tags.index(current_tag)
                if idx + 1 < len(tags):
                    return tags[idx + 1]
            elif tags:
                return tags[0]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.debug("Failed to get tags: %s", exc)
    return None


def _get_commits_between(from_ref: str | None, to_ref: str) -> list[dict[str, str]]:
    """Get commit list between two refs."""
    if from_ref:
        range_spec = f"{from_ref}..{to_ref}"
    else:
        range_spec = to_ref
    try:
        result = subprocess.run(
            ["git", "log", range_spec, "--pretty=format:%H|||%s|||%an|||%aI",
             "--no-merges"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            commits = []
            for line in result.stdout.strip().splitlines():
                parts = line.split("|||")
                if len(parts) >= 4:
                    commits.append({
                        "sha": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })
            return commits
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.debug("Failed to get commits: %s", exc)
    return []


# ── Phase: Generate ──────────────────────────────────────────────────────────
def phase_generate(
    commits_path: Path,
    tag: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Categorize commits and produce release notes."""
    log.info("Phase: GENERATE — categorizing commits")
    commits_data = json.loads(commits_path.read_text())
    commits = commits_data.get("commits", [])

    categorized: dict[str, list[dict[str, str]]] = {
        "features": [],
        "fixes": [],
        "security": [],
        "docs": [],
        "refactors": [],
        "performance": [],
        "tests": [],
        "infrastructure": [],
        "chores": [],
        "other": [],
    }

    for commit in commits:
        category = _categorize_commit(commit["message"])
        categorized[category].append(commit)

    # Generate markdown
    md_lines = [
        f"# Release {tag}",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
    ]

    for pattern_re, cat_key, cat_title in CATEGORY_PATTERNS:
        items = categorized.get(cat_key, [])
        if items:
            md_lines.append(f"## {cat_title}")
            md_lines.append("")
            for item in items:
                short_sha = item["sha"][:7]
                md_lines.append(f"- {item['message']} (`{short_sha}`)")
            md_lines.append("")

    # Other/uncategorized
    other = categorized.get("other", [])
    if other:
        md_lines.append("## 📦 Other Changes")
        md_lines.append("")
        for item in other:
            short_sha = item["sha"][:7]
            md_lines.append(f"- {item['message']} (`{short_sha}`)")
        md_lines.append("")

    md_lines.extend([
        "---",
        f"*Generated by {AGENT_LABEL} v{AGENT_VERSION}*",
    ])

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "generate",
        "tag": tag,
        "total_commits": len(commits),
        "features": len(categorized["features"]),
        "fixes": len(categorized["fixes"]),
        "security": len(categorized["security"]),
        "docs": len(categorized["docs"]),
        "refactors": len(categorized["refactors"]),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "release_notes.md").write_text("\n".join(md_lines))
    (output_dir / "release_notes.json").write_text(json.dumps(report, indent=2))
    log.info("Generated release notes: %d commits categorized", len(commits))
    return report


def _categorize_commit(message: str) -> str:
    """Categorize a commit message using conventional commit + keyword analysis."""
    msg_lower = message.lower().strip()

    # Try conventional commit patterns first
    for pattern, category, _title in CATEGORY_PATTERNS:
        if re.match(pattern, msg_lower):
            return category

    # Fallback to keyword matching
    for pattern, category in KEYWORD_CATEGORIES:
        if re.search(pattern, msg_lower):
            return category

    return "other"


# ── Phase: Release ───────────────────────────────────────────────────────────
def phase_release(
    notes_path: Path,
    tag: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Create GitHub Release (generates the command; actual creation in CI)."""
    log.info("Phase: RELEASE — preparing GitHub Release for %s", tag)
    notes = notes_path.read_text()

    report = {
        "agent": AGENT_LABEL,
        "version": AGENT_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "release",
        "tag": tag,
        "notes_length": len(notes),
        "status": "ready",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "release_status.json").write_text(json.dumps(report, indent=2))

    # Attempt to create the release via gh CLI
    try:
        result = subprocess.run(
            ["gh", "release", "create", tag,
             "--title", f"Release {tag}",
             "--notes-file", str(notes_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            log.info("GitHub Release created: %s", result.stdout.strip())
            report["status"] = "created"
        else:
            log.warning("gh release create failed: %s", result.stderr.strip())
            report["status"] = "gh_cli_failed"
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        log.warning("gh CLI not available: %s", exc)
        report["status"] = "gh_cli_unavailable"

    (output_dir / "release_status.json").write_text(json.dumps(report, indent=2))
    return report


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Release Notes Generator Agent")
    parser.add_argument("--phase", required=True, choices=["collect", "generate", "release"])
    parser.add_argument("--tag", type=str, help="Release tag")
    parser.add_argument("--commits", type=Path, help="Path to commits.json")
    parser.add_argument("--notes", type=Path, help="Path to release_notes.md")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.phase == "collect":
        if not args.tag:
            parser.error("--tag is required for collect phase")
        phase_collect(args.tag, args.output_dir)
    elif args.phase == "generate":
        if not args.commits or not args.tag:
            parser.error("--commits and --tag are required for generate phase")
        phase_generate(args.commits, args.tag, args.output_dir)
    elif args.phase == "release":
        if not args.notes or not args.tag:
            parser.error("--notes and --tag are required for release phase")
        phase_release(args.notes, args.tag, args.output_dir)


if __name__ == "__main__":
    main()
