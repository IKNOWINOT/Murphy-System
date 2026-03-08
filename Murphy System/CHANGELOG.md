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
- **feat:** `src/voice_command_interface.py` — Voice Command Interface (VCI-001): speech-to-text adapter and command parser for the Murphy terminal; AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats dataclass models, AudioFormat/CommandCategory/ParseStatus/STTProviderKind enums, VoiceCommandInterface engine with pluggable STT provider (built-in keyword recogniser for testing), 12 default command patterns, regex + alias matching, argument extraction, session lifecycle management, command history with category filtering, aggregate statistics, custom pattern registration/removal, Flask blueprint with 14 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_voice_command_interface.py` — 88 tests covering dataclass models (AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats), enums (AudioFormat/CommandCategory/ParseStatus/STTProviderKind), STT recognition (simple/empty/whitespace/chunk counting), command parsing (12 built-in commands + alias matching + args extraction + confidence + empty/unrecognised), end-to-end process_voice pipeline (basic/command key/with session), session management (start/end/end nonexistent/list active/list all), pattern management (register/custom match/remove/remove nonexistent/enum category), history and stats (record/filter by category/limit/clear/total/recognised/unrecognised/avg confidence), Wingman validation (pass/empty storyline/empty actuals/length mismatch/value mismatch), Sandbox gating (pass/missing keys/empty text/empty session), thread safety (200 concurrent parses/80 concurrent sessions), Flask API (14 endpoints: recognise/recognise missing/parse/process/sessions CRUD/patterns CRUD/history/clear/stats/health), custom STT provider (uppercase/confidence), edge cases (very long input/special chars/unicode/case insensitive/max history boundary/no session)
- **feat:** `src/blockchain_audit_trail.py` — Blockchain Audit Trail (BAT-001): file-based blockchain-inspired tamper-evident audit log; AuditEntry/Block/ChainVerification/ChainStats dataclass models, EntryType/BlockStatus/ChainIntegrity enums, BlockchainAuditTrail with entry recording (6 types), automatic + manual block sealing, SHA-256 hash chaining, full chain verification, search/export/stats, Flask blueprint with 12 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_blockchain_audit_trail.py` — 58 tests covering core engine (record/auto-seal/manual seal/hash linking/chain verification/tamper detection/search/stats/export/capacity eviction), thread safety (concurrent recording/verify), Wingman validation (pass/empty/mismatch), Sandbox gating (valid/missing/empty/invalid), Flask API (health/record/missing field/invalid type/seal/seal empty/list/get/get 404/by-index/verify/search/export/stats), edge cases (empty chain/all entry types/serialisation/large payload/genesis hash)
- **feat:** `src/ml_model_registry.py` — Machine Learning Model Registry (MLR-001): version, deploy, rollback, A/B test ML models; ModelStatus/ModelFramework/DeploymentTarget/VersionStatus enums, ModelVersion/Model/DeploymentRecord/ABTestConfig dataclass models, MLModelRegistry with model CRUD (register/get/list with status+framework+owner+tag filters/update/delete), version management (add/get/list/promote with automatic demotion/rollback), deployment lifecycle (deploy/complete/fail/rollback, filter by model+status), A/B testing (create/start/complete/route with configurable traffic split), aggregate statistics, Flask blueprint with 22 REST endpoints (/api/mlr/models CRUD, /api/mlr/models/{id}/versions CRUD + promote/rollback, /api/mlr/deployments CRUD + complete/fail/rollback, /api/mlr/ab-tests CRUD + start/complete/route, /api/mlr/stats, /api/mlr/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_ml_model_registry.py` — 90 tests covering enums (4 enum classes), dataclass serialisation (ModelVersion/Model/DeploymentRecord/ABTestConfig), model CRUD (register/get/get nonexistent/list/filter by framework+owner+tag+status/update/update nonexistent/delete/delete nonexistent), version management (add/add bad model/get/get nonexistent/list/filter by status/promote/promote demotes others/rollback/rollback nonexistent/metrics/parameters), deployment (deploy/deploy bad model/get/get nonexistent/list/filter by model+status/complete/fail/rollback/complete nonexistent/target value), A/B testing (create/create bad model/get/get nonexistent/start/complete/complete stores metrics/route/route not running/traffic split distribution/start nonexistent), stats (empty/populated), Wingman validation (valid/empty storyline/empty actuals/length mismatch), Sandbox gating (valid/missing key/empty model_name/bad framework), Flask API (health/register model/register missing fields/list models/get model/get model 404/delete model/add version/list versions/promote/rollback/deploy/list deployments/complete deployment/create A/B test/start A/B test/route A/B traffic/stats), thread safety (100 concurrent registrations/50 concurrent versions), edge cases (empty name/long description/empty metrics/multiple deployments same version/model capacity limit)
- **feat:** `src/geographic_load_balancer.py` — Geographic Load Balancing and Edge Deployment (GLB-001): Region/EdgeNode/RoutingPolicy/RoutingDecision/HealthCheckResult/DeploymentSpec dataclass models, GeographicLoadBalancer with 5 routing strategies (latency_based/geo_proximity/weighted_round_robin/failover/capacity_based), haversine distance calculation, region management with load metrics, edge node health tracking with consecutive-failure degradation (healthy→degraded→offline→recovery), deployment lifecycle (pending→deploying→active/failed/rolled_back) with advance/rollback, Flask blueprint with 20 REST endpoints (/api/glb/regions CRUD + load update, /api/glb/nodes CRUD + health, /api/glb/policies CRUD, /api/glb/route, /api/glb/deployments CRUD + advance/rollback, /api/glb/stats, /api/glb/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_geographic_load_balancer.py` — 65 tests covering region management (add/get/list/filter/update load/remove/tags), edge nodes (add/list/filter by region/get/remove/bad region), health checks (healthy/degraded/offline/recovery/bad node), routing policies (create/get/list), all 5 routing strategies (latency_based picks lowest ms, geo_proximity picks closest via haversine, weighted_round_robin returns valid, failover picks healthy, capacity_based picks least loaded), routing edge cases (bad policy/no healthy regions/same point), deployments (create/get/list/filter/advance/complete/rollback/bad regions/nonexistent), stats, Wingman validation (valid/empty storyline/empty actuals/length mismatch), Sandbox gating (valid/forbidden/missing keys/empty region_id), Flask API (health/add region/list/get/404/add node/route/create policy/stats/create deployment/missing fields/delete region), thread safety (100 concurrent region additions)
- **feat:** `src/data_pipeline_orchestrator.py` — Data Pipeline Orchestrator (DPO-001): ETL/ELT job management with PipelineStage/DataPipeline/PipelineRun/StageResult/DataQualityCheck/QualityCheckResult dataclass models, DataPipelineOrchestrator with pipeline CRUD (draft→active→paused→completed→failed→archived lifecycle), scheduled/manual/event-triggered execution, stage-by-stage advancement with dependency tracking, run management (trigger/cancel/list with filters), data quality checks (completeness/uniqueness/range/format/custom with severity levels), per-pipeline and global statistics, Flask blueprint with 15 REST endpoints (/api/pipelines CRUD + activate/pause/trigger/runs/stats, /api/runs get/cancel/stages/advance, /api/quality-checks CRUD + run, /api/pipelines/stats/global), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_data_pipeline_orchestrator.py` — 94 tests covering pipeline CRUD (create/get/list with status/owner/tag filters/update/delete), lifecycle (activate/pause/status transitions), runs (trigger/get/list with status filter/limit/cancel), stage advancement (first stage/all stages/error handling/records tracking), quality checks (add/list/run evaluation), statistics (per-pipeline/global), Flask API (15 endpoint tests), Wingman validation (pass/mismatch), Sandbox gating (allowed/forbidden), thread safety (concurrent create/trigger/advance), edge cases (empty name/no stages/long name/duplicate names/serialisation)
- **feat:** `src/capacity_planning_engine.py` — Automated Capacity Planning Engine (CPE-001): predict resource needs from historical usage patterns; ResourceType/AlertSeverity/ForecastMethod/PlanStatus enums, ResourceMetric/ForecastResult/CapacityAlert/ScalingRecommendation/CapacityPlan dataclass models, CapacityPlanningEngine with time-series ingestion (7 resource types), three forecasting algorithms (linear regression, exponential smoothing, moving average), time-to-threshold estimation, configurable warning/critical thresholds, alert generation with acknowledge workflow, scaling recommendations (scale_up/plan_scaling/scale_down), capacity plan generation, Flask blueprint with 13 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_capacity_planning_engine.py` — 62 tests covering enums, dataclass serialisation (utilisation property, zero-capacity edge case), metric ingestion (record/get/limit/list resources/cap), forecasting (linear/exponential/moving avg/insufficient data/confidence/nonexistent/time-to-threshold), plan generation (create/get/list/filter by status/archive/nonexistent), alerts (critical/warning/no alert for low usage/acknowledge/filter), recommendations (scale up/scale down), stats, Wingman validation (valid/no resources/insufficient data), Sandbox gating (valid/bad threshold), thread safety (concurrent record/forecast), Flask API (13 endpoint tests)
- **feat:** `src/ab_testing_framework.py` — A/B Testing Framework (ABT-001): split traffic between experiment variants, measure outcomes, auto-promote winners; ExperimentStatus/VariantType/MetricType/AllocationStrategy enums, Variant/MetricDefinition/ExperimentResult/Experiment/Assignment/MetricEvent dataclass models, ABTestingEngine with experiment lifecycle (draft→running→paused→completed→archived), random/deterministic/weighted allocation strategies, sticky assignments, metric recording, simplified Welch's t-test significance (stdlib only), auto-promote winner, confidence intervals, Flask blueprint with 12 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_ab_testing_framework.py` — 75 tests covering enums, dataclass serialisation, experiment CRUD, lifecycle transitions, variant assignment (random/deterministic/weighted/sticky), metric recording, statistics (mean/std/CI/p-value), significance detection, auto-promote, traffic clamping, Wingman validation, Sandbox gating, experiment cap/eviction, thread safety (concurrent create/assign), Flask API (create/list/get/start/assign/metrics/results/delete/404/400)
- **feat:** `src/natural_language_query.py` — Natural Language Query Interface (NLQ-001): ask questions about system state in English; QueryIntent/EntityType/QueryStatus enums, Entity/ParsedQuery/QueryResult/DataSourceRegistration/QueryHistoryEntry dataclass models, NLQueryEngine with rule-based intent detection (9 intents), entity extraction (6 types), pluggable data-source handlers with priority dispatch, synonym expansion, bounded history, stats aggregation, Flask blueprint with 11 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_natural_language_query.py` — 72 tests covering enums, dataclass serialisation, data source CRUD (register/unregister/get/list/enable/disable/cap), intent detection (status/count/list/detail/compare/trend/search/help/unknown), entity extraction (module/metric/time_range/status_filter/number), query execution (with source/no source/help/unknown/error handler/elapsed/confidence), synonyms, history (recorded/filtered/limited/cleared), stats, Wingman validation, Sandbox gating, thread safety (concurrent queries/register), Flask API (query/parse/sources CRUD/history/stats/404/400), source priority ordering, multi-source data combination
- **feat:** `src/audit_logging_system.py` — Immutable Audit Logging System (AUD-001): append-only audit log with AuditEntry/AuditQuery/RetentionPolicy dataclass models, AuditLogger with SHA-256 hash-chain integrity verification (tamper detection), 11 audit action types (create/read/update/delete/login/logout/configure/execute/approve/deny/export), 7 category classifications (api_call/admin_action/config_change/security_event/data_access/system_event/user_action), convenience loggers (log_api_call/log_admin_action/log_config_change/log_security_event), structured query engine with multi-field filtering (action/category/severity/actor/resource/success/time range), retention policies with configurable max_entries and category scoping, JSON export, PII redaction (IP addresses, user agents), pluggable external sink callback, Flask blueprint with 13 REST endpoints (/api/audit/entries CRUD + query, /api/audit/verify, /api/audit/export, /api/audit/count, /api/audit/policies CRUD, /api/audit/retention/apply, /api/audit/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_audit_logging_system.py` — 52 tests covering all enum values (AuditAction/AuditSeverity/AuditCategory), dataclass defaults and serialisation (IP redaction, user agent truncation, hash computation, policy to_dict), core logging (entry creation, hash chain linking), chain integrity (valid chain, tampered detection, empty chain), convenience loggers (API call success/failure, admin action severity, config change, security event), query (by action/category/actor/success, limit, get entry, missing entry, count by category), retention policies (add/delete/apply trimming), export (valid JSON), sink callback (receive entries, failure handling), statistics structure, thread safety (10 concurrent logs, concurrent chain validity), Flask API (15 endpoint tests: entries CRUD + filters, verify, export, count + category filter, policies CRUD, retention apply, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/notification_system.py` — Multi-channel Notification System (NTF-001): programmatic notification dispatch with ChannelConfig/NotificationTemplate/ChannelDelivery/Notification dataclass models, NotificationManager with channel registry (email/Slack/Discord/Teams/webhook/custom), template engine with {{variable}} substitution, priority-based routing with min_priority filtering, per-channel rate limiting (sliding window), quiet-hours suppression (critical bypasses), pluggable send callback for testability, sensitive config key redaction (url/key/secret/token), Flask blueprint with 15 REST endpoints (/api/notifications/channels CRUD + enable/disable, /api/notifications/templates CRUD, /api/notifications/send, /api/notifications/send-template, /api/notifications/notifications list + get, /api/notifications/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_notification_system.py` — 56 tests covering all enum values (ChannelType/NotificationPriority/NotificationStatus/DeliveryResult), dataclass defaults and serialisation (channel secret redaction, template rendering, delivery/notification to_dict), channel CRUD (register/list/filter/update/delete/enable/disable/nonexistent), template CRUD (register/list/delete), notification send (all channels, specific channels, disabled skipped, template send, template not found, failure callback, exception handling, priority filtering, rate limiting, no channels), query helpers (get notification, list with filters, event_type filter, stats structure, failure stats), thread safety (10 concurrent registrations, 5 concurrent sends), Flask API (17 endpoint tests: channels CRUD + enable/disable, templates CRUD, send, send-template, notifications list + get, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/webhook_dispatcher.py` — Outbound Webhook Dispatcher (WHK-001): programmatic outbound webhook dispatch system with WebhookSubscription/WebhookEvent/DeliveryAttempt/DeliveryRecord dataclass models, WebhookDispatcher with subscription registry (create/get/list/update/delete/enable/disable), event matching with wildcard `*` support, HMAC-SHA256 payload signing with `X-Murphy-Signature` header, delivery with exponential-backoff retry (jitter, configurable max_retries/base_delay/max_delay), pluggable delivery callback for testability, delivery history tracking, webhook secret redaction in serialisation, Flask blueprint with 13 REST endpoints (/api/webhooks/subscriptions CRUD + enable/disable, /api/webhooks/events dispatch + log, /api/webhooks/deliveries list + get + retry, /api/webhooks/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_webhook_dispatcher.py` — 59 tests covering all enum values (WebhookStatus/DeliveryStatus/EventPriority), dataclass defaults and serialisation (subscription secret redaction, event to_dict, attempt/record to_dict), subscription CRUD (register/list/filter/update/delete/enable/disable/nonexistent), dispatch (wildcard matching, specific event filter, disabled skipped, multi-subscriber fan-out, no-match empty, event logged), failed delivery (callback 500, exception handling, retry logic, retry non-failed, retry unknown), HMAC-SHA256 signing (signature match, header present with secret, absent without), exponential backoff (increasing delays, max cap), query helpers (stats structure, failure stats, record filter, get by ID, event log limit), thread safety (10 concurrent registrations, 5 concurrent dispatches), Flask API (15 endpoint tests: subscriptions CRUD + enable/disable, events dispatch + log, deliveries list + get + retry, stats, 400/404 validation), Wingman gate, Sandbox gate
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
