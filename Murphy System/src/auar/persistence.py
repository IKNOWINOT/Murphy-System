"""
AUAR Persistence Layer
=======================

Pluggable persistence interface so AUAR state (capability graph, ML
model data, schema mappings, circuit-breaker counters, observability
traces) can survive restarts.

Provides:
  - :class:`StateBackend` — abstract base class.
  - :class:`FileStateBackend` — JSON-file-based reference implementation.

Usage::

    backend = FileStateBackend("/var/lib/auar/state")
    backend.save("graph", graph.get_stats())
    data = backend.load("graph")

Copyright 2024 Inoni LLC – BSL-1.1
"""

import json
import logging
import os
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class StateBackend(ABC):
    """Abstract persistence backend for AUAR state.

    Implementations must be thread-safe.  Keys are dot-separated
    namespaces (e.g. ``graph.capabilities``, ``ml.scores``).
    """

    @abstractmethod
    def save(self, key: str, data: Any) -> None:
        """Persist *data* under *key*.  Must be JSON-serialisable."""

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """Load data previously saved under *key*.

        Returns ``None`` if the key does not exist.
        """

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete the entry for *key*.  Returns ``True`` if it existed."""

    @abstractmethod
    def list_keys(self) -> List[str]:
        """Return all keys currently stored."""

    @abstractmethod
    def flush(self) -> None:
        """Ensure all pending writes are durable (e.g. fsync)."""


# ---------------------------------------------------------------------------
# In-memory backend (testing / ephemeral usage)
# ---------------------------------------------------------------------------

class InMemoryStateBackend(StateBackend):
    """In-memory backend — data is lost on process exit.

    Useful for unit tests or short-lived processes where durability
    is unnecessary.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def save(self, key: str, data: Any) -> None:
        with self._lock:
            self._store[key] = data

    def load(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._store.get(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def list_keys(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def flush(self) -> None:
        pass  # No-op — everything is already in memory.


# ---------------------------------------------------------------------------
# File-based backend
# ---------------------------------------------------------------------------

class FileStateBackend(StateBackend):
    """JSON-file-based persistence backend.

    Each key is stored as a separate ``<key>.json`` file inside
    *base_dir*.  Dots in keys are translated to directory separators
    so that ``graph.capabilities`` becomes ``graph/capabilities.json``.

    Thread-safe via a per-instance lock.  Writes are atomic (write to
    temp then rename) to prevent corruption.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        logger.info("FileStateBackend: %s", self._base)

    def _key_path(self, key: str) -> Path:
        parts = key.replace(".", os.sep)
        return self._base / f"{parts}.json"

    def save(self, key: str, data: Any) -> None:
        path = self._key_path(key)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, default=str, indent=2))
            tmp.rename(path)

    def load(self, key: str) -> Optional[Any]:
        path = self._key_path(key)
        with self._lock:
            if not path.exists():
                return None
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", key, exc)
                return None

    def delete(self, key: str) -> bool:
        path = self._key_path(key)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
            return False

    def list_keys(self) -> List[str]:
        keys: List[str] = []
        with self._lock:
            for p in self._base.rglob("*.json"):
                rel = p.relative_to(self._base).with_suffix("")
                keys.append(str(rel).replace(os.sep, "."))
        return keys

    def flush(self) -> None:
        # Files are written atomically in save(); nothing to flush.
        pass
