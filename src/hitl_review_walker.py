"""
PATCH-WALKER-001 (2026-05-28 R74) — HITL review walker (cursor-through-comments)

WHAT THIS IS:
  A walker that serves HITL review items ONE AT A TIME in chronological order
  to a reviewer. Like cursor-through-comments in a document — forward motion,
  in-flow, with each item inviting verify/flag/suggest/skip.

WHY IT EXISTS:
  R64/R66 trails accumulate (12+ rows in provenance_trails). Each one is
  reviewable but no walker UX exists. List/queue views require the reviewer
  to pick what to look at next — decision fatigue. Walker eliminates that:
  system always serves the NEXT item, reviewer just acts.

  Corey's R-7 insight: review should be the same shape as cursor-through-
  comments-in-document — chronological, in-flow, with each item presenting
  the same action menu.

HOW IT FITS:
  Consumes hitl_provenance.list_trails() + hitl_prov_adapter.summarize for
  context. Uses gfo_augmentations table for additional review items. Adds
  thin cursor-state layer: walker_cursors table tracks each reviewer's
  position.

  Phase D UI (later) will render the walker as keyboard-driven flow.
  Today the walker exposes Python API + can be tested via CLI.

PUBLIC SURFACE:
  get_next(reviewer_id, kinds=None) -> Dict | None
    → returns NEXT review item with surrounding context + action menu
  record_decision(reviewer_id, item_id, action, note=None) -> Dict
    → applies action, advances cursor, returns next item
  get_progress(reviewer_id) -> Dict
    → reviewed_today, remaining, flagged_today
  rewind(reviewer_id, items=1) -> Dict
    → move cursor backward N items

ACTIONS:
  verify  — mark trail/item as verified ✓
  flag    — open hitl ticket (R64 wire)
  suggest — open ticket with correction_data
  skip    — note skip + advance (item may return later)
  snooze  — advance, return tomorrow

DEPENDENCIES:
  - src.hitl_provenance (R64) — list_trails, open_feedback_ticket, get_trail
  - src.hitl_prov_adapter (R66) — summarize_trail_for_human (optional)

LAST UPDATED: 2026-05-28 R74
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hitl_walker")

_WALKER_DB = "/var/lib/murphy-production/hitl_provenance.db"


def _ensure_cursor_table() -> None:
    """Create walker_cursors + walker_decisions if not present."""
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS walker_cursors (
                reviewer_id     TEXT PRIMARY KEY,
                last_item_ts    TEXT,
                last_item_id    TEXT,
                items_reviewed  INTEGER DEFAULT 0,
                items_flagged   INTEGER DEFAULT 0,
                items_skipped   INTEGER DEFAULT 0,
                skip_list       TEXT DEFAULT '[]',
                last_active_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                wire_version    TEXT DEFAULT 'WALKER-001'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS walker_decisions (
                decision_id     TEXT PRIMARY KEY,
                reviewer_id     TEXT,
                item_id         TEXT,
                action          TEXT,
                note            TEXT,
                decided_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                wire_version    TEXT DEFAULT 'WALKER-001'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_walker_decisions_rev ON walker_decisions(reviewer_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_walker_decisions_when ON walker_decisions(decided_at)")
        conn.commit()
    finally:
        conn.close()


def _get_cursor(reviewer_id: str) -> Dict[str, Any]:
    """Fetch (or create) cursor row for this reviewer."""
    _ensure_cursor_table()
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM walker_cursors WHERE reviewer_id = ?", (reviewer_id,)).fetchone()
        if row:
            return dict(row)
        # Initialize
        conn.execute(
            "INSERT INTO walker_cursors (reviewer_id, last_item_ts, items_reviewed) "
            "VALUES (?, ?, 0)", (reviewer_id, "1970-01-01T00:00:00Z")
        )
        conn.commit()
        row = conn.execute("SELECT * FROM walker_cursors WHERE reviewer_id = ?", (reviewer_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def _advance_cursor(reviewer_id: str, item_id: str, item_ts: str,
                    action: str = "skip") -> None:
    """Move cursor forward + increment counters."""
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        inc_reviewed = 1 if action in ("verify", "flag", "suggest") else 0
        inc_flagged = 1 if action in ("flag", "suggest") else 0
        inc_skipped = 1 if action in ("skip", "snooze") else 0
        conn.execute(
            """UPDATE walker_cursors SET
                last_item_ts = ?, last_item_id = ?,
                items_reviewed = items_reviewed + ?,
                items_flagged = items_flagged + ?,
                items_skipped = items_skipped + ?,
                last_active_at = CURRENT_TIMESTAMP
               WHERE reviewer_id = ?""",
            (item_ts, item_id, inc_reviewed, inc_flagged, inc_skipped, reviewer_id)
        )
        conn.commit()
    finally:
        conn.close()


def _list_eligible_items(cursor_ts: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Union all reviewable items newer than cursor, ordered by timestamp.
    Sources: provenance_trails + gfo_augmentations (when refusal_detected=1)
    """
    items: List[Dict[str, Any]] = []

    # Provenance trails (hitl_provenance.db)
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        conn.row_factory = sqlite3.Row
        for r in conn.execute(
            """SELECT trail_id, command_module, command_function, source_kind,
                      source_hint, hitl_status, captured_at
               FROM provenance_trails
               WHERE captured_at > ?
               ORDER BY captured_at ASC LIMIT ?""",
            (cursor_ts, limit)
        ).fetchall():
            d = dict(r)
            d["_kind"] = "provenance_trail"
            d["_ts"] = d["captured_at"]
            d["_id"] = d["trail_id"]
            items.append(d)
    finally:
        conn.close()

    # gfo_augmentations (murphy_audit.db) — chat refusal events
    audit_db = "/var/lib/murphy-production/murphy_audit.db"
    if os.path.exists(audit_db):
        conn2 = sqlite3.connect(audit_db, timeout=3)
        try:
            conn2.row_factory = sqlite3.Row
            for r in conn2.execute(
                """SELECT event_id, action, target, finding_ok, finding_reason,
                          augmented, ts
                   FROM gfo_augmentations
                   WHERE ts > ? AND refusal_detected = 1
                   ORDER BY ts ASC LIMIT ?""",
                (cursor_ts, limit)
            ).fetchall():
                d = dict(r)
                d["_kind"] = "gfo_augmentation"
                d["_ts"] = d["ts"]
                d["_id"] = f"gfo_{d['event_id']}"
                items.append(d)
        finally:
            conn2.close()

    items.sort(key=lambda x: x.get("_ts", ""))
    return items[:limit]


def _enrich_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Add the action menu + summary fields to an item for review display."""
    enriched = {
        "item_id":    item["_id"],
        "kind":       item["_kind"],
        "timestamp":  item["_ts"],
        "raw":        item,
        "actions":    {
            "verify":  f"/api/hitl/walker/decision  body: action=verify  item_id={item['_id']}",
            "flag":    f"/api/hitl/walker/decision  body: action=flag    item_id={item['_id']}",
            "suggest": f"/api/hitl/walker/decision  body: action=suggest item_id={item['_id']} note=<text>",
            "skip":    f"/api/hitl/walker/decision  body: action=skip    item_id={item['_id']}",
            "snooze":  f"/api/hitl/walker/decision  body: action=snooze  item_id={item['_id']}",
        },
    }

    if item["_kind"] == "provenance_trail":
        enriched["title"] = f"{item.get('command_module','?')}.{item.get('command_function','?')}"
        enriched["summary"] = (
            f"Command returned a result from {item.get('source_kind','?')} source: "
            f"{item.get('source_hint','?')}"
        )
        enriched["status"] = item.get("hitl_status", "pending")
    elif item["_kind"] == "gfo_augmentation":
        enriched["title"] = f"Chat refusal: {item.get('action','?')} → {item.get('target','?')[:40]}"
        if item.get("finding_ok"):
            enriched["summary"] = f"Murphy refused, then successfully went and looked."
            enriched["status"] = "resolved"
        else:
            enriched["summary"] = (f"Murphy refused, tried to look but: "
                                   f"{item.get('finding_reason','unknown')}")
            enriched["status"] = "needs_review"
    return enriched


def get_next(reviewer_id: str, kinds: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Serve the NEXT review item for this reviewer (chronologically next after
    their cursor). Returns None if nothing pending.
    """
    cursor = _get_cursor(reviewer_id)
    items = _list_eligible_items(cursor["last_item_ts"], limit=5)
    if kinds:
        items = [i for i in items if i["_kind"] in kinds]
    if not items:
        return None
    return _enrich_item(items[0])


def record_decision(reviewer_id: str, item_id: str, action: str,
                    note: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply reviewer's decision on an item. Advances cursor. Returns next item.
    """
    if action not in ("verify", "flag", "suggest", "skip", "snooze"):
        return {"ok": False, "error": f"unknown action: {action}"}

    _ensure_cursor_table()
    decision_id = uuid.uuid4().hex[:16]
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        conn.execute(
            "INSERT INTO walker_decisions (decision_id, reviewer_id, item_id, action, note) "
            "VALUES (?,?,?,?,?)",
            (decision_id, reviewer_id, item_id, action, note or "")
        )
        conn.commit()
    finally:
        conn.close()

    # If action is flag/suggest + item is a provenance trail → open the
    # R64 feedback ticket
    if action in ("flag", "suggest") and not item_id.startswith("gfo_"):
        try:
            from src.hitl_provenance import open_feedback_ticket
            correction_data = {"reviewer_note": note} if note else None
            open_feedback_ticket(item_id, note or f"Reviewer flagged as {action}",
                                 correction_data=correction_data)
        except Exception as e:
            logger.warning(f"feedback ticket failed: {e}")

    # Look up item timestamp to advance cursor
    item_ts = ""
    if item_id.startswith("gfo_"):
        event_id = item_id.replace("gfo_", "")
        c = sqlite3.connect("/var/lib/murphy-production/murphy_audit.db", timeout=2)
        try:
            r = c.execute("SELECT ts FROM gfo_augmentations WHERE event_id = ?", (event_id,)).fetchone()
            if r: item_ts = r[0]
        finally:
            c.close()
    else:
        c = sqlite3.connect(_WALKER_DB, timeout=2)
        try:
            r = c.execute("SELECT captured_at FROM provenance_trails WHERE trail_id = ?", (item_id,)).fetchone()
            if r: item_ts = r[0]
        finally:
            c.close()

    _advance_cursor(reviewer_id, item_id, item_ts or datetime.now(timezone.utc).isoformat(),
                    action=action)
    return {
        "ok": True,
        "decision_id": decision_id,
        "action": action,
        "advanced_to": item_ts,
        "next_item": get_next(reviewer_id),
    }


def get_progress(reviewer_id: str) -> Dict[str, Any]:
    """Reviewer progress summary."""
    cursor = _get_cursor(reviewer_id)
    pending = _list_eligible_items(cursor["last_item_ts"], limit=1000)
    return {
        "reviewer_id":    reviewer_id,
        "items_reviewed": cursor.get("items_reviewed", 0),
        "items_flagged":  cursor.get("items_flagged", 0),
        "items_skipped":  cursor.get("items_skipped", 0),
        "remaining":      len(pending),
        "cursor_at":      cursor.get("last_item_ts"),
        "last_active":    cursor.get("last_active_at"),
    }


def rewind(reviewer_id: str, items: int = 1) -> Dict[str, Any]:
    """
    Move cursor backward N items. Useful for revisiting a recent decision.
    """
    conn = sqlite3.connect(_WALKER_DB, timeout=3)
    try:
        # Find the cursor's current position, then find Nth-most-recent decision before
        conn.row_factory = sqlite3.Row
        # Get the decision N back
        decisions = conn.execute(
            "SELECT * FROM walker_decisions WHERE reviewer_id = ? "
            "ORDER BY decided_at DESC LIMIT ?", (reviewer_id, items + 1)
        ).fetchall()
        if not decisions or len(decisions) <= items:
            # Rewind all the way to start
            new_ts = "1970-01-01T00:00:00Z"
        else:
            new_ts = decisions[items]["decided_at"]
        conn.execute(
            "UPDATE walker_cursors SET last_item_ts = ?, last_active_at = CURRENT_TIMESTAMP "
            "WHERE reviewer_id = ?", (new_ts, reviewer_id)
        )
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "rewound_to_ts": new_ts, "next_item": get_next(reviewer_id)}


if __name__ == "__main__":
    print("── R74 walker smoke ──\n")
    REV = "smoke_reviewer_r74"
    p0 = get_progress(REV)
    print(f"  Initial progress: reviewed={p0['items_reviewed']}, remaining={p0['remaining']}")

    nxt = get_next(REV)
    if nxt:
        print(f"\n  Next item:")
        print(f"    item_id:   {nxt['item_id']}")
        print(f"    kind:      {nxt['kind']}")
        print(f"    timestamp: {nxt['timestamp']}")
        print(f"    title:     {nxt['title']}")
        print(f"    summary:   {nxt['summary']}")
        print(f"    status:    {nxt['status']}")
        print(f"    actions:   {list(nxt['actions'].keys())}")
    else:
        print("  No items pending")

    if nxt:
        print(f"\n  ── Record skip decision ──")
        r = record_decision(REV, nxt["item_id"], "skip")
        print(f"  ok: {r['ok']}, advanced_to: {r['advanced_to']}, has_next: {bool(r.get('next_item'))}")
        if r.get("next_item"):
            print(f"  next title: {r['next_item']['title']}")

    print(f"\n  ── Progress after one skip ──")
    p1 = get_progress(REV)
    print(f"  reviewed={p1['items_reviewed']}, skipped={p1['items_skipped']}, remaining={p1['remaining']}")

    print(f"\n  ── Verify decision on a real item ──")
    nxt2 = get_next(REV)
    if nxt2:
        r2 = record_decision(REV, nxt2["item_id"], "verify", note="looks correct")
        print(f"  ok={r2['ok']}, action=verify")
        p2 = get_progress(REV)
        print(f"  reviewed={p2['items_reviewed']}, flagged={p2['items_flagged']}")
