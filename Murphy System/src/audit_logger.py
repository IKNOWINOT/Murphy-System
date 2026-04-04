# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Trading Audit Logger — Murphy System

Logs EVERY trading decision with full context.  Storage is either JSON-lines
(default) or SQLite (optional).  Supports structured queries and CSV export.

Logged per decision:
  - Timestamp
  - Strategy that generated the signal
  - Signal details (direction, size, price targets)
  - Risk assessment at time of signal
  - Whether trade was executed or rejected (and why)
  - Actual execution details
  - P&L outcome
  - Calibration adjustments made

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_IN_MEMORY = 10_000

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class TradeOutcome(str, Enum):
    """Result of a trade decision (Enum subclass)."""
    EXECUTED = "executed"
    REJECTED = "rejected"
    PENDING  = "pending"


class CalibrationAction(str, Enum):
    """Type of calibration performed (Enum subclass)."""
    NONE         = "none"
    COST_MODEL   = "cost_model"
    STOP_LOSS    = "stop_loss"
    POSITION_SIZE = "position_size"
    STRATEGY_PARAM = "strategy_param"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SignalDetails:
    """Snapshot of the trading signal at decision time."""
    strategy_id:    str
    pair:           str
    direction:      str        # "buy" | "sell" | "hold"
    suggested_price: float
    suggested_size:  float
    stop_loss:      Optional[float]
    take_profit:    Optional[float]
    confidence:     float      # 0.0-1.0
    reasoning:      str        = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionDetails:
    """Actual execution details (filled after execution)."""
    order_id:      str
    executed_price: float
    executed_size:  float
    exchange_fee:  float
    slippage:      float
    timestamp:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditEntry:
    """Single immutable audit log entry."""
    entry_id:           str
    timestamp:          str
    strategy_id:        str
    pair:               str
    outcome:            TradeOutcome
    rejection_reason:   str             = ""
    signal:             Optional[Dict[str, Any]] = None
    risk_assessment:    Optional[Dict[str, Any]] = None
    execution:          Optional[Dict[str, Any]] = None
    pnl_usd:            Optional[float] = None
    calibration_action: CalibrationAction = CalibrationAction.NONE
    calibration_notes:  str             = ""
    metadata:           Dict[str, Any]  = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["outcome"]            = self.outcome.value
        d["calibration_action"] = self.calibration_action.value
        return d


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------


class TradingAuditLogger:
    """
    Structured audit logger for all trading decisions.

    Supports two backends:
      - ``":memory:"`` (default) — in-process list (fast, non-persistent)
      - ``"<path>.db"``         — SQLite database (persistent, queryable)
      - ``"<path>.jsonl"``      — JSON lines file (append-only, portable)

    Thread-safe.
    """

    def __init__(self, storage: str = ":memory:") -> None:
        self._storage = storage
        self._entries: List[AuditEntry] = []
        self._lock = threading.Lock()
        self._db: Optional[sqlite3.Connection] = None
        self._jsonl_path: Optional[str] = None

        if storage.endswith(".db"):
            self._init_sqlite(storage)
        elif storage.endswith(".jsonl"):
            self._jsonl_path = storage

    # ------------------------------------------------------------------
    # Logging API
    # ------------------------------------------------------------------

    def log_decision(
        self,
        strategy_id:      str,
        pair:             str,
        signal:           Optional[SignalDetails],
        risk_assessment:  Optional[Dict[str, Any]],
        outcome:          TradeOutcome,
        rejection_reason: str                = "",
        execution:        Optional[ExecutionDetails] = None,
        pnl_usd:          Optional[float]    = None,
        calibration_action: CalibrationAction = CalibrationAction.NONE,
        calibration_notes:  str              = "",
        metadata:           Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Create and persist a single audit log entry."""
        entry = AuditEntry(
            entry_id           = str(uuid.uuid4()),
            timestamp          = datetime.now(timezone.utc).isoformat(),
            strategy_id        = strategy_id,
            pair               = pair,
            outcome            = outcome,
            rejection_reason   = rejection_reason,
            signal             = signal.to_dict() if signal else None,
            risk_assessment    = risk_assessment,
            execution          = execution.to_dict() if execution else None,
            pnl_usd            = pnl_usd,
            calibration_action = calibration_action,
            calibration_notes  = calibration_notes,
            metadata           = metadata or {},
        )
        with self._lock:
            capped_append(self._entries, entry, _MAX_IN_MEMORY)
            self._persist(entry)
        logger.debug(
            "AuditLogger: [%s] %s %s → %s",
            entry.timestamp[:19], pair, strategy_id, outcome.value,
        )
        return entry

    def update_pnl(self, entry_id: str, pnl_usd: float) -> bool:
        """Update the P&L field on an already-logged entry (when trade closes)."""
        with self._lock:
            for e in self._entries:
                if e.entry_id == entry_id:
                    e.pnl_usd = pnl_usd
                    self._update_pnl_db(entry_id, pnl_usd)
                    return True
        return False

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    def query(
        self,
        strategy_id:  Optional[str]         = None,
        pair:         Optional[str]         = None,
        outcome:      Optional[TradeOutcome] = None,
        since:        Optional[str]         = None,   # ISO timestamp
        until:        Optional[str]         = None,   # ISO timestamp
        limit:        int                   = 100,
    ) -> List[Dict[str, Any]]:
        """Filter audit entries.  All parameters are optional AND-combined."""
        with self._lock:
            results = list(self._entries)

        if strategy_id:
            results = [e for e in results if e.strategy_id == strategy_id]
        if pair:
            results = [e for e in results if e.pair == pair]
        if outcome:
            results = [e for e in results if e.outcome == outcome]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]

        return [e.to_dict() for e in results[-limit:]]

    def export_csv(
        self,
        strategy_id: Optional[str] = None,
        since:       Optional[str] = None,
    ) -> str:
        """Export filtered log to CSV string."""
        rows = self.query(strategy_id=strategy_id, since=since, limit=_MAX_IN_MEMORY)
        if not rows:
            return ""
        # Flatten nested dicts for CSV
        flat_rows = []
        for r in rows:
            flat = {}
            for k, v in r.items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        flat[f"{k}_{kk}"] = vv
                else:
                    flat[k] = v
            flat_rows.append(flat)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(flat_rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flat_rows)
        return output.getvalue()

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregate statistics over all logged entries."""
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return {"total_entries": 0}
        executed = [e for e in entries if e.outcome == TradeOutcome.EXECUTED]
        rejected = [e for e in entries if e.outcome == TradeOutcome.REJECTED]
        pnls     = [e.pnl_usd for e in executed if e.pnl_usd is not None]
        return {
            "total_entries":  len(entries),
            "executed_count": len(executed),
            "rejected_count": len(rejected),
            "pending_count":  len([e for e in entries if e.outcome == TradeOutcome.PENDING]),
            "total_pnl_usd":  round(sum(pnls), 4) if pnls else None,
            "win_count":      sum(1 for p in pnls if p > 0),
            "loss_count":     sum(1 for p in pnls if p <= 0),
            "earliest":       entries[0].timestamp,
            "latest":         entries[-1].timestamp,
        }

    # ------------------------------------------------------------------
    # Storage backends
    # ------------------------------------------------------------------

    def _init_sqlite(self, path: str) -> None:
        """Initialise SQLite database."""
        try:
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    entry_id           TEXT PRIMARY KEY,
                    timestamp          TEXT NOT NULL,
                    strategy_id        TEXT,
                    pair               TEXT,
                    outcome            TEXT,
                    rejection_reason   TEXT,
                    signal_json        TEXT,
                    risk_json          TEXT,
                    execution_json     TEXT,
                    pnl_usd            REAL,
                    calibration_action TEXT,
                    calibration_notes  TEXT,
                    metadata_json      TEXT
                )
                """
            )
            self._db.commit()
        except Exception as exc:
            logger.warning("AuditLogger: SQLite init failed (%s) — using in-memory.", exc)
            self._db = None

    def _persist(self, entry: AuditEntry) -> None:
        """Write entry to SQLite or JSONL backend."""
        if self._db:
            try:
                self._db.execute(
                    """
                    INSERT OR REPLACE INTO audit_log VALUES
                    (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        entry.entry_id, entry.timestamp, entry.strategy_id, entry.pair,
                        entry.outcome.value, entry.rejection_reason,
                        json.dumps(entry.signal),
                        json.dumps(entry.risk_assessment),
                        json.dumps(entry.execution),
                        entry.pnl_usd,
                        entry.calibration_action.value,
                        entry.calibration_notes,
                        json.dumps(entry.metadata),
                    ),
                )
                self._db.commit()
            except Exception as exc:
                logger.warning("AuditLogger: SQLite write failed: %s", exc)
        elif self._jsonl_path:
            try:
                with open(self._jsonl_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except Exception as exc:
                logger.warning("AuditLogger: JSONL write failed: %s", exc)

    def _update_pnl_db(self, entry_id: str, pnl_usd: float) -> None:
        if self._db:
            try:
                self._db.execute(
                    "UPDATE audit_log SET pnl_usd=? WHERE entry_id=?",
                    (pnl_usd, entry_id),
                )
                self._db.commit()
            except Exception:
                logger.debug("Suppressed exception in audit_logger")
