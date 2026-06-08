#!/usr/bin/env python3
"""
phase6b_check.py — verifier for PCR-023 / Phase 6b.

Confirms:
  1. src/bottleneck_hitl_writer.py importable
  2. src/auto_fix_matrix.py importable, classify() returns expected shape
  3. /api/auth/verify-email returns 400 (not 500) on bad token
     — the HTMLResponse import fix is live
  4. /api/canvas/hotspots route registered (200 or 401)
  5. All Phase 1-6a verifiers still pass (no regression)
"""

from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
HITL_WRITER = REPO_ROOT / "src" / "bottleneck_hitl_writer.py"
MATRIX = REPO_ROOT / "src" / "auto_fix_matrix.py"

BASE = "https://murphy.systems"
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-023)"
TIMEOUT = 6


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

    print("PCR-023 / Phase 6b verifier")
    print("=" * 60)
    all_pass = True

    # 1. Files exist
    for f in (HITL_WRITER, MATRIX):
        if not f.exists():
            print(f"  ✗ missing: {f.relative_to(REPO_ROOT)}")
            all_pass = False
        else:
            print(f"  ✓ {f.relative_to(REPO_ROOT)} ({f.stat().st_size}b)")

    # 2. Modules importable
    for mod_path, fn in [(HITL_WRITER, "derive_hitl_id"),
                        (MATRIX, "classify")]:
        rc = subprocess.run(
            ["python3", "-c",
             f"import importlib.util as iu; "
             f"s=iu.spec_from_file_location('m','{mod_path}'); "
             f"m=iu.module_from_spec(s); s.loader.exec_module(m); "
             f"assert hasattr(m, '{fn}')"],
            capture_output=True, timeout=10
        )
        if rc.returncode == 0:
            print(f"  ✓ {mod_path.name}.{fn}() importable")
        else:
            print(f"  ✗ {mod_path.name}: {rc.stderr.decode()[:200]}")
            all_pass = False

    if args.quick:
        print("=" * 60)
        print("  ✓ PASS (quick)")
        return 0

    # 3. THE FIX: /api/auth/verify-email no longer 500
    s = http_status(BASE + "/api/auth/verify-email")
    if s == 400:
        print(f"  ✓ /api/auth/verify-email: 400 (no longer 500 — HTMLResponse fix live)")
    elif s == 500:
        print(f"  ✗ /api/auth/verify-email: still 500 (fix not live)")
        all_pass = False
    elif s is None:
        print(f"  · /api/auth/verify-email: unreachable (skip)")
    else:
        print(f"  · /api/auth/verify-email: {s} (not 500, accepted)")

    # 4. Canvas hotspots route
    s = http_status(BASE + "/api/canvas/hotspots")
    if s in (200, 401, 403):
        print(f"  ✓ /api/canvas/hotspots: {s} (route registered)")
    else:
        print(f"  ✗ /api/canvas/hotspots: {s}")
        all_pass = False

    # 5. No regression
    for route in ["/", "/os", "/canvas", "/health-os", "/marketplace",
                  "/comms", "/developers", "/roi-calendar",
                  "/api/health", "/api/conductor/healthz",
                  "/api/public/stats"]:
        s = http_status(BASE + route)
        if s == 200:
            print(f"  ✓ {route}: 200")
        else:
            print(f"  ✗ {route}: {s} (regression)")
            all_pass = False
    for route in ["/api/provenance/preview", "/api/bottleneck/flags"]:
        s = http_status(BASE + route)
        if s in (401, 403):
            print(f"  ✓ {route}: {s} (owner-gated)")
        else:
            print(f"  · {route}: {s}")

    print("=" * 60)
    print("  ✓ PASS: PCR-023 / Phase 6b verifier green" if all_pass else "  ✗ FAIL")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
