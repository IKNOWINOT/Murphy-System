#!/usr/bin/env python3
"""
check_adr_0008_eligibility.py — Item 13 calendar-gate watchman.

ADR-0008 commits to deleting `src/graphql_api_layer.py` on the *earlier* of:
    1. The next major version bump, OR
    2. 90 days from the ADR's date (2026-04-22).

This script answers exactly one question: "Is the deletion eligible today?"
It is intentionally machine-readable so a CI job can fail loud once the
window opens and the deletion still has not happened.

Behaviour
---------
* Exit 0  →  deletion NOT yet eligible. Prints "STILL DEPRECATED (N days remaining)".
* Exit 1  →  deletion IS eligible. Prints the one-line PR plan and a copy-pasteable
            `git rm` command.

Usage
-----
    python scripts/check_adr_0008_eligibility.py
    python scripts/check_adr_0008_eligibility.py --json

The "next major version" branch of ADR-0008 is owner-driven and not
automatable from this script. When a major-version bump lands earlier than
the calendar gate, the deletion PR cites the version bump as its
justification rather than this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ADR-0008 §Decision step 2 fixes both endpoints of the calendar gate.
ADR_0008_DATE = dt.date(2026, 4, 22)
GATE_DAYS = 90
ELIGIBLE_AFTER = ADR_0008_DATE + dt.timedelta(days=GATE_DAYS)

QUARANTINED_FILE = REPO_ROOT / "src" / "graphql_api_layer.py"
QUARANTINED_TESTS = REPO_ROOT / "tests" / "integration_connector" / "test_graphql_api_layer.py"
QUARANTINED_CONTRACT = REPO_ROOT / "tests" / "contracts" / "test_graphql_layer_quarantine.py"


def _today() -> dt.date:
    """Indirection so tests can monkey-patch."""
    return dt.date.today()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON status")
    args = parser.parse_args(argv)

    today = _today()
    days_remaining = (ELIGIBLE_AFTER - today).days
    eligible = days_remaining <= 0

    payload = {
        "adr": "0008",
        "adr_date": ADR_0008_DATE.isoformat(),
        "eligible_after": ELIGIBLE_AFTER.isoformat(),
        "today": today.isoformat(),
        "days_remaining": days_remaining,
        "eligible": eligible,
        "files_to_delete": [
            str(QUARANTINED_FILE.relative_to(REPO_ROOT)),
            str(QUARANTINED_TESTS.relative_to(REPO_ROOT)),
            str(QUARANTINED_CONTRACT.relative_to(REPO_ROOT)),
        ],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if eligible else 0

    if not eligible:
        print(
            f"STILL DEPRECATED ({days_remaining} day(s) remaining until "
            f"{ELIGIBLE_AFTER.isoformat()}). ADR-0008 calendar gate not yet open."
        )
        print("If a major version bump lands earlier, cite that in the deletion PR.")
        return 0

    print(f"ELIGIBLE FOR DELETION as of {ELIGIBLE_AFTER.isoformat()} "
          f"({-days_remaining} day(s) overdue).")
    print()
    print("Open the deletion PR titled:")
    print('  "Item 13 (final): Delete src/graphql_api_layer.py per ADR-0008"')
    print()
    print("Copy-pasteable diff:")
    for f in payload["files_to_delete"]:
        print(f"  git rm {f}")
    print()
    print("Then update docs/ROADMAP_TO_CLASS_S.md row 13 from 🟡 to ✅ and link the PR.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
