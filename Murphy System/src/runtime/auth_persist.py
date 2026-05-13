# src/runtime/auth_persist.py
# PATCH-274: Standalone account persistence. No dependency on src.runtime.auth.
# load_all_accounts() and upsert_account() backed by WAL sqlite.
import logging
import os
import time
from sqlite3 import connect as _sql_connect
from sqlite3 import Row as _Row
from typing import Dict, List

log = logging.getLogger(__name__)

_DB_PATH = os.environ.get("MURPHY_AUTH_DB", "/opt/Murphy-System/data/murphy_users.db")
_FB_PATH = os.path.join(os.getenv("MURPHY_PERSISTENCE_DIR", ".murphy_persistence"), "murphy_users.db")

def _get_db_path():
    primary_dir = os.path.dirname(_DB_PATH)
    try:
        os.makedirs(primary_dir, exist_ok=True)
        if os.path.isdir(primary_dir):
            return _DB_PATH
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(_FB_PATH), exist_ok=True)
    except Exception:
        pass
    return _FB_PATH

_ACTIVE_DB = _get_db_path()
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS accounts ("
    "id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, "
    "password_hash TEXT NOT NULL DEFAULT '', token TEXT DEFAULT '', "
    "tier TEXT DEFAULT 'free', role TEXT DEFAULT 'user', "
    "full_name TEXT DEFAULT '', company TEXT DEFAULT '', "
    "job_title TEXT DEFAULT '', email_validated INTEGER DEFAULT 1, "
    "eula_accepted INTEGER DEFAULT 1, created_at TEXT DEFAULT '', updated_at TEXT DEFAULT '')"
)

def _open_db():
    db_dir = os.path.dirname(_ACTIVE_DB)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = _sql_connect(_ACTIVE_DB, check_same_thread=False, timeout=10)
    conn.row_factory = _Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(_SCHEMA)
    conn.commit()
    return conn

def load_all_accounts() -> List[Dict]:
    try:
        conn = _open_db()
        rows = conn.execute(
            "SELECT id, email, password_hash, token, tier, role, "
            "full_name, company, job_title, email_validated, eula_accepted, created_at FROM accounts"
        ).fetchall()
        conn.close()
        return [{
            "account_id": row["id"], "email": row["email"],
            "password_hash": row["password_hash"], "token": row["token"] or "",
            "tier": row["tier"] or "free", "role": row["role"] or "user",
            "full_name": row["full_name"] or "", "company": row["company"] or "",
            "job_title": row["job_title"] or "", "email_validated": bool(row["email_validated"]),
            "eula_accepted": bool(row["eula_accepted"]), "created_at": row["created_at"] or ""
        } for row in rows]
    except Exception as exc:
        log.error("auth_persist.load_all_accounts failed: %s", exc)
        return []

def upsert_account(account: Dict) -> bool:
    aid = account.get("account_id") or account.get("id")
    if not aid:
        return False
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        conn = _open_db()
        conn.execute(
            "INSERT OR REPLACE INTO accounts "
            "(id,email,password_hash,token,tier,role,full_name,company,job_title,"
            "email_validated,eula_accepted,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, account.get("email",""), account.get("password_hash",""),
             account.get("token",""), account.get("tier","free"), account.get("role","user"),
             account.get("full_name",""), account.get("company",""), account.get("job_title",""),
             1 if account.get("email_validated",True) else 0,
             1 if account.get("eula_accepted",True) else 0,
             account.get("created_at",now), now))
        conn.commit(); conn.close()
        return True
    except Exception as exc:
        log.error("auth_persist.upsert_account failed for %s: %s", aid, exc)
        return False
