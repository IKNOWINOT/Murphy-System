"""
PATCH-427-A — Fix /api/roi-calendar/live and /summary 500 errors

Root cause: _roi_db_list() returns the JSON payload only. 151 of 166 rows
have payloads missing 'event_id' (stored in SQL column, not JSON). 108
of 166 rows also lack 'human_cost_estimate', 'agent_compute_cost', etc.

Fix: make _roi_db_list() splice event_id back from the SQL row, and
defensively default any missing numeric/string keys. Also fix summary
endpoint to use .get() everywhere.

LAST UPDATED: 2026-05-25 by PATCH-427-A
"""
import ast
import shutil
from pathlib import Path

NL = chr(10)

APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()

if "PATCH-427-A" in src:
    print("  ⚠ PATCH-427-A already applied — skipping")
    raise SystemExit(0)

# ─── Fix 1: _roi_db_list — splice event_id + provide defaults ─────────
old_list_fn = (
    '    def _roi_db_list():' + NL +
    '        con = _sqlite3_roi.connect(_ROI_DB_PATH)' + NL +
    '        rows = con.execute("SELECT data FROM roi_events ORDER BY updated_at ASC").fetchall()' + NL +
    '        con.close()' + NL +
    '        return [_json_roi_db.loads(r[0]) for r in rows]'
)
new_list_fn = (
    '    def _roi_db_list():' + NL +
    '        # PATCH-427-A: splice event_id from SQL row + default missing keys' + NL +
    '        con = _sqlite3_roi.connect(_ROI_DB_PATH)' + NL +
    '        rows = con.execute("SELECT event_id, data FROM roi_events ORDER BY updated_at ASC").fetchall()' + NL +
    '        con.close()' + NL +
    '        out = []' + NL +
    '        for eid, dat in rows:' + NL +
    '            try:' + NL +
    '                d = _json_roi_db.loads(dat)' + NL +
    '            except Exception:' + NL +
    '                continue' + NL +
    '            d.setdefault("event_id", eid)' + NL +
    '            d.setdefault("human_cost_estimate", 0.0)' + NL +
    '            d.setdefault("agent_compute_cost", 0.0)' + NL +
    '            d.setdefault("overhead_cost", 0.0)' + NL +
    '            d.setdefault("status", "unknown")' + NL +
    '            d.setdefault("task_type", "other")' + NL +
    '            out.append(d)' + NL +
    '        return out'
)
if old_list_fn not in src:
    print("  ✗ couldn't find _roi_db_list anchor")
    raise SystemExit(1)
src = src.replace(old_list_fn, new_list_fn, 1)
print("  ✓ patched _roi_db_list")

# ─── Fix 2: summary endpoint — use .get() everywhere ─────────────────
old_sum = (
    '        total_human = sum(e["human_cost_estimate"] for e in events)' + NL +
    '        total_agent = sum(e["agent_compute_cost"] for e in events)' + NL +
    '        total_overhead = sum(e["overhead_cost"] for e in events)' + NL +
    '        total_roi = total_human - total_agent - total_overhead'
)
new_sum = (
    '        # PATCH-427-A: defensive .get() — many rows lack these keys' + NL +
    '        total_human = sum(float(e.get("human_cost_estimate", 0) or 0) for e in events)' + NL +
    '        total_agent = sum(float(e.get("agent_compute_cost", 0) or 0) for e in events)' + NL +
    '        total_overhead = sum(float(e.get("overhead_cost", 0) or 0) for e in events)' + NL +
    '        total_roi = total_human - total_agent - total_overhead'
)
if old_sum in src:
    src = src.replace(old_sum, new_sum, 1)
    print("  ✓ patched summary cost sums")
else:
    print("  ⚠ summary cost sums anchor not found")

# Also fix the active_tasks/completed_tasks counters
old_counters = (
    '            "active_tasks": sum(1 for e in events if e["status"] in ("running", "qc", "hitl_review")),' + NL +
    '            "completed_tasks": sum(1 for e in events if e["status"] == "complete"),'
)
new_counters = (
    '            "active_tasks": sum(1 for e in events if e.get("status") in ("running", "qc", "hitl_review")),' + NL +
    '            "completed_tasks": sum(1 for e in events if e.get("status") == "complete"),'
)
if old_counters in src:
    src = src.replace(old_counters, new_counters, 1)
    print("  ✓ patched summary counters")

# Validate + write
ast.parse(src)
shutil.copy(APP, APP.with_suffix(".py.pre-427a"))
APP.write_text(src)
print(f"  ✓ wrote app.py ({len(src)} bytes)")
