"""
OpenTelemetry tracing scaffold — Class S Roadmap, Item 6.

This module is the optional, no-op-by-default tracing setup for Murphy.
It is **deliberately** a thin wrapper that:

1. Does nothing if the ``opentelemetry`` packages are not installed
   (development environments and the slim CI test image do not need
   them).
2. Does nothing if ``MURPHY_OTEL_ENABLED`` is not truthy
   (production opt-in switch).
3. When both conditions are met, configures an OTLP exporter from
   environment variables, instruments FastAPI and HTTPX, and registers
   a process-wide ``TracerProvider``.

The wiring point (``configure_tracing(app)`` near the existing
``configure_logging()`` call in ``src/runtime/app.py``) is the only
caller a follow-up PR needs to add. Until it does, importing this
module costs nothing at runtime, even when OpenTelemetry is not
installed — verified by the unit tests in
``tests/test_runtime_tracing.py``.

Environment variables
---------------------
MURPHY_OTEL_ENABLED : bool
    ``true``/``1``/``yes`` to enable tracing. Default: false.
OTEL_SERVICE_NAME : str
    Service name reported in spans. Default: ``murphy-system``.
OTEL_EXPORTER_OTLP_ENDPOINT : str
    Collector endpoint, e.g. ``http://otel-collector:4317``. The OTLP
    exporter reads this directly when present.
OTEL_TRACES_SAMPLER, OTEL_TRACES_SAMPLER_ARG : str
    Standard OTel sampler controls (e.g. ``parentbased_traceidratio``
    + ``0.1``).

The intentional non-goals of this scaffold are:

* No vendor-specific exporter (Datadog, New Relic, Honeycomb) — all of
  those speak OTLP, so the standard exporter is sufficient.
* No metrics pipeline. Prometheus already covers metrics
  (``prometheus-rules/murphy-slo-alerts.yml``); duplicating the same
  signals through OTel would be wasteful.
* No log-export bridge. ``src/logging_config.py`` already emits
  structured JSON; collectors should ingest stdout, not OTel logs.

See ``docs/adr/`` for the architectural decision once tracing is wired.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Set to True after a successful ``configure_tracing()`` call so repeat
#: calls (e.g. from test fixtures) become no-ops instead of producing
#: duplicate provider warnings.
_CONFIGURED: bool = False


def is_enabled() -> bool:
    """Return True if tracing should be configured.

    Honors ``MURPHY_OTEL_ENABLED`` (truthy values: ``1``, ``true``,
    ``yes``, ``on`` — case-insensitive). Defaults to False so the
    scaffold has no production effect until explicitly opted in.
    """
    raw = os.environ.get("MURPHY_OTEL_ENABLED", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def configure_tracing(app: Optional[Any] = None) -> bool:
    """Configure OpenTelemetry tracing if the environment opts in.

    Returns True if tracing was successfully configured, False otherwise.
    Safe to call multiple times — subsequent calls return True without
    re-initializing the provider.

    Parameters
    ----------
    app : FastAPI, optional
        If provided and ``opentelemetry-instrumentation-fastapi`` is
        installed, the FastAPI app will be instrumented for HTTP-server
        spans. Other instrumentations (HTTPX client, SQLAlchemy) attach
        themselves globally and do not need the app object.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return True
    if not is_enabled():
        logger.debug(
            "OTel tracing disabled (MURPHY_OTEL_ENABLED not set). "
            "configure_tracing() is a no-op."
        )
        return False

    # Imports are inside the function so the module is importable in
    # environments that have not installed opentelemetry. Each piece
    # degrades independently — missing the FastAPI instrumentor does
    # not prevent the SDK from initializing.
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "OTel tracing requested via MURPHY_OTEL_ENABLED but the "
            "opentelemetry SDK is not installed: %s. Skipping setup.",
            exc,
        )
        return False

    service_name = os.environ.get("OTEL_SERVICE_NAME", "murphy-system")
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    logger.info(
        "OTel tracing configured (service=%s, OTLP exporter active).",
        service_name,
    )

    # Optional FastAPI instrumentation. Errors here are non-fatal —
    # the SDK is still configured and outbound clients can be
    # instrumented separately.
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import (
                FastAPIInstrumentor,
            )
            FastAPIInstrumentor.instrument_app(app)
            logger.debug("FastAPI instrumentation attached.")
        except ImportError:
            logger.debug(
                "opentelemetry-instrumentation-fastapi not installed; "
                "skipping FastAPI instrumentation."
            )
        except Exception as exc:  # noqa: BLE001 — instrumentation must never crash boot
            logger.warning(
                "FastAPI instrumentation failed (%s: %s). Tracing SDK "
                "is still active for manual spans.",
                type(exc).__name__,
                exc,
            )

    _CONFIGURED = True
    return True


def reset_for_tests() -> None:
    """Reset the module state so tests can re-exercise configure_tracing.

    Intended only for use by the test suite; do not call from runtime
    code (the OTel SDK does not support re-initialization cleanly).
    """
    global _CONFIGURED
    _CONFIGURED = False
