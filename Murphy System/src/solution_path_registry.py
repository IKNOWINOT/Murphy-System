"""
Solution Path Registry — persists solution path alternatives across requests.

Backs the "I found N ways to do this" HITL presentation and feeds outcome data
to :class:`FeedbackIntegrator` to improve future routing.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SolutionPathRegistry:
    """Persists solution path alternatives across process restarts.

    Paths are stored as JSON files under *data_dir*.  Each task maps to a
    single ``<task_id>.json`` file that contains the ordered list of
    :class:`~task_router.SolutionPath` alternatives.

    Outcome data is forwarded to the :class:`~feedback_integrator.FeedbackIntegrator`
    (if provided) so the routing layer can improve over time.

    Usage::

        registry = SolutionPathRegistry(data_dir="data/solution_paths")
        registry.register(task_id, paths)

        # HITL presenter retrieves alternatives:
        alternatives = registry.get_alternatives(task_id)

        # After execution:
        registry.record_outcome(task_id, path_id, success=True, latency_ms=420)
    """

    def __init__(
        self,
        data_dir: str = "data/solution_paths",
        feedback_integrator: Optional[Any] = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._feedback = feedback_integrator
        # In-memory cache: task_id → list of path dicts
        self._cache: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _task_path(self, task_id: str) -> Path:
        return self._data_dir / f"{task_id}.json"

    def _ensure_dir(self) -> None:
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.debug("SolutionPathRegistry: cannot create data_dir: %s", exc)

    def _save(self, task_id: str, paths: List[Dict]) -> None:
        """Write *paths* to disk; silently skip on I/O error."""
        self._ensure_dir()
        try:
            with open(self._task_path(task_id), "w", encoding="utf-8") as fh:
                json.dump(paths, fh, indent=2, default=str)
        except OSError as exc:
            logger.debug("SolutionPathRegistry: save failed for %s: %s", task_id, exc)

    def _load(self, task_id: str) -> List[Dict]:
        """Load *paths* from disk; return empty list on error or missing file."""
        fp = self._task_path(task_id)
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    return data
        except (OSError, json.JSONDecodeError):  # PROD-HARD A2: missing/corrupt registry file — start empty
            logger.warning("Solution-path registry file %s unreadable; starting with empty alternatives", fp, exc_info=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, task_id: str, paths: Any) -> None:
        """Persist the full set of alternatives for *task_id*.

        *paths* may be a list of :class:`~task_router.SolutionPath` instances
        (which have a ``__dict__``) or plain dicts.
        """
        serialised: List[Dict] = []
        for p in paths:
            if hasattr(p, "__dict__"):
                serialised.append({k: v for k, v in p.__dict__.items()})
            elif isinstance(p, dict):
                serialised.append(p)
        self._cache[task_id] = serialised
        self._save(task_id, serialised)
        logger.debug(
            "SolutionPathRegistry: registered %d path(s) for task_id=%s",
            len(serialised),
            task_id,
        )

    def get_alternatives(self, task_id: str) -> List[Dict]:
        """Retrieve all registered alternatives for HITL presentation.

        Returns a list of dicts (serialised :class:`~task_router.SolutionPath`).
        Returns an empty list if the task was never registered.
        """
        if task_id in self._cache:
            return list(self._cache[task_id])
        loaded = self._load(task_id)
        if loaded:
            self._cache[task_id] = loaded
        return list(loaded)

    def get_primary(self, task_id: str) -> Optional[Dict]:
        """Return the highest-scored path (first in sorted list).

        Paths are assumed to be ordered descending by score at registration
        time (which :class:`~task_router.TaskRouter._rank_paths` guarantees).
        """
        alts = self.get_alternatives(task_id)
        return alts[0] if alts else None

    def get_fallback(self, task_id: str, failed_path_id: str) -> Optional[Dict]:
        """Return the next-best alternative after *failed_path_id* failed."""
        alts = self.get_alternatives(task_id)
        remaining = [p for p in alts if p.get("path_id") != failed_path_id]
        return remaining[0] if remaining else None

    def record_outcome(
        self,
        task_id: str,
        path_id: str,
        success: bool,
        latency_ms: int = 0,
    ) -> None:
        """Record whether *path_id* succeeded or failed.

        Updates the persisted record and forwards a feedback signal to the
        :class:`~feedback_integrator.FeedbackIntegrator` (if configured).
        """
        alts = self.get_alternatives(task_id)
        for p in alts:
            if p.get("path_id") == path_id:
                p["last_outcome_success"] = success
                p["last_outcome_latency_ms"] = latency_ms
                break

        # Persist updated record
        self._cache[task_id] = alts
        self._save(task_id, alts)

        logger.info(
            "SolutionPathRegistry: outcome task_id=%s path_id=%s success=%s latency=%dms",
            task_id,
            path_id,
            success,
            latency_ms,
        )

        # Forward to FeedbackIntegrator
        self._forward_to_feedback(task_id, path_id, success, alts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _forward_to_feedback(
        self,
        task_id: str,
        path_id: str,
        success: bool,
        paths: List[Dict],
    ) -> None:
        """Push outcome to FeedbackIntegrator if one is configured."""
        if self._feedback is None:
            return

        capability_id: Optional[str] = None
        for p in paths:
            if p.get("path_id") == path_id:
                capability_id = p.get("capability_id")
                break

        # Try the richer integrate() API first
        integrate = getattr(self._feedback, "integrate", None)
        if callable(integrate):
            try:
                from state_schema import TypedStateVector  # type: ignore[import]

                signal_cls_holder: Any = None
                try:
                    from feedback_integrator import FeedbackSignal  # type: ignore[import]

                    signal_cls_holder = FeedbackSignal
                except ImportError:
                    pass

                if signal_cls_holder is not None:
                    signal = signal_cls_holder(
                        signal_type="feedback",
                        source_task_id=task_id,
                        original_confidence=1.0 if success else 0.0,
                        corrected_confidence=1.0 if success else 0.0,
                        affected_state_variables=[capability_id or "routing"],
                    )
                    state = TypedStateVector()
                    integrate(signal, state)
                    return
            except Exception as exc:
                logger.debug("SolutionPathRegistry: feedback.integrate failed: %s", exc)

        # Fallback — try a simpler record_outcome() on the feedback integrator
        record = getattr(self._feedback, "record_outcome", None)
        if callable(record):
            try:
                record(capability_id or path_id, success)
            except Exception as exc:
                logger.debug("SolutionPathRegistry: feedback.record_outcome failed: %s", exc)


__all__ = ["SolutionPathRegistry"]
