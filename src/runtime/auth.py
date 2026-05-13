"""
src/runtime/auth.py — Persistent auth bridge for murphy_production_server.py

Provides register_account, create_session_token, get_account_from_token
using the same SQLite persistence dir as the rest of the Murphy system.

Uses _prod_hash_password / _prod_verify_password conventions (PBKDF2-SHA256
fallback, bcrypt preferred) compatible with the existing auth infrastructure
in murphy_production_server.py.

PATCH-274 — 2026-05-13
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from typing import Optional, Tuple

_DB_DIR  = os.getenv("MURPHY_PERSISTENCE_DIR", ".murphy_persistence")
_DB_PATH = os.path.join(_DB_DIR, "murphy_accounts.db")

# ── optional bcrypt (same detection pattern as MPS) ─────────────────────
try:
    import bcrypt as _bcrypt  # type: ignore[import-untyped]
except ImportError:
    _bcrypt = None  # type: ignore[assignment]


def _db() -> sqlite3.Connection:
    os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id             TEXT PRIMARY KEY,
            email          TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash  TEXT NOT NULL,
            token          TEXT,
            tier           TEXT NOT NULL DEFAULT 'free',
            role           TEXT NOT NULL DEFAULT 'user',
            full_name      TEXT DEFAULT '',
            company        TEXT DEFAULT '',
            created_at     REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def _hash(password: str) -> str:
    if _bcrypt is not None:
        return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    salt = secrets.token_hex(16)
    dk   = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000)
    return f"pbkdf2:{salt}:{dk.hex()}"


def _verify(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2:"):
            _, salt, expected = stored.split(":", 2)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000)
            return secrets.compare_digest(dk.hex(), expected)
        if _bcrypt is not None:
            return _bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    except Exception:
        pass
    return False


# ── Founder override ─────────────────────────────────────────────────────
_FOUNDER_EMAILS = {"cpost@murphy.systems", "hpost@murphy.systems"}


def _founder_tier_role(email: str) -> Tuple[str, str]:
    if email.lower() in _FOUNDER_EMAILS:
        return "enterprise", "owner"
    return "free", "user"


# ── Public API ───────────────────────────────────────────────────────────

def register_account(
    email: str,
    password: str,
    tier: str = "free",
    role: str = "user",
    full_name: str = "",
    company: str = "",
) -> Tuple[Optional[str], Optional[str]]:
    """
    Register a new account.

    Returns (account_id, session_token) on success.
    Returns (None, None) if the email is already registered.
    """
    email = email.lower().strip()
    f_tier, f_role = _founder_tier_role(email)
    tier = f_tier
    role = f_role

    account_id = "acct-" + secrets.token_hex(12)
    tok        = secrets.token_urlsafe(32)
    pw_hash    = _hash(password)

    try:
        conn = _db()
        conn.execute(
            "INSERT INTO accounts (id, email, password_hash, token, tier, role, full_name, company, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, email, pw_hash, tok, tier, role, full_name, company, time.time()),
        )
        conn.commit()
        conn.close()
        return account_id, tok
    except sqlite3.IntegrityError:
        # Duplicate email
        return None, None


def authenticate(email: str, password: str) -> Optional[Tuple[str, str]]:
    """
    Verify credentials and return a fresh (account_id, token) on success.
    Returns None on bad credentials.
    """
    email = email.lower().strip()
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, password_hash FROM accounts WHERE email = ?", (email,)
        ).fetchone()
        conn.close()
    except Exception:
        return None

    if not row:
        return None
    account_id, pw_hash = row
    if not _verify(password, pw_hash):
        return None

    tok = create_session_token(account_id)
    return account_id, tok


def create_session_token(account_id: str) -> str:
    """Rotate and persist a fresh session token for an account."""
    tok = secrets.token_urlsafe(32)
    try:
        conn = _db()
        conn.execute("UPDATE accounts SET token = ? WHERE id = ?", (tok, account_id))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return tok


def get_account_from_token(token: str) -> Optional[str]:
    """Return account_id for a valid session token, or None."""
    if not token:
        return None
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id FROM accounts WHERE token = ?", (token,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def get_account_record(account_id: str) -> Optional[dict]:
    """Return the full account dict for an account_id, or None."""
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, email, tier, role, full_name, company, created_at "
            "FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "account_id": row[0],
            "email":      row[1],
            "tier":       row[2],
            "role":       row[3],
            "full_name":  row[4],
            "company":    row[5],
            "created_at": row[6],
        }
    except Exception:
        return None


def load_all_accounts() -> list:
    """
    Return all accounts as a list of dicts.
    Used by murphy_production_server._load_prod_accounts_from_db() on startup.
    """
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT id, email, password_hash, token, tier, role, full_name, company, created_at "
            "FROM accounts"
        ).fetchall()
        conn.close()
        return [
            {
                "account_id":    r[0],
                "email":         r[1],
                "password_hash": r[2],
                "token":         r[3],
                "tier":          r[4] or "free",
                "role":          r[5] or "user",
                "full_name":     r[6] or "",
                "company":       r[7] or "",
                "created_at":    r[8],
                "email_validated": True,
                "eula_accepted":   True,
                "job_title":       "",
            }
            for r in rows
        ]
    except Exception:
        return []
