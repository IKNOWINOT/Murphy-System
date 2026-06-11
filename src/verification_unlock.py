"""
Ship 31v — Email verification → launch_allowlist unlock.

Contract:
  - Every stranger reply attaches a verify link in the compliance footer
  - The link encodes a token bound to (email, domain, expiry)
  - One click adds the domain to launch_allowlist (active)
  - From that moment, all future replies from that domain go LIVE
  - Tokens expire in 14 days, single-use
  - All claims logged with IP + UA for audit

Surface:
  - issue_verification_token(email) -> URL string
  - claim_verification_token(token, ip, ua) -> result dict
  - FastAPI route /verify/{token} -> renders confirmation page

Privacy:
  - Tokens are cryptographically random (32 bytes urlsafe -> 43 chars)
  - Not signed JWTs — DB-backed lookup keeps revocation easy
  - Storing minimal claim metadata (IP/UA) for fraud audit only
"""
import sqlite3
import secrets
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

DB = "/var/lib/murphy-production/entity_graph.db"
BASE_URL = "https://murphy.systems"
TOKEN_TTL_DAYS = 14
logger = logging.getLogger("verification_unlock")


def _domain_of(email: str) -> str:
    return (email or "").split("@")[-1].strip().lower()


def issue_verification_token(email: str) -> str:
    """Generate + persist a verification token. Returns the full verify URL.

    Reuses an active unexpired token for the same email if one exists
    (so multiple emails to the same person don't issue 5 different links).
    """
    if not email or "@" not in email:
        return ""
    email = email.strip().lower()
    domain = _domain_of(email)
    now = datetime.now(timezone.utc)

    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        # Reuse existing unexpired pending token
        existing = c.execute("""SELECT token, expires_ts FROM verification_tokens
            WHERE email=? AND status='pending' AND expires_ts > ?
            ORDER BY issued_ts DESC LIMIT 1""",
            (email, now.isoformat())).fetchone()
        if existing:
            c.close()
            return f"{BASE_URL}/verify/{existing['token']}"

        token = secrets.token_urlsafe(32)
        expires = now + timedelta(days=TOKEN_TTL_DAYS)
        c.execute("""INSERT INTO verification_tokens
            (token, email, domain, issued_ts, expires_ts, status)
            VALUES (?,?,?,?,?,'pending')""",
            (token, email, domain, now.isoformat(), expires.isoformat()))
        c.commit()
        c.close()
        return f"{BASE_URL}/verify/{token}"
    except Exception as exc:
        logger.warning("issue_verification_token failed for %s: %s", email, exc)
        return ""


def claim_verification_token(token: str, ip: str = "", ua: str = "") -> dict:
    """Validate token and unlock the domain.

    Returns:
      {"ok": True, "domain": ..., "email": ..., "first_claim": bool}
      or {"ok": False, "reason": "expired"|"not_found"|"already_claimed"|"error"}
    """
    if not token or len(token) < 20:
        return {"ok": False, "reason": "not_found"}

    now = datetime.now(timezone.utc)
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        row = c.execute(
            "SELECT * FROM verification_tokens WHERE token=?",
            (token,)
        ).fetchone()

        if not row:
            c.close()
            return {"ok": False, "reason": "not_found"}

        if row["status"] == "claimed":
            c.close()
            return {
                "ok": True, "domain": row["domain"], "email": row["email"],
                "first_claim": False, "claimed_at": row["claimed_ts"],
            }

        if row["expires_ts"] < now.isoformat():
            c.execute("UPDATE verification_tokens SET status='expired' WHERE token=?",
                      (token,))
            c.commit(); c.close()
            return {"ok": False, "reason": "expired"}

        # Mark claimed
        c.execute("""UPDATE verification_tokens
            SET status='claimed', claimed_ts=?, claimed_ip=?, claimed_ua=?
            WHERE token=?""",
            (now.isoformat(), ip[:64], ua[:200], token))

        # Add domain to launch_allowlist if not present
        existing_allow = c.execute(
            "SELECT id, status FROM launch_allowlist WHERE domain=?",
            (row["domain"],)
        ).fetchone()
        if existing_allow:
            if existing_allow["status"] != "active":
                c.execute(
                    "UPDATE launch_allowlist SET status='active' WHERE domain=?",
                    (row["domain"],)
                )
        else:
            c.execute("""INSERT INTO launch_allowlist
                (domain, org_name, contact_name, notes, added_ts, added_by, status,
                 first_inbound_ts)
                VALUES (?,?,?,?,?,?,?,?)""",
                (row["domain"], row["domain"], row["email"],
                 f"Self-claimed via email verification (token issued {row['issued_ts'][:10]})",
                 now.isoformat(), "self_claim", "active", row["issued_ts"]))

        c.commit()
        c.close()
        return {
            "ok": True, "domain": row["domain"], "email": row["email"],
            "first_claim": True,
        }
    except Exception as exc:
        logger.warning("claim_verification_token failed: %s", exc)
        return {"ok": False, "reason": "error", "detail": str(exc)}


def render_verification_page(result: dict) -> str:
    """Render the HTML confirmation page shown after the user clicks."""
    style = """<style>
body{background:#0d1117;color:#c9d1d9;font:14px -apple-system,BlinkMacSystemFont,sans-serif;
     margin:0;padding:0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:32px;
      max-width:480px;margin:24px}
.logo{width:48px;height:48px;background:#58a6ff;border-radius:8px;
      display:flex;align-items:center;justify-content:center;
      font-weight:700;color:#0d1117;font-size:24px;margin-bottom:16px}
h1{color:#c9d1d9;margin:0 0 8px 0;font-size:22px}
.sub{color:#8b949e;margin:0 0 24px 0;font-size:14px}
.ok{background:#1f6feb22;border:1px solid #1f6feb55;color:#79c0ff;
    padding:12px;border-radius:6px;margin-bottom:16px}
.err{background:#f8514922;border:1px solid #f8514955;color:#ffa198;
    padding:12px;border-radius:6px;margin-bottom:16px}
.detail{color:#8b949e;font-size:13px;line-height:1.5}
strong{color:#c9d1d9}
.cta{display:inline-block;background:#58a6ff;color:#0d1117;
     padding:10px 20px;border-radius:6px;text-decoration:none;
     font-weight:600;margin-top:16px}
</style>"""

    if not result.get("ok"):
        reason = result.get("reason", "unknown")
        msgs = {
            "not_found": "This verification link isn't valid. It may have been mistyped or already used by someone else.",
            "expired":   "This verification link has expired (14-day limit). Reply to any Murphy email to get a fresh one.",
            "error":     "Something went wrong on our end. Please try again or email cpost@murphy.systems for help.",
        }
        body = f"""<div class="card">
<div class="logo">M</div>
<h1>Couldn't verify</h1>
<div class="err">⚠ {msgs.get(reason, 'Unknown error: ' + reason)}</div>
<div class="detail">If you keep getting this, reply to the original Murphy email and we'll sort it out.</div>
</div>"""
    else:
        first = result.get("first_claim", False)
        verb = "Just unlocked" if first else "Already verified"
        body = f"""<div class="card">
<div class="logo">M</div>
<h1>{verb}: <strong>{result['domain']}</strong></h1>
<div class="ok">✓ Future Murphy replies to your team will go live (not shadow). Your domain is now on the allowlist.</div>
<div class="detail">
<p><strong>What this means:</strong></p>
<p>When anyone at <strong>{result['domain']}</strong> emails Murphy, you get a real,
actionable reply within minutes — not a copy that we review first.</p>
<p>You can still unsubscribe any time by replying STOP to a Murphy email.</p>
<p style="margin-top:24px"><strong>Try it now:</strong> send any work question to
<a href="mailto:murphy@murphy.systems" style="color:#58a6ff">murphy@murphy.systems</a>
and you'll get a live, role-tailored reply.</p>
</div>
<a href="https://murphy.systems" class="cta">murphy.systems</a>
</div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Murphy — Verify</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
{style}
</head><body>{body}</body></html>"""


def verify_link_for_email(email: str) -> str:
    """Convenience wrapper used by the compliance footer / outbound builder."""
    return issue_verification_token(email)


def get_verification_stats():
    """For the founder dashboard."""
    try:
        c = sqlite3.connect(DB)
        c.row_factory = sqlite3.Row
        total = c.execute("SELECT COUNT(*) FROM verification_tokens").fetchone()[0]
        claimed = c.execute(
            "SELECT COUNT(*) FROM verification_tokens WHERE status='claimed'"
        ).fetchone()[0]
        expired = c.execute(
            "SELECT COUNT(*) FROM verification_tokens WHERE status='expired'"
        ).fetchone()[0]
        recent = c.execute("""SELECT email, domain, status, issued_ts, claimed_ts
            FROM verification_tokens ORDER BY issued_ts DESC LIMIT 20""").fetchall()
        c.close()
        return {
            "total_issued": total,
            "total_claimed": claimed,
            "total_expired": expired,
            "claim_rate": (claimed / total) if total else 0,
            "recent": [dict(r) for r in recent],
        }
    except Exception:
        return {"total_issued": 0, "total_claimed": 0, "total_expired": 0,
                "claim_rate": 0, "recent": []}
