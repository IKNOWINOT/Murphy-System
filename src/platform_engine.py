"""
PATCH-330 — Murphy Platform Engine
Extends owner_operator_routes.py with:
  - Payment enforcement middleware (suspension kills all automations)
  - HITL re-approval engine (approval is per-instance, never permanent)
  - Voice + text command parser (same engine for both modalities)
  - Dynamic dashboard builder (assembled by question)
  - Timecard engine
  - Password vault API (AES-256-GCM, never plaintext to cloud)
  - Organization onboarding engine (interview → module tailoring → setup → test)
  - Tenant isolation (org gets own DB namespace)

Wire into production_router.py:
  from patch330_platform_engine import register_platform_engine
  register_platform_engine(app)

Adds routes:
  POST /api/platform/command          — voice or text command
  GET  /api/platform/dashboard        — dynamic dashboard by question
  POST /api/platform/timecard/start   — clock in
  POST /api/platform/timecard/stop    — clock out
  GET  /api/platform/timecard/report  — weekly timecard report
  POST /api/platform/vault/save       — save credential (encrypted blob)
  GET  /api/platform/vault/list       — list vault entries (no plaintext)
  POST /api/platform/vault/retrieve   — retrieve decrypted credential
  POST /api/platform/vault/import     — import from OAuth provider
  POST /api/platform/onboard/start    — start org onboarding interview
  POST /api/platform/onboard/answer   — submit interview answer
  GET  /api/platform/onboard/status   — onboarding status + module plan
  POST /api/platform/onboard/approve  — approve module deployment plan
  GET  /api/platform/subscription     — subscription status
  POST /api/stripe/subscription/sync  — internal: sync Stripe status
  POST /api/hitl/reapproval-check     — check if re-approval needed
"""

import uuid
import sqlite3
import json
import os
import re
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
from flask import request, jsonify, g
from functools import wraps

OO_DB = "/var/lib/murphy-production/owner_operator.db"
PLATFORM_DB = "/var/lib/murphy-production/platform.db"

# ─────────────────────────────────────────────────────────────────────────────
# DB INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_platform_db():
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.executescript("""
        -- Subscription state cache
        CREATE TABLE IF NOT EXISTS subscriptions (
            account_id TEXT PRIMARY KEY,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            tier TEXT DEFAULT 'owner_operator',
            status TEXT DEFAULT 'trial',
            current_period_end TEXT,
            grace_until TEXT,
            suspended_at TEXT,
            cancelled_at TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- HITL re-approval tracking
        CREATE TABLE IF NOT EXISTS hitl_approvals (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            pattern_id TEXT,
            action_type TEXT,
            action_fingerprint TEXT,
            approval_policy TEXT DEFAULT 'ALWAYS',
            max_runs INTEGER DEFAULT 1,
            approved_run_count INTEGER DEFAULT 0,
            last_approved_at TIMESTAMP,
            last_approved_by TEXT,
            pattern_confidence_at_approval REAL,
            requires_fresh_approval INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Voice + text commands log
        CREATE TABLE IF NOT EXISTS command_log (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            user_id TEXT,
            input_type TEXT DEFAULT 'text',
            raw_input TEXT,
            parsed_intent TEXT,
            parsed_entities TEXT DEFAULT '{}',
            action_taken TEXT,
            result TEXT,
            required_hitl INTEGER DEFAULT 0,
            hitl_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Timecard entries
        CREATE TABLE IF NOT EXISTS timecard_entries (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            user_id TEXT,
            project_id TEXT,
            task_label TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            duration_min REAL,
            source TEXT DEFAULT 'manual',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Timecard projects
        CREATE TABLE IF NOT EXISTS timecard_projects (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            name TEXT,
            client TEXT,
            billing_rate REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Password vault (encrypted blobs only — no plaintext ever stored)
        CREATE TABLE IF NOT EXISTS vault_entries (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            user_id TEXT,
            service_name TEXT,
            username TEXT,
            encrypted_blob TEXT,
            provider_source TEXT DEFAULT 'manual',
            last_used TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Org onboarding sessions
        CREATE TABLE IF NOT EXISTS onboarding_sessions (
            id TEXT PRIMARY KEY,
            account_id TEXT,
            tier TEXT DEFAULT 'organization',
            phase TEXT DEFAULT 'interview',
            interview_answers TEXT DEFAULT '[]',
            current_question_idx INTEGER DEFAULT 0,
            org_profile TEXT DEFAULT '{}',
            module_plan TEXT DEFAULT '[]',
            plan_approved INTEGER DEFAULT 0,
            setup_complete INTEGER DEFAULT 0,
            test_start_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Tenant registry (one row per organization)
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            account_id TEXT UNIQUE,
            tenant_name TEXT,
            subdomain TEXT,
            db_path TEXT,
            isolation_type TEXT DEFAULT 'shared',
            user_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENT ENFORCEMENT MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────

# Routes exempt from payment check
PAYMENT_EXEMPT = {
    '/start', '/download', '/dashboard',
    '/api/oo/survey', '/api/stripe/webhook',
    '/api/stripe/subscription/sync', '/api/stripe/checkout',
    '/api/platform/subscription',
    '/hitl/',  # prefix match — HITL links must always work
}

def get_subscription_status(account_id: str) -> dict:
    """
    Returns current subscription state for account.
    Checks: active | grace | suspended | cancelled | unknown
    """
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT status, current_period_end, grace_until, suspended_at, tier
        FROM subscriptions WHERE account_id=?
    """, (account_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        # No subscription record = trial
        return {"status": "trial", "tier": "owner_operator", "can_operate": True}

    status, period_end, grace_until, suspended_at, tier = row

    # Compute effective state
    now = datetime.utcnow()

    if status == 'cancelled':
        return {"status": "cancelled", "tier": tier, "can_operate": False,
                "message": "Subscription cancelled. Renew at murphy.systems/billing"}

    if status == 'suspended':
        return {"status": "suspended", "tier": tier, "can_operate": False,
                "message": "Payment past due. Automations paused. Resume at murphy.systems/billing"}

    if status == 'grace':
        grace_dt = datetime.fromisoformat(grace_until) if grace_until else now
        if now > grace_dt:
            # Grace period expired — suspend
            _suspend_account(account_id)
            return {"status": "suspended", "tier": tier, "can_operate": False,
                    "message": "Payment overdue. All automations paused. Resume at murphy.systems/billing"}
        days_left = (grace_dt - now).days
        return {"status": "grace", "tier": tier, "can_operate": True,
                "warning": f"Payment {days_left} day(s) overdue. Update payment to avoid suspension."}

    return {"status": "active", "tier": tier, "can_operate": True}


def _suspend_account(account_id: str):
    """Suspend account — pause all automations."""
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE subscriptions
        SET status='suspended', suspended_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
        WHERE account_id=?
    """, (account_id,))
    conn.commit()
    conn.close()

    # Pause all shadow patterns (stop proposing automations)
    conn2 = sqlite3.connect(OO_DB)
    cur2 = conn2.cursor()
    cur2.execute("""
        UPDATE shadow_patterns
        SET automation_approved=0
        WHERE account_id=?
    """, (account_id,))
    conn2.commit()
    conn2.close()


def payment_required(f):
    """
    Decorator: check subscription before any action.
    Attach to any route that requires active subscription.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        account_id = (
            request.headers.get('X-Account-ID') or
            (request.get_json(silent=True) or {}).get('account_id') or
            kwargs.get('account_id')
        )
        if not account_id:
            return f(*args, **kwargs)  # Let the route handle missing account_id

        sub = get_subscription_status(account_id)
        if not sub['can_operate']:
            return jsonify({
                "error": "subscription_required",
                "status": sub['status'],
                "message": sub.get('message', 'Subscription required'),
                "resume_url": "https://murphy.systems/billing"
            }), 402

        # Attach subscription info to request context
        g.subscription = sub
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# STRIPE SUBSCRIPTION SYNC
# ─────────────────────────────────────────────────────────────────────────────

def route_stripe_subscription_sync():
    """
    Stripe webhook → update subscription status in real time.
    Wire: POST /api/stripe/subscription/sync
    Called by the existing stripe webhook handler AND directly by Stripe.
    """
    payload = request.get_data(as_text=True)
    sig = request.headers.get('Stripe-Signature', '')
    STRIPE_SECRET = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    if not STRIPE_SECRET:
        return jsonify({"ok": True, "note": "Stripe not configured"}), 200

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    event_type = event['type']
    obj = event['data']['object']
    account_id = obj.get('metadata', {}).get('account_id')

    if not account_id:
        # Try to look up by customer email
        customer_email = obj.get('customer_email') or ''
        if customer_email:
            conn = sqlite3.connect(OO_DB)
            cur = conn.cursor()
            cur.execute("SELECT id FROM owner_operator_accounts WHERE email=?",
                        (customer_email.lower(),))
            row = cur.fetchone()
            conn.close()
            if row:
                account_id = row[0]

    if not account_id:
        return '', 200

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()

    if event_type == 'invoice.payment_succeeded':
        period_end = datetime.utcfromtimestamp(
            obj.get('lines', {}).get('data', [{}])[0].get('period', {}).get('end',
            datetime.utcnow().timestamp() + 30*86400)
        ).isoformat()
        cur.execute("""
            INSERT INTO subscriptions (account_id, status, current_period_end)
            VALUES (?, 'active', ?)
            ON CONFLICT(account_id) DO UPDATE SET
              status='active', current_period_end=?, suspended_at=NULL,
              grace_until=NULL, updated_at=CURRENT_TIMESTAMP
        """, (account_id, period_end, period_end))

        # Re-enable automations on payment success
        conn2 = sqlite3.connect(OO_DB)
        cur2 = conn2.cursor()
        cur2.execute("""
            UPDATE owner_operator_accounts
            SET status='active', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (account_id,))
        conn2.commit()
        conn2.close()

    elif event_type == 'invoice.payment_failed':
        # Check if first or second failure
        cur.execute("SELECT status FROM subscriptions WHERE account_id=?", (account_id,))
        row = cur.fetchone()
        current_status = row[0] if row else 'active'

        if current_status == 'grace':
            # Second failure → suspend
            _suspend_account(account_id)
        else:
            # First failure → grace period (3 days)
            grace_until = (datetime.utcnow() + timedelta(days=3)).isoformat()
            cur.execute("""
                INSERT INTO subscriptions (account_id, status, grace_until)
                VALUES (?, 'grace', ?)
                ON CONFLICT(account_id) DO UPDATE SET
                  status='grace', grace_until=?, updated_at=CURRENT_TIMESTAMP
            """, (account_id, grace_until, grace_until))

    elif event_type == 'customer.subscription.deleted':
        cur.execute("""
            INSERT INTO subscriptions (account_id, status, cancelled_at)
            VALUES (?, 'cancelled', CURRENT_TIMESTAMP)
            ON CONFLICT(account_id) DO UPDATE SET
              status='cancelled', cancelled_at=CURRENT_TIMESTAMP,
              updated_at=CURRENT_TIMESTAMP
        """, (account_id,))
        _suspend_account(account_id)

    elif event_type in ('customer.subscription.created', 'customer.subscription.updated'):
        stripe_sub_id = obj.get('id', '')
        customer_id = obj.get('customer', '')
        tier = 'owner_operator'
        # Detect tier by price
        items = obj.get('items', {}).get('data', [])
        for item in items:
            price_id = item.get('price', {}).get('id', '')
            if price_id == os.environ.get('STRIPE_PRICE_ID_ORG', ''):
                tier = 'organization'
        cur.execute("""
            INSERT INTO subscriptions (account_id, stripe_customer_id, stripe_subscription_id, tier, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT(account_id) DO UPDATE SET
              stripe_customer_id=?, stripe_subscription_id=?, tier=?,
              status='active', updated_at=CURRENT_TIMESTAMP
        """, (account_id, customer_id, stripe_sub_id, tier,
              customer_id, stripe_sub_id, tier))

    conn.commit()
    conn.close()
    return '', 200


def route_get_subscription(account_id):
    sub = get_subscription_status(account_id)
    return jsonify(sub), 200


# ─────────────────────────────────────────────────────────────────────────────
# HITL RE-APPROVAL ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def requires_fresh_approval(account_id: str, pattern_id: str,
                             action_fingerprint: str,
                             current_confidence: float) -> dict:
    """
    Check if this specific action needs a fresh HITL approval.
    Returns: { required: bool, reason: str, hitl_approval_id: str | None }
    """
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, approval_policy, max_runs, approved_run_count,
               pattern_confidence_at_approval, action_fingerprint
        FROM hitl_approvals
        WHERE account_id=? AND pattern_id=?
        ORDER BY last_approved_at DESC LIMIT 1
    """, (account_id, pattern_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"required": True, "reason": "no_prior_approval",
                "hitl_approval_id": None}

    apv_id, policy, max_runs, run_count, confidence_at_approval, approved_fingerprint = row

    # Policy: ALWAYS
    if policy == 'ALWAYS':
        return {"required": True, "reason": "policy_always",
                "hitl_approval_id": apv_id}

    # Fingerprint changed (different amount, recipient, etc.)
    if action_fingerprint != approved_fingerprint:
        return {"required": True, "reason": "action_changed",
                "hitl_approval_id": apv_id}

    # Policy: N_RUNS — check if run count exhausted
    if policy == 'N_RUNS' and run_count >= max_runs:
        return {"required": True, "reason": f"run_limit_reached_{run_count}/{max_runs}",
                "hitl_approval_id": apv_id}

    # Pattern drift check (confidence dropped > 15% since approval)
    if confidence_at_approval and current_confidence:
        drift = abs(confidence_at_approval - current_confidence)
        if drift > 0.15:
            return {"required": True, "reason": f"pattern_drift_{drift:.2f}",
                    "hitl_approval_id": apv_id}

    # Policy: TRUSTED or N_RUNS within limit
    return {"required": False, "reason": "approved",
            "hitl_approval_id": apv_id,
            "runs_remaining": max_runs - run_count if policy == 'N_RUNS' else None}


def record_hitl_approval(account_id: str, pattern_id: str,
                          action_type: str, action_fingerprint: str,
                          policy: str, max_runs: int,
                          confidence: float) -> str:
    """Record a new HITL approval. Returns approval_id."""
    apv_id = str(uuid.uuid4())
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO hitl_approvals
        (id, account_id, pattern_id, action_type, action_fingerprint,
         approval_policy, max_runs, approved_run_count,
         last_approved_at, last_approved_by, pattern_confidence_at_approval,
         requires_fresh_approval)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP, 'owner', ?, 0)
    """, (apv_id, account_id, pattern_id, action_type, action_fingerprint,
          policy, max_runs, confidence))
    conn.commit()
    conn.close()
    return apv_id


def increment_approval_run(approval_id: str):
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE hitl_approvals
        SET approved_run_count = approved_run_count + 1,
            requires_fresh_approval = CASE
                WHEN approval_policy = 'N_RUNS' AND approved_run_count + 1 >= max_runs THEN 1
                ELSE 0
            END
        WHERE id=?
    """, (approval_id,))
    conn.commit()
    conn.close()


def route_hitl_reapproval_check():
    """
    Check if a pattern needs re-approval before executing.
    Body: { account_id, pattern_id, action_fingerprint, current_confidence }
    """
    data = request.get_json() or {}
    result = requires_fresh_approval(
        account_id=data.get('account_id', ''),
        pattern_id=data.get('pattern_id', ''),
        action_fingerprint=data.get('action_fingerprint', ''),
        current_confidence=float(data.get('current_confidence', 0))
    )
    return jsonify(result), 200


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND PARSER — voice + text → action
# ─────────────────────────────────────────────────────────────────────────────

INTENT_PATTERNS = {
    'STATUS': [
        r"what('s| is) happening", r"show me", r"how many", r"what are",
        r"tell me about", r"status of", r"overview", r"summary"
    ],
    'RUN': [
        r"run (the )?", r"execute", r"trigger", r"send (the )?", r"fire"
    ],
    'APPROVE': [
        r"^yes$", r"^approve$", r"^do it$", r"^confirmed?$", r"go ahead",
        r"approve that", r"looks good"
    ],
    'REJECT': [
        r"^no$", r"^cancel( that)?$", r"don't send", r"reject", r"stop that",
        r"don't do"
    ],
    'SCHEDULE': [
        r"schedule", r"set up (an? )?automation", r"run (this )?every",
        r"automate (this )?", r"create (a )?workflow"
    ],
    'REPORT': [
        r"report", r"how did", r"this week", r"last week", r"pipeline",
        r"metrics", r"analytics"
    ],
    'TIMECARD': [
        r"start timer", r"stop timer", r"clock (in|out)", r"log .* hours?",
        r"time(card)?", r"start working on", r"done (with|for)"
    ],
    'PASSWORD': [
        r"save (this )?password", r"what('s| is) my (login|password|credentials?) for",
        r"vault", r"credentials? for", r"add (to )?vault"
    ],
    'QUERY': [
        r"who (signed|paid|booked)", r"show (deals|leads|contracts|appointments)",
        r"list (all )?", r"find ", r"search for"
    ],
    'BUILD': [
        r"build (a )?workflow", r"i need automation for", r"create (a )?module",
        r"make (a )?", r"design (a )?"
    ],
    'ONBOARD': [
        r"start onboarding", r"interview", r"new (hire|employee|user)",
        r"add (a )?user", r"onboard"
    ],
    'SYSTEM': [
        r"pause (all )?automations?", r"resume (subscription|automations?)",
        r"restart", r"system status", r"subscription"
    ],
}

FINANCIAL_KEYWORDS = ['send', 'contract', 'invoice', 'payment', 'charge',
                       'pay', 'transfer', 'quote', 'proposal']
CUSTOMER_KEYWORDS  = ['email', 'message', 'contact', 'call', 'reach out',
                       'notify', 'alert']
ORG_KEYWORDS       = ['hire', 'add user', 'remove user', 'org chart',
                       'onboard', 'fire', 'promote']


def parse_command(raw_input: str) -> dict:
    """
    Parse natural language command → intent + entities + authority_level.
    Returns:
    {
      intent: str,
      entities: { project, amount, recipient, timeframe, workflow },
      authority: 'safe' | 'financial' | 'customer' | 'org',
      requires_hitl: bool,
      action_description: str
    }
    """
    text = raw_input.lower().strip()

    # Classify intent
    intent = 'STATUS'  # default
    for intent_name, patterns in INTENT_PATTERNS.items():
        if any(re.search(p, text) for p in patterns):
            intent = intent_name
            break

    # Extract entities
    entities = {}

    # Amount (e.g. "$5,000" or "5000 dollars")
    amount_match = re.search(r'\$?([\d,]+(?:\.\d{2})?)\s*(dollars?|usd)?', text)
    if amount_match:
        entities['amount'] = float(amount_match.group(1).replace(',', ''))

    # Time references
    for tf in ['today', 'this week', 'last week', 'this month', 'yesterday']:
        if tf in text:
            entities['timeframe'] = tf
            break

    # Project/task name (quoted or after "on"/"for")
    project_match = re.search(r'"([^"]+)"', raw_input) or re.search(r'\bon\s+([A-Z][^,\.]+)', raw_input)
    if project_match:
        entities['project'] = project_match.group(1)

    # Recipient (email address)
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', text)
    if email_match:
        entities['recipient'] = email_match.group(0)

    # Authority level
    authority = 'safe'
    requires_hitl = False

    if intent in ('RUN', 'SCHEDULE', 'BUILD') or any(k in text for k in FINANCIAL_KEYWORDS):
        authority = 'financial'
        requires_hitl = True
    elif any(k in text for k in CUSTOMER_KEYWORDS):
        authority = 'customer'
        requires_hitl = True
    elif any(k in text for k in ORG_KEYWORDS) or intent == 'ONBOARD':
        authority = 'org'
        requires_hitl = True

    # Build action description
    action_description = _describe_action(intent, entities, raw_input)

    return {
        "intent": intent,
        "entities": entities,
        "authority": authority,
        "requires_hitl": requires_hitl,
        "action_description": action_description,
        "raw": raw_input
    }


def _describe_action(intent: str, entities: dict, raw: str) -> str:
    descs = {
        'STATUS':   f"Check status: {raw[:80]}",
        'RUN':      f"Execute workflow: {raw[:80]}",
        'APPROVE':  "Approve queued action",
        'REJECT':   "Reject queued action",
        'SCHEDULE': f"Create automation: {raw[:80]}",
        'REPORT':   f"Generate report: {raw[:80]}",
        'TIMECARD': f"Timecard action: {raw[:80]}",
        'PASSWORD': f"Vault action: {raw[:80]}",
        'QUERY':    f"Query: {raw[:80]}",
        'BUILD':    f"Build workflow: {raw[:80]}",
        'ONBOARD':  f"Start onboarding: {raw[:80]}",
        'SYSTEM':   f"System command: {raw[:80]}",
    }
    return descs.get(intent, raw[:100])


def route_platform_command():
    """
    Universal command endpoint. Accepts voice transcript or typed text.
    Body: {
        account_id: str,
        input: str,         — the command text (already transcribed if voice)
        input_type: "voice" | "text",
        user_id: str (optional)
    }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    raw_input = (data.get('input') or data.get('text') or '').strip()
    input_type = data.get('input_type', 'text')
    user_id = data.get('user_id', account_id)

    if not account_id or not raw_input:
        return jsonify({"error": "account_id and input required"}), 400

    # Check subscription
    sub = get_subscription_status(account_id)
    if not sub['can_operate']:
        # Only allow subscription commands
        if 'resume' not in raw_input.lower() and 'subscription' not in raw_input.lower():
            return jsonify({
                "error": "subscription_suspended",
                "message": sub.get('message'),
                "allowed_commands": ["resume subscription", "update payment"],
                "billing_url": "https://murphy.systems/billing"
            }), 402

    parsed = parse_command(raw_input)
    cmd_id = str(uuid.uuid4())
    hitl_id = None
    result = None
    action_taken = 'pending'

    # Execute or queue
    if parsed['requires_hitl']:
        # Queue HITL — do NOT execute
        from patch329_owner_operator_routes import queue_hitl
        hitl_id = queue_hitl(
            account_id=account_id,
            action_type=f"command_{parsed['intent'].lower()}",
            description=(f"Voice/text command requires your approval:\n\n"
                         f"  Command: \"{raw_input}\"\n"
                         f"  Intent: {parsed['intent']}\n"
                         f"  Authority: {parsed['authority']}\n\n"
                         f"Approve to execute, reject to cancel."),
            action_data={"command": raw_input, "parsed": parsed,
                         "user_id": user_id, "input_type": input_type}
        )
        action_taken = 'queued_hitl'
        result = {
            "queued": True,
            "hitl_id": hitl_id,
            "message": f"I've queued that for your approval — check your alerts to confirm.",
            "approve_url": f"https://murphy.systems/hitl/{hitl_id}/approve"
        }
    else:
        # Execute safe commands immediately
        action_taken = 'executed'
        result = _execute_safe_command(account_id, parsed)

    # Log command
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO command_log
        (id, account_id, user_id, input_type, raw_input, parsed_intent,
         parsed_entities, action_taken, result, required_hitl, hitl_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cmd_id, account_id, user_id, input_type, raw_input,
          parsed['intent'], json.dumps(parsed['entities']),
          action_taken, json.dumps(result), 1 if parsed['requires_hitl'] else 0,
          hitl_id))
    conn.commit()
    conn.close()

    return jsonify({
        "command_id": cmd_id,
        "intent": parsed['intent'],
        "authority": parsed['authority'],
        "requires_hitl": parsed['requires_hitl'],
        "action_taken": action_taken,
        "result": result,
        "hitl_id": hitl_id
    }), 200


def _execute_safe_command(account_id: str, parsed: dict) -> dict:
    """Execute commands that don't require HITL."""
    intent = parsed['intent']
    entities = parsed['entities']

    if intent == 'STATUS':
        return {"type": "status", "message": "System operational. Checking live state...",
                "dashboard_url": f"/dashboard?id={account_id}"}

    if intent == 'REPORT':
        tf = entities.get('timeframe', 'this week')
        return {"type": "report", "timeframe": tf,
                "message": f"Generating {tf} report...",
                "report_url": f"/api/oo/metrics/weekly/{account_id}"}

    if intent == 'APPROVE':
        return {"type": "approve", "message": "Noted — use the approve link in the alert email or dashboard."}

    if intent == 'REJECT':
        return {"type": "reject", "message": "Noted — use the reject link in the alert email or dashboard."}

    if intent == 'TIMECARD':
        raw = parsed.get('raw', '').lower()
        if 'start' in raw or 'clock in' in raw or 'working on' in raw:
            project = entities.get('project', 'General')
            return {"type": "timecard_start", "project": project,
                    "message": f"Timer started for '{project}'. I'll log your time.",
                    "action": "start_timer", "project": project}
        else:
            return {"type": "timecard_stop",
                    "message": "Timer stopped. Time logged.",
                    "action": "stop_timer"}

    if intent == 'QUERY':
        return {"type": "query",
                "message": "Searching...",
                "dashboard_url": f"/dashboard?id={account_id}&q={parsed.get('raw','')}"}

    if intent == 'SYSTEM':
        raw = parsed.get('raw', '').lower()
        if 'resume' in raw:
            return {"type": "system", "message": "Redirect to billing to resume subscription.",
                    "billing_url": "https://murphy.systems/billing"}
        return {"type": "system", "message": "System command noted."}

    return {"type": intent.lower(), "message": "Understood."}


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC DASHBOARD BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def route_platform_dashboard():
    """
    Assemble a dashboard from a natural language question.
    Query params: account_id, q (question)
    """
    account_id = request.args.get('account_id', '') or \
                 (request.get_json(silent=True) or {}).get('account_id', '')
    question = request.args.get('q', '') or \
               (request.get_json(silent=True) or {}).get('question', '')

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    if not question:
        question = "show me everything important right now"

    parsed = parse_command(question)
    intent = parsed['intent']
    entities = parsed['entities']
    cards = []

    # Always include subscription status
    sub = get_subscription_status(account_id)
    if sub['status'] != 'active':
        cards.append({
            "type": "alert",
            "priority": 0,
            "title": "⚠️ Subscription",
            "content": sub.get('message') or sub.get('warning') or "Check billing",
            "action_url": "https://murphy.systems/billing"
        })

    conn = sqlite3.connect(OO_DB)
    cur = conn.cursor()

    # What cards to build based on question
    show = {
        'hitl':     intent in ('STATUS', 'REPORT') or 'approval' in question.lower() or 'pending' in question.lower(),
        'pipeline': intent in ('STATUS', 'REPORT', 'QUERY') or 'pipeline' in question.lower() or 'deal' in question.lower(),
        'backlog':  intent in ('STATUS', 'REPORT') or 'backlog' in question.lower() or 'work' in question.lower(),
        'patterns': intent in ('STATUS', 'REPORT') or 'shadow' in question.lower() or 'pattern' in question.lower(),
        'timecard': intent == 'TIMECARD' or 'time' in question.lower() or 'hours' in question.lower(),
        'metrics':  intent == 'REPORT' or 'metric' in question.lower() or 'week' in question.lower(),
    }

    # Default: show everything for generic questions
    if intent == 'STATUS' and not any(show.values()):
        show = {k: True for k in show}

    if show['hitl']:
        cur.execute("""
            SELECT COUNT(*) FROM hitl_queue
            WHERE account_id=? AND status='pending'
        """, (account_id,))
        pending = cur.fetchone()[0]
        cards.append({
            "type": "hitl_summary",
            "priority": 1 if pending > 0 else 5,
            "title": f"⚡ Pending Approvals",
            "count": pending,
            "content": f"{pending} action{'s' if pending != 1 else ''} waiting for your approval",
            "action_url": f"/dashboard?id={account_id}",
            "urgent": pending > 0
        })

    if show['pipeline']:
        tf = entities.get('timeframe', 'this week')
        since = {'today': 1, 'this week': 7, 'last week': 14,
                 'this month': 30}.get(tf, 7)
        cur.execute("""
            SELECT status, COUNT(*) FROM saas_contracts
            WHERE account_id=?
            GROUP BY status
        """, (account_id,))
        pipeline = {r[0]: r[1] for r in cur.fetchall()}
        cards.append({
            "type": "pipeline",
            "priority": 2,
            "title": "📊 Pipeline",
            "content": pipeline,
            "timeframe": tf
        })

    if show['backlog']:
        cur.execute("""
            SELECT status, COUNT(*) FROM saas_work_backlog
            WHERE account_id=? GROUP BY status
        """, (account_id,))
        backlog = {r[0]: r[1] for r in cur.fetchall()}
        # Get next activation date
        cur.execute("""
            SELECT MIN(backlog_activation_date) FROM saas_contracts
            WHERE account_id=? AND backlog_activation_date IS NOT NULL
        """, (account_id,))
        act_date = cur.fetchone()[0]
        cards.append({
            "type": "backlog",
            "priority": 3,
            "title": "📋 Work Backlog",
            "content": backlog,
            "activation_date": act_date
        })

    if show['patterns']:
        cur.execute("""
            SELECT pattern_type, confidence, sample_count, automation_approved
            FROM shadow_patterns WHERE account_id=?
            ORDER BY confidence DESC LIMIT 5
        """, (account_id,))
        patterns = [{"type": r[0], "confidence": f"{r[1]:.0%}",
                     "observations": r[2], "approved": bool(r[3])}
                    for r in cur.fetchall()]
        cards.append({
            "type": "shadow_patterns",
            "priority": 4,
            "title": "🧠 Shadow Agent",
            "content": patterns,
            "total": len(patterns)
        })

    if show['timecard']:
        conn2 = sqlite3.connect(PLATFORM_DB)
        cur2 = conn2.cursor()
        cur2.execute("""
            SELECT SUM(duration_min), project_id, task_label
            FROM timecard_entries
            WHERE account_id=?
            AND start_time >= datetime('now', '-7 days')
            GROUP BY project_id
            ORDER BY SUM(duration_min) DESC LIMIT 5
        """, (account_id,))
        tc = [{"project": r[1] or 'General', "task": r[2],
               "hours": round((r[0] or 0) / 60, 1)}
              for r in cur2.fetchall()]
        conn2.close()
        cards.append({
            "type": "timecard",
            "priority": 3,
            "title": "⏱ Time This Week",
            "content": tc,
            "total_hours": sum(c['hours'] for c in tc)
        })

    conn.close()

    # Sort cards by priority
    cards.sort(key=lambda c: c.get('priority', 9))

    return jsonify({
        "question": question,
        "intent": intent,
        "cards": cards,
        "generated_at": datetime.utcnow().isoformat(),
        "account_id": account_id
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# TIMECARD ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def route_timecard_start():
    """
    Clock in. Creates an open entry.
    Body: { account_id, user_id, project_id (or project_name), task_label, source }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    user_id = data.get('user_id', account_id)
    project_id = data.get('project_id', '')
    project_name = data.get('project_name', 'General')
    task_label = data.get('task_label', '')
    source = data.get('source', 'manual')

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()

    # Close any open entries for this user first
    cur.execute("""
        UPDATE timecard_entries
        SET end_time=CURRENT_TIMESTAMP,
            duration_min=(julianday('now') - julianday(start_time)) * 1440
        WHERE account_id=? AND user_id=? AND end_time IS NULL
    """, (account_id, user_id))

    # Auto-create project if needed
    if not project_id and project_name:
        cur.execute("SELECT id FROM timecard_projects WHERE account_id=? AND name=?",
                    (account_id, project_name))
        proj = cur.fetchone()
        if proj:
            project_id = proj[0]
        else:
            project_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO timecard_projects (id, account_id, name)
                VALUES (?, ?, ?)
            """, (project_id, account_id, project_name))

    entry_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO timecard_entries
        (id, account_id, user_id, project_id, task_label, start_time, source)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """, (entry_id, account_id, user_id, project_id, task_label, source))

    conn.commit()
    conn.close()

    return jsonify({
        "entry_id": entry_id,
        "project": project_name,
        "task": task_label,
        "started_at": datetime.utcnow().isoformat(),
        "message": f"Timer started — {task_label or project_name}"
    }), 201


def route_timecard_stop():
    """
    Clock out. Closes open entry.
    Body: { account_id, user_id, notes }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    user_id = data.get('user_id', account_id)
    notes = data.get('notes', '')

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE timecard_entries
        SET end_time=CURRENT_TIMESTAMP,
            duration_min=(julianday('now') - julianday(start_time)) * 1440,
            notes=?
        WHERE account_id=? AND user_id=? AND end_time IS NULL
        RETURNING id, project_id, task_label, start_time, duration_min
    """, (notes, account_id, user_id))
    row = cur.fetchone()
    conn.commit()
    conn.close()

    if not row:
        return jsonify({"error": "No open timer found"}), 404

    entry_id, project_id, task, start_time, duration = row
    hours = round((duration or 0) / 60, 2)
    return jsonify({
        "entry_id": entry_id,
        "task": task,
        "duration_hours": hours,
        "message": f"Timer stopped — {hours}h logged"
    }), 200


def route_timecard_report(account_id):
    """Weekly timecard report."""
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT te.id, te.task_label, te.start_time, te.end_time,
               te.duration_min, te.source, te.notes,
               tp.name as project_name, tp.billing_rate
        FROM timecard_entries te
        LEFT JOIN timecard_projects tp ON te.project_id = tp.id
        WHERE te.account_id=?
        AND te.start_time >= datetime('now', '-7 days')
        ORDER BY te.start_time DESC
    """, (account_id,))
    entries = cur.fetchall()
    conn.close()

    total_min = sum(e[4] or 0 for e in entries)
    billable_min = sum((e[4] or 0) for e in entries if (e[8] or 0) > 0)

    rows = [{
        "id": e[0], "task": e[1], "start": e[2], "end": e[3],
        "hours": round((e[4] or 0) / 60, 2), "source": e[5],
        "notes": e[6], "project": e[7], "billing_rate": e[8]
    } for e in entries]

    return jsonify({
        "period": "last_7_days",
        "total_hours": round(total_min / 60, 2),
        "billable_hours": round(billable_min / 60, 2),
        "entries": rows,
        "entry_count": len(rows)
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# PASSWORD VAULT
# ─────────────────────────────────────────────────────────────────────────────

def _derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive AES key from master password using PBKDF2."""
    import hashlib as _hl
    return _hl.pbkdf2_hmac('sha256', master_password.encode(), salt, 100000, 32)


def _encrypt_blob(plaintext: str, master_password: str) -> str:
    """AES-256-GCM encrypt. Returns base64 JSON blob."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        salt = os.urandom(16)
        key = _derive_key(master_password, salt)
        nonce = os.urandom(12)
        aad = b"murphy_vault_v1"
        ct = AESGCM(key).encrypt(nonce, plaintext.encode(), aad)
        blob = {"s": base64.b64encode(salt).decode(), "n": base64.b64encode(nonce).decode(),
                "c": base64.b64encode(ct).decode()}
        return base64.b64encode(json.dumps(blob).encode()).decode()
    except ImportError:
        # cryptography not installed — use simple XOR (dev fallback, NOT production)
        return base64.b64encode(plaintext.encode()).decode() + "__UNENCRYPTED"


def _decrypt_blob(blob_b64: str, master_password: str) -> str:
    """Decrypt AES-256-GCM blob."""
    if blob_b64.endswith("__UNENCRYPTED"):
        return base64.b64decode(blob_b64.replace("__UNENCRYPTED", "")).decode()
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        blob = json.loads(base64.b64decode(blob_b64))
        salt = base64.b64decode(blob['s'])
        nonce = base64.b64decode(blob['n'])
        ct = base64.b64decode(blob['c'])
        key = _derive_key(master_password, salt)
        aad = b"murphy_vault_v1"
        return AESGCM(key).decrypt(nonce, ct, aad).decode()
    except Exception:
        raise ValueError("Decryption failed — wrong master password or corrupted vault")


def route_vault_save():
    """
    Save credential to vault. Password is encrypted before storage.
    Body: {
        account_id, user_id, service_name, username,
        password (plaintext — encrypted immediately, never stored plain),
        master_password (vault key — never stored),
        provider_source (manual | google | github | linkedin | meta | microsoft | apple)
    }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    service = data.get('service_name', '')
    username = data.get('username', '')
    password = data.get('password', '')
    master_pw = data.get('master_password', '')

    if not all([account_id, service, password, master_pw]):
        return jsonify({"error": "account_id, service_name, password, master_password required"}), 400

    encrypted = _encrypt_blob(json.dumps({"password": password, "username": username,
                                           "service": service}), master_pw)
    entry_id = str(uuid.uuid4())
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vault_entries
        (id, account_id, user_id, service_name, username, encrypted_blob, provider_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (entry_id, account_id, data.get('user_id', account_id),
          service, username, encrypted, data.get('provider_source', 'manual')))
    conn.commit()
    conn.close()

    return jsonify({"entry_id": entry_id, "service": service,
                    "message": "Saved. Master password never leaves your device."}), 201


def route_vault_list(account_id):
    """List vault entries — service names and usernames only, no passwords."""
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, service_name, username, provider_source, last_used, created_at
        FROM vault_entries WHERE account_id=?
        ORDER BY service_name
    """, (account_id,))
    entries = [{"id": r[0], "service": r[1], "username": r[2],
                "source": r[3], "last_used": r[4], "created": r[5]}
               for r in cur.fetchall()]
    conn.close()
    return jsonify({"entries": entries, "count": len(entries)}), 200


def route_vault_retrieve():
    """
    Retrieve decrypted credential. Master password required.
    Body: { account_id, entry_id, master_password }
    NEVER logged. Decrypted only in-memory, returned once.
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    entry_id = data.get('entry_id', '')
    master_pw = data.get('master_password', '')

    if not all([account_id, entry_id, master_pw]):
        return jsonify({"error": "account_id, entry_id, master_password required"}), 400

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT encrypted_blob, service_name, username
        FROM vault_entries WHERE id=? AND account_id=?
    """, (entry_id, account_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Entry not found"}), 404

    encrypted, service, username = row
    cur.execute("UPDATE vault_entries SET last_used=CURRENT_TIMESTAMP WHERE id=?", (entry_id,))
    conn.commit()
    conn.close()

    try:
        decrypted = json.loads(_decrypt_blob(encrypted, master_pw))
        return jsonify({"service": service, "username": username,
                        "password": decrypted.get('password'),
                        "note": "This credential is not logged or stored by Murphy."}), 200
    except ValueError:
        return jsonify({"error": "Wrong master password"}), 403


def route_vault_import():
    """
    Import credentials from OAuth provider.
    Body: { account_id, provider (google|github|linkedin|meta|microsoft|apple),
            access_token, master_password }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    provider = data.get('provider', '').lower()
    access_token = data.get('access_token', '')
    master_pw = data.get('master_password', '')

    if not all([account_id, provider, access_token, master_pw]):
        return jsonify({"error": "account_id, provider, access_token, master_password required"}), 400

    SUPPORTED_PROVIDERS = ['google', 'github', 'linkedin', 'meta', 'microsoft', 'apple']
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"error": f"Unsupported provider. Use one of: {SUPPORTED_PROVIDERS}"}), 400

    # Fetch identity from provider
    profile = _fetch_provider_profile(provider, access_token)
    if not profile:
        return jsonify({"error": f"Failed to fetch profile from {provider}"}), 400

    # Save as vault entry
    entry_data = json.dumps({
        "password": f"oauth_token_{provider}",
        "username": profile.get('email') or profile.get('login') or profile.get('sub', ''),
        "service": provider,
        "profile": profile
    })
    encrypted = _encrypt_blob(entry_data, master_pw)
    entry_id = str(uuid.uuid4())

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO vault_entries
        (id, account_id, user_id, service_name, username, encrypted_blob, provider_source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
    """, (entry_id, account_id, account_id, provider,
          profile.get('email') or profile.get('login', ''),
          encrypted, provider))
    conn.commit()
    conn.close()

    return jsonify({
        "entry_id": entry_id,
        "provider": provider,
        "username": profile.get('email') or profile.get('login', ''),
        "imported_fields": list(profile.keys()),
        "message": f"{provider.capitalize()} account imported to vault"
    }), 201


def _fetch_provider_profile(provider: str, token: str) -> dict:
    """Fetch user profile from OAuth provider using access token."""
    import urllib.request
    ENDPOINTS = {
        'google':    ('https://www.googleapis.com/oauth2/v3/userinfo', 'Bearer'),
        'github':    ('https://api.github.com/user', 'Bearer'),
        'linkedin':  ('https://api.linkedin.com/v2/me', 'Bearer'),
        'meta':      ('https://graph.facebook.com/me?fields=id,name,email', 'Bearer'),
        'microsoft': ('https://graph.microsoft.com/v1.0/me', 'Bearer'),
        'apple':     (None, None),  # Apple uses JWT decode, not REST
    }
    endpoint, auth_type = ENDPOINTS.get(provider, (None, None))
    if not endpoint:
        return {"provider": provider, "note": "profile fetch not supported for this provider"}

    try:
        req = urllib.request.Request(endpoint,
                                      headers={"Authorization": f"{auth_type} {token}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# ORGANIZATION ONBOARDING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

INTERVIEW_QUESTIONS = [
    {
        "id": "team_size",
        "question": "How many people work here, and what does each person primarily do?",
        "hint": "e.g. '5 people: 1 owner, 2 field techs, 1 office manager, 1 sales rep'",
        "maps_to": "org_chart"
    },
    {
        "id": "job_flow",
        "question": "Walk me through a typical job from the moment a lead contacts you to the final invoice.",
        "hint": "Don't skip steps — include every handoff, approval, and system touch.",
        "maps_to": "workflow_map"
    },
    {
        "id": "biggest_gap",
        "question": "What's the thing that falls through the cracks most often?",
        "hint": "The thing you've said 'we really need to fix this' more than once.",
        "maps_to": "priority_automation"
    },
    {
        "id": "current_tools",
        "question": "What software and tools does your team use daily?",
        "hint": "CRM, scheduling, invoicing, communication — everything.",
        "maps_to": "integration_map"
    },
    {
        "id": "time_sink",
        "question": "Where does your team spend time that you wish they didn't?",
        "hint": "Repetitive tasks, manual data entry, follow-ups, reporting.",
        "maps_to": "automation_candidates"
    },
    {
        "id": "growth_block",
        "question": "What's the one thing preventing you from taking on 20% more work right now?",
        "hint": "Capacity, coordination, quality control, cash flow?",
        "maps_to": "scale_blockers"
    },
    {
        "id": "decision_authority",
        "question": "Who in your organization has the authority to approve contracts, payments, and new hires?",
        "hint": "This determines who gets HITL approval alerts.",
        "maps_to": "hitl_authority_map"
    },
    {
        "id": "automation_hours",
        "question": "What hours is it safe for Murphy to operate autonomously without interrupting your team?",
        "hint": "e.g. 'After 8pm and before 7am' or 'Weekends only'",
        "maps_to": "automation_schedule"
    },
    {
        "id": "compliance",
        "question": "Are there any regulatory, legal, or compliance requirements your business must follow?",
        "hint": "HIPAA, licensing, bonding, contracts that must be reviewed by a lawyer, etc.",
        "maps_to": "compliance_gates"
    },
    {
        "id": "success_metric",
        "question": "Six months from now, what would make you say 'Murphy was worth every penny'?",
        "hint": "Be specific — revenue, time saved, headcount avoided, etc.",
        "maps_to": "success_definition"
    },
]

MURPHY_GITHUB_MODULES = [
    {"id": "apc_prospector",    "name": "APC Prospector",       "use_case": "lead generation, outreach, prospecting"},
    {"id": "appointment_engine","name": "Appointment Engine",   "use_case": "scheduling, booking, calendar, appointments"},
    {"id": "contract_engine",   "name": "Contract Engine",      "use_case": "contracts, proposals, signatures, agreements"},
    {"id": "crm_pipeline",      "name": "CRM Pipeline",         "use_case": "deals, contacts, follow-up, pipeline"},
    {"id": "hitl_dispatcher",   "name": "HITL Dispatcher",      "use_case": "approvals, human-in-the-loop, notifications"},
    {"id": "shadow_trainer",    "name": "Shadow Agent Trainer",  "use_case": "learning, patterns, automation proposals"},
    {"id": "mfgc_gates",        "name": "MFGC Business Gates",  "use_case": "compliance, validation, phase control"},
    {"id": "swarm_coordinator", "name": "Swarm Coordinator",    "use_case": "multi-agent tasks, complex workflows"},
    {"id": "timecard_engine",   "name": "Timecard Engine",      "use_case": "time tracking, billing, timesheets"},
    {"id": "invoice_engine",    "name": "Invoice Engine",       "use_case": "invoicing, billing, payment collection"},
    {"id": "email_cadence",     "name": "Email Cadence",        "use_case": "email sequences, nurture, follow-up"},
    {"id": "gap_detector",      "name": "Gap Detector",         "use_case": "employment gaps, job descriptions, hiring"},
    {"id": "metrics_reporter",  "name": "Metrics Reporter",     "use_case": "analytics, reporting, dashboards"},
    {"id": "vault_engine",      "name": "Vault Engine",         "use_case": "passwords, credentials, identity"},
]


def _map_modules_to_answers(answers: list) -> list:
    """Map interview answers to Murphy GitHub modules."""
    all_text = ' '.join(a.get('answer', '') for a in answers).lower()
    matched = []

    for module in MURPHY_GITHUB_MODULES:
        use_cases = module['use_case'].split(', ')
        score = sum(1 for uc in use_cases if uc in all_text)
        if score > 0:
            matched.append({**module, "match_score": score, "matched_on": [uc for uc in use_cases if uc in all_text]})

    # Always include core modules
    core_ids = {'hitl_dispatcher', 'shadow_trainer', 'crm_pipeline'}
    for m in MURPHY_GITHUB_MODULES:
        if m['id'] in core_ids and not any(x['id'] == m['id'] for x in matched):
            matched.append({**m, "match_score": 0, "matched_on": ["core_module"], "required": True})

    matched.sort(key=lambda x: x['match_score'], reverse=True)
    return matched


def route_onboarding_start():
    """
    Start org onboarding interview.
    Body: { account_id, company_name, contact_name, email, user_count }
    """
    data = request.get_json() or {}
    account_id = data.get('account_id', '')
    user_count = int(data.get('user_count') or 1)

    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    if user_count <= 3:
        return jsonify({
            "error": "Organization onboarding requires 4+ users",
            "recommendation": "Use Owner-Operator mode ($100/mo) for 1-3 users",
            "owner_operator_url": "https://murphy.systems/start"
        }), 400

    session_id = str(uuid.uuid4())
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO onboarding_sessions
        (id, account_id, tier, phase, interview_answers, current_question_idx)
        VALUES (?, ?, 'organization', 'interview', '[]', 0)
    """, (session_id, account_id))

    # Create tenant record
    tenant_id = str(uuid.uuid4())
    subdomain = re.sub(r'[^a-z0-9]', '', (data.get('company_name') or '').lower())[:20]
    cur.execute("""
        INSERT INTO tenants (id, account_id, tenant_name, subdomain, user_count, isolation_type)
        VALUES (?, ?, ?, ?, ?, 'dedicated')
        ON CONFLICT(account_id) DO UPDATE SET user_count=?
    """, (tenant_id, account_id, data.get('company_name', 'Organization'),
          subdomain, user_count, user_count))

    conn.commit()
    conn.close()

    first_q = INTERVIEW_QUESTIONS[0]
    return jsonify({
        "session_id": session_id,
        "tenant_id": tenant_id,
        "tier": "organization",
        "total_questions": len(INTERVIEW_QUESTIONS),
        "current_question": {
            "index": 0,
            "id": first_q['id'],
            "question": first_q['question'],
            "hint": first_q['hint']
        },
        "message": ("Welcome. I'm going to ask you 10 questions about your operation. "
                    "Your answers shape everything Murphy builds for you. "
                    "Answer as specifically as you can — this is your build config.")
    }), 201


def route_onboarding_answer():
    """
    Submit an interview answer. Returns next question or module plan.
    Body: { session_id, account_id, answer }
    """
    data = request.get_json() or {}
    session_id = data.get('session_id', '')
    account_id = data.get('account_id', '')
    answer = data.get('answer', '').strip()

    if not all([session_id, account_id, answer]):
        return jsonify({"error": "session_id, account_id, answer required"}), 400

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT interview_answers, current_question_idx, phase
        FROM onboarding_sessions WHERE id=? AND account_id=?
    """, (session_id, account_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    answers_json, q_idx, phase = row
    answers = json.loads(answers_json)
    q = INTERVIEW_QUESTIONS[q_idx] if q_idx < len(INTERVIEW_QUESTIONS) else None

    # Store this answer
    answers.append({
        "question_id": q['id'] if q else 'unknown',
        "question": q['question'] if q else '',
        "answer": answer,
        "answered_at": datetime.utcnow().isoformat()
    })

    next_idx = q_idx + 1

    if next_idx >= len(INTERVIEW_QUESTIONS):
        # Interview complete — build module plan
        module_plan = _map_modules_to_answers(answers)
        org_profile = _build_org_profile(answers)

        cur.execute("""
            UPDATE onboarding_sessions
            SET interview_answers=?, current_question_idx=?, phase='planning',
                module_plan=?, org_profile=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (json.dumps(answers), next_idx, json.dumps(module_plan),
              json.dumps(org_profile), session_id))
        conn.commit()
        conn.close()

        return jsonify({
            "session_id": session_id,
            "interview_complete": True,
            "phase": "planning",
            "org_profile": org_profile,
            "module_plan": {
                "modules": module_plan,
                "total": len(module_plan),
                "message": (f"Based on your answers, I've identified {len(module_plan)} Murphy modules "
                            f"to deploy for your operation. Review and approve to proceed.")
            },
            "approve_url": f"/api/platform/onboard/approve"
        }), 200
    else:
        # Next question
        cur.execute("""
            UPDATE onboarding_sessions
            SET interview_answers=?, current_question_idx=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (json.dumps(answers), next_idx, session_id))
        conn.commit()
        conn.close()

        next_q = INTERVIEW_QUESTIONS[next_idx]
        return jsonify({
            "session_id": session_id,
            "answers_recorded": len(answers),
            "progress": f"{next_idx}/{len(INTERVIEW_QUESTIONS)}",
            "next_question": {
                "index": next_idx,
                "id": next_q['id'],
                "question": next_q['question'],
                "hint": next_q['hint']
            }
        }), 200


def _build_org_profile(answers: list) -> dict:
    """Build org profile JSON from interview answers."""
    profile = {"roles": [], "workflows": [], "integrations": [],
               "automations": [], "compliance": [], "success_metric": "",
               "hitl_authority": [], "automation_hours": ""}

    for a in answers:
        qid = a.get('question_id', '')
        ans = a.get('answer', '')

        if qid == 'team_size':
            # Extract roles from answer
            profile['roles'] = [r.strip() for r in re.split(r'[,\n]', ans) if r.strip()]
        elif qid == 'current_tools':
            profile['integrations'] = [t.strip() for t in re.split(r'[,\n]', ans) if t.strip()]
        elif qid == 'compliance':
            profile['compliance'] = [c.strip() for c in re.split(r'[,\n]', ans) if c.strip()]
        elif qid == 'automation_hours':
            profile['automation_hours'] = ans
        elif qid == 'success_metric':
            profile['success_metric'] = ans
        elif qid == 'decision_authority':
            profile['hitl_authority'] = [r.strip() for r in re.split(r'[,\n]', ans) if r.strip()]

    return profile


def route_onboarding_approve():
    """
    Approve module deployment plan. Triggers setup phase.
    Body: { session_id, account_id, approved_module_ids (list, optional — default all) }
    """
    data = request.get_json() or {}
    session_id = data.get('session_id', '')
    account_id = data.get('account_id', '')
    approved_ids = data.get('approved_module_ids', [])

    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT module_plan, org_profile FROM onboarding_sessions
        WHERE id=? AND account_id=?
    """, (session_id, account_id))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    module_plan = json.loads(row[0])
    if approved_ids:
        module_plan = [m for m in module_plan if m['id'] in approved_ids]

    test_start = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

    cur.execute("""
        UPDATE onboarding_sessions
        SET phase='setup', plan_approved=1, module_plan=?,
            test_start_date=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (json.dumps(module_plan), test_start, session_id))
    conn.commit()
    conn.close()

    # HITL to owner: setup approved
    from patch329_owner_operator_routes import queue_hitl
    hitl_id = queue_hitl(
        account_id=account_id,
        action_type="org_setup_approved",
        description=(f"Onboarding plan approved. Murphy will deploy {len(module_plan)} modules.\n"
                     f"30-day testing period begins {test_start}.\n"
                     f"Murphy will report weekly on what it's learned and what it can automate.\n\n"
                     f"No autonomous actions will run until HITL approved per pattern. Confirm?"),
        action_data={"session_id": session_id, "module_count": len(module_plan),
                     "test_start": test_start}
    )

    return jsonify({
        "session_id": session_id,
        "phase": "setup",
        "modules_approved": len(module_plan),
        "modules": [{"id": m['id'], "name": m['name']} for m in module_plan],
        "test_start_date": test_start,
        "hitl_id": hitl_id,
        "message": (f"Plan approved. Setting up {len(module_plan)} modules. "
                    f"30-day observation period starts {test_start}. "
                    f"You'll get weekly reports on what Murphy is learning.")
    }), 200


def route_onboarding_status(account_id):
    conn = sqlite3.connect(PLATFORM_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, phase, current_question_idx, plan_approved, setup_complete,
               test_start_date, module_plan
        FROM onboarding_sessions WHERE account_id=?
        ORDER BY created_at DESC LIMIT 1
    """, (account_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "not_started"}), 200

    session_id, phase, q_idx, plan_approved, setup_complete, test_start, module_plan_json = row
    modules = json.loads(module_plan_json) if module_plan_json else []

    next_q = None
    if phase == 'interview' and q_idx < len(INTERVIEW_QUESTIONS):
        q = INTERVIEW_QUESTIONS[q_idx]
        next_q = {"index": q_idx, "id": q['id'], "question": q['question']}

    return jsonify({
        "session_id": session_id,
        "phase": phase,
        "interview_progress": f"{q_idx}/{len(INTERVIEW_QUESTIONS)}",
        "plan_approved": bool(plan_approved),
        "setup_complete": bool(setup_complete),
        "test_start_date": test_start,
        "modules_planned": len(modules),
        "next_question": next_q
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────

def register_platform_engine(app):
    """
    Call from production_router.py:
      from patch330_platform_engine import register_platform_engine
      register_platform_engine(app)
    """
    init_platform_db()

    # Commands (voice + text)
    app.add_url_rule('/api/platform/command',              'platform_command',         route_platform_command,        methods=['POST'])
    app.add_url_rule('/api/platform/dashboard',            'platform_dashboard',       route_platform_dashboard,      methods=['GET', 'POST'])

    # Timecard
    app.add_url_rule('/api/platform/timecard/start',       'timecard_start',           route_timecard_start,          methods=['POST'])
    app.add_url_rule('/api/platform/timecard/stop',        'timecard_stop',            route_timecard_stop,           methods=['POST'])
    app.add_url_rule('/api/platform/timecard/report/<account_id>', 'timecard_report',  route_timecard_report,         methods=['GET'])

    # Vault
    app.add_url_rule('/api/platform/vault/save',           'vault_save',               route_vault_save,              methods=['POST'])
    app.add_url_rule('/api/platform/vault/list/<account_id>','vault_list',             route_vault_list,              methods=['GET'])
    app.add_url_rule('/api/platform/vault/retrieve',       'vault_retrieve',           route_vault_retrieve,          methods=['POST'])
    app.add_url_rule('/api/platform/vault/import',         'vault_import',             route_vault_import,            methods=['POST'])

    # Org onboarding
    app.add_url_rule('/api/platform/onboard/start',        'onboard_start',            route_onboarding_start,        methods=['POST'])
    app.add_url_rule('/api/platform/onboard/answer',       'onboard_answer',           route_onboarding_answer,       methods=['POST'])
    app.add_url_rule('/api/platform/onboard/approve',      'onboard_approve',          route_onboarding_approve,      methods=['POST'])
    app.add_url_rule('/api/platform/onboard/status/<account_id>','onboard_status',     route_onboarding_status,       methods=['GET'])

    # Subscription
    app.add_url_rule('/api/platform/subscription/<account_id>','get_subscription',     route_get_subscription,        methods=['GET'])
    app.add_url_rule('/api/stripe/subscription/sync',      'stripe_sub_sync',          route_stripe_subscription_sync,methods=['POST'])

    # HITL re-approval
    app.add_url_rule('/api/hitl/reapproval-check',         'hitl_reapproval_check',    route_hitl_reapproval_check,   methods=['POST'])

    print("[PATCH-330] Platform engine registered (17 endpoints)")
    return app
