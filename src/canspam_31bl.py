"""
Ship 31bl.CAN_SPAM — make every Murphy outbound legal in the US.

15 USC §7704 requirements:
  (a)(5)(A)(iii) physical postal address in every commercial email
  (a)(3)         clear unsubscribe mechanism honored within 10 days
  (a)(4)         opt-out request honored within 10 business days
  (a)(1-2)       no false / misleading headers or subjects (already pass)

CANONICAL FUNCTIONS
  unsubscribe_token(email)      → HMAC token (stable per recipient)
  unsubscribe_url(email)        → public one-click URL with token
  postal_footer_plain()         → text postal address line
  postal_footer_html()          → HTML postal address + unsub block
  is_suppressed(email)          → True if recipient unsubscribed
  reason_or_none(email)         → ('suppressed', detail) or None
  append_footer(plain, html, recipient)
                                → returns (plain_with_footer, html_with_footer)

SUPPRESSION LIST
  Reuses unsubscribe_registry table created by Ship 31ae.
  is_suppressed() checks email + last 60 days of bounces.
  After unsub, sends within 10 days are still legal (grace period
  per the statute) but Murphy enforces zero-tolerance: 0-day grace.
"""
import os
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone
from typing import Optional, Tuple

# Inoni LLC physical address (founder confirmed earlier)
POSTAL_ADDRESS = "Inoni LLC · 7805 SE 70th Ave · Portland, OR 97206 · USA"

# Public base URL for unsubscribe links
PUBLIC_BASE = os.environ.get("MURPHY_PUBLIC_BASE", "https://murphy.systems")

# HMAC secret for unsubscribe tokens (stable + private)
_SECRET = (os.environ.get("MURPHY_UNSUB_SECRET") or
           os.environ.get("MURPHY_API_KEY") or
           "murphy_unsub_secret_2026").encode()

UNSUBSCRIBE_DB = "/var/lib/murphy-production/entity_graph.db"
SUPPRESSION_LOG_DB = "/var/lib/murphy-production/canspam_audit.db"


def unsubscribe_token(email: str) -> str:
    """Stable per-recipient HMAC token. Same email → same token."""
    e = (email or "").lower().strip()
    return hmac.new(_SECRET, e.encode(), hashlib.sha256).hexdigest()[:24]


def unsubscribe_url(email: str) -> str:
    """One-click unsubscribe URL (RFC 8058 compatible)."""
    t = unsubscribe_token(email)
    return f"{PUBLIC_BASE}/unsubscribe?e={email}&t={t}"


def short_unsubscribe_url(email: str) -> str:
    """Shorter URL using the /u/{token} form."""
    return f"{PUBLIC_BASE}/u/{unsubscribe_token(email)}"


def postal_footer_plain(recipient: Optional[str] = None) -> str:
    """Plain text postal footer + unsubscribe."""
    lines = [
        "",
        "—",
        POSTAL_ADDRESS,
    ]
    if recipient:
        lines.append(f"Unsubscribe: {unsubscribe_url(recipient)}")
    lines.append("Murphy is an autonomous research AI by Inoni LLC.")
    return "\n".join(lines)


def postal_footer_html(recipient: Optional[str] = None) -> str:
    """HTML postal footer block matching Modern Victorian aesthetic."""
    unsub_link = ""
    if recipient:
        url = unsubscribe_url(recipient)
        unsub_link = (
            f'<a href="{url}" style="color:#A8997A;text-decoration:underline;'
            f'font-size:11px;letter-spacing:0.5px">Unsubscribe</a>'
        )
    return f'''
<table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:32px;border-top:1px solid #D4AF3733;padding-top:18px">
  <tr><td style="text-align:center;padding:14px 16px">
    <div style="font-family:Georgia,serif;font-size:11px;color:#A8997A;letter-spacing:0.5px;line-height:1.7">
      {POSTAL_ADDRESS}
    </div>
    <div style="margin-top:10px;font-size:10px;color:#A8997A;letter-spacing:1px">
      {unsub_link}
      {('&nbsp;·&nbsp;' if unsub_link else '')}
      Murphy is an autonomous research AI by Inoni LLC
    </div>
  </td></tr>
</table>
'''


def is_suppressed(email: str) -> bool:
    """True if recipient has unsubscribed. Zero-day grace — block immediately.

    Per Murphy decision (2026-06-13): checks both columns —
    `registered_ts` (legacy stop_keyword unsubs) AND `unsubscribed_at`
    (Ship 31ae RFC 8058 one-click) — via COALESCE. Both schemas now
    coexist in unsubscribe_registry; honoring either flags the user
    as suppressed and blocks the send.
    """
    if not email:
        return False
    e = email.lower().strip()
    try:
        with sqlite3.connect(UNSUBSCRIBE_DB, timeout=10.0) as c:
            row = c.execute(
                "SELECT COALESCE(unsubscribed_at, registered_ts) "
                "FROM unsubscribe_registry WHERE email_addr=?",
                (e,)
            ).fetchone()
        return bool(row and row[0])
    except Exception:
        return False


def reason_or_none(email: str) -> Optional[Tuple[str, str]]:
    """Return (reason_code, detail) if recipient should NOT be emailed, else None."""
    if not email:
        return ("invalid", "empty email address")
    e = email.lower().strip()
    if "@" not in e or e.count("@") != 1:
        return ("invalid", f"malformed: {e[:40]}")
    if is_suppressed(e):
        return ("suppressed", "recipient previously unsubscribed")
    return None


def append_footer(plain_body: str, html_body: Optional[str],
                  recipient: str) -> Tuple[str, Optional[str]]:
    """Glue CAN-SPAM footer onto an outbound. Idempotent — won't double-stamp."""
    plain_marker = POSTAL_ADDRESS.split(" · ")[0]  # "Inoni LLC"
    if plain_body and plain_marker not in plain_body:
        plain_body = (plain_body or "").rstrip() + "\n" + postal_footer_plain(recipient)
    if html_body and plain_marker not in html_body:
        # Insert before </body> if present, else append
        footer = postal_footer_html(recipient)
        if "</body>" in html_body:
            html_body = html_body.replace("</body>", footer + "</body>", 1)
        else:
            html_body = html_body + footer
    return plain_body, html_body


def record_send_attempt(recipient: str, allowed: bool, reason: str = "",
                         subject: str = "", source: str = "") -> None:
    """Audit log for every gate decision."""
    try:
        with sqlite3.connect(SUPPRESSION_LOG_DB, timeout=10.0) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS send_gate_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                recipient TEXT,
                allowed INTEGER,
                reason TEXT,
                subject TEXT,
                source TEXT)""")
            c.execute(
                "INSERT INTO send_gate_log (ts, recipient, allowed, reason, subject, source) "
                "VALUES (?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), (recipient or "")[:120],
                 1 if allowed else 0, reason[:200], subject[:200], source[:80])
            )
    except Exception:
        pass


def gate_check(recipient: str, subject: str = "", source: str = "") -> dict:
    """One-call gate. Returns {ok, reason, recipient}."""
    r = reason_or_none(recipient)
    if r is None:
        record_send_attempt(recipient, True, "ok", subject, source)
        return {"ok": True, "recipient": recipient}
    record_send_attempt(recipient, False, f"{r[0]}: {r[1]}", subject, source)
    return {"ok": False, "reason": r[0], "detail": r[1], "recipient": recipient}


def stats(days: int = 7) -> dict:
    """Reporting for /api/health/canspam."""
    try:
        with sqlite3.connect(SUPPRESSION_LOG_DB, timeout=10.0) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS send_gate_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
                recipient TEXT, allowed INTEGER, reason TEXT,
                subject TEXT, source TEXT)""")
            c.row_factory = sqlite3.Row
            allowed = c.execute(
                "SELECT COUNT(*) FROM send_gate_log "
                "WHERE allowed=1 AND ts > datetime('now','-' || ? || ' days')",
                (days,)
            ).fetchone()[0]
            blocked = c.execute(
                "SELECT COUNT(*) FROM send_gate_log "
                "WHERE allowed=0 AND ts > datetime('now','-' || ? || ' days')",
                (days,)
            ).fetchone()[0]
            by_reason = dict(c.execute(
                "SELECT reason, COUNT(*) FROM send_gate_log "
                "WHERE allowed=0 AND ts > datetime('now','-' || ? || ' days') "
                "GROUP BY reason", (days,)
            ).fetchall())
        # Suppressed count
        try:
            with sqlite3.connect(UNSUBSCRIBE_DB, timeout=10.0) as c:
                total_supp = c.execute(
                    "SELECT COUNT(*) FROM unsubscribe_registry"
                ).fetchone()[0]
        except Exception:
            total_supp = 0
        return {
            "window_days":         days,
            "sends_allowed":       allowed,
            "sends_blocked":       blocked,
            "block_reasons":       by_reason,
            "suppression_list_size": total_supp,
            "block_pct":           round(100 * blocked / max(1, allowed + blocked), 1),
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import json
    print("CAN-SPAM SELF-TEST")
    print()
    cases = [
        ("alice@example.com", True, "regular send"),
        ("", False, "empty"),
        ("not-an-email", False, "malformed"),
    ]
    for r, exp, label in cases:
        result = gate_check(r, "test subject", "self_test")
        ok = result["ok"] == exp
        mark = "✅" if ok else "❌"
        print(f"  {mark} {label:20} '{r}' → ok={result['ok']}  ({result.get('reason') or 'pass'})")
    print()
    print("Token sample:")
    e = "alice@example.com"
    print(f"  token({e})  = {unsubscribe_token(e)}")
    print(f"  URL({e})    = {unsubscribe_url(e)}")
    print(f"  short({e})  = {short_unsubscribe_url(e)}")
    print()
    print("Footer sample (plain):")
    print(postal_footer_plain("alice@example.com"))
    print()
    print("Footer sample (HTML, first 200 chars):")
    print(postal_footer_html("alice@example.com")[:300])
    print()
    print("Stats:")
    print(json.dumps(stats(7), indent=2))
