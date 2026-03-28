# golden_path_engine.py — Murphy System Golden Path Recommendation Engine
# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""
GoldenPathEngine drives the gold-glow recommendation system.

Every UI page calls GET /api/golden-path and applies gold-glow CSS to the
elements the engine marks as highest-priority for the current user.

Hero Flow fast-track (Task 5)
------------------------------
:meth:`GoldenPathEngine.is_eligible_for_fast_track` detects whether a command
is simple/common enough to skip the full pipeline.

:meth:`GoldenPathEngine.execute_fast_path` attempts fast-track execution
via :class:`~golden_path_bridge.GoldenPathBridge` and falls back to the
full pipeline when a golden path is not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Priority(int, Enum):
    """Recommendation priority levels — lower number = more urgent."""

    HITL_GATE = 1
    STUCK_PROCESS = 2
    QC_READY = 3
    CONFIG_GAP = 4
    OPTIMISATION = 5


@dataclass
class Recommendation:
    """A single actionable recommendation for the current user."""

    priority: Priority
    element_id: str          # CSS id / data-target that UI should gold-glow
    title: str
    description: str
    action_url: str          # URL to navigate to on click
    workflow_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "priority": self.priority.value,
            "priority_name": self.priority.name,
            "element_id": self.element_id,
            "title": self.title,
            "description": self.description,
            "action_url": self.action_url,
            "workflow_id": self.workflow_id,
            "metadata": self.metadata,
        }


class GoldenPathEngine:
    """Determines what the user should look at next based on system state.

    Priority ladder (ascending urgency):
        1. HITL gates waiting for human approval
        2. Stuck / red processes
        3. QC items ready for review
        4. Config gaps (missing API keys, incomplete onboarding)
        5. Optimisation suggestions (cost savings, performance)
    """

    # Role-based permission map
    _ROLE_PERMISSIONS: dict[str, set[str]] = {
        "FOUNDER": {"view_all", "override_gate", "abort_automation", "admin_config"},
        "ADMIN":   {"view_all", "abort_automation", "admin_config"},
        "OPERATOR": {"view_assigned", "submit_hitl"},
        "VIEWER":   {"view_assigned"},
    }

    def get_permissions(self, user_role: str) -> set[str]:
        """Return the permission set for the given role."""
        return self._ROLE_PERMISSIONS.get(user_role.upper(), {"view_assigned"})

    def get_recommendations(
        self, user_role: str, system_state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return a prioritised list of recommended actions.

        Parameters
        ----------
        user_role:
            One of FOUNDER, ADMIN, OPERATOR, VIEWER.
        system_state:
            Snapshot of current system; expected keys (all optional):
            - hitl_pending:   list of { id, workflow_id, description }
            - stuck_workflows: list of { id, name, step, since }
            - qc_ready:        list of { id, name }
            - config_gaps:     list of { key, description }
            - optimisations:   list of { id, title, saving }
        """
        recs: list[Recommendation] = []
        role_upper = user_role.upper()
        perms = self.get_permissions(role_upper)

        # ── Priority 1: HITL gates ──────────────────────────────
        if "submit_hitl" in perms or "view_all" in perms:
            for item in (system_state.get("hitl_pending") or []):
                recs.append(Recommendation(
                    priority=Priority.HITL_GATE,
                    element_id=f"hitl-{item.get('id', 'unknown')}",
                    title="HITL Gate Requires Approval",
                    description=item.get("description", "A gate is awaiting human review."),
                    action_url="/terminal_orchestrator.html#hitl",
                    workflow_id=item.get("workflow_id"),
                    metadata=item,
                ))

        # ── Priority 2: Stuck / red processes ──────────────────
        if "view_all" in perms or "view_assigned" in perms:
            for item in (system_state.get("stuck_workflows") or []):
                recs.append(Recommendation(
                    priority=Priority.STUCK_PROCESS,
                    element_id=f"workflow-{item.get('id', 'unknown')}",
                    title=f"Stuck: {item.get('name', 'Unknown workflow')}",
                    description=f"Stuck at step: {item.get('step', '?')}",
                    action_url=f"/terminal_orchestrator.html#workflow-{item.get('id', '')}",
                    workflow_id=item.get("id"),
                    metadata=item,
                ))

        # ── Priority 3: QC items ready for review ──────────────
        if "view_all" in perms or "view_assigned" in perms:
            for item in (system_state.get("qc_ready") or []):
                recs.append(Recommendation(
                    priority=Priority.QC_READY,
                    element_id=f"qc-{item.get('id', 'unknown')}",
                    title=f"QC Ready: {item.get('name', 'Item')}",
                    description="This item has passed automated checks and is ready for review.",
                    action_url="/terminal_orchestrator.html#qc",
                    workflow_id=item.get("workflow_id"),
                    metadata=item,
                ))

        # ── Priority 4: Config gaps ─────────────────────────────
        if "admin_config" in perms:
            for item in (system_state.get("config_gaps") or []):
                recs.append(Recommendation(
                    priority=Priority.CONFIG_GAP,
                    element_id=f"config-{item.get('key', 'unknown').replace('.', '-')}",
                    title=f"Config Gap: {item.get('key', '?')}",
                    description=item.get("description", "A required configuration key is missing."),
                    action_url="/terminal_integrations.html",
                    metadata=item,
                ))

        # ── Priority 5: Optimisation suggestions ───────────────
        if "view_all" in perms:
            for item in (system_state.get("optimisations") or []):
                recs.append(Recommendation(
                    priority=Priority.OPTIMISATION,
                    element_id=f"opt-{item.get('id', 'unknown')}",
                    title=item.get("title", "Optimisation available"),
                    description=f"Potential saving: {item.get('saving', 'unknown')}",
                    action_url="/terminal_costs.html",
                    metadata=item,
                ))

        # Sort by priority then by insertion order (stable)
        recs.sort(key=lambda r: r.priority.value)

        return [r.to_dict() for r in recs]

    def get_critical_path(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return the critical path through a workflow.

        Returns the sequence of gates/steps that have the most impact on
        overall completion time and quality.  Currently returns a structured
        placeholder; wire up to the real workflow DAG engine as needed.
        """
        if not workflow_id:
            return []

        # Default critical-path template (all 7 MFGC phases)
        mfgc_phases = [
            ("EXPAND",   "Requirement expansion and scope definition"),
            ("TYPE",     "Classify and type all inputs"),
            ("SHOW",     "Enumerate concrete deliverables"),
            ("COUNTS",   "Quantify scope — lines, tokens, items"),
            ("COLLAPSE", "Remove ambiguity and contradictions"),
            ("SIZE",     "Estimate effort and resource requirements"),
            ("TEST",     "Validate outputs meet acceptance criteria"),
        ]

        return [
            {
                "phase":       phase,
                "description": desc,
                "workflow_id": workflow_id,
                "is_gate":     phase in {"SHOW", "TEST"},
                "requires_hitl": phase == "TEST",
            }
            for phase, desc in mfgc_phases
        ]

    # ------------------------------------------------------------------
    # Hero Flow fast-track — Task 5
    # ------------------------------------------------------------------

    # Commands/patterns considered "simple" enough for golden-path fast-track.
    # A command is eligible when it matches one of these patterns AND the
    # golden-path bridge has a recorded path for it with sufficient confidence.
    _FAST_TRACK_PATTERNS: List[str] = [
        # Read-only / informational
        "/status", "/help", "/memory", "/confidence", "/gates",
        "/swarmmonitor", "/docs", "/module", "/learning",
        # Simple automations that have been run many times
        "list", "show", "get", "fetch", "query", "search",
    ]

    # Minimum bridge confidence to fast-track
    _FAST_TRACK_MIN_CONFIDENCE: float = 0.75

    def is_eligible_for_fast_track(
        self,
        command: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Return True when *command* may be fast-tracked via golden path.

        A command is eligible when:
        1. It matches one of the ``_FAST_TRACK_PATTERNS``.
        2. It is not a high-risk/write command (no ``create``, ``delete``,
           ``autonomous``, ``governance`` destructive keywords).

        Parameters
        ----------
        command:
            The raw command or task string.
        context:
            Optional context dict; reserved for future risk scoring.
        """
        cmd_lower = command.strip().lower()

        # Blocklist — never fast-track these
        blocklist = ["delete", "remove", "destroy", "drop", "purge", "reset",
                     "create automation", "autonomous start"]
        if any(bl in cmd_lower for bl in blocklist):
            return False

        return any(pat in cmd_lower for pat in self._FAST_TRACK_PATTERNS)

    def execute_fast_path(
        self,
        command: str,
        bridge: Any,
        domain: str = "default",
        *,
        fallback_fn: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Attempt fast-track execution via *bridge*.

        If a golden path exists with sufficient confidence, replays it and
        returns the execution spec.  Otherwise calls *fallback_fn* (or
        returns a ``{"fast_path": False}`` sentinel so the caller can
        invoke the full pipeline).

        Parameters
        ----------
        command:
            The command/task string to execute.
        bridge:
            A :class:`~golden_path_bridge.GoldenPathBridge` instance.
        domain:
            Domain hint for path matching.
        fallback_fn:
            Optional callable ``(command) -> dict`` to invoke when no
            golden path is available.  When ``None``, the method returns
            ``{"fast_path": False, "command": command}``.

        Returns
        -------
        A dict with ``"fast_path": True`` and execution spec keys on a
        cache hit, or ``{"fast_path": False, ...}`` on a miss.
        """
        try:
            matches = bridge.find_matching_paths(
                command,
                domain=domain,
                min_confidence=self._FAST_TRACK_MIN_CONFIDENCE,
            )
        except Exception as exc:
            logger.warning("GoldenPathEngine: bridge lookup failed: %s", exc)
            matches = []

        if matches:
            best = matches[0]
            spec = bridge.replay_path(best.path_id)
            if spec is not None:
                logger.info(
                    "GoldenPathEngine: fast-track hit for %r (path=%s, score=%.2f)",
                    command, best.path_id, best.match_score,
                )
                return {
                    "fast_path": True,
                    "path_id": best.path_id,
                    "match_score": best.match_score,
                    "confidence": best.confidence,
                    **spec,
                }

        logger.debug("GoldenPathEngine: no fast-track path for %r — falling back", command)

        if fallback_fn is not None:
            try:
                return fallback_fn(command)
            except Exception as exc:
                logger.error("GoldenPathEngine: fallback_fn raised: %s", exc)

        return {"fast_path": False, "command": command}
