"""
Automation Integration Hub for Murphy System.

Design Label: INT-001 — Master Orchestration Layer for Cross-Phase Module Coordination
Owner: Platform Engineering / Architecture Team
Dependencies:
  - EventBackbone (subscribes to all event types, routes to appropriate engines)
  - PersistenceManager (for durable integration state)
  - HealthMonitor (OBS-001/002, for system health feeds)
  - LogAnalysisEngine (OBS-003, for log pattern feeds)
  - SelfHealingCoordinator (OBS-004, for failure recovery)
  - AutomationLoopConnector (DEV-001, for feedback automation)
  - SLORemediationBridge (DEV-002, for SLO-driven proposals)
  - TicketTriageEngine (SUP-001, for ticket routing)
  - KnowledgeBaseManager (SUP-002, for knowledge feeds)
  - ComplianceAutomationBridge (CMP-001, for compliance events)
  - ContentPipelineEngine (MKT-001, for content lifecycle)
  - SEOOptimisationEngine (MKT-002, for SEO feeds)
  - CampaignOrchestrator (MKT-003, for campaign events)
  - FinancialReportingEngine (BIZ-001, for financial feeds)
  - InvoiceProcessingPipeline (BIZ-002, for invoice feeds)
  - OnboardingAutomationEngine (BIZ-003, for onboarding events)
  - CodeGenerationGateway (ADV-001, for code gen events)
  - DeploymentAutomationController (ADV-002, for deployment events)
  - SelfOptimisationEngine (ADV-003, for optimisation feeds)
  - ResourceScalingController (ADV-004, for scaling events)

Implements Phase 7 — Integration & Orchestration:
  Acts as the central nervous system connecting all Phase 1–6 modules.
  Subscribes to EventBackbone events and routes them to appropriate
  downstream engines, enabling cross-module automation flows.

Flow:
  1. Register automation modules by design label
  2. Subscribe to EventBackbone events for cross-module routing
  3. Route events to registered module handlers
  4. Track integration health and event flow metrics
  5. Detect broken integration links (modules not responding)
  6. Publish integration status events

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Non-destructive: routes events, does not modify them
  - Bounded: configurable max events in flight
  - Audit trail: every routing decision is logged
  - Graceful degradation: missing modules logged but not fatal

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_ROUTE_HISTORY = 10_000
_MAX_REGISTERED_MODULES = 100


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ModulePhase(str, Enum):
    """Automation phase a module belongs to."""
    FOUNDATION = "foundation"       # Phase 0
    OBSERVABILITY = "observability"  # Phase 1
    DEVELOPMENT = "development"     # Phase 2
    SUPPORT = "support"             # Phase 3
    MARKETING = "marketing"         # Phase 4
    BUSINESS = "business"           # Phase 5
    ADVANCED = "advanced"           # Phase 6
    INTEGRATION = "integration"     # Phase 7


class RouteStatus(str, Enum):
    """Outcome of an event routing attempt."""
    DELIVERED = "delivered"
    NO_HANDLER = "no_handler"
    HANDLER_ERROR = "handler_error"
    MODULE_MISSING = "module_missing"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RegisteredModule:
    """A module registered in the integration hub."""
    design_label: str
    name: str
    phase: ModulePhase
    handler: Optional[Callable] = None
    description: str = ""
    registered_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    events_routed: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "design_label": self.design_label,
            "name": self.name,
            "phase": self.phase.value,
            "description": self.description,
            "registered_at": self.registered_at,
            "events_routed": self.events_routed,
            "errors": self.errors,
        }


@dataclass
class RouteRecord:
    """Record of an event routing decision."""
    route_id: str
    event_type: str
    source_module: str
    target_module: str
    status: RouteStatus
    payload_summary: str = ""
    routed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "event_type": self.event_type,
            "source_module": self.source_module,
            "target_module": self.target_module,
            "status": self.status.value,
            "payload_summary": self.payload_summary,
            "routed_at": self.routed_at,
        }


@dataclass
class IntegrationHealthReport:
    """Summary of integration health across all modules."""
    report_id: str
    total_modules: int
    healthy_modules: int
    total_events_routed: int
    total_errors: int
    phase_summary: Dict[str, int] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_modules": self.total_modules,
            "healthy_modules": self.healthy_modules,
            "total_events_routed": self.total_events_routed,
            "total_errors": self.total_errors,
            "phase_summary": dict(self.phase_summary),
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# AutomationIntegrationHub
# ---------------------------------------------------------------------------

class AutomationIntegrationHub:
    """Master orchestration layer for cross-phase module coordination.

    Design Label: INT-001
    Owner: Platform Engineering / Architecture Team

    Usage::

        hub = AutomationIntegrationHub(
            event_backbone=backbone,
            persistence_manager=pm,
        )
        hub.register_module("OBS-001", "HealthMonitor", ModulePhase.OBSERVABILITY,
                            handler=health_monitor.handle_event)
        hub.route_event("LEARNING_FEEDBACK", source="OBS-003",
                        payload={"pattern": "recurring_timeout"})
    """

    def __init__(
        self,
        event_backbone=None,
        persistence_manager=None,
        max_route_history: int = _MAX_ROUTE_HISTORY,
    ) -> None:
        self._lock = threading.Lock()
        self._backbone = event_backbone
        self._pm = persistence_manager
        self._modules: Dict[str, RegisteredModule] = {}
        self._event_routes: Dict[str, List[str]] = defaultdict(list)
        self._route_history: List[RouteRecord] = []
        self._max_route_history = max_route_history
        self._event_counts: Counter = Counter()

    # ------------------------------------------------------------------
    # Module registration
    # ------------------------------------------------------------------

    def register_module(
        self,
        design_label: str,
        name: str,
        phase: ModulePhase,
        handler: Optional[Callable] = None,
        description: str = "",
        event_types: Optional[List[str]] = None,
    ) -> RegisteredModule:
        """Register a module with the integration hub."""
        module = RegisteredModule(
            design_label=design_label,
            name=name,
            phase=phase,
            handler=handler,
            description=description,
        )
        with self._lock:
            if len(self._modules) >= _MAX_REGISTERED_MODULES:
                logger.warning("Max registered modules reached (%d)", _MAX_REGISTERED_MODULES)
                return module
            self._modules[design_label] = module
            if event_types:
                for et in event_types:
                    if design_label not in self._event_routes[et]:
                        self._event_routes[et].append(design_label)
        logger.info("Registered module %s (%s) in phase %s", design_label, name, phase.value)
        return module

    def unregister_module(self, design_label: str) -> bool:
        """Unregister a module from the integration hub."""
        with self._lock:
            if design_label not in self._modules:
                return False
            del self._modules[design_label]
            for et in list(self._event_routes.keys()):
                if design_label in self._event_routes[et]:
                    self._event_routes[et].remove(design_label)
            return True

    # ------------------------------------------------------------------
    # Event routing
    # ------------------------------------------------------------------

    def route_event(
        self,
        event_type: str,
        source: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> List[RouteRecord]:
        """Route an event to all registered handlers for that event type."""
        payload = payload or {}
        records: List[RouteRecord] = []

        with self._lock:
            targets = list(self._event_routes.get(event_type, []))

        if not targets:
            record = RouteRecord(
                route_id=f"rte-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                source_module=source,
                target_module="none",
                status=RouteStatus.NO_HANDLER,
                payload_summary=str(payload)[:200],
            )
            with self._lock:
                self._append_route(record)
            return [record]

        for label in targets:
            with self._lock:
                module = self._modules.get(label)
            if module is None:
                record = RouteRecord(
                    route_id=f"rte-{uuid.uuid4().hex[:8]}",
                    event_type=event_type,
                    source_module=source,
                    target_module=label,
                    status=RouteStatus.MODULE_MISSING,
                )
                with self._lock:
                    self._append_route(record)
                records.append(record)
                continue

            status = RouteStatus.DELIVERED
            if module.handler is not None:
                try:
                    module.handler(event_type, payload)
                except Exception as exc:
                    logger.warning("Handler error for %s: %s", label, exc)
                    status = RouteStatus.HANDLER_ERROR
                    with self._lock:
                        module.errors += 1

            with self._lock:
                module.events_routed += 1
                self._event_counts[event_type] += 1

            record = RouteRecord(
                route_id=f"rte-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                source_module=source,
                target_module=label,
                status=status,
                payload_summary=str(payload)[:200],
            )
            with self._lock:
                self._append_route(record)
            records.append(record)

        # Publish integration event
        if self._backbone is not None:
            self._publish_event(event_type, source, len(records))

        return records

    def add_event_route(self, event_type: str, design_label: str) -> None:
        """Add an event type → module route."""
        with self._lock:
            if design_label not in self._event_routes[event_type]:
                self._event_routes[event_type].append(design_label)

    def remove_event_route(self, event_type: str, design_label: str) -> None:
        """Remove an event type → module route."""
        with self._lock:
            if design_label in self._event_routes.get(event_type, []):
                self._event_routes[event_type].remove(design_label)

    # ------------------------------------------------------------------
    # Health reporting
    # ------------------------------------------------------------------

    def generate_health_report(self) -> IntegrationHealthReport:
        """Generate an integration health report across all modules."""
        with self._lock:
            modules = list(self._modules.values())

        total = len(modules)
        healthy = sum(1 for m in modules if m.errors == 0)
        total_routed = sum(m.events_routed for m in modules)
        total_errors = sum(m.errors for m in modules)

        phase_counts: Dict[str, int] = Counter()
        for m in modules:
            phase_counts[m.phase.value] += 1

        report = IntegrationHealthReport(
            report_id=f"ihr-{uuid.uuid4().hex[:8]}",
            total_modules=total,
            healthy_modules=healthy,
            total_events_routed=total_routed,
            total_errors=total_errors,
            phase_summary=dict(phase_counts),
        )

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(
                    doc_id=report.report_id,
                    document=report.to_dict(),
                )
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        return report

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_module(self, design_label: str) -> Optional[Dict[str, Any]]:
        """Get a registered module by design label."""
        with self._lock:
            mod = self._modules.get(design_label)
        return mod.to_dict() if mod else None

    def list_modules(
        self, phase: Optional[ModulePhase] = None, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List registered modules, optionally filtered by phase."""
        with self._lock:
            modules = list(self._modules.values())
        if phase is not None:
            modules = [m for m in modules if m.phase == phase]
        return [m.to_dict() for m in modules[:limit]]

    def get_route_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent route records."""
        with self._lock:
            history = list(self._route_history)
        return [r.to_dict() for r in history[-limit:]]

    def get_event_routes(self) -> Dict[str, List[str]]:
        """Return the current event routing table."""
        with self._lock:
            return {k: list(v) for k, v in self._event_routes.items()}

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return integration hub status summary."""
        with self._lock:
            return {
                "total_modules": len(self._modules),
                "total_event_types": len(self._event_routes),
                "total_routes": sum(len(v) for v in self._event_routes.values()),
                "total_events_routed": sum(self._event_counts.values()),
                "route_history_size": len(self._route_history),
                "event_counts": dict(self._event_counts),
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_route(self, record: RouteRecord) -> None:
        """Append a route record, evicting oldest if over limit."""
        if len(self._route_history) >= self._max_route_history:
            evict = max(1, self._max_route_history // 10)
            self._route_history = self._route_history[evict:]
        self._route_history.append(record)

    def _publish_event(self, event_type: str, source: str, target_count: int) -> None:
        """Publish an integration routing event to EventBackbone."""
        try:
            from event_backbone import EventType as ET, Event
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.LEARNING_FEEDBACK,
                payload={
                    "source": "automation_integration_hub",
                    "action": "event_routed",
                    "routed_event_type": event_type,
                    "origin": source,
                    "target_count": target_count,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="automation_integration_hub",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
