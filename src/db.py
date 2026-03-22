# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Database module for Murphy System.

Provides synchronous SQLAlchemy engine, session factory, and FastAPI dependency
for relational persistence alongside the existing JSON-based PersistenceManager.

Reads DATABASE_URL from env (default: sqlite:///murphy_logs.db).
"""

import logging
import os

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    sessionmaker,
)
from sqlalchemy.orm import (
    Session as SyncSession,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    os.environ.get("MURPHY_DB_URL", "sqlite:///murphy_logs.db"),
)

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Shared declarative base for all Murphy ORM models."""
    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class SessionRecord(Base):
    """Persistent session state."""
    __tablename__ = "sessions"

    session_id = Column(String(128), primary_key=True)
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LivingDocumentRecord(Base):
    """Living Document persistence."""
    __tablename__ = "living_documents"

    doc_id = Column(String(128), primary_key=True)
    state = Column(String(32), default="DRAFT")
    confidence = Column(Float, default=0.0)
    content = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ExecutionRecord(Base):
    """Task execution audit trail."""
    __tablename__ = "execution_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), ForeignKey("sessions.session_id"), nullable=True)
    task_type = Column(String(64), default="general")
    status = Column(String(32), default="pending")
    latency_ms = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditTrail(Base):
    """System-wide audit log."""
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False)
    actor = Column(String(128), default="system")
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HITLIntervention(Base):
    """Human-in-the-loop intervention records."""
    __tablename__ = "hitl_interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(32), default="pending")
    response = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Communication Hub ORM Models
# ---------------------------------------------------------------------------


class IMThread(Base):
    """Persistent IM thread record."""
    __tablename__ = "comms_im_threads"

    id = Column(String(32), primary_key=True)
    name = Column(String(256), default="")
    type = Column(String(32), default="direct")
    participants = Column(JSON, default=list)
    created = Column(String(64), default="")


class IMMessage(Base):
    """Persistent IM message record."""
    __tablename__ = "comms_im_messages"

    id = Column(String(32), primary_key=True)
    thread_id = Column(String(32), nullable=False)
    sender = Column(String(256), nullable=False)
    content = Column(Text, default="")
    attachments = Column(JSON, default=list)
    created = Column(String(64), default="")
    edited = Column(String(64), nullable=True)
    reactions = Column(JSON, default=dict)
    automod = Column(JSON, default=dict)


class CallSession(Base):
    """Persistent voice/video call session record."""
    __tablename__ = "comms_call_sessions"

    id = Column(String(32), primary_key=True)
    type = Column(String(16), default="voice")
    caller = Column(String(256), nullable=False)
    participants = Column(JSON, default=list)
    state = Column(String(32), default="ringing")
    created = Column(String(64), default="")
    answered_at = Column(String(64), nullable=True)
    ended_at = Column(String(64), nullable=True)
    sdp_offer = Column(Text, nullable=True)
    sdp_answer = Column(Text, nullable=True)
    ice_candidates = Column(JSON, default=list)
    duration_seconds = Column(Integer, nullable=True)
    recording_url = Column(String(512), nullable=True)
    voicemail_url = Column(String(512), nullable=True)


class EmailRecord(Base):
    """Persistent email record."""
    __tablename__ = "comms_emails"

    id = Column(String(32), primary_key=True)
    sender = Column(String(256), nullable=False)
    recipients = Column(JSON, default=list)
    cc = Column(JSON, default=list)
    bcc = Column(JSON, default=list)
    subject = Column(String(512), default="")
    body = Column(Text, default="")
    attachments = Column(JSON, default=list)
    priority = Column(String(32), default="normal")
    thread_id = Column(String(32), nullable=True)
    created = Column(String(64), default="")
    read_by = Column(JSON, default=list)
    status = Column(String(32), default="sent")
    automod = Column(JSON, default=dict)


class CommsAutomationRule(Base):
    """Persistent automation rule for the comms hub."""
    __tablename__ = "comms_automation_rules"

    id = Column(String(32), primary_key=True)
    name = Column(String(256), default="")
    trigger = Column(String(64), default="")
    channel = Column(String(64), default="*")
    action = Column(String(64), default="")
    conditions = Column(JSON, default=dict)
    action_params = Column(JSON, default=dict)
    enabled = Column(Integer, default=1)
    created_by = Column(String(256), default="system")
    created = Column(String(64), default="")
    last_fired = Column(String(64), nullable=True)
    fire_count = Column(Integer, default=0)


class CommsModAuditLog(Base):
    """Moderator audit log entry."""
    __tablename__ = "comms_mod_audit"

    id = Column(String(32), primary_key=True)
    actor = Column(String(256), nullable=False)
    action = Column(String(64), nullable=False)
    target = Column(String(256), nullable=False)
    reason = Column(String(512), default="")
    details = Column(JSON, default=dict)
    timestamp = Column(String(64), default="")


class CommsBroadcast(Base):
    """Persistent broadcast record."""
    __tablename__ = "comms_broadcasts"

    id = Column(String(32), primary_key=True)
    sender = Column(String(256), nullable=False)
    message = Column(Text, default="")
    subject = Column(String(512), nullable=True)
    priority = Column(String(32), default="normal")
    platforms = Column(JSON, default=list)
    results = Column(JSON, default=dict)
    created = Column(String(64), default="")


class CommsUserProfile(Base):
    """Moderator-managed user profile."""
    __tablename__ = "comms_user_profiles"

    user = Column(String(256), primary_key=True)
    role = Column(String(64), default="member")
    muted = Column(Integer, default=0)
    banned = Column(Integer, default=0)
    warnings = Column(Integer, default=0)


# ---------------------------------------------------------------------------
# Meetings, Shadow, Avatar, and Dispatch ORM Models
# ---------------------------------------------------------------------------


class MeetingSession(Base):
    __tablename__ = "meeting_sessions"
    session_id = Column(String(32), primary_key=True)
    title = Column(String(512), default="Untitled Meeting")
    account_id = Column(String(256), nullable=True)
    participants = Column(JSON, default=list)
    im_thread_id = Column(String(32), nullable=True)
    started_at = Column(String(64), default="")
    ended_at = Column(String(64), nullable=True)
    status = Column(String(32), default="active")
    metadata_ = Column("metadata", JSON, default=dict)


class MeetingTranscriptEntry(Base):
    __tablename__ = "meeting_transcript"
    id = Column(String(32), primary_key=True)
    session_id = Column(String(32), nullable=False, index=True)
    speaker = Column(String(256), nullable=False)
    text = Column(Text, default="")
    timestamp = Column(String(64), default="")
    is_ai = Column(Integer, default=0)


class ShadowAgentCommsLog(Base):
    __tablename__ = "shadow_agent_comms_log"
    id = Column(String(32), primary_key=True)
    agent_id = Column(String(256), nullable=False)
    action = Column(String(64), nullable=False)
    content = Column(Text, default="")
    primary_account = Column(String(256), nullable=True)
    cc_accounts = Column(JSON, default=list)
    im_thread_id = Column(String(32), nullable=True)
    email_ids = Column(JSON, default=list)
    timestamp = Column(String(64), default="")


class AvatarCommsLog(Base):
    __tablename__ = "avatar_comms_log"
    id = Column(String(32), primary_key=True)
    avatar_id = Column(String(256), nullable=False)
    user_id = Column(String(256), nullable=False)
    session_id = Column(String(256), nullable=True)
    channel = Column(String(32), default="im")
    content = Column(Text, default="")
    im_thread_id = Column(String(32), nullable=True)
    email_id = Column(String(32), nullable=True)
    shadow_agent_id = Column(String(256), nullable=True)
    org_node_id = Column(String(256), nullable=True)
    rosetta_translated = Column(Integer, default=0)
    timestamp = Column(String(64), default="")


class DispatchLog(Base):
    __tablename__ = "dispatch_log"
    id = Column(String(32), primary_key=True)
    tool_name = Column(String(256), nullable=False, index=True)
    caller_id = Column(String(256), nullable=True)
    caller_type = Column(String(64), default="agent")
    args = Column(JSON, default=dict)
    result_ok = Column(Integer, default=1)
    result_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    timestamp = Column(String(64), default="")


# ---------------------------------------------------------------------------
# Engine & Session Factory (synchronous — works with SQLite out of the box)
# ---------------------------------------------------------------------------

_engine = None
_SessionFactory = None


def _get_engine():
    """Lazily create the SQLAlchemy engine.

    For SQLite the ``check_same_thread`` connect arg is applied automatically.
    For PostgreSQL (or other backends), connection-pool settings are tuned for
    production use.
    """
    global _engine
    if _engine is None:
        url = DATABASE_URL
        kwargs: dict = {"echo": False}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # Production pool settings for PostgreSQL / other RDBMS
            kwargs.update(
                pool_size=int(os.environ.get("MURPHY_DB_POOL_SIZE", "5")),
                max_overflow=int(os.environ.get("MURPHY_DB_MAX_OVERFLOW", "10")),
                pool_pre_ping=True,
            )
        _engine = create_engine(url, **kwargs)
    return _engine


def _get_session_factory():
    """Lazily create the session factory."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=_get_engine())
    return _SessionFactory


def get_db():
    """
    FastAPI dependency that yields a database session.

    Usage::

        @app.get("/example")
        def example(db: SyncSession = Depends(get_db)):
            ...
    """
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all ORM tables if they do not exist."""
    engine = _get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables ensured (url=%s)", DATABASE_URL)


def check_database() -> str:
    """
    Health check: attempt SELECT 1 against the database.

    Returns 'ok' on success, 'error' on failure.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        return "error"
