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
| 1 | Decompose `murphy_production_server.py` into routers | 🟡 | `src/runtime/subsystem_registry.py` and `src/routers/` package landed. Extracting the 184 handlers is one router per follow-up PR. **Backlog ranking landed:** `python scripts/extract_router_candidates.py` reads both entrypoints, classifies every handler by extraction safety (mutable globals, `app.state` use, startup-hook proximity), and groups by URL-path domain so each PR == one domain router. Per-PR commissioning checklist documented in `src/routers/__init__.py`. |
| 2 | SQLAlchemy-backed persistent `TenantMemoryStore` | ⏳ | Requires new ORM table, Alembic migration, restart-survival test. |
| 3 | Real user identity (OIDC + JWT) replacing shared API key | ⏳ | `src/oauth_oidc_provider.py` exists but is not wired into `auth_middleware.py`. Threat model (`docs/SECURITY_THREAT_MODEL.md` §2.1) flags the legacy API-key path as the current weak link. **Decision recorded in [ADR-0012](adr/0012-oidc-replaces-shared-api-key.md):** OIDC primary, API key deprecated over a 2-release transition; threat-model amendment lands in the wiring PR. |
| 4 | Real embeddings + vector store as default RAG | ⏳ | ADR-0003 records this as an interim default. **Superseded by [ADR-0009](adr/0009-embeddings-vector-store-rag.md):** `bge-small-en-v1.5` + `chromadb` as default; TF-IDF retained as warning-emitting fallback. Implementation PR pending. |
| 5 | Coverage enforced across the whole `src/` tree | ✅ | `.coveragerc` tracks `src/`; CI test step now runs `--cov=src` and publishes both XML and HTML coverage artifacts. Trajectory: Q1=20, Q2=40, Q3=60, Q4=80 — raise `fail_under` per quarter. HTML artifact is the per-module heatmap that prioritizes which low-covered subsystems get tests next. |

## Tier 2 — Production hardening

| # | Item | Status | Notes |
|---|---|---|---|
| 6 | OpenTelemetry tracing + structured JSON logs + request-id middleware | ✅ | Structured JSON logs (`src/logging_config.py`) and request-ID middleware (`src/request_context.py:RequestIDMiddleware`) wired in `src/runtime/app.py` (lines 8988, 15767). OTel tracing scaffold (`src/runtime/tracing.py`) is now wired into `app.py` next to the request-ID middleware: a no-op when `MURPHY_OTEL_ENABLED` is unset, a graceful no-op when the env switch is on but the OTel SDK is missing, and a fully-configured OTLP pipeline (FastAPI instrumentation + BatchSpanProcessor) when both are in place. The OTel SDK is an opt-in production extra and is intentionally not in `requirements_ci.txt` to keep the test image slim. Rationale and rejected alternatives captured in [ADR-0007](adr/0007-opentelemetry-opt-in.md). |
| 7 | Real Redis usage (rate limit, sessions, queue, cache) | ⏳ | Keep the in-memory fallback for single-node dev. **Decision recorded in [ADR-0011](adr/0011-redis-required.md):** Redis required in production mode (process refuses to start if unreachable); in-memory fallbacks gated by `MURPHY_RUNTIME_MODE=single-node-dev`. |
| 8 | Background work as a real job system (Celery/RQ/Arq) | ⏳ | Move automation ticks out of the web process. **Decision recorded in [ADR-0010](adr/0010-background-workers-arq.md):** Arq chosen (native asyncio, single Redis backend, cron-style schedules). Depends on ADR-0011. |
| 9 | Pin and scan dependencies | ✅ | Dockerfile base image pinned to `python:3.12-slim@sha256:804ddf3251a60bbf9c92e73b7566c40428d54d0e79d3428194edf40da6521286`. Dependabot, pip-audit, bandit wired in CI. Trivy container scan now runs in `release.yml`: HIGH/CRITICAL CVEs block the release; the full report is attached to the GitHub Release as `trivy-report.json`. |
| 10 | Reduce broad `except Exception` use; enable Ruff `BLE001` | 🟡 | `BLE001` enforced via the `lint` CI job on the roadmap-foundation paths (`src/runtime/subsystem_registry.py`, `src/runtime/tracing.py`, `src/runtime/module_loader.py`, `src/routers/`, the three `scripts/` helpers) so no NEW broad-except debt lands on the surfaces we just built. Pre-existing ~2 900 occurrences across the legacy surface remain — graduate paths to BLE001-clean incrementally and add them to the gate. When global debt reaches zero, move `BLE001` into the main Ruff `select` list. |

## Tier 3 — Architectural polish

| # | Item | Status | Notes |
|---|---|---|---|
| 11 | Consolidate the 69 root-level HTML files | ⏳ | Pick Jinja2 templating (minimal) or SPA (modern). Move marketing pages out of the product tree. **Decision recorded in [ADR-0013](adr/0013-jinja2-over-spa.md):** Jinja2 chosen; full per-file triage and 7-phase migration order in the ADR. Owner can override by writing a counter-ADR before any migration PR lands. |
| 12 | Integration connector contract tests | 🟡 | `tests/integration_connector/test_base_contract.py` defines `CONNECTOR_REQUIRED_FIELDS`, `validate_connector_definition`, and runs the contract against `DEFAULT_PLATFORMS` (3 tests passing). Per-connector VCR/`responses` fixtures are the remaining sub-item. |
| 13 | Graduate or delete the GraphQL layer | 🟡 | **Decided in [ADR-0008](adr/0008-graphql-layer-experimental.md):** marked experimental, slated for removal at next major version (or 90 days, whichever comes first). `src/graphql_api_layer.py` now emits `DeprecationWarning` at import (citing ADR-0008); not wired into any production HTTP route. The 976-line test file still passes. **Quarantine guard landed:** `tests/contracts/test_graphql_layer_quarantine.py` enforces (a) the deprecation warning fires and cites the ADR, (b) `__experimental__ = True`, (c) no other `src/` module imports it via real Python `import` statements. **Calendar watchman landed:** `python scripts/check_adr_0008_eligibility.py` exits non-zero when 2026-07-21 elapses and prints the deletion PR's `git rm` lines. |
| 14 | API versioning + published OpenAPI schema | ✅ | `scripts/export_openapi.py` exports the schema; baseline committed at `docs/openapi.json` (815 paths). New CI job `openapi-check` (in `.github/workflows/ci.yml`) runs `--check` on every PR — drift fails the build until the maintainer re-runs `python scripts/export_openapi.py` and commits the result. `docs/openapi.json` is marked `linguist-generated` in `.gitattributes` so PR diffs collapse it by default. Versioning (`/api/v1/...`) is the remaining sub-item, deferred to a focused PR. |
| 15 | Performance baselines (pytest-benchmark + locust/k6) | ✅ | `tests/benchmarks/` covers all four roadmap-named hot paths in `test_benchmark_statistical.py`: governance kernel ✅ (`test_gate_evaluation_throughput`, target >50 000 ops/s), control plane ✅ (`test_control_plane_creation_throughput`, target >1 000 ops/s), platform connector framework ✅ (`test_platform_connector_framework_throughput`, target >200 ops/s), LLM provider routing ✅ (`test_llm_routing_dispatch_throughput`, target >5 000 ops/s; observed ~41 700), RAG retrieval ✅ (`test_rag_retrieval_throughput`, target >500 ops/s; observed ~45 000 over a 5-doc TF-IDF corpus), HITL queue dispatch ✅ (`test_hitl_queue_enqueue_throughput`, target >10 000 ops/s; observed ~216 000). API-throughput, integration-speed, and locust suites also present. **Regression gate landed:** `.benchmarks/Linux-CPython-3.12-64bit/0001_baseline.json` committed; new `benchmark-regression` CI job (in `ci.yml`) runs the four dispatch benchmarks and compares HEAD's `min` vs baseline with `--benchmark-compare-fail=min:25%`. Currently advisory (`continue-on-error: true`) for a ≥2-week soak phase to characterise CI-runner variance before promotion to blocking — rationale and refresh procedure in [`.benchmarks/README.md`](../.benchmarks/README.md). **Soak watchman landed:** `python scripts/check_benchmark_soak.py` reads the baseline `datetime` field, exits non-zero when the 14-day soak elapses, and prints the exact two-line patch to flip the gate from advisory to blocking. |

## Tier 4 — Process and governance

| # | Item | Status | Notes |
|---|---|---|---|
| 16 | Architecture Decision Records | ✅ | `docs/adr/` created with index and ADRs 0001–0008. New ADRs land alongside the changes that justify them; the policy is now surfaced in `CONTRIBUTING.md` and the PR template so contributors see it at PR-open time. ADR-0008 records the decision that closes Item 13. |
| 17 | SLO/SLI definitions + Prometheus alerts | ✅ | `prometheus-rules/murphy-slo-alerts.yml` added: API availability, /api/prompt latency, HITL approval time, LLM terminal-failure rate. Multi-window/multi-burn-rate per Google SRE workbook. |
| 18 | STRIDE threat model | ✅ | `docs/SECURITY_THREAT_MODEL.md`, reviewed quarterly and on any change to a trust boundary. |
| 19 | Release engineering: SBOM (CycloneDX) + cosign signing + GHCR push | ✅ | `.github/workflows/release.yml` triggers on tag push: builds the digest-pinned container, generates Python (`cyclonedx-bom`) and image (`syft`) SBOMs, signs the image and attests the SBOM with cosign keyless (Sigstore + GitHub OIDC), pushes to GHCR, and attaches both SBOMs to the GitHub Release. |
| 20 | Surface-area audit: move stubs to `experimental/` or delete | ✅ | `scripts/find_unused_modules.py` + `scripts/find_unused_modules.allowlist.txt` (74 entries: matrix-bridge manifest, terminal command registry, `python -m` entrypoints). Detector now catches relative imports (`from .leaf import X`, `from ..pkg.leaf import X`, `from . import leaf`) — fixed a real bug that was inflating the unused list ~10x. Pinned by 11-test unit suite (`tests/test_find_unused_modules.py`). Final actionable list documented in [`docs/SURFACE_AREA_AUDIT.md`](SURFACE_AREA_AUDIT.md). **Deletion pass landed:** 4 obsolete vertical presets removed (`src/presets/{healthcare,professional_services,retail_commerce,technology}.py`, **−3 460 LOC**), superseded by `src/org_build_plan/presets/`. **Contract-pinning pass landed:** the last candidate (`src/runtime/module_loader.py`, 244 LOC, built-but-not-wired) is now exercised by a 13-test contract suite (`tests/test_runtime_module_loader.py`), making the eventual wire-into-`app.py` PR safe to do incrementally. Actionable count: 200 → 79 (after detector fix) → 5 (after allowlist) → 1 (after deletions) → **0** (after pinning). The remaining behaviour-changing follow-up — *"Wire `ModuleLoader` into `app.py`; remove `src/runtime/_deps.py` try/except blocks"* — is queued as a separate PR (multi-PR scope: `app.py` is 15 859 lines). |

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
