"""PCR-090e — Button-action commissioning ledger.

Per founder directive: every UI button gets:
  - success_surface: where success lands
  - fail_surface:    predicted failure UX
  - error_surface:   unexpected error UX + recovery path
  - status:          'commissioned' | 'pending' | 'broken'

Decorator + table per Murphy verdict (Z).

Usage:
    @commission_button(
        page='/os',
        button_id='cards.work.click',
        intent='Open chat with Murphy about work domain',
        success='Chat thread opens with work-context preamble',
        fail='Toast: "Chat unavailable, retrying..."',
        error='Toast + chat link to /chat?fallback=1; logged to ButtonAudit',
    )
    def on_work_card_click(): ...

Audit endpoints:
  GET /api/buttons/audit            — full commissioning ledger
  GET /api/buttons/audit/{page}     — commissioning for one page
"""
import sqlite3
import time
from typing import Callable, Dict, Any, Optional
from pathlib import Path

DB_PATH = "/var/lib/murphy-production/button_commission.db"


def _ensure_schema():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=2.0)
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS button_commission (
            button_id        TEXT PRIMARY KEY,
            page             TEXT NOT NULL,
            intent           TEXT NOT NULL,
            success_surface  TEXT NOT NULL,
            fail_surface     TEXT NOT NULL,
            error_surface    TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'commissioned',
            registered_at    REAL NOT NULL,
            last_seen_at     REAL NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS button_audit (
            audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            button_id        TEXT NOT NULL,
            event            TEXT NOT NULL,
            ts               REAL NOT NULL,
            detail           TEXT
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_button ON button_audit(button_id, ts)")
        conn.commit()
    finally:
        conn.close()


def register_button(
    page: str,
    button_id: str,
    intent: str,
    success: str,
    fail: str,
    error: str,
    status: str = "commissioned",
) -> Dict[str, Any]:
    _ensure_schema()
    now = time.time()
    conn = sqlite3.connect(DB_PATH, timeout=2.0)
    try:
        conn.execute(
            """INSERT INTO button_commission
               (button_id, page, intent, success_surface, fail_surface,
                error_surface, status, registered_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(button_id) DO UPDATE SET
                 page=excluded.page,
                 intent=excluded.intent,
                 success_surface=excluded.success_surface,
                 fail_surface=excluded.fail_surface,
                 error_surface=excluded.error_surface,
                 status=excluded.status,
                 last_seen_at=excluded.last_seen_at
            """,
            (button_id, page, intent, success, fail, error, status, now, now),
        )
        conn.commit()
        return {"button_id": button_id, "status": status, "registered_at": now}
    finally:
        conn.close()


def log_button_event(button_id: str, event: str, detail: str = "") -> None:
    try:
        _ensure_schema()
        conn = sqlite3.connect(DB_PATH, timeout=2.0)
        try:
            conn.execute(
                "INSERT INTO button_audit (button_id, event, ts, detail) VALUES (?, ?, ?, ?)",
                (button_id, event, time.time(), detail),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass  # logging must never crash UI


def get_commissioning_audit(page: Optional[str] = None) -> Dict[str, Any]:
    _ensure_schema()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=2.0)
    try:
        if page:
            rows = conn.execute(
                "SELECT button_id, page, intent, success_surface, fail_surface, "
                "error_surface, status, registered_at, last_seen_at "
                "FROM button_commission WHERE page=? ORDER BY button_id",
                (page,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT button_id, page, intent, success_surface, fail_surface, "
                "error_surface, status, registered_at, last_seen_at "
                "FROM button_commission ORDER BY page, button_id"
            ).fetchall()
        buttons = [
            {
                "button_id": r[0], "page": r[1], "intent": r[2],
                "success_surface": r[3], "fail_surface": r[4],
                "error_surface": r[5], "status": r[6],
                "registered_at": r[7], "last_seen_at": r[8],
            }
            for r in rows
        ]
        # Per-page summary
        pages = {}
        for b in buttons:
            p = b["page"]
            if p not in pages:
                pages[p] = {"total": 0, "commissioned": 0, "pending": 0, "broken": 0}
            pages[p]["total"] += 1
            pages[p][b["status"]] = pages[p].get(b["status"], 0) + 1
        return {
            "buttons": buttons,
            "total_count": len(buttons),
            "pages": pages,
        }
    finally:
        conn.close()
