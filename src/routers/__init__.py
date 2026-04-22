"""
src.routers — FastAPI APIRouter package.

Class S Roadmap, Item 1 (scaffolding).

This package is the destination for handlers extracted from
``murphy_production_server.py``. Each domain (HITL, automations, auth,
marketing, infrastructure, feedback, BAS/EMS, etc.) lands as one module
exposing a module-level ``router`` of type :class:`fastapi.APIRouter`.

Decomposition strategy
----------------------
Routers are extracted incrementally, one domain per PR, leaving the legacy
handlers in place until the new router is wired and tests pass. The legacy
handler is then removed in the same PR as the router wiring to avoid a
window where two handlers race for the same path.

Example skeleton for a new router::

    # src/routers/hitl.py
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/v1/hitl", tags=["hitl"])

    @router.get("/queue")
    async def list_queue() -> dict:
        ...

And the assembler in ``murphy_production_server.py``::

    from src.routers import hitl as hitl_router
    app.include_router(hitl_router.router)

This package is intentionally empty at first and grows one module at a time.
"""

from __future__ import annotations

__all__: list[str] = []
