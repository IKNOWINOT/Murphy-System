"""
Shadow Mode & Authorization System

Provides:
1. Shadow mode: Learn and recommend without enforcing
2. Authorization interface: Control Plane approval required
3. Rollback mechanism: Restore previous stable state
4. Audit logging: Track all changes and decisions
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    GateEvolutionArtifact,
    InsightArtifact,
    ReasonCode,
)

logger = logging.getLogger(__name__)


class OperationMode(str, Enum):
    """System operation modes"""
    SHADOW = "shadow"  # Learn only, no enforcement
    GRADUAL = "gradual"  # Gradual rollout with A/B testing
    FULL = "full"  # Full enforcement


class AuthorizationStatus(str, Enum):
    """Authorization status for gate evolutions"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class ShadowModeController:
    """
    Controls shadow mode operation and enforcement.

    Shadow Mode:
    - Collects telemetry
    - Generates insights and recommendations
    - Logs proposed changes
    - DOES NOT enforce changes

    Gradual Mode:
    - Enforces changes for subset of traffic
    - A/B testing with control group
    - Monitors impact

    Full Mode:
    - Full enforcement of authorized changes
    - Continuous monitoring
    - Automatic rollback on violations
    """

    def __init__(self, mode: OperationMode = OperationMode.SHADOW):
        self.mode = mode
        self.shadow_log: List[Dict[str, Any]] = []
        self.enforcement_percentage = 0.0  # For gradual mode
        self.stats = {
            "proposals_generated": 0,
            "proposals_logged": 0,
            "proposals_enforced": 0,
            "rollbacks_triggered": 0,
        }

    def set_mode(self, mode: OperationMode) -> None:
        """Change operation mode"""
        logger.info(f"Changing mode from {self.mode} to {mode}")
        self.mode = mode

        if mode == OperationMode.SHADOW:
            self.enforcement_percentage = 0.0
        elif mode == OperationMode.GRADUAL:
            self.enforcement_percentage = 0.1  # Start at 10%
        elif mode == OperationMode.FULL:
            self.enforcement_percentage = 1.0

    def set_enforcement_percentage(self, percentage: float) -> None:
        """Set enforcement percentage for gradual mode"""
        if not 0.0 <= percentage <= 1.0:
            raise ValueError("Percentage must be between 0 and 1")

        if self.mode != OperationMode.GRADUAL:
            logger.warning(
                f"Setting enforcement percentage in {self.mode} mode has no effect"
            )

        self.enforcement_percentage = percentage
        logger.info(f"Enforcement percentage set to {percentage:.1%}")

    def should_enforce(self, artifact_id: str) -> bool:
        """
        Determine if a change should be enforced.

        In shadow mode: Always False
        In gradual mode: Based on enforcement percentage
        In full mode: Always True
        """
        if self.mode == OperationMode.SHADOW:
            return False
        elif self.mode == OperationMode.FULL:
            return True
        else:  # GRADUAL
            # Use hash of artifact_id for consistent A/B assignment
            hash_val = hash(artifact_id) % 100
            return hash_val < (self.enforcement_percentage * 100)

    def log_proposal(
        self,
        proposal: GateEvolutionArtifact,
        enforced: bool,
    ) -> None:
        """Log a gate evolution proposal"""
        self.stats["proposals_generated"] += 1

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evolution_id": proposal.evolution_id,
            "gate_id": proposal.gate_id,
            "reason_codes": [rc.value for rc in proposal.reason_codes],
            "parameter_diff": proposal.parameter_diff,
            "enforced": enforced,
            "mode": self.mode.value,
        }

        self.shadow_log.append(log_entry)
        self.stats["proposals_logged"] += 1

        if enforced:
            self.stats["proposals_enforced"] += 1

        logger.info(
            f"Logged proposal {proposal.evolution_id}: "
            f"enforced={enforced}, mode={self.mode}"
        )

    def log_insight(
        self,
        insight: InsightArtifact,
    ) -> None:
        """Log an insight/recommendation"""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "insight_id": insight.insight_id,
            "insight_type": insight.insight_type.value,
            "severity": insight.severity,
            "title": insight.title,
            "recommendation": insight.recommendation,
            "mode": self.mode.value,
        }

        self.shadow_log.append(log_entry)

        logger.info(
            f"Logged insight {insight.insight_id}: "
            f"type={insight.insight_type}, severity={insight.severity}"
        )

    def get_shadow_log(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get shadow mode log entries"""
        log = self.shadow_log

        if since:
            log = [
                entry for entry in log
                if datetime.fromisoformat(entry["timestamp"]) >= since
            ]

        # Sort by timestamp (newest first)
        log.sort(key=lambda x: x["timestamp"], reverse=True)

        return log[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get shadow mode statistics"""
        return {
            **self.stats,
            "mode": self.mode.value,
            "enforcement_percentage": self.enforcement_percentage,
            "log_size": len(self.shadow_log),
        }

    def clear_log(self) -> None:
        """Clear shadow log (for testing)"""
        self.shadow_log.clear()


class AuthorizationInterface:
    """
    Interface for Control Plane authorization of gate evolutions.

    All gate changes must be authorized by Control Plane before enforcement.
    Provides audit trail and rollback capability.
    """

    def __init__(self):
        self.pending_proposals: Dict[str, GateEvolutionArtifact] = {}
        self.authorization_log: List[Dict[str, Any]] = {}
        self.rollback_history: List[Dict[str, Any]] = []
        self.stats = {
            "proposals_submitted": 0,
            "proposals_approved": 0,
            "proposals_rejected": 0,
            "rollbacks_executed": 0,
        }

    def submit_proposal(
        self,
        proposal: GateEvolutionArtifact,
    ) -> str:
        """
        Submit a gate evolution proposal for authorization.

        Returns proposal ID for tracking.
        """
        self.pending_proposals[proposal.evolution_id] = proposal
        self.stats["proposals_submitted"] += 1

        logger.info(
            f"Submitted proposal {proposal.evolution_id} for authorization"
        )

        return proposal.evolution_id

    def authorize_proposal(
        self,
        evolution_id: str,
        authorized_by: str,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Authorize a gate evolution proposal.

        Returns True if successful, False if proposal not found.
        """
        proposal = self.pending_proposals.get(evolution_id)
        if not proposal:
            logger.error(f"Proposal {evolution_id} not found")
            return False

        # Authorize the proposal
        proposal.authorize(authorized_by)

        # Log authorization
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evolution_id": evolution_id,
            "gate_id": proposal.gate_id,
            "status": AuthorizationStatus.APPROVED.value,
            "authorized_by": authorized_by,
            "notes": notes,
            "parameter_diff": proposal.parameter_diff,
        }
        self.authorization_log[evolution_id] = log_entry

        # Remove from pending
        del self.pending_proposals[evolution_id]

        self.stats["proposals_approved"] += 1

        logger.info(
            f"Authorized proposal {evolution_id} by {authorized_by}"
        )

        return True

    def reject_proposal(
        self,
        evolution_id: str,
        rejected_by: str,
        reason: str,
    ) -> bool:
        """
        Reject a gate evolution proposal.

        Returns True if successful, False if proposal not found.
        """
        proposal = self.pending_proposals.get(evolution_id)
        if not proposal:
            logger.error(f"Proposal {evolution_id} not found")
            return False

        # Log rejection
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evolution_id": evolution_id,
            "gate_id": proposal.gate_id,
            "status": AuthorizationStatus.REJECTED.value,
            "rejected_by": rejected_by,
            "reason": reason,
        }
        self.authorization_log[evolution_id] = log_entry

        # Remove from pending
        del self.pending_proposals[evolution_id]

        self.stats["proposals_rejected"] += 1

        logger.info(
            f"Rejected proposal {evolution_id} by {rejected_by}: {reason}"
        )

        return True

    def rollback_evolution(
        self,
        evolution_id: str,
        rolled_back_by: str,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Rollback a gate evolution to previous state.

        Returns rollback state if successful, None if not found.
        """
        log_entry = self.authorization_log.get(evolution_id)
        if not log_entry:
            logger.error(f"Evolution {evolution_id} not found in log")
            return None

        if log_entry["status"] != AuthorizationStatus.APPROVED.value:
            logger.error(f"Evolution {evolution_id} was not approved")
            return None

        # Get rollback state from original proposal
        # In production, this would fetch from the gate synthesis engine
        rollback_state = {
            "evolution_id": evolution_id,
            "gate_id": log_entry["gate_id"],
            "rollback_timestamp": datetime.now(timezone.utc).isoformat(),
            "rolled_back_by": rolled_back_by,
            "reason": reason,
        }

        # Update log
        log_entry["status"] = AuthorizationStatus.ROLLED_BACK.value
        log_entry["rollback_timestamp"] = rollback_state["rollback_timestamp"]
        log_entry["rolled_back_by"] = rolled_back_by
        log_entry["rollback_reason"] = reason

        # Add to rollback history
        self.rollback_history.append(rollback_state)

        self.stats["rollbacks_executed"] += 1

        logger.info(
            f"Rolled back evolution {evolution_id} by {rolled_back_by}: {reason}"
        )

        return rollback_state

    def get_pending_proposals(self) -> List[GateEvolutionArtifact]:
        """Get all pending proposals"""
        return list(self.pending_proposals.values())

    def get_authorization_log(
        self,
        since: Optional[datetime] = None,
        status: Optional[AuthorizationStatus] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get authorization log with filters"""
        log = list(self.authorization_log.values())

        if since:
            log = [
                entry for entry in log
                if datetime.fromisoformat(entry["timestamp"]) >= since
            ]

        if status:
            log = [
                entry for entry in log
                if entry["status"] == status.value
            ]

        # Sort by timestamp (newest first)
        log.sort(key=lambda x: x["timestamp"], reverse=True)

        return log[:limit]

    def get_rollback_history(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get rollback history"""
        history = self.rollback_history

        if since:
            history = [
                entry for entry in history
                if datetime.fromisoformat(entry["rollback_timestamp"]) >= since
            ]

        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x["rollback_timestamp"], reverse=True)

        return history[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get authorization statistics"""
        return {
            **self.stats,
            "pending_proposals": len(self.pending_proposals),
            "total_logged": len(self.authorization_log),
            "total_rollbacks": len(self.rollback_history),
        }


class SafetyEnforcer:
    """
    Enforces safety constraints on telemetry learning system.

    Ensures:
    - Telemetry NEVER generates execution actions
    - All gate changes require authorization
    - Rollbacks are always available
    - Audit trail is maintained
    """

    def __init__(self):
        self.violations: List[Dict[str, Any]] = []
        self.blocked_actions: List[Dict[str, Any]] = []

    def validate_proposal(
        self,
        proposal: GateEvolutionArtifact,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a gate evolution proposal for safety.

        Returns (is_valid, error_message).
        """
        # Check for authorization
        if proposal.authorized:
            # Already authorized, check who authorized
            if not proposal.authorized_by:
                return False, "Authorized proposal missing authorized_by field"

        # Check for rollback state
        if not proposal.rollback_state:
            return False, "Proposal missing rollback state"

        # Check for evidence
        if not proposal.telemetry_evidence:
            return False, "Proposal missing telemetry evidence"

        # Check for reason codes
        if not proposal.reason_codes:
            return False, "Proposal missing reason codes"

        # Check for relaxation without deterministic evidence
        is_relaxation = self._is_relaxation(proposal)
        if is_relaxation:
            if ReasonCode.DETERMINISTIC_EVIDENCE not in proposal.reason_codes:
                return False, "Relaxation requires deterministic evidence"

        return True, None

    def block_execution_action(
        self,
        action_type: str,
        reason: str,
    ) -> None:
        """Block an execution action (telemetry must not execute)"""
        blocked = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "reason": reason,
        }
        self.blocked_actions.append(blocked)

        logger.warning(
            f"BLOCKED execution action: {action_type} - {reason}"
        )

    def record_violation(
        self,
        violation_type: str,
        details: Dict[str, Any],
    ) -> None:
        """Record a safety violation"""
        violation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "violation_type": violation_type,
            "details": details,
        }
        self.violations.append(violation)

        logger.error(
            f"SAFETY VIOLATION: {violation_type} - {details}"
        )

    def get_violations(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get safety violations"""
        violations = self.violations

        if since:
            violations = [
                v for v in violations
                if datetime.fromisoformat(v["timestamp"]) >= since
            ]

        return violations

    def get_blocked_actions(
        self,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get blocked actions"""
        blocked = self.blocked_actions

        if since:
            blocked = [
                b for b in blocked
                if datetime.fromisoformat(b["timestamp"]) >= since
            ]

        return blocked

    def _is_relaxation(self, proposal: GateEvolutionArtifact) -> bool:
        """Check if proposal relaxes constraints"""
        for param, diff in proposal.parameter_diff.items():
            before = diff.get("before")
            after = diff.get("after")

            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                if after < before:
                    return True
            elif isinstance(before, bool) and isinstance(after, bool):
                if before and not after:
                    return True

        return False
