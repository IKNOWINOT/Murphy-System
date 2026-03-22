"""
Grant API — FastAPI router for all grant system endpoints.

All endpoints under /api/grants/. Follows src/billing/api.py patterns:
FastAPI, Pydantic models, proper error handling, logging, tenant isolation.

Endpoints:
  GET  /api/grants/eligibility                    — Match project → grants
  GET  /api/grants/programs                       — List all programs
  GET  /api/grants/programs/{program_id}          — Program details
  GET  /api/grants/stats                          — Catalog stats
  POST /api/grants/sessions                       — Create session
  GET  /api/grants/sessions                       — List sessions
  GET  /api/grants/sessions/{session_id}          — Session details
  DELETE /api/grants/sessions/{session_id}        — Delete session
  POST /api/grants/sessions/{session_id}/credentials    — Assign access
  DELETE /api/grants/sessions/{session_id}/credentials/{user_id} — Revoke
  GET  /api/grants/sessions/{session_id}/formdata       — Get form data
  PUT  /api/grants/sessions/{session_id}/formdata       — Update form data
  POST /api/grants/sessions/{session_id}/applications           — Start app
  GET  /api/grants/sessions/{session_id}/applications           — List apps
  GET  /api/grants/sessions/{session_id}/applications/{app_id}  — Get app
  PUT  /api/grants/sessions/{session_id}/applications/{app_id}  — Update app
  DELETE /api/grants/sessions/{session_id}/applications/{app_id} — Delete app
  GET  /api/grants/sessions/{session_id}/tasks                  — Task queue
  PUT  /api/grants/sessions/{session_id}/tasks/{task_id}        — Update task
  GET  /api/grants/sessions/{session_id}/tasks/{task_id}/dependencies — Deps
  GET  /api/grants/prerequisites                  — Prerequisite chain
  PUT  /api/grants/prerequisites/{prereq_id}      — Mark prereq complete
  GET  /api/grants/profiles                       — Murphy profiles
  GET  /api/grants/profiles/{flavor}              — Specific profile

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.billing.grants.database import GRANT_CATALOG, get_catalog_stats, list_grants
from src.billing.grants.engine import GrantEligibilityEngine
from src.billing.grants.models import (
    EligibilityRequest,
    GrantCategory,
    GrantFlavor,
    GrantTrack,
    HitlTaskState,
    PrerequisiteStatus,
    SessionRole,
)
from src.billing.grants.murphy_profiles import get_all_profiles, get_profile
from src.billing.grants.prerequisites import get_prereq_chain
from src.billing.grants.sessions import SessionManager, TenantAccessError, get_session_manager
from src.billing.grants.task_queue import HitlTaskManager, TaskNotFoundError, get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/grants", tags=["grants"])

# ---------------------------------------------------------------------------
# Security constants (consistent with billing/api.py)
# ---------------------------------------------------------------------------
_ACCOUNT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")
_PREREQ_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_FLAVOR_RE = re.compile(r"^[a-zA-Z0-9_-]{1,50}$")


def _validate_id(value: str, field_name: str = "id", pattern: re.Pattern = _ACCOUNT_ID_RE) -> str:
    if not value or not pattern.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value!r}")
    return value


def _dev_mode() -> bool:
    return os.environ.get("MURPHY_ENV", "production").lower() == "development"


def _handle_error(exc: Exception, detail: str = "Internal error") -> HTTPException:
    if _dev_mode():
        return HTTPException(status_code=500, detail=str(exc))
    return HTTPException(status_code=500, detail=detail)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=1000)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssignCredentialRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=200)
    role: SessionRole = SessionRole.VIEWER


class UpdateFormDataRequest(BaseModel):
    data: Dict[str, Any] = Field(..., description="Key-value pairs to save")
    source: str = Field("user_input", max_length=50)


class CreateApplicationRequest(BaseModel):
    grant_id: str = Field(..., min_length=1, max_length=100)


class UpdateApplicationRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    estimated_value_usd: Optional[float] = None


class UpdateTaskRequest(BaseModel):
    state: HitlTaskState
    human_provided_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class UpdatePrerequisiteRequest(BaseModel):
    status: PrerequisiteStatus
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper to extract account_id from request headers (mock for now)
# ---------------------------------------------------------------------------

def _get_account_id(request: Request) -> str:
    """Extract account_id from request. In production, from JWT/session."""
    account_id = request.headers.get("X-Account-Id", "")
    if not account_id:
        # In dev mode, use a default account
        if _dev_mode():
            return "dev-account"
        raise HTTPException(status_code=401, detail="X-Account-Id header required")
    return _validate_id(account_id, "account_id")


# ---------------------------------------------------------------------------
# Eligibility endpoints
# ---------------------------------------------------------------------------

@router.get("/eligibility")
async def get_eligibility(
    project_type: str = Query(..., description="Project type (bas_bms, ems, scada, manufacturing, etc.)"),
    entity_type: str = Query("small_business", description="Entity type"),
    state: str = Query("OR", description="2-letter US state code"),
    project_cost_usd: Optional[float] = Query(None, description="Estimated project cost in USD"),
    is_commercial: bool = Query(True),
    has_rd_activity: bool = Query(False),
    existing_building: bool = Query(True),
    zip_code: Optional[str] = Query(None),
) -> JSONResponse:
    """Match project parameters to applicable grant and incentive programs."""
    try:
        req = EligibilityRequest(
            project_type=project_type,
            entity_type=entity_type,
            state=state.upper()[:2],
            project_cost_usd=project_cost_usd,
            is_commercial=is_commercial,
            has_rd_activity=has_rd_activity,
            existing_building=existing_building,
            zip_code=zip_code,
        )
        engine = GrantEligibilityEngine()
        response = engine.match(req)
        return JSONResponse(content={
            "matches": [
                {
                    "grant_id": m.grant.id,
                    "grant_name": m.grant.name,
                    "category": m.grant.category.value,
                    "match_score": m.match_score,
                    "estimated_value_usd": m.estimated_value_usd,
                    "match_reasons": m.match_reasons,
                    "stacking_opportunities": m.stacking_opportunities,
                    "program_url": m.grant.program_url,
                    "value_description": m.grant.value_description,
                }
                for m in response.matches
            ],
            "total_matches": len(response.matches),
            "total_estimated_value_usd": response.total_estimated_value_usd,
            "evaluated_at": response.evaluated_at.isoformat(),
        })
    except Exception as exc:
        logger.exception("Eligibility matching failed")
        raise _handle_error(exc, "Eligibility matching failed") from exc


# ---------------------------------------------------------------------------
# Grant program endpoints
# ---------------------------------------------------------------------------

@router.get("/programs")
async def list_programs(
    category: Optional[str] = Query(None),
    track: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
) -> JSONResponse:
    """List all grant programs with optional filtering."""
    try:
        cat_filter = GrantCategory(category) if category else None
        track_filter = GrantTrack(track) if track else None
        grants = list_grants(category=cat_filter, track=track_filter, state=state)
        return JSONResponse(content={
            "programs": [
                {
                    "id": g.id,
                    "name": g.name,
                    "category": g.category.value,
                    "track": g.track.value,
                    "short_description": g.short_description,
                    "value_description": g.value_description,
                    "min_amount_usd": g.min_amount_usd,
                    "max_amount_usd": g.max_amount_usd,
                    "program_url": g.program_url,
                    "is_recurring": g.is_recurring,
                    "longevity_note": g.longevity_note,
                    "tags": g.tags,
                }
                for g in grants
            ],
            "total": len(grants),
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/programs/{program_id}")
async def get_program(program_id: str) -> JSONResponse:
    """Get full details of a specific grant program."""
    _validate_id(program_id, "program_id")
    grant = GRANT_CATALOG.get(program_id)
    if not grant:
        raise HTTPException(status_code=404, detail=f"Program {program_id!r} not found")
    return JSONResponse(content=grant.model_dump())


@router.get("/stats")
async def get_stats() -> JSONResponse:
    """Return catalog statistics."""
    return JSONResponse(content=get_catalog_stats())


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions")
async def create_session(
    request: Request,
    body: CreateSessionRequest,
) -> JSONResponse:
    """Create a new grant workspace (session) for the authenticated account."""
    account_id = _get_account_id(request)
    try:
        mgr = get_session_manager()
        session = mgr.create_session(
            account_id=account_id,
            name=body.name,
            description=body.description,
            metadata=body.metadata,
        )
        return JSONResponse(content=session.model_dump(mode="json"), status_code=201)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create grant session")
        raise _handle_error(exc, "Failed to create session") from exc


@router.get("/sessions")
async def list_sessions(request: Request) -> JSONResponse:
    """List all grant sessions for the authenticated account."""
    account_id = _get_account_id(request)
    mgr = get_session_manager()
    sessions = mgr.list_sessions(account_id)
    return JSONResponse(content={
        "sessions": [s.model_dump(mode="json") for s in sessions],
        "total": len(sessions),
    })


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: str) -> JSONResponse:
    """Get details of a specific grant session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        session = mgr.get_session(session_id, account_id)
        return JSONResponse(content=session.model_dump(mode="json"))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str) -> JSONResponse:
    """Delete a grant session and all associated data."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        mgr.delete_session(session_id, account_id)
        return JSONResponse(content={"status": "deleted", "session_id": session_id})
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Session credential endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/credentials")
async def assign_credential(
    request: Request,
    session_id: str,
    body: AssignCredentialRequest,
) -> JSONResponse:
    """Assign access to a session for another user."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        cred = mgr.assign_credential(
            session_id=session_id,
            user_id=body.user_id,
            role=body.role,
            granted_by=account_id,
        )
        return JSONResponse(content=cred.model_dump(mode="json"), status_code=201)
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}/credentials/{user_id}")
async def revoke_credential(
    request: Request,
    session_id: str,
    user_id: str,
) -> JSONResponse:
    """Revoke a user's access to a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        mgr.revoke_credential(session_id=session_id, user_id=user_id, revoked_by=account_id)
        return JSONResponse(content={"status": "revoked", "user_id": user_id})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Saved form data endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/formdata")
async def get_form_data(request: Request, session_id: str) -> JSONResponse:
    """Get all saved form data for a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        data = mgr.get_form_data(session_id, account_id)
        return JSONResponse(content={
            "session_id": session_id,
            "form_data": {k: v.model_dump(mode="json") for k, v in data.items()},
        })
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.put("/sessions/{session_id}/formdata")
async def update_form_data(
    request: Request,
    session_id: str,
    body: UpdateFormDataRequest,
) -> JSONResponse:
    """Update saved form data for a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        updated = mgr.bulk_update_form_data(
            session_id=session_id,
            data=body.data,
            requesting_account_id=account_id,
            source=body.source,
        )
        return JSONResponse(content={
            "session_id": session_id,
            "updated_fields": list(updated.keys()),
        })
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    except TenantAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Application endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/applications")
async def create_application(
    request: Request,
    session_id: str,
    body: CreateApplicationRequest,
) -> JSONResponse:
    """Start a new grant application within a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    if body.grant_id not in GRANT_CATALOG:
        raise HTTPException(status_code=404, detail=f"Grant {body.grant_id!r} not found")
    try:
        mgr = get_session_manager()
        app = mgr.create_application(session_id, body.grant_id, account_id)
        return JSONResponse(content=app.model_dump(mode="json"), status_code=201)
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/applications")
async def list_applications(request: Request, session_id: str) -> JSONResponse:
    """List all applications in a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        apps = mgr.list_applications(session_id, account_id)
        return JSONResponse(content={
            "applications": [a.model_dump(mode="json") for a in apps],
            "total": len(apps),
        })
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/applications/{app_id}")
async def get_application(request: Request, session_id: str, app_id: str) -> JSONResponse:
    """Get a specific application."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        app = mgr.get_application(session_id, app_id, account_id)
        return JSONResponse(content=app.model_dump(mode="json"))
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.put("/sessions/{session_id}/applications/{app_id}")
async def update_application(
    request: Request,
    session_id: str,
    app_id: str,
    body: UpdateApplicationRequest,
) -> JSONResponse:
    """Update an application."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        app = mgr.update_application(session_id, app_id, updates, account_id)
        return JSONResponse(content=app.model_dump(mode="json"))
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.delete("/sessions/{session_id}/applications/{app_id}")
async def delete_application(request: Request, session_id: str, app_id: str) -> JSONResponse:
    """Delete an application from a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        mgr.delete_application(session_id, app_id, account_id)
        return JSONResponse(content={"status": "deleted", "application_id": app_id})
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# HITL Task Queue endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/tasks")
async def get_task_queue(request: Request, session_id: str) -> JSONResponse:
    """Get the HITL task queue for a session."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    # Verify session access
    try:
        mgr = get_session_manager()
        mgr.get_session(session_id, account_id)
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    task_mgr = get_task_manager()
    try:
        queue = task_mgr.get_or_create_queue(session_id)
        return JSONResponse(content={
            "session_id": session_id,
            "tasks": [t.model_dump(mode="json") for t in queue.tasks],
            "summary": queue.progress_summary(),
        })
    except Exception as exc:
        logger.exception("Failed to get task queue")
        raise _handle_error(exc, "Failed to get task queue") from exc


@router.put("/sessions/{session_id}/tasks/{task_id}")
async def update_task(
    request: Request,
    session_id: str,
    task_id: str,
    body: UpdateTaskRequest,
) -> JSONResponse:
    """Update a HITL task's state."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    # Verify session access
    try:
        mgr = get_session_manager()
        mgr.get_session(session_id, account_id)
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    try:
        task_mgr = get_task_manager()
        task = task_mgr.update_task(
            session_id=session_id,
            task_id=task_id,
            new_state=body.state,
            human_provided_data=body.human_provided_data,
            notes=body.notes,
        )
        return JSONResponse(content=task.model_dump(mode="json"))
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/tasks/{task_id}/dependencies")
async def get_task_dependencies(
    request: Request,
    session_id: str,
    task_id: str,
) -> JSONResponse:
    """Get dependency tasks for a specific task."""
    account_id = _get_account_id(request)
    _validate_id(session_id, "session_id", _SESSION_ID_RE)
    try:
        mgr = get_session_manager()
        mgr.get_session(session_id, account_id)
    except (KeyError, TenantAccessError) as exc:
        status = 404 if isinstance(exc, KeyError) else 403
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    try:
        task_mgr = get_task_manager()
        deps = task_mgr.get_task_dependencies(session_id, task_id)
        return JSONResponse(content={
            "task_id": task_id,
            "dependencies": [t.model_dump(mode="json") for t in deps],
        })
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")


# ---------------------------------------------------------------------------
# Prerequisites endpoints
# ---------------------------------------------------------------------------

@router.get("/prerequisites")
async def get_prerequisites() -> JSONResponse:
    """Get the federal grant prerequisite chain with current status."""
    chain = get_prereq_chain()
    prereqs = chain.list_prerequisites()
    return JSONResponse(content={
        "prerequisites": [p.model_dump(mode="json") for p in prereqs],
        "summary": chain.completion_summary(),
    })


@router.put("/prerequisites/{prereq_id}")
async def update_prerequisite(
    prereq_id: str,
    body: UpdatePrerequisiteRequest,
) -> JSONResponse:
    """Update the status of a prerequisite."""
    _validate_id(prereq_id, "prereq_id", _PREREQ_ID_RE)
    try:
        chain = get_prereq_chain()
        prereq = chain.update_status(prereq_id, body.status, notes=body.notes)
        return JSONResponse(content=prereq.model_dump(mode="json"))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Prerequisite {prereq_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Murphy profile endpoints
# ---------------------------------------------------------------------------

@router.get("/profiles")
async def list_profiles() -> JSONResponse:
    """List all Murphy grant profiles (R&D, Energy, Manufacturing, General)."""
    profiles = get_all_profiles()
    return JSONResponse(content={
        "profiles": [
            {
                "flavor": p.flavor.value,
                "name": p.name,
                "target_grants": p.target_grants,
                "naics_codes": p.naics_codes,
                "keywords": p.keywords,
            }
            for p in profiles
        ],
        "total": len(profiles),
    })


@router.get("/profiles/{flavor}")
async def get_profile_endpoint(flavor: str) -> JSONResponse:
    """Get a specific Murphy grant profile by flavor."""
    _validate_id(flavor, "flavor", _FLAVOR_RE)
    try:
        flavor_enum = GrantFlavor(flavor.lower())
    except ValueError:
        valid = [f.value for f in GrantFlavor]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid flavor {flavor!r}. Valid flavors: {valid}",
        )

    profile = get_profile(flavor_enum)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Profile {flavor!r} not found")

    return JSONResponse(content=profile.model_dump())
