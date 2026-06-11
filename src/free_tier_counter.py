"""
Ship 31ab — Free tier counter + signup CTA.

Tracks how many auto-replies each stranger email address has received
this month. Surfaces the counter in outbound replies so recipients see
their remaining quota and a one-click claim link to upgrade.

Model:
  - 5 free replies per email address per calendar month
  - Counter resets at 00:00 UTC on the 1st of each month
  - Once an account is claimed (account_claimed=1), counter is bypassed
  - On the last free reply, a stronger "claim now" CTA is shown
  - One reply past the cap, we still reply ONCE with claim-required text,
    then go silent until they claim or the month resets
"""
import sqlite3, datetime, secrets
from pathlib import Path
from typing import Tuple

DB_PATH = "/var/lib/murphy-production/entity_graph.db"
FREE_LIMIT = 5
TABLE_NAME = "free_tier_usage"

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_schema():
    with _conn() as c:
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                email_addr        TEXT PRIMARY KEY,
                replies_used      INTEGER NOT NULL DEFAULT 0,
                period_start      TEXT NOT NULL,
                first_seen        TEXT NOT NULL,
                last_reply        TEXT,
                account_claimed   INTEGER NOT NULL DEFAULT 0,
                claim_token       TEXT,
                claim_token_expires TEXT
            )
        """)
        c.execute(f"CREATE INDEX IF NOT EXISTS idx_ft_period ON {TABLE_NAME}(period_start)")
        c.execute(f"CREATE INDEX IF NOT EXISTS idx_ft_claimed ON {TABLE_NAME}(account_claimed)")

def _period_start_iso() -> str:
    n = datetime.datetime.now(datetime.UTC)
    return n.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

def increment_and_get(email_addr: str) -> Tuple[int, int, int]:
    """Increment counter for email_addr. Return (used, limit, remaining).
    If account already claimed, returns (0, FREE_LIMIT, 999) — unlimited."""
    init_schema()
    email_addr = (email_addr or "").lower().strip()
    if not email_addr:
        return (0, FREE_LIMIT, FREE_LIMIT)

    now = datetime.datetime.now(datetime.UTC).isoformat()
    period = _period_start_iso()

    with _conn() as c:
        row = c.execute(
            f"SELECT replies_used, period_start, account_claimed FROM {TABLE_NAME} WHERE email_addr=?",
            (email_addr,),
        ).fetchone()
        if row is None:
            c.execute(
                f"""INSERT INTO {TABLE_NAME}
                    (email_addr, replies_used, period_start, first_seen, last_reply)
                    VALUES (?, 1, ?, ?, ?)""",
                (email_addr, period, now, now),
            )
            return (1, FREE_LIMIT, FREE_LIMIT - 1)
        if row["account_claimed"]:
            c.execute(
                f"UPDATE {TABLE_NAME} SET replies_used=replies_used+1, last_reply=? WHERE email_addr=?",
                (now, email_addr),
            )
            return (0, FREE_LIMIT, 999)
        # if period rolled over, reset
        if row["period_start"] != period:
            c.execute(
                f"UPDATE {TABLE_NAME} SET replies_used=1, period_start=?, last_reply=? WHERE email_addr=?",
                (period, now, email_addr),
            )
            return (1, FREE_LIMIT, FREE_LIMIT - 1)
        new_used = row["replies_used"] + 1
        c.execute(
            f"UPDATE {TABLE_NAME} SET replies_used=?, last_reply=? WHERE email_addr=?",
            (new_used, now, email_addr),
        )
        remaining = max(0, FREE_LIMIT - new_used)
        return (new_used, FREE_LIMIT, remaining)

def is_over_limit(email_addr: str) -> bool:
    init_schema()
    email_addr = (email_addr or "").lower().strip()
    if not email_addr:
        return False
    with _conn() as c:
        row = c.execute(
            f"SELECT replies_used, period_start, account_claimed FROM {TABLE_NAME} WHERE email_addr=?",
            (email_addr,),
        ).fetchone()
        if row is None or row["account_claimed"]:
            return False
        if row["period_start"] != _period_start_iso():
            return False
        return row["replies_used"] >= FREE_LIMIT

def get_or_create_claim_token(email_addr: str) -> str:
    """Issue a one-time claim token. Reuses existing unexpired token."""
    init_schema()
    email_addr = (email_addr or "").lower().strip()
    now = datetime.datetime.now(datetime.UTC)
    expires = (now + datetime.timedelta(days=30)).isoformat()
    with _conn() as c:
        row = c.execute(
            f"SELECT claim_token, claim_token_expires FROM {TABLE_NAME} WHERE email_addr=?",
            (email_addr,),
        ).fetchone()
        if row and row["claim_token"] and row["claim_token_expires"]:
            if row["claim_token_expires"] > now.isoformat():
                return row["claim_token"]
        token = secrets.token_urlsafe(24).lower()  # cloudflare may lowercase the URL
        c.execute(
            f"""INSERT INTO {TABLE_NAME} (email_addr, replies_used, period_start, first_seen,
                                          claim_token, claim_token_expires)
                VALUES (?, 0, ?, ?, ?, ?)
                ON CONFLICT(email_addr) DO UPDATE SET
                  claim_token=excluded.claim_token,
                  claim_token_expires=excluded.claim_token_expires""",
            (email_addr, _period_start_iso(), now.isoformat(), token, expires),
        )
        return token

def claim_account(token: str) -> str | None:
    """Activate account by token. Case-insensitive (Cloudflare may lowercase
    the URL path). Returns email_addr on success, None otherwise."""
    init_schema()
    now = datetime.datetime.now(datetime.UTC).isoformat()
    with _conn() as c:
        # Try exact match first, then case-insensitive
        row = c.execute(
            f"SELECT email_addr, claim_token_expires FROM {TABLE_NAME} WHERE claim_token=?",
            (token,),
        ).fetchone()
        if row is None:
            row = c.execute(
                f"SELECT email_addr, claim_token_expires FROM {TABLE_NAME} "
                f"WHERE LOWER(claim_token)=LOWER(?)",
                (token,),
            ).fetchone()
        if not row or (row["claim_token_expires"] or "") < now:
            return None
        c.execute(
            f"UPDATE {TABLE_NAME} SET account_claimed=1, claim_token=NULL, claim_token_expires=NULL WHERE email_addr=?",
            (row["email_addr"],),
        )
        return row["email_addr"]

def get_state(email_addr: str) -> dict:
    """Snapshot for the brand template renderer."""
    init_schema()
    email_addr = (email_addr or "").lower().strip()
    with _conn() as c:
        row = c.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE email_addr=?", (email_addr,)
        ).fetchone()
    if not row:
        return {"used": 0, "limit": FREE_LIMIT, "remaining": FREE_LIMIT,
                "claimed": False, "is_last": False, "is_over": False}
    if row["account_claimed"]:
        return {"used": 0, "limit": FREE_LIMIT, "remaining": 999,
                "claimed": True, "is_last": False, "is_over": False}
    used = row["replies_used"] if row["period_start"] == _period_start_iso() else 0
    remaining = max(0, FREE_LIMIT - used)
    return {"used": used, "limit": FREE_LIMIT, "remaining": remaining,
            "claimed": False, "is_last": remaining == 1, "is_over": remaining == 0}
