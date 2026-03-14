"""
Agentic API Provisioner — Murphy System

Self-provisioning API infrastructure that allows the system to autonomously
set up, configure, register, and manage its own REST/GraphQL/WebSocket API
endpoints without human intervention.

Capabilities:
  - Autonomous endpoint registration and route generation
  - Schema-driven API scaffolding from module introspection
  - Auto-discovery of capabilities from MODULE_CATALOG
  - Self-healing endpoint health monitoring
  - Rate-limit and auth policy auto-configuration
  - API versioning and deprecation management
  - OpenAPI/Swagger spec generation
  - Webhook auto-registration for event-driven APIs

All operations are pure-Python with no external dependencies.
"""

import enum
import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EndpointMethod(enum.Enum):
    """Endpoint method (Enum subclass)."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    WS = "WEBSOCKET"


class AuthPolicy(enum.Enum):
    """Auth policy (Enum subclass)."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    OAUTH2 = "oauth2"
    MUTUAL_TLS = "mutual_tls"


class EndpointStatus(enum.Enum):
    """Endpoint status (Enum subclass)."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    PROVISIONING = "provisioning"


class APIVersion(enum.Enum):
    """API version (Enum subclass)."""
    V1 = "v1"
    V2 = "v2"
    V3 = "v3"


# ---------------------------------------------------------------------------
# Endpoint Definition
# ---------------------------------------------------------------------------

class EndpointDefinition:
    """Represents a single API endpoint with all configuration."""

    def __init__(self, path: str, method: EndpointMethod, handler_name: str,
                 description: str = "", auth_policy: AuthPolicy = AuthPolicy.BEARER_TOKEN,
                 rate_limit: int = 100, version: APIVersion = APIVersion.V1,
                 request_schema: Optional[Dict] = None,
                 response_schema: Optional[Dict] = None,
                 tags: Optional[List[str]] = None):
        self.id = str(uuid.uuid4())[:12]
        self.path = path
        self.method = method
        self.handler_name = handler_name
        self.description = description
        self.auth_policy = auth_policy
        self.rate_limit = rate_limit
        self.version = version
        self.request_schema = request_schema or {}
        self.response_schema = response_schema or {}
        self.tags = tags or []
        self.status = EndpointStatus.PROVISIONING
        self.created_at = time.time()
        self.health_checks = 0
        self.health_failures = 0
        self.request_count = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "path": f"/api/{self.version.value}{self.path}",
            "method": self.method.value,
            "handler": self.handler_name,
            "description": self.description,
            "auth_policy": self.auth_policy.value,
            "rate_limit_rpm": self.rate_limit,
            "version": self.version.value,
            "status": self.status.value,
            "tags": self.tags,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "health_checks": self.health_checks,
            "health_failures": self.health_failures,
            "request_count": self.request_count,
        }


# ---------------------------------------------------------------------------
# Webhook Registration
# ---------------------------------------------------------------------------

class WebhookRegistration:
    """Auto-registered webhook for event-driven integrations."""

    def __init__(self, event_type: str, callback_url: str,
                 secret: Optional[str] = None):
        self.id = str(uuid.uuid4())[:12]
        self.event_type = event_type
        self.callback_url = callback_url
        self.secret = secret or hashlib.sha256(
            f"{event_type}:{time.time()}".encode()
        ).hexdigest()[:32]
        self.created_at = time.time()
        self.delivery_count = 0
        self.failure_count = 0
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "callback_url": self.callback_url,
            "active": self.active,
            "delivery_count": self.delivery_count,
            "failure_count": self.failure_count,
        }


# ---------------------------------------------------------------------------
# OpenAPI Spec Generator
# ---------------------------------------------------------------------------

class OpenAPISpecGenerator:
    """Generates OpenAPI 3.0 specifications from registered endpoints."""

    def __init__(self, title: str = "Murphy System API",
                 version: str = "1.0.0"):
        self.title = title
        self.version = version

    def generate(self, endpoints: List[EndpointDefinition],
                 webhooks: Optional[List[WebhookRegistration]] = None) -> Dict[str, Any]:
        paths: Dict[str, Any] = {}
        for ep in endpoints:
            full_path = f"/api/{ep.version.value}{ep.path}"
            method_key = ep.method.value.lower()
            if method_key == "websocket":
                method_key = "get"  # WebSocket upgrade over GET
            if full_path not in paths:
                paths[full_path] = {}
            paths[full_path][method_key] = {
                "summary": ep.description or ep.handler_name,
                "tags": ep.tags,
                "security": [{"bearerAuth": []}] if ep.auth_policy != AuthPolicy.NONE else [],
                "responses": {
                    "200": {
                        "description": "Successful response",
                        "content": {"application/json": {"schema": ep.response_schema}}
                    }
                },
            }
            if ep.request_schema:
                paths[full_path][method_key]["requestBody"] = {
                    "content": {"application/json": {"schema": ep.request_schema}}
                }

        spec = {
            "openapi": "3.0.3",
            "info": {"title": self.title, "version": self.version},
            "paths": paths,
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer"},
                    "apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                }
            },
        }
        if webhooks:
            spec["x-webhooks"] = {
                wh.event_type: wh.to_dict() for wh in webhooks if wh.active
            }
        return spec


# ---------------------------------------------------------------------------
# Module Introspector
# ---------------------------------------------------------------------------

class ModuleIntrospector:
    """Discovers capabilities from MODULE_CATALOG entries and generates
    endpoint definitions automatically."""

    CAPABILITY_TO_METHODS = {
        "execute": (EndpointMethod.POST, "Execute operation"),
        "status": (EndpointMethod.GET, "Get status"),
        "configure": (EndpointMethod.PUT, "Update configuration"),
        "list": (EndpointMethod.GET, "List resources"),
        "delete": (EndpointMethod.DELETE, "Delete resource"),
        "stream": (EndpointMethod.WS, "WebSocket stream"),
        "health": (EndpointMethod.GET, "Health check"),
    }

    def introspect_catalog(self, catalog: List[Dict[str, Any]]
                           ) -> List[EndpointDefinition]:
        endpoints = []
        for entry in catalog:
            name = entry.get("name", "unknown")
            caps = entry.get("capabilities", [])
            tags = [name]

            # Always generate status + execute endpoints for each module
            endpoints.append(EndpointDefinition(
                path=f"/{name}/status",
                method=EndpointMethod.GET,
                handler_name=f"{name}_status",
                description=f"Get {name} module status",
                tags=tags,
            ))
            endpoints.append(EndpointDefinition(
                path=f"/{name}/execute",
                method=EndpointMethod.POST,
                handler_name=f"{name}_execute",
                description=f"Execute {name} operation",
                tags=tags,
                request_schema={"type": "object", "properties": {
                    "action": {"type": "string"},
                    "parameters": {"type": "object"}
                }},
            ))

            # Generate capability-specific endpoints
            for cap in caps[:5]:  # Limit to avoid explosion
                cap_key = cap.lower().replace("-", "_")
                for keyword, (method, desc) in self.CAPABILITY_TO_METHODS.items():
                    if keyword in cap_key:
                        endpoints.append(EndpointDefinition(
                            path=f"/{name}/{cap_key}",
                            method=method,
                            handler_name=f"{name}_{cap_key}",
                            description=f"{desc} for {name}.{cap_key}",
                            tags=tags,
                        ))
                        break

        return endpoints


# ---------------------------------------------------------------------------
# Self-Healing Health Monitor
# ---------------------------------------------------------------------------

class EndpointHealthMonitor:
    """Monitors endpoint health and triggers self-healing actions."""

    def __init__(self, failure_threshold: int = 3,
                 check_interval: float = 60.0):
        self.failure_threshold = failure_threshold
        self.check_interval = check_interval
        self._lock = threading.Lock()
        self.healing_actions: List[Dict[str, Any]] = []

    def check_endpoint(self, endpoint: EndpointDefinition) -> Dict[str, Any]:
        endpoint.health_checks += 1
        # Simulated health check — in production this would hit the actual endpoint
        is_healthy = endpoint.status in (EndpointStatus.ACTIVE, EndpointStatus.PROVISIONING)
        result = {
            "endpoint_id": endpoint.id,
            "path": endpoint.path,
            "healthy": is_healthy,
            "check_number": endpoint.health_checks,
            "consecutive_failures": endpoint.health_failures,
        }
        if not is_healthy:
            endpoint.health_failures += 1
            if endpoint.health_failures >= self.failure_threshold:
                result["action"] = "self_heal"
                self._trigger_heal(endpoint)
        else:
            endpoint.health_failures = 0
        return result

    def _trigger_heal(self, endpoint: EndpointDefinition) -> None:
        with self._lock:
            endpoint.status = EndpointStatus.PROVISIONING
            endpoint.health_failures = 0
            self.healing_actions.append({
                "endpoint_id": endpoint.id,
                "path": endpoint.path,
                "action": "restart",
                "timestamp": time.time(),
            })
            # After heal, set back to active
            endpoint.status = EndpointStatus.ACTIVE

    def get_healing_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.healing_actions)


# ---------------------------------------------------------------------------
# Agentic API Provisioner (Orchestrator)
# ---------------------------------------------------------------------------

class AgenticAPIProvisioner:
    """Main orchestrator that autonomously provisions, manages, and heals
    the system's own API surface.

    Usage:
        provisioner = AgenticAPIProvisioner()
        provisioner.auto_provision(module_catalog)  # One-call self-setup
        spec = provisioner.generate_openapi_spec()
        status = provisioner.status()
    """

    def __init__(self, api_title: str = "Murphy System API",
                 api_version: str = "1.0.0",
                 default_auth: AuthPolicy = AuthPolicy.BEARER_TOKEN,
                 default_rate_limit: int = 100):
        self._lock = threading.Lock()
        self.api_title = api_title
        self.api_version = api_version
        self.default_auth = default_auth
        self.default_rate_limit = default_rate_limit

        self.endpoints: Dict[str, EndpointDefinition] = {}
        self.webhooks: Dict[str, WebhookRegistration] = {}
        self.introspector = ModuleIntrospector()
        self.spec_generator = OpenAPISpecGenerator(api_title, api_version)
        self.health_monitor = EndpointHealthMonitor()
        self._provisioned = False
        self._provision_log: List[Dict[str, Any]] = []

    # -- Public API --

    def auto_provision(self, module_catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Autonomously discover modules and provision API endpoints."""
        with self._lock:
            discovered = self.introspector.introspect_catalog(module_catalog)
            registered = 0
            for ep in discovered:
                ep.auth_policy = self.default_auth
                ep.rate_limit = self.default_rate_limit
                ep.status = EndpointStatus.ACTIVE
                self.endpoints[ep.id] = ep
                registered += 1

            # Auto-register system-level endpoints
            system_endpoints = self._create_system_endpoints()
            for ep in system_endpoints:
                self.endpoints[ep.id] = ep
                registered += 1

            # Auto-register default webhooks
            default_events = [
                "task.completed", "task.failed", "module.health_changed",
                "api.rate_limit_exceeded", "security.auth_failure",
                "heartbeat.sync", "integration.connected", "integration.error"
            ]
            for event in default_events:
                wh = WebhookRegistration(
                    event_type=event,
                    callback_url=f"/api/v1/webhooks/{event.replace('.', '/')}"
                )
                self.webhooks[wh.id] = wh

            self._provisioned = True
            result = {
                "status": "provisioned",
                "endpoints_registered": registered,
                "webhooks_registered": len(self.webhooks),
                "module_count": len(module_catalog),
                "timestamp": time.time(),
            }
            capped_append(self._provision_log, result)
            return result

    def register_endpoint(self, path: str, method: EndpointMethod,
                          handler_name: str, **kwargs) -> EndpointDefinition:
        """Manually register a single endpoint."""
        ep = EndpointDefinition(
            path=path, method=method, handler_name=handler_name,
            auth_policy=kwargs.get("auth_policy", self.default_auth),
            rate_limit=kwargs.get("rate_limit", self.default_rate_limit),
            description=kwargs.get("description", ""),
            tags=kwargs.get("tags", []),
        )
        ep.status = EndpointStatus.ACTIVE
        with self._lock:
            self.endpoints[ep.id] = ep
        return ep

    def register_webhook(self, event_type: str,
                         callback_url: str) -> WebhookRegistration:
        """Register a webhook for an event type."""
        wh = WebhookRegistration(event_type=event_type,
                                 callback_url=callback_url)
        with self._lock:
            self.webhooks[wh.id] = wh
        return wh

    def decommission_endpoint(self, endpoint_id: str) -> bool:
        """Deprecate and remove an endpoint."""
        with self._lock:
            if endpoint_id in self.endpoints:
                self.endpoints[endpoint_id].status = EndpointStatus.DEPRECATED
                return True
        return False

    def run_health_checks(self) -> List[Dict[str, Any]]:
        """Run health checks on all active endpoints."""
        results = []
        for ep in list(self.endpoints.values()):
            if ep.status != EndpointStatus.DEPRECATED:
                results.append(self.health_monitor.check_endpoint(ep))
        return results

    def generate_openapi_spec(self) -> Dict[str, Any]:
        """Generate OpenAPI 3.0 specification for all endpoints."""
        with self._lock:
            active = [ep for ep in self.endpoints.values()
                      if ep.status != EndpointStatus.DEPRECATED]
            webhooks = [wh for wh in self.webhooks.values() if wh.active]
        return self.spec_generator.generate(active, webhooks)

    def list_endpoints(self) -> List[Dict[str, Any]]:
        """List all registered endpoints."""
        with self._lock:
            return [ep.to_dict() for ep in self.endpoints.values()]

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks."""
        with self._lock:
            return [wh.to_dict() for wh in self.webhooks.values()]

    def status(self) -> Dict[str, Any]:
        """Overall provisioner status."""
        with self._lock:
            active = sum(1 for ep in self.endpoints.values()
                         if ep.status == EndpointStatus.ACTIVE)
            deprecated = sum(1 for ep in self.endpoints.values()
                             if ep.status == EndpointStatus.DEPRECATED)
            return {
                "provisioned": self._provisioned,
                "total_endpoints": len(self.endpoints),
                "active_endpoints": active,
                "deprecated_endpoints": deprecated,
                "total_webhooks": len(self.webhooks),
                "active_webhooks": sum(1 for w in self.webhooks.values()
                                       if w.active),
                "healing_actions": len(
                    self.health_monitor.get_healing_history()),
                "provision_count": len(self._provision_log),
            }

    # -- Internal --

    def _create_system_endpoints(self) -> List[EndpointDefinition]:
        """Create built-in system management endpoints."""
        system_eps = [
            EndpointDefinition(
                path="/system/status", method=EndpointMethod.GET,
                handler_name="system_status",
                description="Overall system health and status",
                auth_policy=AuthPolicy.BEARER_TOKEN,
                tags=["system"],
            ),
            EndpointDefinition(
                path="/system/modules", method=EndpointMethod.GET,
                handler_name="list_modules",
                description="List all registered modules",
                auth_policy=AuthPolicy.BEARER_TOKEN,
                tags=["system"],
            ),
            EndpointDefinition(
                path="/system/provision", method=EndpointMethod.POST,
                handler_name="trigger_provision",
                description="Trigger re-provisioning of API endpoints",
                auth_policy=AuthPolicy.OAUTH2,
                tags=["system", "admin"],
            ),
            EndpointDefinition(
                path="/system/openapi", method=EndpointMethod.GET,
                handler_name="get_openapi_spec",
                description="Get OpenAPI specification",
                auth_policy=AuthPolicy.NONE,
                tags=["system", "docs"],
            ),
            EndpointDefinition(
                path="/system/webhooks", method=EndpointMethod.GET,
                handler_name="list_webhooks",
                description="List all registered webhooks",
                auth_policy=AuthPolicy.BEARER_TOKEN,
                tags=["system"],
            ),
            EndpointDefinition(
                path="/system/health", method=EndpointMethod.GET,
                handler_name="health_check",
                description="System health check endpoint",
                auth_policy=AuthPolicy.NONE,
                tags=["system", "health"],
            ),
        ]
        for ep in system_eps:
            ep.status = EndpointStatus.ACTIVE
        return system_eps
