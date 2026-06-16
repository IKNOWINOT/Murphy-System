#!/usr/bin/env python3
"""Ship 31ao.SEE Phase 2 — /api/self/state_of_complete

ONE endpoint. Full snapshot of Murphy's current state. Pollable by /is.
Read-only. No side effects. Always responds in <1s.
"""
import sqlite3, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

EVENT_LOG = "/var/lib/murphy-production/event_log.db"
MAIL_DB   = "/var/lib/murphy-production/murphy_mail.db"
USERS_DB  = "/var/lib/murphy-production/murphy_users.db"
BILLING   = "/var/lib/murphy-production/billing.db"
CRM       = "/var/lib/murphy-production/crm.db"

def _safe(fn, default):
    try: return fn()
    except Exception as e: return default

def _q(db, sql, default=None):
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return c.execute(sql).fetchone()
    except Exception:
        return default

def _qall(db, sql, default=None):
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as c:
            return c.execute(sql).fetchall()
    except Exception:
        return default or []

def build_state_of_complete():
    now = datetime.now(timezone.utc).isoformat()
    h24 = "datetime('now','-1 day')"

    # event_log roll-ups
    el_total = _q(EVENT_LOG, "SELECT COUNT(*) FROM state_transitions")
    el_24h   = _q(EVENT_LOG, f"SELECT COUNT(*) FROM state_transitions WHERE ts > {h24}")
    el_fail  = _q(EVENT_LOG, f"SELECT COUNT(*) FROM state_transitions WHERE transition='fail' AND ts > {h24}")
    el_succ  = _q(EVENT_LOG, f"SELECT COUNT(*) FROM state_transitions WHERE transition='succeed' AND ts > {h24}")

    by_subject = _qall(EVENT_LOG,
        f"SELECT subject, transition, COUNT(*) FROM state_transitions "
        f"WHERE ts > {h24} GROUP BY subject, transition ORDER BY 3 DESC LIMIT 15")

    # outbound mail
    out_24h = _q(MAIL_DB,
        f"SELECT COUNT(*) FROM outbound_email_queue WHERE created_at > {h24}")

    # signups
    users_total = _q(USERS_DB, "SELECT COUNT(*) FROM user_accounts")
    users_24h   = _q(USERS_DB, f"SELECT COUNT(*) FROM user_accounts WHERE created_at > {h24}")

    # billing
    cost_24h = _q(BILLING, f"SELECT ROUND(SUM(amount_usd),2) FROM stranger_quotas WHERE last_reply_at > {h24}")

    # CRM
    crm_total = _q(CRM, "SELECT COUNT(*) FROM contacts")

    # variance zone — coarse heuristic until 33/66 wiring exists
    fail_rate = 0.0
    if el_24h and el_24h[0] and el_24h[0] > 10:
        fail_rate = (el_fail[0] or 0) / el_24h[0]
    if   fail_rate > 0.20: zone = "red"
    elif fail_rate > 0.10: zone = "orange"
    elif fail_rate > 0.03: zone = "yellow"
    else:                  zone = "green"

    return {
        "now": now,
        "zone": zone,
        "fail_rate_24h": round(fail_rate, 4),
        "event_log": {
            "total_lifetime":     (el_total or [0])[0],
            "transitions_24h":    (el_24h or [0])[0],
            "succeeded_24h":      (el_succ or [0])[0],
            "failed_24h":         (el_fail or [0])[0],
            "top_subjects_24h":   [{"subject": r[0], "transition": r[1], "count": r[2]} for r in (by_subject or [])],
        },
        "mail": {
            "outbound_24h":       (out_24h or [0])[0],
        },
        "users": {
            "total":              (users_total or [0])[0],
            "signups_24h":        (users_24h or [0])[0],
        },
        "costs": {
            "stranger_replies_usd_24h": (cost_24h or [0])[0] or 0,
        },
        "crm": {
            "contacts_total":     (crm_total or [0])[0],
        },
        "narration": _narrate(zone, fail_rate, el_24h, el_succ, el_fail, out_24h, users_24h),
    }

def _narrate(zone, fail_rate, el_24h, el_succ, el_fail, out_24h, users_24h):
    """Murphy's self-talk paragraph — what's the picture?"""
    e24  = (el_24h or [0])[0]
    es   = (el_succ or [0])[0]
    ef   = (el_fail or [0])[0]
    o24  = (out_24h or [0])[0]
    u24  = (users_24h or [0])[0]

    lines = []
    lines.append(f"Last 24h I logged {e24} state transitions ({es} succeeds, {ef} fails).")
    if e24 > 0:
        lines.append(f"Fail rate {round(fail_rate*100, 1)}% — variance zone {zone.upper()}.")
    lines.append(f"Outbound email queue activity: {o24} new items.")
    lines.append(f"New signups: {u24}.")
    if u24 == 0 and o24 == 0:
        lines.append("Quiet day — no inbound triggers, no outbound, no signups. Nothing failed but nothing moved.")
    if zone == "red":
        lines.append("⚠ Red zone. Recent fail rate exceeds 20%. Needs founder review.")
    elif zone == "orange":
        lines.append("Orange — fail rate above 10%. Monitoring.")
    return " ".join(lines)


if __name__ == "__main__":
    print(json.dumps(build_state_of_complete(), indent=2))
