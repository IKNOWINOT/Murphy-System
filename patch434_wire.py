"""PATCH-434 Part 2 — wire routes into app.py + exempt /api/policy/ from auth."""
import ast, shutil
from pathlib import Path

NL = chr(10)

# ─── Wire into app.py ────────────────────────────────────────────────────
APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()
if "PATCH-434" in src:
    print("  ⚠ app.py already has PATCH-434 marker — skipping wire")
else:
    anchor = "    return app" + NL
    last = src.rfind(anchor)
    if last < 0:
        print("  ✗ couldn't find 'return app' — aborting")
        raise SystemExit(1)
    wire = (
        "    # ── PATCH-434: Customer-facing autonomy policy routes ──" + NL +
        "    try:" + NL +
        "        import sys as _sys434" + NL +
        "        _sys434.path.insert(0, '/opt/Murphy-System')" + NL +
        "        from src.patch434_routes import init_policy_routes as _ipr" + NL +
        "        _ipr(app)" + NL +
        "    except Exception as _e434:" + NL +
        "        import logging as _log434" + NL +
        "        _log434.getLogger(__name__).warning(f'PATCH-434 routes failed: {_e434}')" + NL +
        "" + NL
    )
    new = src[:last] + wire + src[last:]
    ast.parse(new)
    shutil.copy(APP, APP.with_suffix(".py.pre-434"))
    APP.write_text(new)
    print("  ✓ app.py wired")

# ─── Make /api/policy/ exempt ────────────────────────────────────────────
AM = Path("/opt/Murphy-System/src/auth_middleware.py")
am = AM.read_text()
if "PATCH-434" in am:
    print("  ⚠ auth_middleware.py already has PATCH-434 marker — skipping")
else:
    OLD_A = '    "/api/billing/checkout",' + NL + '    # PATCH-426'
    NEW_A = ('    "/api/billing/checkout",' + NL +
             '    # PATCH-434: policy routes (GET public, POST founder-only)' + NL +
             '    "/api/policy/",' + NL +
             '    # PATCH-426')
    OLD_B = '        "/api/billing/checkout",' + NL + '        # PATCH-426'
    NEW_B = ('        "/api/billing/checkout",' + NL +
             '        # PATCH-434: policy routes' + NL +
             '        "/api/policy/",' + NL +
             '        # PATCH-426')
    new = am
    patched = 0
    if OLD_A in new:
        new = new.replace(OLD_A, NEW_A, 1)
        patched += 1
    if OLD_B in new:
        new = new.replace(OLD_B, NEW_B, 1)
        patched += 1
    if patched == 2:
        ast.parse(new)
        shutil.copy(AM, AM.with_suffix(".py.pre-434"))
        AM.write_text(new)
        print(f"  ✓ auth_middleware.py patched ({patched} allowlists)")
    else:
        print(f"  ✗ only patched {patched}/2 allowlists — check anchors")

print("  ✓ Part 2 complete")
