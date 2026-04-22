#!/usr/bin/env python3
"""
check_benchmark_soak.py — Item 15 calendar-gate watchman.

The Class S Roadmap, Item 15, requires the benchmark-regression CI job to
soak in *advisory* mode for ≥2 weeks before being promoted to *blocking*.
The 2-week window exists to characterise CI-runner variance so the
promotion does not convert noise into spurious red builds.

This script answers exactly one question: "Has the soak elapsed?"

Behaviour
---------
* Exit 0  →  soak still in progress.  Prints "STILL SOAKING (N days remaining)".
* Exit 1  →  soak elapsed.            Prints the exact two-line patch to apply
            to `.github/workflows/ci.yml` to flip the gate from advisory to
            blocking.

The baseline date is read from
``.benchmarks/Linux-CPython-3.12-64bit/0001_baseline.json``'s ``datetime``
field — the same JSON pytest-benchmark wrote when the baseline was captured.
Refreshing the baseline (which legitimately resets the soak clock — the
runner profile may have changed) automatically resets the countdown.

Usage
-----
    python scripts/check_benchmark_soak.py
    python scripts/check_benchmark_soak.py --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / ".benchmarks" / "Linux-CPython-3.12-64bit" / "0001_baseline.json"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

SOAK_DAYS = 14


def _now() -> dt.datetime:
    """Indirection so tests can monkey-patch."""
    return dt.datetime.now(tz=dt.timezone.utc)


def _read_baseline_datetime() -> dt.datetime:
    if not BASELINE.exists():
        raise SystemExit(
            f"baseline file not found: {BASELINE.relative_to(REPO_ROOT)} — "
            "capture a baseline before running the soak check."
        )
    raw = json.loads(BASELINE.read_text(encoding="utf-8"))
    iso = raw.get("datetime")
    if not iso:
        raise SystemExit("baseline JSON has no `datetime` field; refusing to guess.")
    parsed = dt.datetime.fromisoformat(iso)
    # pytest-benchmark writes naive ISO strings sometimes; normalise to UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON status")
    args = parser.parse_args(argv)

    baseline_at = _read_baseline_datetime()
    elapses_at = baseline_at + dt.timedelta(days=SOAK_DAYS)
    now = _now()
    days_remaining = (elapses_at - now).days
    elapsed = now >= elapses_at

    payload = {
        "baseline_at": baseline_at.isoformat(),
        "elapses_at": elapses_at.isoformat(),
        "now": now.isoformat(),
        "days_remaining": days_remaining,
        "elapsed": elapsed,
        "soak_days_required": SOAK_DAYS,
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1 if elapsed else 0

    if not elapsed:
        print(
            f"STILL SOAKING ({days_remaining} day(s) remaining; "
            f"elapses at {elapses_at.isoformat()})."
        )
        print("Do NOT flip the gate to blocking yet — variance characterisation "
              "is the entry condition.")
        return 0

    print(
        f"SOAK ELAPSED at {elapses_at.isoformat()} "
        f"({-days_remaining} day(s) ago). Promote the gate now."
    )
    print()
    print(f"Open the promotion PR titled:")
    print('  "Item 15 (promotion): Promote benchmark-regression to blocking"')
    print()
    print(f"Apply to {CI_WORKFLOW.relative_to(REPO_ROOT)}:")
    print("  - In the `benchmark-regression:` job, change")
    print("        continue-on-error: true")
    print("    to")
    print("        continue-on-error: false")
    print()
    print("Then update docs/ROADMAP_TO_CLASS_S.md Item 15 to remove the")
    print("\"Currently advisory\" caveat and link the promotion PR.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
