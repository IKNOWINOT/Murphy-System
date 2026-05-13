"""
src/runtime/auth.py
───────────────────
Persistent auth bridge for murphy_production_server.py.

Interface required by MPS (murphy_production_server.py):
  - _db()                   → sqlite3.Connection  (used by _persist_prod_account)
  - load_all_accounts()     → List[Dict]          (used by _load_prod_accounts_from_db)
  - register_account()      → Tuple[str|None, str|None]  (used by /api/auth/register-free)
  - create_session_token()  → str                 (used by /api/auth/register-free)
  - get_account_from_token() → str|None           (used by profile endpoints)

DB path: /opt/Murphy-System/data/murphy_users.db
  — lives on the Hetzner persistent volume, survives restarts.
  — Falls back to .murphy_persistence/murphy_users.db for local dev.

PATCH-274/275 — User data persistence across restarts.
"""
from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
import time
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── DB path — persistent across restarts ────────────────────────────────────
_PRIMARY_PATH   = "/opt/Murphy-System/data/murphy_users.db"
_FALLBACK_PATH  = os.path.join(
    os.getenv("MURPHY_PERSISTENCE_DIR", ".murphy_persistence"),
    "murphy_users.db",
)

def _resolve_db_path() -> str:
    """Return the first writable path."""
    primary_dir = os.path.dirname(_PRIMARY_PATH)
    if os.path.isdir(primary_dir) or _try_mkdir(primary_dir):
        return _PRIMARY_PATH
    fallback_dir = os.path.dirname(_FALLBACK_PATH)
    _try_mkdir(fallback_dir)
    return _FALLBACK_PATH

def _try_mkdir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False

_DB_PATH: str = _resolve_db_path()


# ── Connection factory ───────────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    """
    Open (and if needed create) the accounts DB.
    Returns an open sqlite3.Connection — caller must commit + close.
    """
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token         TEXT,
            tier          TEXT DEFAULT 'free',
            role          TEXT DEFAULT 'user',
            full_name     TEXT DEFAULT '',
            company       TEXT DEFAULT '',
            job_title     TEXT DEFAULT '',
            email_validated INTEGER DEFAULT 1,
            eula_accepted   INTEGER DEFAULT 1,
            created_at    TEXT,
            updated_at    TEXT
        )
    """)
    conn.commit()
    return conn


# ── Password helpers ─────────────────────────────────────────────────────────
def _hash(password: str) -> str:
    """PBKDF2-SHA256 — 600k iterations, random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000
    )
    return f"pbkdf2:{salt}:{dk.hex()}"


def _verify(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2:"):
            _, salt, expected = stored.split(":", 2)
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000
            )
            return dk.hex() == expected
        # bcrypt hashes (if migrated)
        if stored.startswith("$2"):
            try:
                import bcrypt  # type: ignore
                return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
            except ImportError:
                pass
    except Exception:
        pass
    return False


# ── Core API ─────────────────────────────────────────────────────────────────

def load_all_accounts() -> List[Dict]:
    """
    Return all accounts as dicts compatible with _prod_user_store.
    Called by _load_prod_accounts_from_db() at startup.
    """
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT id, email, password_hash, token, tier, role, "
            "full_name, company, job_title, email_validated, eula_accepted, created_at "
            "FROM accounts"
        ).fetchall()
        conn.close()
        accounts = []
        for row in rows:
            accounts.append({
                "account_id":      row["id"],
                "email":           row["email"],
                "password_hash":   row["password_hash"],
                "token":           row["token"] or "",
                "tier":            row["tier"] or "free",
                "role":            row["role"] or "user",
                "full_name":       row["full_name"] or "",
                "company":         row["company"] or "",
                "job_title":       row["job_title"] or "",
                "email_validated": bool(row["email_validated"]),
                "eula_accepted":   bool(row["eula_accepted"]),
                "created_at":      row["created_at"] or "",
            })
        log.info("auth.load_all_accounts: loaded %d accounts from %s", len(accounts), _DB_PATH)
        return accounts
    except Exception as exc:
        log.error("auth.load_all_accounts failed: %s", exc)
        return []


def register_account(
    email: str,
    password: str,
    tier: str = "free",
    role: str = "user",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a new account. Returns (account_id, session_token) or (None, None)
    if the email is already registered.
    """
    email = email.strip().lower()

    # Founder always gets owner/enterprise
    if email in ("cpost@murphy.systems", "hpost@murphy.systems"):
        role = "owner"
        tier = "enterprise"

    account_id = secrets.token_hex(12)
    token      = secrets.token_hex(32)
    now        = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        conn = _db()
        conn.execute(
            "INSERT INTO accounts "
            "(id, email, password_hash, token, tier, role, full_name, company, "
            "job_title, email_validated, eula_accepted, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,1,1,?,?)",
            (account_id, email, _hash(password), token, tier, role,
             "", "", "", now, now),
        )
        conn.commit()
        conn.close()
        log.info("auth.register_account: created %s (%s)", account_id, email)
        return account_id, token
    except sqlite3.IntegrityError:
        # Duplicate email
        return None, None
    except Exception as exc:
        log.error("auth.register_account failed: %s", exc)
        return None, None


def create_session_token(account_id: str) -> str:
    """Rotate session token for an existing account. Returns new token."""
    token = secrets.token_hex(32)
    try:
        conn = _db()
        conn.execute(
            "UPDATE accounts SET token=?, updated_at=? WHERE id=?",
            (token, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), account_id),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.warning("auth.create_session_token failed for %s: %s", account_id, exc)
    return token


def get_account_from_token(token: str) -> Optional[str]:
    """Return account_id for a valid session token, or None."""
    if not token:
        return None
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id FROM accounts WHERE token=?", (token,)
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except Exception as exc:
        log.warning("auth.get_account_from_token failed: %s", exc)
        return None


def save_account(account: Dict) -> bool:
    """
    Upsert a full account dict into the DB.
    Used by _persist_prod_account() in MPS via the _db() interface.
    Returns True on success.
    """
    aid = account.get("account_id") or account.get("id")
    if not aid:
        return False
    try:
        conn = _db()
        conn.execute(
            "INSERT OR REPLACE INTO accounts "
            "(id, email, password_hash, token, tier, role, full_name, company, "
            "job_title, email_validated, eula_accepted, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                aid,
                account.get("email", ""),
                account.get("password_hash", ""),
                account.get("token", ""),
                account.get("tier", "free"),
                account.get("role", "user"),
                account.get("full_name", ""),
                account.get("company", ""),
                account.get("job_title", ""),
                1 if account.get("email_validated", True) else 0,
                1 if account.get("eula_accepted", True) else 0,
                account.get("created_at", ""),
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        log.error("auth.save_account failed for %s: %s", aid, exc)
        return False
