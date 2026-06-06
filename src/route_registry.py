"""
route_registry.py — Single source of truth for every HTTP route Murphy serves.

Generated at startup by walking app.routes. Persisted to JSON for tools to query.
Used by murphy_voice._verify_paths_in_reply to catch URL hallucinations.

Refresh:
  - on app startup (build_route_index called from app.py)
  - manually: from src.route_registry import build_route_index; build_route_index(app)
"""
from __future__ import annotations
import json, logging, os, time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("murphy.route_registry")
REGISTRY_PATH = Path("/var/lib/murphy-production/route_registry.json")


def build_route_index(app) -> Dict[str, Any]:
    """Walk the FastAPI app and dump every route to disk."""
    routes = []
    try:
        for r in app.routes:
            path = getattr(r, "path", None)
            if not path:
                continue
            methods = sorted(list(getattr(r, "methods", set())) or ["GET"])
            name = getattr(r, "name", "") or ""
            routes.append({"path": path, "methods": methods, "name": name})
    except Exception as exc:
        log.error("build_route_index walk failed: %s", exc)
        return {"error": str(exc), "routes": []}
    payload = {
        "generated_at": time.time(),
        "count": len(routes),
        "routes": routes,
    }
    try:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(payload, indent=2))
        log.info("route_registry: %d routes written to %s", len(routes), REGISTRY_PATH)
    except Exception as exc:
        log.warning("route_registry write failed: %s", exc)
    return payload


def _load() -> Dict[str, Any]:
    try:
        if REGISTRY_PATH.exists():
            return json.loads(REGISTRY_PATH.read_text())
    except Exception as exc:
        log.warning("route_registry load failed: %s", exc)
    return {"routes": []}


def route_exists(path: str, method: str = "GET") -> Dict[str, Any]:
    """Does this URL path exist on the server? Returns dict with 'exists' and 'suggestions'."""
    data = _load()
    routes = data.get("routes", [])
    if not routes:
        return {"exists": None, "error": "registry_unavailable"}
    method = method.upper()
    # Exact match first
    for r in routes:
        if r["path"] == path and method in r["methods"]:
            return {"exists": True, "path": r["path"], "methods": r["methods"]}
    # Param-aware match — /api/jobs/{id} should match /api/jobs/abc123
    import re
    for r in routes:
        if "{" not in r["path"]:
            continue
        pat = re.sub(r"\{[^}]+\}", r"[^/]+", r["path"])
        if re.fullmatch(pat, path) and method in r["methods"]:
            return {"exists": True, "path": r["path"], "matched_pattern": True, "methods": r["methods"]}
    # Fuzzy fallback
    import difflib
    all_paths = [r["path"] for r in routes]
    close = difflib.get_close_matches(path, all_paths, n=5, cutoff=0.5)
    return {"exists": False, "suggestions": close}


def find_route(pattern: str, max_results: int = 20) -> Dict[str, Any]:
    """Substring/fuzzy search across known routes."""
    data = _load()
    pat = pattern.lower()
    matches = [r for r in data.get("routes", []) if pat in r["path"].lower()]
    matches.sort(key=lambda r: (len(r["path"]), r["path"]))
    return {"matches": matches[:max_results], "total": len(matches)}


def list_routes_by_prefix(prefix: str) -> List[Dict[str, Any]]:
    """Get all routes under a prefix (e.g. '/api/swarm')."""
    data = _load()
    return [r for r in data.get("routes", []) if r["path"].startswith(prefix)]
