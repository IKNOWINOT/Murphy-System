# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Dispatch Routes — FastAPI Router for Dispatch Tool-Calling Engine

Endpoints:
- GET  /api/dispatch/tools       — List all tools (filter by ?category=)
- POST /api/dispatch/call        — Execute one tool call
- POST /api/dispatch/batch       — Execute multiple tool calls
- POST /api/dispatch/llm         — Parse OpenAI tool_calls array and dispatch
- GET  /api/dispatch/log         — Get recent dispatch log entries
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ToolCallRequest(BaseModel):
    tool_name: str
    args: dict
    caller_id: Optional[str] = "system"
    caller_type: Optional[str] = "agent"


class BatchCallRequest(BaseModel):
    calls: List[ToolCallRequest]


class LLMCallRequest(BaseModel):
    tool_calls: list
    caller_id: Optional[str] = "llm"


# ---------------------------------------------------------------------------
# Router Factory
# ---------------------------------------------------------------------------


def create_dispatch_router() -> APIRouter:
    """Create and return the dispatch router."""
    router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])

    @router.get("/tools")
    def list_tools(category: Optional[str] = Query(None)):
        """List all registered tools, optionally filtered by category."""
        try:
            from src.dispatch import _registry
            tools = _registry.list_tools(category=category)
            return JSONResponse(content={"tools": tools, "count": len(tools)})
        except Exception as exc:
            logger.exception("Failed to list tools")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to list tools", "detail": str(exc)},
            )

    @router.post("/call")
    def call_tool(req: ToolCallRequest):
        """Execute a single tool call."""
        try:
            from src.dispatch import ToolCall, dispatcher
            tc = ToolCall(
                tool_name=req.tool_name,
                args=req.args,
                caller_id=req.caller_id,
                caller_type=req.caller_type,
            )
            result = dispatcher.call(tc)
            return JSONResponse(
                content={
                    "ok": result.ok,
                    "data": result.data,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                    "tool_name": result.tool_name,
                    "call_id": result.call_id,
                }
            )
        except Exception as exc:
            logger.exception("Failed to call tool")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to call tool", "detail": str(exc)},
            )

    @router.post("/batch")
    def batch_call(req: BatchCallRequest):
        """Execute multiple tool calls sequentially."""
        try:
            from src.dispatch import ToolCall, dispatcher
            calls = [
                ToolCall(
                    tool_name=tc.tool_name,
                    args=tc.args,
                    caller_id=tc.caller_id,
                    caller_type=tc.caller_type,
                )
                for tc in req.calls
            ]
            results = dispatcher.batch(calls)
            return JSONResponse(
                content={
                    "results": [
                        {
                            "ok": r.ok,
                            "data": r.data,
                            "error": r.error,
                            "duration_ms": r.duration_ms,
                            "tool_name": r.tool_name,
                            "call_id": r.call_id,
                        }
                        for r in results
                    ]
                }
            )
        except Exception as exc:
            logger.exception("Failed to batch call")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to batch call", "detail": str(exc)},
            )

    @router.post("/llm")
    def llm_call(req: LLMCallRequest):
        """Parse OpenAI tool_calls array and dispatch each one."""
        try:
            from src.dispatch import dispatcher
            llm_resp = {"tool_calls": req.tool_calls}
            results = dispatcher.call_from_llm_response(llm_resp, caller_id=req.caller_id)
            return JSONResponse(
                content={
                    "results": [
                        {
                            "ok": r.ok,
                            "data": r.data,
                            "error": r.error,
                            "duration_ms": r.duration_ms,
                            "tool_name": r.tool_name,
                            "call_id": r.call_id,
                        }
                        for r in results
                    ]
                }
            )
        except Exception as exc:
            logger.exception("Failed to call from LLM response")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to call from LLM response", "detail": str(exc)},
            )

    @router.get("/log")
    def get_log(limit: int = Query(50, ge=1, le=500)):
        """Get recent dispatch log entries."""
        try:
            from src.dispatch import dispatcher
            entries = dispatcher.get_log(limit=limit)
            return JSONResponse(content={"log": entries, "count": len(entries)})
        except Exception as exc:
            logger.exception("Failed to fetch dispatch log")
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to fetch dispatch log", "detail": str(exc)},
            )

    # ── Natural Language / Voice activation ──────────────────────────────────

    @router.post("/nl")
    async def dispatch_nl(body: dict):
        """
        Activate Dispatch via natural language.
        Body: {text: str, caller_id?: str, caller_type?: str}

        Parses the text into a ToolCall and dispatches it.  If the intent
        cannot be parsed, returns {ok: false, error: "..."}. If the tool
        requires approval, returns the pending approval record instead.
        """
        text = body.get("text", "").strip()
        if not text:
            return JSONResponse(status_code=400, content={"ok": False, "error": "text is required"})
        from src.dispatch import dispatcher, parse_natural_language
        caller_id = body.get("caller_id", "human")
        caller_type = body.get("caller_type", "human")
        tc = parse_natural_language(text, caller_id=caller_id)
        if tc is None:
            return JSONResponse(content={"ok": False, "parsed": False, "error": "Could not parse intent from text"})
        tc.caller_type = caller_type
        result = dispatcher.call(tc)
        return JSONResponse(content={
            "ok": result.ok,
            "parsed": True,
            "tool_name": result.tool_name,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "call_id": result.call_id,
        })

    @router.post("/voice")
    async def dispatch_voice(body: dict):
        """
        Activate Dispatch via voice transcript.
        Body: {transcript: str, caller_id?: str}

        Treats the transcript as natural language and dispatches accordingly.
        """
        transcript = body.get("transcript", "").strip()
        if not transcript:
            return JSONResponse(status_code=400, content={"ok": False, "error": "transcript is required"})
        # Re-use the NL endpoint logic
        return await dispatch_nl({"text": transcript, "caller_id": body.get("caller_id", "voice"), "caller_type": "human"})

    # ── HITL Approval Queue ───────────────────────────────────────────────────

    @router.get("/approvals")
    def list_approvals(tier: str = Query(None)):
        """
        List pending HITL approvals.
        Optional ?tier=platform|user|customer to filter.

        Three-tier model:
          platform  — Murphy platform auto-reviews (MSS/gate check required)
          user      — the account owner must approve
          customer  — the account owner's external customer must approve
        """
        from src.dispatch import approval_store
        pending = approval_store.list_pending(tier=tier)
        return JSONResponse(content={"ok": True, "approvals": pending, "count": len(pending)})

    @router.post("/approvals/{call_id}/approve")
    async def approve_tool_call(call_id: str, body: dict):
        """
        Approve a pending tool call and execute it immediately.
        Body: {approved_by?: str}
        """
        from src.dispatch import ToolCall, approval_store, dispatcher
        approved_by = body.get("approved_by", "user")
        tc = approval_store.approve(call_id, approved_by=approved_by)
        if tc is None:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Pending approval not found"})
        # Execute the tool directly (bypass approval check — it was already approved)
        result = dispatcher._execute(tc)
        return JSONResponse(content={
            "ok": result.ok,
            "tool_name": result.tool_name,
            "data": result.data,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "approved_by": approved_by,
        })

    @router.post("/approvals/{call_id}/reject")
    async def reject_tool_call(call_id: str, body: dict):
        """
        Reject a pending tool call.
        Body: {rejected_by?: str, reason?: str}
        """
        from src.dispatch import approval_store
        rejected_by = body.get("rejected_by", "user")
        reason = body.get("reason", "Rejected by user")
        ok = approval_store.reject(call_id, rejected_by=rejected_by, reason=reason)
        if not ok:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Pending approval not found"})
        return JSONResponse(content={"ok": True, "call_id": call_id, "status": "rejected", "reason": reason})

    # ── MultiCursor workspace snapshot ───────────────────────────────────────

    @router.post("/cursor")
    async def take_cursor_snapshot(body: dict):
        """
        Take a multi-domain workspace snapshot (MultiCursor).
        Body: {domains?: list[str], user?: str}

        Returns a cursor_id and per-domain state snapshot.  Use this before
        complex agentic tasks — analogous to playwright-browser_snapshot.

        Available domains: im, meetings, calls, email, ambient, shadow,
                           automation, moderator, system, approvals
        """
        from src.dispatch import cursor_context
        domains = body.get("domains") or None
        user = body.get("user") or None
        snapshot = cursor_context.snapshot(domains=domains, user=user)
        formatted = cursor_context.format_for_agent(snapshot)
        return JSONResponse(content={
            "ok": True,
            "cursor_id": snapshot.get("cursor_id"),
            "snapshot": snapshot,
            "agent_summary": formatted,
        })

    return router
