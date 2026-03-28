"""
Agent Descriptor Implementation

Implements the formal Agent Descriptor schema and validation for the Murphy System.
Ensures agents operate within bounded authority, stability limits, and phase constraints.
"""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AuthorityBand(Enum):
    """Authority levels for agents"""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ActionType(Enum):
    """Types of actions agents may propose"""
    PROPOSE_PLAN = "propose_plan"
    PROPOSE_CODE = "propose_code"
    PROPOSE_ACTION = "propose_action"
    VALIDATE = "validate"
    EXECUTE = "execute"
    COMMUNICATE = "communicate"


class ValidationType(Enum):
    """Types of validation agents may perform"""
    SYMBOLIC_CHECK = "symbolic_check"
    DETERMINISTIC_TEST = "deterministic_test"
    EMPIRICAL_VALIDATION = "empirical_validation"
    PEER_REVIEW = "peer_review"


class ExecutionType(Enum):
    """Types of execution actions"""
    COMPUTE = "compute"
    TRANSFORM = "transform"
    COMMUNICATE = "communicate"
    STORE = "store"
    RETRIEVE = "retrieve"


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
    """Resource limits for agent execution"""
    max_cpu_cores: int
    max_memory_mb: int
    max_execution_time_sec: int
    max_api_calls_per_sec: int


@dataclass
class AccessMatrix:
    """Access control patterns for agent"""
    readable_paths: List[str] = field(default_factory=list)
    writable_paths: List[str] = field(default_factory=list)
    network_endpoints: List[str] = field(default_factory=list)
    database_tables: List[str] = field(default_factory=list)


@dataclass
class ActionSet:
    """Permitted action types for agent"""
    allowed_proposals: List[ActionType] = field(default_factory=list)
    allowed_validations: List[ValidationType] = field(default_factory=list)
    allowed_executions: List[ExecutionType] = field(default_factory=list)
    prohibited_actions: List[ActionType] = field(default_factory=list)


@dataclass
class ConvergenceSpec:
    """Stability and convergence constraints"""
    max_iterations: int
    convergence_threshold: float
    divergence_threshold: float
    stability_window_ms: int
    max_state_changes_per_window: int


@dataclass
class RetrySpec:
    """Retry policy specifications"""
    max_retries: int
    min_backoff_ms: int
    max_backoff_ms: int
    retry_condition: RetryCondition


@dataclass
class SchedulingSpec:
    """Scheduling requirements and constraints"""
    priority: PriorityLevel
    cpu_reservation: int
    memory_reservation: int
    deadline_ms: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)
    exclusivity_group: Optional[str] = None


@dataclass
class Condition:
    """Generic condition specification"""
    condition_type: str
    parameters: Dict[str, Any]
    required: bool = True


@dataclass
class TerminationSpec:
    """Conditions for agent termination"""
    success_conditions: List[Condition] = field(default_factory=list)
    failure_conditions: List[Condition] = field(default_factory=list)
    timeout_conditions: List[Condition] = field(default_factory=list)
    stability_conditions: List[Condition] = field(default_factory=list)
    refusal_conditions: List[Condition] = field(default_factory=list)


@dataclass
class Trigger:
    """Escalation trigger specification"""
    trigger_type: str
    condition: str
    threshold: Optional[float] = None
    time_window_ms: Optional[int] = None


@dataclass
class EscalationPath:
    """Approved escalation path"""
    target_authority: AuthorityBand
    approval_required: bool
    timeout_ms: int
    fallback_action: str


@dataclass
class EscalationSpec:
    """Escalation policy and procedures"""
    escalation_triggers: List[Trigger] = field(default_factory=list)
    required_authority_level: AuthorityBand = AuthorityBand.HIGH
    escalation_timeout_ms: int = 300000  # 5 minutes
    fallback_behavior: str = "TERMINATE"
    escalation_paths: List[EscalationPath] = field(default_factory=list)


@dataclass
class AgentDescriptor:
    """
    Formal Agent Descriptor for Murphy System

    Defines complete governance constraints, authority limits, and operational
    parameters for autonomous agents operating within the Murphy System.
    """
    # Identity
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    signature: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Authority Scope
    authority_band: AuthorityBand = AuthorityBand.NONE
    resource_limits: ResourceCaps = field(default_factory=lambda: ResourceCaps(
        max_cpu_cores=1,
        max_memory_mb=512,
        max_execution_time_sec=300,
        max_api_calls_per_sec=10
    ))
    access_scope: AccessMatrix = field(default_factory=AccessMatrix)

    # Permitted Action Types
    action_permissions: ActionSet = field(default_factory=ActionSet)

    # Stability Limits
    convergence_constraints: ConvergenceSpec = field(default_factory=lambda: ConvergenceSpec(
        max_iterations=100,
        convergence_threshold=0.05,
        divergence_threshold=0.1,
        stability_window_ms=300000,  # 5 minutes
        max_state_changes_per_window=10
    ))
    retry_policy: RetrySpec = field(default_factory=lambda: RetrySpec(
        max_retries=3,
        min_backoff_ms=1000,
        max_backoff_ms=30000,
        retry_condition=RetryCondition.STATE_CHANGE_REQUIRED
    ))

    # Scheduling Constraints
    scheduling_requirements: SchedulingSpec = field(default_factory=lambda: SchedulingSpec(
        priority=PriorityLevel.NORMAL,
        cpu_reservation=1,
        memory_reservation=256
    ))

    # Termination Conditions
    termination_criteria: TerminationSpec = field(default_factory=TerminationSpec)

    # Escalation Rules
    escalation_policy: EscalationSpec = field(default_factory=EscalationSpec)

    # Additional metadata
    owner: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate descriptor after initialization"""
        self.validate_basic_constraints()
        self.generate_hash()

    def validate_basic_constraints(self):
        """Validate basic descriptor constraints"""
        if not self.agent_id:
            raise ValueError("Agent ID is required")

        if not self.version:
            raise ValueError("Version is required")

        if self.resource_limits.max_cpu_cores <= 0:
            raise ValueError("Max CPU cores must be positive")

        if self.resource_limits.max_memory_mb <= 0:
            raise ValueError("Max memory must be positive")

        if self.resource_limits.max_execution_time_sec <= 0:
            raise ValueError("Max execution time must be positive")

        if self.convergence_constraints.max_iterations <= 0:
            raise ValueError("Max iterations must be positive")

        if not (0 <= self.convergence_constraints.convergence_threshold <= 1):
            raise ValueError("Convergence threshold must be between 0 and 1")

        if not (0 <= self.convergence_constraints.divergence_threshold <= 1):
            raise ValueError("Divergence threshold must be between 0 and 1")

    def generate_hash(self):
        """Generate cryptographic hash of descriptor"""
        descriptor_dict = self.to_dict()
        descriptor_json = json.dumps(descriptor_dict, sort_keys=True, default=str)
        self.signature = hashlib.sha256(descriptor_json.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert descriptor to dictionary"""
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "authority_band": self.authority_band.name,
            "resource_limits": {
                "max_cpu_cores": self.resource_limits.max_cpu_cores,
                "max_memory_mb": self.resource_limits.max_memory_mb,
                "max_execution_time_sec": self.resource_limits.max_execution_time_sec,
                "max_api_calls_per_sec": self.resource_limits.max_api_calls_per_sec
            },
            "access_scope": {
                "readable_paths": self.access_scope.readable_paths,
                "writable_paths": self.access_scope.writable_paths,
                "network_endpoints": self.access_scope.network_endpoints,
                "database_tables": self.access_scope.database_tables
            },
            "action_permissions": {
                "allowed_proposals": [a.name for a in self.action_permissions.allowed_proposals],
                "allowed_validations": [v.name for v in self.action_permissions.allowed_validations],
                "allowed_executions": [e.name for e in self.action_permissions.allowed_executions],
                "prohibited_actions": [a.name for a in self.action_permissions.prohibited_actions]
            },
            "convergence_constraints": {
                "max_iterations": self.convergence_constraints.max_iterations,
                "convergence_threshold": self.convergence_constraints.convergence_threshold,
                "divergence_threshold": self.convergence_constraints.divergence_threshold,
                "stability_window_ms": self.convergence_constraints.stability_window_ms,
                "max_state_changes_per_window": self.convergence_constraints.max_state_changes_per_window
            },
            "retry_policy": {
                "max_retries": self.retry_policy.max_retries,
                "min_backoff_ms": self.retry_policy.min_backoff_ms,
                "max_backoff_ms": self.retry_policy.max_backoff_ms,
                "retry_condition": self.retry_policy.retry_condition.name
            },
            "scheduling_requirements": {
                "priority": self.scheduling_requirements.priority.name,
                "cpu_reservation": self.scheduling_requirements.cpu_reservation,
                "memory_reservation": self.scheduling_requirements.memory_reservation,
                "deadline_ms": self.scheduling_requirements.deadline_ms,
                "dependencies": self.scheduling_requirements.dependencies,
                "exclusivity_group": self.scheduling_requirements.exclusivity_group
            },
            "termination_criteria": {
                "success_conditions": [{"type": c.condition_type, "params": c.parameters} for c in self.termination_criteria.success_conditions],
                "failure_conditions": [{"type": c.condition_type, "params": c.parameters} for c in self.termination_criteria.failure_conditions],
                "timeout_conditions": [{"type": c.condition_type, "params": c.parameters} for c in self.termination_criteria.timeout_conditions],
                "stability_conditions": [{"type": c.condition_type, "params": c.parameters} for c in self.termination_criteria.stability_conditions],
                "refusal_conditions": [{"type": c.condition_type, "params": c.parameters} for c in self.termination_criteria.refusal_conditions]
            },
            "escalation_policy": {
                "escalation_triggers": [{"type": t.trigger_type, "condition": t.condition} for t in self.escalation_policy.escalation_triggers],
                "required_authority_level": self.escalation_policy.required_authority_level.name,
                "escalation_timeout_ms": self.escalation_policy.escalation_timeout_ms,
                "fallback_behavior": self.escalation_policy.fallback_behavior
            },
            "owner": self.owner,
            "description": self.description,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentDescriptor':
        """Create descriptor from dictionary"""
        # Convert enum values back to enums
        data["authority_band"] = AuthorityBand[data["authority_band"]]
        data["scheduling_requirements"]["priority"] = PriorityLevel[data["scheduling_requirements"]["priority"]]
        data["retry_policy"]["retry_condition"] = RetryCondition[data["retry_policy"]["retry_condition"]]
        data["escalation_policy"]["required_authority_level"] = AuthorityBand[data["escalation_policy"]["required_authority_level"]]

        # Convert action permissions
        if "action_permissions" in data:
            ap = data["action_permissions"]
            data["action_permissions"] = ActionSet(
                allowed_proposals=[ActionType[a] for a in ap.get("allowed_proposals", [])],
                allowed_validations=[ValidationType[v] for v in ap.get("allowed_validations", [])],
                allowed_executions=[ExecutionType[e] for e in ap.get("allowed_executions", [])],
                prohibited_actions=[ActionType[a] for a in ap.get("prohibited_actions", [])]
            )

        # Convert datetime
        if "created_at" in data:
            data["created_at"] = datetime.fromisoformat(data["created_at"])

        # Create descriptor
        descriptor = cls(**data)
        return descriptor

    def can_execute_action(self, action_type: ActionType) -> bool:
        """Check if agent is permitted to execute specific action type"""
        if action_type in self.action_permissions.prohibited_actions:
            return False

        if action_type in [ActionType.PROPOSE_PLAN, ActionType.PROPOSE_CODE, ActionType.PROPOSE_ACTION]:
            return action_type in self.action_permissions.allowed_proposals
        elif action_type == ActionType.VALIDATE:
            return True  # Validation is generally permitted
        elif action_type == ActionType.EXECUTE:
            return action_type in self.action_permissions.allowed_executions
        elif action_type == ActionType.COMMUNICATE:
            return action_type in self.action_permissions.allowed_executions

        return False

    def has_sufficient_authority(self, required_band: AuthorityBand) -> bool:
        """Check if agent has sufficient authority for required level"""
        return self.authority_band.value >= required_band.value

    def is_within_resource_limits(self, cpu: int, memory: int, time_sec: int) -> bool:
        """Check if resource usage is within limits"""
        return (cpu <= self.resource_limits.max_cpu_cores and
                memory <= self.resource_limits.max_memory_mb and
                time_sec <= self.resource_limits.max_execution_time_sec)


class AgentDescriptorValidator:
    """Validates agent descriptors against Murphy System constraints"""

    def __init__(self):
        self.validation_rules = [
            self.validate_authority_consistency,
            self.validate_resource_limits,
            self.validate_action_permissions,
            self.validate_stability_constraints,
            self.validate_termination_conditions,
            self.validate_escalation_policy
        ]

    def validate(self, descriptor: AgentDescriptor) -> tuple[bool, List[str]]:
        """Validate descriptor against all rules"""
        errors = []

        for rule in self.validation_rules:
            try:
                rule_errors = rule(descriptor)
                errors.extend(rule_errors)
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                errors.append(f"Validation rule error: {str(exc)}")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_authority_consistency(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate authority band consistency with other parameters"""
        errors = []

        # High authority requires more resources
        if descriptor.authority_band.value >= AuthorityBand.HIGH.value:
            if descriptor.resource_limits.max_cpu_cores < 2:
                errors.append("High authority agents require at least 2 CPU cores")
            if descriptor.resource_limits.max_memory_mb < 1024:
                errors.append("High authority agents require at least 1GB memory")

        # Critical authority requires specific configurations
        if descriptor.authority_band == AuthorityBand.CRITICAL:
            if not descriptor.escalation_policy.escalation_paths:
                errors.append("Critical authority agents must have escalation paths defined")
            if descriptor.scheduling_requirements.priority != PriorityLevel.REALTIME:
                errors.append("Critical authority agents must have REALTIME priority")

        return errors

    def validate_resource_limits(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate resource limit constraints"""
        errors = []

        # Check for reasonable resource limits
        if descriptor.resource_limits.max_execution_time_sec > 86400:  # 24 hours
            errors.append("Maximum execution time cannot exceed 24 hours without escalation")

        if descriptor.resource_limits.max_api_calls_per_sec > 1000:
            errors.append("API call rate limit cannot exceed 1000 per second")

        # Validate reservations don't exceed limits
        if descriptor.scheduling_requirements.cpu_reservation > descriptor.resource_limits.max_cpu_cores:
            errors.append("CPU reservation cannot exceed maximum CPU cores")

        if descriptor.scheduling_requirements.memory_reservation > descriptor.resource_limits.max_memory_mb:
            errors.append("Memory reservation cannot exceed maximum memory")

        return errors

    def validate_action_permissions(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate action permission consistency"""
        errors = []

        # Check for prohibited actions in allowed lists
        prohibited_in_allowed = set(descriptor.action_permissions.prohibited_actions) & \
                               set(descriptor.action_permissions.allowed_proposals +
                                   descriptor.action_permissions.allowed_executions)

        if prohibited_in_allowed:
            errors.append(f"Prohibited actions found in allowed lists: {[a.name for a in prohibited_in_allowed]}")

        # Low authority agents have restricted actions
        if descriptor.authority_band == AuthorityBand.LOW:
            dangerous_actions = [ActionType.EXECUTE, ActionType.PROPOSE_ACTION]
            for action in dangerous_actions:
                if action in descriptor.action_permissions.allowed_executions:
                    errors.append(f"Low authority agents cannot execute {action.name}")

        return errors

    def validate_stability_constraints(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate stability and convergence constraints"""
        errors = []

        # Convergence threshold should be reasonable
        if descriptor.convergence_constraints.convergence_threshold > descriptor.convergence_constraints.divergence_threshold:
            errors.append("Convergence threshold cannot be greater than divergence threshold")

        # Stability window should be reasonable for iteration count
        min_window_for_iterations = descriptor.convergence_constraints.max_iterations * 100  # 100ms per iteration
        if descriptor.convergence_constraints.stability_window_ms < min_window_for_iterations:
            errors.append("Stability window too small for max iterations")

        # Retry policy should be reasonable
        if descriptor.retry_policy.max_retries > 10:
            errors.append("Maximum retries cannot exceed 10 without escalation")

        return errors

    def validate_termination_conditions(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate termination condition specifications"""
        errors = []

        # At least one termination condition should be specified
        all_conditions = (descriptor.termination_criteria.success_conditions +
                          descriptor.termination_criteria.failure_conditions +
                          descriptor.termination_criteria.timeout_conditions)

        if not all_conditions:
            errors.append("At least one termination condition must be specified")

        # Timeout conditions should be reasonable
        for condition in descriptor.termination_criteria.timeout_conditions:
            if "timeout_ms" in condition.parameters:
                timeout_ms = condition.parameters["timeout_ms"]
                if timeout_ms > descriptor.resource_limits.max_execution_time_sec * 1000:
                    errors.append("Timeout condition exceeds maximum execution time")

        return errors

    def validate_escalation_policy(self, descriptor: AgentDescriptor) -> List[str]:
        """Validate escalation policy specifications"""
        errors = []

        # Escalation timeout should be reasonable
        if descriptor.escalation_policy.escalation_timeout_ms > 3600000:  # 1 hour
            errors.append("Escalation timeout cannot exceed 1 hour")

        # Required authority level should be higher than current
        if descriptor.escalation_policy.required_authority_level.value <= descriptor.authority_band.value:
            errors.append("Required escalation authority must be higher than current authority")

        # Escalation paths should be valid
        for path in descriptor.escalation_policy.escalation_paths:
            if path.target_authority.value <= descriptor.authority_band.value:
                errors.append("Escalation path target authority must be higher than current authority")

        return errors


def create_standard_descriptor(
    agent_id: str,
    authority_band: AuthorityBand = AuthorityBand.MEDIUM,
    max_execution_time_sec: int = 300,
    max_retries: int = 3
) -> AgentDescriptor:
    """Create a standard agent descriptor with common defaults"""

    descriptor = AgentDescriptor(
        agent_id=agent_id,
        authority_band=authority_band,
        resource_limits=ResourceCaps(
            max_cpu_cores=2 if authority_band.value >= AuthorityBand.HIGH.value else 1,
            max_memory_mb=1024 if authority_band.value >= AuthorityBand.HIGH.value else 512,
            max_execution_time_sec=max_execution_time_sec,
            max_api_calls_per_sec=50 if authority_band.value >= AuthorityBand.HIGH.value else 10
        ),
        action_permissions=ActionSet(
            allowed_proposals=[ActionType.PROPOSE_PLAN, ActionType.PROPOSE_CODE],
            allowed_validations=[ValidationType.SYMBOLIC_CHECK, ValidationType.DETERMINISTIC_TEST],
            allowed_executions=[ActionType.COMPUTE, ActionType.TRANSFORM]
        ),
        retry_policy=RetrySpec(
            max_retries=max_retries,
            min_backoff_ms=1000,
            max_backoff_ms=30000,
            retry_condition=RetryCondition.STATE_CHANGE_REQUIRED
        ),
        scheduling_requirements=SchedulingSpec(
            priority=PriorityLevel.HIGH if authority_band.value >= AuthorityBand.HIGH.value else PriorityLevel.NORMAL,
            cpu_reservation=1,
            memory_reservation=256
        )
    )

    return descriptor
