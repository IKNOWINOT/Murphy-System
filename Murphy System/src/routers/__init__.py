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

Pick the next router to extract using::

    python scripts/extract_router_candidates.py --top 20

The script reads ``src/runtime/app.py`` and ``murphy_production_server.py``,
classifies every handler by extraction safety (lower score = safer), and
groups handlers by URL-path domain. **One PR == one domain.** Start with
the lowest-score domain that has more than one handler — those are pure
extractions with no shared state, no startup-hook ordering, and no
``app.state`` threading.

Per-PR commissioning checklist (apply to every router-extraction PR):

1. Create ``src/routers/<domain>.py`` exporting a module-level ``router``.
2. Copy each handler verbatim; replace ``@app.<verb>`` with
   ``@router.<verb>`` and adjust the path (``/api/v1/<domain>/...``).
3. Add ``app.include_router(<domain>.router)`` in the entrypoint.
4. Delete the legacy inline handler in the SAME commit (no two handlers
   may register the same path).
5. Run the existing route smoke tests; the response body for each
   migrated path must be byte-identical to before.
6. Run ``ruff check --select=BLE001 src/routers/`` (already gated in CI).
7. Update ``docs/ROADMAP_TO_CLASS_S.md`` Item 1 with a row counting
   migrated handlers (``N of 184 extracted``).

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
