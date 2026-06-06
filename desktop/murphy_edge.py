"""
PATCH-OPT-5 — murphy-edge service
===================================

WHAT THIS IS:
  The first standalone module-service in Murphy's new architecture.
  Lightweight FastAPI process that handles:
    - Identity (PATCH-410): device pairing, capabilities, voice login
    - Auth gateway: validates OIDC bearers, session cookies, API keys
    - System introspection: /api/system/modules, /api/system/health
    - Internal auth diagnostics: /api/internal/health, /api/internal/ping
    - Event bus: /api/bus/status, /api/bus/topics

  Listens on 127.0.0.1:8011 (during cutover; will become :8000 once monolith
  vacates that port). nginx is updated to route /api/identity/* here first.

WHY IT EXISTS:
  Identity should boot in seconds, not 90 — when the monolith is starting,
  customers should still be able to login. Edge is the always-on, never-
  crashes-because-it's-tiny entry point.

HOW IT FITS:
  - Imported by uvicorn via murphy-edge.service systemd unit
  - Discovers + registers modules tagged service="edge"
  - Forwards core/business/ops/robotics calls via internal_auth.call_internal
  - Does NOT import rosetta/mfgc/swarm — those stay in core

KEY CONCEPTS:
  - Boot target: < 5 seconds (vs monolith's 90s)
  - Module set: identity + auth + system + internal_auth + event_bus
  - Process isolation: edge crash never blocks robotics or core

ENDPOINTS:
  GET  /                       — service banner
  GET  /api/internal/health    — public health probe (no auth)
  GET  /api/system/health      — registry health
  GET  /api/system/modules     — what's loaded
  /api/identity/*              — PATCH-410 (when wired)
  /api/bus/*                   — event bus admin

DEPENDENCIES:
  - module_registry.py
  - internal_auth.py
  - event_bus.py
  - patch410_unified_identity.py (when migrated)

KNOWN LIMITS:
  - Identity routes not yet migrated this iteration (TODO PATCH-OPT-6)
  - Auth middleware reconciliation deferred to next session

LAST UPDATED: 2026-05-24 by Murphy
"""
from __future__ import annotations

import os, sys, time, logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse

# Make our modules importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("murphy-edge")

SERVICE_NAME = "edge"
BOOT_AT = time.time()

app = FastAPI(
    title="Murphy Edge",
    description="Identity + auth gateway for the modular Murphy architecture.",
    version="opt-5",
)

# ── Bootstrap modules ───────────────────────────────────────────────────────
try:
    import module_registry
    import internal_auth
    import event_bus
except Exception as e:
    log.critical("FATAL: cannot import bootstrap modules: %s", e)
    raise

# Register identity module if present
try:
    import patch410_unified_identity as p410
    def _init_identity(app_):
        # patch410 has an init_routes(app) or similar — try common patterns
        for name in ("init_routes", "register_routes", "init", "setup"):
            fn = getattr(p410, name, None)
            if callable(fn):
                fn(app_)
                return
        log.warning("PATCH-410 imported but no init function found — skipping route wire")
    module_registry.register(
        "identity", patch_id="PATCH-410",
        init_fn=_init_identity, service="edge",
        description="Device pairing, capabilities, voice login",
    )
except ImportError:
    log.info("PATCH-410 module not yet available — identity stub mode")
    module_registry.register(
        "identity", patch_id="PATCH-410",
        init_fn=None, service="edge",
        description="(stub) Device pairing — module not imported",
    )


# ── Always-on system routes (registry, internal_auth, event_bus) ────────────
@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "uptime_s": round(time.time() - BOOT_AT, 1),
        "endpoints": [
            "/api/internal/health",
            "/api/system/health",
            "/api/system/modules",
            "/api/bus/status",
        ],
    }


@app.get("/healthz")
async def healthz():
    """Always 200 if process is alive. For nginx/watchdog."""
    return JSONResponse({"ok": True, "service": SERVICE_NAME,
                         "uptime_s": round(time.time() - BOOT_AT, 1)})


# Mount common subsystem routes
internal_auth.init_internal_auth_routes(app, SERVICE_NAME)
event_bus.init_bus_routes(app, SERVICE_NAME)
module_registry.init_system_routes(app)


# ── Load all edge-service modules in dependency order ──────────────────────
@app.on_event("startup")
async def _load_modules():
    summary = module_registry.load_modules_for_service(SERVICE_NAME, app)
    log.info("edge bootstrap complete: %d loaded, %d disabled, %d errors",
             len(summary["loaded"]), len(summary["disabled"]),
             len(summary["errors"]))
    # Emit a boot event
    event_bus.publish("service.booted", {
        "service": SERVICE_NAME,
        "modules_loaded": summary["loaded"],
        "modules_disabled": summary["disabled"],
        "errors": summary["errors"],
    })


# ── For uvicorn ─────────────────────────────────────────────────────────────
# Run with: uvicorn murphy_edge:app --host 127.0.0.1 --port 8011
