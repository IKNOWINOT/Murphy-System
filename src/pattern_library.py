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



# ── PATCH-WIRE3-001 (R49): observe gate outcomes from chain_engine ────────────
# When chain_engine.evaluate_gate result lands in chain_step_gates, also
# crystallize the (domain, result) pair into pattern_library so we can
# learn which domain × gate-result combos succeed. This is the data flow
# Wire #4 (fitness_score → agent_contracts) will read.

def observe_gate_outcome(
    domain: str,
    gate_result: str,
    step_name: str = "",
    cost_delta: float = 0.0,
    chain_id: str = "",
) -> bool:
    """
    Record one gate-outcome observation into pattern_library.

    Args:
        domain: domain matched by domain_pipeline (e.g. "engineering", "product")
        gate_result: PASS | PARTIAL | BLOCKED
        step_name: optional step identifier for traceability
        cost_delta: compliance cost (positive = expensive, negative = credit)
        chain_id: optional chain instance ID

    Returns:
        True if observation written, False on any error (never raises).
    """
    import sqlite3 as _sq3
    import json as _json
    import logging as _logging
    import os as _os
    from datetime import datetime as _dt, timezone as _tz

    _log = _logging.getLogger("pattern_library")
    _DB = "/var/lib/murphy-production/pattern_library.db"

    if not domain or not gate_result:
        return False

    try:
        if not _os.path.exists(_DB):
            return False
        conn = _sq3.connect(_DB, timeout=3)
        try:
            # Ensure observation table exists (separate from patterns table —
            # additive so we don't conflict with existing crystallization code)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gate_observations (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain          TEXT NOT NULL,
                    gate_result     TEXT NOT NULL,
                    step_name       TEXT,
                    cost_delta      REAL DEFAULT 0,
                    chain_id        TEXT,
                    observed_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                    wire_version    TEXT DEFAULT 'WIRE3-001'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_go_domain_result
                ON gate_observations(domain, gate_result)
            """)
            conn.execute(
                "INSERT INTO gate_observations "
                "(domain, gate_result, step_name, cost_delta, chain_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (domain, gate_result, step_name[:200] if step_name else "",
                 float(cost_delta or 0), chain_id[:64] if chain_id else "")
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        _log.debug("observe_gate_outcome failed: %s", e)
        return False


def get_domain_fitness(domain: str) -> dict:
    """
    Return crystallized fitness for a domain — counts of each gate outcome.
    Used by Wire #4 to score agent_contracts.

    Returns: {"domain", "total", "pass", "partial", "blocked",
              "pass_rate", "wire_version"}
    """
    import sqlite3 as _sq3
    import os as _os
    _DB = "/var/lib/murphy-production/pattern_library.db"
    out = {"domain": domain, "total": 0, "pass": 0, "partial": 0,
           "blocked": 0, "pass_rate": 0.0, "wire_version": "WIRE3-001"}
    try:
        if not _os.path.exists(_DB):
            return out
        conn = _sq3.connect(f"file:{_DB}?mode=ro", uri=True, timeout=2)
        try:
            cur = conn.execute(
                "SELECT gate_result, COUNT(*) FROM gate_observations "
                "WHERE domain = ? GROUP BY gate_result", (domain,)
            )
            for result, count in cur.fetchall():
                key = (result or "").lower()
                if key in ("pass", "partial", "blocked"):
                    out[key] = count
                    out["total"] += count
            if out["total"] > 0:
                out["pass_rate"] = round(out["pass"] / out["total"], 3)
        finally:
            conn.close()
    except Exception:
        pass
    return out
