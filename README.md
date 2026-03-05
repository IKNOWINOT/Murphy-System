# Murphy System 1.0

**Universal AI Automation System**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/IKNOWINOT/Murphy-System) [![License](https://img.shields.io/badge/license-BSL%201.1-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)](https://www.python.org/) [![Tests](https://img.shields.io/badge/tests-8843%20passing-brightgreen.svg)](#-test-status)

---

> ## ⚠️ Important — Please Read Before Using
>
> **Murphy is an ambitious, deeply complex AI automation system.** It is currently
> developed and maintained by a **single developer** ([@IKNOWINOT](https://github.com/IKNOWINOT)).
> While the architecture is comprehensive and the test suite covers thousands of
> functions, **not everything works as intended**. Emergent bugs are still being
> discovered and classified across the 595+ module surface area.
>
> **What this means for you:**
>
> - 🧪 **Alpha-quality software** — treat it as a research prototype, not a
>   production-ready product. Security hardening is required before any
>   deployment.
> - 🐛 **Emergent bugs** — complex interactions between modules can produce
>   unexpected behavior. Edge cases are actively being catalogued.
> - 🔧 **Self-healing capabilities** — Murphy includes a self-improvement engine,
>   bug pattern detector, and correction loop. It *can* apply patches and
>   process improvement requests automatically, but this pipeline is still
>   maturing. File issues or submit patches and the system's self-improvement
>   loop will attempt to incorporate them.
> - 📊 **Test coverage is extensive but not exhaustive** — 8,800+ tests pass
>   across 371 test files, yet some Flask/Textual-dependent tests require
>   optional dependencies and are skipped when those packages are absent.
> - 🤝 **Contributions welcome** — see [CONTRIBUTING.md](CONTRIBUTING.md). Bug
>   reports, especially with reproduction steps, are especially valuable at
>   this stage.
>
> **Bottom line:** This system is genuinely powerful — it can automate an entire
> business stack from intake to delivery. But running it in production without
> review is not recommended. Proceed with curiosity, caution, and the
> understanding that you're looking at a one-person moonshot.

---

## 🎯 What is Murphy?

Murphy is a **complete, operational AI automation system** that can automate any business type, including its own operations. It requires security hardening before production deployment.

### Key Features

✅ **Universal Automation** - Automate anything (factory, content, data, system, agent, business)  
✅ **Self-Integration** - Add GitHub repos, APIs, hardware automatically  
✅ **Self-Improvement** - Learns from corrections, trains shadow agent  
✅ **Self-Operation** - Runs Inoni LLC autonomously  
✅ **Human-in-the-Loop** - Safety approval for all integrations  
✅ **Deployment References** - Legacy Docker/Kubernetes examples available in archives (security hardening required)

---

## 🚀 Quick Start & Installation

### One-Step Setup & Start (Recommended)

Clone the repo, then run **one command** — it installs everything and starts Murphy:

```bash
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
bash setup_and_start.sh
```

On Windows:
```cmd
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
setup_and_start.bat
```

That's it. The script handles the virtual environment, installs **all** dependencies (including extras), configures `.env`, and lets you choose between the backend server or the terminal UI.

> **No API key required** — the onboard LLM works out of the box. Add a [Groq API key](https://console.groq.com) to `.env` for enhanced quality (optional).

### Remote One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
```

Then use the `murphy` CLI:
```bash
murphy start          # Start in foreground
murphy start -d       # Start as background daemon
murphy status         # Check health
murphy stop           # Stop daemon
murphy help           # See all commands
```

**📚 Documentation:**
- **Complete Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **Quick Start:** [Murphy System/MURPHY_1.0_QUICK_START.md](Murphy%20System/MURPHY_1.0_QUICK_START.md)
- **API Reference:** [Murphy System/API_DOCUMENTATION.md](Murphy%20System/API_DOCUMENTATION.md)
- **Deployment Guide:** [Murphy System/DEPLOYMENT_GUIDE.md](Murphy%20System/DEPLOYMENT_GUIDE.md)

---

## 📊 Overall System Completion

| Area | Completion |
| --- | --- |
| Execution wiring (gate + swarm + orchestrator) | **100%** |
| Deterministic + LLM routing | **100%** |
| Persistence + replay | **100%** |
| Multi-channel delivery | **100%** |
| Compliance validation | **100%** |
| Operational automation | **100%** |
| File system cleanup | **100%** |
| Test coverage (dynamic chains) | **100%** |
| UI + user testing | **85%** |
| Security hardening | **100%** |
| Code quality audit (90 categories) | **100%** |
| **Overall average** | **~99%** |

> **Test status (latest run):** 8,843 test functions · 0 failed · 371 test files.
> Skipped tests require optional packages (Flask, Textual, torch).
> See [Test Status](#-test-status) below.

---

## 🗂️ Repository Structure (Post-Cleanup)

```
Murphy-System/
├── README.md                           ← You are here
├── GETTING_STARTED.md                  ← Setup guide
├── CONTRIBUTING.md                     ← Contribution guidelines
├── CODE_OF_CONDUCT.md                  ← Community standards
├── SECURITY.md                         ← Vulnerability reporting
├── CHANGELOG.md                        ← Version history
├── LICENSE                             ← BSL 1.1 (→ Apache 2.0 after 4 yr)
├── install.sh                          ← One-line CLI installer
├── .gitignore
├── requirements.txt
├── scripts/
│   └── transfer_archive.sh             ← Archive transfer tool
├── docs/
│   └── screenshots/                    ← Verification screenshots
└── Murphy System/                      ← ACTIVE SYSTEM
    ├── murphy                          ← CLI tool (start/stop/status/…)
    ├── murphy_system_1.0_runtime.py    ← Single production runtime
    ├── src/                            ← 595 production modules
    ├── tests/                          ← 371 test files (8,800+ tests)
    ├── bots/                           ← 104 bot modules
    ├── documentation/                  ← Structured API/user docs
    ├── docs/                           ← Technical docs
    ├── k8s/                            ← Kubernetes manifests
    ├── monitoring/                     ← Prometheus config
    ├── scripts/                        ← Operational scripts
    ├── *.html                          ← 8 neon terminal UIs
    ├── USER_MANUAL.md                  ← Comprehensive user manual
    ├── BUSINESS_MODEL.md               ← Open-core editions
    ├── README.md, API_DOCUMENTATION.md, DEPLOYMENT_GUIDE.md
    └── Dockerfile, docker-compose.yml  ← Container deployment
```

> **Archive:** Legacy versions and artifacts have been moved to
> [iknowinot/murphy-system-archive](https://github.com/IKNOWINOT/murphy-system-archive)
> to keep downloads lean.

---

## ✅ Runtime 1.0 Status

`murphy_system_1.0_runtime.py` is the single production runtime.

**How to run:**
```bash
cd "Murphy System" && ./start_murphy_1.0.sh
```

**Available endpoints:** `/api/health`, `/api/status`, `/api/info`, `/api/execute`, and automation endpoints under `/api/automation/...`

**Key runtime capabilities:**
- Deterministic and LLM routing via policy-driven routing engine
- Multi-channel delivery (document, email, chat, voice, translation)
- Gate-based execution wiring with EXECUTIVE/OPERATIONS/QA/HITL/COMPLIANCE/BUDGET gates
- Two-phase and async orchestration with swarm execution support
- Persistence and replay via durable file-based JSON storage
- Event backbone with pub/sub, retry, circuit breakers, and dead letter queue
- Self-improvement engine with pattern extraction and confidence calibration
- Operational SLO tracking (success rates, latency percentiles)
- Compliance validation (GDPR/SOC 2/HIPAA/PCI-DSS) with regional support
- RBAC governance with shadow agent integration
- Per-request ownership verification and session context enforcement
- PII detection and automated log sanitization (8 pattern types)
- Per-bot and per-swarm resource quotas with auto-suspension
- Swarm communication loop detection (DFS cycle detection, rate limiting)
- Cryptographic bot identity verification (HMAC-SHA256 signing)
- Behavioral anomaly detection (z-score analysis, resource spikes, API patterns)
- Unified security dashboard with event correlation and compliance reporting
- 42 integrated modules, 8,800+ tests passing
- Neon terminal UI across 8 HTML interfaces with consistent theme

**Architect UI:** serve `Murphy System/terminal_architect.html` with `python -m http.server 8090` and open `http://localhost:8090/Murphy%20System/terminal_architect.html?apiPort=8000`

---

## 🗃️ Repository Index (Database-Style Reference)

Use this table as the primary lookup for active modules, docs, and entry points.

| Domain | Location | Purpose | Entry Points |
| --- | --- | --- | --- |
| **Runtime API** | `Murphy System/murphy_system_1.0_runtime.py` | Runtime 1.0 API server | `Murphy System/start_murphy_1.0.sh`, `GET /api/status` |
| **Role-based UIs** | `Murphy System/terminal_architect.html` | Architect planning + gate review UI | `python -m http.server 8090`, `?apiPort=8000` |
| **Operations UI** | `Murphy System/terminal_integrated.html` | Operations execution UI | `python -m http.server 8090`, `?apiPort=8000` |
| **Worker UI** | `Murphy System/terminal_worker.html` | Delivery worker UI | `python -m http.server 8090`, `?apiPort=8000` |
| **Legacy UI Assets** | `Murphy System/murphy_ui_integrated.html` | Legacy UI assets (scheduled for archive) | Open directly for reference |
| **Tests** | `Murphy System/tests/` | Dynamic chain, gate, and capability tests | `python -m pytest` |

### Subsystem Lookup

| Subsystem | Primary Module | Notes |
| --- | --- | --- |
| **Gate + Confidence** | `src/confidence_engine/` | G/D/H + 5D uncertainty |
| **Learning + Corrections** | `src/learning_engine/` | Shadow agent training pipeline |
| **Integration Engine** | `src/integration_engine/` | GitHub ingestion + HITL approvals |
| **Swarm System** | `src/true_swarm_system.py` | Dynamic swarm generation (wiring ongoing) |
| **Governance** | `src/governance_framework/` | Scheduler + authority bands |
| **Persistence** | `src/persistence_manager.py` | Durable JSON storage, audit trails, replay |
| **Event Backbone** | `src/event_backbone.py` | Durable queues, retry, circuit breakers |
| **Delivery Adapters** | `src/delivery_adapters.py` | Document/email/chat/voice/translation |
| **Gate Execution** | `src/gate_execution_wiring.py` | Runtime gate enforcement + policy modes |
| **Self-Improvement** | `src/self_improvement_engine.py` | Feedback loops, calibration, remediation |
| **SLO Tracker** | `src/operational_slo_tracker.py` | Success rate, latency percentiles, SLO compliance |
| **Automation Scheduler** | `src/automation_scheduler.py` | Multi-project priority scheduling + load balancing |
| **Capability Map** | `src/capability_map.py` | AST-based module inventory, gap analysis, remediation |
| **Compliance Engine** | `src/compliance_engine.py` | GDPR/SOC2/HIPAA/PCI-DSS sensors, HITL approvals |
| **RBAC Governance** | `src/rbac_governance.py` | Multi-tenant RBAC, shadow agent governance |
| **Ticketing Adapter** | `src/ticketing_adapter.py` | ITSM lifecycle, remote access, patch/rollback |
| **Wingman Protocol** | `src/wingman_protocol.py` | Executor/validator pairing, deterministic validation |
| **Runtime Profile Compiler** | `src/runtime_profile_compiler.py` | Onboarding-to-profile, safety/autonomy controls |
| **Governance Kernel** | `src/governance_kernel.py` | Non-LLM enforcement, budget tracking, audit emission |
| **Control Plane Separation** | `src/control_plane_separation.py` | Planning/execution plane split, mode switching |
| **Durable Swarm Orchestrator** | `src/durable_swarm_orchestrator.py` | Budget-aware swarms, idempotency, circuit breaker |
| **Golden Path Bridge** | `src/golden_path_bridge.py` | Execution path capture, replay, similarity matching |
| **Org Chart Enforcement** | `src/org_chart_enforcement.py` | Role-bound permissions, escalation chains, cross-dept arbitration |
| **Shadow Agent Integration** | `src/shadow_agent_integration.py` | Shadow-agent org-chart parity, account/user controls |
| **Triage Rollcall Adapter** | `src/triage_rollcall_adapter.py` | Capability rollcall before swarm expansion, candidate ranking |
| **Rubix Evidence Adapter** | `src/rubix_evidence_adapter.py` | Deterministic evidence lane: CI, Bayesian, Monte Carlo, forecast |
| **Semantics Boundary Controller** | `src/semantics_boundary_controller.py` | Belief-state, risk/CVaR, RVoI questions, invariance, verification-feedback |
| **Bot Governance Policy Mapper** | `src/bot_governance_policy_mapper.py` | Legacy bot quota/budget/stability → Murphy runtime profiles |
| **Bot Telemetry Normalizer** | `src/bot_telemetry_normalizer.py` | Triage/rubix bot events → Murphy observability schema |
| **Legacy Compatibility Matrix** | `src/legacy_compatibility_matrix.py` | Legacy orchestration bridge hooks, migration paths, governance validation |
| **HITL Autonomy Controller** | `src/hitl_autonomy_controller.py` | HITL arming/disarming, confidence-gated autonomy, cooldown management |
| **Freelancer Validator** | `src/freelancer_validator/` | Freelance-platform HITL: Fiverr/Upwork adapters, org budgets, criteria scoring, credential verification |
| **Compliance Region Validator** | `src/compliance_region_validator.py` | Region-specific compliance validation, cross-border checks, data residency |
| **Observability Summary Counters** | `src/observability_counters.py` | Behavior fix vs coverage tracking, improvement velocity, closed-loop metrics |
| **Deterministic Routing Engine** | `src/deterministic_routing_engine.py` | Policy-driven deterministic/LLM/hybrid routing, fallback promotion, parity |
| **Platform Connector Framework** | `src/platform_connector_framework.py` | 20 platform connectors (Slack, Jira, Salesforce, GitHub, AWS, etc.) |
| **Workflow DAG Engine** | `src/workflow_dag_engine.py` | DAG workflows: topological sort, parallel groups, conditional branching |
| **Automation Type Registry** | `src/automation_type_registry.py` | 16 templates across 11 categories (IT, DevOps, marketing, etc.) |
| **API Gateway Adapter** | `src/api_gateway_adapter.py` | Rate limiting, auth, circuit breaker, caching, webhook dispatch |
| **Webhook Event Processor** | `src/webhook_event_processor.py` | 10 webhook sources, signature verification, event normalization |
| **Self-Automation Orchestrator** | `src/self_automation_orchestrator.py` | Prompt chain, task queue, gap analysis, AI collaborator mode |
| **Plugin/Extension SDK** | `src/plugin_extension_sdk.py` | Third-party plugin lifecycle, manifest validation, sandboxed execution |
| **AI Workflow Generator** | `src/ai_workflow_generator.py` | Natural language → DAG workflows, template matching, keyword inference |
| **Workflow Template Marketplace** | `src/workflow_template_marketplace.py` | Publish, search, install, rate community workflow templates |
| **Cross-Platform Data Sync** | `src/cross_platform_data_sync.py` | Bidirectional sync, field mapping, conflict resolution, change tracking |
| **Digital Asset Generator** | `src/digital_asset_generator.py` | Unreal/Maya/Blender/Fortnite/Unity/Godot asset pipelines, sprite sheets, texture atlases |
| **Rosetta Stone Heartbeat** | `src/rosetta_stone_heartbeat.py` | Executive-origin org-wide pulse propagation, tier translators, sync verification |
| **Content Creator Platform Modulator** | `src/content_creator_platform_modulator.py` | YouTube/Twitch/OnlyFans/TikTok/Patreon/Kick/Rumble connectors, cross-platform syndication |
| **ML Strategy Engine** | `src/ml_strategy_engine.py` | Anomaly detection, forecasting, classification, recommendation, clustering, Q-learning RL, A/B testing, ensemble, online learning |
| **Agentic API Provisioner** | `src/agentic_api_provisioner.py` | Self-provisioning API with OpenAPI spec generation, webhook management, module introspection, self-healing health monitoring |
| **Video Streaming Connector** | `src/video_streaming_connector.py` | Twitch/YouTube Live/OBS/vMix/Restream/StreamYard/Streamlabs/Kick Live/Facebook Live with simulcasting |
| **Remote Access Connector** | `src/remote_access_connector.py` | TeamViewer/AnyDesk/RDP/VNC/SSH/Parsec/Chrome Remote Desktop/Guacamole/Splashtop |
| **UI Testing Framework** | `src/ui_testing_framework.py` | 12 testing capabilities: visual regression, interactive components, E2E, performance, cross-browser, mobile gestures, dark mode, security, i18n |
| **Security Hardening Config** | `src/security_hardening_config.py` | Input sanitization (XSS/SQLi/path traversal), CORS lockdown, token-bucket rate limiting, CSP headers, API key rotation, audit logging, session security (MFA, concurrent limits) |
| **Authorization Enhancer** | `src/security_plane/authorization_enhancer.py` | Per-request ownership verification, session context enforcement, audit trail |
| **Log Sanitizer** | `src/security_plane/log_sanitizer.py` | PII detection (8 types), automated redaction, retroactive log sanitization |
| **Bot Resource Quotas** | `src/security_plane/bot_resource_quotas.py` | Per-bot quotas, swarm aggregate limits, auto-suspension |
| **Swarm Communication Monitor** | `src/security_plane/swarm_communication_monitor.py` | Message graph tracking, DFS cycle detection, rate limiting, pattern detection |
| **Bot Identity Verifier** | `src/security_plane/bot_identity_verifier.py` | HMAC-SHA256 signing, message verification, identity registry, key revocation |
| **Bot Anomaly Detector** | `src/security_plane/bot_anomaly_detector.py` | Z-score anomaly detection, resource spikes, API pattern analysis |
| **Security Dashboard** | `src/security_plane/security_dashboard.py` | Unified event view, correlation, compliance reports, escalation |

**Progress tracking:** All security enhancements are complete. All RFI items (`RFI-001`..`RFI-015`) have been resolved. See [SECURITY.md](SECURITY.md) for vulnerability reporting.

---

## 📊 What Can Murphy Do?

### 1\. Universal Automation

Murphy can automate **any business type** once the relevant integrations/adapters are configured:

| Type | Examples | Use Cases |
| --- | --- | --- |
| **Factory/IoT** | Sensors, actuators, HVAC, BACnet, Modbus, OPC UA | Temperature control, production lines, building automation |
| **Building Automation** | Johnson Controls, Honeywell, Siemens, Alerton, KNX, DALI | HVAC optimization, lighting, energy management |
| **Manufacturing** | ISA-95, MTConnect, PackML, MQTT/Sparkplug B, IEC 61131 | Production scheduling, PLC integration, quality management |
| **Energy Management** | OpenBlue, EcoStruxure, EnergyCAP, ENERGY STAR | Energy analytics, demand response, sustainability reporting |
| **Content** | Blog posts, social media | Publishing, marketing automation |
| **Creator Platforms** | YouTube, Twitch, OnlyFans, TikTok, Patreon, Kick, Rumble | Content scheduling, cross-platform syndication, monetization, analytics |
| **Messaging** | WhatsApp, Telegram, Signal, Snapchat, WeChat, LINE, KakaoTalk | Secure messaging, bot automation, group/channel management, payments |
| **Business Services** | ZenBusiness, Google Business Messages | Business formation, compliance, registered agent, business messaging |
| **Digital Assets** | Unreal Engine, Maya, Blender, Fortnite Creative, Unity, Godot | Game assets, sprite sheets, 3D models, texture atlases |
| **Data** | Databases, analytics | ETL, reporting, insights |
| **System** | Commands, DevOps | Infrastructure, deployments |
| **Agent** | Swarms, reasoning | Complex tasks, decision-making |
| **Business** | Sales, marketing, finance | Lead gen, content, invoicing |

### 2\. Self-Integration

Murphy can **add integrations automatically**:

```python
# Add Stripe integration
POST /api/integrations/add
{
    "source": "https://github.com/stripe/stripe-python",
    "category": "payment-processing"
}

# Murphy will:
# 1. Clone and analyze repository ✅
# 2. Extract capabilities ✅
# 3. Generate module/agent ✅
# 4. Test for safety ✅
# 5. Ask for approval (HITL) ✅
# 6. Load if approved ✅
```

**Result:** Integration time depends on repository size, dependencies, and safety review.

**Note:** Integration endpoints require optional dependencies and external credentials to run end-to-end.

### 3\. Self-Improvement

Murphy **learns from corrections**:

```python
# Submit correction
POST /api/corrections/submit
{
    "task_id": "abc123",
    "correction": "The correct output should be..."
}

# Murphy will:
# 1. Capture correction ✅
# 2. Extract patterns ✅
# 3. Train shadow agent ✅
# 4. Improve future performance ✅
```

**Result:** Designed to improve over time as corrections accumulate (measured results vary by workflow).

### 4\. Self-Operation

Murphy **runs Inoni LLC autonomously** via configurable automation templates:

| Engine | Capabilities | Notes |
| --- | --- | --- |
| **Sales** | Lead gen, qualification, outreach | Automated workflows included |
| **Marketing** | Content, social media, SEO | Content automation support |
| **R&D** | Bug detection, fixes, deployment | R&D automation hooks |
| **Business** | Finance, support, project mgmt | Workflow templates included |
| **Production** | Releases, QA, monitoring | Release/monitoring automation |

**The Meta-Case:** Murphy improves Murphy (R&D engine fixes Murphy's bugs automatically).

**Automation reality:** Runtime 1.0 can automate workflows once integrations, credentials, and adapters are configured. Out-of-the-box it provides orchestration, templates, and safety gates rather than full autonomous operation.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  MURPHY SYSTEM 1.0                          │
│              Universal Control Plane                        │
└─────────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
┌───────────────┐                  ┌──────────────┐
│ PHASE 1:      │                  │ PHASE 2:     │
│ Setup         │                  │ Execute      │
│ (Generative)  │                  │ (Production) │
└───────────────┘                  └──────────────┘
        ↓                                   ↓
┌─────────────────────────────────────────────────┐
│           MODULAR ENGINES                       │
│  Sensor | Actuator | Database | API | Content  │
│  Command | Agent | Compute | Reasoning         │
└─────────────────────────────────────────────────┘
        ↓
┌─────────────────────────────────────────────────┐
│           CORE SUBSYSTEMS                       │
│  Murphy Validation | Confidence Engine          │
│  Learning Engine | Supervisor System            │
│  HITL Monitor | Integration Engine              │
│  TrueSwarmSystem | Governance Framework         │
└─────────────────────────────────────────────────┘
```

---

## 📦 What's Included

### Complete System (~1,780 files in Murphy System)

| Component | Description | Files |
| --- | --- | --- |
| **Original Runtime** | Base Murphy system | Hundreds of Python files |
| **Phase 1-5** | Forms, validation, correction, learning | Dozens of files |
| **Control Plane** | Universal automation engine | 7 engines |
| **Business Automation** | Inoni self-operation | 5 engines |
| **Integration Engine** | GitHub ingestion with HITL | 6 components |
| **Orchestrator** | Two-phase execution | 1 file |
| **Final Runtime** | Complete system | 1 file |

### Documentation (10+ guides)

-   **MURPHY\_1.0\_QUICK\_START.md** - Get started in 5 minutes
-   **MURPHY\_SYSTEM\_1.0\_SPECIFICATION.md** - Complete specification
-   **INTEGRATION\_ENGINE\_COMPLETE.md** - Integration documentation
-   **API Documentation** - Interactive docs at /docs

---

## 🎯 Use Cases

### Use Case 1: Factory Automation

```bash
POST /api/execute
{
    "task_description": "Monitor temperature and adjust HVAC to maintain 72°F",
    "task_type": "automation"
}
```

### Use Case 2: Content Publishing

```bash
POST /api/automation/marketing/create_content
{
    "parameters": {
        "content_type": "blog_post",
        "topic": "AI Automation",
        "length": "1500 words"
    }
}
```

### Use Case 3: Sales Automation

```bash
POST /api/automation/sales/generate_leads
{
    "parameters": {
        "target_industry": "SaaS",
        "company_size": "10-50"
    }
}
```

### Use Case 4: Add Integration

```bash
POST /api/integrations/add
{
    "source": "https://github.com/stripe/stripe-python",
    "category": "payment-processing"
}
```

---

## 🛡️ Safety & Governance

### Security Hardening (Active)

-   ✅ Centralized auth on all API servers (`flask_security.py`, `fastapi_security.py`)
-   ✅ API key authentication on all routes (health endpoints exempt)
-   ✅ CORS origin allowlist (no wildcards) — `MURPHY_CORS_ORIGINS` env var
-   ✅ Rate limiting per client IP (token-bucket, 60 req/min default)
-   ✅ Security response headers (HSTS, CSP, X-Frame-Options, etc.)
-   ✅ Input sanitization (XSS, SQL injection, path traversal detection)
-   ✅ Tenant isolation in confidence engine (thread-safe per-tenant graphs)
-   ✅ IDOR protection on execution orchestrator (ownership checks on pause/resume/abort)
-   ✅ Input validation on execution orchestrator (authority level allowlist, safe ID patterns)
-   ✅ Environment-based debug mode (`MURPHY_ENV`, no hardcoded `debug=True`)

### Artifact Viewport (Content Inspection)

-   ✅ Range-based content inspection for artifacts, intake files, and deliverables
-   ✅ Content manifest with section index, line count, byte size, SHA-256 checksum
-   ✅ Head/tail/range/section projection modes (analogous to `view_range`)
-   ✅ Structured content key-path navigation with depth truncation
-   ✅ Content search with configurable context lines
-   ✅ Tenant-isolated access logging and audit trail
-   ✅ REST API: `/viewport/manifest`, `/viewport/project`, `/viewport/search`
-   ✅ Content resolver bridging MAS planes, Persistence Manager, and System Librarian

### Human-in-the-Loop (HITL)

-   ✅ Every integration requires approval
-   ✅ LLM-powered risk analysis
-   ✅ Clear recommendations
-   ✅ No automatic commits

### Murphy Validation

-   ✅ G/D/H Formula (Goodness, Domain, Hazard)
-   ✅ 5D Uncertainty (UD, UA, UI, UR, UG)
-   ✅ Murphy Gate (threshold validation)
-   ✅ Safety Score (0.0-1.0)

### Compliance

-   ✅ Includes GDPR-aligned controls (requires review)
-   ✅ Includes SOC 2 Type II-aligned controls (requires review)
-   ✅ Includes HIPAA-aligned controls (requires review)
-   ✅ Includes PCI DSS-aligned controls (requires review)

### Multi-Agent Security Enhancements

-   ✅ Per-request ownership verification with session context enforcement (`authorization_enhancer.py`)
-   ✅ PII detection and automated log sanitization — 8 pattern types (`log_sanitizer.py`)
-   ✅ Per-bot and per-swarm resource quotas with auto-suspension (`bot_resource_quotas.py`)
-   ✅ Swarm communication loop detection — DFS cycle detection, rate limiting (`swarm_communication_monitor.py`)
-   ✅ Cryptographic bot identity verification — HMAC-SHA256 signing and revocation (`bot_identity_verifier.py`)
-   ✅ Behavioral anomaly detection — z-score analysis, resource spikes, API patterns (`bot_anomaly_detector.py`)
-   ✅ Unified security dashboard with event correlation and compliance reporting (`security_dashboard.py`)

---

## 📈 Performance (Design Targets)

| Metric | Specification |
| --- | --- |
| **API Throughput** | Targeted 1,000+ req/s |
| **Task Execution** | Targeted 100+ tasks/s |
| **Integration Time** | Targeted <5 min per repo |
| **API Latency** | Targeted <100ms p95 |
| **Uptime Target** | 99.9% target |
| **Error Rate** | Targeted <1% |

---

## 🚀 Deployment

### Local Development

```bash
./start_murphy_1.0.sh
```

### Containers & Kubernetes (Legacy Examples)

Container and Kubernetes deployment manifests are available as legacy reference in the [murphy-system-archive](https://github.com/IKNOWINOT/murphy-system-archive) repository.

---

## 📚 Documentation

| Document | Description |
| --- | --- |
| [Quick Start](Murphy%20System/MURPHY_1.0_QUICK_START.md) | Get started in 5 minutes |
| [Specification](<Murphy System/MURPHY_SYSTEM_1.0_SPECIFICATION.md>) | Complete system spec |
| [API Documentation](<Murphy System/API_DOCUMENTATION.md>) | API reference |
| [Deployment Guide](<Murphy System/DEPLOYMENT_GUIDE.md>) | Deployment instructions |
| [User Manual](<Murphy System/USER_MANUAL.md>) | Comprehensive user manual |
| [Launch Automation Plan](<Murphy System/docs/LAUNCH_AUTOMATION_PLAN.md>) | Self-automating launch strategy |
| [Operations & Testing Plan](<Murphy System/docs/OPERATIONS_TESTING_PLAN.md>) | Iterative test-fix-document cycle |
| [Gap Analysis](<Murphy System/docs/GAP_ANALYSIS.md>) | System gap analysis and status |
| [API Docs](http://localhost:8000/docs) | Interactive API docs (requires running server) |
| [Archive](https://github.com/IKNOWINOT/murphy-system-archive) | Legacy versions and artifacts (separate repository) |

---

## 🧪 Testing

```bash
# Run tests (some suites require optional dependencies like pydantic, numpy, torch)
python -m pytest

# Run integration tests
pytest tests/integration/

# Run performance tests
k6 run tests/performance/load-test.js
```

---

## 🤝 Contributing

We welcome contributions! Please read:
- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Community standards
- [SECURITY.md](SECURITY.md) — Reporting vulnerabilities

---

## 📄 License

**Business Source License 1.1 (BSL 1.1)**

Copyright © 2025 Inoni Limited Liability Company  
Creator: Corey Post

The core Murphy System is licensed under BSL 1.1, which converts to Apache
License 2.0 after four years. You may freely use, modify, and redistribute
the software for any purpose except offering it as a competing hosted service.
Enterprise features are available under a separate commercial license.

See [LICENSE](LICENSE) for the full license text.

---

## 🆘 Support

### Community Support

-   GitHub Issues
-   Documentation
-   Examples

---

## 🎉 Success Stories

### Inoni LLC

**Murphy runs Inoni LLC (the company that makes Murphy)**

-   **Sales:** Lead generation automation workflows
-   **Marketing:** Content and campaign automation support
-   **R&D:** Bug triage and fix workflow automation
-   **Business:** Finance/support workflow automation
-   **Production:** Release and monitoring automation

**The Ultimate Proof:** The product IS the proof.

---

## 🗺️ Roadmap (TBD)

-   ✅ Security hardening — centralized auth, CORS, rate limiting, input validation
-   ✅ Artifact Viewport — range-based content inspection system
-   ✅ Tenant isolation — per-tenant memory planes, thread-safe graph managers
-   Multi-language support (JavaScript, Java, Go)
-   Enhanced shadow agent improvements
-   Integration marketplace
-   Advanced analytics
-   Real-time collaboration
-   Visual workflow builder
-   Mobile app
-   Enterprise features
-   Multi-tenant architecture
-   Global deployment

---

## 🌟 Why Murphy?

### vs Zapier (5,000+ integrations)

-   **Zapier:** Manual, weeks per integration
-   **Murphy:** Automatic, minutes per integration
-   **Advantage:** 100x faster

### vs Make/Integromat (1,500+ integrations)

-   **Make:** Manual, visual builder
-   **Murphy:** Code-based, automatic
-   **Advantage:** Developer-friendly

### vs n8n (400+ integrations)

-   **n8n:** Community-driven, days per integration
-   **Murphy:** AI-powered, minutes per integration
-   **Advantage:** No manual work

---

## 📊 Stats (Murphy System, as of 2026-03-05)

| Metric | Value |
| --- | --- |
| **Source Files** | 595 Python modules |
| **Source Lines** | 218,497 |
| **Classes** | 2,487 |
| **Functions / Methods** | 8,472 |
| **Packages** | 54 subsystem directories |
| **Test Files** | 371 |
| **Test Functions** | 8,843 |
| **Automation Types** | 6 (factory, content, data, system, agent, business) |
| **Gap-Closure Categories Audited** | 90 (all at zero) |

---

## 🧪 Test Status

The test suite is the primary quality gate for Murphy. Run it with:

```bash
cd "Murphy System"
python -m pytest tests/ -q --tb=short
```

**Latest verified results (2026-03-05):**

| Metric | Count |
| --- | --- |
| Test files | 371 |
| Test functions | 8,843 |
| Gap-closure tests | 406 (rounds 3–42) |

**Skipped tests** require optional dependencies (Flask, Textual, torch) that are
not part of the core FastAPI-based system. Install them with `pip install flask
flask-cors textual torch` if you want full coverage.

**Known collection error:** `test_fastapi_rate_limiter_cleanup.py` requires
`fastapi` — install with `pip install fastapi` to include it.

---

## 🔧 Self-Healing & Patch Capabilities

Murphy includes built-in self-improvement infrastructure:

| Component | Module | What It Does |
| --- | --- | --- |
| **Bug Pattern Detector** | `src/bug_pattern_detector.py` | Analyzes error logs to classify recurring failure patterns |
| **Self-Improvement Engine** | `src/self_improvement_engine.py` | Extracts lessons from corrections, calibrates confidence scores |
| **Correction Loop** | `src/learning_engine/` | Shadow agent training pipeline that learns from human overrides |
| **Self-Healing Coordinator** | `src/self_healing_coordinator.py` | Coordinates automated remediation across subsystems |
| **Synthetic Failure Generator** | `src/synthetic_failure_generator/` | Creates controlled failures to test recovery paths |

**Can Murphy fix itself?** Partially. The self-improvement engine can:
- ✅ Detect recurring error patterns and suggest fixes
- ✅ Learn from human corrections and adjust behavior
- ✅ Auto-calibrate confidence thresholds based on outcomes
- ✅ Process patch requests through the correction loop
- ⚠️ Cannot yet auto-generate and apply code patches without human review
- ⚠️ Complex emergent bugs require manual diagnosis

File an issue or submit a patch — Murphy's learning loop will incorporate the
feedback into its operational models.

---

## 🎯 Get Started Now

```bash
# 1. Clone
git clone https://github.com/IKNOWINOT/Murphy-System.git

# 2. Start
cd Murphy-System/Murphy\ System
./start_murphy_1.0.sh

# 3. Use
curl http://localhost:8000/api/status
```

**Welcome to the future of AI automation!** 🚀

---

##  Contact

-   **Email:** corey.gfc@gmail.com


---

**Murphy System 1.0 - Automate Everything** ™
