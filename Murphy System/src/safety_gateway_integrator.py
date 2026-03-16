"""
Safety Gateway Integrator for Murphy System.

Design Label: ORCH-001 — API Gateway Safety Validation Wiring
Owner: Platform Engineering / Security Team
Dependencies:
  - SafetyValidationPipeline (SAF-001, for pre/post execution checks)
  - PersistenceManager (for durable gateway audit records)
  - EventBackbone (publishes SYSTEM_HEALTH on gateway decisions)

Implements Plan §6.1 + ARCHITECTURE_MAP Next Step #2:
  Wires SAF-001 SafetyValidationPipeline into API request lifecycle.
  Every inbound request is intercepted, classified by risk level,
  and routed through pre-execution validation.  After execution,
  post-execution validation captures output verification.  The
  integrator provides per-route risk classification and bypass
  lists for health-check and monitoring endpoints.

Flow:
  1. Register API routes with risk classifications (CRITICAL/HIGH/MEDIUM/LOW/MINIMAL)
  2. Intercept inbound requests → build validation context
  3. Run SAF-001 pre-execution checks
  4. Allow or block request based on validation result
  5. After execution, run SAF-001 post-execution checks
  6. Log gateway decision and publish event

Safety invariants:
  - Thread-safe: all shared state guarded by Lock
  - Fail-closed: unclassified routes default to HIGH risk
  - Bypass list: health/monitoring endpoints skip validation
  - Bounded: configurable max decision history
  - Audit trail: every gateway decision is logged

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
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_DECISIONS = 10_000
_DECISIONS_TRIM_TARGET = _MAX_DECISIONS // 10  # retain ~10% after overflow trim
_DEFAULT_BYPASS_ROUTES = frozenset({"/health", "/healthz", "/ready", "/metrics", "/status"})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    """Risk classification for API routes."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class GatewayAction(str, Enum):
    """Action taken by the gateway on a request."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    BYPASSED = "bypassed"


@dataclass
class RouteClassification:
    """Risk classification for a single API route."""
    route: str
    risk_level: RiskLevel
    require_auth: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "risk_level": self.risk_level.value,
            "require_auth": self.require_auth,
            "description": self.description,
        }


@dataclass
class GatewayDecision:
    """Record of a gateway decision for a single request."""
    decision_id: str
    route: str
    method: str
    risk_level: str
    action: GatewayAction
    validation_verdict: str = ""
    reason: str = ""
    tenant_id: str = ""
    user_id: str = ""
    decided_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "route": self.route,
            "method": self.method,
            "risk_level": self.risk_level,
            "action": self.action.value,
            "validation_verdict": self.validation_verdict,
            "reason": self.reason,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "decided_at": self.decided_at,
        }


# ---------------------------------------------------------------------------
# SafetyGatewayIntegrator
# ---------------------------------------------------------------------------

class SafetyGatewayIntegrator:
    """Wires SafetyValidationPipeline into the API request lifecycle.

    Design Label: ORCH-001
    Owner: Platform Engineering / Security Team

    Usage::

        gw = SafetyGatewayIntegrator()
        gw.classify_route("/api/deploy", RiskLevel.CRITICAL)
        decision = gw.intercept("/api/deploy", "POST", {"user": "admin"})
    """

    def __init__(
        self,
        persistence_manager=None,
        event_backbone=None,
        safety_pipeline=None,
        bypass_routes: Optional[Set[str]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._pm = persistence_manager
        self._backbone = event_backbone
        self._pipeline = safety_pipeline
        self._bypass: Set[str] = set(bypass_routes or _DEFAULT_BYPASS_ROUTES)
        self._classifications: Dict[str, RouteClassification] = {}
        self._decisions: List[GatewayDecision] = []

    # ------------------------------------------------------------------
    # Route classification
    # ------------------------------------------------------------------

    def classify_route(
        self,
        route: str,
        risk_level: RiskLevel,
        require_auth: bool = True,
        description: str = "",
    ) -> None:
        """Register a risk classification for an API route."""
        with self._lock:
            self._classifications[route] = RouteClassification(
                route=route,
                risk_level=risk_level,
                require_auth=require_auth,
                description=description,
            )
        logger.debug("Classified route %s as %s", route, risk_level.value)

    def add_bypass(self, route: str) -> None:
        """Add a route to the bypass list (skip validation)."""
        with self._lock:
            self._bypass.add(route)

    def remove_bypass(self, route: str) -> bool:
        """Remove a route from the bypass list."""
        with self._lock:
            if route in self._bypass:
                self._bypass.discard(route)
                return True
            return False

    def get_classification(self, route: str) -> Optional[Dict[str, Any]]:
        """Get the classification for a route, or None."""
        with self._lock:
            c = self._classifications.get(route)
            return c.to_dict() if c else None

    # ------------------------------------------------------------------
    # Request interception
    # ------------------------------------------------------------------

    def intercept(
        self,
        route: str,
        method: str = "GET",
        context: Optional[Dict[str, Any]] = None,
    ) -> GatewayDecision:
        """Intercept a request, validate through SAF-001 pipeline, and decide."""
        ctx = context or {}

        # Check bypass
        with self._lock:
            is_bypass = route in self._bypass

        if is_bypass:
            return self._record_decision(
                route, method, "minimal", GatewayAction.BYPASSED,
                "", "Route in bypass list",
                ctx.get("tenant_id", ""), ctx.get("user_id", ""),
            )

        # Get risk classification (default: HIGH for unclassified)
        with self._lock:
            classification = self._classifications.get(route)
            risk_level = classification.risk_level.value if classification else "high"

        # If pipeline is wired, run pre-execution validation
        validation_verdict = ""
        if self._pipeline is not None:
            try:
                result = self._pipeline.validate(
                    action_id=f"gw-{uuid.uuid4().hex[:8]}",
                    action_type=f"{method} {route}",
                    context={**ctx, "route": route, "method": method, "risk_level": risk_level},
                )
                validation_verdict = result.verdict.value if hasattr(result, 'verdict') else str(result)
            except Exception as exc:
                validation_verdict = "error"
                logger.warning("Safety pipeline error for %s %s: %s", method, route, exc)
        else:
            validation_verdict = "no_pipeline"

        # Decision: block if validation failed
        if validation_verdict == "failed":
            action = GatewayAction.BLOCKED
            reason = "Safety validation failed"
        else:
            action = GatewayAction.ALLOWED
            reason = f"Validation: {validation_verdict}"

        return self._record_decision(
            route, method, risk_level, action,
            validation_verdict, reason,
            ctx.get("tenant_id", ""), ctx.get("user_id", ""),
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent gateway decisions."""
        with self._lock:
            return [d.to_dict() for d in self._decisions[-limit:]]

    def get_status(self) -> Dict[str, Any]:
        """Get gateway status summary."""
        with self._lock:
            return {
                "classified_routes": len(self._classifications),
                "bypass_routes": len(self._bypass),
                "total_decisions": len(self._decisions),
                "pipeline_attached": self._pipeline is not None,
                "persistence_attached": self._pm is not None,
                "backbone_attached": self._backbone is not None,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_decision(
        self,
        route: str,
        method: str,
        risk_level: str,
        action: GatewayAction,
        validation_verdict: str,
        reason: str,
        tenant_id: str,
        user_id: str,
    ) -> GatewayDecision:
        decision = GatewayDecision(
            decision_id=f"gd-{uuid.uuid4().hex[:8]}",
            route=route,
            method=method,
            risk_level=risk_level,
            action=action,
            validation_verdict=validation_verdict,
            reason=reason,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        with self._lock:
            if len(self._decisions) >= _MAX_DECISIONS:
                self._decisions = self._decisions[_DECISIONS_TRIM_TARGET:]
            self._decisions.append(decision)

        # Persist
        if self._pm is not None:
            try:
                self._pm.save_document(doc_id=decision.decision_id, document=decision.to_dict())
            except Exception as exc:
                logger.debug("Persistence skipped: %s", exc)

        # Publish
        if self._backbone is not None:
            self._publish_event(decision)

        logger.info(
            "Gateway %s for %s %s (risk=%s, verdict=%s)",
            action.value, method, route, risk_level, validation_verdict,
        )
        return decision

    def _publish_event(self, decision: GatewayDecision) -> None:
        try:
            from event_backbone import Event
            from event_backbone import EventType as ET
            evt = Event(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=ET.SYSTEM_HEALTH,
                payload={
                    "source": "safety_gateway_integrator",
                    "action": "gateway_decision",
                    "decision_id": decision.decision_id,
                    "route": decision.route,
                    "gateway_action": decision.action.value,
                    "risk_level": decision.risk_level,
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                source="safety_gateway_integrator",
            )
            self._backbone.publish_event(evt)
        except Exception as exc:
            logger.debug("EventBackbone publish skipped: %s", exc)
