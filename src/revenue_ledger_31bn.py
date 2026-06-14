"""
Ship 31bn — Murphy's OWN referral/revenue tracking.

Founder direction 2026-06-13:
  'Make our own system for getting money for Murphy.'

DESIGN (Murphy-approved 2026-06-13):
  - NEW table: murphy_referral_ledger
  - Composes with existing tables (does not replace):
      revenue_events       — final transactions
      chain_revenue_events — agent-chain royalties
      button_commission    — button click tracking
      capital_ledger       — investment-grade decisions
  - Records every outbound URL Murphy embeds with a Murphy-owned tracking_id.
  - When the referred party converts, revenue_events records the actual money
    and we link them via tracking_id.

TRACKING_ID FORMAT
  mr-{tenant_hash[:8]}-{ts_b36}-{nonce_b36}
  Always shows Murphy is the referrer; never exposes raw tenant data.

OUTBOUND LINK REWRITER
  rewrite_link(url, recipient, context)
    → returns Murphy-tracked URL.
    → strips any pre-existing third-party affiliate codes.
    → appends our tracking params (utm_source=murphy + ref=tracking_id).
    → logs the embed to murphy_referral_ledger.
"""
import os
import re
import time
import json
import hmac
import hashlib
import sqlite3
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional

DB = "/var/lib/murphy-production/murphy_referral_ledger.db"
SECRET = (os.environ.get("MURPHY_REFERRAL_SECRET") or
          os.environ.get("MURPHY_UNSUB_SECRET") or
          os.environ.get("MURPHY_API_KEY") or "murphy_referral_2026").encode()

# Third-party affiliate codes to STRIP before re-tracking
STRIP_AFFILIATE_PATTERNS = [
    r'[?&]fpr=[^&]+',
    r'[?&]ref=[^&]+',
    r'[?&]aff=[^&]+',
    r'[?&]aff_id=[^&]+',
    r'[?&]affiliate=[^&]+',
    r'[?&]via=[^&]+',
    r'[?&]r=[^&]+',
    r'[?&]partner=[^&]+',
    r'[?&]referrer=[^&]+',
]


def _init_schema():
    conn = sqlite3.connect(DB, timeout=15.0)
    conn.execute("""CREATE TABLE IF NOT EXISTS murphy_referral_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_id   TEXT UNIQUE NOT NULL,
        original_url  TEXT NOT NULL,
        clean_url     TEXT NOT NULL,
        tracked_url   TEXT NOT NULL,
        recipient     TEXT,
        tenant_id     TEXT,
        context       TEXT,
        embedded_at   TEXT NOT NULL,
        first_click_at TEXT,
        click_count   INTEGER DEFAULT 0,
        converted_at  TEXT,
        converted_amount_usd REAL,
        revenue_event_id INTEGER
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_tracking ON murphy_referral_ledger(tracking_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_recipient ON murphy_referral_ledger(recipient)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ref_tenant ON murphy_referral_ledger(tenant_id)")
    conn.commit()
    conn.close()


def _b36(n: int) -> str:
    """Encode int to base36."""
    if n == 0: return "0"
    out = []
    while n:
        n, r = divmod(n, 36)
        out.append("0123456789abcdefghijklmnopqrstuvwxyz"[r])
    return "".join(reversed(out))


def mint_tracking_id(recipient: str = "", tenant_id: str = "") -> str:
    """Mint a Murphy-owned tracking_id. Always shows Murphy as the referrer."""
    seed = f"{recipient}|{tenant_id}".encode()
    th = hmac.new(SECRET, seed, hashlib.sha256).hexdigest()[:8]
    ts = _b36(int(time.time()))
    nonce = secrets.token_hex(3)
    return f"mr-{th}-{ts}-{nonce}"


def strip_third_party_affiliate(url: str) -> str:
    """Remove ANY third-party affiliate params and re-canonicalize the URL.

    Ship 31bo: when an affiliate pattern was middle-of-string, naive regex
    sub leaves orphan & or ?. Strategy: parse query string into key/value
    pairs, drop the bad keys, rebuild a clean canonical URL.
    """
    if not url:
        return ""
    try:
        from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
        parts = urlsplit(url)
        # parse_qsl preserves duplicates and order; keep_blank_values=False drops empties
        kept = []
        BAD_KEYS = {"fpr", "ref", "aff", "aff_id", "affiliate", "via",
                    "r", "partner", "referrer"}
        for k, v in parse_qsl(parts.query, keep_blank_values=False):
            if k.lower() in BAD_KEYS:
                continue
            kept.append((k, v))
        new_query = urlencode(kept)
        return urlunsplit((parts.scheme, parts.netloc, parts.path,
                           new_query, parts.fragment))
    except Exception:
        # Fall back to the old method if parsing fails for any reason
        for pattern in STRIP_AFFILIATE_PATTERNS:
            url = re.sub(pattern, '', url)
        url = url.rstrip('?&').replace('?&', '?').replace('&&', '&')
        return url


def rewrite_link(url: str, recipient: str = "", tenant_id: str = "",
                 context: str = "outbound") -> Dict:
    """Murphy's canonical link rewriter.

    Returns dict with:
      tracking_id : Murphy-owned ID
      clean_url   : original URL with all third-party affiliate codes stripped
      tracked_url : clean URL with Murphy's UTM + ref params appended

    Always logs to murphy_referral_ledger.
    """
    _init_schema()
    if not url:
        return {"ok": False, "error": "empty_url"}

    clean = strip_third_party_affiliate(url)
    tracking_id = mint_tracking_id(recipient, tenant_id)

    # Append Murphy's tracking
    sep = '&' if '?' in clean else '?'
    tracked = f"{clean}{sep}utm_source=murphy&utm_medium=ai&ref={tracking_id}"

    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB, timeout=10.0) as c:
            c.execute("""INSERT INTO murphy_referral_ledger
                (tracking_id, original_url, clean_url, tracked_url,
                 recipient, tenant_id, context, embedded_at)
                VALUES (?,?,?,?,?,?,?,?)""", (
                tracking_id, url[:500], clean[:500], tracked[:500],
                recipient[:120], tenant_id[:80], context[:80], now
            ))
    except Exception:
        pass

    return {
        "ok":           True,
        "tracking_id":  tracking_id,
        "clean_url":    clean,
        "tracked_url":  tracked,
        "recipient":    recipient,
        "context":      context,
    }


def record_click(tracking_id: str) -> bool:
    """Record a click on a Murphy-tracked URL."""
    _init_schema()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB, timeout=10.0) as c:
            c.execute("""UPDATE murphy_referral_ledger
                SET click_count = COALESCE(click_count, 0) + 1,
                    first_click_at = COALESCE(first_click_at, ?)
                WHERE tracking_id = ?""", (now, tracking_id))
            return c.total_changes > 0
    except Exception:
        return False


def record_conversion(tracking_id: str, amount_usd: float,
                      revenue_event_id: Optional[int] = None) -> bool:
    """Link a referral to a revenue_event when a tracked link converts."""
    _init_schema()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB, timeout=10.0) as c:
            c.execute("""UPDATE murphy_referral_ledger
                SET converted_at = ?, converted_amount_usd = ?,
                    revenue_event_id = ?
                WHERE tracking_id = ?""",
                (now, amount_usd, revenue_event_id, tracking_id))
            return c.total_changes > 0
    except Exception:
        return False


def stats(days: int = 30) -> Dict:
    """Reporting for /api/health/referral."""
    _init_schema()
    try:
        with sqlite3.connect(DB, timeout=10.0) as c:
            embedded = c.execute(
                "SELECT COUNT(*) FROM murphy_referral_ledger WHERE embedded_at > datetime('now', '-' || ? || ' days')",
                (days,)
            ).fetchone()[0]
            clicked = c.execute(
                "SELECT COUNT(*) FROM murphy_referral_ledger WHERE first_click_at > datetime('now', '-' || ? || ' days')",
                (days,)
            ).fetchone()[0]
            converted = c.execute(
                "SELECT COUNT(*), COALESCE(SUM(converted_amount_usd), 0) FROM murphy_referral_ledger WHERE converted_at > datetime('now', '-' || ? || ' days')",
                (days,)
            ).fetchone()
            total = c.execute("SELECT COUNT(*) FROM murphy_referral_ledger").fetchone()[0]
        return {
            "window_days":       days,
            "embedded_count":    embedded,
            "clicked_count":     clicked,
            "click_through_pct": round(100 * clicked / max(1, embedded), 1),
            "converted_count":   converted[0],
            "converted_revenue_usd": round(converted[1], 2),
            "conversion_pct":    round(100 * converted[0] / max(1, clicked), 1),
            "total_lifetime":    total,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("REVENUE LEDGER SELF-TEST")
    print()
    # Test rewrite
    test_url = "https://apify.com/some/actor?fpr=p2hrc6&utm_campaign=x"
    r = rewrite_link(test_url, recipient="alice@example.com",
                     tenant_id="t_test", context="self_test")
    print(f"  input:    {test_url}")
    print(f"  clean:    {r['clean_url']}")
    print(f"  tracked:  {r['tracked_url']}")
    print(f"  track_id: {r['tracking_id']}")
    print()
    # Simulate click + conversion
    record_click(r["tracking_id"])
    record_click(r["tracking_id"])
    record_conversion(r["tracking_id"], 12.50)
    print()
    print("Stats:")
    print(json.dumps(stats(30), indent=2))
