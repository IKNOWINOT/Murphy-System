# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: errors/registry.py
Subsystem: Error Handling
Purpose: Error registry mapping Murphy error codes to metadata and existing
         exception classes.
Status: Production

The registry is the single source of truth for every error the system can
raise.  The ``/api/errors/{code}`` and ``/api/errors/catalog`` endpoints
read from it, and ``docs/ERROR_CATALOG.md`` is generated from it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .codes import ErrorCode


@dataclass(frozen=True)
class ErrorEntry:
    """Metadata for a single Murphy error code."""

    code: ErrorCode
    message: str
    cause: str
    fix: str
    severity: str  # "critical" | "high" | "medium" | "low"
    http_status: int = 500
    exception_class: Optional[str] = None  # dotted-path to existing class


# ---------------------------------------------------------------------------
# Master registry — every MURPHY-Exxx code must appear here.
# ---------------------------------------------------------------------------
_ENTRIES: list[ErrorEntry] = [
    # --- E0xx: Core / Boot -------------------------------------------------
    ErrorEntry(
        code=ErrorCode.E001,
        message="Internal server error",
        cause="An unexpected condition was encountered.",
        fix="Check server logs for the full traceback.",
        severity="critical",
        http_status=500,
    ),
    ErrorEntry(
        code=ErrorCode.E002,
        message="State operation failed",
        cause="A state transition or lookup could not be completed.",
        fix="Verify the requested state key exists and the transition is valid.",
        severity="high",
        http_status=500,
        exception_class="src.environment_state_manager.StateError",
    ),
    ErrorEntry(
        code=ErrorCode.E003,
        message="Connector not configured",
        cause="A required integration connector has no credentials.",
        fix="Set the required environment variables for this connector.",
        severity="high",
        http_status=503,
        exception_class="src.integrations.base_connector.NotConfiguredError",
    ),
    ErrorEntry(
        code=ErrorCode.E004,
        message="Stability violation",
        cause="The control-loop stability monitor detected unacceptable oscillation.",
        fix="Reduce gain or increase damping on the affected control plane.",
        severity="critical",
        http_status=500,
        exception_class="src.control_plane.control_loop.StabilityViolation",
    ),
    ErrorEntry(
        code=ErrorCode.E005,
        message="Runaway loop detected",
        cause="A loop exceeded its hard cap or wall-clock timeout.",
        fix="Inspect the loop bounds and ensure an exit condition is reachable.",
        severity="critical",
        http_status=500,
        exception_class="src.automation_safeguard_engine.RunawayLoopError",
    ),

    # --- E1xx: Authentication / Authorisation ------------------------------
    ErrorEntry(
        code=ErrorCode.E100,
        message="Authentication required",
        cause="No valid credentials were provided.",
        fix="Supply a valid API key or JWT token.",
        severity="high",
        http_status=401,
    ),
    ErrorEntry(
        code=ErrorCode.E101,
        message="Authentication failed",
        cause="The supplied credentials are invalid or expired.",
        fix="Refresh the token or re-authenticate.",
        severity="high",
        http_status=401,
        exception_class="src.signup_gateway.AuthError",
    ),
    ErrorEntry(
        code=ErrorCode.E102,
        message="Signup validation failed",
        cause="One or more signup fields did not pass validation.",
        fix="Check the error detail for the specific field that failed.",
        severity="medium",
        http_status=422,
        exception_class="src.signup_gateway.SignupError",
    ),
    ErrorEntry(
        code=ErrorCode.E103,
        message="Tenant access denied",
        cause="User attempted to access another tenant's resource.",
        fix="Verify you are using the correct tenant context.",
        severity="critical",
        http_status=403,
        exception_class="src.billing.grants.sessions.TenantAccessError",
    ),

    # --- E2xx: API / Request handling --------------------------------------
    ErrorEntry(
        code=ErrorCode.E200,
        message="Bad request",
        cause="The request was malformed or missing required fields.",
        fix="Check the request body/parameters against the API docs.",
        severity="medium",
        http_status=400,
    ),
    ErrorEntry(
        code=ErrorCode.E201,
        message="Input validation failed",
        cause="Request payload did not pass security hardening validation.",
        fix="Remove disallowed characters or patterns from input.",
        severity="high",
        http_status=422,
        exception_class="src.security_plane.hardening.ValidationError",
    ),
    ErrorEntry(
        code=ErrorCode.E202,
        message="Injection attempt blocked",
        cause="Input matched a known injection attack pattern.",
        fix="Do not include SQL, script, or shell metacharacters in input.",
        severity="critical",
        http_status=403,
        exception_class="src.security_plane.hardening.InjectionAttemptError",
    ),
    ErrorEntry(
        code=ErrorCode.E203,
        message="LLM output validation failed",
        cause="The LLM produced output that did not match the expected schema.",
        fix="Retry the request. If persistent, adjust the prompt or schema.",
        severity="medium",
        http_status=502,
        exception_class="src.llm_output_validator.ValidationError",
    ),
    ErrorEntry(
        code=ErrorCode.E204,
        message="Approval not permitted",
        cause="The approval operation is not allowed in the current state.",
        fix="Check the item status and your permission level.",
        severity="medium",
        http_status=403,
        exception_class="src.time_tracking.approval_service.ApprovalError",
    ),

    # --- E3xx: Business logic ----------------------------------------------
    ErrorEntry(
        code=ErrorCode.E300,
        message="Business rule violation",
        cause="A business-logic invariant was violated.",
        fix="Review the operation parameters against business rules.",
        severity="medium",
        http_status=400,
    ),
    ErrorEntry(
        code=ErrorCode.E301,
        message="Marketplace error",
        cause="Marketplace validation check failed.",
        fix="Ensure the listing meets all marketplace requirements.",
        severity="medium",
        http_status=400,
        exception_class="src.automation_marketplace.MarketplaceError",
    ),
    ErrorEntry(
        code=ErrorCode.E302,
        message="Sweep failure",
        cause="Profit sweep operation could not complete.",
        fix="Verify account balances and sweep configuration.",
        severity="high",
        http_status=500,
        exception_class="src.profit_sweep.SweepError",
    ),
    ErrorEntry(
        code=ErrorCode.E303,
        message="Circular dependency detected",
        cause="A dependency cycle exists in the task graph.",
        fix="Remove or restructure tasks to eliminate the cycle.",
        severity="high",
        http_status=400,
        exception_class="src.billing.grants.task_queue.CircularDependencyError",
    ),
    ErrorEntry(
        code=ErrorCode.E304,
        message="Task not found",
        cause="The specified task ID does not exist in the queue.",
        fix="Verify the task_id and retry.",
        severity="low",
        http_status=404,
        exception_class="src.billing.grants.task_queue.TaskNotFoundError",
    ),
    ErrorEntry(
        code=ErrorCode.E305,
        message="Fleet manifest validation failed",
        cause="The fleet manifest contains invalid or conflicting declarations.",
        fix="Check the manifest YAML against the schema.",
        severity="medium",
        http_status=422,
        exception_class="src.declarative_fleet_manager.ManifestValidationError",
    ),

    # --- E4xx: Integration -------------------------------------------------
    ErrorEntry(
        code=ErrorCode.E400,
        message="Integration error",
        cause="An external service call failed.",
        fix="Check connectivity and credentials for the external service.",
        severity="high",
        http_status=502,
    ),
    ErrorEntry(
        code=ErrorCode.E401,
        message="LLM response wiring failed",
        cause="The LLM response could not be compiled into an execution packet.",
        fix="Inspect the LLM output format. Retry with a simpler prompt.",
        severity="high",
        http_status=502,
        exception_class="src.murphy_action_engine.LLMResponseWiringError",
    ),
    ErrorEntry(
        code=ErrorCode.E402,
        message="Large Action Model error",
        cause="The LAM framework encountered an execution failure.",
        fix="Check the action plan and retry. Review LAM logs for details.",
        severity="high",
        http_status=500,
        exception_class="src.large_action_model.LAMError",
    ),
    ErrorEntry(
        code=ErrorCode.E403,
        message="Matrix client error",
        cause="Unrecoverable Matrix API or connection error.",
        fix="Verify Matrix homeserver URL and access token.",
        severity="high",
        http_status=502,
        exception_class="src.matrix_bridge.matrix_client.MatrixClientError",
    ),

    # --- E5xx: Data / Persistence ------------------------------------------
    ErrorEntry(
        code=ErrorCode.E500,
        message="Data persistence error",
        cause="A database or storage operation failed.",
        fix="Check database connectivity and disk space.",
        severity="critical",
        http_status=500,
    ),

    # --- E6xx: Orchestration -----------------------------------------------
    ErrorEntry(
        code=ErrorCode.E600,
        message="Orchestration error",
        cause="A workflow or orchestration step failed.",
        fix="Inspect the workflow DAG and retry the failed step.",
        severity="high",
        http_status=500,
    ),
    ErrorEntry(
        code=ErrorCode.E601,
        message="Packet compilation failed",
        cause="The control-plane packet compiler could not produce a valid packet.",
        fix="Check the input signals and packet schema.",
        severity="high",
        http_status=500,
        exception_class="src.control_plane.packet_compiler.PacketCompilationError",
    ),
    ErrorEntry(
        code=ErrorCode.E602,
        message="Module compilation failed",
        cause="A module could not be compiled from its source definition.",
        fix="Check the module source for syntax errors.",
        severity="high",
        http_status=500,
        exception_class="src.module_compiler.compiler.CompilationError",
    ),

    # --- E7xx: UI / Frontend -----------------------------------------------
    ErrorEntry(
        code=ErrorCode.E700,
        message="UI error",
        cause="A frontend rendering or data-fetch operation failed.",
        fix="Refresh the page. If persistent, check browser console.",
        severity="low",
        http_status=500,
    ),

    # --- E8xx: Infrastructure ----------------------------------------------
    ErrorEntry(
        code=ErrorCode.E800,
        message="Infrastructure error",
        cause="A Docker, K8s, or monitoring subsystem failed.",
        fix="Check infrastructure dashboards and pod status.",
        severity="critical",
        http_status=503,
    ),

    # --- E9xx: Reserved / Internal -----------------------------------------
    ErrorEntry(
        code=ErrorCode.E999,
        message="Unclassified internal error",
        cause="An error occurred that has not yet been assigned a specific code.",
        fix="Report this error code and the traceback to the development team.",
        severity="medium",
        http_status=500,
    ),
]


class ErrorRegistry:
    """Singleton registry of all Murphy error codes."""

    _instance: Optional["ErrorRegistry"] = None

    def __init__(self) -> None:
        self._by_code: dict[str, ErrorEntry] = {}
        for entry in _ENTRIES:
            self._by_code[entry.code.value] = entry

    @classmethod
    def get(cls) -> "ErrorRegistry":
        """Return the shared registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def lookup(self, code: str) -> Optional[ErrorEntry]:
        """Look up an error entry by its MURPHY-Exxx code string."""
        return self._by_code.get(code)

    def catalog(self) -> list[dict]:
        """Return the full catalog as a list of dicts (JSON-serialisable)."""
        return [
            {
                "code": e.code.value,
                "message": e.message,
                "cause": e.cause,
                "fix": e.fix,
                "severity": e.severity,
                "http_status": e.http_status,
                "exception_class": e.exception_class,
            }
            for e in _ENTRIES
        ]
