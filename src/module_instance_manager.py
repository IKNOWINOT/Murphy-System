"""
Module Instance Manager
===========================

Lifecycle management for dynamically spawned module instances.

Handles spawn/despawn decisions, viability checks, circuit-breaker
protection, configuration snapshots, audit trails, and resource
accounting.  All mutable state is guarded by a single threading.Lock
so the manager is safe for concurrent access from the orchestration
layer.

Business Source License 1.1 (BSL 1.1)
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:  # pragma: no cover

    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _new_instance_id() -> str:
    return uuid.uuid4().hex[:12]


def _new_snapshot_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InstanceState(str, Enum):
    """Lifecycle state of a module instance."""

    SPAWNING = "spawning"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    DESPAWNING = "despawning"
    DESPAWNED = "despawned"


class ViabilityResult(str, Enum):
    """Outcome of a viability check."""

    VIABLE = "viable"
    NOT_VIABLE = "not_viable"
    INSUFFICIENT_RESOURCES = "insufficient_resources"
    DEPENDENCY_MISSING = "dependency_missing"
    ALREADY_SPAWNED = "already_spawned"
    BLACKLISTED = "blacklisted"


class SpawnDecision(str, Enum):
    """Result of the spawn-approval pipeline."""

    APPROVED = "approved"
    DENIED_BUDGET = "denied_budget"
    DENIED_DEPTH = "denied_depth"
    DENIED_CIRCUIT = "denied_circuit"
    DENIED_BLACKLIST = "denied_blacklist"
    DENIED_DEPENDENCY = "denied_dependency"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """Immutable record of a lifecycle action."""

    timestamp: str
    action: str
    actor: str
    correlation_id: str
    instance_id: Optional[str] = None
    module_type: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "instance_id": self.instance_id,
            "module_type": self.module_type,
            "details": self.details,
        }


@dataclass
class ConfigurationSnapshot:
    """Point-in-time capture of an instance's configuration."""

    snapshot_id: str
    instance_id: str
    timestamp: str
    config: Dict[str, Any]
    previous_snapshot_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "instance_id": self.instance_id,
            "timestamp": self.timestamp,
            "config": dict(self.config),
            "previous_snapshot_id": self.previous_snapshot_id,
        }


@dataclass
class ResourceProfile:
    """Resource reservation for a module instance."""

    cpu_cores: float = 1.0
    memory_mb: int = 512
    max_concurrent: int = 5
    timeout_seconds: int = 300
    priority: int = 5

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary."""
        return {
            "cpu_cores": self.cpu_cores,
            "memory_mb": self.memory_mb,
            "max_concurrent": self.max_concurrent,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
        }


@dataclass
class ModuleInstance:
    """Runtime representation of a single spawned module."""

    instance_id: str
    module_type: str
    state: InstanceState
    spawned_at: str
    config: Dict[str, Any]
    resource_profile: ResourceProfile
    capabilities: List[str]
    parent_instance_id: Optional[str] = None
    spawn_depth: int = 0
    actor: str = "system"
    correlation_id: str = ""
    despawned_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialise all fields to a plain dictionary."""
        return {
            "instance_id": self.instance_id,
            "module_type": self.module_type,
            "state": self.state.value,
            "spawned_at": self.spawned_at,
            "config": dict(self.config),
            "resource_profile": self.resource_profile.to_dict(),
            "capabilities": list(self.capabilities),
            "parent_instance_id": self.parent_instance_id,
            "spawn_depth": self.spawn_depth,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "despawned_at": self.despawned_at,
        }


# ---------------------------------------------------------------------------
# Viability checker
# ---------------------------------------------------------------------------

class ViabilityChecker:
    """Pre-flight checks that decide whether a module *may* be spawned."""

    def __init__(
        self,
        max_instances_per_type: int = 10,
        max_spawn_depth: int = 5,
        blacklist: Optional[Set[str]] = None,
    ) -> None:
        self._max_instances_per_type = max_instances_per_type
        self._max_spawn_depth = max_spawn_depth
        self._blacklist: Set[str] = set(blacklist) if blacklist else set()

    # -- public API ---------------------------------------------------------

    def check_viability(
        self,
        module_type: str,
        current_instances: int,
        resource_profile: ResourceProfile,
        parent_depth: int = 0,
    ) -> ViabilityResult:
        """Run the ordered viability checks and return the first failure
        or ``ViabilityResult.VIABLE`` when all checks pass."""
        if self.is_blacklisted(module_type):
            return ViabilityResult.BLACKLISTED
        if current_instances >= self._max_instances_per_type:
            return ViabilityResult.ALREADY_SPAWNED
        if parent_depth >= self._max_spawn_depth:
            return ViabilityResult.NOT_VIABLE
        if resource_profile.memory_mb > 8192 or resource_profile.cpu_cores > 16:
            return ViabilityResult.INSUFFICIENT_RESOURCES
        return ViabilityResult.VIABLE

    def add_to_blacklist(self, module_type: str) -> None:
        """Block a module type from being spawned."""
        self._blacklist.add(module_type)

    def remove_from_blacklist(self, module_type: str) -> None:
        """Allow a previously-blacklisted module type to spawn again."""
        self._blacklist.discard(module_type)

    def is_blacklisted(self, module_type: str) -> bool:
        """Return ``True`` when *module_type* is on the blacklist."""
        return module_type in self._blacklist


# ---------------------------------------------------------------------------
# Viability → SpawnDecision mapping
# ---------------------------------------------------------------------------

_VIABILITY_TO_DECISION: Dict[ViabilityResult, SpawnDecision] = {
    ViabilityResult.BLACKLISTED: SpawnDecision.DENIED_BLACKLIST,
    ViabilityResult.ALREADY_SPAWNED: SpawnDecision.DENIED_BUDGET,
    ViabilityResult.NOT_VIABLE: SpawnDecision.DENIED_DEPTH,
    ViabilityResult.INSUFFICIENT_RESOURCES: SpawnDecision.DENIED_BUDGET,
    ViabilityResult.DEPENDENCY_MISSING: SpawnDecision.DENIED_DEPENDENCY,
}


# ---------------------------------------------------------------------------
# Module Instance Manager
# ---------------------------------------------------------------------------

class ModuleInstanceManager:
    """Central authority for spawning, tracking and despawning module
    instances.

    All public methods acquire ``self._lock`` so the manager is safe for
    use from multiple threads.
    """

    _MAX_AUDIT_ENTRIES = 1000

    def __init__(
        self,
        max_spawn_depth: int = 5,
        max_instances_per_type: int = 10,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_recovery_seconds: int = 30,
    ) -> None:
        self._lock = threading.Lock()

        self._max_spawn_depth = max_spawn_depth
        self._max_instances_per_type = max_instances_per_type
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_breaker_recovery_seconds = circuit_breaker_recovery_seconds

        self._instances: Dict[str, ModuleInstance] = {}
        self._audit_trail: List[AuditEntry] = []
        self._config_snapshots: Dict[str, List[ConfigurationSnapshot]] = {}
        self._failure_counts: Dict[str, int] = {}
        self._circuit_open_at: Dict[str, datetime] = {}
        self._viability_checker = ViabilityChecker(
            max_instances_per_type=max_instances_per_type,
            max_spawn_depth=max_spawn_depth,
        )
        self._registered_types: Dict[str, Dict[str, Any]] = {}

    # -- spawn / despawn ----------------------------------------------------

    def spawn_instance(
        self,
        module_type: str,
        config: Optional[Dict[str, Any]] = None,
        resource_profile: Optional[ResourceProfile] = None,
        capabilities: Optional[List[str]] = None,
        parent_instance_id: Optional[str] = None,
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> Tuple[SpawnDecision, Optional[ModuleInstance]]:
        """Attempt to spawn a new module instance.

        Returns a ``(decision, instance)`` tuple.  *instance* is ``None``
        when the decision is anything other than ``APPROVED``.
        """
        correlation_id = correlation_id or uuid.uuid4().hex[:8]
        config = config or {}
        resource_profile = resource_profile or ResourceProfile()
        capabilities = capabilities or []

        with self._lock:
            # Circuit breaker
            if self._check_circuit_breaker(module_type):
                logger.warning(
                    "Circuit breaker open for %s – spawn denied", module_type,
                )
                self._record_audit(
                    "spawn_denied_circuit", actor, correlation_id,
                    module_type=module_type,
                )
                return SpawnDecision.DENIED_CIRCUIT, None

            # Resolve the depth at which the new child will sit
            child_depth = 0
            if parent_instance_id and parent_instance_id in self._instances:
                child_depth = self._instances[parent_instance_id].spawn_depth + 1

            # Count active instances of this type
            current_count = sum(
                1 for inst in self._instances.values()
                if inst.module_type == module_type
                and inst.state not in (InstanceState.DESPAWNED, InstanceState.DESPAWNING)
            )

            # Viability
            viability = self._viability_checker.check_viability(
                module_type, current_count, resource_profile, child_depth,
            )
            if viability != ViabilityResult.VIABLE:
                decision = _VIABILITY_TO_DECISION.get(
                    viability, SpawnDecision.DENIED_BUDGET,
                )
                self._failure_counts[module_type] = (
                    self._failure_counts.get(module_type, 0) + 1
                )
                if self._failure_counts[module_type] >= self._circuit_breaker_threshold:
                    self._circuit_open_at[module_type] = datetime.now(timezone.utc)
                    logger.warning(
                        "Circuit breaker tripped for %s after %d failures",
                        module_type,
                        self._failure_counts[module_type],
                    )
                self._record_audit(
                    f"spawn_denied_{decision.value}", actor, correlation_id,
                    module_type=module_type,
                    details={"viability": viability.value},
                )
                return decision, None

            # Approved – create instance
            instance_id = _new_instance_id()
            now = _utcnow()
            instance = ModuleInstance(
                instance_id=instance_id,
                module_type=module_type,
                state=InstanceState.SPAWNING,
                spawned_at=now,
                config=dict(config),
                resource_profile=resource_profile,
                capabilities=list(capabilities),
                parent_instance_id=parent_instance_id,
                spawn_depth=child_depth,
                actor=actor,
                correlation_id=correlation_id,
            )
            self._instances[instance_id] = instance
            instance.state = InstanceState.ACTIVE

            # Config snapshot
            snap = ConfigurationSnapshot(
                snapshot_id=_new_snapshot_id(),
                instance_id=instance_id,
                timestamp=now,
                config=dict(config),
            )
            self._config_snapshots[instance_id] = [snap]

            # Reset failure counter on success
            self._failure_counts.pop(module_type, None)
            self._circuit_open_at.pop(module_type, None)

            self._record_audit(
                "spawn", actor, correlation_id,
                instance_id=instance_id,
                module_type=module_type,
                details={"resource_profile": resource_profile.to_dict()},
            )
            logger.info(
                "Spawned instance %s of type %s (depth=%d)",
                instance_id, module_type, child_depth,
            )
            return SpawnDecision.APPROVED, instance

    def despawn_instance(
        self,
        instance_id: str,
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Gracefully despawn an instance.  Returns ``True`` on success."""
        correlation_id = correlation_id or uuid.uuid4().hex[:8]
        with self._lock:
            instance = self._instances.get(instance_id)
            if instance is None:
                logger.warning("Despawn requested for unknown instance %s", instance_id)
                return False
            if instance.state == InstanceState.DESPAWNED:
                logger.debug("Instance %s is already despawned", instance_id)
                return False

            # Transition through DESPAWNING (observable marker for hooks)
            # before settling on DESPAWNED.
            instance.state = InstanceState.DESPAWNING
            instance.despawned_at = _utcnow()
            instance.state = InstanceState.DESPAWNED

            self._record_audit(
                "despawn", actor, correlation_id,
                instance_id=instance_id,
                module_type=instance.module_type,
            )
            logger.info("Despawned instance %s", instance_id)
            return True

    # -- queries ------------------------------------------------------------

    def get_instance(self, instance_id: str) -> Optional[ModuleInstance]:
        """Return a single instance by ID, or ``None``."""
        with self._lock:
            return self._instances.get(instance_id)

    def list_instances(
        self,
        module_type: Optional[str] = None,
        state: Optional[InstanceState] = None,
    ) -> List[ModuleInstance]:
        """Return instances with optional type/state filtering."""
        with self._lock:
            results = list(self._instances.values())
            if module_type is not None:
                results = [i for i in results if i.module_type == module_type]
            if state is not None:
                results = [i for i in results if i.state == state]
            return results

    def get_audit_trail(
        self,
        limit: int = 50,
        instance_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Return recent audit entries, optionally scoped to one instance."""
        with self._lock:
            entries = self._audit_trail
            if instance_id is not None:
                entries = [e for e in entries if e.instance_id == instance_id]
            return list(entries[-limit:])

    def get_config_history(self, instance_id: str) -> List[ConfigurationSnapshot]:
        """Return full configuration snapshot history for an instance."""
        with self._lock:
            return list(self._config_snapshots.get(instance_id, []))

    def update_instance_config(
        self,
        instance_id: str,
        new_config: Dict[str, Any],
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Apply a new configuration to a running instance and snapshot it.

        Returns ``True`` on success.
        """
        correlation_id = correlation_id or uuid.uuid4().hex[:8]
        with self._lock:
            instance = self._instances.get(instance_id)
            if instance is None:
                return False
            if instance.state == InstanceState.DESPAWNED:
                return False

            previous_id: Optional[str] = None
            snaps = self._config_snapshots.get(instance_id, [])
            if snaps:
                previous_id = snaps[-1].snapshot_id

            snap = ConfigurationSnapshot(
                snapshot_id=_new_snapshot_id(),
                instance_id=instance_id,
                timestamp=_utcnow(),
                config=dict(new_config),
                previous_snapshot_id=previous_id,
            )
            self._config_snapshots.setdefault(instance_id, []).append(snap)
            instance.config = dict(new_config)

            self._record_audit(
                "config_update", actor, correlation_id,
                instance_id=instance_id,
                module_type=instance.module_type,
                details={"snapshot_id": snap.snapshot_id},
            )
            return True

    # -- status / resource accounting ---------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Aggregate status overview of all managed instances."""
        with self._lock:
            by_state: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for inst in self._instances.values():
                by_state[inst.state.value] = by_state.get(inst.state.value, 0) + 1
                by_type[inst.module_type] = by_type.get(inst.module_type, 0) + 1

            cb_status: Dict[str, Any] = {}
            for mtype, opened in self._circuit_open_at.items():
                elapsed = (datetime.now(timezone.utc) - opened).total_seconds()
                cb_status[mtype] = {
                    "open": elapsed < self._circuit_breaker_recovery_seconds,
                    "failures": self._failure_counts.get(mtype, 0),
                    "elapsed_seconds": round(elapsed, 1),
                }

            return {
                "total_instances": len(self._instances),
                "by_state": by_state,
                "by_type": by_type,
                "circuit_breaker_status": cb_status,
            }

    def get_resource_availability(self) -> Dict[str, Any]:
        """Summarise allocated vs available resource budgets."""
        with self._lock:
            allocated_cpu = 0.0
            allocated_mem = 0
            for inst in self._instances.values():
                if inst.state not in (InstanceState.DESPAWNED, InstanceState.DESPAWNING):
                    allocated_cpu += inst.resource_profile.cpu_cores
                    allocated_mem += inst.resource_profile.memory_mb
            return {
                "allocated_cpu_cores": round(allocated_cpu, 2),
                "allocated_memory_mb": allocated_mem,
                "available_cpu_cores": round(max(0.0, 16.0 - allocated_cpu), 2),
                "available_memory_mb": max(0, 8192 - allocated_mem),
            }

    # -- type management ----------------------------------------------------

    def register_module_type(
        self,
        module_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Register a module type so it can be spawned.

        Returns ``False`` if already registered.
        """
        with self._lock:
            if module_type in self._registered_types:
                return False
            self._registered_types[module_type] = metadata or {}
            logger.info("Registered module type: %s", module_type)
            return True

    def blacklist_module_type(
        self,
        module_type: str,
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> bool:
        """Add *module_type* to the viability blacklist."""
        correlation_id = correlation_id or uuid.uuid4().hex[:8]
        with self._lock:
            if self._viability_checker.is_blacklisted(module_type):
                return False
            self._viability_checker.add_to_blacklist(module_type)
            self._record_audit(
                "blacklist", actor, correlation_id, module_type=module_type,
            )
            logger.info("Blacklisted module type: %s", module_type)
            return True

    # -- bulk operations ----------------------------------------------------

    def bulk_despawn(
        self,
        instance_ids: List[str],
        actor: str = "system",
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Despawn several instances in one call.

        Returns a dict mapping each id to ``True``/``False``.
        """
        results: Dict[str, bool] = {}
        for iid in instance_ids:
            results[iid] = self.despawn_instance(iid, actor=actor, correlation_id=correlation_id)
        return {"results": results}

    # -- capability search --------------------------------------------------

    def find_viable_instances(
        self,
        module_type: str,
        required_capabilities: Optional[List[str]] = None,
    ) -> List[ModuleInstance]:
        """Return active instances of *module_type* that satisfy the
        given capability requirements."""
        required = set(required_capabilities) if required_capabilities else set()
        with self._lock:
            matches: List[ModuleInstance] = []
            for inst in self._instances.values():
                if inst.module_type != module_type:
                    continue
                if inst.state != InstanceState.ACTIVE:
                    continue
                if required and not required.issubset(set(inst.capabilities)):
                    continue
                matches.append(inst)
            return matches

    # -- private helpers ----------------------------------------------------

    def _record_audit(
        self,
        action: str,
        actor: str,
        correlation_id: str,
        instance_id: Optional[str] = None,
        module_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an entry to the bounded audit trail.

        Must be called while ``self._lock`` is held.
        """
        entry = AuditEntry(
            timestamp=_utcnow(),
            action=action,
            actor=actor,
            correlation_id=correlation_id,
            instance_id=instance_id,
            module_type=module_type,
            details=details,
        )
        capped_append(self._audit_trail, entry, max_size=self._MAX_AUDIT_ENTRIES)

    def _check_circuit_breaker(self, module_type: str) -> bool:
        """Return ``True`` when the circuit breaker is open (blocking spawns).

        Must be called while ``self._lock`` is held.
        """
        opened = self._circuit_open_at.get(module_type)
        if opened is None:
            return False
        elapsed = (datetime.now(timezone.utc) - opened).total_seconds()
        if elapsed >= self._circuit_breaker_recovery_seconds:
            # Recovery window passed – reset
            self._circuit_open_at.pop(module_type, None)
            self._failure_counts.pop(module_type, None)
            logger.info("Circuit breaker recovered for %s", module_type)
            return False
        return True


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------

def integrate_with_triage_rollcall(
    manager: ModuleInstanceManager,
    adapter: Any,
) -> None:
    """Register all known candidates from a ``TriageRollcallAdapter`` as
    module types in the instance manager."""
    try:
        candidates = adapter.list_candidates()
        for candidate in candidates:
            name = getattr(candidate, "name", None)
            if name is None:
                name = getattr(candidate, "candidate_id", None)
            if name:
                caps = getattr(candidate, "capabilities", [])
                manager.register_module_type(name, metadata={"capabilities": caps, "source": "triage_rollcall"})
        logger.info(
            "Integrated %d candidates from triage rollcall adapter",
            len(candidates),
        )
    except Exception as exc:
        logger.error("Failed to integrate triage rollcall adapter: %s", exc)


def integrate_with_module_registry(
    manager: ModuleInstanceManager,
    registry: Any,
) -> None:
    """Register all loaded modules from a ``ModuleRegistry`` as module
    types in the instance manager."""
    try:
        available = registry.list_available()
        for module_name in available:
            status = registry.get_module_status(module_name)
            manager.register_module_type(module_name, metadata={"status": status, "source": "module_registry"})
        logger.info(
            "Integrated %d modules from module registry", len(available),
        )
    except Exception as exc:
        logger.error("Failed to integrate module registry: %s", exc)
