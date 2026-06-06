"""
capability_autoseed.py — Expand CapabilityCube from real Murphy infra.

The seeded cube has only 10 capabilities. Murphy has hundreds of real
endpoints, agents, and modules. This walks them at boot and registers
each as a capability so CAF discovery actually finds matches.
"""
from __future__ import annotations
import json, logging
from pathlib import Path

log = logging.getLogger("murphy.capability_autoseed")


def autoseed_from_routes(max_routes: int = 100) -> int:
    """Read route_registry and add high-value /api/* routes as capabilities."""
    try:
        try:
            from src.patch412_capability_cube import (
                CapabilityCube, CapabilityManifest,
                Accepts, Produces, Domain, RiskClass, TrustTier, SoulFit,
            )
        except (ImportError, ModuleNotFoundError):
            from patch412_capability_cube import (
                CapabilityCube, CapabilityManifest,
                Accepts, Produces, Domain, RiskClass, TrustTier, SoulFit,
            )
    except Exception as exc:
        log.warning("autoseed: capability cube import failed: %s", exc)
        return 0

    reg = Path("/var/lib/murphy-production/route_registry.json")
    if not reg.exists():
        return 0
    data = json.loads(reg.read_text())

    try:
        try:
            from src.patch412_capability_cube import get_cube
        except (ImportError, ModuleNotFoundError):
            from patch412_capability_cube import get_cube
        cube = get_cube()
    except Exception as exc:
        log.warning("autoseed: get_cube failed: %s", exc)
        return 0

    # Categorize routes by prefix into domains
    domain_map = {
        "/api/crm":          Domain.SALES if hasattr(Domain, "SALES") else Domain.PLATFORM,
        "/api/swarm":        Domain.OBSERVABILITY if hasattr(Domain, "OBSERVABILITY") else Domain.PLATFORM,
        "/api/patcher":      Domain.PLATFORM,
        "/api/hitl":         Domain.UX if hasattr(Domain, "UX") else Domain.PLATFORM,
        "/api/mail":         Domain.PLATFORM,
        "/api/phone":        Domain.PLATFORM,
        "/api/channels":     Domain.PLATFORM,
        "/api/audit":        Domain.OBSERVABILITY if hasattr(Domain, "OBSERVABILITY") else Domain.PLATFORM,
        "/api/billing":      Domain.PLATFORM,
        "/api/grants":       Domain.SALES if hasattr(Domain, "SALES") else Domain.PLATFORM,
        "/api/self":         Domain.OBSERVABILITY if hasattr(Domain, "OBSERVABILITY") else Domain.PLATFORM,
        "/api/cube":         Domain.PLATFORM,
        "/api/registry":     Domain.PLATFORM,
        "/api/rosetta":      Domain.PLATFORM,
        "/api/llm":          Domain.PLATFORM,
        "/api/pulse":        Domain.OBSERVABILITY if hasattr(Domain, "OBSERVABILITY") else Domain.PLATFORM,
        "/api/voice":        Domain.PLATFORM,
        "/api/sms":          Domain.PLATFORM,
        "/api/jobs":         Domain.PLATFORM,
    }

    seeded = 0
    seen_names = set()
    for route in data.get("routes", []):
        path = route.get("path", "")
        methods = route.get("methods", [])
        # Skip non-API and parameterized routes for cleaner names
        if not path.startswith("/api/"):
            continue
        if "{" in path:
            continue
        # Choose method label
        method = "POST" if "POST" in methods else ("GET" if "GET" in methods else (methods[0] if methods else "GET"))
        # Pick domain
        dom = Domain.PLATFORM
        for prefix, d in domain_map.items():
            if path.startswith(prefix):
                dom = d
                break
        # Build a name from the path
        name = "http_" + path.replace("/api/", "").replace("/", "_").replace("-", "_")[:60]
        if name in seen_names:
            continue
        seen_names.add(name)
        # Description = the route name from registry, or the path itself
        desc = route.get("name", "") or f"{method} {path}"
        # Risk class — most reads are green, writes default to yellow
        risk = RiskClass.YELLOW if method in ("POST", "PUT", "DELETE", "PATCH") else RiskClass.GREEN
        try:
            cube.register(name, CapabilityManifest(
                accepts={Accepts.USER_INTENT},
                produces={Produces.DATA_RECORD},
                domain=dom,
                risk_class=risk,
                trust_tier=TrustTier.BUILTIN,
                soul_fit=SoulFit.EXECUTOR if hasattr(SoulFit, "EXECUTOR") else SoulFit.AUDITOR,
                cost_hint=0.0,
                avg_latency_ms=200,
                description=f"{method} {path}",
                tags=[path.split("/")[2] if len(path.split("/")) > 2 else "api"],
            ))
            seeded += 1
            if seeded >= max_routes:
                break
        except Exception:
            continue

    log.info("capability_autoseed: registered %d HTTP-route capabilities", seeded)
    return seeded
