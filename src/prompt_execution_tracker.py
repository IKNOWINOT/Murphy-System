# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
# prompt_execution_tracker.py
# Design Label: PROMPT-TRACKER-001
#
# Lightweight tracker for Murphy System prompt execution status.
# Records which prompts have been executed, their results, CITL outcomes,
# and documentation sections that need updating ([DOC-UPDATE] tags).
#
# [DOC-UPDATE: ARCHITECTURE_MAP.md]

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level in-memory store (thread-safe via _lock)
# ---------------------------------------------------------------------------

_lock = threading.Lock()

# prompt_id -> PromptRecord
_records: Dict[str, "PromptRecord"] = {}

# prompt_id -> list of CITL result dicts
_citl_results: Dict[str, List[Dict[str, Any]]] = {}

# Set of documentation file names that need updating
_pending_doc_updates: set[str] = set()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class PromptRecord:
    """Record of a single prompt execution."""

    def __init__(
        self,
        prompt_id: str,
        completed_at: str,
        results: Dict[str, Any],
    ) -> None:
        """Initialise a PromptRecord.

        Args:
            prompt_id: Identifier matching the prompt filename prefix
                       (e.g. "00_PRIORITY_0_SYSTEM_BOOT").
            completed_at: ISO-8601 timestamp of completion.
            results: Arbitrary dict of results produced by the prompt.
        """
        self.prompt_id = prompt_id
        self.completed_at = completed_at
        self.results = results

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "prompt_id": self.prompt_id,
            "completed_at": self.completed_at,
            "results": self.results,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PromptExecutionTracker:
    """Track Murphy System prompt execution status and documentation updates.

    All methods are thread-safe.  Data is stored in module-level dicts so
    multiple tracker instances share the same state within a process.

    Example usage::

        tracker = PromptExecutionTracker()
        tracker.mark_prompt_complete("00_PRIORITY_0_SYSTEM_BOOT", {
            "boot_healthy": True,
            "doc_updates": ["STATUS.md", "CHANGELOG.md"],
        })
        status = tracker.get_execution_status()
        pending = tracker.get_pending_doc_updates()
    """

    # Canonical set of prompt IDs in execution order
    PROMPT_IDS: List[str] = [
        "00_PRIORITY_0_SYSTEM_BOOT",
        "01_SCAN_AND_AUDIT",
        "02_PRIORITIZE_RED_LINE",
        "03_WIRE_REVENUE_MODULES",
        "04_WIRE_ONBOARDING_MODULES",
        "05_WIRE_QA_AND_GOVERNANCE",
        "06_WIRE_ROI_CALENDAR",
        "07_WIRE_CEO_REPORT_HIERARCHY",
        "08_WIRE_INFERENCE_AND_CITL",
        "09_UI_SIMPLIFICATION_AUDIT",
        "10_REPORT_AND_ITERATE",
    ]

    def mark_prompt_complete(
        self,
        prompt_id: str,
        results: Optional[Dict[str, Any]] = None,
    ) -> PromptRecord:
        """Mark a prompt as complete and record its results.

        Args:
            prompt_id: Canonical prompt identifier (e.g.
                       "00_PRIORITY_0_SYSTEM_BOOT").
            results: Optional dict of results produced by running the prompt.
                     If ``results`` contains a ``"doc_updates"`` key (list of
                     str), those files are added to the pending doc-update set.

        Returns:
            The created :class:`PromptRecord`.

        Raises:
            ValueError: If *prompt_id* is empty.
        """
        if not prompt_id:
            raise ValueError("prompt_id must not be empty")

        results = results or {}
        completed_at = datetime.now(timezone.utc).isoformat()
        record = PromptRecord(
            prompt_id=prompt_id,
            completed_at=completed_at,
            results=results,
        )

        try:
            with _lock:
                _records[prompt_id] = record
                # Harvest [DOC-UPDATE] tags from results
                doc_updates = results.get("doc_updates", [])
                if isinstance(doc_updates, list):
                    _pending_doc_updates.update(str(d) for d in doc_updates)
            logger.info(
                "PROMPT-TRACKER-001: prompt '%s' marked complete at %s",
                prompt_id,
                completed_at,
            )
        except Exception as e:  # PROMPT-TRACKER-ERR-001
            logger.error(
                "PROMPT-TRACKER-ERR-001: failed to record completion for '%s': %s",
                prompt_id,
                e,
            )
            raise

        return record

    def record_citl_result(
        self,
        module: str,
        level: int,
        passed: bool,
        failure_description: str = "",
    ) -> None:
        """Record a CITL pass/fail result for a module.

        Args:
            module: Module name (e.g. "sales_automation").
            level: CITL level (1 = code output, 2 = user output).
            passed: Whether the CITL check passed.
            failure_description: Human-readable description if failed.
        """
        entry = {
            "module": module,
            "level": level,
            "passed": passed,
            "failure_description": failure_description,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with _lock:
                if module not in _citl_results:
                    _citl_results[module] = []
                _citl_results[module].append(entry)
            if not passed:
                logger.warning(
                    "PROMPT-TRACKER-CITL-001: CITL Level %d FAILED for '%s': %s",
                    level,
                    module,
                    failure_description,
                )
            else:
                logger.debug(
                    "PROMPT-TRACKER-001: CITL Level %d passed for '%s'",
                    level,
                    module,
                )
        except Exception as e:  # PROMPT-TRACKER-ERR-002
            logger.error(
                "PROMPT-TRACKER-ERR-002: failed to record CITL result for '%s': %s",
                module,
                e,
            )
            raise

    def get_execution_status(self) -> Dict[str, Any]:
        """Return a snapshot of all prompt execution statuses.

        Returns:
            Dict with keys:

            * ``total_prompts`` – number of canonical prompts
            * ``completed`` – number of prompts marked complete
            * ``pending`` – list of prompt IDs not yet completed
            * ``prompts`` – dict of prompt_id → serialised PromptRecord
            * ``citl_summary`` – module → {pass, fail} counts
        """
        try:
            with _lock:
                completed_ids = set(_records.keys())
                pending = [p for p in self.PROMPT_IDS if p not in completed_ids]
                prompts_snapshot = {
                    pid: rec.to_dict() for pid, rec in _records.items()
                }
                citl_summary: Dict[str, Dict[str, int]] = {}
                for mod, entries in _citl_results.items():
                    pass_count = sum(1 for e in entries if e["passed"])
                    fail_count = len(entries) - pass_count
                    citl_summary[mod] = {"pass": pass_count, "fail": fail_count}

            return {
                "total_prompts": len(self.PROMPT_IDS),
                "completed": len(completed_ids),
                "pending": pending,
                "prompts": prompts_snapshot,
                "citl_summary": citl_summary,
            }
        except Exception as e:  # PROMPT-TRACKER-ERR-003
            logger.error(
                "PROMPT-TRACKER-ERR-003: get_execution_status failed: %s", e
            )
            return {
                "total_prompts": len(self.PROMPT_IDS),
                "completed": 0,
                "pending": list(self.PROMPT_IDS),
                "prompts": {},
                "citl_summary": {},
            }

    def get_pending_doc_updates(self) -> List[str]:
        """Return a sorted list of documentation files that need updating.

        Files are added to the pending set whenever a prompt is marked
        complete with a ``"doc_updates"`` list in its results, or via
        :meth:`add_doc_update`.

        Returns:
            Sorted list of documentation file names/paths.
        """
        try:
            with _lock:
                return sorted(_pending_doc_updates)
        except Exception as e:  # PROMPT-TRACKER-ERR-004
            logger.error(
                "PROMPT-TRACKER-ERR-004: get_pending_doc_updates failed: %s", e
            )
            return []

    def add_doc_update(self, doc_path: str) -> None:
        """Manually add a documentation file to the pending-update set.

        Args:
            doc_path: Path or name of the documentation file
                      (e.g. "CHANGELOG.md").
        """
        if not doc_path:
            return
        try:
            with _lock:
                _pending_doc_updates.add(doc_path)
            logger.debug(
                "PROMPT-TRACKER-001: added doc update: %s", doc_path
            )
        except Exception as e:  # PROMPT-TRACKER-ERR-005
            logger.error(
                "PROMPT-TRACKER-ERR-005: add_doc_update failed: %s", e
            )
            raise

    def resolve_doc_update(self, doc_path: str) -> bool:
        """Remove a documentation file from the pending-update set.

        Args:
            doc_path: Path or name previously added to the pending set.

        Returns:
            ``True`` if the file was present and removed, ``False`` otherwise.
        """
        try:
            with _lock:
                if doc_path in _pending_doc_updates:
                    _pending_doc_updates.discard(doc_path)
                    logger.info(
                        "PROMPT-TRACKER-001: resolved doc update: %s", doc_path
                    )
                    return True
                return False
        except Exception as e:  # PROMPT-TRACKER-ERR-006
            logger.error(
                "PROMPT-TRACKER-ERR-006: resolve_doc_update failed: %s", e
            )
            return False

    def reset(self) -> None:
        """Clear all recorded state.  Intended for testing only.

        .. warning::
            This wipes all prompt records, CITL results, and pending doc
            updates.  Do not call in production code.
        """
        try:
            with _lock:
                _records.clear()
                _citl_results.clear()
                _pending_doc_updates.clear()
            logger.warning(
                "PROMPT-TRACKER-001: tracker state reset (all data cleared)"
            )
        except Exception as e:  # PROMPT-TRACKER-ERR-007
            logger.error(
                "PROMPT-TRACKER-ERR-007: reset failed: %s", e
            )
            raise
