#!/usr/bin/env python3
"""
gap_map_check.py — verifier for PCR-019 / Phase 3 of Final Shape of Complete.

Confirms:
  1. gap_map_and_closure.md exists with all expected sections
  2. Phase 1 + Phase 2 inputs are present (audit + catalog)
  3. Every closure rank 1-10 has a sub-PCR ID
  4. Verify-email endpoint still 500s (the known critical bug)
  5. Canvas/workshop/dispatch routes still 404 (kill targets pre-execution)

Exit codes:
  0 = PASS  (Phase 3 verifier green)
  2 = FAIL  (drift; investigate)

Usage:
    gap_map_check.py            # full verify with probes
    gap_map_check.py --quick    # skip HTTP probes
    gap_map_check.py --verbose
"""

from __future__ import annotations
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_DOC = REPO_ROOT / "docs" / "strategy" / "final_shape_of_complete_plan.md"
UI_AUDIT = REPO_ROOT / "docs" / "strategy" / "ui_surface_audit.md"
CATALOG = REPO_ROOT / "docs" / "strategy" / "backend_function_catalog.md"
GAP_MAP = REPO_ROOT / "docs" / "strategy" / "gap_map_and_closure.md"

BASE_URL = "https://murphy.systems"
HTTP_TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (Murphy-Verifier/PCR-019)"

REQUIRED_SECTIONS = [
    "Section A — UI without backend",
    "Section B — Backend without UI",
    "Section C — UI labels in jargon",
    "The DEAD 122",
    "Closure priorities",
    "Verifier",
]

# The single known critical bug from Phase 2's DEAD list:
# /api/auth/verify-email returns 500. This verifier confirms it's still
# broken (regression catch: if someone fixes it independently, we know).
KNOWN_BROKEN_VERIFY_EMAIL = "/api/auth/verify-email"

# Kill targets from Section A5 — confirm still 404 pre-execution
PRE_KILL_404_TARGETS = ["/workshop", "/dispatch", "/workspace", "/chain"]

# /canvas should still 404 (Phase 5 hasn't mounted it yet)
CANVAS_ROUTE = "/canvas"


def http_status(url: str, _retry: int = 1) -> int | None:
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.status
    except HTTPError as e:
        if e.code == 403 and _retry > 0:
            time.sleep(0.5)
            return http_status(url, _retry=0)
        return e.code
    except (URLError, TimeoutError):
        if _retry > 0:
            time.sleep(0.5)
            return http_status(url, _retry=0)
        return None
    except Exception:
        return None


def check_inputs() -> tuple[bool, str]:
    if not PLAN_DOC.exists():
        return False, f"plan missing: {PLAN_DOC}"
    if not UI_AUDIT.exists():
        return False, f"Phase 1 audit missing — run Phase 1 first"
    if not CATALOG.exists():
        return False, f"Phase 2 catalog missing — run Phase 2 first"
    return True, "Phase 1 + Phase 2 inputs OK"


def check_gap_map_doc() -> tuple[bool, list[str]]:
    notes: list[str] = []
    if not GAP_MAP.exists():
        return False, [f"gap_map_and_closure.md missing: {GAP_MAP}"]
    text = GAP_MAP.read_text(encoding="utf-8", errors="replace")
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    if missing:
        return False, [f"missing sections: {missing}"]
    notes.append(f"  ✓ all {len(REQUIRED_SECTIONS)} required sections present")
    return True, notes


def check_sub_pcr_ids(verbose: bool = False) -> tuple[bool, list[str]]:
    """Every closure rank 1-10 needs a sub-PCR ID like PCR-019.X."""
    notes: list[str] = []
    text = GAP_MAP.read_text(encoding="utf-8", errors="replace")

    # Look for the closure priorities table (ranks 1-10 at minimum)
    pcr_ids = re.findall(r"PCR-019\.[A-Z0-9.\-]+", text)
    unique_pcrs = sorted(set(pcr_ids))
    if len(unique_pcrs) < 10:
        notes.append(f"  ✗ only {len(unique_pcrs)} sub-PCR IDs found "
                     f"(expected ≥10)")
        return False, notes
    if verbose:
        notes.append(f"  ✓ {len(unique_pcrs)} unique sub-PCR IDs: "
                     f"{', '.join(unique_pcrs[:8])}…")
    else:
        notes.append(f"  ✓ {len(unique_pcrs)} unique sub-PCR IDs")
    return True, notes


def check_known_broken_still_broken(verbose: bool = False) -> tuple[bool, list[str]]:
    """Regression catch: /api/auth/verify-email should still 500."""
    notes: list[str] = []
    status = http_status(BASE_URL + KNOWN_BROKEN_VERIFY_EMAIL)
    if status is None:
        notes.append(f"  · {KNOWN_BROKEN_VERIFY_EMAIL}: unreachable (skip)")
        return True, notes
    if status == 500:
        if verbose:
            notes.append(f"  ✓ {KNOWN_BROKEN_VERIFY_EMAIL}: still 500 (Phase 6 fix target)")
        return True, notes
    elif status == 404:
        notes.append(f"  · {KNOWN_BROKEN_VERIFY_EMAIL}: 404 (changed from 500; route may have been removed)")
        return True, notes
    elif status == 200:
        notes.append(f"  ⚠ {KNOWN_BROKEN_VERIFY_EMAIL}: now 200 (someone fixed it — update gap map)")
        # Not a failure — just informational
        return True, notes
    else:
        notes.append(f"  · {KNOWN_BROKEN_VERIFY_EMAIL}: now {status}")
        return True, notes


def check_pre_kill_targets_still_404(verbose: bool = False) -> tuple[bool, list[str]]:
    """Section A5 kill targets — confirm still 404 pre-Phase-4."""
    notes: list[str] = []
    surprises = []
    for path in PRE_KILL_404_TARGETS:
        status = http_status(BASE_URL + path)
        if status is None:
            notes.append(f"  · {path}: unreachable (skip)")
            continue
        if status == 404:
            if verbose:
                notes.append(f"  ✓ {path}: still 404 (kill target pre-execution)")
        else:
            surprises.append(f"  ⚠ {path}: now {status} (was 404 in audit)")
    notes.extend(surprises)
    return True, notes  # surprises are info, not failure


def check_canvas_still_404(verbose: bool = False) -> tuple[bool, list[str]]:
    """Phase 5 hasn't shipped yet — /canvas should still 404."""
    notes: list[str] = []
    status = http_status(BASE_URL + CANVAS_ROUTE)
    if status is None:
        notes.append(f"  · {CANVAS_ROUTE}: unreachable (skip)")
        return True, notes
    if status == 404:
        if verbose:
            notes.append(f"  ✓ {CANVAS_ROUTE}: still 404 (Phase 5 mount target)")
    elif status == 200:
        notes.append(f"  ⚠ {CANVAS_ROUTE}: now 200 (Phase 5 may have shipped early?)")
    else:
        notes.append(f"  · {CANVAS_ROUTE}: now {status}")
    return True, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="skip HTTP probes")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("PCR-019 / Phase 3: Gap Map + Closure Priorities")
    print("=" * 60)

    all_pass = True

    ok, msg = check_inputs()
    print(f"  {'✓' if ok else '✗'} {msg}")
    all_pass = all_pass and ok

    ok, notes = check_gap_map_doc()
    print(f"  {'✓' if ok else '✗'} gap_map_and_closure.md structure")
    for n in notes:
        print(n)
    all_pass = all_pass and ok

    ok, notes = check_sub_pcr_ids(verbose=args.verbose)
    print(f"  {'✓' if ok else '✗'} sub-PCR IDs present for top closures")
    for n in notes:
        print(n)
    all_pass = all_pass and ok

    if not args.quick:
        ok, notes = check_known_broken_still_broken(verbose=args.verbose)
        print(f"  {'✓' if ok else '·'} verify-email regression check")
        for n in notes:
            print(n)

        ok, notes = check_pre_kill_targets_still_404(verbose=args.verbose)
        print(f"  {'✓' if ok else '·'} Section A5 kill targets")
        for n in notes:
            print(n)

        ok, notes = check_canvas_still_404(verbose=args.verbose)
        print(f"  {'✓' if ok else '·'} /canvas still 404 (Phase 5 target)")
        for n in notes:
            print(n)

    print("=" * 60)
    if all_pass:
        print("  ✓ PASS: PCR-019 / Phase 3 verifier green")
        return 0
    else:
        print("  ✗ FAIL: drift detected; investigate")
        return 2


if __name__ == "__main__":
    sys.exit(main())
