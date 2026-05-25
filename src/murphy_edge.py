"""
PATCH-OPT-5/8 — murphy-edge service

WHAT THIS IS:
  Standalone lightweight FastAPI service that handles:
    - PATCH-410 Unified Identity (device pair, capabilities, voice login)
    - System introspection (/api/system/*)
    - Internal auth diagnostics (/api/internal/*)
    - Event bus admin (/api/bus/*)

LAST UPDATED: 2026-05-24 (OPT-8: PATCH-410 promoted from stub to full wire)
"""
from __future__ import annotations

import os, sys, time, logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("murphy-edge")

SERVICE_NAME = "edge"
BOOT_AT = time.time()

app = FastAPI(
    title="Murphy Edge",
    description="Identity + system gateway for the modular Murphy architecture.",
    version="opt-8",
)

import module_registry
import internal_auth
import event_bus
import modular_auth


def _register_patch(name, patch_id, module_path, init_attr, description, requires=None):
    """Register a patch module by calling its known init function."""
    try:
        mod = __import__(module_path)
        init_fn = getattr(mod, init_attr, None)
        if init_fn is None:
            raise AttributeError(f"{module_path}.{init_attr} not found")
        module_registry.register(
            name, patch_id=patch_id, init_fn=init_fn,
            service=SERVICE_NAME, description=description,
            requires=requires or [],
        )
        log.info("registered %s (%s) -> %s.%s", name, patch_id, module_path, init_attr)
    except Exception as e:
        log.warning("could not register %s (%s): %s", name, patch_id, e)
        module_registry.register(
            name, patch_id=patch_id, init_fn=None,
            service=SERVICE_NAME, description=f"(stub) {description}",
            requires=requires or [],
        )


# PATCH-417: Outbound Review Queue (Phase 7a hard prereq for swarm sales)
_register_patch(
    "mail_outbound", "PATCH-417", "patch417_outbound_queue",
    "init_outbound_routes",
    "Outbound email queue with founder approval; intercepts swarm-agent sends",
    requires=["identity"],
)


# PATCH-410: full Identity wire-up (was stub in OPT-5; promoted in OPT-8)
_register_patch(
    "identity", "PATCH-410", "patch410_unified_identity",
    "init_identity_routes",
    "Device pair + capabilities + voice login + token refresh + /devices HTML",
)


@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "uptime_s": round(time.time() - BOOT_AT, 1),
        "purpose": "identity + system gateway",
        "endpoints": ["/api/identity/*", "/api/system/*",
                      "/api/internal/*", "/api/bus/*", "/devices"],
    }


@app.get("/healthz")
async def healthz():
    return JSONResponse({
        "ok": True, "service": SERVICE_NAME,
        "uptime_s": round(time.time() - BOOT_AT, 1),
    })


internal_auth.init_internal_auth_routes(app, SERVICE_NAME)
event_bus.init_bus_routes(app, SERVICE_NAME)
module_registry.init_system_routes(app)

# PATCH-411 — Modular service authentication (added 2026-05-24)
modular_auth.install_modular_auth(app, service_name="edge")



@app.on_event("startup")
async def _load_modules():
    summary = module_registry.load_modules_for_service(SERVICE_NAME, app)
    log.info(
        "edge bootstrap: %d loaded, %d disabled, %d errors",
        len(summary["loaded"]), len(summary["disabled"]), len(summary["errors"]),
    )
    event_bus.publish("service.booted", {
        "service": SERVICE_NAME,
        "modules_loaded": summary["loaded"],
        "errors": summary["errors"],
    })
