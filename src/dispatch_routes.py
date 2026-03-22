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
            from src.dispatch import dispatcher, ToolCall
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
            from src.dispatch import dispatcher, ToolCall
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

    return router
