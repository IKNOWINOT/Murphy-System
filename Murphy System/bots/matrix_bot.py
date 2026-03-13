"""Murphy Matrix Bot — core command router and API client.

All !murphy commands are handled here.  Each handler:
  1. Parses the command arguments
  2. Calls the Murphy API via httpx (async)
  3. Formats the response with matrix_formatters
  4. Sends the formatted HTML message back to the room
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Callable, Coroutine, Optional

import httpx

try:
    import nio
    from nio import AsyncClient, MatrixRoom, RoomMessageText
except ImportError:  # pragma: no cover — matrix-nio optional
    nio = None  # type: ignore
    AsyncClient = None  # type: ignore
    MatrixRoom = None  # type: ignore
    RoomMessageText = None  # type: ignore

from .matrix_config import MatrixBotConfig
from .matrix_formatters import (
    format_agents,
    format_costs,
    format_dict,
    format_flows,
    format_health,
    format_help,
    format_hitl_list,
    format_json,
    format_links,
    format_list_table,
    format_orgchart,
    format_status,
    format_workflows,
    skull_header,
    error_msg,
    warn_msg,
    success_msg,
    status_badge,
    _code,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Circuit breaker state (mirrors MurphyAPI._checkCircuit in murphy-components.js)
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """Simple async circuit breaker — CLOSED → OPEN → HALF_OPEN → CLOSED."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, threshold: int = 5, timeout: int = 60) -> None:
        self.threshold = threshold
        self.timeout = timeout
        self._failures = 0
        self._state = self.CLOSED
        self._opened_at: float = 0.0

    def record_success(self) -> None:
        self._failures = 0
        self._state = self.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            self._state = self.OPEN
            self._opened_at = time.monotonic()

    def is_open(self) -> bool:
        if self._state == self.OPEN:
            if time.monotonic() - self._opened_at >= self.timeout:
                self._state = self.HALF_OPEN
                return False
            return True
        return False

    @property
    def state(self) -> str:
        return self._state


# ---------------------------------------------------------------------------
# Murphy API client
# ---------------------------------------------------------------------------

class MurphyAPIClient:
    """Async httpx client for the Murphy REST API with circuit breaker."""

    def __init__(self, config: MatrixBotConfig) -> None:
        self.base_url = config.murphy_api_url.rstrip("/")
        self.timeout = config.api_timeout
        self.circuit = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            timeout=config.circuit_breaker_timeout,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get(self, path: str, **params: Any) -> Any:
        return await self._request("GET", path, params=params or None)

    async def post(self, path: str, body: Any = None) -> Any:
        return await self._request("POST", path, json=body)

    async def patch(self, path: str, body: Any = None) -> Any:
        return await self._request("PATCH", path, json=body)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self.circuit.is_open():
            raise RuntimeError(
                f"Murphy API circuit breaker is OPEN "
                f"(too many failures). Try again later."
            )
        url = f"{self.base_url}{path}"
        client = await self._get_client()
        try:
            resp = await client.request(method, url, **kwargs)
            resp.raise_for_status()
            self.circuit.record_success()
            try:
                return resp.json()
            except Exception:
                return resp.text
        except Exception as exc:
            self.circuit.record_failure()
            raise RuntimeError(f"API error [{method} {path}]: {exc}") from exc


# ---------------------------------------------------------------------------
# Core bot
# ---------------------------------------------------------------------------

class MurphyMatrixBot:
    """Matrix bot that exposes all Murphy terminal functions as chat commands."""

    COMMAND_PREFIX = "!murphy"

    def __init__(self, config: MatrixBotConfig) -> None:
        if nio is None:
            raise ImportError(
                "matrix-nio is required. Install with: pip install 'matrix-nio[e2e]>=0.24.0'"
            )
        self.config = config
        self.api = MurphyAPIClient(config)
        self.client = AsyncClient(config.homeserver, config.user_id)
        self._running = False
        # event_id → intervention_id for reaction-based HITL
        self._hitl_event_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Login and begin processing events."""
        errors = self.config.validate()
        if errors:
            raise ValueError("Config errors: " + "; ".join(errors))

        if self.config.access_token:
            self.client.access_token = self.config.access_token
            self.client.user_id = self.config.user_id
        else:
            resp = await self.client.login(self.config.password)
            if hasattr(resp, "access_token"):
                logger.info("Logged in as %s", self.config.user_id)
            else:
                raise RuntimeError(f"Login failed: {resp}")

        self.client.add_event_callback(self._on_message, RoomMessageText)
        try:
            from nio import UnknownEvent
            self.client.add_event_callback(self._on_reaction, UnknownEvent)
        except Exception:  # pragma: no cover
            pass

        self._running = True
        logger.info("Murphy Matrix bot started — prefix: %s", self.COMMAND_PREFIX)
        await self.client.sync_forever(timeout=30000, full_state=True)

    async def stop(self) -> None:
        self._running = False
        await self.api.close()
        await self.client.close()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _on_message(self, room: "MatrixRoom", event: "RoomMessageText") -> None:
        if event.sender == self.config.user_id:
            return
        body = (event.body or "").strip()
        if not body.lower().startswith(self.COMMAND_PREFIX):
            return
        args = body[len(self.COMMAND_PREFIX):].strip().split()
        try:
            response = await self._dispatch(args)
        except RuntimeError as exc:
            response = error_msg(str(exc))
        except Exception as exc:
            logger.exception("Unhandled error in command handler")
            response = error_msg(f"Unexpected error: {exc}")
        await self._send(room.room_id, response)

    async def _on_reaction(self, room: "MatrixRoom", event: Any) -> None:
        """Handle ✅/❌ reactions for HITL approval/rejection."""
        try:
            content = event.source.get("content", {})
            if content.get("m.relates_to", {}).get("rel_type") != "m.annotation":
                return
            key = content["m.relates_to"].get("key", "")
            relates_to = content["m.relates_to"].get("event_id", "")
            intervention_id = self._hitl_event_map.get(relates_to)
            if not intervention_id:
                return
            if key == "✅":
                await self._hitl_respond(intervention_id, "approve")
                await self._send(room.room_id, success_msg(
                    f"Intervention {_code(intervention_id)} approved via reaction."
                ))
            elif key == "❌":
                await self._hitl_respond(intervention_id, "reject")
                await self._send(room.room_id, warn_msg(
                    f"Intervention {_code(intervention_id)} rejected via reaction."
                ))
        except Exception:
            logger.exception("Error processing reaction")

    # ------------------------------------------------------------------
    # Message sender
    # ------------------------------------------------------------------

    async def _send(self, room_id: str, html: str, plain: str | None = None) -> str | None:
        """Send an HTML message; return event_id if available."""
        content = {
            "msgtype": "m.text",
            "body": plain or _strip_html(html),
            "format": "org.matrix.custom.html",
            "formatted_body": html,
        }
        try:
            resp = await self.client.room_send(room_id, "m.room.message", content)
            return getattr(resp, "event_id", None)
        except Exception as exc:
            logger.error("Failed to send message to %s: %s", room_id, exc)
            return None

    # ------------------------------------------------------------------
    # Command dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(self, args: list[str]) -> str:
        if not args:
            return format_help()

        cmd = args[0].lower()

        # ---- help & navigation ----
        if cmd == "help":
            return format_help(args[1] if len(args) > 1 else None)
        if cmd == "links":
            return format_links(self.config.murphy_web_url)

        # ---- core system ----
        if cmd == "status":
            data = await self.api.get("/status")
            return format_status(data) if isinstance(data, dict) else format_json(data)
        if cmd == "health":
            data = await self.api.get("/health")
            return format_health(data) if isinstance(data, dict) else format_json(data)
        if cmd == "info":
            data = await self.api.get("/info")
            return format_dict(data, "System Info") if isinstance(data, dict) else format_json(data)

        # ---- orchestrator ----
        if cmd == "overview":
            data = await self.api.get("/orchestrator/overview")
            return format_json(data)
        if cmd == "flows":
            return await self._cmd_flows(args[1:])

        # ---- execute / chat ----
        if cmd == "execute":
            if len(args) < 2:
                return error_msg("Usage: !murphy execute <command>")
            command_text = " ".join(args[1:])
            data = await self.api.post("/execute", {"command": command_text})
            return format_json(data)
        if cmd == "chat":
            if len(args) < 2:
                return error_msg("Usage: !murphy chat <message>")
            message = " ".join(args[1:])
            data = await self.api.post("/chat", {"message": message})
            reply = data.get("response", data.get("message", str(data))) if isinstance(data, dict) else str(data)
            return f"{skull_header('Murphy')}<br/>{reply}"

        # ---- workflows ----
        if cmd == "workflows":
            data = await self.api.get("/workflows")
            items = data if isinstance(data, list) else data.get("workflows", data)
            return format_workflows(items) if isinstance(items, list) else format_json(data)
        if cmd == "workflow":
            return await self._cmd_workflow(args[1:])
        if cmd == "workflow-terminal":
            if len(args) > 1 and args[1].lower() == "list":
                data = await self.api.get("/workflow-terminal/list")
                return format_json(data)
            return error_msg("Usage: !murphy workflow-terminal list")
        if cmd == "generate":
            return await self._cmd_generate(args[1:])
        if cmd == "upload":
            return await self._cmd_upload(args[1:])

        # ---- agents & orgchart ----
        if cmd == "agents":
            data = await self.api.get("/agent-dashboard/agents")
            items = data if isinstance(data, list) else data.get("agents", data)
            return format_agents(items) if isinstance(items, list) else format_json(data)
        if cmd == "agent":
            return await self._cmd_agent(args[1:])
        if cmd == "orgchart":
            task_id = args[1] if len(args) > 1 else None
            if task_id:
                data = await self.api.get(f"/orgchart/{task_id}")
            else:
                data = await self.api.get("/orgchart/live")
            return format_orgchart(data) if isinstance(data, dict) else format_json(data)

        # ---- HITL ----
        if cmd == "hitl":
            return await self._cmd_hitl(args[1:])

        # ---- forms ----
        if cmd == "form":
            return await self._cmd_form(args[1:])

        # ---- corrections ----
        if cmd == "corrections":
            return await self._cmd_corrections(args[1:])

        # ---- costs ----
        if cmd == "costs":
            return await self._cmd_costs(args[1:])

        # ---- integrations ----
        if cmd == "integrations":
            subarg = args[1].lower() if len(args) > 1 else ""
            if subarg == "all":
                data = await self.api.get("/integrations/all")
            else:
                data = await self.api.get("/integrations/active")
            return format_json(data)

        # ---- mfgc ----
        if cmd == "mfgc":
            return await self._cmd_mfgc(args[1:])

        # ---- librarian ----
        if cmd == "ask":
            if len(args) < 2:
                return error_msg("Usage: !murphy ask <query>")
            query = " ".join(args[1:])
            data = await self.api.post("/librarian/ask", {"query": query})
            answer = data.get("answer", data.get("response", str(data))) if isinstance(data, dict) else str(data)
            return f"{skull_header('Librarian')}<br/>{answer}"
        if cmd == "librarian":
            if len(args) > 1 and args[1].lower() == "status":
                data = await self.api.get("/librarian/status")
                return format_json(data)
            return error_msg("Usage: !murphy librarian status")

        # ---- documents & deliverables ----
        if cmd == "documents":
            data = await self.api.get("/documents")
            return format_json(data)
        if cmd == "deliverables":
            data = await self.api.get("/deliverables")
            return format_json(data)

        # ---- tasks & queue ----
        if cmd == "tasks":
            data = await self.api.get("/tasks")
            return format_json(data)
        if cmd == "queue":
            data = await self.api.get("/production/queue")
            return format_json(data)

        # ---- llm & mfm ----
        if cmd == "llm":
            if len(args) > 1 and args[1].lower() == "status":
                data = await self.api.get("/llm/status")
                return format_json(data)
            return error_msg("Usage: !murphy llm status")
        if cmd == "mfm":
            return await self._cmd_mfm(args[1:])

        # ---- onboarding ----
        if cmd == "onboarding":
            return await self._cmd_onboarding(args[1:])

        # ---- ip & credentials ----
        if cmd == "ip":
            if len(args) > 1 and args[1].lower() == "assets":
                data = await self.api.get("/ip/assets")
                return format_json(data)
            return error_msg("Usage: !murphy ip assets")
        if cmd == "credentials":
            data = await self.api.get("/credentials/list")
            return format_json(data)

        # ---- profiles & auth ----
        if cmd == "profiles":
            data = await self.api.get("/profiles")
            return format_json(data)
        if cmd == "role":
            data = await self.api.get("/auth/role")
            return format_json(data)
        if cmd == "permissions":
            data = await self.api.get("/auth/permissions")
            return format_json(data)

        # ---- diagnostics ----
        if cmd == "diagnostics":
            data = await self.api.get("/diagnostics")
            return format_json(data)

        # ---- wingman & causality ----
        if cmd == "wingman":
            data = await self.api.get("/wingman/status")
            return format_json(data)
        if cmd == "causality":
            data = await self.api.get("/causality/status")
            return format_json(data)

        return error_msg(
            f"Unknown command: {_code(cmd)}. "
            "Try <code>!murphy help</code> to see all commands."
        )

    # ------------------------------------------------------------------
    # Sub-command helpers
    # ------------------------------------------------------------------

    async def _cmd_flows(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "inbound":
            data = await self.api.get("/flows/inbound")
        elif sub == "processing":
            data = await self.api.get("/flows/processing")
        elif sub == "outbound":
            data = await self.api.get("/flows/outbound")
        elif sub == "state":
            data = await self.api.get("/flows/state")
        else:
            data = await self.api.get("/orchestrator/flows")
        return format_flows(data)

    async def _cmd_workflow(self, args: list[str]) -> str:
        if not args:
            return error_msg("Usage: !murphy workflow <id> | save <json> | builder")
        sub = args[0].lower()
        if sub == "builder":
            url = self.config.terminal_url("workflow_canvas.html")
            return (
                f"{skull_header('Workflow Builder')}<br/>"
                f'Open the visual workflow builder: <a href="{url}">{url}</a>'
            )
        if sub == "save":
            if len(args) < 2:
                return error_msg("Usage: !murphy workflow save <json>")
            try:
                payload = json.loads(" ".join(args[1:]))
            except json.JSONDecodeError as exc:
                return error_msg(f"Invalid JSON: {exc}")
            data = await self.api.post("/workflows", payload)
            return success_msg(f"Workflow saved.") + format_json(data)
        # get by id
        workflow_id = args[0]
        data = await self.api.get(f"/workflows/{workflow_id}")
        return format_json(data)

    async def _cmd_generate(self, args: list[str]) -> str:
        if not args or args[0].lower() != "plan":
            return error_msg("Usage: !murphy generate plan <description>")
        description = " ".join(args[1:])
        if not description:
            return error_msg("Usage: !murphy generate plan <description>")
        data = await self.api.post("/forms/plan-generation", {"description": description})
        return f"{skull_header('Generated Plan')}<br/>{format_json(data)}"

    async def _cmd_upload(self, args: list[str]) -> str:
        if not args or args[0].lower() != "plan":
            return error_msg("Usage: !murphy upload plan <json>")
        try:
            payload = json.loads(" ".join(args[1:]))
        except json.JSONDecodeError as exc:
            return error_msg(f"Invalid JSON: {exc}")
        data = await self.api.post("/forms/plan-upload", payload)
        return success_msg("Plan uploaded.") + format_json(data)

    async def _cmd_agent(self, args: list[str]) -> str:
        if not args:
            return error_msg("Usage: !murphy agent <id> [activity]")
        agent_id = args[0]
        if len(args) > 1 and args[1].lower() == "activity":
            data = await self.api.get(f"/agent-dashboard/agents/{agent_id}/activity")
            return format_json(data)
        data = await self.api.get(f"/agent-dashboard/agents/{agent_id}")
        return format_json(data)

    async def _cmd_hitl(self, args: list[str]) -> str:
        sub = args[0].lower() if args else "pending"
        if sub == "pending":
            data = await self.api.get("/hitl/interventions/pending")
            items = data if isinstance(data, list) else data.get("interventions", data)
            return format_hitl_list(items) if isinstance(items, list) else format_json(data)
        if sub == "stats":
            data = await self.api.get("/hitl/statistics")
            return format_json(data)
        if sub == "respond":
            return await self._cmd_hitl_respond(args[1:])
        return error_msg("Usage: !murphy hitl pending | stats | respond <id> <approve|reject> [reason]")

    async def _cmd_hitl_respond(self, args: list[str]) -> str:
        if len(args) < 2:
            return error_msg("Usage: !murphy hitl respond <id> <approve|reject> [reason]")
        intervention_id = args[0]
        action = args[1].lower()
        if action not in ("approve", "reject"):
            return error_msg("Action must be 'approve' or 'reject'")
        reason = " ".join(args[2:]) if len(args) > 2 else ""
        return await self._hitl_respond(intervention_id, action, reason)

    async def _hitl_respond(
        self, intervention_id: str, action: str, reason: str = ""
    ) -> str:
        payload: dict = {"action": action}
        if reason:
            payload["reason"] = reason
        data = await self.api.post(
            f"/hitl/interventions/{intervention_id}/respond", payload
        )
        return success_msg(
            f"Intervention {_code(intervention_id)} {action}d."
        ) + format_json(data)

    async def _cmd_form(self, args: list[str]) -> str:
        if not args:
            return error_msg("Usage: !murphy form task|validate|correct|status ...")
        sub = args[0].lower()
        if sub == "status":
            if len(args) < 2:
                return error_msg("Usage: !murphy form status <id>")
            data = await self.api.get(f"/forms/submission/{args[1]}")
            return format_json(data)
        json_str = " ".join(args[1:])
        try:
            payload = json.loads(json_str)
        except json.JSONDecodeError as exc:
            return error_msg(f"Invalid JSON: {exc}")
        path_map = {
            "task": "/forms/task-execution",
            "validate": "/forms/validation",
            "correct": "/forms/correction",
        }
        if sub not in path_map:
            return error_msg(f"Unknown form subcommand: {_code(sub)}")
        data = await self.api.post(path_map[sub], payload)
        return success_msg(f"Form {sub} submitted.") + format_json(data)

    async def _cmd_corrections(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "patterns":
            data = await self.api.get("/corrections/patterns")
        elif sub == "stats":
            data = await self.api.get("/corrections/statistics")
        elif sub == "training":
            data = await self.api.get("/corrections/training-data")
        else:
            return error_msg("Usage: !murphy corrections patterns|stats|training")
        return format_json(data)

    async def _cmd_costs(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "breakdown":
            data = await self.api.get("/costs/breakdown")
        elif sub == "by-bot":
            data = await self.api.get("/costs/by-bot")
        elif sub == "budget":
            data = await self.api.patch("/costs/budget")
        else:
            data = await self.api.get("/costs")
        return format_costs(data) if isinstance(data, dict) else format_json(data)

    async def _cmd_mfgc(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "state":
            data = await self.api.get("/mfgc/state")
        elif sub == "config":
            if len(args) > 1 and args[1].lower() == "set":
                try:
                    payload = json.loads(" ".join(args[2:]))
                except json.JSONDecodeError as exc:
                    return error_msg(f"Invalid JSON: {exc}")
                data = await self.api.post("/mfgc/config", payload)
            else:
                data = await self.api.get("/mfgc/config")
        elif sub == "setup":
            if len(args) < 2:
                return error_msg("Usage: !murphy mfgc setup <profile>")
            data = await self.api.post(f"/mfgc/setup/{args[1]}")
        else:
            return error_msg("Usage: !murphy mfgc state|config|config set <json>|setup <profile>")
        return format_json(data)

    async def _cmd_mfm(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "status":
            data = await self.api.get("/mfm/status")
        elif sub == "metrics":
            data = await self.api.get("/mfm/metrics")
        else:
            return error_msg("Usage: !murphy mfm status|metrics")
        return format_json(data)

    async def _cmd_onboarding(self, args: list[str]) -> str:
        sub = args[0].lower() if args else ""
        if sub == "status":
            data = await self.api.get("/onboarding/status")
        elif sub == "questions":
            data = await self.api.get("/onboarding/wizard/questions")
        else:
            return error_msg("Usage: !murphy onboarding status|questions")
        return format_json(data)

    # ------------------------------------------------------------------
    # HITL reaction registration (called by matrix_hitl.py)
    # ------------------------------------------------------------------

    def register_hitl_event(self, event_id: str, intervention_id: str) -> None:
        """Register an event_id → intervention_id for reaction-based HITL."""
        self._hitl_event_map[event_id] = intervention_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Very basic HTML-to-plain-text for the Matrix plain-text body."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()
