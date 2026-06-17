"""Recursion gate — spawn-depth tracker. In-process counter + DB log."""
import threading, sqlite3, logging
from datetime import datetime, timezone

_DB = "/var/lib/murphy-production/recursion_gate.db"
_local = threading.local()
_MAX_DEPTH = 8
logger = logging.getLogger(__name__)


def _init():
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS gate_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT,
            event TEXT NOT NULL,
            label TEXT,
            depth INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.commit(); c.close()


def _stack():
    if not hasattr(_local, "stack"):
        _local.stack = []
    return _local.stack


def depth() -> int:
    return len(_stack())


def enter(label: str, correlation_id: str = "") -> bool:
    """Push a frame. Returns False if MAX_DEPTH exceeded (caller should abort)."""
    s = _stack()
    if len(s) >= _MAX_DEPTH:
        try:
            _init()
            c = sqlite3.connect(_DB, timeout=10.0)
            c.execute(
                "INSERT INTO gate_events (correlation_id, event, label, depth, created_at) "
                "VALUES (?,?,?,?,?)",
                (correlation_id, "BLOCKED_MAX_DEPTH", label, len(s),
                 datetime.now(timezone.utc).isoformat()),
            )
            c.commit(); c.close()
        except Exception:
            pass
        logger.warning("recursion_gate: BLOCKED at depth %d for %s", len(s), label)
        return False
    s.append(label)
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        c.execute(
            "INSERT INTO gate_events (correlation_id, event, label, depth, created_at) "
            "VALUES (?,?,?,?,?)",
            (correlation_id, "ENTER", label, len(s),
             datetime.now(timezone.utc).isoformat()),
        )
        c.commit(); c.close()
    except Exception:
        pass
    return True


def exit_(label: str = "", correlation_id: str = "") -> None:
    s = _stack()
    if s:
        s.pop()
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        c.execute(
            "INSERT INTO gate_events (correlation_id, event, label, depth, created_at) "
            "VALUES (?,?,?,?,?)",
            (correlation_id, "EXIT", label, len(s),
             datetime.now(timezone.utc).isoformat()),
        )
        c.commit(); c.close()
    except Exception:
        pass


def reset():
    """For test cleanup only."""
    if hasattr(_local, "stack"):
        _local.stack = []
