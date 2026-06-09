"""
PCR-054c.1 — Engagement Loop HTTP surface

Mirrors PCR-053d's org_compiler_routes pattern: a single registration
function attaches engagement endpoints to the running app. Idempotent,
additive, reversible.

WHAT THIS WIRES:

  app.state._engagement_routes_registered → idempotency guard

  POST /api/org/engagement/create
       → create a new EngagementFolder in DRAFTING. Body: tenant_id,
         role_id, artifact_type, artifact_content (string), and
         optional license_type_required + jurisdiction_required.

  POST /api/org/engagement/{engagement_id}/transition
       → move folder to a new state (drafting -> outreach_queued -> ...).
         Body: to_state, optional reason, optional update_fields dict.

  GET  /api/org/engagement/{engagement_id}
       → fetch folder summary + recent events + attestations.

  GET  /api/org/engagements
       → list folders, optionally filtered by tenant_id and state.

WHAT THIS DOES NOT WIRE (deferred):
  - Outbound engagement-request email composition  → PCR-054d
  - Inbound attestation parser                      → PCR-054e
  - Rate quoting in the email                       → PCR-054f

ALL ROUTES:
  - Fail-soft: bad SQLite path / missing file = HTTP 500 with structured
    error, not a stack trace.
  - Idempotent: registration is guarded by app.state flag; double-wire = no-op.
  - JSONResponse with explicit status codes (matches PCR-053d/f voice).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover — only matters in test/import shadowing
    HTTPException = None  # type: ignore
    JSONResponse = None  # type: ignore
    BaseModel = object  # type: ignore
    Field = lambda *a, **kw: None  # type: ignore

from src.engagement_folder import (
    DEFAULT_BROWSE_ROOT,
    DEFAULT_DB_PATH,
    FolderState,
    IllegalTransition,
    create_folder,
    folder_summary,
    get_attestations,
    get_events,
    get_folder,
    init_db,
    list_folders,
    transition,
)

LOG = logging.getLogger("murphy.engagement_routes")


# ─────────────────────────────────────────────────────────────────────
# Request models (only when pydantic is available)
# ─────────────────────────────────────────────────────────────────────


class _CreateBody(BaseModel):  # type: ignore[misc]
    tenant_id: str
    role_id: str
    artifact_type: str
    artifact_content: str = ""
    license_type_required: Optional[str] = None
    jurisdiction_required: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class _TransitionBody(BaseModel):  # type: ignore[misc]
    to_state: str
    reason: str = ""
    actor: str = "system"
    update_fields: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _err(status: int, body: Dict[str, Any]):
    """Structured JSON error, matches PCR-053d voice."""
    if JSONResponse is not None:
        return JSONResponse(content=body, status_code=status)
    return (body, status)


def _parse_state(value: str) -> FolderState:
    try:
        return FolderState(value)
    except ValueError as e:
        raise ValueError(
            f"unknown state '{value}'; valid: {[s.value for s in FolderState]}"
        ) from e


# ─────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────


def register_engagement_routes(
    app,
    *,
    db_path: str = DEFAULT_DB_PATH,
    browse_root: str = DEFAULT_BROWSE_ROOT,
) -> Dict[str, Any]:
    """Attach engagement-loop routes to a FastAPI app.

    Returns a small status dict so the lifespan wiring can log what happened.
    Safe to call multiple times — guarded by app.state._engagement_routes_registered.
    """
    status: Dict[str, Any] = {
        "ok": True,
        "registered": False,
        "routes_added": [],
        "db_path": db_path,
        "browse_root": browse_root,
    }

    if getattr(app.state, "_engagement_routes_registered", False):
        status["registered"] = True
        status["note"] = "already registered (idempotent no-op)"
        return status

    # Make sure schema exists before any request hits.
    try:
        init_db(db_path)
    except Exception as e:
        status["ok"] = False
        status["error"] = f"init_db failed: {type(e).__name__}: {e}"
        LOG.exception("PCR-054c.1 init_db failed")
        return status

    # ── POST /api/org/engagement/create ───────────────────────────
    @app.post("/api/org/engagement/create")
    async def engagement_create(body: _CreateBody):
        try:
            folder = create_folder(
                tenant_id=body.tenant_id,
                role_id=body.role_id,
                artifact_type=body.artifact_type,
                artifact_content=body.artifact_content,
                license_type_required=body.license_type_required,
                jurisdiction_required=body.jurisdiction_required,
                metadata=body.metadata,
                db_path=db_path,
                browse_root=browse_root,
            )
            return {"ok": True, "engagement": folder_summary(folder)}
        except Exception as e:
            LOG.exception("PCR-054c.1 create failed")
            return _err(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    status["routes_added"].append("POST /api/org/engagement/create")

    # ── POST /api/org/engagement/{id}/transition ──────────────────
    @app.post("/api/org/engagement/{engagement_id}/transition")
    async def engagement_transition(engagement_id: str, body: _TransitionBody):
        try:
            target = _parse_state(body.to_state)
        except ValueError as e:
            return _err(400, {"ok": False, "error": str(e)})
        try:
            folder = transition(
                engagement_id, target,
                actor=body.actor, reason=body.reason,
                update_fields=body.update_fields,
                db_path=db_path,
            )
            return {"ok": True, "engagement": folder_summary(folder)}
        except IllegalTransition as e:
            return _err(409, {"ok": False, "error": str(e)})
        except Exception as e:
            LOG.exception("PCR-054c.1 transition failed")
            return _err(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    status["routes_added"].append("POST /api/org/engagement/{id}/transition")

    # ── GET /api/org/engagement/{id} ──────────────────────────────
    @app.get("/api/org/engagement/{engagement_id}")
    async def engagement_get(engagement_id: str):
        try:
            folder = get_folder(engagement_id, db_path=db_path)
            if folder is None:
                return _err(404, {"ok": False, "error": "not_found"})
            events = get_events(engagement_id, db_path=db_path)
            attestations = get_attestations(engagement_id, db_path=db_path)
            return {
                "ok": True,
                "engagement": folder_summary(folder),
                "events": events,
                "attestations": attestations,
            }
        except Exception as e:
            LOG.exception("PCR-054c.1 get failed")
            return _err(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    status["routes_added"].append("GET /api/org/engagement/{id}")

    # ── GET /api/org/engagements ──────────────────────────────────
    @app.get("/api/org/engagements")
    async def engagement_list(
        tenant_id: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 50,
    ):
        try:
            state_enum = _parse_state(state) if state else None
        except ValueError as e:
            return _err(400, {"ok": False, "error": str(e)})
        try:
            folders = list_folders(
                tenant_id=tenant_id, state=state_enum,
                limit=limit, db_path=db_path,
            )
            return {
                "ok": True,
                "count": len(folders),
                "engagements": [folder_summary(f) for f in folders],
            }
        except Exception as e:
            LOG.exception("PCR-054c.1 list failed")
            return _err(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    status["routes_added"].append("GET /api/org/engagements")

    # Mark idempotent
    app.state._engagement_routes_registered = True
    status["registered"] = True
    LOG.info(
        "PCR-054c.1 engagement routes registered: %d endpoints (db=%s, browse=%s)",
        len(status["routes_added"]), db_path, browse_root,
    )
    return status
