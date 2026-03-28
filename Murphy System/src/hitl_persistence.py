"""
Murphy System — HITL Persistence Layer (DEF-047)

SQLite-backed persistence for the Human-in-the-Loop queue so that
pending approvals survive server restarts.

Tables:
  - hitl_items: full HITL item state (JSON blob + indexed columns)
  - automation_state: automation state snapshots
  - execution_log: audit trail of HITL decisions

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.hitl_persistence")

_DEFAULT_DB_PATH = os.environ.get(
    "MURPHY_HITL_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "hitl_queue.db"),
)


class HITLStore:
    """Thread-safe SQLite store for HITL queue items.

    Uses WAL mode for concurrent read access and serialized writes.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or _DEFAULT_DB_PATH
        self._lock = threading.Lock()

        # Ensure directory exists
        db_dir = Path(self._db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._init_db()

    # ── Connection helpers ──────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS hitl_items (
                        id          TEXT PRIMARY KEY,
                        type        TEXT NOT NULL DEFAULT 'approval',
                        title       TEXT NOT NULL DEFAULT '',
                        description TEXT DEFAULT '',
                        status      TEXT NOT NULL DEFAULT 'pending',
                        priority    TEXT DEFAULT 'medium',
                        created_at  TEXT DEFAULT '',
                        updated_at  TEXT DEFAULT '',
                        metadata    TEXT DEFAULT '{}',
                        full_json   TEXT NOT NULL DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS idx_hitl_status
                        ON hitl_items(status);
                    CREATE INDEX IF NOT EXISTS idx_hitl_type
                        ON hitl_items(type);
                    CREATE INDEX IF NOT EXISTS idx_hitl_priority
                        ON hitl_items(priority);
                    CREATE INDEX IF NOT EXISTS idx_hitl_created
                        ON hitl_items(created_at);

                    CREATE TABLE IF NOT EXISTS automation_state (
                        id          TEXT PRIMARY KEY,
                        state_json  TEXT NOT NULL DEFAULT '{}',
                        updated_at  TEXT DEFAULT ''
                    );

                    CREATE TABLE IF NOT EXISTS execution_log (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        hitl_id     TEXT NOT NULL,
                        action      TEXT NOT NULL,
                        actor       TEXT DEFAULT 'system',
                        timestamp   TEXT DEFAULT '',
                        details     TEXT DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS idx_exec_hitl
                        ON execution_log(hitl_id);
                """)
                conn.commit()
                logger.info("HITL persistence initialized: %s", self._db_path)
            finally:
                conn.close()

    # ── CRUD ────────────────────────────────────────────────────────────

    def save_item(self, item: Dict[str, Any]) -> None:
        """Insert or replace a HITL item."""
        with self._lock:
            conn = self._connect()
            try:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT OR REPLACE INTO hitl_items
                       (id, type, title, description, status, priority,
                        created_at, updated_at, metadata, full_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.get("id", ""),
                        item.get("type", "approval"),
                        item.get("title", ""),
                        item.get("description", ""),
                        item.get("status", "pending"),
                        item.get("priority", "medium"),
                        item.get("created_at", now),
                        now,
                        json.dumps(item.get("metadata", {})),
                        json.dumps(item),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> None:
        """Update specific fields of a HITL item."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT full_json FROM hitl_items WHERE id = ?", (item_id,)
                ).fetchone()
                if row is None:
                    logger.warning("HITL item %s not found for update", item_id)
                    return

                current = json.loads(row["full_json"])
                current.update(updates)
                now = datetime.now(timezone.utc).isoformat()

                conn.execute(
                    """UPDATE hitl_items
                       SET status=?, priority=?, updated_at=?, full_json=?
                       WHERE id=?""",
                    (
                        current.get("status", "pending"),
                        current.get("priority", "medium"),
                        now,
                        json.dumps(current),
                        item_id,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single HITL item by ID."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT full_json FROM hitl_items WHERE id = ?", (item_id,)
            ).fetchone()
            if row:
                return json.loads(row["full_json"])
            return None
        finally:
            conn.close()

    def load_all(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load all HITL items, optionally filtered by status."""
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT full_json FROM hitl_items WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT full_json FROM hitl_items ORDER BY created_at"
                ).fetchall()
            return [json.loads(r["full_json"]) for r in rows]
        finally:
            conn.close()

    def count(self, status: Optional[str] = None) -> int:
        """Count HITL items, optionally filtered by status."""
        conn = self._connect()
        try:
            if status:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM hitl_items WHERE status = ?",
                    (status,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM hitl_items"
                ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def save_execution(
        self, hitl_id: str, action: str, actor: str = "system",
        details: Optional[Dict] = None
    ) -> None:
        """Log an execution action (approve, reject, escalate, etc.)."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT INTO execution_log (hitl_id, action, actor, timestamp, details)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        hitl_id,
                        action,
                        actor,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(details or {}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()