#!/usr/bin/env python3
"""
PATCH-426b — Let /api/payments/checkout accept founder API key
================================================================

WHAT THIS IS:
  The /api/payments/checkout handler (app.py:25928) calls
  _account_or_founder(request) to get the caller's account.

  _account_or_founder only succeeds if EITHER:
    (a) request has a session cookie → _get_account_from_session returns it
    (b) auth middleware stamped request.state.actor_kind = 'api_key'

  Now that /api/payments/ is on the exempt list (PATCH-426), middleware
  skips it and never stamps actor_kind. So (b) never fires, even when
  X-API-Key is present.

  Fix: in payment_checkout_link, ALSO check the X-API-Key header
  directly. If it matches FOUNDER_API_KEY, look up founder account
  from murphy.db. No middleware dependency.

WHY IT EXISTS:
  Closing the loop on PATCH-426. Webhook works (just verified —
  bad sig 400, good sig 200). Checkout is the other half of the
  NOWPayments rail; founder needs to be able to test it before we
  hand it to anonymous pricing-page visitors.

HOW IT FITS:
  Surgical edit to one handler. Mirrors the same fallback pattern
  that _account_or_founder uses internally — just done at the
  handler level instead of relying on middleware stamping.

  After this patch the call ordering is:
    1. session cookie (logged-in users)
    2. X-API-Key === FOUNDER_API_KEY (us, testing)
    3. body.account_id (future: anonymous pricing-page visitors)

LAST UPDATED: 2026-05-25 by PATCH-426b
"""
import ast
import shutil
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()
NL = chr(10)

if "PATCH-426b" in src:
    print("  ⚠ PATCH-426b marker already in file — skipping")
    raise SystemExit(0)

OLD = (
    '    @app.get("/api/payments/checkout")' + NL +
    '    async def payment_checkout_link(request: Request, tier: str = "solo", add_on: str = ""):' + NL +
    '        """Generate a NOWPayments invoice link for the requested tier."""' + NL +
    '        import urllib.request, urllib.parse, json as _json' + NL +
    '        account = _account_or_founder(request)' + NL +
    '        if not account:' + NL +
    '            from fastapi import HTTPException as _HE' + NL +
    '            raise _HE(status_code=401, detail="Not authenticated")'
)

NEW = (
    '    @app.get("/api/payments/checkout")' + NL +
    '    async def payment_checkout_link(request: Request, tier: str = "solo", add_on: str = ""):' + NL +
    '        """Generate a NOWPayments invoice link for the requested tier.' + NL +
    '        ' + NL +
    '        PATCH-426b: Also accepts X-API-Key=FOUNDER_API_KEY directly' + NL +
    '        (route is exempt from middleware, so we look up founder here).' + NL +
    '        """' + NL +
    '        import urllib.request, urllib.parse, json as _json' + NL +
    '        account = _account_or_founder(request)' + NL +
    '        ' + NL +
    '        # PATCH-426b: Fallback — direct X-API-Key check' + NL +
    '        if not account:' + NL +
    '            api_key_header = (' + NL +
    '                request.headers.get("X-API-Key")' + NL +
    '                or request.headers.get("x-api-key")' + NL +
    '                or ""' + NL +
    '            )' + NL +
    '            founder_key = os.environ.get("FOUNDER_API_KEY") or os.environ.get("MURPHY_API_KEY", "")' + NL +
    '            if api_key_header and founder_key and api_key_header == founder_key:' + NL +
    '                try:' + NL +
    '                    import sqlite3 as _sq' + NL +
    '                    _femail = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")' + NL +
    '                    _conn = _sq.connect("/opt/Murphy-System/murphy.db", timeout=2)' + NL +
    '                    _row = _conn.execute(' + NL +
    '                        "SELECT account_id, email FROM user_accounts WHERE email=? LIMIT 1",' + NL +
    '                        (_femail,)' + NL +
    '                    ).fetchone()' + NL +
    '                    _conn.close()' + NL +
    '                    if _row:' + NL +
    '                        account = {"account_id": _row[0], "email": _row[1], "role": "founder"}' + NL +
    '                except Exception:' + NL +
    '                    pass' + NL +
    '        ' + NL +
    '        if not account:' + NL +
    '            from fastapi import HTTPException as _HE' + NL +
    '            raise _HE(status_code=401, detail="Not authenticated")'
)

if OLD not in src:
    print("  ✗ OLD block not found verbatim — re-examining handler")
    # Show what the actual current text looks like
    import re
    m = re.search(r'@app\.get\("/api/payments/checkout"\).*?raise _HE\(status_code=401', src, re.DOTALL)
    if m:
        print(f"  Found similar block at {m.start()}..{m.end()}; length={m.end()-m.start()}")
        print("  First 400 chars:")
        print(m.group(0)[:400])
    raise SystemExit(1)

new_src = src.replace(OLD, NEW, 1)
ast.parse(new_src)
print("  ✓ AST parses")

backup = APP.with_suffix(".py.pre-426b")
shutil.copy(APP, backup)
APP.write_text(new_src)
print(f"  ✓ wrote {APP} (backup: {backup.name})")
