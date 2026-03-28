# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Dispatch — Unified Tool-Calling Engine for Murphy System

Enhanced with HITL approval tiers, natural language parsing, and MultiCursor snapshots.
"""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable
    category: str
    requires_approval: bool = False
    approval_tier: str = "none"  # none|platform|user|customer

@dataclass
class ToolCall:
    tool_name: str
    args: dict
    caller_id: str = "system"
    caller_type: str = "agent"
    call_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

@dataclass
class ToolResult:
    ok: bool
    data: Any
    error: Optional[str]
    duration_ms: int
    tool_name: str
    call_id: str

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._lock = threading.Lock()

    def register(self, tool: Tool):
        with self._lock:
            self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def unregister(self, name: str):
        with self._lock:
            if name in self._tools:
                del self._tools[name]

    def get(self, name: str) -> Optional[Tool]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[dict]:
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
                "approval_tier": t.approval_tier,
            }
            for t in tools
        ]

class PendingApprovalStore:
    def __init__(self):
        self._pending: Dict[str, dict] = {}
        self._lock = threading.Lock()

    def queue(self, tc: ToolCall, tier: str) -> dict:
        rec = {
            "call_id": tc.call_id,
            "tool_name": tc.tool_name,
            "caller_id": tc.caller_id,
            "caller_type": tc.caller_type,
            "args": tc.args,
            "approval_tier": tier,
            "status": "pending",
            "created_at": _now_iso(),
        }
        with self._lock:
            self._pending[tc.call_id] = rec

        try:
            from src.db import PendingApproval, get_session
            sess = get_session()
            pa = PendingApproval(
                id=uuid.uuid4().hex[:12],
                call_id=tc.call_id,
                tool_name=tc.tool_name,
                caller_id=tc.caller_id,
                caller_type=tc.caller_type,
                args=tc.args,
                approval_tier=tier,
                status="pending",
                created_at=rec["created_at"],
            )
            sess.add(pa)
            sess.commit()
            sess.close()
        except Exception as e:
            logger.debug("DB write failed (in-memory fallback): %s", e)

        return rec

    def approve(self, call_id: str, approved_by: str = "user") -> Optional[ToolCall]:
        with self._lock:
            rec = self._pending.get(call_id)
            if not rec or rec["status"] != "pending":
                return None
            rec["status"] = "approved"
            rec["approved_by"] = approved_by
            rec["decided_at"] = _now_iso()

        try:
            from src.db import PendingApproval, get_session
            sess = get_session()
            pa = sess.query(PendingApproval).filter_by(call_id=call_id, status="pending").first()
            if pa:
                pa.status = "approved"
                pa.approved_by = approved_by
                pa.decided_at = rec["decided_at"]
                sess.commit()
            sess.close()
        except Exception:
            pass

        return ToolCall(
            tool_name=rec["tool_name"],
            args=rec["args"],
            caller_id=rec["caller_id"],
            caller_type=rec["caller_type"],
            call_id=call_id,
        )

    def reject(self, call_id: str, rejected_by: str = "user", reason: str = "") -> bool:
        with self._lock:
            rec = self._pending.get(call_id)
            if not rec or rec["status"] != "pending":
                return False
            rec["status"] = "rejected"
            rec["approved_by"] = rejected_by
            rec["rejection_reason"] = reason
            rec["decided_at"] = _now_iso()

        try:
            from src.db import PendingApproval, get_session
            sess = get_session()
            pa = sess.query(PendingApproval).filter_by(call_id=call_id, status="pending").first()
            if pa:
                pa.status = "rejected"
                pa.approved_by = rejected_by
                pa.rejection_reason = reason
                pa.decided_at = rec["decided_at"]
                sess.commit()
            sess.close()
        except Exception:
            pass

        return True

    def list_pending(self, tier: str = None) -> List[dict]:
        with self._lock:
            pending = [r for r in self._pending.values() if r["status"] == "pending"]
        if tier:
            pending = [r for r in pending if r["approval_tier"] == tier]
        return pending

    def get(self, call_id: str) -> Optional[dict]:
        with self._lock:
            return self._pending.get(call_id)

class MultiCursorContext:
    DOMAINS = ["im", "meetings", "calls", "email", "ambient",
               "shadow", "automation", "moderator", "system", "approvals"]

    def snapshot(self, domains: List[str] = None, user: str = None) -> dict:
        if domains is None:
            domains = self.DOMAINS

        cursor_id = uuid.uuid4().hex[:12]
        snap = {"cursor_id": cursor_id, "timestamp": _now_iso(), "domains": {}}

        for domain in domains:
            try:
                snap["domains"][domain] = self._snapshot_domain(domain, user)
            except Exception as e:
                snap["domains"][domain] = {"error": str(e)}

        return snap

    def _snapshot_domain(self, domain: str, user: str) -> dict:
        if domain == "im":
            from src.communication_hub import im_store
            threads = im_store.list_threads(user=user) if user else im_store.list_threads()
            return {"threads": len(threads), "total": len(threads)}
        elif domain == "meetings":
            from src.meetings_bridge import MeetingsBridge
            mb = MeetingsBridge()
            meetings = mb.list_meetings()
            return {"meetings": len(meetings)}
        elif domain == "calls":
            from src.communication_hub import call_store
            sessions = call_store.list_sessions()
            active = [s for s in sessions if s.get("state") in ["ringing", "active", "on_hold"]]
            return {"active_calls": len(active)}
        elif domain == "email":
            from src.communication_hub import email_store
            inbox = email_store.get_inbox(user) if user else []
            return {"count": len(inbox)}
        elif domain == "ambient":
            from src.ambient_context_store import AmbientContextStore
            acs = AmbientContextStore()
            recent = acs.get_recent(limit=5)
            stats = acs.get_stats()
            return {"recent": len(recent), "stats": stats}
        elif domain == "shadow":
            from src.shadow_agent_integration import ShadowAgentIntegration
            sai = ShadowAgentIntegration()
            return sai.get_status()
        elif domain == "automation":
            from src.communication_hub import automate_store
            rules = automate_store.list_rules()
            return {"rules": len(rules)}
        elif domain == "moderator":
            from src.communication_hub import mod_console
            users = mod_console.list_users()
            history = mod_console.get_broadcast_history(limit=3)
            return {"users": len(users), "broadcasts": len(history)}
        elif domain == "system":
            from src.db import check_database
            db_ok = check_database()
            return {
                "db": "ok" if db_ok else "error",
                "tools_registered": len(_registry._tools),
                "pending_approvals": len(_approval_store.list_pending()),
            }
        elif domain == "approvals":
            return {"pending": _approval_store.list_pending()}
        return {}

    def format_for_agent(self, snapshot: dict) -> str:
        lines = [f"MultiCursor Snapshot {snapshot['cursor_id']} @ {snapshot['timestamp']}", ""]
        for domain, data in snapshot.get("domains", {}).items():
            lines.append(f"[{domain.upper()}]")
            if isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"  {k}: {v}")
            lines.append("")
        return "\n".join(lines)

def parse_natural_language(text: str, caller_id: str = "human") -> Optional[ToolCall]:
    text_lower = text.lower()

    # Snapshot/cursor
    if any(kw in text_lower for kw in ["snapshot", "cursor", "context"]):
        return None

    # IM
    if "send im" in text_lower or "send message" in text_lower or "chat" in text_lower:
        import re
        match = re.search(r"to\s+(\w+)", text, re.I)
        target = match.group(1) if match else "unknown"
        msg_match = re.search(r":\s*(.+)$", text)
        message = msg_match.group(1).strip() if msg_match else "hello"
        return ToolCall("comms.send_im", {"target": target, "message": message}, caller_id)

    # Email
    if "email" in text_lower or "mail" in text_lower:
        import re
        match = re.search(r"(to|email)\s+([\w\s,]+?)\s*:", text, re.I)
        recipients = match.group(2).split(",") if match else ["team"]
        body_match = re.search(r":\s*(.+)$", text)
        body = body_match.group(1).strip() if body_match else "update"
        return ToolCall("comms.send_email", {
            "sender": caller_id + "@murphy.local",
            "recipients": [r.strip() + "@murphy.local" for r in recipients],
            "subject": "Murphy Dispatch",
            "body": body,
        }, caller_id)

    # Meeting
    if "meeting" in text_lower or "meet" in text_lower:
        import re
        match = re.search(r"with\s+([\w\s,]+?)\s+about\s+(.+)", text, re.I)
        if match:
            participants = [p.strip() for p in match.group(1).split(",")]
            topic = match.group(2).strip()
            return ToolCall("meeting.start", {"topic": topic, "participants": participants}, caller_id)

    # Broadcast
    if "broadcast" in text_lower or "announce" in text_lower:
        import re
        match = re.search(r":\s*(.+)$", text)
        message = match.group(1).strip() if match else text
        return ToolCall("comms.broadcast", {"message": message, "sender_id": caller_id}, caller_id)

    # Voice call
    if "call" in text_lower or "phone" in text_lower:
        import re
        match = re.search(r"call\s+(\w+)", text, re.I)
        target = match.group(1) if match else "unknown"
        return ToolCall("comms.start_voice_call", {"caller_id": caller_id, "target_id": target}, caller_id)

    # Video call
    if "video" in text_lower:
        import re
        match = re.search(r"with\s+([\w\s,]+)", text, re.I)
        participants = [p.strip() for p in match.group(1).split(",")] if match else ["team"]
        return ToolCall("comms.start_video_call", {"initiator_id": caller_id, "participant_ids": participants}, caller_id)

    # Health check
    if "health" in text_lower or "status" in text_lower:
        return ToolCall("system.health", {}, caller_id)

    return None

class Dispatcher:
    def __init__(self, registry: ToolRegistry, approval_store: PendingApprovalStore):
        self._registry = registry
        self._approval_store = approval_store
        self._lock = threading.Lock()

    def call(self, tc: ToolCall) -> ToolResult:
        tool = self._registry.get(tc.tool_name)
        if not tool:
            return ToolResult(False, None, f"Tool {tc.tool_name} not found", 0, tc.tool_name, tc.call_id)

        # Approval check
        if tool.approval_tier != "none":
            if tool.approval_tier == "platform":
                score = self._mss_soft_check(str(tc.args))
                if score < 0.3:
                    self._approval_store.queue(tc, "platform")
                    return ToolResult(False, {"pending": True, "approval_id": tc.call_id, "tier": "platform"}, None, 0, tc.tool_name, tc.call_id)
            elif tool.approval_tier in ["user", "customer"]:
                self._approval_store.queue(tc, tool.approval_tier)
                return ToolResult(False, {"pending": True, "approval_id": tc.call_id, "tier": tool.approval_tier}, None, 0, tc.tool_name, tc.call_id)

        return self._execute(tc, tool)

    def _execute(self, tc: ToolCall, tool: Tool = None) -> ToolResult:
        if tool is None:
            tool = self._registry.get(tc.tool_name)
            if not tool:
                return ToolResult(False, None, f"Tool {tc.tool_name} not found", 0, tc.tool_name, tc.call_id)

        start = time.time()
        try:
            result = tool.handler(tc.args)
            duration = int((time.time() - start) * 1000)
            self._persist(tc, True, result, None, duration)
            return ToolResult(True, result, None, duration, tc.tool_name, tc.call_id)
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self._persist(tc, False, None, str(e), duration)
            return ToolResult(False, None, str(e), duration, tc.tool_name, tc.call_id)

    def _mss_soft_check(self, content: str) -> float:
        try:
            import httpx
            resp = httpx.post("http://localhost:8000/api/mss/score",
                              json={"text": content}, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                q = data.get("quality", {})
                return float(q.get("overall_score", 1.0))
        except Exception:
            pass
        return 1.0

    def _persist(self, tc: ToolCall, ok: bool, data: Any, error: Optional[str], duration: int):
        try:
            from src.db import DispatchLog, get_session
            sess = get_session()
            log = DispatchLog(
                call_id=tc.call_id,
                tool_name=tc.tool_name,
                caller_id=tc.caller_id,
                caller_type=tc.caller_type,
                args=tc.args,
                result_ok=ok,
                result_data=data,
                error_message=error,
                duration_ms=duration,
                timestamp=_now_iso(),
            )
            sess.add(log)
            sess.commit()
            sess.close()
        except Exception as e:
            logger.debug("Failed to persist log: %s", e)

    def call_fn(self, tool_name: str, args: dict, caller_id: str = "system") -> ToolResult:
        tc = ToolCall(tool_name, args, caller_id)
        return self.call(tc)

    def batch(self, calls: List[ToolCall]) -> List[ToolResult]:
        return [self.call(tc) for tc in calls]

    def call_from_llm_response(self, tool_calls: list, caller_id: str = "llm") -> List[ToolResult]:
        results = []
        for tc_dict in tool_calls:
            name = tc_dict.get("function", {}).get("name") or tc_dict.get("name", "unknown")
            args_str = tc_dict.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except (ValueError, TypeError) as exc:
                logger.debug("Failed to parse tool call arguments for %s: %s", name, exc)
                args = {}
            tc = ToolCall(name, args, caller_id, "llm")
            results.append(self.call(tc))
        return results

    def get_log(self, limit: int = 50) -> List[dict]:
        try:
            from src.db import DispatchLog, get_session
            sess = get_session()
            logs = sess.query(DispatchLog).order_by(DispatchLog.timestamp.desc()).limit(limit).all()
            result = [
                {
                    "call_id": log.call_id,
                    "tool_name": log.tool_name,
                    "caller_id": log.caller_id,
                    "ok": log.result_ok,
                    "duration_ms": log.duration_ms,
                    "timestamp": log.timestamp,
                }
                for log in logs
            ]
            sess.close()
            return result
        except Exception:
            return []

def _register_builtin_tools(registry: ToolRegistry):
    # Comms tools
    def send_im_handler(args):
        from src.communication_hub import im_store
        return im_store.send_message(args["target"], args["message"], args.get("sender", "murphy"))

    registry.register(Tool("comms.send_im", "Send IM", {"type": "object", "properties": {"target": {"type": "string"}, "message": {"type": "string"}}}, send_im_handler, "comms", approval_tier="platform"))

    def send_email_handler(args):
        from src.communication_hub import email_store
        return email_store.send(args["sender"], args["recipients"], args["subject"], args["body"])

    registry.register(Tool("comms.send_email", "Send email", {"type": "object"}, send_email_handler, "comms", approval_tier="user"))

    def broadcast_handler(args):
        from src.communication_hub import mod_console
        return mod_console.broadcast(args["message"], args.get("sender_id", "murphy"))

    registry.register(Tool("comms.broadcast", "Broadcast message", {"type": "object"}, broadcast_handler, "comms", approval_tier="user"))

    def voice_call_handler(args):
        from src.communication_hub import call_store
        return call_store.start_call(args["caller_id"], args["target_id"], "voice")

    registry.register(Tool("comms.start_voice_call", "Start voice call", {"type": "object"}, voice_call_handler, "comms", approval_tier="platform"))

    def video_call_handler(args):
        from src.communication_hub import call_store
        return call_store.start_video_call(args["initiator_id"], args.get("participant_ids", []))

    registry.register(Tool("comms.start_video_call", "Start video call", {"type": "object"}, video_call_handler, "comms", approval_tier="platform"))

    # Meeting tools
    def meeting_start_handler(args):
        from src.meetings_bridge import MeetingsBridge
        mb = MeetingsBridge()
        return mb.start_meeting(args.get("topic", "Meeting"), args.get("participants", []))

    registry.register(Tool("meeting.start", "Start meeting", {"type": "object"}, meeting_start_handler, "meetings", approval_tier="user"))

    def meeting_end_handler(args):
        from src.meetings_bridge import MeetingsBridge
        mb = MeetingsBridge()
        return mb.end_meeting(args["meeting_id"])

    registry.register(Tool("meeting.end", "End meeting", {"type": "object"}, meeting_end_handler, "meetings", approval_tier="user"))

    # System health
    def health_handler(args):
        from src.db import check_database
        return {"db": "ok" if check_database() else "error", "status": "running"}

    registry.register(Tool("system.health", "System health", {"type": "object"}, health_handler, "system", approval_tier="none"))

    # Analysis
    def analysis_handler(args):
        try:
            from bots.analysisbot import AnalysisBot
            ab = AnalysisBot()
            return ab.analyze(args["task"], args.get("context", ""))
        except Exception as exc:
            logger.debug("analysis.run handler unavailable: %s", exc)
            return {"result": f"Analysis: {args['task']}"}

    registry.register(Tool("analysis.run", "Run analysis", {"type": "object"}, analysis_handler, "analysis", approval_tier="platform"))

    # Memory
    def memory_store_handler(args):
        try:
            from bots.memory_cortex_bot import MemoryCortexBot
            mb = MemoryCortexBot()
            return mb.store(args["key"], args["value"], args.get("tags", []))
        except Exception as exc:
            logger.debug("memory.store handler unavailable: %s", exc)
            return {"stored": True}

    registry.register(Tool("memory.store", "Store memory", {"type": "object"}, memory_store_handler, "memory", approval_tier="platform"))

    def memory_recall_handler(args):
        try:
            from bots.memory_cortex_bot import MemoryCortexBot
            mb = MemoryCortexBot()
            return mb.recall(args["query"], args.get("limit", 5))
        except Exception as exc:
            logger.debug("memory.recall handler unavailable: %s", exc)
            return {"results": []}

    registry.register(Tool("memory.recall", "Recall memory", {"type": "object"}, memory_recall_handler, "memory", approval_tier="platform"))

    # LLM
    def llm_query_handler(args):
        try:
            from src.llm_controller import LLMController
            llm = LLMController()
            return llm.query(args["prompt"], args.get("context", ""), args.get("max_tokens", 500))
        except Exception as exc:
            logger.debug("llm.query handler unavailable: %s", exc)
            return {"response": "LLM unavailable"}

    registry.register(Tool("llm.query", "LLM query", {"type": "object"}, llm_query_handler, "llm", approval_tier="platform"))

    # Org
    def org_check_handler(args):
        try:
            from src.org_chart_enforcement import OrgChartEnforcement
            oce = OrgChartEnforcement()
            return oce.check_permission(args["node_id"], args["action"])
        except Exception as exc:
            logger.debug("org.check_permission handler unavailable: %s", exc)
            return {"allowed": True}

    registry.register(Tool("org.check_permission", "Check org permission", {"type": "object"}, org_check_handler, "org", approval_tier="platform"))

    def org_escalate_handler(args):
        try:
            from src.org_chart_enforcement import OrgChartEnforcement
            oce = OrgChartEnforcement()
            return oce.escalate(args["node_id"], args["reason"], args.get("target_level"))
        except Exception as exc:
            logger.debug("org.escalate handler unavailable: %s", exc)
            return {"escalated": True}

    registry.register(Tool("org.escalate", "Escalate org issue", {"type": "object"}, org_escalate_handler, "org", approval_tier="user"))

_registry = ToolRegistry()
_approval_store = PendingApprovalStore()
_cursor_context = MultiCursorContext()
_dispatcher = Dispatcher(_registry, _approval_store)

# Public API
dispatcher = _dispatcher
register_tool = _registry.register
dispatch = _dispatcher.call
approval_store = _approval_store
cursor_context = _cursor_context

_register_builtin_tools(_registry)

logger.info("Dispatch engine initialized with %d tools", len(_registry._tools))
