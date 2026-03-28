# © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""FastAPI router for the Platform Onboarding module."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
    _HAS_FASTAPI = True

    class StartRequest(BaseModel):
        account_id: str = "default"
        session_data: Dict[str, str] = Field(default_factory=dict)

    class CompleteRequest(BaseModel):
        data: Dict[str, Any] = Field(default_factory=dict)

    class ResumeRequest(BaseModel):
        session_id: str

except ImportError:  # pragma: no cover
    _HAS_FASTAPI = False
    APIRouter = None  # type: ignore[misc,assignment]
    StartRequest = None  # type: ignore[misc,assignment]
    CompleteRequest = None  # type: ignore[misc,assignment]
    ResumeRequest = None  # type: ignore[misc,assignment]

from .onboarding_session import OnboardingSession
from .priority_scorer import PriorityScorer
from .progress_tracker import ProgressTracker
from .task_catalog import TASK_CATALOG
from .wait_state_handler import WaitStateHandler
from .workflow_definition import create_onboarding_workflow

_sessions: Dict[str, OnboardingSession] = {}
_task_map = {t.task_id: t for t in TASK_CATALOG}
_scorer = PriorityScorer()
_wait_handler = WaitStateHandler()
_tracker = ProgressTracker()


def _get_session(session_id: str) -> OnboardingSession:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _sessions[session_id]


def _resolve_session(session_id: str) -> OnboardingSession:
    """Resolve 'default' to first available session, or look up by ID."""
    if session_id == "default":
        if not _sessions:
            raise HTTPException(status_code=404, detail="No active sessions")
        return next(iter(_sessions.values()))
    return _get_session(session_id)


def create_onboarding_router() -> "APIRouter":
    """Factory: create and return the onboarding APIRouter."""
    if not _HAS_FASTAPI:  # pragma: no cover
        raise RuntimeError("FastAPI is not installed")

    router = APIRouter(prefix="/api/onboarding", tags=["Platform Onboarding"])

    # ------------------------------------------------------------------ #
    # Onboarding Workflow                                                   #
    # ------------------------------------------------------------------ #

    @router.post("/start")
    def start_onboarding(body: StartRequest) -> Dict:
        """Start a new platform onboarding workflow session."""
        session = OnboardingSession.create_new(body.account_id)
        session.session_data.update(body.session_data)
        _sessions[session.session_id] = session
        wf = create_onboarding_workflow()
        return {
            "session_id": session.session_id,
            "account_id": session.account_id,
            "workflow_id": wf.workflow_id,
            "total_tasks": len(TASK_CATALOG),
            "status": "started",
        }

    @router.get("/status")
    def get_status(session_id: str = "default") -> Dict:
        """Get the progress dashboard for a session."""
        session = _resolve_session(session_id)
        progress = _tracker.compute_progress(session)
        return {
            "session_id": session.session_id,
            "progress": {
                "total_tasks": progress.total_tasks,
                "completed": progress.completed,
                "in_progress": progress.in_progress,
                "waiting_on_external": progress.waiting_on_external,
                "blocked": progress.blocked,
                "not_started": progress.not_started,
                "completion_percentage": progress.completion_percentage,
                "estimated_remaining_hours": progress.estimated_remaining_hours,
            },
            "next_recommended_tasks": progress.next_recommended_tasks,
        }

    @router.get("/next")
    def get_next_tasks(session_id: str = "default", limit: int = 10) -> Dict:
        """Get priority-sorted list of next recommended tasks."""
        if not _sessions and session_id == "default":
            # No session yet - return global priority ranking
            scored = _scorer.score_tasks(TASK_CATALOG, {})
            return {"tasks": [
                {"task_id": t.task_id, "title": t.title, "score": round(s, 2),
                 "category": t.category, "time_minutes": t.time_estimate_minutes}
                for t, s in scored[:limit]
            ]}
        session = _resolve_session(session_id)
        unblocked = _tracker.get_unblocked_tasks(session)
        scored = _scorer.score_tasks(unblocked, session.session_data)
        return {
            "session_id": session.session_id,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "score": round(s, 2),
                    "category": t.category,
                    "time_minutes": t.time_estimate_minutes,
                    "estimated_value": t.estimated_value,
                }
                for t, s in scored[:limit]
            ],
        }

    @router.get("/tasks")
    def get_all_tasks(session_id: str = "default") -> Dict:
        """Get all tasks with their current status."""
        if not _sessions and session_id == "default":
            return {
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "title": t.title,
                        "section": t.section,
                        "status": "not_started",
                        "category": t.category,
                        "task_type": t.task_type,
                        "time_minutes": t.time_estimate_minutes,
                        "depends_on": t.depends_on,
                    }
                    for t in TASK_CATALOG
                ],
                "total": len(TASK_CATALOG),
            }
        session = _resolve_session(session_id)
        return {
            "session_id": session.session_id,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "section": t.section,
                    "status": session.get_task_state(t.task_id),
                    "category": t.category,
                    "task_type": t.task_type,
                    "time_minutes": t.time_estimate_minutes,
                    "depends_on": t.depends_on,
                }
                for t in TASK_CATALOG
            ],
            "total": len(TASK_CATALOG),
        }

    @router.get("/tasks/{task_id}")
    def get_task_detail(task_id: str, session_id: str = "default") -> Dict:
        """Get task details, dependencies, and current status."""
        task = _task_map.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        status = "not_started"
        if _sessions:
            s = _resolve_session(session_id)
            status = s.get_task_state(task_id)
        return {
            "task_id": task.task_id,
            "title": task.title,
            "section": task.section,
            "description": task.description,
            "why": task.why,
            "url": task.target_url,
            "task_type": task.task_type,
            "hitl_level": task.hitl_level,
            "category": task.category,
            "value_type": task.value_type,
            "estimated_value": task.estimated_value,
            "time_estimate_minutes": task.time_estimate_minutes,
            "depends_on": task.depends_on,
            "blocks": task.blocks,
            "external_wait_days": task.external_wait_days,
            "is_conditional": task.is_conditional,
            "condition": task.condition,
            "recurrence": task.recurrence,
            "status": status,
        }

    # ------------------------------------------------------------------ #
    # Task Execution                                                         #
    # ------------------------------------------------------------------ #

    @router.post("/tasks/{task_id}/start")
    def start_task(task_id: str, session_id: str = "default") -> Dict:
        """Mark a task as in-progress."""
        task = _task_map.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        session = _resolve_session(session_id)
        session.set_task_state(task_id, "in_progress")
        from .url_launcher import URLLauncher
        ctx = URLLauncher().launch(task)
        return {"task_id": task_id, "status": "in_progress", "navigation": ctx}

    @router.post("/tasks/{task_id}/complete")
    def complete_task(task_id: str, body: CompleteRequest, session_id: str = "default") -> Dict:
        """Mark a task as completed."""
        task = _task_map.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        session = _resolve_session(session_id)
        session.set_task_state(task_id, "completed", body.data or None)
        newly_unblocked = _wait_handler.cascade_unlock(task_id, session)
        return {
            "task_id": task_id,
            "status": "completed",
            "newly_unblocked": newly_unblocked,
        }

    @router.post("/tasks/{task_id}/skip")
    def skip_task(task_id: str, session_id: str = "default") -> Dict:
        """Skip a task."""
        if not _task_map.get(task_id):
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        session = _resolve_session(session_id)
        session.set_task_state(task_id, "skipped")
        return {"task_id": task_id, "status": "skipped"}

    @router.post("/tasks/{task_id}/wait")
    def wait_task(task_id: str, session_id: str = "default") -> Dict:
        """Mark a task as waiting on external."""
        if not _task_map.get(task_id):
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        session = _resolve_session(session_id)
        expected = _wait_handler.mark_waiting(task_id, session)
        return {
            "task_id": task_id,
            "status": "waiting_on_external",
            "expected_completion": expected.isoformat(),
        }

    # ------------------------------------------------------------------ #
    # Session Management                                                    #
    # ------------------------------------------------------------------ #

    @router.get("/checkpoint")
    def save_checkpoint(session_id: str = "default") -> Dict:
        """Save and return a session checkpoint."""
        session = _resolve_session(session_id)
        checkpoint = session.to_dict()
        session.checkpoint = checkpoint
        return {"session_id": session.session_id, "checkpoint": checkpoint}

    @router.post("/resume")
    def resume_session(body: ResumeRequest) -> Dict:
        """Resume a session from checkpoint."""
        session = _get_session(body.session_id)
        progress = _tracker.compute_progress(session)
        return {
            "session_id": session.session_id,
            "resumed": True,
            "progress": {
                "completed": progress.completed,
                "total_tasks": progress.total_tasks,
                "completion_percentage": progress.completion_percentage,
            },
        }

    @router.get("/parallel-groups")
    def get_parallel_groups() -> Dict:
        """Get tasks grouped by dependency level for parallel execution."""
        groups = _tracker.get_parallel_groups()
        return {
            "groups": {
                str(level): task_ids
                for level, task_ids in sorted(groups.items())
            },
            "total_levels": len(groups),
        }

    @router.get("/critical-path")
    def get_critical_path() -> Dict:
        """Get the critical dependency path."""
        path = _tracker.get_critical_path()
        tasks = [
            {"task_id": tid, "title": _task_map[tid].title}
            for tid in path
            if tid in _task_map
        ]
        return {"critical_path": path, "tasks": tasks}

    # ------------------------------------------------------------------ #
    # Analytics                                                             #
    # ------------------------------------------------------------------ #

    @router.get("/value-report")
    def get_value_report(session_id: str = "default") -> Dict:
        """Return total estimated value captured and pending."""
        session = None
        if _sessions:
            try:
                session = _resolve_session(session_id)
            except (KeyError, ValueError):
                pass
        tasks_with_value = [t for t in TASK_CATALOG if t.estimated_value]
        completed_ids: set = set()
        if session:
            completed_ids = {
                tid for tid, state in session.task_states.items()
                if state == "completed"
            }
        captured = [t for t in tasks_with_value if t.task_id in completed_ids]
        pending = [t for t in tasks_with_value if t.task_id not in completed_ids]
        return {
            "captured": [
                {"task_id": t.task_id, "title": t.title, "value": t.estimated_value}
                for t in captured
            ],
            "pending": [
                {"task_id": t.task_id, "title": t.title, "value": t.estimated_value}
                for t in pending
            ],
            "total_tasks_with_value": len(tasks_with_value),
            "captured_count": len(captured),
            "pending_count": len(pending),
        }

    @router.get("/timeline")
    def get_timeline(session_id: str = "default") -> Dict:
        """Return projected completion timeline."""
        session = None
        if _sessions:
            try:
                session = _resolve_session(session_id)
            except (KeyError, ValueError):
                pass
        total_remaining_minutes = sum(
            t.time_estimate_minutes
            for t in TASK_CATALOG
            if not session or session.get_task_state(t.task_id) not in ("completed", "skipped")
        )
        return {
            "total_remaining_minutes": total_remaining_minutes,
            "total_remaining_hours": round(total_remaining_minutes / 60, 1),
            "total_remaining_days_at_8h": round(total_remaining_minutes / 480, 1),
            "critical_path": _tracker.get_critical_path(),
        }

    return router
