"""
Blueprint Authentication for Murphy System

Provides a shared utility that applies API key authentication to any Flask
Blueprint so that each blueprint is self-defending even when mounted on a
bare (unsecured) Flask application.

Usage::

    from src.blueprint_auth import require_blueprint_auth
    bp = Blueprint("my_api", __name__, url_prefix="/api/my")
    # … register routes …
    require_blueprint_auth(bp)
    return bp

Environment variables:
    MURPHY_ENV        - Set to ``production`` or ``staging`` to enable auth.
                        Defaults to ``development`` (auth skipped).
    MURPHY_API_KEYS   - Comma-separated list of valid API keys (legacy alias; MURPHY_API_KEY is canonical).

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import hmac
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from flask import jsonify, request
    _HAS_FLASK = True
except ImportError:  # pragma: no cover
    _HAS_FLASK = False


def require_blueprint_auth(blueprint: Any) -> Any:
    """Apply API key authentication to a Flask Blueprint.

    Registers a ``before_request`` hook that validates the ``Authorization:
    Bearer <token>`` or ``X-API-Key: <token>`` header against the keys
    listed in ``MURPHY_API_KEY`` (or legacy ``MURPHY_API_KEYS``).

    Behaviour by environment (``MURPHY_ENV``):
    - ``development`` / ``test``  — auth is **skipped** (with a startup log).
    - ``staging`` / ``production`` — auth is **enforced** (401 if no valid key).

    Health-check endpoints (``/health``, ``/healthz``, ``/ready``) are always
    exempt so that load-balancer probes continue to work.

    Args:
        blueprint: A :class:`flask.Blueprint` instance.

    Returns:
        The same blueprint (for chaining).
    """
    if not _HAS_FLASK or blueprint is None:
        return blueprint

    @blueprint.before_request  # type: ignore[misc]
    def _check_auth() -> Any:  # noqa: WPS430
        murphy_env = os.environ.get("MURPHY_ENV", "development")

        # Skip auth in development / test mode
        if murphy_env in ("development", "test"):
            return None

        # Health-check endpoints are always exempt
        path = request.path.rstrip("/")
        for suffix in ("/health", "/healthz", "/ready"):
            if path.endswith(suffix) or path == suffix.lstrip("/"):
                return None

        # OPTIONS (CORS preflight) is exempt
        if request.method == "OPTIONS":
            return None

        # Extract token from Authorization header or X-API-Key header
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif api_key_header:
            token = api_key_header.strip()

        # Load configured API keys
        api_keys_raw = os.environ.get("MURPHY_API_KEY", "") or os.environ.get("MURPHY_API_KEYS", "")
        api_keys = [k.strip() for k in api_keys_raw.split(",") if k.strip()]

        if not api_keys:
            if murphy_env in ("staging", "production"):
                logger.error(
                    "Blueprint %s: MURPHY_API_KEY not configured in %s — "
                    "REJECTING all requests. Set MURPHY_API_KEY to enable access.",
                    blueprint.name,
                    murphy_env,
                )
                return jsonify({"error": "Service misconfigured — API keys required"}), 503
            logger.warning(
                "Blueprint %s: MURPHY_API_KEY not configured in %s — "
                "all requests are allowed.",
                blueprint.name,
                murphy_env,
            )
            return None

        if not token:
            logger.warning(
                "Blueprint %s: missing API key from %s",
                blueprint.name,
                request.remote_addr,
            )
            return jsonify({"error": "Unauthorized"}), 401

        if not any(hmac.compare_digest(token, k) for k in api_keys):
            logger.warning(
                "Blueprint %s: invalid API key from %s",
                blueprint.name,
                request.remote_addr,
            )
            return jsonify({"error": "Unauthorized"}), 401

        return None

    return blueprint
