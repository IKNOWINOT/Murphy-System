# Murphy System — Module Registry

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

*Last updated: 2026-03-14*

---

## Overview

This registry provides a comprehensive index of all major modules in the
Murphy System organised by subsystem. It is the authoritative reference
for understanding what each module does, where it lives, and its current
operational status.

**Counts (as of 2026-03-14):** 656+ source modules across 57 packages in `src/`.

Legend:
- ✅ **Operational** — module is active and tested
- 🔄 **In Progress** — being added in issue #136 or an active PR
- 📋 **Planned** — on the roadmap; not yet committed

---

## Core Runtime

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `murphy_system_1.0_runtime.py` | `` | Thin entry-point; re-exports all public symbols — implementation lives in `src/runtime/` (INC-13 closed) | ✅ | fastapi, uvicorn, pydantic |
| `config.py` | `src/config.py` | Pydantic `BaseSettings`; loads `.env`, provides typed config | ✅ | pydantic-settings |
| `command_system.py` | `src/command_system.py` | CLI command dispatcher | ✅ | — |
| `command_parser.py` | `src/command_parser.py` | Natural-language command parser | ✅ | — |
| `capability_map.py` | `src/capability_map.py` | Maps task types to available module capabilities | ✅ | — |
| `automation_scheduler.py` | `src/automation_scheduler.py` | Task scheduling and periodic automation triggers | ✅ | apscheduler |
| `automation_mode_controller.py` | `src/automation_mode_controller.py` | Controls automation level (manual / semi / full) | ✅ | — |
| `domain_engine.py` | `src/domain_engine.py` | Domain-aware task routing | ✅ | — |
| `constraint_system.py` | `src/constraint_system.py` | Hard and soft constraint enforcement | ✅ | — |

---

## Self-Healing & Improvement

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `self_fix_loop.py` | `src/self_fix_loop.py` | Iterative diagnose-plan-implement-test-verify loop | ✅ | — |
| `causality_sandbox.py` | `src/causality_sandbox.py` | Causal simulation engine; what-if scenario cycles | ✅ | — |
| `murphy_code_healer.py` | `src/murphy_code_healer.py` | AST-level code repair and patch application | ✅ | ast |
| `bug_pattern_detector.py` | `src/bug_pattern_detector.py` | Detects recurring bug patterns in source code | ✅ | — |
| `code_repair_engine.py` | `src/code_repair_engine.py` | Generates and applies code repair patches | ✅ | — |
| `autonomous_repair_system.py` | `src/autonomous_repair_system.py` | Fully autonomous repair pipeline | ✅ | — |
| `chaos_resilience_loop.py` | `src/chaos_resilience_loop.py` | Chaos injection and resilience validation | ✅ | — |
| `architecture_evolution.py` | `src/architecture_evolution.py` | Tracks and guides architectural evolution | ✅ | — |

---

## Wingman Protocol

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `wingman_protocol.py` | `src/wingman_protocol.py` | Executor/validator pairing; runbooks; full validation history | ✅ | threading |

See [WINGMAN_PROTOCOL.md](WINGMAN_PROTOCOL.md) for full architecture documentation.

---

## Orchestrators

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `campaign_orchestrator.py` | `src/campaign_orchestrator.py` | Campaign lifecycle orchestration | ✅ | — |
| `safety_orchestrator.py` | `src/safety_orchestrator.py` | Safety checks, compliance dashboard | 📋 Planned | — |
| `efficiency_orchestrator.py` | `src/efficiency_orchestrator.py` | Efficiency scoring, optimisation recommendations | 📋 Planned | — |
| `supply_orchestrator.py` | `src/supply_orchestrator.py` | Inventory, usage, receipts, reorder management | 📋 Planned | — |

---

## Engines

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `hitl_graduation_engine.py` | `src/hitl_graduation_engine.py` | Human-to-automation handoff pipeline — register, evaluate, graduate, rollback | ✅ | — |
| `functionality_heatmap.py` | `src/functionality_heatmap.py` | Activity recording, cold/hot-spot analysis, coverage dashboard | 📋 Planned | — |
| `agentic_onboarding_engine.py` | `src/agentic_onboarding_engine.py` | Autonomous onboarding with adaptive path selection | ✅ Operational | — |
| `production_assistant.py` | `src/production_assistant.py` | Production Assistant (PROD-001): proposal validation at 99% confidence, HITL gate requirements (certifications, licensing, experience, discipline accountability), work-order deliverable matching, lifecycle management (created→in_review→approved→in_progress→delivered→verified), regulatory completeness checks; integrates ProductionOutputCalibrator, SafetyGate, ComplianceEngine | ✅ | `production_output_calibrator`, `thread_safe_operations`, `strategic.murphy_confidence.gates` |
| `code_generation_gateway.py` | `src/code_generation_gateway.py` | LLM-powered code generation gateway | ✅ | — |
| `auto_documentation_engine.py` | `src/auto_documentation_engine.py` | Automated docstring and README generation | ✅ | — |
| `domain_gate_generator.py` | `src/domain_gate_generator.py` | Dynamic gate generation per domain | ✅ | — |
| `digital_asset_generator.py` | `src/digital_asset_generator.py` | Procedural digital asset generation | ✅ | Pillow |
| `content_pipeline_engine.py` | `src/content_pipeline_engine.py` | Multi-stage content processing pipeline | ✅ | — |
| `concept_graph_engine.py` | `src/concept_graph_engine.py` | Concept graph construction and traversal | ✅ | — |
| `adaptive_campaign_engine.py` | `src/adaptive_campaign_engine.py` | Adaptive campaign strategy engine | ✅ | — |
| `outreach_campaign_planner.py` | `src/outreach_campaign_planner.py` | Campaign Planner (CAMP-001): self-advertising outreach with META_PROOF self-referential messaging, multi-channel cadence (email→LinkedIn→SMS), CampaignPlan/CadenceStep/AudienceSegment models, business-type personalisation for 12 verticals, 3-day free-trial offers, shadow-agent deployment, suppression list management, audit trail; enforces 30-day/7-day cooldowns, permanent DNC, CAN-SPAM/TCPA/GDPR/CCPA/CASL via ContactComplianceGovernor | ✅ | `contact_compliance_governor`, `outreach_compliance_integration`, `self_selling_engine`, `thread_safe_operations` |
| `competitive_intelligence_engine.py` | `src/competitive_intelligence_engine.py` | Market and competitor analysis engine | ✅ | — |
| `alert_rules_engine.py` | `src/alert_rules_engine.py` | Configurable alert rules and notification routing | ✅ | — |

---

## Bridges & Adapters

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `golden_path_bridge.py` | `src/golden_path_bridge.py` | Captures and replays successful execution paths | ✅ | — |
| `telemetry_adapter.py` | `src/telemetry_adapter.py` | Telemetry data collection, analysis, and learning | ✅ | — |
| `api_gateway_adapter.py` | `src/api_gateway_adapter.py` | Normalises inbound requests across API gateways | ✅ | — |
| `compliance_automation_bridge.py` | `src/compliance_automation_bridge.py` | Bridges compliance framework to automation layer | ✅ | — |
| `compliance_orchestration_bridge.py` | `src/compliance_orchestration_bridge.py` | Orchestrates cross-framework compliance checks | ✅ | — |
| `automation_loop_connector.py` | `src/automation_loop_connector.py` | Connects automation loop to external event sources | ✅ | — |
| `automation_integration_hub.py` | `src/automation_integration_hub.py` | Central hub for automation integration wiring | ✅ | — |
| `cross_platform_data_sync.py` | `src/cross_platform_data_sync.py` | Cross-platform data synchronisation | ✅ | — |
| `delivery_adapters.py` | `src/delivery_adapters.py` | Channel delivery adapters (email, chat, voice, doc) | ✅ | — |

---

## Security

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `secure_key_manager.py` | `src/secure_key_manager.py` | Fernet-encrypted API key storage | ✅ | cryptography |
| `flask_security.py` | `src/flask_security.py` | Flask request-level security middleware | ✅ | flask |
| `fastapi_security.py` | `src/fastapi_security.py` | FastAPI request-level security middleware | ✅ | fastapi |
| `credential_profile_system.py` | `src/credential_profile_system.py` | HITL credential profiles and storage | ✅ | — |
| `authority_gate.py` | `src/authority_gate.py` | Authority and permission gate | ✅ | — |
| `compliance_engine.py` | `src/compliance_engine.py` | Compliance engine (GDPR, SOC 2, HIPAA, PCI DSS, ISO 27001) | ✅ | — |
| `compliance_region_validator.py` | `src/compliance_region_validator.py` | Region-specific compliance validation | ✅ | — |
| `automation_rbac_controller.py` | `src/automation_rbac_controller.py` | Role-based access control for automation actions | ✅ | — |
| `contractual_audit.py` | `src/contractual_audit.py` | Contractual obligation audit trail | ✅ | — |

---

## Confidence & Gate System

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `confidence_engine/` | `src/confidence_engine/` | Confidence scoring engine and API server | ✅ | fastapi |
| `gate_synthesis/` | `src/gate_synthesis/` | Gate synthesis — evaluates all gates before task release | ✅ | — |
| `deterministic_routing_engine.py` | `src/deterministic_routing_engine.py` | Deterministic, rule-based task routing | ✅ | — |
| `deterministic_compute.py` | `src/deterministic_compute.py` | Deterministic compute path (no LLM) | ✅ | — |

---

## LLM & Learning

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `learning_engine/` | `src/learning_engine/` | Feedback-loop learning engine | ✅ | — |
| `neuro_symbolic_models/` | `src/neuro_symbolic_models/` | Neuro-symbolic model implementations | ✅ | — |
| `concept_translation.py` | `src/concept_translation.py` | Cross-domain concept translation | ✅ | — |
| `domain_expert_system.py` | `src/domain_expert_system.py` | Domain expert knowledge base | ✅ | — |
| `domain_expert_integration.py` | `src/domain_expert_integration.py` | Integrates domain experts into routing | ✅ | — |
| `advanced_research.py` | `src/advanced_research.py` | Autonomous research and synthesis | ✅ | — |

---

## Analytics & Observability

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `analytics_dashboard.py` | `src/analytics_dashboard.py` | Real-time analytics dashboard | ✅ | — |
| `agent_monitor_dashboard.py` | `src/agent_monitor_dashboard.py` | Agent health and activity monitoring | ✅ | — |
| `agent_run_recorder.py` | `src/agent_run_recorder.py` | Immutable agent run recording | ✅ | — |
| `advanced_reports.py` | `src/advanced_reports.py` | Advanced reporting and export | ✅ | — |
| `bot_telemetry_normalizer.py` | `src/bot_telemetry_normalizer.py` | Normalises telemetry from heterogeneous bots | ✅ | — |
| `telemetry_system/` | `src/telemetry_system/` | Core telemetry ingestion and aggregation | ✅ | prometheus-client |
| `telemetry_learning/` | `src/telemetry_learning/` | Telemetry-driven learning loop | ✅ | — |
| `compliance_report_aggregator.py` | `src/compliance_report_aggregator.py` | Aggregates compliance reports across frameworks | ✅ | — |

---

## Execution & Orchestration

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `execution/` | `src/execution/` | Core execution engine | ✅ | — |
| `execution_engine/` | `src/execution_engine/` | Staged execution engine | ✅ | — |
| `execution_orchestrator/` | `src/execution_orchestrator/` | Two-phase task orchestrator | ✅ | — |
| `execution_packet_compiler/` | `src/execution_packet_compiler/` | Compiles execution packets for dispatch | ✅ | — |
| `control_plane/` | `src/control_plane/` | Universal Control Plane | ✅ | — |
| `control_theory/` | `src/control_theory/` | Control-theory primitives (PID, FSM) | ✅ | — |
| `recursive_stability_controller/` | `src/recursive_stability_controller/` | Recursive stability control loop | ✅ | — |
| `supervisor/` | `src/supervisor/` | Agent supervision and lifecycle management | ✅ | — |
| `supervisor_system/` | `src/supervisor_system/` | Multi-agent supervisor system | ✅ | — |
| `automation_readiness_evaluator.py` | `src/automation_readiness_evaluator.py` | Evaluates task readiness for automation | ✅ | — |
| `automation_type_registry.py` | `src/automation_type_registry.py` | Registry of automation type definitions | ✅ | — |

---

## Integration & Connectors

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `integration_engine/` | `src/integration_engine/` | Unified integration engine | ✅ | — |
| `integrations/` | `src/integrations/` | External service integration adapters | ✅ | — |
| `adapter_framework/` | `src/adapter_framework/` | Generic adapter framework | ✅ | — |
| `cloudflare_deploy.py` | `src/cloudflare_deploy.py` | Cloudflare deployment automation | ✅ | — |
| `additive_manufacturing_connectors.py` | `src/additive_manufacturing_connectors.py` | 3D printing / additive manufacturing connectors | ✅ | — |
| `building_automation_connectors.py` | `src/building_automation_connectors.py` | BMS / smart building connectors | ✅ | — |
| `energy_management_connectors.py` | `src/energy_management_connectors.py` | Utility analytics, building EMS, grid management, demand response | ✅ | — |
| `factory_automation_connectors.py` | `src/factory_automation_connectors.py` | Factory automation connectors (FAC-001); OPC-UA/EtherNet-IP/PROFINET/MTConnect/MQTT-Sparkplug; 15 vendor connectors (Rockwell/Siemens/Beckhoff/FANUC/ABB/KUKA/Yaskawa/Omron/Mitsubishi/PTC/Ignition/Emerson/Cognex/Keyence/Bosch Rexroth); ISA-95 layer-ordered execution; IEC 13849 safety gate (sub-CAT_2 requires override); `FactoryAutomationRegistry` + `FactoryAutomationOrchestrator` | ✅ Operational | `thread_safe_operations` |
| `energy_audit_engine.py` | `src/energy_audit_engine.py` | Energy Audit Engine (EAE-001); ASHRAE Level I/II/III audit workflows; ECM identification; ROI/payback auto-computation; ISO 50001/50002 compliance checklists; CBECS benchmarking (12 building types); greedy-knapsack ECM prioritisation within budget; `EnergyAuditEngine`; thread-safe with RLock | ✅ Operational | `thread_safe_operations` |
| `agentic_api_provisioner.py` | `src/agentic_api_provisioner.py` | Autonomous API provisioning | ✅ | — |
| `api_collection_agent.py` | `src/api_collection_agent.py` | Discovers and catalogues external APIs | ✅ | — |
| `deployment_automation_controller.py` | `src/deployment_automation_controller.py` | Controls deployment pipelines | ✅ | — |

---

## Governance & Compliance

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `governance_framework/` | `src/governance_framework/` | Governance framework core | ✅ | — |
| `base_governance_runtime/` | `src/base_governance_runtime/` | Base governance runtime primitives | ✅ | — |
| `bot_governance_policy_mapper.py` | `src/bot_governance_policy_mapper.py` | Maps policies to bot actions | ✅ | — |
| `compliance_monitoring_completeness.py` | `src/compliance_monitoring_completeness.py` | Monitors compliance coverage completeness | ✅ | — |
| `dependency_audit_engine.py` | `src/dependency_audit_engine.py` | Audits module dependency chains | ✅ | — |

---

## Forms & Onboarding

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `form_intake/` | `src/form_intake/` | Form ingestion and processing pipeline | ✅ | — |
| `setup_wizard.py` | `src/setup_wizard.py` | 6-preset guided setup wizard | ✅ | — |
| `onboarding_flow.py` | `src/onboarding_flow.py` | Enterprise org-chart onboarding flow | ✅ | — |

---

## Bots & Autonomous Agents

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `autonomous_systems/` | `src/autonomous_systems/` | Autonomous agent runtime | ✅ | — |
| `avatar/` | `src/avatar/` | Avatar agent (persona layer) | ✅ | — |
| `aionmind/` | `src/aionmind/` | AionMind agent core | ✅ | — |
| `bot_inventory_library.py` | `src/bot_inventory_library.py` | Bot inventory and catalogue | ✅ | — |
| `advanced_swarm_system.py` | `src/advanced_swarm_system.py` | Multi-agent swarm coordination | ✅ | — |

---

## Librarian & Knowledge

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `librarian/` | `src/librarian/` | Knowledge-base and document librarian | ✅ | — |
| `schema_registry/` | `src/schema_registry/` | Schema registry and versioning | ✅ | — |
| `data_archive_manager.py` | `src/data_archive_manager.py` | Long-term data archive management | ✅ | — |
| `document_processor.py` | `src/document_processor.py` | Document ingestion and processing | ✅ | — |

---

## Backup & Disaster Recovery

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `backup_disaster_recovery.py` | `src/backup_disaster_recovery.py` | Automated snapshot/restore to S3-compatible storage; SHA-256 integrity, retention, Wingman + Sandbox gating | ✅ | — |
| `startup_validator.py` | `src/startup_validator.py` | Boot-time validation of env vars, files, ports, and dependencies | ✅ | — |

---

## Federated Learning

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `federated_learning_coordinator.py` | `src/federated_learning_coordinator.py` | Train models across distributed Murphy instances without sharing raw data; FedAvg/Median aggregation, differential-privacy noise, Wingman + Sandbox gating | ✅ | — |

---

## Real-time Event Streaming

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `websocket_event_server.py` | `src/websocket_event_server.py` | Real-time event streaming server with pub-sub EventBus, channel-based isolation, subscriber lifecycle with heartbeat TTL, Flask REST + SSE endpoints, user-agent workflow support, Wingman + Sandbox gating | ✅ | — |

---

## Digital Twin Simulation

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `digital_twin_engine.py` | `src/digital_twin_engine.py` | Model physical/logical systems as digital twins; z-score anomaly detection, failure prediction, what-if scenario simulation, fleet registry, Wingman + Sandbox gating | ✅ | — |

---

## Prometheus / OpenTelemetry Metrics Exporter

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `prometheus_metrics_exporter.py` | `src/prometheus_metrics_exporter.py` | Full Prometheus text exposition + JSON metrics API; Counter/Gauge/Histogram/Summary metric types, LabelSet dimensions, CollectorRegistry, built-in Murphy system metrics, Flask blueprint with /metrics + /api/metrics/json + /api/metrics/families + /api/metrics/register + /api/metrics/health endpoints, Wingman + Sandbox gating | ✅ | — |
| `graphql_api_layer.py` | `src/graphql_api_layer.py` | Lightweight stdlib-only GraphQL execution engine; ObjectType/InputType/EnumType schema definitions, resolver registry, query parser (shorthand + named queries + mutations + aliases + arguments), AST executor with introspection (__schema/__type), Flask blueprint with POST /graphql + GET /graphql/schema + /graphql/types + /graphql/health, Murphy REST wrapper types (HealthCheck/Metric/Module), Wingman + Sandbox gating | ✅ | — |
| `multi_tenant_workspace.py` | `src/multi_tenant_workspace.py` | Full multi-tenant workspace isolation (MTW-001); TenantConfig/TenantMember/WorkspaceData/AuditEntry dataclass models, WorkspaceManager with tenant lifecycle (create/suspend/activate/archive/delete), per-tenant RBAC (owner/admin/member/viewer/service_account), data namespace isolation, config isolation, bounded audit trail, resource quotas, Flask blueprint with 17 REST endpoints (/api/tenants CRUD, members, data, config, audit, health), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `ci_cd_pipeline_manager.py` | `src/ci_cd_pipeline_manager.py` | CI/CD Pipeline Manager (CICD-001); PipelineDefinition/PipelineRun/StageResult/BuildArtifact dataclass models, PipelineManager with full pipeline lifecycle (create/update/delete/enable/disable), run triggering with stage advancement, manual approval gates, artifact registry, pipeline statistics (success rate, avg duration), retry logic, timeout enforcement, Flask blueprint with 17 REST endpoints (/api/cicd/pipelines CRUD, /api/cicd/runs lifecycle, /api/cicd/artifacts, /api/cicd/pipelines/<id>/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `docker_containerization.py` | `src/docker_containerization.py` | Docker Containerization Manager (DCK-001); ContainerDefinition/ContainerInstance/ComposeProject/ImageRecord dataclass models, DockerManager with container lifecycle (create/start/stop/remove), Dockerfile generation (multi-stage build), docker-compose YAML generation, health check configuration, image registry, volume mounts, environment variable management with secret redaction, Flask blueprint with 17 REST endpoints (/api/docker/definitions CRUD, /api/docker/containers lifecycle, /api/docker/compose, /api/docker/images, /api/docker/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `kubernetes_deployment.py` | `src/kubernetes_deployment.py` | Kubernetes Deployment Manager (K8S-001); K8sDeployment/K8sService/K8sHPA/K8sConfigMap/K8sSecret/K8sIngress/K8sNamespace/HelmChart dataclass models, KubernetesManager with resource CRUD for all K8s resource kinds, YAML manifest generation (Deployment/Service/HPA/Chart.yaml), replica scaling, PKCE-style secrets redaction, Flask blueprint with 25+ REST endpoints (/api/k8s/deployments CRUD+scale+yaml, /api/k8s/services, /api/k8s/hpas, /api/k8s/configmaps, /api/k8s/secrets, /api/k8s/ingresses, /api/k8s/namespaces, /api/k8s/charts, /api/k8s/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `oauth_oidc_provider.py` | `src/oauth_oidc_provider.py` | OAuth2/OIDC Authentication Provider (OAU-001); ProviderConfig/AuthorizationRequest/TokenSet/OIDCDiscovery/UserInfo/OAuthSession dataclass models, OAuthManager with provider registry (Google/GitHub/Microsoft/Custom), authorization code flow with PKCE (S256 challenge), token exchange/refresh/revoke, session lifecycle (create/touch/revoke), OIDC discovery caching, role mapping, secret/token/email redaction in serialisation, Flask blueprint with 18 REST endpoints (/api/oauth/providers CRUD, /api/oauth/authorize, /api/oauth/callback, /api/oauth/tokens, /api/oauth/sessions, /api/oauth/discovery, /api/oauth/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `webhook_dispatcher.py` | `src/webhook_dispatcher.py` | Outbound Webhook Dispatcher (WHK-001); WebhookSubscription/WebhookEvent/DeliveryAttempt/DeliveryRecord dataclass models, WebhookDispatcher with subscription registry (create/get/list/update/delete/enable/disable), event matching with wildcard `*` support, HMAC-SHA256 payload signing with X-Murphy-Signature header, delivery with exponential-backoff retry (jitter, configurable max_retries/base_delay/max_delay), pluggable delivery callback, delivery history tracking, secret redaction, Flask blueprint with 13 REST endpoints (/api/webhooks/subscriptions CRUD + enable/disable, /api/webhooks/events dispatch + log, /api/webhooks/deliveries list + get + retry, /api/webhooks/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `notification_system.py` | `src/notification_system.py` | Multi-channel Notification System (NTF-001); ChannelConfig/NotificationTemplate/ChannelDelivery/Notification dataclass models, NotificationManager with channel registry (email/Slack/Discord/Teams/webhook/custom), template engine with {{variable}} substitution, priority-based routing with min_priority filtering, per-channel rate limiting (sliding window), quiet-hours suppression (critical bypasses), pluggable send callback, sensitive config key redaction, Flask blueprint with 15 REST endpoints (/api/notifications/channels CRUD + enable/disable, /api/notifications/templates CRUD, /api/notifications/send + send-template, /api/notifications/notifications list + get, /api/notifications/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `audit_logging_system.py` | `src/audit_logging_system.py` | Immutable Audit Logging System (AUD-001); AuditEntry/AuditQuery/RetentionPolicy dataclass models, AuditLogger with SHA-256 hash-chain integrity verification (tamper detection), 11 audit action types, 7 category classifications, convenience loggers (log_api_call/log_admin_action/log_config_change/log_security_event), structured query engine with multi-field filtering, retention policies with max_entries and category scoping, JSON export, PII redaction (IP/user agent), pluggable external sink callback, Flask blueprint with 13 REST endpoints (/api/audit/entries CRUD + query, /api/audit/verify, /api/audit/export, /api/audit/count, /api/audit/policies CRUD, /api/audit/retention/apply, /api/audit/stats), thread-safe lock-protected state, Wingman + Sandbox gating | ✅ | — |
| `ab_testing_framework.py` | `src/ab_testing_framework.py` | A/B Testing Framework (ABT-001); Variant/MetricDefinition/ExperimentResult/Experiment/Assignment/MetricEvent dataclass models, ABTestingEngine with experiment lifecycle (draft→running→paused→completed→archived), random/deterministic/weighted allocation strategies, sticky assignments (same subject→same variant), metric recording with per-variant per-metric statistics, simplified Welch's t-test for significance (stdlib only, no scipy), auto-promote winner when significance threshold reached, confidence intervals via z-approximation, Flask blueprint with 12 REST endpoints (/api/ab-testing/experiments CRUD + start/pause/complete, /assign, /metrics, /results, /significance, /auto-promote), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `natural_language_query.py` | `src/natural_language_query.py` | Natural Language Query Interface (NLQ-001); Entity/ParsedQuery/QueryResult/DataSourceRegistration/QueryHistoryEntry dataclass models, NLQueryEngine with rule-based intent detection (9 intents: status/count/list/detail/compare/trend/search/help/unknown), entity extraction (module/metric/time_range/status_filter/number), pluggable data-source handlers with priority-based dispatch, synonym expansion, bounded query history with intent filtering, statistics aggregation, Flask blueprint with 11 REST endpoints (/api/nlq/query, /parse, /sources CRUD + enable/disable, /history + clear, /stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `capacity_planning_engine.py` | `src/capacity_planning_engine.py` | Automated Capacity Planning Engine (CPE-001); ResourceMetric/ForecastResult/CapacityAlert/ScalingRecommendation/CapacityPlan dataclass models, CapacityPlanningEngine with time-series metric ingestion (CPU/memory/disk/network/GPU/connections/custom), three forecasting algorithms (linear regression, exponential smoothing, moving average), time-to-threshold estimation, configurable warning/critical utilisation thresholds, alert generation with acknowledge workflow, scaling recommendation engine (scale_up/plan_scaling/scale_down), capacity plan generation across all tracked resources, Flask blueprint with 13 REST endpoints (/api/capacity/metrics CRUD, /resources, /forecast, /plans CRUD + archive, /alerts + acknowledge, /stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `data_pipeline_orchestrator.py` | `src/data_pipeline_orchestrator.py` | Data Pipeline Orchestrator (DPO-001); PipelineStage/DataPipeline/PipelineRun/StageResult/DataQualityCheck/QualityCheckResult dataclass models, DataPipelineOrchestrator with pipeline CRUD (draft→active→paused→completed→failed→archived lifecycle), scheduled/manual/event-triggered execution, stage-by-stage advancement with dependency tracking, run management (trigger/cancel/list with filters), data quality checks (completeness/uniqueness/range/format/custom with severity levels), per-pipeline and global statistics, Flask blueprint with 15 REST endpoints (/api/pipelines CRUD + activate/pause/trigger/runs/stats, /api/runs get/cancel/stages/advance, /api/quality-checks CRUD + run, /api/pipelines/stats/global), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `geographic_load_balancer.py` | `src/geographic_load_balancer.py` | Geographic Load Balancing and Edge Deployment (GLB-001); Region/EdgeNode/RoutingPolicy/RoutingDecision/HealthCheckResult/DeploymentSpec dataclass models, 5 routing strategies (latency_based/geo_proximity/weighted_round_robin/failover/capacity_based), haversine distance calculation, edge node health tracking with consecutive-failure degradation, deployment lifecycle (pending→deploying→active/failed/rolled_back) with advance/rollback, Flask blueprint with 20 REST endpoints (/api/glb/regions CRUD + load update, /api/glb/nodes CRUD + health, /api/glb/policies CRUD, /api/glb/route, /api/glb/deployments CRUD + advance/rollback, /api/glb/stats, /api/glb/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `ml_model_registry.py` | `src/ml_model_registry.py` | Machine Learning Model Registry (MLR-001); ModelVersion/Model/DeploymentRecord/ABTestConfig dataclass models, ModelStatus/ModelFramework/DeploymentTarget/VersionStatus enums, MLModelRegistry with model CRUD (register/get/list with status+framework+owner+tag filters/update/delete), version management (add/get/list/promote/rollback with demotion), deployment lifecycle (deploy/complete/fail/rollback, filter by model+status), A/B testing (create/start/complete/route with configurable traffic split), aggregate statistics, Flask blueprint with 22 REST endpoints (/api/mlr/models CRUD, /api/mlr/models/{id}/versions CRUD + promote/rollback, /api/mlr/deployments CRUD + complete/fail/rollback, /api/mlr/ab-tests CRUD + start/complete/route, /api/mlr/stats, /api/mlr/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `blockchain_audit_trail.py` | `src/blockchain_audit_trail.py` | Blockchain Audit Trail (BAT-001); file-based blockchain-inspired tamper-evident audit log; AuditEntry/Block/ChainVerification/ChainStats dataclass models, EntryType/BlockStatus/ChainIntegrity enums, BlockchainAuditTrail with entry recording (6 types: api_call/admin_action/config_change/security_event/data_access/system_event), automatic + manual block sealing, SHA-256 hash chaining for tamper detection, full chain verification, paginated block listing, multi-field entry search (type/actor/resource/action), chain export, aggregate statistics, capacity eviction, Flask blueprint with 12 REST endpoints (/api/bat/entries POST + search, /api/bat/blocks GET + seal + by-id + by-index, /api/bat/verify, /api/bat/export, /api/bat/stats, /api/bat/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `voice_command_interface.py` | `src/voice_command_interface.py` | Voice Command Interface (VCI-001); speech-to-text adapter and command parser for the Murphy terminal; AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats dataclass models, AudioFormat/CommandCategory/ParseStatus/STTProviderKind enums, VoiceCommandInterface engine with pluggable STT provider (built-in keyword recogniser for testing), 12 default command patterns (status/health/deploy/help/stop/restart/configure/query/logs/security_scan/list_modules/version), regex + alias matching, argument extraction, session lifecycle management, command history with category filtering, aggregate statistics, custom pattern registration/removal, Flask blueprint with 14 REST endpoints (/api/vci/recognise POST, /api/vci/parse POST, /api/vci/process POST, /api/vci/sessions POST + GET + GET/<id> + DELETE/<id>, /api/vci/patterns GET + POST + DELETE/<cmd>, /api/vci/history GET + DELETE, /api/vci/stats GET, /api/vci/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `computer_vision_pipeline.py` | `src/computer_vision_pipeline.py` | Computer Vision Pipeline Manager (CVP-001); chain CV models into sequential pipelines: detect → classify → track → alert; ModelStage/PipelineConfig/FrameInput/DetectionResult/ClassificationResult/TrackingResult/AlertResult/PipelineRunResult/PipelineStats dataclass models, StageKind/PipelineStatus/AlertSeverity/FrameFormat enums, ComputerVisionPipeline engine with pluggable model backends (built-in keyword detector/classifier/tracker/alerter for testing), pipeline CRUD with stage management, frame processing through enabled stages, confidence threshold filtering, hazard classification and alert generation, run history with pipeline filtering, alert severity filtering, aggregate statistics, Flask blueprint with 13 REST endpoints (/api/cvp/pipelines POST + GET + GET/<id> + DELETE/<id>, /api/cvp/pipelines/<id>/status PUT, /api/cvp/pipelines/<id>/stages POST + DELETE/<sid>, /api/cvp/process POST, /api/cvp/history GET, /api/cvp/alerts GET + DELETE, /api/cvp/stats GET, /api/cvp/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `rpa_recorder_engine.py` | `src/rpa_recorder_engine.py` | Robotic Process Automation (RPA) Recorder & Playback Engine (RPA-001); record sequences of UI actions (click/type/scroll/wait/key-press/screenshot-match/drag-drop/hover/assert-text/conditional/loop) as structured recordings, play them back with parameterised templates; ActionStep/RecordingConfig/PlaybackRun/PlaybackResult/LoopDirective/ConditionalBranch/TemplateParam/RecordingStats dataclass models, ActionKind/RecordingStatus/PlaybackStatus/LoopMode enums, RpaRecorderEngine with pluggable step executor (built-in simulator for testing), recording CRUD with status lifecycle (draft→recording→paused→complete→template→archived), step add/remove/reorder, template promotion and instantiation with parameter substitution, playback execution with failure handling, run history with status/recording filters, full-text search over names/descriptions/tags, export/import, aggregate statistics, Flask blueprint with 20 REST endpoints (/api/rpa/recordings POST + GET + GET/<id> + DELETE/<id>, /api/rpa/recordings/<id>/status PUT, /api/rpa/recordings/<id>/steps POST + DELETE/<sid>, /api/rpa/recordings/<id>/steps/reorder PUT, /api/rpa/playback POST, /api/rpa/runs GET + GET/<id>, /api/rpa/runs/<id>/cancel POST, /api/rpa/recordings/<id>/promote POST, /api/rpa/recordings/<id>/instantiate POST, /api/rpa/recordings/<id>/export GET, /api/rpa/recordings/import POST, /api/rpa/search GET, /api/rpa/stats GET, /api/rpa/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `knowledge_graph_builder.py` | `src/knowledge_graph_builder.py` | Knowledge Graph Builder (KGB-001); extract entities and relationships from system data to build a queryable in-memory knowledge graph; GraphNode/GraphEdge/TraversalResult/GraphStats/SubgraphResult/QueryResult/NodeProperties/EdgeProperties dataclass models, NodeKind/EdgeKind/GraphStatus/TraversalMode enums, KnowledgeGraphEngine with node CRUD (add/get/update/delete with cascading edge removal), edge CRUD (add/get/delete with adjacency tracking), filtered listing (by kind/tag/label/source/target with limit), neighbor lookup (outgoing/incoming/both with node-kind filter), graph traversal (BFS/DFS with depth limit), shortest-path via BFS, subgraph extraction (with optional internal edges), full-text search across labels/tags/properties, graph statistics (density/components/avg degree), merge/export/import/clear, Flask blueprint with 18 REST endpoints (/api/kg/nodes POST + GET + GET/<id> + PUT/<id> + DELETE/<id>, /api/kg/edges POST + GET + GET/<id> + DELETE/<id>, /api/kg/nodes/<id>/neighbors GET, /api/kg/traverse POST, /api/kg/shortest-path POST, /api/kg/subgraph POST, /api/kg/search GET, /api/kg/stats GET, /api/kg/export POST, /api/kg/import POST, /api/kg/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `predictive_maintenance_engine.py` | `src/predictive_maintenance_engine.py` | Predictive Maintenance Engine (PME-001); anomaly detection on hardware telemetry, predict failures before they happen; SensorReading/ThresholdRule/AnomalyAlert/AssetHealth/MaintenancePrediction/TelemetrySummary dataclass models, SensorKind/AlertSeverity/AssetStatus/AggregationWindow enums, PredictiveMaintenanceEngine with reading ingestion (multi-sensor multi-asset), threshold rule CRUD (add/get/list/update/delete with warn/critical/emergency above/below thresholds), automatic alert generation (highest-severity-wins evaluation), alert management (list/filter/acknowledge), asset health tracking (auto-created on first ingest, health score 0-100, status derivation from alert ratio), manual status override, per-sensor rolling telemetry summaries (mean/median/std_dev/min/max/trend_slope with configurable window), maintenance predictions (trend-based failure classification, confidence scoring, days-to-failure estimation, human-readable recommendations), prediction history, state export/clear, Flask blueprint with 19 REST endpoints (/api/pme/readings POST + GET/<id>, /api/pme/rules POST + GET + GET/<id> + PUT/<id> + DELETE/<id>, /api/pme/alerts GET + /api/pme/alerts/<id>/ack POST, /api/pme/assets GET + /api/pme/assets/<id>/health GET + /api/pme/assets/<id>/status PUT, /api/pme/telemetry/<id> GET, /api/pme/predict/<id> POST + /api/pme/predictions/<id> GET, /api/pme/export POST, /api/pme/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `cost_optimization_advisor.py` | `src/cost_optimization_advisor.py` | Cost Optimization Advisor (COA-001); analyze cloud spend, recommend rightsizing, spot instance opportunities; CloudResource/SpendRecord/CostRecommendation/SpotOpportunity/BudgetAlert/CostSummary dataclass models, CloudProvider/ResourceKind/RecommendationSeverity/RecommendationStatus/SpotOpportunityStatus enums, CostOptimizationAdvisor with resource CRUD (register/get/list/update/delete with provider/kind/region filters), spend recording and querying (per-resource/provider/period), rightsizing analysis (utilization-based severity grading: <20% high, <40% medium, <60% low, ≥60% no action), spot instance opportunity scanning (compute-only, utilization <70% threshold, 70% savings estimate), recommendation management (list/filter/status updates), budget alerting (set budgets, 80% breach threshold, multi-budget tracking), cost summary aggregation (total spend, resource count, top category, avg utilization, potential savings per provider), state export/clear, Flask blueprint with 17 REST endpoints (/api/coa/resources CRUD, /api/coa/spend POST + GET, /api/coa/analyze/<id> POST, /api/coa/spot/scan POST, /api/coa/recommendations GET + PUT/<id>/status, /api/coa/budgets POST + GET/check, /api/coa/summary GET, /api/coa/export POST, /api/coa/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `compliance_as_code_engine.py` | `src/compliance_as_code_engine.py` | Compliance-as-Code Engine (CCE-001); encode regulatory requirements as testable rules, continuous compliance checking; ComplianceRule/CheckExecution/ComplianceScan/RemediationAction/ComplianceReport dataclass models, Framework/RuleSeverity/RuleStatus/CheckResult/ComplianceStatus enums, ComplianceAsCodeEngine with rule CRUD (create/get/list/update/delete with framework/severity/status filters), safe expression evaluator (AST-validated restricted eval — no builtins, no imports, no calls), individual rule checking against context dicts, full compliance scan execution (aggregate pass/fail/error/skip counts, compute compliant/non_compliant/partial/unknown status), report generation (compliance percentage, findings list), remediation action tracking (create/list/complete with rule/scan/completed filters), compliance summary aggregation, state export/clear, Flask blueprint with 17 REST endpoints (/api/cce/rules CRUD, /api/cce/check/<id> POST, /api/cce/scan POST, /api/cce/scans GET + GET/<id> + GET/<id>/report, /api/cce/remediations POST + GET + POST/<id>/complete, /api/cce/summary GET, /api/cce/export POST, /api/cce/health GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |
| `multi_cloud_orchestrator.py` | `src/multi_cloud_orchestrator.py` | Multi-Cloud Orchestrator (MCO-001); deploy and manage Murphy across AWS, GCP, Azure simultaneously; ProviderConfig/CloudDeployment/FailoverRule/SyncTask/CostRecord dataclass models, CloudProvider/DeploymentStatus/HealthState/FailoverStrategy enums, MultiCloudOrchestrator with provider CRUD (register/get/list/update/remove with provider/enabled filters), deployment lifecycle (create/get/list/update status/delete with provider/status filters), failover rule management (create/list with primary_provider/enabled filters, evaluate_failover with health-based triggering), resource sync (start/complete/list with source_provider/status filters, in_progress/completed/failed states), cost tracking (record/list/summary with per-provider aggregation), health monitoring (update per-deployment state, get_health_overview with healthy/degraded/unhealthy/unknown counts), state export/clear/summary, Flask blueprint with 25 REST endpoints (/api/mco/providers CRUD, /api/mco/deployments CRUD + status + health, /api/mco/failover-rules POST + GET, /api/mco/failover/<id>/evaluate, /api/mco/syncs POST + GET + complete, /api/mco/costs POST + GET + /summary, /api/mco/health/overview + /health, /api/mco/export POST, /api/mco/summary GET), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating | ✅ | — |

---

## Issue #136 Subsystems (Operational)

These seven subsystems were added under issue #136 and are now fully operational with
production-grade tests. All gaps have been filled and all tests pass.

| Module | Path | Description | Status |
|--------|------|-------------|--------|
| `murphy_drawing_engine.py` | `src/murphy_drawing_engine.py` | Engineering drawing engine with SVG/DXF export, BOM extraction, agentic commands | ✅ Operational |
| `murphy_credential_gate.py` | `src/murphy_credential_gate.py` | Zero-trust credential validation at every gate boundary | 🔄 In Progress |
| `murphy_sensor_fusion.py` | `src/murphy_sensor_fusion.py` | Multi-source signal merging for autonomous decision-making | 🔄 In Progress |
| `murphy_osmosis_engine.py` | `src/murphy_osmosis_engine.py` | Passive knowledge absorption and cross-domain synthesis | 🔄 In Progress |
| `murphy_autonomous_perception.py` | `src/murphy_autonomous_perception.py` | Environment awareness and contextual state inference | 🔄 In Progress |
| `murphy_wingman_evolution.py` | `src/murphy_wingman_evolution.py` | Adaptive learning for Wingman Protocol validation rules | 🔄 In Progress |
| `murphy_engineering_toolbox.py` | `src/murphy_engineering_toolbox.py` | Developer utilities: schema scaffolding, stub generation, diff tools | ✅ Operational |
| `murphy_drawing_engine.py` | `src/murphy_drawing_engine.py` | Vector/raster canvas; DXF R12, SVG, PDF export; NL command assistant (rectangle, circle, line, polygon, text, sheet); PE-stamp approval integration | ✅ Operational |
| `murphy_credential_gate.py` | `src/murphy_credential_gate.py` | Zero-trust credential validation; 15 credential types; SHA-256 e-stamp; multi-party approval workflow; suspension/revocation handling | ✅ Operational |
| `murphy_sensor_fusion.py` | `src/murphy_sensor_fusion.py` | All 6 fusion strategies (Kalman, Bayesian, Complementary, Weighted Average, Majority Vote, Latest Valid); spike/stuck/disagreement anomaly detection; staleness computation | ✅ Operational |
| `murphy_osmosis_engine.py` | `src/murphy_osmosis_engine.py` | Full Observe→Extract→Build→Sandbox→Validate→Deploy pipeline; AbsorbedCapabilityRegistry; InsightExtractor; effectiveness_score ≥ 0.7 gating | ✅ Operational |
| `murphy_autonomous_perception.py` | `src/murphy_autonomous_perception.py` | Object tracking (greedy nearest-neighbor); TTC-based safety decisions (PROCEED/SLOW/STOP/EMERGENCY_STOP); drivable area ray-casting; full perception pipeline | ✅ Operational |
| `murphy_wingman_evolution.py` | `src/murphy_wingman_evolution.py` | Validation metrics (precision/recall/F1); runbook evolution (relax/tighten/add rules); cascading wingman; auto runbook generator; wingman factory | ✅ Operational |
| `murphy_engineering_toolbox.py` | `src/murphy_engineering_toolbox.py` | 60+ unit conversions across 11 categories (incl. temperature C/F/K); structural, HVAC, electrical, plumbing, CPM critical-path, earned-value management | ✅ Operational |

---

## Self-Marketing & Revenue Generation

These modules form Murphy's autonomous marketing and go-to-market engine — Murphy markets,
sells, and partners for itself with full compliance gating and human-in-the-loop oversight.

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `market_positioning_engine.py` | `src/market_positioning_engine.py` | Market Positioning Engine (MPE-001); authoritative source for Murphy's capabilities, target industry verticals, ICPs, value propositions, and competitive moats; 17 registered capabilities (maturity-scored from CAPABILITY_SCORECARD); **10 industry verticals**: Healthcare, Financial Services, Manufacturing, Technology, Professional Services, Government, IoT/Building Automation, Energy Management, Additive Manufacturing, Factory Automation — each with ICP, pain points, regulatory context, content topics, and B2B pitch hooks; updated `MURPHY_MARKET_POSITION` with 8 competitive moats, 6 target segments, 6 differentiation pillars; `MarketPositioningEngine` with `get_market_position`, `list_capabilities`, `get_vertical`, `get_ideal_customer_profile`, `get_content_topics_for_vertical`, `get_industry_pitch_angle`, `get_positioning_for_offering_types`, `score_partner_fit`; all inputs validated against closed allowlists (CWE-20); zero external deps; ~120 tests in `test_market_positioning_engine.py` | ✅ Operational | — |
| `self_marketing_orchestrator.py` | `src/self_marketing_orchestrator.py` | Self-Marketing Orchestrator (MKT-006); autonomous marketing loop: weekly content cycle (blog posts, case studies, tutorials), daily social cycle (Twitter/LinkedIn/Reddit variants), outreach cycle (COMPL-001/002 gated), developer attraction cycle, and weekly B2B partnership cycle; `SelfMarketingOrchestrator` wired to `MarketPositioningEngine` — content cycles enriched with vertical-specific topics, B2B pitches enriched with capability intelligence; `PartnershipProspect` with named salesperson contacts (`salesperson_name`, `salesperson_title`, `salesperson_email` [PII-safe], `salesperson_linkedin`); `add_salesperson_contact()` for runtime contact updates; **22 default partners** spanning all 10 verticals: HubSpot, Zapier, Make, n8n, Salesforce, M365, Notion, Linear, Datadog, GitHub (core) + Siemens Smart Infrastructure, Johnson Controls OpenBlue, Honeywell Forge Buildings, Ameresco, Facilio, EnergyCAP, Stratasys, EOS GmbH, Markforged, Rockwell Automation, Beckhoff, PTC ThingWorx (new); `_commission_system()` is a cross-cutting gate (NOT a partner offering) called automatically at the end of every B2B cycle and content cycle, emitting `system_commissioned` event to audit trail; 10 content categories including `building_automation_iot`, `energy_management`, `additive_manufacturing`, `factory_automation`; hardened: `_PROSPECT_ID_RE`, `_PARTNER_ID_RE`, `_CONTENT_ID_RE`, `_ALLOWED_CHANNELS`, topic/keyword/reply/queue/DNC/cooldown/content caps, `_sanitize_error` (CWE-209), type guards in `load_state`; **264 tests across 3 test files** | ✅ Operational | `market_positioning_engine`, `contact_compliance_governor`, `outreach_compliance_integration`, `thread_safe_operations` |

---

## Industrial & OT Connector Ecosystem

These modules provide protocol-native connectors to industrial and operational-technology platforms,
enabling Murphy to integrate directly with factory floors, smart buildings, energy systems, and
additive-manufacturing cells.

| Module | Protocols | Connectors / Classes | Key Features | Status |
|--------|-----------|----------------------|--------------|--------|
| `building_automation_connectors.py` | BACnet/IP, KNX, Modbus, DALI, LonWorks, OPC-UA | 15+ connectors; `BuildingAutomationRegistry` + `BuildingAutomationOrchestrator` | HVAC/lighting/access control; LEED/BREEAM compliance hooks; Siemens Desigo, JCI OpenBlue, Honeywell Forge | ✅ Operational |
| `energy_management_connectors.py` | REST, OPC-UA, Modbus, DNP3 | `EnergyManagementRegistry` + `EnergyWorkflowOrchestrator` | Utility analytics, building EMS, grid management, demand response; EnergyCAP, Facilio, Ameresco | ✅ Operational |
| `additive_manufacturing_connectors.py` | OPC-UA AM / OPC 40564, REST | `AdditiveManufacturingRegistry` + `AMWorkflowBinder` | FDM/SLS/DMLS/SLA/PolyJet/EBM/WAAM processes; GrabCAD/Eiger/EOSTATE integration; Stratasys/EOS/Markforged | ✅ Operational |
| `factory_automation_connectors.py` (FAC-001) | OPC-UA, EtherNet/IP, PROFINET, MTConnect, MQTT Sparkplug | 15 vendor connectors (Rockwell/Siemens/Beckhoff/FANUC/ABB/KUKA/Yaskawa/Omron/Mitsubishi/PTC/Ignition/Emerson/Cognex/Keyence/Bosch Rexroth); `FactoryAutomationRegistry` + `FactoryAutomationOrchestrator` | ISA-95 layer-aware orchestration (FIELD→CONTROL→SUPERVISORY→MES); IEC 13849 safety gate (sub-CAT_2 requires override) | ✅ Operational |
| `energy_audit_engine.py` (EAE-001) | Internal (no OT protocol) | `EnergyAuditEngine` | ASHRAE Level I/II/III workflows; ECM identification; ROI/payback auto-computation; ISO 50001/50002 compliance checklists; CBECS benchmarking (12 building types); greedy-knapsack ECM prioritisation | ✅ Operational |

---

## New Modules (2026-03-14)

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `self_introspection_module.py` | `src/self_introspection_module.py` | Runtime self-analysis, codebase scanning, dependency graph extraction | ✅ Operational | ast |
| `self_codebase_swarm.py` | `src/self_codebase_swarm.py` | Autonomous BMS spec generation, RFP parsing, deliverable packaging | ✅ Operational | cutsheet_engine |
| `cutsheet_engine.py` | `src/cutsheet_engine.py` | Manufacturer data parsing, wiring diagrams, device config generation | ✅ Operational | — |
| `visual_swarm_builder.py` | `src/visual_swarm_builder.py` | Visual pipeline construction for swarm workflows | ✅ Operational | — |
| `ceo_branch_activation.py` | `src/ceo_branch_activation.py` | Top-level autonomous decision-making, org chart automation, operational planning | ✅ Operational | event_backbone, org_chart_enforcement |
| `production_assistant_engine.py` | `src/production_assistant_engine.py` | Request lifecycle management with deliverable gate validation | ✅ Operational | event_backbone, persistence_manager |

---

## Time Tracking Phase 6B–6D

| Module | Path | Description | Status | Key Dependencies |
|--------|------|-------------|--------|-----------------|
| `time_tracking/reporting_service.py` | `src/time_tracking/reporting_service.py` | Time entry reporting | ✅ Operational | time_tracking |
| `time_tracking/approval_service.py` | `src/time_tracking/approval_service.py` | Time entry approval workflows | ✅ Operational | time_tracking |
| `time_tracking/export_service.py` | `src/time_tracking/export_service.py` | Time data export (CSV, PDF) | ✅ Operational | time_tracking |
| `time_tracking/dashboard_widgets.py` | `src/time_tracking/dashboard_widgets.py` | Dashboard UI widgets | ✅ Operational | time_tracking |
| `time_tracking/summary_statistics.py` | `src/time_tracking/summary_statistics.py` | Summary statistics aggregation | ✅ Operational | time_tracking |
| `time_tracking/team_views.py` | `src/time_tracking/team_views.py` | Team-level time views | ✅ Operational | time_tracking |
| `time_tracking/dashboard_api.py` | `src/time_tracking/dashboard_api.py` | Dashboard REST API endpoints | ✅ Operational | time_tracking |
| `time_tracking/billing_integration.py` | `src/time_tracking/billing_integration.py` | Billing system integration | ✅ Operational | time_tracking |
| `time_tracking/invoicing_hooks.py` | `src/time_tracking/invoicing_hooks.py` | Invoice generation hooks | ✅ Operational | time_tracking |
| `time_tracking/settings_api.py` | `src/time_tracking/settings_api.py` | Time tracking settings API | ✅ Operational | time_tracking |
| `time_tracking/config.py` | `src/time_tracking/config.py` | Time tracking configuration | ✅ Operational | time_tracking |

---

## Related Documents

- [WINGMAN_PROTOCOL.md](WINGMAN_PROTOCOL.md) — Wingman Protocol architecture
- [API_REFERENCE.md](API_REFERENCE.md) — REST API documentation for all modules
- [GAP_ANALYSIS.md](GAP_ANALYSIS.md) — Gap analysis including #136 subsystem tracking
- [GAP_CLOSURE.md](GAP_CLOSURE.md) — Code gap remediation log
- [ARCHITECTURE_MAP.md](../ARCHITECTURE_MAP.md) — High-level system architecture

---

*Copyright © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1 | Last Updated: 2026-03-14*
