# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
API Route Coverage Scanner — Murphy System

Computes per-module API route coverage by comparing the routes
registered in the running FastAPI application against the canonical
specification in ``API_ROUTES.md``.

Exposes:
  ``GET  /api/route-coverage``           — full coverage report
  ``POST /api/route-coverage/scan``      — trigger a fresh scan

The dashboard "API ROUTE COVERAGE" widget reads from these endpoints
to render module cards with coverage percentages.

Module grouping
───────────────
Routes are grouped into logical dashboard modules by prefix:

  auth, admin, demo/forge, hitl, trading, compliance, automations,
  agents, llm, mail, boards, crm, workdocs, onboarding, dispatch,
  gate-synthesis, repair, wingman

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("murphy.route_coverage_scanner")


# ---------------------------------------------------------------------------
# Module grouping configuration
# ---------------------------------------------------------------------------

MODULE_PREFIX_MAP: Dict[str, List[str]] = {
    "auth": ["/api/auth/"],
    "admin": ["/api/admin/"],
    "demo/forge": ["/api/demo/"],
    "hitl": ["/api/hitl/", "/api/production/hitl/"],
    "trading": ["/api/trading/", "/api/coinbase/", "/api/market/", "/api/wallet/"],
    "compliance": ["/api/compliance/", "/api/cce/"],
    "automations": [
        "/api/automations/", "/api/automation/",
        "/api/self-automation/", "/api/scheduler/",
    ],
    "agents": ["/api/agents/", "/api/agent-dashboard/"],
    "llm": ["/api/llm/", "/api/chat/", "/api/learning/"],
    "mail": ["/api/email/", "/api/domains/", "/api/comms/"],
    "boards": ["/api/community/", "/api/reviews/"],
    "crm": ["/api/client-portfolio/", "/api/partner/", "/api/referrals/"],
    "workdocs": ["/api/documents/", "/api/forms/"],
    "onboarding": ["/api/onboarding/", "/api/onboarding-flow/"],
    "dispatch": ["/api/production/", "/api/deliverables/"],
    "gate-synthesis": ["/api/gate-synthesis/"],
    "repair": ["/api/repair/", "/api/self-fix/"],
    "wingman": ["/api/wingman/", "/api/heatmap/"],
}


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class RouteCoverageScanner:
    """Compare registered FastAPI routes against API_ROUTES.md spec."""

    def __init__(self, app=None, spec_path: Optional[str] = None) -> None:
        self._app = app
        self._spec_path = spec_path or str(
            Path(__file__).resolve().parent.parent / "API_ROUTES.md"
        )
        self._last_scan: Optional[Dict[str, Any]] = None
        self._last_scan_at: Optional[str] = None

    def set_app(self, app) -> None:
        """Bind the FastAPI app after construction."""
        self._app = app

    # ------------------------------------------------------------------
    # Spec parsing
    # ------------------------------------------------------------------

    def _parse_spec(self) -> Set[str]:
        """Parse API_ROUTES.md and return set of 'METHOD /path' strings.

        Excludes removed (~~strikethrough~~) routes.
        """
        spec_routes: Set[str] = set()
        try:
            with open(self._spec_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line.startswith("|"):
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) < 4:
                        continue
                    method = parts[1].upper().strip()
                    path = parts[2].strip()
                    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"):
                        continue
                    if "~~" in path:
                        continue
                    if not path.startswith("/api/"):
                        continue
                    spec_routes.add(f"{method} {path}")
        except FileNotFoundError:
            logger.warning("API_ROUTES.md not found at %s", self._spec_path)
        return spec_routes

    # ------------------------------------------------------------------
    # App route introspection
    # ------------------------------------------------------------------

    def _get_implemented_routes(self) -> Set[str]:
        """Introspect FastAPI app.routes for registered endpoints."""
        if self._app is None:
            return set()
        impl: Set[str] = set()
        for route in self._app.routes:
            path = getattr(route, "path", None)
            if not path or not path.startswith("/api/"):
                continue
            raw_methods = getattr(route, "methods", None)
            if raw_methods is None:
                continue
            for method in sorted(raw_methods - {"HEAD", "OPTIONS"}):
                impl.add(f"{method} {path}")
        return impl

    # ------------------------------------------------------------------
    # Coverage computation
    # ------------------------------------------------------------------

    @staticmethod
    def _categorise(route: str, prefixes: List[str]) -> bool:
        """Check if a route matches any of the module prefixes."""
        path = route.split(" ", 1)[1] if " " in route else route
        return any(path.startswith(p) for p in prefixes)

    def scan(self) -> Dict[str, Any]:
        """Run a full coverage scan and return the report.

        Returns
        -------
        dict
            ``{ "modules": [ { "name", "coverage_pct", "total",
            "covered", "missing", "extra" }, ... ],
            "overall": { ... }, "scanned_at": "..." }``
        """
        spec_routes = self._parse_spec()
        impl_routes = self._get_implemented_routes()

        modules: List[Dict[str, Any]] = []
        for mod_name, prefixes in sorted(MODULE_PREFIX_MAP.items()):
            spec_mod = {r for r in spec_routes if self._categorise(r, prefixes)}
            impl_mod = {r for r in impl_routes if self._categorise(r, prefixes)}

            covered = spec_mod & impl_mod
            missing = sorted(spec_mod - impl_mod)
            extra = sorted(impl_mod - spec_mod)

            total = len(spec_mod)
            done = len(covered)
            pct = round(done / total * 100) if total > 0 else 100

            modules.append({
                "name": mod_name,
                "coverage_pct": pct,
                "total": total,
                "covered": done,
                "route_count": total + len(extra),
                "missing": missing,
                "extra": extra,
            })

        total_spec = len(spec_routes)
        total_overlap = len(spec_routes & impl_routes)
        overall_pct = round(total_overlap / total_spec * 100) if total_spec > 0 else 100

        result = {
            "modules": modules,
            "overall": {
                "coverage_pct": overall_pct,
                "spec_routes": total_spec,
                "implemented_routes": len(impl_routes),
                "covered": total_overlap,
                "missing": total_spec - total_overlap,
            },
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }
        self._last_scan = result
        self._last_scan_at = result["scanned_at"]
        logger.info(
            "Route coverage scan: %d/%d (%d%%) — %d modules",
            total_overlap, total_spec, overall_pct, len(modules),
        )
        return result

    def get_last_scan(self) -> Optional[Dict[str, Any]]:
        """Return cached scan result."""
        return self._last_scan


def register_route_coverage_endpoints(app) -> RouteCoverageScanner:
    """Register /api/route-coverage endpoints on the FastAPI app.

    Returns the scanner instance for reuse.
    """
    from fastapi.responses import JSONResponse

    scanner = RouteCoverageScanner(app=app)

    @app.get("/api/route-coverage")
    async def route_coverage():
        """Return the last route-coverage scan result, or run a fresh scan."""
        result = scanner.get_last_scan()
        if result is None:
            result = scanner.scan()
        return JSONResponse({"success": True, **result})

    @app.post("/api/route-coverage/scan")
    async def route_coverage_scan():
        """Trigger a fresh route-coverage scan (the 'Scan Now' button)."""
        result = scanner.scan()
        return JSONResponse({"success": True, **result})

    logger.info("Route coverage scanner registered at /api/route-coverage")
    return scanner
