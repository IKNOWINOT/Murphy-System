"""
Ship 31e — Stranger Quota / Pay Gate (2026-06-10)
==================================================

Free-tier limits and upgrade-offer logic for stranger_responder.

WHAT THIS IS:
  Adjudicates whether a stranger email gets a tailored reply, an
  upgrade-offer reply, or no reply at all.

POLICY (locked 2026-06-10):
  - free_tier per email_addr per rolling 30 days:
      DIRECT replies:  1 free   (then upgrade offer)
      AMBIENT replies: 3 free   (then upgrade offer)
  - After 4 total upgrade offers across all modes: stop replying
    (avoid pestering)
  - Upgraded tenants: unlimited
  - Founder + allowlist: unlimited
  - Quota tracking lives in billing.db.stranger_quotas

UPGRADE OFFER WORDING:
  "You've used your X free Murphy replies this month. Murphy keeps
   going to work for you on a paid plan starting at \$99/mo.
   See murphy.systems/pricing"

WHY \$99 ENTRY:
  Existing tier (solo). No new tier added (per Murphy verdict — added
  complexity not justified yet).

WHY pricing page not inline checkout:
  Security: Murphy verdict flagged inline link risk. Direct stranger
  to pricing.html, they go through normal NOWPayments flow.

PUBLIC SURFACE:
  check_quota(email_addr, mode) -> {action, reason, quota_state}
    action: 'allow' | 'upgrade_offer' | 'silent_drop'
  record_reply(email_addr, mode, cost_usd) -> None
  upgrade_offer_body(email_addr, mode, days_until_reset) -> str

LAST UPDATED: 2026-06-10
"""

import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

_BILLING_DB = "/var/lib/murphy-production/billing.db"

# Locked policy
FREE_DIRECT_PER_30D = 1
FREE_AMBIENT_PER_30D = 3
MAX_UPGRADE_OFFERS = 4   # then silent drop


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_BILLING_DB, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _domain(addr: str) -> str:
    a = (addr or "").strip().lower()
    return a.split("@", 1)[1] if "@" in a else ""


def _get_or_create(conn: sqlite3.Connection, email_addr: str) -> Dict:
    addr = (email_addr or "").strip().lower()
    row = conn.execute(
        "SELECT * FROM stranger_quotas WHERE email_addr = ?", (addr,)
    ).fetchone()
    if row:
        return dict(row)
    conn.execute(
        """INSERT INTO stranger_quotas
           (email_addr, email_domain, first_seen_at, updated_at)
           VALUES (?, ?, ?, ?)""",
        (addr, _domain(addr), _now_iso(), _now_iso()),
    )
    conn.commit()
    return {
        "email_addr": addr,
        "email_domain": _domain(addr),
        "first_seen_at": _now_iso(),
        "last_reply_at": None,
        "direct_replies_30d": 0,
        "ambient_replies_30d": 0,
        "total_cost_usd": 0.0,
        "upgraded_tenant_id": None,
        "upgrade_offered_at": None,
        "upgrade_offer_count": 0,
        "notes": None,
    }


def _decay_30d(conn: sqlite3.Connection, row: Dict) -> Dict:
    """Reset counters if last_reply_at is > 30 days ago."""
    if not row.get("last_reply_at"):
        return row
    try:
        last = datetime.fromisoformat(row["last_reply_at"].replace("Z", "+00:00"))
    except Exception:
        return row
    if datetime.now(timezone.utc) - last > timedelta(days=30):
        conn.execute(
            """UPDATE stranger_quotas SET direct_replies_30d = 0,
               ambient_replies_30d = 0, updated_at = ? WHERE email_addr = ?""",
            (_now_iso(), row["email_addr"]),
        )
        conn.commit()
        row["direct_replies_30d"] = 0
        row["ambient_replies_30d"] = 0
    return row


def check_quota(email_addr: str, mode: str) -> Dict:
    """Decide what to do with this stranger.
    
    Returns:
      action: 'allow' | 'upgrade_offer' | 'silent_drop'
      reason: human-readable explanation
      quota_state: current counters
    """
    conn = _conn()
    try:
        row = _get_or_create(conn, email_addr)
        row = _decay_30d(conn, row)
        
        # Upgraded tenants get unlimited
        if row.get("upgraded_tenant_id"):
            return {
                "action": "allow",
                "reason": f"upgraded ({row['upgraded_tenant_id']})",
                "quota_state": row,
            }
        
        # Check free-tier limit per mode
        if mode == "direct":
            used = row.get("direct_replies_30d", 0)
            limit = FREE_DIRECT_PER_30D
        else:  # ambient
            used = row.get("ambient_replies_30d", 0)
            limit = FREE_AMBIENT_PER_30D
        
        if used < limit:
            return {
                "action": "allow",
                "reason": f"under free tier ({used}/{limit} {mode} used)",
                "quota_state": row,
            }
        
        # Over free limit → upgrade offer (unless we've offered too many times)
        offer_count = row.get("upgrade_offer_count", 0)
        if offer_count >= MAX_UPGRADE_OFFERS:
            return {
                "action": "silent_drop",
                "reason": f"over limit + offered {offer_count}x already",
                "quota_state": row,
            }
        
        return {
            "action": "upgrade_offer",
            "reason": f"over free tier ({used}/{limit} {mode}), offer #{offer_count + 1}",
            "quota_state": row,
        }
    finally:
        conn.close()


def record_reply(email_addr: str, mode: str, cost_usd: float = 0.0,
                 was_upgrade_offer: bool = False) -> None:
    """Update counters after sending a reply."""
    conn = _conn()
    try:
        addr = (email_addr or "").strip().lower()
        _get_or_create(conn, addr)
        if was_upgrade_offer:
            conn.execute(
                """UPDATE stranger_quotas SET
                   upgrade_offered_at = ?,
                   upgrade_offer_count = upgrade_offer_count + 1,
                   total_cost_usd = total_cost_usd + ?,
                   last_reply_at = ?,
                   updated_at = ?
                   WHERE email_addr = ?""",
                (_now_iso(), float(cost_usd), _now_iso(), _now_iso(), addr),
            )
        elif mode == "direct":
            conn.execute(
                """UPDATE stranger_quotas SET
                   direct_replies_30d = direct_replies_30d + 1,
                   total_cost_usd = total_cost_usd + ?,
                   last_reply_at = ?,
                   updated_at = ?
                   WHERE email_addr = ?""",
                (float(cost_usd), _now_iso(), _now_iso(), addr),
            )
        else:  # ambient
            conn.execute(
                """UPDATE stranger_quotas SET
                   ambient_replies_30d = ambient_replies_30d + 1,
                   total_cost_usd = total_cost_usd + ?,
                   last_reply_at = ?,
                   updated_at = ?
                   WHERE email_addr = ?""",
                (float(cost_usd), _now_iso(), _now_iso(), addr),
            )
        conn.commit()
    finally:
        conn.close()


def upgrade_offer_body(email_addr: str, mode: str, quota_state: Dict) -> str:
    """Compose the upgrade-offer email body."""
    used_direct = quota_state.get("direct_replies_30d", 0)
    used_ambient = quota_state.get("ambient_replies_30d", 0)
    total_cost = quota_state.get("total_cost_usd", 0.0)
    
    return f"""Murphy automates the rule-bound periodic work you've been doing manually.

You've reached your free monthly limit ({used_direct} direct request + {used_ambient} ambient replies). I've enjoyed working for you and want to keep going — but Murphy isn't free past this point.

Plans start at $99/month (solo tier) for unlimited Murphy replies, agent generation across any vertical, and automation execution.

See: https://murphy.systems/pricing

Your free quota resets 30 days after your last reply (currently: {quota_state.get('last_reply_at','')[:10]}).

— Murphy (automated reply; reply STOP to opt out)
"""


def mark_upgraded(email_addr: str, tenant_id: str) -> None:
    """Called when a stranger upgrades to a paid plan. Unlocks unlimited."""
    conn = _conn()
    try:
        conn.execute(
            """UPDATE stranger_quotas SET upgraded_tenant_id = ?, updated_at = ?
               WHERE email_addr = ?""",
            (tenant_id, _now_iso(), (email_addr or "").strip().lower()),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> Dict:
    """Aggregate stats for dashboard / introspection."""
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT 
                 COUNT(*) AS total_strangers,
                 SUM(direct_replies_30d) AS total_direct_30d,
                 SUM(ambient_replies_30d) AS total_ambient_30d,
                 SUM(total_cost_usd) AS total_cost_usd,
                 SUM(CASE WHEN upgraded_tenant_id IS NOT NULL THEN 1 ELSE 0 END) AS upgraded,
                 SUM(CASE WHEN upgrade_offer_count > 0 THEN 1 ELSE 0 END) AS offered
               FROM stranger_quotas"""
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()
