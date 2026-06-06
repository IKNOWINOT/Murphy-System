"""
PATCH-OPT-7 — murphy-robotics service
=======================================

WHAT THIS IS:
  Standalone service for hard-real-time robotic dispatch + voice telephony.
  Hosts:
    - PATCH-408 Household + PiCar-X (/api/household/*, /api/picarx/*, /household, /picarx)
    - PATCH-406a Voice Telephony (/api/phone/*, /phone)

WHY IT EXISTS:
  Robots can't afford GC pauses from the brain. Voice calls can't
  afford to wait for an LLM swarm to finish. By giving these their own
  process, they get their own asyncio loop, their own memory, their
  own restart cycle.

  Also: PiCar telemetry (audio/video/LiDAR) is a sustained data stream.
  Sharing that loop with rosetta/mfgc would starve compute-heavy
  cognitive work. Separation = both run smoothly.

HOW IT FITS:
  - Process: 127.0.0.1:8004 via murphy-robotics.service systemd unit
  - nginx routes /api/household/*, /api/picarx/*, /api/phone/*, /household, /picarx, /phone
  - patch408's init_household_routes wires BOTH /api/household/* AND /api/picarx/*
    (it's the same module — single init call covers both)
  - patch406a's init_voice_routes wires /api/phone/* and /phone HTML page
  - Internal auth on internal endpoints only (public dispatch is OIDC-bearer)
  - TimeoutStopSec=2 — fast SIGTERM honor as hard-stop button

KEY CONCEPTS:
  - Latency-first: every endpoint < 50ms target
  - No LLM calls in this service — those happen in core, results passed via bus
  - Hard-stop button: SIGTERM honored within 1 second

ENDPOINTS:
  /api/household/*                — PATCH-408 profiles + members
  /api/picarx/*                   — PATCH-408 PiCar dispatch + telemetry
  /household                      — PATCH-408 HTML page
  /picarx                         — PATCH-408 HTML page
  /api/phone/*                    — PATCH-406a Twilio voice
  /phone                          — PATCH-406a HTML page
  /api/system/*                   — module registry introspection
  /api/internal/*                 — cross-service auth
  /api/bus/*                      — event bus admin
  /healthz                        — public health probe

DEPENDENCIES:
  - module_registry.py
  - internal_auth.py
  - event_bus.py
  - patch408_household_picarx.py (init_household_routes)
  - patch406a_voice_telephony.py (init_voice_routes)

KNOWN LIMITS:
  - Cannot yet preempt long-running LLM calls (they happen in core)
  - PiCar real-device control is over public internet — needs PATCH-411
    stream service for private-net dispatch

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
log = logging.getLogger("murphy-robotics")

SERVICE_NAME = "robotics"
BOOT_AT = time.time()

app = FastAPI(
    title="Murphy Robotics",
    description="Household + PiCar dispatch + voice telephony (low-latency tier).",
    version="opt-7",
)

import module_registry
import internal_auth
import event_bus


def _register_patch(name, patch_id, module_path, init_attr,
                    description, requires=None):
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


# PATCH-408 covers both household AND picarx in a single init call —
# register it once as "household_and_picarx" (or we could call init twice
# but that would double-register routes). Single registration is right.
_register_patch("household_picarx", "PATCH-408", "patch408_household_picarx",
                "init_household_routes",
                "Household profiles + PiCar-X dispatch + telemetry")

_register_patch("voice_telephony", "PATCH-406a", "patch406a_voice_telephony",
                "init_voice_routes",
                "Twilio voice telephony foundation")


@app.get("/")
async def root():
    return {
        "service": SERVICE_NAME,
        "uptime_s": round(time.time() - BOOT_AT, 1),
        "purpose": "robotic dispatch + voice telephony (low-latency)",
    }


@app.get("/healthz")
async def healthz():
    return JSONResponse({"ok": True, "service": SERVICE_NAME,
                         "uptime_s": round(time.time() - BOOT_AT, 1)})


internal_auth.init_internal_auth_routes(app, SERVICE_NAME)
event_bus.init_bus_routes(app, SERVICE_NAME)
module_registry.init_system_routes(app)


@app.on_event("startup")
async def _load_modules():
    summary = module_registry.load_modules_for_service(SERVICE_NAME, app)
    log.info("robotics bootstrap: %d loaded, %d disabled, %d errors",
             len(summary["loaded"]),
             len(summary["disabled"]),
             len(summary["errors"]))
    event_bus.publish("service.booted", {
        "service": SERVICE_NAME,
        "modules_loaded": summary["loaded"],
        "errors": summary["errors"],
    })

    async def on_cmd(topic, payload):
        log.info("event %s: keys=%s", topic, list(payload.keys())[:5])

    event_bus.subscribe("robot.command.*", on_cmd)
    event_bus.subscribe("voice.call.*", on_cmd)
