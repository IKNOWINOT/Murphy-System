# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post · License: BSL 1.1
"""
murphy_connector_agent.py — PATCH-065c
Murphy Autonomous API Connector Agent

Enables Murphy to discover, understand, and connect to any external API
without human configuration:

  1. DISCOVER — Given a URL or name, fetch the OpenAPI/Swagger spec
  2. PARSE    — Extract endpoints, auth requirements, and schemas
  3. GENERATE — Synthesize a typed connector module (Python)
  4. REGISTER — Wire into UniversalIntegrationAdapter + persist
  5. HEAL     — Monitor health; auto-regenerate on failure

The agent can also do capability-based discovery:
  "I need to send SMS" → searches known connector catalog → recommends Twilio

Design: MCA-001
Thread-safe: Yes
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONNECTOR_DIR      = "/var/lib/murphy-production/connectors"
CONNECTOR_CATALOG  = "/var/lib/murphy-production/connector_catalog.json"
SPEC_FETCH_TIMEOUT = 15   # seconds
MAX_ENDPOINTS      = 50   # cap per connector
HEALTH_CHECK_INTERVAL = 300  # 5 minutes

# Known spec locations for popular APIs (Murphy's internal knowledge)
KNOWN_SPECS: Dict[str, str] = {
    "stripe":     "https://raw.githubusercontent.com/stripe/openapi/master/openapi/spec3.json",
    "github":     "https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json",
    "slack":      "https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json",
    "twilio":     "https://raw.githubusercontent.com/twilio/twilio-oai/main/spec/json/twilio_api_v2010.json",
    "sendgrid":   "https://raw.githubusercontent.com/sendgrid/sendgrid-oai/main/oai.json",
    "openai":     "https://raw.githubusercontent.com/openai/openai-openapi/master/openapi.yaml",
    "notion":     "https://developers.notion.com/openapi.yaml",
    "airtable":   "https://api.airtable.com/openapi.json",
    "hubspot":    "https://api.hubspot.com/api-catalog-public/v1/apis",
    "shopify":    "https://shopify.dev/docs/api/admin-rest/2024-01/openapi.json",
    "plaid":      "https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml",
    "deepinfra":  "https://api.deepinfra.com/openapi.json",
    "resend":     "https://raw.githubusercontent.com/resendlabs/resend-openapi/main/resend.yaml",
    "linear":     "https://api.linear.app/graphql",  # GraphQL — special handling
    "discord":    "https://discord.com/developers/docs/reference",
    "anthropic":  "https://anthropic-openapi-mock.vercel.app/openapi.json",
    "together":   "https://docs.together.ai/openapi.json",
}

# Capability → connector suggestions
CAPABILITY_MAP: Dict[str, List[str]] = {
    "sms":           ["twilio", "vonage", "sinch"],
    "email":         ["sendgrid", "resend", "mailgun", "postmark"],
    "payment":       ["stripe", "braintree", "square", "paypal"],
    "storage":       ["s3", "cloudflare_r2", "backblaze"],
    "calendar":      ["googlecalendar", "outlook"],
    "crm":           ["hubspot", "salesforce", "pipedrive"],
    "llm":           ["openai", "anthropic", "deepinfra", "together"],
    "code":          ["github", "gitlab"],
    "messaging":     ["slack", "discord", "teams"],
    "database":      ["supabase", "planetscale", "neon"],
    "analytics":     ["mixpanel", "amplitude", "segment"],
    "ecommerce":     ["shopify", "woocommerce"],
    "maps":          ["googlemaps", "mapbox"],
    "auth":          ["auth0", "clerk", "stytch"],
}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConnectorStatus(str, Enum):
    PENDING    = "pending"
    ACTIVE     = "active"
    FAILED     = "failed"
    HEALING    = "healing"
    DEPRECATED = "deprecated"


class AuthType(str, Enum):
    NONE        = "none"
    API_KEY     = "api_key"
    BEARER      = "bearer"
    BASIC       = "basic"
    OAUTH2      = "oauth2"
    CUSTOM      = "custom"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EndpointDef:
    path:        str
    method:      str
    operation_id: str
    summary:     str
    parameters:  List[Dict] = field(default_factory=list)
    request_body: Optional[Dict] = None
    response_schema: Optional[Dict] = None
    tags:        List[str] = field(default_factory=list)


@dataclass
class ConnectorSpec:
    connector_id: str
    name:         str
    base_url:     str
    spec_url:     Optional[str]
    auth_type:    AuthType
    auth_config:  Dict[str, Any]       # {"header": "Authorization", "prefix": "Bearer"}
    endpoints:    List[EndpointDef]
    version:      str = "1.0.0"
    description:  str = ""
    created_at:   float = field(default_factory=time.time)
    status:       ConnectorStatus = ConnectorStatus.PENDING
    last_health:  float = 0.0
    health_ok:    bool = False
    error_count:  int = 0
    metadata:     Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name":         self.name,
            "base_url":     self.base_url,
            "spec_url":     self.spec_url,
            "auth_type":    self.auth_type.value,
            "version":      self.version,
            "description":  self.description,
            "endpoints":    len(self.endpoints),
            "status":       self.status.value,
            "last_health":  self.last_health,
            "health_ok":    self.health_ok,
            "error_count":  self.error_count,
        }


# ---------------------------------------------------------------------------
# Spec Fetcher
# ---------------------------------------------------------------------------

class SpecFetcher:
    """Fetches and normalizes OpenAPI specs from URLs."""

    @staticmethod
    def fetch(url: str) -> Tuple[bool, Optional[Dict], str]:
        """Returns (ok, spec_dict, error_msg)."""
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MurphyConnectorAgent/1.0 (PATCH-065c)"}
            )
            with urllib.request.urlopen(req, timeout=SPEC_FETCH_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return False, None, f"HTTP {e.code}: {e.reason}"
        except Exception as e:
            return False, None, str(e)

        # Try JSON first, then YAML
        try:
            return True, json.loads(raw), "ok"
        except json.JSONDecodeError:
            pass
        try:
            import yaml
            return True, yaml.safe_load(raw), "ok"
        except Exception:
            pass
        return False, None, "Could not parse spec as JSON or YAML"

    @staticmethod
    def normalize(spec: Dict) -> Dict:
        """Convert Swagger 2.0 → OpenAPI 3.x shell if needed."""
        if spec.get("swagger", "").startswith("2."):
            # Minimal conversion
            host    = spec.get("host", "api.example.com")
            schemes = spec.get("schemes", ["https"])
            base    = spec.get("basePath", "/")
            spec["openapi"]  = "3.0.0"
            spec["servers"]  = [{"url": f"{schemes[0]}://{host}{base}"}]
            spec.setdefault("components", {})
        return spec


# ---------------------------------------------------------------------------
# Spec Parser
# ---------------------------------------------------------------------------

class SpecParser:
    """Extracts typed EndpointDefs from an OpenAPI 3.x spec."""

    @staticmethod
    def parse_auth(spec: Dict) -> Tuple[AuthType, Dict]:
        security_schemes = (
            spec.get("components", {}).get("securitySchemes", {})
            or spec.get("securityDefinitions", {})
        )
        if not security_schemes:
            return AuthType.NONE, {}
        for name, scheme in security_schemes.items():
            stype = scheme.get("type", "").lower()
            if stype == "oauth2":
                return AuthType.OAUTH2, scheme
            if stype == "http":
                sc = scheme.get("scheme", "").lower()
                if sc == "bearer":
                    return AuthType.BEARER, {"header": "Authorization", "prefix": "Bearer"}
                if sc == "basic":
                    return AuthType.BASIC, {}
            if stype == "apikey":
                return AuthType.API_KEY, {
                    "header": scheme.get("name", "X-API-Key"),
                    "in":     scheme.get("in", "header"),
                }
        return AuthType.CUSTOM, {}

    @staticmethod
    def parse_endpoints(spec: Dict) -> List[EndpointDef]:
        endpoints: List[EndpointDef] = []
        paths = spec.get("paths", {})

        for path, methods in list(paths.items())[:MAX_ENDPOINTS]:
            for method, op in methods.items():
                if method.upper() not in ("GET","POST","PUT","PATCH","DELETE","HEAD"):
                    continue
                if not isinstance(op, dict):
                    continue
                op_id = op.get("operationId") or f"{method.upper()}_{path.replace('/','_')}"
                ep = EndpointDef(
                    path=path,
                    method=method.upper(),
                    operation_id=op_id,
                    summary=op.get("summary", ""),
                    parameters=op.get("parameters", []),
                    request_body=op.get("requestBody"),
                    tags=op.get("tags", []),
                )
                endpoints.append(ep)

        return endpoints

    @classmethod
    def parse(cls, spec: Dict, spec_url: str = "") -> ConnectorSpec:
        spec  = SpecFetcher.normalize(spec)
        info  = spec.get("info", {})
        servers = spec.get("servers", [{}])
        base_url = servers[0].get("url", "") if servers else ""
        if not base_url.startswith("http"):
            base_url = "https://" + base_url.lstrip("/")

        auth_type, auth_config = cls.parse_auth(spec)
        endpoints = cls.parse_endpoints(spec)

        return ConnectorSpec(
            connector_id = str(uuid.uuid4()),
            name         = info.get("title", "Unknown API"),
            base_url     = base_url,
            spec_url     = spec_url,
            auth_type    = auth_type,
            auth_config  = auth_config,
            endpoints    = endpoints,
            version      = info.get("version", "1.0.0"),
            description  = info.get("description", ""),
        )


# ---------------------------------------------------------------------------
# Code Generator
# ---------------------------------------------------------------------------

class ConnectorCodeGenerator:
    """Generates a typed Python connector module from a ConnectorSpec."""

    @staticmethod
    def generate(spec: ConnectorSpec) -> str:
        class_name = re.sub(r"[^A-Za-z0-9]", "", spec.name.title().replace(" ", "")) + "Connector"

        # Generate method stubs for each endpoint
        methods = []
        for ep in spec.endpoints[:30]:   # cap at 30 methods
            mname = re.sub(r"[^A-Za-z0-9_]", "_", ep.operation_id).lower()
            params = [p.get("name", "p") for p in (ep.parameters or []) if p.get("in") == "query"]
            sig_params = ", ".join(["self"] + [f"{p}=None" for p in params[:5]])
            qs   = ""
            if params:
                qs = f"""
        qp = {{k: v for k, v in {{{', '.join(f'"{p}": {p}' for p in params[:5])}}}.items() if v is not None}}
        if qp:
            url += "?" + "&".join(f"{{k}}={{v}}" for k, v in qp.items())"""
            body_param = "data=None, " if ep.request_body else ""
            method_code = f'''
    def {mname}({sig_params.replace("self, ", "self, " + body_param if ep.request_body else "")}) -> Dict[str, Any]:
        """{ep.summary or ep.operation_id}"""
        url = self.base_url + "{ep.path}"{qs}
        return self._request("{ep.method}", url{", json=data" if ep.request_body else ""})
'''
            methods.append(method_code)

        auth_setup = {
            AuthType.API_KEY: f"""
        header_name = self._auth_config.get("header", "X-API-Key")
        if self._api_key:
            self._session_headers[header_name] = self._api_key""",
            AuthType.BEARER: """
        if self._api_key:
            self._session_headers["Authorization"] = f"Bearer {self._api_key}" """,
            AuthType.BASIC: """
        if self._api_key and ":" in self._api_key:
            import base64
            self._session_headers["Authorization"] = "Basic " + base64.b64encode(self._api_key.encode()).decode()""",
        }.get(spec.auth_type, "")

        code = f'''# Auto-generated by MurphyConnectorAgent (PATCH-065c)
# Connector: {spec.name} | ID: {spec.connector_id}
# Generated: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


class {class_name}:
    """{spec.name} connector — {spec.description[:120] if spec.description else "Auto-generated"}"""

    CONNECTOR_ID = "{spec.connector_id}"
    NAME         = "{spec.name}"
    BASE_URL     = "{spec.base_url}"
    AUTH_TYPE    = "{spec.auth_type.value}"
    VERSION      = "{spec.version}"

    def __init__(self, api_key: str = "", **kwargs) -> None:
        self.base_url         = self.BASE_URL.rstrip("/")
        self._api_key         = api_key or os.environ.get("{re.sub(r"[^A-Z0-9]", "_", spec.name.upper())}_API_KEY", "")
        self._auth_config     = {json.dumps(spec.auth_config)}
        self._session_headers = {{"Content-Type": "application/json", "User-Agent": "Murphy/1.0"}}{auth_setup}
        self._timeout         = int(kwargs.get("timeout", 30))
        self._last_ok         = False

    def _request(self, method: str, url: str, json: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        body = __import__("json").dumps(json).encode() if json else None
        req  = urllib.request.Request(url, data=body, headers=self._session_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                self._last_ok = True
                return __import__("json").loads(resp.read())
        except urllib.error.HTTPError as e:
            self._last_ok = False
            return {{"error": str(e), "status": e.code}}
        except Exception as e:
            self._last_ok = False
            return {{"error": str(e)}}

    def health_check(self) -> bool:
        """Ping base URL to verify connectivity."""
        try:
            req = urllib.request.Request(
                self.base_url, headers={{"User-Agent": "Murphy/1.0"}}, method="HEAD"
            )
            urllib.request.urlopen(req, timeout=5)
            self._last_ok = True
            return True
        except Exception:
            self._last_ok = False
            return False

    def status(self) -> Dict[str, Any]:
        return {{"connector_id": self.CONNECTOR_ID, "name": self.NAME,
                 "base_url": self.BASE_URL, "last_ok": self._last_ok}}
{"".join(methods)}
'''
        return code


# ---------------------------------------------------------------------------
# Connector Registry (on-disk + in-memory)
# ---------------------------------------------------------------------------

class ConnectorRegistry:
    """Persists and serves all discovered connectors."""

    def __init__(self) -> None:
        self._connectors: Dict[str, ConnectorSpec] = {}
        self._modules:    Dict[str, Any] = {}  # connector_id → loaded module
        self._lock = threading.RLock()
        os.makedirs(CONNECTOR_DIR, exist_ok=True)
        self._load_catalog()

    def register(self, spec: ConnectorSpec, code: str) -> bool:
        try:
            # Write connector module
            fname = re.sub(r"[^a-z0-9_]", "_", spec.name.lower()) + "_connector.py"
            fpath = os.path.join(CONNECTOR_DIR, fname)
            with open(fpath, "w") as f:
                f.write(code)

            # Load the module
            mod = self._load_module(spec.connector_id, fpath)
            with self._lock:
                spec.status = ConnectorStatus.ACTIVE
                self._connectors[spec.connector_id] = spec
                if mod:
                    self._modules[spec.connector_id] = mod
            self._save_catalog()
            logger.info("ConnectorRegistry: registered %s (%s endpoints)", spec.name, len(spec.endpoints))
            return True
        except Exception as exc:
            logger.error("ConnectorRegistry.register failed: %s", exc)
            return False

    def get(self, connector_id: str) -> Optional[ConnectorSpec]:
        with self._lock:
            return self._connectors.get(connector_id)

    def list_all(self) -> List[ConnectorSpec]:
        with self._lock:
            return list(self._connectors.values())

    def find_by_name(self, name: str) -> Optional[ConnectorSpec]:
        name_lower = name.lower()
        with self._lock:
            for spec in self._connectors.values():
                if spec.name.lower() == name_lower or name_lower in spec.name.lower():
                    return spec
        return None

    def call(self, connector_id: str, method_name: str, **kwargs) -> Dict[str, Any]:
        """Instantiate connector and call a method."""
        with self._lock:
            mod  = self._modules.get(connector_id)
            spec = self._connectors.get(connector_id)
        if not mod or not spec:
            return {"error": "connector_not_found"}
        try:
            classes = [c for c in dir(mod) if c.endswith("Connector") and c != "Connector"]
            if not classes:
                return {"error": "no_connector_class_found"}
            cls  = getattr(mod, classes[0])
            inst = cls()
            fn   = getattr(inst, method_name, None)
            if not fn:
                return {"error": f"method_{method_name}_not_found"}
            result = fn(**kwargs)
            self._connectors[connector_id].health_ok = True
            self._connectors[connector_id].last_health = time.time()
            return result
        except Exception as exc:
            self._connectors[connector_id].error_count += 1
            return {"error": str(exc)}

    def _load_module(self, connector_id: str, fpath: str) -> Optional[Any]:
        try:
            spec = importlib.util.spec_from_file_location(f"mc_{connector_id}", fpath)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception as exc:
            logger.warning("Failed to load connector module %s: %s", fpath, exc)
            return None

    def _save_catalog(self) -> None:
        try:
            data = {cid: spec.to_dict() for cid, spec in self._connectors.items()}
            tmp  = CONNECTOR_CATALOG + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, CONNECTOR_CATALOG)
        except Exception as exc:
            logger.error("ConnectorRegistry._save_catalog: %s", exc)

    def _load_catalog(self) -> None:
        if not os.path.exists(CONNECTOR_CATALOG):
            return
        try:
            with open(CONNECTOR_CATALOG) as f:
                data = json.load(f)
            for cid, d in data.items():
                # Re-load module if file exists
                fname = re.sub(r"[^a-z0-9_]", "_", d.get("name","").lower()) + "_connector.py"
                fpath = os.path.join(CONNECTOR_DIR, fname)
                spec  = ConnectorSpec(
                    connector_id=cid, name=d["name"], base_url=d["base_url"],
                    spec_url=d.get("spec_url"), auth_type=AuthType(d.get("auth_type","none")),
                    auth_config={}, endpoints=[], version=d.get("version","1.0.0"),
                    description=d.get("description",""),
                    status=ConnectorStatus(d.get("status","active")),
                )
                self._connectors[cid] = spec
                if os.path.exists(fpath):
                    mod = self._load_module(cid, fpath)
                    if mod:
                        self._modules[cid] = mod
            logger.info("ConnectorRegistry loaded %d connectors from catalog", len(self._connectors))
        except Exception as exc:
            logger.error("ConnectorRegistry._load_catalog: %s", exc)


# ---------------------------------------------------------------------------
# Self-Healing Monitor
# ---------------------------------------------------------------------------

class ConnectorHealthMonitor(threading.Thread):
    """Background thread that pings active connectors and triggers self-heal."""

    def __init__(self, registry: ConnectorRegistry, agent: "MurphyConnectorAgent") -> None:
        super().__init__(daemon=True, name="ConnectorHealthMonitor")
        self._registry = registry
        self._agent    = agent
        self._stop     = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(HEALTH_CHECK_INTERVAL):
            for spec in self._registry.list_all():
                if spec.status != ConnectorStatus.ACTIVE:
                    continue
                result = self._registry.call(spec.connector_id, "health_check")
                ok     = result.get("error") is None
                spec.health_ok   = ok
                spec.last_health = time.time()
                if not ok:
                    spec.error_count += 1
                    if spec.error_count >= 3 and spec.spec_url:
                        logger.warning("Connector %s failing — triggering self-heal", spec.name)
                        spec.status = ConnectorStatus.HEALING
                        self._agent.heal(spec.connector_id)

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------
# Murphy Connector Agent (main façade)
# ---------------------------------------------------------------------------

class MurphyConnectorAgent:
    """
    The autonomous API connector agent. Main entry point for all connector ops.
    Singleton — call MurphyConnectorAgent() anywhere.
    """

    _instance: Optional["MurphyConnectorAgent"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MurphyConnectorAgent":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self.registry = ConnectorRegistry()
        self._monitor = ConnectorHealthMonitor(self.registry, self)
        self._monitor.start()
        logger.info("MurphyConnectorAgent initialised (MCA-001)")

    # ── Primary API: connect from spec URL ─────────────────────────────────

    def connect_from_url(self, spec_url: str, name_override: str = "") -> Tuple[bool, Optional[ConnectorSpec], str]:
        """
        Full pipeline: fetch spec → parse → generate code → register.
        Returns (ok, ConnectorSpec, message).
        """
        logger.info("ConnectorAgent: fetching spec from %s", spec_url)
        ok, spec_dict, err = SpecFetcher.fetch(spec_url)
        if not ok:
            return False, None, f"fetch_failed: {err}"
        return self._process_spec(spec_dict, spec_url, name_override)

    def connect_from_spec(self, spec_dict: Dict, name_override: str = "") -> Tuple[bool, Optional[ConnectorSpec], str]:
        """Connect from a raw spec dict (e.g. pasted by user)."""
        return self._process_spec(spec_dict, None, name_override)

    def connect_by_name(self, name: str) -> Tuple[bool, Optional[ConnectorSpec], str]:
        """
        Connect to a known API by name (uses KNOWN_SPECS lookup).
        e.g. connect_by_name("stripe") → fetches Stripe OpenAPI spec.
        """
        # Check if already registered
        existing = self.registry.find_by_name(name)
        if existing and existing.status == ConnectorStatus.ACTIVE:
            return True, existing, "already_registered"

        url = KNOWN_SPECS.get(name.lower())
        if not url:
            return False, None, f"unknown_api: {name}. Try connect_from_url() with the spec URL."
        return self.connect_from_url(url, name_override=name)

    # ── Capability-based discovery ──────────────────────────────────────────

    def suggest_for_capability(self, capability: str) -> List[str]:
        """e.g. 'send SMS' → ['twilio', 'vonage', 'sinch']"""
        cap_lower = capability.lower()
        for key, suggestions in CAPABILITY_MAP.items():
            if key in cap_lower or cap_lower in key:
                return suggestions
        return []

    # ── Call a connected API ────────────────────────────────────────────────

    def call(self, connector_id_or_name: str, method: str, **kwargs) -> Dict[str, Any]:
        """
        Call a registered connector method.
        e.g. call("stripe", "listcharges", limit=10)
        """
        spec = (
            self.registry.get(connector_id_or_name)
            or self.registry.find_by_name(connector_id_or_name)
        )
        if not spec:
            return {"error": "connector_not_found", "name": connector_id_or_name}
        return self.registry.call(spec.connector_id, method, **kwargs)

    # ── Self-healing ────────────────────────────────────────────────────────

    def heal(self, connector_id: str) -> bool:
        """Re-fetch spec and regenerate connector module."""
        spec = self.registry.get(connector_id)
        if not spec or not spec.spec_url:
            return False
        logger.info("ConnectorAgent: healing %s from %s", spec.name, spec.spec_url)
        ok, new_spec, msg = self.connect_from_url(spec.spec_url, spec.name)
        if ok:
            spec.status      = ConnectorStatus.ACTIVE
            spec.error_count = 0
            logger.info("ConnectorAgent: healed %s", spec.name)
        else:
            spec.status = ConnectorStatus.FAILED
            logger.error("ConnectorAgent: heal failed for %s: %s", spec.name, msg)
        return ok

    # ── Status ──────────────────────────────────────────────────────────────

    def list_connectors(self) -> List[Dict]:
        return [s.to_dict() for s in self.registry.list_all()]

    def stats(self) -> Dict[str, Any]:
        all_specs = self.registry.list_all()
        return {
            "total":      len(all_specs),
            "active":     sum(1 for s in all_specs if s.status == ConnectorStatus.ACTIVE),
            "failed":     sum(1 for s in all_specs if s.status == ConnectorStatus.FAILED),
            "healing":    sum(1 for s in all_specs if s.status == ConnectorStatus.HEALING),
            "known_apis": len(KNOWN_SPECS),
        }

    # ── Internal ────────────────────────────────────────────────────────────

    def _process_spec(
        self, spec_dict: Dict, spec_url: Optional[str], name_override: str
    ) -> Tuple[bool, Optional[ConnectorSpec], str]:
        try:
            conn_spec = SpecParser.parse(spec_dict, spec_url or "")
            if name_override:
                conn_spec.name = name_override
            code = ConnectorCodeGenerator.generate(conn_spec)
            ok   = self.registry.register(conn_spec, code)
            if not ok:
                return False, None, "registration_failed"
            return True, conn_spec, "ok"
        except Exception as exc:
            logger.error("ConnectorAgent._process_spec: %s\n%s", exc, traceback.format_exc())
            return False, None, str(exc)


# ---------------------------------------------------------------------------
# Route factory (called from app.py)
# ---------------------------------------------------------------------------

def create_connector_agent_routes(app) -> None:
    """Register /api/connectors/* routes on the FastAPI app."""
    try:
        from fastapi import Request
    except ImportError:
        from starlette.requests import Request
    from starlette.responses import JSONResponse

    agent = MurphyConnectorAgent()

    def _ok(data: Any) -> JSONResponse:
        return JSONResponse({"success": True, "data": data})

    def _err(code: str, msg: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"success": False, "error": code, "message": msg}, status_code=status)

    @app.get("/api/connectors")
    async def list_connectors(request: Request):
        return _ok(agent.list_connectors())

    @app.get("/api/connectors/stats")
    async def connector_stats():
        return _ok(agent.stats())

    @app.get("/api/connectors/suggest")
    async def suggest_connectors(request: Request):
        capability = request.query_params.get("capability", "")
        if not capability:
            return _err("missing_param", "capability query param required")
        suggestions = agent.suggest_for_capability(capability)
        return _ok({"capability": capability, "suggestions": suggestions})

    @app.get("/api/connectors/known")
    async def known_apis():
        return _ok({"apis": list(KNOWN_SPECS.keys()), "count": len(KNOWN_SPECS)})

    @app.post("/api/connectors/connect/url")
    async def connect_from_url(request: Request):
        body = await request.json()
        url  = body.get("url", "")
        name = body.get("name", "")
        if not url:
            return _err("missing_param", "url is required")
        ok, spec, msg = agent.connect_from_url(url, name)
        if not ok:
            return _err("connect_failed", msg, 422)
        return JSONResponse({"success": True, "connector": spec.to_dict()}, status_code=201)

    @app.post("/api/connectors/connect/name")
    async def connect_by_name(request: Request):
        body = await request.json()
        name = body.get("name", "")
        if not name:
            return _err("missing_param", "name is required")
        ok, spec, msg = agent.connect_by_name(name)
        if not ok:
            return _err("connect_failed", msg, 422)
        return JSONResponse({"success": True, "connector": spec.to_dict()}, status_code=201)

    @app.post("/api/connectors/connect/spec")
    async def connect_from_spec(request: Request):
        body = await request.json()
        spec_dict = body.get("spec")
        name      = body.get("name", "")
        if not spec_dict:
            return _err("missing_param", "spec (OpenAPI dict) is required")
        ok, spec, msg = agent.connect_from_spec(spec_dict, name)
        if not ok:
            return _err("connect_failed", msg, 422)
        return JSONResponse({"success": True, "connector": spec.to_dict()}, status_code=201)

    @app.post("/api/connectors/{connector_id}/call")
    async def call_connector(request: Request, connector_id: str):
        body   = await request.json()
        method = body.get("method", "")
        params = body.get("params", {})
        if not method:
            return _err("missing_param", "method is required")
        result = agent.call(connector_id, method, **params)
        if "error" in result:
            return _err("call_failed", result["error"], 422)
        return _ok(result)

    @app.post("/api/connectors/{connector_id}/heal")
    async def heal_connector(request: Request, connector_id: str):
        ok = agent.heal(connector_id)
        return _ok({"healed": ok, "connector_id": connector_id})

    @app.get("/api/connectors/{connector_id}")
    async def get_connector(request: Request, connector_id: str):
        spec = agent.registry.get(connector_id)
        if not spec:
            return _err("not_found", "Connector not found", 404)
        return _ok(spec.to_dict())

    logger.info("PATCH-065c: Connector agent routes registered (/api/connectors/*)")
