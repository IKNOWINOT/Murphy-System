# Murphy Production System — Complete Session Specification

## Preamble: Guiding Principles

Act as a team of software engineers trying to finish what exists for production. For all choices, ask these questions and build plans from the answers:

1. **Does the module do what it was designed to do?**
2. **What exactly is the module supposed to do, knowing that this may change as design decisions evolve?**
3. **What conditions are possible based on the module?**
4. **Does the test profile actually reflect the full range of capabilities and possible conditions?**
5. **What is the expected result at all points of operation?**
6. **What is the actual result?**
7. **If there are still problems, how do we restart the process from the symptoms and work back through validation again?**
8. **Has all ancillary code and documentation been updated to reflect the changes made, including as-builts?**
9. **Has hardening been applied?**
10. **Has the module been commissioned again after those steps?**

---

## Part I: Project Context and Initial State

### 1.1 System Overview

The Murphy System is a full-stack automation platform designed to provide intelligent workflow automation with Human-in-the-Loop (HITL) safety mechanisms. The system operates across 10 verticals: marketing, proposals, crm, monitoring, finance, security, content, comms, pipeline, and industrial.

### 1.2 Core Architectural Components

The system is built on several foundational subsystems:

**MFGC (Multi-Factor Gate Controller)** — A 7-phase control system:
- INTAKE: Receive and validate input
- ANALYSIS: Parse and understand context
- SCORING: Calculate confidence and priority
- GATING: Apply decision thresholds
- MURPHY_INDEX: Determine automation risk level
- ENRICHMENT: Add contextual metadata
- OUTPUT: Generate final result

**MSS (Magnify-Simplify-Solidify)** — Information transformation pipeline with optimal sequence "MMSMM":
- MAGNIFY: Expand context
- MINIFY: Compress to essentials
- SOLIDIFY: Lock in decisions
- MAGNIFY: Expand implications
- MINIFY: Final compression

**HITL (Human-in-the-Loop)** — Safety layer requiring human approval for high-risk operations:
- Real state machine that blocks until approved/rejected
- Mandatory rejection reasons (minimum 10 characters)
- LLM-generated follow-up questions
- Example upload support for clarification

---

## Part II: Initial Request Specification

### 2.1 Primary Objectives

The user requested to:

1. **Integrate forge demo functionality into production server** — The demo deliverable generator needed to be properly integrated with configuration visibility
2. **Enhance HITL system** — Add mandatory rejection reasons, LLM follow-up questions, and example uploads
3. **Improve deliverable inspection** — Show what the deliverable is, changes made, and effect of changes
4. **Compare hetzner_load.sh with production server** — Identify missing infrastructure components
5. **Push to GitHub** — Version control the enhanced system
6. **Add Matrix server integration** — Real-time messaging for HITL notifications

### 2.2 Initial Analysis Tasks

Before writing code, perform these analysis steps:

1. Examine `src/demo_deliverable_generator.py` to understand configuration flow
2. Identify `_KEYWORD_MAP` (97 keywords) and `_SCENARIO_TEMPLATES` (10 scenarios)
3. Map `_detect_scenario()` function logic
4. Review `murphy_production_server.py` for existing endpoints
5. Analyze `scripts/hetzner_load.sh` for infrastructure components
6. Check for missing dependencies (numpy, concept_translation)

---

## Part III: Demo Configuration Endpoints Specification

### 3.1 GET /api/demo/config

**Purpose:** Expose the complete configuration of the demo deliverable generator for debugging and transparency.

**Response Schema:**
```json
{
  "scenarios": {
    "count": 10,
    "templates": [
      {
        "id": "onboarding",
        "name": "Employee Onboarding",
        "keywords": ["employee", "onboarding", "new hire", "orientation", "welcome"],
        "has_template_structure": true
      }
    ]
  },
  "keywords": {
    "count": 97,
    "mapping": {
      "employee": "onboarding",
      "invoice": "invoice",
      "budget": "finance"
    }
  },
  "pipeline_steps": [
    {"step": 1, "name": "parse_query", "description": "Parse natural language query"},
    {"step": 2, "name": "detect_scenario", "description": "Match to scenario template"},
    {"step": 3, "name": "generate_content", "description": "Create deliverable content"},
    {"step": 4, "name": "format_output", "description": "Format final deliverable"}
  ],
  "mfgc_phases": [
    "INTAKE", "ANALYSIS", "SCORING", "GATING", 
    "MURPHY_INDEX", "ENRICHMENT", "OUTPUT"
  ]
}
```

**Implementation Requirements:**
- Import from `demo_deliverable_generator`
- Access `_SCENARIO_TEMPLATES` and `_KEYWORD_MAP`
- Return static configuration data
- Handle import errors gracefully with fallback data

### 3.2 POST /api/demo/inspect

**Purpose:** Trace how a query is processed through the demo pipeline for debugging.

**Request Schema:**
```json
{
  "query": "Create an employee onboarding checklist"
}
```

**Response Schema:**
```json
{
  "query": "Create an employee onboarding checklist",
  "trace": {
    "detected_scenario": "onboarding",
    "confidence": 0.85,
    "matched_keywords": ["employee", "onboarding"],
    "processing_steps": [
      {
        "step": "parse_query",
        "status": "complete",
        "duration_ms": 12
      },
      {
        "step": "detect_scenario",
        "status": "complete",
        "matched_template": "onboarding",
        "duration_ms": 8
      }
    ],
    "mfgc_trace": {
      "phase": "OUTPUT",
      "score": 0.85,
      "gates_passed": ["confidence_threshold", "keyword_match"]
    }
  },
  "would_generate": {
    "type": "checklist",
    "estimated_sections": 5,
    "template_used": "onboarding"
  }
}
```

---

## Part IV: HITL System Enhancements Specification

### 4.1 Enhanced HITLRejectionRequest Model

**Purpose:** Ensure rejections are meaningful and actionable with mandatory documentation.

**Schema:**
```python
class HITLRejectionRequest(BaseModel):
    """Enhanced rejection with mandatory reason and follow-up support."""
    reason: str = Field(
        ..., 
        min_length=10,
        description="Mandatory rejection reason (minimum 10 characters)"
    )
    follow_up_questions: List[str] = Field(
        default_factory=list,
        description="LLM-generated questions for clarification"
    )
    example_upload_url: Optional[str] = Field(
        None,
        description="URL to example of desired output"
    )
    example_description: Optional[str] = Field(
        None,
        description="Description of what the example demonstrates"
    )
    desired_outcome: Optional[str] = Field(
        None,
        description="Description of the desired outcome"
    )
```

### 4.2 Enhanced POST /api/hitl/{hitl_id}/reject

**Purpose:** Process rejection with intelligent follow-up generation.

**Enhanced Response Schema:**
```json
{
  "status": "rejected",
  "hitl_id": "hitl-abc12345",
  "rejected_at": "2024-01-15T10:30:00Z",
  "rejection": {
    "reason": "The generated proposal lacks specific pricing details for enterprise tier",
    "follow_up_questions": [
      "What pricing structure would you prefer for the enterprise tier?",
      "Should the proposal include volume discounts?",
      "Do you need custom pricing for different regions?"
    ],
    "ambiguity_flags": [
      {
        "field": "pricing",
        "issue": "unclear_requirements",
        "suggestion": "Provide pricing template or example"
      }
    ],
    "example_request": {
      "url_provided": false,
      "description_provided": false,
      "suggested_action": "Upload an example proposal with desired pricing format"
    }
  },
  "llm_enhanced": true,
  "processing_metadata": {
    "questions_generated": 3,
    "ambiguities_detected": 1
  }
}
```

**Implementation Requirements:**
1. Validate reason is at least 10 characters
2. Use LLM to generate 2-5 follow-up questions based on rejection reason
3. Analyze original request for ambiguity flags
4. Support example upload URL and description
5. Log rejection for analytics

### 4.3 GET /api/hitl/{hitl_id}/inspect

**Purpose:** Provide detailed inspection of a HITL deliverable for debugging and transparency.

**Response Schema:**
```json
{
  "hitl_id": "hitl-abc12345",
  "deliverable_inspection": {
    "what_it_is": {
      "type": "proposal",
      "title": "Q1 Marketing Campaign Proposal",
      "format": "markdown",
      "generated_at": "2024-01-15T10:00:00Z",
      "sections": ["executive_summary", "objectives", "timeline", "budget", "metrics"]
    },
    "changes_made": {
      "total_changes": 3,
      "change_log": [
        {
          "field": "timeline",
          "previous": "4 weeks",
          "current": "6 weeks",
          "reason": "Extended for review buffer"
        },
        {
          "field": "budget",
          "previous": "$15,000",
          "current": "$22,500",
          "reason": "Added contingency buffer"
        }
      ],
      "last_modified": "2024-01-15T10:15:00Z"
    },
    "what_changes_do": {
      "impact_summary": "Timeline extension allows for stakeholder review. Budget increase provides 50% contingency.",
      "affected_automations": ["campaign-launch", "budget-tracking"],
      "downstream_effects": [
        "Campaign launch delayed by 2 weeks",
        "Monthly spend cap increased"
      ],
      "requires_reapproval": true
    }
  },
  "original_request": {
    "type": "marketing_proposal",
    "submitted_at": "2024-01-15T09:00:00Z",
    "requester": "user@example.com"
  },
  "current_status": "pending_review"
}
```

---

## Part V: Infrastructure Status Endpoints Specification

### 5.1 GET /api/infrastructure/status

**Purpose:** Comprehensive overview of all infrastructure components.

**Response Schema:**
```json
{
  "environment_config": {
    "database_url": "postgresql://***:***@localhost:5432/murphy",
    "redis_url": "redis://localhost:6379/0",
    "mail_server": "mail.murphy.local",
    "matrix_server": "matrix.murphy.local"
  },
  "services": {
    "database": {"status": "running", "healthy": true},
    "cache": {"status": "running", "healthy": true},
    "mail": {"status": "configured", "healthy": true},
    "monitoring": {"status": "running", "healthy": true},
    "llm": {"status": "available", "healthy": true},
    "matrix": {"status": "configured", "healthy": true}
  },
  "nginx_routes": {
    "/": "Murphy API :8000",
    "/ui/": "Murphy UI :8000",
    "/api/": "Murphy API :8000",
    "/grafana/": "Grafana :3000",
    "/mail/": "Roundcube :8443"
  },
  "docker_services": [
    {"name": "murphy-postgres", "port": 5432, "status": "running"},
    {"name": "murphy-redis", "port": 6379, "status": "running"},
    {"name": "murphy-prometheus", "port": 9090, "status": "running"},
    {"name": "murphy-grafana", "port": 3000, "status": "running"},
    {"name": "murphy-mailserver", "port": 25, "status": "running"},
    {"name": "murphy-webmail", "port": 8443, "status": "running"}
  ]
}
```

### 5.2 GET /api/infrastructure/database

**Purpose:** Detailed PostgreSQL database status.

**Response Schema:**
```json
{
  "service": "PostgreSQL",
  "status": "running",
  "connection": {
    "host": "localhost",
    "port": 5432,
    "database": "murphy",
    "ssl_mode": "prefer"
  },
  "pool": {
    "min_connections": 5,
    "max_connections": 20,
    "current_connections": 8
  },
  "tables": {
    "tenants": 3,
    "automations": 47,
    "hitl_queue": 12,
    "proposals": 156
  },
  "health": {
    "status": "healthy",
    "last_check": "2024-01-15T10:30:00Z",
    "response_time_ms": 2
  }
}
```

### 5.3 GET /api/infrastructure/cache

**Purpose:** Redis cache status and configuration.

**Response Schema:**
```json
{
  "service": "Redis",
  "status": "running",
  "connection": {
    "host": "localhost",
    "port": 6379,
    "database": 0
  },
  "memory": {
    "used_memory": "128MB",
    "max_memory": "512MB",
    "utilization_percent": 25
  },
  "keys": {
    "total": 1247,
    "by_prefix": {
      "session:": 45,
      "cache:": 892,
      "rate_limit:": 310
    }
  },
  "health": {
    "status": "healthy",
    "last_check": "2024-01-15T10:30:00Z"
  }
}
```

### 5.4 GET /api/infrastructure/mail

**Purpose:** Mail server configuration and status.

**Response Schema:**
```json
{
  "service": "Mail Server",
  "status": "configured",
  "smtp": {
    "host": "mail.murphy.local",
    "port": 587,
    "tls": true,
    "authentication": "starttls"
  },
  "imap": {
    "host": "mail.murphy.local",
    "port": 993,
    "tls": true
  },
  "webmail": {
    "url": "https://murphy.local/mail/",
    "interface": "Roundcube"
  },
  "dkim": {
    "configured": true,
    "selector": "default"
  },
  "spf": {
    "configured": true,
    "record": "v=spf1 mx -all"
  }
}
```

### 5.5 GET /api/infrastructure/monitoring

**Purpose:** Prometheus and Grafana monitoring configuration.

**Response Schema:**
```json
{
  "prometheus": {
    "status": "running",
    "url": "http://localhost:9090",
    "scrape_interval": "15s",
    "targets": [
      {"job": "murphy-api", "target": "localhost:8000", "status": "up"},
      {"job": "postgres", "target": "localhost:5432", "status": "up"},
      {"job": "redis", "target": "localhost:6379", "status": "up"}
    ]
  },
  "grafana": {
    "status": "running",
    "url": "https://murphy.local/grafana/",
    "dashboards": [
      {"name": "Murphy Overview", "uid": "murphy-main"},
      {"name": "API Performance", "uid": "api-perf"},
      {"name": "HITL Metrics", "uid": "hitl-metrics"}
    ]
  }
}
```

### 5.6 GET /api/infrastructure/llm

**Purpose:** Local LLM (Ollama) configuration.

**Response Schema:**
```json
{
  "service": "Ollama",
  "status": "running",
  "url": "http://localhost:11434",
  "models": [
    {"name": "llama3.2:latest", "size": "4.7GB", "modified": "2024-01-10"},
    {"name": "mistral:latest", "size": "4.1GB", "modified": "2024-01-08"}
  ],
  "current_model": "llama3.2:latest",
  "capabilities": {
    "chat": true,
    "embeddings": true,
    "vision": false
  }
}
```

### 5.7 POST /api/infrastructure/configure

**Purpose:** Update infrastructure configuration dynamically.

**Request Schema:**
```python
class InfrastructureConfigRequest(BaseModel):
    component: str  # database, cache, mail, monitoring, llm, matrix
    config: Dict[str, Any]
    restart_required: bool = False
```

**Response Schema:**
```json
{
  "status": "configured",
  "component": "cache",
  "changes_applied": ["max_memory", "timeout"],
  "restart_required": false,
  "effective_at": "2024-01-15T10:30:00Z"
}
```

### 5.8 GET /api/infrastructure/health

**Purpose:** Aggregated health check for all infrastructure.

**Response Schema:**
```json
{
  "overall_status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {"status": "healthy", "latency_ms": 2},
    "cache": {"status": "healthy", "latency_ms": 0.5},
    "mail": {"status": "healthy", "latency_ms": 15},
    "monitoring": {"status": "healthy", "latency_ms": 8},
    "llm": {"status": "healthy", "latency_ms": 120},
    "matrix": {"status": "healthy", "latency_ms": 25}
  },
  "alerts": [],
  "recommendations": []
}
```

---

## Part VI: Matrix Server Integration Specification

### 6.1 GET /api/infrastructure/matrix

**Purpose:** Matrix server configuration and status.

**Response Schema:**
```json
{
  "service": "Matrix",
  "status": "configured",
  "homeserver": {
    "url": "https://matrix.murphy.local",
    "name": "murphy.local",
    "version": "1.9.0"
  },
  "bot": {
    "username": "@murphy-bot:murphy.local",
    "display_name": "Murphy Bot",
    "status": "online"
  },
  "features": {
    "hitl_notifications": true,
    "approval_requests": true,
    "status_updates": true,
    "alert_broadcasts": true
  },
  "bridge": {
    "status": "active",
    "connected_rooms": 5,
    "last_sync": "2024-01-15T10:30:00Z"
  }
}
```

### 6.2 GET /api/infrastructure/matrix/rooms

**Purpose:** List configured Matrix rooms.

**Response Schema:**
```json
{
  "rooms": [
    {
      "id": "!hitl-approvals:murphy.local",
      "name": "HITL Approvals",
      "purpose": "Human-in-the-loop approval requests",
      "members": 8,
      "unread": 3
    },
    {
      "id": "!alerts:murphy.local",
      "name": "System Alerts",
      "purpose": "Critical system notifications",
      "members": 12,
      "unread": 0
    },
    {
      "id": "!automation-status:murphy.local",
      "name": "Automation Status",
      "purpose": "Automation execution updates",
      "members": 5,
      "unread": 7
    }
  ],
  "total_rooms": 3,
  "bot_joined": 3
}
```

### 6.3 GET /api/infrastructure/matrix/bridge

**Purpose:** Matrix-Murphy API bridge status.

**Response Schema:**
```json
{
  "bridge_status": "active",
  "connection": {
    "homeserver": "https://matrix.murphy.local",
    "bot_user": "@murphy-bot:murphy.local",
    "connected": true,
    "last_ping": "2024-01-15T10:30:00Z"
  },
  "message_routing": {
    "hitl_approved": "!hitl-approvals:murphy.local",
    "hitl_rejected": "!hitl-approvals:murphy.local",
    "automation_complete": "!automation-status:murphy.local",
    "system_alert": "!alerts:murphy.local"
  },
  "stats": {
    "messages_sent_24h": 47,
    "messages_received_24h": 12,
    "errors_24h": 0
  }
}
```

### 6.4 POST /api/infrastructure/matrix/send

**Purpose:** Send a message to a Matrix room.

**Request Schema:**
```python
class MatrixMessageRequest(BaseModel):
    room_id: str  # Matrix room ID or alias
    message: str  # Message content (Markdown supported)
    message_type: str = "m.text"  # m.text, m.notice, m.emote
    formatted: bool = False  # If true, parse as HTML
```

**Response Schema:**
```json
{
  "status": "sent",
  "event_id": "$abc123:murphy.local",
  "room_id": "!hitl-approvals:murphy.local",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 6.5 POST /api/infrastructure/matrix/rooms/create

**Purpose:** Create a new Matrix room for Murphy integration.

**Request Schema:**
```python
class MatrixRoomRequest(BaseModel):
    name: str
    topic: str
    purpose: str  # hitl, alerts, automation, general
    visibility: str = "private"  # public, private
    preset: str = "private_chat"  # private_chat, public_chat, trusted_private_chat
```

**Response Schema:**
```json
{
  "status": "created",
  "room_id": "!new-room:murphy.local",
  "name": "New Integration Room",
  "join_url": "https://matrix.to/#/!new-room:murphy.local"
}
```

### 6.6 GET /api/infrastructure/matrix/health

**Purpose:** Matrix server connectivity health check.

**Response Schema:**
```json
{
  "matrix_status": "healthy",
  "homeserver_reachable": true,
  "bot_authenticated": true,
  "bridge_active": true,
  "response_time_ms": 25,
  "last_check": "2024-01-15T10:30:00Z",
  "errors": []
}
```

---

## Part VII: Existing API Endpoints Reference

### 7.1 Core HITL Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/hitl/queue` | List all pending HITL items |
| GET | `/api/hitl/{hitl_id}` | Get specific HITL item |
| GET | `/api/hitl/{hitl_id}/inspect` | Inspect deliverable details |
| POST | `/api/hitl/{hitl_id}/approve` | Approve HITL item |
| POST | `/api/hitl/{hitl_id}/reject` | Reject HITL item with reason |

### 7.2 Automation Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/automations` | List all automations |
| GET | `/api/automations/stream` | SSE stream of automation updates |
| GET | `/api/automations/{auto_id}` | Get specific automation |
| GET | `/api/automations/{auto_id}/milestones` | Get automation milestones |
| POST | `/api/automations/{auto_id}/milestones/{ms_id}/delay` | Add milestone delay |
| PATCH | `/api/automations/{auto_id}` | Update automation |
| DELETE | `/api/automations/{auto_id}` | Delete automation |

### 7.3 Workflow Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/workflows/generate` | Generate workflow from description |
| GET | `/api/workflows` | List all workflows |
| POST | `/api/workflows/{workflow_id}/execute` | Execute workflow |
| POST | `/api/workflows/{workflow_id}/steps/{step_id}/approve` | Approve workflow step |
| POST | `/api/workflows/{workflow_id}/advance` | Advance workflow |

### 7.4 Demo Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/demo/config` | Get demo configuration |
| POST | `/api/demo/inspect` | Trace query processing |
| POST | `/api/demo/generate-deliverable` | Generate demo deliverable |

### 7.5 Communication Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/comms/rooms` | List communication rooms |
| POST | `/api/comms/send` | Send agent message |
| GET | `/api/comms/messages` | Get message history |
| POST | `/api/comms/broadcast` | Broadcast to all rooms |

### 7.6 Marketing & Proposal Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/marketing/campaigns` | List all campaigns |
| GET | `/api/marketing/campaigns/{tier}` | Get campaign by tier |
| POST | `/api/marketing/campaigns/{tier}/adjust` | Adjust campaign |
| POST | `/api/marketing/paid-proposal` | Create paid proposal |
| POST | `/api/marketing/paid-proposal/{proposal_id}/approve` | Approve paid proposal |
| GET | `/api/marketing/paid-proposals` | List paid proposals |
| GET | `/api/proposals/requests` | List proposal requests |
| POST | `/api/proposals/generate` | Generate proposal |
| GET | `/api/proposals/generated` | List generated proposals |
| GET | `/api/proposals/generated/{proposal_id}` | Get generated proposal |
| POST | `/api/proposals/generated/{proposal_id}/approve` | Approve generated proposal |

### 7.7 Calendar & Timeline Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/calendar` | Get calendar view |
| GET | `/api/calendar/blocks` | Get timeline blocks |

### 7.8 Pipeline & Setup Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/pipeline/self-setup` | Get self-setup status |
| POST | `/api/pipeline/self-setup/advance` | Advance setup |
| POST | `/api/pipeline/self-setup/run-full` | Run full setup |

### 7.9 Utility Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/health` | Health check |
| GET | `/api/tiers` | Get contribution tiers |
| GET | `/api/bots/status` | Get bot status |
| GET | `/api/labor-cost` | Get labor cost summary |
| GET | `/api/verticals` | List verticals |
| POST | `/api/verticals/{vertical_id}/activate` | Activate vertical |
| GET | `/api/executions` | List executions |
| POST | `/api/prompt` | Create from natural language prompt |

### 7.10 UI Routes

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve dashboard |
| GET | `/calendar` | Serve calendar view |
| GET | `/dashboard` | Serve legacy dashboard |
| GET | `/landing` | Serve landing page |
| GET | `/production-wizard` | Serve production wizard |
| GET | `/onboarding` | Serve onboarding page |

### 7.11 WebSocket

| Method | Endpoint | Purpose |
|--------|----------|---------|
| WS | `/ws` | WebSocket connection for real-time updates |

---

## Part VIII: Docker Compose Infrastructure

### 8.1 Required Services (from hetzner_load.sh)

```yaml
services:
  murphy-postgres:
    image: postgres:15-alpine
    container_name: murphy-postgres
    environment:
      POSTGRES_DB: murphy
      POSTGRES_USER: murphy
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U murphy"]
      interval: 10s
      timeout: 5s
      retries: 5

  murphy-redis:
    image: redis:7-alpine
    container_name: murphy-redis
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  murphy-prometheus:
    image: prom/prometheus:latest
    container_name: murphy-prometheus
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  murphy-grafana:
    image: grafana/grafana:latest
    container_name: murphy-grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning
    ports:
      - "3000:3000"
    environment:
      GF_SERVER_ROOT_URL: "%(protocol)s://%(domain)s/grafana/"

  murphy-mailserver:
    image: mailserver/docker-mailserver:latest
    container_name: murphy-mailserver
    hostname: mail
    domainname: murphy.local
    volumes:
      - maildata:/var/mail
      - mailstate:/var/mail-state
      - ./config/mail:/tmp/docker-mailserver
    ports:
      - "25:25"
      - "587:587"
      - "993:993"
    environment:
      ENABLE_SPAMASSASSIN: 1
      ENABLE_CLAMAV: 1
      ENABLE_FAIL2BAN: 1

  murphy-webmail:
    image: roundcube/roundcubemail:latest
    container_name: murphy-webmail
    ports:
      - "8443:80"
    environment:
      ROUNDCUBEMAIL_DEFAULT_HOST: ssl://mail.murphy.local
      ROUNDCUBEMAIL_DEFAULT_PORT: 993
```

### 8.2 Nginx Routing Configuration

```nginx
server {
    listen 80;
    server_name murphy.local;

    # Murphy API and UI
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /api/ {
        proxy_pass http://localhost:8000;
    }

    location /ui/ {
        proxy_pass http://localhost:8000;
    }

    location /static/ {
        proxy_pass http://localhost:8000;
    }

    location /docs {
        proxy_pass http://localhost:8000;
    }

    # Grafana monitoring
    location /grafana/ {
        proxy_pass http://localhost:3000/;
        proxy_set_header Host $host;
    }

    # Roundcube webmail
    location /mail/ {
        proxy_pass https://localhost:8443/;
        proxy_ssl_verify off;
    }

    # Matrix server
    location /_matrix/ {
        proxy_pass http://localhost:8008;
    }
}
```

---

## Part IX: Implementation Checklist

### 9.1 Configuration Endpoints
- [ ] Implement `GET /api/demo/config` with scenario templates
- [ ] Implement `POST /api/demo/inspect` with query tracing
- [ ] Add MFGC phase visibility to both endpoints
- [ ] Test with various query types

### 9.2 HITL Enhancements
- [ ] Update `HITLRejectionRequest` model with mandatory fields
- [ ] Implement LLM-based follow-up question generation
- [ ] Add ambiguity detection for rejection reasons
- [ ] Support example upload URLs
- [ ] Implement `GET /api/hitl/{hitl_id}/inspect` endpoint

### 9.3 Infrastructure Endpoints
- [ ] Implement `GET /api/infrastructure/status`
- [ ] Implement `GET /api/infrastructure/database`
- [ ] Implement `GET /api/infrastructure/cache`
- [ ] Implement `GET /api/infrastructure/mail`
- [ ] Implement `GET /api/infrastructure/monitoring`
- [ ] Implement `GET /api/infrastructure/llm`
- [ ] Implement `POST /api/infrastructure/configure`
- [ ] Implement `GET /api/infrastructure/health`

### 9.4 Matrix Integration
- [ ] Implement `GET /api/infrastructure/matrix`
- [ ] Implement `GET /api/infrastructure/matrix/rooms`
- [ ] Implement `GET /api/infrastructure/matrix/bridge`
- [ ] Implement `POST /api/infrastructure/matrix/send`
- [ ] Implement `POST /api/infrastructure/matrix/rooms/create`
- [ ] Implement `GET /api/infrastructure/matrix/health`

### 9.5 Documentation & Deployment
- [ ] Update API_DOCUMENTATION.md
- [ ] Update ARCHITECTURE_MAP.md
- [ ] Push to GitHub repository
- [ ] Run full integration tests
- [ ] Commission the updated system

---

## Part X: Validation Questions

After implementation, validate each component by asking:

1. **Does the module do what it was designed to do?**
   - Test each endpoint manually
   - Verify response schemas match specifications
   - Check error handling

2. **What conditions are possible?**
   - Database unavailable
   - Redis cache miss
   - Mail server offline
   - Matrix server disconnected
   - LLM timeout

3. **Does the test profile reflect full capabilities?**
   - Unit tests for each endpoint
   - Integration tests for infrastructure
   - Load tests for concurrent requests

4. **What is the expected vs actual result?**
   - Document baseline performance
   - Compare with benchmarks
   - Identify bottlenecks

5. **Has documentation been updated?**
   - API documentation
   - Architecture diagrams
   - Deployment guides

6. **Has hardening been applied?**
   - Input validation
   - Rate limiting
   - Authentication checks
   - Error message sanitization

7. **Has the module been commissioned?**
   - Full end-to-end test
   - Monitoring configured
   - Alerts set up
   - Runbook documented

---

## Appendix A: File Structure

```
Murphy-System/
├── murphy_production_server.py    # Main FastAPI server (3200+ lines)
├── src/
│   ├── demo_deliverable_generator.py
│   ├── llm_provider.py
│   ├── automations/
│   │   ├── engine.py
│   │   └── models.py
│   └── mfgc/
│       └── core.py
├── bots/
│   ├── matrix_config.py
│   ├── matrix_bot.py
│   └── [30+ bot modules]
├── config/
│   ├── nginx/
│   │   └── murphy-production.conf
│   ├── prometheus.yml
│   └── grafana/
├── scripts/
│   └── hetzner_load.sh
├── docker-compose.hetzner.yml
├── API_DOCUMENTATION.md
├── ARCHITECTURE_MAP.md
└── SESSION_SPECIFICATION_PROMPT.md  # This document
```

---

## Appendix B: Environment Variables

```bash
# Database
DATABASE_URL=postgresql://murphy:password@localhost:5432/murphy

# Redis
REDIS_URL=redis://localhost:6379/0

# Mail Server
SMTP_HOST=mail.murphy.local
SMTP_PORT=587
SMTP_USER=noreply@murphy.local
SMTP_PASSWORD=changeme

# Matrix
MATRIX_HOMESERVER=https://matrix.murphy.local
MATRIX_USER=@murphy-bot:murphy.local
 MATRIX_PASSWORD=changeme

# LLM
OLLAMA_HOST=http://localhost:11434
DEEPINFRA_API_KEY=changeme
TOGETHER_API_KEY=changeme

# Security
SECRET_KEY=changeme
JWT_SECRET=changeme
```

---

*Document Version: 1.0*
*Generated: Session Continuation*
*Author: SuperNinja AI Agent*