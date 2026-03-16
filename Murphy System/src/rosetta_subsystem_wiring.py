# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Rosetta Subsystem Wiring — RSW-001

Closes the six Priority-3 wiring tasks defined in the Rosetta State Management
System implementation checklist (P3-001 through P3-006):

  P3-001  Wire ``SelfImprovementEngine.extract_patterns()`` →
          ``RosettaManager.update_after_task()``
  P3-002  Wire ``SelfAutomationOrchestrator`` cycle records →
          ``automation_progress.workflows[]``
  P3-003  Wire ``RAGVectorIntegration.ingest_document()`` →
          ``RosettaManager.save_agent_doc()``
  P3-004  Wire ``EventBackbone`` subscriptions in RosettaStateManager
          (TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED)
  P3-005  Wire ``StateManager`` sync — push ``SystemState`` delta to the
          Rosetta document on every status change
  P3-006  ``tests/test_rosetta_subsystem_wiring.py``  (implemented separately)

Usage::

    from rosetta_subsystem_wiring import bootstrap_rosetta_wiring
    from rosetta.rosetta_manager import RosettaManager
    from event_backbone import EventBackbone

    rosetta = RosettaManager()
    backbone = EventBackbone()
    wiring = bootstrap_rosetta_wiring(
        rosetta_manager=rosetta,
        backbone=backbone,
        improvement_engine=my_improvement_engine,   # optional
        orchestrator=my_orchestrator,               # optional
        rag=my_rag,                                 # optional
    )

All arguments except ``rosetta_manager`` are optional; the wiring silently
skips any unsupported bridge if the component is not provided.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SYSTEM_AGENT_ID = "system"


class RosettaSubsystemWiring:
    """Bridges the Rosetta State Manager with the rest of the Murphy subsystems.

    Each P3 wiring task is implemented as a dedicated method so the bridges
    can be exercised and tested independently.

    Args:
        rosetta_manager: A ``RosettaManager`` instance.
        backbone: An ``EventBackbone`` instance (optional).
        improvement_engine: A ``SelfImprovementEngine`` instance (optional).
        orchestrator: A ``SelfAutomationOrchestrator`` instance (optional).
        rag: A ``RAGVectorIntegration`` instance (optional).
        agent_id: The agent ID used when writing to the Rosetta document.
            Defaults to ``"system"``.
    """

    def __init__(
        self,
        rosetta_manager: Any,
        backbone: Optional[Any] = None,
        improvement_engine: Optional[Any] = None,
        orchestrator: Optional[Any] = None,
        rag: Optional[Any] = None,
        agent_id: str = _SYSTEM_AGENT_ID,
    ) -> None:
        self._rosetta = rosetta_manager
        self._backbone = backbone
        self._improvement_engine = improvement_engine
        self._orchestrator = orchestrator
        self._rag = rag
        self._agent_id = agent_id
        self._subscription_ids: List[str] = []

    # ------------------------------------------------------------------
    # P3-001  SelfImprovementEngine → RosettaManager.update_after_task()
    # ------------------------------------------------------------------

    def sync_improvement_patterns(self) -> Optional[Any]:
        """P3-001: Extract patterns from SelfImprovementEngine and push to Rosetta.

        Returns:
            Updated ``RosettaAgentState`` or ``None`` if the engine is unavailable.
        """
        if self._improvement_engine is None:
            logger.debug("sync_improvement_patterns: no improvement_engine configured")
            return None

        try:
            patterns: List[Dict[str, Any]] = self._improvement_engine.extract_patterns()
        except Exception as exc:  # noqa: BLE001
            logger.warning("sync_improvement_patterns: extract_patterns failed — %s", exc)
            return None

        return self._rosetta.update_after_task(self._agent_id, patterns)

    # ------------------------------------------------------------------
    # P3-002  SelfAutomationOrchestrator cycles → automation_progress
    # ------------------------------------------------------------------

    def sync_automation_cycles(self) -> Optional[Any]:
        """P3-002: Push SelfAutomationOrchestrator cycle records to Rosetta.

        Reads the orchestrator's cycle history and pushes an ``AutomationProgress``
        entry for the ``"self_improvement"`` category into the Rosetta document.

        Returns:
            Updated ``RosettaAgentState`` or ``None`` if the orchestrator is unavailable.
        """
        if self._orchestrator is None:
            logger.debug("sync_automation_cycles: no orchestrator configured")
            return None

        try:
            cycles = self._orchestrator.get_cycle_history()
        except Exception as exc:  # noqa: BLE001
            logger.warning("sync_automation_cycles: get_cycle_history failed — %s", exc)
            return None

        total = len(cycles)
        completed = sum(
            1 for c in cycles
            if getattr(c, "completed_at", None) is not None
        )

        return self._rosetta.sync_automation_progress(
            agent_id=self._agent_id,
            category="self_improvement",
            completed=completed,
            total=total,
        )

    # ------------------------------------------------------------------
    # P3-003  RAGVectorIntegration.ingest_document() via save_agent_doc()
    # ------------------------------------------------------------------

    def sync_rag_doc(self, content: Optional[str] = None) -> Dict[str, Any]:
        """P3-003: Ingest the current Rosetta agent state into the RAG store.

        Args:
            content: Optional pre-serialised content string. When ``None``, the
                current agent state is serialised automatically.

        Returns:
            Result dict from ``rag.ingest_document()`` or an error dict.
        """
        if self._rag is None:
            logger.debug("sync_rag_doc: no rag configured")
            return {"status": "skipped", "reason": "no rag configured"}

        return self._rosetta.save_agent_doc(
            agent_id=self._agent_id,
            rag=self._rag,
            content=content,
        )

    # ------------------------------------------------------------------
    # P3-004  EventBackbone subscriptions in RosettaStateManager
    # ------------------------------------------------------------------

    def wire_event_subscriptions(self) -> List[str]:
        """P3-004: Subscribe to TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED events.

        Returns:
            List of subscription IDs registered with the EventBackbone.
        """
        if self._backbone is None:
            logger.debug("wire_event_subscriptions: no backbone configured")
            return []

        try:
            from event_backbone import EventType  # lazy import
        except ImportError as exc:
            logger.warning("wire_event_subscriptions: cannot import EventType — %s", exc)
            return []

        handlers = [
            (EventType.TASK_COMPLETED, self._on_task_completed),
            (EventType.TASK_FAILED, self._on_task_failed),
            (EventType.GATE_EVALUATED, self._on_gate_evaluated),
        ]

        for event_type, handler in handlers:
            try:
                sub_id = self._backbone.subscribe(event_type, handler)
                self._subscription_ids.append(sub_id)
                logger.debug(
                    "wire_event_subscriptions: subscribed to %s (id=%s)",
                    event_type.value, sub_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "wire_event_subscriptions: failed to subscribe to %s — %s",
                    event_type.value, exc,
                )

        return list(self._subscription_ids)

    def _on_task_completed(self, event: Any) -> None:
        """Handle TASK_COMPLETED: refresh improvement patterns in Rosetta."""
        try:
            self.sync_improvement_patterns()
        except Exception as exc:  # noqa: BLE001
            logger.debug("_on_task_completed handler error: %s", exc)

    def _on_task_failed(self, event: Any) -> None:
        """Handle TASK_FAILED: refresh improvement patterns to capture failures."""
        try:
            self.sync_improvement_patterns()
        except Exception as exc:  # noqa: BLE001
            logger.debug("_on_task_failed handler error: %s", exc)

    def _on_gate_evaluated(self, event: Any) -> None:
        """Handle GATE_EVALUATED: update system state in Rosetta."""
        try:
            payload: Dict[str, Any] = {}
            if hasattr(event, "payload") and isinstance(event.payload, dict):
                payload = event.payload
            gate_status = payload.get("status", "evaluated")
            self._rosetta.update_state(
                self._agent_id,
                {"system_state": {"status": gate_status}},
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("_on_gate_evaluated handler error: %s", exc)

    # ------------------------------------------------------------------
    # P3-005  StateManager sync — push SystemState delta to Rosetta doc
    # ------------------------------------------------------------------

    def sync_system_state(
        self,
        status: str = "active",
        uptime_seconds: float = 0.0,
        memory_usage_mb: float = 0.0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """P3-005: Push a SystemState snapshot into the Rosetta document.

        Args:
            status: One of ``"idle"``, ``"active"``, ``"paused"``, ``"error"``.
            uptime_seconds: Server uptime in seconds.
            memory_usage_mb: Current memory usage in MB.
            extra: Additional fields merged into ``system_state``.

        Returns:
            Updated ``RosettaAgentState`` or ``None`` on error.
        """
        try:
            from rosetta.rosetta_models import SystemState  # lazy import

            system_state = SystemState(
                status=status,
                uptime_seconds=uptime_seconds,
                memory_usage_mb=memory_usage_mb,
                **(extra or {}),
            )
            return self._rosetta.sync_system_state(self._agent_id, system_state)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sync_system_state failed — %s", exc)
            return None

    # ------------------------------------------------------------------
    # Convenience: wire everything at once
    # ------------------------------------------------------------------

    def wire_all(self) -> Dict[str, Any]:
        """Wire all P3-001–P3-005 bridges in one call.

        Returns a summary dict describing what was wired and the results.
        """
        results: Dict[str, Any] = {
            "agent_id": self._agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # P3-001
        state = self.sync_improvement_patterns()
        results["p3_001_patterns_synced"] = state is not None

        # P3-002
        state = self.sync_automation_cycles()
        results["p3_002_cycles_synced"] = state is not None

        # P3-003
        rag_result = self.sync_rag_doc()
        results["p3_003_rag_doc"] = rag_result.get("status")

        # P3-004
        sub_ids = self.wire_event_subscriptions()
        results["p3_004_subscriptions"] = len(sub_ids)

        # P3-005
        state = self.sync_system_state()
        results["p3_005_system_state"] = state is not None

        logger.info("RosettaSubsystemWiring.wire_all() complete: %s", json.dumps(results))
        return results


def bootstrap_rosetta_wiring(
    rosetta_manager: Any,
    backbone: Optional[Any] = None,
    improvement_engine: Optional[Any] = None,
    orchestrator: Optional[Any] = None,
    rag: Optional[Any] = None,
    agent_id: str = _SYSTEM_AGENT_ID,
) -> "RosettaSubsystemWiring":
    """Create and wire a ``RosettaSubsystemWiring`` instance.

    Instantiates ``RosettaSubsystemWiring`` with the supplied components, calls
    ``wire_all()``, and returns the wired instance so the caller can retain a
    reference for later re-sync calls.

    Args:
        rosetta_manager: Required ``RosettaManager`` instance.
        backbone: Optional ``EventBackbone`` instance.
        improvement_engine: Optional ``SelfImprovementEngine`` instance.
        orchestrator: Optional ``SelfAutomationOrchestrator`` instance.
        rag: Optional ``RAGVectorIntegration`` instance.
        agent_id: Agent ID used for all Rosetta writes. Defaults to ``"system"``.

    Returns:
        A wired ``RosettaSubsystemWiring`` instance.
    """
    wiring = RosettaSubsystemWiring(
        rosetta_manager=rosetta_manager,
        backbone=backbone,
        improvement_engine=improvement_engine,
        orchestrator=orchestrator,
        rag=rag,
        agent_id=agent_id,
    )
    wiring.wire_all()
    logger.info("bootstrap_rosetta_wiring: wiring complete for agent %r", agent_id)
    return wiring
