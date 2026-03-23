# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.billing.grants.submission.models import SubmissionStatus
from src.billing.grants.submission.submission_manager import SubmissionManager
from src.billing.grants.submission.submission_tracker import SubmissionTracker
from src.billing.grants.notifications.deadline_alerts import DeadlineAlertSystem

router = APIRouter(prefix="/api/grants", tags=["grants"])

_manager = SubmissionManager()
_tracker = SubmissionTracker()
_alert_system = DeadlineAlertSystem()

# In-memory deadlines store — populated by grant discovery/import flows (demo placeholder)
_deadlines: List[Dict] = []


class GenerateRequest(BaseModel):
    portal: str
    application_data: Optional[Dict[str, Any]] = None


class MarkSubmittedRequest(BaseModel):
    confirmation_number: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = ""


def _package_to_dict(pkg) -> dict:
    d = asdict(pkg)
    for key in ("created_at", "submitted_at"):
        if d.get(key):
            d[key] = d[key].isoformat() if isinstance(d[key], datetime) else d[key]
    return d


def _status_to_dict(s: SubmissionStatus) -> dict:
    d = asdict(s)
    for key in ("submitted_at", "last_checked"):
        if d.get(key):
            d[key] = d[key].isoformat() if isinstance(d[key], datetime) else d[key]
    for change in d.get("history", []):
        if change.get("changed_at"):
            change["changed_at"] = change["changed_at"].isoformat() if isinstance(change["changed_at"], datetime) else change["changed_at"]
    return d


@router.post("/sessions/{sid}/applications/{aid}/submission/generate")
def generate_submission(sid: str, aid: str, body: GenerateRequest):
    pkg = _manager.generate_package(
        session_id=sid,
        application_id=aid,
        portal=body.portal,
        application_data=body.application_data or {},
    )
    _tracker.create(pkg.package_id, pkg.portal, initial_status="generated")
    return {"package_id": pkg.package_id, **_package_to_dict(pkg)}


@router.get("/sessions/{sid}/applications/{aid}/submission")
def get_submission(sid: str, aid: str):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    return _package_to_dict(pkg)


@router.get("/sessions/{sid}/applications/{aid}/submission/files")
def get_submission_files(sid: str, aid: str):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    return {"files": [asdict(f) for f in pkg.files]}


@router.get("/sessions/{sid}/applications/{aid}/submission/files/{fid}/download")
def download_submission_file(sid: str, aid: str, fid: str):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    file = next((f for f in pkg.files if f.file_id == fid), None)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "file_id": file.file_id,
        "filename": file.filename,
        "content": f"[Placeholder content for {file.filename}]",
        "content_type": file.content_type,
    }


@router.post("/sessions/{sid}/applications/{aid}/submission/mark-submitted")
def mark_submitted(sid: str, aid: str, body: MarkSubmittedRequest):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    pkg.status = "submitted"
    pkg.submitted_at = datetime.utcnow()
    if body.confirmation_number:
        pkg.confirmation_number = body.confirmation_number
    _tracker.mark_submitted(pkg.package_id, body.confirmation_number)
    return {"status": "submitted", "package_id": pkg.package_id, "confirmation_number": pkg.confirmation_number}


@router.put("/sessions/{sid}/applications/{aid}/submission/status")
def update_submission_status(sid: str, aid: str, body: UpdateStatusRequest):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    pkg.status = body.status
    sub_status = _tracker.update_status(pkg.package_id, body.status, body.notes or "")
    if not sub_status:
        sub_status = _tracker.create(pkg.package_id, pkg.portal, body.status)
    return _status_to_dict(sub_status)


@router.get("/sessions/{sid}/applications/{aid}/submission/status")
def get_submission_status(sid: str, aid: str):
    pkg = _manager.get_package(sid, aid)
    if not pkg:
        raise HTTPException(status_code=404, detail="Submission package not found")
    sub_status = _tracker.get(pkg.package_id)
    if not sub_status:
        sub_status = _tracker.create(pkg.package_id, pkg.portal, pkg.status)
    return _status_to_dict(sub_status)


@router.get("/deadlines")
def get_deadlines():
    return {"deadlines": _deadlines}


@router.get("/deadlines/alerts")
def get_deadline_alerts():
    """Return active (non-dismissed) deadline alerts.

    Checks _deadlines against ALERT_THRESHOLDS_DAYS (30/14/7/3/1 days) and
    returns all alerts that have not been dismissed. Each deadline dict must
    contain ``grant_id``, ``title``, and ``deadline`` (ISO string or datetime).
    """
    _alert_system.check_deadlines(_deadlines)
    active = _alert_system.get_active_alerts()
    return {
        "alerts": [
            {**asdict(a), "deadline": a.deadline.isoformat(), "created_at": a.created_at.isoformat()}
            for a in active
        ]
    }


@router.put("/deadlines/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: str):
    alert = _alert_system.dismiss_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"alert_id": alert_id, "dismissed": True}


@router.post("/sessions/{sid}/applications/{aid}/submission/auto-submit")
def auto_submit(sid: str, aid: str):
    """Phase B placeholder for direct portal API submission.

    Automated end-to-end submission (filling forms, uploading files, and
    receiving confirmation numbers via portal APIs) is planned for Phase B.
    Until then, callers should follow the manual submission instructions
    returned by the generate endpoint.
    """
    return {
        "status": "not_yet_available",
        "message": "Automated submission is planned for Phase B. Please follow the manual submission instructions.",
        "manual_instructions_url": f"/api/grants/sessions/{sid}/applications/{aid}/submission",
    }

# ===========================================================================
# Grants API - Phase 2 HITL Agentic Form-Filling System
# ===========================================================================
"""
Grants API - FastAPI router for Phase 2 HITL Agentic Form-Filling System.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""

import logging
import re
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.billing.grants.eligibility_engine import EligibilityEngine
from src.billing.grants.form_filler.agent import FormFillerAgent
from src.billing.grants.form_filler.form_definitions import FORM_REGISTRY, get_form, list_forms
from src.billing.grants.form_filler.output_generators import JSONExporter, PDFGenerator, XMLGenerator
from src.billing.grants.form_filler.review_session import ReviewSessionManager
from src.billing.grants.grant_database import get_program, list_programs
from src.billing.grants.hitl_task_queue import HITLTaskQueue
from src.billing.grants.murphy_profiles import MurphyProfileManager
from src.billing.grants.prerequisites_tracker import PrerequisitesTracker
from src.billing.grants.session_manager import GrantSessionManager

# ===========================================================================
# Extended Grant API (Full endpoint catalog)
# ===========================================================================
"""
Grant API - FastAPI router for all grant system endpoints.

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

# NOTE: router already defined at module top - using the same router instance
# router = APIRouter(prefix="/api/grants", tags=["grants"])

# Singletons — module-level so they are shared across requests
_session_manager = GrantSessionManager()
_eligibility_engine = EligibilityEngine()
_task_queue = HITLTaskQueue()
_prereqs_tracker = PrerequisitesTracker()
_profile_manager = MurphyProfileManager()
_review_manager = ReviewSessionManager()
_agent = FormFillerAgent(_session_manager, _profile_manager, _task_queue)

# --- Validation patterns ---
_SESSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_TENANT_RE = re.compile(r"^[a-zA-Z0-9_-]{1,200}$")
_PROGRAM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")

_EXPORT_GENERATORS = {
    "json": JSONExporter(),
    "xml": XMLGenerator(),
    "pdf": PDFGenerator(),
}


def _validate_session_id(sid: str) -> str:
    if not sid or not _SESSION_RE.match(sid):
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    return sid


def _validate_tenant_id(tid: str) -> str:
    if not tid or not _TENANT_RE.match(tid):
        raise HTTPException(status_code=400, detail="Invalid tenant_id format")
    return tid


def _validate_program_id(pid: str) -> str:
    if not pid or not _PROGRAM_RE.match(pid):
        raise HTTPException(status_code=400, detail="Invalid program_id format")
    return pid


def _validate_application_id(aid: str) -> str:
    if not aid or not _SESSION_RE.match(aid):
        raise HTTPException(status_code=400, detail="Invalid application_id format")
    return aid


# --- Request/Response Models ---

class EligibilityCheckRequestLegacy(BaseModel):
    """Legacy model for Phase 2 HITL eligibility checks."""
    program_ids: List[str]
    project_params: Dict[str, Any] = Field(default_factory=dict)


class CreateSessionRequestLegacy(BaseModel):
    """Legacy model for HITL form-filling system (Phase 2). Uses explicit tenant_id."""
    tenant_id: str
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateApplicationRequestLegacy(BaseModel):
    """Legacy model for HITL form-filling system (Phase 2)."""
    tenant_id: str
    program_id: str
    form_id: str


class FillFormRequestLegacy(BaseModel):
    """Legacy model for HITL form-filling system (Phase 2)."""
    tenant_id: str
    force_refill: bool = False


class StartReviewRequestLegacy(BaseModel):
    """Legacy model for HITL form-filling system (Phase 2)."""
    tenant_id: str
    reviewer_id: str


class SubmitReviewRequestLegacy(BaseModel):
    """Legacy model for HITL form-filling system (Phase 2)."""
    tenant_id: str
    reviewer_id: str
    action: str  # "approve" or "reject"
    notes: str = ""


class EditFieldRequest(BaseModel):
    tenant_id: str
    reviewer_id: str
    new_value: Any


class ExportRequest(BaseModel):
    tenant_id: str
    format: str = "json"


class CompletePrereqRequest(BaseModel):
    session_id: str
    tenant_id: str


# --- Program endpoints ---

# DISABLED: Duplicate route - use main API
# @router.get("/programs")
def _legacy_list_all_programs():
    programs = list_programs()
    return [
        {
            "program_id": p.program_id,
            "name": p.name,
            "agency": p.agency,
            "description": p.description,
            "max_award_usd": p.max_award_usd,
            "eligibility_requirements": p.eligibility_requirements,
            "naics_codes": p.naics_codes,
            "form_ids": p.form_ids,
            "prerequisites": p.prerequisites,
            "url": p.url,
            "active": p.active,
        }
        for p in programs
    ]


# DISABLED: Duplicate route - use main API
# @router.get("/programs/{program_id}")
def _legacy_get_single_program(program_id: str):
    _validate_program_id(program_id)
    prog = get_program(program_id)
    if prog is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return {
        "program_id": prog.program_id,
        "name": prog.name,
        "agency": prog.agency,
        "description": prog.description,
        "max_award_usd": prog.max_award_usd,
        "eligibility_requirements": prog.eligibility_requirements,
        "naics_codes": prog.naics_codes,
        "form_ids": prog.form_ids,
        "prerequisites": prog.prerequisites,
        "url": prog.url,
        "active": prog.active,
    }


# DISABLED: Duplicate route - use main API
# @router.post("/eligibility")
def _legacy_check_eligibility(request: EligibilityCheckRequestLegacy):
    results = _eligibility_engine.check_multiple(request.program_ids, request.project_params)
    return [
        {
            "program_id": r.program_id,
            "eligible": r.eligible,
            "score": r.score,
            "missing_requirements": r.missing_requirements,
            "met_requirements": r.met_requirements,
            "recommendations": r.recommendations,
        }
        for r in results
    ]


# --- Session endpoints ---

# DISABLED: Duplicate route - use main API
# @router.post("/sessions")
def _legacy_create_session_phase2(request: CreateSessionRequestLegacy):
    _validate_tenant_id(request.tenant_id)
    session = _session_manager.create_session(
        request.tenant_id, request.name, request.metadata
    )
    # Initialize prerequisites for this session
    _prereqs_tracker.initialize_for_session(session.session_id)
    return {
        "session_id": session.session_id,
        "tenant_id": session.tenant_id,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "metadata": session.metadata,
    }


# DISABLED: Duplicate route - use main API
# @router.get("/sessions/{sid}")
def _legacy_get_session_phase2(sid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_tenant_id(tenant_id)
    session = _session_manager.get_session(sid, tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "tenant_id": session.tenant_id,
        "name": session.name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "metadata": session.metadata,
    }


# DISABLED: Duplicate route - use main API
# @router.get("/sessions/{sid}/applications")
def _legacy_list_applications_phase2(sid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_tenant_id(tenant_id)
    apps = _session_manager.list_applications(sid, tenant_id)
    return [_app_to_dict(a) for a in apps]


# DISABLED: Duplicate route - use main API
# @router.post("/sessions/{sid}/applications")
def _legacy_create_application_phase2(sid: str, request: CreateApplicationRequestLegacy):
    _validate_session_id(sid)
    _validate_tenant_id(request.tenant_id)
    _validate_program_id(request.program_id)
    _validate_program_id(request.form_id)
    try:
        app = _session_manager.create_application(
            sid, request.tenant_id, request.program_id, request.form_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _app_to_dict(app)


# DISABLED: Duplicate route - use main API
# @router.get("/sessions/{sid}/applications/{aid}")
def _legacy_get_application_phase2(sid: str, aid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(tenant_id)
    app = _session_manager.get_application(aid, sid, tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _app_to_dict(app)


# --- Form endpoints ---

@router.get("/forms")
def list_all_forms():
    return [_form_def_summary(fd.get_definition()) for fd in list_forms()]


@router.get("/forms/{form_id}")
def get_form_definition(form_id: str):
    _validate_program_id(form_id)
    fd = get_form(form_id)
    if fd is None:
        raise HTTPException(status_code=404, detail="Form not found")
    defn = fd.get_definition()
    return defn.model_dump()


# --- Fill endpoints ---

@router.post("/sessions/{sid}/applications/{aid}/fill")
def fill_form(sid: str, aid: str, request: FillFormRequestLegacy):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(request.tenant_id)

    app = _session_manager.get_application(aid, sid, request.tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    form_obj = get_form(app.form_id)
    if form_obj is None:
        raise HTTPException(status_code=404, detail=f"Form definition '{app.form_id}' not found")

    form_def = form_obj.get_definition()
    filled_fields = _agent.fill_form(sid, request.tenant_id, aid, form_def)

    # Create or update review session
    existing = _review_manager.get_review_for_application(aid)
    if existing is None or request.force_refill:
        _review_manager.create_review(sid, aid, app.form_id, filled_fields)

    return [ff.model_dump() for ff in filled_fields]


@router.get("/sessions/{sid}/applications/{aid}/fields")
def get_filled_fields(sid: str, aid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(tenant_id)

    app = _session_manager.get_application(aid, sid, tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    review = _review_manager.get_review_for_application(aid)
    if review is None:
        return []
    return [ff.model_dump() for ff in review.filled_fields]


# --- Review endpoints ---

@router.post("/sessions/{sid}/applications/{aid}/review")
def start_review(sid: str, aid: str, request: StartReviewRequestLegacy):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(request.tenant_id)

    app = _session_manager.get_application(aid, sid, request.tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    review = _review_manager.get_review_for_application(aid)
    if review is None:
        raise HTTPException(status_code=404, detail="No review session — call /fill first")

    updated = _review_manager.start_review(review.review_id, request.reviewer_id)
    return _review_summary(updated)


@router.get("/sessions/{sid}/applications/{aid}/review")
def get_review_status(sid: str, aid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(tenant_id)

    app = _session_manager.get_application(aid, sid, tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    review = _review_manager.get_review_for_application(aid)
    if review is None:
        raise HTTPException(status_code=404, detail="No review session — call /fill first")

    summary = _review_manager.get_review_summary(review.review_id)
    return {**_review_summary(review), "field_counts": summary}


@router.put("/sessions/{sid}/applications/{aid}/review")
def submit_review(sid: str, aid: str, request: SubmitReviewRequestLegacy):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(request.tenant_id)

    if request.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    app = _session_manager.get_application(aid, sid, request.tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    review = _review_manager.get_review_for_application(aid)
    if review is None:
        raise HTTPException(status_code=404, detail="No review session")

    if request.action == "approve":
        updated = _review_manager.approve_review(review.review_id, request.reviewer_id, request.notes)
        _session_manager.update_application(aid, sid, request.tenant_id, {"status": "approved"})
    else:
        updated = _review_manager.reject_review(review.review_id, request.reviewer_id, request.notes)

    return _review_summary(updated)


@router.put("/sessions/{sid}/applications/{aid}/fields/{fid}")
def edit_field(sid: str, aid: str, fid: str, request: EditFieldRequest):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(request.tenant_id)
    _validate_program_id(fid)

    app = _session_manager.get_application(aid, sid, request.tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    result = _agent.update_field(sid, request.tenant_id, aid, fid, request.new_value, request.reviewer_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to update field")

    review = _review_manager.get_review_for_application(aid)
    if review:
        _review_manager.edit_field(review.review_id, fid, request.new_value, request.reviewer_id)

    return result.model_dump()


# --- Export endpoints ---

@router.post("/sessions/{sid}/applications/{aid}/export")
def generate_export(sid: str, aid: str, request: ExportRequest):
    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(request.tenant_id)

    fmt = request.format.lower()
    if fmt not in _EXPORT_GENERATORS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Choose from: {list(_EXPORT_GENERATORS)}")

    app = _session_manager.get_application(aid, sid, request.tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    form_obj = get_form(app.form_id)
    if form_obj is None:
        raise HTTPException(status_code=404, detail="Form definition not found")

    review = _review_manager.get_review_for_application(aid)
    filled_fields = review.filled_fields if review else []

    return {"status": "ready", "format": fmt, "application_id": aid, "session_id": sid}


@router.get("/sessions/{sid}/applications/{aid}/export/{fmt}")
def download_export(sid: str, aid: str, fmt: str, tenant_id: str = Query(...)):
    from fastapi.responses import Response

    _validate_session_id(sid)
    _validate_application_id(aid)
    _validate_tenant_id(tenant_id)

    fmt = fmt.lower()
    generator = _EXPORT_GENERATORS.get(fmt)
    if generator is None:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}")

    app = _session_manager.get_application(aid, sid, tenant_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")

    form_obj = get_form(app.form_id)
    if form_obj is None:
        raise HTTPException(status_code=404, detail="Form definition not found")

    review = _review_manager.get_review_for_application(aid)
    filled_fields = review.filled_fields if review else []

    form_def = form_obj.get_definition()
    content = generator.generate(
        form_def,
        filled_fields,
        {"session_id": sid, "application_id": aid, "tenant_id": tenant_id},
    )

    return Response(
        content=content,
        media_type=generator.get_content_type(),
        headers={
            "Content-Disposition": (
                f"attachment; filename={app.form_id}.{generator.get_file_extension()}"
            )
        },
    )


# --- Prerequisites endpoints ---

# DISABLED: Duplicate route - use main API
# @router.get("/prerequisites")
def _legacy_get_prerequisites_session(session_id: str = Query(...), tenant_id: str = Query(...)):
    _validate_session_id(session_id)
    _validate_tenant_id(tenant_id)

    session = _session_manager.get_session(session_id, tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    prereqs = _prereqs_tracker.get_prerequisites(session_id)
    return {
        pid: {
            "prereq_id": p.prereq_id,
            "name": p.name,
            "description": p.description,
            "instructions": p.instructions,
            "url": p.url,
            "estimated_days": p.estimated_days,
            "completed": p.completed,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "depends_on": p.depends_on,
        }
        for pid, p in prereqs.items()
    }


@router.post("/prerequisites/{prereq_id}/complete")
def mark_prereq_complete(prereq_id: str, request: CompletePrereqRequest):
    _validate_program_id(prereq_id)
    _validate_session_id(request.session_id)
    _validate_tenant_id(request.tenant_id)

    session = _session_manager.get_session(request.session_id, request.tenant_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    prereq = _prereqs_tracker.mark_complete(request.session_id, prereq_id)
    if prereq is None:
        raise HTTPException(status_code=404, detail=f"Prerequisite '{prereq_id}' not found")

    return {
        "prereq_id": prereq.prereq_id,
        "name": prereq.name,
        "completed": prereq.completed,
        "completed_at": prereq.completed_at.isoformat() if prereq.completed_at else None,
    }


# --- Helpers ---

def _app_to_dict(app) -> Dict[str, Any]:
    return {
        "application_id": app.application_id,
        "session_id": app.session_id,
        "program_id": app.program_id,
        "form_id": app.form_id,
        "status": app.status,
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
    }


def _review_summary(review) -> Dict[str, Any]:
    if review is None:
        return {}
    return {
        "review_id": review.review_id,
        "session_id": review.session_id,
        "application_id": review.application_id,
        "form_id": review.form_id,
        "status": review.status,
        "reviewer_id": review.reviewer_id,
        "created_at": review.created_at.isoformat(),
        "approved_at": review.approved_at.isoformat() if review.approved_at else None,
        "review_notes": review.review_notes,
    }


def _form_def_summary(defn) -> Dict[str, Any]:
    return {
        "form_id": defn.form_id,
        "form_name": defn.form_name,
        "grant_program_id": defn.grant_program_id,
        "version": defn.version,
        "submission_format": defn.submission_format,
        "field_count": len(defn.fields),
        "section_count": len(defn.sections),
    }
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
