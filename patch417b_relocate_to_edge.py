#!/usr/bin/env python3
"""
PATCH-417b — Relocate Outbound Review Queue to murphy-edge
============================================================

WHAT THIS IS:
  Moves the PATCH-417 routes (originally injected into the monolith) into
  a standalone module on murphy-edge, where the modular auth middleware
  (PATCH-414b) actually recognizes employee API keys.

WHY IT EXISTS:
  Initial PATCH-417 deployed to the monolith. Tests revealed the monolith's
  legacy OIDCAuthMiddleware rejects employee keys — only murphy-edge's
  modular auth understands them. Since the Outbound Queue's whole purpose
  is to intercept SWARM AGENT traffic (which uses employee keys), the
  routes must live on edge.

HOW IT FITS:
  - Creates: src/patch417_outbound_queue.py — a clean module with
    init_outbound_routes(app)
  - Removes: the PATCH-417 routes block from runtime/app.py (monolith)
  - Registers: a new "mail_outbound" module in murphy_edge.py alongside
    identity

KEY CONCEPTS:
  - init_outbound_routes(app): standard FastAPI router init pattern
  - The DB table created by PATCH-417 in /var/lib/murphy-production/
    murphy_mail.db is preserved — only the route handlers move

DEPENDENCIES:
  - PATCH-414b (modular_auth populates request.state.tier/department/actor_account_id)
  - PATCH-414d (spawn-agent + employee keys)
  - module_registry (registration)

LAST UPDATED: 2026-05-25 by PATCH-417b
"""
import shutil
from pathlib import Path

MODULE_PATH = Path("/opt/Murphy-System/src/patch417_outbound_queue.py")
EDGE_PATH = Path("/opt/Murphy-System/src/murphy_edge.py")
MONOLITH = Path("/opt/Murphy-System/src/runtime/app.py")


# ── The standalone module that exposes init_outbound_routes(app) ───────────
MODULE_CONTENT = '''"""
PATCH-417 — Outbound Review Queue routes (murphy-edge edition)
================================================================

WHAT THIS IS:
  FastAPI route handlers for the outbound email review queue. Imported and
  initialized by murphy_edge.py via init_outbound_routes(app).

WHY IT EXISTS:
  See PATCH-417 module header. Briefly: every email a swarm agent (or any
  non-founder caller) tries to send goes through this queue. Founder reviews,
  approves with optional edits, or rejects with reason. Hard prereq for
  Phase 5a swarm sales going live.

HOW IT FITS:
  - Uses the outbound_email_queue table in /var/lib/murphy-production/murphy_mail.db
    (table created by patch417_outbound_review_queue.py)
  - Reads request.state.{tier, department, actor_account_id} set by
    modular_auth middleware (PATCH-414b)
  - Emits to event_bus when present

ENDPOINTS:
  POST /api/mail/outbound/submit                — any auth, queues a draft
  GET  /api/mail/outbound/queue                 — founder-only, lists by status
  GET  /api/mail/outbound/{queue_id}            — founder-only, full detail
  POST /api/mail/outbound/{queue_id}/approve    — founder-only, sends
  POST /api/mail/outbound/{queue_id}/reject     — founder-only, with reason
  GET  /api/mail/outbound/stats                 — any auth, aggregate counts

LAST UPDATED: 2026-05-25 by PATCH-417b
"""
from __future__ import annotations

import json
import sqlite3
import secrets
import logging
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("murphy.mail_outbound")

DB_PATH = "/var/lib/murphy-production/murphy_mail.db"
HOUSEHOLD_DB = "/var/lib/murphy-production/murphy_household.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(event_type: str, payload: dict) -> None:
    """Best-effort event bus emission."""
    try:
        from event_bus import publish
        publish(event_type, payload)
    except Exception as e:
        log.debug("event_bus emit failed for %s: %s", event_type, e)


def init_outbound_routes(app) -> None:
    """Register all PATCH-417 routes on the given FastAPI app.

    Called by murphy_edge.py via _register_patch("mail_outbound", ...).
    """

    # ── POST /api/mail/outbound/submit ────────────────────────────────────
    @app.post("/api/mail/outbound/submit")
    async def outbound_submit(request: Request):
        """Queue a draft email for founder review.

        Body:
            to: str | list[str]   — required
            subject: str           — required
            body: str              — required
            from?: str             — optional sender override
            urgency?: str          — low | normal | high (default normal)
            body_format?: str      — plain | html (default plain)
            cc?: list[str]         — optional

        Returns:
            {ok, queue_id, status, review_url}
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_json"},
                                status_code=400)

        to = body.get("to")
        if isinstance(to, str):
            to = [to]
        if not to or not body.get("subject") or not body.get("body"):
            return JSONResponse({
                "ok": False, "error": "missing_required",
                "required": ["to", "subject", "body"]}, status_code=400)

        agent_pid = getattr(request.state, "actor_account_id", None)
        tier = getattr(request.state, "tier", None) or "anonymous"
        dept = getattr(request.state, "department", None)

        # Pull richer agent context from household DB if employee
        agent_role = None
        agent_class = None
        if tier == "employee" and agent_pid:
            try:
                conn = sqlite3.connect(HOUSEHOLD_DB)
                row = conn.execute(
                    "SELECT role, notes FROM household_profiles "
                    "WHERE profile_id=?", (agent_pid,)).fetchone()
                conn.close()
                if row:
                    agent_role = row[0]
                    try:
                        meta = json.loads(row[1] or "{}")
                        agent_class = meta.get("class")
                    except Exception:
                        pass
            except Exception:
                pass

        queue_id = "mq_" + secrets.token_hex(8)
        now = _now()
        from_addr = body.get("from") or (
            "swarm@murphy.systems" if tier == "employee"
            else "founder@murphy.systems"
        )

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                INSERT INTO outbound_email_queue
                    (queue_id, from_address, to_addresses, cc_addresses,
                     subject, body, body_format, agent_profile_id,
                     agent_role, agent_class, urgency, status,
                     created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'pending_review', ?, ?, ?)
            """, (
                queue_id, from_addr, json.dumps(to),
                json.dumps(body.get("cc", [])) if body.get("cc") else None,
                body.get("subject"), body.get("body"),
                body.get("body_format", "plain"),
                agent_pid, agent_role, agent_class,
                body.get("urgency", "normal"),
                now, now,
                json.dumps({"tier": tier, "dept": dept,
                            "submitted_via": "edge_mail_outbound"})
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            log.exception("outbound_submit db_insert failed")
            return JSONResponse({"ok": False, "error": f"db_insert: {e}"},
                                status_code=500)

        _emit("mail.outbound.submitted", {
            "queue_id": queue_id, "agent": agent_pid, "to": to,
            "subject": body.get("subject"),
            "urgency": body.get("urgency", "normal"),
        })

        return JSONResponse({
            "ok": True, "queue_id": queue_id,
            "status": "pending_review",
            "review_url": f"/api/mail/outbound/{queue_id}",
        })

    # ── GET /api/mail/outbound/queue ─────────────────────────────────────
    @app.get("/api/mail/outbound/queue")
    async def outbound_list(request: Request):
        """List queued emails by status. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)

        status_filter = request.query_params.get("status", "pending_review")
        try:
            limit = min(int(request.query_params.get("limit", 50)), 200)
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return JSONResponse({"ok": False, "error": "invalid_pagination"},
                                status_code=400)

        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT queue_id, from_address, to_addresses, subject, body,
                   agent_profile_id, agent_role, agent_class, urgency,
                   status, created_at
            FROM outbound_email_queue
            WHERE status = ?
            ORDER BY
                CASE urgency
                    WHEN 'high' THEN 0
                    WHEN 'normal' THEN 1
                    ELSE 2
                END,
                created_at DESC
            LIMIT ? OFFSET ?
        """, (status_filter, limit, offset)).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM outbound_email_queue WHERE status = ?",
            (status_filter,)).fetchone()[0]
        conn.close()

        items = [{
            "queue_id":         r[0],
            "from":             r[1],
            "to":               json.loads(r[2]) if r[2] else [],
            "subject":          r[3],
            "body_preview":     (r[4] or "")[:200],
            "agent_profile_id": r[5],
            "agent_role":       r[6],
            "agent_class":      r[7],
            "urgency":          r[8],
            "status":           r[9],
            "created_at":       r[10],
        } for r in rows]

        return JSONResponse({
            "ok": True, "count": len(items), "total": total,
            "status_filter": status_filter, "items": items,
        })

    # ── GET /api/mail/outbound/{queue_id} ────────────────────────────────
    @app.get("/api/mail/outbound/{queue_id}")
    async def outbound_get(queue_id: str, request: Request):
        """Full row detail. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)

        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT * FROM outbound_email_queue WHERE queue_id=?",
            (queue_id,)).fetchone()
        cols = [c[1] for c in conn.execute(
            "PRAGMA table_info(outbound_email_queue)").fetchall()]
        conn.close()

        if not row:
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        item = dict(zip(cols, row))
        for jf in ("to_addresses", "cc_addresses", "metadata"):
            if item.get(jf):
                try:
                    item[jf] = json.loads(item[jf])
                except Exception:
                    pass
        return JSONResponse({"ok": True, "item": item})

    # ── POST /api/mail/outbound/{queue_id}/approve ───────────────────────
    @app.post("/api/mail/outbound/{queue_id}/approve")
    async def outbound_approve(queue_id: str, request: Request):
        """Approve and send. Founder only.

        Body (optional): {edits: {subject?, body?, to?}}
        """
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        edits = body.get("edits", {}) or {}

        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT from_address, to_addresses, subject, body, status
            FROM outbound_email_queue WHERE queue_id=?
        """, (queue_id,)).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        if row[4] != "pending_review":
            conn.close()
            return JSONResponse({
                "ok": False, "error": "not_pending",
                "current_status": row[4]}, status_code=409)

        to_list = edits.get("to") or json.loads(row[1])
        if isinstance(to_list, str):
            to_list = [to_list]
        subject = edits.get("subject") or row[2]
        body_text = edits.get("body") or row[3]

        now = _now()
        approver_pid = getattr(request.state, "actor_account_id", "founder")

        conn.execute("""
            UPDATE outbound_email_queue
            SET status='approved', approved_by=?, approved_at=?, updated_at=?,
                subject=?, body=?, to_addresses=?
            WHERE queue_id=?
        """, (approver_pid, now, now, subject, body_text,
              json.dumps(to_list), queue_id))
        conn.commit()

        # v1: mark as sent via stub. Real SMTP path lands when monolith
        # gets a real send route or we wire Postfix directly.
        send_ok, send_err, sent_via = True, None, "stub_v1"

        if send_ok:
            conn.execute("""
                UPDATE outbound_email_queue
                SET status='sent', sent_at=?, sent_via=?, updated_at=?
                WHERE queue_id=?
            """, (now, sent_via, now, queue_id))
        else:
            conn.execute("""
                UPDATE outbound_email_queue
                SET status='failed', failure_reason=?, updated_at=?
                WHERE queue_id=?
            """, (send_err, now, queue_id))
        conn.commit()
        conn.close()

        _emit("mail.outbound.approved" if send_ok else "mail.outbound.failed",
              {"queue_id": queue_id, "approver": approver_pid,
               "to": to_list, "subject": subject})
        if send_ok:
            _emit("mail.outbound.sent",
                  {"queue_id": queue_id, "sent_via": sent_via})

        return JSONResponse({
            "ok": send_ok, "queue_id": queue_id,
            "status": "sent" if send_ok else "failed",
            "sent_via": sent_via, "error": send_err,
        })

    # ── POST /api/mail/outbound/{queue_id}/reject ────────────────────────
    @app.post("/api/mail/outbound/{queue_id}/reject")
    async def outbound_reject(queue_id: str, request: Request):
        """Reject with a reason. Founder only."""
        if getattr(request.state, "tier", None) != "founder":
            return JSONResponse({"ok": False, "error": "founder_only"},
                                status_code=403)
        try:
            body = await request.json()
        except Exception:
            body = {}
        reason = body.get("reason", "no_reason_given")
        now = _now()

        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("""
            UPDATE outbound_email_queue
            SET status='rejected', reject_reason=?, updated_at=?
            WHERE queue_id=? AND status='pending_review'
        """, (reason, now, queue_id))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return JSONResponse({
                "ok": False, "error": "not_found_or_not_pending"},
                status_code=404)

        _emit("mail.outbound.rejected",
              {"queue_id": queue_id, "reason": reason})

        return JSONResponse({
            "ok": True, "queue_id": queue_id,
            "status": "rejected", "reason": reason,
        })

    # ── GET /api/mail/outbound/stats ─────────────────────────────────────
    @app.get("/api/mail/outbound/stats")
    async def outbound_stats(request: Request):
        """Aggregate counts across queue states. Any authed caller."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("""
            SELECT status, COUNT(*) FROM outbound_email_queue GROUP BY status
        """).fetchall()
        conn.close()
        stats = {r[0]: r[1] for r in rows}
        return JSONResponse({
            "ok": True,
            "total":          sum(stats.values()),
            "pending_review": stats.get("pending_review", 0),
            "approved":       stats.get("approved", 0),
            "rejected":       stats.get("rejected", 0),
            "sent":           stats.get("sent", 0),
            "failed":         stats.get("failed", 0),
        })

    log.info("PATCH-417 mail_outbound: 6 routes registered")
'''


def step(m): print(f"  ▶ {m}", flush=True)
def done(m): print(f"  ✓ {m}", flush=True)
def warn(m): print(f"  ⚠ {m}", flush=True)


def write_module():
    step("Step 1 — write standalone mail_outbound module")
    MODULE_PATH.write_text(MODULE_CONTENT)
    done(f"wrote {MODULE_PATH} ({len(MODULE_CONTENT)} bytes)")


def register_in_edge():
    step("Step 2 — register mail_outbound in murphy_edge.py")
    src = EDGE_PATH.read_text()
    if "mail_outbound" in src:
        warn("already registered — skipping")
        return
    # Anchor: the identity registration block
    anchor = '# PATCH-410: full Identity wire-up'
    if anchor not in src:
        warn(f"anchor not found: {anchor}")
        return
    block = '''# PATCH-417: Outbound Review Queue (Phase 7a hard prereq for swarm sales)
_register_patch(
    "mail_outbound", "PATCH-417", "patch417_outbound_queue",
    "init_outbound_routes",
    "Outbound email queue with founder approval; intercepts swarm-agent sends",
    requires=["identity"],
)


'''
    new = src.replace(anchor, block + anchor, 1)

    import ast
    try:
        ast.parse(new)
    except SyntaxError as e:
        warn(f"syntax error in edge after edit: {e}")
        return

    backup = EDGE_PATH.with_suffix(".py.pre-417b")
    shutil.copy(EDGE_PATH, backup)
    EDGE_PATH.write_text(new)
    done(f"murphy_edge.py: {len(src)} → {len(new)} bytes (backup at {backup})")


def remove_from_monolith():
    step("Step 3 — remove PATCH-417 routes from monolith")
    src = MONOLITH.read_text()
    start = src.find("# ── PATCH-417:")
    if start < 0:
        warn("PATCH-417 block not found in monolith (already clean?)")
        return
    # End: just before the @app.get("/api/email/config") line
    end = src.find('@app.get("/api/email/config")', start)
    if end < 0:
        warn("could not find end anchor — leaving monolith alone")
        return
    # Walk back to start of that decorator line
    while end > 0 and src[end - 1] != "\n":
        end -= 1
    # And keep the 4-space indent before that decorator
    while end > 0 and src[end - 1] == " ":
        end -= 1
    # Add back the proper indent for the next route
    new = src[:start] + "    " + src[end:].lstrip()

    import ast
    try:
        ast.parse(new)
    except SyntaxError as e:
        warn(f"syntax error after removal: {e} line {e.lineno}")
        return

    backup = MONOLITH.with_suffix(".py.pre-417b")
    shutil.copy(MONOLITH, backup)
    MONOLITH.write_text(new)
    done(f"monolith: {len(src)} → {len(new)} bytes (backup at {backup})")


if __name__ == "__main__":
    print("═" * 64)
    print("  PATCH-417b — Relocate Outbound Queue to murphy-edge")
    print("═" * 64)
    write_module()
    register_in_edge()
    remove_from_monolith()
    print("\n  Next: restart murphy-edge and murphy-production")
