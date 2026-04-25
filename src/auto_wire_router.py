"""
Murphy Auto-Wire Router — PATCH-084
Exposes a consistent REST API surface for all unwired modules.

For each module: GET /api/modules/{name}/status  — health + class inventory
For each module: POST /api/modules/{name}/call   — call any public method

This is not a substitute for purpose-built routers — it's a discovery
and activation layer that makes every module inspectable and callable.

PATCH-084 | Label: AUTOWIRE-001
"""
from __future__ import annotations

import importlib
import inspect
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/modules", tags=["auto_wire"])

# ── Module registry — every unwired module goes here ────────────────────────
MODULE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "management_systems":        {"path": "src.management_systems",       "label": "Management AI Systems"},
    "learning_engine":           {"path": "src.learning_engine",          "label": "Learning Engine"},
    "security_plane":            {"path": "src.security_plane",           "label": "Security Plane"},
    "control_theory":            {"path": "src.control_theory",           "label": "Control Theory"},
    "supervisor_system":         {"path": "src.supervisor_system",        "label": "Supervisor System"},
    "org_compiler":              {"path": "src.org_compiler",             "label": "Org Compiler"},
    "self_selling_engine":       {"path": "src.self_selling_engine",      "label": "Self-Selling Engine"},
    "execution_packet_compiler": {"path": "src.execution_packet_compiler","label": "Execution Packet Compiler"},
    "adapter_framework":         {"path": "src.adapter_framework",        "label": "Adapter Framework"},
    "autonomous_systems":        {"path": "src.autonomous_systems",       "label": "Autonomous Systems"},
    "governance_framework":      {"path": "src.governance_framework",     "label": "Governance Framework"},
    "persistent_memory":         {"path": "src.persistent_memory",        "label": "Persistent Memory"},
    "skill_system":              {"path": "src.skill_system",             "label": "Skill System"},
    "tool_registry":             {"path": "src.tool_registry",            "label": "Tool Registry"},
    "mcp_plugin":                {"path": "src.mcp_plugin",               "label": "MCP Plugin"},
    "feature_flags":             {"path": "src.feature_flags",            "label": "Feature Flags"},
    "multiverse_game_framework": {"path": "src.multiverse_game_framework","label": "Multiverse Game Framework"},
    "murphy_cli":                {"path": "src.murphy_cli",               "label": "Murphy CLI"},
    "control_plane":             {"path": "src.control_plane",            "label": "Control Plane"},
    "bridge_layer":              {"path": "src.bridge_layer",             "label": "Bridge Layer"},
    "neuro_symbolic_models":     {"path": "src.neuro_symbolic_models",    "label": "Neuro-Symbolic Models"},
    "benchmark_adapters":        {"path": "src.benchmark_adapters",       "label": "Benchmark Adapters"},
    "founder_update_engine":     {"path": "src.founder_update_engine",    "label": "Founder Update Engine"},
    "schema_registry":           {"path": "src.schema_registry",          "label": "Schema Registry"},
    "org_build_plan":            {"path": "src.org_build_plan",           "label": "Org Build Plan"},
    "strategy_templates":        {"path": "src.strategy_templates",       "label": "Strategy Templates"},
    "building_automation":       {"path": "src.building_automation",      "label": "Building Automation"},
    "energy_management":         {"path": "src.energy_management",        "label": "Energy Management"},
    "murphy_terminal":           {"path": "src.murphy_terminal",          "label": "Murphy Terminal"},
    "copilot_tenant":            {"path": "src.copilot_tenant",           "label": "Copilot Tenant"},
    "base_governance_runtime":   {"path": "src.base_governance_runtime",  "label": "Base Governance Runtime"},
    "fdd":                       {"path": "src.fdd",                      "label": "Failure-Driven Development"},
}

_module_cache: Dict[str, Any] = {}

def _load_module(name: str) -> Optional[Any]:
    if name in _module_cache:
        return _module_cache[name]
    meta = MODULE_REGISTRY.get(name)
    if not meta:
        return None
    try:
        mod = importlib.import_module(meta["path"])
        _module_cache[name] = mod
        return mod
    except Exception as exc:
        logger.warning("AUTOWIRE: failed to load %s: %s", name, exc)
        return None

def _inspect_module(mod: Any, name: str) -> Dict[str, Any]:
    """Inspect a module and return its public API surface."""
    classes = {}
    functions = {}
    
    for attr_name in dir(mod):
        if attr_name.startswith("_"):
            continue
        try:
            obj = getattr(mod, attr_name)
            if inspect.isclass(obj) and obj.__module__ == mod.__name__:
                methods = [m for m in dir(obj) if not m.startswith("_") and callable(getattr(obj, m, None))]
                classes[attr_name] = {"methods": methods[:20], "doc": (obj.__doc__ or "")[:100]}
            elif inspect.isfunction(obj) and obj.__module__ == mod.__name__:
                sig = str(inspect.signature(obj))[:80]
                functions[attr_name] = {"signature": sig, "doc": (obj.__doc__ or "")[:80]}
        except Exception:
            pass
    
    return {"classes": classes, "functions": functions}


@router.get("/")
async def list_modules():
    """List all registered modules and their load status."""
    result = {}
    for name, meta in MODULE_REGISTRY.items():
        mod = _load_module(name)
        result[name] = {
            "label": meta["label"],
            "loaded": mod is not None,
            "path": meta["path"],
        }
    total = len(result)
    loaded = sum(1 for v in result.values() if v["loaded"])
    return JSONResponse({"total": total, "loaded": loaded, "modules": result})


@router.get("/{module_name}/status")
async def module_status(module_name: str):
    """Get status and API surface of a specific module."""
    if module_name not in MODULE_REGISTRY:
        return JSONResponse({"ok": False, "error": f"Unknown module: {module_name}"}, status_code=404)
    
    mod = _load_module(module_name)
    if mod is None:
        return JSONResponse({
            "ok": False, "module": module_name,
            "label": MODULE_REGISTRY[module_name]["label"],
            "loaded": False, "error": "Module failed to import",
        })
    
    surface = _inspect_module(mod, module_name)
    return JSONResponse({
        "ok": True,
        "module": module_name,
        "label": MODULE_REGISTRY[module_name]["label"],
        "loaded": True,
        "class_count": len(surface["classes"]),
        "function_count": len(surface["functions"]),
        "classes": surface["classes"],
        "top_functions": list(surface["functions"].keys())[:15],
    })


class CallRequest(BaseModel):
    class_name: Optional[str] = None   # if calling a class method
    method: str
    args: Dict[str, Any] = {}
    init_args: Dict[str, Any] = {}     # constructor args if instantiating

@router.post("/{module_name}/call")
async def call_module_method(module_name: str, req: CallRequest):
    """Call any public method on any module."""
    if module_name not in MODULE_REGISTRY:
        return JSONResponse({"ok": False, "error": f"Unknown module: {module_name}"}, status_code=404)
    
    mod = _load_module(module_name)
    if mod is None:
        return JSONResponse({"ok": False, "error": "Module not loaded"}, status_code=503)
    
    try:
        if req.class_name:
            cls = getattr(mod, req.class_name, None)
            if cls is None:
                return JSONResponse({"ok": False, "error": f"Class {req.class_name} not found"}, status_code=404)
            instance = cls(**req.init_args)
            method_fn = getattr(instance, req.method, None)
        else:
            method_fn = getattr(mod, req.method, None)
        
        if method_fn is None:
            return JSONResponse({"ok": False, "error": f"Method {req.method} not found"}, status_code=404)
        
        t0 = time.time()
        result = method_fn(**req.args)
        elapsed = round(time.time() - t0, 3)
        
        # Serialize result safely
        try:
            import json
            json.dumps(result)
            serialized = result
        except Exception:
            serialized = str(result)[:500]
        
        return JSONResponse({
            "ok": True, "module": module_name,
            "method": req.method, "result": serialized,
            "elapsed_s": elapsed,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[:300]}, status_code=500)
