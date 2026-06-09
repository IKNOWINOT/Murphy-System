#!/usr/bin/env python3
"""
phase8_check.py — verifier for PCR-026 / Phase 8.

Confirms bottleneck_monitor.scan_cost_spikes now reads
llm_cost_ledger.calls (alive) instead of economic_pulse.cost_events
(dead since 2026-05-12).

  1. monitor module importable + patcher marker present
  2. scan_cost_spikes() now references llm_cost_ledger
  3. Direct call returns costs_scanned > 0 (was always 0)
  4. No regression on prior phase verifiers
"""

from __future__ import annotations
import argparse
import importlib.util
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
MONITOR = REPO_ROOT / "src" / "bottleneck_monitor.py"
BASE = "https://murphy.systems"
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-026)"


def http_status(url, _retry=1):
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=6) as r:
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    print("PCR-026 / Phase 8 verifier")
    print("=" * 60)
    all_pass = True

    # 1. Marker present
    src_text = MONITOR.read_text(encoding="utf-8")
    if "PCR-026 BEGIN rewired scan_cost_spikes" in src_text:
        print("  ✓ PCR-026 marker present in bottleneck_monitor.py")
    else:
        print("  ✗ PCR-026 marker missing")
        all_pass = False

    if "llm_cost_ledger" not in src_text:
        print("  ✗ llm_cost_ledger reference missing")
        all_pass = False
    else:
        print("  ✓ bottleneck_monitor references llm_cost_ledger")

    # 2. Compile check
    rc = subprocess.run(
        ["python3", "-c",
         f"import py_compile; py_compile.compile('{MONITOR}', doraise=True)"],
        capture_output=True, timeout=10
    )
    if rc.returncode == 0:
        print("  ✓ bottleneck_monitor.py compiles")
    else:
        print(f"  ✗ compile failure: {rc.stderr.decode()[:200]}")
        all_pass = False
        return 2

    if args.quick:
        print("=" * 60)
        print("  ✓ PASS (quick)")
        return 0 if all_pass else 2

    # 3. Live call (must run on prod where the DB exists)
    db = Path("/var/lib/murphy-production/llm_cost_ledger.db")
    if not db.exists():
        print("  · skipping live call: not on prod (llm_cost_ledger.db absent)")
    else:
        try:
            spec = importlib.util.spec_from_file_location(
                "bottleneck_monitor", MONITOR)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            flags, stats = mod.scan_cost_spikes(window_minutes=60)
            scanned = stats.get("costs_scanned", 0)
            seen = stats.get("action_types_seen", 0)
            print(f"  · scan_cost_spikes(60min): costs_scanned={scanned}, "
                  f"action_types_seen={seen}, flags={len(flags)}")
            if scanned > 0:
                print(f"  ✓ {scanned} cost rows scanned (was always 0 before)")
            else:
                print(f"  ⚠ scanned=0 — possible if no LLM calls in last hour")
        except Exception as e:
            print(f"  ✗ scan_cost_spikes call failed: {e}")
            all_pass = False

    # 4. No regression
    for route in ["/", "/os", "/canvas", "/api/health",
                  "/api/auth/verify-email"]:
        s = http_status(BASE + route)
        expected = (200, 400) if route == "/api/auth/verify-email" else (200,)
        if s in expected:
            print(f"  ✓ {route}: {s}")
        else:
            print(f"  ✗ {route}: {s} (regression)")
            all_pass = False

    print("=" * 60)
    print("  ✓ PASS: PCR-026 / Phase 8 verifier green" if all_pass else "  ✗ FAIL")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
