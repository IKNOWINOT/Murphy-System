"""
Rosetta Subsystem Wiring — INC-07 / P3-001 through P3-005.

Connects five existing Murphy subsystems to the Rosetta state layer:

  P3-001  SelfImprovementEngine.extract_patterns() → improvement_proposals
  P3-002  SelfAutomationOrchestrator cycle records → automation_progress
  P3-003  RAGVectorIntegration.ingest_document() on every save_state()
  P3-004  EventBackbone subscriptions: TASK_COMPLETED / TASK_FAILED /
          GATE_EVALUATED → system_state.status update
  P3-005  StateManager.update_state() delta push → system_state fields

All connections are **non-invasive monkey-patches** applied at runtime.
Each patch is wrapped in a try/except so that Rosetta keeps working even
if a subsystem raises or is unavailable.

Usage::

    from src.rosetta.subsystem_wiring import bootstrap_wiring
    from src.rosetta import RosettaManager

    mgr = RosettaManager()
    bootstrap_wiring(mgr)           # auto-discovers and wires all subsystems

Or selectively::

    wiring = RosettaSubsystemWiring(mgr)
    wiring.connect_self_improvement(engine)
    wiring.connect_automation_orchestrator(orchestrator)
    wiring.connect_rag(rag)
    wiring.connect_event_backbone(backbone)
    wiring.connect_state_manager(state_mgr)

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)

# Sentinel agent ID used when an event doesn't carry a named agent.
_DEFAULT_AGENT_ID = "system"

# Module-level EventType reference — populated lazily on first use by
# connect_event_backbone().  Exposed at module scope so tests can patch it.
_EventType: Optional[Any] = None


def _load_event_type() -> Optional[Any]:
    """Import and cache EventType from the event_backbone module."""
    global _EventType
    if _EventType is not None:
        return _EventType
    for mod_name in ("src.event_backbone", "event_backbone"):
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            _EventType = mod.EventType
            return _EventType
        except (ImportError, AttributeError):
            continue
    return None


class RosettaSubsystemWiring:
    """Wires external Murphy subsystems into ``RosettaManager``.

    All ``connect_*`` methods apply a lightweight non-invasive patch to the
    target object.  The original behaviour is preserved; the Rosetta update
    is appended as a silent side-effect.  Any exception raised inside the
    Rosetta side-effect is caught and logged so that the original call is
    never disrupted.

    Attributes:
        _mgr: The ``RosettaManager`` instance that owns the state documents.
        _subscription_ids: EventBackbone subscription IDs to allow cleanup.
    """

    def __init__(self, mgr: Any) -> None:  # mgr: RosettaManager
        self._mgr = mgr
        self._subscription_ids: List[str] = []

    # ------------------------------------------------------------------
    # P3-001 — SelfImprovementEngine → improvement_proposals in Rosetta
    # ------------------------------------------------------------------

    def connect_self_improvement(self, engine: Any) -> None:
        """Patch *engine* so each ``record_outcome()`` call also syncs the
        extracted improvement patterns into the ``improvement_proposals``
        field of the Rosetta state for the agent specified by the outcome's
        ``agent_id`` attribute (if present).

        Each raw pattern dict is mapped to a minimal ``ImprovementProposal``
        compatible dict that Pydantic will accept when ``update_state()``
        does its deep-merge + re-validate cycle.

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
                logger.debug(
                    "P3-001: pushed %d patterns as proposals to Rosetta agent %s",
                    len(proposals),
                    agent_id,
                )
            except Exception as exc:
                logger.warning("P3-001 Rosetta side-effect failed: %s", exc)
            return result

        engine.record_outcome = _patched_record_outcome
        logger.info("P3-001: SelfImprovementEngine wired to RosettaManager")

    # ------------------------------------------------------------------
    # P3-002 — SelfAutomationOrchestrator cycle records → automation_progress
    # ------------------------------------------------------------------

    def connect_automation_orchestrator(self, orchestrator: Any) -> None:
        """Patch *orchestrator* so each ``complete_cycle()`` call also pushes
        a summary of the completed cycle into the ``automation_progress``
        list in the Rosetta state document for ``system``.

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
                    logger.debug(
                        "P3-002: pushed cycle %s to Rosetta",
                        getattr(cycle, "cycle_id", "?"),
                    )
                except Exception as exc:
                    logger.warning("P3-002 Rosetta side-effect failed: %s", exc)
            return cycle

        orchestrator.complete_cycle = _patched_complete_cycle
        logger.info("P3-002: SelfAutomationOrchestrator wired to RosettaManager")

    # ------------------------------------------------------------------
    # P3-003 — RAGVectorIntegration ingestion on save_state()
    # ------------------------------------------------------------------

    def connect_rag(self, rag: Any) -> None:
        """Patch the ``RosettaManager.save_state()`` method so that every
        successful save also calls ``rag.ingest_document()`` with a text
        rendering of the saved state.

        This is applied to ``self._mgr`` directly (not to the rag object).

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
                logger.debug(
                    "P3-003: ingested Rosetta state for agent %s into RAG",
                    agent_id,
                )
            except Exception as exc:
                logger.warning("P3-003 Rosetta side-effect failed: %s", exc)
            return agent_id

        mgr.save_state = _patched_save_state
        logger.info("P3-003: RAGVectorIntegration wired to RosettaManager.save_state()")

    # ------------------------------------------------------------------
    # P3-004 — EventBackbone subscriptions
    # ------------------------------------------------------------------

    def connect_event_backbone(
        self,
        backbone: Any,
        *,
        _event_type_cls: Optional[Any] = None,
    ) -> None:
        """Subscribe to ``TASK_COMPLETED``, ``TASK_FAILED``, and
        ``GATE_EVALUATED`` events on *backbone*.  Each event triggers a
        lightweight update to the ``system_state.status`` of the Rosetta
        state for the agent named in the event payload.

        Args:
            backbone: An ``EventBackbone`` instance.
            _event_type_cls: Optional override for the ``EventType`` enum
                (used in tests to inject a stub without modifying imports).
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
                    logger.debug(
                        "P3-004: %s → Rosetta agent %s (status=%s)",
                        evt_label,
                        agent_id,
                        status,
                    )
                except Exception as exc:
                    logger.warning("P3-004 %s handler failed: %s", evt_label, exc)
            return _handler

        event_map = {}
        for attr, label in (
            ("TASK_COMPLETED", "TASK_COMPLETED"),
            ("TASK_FAILED", "TASK_FAILED"),
            ("GATE_EVALUATED", "GATE_EVALUATED"),
        ):
            evt = getattr(EventType, attr, None)
            if evt is not None:
                event_map[evt] = label
        for event_type, label in event_map.items():
            try:
                sub_id = backbone.subscribe(event_type, _make_handler(label))
                self._subscription_ids.append(sub_id)
                logger.debug("P3-004: subscribed to %s (id=%s)", label, sub_id)
            except Exception as exc:
                logger.warning("P3-004: failed to subscribe to %s: %s", label, exc)

        logger.info(
            "P3-004: EventBackbone wired (%d subscriptions)",
            len(self._subscription_ids),
        )

    # ------------------------------------------------------------------
    # P3-005 — StateManager delta push → Rosetta document
    # ------------------------------------------------------------------

    def connect_state_manager(self, state_mgr: Any) -> None:
        """Patch *state_mgr* so every ``update_state()`` call also pushes
        a ``system_state.status`` update to the corresponding Rosetta
        document.

        The agent ID is derived from the state's ``state_name``.  If it
        matches an existing Rosetta document, the ``system_state.status``
        is refreshed to ``"active"`` and the ``active_tasks`` counter is
        updated from ``variables.get("active_tasks")``.

        Args:
            state_mgr: An ``execution_engine.state_manager.StateManager``
                instance.
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
                    _safe_update_system_state(
                        mgr,
                        agent_id,
                        new_status,
                        active_tasks=active_tasks,
                    )
                    logger.debug(
                        "P3-005: pushed state delta for %s → Rosetta %s",
                        state_id,
                        agent_id,
                    )
                except Exception as exc:
                    logger.warning("P3-005 Rosetta side-effect failed: %s", exc)
            return result

        state_mgr.update_state = _patched_update_state
        logger.info("P3-005: StateManager wired to RosettaManager")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def disconnect_event_backbone(self, backbone: Any) -> None:
        """Unsubscribe all EventBackbone subscriptions created by this wiring.

        Args:
            backbone: The same ``EventBackbone`` instance passed to
                ``connect_event_backbone()``.
        """
        for sub_id in self._subscription_ids:
            try:
                backbone.unsubscribe(sub_id)
            except Exception as exc:
                logger.debug("Failed to unsubscribe %s: %s", sub_id, exc)
        self._subscription_ids.clear()
        logger.info("P3-004: EventBackbone subscriptions removed")


# ---------------------------------------------------------------------------
# Convenience bootstrap function
# ---------------------------------------------------------------------------


def bootstrap_wiring(rosetta_mgr: Any) -> Optional[RosettaSubsystemWiring]:
    """Auto-discover and wire all available Murphy subsystems.

    This is the single call that the startup sequence invokes.  Each
    subsystem is imported and instantiated with ``except ImportError``
    fallbacks so that a missing optional package never prevents the system
    from starting.

    Args:
        rosetta_mgr: An active ``RosettaManager`` instance.

    Returns:
        The ``RosettaSubsystemWiring`` instance (useful for tests or for
        later ``disconnect_event_backbone()`` calls), or ``None`` if the
        wiring object itself could not be created.
    """
    try:
        wiring = RosettaSubsystemWiring(rosetta_mgr)
    except Exception as exc:
        logger.error("bootstrap_wiring: failed to create wiring object: %s", exc)
        return None

    # --- P3-001: SelfImprovementEngine ---
    try:
        from src.self_improvement_engine import SelfImprovementEngine  # noqa: F401
        engine = SelfImprovementEngine()
        wiring.connect_self_improvement(engine)
    except ImportError:
        try:
            from self_improvement_engine import SelfImprovementEngine  # type: ignore[no-redef]
            engine = SelfImprovementEngine()
            wiring.connect_self_improvement(engine)
        except ImportError:
            logger.info("bootstrap_wiring: SelfImprovementEngine not available; P3-001 skipped")
    except Exception as exc:
        logger.warning("bootstrap_wiring: P3-001 wiring failed: %s", exc)

    # --- P3-002: SelfAutomationOrchestrator ---
    try:
        from src.self_automation_orchestrator import SelfAutomationOrchestrator  # noqa: F401
        orchestrator = SelfAutomationOrchestrator()
        wiring.connect_automation_orchestrator(orchestrator)
    except ImportError:
        try:
            from self_automation_orchestrator import SelfAutomationOrchestrator  # type: ignore[no-redef]
            orchestrator = SelfAutomationOrchestrator()
            wiring.connect_automation_orchestrator(orchestrator)
        except ImportError:
            logger.info("bootstrap_wiring: SelfAutomationOrchestrator not available; P3-002 skipped")
    except Exception as exc:
        logger.warning("bootstrap_wiring: P3-002 wiring failed: %s", exc)

    # --- P3-003: RAGVectorIntegration ---
    try:
        from src.rag_vector_integration import RAGVectorIntegration  # noqa: F401
        rag = RAGVectorIntegration()
        wiring.connect_rag(rag)
    except ImportError:
        try:
            from rag_vector_integration import RAGVectorIntegration  # type: ignore[no-redef]
            rag = RAGVectorIntegration()
            wiring.connect_rag(rag)
        except ImportError:
            logger.info("bootstrap_wiring: RAGVectorIntegration not available; P3-003 skipped")
    except Exception as exc:
        logger.warning("bootstrap_wiring: P3-003 wiring failed: %s", exc)

    # --- P3-004: EventBackbone ---
    try:
        from src.event_backbone import EventBackbone  # noqa: F401
        backbone = EventBackbone()
        wiring.connect_event_backbone(backbone)
    except ImportError:
        try:
            from event_backbone import EventBackbone  # type: ignore[no-redef]
            backbone = EventBackbone()
            wiring.connect_event_backbone(backbone)
        except ImportError:
            logger.info("bootstrap_wiring: EventBackbone not available; P3-004 skipped")
    except Exception as exc:
        logger.warning("bootstrap_wiring: P3-004 wiring failed: %s", exc)

    # --- P3-005: StateManager ---
    try:
        from src.execution_engine.state_manager import StateManager  # noqa: F401
        state_mgr = StateManager()
        wiring.connect_state_manager(state_mgr)
    except ImportError:
        try:
            from execution_engine.state_manager import StateManager  # type: ignore[no-redef]
            state_mgr = StateManager()
            wiring.connect_state_manager(state_mgr)
        except ImportError:
            logger.info("bootstrap_wiring: StateManager not available; P3-005 skipped")
    except Exception as exc:
        logger.warning("bootstrap_wiring: P3-005 wiring failed: %s", exc)

    logger.info("bootstrap_wiring: Rosetta subsystem wiring complete")
    return wiring


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_update_proposals(
    mgr: Any, agent_id: str, proposals: List[Dict[str, Any]]
) -> None:
    """Append *proposals* to the ``improvement_proposals`` list in the
    Rosetta state for *agent_id*.  Skips silently if the agent has no state.
    """
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
        existing["improvement_proposals"] = existing_proposals
        mgr.update_state(agent_id, {"improvement_proposals": existing_proposals})
    except Exception as exc:
        logger.debug("_safe_update_proposals(%s) suppressed: %s", agent_id, exc)


def _safe_update_automation_progress(
    mgr: Any, agent_id: str, progress_entry: Dict[str, Any]
) -> None:
    """Upsert the ``automation_progress`` list in the Rosetta state.

    If an entry with matching ``category`` already exists it is replaced;
    otherwise the new entry is appended.
    """
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
    """Update ``system_state.status`` (and optionally ``active_tasks``) in
    the Rosetta state for *agent_id*.  Skips silently if no state exists.
    """
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
    """Generic helper: call ``mgr.update_state(agent_id, fields)`` if the
    agent state exists; otherwise silently skip.

    This is a low-level helper for callers that already speak the Pydantic
    schema.  For typed sub-operations prefer the ``_safe_update_*`` helpers.
    """
    try:
        state = mgr.load_state(agent_id)
        if state is not None:
            mgr.update_state(agent_id, fields)
    except Exception as exc:
        logger.debug("_safe_update(%s) suppressed: %s", agent_id, exc)


def _state_to_text(state: Any) -> str:
    """Convert a Rosetta agent state object to a plain-text summary
    suitable for ingestion by ``RAGVectorIntegration``.
    """
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
    """Derive an agent ID from a ``SystemState`` object."""
    if state is None:
        return _DEFAULT_AGENT_ID
    name = getattr(state, "state_name", None)
    if name and name not in ("default", ""):
        return name
    return _DEFAULT_AGENT_ID


def _now_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "RosettaSubsystemWiring",
    "bootstrap_wiring",
    "_DEFAULT_AGENT_ID",
    "_safe_update",
    "_safe_update_proposals",
    "_safe_update_automation_progress",
    "_safe_update_system_state",
    "_state_to_text",
    "_derive_agent_id",
    "_now_iso",
]
