"""
Full Automation Controller for Murphy System

Implements toggleable full automation with HITL transition gap detection,
risk-based activation, and success rate monitoring. Only admin/owner roles
can enable full automation for organizations, and only account owners can
enable it for their own agents in non-organization contexts.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class AutomationMode(str, Enum):
    """Automation operation modes."""
    MANUAL = "manual"  # All actions require human approval
    SEMI_AUTONOMOUS = "semi_autonomous"  # Low-risk actions auto-approved
    FULL_AUTONOMOUS = "full_autonomous"  # All actions auto-approved except critical


class AutomationToggleReason(str, Enum):
    """Reasons for automation mode changes."""
    MANUAL_ENABLE = "manual_enable"
    HITL_GAP_DETECTED = "hitl_gap_detected"
    RISK_THRESHOLD_EXCEEDED = "risk_threshold_exceeded"
    SUCCESS_RATE_HIGH = "success_rate_high"
    ADMIN_OVERRIDE = "admin_override"
    OWNER_OVERRIDE = "owner_override"
    EMERGENCY_STOP = "emergency_stop"
    SCHEDULED_CHANGE = "scheduled_change"


class RiskLevel(str, Enum):
    """Risk levels for automation decisions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


@dataclass
class AutomationState:
    """Current automation state for a tenant or agent."""
    tenant_id: str
    agent_id: Optional[str] = None  # None for tenant-level automation
    mode: AutomationMode = AutomationMode.MANUAL
    enabled_at: Optional[datetime] = None
    enabled_by: Optional[str] = None  # user_id who enabled
    reason: AutomationToggleReason = AutomationToggleReason.MANUAL_ENABLE
    last_transition: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transition_history: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HITLTransitionGap:
    """Represents a gap in human-in-the-loop transitions."""
    gap_id: str
    detected_at: datetime
    gap_type: str  # approval_timeout, escalation_failure, intervention_rate
    severity: RiskLevel
    description: str
    tenant_id: str = ""
    agent_id: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class AutomationMetrics:
    """Metrics for automation performance."""
    total_actions: int = 0
    auto_approved: int = 0
    human_approved: int = 0
    rejected: int = 0
    escalated: int = 0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    hitl_gap_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FullAutomationController:
    """
    Controller for toggleable full automation with HITL gap detection.

    Features:
    - Toggle between MANUAL, SEMI_AUTONOMOUS, and FULL_AUTONOMOUS modes
    - HITL transition gap detection and monitoring
    - Risk-based automation activation
    - Success rate monitoring and adaptive thresholds
    - Admin/owner-only toggle controls
    - RBAC integration for permission checks
    - Audit logging for all mode changes
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._states: Dict[str, AutomationState] = {}  # key: tenant_id or tenant_id:agent_id
        self._hitl_gaps: Dict[str, HITLTransitionGap] = {}
        self._metrics: Dict[str, AutomationMetrics] = {}
        self._audit_log: List[Dict[str, Any]] = []

        # Configuration
        self._success_rate_threshold = 0.95  # 95% success rate for full automation
        self._hitl_gap_threshold = 3  # Max gaps before mode downgrade
        self._risk_threshold = RiskLevel.MEDIUM  # Max risk for semi-autonomous
        self._min_observations = 50  # Minimum actions before considering automation

        # Callbacks
        self._on_mode_change: Optional[Callable[[str, AutomationMode, AutomationMode], None]] = None
        self._on_hitl_gap_detected: Optional[Callable[[HITLTransitionGap], None]] = None

    # ========================================================================
    # Mode Management
    # ========================================================================

    def set_automation_mode(
        self,
        tenant_id: str,
        agent_id: Optional[str],
        mode: AutomationMode,
        user_id: str,
        reason: AutomationToggleReason,
        user_role: str,
        is_organization: bool = True,
    ) -> Tuple[bool, str]:
        """
        Set automation mode for a tenant or agent.

        Only admin/owner roles can enable full automation for organizations.
        Only account owners can enable full automation for their own agents.

        Args:
            tenant_id: Tenant identifier
            agent_id: Optional agent identifier (None for tenant-level)
            mode: Desired automation mode
            user_id: User requesting the change
            reason: Reason for the change
            user_role: Role of the requesting user
            is_organization: Whether this is an organization context

        Returns:
            (success, message) tuple
        """
        # Check permissions
        if mode == AutomationMode.FULL_AUTONOMOUS:
            if is_organization:
                if user_role not in ["admin", "owner"]:
                    return False, "Only admin or owner roles can enable full automation in organizations"
            else:
                if user_role != "owner":
                    return False, "Only account owners can enable full automation for their agents"

        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            current_state = self._states.get(key)

            if current_state is None:
                current_state = AutomationState(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    mode=mode,
                    enabled_at=datetime.now(timezone.utc),
                    enabled_by=user_id,
                    reason=reason,
                )
                self._states[key] = current_state
            else:
                # Record transition
                old_mode = current_state.mode
                current_state.transition_history.append({
                    "from_mode": old_mode.value,
                    "to_mode": mode.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "user_id": user_id,
                    "reason": reason.value,
                })

                # Update state
                current_state.mode = mode
                current_state.enabled_at = datetime.now(timezone.utc)
                current_state.enabled_by = user_id
                current_state.reason = reason
                current_state.last_transition = datetime.now(timezone.utc)

            # Log audit
            capped_append(self._audit_log, {
                "event": "automation_mode_changed",
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "old_mode": current_state.transition_history[-2]["from_mode"] if len(current_state.transition_history) >= 2 else "none",
                "new_mode": mode.value,
                "user_id": user_id,
                "user_role": user_role,
                "reason": reason.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            logger.info(
                "Automation mode changed for %s: %s -> %s by %s (%s)",
                key, current_state.transition_history[-2]["from_mode"] if len(current_state.transition_history) >= 2 else "none",
                mode.value, user_id, reason.value
            )

            # Trigger callback
            if self._on_mode_change and len(current_state.transition_history) >= 2:
                old_mode = AutomationMode(current_state.transition_history[-2]["from_mode"])
                self._on_mode_change(key, old_mode, mode)

            return True, f"Automation mode set to {mode.value}"

    def get_automation_mode(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
    ) -> Optional[AutomationMode]:
        """Get current automation mode for a tenant or agent."""
        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            state = self._states.get(key)
            return state.mode if state else None

    def get_automation_state(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get full automation state for a tenant or agent."""
        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            state = self._states.get(key)
            if state is None:
                return None

            return {
                "tenant_id": state.tenant_id,
                "agent_id": state.agent_id,
                "mode": state.mode.value,
                "enabled_at": state.enabled_at.isoformat() if state.enabled_at else None,
                "enabled_by": state.enabled_by,
                "reason": state.reason.value,
                "last_transition": state.last_transition.isoformat(),
                "transition_count": len(state.transition_history),
                "metrics": state.metrics,
            }

    # ========================================================================
    # HITL Transition Gap Detection
    # ========================================================================

    def detect_hitl_gap(
        self,
        tenant_id: str,
        agent_id: Optional[str],
        gap_type: str,
        severity: RiskLevel,
        description: str,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> HITLTransitionGap:
        """
        Detect and record a HITL transition gap.

        Args:
            tenant_id: Tenant identifier
            agent_id: Optional agent identifier
            gap_type: Type of gap (approval_timeout, escalation_failure, intervention_rate)
            severity: Risk level of the gap
            description: Description of the gap
            metrics: Additional metrics about the gap

        Returns:
            Created HITLTransitionGap
        """
        import uuid

        gap = HITLTransitionGap(
            gap_id=str(uuid.uuid4()),
            detected_at=datetime.now(timezone.utc),
            gap_type=gap_type,
            severity=severity,
            description=description,
            tenant_id=tenant_id,
            agent_id=agent_id,
            metrics=metrics or {},
        )

        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            self._hitl_gaps[gap.gap_id] = gap

            # Update metrics
            if key not in self._metrics:
                self._metrics[key] = AutomationMetrics()
            self._metrics[key].hitl_gap_count += 1

            # Check if we should downgrade automation mode
            self._check_hitl_gap_threshold(key, tenant_id, agent_id)

            # Trigger callback
            if self._on_hitl_gap_detected:
                self._on_hitl_gap_detected(gap)

            logger.warning(
                "HITL gap detected for %s: %s (%s) - %s",
                key, gap_type, severity.value, description
            )

        return gap

    def resolve_hitl_gap(self, gap_id: str, resolved_by: str) -> bool:
        """Mark a HITL gap as resolved."""
        with self._lock:
            gap = self._hitl_gaps.get(gap_id)
            if gap is None:
                return False

            gap.resolved = True
            gap.resolved_at = datetime.now(timezone.utc)

            logger.info("HITL gap %s resolved by %s", gap_id, resolved_by)
            return True

    def get_active_hitl_gaps(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
    ) -> List[HITLTransitionGap]:
        """Get all active (unresolved) HITL gaps for a tenant or agent."""
        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            return [
                gap for gap in self._hitl_gaps.values()
                if not gap.resolved and self._gap_belongs_to(gap, tenant_id, agent_id)
            ]

    def _check_hitl_gap_threshold(
        self,
        key: str,
        tenant_id: str,
        agent_id: Optional[str],
    ) -> None:
        """Check if HITL gap threshold exceeded and downgrade mode if needed."""
        active_gaps = self.get_active_hitl_gaps(tenant_id, agent_id)

        if len(active_gaps) >= self._hitl_gap_threshold:
            state = self._states.get(key)
            if state and state.mode != AutomationMode.MANUAL:
                # Downgrade to manual
                old_mode = state.mode
                state.mode = AutomationMode.MANUAL
                state.reason = AutomationToggleReason.HITL_GAP_DETECTED
                state.last_transition = datetime.now(timezone.utc)

                logger.warning(
                    "Downgrading automation mode for %s from %s to MANUAL due to HITL gaps",
                    key, old_mode.value
                )

    def _gap_belongs_to(
        self,
        gap: HITLTransitionGap,
        tenant_id: str,
        agent_id: Optional[str],
    ) -> bool:
        """Determine whether *gap* belongs to the given tenant / agent scope.

        Matching rules (most-specific first):
        1. If *agent_id* is provided, the gap must match both
           ``tenant_id`` **and** ``agent_id`` exactly.
        2. If *agent_id* is ``None`` (tenant-level query), the gap must
           match ``tenant_id``; agent-level gaps within that tenant are
           also included.
        3. Legacy gaps that were recorded before ownership fields were
           added (empty ``tenant_id``) are visible to every query so
           they remain actionable.
        """
        # Legacy / untagged gaps (tenant_id is empty string or None) are
        # globally visible so they remain actionable after schema migration.
        if not gap.tenant_id:
            return True

        if gap.tenant_id != tenant_id:
            return False

        # Tenant-level query → include all gaps for this tenant
        if agent_id is None:
            return True

        # Agent-level query → must also match agent_id
        return gap.agent_id == agent_id

    # ========================================================================
    # Risk-Based Automation
    # ========================================================================

    def evaluate_action_risk(
        self,
        action_type: str,
        context: Dict[str, Any],
    ) -> RiskLevel:
        """
        Evaluate the risk level of an action.

        Args:
            action_type: Type of action being evaluated
            context: Context information about the action

        Returns:
            Risk level for the action
        """
        # Simple risk evaluation logic
        # This would be enhanced with more sophisticated risk assessment

        critical_actions = {
            "deploy_to_production",
            "delete_data",
            "modify_security_settings",
            "change_user_permissions",
        }

        high_risk_actions = {
            "deploy_to_staging",
            "modify_configuration",
            "execute_code",
            "access_sensitive_data",
        }

        if action_type in critical_actions:
            return RiskLevel.CRITICAL
        elif action_type in high_risk_actions:
            return RiskLevel.HIGH
        elif context.get("has_rollback", False):
            return RiskLevel.LOW
        else:
            return RiskLevel.MEDIUM

    def should_auto_approve(
        self,
        tenant_id: str,
        agent_id: Optional[str],
        action_type: str,
        context: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Determine if an action should be auto-approved based on automation mode and risk.

        Args:
            tenant_id: Tenant identifier
            agent_id: Optional agent identifier
            action_type: Type of action
            context: Context information

        Returns:
            (should_approve, reason) tuple
        """
        mode = self.get_automation_mode(tenant_id, agent_id)
        if mode is None:
            return False, "No automation mode configured"

        risk = self.evaluate_action_risk(action_type, context)

        if mode == AutomationMode.MANUAL:
            return False, "Manual mode - all actions require approval"

        elif mode == AutomationMode.SEMI_AUTONOMOUS:
            # Auto-approve only low and minimal risk actions
            if risk in [RiskLevel.LOW, RiskLevel.MINIMAL]:
                return True, f"Semi-autonomous mode - {risk.value} risk auto-approved"
            else:
                return False, f"Semi-autonomous mode - {risk.value} risk requires approval"

        elif mode == AutomationMode.FULL_AUTONOMOUS:
            # Auto-approve everything except critical
            if risk == RiskLevel.CRITICAL:
                return False, "Full-autonomous mode - critical risk requires approval"
            else:
                return True, f"Full-autonomous mode - {risk.value} risk auto-approved"

        return False, "Unknown automation mode"

    # ========================================================================
    # Success Rate Monitoring
    # ========================================================================

    def record_action_outcome(
        self,
        tenant_id: str,
        agent_id: Optional[str],
        action_type: str,
        approved: bool,
        auto_approved: bool,
        success: bool,
        response_time: Optional[float] = None,
    ) -> None:
        """
        Record the outcome of an action for success rate tracking.

        Args:
            tenant_id: Tenant identifier
            agent_id: Optional agent identifier
            action_type: Type of action
            approved: Whether the action was approved
            auto_approved: Whether it was auto-approved
            success: Whether the action succeeded
            response_time: Time taken for the action (seconds)
        """
        with self._lock:
            key = self._make_key(tenant_id, agent_id)

            if key not in self._metrics:
                self._metrics[key] = AutomationMetrics()

            metrics = self._metrics[key]
            metrics.total_actions += 1

            if approved:
                if auto_approved:
                    metrics.auto_approved += 1
                else:
                    metrics.human_approved += 1
            else:
                metrics.rejected += 1

            if success:
                # Update success rate using exponential moving average
                current_rate = metrics.success_rate
                alpha = 0.1  # Smoothing factor
                new_rate = 1.0 if not approved else (alpha * 1.0 + (1 - alpha) * current_rate)
                metrics.success_rate = new_rate
            else:
                # Update success rate for failure
                current_rate = metrics.success_rate
                alpha = 0.1
                new_rate = alpha * 0.0 + (1 - alpha) * current_rate
                metrics.success_rate = new_rate

            if response_time is not None:
                # Update average response time
                current_avg = metrics.avg_response_time
                count = metrics.total_actions
                metrics.avg_response_time = (current_avg * (count - 1) + response_time) / count

            metrics.last_updated = datetime.now(timezone.utc)

            # Check if we should upgrade automation mode
            self._check_success_rate_threshold(key, tenant_id, agent_id)

    def _check_success_rate_threshold(
        self,
        key: str,
        tenant_id: str,
        agent_id: Optional[str],
    ) -> None:
        """Check if success rate threshold met and upgrade mode if appropriate."""
        metrics = self._metrics.get(key)
        if metrics is None:
            return

        if metrics.total_actions < self._min_observations:
            return

        state = self._states.get(key)
        if state is None:
            return

        # Check if we can upgrade to semi-autonomous
        if (state.mode == AutomationMode.MANUAL and
            metrics.success_rate >= self._success_rate_threshold and
            metrics.hitl_gap_count == 0):

            state.mode = AutomationMode.SEMI_AUTONOMOUS
            state.reason = AutomationToggleReason.SUCCESS_RATE_HIGH
            state.last_transition = datetime.now(timezone.utc)

            logger.info(
                "Upgrading automation mode for %s to SEMI_AUTONOMOUS due to high success rate (%.2f)",
                key, metrics.success_rate
            )

    def get_metrics(
        self,
        tenant_id: str,
        agent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get automation metrics for a tenant or agent."""
        with self._lock:
            key = self._make_key(tenant_id, agent_id)
            metrics = self._metrics.get(key)
            if metrics is None:
                return None

            return {
                "total_actions": metrics.total_actions,
                "auto_approved": metrics.auto_approved,
                "human_approved": metrics.human_approved,
                "rejected": metrics.rejected,
                "escalated": metrics.escalated,
                "success_rate": round(metrics.success_rate, 4),
                "avg_response_time": round(metrics.avg_response_time, 2),
                "hitl_gap_count": metrics.hitl_gap_count,
                "last_updated": metrics.last_updated.isoformat(),
            }

    # ========================================================================
    # Callbacks
    # ========================================================================

    def set_mode_change_callback(
        self,
        callback: Callable[[str, AutomationMode, AutomationMode], None],
    ) -> None:
        """Set callback for automation mode changes."""
        self._on_mode_change = callback

    def set_hitl_gap_callback(
        self,
        callback: Callable[[HITLTransitionGap], None],
    ) -> None:
        """Set callback for HITL gap detection."""
        self._on_hitl_gap_detected = callback

    # ========================================================================
    # Audit & Status
    # ========================================================================

    def get_audit_log(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit log entries, optionally filtered by tenant."""
        with self._lock:
            logs = self._audit_log
            if tenant_id:
                logs = [log for log in logs if log.get("tenant_id") == tenant_id]
            return logs[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Get overall controller status."""
        with self._lock:
            return {
                "total_states": len(self._states),
                "active_hitl_gaps": sum(1 for gap in self._hitl_gaps.values() if not gap.resolved),
                "total_metrics": len(self._metrics),
                "audit_log_entries": len(self._audit_log),
                "success_rate_threshold": self._success_rate_threshold,
                "hitl_gap_threshold": self._hitl_gap_threshold,
                "risk_threshold": self._risk_threshold.value,
                "min_observations": self._min_observations,
            }

    # ========================================================================
    # Helpers
    # ========================================================================

    def _make_key(self, tenant_id: str, agent_id: Optional[str]) -> str:
        """Create a unique key for a tenant/agent combination."""
        if agent_id:
            return f"{tenant_id}:{agent_id}"
        return tenant_id
