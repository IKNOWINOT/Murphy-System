#!/usr/bin/env python3
"""
Ship 31ck — Org Admin User Management

Implements the locked-in model:
  - Murphy accounts live at platform level (ship31ah_signup.accounts)
  - Tenants are organizations (tenants.db tenants)
  - tenant_members is the join (extended with status/audit)
  - tenant_invitations is the pending-invite state

Flow A: invite-new — recipient creates Murphy account → auto-joined
Flow B: invite-existing — recipient already has account → accepts → joined

Hard rules (locked):
  - 7-day invite TTL
  - removed-then-reinvited: reactivate the SAME membership row (audit thread)
  - seat caps enforced via tier; over-seat = block + upgrade prompt, NEVER auto-charge
  - removed users keep audit history (compliance)
"""
from __future__ import annotations
import sqlite3, secrets, sys, logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/opt/Murphy-System")

TENANTS_DB = "/var/lib/murphy-production/tenants.db"
INVITE_TTL_DAYS = 7

logger = logging.getLogger("tenant_members_31ck")
NOW = lambda: datetime.now(timezone.utc).isoformat()


# ───────── seat caps ─────────

# Source of truth derived from nowpayments_billing.py:
# tier_2_team=5 seats, tier_3_business=15 seats, tier_6_forward_deployed=unlimited
SEAT_CAPS = {
    "tier_0_free":     1,
    "tier_1_solo":     1,
    "tier_2_team":     5,
    "team_synthesis":  5,   # same seat shape as Team (synthesis is feature, not seat)
    "tier_3_business": 15,
    "tier_4_ai_audit": 0,   # audit is engagement, no platform seats
    "tier_5_ops_audit": 0,
    "tier_6_forward_deployed": 9999,  # unlimited within contract
}

def get_seat_cap(tier: str) -> int:
    return SEAT_CAPS.get(tier or "tier_0_free", 1)


def get_tier_for_tenant(tenant_id: str) -> str:
    try:
        from src.platform_engine import get_subscription_status
        return get_subscription_status(tenant_id).get("tier", "tier_0_free")
    except Exception:
        return "tier_0_free"


# ───────── role checks ─────────

def is_member(tenant_id: str, account_id: str) -> bool:
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        r = c.execute(
            "SELECT status FROM tenant_members WHERE tenant_id=? AND user_id=?",
            (tenant_id, account_id)
        ).fetchone()
        return bool(r and r[0] == "active")
    finally: c.close()


def is_admin(tenant_id: str, account_id: str) -> bool:
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        r = c.execute(
            "SELECT role, status FROM tenant_members WHERE tenant_id=? AND user_id=?",
            (tenant_id, account_id)
        ).fetchone()
        return bool(r and r[1] == "active" and r[0] in ("admin", "owner"))
    finally: c.close()


# ───────── list members ─────────

def list_members(tenant_id: str) -> list[dict]:
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        rows = c.execute(
            "SELECT user_id, role, status, joined_at, invited_by, invited_at, removed_at "
            "FROM tenant_members WHERE tenant_id=? "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, joined_at",
            (tenant_id,)
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "account_id": r[0], "role": r[1], "status": r[2],
                "joined_at": r[3], "invited_by": r[4], "invited_at": r[5],
                "removed_at": r[6],
            })
        return out
    finally: c.close()


def get_seat_usage(tenant_id: str) -> dict:
    """Return {used, cap, tier} for the tenant."""
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        used = c.execute(
            "SELECT COUNT(*) FROM tenant_members WHERE tenant_id=? AND status='active'",
            (tenant_id,)
        ).fetchone()[0]
        # also count pending invites against cap (else races)
        pending = c.execute(
            "SELECT COUNT(*) FROM tenant_invitations WHERE tenant_id=? AND status='pending' "
            "AND expires_at > ?", (tenant_id, NOW())
        ).fetchone()[0]
    finally: c.close()
    tier = get_tier_for_tenant(tenant_id)
    return {"used": used, "pending": pending, "total": used + pending,
            "cap": get_seat_cap(tier), "tier": tier}


# ───────── list invites ─────────

def list_invites(tenant_id: str, status: str = "pending") -> list[dict]:
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        rows = c.execute(
            "SELECT id, invited_email, invited_by, invited_at, expires_at, role, status "
            "FROM tenant_invitations WHERE tenant_id=? AND status=? "
            "ORDER BY invited_at DESC", (tenant_id, status)
        ).fetchall()
        return [{"id": r[0], "email": r[1], "invited_by": r[2], "invited_at": r[3],
                 "expires_at": r[4], "role": r[5], "status": r[6]} for r in rows]
    finally: c.close()


# ───────── invite ─────────

def create_invite(tenant_id: str, inviter_account_id: str, email: str,
                  role: str = "member") -> dict:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "error": "invalid_email"}
    if role not in ("admin", "member", "viewer"):
        return {"ok": False, "error": "invalid_role"}

    if not is_admin(tenant_id, inviter_account_id):
        return {"ok": False, "error": "not_admin"}

    seats = get_seat_usage(tenant_id)
    if seats["total"] >= seats["cap"]:
        return {"ok": False, "error": "seat_cap_reached",
                "message": f"Your {seats['tier']} tier supports {seats['cap']} seats. "
                           f"Upgrade tier or remove a member before inviting more.",
                "seats": seats}

    # check if already a member (active)
    if _existing_active_member_by_email(tenant_id, email):
        return {"ok": False, "error": "already_member"}

    # check for outstanding invite
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        existing = c.execute(
            "SELECT id, invite_token FROM tenant_invitations "
            "WHERE tenant_id=? AND invited_email=? AND status='pending' AND expires_at > ?",
            (tenant_id, email, NOW())
        ).fetchone()
        if existing:
            return {"ok": True, "id": existing[0], "token": existing[1],
                    "message": "reused existing pending invite"}

        token = secrets.token_urlsafe(32)
        expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)).isoformat()
        cur = c.execute(
            "INSERT INTO tenant_invitations (tenant_id, invited_email, invited_by, "
            "invite_token, role, invited_at, expires_at) VALUES (?,?,?,?,?,?,?)",
            (tenant_id, email, inviter_account_id, token, role, NOW(), expires)
        )
        c.commit()
        invite_id = cur.lastrowid
    finally: c.close()

    # check if recipient already has a Murphy account (Flow B)
    try:
        from src import ship31ah_signup as auth
        existing_account = auth.get_user_by_email(email)
        flow = "B_existing_account" if existing_account else "A_new_account"
    except Exception:
        flow = "A_new_account"

    return {"ok": True, "id": invite_id, "token": token, "flow": flow,
            "expires_at": expires, "seats_after": seats["total"] + 1}


def _existing_active_member_by_email(tenant_id: str, email: str) -> bool:
    try:
        from src import ship31ah_signup as auth
        u = auth.get_user_by_email(email)
        if not u: return False
        return is_member(tenant_id, u["account_id"])
    except Exception:
        return False


# ───────── accept invite ─────────

def accept_invite(token: str, account_id: str) -> dict:
    """Account accepts invite. If account didn't exist, signup happens first
    and then this is called with the new account_id."""
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        r = c.execute(
            "SELECT id, tenant_id, invited_email, role, expires_at, status "
            "FROM tenant_invitations WHERE invite_token=?", (token,)
        ).fetchone()
        if not r:
            return {"ok": False, "error": "invalid_token"}
        invite_id, tenant_id, email, role, expires, status = r
        if status != "pending":
            return {"ok": False, "error": f"invite_{status}"}
        if expires < NOW():
            c.execute("UPDATE tenant_invitations SET status='expired' WHERE id=?", (invite_id,))
            c.commit()
            return {"ok": False, "error": "expired"}

        # check whether membership row already exists (re-invite of removed member)
        existing = c.execute(
            "SELECT user_id, status FROM tenant_members WHERE tenant_id=? AND user_id=?",
            (tenant_id, account_id)
        ).fetchone()

        if existing:
            # REACTIVATE (preserve audit thread, locked rule)
            c.execute(
                "UPDATE tenant_members SET status='active', role=?, removed_at=NULL, "
                "removed_by=NULL WHERE tenant_id=? AND user_id=?",
                (role, tenant_id, account_id)
            )
        else:
            c.execute(
                "INSERT INTO tenant_members (tenant_id, user_id, role, joined_at, "
                "invited_at, status) VALUES (?,?,?,?,?,?)",
                (tenant_id, account_id, role, NOW(), NOW(), "active")
            )

        c.execute(
            "UPDATE tenant_invitations SET status='accepted', accepted_at=?, "
            "accepted_by_account_id=? WHERE id=?",
            (NOW(), account_id, invite_id)
        )
        c.commit()
        return {"ok": True, "tenant_id": tenant_id, "role": role, "reactivated": bool(existing)}
    finally: c.close()


# ───────── remove member ─────────

def remove_member(tenant_id: str, target_account_id: str, by_account_id: str) -> dict:
    if not is_admin(tenant_id, by_account_id):
        return {"ok": False, "error": "not_admin"}
    if target_account_id == by_account_id:
        return {"ok": False, "error": "cannot_remove_self",
                "message": "Transfer admin to another member first."}

    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        r = c.execute(
            "SELECT role, status FROM tenant_members WHERE tenant_id=? AND user_id=?",
            (tenant_id, target_account_id)
        ).fetchone()
        if not r: return {"ok": False, "error": "not_a_member"}
        if r[1] != "active": return {"ok": False, "error": f"member_{r[1]}"}
        if r[0] == "owner":
            return {"ok": False, "error": "cannot_remove_owner",
                    "message": "Tenant owners cannot be removed."}
        c.execute(
            "UPDATE tenant_members SET status='removed', removed_at=?, removed_by=? "
            "WHERE tenant_id=? AND user_id=?",
            (NOW(), by_account_id, tenant_id, target_account_id)
        )
        c.commit()
    finally: c.close()

    # revoke any active sessions for this user scoped to this tenant
    try:
        from src import ship31ah_signup as auth
        # if session_store exists in auth, revoke; else skip silently
        if hasattr(auth, "revoke_sessions_for_account_in_tenant"):
            auth.revoke_sessions_for_account_in_tenant(target_account_id, tenant_id)
    except Exception as e:
        logger.warning(f"session revoke failed: {e}")

    return {"ok": True, "removed_account_id": target_account_id,
            "audit_preserved": True}


def revoke_invite(tenant_id: str, invite_id: int, by_account_id: str) -> dict:
    if not is_admin(tenant_id, by_account_id):
        return {"ok": False, "error": "not_admin"}
    c = sqlite3.connect(TENANTS_DB, timeout=8.0)
    try:
        r = c.execute(
            "SELECT status FROM tenant_invitations WHERE id=? AND tenant_id=?",
            (invite_id, tenant_id)
        ).fetchone()
        if not r: return {"ok": False, "error": "not_found"}
        if r[0] != "pending": return {"ok": False, "error": f"invite_{r[0]}"}
        c.execute(
            "UPDATE tenant_invitations SET status='revoked', revoked_at=?, revoked_by=? "
            "WHERE id=?", (NOW(), by_account_id, invite_id)
        )
        c.commit()
        return {"ok": True}
    finally: c.close()
