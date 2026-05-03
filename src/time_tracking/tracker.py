"""
Time Tracker — SQLite-backed persistent implementation.
PATCH-158: Replaces in-memory stub with SQLite backend.
"""
from __future__ import annotations
import sqlite3, json, logging
import datetime as _dt
from typing import Any, Dict, List, Optional
from .models import TimeEntry, TimeSheet, EntryStatus, SheetStatus, _new_id, _now

logger = logging.getLogger(__name__)
_UTC = _dt.timezone.utc
_DB = "/var/lib/murphy-production/time_tracking.db"


def _db():
    db = sqlite3.connect(_DB)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS entries (
        id TEXT PRIMARY KEY, user_id TEXT DEFAULT 'founder', board_id TEXT DEFAULT '',
        item_id TEXT DEFAULT '', note TEXT DEFAULT '',
        started_at TEXT, ended_at TEXT, duration_seconds INTEGER DEFAULT 0,
        billable INTEGER DEFAULT 1, tags TEXT DEFAULT '[]',
        status TEXT DEFAULT 'completed')""")
    db.execute("""CREATE TABLE IF NOT EXISTS sheets (
        id TEXT PRIMARY KEY, user_id TEXT, period_start TEXT, period_end TEXT,
        entry_ids TEXT DEFAULT '[]', total_seconds INTEGER DEFAULT 0,
        status TEXT DEFAULT 'draft', submitted_at TEXT DEFAULT '', approved_by TEXT DEFAULT '')""")
    db.execute("""CREATE TABLE IF NOT EXISTS timer_state (
        id INTEGER PRIMARY KEY, active INTEGER DEFAULT 0, user_id TEXT DEFAULT '',
        board_id TEXT DEFAULT '', item_id TEXT DEFAULT '',
        note TEXT DEFAULT '', started_at TEXT DEFAULT '', billable INTEGER DEFAULT 1)""")
    db.execute("INSERT OR IGNORE INTO timer_state (id) VALUES (1)")
    db.commit()
    return db


def _seed():
    db = _db()
    if db.execute("SELECT COUNT(*) FROM entries").fetchone()[0] > 0:
        db.close(); return
    entries = [
        ("Shield Wall audit",      6*3600),
        ("PATCH-157 Matrix Chat",  4*3600+30*60),
        ("ROI model design",       2*3600),
        ("Nav style sweep",        3*3600+15*60),
        ("Team sync meeting",      1*3600),
    ]
    now_dt = _dt.datetime.now(tz=_UTC)
    for note, dur in entries:
        eid = _new_id()
        end = now_dt.isoformat()
        start = (now_dt - _dt.timedelta(seconds=dur)).isoformat()
        db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (eid, "founder", "", "", note, start, end, dur, 1, "[]", "completed"))
    db.commit(); db.close()


def _row_to_entry(r) -> TimeEntry:
    status_val = r["status"] if r["status"] else "completed"
    valid_statuses = [e.value for e in EntryStatus]
    if status_val not in valid_statuses:
        status_val = "completed"
    st = EntryStatus(status_val)
    return TimeEntry(id=r["id"], user_id=r["user_id"] or "", board_id=r["board_id"] or "",
                     item_id=r["item_id"] or "", note=r["note"] or "",
                     started_at=r["started_at"] or "", ended_at=r["ended_at"] or "",
                     duration_seconds=r["duration_seconds"] or 0, billable=bool(r["billable"]),
                     tags=json.loads(r["tags"] or "[]"), status=st)


class TimeTracker:
    def __init__(self): _seed()

    def start_timer(self, user_id, *, board_id="", item_id="", note="", billable=True) -> TimeEntry:
        db = _db(); now = _now(); eid = _new_id()
        db.execute("UPDATE timer_state SET active=1, user_id=?, board_id=?, item_id=?, note=?, started_at=?, billable=? WHERE id=1",
                   (user_id, board_id, item_id, note, now, 1 if billable else 0))
        db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (eid, user_id, board_id, item_id, note, now, "", 0, 1 if billable else 0, "[]", "running"))
        db.commit(); db.close()
        return TimeEntry(id=eid, user_id=user_id, board_id=board_id, item_id=item_id, note=note,
                         started_at=now, billable=billable, status=EntryStatus.RUNNING)

    def stop_timer(self, user_id) -> Optional[TimeEntry]:
        db = _db()
        ts = db.execute("SELECT * FROM timer_state WHERE id=1").fetchone()
        if not ts or not ts["active"]:
            db.close(); return None
        now = _now(); start = ts["started_at"]
        try:
            s = _dt.datetime.fromisoformat(start.replace("Z","")).replace(tzinfo=_UTC)
            dur = int((_dt.datetime.now(_UTC) - s).total_seconds())
        except: dur = 0
        r = db.execute("SELECT * FROM entries WHERE user_id=? AND status='running' ORDER BY started_at DESC LIMIT 1",
                       (ts["user_id"],)).fetchone()
        if r:
            db.execute("UPDATE entries SET ended_at=?, duration_seconds=?, status='completed' WHERE id=?",
                       (now, dur, r["id"]))
        db.execute("UPDATE timer_state SET active=0, user_id='', started_at='' WHERE id=1")
        db.commit()
        entry = _row_to_entry(db.execute("SELECT * FROM entries WHERE id=?", (r["id"],)).fetchone()) if r else None
        db.close(); return entry

    def get_active_timer(self, user_id) -> Optional[TimeEntry]:
        db = _db(); ts = db.execute("SELECT * FROM timer_state WHERE id=1").fetchone(); db.close()
        if not ts or not ts["active"] or ts["user_id"] != user_id:
            return None
        return TimeEntry(id="active", user_id=user_id, board_id=ts["board_id"] or "",
                         item_id=ts["item_id"] or "", note=ts["note"] or "",
                         started_at=ts["started_at"] or "", status=EntryStatus.RUNNING)

    def add_entry(self, user_id, *, duration_seconds=0, duration_minutes=0, note="",
                  description="", date="", board_id="", item_id="", started_at="",
                  billable=True, tags=None) -> TimeEntry:
        db = _db(); now = _now(); eid = _new_id()
        dur = duration_seconds or (duration_minutes * 60)
        start = started_at or date or now
        db.execute("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                   (eid, user_id, board_id, item_id, note or description,
                    start, now, dur, 1 if billable else 0, json.dumps(tags or []), "completed"))
        db.commit(); db.close()
        return TimeEntry(id=eid, user_id=user_id, board_id=board_id, item_id=item_id, note=note or description,
                         started_at=start, ended_at=now, duration_seconds=dur, billable=billable,
                         tags=tags or [], status=EntryStatus.COMPLETED)

    def list_entries(self, *, user_id=None, board_id=None, item_id=None,
                     from_date=None, to_date=None, limit=50) -> List[TimeEntry]:
        db = _db(); q = "SELECT * FROM entries WHERE 1=1"; params = []
        if user_id: q += " AND user_id=?"; params.append(user_id)
        if board_id: q += " AND board_id=?"; params.append(board_id)
        if item_id: q += " AND item_id=?"; params.append(item_id)
        if from_date: q += " AND started_at>=?"; params.append(from_date)
        if to_date: q += " AND started_at<=?"; params.append(to_date)
        q += f" ORDER BY started_at DESC LIMIT {int(limit)}"
        rows = db.execute(q, params).fetchall(); db.close()
        return [_row_to_entry(r) for r in rows]

    def get_entry(self, entry_id: str) -> Optional[TimeEntry]:
        db = _db(); r = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone(); db.close()
        return _row_to_entry(r) if r else None

    def create_sheet(self, user_id, *, period_start, period_end, entry_ids=None) -> TimeSheet:
        db = _db(); sid = _new_id(); eids = entry_ids or []
        total = 0
        for eid in eids:
            row = db.execute("SELECT duration_seconds FROM entries WHERE id=?", (eid,)).fetchone()
            if row: total += row[0] or 0
        db.execute("INSERT INTO sheets VALUES (?,?,?,?,?,?,?,?,?)",
                   (sid, user_id, period_start, period_end, json.dumps(eids), total, "draft", "", ""))
        db.commit(); db.close()
        return TimeSheet(id=sid, user_id=user_id, period_start=period_start, period_end=period_end,
                         entry_ids=eids, total_seconds=total, status=SheetStatus.DRAFT)

    def get_sheet(self, sheet_id: str) -> Optional[TimeSheet]:
        db = _db(); r = db.execute("SELECT * FROM sheets WHERE id=?", (sheet_id,)).fetchone(); db.close()
        if not r: return None
        ss = SheetStatus(r["status"]) if r["status"] in [e.value for e in SheetStatus] else SheetStatus.DRAFT
        return TimeSheet(id=r["id"], user_id=r["user_id"], period_start=r["period_start"],
                         period_end=r["period_end"], entry_ids=json.loads(r["entry_ids"] or "[]"),
                         total_seconds=r["total_seconds"] or 0, status=ss,
                         submitted_at=r["submitted_at"] or "", approved_by=r["approved_by"] or "")

    def list_sheets(self, *, user_id=None) -> List[TimeSheet]:
        db = _db(); q = "SELECT * FROM sheets WHERE 1=1"; params = []
        if user_id: q += " AND user_id=?"; params.append(user_id)
        rows = db.execute(q + " ORDER BY rowid DESC", params).fetchall(); db.close()
        result = []
        for r in rows:
            ss = SheetStatus(r["status"]) if r["status"] in [e.value for e in SheetStatus] else SheetStatus.DRAFT
            result.append(TimeSheet(id=r["id"], user_id=r["user_id"], period_start=r["period_start"],
                                    period_end=r["period_end"], entry_ids=json.loads(r["entry_ids"] or "[]"),
                                    total_seconds=r["total_seconds"] or 0, status=ss))
        return result
