"""
PATCH-OPT-6 — murphy-ops service
==================================

WHAT THIS IS:
  Second standalone module-service. Hosts internal/admin subsystems:
    - PATCH-405 Secrets Vault (/api/vault/*, /vault HTML page)
    - PATCH-407 Security Audit (/api/audit/*, /audit HTML page)
    - PATCH-403 Client Solutions Sorting Hat (/api/client-solutions/*)

WHY IT EXISTS:
  Ops modules have a different SLA than customer-facing services. They
  must keep working when edge or core has issues — that's exactly when
  you need audit + vault. Isolating them on their own process means a
  buggy customer endpoint can't poison vault state.

HOW IT FITS:
  - Process: 127.0.0.1:8003 via murphy-ops.service systemd unit
  - nginx routes /api/vault/*, /api/audit/*, /api/client-solutions/*, /vault, /audit
  - SQLite DBs in /var/lib/murphy-production/ (shared filesystem path)
  - During cutover: monolith and ops both serve same routes from same code.
    nginx prefers ops; monolith is silent backup. Once cutover proven,
    we delete the monolith's init_*_routes calls.

KEY CONCEPTS:
  - Each patch module's existing init_<x>_routes(app) function is reused
  - No code changes to the patch modules themselves — just call them
  - Boot target: < 3 seconds

ENDPOINTS:
  /api/vault/*                    — PATCH-405
  /vault                          — PATCH-405 (HTML approval UI)
  /api/audit/*                    — PATCH-407
  /audit                          — PATCH-407 (HTML grade UI)
  /api/client-solutions/*         — PATCH-403
  /api/system/*                   — module registry introspection
  /api/internal/*                 — cross-service auth
  /api/bus/*                      — event bus admin
  /healthz                        — public health probe

DEPENDENCIES:
  - module_registry.py
  - internal_auth.py
  - event_bus.py
  - patch405_secrets_vault.py (init_vault_routes)
  - patch407_security_audit.py (init_audit_routes)
  - patch403_client_solutions.py (init_client_solutions_routes)

KNOWN LIMITS:
  - During parallel-serve phase: avoid simultaneous writes to vault DB
    from both ops and monolith. Practical mitigation: nginx routes only
    ops, so monolith's vault routes go unused.

LAST UPDATED: 2026-05-24 by Murphy
"""
from __future__ import annotations

import os, sys, time, logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("murphy-ops")

SERVICE_NAME = "ops"
BOOT_AT = time.time()

app = FastAPI(
    title="Murphy Ops",
    description="Vault + Audit + Sorting Hat — internal/admin surface.",
    version="opt-6",
)

import module_registry
import internal_auth
import event_bus
import modular_auth


def _register_patch(name: str, patch_id: str, module_path: str,
                    init_attr: str, description: str, requires=None):
    """
    Register a patch module by calling its known init function name.
    Falls back to stub if import fails.
    """
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
        log.info("registered %s (%s) -> %s.%s",
                 name, patch_id, module_path, init_attr)
    except Exception as e:
        log.warning("could not register %s (%s): %s", name, patch_id, e)
        module_registry.register(
            name, patch_id=patch_id, init_fn=None,
            service=SERVICE_NAME, description=f"(stub) {description}",
            requires=requires or [],
        )


# Register patch modules with their EXACT init function names
_register_patch("vault", "PATCH-405", "patch405_secrets_vault",
                "init_vault_routes",
                "AES-256-GCM secrets vault with HITL approval matrix")

_register_patch("audit", "PATCH-407", "patch407_security_audit",
                "init_audit_routes",
                "15-check security audit + compliance evidence chain")

_register_patch("client_solutions", "PATCH-403", "patch403_client_solutions",
                "init_client_solutions_routes",
                "Customer ticket triage + free-month policy gate")

_register_patch("event_spine", "PATCH-400", "patch400_event_spine",
                "init_event_spine_routes",
                "Universal event spine + HITL-as-graph + hash chain audit")


# ── System routes ───────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "uptime_s": round(time.time() - BOOT_AT, 1),
        "purpose": "vault + audit + sorting hat (internal/admin)",
    }


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "service": SERVICE_NAME,
                         "uptime_s": round(time.time() - BOOT_AT, 1)})


internal_auth.init_internal_auth_routes(app, SERVICE_NAME)
event_bus.init_bus_routes(app, SERVICE_NAME)
module_registry.init_system_routes(app)

# PATCH-412 — CapabilityCube: semantic addressing for all capability modules
try:
    import patch412_capability_cube as cube_mod
    cube_mod.install_cube_routes(app)
    cube_mod.seed_builtin_capabilities()
    # CAF (2026-05-26): also autoseed HTTP routes from the registry
    try:
        try:
            from src.capability_autoseed import autoseed_from_routes
        except (ImportError, ModuleNotFoundError):
            from capability_autoseed import autoseed_from_routes
        n = autoseed_from_routes(max_routes=120)
        log.info("CAF autoseed (ops process): %d HTTP routes registered", n)
    except Exception as _as_exc:
        log.warning("CAF autoseed (ops) failed: %s", _as_exc)
    log.info("PATCH-412 CapabilityCube online — %d capabilities seeded",
             len(cube_mod.get_cube().list_all()))
except Exception as e:
    log.error("PATCH-412 CapabilityCube failed to load: %s", e)

# PATCH-411 — Modular service authentication (added 2026-05-24)
modular_auth.install_modular_auth(app, service_name="ops")



@app.on_event("startup")
async def _load_modules():
    summary = module_registry.load_modules_for_service(SERVICE_NAME, app)
    loaded_with_routes = sum(
        1 for n in summary["loaded"]
        if module_registry.module_details(n)
        and module_registry.module_details(n).get("routes_added", 0) > 0
    )
    log.info("ops bootstrap: %d modules loaded (%d wired routes), "
             "%d disabled, %d errors",
             len(summary["loaded"]), loaded_with_routes,
             len(summary["disabled"]), len(summary["errors"]))
    event_bus.publish("service.booted", {
        "service": SERVICE_NAME,
        "modules_loaded": summary["loaded"],
        "errors": summary["errors"],
    })

    async def on_audit(topic, payload):
        log.info("event %s: keys=%s", topic, list(payload.keys())[:5])

    event_bus.subscribe("audit.*", on_audit)
    event_bus.subscribe("vault.*", on_audit)
    event_bus.subscribe("internal_auth.failed", on_audit)
