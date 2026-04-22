# ADR-0007: OpenTelemetry tracing is opt-in, not on-by-default

* **Status:** Accepted
* **Date:** 2026-04-22
* **Implementation:** `src/runtime/tracing.py`, `src/runtime/app.py`
  (call site next to `RequestIDMiddleware` registration),
  `tests/test_runtime_tracing.py`

## Context

Class S Roadmap Item 6 calls for distributed tracing alongside the
already-shipped structured JSON logs (`src/logging_config.py`) and
request-ID middleware (`src/request_context.py:RequestIDMiddleware`).
Tracing rounds out the three-pillar observability model
(logs / metrics / traces) and is the precondition for any meaningful SLO
investigation in production — the SLO-burn alerts in
`prometheus-rules/murphy-slo-alerts.yml` (ADR scope: Item 17) tell us
*that* the budget is burning; traces tell us *why*.

The constraints we had to satisfy:

1. **Boot must never depend on tracing.** Murphy is a self-modification
   platform; an observability bug must not be able to wedge the system.
2. **The CI image must stay slim.** Adding the OTel SDK + OTLP exporter +
   FastAPI/HTTPX/SQLAlchemy instrumentations to `requirements_ci.txt`
   would roughly double the test image size and the cold-start time on
   every CI run, with no benefit to the tests themselves.
3. **No vendor lock-in.** The choice of where traces flow (Jaeger,
   Tempo, a managed APM) is an operator decision, not a source-tree
   decision.
4. **Local dev must work without any tracing infrastructure running.**
   A developer running `uvicorn` against a fresh checkout should not see
   exporter-connection-refused errors filling their console.

## Decision

* Adopt **OpenTelemetry** (vendor-neutral, CNCF-graduated) as the
  tracing API. Do not adopt a vendor SDK (Datadog, New Relic, Sentry
  performance) — operators can attach those via OTLP exporters or
  in-process bridges if they want them, without us hard-coding the
  choice.
* Tracing is **opt-in via a single env switch**: `MURPHY_OTEL_ENABLED`.
  When unset (the default in dev, CI, and any deployment that hasn't
  explicitly enabled it), `configure_tracing(app)` is a documented
  no-op that returns `False` and logs nothing.
* The OTel SDK is **a production extra**, intentionally excluded from
  `requirements_ci.txt`. Operators install
  `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, and the FastAPI
  instrumentation in their production image.
* When the env switch is on **but** the SDK is missing, `configure_tracing`
  fails gracefully — it logs a single warning and returns `False` rather
  than raising. The wiring site in `app.py` is also wrapped in a
  defensive `try/except` (with an explicit `# noqa: BLE001` rationale)
  for the same reason: **tracing must never block boot**.
* Span attributes follow the [OTel semantic conventions for HTTP][semconv]:
  `http.method`, `http.route`, `http.status_code`, plus the existing
  `X-Request-ID` propagated as a span attribute so that a trace, a
  request-ID-tagged log line, and an HITL audit-ledger entry can all be
  joined on the same key.
* The exporter is **OTLP/gRPC by default**, configurable via the
  standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var. We do not invent our
  own configuration surface.

[semconv]: https://opentelemetry.io/docs/specs/semconv/http/

### Alternatives rejected

* **On-by-default with a no-op exporter.** Rejected: the SDK still
  imports heavy modules, lengthens cold-start, and a misconfigured
  exporter url silently dropping spans is worse than the operator
  consciously turning tracing on.
* **A single vendor APM (Datadog / New Relic).** Rejected: locks the
  source tree to one billing relationship and one wire format. OTLP
  with vendor-side ingest is the modern equivalent and keeps
  `src/runtime/tracing.py` vendor-free.
* **Sentry-only performance traces.** Rejected: Sentry is excellent for
  errors but its performance product is sampled aggressively and not
  designed for SLO-burn forensics.
* **A custom span emitter on top of `logging`.** Rejected: re-implements
  context propagation, baggage, and W3C traceparent badly, and locks us
  out of the wider OTel-instrumented library ecosystem (HTTPX,
  SQLAlchemy, Celery, etc.).

## Consequences

* **Positive:** zero runtime cost when disabled; zero new CI image
  weight; zero dev-onboarding friction. The default `pip install -r
  requirements_ci.txt` cold-start is unchanged.
* **Positive:** when an operator turns tracing on in production, the
  same OTLP endpoint can fan out to Jaeger / Tempo / Honeycomb /
  Datadog / New Relic / Splunk simultaneously via an OTel Collector.
  No source change required to switch backends.
* **Positive:** request-ID, log line, trace, and HITL audit ledger
  share the same correlation key — incident forensics is one query
  away in any of the four stores.
* **Negative:** "is tracing on?" becomes a deploy-time question.
  Operators must read `docs/RUNBOOKS.md` to know how to turn it on.
  We accept this in exchange for the boot-safety and CI-weight wins.
* **Negative:** the opt-in path means the very first time tracing is
  enabled in a new environment, the operator has to also install the
  SDK extras. We document this explicitly in the `tracing.py` module
  docstring and in the runbook.
* **Negative:** we cannot rely on traces being present when triaging an
  incident in an environment where the operator forgot to enable them.
  The `X-Request-ID` + structured logs + HITL ledger combination
  remains the always-on forensic floor.
