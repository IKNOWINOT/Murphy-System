"""
R403 — universal state-transition labeling library
==================================================

WHAT THIS IS:
  One import everything uses to record state transitions. Backs onto
  /var/lib/murphy-production/event_log.db.

WHY IT EXISTS:
  Founder rule (2026-06-01): "nothing should start stop fail or succeed
  without written information". This module makes compliance trivial.

USAGE:
  from src.r403_event_log import log_transition, log_start, log_succeed, log_fail

  # convenience helpers (most common):
  log_start("r386_auto_approve", reason="timer fired")
  log_succeed("r386_auto_approve", reason="approved 2 drafts", elapsed_ms=140)
  log_fail("r386_auto_approve", code="E_STATE_0030", reason="DB locked")

  # full form:
  log_transition(
      actor="founder",
      subject="scheduler:lead_prospector",
      transition="pause",
      from_state="running",
      to_state="paused",
      reason="manual pause pending product fit",
  )

KNOWN LIMITS:
  - SQLite single-writer (fine for our volume; ~10/sec ceiling)
  - No async variant yet (synchronous only)
  - Caller is responsible for not blowing up the log (we trust the rule, not enforce volume caps)

LAST UPDATED: 2026-06-01 by R403
"""

import sqlite3
import json
import datetime
import os
import sys
import threading
from typing import Optional, Dict, Any

_DB_PATH = os.environ.get(
    "R403_EVENT_LOG_DB",
    "/var/lib/murphy-production/event_log.db"
)
_LOCK = threading.Lock()

# Allowed transition vocabulary — keeps labels consistent.
ALLOWED_TRANSITIONS = {
    "start", "stop", "fail", "succeed",
    "pause", "resume",
    "create", "update", "delete",
    "timeout", "retry", "skip",
    "approve", "reject", "expire", "archive",
    "send", "receive", "bounce",
    "open", "close",  # for circuits, gates
}


def log_transition(
    actor: str,
    subject: str,
    transition: str,
    *,
    from_state: Optional[str] = None,
    to_state: Optional[str] = None,
    reason: Optional[str] = None,
    code: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Record a state transition. Returns True on success, False if it couldn't write.

    NEVER raises — logging must not break the calling code path. Worst case
    we lose a row (and print a stderr warning).
    """
    if transition not in ALLOWED_TRANSITIONS:
        # Log it anyway but flag in metadata — discoverability beats strictness
        metadata = metadata or {}
        metadata["_unknown_transition"] = True

    ts = datetime.datetime.utcnow().isoformat() + "Z"
    md_json = json.dumps(metadata) if metadata else None

    try:
        with _LOCK:
            con = sqlite3.connect(_DB_PATH, timeout=2.0)
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                INSERT INTO state_transitions
                    (ts, actor, subject, transition, from_state, to_state,
                     reason, code, elapsed_ms, correlation_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, actor, subject, transition, from_state, to_state,
                 reason, code, elapsed_ms, correlation_id, md_json),
            )
            con.commit()
            con.close()
        return True
    except Exception as e:
        # Never raise from logging — but DO leave a stderr breadcrumb
        print(f"R403_LOG_ERROR actor={actor} subject={subject} transition={transition} err={e}",
              file=sys.stderr)
        return False


# ── Convenience helpers (the common 80%) ─────────────────────────────────────
def log_start(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="start", **kw)


def log_succeed(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="succeed", **kw)


def log_fail(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="fail", **kw)


def log_stop(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="stop", **kw)


def log_pause(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="pause", **kw)


def log_resume(subject: str, *, actor: str = "auto", **kw) -> bool:
    return log_transition(actor=actor, subject=subject, transition="resume", **kw)


# ── CLI for shell scripts ────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="R403 transition logger CLI")
    ap.add_argument("--actor", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--transition", required=True)
    ap.add_argument("--from-state", default=None)
    ap.add_argument("--to-state", default=None)
    ap.add_argument("--reason", default=None)
    ap.add_argument("--code", default=None)
    ap.add_argument("--elapsed-ms", type=int, default=None)
    ap.add_argument("--correlation-id", default=None)
    ap.add_argument("--metadata", default=None, help="JSON string")
    args = ap.parse_args()

    md = None
    if args.metadata:
        try:
            md = json.loads(args.metadata)
        except Exception:
            md = {"_raw": args.metadata}

    ok = log_transition(
        actor=args.actor,
        subject=args.subject,
        transition=args.transition,
        from_state=args.from_state,
        to_state=args.to_state,
        reason=args.reason,
        code=args.code,
        elapsed_ms=args.elapsed_ms,
        correlation_id=args.correlation_id,
        metadata=md,
    )
    sys.exit(0 if ok else 1)
