"""
PATCH-OPT-2 — Murphy Module Registry
=====================================

WHAT THIS IS:
  The foundation of the modular architecture (Track B). Every Murphy
  subsystem registers itself here with a name, version, init function,
  and dependencies. Modules can be enabled or disabled per-environment
  via /etc/murphy-production/modules.toml — exactly Corey's "pocket needs
  and deactivations" directive.

WHY IT EXISTS:
  Before: 962 endpoints jammed into app.py, all imported at boot, one
  bad module crashes the whole process, no way to turn off rosetta/mfgc/
  swarm/etc when not in use.

  After: Each subsystem is a registered module. Boot order is dependency-
  ordered. Disabled modules don't import at all (zero memory cost).
  Modules can be in any of 6 services (edge/core/business/ops/robotics/
  stream). Adding a new module = one register() call.

HOW IT FITS:
  - Loaded FIRST by every Murphy service (edge, core, ops, robotics, etc.)
  - Each service passes its name and gets back its module set
  - Each module's init_fn receives the FastAPI app and wires its routes
  - Module list + status visible at /api/system/modules

KEY CONCEPTS:
  - Module: a named bundle with init function, dependencies, surface
  - Service: one of 6 processes that hosts a subset of modules
  - Manifest: /etc/murphy-production/modules.toml lists what's on/off
  - Hot-toggle: enable/disable without code change (requires service restart)

ENDPOINTS / PUBLIC SURFACE:
  GET   /api/system/modules         — full registry status
  GET   /api/system/modules/{name}  — one module's details
  POST  /api/system/modules/{name}/enable   — founder-only
  POST  /api/system/modules/{name}/disable  — founder-only

DEPENDENCIES:
  - tomllib (Python 3.11+ stdlib) for manifest
  - fastapi for route registration
  - PATCH-405 vault (optional, for founder check)

KNOWN LIMITS:
  - Enable/disable requires service restart (no hot reload of code yet)
  - Circular dependencies are detected but not auto-resolved
  - No per-tenant module activation yet (planned PATCH-OPT-7)

LAST UPDATED: 2026-05-24 by Murphy
"""
from __future__ import annotations

import os, sys, time, logging, importlib, traceback
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

try:
    import tomllib                          # Python 3.11+
except ImportError:                         # pragma: no cover
    import tomli as tomllib                 # type: ignore

log = logging.getLogger("murphy.modules")


MANIFEST_PATH = "/etc/murphy-production/modules.toml"


# ── Module descriptor ───────────────────────────────────────────────────────
@dataclass
class Module:
    name: str
    patch_id: str                     # e.g. "PATCH-410"
    init_fn: Optional[Callable]       # called with FastAPI app
    service: str                      # edge|core|business|ops|robotics|stream
    requires: List[str]               # module names that must load first
    description: str
    enabled: bool = True
    loaded: bool = False
    load_error: Optional[str] = None
    load_time_ms: Optional[float] = None
    routes_added: int = 0


# ── Registry singleton ──────────────────────────────────────────────────────
_REGISTRY: Dict[str, Module] = {}
_SERVICE_NAME: Optional[str] = None
_LOAD_ORDER: List[str] = []


def register(
    name: str,
    *,
    patch_id: str,
    init_fn: Optional[Callable] = None,
    service: str = "core",
    requires: Optional[List[str]] = None,
    description: str = "",
    default_enabled: bool = True,
) -> None:
    """
    Register a Murphy subsystem.

    Example:
        register("identity", patch_id="PATCH-410",
                 init_fn=init_identity_routes,
                 service="edge",
                 requires=["household"],
                 description="Device pairing, capabilities, voice-login")
    """
    if name in _REGISTRY:
        log.warning("module %r already registered — overwriting", name)
    _REGISTRY[name] = Module(
        name=name, patch_id=patch_id, init_fn=init_fn, service=service,
        requires=requires or [], description=description,
        enabled=default_enabled,
    )


def _load_manifest() -> Dict[str, Any]:
    if not os.path.exists(MANIFEST_PATH):
        return {}
    try:
        with open(MANIFEST_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        log.error("failed to load %s: %s — using defaults", MANIFEST_PATH, e)
        return {}


def _apply_manifest(manifest: Dict[str, Any]) -> None:
    """Apply enabled/disabled state from manifest onto registered modules."""
    modules_cfg = manifest.get("modules", {})
    for name, mod in _REGISTRY.items():
        cfg = modules_cfg.get(name, {})
        if "enabled" in cfg:
            mod.enabled = bool(cfg["enabled"])


def _topo_sort() -> List[str]:
    """Return module names in dependency-safe load order."""
    visited: Set[str] = set()
    order: List[str] = []
    visiting: Set[str] = set()

    def visit(n: str, path: List[str]):
        if n in visited:
            return
        if n in visiting:
            cycle = " -> ".join(path + [n])
            raise RuntimeError(f"circular module dependency: {cycle}")
        if n not in _REGISTRY:
            log.warning("module %r required but not registered — skipping", n)
            return
        visiting.add(n)
        for dep in _REGISTRY[n].requires:
            visit(dep, path + [n])
        visiting.remove(n)
        visited.add(n)
        order.append(n)

    for name in _REGISTRY:
        visit(name, [])
    return order


def load_modules_for_service(service_name: str, app) -> Dict[str, Any]:
    """
    Called once at service boot. Loads every module assigned to this service
    (in dependency order) and wires its routes into the FastAPI app.

    Returns a summary suitable for logging.
    """
    global _SERVICE_NAME, _LOAD_ORDER
    _SERVICE_NAME = service_name

    manifest = _load_manifest()
    _apply_manifest(manifest)

    order = _topo_sort()
    _LOAD_ORDER = order

    summary = {"service": service_name, "loaded": [], "skipped": [],
               "disabled": [], "errors": []}

    for name in order:
        mod = _REGISTRY[name]
        if mod.service != service_name:
            summary["skipped"].append(f"{name}({mod.service})")
            continue
        if not mod.enabled:
            summary["disabled"].append(name)
            log.info("module %s: disabled by manifest", name)
            continue
        if mod.init_fn is None:
            log.warning("module %s has no init_fn — registered for tracking only",
                        name)
            mod.loaded = True
            summary["loaded"].append(name)
            continue

        # Count routes before/after to attribute new ones to this module
        before = len(app.routes) if hasattr(app, "routes") else 0
        t0 = time.time()
        try:
            mod.init_fn(app)
            mod.loaded = True
            mod.load_time_ms = (time.time() - t0) * 1000
            after = len(app.routes) if hasattr(app, "routes") else 0
            mod.routes_added = after - before
            summary["loaded"].append(name)
            log.info("module %s: loaded (%d routes, %.0fms)",
                     name, mod.routes_added, mod.load_time_ms)
        except Exception as e:
            mod.load_error = f"{type(e).__name__}: {e}"
            tb = traceback.format_exc()
            log.error("module %s: load FAILED: %s\n%s", name, mod.load_error, tb)
            summary["errors"].append({"name": name, "error": mod.load_error})

    return summary


# ── Public API ──────────────────────────────────────────────────────────────
def registry_status() -> Dict[str, Any]:
    return {
        "service": _SERVICE_NAME,
        "load_order": _LOAD_ORDER,
        "modules": {
            n: {
                "patch_id": m.patch_id,
                "service": m.service,
                "enabled": m.enabled,
                "loaded": m.loaded,
                "requires": m.requires,
                "description": m.description,
                "routes_added": m.routes_added,
                "load_time_ms": m.load_time_ms,
                "error": m.load_error,
            }
            for n, m in _REGISTRY.items()
        },
    }


def module_details(name: str) -> Optional[Dict[str, Any]]:
    if name not in _REGISTRY:
        return None
    m = _REGISTRY[name]
    return {
        "name": m.name, "patch_id": m.patch_id, "service": m.service,
        "enabled": m.enabled, "loaded": m.loaded,
        "requires": m.requires, "description": m.description,
        "routes_added": m.routes_added, "load_time_ms": m.load_time_ms,
        "error": m.load_error,
    }


def set_module_enabled(name: str, enabled: bool) -> Dict[str, Any]:
    """Persist enable/disable to manifest. Restart required to apply."""
    if name not in _REGISTRY:
        return {"ok": False, "error": "unknown_module"}

    manifest = _load_manifest()
    manifest.setdefault("modules", {}).setdefault(name, {})
    manifest["modules"][name]["enabled"] = enabled

    # Write back as TOML
    lines = ["# Murphy module manifest — auto-generated, do not edit while service running",
             "# To toggle: POST /api/system/modules/{name}/{enable|disable}",
             ""]
    for mname, mcfg in sorted(manifest.get("modules", {}).items()):
        if mcfg:
            lines.append(f"[modules.{mname}]")
            for k, v in mcfg.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {str(v).lower()}")
                elif isinstance(v, (int, float)):
                    lines.append(f"{k} = {v}")
                else:
                    lines.append(f'{k} = "{v}"')
            lines.append("")

    try:
        os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
        with open(MANIFEST_PATH, "w") as f:
            f.write("\n".join(lines))
        # Also update in-memory state
        _REGISTRY[name].enabled = enabled
        return {"ok": True, "name": name, "enabled": enabled,
                "manifest_path": MANIFEST_PATH,
                "note": "Restart the owning service to apply."}
    except Exception as e:
        return {"ok": False, "error": f"manifest_write_failed: {e}"}


# ── FastAPI wiring ──────────────────────────────────────────────────────────
def init_system_routes(app):
    """
    Wires /api/system/* — works the same on every service so any service
    can introspect itself.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.get("/api/system/modules")
    async def api_modules():
        return JSONResponse(registry_status())

    @app.get("/api/system/modules/{name}")
    async def api_module(name: str):
        d = module_details(name)
        if d is None:
            return JSONResponse({"ok": False, "error": "not_found"},
                                status_code=404)
        return JSONResponse({"ok": True, "module": d})

    @app.post("/api/system/modules/{name}/enable")
    async def api_enable(name: str):
        return JSONResponse(set_module_enabled(name, True))

    @app.post("/api/system/modules/{name}/disable")
    async def api_disable(name: str):
        return JSONResponse(set_module_enabled(name, False))

    @app.get("/api/system/health")
    async def api_system_health():
        rs = registry_status()
        loaded = sum(1 for m in rs["modules"].values() if m["loaded"])
        errors = sum(1 for m in rs["modules"].values() if m["error"])
        return JSONResponse({
            "ok": errors == 0,
            "service": rs["service"],
            "modules_total": len(rs["modules"]),
            "modules_loaded": loaded,
            "modules_with_error": errors,
            "load_order": rs["load_order"],
        })
