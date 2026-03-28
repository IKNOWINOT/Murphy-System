"""
Module Instance Manager for Murphy System

Implements dynamic module instantiation with:
- Unique instance IDs for all module instances
- Spawn/despawn lifecycle management
- Configuration backward logic for auditing
- Viability checking before module loading
- Resource-efficient lazy loading
- Integration with existing TriageRollcallAdapter and ModuleRegistry

Design Principles Applied:
- Single Responsibility: Each class handles one concern
- Open/Closed: Extensible via plugins without modification
- Dependency Inversion: Depends on abstractions, not concretions
- Interface Segregation: Small, focused interfaces
- DRY: Reuses existing patterns from triage_rollcall_adapter and module_registry

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, Union

# Import existing patterns for integration
try:
    from .triage_rollcall_adapter import (
        BotCandidate,
        CandidateStatus,
        TriageRollcallAdapter,
    )
    from .module_registry import ModuleDescriptor, ModuleStatus, ModuleRegistry
except ImportError:
    # Allow standalone usage
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InstanceState(str, Enum):
    """Lifecycle states for a module instance."""
    SPAWNING = "spawning"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DESPAWNING = "despawning"
    DESPAWNED = "despawned"


class ViabilityResult(str, Enum):
    """Results of viability checking."""
    VIABLE = "viable"
    NOT_VIABLE = "not_viable"
    INSUFFICIENT_RESOURCES = "insufficient_resources"
    DEPENDENCY_MISSING = "dependency_missing"
    ALREADY_SPAWNED = "already_spawned"
    BLACKLISTED = "blacklisted"


class SpawnDecision(str, Enum):
    """Decision outcomes for spawn requests."""
    APPROVED = "approved"
    DENIED_BUDGET = "denied_budget"
    DENIED_DEPTH = "denied_depth"
    DENIED_CIRCUIT = "denied_circuit"
    DENIED_BLACKLIST = "denied_blacklist"
    DENIED_DEPENDENCY = "denied_dependency"


# ---------------------------------------------------------------------------
# Audit Trail
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """Single audit entry for configuration backward logic."""
    timestamp: datetime
    instance_id: str
    module_type: str
    action: str  # spawn, despawn, execute, error, config_change
    actor: str  # system, user_id, or automated
    details: Dict[str, Any]
    parent_instance_id: Optional[str] = None
    correlation_id: Optional[str] = None  # Links related operations
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "instance_id": self.instance_id,
            "module_type": self.module_type,
            "action": self.action,
            "actor": self.actor,
            "details": self.details,
            "parent_instance_id": self.parent_instance_id,
            "correlation_id": self.correlation_id,
        }


@dataclass
class ConfigurationSnapshot:
    """Captures full configuration state for backward logic."""
    snapshot_id: str
    instance_id: str
    timestamp: datetime
    config: Dict[str, Any]
    source_config: Optional[str] = None  # Path or reference to source config
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            config_str = json.dumps(self.config, sort_keys=True)
            self.checksum = hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp.isoformat(),
            "config": self.config,
            "source_config": self.source_config,
            "checksum": self.checksum,
        }


# ---------------------------------------------------------------------------
# Resource Profile
# ---------------------------------------------------------------------------

@dataclass
class ResourceProfile:
    """Resource requirements for a module instance."""
    cpu_cores: float = 1.0
    memory_mb: int = 512
    max_concurrent: int = 1
    timeout_seconds: int = 300
    priority: int = 5  # 1-10, higher is more important
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "max_concurrent": self.max_concurrent,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# Module Instance
# ---------------------------------------------------------------------------

@dataclass
class ModuleInstance:
    """
    Represents a single spawned module instance with unique ID.
    
    This is the core data structure for the instance management system.
    Each instance has:
    - Unique instance_id for tracking and auditing
    - Module type reference for capability lookup
    - State lifecycle tracking
    - Configuration snapshot for backward logic
    - Resource profile for viability checking
    """
    instance_id: str
    module_type: str
    state: InstanceState
    spawned_at: datetime
    config: Dict[str, Any]
    resource_profile: ResourceProfile
    capabilities: List[str] = field(default_factory=list)
    parent_instance_id: Optional[str] = None
    spawn_depth: int = 0
    actor: str = "system"
    correlation_id: Optional[str] = None
    last_activity: Optional[datetime] = None
    execution_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _instance_object: Any = field(default=None, repr=False)
    _config_snapshot: Optional[ConfigurationSnapshot] = None
    
    def __post_init__(self):
        if self.last_activity is None:
            self.last_activity = self.spawned_at
        if self._config_snapshot is None and self.config:
            self._config_snapshot = ConfigurationSnapshot(
                snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
                instance_id=self.instance_id,
                timestamp=self.spawned_at,
                config=self.config,
            )
    
    def is_available(self) -> bool:
        """Check if instance can accept new work."""
        return self.state in (InstanceState.ACTIVE, InstanceState.IDLE)
    
    def is_active(self) -> bool:
        """Check if instance is alive (not despawned)."""
        return self.state not in (InstanceState.DESPAWNED, InstanceState.ERROR)
    
    def record_execution(self):
        """Record a successful execution."""
        self.execution_count += 1
        self.last_activity = datetime.now(timezone.utc)
    
    def record_error(self, error: str):
        """Record an error occurrence."""
        self.error_count += 1
        self.last_error = error
        self.last_activity = datetime.now(timezone.utc)
    
    def get_config_snapshot(self) -> Optional[ConfigurationSnapshot]:
        """Get the configuration snapshot for audit trail."""
        return self._config_snapshot
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "module_type": self.module_type,
            "state": self.state.value,
            "spawned_at": self.spawned_at.isoformat(),
            "config": self.config,
            "resource_profile": self.resource_profile.to_dict(),
            "capabilities": self.capabilities,
            "parent_instance_id": self.parent_instance_id,
            "spawn_depth": self.spawn_depth,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Viability Checker Protocol
# ---------------------------------------------------------------------------

class ViabilityChecker(Protocol):
    """Protocol for viability checking implementations."""
    
    def check_viability(
        self,
        module_type: str,
        request: Dict[str, Any],
        context: Dict[str, Any],
    ) -> tuple[ViabilityResult, str]:
        """Check if a module is viable for a given request."""
        ...


class DefaultViabilityChecker:
    """Default viability checker implementation."""
    
    def __init__(self, manager: 'ModuleInstanceManager'):
        self._manager = manager
    
    def check_viability(
        self,
        module_type: str,
        request: Dict[str, Any],
        context: Dict[str, Any],
    ) -> tuple[ViabilityResult, str]:
        """
        Check viability based on:
        1. Module type is registered
        2. Required capabilities match request
        3. Resources are available
        4. Dependencies are satisfied
        """
        # Check if module type is known
        if module_type not in self._manager._module_types:
            return (ViabilityResult.NOT_VIABLE, f"Unknown module type: {module_type}")
        
        # Check blacklist
        if module_type in self._manager._blacklist:
            return (ViabilityResult.BLACKLISTED, f"Module type {module_type} is blacklisted")
        
        # Get module type info
        type_info = self._manager._module_types[module_type]
        
        # Check capabilities match
        required_caps = type_info.get("capabilities", [])
        request_needs = context.get("required_capabilities", [])
        
        if request_needs:
            missing = set(request_needs) - set(required_caps)
            if missing:
                return (
                    ViabilityResult.NOT_VIABLE,
                    f"Missing capabilities: {missing}"
                )
        
        # Check resources
        available = self._manager.get_available_resources()
        required = type_info.get("resource_profile", ResourceProfile())
        
        if available["cpu_available"] < required.cpu_cores:
            return (
                ViabilityResult.INSUFFICIENT_RESOURCES,
                f"Insufficient CPU: need {required.cpu_cores}, have {available['cpu_available']}"
            )
        
        if available["memory_available_mb"] < required.memory_mb:
            return (
                ViabilityResult.INSUFFICIENT_RESOURCES,
                f"Insufficient memory: need {required.memory_mb}MB, have {available['memory_available_mb']}MB"
            )
        
        # Check dependencies
        dependencies = type_info.get("dependencies", [])
        for dep in dependencies:
            dep_instances = self._manager.get_instances_by_type(dep)
            if not dep_instances:
                return (
                    ViabilityResult.DEPENDENCY_MISSING,
                    f"Dependency not available: {dep}"
                )
        
        return (ViabilityResult.VIABLE, "Module is viable for request")


# ---------------------------------------------------------------------------
# Module Instance Manager
# ---------------------------------------------------------------------------

class ModuleInstanceManager:
    """
    Central manager for dynamic module instantiation.
    
    Features:
    - Spawn/despawn module instances on command
    - Unique ID tracking for all instances
    - Viability checking before spawning
    - Audit trail for configuration backward logic
    - Resource management and budget awareness
    - Integration with existing TriageRollcallAdapter and ModuleRegistry
    
    Thread-safe for concurrent access.
    """
    
    def __init__(
        self,
        total_cpu_budget: float = 16.0,
        total_memory_budget_mb: int = 16384,
        max_spawn_depth: int = 5,
        max_instances_per_type: int = 10,
        audit_retention_count: int = 10000,
    ):
        self._lock = threading.RLock()
        
        # Instance storage
        self._instances: Dict[str, ModuleInstance] = {}
        self._instances_by_type: Dict[str, List[str]] = {}
        
        # Module type registry
        self._module_types: Dict[str, Dict[str, Any]] = {}
        self._blacklist: set = set()
        
        # Resource management
        self._total_cpu = total_cpu_budget
        self._total_memory_mb = total_memory_budget_mb
        self._max_spawn_depth = max_spawn_depth
        self._max_instances_per_type = max_instances_per_type
        
        # Audit trail
        self._audit_log: List[AuditEntry] = []
        self._audit_retention = audit_retention_count
        self._config_snapshots: Dict[str, ConfigurationSnapshot] = {}
        
        # Viability checker
        self._viability_checker = DefaultViabilityChecker(self)
        
        # Circuit breaker for spawn protection
        self._circuit_failures = 0
        self._circuit_threshold = 5
        self._circuit_open = False
        self._circuit_last_failure: Optional[float] = None
        self._circuit_recovery_seconds = 30.0
        
        # ID counter for deterministic IDs (optional)
        self._id_counter = 0
        
        logger.info(
            "ModuleInstanceManager initialized: cpu=%.1f, memory=%dMB, max_depth=%d",
            total_cpu_budget, total_memory_budget_mb, max_spawn_depth
        )
    
    # ------------------------------------------------------------------
    # Module Type Registration
    # ------------------------------------------------------------------
    
    def register_module_type(
        self,
        module_type: str,
        capabilities: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        resource_profile: Optional[ResourceProfile] = None,
        factory: Optional[Callable] = None,
        config_schema: Optional[Dict] = None,
    ) -> bool:
        """
        Register a module type that can be spawned.
        
        Args:
            module_type: Unique identifier for this module type
            capabilities: List of capability strings
            dependencies: List of required module types
            resource_profile: Resource requirements
            factory: Optional factory function to create instances
            config_schema: Optional JSON schema for configuration validation
            
        Returns:
            True if registered successfully
        """
        with self._lock:
            if module_type in self._module_types:
                logger.warning("Module type %s already registered, updating", module_type)
            
            self._module_types[module_type] = {
                "capabilities": capabilities or [],
                "dependencies": dependencies or [],
                "resource_profile": resource_profile or ResourceProfile(),
                "factory": factory,
                "config_schema": config_schema,
                "registered_at": datetime.now(timezone.utc),
            }
            
            # Remove from blacklist if present
            self._blacklist.discard(module_type)
            
        logger.info("Registered module type: %s with capabilities: %s", module_type, capabilities)
        return True
    
    def unregister_module_type(self, module_type: str) -> bool:
        """
        Unregister a module type. Existing instances are not affected.
        Returns True if the type was registered.
        """
        with self._lock:
            if module_type not in self._module_types:
                return False
            del self._module_types[module_type]
        logger.info("Unregistered module type: %s", module_type)
        return True
    
    def blacklist_module_type(self, module_type: str, reason: str = ""):
        """Blacklist a module type from spawning."""
        with self._lock:
            self._blacklist.add(module_type)
        logger.warning("Blacklisted module type: %s (reason: %s)", module_type, reason)
    
    def unblacklist_module_type(self, module_type: str):
        """Remove a module type from the blacklist."""
        with self._lock:
            self._blacklist.discard(module_type)
        logger.info("Removed %s from blacklist", module_type)
    
    # ------------------------------------------------------------------
    # Spawn / Despawn
    # ------------------------------------------------------------------
    
    def spawn_module(
        self,
        module_type: str,
        config: Optional[Dict[str, Any]] = None,
        parent_instance_id: Optional[str] = None,
        actor: str = "system",
        correlation_id: Optional[str] = None,
        instance_id: Optional[str] = None,
    ) -> tuple[SpawnDecision, Optional[str], str]:
        """
        Spawn a new module instance.
        
        Args:
            module_type: Type of module to spawn
            config: Configuration for the instance
            parent_instance_id: Optional parent for hierarchical tracking
            actor: Who initiated the spawn
            correlation_id: Optional ID to link related operations
            instance_id: Optional specific instance ID (auto-generated if not provided)
            
        Returns:
            (decision, instance_id_or_reason, correlation_id)
        """
        # Generate correlation ID if not provided
        if not correlation_id:
            correlation_id = f"corr-{uuid.uuid4().hex[:12]}"
        
        # Circuit breaker check
        if self._is_circuit_open():
            self._record_audit(
                instance_id="",
                module_type=module_type,
                action="spawn_denied",
                actor=actor,
                details={"reason": "circuit_open"},
                correlation_id=correlation_id,
            )
            return (SpawnDecision.DENIED_CIRCUIT, None, correlation_id)
        
        # Check viability
        viability, reason = self._viability_checker.check_viability(
            module_type, config or {}, {"parent_instance_id": parent_instance_id}
        )
        
        if viability != ViabilityResult.VIABLE:
            self._record_audit(
                instance_id="",
                module_type=module_type,
                action="spawn_denied",
                actor=actor,
                details={"reason": viability.value, "detail": reason},
                correlation_id=correlation_id,
            )
            
            decision_map = {
                ViabilityResult.NOT_VIABLE: SpawnDecision.DENIED_BLACKLIST,
                ViabilityResult.BLACKLISTED: SpawnDecision.DENIED_BLACKLIST,
                ViabilityResult.INSUFFICIENT_RESOURCES: SpawnDecision.DENIED_BUDGET,
                ViabilityResult.DEPENDENCY_MISSING: SpawnDecision.DENIED_DEPENDENCY,
                ViabilityResult.ALREADY_SPAWNED: SpawnDecision.DENIED_BUDGET,
            }
            return (decision_map.get(viability, SpawnDecision.DENIED_BLACKLIST), reason, correlation_id)
        
        with self._lock:
            # Calculate spawn depth
            spawn_depth = 0
            if parent_instance_id:
                parent = self._instances.get(parent_instance_id)
                if parent:
                    spawn_depth = parent.spawn_depth + 1
                else:
                    return (SpawnDecision.DENIED_DEPTH, "Parent instance not found", correlation_id)
            
            # Depth limit check
            if spawn_depth > self._max_spawn_depth:
                return (SpawnDecision.DENIED_DEPTH, f"Max spawn depth ({self._max_spawn_depth}) exceeded", correlation_id)
            
            # Instance limit per type check
            current_count = len(self._instances_by_type.get(module_type, []))
            if current_count >= self._max_instances_per_type:
                return (SpawnDecision.DENIED_BUDGET, f"Max instances ({self._max_instances_per_type}) reached for {module_type}", correlation_id)
            
            # Generate instance ID
            inst_id = instance_id or self._generate_instance_id(module_type)
            
            # Get type info
            type_info = self._module_types[module_type]
            
            # Create instance
            instance = ModuleInstance(
                instance_id=inst_id,
                module_type=module_type,
                state=InstanceState.SPAWNING,
                spawned_at=datetime.now(timezone.utc),
                config=config or {},
                resource_profile=type_info.get("resource_profile", ResourceProfile()),
                capabilities=type_info.get("capabilities", []),
                parent_instance_id=parent_instance_id,
                spawn_depth=spawn_depth,
                actor=actor,
                correlation_id=correlation_id,
            )
            
            # Store instance
            self._instances[inst_id] = instance
            
            # Index by type
            if module_type not in self._instances_by_type:
                self._instances_by_type[module_type] = []
            self._instances_by_type[module_type].append(inst_id)
            
            # Store config snapshot
            if instance._config_snapshot:
                self._config_snapshots[inst_id] = instance._config_snapshot
        
        # Record audit
        self._record_audit(
            instance_id=inst_id,
            module_type=module_type,
            action="spawn",
            actor=actor,
            details={
                "config": config,
                "parent_instance_id": parent_instance_id,
                "spawn_depth": spawn_depth,
            },
            parent_instance_id=parent_instance_id,
            correlation_id=correlation_id,
        )
        
        # Transition to ACTIVE
        instance.state = InstanceState.ACTIVE
        instance.last_activity = datetime.now(timezone.utc)
        
        logger.info(
            "Spawned instance %s of type %s (depth=%d, actor=%s)",
            inst_id, module_type, spawn_depth, actor
        )
        
        return (SpawnDecision.APPROVED, inst_id, correlation_id)
    
    def despawn_module(
        self,
        instance_id: str,
        reason: str = "manual",
        actor: str = "system",
        force: bool = False,
    ) -> bool:
        """
        Despawn a module instance.
        
        Args:
            instance_id: ID of instance to despawn
            reason: Reason for despawning
            actor: Who initiated the despawn
            force: Force despawn even if busy
            
        Returns:
            True if successfully despawned
        """
        with self._lock:
            instance = self._instances.get(instance_id)
            if instance is None:
                logger.warning("Cannot despawn: instance %s not found", instance_id)
                return False
            
            if instance.state == InstanceState.DESPAWNED:
                logger.warning("Instance %s already despawned", instance_id)
                return True
            
            # Check if busy (unless forced)
            if instance.state == InstanceState.BUSY and not force:
                logger.warning("Cannot despawn busy instance %s without force=True", instance_id)
                return False
            
            # Transition state
            old_state = instance.state
            instance.state = InstanceState.DESPAWNING
            
            # Check for children
            children = self._get_children(instance_id)
            if children and not force:
                logger.warning("Instance %s has %d children, despawning them first", instance_id, len(children))
                for child_id in children:
                    self.despawn_module(child_id, reason=f"parent_despawn:{instance_id}", actor=actor, force=True)
            
            # Final state
            instance.state = InstanceState.DESPAWNED
            instance.last_activity = datetime.now(timezone.utc)
        
        # Record audit
        self._record_audit(
            instance_id=instance_id,
            module_type=instance.module_type,
            action="despawn",
            actor=actor,
            details={
                "reason": reason,
                "previous_state": old_state.value,
                "force": force,
                "execution_count": instance.execution_count,
                "error_count": instance.error_count,
            },
        )
        
        logger.info(
            "Despawned instance %s (type=%s, reason=%s, actor=%s)",
            instance_id, instance.module_type, reason, actor
        )
        
        return True
    
    def despawn_all(
        self,
        module_type: Optional[str] = None,
        reason: str = "bulk_despawn",
        actor: str = "system",
        force: bool = False,
    ) -> int:
        """
        Despawn multiple instances.
        
        Args:
            module_type: Optional filter to specific type
            reason: Reason for despawning
            actor: Who initiated
            force: Force despawn even if busy
            
        Returns:
            Number of instances despawned
        """
        with self._lock:
            if module_type:
                instance_ids = list(self._instances_by_type.get(module_type, []))
            else:
                instance_ids = list(self._instances.keys())
        
        count = 0
        for inst_id in instance_ids:
            if self.despawn_module(inst_id, reason=reason, actor=actor, force=force):
                count += 1
        
        logger.info("Bulk despawned %d instances (type=%s, actor=%s)", count, module_type or "all", actor)
        return count
    
    # ------------------------------------------------------------------
    # Instance Access
    # ------------------------------------------------------------------
    
    def get_instance(self, instance_id: str) -> Optional[ModuleInstance]:
        """Get an instance by ID."""
        with self._lock:
            return self._instances.get(instance_id)
    
    def get_instances_by_type(self, module_type: str) -> List[ModuleInstance]:
        """Get all active instances of a given type."""
        with self._lock:
            instance_ids = self._instances_by_type.get(module_type, [])
            return [
                self._instances[iid]
                for iid in instance_ids
                if iid in self._instances and self._instances[iid].is_active()
            ]
    
    def get_instances_by_capability(self, capability: str) -> List[ModuleInstance]:
        """Get all instances that have a specific capability."""
        with self._lock:
            return [
                inst
                for inst in self._instances.values()
                if inst.is_active() and capability in inst.capabilities
            ]
    
    def get_active_instances(self) -> List[ModuleInstance]:
        """Get all active instances."""
        with self._lock:
            return [inst for inst in self._instances.values() if inst.is_active()]
    
    def find_viable_instances(
        self,
        request: Dict[str, Any],
        required_capabilities: Optional[List[str]] = None,
        module_type: Optional[str] = None,
    ) -> List[ModuleInstance]:
        """
        Find instances that are viable for a given request.
        
        This implements the "murphy cursor actions" style of selecting
        modules based on request viability.
        """
        results = []
        
        with self._lock:
            candidates = list(self._instances.values())
        
        for inst in candidates:
            if not inst.is_available():
                continue
            
            # Type filter
            if module_type and inst.module_type != module_type:
                continue
            
            # Capability filter
            if required_capabilities:
                has_caps = all(cap in inst.capabilities for cap in required_capabilities)
                if not has_caps:
                    continue
            
            # Viability check
            viability, _ = self._viability_checker.check_viability(
                inst.module_type, request, {"instance_id": inst.instance_id}
            )
            
            if viability == ViabilityResult.VIABLE:
                results.append(inst)
        
        # Sort by execution count (prefer less used) and error count (prefer fewer errors)
        results.sort(key=lambda i: (i.execution_count, i.error_count))
        
        return results
    
    # ------------------------------------------------------------------
    # Resource Management
    # ------------------------------------------------------------------
    
    def get_available_resources(self) -> Dict[str, Any]:
        """Get currently available resources."""
        with self._lock:
            used_cpu = sum(
                inst.resource_profile.cpu_cores
                for inst in self._instances.values()
                if inst.is_active()
            )
            used_memory = sum(
                inst.resource_profile.memory_mb
                for inst in self._instances.values()
                if inst.is_active()
            )
            
            return {
                "cpu_total": self._total_cpu,
                "cpu_used": used_cpu,
                "cpu_available": self._total_cpu - used_cpu,
                "memory_total_mb": self._total_memory_mb,
                "memory_used_mb": used_memory,
                "memory_available_mb": self._total_memory_mb - used_memory,
                "active_instances": len([i for i in self._instances.values() if i.is_active()]),
                "total_instances": len(self._instances),
            }
    
    # ------------------------------------------------------------------
    # Audit Trail (Configuration Backward Logic)
    # ------------------------------------------------------------------
    
    def get_audit_trail(
        self,
        instance_id: Optional[str] = None,
        module_type: Optional[str] = None,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Get audit trail entries for backward configuration logic.
        
        This enables tracing back from a current state to understand:
        - Who spawned/despawned instances
        - What configuration was used
        - What the parent-child relationships are
        - What errors occurred
        """
        with self._lock:
            entries = list(self._audit_log)
        
        # Apply filters
        if instance_id:
            entries = [e for e in entries if e.instance_id == instance_id]
        if module_type:
            entries = [e for e in entries if e.module_type == module_type]
        if action:
            entries = [e for e in entries if e.action == action]
        if actor:
            entries = [e for e in entries if e.actor == actor]
        if correlation_id:
            entries = [e for e in entries if e.correlation_id == correlation_id]
        
        # Sort by timestamp descending, then limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]
    
    def get_config_snapshot(self, instance_id: str) -> Optional[ConfigurationSnapshot]:
        """Get the configuration snapshot for an instance."""
        with self._lock:
            return self._config_snapshots.get(instance_id)
    
    def get_configuration_history(
        self,
        instance_id: str,
    ) -> Dict[str, Any]:
        """
        Get full configuration backward logic for an instance.
        
        Returns the complete history of configuration changes,
        parent relationships, and audit entries.
        """
        instance = self.get_instance(instance_id)
        if not instance:
            return {"error": f"Instance {instance_id} not found"}
        
        audit_entries = self.get_audit_trail(instance_id=instance_id, limit=1000)
        snapshot = self.get_config_snapshot(instance_id)
        
        # Get parent chain
        parent_chain = []
        parent_id = instance.parent_instance_id
        while parent_id:
            parent = self.get_instance(parent_id)
            if parent:
                parent_chain.append({
                    "instance_id": parent_id,
                    "module_type": parent.module_type,
                    "spawned_at": parent.spawned_at.isoformat(),
                })
                parent_id = parent.parent_instance_id
            else:
                break
        
        return {
            "instance_id": instance_id,
            "module_type": instance.module_type,
            "current_state": instance.state.value,
            "configuration_snapshot": snapshot.to_dict() if snapshot else None,
            "parent_chain": parent_chain,
            "audit_trail": [e.to_dict() for e in audit_entries],
            "execution_count": instance.execution_count,
            "error_count": instance.error_count,
        }
    
    def export_audit_report(self) -> Dict[str, Any]:
        """Export a complete audit report for compliance."""
        with self._lock:
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "total_instances_spawned": len(self._instances),
                    "active_instances": len([i for i in self._instances.values() if i.is_active()]),
                    "total_audit_entries": len(self._audit_log),
                    "module_types_registered": list(self._module_types.keys()),
                    "blacklisted_types": list(self._blacklist),
                },
                "instances": {
                    inst_id: inst.to_dict()
                    for inst_id, inst in self._instances.items()
                },
                "audit_log": [e.to_dict() for e in self._audit_log[-1000:]],
                "config_snapshots": {
                    inst_id: snap.to_dict()
                    for inst_id, snap in self._config_snapshots.items()
                },
            }
    
    # ------------------------------------------------------------------
    # Status and Monitoring
    # ------------------------------------------------------------------
    
    def get_status(self) -> Dict[str, Any]:
        """Get current manager status."""
        with self._lock:
            instances_by_type = {}
            for module_type, inst_ids in self._instances_by_type.items():
                active = sum(1 for iid in inst_ids if iid in self._instances and self._instances[iid].is_active())
                instances_by_type[module_type] = {
                    "total": len(inst_ids),
                    "active": active,
                }
            
            state_counts = {}
            for inst in self._instances.values():
                state = inst.state.value
                state_counts[state] = state_counts.get(state, 0) + 1
            
            return {
                "circuit_breaker_open": self._circuit_open,
                "total_instances": len(self._instances),
                "active_instances": len([i for i in self._instances.values() if i.is_active()]),
                "instances_by_type": instances_by_type,
                "instances_by_state": state_counts,
                "registered_types": list(self._module_types.keys()),
                "blacklisted_types": list(self._blacklist),
                "resources": self.get_available_resources(),
                "audit_entries": len(self._audit_log),
            }
    
    # ------------------------------------------------------------------
    # Private Methods
    # ------------------------------------------------------------------
    
    def _generate_instance_id(self, module_type: str) -> str:
        """Generate a unique instance ID."""
        self._id_counter += 1
        short_type = module_type[:12].replace("_", "-")
        return f"inst-{short_type}-{self._id_counter:04d}-{uuid.uuid4().hex[:6]}"
    
    def _record_audit(
        self,
        instance_id: str,
        module_type: str,
        action: str,
        actor: str,
        details: Dict[str, Any],
        parent_instance_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Record an audit entry."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            instance_id=instance_id,
            module_type=module_type,
            action=action,
            actor=actor,
            details=details,
            parent_instance_id=parent_instance_id,
            correlation_id=correlation_id,
        )
        
        with self._lock:
            self._audit_log.append(entry)
            
            # Trim old entries if needed
            if len(self._audit_log) > self._audit_retention:
                self._audit_log = self._audit_log[-self._audit_retention:]
    
    def _get_children(self, parent_instance_id: str) -> List[str]:
        """Get all child instances of a parent."""
        return [
            inst_id
            for inst_id, inst in self._instances.items()
            if inst.parent_instance_id == parent_instance_id and inst.is_active()
        ]
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_open:
            return False
        
        # Check for recovery
        if self._circuit_last_failure:
            elapsed = time.monotonic() - self._circuit_last_failure
            if elapsed >= self._circuit_recovery_seconds:
                self._circuit_open = False
                self._circuit_failures = 0
                logger.info("Circuit breaker recovered")
                return False
        
        return True
    
    def _record_spawn_failure(self):
        """Record a spawn failure for circuit breaker."""
        self._circuit_failures += 1
        self._circuit_last_failure = time.monotonic()
        
        if self._circuit_failures >= self._circuit_threshold:
            self._circuit_open = True
            logger.warning(
                "Circuit breaker opened after %d failures",
                self._circuit_failures
            )
    
    def _record_spawn_success(self):
        """Record a successful spawn."""
        self._circuit_failures = 0
        self._circuit_open = False


# ---------------------------------------------------------------------------
# Integration with Existing Systems
# ---------------------------------------------------------------------------

def integrate_with_triage_rollcall(
    manager: ModuleInstanceManager,
    adapter: 'TriageRollcallAdapter',
) -> None:
    """
    Integrate ModuleInstanceManager with existing TriageRollcallAdapter.
    
    This allows the rollcall system to spawn instances based on
    capability matching and viability.
    """
    def spawn_from_rollcall(
        task: str,
        constraints: Optional[Dict] = None,
        max_instances: int = 3,
    ) -> List[str]:
        """Spawn instances based on rollcall results."""
        results = adapter.rollcall(task=task, max_results=max_instances)
        spawned = []
        
        for result in results:
            if result.status != CandidateStatus.AVAILABLE:
                continue
            
            decision, inst_id, _ = manager.spawn_module(
                module_type=result.name,
                config={"task": task, "constraints": constraints},
                actor="triage_rollcall",
            )
            
            if decision == SpawnDecision.APPROVED and inst_id:
                spawned.append(inst_id)
        
        return spawned
    
    # Attach the function to the adapter
    adapter.spawn_from_rollcall = spawn_from_rollcall


def integrate_with_module_registry(
    manager: ModuleInstanceManager,
    registry: 'ModuleRegistry',
) -> None:
    """
    Integrate ModuleInstanceManager with existing ModuleRegistry.
    
    This automatically registers discovered modules as spawnable types.
    """
    # Register all discovered modules
    for module_name in registry.list_available():
        descriptor = registry._modules.get(module_name)
        if descriptor:
            manager.register_module_type(
                module_type=module_name,
                capabilities=descriptor.capabilities,
                dependencies=descriptor.dependencies,
            )


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

_instance_manager: Optional[ModuleInstanceManager] = None

def get_instance_manager() -> ModuleInstanceManager:
    """Get or create the global ModuleInstanceManager instance."""
    global _instance_manager
    if _instance_manager is None:
        _instance_manager = ModuleInstanceManager()
    return _instance_manager