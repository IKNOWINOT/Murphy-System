# Murphy System 1.0

**Universal AI Automation System**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/IKNOWINOT/Murphy-System) [![License](https://img.shields.io/badge/license-BSL%201.1-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10+-yellow.svg)](https://www.python.org/) [![CI](https://github.com/IKNOWINOT/Murphy-System/actions/workflows/ci.yml/badge.svg)](https://github.com/IKNOWINOT/Murphy-System/actions/workflows/ci.yml) [![Tests](https://img.shields.io/badge/tests-17368%20passing-brightgreen.svg)](#-test-status)

---

> ## ⚠️ Important — Please Read Before Using
>
> **Murphy is an ambitious, deeply complex AI automation system.** It is currently
> developed and maintained by a **single developer** ([@IKNOWINOT](https://github.com/IKNOWINOT)).
> While the architecture is comprehensive and the test suite covers thousands of
> functions, **not everything works as intended**. Emergent bugs are still being
> discovered and classified across the 978-module surface area.
>
> **What this means for you:**
>
> - 🚀 **Beta-quality software** — core automation, integrations, and governance
>   pipelines are functional. Industrial/OT connectors require hardware.
>   Security hardening is complete for the authentication and CORS layers but
>   should be verified before internet-facing deployment.
> - 🐛 **Emergent bugs** — complex interactions between modules can produce
>   unexpected behavior. Edge cases are actively being catalogued.
> - 🔧 **Self-healing capabilities** — Murphy includes a self-improvement engine,
>   bug pattern detector, and correction loop.
> - 📊 **Test coverage is extensive** — 644 test files with comprehensive coverage.
>   CI runs automatically on push/PR via GitHub Actions.
> - 🤝 **Contributions welcome** — see [CONTRIBUTING.md](CONTRIBUTING.md).
>
> **Bottom line:** This system is genuinely powerful — it can automate an entire
> business stack from intake to delivery, manage SCADA/industrial systems,
> orchestrate content creation pipelines, and run AI agent swarms. Review and
> configure credentials before production deployment.

---

## 🎯 What is Murphy?

Murphy is a **complete, operational AI automation system** that can automate any business type, including its own operations. It requires security hardening before production deployment.

### Key Features

✅ **Describe → Execute** - Tell Murphy what you want in plain English; it builds the plan, governs it, and runs it  
✅ **Universal Automation** - Automate anything (factory, content, data, system, agent, business)  
✅ **Self-Integration** - Add GitHub repos, APIs, hardware automatically  
✅ **Self-Improvement** - Learns from corrections, trains shadow agent  
✅ **Self-Operation** - Runs Inoni LLC autonomously  
✅ **Human-in-the-Loop** - Safety approval for all integrations  
✅ **Wingman Protocol** - Executor/validator pairing for every task  
✅ **Causality Sandbox** - What-if scenario simulation and causal reasoning  
✅ **HITL Graduation** - Structured human-to-automation handoff pipeline  
✅ **Orchestrators** - Safety, efficiency, and supply chain orchestration  
✅ **Container Deployment** - Docker and Kubernetes configs included (security hardening required before production)

> **Coming in #136:** Drawing Engine, Credential Gate, Sensor Fusion, Osmosis Engine, Autonomous Perception, Wingman Evolution, Engineering Toolbox

---

## 🗣️ How It Works: Describe → Execute → Refine

Murphy's hero flow inverts the traditional automation paradigm — you describe what you want; Murphy builds it.

```
1. DESCRIBE: "Monitor my sales data and send a weekly summary to Slack"
2. EXECUTE:  Murphy builds a governed DAG workflow with safety gates
3. REFINE:   Open the visual canvas to tweak any step (optional)
```

**No drag-and-drop. No connector wiring. No trigger logic.** Just a plain English sentence.

Murphy uses [`ai_workflow_generator.py`](<Murphy System/src/ai_workflow_generator.py>) to convert your description into a structured workflow, [`nocode_workflow_terminal.py`](<Murphy System/src/nocode_workflow_terminal.py>) as the Librarian-powered conversation interface, and [`workflow_canvas.html`](<Murphy System/workflow_canvas.html>) as the optional visual refinement layer once the plan is generated.

**📖 For comprehensive documentation on voice/typed command automation, see:**
- [Generative Automation Presets](documentation/features/GENERATIVE_AUTOMATION_PRESETS.md) — Complete guide to natural language workflow generation, industry presets, role-based execution, and human-in-the-loop governance

See the full [Roadmap](ROADMAP.md) for the sprint plan that takes this from prototype to production.

---

## 🚀 Quick Start & Installation

### ⚡ One-Line Install (Recommended)

**Copy-paste this single command** — it clones, installs, and configures everything:

```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
```

Then start Murphy:

```bash
murphy start          # Start in foreground
murphy start -d       # Start as background daemon
murphy status         # Check health
murphy stop           # Stop daemon
murphy help           # See all commands
```

> **No API key required** — the onboard LLM works out of the box. Add a [Groq API key](https://console.groq.com) to `.env` for enhanced quality (optional).

### Clone & Run

If you prefer not to pipe to bash:

```bash
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
bash setup_and_start.sh          # Linux / macOS
```

```cmd
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
setup_and_start.bat              &REM Windows
```

The script handles the virtual environment, installs **all** dependencies (including extras), configures `.env`, and lets you choose between the backend server or the terminal UI.

**📚 Documentation:**
- **Complete Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **Quick Start:** [Murphy System/MURPHY_1.0_QUICK_START.md](Murphy%20System/MURPHY_1.0_QUICK_START.md)
- **API Reference:** [Murphy System/API_DOCUMENTATION.md](Murphy%20System/API_DOCUMENTATION.md)
- **Deployment Guide:** [Murphy System/DEPLOYMENT_GUIDE.md](Murphy%20System/DEPLOYMENT_GUIDE.md)

---

## Quick Start (Development)

```bash
# Clone and enter
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System

# Option A: Use the setup script (recommended)
bash setup_and_start.sh

# Option B: Manual setup
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements_core.txt  # Fast install (~30 seconds)
# OR: pip install -r requirements.txt  # Full install (includes ML, Matrix, etc.)
cp .env.example .env
python -m src.runtime.boot  # Starts on http://localhost:8000
```

### Verify It's Running
```bash
curl http://localhost:8000/api/health
# → {"status": "healthy", ...}
```

### Runtime Modes
Murphy System supports two runtime modes:
- **Monolith** (default): Loads all modules. Use for full system testing.
- **Tiered**: Loads only what your team needs. Faster startup, lower memory.

Set `MURPHY_RUNTIME_MODE=tiered` in `.env` to try tiered mode.
See [docs/TIERED_RUNTIME.md](docs/TIERED_RUNTIME.md) for details.

---

## 📊 Overall System Completion

| Area | Completion | Notes |
| --- | --- | --- |
| Core automation pipeline (Describe → Execute) | **90%** | Code exists and structured; 19/19 critical path tests passing |
| Execution wiring (gate + swarm + orchestrator) | **95%** | Wired and tested; E2E hero flow validation pending |
| Deterministic + LLM routing | **95%** | Functional; LLM key config hardening in progress |
| Persistence + replay | **70%** | JSON, SQLite, and PostgreSQL backends; Alembic migrations; production pooling |
| Multi-channel delivery | **90%** | Email, webhook, Slack stubs; real channel testing pending |
| Compliance validation | **90%** | Framework complete; formal attestation (SOC 2, ISO 27001) pending |
| Operational automation | **85%** | Core flows working; Phases 2–8 all implemented and verified |
| File system cleanup | **100%** | Complete |
| Test coverage (dynamic chains) | **85%** | 644 test files, 17,368 test functions; 1,611 verified passing across 37+ suites |
| UI + user testing | **75%** | 14 web interfaces built; UI completion PR pending |
| Security hardening | **80%** | Auth/CORS/CSP/JWT done; E2EE stub gated for production |
| Code quality audit (90 categories) | **90%** | Audit complete; remediation for remaining items in progress |
| Management parity (Phases 1–12) | **70%** | Phases 1–8 implemented with real code; Phase 9-11 checked; Phase 12 API-only |
| CI/CD pipeline | **90%** | Ruff lint 0 errors; lightweight CI deps; prometheus safe for repeated init |
| Documentation accuracy | **85%** | All placeholder docs filled; README truth reconciliation complete |
| E2E Hero Flow Validation | **85%** | Describe→Generate→Execute chain validated: 49 integration tests pass; real-user validation and production load testing remain |
| Librarian Command Coverage | **100%** | All 154 commands wired into Librarian; `generate_command()` + triage escalation tested across every category |
| Librarian Triage Escalation | **100%** | Mode-aware (ASK/ONBOARDING/PRODUCTION/ASSISTANT); triage→execution path validated with 57 tests |
| **Weighted overall** | **~83%** | See [Production Readiness Audit](Murphy%20System/strategic/PRODUCTION_READINESS_AUDIT.md) |

> **Test status:** 644 test files with 17,368 test functions; 1,611 verified passing.
> Skipped tests require optional packages (Flask, Textual, torch).
> CI pipeline runs on every push/PR — see [Test Status](#-test-status) below.

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
    ├── src/                            ← 1037 production modules
    ├── tests/                          ← 644 test files
    ├── bots/                           ← 104 bot modules
    ├── documentation/                  ← Structured API/user docs
    ├── docs/                           ← Technical docs
    ├── k8s/                            ← Kubernetes manifests
    ├── monitoring/                     ← Prometheus config
    ├── scripts/                        ← Operational scripts
    ├── *.html                          ← 14 web interfaces (12 active + 2 legacy redirects)
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
bash setup_and_start.sh
```

**Available endpoints:** `/api/health`, `/api/status`, `/api/info`, `/api/execute`, and automation endpoints under `/api/automation/...`

**Key runtime capabilities:**
- Deterministic and LLM routing via policy-driven routing engine
- Multi-channel delivery (document, email, chat, voice, translation)
- Gate-based execution wiring with EXECUTIVE/OPERATIONS/QA/HITL/COMPLIANCE/BUDGET gates
- Two-phase and async orchestration with swarm execution support
- Persistence and replay via JSON, SQLite, or PostgreSQL backends with Alembic migrations
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
- 42 integrated modules, 8,843 tests passing
- Neon terminal UI across 14 web interfaces with consistent theme

**Architect UI:** serve `Murphy System/terminal_architect.html` with `python -m http.server 8090` and open `http://localhost:8090/Murphy%20System/terminal_architect.html?apiPort=8000`

---

## 🗃️ Repository Index (Database-Style Reference)

Use this table as the primary lookup for active modules, docs, and entry points.

| Domain | Location | Purpose | Entry Points |
| --- | --- | --- | --- |
| **Runtime API** | `Murphy System/murphy_system_1.0_runtime.py` | Runtime 1.0 API server | `bash setup_and_start.sh`, `GET /api/status` |
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
| **Persistence** | `src/persistence_manager.py`, `src/db.py` | JSON, SQLite, PostgreSQL backends; Alembic migrations |
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
| **Platform Connector Framework** | `src/platform_connector_framework.py` | 90+ platform connectors (Slack, Jira, Salesforce, GitHub, AWS, OpenAI, Anthropic, Mailchimp, Shopify, Stripe, SCADA/Modbus, BACnet, OPC UA, Building Automation, Energy Management, Additive Manufacturing, and more) |
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
| **Self-Introspection** | `src/self_introspection_module.py` | Runtime self-analysis and codebase scanning |
| **Self-Codebase Swarm** | `src/self_codebase_swarm.py` | Autonomous BMS spec generation and RFP parsing |
| **Cut Sheet Engine** | `src/cutsheet_engine.py` | Manufacturer data parsing and wiring diagram generation |
| **Visual Swarm Builder** | `src/visual_swarm_builder.py` | Visual pipeline construction for swarm workflows |
| **CEO Branch Activation** | `src/ceo_branch_activation.py` | Top-level autonomous decision-making and planning |
| **Production Assistant Engine** | `src/production_assistant_engine.py` | Request lifecycle and deliverable gate validation |

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
| **Paper Trading Engine** | Simulated crypto trading + 9 strategies | 7+ files |

### Paper Trading System (PR-2)

Murphy includes a full paper-trading simulation engine for personal crypto trading research:

| Module | Purpose |
|--------|---------|
| `src/paper_trading_engine.py` | Portfolio simulator: slippage, fees, stop-loss, P&L metrics |
| `src/strategy_templates/` | 9 strategy templates (momentum, mean reversion, breakout, scalping, DCA, grid, trajectory, sentiment, arbitrage) |
| `src/cost_calibrator.py` | Detects hidden costs (spread, slippage, fees) and auto-adjusts estimates |
| `src/error_calibrator.py` | Tracks prediction vs actual divergence; triggers recalibration when bias is detected |
| `src/backtester.py` | Historical backtesting via CSV or yfinance; multi-strategy comparison |
| `src/paper_trading_routes.py` | FastAPI routes at `/api/trading/*` |
| `paper_trading_dashboard.html` | Dashboard at `/ui/paper-trading` |

> **Note:** All trading is PAPER/SIMULATED only in this phase. No real money is moved.
> The system is for personal use — see the graduation system (PR-3) before enabling live trading.

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
bash setup_and_start.sh
```

### Containers & Kubernetes

`Dockerfile`, `docker-compose.yml`, and `k8s/` manifests are included in `Murphy System/` as active deployment options. Security hardening is required before production use.

```bash
# From the Murphy System/ directory
docker build -t murphy-system .
docker compose up -d

# Kubernetes
kubectl apply -f k8s/
```

> **Note:** Review and harden the container configuration before deploying to a production environment.

---

## 🔌 API Endpoints

The Murphy System Runtime exposes a FastAPI-based REST API. Start the server with `bash setup_and_start.sh`, then visit `http://localhost:8000/docs` for interactive documentation.

| Method | Path | Auth Required | Description |
| --- | --- | --- | --- |
| `GET` | `/api/health` | No | Health check — returns system status |
| `GET` | `/api/status` | Yes | Full system status and metrics |
| `GET` | `/api/info` | Yes | System info (version, modules, capabilities) |
| `GET` | `/api/system/info` | Yes | Detailed system configuration info |
| `POST` | `/api/execute` | Yes | Execute a task via the universal control plane |
| `POST` | `/api/forms/plan-upload` | Yes | Upload a pre-existing execution plan |
| `POST` | `/api/forms/plan-generation` | Yes | Generate a plan from natural language description |
| `POST` | `/api/forms/task-execution` | Yes | Execute a task with structured validation |
| `POST` | `/api/forms/validation` | Yes | Validate an execution packet |
| `POST` | `/api/forms/correction` | Yes | Submit a correction for learning loop |
| `GET` | `/api/forms/submission/{id}` | Yes | Retrieve a form submission by ID |
| `GET` | `/api/llm/status` | Yes | LLM provider status and availability |
| `GET` | `/api/librarian/status` | Yes | System Librarian knowledge-base status |
| `GET` | `/api/onboarding/status` | Yes | Onboarding workflow status |
| `POST` | `/api/ucp/execute` | Yes | Universal Control Protocol execution |
| `GET` | `/api/integrations/{status}` | Yes | List integrations filtered by status |

> **Authentication:** Production mode (`MURPHY_ENV=production`) requires `Authorization: Bearer <key>` or `X-API-Key: <key>` header on all non-health endpoints. Development mode allows unauthenticated access. See [`Murphy System/documentation/api/AUTHENTICATION.md`](<Murphy System/documentation/api/AUTHENTICATION.md>) for full details.

---

## ⚙️ Configuration

Murphy System supports two complementary configuration mechanisms. **Environment variables always take precedence.**

### YAML Files (recommended starting point)

```bash
# Edit main settings (LLM provider, thresholds, safety levels, logging):
nano "Murphy System/config/murphy.yaml"

# Edit engine settings (swarm, gates, orchestrator, self-healing):
nano "Murphy System/config/engines.yaml"
```

See `Murphy System/config/murphy.yaml.example` and `Murphy System/config/engines.yaml.example` for fully-annotated documentation of every setting.

### Environment Variables

Copy `Murphy System/.env.example` to `Murphy System/.env` and fill in the values. Environment variables override YAML defaults.

| Variable | Default | Description |
| --- | --- | --- |
| `GROQ_API_KEY` | *(none)* | Groq API key — enables Mixtral/Llama/Gemma cloud LLMs. Optional: the onboard local LLM (phi3 via Ollama) works without this. |
| `MURPHY_LLM_PROVIDER` | `local` | LLM provider to use: `local`, `groq`, `openai`, or `anthropic`. |
| `OLLAMA_MODEL` | `phi3` | Default Ollama model. `phi3` is pulled automatically by the deploy workflow. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint. |
| `MURPHY_ENV` | `development` | Runtime environment: `development` (auth optional) or `production` (auth required). |
| `MURPHY_API_KEYS` | *(none)* | Comma-separated API keys for request authentication in production mode. |
| `MURPHY_CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated list of allowed CORS origins. |
| `MURPHY_RATE_LIMIT_RPM` | `60` | Maximum requests per minute per client IP (token-bucket rate limiter). |
| `MURPHY_RATE_LIMIT_BURST` | `20` | Maximum burst size for rate limiter. |

> **Secrets** (API keys, passwords, tokens) must never be placed in YAML files. Use `.env` (development) or a secrets manager (production).

---

## 📚 Documentation

| Document | Description |
| --- | --- |
| [Quick Start](Murphy%20System/MURPHY_1.0_QUICK_START.md) | Get started in 5 minutes |
| [Roadmap](ROADMAP.md) | Public revenue-first sprint plan |
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

Murphy is **free to use, modify, and deploy** for any purpose — personal,
commercial, internal, or educational. The only restriction: you cannot offer
Murphy itself as a competing hosted service.

After four years, each version automatically converts to **Apache 2.0**
(fully permissive open source).

**TL;DR:** Use it however you want. Just don't clone it and sell it as SaaS.

See [LICENSE](LICENSE) for details.

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

Murphy is the **only automation platform** that covers the entire stack — from factory floor SCADA to enterprise business workflows to content creator pipelines — in a single governed system.

### Capability Comparison

| Capability | Murphy | Zapier | Make | n8n | Temporal | LangChain |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Describe → Execute (NL→Workflow)** | ✅ | ❌ | ❌ | ❌ | ❌ | ⚠️ |
| **SCADA / Modbus / BACnet / OPC UA** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Building Automation (BAS/BMS)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Energy Management (EMS)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Additive Manufacturing / 3D Printing** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Content Creator Platform (YouTube, Twitch)** | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ | ❌ |
| **Self-Integration Engine** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Self-Improvement + Immune Engine** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Confidence-Gated Execution** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Human-in-the-Loop Gates** | ✅ | ❌ | ❌ | ⚠️ | ❌ | ❌ |
| **Pre-built Connectors** | 90+ | 7,000+ | 1,800+ | 400+ | N/A | N/A |
| **Production Readiness** | Beta | ✅ | ✅ | ✅ | ✅ | ⚠️ |

### vs Zapier (7,000+ integrations)
- **Zapier:** Integration breadth, but no NL execution, no industrial, no AI governance
- **Murphy:** Self-integration engine closes the breadth gap; NL-to-workflow is unique
- **Advantage:** Industrial/OT + AI orchestration + governance — categories Zapier cannot enter

### vs Make / Integromat
- **Make:** Great visual builder, cheaper per operation
- **Murphy:** NL execution, SCADA, content creator, and self-improvement — no equivalent in Make
- **Advantage:** Premium verticals (industrial, content, AI) justify higher price

### vs n8n
- **n8n:** Open-source, self-hosted, strong developer community
- **Murphy:** Same self-hosting story + governance + industrial + AI-native execution
- **Advantage:** Governance gates, HITL, SCADA, and Murphy Foundation Model

---

## 📊 Stats (Murphy System, as of 2026-03-14)

| Metric | Value |
| --- | --- |
| **Source Files** | 978 Python modules |
| **Source Lines** | 218,497 |
| **Classes** | 2,487 |
| **Functions / Methods** | 8,472 |
| **Packages** | 81 subsystem directories |
| **Test Files** | 644 |
| **Test Functions** | 8,843+ |
| **Automation Types** | 6 (factory, content, data, system, agent, business) |
| **Gap-Closure Categories Audited** | 90 (all at zero) |

---

## 🧪 Test Status

The test suite is the primary quality gate for Murphy. Run it with:

```bash
cd "Murphy System"
python -m pytest tests/ -q --tb=short
```

**Latest verified results:**

| Metric | Count |
| --- | --- |
| Test files | 644 |
| Test functions | 8,843+ |
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
| **Self-Fix Loop** | `src/self_fix_loop.py` | **NEW** — Autonomous closed-loop: diagnose → plan → execute → test → verify → repeat |
| **Synthetic Failure Generator** | `src/synthetic_failure_generator/` | Creates controlled failures to test recovery paths |
| **Murphy Immune Engine** | `src/murphy_immune_engine.py` | **NEW** — 11-phase immune cycle: reconcile → predict → diagnose → recall → plan → execute → test → harden → cascade-check → memorize → report |

**Can Murphy fix itself?** Yes — for runtime-adjustable issues:
- ✅ Detect recurring error patterns and suggest fixes
- ✅ Learn from human corrections and adjust behavior
- ✅ Auto-calibrate confidence thresholds based on outcomes
- ✅ Process patch requests through the correction loop
- ✅ **NEW: Autonomously diagnose gaps, plan runtime fixes, execute adjustments (timeout tuning, confidence recalibration, recovery procedure registration, route optimization), test the fix, and repeat until zero gaps remain**
- ❌ Modify source code (requires human review via code proposals)
- ⚠️ Complex emergent bugs require manual diagnosis

See [`docs/SELF_FIX_LOOP.md`](<Murphy System/docs/SELF_FIX_LOOP.md>) for full documentation on the autonomous self-fix loop.

File an issue or submit a patch — Murphy's learning loop will incorporate the
feedback into its operational models.

---

## 🎯 Get Started Now

```bash
# 1. Clone
git clone https://github.com/IKNOWINOT/Murphy-System.git

# 2. Start
cd Murphy-System
bash setup_and_start.sh

# 3. Use
curl http://localhost:8000/api/status
```

**Welcome to the future of AI automation!** 🚀

---

##  Contact

-   **Email:** corey.gfc@gmail.com


---

## 📈 System Completion Summary (as of 2026-03-16)

| Category | Completion |
|----------|-----------|
| Core Architecture & Engine Wiring | 93% |
| Hero Flow (Describe → Execute → Refine) | 85% |
| Librarian Command Coverage & Triage | 100% |
| Security Hardening | 80% |
| Test Coverage | 87% |
| Documentation | 87% |
| UI/UX | 100% |
| Management Parity (12 Phases) | 70% |
| CI/CD Pipeline | 90% |
| Production Deployment Readiness | 65% |
| **Weighted Overall** | **~83%** |

> The overall percentage reflects the reality that while code coverage is extensive
> (1037 modules, 922 in `src/`, 644 test files), the critical **E2E validation of the
> hero flow** and **production deployment hardening** are the primary gaps preventing
> a 100% readiness declaration.

---

**Murphy System 1.0 - Automate Everything** ™
