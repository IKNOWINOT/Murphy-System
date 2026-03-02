"""
AUAR API Integration Module
============================

Wires the AUAR (Adaptive Universal API Router) pipeline into the
Murphy System as a set of REST API endpoints.  This module provides:

  - POST /api/auar/route     — Execute a full AUAR pipeline request
  - POST /api/auar/register  — Register a capability + provider
  - GET  /api/auar/stats     — System statistics (ML, routing, observability)
  - GET  /api/auar/health    — AUAR subsystem health check

Usage:
    from src.auar_api import create_auar_router, initialize_auar
    auar_components = initialize_auar()
    app.include_router(create_auar_router(auar_components))

Copyright 2024 Inoni LLC – Apache License 2.0
"""

import logging
from typing import Any, Dict, Optional

from auar import (
    AUARPipeline,
    AdapterConfig,
    AuthMethod,
    Capability,
    CapabilityGraph,
    CapabilityMapping,
    CertificationLevel,
    FieldMapping,
    HealthStatus,
    MLOptimizer,
    ObservabilityLayer,
    PerformanceMetrics,
    PipelineResult,
    Provider,
    ProviderAdapterManager,
    RequestContext,
    RoutingDecisionEngine,
    SchemaMapping,
    SchemaTranslator,
    SignalInterpreter,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bootstrap helper
# ---------------------------------------------------------------------------

class AUARComponents:
    """Container for all initialised AUAR components."""

    def __init__(self):
        self.graph = CapabilityGraph()
        self.interpreter = SignalInterpreter()
        self.ml = MLOptimizer()
        self.router = RoutingDecisionEngine(self.graph, ml_optimizer=self.ml)
        self.translator = SchemaTranslator()
        self.adapters = ProviderAdapterManager()
        self.observability = ObservabilityLayer()
        self.pipeline = AUARPipeline(
            interpreter=self.interpreter,
            graph=self.graph,
            router=self.router,
            translator=self.translator,
            adapters=self.adapters,
            ml=self.ml,
            observability=self.observability,
        )


def initialize_auar() -> AUARComponents:
    """Create and return a fully wired AUAR subsystem."""
    components = AUARComponents()
    logger.info("AUAR subsystem initialised (FAPI v0.1.0)")
    return components


# ---------------------------------------------------------------------------
# API route factory (framework-agnostic dict-based handlers)
# ---------------------------------------------------------------------------

def handle_route(components: AUARComponents, body: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a full AUAR pipeline request.

    Expected body::

        {
            "capability": "send_email",
            "parameters": {"to": "user@example.com", ...},
            "tenant_id": "optional-tenant-id",
            "user_id": "optional-user-id"
        }

    Returns a dict with PipelineResult fields.
    """
    ctx = RequestContext(
        tenant_id=body.get("tenant_id", ""),
        user_id=body.get("user_id", ""),
    )
    result = components.pipeline.execute(body, context=ctx)
    return {
        "success": result.success,
        "request_id": result.request_id,
        "capability": result.capability,
        "provider_id": result.provider_id,
        "provider_name": result.provider_name,
        "response_body": result.response_body,
        "response_status": result.response_status,
        "confidence_score": result.confidence_score,
        "routing_score": result.routing_score,
        "total_latency_ms": result.total_latency_ms,
        "interpretation_method": result.interpretation_method,
        "requires_clarification": result.requires_clarification,
        "error": result.error,
        "trace_id": result.trace_id,
        "ml_reward": result.ml_reward,
    }


def handle_register(components: AUARComponents, body: Dict[str, Any]) -> Dict[str, Any]:
    """Register a capability and/or provider.

    Expected body::

        {
            "capability": {
                "name": "send_email",
                "domain": "communication",
                "category": "email",
                "semantic_tags": ["email", "messaging"]
            },
            "provider": {
                "name": "SendGrid",
                "base_url": "https://api.sendgrid.com",
                "auth_method": "api_key",
                "cost_per_call": 0.001
            },
            "schema_mappings": [
                {
                    "direction": "request",
                    "field_mappings": [
                        {"source_field": "to", "target_field": "personalizations.to"}
                    ]
                }
            ]
        }
    """
    result: Dict[str, Any] = {"registered": []}

    cap_data = body.get("capability", {})
    cap_id = ""
    if cap_data and cap_data.get("name"):
        cap = Capability(
            name=cap_data["name"],
            domain=cap_data.get("domain", ""),
            category=cap_data.get("category", ""),
            semantic_tags=cap_data.get("semantic_tags", []),
        )
        cap_id = components.graph.register_capability(cap)

        # Register schema in interpreter
        components.interpreter.register_schema(
            cap.name,
            required_params=cap_data.get("required_params", []),
            domain=cap.domain,
            category=cap.category,
        )
        result["registered"].append(f"capability:{cap.name}")
        result["capability_id"] = cap_id

    prov_data = body.get("provider", {})
    if prov_data and prov_data.get("name"):
        perf = PerformanceMetrics(
            avg_latency_ms=prov_data.get("avg_latency_ms", 100),
            success_rate=prov_data.get("success_rate", 0.99),
        )
        mapping = CapabilityMapping(
            capability_id=cap_id,
            cost_per_call=prov_data.get("cost_per_call", 0.0),
            performance=perf,
            certification_level=CertificationLevel(
                prov_data.get("certification_level", "production")
            ),
        )
        provider = Provider(
            name=prov_data["name"],
            base_url=prov_data.get("base_url", ""),
            supported_capabilities=[mapping],
            health_status=HealthStatus.HEALTHY,
        )
        components.graph.register_provider(provider)

        # Register adapter
        auth_method = AuthMethod(prov_data.get("auth_method", "api_key"))
        components.adapters.register_adapter(AdapterConfig(
            provider_id=provider.id,
            provider_name=provider.name,
            base_url=provider.base_url,
            auth_method=auth_method,
            auth_credentials=prov_data.get("auth_credentials", {}),
        ))
        result["registered"].append(f"provider:{provider.name}")
        result["provider_id"] = provider.id

    # Register schema mappings
    for sm_data in body.get("schema_mappings", []):
        if prov_data and cap_data:
            field_mappings = [
                FieldMapping(
                    source_field=fm["source_field"],
                    target_field=fm["target_field"],
                    transform=fm.get("transform"),
                    default_value=fm.get("default_value"),
                    required=fm.get("required", False),
                )
                for fm in sm_data.get("field_mappings", [])
            ]
            sm = SchemaMapping(
                capability_name=cap_data["name"],
                provider_id=result.get("provider_id", ""),
                direction=sm_data.get("direction", "request"),
                field_mappings=field_mappings,
                static_fields=sm_data.get("static_fields", {}),
            )
            components.translator.register_mapping(sm)
            result["registered"].append(f"schema_mapping:{sm.direction}")

    return result


def handle_stats(components: AUARComponents) -> Dict[str, Any]:
    """Return AUAR system statistics."""
    return {
        "graph": components.graph.get_stats(),
        "interpreter": components.interpreter.get_stats(),
        "routing": components.router.get_stats(),
        "ml": components.ml.get_stats(),
        "translator": components.translator.get_stats(),
        "adapters": components.adapters.get_all_stats(),
        "observability": components.observability.get_stats(),
    }


def handle_health(components: AUARComponents) -> Dict[str, Any]:
    """Return AUAR subsystem health."""
    graph_stats = components.graph.get_stats()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "codename": "FAPI",
        "capabilities_registered": graph_stats["total_capabilities"],
        "providers_registered": graph_stats["total_providers"],
        "ml_observations": components.ml.get_stats()["total_observations"],
        "active_traces": components.observability.get_stats()["traces"],
    }


# ---------------------------------------------------------------------------
# FastAPI router factory
# ---------------------------------------------------------------------------

def create_auar_router(components: Optional[AUARComponents] = None):
    """Create a FastAPI ``APIRouter`` with AUAR endpoints.

    If *components* is ``None`` a fresh set is initialised via
    ``initialize_auar()``.

    Returns ``None`` gracefully if FastAPI is not installed, so callers
    that only need the handler functions are not forced to depend on
    FastAPI.
    """
    try:
        from fastapi import APIRouter, Request
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.warning(
            "FastAPI not installed — AUAR REST endpoints unavailable.  "
            "Install with: pip install fastapi"
        )
        return None

    if components is None:
        components = initialize_auar()

    router = APIRouter(prefix="/api/auar", tags=["auar"])

    @router.post("/route")
    async def route_request(request: Request) -> JSONResponse:
        """Execute a full AUAR pipeline request."""
        body = await request.json()
        result = handle_route(components, body)
        status = 200 if result.get("success") else 422
        return JSONResponse(content=result, status_code=status)

    @router.post("/register")
    async def register_capability(request: Request) -> JSONResponse:
        """Register a capability and/or provider."""
        body = await request.json()
        result = handle_register(components, body)
        return JSONResponse(content=result, status_code=201)

    @router.get("/stats")
    async def get_stats() -> JSONResponse:
        """Return AUAR system statistics."""
        return JSONResponse(content=handle_stats(components))

    @router.get("/health")
    async def health_check() -> JSONResponse:
        """AUAR subsystem health check."""
        return JSONResponse(content=handle_health(components))

    return router
