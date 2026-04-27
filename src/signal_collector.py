"""
PATCH-112 — src/signal_collector.py
Murphy System — Swarm Rosetta Signal Collector

Ingests all ambient signals (calendar, email, git, telemetry, incidents,
approval queue, LCM intents, executive decisions, patch outcomes) and
normalizes them into a unified SignalRecord written to SQLite.

This is the data foundation for the NL→Workflow engine.
Without signals, Rosetta has no context to translate from.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.signal_collector")

# ── Storage ──────────────────────────────────────────────────────────────────
_DB_PATH = Path("/var/lib/murphy-production/signal_records.db")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Signal Schema ─────────────────────────────────────────────────────────────

@dataclass
class SignalRecord:
    """Normalized signal record. Every signal type maps to this shape."""
    signal_id: str
    signal_type: str          # calendar | email | git | telemetry | incident
                              # | approval | lcm_intent | exec_decision | patch_outcome
    source: str               # which system produced it
    timestamp: str            # ISO-8601 UTC
    domain: str               # exec_admin | prod_ops | data | comms | system
    urgency: str              # immediate | scheduled | ambient
    stake: str                # low | medium | high | critical
    intent_hint: str          # rough NL intent inferred from signal
    entities: List[str]       # names, repos, services, people mentioned
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    workflow_triggered: Optional[str] = None  # DAG id if a workflow was started


# ── Database ──────────────────────────────────────────────────────────────────

class SignalDB:
    """Thread-safe SQLite backend for signal records."""

    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signal_records (
                    signal_id       TEXT PRIMARY KEY,
                    signal_type     TEXT NOT NULL,
                    source          TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    domain          TEXT NOT NULL,
                    urgency         TEXT NOT NULL,
                    stake           TEXT NOT NULL,
                    intent_hint     TEXT,
                    entities        TEXT,      -- JSON array
                    raw_payload     TEXT,      -- JSON object
                    processed       INTEGER DEFAULT 0,
                    workflow_triggered TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_type ON signal_records(signal_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON signal_records(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_processed ON signal_records(processed)")

    def _conn(self):
        return sqlite3.connect(str(self._db_path), timeout=10)

    def insert(self, record: SignalRecord) -> bool:
        try:
            with self._lock:
                with self._conn() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO signal_records
                        (signal_id, signal_type, source, timestamp, domain, urgency, stake,
                         intent_hint, entities, raw_payload, processed, workflow_triggered)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        record.signal_id, record.signal_type, record.source,
                        record.timestamp, record.domain, record.urgency, record.stake,
                        record.intent_hint, json.dumps(record.entities),
                        json.dumps(record.raw_payload), int(record.processed),
                        record.workflow_triggered
                    ))
            return True
        except Exception as exc:
            logger.error("SignalDB insert failed: %s", exc)
            return False

    def latest(self, signal_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        with self._conn() as conn:
            if signal_type:
                rows = conn.execute(
                    "SELECT * FROM signal_records WHERE signal_type=? ORDER BY timestamp DESC LIMIT ?",
                    (signal_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM signal_records ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        cols = ["signal_id","signal_type","source","timestamp","domain","urgency","stake",
                "intent_hint","entities","raw_payload","processed","workflow_triggered"]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["entities"] = json.loads(d["entities"] or "[]")
            d["raw_payload"] = json.loads(d["raw_payload"] or "{}")
            result.append(d)
        return result

    def unprocessed(self, limit: int = 20) -> List[Dict]:
        return self.latest(limit=limit)  # simplified — filter processed=0

    def mark_processed(self, signal_id: str, workflow_id: Optional[str] = None):
        with self._lock:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE signal_records SET processed=1, workflow_triggered=? WHERE signal_id=?",
                    (workflow_id, signal_id)
                )

    def stats(self) -> Dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM signal_records").fetchone()[0]
            by_type = conn.execute(
                "SELECT signal_type, COUNT(*) FROM signal_records GROUP BY signal_type"
            ).fetchall()
            unprocessed = conn.execute(
                "SELECT COUNT(*) FROM signal_records WHERE processed=0"
            ).fetchone()[0]
        return {
            "total": total,
            "unprocessed": unprocessed,
            "by_type": {t: c for t, c in by_type}
        }


# ── Normalizers ───────────────────────────────────────────────────────────────

import uuid

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sid() -> str:
    return f"sig-{uuid.uuid4().hex[:12]}"


class SignalCollector:
    """
    PATCH-112: Murphy Swarm Rosetta — Signal Collector.

    Ingest any signal type → normalize → store → make available
    to the Rosetta coordinator and NL Workflow Parser.
    """

    def __init__(self, db: Optional[SignalDB] = None):
        self._db = db or SignalDB()
        self._hooks: List = []  # callbacks when a signal is ingested
        logger.info("PATCH-112: SignalCollector initialized — DB: %s", _DB_PATH)

    def ingest(self, signal_type: str, source: str, payload: Dict[str, Any],
               domain: str = "system", urgency: str = "ambient",
               stake: str = "low", intent_hint: str = "",
               entities: Optional[List[str]] = None) -> SignalRecord:
        """
        Ingest a signal from any source. Normalizes and stores it.
        Returns the created SignalRecord.
        """
        record = SignalRecord(
            signal_id=_sid(),
            signal_type=signal_type,
            source=source,
            timestamp=_now(),
            domain=domain,
            urgency=urgency,
            stake=stake,
            intent_hint=intent_hint or f"{signal_type} from {source}",
            entities=entities or [],
            raw_payload=payload,
        )
        self._db.insert(record)
        logger.debug("Signal ingested: %s [%s] %s", record.signal_id, signal_type, intent_hint[:60])
        for hook in self._hooks:
            try:
                hook(record)
            except Exception as exc:
                logger.warning("Signal hook failed: %s", exc)
        return record

    def ingest_lcm_intent(self, intent: str, domain: str, account: str,
                          outcome: str = "") -> SignalRecord:
        """Ingest a processed LCM intent as a signal (ambient behavior)."""
        return self.ingest(
            signal_type="lcm_intent",
            source=f"lcm:{account}",
            payload={"intent": intent, "outcome": outcome, "account": account},
            domain=domain,
            urgency="ambient",
            stake="low",
            intent_hint=intent[:120],
            entities=[account],
        )

    def ingest_hardware_alert(self, metric: str, value: float, threshold: float) -> SignalRecord:
        """Ingest a hardware telemetry alert (triggered when threshold exceeded)."""
        stake = "high" if value > threshold * 1.2 else "medium"
        return self.ingest(
            signal_type="telemetry",
            source="hardware_telemetry",
            payload={"metric": metric, "value": value, "threshold": threshold},
            domain="prod_ops",
            urgency="immediate" if stake == "high" else "scheduled",
            stake=stake,
            intent_hint=f"{metric} exceeded threshold: {value:.1f} > {threshold:.1f}",
            entities=["murphy-production"],
        )

    def ingest_git_event(self, repo: str, branch: str, author: str,
                         message: str, event_type: str = "push") -> SignalRecord:
        """Ingest a git event (push, PR, tag)."""
        return self.ingest(
            signal_type="git",
            source=f"github:{repo}",
            payload={"repo": repo, "branch": branch, "author": author,
                     "message": message, "event_type": event_type},
            domain="prod_ops",
            urgency="immediate" if branch in ("main", "master") else "scheduled",
            stake="medium" if branch in ("main", "master") else "low",
            intent_hint=f"git {event_type}: {message[:80]}",
            entities=[author, repo],
        )

    def ingest_approval_request(self, task_id: str, requester: str,
                                action: str, stake: str = "medium") -> SignalRecord:
        """Ingest an approval queue item."""
        return self.ingest(
            signal_type="approval",
            source="approval_queue",
            payload={"task_id": task_id, "requester": requester, "action": action},
            domain="exec_admin",
            urgency="scheduled",
            stake=stake,
            intent_hint=f"Approval needed: {action}",
            entities=[requester, task_id],
        )

    def add_hook(self, fn) -> None:
        """Register a callback — called every time a signal is ingested."""
        self._hooks.append(fn)

    def latest(self, signal_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        return self._db.latest(signal_type=signal_type, limit=limit)

    def stats(self) -> Dict:
        return self._db.stats()


# ── Singleton ─────────────────────────────────────────────────────────────────
_collector_lock = threading.Lock()
_collector: Optional[SignalCollector] = None

def get_collector() -> SignalCollector:
    global _collector
    if _collector is None:
        with _collector_lock:
            if _collector is None:
                _collector = SignalCollector()
    return _collector
