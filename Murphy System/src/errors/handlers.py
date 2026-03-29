# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: errors/handlers.py
Subsystem: Error Handling
Purpose: FastAPI exception handlers and API endpoints for the Murphy error
         system.
Status: Production

Call ``register_error_handlers(app)`` once during app setup to install
global exception handlers and the ``/api/errors/*`` catalogue endpoints.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

from .codes import ErrorCode
from .registry import ErrorRegistry

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception → error-code mapping helpers
# ---------------------------------------------------------------------------

def _classify_exception(exc: Exception) -> ErrorCode:
    """Map a Python exception to the best-matching Murphy error code."""
    cls_name = type(exc).__qualname__
    module = getattr(type(exc), "__module__", "")
    fqn = f"{module}.{cls_name}" if module else cls_name

    registry = ErrorRegistry.get()
    for entry in registry.catalog():
        if entry["exception_class"] and entry["exception_class"] in fqn:
            return ErrorCode(entry["code"])

    # Fall back to generic codes by base type.
    if isinstance(exc, PermissionError):
        return ErrorCode.E100
    if isinstance(exc, ValueError):
        return ErrorCode.E200
    if isinstance(exc, KeyError):
        return ErrorCode.E304
    if isinstance(exc, ConnectionError):
        return ErrorCode.E400
    if isinstance(exc, OSError):
        return ErrorCode.E500

    return ErrorCode.E999


def _error_json(code: ErrorCode, detail: str, http_status: int) -> JSONResponse:
    """Build a standard error envelope."""
    return JSONResponse(
        {
            "success": False,
            "error": {
                "code": code.value,
                "message": detail,
            },
        },
        status_code=http_status,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_error_handlers(app: "FastAPI") -> None:
    """Install global exception handlers and error-catalogue endpoints.

    Call this once during app startup — it is idempotent.
    """

    # --- Global catch-all handler ------------------------------------------
    @app.exception_handler(Exception)
    async def _catch_all(request: Request, exc: Exception) -> JSONResponse:
        code = _classify_exception(exc)
        registry = ErrorRegistry.get()
        entry = registry.lookup(code.value)
        http_status = entry.http_status if entry else 500
        detail = str(exc) if str(exc) else (entry.message if entry else "Internal error")
        logger.error(
            "Unhandled exception [%s]: %s",
            code.value,
            detail,
            exc_info=True,
        )
        return _error_json(code, detail, http_status)

    # --- Catalogue endpoints -----------------------------------------------
    # NOTE: /catalog must be registered BEFORE /{code} so FastAPI matches
    # the literal path before the parameterised one.
    @app.get("/api/errors/catalog")
    async def _error_catalog() -> JSONResponse:
        """Return the complete error catalogue."""
        registry = ErrorRegistry.get()
        return JSONResponse({"success": True, "data": registry.catalog()})

    @app.get("/api/errors/{code}")
    async def _error_lookup(code: str) -> JSONResponse:
        """Look up a single MURPHY-Exxx error code."""
        registry = ErrorRegistry.get()
        entry = registry.lookup(code)
        if entry is None:
            return JSONResponse(
                {"success": False, "error": {"code": "NOT_FOUND", "message": f"Unknown error code: {code}"}},
                status_code=404,
            )
        return JSONResponse({
            "success": True,
            "data": {
                "code": entry.code.value,
                "message": entry.message,
                "cause": entry.cause,
                "fix": entry.fix,
                "severity": entry.severity,
                "http_status": entry.http_status,
            },
        })
