# Changelog

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1 (Business Source License 1.1)
-->

All notable changes to Murphy System are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## [Unreleased]

### Added
- **feat:** `src/oauth_oidc_provider.py` — OAuth2/OIDC Authentication Provider (OAU-001): programmatic OAuth2/OpenID Connect provider integration with ProviderConfig/AuthorizationRequest/TokenSet/OIDCDiscovery/UserInfo/OAuthSession dataclass models, OAuthManager with provider registry (Google/GitHub/Microsoft/Custom), authorization code flow with PKCE S256 challenge, token exchange/refresh/revoke lifecycle, session management (create/touch/revoke), OIDC discovery caching, role mapping, client_secret/token/email redaction in serialisation, Flask blueprint with 18 REST endpoints (/api/oauth/providers CRUD, /api/oauth/authorize, /api/oauth/callback, /api/oauth/tokens refresh+revoke, /api/oauth/sessions CRUD+revoke, /api/oauth/discovery, /api/oauth/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_oauth_oidc_provider.py` — 43 tests covering enum values (OAuthProvider/GrantType/TokenStatus/SessionStatus), dataclass creation and serialisation (ProviderConfig secret redaction, TokenSet token redaction, OAuthSession email redaction, PKCE code challenge), provider CRUD (register/list/remove/enable/disable), authorization flow (start/exchange/invalid state), token lifecycle (refresh/revoke/list with filter), session management (create/revoke/touch/list with status filter, revoked-token rejection), OIDC discovery cache, stats, thread safety under 10 concurrent threads, Flask API endpoints (providers CRUD, authorize, callback, sessions, tokens refresh+revoke, discovery, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/kubernetes_deployment.py` — Kubernetes Deployment Manager (K8S-001): K8sDeployment/K8sService/K8sHPA/K8sConfigMap/K8sSecret/K8sIngress/K8sNamespace/HelmChart dataclass models, KubernetesManager with resource CRUD for all K8s kinds, YAML manifest generation, replica scaling, secrets redaction, Flask blueprint with 25+ REST endpoints, thread-safe lock-protected state, Wingman + Sandbox gating
- **test:** `tests/test_kubernetes_deployment.py` — 57 tests covering all enum values, dataclass creation/serialisation, deployment/service/HPA/ConfigMap/secret/ingress/namespace/Helm chart CRUD, YAML generation, replica scaling, Flask API endpoints, thread safety, Wingman gate, Sandbox gate
- **feat:** `src/docker_containerization.py` — Docker Containerization Manager (DCK-001): container definitions, lifecycle, Dockerfile/Compose generation, image registry, health checks, Flask blueprint with 17 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_docker_containerization.py` — 38 tests covering all enums, dataclass models, container lifecycle, Dockerfile generation, Compose YAML, image registry, Flask API, thread safety, Wingman + Sandbox gates
- **feat:** `src/ci_cd_pipeline_manager.py` — CI/CD Pipeline Manager (CICD-001): programmatic CI/CD pipeline lifecycle management with PipelineDefinition/PipelineRun/StageResult/BuildArtifact dataclass models, PipelineManager with full pipeline CRUD (create/update/delete/enable/disable), run triggering with 6 trigger types (push/pull_request/schedule/manual/webhook/tag), 8-stage pipeline progression (source/build/test/security_scan/package/deploy_staging/integration_test/deploy_production), manual approval gates, artifact registry with SHA-256 checksums, pipeline statistics (success rate, avg duration, recent failures), retry logic, timeout enforcement, Flask blueprint with 17 REST endpoints (/api/cicd/pipelines CRUD, /api/cicd/runs lifecycle, /api/cicd/artifacts, /api/cicd/pipelines/<id>/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_ci_cd_pipeline_manager.py` — 47 tests covering pipeline CRUD (create/get/list/update/delete/enable/disable), run triggering (enabled/disabled pipelines), stage advancement, manual approval gates (approve/reject non-gated), run cancellation (active/finished), artifact registration and retrieval, pipeline statistics calculation, thread safety under 10 concurrent triggers, retry logic, timeout enforcement, Flask API endpoints (create pipeline/trigger run/list runs with filters/artifact endpoints/error responses), Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/multi_tenant_workspace.py` — Multi-tenant Workspace Isolation (MTW-001): full workspace isolation with TenantConfig/TenantMember/WorkspaceData/AuditEntry dataclass models, WorkspaceManager with tenant lifecycle (create/suspend/activate/archive/delete), per-tenant RBAC with 5 roles (owner/admin/member/viewer/service_account) and 6 permission actions (read/write/admin/delete/manage_members/view_audit), data namespace isolation ensuring no cross-tenant access, config isolation, bounded audit trail, resource quotas (storage/API calls/members), Flask blueprint with 17 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_multi_tenant_workspace.py` — 35 tests covering all enum values, dataclass creation/serialisation, workspace CRUD lifecycle, member management, RBAC permission matrix (owner/viewer/member), cross-tenant data isolation, data store/get/delete, config isolation, audit log generation, Flask API endpoints (create/list/get/404), thread safety under 10 concurrent threads, Wingman gate, Sandbox gate
- **feat:** `src/graphql_api_layer.py` — GraphQL API Layer (GQL-001): lightweight stdlib-only GraphQL execution engine wrapping Murphy REST endpoints; ObjectTypeDef/InputTypeDef/EnumTypeDef schema definitions, SchemaRegistry with resolver registry, QueryParser supporting shorthand queries/named queries/mutations/aliases/arguments with string/int/float/bool/null literals, AST Executor with introspection (__schema/__type), Flask blueprint with POST /graphql + GET /graphql/schema + /graphql/types + /graphql/health, pre-built Murphy types (HealthCheck/Metric/Module) and queries (health/modules/echo), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_graphql_api_layer.py` — 45 tests covering data models (GraphQLType/ScalarKind/FieldDef/ObjectTypeDef/InputTypeDef/EnumTypeDef), SchemaRegistry type/enum/input/query/mutation registration and lookup, QueryParser shorthand/named/mutation/arguments/nested/alias/bool-null/float parsing, Executor simple/args/nested/list/error/introspection queries, Flask API endpoints (POST /graphql, GET /graphql/schema, /graphql/types, /graphql/health), input validation (missing/empty query), thread safety under concurrent registration, Wingman gate, Sandbox gate, Murphy type/query helpers, user-agent operator workflow
- **feat:** `src/prometheus_metrics_exporter.py` — Prometheus/OpenTelemetry Metrics Exporter (PME-001): Counter/Gauge/Histogram/Summary metric types with LabelSet dimensions, CollectorRegistry, PrometheusRenderer (text exposition format), JsonRenderer, built-in Murphy system metrics helper, Flask blueprint with /metrics + /api/metrics/json + /api/metrics/families + /api/metrics/register + /api/metrics/health endpoints, thread-safe lock-protected mutations, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_prometheus_metrics_exporter.py` — 35 tests covering data models, counter inc/negative rejection, gauge inc/dec/set, histogram observe/buckets/sum/count/+Inf, summary quantiles, registry register/unregister/clear/idempotent/collect_all, Prometheus text rendering, JSON rendering, built-in metrics, Flask API endpoints, input validation, thread safety, Wingman gate, Sandbox gate, user-agent operator workflow
- **feat:** `src/websocket_event_server.py` — Real-time WebSocket Event Streaming Server (WES-001): EventBus pub-sub with channel isolation, subscriber lifecycle with heartbeat TTL, EventFilter (channel/type/severity), ConnectionManager with auto-expire, Flask REST + SSE endpoints, user-agent workflow support for non-technical operators, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_websocket_event_server.py` — 34 tests covering data models, event filters, channel history, connection management, EventBus pub/sub, Flask API endpoints (subscribe/publish/poll/history/channels/stats/unsubscribe), input validation, thread safety, Wingman gate, Sandbox gate, user-agent lifecycle workflows
- **feat:** `src/digital_twin_engine.py` — Digital Twin Simulation Engine (DTE-001): model physical/logical systems, z-score anomaly detection, failure prediction, what-if scenario simulation, TwinRegistry fleet management, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/federated_learning_coordinator.py` — Federated Learning Coordinator (FLC-001): train models across distributed Murphy instances without sharing raw data; FedAvg/Median aggregation, differential-privacy noise injection, gradient clipping, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/backup_disaster_recovery.py` — Automated Backup & Disaster Recovery System (BDR-001): BackupManager with create/list/restore/delete/expire/verify, LocalStorageBackend, SHA-256 integrity checks, bundle serialisation, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/startup_validator.py` — Boot-time startup validation: env vars, file existence, port availability, dependency importability (SV-001)
- **test:** `tests/test_digital_twin_engine.py` — 28 tests covering data models, anomaly detector, twin lifecycle, failure prediction, scenario simulation, fleet registry, thread safety, Wingman gate, Sandbox gate
- **test:** `tests/test_federated_learning_coordinator.py` — 29 tests covering data models, privacy guard, FedAvg/Median aggregation, coordinator lifecycle, edge cases, thread safety, Wingman gate, Sandbox gate
- **test:** `tests/test_backup_disaster_recovery.py` — 33 tests covering data models, storage CRUD, bundle round-trip, backup lifecycle, restore with checksum validation, retention expiry, thread safety, Wingman gate, Sandbox gate
- **test:** `tests/test_performance_reliability.py` — 34 tests for graceful shutdown, health checks, startup validation, circuit breakers, connection pooling

### Changed
- **refactor:** Converted 12 `raise NotImplementedError` stubs in 6 abstract base classes to proper `abc.ABC` + `@abstractmethod` patterns:
  - `command_system.py` — `CommandModule.execute()`
  - `crypto_exchange_connector.py` — `ExchangeConnector._place_order()`, `_fetch_ticker()`, `_fetch_balances()`, `_probe()`
  - `crypto_wallet_manager.py` — `BaseWallet._do_sync()`
  - `domain_swarms.py` — `DomainSwarmGenerator.generate_candidates()`, `generate_gates()`
  - `learning_engine/model_architecture.py` — `ShadowAgentModel.train()`, `predict()`
  - `murphy_code_healer.py` — Replaced `NotImplementedError` in code-generation templates with `RuntimeError`
- **legal:** Priority 0 — License compliance audit, PII redaction, dependency cleanup (pylint→ruff, Apache headers→BSL-1.1, THIRD_PARTY_LICENSES.md, PRIVACY.md)

### Added
- **test:** `tests/test_code_quality.py` — 10-check automated code-quality gate (CQ-010 through CQ-061): no bare excepts, no TODOs, no stub/placeholder markers, file-size limits with legacy allowlist, docstring coverage baseline, syntax validation, trailing-whitespace check

### Fixed
- **refactor:** Replaced 19 `# Placeholder` / `# Stub` comments across 13 src/ files with descriptive alternatives
- **refactor:** Added missing docstrings to 6 public functions in strict security modules (`fastapi_security.py`, `flask_security.py`, `signup_gateway.py`)
- **refactor:** Removed excess trailing newlines from `src/control_theory/observation_model.py`

---

## [1.0.0] — 2026-03-07

### Added

**Core Runtime**
- FastAPI-based orchestration server (`murphy_system_1.0_runtime.py`) serving on port 8000
- 620+ registered modules across the full system
- Multi-stage production Dockerfile with non-root `murphy` user
- Docker Compose stack: Murphy API, PostgreSQL 16, Redis 7, Prometheus, Grafana

**API**
- `GET /api/health` — liveness probe (no auth required)
- `GET /api/status` — system status dashboard
- `POST /api/execute` — task execution through the full orchestration pipeline
- `GET /api/llm/configure` — read LLM provider configuration
- `POST /api/llm/configure` — hot-reload LLM provider (no restart required)
- `POST /api/confidence/score` — GDH confidence scoring with 5-dimensional uncertainty
- `GET /api/orchestrator/status` — pipeline queue and latency metrics
- `GET /api/orchestrator/tasks` — list recent tasks with status and audit IDs
- `GET /api/modules` — module registry status
- `GET /api/modules/{name}/status` — per-module status
- `POST /api/feedback` — human feedback signals for confidence recalibration
- `POST /api/system/build` — build a complete expert/gate/constraint system
- Full Pydantic v2 request/response validation
- HTTP 429 rate-limit responses with `Retry-After` header

**Security**
- `src/fastapi_security.py` — centralized security middleware (resolves SEC-001, SEC-002, SEC-004)
- API key authentication via `Authorization: Bearer` and `X-API-Key` headers
- CORS origin allowlist (replaces wildcard `*`); configurable via `MURPHY_CORS_ORIGINS`
- Token-bucket rate limiting per IP and per API key
- Input sanitization on all request bodies
- Security response headers: `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`
- Development mode (`MURPHY_ENV=development`) bypasses auth for local use

**Orchestration Engines**
- AUAR 7-layer routing pipeline with ML optimization
- AionMind Kernel: context engine, reasoning engine, orchestration engine
- Unified Control Protocol: 10-engine pipeline, 7 execution states, rollback support
- Session Context Manager: per-session locking, TTL expiry, RM0–RM6 resource tracking
- Concept Graph Engine: 7 node/edge types, graph health scoring, GCS metric
- Execution engines: task executor, workflow orchestrator, sandbox manager

**Confidence and Governance**
- Unified Confidence Engine with Bayesian scoring and Murphy Index
- GDH (Generative / Discriminative / Hybrid) confidence breakdown
- 5-dimensional uncertainty quantification (epistemic, aleatoric, model, data, domain)
- HITL (Human-in-the-Loop) governance gates
- Governance kernel with compliance scheduling
- Artifact graph for full execution provenance

**LLM Integration**
- Groq provider (recommended; free tier available via `GROQ_API_KEYS` pool for rotation)
- OpenAI provider (GPT-4o and above)
- Anthropic provider (Claude 3.5 Sonnet and above)
- Local / offline mode (deterministic Aristotle + Wulfrum engines only)
- Hot-reload LLM provider without server restart

**Setup and Operations**
- `setup_and_start.sh` / `setup_and_start.bat` — guided setup and startup scripts
- `.env.example` — complete environment variable reference with inline documentation
- `requirements_murphy_1.0.txt` — pinned dependency manifest
- Prometheus metrics at `/metrics`: request counters, latency histograms, queue depth, LLM call counters
- Grafana dashboards (included in Docker Compose stack)

**Testing**
- 250+ test files across unit, integration, and end-to-end categories
- CI via GitHub Actions (`ci.yml`): lint, syntax check, full pytest suite
- Test command: `python -m pytest --timeout=60 -v --tb=short` (run from `Murphy System/`)

**Documentation**
- `docs/API_REFERENCE.md` — full endpoint reference
- `documentation/api/` — authentication guide, endpoint reference, examples
- `documentation/deployment/` — deployment guide, configuration, scaling, maintenance
- `documentation/testing/` — testing guide
- `ARCHITECTURE_MAP.md`, `DEPENDENCY_GRAPH.md`, `MURPHY_SYSTEM_1.0_SPECIFICATION.md`
- `USER_MANUAL.md`, `MURPHY_1.0_QUICK_START.md`

**Regulatory Alignment** *(see STATUS.md for full detail)*
- GDPR — data minimization, consent tracking, right-to-erasure support
- SOC 2 — audit logging, access controls, encryption at rest
- HIPAA — role-based access, PHI handling controls, audit trails
- PCI DSS — payment data isolation, encryption, tokenization support
- ISO 27001 — information security management controls

### Known Gaps (tracked for future releases)

| ID | Description |
|----|-------------|
| G-004 | Full ML feedback loop not yet wired to routing weights |
| G-005 | Dashboard UI incomplete |
| G-006 | Formal third-party penetration test pending |
| G-008 | Kubernetes manifests not yet hardened for production |

---

[Unreleased]: https://github.com/Murphy-System/Murphy-System/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Murphy-System/Murphy-System/releases/tag/v1.0.0

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
