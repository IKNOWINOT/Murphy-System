"""
PATCH-119 — src/pattern_library.py
Murphy System — Swarm Rosetta Pattern Library

SQLite-backed store of learned workflow patterns.
Every successful DAG run writes a pattern record keyed by (domain, intent_fingerprint).
The Rosetta PAST layer reads from here before calling the LLM.

Intent fingerprint: hash of the 5 most significant lowercased words (stop-word stripped).
This gives fuzzy-but-stable matching without vector DB dependencies.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.pattern_library")

_DB_PATH = Path("/var/lib/murphy-production/pattern_library.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Stop words stripped before fingerprinting
_STOP = {"a","an","the","and","or","to","for","of","in","on","with","is","it",
         "this","that","be","by","at","as","from","i","me","my","we","you","your"}


def _fingerprint(text: str) -> str:
    """Stable intent fingerprint: top-5 significant words, sorted, hashed."""
    words = re.findall(r"[a-z]+", text.lower())
    sig = sorted([w for w in words if w not in _STOP and len(w) > 2])[:5]
    key = " ".join(sig)
    return hashlib.md5(key.encode()).hexdigest()[:12]


class PatternLibrary:
    """
    PATCH-119: Learn from workflow outcomes. Retrieve known patterns.
    """

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        logger.info("PATCH-119: PatternLibrary initialized — %s", db_path)

    def _conn(self):
        return sqlite3.connect(str(self._db_path), timeout=10)

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_id       TEXT PRIMARY KEY,
                    domain           TEXT NOT NULL,
                    intent_sample    TEXT NOT NULL,
                    intent_fingerprint TEXT NOT NULL,
                    step_template    TEXT NOT NULL,  -- JSON array of step dicts
                    stake            TEXT DEFAULT 'low',
                    success_count    INTEGER DEFAULT 0,
                    failure_count    INTEGER DEFAULT 0,
                    last_used        TEXT,
                    created_at       TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pat_domain ON patterns(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pat_fp ON patterns(intent_fingerprint)")

    def record(self, dag_id: str, domain: str, intent_text: str,
               steps: List[Dict], stake: str, success: bool) -> str:
        """Record a workflow outcome. Updates existing pattern or creates new one."""
        fp = _fingerprint(intent_text)
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            with self._conn() as conn:
                existing = conn.execute(
                    "SELECT pattern_id, success_count, failure_count FROM patterns "
                    "WHERE intent_fingerprint=? AND domain=?", (fp, domain)
                ).fetchone()

                if existing:
                    pid, sc, fc = existing
                    if success:
                        conn.execute("UPDATE patterns SET success_count=?, last_used=? WHERE pattern_id=?",
                                     (sc+1, now, pid))
                    else:
                        conn.execute("UPDATE patterns SET failure_count=?, last_used=? WHERE pattern_id=?",
                                     (fc+1, now, pid))
                    logger.debug("PatternLib: updated pattern %s (%s/%s)", pid, sc+1 if success else sc, fc+1 if not success else fc)
                    return pid
                else:
                    import uuid
                    pid = f"pat-{uuid.uuid4().hex[:10]}"
                    conn.execute("""
                        INSERT INTO patterns
                        (pattern_id, domain, intent_sample, intent_fingerprint, step_template,
                         stake, success_count, failure_count, last_used, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        pid, domain, intent_text[:200], fp,
                        json.dumps(steps), stake,
                        1 if success else 0, 0 if success else 1, now, now
                    ))
                    logger.info("PatternLib: new pattern %s [%s] %s", pid, domain, intent_text[:60])
                    return pid

    def lookup(self, intent_text: str, domain: str) -> Optional[Dict]:
        """
        Retrieve best matching pattern for this intent+domain.
        Returns the pattern dict with step_template, or None if no match.
        """
        fp = _fingerprint(intent_text)
        with self._conn() as conn:
            # Exact fingerprint match first
            row = conn.execute(
                "SELECT * FROM patterns WHERE intent_fingerprint=? AND domain=? "
                "ORDER BY success_count DESC LIMIT 1", (fp, domain)
            ).fetchone()

            if not row:
                # Fuzzy: same domain, any pattern (pick highest success)
                row = conn.execute(
                    "SELECT * FROM patterns WHERE domain=? AND success_count > 0 "
                    "ORDER BY success_count DESC LIMIT 1", (domain,)
                ).fetchone()

        if not row:
            return None

        cols = ["pattern_id","domain","intent_sample","intent_fingerprint","step_template",
                "stake","success_count","failure_count","last_used","created_at"]
        d = dict(zip(cols, row))
        d["step_template"] = json.loads(d["step_template"])
        return d

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
            by_domain = conn.execute(
                "SELECT domain, COUNT(*), SUM(success_count), SUM(failure_count) "
                "FROM patterns GROUP BY domain"
            ).fetchall()
        return {
            "total_patterns": total,
            "by_domain": {d: {"patterns": c, "successes": s, "failures": f}
                          for d, c, s, f in by_domain}
        }

    def top_patterns(self, limit: int = 10) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT pattern_id, domain, intent_sample, success_count, failure_count "
                "FROM patterns ORDER BY success_count DESC LIMIT ?", (limit,)
            ).fetchall()
        cols = ["pattern_id","domain","intent_sample","success_count","failure_count"]
        return [dict(zip(cols, r)) for r in rows]


_pat_lib: Optional[PatternLibrary] = None
_pat_lock = threading.Lock()

def get_pattern_library() -> PatternLibrary:
    global _pat_lib
    if _pat_lib is None:
        with _pat_lock:
            if _pat_lib is None:
                _pat_lib = PatternLibrary()
    return _pat_lib
