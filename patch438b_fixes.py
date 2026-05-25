"""
PATCH-438-B — Three fixes for PATCH-438
========================================
1. _check_mfgc_authority — read confidence from DB cycle_log (process-independent)
   instead of per-process get_mind().stats() which returns running=False on edge
2. GET /api/policy/autonomy — SELECT * so MFGC columns surface in API
3. POST /api/policy/autonomy — relax invariant to allow has_mfgc_authority path
"""
import ast
import shutil
from pathlib import Path

NL = chr(10)

# ─── Fix 1: rewrite _check_mfgc_authority to read DB, not get_mind() ──
print("▶ Fix 1: _check_mfgc_authority — DB-based confidence read")
P417 = Path("/opt/Murphy-System/src/patch417_outbound_queue.py")
src = P417.read_text()

old_helper = NL.join([
    "    # Read live Swarm Mind confidence",
    "    try:",
    "        import sys as _sys",
    "        if '/opt/Murphy-System' not in _sys.path:",
    "            _sys.path.insert(0, '/opt/Murphy-System')",
    "        from src.murphy_mind import get_mind as _get_mind",
    "        stats = _get_mind().stats()",
    "        mind_running = bool(stats.get('running', False))",
    "        mind_conf = float(stats.get('avg_confidence')",
    "                          or stats.get('confidence') or 0.0)",
    "        mind_cycle = int(stats.get('cycle') or stats.get('total_cycles') or 0)",
    "    except Exception as e:",
    "        return {'allowed': False, 'reason': f'mind_unreachable:{e}'}",
    "    if not mind_running:",
    "        return {'allowed': False, 'reason': 'mind_not_running',",
    "                'mind_confidence': mind_conf, 'required': required,",
    "                'phase': phase}",
])

new_helper = NL.join([
    "    # Read live Swarm Mind confidence FROM DB (process-independent — the",
    "    # per-process get_mind() returns running=False unless that process is",
    "    # the monolith. Confidence is persisted to cycle_log every ~10min.)",
    "    try:",
    "        import sqlite3 as _sq438",
    "        from datetime import datetime as _dt438, timezone as _tz438",
    "        _mc = _sq438.connect('/var/lib/murphy-production/murphy_mind.db')",
    "        # Average of last 10 cycles to smooth out single-cycle noise",
    "        avg_row = _mc.execute(",
    "            'SELECT AVG(confidence), MAX(cycle), MAX(timestamp) '",
    "            'FROM cycle_log WHERE cycle > (SELECT MAX(cycle)-10 FROM cycle_log)'",
    "        ).fetchone()",
    "        _mc.close()",
    "        mind_conf  = float(avg_row[0] or 0.0)",
    "        mind_cycle = int(avg_row[1] or 0)",
    "        # Staleness check — confidence is only fresh if last cycle was < 30min ago",
    "        if avg_row[2]:",
    "            last_ts = _dt438.fromisoformat(avg_row[2].replace('Z', '+00:00'))",
    "            staleness_s = (_dt438.now(_tz438.utc) - last_ts).total_seconds()",
    "        else:",
    "            staleness_s = 99999",
    "        mind_running = staleness_s < 1800  # 30 minutes",
    "    except Exception as e:",
    "        return {'allowed': False, 'reason': f'mind_db_error:{e}'}",
    "    if not mind_running:",
    "        return {'allowed': False, 'reason': 'mind_stale',",
    "                'mind_confidence': mind_conf, 'required': required,",
    "                'phase': phase, 'staleness_s': staleness_s}",
])

if old_helper in src:
    src = src.replace(old_helper, new_helper, 1)
    ast.parse(src)
    shutil.copy(P417, P417.with_suffix(".py.pre-438b"))
    P417.write_text(src)
    print("  ✓ patch417 helper rewritten to read cycle_log DB")
else:
    print("  ✗ couldn't find old helper anchor")
    raise SystemExit(1)

# ─── Fix 2 + 3: patch434_routes.py ─────────────────────────────────
print()
print("▶ Fix 2: GET /api/policy/autonomy — SELECT all columns")
print("▶ Fix 3: POST invariant — relax to audit_gate OR mfgc_authority")
P434 = Path("/opt/Murphy-System/src/patch434_routes.py")
src = P434.read_text()

if "PATCH-438" in src:
    print("  ⚠ patch434 already has PATCH-438 marker")
else:
    # Fix 2 — the SELECT in the GET endpoint
    # Need to find the exact SQL — read the file
    import re
    select_match = re.search(
        r'(SELECT\s+role,\s+action_type,\s+has_audit_gate,\s+master_enabled,\s*\n[^\n]*\n[^\n]*\n[^\n]*FROM agent_action_policy)',
        src
    )
    if select_match:
        old_select = select_match.group(1)
        # Just replace with SELECT *
        new_select = "SELECT * FROM agent_action_policy"
        src = src.replace(old_select, new_select, 1)
        print(f"  ✓ Fix 2 applied")
    else:
        print(f"  ⚠ Fix 2: couldn't match SELECT regex, trying simpler approach")
        # Try the simpler form: grep for "SELECT role" line
        lines = src.split(NL)
        for i, ln in enumerate(lines):
            if "SELECT role, action_type, has_audit_gate" in ln:
                # Replace this and forward lines until we hit FROM
                start = i
                end = i
                for j in range(i, min(i+10, len(lines))):
                    if "FROM agent_action_policy" in lines[j]:
                        end = j
                        break
                # Build replacement preserving leading whitespace
                indent = len(ln) - len(ln.lstrip())
                lines[start:end+1] = [' ' * indent + 'SELECT * FROM agent_action_policy ORDER BY role, action_type']
                src = NL.join(lines)
                print(f"  ✓ Fix 2 applied (line-based)")
                break

    # Fix 3 — the invariant
    old_inv = NL.join([
        '    if new_master_int == 1 and not current["has_audit_gate"]:',
        '        conn.close()',
        '        raise HTTPException(',
        '            status_code=400,',
        '            detail=f"Cannot enable autonomy for {action_type} — no audit gate. Locked at master_enabled=0 by invariant."',
        '        )',
    ])
    new_inv = NL.join([
        '    # PATCH-438-B: relaxed — allow audit_gate OR mfgc_authority',
        '    has_audit = bool(current.get("has_audit_gate", 0))',
        '    has_mfgc  = bool(current.get("has_mfgc_authority", 0))',
        '    if new_master_int == 1 and not (has_audit or has_mfgc):',
        '        conn.close()',
        '        raise HTTPException(',
        '            status_code=400,',
        '            detail=f"Cannot enable autonomy for {action_type} — no audit gate "',
        '                   "AND no MFGC authority. Locked at master_enabled=0 by invariant."',
        '        )',
    ])
    if old_inv in src:
        src = src.replace(old_inv, new_inv, 1)
        print("  ✓ Fix 3 applied — invariant relaxed")
    else:
        print("  ✗ Fix 3: couldn't find invariant anchor")

    ast.parse(src)
    shutil.copy(P434, P434.with_suffix(".py.pre-438b"))
    P434.write_text(src)
    print(f"  ✓ patch434_routes.py written ({len(src)} bytes)")
