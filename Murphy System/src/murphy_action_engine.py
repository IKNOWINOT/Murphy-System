"""
Murphy System - Murphy Action Engine
Copyright 2024-2026 Corey Post, Inoni LLC
License: BSL 1.1

Large Action Model interface providing structured function/tool calling for Murphy's LLM routing.
Integrates with: deterministic_routing_engine.py, api_gateway_adapter.py
"""

import functools
import importlib
import importlib.util
import logging
import os
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
            return datetime.datetime.utcnow().isoformat()
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
    before = len(_GLOBAL_REGISTRY.list_all())
    loaded = 0

    for entry in os.listdir(src_dir):
        if not entry.endswith(".py") or entry.startswith("_"):
            continue
        module_name = entry[:-3]
        module_path = os.path.join(src_dir, entry)
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
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
