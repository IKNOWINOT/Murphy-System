#!/usr/bin/env python3
"""
PATCH-419 — Money plumbing visibility + sales lens financing awareness
======================================================================

WHAT THIS IS:
  Three small, focused changes to make the existing financial subsystem
  visible to humans and to the swarm:

  1. Expose treasury via /api/treasury/* (the module is wired into the
     scheduler but has zero HTTP endpoints — the data is invisible)
  2. Remove the duplicate /api/grants router mount (lines 2242 + 2249)
  3. Teach the vp-sales lens that financing exists, so when it hits price
     resistance it checks /api/grants/programs before discounting

WHY IT EXISTS:
  Following the GitHub-first rule, audit revealed:
    - murphy_treasury.py: 882 lines, wired, scheduled, 60KB SQLite DB — no API
    - billing/grants/: 14 program files, router mounted, 43 programs live
    - role_cognitive_lenses.py: vp-sales lens has 5 heuristics, none about
      financing — agent will discount blindly instead of pivoting to BNPL/SBA/grant

HOW IT FITS:
  - Patches /opt/Murphy-System/src/runtime/app.py (treasury routes + dedup)
  - Patches /opt/Murphy-System/src/role_cognitive_lenses.py (vp-sales heuristic)

NO NEW MODULES. Just wiring + one heuristic.

LAST UPDATED: 2026-05-25 by PATCH-419
"""
import ast
import shutil
from pathlib import Path

NL = chr(10)

# ──────────────────────────────────────────────────────────────────────────
# Part 1: Add /api/treasury/* routes to monolith
# ──────────────────────────────────────────────────────────────────────────
MONO = Path("/opt/Murphy-System/src/runtime/app.py")
src = MONO.read_text()

if "PATCH-419" in src:
    print("  ⚠ PATCH-419 already in monolith — skipping treasury route injection")
else:
    TREASURY_ROUTES = [
        "",
        "    # ── PATCH-419: Treasury visibility (HTTP surface for murphy_treasury) ─",
        '    @app.get("/api/treasury/status")',
        "    async def _treasury_status(request: Request):",
        '        """Treasury snapshot: operations wallet, runway, upcoming bills. PATCH-419."""',
        "        try:",
        "            import sys as _sys",
        '            _sys.path.insert(0, "/opt/Murphy-System/src")',
        "            from murphy_treasury import get_treasury",
        "            t = get_treasury()",
        "            data = t.get_status() if hasattr(t, 'get_status') else {}",
        '            return JSONResponse({"ok": True, "treasury": data})',
        "        except Exception as e:",
        '            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)',
        "",
        '    @app.get("/api/treasury/wallet")',
        "    async def _treasury_wallet(request: Request):",
        '        """Operations wallet balance (the 50% cash split). PATCH-419."""',
        "        try:",
        "            import sys as _sys",
        '            _sys.path.insert(0, "/opt/Murphy-System/src")',
        "            from murphy_treasury import get_treasury",
        "            t = get_treasury()",
        "            bal = t.get_wallet_balance() if hasattr(t, 'get_wallet_balance') else None",
        '            return JSONResponse({"ok": True, "operations_wallet_usd": bal})',
        "        except Exception as e:",
        '            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)',
        "",
        '    @app.get("/api/treasury/llm-spend")',
        "    async def _treasury_llm_spend(request: Request):",
        '        """LLM cost ledger summary — daily + provider breakdown. PATCH-419."""',
        "        try:",
        "            import sqlite3 as _sqlite",
        '            db = "/var/lib/murphy-production/llm_cost_ledger.db"',
        "            conn = _sqlite.connect(db)",
        "            conn.row_factory = _sqlite.Row",
        "            cur = conn.cursor()",
        "            cur.execute(",
        '                "SELECT COUNT(*) AS calls, SUM(cost_usd) AS total_cost_usd, "',
        '                "MIN(ts) AS first_call, MAX(ts) AS last_call FROM calls"',
        "            )",
        "            summary = dict(cur.fetchone() or {})",
        "            cur.execute(",
        '                "SELECT provider, COUNT(*) AS calls, SUM(cost_usd) AS cost_usd "',
        '                "FROM calls GROUP BY provider ORDER BY calls DESC LIMIT 10"',
        "            )",
        "            by_provider = [dict(r) for r in cur.fetchall()]",
        "            cur.execute(",
        '                "SELECT date(ts) AS day, COUNT(*) AS calls, SUM(cost_usd) AS cost_usd "',
        '                "FROM calls GROUP BY day ORDER BY day DESC LIMIT 7"',
        "            )",
        "            by_day = [dict(r) for r in cur.fetchall()]",
        "            conn.close()",
        '            return JSONResponse({"ok": True, "summary": summary,',
        '                                 "by_provider": by_provider, "by_day": by_day})',
        "        except Exception as e:",
        '            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)',
        "",
        '    @app.get("/api/treasury/financing-options")',
        "    async def _treasury_financing_options(request: Request):",
        '        """Quick handle to financing programs — used by vp-sales lens. PATCH-419."""',
        "        try:",
        "            import sys as _sys",
        '            _sys.path.insert(0, "/opt/Murphy-System")',
        "            from src.billing.grants.api import router as _gr",
        "            # The router already serves /api/grants/programs — we just return a",
        "            # curated summary appropriate for sales-side use.",
        "            from src.billing.grants import federal_grants, federal_tax_credits",
        "            from src.billing.grants import sba_financing, pace_financing, espc",
        "            from src.billing.grants import green_banks, usda_programs, utility_programs",
        "            categories = {",
        '                "federal_grants": "Federal grants (DOE, EPA, IIJA, IRA)",',
        '                "federal_tax_credits": "Federal tax credits (179D, 48, 48C, 25C, 25D)",',
        '                "sba": "SBA 7(a) / 504 / Express loans",',
        '                "pace": "C-PACE financing (commercial property assessed)",',
        '                "espc": "Energy Service Performance Contracts",',
        '                "green_banks": "State green bank financing",',
        '                "usda": "USDA REAP for rural / agricultural",',
        '                "utility": "Utility rebate / incentive programs",',
        "            }",
        '            return JSONResponse({"ok": True,',
        '                                 "categories": categories,',
        '                                 "all_programs_url": "/api/grants/programs",',
        '                                 "guidance": "Before discounting, check matched programs '
        'for the prospect industry and location."})',
        "        except Exception as e:",
        '            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)',
        "",
    ]
    routes_block = NL.join(TREASURY_ROUTES)

    # Parse-test the block in isolation
    ast.parse("def _t(app):\n" + routes_block)

    # Inject just before the PATCH-418 lenses block (or before /api/rosetta/status
    # if 418 not present)
    anchor_candidates = [
        '# ── PATCH-418: Rosetta cognitive lenses',
        '@app.get("/api/rosetta/lenses")',
        '@app.get("/api/rosetta/status")',
    ]
    anchor = None
    for c in anchor_candidates:
        if c in src:
            anchor = c
            break
    if not anchor:
        print("  ✗ no anchor found")
        raise SystemExit(1)

    new_src = src.replace(anchor, routes_block + NL + "    " + anchor, 1)
    ast.parse(new_src)
    print(f"  ✓ /api/treasury/* routes injected (anchor: {anchor[:50]!r})")

    # ──────────────────────────────────────────────────────────────────────
    # Part 2: Dedup the double grants-router mount
    # ──────────────────────────────────────────────────────────────────────
    # The double mount is harmless but ugly. We look for the second
    # occurrence and comment it out.
    if new_src.count("app.include_router(_grants_router)") == 2:
        # Replace the second one with a comment
        first = new_src.index("app.include_router(_grants_router)")
        rest = new_src[first + 1:]
        second_rel = rest.index("app.include_router(_grants_router)")
        second_abs = first + 1 + second_rel
        new_src = (
            new_src[:second_abs]
            + "# PATCH-419: dedup (was double mount)  "
            + "# app.include_router(_grants_router)"
            + new_src[second_abs + len("app.include_router(_grants_router)"):]
        )
        ast.parse(new_src)
        print("  ✓ duplicate /api/grants mount removed")
    else:
        print(f"  ⚠ unexpected number of grants-router mounts: "
              f"{new_src.count('app.include_router(_grants_router)')}")

    backup = MONO.with_suffix(".py.pre-419")
    shutil.copy(MONO, backup)
    MONO.write_text(new_src)
    print(f"  ✓ wrote {MONO} ({len(src)} -> {len(new_src)} bytes, backup: {backup.name})")


# ──────────────────────────────────────────────────────────────────────────
# Part 3: Patch the vp-sales lens to know about financing
# ──────────────────────────────────────────────────────────────────────────
LENSES = Path("/opt/Murphy-System/src/role_cognitive_lenses.py")
lsrc = LENSES.read_text()

if "PATCH-419" in lsrc:
    print("  ⚠ PATCH-419 already in lenses — skipping")
else:
    # Find the vp-sales heuristics list and append the financing heuristic
    # The lens structure (from earlier deploy) puts heuristics as a list inside
    # ROLE_LENSES["vp-sales"]["heuristics"].
    target_marker = '"vp-sales":'
    if target_marker not in lsrc:
        print("  ✗ vp-sales key not found in lenses")
        raise SystemExit(1)

    # Find the heuristics list inside the vp-sales block.
    vp_start = lsrc.index(target_marker)
    # Find the next "heuristics": [ after vp_start
    h_start = lsrc.index('"heuristics":', vp_start)
    h_open = lsrc.index('[', h_start)
    # Walk forward to find the matching close bracket (heuristics is a list of strings)
    depth = 1
    i = h_open + 1
    while i < len(lsrc) and depth > 0:
        c = lsrc[i]
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
        i += 1
    h_close = i - 1  # the closing ]

    existing_block = lsrc[h_open:h_close + 1]
    # Find the last item: the last string literal before h_close
    # Easiest: insert our new item just before the close bracket
    new_heuristic = (
        '        "PATCH-419: If a prospect raises price as the objection, '
        "DO NOT discount blindly. First check /api/treasury/financing-options "
        "to see if a matching grant, tax credit, BNPL, SBA loan, or C-PACE "
        "instrument exists for their industry/location. Financing changes the "
        "monthly carrying cost; discounting permanently reduces margin and "
        "trains the customer to negotiate. Pivot to financing first; discount "
        "only as last resort with founder approval.\",\n    "
    )

    # Find position: just before h_close, after the last comma + newline
    # Walk back from h_close to find the last "
    j = h_close - 1
    while j > h_open and lsrc[j] in (' ', '\t', '\n', '\r', ','):
        j -= 1
    # j now points at the last character of the last item (probably ")
    # Insert a comma if needed then our new line
    insertion_point = j + 1
    head = lsrc[:insertion_point]
    tail = lsrc[insertion_point:]
    # Make sure there's a comma before our insertion
    if not head.rstrip().endswith(','):
        sep = ",\n        "
    else:
        sep = "\n        "
    new_lsrc = head + sep + new_heuristic.lstrip() + tail

    # Parse-check
    try:
        ast.parse(new_lsrc)
    except SyntaxError as e:
        print(f"  ✗ syntax error after heuristic injection: line {e.lineno}: {e.msg}")
        # Show context
        ls = new_lsrc.split("\n")
        for k in range(max(0, e.lineno - 3), min(len(ls), e.lineno + 2)):
            print(f"    {k+1}: {ls[k][:120]}")
        raise SystemExit(1)

    backup2 = LENSES.with_suffix(".py.pre-419")
    shutil.copy(LENSES, backup2)
    LENSES.write_text(new_lsrc)
    print(f"  ✓ vp-sales heuristic added (lenses: {len(lsrc)} -> {len(new_lsrc)} bytes)")

print()
print("✓ PATCH-419 staged. Now restart murphy-production to activate.")
