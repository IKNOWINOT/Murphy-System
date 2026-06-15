#!/usr/bin/env python3
"""
Ship 31co — Loud-fail guardrail on stranger_responder.

Tracks the last N R121 cycle outcomes. If classified>0 but stranger_sent==0
for >= ALERT_THRESHOLD consecutive cycles, raise an alert in the founder
digest. This catches the exact silent-failure mode that hit Ship 31ba.
"""
import sqlite3, json, logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("stranger_responder_guard_31co")
DB = "/var/lib/murphy-production/r121_guard.db"
ALERT_THRESHOLD = 2  # consecutive bad cycles before alert

def _init():
    c = sqlite3.connect(DB, timeout=8)
    c.execute("""CREATE TABLE IF NOT EXISTS r121_cycles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorded_at TEXT NOT NULL,
        classified INTEGER, allow_sent INTEGER, stranger_sent INTEGER,
        duration_s REAL,
        is_bad INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS r121_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raised_at TEXT NOT NULL,
        consecutive_bad INTEGER,
        last_classified INTEGER,
        message TEXT,
        acknowledged INTEGER DEFAULT 0
    )""")
    c.commit(); c.close()


def record_cycle(classified: int, allow_sent: int, stranger_sent: int,
                 duration_s: float) -> dict:
    _init()
    is_bad = 1 if (classified > 0 and (allow_sent + stranger_sent) == 0) else 0
    c = sqlite3.connect(DB, timeout=8)
    c.execute("INSERT INTO r121_cycles (recorded_at, classified, allow_sent, "
              "stranger_sent, duration_s, is_bad) VALUES (?,?,?,?,?,?)",
              (datetime.now(timezone.utc).isoformat(), classified, allow_sent,
               stranger_sent, duration_s, is_bad))
    c.commit()
    # check consecutive bad
    rows = c.execute("SELECT is_bad, classified FROM r121_cycles "
                     "ORDER BY id DESC LIMIT ?", (ALERT_THRESHOLD,)).fetchall()
    c.close()
    if len(rows) >= ALERT_THRESHOLD and all(r[0] == 1 for r in rows):
        return raise_alert(consecutive=ALERT_THRESHOLD, last_classified=rows[0][1])
    return {"ok": True, "is_bad": bool(is_bad), "alert": False}


def raise_alert(consecutive: int, last_classified: int) -> dict:
    _init()
    msg = (f"🔴 R121 silent failure: {consecutive} consecutive cycles classified "
           f"emails ({last_classified} in last cycle) but sent 0 replies. "
           f"Check stranger_responder logs for exception swallowing.")
    c = sqlite3.connect(DB, timeout=8)
    # only raise once per silence window
    recent = c.execute("SELECT id FROM r121_alerts WHERE acknowledged=0 "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    if recent:
        c.close()
        return {"ok": True, "alert": False, "reason": "already_open"}
    c.execute("INSERT INTO r121_alerts (raised_at, consecutive_bad, last_classified, "
              "message) VALUES (?,?,?,?)",
              (datetime.now(timezone.utc).isoformat(), consecutive,
               last_classified, msg))
    c.commit(); c.close()
    logger.error(msg)
    return {"ok": True, "alert": True, "message": msg}


def get_open_alerts() -> list:
    _init()
    c = sqlite3.connect(DB, timeout=8)
    rows = c.execute("SELECT id, raised_at, consecutive_bad, last_classified, message "
                     "FROM r121_alerts WHERE acknowledged=0 ORDER BY id DESC").fetchall()
    c.close()
    return [{"id":r[0],"raised_at":r[1],"consecutive_bad":r[2],
             "last_classified":r[3],"message":r[4]} for r in rows]


def acknowledge_alert(alert_id: int) -> dict:
    _init()
    c = sqlite3.connect(DB, timeout=8)
    c.execute("UPDATE r121_alerts SET acknowledged=1 WHERE id=?", (alert_id,))
    c.commit(); c.close()
    return {"ok": True}


def get_recent_cycles(limit: int = 20) -> list:
    _init()
    c = sqlite3.connect(DB, timeout=8)
    rows = c.execute("SELECT recorded_at, classified, allow_sent, stranger_sent, "
                     "duration_s, is_bad FROM r121_cycles ORDER BY id DESC LIMIT ?",
                     (limit,)).fetchall()
    c.close()
    return [{"at":r[0],"classified":r[1],"allow_sent":r[2],"stranger_sent":r[3],
             "duration_s":r[4],"is_bad":bool(r[5])} for r in rows]
