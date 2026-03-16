"""
Structured Logging Configuration for Murphy System.

Provides environment-aware logging:
  - ``development`` — human-readable colored output (standard formatter)
  - ``production`` / ``staging`` — JSON lines format parseable by ELK,
    Datadog, CloudWatch, and other log aggregators

Environment variables
---------------------
MURPHY_ENV : str
    Runtime environment: ``development`` (default), ``test``,
    ``staging``, or ``production``.
MURPHY_LOG_FORMAT : str
    ``text`` — human-readable output (always, overrides env default)
    ``json`` — JSON lines output (always, overrides env default)
LOG_LEVEL : str
    Standard log level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``,
    ``CRITICAL``.  Default: ``INFO``.

Usage::

    from logging_config import configure_logging
    configure_logging(env="production")

    # Or read from environment:
    configure_logging()

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import traceback
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Request ID integration (optional — used when request_context is available)
# ---------------------------------------------------------------------------

try:
    from request_context import get_request_id  # type: ignore[import]
    _HAS_REQUEST_CONTEXT = True
except ImportError:
    _HAS_REQUEST_CONTEXT = False


def _get_request_id() -> str:
    if _HAS_REQUEST_CONTEXT:
        try:
            return get_request_id() or ""
        except Exception as exc:
            return ""
    return ""


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Formats log records as JSON lines for log aggregators.

    Each line is a valid JSON object with fields:
        timestamp, level, logger, message, request_id, module, function
    Exception information is included as ``exception`` when present.
    Extra fields passed via ``extra={}`` are merged into the top-level object.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _get_request_id(),
            "module": record.module,
            "function": record.funcName,
        }

        # Merge extra fields (skip internal Python log record attributes)
        _skip = frozenset(logging.LogRecord.__dict__) | {
            "message", "asctime", "args", "msg",
        }
        for key, value in record.__dict__.items():
            if key not in _skip and not key.startswith("_"):
                try:
                    json.dumps(value)  # check serialisability
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Text formatter (development)
# ---------------------------------------------------------------------------

_TEXT_FORMAT = (
    "%(asctime)s [%(levelname)-8s] %(name)s:%(funcName)s — %(message)s"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def configure_logging(env: str | None = None, level: str | None = None) -> None:
    """Configure application-wide logging for the given environment.

    Args:
        env: Runtime environment string.  Reads ``MURPHY_ENV`` if not
            provided.  Recognised values: ``development``, ``test``,
            ``staging``, ``production``.
        level: Log level string (e.g. ``"INFO"``).  Reads ``LOG_LEVEL``
            env var if not provided.  Defaults to ``"INFO"``.

    In ``development``/``test``, logs are human-readable text.
    In ``staging``/``production``, logs are JSON lines (one per record).

    The ``MURPHY_LOG_FORMAT`` env var (``text`` | ``json``) overrides the
    environment-derived default.
    """
    if env is None:
        env = os.environ.get("MURPHY_ENV", "development").lower()
    else:
        env = env.lower()

    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Honour explicit format override
    _log_format_override = os.environ.get("MURPHY_LOG_FORMAT", "").lower()
    _production_envs = {"production", "staging"}

    use_json = (
        _log_format_override == "json"
        or (env in _production_envs and _log_format_override != "text")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove any pre-existing handlers to avoid duplicate output
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, level, logging.INFO))

    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

    root_logger.addHandler(handler)
    logging.getLogger(__name__).debug(
        "Logging configured: env=%s level=%s format=%s",
        env,
        level,
        "json" if use_json else "text",
    )
