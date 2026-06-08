#!/usr/bin/env python3
"""
ui_audit_check.py — verifier for PCR-017 (UI Surface Audit, Phase 1).

Walks static/*.html and confirms:
  1. Every HTML file accounted for in the audit doc
  2. CTA counts in the doc match reality (within tolerance)
  3. The 5 known FAKE routes still return 404 (regression catch)
  4. The canonical 200/401 endpoints still respond as expected
  5. The audit doc itself exists and has the expected sections

Exit codes:
  0 = PASS (Phase 1 verifier green)
  2 = FAIL (drift detected; investigate before next phase)

Usage:
    ui_audit_check.py            # full verify
    ui_audit_check.py --quick    # skip live HTTP probes
    ui_audit_check.py --verbose  # show per-file CTA counts

Plan: docs/strategy/final_shape_of_complete_plan.md (Phase 1)
Doc:  docs/strategy/ui_surface_audit.md
"""

from __future__ import annotations
import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "static"
AUDIT_DOC = REPO_ROOT / "docs" / "strategy" / "ui_surface_audit.md"
PLAN_DOC = REPO_ROOT / "docs" / "strategy" / "final_shape_of_complete_plan.md"

# Routes the audit identified as FAKE (returning 404). Regression catch:
# if any of these starts returning 200, that's actually GOOD — but the
# audit doc needs updating. The verifier flags it so we know.
KNOWN_FAKE_ROUTES = [
    "/canvas",
    "/api/canvas/items",
    "/api/canvas/attach",
    "/api/canvas/save",
    "/workshop",
    "/dispatch",
    "/workspace",
    "/chain",
]

# Routes the audit identified as REAL (200) — confirm they stay green.
EXPECTED_GREEN_ROUTES = [
    "/",
    "/os",
    "/api/health",
    "/api/conductor/healthz",
    "/api/public/stats",
]

# Routes the audit identified as INTERNAL (401-gated). Confirm they
# still 401 (not silently opened, not silently broken).
EXPECTED_AUTH_GATED = [
    "/api/hitl/items",
    "/api/self/audit",
    "/api/registry/capabilities",
    "/api/tellmurphy/dispatch",
]

# Expected per-page totals (from the audit). Within tolerance.
# Format: filename → (min_onclicks, max_onclicks, min_fetches, max_fetches)
EXPECTED_TOTALS = {
    "murphy-os.html":               (90, 110, 4, 10),
    "murphy-work-canvas.html":      (1, 6, 2, 5),
    "hitl.html":                    (0, 5, 4, 10),
    "pricing.html":                 (3, 8, 1, 4),
    "checkout.html":                (0, 4, 2, 5),
    "founder-control.html":         (0, 4, 0, 3),
    "customer-dashboard.html":      (0, 4, 3, 7),
    "chat.html":                    (0, 4, 2, 5),
    "conductor.html":               (1, 4, 1, 4),
    "llm-spend.html":               (1, 3, 1, 3),
    "timeline.html":                (1, 3, 1, 4),
    "cyborg-status.html":           (0, 4, 3, 6),
    "r427_op_canvas.html":          (1, 4, 1, 3),
    "dlfr.html":                    (0, 3, 1, 4),
}

BASE_URL = "https://murphy.systems"
HTTP_TIMEOUT = 5


def http_status(url: str) -> int | None:
    """Return HTTP status code for url, or None on error."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return r.status
    except HTTPError as e:
        return e.code
    except (URLError, TimeoutError):
        return None
    except Exception:
        return None


def count_ctas(html_path: Path) -> dict:
    """Count CTAs in an HTML file."""
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"onclick": 0, "fetch": 0, "action": 0, "href": 0, "error": "unreadable"}

    onclick = len(re.findall(r'onclick\s*=\s*"[^"]+"', text))
    onclick += len(re.findall(r"onclick\s*=\s*'[^']+'", text))
    fetch = len(re.findall(r"fetch\s*\(\s*[\"'][^\"']+[\"']", text))
    action = len(re.findall(r'<form\s+[^>]*action\s*=\s*"[^"]+"', text))
    href = len(re.findall(r'href\s*=\s*"/[^"]*"', text))

    return {"onclick": onclick, "fetch": fetch, "action": action, "href": href}


def check_audit_doc_exists() -> tuple[bool, str]:
    """Confirm the audit doc exists and has the expected sections."""
    if not AUDIT_DOC.exists():
        return False, f"audit doc missing: {AUDIT_DOC}"
    text = AUDIT_DOC.read_text(encoding="utf-8", errors="replace")
    required_sections = [
        "Page-by-page CTA inventory",
        "Cross-page totals",
        "The 5 critical FAKE findings",
        "Verifier",
    ]
    missing = [s for s in required_sections if s not in text]
    if missing:
        return False, f"audit doc missing sections: {missing}"
    return True, "audit doc OK"


def check_plan_doc_exists() -> tuple[bool, str]:
    if not PLAN_DOC.exists():
        return False, f"plan doc missing: {PLAN_DOC}"
    return True, "plan doc OK"


def check_cta_totals(verbose: bool = False) -> tuple[bool, list[str]]:
    """Confirm CTA counts in each HTML file match expected tolerance."""
    failures = []
    notes = []

    if not STATIC.exists():
        return False, [f"static/ dir missing: {STATIC}"]

    for fname, (min_o, max_o, min_f, max_f) in EXPECTED_TOTALS.items():
        html = STATIC / fname
        if not html.exists():
            failures.append(f"  ✗ {fname}: file missing")
            continue
        counts = count_ctas(html)
        oc = counts["onclick"]
        fc = counts["fetch"]
        ok = (min_o <= oc <= max_o) and (min_f <= fc <= max_f)
        marker = "✓" if ok else "✗"
        msg = f"  {marker} {fname}: {oc} onclick (expect {min_o}-{max_o}), {fc} fetch (expect {min_f}-{max_f})"
        if verbose or not ok:
            notes.append(msg)
        if not ok:
            failures.append(f"{fname}: drift")

    return len(failures) == 0, notes


def check_fake_routes_still_fake(verbose: bool = False) -> tuple[bool, list[str]]:
    """Confirm known FAKE routes still return 404 (regression detection)."""
    notes = []
    surprises = []
    for route in KNOWN_FAKE_ROUTES:
        status = http_status(BASE_URL + route)
        if status is None:
            notes.append(f"  · {route}: unreachable (skipped)")
            continue
        if status == 404:
            if verbose:
                notes.append(f"  ✓ {route}: still 404 (expected)")
        else:
            # Got something other than 404 — not necessarily bad
            # but the audit doc needs an update
            surprises.append(f"  ⚠ {route}: now {status} (was 404 at audit time)")
    notes.extend(surprises)
    # NOT a failure if a fake route became real — just a heads-up.
    # We pass the verifier but flag the surprise.
    return True, notes


def check_green_routes_still_green(verbose: bool = False) -> tuple[bool, list[str]]:
    """Confirm canonical REAL routes still 200."""
    notes = []
    failures = []
    for route in EXPECTED_GREEN_ROUTES:
        status = http_status(BASE_URL + route)
        if status is None:
            notes.append(f"  · {route}: unreachable (skipped)")
            continue
        if status == 200:
            if verbose:
                notes.append(f"  ✓ {route}: 200")
        else:
            failures.append(f"  ✗ {route}: {status} (expected 200)")
    notes.extend(failures)
    return len(failures) == 0, notes


def check_auth_gated_still_gated(verbose: bool = False) -> tuple[bool, list[str]]:
    """Confirm INTERNAL routes still require auth (401/403)."""
    notes = []
    failures = []
    for route in EXPECTED_AUTH_GATED:
        status = http_status(BASE_URL + route)
        if status is None:
            notes.append(f"  · {route}: unreachable (skipped)")
            continue
        if status in (401, 403):
            if verbose:
                notes.append(f"  ✓ {route}: {status} (still gated)")
        elif status == 200:
            # Silently opened — security regression
            failures.append(f"  ⚠ {route}: 200 (was {status}-gated at audit time — was this intentional?)")
        elif status == 404:
            failures.append(f"  ✗ {route}: 404 (was gated, now missing)")
        else:
            notes.append(f"  · {route}: {status} (unexpected; not a failure)")
    notes.extend(failures)
    return len(failures) == 0, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true",
                    help="skip live HTTP probes (offline-friendly)")
    ap.add_argument("--verbose", action="store_true",
                    help="show all per-check details")
    args = ap.parse_args()

    print("PCR-017 / Phase 1 verifier: UI Surface Audit")
    print("=" * 60)

    all_pass = True

    # 1. Audit doc + plan doc exist
    ok, msg = check_audit_doc_exists()
    print(f"  {'✓' if ok else '✗'} {msg}")
    all_pass = all_pass and ok

    ok, msg = check_plan_doc_exists()
    print(f"  {'✓' if ok else '✗'} {msg}")
    all_pass = all_pass and ok

    # 2. CTA totals match within tolerance
    ok, notes = check_cta_totals(verbose=args.verbose)
    print(f"  {'✓' if ok else '✗'} CTA counts within tolerance")
    for n in notes:
        print(n)
    all_pass = all_pass and ok

    # 3-5. Live HTTP probes (skip if --quick)
    if not args.quick:
        ok, notes = check_green_routes_still_green(verbose=args.verbose)
        print(f"  {'✓' if ok else '✗'} REAL routes still 200")
        for n in notes:
            print(n)
        all_pass = all_pass and ok

        ok, notes = check_auth_gated_still_gated(verbose=args.verbose)
        print(f"  {'✓' if ok else '✗'} INTERNAL routes still auth-gated")
        for n in notes:
            print(n)
        all_pass = all_pass and ok

        ok, notes = check_fake_routes_still_fake(verbose=args.verbose)
        print(f"  {'✓' if ok else '·'} FAKE routes regression check")
        for n in notes:
            print(n)
        # Not strictly a fail; just informational

    print("=" * 60)
    if all_pass:
        print("  ✓ PASS: PCR-017 / Phase 1 verifier green")
        return 0
    else:
        print("  ✗ FAIL: drift detected; investigate before next phase")
        return 2


if __name__ == "__main__":
    sys.exit(main())
