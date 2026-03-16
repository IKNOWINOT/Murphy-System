"""
Time Tracking – REST API
==========================

FastAPI router for time tracking, timesheets, and reports.

All endpoints live under ``/api/time-tracking``.

Copyright 2024 Inoni LLC – BSL-1.1
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover
    APIRouter = None  # type: ignore[assignment,misc]

from .tracker import TimeTracker

logger = logging.getLogger(__name__)

if APIRouter is not None:

    class StartTimerRequest(BaseModel):
        """Start Timer Request."""
        user_id: str
        board_id: str = ""
        item_id: str = ""
        note: str = ""
        billable: bool = True

    class AddEntryRequest(BaseModel):
        """Add Entry Request."""
        user_id: str
        duration_seconds: int
        board_id: str = ""
        item_id: str = ""
        note: str = ""
        started_at: str = ""
        billable: bool = True
        tags: List[str] = Field(default_factory=list)

    class CreateSheetRequest(BaseModel):
        """Create Sheet Request."""
        user_id: str
        period_start: str
        period_end: str
        entry_ids: List[str] = Field(default_factory=list)


def create_time_tracking_router(
    tracker: Optional[TimeTracker] = None,
) -> "APIRouter":
    if APIRouter is None:
        raise RuntimeError("FastAPI is required for the time tracking API")
    if tracker is None:
        tracker = TimeTracker()

    router = APIRouter(prefix="/api/time-tracking", tags=["time-tracking"])

    @router.post("/timer/start")
    async def start_timer(req: StartTimerRequest):
        entry = tracker.start_timer(
            req.user_id, board_id=req.board_id,
            item_id=req.item_id, note=req.note, billable=req.billable,
        )
        return JSONResponse(entry.to_dict(), status_code=201)

    @router.post("/timer/stop/{user_id}")
    async def stop_timer(user_id: str):
        entry = tracker.stop_timer(user_id)
        if entry is None:
            raise HTTPException(404, "No active timer")
        return JSONResponse(entry.to_dict())

    @router.get("/timer/{user_id}")
    async def get_active_timer(user_id: str):
        entry = tracker.get_active_timer(user_id)
        if entry is None:
            raise HTTPException(404, "No active timer")
        return JSONResponse(entry.to_dict())

    @router.post("/entries")
    async def add_entry(req: AddEntryRequest):
        entry = tracker.add_entry(
            req.user_id, req.duration_seconds,
            board_id=req.board_id, item_id=req.item_id,
            note=req.note, started_at=req.started_at,
            billable=req.billable, tags=req.tags,
        )
        return JSONResponse(entry.to_dict(), status_code=201)

    @router.get("/entries")
    async def list_entries(
        user_id: str = Query(""), board_id: str = Query(""),
    ):
        entries = tracker.list_entries(user_id=user_id, board_id=board_id)
        return JSONResponse([e.to_dict() for e in entries])

    @router.delete("/entries/{entry_id}")
    async def delete_entry(entry_id: str):
        if not tracker.delete_entry(entry_id):
            raise HTTPException(404, "Entry not found")
        return JSONResponse({"deleted": True})

    @router.get("/report/total")
    async def total_time(
        user_id: str = Query(""), board_id: str = Query(""),
        billable_only: bool = Query(False),
    ):
        total = tracker.total_time(
            user_id=user_id, board_id=board_id, billable_only=billable_only,
        )
        return JSONResponse({"total_seconds": total})

    @router.get("/report/by-item/{board_id}")
    async def time_by_item(board_id: str):
        result = tracker.time_by_item(board_id)
        return JSONResponse(result)

    @router.post("/timesheets")
    async def create_timesheet(req: CreateSheetRequest):
        sheet = tracker.create_timesheet(
            req.user_id, req.period_start, req.period_end,
            entry_ids=req.entry_ids,
        )
        return JSONResponse(sheet.to_dict(), status_code=201)

    @router.post("/timesheets/{sheet_id}/submit")
    async def submit_timesheet(sheet_id: str):
        try:
            sheet = tracker.submit_timesheet(sheet_id)
            return JSONResponse(sheet.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.post("/timesheets/{sheet_id}/approve")
    async def approve_timesheet(sheet_id: str, approver_id: str = Query("")):
        try:
            sheet = tracker.approve_timesheet(sheet_id, approver_id)
            return JSONResponse(sheet.to_dict())
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @router.get("/timesheets")
    async def list_timesheets(user_id: str = Query("")):
        sheets = tracker.list_timesheets(user_id)
        return JSONResponse([s.to_dict() for s in sheets])

    return router
