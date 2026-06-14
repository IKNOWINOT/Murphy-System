"""
Ship 31bd — capacity-warning deduper / rate-limiter.

The capacity emitter was firing 'HITL queue has 51 pending' 35x in
24h. Once is enough. Suppress repeats unless:
  - the metric value changed meaningfully (>=10% drift), OR
  - more than 6 hours have passed since the last warning

Persistent state in capacity_dedupe.db so this survives restarts.
"""
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Optional

_DB = "/var/lib/murphy-production/capacity_dedupe.db"


def _init():
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capacity_dedupe (
            signature TEXT PRIMARY KEY,
            metric_key TEXT,
            last_value REAL,
            last_emitted_at TEXT,
            emit_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def should_emit(metric_key: str, current_value: float,
                min_drift_pct: float = 10.0,
                cooldown_hours: float = 6.0) -> bool:
    """Return True if this capacity warning should actually be sent."""
    _init()
    sig = hashlib.sha256(metric_key.encode()).hexdigest()[:16]
    conn = sqlite3.connect(_DB, timeout=10.0)
    row = conn.execute(
        "SELECT last_value, last_emitted_at, emit_count "
        "FROM capacity_dedupe WHERE signature=?", (sig,)
    ).fetchone()

    now = datetime.now(timezone.utc)
    if row is None:
        # First time ever — emit
        conn.execute(
            "INSERT INTO capacity_dedupe (signature, metric_key, last_value, "
            "last_emitted_at, emit_count) VALUES (?, ?, ?, ?, 1)",
            (sig, metric_key, current_value, now.isoformat())
        )
        conn.commit(); conn.close()
        return True

    last_value, last_at_iso, count = row
    last_at = datetime.fromisoformat(last_at_iso)
    hours_since = (now - last_at).total_seconds() / 3600

    # Cooldown override
    if hours_since >= cooldown_hours:
        conn.execute(
            "UPDATE capacity_dedupe SET last_value=?, last_emitted_at=?, "
            "emit_count=emit_count+1 WHERE signature=?",
            (current_value, now.isoformat(), sig)
        )
        conn.commit(); conn.close()
        return True

    # Drift check
    if last_value and abs(current_value - last_value) / max(abs(last_value), 1) * 100 >= min_drift_pct:
        conn.execute(
            "UPDATE capacity_dedupe SET last_value=?, last_emitted_at=?, "
            "emit_count=emit_count+1 WHERE signature=?",
            (current_value, now.isoformat(), sig)
        )
        conn.commit(); conn.close()
        return True

    conn.close()
    return False


def stats():
    _init()
    conn = sqlite3.connect(_DB, timeout=10.0)
    rows = conn.execute(
        "SELECT metric_key, last_value, last_emitted_at, emit_count "
        "FROM capacity_dedupe ORDER BY last_emitted_at DESC LIMIT 20"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM capacity_dedupe").fetchone()[0]
    conn.close()
    return {"total_signatures": total, "recent": [
        {"key": r[0], "value": r[1], "last": r[2], "count": r[3]}
        for r in rows
    ]}


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), indent=2))
