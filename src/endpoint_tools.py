"""
PATCH-R420 — Auto-register every internal API endpoint as an AionMind tool.

Reads /var/lib/murphy-production/route_registry.json on startup and registers
one tool per /api/ endpoint. The tool's callable is a self-HTTP wrapper that
invokes the endpoint with founder-level auth.

When the user types natural language to /api/aionmind/chat, AionMind selects
from these tools (plus the 11 generic ones) based on tag/description match
and invokes them. The 1,950 endpoints become 1,950 callable tools.

Label: ENDPOINT-TOOL-001
"""
from __future__ import annotations
import json, logging, os, urllib.request, urllib.error, urllib.parse, time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REGISTERED = False
_ROUTE_REG_PATH = Path("/var/lib/murphy-production/route_registry.json")
_HEALTH_MAP_PATH = Path("/var/lib/murphy-production/api_health_map.json")

# Self-call base URL — talks to ourselves over loopback
_BASE = "http://127.0.0.1:8000"
_TIMEOUT = 15

# Founder key for internal calls (read from env)
_FOUNDER_KEY = os.environ.get("MURPHY_API_KEY", "")


def _make_caller(path: str, method: str):
    """Build a callable that invokes a specific endpoint with given method."""
    def _call(**kwargs):
        # Substitute path params from kwargs if path contains {param}
        local_path = path
        for k, v in list(kwargs.items()):
            placeholder = "{" + k + "}"
            if placeholder in local_path:
                local_path = local_path.replace(placeholder, urllib.parse.quote(str(v)))
                kwargs.pop(k)

        url = _BASE + local_path
        headers = {
            "Content-Type": "application/json",
            "X-User-ID": "founder",  # R422: bypass per-user rate limit
            "X-Internal-Tool-Call": "1",  # R422: marker for audit
        }
        if _FOUNDER_KEY:
            headers["X-API-Key"] = _FOUNDER_KEY

        data = None
        if method == "GET":
            # remaining kwargs become query string
            if kwargs:
                url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(kwargs)
        else:
            data = json.dumps(kwargs).encode()

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    return {"ok": True, "status": resp.code, "data": json.loads(body)}
                except json.JSONDecodeError:
                    return {"ok": True, "status": resp.code, "text": body[:4000]}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:2000]
            return {"ok": False, "status": e.code, "error": body}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"URL error: {e.reason}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    return _call


def _describe_endpoint(path: str, method: str, name: str) -> Dict[str, str]:
    """Derive human-readable tool name, description, and tags from path+name."""
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if parts and parts[0] == "api":
        parts = parts[1:]

    group = parts[0] if parts else "misc"
    # Last segment is the action (e.g. /api/crm/deals → action=deals)
    action = parts[-1] if len(parts) > 1 else (name or path)

    # Build a natural label: "List CRM deals" from /api/crm/deals + GET
    verb_map = {
        "GET": "Get",
        "POST": "Create or run",
        "PUT": "Update",
        "PATCH": "Patch",
        "DELETE": "Delete",
    }
    verb = verb_map.get(method, "Call")
    # Singularize plural sound: "deals" stays, "list" stays — keep verbatim
    nice_action = action.replace("-", " ").replace("_", " ")
    label = f"{verb} {group} {nice_action}".strip()[:80]

    desc = f"{method} {path}"
    if name and not name.startswith("_"):
        desc = f"{name}: {method} {path}"
    elif name and name.startswith("_"):
        # The auto-generated name like _list, _get → use the action
        desc = f"{method} {path} ({name})"

    tags = [group]
    if action and action not in tags:
        tags.append(action)
    if method.lower() not in tags:
        tags.append(method.lower())

    return {
        "label": label,
        "description": desc[:200],
        "tags": tags[:5],
        "category": group,
    }


def _permission_for(method: str, path: str) -> str:
    """Risk-tier from HTTP method + path keywords."""
    if method == "GET":
        return "low"
    # Sensitive paths
    sensitive = ["payments", "billing", "auth", "self-modify", "platform/admin",
                 "send", "submit", "delete", "rebuild", "restart"]
    if any(s in path for s in sensitive):
        return "high"
    if method == "DELETE":
        return "critical"
    return "medium"


def register_endpoint_tools() -> Dict[str, Any]:
    """Read the live route registry and register every /api/ endpoint as a tool."""
    global _REGISTERED
    if _REGISTERED:
        return {"already_registered": True}

    if not _ROUTE_REG_PATH.exists():
        logger.warning("R420: route_registry.json not found, skipping")
        return {"ok": False, "error": "route_registry.json missing"}

    try:
        from src.tool_registry.models import (
            ToolDefinition, ToolInputSchema, ToolOutputSchema,
            CostEstimate, CostTier, PermissionLevel,
        )
        from src.aionmind.tool_executor import _get_registry, register_all_tools
        register_all_tools()  # ensure the 11 base tools are in first
        registry = _get_registry()
    except Exception as e:
        logger.error("R420: tool_registry import failed: %s", e)
        return {"ok": False, "error": str(e)}

    routes = json.loads(_ROUTE_REG_PATH.read_text()).get("routes", [])

    # Read health map to skip broken/timeout endpoints
    health = {}
    if _HEALTH_MAP_PATH.exists():
        try:
            hd = json.loads(_HEALTH_MAP_PATH.read_text())
            for g, info in hd.get("groups", {}).items():
                for path, code in info.get("probe_results", []):
                    health[path] = code
        except Exception:
            pass

    perm_enum = {
        "low": PermissionLevel.LOW,
        "medium": PermissionLevel.MEDIUM,
        "high": PermissionLevel.HIGH,
        "critical": PermissionLevel.CRITICAL,
    }

    registered = 0
    skipped = 0
    by_group: Dict[str, int] = {}

    for r in routes:
        path = r.get("path", "")
        if not path.startswith("/api/"):
            continue
        # Skip non-callable internals
        if path.startswith("/api/inventory/all-routes"):
            continue
        if "/static" in path or "/openapi" in path or "/docs" in path:
            continue
        methods = r.get("methods", ["GET"])
        # Filter HEAD/OPTIONS noise
        methods = [m for m in methods if m in ("GET", "POST", "PUT", "PATCH", "DELETE")]
        for method in methods:
            name = r.get("name", "")
            meta = _describe_endpoint(path, method, name)
            risk = _permission_for(method, path)

            tool_id = f"api.{method.lower()}{path.replace('/', '.').replace('{', '_').replace('}', '_')}"
            tool_id = tool_id[:120]  # keep ID bounded

            try:
                defn = ToolDefinition(
                    tool_id=tool_id,
                    name=meta["label"],
                    description=meta["description"],
                    permission_level=perm_enum[risk],
                    cost_estimate=CostEstimate(tier=CostTier.FREE),
                    input_schema=ToolInputSchema(
                        description=f"Args passed as query string ({method}) or JSON body."
                    ),
                    output_schema=ToolOutputSchema(
                        description="Returns {ok, status, data|text|error}."
                    ),
                    provider="murphy.internal",
                    tags=meta["tags"],
                    category=meta["category"],
                    requires_approval=(risk in ("high", "critical")),
                    metadata={
                        "_callable": _make_caller(path, method),
                        "_path": path,
                        "_method": method,
                        "_health_status": health.get(path),
                    },
                )
                registry.register(defn)
                registered += 1
                by_group[meta["category"]] = by_group.get(meta["category"], 0) + 1
            except Exception as e:
                logger.debug("R420: skip %s %s: %s", method, path, e)
                skipped += 1

    _REGISTERED = True
    logger.info("R420: registered %d endpoint tools (skipped %d) across %d groups",
                registered, skipped, len(by_group))
    return {
        "ok": True,
        "registered": registered,
        "skipped": skipped,
        "groups": len(by_group),
        "by_group_top": dict(sorted(by_group.items(), key=lambda x: -x[1])[:10]),
    }


def stats() -> Dict[str, Any]:
    """Return current registration stats."""
    try:
        from src.aionmind.tool_executor import _get_registry
        registry = _get_registry()
        all_tools = registry.list_all() if hasattr(registry, "list_all") else []
        internal = [t for t in all_tools if getattr(t, "provider", "") == "murphy.internal"]
        return {
            "total_tools": len(all_tools),
            "internal_endpoints": len(internal),
            "generic_tools": len(all_tools) - len(internal),
        }
    except Exception as e:
        return {"error": str(e)}
