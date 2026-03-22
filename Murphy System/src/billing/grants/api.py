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
