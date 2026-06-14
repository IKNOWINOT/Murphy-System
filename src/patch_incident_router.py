"""
PATCH-INC-001 - Incident Router (LOCKED 2026-05-27)
=====================================================
Single ingestion point: tickets, feedback, errors, watchdog alerts.
For each event: Murphy plan -> parallel email + SMS + HITL + dept dispatch.
Locked: route paths, severity thresholds, parallel asyncio.gather pattern.
"""
from __future__ import annotations
import asyncio
import json
import logging

# Ship 31be — founder mail gate (HITL acceptance only)
try:
    from src.founder_mail_gate_31be import should_send_to_founder as _founder_gate_31be
except Exception:
    _founder_gate_31be = lambda *a, **k: True  # fail-open


# Ship 31bd — capacity dedupe
try:
    from src.capacity_dedupe_31bd import should_emit as _capacity_should_emit_31bd
except Exception:
    _capacity_should_emit_31bd = lambda *a, **k: True

import sqlite3
import uuid
import datetime as _dt
from typing import Optional, Dict, Any
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("murphy.incident_router")

DB_PATH = "/var/lib/murphy-production/incident_router.db"
HITL_DB = "/var/lib/murphy-production/hitl.db"
FOUNDER_EMAIL = "cpost@murphy.systems"
# R392 — Verizon shut down SMS-via-email gateway (AUP#BL). 
# Founder SMS now via R389 Twilio service. This constant disabled.
FOUNDER_SMS_GATEWAY = ""  # disabled R392 — use R389 SMS instead
FOUNDER_KEY = "founder_ad6b1fade355dc1c6dfa89db96d77608886bf63b01b4fb70"

DEPT_KEYWORDS = {
    "engineering": ["bug", "error", "crash", "broken", "exception", "stack", "api", "deploy"],
    "billing":     ["billing", "charge", "refund", "invoice", "subscription", "payment"],
    "sales":       ["pricing", "demo", "trial", "quote", "prospect", "deal"],
    "support":     ["how do i", "tutorial", "help", "guide", "docs"],
    "ops":         ["outage", "down", "slow", "latency", "watchdog", "drift", "silent", "pulse"],
    "executive":   ["churn", "cancel", "leaving", "downgrade"],
}
SEVERITY_RANK = {"low": 0, "normal": 1, "high": 2, "urgent": 3, "critical": 4}


def _ensure_schema():
    with sqlite3.connect(DB_PATH, timeout=4) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS incidents (
            incident_id TEXT PRIMARY KEY, source TEXT, severity TEXT,
            title TEXT, body TEXT, origin_id TEXT, origin_tenant_id TEXT,
            classified_dept TEXT, plan_summary TEXT,
            email_status TEXT, sms_status TEXT, hitl_id TEXT, dept_dispatch_id TEXT,
            status TEXT DEFAULT 'open', created_at TEXT, resolved_at TEXT, metadata TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_inc_status ON incidents(status)")
        c.commit()


def _classify_dept(text: str) -> str:
    tl = text.lower()
    scores = {d: sum(1 for k in kws if k in tl) for d, kws in DEPT_KEYWORDS.items()}
    scores = {d: s for d, s in scores.items() if s > 0}
    if not scores:
        return "support"
    return max(scores.items(), key=lambda kv: kv[1])[0]


async def _generate_plan(title: str, body: str, severity: str, dept: str) -> str:
    try:
        import aiohttp
        prompt = (
            "Generate a 3-step fix plan for this incident:\n"
            "Title: " + title + "\n"
            "Severity: " + severity + "\n"
            "Dept: " + dept + "\n"
            "Body: " + body[:1500] + "\n\n"
            "Output: numbered list, max 3 lines, action-only."
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:8000/api/chat",
                json={"message": prompt, "session_id": "incident_" + uuid.uuid4().hex[:8]},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("reply", "")[:800]
    except Exception as exc:
        log.warning("plan gen failed: %s", exc)
    return "Triage " + severity + " " + dept + " incident -- manual review needed"


async def _send_email_alert(iid, title, body, severity, dept, plan):
    try:
        from src.email_integration import EmailService
        es = EmailService.from_env()
        body_text = (
            "Incident #" + iid[:12] + "\n"
            "Severity: " + severity + "  |  Dept: " + dept + "\n\n"
            "--- ORIGINAL ---\n" + body[:2000] + "\n\n"
            "--- MURPHY PLAN ---\n" + plan + "\n\n"
            "Approve: https://murphy.systems/api/incidents/" + iid + "/approve\n"
            "Reject:  https://murphy.systems/api/incidents/" + iid + "/reject\n"
            "View:    https://murphy.systems/hitl\n"
        )
        result = await es.send(
            to=[FOUNDER_EMAIL],
            subject="[Murphy " + severity.upper() + "] " + title[:100],
            body=body_text,
            from_addr="murphy@murphy.systems",
        )
        return "sent" if getattr(result, "success", False) else "failed"
    except Exception as exc:
        log.warning("email failed: %s", exc)
        return "error:" + type(exc).__name__


async def _send_sms_alert(iid, title, severity):
    if SEVERITY_RANK.get(severity, 1) < SEVERITY_RANK["urgent"]:
        return "skipped_low_severity"
    try:
        from src.email_integration import EmailService
        es = EmailService.from_env()
        result = await es.send(
            to=[FOUNDER_SMS_GATEWAY],
            subject="Murphy " + severity.upper(),
            body=title[:120] + "\nhttps://murphy.systems/hitl",
            from_addr="murphy@murphy.systems",
        )
        return "sent_via_gateway" if getattr(result, "success", False) else "failed"
    except Exception as exc:
        log.warning("sms failed: %s", exc)
        return "error:" + type(exc).__name__


async def _queue_hitl(iid, title, body, severity, dept, plan):
    """Direct DB insert - bypasses HTTP and auth overhead."""
    try:
        with sqlite3.connect(HITL_DB, timeout=4) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS interventions (
                id TEXT PRIMARY KEY, type TEXT, title TEXT, context TEXT,
                proposed_action TEXT, severity TEXT, status TEXT DEFAULT 'pending',
                metadata TEXT, created_at TEXT, resolved_at TEXT
            )""")
            review_id = "hitl_" + uuid.uuid4().hex[:12]
            now = _dt.datetime.now(_dt.UTC).isoformat()
            c.execute(
                "INSERT INTO interventions (id,type,title,context,proposed_action,"
                "severity,status,metadata,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (review_id, "incident_approval", title[:120], body[:2000],
                 plan, severity, "pending",
                 json.dumps({"incident_id": iid, "dept": dept}), now)
            )
            c.commit()
        return review_id
    except Exception as exc:
        log.warning("hitl direct insert failed: %s", exc)
        return "error"


async def _dispatch_dept(iid, dept, title, body, plan):
    """TRUE fire-and-forget dispatch via asyncio.create_task."""
    role_map = {"engineering": "executor", "billing": "exec_admin", "sales": "exec_admin",
                "support": "hitl", "ops": "prod_ops", "executive": "rosetta"}
    role = role_map.get(dept, "executor")
    task_id = "task_" + uuid.uuid4().hex[:10]
    question_text = (
        "Incident #" + iid[:12] + " [" + dept + "]: " + title +
        "\n\n" + body[:1500] + "\n\nPlan:\n" + plan
    )

    async def _do_dispatch():
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://127.0.0.1:8000/api/rosetta/dispatch",
                    json={"role": role, "question": question_text, "max_rounds": 3},
                    headers={
                        "X-Internal": "incident_router",
                        "X-API-Key": FOUNDER_KEY,
                    },
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    log.info("dispatch task %s returned HTTP %s for incident %s",
                             task_id, resp.status, iid)
        except Exception as exc:
            log.warning("dispatch task %s for incident %s failed: %s", task_id, iid, exc)

    asyncio.create_task(_do_dispatch())
    return "dispatched_" + task_id



async def _pack_dlfr(iid, source, severity, title, body, dept, plan, origin_id, metadata):
    """5th leg of the fanout — emit a DLF-R semantic package for this incident.

    Captures the incident as Threads+Nodes+Weaves with a live Rosetta snapshot.
    Failure here MUST NOT break the other 4 legs — wrapped + best-effort.
    """
    try:
        from src.dlf_r import pack, store
        threads = [{
            "id": "thr_" + iid,
            "payload": (title[:200] + "\n\n" + body[:1000]),
            "created_at_utc": _dt.datetime.now(_dt.UTC).isoformat(),
            "metadata": {"source": source, "severity": severity,
                         "dept": dept, "origin_id": origin_id},
        }]
        if plan:
            threads.append({
                "id": "thr_plan_" + iid,
                "payload": plan[:1500],
                "created_at_utc": _dt.datetime.now(_dt.UTC).isoformat(),
                "metadata": {"kind": "murphy_plan", "incident_id": iid},
            })
        # Nodes: incident itself + each fanout target
        nodes = [
            {"id": "node_inc_" + iid, "label": "incident:" + iid,
             "thread_refs": ["thr_" + iid], "metadata": {"severity": severity}},
            {"id": "node_src_" + source, "label": "source:" + source,
             "thread_refs": [], "metadata": {"role": "trigger"}},
            {"id": "node_dept_" + dept, "label": "dept:" + dept,
             "thread_refs": [], "metadata": {"role": "handler"}},
            {"id": "node_email", "label": "channel:email",
             "thread_refs": [], "metadata": {"role": "notify"}},
            {"id": "node_sms",   "label": "channel:sms",
             "thread_refs": [], "metadata": {"role": "notify"}},
            {"id": "node_hitl",  "label": "channel:hitl_queue",
             "thread_refs": [], "metadata": {"role": "governance"}},
        ]
        # Weaves: how this incident is connected
        weaves = [
            {"id": "w_route_" + iid,  "source": "node_src_" + source,
             "target": "node_inc_" + iid, "type": "ROUTED_TO", "confidence": 1.0,
             "provenance": "patch_incident_router.route_incident"},
            {"id": "w_dept_" + iid,   "source": "node_inc_" + iid,
             "target": "node_dept_" + dept, "type": "DEPENDS_ON", "confidence": 1.0,
             "provenance": "_classify_dept"},
            {"id": "w_email_" + iid,  "source": "node_inc_" + iid,
             "target": "node_email", "type": "SUPPORTS", "confidence": 1.0,
             "provenance": "_send_email_alert"},
            {"id": "w_sms_" + iid,    "source": "node_inc_" + iid,
             "target": "node_sms",   "type": "SUPPORTS", "confidence": 1.0,
             "provenance": "_send_sms_alert"},
            {"id": "w_hitl_" + iid,   "source": "node_inc_" + iid,
             "target": "node_hitl",  "type": "ESCALATED_TO", "confidence": 1.0,
             "provenance": "_queue_hitl"},
        ]
        blob = pack(threads, nodes, weaves,
                    creator="incident_router",
                    metadata={"incident_id": iid, "user_metadata": metadata or {}})
        pkg_id = store(blob, label="incident:" + iid)
        return "dlfr_" + pkg_id
    except Exception as exc:
        log.warning("dlfr pack failed for %s: %s", iid, exc)
        return "dlfr_skipped"


async def route_incident(source, severity, title, body,
                         origin_id="", origin_tenant_id="", metadata=None):
    _ensure_schema()
    iid = "inc_" + uuid.uuid4().hex[:12]
    now = _dt.datetime.now(_dt.UTC).isoformat()
    dept = _classify_dept(title + " " + body)

    plan = await _generate_plan(title, body, severity, dept)

    # PARALLEL fan-out: email, sms, hitl-direct, dispatch-detached
    # PARALLEL fan-out — 5 legs:
    # legs 1-4 are the locked founder-cockpit pipeline.
    # leg 5 (DLF-R pack) is best-effort; failure must not affect 1-4.
    email_status, sms_status, hitl_id, dept_dispatch_id, dlfr_pkg = await asyncio.gather(
        _send_email_alert(iid, title, body, severity, dept, plan),
        _send_sms_alert(iid, title, severity),
        _queue_hitl(iid, title, body, severity, dept, plan),
        _dispatch_dept(iid, dept, title, body, plan),
        _pack_dlfr(iid, source, severity, title, body, dept, plan, origin_id, metadata),
        return_exceptions=False,
    )

    try:
        with sqlite3.connect(DB_PATH, timeout=4) as c:
            c.execute(
                "INSERT INTO incidents (incident_id,source,severity,title,body,origin_id,"
                "origin_tenant_id,classified_dept,plan_summary,email_status,sms_status,"
                "hitl_id,dept_dispatch_id,status,created_at,metadata) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (iid, source, severity, title[:200], body[:8000], origin_id,
                 origin_tenant_id, dept, plan[:1500], email_status, sms_status,
                 hitl_id, dept_dispatch_id, "open", now,
                 json.dumps({**(metadata or {}), "dlfr_package": dlfr_pkg}))
            )
            c.commit()
    except Exception as exc:
        log.error("persist failed: %s", exc)

    log.info("incident %s routed: sev=%s dept=%s email=%s sms=%s hitl=%s dlfr=%s",
             iid, severity, dept, email_status, sms_status, hitl_id, dlfr_pkg)

    return {
        "incident_id": iid, "severity": severity, "dept": dept, "plan": plan,
        "email_status": email_status, "sms_status": sms_status,
        "hitl_id": hitl_id, "dept_dispatch_id": dept_dispatch_id, "status": "open"
    }


def install_incident_router_routes(app):
    _ensure_schema()

    @app.post("/api/incidents/route")
    async def _route(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)
        result = await route_incident(
            source=data.get("source", "manual"),
            severity=data.get("severity", "normal"),
            title=data.get("title", "Untitled incident"),
            body=data.get("body", ""),
            origin_id=data.get("origin_id", ""),
            origin_tenant_id=data.get("origin_tenant_id", ""),
            metadata=data.get("metadata"),
        )
        return JSONResponse(result)

    @app.get("/api/incidents")
    async def _list(request: Request, limit: int = 50, status: str = ""):
        try:
            with sqlite3.connect(DB_PATH, timeout=4) as c:
                q = ("SELECT incident_id,source,severity,title,classified_dept,"
                     "email_status,sms_status,hitl_id,status,created_at FROM incidents")
                params = []
                if status:
                    q += " WHERE status=?"
                    params.append(status)
                q += " ORDER BY created_at DESC LIMIT ?"
                params.append(min(max(1, limit), 200))
                rows = c.execute(q, params).fetchall()
            return JSONResponse({"count": len(rows), "incidents": [
                {"incident_id": r[0], "source": r[1], "severity": r[2], "title": r[3],
                 "dept": r[4], "email_status": r[5], "sms_status": r[6], "hitl_id": r[7],
                 "status": r[8], "created_at": r[9]} for r in rows]})
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.post("/api/incidents/{incident_id}/approve")
    async def _approve(incident_id: str):
        with sqlite3.connect(DB_PATH, timeout=4) as c:
            c.execute("UPDATE incidents SET status='approved', resolved_at=? WHERE incident_id=?",
                      (_dt.datetime.now(_dt.UTC).isoformat(), incident_id))
            c.commit()
        return JSONResponse({"success": True, "incident_id": incident_id, "status": "approved"})

    @app.post("/api/incidents/{incident_id}/reject")
    async def _reject(incident_id: str):
        with sqlite3.connect(DB_PATH, timeout=4) as c:
            c.execute("UPDATE incidents SET status='rejected', resolved_at=? WHERE incident_id=?",
                      (_dt.datetime.now(_dt.UTC).isoformat(), incident_id))
            c.commit()
        return JSONResponse({"success": True, "incident_id": incident_id, "status": "rejected"})

    log.info("PATCH-INC-001 incident router mounted: /api/incidents/{route,list,approve,reject}")
