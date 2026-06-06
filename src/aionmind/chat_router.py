"""
Murphy Intelligence Chat + Tool Router — PATCH-065
Copyright 2020 Inoni LLC | License: BSL 1.1

Endpoints:
  POST /api/aionmind/chat          — natural language → AionMind acts with real tools
  POST /api/aionmind/integrate     — give API name+docs URL → connector auto-built
  GET  /api/aionmind/agents        — list all persisted Rosetta agents
  GET  /api/aionmind/memory/{id}   — retrieve agent memory from Rosetta
  POST /api/aionmind/tool/{id}     — directly invoke a registered tool
  GET  /api/aionmind/tools         — list all registered tools
  GET  /api/aionmind/status        — health check

Label: AION-CHAT-001
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aionmind", tags=["murphy"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    # _R443_TENANT_AWARE
    message: str
    agent_id: Optional[str] = "aionmind_default"
    auto_approve: bool = False
    include_memory: bool = True
    actor: Optional[str] = None
    tenant_id: Optional[str] = None
    thread_id: Optional[str] = "default"
    user_id: Optional[str] = None


class IntegrateRequest(BaseModel):
    api_name: str
    docs_url: str
    base_url: str = ""
    auth_type: str = "api_key"
    api_key: Optional[str] = None
    spec_url: Optional[str] = None


class ToolCallRequest(BaseModel):
    kwargs: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Helper: resolve intent → tool calls via LLM
# ---------------------------------------------------------------------------

def _resolve_tool_calls(message: str, memory_context: str, available_tools: List[Dict]) -> List[Dict]:
    """
    Ask LLM to decompose the user message into tool calls.
    Returns list of {tool_id, kwargs, reason}.
    Label: AION-CHAT-002
    """
    try:
        from src.llm_provider import MurphyLLMProvider
        llm = MurphyLLMProvider.from_env()

        # _R420C_TOOL_FILTER: with 1800+ tools, alphabetical first-20 misses everything.
        # Rank tools by keyword overlap with the user message before truncating.
        _msg_words = set(re.findall(r"[a-z]{3,}", message.lower()))
        def _score(t):
            hay = (t.get('tool_id','') + ' ' + t.get('description','') + ' ' + ' '.join(t.get('tags', []))).lower()
            return sum(1 for w in _msg_words if w in hay)
        ranked = sorted(available_tools, key=_score, reverse=True)
        # Always keep the 11 generic tools available (provider check)
        generic = [t for t in available_tools if t.get('provider','') != 'murphy.internal'][:11]
        top_specific = [t for t in ranked if t.get('provider','') == 'murphy.internal' and _score(t) > 0][:25]
        tools_for_prompt = top_specific + generic
        tools_summary = "\n".join(
            f"- {t['tool_id']}: {t['description']} (approval_required={t['requires_approval']})"
            for t in tools_for_prompt
        )

        system = (
            "You are Murphy, the AI operating system. "
            "Given a user message and available tools, decide which tool calls to make. "
            "Respond ONLY with a JSON array of tool calls, each with keys: "
            "{tool_id, kwargs, reason}. "
            "If no tool is needed, return [{'tool_id': 'llm_only', 'kwargs': {}, 'reason': 'LLM response only'}]. "
            "For shell commands: use sys.shell_exec with {cmd: '...'}. "
            "For HTTP: use net.http_get with {url: '...'}. "
            "For file reads: use fs.file_read with {path: '...'}. "
            "NEVER invent tool IDs not in the list."
        )

        prompt = (
            f"Available tools:\n{tools_summary}\n\n"
            f"Recent memory context:\n{memory_context[:2000]}\n\n"
            f"User message: {message}"
        )

        completion = llm.complete(prompt, system=system, max_tokens=800, temperature=0.1)
        content = completion.content.strip()

        # Extract JSON array
        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if match:
            calls = json.loads(match.group(0))
            return calls if isinstance(calls, list) else []
        return []
    except Exception as exc:
        logger.warning("AION-CHAT-002: _resolve_tool_calls failed: %s", exc)
        return []


def _synthesize_response(message: str, tool_results: List[Dict], memory_context: str) -> str:
    """
    Given tool results, synthesize a natural language response.
    Label: AION-CHAT-003
    """
    try:
        from src.llm_provider import MurphyLLMProvider
        llm = MurphyLLMProvider.from_env()

        results_text = json.dumps(tool_results, indent=2, default=str)[:5000]

        system = (
            "You are Murphy, the AI operating system. "
            "You have just executed tool calls on behalf of the user. "
            "Summarize what you did and what you found in clear, concise language. "
            "Be specific — quote key data from tool results. "
            "If something failed, say so clearly and suggest next steps."
        )

        prompt = (
            f"User asked: {message}\n\n"
            f"Tool results:\n{results_text}\n\n"
            f"Provide a clear response."
        )

        completion = llm.complete(prompt, system=system, max_tokens=1000, temperature=0.5)
        return completion.content
    except Exception as exc:
        return f"Tools executed. Results: {json.dumps(tool_results, default=str)[:2000]}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
async def aionmind_status():
    """Health check."""
    try:
        from src.aionmind.tool_executor import _TOOLS_REGISTERED
        from src.aionmind.rosetta_bridge import list_all_agents
        agents = list_all_agents()
        return {
            "ok": True,
            "tools_registered": _TOOLS_REGISTERED,
            "persisted_agents": len(agents),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/tools")
async def list_tools():
    """List all registered tools in UniversalToolRegistry."""
    try:
        from src.aionmind.tool_executor import _get_registry, register_all_tools
        register_all_tools()  # ensure idempotent registration
        registry = _get_registry()
        tools = registry.list_all()
        return {
            "count": len(tools),
            "tools": [
                {
                    "tool_id": t.tool_id,
                    "name": t.name,
                    "description": t.description,
                    "permission_level": t.permission_level,
                    "tags": t.tags,
                    "category": t.category,
                    "requires_approval": t.requires_approval,
                }
                for t in tools
            ],
        }
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/chat")
async def aionmind_chat(req: ChatRequest, request: Request):
    """
    Natural language → AionMind reasons → dispatches real tools → synthesizes response.
    Persists session to Rosetta.
    Label: AION-CHAT-004
    """
    session_id = str(uuid.uuid4())
    tool_results = []

    # _R443_RESOLVE_TENANT
    _r443_tenant_id = req.tenant_id
    _r443_user_id = req.user_id
    _r443_role = "anonymous"
    _r443_org_id = None
    try:
        from src.runtime.app import _r432_resolve_identity as _r443_resolve
        _r443_ident = _r443_resolve(request) or {}
        _r443_tenant_id = _r443_tenant_id or _r443_ident.get("tenant_id") or _r443_ident.get("org_id") or "platform"
        _r443_user_id = _r443_user_id or _r443_ident.get("user_email") or _r443_ident.get("user_id") or "anon"
        _r443_role = _r443_ident.get("role") or "anonymous"
        _r443_org_id = _r443_ident.get("org_id")
    except Exception:
        _r443_tenant_id = _r443_tenant_id or (request.headers.get("X-Tenant-ID") or "platform").strip() or "platform"
        _r443_user_id = _r443_user_id or "anon"
    _r443_thread_id = (req.thread_id or "default").strip() or "default"
    _r443_session_key = f"{_r443_tenant_id}:{_r443_user_id}:{_r443_thread_id}"
    logger.info("AION-CHAT-R443 tenant=%s user=%s thread=%s role=%s",
                _r443_tenant_id, _r443_user_id, _r443_thread_id, _r443_role)


    try:
        # Load agent memory from Rosetta
        memory_context = ""
        if req.include_memory:
            try:
                from src.aionmind.rosetta_bridge import load_agent_memory
                memory = load_agent_memory(req.agent_id, last_n=10)
                if memory:
                    memory_context = "Prior sessions:\n" + json.dumps(memory[:5], default=str)
            except Exception:
                pass

        # Get available tools
        try:
            from src.aionmind.tool_executor import register_all_tools
            register_all_tools()
            from src.aionmind.tool_executor import _get_registry, register_all_tools
            register_all_tools()
            registry = _get_registry()
            available_tools = [
                {
                    "tool_id": t.tool_id,
                    "description": t.description,
                    "requires_approval": t.requires_approval,
                    "tags": list(t.tags),
                    "provider": t.provider,
                }
                for t in registry.list_all()
            ]
        except Exception:
            available_tools = []

        # Resolve tool calls via LLM
        calls = _resolve_tool_calls(req.message, memory_context, available_tools)

        # Execute approved tool calls
        from src.aionmind.tool_executor import dispatch_tool
        for call in calls:
            tool_id = call.get("tool_id", "")
            if tool_id == "llm_only":
                continue

            # Check approval requirement
            tool_def = None
            try:
                from src.aionmind.tool_executor import _get_registry
                tool_def = _get_registry().get(tool_id)
            except Exception:
                pass

            needs_approval = (tool_def and tool_def.requires_approval) if tool_def else False

            if needs_approval and not req.auto_approve:
                tool_results.append({
                    "tool_id": tool_id,
                    "status": "pending_approval",
                    "reason": call.get("reason", ""),
                    "kwargs": call.get("kwargs", {}),
                })
                continue

            # Execute
            try:
                result = dispatch_tool(tool_id, **call.get("kwargs", {}))
                tool_results.append({
                    "tool_id": tool_id,
                    "reason": call.get("reason", ""),
                    "result": result,
                    "status": "executed",
                })
            except Exception as exc:
                tool_results.append({
                    "tool_id": tool_id,
                    "status": "error",
                    "error": str(exc),
                })

        # Synthesize response
        response_text = _synthesize_response(req.message, tool_results, memory_context)

        # Persist to Rosetta
        try:
            from src.aionmind.rosetta_bridge import record_session_to_rosetta
            actor = req.actor or (request.state.user_id if hasattr(request.state, "user_id") else None)
            record_session_to_rosetta(
                agent_id=req.agent_id,
                session_id=session_id,
                raw_input=req.message,
                intent=req.message[:200],
                task_type="chat",
                status="completed",
                result_summary=response_text[:500],
                tool_calls=tool_results,
                actor=actor,
            )
        except Exception as exc:
            logger.debug("Rosetta persist skipped: %s", exc)

        # _R443_PERSIST_CALL
        _r443_tools_used = len([t for t in tool_results if t.get("status") == "executed"])
        try:
            _r443_persist_turn(
                _r443_session_key, _r443_tenant_id, _r443_user_id,
                _r443_thread_id, _r443_role, _r443_org_id,
                req.message, response_text, _r443_tools_used,
            )
        except Exception:
            pass

        return {
            "ok": True,
            "session_id": session_id,
            "agent_id": req.agent_id,
            "response": response_text,
            "tool_calls": tool_results,
            "tools_used": _r443_tools_used,
            # _R443_TENANT_CONTEXT
            "tenant_id": _r443_tenant_id,
            "user_id": _r443_user_id,
            "thread_id": _r443_thread_id,
            "role": _r443_role,
            "session_key": _r443_session_key,
        }

    except Exception as exc:
        logger.error("aionmind_chat error: %s", exc, exc_info=True)
        raise HTTPException(500, detail=str(exc))


@router.post("/integrate")
async def integrate_api(req: IntegrateRequest, request: Request):
    """
    Auto-integrate an external API: fetch docs → generate connector → register tools.
    Label: AION-CHAT-005
    """
    try:
        from src.aionmind.api_integrator import integrate_api as _integrate
        result = _integrate(
            api_name=req.api_name,
            docs_url=req.docs_url,
            base_url=req.base_url,
            auth_type=req.auth_type,
            api_key=req.api_key,
            spec_url=req.spec_url,
        )
        return result
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/agents")
async def list_agents():
    """List all persisted Rosetta agents."""
    try:
        from src.aionmind.rosetta_bridge import list_all_agents
        return {"agents": list_all_agents()}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.get("/memory/{agent_id}")
async def get_agent_memory(agent_id: str, last_n: int = 20):
    """Retrieve recent sessions for an agent from Rosetta."""
    try:
        from src.aionmind.rosetta_bridge import load_agent_memory
        memory = load_agent_memory(agent_id, last_n=last_n)
        return {"agent_id": agent_id, "sessions": memory, "count": len(memory)}
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


@router.post("/tool/{tool_id:path}")
async def invoke_tool(tool_id: str, req: ToolCallRequest, request: Request):
    """Directly invoke a registered tool by ID."""
    try:
        from src.aionmind.tool_executor import dispatch_tool, register_all_tools
        register_all_tools()
        result = dispatch_tool(tool_id, **req.kwargs)
        return result
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))


# _R443_PERSIST — per-tenant session write-through
def _r443_persist_turn(session_key, tenant_id, user_id, thread_id, role, org_id,
                       user_msg, assistant_msg, tools_used):
    """Write one turn to aionmind_chat_sessions. Best-effort — never raises."""
    import sqlite3 as _sq, json as _j, time as _t
    try:
        with _sq.connect("/var/lib/murphy-production/murphy_mind.db", timeout=4) as c:
            row = c.execute(
                "SELECT turns, turn_count, tools_used FROM aionmind_chat_sessions "
                "WHERE tenant_id=? AND user_id=? AND thread_id=?",
                (tenant_id, user_id, thread_id)).fetchone()
            if row:
                turns = _j.loads(row[0])
                turn_count = row[1] + 1
                tools_total = row[2] + int(tools_used or 0)
            else:
                turns = []
                turn_count = 1
                tools_total = int(tools_used or 0)
            turns.append({
                "u": (user_msg or "")[:2000],
                "a": (assistant_msg or "")[:4000],
                "tools": int(tools_used or 0),
                "t": _t.time(),
            })
            turns = turns[-32:]
            c.execute("""
                INSERT INTO aionmind_chat_sessions
                  (tenant_id, user_id, thread_id, turns, role, org_id,
                   updated_at, turn_count, tools_used)
                VALUES (?,?,?,?,?,?, datetime('now'), ?, ?)
                ON CONFLICT(tenant_id, user_id, thread_id) DO UPDATE SET
                  turns=excluded.turns,
                  role=excluded.role,
                  org_id=excluded.org_id,
                  updated_at=excluded.updated_at,
                  turn_count=excluded.turn_count,
                  tools_used=excluded.tools_used
            """, (tenant_id, user_id, thread_id, _j.dumps(turns),
                  role, org_id, turn_count, tools_total))
    except Exception:
        pass
