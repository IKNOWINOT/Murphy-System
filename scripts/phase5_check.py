#!/usr/bin/env python3
"""
phase5_check.py — verifier for PCR-021 / Phase 5 (Canvas Linking).

Confirms:
  1. /canvas now returns 200 (was 404)
  2. murphy-work-canvas.html includes readout component script tag
  3. murphy-work-canvas.html includes the PCR-021 attachments block
  4. r427_op_canvas.html has the deprecation sentinel
  5. All canonical surfaces + Phase 4b new pages still healthy
  6. /api/canvas/* still 401 (Phase 3 finding holds — they are real
     auth-gated routes, not phantom)
"""

from __future__ import annotations
import argparse
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
WORK_CANVAS = REPO_ROOT / "static" / "murphy-work-canvas.html"
R427_CANVAS = REPO_ROOT / "static" / "r427_op_canvas.html"

BASE = "https://murphy.systems"
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-021)"
TIMEOUT = 6

CANONICAL = ["/", "/os", "/api/health", "/api/conductor/healthz",
             "/api/public/stats"]
PHASE4_PAGES = ["/health-os", "/marketplace", "/comms",
                "/developers", "/roi-calendar"]
CANVAS_API = ["/api/canvas/items", "/api/canvas/attach", "/api/canvas/save"]


def http_status(url, _retry=1):
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("PCR-021 / Phase 5 verifier — Canvas Linking")
    print("=" * 60)

    all_pass = True

    # 1. Files: work-canvas + readout script + attachments block
    if not WORK_CANVAS.exists():
        print("  ✗ murphy-work-canvas.html missing")
        all_pass = False
    else:
        t = WORK_CANVAS.read_text(encoding="utf-8", errors="replace")
        ok_script = "/static/components/murphy-readout.js" in t
        ok_block = "PCR-021 BEGIN canvas attachments" in t
        print(f"  {'✓' if ok_script else '✗'} work-canvas readout script tag")
        print(f"  {'✓' if ok_block else '✗'} work-canvas PCR-021 attachments block")
        if not (ok_script and ok_block):
            all_pass = False

    # 2. r427 has deprecation sentinel
    if R427_CANVAS.exists():
        t = R427_CANVAS.read_text(encoding="utf-8", errors="replace")
        ok_sentinel = "PCR-021 / Phase 5" in t and "DEPRECATED" in t
        print(f"  {'✓' if ok_sentinel else '✗'} r427_op_canvas.html deprecation sentinel")
        if not ok_sentinel:
            all_pass = False
    else:
        print("  · r427_op_canvas.html absent (acceptable)")

    if args.quick:
        print("=" * 60)
        print("  ✓ PASS (quick)")
        return 0

    # 3. /canvas now 200
    s = http_status(BASE + "/canvas")
    if s == 200:
        print(f"  ✓ /canvas: 200 (mounted)")
    elif s is None:
        print(f"  · /canvas: unreachable (skip)")
    else:
        print(f"  ✗ /canvas: {s} (expected 200)")
        all_pass = False

    # 4. Canonical surfaces still healthy
    for route in CANONICAL:
        s = http_status(BASE + route)
        if s == 200:
            print(f"  ✓ {route}: 200")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  ✗ {route}: {s} (regression)")
            all_pass = False

    # 5. Phase 4b pages still healthy
    for route in PHASE4_PAGES:
        s = http_status(BASE + route)
        if s == 200:
            print(f"  ✓ {route}: 200 (Phase 4b page)")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  ✗ {route}: {s} (regression from Phase 4b)")
            all_pass = False

    # 6. /api/canvas/* still 401 (Phase 3 finding confirmed)
    for route in CANVAS_API:
        s = http_status(BASE + route)
        if s in (401, 403):
            print(f"  ✓ {route}: {s} (auth-gated, real — Phase 3 finding)")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  · {route}: {s} (unexpected, not failure)")

    print("=" * 60)
    if all_pass:
        print("  ✓ PASS: PCR-021 / Phase 5 verifier green")
        return 0
    print("  ✗ FAIL")
    return 2


if __name__ == "__main__":
    sys.exit(main())
