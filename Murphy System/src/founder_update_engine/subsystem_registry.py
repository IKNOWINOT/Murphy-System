"""
Founder Update Engine — Subsystem Registry

Design Label: ARCH-007 — Founder Update Engine: Subsystem Registry
Owner: Backend Team
Dependencies:
  - PersistenceManager — durable storage

Central registry of all Murphy subsystems.  Auto-discovers subsystems from
the ``src/`` directory structure, tracks health status, update history, and
pending recommendation counts.

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Read-only analysis: never modifies actual source files

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Health status constants
HEALTH_HEALTHY = "healthy"
HEALTH_DEGRADED = "degraded"
HEALTH_FAILED = "failed"
HEALTH_UNKNOWN = "unknown"

_VALID_HEALTH_STATUSES = {HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_FAILED, HEALTH_UNKNOWN}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SubsystemInfo:
    """Metadata and health state for a single Murphy subsystem.

    Attributes:
        name: Canonical subsystem name (usually the module file stem).
        module_path: Dotted import path or file path to the module.
        version: Current version string (``"unknown"`` if not set).
        health_status: One of: healthy, degraded, failed, unknown.
        last_updated: UTC timestamp of the last applied update.
        last_health_check: UTC timestamp of the last health check.
        dependencies: Names of other subsystems this one depends on.
        pending_recommendations: Count of open recommendations.
        update_history: Ordered list of applied update event dicts.
    """

    name: str
    module_path: str
    version: str = "unknown"
    health_status: str = HEALTH_UNKNOWN
    last_updated: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    pending_recommendations: int = 0
    update_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-friendly dictionary."""
        return {
            "name": self.name,
            "module_path": self.module_path,
            "version": self.version,
            "health_status": self.health_status,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_health_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "dependencies": self.dependencies,
            "pending_recommendations": self.pending_recommendations,
            "update_history": self.update_history,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubsystemInfo":
        """Deserialise from a dictionary."""
        return cls(
            name=data["name"],
            module_path=data.get("module_path", ""),
            version=data.get("version", "unknown"),
            health_status=data.get("health_status", HEALTH_UNKNOWN),
            last_updated=(
                datetime.fromisoformat(data["last_updated"])
                if data.get("last_updated")
                else None
            ),
            last_health_check=(
                datetime.fromisoformat(data["last_health_check"])
                if data.get("last_health_check")
                else None
            ),
            dependencies=data.get("dependencies", []),
            pending_recommendations=data.get("pending_recommendations", 0),
            update_history=data.get("update_history", []),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class SubsystemRegistry:
    """Central registry of all Murphy subsystems with health tracking.

    Design Label: ARCH-007
    Owner: Backend Team

    Auto-discovers subsystems from the ``src/`` directory and tracks health,
    update history, and recommendation state.

    Usage::

        registry = SubsystemRegistry(persistence_manager=pm)
        registry.discover_subsystems()
        registry.update_health_status("self_fix_loop", "healthy")
        info = registry.get_subsystem("self_fix_loop")
    """

    _PERSISTENCE_DOC_KEY = "founder_update_engine_subsystems"

    # Directories and stems to exclude from auto-discovery
    _EXCLUDE_DIRS = {"__pycache__", ".mypy_cache", "node_modules", "billing"}
    _EXCLUDE_STEMS = {"__init__", "conftest", "setup"}

    def __init__(
        self,
        src_root: Optional[str] = None,
        persistence_manager=None,
    ) -> None:
        self._src_root = src_root  # resolved lazily if None
        self._persistence = persistence_manager
        self._subsystems: Dict[str, SubsystemInfo] = {}
        self._lock = threading.Lock()

        self._load_state()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_subsystem(self, info: SubsystemInfo) -> None:
        """Add or update a subsystem entry in the registry.

        Args:
            info: :class:`SubsystemInfo` to register.
        """
        with self._lock:
            self._subsystems[info.name] = info
        logger.debug("SubsystemRegistry: registered %s", info.name)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_subsystems(self) -> List[SubsystemInfo]:
        """Scan ``src/`` and register every top-level Python module found.

        Already-registered subsystems are not overwritten; their health
        state is preserved.

        Returns:
            List of all :class:`SubsystemInfo` objects now in the registry
            (including pre-existing ones).
        """
        src_root = self._resolve_src_root()
        if src_root is None:
            logger.warning("SubsystemRegistry: cannot locate src/ directory; skipping discovery")
            return self.get_all_subsystems()

        discovered: List[SubsystemInfo] = []
        for entry in sorted(Path(src_root).iterdir()):
            if entry.is_file() and entry.suffix == ".py":
                stem = entry.stem
                if stem in self._EXCLUDE_STEMS:
                    continue
                info = SubsystemInfo(name=stem, module_path=str(entry))
                discovered.append(info)
            elif entry.is_dir() and entry.name not in self._EXCLUDE_DIRS:
                init = entry / "__init__.py"
                if init.exists():
                    info = SubsystemInfo(
                        name=entry.name,
                        module_path=str(init),
                    )
                    discovered.append(info)

        with self._lock:
            for info in discovered:
                if info.name not in self._subsystems:
                    self._subsystems[info.name] = info

        self._save_state()
        logger.info("SubsystemRegistry: discovered %d subsystem(s)", len(discovered))
        return self.get_all_subsystems()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_subsystem(self, name: str) -> Optional[SubsystemInfo]:
        """Return the :class:`SubsystemInfo` for *name*, or ``None``."""
        with self._lock:
            return self._subsystems.get(name)

    def get_all_subsystems(self) -> List[SubsystemInfo]:
        """Return all registered subsystem entries."""
        with self._lock:
            return list(self._subsystems.values())

    # ------------------------------------------------------------------
    # Health management
    # ------------------------------------------------------------------

    def update_health_status(self, name: str, status: str) -> None:
        """Update the health status of subsystem *name*.

        Args:
            name: Subsystem name.
            status: One of ``healthy``, ``degraded``, ``failed``, ``unknown``.

        Raises:
            ValueError: If *status* is not a recognised value.
        """
        if status not in _VALID_HEALTH_STATUSES:
            raise ValueError(
                f"Invalid health status {status!r}. Must be one of {_VALID_HEALTH_STATUSES}."
            )
        with self._lock:
            info = self._subsystems.get(name)
            if info is None:
                logger.warning("update_health_status: subsystem %s not found", name)
                return
            info.health_status = status
            info.last_health_check = datetime.now(timezone.utc)
        self._save_state()

    def get_subsystems_needing_attention(self) -> List[SubsystemInfo]:
        """Return subsystems that are degraded, failed, or have pending recs.

        Returns:
            List of :class:`SubsystemInfo` that warrant immediate review.
        """
        with self._lock:
            return [
                s
                for s in self._subsystems.values()
                if s.health_status in (HEALTH_DEGRADED, HEALTH_FAILED)
                or s.pending_recommendations > 0
            ]

    def record_update(self, name: str, update_record: Dict[str, Any]) -> None:
        """Append an update event to the history of subsystem *name*.

        Args:
            name: Subsystem name.
            update_record: Dict describing the update event.
        """
        with self._lock:
            info = self._subsystems.get(name)
            if info is None:
                logger.warning("record_update: subsystem %s not found", name)
                return
            info.update_history.append(update_record)
            info.last_updated = datetime.now(timezone.utc)
        self._save_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> bool:
        """Persist the registry to durable storage.

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        return self._save_state()

    def load_state(self) -> bool:
        """Load the registry from durable storage.

        Returns:
            ``True`` if data was loaded, ``False`` otherwise.
        """
        return self._load_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_src_root(self) -> Optional[str]:
        """Determine the absolute path to ``src/``."""
        if self._src_root is not None:
            return self._src_root if os.path.isdir(self._src_root) else None

        # Walk up from this file to find the repo root containing src/
        here = Path(__file__).resolve()
        for parent in [here.parent.parent, here.parent.parent.parent]:
            candidate = parent / "src"
            if candidate.is_dir():
                return str(candidate)
        return None

    def _save_state(self) -> bool:
        if self._persistence is None:
            return False
        try:
            with self._lock:
                data = {name: info.to_dict() for name, info in self._subsystems.items()}
            self._persistence.save_document(self._PERSISTENCE_DOC_KEY, data)
            return True
        except Exception as exc:
            logger.debug("SubsystemRegistry: failed to save state: %s", exc)
            return False

    def _load_state(self) -> bool:
        if self._persistence is None:
            return False
        try:
            data = self._persistence.load_document(self._PERSISTENCE_DOC_KEY)
            if data:
                with self._lock:
                    for name, info_dict in data.items():
                        try:
                            self._subsystems[name] = SubsystemInfo.from_dict(info_dict)
                        except Exception as exc:
                            logger.debug(
                                "SubsystemRegistry: failed to deserialise %s: %s", name, exc
                            )
                return True
        except Exception as exc:
            logger.debug("SubsystemRegistry: failed to load state: %s", exc)
        return False
