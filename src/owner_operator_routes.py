"""
PATCH-329 — Owner-Operator SaaS: Full Pipeline
Routes: /api/oo/* (owner-operator namespace)

Wire into production_router.py with:
  from owner_operator_routes import register_owner_operator_routes
  register_owner_operator_routes(app)

DB: /var/lib/murphy-production/owner_operator.db
"""

import uuid
import sqlite3
import json
import re
from datetime import datetime, timedelta
from flask import request, jsonify, current_app
from functools import wraps

OO_DB = "/var/lib/murphy-production/owner_operator.db"

# ─────────────────────────────────────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_oo_db():
    """Create all tables if they don't exist."""
    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS owner_operator_accounts (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            company_name TEXT,
            contact_name TEXT,
            phone TEXT,
            plan_tier TEXT DEFAULT '$100',
            survey_data TEXT DEFAULT '{}',
            automation_hours_start TEXT DEFAULT '23:00',
            automation_hours_end TEXT DEFAULT '06:00',
            shadow_agent_id TEXT,
            status TEXT DEFAULT 'lead',
            lead_score INTEGER DEFAULT 0,
            lead_routing TEXT DEFAULT 'nurture',
            source TEXT DEFAULT 'website',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS saas_appointments (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            slot_date TEXT,
            slot_time TEXT,
            slot_tz TEXT DEFAULT 'America/Los_Angeles',
            outcome TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS saas_contracts (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            total_contract_value REAL,
            currency TEXT DEFAULT 'USD',
            scope TEXT,
            payment_terms TEXT DEFAULT '60% at booking, 40% at delivery',
            signed_date TEXT,
            first_payment_received TEXT,
            payment_pct_received REAL DEFAULT 0,
            backlog_activation_date TEXT,
            status TEXT DEFAULT 'draft',
            contract_text TEXT,
            sent_at TIMESTAMP,
            signed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS saas_work_backlog (
            id TEXT PRIMARY KEY,
            contract_id TEXT NOT NULL,
            account_id TEXT NOT NULL,
            task_description TEXT,
            priority INTEGER DEFAULT 3,
            estimated_hours REAL DEFAULT 0,
            phase TEXT DEFAULT 'discovery',
            activation_date TEXT,
            start_date TEXT,
            completed_date TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES saas_contracts(id)
        );

        CREATE TABLE IF NOT EXISTS shadow_observations (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            action_type TEXT,
            action_data TEXT DEFAULT '{}',
            pattern_id TEXT,
            confidence_delta REAL DEFAULT 0.01,
            observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS shadow_patterns (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            pattern_name TEXT,
            pattern_type TEXT,
            confidence REAL DEFAULT 0.0,
            sample_count INTEGER DEFAULT 0,
            pattern_data TEXT DEFAULT '{}',
            proposed_automation INTEGER DEFAULT 0,
            automation_approved INTEGER DEFAULT 0,
            automation_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS hitl_queue (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            action_type TEXT,
            action_description TEXT,
            action_data TEXT DEFAULT '{}',
            requires_approval INTEGER DEFAULT 1,
            approved_by TEXT,
            approved_at TIMESTAMP,
            expires_at TIMESTAMP,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS automation_runs (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            workflow_id TEXT,
            workflow_name TEXT,
            triggered_by TEXT DEFAULT 'schedule',
            status TEXT DEFAULT 'pending',
            output_summary TEXT,
            duration_ms INTEGER,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS employment_gap_reports (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            document_name TEXT,
            document_text TEXT,
            parsed_roles TEXT DEFAULT '[]',
            observed_gaps TEXT DEFAULT '[]',
            recommendations TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );

        CREATE TABLE IF NOT EXISTS integration_metrics (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            integration_type TEXT,
            metric_name TEXT,
            metric_value REAL,
            measurement_date TEXT,
            trend TEXT DEFAULT 'flat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES owner_operator_accounts(id)
        );
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def score_oo_lead(data: dict) -> tuple[int, str]:
    """
    Score a lead 1-10.
    Routing:
      < 7  → nurture (email drip)
      7-9  → book (appointment auto-offered)
      10   → enterprise (founder personal outreach)
    Returns: (score, routing)
    """
    score = 4  # baseline

    employees = int(data.get('company_size') or data.get('employees') or 0)
    if employees >= 50:   score += 3
    elif employees >= 20: score += 2
    elif employees >= 5:  score += 1

    industry = (data.get('industry') or '').lower()
    hi_val = ['manufacturing', 'finance', 'healthcare', 'energy', 'logistics',
              'construction', 'engineering', 'real estate', 'legal', 'insurance']
    if any(i in industry for i in hi_val):
        score += 2

    revenue = float(data.get('annual_revenue') or 0)
    if revenue >= 10_000_000:  score += 2
    elif revenue >= 1_000_000: score += 1

    team = int(data.get('team_size') or 0)
    if team >= 20:  score += 2
    elif team >= 5: score += 1

    use = (data.get('use_case') or data.get('biggest_pain') or '').lower()
    good = ['automation', 'lead', 'appointment', 'proposal', 'back office',
            'follow-up', 'contract', 'scheduling', 'dispatch', 'invoicing']
    if any(g in use for g in good):
        score += 1

    score = min(10, max(1, score))

    if score < 7:    routing = 'nurture'
    elif score <= 9: routing = 'book'
    else:            routing = 'enterprise'

    return score, routing


# ─────────────────────────────────────────────────────────────────────────────
# HITL DISPATCHER (internal)
# ─────────────────────────────────────────────────────────────────────────────

def queue_hitl(account_id: str, action_type: str, description: str,
               action_data: dict, ttl_hours: int = 24) -> str:
    """
    Queue a HITL approval request. Returns hitl_id.
    Every money/customer/org-chart action MUST go through here first.
    """
    hitl_id = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(hours=ttl_hours)

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO hitl_queue
        (id, account_id, action_type, action_description, action_data, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (hitl_id, account_id, action_type, description,
          json.dumps(action_data), expires.isoformat()))
    conn.commit()
    conn.close()

    # Try to fire a real notification (email/SMS via existing murphy SMTP)
    try:
        _send_hitl_notification(account_id, action_type, description, hitl_id)
    except Exception:
        pass  # Never block on notification failure

    return hitl_id


def _send_hitl_notification(account_id: str, action_type: str,
                            description: str, hitl_id: str):
    """Send HITL alert to account owner via SMTP."""
    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("SELECT email, contact_name FROM owner_operator_accounts WHERE id=?",
                (account_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return

    email, name = row
    name = name or email

    subject = f"[Murphy Alert] Action Queued: {action_type}"
    body = f"""Hi {name},

Murphy has queued the following action and is waiting for your approval:

ACTION: {action_type}
DESCRIPTION:
{description}

To approve: Reply YES to this email or visit https://murphy.systems/hitl/{hitl_id}/approve
To reject:  Reply NO or visit https://murphy.systems/hitl/{hitl_id}/reject

This request expires in 24 hours.

— Murphy, your autonomous business operator
"""

    # Wire to existing Murphy SMTP (same pattern as existing email sends)
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'murphy@murphy.systems'
        msg['To'] = email
        with smtplib.SMTP_SSL('localhost', 465, timeout=10) as s:
            s.login('murphy@murphy.systems', 'murphy_smtp_pass')
            s.send_message(msg)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/survey  (Intake survey → account + org scaffold)
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_survey():
    """
    Takes the intake survey, creates the account, scores the lead,
    scaffolds the org chart, creates the shadow agent slot.

    Body:
    {
        "email": "owner@company.com",
        "contact_name": "Jane Smith",
        "company_name": "Acme Plumbing",
        "phone": "+1-503-555-0199",
        "industry": "Plumbing / HVAC",
        "employees": 3,
        "annual_revenue": 420000,
        "team_size": 3,
        "roles": ["Owner/Estimator", "Field Tech", "Office Manager"],
        "daily_tasks": ["follow up on quotes", "schedule jobs", "invoice customers"],
        "wished_automated": ["follow-ups", "scheduling", "invoicing"],
        "current_tools": ["QuickBooks", "Google Calendar", "email"],
        "automation_hours_start": "22:00",
        "automation_hours_end": "06:00",
        "biggest_pain": "I spend 3 hours a day on follow-ups and they still fall through",
        "growth_goal": "double revenue without hiring"
    }
    """
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"error": "Valid email required"}), 400

    score, routing = score_oo_lead(data)

    account_id = str(uuid.uuid4())
    shadow_agent_id = f"shadow_{account_id[:8]}"

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    # Upsert
    cur.execute("SELECT id FROM owner_operator_accounts WHERE email=?", (email,))
    existing = cur.fetchone()

    if existing:
        account_id = existing[0]
        cur.execute("""
            UPDATE owner_operator_accounts
            SET company_name=?, contact_name=?, phone=?, survey_data=?,
                automation_hours_start=?, automation_hours_end=?,
                lead_score=?, lead_routing=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (data.get('company_name'), data.get('contact_name'), data.get('phone'),
              json.dumps(data),
              data.get('automation_hours_start', '23:00'),
              data.get('automation_hours_end', '06:00'),
              score, routing, account_id))
    else:
        cur.execute("""
            INSERT INTO owner_operator_accounts
            (id, email, company_name, contact_name, phone, plan_tier, survey_data,
             automation_hours_start, automation_hours_end, shadow_agent_id,
             status, lead_score, lead_routing, source)
            VALUES (?, ?, ?, ?, ?, '$100', ?, ?, ?, ?, 'lead', ?, ?, 'website')
        """, (account_id, email, data.get('company_name'), data.get('contact_name'),
              data.get('phone'), json.dumps(data),
              data.get('automation_hours_start', '23:00'),
              data.get('automation_hours_end', '06:00'),
              shadow_agent_id, score, routing))

    conn.commit()
    conn.close()

    # Build org scaffold from roles
    roles = data.get('roles', ['Owner'])
    org_chart = _scaffold_org(account_id, roles, data.get('employees', 1))

    # Identify workflows from Murphy GitHub that match their needs
    workflow_map = _map_workflows_to_needs(
        data.get('wished_automated', []),
        data.get('daily_tasks', [])
    )

    return jsonify({
        "account_id": account_id,
        "shadow_agent_id": shadow_agent_id,
        "lead_score": score,
        "routing": routing,
        "message": {
            "nurture": "Thanks! We'll send you some resources and follow up in a few days.",
            "book": "Great fit! Let's schedule a 20-minute call to map out your setup.",
            "enterprise": "You're exactly who Murphy was built for. Corey will reach out personally."
        }.get(routing),
        "org_chart_scaffold": org_chart,
        "identified_workflows": workflow_map,
        "automation_hours": {
            "start": data.get('automation_hours_start', '23:00'),
            "end": data.get('automation_hours_end', '06:00'),
            "description": f"Murphy will run autonomously {data.get('automation_hours_start','23:00')} – {data.get('automation_hours_end','06:00')} daily"
        },
        "next_step": {
            "nurture": "Check your email for resources",
            "book": "Book your call at murphy.systems/book",
            "enterprise": "Corey will email you within 24 hours"
        }.get(routing)
    }), 201


def _scaffold_org(account_id: str, roles: list, employee_count: int) -> dict:
    """Build an org chart scaffold from stated roles."""
    nodes = []
    for role in roles:
        node_id = str(uuid.uuid4())[:8]
        nodes.append({
            "id": node_id,
            "title": role,
            "shadow_agent": f"shadow_{node_id}",
            "agent_type": "SHADOW",
            "status": "observing",
            "confidence": 0.0,
            "patterns_learned": 0
        })

    # If solo operator, all shadow points to the owner
    if employee_count <= 1:
        for n in nodes:
            n["shadowed_user"] = account_id
            n["note"] = "All roles observed on single owner — shadow will learn all patterns"

    return {
        "account_id": account_id,
        "total_roles": len(nodes),
        "nodes": nodes,
        "mode": "owner_operator" if employee_count <= 2 else "small_team"
    }


def _map_workflows_to_needs(wished: list, daily: list) -> list:
    """
    Map the user's stated needs to existing Murphy GitHub workflows.
    Returns list of matching workflow modules.
    """
    MURPHY_WORKFLOWS = {
        "follow-up": {
            "module": "/api/apc/call-script",
            "description": "Automated follow-up sequence (email + SMS)",
            "confidence": 0.9
        },
        "invoice": {
            "module": "/api/commercial/proposal",
            "description": "Invoice and proposal generation",
            "confidence": 0.85
        },
        "scheduling": {
            "module": "/api/booking/create-account",
            "description": "Appointment scheduling and calendar management",
            "confidence": 0.9
        },
        "lead generation": {
            "module": "/api/apc/discover",
            "description": "Autonomous prospect discovery",
            "confidence": 0.8
        },
        "appointment": {
            "module": "/api/booking/create-account",
            "description": "Discovery call booking flow",
            "confidence": 0.95
        },
        "proposal": {
            "module": "/api/commercial/proposal",
            "description": "Automated proposal generation after call",
            "confidence": 0.85
        },
        "crm": {
            "module": "/api/crm/deals",
            "description": "Deal tracking and pipeline management",
            "confidence": 0.9
        },
        "contract": {
            "module": "/api/saas/contract/generate",
            "description": "Contract generation with e-sign",
            "confidence": 0.85
        },
        "dispatch": {
            "module": "/api/hitl/submit",
            "description": "Human-in-the-loop dispatch and approval",
            "confidence": 0.9
        }
    }

    matched = []
    all_needs = [w.lower() for w in wished + daily]

    for keyword, workflow in MURPHY_WORKFLOWS.items():
        if any(keyword in need for need in all_needs):
            matched.append({
                "keyword": keyword,
                **workflow
            })

    # Always include core modules
    core = ["follow-up", "scheduling", "crm"]
    for kw in core:
        if not any(m['keyword'] == kw for m in matched):
            matched.append({"keyword": kw, **MURPHY_WORKFLOWS[kw], "core": True})

    return matched


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/observe  (Shadow agent observation intake)
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_observe():
    """
    The shadow agent calls this whenever it observes the user doing something.
    Accumulates into patterns. When confidence >= 0.75, proposes an automation.

    Body:
    {
        "account_id": "...",
        "action_type": "sent_email" | "moved_deal" | "approved_quote" | "scheduled_job" | ...,
        "action_data": {
            "to": "client@example.com",
            "subject": "Follow-up on quote #123",
            "deal_id": "...",
            "amount": 4500
        }
    }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    action_type = data.get('action_type', '')
    action_data = data.get('action_data', {})

    if not account_id or not action_type:
        return jsonify({"error": "account_id and action_type required"}), 400

    obs_id = str(uuid.uuid4())

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    # Log observation
    cur.execute("""
        INSERT INTO shadow_observations (id, account_id, action_type, action_data)
        VALUES (?, ?, ?, ?)
    """, (obs_id, account_id, action_type, json.dumps(action_data)))

    # Find or create pattern for this action type
    cur.execute("""
        SELECT id, confidence, sample_count, proposed_automation
        FROM shadow_patterns
        WHERE account_id=? AND pattern_type=?
    """, (account_id, action_type))
    pattern = cur.fetchone()

    proposed_automation = False
    automation_proposal = None

    if pattern:
        pattern_id, confidence, count, already_proposed = pattern
        new_count = count + 1
        new_confidence = min(1.0, confidence + (0.05 / max(1, count)))

        cur.execute("""
            UPDATE shadow_patterns
            SET confidence=?, sample_count=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (new_confidence, new_count, pattern_id))

        # If confidence hits threshold and not yet proposed
        if new_confidence >= 0.75 and not already_proposed:
            cur.execute("""
                UPDATE shadow_patterns SET proposed_automation=1 WHERE id=?
            """, (pattern_id,))
            proposed_automation = True
            automation_proposal = {
                "pattern_id": pattern_id,
                "action_type": action_type,
                "confidence": new_confidence,
                "sample_count": new_count,
                "proposal": f"I've observed you doing '{action_type}' {new_count} times "
                            f"with {new_confidence:.0%} consistency. "
                            f"Want me to automate this during your automation hours?"
            }
            # Queue HITL for automation proposal
            queue_hitl(
                account_id=account_id,
                action_type="automation_proposal",
                description=automation_proposal['proposal'],
                action_data={"pattern_id": pattern_id, "action_type": action_type,
                             "confidence": new_confidence}
            )
    else:
        # Create new pattern
        pattern_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO shadow_patterns
            (id, account_id, pattern_name, pattern_type, confidence, sample_count, pattern_data)
            VALUES (?, ?, ?, ?, 0.05, 1, ?)
        """, (pattern_id, account_id, f"Auto-learned: {action_type}",
              action_type, json.dumps({"first_seen": action_data})))

    cur.execute("""
        UPDATE shadow_observations SET pattern_id=? WHERE id=?
    """, (pattern_id, obs_id))

    conn.commit()
    conn.close()

    return jsonify({
        "observation_id": obs_id,
        "pattern_id": pattern_id,
        "proposed_automation": proposed_automation,
        "automation_proposal": automation_proposal
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/appointment/book
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_book():
    """
    Book discovery appointment. Fires HITL to owner.
    Body: { account_id, slot_date, slot_time, timezone }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    slot_date = data.get('slot_date', '')
    slot_time = data.get('slot_time', '10:00')
    tz = data.get('timezone', 'America/Los_Angeles')

    if not account_id or not slot_date:
        return jsonify({"error": "account_id and slot_date required"}), 400

    appt_id = str(uuid.uuid4())

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO saas_appointments (id, account_id, slot_date, slot_time, slot_tz)
        VALUES (?, ?, ?, ?, ?)
    """, (appt_id, account_id, slot_date, slot_time, tz))

    cur.execute("""
        UPDATE owner_operator_accounts
        SET status='demo_booked', updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (account_id,))

    cur.execute("SELECT email, contact_name, company_name FROM owner_operator_accounts WHERE id=?",
                (account_id,))
    sub = cur.fetchone()
    conn.commit()
    conn.close()

    email, name, company = sub if sub else ('unknown', 'unknown', 'unknown')

    # HITL to owner: new appointment booked
    hitl_id = queue_hitl(
        account_id=account_id,
        action_type="appointment_booked",
        description=(f"New discovery call booked:\n"
                     f"  Who: {name} ({email}) from {company}\n"
                     f"  When: {slot_date} at {slot_time} {tz}\n\n"
                     f"Murphy will send them a confirmation email and prep doc. Approve?"),
        action_data={"appointment_id": appt_id, "email": email,
                     "slot": f"{slot_date} {slot_time}"}
    )

    return jsonify({
        "appointment_id": appt_id,
        "hitl_id": hitl_id,
        "slot": f"{slot_date} at {slot_time} {tz}",
        "status": "pending_owner_confirmation",
        "message": f"Call booked for {slot_date}. Your owner will receive a confirmation alert."
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/contract/generate
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_contract_generate():
    """
    Generate contract after discovery call. ALWAYS requires HITL before sending.
    Body: {
        account_id, total_contract_value, scope,
        currency (optional, default USD),
        work_items (optional list)
    }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    total_value = float(data.get('total_contract_value') or 0)
    scope = data.get('scope', '')

    if not account_id or total_value <= 0:
        return jsonify({"error": "account_id and total_contract_value required"}), 400

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT email, contact_name, company_name
        FROM owner_operator_accounts WHERE id=?
    """, (account_id,))
    sub = cur.fetchone()
    if not sub:
        conn.close()
        return jsonify({"error": "Account not found"}), 404

    email, name, company = sub
    contract_id = str(uuid.uuid4())
    deposit = total_value * 0.60
    balance = total_value * 0.40

    contract_text = _generate_contract_text(
        name=name or email,
        company=company or 'Your Company',
        email=email,
        total_value=total_value,
        scope=scope,
        deposit=deposit,
        balance=balance,
        contract_id=contract_id
    )

    cur.execute("""
        INSERT INTO saas_contracts
        (id, account_id, total_contract_value, scope, payment_terms, status, contract_text)
        VALUES (?, ?, ?, ?, '60% at booking, 40% at delivery', 'draft', ?)
    """, (contract_id, account_id, total_value, scope, contract_text))

    # Build backlog from work_items if provided
    work_items = data.get('work_items', [])
    if not work_items:
        work_items = _default_backlog_items(scope)

    for item in work_items:
        cur.execute("""
            INSERT INTO saas_work_backlog
            (id, contract_id, account_id, task_description, priority, estimated_hours, phase)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), contract_id, account_id,
              item.get('description', 'Task'),
              item.get('priority', 3),
              item.get('hours', 4),
              item.get('phase', 'discovery')))

    cur.execute("""
        UPDATE owner_operator_accounts
        SET status='proposal_sent', updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (account_id,))

    conn.commit()
    conn.close()

    # HITL: Murphy must get approval before sending
    hitl_id = queue_hitl(
        account_id=account_id,
        action_type="contract_send",
        description=(f"I've generated a contract for {name} at {company}:\n"
                     f"  Value: ${total_value:,.2f}\n"
                     f"  Deposit: ${deposit:,.2f} (60%) at booking\n"
                     f"  Balance: ${balance:,.2f} (40%) at delivery\n"
                     f"  Scope: {scope[:200]}...\n\n"
                     f"  Contract ID: {contract_id}\n\n"
                     f"Approve to email contract to {email}?"),
        action_data={"contract_id": contract_id, "to_email": email,
                     "total_value": total_value}
    )

    return jsonify({
        "contract_id": contract_id,
        "hitl_id": hitl_id,
        "status": "draft_pending_approval",
        "total_value": total_value,
        "deposit_required": deposit,
        "balance_due": balance,
        "work_items_queued": len(work_items),
        "message": f"Contract drafted (${total_value:,.2f}). Waiting for your approval before sending to {email}."
    }), 201


def _generate_contract_text(name, company, email, total_value, scope,
                             deposit, balance, contract_id) -> str:
    today = datetime.utcnow().strftime('%B %d, %Y')
    activation = (datetime.utcnow() + timedelta(days=180)).strftime('%B %d, %Y')

    return f"""MURPHY SYSTEMS — SERVICE AGREEMENT
Contract ID: {contract_id}
Date: {today}

CLIENT:
  Name: {name}
  Company: {company}
  Email: {email}

SERVICE PROVIDER:
  Murphy Systems (murphy.systems)
  Contact: Corey Post, Founder

─────────────────────────────────────
SCOPE OF WORK
─────────────────────────────────────
{scope}

─────────────────────────────────────
PAYMENT TERMS
─────────────────────────────────────
Total Contract Value:   ${total_value:,.2f} USD
Deposit (60% at booking): ${deposit:,.2f} USD — due upon contract signature
Balance (40% at delivery): ${balance:,.2f} USD — due at project completion

BACKLOG ACTIVATION:
Work begins {activation} (6 months from date of first signed contract).
Murphy Systems will execute all deliverables autonomously during designated
automation hours, with HITL approval required for all decisions affecting
money, customers, or organizational structure.

─────────────────────────────────────
TERMS
─────────────────────────────────────
1. Murphy Systems retains full IP ownership of all automation frameworks,
   agents, and workflows. The client receives a perpetual license to use
   the configured system for their business operations.

2. The shadow agent will observe the client's workflows for the 6-month
   onboarding period and build pattern-matched automations tailored to
   their specific operation.

3. All autonomous actions that affect money, customers, or org structure
   require HITL (human-in-the-loop) approval before execution.

4. This agreement auto-renews at $100/month after the initial contract term.

5. Either party may terminate with 30 days written notice.

─────────────────────────────────────
SIGNATURES
─────────────────────────────────────
Client: ____________________________  Date: ___________

Murphy Systems: ____________________  Date: ___________
               Corey Post, Founder
"""


def _default_backlog_items(scope: str) -> list:
    """Generate default backlog items when none are specified."""
    base_items = [
        {"description": "Discovery & intake survey analysis", "priority": 1, "hours": 2, "phase": "discovery"},
        {"description": "Shadow agent configuration & observation period", "priority": 1, "hours": 40, "phase": "discovery"},
        {"description": "Workflow mapping (Murphy GitHub → client needs)", "priority": 2, "hours": 8, "phase": "planning"},
        {"description": "Lead capture form deployment on client website", "priority": 2, "hours": 4, "phase": "development"},
        {"description": "CRM setup & deal pipeline configuration", "priority": 2, "hours": 6, "phase": "development"},
        {"description": "Email automation sequences (nurture/book/enterprise)", "priority": 2, "hours": 8, "phase": "development"},
        {"description": "Appointment booking integration", "priority": 2, "hours": 4, "phase": "development"},
        {"description": "Contract generation & e-sign integration", "priority": 3, "hours": 6, "phase": "development"},
        {"description": "HITL dashboard configuration", "priority": 2, "hours": 4, "phase": "development"},
        {"description": "Automation hours scheduling (user-configured window)", "priority": 2, "hours": 3, "phase": "development"},
        {"description": "Integration metrics baseline + weekly reporting", "priority": 3, "hours": 4, "phase": "testing"},
        {"description": "Go-live + owner orientation session", "priority": 1, "hours": 2, "phase": "deployment"},
    ]
    return base_items


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/payment/received
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_payment():
    """
    Log a payment received. If payment_pct >= 60% AND contract is signed,
    activate the work backlog 6 months from the FIRST signed contract date.

    Body: { contract_id, amount_paid, payment_reference }
    """
    data = request.get_json() or {}
    contract_id = data.get('contract_id', '')
    amount_paid = float(data.get('amount_paid') or 0)

    if not contract_id or amount_paid <= 0:
        return jsonify({"error": "contract_id and amount_paid required"}), 400

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, account_id, total_contract_value, payment_pct_received,
               signed_date, status, first_payment_received
        FROM saas_contracts WHERE id=?
    """, (contract_id,))
    contract = cur.fetchone()
    if not contract:
        conn.close()
        return jsonify({"error": "Contract not found"}), 404

    cid, account_id, total_value, current_pct, signed_date, status, first_pmt = contract
    new_pct = current_pct + (amount_paid / total_value * 100)

    backlog_activation_date = None
    backlog_activated = False

    # Find the FIRST signed contract for this account
    cur.execute("""
        SELECT MIN(signed_date) FROM saas_contracts
        WHERE account_id=? AND status IN ('signed', 'active') AND signed_date IS NOT NULL
    """, (account_id,))
    first_signed = cur.fetchone()[0]

    if new_pct >= 60 and signed_date:
        # Use first signed contract date for the 6-month clock
        ref_date = datetime.fromisoformat(first_signed) if first_signed else datetime.utcnow()
        activation_dt = ref_date + timedelta(days=182)  # ~6 months
        backlog_activation_date = activation_dt.strftime('%Y-%m-%d')
        backlog_activated = True

        # Activate all backlog items for this contract
        cur.execute("""
            UPDATE saas_work_backlog
            SET activation_date=?, status='queued'
            WHERE contract_id=? AND status='pending'
        """, (backlog_activation_date, contract_id))

    # Update contract
    cur.execute("""
        UPDATE saas_contracts
        SET payment_pct_received=?,
            first_payment_received=COALESCE(first_payment_received, CURRENT_TIMESTAMP),
            backlog_activation_date=COALESCE(backlog_activation_date, ?),
            status=CASE WHEN ? >= 60 THEN 'active' ELSE status END,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (new_pct, backlog_activation_date, new_pct, contract_id))

    # Update account status
    if new_pct >= 60:
        cur.execute("""
            UPDATE owner_operator_accounts
            SET status='active', activated_at=COALESCE(activated_at, CURRENT_TIMESTAMP),
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (account_id,))

    conn.commit()
    conn.close()

    # HITL if backlog activated
    if backlog_activated:
        queue_hitl(
            account_id=account_id,
            action_type="backlog_activation",
            description=(f"Payment threshold reached ({new_pct:.1f}% of contract).\n"
                         f"Work backlog will activate on {backlog_activation_date}.\n"
                         f"This is 6 months from the first signed contract.\n"
                         f"Murphy will begin executing {len(_default_backlog_items(''))} work items on that date.\n\n"
                         f"Acknowledge?"),
            action_data={"contract_id": contract_id, "activation_date": backlog_activation_date,
                         "payment_pct": new_pct}
        )

    return jsonify({
        "contract_id": contract_id,
        "payment_pct": round(new_pct, 1),
        "backlog_activated": backlog_activated,
        "backlog_activation_date": backlog_activation_date,
        "message": (f"Payment recorded ({new_pct:.1f}% of contract). "
                    + (f"Backlog activates {backlog_activation_date}."
                       if backlog_activated
                       else f"Need {60 - new_pct:.1f}% more to activate backlog."))
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/contract/signed
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_contract_signed():
    """
    Called by e-sign webhook when client signs contract.
    Sets signed_date — this is the anchor for the 6-month backlog clock.
    """
    data = request.get_json() or {}
    contract_id = data.get('contract_id', '')
    if not contract_id:
        return jsonify({"error": "contract_id required"}), 400

    today = datetime.utcnow().isoformat()

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE saas_contracts
        SET signed_date=?, signed_at=CURRENT_TIMESTAMP, status='signed',
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (today, contract_id))

    cur.execute("SELECT account_id FROM saas_contracts WHERE id=?", (contract_id,))
    row = cur.fetchone()
    account_id = row[0] if row else None

    if account_id:
        cur.execute("""
            UPDATE owner_operator_accounts
            SET status='contract_signed', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (account_id,))

    conn.commit()
    conn.close()

    if account_id:
        queue_hitl(
            account_id=account_id,
            action_type="contract_signed",
            description=(f"Contract {contract_id} has been signed by the client.\n"
                         f"Signed date: {today[:10]}\n"
                         f"Backlog clock starts today. Work begins 6 months from now.\n"
                         f"Next step: Confirm payment receipt to activate backlog."),
            action_data={"contract_id": contract_id, "signed_date": today[:10]}
        )

    return jsonify({
        "contract_id": contract_id,
        "signed_date": today[:10],
        "backlog_clock_started": True,
        "backlog_activation_target": (datetime.utcnow() + timedelta(days=182)).strftime('%Y-%m-%d'),
        "message": "Contract signed. Backlog clock started. 6-month countdown begins today."
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/gap-report  (Employment gap detection)
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_gap_report():
    """
    Parse an uploaded employment contract/offer letter.
    Compare stated responsibilities to observed shadow patterns.
    Generate gap report: what's in the JD but not being done → automation candidate.

    Body: { account_id, document_name, document_text }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    doc_name = data.get('document_name', 'untitled_document')
    doc_text = data.get('document_text', '')

    if not account_id or not doc_text:
        return jsonify({"error": "account_id and document_text required"}), 400

    # Parse responsibilities from document
    roles_found = _parse_roles_from_jd(doc_text)

    # Get observed patterns for this account
    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT pattern_type, confidence, sample_count
        FROM shadow_patterns WHERE account_id=?
    """, (account_id,))
    patterns = [{"type": r[0], "confidence": r[1], "count": r[2]}
                for r in cur.fetchall()]

    # Compare
    observed_types = {p['type'].lower() for p in patterns}
    gaps = []
    recommendations = []

    for role in roles_found:
        role_lower = role.lower()
        covered = any(obs in role_lower or role_lower in obs for obs in observed_types)

        if not covered:
            gaps.append({
                "responsibility": role,
                "status": "not_observed",
                "coverage": "0%",
                "recommendation": f"No activity observed for '{role}'. Candidate for automation or hire."
            })

            rec_type = _classify_gap_recommendation(role)
            recommendations.append({
                "responsibility": role,
                "type": rec_type,
                "action": {
                    "automate": f"Murphy can automate this — ask Murphy to build a '{role}' workflow",
                    "hire": f"Consider hiring for this role or outsourcing",
                    "train": f"Shadow agent will learn this once you start performing these tasks"
                }.get(rec_type, "Review and decide")
            })

    report_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO employment_gap_reports
        (id, account_id, document_name, document_text, parsed_roles,
         observed_gaps, recommendations)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (report_id, account_id, doc_name, doc_text,
          json.dumps(roles_found), json.dumps(gaps), json.dumps(recommendations)))
    conn.commit()
    conn.close()

    # HITL if significant gaps found
    if len(gaps) >= 3:
        queue_hitl(
            account_id=account_id,
            action_type="employment_gap_report",
            description=(f"Gap report complete for '{doc_name}':\n"
                         f"  {len(roles_found)} responsibilities identified\n"
                         f"  {len(gaps)} gaps found (not yet automated or observed)\n"
                         f"  {len([r for r in recommendations if r['type'] == 'automate'])} automation candidates\n"
                         f"  {len([r for r in recommendations if r['type'] == 'hire'])} hire candidates\n\n"
                         f"Review the full report at murphy.systems/dashboard/gaps/{report_id}"),
            action_data={"report_id": report_id, "gaps": len(gaps)}
        )

    return jsonify({
        "report_id": report_id,
        "document": doc_name,
        "responsibilities_found": len(roles_found),
        "gaps_identified": len(gaps),
        "gaps": gaps,
        "recommendations": recommendations,
        "automation_candidates": len([r for r in recommendations if r['type'] == 'automate']),
        "hire_candidates": len([r for r in recommendations if r['type'] == 'hire'])
    }), 201


def _parse_roles_from_jd(doc_text: str) -> list:
    """Extract list of responsibilities from job description text."""
    # Look for bullet points, numbered lists, responsibility sections
    lines = doc_text.split('\n')
    roles = []

    responsibility_sections = False
    keywords = ['responsibilit', 'duties', 'what you will', 'what you\'ll',
                 'your role', 'key tasks', 'essential functions']

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect responsibility section headers
        if any(k in line.lower() for k in keywords):
            responsibility_sections = True
            continue

        # Collect bullet points in responsibility sections
        if responsibility_sections:
            if re.match(r'^[\-•*→◦▸►]', line) or re.match(r'^\d+[\.\)]', line):
                cleaned = re.sub(r'^[\-•*→◦▸►\d\.]+\s*', '', line).strip()
                if len(cleaned) > 10:
                    roles.append(cleaned)
            elif line.isupper() or line.endswith(':'):
                # New section — keep collecting
                pass

    # Fallback: find lines with action verbs if no bullets found
    if not roles:
        action_verbs = ['manage', 'coordinate', 'develop', 'execute', 'lead',
                        'oversee', 'handle', 'process', 'schedule', 'maintain',
                        'track', 'report', 'communicate', 'ensure', 'create']
        for line in lines:
            line = line.strip()
            if any(line.lower().startswith(v) for v in action_verbs) and len(line) > 15:
                roles.append(line)

    return roles[:25]  # Cap at 25


def _classify_gap_recommendation(responsibility: str) -> str:
    """Classify a gap as automate, hire, or train."""
    automate_keywords = ['email', 'follow-up', 'report', 'invoice', 'schedule',
                         'notify', 'update', 'track', 'log', 'send', 'record']
    hire_keywords = ['manage', 'lead', 'strategy', 'negotiate', 'present',
                     'client relationship', 'team', 'mentor']

    r = responsibility.lower()
    if any(k in r for k in automate_keywords):
        return 'automate'
    elif any(k in r for k in hire_keywords):
        return 'hire'
    else:
        return 'train'


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: GET /api/oo/dashboard/{account_id}
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_dashboard(account_id):
    """
    Full owner dashboard: account status, contracts, backlog, patterns,
    HITL queue, integration metrics.
    """
    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    # Account
    cur.execute("""
        SELECT email, company_name, contact_name, status, lead_score, lead_routing,
               automation_hours_start, automation_hours_end, shadow_agent_id,
               created_at, activated_at
        FROM owner_operator_accounts WHERE id=?
    """, (account_id,))
    acct = cur.fetchone()
    if not acct:
        conn.close()
        return jsonify({"error": "Account not found"}), 404

    # Contracts
    cur.execute("""
        SELECT id, total_contract_value, payment_pct_received, status,
               signed_date, backlog_activation_date
        FROM saas_contracts WHERE account_id=?
    """, (account_id,))
    contracts = [{"id": r[0], "value": r[1], "payment_pct": r[2],
                  "status": r[3], "signed_date": r[4], "backlog_activates": r[5]}
                 for r in cur.fetchall()]

    # Backlog
    cur.execute("""
        SELECT id, task_description, phase, priority, status, activation_date
        FROM saas_work_backlog WHERE account_id=?
        ORDER BY priority, phase
    """, (account_id,))
    backlog = [{"id": r[0], "task": r[1], "phase": r[2], "priority": r[3],
                "status": r[4], "activates": r[5]}
               for r in cur.fetchall()]

    # Shadow patterns
    cur.execute("""
        SELECT pattern_type, confidence, sample_count, proposed_automation, automation_approved
        FROM shadow_patterns WHERE account_id=?
        ORDER BY confidence DESC
    """, (account_id,))
    patterns = [{"type": r[0], "confidence": f"{r[1]:.0%}", "observations": r[2],
                 "proposed": bool(r[3]), "approved": bool(r[4])}
                for r in cur.fetchall()]

    # HITL queue (pending only)
    cur.execute("""
        SELECT id, action_type, action_description, status, created_at, expires_at
        FROM hitl_queue WHERE account_id=? AND status='pending'
        ORDER BY created_at DESC
    """, (account_id,))
    hitl = [{"id": r[0], "action": r[1], "description": r[2][:100],
             "status": r[3], "created": r[4], "expires": r[5]}
            for r in cur.fetchall()]

    # Integration metrics (last 7 days)
    cur.execute("""
        SELECT integration_type, metric_name, metric_value, trend, measurement_date
        FROM integration_metrics WHERE account_id=?
        AND measurement_date >= date('now', '-7 days')
        ORDER BY measurement_date DESC
    """, (account_id,))
    metrics = [{"integration": r[0], "metric": r[1], "value": r[2],
                "trend": r[3], "date": r[4]}
               for r in cur.fetchall()]

    conn.close()

    # Days until backlog activates
    backlog_clock = None
    for c in contracts:
        if c.get('backlog_activates'):
            try:
                act_dt = datetime.strptime(c['backlog_activates'], '%Y-%m-%d')
                days_left = (act_dt - datetime.utcnow()).days
                backlog_clock = {
                    "activation_date": c['backlog_activates'],
                    "days_remaining": max(0, days_left),
                    "status": "active" if days_left <= 0 else "counting_down"
                }
            except Exception:
                pass
        break

    return jsonify({
        "account": {
            "id": account_id,
            "email": acct[0],
            "company": acct[1],
            "contact": acct[2],
            "status": acct[3],
            "lead_score": acct[4],
            "routing": acct[5],
            "automation_hours": f"{acct[6]} – {acct[7]}",
            "shadow_agent": acct[8],
            "member_since": acct[9],
            "activated_at": acct[10]
        },
        "contracts": contracts,
        "backlog": {
            "clock": backlog_clock,
            "items": backlog,
            "total": len(backlog),
            "queued": len([b for b in backlog if b['status'] == 'queued']),
            "active": len([b for b in backlog if b['status'] == 'active']),
            "completed": len([b for b in backlog if b['status'] == 'completed'])
        },
        "shadow_agent": {
            "patterns_learned": len(patterns),
            "top_patterns": patterns[:5],
            "pending_proposals": len([p for p in patterns if p['proposed'] and not p['approved']])
        },
        "hitl_queue": {
            "pending": len(hitl),
            "items": hitl
        },
        "metrics": metrics
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: POST /api/oo/hitl/respond  (Approve or reject queued action)
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_hitl_respond():
    """
    Owner approves or rejects a queued HITL action.
    Body: { hitl_id, response: "approve" | "reject", notes: "..." }
    """
    data = request.get_json() or {}
    hitl_id = data.get('hitl_id', '')
    response = data.get('response', '').lower()

    if not hitl_id or response not in ('approve', 'reject', 'yes', 'no'):
        return jsonify({"error": "hitl_id and response (approve/reject) required"}), 400

    approved = response in ('approve', 'yes')
    status = 'approved' if approved else 'rejected'

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE hitl_queue
        SET status=?, approved_by='owner', approved_at=CURRENT_TIMESTAMP
        WHERE id=? AND status='pending'
    """, (status, hitl_id))
    affected = cur.rowcount

    cur.execute("SELECT action_type, action_data, account_id FROM hitl_queue WHERE id=?",
                (hitl_id,))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if affected == 0:
        return jsonify({"error": "HITL item not found or already resolved"}), 404

    action_type = row[0] if row else 'unknown'
    action_data = json.loads(row[1]) if row else {}
    account_id = row[2] if row else None

    # Post-approval execution hooks
    result = None
    if approved:
        result = _execute_hitl_action(action_type, action_data, account_id)

    return jsonify({
        "hitl_id": hitl_id,
        "status": status,
        "action_type": action_type,
        "execution_result": result,
        "message": f"Action {status}. {'Execution triggered.' if approved and result else ''}"
    }), 200


def _execute_hitl_action(action_type: str, action_data: dict, account_id: str):
    """Execute the action after HITL approval."""
    if action_type == "contract_send":
        # Would trigger email send to client
        return {"triggered": "contract_email", "status": "queued"}
    elif action_type == "automation_proposal":
        # Activate the proposed automation
        pattern_id = action_data.get('pattern_id')
        if pattern_id:
            conn = sqlite3.connect(OO_DB)
            cur = conn.cursor()
            cur.execute("UPDATE shadow_patterns SET automation_approved=1 WHERE id=?",
                        (pattern_id,))
            conn.commit()
            conn.close()
        return {"triggered": "automation_activated", "pattern_id": pattern_id}
    elif action_type == "backlog_activation":
        return {"triggered": "backlog_clock_confirmed", "status": "counting_down"}
    return {"triggered": action_type, "status": "acknowledged"}


# ─────────────────────────────────────────────────────────────────────────────
# ── ROUTE: GET /api/oo/metrics/weekly/{account_id}
# ─────────────────────────────────────────────────────────────────────────────

def route_oo_weekly_metrics(account_id):
    """
    Generate weekly integration success report.
    Murphy auto-generates this during automation hours and sends HITL summary.
    """
    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    # Observations this week
    cur.execute("""
        SELECT COUNT(*) FROM shadow_observations
        WHERE account_id=? AND observed_at >= datetime('now', '-7 days')
    """, (account_id,))
    obs_count = cur.fetchone()[0]

    # Patterns progressed
    cur.execute("""
        SELECT COUNT(*) FROM shadow_patterns
        WHERE account_id=? AND updated_at >= datetime('now', '-7 days')
    """, (account_id,))
    pattern_progress = cur.fetchone()[0]

    # Automations approved this week
    cur.execute("""
        SELECT COUNT(*) FROM shadow_patterns
        WHERE account_id=? AND automation_approved=1
        AND updated_at >= datetime('now', '-7 days')
    """, (account_id,))
    autos_approved = cur.fetchone()[0]

    # HITL resolved this week
    cur.execute("""
        SELECT COUNT(*), status FROM hitl_queue
        WHERE account_id=? AND approved_at >= datetime('now', '-7 days')
        GROUP BY status
    """, (account_id,))
    hitl_resolved = {r[1]: r[0] for r in cur.fetchall()}

    # Contract status
    cur.execute("""
        SELECT status, COUNT(*) FROM saas_contracts WHERE account_id=? GROUP BY status
    """, (account_id,))
    contract_summary = {r[0]: r[1] for r in cur.fetchall()}

    conn.close()

    report = {
        "period": "last_7_days",
        "generated_at": datetime.utcnow().isoformat(),
        "shadow_learning": {
            "observations": obs_count,
            "patterns_progressed": pattern_progress,
            "automations_approved": autos_approved
        },
        "hitl_activity": {
            "total_resolved": sum(hitl_resolved.values()),
            "approved": hitl_resolved.get('approved', 0),
            "rejected": hitl_resolved.get('rejected', 0)
        },
        "contracts": contract_summary,
        "health": (
            "green" if obs_count > 5 and autos_approved >= 0 else
            "yellow" if obs_count > 0 else
            "red"
        ),
        "recommendations": _generate_weekly_recommendations(
            obs_count, pattern_progress, autos_approved, hitl_resolved
        )
    }

    return jsonify(report), 200


def _generate_weekly_recommendations(obs, progress, autos, hitl):
    recs = []
    if obs < 3:
        recs.append("Shadow agent has few observations this week. "
                    "Make sure the Murphy Client is running and logging your activity.")
    if autos == 0 and progress > 2:
        recs.append("Patterns are growing but no automations approved. "
                    "Check your HITL queue — Murphy may have proposals waiting.")
    if hitl.get('pending', 0) > 5:
        recs.append(f"You have {hitl.get('pending', 0)} HITL approvals waiting. "
                    "Unresolved approvals block Murphy's autonomous execution.")
    if not recs:
        recs.append("System is healthy. Murphy is learning your patterns and executing autonomously.")
    return recs


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def register_owner_operator_routes(app):
    """
    Call this from production_router.py:

      from owner_operator_routes import register_owner_operator_routes
      register_owner_operator_routes(app)
    """
    init_oo_db()

    app.add_url_rule('/api/oo/survey',              'oo_survey',            route_oo_survey,           methods=['POST'])
    app.add_url_rule('/api/oo/observe',             'oo_observe',           route_oo_observe,          methods=['POST'])
    app.add_url_rule('/api/oo/appointment/book',    'oo_book',              route_oo_book,             methods=['POST'])
    app.add_url_rule('/api/oo/contract/generate',   'oo_contract_generate', route_oo_contract_generate,methods=['POST'])
    app.add_url_rule('/api/oo/contract/signed',     'oo_contract_signed',   route_oo_contract_signed,  methods=['POST'])
    app.add_url_rule('/api/oo/payment/received',    'oo_payment',           route_oo_payment,          methods=['POST'])
    app.add_url_rule('/api/oo/gap-report',          'oo_gap_report',        route_oo_gap_report,       methods=['POST'])
    app.add_url_rule('/api/oo/dashboard/<account_id>','oo_dashboard',       route_oo_dashboard,        methods=['GET'])
    app.add_url_rule('/api/oo/hitl/respond',        'oo_hitl_respond',      route_oo_hitl_respond,     methods=['POST'])
    app.add_url_rule('/api/oo/metrics/weekly/<account_id>','oo_weekly_metrics',route_oo_weekly_metrics,methods=['GET'])

    # Auth-bypass list (add these to the global SKIP_AUTH_ROUTES in app.py)
    # '/api/oo/survey', '/api/oo/appointment/book'
    # All other routes require X-API-Key or session token

    print("[PATCH-329] Owner-Operator routes registered (10 endpoints)")
    return app
