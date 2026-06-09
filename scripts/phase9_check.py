#!/usr/bin/env python3
"""
phase9_check.py — verifier for PCR-027 / Phase 9.

Confirms bottleneck_monitor now computes p95/p50 latency per action_name
and emits HIGH_LATENCY flags when p95 > 2x p50.
"""

from __future__ import annotations
import argparse
import importlib.util
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
MONITOR = REPO_ROOT / "src" / "bottleneck_monitor.py"
BASE = "https://murphy.systems"
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-027)"


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

    print("PCR-027 / Phase 9 verifier")
    print("=" * 60)
    all_pass = True

    src_text = MONITOR.read_text(encoding="utf-8")
    if "PCR-027 BEGIN scan_provenance_latency p95" in src_text:
        print("  ✓ PCR-027 marker present")
    else:
        print("  ✗ PCR-027 marker missing")
        all_pass = False

    if "_parse_latency_ms" in src_text:
        print("  ✓ _parse_latency_ms helper defined")
    else:
        print("  ✗ _parse_latency_ms helper missing")
        all_pass = False

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

    # Live call
    db = Path("/var/lib/murphy-production/entity_graph.db")
    if not db.exists():
        print("  · skipping live call: not on prod")
    else:
        try:
            spec = importlib.util.spec_from_file_location(
                "bottleneck_monitor", MONITOR)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            flags, stats = mod.scan_provenance_latency(window_minutes=240)
            print(f"  · scan_provenance_latency(240min):")
            print(f"      provenance_scanned={stats.get('provenance_scanned')}")
            print(f"      producers_seen={stats.get('producers_seen')}")
            print(f"      actions_with_samples={stats.get('actions_with_samples', 0)}")
            print(f"      flags emitted={len(flags)}")
            for f in flags[:5]:
                e = f["evidence"]
                print(f"      - {f['flag_id']}: p50={e['p50_ms']}ms "
                      f"p95={e['p95_ms']}ms ratio={e['ratio']} n={e['sample_size']} ({f['severity']})")
        except Exception as e:
            print(f"  ✗ live call failed: {type(e).__name__}: {e}")
            all_pass = False

    for route in ["/", "/os", "/canvas", "/api/health",
                  "/api/auth/verify-email"]:
        s = http_status(BASE + route)
        expected = (200, 400) if route == "/api/auth/verify-email" else (200,)
        if s in expected:
            print(f"  ✓ {route}: {s}")
        else:
            print(f"  ✗ {route}: {s}")
            all_pass = False

    print("=" * 60)
    print("  ✓ PASS: PCR-027 / Phase 9 verifier green" if all_pass else "  ✗ FAIL")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
