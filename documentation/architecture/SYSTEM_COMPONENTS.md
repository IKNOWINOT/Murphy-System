# System Components

Overview of the core components that make up the Murphy System architecture.

> **Last updated:** 2026-03-11 — auto-generated from the repository subsystem index.

## Core Runtime

| Component | Module | Description |
|-----------|--------|-------------|
| **Runtime Server** | `murphy_system_1.0_runtime.py` → `src/runtime/` | Thin entry-point; implementation in `src/runtime/app.py` (FastAPI), `src/runtime/murphy_system_core.py` (orchestration), `src/runtime/living_document.py` |
| **CLI Tool** | `murphy` | Start/stop/status/help CLI |
| **Configuration** | `src/config.py` | Pydantic `BaseSettings` — loads `.env` |

## Execution & Orchestration

| Component | Module | Description |
|-----------|--------|-------------|
| **Gate Execution Wiring** | `src/gate_execution_wiring.py` | Runtime gate enforcement — EXECUTIVE/OPERATIONS/QA/HITL/COMPLIANCE/BUDGET |
| **Control Plane Separation** | `src/control_plane_separation.py` | Planning/execution plane split, mode switching |
| **Durable Swarm Orchestrator** | `src/durable_swarm_orchestrator.py` | Budget-aware swarms, idempotency, circuit breaker |
| **Swarm System** | `src/true_swarm_system.py` | Dynamic swarm generation |
| **Automation Scheduler** | `src/automation_scheduler.py` | Multi-project priority scheduling + load balancing |
| **Workflow DAG Engine** | `src/workflow_dag_engine.py` | DAG workflows: topological sort, parallel groups, conditional branching |
| **Golden Path Bridge** | `src/golden_path_bridge.py` | Execution path capture, replay, similarity matching |
| **Deterministic Routing Engine** | `src/deterministic_routing_engine.py` | Policy-driven deterministic/LLM/hybrid routing |

## Intelligence & Learning

| Component | Module | Description |
|-----------|--------|-------------|
| **Confidence Engine** | `src/confidence_engine/` | G/D/H Formula + 5D Uncertainty scoring |
| **Learning Engine** | `src/learning_engine/` | Shadow agent training pipeline |
| **Self-Improvement Engine** | `src/self_improvement_engine.py` | Feedback loops, calibration, remediation |
| **ML Strategy Engine** | `src/ml_strategy_engine.py` | Anomaly detection, forecasting, classification, RL, ensemble |
| **AI Workflow Generator** | `src/ai_workflow_generator.py` | Natural language → DAG workflows |
| **Rubix Evidence Adapter** | `src/rubix_evidence_adapter.py` | Deterministic evidence: CI, Bayesian, Monte Carlo, forecast |
| **Semantics Boundary Controller** | `src/semantics_boundary_controller.py` | Belief-state, risk/CVaR, verification-feedback |

## Governance & Compliance

| Component | Module | Description |
|-----------|--------|-------------|
| **Governance Framework** | `src/governance_framework/` | Scheduler + authority bands |
| **Governance Kernel** | `src/governance_kernel.py` | Non-LLM enforcement, budget tracking, audit emission |
| **RBAC Governance** | `src/rbac_governance.py` | Multi-tenant RBAC, shadow agent governance |
| **Compliance Engine** | `src/compliance_engine.py` | GDPR/SOC2/HIPAA/PCI-DSS sensors |
| **Compliance Region Validator** | `src/compliance_region_validator.py` | Region-specific validation, cross-border, data residency |
| **Org Chart Enforcement** | `src/org_chart_enforcement.py` | Role-bound permissions, escalation chains |
| **Wingman Protocol** | `src/wingman_protocol.py` | Executor/validator pairing |

## Security Plane

| Component | Module | Description |
|-----------|--------|-------------|
| **Security Hardening Config** | `src/security_hardening_config.py` | XSS/SQLi/path traversal, CORS, rate limiting, CSP, API key rotation |
| **Authorization Enhancer** | `src/security_plane/authorization_enhancer.py` | Per-request ownership, session context |
| **Log Sanitizer** | `src/security_plane/log_sanitizer.py` | PII detection (8 types), automated redaction |
| **Bot Resource Quotas** | `src/security_plane/bot_resource_quotas.py` | Per-bot quotas, swarm limits, auto-suspension |
| **Swarm Communication Monitor** | `src/security_plane/swarm_communication_monitor.py` | DFS cycle detection, rate limiting |
| **Bot Identity Verifier** | `src/security_plane/bot_identity_verifier.py` | HMAC-SHA256 signing, key revocation |
| **Bot Anomaly Detector** | `src/security_plane/bot_anomaly_detector.py` | Z-score analysis, resource spikes, API patterns |
| **Security Dashboard** | `src/security_plane/security_dashboard.py` | Unified event view, correlation, compliance reports |

## Human-in-the-Loop (HITL)

| Component | Module | Description |
|-----------|--------|-------------|
| **HITL Autonomy Controller** | `src/hitl_autonomy_controller.py` | Arming/disarming, confidence-gated autonomy |
| **Freelancer Validator** | `src/freelancer_validator/` | Fiverr/Upwork adapters, credential verification |
| **Runtime Profile Compiler** | `src/runtime_profile_compiler.py` | Onboarding-to-profile, safety/autonomy controls |
| **Credential Profile System** | `src/credential_profile_system.py` | HITL credential profiles & metrics |

## Integration & Connectivity

| Component | Module | Description |
|-----------|--------|-------------|
| **Integration Engine** | `src/integration_engine/` | GitHub ingestion + HITL approvals |
| **Platform Connector Framework** | `src/platform_connector_framework.py` | 20 connectors (Slack, Jira, Salesforce, GitHub, AWS, etc.) |
| **API Gateway Adapter** | `src/api_gateway_adapter.py` | Rate limiting, auth, circuit breaker, caching |
| **Webhook Event Processor** | `src/webhook_event_processor.py` | 10 webhook sources, signature verification |
| **Cross-Platform Data Sync** | `src/cross_platform_data_sync.py` | Bidirectional sync, conflict resolution |
| **Remote Access Connector** | `src/remote_access_connector.py` | TeamViewer/AnyDesk/RDP/VNC/SSH/Parsec |
| **Video Streaming Connector** | `src/video_streaming_connector.py` | Twitch/YouTube Live/OBS simulcasting |
| **Content Creator Platform Modulator** | `src/content_creator_platform_modulator.py` | YouTube/Twitch/TikTok/Patreon cross-platform |
| **Ticketing Adapter** | `src/ticketing_adapter.py` | ITSM lifecycle, patch/rollback |

## Persistence & Observability

| Component | Module | Description |
|-----------|--------|-------------|
| **Persistence Manager** | `src/persistence_manager.py` | Durable JSON storage, audit trails, replay |
| **Event Backbone** | `src/event_backbone.py` | Pub/sub, retry, circuit breakers, dead letter queue |
| **SLO Tracker** | `src/operational_slo_tracker.py` | Success rate, latency percentiles |
| **Observability Counters** | `src/observability_counters.py` | Behavior fix vs coverage tracking |
| **Capability Map** | `src/capability_map.py` | AST-based module inventory, gap analysis |
| **Rosetta Stone Heartbeat** | `src/rosetta_stone_heartbeat.py` | Org-wide pulse propagation |

## Delivery & Content

| Component | Module | Description |
|-----------|--------|-------------|
| **Delivery Adapters** | `src/delivery_adapters.py` | Document/email/chat/voice/translation |
| **Digital Asset Generator** | `src/digital_asset_generator.py` | Unreal/Maya/Blender/Unity/Godot pipelines |
| **Automation Type Registry** | `src/automation_type_registry.py` | 16 templates across 11 categories |
| **Workflow Template Marketplace** | `src/workflow_template_marketplace.py` | Publish, search, install community templates |

## Self-Operation & Extensibility

| Component | Module | Description |
|-----------|--------|-------------|
| **Self-Automation Orchestrator** | `src/self_automation_orchestrator.py` | Prompt chain, task queue, gap analysis |
| **Agentic API Provisioner** | `src/agentic_api_provisioner.py` | Self-provisioning API, OpenAPI spec generation |
| **Plugin/Extension SDK** | `src/plugin_extension_sdk.py` | Third-party plugin lifecycle, sandboxed execution |
| **Shadow Agent Integration** | `src/shadow_agent_integration.py` | Shadow-agent org-chart parity |

## Legacy Compatibility

| Component | Module | Description |
|-----------|--------|-------------|
| **Legacy Compatibility Matrix** | `src/legacy_compatibility_matrix.py` | Bridge hooks, migration paths |
| **Bot Governance Policy Mapper** | `src/bot_governance_policy_mapper.py` | Legacy bot → Murphy runtime profiles |
| **Bot Telemetry Normalizer** | `src/bot_telemetry_normalizer.py` | Triage/rubix → Murphy observability schema |
| **Triage Rollcall Adapter** | `src/triage_rollcall_adapter.py` | Capability rollcall, candidate ranking |

## Web Interfaces

62 web interfaces built on a shared design system:

| File | Role | Type |
|------|------|------|
| `murphy_landing_page.html` | Public front door | Landing page |
| `onboarding_wizard.html` | New user | Conversational wizard |
| `terminal_unified.html` | Admin | Multi-role dashboard |
| `terminal_architect.html` | System Architect | Dashboard + Terminal |
| `terminal_enhanced.html` | Power User | Dashboard + Terminal |
| `terminal_integrated.html` | Operations Manager | Dashboard |
| `terminal_worker.html` | Delivery Worker | Dashboard |
| `terminal_costs.html` | Finance / Budget | Dashboard |
| `terminal_orgchart.html` | HR / Admin | Dashboard |
| `terminal_integrations.html` | DevOps | Dashboard |
| `workflow_canvas.html` | Workflow Designer | Graphical canvas |
| `system_visualizer.html` | System Topology | Graphical canvas |
| `murphy-smoke-test.html` | Developer / QA | API smoke test |
| `murphy_ui_integrated.html` | Legacy | Redirects to `terminal_unified.html` |
| `murphy_ui_integrated_terminal.html` | Legacy | Redirects to `terminal_unified.html` |

## New Components (2026-03-14)

### Self-Introspection Module (INTRO-001)
- **Layer:** Observability / Self-Analysis
- **File:** `src/self_introspection_module.py`
- **Purpose:** Runtime self-analysis, codebase scanning, dependency graph extraction
- **Design Label:** INTRO-001
- **Events:** Publishes `introspection_completed`, `metric_recorded`

### Self-Codebase Swarm (SCS-001)
- **Layer:** Autonomous Operations / Swarm
- **File:** `src/self_codebase_swarm.py`
- **Purpose:** Autonomous BMS spec generation, RFP parsing, deliverable packaging
- **Design Label:** SCS-001
- **Events:** Publishes `task_completed`, `task_submitted`
- **Dependencies:** `cutsheet_engine` (CSE-001)

### Cut Sheet Engine (CSE-001)
- **Layer:** Data Processing / Integration
- **File:** `src/cutsheet_engine.py`
- **Purpose:** Manufacturer data parsing, wiring diagrams, device config generation
- **Design Label:** CSE-001
- **Events:** Publishes `task_completed`, `metric_recorded`

### Visual Swarm Builder (VSB-001)
- **Layer:** User Interface / Workflow Construction
- **File:** `src/visual_swarm_builder.py`
- **Purpose:** Visual pipeline construction for swarm workflows
- **Design Label:** VSB-001
- **Events:** Publishes `task_completed`

### CEO Branch Activation (CEO-002)
- **Layer:** Autonomous Operations / Executive Control
- **File:** `src/ceo_branch_activation.py`
- **Purpose:** Top-level autonomous decision-making, org chart automation, operational planning
- **Design Label:** CEO-002
- **Events:** Publishes `ceo_branch_activated`, `ceo_directive_issued`, `metric_recorded`
- **Integration:** Wired to `ActivatedHeartbeatRunner` via tick() callback

### Production Assistant Engine (PROD-ENG-001)
- **Layer:** Operations / Lifecycle Management
- **File:** `src/production_assistant_engine.py`
- **Purpose:** Request lifecycle management with 7-stage pipeline and deliverable gate validation
- **Design Label:** PROD-ENG-001
- **Events:** Publishes `gate_evaluated`, `task_submitted`, `task_completed`
- **Gate:** 99% confidence threshold via `DeliverableGateValidator` (COMPLIANCE SafetyGate)

## See Also

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Root README](../../../README.md) — full subsystem lookup table
