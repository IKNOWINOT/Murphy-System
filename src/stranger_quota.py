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

# Founder policy (locked 2026-06-12):
#   "Everyone is able to email Murphy but with the stipulations of
#    free account 5 free a day. Only 5 until it requests you to sign
#    up or no use."
#
# Window is rolling 24h (per-day, resets at first reply outside window).
# 5/day applies uniformly to all delivery modes (direct, cc, forward, ambient).
# Replies 1-5 are real LLM replies; reply #6 of the day → upgrade offer.
# After MAX_UPGRADE_OFFERS upgrade offers (across separate days),
# silent-drop kicks in to avoid spamming.
FREE_PER_DAY = 5
MAX_UPGRADE_OFFERS = 3   # then silent drop

# Legacy constants kept for any callers still referencing them.
# Both map to the unified per-day allowance.
FREE_DIRECT_PER_30D = FREE_PER_DAY
FREE_AMBIENT_PER_30D = FREE_PER_DAY


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
    """Reset per-day counters if last_reply_at is > 24h ago.

    Renamed in spirit — still called _decay_30d for callsite compat,
    but now enforces a 24-hour rolling window per founder policy
    (Ship 31au, 2026-06-12).
    """
    if not row.get("last_reply_at"):
        return row
    try:
        last = datetime.fromisoformat(
            row["last_reply_at"].replace("Z", "+00:00")
        )
    except Exception:
        return row
    if datetime.now(timezone.utc) - last > timedelta(hours=24):
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
    """Decide what to do with this stranger (Ship 31au policy).

    Policy:
      • 5 replies per rolling 24h window across ALL delivery modes
        (direct, cc, forward, ambient — unified).
      • Replies 1-5: real LLM reply.
      • Reply 6 onward today: upgrade_offer (up to MAX_UPGRADE_OFFERS
        across separate days), then silent_drop.
      • upgrade_offered_at + upgrade_offer_count throttle the prompt.

    Returns:
      action: 'allow' | 'upgrade_offer' | 'silent_drop'
      reason: human-readable explanation
      quota_state: current counters
      remaining_today: how many free replies left in the 24h window
    """
    conn = _conn()
    try:
        row = _get_or_create(conn, email_addr)
        row = _decay_30d(conn, row)  # 24h rolling now

        # Upgraded tenants get unlimited
        if row.get("upgraded_tenant_id"):
            return {
                "action": "allow",
                "reason": f"upgraded ({row['upgraded_tenant_id']})",
                "quota_state": row,
                "remaining_today": -1,
            }

        # Unified per-day counter: sum direct + ambient = "today's replies"
        used = (row.get("direct_replies_30d", 0) +
                row.get("ambient_replies_30d", 0))
        limit = FREE_PER_DAY
        remaining = max(0, limit - used)

        if used < limit:
            return {
                "action": "allow",
                "reason": f"free tier {used+1}/{limit} today ({mode})",
                "quota_state": row,
                "remaining_today": remaining - 1,
            }

        # Over today's limit: have we offered them upgrade today already?
        offer_count = row.get("upgrade_offer_count", 0)
        if offer_count >= MAX_UPGRADE_OFFERS:
            return {
                "action": "silent_drop",
                "reason": (f"over 5/day + offered upgrade "
                           f"{offer_count}x already across separate days"),
                "quota_state": row,
                "remaining_today": 0,
            }

        # Same-day repeat: did we offer already today? Then silent — wait
        # until tomorrow's window opens.
        offered_at = row.get("upgrade_offered_at")
        if offered_at:
            try:
                offered_dt = datetime.fromisoformat(
                    offered_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - offered_dt < timedelta(hours=24):
                    return {
                        "action": "silent_drop",
                        "reason": "already offered upgrade in last 24h",
                        "quota_state": row,
                        "remaining_today": 0,
                    }
            except Exception:
                pass

        return {
            "action": "upgrade_offer",
            "reason": (f"used {used}/{limit} today ({mode}), "
                       f"offer #{offer_count + 1}"),
            "quota_state": row,
            "remaining_today": 0,
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
    """Compose the upgrade-offer email body.

    Ship 31av (2026-06-12): vague-benefit framing per founder direction.
    Does NOT reveal internals (no ship numbers, no module names, no
    commit hashes, no policy code paths). Just what the user gets.
    """
    last_reply = (quota_state.get("last_reply_at") or "")[:10]
    return f"""

Hey — that's 5 free replies from me today, which is the daily ceiling on the free plan. Your inbox resets in 24 hours, so you're welcome back tomorrow with no action needed.

If you'd like more than 5 a day, paid plans start at $99/month and lift the cap entirely. You also unlock:
  • Tailored, deeper replies on your specific work
  • Document generation and automations that take real action
  • Priority response times

Sign up here:  https://murphy.systems/pricing

No worries if you want to stay on free — just hit me again tomorrow.

— Murphy
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
