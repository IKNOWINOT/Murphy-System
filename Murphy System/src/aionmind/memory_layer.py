"""
Layer 5 — Memory Integration Layer (STM / LTM).

Two memory modes:
  * **STM (Short-Term Memory):** active contexts, active workflows, pending
    approvals, current evidence.
  * **LTM (Long-Term Memory):** archived workflows, outcomes, corrections,
    proven templates.

For Murphy 2.0a (embedded) both stores are in-memory dicts; for 2.0b they will
be backed by a persistent store / external service.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryLayer:
    """Unified STM / LTM façade.

    Thread-safe; suitable for in-process use in 2.0a.  The interface is designed
    so that swapping to an external service in 2.0b requires only a new backend
    implementation behind the same API.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # STM — keyed by arbitrary string IDs
        self._stm: Dict[str, Dict[str, Any]] = {}
        # LTM — keyed by arbitrary string IDs
        self._ltm: Dict[str, Dict[str, Any]] = {}

    # ── STM operations ────────────────────────────────────────────

    def store_intermediate_state(
        self, key: str, data: Dict[str, Any]
    ) -> None:
        """Persist an intermediate state into STM."""
        with self._lock:
            self._stm[key] = {
                **data,
                "_stored_at": datetime.now(timezone.utc).isoformat(),
            }
        logger.debug("STM store: %s", key)

    def retrieve_context(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entry from STM."""
        with self._lock:
            return self._stm.get(key)

    def list_stm_keys(self) -> List[str]:
        with self._lock:
            return list(self._stm.keys())

    def delete_stm(self, key: str) -> bool:
        with self._lock:
            return self._stm.pop(key, None) is not None

    # ── LTM operations ────────────────────────────────────────────

    def archive_workflow(
        self, key: str, data: Dict[str, Any]
    ) -> None:
        """Move a workflow / outcome into LTM."""
        with self._lock:
            self._ltm[key] = {
                **data,
                "_archived_at": datetime.now(timezone.utc).isoformat(),
            }
        logger.debug("LTM archive: %s", key)

    def retrieve_archived(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve an entry from LTM."""
        with self._lock:
            return self._ltm.get(key)

    def search_ltm(
        self, *, tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Simple tag-based search over LTM entries."""
        with self._lock:
            if not tags:
                return list(self._ltm.values())
            tag_set = set(tags)
            return [
                v
                for v in self._ltm.values()
                if tag_set & set(v.get("tags", []))
            ]

    def list_ltm_keys(self) -> List[str]:
        with self._lock:
            return list(self._ltm.keys())

    # ── statistics ────────────────────────────────────────────────

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "stm_entries": len(self._stm),
                "ltm_entries": len(self._ltm),
            }
