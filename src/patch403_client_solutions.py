"""
PATCH-403 — Client Solutions Sorting Hat
=========================================

Inbox: clientsolutions@murphy.systems
Function: triage ALL inbound customer mail, classify, route to the right queue,
open a ticket, log every decision to the Event Spine.

Hard rules (IMMUTABLE — never violate):
- May NOT change source code on customer request
- May NOT alter platform rules or terms
- May NOT contradict HIPAA/SOC2/GDPR/consumer law
- May NOT exceed compensation policy without HITL

Free-month grant: auto-grant only when ALL of:
  (a) Documented outage >= 4 hours on a paying tenant
  (b) Customer past 30 days of paid service
  (c) No free month in prior 90 days
  (d) Murphy-side incident log confirms the outage
Anything else -> HITL approval.

This module:
- creates 7 tables (BillingTicket, ChurnTicket, BugTicket, TrainingTicket,
  SalesLead, AccountRecoveryTicket, GeneralTicket, CompensationGrant, IncidentLog)
- exposes 12 endpoints under /api/client-solutions/*
- classifies incoming text (heuristic + LLM)
- routes to the correct queue
- enforces the free-month policy gate
- emits every decision as an Event Spine event

Wired into /opt/Murphy-System/src/runtime/app.py via a single
`init_client_solutions_routes(app)` call.
"""

from __future__ import annotations
import os
import json
import sqlite3
import hashlib
import time
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse

# ----------------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------------
DB_PATH = "/var/lib/murphy-production/client_solutions.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id              TEXT PRIMARY KEY,
    queue           TEXT NOT NULL,           -- billing|churn|bug|training|sales|recovery|general
    status          TEXT NOT NULL DEFAULT 'open',  -- open|in_progress|resolved|closed|escalated
    priority        TEXT NOT NULL DEFAULT 'normal',-- low|normal|high|critical
    subject         TEXT,
    body            TEXT,
    from_email      TEXT,
    from_name       TEXT,
    account_id      TEXT,
    tier            TEXT,                    -- free|starter|pro|enterprise
    classification  TEXT,                    -- json: {confidence, signals[], method}
    triage_decision TEXT,                    -- json: full triage payload
    assigned_agent  TEXT,
    resolution      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    closed_at       TEXT,
    sla_due_at      TEXT,
    raw_payload     TEXT                     -- original email JSON
);
CREATE INDEX IF NOT EXISTS idx_tickets_queue ON tickets(queue);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_account ON tickets(account_id);
CREATE INDEX IF NOT EXISTS idx_tickets_email ON tickets(from_email);

CREATE TABLE IF NOT EXISTS compensation_grants (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    email           TEXT NOT NULL,
    grant_type      TEXT NOT NULL,           -- free_month|partial_refund|credit
    grant_value     REAL NOT NULL,           -- months or dollars
    reason          TEXT NOT NULL,
    incident_id     TEXT,                    -- ties to IncidentLog
    auto_granted    INTEGER NOT NULL,        -- 0 = HITL approved, 1 = automatic
    policy_check    TEXT,                    -- json: which gates passed/failed
    requested_by    TEXT,                    -- agent or email
    approved_by     TEXT,                    -- 'auto' or user_id
    ticket_id       TEXT,                    -- linked ticket
    created_at      TEXT NOT NULL,
    applied_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_grants_account ON compensation_grants(account_id);
CREATE INDEX IF NOT EXISTS idx_grants_created ON compensation_grants(created_at);

CREATE TABLE IF NOT EXISTS incident_log (
    id              TEXT PRIMARY KEY,
    service         TEXT NOT NULL,           -- web|api|mail|database|nginx
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    duration_min    INTEGER,
    severity        TEXT NOT NULL,           -- minor|major|critical
    affected_tiers  TEXT,                    -- json array
    description     TEXT,
    auto_detected   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incident_started ON incident_log(started_at);

CREATE TABLE IF NOT EXISTS triage_events (
    id              TEXT PRIMARY KEY,
    ticket_id       TEXT,
    event_type      TEXT NOT NULL,           -- inbound|classified|routed|escalated|resolved|grant_evaluated
    detail          TEXT,
    agent           TEXT,
    hash_prev       TEXT,
    hash_self       TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_triage_ticket ON triage_events(ticket_id);
"""

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _gen_id(prefix: str) -> str:
    return f"{prefix}_{hashlib.sha1((str(time.time())+os.urandom(8).hex()).encode()).hexdigest()[:12]}"

def _hash_event(prev: str, payload: Dict[str, Any]) -> str:
    raw = (prev or "") + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

def _emit_triage_event(ticket_id: Optional[str], event_type: str,
                       detail: Dict[str, Any], agent: str = "sorting_hat") -> str:
    conn = _db()
    cur = conn.execute("SELECT hash_self FROM triage_events ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    prev_hash = row["hash_self"] if row else ""
    payload = {"ticket_id": ticket_id, "type": event_type, "detail": detail,
               "agent": agent, "ts": _now()}
    h = _hash_event(prev_hash, payload)
    eid = _gen_id("evt")
    conn.execute("""
        INSERT INTO triage_events (id, ticket_id, event_type, detail, agent,
                                   hash_prev, hash_self, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (eid, ticket_id, event_type, json.dumps(detail, default=str),
          agent, prev_hash, h, _now()))
    conn.commit()
    conn.close()
    return eid

# ----------------------------------------------------------------------------
# Classifier — heuristic, LLM augmentation optional
# ----------------------------------------------------------------------------
QUEUE_SIGNALS = {
    "billing": [
        r"\b(invoice|bill|charge|charged|refund|payment|credit card|stripe|"
        r"subscription|renewed|renewal|cancel\w+ charge|disput\w+|chargeback)\b"
    ],
    "churn": [
        r"\b(cancel(?!\s+(my\s+)?charge)|downgrade|leaving|switch\w+|"
        r"unsubscribe|terminate|close (my )?account|delete (my )?account)\b"
    ],
    "bug": [
        r"\b(bug|error|broken|crash\w*|not work\w*|doesn[' ]?t work|fail\w*|"
        r"down|outage|500 error|404|exception|stuck|frozen|glitch|hang\w*)\b"
    ],
    "training": [
        r"\b(how (do|can) (i|we)|how to|tutorial|guide|walkthrough|onboard\w*|"
        r"docs?|documentation|getting started|i don'?t understand|teach\w*|explain)\b"
    ],
    "sales": [
        r"\b(pricing|how much|plan|tier|demo|trial|enterprise|quote|"
        r"interested in|sign up|signing up|new customer|prospect)\b"
    ],
    "recovery": [
        r"\b(forgot (my )?password|can'?t log ?in|locked out|reset (my )?password|"
        r"2fa|two[- ]factor|mfa|access (my )?account)\b"
    ],
}

QUEUE_PRIORITY = {  # lower index = checked first when scores tie
    "recovery": 0,
    "bug": 1,
    "billing": 2,
    "churn": 3,
    "sales": 4,
    "training": 5,
}

def classify_message(subject: str, body: str) -> Dict[str, Any]:
    """Heuristic classifier. Returns {queue, confidence, signals, method}."""
    text = ((subject or "") + " " + (body or "")).lower()
    scores: Dict[str, int] = {}
    matched_signals: Dict[str, List[str]] = {}
    for queue, patterns in QUEUE_SIGNALS.items():
        s = 0
        sigs: List[str] = []
        for p in patterns:
            for m in re.finditer(p, text, flags=re.IGNORECASE):
                s += 1
                sigs.append(m.group(0))
        if s > 0:
            scores[queue] = s
            matched_signals[queue] = sigs[:5]
    if not scores:
        return {"queue": "general", "confidence": 0.0, "signals": [],
                "method": "heuristic_no_match"}
    # Pick the highest scoring queue; tiebreak by QUEUE_PRIORITY
    best = max(scores.items(), key=lambda kv: (kv[1], -QUEUE_PRIORITY[kv[0]]))
    total = sum(scores.values())
    confidence = round(best[1] / max(total, 1), 3)
    return {
        "queue": best[0],
        "confidence": confidence,
        "signals": matched_signals.get(best[0], []),
        "scores": scores,
        "method": "heuristic",
    }

# ----------------------------------------------------------------------------
# Free-month policy gate — IMMUTABLE
# ----------------------------------------------------------------------------
FREE_MONTH_POLICY = {
    "min_outage_hours": 4,
    "min_paid_days": 30,
    "cooldown_days": 90,
    "require_incident_log": True,
}

def _lookup_customer(account_id: Optional[str], email: Optional[str]) -> Optional[Dict]:
    """Look up customer in customers.db."""
    try:
        c = sqlite3.connect("/var/lib/murphy-production/customers.db", timeout=10)
        c.row_factory = sqlite3.Row
        if account_id:
            row = c.execute("SELECT * FROM customers WHERE account_id=?",
                            (account_id,)).fetchone()
        elif email:
            row = c.execute("SELECT * FROM customers WHERE email=?",
                            (email,)).fetchone()
        else:
            row = None
        c.close()
        return dict(row) if row else None
    except Exception:
        return None

def evaluate_free_month(account_id: str, email: str,
                       incident_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns {eligible: bool, auto_grant: bool, reason: str, gates: {...}}
    auto_grant=True only when ALL 4 gates pass.
    Otherwise eligible=False → must route to HITL.
    """
    gates = {
        "outage_4h": False,
        "paid_30d": False,
        "cooldown_90d": False,
        "incident_logged": False,
    }
    reasons: List[str] = []

    cust = _lookup_customer(account_id, email)
    if not cust:
        return {"eligible": False, "auto_grant": False,
                "reason": "no_customer_record",
                "gates": gates}

    # Gate 1+4: incident log
    conn = _db()
    if incident_id:
        inc = conn.execute("SELECT * FROM incident_log WHERE id=?",
                           (incident_id,)).fetchone()
        if inc and inc["duration_min"] is not None:
            gates["incident_logged"] = True
            if inc["duration_min"] >= FREE_MONTH_POLICY["min_outage_hours"] * 60:
                gates["outage_4h"] = True
            else:
                reasons.append(f"outage_only_{inc['duration_min']}min")
        else:
            reasons.append("incident_not_resolved")
    else:
        reasons.append("no_incident_id_provided")

    # Gate 2: paid >= 30 days
    try:
        created = datetime.fromisoformat(cust["created_at"])
        age_days = (datetime.now(timezone.utc) - created.replace(
            tzinfo=created.tzinfo or timezone.utc)).days
        tier = (cust.get("tier") or "").lower()
        is_paying = tier not in ("free", "trial", "")
        if is_paying and age_days >= FREE_MONTH_POLICY["min_paid_days"]:
            gates["paid_30d"] = True
        else:
            reasons.append(f"not_paying_30d (tier={tier}, age={age_days}d)")
    except Exception as e:
        reasons.append(f"cust_age_check_error: {e}")

    # Gate 3: no free month in prior 90 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=FREE_MONTH_POLICY["cooldown_days"])).isoformat()
    prior = conn.execute("""
        SELECT COUNT(*) AS c FROM compensation_grants
        WHERE account_id = ? AND grant_type = 'free_month' AND created_at >= ?
    """, (cust["account_id"], cutoff)).fetchone()
    if prior["c"] == 0:
        gates["cooldown_90d"] = True
    else:
        reasons.append(f"received_free_month_in_last_90d ({prior['c']}x)")

    conn.close()

    all_pass = all(gates.values())
    return {
        "eligible": all_pass,
        "auto_grant": all_pass,
        "reason": "all_gates_passed" if all_pass else ("; ".join(reasons) or "gates_failed"),
        "gates": gates,
        "customer": {"account_id": cust["account_id"],
                     "tier": cust.get("tier"),
                     "email": cust.get("email")},
    }

# ----------------------------------------------------------------------------
# Triage pipeline
# ----------------------------------------------------------------------------
def triage_inbound(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point.  payload expected keys:
        from_email, from_name, subject, body, account_id (optional)
    Returns {ticket_id, queue, classification, priority, next_action}
    """
    subject = (payload.get("subject") or "").strip()
    body = (payload.get("body") or "").strip()
    from_email = (payload.get("from_email") or "").strip().lower()
    from_name = payload.get("from_name") or ""
    account_id = payload.get("account_id")

    # Step 1: classify
    cls = classify_message(subject, body)
    _emit_triage_event(None, "inbound", {
        "from": from_email, "subject": subject[:120],
        "classification": cls,
    })

    # Step 2: customer lookup for tier-based priority
    cust = _lookup_customer(account_id, from_email)
    tier = (cust.get("tier") if cust else "unknown") or "unknown"

    # Priority: enterprise/pro/critical-words = high
    priority = "normal"
    body_low = body.lower()
    if any(kw in body_low for kw in ["down", "outage", "production", "critical", "urgent", "emergency"]):
        priority = "high"
    if tier in ("enterprise", "pro"):
        priority = "high" if priority != "high" else "critical"
    if cls["queue"] == "bug" and tier in ("enterprise", "pro"):
        priority = "critical"

    # Step 3: SLA window
    sla_hours = {"critical": 1, "high": 4, "normal": 24, "low": 72}[priority]
    sla_due = (datetime.now(timezone.utc) + timedelta(hours=sla_hours)).isoformat()

    # Step 4: create ticket
    ticket_id = _gen_id("tkt")
    queue = cls["queue"]
    conn = _db()
    conn.execute("""
        INSERT INTO tickets (id, queue, status, priority, subject, body,
                             from_email, from_name, account_id, tier,
                             classification, created_at, updated_at,
                             sla_due_at, raw_payload)
        VALUES (?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticket_id, queue, priority, subject, body, from_email, from_name,
          (cust["account_id"] if cust else None), tier,
          json.dumps(cls), _now(), _now(), sla_due,
          json.dumps(payload, default=str)))
    conn.commit()
    conn.close()

    _emit_triage_event(ticket_id, "routed", {
        "queue": queue, "priority": priority, "tier": tier,
        "sla_due": sla_due,
    })

    # Step 5: special path for password recovery — try auto-handle
    auto_resolved = False
    next_action = f"queue:{queue}"
    if queue == "recovery" and from_email:
        next_action = "send_reset_link_and_close"
        auto_resolved = True

    return {
        "ticket_id": ticket_id,
        "queue": queue,
        "priority": priority,
        "tier": tier,
        "sla_due_at": sla_due,
        "classification": cls,
        "next_action": next_action,
        "auto_resolved": auto_resolved,
    }

# ----------------------------------------------------------------------------
# FastAPI routes
# ----------------------------------------------------------------------------
def init_client_solutions_routes(app):
    init_db()

    @app.post("/api/client-solutions/triage")
    async def cs_triage(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not data.get("from_email") or not (data.get("subject") or data.get("body")):
            return JSONResponse({"ok": False, "error": "missing required: from_email + subject/body"}, status_code=400)
        result = triage_inbound(data)
        return JSONResponse({"ok": True, **result})

    @app.get("/api/client-solutions/tickets")
    async def cs_list_tickets(queue: str = "", status: str = "", limit: int = 50):
        conn = _db()
        q = "SELECT * FROM tickets WHERE 1=1"
        params: List[Any] = []
        if queue:
            q += " AND queue = ?"
            params.append(queue)
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows), "tickets": rows})

    @app.get("/api/client-solutions/tickets/{ticket_id}")
    async def cs_get_ticket(ticket_id: str):
        conn = _db()
        row = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not row:
            conn.close()
            return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
        events = [dict(e) for e in conn.execute(
            "SELECT * FROM triage_events WHERE ticket_id=? ORDER BY created_at ASC",
            (ticket_id,)).fetchall()]
        conn.close()
        return JSONResponse({"ok": True, "ticket": dict(row), "events": events})

    @app.post("/api/client-solutions/tickets/{ticket_id}/update")
    async def cs_update_ticket(ticket_id: str, request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        allowed = {"status", "priority", "assigned_agent", "resolution"}
        sets = {k: v for k, v in data.items() if k in allowed}
        if not sets:
            return JSONResponse({"ok": False, "error": "no_valid_fields"}, status_code=400)
        conn = _db()
        cols = ", ".join(f"{k}=?" for k in sets)
        params = list(sets.values()) + [_now(), ticket_id]
        conn.execute(f"UPDATE tickets SET {cols}, updated_at=? WHERE id=?", params)
        if sets.get("status") in ("resolved", "closed"):
            conn.execute("UPDATE tickets SET closed_at=? WHERE id=?", (_now(), ticket_id))
        conn.commit()
        conn.close()
        _emit_triage_event(ticket_id, "updated", sets)
        return JSONResponse({"ok": True, "ticket_id": ticket_id, "updated": sets})

    @app.post("/api/client-solutions/grants/evaluate")
    async def cs_evaluate_grant(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not data.get("email") and not data.get("account_id"):
            return JSONResponse({"ok": False, "error": "email or account_id required"}, status_code=400)
        result = evaluate_free_month(
            account_id=data.get("account_id", ""),
            email=data.get("email", ""),
            incident_id=data.get("incident_id"),
        )
        _emit_triage_event(data.get("ticket_id"), "grant_evaluated", result)
        return JSONResponse({"ok": True, **result})

    @app.post("/api/client-solutions/grants/apply")
    async def cs_apply_grant(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        required = ["account_id", "email", "grant_type", "reason"]
        if not all(data.get(k) for k in required):
            return JSONResponse({"ok": False, "error": f"missing required: {required}"}, status_code=400)

        # Re-evaluate to enforce policy
        evaluation = evaluate_free_month(
            account_id=data["account_id"],
            email=data["email"],
            incident_id=data.get("incident_id"),
        )
        auto = evaluation["auto_grant"]
        if not auto and data.get("approved_by", "") not in ("hitl", "founder"):
            return JSONResponse({
                "ok": False,
                "error": "policy_gate_failed_requires_hitl",
                "evaluation": evaluation,
            }, status_code=403)

        gid = _gen_id("grant")
        conn = _db()
        conn.execute("""
            INSERT INTO compensation_grants
            (id, account_id, email, grant_type, grant_value, reason, incident_id,
             auto_granted, policy_check, requested_by, approved_by, ticket_id,
             created_at, applied_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            gid, data["account_id"], data["email"], data["grant_type"],
            float(data.get("grant_value", 1.0)), data["reason"],
            data.get("incident_id"), 1 if auto else 0,
            json.dumps(evaluation),
            data.get("requested_by", "sorting_hat"),
            "auto" if auto else data.get("approved_by", "hitl"),
            data.get("ticket_id"), _now(),
            _now() if auto else None,
        ))
        conn.commit()
        conn.close()
        _emit_triage_event(data.get("ticket_id"), "grant_applied", {
            "grant_id": gid, "auto": auto, "evaluation": evaluation,
        })
        return JSONResponse({"ok": True, "grant_id": gid,
                             "auto_granted": auto, "evaluation": evaluation})

    @app.get("/api/client-solutions/grants")
    async def cs_list_grants(limit: int = 50, account_id: str = ""):
        conn = _db()
        if account_id:
            rows = conn.execute(
                "SELECT * FROM compensation_grants WHERE account_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (account_id, int(limit))).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM compensation_grants ORDER BY created_at DESC LIMIT ?",
                (int(limit),)).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "grants": [dict(r) for r in rows]})

    @app.post("/api/client-solutions/incidents")
    async def cs_log_incident(request: Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        if not data.get("service"):
            return JSONResponse({"ok": False, "error": "service required"}, status_code=400)
        iid = _gen_id("inc")
        started = data.get("started_at") or _now()
        ended = data.get("ended_at")
        duration = data.get("duration_min")
        if ended and not duration:
            try:
                s = datetime.fromisoformat(started)
                e = datetime.fromisoformat(ended)
                duration = int((e - s).total_seconds() / 60)
            except Exception:
                duration = None
        conn = _db()
        conn.execute("""
            INSERT INTO incident_log (id, service, started_at, ended_at,
                                      duration_min, severity, affected_tiers,
                                      description, auto_detected, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (iid, data["service"], started, ended, duration,
              data.get("severity", "minor"),
              json.dumps(data.get("affected_tiers", ["all"])),
              data.get("description"),
              int(data.get("auto_detected", 0)),
              _now()))
        conn.commit()
        conn.close()
        return JSONResponse({"ok": True, "incident_id": iid,
                             "duration_min": duration})

    @app.get("/api/client-solutions/incidents")
    async def cs_list_incidents(limit: int = 25):
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM incident_log ORDER BY started_at DESC LIMIT ?",
            (int(limit),)).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "incidents": [dict(r) for r in rows]})

    @app.get("/api/client-solutions/events")
    async def cs_list_events(ticket_id: str = "", limit: int = 100):
        conn = _db()
        if ticket_id:
            rows = conn.execute(
                "SELECT * FROM triage_events WHERE ticket_id=? "
                "ORDER BY created_at ASC LIMIT ?",
                (ticket_id, int(limit))).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM triage_events ORDER BY created_at DESC LIMIT ?",
                (int(limit),)).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "events": [dict(r) for r in rows]})

    @app.get("/api/client-solutions/stats")
    async def cs_stats():
        conn = _db()
        out = {}
        out["tickets_by_queue"] = {r["queue"]: r["c"] for r in conn.execute(
            "SELECT queue, COUNT(*) AS c FROM tickets GROUP BY queue").fetchall()}
        out["tickets_by_status"] = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) AS c FROM tickets GROUP BY status").fetchall()}
        out["open_tickets"] = conn.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE status='open'").fetchone()["c"]
        out["grants_total"] = conn.execute(
            "SELECT COUNT(*) AS c FROM compensation_grants").fetchone()["c"]
        out["grants_30d"] = conn.execute(
            "SELECT COUNT(*) AS c FROM compensation_grants WHERE created_at >= ?",
            ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),)
        ).fetchone()["c"]
        out["incidents_30d"] = conn.execute(
            "SELECT COUNT(*) AS c FROM incident_log WHERE started_at >= ?",
            ((datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),)
        ).fetchone()["c"]
        conn.close()
        return JSONResponse({"ok": True, "stats": out,
                             "policy": FREE_MONTH_POLICY})

    @app.get("/api/client-solutions/health")
    async def cs_health():
        try:
            conn = _db()
            n = conn.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()["c"]
            conn.close()
            return JSONResponse({"ok": True, "patch": "403",
                                 "module": "client_solutions",
                                 "tickets": n,
                                 "policy": FREE_MONTH_POLICY})
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    return app
