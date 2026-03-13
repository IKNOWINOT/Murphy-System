# ☠ Murphy System — Matrix Bot

> **Matrix protocol integration for the Murphy System.**  
> Full terminal parity, live communication observability, HITL reactions, and 90+ commands.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| Matrix homeserver | Synapse or any spec-compliant server |
| Murphy API | Running at a reachable URL |

---

## Installation

```bash
pip install 'matrix-nio[e2e]>=0.24.0' httpx>=0.27.0
```

Or install all Murphy dependencies:

```bash
cd "Murphy System"
pip install -r requirements.txt
```

---

## Room Setup

Create **4 Matrix rooms** and note their room IDs (format: `!roomid:server.example.com`):

| Room | Purpose | Env Var |
|------|---------|---------|
| `#murphy-general` | General commands | `MATRIX_DEFAULT_ROOM` |
| `#murphy-hitl` | HITL interventions requiring human approval | `MATRIX_HITL_ROOM` |
| `#murphy-alerts` | Health alerts, sentinel notifications, stuck workflows | `MATRIX_ALERTS_ROOM` |
| `#murphy-comms` | Live communication observatory (emails, webhooks, Slack, Teams) | `MATRIX_COMMS_ROOM` |

Invite the bot account to all four rooms.

---

## Environment Variables

### Required — Matrix

| Variable | Example | Description |
|----------|---------|-------------|
| `MATRIX_HOMESERVER` | `https://matrix.example.com` | Matrix homeserver URL |
| `MATRIX_USER_ID` | `@murphy:example.com` | Bot account Matrix ID |
| `MATRIX_PASSWORD` | `s3cr3t` | Bot password (or use token) |
| `MATRIX_ACCESS_TOKEN` | `syt_...` | Alternative to password auth |
| `MATRIX_DEFAULT_ROOM` | `!abc123:example.com` | General command room |
| `MATRIX_HITL_ROOM` | `!def456:example.com` | HITL intervention room |
| `MATRIX_ALERTS_ROOM` | `!ghi789:example.com` | Health/alert room |
| `MATRIX_COMMS_ROOM` | `!jkl012:example.com` | Comms activity room |

> Either `MATRIX_PASSWORD` **or** `MATRIX_ACCESS_TOKEN` must be set.

### Required — Murphy API

| Variable | Example | Description |
|----------|---------|-------------|
| `MURPHY_API_URL` | `http://localhost:8000/api` | Murphy API base URL |
| `MURPHY_API_KEY` | `mk_live_...` | API key for X-API-Key header |
| `MURPHY_WEB_BASE_URL` | `http://localhost:8000` | Web UI base URL (for `!murphy links`) |

### Optional — Bot Behaviour

| Variable | Default | Description |
|----------|---------|-------------|
| `BOT_COMMAND_PREFIX` | `!murphy` | Command prefix |
| `HEALTH_POLL_INTERVAL` | `15` | Seconds between health checks |
| `HITL_POLL_INTERVAL` | `30` | Seconds between HITL polls |
| `STATUS_POLL_INTERVAL` | `10` | Seconds between status overview polls |
| `COMMS_POLL_INTERVAL` | `20` | Seconds between comms activity polls |

### Optional — Email (passed through to EmailService)

| Variable | Description |
|----------|-------------|
| `SENDGRID_API_KEY` | SendGrid API key (activates SendGrid backend) |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP server port |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `SMTP_USE_TLS` | `true`/`false` (default: `true`) |
| `SMTP_FROM_EMAIL` | Default sender address |

---

## Quick Start

```bash
export MATRIX_HOMESERVER="https://matrix.example.com"
export MATRIX_USER_ID="@murphy:example.com"
export MATRIX_PASSWORD="your-bot-password"
export MATRIX_DEFAULT_ROOM="!abc123:example.com"
export MATRIX_HITL_ROOM="!def456:example.com"
export MATRIX_ALERTS_ROOM="!ghi789:example.com"
export MATRIX_COMMS_ROOM="!jkl012:example.com"
export MURPHY_API_URL="http://localhost:8000/api"
export MURPHY_API_KEY="your-api-key"
export MURPHY_WEB_BASE_URL="http://localhost:8000"

python -m bots.run_matrix_bot
```

---

## Command Reference

All commands start with `!murphy` (or your configured `BOT_COMMAND_PREFIX`).

### Dashboard

| Command | Description |
|---------|-------------|
| `!murphy status` | API + MFGC status pills (● ONLINE / ✕ OFFLINE) |
| `!murphy overview` | Running / HITL waiting / stuck workflow counts |
| `!murphy info` | System version, modules, capabilities |

### Orchestrator / Flows

| Command | Description |
|---------|-------------|
| `!murphy workflows` | List all workflows |
| `!murphy workflow <id>` | Workflow detail with step list |
| `!murphy workflow cancel <id>` | Cancel a running workflow |
| `!murphy workflow retry <id>` | Retry a failed workflow |
| `!murphy workflow rollback <id>` | Roll back a workflow |
| `!murphy workflow save <json>` | Save/create a workflow from JSON |
| `!murphy workflow builder` | Link to the visual workflow builder |
| `!murphy flows` | All flows summary |
| `!murphy flows inbound` | Inbound flows |
| `!murphy flows processing` | Flows in processing |
| `!murphy flows outbound` | Outbound flows |
| `!murphy flows state` | Flow state snapshot |

### Execute / Chat

| Command | Description |
|---------|-------------|
| `!murphy execute <command>` | Execute a terminal command |
| `!murphy chat <message>` | Chat with Murphy |
| `!murphy ask <query>` | Ask the Librarian (knowledge base) |

### Workflow Builder

| Command | Description |
|---------|-------------|
| `!murphy workflow builder` | Clickable link to workflow builder UI |
| `!murphy generate plan <text>` | AI-generate a plan from description |
| `!murphy upload plan <json>` | Upload a plan definition |

### Agents / Org Chart

| Command | Description |
|---------|-------------|
| `!murphy agents` | List all agents |
| `!murphy agent <id>` | Agent detail (persona, capabilities, status) |
| `!murphy agent <id> activity` | Agent activity log |
| `!murphy orgchart` | Live org chart |
| `!murphy orgchart <task_id>` | Org chart for a specific task |

### HITL (Human-In-The-Loop)

| Command | Description |
|---------|-------------|
| `!murphy hitl pending` | List pending interventions |
| `!murphy hitl respond <id> approve [reason]` | Approve an intervention |
| `!murphy hitl respond <id> reject [reason]` | Reject an intervention |
| `!murphy hitl respond <id> <message>` | Send a response message |
| `!murphy hitl stats` | HITL statistics |

### 📧 Email / Communication

| Command | Description |
|---------|-------------|
| `!murphy email send <to> <subject> :: <body>` | Send an email (use `::` to separate subject and body) |
| `!murphy email status` | Active email backend (SendGrid/SMTP/Mock) |
| `!murphy email test` | Send a test email to verify configuration |
| `!murphy notify <subject> :: <body>` | Send notification via all configured channels |
| `!murphy notify template <id> <json>` | Send notification from template |
| `!murphy notify channels` | List configured notification channels |
| `!murphy comms feed` | Recent communication activity feed |
| `!murphy comms stats` | Communication statistics |

### 🔗 Integrations

| Command | Description |
|---------|-------------|
| `!murphy integrations` | List active integrations |
| `!murphy integrations all` | All integrations (including inactive) |
| `!murphy integration <id>` | Integration detail with circuit breaker state |
| `!murphy integration <id> test` | Test integration connectivity |
| `!murphy integration <id> execute <method> [json]` | Execute an integration action |
| `!murphy connectors` | List all 80+ platform connectors |
| `!murphy connector <id>` | Connector detail |

### 🪝 Webhooks

| Command | Description |
|---------|-------------|
| `!murphy webhooks` | List webhook subscriptions |
| `!murphy webhook <id>` | Subscription detail |
| `!murphy webhook create <json>` | Create a webhook subscription |
| `!murphy webhook fire <event_type> [json]` | Dispatch a webhook event |
| `!murphy webhook deliveries <sub_id>` | Delivery log for a subscription |
| `!murphy webhook stats` | Webhook dispatcher statistics |

### 🎫 Service Module

| Command | Description |
|---------|-------------|
| `!murphy service tickets` | List service tickets |
| `!murphy service ticket <id>` | Ticket detail with SLA countdown |
| `!murphy service ticket create <json>` | Create a service ticket |
| `!murphy service ticket <id> assign <agent>` | Assign a ticket |
| `!murphy service catalog` | Service catalog |
| `!murphy service kb search <query>` | Knowledge base search |
| `!murphy service sla` | SLA definitions and status |
| `!murphy service csat` | CSAT average score |

### 💰 Costs

| Command | Description |
|---------|-------------|
| `!murphy costs` | Cost summary with budget gauge |
| `!murphy costs breakdown` | Detailed cost breakdown |
| `!murphy costs by-bot` | Per-bot cost table |
| `!murphy costs budget` | Budget status |
| `!murphy costs optimize` | Cost optimization recommendations |
| `!murphy costs record <json>` | Record a spend event |

### Forms / Corrections

| Command | Description |
|---------|-------------|
| `!murphy form task <json>` | Submit a task form |
| `!murphy form validate <json>` | Validate a form |
| `!murphy form correct <json>` | Submit a correction |
| `!murphy corrections patterns` | Correction patterns |
| `!murphy corrections stats` | Correction statistics |
| `!murphy corrections training` | Training data from corrections |

### MFGC / LLM / MFM

| Command | Description |
|---------|-------------|
| `!murphy mfgc state` | MFGC state |
| `!murphy mfgc config` | MFGC configuration |
| `!murphy mfgc setup` | MFGC setup status |
| `!murphy llm status` | LLM provider status |
| `!murphy llm configure <provider> <key>` | Configure LLM provider |
| `!murphy llm test` | Test LLM connection |
| `!murphy mfm status` | Murphy Foundation Model status |
| `!murphy mfm metrics` | MFM metrics |

### Documents / Tasks / Queue

| Command | Description |
|---------|-------------|
| `!murphy documents` | List documents |
| `!murphy deliverables` | List deliverables |
| `!murphy tasks` | List tasks |
| `!murphy queue` | Queue status |

### Auth / Onboarding / IP

| Command | Description |
|---------|-------------|
| `!murphy onboarding status` | Onboarding status |
| `!murphy onboarding questions` | Onboarding questions |
| `!murphy ip assets` | IP asset list |
| `!murphy credentials` | Credentials list |
| `!murphy profiles` | Profile list |
| `!murphy role` | Current auth role |
| `!murphy permissions` | Current permissions |

### Diagnostics

| Command | Description |
|---------|-------------|
| `!murphy diagnostics` | Full diagnostics report |
| `!murphy wingman` | Wingman co-pilot status |
| `!murphy causality` | Causality engine insights |
| `!murphy sentinel` | Sentinel alert list |
| `!murphy canary` | Canary deployment status |

### Module Compiler

| Command | Description |
|---------|-------------|
| `!murphy modules` | List compiled modules |
| `!murphy module <id>` | Module detail |
| `!murphy module compile <source_path>` | Compile a module |
| `!murphy capabilities` | Capability map |
| `!murphy capability <name>` | Capability detail |

### Bot Management

| Command | Description |
|---------|-------------|
| `!murphy bots` | List registered bots |
| `!murphy bot <id> action <json>` | Execute a bot action |

### Help / Navigation

| Command | Description |
|---------|-------------|
| `!murphy help` | Full command reference |
| `!murphy help <category>` | Commands for a category |
| `!murphy links` | Clickable links to all 7 terminals |
| `!murphy jargon` | All 28 Murphy jargon terms |
| `!murphy jargon <term>` | Single jargon definition |

---

## HITL Reaction Workflow

When Murphy detects a pending HITL intervention, it posts a card to `MATRIX_HITL_ROOM`:

```
⚠ HITL INTERVENTION
ID: <id>  [priority]
<title>
<context>
React ✅ to approve, ❌ to reject,
or: !murphy hitl respond <id> approve/reject [reason]
```

**Supported reactions:**
- **Approve:** ✅ ✔️ 👍 ✓
- **Reject:** ❌ 👎 ✗ ✕

The bot will post a confirmation back to the room after processing.

---

## Communication Observatory

The `MATRIX_COMMS_ROOM` is a **live feed of all Murphy communication activity**.

Every `COMMS_POLL_INTERVAL` seconds (default: 20s), the bot polls `/api/comms/activity` and posts new events:

| Event Type | Shows |
|------------|-------|
| Email sent | To, subject, provider (SendGrid/SMTP/Mock), success/fail, latency |
| Slack message | Channel, connector, success/fail |
| Teams message | Thread, connector, success/fail |
| Discord message | Channel, connector, success/fail |
| Webhook fired | Event type, subscriber URL, HTTP status, latency |
| Notification dispatched | Channels, priority, per-channel delivery status |

This gives operators a **real-time window into all Murphy communication activity** directly in Matrix.

---

## Architecture

```
Matrix Client (Element/etc.)
    ↕ Matrix Protocol
Matrix Homeserver (Synapse)
    ↕
Murphy Matrix Bot (matrix-nio AsyncClient)
├── MatrixBot         — command dispatch, 90+ handlers
├── HITLBridge        — HITL polling + emoji reaction routing
└── NotificationRelay — health, status, sentinel, comms feed
    ↕ httpx (X-API-Key, circuit breaker, retry)
Murphy API (http://localhost:8000/api)
├── /api/health               → health status
├── /api/orchestrator/*       → workflows, flows, overview
├── /api/hitl/*               → interventions
├── /api/notifications/*      → email + multi-channel notifications
├── /api/comms/*              → communication activity feed
├── /api/webhooks/*           → webhook dispatcher
├── /api/integrations/*       → integration framework
├── /api/connectors/*         → platform connectors
├── /api/service/*            → service module (tickets, SLA, KB)
├── /api/coa/*                → cost optimization advisor
└── ...                       → 80+ other endpoints
    ↕
Email/Slack/Teams/Discord/Webhooks (actual delivery)
```

**Resilience:** The HTTP client mirrors `MurphyAPI` from the frontend:
- Circuit breaker: 5 failures → OPEN → 30s cooldown → HALF_OPEN → CLOSED
- Retries: 3 attempts on 5xx, exponential backoff `min(1000×2ⁿ, 8000)ms`
- Timeout: 10s per request
- Graceful degradation: `!murphy help`, `!murphy jargon`, `!murphy links` work even offline

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `matrix-nio not installed` | Run `pip install 'matrix-nio[e2e]>=0.24.0'` |
| `Required environment variable 'X' is not set` | Set all required env vars (see above) |
| Bot does not join rooms | Ensure the bot account is invited to all 4 rooms |
| `Circuit breaker OPEN` errors | Murphy API is down or returning 5xx; check API logs |
| No HITL notifications | Check `MATRIX_HITL_ROOM` is correct and bot has join permission |
| No comms feed activity | Check `/api/comms/activity` or `/api/notifications/recent` endpoint availability |
| E2E encryption issues | Verify `matrix-nio[e2e]` is installed (includes libolm) |
