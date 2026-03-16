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


def get_pool_status() -> dict:
    """Return connection-pool metrics for monitoring and health checks.

    For SQLite (which uses a ``StaticPool`` or ``NullPool``) the pool
    attributes are not available; a minimal dict is returned instead.

    Returns
    -------
    dict
        Keys:

        * ``pool_size``     — configured pool size (0 for SQLite).
        * ``checked_in``    — connections currently idle in the pool.
        * ``checked_out``   — connections currently in use.
        * ``overflow``      — connections opened above ``pool_size``.
        * ``invalid``       — connections that failed a pre-ping.
        * ``url``           — redacted database URL.
    """
    engine = _get_engine()
    pool = engine.pool

    try:
        # QueuePool (PostgreSQL, MySQL, etc.) exposes these attributes
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL,
        }
    except AttributeError:
        # StaticPool / NullPool (SQLite) do not expose these attributes
        return {
            "pool_size": 0,
            "checked_in": 0,
            "checked_out": 0,
            "overflow": 0,
            "invalid": 0,
            "url": DATABASE_URL,
        }
