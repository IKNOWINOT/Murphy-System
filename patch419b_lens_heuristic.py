#!/usr/bin/env python3
"""
PATCH-419b — Add financing heuristic to vp-sales lens (the part that failed
in 419a). Done as targeted string surgery instead of bracket-walking.
"""
import ast
import shutil
from pathlib import Path

LENSES = Path("/opt/Murphy-System/src/role_cognitive_lenses.py")
src = LENSES.read_text()

if "PATCH-419" in src:
    print("  ⚠ already present, skipping")
    raise SystemExit(0)

# Find the last existing heuristic in vp-sales by signature
needle = '"Always end with one specific yes/no question, never an open one"'
if needle not in src:
    print(f"  ✗ anchor not found: {needle[:60]}")
    raise SystemExit(1)

# Replace it with itself + comma + the new heuristic
new_heuristic = (
    needle + ',\n'
    '            "PATCH-419: If a prospect raises price as the objection, '
    'DO NOT discount blindly. First call /api/treasury/financing-options '
    'and /api/grants/programs to see whether matching grants, tax credits, '
    'C-PACE, SBA, USDA REAP, BNPL, or utility rebates can reduce the '
    'customer\'s effective monthly carrying cost. Financing changes the '
    'payment shape; discounting permanently reduces margin and trains the '
    'customer to negotiate. Pivot to financing first; discount only as '
    'last resort with founder approval."'
)

new_src = src.replace(needle, new_heuristic, 1)

try:
    ast.parse(new_src)
    print("  ✓ AST parses")
except SyntaxError as e:
    ls = new_src.split("\n")
    print(f"  ✗ syntax error line {e.lineno}: {e.msg}")
    for k in range(max(0, e.lineno - 3), min(len(ls), e.lineno + 2)):
        print(f"    {k+1}: {ls[k][:120]}")
    raise SystemExit(1)

# Smoke test import
import sys
sys.path.insert(0, "/opt/Murphy-System/src")
backup = LENSES.with_suffix(".py.pre-419b")
shutil.copy(LENSES, backup)
LENSES.write_text(new_src)
print(f"  ✓ wrote {LENSES} (backup: {backup})")

# Reload and validate
if "role_cognitive_lenses" in sys.modules:
    del sys.modules["role_cognitive_lenses"]
import role_cognitive_lenses as rcl
vp = rcl.get_lens("vp-sales")
heuristics = vp.get("heuristics", [])
print(f"  ✓ vp-sales now has {len(heuristics)} heuristics")
financing = [h for h in heuristics if "PATCH-419" in h or "financing-options" in h]
if financing:
    print(f"  ✓ financing heuristic present: {financing[0][:100]}...")
else:
    print(f"  ⚠ financing heuristic not detected in list")
