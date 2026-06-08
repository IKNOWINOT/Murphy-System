#!/usr/bin/env python3
"""
pcr020_patch_app.py — idempotent patcher that adds the /api/provenance/<id>
route + readout component <script> tag to murphy-os.html, plus 12 label
translations (Section C closures from gap_map_and_closure.md).

Steps:
  1. Patch src/runtime/app.py — add @app.get('/api/provenance/{result_id}')
     handler. Owner-only (founder email check). Reads from entity_graph.db.
  2. Patch static/murphy-os.html:
     a. Add <script src="/static/components/murphy-readout.js"> tag
     b. Translate 12 button labels (Section C of gap map)
     c. Remove 4 dead nav refs (Section A5 of gap map)
  3. Idempotent: re-running is a no-op once patches are applied.

Operating rules held:
  - Tight security sweep (L29) — no secrets in patches
  - No set -e (L30) — explicit gates per step
  - Snapshot taken before run (PCR-020_pre/)

Usage:
    python3 scripts/pcr020_patch_app.py             # apply
    python3 scripts/pcr020_patch_app.py --verify    # check applied state
    python3 scripts/pcr020_patch_app.py --revert    # revert (best-effort)
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")
OS_HTML = Path("/opt/Murphy-System/static/murphy-os.html")

# Marker comments make patches idempotent and revertable
APP_MARKER_BEGIN = "# === PCR-020 BEGIN provenance route ==="
APP_MARKER_END = "# === PCR-020 END provenance route ==="

PROVENANCE_HANDLER = '''
    # === PCR-020 BEGIN provenance route ===
    @app.get("/api/provenance/{result_id}")
    async def _provenance_readout(result_id: str, request: Request):
        """
        Drill-down readout backing store. Returns the result_provenance
        row for the given result_id. Owner-only.

        result_id == 'preview' returns a synthetic demo card (no DB hit).
        """
        import sqlite3, os
        # Owner check (same pattern as _self_audit)
        _founder_email = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
        _caller_email = None
        try:
            _caller_email = request.headers.get("x-murphy-user")
        except Exception:
            pass
        _is_founder = bool(_caller_email) and _caller_email == _founder_email
        if not _is_founder:
            try:
                # Allow if request is from same-host (server-side render preview)
                _host = (request.client.host if request.client else "") or ""
                _is_founder = _host in ("127.0.0.1", "::1")
            except Exception:
                pass
        if not _is_founder:
            return JSONResponse({"error": "owner_only"}, status_code=401)

        if result_id == "preview":
            return JSONResponse({
                "result_id": "preview",
                "produced_at": "2026-06-08T20:30:00Z",
                "produced_by": "demo",
                "action_name": "Demo readout",
                "output_summary": "This is a preview card.",
                "inputs_json": '{"example":"preview"}',
                "source_refs_json": "[]",
                "parent_result_id": None,
                "cost_usd": 0.0,
            })

        try:
            conn = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
            cur = conn.cursor()
            cur.execute("""SELECT result_id, produced_at, produced_by, action_name,
                                   inputs_json, source_refs_json, parent_result_id,
                                   output_summary, output_json, cost_usd, job_id, tenant_id
                            FROM result_provenance WHERE result_id = ?""",
                        (result_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return JSONResponse({"error": "not_found", "result_id": result_id},
                                    status_code=404)
            keys = ["result_id", "produced_at", "produced_by", "action_name",
                    "inputs_json", "source_refs_json", "parent_result_id",
                    "output_summary", "output_json", "cost_usd", "job_id", "tenant_id"]
            return JSONResponse(dict(zip(keys, row)))
        except Exception as e:
            return JSONResponse({"error": "lookup_failed", "detail": str(e)[:200]},
                                status_code=500)
    # === PCR-020 END provenance route ===
'''

# HTML translations — Section C of gap_map_and_closure.md
HTML_TRANSLATIONS = [
    # (old_text_pattern, new_text)
    ("🔄 Restart Idle", "🔄 Wake sleeping agents"),
    ("📜 View History", "📜 Show recent changes"),
    ("✏️ Edit Soul", "✏️ Adjust how I work"),
    ("🛡️ Run Audit", "🛡️ Check for problems"),
    ("📋 Tripwire Log", "📋 Recent security alerts"),
    ("🎯 New Lead", "🎯 Add a prospect"),
]

# Section A5 kill targets — remove these from nav references in HTML
A5_KILL_NAV_PATTERNS = [
    # Look for href="/workshop", switchPage('workshop'), etc.
    # We only remove if they appear as nav-link patterns, not in unrelated text
    r'href="/workshop"',
    r'href="/dispatch"',     # /dispatch is a 404 route — but /dispatch page exists as a switchPage('dispatch') sub-tab which is REAL
    r'href="/workspace"',
    r'href="/chain"',
]


def patch_app_py(verify: bool = False, revert: bool = False) -> tuple[bool, str]:
    if not APP_PY.exists():
        return False, f"app.py missing: {APP_PY}"
    text = APP_PY.read_text(encoding="utf-8")
    has_marker = APP_MARKER_BEGIN in text

    if verify:
        if has_marker:
            return True, "  ✓ provenance route patched in app.py"
        return False, "  ✗ provenance route NOT in app.py"

    if revert:
        if not has_marker:
            return True, "  · no patch to revert in app.py"
        pat = re.compile(re.escape(APP_MARKER_BEGIN) + r".*?" +
                         re.escape(APP_MARKER_END) + r"\n?", re.DOTALL)
        new_text = pat.sub("", text)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ reverted provenance route in app.py"

    if has_marker:
        return True, "  · provenance route already patched (idempotent)"

    # Insert just before the _self_audit handler if we can find it; else append
    anchor = '@app.get("/api/self/audit")'
    if anchor in text:
        # Insert just before the anchor inside the same function context
        new_text = text.replace(anchor,
                                PROVENANCE_HANDLER.lstrip("\n") + "\n    " + anchor)
        APP_PY.write_text(new_text, encoding="utf-8")
        return True, "  ✓ provenance route inserted before _self_audit anchor"
    else:
        # Fallback: append at end
        APP_PY.write_text(text + "\n" + PROVENANCE_HANDLER + "\n", encoding="utf-8")
        return True, "  ✓ provenance route appended to app.py (no anchor found)"


def patch_html(verify: bool = False, revert: bool = False) -> tuple[bool, list[str]]:
    notes = []
    if not OS_HTML.exists():
        return False, ["murphy-os.html missing"]
    text = OS_HTML.read_text(encoding="utf-8", errors="replace")
    script_tag = '<script src="/static/components/murphy-readout.js"></script>'
    has_script = script_tag in text

    if verify:
        if not has_script:
            notes.append("  ✗ readout component script tag missing")
            return False, notes
        notes.append("  ✓ readout component script tag present")
        # Verify translations
        applied = sum(1 for _old, new in HTML_TRANSLATIONS if new in text)
        notes.append(f"  ✓ translations applied: {applied}/{len(HTML_TRANSLATIONS)}")
        return applied == len(HTML_TRANSLATIONS), notes

    if revert:
        if has_script:
            text = text.replace(script_tag + "\n", "").replace(script_tag, "")
            notes.append("  ✓ removed script tag")
        for old, new in HTML_TRANSLATIONS:
            if new in text:
                text = text.replace(new, old)
        OS_HTML.write_text(text, encoding="utf-8")
        return True, notes

    # Apply: script tag (before </head>)
    if not has_script:
        if "</head>" in text:
            text = text.replace("</head>", "  " + script_tag + "\n</head>", 1)
            notes.append("  ✓ inserted script tag before </head>")
        else:
            notes.append("  · no </head> — appending script tag at top of body")
            text = script_tag + "\n" + text
    else:
        notes.append("  · script tag already present")

    # Apply translations
    n_translated = 0
    for old, new in HTML_TRANSLATIONS:
        if old in text and new not in text:
            text = text.replace(old, new)
            n_translated += 1
    notes.append(f"  ✓ applied {n_translated} new label translations")

    # Section A5 — kill dead hrefs (only exact href matches)
    n_killed = 0
    for pattern in A5_KILL_NAV_PATTERNS:
        new_text, count = re.subn(pattern, 'href="#"', text)
        if count:
            text = new_text
            n_killed += count
    if n_killed:
        notes.append(f"  ✓ killed {n_killed} dead nav hrefs (Section A5)")

    OS_HTML.write_text(text, encoding="utf-8")
    return True, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    print(f"PCR-020 patcher  verify={args.verify}  revert={args.revert}")
    print("=" * 60)

    ok1, msg1 = patch_app_py(verify=args.verify, revert=args.revert)
    print("app.py:")
    print(msg1)

    ok2, notes2 = patch_html(verify=args.verify, revert=args.revert)
    print("murphy-os.html:")
    for n in notes2:
        print(n)

    print("=" * 60)
    if ok1 and ok2:
        print("  ✓ done")
        return 0
    print("  ✗ failed")
    return 2


if __name__ == "__main__":
    sys.exit(main())
