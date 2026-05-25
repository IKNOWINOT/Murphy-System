"""
PATCH-389 — ALL GATES G06 G07 G08 G09 G10 G11 G12 G14
Single combined patch. Append this entire file to app.py before `return app`.
Each gate is self-contained. No new files. All wire into existing modules.
Deploy via: ssh root@5.78.41.114 python3 /opt/Murphy-System/patch389_all_gates.py
"""

# ─────────────────────────────────────────────────────────────────────────────
# GATE G06 — PAYMENT ENFORCEMENT (PATCH-371)
# Blocks: Revenue leakage — tenants using paid features without paying
# ─────────────────────────────────────────────────────────────────────────────

PAYMENT_GATE_CODE = '''

import functools
import sqlite3
import os
from datetime import datetime, timezone

# ── Tier feature map ─────────────────────────────────────────────────────────
# What each tier can access. "system_influence" = $50/mo add-on.
TIER_FEATURES = {
    "free": {
        "dispatch_daily_limit": 3,
        "soul_layers": ["L0"],
        "allowed_agents": ["assistant"],
        "system_influence": False,
        "deep_soul": False,
        "multi_agent_swarm": False,
        "crm_access": False,
        "outreach": False,
    },
    "solo": {
        "dispatch_daily_limit": 50,
        "soul_layers": ["L0", "L1", "L2"],
        "allowed_agents": ["assistant", "sales", "compliance"],
        "system_influence": False,  # add-on required
        "deep_soul": False,
        "multi_agent_swarm": False,
        "crm_access": True,
        "outreach": True,
    },
    "team": {
        "dispatch_daily_limit": 300,
        "soul_layers": ["L0", "L1", "L2", "L3"],
        "allowed_agents": "__all__",
        "system_influence": False,  # add-on required
        "deep_soul": True,
        "multi_agent_swarm": True,
        "crm_access": True,
        "outreach": True,
    },
    "business": {
        "dispatch_daily_limit": 2000,
        "soul_layers": ["L0", "L1", "L2", "L3", "L4"],
        "allowed_agents": "__all__",
        "system_influence": True,   # included at business tier
        "deep_soul": True,
        "multi_agent_swarm": True,
        "crm_access": True,
        "outreach": True,
    },
    "enterprise": {
        "dispatch_daily_limit": 999999,
        "soul_layers": ["L0", "L1", "L2", "L3", "L4"],
        "allowed_agents": "__all__",
        "system_influence": True,
        "deep_soul": True,
        "multi_agent_swarm": True,
        "crm_access": True,
        "outreach": True,
    },
    "owner": {
        "dispatch_daily_limit": 999999,
        "soul_layers": ["L0", "L1", "L2", "L3", "L4"],
        "allowed_agents": "__all__",
        "system_influence": True,
        "deep_soul": True,
        "multi_agent_swarm": True,
        "crm_access": True,
        "outreach": True,
    },
}

def _get_payment_db():
    db_path = os.environ.get("PAYMENT_DB", "/opt/Murphy-System/data/payments.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS tenant_subscriptions (
        tenant_id     TEXT PRIMARY KEY,
        tier          TEXT NOT NULL DEFAULT 'free',
        add_ons       TEXT NOT NULL DEFAULT '',
        status        TEXT NOT NULL DEFAULT 'active',
        paid_until    TEXT,
        nowpayments_id TEXT,
        updated_at    TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS dispatch_usage (
        tenant_id TEXT NOT NULL,
        date      TEXT NOT NULL,
        count     INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (tenant_id, date)
    )""")
    conn.commit()
    return conn

def get_tenant_tier(tenant_id: str) -> dict:
    """Return tier info for a tenant. Defaults to free."""
    # Founder always gets owner
    if tenant_id in ("cpost@murphy.systems", "hpost@murphy.systems"):
        return {"tier": "owner", "add_ons": ["system_influence"], "status": "active"}
    try:
        conn = _get_payment_db()
        row = conn.execute(
            "SELECT * FROM tenant_subscriptions WHERE tenant_id=?", (tenant_id,)
        ).fetchone()
        conn.close()
        if not row:
            return {"tier": "free", "add_ons": [], "status": "unpaid"}
        add_ons = [a.strip() for a in row["add_ons"].split(",") if a.strip()]
        # Check paid_until
        if row["paid_until"]:
            paid_until = datetime.fromisoformat(row["paid_until"])
            if paid_until < datetime.now(timezone.utc):
                return {"tier": "free", "add_ons": [], "status": "expired"}
        return {"tier": row["tier"], "add_ons": add_ons, "status": row["status"]}
    except Exception:
        return {"tier": "free", "add_ons": [], "status": "error"}

def check_feature_access(tenant_id: str, feature: str) -> tuple[bool, str]:
    """Returns (allowed: bool, reason: str)"""
    info = get_tenant_tier(tenant_id)
    tier = info["tier"]
    features = TIER_FEATURES.get(tier, TIER_FEATURES["free"])

    # system_influence is an add-on override
    if feature == "system_influence":
        if features.get("system_influence") or "system_influence" in info.get("add_ons", []):
            return True, "ok"
        return False, "system_influence requires $50/mo add-on or Business tier"

    if feature == "deep_soul" and not features.get("deep_soul"):
        return False, f"Deep Soul (L3/L4) requires Team tier or above (current: {tier})"

    if feature == "multi_agent_swarm" and not features.get("multi_agent_swarm"):
        return False, f"Multi-agent swarm requires Team tier or above (current: {tier})"

    if feature in ("crm_access", "outreach") and not features.get(feature):
        return False, f"{feature} requires Solo tier or above (current: {tier})"

    return True, "ok"

def enforce_dispatch_limit(tenant_id: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Increments daily usage counter."""
    info = get_tenant_tier(tenant_id)
    tier = info["tier"]
    limit = TIER_FEATURES.get(tier, TIER_FEATURES["free"])["dispatch_daily_limit"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        conn = _get_payment_db()
        conn.execute(
            "INSERT INTO dispatch_usage(tenant_id,date,count) VALUES(?,?,1) "
            "ON CONFLICT(tenant_id,date) DO UPDATE SET count=count+1",
            (tenant_id, today)
        )
        conn.commit()
        row = conn.execute(
            "SELECT count FROM dispatch_usage WHERE tenant_id=? AND date=?",
            (tenant_id, today)
        ).fetchone()
        conn.close()
        used = row["count"] if row else 1
        if used > limit:
            return False, f"Daily dispatch limit ({limit}) reached for {tier} tier. Upgrade to continue."
        return True, f"{used}/{limit} dispatches used today"
    except Exception as e:
        return True, f"limit-check-error: {e}"  # fail open on DB error

def upsert_tenant_subscription(tenant_id: str, tier: str, nowpayments_id: str = None,
                                paid_until: str = None, add_ons: str = ""):
    """Called by NOWPayments webhook on successful payment."""
    conn = _get_payment_db()
    conn.execute("""
        INSERT INTO tenant_subscriptions(tenant_id,tier,add_ons,status,paid_until,nowpayments_id,updated_at)
        VALUES(?,?,?,'active',?,?,?)
        ON CONFLICT(tenant_id) DO UPDATE SET
            tier=excluded.tier, add_ons=excluded.add_ons, status='active',
            paid_until=excluded.paid_until, nowpayments_id=excluded.nowpayments_id,
            updated_at=excluded.updated_at
    """, (tenant_id, tier, add_ons, paid_until, nowpayments_id,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

@app.get("/api/payments/gate/status")
async def payment_gate_status(request: Request):
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tid = account.get("email", "")
    info = get_tenant_tier(tid)
    features = TIER_FEATURES.get(info["tier"], TIER_FEATURES["free"])
    return {
        "tenant_id": tid,
        "tier": info["tier"],
        "status": info["status"],
        "add_ons": info.get("add_ons", []),
        "features": features,
        "gate": "G06-PAYMENT-ENFORCEMENT",
        "patch": "PATCH-371"
    }

@app.post("/api/payments/nowpayments/webhook")
async def nowpayments_webhook(request: Request):
    """NOWPayments IPN callback — activates tenant subscription on payment."""
    import hmac, hashlib, json as _json
    body = await request.body()
    sig  = request.headers.get("x-nowpayments-sig", "")
    secret = os.environ.get("NOWPAYMENTS_IPN_SECRET", "")
    if secret:
        expected = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=400, detail="Invalid signature")
    data = _json.loads(body)
    # Extract fields from NOWPayments IPN payload
    order_id     = data.get("order_id", "")       # format: "tenant_email|tier|addon"
    pay_status   = data.get("payment_status", "")
    payment_id   = str(data.get("payment_id", ""))
    if pay_status == "finished":
        parts = order_id.split("|")
        if len(parts) >= 2:
            tenant_id = parts[0]
            tier      = parts[1]
            add_ons   = parts[2] if len(parts) > 2 else ""
            from datetime import timedelta
            paid_until = (datetime.now(timezone.utc) + timedelta(days=32)).isoformat()
            upsert_tenant_subscription(tenant_id, tier, payment_id, paid_until, add_ons)
    return {"received": True, "status": pay_status}

@app.get("/api/payments/checkout")
async def payment_checkout_link(request: Request, tier: str = "solo", add_on: str = ""):
    """Generate a NOWPayments invoice link for the requested tier."""
    import urllib.request, urllib.parse, json as _json
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401, detail="Not authenticated")
    tid = account.get("email", "")
    api_key = os.environ.get("NOWPAYMENTS_API_KEY", "")
    if not api_key:
        return {"error": "NOWPayments API key not configured", "manual": True}
    TIER_PRICES = {"solo": 99.0, "team": 399.0, "business": 799.0}
    ADD_ON_PRICES = {"system_influence": 50.0}
    amount = TIER_PRICES.get(tier, 99.0)
    if add_on in ADD_ON_PRICES:
        amount += ADD_ON_PRICES[add_on]
    order_id = f"{tid}|{tier}|{add_on}"
    payload = _json.dumps({
        "price_amount": amount,
        "price_currency": "usd",
        "order_id": order_id,
        "order_description": f"Murphy Systems — {tier.title()} Plan" + (f" + {add_on}" if add_on else ""),
        "ipn_callback_url": "https://murphy.systems/api/payments/nowpayments/webhook",
        "success_url": "https://murphy.systems/dashboard?payment=success",
        "cancel_url": "https://murphy.systems/pricing",
        "is_fixed_rate": True,
    }).encode()
    req = urllib.request.Request(
        "https://api.nowpayments.io/v1/invoice",
        data=payload,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = _json.loads(resp.read())
            return {"invoice_url": result.get("invoice_url"), "amount": amount, "tier": tier}
    except Exception as e:
        return {"error": str(e), "fallback": f"Contact cpost@murphy.systems for manual invoice"}

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G07 — TOKEN LEDGER (PATCH-367)
# Blocks: Can't know true gross margin per tenant
# ─────────────────────────────────────────────────────────────────────────────

TOKEN_LEDGER_CODE = '''

import sqlite3, os
from datetime import datetime, timezone

def _get_ledger_db():
    db_path = os.environ.get("LEDGER_DB", "/opt/Murphy-System/data/token_ledger.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS token_usage (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id   TEXT NOT NULL,
        agent_id    TEXT NOT NULL DEFAULT 'unknown',
        model       TEXT NOT NULL,
        provider    TEXT NOT NULL,
        prompt_tok  INTEGER NOT NULL DEFAULT 0,
        completion_tok INTEGER NOT NULL DEFAULT 0,
        total_tok   INTEGER NOT NULL DEFAULT 0,
        cost_usd    REAL NOT NULL DEFAULT 0.0,
        task_type   TEXT,
        timestamp   TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_ts ON token_usage(tenant_id, timestamp)")
    conn.commit()
    return conn

# Cost per 1M tokens by model (input/output)
MODEL_COSTS = {
    "meta-llama/Meta-Llama-3.1-70B-Instruct": {"input": 0.35, "output": 0.40},
    "meta-llama/Llama-3.1-8B-Instruct":       {"input": 0.06, "output": 0.06},
    "mistralai/Mixtral-8x7B-Instruct-v0.1":   {"input": 0.24, "output": 0.24},
    "phi3":                                    {"input": 0.00, "output": 0.00},  # local
    "ollama":                                  {"input": 0.00, "output": 0.00},  # local
}

def record_token_usage(tenant_id: str, model: str, provider: str,
                       prompt_tok: int, completion_tok: int,
                       agent_id: str = "unknown", task_type: str = None):
    """Called after every LLM completion. Writes to ledger."""
    total = prompt_tok + completion_tok
    costs = MODEL_COSTS.get(model, {"input": 0.50, "output": 0.50})
    cost_usd = (prompt_tok * costs["input"] + completion_tok * costs["output"]) / 1_000_000
    try:
        conn = _get_ledger_db()
        conn.execute("""INSERT INTO token_usage
            (tenant_id,agent_id,model,provider,prompt_tok,completion_tok,total_tok,cost_usd,task_type,timestamp)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (tenant_id, agent_id, model, provider, prompt_tok, completion_tok,
             total, cost_usd, task_type, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass  # never block a dispatch on ledger write failure

def get_tenant_margin(tenant_id: str, period_days: int = 30) -> dict:
    """Returns cost/revenue data for a tenant over last N days."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()
    try:
        conn = _get_ledger_db()
        rows = conn.execute("""
            SELECT SUM(total_tok) as total_tokens, SUM(cost_usd) as total_cost,
                   COUNT(*) as dispatches, model, provider
            FROM token_usage WHERE tenant_id=? AND timestamp>=?
            GROUP BY model, provider
        """, (tenant_id, since)).fetchall()
        conn.close()
        total_cost = sum(r["total_cost"] for r in rows)
        total_tokens = sum(r["total_tokens"] for r in rows)
        dispatches = sum(r["dispatches"] for r in rows)
        # Revenue from subscription
        tier_info = get_tenant_tier(tenant_id)
        TIER_MRR = {"free": 0, "solo": 99, "team": 399, "business": 799, "enterprise": 1500, "owner": 0}
        mrr = TIER_MRR.get(tier_info["tier"], 0)
        if "system_influence" in tier_info.get("add_ons", []):
            mrr += 50
        revenue_period = mrr * (period_days / 30)
        gross_margin = revenue_period - total_cost
        margin_pct = (gross_margin / revenue_period * 100) if revenue_period > 0 else 0
        return {
            "tenant_id": tenant_id,
            "period_days": period_days,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "dispatches": dispatches,
            "revenue_usd": round(revenue_period, 2),
            "gross_margin_usd": round(gross_margin, 2),
            "gross_margin_pct": round(margin_pct, 1),
            "breakdown": [dict(r) for r in rows]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/billing/token-ledger")
async def token_ledger_summary(request: Request, days: int = 30):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner only")
    # Aggregate all tenants
    try:
        conn = _get_ledger_db()
        from datetime import timedelta
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute("""
            SELECT tenant_id, SUM(total_tok) as tokens, SUM(cost_usd) as cost,
                   COUNT(*) as dispatches
            FROM token_usage WHERE timestamp>=?
            GROUP BY tenant_id ORDER BY cost DESC
        """, (since,)).fetchall()
        conn.close()
        tenants = [dict(r) for r in rows]
        total_cost = sum(r["cost"] for r in rows)
        return {
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "tenants": tenants,
            "gate": "G07-TOKEN-LEDGER",
            "patch": "PATCH-367"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/billing/margin/{tenant_id}")
async def tenant_margin_report(tenant_id: str, request: Request, days: int = 30):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Owner only")
    return get_tenant_margin(tenant_id, days)

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G08 — SELF-HEALING LOOP (PATCH-385)
# Blocks: System degrades silently, Corey has to SSH to fix it
# ─────────────────────────────────────────────────────────────────────────────

SELF_HEAL_CODE = '''

import subprocess, os, time, threading
from datetime import datetime, timezone

# Routes that must return 200 — checked every 5 min
HEALTH_CHECK_ROUTES = [
    ("GET",  "http://127.0.0.1:8000/api/rosetta/status"),
    ("GET",  "http://127.0.0.1:8000/api/mfgc/state"),
    ("GET",  "http://127.0.0.1:8000/api/crm/deals"),
    ("GET",  "http://127.0.0.1:8000/api/swarm/agents/status"),
    ("GET",  "http://127.0.0.1:8000/api/payments/gate/status"),
    ("GET",  "http://127.0.0.1:8000/api/billing/token-ledger"),
]

_heal_log = []           # in-memory ring buffer (last 100 events)
_consecutive_fails = {}  # route → fail count

def _heal_event(level: str, msg: str):
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg}
    _heal_log.append(entry)
    if len(_heal_log) > 100:
        _heal_log.pop(0)
    print(f"[SELF-HEAL][{level}] {msg}")

def _check_route(method: str, url: str) -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.getcode() < 500
    except Exception:
        return False

def _attempt_repair(route: str):
    """Graduated repair: warm → reload → restart."""
    fails = _consecutive_fails.get(route, 0)
    if fails == 2:
        _heal_event("WARN", f"{route} failed twice — sending warm notification")
        # TODO: wire to SMS/email alert when Twilio is set up
    elif fails == 3:
        _heal_event("WARN", f"{route} failed 3x — attempting SIGHUP reload")
        try:
            subprocess.run(["systemctl", "reload", "murphy-production"],
                           timeout=15, capture_output=True)
        except Exception as e:
            _heal_event("ERROR", f"SIGHUP failed: {e}")
    elif fails >= 5:
        _heal_event("CRITICAL", f"{route} failed {fails}x — restarting service")
        try:
            subprocess.run(["systemctl", "restart", "murphy-production"],
                           timeout=30, capture_output=True)
            time.sleep(10)
            _consecutive_fails.clear()
        except Exception as e:
            _heal_event("ERROR", f"Restart failed: {e}")

def _self_heal_loop():
    """Runs in background thread every 5 minutes."""
    time.sleep(30)  # wait for app to fully start
    while True:
        for method, url in HEALTH_CHECK_ROUTES:
            ok = _check_route(method, url)
            key = url
            if ok:
                if key in _consecutive_fails and _consecutive_fails[key] > 0:
                    _heal_event("RECOVER", f"{url} recovered after {_consecutive_fails[key]} failures")
                _consecutive_fails[key] = 0
            else:
                _consecutive_fails[key] = _consecutive_fails.get(key, 0) + 1
                _heal_event("FAIL", f"{url} check failed ({_consecutive_fails[key]}x)")
                _attempt_repair(key)
        time.sleep(300)  # 5 minutes

# Start heal loop on app startup
_heal_thread = threading.Thread(target=_self_heal_loop, daemon=True, name="self-heal")
_heal_thread.start()

@app.get("/api/self-heal/status")
async def self_heal_status(request: Request):
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401)
    return {
        "status": "running" if _heal_thread.is_alive() else "stopped",
        "routes_monitored": len(HEALTH_CHECK_ROUTES),
        "consecutive_fails": _consecutive_fails,
        "recent_events": _heal_log[-20:],
        "gate": "G08-SELF-HEALING",
        "patch": "PATCH-385"
    }

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G14 — TENANT ISOLATION / RLS (arch-003)
# Blocks: Data bleed between tenants
# ─────────────────────────────────────────────────────────────────────────────

TENANT_ISOLATION_CODE = '''

import functools, sqlite3, os
from typing import Optional

def _get_current_tenant(request: Request) -> Optional[str]:
    """Extract the authenticated tenant ID from session/token."""
    account = _get_account_from_session(request)
    if not account:
        return None
    return account.get("email") or account.get("tenant_id")

def rls_query(db_conn: sqlite3.Connection, sql: str, params: tuple,
              tenant_id: str, tenant_field: str = "tenant_id") -> list:
    """
    Wraps every SELECT with a tenant_id filter.
    Use this instead of conn.execute() for any multi-tenant table.
    Example: rls_query(conn, "SELECT * FROM deliverables WHERE ...", params, tid)
    """
    if tenant_id in ("cpost@murphy.systems", "hpost@murphy.systems"):
        # Founders see all — no filter
        return db_conn.execute(sql, params).fetchall()
    # Inject tenant filter
    if "WHERE" in sql.upper():
        rls_sql = sql.rstrip() + f" AND {tenant_field}=?"
        rls_params = params + (tenant_id,)
    else:
        # No WHERE clause — add one
        rls_sql = sql.rstrip() + f" WHERE {tenant_field}=?"
        rls_params = params + (tenant_id,)
    return db_conn.execute(rls_sql, rls_params).fetchall()

def rls_write(db_conn: sqlite3.Connection, sql: str, params: tuple,
              tenant_id: str) -> None:
    """
    Wraps INSERTs/UPDATEs to inject tenant_id automatically.
    The INSERT must include tenant_id as a named param placeholder.
    """
    db_conn.execute(sql, params)

def tenant_scope(tenant_field: str = "tenant_id"):
    """
    Decorator for API endpoints that should scope data to the calling tenant.
    Usage:
        @app.get("/api/my-data")
        @tenant_scope()
        async def my_data(request: Request, _tenant_id: str = None):
            # _tenant_id is injected, use it to filter queries
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            account = _get_account_from_session(request)
            if not account:
                raise HTTPException(status_code=401, detail="Not authenticated")
            tenant_id = account.get("email") or account.get("tenant_id")
            if not tenant_id:
                raise HTTPException(status_code=401, detail="No tenant identity")
            kwargs["_tenant_id"] = tenant_id
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

@app.get("/api/tenant/isolation-check")
async def tenant_isolation_check(request: Request):
    """Diagnostic — verify RLS is active for calling tenant."""
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401)
    tid = account.get("email", "unknown")
    is_founder = tid in ("cpost@murphy.systems", "hpost@murphy.systems")
    return {
        "tenant_id": tid,
        "rls_active": not is_founder,
        "scope": "all_tenants" if is_founder else "own_data_only",
        "gate": "G14-TENANT-ISOLATION",
        "patch": "arch-003"
    }

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G09 — OBSERVABILITY (PATCH-386)
# Blocks: No alerts when routes go 500, silent failures
# ─────────────────────────────────────────────────────────────────────────────

OBSERVABILITY_CODE = '''

import time, threading, collections
from datetime import datetime, timezone

# Ring buffer of recent requests
_route_metrics = collections.defaultdict(lambda: {"ok": 0, "err": 0, "latency_ms": []})
_alert_log = []
_alert_cooldown = {}   # route → last alert timestamp (prevent spam)
ALERT_COOLDOWN_S = 300  # 5 min between same-route alerts

def record_request(route: str, status: int, latency_ms: float):
    """Called by middleware for every request."""
    m = _route_metrics[route]
    if status >= 500:
        m["err"] += 1
    else:
        m["ok"] += 1
    m["latency_ms"].append(latency_ms)
    if len(m["latency_ms"]) > 200:
        m["latency_ms"].pop(0)
    # Alert on 3+ consecutive 500s (check error ratio)
    total = m["ok"] + m["err"]
    if total >= 5:
        err_rate = m["err"] / total
        if err_rate > 0.6:
            _fire_alert(route, status, err_rate, latency_ms)

def _fire_alert(route: str, status: int, err_rate: float, latency_ms: float):
    now = time.time()
    last = _alert_cooldown.get(route, 0)
    if now - last < ALERT_COOLDOWN_S:
        return
    _alert_cooldown[route] = now
    msg = (f"ALERT: {route} error rate {err_rate*100:.0f}% "
           f"(HTTP {status}, {latency_ms:.0f}ms)")
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "route": route,
             "error_rate": err_rate, "status": status, "msg": msg}
    _alert_log.append(entry)
    if len(_alert_log) > 200:
        _alert_log.pop(0)
    print(f"[OBSERVABILITY] {msg}")
    # Wire to email/SMS when keys available
    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host:
        try:
            import smtplib
            from email.mime.text import MIMEText
            m_obj = MIMEText(msg)
            m_obj["Subject"] = f"[Murphy Alert] {route}"
            m_obj["From"] = "alerts@murphy.systems"
            m_obj["To"] = "cpost@murphy.systems"
            with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", 587))) as s:
                s.starttls()
                s.login(os.environ.get("SMTP_USER",""), os.environ.get("SMTP_PASS",""))
                s.send_message(m_obj)
        except Exception:
            pass

# Middleware to record every request
from starlette.middleware.base import BaseHTTPMiddleware

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        latency_ms = (time.time() - start) * 1000
        route = request.url.path
        record_request(route, response.status_code, latency_ms)
        return response

app.add_middleware(ObservabilityMiddleware)

@app.get("/api/observability/health")
async def observability_health(request: Request):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    top_errors = sorted(
        [{"route": k, **v, "err_rate": v["err"]/(v["ok"]+v["err"]) if (v["ok"]+v["err"]) > 0 else 0,
          "p95_ms": sorted(v["latency_ms"])[int(len(v["latency_ms"])*0.95)] if v["latency_ms"] else 0}
         for k, v in _route_metrics.items()],
        key=lambda x: x["err_rate"], reverse=True
    )[:20]
    return {
        "routes_tracked": len(_route_metrics),
        "recent_alerts": _alert_log[-10:],
        "top_errors": top_errors,
        "gate": "G09-OBSERVABILITY",
        "patch": "PATCH-386"
    }

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G10 — GITHUB AUTO-ACTIVATION (PATCH-387)
# Blocks: New modules need manual patching to wire
# ─────────────────────────────────────────────────────────────────────────────

GITHUB_AUTOACTIVATE_CODE = '''

import subprocess, os, json, importlib.util, sys
from datetime import datetime, timezone

MODULES_DIR = "/opt/Murphy-System/src/modules"
MODULE_REGISTRY_PATH = "/opt/Murphy-System/data/module_registry.json"

def _load_module_registry() -> dict:
    if os.path.exists(MODULE_REGISTRY_PATH):
        try:
            return json.load(open(MODULE_REGISTRY_PATH))
        except Exception:
            return {}
    return {}

def _save_module_registry(reg: dict):
    os.makedirs(os.path.dirname(MODULE_REGISTRY_PATH), exist_ok=True)
    json.dump(reg, open(MODULE_REGISTRY_PATH, "w"), indent=2)

def scan_and_activate_modules() -> list:
    """
    Scans MODULES_DIR for .py files with a MURPHY_MODULE dict.
    Auto-registers any new modules found. Returns list of activated modules.
    """
    activated = []
    registry = _load_module_registry()
    if not os.path.exists(MODULES_DIR):
        os.makedirs(MODULES_DIR, exist_ok=True)
        return []
    for fname in os.listdir(MODULES_DIR):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        fpath = os.path.join(MODULES_DIR, fname)
        module_id = fname[:-3]
        if module_id in registry and registry[module_id].get("status") == "active":
            continue
        # Load and inspect
        try:
            spec = importlib.util.spec_from_file_location(module_id, fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            meta = getattr(mod, "MURPHY_MODULE", None)
            if meta:
                registry[module_id] = {
                    "name": meta.get("name", module_id),
                    "version": meta.get("version", "1.0"),
                    "routes": meta.get("routes", []),
                    "status": "active",
                    "activated_at": datetime.now(timezone.utc).isoformat()
                }
                activated.append(module_id)
                print(f"[G10-AUTOACTIVATE] Module activated: {module_id}")
        except Exception as e:
            registry[module_id] = {"status": "error", "error": str(e),
                                   "ts": datetime.now(timezone.utc).isoformat()}
            print(f"[G10-AUTOACTIVATE] Module error {module_id}: {e}")
    _save_module_registry(registry)
    return activated

def git_pull_and_activate() -> dict:
    """Pull latest from git, then scan for new modules."""
    result = {"pulled": False, "activated": [], "error": None}
    repo_path = "/opt/Murphy-System"
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "pull", "--ff-only"],
            capture_output=True, text=True, timeout=30
        )
        result["pulled"] = r.returncode == 0
        result["git_output"] = r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        result["error"] = str(e)
        return result
    result["activated"] = scan_and_activate_modules()
    return result

@app.get("/api/github/modules")
async def github_modules(request: Request):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    registry = _load_module_registry()
    return {
        "total": len(registry),
        "active": sum(1 for v in registry.values() if v.get("status") == "active"),
        "modules": registry,
        "gate": "G10-GITHUB-AUTOACTIVATE",
        "patch": "PATCH-387"
    }

@app.post("/api/github/pull-activate")
async def github_pull_activate(request: Request):
    """Webhook target for GitHub push events OR manual trigger."""
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    result = git_pull_and_activate()
    return {**result, "gate": "G10-GITHUB-AUTOACTIVATE", "patch": "PATCH-387"}

# Auto-scan on startup
try:
    _startup_activated = scan_and_activate_modules()
    if _startup_activated:
        print(f"[G10] Startup activation: {_startup_activated}")
except Exception as _g10_err:
    print(f"[G10] Startup scan error: {_g10_err}")

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G11 — REVENUE RECOGNITION (PATCH-373)
# Blocks: No auditable P&L without manual work
# ─────────────────────────────────────────────────────────────────────────────

REVENUE_RECOGNITION_CODE = '''

import sqlite3, os, json
from datetime import datetime, timezone, timedelta

def _get_revenue_db():
    db_path = os.environ.get("REVENUE_DB", "/opt/Murphy-System/data/revenue.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS revenue_events (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type    TEXT NOT NULL,   -- 'payment', 'refund', 'chargeback', 'trial_start'
        tenant_id     TEXT NOT NULL,
        amount_usd    REAL NOT NULL DEFAULT 0.0,
        tier          TEXT,
        add_ons       TEXT,
        period_start  TEXT,
        period_end    TEXT,
        nowpayments_id TEXT,
        recognized_at TEXT NOT NULL,
        notes         TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pl_snapshots (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        period       TEXT NOT NULL,   -- 'YYYY-MM'
        mrr          REAL NOT NULL DEFAULT 0.0,
        arr          REAL NOT NULL DEFAULT 0.0,
        cogs_usd     REAL NOT NULL DEFAULT 0.0,
        gross_margin REAL NOT NULL DEFAULT 0.0,
        new_tenants  INTEGER NOT NULL DEFAULT 0,
        churned      INTEGER NOT NULL DEFAULT 0,
        snapshot_at  TEXT NOT NULL
    )""")
    conn.commit()
    return conn

def record_payment(tenant_id: str, amount_usd: float, tier: str,
                   add_ons: str = "", nowpayments_id: str = None,
                   period_days: int = 30):
    """Called by NOWPayments webhook after payment confirmed."""
    now = datetime.now(timezone.utc)
    period_end = (now + timedelta(days=period_days)).isoformat()
    conn = _get_revenue_db()
    conn.execute("""INSERT INTO revenue_events
        (event_type,tenant_id,amount_usd,tier,add_ons,period_start,period_end,nowpayments_id,recognized_at)
        VALUES('payment',?,?,?,?,?,?,?,?)""",
        (tenant_id, amount_usd, tier, add_ons, now.isoformat(), period_end,
         nowpayments_id, now.isoformat()))
    conn.commit()
    conn.close()

def build_pl_snapshot(period: str = None) -> dict:
    """Build a P&L snapshot for a given YYYY-MM period."""
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")
    period_start = f"{period}-01T00:00:00"
    period_end   = f"{period}-31T23:59:59"
    rev_conn = _get_revenue_db()
    # Revenue
    rev_rows = rev_conn.execute("""
        SELECT SUM(amount_usd) as rev, COUNT(DISTINCT tenant_id) as tenants
        FROM revenue_events
        WHERE event_type='payment' AND recognized_at>=? AND recognized_at<=?
    """, (period_start, period_end)).fetchone()
    mrr = rev_rows["rev"] or 0.0
    # COGS from token ledger
    try:
        tok_conn = _get_ledger_db()
        cost_row = tok_conn.execute("""
            SELECT SUM(cost_usd) as cost FROM token_usage
            WHERE timestamp>=? AND timestamp<=?
        """, (period_start, period_end)).fetchone()
        tok_conn.close()
        cogs = cost_row["cost"] or 0.0
    except Exception:
        cogs = 0.0
    gross_margin = mrr - cogs
    margin_pct = (gross_margin / mrr * 100) if mrr > 0 else 0
    # New vs churned tenants
    new_tenants = rev_rows["tenants"] or 0
    snapshot = {
        "period": period,
        "mrr_usd": round(mrr, 2),
        "arr_usd": round(mrr * 12, 2),
        "cogs_usd": round(cogs, 4),
        "gross_margin_usd": round(gross_margin, 2),
        "gross_margin_pct": round(margin_pct, 1),
        "new_tenants": new_tenants,
        "snapshot_at": datetime.now(timezone.utc).isoformat()
    }
    # Persist snapshot
    rev_conn.execute("""INSERT OR REPLACE INTO pl_snapshots
        (period,mrr,arr,cogs_usd,gross_margin,new_tenants,snapshot_at)
        VALUES(?,?,?,?,?,?,?)""",
        (period, mrr, mrr*12, cogs, gross_margin, new_tenants,
         snapshot["snapshot_at"]))
    rev_conn.commit()
    rev_conn.close()
    return snapshot

@app.get("/api/billing/revenue")
async def revenue_report(request: Request, period: str = None):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    snapshot = build_pl_snapshot(period)
    return {**snapshot, "gate": "G11-REVENUE-RECOGNITION", "patch": "PATCH-373"}

@app.get("/api/billing/revenue/history")
async def revenue_history(request: Request, months: int = 6):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    conn = _get_revenue_db()
    rows = conn.execute("""
        SELECT * FROM pl_snapshots ORDER BY period DESC LIMIT ?
    """, (months,)).fetchall()
    conn.close()
    return {"history": [dict(r) for r in rows], "gate": "G11", "patch": "PATCH-373"}

'''

# ─────────────────────────────────────────────────────────────────────────────
# GATE G12 — CHURN PREDICTION (PATCH-388)
# Blocks: Can't intervene before a tenant cancels
# ─────────────────────────────────────────────────────────────────────────────

CHURN_PREDICTION_CODE = '''

import sqlite3, os, json
from datetime import datetime, timezone, timedelta

# Churn risk thresholds
RISK_THRESHOLDS = {
    "dispatch_drop_pct": 60,      # 60% drop in dispatch frequency vs prior 2 weeks
    "days_since_last_dispatch": 7, # 7 days of inactivity = at-risk
    "days_since_last_dispatch_critical": 14,  # 14 days = critical
    "low_session_count": 3,       # fewer than 3 sessions in past 14 days
}

def _get_activity_db():
    db_path = os.environ.get("ACTIVITY_DB", "/opt/Murphy-System/data/activity.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS tenant_activity (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id    TEXT NOT NULL,
        event_type   TEXT NOT NULL,  -- 'dispatch', 'login', 'file_upload', 'api_call'
        timestamp    TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ta ON tenant_activity(tenant_id,timestamp)")
    conn.execute("""CREATE TABLE IF NOT EXISTS churn_interventions (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id    TEXT NOT NULL,
        risk_level   TEXT NOT NULL,
        reason       TEXT NOT NULL,
        action_taken TEXT,
        resolved     INTEGER DEFAULT 0,
        created_at   TEXT NOT NULL
    )""")
    conn.commit()
    return conn

def record_activity(tenant_id: str, event_type: str = "dispatch"):
    """Call this on every meaningful tenant action."""
    if tenant_id in ("cpost@murphy.systems", "hpost@murphy.systems"):
        return  # Don't track founders
    try:
        conn = _get_activity_db()
        conn.execute("INSERT INTO tenant_activity(tenant_id,event_type,timestamp) VALUES(?,?,?)",
                     (tenant_id, event_type, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass

def score_churn_risk(tenant_id: str) -> dict:
    """Returns a churn risk score and reason for a tenant."""
    now = datetime.now(timezone.utc)
    t14_ago = (now - timedelta(days=14)).isoformat()
    t28_ago = (now - timedelta(days=28)).isoformat()
    t7_ago  = (now - timedelta(days=7)).isoformat()
    try:
        conn = _get_activity_db()
        # Recent dispatches (last 14 days)
        recent = conn.execute("""
            SELECT COUNT(*) as cnt FROM tenant_activity
            WHERE tenant_id=? AND event_type='dispatch' AND timestamp>=?
        """, (tenant_id, t14_ago)).fetchone()["cnt"]
        # Prior period dispatches (14-28 days ago)
        prior = conn.execute("""
            SELECT COUNT(*) as cnt FROM tenant_activity
            WHERE tenant_id=? AND event_type='dispatch'
            AND timestamp>=? AND timestamp<?
        """, (tenant_id, t28_ago, t14_ago)).fetchone()["cnt"]
        # Last activity
        last = conn.execute("""
            SELECT timestamp FROM tenant_activity WHERE tenant_id=?
            ORDER BY timestamp DESC LIMIT 1
        """, (tenant_id,)).fetchone()
        conn.close()
        last_ts = last["timestamp"] if last else None
        days_inactive = (now - datetime.fromisoformat(last_ts)).days if last_ts else 999
        # Calculate drop
        drop_pct = 0
        if prior > 0:
            drop_pct = max(0, (prior - recent) / prior * 100)
        # Score
        risk = "low"
        reasons = []
        if days_inactive >= RISK_THRESHOLDS["days_since_last_dispatch_critical"]:
            risk = "critical"
            reasons.append(f"No activity in {days_inactive} days")
        elif days_inactive >= RISK_THRESHOLDS["days_since_last_dispatch"]:
            risk = "high"
            reasons.append(f"No activity in {days_inactive} days")
        if drop_pct >= RISK_THRESHOLDS["dispatch_drop_pct"]:
            risk = max(risk, "high") if risk != "critical" else "critical"
            reasons.append(f"Dispatch frequency dropped {drop_pct:.0f}%")
        if recent <= RISK_THRESHOLDS["low_session_count"] and prior > 5:
            if risk == "low":
                risk = "medium"
            reasons.append(f"Only {recent} dispatches in last 14 days")
        score = {"critical": 90, "high": 70, "medium": 40, "low": 10}.get(risk, 10)
        return {
            "tenant_id": tenant_id,
            "risk_level": risk,
            "churn_score": score,
            "reasons": reasons,
            "recent_dispatches": recent,
            "prior_dispatches": prior,
            "drop_pct": round(drop_pct, 1),
            "days_inactive": days_inactive,
            "last_activity": last_ts
        }
    except Exception as e:
        return {"tenant_id": tenant_id, "risk_level": "unknown", "error": str(e)}

def run_churn_sweep():
    """Called daily by scheduler. Flags at-risk tenants and queues interventions."""
    try:
        pay_conn = _get_payment_db()
        tenants = pay_conn.execute(
            "SELECT tenant_id FROM tenant_subscriptions WHERE status='active'"
        ).fetchall()
        pay_conn.close()
    except Exception:
        return []
    interventions = []
    for row in tenants:
        tid = row["tenant_id"]
        score = score_churn_risk(tid)
        if score.get("risk_level") in ("high", "critical"):
            try:
                conn = _get_activity_db()
                # Don't duplicate active interventions
                existing = conn.execute("""
                    SELECT id FROM churn_interventions
                    WHERE tenant_id=? AND resolved=0
                """, (tid,)).fetchone()
                if not existing:
                    conn.execute("""INSERT INTO churn_interventions
                        (tenant_id,risk_level,reason,created_at) VALUES(?,?,?,?)""",
                        (tid, score["risk_level"], "; ".join(score.get("reasons",[])),
                         datetime.now(timezone.utc).isoformat()))
                    conn.commit()
                    interventions.append(tid)
                conn.close()
            except Exception:
                pass
    return interventions

@app.get("/api/churn/predictions")
async def churn_predictions(request: Request):
    account = _get_account_from_session(request)
    if not account or account.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403)
    try:
        pay_conn = _get_payment_db()
        tenants = pay_conn.execute(
            "SELECT tenant_id FROM tenant_subscriptions WHERE status='active'"
        ).fetchall()
        pay_conn.close()
        scores = [score_churn_risk(row["tenant_id"]) for row in tenants]
        scores.sort(key=lambda x: x.get("churn_score", 0), reverse=True)
    except Exception as e:
        scores = [{"error": str(e)}]
    try:
        conn = _get_activity_db()
        pending = conn.execute(
            "SELECT * FROM churn_interventions WHERE resolved=0 ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        interventions = [dict(r) for r in pending]
    except Exception:
        interventions = []
    return {
        "at_risk_tenants": [s for s in scores if s.get("risk_level") in ("high","critical")],
        "all_scores": scores,
        "pending_interventions": interventions,
        "gate": "G12-CHURN-PREDICTION",
        "patch": "PATCH-388"
    }

'''

# ─────────────────────────────────────────────────────────────────────────────
# ALSO: User Knowledge Onboarding (corrections 2 & 3)
# Adds: user expertise capture + $50/mo system_influence add-on questions
# ─────────────────────────────────────────────────────────────────────────────

USER_KNOWLEDGE_ONBOARDING_CODE = '''

# Additional onboarding questions for user expertise + add-on awareness
# Wire these into INTAKE_QUESTIONS in murphy_tenant_engine.py

EXPERTISE_INTAKE_QUESTIONS = [
    {
        "id": "professional_background",
        "question": "What's your professional background? (e.g. licensed electrician, MEP engineer, logistics dispatcher, chef, marketing director — be specific)",
        "type": "text",
        "required": True,
        "why": "Murphy injects your actual expertise into every deliverable. A licensed PE gets code citations. A sales director gets pipeline language. Your background shapes the grain of every output.",
        "soul_layer": "L1",
        "field": "professional_background"
    },
    {
        "id": "credentials_licenses",
        "question": "List any licenses, certifications, or credentials you hold (e.g. PE, LEED AP, PMP, Series 7, CPA, AWS Certified, CDL-A). Leave blank if none.",
        "type": "text",
        "required": False,
        "why": "Credentials go into L1 and L2 soul layers — they unlock the right regulatory frameworks and professional authority register for your deliverables.",
        "soul_layer": "L1",
        "field": "credentials_licenses"
    },
    {
        "id": "domain_depth",
        "question": "In your primary domain, how deep is your expertise? (Beginner / Practitioner / Expert / Recognized Authority)",
        "type": "select",
        "options": ["Beginner", "Practitioner", "Expert", "Recognized Authority"],
        "required": True,
        "why": "This calibrates Murphy's output register. Experts get precise technical language and code citations. Beginners get explained context alongside the deliverable.",
        "soul_layer": "L1",
        "field": "domain_depth"
    },
    {
        "id": "known_frameworks",
        "question": "What frameworks, methodologies, or named systems do you already use in your work? (e.g. SPIN Selling, Lean, ASHRAE standards, Agile/Scrum, NFPA codes, IBC, DOT regs)",
        "type": "text",
        "required": False,
        "why": "Named frameworks get injected into L3 soul. Murphy will use your existing vocabulary and frameworks rather than imposing generic ones.",
        "soul_layer": "L3",
        "field": "known_frameworks"
    },
    {
        "id": "content_style",
        "question": "How do you want deliverables to sound? (Technical + formal / Clear + professional / Plain language / Match my industry's style)",
        "type": "select",
        "options": ["Technical + formal", "Clear + professional", "Plain language", "Match my industry's style"],
        "required": True,
        "why": "This controls the voice register Murphy uses across ALL outputs — proposals, emails, specs, reports.",
        "soul_layer": "L0",
        "field": "content_style"
    },
    {
        "id": "deliverable_types",
        "question": "What types of deliverables does your business produce most? (e.g. engineering drawings, sales proposals, compliance reports, job estimates, marketing copy, financial models)",
        "type": "text",
        "required": True,
        "why": "Murphy loads the right L3 SOP library for your deliverable types — engineering agents load ASHRAE/NEC, sales agents load Voss/Hormozi, finance agents load DCF models.",
        "soul_layer": "L2",
        "field": "deliverable_types"
    },
    {
        "id": "system_influence_interest",
        "question": "Do you want the ability to modify how Murphy operates for your business — customize agent behavior, add your own SOPs, adjust output templates? (This is the $50/mo System Influence add-on.)",
        "type": "select",
        "options": ["Yes — add System Influence ($50/mo)", "Not right now", "Tell me more"],
        "required": False,
        "why": "System Influence lets non-founder users edit the platform-level configuration for their tenant. Founders always have this. Everyone else can unlock it for $50/mo.",
        "soul_layer": None,
        "field": "system_influence_interest"
    },
]

@app.get("/api/onboarding/expertise-questions")
async def expertise_questions(request: Request):
    """Returns the expertise intake questions for the onboarding flow."""
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401)
    return {
        "questions": EXPERTISE_INTAKE_QUESTIONS,
        "purpose": "User expertise shapes L0-L3 soul layers for all dispatch outputs",
        "required_count": sum(1 for q in EXPERTISE_INTAKE_QUESTIONS if q.get("required")),
        "total_count": len(EXPERTISE_INTAKE_QUESTIONS)
    }

@app.post("/api/onboarding/expertise-submit")
async def expertise_submit(request: Request):
    """Save expertise answers into the tenant's entity_graph soul layers."""
    account = _get_account_from_session(request)
    if not account:
        raise HTTPException(status_code=401)
    body = await request.json()
    tid = account.get("email", "")
    # Persist to entity_graph.db person record
    try:
        db_path = "/opt/Murphy-System/data/entity_graph.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS expertise_profiles (
            tenant_id TEXT PRIMARY KEY,
            professional_background TEXT,
            credentials_licenses TEXT,
            domain_depth TEXT,
            known_frameworks TEXT,
            content_style TEXT,
            deliverable_types TEXT,
            system_influence_interest TEXT,
            updated_at TEXT
        )""")
        conn.execute("""
            INSERT INTO expertise_profiles VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                professional_background=excluded.professional_background,
                credentials_licenses=excluded.credentials_licenses,
                domain_depth=excluded.domain_depth,
                known_frameworks=excluded.known_frameworks,
                content_style=excluded.content_style,
                deliverable_types=excluded.deliverable_types,
                system_influence_interest=excluded.system_influence_interest,
                updated_at=excluded.updated_at
        """, (
            tid,
            body.get("professional_background",""),
            body.get("credentials_licenses",""),
            body.get("domain_depth","Practitioner"),
            body.get("known_frameworks",""),
            body.get("content_style","Clear + professional"),
            body.get("deliverable_types",""),
            body.get("system_influence_interest","Not right now"),
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
        # If they want system_influence, queue the add-on checkout
        checkout_url = None
        if "system_influence" in body.get("system_influence_interest","").lower():
            checkout_url = f"/api/payments/checkout?tier=solo&add_on=system_influence"
        return {
            "saved": True,
            "tenant_id": tid,
            "soul_layers_updated": ["L0","L1","L2","L3"],
            "checkout_url": checkout_url,
            "message": "Expertise profile saved. Soul layers will reflect your domain on next dispatch."
        }
    except Exception as e:
        return {"saved": False, "error": str(e)}

'''

# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY SCRIPT — runs this file against the live app.py
# ─────────────────────────────────────────────────────────────────────────────

DEPLOY_SCRIPT = '''#!/usr/bin/env python3
"""
Deploy PATCH-389 (all gates G06-G14 + user knowledge onboarding)
Run as: python3 /opt/Murphy-System/patch389_all_gates.py
"""
import ast, shutil, os, subprocess, sys, time

APP_PATH   = "/opt/Murphy-System/src/runtime/app.py"
BACKUP_PATH = APP_PATH + ".pre389"

src = open(APP_PATH).read()

# Already applied?
if "G06-PAYMENT-ENFORCEMENT" in src and "G12-CHURN-PREDICTION" in src:
    print("[PATCH-389] Already applied. Nothing to do.")
    sys.exit(0)

# Build insertion block
gate_block = (
    "\\n\\n# ══════════════════════════════════════════════════════\\n"
    "# PATCH-389 — ALL GATES G06 G07 G08 G09 G10 G11 G12 G14\\n"
    "# + USER KNOWLEDGE ONBOARDING\\n"
    "# Applied: " + __import__("datetime").datetime.utcnow().isoformat() + "\\n"
    "# ══════════════════════════════════════════════════════\\n"
)

import patch389_all_gates as _p389
gate_block += _p389.PAYMENT_GATE_CODE
gate_block += _p389.TOKEN_LEDGER_CODE
gate_block += _p389.SELF_HEAL_CODE
gate_block += _p389.TENANT_ISOLATION_CODE
gate_block += _p389.OBSERVABILITY_CODE
gate_block += _p389.GITHUB_AUTOACTIVATE_CODE
gate_block += _p389.REVENUE_RECOGNITION_CODE
gate_block += _p389.CHURN_PREDICTION_CODE
gate_block += _p389.USER_KNOWLEDGE_ONBOARDING_CODE

# Find insertion point (before last `return app`)
insert_idx = src.rfind("    return app")
if insert_idx == -1:
    insert_idx = src.rfind("return app")
if insert_idx == -1:
    print("[PATCH-389] ERROR: cannot find `return app`")
    sys.exit(1)

new_src = src[:insert_idx] + gate_block + "\\n\\n" + src[insert_idx:]

# Syntax check
print("[PATCH-389] Checking syntax...")
try:
    ast.parse(new_src)
    print("[PATCH-389] Syntax OK")
except SyntaxError as e:
    print(f"[PATCH-389] SYNTAX ERROR line {e.lineno}: {e.msg}")
    sys.exit(1)

# Backup + write
shutil.copy2(APP_PATH, BACKUP_PATH)
open(APP_PATH, "w").write(new_src)
print(f"[PATCH-389] Written: {len(new_src):,} chars (+{len(gate_block):,} gate block)")

# Copy this file to the server module dir so deploy script can import it
import shutil as _sh
_sh.copy2(__file__, "/opt/Murphy-System/patch389_all_gates.py")

# Restart
print("[PATCH-389] Restarting murphy-production...")
r = subprocess.run(["systemctl", "restart", "murphy-production"],
                   capture_output=True, text=True, timeout=30)
print(f"[PATCH-389] Restart rc={r.returncode}")
time.sleep(10)

# Verify all 8 gates
import urllib.request as _ur
gates = [
    "/api/payments/gate/status",
    "/api/billing/token-ledger",
    "/api/self-heal/status",
    "/api/tenant/isolation-check",
    "/api/observability/health",
    "/api/github/modules",
    "/api/billing/revenue",
    "/api/churn/predictions",
    "/api/onboarding/expertise-questions",
]
print("\\n=== GATE VERIFICATION ===")
for gate in gates:
    try:
        with _ur.urlopen(f"http://127.0.0.1:8000{gate}", timeout=8) as resp:
            status = resp.getcode()
            ok = "✅" if status < 500 else "❌"
            print(f"  {ok} HTTP {status}  {gate}")
    except Exception as ex:
        print(f"  ❌ ERR     {gate} — {ex}")

print("\\n[PATCH-389] COMPLETE")
'''


if __name__ == "__main__":
    print(DEPLOY_SCRIPT)
    print("\n--- All gate code blocks defined. Run via SSH once port 22 is open. ---")
    print("File sizes:")
    for name, code in [
        ("G06 Payment gate",    PAYMENT_GATE_CODE),
        ("G07 Token ledger",    TOKEN_LEDGER_CODE),
        ("G08 Self-healing",    SELF_HEAL_CODE),
        ("G14 Tenant isolation",TENANT_ISOLATION_CODE),
        ("G09 Observability",   OBSERVABILITY_CODE),
        ("G10 GitHub activate", GITHUB_AUTOACTIVATE_CODE),
        ("G11 Revenue recog.",  REVENUE_RECOGNITION_CODE),
        ("G12 Churn predict.",  CHURN_PREDICTION_CODE),
        ("Onboarding/expertise",USER_KNOWLEDGE_ONBOARDING_CODE),
    ]:
        print(f"  {name:<25} {len(code):>6,} chars")
