#!/usr/bin/env python3
"""
PATCH-426 — Make NOWPayments routes publicly reachable
========================================================
(See header in v1 for full context — only difference here is the
patch must update BOTH allowlists in auth_middleware.py:
  - Line ~101: _EXEMPT_PREFIXES tuple
  - Line ~572: a second allowlist used in a different code path
Both need /api/payments/ added.)
"""
import ast
import shutil
from pathlib import Path

APP = Path("/opt/Murphy-System/src/auth_middleware.py")
src = APP.read_text()
NL = chr(10)

if "PATCH-426" in src:
    print("  ⚠ PATCH-426 marker already in file — skipping")
    raise SystemExit(0)

# Insert AFTER each /api/billing/checkout occurrence
# Both lines have different indentation, so handle them separately
PATCH_HEADER_INLINE = "    # PATCH-426: NOWPayments public routes"

# First occurrence — 4-space indent
OLD_A = (
    '    "/api/billing/currencies",' + NL +
    '    "/api/billing/checkout",' + NL +
    '    # PATCH-097: Foundation modules'
)
NEW_A = (
    '    "/api/billing/currencies",' + NL +
    '    "/api/billing/checkout",' + NL +
    '    # PATCH-426: NOWPayments — webhook has HMAC-SHA512 verification,' + NL +
    '    # checkout is a public pricing-page action (mirrors Stripe pattern)' + NL +
    '    "/api/payments/",' + NL +
    '    "/api/payments",' + NL +
    '    # PATCH-097: Foundation modules'
)

# Second occurrence — 8-space indent
OLD_B = (
    '        "/api/billing/currencies",' + NL +
    '        "/api/billing/checkout",' + NL +
    '        # PATCH-065: Public API'
)
NEW_B = (
    '        "/api/billing/currencies",' + NL +
    '        "/api/billing/checkout",' + NL +
    '        # PATCH-426: NOWPayments public routes (HMAC + pricing-page)' + NL +
    '        "/api/payments/",' + NL +
    '        "/api/payments",' + NL +
    '        # PATCH-065: Public API'
)

errors = []
new_src = src
if OLD_A in new_src:
    new_src = new_src.replace(OLD_A, NEW_A, 1)
    print("  ✓ patched 1st allowlist (4-space)")
else:
    errors.append("OLD_A block not found")

if OLD_B in new_src:
    new_src = new_src.replace(OLD_B, NEW_B, 1)
    print("  ✓ patched 2nd allowlist (8-space)")
else:
    errors.append("OLD_B block not found")

if errors:
    print(f"  ✗ Errors: {errors}")
    raise SystemExit(1)

# Validate
ast.parse(new_src)
print("  ✓ AST parses")

backup = APP.with_suffix(".py.pre-426")
shutil.copy(APP, backup)
APP.write_text(new_src)
print(f"  ✓ wrote {APP} (backup: {backup.name})")
