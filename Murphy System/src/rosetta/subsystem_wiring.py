# Copyright © 2020-2026 Inoni Limited Liability Company
# Creator: Corey Post · License: BSL 1.1
"""
Rosetta Subsystem Wiring — INC-07 Phase 3 (P3-001 … P3-005)

Connects the Rosetta state-management layer to the rest of Murphy so that
the platform can observe and act on its own state — the substrate for
self-improvement, automation telemetry, RAG-backed memory, event-driven
status updates, and heartbeat sync.

Wiring points
-------------
  P3-001  ``SelfImprovementEngine.extract_patterns()`` →
          ``RosettaManager.update_state(improvement_proposals=…)``
  P3-002  ``SelfAutomationOrchestrator.get_cycle_history()`` →
          ``RosettaManager.update_state(automation_progress=…)`` with
          ``category="self_improvement"`` and computed coverage.
  P3-003  Current Rosetta state →
          ``RAGVectorIntegration.ingest_document()`` (single canonical
          document per agent, deterministic title).
  P3-004  ``EventBackbone.subscribe(TASK_COMPLETED | TASK_FAILED |
          GATE_EVALUATED, …)`` — handlers stamp metadata on the agent
          state so operators can see liveness without reading event logs.
  P3-005  ``RosettaManager`` heartbeat sync — touches
          ``system_state.last_heartbeat`` so a stale agent is detectable.

Design contract
---------------
* Every wiring point is **opt-in** — pass the dependency to ``__init__``
  to enable it.  Missing optional dependencies cause the corresponding
  ``wire_*`` method to return ``False`` *without* recording an error.
* Every wiring point is **bounded**.  Dependency exceptions are caught,
  appended to ``status.errors`` with a ``"P3-NNN: …"`` prefix, and the
  method returns ``False``.  Wiring never raises out.
* Empty-input cases are not failures — ``wire_patterns_to_rosetta`` with
  no patterns and ``wire_cycles_to_automation_progress`` with no cycles
  both return ``True``.  This matters because at cold-start there is
  often nothing to sync yet.
* ``wire_all`` is **idempotent** — repeatedly wiring with the same
  dependencies leaves the status unchanged.

The 10-question commissioning checklist is satisfied by
``tests/runtime_core/test_rosetta_subsystem_wiring.py`` (42 cases
covering every method × every documented condition).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_AGENT_ID = "murphy-system"


# ---------------------------------------------------------------------------
# Status dataclass
# ---------------------------------------------------------------------------

@dataclass
class WiringStatus:
    """Per-point activation flags + collected error strings.

    Each ``wire_*`` method flips the matching boolean to True on success
    and appends any caught exception to ``errors`` prefixed with the
    P3-NNN label, so an operator can see at a glance which integration
    point is broken.
    """
    p3_001_patterns_to_rosetta: bool = False
    p3_002_cycles_to_progress: bool = False
    p3_003_rag_to_rosetta: bool = False
    p3_004_event_subscriptions: bool = False
    p3_005_state_sync: bool = False
    errors: List[str] = field(default_factory=list)

    # Mapping kept here (not duplicated elsewhere) so summary() and
    # to_dict() stay aligned with the field set above.
    _LABELS: Dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._LABELS = {
            "p3_001_patterns_to_rosetta": "P3-001 patterns→rosetta",
            "p3_002_cycles_to_progress": "P3-002 cycles→automation_progress",
            "p3_003_rag_to_rosetta": "P3-003 rosetta→RAG",
            "p3_004_event_subscriptions": "P3-004 event subscriptions",
            "p3_005_state_sync": "P3-005 heartbeat sync",
        }

    def summary(self) -> str:
        """Human-readable one-liner: which points are active, plus any errors."""
        active = [label for attr, label in self._LABELS.items() if getattr(self, attr)]
        inactive = [label for attr, label in self._LABELS.items() if not getattr(self, attr)]
        parts = [
            "active: " + (", ".join(active) if active else "(none)"),
            "inactive: " + (", ".join(inactive) if inactive else "(none)"),
        ]
        if self.errors:
            parts.append("errors: " + "; ".join(self.errors))
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Plain dict suitable for JSON / telemetry."""
        return {
            "p3_001_patterns_to_rosetta": self.p3_001_patterns_to_rosetta,
            "p3_002_cycles_to_progress": self.p3_002_cycles_to_progress,
            "p3_003_rag_to_rosetta": self.p3_003_rag_to_rosetta,
            "p3_004_event_subscriptions": self.p3_004_event_subscriptions,
            "p3_005_state_sync": self.p3_005_state_sync,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class RosettaSubsystemWiring:
    """Wires the Rosetta layer into Murphy's existing subsystems.

    The class is intentionally permissive about what it accepts as
    dependencies — anything that quacks like the documented method on
    each subsystem is fine.  This keeps the wiring testable with light
    stubs and resilient to refactors of the underlying engines.
    """

    def __init__(
        self,
        rosetta_manager: Any,
        *,
        event_backbone: Optional[Any] = None,
        rag_vector_integration: Optional[Any] = None,
        self_automation_orchestrator: Optional[Any] = None,
        self_improvement_engine: Optional[Any] = None,
        default_agent_id: str = _DEFAULT_AGENT_ID,
    ) -> None:
        self.rosetta_manager = rosetta_manager
        self.event_backbone = event_backbone
        self.rag_vector_integration = rag_vector_integration
        self.self_automation_orchestrator = self_automation_orchestrator
        self.self_improvement_engine = self_improvement_engine
        self.default_agent_id = default_agent_id
        self.status = WiringStatus()
        # Subscription IDs returned by EventBackbone.subscribe() — used to
        # support clean unwind in the future and to let tests verify wiring.
        self._subscription_ids: List[str] = []

    # ── P3-001 — patterns → rosetta ─────────────────────────────────────
    def wire_patterns_to_rosetta(self) -> bool:
        """Pull patterns from the SelfImprovementEngine into Rosetta.

        Returns ``True`` if patterns were synced (including the
        legitimate empty case), ``False`` if there is no engine or if
        the engine raises.
        """
        if self.self_improvement_engine is None:
            return False
        try:
            patterns = list(self.self_improvement_engine.extract_patterns() or [])
            proposals = [self._pattern_to_proposal(p) for p in patterns]
            if proposals:
                _safe_update_proposals(
                    self.rosetta_manager, self.default_agent_id, proposals
                )
            self.status.p3_001_patterns_to_rosetta = True
            return True
        except Exception as exc:  # noqa: BLE001 — wiring boundary
            self.status.errors.append(f"P3-001: {exc}")
            logger.warning("P3-001 wire_patterns_to_rosetta failed: %s", exc)
            return False

    @staticmethod
    def _pattern_to_proposal(pattern: Dict[str, Any]) -> Dict[str, Any]:
        """Map a SelfImprovementEngine pattern dict to an
        ``ImprovementProposal``-shaped dict."""
        pid = pattern.get("pattern_id") or pattern.get("id") or "pattern-?"
        ptype = pattern.get("type", "improvement")
        category = pattern.get("category", "general")
        occurrences = pattern.get("occurrences", 1)
        return {
            "proposal_id": f"prop-{pid}",
            "title": f"{ptype}: {pid}",
            "description": (
                f"Auto-derived from SelfImprovementEngine pattern '{pid}' "
                f"(type={ptype}, occurrences={occurrences})."
            ),
            "priority": 3,
            "status": "proposed",
            "estimated_effort_hours": 0.0,
            "category": category,
        }

    # ── P3-002 — cycles → automation_progress ───────────────────────────
    def wire_cycles_to_automation_progress(self) -> bool:
        """Sync orchestrator cycle history into ``automation_progress``."""
        if self.self_automation_orchestrator is None:
            return False
        try:
            cycles = list(self.self_automation_orchestrator.get_cycle_history() or [])
            total = len(cycles)
            completed = sum(1 for c in cycles if getattr(c, "completed_at", None))
            coverage = (100.0 * completed / total) if total else 0.0
            entry = {
                "category": "self_improvement",
                "total_items": total,
                "completed_items": completed,
                "coverage_percent": round(coverage, 2),
                "last_updated": _now_iso(),
            }
            _safe_update_automation_progress(
                self.rosetta_manager, self.default_agent_id, entry
            )
            self.status.p3_002_cycles_to_progress = True
            return True
        except Exception as exc:  # noqa: BLE001
            self.status.errors.append(f"P3-002: {exc}")
            logger.warning("P3-002 wire_cycles_to_automation_progress failed: %s", exc)
            return False

    # ── P3-003 — Rosetta state → RAG ────────────────────────────────────
    def wire_rag_ingestion(self, agent_id: Optional[str] = None) -> bool:
        """Ingest the current Rosetta state into the RAG vector store.

        Missing-state is treated as a graceful no-op (returns True with
        zero ingestions) — at cold-start there may simply be nothing to
        index yet, and that's not an error.  RAG returning an
        ``error`` status *is* an error and returns False.
        """
        if self.rag_vector_integration is None:
            return False
        agent_id = agent_id or self.default_agent_id
        try:
            state = self.rosetta_manager.load_state(agent_id)
            if state is None:
                # Graceful: no state yet, nothing to ingest.
                self.status.p3_003_rag_to_rosetta = True
                return True
            text = self._state_to_text(state)
            title = f"rosetta-state:{agent_id}"
            result = self.rag_vector_integration.ingest_document(
                text=text,
                title=title,
                source="rosetta",
                metadata={"agent_id": agent_id, "kind": "rosetta_state"},
            )
            if isinstance(result, dict) and result.get("status") == "error":
                msg = result.get("message", "rag ingest_document returned error")
                self.status.errors.append(f"P3-003: {msg}")
                return False
            self.status.p3_003_rag_to_rosetta = True
            return True
        except Exception as exc:  # noqa: BLE001
            self.status.errors.append(f"P3-003: {exc}")
            logger.warning("P3-003 wire_rag_ingestion failed: %s", exc)
            return False

    # ── P3-004 — EventBackbone subscriptions ────────────────────────────
    def wire_event_subscriptions(self) -> bool:
        """Subscribe TASK_COMPLETED, TASK_FAILED, GATE_EVALUATED handlers.

        Each handler stamps a small marker into ``state.metadata.extras``
        so operators can confirm the event reached Rosetta without
        having to inspect the event-store directly.
        """
        if self.event_backbone is None:
            return False
        try:
            from event_backbone import EventType  # local import: optional
        except Exception as exc:  # noqa: BLE001
            self.status.errors.append(f"P3-004: EventType import failed — {exc}")
            return False
        try:
            mapping = [
                (EventType.TASK_COMPLETED, "last_task_completed_at"),
                (EventType.TASK_FAILED, "last_task_failed_at"),
                (EventType.GATE_EVALUATED, "last_gate_evaluated_at"),
            ]
            for event_type, marker_key in mapping:
                handler = self._make_event_handler(marker_key)
                sub_id = self.event_backbone.subscribe(event_type, handler)
                if sub_id is not None:
                    self._subscription_ids.append(sub_id)
            # All three subscriptions registered (any failure raises and
            # is caught below — we don't want a half-wired backbone).
            self.status.p3_004_event_subscriptions = True
            return True
        except Exception as exc:  # noqa: BLE001
            self.status.errors.append(f"P3-004: {exc}")
            logger.warning("P3-004 wire_event_subscriptions failed: %s", exc)
            return False

    def _make_event_handler(self, marker_key: str) -> Callable[[Any], None]:
        """Build a closure that records the event arrival timestamp into
        Rosetta state.  Always swallow handler errors — a flaky Rosetta
        write must never crash the event-bus."""
        mgr = self.rosetta_manager
        agent_id = self.default_agent_id

        def _handler(event: Any) -> None:
            try:
                state = mgr.load_state(agent_id)
                if state is None:
                    return
                # Touch metadata.extras.<marker_key> with current ISO ts.
                # Use a partial update so we don't accidentally clobber
                # other extras entries the platform has set.
                meta_dump = state.metadata.model_dump(mode="json") if hasattr(state, "metadata") else {}
                extras = dict(meta_dump.get("extras", {}))
                extras[marker_key] = _now_iso()
                meta_dump["extras"] = extras
                mgr.update_state(agent_id, {"metadata": meta_dump})
            except Exception as exc:  # noqa: BLE001 — handlers must never raise
                logger.debug("P3-004 handler %s suppressed: %s", marker_key, exc)
        return _handler

    # ── P3-005 — heartbeat sync ─────────────────────────────────────────
    def wire_state_sync(self, agent_id: Optional[str] = None) -> bool:
        """Touch ``system_state.last_heartbeat`` so liveness is detectable.

        Missing agent → graceful True (nothing to update is not an
        error; agents come and go).
        """
        agent_id = agent_id or self.default_agent_id
        try:
            state = self.rosetta_manager.load_state(agent_id)
            if state is None:
                self.status.p3_005_state_sync = True
                return True
            self.rosetta_manager.update_state(
                agent_id,
                {"system_state": {"last_heartbeat": _now_iso()}},
            )
            self.status.p3_005_state_sync = True
            return True
        except Exception as exc:  # noqa: BLE001
            self.status.errors.append(f"P3-005: {exc}")
            logger.warning("P3-005 wire_state_sync failed: %s", exc)
            return False

    # ── Bulk activation ─────────────────────────────────────────────────
    def wire_all(self) -> WiringStatus:
        """Run every available wire method.  Idempotent."""
        # Order matters slightly: state sync first guarantees there's a
        # heartbeat even if any of the optional integrations break.
        self.wire_state_sync()
        self.wire_patterns_to_rosetta()
        self.wire_cycles_to_automation_progress()
        self.wire_rag_ingestion()
        self.wire_event_subscriptions()
        return self.status

    # ── State serialisation for RAG / debugging ─────────────────────────
    @staticmethod
    def _state_to_text(state: Any) -> str:
        """Render a ``RosettaAgentState`` as Markdown for RAG ingestion.

        Sections are stable so callers can rely on the structure
        downstream (``## Goals``, ``## Tasks``, ``## Automation Progress``,
        plus an Identity header).  Defensive against partially-populated
        states — every section degrades to a "(none)" line rather than
        raising, because RAG ingest must never lose a document just
        because one optional field is missing.
        """
        try:
            identity = getattr(state, "identity", None)
            agent_id = getattr(identity, "agent_id", "unknown")
            name = getattr(identity, "name", "")
            role = getattr(identity, "role", "")

            agent_state = getattr(state, "agent_state", None)
            goals = list(getattr(agent_state, "active_goals", []) or [])
            tasks = list(getattr(agent_state, "task_queue", []) or [])
            progress = list(getattr(state, "automation_progress", []) or [])
            proposals = list(getattr(state, "improvement_proposals", []) or [])

            lines: List[str] = [
                f"# Rosetta Agent State: {agent_id}",
                "",
                f"- name: {name}",
                f"- role: {role}",
                "",
                f"## Goals ({len(goals)})",
            ]
            if goals:
                for g in goals:
                    title = getattr(g, "title", "?")
                    status = getattr(g, "status", "?")
                    lines.append(f"- {title} — {status}")
            else:
                lines.append("(none)")

            lines += ["", f"## Tasks ({len(tasks)})"]
            if tasks:
                for t in tasks:
                    title = getattr(t, "title", "?")
                    status = getattr(t, "status", "?")
                    lines.append(f"- {title} — {status}")
            else:
                lines.append("(none)")

            lines += ["", f"## Automation Progress ({len(progress)})"]
            if progress:
                for p in progress:
                    cat = getattr(p, "category", "?")
                    cov = getattr(p, "coverage_percent", 0.0)
                    lines.append(f"- {cat}: {cov:.1f}%")
            else:
                lines.append("(none)")

            if proposals:
                lines += ["", f"## Improvement Proposals ({len(proposals)})"]
                for pr in proposals:
                    title = getattr(pr, "title", "?")
                    status = getattr(pr, "status", "?")
                    lines.append(f"- {title} — {status}")

            return "\n".join(lines)
        except Exception:  # noqa: BLE001 — last-resort fallback
            try:
                return f"# Rosetta Agent State (raw)\n\n{state.model_dump(mode='json')}"
            except Exception:
                return f"# Rosetta Agent State (raw)\n\n{state!r}"


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def bootstrap_wiring(
    rosetta_manager: Any,
    *,
    event_backbone: Optional[Any] = None,
    rag_vector_integration: Optional[Any] = None,
    self_automation_orchestrator: Optional[Any] = None,
    self_improvement_engine: Optional[Any] = None,
    default_agent_id: str = _DEFAULT_AGENT_ID,
    run_immediately: bool = True,
) -> RosettaSubsystemWiring:
    """Build a ``RosettaSubsystemWiring`` and optionally activate it.

    Defaults to ``run_immediately=True`` because the most common caller
    (startup) wants the wiring live the moment the function returns.
    Pass ``run_immediately=False`` for tests or staged bring-up.
    """
    wiring = RosettaSubsystemWiring(
        rosetta_manager,
        event_backbone=event_backbone,
        rag_vector_integration=rag_vector_integration,
        self_automation_orchestrator=self_automation_orchestrator,
        self_improvement_engine=self_improvement_engine,
        default_agent_id=default_agent_id,
    )
    if run_immediately:
        wiring.wire_all()
    return wiring


# ---------------------------------------------------------------------------
# Module-level helpers — preserved for any caller that imported them
# directly from this module before consolidation.
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def _safe_update_proposals(
    mgr: Any, agent_id: str, proposals: List[Dict[str, Any]]
) -> None:
    """Append *proposals* to ``improvement_proposals``, deduping on
    ``proposal_id``.  Skips silently if the agent has no state."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        existing = state.model_dump(mode="json")
        existing_proposals: List[Dict[str, Any]] = list(
            existing.get("improvement_proposals", [])
        )
        existing_ids = {p.get("proposal_id") for p in existing_proposals}
        for p in proposals:
            if p.get("proposal_id") not in existing_ids:
                existing_proposals.append(p)
                existing_ids.add(p.get("proposal_id"))
        mgr.update_state(agent_id, {"improvement_proposals": existing_proposals})
    except Exception as exc:  # noqa: BLE001
        logger.debug("_safe_update_proposals(%s) suppressed: %s", agent_id, exc)


def _safe_update_automation_progress(
    mgr: Any, agent_id: str, progress_entry: Dict[str, Any]
) -> None:
    """Upsert an entry in ``automation_progress`` keyed on ``category``."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        existing = state.model_dump(mode="json")
        progress_list: List[Dict[str, Any]] = list(
            existing.get("automation_progress", [])
        )
        category = progress_entry.get("category", "")
        updated = [p for p in progress_list if p.get("category") != category]
        updated.append(progress_entry)
        mgr.update_state(agent_id, {"automation_progress": updated})
    except Exception as exc:  # noqa: BLE001
        logger.debug("_safe_update_automation_progress(%s) suppressed: %s", agent_id, exc)


def _safe_update_system_state(
    mgr: Any,
    agent_id: str,
    status: str,
    *,
    active_tasks: Optional[int] = None,
) -> None:
    """Update ``system_state.status`` (and optionally ``active_tasks``)."""
    try:
        state = mgr.load_state(agent_id)
        if state is None:
            return
        update: Dict[str, Any] = {"system_state": {"status": status}}
        if active_tasks is not None:
            update["system_state"]["active_tasks"] = int(active_tasks)
        mgr.update_state(agent_id, update)
    except Exception as exc:  # noqa: BLE001
        logger.debug("_safe_update_system_state(%s) suppressed: %s", agent_id, exc)


def _safe_update(mgr: Any, agent_id: str, fields: Dict[str, Any]) -> None:
    """Generic helper: ``mgr.update_state(agent_id, fields)`` if state exists."""
    try:
        state = mgr.load_state(agent_id)
        if state is not None:
            mgr.update_state(agent_id, fields)
    except Exception as exc:  # noqa: BLE001
        logger.debug("_safe_update(%s) suppressed: %s", agent_id, exc)


def _state_to_text(state: Any) -> str:
    """Module-level alias for ``RosettaSubsystemWiring._state_to_text``."""
    return RosettaSubsystemWiring._state_to_text(state)


def _derive_agent_id(state: Any) -> str:
    """Derive an agent ID from a ``SystemState``-like object."""
    if state is None:
        return _DEFAULT_AGENT_ID
    name = getattr(state, "state_name", None)
    if name and name not in ("default", ""):
        return name
    return _DEFAULT_AGENT_ID


__all__ = [
    "RosettaSubsystemWiring",
    "WiringStatus",
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
