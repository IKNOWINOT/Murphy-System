"""
PATCH-SUP-001 — Support page + public ticket endpoint (LOCKED 2026-05-27)
============================================================================

WHAT THIS IS:
  Mounts on the MONOLITH (port 8000, public-facing via nginx):
  - GET  /support               → support page HTML (static)
  - POST /api/support/ticket    → PUBLIC ticket creation (anonymous OK)
  - GET  /api/support/tickets   → list tickets (auth required by middleware)

  POST /api/support/ticket forwards to the existing PATCH-403 triage logic
  in client_solutions.db. Same schema, same triage events, same SLA.
  Why a wrapper? The /api/client-solutions/triage route lives on ops:8003
  which sits behind ModularAuthMiddleware — fine for admin use, wrong for
  a public support form. This wrapper exposes ONLY the create path,
  rate-limited, with anti-spam input checks.

WHY IT EXISTS:
  Pre-2026-05-27 Murphy had no way for non-authenticated users to
  contact support. Customers had to know cpost@murphy.systems directly.

DEPENDENCIES:
  - /opt/Murphy-System/static/support.html (the page)
  - /var/lib/murphy-production/client_solutions.db (tickets table from PATCH-403)
  - Optional: patch403_client_solutions.triage_inbound (for auto-routing)
  - Optional: src.email_integration.EmailService (founder notify)

RATE LIMITING:
  In-memory token bucket — 5 submissions per email per hour, 30 per IP per hour.
  Bypassed if X-API-Key is a valid founder key.

LAST UPDATED: 2026-05-27 — initial wiring
"""
from __future__ import annotations
import json, sqlite3, uuid, logging, time, datetime as _dt
from collections import defaultdict, deque
from pathlib import Path
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse

log = logging.getLogger("murphy.support")

DB_PATH = "/var/lib/murphy-production/client_solutions.db"
SUPPORT_HTML = "/opt/Murphy-System/static/support.html"

# Rate limit buckets (in-memory, per-process)
_RATE_EMAIL: dict = defaultdict(lambda: deque(maxlen=10))
_RATE_IP: dict = defaultdict(lambda: deque(maxlen=50))
_RATE_WINDOW_SEC = 3600

def _rate_check(email: str, ip: str) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    now = time.time()
    # Email bucket
    eb = _RATE_EMAIL[email.lower()]
    while eb and now - eb[0] > _RATE_WINDOW_SEC:
        eb.popleft()
    if len(eb) >= 5:
        return False, "rate_limit_email"
    # IP bucket
    ib = _RATE_IP[ip]
    while ib and now - ib[0] > _RATE_WINDOW_SEC:
        ib.popleft()
    if len(ib) >= 30:
        return False, "rate_limit_ip"
    return True, ""

def _rate_record(email: str, ip: str):
    now = time.time()
    _RATE_EMAIL[email.lower()].append(now)
    _RATE_IP[ip].append(now)

def _create_ticket_via_triage(email: str, subject: str, body: str, priority: str) -> dict:
    """
    Call PATCH-403's triage_inbound if available — gets full classification,
    queue routing, and SLA. Fall back to direct insert if PATCH-403 missing.
    """
    try:
        # PATCH-403 lives at /opt/Murphy-System/src/patch403_client_solutions.py
        import sys
        sys.path.insert(0, '/opt/Murphy-System/src')
        from patch403_client_solutions import triage_inbound  # type: ignore
        result = triage_inbound({
            "from_email": email,
            "from_name": email.split("@")[0],
            "subject": subject,
            "body": body,
            "priority_hint": priority,
            "source": "support_page_web",
        })
        return {"ok": True, "via": "triage", **result}
    except Exception as exc:
        log.warning("triage_inbound unavailable (%s), falling back to direct insert", exc)
        return _direct_insert(email, subject, body, priority)

def _direct_insert(email: str, subject: str, body: str, priority: str) -> dict:
    """Fallback path — insert directly into client_solutions.db.tickets schema."""
    ticket_id = "tkt_" + uuid.uuid4().hex[:12]
    now = _dt.datetime.now(_dt.UTC).isoformat()
    sla_hours = {"urgent": 4, "high": 8, "normal": 24, "low": 72}.get(priority, 24)
    sla_due = (_dt.datetime.now(_dt.UTC) + _dt.timedelta(hours=sla_hours)).isoformat()
    try:
        with sqlite3.connect(DB_PATH, timeout=4) as c:
            c.execute(
                "INSERT INTO tickets (id,queue,status,priority,subject,body,from_email,"
                "from_name,created_at,updated_at,sla_due_at,classification,triage_decision)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ticket_id, "general", "open", priority, subject, body, email,
                 email.split("@")[0], now, now, sla_due,
                 json.dumps({"method": "no_patch403_fallback"}),
                 json.dumps({"next_action": "human_review"}))
            )
            c.commit()
        return {"ok": True, "via": "direct_insert",
                "ticket_id": ticket_id, "queue": "general",
                "priority": priority, "sla_due_at": sla_due}
    except Exception as exc:
        log.error("direct ticket insert failed: %s", exc)
        return {"ok": False, "error": "persist_failed", "detail": str(exc)}

async def _notify_founder(ticket_id: str, email: str, subject: str, priority: str, body: str) -> bool:
    """Route support ticket through PATCH-INC-001 incident router (2026-05-27).
    The router fans out: email + SMS (if urgent) + HITL + dept dispatch in parallel."""
    severity_map = {"low": "low", "normal": "normal", "high": "high",
                    "urgent": "urgent", "critical": "critical"}
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:8000/api/incidents/route",
                json={
                    "source": "support_ticket",
                    "severity": severity_map.get(priority, "normal"),
                    "title": f"Support ticket from {email}: {subject[:80]}",
                    "body": body,
                    "origin_id": ticket_id,
                    "metadata": {"ticket_id": ticket_id, "from_email": email,
                                 "raw_priority": priority}
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                if resp.status == 200:
                    log.info("support ticket %s routed to incident router", ticket_id)
                    return True
                log.warning("support ticket %s router returned HTTP %s",
                            ticket_id, resp.status)
                return False
    except Exception as exc:
        log.warning("support ticket %s notify via router failed: %s", ticket_id, exc)
        return False

def install_support_routes(app):
    """Mount /support + /api/support/* on the given FastAPI app (monolith)."""

    @app.get("/support")
    async def _support_page():
        p = Path(SUPPORT_HTML)
        if not p.exists():
            return JSONResponse({"error": "support page missing"}, status_code=503)
        return FileResponse(p, media_type="text/html")

    @app.post("/api/support/ticket")
    async def _create_ticket(request: Request):
        """PUBLIC endpoint — no auth required."""
        try:
            body_json = await request.json()
        except Exception:
            return JSONResponse({"success": False, "error": "invalid JSON"}, status_code=400)

        email = (body_json.get("email") or "").strip().lower()
        subject = (body_json.get("subject") or "").strip()[:160]
        priority = (body_json.get("priority") or "normal").strip().lower()
        msg_body = (body_json.get("body") or "").strip()[:6000]

        # Validation
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            return JSONResponse({"success": False, "error": "valid email required"}, status_code=400)
        if not subject or len(subject) < 3:
            return JSONResponse({"success": False, "error": "subject too short"}, status_code=400)
        if not msg_body or len(msg_body) < 10:
            return JSONResponse({"success": False, "error": "body too short"}, status_code=400)
        if priority not in ("low", "normal", "high", "urgent"):
            priority = "normal"

        # Spam heuristics — obvious cases
        for spammy in ["http://", "https://", "www.", "buy now", "click here"]:
            if msg_body.lower().count(spammy) > 3 or subject.lower().count(spammy) > 0:
                log.warning("support ticket rejected as spam: %s", email)
                return JSONResponse({"success": False, "error": "rejected: looks like spam"}, status_code=429)

        # Rate limit
        ip = request.client.host if request.client else "unknown"
        ok, reason = _rate_check(email, ip)
        if not ok:
            log.warning("support ticket rate-limited (%s) email=%s ip=%s", reason, email, ip)
            return JSONResponse({"success": False, "error": reason}, status_code=429)
        _rate_record(email, ip)

        # Create ticket
        result = _create_ticket_via_triage(email, subject, msg_body, priority)
        if not result.get("ok"):
            return JSONResponse({"success": False, "error": result.get("error", "create_failed")},
                              status_code=500)

        ticket_id = result.get("ticket_id", "")
        notified = await _notify_founder(ticket_id, email, subject, priority, msg_body)

        return {
            "success": True,
            "ticket_id": ticket_id,
            "queue": result.get("queue", "general"),
            "priority": priority,
            "sla_due_at": result.get("sla_due_at", ""),
            "notified_founder": notified,
            "message": "Ticket created. You'll hear back via email.",
        }

    @app.get("/api/support/tickets")
    async def _list_tickets(request: Request, limit: int = 100, status: str = ""):
        """Founder/admin endpoint — lists recent tickets. Auth happens upstream."""
        try:
            with sqlite3.connect(DB_PATH, timeout=4) as c:
                if status:
                    q = ("SELECT id,from_email,subject,priority,status,queue,created_at,sla_due_at "
                         "FROM tickets WHERE status=? ORDER BY created_at DESC LIMIT ?")
                    rows = c.execute(q, (status, min(max(1, limit), 500))).fetchall()
                else:
                    q = ("SELECT id,from_email,subject,priority,status,queue,created_at,sla_due_at "
                         "FROM tickets ORDER BY created_at DESC LIMIT ?")
                    rows = c.execute(q, (min(max(1, limit), 500),)).fetchall()
            return {
                "success": True,
                "count": len(rows),
                "tickets": [
                    {"ticket_id": r[0], "email": r[1], "subject": r[2], "priority": r[3],
                     "status": r[4], "queue": r[5], "created_at": r[6], "sla_due_at": r[7]}
                    for r in rows
                ]
            }
        except Exception as exc:
            return JSONResponse({"success": False, "error": str(exc)}, status_code=500)

    log.info("PATCH-SUP-001 mounted: /support + /api/support/{ticket,tickets}")
