"""
Agent Descriptor Implementation for Murphy System

Implements the formal agent descriptor specification including:
- Agent descriptor schema and validation
- Authority scope management
- Stability limits and scheduling constraints
- Termination conditions and escalation rules
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class AuthorityBand(Enum):
    """Authority levels for agents"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ActionType(Enum):
    """Permitted action types for agents"""
    PROPOSE_PLAN = "propose_plan"
    PROPOSE_CODE = "propose_code"
    PROPOSE_ACTION = "propose_action"
    VALIDATE = "validate"
    EXECUTE = "execute"
    COMMUNICATE = "communicate"


class ValidationType(Enum):
    """Validation types agents may perform"""
    SYMBOLIC_CHECK = "symbolic_check"
    DETERMINISTIC_TEST = "deterministic_test"
    EMPIRICAL_VALIDATION = "empirical_validation"


class ExecutionType(Enum):
    """Execution types agents may perform"""
    COMPUTE = "compute"
    TRANSFORM = "transform"
    COMMUNICATE = "communicate"
    ANALYZE = "analyze"


class PriorityLevel(Enum):
    """Scheduling priority levels"""
    REALTIME = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BATCH = 4


class RetryCondition(Enum):
    """Conditions under which retries are permitted"""
    STATE_CHANGE_REQUIRED = "state_change_required"
    NEW_EVIDENCE = "new_evidence"
    AUTHORITY_ESCALATION = "authority_escalation"


@dataclass
class ResourceCaps:
    """Resource limits for agents"""
    max_cpu_cores: int
    max_memory_mb: int
    max_execution_time_sec: int
    max_api_calls_per_sec: int

    def validate(self) -> bool:
        """Validate resource caps are reasonable"""
        return (
            self.max_cpu_cores > 0 and
            self.max_memory_mb > 0 and
            self.max_execution_time_sec > 0 and
            self.max_api_calls_per_sec >= 0
        )


@dataclass
class AccessMatrix:
    """Access permissions for agents"""
    readable_paths: List[str] = field(default_factory=list)
    writable_paths: List[str] = field(default_factory=list)
    network_endpoints: List[str] = field(default_factory=list)
    database_tables: List[str] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate access matrix is properly formatted"""
        return (
            isinstance(self.readable_paths, list) and
            isinstance(self.writable_paths, list) and
            isinstance(self.network_endpoints, list) and
            isinstance(self.database_tables, list)
        )


@dataclass
class ActionSet:
    """Action permissions for agents"""
    allowed_proposals: List[ActionType] = field(default_factory=list)
    allowed_validations: List[ValidationType] = field(default_factory=list)
    allowed_executions: List[ExecutionType] = field(default_factory=list)
    prohibited_actions: List[ActionType] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate action permissions are consistent"""
        allowed_actions = set(self.allowed_proposals + self.allowed_validations + self.allowed_executions)
        prohibited_set = set(self.prohibited_actions)

        # No action should be both allowed and prohibited
        return len(allowed_actions.intersection(prohibited_set)) == 0


@dataclass
class ConvergenceSpec:
    """Convergence constraints for agents"""
    max_iterations: int
    convergence_threshold: float
    divergence_threshold: float
    stability_window_ms: int
    max_state_changes_per_window: int

    def validate(self) -> bool:
        """Validate convergence constraints are reasonable"""
        return (
            self.max_iterations > 0 and
            0.0 <= self.convergence_threshold <= 1.0 and
            self.divergence_threshold > 0.0 and
            self.stability_window_ms > 0 and
            self.max_state_changes_per_window >= 0
        )


@dataclass
class RetrySpec:
    """Retry policy for agents"""
    max_retries: int
    min_backoff_ms: int
    max_backoff_ms: int
    retry_condition: RetryCondition

    def validate(self) -> bool:
        """Validate retry policy is reasonable"""
        return (
            self.max_retries >= 0 and
            0 <= self.min_backoff_ms <= self.max_backoff_ms and
            self.retry_condition is not None
        )


@dataclass
class SchedulingSpec:
    """Scheduling requirements for agents"""
    priority: PriorityLevel
    cpu_reservation: int
    memory_reservation: int
    deadline_ms: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    exclusivity_group: Optional[str] = None

    def validate(self) -> bool:
        """Validate scheduling requirements"""
        return (
            self.cpu_reservation >= 0 and
            self.memory_reservation >= 0 and
            (self.deadline_ms is None or self.deadline_ms > 0)
        )


@dataclass
class Condition:
    """Generic condition for termination criteria"""
    type: str
    parameters: Dict[str, Union[str, int, float, bool]]


@dataclass
class TerminationSpec:
    """Termination conditions for agents"""
    success_conditions: List[Condition] = field(default_factory=list)
    failure_conditions: List[Condition] = field(default_factory=list)
    timeout_conditions: List[Condition] = field(default_factory=list)
    stability_conditions: List[Condition] = field(default_factory=list)
    refusal_conditions: List[Condition] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate termination conditions"""
        return all(hasattr(condition, 'type') for condition in
                  self.success_conditions + self.failure_conditions +
                  self.timeout_conditions + self.stability_conditions +
                  self.refusal_conditions)


@dataclass
class Trigger:
    """Trigger condition for escalation"""
    condition_type: str
    threshold: Union[int, float, str]
    comparison: str  # ">=", "<=", "==", "!=", "contains"


@dataclass
class EscalationPath:
    """Path for escalation requests"""
    target_authority: str
    escalation_method: str
    timeout_ms: int


@dataclass
class FallbackAction:
    """Action to take if escalation fails"""
    action_type: str
    parameters: Dict[str, Union[str, int, float, bool]]


@dataclass
class EscalationSpec:
    """Escalation policy for agents"""
    escalation_triggers: List[Trigger] = field(default_factory=list)
    required_authority_level: AuthorityBand = AuthorityBand.NONE
    escalation_timeout_ms: int = 300000  # 5 minutes
    fallback_behavior: Optional[FallbackAction] = None
    escalation_paths: List[EscalationPath] = field(default_factory=list)

    def validate(self) -> bool:
        """Validate escalation policy"""
        return (
            self.escalation_timeout_ms > 0 and
            all(hasattr(trigger, 'condition_type') for trigger in self.escalation_triggers)
        )


@dataclass
class AgentDescriptor:
    """Complete agent descriptor for Murphy System governance"""

    # Identity
    agent_id: str
    version: str
    signature: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Authority Scope
    authority_band: AuthorityBand = AuthorityBand.NONE
    resource_limits: ResourceCaps = field(default_factory=lambda: ResourceCaps(
        max_cpu_cores=1, max_memory_mb=512, max_execution_time_sec=300, max_api_calls_per_sec=10
    ))
    access_scope: AccessMatrix = field(default_factory=AccessMatrix)

    # Permitted Action Types
    action_permissions: ActionSet = field(default_factory=ActionSet)

    # Stability Limits
    convergence_constraints: ConvergenceSpec = field(default_factory=lambda: ConvergenceSpec(
        max_iterations=1000, convergence_threshold=0.01, divergence_threshold=0.1,
        stability_window_ms=300000, max_state_changes_per_window=10
    ))
    retry_policy: RetrySpec = field(default_factory=lambda: RetrySpec(
        max_retries=3, min_backoff_ms=1000, max_backoff_ms=30000,
        retry_condition=RetryCondition.STATE_CHANGE_REQUIRED
    ))

    # Scheduling Constraints
    scheduling_requirements: SchedulingSpec = field(default_factory=lambda: SchedulingSpec(
        priority=PriorityLevel.NORMAL, cpu_reservation=1, memory_reservation=256
    ))

    # Termination Conditions
    termination_criteria: TerminationSpec = field(default_factory=TerminationSpec)

    # Escalation Rules
    escalation_policy: EscalationSpec = field(default_factory=EscalationSpec)

    def __post_init__(self):
        """Validate descriptor after creation"""
        if not self.validate():
            raise ValueError("Invalid agent descriptor")

    def validate(self) -> bool:
        """Validate the complete descriptor"""
        try:
            # Validate all components
            if not self.resource_limits.validate():
                return False
            if not self.access_scope.validate():
                return False
            if not self.action_permissions.validate():
                return False
            if not self.convergence_constraints.validate():
                return False
            if not self.retry_policy.validate():
                return False
            if not self.scheduling_requirements.validate():
                return False
            if not self.termination_criteria.validate():
                return False
            if not self.escalation_policy.validate():
                return False

            # Validate agent ID format
            if not isinstance(self.agent_id, str) or len(self.agent_id) < 3:
                return False

            # Validate version format (semantic version)
            version_parts = self.version.split('.')
            if len(version_parts) != 3 or not all(part.isdigit() for part in version_parts):
                return False

            return True

        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return False

    def can_execute_action(self, action_type: ActionType) -> bool:
        """Check if agent is permitted to execute specific action type"""
        if action_type in self.action_permissions.prohibited_actions:
            return False

        if action_type in [ActionType.PROPOSE_PLAN, ActionType.PROPOSE_CODE, ActionType.PROPOSE_ACTION]:
            return action_type in self.action_permissions.allowed_proposals
        elif action_type in [ActionType.VALIDATE]:
            return action_type in self.action_permissions.allowed_validations
        elif action_type in [ActionType.EXECUTE, ActionType.COMMUNICATE]:
            return action_type in self.action_permissions.allowed_executions

        return False

    def can_access_resource(self, resource_type: str, resource_path: str) -> bool:
        """Check if agent can access specific resource"""
        if resource_type == "read":
            return any(self._match_pattern(resource_path, pattern) for pattern in self.access_scope.readable_paths)
        elif resource_type == "write":
            return any(self._match_pattern(resource_path, pattern) for pattern in self.access_scope.writable_paths)
        elif resource_type == "network":
            return any(self._match_pattern(resource_path, pattern) for pattern in self.access_scope.network_endpoints)
        elif resource_type == "database":
            return any(self._match_pattern(resource_path, pattern) for pattern in self.access_scope.database_tables)

        return False

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Simple pattern matching (can be enhanced with regex)"""
        if "*" in pattern:
            # Basic wildcard support
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                return path.startswith(prefix) and path.endswith(suffix)
        return path == pattern

    def generate_hash(self) -> str:
        """Generate cryptographic hash of descriptor for integrity checking"""
        descriptor_dict = {
            "agent_id": self.agent_id,
            "version": self.version,
            "authority_band": self.authority_band.value,
            "resource_limits": self.resource_limits.__dict__,
            "access_scope": self.access_scope.__dict__,
            "action_permissions": {
                "allowed_proposals": [a.value for a in self.action_permissions.allowed_proposals],
                "allowed_validations": [v.value for v in self.action_permissions.allowed_validations],
                "allowed_executions": [e.value for e in self.action_permissions.allowed_executions],
                "prohibited_actions": [p.value for p in self.action_permissions.prohibited_actions]
            },
            "convergence_constraints": self.convergence_constraints.__dict__,
            "retry_policy": {
                "max_retries": self.retry_policy.max_retries,
                "min_backoff_ms": self.retry_policy.min_backoff_ms,
                "max_backoff_ms": self.retry_policy.max_backoff_ms,
                "retry_condition": self.retry_policy.retry_condition.value
            },
            "scheduling_requirements": self.scheduling_requirements.__dict__,
            "termination_criteria": {
                "success_conditions": [c.__dict__ for c in self.termination_criteria.success_conditions],
                "failure_conditions": [c.__dict__ for c in self.termination_criteria.failure_conditions],
                "timeout_conditions": [c.__dict__ for c in self.termination_criteria.timeout_conditions],
                "stability_conditions": [c.__dict__ for c in self.termination_criteria.stability_conditions],
                "refusal_conditions": [c.__dict__ for c in self.termination_criteria.refusal_conditions]
            },
            "escalation_policy": {
                "escalation_triggers": [t.__dict__ for t in self.escalation_policy.escalation_triggers],
                "required_authority_level": self.escalation_policy.required_authority_level.value,
                "escalation_timeout_ms": self.escalation_policy.escalation_timeout_ms
            }
        }

        json_str = json.dumps(descriptor_dict, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> Dict:
        """Convert descriptor to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "signature": self.signature,
            "created_at": self.created_at.isoformat(),
            "authority_band": self.authority_band.value,
            "resource_limits": self.resource_limits.__dict__,
            "access_scope": self.access_scope.__dict__,
            "action_permissions": {
                "allowed_proposals": [a.value for a in self.action_permissions.allowed_proposals],
                "allowed_validations": [v.value for v in self.action_permissions.allowed_validations],
                "allowed_executions": [e.value for e in self.action_permissions.allowed_executions],
                "prohibited_actions": [p.value for p in self.action_permissions.prohibited_actions]
            },
            "convergence_constraints": self.convergence_constraints.__dict__,
            "retry_policy": {
                "max_retries": self.retry_policy.max_retries,
                "min_backoff_ms": self.retry_policy.min_backoff_ms,
                "max_backoff_ms": self.retry_policy.max_backoff_ms,
                "retry_condition": self.retry_policy.retry_condition.value
            },
            "scheduling_requirements": {
                "priority": self.scheduling_requirements.priority.value,
                "cpu_reservation": self.scheduling_requirements.cpu_reservation,
                "memory_reservation": self.scheduling_requirements.memory_reservation,
                "deadline_ms": self.scheduling_requirements.deadline_ms,
                "dependencies": self.scheduling_requirements.dependencies,
                "exclusivity_group": self.scheduling_requirements.exclusivity_group
            },
            "termination_criteria": {
                "success_conditions": [c.__dict__ for c in self.termination_criteria.success_conditions],
                "failure_conditions": [c.__dict__ for c in self.termination_criteria.failure_conditions],
                "timeout_conditions": [c.__dict__ for c in self.termination_criteria.timeout_conditions],
                "stability_conditions": [c.__dict__ for c in self.termination_criteria.stability_conditions],
                "refusal_conditions": [c.__dict__ for c in self.termination_criteria.refusal_conditions]
            },
            "escalation_policy": {
                "escalation_triggers": [t.__dict__ for t in self.escalation_policy.escalation_triggers],
                "required_authority_level": self.escalation_policy.required_authority_level.value,
                "escalation_timeout_ms": self.escalation_policy.escalation_timeout_ms,
                "fallback_behavior": self.escalation_policy.fallback_behavior.__dict__ if self.escalation_policy.fallback_behavior else None,
                "escalation_paths": [p.__dict__ for p in self.escalation_policy.escalation_paths]
            }
        }


class AgentDescriptorValidator:
    """Validates agent descriptors against Murphy System requirements"""

    @staticmethod
    def validate_descriptor(descriptor: AgentDescriptor) -> Dict[str, any]:
        """Comprehensive validation of agent descriptor"""
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "authority_score": descriptor.authority_band.value,
            "risk_level": "LOW"
        }

        # Basic validation
        if not descriptor.validate():
            result["valid"] = False
            result["errors"].append("Descriptor failed basic validation")

        # Authority constraints
        if descriptor.authority_band == AuthorityBand.CRITICAL:
            result["risk_level"] = "HIGH"
            result["warnings"].append("Critical authority level requires additional oversight")

        # Resource constraints
        if descriptor.resource_limits.max_cpu_cores > 8:
            result["warnings"].append("High CPU allocation may impact system stability")

        if descriptor.resource_limits.max_memory_mb > 4096:
            result["warnings"].append("High memory allocation may impact system stability")

        # Stability constraints
        if descriptor.convergence_constraints.max_iterations > 10000:
            result["warnings"].append("Very high iteration limit may risk infinite loops")

        if descriptor.convergence_constraints.divergence_threshold > 0.5:
            result["warnings"].append("High divergence threshold may allow unstable behavior")

        # Retry policy
        if descriptor.retry_policy.max_retries > 10:
            result["risk_level"] = "MEDIUM"
            result["warnings"].append("High retry limit may waste resources")

        # Access scope
        if len(descriptor.access_scope.writable_paths) > 100:
            result["warnings"].append("Large write access scope increases security risk")

        if "*" in str(descriptor.access_scope.network_endpoints):
            result["risk_level"] = "MEDIUM"
            result["warnings"].append("Wildcard network access poses security risk")

        # Dependencies
        if len(descriptor.scheduling_requirements.dependencies) > 20:
            result["warnings"].append("Many dependencies increase complexity and failure risk")

        # Termination conditions
        if not descriptor.termination_criteria.timeout_conditions:
            result["errors"].append("Missing timeout termination conditions")
            result["valid"] = False

        if not descriptor.termination_criteria.refusal_conditions:
            result["warnings"].append("No refusal conditions specified")

        return result

    @staticmethod
    def check_invariants(descriptor: AgentDescriptor) -> List[str]:
        """Check descriptor against system invariants"""
        violations = []

        # Authority monotonicity check
        if descriptor.authority_band == AuthorityBand.NONE and descriptor.can_execute_action(ActionType.EXECUTE):
            violations.append("NONE authority cannot execute actions")

        # Resource bounds check
        total_resources = (
            descriptor.resource_limits.max_cpu_cores +
            descriptor.resource_limits.max_memory_mb / 512 +
            descriptor.resource_limits.max_api_calls_per_sec / 10
        )
        if total_resources > 20:  # Arbitrary resource limit
            violations.append("Total resource allocation exceeds system limits")

        # Stability bounds check
        if (descriptor.convergence_constraints.max_iterations *
            descriptor.convergence_constraints.stability_window_ms / 1000) > 3600:  # 1 hour
            violations.append("Maximum potential execution time exceeds stability limits")

        return violations
