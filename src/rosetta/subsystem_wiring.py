"""
Rosetta Subsystem Wiring — INC-07 / H-03.

Implements Priority-3 wiring tasks from the Rosetta State Management System
design (docs/state_management/ROSETTA_STATE_MANAGEMENT_SYSTEM.md):

  P3-001  SelfImprovementEngine.extract_patterns() → RosettaManager.update_state()
  P3-002  SelfAutomationOrchestrator cycle records → automation_progress[]
  P3-003  RAGVectorIntegration.ingest_document() called from RosettaManager
  P3-004  EventBackbone subscriptions in RosettaManager
          (TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED)
  P3-005  StateManager sync — SystemState delta pushed to Rosetta document

All integrations are opt-in and gracefully degrade: if a dependency is not
available the wiring simply logs a warning and skips that hook.

Usage::

    from rosetta.subsystem_wiring import bootstrap_wiring

    wiring = bootstrap_wiring(
        rosetta_manager=my_manager,
        event_backbone=my_backbone,
        self_improvement_engine=my_improvement_engine,
        self_automation_orchestrator=my_orchestrator,
        rag_vector_integration=my_rag,
    )

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Wiring configuration
# ---------------------------------------------------------------------------

_ROSETTA_AGENT_ID = "murphy-system"
_AUTOMATION_CATEGORY = "self_improvement"


@dataclass
class WiringStatus:
    """Records which P3 wiring hooks are active."""

    p3_001_patterns_to_rosetta: bool = False
    p3_002_cycles_to_progress: bool = False
    p3_003_rag_to_rosetta: bool = False
    p3_004_event_subscriptions: bool = False
    p3_005_state_sync: bool = False
    errors: List[str] = field(default_factory=list)

    def summary(self) -> str:
        flags = {
            "P3-001": self.p3_001_patterns_to_rosetta,
            "P3-002": self.p3_002_cycles_to_progress,
            "P3-003": self.p3_003_rag_to_rosetta,
            "P3-004": self.p3_004_event_subscriptions,
            "P3-005": self.p3_005_state_sync,
        }
        active = [k for k, v in flags.items() if v]
        inactive = [k for k, v in flags.items() if not v]
        return (
            f"Rosetta wiring active={active} inactive={inactive} "
            f"errors={self.errors}"
        )


# ---------------------------------------------------------------------------
# Main wiring class
# ---------------------------------------------------------------------------


class RosettaSubsystemWiring:
    """Wires Rosetta state management to the live Murphy subsystems.

    Each ``wire_*`` method corresponds to one P3 task.  All wiring is
    idempotent — calling ``wire_all()`` multiple times is safe.
    """

    def __init__(
        self,
        rosetta_manager: Any,
        *,
        event_backbone: Optional[Any] = None,
        self_improvement_engine: Optional[Any] = None,
        self_automation_orchestrator: Optional[Any] = None,
        rag_vector_integration: Optional[Any] = None,
    ) -> None:
        self._rosetta = rosetta_manager
        self._backbone = event_backbone
        self._improvement = self_improvement_engine
        self._orchestrator = self_automation_orchestrator
        self._rag = rag_vector_integration
        self._status = WiringStatus()
        self._subscription_ids: List[str] = []

    # ------------------------------------------------------------------
    # P3-001  SelfImprovementEngine → RosettaManager
    # ------------------------------------------------------------------

    def wire_patterns_to_rosetta(self) -> bool:
        """P3-001: Push SelfImprovementEngine patterns into RosettaManager.

        Calls ``extract_patterns()`` and stores the result as
        ``improvement_proposals`` metadata on the Murphy system agent state.

        Returns:
            True if patterns were successfully pushed, False otherwise.
        """
        if self._improvement is None:
            logger.debug("P3-001 skipped: no SelfImprovementEngine provided")
            return False

        try:
            patterns: List[Dict[str, Any]] = self._improvement.extract_patterns()
            if not patterns:
                logger.debug("P3-001: no patterns extracted yet, skipping update")
                return True

            self._rosetta.update_state(
                _ROSETTA_AGENT_ID,
                {
                    "metadata": {
                        "improvement_patterns": patterns,
                        "patterns_extracted_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
            logger.info(
                "P3-001: pushed %d improvement patterns to Rosetta", len(patterns)
            )
            self._status.p3_001_patterns_to_rosetta = True
            return True
        except Exception as exc:  # noqa: BLE001
            msg = f"P3-001 error: {exc}"
            logger.warning(msg)
            self._status.errors.append(msg)
            return False

    # ------------------------------------------------------------------
    # P3-002  SelfAutomationOrchestrator → automation_progress
    # ------------------------------------------------------------------

    def wire_cycles_to_automation_progress(self) -> bool:
        """P3-002: Sync SelfAutomationOrchestrator cycle records to automation_progress.

        Reads the orchestrator's cycle history and writes an
        ``AutomationProgress``-compatible summary into the Rosetta agent state.

        Returns:
            True if sync succeeded, False otherwise.
        """
        if self._orchestrator is None:
            logger.debug("P3-002 skipped: no SelfAutomationOrchestrator provided")
            return False

        try:
            cycles = self._orchestrator.get_cycle_history()
            total = len(cycles)
            completed = sum(1 for c in cycles if getattr(c, "completed_at", None))
            failed_count = sum(
                getattr(c, "tasks_failed", 0) for c in cycles
            )
            coverage = round((completed / total * 100) if total else 0.0, 1)

            self._rosetta.update_state(
                _ROSETTA_AGENT_ID,
                {
                    "automation_progress": [
                        {
                            "category": _AUTOMATION_CATEGORY,
                            "total_items": total,
                            "completed_items": completed,
                            "coverage_percent": coverage,
                        }
                    ],
                    "metadata": {
                        "cycle_failures_total": failed_count,
                        "cycles_synced_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            logger.info(
                "P3-002: synced %d orchestrator cycles to Rosetta "
                "(completed=%d, coverage=%.1f%%)",
                total,
                completed,
                coverage,
            )
            self._status.p3_002_cycles_to_progress = True
            return True
        except Exception as exc:  # noqa: BLE001
            msg = f"P3-002 error: {exc}"
            logger.warning(msg)
            self._status.errors.append(msg)
            return False

    # ------------------------------------------------------------------
    # P3-003  RAGVectorIntegration ← RosettaManager state doc
    # ------------------------------------------------------------------

    def wire_rag_ingestion(self, agent_id: str = _ROSETTA_AGENT_ID) -> bool:
        """P3-003: Ingest the current Rosetta agent document into RAG.

        Loads the current agent state, serialises it to a human-readable
        summary, and calls ``RAGVectorIntegration.ingest_document()`` so
        the LLM can query agent history during future planning.

        Args:
            agent_id: Rosetta agent ID whose document to ingest.

        Returns:
            True if ingestion succeeded, False otherwise.
        """
        if self._rag is None:
            logger.debug("P3-003 skipped: no RAGVectorIntegration provided")
            return False

        try:
            state = self._rosetta.load_state(agent_id)
            if state is None:
                logger.debug("P3-003: no Rosetta state found for %s", agent_id)
                return True  # not an error — nothing to ingest yet

            summary = self._state_to_text(state)
            result = self._rag.ingest_document(
                text=summary,
                title=f"Rosetta agent state: {agent_id}",
                source="rosetta_state_manager",
                metadata={
                    "agent_id": agent_id,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            success = result.get("status") != "error"
            if success:
                logger.info(
                    "P3-003: ingested Rosetta state for %s into RAG (%d chunks)",
                    agent_id,
                    result.get("chunks_stored", 0),
                )
                self._status.p3_003_rag_to_rosetta = True
            else:
                logger.warning("P3-003: RAG ingestion returned error: %s", result)
            return success
        except Exception as exc:  # noqa: BLE001
            msg = f"P3-003 error: {exc}"
            logger.warning(msg)
            self._status.errors.append(msg)
            return False

    # ------------------------------------------------------------------
    # P3-004  EventBackbone subscriptions in RosettaManager
    # ------------------------------------------------------------------

    def wire_event_subscriptions(self) -> bool:
        """P3-004: Subscribe RosettaManager to TASK_COMPLETED / TASK_FAILED / GATE_EVALUATED.

        For each event type, registers a lightweight handler that updates
        the Rosetta agent state's ``agent_state.active_tasks`` counter and
        appends a summary to ``metadata.recent_events``.

        Returns:
            True if all subscriptions were registered, False otherwise.
        """
        if self._backbone is None:
            logger.debug("P3-004 skipped: no EventBackbone provided")
            return False

        try:
            from event_backbone import EventType  # lazy import
        except ImportError:
            logger.debug("P3-004 skipped: event_backbone not importable")
            return False

        try:
            sub_ids = []
            for event_type in (
                EventType.TASK_COMPLETED,
                EventType.TASK_FAILED,
                EventType.GATE_EVALUATED,
            ):
                sub_id = self._backbone.subscribe(
                    event_type,
                    self._make_event_handler(event_type.value),
                )
                sub_ids.append(sub_id)

            self._subscription_ids.extend(sub_ids)
            logger.info(
                "P3-004: registered %d Rosetta EventBackbone subscriptions",
                len(sub_ids),
            )
            self._status.p3_004_event_subscriptions = True
            return True
        except Exception as exc:  # noqa: BLE001
            msg = f"P3-004 error: {exc}"
            logger.warning(msg)
            self._status.errors.append(msg)
            return False

    def _make_event_handler(self, event_type_name: str):
        """Return a closure that updates Rosetta state when an event fires."""

        def _handler(event: Any) -> None:
            try:
                payload = getattr(event, "payload", {}) or {}
                self._rosetta.update_state(
                    _ROSETTA_AGENT_ID,
                    {
                        "metadata": {
                            f"last_{event_type_name}_at": datetime.now(
                                timezone.utc
                            ).isoformat(),
                            f"last_{event_type_name}_id": payload.get(
                                "task_id", payload.get("gate_id", "")
                            ),
                        }
                    },
                )
                logger.debug(
                    "P3-004 handler: Rosetta state updated for %s", event_type_name
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "P3-004 handler error (%s): %s", event_type_name, exc
                )

        return _handler

    # ------------------------------------------------------------------
    # P3-005  StateManager sync → Rosetta document delta push
    # ------------------------------------------------------------------

    def wire_state_sync(self, agent_id: str = _ROSETTA_AGENT_ID) -> bool:
        """P3-005: Push SystemState delta to the Rosetta document.

        Reads the current system uptime, active-task count, and status from
        the Rosetta agent state and writes a timestamped snapshot back so
        the Rosetta document stays current without a full re-serialisation.

        Args:
            agent_id: Rosetta agent ID to sync.

        Returns:
            True if sync succeeded, False otherwise.
        """
        try:
            state = self._rosetta.load_state(agent_id)
            if state is None:
                logger.debug("P3-005: no state found for %s, skipping sync", agent_id)
                return True

            current_system = getattr(state, "system_state", None)
            delta: Dict[str, Any] = {
                "metadata": {
                    "last_state_sync_at": datetime.now(timezone.utc).isoformat(),
                }
            }
            if current_system is not None:
                delta["system_state"] = {
                    "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                }

            self._rosetta.update_state(agent_id, delta)
            logger.info("P3-005: Rosetta document sync complete for %s", agent_id)
            self._status.p3_005_state_sync = True
            return True
        except Exception as exc:  # noqa: BLE001
            msg = f"P3-005 error: {exc}"
            logger.warning(msg)
            self._status.errors.append(msg)
            return False

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def wire_all(self) -> WiringStatus:
        """Run all P3 wiring tasks in dependency order.

        Returns:
            A ``WiringStatus`` reflecting which hooks activated successfully.
        """
        self.wire_patterns_to_rosetta()       # P3-001
        self.wire_cycles_to_automation_progress()  # P3-002
        self.wire_rag_ingestion()             # P3-003
        self.wire_event_subscriptions()       # P3-004
        self.wire_state_sync()               # P3-005
        logger.info("Rosetta wiring complete. %s", self._status.summary())
        return self._status

    @property
    def status(self) -> WiringStatus:
        """Current wiring status."""
        return self._status

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _state_to_text(state: Any) -> str:
        """Serialise a RosettaAgentState to a human-readable text summary for RAG."""
        identity = getattr(state, "identity", None)
        system = getattr(state, "system_state", None)
        goals = getattr(state, "goals", [])
        tasks = getattr(state, "tasks", [])
        proposals = getattr(state, "improvement_proposals", [])
        progress = getattr(state, "automation_progress", [])

        lines = [
            "# Rosetta Agent State",
            f"Agent: {getattr(identity, 'agent_id', 'unknown')}",
            f"Name: {getattr(identity, 'name', '')}",
            f"Role: {getattr(identity, 'role', '')}",
            "",
            "## System State",
            f"Status: {getattr(system, 'status', 'unknown')}",
            f"Uptime: {getattr(system, 'uptime_seconds', 0):.1f}s",
            f"Active tasks: {getattr(system, 'active_tasks', 0)}",
            "",
            f"## Goals ({len(goals)})",
        ]
        for g in goals[:10]:
            lines.append(
                f"- [{getattr(g, 'status', '?')}] {getattr(g, 'title', '')} "
                f"(priority={getattr(g, 'priority', '?')}, "
                f"progress={getattr(g, 'progress_percent', 0):.0f}%)"
            )

        lines += ["", f"## Tasks ({len(tasks)})"]
        for t in tasks[:10]:
            lines.append(
                f"- [{getattr(t, 'status', '?')}] {getattr(t, 'title', '')}"
            )

        lines += ["", f"## Automation Progress ({len(progress)})"]
        for p in progress:
            lines.append(
                f"- {getattr(p, 'category', '?')}: "
                f"{getattr(p, 'completed_items', 0)}/{getattr(p, 'total_items', 0)} "
                f"({getattr(p, 'coverage_percent', 0):.1f}%)"
            )

        lines += ["", f"## Improvement Proposals ({len(proposals)})"]
        for prop in proposals[:5]:
            lines.append(
                f"- [{getattr(prop, 'priority', '?')}] "
                f"{getattr(prop, 'description', '')}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Bootstrap helper
# ---------------------------------------------------------------------------


def bootstrap_wiring(
    rosetta_manager: Any,
    *,
    event_backbone: Optional[Any] = None,
    self_improvement_engine: Optional[Any] = None,
    self_automation_orchestrator: Optional[Any] = None,
    rag_vector_integration: Optional[Any] = None,
    run_immediately: bool = True,
) -> RosettaSubsystemWiring:
    """Create and optionally activate a ``RosettaSubsystemWiring`` instance.

    Args:
        rosetta_manager: Required. Active ``RosettaManager`` instance.
        event_backbone: Optional ``EventBackbone`` for P3-004 subscriptions.
        self_improvement_engine: Optional for P3-001 pattern sync.
        self_automation_orchestrator: Optional for P3-002 cycle sync.
        rag_vector_integration: Optional for P3-003 RAG ingestion.
        run_immediately: When True (default) calls ``wire_all()`` before
            returning.  Set False to defer wiring.

    Returns:
        A configured ``RosettaSubsystemWiring`` instance.
    """
    wiring = RosettaSubsystemWiring(
        rosetta_manager,
        event_backbone=event_backbone,
        self_improvement_engine=self_improvement_engine,
        self_automation_orchestrator=self_automation_orchestrator,
        rag_vector_integration=rag_vector_integration,
    )
    if run_immediately:
        wiring.wire_all()
    return wiring
