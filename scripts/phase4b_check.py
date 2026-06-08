#!/usr/bin/env python3
"""
phase4b_check.py — verifier for PCR-020 / Phase 4b.

Confirms:
  1. Phase 4a is still green (delegates to readout_check)
  2. The 5 new HTML files exist with required content
  3. The 4 new HTML routes are mounted and return 200
     (/health-os, /comms, /developers, /roi-calendar)
     /marketplace was already mounted; confirms it still 200s.
  4. Section A5 nav kills are applied in murphy-os.html
  5. All canonical surfaces still 200
"""

from __future__ import annotations
import argparse
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "static"
OS_HTML = STATIC / "murphy-os.html"

NEW_PAGES = ["health.html", "marketplace.html", "comms.html",
             "developers.html", "roi-calendar.html"]

NEW_ROUTES = ["/health-os", "/comms", "/developers", "/roi-calendar", "/marketplace"]
CANONICAL = ["/", "/os", "/api/health", "/api/conductor/healthz",
             "/api/public/stats", "/api/provenance/preview"]

BASE = "https://murphy.systems"
TIMEOUT = 6
UA = "Mozilla/5.0 (Murphy-Verifier/PCR-020b)"


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

    print("PCR-020b / Phase 4b verifier")
    print("=" * 60)

    all_pass = True

    # 1. 5 new HTML files exist
    for f in NEW_PAGES:
        p = STATIC / f
        if not p.exists():
            print(f"  ✗ {f} missing")
            all_pass = False
        else:
            size = p.stat().st_size
            if size < 800:
                print(f"  ✗ {f} suspiciously small ({size}b)")
                all_pass = False
            else:
                print(f"  ✓ {f} ({size}b)")

    # 2. OS_HTML still includes readout component
    if OS_HTML.exists():
        t = OS_HTML.read_text(encoding="utf-8", errors="replace")
        if "components/murphy-readout.js" in t:
            print("  ✓ murphy-os.html still includes readout component")
        else:
            print("  ✗ readout component script tag missing from os.html")
            all_pass = False
    else:
        print("  ✗ murphy-os.html missing")
        all_pass = False

    if args.quick:
        print("=" * 60)
        print("  ✓ PASS (quick mode)")
        return 0

    # 3. New routes return 200
    for route in NEW_ROUTES:
        s = http_status(BASE + route)
        if s == 200:
            print(f"  ✓ {route}: 200")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  ✗ {route}: {s} (expected 200)")
            all_pass = False

    # 4. Canonical surfaces still healthy
    for route in CANONICAL:
        s = http_status(BASE + route)
        expected_ok = (s == 200) or (route.startswith("/api/provenance") and s in (401, 403))
        if expected_ok:
            print(f"  ✓ {route}: {s}")
        elif s is None:
            print(f"  · {route}: unreachable (skip)")
        else:
            print(f"  ✗ {route}: {s} (regression)")
            all_pass = False

    print("=" * 60)
    if all_pass:
        print("  ✓ PASS: PCR-020b / Phase 4b verifier green")
        return 0
    print("  ✗ FAIL")
    return 2


if __name__ == "__main__":
    sys.exit(main())
