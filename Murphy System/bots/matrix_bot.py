# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Core Matrix bot for the Murphy System.

Implements all 90+ commands from the Murphy System Matrix bot specification,
a circuit-breaker pattern mirroring MurphyAPI from murphy-components.js,
retry logic with exponential back-off, and a thin httpx.AsyncClient wrapper.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import re
import time
from typing import Any, Callable, Coroutine, Optional

import httpx

try:
    from nio import AsyncClient, RoomMessageText, InviteMemberEvent, LoginResponse
except ImportError:
    AsyncClient = None
    RoomMessageText = None
    InviteMemberEvent = None
    LoginResponse = None

from .matrix_config import MatrixConfig
from .matrix_formatters import (
    format_status, format_overview, format_table, format_workflow_detail,
    format_agent_detail, format_hitl_intervention, format_cost_summary,
    format_jargon, format_jargon_list, format_help, format_links,
    format_error, format_success, format_code_block, format_terminal_output,
    format_email_result, format_notification_result, format_webhook_delivery,
    format_connector_status, format_comms_activity_feed, format_integration_status,
    format_service_ticket, get_all_jargon,
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
# Help categories
# ---------------------------------------------------------------------------

HELP_CATEGORIES: Dict[str, List[str]] = {
    "Dashboard": [
        "!murphy status", "!murphy overview", "!murphy info"
    ],
    "Orchestrator / Flows": [
        "!murphy workflows", "!murphy workflow <id>",
        "!murphy workflow cancel|retry|rollback <id>",
        "!murphy workflow save <json>", "!murphy workflow builder",
        "!murphy flows", "!murphy flows inbound|processing|outbound|state",
    ],
    "Execute / Chat": [
        "!murphy execute <command>", "!murphy chat <message>", "!murphy ask <query>"
    ],
    "Agents / Org Chart": [
        "!murphy agents", "!murphy agent <id>", "!murphy agent <id> activity",
        "!murphy orgchart", "!murphy orgchart <task_id>",
    ],
    "HITL": [
        "!murphy hitl pending", "!murphy hitl respond <id> approve|reject [reason]",
        "!murphy hitl stats",
    ],
    "📧 Email / Communication": [
        "!murphy email send <to> <subject> :: <body>",
        "!murphy email status", "!murphy email test",
        "!murphy notify <subject> :: <body>",
        "!murphy notify template <id> <json>",
        "!murphy notify channels",
        "!murphy comms feed", "!murphy comms stats",
    ],
    "🔗 Integrations": [
        "!murphy integrations", "!murphy integrations all",
        "!murphy integration <id>", "!murphy integration <id> test",
        "!murphy integration <id> execute <method> [json]",
        "!murphy connectors", "!murphy connector <id>",
    ],
    "🪝 Webhooks": [
        "!murphy webhooks", "!murphy webhook <id>",
        "!murphy webhook create <json>",
        "!murphy webhook fire <event_type> [json]",
        "!murphy webhook deliveries <sub_id>",
        "!murphy webhook stats",
    ],
    "🎫 Service Module": [
        "!murphy service tickets", "!murphy service ticket <id>",
        "!murphy service ticket create <json>",
        "!murphy service ticket <id> assign <agent>",
        "!murphy service catalog",
        "!murphy service kb search <query>",
        "!murphy service sla", "!murphy service csat",
    ],
    "💰 Costs": [
        "!murphy costs", "!murphy costs breakdown", "!murphy costs by-bot",
        "!murphy costs budget", "!murphy costs optimize",
        "!murphy costs record <json>",
    ],
    "Forms / Corrections": [
        "!murphy form task|validate|correct <json>",
        "!murphy corrections patterns|stats|training",
    ],
    "MFGC / LLM / MFM": [
        "!murphy mfgc state|config|setup",
        "!murphy llm status", "!murphy llm configure <provider> <key>",
        "!murphy llm test", "!murphy mfm status|metrics",
    ],
    "Documents / Tasks / Queue": [
        "!murphy documents", "!murphy deliverables",
        "!murphy tasks", "!murphy queue",
    ],
    "Auth / Onboarding / IP": [
        "!murphy onboarding status|questions",
        "!murphy ip assets", "!murphy credentials",
        "!murphy profiles", "!murphy role", "!murphy permissions",
    ],
    "Diagnostics": [
        "!murphy diagnostics", "!murphy wingman",
        "!murphy causality", "!murphy sentinel", "!murphy canary",
    ],
    "Module Compiler": [
        "!murphy modules", "!murphy module <id>",
        "!murphy module compile <source_path>",
        "!murphy capabilities", "!murphy capability <name>",
    ],
    "Bot Management": [
        "!murphy bots", "!murphy bot <id> action <json>",
    ],
    "Help / Navigation": [
        "!murphy help", "!murphy help <category>",
        "!murphy links", "!murphy jargon", "!murphy jargon <term>",
    ],
}

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class CBState(Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker that mirrors MurphyAPI from murphy-components.js.

    Transitions:
        CLOSED  → OPEN      after FAILURE_THRESHOLD consecutive failures
        OPEN    → HALF_OPEN after COOLDOWN seconds
        HALF_OPEN → CLOSED  on success; → OPEN on failure
    """

    FAILURE_THRESHOLD: int = 5
    COOLDOWN: float = 30.0  # seconds

    def __init__(self) -> None:
        self.state: CBState = CBState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0

    def record_success(self) -> None:
        """Reset the breaker to CLOSED after a successful request."""
        self.failure_count = 0
        self.state = CBState.CLOSED

    def record_failure(self) -> None:
        """Increment failure count and open the breaker when threshold is hit."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.FAILURE_THRESHOLD:
            self.state = CBState.OPEN

    def allow_request(self) -> bool:
        """Return True if the circuit breaker permits the next request."""
        if self.state == CBState.CLOSED:
            return True
        if self.state == CBState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.COOLDOWN:
                self.state = CBState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow exactly one probe request
        return True


# ---------------------------------------------------------------------------
# HTTP client with retry + circuit breaker
# ---------------------------------------------------------------------------


class MurphyAPIClient:
    """Async HTTP client wrapping httpx with circuit breaker and retry logic.

    Retry policy: up to MAX_RETRIES additional attempts on 5xx or network
    errors, with exponential back-off capped at 8 seconds.
    """

    MAX_RETRIES: int = 3
    TIMEOUT: float = 10.0

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = httpx.AsyncClient(
            headers={"X-API-Key": api_key},
            timeout=self.TIMEOUT,
        )
        self.cb = CircuitBreaker()

    @staticmethod
    def _backoff(attempt: int) -> float:
        """Return back-off delay in seconds: ``min(1000 * 2^attempt, 8000) ms``."""
        return min(1000 * (2 ** attempt), 8000) / 1000.0

    async def _request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute *method* against *path*, honouring circuit-breaker + retries.

        Returns a normalised response dict: ``{ok, data, error, status}``.
        """
        if not self.cb.allow_request():
            return {"ok": False, "data": None, "error": "Circuit breaker OPEN", "status": 503}

        url = f"{self.base_url}{path}"
        last_err: Optional[str] = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = await self.http.request(method, url, **kwargs)
                if resp.status_code >= 500:
                    await asyncio.sleep(self._backoff(attempt))
                    last_err = f"HTTP {resp.status_code}"
                    self.cb.record_failure()
                    continue
                self.cb.record_success()
                try:
                    data: Any = resp.json()
                except Exception:
                    data = resp.text
                return {"ok": True, "data": data, "error": None, "status": resp.status_code}
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                await asyncio.sleep(self._backoff(attempt))
                last_err = str(exc)
                self.cb.record_failure()

        return {"ok": False, "data": None, "error": last_err or "Unknown error", "status": 0}

    async def get(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Perform a GET request."""
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Perform a POST request."""
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Perform a PUT request."""
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Perform a DELETE request."""
        return await self._request("DELETE", path, **kwargs)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self.http.aclose()


# ---------------------------------------------------------------------------
# Matrix bot
# ---------------------------------------------------------------------------


class MatrixBot:
    """Murphy System Matrix bot.

    Listens for ``!murphy <command>`` messages and dispatches them to the
    corresponding Murphy API endpoint, formatting replies with the helpers
    from :mod:`matrix_formatters`.
    """

    # Maximum characters sent in a single generic code-block reply.
    # Prevents flooding rooms with enormous API payloads.
    _MAX_RESPONSE_CHARS: int = 3000

    # Maximum number of webhook deliveries shown per 'webhook deliveries' query.
    _MAX_DELIVERIES_DISPLAY: int = 10

    def __init__(self, cfg: MatrixConfig, client: Any, api: MurphyAPIClient) -> None:
        self.cfg = cfg
        self.api = api
        self._client: Any = client  # pre-logged-in nio.AsyncClient (may be None)
        self._log = logging.getLogger(f"{__name__}.MatrixBot")
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
        """Register event callbacks and begin syncing using the pre-logged-in client."""
        if AsyncClient is None:
            self._log.error("matrix-nio is not installed; cannot start MatrixBot.")
            return

        if self._client is None:
            self._log.error("No Matrix client provided; cannot start MatrixBot.")
            return

        # Register event callbacks
        self._client.add_event_callback(self._on_message, RoomMessageText)
        self._client.add_event_callback(self._on_invite, InviteMemberEvent)

        self._log.info("MatrixBot starting sync loop for %s.", self.cfg.user_id)
        await self._client.sync_forever(timeout=30000)

    async def stop(self) -> None:
        """Signal the sync loop to stop."""
        if self._client is not None:
            await self._client.close()
        self._log.info("MatrixBot stopped.")

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    async def _on_invite(self, room: Any, event: Any) -> None:
        """Auto-join rooms when invited."""
        if event.membership == "invite" and event.state_key == self.cfg.user_id:
            self._log.info("Joining room %s", room.room_id)
            await self._client.join(room.room_id)

    async def _on_message(self, room: Any, event: Any) -> None:
        """Parse incoming messages and dispatch commands."""
        # Ignore messages sent by the bot itself
        if event.sender == self.cfg.user_id:
            return

        body: str = event.body.strip()
        prefix = self.cfg.command_prefix

        if not body.lower().startswith(prefix.lower()):
            return

        tokens = self._parse_command(body, prefix)
        if not tokens:
            await self.send(room.room_id, f"Usage: {prefix} <command>. Try '{prefix} help'.")
            return

        await self._dispatch(room.room_id, tokens, body)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_command(self, body: str, prefix: str) -> List[str]:
        """Strip *prefix* from *body* and split into tokens, respecting quoted strings."""
        remainder = body[len(prefix):].strip()
        if not remainder:
            return []
        try:
            return shlex.split(remainder)
        except ValueError:
            # Fall back to simple whitespace splitting if shlex fails
            return remainder.split()

    def _parse_json_arg(self, raw: str) -> Tuple[Optional[Any], Optional[str]]:
        """Parse *raw* as JSON; return (parsed, None) or (None, error_msg)."""
        try:
            return json.loads(raw), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"

    # ------------------------------------------------------------------
    # Messaging helper
    # ------------------------------------------------------------------

    async def send(self, room_id: str, plain: str, html: Optional[str] = None) -> None:
        """Send a message to *room_id*, optionally with an HTML formatted body."""
        if AsyncClient is None:
            self._log.warning("matrix-nio not installed; cannot send message")
            return
        content: Dict[str, Any] = {
            "msgtype": "m.text",
            "body": plain,
        }
        if html:
            content["format"] = "org.matrix.custom.html"
            content["formatted_body"] = html
        await self._client.room_send(room_id, "m.room.message", content)

    async def _generic_response(
        self,
        room_id: str,
        result: Dict[str, Any],
        title: str = "",
    ) -> None:
        """Format and send a generic API result as a code block."""
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            data = result["data"]
            if isinstance(data, (dict, list)):
                text = json.dumps(data, indent=2, default=str)
            else:
                text = str(data)
            if title:
                text = f"{title}\n{text}"
            plain, html = format_code_block(text[:self._MAX_RESPONSE_CHARS])
        await self.send(room_id, plain, html)
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

    async def _dispatch(self, room_id: str, tokens: List[str], raw_body: str) -> None:
        """Route tokens to the appropriate command handler."""
        cmd = tokens[0].lower()
        args = tokens[1:]

        try:
            # --- Dashboard ---
            if cmd == "status":
                await self._cmd_status(room_id)
            elif cmd == "overview":
                await self._cmd_overview(room_id)
            elif cmd == "info":
                await self._cmd_info(room_id)

            # --- Orchestrator / Flows ---
            elif cmd == "workflows":
                await self._cmd_workflows(room_id)
            elif cmd == "workflow":
                await self._cmd_workflow(room_id, args, raw_body)
            elif cmd == "flows":
                await self._cmd_flows(room_id, args)

            # --- Execute / Chat ---
            elif cmd == "execute":
                await self._cmd_execute(room_id, args)
            elif cmd == "chat":
                await self._cmd_chat(room_id, args)
            elif cmd == "ask":
                await self._cmd_ask(room_id, args)

            # --- Workflow builder ---
            elif cmd == "generate":
                await self._cmd_generate(room_id, args)
            elif cmd == "upload":
                await self._cmd_upload(room_id, args)

            # --- Agents / Org Chart ---
            elif cmd == "agents":
                await self._cmd_agents(room_id)
            elif cmd == "agent":
                await self._cmd_agent(room_id, args)
            elif cmd == "orgchart":
                await self._cmd_orgchart(room_id, args)

            # --- HITL ---
            elif cmd == "hitl":
                await self._cmd_hitl(room_id, args)

            # --- Email / Comms ---
            elif cmd == "email":
                await self._cmd_email(room_id, args, raw_body)
            elif cmd == "notify":
                await self._cmd_notify(room_id, args, raw_body)
            elif cmd == "comms":
                await self._cmd_comms(room_id, args)

            # --- Integrations ---
            elif cmd == "integrations":
                await self._cmd_integrations(room_id, args)
            elif cmd == "integration":
                await self._cmd_integration(room_id, args)
            elif cmd == "connectors":
                await self._cmd_connectors(room_id)
            elif cmd == "connector":
                await self._cmd_connector(room_id, args)

            # --- Webhooks ---
            elif cmd == "webhooks":
                await self._cmd_webhooks(room_id)
            elif cmd == "webhook":
                await self._cmd_webhook(room_id, args)

            # --- Service Module ---
            elif cmd == "service":
                await self._cmd_service(room_id, args)

            # --- Costs ---
            elif cmd == "costs":
                await self._cmd_costs(room_id, args)

            # --- Forms / Corrections ---
            elif cmd == "form":
                await self._cmd_form(room_id, args)
            elif cmd == "corrections":
                await self._cmd_corrections(room_id, args)

            # --- MFGC / LLM / MFM ---
            elif cmd == "mfgc":
                await self._cmd_mfgc(room_id, args)
            elif cmd == "llm":
                await self._cmd_llm(room_id, args)
            elif cmd == "mfm":
                await self._cmd_mfm(room_id, args)

            # --- Documents / Tasks / Queue ---
            elif cmd == "documents":
                await self._cmd_simple_get(room_id, "/api/documents", "Documents")
            elif cmd == "deliverables":
                await self._cmd_simple_get(room_id, "/api/deliverables", "Deliverables")
            elif cmd == "tasks":
                await self._cmd_simple_get(room_id, "/api/tasks", "Tasks")
            elif cmd == "queue":
                await self._cmd_simple_get(room_id, "/api/queue", "Queue")

            # --- Onboarding / IP / Auth ---
            elif cmd == "onboarding":
                await self._cmd_onboarding(room_id, args)
            elif cmd == "ip":
                await self._cmd_ip(room_id, args)
            elif cmd == "credentials":
                await self._cmd_simple_get(room_id, "/api/credentials", "Credentials")
            elif cmd == "profiles":
                await self._cmd_simple_get(room_id, "/api/profiles", "Profiles")
            elif cmd == "role":
                await self._cmd_simple_get(room_id, "/api/auth/role", "Role")
            elif cmd == "permissions":
                await self._cmd_simple_get(room_id, "/api/auth/permissions", "Permissions")

            # --- Diagnostics / Advanced ---
            elif cmd == "diagnostics":
                await self._cmd_simple_get(room_id, "/api/diagnostics", "Diagnostics")
            elif cmd == "wingman":
                await self._cmd_simple_get(room_id, "/api/wingman/status", "Wingman")
            elif cmd == "causality":
                await self._cmd_simple_get(room_id, "/api/causality/insights", "Causality")
            elif cmd == "sentinel":
                await self._cmd_simple_get(room_id, "/api/sentinel/alerts", "Sentinel")
            elif cmd == "canary":
                await self._cmd_simple_get(room_id, "/api/canary/status", "Canary")

            # --- Module Compiler ---
            elif cmd == "modules":
                await self._cmd_simple_get(room_id, "/api/module-compiler/modules", "Modules")
            elif cmd == "module":
                await self._cmd_module(room_id, args)
            elif cmd == "capabilities":
                await self._cmd_simple_get(room_id, "/api/module-compiler/capabilities", "Capabilities")
            elif cmd == "capability":
                await self._cmd_capability(room_id, args)

            # --- Bot Management ---
            elif cmd == "bots":
                await self._cmd_bots(room_id)
            elif cmd == "bot":
                await self._cmd_bot(room_id, args)

            # --- Help / Navigation ---
            elif cmd == "help":
                await self._cmd_help(room_id, args)
            elif cmd == "links":
                plain, html = format_links(self.cfg.murphy_web_base_url)
                await self.send(room_id, plain, html)
            elif cmd == "jargon":
                await self._cmd_jargon(room_id, args)

            else:
                plain, html = format_error(
                    f"Unknown command '{cmd}'. Try '{self.cfg.command_prefix} help'."
                )
                await self.send(room_id, plain, html)

        except Exception as exc:
            self._log.exception("Unhandled error in command '%s': %s", cmd, exc)
            plain, html = format_error(f"Internal error: {exc}")
            await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Shared simple-GET helper
    # ------------------------------------------------------------------

    async def _cmd_simple_get(self, room_id: str, path: str, title: str = "") -> None:
        result = await self.api.get(path)
        await self._generic_response(room_id, result, title)

    # ------------------------------------------------------------------
    # Dashboard handlers
    # ------------------------------------------------------------------

    async def _cmd_status(self, room_id: str) -> None:
        """Report API and MFGC health."""
        api_result = await self.api.get("/api/health")
        mfgc_result = await self.api.get("/api/mfgc/state")
        api_ok = api_result["ok"] and api_result.get("status", 0) < 400
        mfgc_ok = mfgc_result["ok"] and mfgc_result.get("status", 0) < 400
        plain, html = format_status(api_ok, mfgc_ok)
        await self.send(room_id, plain, html)

    async def _cmd_overview(self, room_id: str) -> None:
        """Show orchestrator overview."""
        result = await self.api.get("/api/orchestrator/overview")
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            plain, html = format_overview(result["data"] or {})
        await self.send(room_id, plain, html)

    async def _cmd_info(self, room_id: str) -> None:
        """Show system info as formatted JSON."""
        result = await self.api.get("/api/info")
        await self._generic_response(room_id, result, "System Info")

    # ------------------------------------------------------------------
    # Orchestrator / Flows handlers
    # ------------------------------------------------------------------

    async def _cmd_workflows(self, room_id: str) -> None:
        """List all workflows."""
        result = await self.api.get("/api/orchestrator/workflows")
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
            await self.send(room_id, plain, html)
            return
        data = result["data"]
        rows: List[List[Any]] = []
        if isinstance(data, list):
            for wf in data:
                rows.append([wf.get("id", ""), wf.get("name", ""), wf.get("status", "")])
        elif isinstance(data, dict):
            items = data.get("workflows") or data.get("items") or []
            for wf in items:
                rows.append([wf.get("id", ""), wf.get("name", ""), wf.get("status", "")])
        plain, html = format_table(["ID", "Name", "Status"], rows)
        await self.send(room_id, plain, html)

    async def _cmd_workflow(self, room_id: str, args: List[str], raw_body: str) -> None:
        """Handle workflow sub-commands."""
        if not args:
            plain, html = format_error("Usage: workflow <id> | workflow cancel|retry|rollback <id> | workflow save <json> | workflow builder")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "builder":
            url = f"{self.cfg.murphy_web_base_url}/workflow-builder"
            plain, html = format_links(self.cfg.murphy_web_base_url)
            await self.send(room_id, f"Workflow Builder: {url}", html)
            return

        if sub == "save":
            json_str = " ".join(args[1:])
            parsed, err = self._parse_json_arg(json_str)
            if err:
                plain, html = format_error(err)
                await self.send(room_id, plain, html)
                return
            result = await self.api.post("/api/workflows", json=parsed)
            await self._generic_response(room_id, result, "Workflow Saved")
            return

        if sub in ("cancel", "retry", "rollback"):
            if len(args) < 2:
                plain, html = format_error(f"Usage: workflow {sub} <id>")
                await self.send(room_id, plain, html)
                return
            wf_id = args[1]
            result = await self.api.post(f"/api/orchestrator/workflows/{wf_id}/{sub}")
            await self._generic_response(room_id, result, f"Workflow {sub.capitalize()}")
            return

        # workflow <id>
        wf_id = args[0]
        result = await self.api.get(f"/api/orchestrator/workflows/{wf_id}")
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            plain, html = format_workflow_detail(result["data"] or {})
        await self.send(room_id, plain, html)

    async def _cmd_flows(self, room_id: str, args: List[str]) -> None:
        """List flows or a specific flow sub-type."""
        if not args:
            result = await self.api.get("/api/orchestrator/flows")
            await self._generic_response(room_id, result, "Flows")
            return
        sub = args[0].lower()
        paths = {
            "inbound": "/api/flows/inbound",
            "processing": "/api/flows/processing",
            "outbound": "/api/flows/outbound",
            "state": "/api/flows/state",
        }
        if sub not in paths:
            plain, html = format_error(f"Unknown flows sub-command '{sub}'.")
            await self.send(room_id, plain, html)
            return
        result = await self.api.get(paths[sub])
        await self._generic_response(room_id, result, f"Flows / {sub.capitalize()}")

    # ------------------------------------------------------------------
    # Execute / Chat handlers
    # ------------------------------------------------------------------

    async def _cmd_execute(self, room_id: str, args: List[str]) -> None:
        """Execute a raw command."""
        if not args:
            plain, html = format_error("Usage: execute <command>")
            await self.send(room_id, plain, html)
            return
        command = " ".join(args)
        result = await self.api.post("/api/execute", json={"command": command})
        await self._generic_response(room_id, result, "Execute")

    async def _cmd_chat(self, room_id: str, args: List[str]) -> None:
        """Send a chat message to Murphy."""
        if not args:
            plain, html = format_error("Usage: chat <message>")
            await self.send(room_id, plain, html)
            return
        message = " ".join(args)
        result = await self.api.post("/api/chat", json={"message": message})
        await self._generic_response(room_id, result, "Chat")

    async def _cmd_ask(self, room_id: str, args: List[str]) -> None:
        """Ask the Murphy librarian a question."""
        if not args:
            plain, html = format_error("Usage: ask <query>")
            await self.send(room_id, plain, html)
            return
        query = " ".join(args)
        result = await self.api.post(
            "/api/librarian/ask",
            json={"query": query, "context": "matrix"},
        )
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            data = result["data"]
            if isinstance(data, dict):
                answer = data.get("answer") or data.get("response") or json.dumps(data, indent=2)
            else:
                answer = str(data)
            plain, html = format_success(answer)
        await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Workflow builder / plan handlers
    # ------------------------------------------------------------------

    async def _cmd_generate(self, room_id: str, args: List[str]) -> None:
        """Generate a plan from a description."""
        if not args or args[0].lower() != "plan":
            plain, html = format_error("Usage: generate plan <description>")
            await self.send(room_id, plain, html)
            return
        description = " ".join(args[1:])
        if not description:
            plain, html = format_error("Please provide a plan description.")
            await self.send(room_id, plain, html)
            return
        result = await self.api.post("/api/forms/plan-generation", json={"description": description})
        await self._generic_response(room_id, result, "Generated Plan")

    async def _cmd_upload(self, room_id: str, args: List[str]) -> None:
        """Upload a plan as JSON."""
        if not args or args[0].lower() != "plan":
            plain, html = format_error("Usage: upload plan <json>")
            await self.send(room_id, plain, html)
            return
        json_str = " ".join(args[1:])
        parsed, err = self._parse_json_arg(json_str)
        if err:
            plain, html = format_error(err)
            await self.send(room_id, plain, html)
            return
        result = await self.api.post("/api/forms/plan-upload", json=parsed)
        await self._generic_response(room_id, result, "Plan Upload")

    # ------------------------------------------------------------------
    # Agents / Org Chart handlers
    # ------------------------------------------------------------------

    async def _cmd_agents(self, room_id: str) -> None:
        """List all agents."""
        result = await self.api.get("/api/agent-dashboard/agents")
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
            await self.send(room_id, plain, html)
            return
        data = result["data"]
        rows: List[List[Any]] = []
        items = data if isinstance(data, list) else (data.get("agents") or data.get("items") or [])
        for ag in items:
            rows.append([ag.get("id", ""), ag.get("persona", ""), ag.get("status", "")])
        plain, html = format_table(["ID", "Persona", "Status"], rows)
        await self.send(room_id, plain, html)

    async def _cmd_agent(self, room_id: str, args: List[str]) -> None:
        """Show agent details or activity."""
        if not args:
            plain, html = format_error("Usage: agent <id> [activity]")
            await self.send(room_id, plain, html)
            return
        agent_id = args[0]
        if len(args) >= 2 and args[1].lower() == "activity":
            result = await self.api.get(f"/api/agent-dashboard/agents/{agent_id}/activity")
            await self._generic_response(room_id, result, f"Agent {agent_id} Activity")
            return
        result = await self.api.get(f"/api/agent-dashboard/agents/{agent_id}")
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            plain, html = format_agent_detail(result["data"] or {})
        await self.send(room_id, plain, html)

    async def _cmd_orgchart(self, room_id: str, args: List[str]) -> None:
        """Show org chart, optionally for a specific task."""
        if args:
            task_id = args[0]
            result = await self.api.get(f"/api/orgchart/{task_id}")
        else:
            result = await self.api.get("/api/orgchart/live")
        await self._generic_response(room_id, result, "Org Chart")

    # ------------------------------------------------------------------
    # HITL handlers
    # ------------------------------------------------------------------

    async def _cmd_hitl(self, room_id: str, args: List[str]) -> None:
        """Handle HITL sub-commands."""
        if not args:
            plain, html = format_error("Usage: hitl pending | hitl respond <id> <action> [reason] | hitl stats")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "pending":
            result = await self.api.get("/api/hitl/interventions/pending")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
                await self.send(room_id, plain, html)
                return
            data = result["data"]
            items = data if isinstance(data, list) else (data.get("interventions") or data.get("items") or [])
            if not items:
                plain, html = format_success("No pending HITL interventions.")
                await self.send(room_id, plain, html)
                return
            messages = [format_hitl_intervention(item) for item in items]
            for plain, html in messages:
                await self.send(room_id, plain, html)
            return

        if sub == "respond":
            # hitl respond <id> approve|reject [reason]
            # hitl respond <id> <message>
            if len(args) < 3:
                plain, html = format_error("Usage: hitl respond <id> approve|reject [reason] | hitl respond <id> <message>")
                await self.send(room_id, plain, html)
                return
            intervention_id = args[1]
            action_or_msg = args[2].lower()
            reason_or_extra = " ".join(args[3:]) if len(args) > 3 else ""

            if action_or_msg in ("approve", "reject"):
                payload: Dict[str, Any] = {"action": action_or_msg}
                if reason_or_extra:
                    payload["reason"] = reason_or_extra
            else:
                message_text = " ".join(args[2:])
                payload = {"action": "respond", "message": message_text}

            result = await self.api.post(
                f"/api/hitl/interventions/{intervention_id}/respond",
                json=payload,
            )
            await self._generic_response(room_id, result, "HITL Response")
            return

        if sub == "stats":
            result = await self.api.get("/api/hitl/statistics")
            await self._generic_response(room_id, result, "HITL Statistics")
            return

        plain, html = format_error(f"Unknown hitl sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Email / Comms handlers
    # ------------------------------------------------------------------

    async def _cmd_email(self, room_id: str, args: List[str], raw_body: str) -> None:
        """Handle email sub-commands."""
        if not args:
            plain, html = format_error("Usage: email send <to> <subject> :: <body> | email status | email test")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "send":
            # Parse: email send <to> <subject> :: <body>
            # Find the '::' separator in the raw message text after 'email send'
            prefix_marker = self.cfg.command_prefix
            # Locate "email send" region in raw_body
            lowered = raw_body.lower()
            send_idx = lowered.find("email send")
            if send_idx == -1:
                plain, html = format_error("Usage: email send <to> <subject> :: <body>")
                await self.send(room_id, plain, html)
                return
            after_send = raw_body[send_idx + len("email send"):].strip()
            if "::" not in after_send:
                plain, html = format_error("Usage: email send <to> <subject> :: <body>  (use '::' to separate subject from body)")
                await self.send(room_id, plain, html)
                return
            before_sep, body_text = after_send.split("::", 1)
            before_tokens = before_sep.split()
            if len(before_tokens) < 2:
                plain, html = format_error("Usage: email send <to> <subject> :: <body>")
                await self.send(room_id, plain, html)
                return
            to_addr = before_tokens[0]
            subject = " ".join(before_tokens[1:])
            email_body = body_text.strip()
            result = await self.api.post(
                "/api/notifications/send",
                json={
                    "to": to_addr,
                    "subject": subject,
                    "body": email_body,
                    "channel": "email",
                    "source": "matrix",
                },
            )
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
            else:
                plain, html = format_email_result(result["data"])
            await self.send(room_id, plain, html)
            return

        if sub == "status":
            result = await self.api.get("/api/email/status")
            await self._generic_response(room_id, result, "Email Status")
            return

        if sub == "test":
            result = await self.api.post("/api/email/test")
            await self._generic_response(room_id, result, "Email Test")
            return

        plain, html = format_error(f"Unknown email sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    async def _cmd_notify(self, room_id: str, args: List[str], raw_body: str) -> None:
        """Handle notify sub-commands."""
        if not args:
            plain, html = format_error("Usage: notify <subject> :: <body> | notify template <id> <json> | notify channels")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "template":
            if len(args) < 3:
                plain, html = format_error("Usage: notify template <template_id> <json_vars>")
                await self.send(room_id, plain, html)
                return
            template_id = args[1]
            json_str = " ".join(args[2:])
            parsed, err = self._parse_json_arg(json_str)
            if err:
                plain, html = format_error(err)
                await self.send(room_id, plain, html)
                return
            result = await self.api.post(
                "/api/notifications/send-template",
                json={"template_id": template_id, "variables": parsed},
            )
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
            else:
                plain, html = format_notification_result(result["data"])
            await self.send(room_id, plain, html)
            return

        if sub == "channels":
            result = await self.api.get("/api/notifications/channels")
            await self._generic_response(room_id, result, "Notification Channels")
            return

        # notify <subject> :: <body>
        lowered = raw_body.lower()
        notify_idx = lowered.find("notify ")
        if notify_idx == -1 or "::" not in raw_body:
            plain, html = format_error("Usage: notify <subject> :: <body>")
            await self.send(room_id, plain, html)
            return
        after_notify = raw_body[notify_idx + len("notify "):].strip()
        if "::" not in after_notify:
            plain, html = format_error("Usage: notify <subject> :: <body>  (use '::' to separate subject from body)")
            await self.send(room_id, plain, html)
            return
        subject, body_text = after_notify.split("::", 1)
        result = await self.api.post(
            "/api/notifications/send",
            json={
                "subject": subject.strip(),
                "body": body_text.strip(),
                "priority": "normal",
                "source": "matrix",
            },
        )
        if not result["ok"]:
            plain, html = format_error(result.get("error") or "Request failed")
        else:
            plain, html = format_notification_result(result["data"])
        await self.send(room_id, plain, html)

    async def _cmd_comms(self, room_id: str, args: List[str]) -> None:
        """Handle comms sub-commands."""
        if not args:
            plain, html = format_error("Usage: comms feed | comms stats")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "feed":
            result = await self.api.get("/api/comms/activity")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
                await self.send(room_id, plain, html)
                return
            data = result["data"]
            activities = data if isinstance(data, list) else (data.get("activities") or data.get("items") or [])
            plain, html = format_comms_activity_feed(activities)
            await self.send(room_id, plain, html)
            return

        if sub == "stats":
            result = await self.api.get("/api/comms/stats")
            await self._generic_response(room_id, result, "Comms Stats")
            return

        plain, html = format_error(f"Unknown comms sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Integrations handlers
    # ------------------------------------------------------------------

    async def _cmd_integrations(self, room_id: str, args: List[str]) -> None:
        """List integrations."""
        if args and args[0].lower() == "all":
            result = await self.api.get("/api/integrations", params={"include_inactive": "true"})
        else:
            result = await self.api.get("/api/integrations")
        await self._generic_response(room_id, result, "Integrations")

    async def _cmd_integration(self, room_id: str, args: List[str]) -> None:
        """Show, test, or execute an integration."""
        if not args:
            plain, html = format_error("Usage: integration <id> [test | execute <method> [json]]")
            await self.send(room_id, plain, html)
            return

        integration_id = args[0]

        if len(args) == 1:
            result = await self.api.get(f"/api/integrations/{integration_id}")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
            else:
                plain, html = format_integration_status(result["data"] or {})
            await self.send(room_id, plain, html)
            return

        sub = args[1].lower()

        if sub == "test":
            result = await self.api.post(f"/api/integrations/{integration_id}/test")
            await self._generic_response(room_id, result, f"Integration {integration_id} Test")
            return

        if sub == "execute":
            if len(args) < 3:
                plain, html = format_error("Usage: integration <id> execute <method> [json]")
                await self.send(room_id, plain, html)
                return
            method = args[2]
            params: Any = {}
            if len(args) > 3:
                json_str = " ".join(args[3:])
                parsed, err = self._parse_json_arg(json_str)
                if err:
                    plain, html = format_error(err)
                    await self.send(room_id, plain, html)
                    return
                params = parsed
            result = await self.api.post(
                f"/api/integrations/{integration_id}/execute",
                json={"method": method, "params": params},
            )
            await self._generic_response(room_id, result, f"Integration {integration_id} Execute")
            return

        plain, html = format_error(f"Unknown integration sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    async def _cmd_connectors(self, room_id: str) -> None:
        """List all connectors."""
        result = await self.api.get("/api/connectors")
        await self._generic_response(room_id, result, "Connectors")

    async def _cmd_connector(self, room_id: str, args: List[str]) -> None:
        """Show a connector by ID."""
        if not args:
            plain, html = format_error("Usage: connector <id>")
            await self.send(room_id, plain, html)
            return
        connector_id = args[0]
        result = await self.api.get(f"/api/connectors/{connector_id}")
        await self._generic_response(room_id, result, f"Connector {connector_id}")

    # ------------------------------------------------------------------
    # Webhook handlers
    # ------------------------------------------------------------------

    async def _cmd_webhooks(self, room_id: str) -> None:
        """List webhook subscriptions."""
        result = await self.api.get("/api/webhooks/subscriptions")
        await self._generic_response(room_id, result, "Webhook Subscriptions")

    async def _cmd_webhook(self, room_id: str, args: List[str]) -> None:
        """Handle webhook sub-commands."""
        if not args:
            plain, html = format_error("Usage: webhook <id> | webhook create <json> | webhook fire <event_type> [json] | webhook deliveries <sub_id> | webhook stats")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "stats":
            result = await self.api.get("/api/webhooks/stats")
            await self._generic_response(room_id, result, "Webhook Stats")
            return

        if sub == "create":
            json_str = " ".join(args[1:])
            parsed, err = self._parse_json_arg(json_str)
            if err:
                plain, html = format_error(err)
                await self.send(room_id, plain, html)
                return
            result = await self.api.post("/api/webhooks/subscriptions", json=parsed)
            await self._generic_response(room_id, result, "Webhook Created")
            return

        if sub == "fire":
            if len(args) < 2:
                plain, html = format_error("Usage: webhook fire <event_type> [json]")
                await self.send(room_id, plain, html)
                return
            event_type = args[1]
            data: Any = {}
            if len(args) > 2:
                json_str = " ".join(args[2:])
                parsed, err = self._parse_json_arg(json_str)
                if err:
                    plain, html = format_error(err)
                    await self.send(room_id, plain, html)
                    return
                data = parsed
            result = await self.api.post(
                "/api/webhooks/events",
                json={"event_type": event_type, "data": data},
            )
            await self._generic_response(room_id, result, "Webhook Fired")
            return

        if sub == "deliveries":
            if len(args) < 2:
                plain, html = format_error("Usage: webhook deliveries <sub_id>")
                await self.send(room_id, plain, html)
                return
            sub_id = args[1]
            result = await self.api.get(f"/api/webhooks/deliveries/{sub_id}")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
                await self.send(room_id, plain, html)
                return
            data = result["data"]
            deliveries = data if isinstance(data, list) else (data.get("deliveries") or data.get("items") or [data])
            for delivery in deliveries[:self._MAX_DELIVERIES_DISPLAY]:
                plain, html = format_webhook_delivery(delivery)
                await self.send(room_id, plain, html)
            return

        # webhook <id>
        webhook_id = args[0]
        result = await self.api.get(f"/api/webhooks/subscriptions/{webhook_id}")
        await self._generic_response(room_id, result, f"Webhook {webhook_id}")

    # ------------------------------------------------------------------
    # Service Module handlers
    # ------------------------------------------------------------------

    async def _cmd_service(self, room_id: str, args: List[str]) -> None:
        """Handle service sub-commands."""
        if not args:
            plain, html = format_error("Usage: service tickets | service ticket <id> | service catalog | service kb search <query> | service sla | service csat")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "tickets":
            result = await self.api.get("/api/service/tickets")
            await self._generic_response(room_id, result, "Service Tickets")
            return

        if sub == "ticket":
            if len(args) < 2:
                plain, html = format_error("Usage: service ticket <id> | service ticket create <json> | service ticket <id> assign <agent>")
                await self.send(room_id, plain, html)
                return

            ticket_arg = args[1].lower()

            if ticket_arg == "create":
                json_str = " ".join(args[2:])
                parsed, err = self._parse_json_arg(json_str)
                if err:
                    plain, html = format_error(err)
                    await self.send(room_id, plain, html)
                    return
                result = await self.api.post("/api/service/tickets", json=parsed)
                await self._generic_response(room_id, result, "Ticket Created")
                return

            ticket_id = args[1]
            if len(args) >= 4 and args[2].lower() == "assign":
                agent = args[3]
                result = await self.api.post(
                    f"/api/service/tickets/{ticket_id}/assign",
                    json={"agent": agent},
                )
                await self._generic_response(room_id, result, f"Ticket {ticket_id} Assigned")
                return

            result = await self.api.get(f"/api/service/tickets/{ticket_id}")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
            else:
                plain, html = format_service_ticket(result["data"] or {})
            await self.send(room_id, plain, html)
            return

        if sub == "catalog":
            result = await self.api.get("/api/service/catalogs")
            await self._generic_response(room_id, result, "Service Catalog")
            return

        if sub == "kb":
            if len(args) < 3 or args[1].lower() != "search":
                plain, html = format_error("Usage: service kb search <query>")
                await self.send(room_id, plain, html)
                return
            query = " ".join(args[2:])
            result = await self.api.get("/api/service/kb/search", params={"q": query})
            await self._generic_response(room_id, result, "KB Search")
            return

        if sub == "sla":
            result = await self.api.get("/api/service/sla")
            await self._generic_response(room_id, result, "Service SLA")
            return

        if sub == "csat":
            result = await self.api.get("/api/service/csat/average")
            await self._generic_response(room_id, result, "CSAT Average")
            return

        plain, html = format_error(f"Unknown service sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Cost handlers
    # ------------------------------------------------------------------

    async def _cmd_costs(self, room_id: str, args: List[str]) -> None:
        """Handle costs sub-commands."""
        if not args:
            result = await self.api.get("/api/coa/summary")
            if not result["ok"]:
                plain, html = format_error(result.get("error") or "Request failed")
            else:
                plain, html = format_cost_summary(result["data"] or {})
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "breakdown":
            result = await self.api.get("/api/coa/resources")
            await self._generic_response(room_id, result, "Costs Breakdown")
            return

        if sub == "by-bot":
            result = await self.api.get("/api/costs/by-bot")
            await self._generic_response(room_id, result, "Costs by Bot")
            return

        if sub == "budget":
            result = await self.api.get("/api/costs/budget")
            await self._generic_response(room_id, result, "Costs Budget")
            return

        if sub == "optimize":
            result = await self.api.get("/api/coa/recommendations")
            await self._generic_response(room_id, result, "Cost Optimisations")
            return

        if sub == "record":
            json_str = " ".join(args[1:])
            parsed, err = self._parse_json_arg(json_str)
            if err:
                plain, html = format_error(err)
                await self.send(room_id, plain, html)
                return
            result = await self.api.post("/api/coa/spend", json=parsed)
            await self._generic_response(room_id, result, "Cost Recorded")
            return

        plain, html = format_error(f"Unknown costs sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    # ------------------------------------------------------------------
    # Forms / Corrections handlers
    # ------------------------------------------------------------------

    async def _cmd_form(self, room_id: str, args: List[str]) -> None:
        """Handle form sub-commands."""
        form_routes = {
            "task": "/api/forms/task-submission",
            "validate": "/api/forms/validate",
            "correct": "/api/forms/correction",
        }
        if not args or args[0].lower() not in form_routes:
            plain, html = format_error("Usage: form task|validate|correct <json>")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()
        json_str = " ".join(args[1:])
        parsed, err = self._parse_json_arg(json_str)
        if err:
            plain, html = format_error(err)
            await self.send(room_id, plain, html)
            return
        result = await self.api.post(form_routes[sub], json=parsed)
        await self._generic_response(room_id, result, f"Form {sub.capitalize()}")

    async def _cmd_corrections(self, room_id: str, args: List[str]) -> None:
        """Handle corrections sub-commands."""
        corrections_routes = {
            "patterns": "/api/corrections/patterns",
            "stats": "/api/corrections/stats",
            "training": "/api/corrections/training",
        }
        if not args or args[0].lower() not in corrections_routes:
            plain, html = format_error("Usage: corrections patterns|stats|training")
            await self.send(room_id, plain, html)
            return
        sub = args[0].lower()
        result = await self.api.get(corrections_routes[sub])
        await self._generic_response(room_id, result, f"Corrections {sub.capitalize()}")

    # ------------------------------------------------------------------
    # MFGC / LLM / MFM handlers
    # ------------------------------------------------------------------

    async def _cmd_mfgc(self, room_id: str, args: List[str]) -> None:
        """Handle MFGC sub-commands."""
        routes = {
            "state": "/api/mfgc/state",
            "config": "/api/mfgc/config",
            "setup": "/api/mfgc/setup",
        }
        if not args or args[0].lower() not in routes:
            plain, html = format_error("Usage: mfgc state|config|setup")
            await self.send(room_id, plain, html)
            return
        sub = args[0].lower()
        result = await self.api.get(routes[sub])
        await self._generic_response(room_id, result, f"MFGC {sub.capitalize()}")

    async def _cmd_llm(self, room_id: str, args: List[str]) -> None:
        """Handle LLM sub-commands."""
        if not args:
            plain, html = format_error("Usage: llm status | llm configure <provider> <key> | llm test")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "status":
            result = await self.api.get("/api/llm/status")
            await self._generic_response(room_id, result, "LLM Status")
            return

        if sub == "configure":
            if len(args) < 3:
                plain, html = format_error("Usage: llm configure <provider> <key>")
                await self.send(room_id, plain, html)
                return
            provider = args[1]
            api_key = args[2]
            result = await self.api.post(
                "/api/llm/configure",
                json={"provider": provider, "api_key": api_key},
            )
            await self._generic_response(room_id, result, "LLM Configure")
            return

        if sub == "test":
            result = await self.api.post("/api/llm/test")
            await self._generic_response(room_id, result, "LLM Test")
            return

        plain, html = format_error(f"Unknown llm sub-command '{sub}'.")
        await self.send(room_id, plain, html)

    async def _cmd_mfm(self, room_id: str, args: List[str]) -> None:
        """Handle MFM sub-commands."""
        routes = {
            "status": "/api/mfm/status",
            "metrics": "/api/mfm/metrics",
        }
        if not args or args[0].lower() not in routes:
            plain, html = format_error("Usage: mfm status|metrics")
            await self.send(room_id, plain, html)
            return
        sub = args[0].lower()
        result = await self.api.get(routes[sub])
        await self._generic_response(room_id, result, f"MFM {sub.capitalize()}")

    # ------------------------------------------------------------------
    # Onboarding / IP handlers
    # ------------------------------------------------------------------

    async def _cmd_onboarding(self, room_id: str, args: List[str]) -> None:
        """Handle onboarding sub-commands."""
        routes = {
            "status": "/api/onboarding/status",
            "questions": "/api/onboarding/questions",
        }
        if not args or args[0].lower() not in routes:
            plain, html = format_error("Usage: onboarding status|questions")
            await self.send(room_id, plain, html)
            return
        sub = args[0].lower()
        result = await self.api.get(routes[sub])
        await self._generic_response(room_id, result, f"Onboarding {sub.capitalize()}")

    async def _cmd_ip(self, room_id: str, args: List[str]) -> None:
        """Handle IP sub-commands."""
        if not args or args[0].lower() != "assets":
            plain, html = format_error("Usage: ip assets")
            await self.send(room_id, plain, html)
            return
        result = await self.api.get("/api/ip/assets")
        await self._generic_response(room_id, result, "IP Assets")

    # ------------------------------------------------------------------
    # Module Compiler handlers
    # ------------------------------------------------------------------

    async def _cmd_module(self, room_id: str, args: List[str]) -> None:
        """Handle module sub-commands."""
        if not args:
            plain, html = format_error("Usage: module <id> | module compile <source_path>")
            await self.send(room_id, plain, html)
            return

        sub = args[0].lower()

        if sub == "compile":
            if len(args) < 2:
                plain, html = format_error("Usage: module compile <source_path>")
                await self.send(room_id, plain, html)
                return
            source_path = args[1]
            result = await self.api.post(
                "/api/module-compiler/compile",
                json={"source_path": source_path},
            )
            await self._generic_response(room_id, result, "Module Compile")
            return

        # module <id>
        module_id = args[0]
        result = await self.api.get(f"/api/module-compiler/modules/{module_id}")
        await self._generic_response(room_id, result, f"Module {module_id}")

    async def _cmd_capability(self, room_id: str, args: List[str]) -> None:
        """Show a capability by name."""
        if not args:
            plain, html = format_error("Usage: capability <name>")
            await self.send(room_id, plain, html)
            return
        name = args[0]
        result = await self.api.get(f"/api/module-compiler/capabilities/{name}")
        await self._generic_response(room_id, result, f"Capability: {name}")

    # ------------------------------------------------------------------
    # Bot Management handlers
    # ------------------------------------------------------------------

    async def _cmd_bots(self, room_id: str) -> None:
        """List all bots."""
        base = self.cfg.murphy_api_url.replace("/api", "").rstrip("/")
        result = await self.api.get("/bots")
        # Attempt against the stripped base if the api url includes /api
        if not result["ok"]:
            # Try fetching directly from the non-api base
            try:
                resp = await self.api.http.get(f"{base}/bots")
                self.api.cb.record_success()
                try:
                    data: Any = resp.json()
                except Exception:
                    data = resp.text
                result = {"ok": True, "data": data, "error": None, "status": resp.status_code}
            except Exception as exc:
                result = {"ok": False, "data": None, "error": str(exc), "status": 0}
        await self._generic_response(room_id, result, "Bots")

    async def _cmd_bot(self, room_id: str, args: List[str]) -> None:
        """Perform an action on a specific bot."""
        # bot <id> action <json>
        if len(args) < 3 or args[1].lower() != "action":
            plain, html = format_error("Usage: bot <id> action <json>")
            await self.send(room_id, plain, html)
            return
        bot_id = args[0]
        json_str = " ".join(args[2:])
        parsed, err = self._parse_json_arg(json_str)
        if err:
            plain, html = format_error(err)
            await self.send(room_id, plain, html)
            return
        base = self.cfg.murphy_api_url.replace("/api", "").rstrip("/")
        try:
            resp = await self.api.http.post(f"{base}/bots/{bot_id}/action", json=parsed)
            self.api.cb.record_success()
            try:
                data: Any = resp.json()
            except Exception:
                data = resp.text
            result: Dict[str, Any] = {"ok": True, "data": data, "error": None, "status": resp.status_code}
        except Exception as exc:
            self.api.cb.record_failure()
            result = {"ok": False, "data": None, "error": str(exc), "status": 0}
        await self._generic_response(room_id, result, f"Bot {bot_id} Action")

    # ------------------------------------------------------------------
    # Help / Navigation handlers
    # ------------------------------------------------------------------

    async def _cmd_help(self, room_id: str, args: List[str]) -> None:
        """Show help, optionally filtered by category."""
        if args:
            category_filter = " ".join(args).lower()
            filtered = {
                k: v
                for k, v in HELP_CATEGORIES.items()
                if category_filter in k.lower()
            }
            if not filtered:
                # Try partial match on command text
                filtered = {
                    k: [c for c in v if category_filter in c.lower()]
                    for k, v in HELP_CATEGORIES.items()
                }
                filtered = {k: v for k, v in filtered.items() if v}
            categories = filtered if filtered else HELP_CATEGORIES
        else:
            categories = HELP_CATEGORIES
        plain, html = format_help(categories)
        await self.send(room_id, plain, html)

    async def _cmd_jargon(self, room_id: str, args: List[str]) -> None:
        """Show jargon term(s)."""
        if not args:
            plain, html = format_jargon_list()
            await self.send(room_id, plain, html)
            return

        term = " ".join(args).lower()
        all_terms = get_all_jargon()
        # Case-insensitive lookup
        definition: Optional[str] = None
        matched_term: str = term
        for key, val in all_terms.items():
            if key.lower() == term:
                definition = val
                matched_term = key
                break

        if definition is None:
            # Partial match fallback
            for key, val in all_terms.items():
                if term in key.lower():
                    definition = val
                    matched_term = key
                    break

        if definition is None:
            plain, html = format_error(f"Jargon term '{term}' not found.")
        else:
            plain, html = format_jargon(matched_term, definition)
        await self.send(room_id, plain, html)


__all__ = ["MatrixBot", "MurphyAPIClient", "CircuitBreaker"]
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
