# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
# Design-label: ENVELOPE-001
"""Production-grade structured error envelope for all Murphy API responses.

Inspired by RFC 9457 ("Problem Details for HTTP APIs") and the synthorg
``exception_handlers.py`` pattern.  Every API response follows a consistent
shape so the frontend ``MurphyAPI`` client can parse it without guessing:

    Success
    -------
    {"success": true,  "data": <payload>}

    Legacy error (backward-compatible)
    -----------------------------------
    {"success": false, "error": {"code": "...", "message": "..."}}

    Structured error (new)
    ----------------------
    {"success": false, "error": {
        "code":                "...",
        "message":             "...",
        "category":            "VALIDATION | AUTH | ...",
        "retryable":           true | false,
        "retry_after_seconds": null | <int>,
        "correlation_id":      "<uuid>",
        "timestamp":           "<ISO-8601>"
    }}

    Paginated success
    -----------------
    {"success": true, "data": [...], "pagination": {
        "page": 1, "per_page": 20, "total": 100, "total_pages": 5
    }}
"""
from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Sequence

from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error categories
# ---------------------------------------------------------------------------


class ErrorCategory(str, Enum):
    """High-level error categories used for structured error responses.

    Inheriting from ``str`` allows JSON serialisation to produce the bare
    string value (e.g. ``"VALIDATION"``) rather than ``"ErrorCategory.VALIDATION"``.
    """

    VALIDATION = "VALIDATION"
    AUTH = "AUTH"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMIT = "RATE_LIMIT"
    INTERNAL = "INTERNAL"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY = "DEPENDENCY"


# ---------------------------------------------------------------------------
# Status-code → default category / retryability mapping
# ---------------------------------------------------------------------------

_STATUS_TO_CATEGORY: Dict[int, tuple[ErrorCategory, bool]] = {
    400: (ErrorCategory.VALIDATION, False),
    401: (ErrorCategory.AUTH, False),
    403: (ErrorCategory.AUTH, False),
    404: (ErrorCategory.NOT_FOUND, False),
    409: (ErrorCategory.CONFLICT, False),
    422: (ErrorCategory.VALIDATION, False),
    429: (ErrorCategory.RATE_LIMIT, True),
    500: (ErrorCategory.INTERNAL, False),
    502: (ErrorCategory.DEPENDENCY, True),
    503: (ErrorCategory.DEPENDENCY, True),
    504: (ErrorCategory.TIMEOUT, True),
}
"""Maps HTTP status codes to a ``(default_category, retryable)`` tuple.

Callers can override both values explicitly; this mapping is only used as a
convenient fallback when ``category`` or ``retryable`` is not provided.
"""


# ---------------------------------------------------------------------------
# Structured error dataclass
# ---------------------------------------------------------------------------


@dataclass
class StructuredError:
    """Rich, RFC 9457-inspired error descriptor.

    Parameters
    ----------
    code:
        Machine-readable error code (e.g. ``"INVALID_TOKEN"``).
    message:
        Human-readable explanation of the error.
    category:
        Broad error category drawn from :class:`ErrorCategory`.
    retryable:
        Whether the client should consider retrying the request.
    retry_after_seconds:
        Optional hint indicating how many seconds to wait before retrying.
    correlation_id:
        Unique ID for correlating this error across logs and traces.
        Auto-generated as a UUID-4 string if not supplied.
    timestamp:
        ISO 8601 UTC timestamp of when the error was created.
        Auto-generated if not supplied.
    """

    code: str
    message: str
    category: ErrorCategory
    retryable: bool = False
    retry_after_seconds: Optional[int] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary suitable for JSON responses."""
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category.value,
            "retryable": self.retryable,
            "retry_after_seconds": self.retry_after_seconds,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Legacy helpers (backward-compatible — signatures unchanged)
# ---------------------------------------------------------------------------


def success_response(data=None, status_code: int = 200) -> JSONResponse:
    """Return a standard success envelope."""
    return JSONResponse({"success": True, "data": data}, status_code=status_code)


def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Return a standard error envelope."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# New structured helpers
# ---------------------------------------------------------------------------


def structured_error_response(
    code: str,
    message: str,
    status_code: int = 400,
    *,
    category: Optional[ErrorCategory] = None,
    retryable: Optional[bool] = None,
    retry_after_seconds: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> JSONResponse:
    """Return a rich, structured error envelope.

    For **5xx** status codes the ``message`` field in the response body is
    replaced with a generic ``"Internal server error"`` string to avoid
    leaking implementation details to clients.  The original message is
    logged at ``ERROR`` level together with the ``correlation_id`` so that
    operators can correlate client reports with server-side diagnostics.

    Parameters
    ----------
    code:
        Machine-readable error code.
    message:
        Human-readable error description.
    status_code:
        HTTP status code for the response (default ``400``).
    category:
        Explicit error category.  Falls back to :data:`_STATUS_TO_CATEGORY`.
    retryable:
        Explicit retryability flag.  Falls back to :data:`_STATUS_TO_CATEGORY`.
    retry_after_seconds:
        Optional retry-after hint (seconds).
    correlation_id:
        Optional correlation ID.  A UUID-4 is generated when omitted.
    """
    default_category, default_retryable = _STATUS_TO_CATEGORY.get(
        status_code, (ErrorCategory.INTERNAL, False),
    )
    resolved_category = category if category is not None else default_category
    resolved_retryable = retryable if retryable is not None else default_retryable

    error = StructuredError(
        code=code,
        message=message,
        category=resolved_category,
        retryable=resolved_retryable,
        retry_after_seconds=retry_after_seconds,
        **({"correlation_id": correlation_id} if correlation_id else {}),
    )

    # 5xx: scrub detailed message from the client-facing payload
    payload = error.to_dict()
    if status_code >= 500:
        logger.error(
            "Structured error [%s] correlation_id=%s: %s",
            code,
            error.correlation_id,
            message,
        )
        payload["message"] = "Internal server error"

    return JSONResponse({"success": False, "error": payload}, status_code=status_code)


def paginated_response(
    data: Sequence[Any],
    *,
    page: int,
    per_page: int,
    total: int,
    status_code: int = 200,
) -> JSONResponse:
    """Return a success envelope with pagination metadata.

    Parameters
    ----------
    data:
        The items for the current page.
    page:
        Current page number (1-based).
    per_page:
        Maximum number of items per page.
    total:
        Total number of items across all pages.
    status_code:
        HTTP status code (default ``200``).

    Returns
    -------
    JSONResponse
        A JSON response with ``success``, ``data``, and ``pagination`` keys.
    """
    total_pages = math.ceil(total / per_page) if per_page > 0 else 0
    return JSONResponse(
        {
            "success": True,
            "data": list(data),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            },
        },
        status_code=status_code,
    )
