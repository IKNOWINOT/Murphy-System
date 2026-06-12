"""Ship 31ah — Claim/Login/Me bridge (per-tenant scope).

Wires:
  POST /claim/{token}  — password form submission, creates user+tenant+session
  GET  /login          — form
  POST /login          — auth, session cookie
  GET  /me             — JSON tenant snapshot
  GET  /dashboard      — HTML tenant dashboard (Ship 31ak entry)
  POST /logout         — clear session

Composes with: free_tier_counter, murphy_users.db, tenants.db,
billing.tenant_subscriptions, murphy_registry, llm_cost_ledger.
"""
import bcrypt, json, secrets, sqlite3
from datetime import datetime, timedelta, timezone

USERS_DB    = "/var/lib/murphy-production/murphy_users.db"
TENANTS_DB  = "/var/lib/murphy-production/tenants.db"
BILLING_DB  = "/var/lib/murphy-production/billing.db"
REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"
LEDGER_DB   = "/var/lib/murphy-production/llm_cost_ledger.db"

SESSION_DAYS = 30
COOKIE_NAME  = "murphy_session"

TIER_INCLUDES = {
    "free": ["client_solutions_classify"],
    "solo": [
        "client_solutions_classify", "sales_followup_send",
        "automations.workflows.list", "automations.workflows.execute",
        "hitl.pending.list",
    ],
    "team": [
        "client_solutions_classify", "sales_followup_send",
        "automations.workflows.list", "automations.workflows.execute",
        "automations.workflows.get", "automations.commission",
        "boards.list", "boards.create", "boards.get", "boards.update",
        "document.gates.list", "document.gates.evaluate",
        "hitl.pending.list", "hitl.queue.list", "hitl.decide",
    ],
    "business": [
        "client_solutions_classify", "sales_followup_send",
        "automations.workflows.list", "automations.workflows.execute",
        "automations.workflows.get", "automations.commission",
        "automations.workflows.delete", "automations.fire_trigger",
        "boards.list", "boards.create", "boards.get", "boards.update",
        "boards.delete",
        "document.gates.list", "document.gates.evaluate",
        "document.blocks.get", "document.blocks.update",
        "hitl.pending.list", "hitl.queue.list", "hitl.decide",
        "hitl.intervention.respond",
        "production.proposals.list", "production.proposals.create",
        "production.work_orders.create", "production.schedule.set",
        "integration_bus.process", "rosetta_dispatch", "revenue_driver",
        "audit_history_read",
    ],
    "enterprise": ["__all__"],
}

TIER_LABELS = {
    "free":       ("Free",       0,    "5 Murphy emails/month, ad-supported"),
    "solo":       ("Solo",       99,   "50 emails/month, 1 saved automation"),
    "team":       ("Team",       399,  "250 emails, 5 automations, boards"),
    "business":   ("Business",   799,  "Unlimited, 20 automations, full surface"),
    "enterprise": ("Enterprise", 0,    "Custom — quote + hardware"),
}


def _hash_pw(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(12)).decode()
def _check_pw(pw, h):
    try: return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception: return False
def _now(): return datetime.now(timezone.utc).isoformat()
def _new_id(p, n=12): return f"{p}_{secrets.token_hex(n)}"
def _new_token(n=32): return secrets.token_urlsafe(n)


def get_user_by_email(email):
    with sqlite3.connect(USERS_DB) as c:
        r = c.execute(
            "SELECT account_id, email, data FROM user_accounts WHERE email=?",
            (email.lower(),)
        ).fetchone()
    if not r: return None
    return {"account_id": r[0], "email": r[1], "data": json.loads(r[2] or "{}")}


def create_user_with_password(email, password):
    account_id = _new_id("acct")
    data = {
        "pw_hash": _hash_pw(password),
        "tier": "free",
        "claimed_at": _now(),
        "auth_method": "claim",
    }
    with sqlite3.connect(USERS_DB) as c:
        c.execute(
            "INSERT INTO user_accounts (account_id, email, data) VALUES (?,?,?)",
            (account_id, email.lower(), json.dumps(data))
        )
        c.commit()
    return {"account_id": account_id, "email": email.lower(), "data": data}


def update_user_password(email, new_pw):
    u = get_user_by_email(email)
    if not u: raise ValueError("no such user")
    u["data"]["pw_hash"] = _hash_pw(new_pw)
    u["data"]["pw_changed_at"] = _now()
    with sqlite3.connect(USERS_DB) as c:
        c.execute(
            "UPDATE user_accounts SET data=?, updated_at=datetime('now') WHERE email=?",
            (json.dumps(u["data"]), email.lower())
        )
        c.commit()


def get_or_create_tenant_for_user(account_id, email):
    with sqlite3.connect(TENANTS_DB) as c:
        rows = c.execute(
            "SELECT tenant_id, config FROM tenants WHERE state='active'"
        ).fetchall()
        for tid, cfg_s in rows:
            try:
                cfg = json.loads(cfg_s or "{}")
                if cfg.get("owner_account_id") == account_id:
                    return tid
            except Exception:
                continue

    tenant_id = _new_id("tenant", 8)
    cfg = {
        "owner_account_id": account_id,
        "owner_email": email,
        "tier": "free",
        "interval": "monthly",
        "provisioned_via": "claim_signup",
        "created_at": _now(),
    }
    with sqlite3.connect(TENANTS_DB) as c:
        c.execute(
            """INSERT INTO tenants
               (tenant_id, name, state, isolation, config, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (tenant_id, f"{email.split('@')[0]}'s workspace",
             "active", "strict", json.dumps(cfg), _now(), _now())
        )
        c.commit()

    with sqlite3.connect(BILLING_DB) as c:
        c.execute(
            """INSERT OR REPLACE INTO tenant_subscriptions
               (tenant_id, tier, add_ons, status, paid_until, updated_at)
               VALUES (?, 'free', '', 'active', NULL, ?)""",
            (tenant_id, _now())
        )
        c.commit()
    return tenant_id


def create_session(account_id, email, tenant_id):
    sid = _new_token(32)
    expires = (datetime.now(timezone.utc) +
               timedelta(days=SESSION_DAYS)).isoformat()
    with sqlite3.connect(USERS_DB) as c:
        c.execute(
            """INSERT INTO session_store
               (session_id, tenant_id, account_id, email, expires_at)
               VALUES (?,?,?,?,?)""",
            (sid, tenant_id, account_id, email, expires)
        )
        c.commit()
    return sid


def lookup_session(sid):
    if not sid: return None
    with sqlite3.connect(USERS_DB) as c:
        r = c.execute(
            """SELECT account_id, email, tenant_id, expires_at
               FROM session_store WHERE session_id=?""",
            (sid,)
        ).fetchone()
    if not r: return None
    acct, email, tid, exp = r
    try:
        if datetime.fromisoformat(exp) < datetime.now(timezone.utc):
            return None
    except Exception:
        pass
    return {"account_id": acct, "email": email, "tenant_id": tid}


def destroy_session(sid):
    if not sid: return
    with sqlite3.connect(USERS_DB) as c:
        c.execute("DELETE FROM session_store WHERE session_id=?", (sid,))
        c.commit()


def _first_tier_with(cap_id):
    for tier in ("free", "solo", "team", "business"):
        if cap_id in TIER_INCLUDES.get(tier, []):
            return tier
    return "enterprise"


def get_tenant_snapshot(tenant_id, account_id, email):
    with sqlite3.connect(BILLING_DB) as c:
        row = c.execute(
            "SELECT tier, add_ons, status, paid_until FROM tenant_subscriptions WHERE tenant_id=?",
            (tenant_id,)
        ).fetchone()
    tier, addons_s, status, paid_until = row or ("free", "", "active", None)
    add_ons = [a for a in (addons_s or "").split(",") if a.strip()]

    with sqlite3.connect(LEDGER_DB) as c:
        usage = c.execute(
            """SELECT COALESCE(SUM(llm_calls),0), COALESCE(SUM(llm_cost_usd),0)
               FROM tenant_daily_pnl
               WHERE tenant_id=? AND date >= date('now','start of month')""",
            (tenant_id,)
        ).fetchone()
    llm_calls, llm_cost = usage or (0, 0.0)

    included = TIER_INCLUDES.get(tier, [])
    if "__all__" in included:
        with sqlite3.connect(REGISTRY_DB) as c:
            cap_rows = c.execute(
                "SELECT capability_id FROM registry_capabilities WHERE archived=0"
            ).fetchall()
        included = [r[0] for r in cap_rows]

    with sqlite3.connect(REGISTRY_DB) as c:
        all_caps = c.execute(
            """SELECT capability_id, name, description, domain, risk_class,
                      requires_hitl, gate_summary
               FROM registry_capabilities WHERE archived=0
               ORDER BY domain, capability_id"""
        ).fetchall()

    caps = []
    for cap_id, name, desc, domain, risk, hitl, gates in all_caps:
        caps.append({
            "id": cap_id, "name": name,
            "description": desc or "",
            "domain": domain or "general",
            "risk_class": risk or "green",
            "requires_hitl": bool(hitl),
            "gates_passed": gates or "",
            "unlocked": (cap_id in included) or (cap_id in add_ons),
            "tier_required": _first_tier_with(cap_id),
        })

    label, price, summary = TIER_LABELS.get(tier, ("Unknown", 0, ""))
    return {
        "account": {"email": email, "id": account_id},
        "tenant": {"id": tenant_id},
        "subscription": {
            "tier": tier, "tier_label": label,
            "tier_price_usd": price, "tier_summary": summary,
            "status": status, "paid_until": paid_until,
            "add_ons": add_ons,
        },
        "usage": {
            "llm_calls_mtd": llm_calls,
            "llm_cost_usd_mtd": round(llm_cost, 4),
        },
        "capabilities": caps,
        "all_tiers": [
            {"id": k, "label": v[0], "price_usd": v[1], "summary": v[2]}
            for k, v in TIER_LABELS.items()
        ],
    }


def tenant_can(tenant_id, capability_id):
    if not tenant_id: return False
    with sqlite3.connect(BILLING_DB) as c:
        row = c.execute(
            "SELECT tier, add_ons FROM tenant_subscriptions WHERE tenant_id=?",
            (tenant_id,)
        ).fetchone()
    if not row: return False
    tier, addons_s = row
    add_ons = [a for a in (addons_s or "").split(",") if a.strip()]
    included = TIER_INCLUDES.get(tier, [])
    if "__all__" in included: return True
    return capability_id in included or capability_id in add_ons
