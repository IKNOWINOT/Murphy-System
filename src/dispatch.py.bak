# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Dispatch — Unified Tool-Calling Engine for Murphy System

Provides a central registry and dispatcher for all tool-based actions across
the system. Tools are categorized (comms, meetings, shadow, avatar, ambient, system)
and can be called by agents, LLMs, or humans. All calls are logged to the DB.

Features:
- Thread-safe tool registration
- Built-in tools for comms hub, meetings, shadow agents, avatars, and ambient context
- LLM tool-call parsing (OpenAI format)
- Batch execution
- Persistent audit log in DB (graceful fallback if unavailable)
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema object
    handler: Callable
    category: str  # comms, meetings, shadow, avatar, ambient, system
    requires_approval: bool = False


@dataclass
class ToolCall:
    tool_name: str
    args: dict
    caller_id: str = "system"
    caller_type: str = "agent"  # agent|llm|human|shadow|avatar|ambient|meeting
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class ToolResult:
    ok: bool
    data: Any
    error: Optional[str]
    duration_ms: int
    tool_name: str
    call_id: str


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Thread-safe registry for all tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._lock = threading.Lock()

    def register(self, tool: Tool):
        """Add a tool to the registry."""
        with self._lock:
            self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (category=%s)", tool.name, tool.category)

    def unregister(self, name: str):
        """Remove a tool from the registry."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.debug("Unregistered tool: %s", name)

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        with self._lock:
            return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[dict]:
        """List all tools as JSON-schema-like dicts for LLM consumption."""
        with self._lock:
            tools = list(self._tools.values())
        
        if category:
            tools = [t for t in tools if t.category == category]
        
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "category": t.category,
                "requires_approval": t.requires_approval,
            }
            for t in tools
        ]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class Dispatcher:
    """Executes tool calls, times them, and persists logs."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    def call(self, tc: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        tool = self._registry.get(tc.tool_name)
        if not tool:
            return ToolResult(
                ok=False,
                data=None,
                error=f"Tool not found: {tc.tool_name}",
                duration_ms=0,
                tool_name=tc.tool_name,
                call_id=tc.call_id,
            )

        start = time.time()
        try:
            data = tool.handler(tc.args)
            duration_ms = int((time.time() - start) * 1000)
            result = ToolResult(
                ok=True,
                data=data,
                error=None,
                duration_ms=duration_ms,
                tool_name=tc.tool_name,
                call_id=tc.call_id,
            )
        except Exception as exc:
            duration_ms = int((time.time() - start) * 1000)
            logger.exception("Tool call failed: %s", tc.tool_name)
            result = ToolResult(
                ok=False,
                data=None,
                error=str(exc),
                duration_ms=duration_ms,
                tool_name=tc.tool_name,
                call_id=tc.call_id,
            )

        self._persist(tc, result, duration_ms)
        return result

    def call_fn(self, tool_name: str, args: dict, caller_id: str = "system", caller_type: str = "agent") -> ToolResult:
        """Convenience wrapper for calling a tool by name."""
        tc = ToolCall(tool_name=tool_name, args=args, caller_id=caller_id, caller_type=caller_type)
        return self.call(tc)

    def batch(self, calls: List[ToolCall]) -> List[ToolResult]:
        """Execute multiple tool calls sequentially."""
        return [self.call(tc) for tc in calls]

    def call_from_llm_response(self, llm_resp: dict, caller_id: str = "llm") -> List[ToolResult]:
        """Parse OpenAI tool_calls array from LLM response and dispatch each one."""
        tool_calls = llm_resp.get("tool_calls", [])
        results = []
        for tc_dict in tool_calls:
            func = tc_dict.get("function", {})
            tool_name = func.get("name", "")
            args = func.get("arguments", {})
            if isinstance(args, str):
                import json
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            tc = ToolCall(tool_name=tool_name, args=args, caller_id=caller_id, caller_type="llm")
            results.append(self.call(tc))
        return results

    def get_log(self, limit: int = 50) -> List[dict]:
        """Get recent dispatch log entries from DB."""
        try:
            from src.db import _get_session_factory, DispatchLog
            factory = _get_session_factory()
            session = factory()
            try:
                entries = session.query(DispatchLog).order_by(DispatchLog.timestamp.desc()).limit(limit).all()
                return [
                    {
                        "id": e.id,
                        "tool_name": e.tool_name,
                        "caller_id": e.caller_id,
                        "caller_type": e.caller_type,
                        "args": e.args,
                        "result_ok": bool(e.result_ok),
                        "result_data": e.result_data,
                        "error": e.error,
                        "duration_ms": e.duration_ms,
                        "timestamp": e.timestamp,
                    }
                    for e in entries
                ]
            finally:
                session.close()
        except Exception as exc:
            logger.debug("Could not fetch dispatch log: %s", exc)
            return []

    def _persist(self, tc: ToolCall, result: ToolResult, duration_ms: int):
        """Persist a tool call to the dispatch_log table (graceful no-op if unavailable)."""
        try:
            from datetime import datetime, timezone
            from src.db import _get_session_factory, DispatchLog
            
            factory = _get_session_factory()
            session = factory()
            try:
                log_entry = DispatchLog(
                    id=tc.call_id,
                    tool_name=tc.tool_name,
                    caller_id=tc.caller_id,
                    caller_type=tc.caller_type,
                    args=tc.args,
                    result_ok=1 if result.ok else 0,
                    result_data=result.data if result.ok else None,
                    error=result.error,
                    duration_ms=duration_ms,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                session.add(log_entry)
                session.commit()
            finally:
                session.close()
        except Exception as exc:
            logger.debug("Could not persist dispatch log: %s", exc)


# ---------------------------------------------------------------------------
# Built-in Tool Handlers
# ---------------------------------------------------------------------------


def _handle_send_im(args):
    from src.communication_hub import im_store
    thread_id = args["thread_id"]
    sender = args["sender"]
    content = args["content"]
    return im_store.post_message(thread_id, sender, content)


def _handle_create_thread(args):
    from src.communication_hub import im_store
    participants = args["participants"]
    name = args.get("name", "")
    thread_type = args.get("type", "group")
    return im_store.create_thread(participants, name=name, thread_type=thread_type)


def _handle_send_email(args):
    from src.communication_hub import email_store
    sender = args["sender"]
    recipients = args["recipients"]
    subject = args["subject"]
    body = args["body"]
    priority = args.get("priority", "normal")
    return email_store.compose_and_send(sender, recipients, subject, body, priority=priority)


def _handle_start_voice_call(args):
    from src.communication_hub import call_store
    caller = args["caller"]
    participants = args["participants"]
    return call_store.create_session("voice", caller, participants)


def _handle_start_video_call(args):
    from src.communication_hub import call_store
    caller = args["caller"]
    participants = args["participants"]
    return call_store.create_session("video", caller, participants)


def _handle_broadcast(args):
    from src.communication_hub import mod_console
    message = args["message"]
    platforms = args.get("platforms", ["im", "email"])
    sender = args.get("sender", "system")
    priority = args.get("priority", "normal")
    return mod_console.broadcast(message, platforms=platforms, sender=sender, priority=priority)


def _handle_meeting_start(args):
    from src.ai_comms_orchestrator import meetings_bridge
    title = args["title"]
    participants = args["participants"]
    account_id = args.get("account_id")
    return meetings_bridge.start_meeting(title, participants, account_id=account_id)


def _handle_meeting_end(args):
    from src.ai_comms_orchestrator import meetings_bridge
    session_id = args["session_id"]
    return meetings_bridge.end_meeting(session_id)


def _handle_meeting_add_transcript(args):
    from src.ai_comms_orchestrator import meetings_bridge
    session_id = args["session_id"]
    speaker = args["speaker"]
    text = args["text"]
    is_ai = args.get("is_ai", False)
    return meetings_bridge.add_transcript_entry(session_id, speaker, text, is_ai=is_ai)


def _handle_meeting_shadow_suggest(args):
    from src.ai_comms_orchestrator import meetings_bridge
    session_id = args["session_id"]
    agent_id = args["agent_id"]
    suggestion_type = args["suggestion_type"]
    content = args["content"]
    return meetings_bridge.shadow_suggest(session_id, agent_id, suggestion_type, content)


def _handle_shadow_observe(args):
    from src.ai_comms_orchestrator import shadow_comms
    agent_id = args["agent_id"]
    action_type = args["action_type"]
    action_data = args["action_data"]
    primary_account = args.get("primary_account")
    cc_accounts = args.get("cc_accounts", [])
    observation = {"action_type": action_type, "action_data": action_data}
    return shadow_comms.route_observation(agent_id, observation, primary_account, cc_accounts=cc_accounts)


def _handle_shadow_propose(args):
    from src.ai_comms_orchestrator import shadow_comms
    agent_id = args["agent_id"]
    pattern = args.get("pattern", {})
    primary_account = args.get("primary_account")
    cc_accounts = args.get("cc_accounts", [])
    proposal = {"pattern": pattern}
    return shadow_comms.route_proposal(agent_id, proposal, primary_account, cc_accounts=cc_accounts)


def _handle_shadow_clarify(args):
    from src.ai_comms_orchestrator import shadow_comms
    agent_id = args["agent_id"]
    context = args.get("context", {})
    primary_account = args.get("primary_account")
    cc_accounts = args.get("cc_accounts", [])
    question = {"context": context}
    return shadow_comms.route_question(agent_id, question, primary_account, cc_accounts=cc_accounts)


def _handle_avatar_speak(args):
    from src.ai_comms_orchestrator import avatar_comms
    avatar_id = args["avatar_id"]
    user_id = args["user_id"]
    content = args["content"]
    channel = args.get("channel", "im")
    shadow_agent_id = args.get("shadow_agent_id")
    org_node_id = args.get("org_node_id")
    return avatar_comms.speak_as_avatar(avatar_id, user_id, content, channel=channel,
                                       shadow_agent_id=shadow_agent_id, org_node_id=org_node_id)


def _handle_ambient_signal(args):
    from src.ambient_context_store import AmbientContextStore
    store = AmbientContextStore()
    signals = args["signals"]
    return {"count": store.push(signals)}


def _handle_ambient_deliver(args):
    from src.ai_comms_orchestrator import ambient_bridge
    return ambient_bridge.deliver(args)


def _handle_system_health(args):
    from src.db import check_database
    return {"status": "ok", "db": check_database()}


# ---------------------------------------------------------------------------
# Process-wide Singleton
# ---------------------------------------------------------------------------


_registry = ToolRegistry()
_dispatcher = Dispatcher(_registry)
dispatcher = _dispatcher


def register_tool(tool: Tool):
    """Module-level convenience function for registering a tool."""
    _registry.register(tool)


def dispatch(tool_name: str, args: dict, caller_id: str = "system", caller_type: str = "agent") -> ToolResult:
    """Module-level convenience function for dispatching a tool call."""
    return _dispatcher.call_fn(tool_name, args, caller_id, caller_type)


# ---------------------------------------------------------------------------
# Register Built-in Tools
# ---------------------------------------------------------------------------


def _register_builtin_tools():
    """Register all built-in tools."""
    
    # Category: comms
    register_tool(Tool(
        name="comms.send_im",
        description="Send an IM message to a thread",
        parameters={
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "sender": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["thread_id", "sender", "content"],
        },
        handler=_handle_send_im,
        category="comms",
    ))
    
    register_tool(Tool(
        name="comms.create_thread",
        description="Create a new IM thread",
        parameters={
            "type": "object",
            "properties": {
                "participants": {"type": "array", "items": {"type": "string"}},
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["direct", "group"]},
            },
            "required": ["participants"],
        },
        handler=_handle_create_thread,
        category="comms",
    ))
    
    register_tool(Tool(
        name="comms.send_email",
        description="Send an email",
        parameters={
            "type": "object",
            "properties": {
                "sender": {"type": "string"},
                "recipients": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"]},
            },
            "required": ["sender", "recipients", "subject", "body"],
        },
        handler=_handle_send_email,
        category="comms",
    ))
    
    register_tool(Tool(
        name="comms.start_voice_call",
        description="Start a voice call session",
        parameters={
            "type": "object",
            "properties": {
                "caller": {"type": "string"},
                "participants": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["caller", "participants"],
        },
        handler=_handle_start_voice_call,
        category="comms",
    ))
    
    register_tool(Tool(
        name="comms.start_video_call",
        description="Start a video call session",
        parameters={
            "type": "object",
            "properties": {
                "caller": {"type": "string"},
                "participants": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["caller", "participants"],
        },
        handler=_handle_start_video_call,
        category="comms",
    ))
    
    register_tool(Tool(
        name="comms.broadcast",
        description="Broadcast a message to multiple platforms",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "platforms": {"type": "array", "items": {"type": "string"}},
                "sender": {"type": "string"},
                "priority": {"type": "string"},
            },
            "required": ["message"],
        },
        handler=_handle_broadcast,
        category="comms",
    ))
    
    # Category: meetings
    register_tool(Tool(
        name="meeting.start",
        description="Start a new meeting session",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "participants": {"type": "array", "items": {"type": "string"}},
                "account_id": {"type": "string"},
            },
            "required": ["title", "participants"],
        },
        handler=_handle_meeting_start,
        category="meetings",
    ))
    
    register_tool(Tool(
        name="meeting.end",
        description="End a meeting session",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
            },
            "required": ["session_id"],
        },
        handler=_handle_meeting_end,
        category="meetings",
    ))
    
    register_tool(Tool(
        name="meeting.add_transcript",
        description="Add a transcript entry to a meeting",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "speaker": {"type": "string"},
                "text": {"type": "string"},
                "is_ai": {"type": "boolean"},
            },
            "required": ["session_id", "speaker", "text"],
        },
        handler=_handle_meeting_add_transcript,
        category="meetings",
    ))
    
    register_tool(Tool(
        name="meeting.shadow_suggest",
        description="Shadow agent suggests something during a meeting",
        parameters={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "agent_id": {"type": "string"},
                "suggestion_type": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["session_id", "agent_id", "suggestion_type", "content"],
        },
        handler=_handle_meeting_shadow_suggest,
        category="meetings",
    ))
    
    # Category: shadow
    register_tool(Tool(
        name="shadow.observe",
        description="Shadow agent observes an action",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "action_type": {"type": "string"},
                "action_data": {"type": "object"},
                "primary_account": {"type": "string"},
                "cc_accounts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id", "action_type", "action_data"],
        },
        handler=_handle_shadow_observe,
        category="shadow",
    ))
    
    register_tool(Tool(
        name="shadow.propose",
        description="Shadow agent proposes an automation",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "pattern": {"type": "object"},
                "primary_account": {"type": "string"},
                "cc_accounts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id"],
        },
        handler=_handle_shadow_propose,
        category="shadow",
        requires_approval=True,
    ))
    
    register_tool(Tool(
        name="shadow.clarify",
        description="Shadow agent asks a clarifying question",
        parameters={
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "context": {"type": "object"},
                "primary_account": {"type": "string"},
                "cc_accounts": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id"],
        },
        handler=_handle_shadow_clarify,
        category="shadow",
    ))
    
    # Category: avatar
    register_tool(Tool(
        name="avatar.speak",
        description="Avatar speaks to a user",
        parameters={
            "type": "object",
            "properties": {
                "avatar_id": {"type": "string"},
                "user_id": {"type": "string"},
                "content": {"type": "string"},
                "channel": {"type": "string", "enum": ["im", "email", "both"]},
                "shadow_agent_id": {"type": "string"},
                "org_node_id": {"type": "string"},
            },
            "required": ["avatar_id", "user_id", "content"],
        },
        handler=_handle_avatar_speak,
        category="avatar",
    ))
    
    # Category: ambient
    register_tool(Tool(
        name="ambient.signal",
        description="Store ambient context signals",
        parameters={
            "type": "object",
            "properties": {
                "signals": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["signals"],
        },
        handler=_handle_ambient_signal,
        category="ambient",
    ))
    
    register_tool(Tool(
        name="ambient.deliver",
        description="Deliver an ambient insight to the user",
        parameters={
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "content": {"type": "string"},
                "recipient": {"type": "string"},
                "subject": {"type": "string"},
            },
            "required": ["content"],
        },
        handler=_handle_ambient_deliver,
        category="ambient",
    ))
    
    # Category: system
    register_tool(Tool(
        name="system.health",
        description="Check system health",
        parameters={
            "type": "object",
            "properties": {},
        },
        handler=_handle_system_health,
        category="system",
    ))


_register_builtin_tools()
