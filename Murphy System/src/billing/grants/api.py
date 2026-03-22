"""Grants and financing API router for Murphy System.

Exposes the grants catalog, session management, HITL task queue,
prerequisites, and eligibility matching as FastAPI routes.

Endpoints:
  POST   /api/grants/sessions                              — create session
  GET    /api/grants/sessions/{session_id}                 — get session
  DELETE /api/grants/sessions/{session_id}                 — delete session
  POST   /api/grants/sessions/{session_id}/match           — run eligibility match
  GET    /api/grants/sessions/{session_id}/results         — get match results (stored in profile)
  GET    /api/grants/sessions/{session_id}/tasks           — list all tasks
  GET    /api/grants/sessions/{session_id}/tasks/next      — get next unblocked tasks
  POST   /api/grants/sessions/{session_id}/tasks/{task_id}/complete — complete a task
  GET    /api/grants/prerequisites                         — get prerequisite chain
  POST   /api/grants/prerequisites/{prereq_id}/status      — update prereq status
  GET    /api/grants/catalog                               — list all grants
  GET    /api/grants/catalog/{grant_id}                    — get grant by ID
  GET    /api/grants/profiles/murphy                       — get Murphy profiles
  GET    /api/grants/health                                — health check
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.billing.grants import engine, prerequisites, sessions, task_queue
from src.billing.grants.database import get_all_grants, get_grant_by_id
from src.billing.grants.models import GrantTrack, PrereqStatus, TaskType
from src.billing.grants.murphy_profiles import get_murphy_profiles

logger = logging.getLogger(__name__)

# Session and tenant IDs must be alphanumeric + hyphens/underscores, 1-200 chars (CWE-20)
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")
_TENANT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")
_PREREQ_ID_RE = re.compile(r"^[a-zA-Z0-9_]{1,100}$")
_TASK_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")


def _validate_session_id(session_id: str) -> str:
    """Validate session_id format or raise HTTPException."""
    if not session_id or not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    return session_id


def _validate_tenant_id(tenant_id: str) -> str:
    """Validate tenant_id format or raise HTTPException."""
    if not tenant_id or not _TENANT_ID_RE.match(tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id format.")
    return tenant_id


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    track: str = Field("track_b_customer", description="track_a_murphy or track_b_customer")


class MatchRequest(BaseModel):
    profile_data: Dict[str, Any] = Field(default_factory=dict, description="Applicant profile")


class CompleteTaskRequest(BaseModel):
    result_data: Dict[str, Any] = Field(default_factory=dict, description="Task result data")


class UpdatePrereqRequest(BaseModel):
    status: str = Field(..., description="New prerequisite status")


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def create_grants_router() -> APIRouter:
    """Create and return the grants APIRouter."""
    router = APIRouter(prefix="/api/grants", tags=["grants"])

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    @router.post("/sessions")
    async def create_session(body: CreateSessionRequest) -> JSONResponse:
        """Create a new grants session for a tenant."""
        tenant_id = _validate_tenant_id(body.tenant_id)
        try:
            track = GrantTrack(body.track)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid track '{body.track}'. Must be track_a_murphy or track_b_customer.",
            )
        session = sessions.create_session(tenant_id=tenant_id, track=track)
        return JSONResponse({"session": session.model_dump(mode="json")}, status_code=201)

    @router.get("/sessions/{session_id}")
    async def get_session(
        session_id: str,
        tenant_id: Optional[str] = Query(None, description="Tenant ID for ownership validation"),
    ) -> JSONResponse:
        """Retrieve a session by ID."""
        _validate_session_id(session_id)
        validated_tenant = _validate_tenant_id(tenant_id) if tenant_id else None
        session = sessions.get_session(session_id, tenant_id=validated_tenant)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return JSONResponse({"session": session.model_dump(mode="json")})

    @router.delete("/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        tenant_id: Optional[str] = Query(None),
    ) -> JSONResponse:
        """Destroy a session."""
        _validate_session_id(session_id)
        validated_tenant = _validate_tenant_id(tenant_id) if tenant_id else None
        try:
            destroyed = sessions.destroy_session(session_id, tenant_id=validated_tenant)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        if not destroyed:
            raise HTTPException(status_code=404, detail="Session not found.")
        return JSONResponse({"deleted": True, "session_id": session_id})

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    @router.post("/sessions/{session_id}/match")
    async def run_match(
        session_id: str,
        body: MatchRequest,
        tenant_id: Optional[str] = Query(None),
    ) -> JSONResponse:
        """Run eligibility matching for a session's profile."""
        _validate_session_id(session_id)
        validated_tenant = _validate_tenant_id(tenant_id) if tenant_id else None
        session = sessions.get_session(session_id, tenant_id=validated_tenant)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        profile = {**session.profile_data, **body.profile_data}
        results = engine.match_grants(profile)

        # Store results summary in session
        try:
            sessions.update_session(
                session_id,
                {"last_match_results": [r.model_dump() for r in results[:20]]},
                tenant_id=validated_tenant,
            )
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc))

        eligible = [r for r in results if r.eligible]
        return JSONResponse({
            "session_id": session_id,
            "total_evaluated": len(results),
            "eligible_count": len(eligible),
            "results": [r.model_dump() for r in results],
        })

    @router.get("/sessions/{session_id}/results")
    async def get_results(
        session_id: str,
        tenant_id: Optional[str] = Query(None),
    ) -> JSONResponse:
        """Get previously stored match results for a session."""
        _validate_session_id(session_id)
        validated_tenant = _validate_tenant_id(tenant_id) if tenant_id else None
        session = sessions.get_session(session_id, tenant_id=validated_tenant)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        stored = session.profile_data.get("last_match_results", [])
        return JSONResponse({"session_id": session_id, "results": stored})

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @router.get("/sessions/{session_id}/tasks")
    async def list_tasks(session_id: str) -> JSONResponse:
        """List all HITL tasks for a session."""
        _validate_session_id(session_id)
        tasks = task_queue.get_all_tasks(session_id)
        return JSONResponse({
            "session_id": session_id,
            "tasks": [t.model_dump() for t in tasks],
            "progress": task_queue.get_progress(session_id),
        })

    @router.get("/sessions/{session_id}/tasks/next")
    async def get_next_tasks(session_id: str) -> JSONResponse:
        """Get the next unblocked pending tasks for a session."""
        _validate_session_id(session_id)
        tasks = task_queue.get_next_tasks(session_id)
        return JSONResponse({
            "session_id": session_id,
            "next_tasks": [t.model_dump() for t in tasks],
        })

    @router.post("/sessions/{session_id}/tasks/{task_id}/complete")
    async def complete_task(
        session_id: str,
        task_id: str,
        body: CompleteTaskRequest,
    ) -> JSONResponse:
        """Mark a HITL task as completed."""
        _validate_session_id(session_id)
        if not task_id or not _TASK_ID_RE.match(task_id):
            raise HTTPException(status_code=400, detail="Invalid task_id format.")
        task = task_queue.complete_task(session_id, task_id, result_data=body.result_data)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return JSONResponse({
            "task": task.model_dump(),
            "progress": task_queue.get_progress(session_id),
        })

    # ------------------------------------------------------------------
    # Prerequisites
    # ------------------------------------------------------------------

    @router.get("/prerequisites")
    async def list_prerequisites(
        session_id: Optional[str] = Query(None, description="Session ID for status context"),
    ) -> JSONResponse:
        """Return the prerequisite chain with optional session-specific status."""
        chain = prerequisites.get_prerequisite_chain()
        if session_id:
            _validate_session_id(session_id)
            summary = prerequisites.get_session_prereq_summary(session_id)
            return JSONResponse({"prerequisites": chain_to_dict(chain), "summary": summary})
        return JSONResponse({"prerequisites": chain_to_dict(chain)})

    @router.post("/prerequisites/{prereq_id}/status")
    async def update_prereq_status(
        prereq_id: str,
        body: UpdatePrereqRequest,
        session_id: Optional[str] = Query(None),
    ) -> JSONResponse:
        """Update the status of a prerequisite for a session."""
        if not prereq_id or not _PREREQ_ID_RE.match(prereq_id):
            raise HTTPException(status_code=400, detail="Invalid prereq_id format.")
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id query param required.")
        _validate_session_id(session_id)

        try:
            status_enum = PrereqStatus(body.status)
        except ValueError:
            valid = [s.value for s in PrereqStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{body.status}'. Valid values: {valid}",
            )
        try:
            prereq = prerequisites.update_prerequisite_status(session_id, prereq_id, status_enum)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

        return JSONResponse({
            "prereq_id": prereq_id,
            "status": body.status,
            "summary": prerequisites.get_session_prereq_summary(session_id),
        })

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    @router.get("/catalog")
    async def list_catalog(
        program_type: Optional[str] = Query(None, description="Filter by program_type"),
        state: Optional[str] = Query(None, description="Filter by eligible state (2-letter)"),
    ) -> JSONResponse:
        """Return all grants in the catalog with optional filters."""
        grants = get_all_grants()
        if program_type:
            grants = [g for g in grants if g.program_type.value == program_type]
        if state:
            state_upper = state.upper()
            grants = [
                g for g in grants
                if not g.eligible_states or state_upper in [s.upper() for s in g.eligible_states]
            ]
        return JSONResponse({
            "count": len(grants),
            "grants": [g.model_dump() for g in grants],
        })

    @router.get("/catalog/{grant_id}")
    async def get_catalog_grant(grant_id: str) -> JSONResponse:
        """Return a single grant by ID."""
        grant = get_grant_by_id(grant_id)
        if grant is None:
            raise HTTPException(status_code=404, detail=f"Grant '{grant_id}' not found.")
        return JSONResponse({"grant": grant.model_dump()})

    # ------------------------------------------------------------------
    # Murphy profiles
    # ------------------------------------------------------------------

    @router.get("/profiles/murphy")
    async def get_murphy_profiles_endpoint() -> JSONResponse:
        """Return all Murphy System Track A grant profiles."""
        profiles = get_murphy_profiles()
        return JSONResponse({"profiles": profiles})

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @router.get("/health")
    async def health() -> JSONResponse:
        """Return health status for the grants module."""
        grants = get_all_grants()
        return JSONResponse({
            "status": "ok",
            "module": "grants",
            "catalog_size": len(grants),
        })

    return router


def chain_to_dict(chain: list) -> list:
    """Serialize a list of Prerequisite models to dicts."""
    return [p.model_dump() for p in chain]
