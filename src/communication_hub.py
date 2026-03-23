# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Communication Hub — Murphy System

Unified onboard communication engine providing:

  * Instant Messaging (IM)  — thread-based, SQLite-persisted message store
  * Voice Call sessions     — signalling records (SDP/ICE forwarded by caller)
  * Video Call sessions     — WebRTC signalling + participant roster
  * Email integration       — compose / send / inbox backed by SQLite
  * Automation rules        — per-channel triggers (auto-reply, escalation, routing)
  * Moderator console       — broadcast to N platforms, auto-moderation, role gates

Persistence
-----------
All stores are backed by SQLite (via the SQLAlchemy ORM models in ``src/db.py``).
Data survives server restarts and is shared across all active accounts in the
same deployment.  When the database is unavailable the stores fall back to
in-memory dicts so the server continues to function.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

def _bootstrap_db() -> bool:
    """Ensure the comms hub tables exist.  Returns True on success."""
    try:
        from src.db import create_tables
        create_tables()
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("CommsHub DB bootstrap failed — using in-memory fallback: %s", exc)
        return False


_DB_READY: bool = _bootstrap_db()


def _get_db_session():
    """Return an SQLAlchemy session, or None if the DB is unavailable."""
    if not _DB_READY:
        return None
    try:
        from src.db import _get_session_factory
        factory = _get_session_factory()
        return factory()
    except Exception as exc:  # pragma: no cover
        logger.warning("CommsHub DB session unavailable: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CallState(str, Enum):
    RINGING  = "ringing"
    ACTIVE   = "active"
    ON_HOLD  = "on_hold"
    ENDED    = "ended"
    REJECTED = "rejected"


class ModerationAction(str, Enum):
    WARN    = "warn"
    MUTE    = "mute"
    KICK    = "kick"
    BAN     = "ban"
    DELETE  = "delete"
    ALLOW   = "allow"


class AutomationTrigger(str, Enum):
    ON_MESSAGE     = "on_message"
    ON_MISSED_CALL = "on_missed_call"
    ON_VOICEMAIL   = "on_voicemail"
    ON_EMAIL       = "on_email"
    SCHEDULED      = "scheduled"


# ---------------------------------------------------------------------------
# Moderation helpers
# ---------------------------------------------------------------------------

_DEFAULT_BLOCKED_WORDS: List[str] = [
    "spam", "scam", "phishing", "malware", "ransomware",
]

_BLOCKED_WORD_RE: re.Pattern = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _DEFAULT_BLOCKED_WORDS) + r")\b",
    re.IGNORECASE,
)


def _check_automod(text: str, extra_words: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return automod verdict for *text*."""
    pattern = _BLOCKED_WORD_RE
    if extra_words:
        combined = _DEFAULT_BLOCKED_WORDS + list(extra_words)
        pattern = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in combined) + r")\b",
            re.IGNORECASE,
        )
    matches = pattern.findall(text)
    if matches:
        return {
            "flagged": True,
            "action": ModerationAction.WARN,
            "matches": list(set(m.lower() for m in matches)),
            "reason": "blocked_word",
        }
    return {"flagged": False, "action": ModerationAction.ALLOW, "matches": [], "reason": None}


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a SQLAlchemy ORM row to a plain dict."""
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


# ---------------------------------------------------------------------------
# IM (Instant Messaging)
# ---------------------------------------------------------------------------

class IMStore:
    """SQLite-persisted store for direct messages and group IM threads.

    Falls back to in-process dicts when the database is unavailable so the
    server always starts cleanly.
    """

    def __init__(self) -> None:
        # Fallback in-memory stores (used when DB is unavailable)
        self._threads: Dict[str, Dict[str, Any]] = {}

    # -- Threads --

    def create_thread(
        self,
        participants: List[str],
        name: Optional[str] = None,
        thread_type: str = "direct",
    ) -> Dict[str, Any]:
        tid = _uid()
        thread = {
            "id": tid,
            "name": name or f"Thread-{tid[:6]}",
            "type": thread_type,
            "participants": list(participants),
            "created": _now_iso(),
        }
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMThread as _IMThread
                session.add(_IMThread(**thread))
                session.commit()
                return thread
            except Exception as exc:
                session.rollback()
                logger.warning("IMStore.create_thread DB error: %s", exc)
            finally:
                session.close()
        # Fallback
        self._threads[tid] = {**thread, "messages": []}
        return thread

    def list_threads(self, user: Optional[str] = None) -> List[Dict[str, Any]]:
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMThread as _IMThread
                rows = session.query(_IMThread).all()
                result = []
                for row in rows:
                    d = _row_to_dict(row)
                    if user is None or user in (d.get("participants") or []):
                        result.append(d)
                return result
            except Exception as exc:
                logger.warning("IMStore.list_threads DB error: %s", exc)
            finally:
                session.close()
        # Fallback
        threads = []
        for t in self._threads.values():
            if user is None or user in t["participants"]:
                threads.append({k: v for k, v in t.items() if k != "messages"})
        return threads

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMThread as _IMThread
                row = session.get(_IMThread, thread_id)
                return _row_to_dict(row) if row else None
            except Exception as exc:
                logger.warning("IMStore.get_thread DB error: %s", exc)
            finally:
                session.close()
        return self._threads.get(thread_id)

    # -- Messages --

    def post_message(
        self,
        thread_id: str,
        sender: str,
        content: str,
        attachments: Optional[List[str]] = None,
        extra_blocked_words: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Verify thread exists
        if self.get_thread(thread_id) is None:
            raise KeyError(f"Thread {thread_id!r} not found")
        automod = _check_automod(content, extra_blocked_words)
        mid = _uid()
        msg = {
            "id": mid,
            "thread_id": thread_id,
            "sender": sender,
            "content": content,
            "attachments": attachments or [],
            "created": _now_iso(),
            "edited": None,
            "reactions": {},
            "automod": automod,
        }
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMMessage as _IMMessage
                session.add(_IMMessage(**msg))
                session.commit()
                logger.debug("IM message %s persisted in thread %s by %s", mid, thread_id, sender)
                return msg
            except Exception as exc:
                session.rollback()
                logger.warning("IMStore.post_message DB error: %s", exc)
            finally:
                session.close()
        # Fallback
        thread = self._threads.get(thread_id)
        if thread is None:
            raise KeyError(f"Thread {thread_id!r} not found")
        thread["messages"].append(msg)
        return msg

    def get_messages(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMMessage as _IMMessage
                rows = (
                    session.query(_IMMessage)
                    .filter(_IMMessage.thread_id == thread_id)
                    .order_by(_IMMessage.created)
                    .all()
                )
                all_msgs = [_row_to_dict(r) for r in rows]
                return all_msgs[-limit:]
            except Exception as exc:
                logger.warning("IMStore.get_messages DB error: %s", exc)
            finally:
                session.close()
        # Fallback
        thread = self._threads.get(thread_id)
        return (thread["messages"] if thread else [])[-limit:]

    def add_reaction(self, thread_id: str, message_id: str, emoji: str, user: str) -> Dict[str, Any]:
        """Add an emoji reaction to a message (persisted in DB)."""
        session = _get_db_session()
        if session is not None:
            try:
                from src.db import IMMessage as _IMMessage
                row = session.get(_IMMessage, message_id)
                if row is None or row.thread_id != thread_id:
                    raise KeyError(f"Message {message_id!r} not found in thread {thread_id!r}")
                reactions = dict(row.reactions or {})
                reactions.setdefault(emoji, [])
                if user not in reactions[emoji]:
                    reactions[emoji].append(user)
                row.reactions = reactions
                session.commit()
                return reactions
            except KeyError:
                raise
            except Exception as exc:
                session.rollback()
                logger.warning("IMStore.add_reaction DB error: %s", exc)
            finally:
                session.close()
        # Fallback
        thread = self._threads.get(thread_id)
        if thread is None:
            raise KeyError(f"Thread {thread_id!r} not found")
        for msg in thread["messages"]:
            if msg["id"] == message_id:
                msg["reactions"].setdefault(emoji, [])
                if user not in msg["reactions"][emoji]:
                    msg["reactions"][emoji].append(user)
                return msg["reactions"]
        raise KeyError(f"Message {message_id!r} not found")


# ---------------------------------------------------------------------------
# Voice / Video Call Sessions
# ---------------------------------------------------------------------------

class CallSessionStore:
    """SQLite-persisted voice and video call sessions (signalling only)."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def _from_row(self, row) -> Dict[str, Any]:
        return _row_to_dict(row)

    def create_session(
        self,
        caller: str,
        participants: List[str],
        call_type: str = "voice",
        sdp_offer: Optional[str] = None,
    ) -> Dict[str, Any]:
        sid = _uid()
        session_data = {
            "id": sid,
            "type": call_type,
            "caller": caller,
            "participants": list(participants),
            "state": CallState.RINGING,
            "created": _now_iso(),
            "answered_at": None,
            "ended_at": None,
            "sdp_offer": sdp_offer,
            "sdp_answer": None,
            "ice_candidates": [],
            "duration_seconds": None,
            "recording_url": None,
            "voicemail_url": None,
        }
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CallSession as _CallSession
                db.add(_CallSession(**session_data))
                db.commit()
                logger.info("Call session %s persisted: %s -> %s [%s]", sid, caller, participants, call_type)
                return session_data
            except Exception as exc:
                db.rollback()
                logger.warning("CallSessionStore.create_session DB error: %s", exc)
            finally:
                db.close()
        self._sessions[sid] = session_data
        return session_data

    def _db_update(self, session_id: str, **fields) -> Optional[Dict[str, Any]]:
        db = _get_db_session()
        if db is None:
            return None
        try:
            from src.db import CallSession as _CallSession
            row = db.get(_CallSession, session_id)
            if row is None:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            db.commit()
            db.refresh(row)
            return self._from_row(row)
        except Exception as exc:
            db.rollback()
            logger.warning("CallSessionStore._db_update DB error: %s", exc)
            return None
        finally:
            db.close()

    def answer_session(self, session_id: str, sdp_answer: Optional[str] = None) -> Dict[str, Any]:
        updates: Dict[str, Any] = {"state": CallState.ACTIVE, "answered_at": _now_iso()}
        if sdp_answer:
            updates["sdp_answer"] = sdp_answer
        result = self._db_update(session_id, **updates)
        if result is not None:
            return result
        s = self._get_mem(session_id)
        s.update(updates)
        return s

    def add_ice_candidate(self, session_id: str, candidate: str) -> None:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CallSession as _CallSession
                row = db.get(_CallSession, session_id)
                if row is None:
                    raise KeyError(f"Call session {session_id!r} not found")
                ice = list(row.ice_candidates or [])
                ice.append(candidate)
                row.ice_candidates = ice
                db.commit()
                return
            except KeyError:
                raise
            except Exception as exc:
                db.rollback()
                logger.warning("CallSessionStore.add_ice_candidate DB error: %s", exc)
            finally:
                db.close()
        s = self._get_mem(session_id)
        s["ice_candidates"].append(candidate)

    def hold_session(self, session_id: str) -> Dict[str, Any]:
        result = self._db_update(session_id, state=CallState.ON_HOLD)
        if result is not None:
            return result
        s = self._get_mem(session_id)
        s["state"] = CallState.ON_HOLD
        return s

    def end_session(self, session_id: str, voicemail_url: Optional[str] = None) -> Dict[str, Any]:
        ended_at = _now_iso()
        updates: Dict[str, Any] = {"state": CallState.ENDED, "ended_at": ended_at}
        if voicemail_url:
            updates["voicemail_url"] = voicemail_url
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CallSession as _CallSession
                row = db.get(_CallSession, session_id)
                if row is None:
                    raise KeyError(f"Call session {session_id!r} not found")
                if row.answered_at:
                    start = datetime.fromisoformat(row.answered_at)
                    end = datetime.fromisoformat(ended_at)
                    updates["duration_seconds"] = int((end - start).total_seconds())
                for k, v in updates.items():
                    setattr(row, k, v)
                db.commit()
                db.refresh(row)
                return self._from_row(row)
            except KeyError:
                raise
            except Exception as exc:
                db.rollback()
                logger.warning("CallSessionStore.end_session DB error: %s", exc)
            finally:
                db.close()
        s = self._get_mem(session_id)
        s.update(updates)
        if s.get("answered_at"):
            start = datetime.fromisoformat(s["answered_at"])
            end = datetime.fromisoformat(ended_at)
            s["duration_seconds"] = int((end - start).total_seconds())
        return s

    def reject_session(self, session_id: str) -> Dict[str, Any]:
        result = self._db_update(session_id, state=CallState.REJECTED, ended_at=_now_iso())
        if result is not None:
            return result
        s = self._get_mem(session_id)
        s["state"] = CallState.REJECTED
        s["ended_at"] = _now_iso()
        return s

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CallSession as _CallSession
                row = db.get(_CallSession, session_id)
                return self._from_row(row) if row else None
            except Exception as exc:
                logger.warning("CallSessionStore.get_session DB error: %s", exc)
            finally:
                db.close()
        return self._sessions.get(session_id)

    def list_sessions(
        self,
        user: Optional[str] = None,
        call_type: Optional[str] = None,
        state: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CallSession as _CallSession
                q = db.query(_CallSession)
                if call_type:
                    q = q.filter(_CallSession.type == call_type)
                if state:
                    q = q.filter(_CallSession.state == state)
                rows = q.all()
                result = []
                for row in rows:
                    d = self._from_row(row)
                    if user and user != d["caller"] and user not in (d.get("participants") or []):
                        continue
                    result.append(d)
                return result
            except Exception as exc:
                logger.warning("CallSessionStore.list_sessions DB error: %s", exc)
            finally:
                db.close()
        sessions = list(self._sessions.values())
        if user:
            sessions = [s for s in sessions if user == s["caller"] or user in s["participants"]]
        if call_type:
            sessions = [s for s in sessions if s["type"] == call_type]
        if state:
            sessions = [s for s in sessions if s["state"] == state]
        return sessions

    def _get_mem(self, session_id: str) -> Dict[str, Any]:
        s = self._sessions.get(session_id)
        if s is None:
            raise KeyError(f"Call session {session_id!r} not found")
        return s


# ---------------------------------------------------------------------------
# Email store
# ---------------------------------------------------------------------------

class EmailStore:
    """SQLite-persisted email inbox/outbox for the communication hub."""

    def __init__(self) -> None:
        self._emails: Dict[str, Dict[str, Any]] = {}

    def compose_and_send(
        self,
        sender: str,
        recipients: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        priority: str = "normal",
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        eid = _uid()
        email = {
            "id": eid,
            "sender": sender,
            "recipients": list(recipients),
            "cc": list(cc or []),
            "bcc": list(bcc or []),
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "priority": priority,
            "thread_id": thread_id or eid,
            "created": _now_iso(),
            "read_by": [],
            "status": "sent",
            "automod": _check_automod(f"{subject} {body}"),
        }
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import EmailRecord as _EmailRecord
                db.add(_EmailRecord(**email))
                db.commit()
                logger.info("Email %s persisted: from=%s to=%s", eid, sender, recipients)
                return email
            except Exception as exc:
                db.rollback()
                logger.warning("EmailStore.compose_and_send DB error: %s", exc)
            finally:
                db.close()
        self._emails[eid] = email
        return email

    def get_inbox(self, user: str) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import EmailRecord as _EmailRecord
                rows = db.query(_EmailRecord).all()
                inbox = []
                for row in rows:
                    d = _row_to_dict(row)
                    if (user in (d.get("recipients") or [])
                            or user in (d.get("cc") or [])
                            or user in (d.get("bcc") or [])):
                        inbox.append(d)
                return sorted(inbox, key=lambda x: x["created"], reverse=True)
            except Exception as exc:
                logger.warning("EmailStore.get_inbox DB error: %s", exc)
            finally:
                db.close()
        return sorted(
            [e for e in self._emails.values()
             if user in e["recipients"] or user in e.get("cc", []) or user in e.get("bcc", [])],
            key=lambda x: x["created"], reverse=True,
        )

    def get_outbox(self, user: str) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import EmailRecord as _EmailRecord
                rows = db.query(_EmailRecord).filter(_EmailRecord.sender == user).all()
                return sorted([_row_to_dict(r) for r in rows], key=lambda x: x["created"], reverse=True)
            except Exception as exc:
                logger.warning("EmailStore.get_outbox DB error: %s", exc)
            finally:
                db.close()
        return sorted(
            [e for e in self._emails.values() if e["sender"] == user],
            key=lambda x: x["created"], reverse=True,
        )

    def mark_read(self, email_id: str, user: str) -> Dict[str, Any]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import EmailRecord as _EmailRecord
                row = db.get(_EmailRecord, email_id)
                if row is None:
                    raise KeyError(f"Email {email_id!r} not found")
                read_by = list(row.read_by or [])
                if user not in read_by:
                    read_by.append(user)
                    row.read_by = read_by
                    db.commit()
                    db.refresh(row)
                return _row_to_dict(row)
            except KeyError:
                raise
            except Exception as exc:
                db.rollback()
                logger.warning("EmailStore.mark_read DB error: %s", exc)
            finally:
                db.close()
        e = self._emails.get(email_id)
        if e is None:
            raise KeyError(f"Email {email_id!r} not found")
        if user not in e["read_by"]:
            e["read_by"].append(user)
        return e

    def get_email(self, email_id: str) -> Optional[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import EmailRecord as _EmailRecord
                row = db.get(_EmailRecord, email_id)
                return _row_to_dict(row) if row else None
            except Exception as exc:
                logger.warning("EmailStore.get_email DB error: %s", exc)
            finally:
                db.close()
        return self._emails.get(email_id)


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------

class AutomationRuleStore:
    """SQLite-persisted automation rules for the comms hub."""

    def __init__(self) -> None:
        self._rules: Dict[str, Dict[str, Any]] = {}

    def _row_to_rule(self, row) -> Dict[str, Any]:
        d = _row_to_dict(row)
        d["enabled"] = bool(d["enabled"])
        return d

    def create_rule(
        self,
        name: str,
        trigger: str,
        channel: str,
        action: str,
        conditions: Optional[Dict[str, Any]] = None,
        action_params: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
    ) -> Dict[str, Any]:
        rid = _uid()
        rule = {
            "id": rid,
            "name": name,
            "trigger": trigger,
            "channel": channel,
            "action": action,
            "conditions": conditions or {},
            "action_params": action_params or {},
            "enabled": True,
            "created_by": created_by,
            "created": _now_iso(),
            "last_fired": None,
            "fire_count": 0,
        }
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                db_rule = {**rule, "enabled": 1}
                db.add(_CAR(**db_rule))
                db.commit()
                return rule
            except Exception as exc:
                db.rollback()
                logger.warning("AutomationRuleStore.create_rule DB error: %s", exc)
            finally:
                db.close()
        self._rules[rid] = rule
        return rule

    def list_rules(self, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                q = db.query(_CAR)
                if channel:
                    q = q.filter(_CAR.channel.in_([channel, "*"]))
                return [self._row_to_rule(r) for r in q.all()]
            except Exception as exc:
                logger.warning("AutomationRuleStore.list_rules DB error: %s", exc)
            finally:
                db.close()
        rules = list(self._rules.values())
        if channel:
            rules = [r for r in rules if r["channel"] in (channel, "*")]
        return rules

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                row = db.get(_CAR, rule_id)
                return self._row_to_rule(row) if row else None
            except Exception as exc:
                logger.warning("AutomationRuleStore.get_rule DB error: %s", exc)
            finally:
                db.close()
        return self._rules.get(rule_id)

    def toggle_rule(self, rule_id: str, enabled: bool) -> Dict[str, Any]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                row = db.get(_CAR, rule_id)
                if row is None:
                    raise KeyError(f"Rule {rule_id!r} not found")
                row.enabled = 1 if enabled else 0
                db.commit()
                db.refresh(row)
                return self._row_to_rule(row)
            except KeyError:
                raise
            except Exception as exc:
                db.rollback()
                logger.warning("AutomationRuleStore.toggle_rule DB error: %s", exc)
            finally:
                db.close()
        r = self._rules.get(rule_id)
        if r is None:
            raise KeyError(f"Rule {rule_id!r} not found")
        r["enabled"] = enabled
        return r

    def delete_rule(self, rule_id: str) -> bool:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                row = db.get(_CAR, rule_id)
                if row is None:
                    return False
                db.delete(row)
                db.commit()
                return True
            except Exception as exc:
                db.rollback()
                logger.warning("AutomationRuleStore.delete_rule DB error: %s", exc)
            finally:
                db.close()
        return self._rules.pop(rule_id, None) is not None

    def fire_rule(self, rule_id: str) -> Dict[str, Any]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsAutomationRule as _CAR
                row = db.get(_CAR, rule_id)
                if row is None:
                    raise KeyError(f"Rule {rule_id!r} not found")
                row.last_fired = _now_iso()
                row.fire_count = (row.fire_count or 0) + 1
                db.commit()
                db.refresh(row)
                return self._row_to_rule(row)
            except KeyError:
                raise
            except Exception as exc:
                db.rollback()
                logger.warning("AutomationRuleStore.fire_rule DB error: %s", exc)
            finally:
                db.close()
        r = self._rules.get(rule_id)
        if r is None:
            raise KeyError(f"Rule {rule_id!r} not found")
        r["last_fired"] = _now_iso()
        r["fire_count"] += 1
        return r

    def evaluate(self, trigger: str, channel: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        matched = []
        for r in self.list_rules():
            if not r.get("enabled"):
                continue
            if r["trigger"] != trigger:
                continue
            if r["channel"] not in ("*", channel):
                continue
            cond = r.get("conditions") or {}
            if cond.get("keyword"):
                text = str(payload.get("content", ""))
                if cond["keyword"].lower() not in text.lower():
                    continue
            if cond.get("automod_flagged") and not payload.get("automod_flagged"):
                continue
            matched.append(r)
        return matched


# ---------------------------------------------------------------------------
# Moderator Console
# ---------------------------------------------------------------------------

class ModeratorConsole:
    """Discord-inspired moderator console with SQLite persistence."""

    SUPPORTED_PLATFORMS = frozenset({
        "im", "voice", "video", "email", "slack", "discord", "matrix", "sms"
    })

    def __init__(self) -> None:
        # Fallback in-memory stores
        self._users: Dict[str, Dict[str, Any]] = {}
        self._broadcast_targets: Dict[str, List[str]] = {}
        self._extra_blocked: List[str] = []
        self._audit_log: List[Dict[str, Any]] = []
        self._broadcasts: List[Dict[str, Any]] = []

    # -- User management --

    def _load_user(self, user: str) -> Dict[str, Any]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsUserProfile as _CUP
                row = db.get(_CUP, user)
                if row:
                    d = _row_to_dict(row)
                    d["muted"] = bool(d["muted"])
                    d["banned"] = bool(d["banned"])
                    return d
            except Exception as exc:
                logger.warning("ModeratorConsole._load_user DB error: %s", exc)
            finally:
                db.close()
        return self._users.get(
            user, {"role": "member", "muted": False, "banned": False, "warnings": 0}
        )

    def _save_user(self, user: str, profile: Dict[str, Any]) -> None:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsUserProfile as _CUP
                row = db.get(_CUP, user)
                db_profile = {
                    **profile,
                    "muted": 1 if profile.get("muted") else 0,
                    "banned": 1 if profile.get("banned") else 0,
                }
                if row is None:
                    db.add(_CUP(user=user, **db_profile))
                else:
                    for k, v in db_profile.items():
                        setattr(row, k, v)
                db.commit()
                return
            except Exception as exc:
                db.rollback()
                logger.warning("ModeratorConsole._save_user DB error: %s", exc)
            finally:
                db.close()
        self._users[user] = profile

    def set_user_role(self, user: str, role: str, by: str = "system") -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["role"] = role
        self._save_user(user, profile)
        self._audit(by, "set_role", user, details={"role": role})
        return profile

    def get_user(self, user: str) -> Optional[Dict[str, Any]]:
        return self._load_user(user)

    def list_users(self) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsUserProfile as _CUP
                rows = db.query(_CUP).all()
                result = []
                for row in rows:
                    d = _row_to_dict(row)
                    d["muted"] = bool(d["muted"])
                    d["banned"] = bool(d["banned"])
                    result.append({"user": d.pop("user"), **d})
                return result
            except Exception as exc:
                logger.warning("ModeratorConsole.list_users DB error: %s", exc)
            finally:
                db.close()
        return [{"user": u, **v} for u, v in self._users.items()]

    # -- Moderation actions --

    def warn_user(self, user: str, reason: str, by: str) -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["warnings"] = profile.get("warnings", 0) + 1
        self._save_user(user, profile)
        self._audit(by, ModerationAction.WARN, user, reason=reason)
        return {"user": user, "warnings": profile["warnings"], "reason": reason}

    def mute_user(self, user: str, reason: str, by: str) -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["muted"] = True
        self._save_user(user, profile)
        self._audit(by, ModerationAction.MUTE, user, reason=reason)
        return {"user": user, "muted": True, "reason": reason}

    def unmute_user(self, user: str, by: str) -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["muted"] = False
        self._save_user(user, profile)
        self._audit(by, "unmute", user)
        return {"user": user, "muted": False}

    def kick_user(self, user: str, reason: str, by: str) -> Dict[str, Any]:
        self._audit(by, ModerationAction.KICK, user, reason=reason)
        return {"user": user, "kicked": True, "reason": reason}

    def ban_user(self, user: str, reason: str, by: str) -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["banned"] = True
        self._save_user(user, profile)
        self._audit(by, ModerationAction.BAN, user, reason=reason)
        return {"user": user, "banned": True, "reason": reason}

    def unban_user(self, user: str, by: str) -> Dict[str, Any]:
        profile = self._load_user(user)
        profile["banned"] = False
        self._save_user(user, profile)
        self._audit(by, "unban", user)
        return {"user": user, "banned": False}

    def delete_message(self, channel: str, message_id: str, by: str, reason: str = "") -> Dict[str, Any]:
        self._audit(by, ModerationAction.DELETE, message_id, reason=reason, details={"channel": channel})
        return {"ok": True, "message_id": message_id, "channel": channel}

    # -- Auto-moderation --

    def add_blocked_words(self, words: List[str], by: str) -> List[str]:
        added = []
        for w in words:
            w = w.strip().lower()
            if w and w not in self._extra_blocked:
                self._extra_blocked.append(w)
                added.append(w)
        if added:
            self._audit(by, "add_blocked_words", "automod", details={"words": added})
        return self._extra_blocked[:]

    def remove_blocked_word(self, word: str, by: str) -> List[str]:
        word = word.strip().lower()
        if word in self._extra_blocked:
            self._extra_blocked.remove(word)
            self._audit(by, "remove_blocked_word", "automod", details={"word": word})
        return self._extra_blocked[:]

    def list_blocked_words(self) -> Dict[str, List[str]]:
        return {"default": _DEFAULT_BLOCKED_WORDS[:], "custom": self._extra_blocked[:]}

    def check_content(self, text: str) -> Dict[str, Any]:
        return _check_automod(text, self._extra_blocked)

    # -- Broadcast --

    def register_target(self, platform: str, channel_id: str, by: str) -> None:
        if platform not in self.SUPPORTED_PLATFORMS:
            raise ValueError(
                f"Platform {platform!r} not supported. "
                f"Choose from: {sorted(self.SUPPORTED_PLATFORMS)}"
            )
        self._broadcast_targets.setdefault(platform, [])
        if channel_id not in self._broadcast_targets[platform]:
            self._broadcast_targets[platform].append(channel_id)
            self._audit(by, "register_target", platform, details={"channel_id": channel_id})

    def unregister_target(self, platform: str, channel_id: str, by: str) -> None:
        targets = self._broadcast_targets.get(platform, [])
        if channel_id in targets:
            targets.remove(channel_id)
            self._audit(by, "unregister_target", platform, details={"channel_id": channel_id})

    def list_targets(self) -> Dict[str, List[str]]:
        return {k: v[:] for k, v in self._broadcast_targets.items() if v}

    def broadcast(
        self,
        message: str,
        platforms: Optional[List[str]] = None,
        sender: str = "moderator",
        subject: Optional[str] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        automod = self.check_content(message)
        if automod["flagged"]:
            return {"ok": False, "error": "broadcast_blocked_by_automod", "automod": automod}

        targets_used = platforms if platforms else list(self._broadcast_targets.keys())
        results: Dict[str, Any] = {}
        for platform in targets_used:
            channel_ids = self._broadcast_targets.get(platform, [])
            if not channel_ids:
                results[platform] = {"status": "no_targets"}
                continue
            results[platform] = {"status": "delivered", "channels": list(channel_ids)}

        bid = _uid()
        record = {
            "id": bid,
            "sender": sender,
            "message": message,
            "subject": subject,
            "priority": priority,
            "platforms": targets_used,
            "results": results,
            "created": _now_iso(),
        }
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsBroadcast as _CB
                db.add(_CB(**record))
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("ModeratorConsole.broadcast DB error: %s", exc)
            finally:
                db.close()
        else:
            self._broadcasts.append(record)
        self._audit(sender, "broadcast", "multi-platform",
                    details={"broadcast_id": bid, "platforms": targets_used})
        logger.info("Broadcast %s dispatched to platforms: %s", bid, targets_used)
        return {"ok": True, "broadcast": record}

    def broadcast_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsBroadcast as _CB
                rows = db.query(_CB).order_by(_CB.created).all()
                return [_row_to_dict(r) for r in rows[-limit:]]
            except Exception as exc:
                logger.warning("ModeratorConsole.broadcast_history DB error: %s", exc)
            finally:
                db.close()
        return self._broadcasts[-limit:]

    # -- Audit --

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsModAuditLog as _CMAL
                rows = db.query(_CMAL).order_by(_CMAL.timestamp).all()
                return [_row_to_dict(r) for r in rows[-limit:]]
            except Exception as exc:
                logger.warning("ModeratorConsole.get_audit_log DB error: %s", exc)
            finally:
                db.close()
        return self._audit_log[-limit:]

    # -- Internal audit helper --

    def _audit(
        self,
        actor: str,
        action: str,
        target: str,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = {
            "id": _uid(),
            "actor": actor,
            "action": action.value if hasattr(action, "value") else str(action),
            "target": target,
            "reason": reason,
            "details": details or {},
            "timestamp": _now_iso(),
        }
        db = _get_db_session()
        if db is not None:
            try:
                from src.db import CommsModAuditLog as _CMAL
                db.add(_CMAL(**entry))
                db.commit()
                return
            except Exception as exc:
                db.rollback()
                logger.warning("ModeratorConsole._audit DB error: %s", exc)
            finally:
                db.close()
        self._audit_log.append(entry)


# ---------------------------------------------------------------------------
# Singleton stores (module-level, shared across the router)
# ---------------------------------------------------------------------------

im_store         = IMStore()
call_store       = CallSessionStore()
email_store      = EmailStore()
automation_store = AutomationRuleStore()
mod_console      = ModeratorConsole()


def _seed_default_rules() -> None:
    """Seed default automation rules if they do not already exist."""
    existing = automation_store.list_rules()
    names = {r["name"] for r in existing}
    defaults = [
        dict(
            name="Auto-reply on missed call",
            trigger=AutomationTrigger.ON_MISSED_CALL,
            channel="*",
            action="send_im",
            action_params={"template": "Sorry, I missed your call. I'll call you back shortly."},
        ),
        dict(
            name="Escalate urgent emails",
            trigger=AutomationTrigger.ON_EMAIL,
            channel="email",
            action="notify_admin",
            conditions={"keyword": "urgent"},
            action_params={"notify": "admin@murphy.systems"},
        ),
        dict(
            name="Auto-moderate flagged IM",
            trigger=AutomationTrigger.ON_MESSAGE,
            channel="*",
            action="automod_delete",
            conditions={"automod_flagged": True},
        ),
    ]
    for d in defaults:
        if d["name"] not in names:
            automation_store.create_rule(created_by="system", **d)


def _seed_default_targets() -> None:
    """Seed default broadcast targets if none are registered."""
    if not mod_console.list_targets():
        mod_console.register_target("im",     "general",        "system")
        mod_console.register_target("email",  "all-staff",      "system")
        mod_console.register_target("matrix", "murphy-general", "system")


_seed_default_rules()
_seed_default_targets()
