#!/usr/bin/env python3
"""
pcr023_patch_app.py — PCR-023 / Phase 6b patcher (v2 — safer anchor).

Two changes to src/runtime/app.py:

  1. FIX verify-email 500: change the verify-email handler signature
     to import HTMLResponse inline. The existing handler at line ~14536
     references HTMLResponse but the name is not defined at that scope.
     The same module imports it with an alias (_HTMLResponse132) at
     line 606, AND 8 other handlers in the same file do their own
     inline import. We follow that established pattern.

     Specifically: insert `from fastapi.responses import HTMLResponse`
     as the FIRST line inside the auth_verify_email function body.

  2. Add GET /api/canvas/hotspots — owner-only, reads bottleneck_flags.json
     and reshapes for canvas consumption.

Idempotent, marker-based, --revert capable.

LEARNED FROM PCR-023 v1 FAILURE (L35):
  Don't anchor on import lines deep inside the file — they may live
  inside try/except blocks. Anchor only on top-level @app.get() routes
  or insert into known-safe in-function locations.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

APP_PY = Path("/opt/Murphy-System/src/runtime/app.py")

# Sentinel comments inserted alongside the changes
VERIFY_FIX_MARKER = "# === PCR-023 verify-email HTMLResponse fix ==="
ROUTE_MARKER = "# === PCR-023 BEGIN canvas hotspots route ==="
ROUTE_END = "# === PCR-023 END canvas hotspots route ==="

# The pattern we're searching for is the docstring opening line of
# auth_verify_email. We insert the import line RIGHT AFTER it.
VERIFY_OLD = '''    @app.get("/api/auth/verify-email")
    async def auth_verify_email(request: Request, token: str = ""):
        """Verify email address from the link sent during signup."""
'''

VERIFY_NEW = '''    @app.get("/api/auth/verify-email")
    async def auth_verify_email(request: Request, token: str = ""):
        """Verify email address from the link sent during signup."""
        ''' + VERIFY_FIX_MARKER + '''
        from fastapi.responses import HTMLResponse  # PCR-023 / Phase 6b
'''

ROUTE_HANDLER = '''
    # === PCR-023 BEGIN canvas hotspots route ===
    @app.get("/api/canvas/hotspots")
    async def _pcr023_canvas_hotspots(request: Request):
        """Bottleneck flags reshaped for canvas consumption. Owner-only."""
        import json, os
        from pathlib import Path as _Path
        _founder_email = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
        _caller = None
        try:
            _caller = request.headers.get("x-murphy-user")
        except Exception:
            pass
        _is_founder = bool(_caller) and _caller == _founder_email
        if not _is_founder:
            try:
                _host = (request.client.host if request.client else "") or ""
                _is_founder = _host in ("127.0.0.1", "::1")
            except Exception:
                pass
        if not _is_founder:
            return JSONResponse({"error": "owner_only"}, status_code=401)

        flags_path = _Path("/var/lib/murphy-production/bottleneck_flags.json")
        if not flags_path.exists():
            return JSONResponse({"hotspots": [], "note": "monitor has not yet produced output"})
        try:
            with flags_path.open() as f:
                data = json.load(f)
            hotspots = []
            for fl in data.get("flags", []):
                hotspots.append({
                    "id": fl.get("flag_id"),
                    "label": fl.get("flag_id", "flag"),
                    "kind": fl.get("kind"),
                    "target": fl.get("target"),
                    "severity": fl.get("severity"),
                    "summary": fl.get("rationale", "")[:200],
                    "result_id": fl.get("flag_id", "preview"),
                })
            return JSONResponse({
                "hotspots": hotspots,
                "generated_at": data.get("generated_at"),
                "count": len(hotspots),
            })
        except Exception as e:
            return JSONResponse({"error": "read_failed", "detail": str(e)[:200]},
                                status_code=500)
    # === PCR-023 END canvas hotspots route ===
'''


def patch_verify_email(verify=False, revert=False):
    text = APP_PY.read_text(encoding="utf-8")
    has = VERIFY_FIX_MARKER in text
    if verify:
        return has, ("  ✓ verify-email HTMLResponse fix applied" if has
                     else "  ✗ verify-email fix NOT applied")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        text = text.replace(VERIFY_NEW, VERIFY_OLD, 1)
        APP_PY.write_text(text, encoding="utf-8")
        return True, "  ✓ reverted verify-email fix"
    if has:
        return True, "  · verify-email already fixed (idempotent)"
    if VERIFY_OLD not in text:
        return False, ("  ✗ exact handler header NOT found — refusing to patch."
                       " Handler may already be modified or removed.")
    text = text.replace(VERIFY_OLD, VERIFY_NEW, 1)
    APP_PY.write_text(text, encoding="utf-8")
    return True, "  ✓ inserted inline HTMLResponse import into auth_verify_email"


def patch_route(verify=False, revert=False):
    text = APP_PY.read_text(encoding="utf-8")
    has = ROUTE_MARKER in text
    if verify:
        return has, ("  ✓ /api/canvas/hotspots patched" if has
                     else "  ✗ /api/canvas/hotspots NOT patched")
    if revert:
        if not has:
            return True, "  · nothing to revert"
        pat = re.compile(re.escape(ROUTE_MARKER) + r".*?" +
                         re.escape(ROUTE_END) + r"\n?", re.DOTALL)
        APP_PY.write_text(pat.sub("", text), encoding="utf-8")
        return True, "  ✓ reverted route"
    if has:
        return True, "  · route already patched (idempotent)"
    anchor = '@app.get("/api/bottleneck/flags")'
    if anchor in text:
        text = text.replace(anchor,
                            ROUTE_HANDLER.lstrip("\n") + "\n    " + anchor)
        APP_PY.write_text(text, encoding="utf-8")
        return True, "  ✓ inserted before /api/bottleneck/flags anchor"
    APP_PY.write_text(text + "\n" + ROUTE_HANDLER + "\n", encoding="utf-8")
    return True, "  ✓ appended (no anchor)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    print(f"PCR-023 patcher v2 verify={args.verify} revert={args.revert}")
    print("=" * 60)
    ok1, msg1 = patch_verify_email(verify=args.verify, revert=args.revert)
    print("verify-email fix:")
    print(msg1)
    ok2, msg2 = patch_route(verify=args.verify, revert=args.revert)
    print("canvas hotspots route:")
    print(msg2)
    print("=" * 60)
    print("  ✓ done" if (ok1 and ok2) else "  ✗ failed")
    return 0 if (ok1 and ok2) else 2


if __name__ == "__main__":
    sys.exit(main())
