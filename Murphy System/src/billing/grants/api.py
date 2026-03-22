"""
Grants API — FastAPI router for Phase 2 HITL Agentic Form-Filling System.
© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""
from __future__ import annotations

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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/grants", tags=["grants"])

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

class EligibilityRequest(BaseModel):
    program_ids: List[str]
    project_params: Dict[str, Any] = Field(default_factory=dict)


class CreateSessionRequest(BaseModel):
    tenant_id: str
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CreateApplicationRequest(BaseModel):
    tenant_id: str
    program_id: str
    form_id: str


class FillFormRequest(BaseModel):
    tenant_id: str
    force_refill: bool = False


class StartReviewRequest(BaseModel):
    tenant_id: str
    reviewer_id: str


class SubmitReviewRequest(BaseModel):
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

@router.get("/programs")
def list_all_programs():
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


@router.get("/programs/{program_id}")
def get_single_program(program_id: str):
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


@router.post("/eligibility")
def check_eligibility(request: EligibilityRequest):
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

@router.post("/sessions")
def create_session(request: CreateSessionRequest):
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


@router.get("/sessions/{sid}")
def get_session(sid: str, tenant_id: str = Query(...)):
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


@router.get("/sessions/{sid}/applications")
def list_applications(sid: str, tenant_id: str = Query(...)):
    _validate_session_id(sid)
    _validate_tenant_id(tenant_id)
    apps = _session_manager.list_applications(sid, tenant_id)
    return [_app_to_dict(a) for a in apps]


@router.post("/sessions/{sid}/applications")
def create_application(sid: str, request: CreateApplicationRequest):
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


@router.get("/sessions/{sid}/applications/{aid}")
def get_application(sid: str, aid: str, tenant_id: str = Query(...)):
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
def fill_form(sid: str, aid: str, request: FillFormRequest):
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
def start_review(sid: str, aid: str, request: StartReviewRequest):
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
def submit_review(sid: str, aid: str, request: SubmitReviewRequest):
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

@router.get("/prerequisites")
def get_prerequisites(session_id: str = Query(...), tenant_id: str = Query(...)):
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
