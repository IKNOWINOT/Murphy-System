# Murphy System 1.0 — User Manual

**Universal AI Automation System**
**Version:** 1.0 | **Publisher:** Inoni LLC | **Creator:** Corey Post
**License:** BSL 1.1 (converts to Apache 2.0 after 4 years)

---

## Table of Contents

1. [Getting Started](#chapter-1-getting-started)
2. [Task Execution](#chapter-2-task-execution)
3. [Automation Types](#chapter-3-automation-types)
4. [Self-Integration](#chapter-4-self-integration)
5. [Self-Improvement & Learning](#chapter-5-self-improvement--learning)
6. [Confidence Engine & Validation](#chapter-6-confidence-engine--validation)
7. [Security & Governance](#chapter-7-security--governance)
8. [Robotics Integration](#chapter-8-robotics-integration)
9. [Avatar Identity Layer](#chapter-9-avatar-identity-layer)
10. [Rosetta State Management](#chapter-10-rosetta-state-management)
11. [Gate Synthesis & Failure Prevention](#chapter-11-gate-synthesis--failure-prevention)
12. [Execution Orchestrator](#chapter-12-execution-orchestrator)
13. [Monitoring & Analytics](#chapter-13-monitoring--analytics)
14. [Bot System](#chapter-14-bot-system)
15. [UI Interfaces](#chapter-15-ui-interfaces)
16. [Deployment](#chapter-16-deployment)
17. [API Reference](#chapter-17-api-reference)
18. [Troubleshooting](#chapter-18-troubleshooting)
19. [Business Model](#chapter-19-business-model)
20. [No-Code Workflow Builder](#chapter-20-no-code-workflow-builder)
21. [Onboarding & Org Chart](#chapter-21-onboarding--org-chart)
22. [IP Classification & Trade Secrets](#chapter-22-ip-classification--trade-secrets)
23. [Credential Profiles & Automation Metrics](#chapter-23-credential-profiles--automation-metrics)
24. [Agent Monitor Dashboard](#chapter-24-agent-monitor-dashboard)
25. [Complete User Journey](#chapter-25-complete-user-journey)

---

## Chapter 1: Getting Started

### 1.1 Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| pip | Latest |
| OS | Linux, macOS, or Windows |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | 2 GB free space |

### 1.2 Installation

**⚡ One-Line Install (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
```

This single command clones the repo, sets up a virtual environment, installs dependencies, and configures Murphy. Then start with `murphy start`.

**Clone & run:**

```bash
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System
bash setup_and_start.sh
```

**Manual setup:**

```bash
cd "Murphy System"
pip install -r requirements_murphy_1.0.txt
python murphy_system_1.0_runtime.py
```

**Windows:**

```bat
cd "Murphy System"
setup_murphy.bat
```

### 1.3 Quick Start

```bash
# Linux / macOS
chmod +x start_murphy_1.0.sh
./start_murphy_1.0.sh

# Windows
start_murphy_1.0.bat
```

The system starts on **port 8000** by default. Verify with:

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0",
  "uptime_seconds": 12.5
}
```

### 1.4 Accessing the System

| Access Method | URL / Command |
|---------------|--------------|
| REST API | `http://localhost:8000/api/` |
| Landing Page | `http://localhost:8000/` (murphy_landing_page.html) |
| Integrated Dashboard | `http://localhost:8000/dashboard` |
| Terminal UI | `http://localhost:8000/terminal` |

### 1.5 Configuration

Configuration is managed via environment variables or `src/config.py` (Pydantic BaseSettings):

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_HOST` | `127.0.0.1` | API bind address (use 0.0.0.0 to expose externally) |
| `MURPHY_PORT` | `8000` | API port |
| `MURPHY_DB_PATH` | `murphy.db` | SQLite database path |
| `MURPHY_LLM_PROVIDER` | `deepinfra` | LLM provider (deepinfra, openai, local) |
| `DEEPINFRA_API_KEY` | — | DeepInfra API key |
| `OPENAI_API_KEY` | — | OpenAI API key |

---

## Chapter 2: Task Execution

### 2.1 Submitting Tasks

Send any task to Murphy via the execute endpoint:

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Generate a quarterly sales report",
    "context": {"quarter": "Q4", "year": 2024},
    "priority": "high"
  }'
```

Response:

```json
{
  "execution_id": "exec-a1b2c3",
  "status": "running",
  "confidence": 0.87,
  "estimated_completion": "2024-12-01T10:05:00Z"
}
```

### 2.2 Plan Upload

Upload a pre-defined execution plan:

```bash
curl -X POST http://localhost:8000/api/forms/plan-upload \
  -H "Content-Type: application/json" \
  -d '{
    "plan_name": "weekly-etl",
    "steps": [
      {"action": "extract", "source": "postgres://db/sales"},
      {"action": "transform", "rules": ["deduplicate", "normalize"]},
      {"action": "load", "target": "warehouse"}
    ]
  }'
```

### 2.3 Plan Generation from Natural Language

Let Murphy generate a plan from a description:

```bash
curl -X POST http://localhost:8000/api/forms/plan-generation \
  -d '{"description": "Set up a CI/CD pipeline for our Python microservice"}'
```

### 2.4 Task Execution with Validation

Submit a task with built-in validation checks:

```bash
curl -X POST http://localhost:8000/api/forms/task-execution \
  -d '{
    "task": "Deploy staging environment",
    "validation": {
      "require_approval": true,
      "confidence_threshold": 0.85,
      "dry_run": false
    }
  }'
```

### 2.5 Monitoring Execution

```bash
# Check execution status
curl http://localhost:8000/api/status?execution_id=exec-a1b2c3

# List all active executions
curl http://localhost:8000/api/status
```

---

## Chapter 3: Automation Types

Murphy supports six automation domains, each handled by the Universal Control Plane's modular engines.

### 3.1 Automation Domain Matrix

| Domain | Engine | Use Cases | Example |
|--------|--------|-----------|---------|
| **Factory/IoT** | Sensor + Actuator | HVAC, robotics, PLC control | Read temperature, toggle valve |
| **Content** | Content Engine | Blog posts, social media, docs | Generate weekly newsletter |
| **Data** | Database Engine | ETL, analytics, migrations | Run nightly data pipeline |
| **System** | Command Engine | Shell commands, DevOps, infra | Restart service, scale pods |
| **Agent** | Agent Engine | AI swarms, complex reasoning | Multi-agent research task |
| **Business** | Inoni Business Suite | Sales, marketing, finance | Generate invoice, run campaign |

### 3.2 Factory/IoT Automation

```bash
curl -X POST http://localhost:8000/api/automation/sensor/read \
  -d '{"sensor_id": "temp-floor-3", "protocol": "modbus"}'

curl -X POST http://localhost:8000/api/automation/actuator/execute \
  -d '{"actuator_id": "valve-07", "command": "open", "parameters": {"percent": 75}}'
```

### 3.3 Content Automation

```bash
curl -X POST http://localhost:8000/api/automation/content/generate \
  -d '{
    "type": "blog_post",
    "topic": "AI in Manufacturing",
    "tone": "professional",
    "word_count": 1200
  }'
```

### 3.4 Data Automation

```bash
curl -X POST http://localhost:8000/api/automation/database/query \
  -d '{"query": "SELECT * FROM orders WHERE status = ?", "params": ["pending"]}'
```

### 3.5 System Automation

```bash
curl -X POST http://localhost:8000/api/automation/command/execute \
  -d '{"command": "systemctl restart nginx", "require_approval": true}'
```

### 3.6 Agent Automation (Swarm)

```bash
curl -X POST http://localhost:8000/api/automation/agent/swarm \
  -d '{
    "objective": "Research competitor pricing strategies",
    "agent_count": 3,
    "coordination": "collaborative"
  }'
```

### 3.7 Business Automation (Inoni Suite)

The Inoni Business Automation layer contains five engines:

| Engine | Capabilities |
|--------|-------------|
| **Sales** | Lead scoring, pipeline management, quote generation |
| **Marketing** | Campaign automation, content calendar, analytics |
| **R&D** | Experiment tracking, patent research, prototyping |
| **Business Management** | Financial reporting, compliance, HR workflows |
| **Production Management** | Scheduling, quality control, inventory |

```bash
curl -X POST http://localhost:8000/api/automation/sales/score-lead \
  -d '{"company": "Acme Corp", "contact": "jane@acme.com", "signals": ["demo_request"]}'
```

---

## Chapter 4: Self-Integration

Murphy can integrate external tools and repositories autonomously using the SwissKiss analysis workflow.

### 4.1 Integration Workflow

```
Repository URL → SwissKiss Analysis → Capability Extraction
    → Module/Agent Generation → Safety Testing → HITL Approval → Live Integration
```

### 4.2 Adding a GitHub Integration

```bash
curl -X POST http://localhost:8000/api/integrations/add \
  -d '{
    "repository_url": "https://github.com/org/repo",
    "integration_type": "github",
    "auto_analyze": true
  }'
```

### 4.3 SwissKiss Analysis

SwissKiss analyzes the repository to extract capabilities, assess risk, and generate integration modules.

**Capability types extracted (30+):**

| Category | Examples |
|----------|----------|
| API | REST endpoints, GraphQL schemas, WebSocket handlers |
| Data | Database models, migration scripts, ETL pipelines |
| Auth | OAuth flows, API key management, JWT handling |
| Compute | Functions, workers, batch processors |
| UI | Components, templates, pages |
| DevOps | Dockerfiles, CI configs, deploy scripts |

### 4.4 Safety Testing

Every generated module undergoes five test categories before deployment:

| Test Category | What It Validates |
|--------------|-------------------|
| **Functional** | Correct behavior, expected outputs |
| **Security** | No injection, no data leakage, input sanitization |
| **Performance** | Latency < thresholds, memory bounds |
| **Compatibility** | No conflicts with existing modules |
| **Rollback** | Clean removal, state restoration |

### 4.5 HITL Approval

Pending integrations require human approval:

```bash
# List pending integrations
curl http://localhost:8000/api/hitl/interventions/pending

# Approve an integration
curl -X POST http://localhost:8000/api/integrations/approve \
  -d '{"integration_id": "int-xyz789", "approver": "admin"}'

# Reject an integration
curl -X POST http://localhost:8000/api/integrations/reject \
  -d '{"integration_id": "int-xyz789", "reason": "Incompatible license"}'
```

### 4.6 Integration Catalog

```bash
# List all integrations by status
curl http://localhost:8000/api/integrations/active
curl http://localhost:8000/api/integrations/pending
curl http://localhost:8000/api/integrations/rejected
```

---

## Chapter 5: Self-Improvement & Learning

Murphy continuously improves through human corrections, pattern extraction, and adaptive training.

### 5.1 Correction Submission

When Murphy makes an error, submit a correction:

```bash
curl -X POST http://localhost:8000/api/corrections/submit \
  -d '{
    "execution_id": "exec-a1b2c3",
    "field": "output.recommendation",
    "original_value": "Increase inventory by 50%",
    "corrected_value": "Increase inventory by 15%",
    "reason": "50% is too aggressive for current demand"
  }'
```

### 5.2 Learning Pipeline

```
Correction → Pattern Extraction → Shadow Agent Training → Evaluation → Deployment
```

| Stage | Description |
|-------|-------------|
| **Pattern Extraction** | Groups corrections by domain, identifies recurring mistakes |
| **Shadow Agent Training** | Trains a shadow model on corrections without affecting production |
| **Evaluation** | Compares shadow agent performance against baseline |
| **Deployment** | Promotes shadow agent if performance improves |

### 5.3 Querying Learning Data

```bash
# View extracted patterns
curl http://localhost:8000/api/corrections/patterns

# View correction statistics
curl http://localhost:8000/api/corrections/statistics

# Export training data
curl http://localhost:8000/api/corrections/training-data
```

### 5.4 Adaptive Decision Engine

The learning engine tracks per-domain accuracy and adjusts future confidence scores automatically. Features include:

- **Feature engineering** — automatic extraction of decision-relevant features
- **Decision weighting** — adjusts weights based on outcome feedback
- **Domain specialization** — learns domain-specific heuristics over time

---

## Chapter 6: Confidence Engine & Validation

### 6.1 Murphy Validation Formula (G/D/H)

Every execution is scored using the **G/D/H formula**:

| Component | Meaning | Range |
|-----------|---------|-------|
| **G** (Generative) | Quality of the generated plan | 0.0–1.0 |
| **D** (Deterministic) | Correctness verified by rules/tests | 0.0–1.0 |
| **H** (Human) | Human approval confidence | 0.0–1.0 |

**Final Confidence** = weighted combination of G, D, and H scores.

### 6.2 5D Uncertainty Model

In addition to G/D/H, Murphy tracks five uncertainty dimensions:

| Dimension | Code | Description |
|-----------|------|-------------|
| Data Uncertainty | UD | Quality and completeness of input data |
| Algorithmic Uncertainty | UA | Model/algorithm reliability |
| Integration Uncertainty | UI | External system dependency risk |
| Resource Uncertainty | UR | Compute/memory availability |
| Governance Uncertainty | UG | Compliance and policy risk |

### 6.3 Trust Model & Trust Graph

Murphy maintains a trust graph across all modules, agents, and integrations:

```bash
# Check trust score for a module
curl http://localhost:8000/api/documents/{id}/magnify

# Solidify a validated artifact
curl -X POST http://localhost:8000/api/documents/{id}/solidify
```

### 6.4 Phase Transitions

Executions move through phases with confidence gates:

```
Draft → Validated → Approved → Executing → Completed
         ↓                        ↓
       Rejected                 Failed → Retry
```

A phase transition requires the confidence score to meet the configured threshold (default: 0.85).

### 6.5 Risk Assessment

```bash
curl http://localhost:8000/api/documents/{id}/gates
```

Returns risk assessment with severity levels (`low`, `medium`, `high`, `critical`) and recommended mitigations.

---

## Chapter 7: Security & Governance

### 7.1 Security Plane

The security plane provides defense-in-depth:

| Layer | Implementation |
|-------|---------------|
| **Authentication** | API key validation, JWT tokens |
| **Authorization** | RBAC with role-based access control |
| **Encryption** | TLS in transit, AES-256 at rest |
| **Input Validation** | Schema validation, injection prevention |
| **Rate Limiting** | Per-client request throttling |
| **DLP** | Data Loss Prevention scanning |

### 7.2 API Key Management

```bash
# API requests require the X-API-Key header
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/execute \
  -d '{"task": "..."}'
```

### 7.3 RBAC Governance

| Role | Permissions |
|------|------------|
| `viewer` | Read-only access to dashboards and status |
| `operator` | Execute tasks, view results |
| `admin` | Full access: configure, approve, manage users |
| `auditor` | Read all logs, compliance reports |

### 7.4 Compliance Monitoring

Murphy supports compliance frameworks out of the box:

| Framework | Features |
|-----------|----------|
| **HIPAA** | PHI detection, access logging, encryption enforcement |
| **SOC 2** | Audit trails, access controls, change management |
| **GDPR** | PII detection, data retention policies, right to erasure |

### 7.5 Audit Trails

All operations are logged with full audit trails:

```bash
# View audit log
curl http://localhost:8000/api/audit/log?limit=50

# Filter by action type
curl http://localhost:8000/api/audit/log?action=execution&limit=20
```

---

## Chapter 8: Robotics Integration

### 8.1 Supported Protocols

Murphy integrates with 12 robotics/industrial protocol clients:

| Protocol | Use Case | Example Devices |
|----------|----------|----------------|
| **Boston Dynamics Spot** | Mobile inspection | Spot robot |
| **Universal Robots (UR)** | Collaborative arms | UR5e, UR10e |
| **ROS2** | General robotics | Any ROS2 node |
| **Modbus** | Industrial I/O | PLCs, sensors |
| **BACnet** | Building automation | HVAC, lighting |
| **OPC-UA** | Industrial data | SCADA systems |
| **Fanuc** | CNC / industrial arms | Fanuc robots |
| **KUKA** | Industrial arms | KUKA KR series |
| **ABB** | Industrial arms | ABB IRB series |
| **DJI** | Aerial drones | DJI Matrice |
| **Clearpath** | Mobile platforms | Husky, Jackal |
| **MQTT** | IoT messaging | Any MQTT device |

### 8.2 Robot Registry

```bash
# Register a robot
curl -X POST http://localhost:8000/api/robotics/register \
  -d '{
    "robot_id": "ur5e-cell-1",
    "protocol": "universal_robots",
    "endpoint": "192.168.1.100:30002",
    "capabilities": ["pick_and_place", "welding"]
  }'

# List registered robots
curl http://localhost:8000/api/robotics/registry
```

### 8.3 Sensor Engine

Unified sensor reads with caching:

```bash
curl -X POST http://localhost:8000/api/automation/sensor/read \
  -d '{"sensor_id": "temp-zone-A", "protocol": "modbus", "cache_ttl": 5}'
```

### 8.4 Actuator Engine

Command execution with full audit logging:

```bash
curl -X POST http://localhost:8000/api/automation/actuator/execute \
  -d '{
    "actuator_id": "gripper-01",
    "command": "close",
    "parameters": {"force_n": 20},
    "require_confirmation": true
  }'
```

### 8.5 Emergency Stop

```bash
# Emergency stop — all robots
curl -X POST http://localhost:8000/api/robotics/emergency-stop

# Emergency stop — specific robot
curl -X POST http://localhost:8000/api/robotics/emergency-stop \
  -d '{"robot_id": "ur5e-cell-1"}'
```

> **⚠️ WARNING:** Emergency stop is immediate and irreversible. All active commands are aborted.

---

## Chapter 9: Avatar Identity Layer

The Avatar system gives Murphy configurable personality, voice, and behavioral traits for user-facing interactions.

### 9.1 Avatar Profiles

| Property | Description | Example |
|----------|-------------|---------|
| `voice` | Voice synthesis provider and voice ID | ElevenLabs "Rachel" |
| `style` | Communication style | Professional, casual, technical |
| `personality_traits` | Behavioral characteristics | Helpful, concise, empathetic |
| `knowledge_domains` | Expertise areas | Manufacturing, finance, DevOps |

### 9.2 Persona Injection

```bash
curl -X POST http://localhost:8000/api/avatar/inject \
  -d '{
    "session_id": "sess-001",
    "persona": {
      "name": "Murphy Manufacturing Expert",
      "style": "technical",
      "traits": ["precise", "safety-focused"],
      "domains": ["manufacturing", "quality_control"]
    }
  }'
```

### 9.3 User Adaptation

- **Interaction patterns** — learns preferred communication style
- **Formality preferences** — adjusts language register automatically
- **Sentiment classification** — detects user mood and adapts tone
- **Behavioral scoring** — tracks engagement and satisfaction

### 9.4 Session Management

```bash
curl http://localhost:8000/api/avatar/session/sess-001
# Returns: session_id, total_tokens, estimated_cost_usd, interactions, sentiment_score
```

### 9.5 Compliance Guard

Built-in PII detection prevents accidental exposure of sensitive data in responses.

### 9.6 External Connectors

| Connector | Purpose |
|-----------|---------|
| **ElevenLabs** | Text-to-speech voice synthesis |
| **HeyGen** | AI video avatar generation |
| **Tavus** | Personalized video at scale |
| **Vapi** | Voice AI phone agents |

---

## Chapter 10: Rosetta State Management

Rosetta manages agent state across the system, providing a universal state model for all agents.

### 10.1 Agent State Model

Each agent maintains structured state with fields for `identity`, `goals`, `tasks`, and `recalibration` (including drift score and scheduling).

### 10.2 State CRUD Operations

```bash
# Create
curl -X POST http://localhost:8000/api/rosetta/agents \
  -d '{"agent_id": "agent-sales-01", "identity": {...}, "goals": [...]}'

# Read
curl http://localhost:8000/api/rosetta/agents/agent-sales-01

# Update
curl -X PUT http://localhost:8000/api/rosetta/agents/agent-sales-01 \
  -d '{"goals": ["increase_conversion_rate", "expand_market"]}'

# Delete
curl -X DELETE http://localhost:8000/api/rosetta/agents/agent-sales-01
```

### 10.3 Archive & Recalibration

- **Archive classification** — completed/retired states are archived with tags for training data
- **Drift score** — measures behavioral divergence (0.0–1.0); auto-recalibration at threshold 0.3
- **Manual recalibration** — via API or HITL intervention

### 10.4 Global Health

```bash
curl http://localhost:8000/api/rosetta/health
# Returns: active agents, average drift, recalibration queue depth
```

---

## Chapter 11: Gate Synthesis & Failure Prevention

Gate Synthesis proactively identifies and prevents failures before they occur.

### 11.1 How Gates Work

```
Task Analysis → Failure Mode Enumeration → Gate Generation
    → Gate Activation → Continuous Monitoring → Auto-Response
```

### 11.2 Failure Mode Enumeration

Murphy analyzes each execution to enumerate possible failure modes:

```bash
curl -X POST http://localhost:8000/api/documents/{id}/gates \
  -d '{"enumerate_failures": true}'
```

### 11.3 Gate Generation & Activation

Gates are conditional checks inserted at critical execution points:

| Gate Type | Trigger | Action |
|-----------|---------|--------|
| **Confidence Gate** | Score drops below threshold | Pause and request HITL |
| **Resource Gate** | Memory/CPU exceeds limit | Throttle or queue |
| **Dependency Gate** | External service unavailable | Retry with backoff |
| **Data Gate** | Input validation fails | Reject and notify |
| **Time Gate** | Execution exceeds deadline | Abort with report |

### 11.4 Murphy Exposure Analysis

Exposure analysis quantifies the blast radius of potential failures:

```bash
curl http://localhost:8000/api/gate-synthesis/exposure?execution_id=exec-a1b2c3
```

### 11.5 Synthetic Failure Generation (Chaos Engineering)

Generate synthetic failures to test system resilience:

```bash
curl -X POST http://localhost:8000/api/gate-synthesis/chaos \
  -d '{
    "target": "database_engine",
    "failure_type": "latency_spike",
    "duration_seconds": 30,
    "severity": "medium"
  }'
```

> **⚠️ CAUTION:** Only use chaos engineering in non-production environments unless you have appropriate safeguards.

---

## Chapter 12: Execution Orchestrator

### 12.1 Execution Packets

The orchestrator compiles self-contained execution packets (task + plan + context + gates + risk):

```bash
curl -X POST http://localhost:8000/api/orchestrator/compile \
  -d '{"task_id": "task-001", "include_gates": true, "include_risk": true}'
```

Packets are cryptographically sealed (SHA-256) to prevent tampering.

### 12.2 Execution Lifecycle

Control execution flow with lifecycle commands:

```bash
# Pause execution
curl -X POST http://localhost:8000/api/orchestrator/pause \
  -d '{"execution_id": "exec-a1b2c3"}'

# Resume execution
curl -X POST http://localhost:8000/api/orchestrator/resume \
  -d '{"execution_id": "exec-a1b2c3"}'

# Abort execution
curl -X POST http://localhost:8000/api/orchestrator/abort \
  -d '{"execution_id": "exec-a1b2c3", "reason": "Resource constraint"}'
```

### 12.3 Telemetry & Risk Certificates

```bash
curl http://localhost:8000/api/orchestrator/telemetry?execution_id=exec-a1b2c3
```

Returns real-time metrics: step progress, latency, resource usage, and gate status.

Each execution also produces a **risk certificate** summarizing pre/post risk assessment, gates triggered, and confidence delta.

---

## Chapter 13: Monitoring & Analytics

### 13.1 Prometheus Metrics

Murphy exposes a Prometheus-compatible metrics endpoint:

```bash
curl http://localhost:8000/metrics
```

Key metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `murphy_requests_total` | Counter | Total API requests |
| `murphy_execution_duration_seconds` | Histogram | Execution latency |
| `murphy_confidence_score` | Gauge | Current confidence scores |
| `murphy_active_executions` | Gauge | Running executions |
| `murphy_gate_triggers_total` | Counter | Gate activations |
| `murphy_errors_total` | Counter | Error count by type |

### 13.2 System Health

```bash
curl http://localhost:8000/api/health
```

Returns aggregated health across all subsystems:

```json
{
  "status": "healthy",
  "subsystems": {
    "execution_engine": "healthy",
    "confidence_engine": "healthy",
    "learning_engine": "healthy",
    "security_plane": "healthy",
    "database": "healthy"
  },
  "version": "1.0",
  "uptime_seconds": 86400
}
```

### 13.3 Analytics Dashboard

Access via the integrated UI at `http://localhost:8000/dashboard`. The dashboard shows:

- Real-time execution pipeline
- Confidence score distributions
- Error rate trends
- Resource utilization
- Top active bots and agents

### 13.4 Operational SLOs

| SLO | Target | Metric |
|-----|--------|--------|
| API Availability | 99.9% | Uptime percentage |
| Execution Latency (p95) | < 5s | Response time |
| Confidence Accuracy | > 90% | Prediction vs. outcome |
| Gate False Positive Rate | < 5% | Unnecessary blocks |

### 13.5 Telemetry Learning

Murphy uses execution telemetry as training data to improve future predictions — latency patterns, failure correlations, and resource usage trends feed back into the learning engine.

---

## Chapter 14: Bot System

### 14.1 Overview

Murphy includes 80+ specialized bots, each focused on a specific domain. Bots are managed via the bot registry and governed by policy enforcement.

### 14.2 Key Bots

| Bot | Module | Purpose |
|-----|--------|---------|
| **Engineering Bot** | `engineering_bot/` | Technical tasks, architecture review |
| **Coding Bot** | `code_translator_bot/` | Code generation, translation, refactoring |
| **Memory Bot** | `memory_bot/` | Context retention, session history |
| **Librarian Bot** | `librarian_bot/` | Knowledge base management, RAG retrieval |
| **Security Bot** | `security_bot/` | Vulnerability scanning, policy enforcement |
| **Optimization Bot** | `optimization_bot/` | Performance tuning, resource optimization |
| **Anomaly Detection Bot** | `anomaly_bot/` | Pattern deviation detection, alerting |
| **Analysis Bot** | `analysisbot/` | Data analysis, statistical reporting |
| **Triage Bot** | `triage_bot/` | Ticket classification, priority assignment |
| **Research Bot** | `research_bot/` | Information gathering, summarization |
| **Commissioning Bot** | `commissioning_bot/` | Deployment automation, validation |
| **Scaling Bot** | `scaling_bot/` | Infrastructure auto-scaling |
| **Ghost Controller** | `ghost_controller_bot/` | System-level control, orchestration |
| **RubixCube Bot** | `rubixcube_bot/` | Evidence aggregation, multi-source correlation |

### 14.3 Bot Governance

All bots operate under governance policies:

- **Execution limits** — max concurrent tasks per bot
- **Resource budgets** — token and compute caps
- **Scope restrictions** — bots can only access their designated domain
- **Audit logging** — all bot actions are recorded

### 14.4 Bot Telemetry

```bash
curl http://localhost:8000/api/bots/telemetry
```

Returns per-bot metrics: invocation count, success rate, average latency, and resource consumption.

---

## Chapter 15: UI Interfaces

### 15.1 Available Interfaces

Murphy provides multiple interfaces for different user roles:

| Interface | File | Purpose |
|-----------|------|---------|
| **Onboarding Wizard** | `onboarding_wizard.html` | No-code guided setup for new users |
| **Landing Page** | `murphy_landing_page.html` | System overview and navigation hub |
| **Integrated Dashboard** | `murphy_ui_integrated.html` | Full management interface |
| **Integrated Terminal** | `murphy_ui_integrated_terminal.html` | Combined terminal with dashboard |
| **Architect Terminal** | `terminal_architect.html` | System design, module config |
| **Worker Terminal** | `terminal_worker.html` | Task submission and monitoring |
| **Enhanced Terminal** | `terminal_enhanced.html` | Advanced command interface |
| **Full Terminal** | `terminal_integrated.html` | All terminal features combined |
| **Python TUI** | `murphy_terminal.py` | Textual-based conversational CLI |
| **Setup Wizard CLI** | `src/setup_wizard.py` | Interactive configuration wizard |
| **Swagger API Docs** | `/docs` (when server running) | Auto-generated REST API reference |

### 15.2 Opening Web Interfaces

All HTML interfaces are static files. Open them directly in a browser:

```bash
# Open the onboarding wizard
open "Murphy System/onboarding_wizard.html"       # macOS
xdg-open "Murphy System/onboarding_wizard.html"   # Linux
start "Murphy System\onboarding_wizard.html"       # Windows
```

Or serve them via the API when the server is running at `http://localhost:8000/`.

### 15.3 Dashboard Features

The integrated dashboard (`murphy_ui_integrated.html`) provides: execution pipeline visualization, bot activity monitoring, confidence score distributions, system health matrix, and streaming log viewer with filtering.

Terminal interfaces provide browser-based command-line access for direct API interaction, task scripting, diagnostics, and configuration management.

---

## Chapter 16: Deployment

### 16.1 Docker Deployment

```bash
cd "Murphy System"

# Build the image (multi-stage build)
docker build -t murphy-system:1.0 .

# Run the container
docker run -d \
  --name murphy \
  -p 8000:8000 \
  -e DEEPINFRA_API_KEY=your-key \
  -v murphy-data:/app/data \
  murphy-system:1.0
```

### 16.2 Docker Compose (Local Dev)

```bash
docker-compose up -d
```

The `docker-compose.yml` includes:

| Service | Port | Purpose |
|---------|------|---------|
| `murphy` | 8000 | Main application |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Metrics visualization |

### 16.3 Kubernetes Deployment

Kubernetes manifests are in the `k8s/` directory:

```bash
# Deploy to Kubernetes
kubectl apply -f k8s/

# Key resources created:
# - Deployment (with HPA for auto-scaling)
# - Service (ClusterIP + Ingress)
# - PersistentVolumeClaim (data persistence)
# - ConfigMap (environment configuration)
# - Secret (API keys)
```

**Horizontal Pod Autoscaler (HPA):**

| Metric | Min Pods | Max Pods | Target |
|--------|----------|----------|--------|
| CPU | 2 | 10 | 70% utilization |

### 16.4 CI/CD Pipeline

The `.github/workflows/` directory contains CI/CD configurations:

- **Build** — linting, type checking, unit tests
- **Test** — integration tests, E2E tests (270+ tests)
- **Deploy** — staging → production with manual approval gate

### 16.5 Environment Configuration

| Environment | Config Source | Notes |
|-------------|-------------|-------|
| Development | `.env` file or env vars | Debug mode enabled |
| Staging | ConfigMap / env vars | Production-like with test data |
| Production | Kubernetes Secrets | All secrets encrypted |

---

## Chapter 17: API Reference

### 17.1 Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | System health check |
| `GET` | `/api/status` | Execution status |
| `GET` | `/api/info` | System information |
| `POST` | `/api/execute` | Submit a task for execution |
| `POST` | `/api/chat` | Conversational interface |

### 17.2 Form Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/forms/plan-upload` | Upload an execution plan |
| `POST` | `/api/forms/plan-generation` | Generate plan from description |
| `POST` | `/api/forms/task-execution` | Execute task with validation |
| `POST` | `/api/forms/correction` | Submit a correction form |
| `POST` | `/api/forms/validation` | Validate an artifact |

### 17.3 Document Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/documents/{id}` | Retrieve document |
| `POST` | `/api/documents/{id}/magnify` | Deep inspection |
| `POST` | `/api/documents/{id}/solidify` | Finalize artifact |
| `GET` | `/api/documents/{id}/gates` | View gates and risk |

### 17.4 Learning Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/corrections/submit` | Submit a correction |
| `GET` | `/api/corrections/patterns` | View learned patterns |
| `GET` | `/api/corrections/statistics` | Correction statistics |
| `GET` | `/api/corrections/training-data` | Export training data |

### 17.5 HITL Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/hitl/interventions/pending` | List pending approvals |
| `POST` | `/api/hitl/respond` | Respond to intervention |
| `GET` | `/api/hitl/statistics` | HITL statistics |

### 17.6 Integration Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/integrations/add` | Add new integration |
| `POST` | `/api/integrations/approve` | Approve integration |
| `POST` | `/api/integrations/reject` | Reject integration |
| `GET` | `/api/integrations/{status}` | List by status |

### 17.7 Automation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/automation/{engine}/{action}` | Execute automation action |
| `GET` | `/api/modules` | List loaded modules |
| `GET` | `/api/diagnostics/activation` | Module activation status |

### 17.8 Manufacturing (MFGC) Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mfgc/state` | Manufacturing state |
| `GET` | `/api/mfgc/config` | Manufacturing config |
| `POST` | `/api/mfgc/setup/{profile}` | Apply setup profile |

### 17.9 Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| `400` | Bad Request | Check request body schema |
| `401` | Unauthorized | Provide valid API key |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Verify endpoint and resource ID |
| `409` | Conflict | Resource already exists or state conflict |
| `422` | Validation Error | Check field types and required fields |
| `429` | Rate Limited | Reduce request frequency |
| `500` | Internal Error | Check logs, retry, or contact support |
| `503` | Service Unavailable | System starting up or overloaded |

### 17.10 Request/Response Examples

**Execute a task:**

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"task": "Analyze Q4 sales data", "priority": "high", "timeout_seconds": 300}'
```

**Success response:** `{"execution_id": "exec-7d3f2a", "status": "completed", "confidence": 0.92, ...}`

**Error response:** `{"error": {"code": 422, "message": "Validation failed", "details": [...]}}`

---

## Chapter 18: Troubleshooting

### 18.1 Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| System won't start | Port 8000 in use | `lsof -i :8000` and kill conflicting process |
| `ModuleNotFoundError` | Missing dependencies | `pip install -r requirements_murphy_1.0.txt` |
| LLM requests fail | Missing API key | Set `DEEPINFRA_API_KEY` or `OPENAI_API_KEY` env var |
| Low confidence scores | Insufficient context | Provide more detailed task descriptions |
| Slow execution | Resource constraints | Increase RAM/CPU or reduce concurrent tasks |
| 401 errors | Invalid API key | Regenerate API key and update configuration |
| Database locked | Concurrent writes | Increase `DB_TIMEOUT` or switch to PostgreSQL |
| Bot not responding | Bot crashed or overloaded | Check bot telemetry, restart bot via API |

### 18.2 Log Analysis

Logs are written to stdout and can be captured by your log aggregator:

```bash
# View recent logs
docker logs murphy --tail 100

# Filter for errors
docker logs murphy 2>&1 | grep ERROR

# Follow log stream
docker logs murphy -f
```

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

Set log level via environment variable:

```bash
export MURPHY_LOG_LEVEL=DEBUG
```

### 18.3 Performance Tuning

| Parameter | Default | Tuning Advice |
|-----------|---------|---------------|
| `MURPHY_WORKERS` | 4 | Set to CPU core count |
| `MURPHY_MAX_CONCURRENT` | 10 | Increase for high-throughput workloads |
| `MURPHY_CACHE_TTL` | 60s | Increase for stable data sources |
| `MURPHY_DB_TIMEOUT` | 30s | Increase if seeing lock timeouts |
| `MURPHY_LLM_TIMEOUT` | 60s | Increase for complex generation tasks |

### 18.4 Diagnostic Commands

```bash
# System diagnostics
curl http://localhost:8000/api/diagnostics/activation

# Module status
curl http://localhost:8000/api/modules

# Health deep-check
curl http://localhost:8000/api/health
```

### 18.5 Support Channels

| Channel | Contact |
|---------|---------|
| GitHub Issues | [Murphy-System Issues](https://github.com/IKNOWINOT/Murphy-System/issues) |
| Documentation | `documentation/` directory in the repository |
| Email | support@inoni.com |

---

## Chapter 19: License

Murphy System is available under the Business Source License 1.1. See [LICENSE](../LICENSE) for details.

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    MURPHY SYSTEM 1.0                            │
│                    Quick Reference                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  START:    ./start_murphy_1.0.sh                                │
│  HEALTH:   curl localhost:8000/api/health                       │
│  EXECUTE:  curl -X POST localhost:8000/api/execute -d '{...}'   │
│  STATUS:   curl localhost:8000/api/status                       │
│  METRICS:  curl localhost:8000/metrics                          │
│  LOGS:     docker logs murphy -f                                │
│  STOP:     docker stop murphy                                   │
│                                                                 │
│  DEFAULT PORT: 8000                                             │
│  CONFIG:       src/config.py or environment variables           │
│  DOCS:         documentation/ directory                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Chapter 20: No-Code Workflow Builder

The No-Code Workflow Builder provides a conversational "Librarian" terminal where you describe what you want to automate in natural language. The Librarian infers configuration, creates workflow steps in real-time, assigns monitoring agents, and compiles deployable workflows.

### 20.1 Creating a Session

```bash
curl -X POST http://localhost:8000/api/workflow-terminal/sessions
```

**Response:**
```json
{
  "success": true,
  "session": {
    "session_id": "abc-123",
    "state": "greeting",
    "conversation_history": [
      {
        "role": "librarian",
        "message": "Welcome to the Murphy No-Code Workflow Builder. I'm your Librarian — describe what you'd like to automate..."
      }
    ]
  }
}
```

### 20.2 Describing Your Workflow

Send a natural language message and the Librarian infers which steps to create:

```bash
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I need to monitor our API endpoints and send notifications on failures"}'
```

**Response includes:**
- `steps_created` — each workflow step built in real-time
- `agent_status` — monitoring agents assigned to each step
- `inferences` — what the Librarian understood from your description
- `workflow_snapshot` — current state of the full workflow

### 20.3 Supported Intent Categories

The Librarian recognizes 10 automation categories from keywords in your description:

| Category | Keywords | Step Type |
|----------|----------|-----------|
| Data Processing | process, transform, etl, csv, database | Transform |
| Notification | notify, alert, email, slack, sms | Action |
| Monitoring | monitor, watch, track, health, uptime | Action |
| Scheduling | schedule, cron, daily, weekly, recurring | Action |
| API Integration | api, rest, endpoint, webhook, fetch | Connector |
| Content Generation | generate, create, write, report, pdf | Action |
| Security | security, scan, audit, compliance, encrypt | Action |
| Deployment | deploy, release, build, ci, docker | Action |
| Approval | approve, review, sign-off, authorize | Condition |
| Onboarding | onboard, welcome, new hire, provision | Action |

### 20.4 Reviewing and Finalizing

```bash
# Review current state
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "review the workflow"}'

# Finalize and compile
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{session_id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "finalize"}'
```

### 20.5 Compiling and Exporting

```bash
curl http://localhost:8000/api/workflow-terminal/sessions/{session_id}/compile
```

Returns a compiled workflow with nodes, edges, and agent configurations ready for execution.

### 20.6 Agent Drill-Down

Inspect any agent's activity during workflow building:

```bash
curl http://localhost:8000/api/workflow-terminal/sessions/{session_id}/agents/{agent_id}
```

### 20.7 Generative Automation Presets

For advanced users who want to utilize pre-configured automation patterns that wire together multiple subsystems via voice activation or typed commands, see the comprehensive **[Generative Automation Presets Guide](documentation/features/GENERATIVE_AUTOMATION_PRESETS.md)**.

**Key capabilities include:**
- **Voice Command Interface (VCI)** — Speak natural language commands via `/api/vci/process`
- **Template Matching** — 12+ built-in automation templates (ETL, CI/CD, monitoring, etc.)
- **Industry Presets** — Pre-configured packages for SaaS, retail, finance, manufacturing, etc.
- **Role-Aware Execution** — Automations respect RBAC permissions (Platform Admin → Tenant Owner → Operator → Viewer)
- **Human-in-the-Loop Gates** — Automatic governance injection at critical points

**Quick example:**
```bash
# Create automation from natural language
curl -X POST http://localhost:8000/api/vci/process \
  -H "Content-Type: application/json" \
  -d '{"text_input": "Monitor sales data and send weekly summary to Slack"}'
```

---

## Chapter 21: Onboarding & Org Chart

The Onboarding Flow manages the complete journey from corporate org chart setup through individual onboarding to the no-code workflow builder.

### 21.1 Initialize Corporate Org Chart

Set up the default org chart with 12 agentic positions:

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/org/initialize
```

**Creates positions across:**
- **C-Suite:** CEO, CTO, COO, CFO
- **VP Level:** VP Engineering, VP Sales, VP Product
- **Managers:** Engineering Manager, Product Manager, Sales Manager
- **ICs:** Software Engineer, Sales Representative

Each position has a shadow agent configuration with monitoring level and auto-escalation settings. The org chart structure is classified as **Business IP**.

### 21.2 View Org Chart

```bash
# Full hierarchical chart
curl http://localhost:8000/api/onboarding-flow/org/chart

# List all positions
curl http://localhost:8000/api/onboarding-flow/org/positions
```

### 21.3 Start Individual Onboarding

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/start \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex Smith", "email": "alex@company.com"}'
```

### 21.4 Onboarding Questions

The system provides 10 onboarding questions covering:

| Category | Questions |
|----------|-----------|
| Personal | Full name, work email |
| Role | Department, position, manager |
| Responsibilities | Primary job duties |
| Tools | GitHub, Jira, Slack, Salesforce, etc. |
| Automation | Repetitive tasks to automate |
| Preferences | Notification style |
| Security | Compliance requirements (HIPAA, SOC2, GDPR, PCI-DSS) |

```bash
# Get questions
curl http://localhost:8000/api/onboarding-flow/sessions/{session_id}/questions

# Answer a question
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{session_id}/answer \
  -H "Content-Type: application/json" \
  -d '{"question_id": "q1", "answer": "Alex Smith"}'
```

### 21.5 Shadow Agent Assignment

Shadow agents are assigned to onboarded individuals. The agent learns from their work patterns and becomes **Employee IP**:

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{session_id}/shadow-agent \
  -H "Content-Type: application/json" \
  -d '{"position_id": "pos-123"}'
```

### 21.6 Transition to Workflow Builder

After onboarding, the system naturally transitions to the no-code builder with pre-loaded context:

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{session_id}/transition
```

The builder context includes the employee's name, position, shadow agent ID, and suggested automations based on their role and answers.

---

## Chapter 22: IP Classification & Trade Secrets

Murphy manages intellectual property across three tiers with trade secret protection.

### 22.1 Three-Tier IP Model

| Tier | Source | Protection | Owner |
|------|--------|------------|-------|
| **Employee IP** | Shadow agent learning data | Confidential | Employee |
| **Business IP** | Org chart interactions, process flows | Restricted | Business |
| **System IP** | Aggregated automation metrics | Internal (licensed to Murphy) | System |

**Protection Levels:**
- **Confidential** — Viewable only by the asset owner; not shared with other users or systems.
- **Restricted** — Limited to authorized personnel within the organization; eligible for trade secret designation.
- **Internal** — Accessible within the Murphy platform; automatically licensed for system-wide improvement.
- **Trade Secret** — Highest protection with access logging, NDA requirements, encryption at rest, and need-to-know access control.

### 22.2 Registering IP Assets

```bash
# Employee IP (from shadow agent)
curl -X POST http://localhost:8000/api/ip/assets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Work Patterns",
    "description": "Shadow agent learning data",
    "classification": "employee_ip",
    "owner_id": "emp-001",
    "owner_type": "employee"
  }'

# Business IP (trade secret)
curl -X POST http://localhost:8000/api/ip/assets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Department Interaction Map",
    "description": "How engineering interacts with product",
    "classification": "business_ip",
    "owner_id": "org-001",
    "owner_type": "business",
    "is_trade_secret": true
  }'
```

### 22.3 Trade Secret Protection

Trade secrets receive additional protections:
- Access logging on every attempt
- Need-to-know basis restrictions
- NDA requirement tracking
- Encryption at rest designation

### 22.4 Access Control

```bash
curl -X POST http://localhost:8000/api/ip/assets/{asset_id}/access-check \
  -H "Content-Type: application/json" \
  -d '{"requester_id": "user-123"}'
```

Returns `allowed: true/false` with reason (owner access, licensed access, or restricted).

### 22.5 IP Summary

```bash
curl http://localhost:8000/api/ip/summary
```

Returns breakdown by classification, protection level, trade secret count, and active licenses.

---

## Chapter 23: Credential Profiles & Automation Metrics

HITL credential profiles track user interaction patterns to build optimal automation recommendations.

### 23.1 Creating Profiles

```bash
curl -X POST http://localhost:8000/api/credentials/profiles \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-001", "user_name": "Jane Doe", "role": "engineer"}'
```

### 23.2 Recording Interactions

Every HITL decision is tracked:

```bash
curl -X POST http://localhost:8000/api/credentials/profiles/{profile_id}/interactions \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_type": "approval",
    "context": "deploy-v2",
    "decision": "approved",
    "confidence_before": 0.7,
    "confidence_after": 0.9,
    "response_time_ms": 1500
  }'
```

**Interaction types:** approval, rejection, modification, escalation, override, delegation, review.

### 23.3 Tier Progression

| Tier | Interactions Required |
|------|-----------------------|
| New | 0-9 |
| Learning | 10-49 |
| Established | 50-199 |
| Expert | 200-499 |
| Authority | 500+ |

### 23.4 Trust Score

The automation trust score (0.0–1.0) is computed from approval/rejection ratios:
- High approval rate → higher trust → more automation
- High rejection rate → lower trust → more human oversight

### 23.5 Optimal Automation Metrics (System IP)

```bash
curl http://localhost:8000/api/credentials/metrics
```

Returns system-wide metrics licensed to Murphy for improving recommendations:
- `auto_approve_confidence` — threshold above which tasks can be auto-approved
- `escalation_confidence` — threshold below which tasks should be escalated
- `target_response_time_ms` — target for human review speed

---

## Chapter 24: Agent Monitor Dashboard

The Agent Monitor Dashboard provides real-time visibility into all agents in the system.

### 24.1 Registering Agents

```bash
curl -X POST http://localhost:8000/api/agent-dashboard/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Monitor",
    "role": "monitor",
    "monitoring_mode": "active",
    "targets": ["api-service"],
    "metrics": ["latency", "error_rate"]
  }'
```

### 24.2 Dashboard Snapshot

```bash
curl http://localhost:8000/api/agent-dashboard/snapshot
```

Returns total agents, agents by state, agents by role, total alerts, and summaries.

### 24.3 Agent Drill-Down

```bash
# Full agent details
curl http://localhost:8000/api/agent-dashboard/agents/{agent_id}

# Activity log
curl http://localhost:8000/api/agent-dashboard/agents/{agent_id}/activity
```

### 24.4 Agent States

| State | Description |
|-------|-------------|
| idle | Agent registered but not actively monitoring |
| monitoring | Actively monitoring assigned targets |
| executing | Running a task |
| alerting | Has raised an alert |
| paused | Temporarily paused |
| error | Agent encountered an error |
| terminated | Agent deregistered |

---

## Chapter 25: Complete User Journey

This chapter walks through the complete flow from initial setup to active automation.

### Step 1 — Initialize the Organization

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/org/initialize
# Creates 12 agentic positions with reporting chains
# Org chart = Business IP
```

### Step 2 — Onboard an Individual

```bash
# Start onboarding
curl -X POST http://localhost:8000/api/onboarding-flow/start \
  -H "Content-Type: application/json" \
  -d '{"name": "Alex Smith", "email": "alex@company.com"}'

# Answer onboarding questions (10 questions)
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{id}/answer \
  -H "Content-Type: application/json" \
  -d '{"question_id": "q1", "answer": "Alex Smith"}'
```

### Step 3 — Assign Shadow Agent

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{id}/shadow-agent \
  -H "Content-Type: application/json" \
  -d '{"position_id": "pos-cto"}'
# Shadow agent = Employee IP
```

### Step 4 — Transition to No-Code Builder

```bash
curl -X POST http://localhost:8000/api/onboarding-flow/sessions/{id}/transition
# Returns builder context with suggested automations
```

### Step 5 — Build Workflow with Librarian

```bash
# Create builder session
curl -X POST http://localhost:8000/api/workflow-terminal/sessions

# Describe your automation
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Monitor our servers and alert on failures"}'

# Finalize
curl -X POST http://localhost:8000/api/workflow-terminal/sessions/{id}/message \
  -H "Content-Type: application/json" \
  -d '{"message": "finalize"}'
```

### Step 6 — Monitor Agents

```bash
# Register workflow agents on dashboard
curl -X POST http://localhost:8000/api/agent-dashboard/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "Server Monitor", "role": "monitor", "monitoring_mode": "active"}'

# View dashboard
curl http://localhost:8000/api/agent-dashboard/snapshot
```

### Step 7 — Track IP & Credentials

```bash
# Register automation metrics as System IP
curl -X POST http://localhost:8000/api/ip/assets \
  -H "Content-Type: application/json" \
  -d '{"name": "Q1 Metrics", "classification": "system_ip", "owner_id": "murphy_system"}'

# View optimal automation metrics
curl http://localhost:8000/api/credentials/metrics
```

---

## Appendix B: Glossary

| Term | Definition |
|------|-----------|
| **G/D/H** | Generative / Deterministic / Human — the three-component confidence formula |
| **HITL** | Human-in-the-Loop — safety mechanism requiring human approval for critical actions |
| **Gate** | A conditional check at an execution point that can pause, block, or redirect |
| **SwissKiss** | Murphy's automated repository analysis and integration workflow |
| **Rosetta** | Universal agent state management subsystem |
| **Exposure** | The blast radius of a potential failure |
| **Packet** | Self-contained execution unit with task, plan, gates, and risk assessment |
| **Drift** | Divergence of an agent's behavior from expected baseline |
| **Shadow Agent** | An AI agent that mirrors a human role, learning from their work patterns; becomes Employee IP |
| **Solidify** | Finalize and lock an artifact after validation |
| **Magnify** | Deep inspection of an artifact's trust and confidence scores |
| **UCP** | Universal Control Plane — the routing layer for all automation types |
| **Librarian** | The conversational AI in the no-code workflow builder that infers and builds automations |
| **Employee IP** | Intellectual property generated by shadow agents learning employee work patterns |
| **Business IP** | Intellectual property from org chart structure and system interaction patterns |
| **System IP** | Aggregated automation metrics licensed to Murphy for improving recommendations |
| **Trade Secret** | Protected IP with restricted access, audit logging, and need-to-know controls |
| **Credential Profile** | HITL user profile tracking approval patterns, trust scores, and tier progression |

---

*Murphy System 1.0 — © 2024 Inoni LLC. All rights reserved.*
*Created by Corey Post. Licensed under MIT (Community Edition).*
