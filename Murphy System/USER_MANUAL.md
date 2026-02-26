# Murphy System 1.0 — User Manual

**Universal AI Automation System**
**Version:** 1.0 | **Publisher:** Inoni LLC | **Creator:** Corey Post
**License:** MIT (Community Edition)

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

---

## Chapter 1: Getting Started

### 1.1 Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11+ |
| pip | Latest |
| OS | Linux, macOS, or Windows |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | 2 GB free space |

### 1.2 Installation

```bash
# Clone the repository
git clone https://github.com/your-org/Murphy-System.git
cd "Murphy System"

# Install dependencies
pip install -r requirements_murphy_1.0.txt

# Or use the setup script
chmod +x setup_murphy.sh
./setup_murphy.sh
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

The system starts on **port 6666** by default. Verify with:

```bash
curl http://localhost:6666/api/health
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
| REST API | `http://localhost:6666/api/` |
| Landing Page | `http://localhost:6666/` (murphy_landing_page.html) |
| Integrated Dashboard | `http://localhost:6666/dashboard` |
| Terminal UI | `http://localhost:6666/terminal` |

### 1.5 Configuration

Configuration is managed via environment variables or `src/config.py` (Pydantic BaseSettings):

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_HOST` | `0.0.0.0` | API bind address |
| `MURPHY_PORT` | `6666` | API port |
| `MURPHY_DB_PATH` | `murphy.db` | SQLite database path |
| `MURPHY_LLM_PROVIDER` | `groq` | LLM provider (groq, openai, local) |
| `GROQ_API_KEY` | — | Groq API key |
| `OPENAI_API_KEY` | — | OpenAI API key |

---

## Chapter 2: Task Execution

### 2.1 Submitting Tasks

Send any task to Murphy via the execute endpoint:

```bash
curl -X POST http://localhost:6666/api/execute \
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
curl -X POST http://localhost:6666/api/forms/plan-upload \
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
curl -X POST http://localhost:6666/api/forms/plan-generation \
  -d '{"description": "Set up a CI/CD pipeline for our Python microservice"}'
```

### 2.4 Task Execution with Validation

Submit a task with built-in validation checks:

```bash
curl -X POST http://localhost:6666/api/forms/task-execution \
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
curl http://localhost:6666/api/status?execution_id=exec-a1b2c3

# List all active executions
curl http://localhost:6666/api/status
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
curl -X POST http://localhost:6666/api/automation/sensor/read \
  -d '{"sensor_id": "temp-floor-3", "protocol": "modbus"}'

curl -X POST http://localhost:6666/api/automation/actuator/execute \
  -d '{"actuator_id": "valve-07", "command": "open", "parameters": {"percent": 75}}'
```

### 3.3 Content Automation

```bash
curl -X POST http://localhost:6666/api/automation/content/generate \
  -d '{
    "type": "blog_post",
    "topic": "AI in Manufacturing",
    "tone": "professional",
    "word_count": 1200
  }'
```

### 3.4 Data Automation

```bash
curl -X POST http://localhost:6666/api/automation/database/query \
  -d '{"query": "SELECT * FROM orders WHERE status = ?", "params": ["pending"]}'
```

### 3.5 System Automation

```bash
curl -X POST http://localhost:6666/api/automation/command/execute \
  -d '{"command": "systemctl restart nginx", "require_approval": true}'
```

### 3.6 Agent Automation (Swarm)

```bash
curl -X POST http://localhost:6666/api/automation/agent/swarm \
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
curl -X POST http://localhost:6666/api/automation/sales/score-lead \
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
curl -X POST http://localhost:6666/api/integrations/add \
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
curl http://localhost:6666/api/hitl/interventions/pending

# Approve an integration
curl -X POST http://localhost:6666/api/integrations/approve \
  -d '{"integration_id": "int-xyz789", "approver": "admin"}'

# Reject an integration
curl -X POST http://localhost:6666/api/integrations/reject \
  -d '{"integration_id": "int-xyz789", "reason": "Incompatible license"}'
```

### 4.6 Integration Catalog

```bash
# List all integrations by status
curl http://localhost:6666/api/integrations/active
curl http://localhost:6666/api/integrations/pending
curl http://localhost:6666/api/integrations/rejected
```

---

## Chapter 5: Self-Improvement & Learning

Murphy continuously improves through human corrections, pattern extraction, and adaptive training.

### 5.1 Correction Submission

When Murphy makes an error, submit a correction:

```bash
curl -X POST http://localhost:6666/api/corrections/submit \
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
curl http://localhost:6666/api/corrections/patterns

# View correction statistics
curl http://localhost:6666/api/corrections/statistics

# Export training data
curl http://localhost:6666/api/corrections/training-data
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
curl http://localhost:6666/api/documents/{id}/magnify

# Solidify a validated artifact
curl -X POST http://localhost:6666/api/documents/{id}/solidify
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
curl http://localhost:6666/api/documents/{id}/gates
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
curl -H "X-API-Key: your-api-key" http://localhost:6666/api/execute \
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
curl http://localhost:6666/api/audit/log?limit=50

# Filter by action type
curl http://localhost:6666/api/audit/log?action=execution&limit=20
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
curl -X POST http://localhost:6666/api/robotics/register \
  -d '{
    "robot_id": "ur5e-cell-1",
    "protocol": "universal_robots",
    "endpoint": "192.168.1.100:30002",
    "capabilities": ["pick_and_place", "welding"]
  }'

# List registered robots
curl http://localhost:6666/api/robotics/registry
```

### 8.3 Sensor Engine

Unified sensor reads with caching:

```bash
curl -X POST http://localhost:6666/api/automation/sensor/read \
  -d '{"sensor_id": "temp-zone-A", "protocol": "modbus", "cache_ttl": 5}'
```

### 8.4 Actuator Engine

Command execution with full audit logging:

```bash
curl -X POST http://localhost:6666/api/automation/actuator/execute \
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
curl -X POST http://localhost:6666/api/robotics/emergency-stop

# Emergency stop — specific robot
curl -X POST http://localhost:6666/api/robotics/emergency-stop \
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
curl -X POST http://localhost:6666/api/avatar/inject \
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
curl http://localhost:6666/api/avatar/session/sess-001
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
curl -X POST http://localhost:6666/api/rosetta/agents \
  -d '{"agent_id": "agent-sales-01", "identity": {...}, "goals": [...]}'

# Read
curl http://localhost:6666/api/rosetta/agents/agent-sales-01

# Update
curl -X PUT http://localhost:6666/api/rosetta/agents/agent-sales-01 \
  -d '{"goals": ["increase_conversion_rate", "expand_market"]}'

# Delete
curl -X DELETE http://localhost:6666/api/rosetta/agents/agent-sales-01
```

### 10.3 Archive & Recalibration

- **Archive classification** — completed/retired states are archived with tags for training data
- **Drift score** — measures behavioral divergence (0.0–1.0); auto-recalibration at threshold 0.3
- **Manual recalibration** — via API or HITL intervention

### 10.4 Global Health

```bash
curl http://localhost:6666/api/rosetta/health
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
curl -X POST http://localhost:6666/api/documents/{id}/gates \
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
curl http://localhost:6666/api/gate-synthesis/exposure?execution_id=exec-a1b2c3
```

### 11.5 Synthetic Failure Generation (Chaos Engineering)

Generate synthetic failures to test system resilience:

```bash
curl -X POST http://localhost:6666/api/gate-synthesis/chaos \
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
curl -X POST http://localhost:6666/api/orchestrator/compile \
  -d '{"task_id": "task-001", "include_gates": true, "include_risk": true}'
```

Packets are cryptographically sealed (SHA-256) to prevent tampering.

### 12.2 Execution Lifecycle

Control execution flow with lifecycle commands:

```bash
# Pause execution
curl -X POST http://localhost:6666/api/orchestrator/pause \
  -d '{"execution_id": "exec-a1b2c3"}'

# Resume execution
curl -X POST http://localhost:6666/api/orchestrator/resume \
  -d '{"execution_id": "exec-a1b2c3"}'

# Abort execution
curl -X POST http://localhost:6666/api/orchestrator/abort \
  -d '{"execution_id": "exec-a1b2c3", "reason": "Resource constraint"}'
```

### 12.3 Telemetry & Risk Certificates

```bash
curl http://localhost:6666/api/orchestrator/telemetry?execution_id=exec-a1b2c3
```

Returns real-time metrics: step progress, latency, resource usage, and gate status.

Each execution also produces a **risk certificate** summarizing pre/post risk assessment, gates triggered, and confidence delta.

---

## Chapter 13: Monitoring & Analytics

### 13.1 Prometheus Metrics

Murphy exposes a Prometheus-compatible metrics endpoint:

```bash
curl http://localhost:6666/metrics
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
curl http://localhost:6666/api/health
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

Access via the integrated UI at `http://localhost:6666/dashboard`. The dashboard shows:

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
curl http://localhost:6666/api/bots/telemetry
```

Returns per-bot metrics: invocation count, success rate, average latency, and resource consumption.

---

## Chapter 15: UI Interfaces

### 15.1 Available Interfaces

| Interface | File | Description |
|-----------|------|-------------|
| **Landing Page** | `murphy_landing_page.html` | System overview and navigation |
| **Integrated Dashboard** | `murphy_ui_integrated.html` | Full control dashboard |
| **Worker Terminal** | `murphy_ui_worker_terminal.html` | Task submission and monitoring |
| **Architect Terminal** | `terminal_architect.html` | System design and config |
| **Enhanced Terminal** | `murphy_ui_enhanced_terminal.html` | Advanced command interface |
| **Integrated Terminal** | `murphy_ui_integrated_terminal.html` | Combined terminal experience |

### 15.2 Dashboard Features

The integrated dashboard (`/dashboard`) provides: execution pipeline visualization, bot activity monitoring, confidence score distributions, system health matrix, and streaming log viewer with filtering.

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
  -p 6666:6666 \
  -e GROQ_API_KEY=your-key \
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
| `murphy` | 6666 | Main application |
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
curl -X POST http://localhost:6666/api/execute \
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
| System won't start | Port 6666 in use | `lsof -i :6666` and kill conflicting process |
| `ModuleNotFoundError` | Missing dependencies | `pip install -r requirements_murphy_1.0.txt` |
| LLM requests fail | Missing API key | Set `GROQ_API_KEY` or `OPENAI_API_KEY` env var |
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
curl http://localhost:6666/api/diagnostics/activation

# Module status
curl http://localhost:6666/api/modules

# Health deep-check
curl http://localhost:6666/api/health
```

### 18.5 Support Channels

| Channel | Contact |
|---------|---------|
| GitHub Issues | [Murphy-System Issues](https://github.com/your-org/Murphy-System/issues) |
| Documentation | `documentation/` directory in the repository |
| Email | support@inoni.com |

---

## Chapter 19: Business Model

### 19.1 Editions

| Feature | Community | Professional | Enterprise |
|---------|-----------|-------------|------------|
| **License** | MIT (Open Source) | Per-Seat | Annual Agreement |
| **Core Automation** | ✅ | ✅ | ✅ |
| **All 6 Automation Types** | ✅ | ✅ | ✅ |
| **Self-Integration** | ✅ | ✅ | ✅ |
| **Self-Improvement** | ✅ | ✅ | ✅ |
| **Bot System (80+)** | ✅ | ✅ | ✅ |
| **Priority Support** | — | ✅ | ✅ |
| **SLA Guarantees** | — | ✅ | ✅ |
| **Custom Integrations** | — | ✅ | ✅ |
| **Compliance Packages** | — | — | ✅ |
| **Dedicated Support** | — | — | ✅ |
| **On-Premise Deployment** | — | — | ✅ |
| **Custom Bot Development** | — | — | ✅ |

### 19.2 Edition Details

- **Community Edition** — fully functional open-source (MIT). All core features, self-hosted. Community support via GitHub Issues.
- **Professional Edition** — per-seat licensing. Priority support, SLA guarantees, custom integration assistance, regular updates.
- **Enterprise Edition** — annual agreement. Dedicated account management, full compliance packages (HIPAA, SOC 2, GDPR), on-premise deployment, custom bot/module development, training and onboarding.

---

## Appendix A: Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    MURPHY SYSTEM 1.0                            │
│                    Quick Reference                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  START:    ./start_murphy_1.0.sh                                │
│  HEALTH:   curl localhost:6666/api/health                       │
│  EXECUTE:  curl -X POST localhost:6666/api/execute -d '{...}'   │
│  STATUS:   curl localhost:6666/api/status                       │
│  METRICS:  curl localhost:6666/metrics                          │
│  LOGS:     docker logs murphy -f                                │
│  STOP:     docker stop murphy                                   │
│                                                                 │
│  DEFAULT PORT: 6666                                             │
│  CONFIG:       src/config.py or environment variables           │
│  DOCS:         documentation/ directory                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
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
| **Shadow Agent** | A model trained on corrections that runs in parallel for evaluation |
| **Solidify** | Finalize and lock an artifact after validation |
| **Magnify** | Deep inspection of an artifact's trust and confidence scores |
| **UCP** | Universal Control Plane — the routing layer for all automation types |

---

*Murphy System 1.0 — © 2024 Inoni LLC. All rights reserved.*
*Created by Corey Post. Licensed under MIT (Community Edition).*
