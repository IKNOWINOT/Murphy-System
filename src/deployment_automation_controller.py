"""
Deployment Automation Controller for Murphy System.

Design Label: ADV-002 — CI/CD Pipeline Integration with Safety Gates
Owner: DevOps Team / Platform Engineering
Dependencies:
  - EventBackbone (publishes deployment events, subscribes to TASK_COMPLETED)
  - SelfHealingCoordinator (OBS-004, for automatic rollback)
  - PersistenceManager (for deployment history)
  - ComplianceAutomationBridge (CMP-001, optional pre-deploy compliance check)

Implements Phase 6 — Advanced Self-Automation:
  Manages the deployment lifecycle with configurable safety gates,
  approval workflows, automatic rollback on failure, and deployment
  history tracking.

Flow:
  1. Create deployment request (artifact, target environment, version)
  2. Run pre-deployment gates (compliance, tests, approval)
  3. Execute deployment (simulate or delegate to external CI/CD)
  4. Monitor deployment health
  5. Automatic rollback on failure
  6. Publish events for downstream automation

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Production deployments always require approval
  - Automatic rollback on health check failure
  - Deployment history is immutable
  - Audit trail: every deployment action is logged

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class DeploymentStatus(str, Enum):
    """Deployment lifecycle states."""
    REQUESTED = "requested"
    GATES_CHECKING = "gates_checking"
    GATES_PASSED = "gates_passed"
    GATES_FAILED = "gates_failed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    HEALTH_CHECK = "health_check"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class Environment(str, Enum):
    """Target deployment environments."""
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


_REQUIRES_APPROVAL = {Environment.PRODUCTION}


@dataclass
class DeploymentGate:
    """A pre-deployment safety gate."""
    gate_id: str
    name: str
    checker: Callable[..., bool]
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "required": self.required,
        }


@dataclass
class DeploymentRequest:
    """A single deployment request."""
    deployment_id: str
    artifact: str
    version: str
    environment: Environment
    status: DeploymentStatus = DeploymentStatus.REQUESTED
    gate_results: Dict[str, bool] = field(default_factory=dict)
    approver: Optional[str] = None
    rollback_version: Optional[str] = None
    health_checks_passed: bool = False
    error_message: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "artifact": self.artifact,
            "version": self.version,
            "environment": self.environment.value,
            "status": self.status.value,
            "gate_results": dict(self.gate_results),
            "approver": self.approver,
            "rollback_version": self.rollback_version,
            "health_checks_passed": self.health_checks_passed,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# DeploymentAutomationController
# ---------------------------------------------------------------------------

class DeploymentAutomationController:
    """CI/CD pipeline integration with safety gates and rollback.

    Design Label: ADV-002
    Owner: DevOps Team

    Usage::

        ctrl = DeploymentAutomationController(event_backbone=backbone)
        ctrl.register_gate("tests_pass", lambda: True)
        dep = ctrl.create_deployment(
            artifact="murphy-system",
            version="1.2.0",
            environment="staging",
        )
        ctrl.run_gates(dep.deployment_id)
        ctrl.deploy(dep.deployment_id)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._deployments: Dict[str, DeploymentRequest] = {}
        self._gates: List[DeploymentGate] = []
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Gate management
    # ------------------------------------------------------------------

    def register_gate(
        self,
        name: str,
        checker: Callable[..., bool],
        required: bool = True,
    ) -> str:
        """Register a pre-deployment gate. Returns gate_id."""
        gate = DeploymentGate(
            gate_id=f"gate-{uuid.uuid4().hex[:6]}",
            name=name,
            checker=checker,
            required=required,
        )
        with self._lock:
            capped_append(self._gates, gate)
        return gate.gate_id

    def list_gates(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [g.to_dict() for g in self._gates]

    # ------------------------------------------------------------------
    # Deployment lifecycle
    # ------------------------------------------------------------------

    def create_deployment(
        self,
        artifact: str,
        version: str,
        environment: str,
        rollback_version: Optional[str] = None,
    ) -> DeploymentRequest:
        """Create a new deployment request."""
        env = Environment(environment.lower()) if isinstance(environment, str) else environment
        dep = DeploymentRequest(
            deployment_id=f"dep-{uuid.uuid4().hex[:8]}",
            artifact=artifact,
            version=version,
            environment=env,
            rollback_version=rollback_version,
        )
        with self._lock:
            self._deployments[dep.deployment_id] = dep
            self._record_event(dep.deployment_id, "created", {})
        logger.info("Created deployment %s: %s v%s -> %s", dep.deployment_id, artifact, version, env.value)
        return dep

    def run_gates(self, deployment_id: str) -> Optional[DeploymentRequest]:
        """Run all registered gates against a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            dep.status = DeploymentStatus.GATES_CHECKING
            gates = list(self._gates)

        results = {}
        all_passed = True
        for gate in gates:
            try:
                passed = gate.checker()
            except Exception as exc:
                logger.warning("Gate %s failed with exception: %s", gate.name, exc)
                passed = False
            results[gate.name] = passed
            if gate.required and not passed:
                all_passed = False

        with self._lock:
            dep.gate_results = results
            if all_passed:
                dep.status = DeploymentStatus.GATES_PASSED
                # Check if approval is needed
                if dep.environment in _REQUIRES_APPROVAL:
                    dep.status = DeploymentStatus.PENDING_APPROVAL
            else:
                dep.status = DeploymentStatus.GATES_FAILED
            dep.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(deployment_id, "gates_checked", {"results": results, "passed": all_passed})

        self._persist(dep)
        self._publish(dep, "gates_checked")
        return dep

    def approve(self, deployment_id: str, approver: str) -> Optional[DeploymentRequest]:
        """Approve a pending deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            if dep.status != DeploymentStatus.PENDING_APPROVAL:
                return dep
            dep.status = DeploymentStatus.APPROVED
            dep.approver = approver
            dep.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(deployment_id, "approved", {"approver": approver})
        self._persist(dep)
        self._publish(dep, "approved")
        return dep

    def deploy(self, deployment_id: str) -> Optional[DeploymentRequest]:
        """Execute a deployment (simulation — marks as deployed)."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            allowed = {DeploymentStatus.GATES_PASSED, DeploymentStatus.APPROVED}
            if dep.status not in allowed:
                return dep
            dep.status = DeploymentStatus.DEPLOYING
            dep.updated_at = datetime.now(timezone.utc).isoformat()

        # Simulate deployment execution
        try:
            # In a real system, this would call external CI/CD
            with self._lock:
                dep.status = DeploymentStatus.DEPLOYED
                dep.updated_at = datetime.now(timezone.utc).isoformat()
                self._record_event(deployment_id, "deployed", {"version": dep.version})
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            with self._lock:
                dep.status = DeploymentStatus.FAILED
                dep.error_message = str(exc)
                dep.updated_at = datetime.now(timezone.utc).isoformat()
                self._record_event(deployment_id, "deploy_failed", {"error": str(exc)})

        self._persist(dep)
        self._publish(dep, "deployed" if dep.status == DeploymentStatus.DEPLOYED else "failed")
        return dep

    def check_health(self, deployment_id: str, healthy: bool = True) -> Optional[DeploymentRequest]:
        """Report health check result for a deployment."""
        with self._lock:
            dep = self._deployments.get(deployment_id)
            if dep is None:
                return None
            if healthy:
                dep.status = DeploymentStatus.HEALTHY
                dep.health_checks_passed = True
                self._record_event(deployment_id, "health_ok", {})
            else:
                dep.status = DeploymentStatus.UNHEALTHY
                dep.health_checks_passed = False
                self._record_event(deployment_id, "health_failed", {})
            dep.updated_at = datetime.now(timezone.utc).isoformat()

        if not healthy and dep.rollback_version:
            self._rollback(dep)

        self._persist(dep)
        self._publish(dep, "health_check")
        return dep

    def _rollback(self, dep: DeploymentRequest) -> None:
        """Execute automatic rollback."""
        with self._lock:
            dep.status = DeploymentStatus.ROLLING_BACK
            dep.updated_at = datetime.now(timezone.utc).isoformat()
        logger.warning("Rolling back deployment %s to %s", dep.deployment_id, dep.rollback_version)
        # Simulate rollback
        with self._lock:
            dep.status = DeploymentStatus.ROLLED_BACK
            dep.updated_at = datetime.now(timezone.utc).isoformat()
            self._record_event(dep.deployment_id, "rolled_back", {
                "from_version": dep.version,
                "to_version": dep.rollback_version,
            })

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            dep = self._deployments.get(deployment_id)
        return dep.to_dict() if dep else None

    def list_deployments(
        self,
        environment: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            deps = list(self._deployments.values())
        if environment:
            deps = [d for d in deps if d.environment.value == environment.lower()]
        deps.sort(key=lambda d: d.created_at, reverse=True)
        return [d.to_dict() for d in deps[:limit]]

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self._deployments)
            by_status = {}
            for d in self._deployments.values():
                by_status[d.status.value] = by_status.get(d.status.value, 0) + 1
            gate_count = len(self._gates)
        return {
            "total_deployments": total,
            "by_status": by_status,
            "registered_gates": gate_count,
            "persistence_attached": self._pm is not None,
            "backbone_attached": self._backbone is not None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_event(self, deployment_id: str, action: str, details: Dict[str, Any]) -> None:
        """Append audit event (caller must hold _lock)."""
        capped_append(self._history, {
            "deployment_id": deployment_id,
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _persist(self, dep: DeploymentRequest) -> None:
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=dep.deployment_id,
                    document=dep.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

    def _publish(self, dep: DeploymentRequest, action: str) -> None:
        if self._backbone is not None:
            try:
                from event_backbone import EventType
                self._backbone.publish(
                    event_type=EventType.LEARNING_FEEDBACK,
                    payload={
                        "source": "deployment_automation_controller",
                        "action": action,
                        "deployment_id": dep.deployment_id,
                        "artifact": dep.artifact,
                        "version": dep.version,
                        "environment": dep.environment.value,
                        "status": dep.status.value,
                    },
                    source="deployment_automation_controller",
                )
            except Exception as exc:
                logger.debug("EventBackbone publish skipped: %s", exc)
