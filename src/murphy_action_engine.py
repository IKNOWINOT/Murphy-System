"""
Murphy System - Murphy Action Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Large Action Model interface providing structured function/tool calling for Murphy's LLM routing.
Integrates with: deterministic_routing_engine.py, api_gateway_adapter.py
"""

import functools
import importlib
import logging
import os
import sys
import time
import uuid
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ActionParameter(BaseModel):
    """Describes a single parameter accepted by a registered action."""

    name: str = Field(..., description="Parameter name as used in the function signature.")
    description: str = Field(..., description="Human-readable explanation of the parameter.")
    type: str = Field(..., description="JSON Schema primitive type (string, number, boolean, object, array).")
    required: bool = Field(default=True, description="Whether the parameter must be supplied by the caller.")
    default: Optional[Any] = Field(default=None, description="Default value when the parameter is omitted.")


class ActionSchema(BaseModel):
    """Full schema definition for a single callable action."""

    name: str = Field(..., description="Unique action identifier used for registration and dispatch.")
    description: str = Field(..., description="What this action does and when to invoke it.")
    parameters: List[ActionParameter] = Field(default_factory=list, description="Ordered list of accepted parameters.")
    returns: str = Field(default="Any", description="Description or type annotation of the return value.")
    examples: List[str] = Field(default_factory=list, description="Illustrative call examples in plain text.")


class ActionResult(BaseModel):
    """Outcome produced by executing a single action."""

    action_name: str = Field(..., description="Name of the action that was executed.")
    success: bool = Field(..., description="True if execution completed without an unhandled error.")
    output: Any = Field(default=None, description="Return value produced by the action callable.")
    error: Optional[str] = Field(default=None, description="Error message when success is False.")
    cost_usd: float = Field(default=0.0, description="Estimated cost in US dollars for this invocation.")
    duration_ms: float = Field(default=0.0, description="Wall-clock execution time in milliseconds.")
    confidence: float = Field(default=1.0, description="Planner confidence score for this action (0–1).")


# ---------------------------------------------------------------------------
# ActionRegistry
# ---------------------------------------------------------------------------


class ActionRegistry:
    """
    Thread-safe registry that maps action names to their schemas and callables.

    Usage
    -----
    registry = ActionRegistry()
    registry.register(schema, my_function)
    schema = registry.get("my_function")
    all_schemas = registry.list_all()
    ok = registry.validate_call("my_function", {"param": "value"})
    """

    def __init__(self) -> None:
        self._lock: Lock = Lock()
        self._schemas: Dict[str, ActionSchema] = {}
        self._callables: Dict[str, Callable] = {}

    def register(self, schema: ActionSchema, fn: Callable) -> None:
        """Register an action schema paired with its callable implementation."""
        with self._lock:
            if schema.name in self._schemas:
                logger.debug("Re-registering action '%s'; overwriting previous entry.", schema.name)
            self._schemas[schema.name] = schema
            self._callables[schema.name] = fn
            logger.debug("Registered action '%s'.", schema.name)

    def get(self, name: str) -> Optional[ActionSchema]:
        """Return the schema for *name*, or None if not registered."""
        with self._lock:
            return self._schemas.get(name)

    def get_callable(self, name: str) -> Optional[Callable]:
        """Return the callable for *name*, or None if not registered."""
        with self._lock:
            return self._callables.get(name)

    def list_all(self) -> List[ActionSchema]:
        """Return a snapshot of all registered action schemas."""
        with self._lock:
            return list(self._schemas.values())

    def validate_call(self, name: str, args: Dict[str, Any]) -> bool:
        """
        Validate that *args* satisfies the parameter contract for action *name*.

        Returns True when all required parameters are present; False otherwise.
        """
        with self._lock:
            schema = self._schemas.get(name)
        if schema is None:
            logger.warning("validate_call: action '%s' is not registered.", name)
            return False
        for param in schema.parameters:
            if param.required and param.name not in args:
                logger.debug(
                    "validate_call: required parameter '%s' missing for action '%s'.",
                    param.name,
                    name,
                )
                return False
        return True


# ---------------------------------------------------------------------------
# Circuit-breaker state
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    """Per-action circuit breaker that trips after three consecutive failures."""

    TRIP_THRESHOLD: int = 3
    RECOVERY_SECONDS: float = 60.0

    def __init__(self) -> None:
        self._consecutive_failures: int = 0
        self._tripped_at: float = 0.0
        self._tripped: bool = False

    @property
    def is_open(self) -> bool:
        """Return True when the circuit is tripped and the recovery window has not elapsed."""
        if not self._tripped:
            return False
        elapsed = time.monotonic() - self._tripped_at
        if elapsed >= self.RECOVERY_SECONDS:
            self._tripped = False
            self._consecutive_failures = 0
            logger.debug("Circuit breaker recovered after %.1fs.", elapsed)
            return False
        return True

    def record_success(self) -> None:
        """Reset the failure counter on a successful call."""
        self._consecutive_failures = 0
        self._tripped = False

    def record_failure(self) -> None:
        """Increment the failure counter and trip the breaker when the threshold is reached."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.TRIP_THRESHOLD:
            self._tripped = True
            self._tripped_at = time.monotonic()
            logger.warning(
                "Circuit breaker tripped after %d consecutive failures.",
                self._consecutive_failures,
            )


# ---------------------------------------------------------------------------
# ActionPlanner
# ---------------------------------------------------------------------------

# Keyword groups used by the rule-based planner to recognise intent tokens.
_KEYWORD_MAP: Dict[str, List[str]] = {
    "search": ["search", "find", "look up", "query", "fetch", "retrieve"],
    "create": ["create", "make", "build", "generate", "produce", "write"],
    "update": ["update", "edit", "modify", "change", "patch", "set"],
    "delete": ["delete", "remove", "destroy", "drop", "purge"],
    "analyse": ["analyse", "analyze", "inspect", "evaluate", "assess", "review", "check"],
    "summarise": ["summarise", "summarize", "condense", "brief", "overview"],
    "send": ["send", "dispatch", "emit", "notify", "publish", "post"],
    "list": ["list", "show", "display", "enumerate", "get all"],
}


class ActionPlanner:
    """
    Rule-based planner that maps a natural-language task string to an ordered
    sequence of ``{action_name, args}`` dicts drawn from *available_actions*.

    No LLM is required; matching is done via keyword scanning.
    """

    def plan(self, task: str, available_actions: List[ActionSchema]) -> List[Dict[str, Any]]:
        """
        Produce an ordered execution plan for *task* using *available_actions*.

        Parameters
        ----------
        task:
            Natural-language description of what should be accomplished.
        available_actions:
            Schemas of all actions the executor has access to.

        Returns
        -------
        List of ``{"action_name": str, "args": dict, "confidence": float}`` dicts
        in intended execution order.
        """
        task_lower = task.lower()
        matched_intents: List[str] = []
        for intent, keywords in _KEYWORD_MAP.items():
            if any(kw in task_lower for kw in keywords):
                matched_intents.append(intent)

        action_lookup: Dict[str, ActionSchema] = {s.name: s for s in available_actions}

        plan: List[Dict[str, Any]] = []
        used: set = set()

        for intent in matched_intents:
            for schema in available_actions:
                if schema.name in used:
                    continue
                name_lower = schema.name.lower()
                desc_lower = schema.description.lower()
                if intent in name_lower or intent in desc_lower:
                    plan.append(
                        {
                            "action_name": schema.name,
                            "args": self._default_args(schema),
                            "confidence": 0.75,
                        }
                    )
                    used.add(schema.name)
                    break

        if not plan:
            tokens = task_lower.split()
            for schema in available_actions:
                if schema.name in used:
                    continue
                name_tokens = set(schema.name.lower().replace("_", " ").split())
                if name_tokens & set(tokens):
                    plan.append(
                        {
                            "action_name": schema.name,
                            "args": self._default_args(schema),
                            "confidence": 0.5,
                        }
                    )
                    used.add(schema.name)

        if not plan and available_actions:
            first = available_actions[0]
            logger.debug("ActionPlanner: no keywords matched; defaulting to first action '%s'.", first.name)
            plan.append(
                {
                    "action_name": first.name,
                    "args": self._default_args(first),
                    "confidence": 0.25,
                }
            )

        logger.debug("ActionPlanner produced %d step(s) for task: %r", len(plan), task[:80])
        return plan

    @staticmethod
    def _default_args(schema: ActionSchema) -> Dict[str, Any]:
        """Build a minimal args dict populated with parameter defaults."""
        return {
            p.name: p.default
            for p in schema.parameters
            if not p.required and p.default is not None
        }


# ---------------------------------------------------------------------------
# ActionExecutor
# ---------------------------------------------------------------------------


class ActionExecutor:
    """
    Executes an ordered action plan with per-action timeout, retry logic,
    and a circuit breaker that trips after three consecutive failures and
    recovers automatically after sixty seconds.
    """

    def __init__(self) -> None:
        self._breakers: Dict[str, _CircuitBreaker] = {}
        self._lock: Lock = Lock()

    def _get_breaker(self, action_name: str) -> _CircuitBreaker:
        with self._lock:
            if action_name not in self._breakers:
                self._breakers[action_name] = _CircuitBreaker()
            return self._breakers[action_name]

    def execute(
        self,
        plan: List[Dict[str, Any]],
        registry: ActionRegistry,
        timeout_s: float = 30.0,
        max_retries: int = 3,
    ) -> List[ActionResult]:
        """
        Execute every step in *plan* using callables looked up from *registry*.

        Parameters
        ----------
        plan:
            Output of :py:meth:`ActionPlanner.plan`.
        registry:
            Registry that maps action names to callables.
        timeout_s:
            Per-action wall-clock timeout in seconds (enforced via a deadline check).
        max_retries:
            Maximum number of attempts for each action before recording failure.

        Returns
        -------
        List of :class:`ActionResult` in the same order as *plan*.
        """
        results: List[ActionResult] = []
        for step in plan:
            action_name: str = step.get("action_name", "")
            args: Dict[str, Any] = step.get("args", {})
            confidence: float = float(step.get("confidence", 1.0))
            result = self._execute_step(action_name, args, confidence, registry, timeout_s, max_retries)
            results.append(result)
        return results

    def _execute_step(
        self,
        action_name: str,
        args: Dict[str, Any],
        confidence: float,
        registry: ActionRegistry,
        timeout_s: float,
        max_retries: int,
    ) -> ActionResult:
        """Execute a single plan step, honouring the circuit breaker and retry policy."""
        breaker = self._get_breaker(action_name)

        if breaker.is_open:
            logger.warning("Circuit breaker open for action '%s'; skipping.", action_name)
            return ActionResult(
                action_name=action_name,
                success=False,
                error="Circuit breaker open; action skipped.",
                confidence=confidence,
            )

        fn = registry.get_callable(action_name)
        if fn is None:
            logger.error("Action '%s' not found in registry.", action_name)
            return ActionResult(
                action_name=action_name,
                success=False,
                error=f"Action '{action_name}' is not registered.",
                confidence=confidence,
            )

        attempt = 0
        last_error: str = ""
        deadline = time.monotonic() + timeout_s

        while attempt < max_retries:
            attempt += 1
            if time.monotonic() > deadline:
                last_error = f"Timeout exceeded ({timeout_s}s) before attempt {attempt}."
                logger.warning("Action '%s' timed out on attempt %d.", action_name, attempt)
                breaker.record_failure()
                break

            start_ns = time.perf_counter_ns()
            try:
                output = fn(**args)
                duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                breaker.record_success()
                logger.debug(
                    "Action '%s' succeeded on attempt %d in %.2fms.",
                    action_name,
                    attempt,
                    duration_ms,
                )
                return ActionResult(
                    action_name=action_name,
                    success=True,
                    output=output,
                    duration_ms=duration_ms,
                    confidence=confidence,
                )
            except Exception as exc:
                duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                last_error = str(exc)
                breaker.record_failure()
                logger.warning(
                    "Action '%s' failed on attempt %d/%d: %s",
                    action_name,
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        backoff = 0.1 * (2 ** (attempt - 1))
                        time.sleep(min(backoff, remaining))

        return ActionResult(
            action_name=action_name,
            success=False,
            error=last_error,
            confidence=confidence,
        )


# ---------------------------------------------------------------------------
# Global registry and decorator
# ---------------------------------------------------------------------------

_GLOBAL_REGISTRY: ActionRegistry = ActionRegistry()
_REGISTRY_LOCK: Lock = Lock()


def get_global_registry() -> ActionRegistry:
    """Return the module-level singleton :class:`ActionRegistry`."""
    return _GLOBAL_REGISTRY


def murphy_action(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[List[ActionParameter]] = None,
    returns: str = "Any",
    examples: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator that registers the decorated function in the global :class:`ActionRegistry`.

    Parameters
    ----------
    name:
        Override the action name; defaults to the function's ``__name__``.
    description:
        Human-readable description of what the action does.
    parameters:
        Explicit parameter list; when omitted an empty list is used.
    returns:
        Description of the return value.
    examples:
        Illustrative usage examples.

    Example
    -------
    .. code-block:: python

        @murphy_action(description="Return the current UTC timestamp.")
        def get_timestamp() -> str:
            import datetime
            return datetime.datetime.now(datetime.timezone.utc).isoformat()
    """

    def decorator(fn: Callable) -> Callable:
        action_name = name if name is not None else fn.__name__
        schema = ActionSchema(
            name=action_name,
            description=description or (fn.__doc__ or "").strip().split("\n")[0],
            parameters=parameters or [],
            returns=returns,
            examples=examples or [],
        )
        _GLOBAL_REGISTRY.register(schema, fn)
        logger.debug("@murphy_action registered '%s'.", action_name)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Action discovery
# ---------------------------------------------------------------------------


def discover_actions(src_dir: str) -> int:
    """
    Scan *src_dir* for Python modules, import them, and count newly registered
    ``@murphy_action`` decorated functions.

    Modules that fail to import are logged at WARNING level and skipped.

    Parameters
    ----------
    src_dir:
        Absolute or relative path to the directory to scan.

    Returns
    -------
    Number of actions registered in the global registry after scanning.
    """
    src_dir = os.path.abspath(src_dir)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    before = len(_GLOBAL_REGISTRY.list_all())
    loaded = 0

    for entry in os.listdir(src_dir):
        if not entry.endswith(".py") or entry.startswith("_"):
            continue
        module_name = entry[:-3]
        try:
            importlib.import_module(module_name)
            loaded += 1
        except ImportError as exc:
            logger.warning("discover_actions: could not import '%s': %s", module_name, exc)
        except Exception as exc:
            logger.warning("discover_actions: error loading '%s': %s", module_name, exc)

    after = len(_GLOBAL_REGISTRY.list_all())
    newly_registered = after - before
    logger.info(
        "discover_actions: scanned %d module(s) in '%s', found %d new action(s).",
        loaded,
        src_dir,
        newly_registered,
    )
    return after


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def build_action_schema(
    name: str,
    description: str,
    parameters: Optional[List[Dict[str, Any]]] = None,
    returns: str = "Any",
    examples: Optional[List[str]] = None,
) -> ActionSchema:
    """
    Construct an :class:`ActionSchema` from plain dicts, useful for dynamic registration.

    Each dict in *parameters* must contain at minimum ``name``, ``description``,
    and ``type`` keys.
    """
    parsed: List[ActionParameter] = []
    for p in (parameters or []):
        parsed.append(
            ActionParameter(
                name=p["name"],
                description=p.get("description", ""),
                type=p.get("type", "string"),
                required=p.get("required", True),
                default=p.get("default"),
            )
        )
    return ActionSchema(
        name=name,
        description=description,
        parameters=parsed,
        returns=returns,
        examples=examples or [],
    )


def summarise_results(results: List[ActionResult]) -> Dict[str, Any]:
    """
    Produce a summary dict for a list of :class:`ActionResult` objects.

    Includes success rate, average duration, and total estimated cost.
    """
    total = len(results)
    successes = sum(1 for r in results if r.success)
    total_cost = sum(r.cost_usd for r in results)
    total_duration = sum(r.duration_ms for r in results)
    avg_duration = total_duration / (total or 1)
    avg_confidence = sum(r.confidence for r in results) / (total or 1)
    return {
        "run_id": str(uuid.uuid4()),
        "total_actions": total,
        "successful": successes,
        "failed": total - successes,
        "success_rate": successes / (total or 1),
        "total_cost_usd": total_cost,
        "total_duration_ms": total_duration,
        "avg_duration_ms": avg_duration,
        "avg_confidence": avg_confidence,
    }


# ---------------------------------------------------------------------------
# LLM response → ExecutionCompiler wiring  (Hero Flow — Task 1)
# ---------------------------------------------------------------------------

class LLMResponseWiringError(Exception):
    """Raised when the LLM response cannot be compiled into an execution packet."""


class LLMResponseWirer:
    """Parses a raw LLM response and compiles it into an execution packet.

    This closes the Hero Flow loop:
        LLM response → parse → compile (ExecutionCompiler) → execution packet

    Retry behaviour
    ---------------
    *max_retries* (default 3) controls how many times the wirer will retry on
    transient errors (timeout, rate-limit, or malformed-JSON).  Between each
    attempt an exponential back-off of ``0.1 * 2**(attempt-1)`` seconds is
    applied.

    Graceful degradation
    --------------------
    When all retries are exhausted the wirer returns a ``degraded`` packet
    instead of raising, so the Hero Flow can continue and notify the user.
    The packet contains ``"status": "degraded"`` and a human-readable
    ``"reason"`` field.

    Parameters
    ----------
    max_retries:
        Maximum retry attempts for transient failures.
    timeout_seconds:
        Per-attempt wall-clock budget (informational — callers are
        responsible for honouring the timeout at the transport layer).
    """

    # Transient error indicators that warrant a retry
    _TRANSIENT_PATTERNS: List[str] = [
        "timeout",
        "rate limit",
        "rate_limit",
        "too many requests",
        "503",
        "502",
        "connection",
    ]

    def __init__(
        self,
        max_retries: int = 3,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wire(
        self,
        llm_response: str,
        *,
        confidence: float = 0.85,
        authority_level: str = "high",
        gates_satisfied: Optional[List[str]] = None,
        gates_required: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Parse *llm_response* and compile it into an execution packet.

        Parameters
        ----------
        llm_response:
            Raw string returned by the LLM.
        confidence:
            Confidence score to pass to :class:`ExecutionCompiler`.
        authority_level:
            Authority level for the compiled packet.
        gates_satisfied:
            Gates already satisfied by the caller.
        gates_required:
            Gates required for compilation.

        Returns
        -------
        An execution packet dict (always a dict, never raises).
        ``packet["status"]`` is ``"compiled"`` on success or ``"degraded"``
        on failure.
        """
        last_error: Optional[str] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                plan = self._parse_llm_response(llm_response)
                packet = self._compile(
                    plan,
                    confidence=confidence,
                    authority_level=authority_level,
                    gates_satisfied=gates_satisfied or [],
                    gates_required=gates_required or [],
                )
                logger.info(
                    "LLMResponseWirer: compiled packet %s on attempt %d",
                    packet.get("packet_id", "?"),
                    attempt,
                )
                return packet

            except Exception as exc:
                last_error = str(exc)
                if self._is_transient(last_error) and attempt < self._max_retries:
                    backoff = 0.1 * (2 ** (attempt - 1))
                    logger.warning(
                        "LLMResponseWirer: transient error on attempt %d/%d — "
                        "retrying in %.2fs: %s",
                        attempt, self._max_retries, backoff, last_error,
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        "LLMResponseWirer: non-transient or final-attempt error: %s",
                        last_error,
                    )
                    break

        return self._degraded_packet(last_error or "unknown error")

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(response: str) -> Dict[str, Any]:
        """Extract a structured plan from a raw LLM string.

        Supported formats (in order of preference):
        1. JSON object with ``"actions"`` key.
        2. JSON array (each element treated as an action dict).
        3. Plain text — each non-empty line becomes one action.

        Raises
        ------
        ValueError
            When the response is empty or cannot be parsed into a plan.
        """
        import json

        response = response.strip()
        if not response:
            raise ValueError("LLM returned an empty response")

        # Attempt 1: JSON object
        if response.startswith("{"):
            try:
                data = json.loads(response)
                actions = data.get("actions", [])
                if not isinstance(actions, list):
                    actions = [{"description": str(actions)}]
                return {
                    "actions": actions,
                    "summary": data.get("summary", "LLM-generated plan"),
                    "hypothesis_id": data.get("hypothesis_id", f"llm_{uuid.uuid4().hex[:8]}"),
                    "confidence": data.get("confidence", 0.85),
                }
            except json.JSONDecodeError:  # PROD-HARD A2: not a JSON object — try array next
                logger.debug("LLM response failed JSON-object parse; trying array form", exc_info=True)

        # Attempt 2: JSON array
        if response.startswith("["):
            try:
                actions = json.loads(response)
                if isinstance(actions, list):
                    return {
                        "actions": [
                            a if isinstance(a, dict) else {"description": str(a)}
                            for a in actions
                        ],
                        "summary": "LLM-generated action list",
                        "hypothesis_id": f"llm_{uuid.uuid4().hex[:8]}",
                        "confidence": 0.85,
                    }
            except json.JSONDecodeError:  # PROD-HARD A2: not a JSON array either — fall through to plain-text
                logger.debug("LLM response failed JSON-array parse; falling through to plain text", exc_info=True)

        # Attempt 3: plain text — each line = one action
        lines = [ln.strip() for ln in response.splitlines() if ln.strip()]
        if not lines:
            raise ValueError("LLM response contains no actionable content")

        return {
            "actions": [{"description": ln, "type": "text_directive"} for ln in lines],
            "summary": lines[0][:120] if lines else "LLM-generated plan",
            "hypothesis_id": f"llm_{uuid.uuid4().hex[:8]}",
            "confidence": 0.75,
        }

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------

    @staticmethod
    def _compile(
        plan: Dict[str, Any],
        *,
        confidence: float,
        authority_level: str,
        gates_satisfied: List[str],
        gates_required: List[str],
    ) -> Dict[str, Any]:
        """Delegate to :class:`ExecutionCompiler` from ``execution_compiler``."""
        try:
            from src.execution_compiler import ExecutionCompiler
        except ImportError:
            from execution_compiler import ExecutionCompiler  # type: ignore[no-redef]

        compiler = ExecutionCompiler()
        packet = compiler.compile(
            plan,
            confidence=confidence,
            authority_level=authority_level,
            gates_satisfied=gates_satisfied,
            gates_required=gates_required,
        )

        if not packet.get("compiled", True):
            reason = packet.get("reason", "compilation rejected by gate")
            raise LLMResponseWiringError(f"Compilation failed: {reason}")

        return packet

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_transient(self, error_msg: str) -> bool:
        """Return True when *error_msg* looks like a transient/retriable error."""
        lower = error_msg.lower()
        return any(pat in lower for pat in self._TRANSIENT_PATTERNS)

    @staticmethod
    def _degraded_packet(reason: str) -> Dict[str, Any]:
        """Return a minimal degraded packet indicating LLM unavailability."""
        import hashlib
        import json
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).isoformat()
        packet: Dict[str, Any] = {
            "packet_id": f"degraded_{uuid.uuid4().hex[:12]}",
            "status": "degraded",
            "compiled": False,
            "reason": reason,
            "timestamp": ts,
            "degraded": True,
            "user_message": (
                "Murphy is temporarily unable to process your request. "
                "Your task has been queued and will be retried automatically."
            ),
        }
        canonical = json.dumps(
            {k: packet[k] for k in sorted(packet) if k != "signature"},
            sort_keys=True,
            default=str,
        )
        packet["signature"] = hashlib.sha256(canonical.encode()).hexdigest()
        logger.warning("LLMResponseWirer: returning degraded packet — %s", reason)
        return packet
