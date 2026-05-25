"""
PATCH-453p (pre): Endpoint discovery — walks source code to build the
authoritative route inventory. Re-run anytime endpoints feel uncertain.

Usage:
  cd /opt/Murphy-System && python3 scripts/dump_routes.py
  # Output: /tmp/murphy_routes.json

Why: My memory of route names was wrong in 4 places (capital/proposals,
mail/outbound/review, mail/outbound/approve shape, phone/dial mount).
This script removes the guesswork.
"""
import re, json, os

ROOT = "src"
SKIP_PATTERNS = (".bak", ".pre-")

routes = []
pattern_app = re.compile(r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', re.IGNORECASE)
pattern_prefix = re.compile(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']')
pattern_router = re.compile(r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', re.IGNORECASE)

# Walk every .py file under src/
for root, _, files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"): continue
        if any(s in fn for s in SKIP_PATTERNS): continue
        if any(s in root for s in SKIP_PATTERNS): continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        # Inline @app routes (only main app.py)
        if fp == "src/runtime/app.py":
            for line_idx, line in enumerate(content.split("\n"), 1):
                m = pattern_app.search(line)
                if m:
                    routes.append({"method": m.group(1).upper(), "path": m.group(2),
                                   "source": fp, "line": line_idx, "router": "inline"})
        # APIRouter modules
        if "APIRouter(" in content:
            pm = pattern_prefix.search(content)
            prefix = pm.group(1) if pm else ""
            for line_idx, line in enumerate(content.split("\n"), 1):
                rm = pattern_router.search(line)
                if rm:
                    sub = rm.group(2)
                    full = prefix + sub if sub.startswith("/") else (prefix + "/" + sub if prefix else sub)
                    routes.append({"method": rm.group(1).upper(), "path": full,
                                   "source": fp, "line": line_idx, "router": prefix or "(no prefix)"})

# Dedupe and sort
seen = set(); unique = []
for r in routes:
    key = (r["method"], r["path"])
    if key in seen: continue
    seen.add(key); unique.append(r)
unique.sort(key=lambda r: (r["path"], r["method"]))

# Group by top-level
from collections import defaultdict
groups = defaultdict(list)
for r in unique:
    p = r["path"]
    if p.startswith("/api/"):
        parts = p.split("/")
        top = "/api/" + parts[2] if len(parts) > 2 else "/api"
        if len(parts) > 3 and parts[2] in ("platform", "swarm"):
            top = "/api/" + parts[2] + "/" + parts[3]
    else:
        top = "(other)"
    groups[top].append(r)

with open("/tmp/murphy_routes.json", "w") as f:
    json.dump({"total": len(unique), "groups": dict(sorted(groups.items()))}, f, indent=2)

print(f"✓ {len(unique)} unique routes across {len(groups)} prefixes")
print(f"  Inventory: /tmp/murphy_routes.json")
