# Deferred multi-PR follow-up queue

This file is the canonical queue of work that was *honestly deferred* out of
the current branch per CLAUDE.md §3 (surgical changes). Each row names the
next PR by its exact title, why it was deferred, and what "done" looks like
when commissioning per the eight-question checklist.

This file exists so deferrals are auditable rather than implicit. A row is
removed from this file in the same PR that closes it.

## Legend

* **Title** — verbatim PR title for the maintainer to copy-paste.
* **Why deferred** — the entry condition that was not met when the parent
  branch landed.
* **Acceptance criteria** — the eight-question commissioning checklist
  collapsed into the smallest verifiable set for that item.
* **Tooling** — repo-local helper(s) the deletion / soak / extraction PR
  uses to confirm eligibility.

## Queue

### Item 1 (per router) — "Extract router N from murphy_production_server.py"

| Field | Value |
|---|---|
| Why deferred | Cardinal mismatch: 184 handlers ⇒ ~184 PRs by definition. The single-PR scaffolding is in `src/routers/__init__.py`. |
| Acceptance | (1) `python scripts/extract_router_candidates.py --top 1` names the next domain; (2) new `src/routers/<domain>.py` exposes module-level `router`; (3) `app.include_router(<domain>.router)` added in entrypoint; (4) legacy inline handlers deleted in same commit; (5) existing route smoke tests pass byte-identical; (6) `ruff check --select=BLE001 src/routers/` clean; (7) Roadmap Item 1 row updated with `N of 184 extracted`. |
| Tooling | `scripts/extract_router_candidates.py` |

### Item 2 — "Persistent TenantMemoryStore: ORM table + Alembic migration + restart-survival test"

| Field | Value |
|---|---|
| Why deferred | New schema requires its own focused PR; not bundled with the deferral-tracking branch. |
| Acceptance | (1) `SQLAlchemyTenantMemoryStore` exposes the same public surface as `TenantMemoryStore`; (2) Alembic migration `002_tenant_memory.py` adds `tenant_memory_entries` table with composite PK `(tenant_id, key)` and `created_at`/`updated_at`; (3) restart-survival test inserts via instance A, instantiates instance B against the same DB, asserts retrieval succeeds; (4) `MURPHY_TENANT_MEMORY_BACKEND={memory,sqlalchemy}` env switch; (5) docs updated in `docs/CONFIGURATION.md`; (6) old in-memory store retained as default until N+1. |
| Tooling | existing `alembic` machinery |

### Item 3 — "Wire oauth_oidc_provider.py into auth_middleware.py; deprecate the shared API key"

| Field | Value |
|---|---|
| Why deferred | Trust-boundary change. ADR + threat-model amendment is the entry condition. |
| Acceptance | Per [ADR-0012](adr/0012-oidc-replaces-shared-api-key.md): JWT primary, session cookie secondary, API key deprecated fallback gated by `MURPHY_ALLOW_API_KEY`; threat model §2.1 rewritten in same PR; `tests/auth/test_oidc_middleware.py` covers the 18 cases enumerated in the ADR; `mock-oauth2-server` container in CI. |
| Tooling | [ADR-0012](adr/0012-oidc-replaces-shared-api-key.md) |

### Item 4 — "Replace TF-IDF default RAG with embeddings + vector store"

| Field | Value |
|---|---|
| Why deferred | Required a superseding ADR before code; ADR-0009 was that artifact. |
| Acceptance | Per [ADR-0009](adr/0009-embeddings-vector-store-rag.md): `bge-small-en-v1.5` via `sentence-transformers` + `chromadb` persistent-client default; TF-IDF retained as `RuntimeWarning`-emitting fallback; `rag-recall-smoke` CI job asserts top-1 recall ≥0.8 on 5 paraphrased queries; reindex via idempotent `scripts/reindex_rag.py`; ADR-0003 marked Superseded by 0009 (already done in this PR). |
| Tooling | [ADR-0009](adr/0009-embeddings-vector-store-rag.md) |

### Item 7 — "Promote Redis from optional to required for rate-limit/sessions/queue/cache"

| Field | Value |
|---|---|
| Why deferred | Production deployment break. ADR-0011 captures the decision; the breaking-change PR is the implementation. |
| Acceptance | Per [ADR-0011](adr/0011-redis-required.md): `MURPHY_RUNTIME_MODE` env (`single-node-dev` vs `production`); production mode raises `RuntimeError` on missing Redis at startup; `src/runtime/redis_client.py` consolidates client construction; `/api/health` returns 503 when Redis down in prod; `tests/runtime/test_runtime_mode.py` covers both modes; release notes lead with the breaking change. |
| Tooling | [ADR-0011](adr/0011-redis-required.md) |

### Item 8 — "Move automation ticks out of the web process into Arq"

| Field | Value |
|---|---|
| Why deferred | Architectural choice (Arq vs Celery vs RQ); ADR-0010 is the entry condition. Depends on ADR-0011. |
| Acceptance | Per [ADR-0010](adr/0010-background-workers-arq.md): `src/workers/{queue,jobs}.py` with Arq `WorkerSettings`; web process no longer schedules ticks; separate worker container in compose/k8s; Arq dead-letter stream wired to Prometheus counter `murphy_arq_dead_jobs_total`; `worker-smoke` CI job boots Redis + Arq and asserts each tick type meets its declared SLA. |
| Tooling | [ADR-0010](adr/0010-background-workers-arq.md) |

### Item 10 (continuing) — "Graduate next path-group to BLE001-clean"

| Field | Value |
|---|---|
| Why deferred | Each graduation is a focused, owner-owned audit; sequencing is per-file. |
| Acceptance | (1) Pick file via the `BLE001` lint output; (2) every `except Exception` either narrowed to a specific exception class or annotated with `# noqa: BLE001` plus a comment explaining the imperative reason; (3) add path to the `BLE001` step in `.github/workflows/ci.yml`; (4) `ruff check --select=BLE001 <new_path>` clean. |
| Tooling | `ruff` |

### Item 11 (per phase) — "Frontend consolidation phase N: <bucket>"

| Field | Value |
|---|---|
| Why deferred | Owner architecture call required; decision now recorded in ADR-0013 (Jinja2). |
| Acceptance | Per [ADR-0013](adr/0013-jinja2-over-spa.md) §"Migration order": each phase moves the named bucket under `templates/<bucket>/`, extracts shared chrome to `_layout_*.html`, flips handlers to `templates.TemplateResponse(...)`, deletes the root copy, and runs the existing route smoke tests for byte-identical-key-strings response bodies. The scaffolding PR (phase 1) also adds `tests/contracts/test_no_root_html.py`. |
| Tooling | [ADR-0013](adr/0013-jinja2-over-spa.md) |

### Item 12 (sub) — "Per-connector VCR/responses fixtures for test_base_contract.py"

| Field | Value |
|---|---|
| Why deferred | Multi-PR by connector. |
| Acceptance | (1) `tests/integration_connector/conftest.py` exposes `mocked_responses` fixture wrapping the `responses` library; (2) at least one connector class added to `UNIFIED_CONTRACT_CONNECTORS` with a recorded fixture; (3) the contract test exercises envelope shape, timeout, and 429 back-off against the recorded fixture; (4) per-connector PRs follow the same template. |
| Tooling | `responses` library |

### Item 13 (final) — "Item 13 (final): Delete src/graphql_api_layer.py per ADR-0008"

| Field | Value |
|---|---|
| Why deferred | ADR-0008 calendar gate: 90 days from 2026-04-22, i.e. **eligible 2026-07-21** OR earlier on a major version bump. |
| Acceptance | (1) `python scripts/check_adr_0008_eligibility.py` exits 1; (2) `git rm src/graphql_api_layer.py tests/integration_connector/test_graphql_api_layer.py tests/contracts/test_graphql_layer_quarantine.py`; (3) Roadmap Item 13 → ✅; (4) PR description cites ADR-0008. |
| Tooling | `scripts/check_adr_0008_eligibility.py` |

### Item 14 (sub) — "Add /api/v1/... versioning prefix; superseded routes return 308"

| Field | Value |
|---|---|
| Why deferred | Route-shape change with client impact. |
| Acceptance | (1) New routers extracted via Item 1 sit under `/api/v1/`; (2) legacy `/api/<x>` paths return `308 Permanent Redirect` to their `/api/v1/<x>` equivalent; (3) `docs/openapi.json` regenerated; (4) versioning policy documented in `src/routers/__init__.py`. |
| Tooling | `scripts/export_openapi.py` |

### Item 15 (promotion) — "Item 15 (promotion): Promote benchmark-regression to blocking"

| Field | Value |
|---|---|
| Why deferred | Calendar gate: ≥14 days of CI soak data required to characterise runner variance. |
| Acceptance | (1) `python scripts/check_benchmark_soak.py` exits 1; (2) flip `continue-on-error: true` → `false` on the `benchmark-regression:` job in `.github/workflows/ci.yml`; (3) Roadmap Item 15 row drops the "Currently advisory" caveat; (4) if the soak surfaced legitimate flakiness, the threshold is adjusted *first* and the soak clock restarted. |
| Tooling | `scripts/check_benchmark_soak.py` |

### Item 20 follow-up — "Wire ModuleLoader into app.py; remove src/runtime/_deps.py try/except blocks"

| Field | Value |
|---|---|
| Why deferred | `app.py` is 15 859 lines and `_deps.py` has 82 try/except guards; this is multi-PR by definition. The contract is already pinned by `tests/test_runtime_module_loader.py` (13 tests). |
| Acceptance | Per slice: (1) move N optional imports from `_deps.py` into `ModuleLoader.register(...)` calls; (2) replace the corresponding `try/except ImportError` guards with `RUNTIME_MODULE_LOADER.get(...)` accessors; (3) `/api/health` and `/api/modules` reflect the change; (4) a critical-vs-optional classification is captured per module so optional failures degrade gracefully but critical failures abort startup (no silent failure). |
| Tooling | `src/runtime/module_loader.py`, `tests/test_runtime_module_loader.py` |

## How to use this file

1. Pick the top-most row whose tooling reports "eligible" or whose owner is
   ready to start.
2. Open the named PR with the verbatim title.
3. Satisfy every checkbox in *Acceptance criteria*.
4. Delete the row from this file in the same PR.

When all rows are deleted, the Class S Roadmap is closed.
