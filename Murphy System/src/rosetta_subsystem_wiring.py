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
from typing import Any, Callable, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)

_SYSTEM_AGENT_ID = "system"
_DEFAULT_AGENT_ID = _SYSTEM_AGENT_ID  # alias used by connect_* methods

# Module-level EventType cache — populated lazily by connect_event_backbone()
_EventType: Optional[Any] = None


def _load_event_type() -> Optional[Any]:
    """Import and cache EventType from the event_backbone module."""
    global _EventType
    if _EventType is not None:
        return _EventType
    for mod_name in ("src.event_backbone", "event_backbone"):
        try:
            mod = __import__(mod_name, fromlist=["EventType"])
            _EventType = mod.EventType
            return _EventType
        except (ImportError, AttributeError):
            pass
    return None


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
        self._mgr = rosetta_manager  # alias for connect_* methods
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

    # ------------------------------------------------------------------
    # P3-001 (monkey-patch variant)
    # ------------------------------------------------------------------

    def connect_self_improvement(self, engine: Any) -> None:
        """Patch *engine* so each ``record_outcome()`` call also syncs the
        extracted improvement patterns into the Rosetta state.

        Args:
            engine: A ``SelfImprovementEngine`` instance.
        """
        original_record = engine.record_outcome
        mgr = self._mgr

        def _patched_record_outcome(outcome: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_record(outcome, *args, **kwargs)
            try:
                patterns = engine.extract_patterns()
                agent_id = getattr(outcome, "agent_id", None) or _DEFAULT_AGENT_ID
                proposals = [
                    {
                        "proposal_id": f"pat-{uuid.uuid4().hex[:8]}",
                        "title": str(p.get("pattern", p)) if isinstance(p, dict) else str(p),
                        "description": str(p),
                        "category": "self_improvement",
                        "status": "proposed",
                    }
                    for p in patterns
                ]
                _safe_update_proposals(mgr, agent_id, proposals)
            except Exception as exc:
                logger.warning("P3-001 Rosetta side-effect failed: %s", exc)
            return result

        engine.record_outcome = _patched_record_outcome
        logger.info("P3-001: SelfImprovementEngine wired to RosettaManager")

    # ------------------------------------------------------------------
    # P3-002 (monkey-patch variant)
    # ------------------------------------------------------------------

    def connect_automation_orchestrator(self, orchestrator: Any) -> None:
        """Patch *orchestrator* so each ``complete_cycle()`` call also pushes
        a summary into the Rosetta state.

        Args:
            orchestrator: A ``SelfAutomationOrchestrator`` instance.
        """
        original_complete = orchestrator.complete_cycle
        mgr = self._mgr

        def _patched_complete_cycle(*args: Any, **kwargs: Any) -> Any:
            cycle = original_complete(*args, **kwargs)
            if cycle is not None:
                try:
                    all_cycles = orchestrator.get_cycle_history()
                    completed_count = sum(
                        1 for c in all_cycles
                        if getattr(c, "completed_at", None) is not None
                    )
                    progress_entry = {
                        "category": "self_automation",
                        "total_items": len(all_cycles),
                        "completed_items": completed_count,
                        "coverage_percent": (
                            round(completed_count / len(all_cycles) * 100, 1)
                            if all_cycles else 0.0
                        ),
                        "last_updated": _now_iso(),
                    }
                    _safe_update_automation_progress(mgr, _DEFAULT_AGENT_ID, progress_entry)
                except Exception as exc:
                    logger.warning("P3-002 Rosetta side-effect failed: %s", exc)
            return cycle

        orchestrator.complete_cycle = _patched_complete_cycle
        logger.info("P3-002: SelfAutomationOrchestrator wired to RosettaManager")

    # ------------------------------------------------------------------
    # P3-003 (monkey-patch variant)
    # ------------------------------------------------------------------

    def connect_rag(self, rag: Any) -> None:
        """Patch ``self._mgr.save_state()`` to also call ``rag.ingest_document()``
        after every successful save.

        Args:
            rag: A ``RAGVectorIntegration`` instance.
        """
        original_save = self._mgr.save_state
        mgr = self._mgr

        def _patched_save_state(state: Any, *args: Any, **kwargs: Any) -> Any:
            agent_id = original_save(state, *args, **kwargs)
            try:
                text = _state_to_text(state)
                metadata = {
                    "agent_id": agent_id,
                    "source": "rosetta_state",
                    "updated_at": _now_iso(),
                }
                rag.ingest_document(
                    text=text,
                    title=f"Agent state: {agent_id}",
                    source="rosetta",
                    metadata=metadata,
                )
            except Exception as exc:
                logger.warning("P3-003 Rosetta side-effect failed: %s", exc)
            return agent_id

        mgr.save_state = _patched_save_state
        logger.info("P3-003: RAGVectorIntegration wired to RosettaManager.save_state()")

    # ------------------------------------------------------------------
    # P3-004 (monkey-patch variant)
    # ------------------------------------------------------------------

    def connect_event_backbone(
        self,
        backbone: Any,
        *,
        _event_type_cls: Optional[Any] = None,
    ) -> None:
        """Subscribe to TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED events.

        Args:
            backbone: An ``EventBackbone`` instance.
            _event_type_cls: Optional ``EventType`` override for testing.
        """
        EventType = _event_type_cls or _load_event_type()
        if EventType is None:
            logger.warning("P3-004: EventType not importable; skipping backbone wiring")
            return

        mgr = self._mgr

        def _status_for_event(event_type_value: str) -> str:
            if "failed" in event_type_value.lower():
                return "error"
            return "active"

        def _make_handler(evt_label: str) -> Callable[[Any], None]:
            def _handler(event: Any) -> None:
                try:
                    payload: Dict[str, Any] = getattr(event, "payload", {}) or {}
                    agent_id = payload.get("agent_id") or _DEFAULT_AGENT_ID
                    status = _status_for_event(evt_label)
                    _safe_update_system_state(mgr, agent_id, status)
                except Exception as exc:
                    logger.warning("P3-004 %s handler failed: %s", evt_label, exc)
            return _handler

        for attr, label in (
            ("TASK_COMPLETED", "TASK_COMPLETED"),
            ("TASK_FAILED", "TASK_FAILED"),
            ("GATE_EVALUATED", "GATE_EVALUATED"),
        ):
            evt = getattr(EventType, attr, None)
            if evt is not None:
                try:
                    sub_id = backbone.subscribe(evt, _make_handler(label))
                    self._subscription_ids.append(sub_id)
                except Exception as exc:
                    logger.warning("P3-004: failed to subscribe to %s: %s", label, exc)

        logger.info("P3-004: EventBackbone wired (%d subscriptions)", len(self._subscription_ids))

    # ------------------------------------------------------------------
    # P3-005 (monkey-patch variant)
    # ------------------------------------------------------------------

    def connect_state_manager(self, state_mgr: Any) -> None:
        """Patch *state_mgr* so every ``update_state()`` call also updates Rosetta.

        Args:
            state_mgr: A ``StateManager`` instance.
        """
        original_update = state_mgr.update_state
        mgr = self._mgr

        def _patched_update_state(
            state_id: str,
            variables: Dict[str, Any],
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            result = original_update(state_id, variables, *args, **kwargs)
            if result:
                try:
                    state = state_mgr.get_state(state_id)
                    agent_id = _derive_agent_id(state)
                    new_status = str(variables.get("status", "active"))
                    active_tasks: Optional[int] = variables.get("active_tasks")
                    _safe_update_system_state(mgr, agent_id, new_status, active_tasks=active_tasks)
                except Exception as exc:
                    logger.warning("P3-005 Rosetta side-effect failed: %s", exc)
            return result

        state_mgr.update_state = _patched_update_state
        logger.info("P3-005: StateManager wired to RosettaManager")

    def disconnect_event_backbone(self, backbone: Any) -> None:
        """Unsubscribe all EventBackbone subscriptions created by this wiring.

        Args:
            backbone: The same ``EventBackbone`` passed to connect_event_backbone().
        """
        for sub_id in self._subscription_ids:
            try:
                backbone.unsubscribe(sub_id)
            except Exception as exc:
                logger.debug("Failed to unsubscribe %s: %s", sub_id, exc)
        self._subscription_ids.clear()
        logger.info("P3-004: EventBackbone subscriptions removed")


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


# ---------------------------------------------------------------------------
# Module-level helper functions used by connect_* methods
# ---------------------------------------------------------------------------

def _safe_update_proposals(
    mgr: Any, agent_id: str, proposals: List[Dict[str, Any]]
) -> None:
    """Append *proposals* to the Rosetta state for *agent_id*."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        existing = state.model_dump(mode="json")
        existing_proposals: List[Dict[str, Any]] = existing.get("improvement_proposals", [])
        existing_ids = {p.get("proposal_id") for p in existing_proposals}
        for p in proposals:
            if p.get("proposal_id") not in existing_ids:
                existing_proposals.append(p)
                existing_ids.add(p.get("proposal_id"))
        mgr.update_state(agent_id, {"improvement_proposals": existing_proposals})
    except Exception as exc:
        logger.debug("_safe_update_proposals(%s) suppressed: %s", agent_id, exc)


def _safe_update_automation_progress(
    mgr: Any, agent_id: str, progress_entry: Dict[str, Any]
) -> None:
    """Upsert the automation_progress list in the Rosetta state."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        existing = state.model_dump(mode="json")
        progress_list: List[Dict[str, Any]] = existing.get("automation_progress", [])
        category = progress_entry.get("category", "")
        updated = [p for p in progress_list if p.get("category") != category]
        updated.append(progress_entry)
        mgr.update_state(agent_id, {"automation_progress": updated})
    except Exception as exc:
        logger.debug("_safe_update_automation_progress(%s) suppressed: %s", agent_id, exc)


def _safe_update_system_state(
    mgr: Any,
    agent_id: str,
    status: str,
    *,
    active_tasks: Optional[int] = None,
) -> None:
    """Update system_state.status in the Rosetta state for *agent_id*."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        update: Dict[str, Any] = {"system_state": {"status": status}}
        if active_tasks is not None:
            update["system_state"]["active_tasks"] = int(active_tasks)
        mgr.update_state(agent_id, update)
    except Exception as exc:
        logger.debug("_safe_update_system_state(%s) suppressed: %s", agent_id, exc)


def _safe_update(mgr: Any, agent_id: str, fields: Dict[str, Any]) -> None:
    """Generic helper: call mgr.update_state(agent_id, fields) if state exists."""
    try:
        state = mgr.load_state(agent_id)
        if state is not None:
            mgr.update_state(agent_id, fields)
    except Exception as exc:
        logger.debug("_safe_update(%s) suppressed: %s", agent_id, exc)


def _state_to_text(state: Any) -> str:
    """Convert a Rosetta agent state to a plain-text summary."""
    try:
        identity = state.identity
        agent_state = state.agent_state
        lines = [
            f"Agent: {identity.agent_id}",
            f"Role: {identity.role}",
            f"Goals: {', '.join(str(g) for g in agent_state.active_goals)}",
            f"Tasks: {', '.join(str(t) for t in agent_state.task_queue)}",
        ]
        return "\n".join(lines)
    except Exception:
        try:
            return str(state.model_dump(mode="json"))
        except Exception:
            return str(state)


def _derive_agent_id(state: Any) -> str:
    """Derive an agent ID from a SystemState object."""
    if state is None:
        return _DEFAULT_AGENT_ID
    name = getattr(state, "state_name", None)
    if name and name not in ("default", ""):
        return name
    return _DEFAULT_AGENT_ID


def _now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
