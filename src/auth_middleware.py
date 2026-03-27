"""
Murphy System — Authentication & Security Middleware (DEF-014, DEF-015)

Provides:
  - APIKeyMiddleware: Validates API key via X-API-Key header, Authorization
    Bearer token, or query parameter. Environment-aware (dev allows, prod requires).
  - SecurityHeadersMiddleware: Adds standard security headers to all responses.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Optional, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("murphy.auth")

# ── Exempt paths that never require authentication ─────────────────────────
_DEFAULT_EXEMPT: Set[str] = {
    "/health",
    "/api/health",
    "/api/readiness",
    "/api/status",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/",
}

_EXEMPT_PREFIXES = (
    "/static",
    "/murphy-static",
    "/ui/",
    "/api/ui/",
    "/api/auth/",
    "/api/demo",
    "/api/v1/auth/",
)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforce API key authentication on all non-exempt routes.

    Supports three authentication methods:
      1. X-API-Key header
      2. Authorization: Bearer <key>
      3. ?api_key=<key> query parameter

    Environment-aware:
      - Development mode (MURPHY_ENV != production/staging): allows requests
        when MURPHY_AUTH_ENABLED is not explicitly "true"
      - Production/staging: requires valid API key unless MURPHY_AUTH_ENABLED=false
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/") or "/"
        method = request.method.upper()

        # Always allow OPTIONS (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)

        # Check exempt paths
        if path in _DEFAULT_EXEMPT:
            return await call_next(request)
        for prefix in _EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Check user-defined exempt paths
        extra_exempt = os.environ.get("MURPHY_AUTH_EXEMPT", "")
        if extra_exempt:
            for ep in extra_exempt.split(","):
                ep = ep.strip()
                if ep and path.startswith(ep):
                    return await call_next(request)

        # Check if auth is enabled
        env_mode = os.environ.get("MURPHY_ENV", "development").lower()
        auth_enabled = os.environ.get("MURPHY_AUTH_ENABLED", "").lower()

        if env_mode in ("production", "staging"):
            # Production: auth enabled by default unless explicitly disabled
            if auth_enabled == "false":
                return await call_next(request)
        else:
            # Development: auth disabled by default unless explicitly enabled
            if auth_enabled != "true":
                return await call_next(request)

        # Get the expected API key
        expected_key = os.environ.get("MURPHY_API_KEY", "")
        if not expected_key:
            logger.warning(
                "MURPHY_API_KEY not set but auth is enabled — blocking request to %s",
                path,
            )
            return JSONResponse(
                {"error": "Server misconfiguration: API key not set"},
                status_code=500,
            )

        # Extract key from request
        provided_key = _extract_api_key(request)
        if not provided_key:
            return JSONResponse(
                {"error": "Authentication required", "detail": "Provide API key via X-API-Key header, Authorization: Bearer, or ?api_key= query param"},
                status_code=401,
            )

        # Constant-time comparison
        if not hmac.compare_digest(provided_key, expected_key):
            logger.warning("Invalid API key attempt on %s", path)
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=403,
            )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to all responses (DEF-015)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS only in production
        env_mode = os.environ.get("MURPHY_ENV", "development").lower()
        if env_mode in ("production", "staging"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


def _extract_api_key(request: Request) -> Optional[str]:
    """Extract API key from multiple sources."""
    # 1. X-API-Key header
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if key:
        return key

    # 2. Authorization: Bearer <key>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    # 3. Query parameter
    key = request.query_params.get("api_key")
    if key:
        return key

    return None