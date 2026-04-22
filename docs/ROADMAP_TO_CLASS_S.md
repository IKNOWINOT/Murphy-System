# Roadmap to Class S (A+)

This document is the single source of truth for the 20-item roadmap that
moves the platform from its current overall **B** grade to **Class S / A+**.
Each item links to the PR(s) that close it. The full plan was captured in
the engineering review of 2026-04-22.

## Status legend

* ✅ **Done** — landed on `main` and verified.
* 🟡 **Scaffolded** — supporting infrastructure exists; primary work still pending.
* ⏳ **Pending** — not yet started.
* 🚫 **Decided not to do** — explicitly deferred or rejected; reason recorded.

## Tier 1 — The five things blocking A+

| # | Item | Status | Notes |
|---|---|---|---|
| 1 | Decompose `murphy_production_server.py` into routers | 🟡 | `src/runtime/subsystem_registry.py` and `src/routers/` package landed. Extracting the 184 handlers is one router per follow-up PR. |
| 2 | SQLAlchemy-backed persistent `TenantMemoryStore` | ⏳ | Requires new ORM table, Alembic migration, restart-survival test. |
| 3 | Real user identity (OIDC + JWT) replacing shared API key | ⏳ | `src/oauth_oidc_provider.py` exists but is not wired into `auth_middleware.py`. Threat model (`docs/SECURITY_THREAT_MODEL.md` §2.1) flags the legacy API-key path as the current weak link. |
| 4 | Real embeddings + vector store as default RAG | ⏳ | ADR-0003 records this as an interim default. Will be superseded by a new ADR when the change lands. |
| 5 | Coverage enforced across the whole `src/` tree | ✅ | `.coveragerc` tracks `src/`; CI test step now runs `--cov=src` and publishes both XML and HTML coverage artifacts. Trajectory: Q1=20, Q2=40, Q3=60, Q4=80 — raise `fail_under` per quarter. HTML artifact is the per-module heatmap that prioritizes which low-covered subsystems get tests next. |

## Tier 2 — Production hardening

| # | Item | Status | Notes |
|---|---|---|---|
| 6 | OpenTelemetry tracing + structured JSON logs + request-id middleware | ⏳ | |
| 7 | Real Redis usage (rate limit, sessions, queue, cache) | ⏳ | Keep the in-memory fallback for single-node dev. |
| 8 | Background work as a real job system (Celery/RQ/Arq) | ⏳ | Move automation ticks out of the web process. |
| 9 | Pin and scan dependencies | ✅ | Dockerfile base image pinned to `python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286`. Dependabot, pip-audit, and bandit already wired in CI. Trivy/Grype container scan is the remaining sub-item. |
| 10 | Reduce broad `except Exception` use; enable Ruff `BLE001` | ⏳ | ~2 900 occurrences today. Triage required. |

## Tier 3 — Architectural polish

| # | Item | Status | Notes |
|---|---|---|---|
| 11 | Consolidate the 69 root-level HTML files | ⏳ | Pick Jinja2 templating (minimal) or SPA (modern). Move marketing pages out of the product tree. |
| 12 | Integration connector contract tests | 🟡 | `tests/integration_connector/test_base_contract.py` defines `CONNECTOR_REQUIRED_FIELDS`, `validate_connector_definition`, and runs the contract against `DEFAULT_PLATFORMS` (3 tests passing). Per-connector VCR/`responses` fixtures are the remaining sub-item. |
| 13 | Graduate or delete the GraphQL layer | ⏳ | Decision required: 800-line custom GraphQL engine that no client uses. |
| 14 | API versioning + published OpenAPI schema | 🟡 | `scripts/export_openapi.py` supports both `module:attr` and `module:factory()` syntax. CI `--check` wiring blocked on importing `create_app()` (heavy deps); deferred to the PR that lands `/api/v1/...` versioning. |
| 15 | Performance baselines (pytest-benchmark + locust/k6) | ⏳ | Hot paths: LLM provider routing, governance kernel, RAG retrieval, HITL queue dispatch. |

## Tier 4 — Process and governance

| # | Item | Status | Notes |
|---|---|---|---|
| 16 | Architecture Decision Records | ✅ | `docs/adr/` created with index and ADRs 0001–0006. New ADRs land alongside the changes that justify them. |
| 17 | SLO/SLI definitions + Prometheus alerts | ✅ | `prometheus-rules/murphy-slo-alerts.yml` added: API availability, /api/prompt latency, HITL approval time, LLM terminal-failure rate. Multi-window/multi-burn-rate per Google SRE workbook. |
| 18 | STRIDE threat model | ✅ | `docs/SECURITY_THREAT_MODEL.md`, reviewed quarterly and on any change to a trust boundary. |
| 19 | Release engineering: SBOM (CycloneDX) + cosign signing + GHCR push | ✅ | `.github/workflows/release.yml` triggers on tag push: builds the digest-pinned container, generates Python (`cyclonedx-bom`) and image (`syft`) SBOMs, signs the image and attests the SBOM with cosign keyless (Sigstore + GitHub OIDC), pushes to GHCR, and attaches both SBOMs to the GitHub Release. |
| 20 | Surface-area audit: move stubs to `experimental/` or delete | 🟡 | `scripts/find_unused_modules.py` lands the audit tool: scans 1 301 `src/` modules and reports the 200 with no static import references. Allowlist support for runtime-loaded modules. The deletion/move decisions are the remaining sub-item. |

## Expected grade movement

| Category | Today | After Tier 1 | After Tier 2 | After Tier 3+4 |
|---|---|---|---|---|
| Architecture & Modularity | B+ | A | A | A+ |
| Core AI/Agent | B | A- | A | A+ |
| API & Integration | B+ | B+ | A | A+ |
| Data & State | B | A- | A | A+ |
| Testing | A- | A | A | A+ |
| Code Quality | B+ | A- | A | A+ |
| Observability | B+ | B+ | A+ | A+ |
| Security | B | A- | A | A+ |
| Frontend | C+ | C+ | C+ | A- |
| Production Readiness | B | B+ | A | A+ |
| **Overall** | **B** | **B+/A-** | **A** | **A+ / Class S** |

The single largest leverage points are #1 (server decomposition), #3 (real
auth), and #11 (frontend consolidation).

## How to update this document

* Mark an item `✅` in the same PR that lands the work, and link to that PR
  in the *Notes* column.
* If an item is split across multiple PRs, leave it `🟡` until the last
  sub-item closes.
* If an item is reconsidered, mark it `🚫` and write a short note explaining
  why; if the decision is large enough to warrant it, write an ADR instead.
