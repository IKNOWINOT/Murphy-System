"""
Core data models for Execution Packet Compiler
Defines execution packets, scopes, graphs, interfaces, and telemetry
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PacketState(Enum):
    """States of an execution packet"""
    COMPILING = "compiling"           # Being compiled
    SEALED = "sealed"                 # Compilation complete, ready for execution
    EXECUTING = "executing"           # Currently executing
    COMPLETED = "completed"           # Execution completed successfully
    FAILED = "failed"                 # Execution failed
    ABORTED = "aborted"              # Execution aborted
    INVALIDATED = "invalidated"      # Packet invalidated (scope changed, confidence dropped, etc.)


class StepType(Enum):
    """Types of execution steps"""
    API_CALL = "api_call"             # Call to external API
    MATH_MODULE = "math_module"       # Mathematical computation
    CODE_BLOCK = "code_block"         # Verified code execution
    ACTUATOR_COMMAND = "actuator_command"  # Physical actuator command
    DATA_TRANSFORM = "data_transform"  # Data transformation


class InterfaceType(Enum):
    """Types of interfaces"""
    API = "api"
    BOT = "bot"
    SENSOR = "sensor"
    ROBOT = "robot"
    DATABASE = "database"
    FILESYSTEM = "filesystem"


@dataclass
class ExecutionScope:
    """
    Immutable snapshot of execution scope

    After creation, no further artifact creation allowed
    """
    scope_id: str
    artifact_ids: List[str]
    constraints: List[Dict[str, Any]]
    parameters: Dict[str, Any]
    interface_bindings: Dict[str, str]  # interface_name -> interface_id
    timestamp: datetime = field(default_factory=datetime.now)
    frozen: bool = False

    def freeze(self) -> str:
        """
        Freeze scope and return hash

        Returns:
            SHA-256 hash of scope
        """
        if self.frozen:
            return self.calculate_hash()

        self.frozen = True
        return self.calculate_hash()

    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of scope"""
        content = {
            'scope_id': self.scope_id,
            'artifact_ids': sorted(self.artifact_ids),
            'constraints': self.constraints,
            'parameters': self.parameters,
            'interface_bindings': self.interface_bindings
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate scope

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        if not self.artifact_ids:
            errors.append("Scope has no artifacts")

        if not self.frozen:
            errors.append("Scope not frozen")

        # Check for unresolved dependencies (would be checked by caller)

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'scope_id': self.scope_id,
            'artifact_ids': self.artifact_ids,
            'constraints': self.constraints,
            'parameters': self.parameters,
            'interface_bindings': self.interface_bindings,
            'timestamp': self.timestamp.isoformat(),
            'frozen': self.frozen,
            'hash': self.calculate_hash() if self.frozen else None
        }


@dataclass
class ExecutionStep:
    """
    Single deterministic execution step

    DESIGN LAW: No LLM calls allowed
    """
    step_id: str
    step_type: StepType
    description: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)  # step_ids this depends on
    interface_binding: Optional[str] = None  # interface to use
    deterministic: bool = True
    verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_determinism(self) -> tuple[bool, str]:
        """
        Validate that step is deterministic

        Returns:
            (is_deterministic, reason)
        """
        if not self.deterministic:
            return False, "Step marked as non-deterministic"

        # Check for LLM-related keywords
        llm_keywords = ['llm', 'gpt', 'generate', 'creative', 'sample']
        description_lower = self.description.lower()

        for keyword in llm_keywords:
            if keyword in description_lower:
                return False, f"Step description contains LLM keyword: {keyword}"

        # Verify step type is allowed
        if self.step_type not in [StepType.API_CALL, StepType.MATH_MODULE,
                                   StepType.CODE_BLOCK, StepType.ACTUATOR_COMMAND,
                                   StepType.DATA_TRANSFORM]:
            return False, f"Invalid step type: {self.step_type}"

        return True, "Step is deterministic"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'step_id': self.step_id,
            'step_type': self.step_type.value,
            'description': self.description,
            'inputs': self.inputs,
            'outputs': self.outputs,
            'dependencies': self.dependencies,
            'interface_binding': self.interface_binding,
            'deterministic': self.deterministic,
            'verified': self.verified,
            'metadata': self.metadata
        }


@dataclass
class ExecutionGraph:
    """
    Execution DAG - strict ordering of deterministic steps

    No branching allowed without explicit gate
    """
    graph_id: str
    steps: Dict[str, ExecutionStep] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # step_id -> [dependent_step_ids]

    def add_step(self, step: ExecutionStep) -> None:
        """Add step to graph"""
        self.steps[step.step_id] = step
        if step.step_id not in self.edges:
            self.edges[step.step_id] = []

        # Add edges from dependencies
        for dep_id in step.dependencies:
            if dep_id not in self.edges:
                self.edges[dep_id] = []
            if step.step_id not in self.edges[dep_id]:
                self.edges[dep_id].append(step.step_id)

    def is_dag(self) -> bool:
        """Check if graph is a DAG (no cycles)"""
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            for dependent_id in self.edges.get(step_id, []):
                if dependent_id not in visited:
                    if has_cycle(dependent_id):
                        return True
                elif dependent_id in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step_id in self.steps:
            if step_id not in visited:
                if has_cycle(step_id):
                    return False

        return True

    def get_execution_order(self) -> List[str]:
        """
        Get topological sort of steps (execution order)

        Returns:
            List of step IDs in execution order
        """
        if not self.is_dag():
            return []

        in_degree = {step_id: 0 for step_id in self.steps}

        for step_id in self.steps:
            for dependent_id in self.edges.get(step_id, []):
                in_degree[dependent_id] += 1

        queue = [step_id for step_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            step_id = queue.pop(0)
            result.append(step_id)

            for dependent_id in self.edges.get(step_id, []):
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)

        return result if len(result) == len(self.steps) else []

    def validate_determinism(self) -> tuple[bool, List[str]]:
        """
        Validate that all steps are deterministic

        Returns:
            (all_deterministic, error_messages)
        """
        errors = []

        for step in self.steps.values():
            is_det, reason = step.validate_determinism()
            if not is_det:
                errors.append(f"Step {step.step_id}: {reason}")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'graph_id': self.graph_id,
            'steps': {sid: step.to_dict() for sid, step in self.steps.items()},
            'edges': self.edges,
            'is_dag': self.is_dag(),
            'execution_order': self.get_execution_order(),
            'step_count': len(self.steps)
        }


@dataclass
class InterfaceBinding:
    """Binding to a specific interface"""
    interface_id: str
    interface_type: InterfaceType
    interface_name: str
    capabilities: List[str]
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'interface_id': self.interface_id,
            'interface_type': self.interface_type.value,
            'interface_name': self.interface_name,
            'capabilities': self.capabilities,
            'constraints': self.constraints
        }


@dataclass
class InterfaceMap:
    """
    Map of allowed interfaces

    Defines what the execution packet is allowed to interact with
    """
    allowed_apis: List[InterfaceBinding] = field(default_factory=list)
    allowed_bots: List[InterfaceBinding] = field(default_factory=list)
    allowed_sensors: List[InterfaceBinding] = field(default_factory=list)
    allowed_robots: List[InterfaceBinding] = field(default_factory=list)

    def get_interface(self, interface_id: str) -> Optional[InterfaceBinding]:
        """Get interface by ID"""
        all_interfaces = (
            self.allowed_apis +
            self.allowed_bots +
            self.allowed_sensors +
            self.allowed_robots
        )

        for interface in all_interfaces:
            if interface.interface_id == interface_id:
                return interface

        return None

    def is_allowed(self, interface_id: str) -> bool:
        """Check if interface is allowed"""
        return self.get_interface(interface_id) is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'allowed_apis': [api.to_dict() for api in self.allowed_apis],
            'allowed_bots': [bot.to_dict() for bot in self.allowed_bots],
            'allowed_sensors': [sensor.to_dict() for sensor in self.allowed_sensors],
            'allowed_robots': [robot.to_dict() for robot in self.allowed_robots],
            'total_interfaces': (
                len(self.allowed_apis) +
                len(self.allowed_bots) +
                len(self.allowed_sensors) +
                len(self.allowed_robots)
            )
        }


@dataclass
class RollbackStep:
    """Single rollback step"""
    step_id: str
    description: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'step_id': self.step_id,
            'description': self.description,
            'action': self.action,
            'parameters': self.parameters
        }


@dataclass
class RollbackPlan:
    """
    Plan for rolling back execution if needed

    Defines safe stop procedures
    """
    plan_id: str
    steps: List[RollbackStep] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)  # Conditions that trigger rollback

    def add_step(self, step: RollbackStep) -> None:
        """Add rollback step"""
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'plan_id': self.plan_id,
            'steps': [step.to_dict() for step in self.steps],
            'triggers': self.triggers,
            'step_count': len(self.steps)
        }


@dataclass
class TelemetryConfig:
    """Configuration for telemetry collection"""
    metric_name: str
    collection_interval: float  # seconds
    thresholds: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'metric_name': self.metric_name,
            'collection_interval': self.collection_interval,
            'thresholds': self.thresholds
        }


@dataclass
class TelemetryPlan:
    """
    Plan for collecting telemetry during execution
    """
    plan_id: str
    configs: List[TelemetryConfig] = field(default_factory=list)

    def add_config(self, config: TelemetryConfig) -> None:
        """Add telemetry configuration"""
        self.configs.append(config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'plan_id': self.plan_id,
            'configs': [config.to_dict() for config in self.configs],
            'config_count': len(self.configs)
        }


@dataclass
class ExecutionPacket:
    """
    Sealed execution packet

    DESIGN LAW: No packet may contain uncertainty

    Signature binds:
    - artifacts
    - constraints
    - authority state

    Any mutation invalidates packet
    """
    packet_id: str
    scope: ExecutionScope
    execution_graph: ExecutionGraph
    interfaces: InterfaceMap
    rollback_plan: RollbackPlan
    telemetry_plan: TelemetryPlan

    # State
    state: PacketState = PacketState.COMPILING

    # Authority snapshot
    confidence: float = 0.0
    authority_band: str = ""
    phase: str = ""

    # Signature
    signature: Optional[str] = None
    signed_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    sealed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def seal(self, confidence: float, authority_band: str, phase: str) -> str:
        """
        Seal packet with signature

        Args:
            confidence: Current confidence
            authority_band: Current authority band
            phase: Current phase

        Returns:
            Signature hash
        """
        if self.state != PacketState.COMPILING:
            raise ValueError(f"Cannot seal packet in state {self.state}")

        # Freeze scope
        scope_hash = self.scope.freeze()

        # Store authority snapshot
        self.confidence = confidence
        self.authority_band = authority_band
        self.phase = phase

        # Store timestamp BEFORE generating signature
        self.signed_at = datetime.now(timezone.utc)
        self.sealed_at = self.signed_at

        # Generate signature
        signature_content = {
            'packet_id': self.packet_id,
            'scope_hash': scope_hash,
            'execution_graph_id': self.execution_graph.graph_id,
            'confidence': confidence,
            'authority_band': authority_band,
            'phase': phase,
            'timestamp': self.signed_at.isoformat()
        }

        signature_str = json.dumps(signature_content, sort_keys=True)
        self.signature = hashlib.sha256(signature_str.encode()).hexdigest()
        self.state = PacketState.SEALED

        return self.signature

    def verify_signature(self) -> bool:
        """
        Verify packet signature

        Returns:
            True if signature is valid
        """
        if not self.signature or not self.signed_at:
            return False

        # Recalculate signature
        scope_hash = self.scope.calculate_hash()

        signature_content = {
            'packet_id': self.packet_id,
            'scope_hash': scope_hash,
            'execution_graph_id': self.execution_graph.graph_id,
            'confidence': self.confidence,
            'authority_band': self.authority_band,
            'phase': self.phase,
            'timestamp': self.signed_at.isoformat()
        }

        signature_str = json.dumps(signature_content, sort_keys=True)
        expected_signature = hashlib.sha256(signature_str.encode()).hexdigest()

        return self.signature == expected_signature

    def invalidate(self, reason: str) -> None:
        """
        Invalidate packet

        Args:
            reason: Reason for invalidation
        """
        self.state = PacketState.INVALIDATED
        self.metadata['invalidation_reason'] = reason
        self.metadata['invalidated_at'] = datetime.now(timezone.utc).isoformat()

    def can_execute(self) -> tuple[bool, List[str]]:
        """
        Check if packet can be executed

        Returns:
            (can_execute, blockers)
        """
        blockers = []

        if self.state != PacketState.SEALED:
            blockers.append(f"Packet not sealed (state: {self.state.value})")

        if not self.verify_signature():
            blockers.append("Signature verification failed")

        if not self.scope.frozen:
            blockers.append("Scope not frozen")

        if not self.execution_graph.is_dag():
            blockers.append("Execution graph is not a DAG")

        is_det, det_errors = self.execution_graph.validate_determinism()
        if not is_det:
            blockers.extend(det_errors)

        return len(blockers) == 0, blockers

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'packet_id': self.packet_id,
            'scope': self.scope.to_dict(),
            'execution_graph': self.execution_graph.to_dict(),
            'interfaces': self.interfaces.to_dict(),
            'rollback_plan': self.rollback_plan.to_dict(),
            'telemetry_plan': self.telemetry_plan.to_dict(),
            'state': self.state.value,
            'authority_snapshot': {
                'confidence': self.confidence,
                'authority_band': self.authority_band,
                'phase': self.phase
            },
            'signature': self.signature,
            'signed_at': self.signed_at.isoformat() if self.signed_at else None,
            'created_at': self.created_at.isoformat(),
            'sealed_at': self.sealed_at.isoformat() if self.sealed_at else None,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'metadata': self.metadata,
            'can_execute': self.can_execute()[0]
        }
