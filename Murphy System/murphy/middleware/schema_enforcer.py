# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Schema Enforcer Middleware — MURPHY-MIDDLEWARE-SCHEMA-001

Owner: Platform Engineering
Dep: AgentOutput schema, BAT sealing, Matrix notifications

Intercepts every inter-agent message and validates it against the
AgentOutput schema before delivery.  If validation fails:
  1. Reject the message
  2. Return FAIL AgentOutput to the sender
  3. Post the failure to Matrix
  4. Seal the failure in BAT

No agent communicates outside this middleware.

Error codes: SCHEMA-ENFORCE-ERR-001 through SCHEMA-ENFORCE-ERR-004.
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from pydantic import ValidationError

from murphy.rosetta.org_lookup import (
    BATSealError,
    _post_matrix_alert,
    _seal_to_bat,
)
from murphy.schemas.agent_output import AgentOutput

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Validation core  (SCHEMA-ENFORCE-VALIDATE-001)
# ---------------------------------------------------------------------------

def validate_agent_message(raw: Any) -> AgentOutput:
    """Validate an inter-agent message against AgentOutput schema.

    Args:
        raw: The message to validate — can be dict, JSON string, or
             AgentOutput instance.

    Returns:
        Validated AgentOutput.

    Raises:
        SchemaEnforcementError: If the message does not conform.
    """
    if isinstance(raw, AgentOutput):
        return raw

    try:
        if isinstance(raw, str):
            return AgentOutput.from_json(raw)
        if isinstance(raw, dict):
            return AgentOutput.model_validate(raw)
    except (ValidationError, json.JSONDecodeError) as exc:
        raise SchemaEnforcementError(
            f"SCHEMA-ENFORCE-ERR-001: Message does not conform to AgentOutput — {exc}"
        ) from exc

    raise SchemaEnforcementError(
        f"SCHEMA-ENFORCE-ERR-002: Unsupported message type {type(raw).__name__} — "
        f"expected AgentOutput, dict, or JSON string"
    )


class SchemaEnforcementError(Exception):
    """Raised when an inter-agent message fails schema validation."""
    pass


# ---------------------------------------------------------------------------
# Middleware wrapper  (SCHEMA-ENFORCE-WRAP-001)
# ---------------------------------------------------------------------------

def enforce_schema(func: F) -> F:
    """Decorator: wrap any agent-to-agent call with schema enforcement.

    The decorated function's return value is validated against AgentOutput.
    If validation fails, a FAIL AgentOutput is returned, Matrix is notified,
    and the failure is sealed in BAT.

    Usage::

        @enforce_schema
        def my_agent_call(request):
            ...
            return AgentOutput(...)
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> AgentOutput:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # SCHEMA-ENFORCE-ERR-003
            logger.error("SCHEMA-ENFORCE-ERR-003: Agent call raised: %s", exc)
            return _handle_enforcement_failure(
                func.__name__,
                f"SCHEMA-ENFORCE-ERR-003: Agent call raised: {exc}",
            )

        try:
            validated = validate_agent_message(result)
            return validated
        except SchemaEnforcementError as exc:
            logger.error("SCHEMA-ENFORCE-ERR-001: %s", exc)
            return _handle_enforcement_failure(func.__name__, str(exc))

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Failure handler  (SCHEMA-ENFORCE-FAIL-001)
# ---------------------------------------------------------------------------

def _handle_enforcement_failure(
    source: str,
    error_message: str,
) -> AgentOutput:
    """Handle a schema enforcement failure: FAIL + Matrix + BAT."""
    # 1. Post to Matrix
    _post_matrix_alert(
        f"🚫 SCHEMA ENFORCEMENT FAILURE from {source}: {error_message}"
    )

    # 2. Seal in BAT
    try:
        _seal_to_bat(
            action="schema_enforcement_failure",
            resource=source,
            metadata={
                "error": error_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except BATSealError as bat_exc:  # SCHEMA-ENFORCE-ERR-004
        logger.error("SCHEMA-ENFORCE-ERR-004: BAT seal also failed — %s", bat_exc)

    # 3. Return FAIL AgentOutput
    return AgentOutput.from_error(
        agent_id="schema-enforcer",
        agent_name="SchemaEnforcer",
        file_path=f"enforcement/{source}",
        org_node_id="platform-engineering",
        error_message=error_message,
    )


# ---------------------------------------------------------------------------
# Bulk enforcement  (SCHEMA-ENFORCE-BULK-001)
# ---------------------------------------------------------------------------

def validate_all_outputs(outputs: list[Any]) -> tuple[list[AgentOutput], list[str]]:
    """Validate a batch of agent outputs.

    Returns (valid_outputs, error_messages).
    """
    valid: list[AgentOutput] = []
    errors: list[str] = []

    for i, raw in enumerate(outputs):
        try:
            validated = validate_agent_message(raw)
            valid.append(validated)
        except SchemaEnforcementError as exc:
            errors.append(f"Output[{i}]: {exc}")

    return valid, errors
