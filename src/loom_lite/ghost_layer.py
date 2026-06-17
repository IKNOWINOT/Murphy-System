"""Per-turn working-set snapshots."""
import json, sqlite3, logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_DB = "/var/lib/murphy-production/ghost_snapshots.db"
logger = logging.getLogger(__name__)


def _init():
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            phase TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_gs_corr ON snapshots(correlation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_gs_created ON snapshots(created_at)")
    c.commit(); c.close()


def snapshot(correlation_id: str, phase: str, payload: Dict[str, Any]) -> None:
    """Record a working-set snapshot. Never raises."""
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        c.execute(
            "INSERT INTO snapshots (correlation_id, phase, payload_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (correlation_id, phase, json.dumps(payload, default=str)[:50000],
             datetime.now(timezone.utc).isoformat()),
        )
        c.commit(); c.close()
    except Exception as exc:
        logger.debug("ghost_layer.snapshot failed: %s", exc)


def list_for_turn(correlation_id: str) -> List[Dict[str, Any]]:
    """Return all snapshots for a correlation_id in order."""
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        rows = c.execute(
            "SELECT phase, payload_json, created_at FROM snapshots "
            "WHERE correlation_id=? ORDER BY id ASC",
            (correlation_id,),
        ).fetchall()
        c.close()
        return [{"phase": r[0], "payload": json.loads(r[1]), "created_at": r[2]}
                for r in rows]
    except Exception as exc:
        logger.debug("ghost_layer.list_for_turn failed: %s", exc)
        return []


def sweep_old(days: int = 7) -> int:
    """Retention sweep — call from a daily timer."""
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        n = c.execute(
            f"DELETE FROM snapshots WHERE created_at < datetime('now','-{int(days)} days')"
        ).rowcount
        c.commit(); c.close()
        return n or 0
    except Exception:
        return 0
