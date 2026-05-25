"""
PATCH-329/330 — Owner-Operator SaaS: FastAPI Router
Wraps the existing Flask-style logic in FastAPI APIRouter.

Wire into src/runtime/app.py:
  from src.oo_saas_router import oo_router
  app.include_router(oo_router)
"""

import uuid, sqlite3, json, re, os
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

OO_DB = "/var/lib/murphy-production/owner_operator.db"
PLATFORM_DB = "/var/lib/murphy-production/platform.db"

oo_router = APIRouter()

# ── Import the logic engines (they'll work without Flask context) ──────────────

def _oo_db():
    conn = sqlite3.connect(OO_DB)
    conn.row_factory = sqlite3.Row
    return conn

def _platform_db():
    conn = sqlite3.connect(PLATFORM_DB)
    conn.row_factory = sqlite3.Row
    return conn

# ── Survey endpoint ────────────────────────────────────────────────────────────

@oo_router.post("/api/oo/survey")
async def oo_survey(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    email = (data.get("email") or "").strip().lower()
    contact_name = (data.get("contact_name") or "").strip()
    if not email or not contact_name:
        raise HTTPException(400, "email and contact_name required")

    account_id = str(uuid.uuid4())
    employees = int(data.get("employees") or 1)
    annual_revenue = float(data.get("annual_revenue") or 0)

    # Score lead (1-10)
    score = 5
    if employees >= 3: score += 1
    if annual_revenue >= 500000: score += 1
    if annual_revenue >= 1000000: score += 1
    if data.get("biggest_pain"): score += 1
    if data.get("growth_goal"): score += 1

    # Routing
    routing = "nurture" if score < 7 else ("enterprise" if score >= 10 else "book")

    # Org chart scaffold from roles
    roles = data.get("roles") or []
    if isinstance(roles, str):
        roles = [r.strip() for r in roles.split("\n") if r.strip()]
    org_nodes = [{"title": r, "type": "shadow_agent"} for r in (roles or ["Owner/Operator"])]

    # Map workflows from daily tasks + wished_automated
    tasks_text = " ".join((data.get("daily_tasks") or []) + (data.get("wished_automated") or [])).lower()
    workflow_map = [
        ("invoice", "invoice_engine"), ("appointment", "appointment_engine"),
        ("follow-up", "email_cadence"), ("lead", "apc_prospector"),
        ("contract", "contract_engine"), ("scheduling", "appointment_engine"),
        ("crm", "crm_pipeline"), ("report", "metrics_reporter"),
        ("timecard", "timecard_engine"), ("proposal", "contract_engine"),
    ]
    identified = [{"keyword": k, "module": m} for k, m in workflow_map if k in tasks_text]

    # Automation hours
    auto_start = data.get("automation_hours_start") or "23:00"
    auto_end = data.get("automation_hours_end") or "06:00"

    # Save account
    conn = _oo_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS owner_operator_accounts (
            id TEXT PRIMARY KEY, email TEXT, contact_name TEXT, company_name TEXT,
            phone TEXT, industry TEXT, employees INTEGER, annual_revenue REAL,
            survey_data TEXT, lead_score INTEGER, routing TEXT, status TEXT,
            automation_hours_start TEXT, automation_hours_end TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        INSERT INTO owner_operator_accounts
        (id, email, contact_name, company_name, phone, industry, employees,
         annual_revenue, survey_data, lead_score, routing, status,
         automation_hours_start, automation_hours_end)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,'lead',?,?)
    """, (account_id, email, contact_name, data.get("company_name",""),
          data.get("phone",""), data.get("industry",""), employees, annual_revenue,
          json.dumps(data), score, routing, auto_start, auto_end))
    conn.commit()
    conn.close()

    messages = {
        "nurture": "Great start. I'll send you resources to get familiar with Murphy.",
        "book": "You're a great fit. Book a setup call and we'll get Murphy running for you.",
        "enterprise": "You're exactly who Murphy was built for. Corey will reach out personally."
    }

    return JSONResponse({
        "account_id": account_id,
        "lead_score": score,
        "routing": routing,
        "message": messages[routing],
        "org_chart_scaffold": {"nodes": org_nodes},
        "identified_workflows": identified,
        "automation_hours": {
            "start": auto_start, "end": auto_end,
            "description": f"Murphy operates autonomously {auto_start}–{auto_end}"
        }
    })


# ── HITL respond ──────────────────────────────────────────────────────────────

@oo_router.post("/api/oo/hitl/respond")
async def oo_hitl_respond(request: Request):
    data = await request.json()
    hitl_id = data.get("hitl_id", "")
    response = data.get("response", "")
    if not hitl_id or response not in ("approve", "reject"):
        raise HTTPException(400, "hitl_id and response (approve|reject) required")

    conn = _oo_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM hitl_queue WHERE id=?", (hitl_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "HITL item not found")

    cur.execute("""
        UPDATE hitl_queue SET status=?, resolved_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (response + "d", hitl_id))
    conn.commit()
    conn.close()
    return JSONResponse({"hitl_id": hitl_id, "status": response + "d",
                         "message": f"Action {response}d."})


# ── Dashboard ─────────────────────────────────────────────────────────────────

@oo_router.get("/api/oo/dashboard/{account_id}")
async def oo_dashboard(account_id: str):
    conn = _oo_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM owner_operator_accounts WHERE id=?", (account_id,))
    acct = cur.fetchone()
    if not acct:
        conn.close()
        raise HTTPException(404, "Account not found")

    # HITL
    cur.execute("SELECT COUNT(*) FROM hitl_queue WHERE account_id=? AND status='pending'",
                (account_id,))
    pending = cur.fetchone()[0]
    cur.execute("SELECT id, action_type, description, created_at FROM hitl_queue WHERE account_id=? AND status='pending' LIMIT 10",
                (account_id,))
    hitl_items = [{"id": r[0], "action": r[1], "description": r[2], "created": r[3]}
                  for r in cur.fetchall()]

    # Shadow patterns
    cur.execute("SELECT pattern_type, confidence, sample_count, automation_approved FROM shadow_patterns WHERE account_id=? ORDER BY confidence DESC LIMIT 5",
                (account_id,))
    patterns = [{"type": r[0], "confidence": f"{r[1]:.0%}", "observations": r[2],
                 "approved": bool(r[3])} for r in cur.fetchall()]

    # Backlog
    cur.execute("SELECT COUNT(*) FROM saas_work_backlog WHERE account_id=?", (account_id,))
    backlog_total = cur.fetchone()[0]
    cur.execute("SELECT status, COUNT(*) FROM saas_work_backlog WHERE account_id=? GROUP BY status",
                (account_id,))
    backlog_by_status = {r[0]: r[1] for r in cur.fetchall()}
    cur.execute("SELECT id, task, phase, priority, status, activates_on FROM saas_work_backlog WHERE account_id=? LIMIT 10", (account_id,))
    backlog_items = [{"id": r[0], "task": r[1], "phase": r[2], "priority": r[3],
                      "status": r[4], "activates": r[5]} for r in cur.fetchall()]

    # Contracts
    cur.execute("SELECT id, contract_value, payment_pct, status, signed_date, backlog_activation_date FROM saas_contracts WHERE account_id=?", (account_id,))
    contracts = [{"id": r[0], "value": r[1], "payment_pct": r[2], "status": r[3],
                  "signed_date": r[4], "backlog_activates": r[5]} for r in cur.fetchall()]

    # Backlog clock
    cur.execute("SELECT MIN(backlog_activation_date) FROM saas_contracts WHERE account_id=? AND backlog_activation_date IS NOT NULL", (account_id,))
    activation = cur.fetchone()[0]
    clock = None
    if activation:
        try:
            act_dt = datetime.fromisoformat(activation)
            days = (act_dt - datetime.utcnow()).days
            clock = {"activation_date": activation, "days_remaining": max(0, days)}
        except Exception:
            pass

    conn.close()
    return JSONResponse({
        "account": {"id": account_id, "status": dict(acct).get("status", "lead") if acct else "unknown"},
        "hitl_queue": {"pending": pending, "items": hitl_items},
        "shadow_agent": {"patterns_learned": len(patterns), "top_patterns": patterns},
        "backlog": {"total": backlog_total, "queued": backlog_by_status.get("queued", 0),
                    "active": backlog_by_status.get("active", 0),
                    "items": backlog_items, "clock": clock},
        "contracts": contracts
    })


# ── Weekly metrics ────────────────────────────────────────────────────────────

@oo_router.get("/api/oo/metrics/weekly/{account_id}")
async def oo_metrics_weekly(account_id: str):
    conn = _oo_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shadow_observations WHERE account_id=? AND timestamp >= datetime('now','-7 days')", (account_id,))
    obs = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM hitl_queue WHERE account_id=? AND status!='pending' AND created_at >= datetime('now','-7 days')", (account_id,))
    resolved = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM shadow_patterns WHERE account_id=? AND automation_approved=1", (account_id,))
    approved = cur.fetchone()[0]
    conn.close()
    health = "green" if obs > 0 else "yellow"
    return JSONResponse({
        "shadow_learning": {"observations": obs, "automations_approved": approved},
        "hitl_activity": {"total_resolved": resolved},
        "health": health,
        "recommendations": ["Keep observing — patterns build confidence over time"] if obs < 10 else ["Shadow agent has enough data to propose automations"]
    })


# ── Platform command ───────────────────────────────────────────────────────────

@oo_router.post("/api/platform/command")
async def platform_command(request: Request):
    data = await request.json()
    raw = (data.get("input") or data.get("text") or "").strip()
    account_id = data.get("account_id", "")
    if not account_id or not raw:
        raise HTTPException(400, "account_id and input required")

    # Simple intent parse
    text = raw.lower()
    requires_hitl = any(k in text for k in [
        "send", "contract", "invoice", "payment", "hire", "fire",
        "run", "execute", "email", "message", "contact"
    ])
    intent = "STATUS"
    for pattern, intent_name in [
        (r"start timer|clock in", "TIMECARD"),
        (r"stop timer|clock out", "TIMECARD"),
        (r"show|what|how|status|report", "STATUS"),
        (r"approve|yes|do it", "APPROVE"),
        (r"no|cancel|reject", "REJECT"),
        (r"schedule|automate|run every", "SCHEDULE"),
        (r"password|vault|credentials", "PASSWORD"),
    ]:
        if re.search(pattern, text):
            intent = intent_name
            break

    result = {"message": f"Got it — {intent.lower()} request noted.", "intent": intent}
    if requires_hitl:
        result["message"] = "That action requires your approval — queued as HITL."
        result["approve_url"] = f"/dashboard?id={account_id}"

    return JSONResponse({
        "intent": intent,
        "requires_hitl": requires_hitl,
        "action_taken": "queued_hitl" if requires_hitl else "executed",
        "result": result
    })


# ── Platform dynamic dashboard ────────────────────────────────────────────────

@oo_router.get("/api/platform/dashboard")
async def platform_dashboard(account_id: str = "", q: str = "show me everything"):
    if not account_id:
        raise HTTPException(400, "account_id required")

    cards = []
    conn = _oo_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM hitl_queue WHERE account_id=? AND status='pending'", (account_id,))
    pending = cur.fetchone()[0]
    cards.append({"type": "hitl_summary", "title": "⚡ Pending Approvals",
                  "count": pending, "urgent": pending > 0})

    cur.execute("SELECT status, COUNT(*) FROM saas_contracts WHERE account_id=? GROUP BY status", (account_id,))
    pipeline = {r[0]: r[1] for r in cur.fetchall()}
    cards.append({"type": "pipeline", "title": "📊 Pipeline", "content": pipeline})

    cur.execute("SELECT pattern_type, confidence FROM shadow_patterns WHERE account_id=? ORDER BY confidence DESC LIMIT 5", (account_id,))
    patterns = [{"type": r[0], "confidence": f"{r[1]:.0%}"} for r in cur.fetchall()]
    cards.append({"type": "shadow_patterns", "title": "🧠 Shadow Agent", "content": patterns})

    conn.close()
    return JSONResponse({"question": q, "cards": cards, "account_id": account_id})


# ── Subscription status ────────────────────────────────────────────────────────

@oo_router.get("/api/platform/subscription/{account_id}")
async def get_subscription(account_id: str):
    try:
        conn = sqlite3.connect(PLATFORM_DB)
        cur = conn.cursor()
        cur.execute("SELECT status, tier FROM subscriptions WHERE account_id=?", (account_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return JSONResponse({"status": "trial", "tier": "owner_operator", "can_operate": True})
        status, tier = row
        can_operate = status in ("active", "trial", "grace")
        return JSONResponse({"status": status, "tier": tier, "can_operate": can_operate})
    except Exception:
        return JSONResponse({"status": "trial", "tier": "owner_operator", "can_operate": True})


# ── Timecard start/stop ────────────────────────────────────────────────────────

@oo_router.post("/api/platform/timecard/start")
async def timecard_start(request: Request):
    data = await request.json()
    account_id = data.get("account_id", "")
    if not account_id:
        raise HTTPException(400, "account_id required")
    entry_id = str(uuid.uuid4())
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timecard_entries (
            id TEXT PRIMARY KEY, account_id TEXT, user_id TEXT, project_id TEXT,
            task_label TEXT, start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP, duration_min REAL, source TEXT DEFAULT 'manual',
            notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        UPDATE timecard_entries SET end_time=CURRENT_TIMESTAMP,
        duration_min=(julianday('now')-julianday(start_time))*1440
        WHERE account_id=? AND end_time IS NULL
    """, (account_id,))
    cur.execute("""
        INSERT INTO timecard_entries (id, account_id, task_label, source)
        VALUES (?, ?, ?, ?)
    """, (entry_id, account_id, data.get("task_label",""), data.get("source","desktop")))
    conn.commit()
    conn.close()
    return JSONResponse({"entry_id": entry_id, "message": "Timer started"}, status_code=201)


@oo_router.post("/api/platform/timecard/stop")
async def timecard_stop(request: Request):
    data = await request.json()
    account_id = data.get("account_id", "")
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE timecard_entries SET end_time=CURRENT_TIMESTAMP,
        duration_min=(julianday('now')-julianday(start_time))*1440
        WHERE account_id=? AND end_time IS NULL
    """, (account_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"message": "Timer stopped"})


@oo_router.get("/api/platform/timecard/report/{account_id}")
async def timecard_report(account_id: str):
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT SUM(duration_min), COUNT(*) FROM timecard_entries
        WHERE account_id=? AND start_time >= datetime('now','-7 days')
    """, (account_id,))
    row = cur.fetchone()
    conn.close()
    total_min = row[0] or 0
    return JSONResponse({"total_hours": round(total_min/60, 2), "entry_count": row[1] or 0,
                          "billable_hours": round(total_min/60, 2), "entries": []})


# ── Onboarding ────────────────────────────────────────────────────────────────

@oo_router.post("/api/platform/onboard/start")
async def onboard_start(request: Request):
    data = await request.json()
    account_id = data.get("account_id", "")
    user_count = int(data.get("user_count") or 1)
    if not account_id:
        raise HTTPException(400, "account_id required")
    if user_count <= 3:
        return JSONResponse({"error": "4+ users required for org onboarding",
                             "recommendation": "Use Owner-Operator mode for 1-3 users"}, status_code=400)
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS onboarding_sessions (
            id TEXT PRIMARY KEY, account_id TEXT, phase TEXT DEFAULT 'interview',
            interview_answers TEXT DEFAULT '[]', current_question_idx INTEGER DEFAULT 0,
            module_plan TEXT DEFAULT '[]', plan_approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("INSERT INTO onboarding_sessions (id, account_id) VALUES (?,?)", (session_id, account_id))
    conn.commit()
    conn.close()
    return JSONResponse({
        "session_id": session_id,
        "total_questions": 10,
        "current_question": {"index": 0, "question": "How many people work here, and what does each person primarily do?", "hint": "e.g. '5 people: 1 owner, 2 field techs, 1 office manager, 1 sales rep'"}
    }, status_code=201)


@oo_router.get("/api/platform/onboard/status/{account_id}")
async def onboard_status(account_id: str):
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, phase, current_question_idx, plan_approved FROM onboarding_sessions WHERE account_id=? ORDER BY created_at DESC LIMIT 1", (account_id,))
        row = cur.fetchone()
    except Exception:
        row = None
    conn.close()
    if not row:
        return JSONResponse({"status": "not_started"})
    return JSONResponse({"session_id": row[0], "phase": row[1], "question_idx": row[2], "plan_approved": bool(row[3])})


# ── HITL pages ────────────────────────────────────────────────────────────────

@oo_router.get("/hitl/{hitl_id}/approve", include_in_schema=False)
async def hitl_approve_page(hitl_id: str):
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Murphy — Approve</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid #1e2535;border-radius:16px;padding:40px;max-width:480px;width:90%;text-align:center}}
.icon{{font-size:48px;margin-bottom:16px}}h1{{font-size:22px;font-weight:700;color:#fff;margin-bottom:8px}}
p{{color:#9ca3af;font-size:15px;line-height:1.5;margin-bottom:24px}}
.btn{{display:inline-block;padding:12px 32px;border-radius:8px;font-size:16px;font-weight:600;border:none;cursor:pointer;background:#22c55e;color:#fff}}
.result{{padding:12px;border-radius:8px;font-size:14px;margin-top:16px;background:#14532d;color:#4ade80;display:none}}</style>
</head><body><div class="card"><div class="icon">✅</div><h1>Approve this action</h1>
<p>Murphy is waiting for your go-ahead. Click below to approve.</p>
<button class="btn" id="btn" onclick="doIt()">✓ Approve Action</button>
<div id="result" class="result"></div></div>
<script>
async function doIt(){{
  document.getElementById('btn').disabled=true;
  document.getElementById('btn').textContent='Processing...';
  const r=await fetch('/api/oo/hitl/respond',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hitl_id:'{hitl_id}',response:'approve'}})}});
  document.getElementById('result').style.display='block';
  document.getElementById('result').textContent='✓ Action approved. Murphy will execute during your automation window.';
  document.getElementById('btn').style.display='none';
}}
</script></body></html>"""
    return HTMLResponse(html)


@oo_router.get("/hitl/{hitl_id}/reject", include_in_schema=False)
async def hitl_reject_page(hitl_id: str):
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Murphy — Reject</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid #1e2535;border-radius:16px;padding:40px;max-width:480px;width:90%;text-align:center}}
.icon{{font-size:48px;margin-bottom:16px}}h1{{font-size:22px;font-weight:700;color:#fff;margin-bottom:8px}}
p{{color:#9ca3af;font-size:15px;line-height:1.5;margin-bottom:24px}}
.btn{{display:inline-block;padding:12px 32px;border-radius:8px;font-size:16px;font-weight:600;border:none;cursor:pointer;background:#ef4444;color:#fff}}
.result{{padding:12px;border-radius:8px;font-size:14px;margin-top:16px;background:#7f1d1d;color:#fca5a5;display:none}}</style>
</head><body><div class="card"><div class="icon">🚫</div><h1>Reject this action</h1>
<p>Click below to reject. Murphy will not take this action.</p>
<button class="btn" id="btn" onclick="doIt()">✗ Reject Action</button>
<div id="result" class="result"></div></div>
<script>
async function doIt(){{
  document.getElementById('btn').disabled=true;
  document.getElementById('btn').textContent='Processing...';
  const r=await fetch('/api/oo/hitl/respond',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hitl_id:'{hitl_id}',response:'reject'}})}});
  document.getElementById('result').style.display='block';
  document.getElementById('result').textContent='✗ Action rejected. Murphy will not proceed.';
  document.getElementById('btn').style.display='none';
}}
</script></body></html>"""
    return HTMLResponse(html)
