"""
PATCH-175: Customer persistence layer.
Stores subscription records in SQLite so they survive restarts.
DB: /var/lib/murphy-production/customers.db
"""
import sqlite3
import json
import os
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("MURPHY_CUSTOMERS_DB", "/var/lib/murphy-production/customers.db")

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    with _lock:
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                account_id      TEXT PRIMARY KEY,
                email           TEXT,
                full_name       TEXT,
                stripe_customer_id TEXT,
                tier            TEXT NOT NULL DEFAULT 'free',
                status          TEXT NOT NULL DEFAULT 'active',
                interval        TEXT DEFAULT 'monthly',
                stripe_subscription_id TEXT,
                trial_ends      TEXT,
                current_period_end TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                meta            TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS billing_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id      TEXT,
                event_type      TEXT,
                provider        TEXT DEFAULT 'stripe',
                stripe_event_id TEXT,
                payload         TEXT,
                created_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
            CREATE INDEX IF NOT EXISTS idx_customers_tier  ON customers(tier);
            CREATE INDEX IF NOT EXISTS idx_billing_account ON billing_events(account_id);
        """)
        conn.commit()
        conn.close()
    logger.info("PATCH-175: customers.db initialised at %s", DB_PATH)


def upsert_customer(
    account_id: str,
    tier: str,
    status: str = "active",
    email: str = "",
    full_name: str = "",
    stripe_customer_id: str = "",
    stripe_subscription_id: str = "",
    interval: str = "monthly",
    trial_ends: str = "",
    current_period_end: str = "",
    meta: Optional[Dict] = None,
) -> None:
    """Insert or update a customer record."""
    now = datetime.now(timezone.utc).isoformat()
    meta_str = json.dumps(meta or {})
    with _lock:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO customers
                (account_id, email, full_name, stripe_customer_id, tier, status,
                 interval, stripe_subscription_id, trial_ends, current_period_end,
                 created_at, updated_at, meta)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(account_id) DO UPDATE SET
                email                  = COALESCE(NULLIF(excluded.email,''), customers.email),
                full_name              = COALESCE(NULLIF(excluded.full_name,''), customers.full_name),
                stripe_customer_id     = COALESCE(NULLIF(excluded.stripe_customer_id,''), customers.stripe_customer_id),
                tier                   = excluded.tier,
                status                 = excluded.status,
                interval               = excluded.interval,
                stripe_subscription_id = COALESCE(NULLIF(excluded.stripe_subscription_id,''), customers.stripe_subscription_id),
                trial_ends             = COALESCE(NULLIF(excluded.trial_ends,''), customers.trial_ends),
                current_period_end     = COALESCE(NULLIF(excluded.current_period_end,''), customers.current_period_end),
                updated_at             = excluded.updated_at,
                meta                   = excluded.meta
        """, (account_id, email, full_name, stripe_customer_id, tier, status,
              interval, stripe_subscription_id, trial_ends, current_period_end,
              now, now, meta_str))
        conn.commit()
        conn.close()


def log_event(account_id: str, event_type: str, stripe_event_id: str = "", payload: Any = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO billing_events (account_id, event_type, stripe_event_id, payload, created_at) VALUES (?,?,?,?,?)",
            (account_id, event_type, stripe_event_id, json.dumps(payload or {}), now)
        )
        conn.commit()
        conn.close()


def get_customer(account_id: str) -> Optional[Dict]:
    with _lock:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM customers WHERE account_id=?", (account_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


def list_customers(
    tier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict]:
    query = "SELECT * FROM customers WHERE 1=1"
    params: list = []
    if tier:
        query += " AND tier=?"; params.append(tier)
    if status:
        query += " AND status=?"; params.append(status)
    query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _lock:
        conn = _get_conn()
        rows = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        conn.close()
    return {"customers": [dict(r) for r in rows], "total": total}


def customer_stats() -> Dict:
    with _lock:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        by_tier = {r[0]: r[1] for r in conn.execute(
            "SELECT tier, COUNT(*) FROM customers GROUP BY tier").fetchall()}
        by_status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM customers GROUP BY status").fetchall()}
        active = conn.execute("SELECT COUNT(*) FROM customers WHERE status='active'").fetchone()[0]
        # MRR estimate
        tier_prices = {"solo": 49, "professional": 99, "business": 299}
        mrr = sum(
            tier_prices.get(t, 0) * cnt
            for t, cnt in by_tier.items()
            if by_tier.get(t, 0) > 0
        )
        conn.close()
    return {
        "total_customers": total,
        "active": active,
        "by_tier": by_tier,
        "by_status": by_status,
        "estimated_mrr_usd": mrr,
    }
