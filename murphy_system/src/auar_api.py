"""
AUAR API Integration Module
============================

Wires the AUAR (Adaptive Universal API Router) pipeline into the
Murphy System as a set of REST API endpoints.  This module provides:

  - POST /api/auar/route     — Execute a full AUAR pipeline request
  - POST /api/auar/register  — Register a capability + provider (admin only)
  - DELETE /api/auar/provider/{id} — Deregister a provider (admin only)
  - DELETE /api/auar/capability/{id} — Deregister a capability (admin only)
  - GET  /api/auar/stats     — System statistics (ML, routing, observability)
  - GET  /api/auar/health    — AUAR subsystem health check

Usage:
    from src.auar_api import create_auar_router, initialize_auar
    auar_components = initialize_auar()
    app.include_router(create_auar_router(auar_components))

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import os
from typing import Any, Dict, List, Optional

from auar import (
    AdapterConfig,
    AUARConfig,
    AUARPipeline,
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
    RoutingStrategy,
    SchemaMapping,
    SchemaTranslator,
    SignalInterpreter,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request/response models (Issue #3)
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, Field, field_validator
    _PYDANTIC_AVAILABLE = True
except ImportError:
    _PYDANTIC_AVAILABLE = False

if _PYDANTIC_AVAILABLE:
    class RouteRequest(BaseModel):
        """Validated payload for POST /api/auar/route."""
        capability: str = Field(..., min_length=1, max_length=256)
        parameters: Dict[str, Any] = Field(default_factory=dict)
        tenant_id: str = Field(default="", max_length=256)
        user_id: str = Field(default="", max_length=256)

    class CapabilityRegistration(BaseModel):
        """Validated capability section of a registration payload."""
        name: str = Field(..., min_length=1, max_length=256)
        domain: str = Field(default="", max_length=256)
        category: str = Field(default="", max_length=256)
        required_params: List[str] = Field(default_factory=list)
        semantic_tags: List[str] = Field(default_factory=list)

    class ProviderRegistration(BaseModel):
        """Validated provider section of a registration payload."""
        name: str = Field(..., min_length=1, max_length=256)
        base_url: str = Field(default="", max_length=2048)
        auth_method: str = Field(default="api_key", max_length=64)
        cost_per_call: float = Field(default=0.0, ge=0.0)
        avg_latency_ms: float = Field(default=100.0, ge=0.0)
        success_rate: float = Field(default=0.99, ge=0.0, le=1.0)
        certification_level: str = Field(default="production", max_length=64)
        auth_credentials: Dict[str, str] = Field(default_factory=dict)

    class FieldMappingModel(BaseModel):
        """Validated field mapping."""
        source_field: str = Field(..., min_length=1, max_length=512)
        target_field: str = Field(..., min_length=1, max_length=512)
        transform: Optional[str] = None
        default_value: Optional[Any] = None
        required: bool = False

    class SchemaMappingModel(BaseModel):
        """Validated schema mapping."""
        direction: str = Field(default="request", max_length=64)
        field_mappings: List[FieldMappingModel] = Field(default_factory=list)
        static_fields: Dict[str, Any] = Field(default_factory=dict)

    class RegisterRequest(BaseModel):
        """Validated payload for POST /api/auar/register."""
        capability: Optional[CapabilityRegistration] = None
        provider: Optional[ProviderRegistration] = None
        schema_mappings: List[SchemaMappingModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Bootstrap helper
# ---------------------------------------------------------------------------

class AUARComponents:
    """Container for all initialised AUAR components."""

    def __init__(self, config: Optional[AUARConfig] = None):
        cfg = config or AUARConfig.from_env()
        self.config = cfg
        self.graph = CapabilityGraph()
        self.interpreter = SignalInterpreter()
        self.ml = MLOptimizer(
            epsilon=cfg.ml.epsilon,
            epsilon_min=cfg.ml.epsilon_min,
            epsilon_decay=cfg.ml.epsilon_decay,
            max_latency_ms=cfg.ml.max_latency_ms,
            max_cost=cfg.ml.max_cost,
            reward_weights=dict(cfg.ml.reward_weights),
        )
        strategy = RoutingStrategy(cfg.routing.strategy)
        self.router = RoutingDecisionEngine(
            self.graph,
            strategy=strategy,
            weights=dict(cfg.routing.weights),
            circuit_failure_threshold=cfg.routing.circuit_breaker_threshold,
            circuit_recovery_s=cfg.routing.circuit_breaker_recovery_s,
            ml_optimizer=self.ml,
            ml_weight=cfg.routing.ml_weight,
            max_latency_ms=cfg.routing.max_latency_ms,
            max_cost=cfg.routing.max_cost,
            half_open_required_successes=cfg.routing.half_open_required_successes,
            half_open_traffic_ratio=cfg.routing.half_open_traffic_ratio,
        )
        self.translator = SchemaTranslator()
        self.adapters = ProviderAdapterManager()
        self.observability = ObservabilityLayer(
            max_traces=cfg.observability.max_traces,
            max_audit=cfg.observability.max_audit_entries,
        )
        self.pipeline = AUARPipeline(
            interpreter=self.interpreter,
            graph=self.graph,
            router=self.router,
            translator=self.translator,
            adapters=self.adapters,
            ml=self.ml,
            observability=self.observability,
        )


def initialize_auar(config: Optional[AUARConfig] = None) -> AUARComponents:
    """Create and return a fully wired AUAR subsystem.

    If *config* is ``None``, configuration is loaded from ``AUAR_*``
    environment variables via :meth:`AUARConfig.from_env`.
    """
    cfg = config or AUARConfig.from_env()
    components = AUARComponents(config=cfg)
    logger.info(
        "AUAR subsystem initialised (FAPI v%s) — strategy=%s, epsilon=%.3f",
        cfg.version, cfg.routing.strategy, cfg.ml.epsilon,
    )
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


def handle_register(
    components: AUARComponents,
    body: Dict[str, Any],
    *,
    actor: str = "",
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Register a capability and/or provider.

    *actor* and *tenant_id* are used for audit logging when called via
    the authenticated API endpoint.
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

        # Audit the registration action
        components.observability.audit(
            actor=actor or "system",
            action="register_capability",
            resource=f"capability:{cap.name}",
            detail={"capability_id": cap_id, "domain": cap.domain},
            tenant_id=tenant_id,
        )

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

        # Audit the registration action
        components.observability.audit(
            actor=actor or "system",
            action="register_provider",
            resource=f"provider:{provider.name}",
            detail={"provider_id": provider.id, "base_url": provider.base_url},
            tenant_id=tenant_id,
        )

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


def handle_deregister_provider(
    components: AUARComponents,
    provider_id: str,
    *,
    actor: str = "",
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Deregister a provider and cascade-remove related state."""
    removed = components.graph.deregister_provider(provider_id)
    if not removed:
        return {"success": False, "error": f"Provider {provider_id} not found"}

    # Cascade: remove adapter
    components.adapters.deregister_adapter(provider_id)

    # Cascade: remove schema mappings for this provider
    components.translator.deregister_provider_mappings(provider_id)

    # Audit
    components.observability.audit(
        actor=actor or "system",
        action="deregister_provider",
        resource=f"provider:{provider_id}",
        tenant_id=tenant_id,
    )
    return {"success": True, "provider_id": provider_id}


def handle_deregister_capability(
    components: AUARComponents,
    capability_name: str,
    *,
    actor: str = "",
    tenant_id: str = "",
) -> Dict[str, Any]:
    """Deregister a capability and cascade-remove related state."""
    removed = components.graph.deregister_capability(capability_name)
    if not removed:
        return {"success": False, "error": f"Capability {capability_name} not found"}

    # Cascade: remove schema mappings for this capability
    components.translator.deregister_capability_mappings(capability_name)

    # Audit
    components.observability.audit(
        actor=actor or "system",
        action="deregister_capability",
        resource=f"capability:{capability_name}",
        tenant_id=tenant_id,
    )
    return {"success": True, "capability_name": capability_name}


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

def _get_admin_user(request: Any) -> Optional[str]:
    """Extract and validate admin user from request headers.

    Returns the user ID if the caller has admin privileges, else ``None``.
    The ``X-User-Role`` header must be ``admin`` for write endpoints.
    """
    user_id = request.headers.get("x-user-id", "")
    role = request.headers.get("x-user-role", "")
    if role == "admin" and user_id:
        return user_id
    return None


def create_auar_router(components: Optional[AUARComponents] = None):
    """Create a FastAPI ``APIRouter`` with AUAR endpoints.

    If *components* is ``None`` a fresh set is initialised via
    ``initialize_auar()``.

    Returns ``None`` gracefully if FastAPI is not installed, so callers
    that only need the handler functions are not forced to depend on
    FastAPI.

    Security Note:
        This module returns an APIRouter. The parent FastAPI application
        that mounts this router MUST apply security hardening via
        :func:`fastapi_security.configure_secure_fastapi` to enforce
        authentication, CORS, and rate limiting.  See
        :func:`create_secure_auar_app` for a convenience wrapper that
        does this automatically.
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

    router = APIRouter(tags=["auar"])

    @router.post("/route")
    async def route_request(request: Request) -> JSONResponse:
        """Execute a full AUAR pipeline request."""
        if _PYDANTIC_AVAILABLE:
            body = await request.json()
            try:
                validated = RouteRequest(**body)
                body = validated.model_dump()
            except Exception as exc:
                return JSONResponse(
                    content={"error": f"Validation error: {exc}"},
                    status_code=422,
                )
        else:
            body = await request.json()
        result = handle_route(components, body)
        status = 200 if result.get("success") else 422
        return JSONResponse(content=result, status_code=status)

    @router.post("/register")
    async def register_capability(request: Request) -> JSONResponse:
        """Register a capability and/or provider (admin only)."""
        admin_user = _get_admin_user(request)
        if not admin_user:
            components.observability.audit(
                actor=request.headers.get("x-user-id", "anonymous"),
                action="register_attempt_denied",
                resource="auar_register",
                outcome="denied",
                tenant_id=request.headers.get("x-tenant-id", ""),
            )
            return JSONResponse(
                content={"error": "Admin role required for registration"},
                status_code=403,
            )
        if _PYDANTIC_AVAILABLE:
            body = await request.json()
            try:
                validated = RegisterRequest(**body)
                body = validated.model_dump(exclude_none=True)
            except Exception as exc:
                return JSONResponse(
                    content={"error": f"Validation error: {exc}"},
                    status_code=422,
                )
        else:
            body = await request.json()
        tenant_id = request.headers.get("x-tenant-id", "")
        result = handle_register(
            components, body, actor=admin_user, tenant_id=tenant_id,
        )
        return JSONResponse(content=result, status_code=201)

    @router.delete("/provider/{provider_id}")
    async def deregister_provider(provider_id: str, request: Request) -> JSONResponse:
        """Deregister a provider (admin only)."""
        admin_user = _get_admin_user(request)
        if not admin_user:
            return JSONResponse(
                content={"error": "Admin role required"},
                status_code=403,
            )
        tenant_id = request.headers.get("x-tenant-id", "")
        result = handle_deregister_provider(
            components, provider_id, actor=admin_user, tenant_id=tenant_id,
        )
        status = 200 if result.get("success") else 404
        return JSONResponse(content=result, status_code=status)

    @router.delete("/capability/{capability_name}")
    async def deregister_capability(capability_name: str, request: Request) -> JSONResponse:
        """Deregister a capability (admin only)."""
        admin_user = _get_admin_user(request)
        if not admin_user:
            return JSONResponse(
                content={"error": "Admin role required"},
                status_code=403,
            )
        tenant_id = request.headers.get("x-tenant-id", "")
        result = handle_deregister_capability(
            components, capability_name, actor=admin_user, tenant_id=tenant_id,
        )
        status = 200 if result.get("success") else 404
        return JSONResponse(content=result, status_code=status)

    @router.get("/stats")
    async def get_stats() -> JSONResponse:
        """Return AUAR system statistics."""
        return JSONResponse(content=handle_stats(components))

    @router.get("/health")
    async def health_check() -> JSONResponse:
        """AUAR subsystem health check."""
        return JSONResponse(content=handle_health(components))

    return router


def create_secure_auar_app(components: Optional[AUARComponents] = None):
    """Create a security-hardened FastAPI application with AUAR endpoints.

    Convenience wrapper that:
      1. Creates a :class:`FastAPI` application.
      2. Applies :func:`fastapi_security.configure_secure_fastapi`
         (CORS, API-key auth, rate limiting, security headers).
      3. Mounts the AUAR router.

    Raises ``RuntimeError`` if ``fastapi_security`` is not importable
    unless the ``AUAR_ALLOW_INSECURE=true`` environment variable is set.
    Returns ``None`` if FastAPI is not installed.
    """
    try:
        from fastapi import FastAPI as _FastAPI
    except ImportError:
        logger.warning("FastAPI not installed — secure AUAR app unavailable.")
        return None

    router = create_auar_router(components)
    if router is None:
        return None

    app = _FastAPI(title="AUAR API", version="0.1.0")

    # Apply security hardening (SEC-001, SEC-002, SEC-004)
    try:
        from fastapi_security import configure_secure_fastapi
        configure_secure_fastapi(app, service_name="auar-api")
    except ImportError:
        allow_insecure = os.environ.get("AUAR_ALLOW_INSECURE", "").lower() == "true"
        if allow_insecure:
            logger.warning(
                "╔══════════════════════════════════════════════════════════╗\n"
                "║  WARNING: AUAR running WITHOUT security middleware!     ║\n"
                "║  AUAR_ALLOW_INSECURE=true — for development only.      ║\n"
                "╚══════════════════════════════════════════════════════════╝"
            )
        else:
            raise RuntimeError(
                "fastapi_security module is required but not installed. "
                "Install it or set AUAR_ALLOW_INSECURE=true for development."
            )

    app.include_router(router)
    return app
