"""PSI history — operation log with cost/latency/outcome typing."""
import sqlite3, logging
from datetime import datetime, timezone

_DB = "/var/lib/murphy-production/psi_log.db"
logger = logging.getLogger(__name__)


def _init():
    c = sqlite3.connect(_DB, timeout=10.0)
    c.execute("""
        CREATE TABLE IF NOT EXISTS psi_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            correlation_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            cost_usd REAL DEFAULT 0.0,
            latency_ms INTEGER DEFAULT 0,
            outcome TEXT,
            detail TEXT,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_psi_corr ON psi_events(correlation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_psi_created ON psi_events(created_at)")
    c.commit(); c.close()


def log_op(correlation_id: str, operation: str,
           cost_usd: float = 0.0, latency_ms: int = 0,
           outcome: str = "", detail: str = "") -> None:
    """Record one operation. Never raises."""
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        c.execute(
            "INSERT INTO psi_events (correlation_id, operation, cost_usd, "
            "latency_ms, outcome, detail, created_at) VALUES (?,?,?,?,?,?,?)",
            (correlation_id, operation, float(cost_usd), int(latency_ms),
             outcome, detail[:2000], datetime.now(timezone.utc).isoformat()),
        )
        c.commit(); c.close()
    except Exception as exc:
        logger.debug("psi_history.log_op failed: %s", exc)


def list_for_turn(correlation_id: str):
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        rows = c.execute(
            "SELECT operation, cost_usd, latency_ms, outcome, detail, created_at "
            "FROM psi_events WHERE correlation_id=? ORDER BY id ASC",
            (correlation_id,),
        ).fetchall()
        c.close()
        return [{"operation": r[0], "cost_usd": r[1], "latency_ms": r[2],
                 "outcome": r[3], "detail": r[4], "created_at": r[5]}
                for r in rows]
    except Exception:
        return []


def sweep_old(days: int = 30) -> int:
    try:
        _init()
        c = sqlite3.connect(_DB, timeout=10.0)
        n = c.execute(
            f"DELETE FROM psi_events WHERE created_at < datetime('now','-{int(days)} days')"
        ).rowcount
        c.commit(); c.close()
        return n or 0
    except Exception:
        return 0
