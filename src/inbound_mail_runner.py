"""
PATCH-INBOUND-R116 (2026-05-29 R116) — inbound mail runner

WHAT THIS IS:
  Wraps inbound_maildir_poller into a callable that:
  - Polls postfix's maildir for cpost@murphy.systems and aliases
  - Persists NEW (unseen) messages to inbound_replies.db
  - Returns summary {new_count, persisted_ids, errors}
  
  Designed for scheduled-automation use (call every 60s).

WHY IT EXISTS:
  R114 found callmehandy@gmail.com sending Murphy → no response.
  Substrate gap was no inbound handler wired.
  R116 closes that gap: inbound mail now LANDS in inbound_replies.db.
  R117 will add intent classification on top.
  R118 will wire autoresponse via R105 send substrate.

DESIGN CHOICE LOCKED R116: scheduled automation (60s poll)
  Murphy meta-Q answered (expected timeout — locked my call).
  Reason: 
    - No new systemd unit (minimize ops surface, R45 rule)
    - Murphy automation infrastructure handles cron-like scheduling
    - Existing pattern: 'Murphy Sales Engine' runs as automation
    - Failure mode: missed polls just delay processing, no data loss
    - Compose-with-existing not parallel-new

PUBLIC SURFACE:
  poll_and_persist(max_messages=50) -> dict
    Returns {ok, new_count, persisted_ids, errors, scanned_at}

DEPENDS ON:
  Postfix maildir at /var/mail/cpost (or virtual mailbox path)
  inbound_replies.db with inbound_replies table
  src.inbound_maildir_poller (the underlying poller)

LAST UPDATED: 2026-05-29 R116
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger("inbound_mail_runner")

_INBOUND_DB = "/var/lib/murphy-production/inbound_replies.db"
_MAILDIR_PATHS = [
    "/var/mail/cpost",
    "/home/cpost/Maildir/new",
    "/var/spool/mail/cpost",
]


def _ensure_inbound_table():
    """inbound_replies.db is shared with outbound-reply tracking; add
    fresh-inbound support if columns missing."""
    conn = sqlite3.connect(_INBOUND_DB, timeout=5)
    # Make sure source_type column exists
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(inbound_replies)").fetchall()]
        if "source_type" not in cols:
            conn.execute(
                "ALTER TABLE inbound_replies ADD COLUMN source_type TEXT "
                "DEFAULT 'reply'"
            )
        conn.commit()
    except Exception as e:
        logger.warning("schema check: {}".format(e))
    conn.close()


def _list_existing_message_ids() -> set:
    """Pull all already-persisted message-ids so we skip them."""
    try:
        conn = sqlite3.connect(_INBOUND_DB, timeout=3)
        # message_id column may not exist; check first
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(inbound_replies)").fetchall()]
        if "message_id" in cols:
            rows = conn.execute(
                "SELECT message_id FROM inbound_replies WHERE message_id IS NOT NULL"
            ).fetchall()
            conn.close()
            return set(r[0] for r in rows if r[0])
        conn.close()
    except Exception:
        pass
    return set()


def _parse_mbox_message(raw: str) -> Dict[str, Any]:
    """Quick header extraction without full email parser."""
    headers = {}
    body_start = raw.find("\n\n")
    header_block = raw[:body_start] if body_start > 0 else raw[:2048]
    for line in header_block.split("\n"):
        if ":" in line and not line.startswith(" ") and not line.startswith("\t"):
            k, _, v = line.partition(":")
            k = k.strip().lower()
            v = v.strip()
            if k in ("from", "to", "subject", "message-id", "date",
                     "reply-to"):
                headers[k] = v
    body_preview = raw[body_start+2:body_start+2+500] if body_start > 0 else ""
    return {
        "from_addr": headers.get("from", ""),
        "to_addr": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "message_id": headers.get("message-id", ""),
        "received_at": headers.get("date", ""),
        "body_preview": body_preview[:500],
        "raw_size": len(raw),
    }


def poll_and_persist(max_messages: int = 50) -> Dict[str, Any]:
    """
    Poll all known maildir paths, persist NEW messages to inbound_replies.db.
    Returns summary dict.
    """
    _ensure_inbound_table()
    existing_ids = _list_existing_message_ids()
    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    persisted = []
    errors = []
    new_count = 0

    for path in _MAILDIR_PATHS:
        if not os.path.exists(path):
            continue
        try:
            if os.path.isfile(path):
                # mbox-format single file
                with open(path, "r", errors="replace") as f:
                    content = f.read()
                # Naive split on "\nFrom " mbox boundary
                msgs = content.split("\nFrom ")
                for raw in msgs[:max_messages]:
                    if not raw.strip():
                        continue
                    parsed = _parse_mbox_message(raw)
                    mid = parsed.get("message_id")
                    if mid and mid in existing_ids:
                        continue
                    # Persist
                    try:
                        conn = sqlite3.connect(_INBOUND_DB, timeout=3)
                        # Use the schema actually present
                        cols = [r[1] for r in conn.execute(
                            "PRAGMA table_info(inbound_replies)").fetchall()]
                        if "source_type" in cols and "message_id" in cols:
                            conn.execute(
                                "INSERT INTO inbound_replies "
                                "(from_addr, to_addr, subject, body_preview, "
                                " received_at, message_id, source_type) "
                                "VALUES (?,?,?,?,?,?,?)",
                                (parsed["from_addr"], parsed["to_addr"],
                                 parsed["subject"], parsed["body_preview"],
                                 parsed["received_at"] or scanned_at,
                                 mid, "fresh_inbound"),
                            )
                            new_count += 1
                            persisted.append(mid or "(no_id)")
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        errors.append("persist: {}".format(str(e)[:120]))
            elif os.path.isdir(path):
                # Maildir-format directory
                for fn in os.listdir(path)[:max_messages]:
                    fp = os.path.join(path, fn)
                    if not os.path.isfile(fp):
                        continue
                    try:
                        with open(fp, "r", errors="replace") as f:
                            raw = f.read()
                        parsed = _parse_mbox_message(raw)
                        mid = parsed.get("message_id")
                        if mid and mid in existing_ids:
                            continue
                        conn = sqlite3.connect(_INBOUND_DB, timeout=3)
                        cols = [r[1] for r in conn.execute(
                            "PRAGMA table_info(inbound_replies)").fetchall()]
                        if "source_type" in cols and "message_id" in cols:
                            conn.execute(
                                "INSERT INTO inbound_replies "
                                "(from_addr, to_addr, subject, body_preview, "
                                " received_at, message_id, source_type) "
                                "VALUES (?,?,?,?,?,?,?)",
                                (parsed["from_addr"], parsed["to_addr"],
                                 parsed["subject"], parsed["body_preview"],
                                 parsed["received_at"] or scanned_at,
                                 mid, "fresh_inbound"),
                            )
                            new_count += 1
                            persisted.append(mid or fn)
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        errors.append("maildir file {}: {}".format(
                            fn, str(e)[:80]))
        except Exception as e:
            errors.append("{}: {}".format(path, str(e)[:120]))

    return {
        "ok": True,
        "new_count": new_count,
        "persisted_ids": persisted[:10],
        "errors": errors[:5],
        "scanned_at": scanned_at,
        "maildir_paths_checked": [p for p in _MAILDIR_PATHS if os.path.exists(p)],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(poll_and_persist(), indent=2, default=str))
