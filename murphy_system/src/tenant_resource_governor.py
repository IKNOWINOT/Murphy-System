"""
Tenant Resource Governor for Murphy System.

Design Label: SAF-003 — Per-Tenant Resource Limits & Enforcement
Owner: Platform Engineering / Security Team
Dependencies:
  - PersistenceManager (for durable limit configs and usage snapshots)
  - EventBackbone (publishes SYSTEM_HEALTH on limit breaches)
  - EmergencyStopController (OPS-004, optional, for tenant-level stop)

Implements Plan §6.2 — Multi-Tenant Isolation / Resource Containment:
  Defines per-tenant resource limits (CPU seconds, memory MB, API calls,
  budget USD) and tracks real-time usage.  Requests are checked against
  limits before execution; breaches trigger warnings or blocks.

Flow:
  1. Configure resource limits per tenant
  2. Record resource usage per tenant (api_calls, cpu_seconds, memory_mb, budget_usd)
  3. Check a usage request against tenant limits
  4. Block if any limit would be exceeded
  5. Generate UsageSnapshot for monitoring
  6. Persist snapshot and publish breach events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Fail-closed: unknown tenant or missing limit → request denied
  - Bounded: configurable max snapshots
  - Per-tenant isolation: no cross-tenant data access
  - Audit trail: every breach is logged

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
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_SNAPSHOTS = 5_000

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class LimitCheckResult(str, Enum):
    """Limit check result (str subclass)."""
    ALLOWED = "allowed"
    DENIED_OVER_LIMIT = "denied_over_limit"
    DENIED_UNKNOWN_TENANT = "denied_unknown_tenant"


@dataclass
class ResourceLimits:
    """Resource limits for a single tenant."""
    tenant_id: str
    max_api_calls: int = 10_000
    max_cpu_seconds: float = 3600.0
    max_memory_mb: float = 4096.0
    max_budget_usd: float = 1000.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "max_api_calls": self.max_api_calls,
            "max_cpu_seconds": self.max_cpu_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_budget_usd": self.max_budget_usd,
        }


@dataclass
class ResourceUsage:
    """Current resource usage for a single tenant."""
    tenant_id: str
    api_calls: int = 0
    cpu_seconds: float = 0.0
    memory_mb: float = 0.0
    budget_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "api_calls": self.api_calls,
            "cpu_seconds": round(self.cpu_seconds, 4),
            "memory_mb": round(self.memory_mb, 4),
            "budget_usd": round(self.budget_usd, 4),
        }


@dataclass
class UsageSnapshot:
    """Point-in-time snapshot of a tenant's usage vs limits."""
    snapshot_id: str
    tenant_id: str
    usage: Dict[str, Any] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    breaches: List[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "tenant_id": self.tenant_id,
            "usage": self.usage,
            "limits": self.limits,
            "breaches": self.breaches,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# TenantResourceGovernor
# ---------------------------------------------------------------------------

class TenantResourceGovernor:
    """Per-tenant resource limits and enforcement.

    Design Label: SAF-003
    Owner: Platform Engineering / Security Team

    Usage::

        gov = TenantResourceGovernor()
        gov.set_limits(ResourceLimits("tenant-1", max_api_calls=100))
        gov.record_usage("tenant-1", api_calls=1)
        result = gov.check_request("tenant-1", api_calls=1)
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._limits: Dict[str, ResourceLimits] = {}
        self._usage: Dict[str, ResourceUsage] = {}
        self._snapshots: List[UsageSnapshot] = []

    # ------------------------------------------------------------------
    # Limit management
    # ------------------------------------------------------------------

    def set_limits(self, limits: ResourceLimits) -> None:
        """Set or update resource limits for a tenant."""
        with self._lock:
            self._limits[limits.tenant_id] = limits
            if limits.tenant_id not in self._usage:
                self._usage[limits.tenant_id] = ResourceUsage(tenant_id=limits.tenant_id)
        logger.info("Set limits for tenant %s", limits.tenant_id)

    def get_limits(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            lim = self._limits.get(tenant_id)
            return lim.to_dict() if lim else None

    def remove_tenant(self, tenant_id: str) -> bool:
        with self._lock:
            removed = self._limits.pop(tenant_id, None) is not None
            self._usage.pop(tenant_id, None)
            return removed

    # ------------------------------------------------------------------
    # Usage tracking
    # ------------------------------------------------------------------

    def record_usage(
        self,
        tenant_id: str,
        api_calls: int = 0,
        cpu_seconds: float = 0.0,
        memory_mb: float = 0.0,
        budget_usd: float = 0.0,
    ) -> bool:
        """Record resource consumption for a tenant. Returns False if tenant unknown."""
        with self._lock:
            usage = self._usage.get(tenant_id)
            if usage is None:
                return False
            usage.api_calls += api_calls
            usage.cpu_seconds += cpu_seconds
            usage.memory_mb = max(usage.memory_mb, memory_mb)  # peak
            usage.budget_usd += budget_usd
        return True

    def reset_usage(self, tenant_id: str) -> bool:
        """Reset usage counters for a tenant (e.g., at billing cycle start)."""
        with self._lock:
            if tenant_id not in self._usage:
                return False
            self._usage[tenant_id] = ResourceUsage(tenant_id=tenant_id)
        return True

    # ------------------------------------------------------------------
    # Limit checking
    # ------------------------------------------------------------------

    def check_request(
        self,
        tenant_id: str,
        api_calls: int = 0,
        cpu_seconds: float = 0.0,
        memory_mb: float = 0.0,
        budget_usd: float = 0.0,
    ) -> LimitCheckResult:
        """Check whether a request would exceed tenant limits."""
        with self._lock:
            limits = self._limits.get(tenant_id)
            usage = self._usage.get(tenant_id)
            if limits is None or usage is None:
                return LimitCheckResult.DENIED_UNKNOWN_TENANT

            breaches = []
            if usage.api_calls + api_calls > limits.max_api_calls:
                breaches.append("api_calls")
            if usage.cpu_seconds + cpu_seconds > limits.max_cpu_seconds:
                breaches.append("cpu_seconds")
            if max(usage.memory_mb, memory_mb) > limits.max_memory_mb:
                breaches.append("memory_mb")
            if usage.budget_usd + budget_usd > limits.max_budget_usd:
                breaches.append("budget_usd")

        if breaches:
            self._record_breach(tenant_id, breaches)
            return LimitCheckResult.DENIED_OVER_LIMIT
        return LimitCheckResult.ALLOWED

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self, tenant_id: str) -> Optional[UsageSnapshot]:
        """Generate a usage vs limits snapshot for a tenant."""
        with self._lock:
            limits = self._limits.get(tenant_id)
            usage = self._usage.get(tenant_id)
            if limits is None or usage is None:
                return None

            breaches = []
            if usage.api_calls > limits.max_api_calls:
                breaches.append("api_calls")
            if usage.cpu_seconds > limits.max_cpu_seconds:
                breaches.append("cpu_seconds")
            if usage.memory_mb > limits.max_memory_mb:
                breaches.append("memory_mb")
            if usage.budget_usd > limits.max_budget_usd:
                breaches.append("budget_usd")

            snap = UsageSnapshot(
                snapshot_id=f"us-{uuid.uuid4().hex[:8]}",
                tenant_id=tenant_id,
                usage=usage.to_dict(),
                limits=limits.to_dict(),
                breaches=breaches,
            )

            if len(self._snapshots) >= _MAX_SNAPSHOTS:
                self._snapshots = self._snapshots[_MAX_SNAPSHOTS // 10:]
            self._snapshots.append(snap)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=snap.snapshot_id, document=snap.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        return snap

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._snapshots[-limit:]]

    def get_usage(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            usage = self._usage.get(tenant_id)
            return usage.to_dict() if usage else None

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_tenants": len(self._limits),
                "total_snapshots": len(self._snapshots),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_breach(self, tenant_id: str, breaches: List[str]) -> None:
        logger.warning("Resource breach for tenant %s: %s", tenant_id, breaches)
        if self._backbone is not None:
            self._publish_event(tenant_id, breaches)

    def _publish_event(self, tenant_id: str, breaches: List[str]) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "tenant_resource_governor",
                    "action": "resource_breach",
                    "tenant_id": tenant_id,
                    "breaches": breaches,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="tenant_resource_governor",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
