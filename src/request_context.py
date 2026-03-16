"""
Request ID / Correlation ID Context for Murphy System.

Provides a per-request UUID that is:
  - Read from the incoming ``X-Request-ID`` header when present
  - Generated as a UUID4 when absent
  - Stored in a ``contextvars.ContextVar`` for use across async calls
  - Returned in the ``X-Request-ID`` response header
  - Included in every log record via the JSON logging formatter

Usage::

    from request_context import get_request_id, RequestIDMiddleware

    # Add to FastAPI app:
    app.add_middleware(RequestIDMiddleware)

    # In any handler or service:
    from request_context import get_request_id
    request_id = get_request_id()

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations
import logging

import uuid
from contextvars import ContextVar
from typing import Optional

# ---------------------------------------------------------------------------
# Context variable
# ---------------------------------------------------------------------------

_REQUEST_ID_VAR: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request ID from the context, or an empty string."""
    return _REQUEST_ID_VAR.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID in the context."""
    _REQUEST_ID_VAR.set(request_id)


def generate_request_id() -> str:
    """Generate a new UUID4 request ID."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# FastAPI / Starlette middleware
# ---------------------------------------------------------------------------

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
    _STARLETTE_AVAILABLE = True
except ImportError:
    _STARLETTE_AVAILABLE = False

if _STARLETTE_AVAILABLE:
    class RequestIDMiddleware(BaseHTTPMiddleware):
        """FastAPI middleware that assigns a request ID to every request.

        - Reads ``X-Request-ID`` header from the incoming request.
        - Generates a UUID4 if the header is absent or empty.
        - Stores the ID in the ``request_id`` context variable.
        - Adds ``X-Request-ID`` to the response headers.
        """

        async def dispatch(self, request: Request, call_next) -> Response:
            request_id = (
                request.headers.get("X-Request-ID") or generate_request_id()
            )
            token = _REQUEST_ID_VAR.set(request_id)
            try:
                response: Response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response
            finally:
                _REQUEST_ID_VAR.reset(token)

else:
    # Fallback when Starlette is not installed (e.g. unit tests without web deps)
    class RequestIDMiddleware:  # type: ignore[no-redef]
        """Stub middleware — Starlette is not installed."""

        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)
