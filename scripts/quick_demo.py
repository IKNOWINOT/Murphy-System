#!/usr/bin/env python3
# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Murphy System — Quick Demo Script

Demonstrates core API endpoints by sending requests to a running Murphy
instance.  Run ``make up`` first, then ``make demo`` in a separate terminal.
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"


def _get(path: str) -> dict:
    """GET *path* and return the parsed JSON body."""
    url = f"{BASE_URL}{path}"
    print(f"\n→ GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = json.loads(resp.read())
            print(f"  Status: {resp.status}")
            print(f"  Body:   {json.dumps(body, indent=2)[:500]}")
            return body
    except urllib.error.URLError as exc:
        print(f"  ✗ Request failed: {exc}")
        return {}


def main() -> None:
    print("=" * 72)
    print("  Murphy System — Quick Demo")
    print("=" * 72)
    print(f"\nTarget: {BASE_URL}")

    # 1. Health check
    health = _get("/api/health")
    if not health:
        print(
            "\n✗ Murphy API is not running.  Start it first:\n"
            "    make up        (or)    python murphy_system_1.0_runtime.py\n"
        )
        sys.exit(1)

    # 2. System status
    _get("/api/status")

    # 3. Deep health / readiness
    _get("/api/health?deep=true")

    print("\n" + "=" * 72)
    print("  Demo complete — Murphy is healthy ✓")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
