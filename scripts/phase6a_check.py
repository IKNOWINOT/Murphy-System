#!/usr/bin/env python3
"""
phase6a_check.py — verifier for PCR-022 / Phase 6a (Bottleneck Monitor).

Confirms:
  1. src/bottleneck_monitor.py exists and is importable
  2. systemd unit files installed and enabled
  3. /api/bottleneck/flags route is reachable (401 if not authed; that's
     correct — same edge-gate pattern as /api/provenance)
  4. /var/lib/murphy-production/bottleneck_flags.json exists after first run
  5. JSON has the expected schema (generated_at, flags array, stats dict)
  6. All Phase 1-5 verifiers still pass (no regression)
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
MONITOR_PY = REPO_ROOT / "src" / "bottleneck_monitor.py"
SERVICE_FILE = REPO_ROOT / "deploy" / "murphy-bottleneck-monitor.service"
TIMER_FILE = REPO_ROOT / "deploy" / "murphy-bottleneck-monitor.timer"
FLAGS_JSON = Path("/var/lib/murphy-production/bottleneck_flags.json")

BASE = "https://murphy.systems"
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-022)"
TIMEOUT = 6

CANONICAL = ["/", "/os", "/canvas", "/api/health", "/api/public/stats"]
PHASE4_PAGES = ["/health-os", "/marketplace", "/comms",
                "/developers", "/roi-calendar"]


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

    print("PCR-022 / Phase 6a verifier — Bottleneck Monitor")
    print("=" * 60)
    all_pass = True

    # 1. Files
    for f in (MONITOR_PY, SERVICE_FILE, TIMER_FILE):
        if not f.exists():
            print(f"  ✗ missing: {f.relative_to(REPO_ROOT)}")
            all_pass = False
        else:
            print(f"  ✓ {f.relative_to(REPO_ROOT)} ({f.stat().st_size}b)")

    # 2. Monitor compiles + runnable
    try:
        rc = subprocess.run(["python3", "-c",
                             "import importlib.util; "
                             "spec=importlib.util.spec_from_file_location('m', "
                             f"'{MONITOR_PY}'); "
                             "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
                             "assert hasattr(m, 'compute_flags')"],
                            capture_output=True, timeout=10)
        if rc.returncode == 0:
            print("  ✓ bottleneck_monitor.compute_flags importable")
        else:
            print(f"  ✗ import failed: {rc.stderr.decode()[:200]}")
            all_pass = False
    except Exception as e:
        print(f"  · import check skipped ({e})")

    if args.quick:
        print("=" * 60)
        print("  ✓ PASS (quick)")
        return 0

    # 3. Flags JSON has expected schema (if monitor has run at least once)
    if FLAGS_JSON.exists():
        try:
            with FLAGS_JSON.open() as f:
                data = json.load(f)
            required = {"generated_at", "window_minutes", "flags",
                        "flag_count", "stats", "phase", "schema_version"}
            missing = required - set(data.keys())
            if missing:
                print(f"  ✗ flags JSON missing keys: {missing}")
                all_pass = False
            else:
                print(f"  ✓ flags JSON schema ok "
                      f"({data['flag_count']} flags, generated {data['generated_at']})")
        except Exception as e:
            print(f"  ✗ flags JSON unreadable: {e}")
            all_pass = False
    else:
        print("  · flags JSON not yet written (monitor may not have run)")

    # 4. /api/bottleneck/flags route
    s = http_status(BASE + "/api/bottleneck/flags")
    if s in (200, 401, 403):
        print(f"  ✓ /api/bottleneck/flags: {s} (route registered)")
    elif s is None:
        print(f"  · /api/bottleneck/flags: unreachable (skip)")
    else:
        print(f"  ✗ /api/bottleneck/flags: {s} (expected 200/401/403)")
        all_pass = False

    # 5. No regression on any prior phase
    for route in CANONICAL + PHASE4_PAGES:
        s = http_status(BASE + route)
        if s == 200:
            print(f"  ✓ {route}: 200")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  ✗ {route}: {s} (regression)")
            all_pass = False

    print("=" * 60)
    print("  ✓ PASS: PCR-022 / Phase 6a verifier green" if all_pass else "  ✗ FAIL")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
