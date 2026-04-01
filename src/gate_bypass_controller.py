"""
Low-Risk Gate Bypass for Murphy System Confidence Gates.

Design Label: GATE-001 — Risk-Based Confidence Gate Bypass
Owner: AI Team / Platform Engineering
Dependencies: None (standalone policy evaluator)

Addresses Constraint 1 from the self-automation plan:
  Confidence gates block simple text generation tasks.

Implements a tiered risk classification that allows MINIMAL and LOW risk
tasks to bypass the full 9-gate confidence chain when the task meets
predefined safety criteria.  CRITICAL and HIGH risk tasks are never
bypassed.

Safety invariants:
- CRITICAL risk tasks always require full gate evaluation + HITL approval
- HIGH risk tasks require full gate evaluation for first N executions
- MEDIUM risk tasks require abbreviated gate evaluation
- LOW risk tasks may bypass after K consecutive successes
- MINIMAL risk tasks may bypass immediately

Trust Escalation Ladder (GATE-002):
  Per-tool confidence history tracks outcomes over time.  When a specific
  bot/engine/skill consistently passes HITL review with high confidence,
  its bypass threshold is automatically raised:

  New tool → Always HITL
  → 10 successful runs → Auto-bypass for LOW risk
  → 50 runs → Auto-bypass for MEDIUM risk

  This reduces operational friction as the system proves itself.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

class TaskRiskLevel(str, Enum):
    """Risk classification for gate bypass decisions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


# Ordered from most to least restrictive
_RISK_ORDER = {
    TaskRiskLevel.CRITICAL: 0,
    TaskRiskLevel.HIGH: 1,
    TaskRiskLevel.MEDIUM: 2,
    TaskRiskLevel.LOW: 3,
    TaskRiskLevel.MINIMAL: 4,
}


@dataclass
class BypassPolicy:
    """Configuration for a gate bypass policy tier."""
    risk_level: TaskRiskLevel
    bypass_allowed: bool
    min_consecutive_successes: int = 0
    require_abbreviated_gates: bool = True
    max_auto_approvals: int = 100


# Default policy table  [GATE-001]
DEFAULT_POLICIES: Dict[TaskRiskLevel, BypassPolicy] = {
    TaskRiskLevel.CRITICAL: BypassPolicy(
        risk_level=TaskRiskLevel.CRITICAL,
        bypass_allowed=False,
        require_abbreviated_gates=True,
    ),
    TaskRiskLevel.HIGH: BypassPolicy(
        risk_level=TaskRiskLevel.HIGH,
        bypass_allowed=False,
        require_abbreviated_gates=True,
    ),
    TaskRiskLevel.MEDIUM: BypassPolicy(
        risk_level=TaskRiskLevel.MEDIUM,
        bypass_allowed=False,
        min_consecutive_successes=5,
        require_abbreviated_gates=True,
    ),
    TaskRiskLevel.LOW: BypassPolicy(
        risk_level=TaskRiskLevel.LOW,
        bypass_allowed=True,
        min_consecutive_successes=3,
        require_abbreviated_gates=False,
        max_auto_approvals=50,
    ),
    TaskRiskLevel.MINIMAL: BypassPolicy(
        risk_level=TaskRiskLevel.MINIMAL,
        bypass_allowed=True,
        min_consecutive_successes=0,
        require_abbreviated_gates=False,
        max_auto_approvals=100,
    ),
}


@dataclass
class BypassDecision:
    """Result of a gate bypass evaluation."""
    task_type: str
    risk_level: TaskRiskLevel
    bypass_granted: bool
    reason: str
    require_gates: bool = True
    consecutive_successes: int = 0
    auto_approvals_remaining: int = 0
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "risk_level": self.risk_level.value,
            "bypass_granted": self.bypass_granted,
            "reason": self.reason,
            "require_gates": self.require_gates,
            "consecutive_successes": self.consecutive_successes,
            "auto_approvals_remaining": self.auto_approvals_remaining,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# Low-risk task type registry
# ---------------------------------------------------------------------------

# Task types classified as MINIMAL risk by default
MINIMAL_RISK_TASK_TYPES = frozenset({
    "text_generation",
    "tagline_creation",
    "documentation_update",
    "readme_update",
    "faq_generation",
    "status_report",
    "log_summary",
})

# Task types classified as LOW risk by default
LOW_RISK_TASK_TYPES = frozenset({
    "content_generation",
    "blog_draft",
    "email_template",
    "knowledge_base_update",
    "test_generation",
    "code_quality_report",
    "metric_report",
})


# ---------------------------------------------------------------------------
# GateBypassController
# ---------------------------------------------------------------------------

class GateBypassController:
    """Evaluates whether a task may bypass the full confidence gate chain.

    Design Label: GATE-001
    Owner: AI Team

    Usage::

        ctrl = GateBypassController()
        decision = ctrl.evaluate("tagline_creation", risk_level=TaskRiskLevel.MINIMAL)
        if decision.bypass_granted:
            # skip full gate chain
            ...
    """

    def __init__(
        self,
        policies: Optional[Dict[TaskRiskLevel, BypassPolicy]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._policies = dict(policies or DEFAULT_POLICIES)
        self._success_tracker: Dict[str, int] = defaultdict(int)  # task_type → consecutive successes
        self._auto_approval_counts: Dict[str, int] = defaultdict(int)  # task_type → approvals used
        self._decision_log: List[BypassDecision] = []
        self._max_log = 200

    # ------------------------------------------------------------------
    # Risk classification
    # ------------------------------------------------------------------

    def classify_risk(self, task_type: str, risk_hint: Optional[TaskRiskLevel] = None) -> TaskRiskLevel:
        """Classify a task type into a risk level.

        Uses an explicit hint if provided, otherwise falls back to the
        built-in task type registries.
        """
        if risk_hint is not None:
            return risk_hint
        if task_type in MINIMAL_RISK_TASK_TYPES:
            return TaskRiskLevel.MINIMAL
        if task_type in LOW_RISK_TASK_TYPES:
            return TaskRiskLevel.LOW
        return TaskRiskLevel.MEDIUM  # default conservative

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        task_type: str,
        risk_level: Optional[TaskRiskLevel] = None,
    ) -> BypassDecision:
        """Evaluate whether *task_type* may bypass the full gate chain."""
        risk = self.classify_risk(task_type, risk_level)
        policy = self._policies.get(risk)
        if policy is None:
            decision = BypassDecision(
                task_type=task_type,
                risk_level=risk,
                bypass_granted=False,
                reason="no_policy_for_risk_level",
                require_gates=True,
            )
            self._log_decision(decision)
            return decision

        with self._lock:
            consecutive = self._success_tracker.get(task_type, 0)
            approvals_used = self._auto_approval_counts.get(task_type, 0)

        if not policy.bypass_allowed:
            decision = BypassDecision(
                task_type=task_type,
                risk_level=risk,
                bypass_granted=False,
                reason=f"bypass_not_allowed_for_{risk.value}_risk",
                require_gates=policy.require_abbreviated_gates,
                consecutive_successes=consecutive,
            )
            self._log_decision(decision)
            return decision

        if consecutive < policy.min_consecutive_successes:
            decision = BypassDecision(
                task_type=task_type,
                risk_level=risk,
                bypass_granted=False,
                reason=f"insufficient_successes_{consecutive}/{policy.min_consecutive_successes}",
                require_gates=True,
                consecutive_successes=consecutive,
            )
            self._log_decision(decision)
            return decision

        if approvals_used >= policy.max_auto_approvals:
            decision = BypassDecision(
                task_type=task_type,
                risk_level=risk,
                bypass_granted=False,
                reason="max_auto_approvals_exhausted",
                require_gates=True,
                consecutive_successes=consecutive,
                auto_approvals_remaining=0,
            )
            self._log_decision(decision)
            return decision

        # Bypass granted
        with self._lock:
            self._auto_approval_counts[task_type] = approvals_used + 1

        decision = BypassDecision(
            task_type=task_type,
            risk_level=risk,
            bypass_granted=True,
            reason="low_risk_bypass_granted",
            require_gates=False,
            consecutive_successes=consecutive,
            auto_approvals_remaining=policy.max_auto_approvals - approvals_used - 1,
        )
        self._log_decision(decision)
        return decision

    # ------------------------------------------------------------------
    # Outcome feedback
    # ------------------------------------------------------------------

    def record_success(self, task_type: str) -> None:
        """Record a successful task execution (increments consecutive counter)."""
        with self._lock:
            self._success_tracker[task_type] = self._success_tracker.get(task_type, 0) + 1

    def record_failure(self, task_type: str) -> None:
        """Record a failed task execution (resets consecutive counter)."""
        with self._lock:
            self._success_tracker[task_type] = 0

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policies": {
                    rl.value: {
                        "bypass_allowed": p.bypass_allowed,
                        "min_consecutive_successes": p.min_consecutive_successes,
                        "max_auto_approvals": p.max_auto_approvals,
                    }
                    for rl, p in self._policies.items()
                },
                "success_tracker": dict(self._success_tracker),
                "auto_approval_counts": dict(self._auto_approval_counts),
                "decisions_logged": len(self._decision_log),
            }

    def get_decision_log(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            recent = self._decision_log[-limit:]
        return [d.to_dict() for d in recent]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_decision(self, decision: BypassDecision) -> None:
        with self._lock:
            self._decision_log.append(decision)
            if len(self._decision_log) > self._max_log:
                self._decision_log = self._decision_log[-self._max_log:]


# ---------------------------------------------------------------------------
# Trust Escalation Ladder (GATE-002)
# ---------------------------------------------------------------------------

_DEFAULT_LOW_THRESHOLD = 10     # runs before auto-bypass for LOW risk
_DEFAULT_MEDIUM_THRESHOLD = 50  # runs before auto-bypass for MEDIUM risk
_MAX_HISTORY_PER_TOOL = 200


@dataclass
class TrustLevel:
    """Current trust state for a single tool."""
    tool_id: str
    total_runs: int = 0
    successful_runs: int = 0
    consecutive_successes: int = 0
    current_bypass_level: TaskRiskLevel = TaskRiskLevel.CRITICAL  # starts most restrictive
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def success_rate(self) -> float:
        return self.successful_runs / self.total_runs if self.total_runs > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "consecutive_successes": self.consecutive_successes,
            "success_rate": round(self.success_rate, 4),
            "current_bypass_level": self.current_bypass_level.value,
            "last_updated": self.last_updated,
        }


@dataclass
class EscalationThresholds:
    """Configurable thresholds for trust escalation."""
    low_risk_bypass_after: int = _DEFAULT_LOW_THRESHOLD
    medium_risk_bypass_after: int = _DEFAULT_MEDIUM_THRESHOLD
    min_success_rate: float = 0.95  # 95% success rate required
    cooldown_on_failure: int = 5    # failures before de-escalation


class ConfidenceHistoryTracker:
    """Tracks per-tool confidence history for trust escalation.

    Design Label: GATE-002

    Trust escalation ladder:
      New tool → Always HITL (CRITICAL bypass level)
      → low_risk_bypass_after successful runs → Auto-bypass for LOW risk
      → medium_risk_bypass_after runs → Auto-bypass for MEDIUM risk

    A failure resets the consecutive counter and may de-escalate trust.

    Thread-safe, bounded history per tool.
    """

    def __init__(
        self,
        thresholds: Optional[EscalationThresholds] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._thresholds = thresholds or EscalationThresholds()
        self._trust_levels: Dict[str, TrustLevel] = {}

    def record_outcome(self, tool_id: str, success: bool) -> TrustLevel:
        """Record a tool execution outcome and re-evaluate trust."""
        with self._lock:
            trust = self._trust_levels.get(tool_id)
            if trust is None:
                trust = TrustLevel(tool_id=tool_id)
                self._trust_levels[tool_id] = trust

            trust.total_runs += 1
            if success:
                trust.successful_runs += 1
                trust.consecutive_successes += 1
            else:
                trust.consecutive_successes = 0

            trust.last_updated = datetime.now(timezone.utc).isoformat()

            # Re-evaluate trust level
            self._evaluate_escalation(trust)

            return trust

    def get_trust_level(self, tool_id: str) -> Optional[TrustLevel]:
        """Get current trust level for a tool."""
        with self._lock:
            return self._trust_levels.get(tool_id)

    def get_bypass_level(self, tool_id: str) -> TaskRiskLevel:
        """Get the current maximum bypass risk level for a tool.

        Returns CRITICAL (no bypass) for unknown tools.
        """
        with self._lock:
            trust = self._trust_levels.get(tool_id)
            if trust is None:
                return TaskRiskLevel.CRITICAL
            return trust.current_bypass_level

    def should_bypass(self, tool_id: str, task_risk: TaskRiskLevel) -> bool:
        """Check if a tool has earned enough trust to bypass at a given risk level.

        CRITICAL tasks are never bypassed regardless of trust.
        """
        if task_risk == TaskRiskLevel.CRITICAL:
            return False

        with self._lock:
            trust = self._trust_levels.get(tool_id)
            if trust is None:
                return False

            tool_bypass_order = _RISK_ORDER.get(trust.current_bypass_level, 0)
            task_risk_order = _RISK_ORDER.get(task_risk, 0)

            # Tool can bypass if its trust level permits this risk level or lower
            return task_risk_order >= tool_bypass_order

    def get_all_trust_levels(self) -> List[TrustLevel]:
        """Return all tracked trust levels."""
        with self._lock:
            return list(self._trust_levels.values())

    def get_escalation_status(self) -> Dict[str, Any]:
        """Return summary of trust escalation state."""
        with self._lock:
            levels: Dict[str, int] = {}
            for trust in self._trust_levels.values():
                lv = trust.current_bypass_level.value
                levels[lv] = levels.get(lv, 0) + 1
            return {
                "total_tools_tracked": len(self._trust_levels),
                "bypass_level_distribution": levels,
                "thresholds": {
                    "low_risk_after": self._thresholds.low_risk_bypass_after,
                    "medium_risk_after": self._thresholds.medium_risk_bypass_after,
                    "min_success_rate": self._thresholds.min_success_rate,
                },
            }

    def reset_tool(self, tool_id: str) -> None:
        """Reset trust for a tool (e.g., after a major update)."""
        with self._lock:
            if tool_id in self._trust_levels:
                self._trust_levels[tool_id] = TrustLevel(tool_id=tool_id)
                logger.info("Trust reset for tool: %s", tool_id)

    # ------------------------------------------------------------------
    # Internal escalation logic
    # ------------------------------------------------------------------

    def _evaluate_escalation(self, trust: TrustLevel) -> None:
        """Re-evaluate and possibly escalate/de-escalate trust.

        Called while holding self._lock.
        """
        th = self._thresholds

        # De-escalation on low success rate
        if trust.total_runs >= 10 and trust.success_rate < th.min_success_rate:
            if trust.current_bypass_level != TaskRiskLevel.CRITICAL:
                logger.info(
                    "Trust de-escalated for %s: success_rate=%.2f < %.2f",
                    trust.tool_id, trust.success_rate, th.min_success_rate,
                )
                trust.current_bypass_level = TaskRiskLevel.CRITICAL
            return

        # Escalation ladder
        if (
            trust.consecutive_successes >= th.medium_risk_bypass_after
            and trust.success_rate >= th.min_success_rate
        ):
            new_level = TaskRiskLevel.MEDIUM
        elif (
            trust.consecutive_successes >= th.low_risk_bypass_after
            and trust.success_rate >= th.min_success_rate
        ):
            new_level = TaskRiskLevel.LOW
        else:
            new_level = TaskRiskLevel.CRITICAL

        if new_level != trust.current_bypass_level:
            old = trust.current_bypass_level
            trust.current_bypass_level = new_level
            logger.info(
                "Trust escalated for %s: %s → %s (runs=%d, consecutive=%d, rate=%.2f)",
                trust.tool_id, old.value, new_level.value,
                trust.total_runs, trust.consecutive_successes, trust.success_rate,
            )
