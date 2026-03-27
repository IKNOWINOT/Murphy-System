#!/usr/bin/env python3
"""
sync_module_counts.py — Documentation Module Count Auto-Sync

Counts Python modules in src/ and updates the documented count in:
  - README.md
  - STATUS.md
  - CONTRIBUTING.md

Run manually or as a CI step:
    python scripts/sync_module_counts.py [--dry-run] [--root <project_root>]

Exit codes:
    0 — Success (all files updated or already current)
    1 — Error (file not found, etc.)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Regex patterns to match common module-count phrases in docs.
# Each pattern captures a group(1) that is the numeric count to be replaced.
_COUNT_PATTERNS: list[re.Pattern] = [
    # "620+ modules" / "978 source modules" / "978 modules"
    re.compile(r"(\d+)\+?\s*(?:source\s+)?modules?", re.IGNORECASE),
    # "978 production modules"
    re.compile(r"(\d+)\s+production\s+modules?", re.IGNORECASE),
]

# Replacement template: produces "<count>+ modules"
_REPLACEMENT_TEMPLATE = "{count}+ modules"


def count_modules(src_root: Path) -> int:
    """Count non-init Python module files under *src_root*."""
    return sum(
        1 for p in src_root.rglob("*.py")
        if p.name != "__init__.py"
    )


def update_file(
    file_path: Path,
    new_count: int,
    dry_run: bool = False,
) -> tuple[bool, int]:
    """Update module-count mentions in *file_path*.

    Returns (changed: bool, occurrences_updated: int).
    """
    if not file_path.exists():
        print(f"  SKIP  {file_path} — file not found")
        return False, 0

    content = file_path.read_text(encoding="utf-8")
    original = content
    total_updated = 0

    for pattern in _COUNT_PATTERNS:
        def _replace(m: re.Match) -> str:
            old_count = int(m.group(1))
            if old_count == new_count:
                return m.group(0)  # already current
            replacement = m.group(0).replace(
                m.group(1), str(new_count), 1
            )
            return replacement

        content, n = pattern.subn(_replace, content)
        total_updated += n

    changed = content != original
    if changed and not dry_run:
        file_path.write_text(content, encoding="utf-8")

    return changed, total_updated


def sync(
    project_root: Path,
    dry_run: bool = False,
) -> dict:
    """Run the full sync and return a summary dict."""
    src_root = project_root / "src"
    if not src_root.exists():
        print(f"ERROR: src/ not found at {src_root}", file=sys.stderr)
        sys.exit(1)

    actual_count = count_modules(src_root)
    print(f"Actual module count: {actual_count} (in {src_root})")

    targets = [
        project_root / "README.md",
        project_root / "STATUS.md",
        project_root / "CONTRIBUTING.md",
    ]

    summary = {
        "actual_count": actual_count,
        "files_checked": len(targets),
        "files_updated": 0,
        "occurrences_updated": 0,
        "dry_run": dry_run,
    }

    for target in targets:
        changed, n = update_file(target, actual_count, dry_run=dry_run)
        status = "DRY-RUN-UPDATED" if (changed and dry_run) else (
            "UPDATED" if changed else "OK (no change)"
        )
        print(f"  {status:20s} {target.name} ({n} occurrence(s))")
        if changed:
            summary["files_updated"] += 1
            summary["occurrences_updated"] += n

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-sync module counts in README.md, STATUS.md, CONTRIBUTING.md"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing files",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root directory (default: auto-detect from script location)",
    )
    args = parser.parse_args()

    if args.root is not None:
        project_root = args.root.resolve()
    else:
        # Auto-detect: this script lives in <project_root>/scripts/
        project_root = Path(__file__).resolve().parent.parent

    print(f"Project root: {project_root}")
    summary = sync(project_root, dry_run=args.dry_run)

    if summary["files_updated"]:
        verb = "Would update" if args.dry_run else "Updated"
        print(
            f"\n{verb} {summary['files_updated']} file(s), "
            f"{summary['occurrences_updated']} occurrence(s) → "
            f"{summary['actual_count']}+ modules"
        )
    else:
        print(f"\nAll docs already reflect {summary['actual_count']}+ modules — no changes needed")


if __name__ == "__main__":
    main()
