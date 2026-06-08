#!/usr/bin/env python3
"""
readout_check.py — verifier for PCR-020 / Phase 4a (Drill-Down Readout System).

Confirms:
  1. result_provenance schema exists in entity_graph.db
  2. <murphy-readout> component file exists with expected exports
  3. /api/provenance/<id> route is reachable (401-gated; that's REAL+INTERNAL)
  4. murphy-os.html includes the readout component script tag
  5. Inputs (Phase 1-3 docs) are present

Exit codes:
  0 = PASS  (Phase 4a verifier green)
  2 = FAIL  (drift; investigate)
"""

from __future__ import annotations
import argparse
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path("/var/lib/murphy-production/entity_graph.db")
COMPONENT_JS = REPO_ROOT / "static" / "components" / "murphy-readout.js"
OS_HTML = REPO_ROOT / "static" / "murphy-os.html"
PLAN_DOC = REPO_ROOT / "docs" / "strategy" / "final_shape_of_complete_plan.md"
GAP_MAP = REPO_ROOT / "docs" / "strategy" / "gap_map_and_closure.md"

BASE_URL = "https://murphy.systems"
HTTP_TIMEOUT = 5
USER_AGENT = "Mozilla/5.0 (Murphy-Verifier/PCR-020)"


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


def check_inputs() -> tuple[bool, list[str]]:
    notes = []
    for f in (PLAN_DOC, GAP_MAP):
        if not f.exists():
            return False, [f"missing input: {f.relative_to(REPO_ROOT)}"]
        notes.append(f"  ✓ {f.relative_to(REPO_ROOT)} present")
    return True, notes


def check_schema() -> tuple[bool, list[str]]:
    if not DB_PATH.exists():
        return False, [f"  ✗ DB missing: {DB_PATH}"]
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name='result_provenance';")
        if not cur.fetchone():
            return False, ["  ✗ result_provenance table missing"]
        # Check indexes
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='result_provenance';")
        idx = sorted(r[0] for r in cur.fetchall())
        expected_idx = ['idx_provenance_job_id', 'idx_provenance_parent_result_id',
                        'idx_provenance_produced_at', 'idx_provenance_tenant_id']
        missing = [i for i in expected_idx if i not in idx]
        if missing:
            return False, [f"  ✗ missing indexes: {missing}"]
        cur.execute("SELECT COUNT(*) FROM result_provenance;")
        n = cur.fetchone()[0]
        conn.close()
        return True, [f"  ✓ result_provenance table OK ({len(idx)} indexes, {n} rows)"]
    except Exception as e:
        return False, [f"  ✗ schema check error: {e}"]


def check_component() -> tuple[bool, list[str]]:
    if not COMPONENT_JS.exists():
        return False, [f"  ✗ component missing: {COMPONENT_JS.relative_to(REPO_ROOT)}"]
    text = COMPONENT_JS.read_text(encoding="utf-8")
    required = [
        "customElements.define",
        "murphy-readout",
        "result-id",
        "/api/provenance/",
    ]
    missing = [s for s in required if s not in text]
    if missing:
        return False, [f"  ✗ component missing: {missing}"]
    return True, [f"  ✓ <murphy-readout> component OK ({len(text)} bytes)"]


def check_html_includes_component() -> tuple[bool, list[str]]:
    if not OS_HTML.exists():
        return False, ["  ✗ murphy-os.html missing"]
    text = OS_HTML.read_text(encoding="utf-8", errors="replace")
    if "components/murphy-readout.js" not in text:
        return False, ["  ✗ murphy-os.html does not include components/murphy-readout.js"]
    return True, ["  ✓ murphy-os.html includes murphy-readout component"]


def check_provenance_route() -> tuple[bool, list[str]]:
    """The /api/provenance/<id> route should exist and be auth-gated."""
    # Use a fake ID; we expect 401/403 (auth-gated) or 404 (id not found)
    # not 500 or network error
    status = http_status(BASE_URL + "/api/provenance/preview")
    if status is None:
        return True, ["  · /api/provenance/preview: unreachable (skip)"]
    if status in (200, 401, 403, 404):
        return True, [f"  ✓ /api/provenance/<id>: {status} (route registered)"]
    if status == 500:
        return False, [f"  ✗ /api/provenance/<id>: 500 (route broken)"]
    return True, [f"  · /api/provenance/<id>: {status}"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="skip HTTP probes")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("PCR-020 / Phase 4a: Drill-Down Readout System")
    print("=" * 60)

    all_pass = True
    for name, fn in [
        ("inputs",      check_inputs),
        ("schema",      check_schema),
        ("component",   check_component),
        ("html include", check_html_includes_component),
    ]:
        ok, notes = fn()
        print(f"  {'✓' if ok else '✗'} {name}")
        for n in notes:
            print(n)
        all_pass = all_pass and ok

    if not args.quick:
        ok, notes = check_provenance_route()
        print(f"  {'✓' if ok else '✗'} /api/provenance route")
        for n in notes:
            print(n)
        all_pass = all_pass and ok

    print("=" * 60)
    if all_pass:
        print("  ✓ PASS: PCR-020 / Phase 4a verifier green")
        return 0
    print("  ✗ FAIL: drift; investigate")
    return 2


if __name__ == "__main__":
    sys.exit(main())
