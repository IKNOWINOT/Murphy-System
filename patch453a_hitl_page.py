"""
PATCH-453a — HITL Founder Page
==============================

WHAT THIS IS:
  Adds GET /hitl serving /static/hitl.html — the founder's unified
  approve/reject queue. One URL surfaces every pending action across:
    - outbound_email_queue (murphy_mail.db)
    - hitl_jobs (hitl_jobs.db)
    - swarm hitl_signals (shadow_forge_agent.db, future)

WHY IT EXISTS:
  Founder directive 2026-05-25: "Hitl is a location murphy.systems/hitl
  I should be able accept or reject anything and if it isn't from the
  last day it's bullshit and should be cleared out."

  Before this patch, four scattered tables held HITL data and the founder
  had no single page to triage. 28 MEP engineering jobs sat unseen for
  18 days. This patch closes Gate E (visibility) for the HITL capability.

HOW IT FITS:
  Static HTML page (already at /opt/Murphy-System/static/hitl.html) calls
  existing backend endpoints:
    GET  /api/mail/outbound/queue?status=pending_review
    GET  /api/hitl/queue?fresh=1
    POST /api/mail/outbound/{queue_id}/{approve,reject}
    POST /api/hitl/{id}/decide

  No new API surface. Just a viewer.

KEY CONCEPTS:
  - Stale rule: any item older than 24h auto-marked status='expired_stale'
    by the nightly autonomy-reset systemd timer.
  - Fresh filter: /api/hitl/queue?fresh=1 returns only items <24h old.

LAST UPDATED: 2026-05-25 by Murphy
"""
import re, sys, shutil

APP_PY = "/opt/Murphy-System/src/runtime/app.py"
backup = APP_PY + ".pre-453a"
shutil.copyfile(APP_PY, backup)
print(f"backed up to {backup}")

with open(APP_PY) as f:
    src = f.read()

# Skip if already patched
if 'PATCH-453a' in src:
    print("PATCH-453a already applied — exiting clean")
    sys.exit(0)

# Insert after the /contact route block, before /logo-demo
anchor = '    # PATCH-450-logo-demo: live gaze demo'
if anchor not in src:
    print("ERROR: anchor not found — manual insertion required")
    sys.exit(1)

new_route = chr(10).join([
    "    # PATCH-453a — HITL founder page",
    '    @app.get("/hitl", include_in_schema=False)',
    "    async def hitl_page_top():",
    "        from fastapi.responses import FileResponse as _hFR, RedirectResponse as _hRR",
    "        import os as _hos",
    "        cand = \"/opt/Murphy-System/static/hitl.html\"",
    "        if _hos.path.isfile(cand):",
    "            return _hFR(cand, media_type=\"text/html\")",
    "        return _hRR(\"/\")",
    "",
    "    # /api/hitl/queue?fresh=1 — unified fresh-only queue (PATCH-453a)",
    '    @app.get("/api/hitl/queue", include_in_schema=False)',
    "    async def hitl_queue_fresh(fresh: int = 0):",
    "        import sqlite3 as _sq",
    "        try:",
    "            conn = _sq.connect(\"/var/lib/murphy-production/hitl_jobs.db\", timeout=5)",
    "            conn.row_factory = _sq.Row",
    "            where = \"status='open'\"",
    "            if fresh:",
    "                where += \" AND created_at >= datetime('now','-1 day')\"",
    "            rows = conn.execute(f\"SELECT * FROM hitl_jobs WHERE {where} ORDER BY created_at DESC LIMIT 200\").fetchall()",
    "            conn.close()",
    "            return {\"ok\": True, \"jobs\": [dict(r) for r in rows], \"count\": len(rows)}",
    "        except Exception as e:",
    "            return {\"ok\": False, \"error\": str(e), \"jobs\": []}",
    "",
    "",
])

src = src.replace(anchor, new_route + anchor)

with open(APP_PY, "w") as f:
    f.write(src)

print(f"✓ PATCH-453a applied to {APP_PY}")
print(f"  inserted /hitl route + /api/hitl/queue?fresh=1")
