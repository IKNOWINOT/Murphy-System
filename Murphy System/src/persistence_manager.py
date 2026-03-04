"""
PERSISTENCE MANAGER FOR MURPHY SYSTEM
Durable file-based JSON persistence for documents, gate history,
librarian context, audit trails, and replay support.

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
"""

import json
import os
import uuid
import time
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default persistence directory
DEFAULT_PERSISTENCE_DIR = ".murphy_persistence"

# Subdirectory names
DOCUMENTS_DIR = "documents"
GATE_HISTORY_DIR = "gate_history"
LIBRARIAN_DIR = "librarian_context"
AUDIT_DIR = "audit"
ROSETTA_DIR = "rosetta"


@dataclass
class PersistenceEvent:
    """Represents a persisted event with metadata."""
    event_id: str
    event_type: str
    timestamp: float
    session_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PersistenceEvent":
        """Create from dictionary."""
        return cls(
            event_id=d.get("event_id", ""),
            event_type=d.get("event_type", ""),
            timestamp=d.get("timestamp", 0.0),
            session_id=d.get("session_id"),
            data=d.get("data", {}),
        )


class PersistenceManager:
    """
    File-based JSON persistence manager for the Murphy System.

    Provides durable storage for living documents, gate history,
    librarian context, and audit trails with replay support.
    Thread-safe via file locks (threading.Lock per subdirectory).
    """

    def __init__(self, persistence_dir: Optional[str] = None) -> None:
        self._base_dir = Path(
            persistence_dir
            or os.environ.get("MURPHY_PERSISTENCE_DIR", DEFAULT_PERSISTENCE_DIR)
        )
        self._locks: Dict[str, threading.Lock] = {
            DOCUMENTS_DIR: threading.Lock(),
            GATE_HISTORY_DIR: threading.Lock(),
            LIBRARIAN_DIR: threading.Lock(),
            AUDIT_DIR: threading.Lock(),
            ROSETTA_DIR: threading.Lock(),
        }
        self._init_directories()
        logger.info("PersistenceManager initialized at %s", self._base_dir)

    # ==================== Initialization ====================

    def _init_directories(self) -> None:
        """Create persistence subdirectories if they don't exist."""
        for subdir in (DOCUMENTS_DIR, GATE_HISTORY_DIR, LIBRARIAN_DIR, AUDIT_DIR, ROSETTA_DIR):
            path = self._base_dir / subdir
            path.mkdir(parents=True, exist_ok=True)
            logger.debug("Ensured directory: %s", path)

    # ==================== Internal Helpers ====================

    def _write_json(self, filepath: Path, data: Any) -> None:
        """Atomically write JSON data to a file."""
        tmp_path = filepath.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            tmp_path.replace(filepath)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    def _read_json(self, filepath: Path) -> Any:
        """Read JSON data from a file."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def _make_event_id(self) -> str:
        """Generate a unique event ID."""
        return str(uuid.uuid4())

    # ==================== Document Persistence ====================

    def save_document(self, doc_id: str, document: Dict[str, Any]) -> str:
        """
        Save a LivingDocument as JSON.

        Args:
            doc_id: Unique document identifier.
            document: Document data to persist.

        Returns:
            The doc_id used for storage.
        """
        filepath = self._base_dir / DOCUMENTS_DIR / f"{doc_id}.json"
        with self._locks[DOCUMENTS_DIR]:
            self._write_json(filepath, document)
        logger.info("Saved document: %s", doc_id)
        return doc_id

    def load_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a LivingDocument by ID.

        Returns:
            Document dict or None if not found.
        """
        filepath = self._base_dir / DOCUMENTS_DIR / f"{doc_id}.json"
        with self._locks[DOCUMENTS_DIR]:
            if not filepath.exists():
                logger.debug("Document not found: %s", doc_id)
                return None
            try:
                return self._read_json(filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load document %s: %s", doc_id, exc)
                return None

    def list_documents(self) -> List[str]:
        """
        List all stored document IDs.

        Returns:
            List of document ID strings.
        """
        doc_dir = self._base_dir / DOCUMENTS_DIR
        with self._locks[DOCUMENTS_DIR]:
            return sorted(
                p.stem for p in doc_dir.glob("*.json")
            )

    # ==================== Gate History ====================

    def save_gate_event(self, session_id: str, gate_event: Dict[str, Any]) -> str:
        """
        Append a gate decision event for a session.

        Args:
            session_id: Session identifier.
            gate_event: Gate decision data (decision, overrides, etc.).

        Returns:
            The generated event ID.
        """
        event_id = self._make_event_id()
        record = PersistenceEvent(
            event_id=event_id,
            event_type="gate",
            timestamp=time.time(),
            session_id=session_id,
            data=gate_event,
        )
        filepath = self._base_dir / GATE_HISTORY_DIR / f"{session_id}.json"
        with self._locks[GATE_HISTORY_DIR]:
            history: List[Dict[str, Any]] = []
            if filepath.exists():
                try:
                    history = self._read_json(filepath)
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Resetting corrupt gate history for %s: %s", session_id, exc)
            history.append(record.to_dict())
            self._write_json(filepath, history)
        logger.info("Saved gate event %s for session %s", event_id, session_id)
        return event_id

    def get_gate_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all gate events for a session, ordered by timestamp.

        Returns:
            List of gate event dicts, or empty list if none found.
        """
        filepath = self._base_dir / GATE_HISTORY_DIR / f"{session_id}.json"
        with self._locks[GATE_HISTORY_DIR]:
            if not filepath.exists():
                return []
            try:
                history = self._read_json(filepath)
                return sorted(history, key=lambda e: e.get("timestamp", 0))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load gate history for %s: %s", session_id, exc)
                return []

    # ==================== Librarian Context ====================

    def save_librarian_context(self, request_id: str, context: Dict[str, Any]) -> str:
        """
        Save curated librarian context for a request.

        Args:
            request_id: Request identifier.
            context: Curated conditions and context data.

        Returns:
            The request_id used for storage.
        """
        filepath = self._base_dir / LIBRARIAN_DIR / f"{request_id}.json"
        record = {
            "request_id": request_id,
            "timestamp": time.time(),
            "context": context,
        }
        with self._locks[LIBRARIAN_DIR]:
            self._write_json(filepath, record)
        logger.info("Saved librarian context: %s", request_id)
        return request_id

    def load_librarian_context(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Load librarian context by request ID.

        Returns:
            Context dict or None if not found.
        """
        filepath = self._base_dir / LIBRARIAN_DIR / f"{request_id}.json"
        with self._locks[LIBRARIAN_DIR]:
            if not filepath.exists():
                logger.debug("Librarian context not found: %s", request_id)
                return None
            try:
                return self._read_json(filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load librarian context %s: %s", request_id, exc)
                return None

    # ==================== Audit Trail ====================

    def append_audit_event(self, event: Dict[str, Any]) -> str:
        """
        Append an execution event to the audit trail.

        Automatically adds event_id and timestamp if not present.

        Args:
            event: Audit event data (should include session_id for filtering).

        Returns:
            The generated event ID.
        """
        event_id = self._make_event_id()
        record = PersistenceEvent(
            event_id=event_id,
            event_type=event.get("event_type", "audit"),
            timestamp=event.get("timestamp", time.time()),
            session_id=event.get("session_id"),
            data=event,
        )
        filepath = self._base_dir / AUDIT_DIR / "audit_trail.json"
        with self._locks[AUDIT_DIR]:
            trail: List[Dict[str, Any]] = []
            if filepath.exists():
                try:
                    trail = self._read_json(filepath)
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Resetting corrupt audit trail: %s", exc)
            trail.append(record.to_dict())
            self._write_json(filepath, trail)
        logger.info("Appended audit event %s", event_id)
        return event_id

    def get_audit_trail(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail events, optionally filtered by session.

        Args:
            session_id: If provided, filter to this session only.
            limit: Maximum number of events to return (most recent first).

        Returns:
            List of audit event dicts ordered by timestamp descending.
        """
        filepath = self._base_dir / AUDIT_DIR / "audit_trail.json"
        with self._locks[AUDIT_DIR]:
            if not filepath.exists():
                return []
            try:
                trail = self._read_json(filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load audit trail: %s", exc)
                return []

        if session_id is not None:
            trail = [e for e in trail if e.get("session_id") == session_id]

        trail.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
        return trail[:limit]

    # ==================== Replay Support ====================

    def get_replay_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Enumerate all stored events for a session in chronological order.

        Merges gate history and audit trail events for the session.

        Args:
            session_id: Session to replay.

        Returns:
            Chronologically ordered list of all events for the session.
        """
        events: List[Dict[str, Any]] = []

        # Collect gate events
        gate_events = self.get_gate_history(session_id)
        events.extend(gate_events)

        # Collect audit events for the session
        audit_events = self.get_audit_trail(session_id=session_id, limit=10000)
        events.extend(audit_events)

        # Sort chronologically for replay
        events.sort(key=lambda e: e.get("timestamp", 0))
        return events

    # ==================== Rosetta State ====================

    def save_rosetta_state(self, agent_id: str, state: Dict[str, Any]) -> str:
        """Save rosetta agent state."""
        filepath = self._base_dir / ROSETTA_DIR / f"{agent_id}.json"
        with self._locks[ROSETTA_DIR]:
            self._write_json(filepath, state)
        logger.info("Saved rosetta state: %s", agent_id)
        return agent_id

    def load_rosetta_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load rosetta agent state."""
        filepath = self._base_dir / ROSETTA_DIR / f"{agent_id}.json"
        with self._locks[ROSETTA_DIR]:
            if not filepath.exists():
                logger.debug("Rosetta state not found: %s", agent_id)
                return None
            try:
                return self._read_json(filepath)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Failed to load rosetta state %s: %s", agent_id, exc)
                return None

    def list_rosetta_agents(self) -> List[str]:
        """List all rosetta agent IDs."""
        rosetta_dir = self._base_dir / ROSETTA_DIR
        with self._locks[ROSETTA_DIR]:
            return sorted(p.stem for p in rosetta_dir.glob("*.json"))

    # ==================== Status ====================

    def get_status(self) -> Dict[str, Any]:
        """
        Get persistence layer status summary.

        Returns:
            Dict with counts and storage path information.
        """
        doc_count = len(self.list_documents())

        gate_dir = self._base_dir / GATE_HISTORY_DIR
        gate_session_count = len(list(gate_dir.glob("*.json")))

        librarian_dir = self._base_dir / LIBRARIAN_DIR
        librarian_count = len(list(librarian_dir.glob("*.json")))

        audit_filepath = self._base_dir / AUDIT_DIR / "audit_trail.json"
        audit_count = 0
        if audit_filepath.exists():
            try:
                trail = self._read_json(audit_filepath)
                audit_count = len(trail)
            except (json.JSONDecodeError, OSError):
                audit_count = -1

        return {
            "persistence_dir": str(self._base_dir),
            "documents": doc_count,
            "gate_sessions": gate_session_count,
            "librarian_contexts": librarian_count,
            "audit_events": audit_count,
        }
