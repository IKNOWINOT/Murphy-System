# Murphy Matrix Bot

Full-parity Murphy System integration via Matrix (Synapse / Dendrite).

Every Murphy terminal function is available as a `!murphy` chat command.

---

## Prerequisites

- Python 3.10+
- A running Synapse or Dendrite homeserver
- A dedicated Matrix bot account (e.g. `@murphy:your.server`)
- Murphy System API running (default `http://localhost:8000`)

Install dependencies:

```bash
pip install "matrix-nio[e2e]>=0.24.0" "httpx>=0.27.0"
# or install the full requirements:
pip install -r requirements.txt
```

---

## Configuration

All settings are via environment variables.  Create a `.env` file or export
them before starting the bot:

| Variable | Default | Description |
|---|---|---|
| `MATRIX_HOMESERVER` | `http://localhost:8008` | Synapse / Dendrite URL |
| `MATRIX_USER_ID` | `@murphy:localhost` | Bot Matrix user ID |
| `MATRIX_PASSWORD` | _(empty)_ | Bot password (or use access token) |
| `MATRIX_ACCESS_TOKEN` | _(empty)_ | Bot access token (preferred) |
| `MURPHY_API_URL` | `http://localhost:8000/api` | Murphy REST API base URL |
| `MURPHY_WEB_URL` | `http://localhost:8000` | Murphy web UI base URL (for links) |
| `MATRIX_HITL_ROOM` | _(empty)_ | Room ID for HITL notifications |
| `MATRIX_ALERTS_ROOM` | _(empty)_ | Room ID for system alerts |
| `HITL_POLL_INTERVAL` | `30` | Seconds between HITL polls |
| `HEALTH_POLL_INTERVAL` | `15` | Seconds between health polls |
| `CIRCUIT_BREAKER_THRESHOLD` | `5` | Failures before circuit opens |
| `CIRCUIT_BREAKER_TIMEOUT` | `60` | Seconds before circuit resets |
| `MURPHY_BOT_CONFIG` | _(empty)_ | Path to optional YAML config file |
| `LOG_LEVEL` | `INFO` | Python log level |

### YAML config (optional)

```yaml
homeserver: https://matrix.example.com
user_id: "@murphy:example.com"
password: "s3cr3t"
murphy_api_url: "https://murphy.example.com/api"
murphy_web_url: "https://murphy.example.com"
hitl_room: "!abc123:example.com"
alerts_room: "!def456:example.com"
hitl_poll_interval: 30
health_poll_interval: 15
```

Set `MURPHY_BOT_CONFIG=/path/to/config.yaml` before starting.

---

## Starting the Bot

```bash
cd "Murphy System"

# Option 1 — module
python -m bots.run_matrix_bot

# Option 2 — script
python bots/run_matrix_bot.py
```

---

## All Commands

### Core System
| Command | Description |
|---|---|
| `!murphy status` | Full system status and metrics |
| `!murphy health` | Deep health check |
| `!murphy info` | System info (version, modules) |

### Orchestrator
| Command | Description |
|---|---|
| `!murphy overview` | Full business flow snapshot |
| `!murphy flows` | All active information flows |
| `!murphy flows inbound` | Inbound flows by department |
| `!murphy flows processing` | Agents/workflows processing |
| `!murphy flows outbound` | Outbound flows by type/client |
| `!murphy flows state` | Collective state of all flows |

### Task Execution
| Command | Description |
|---|---|
| `!murphy execute <command>` | Execute a task |
| `!murphy chat <message>` | Chat with Murphy |

### Workflows
| Command | Description |
|---|---|
| `!murphy workflows` | List all saved workflows |
| `!murphy workflow <id>` | Get workflow details |
| `!murphy workflow save <json>` | Save a workflow |
| `!murphy workflow-terminal list` | List workflow terminal items |
| `!murphy workflow builder` | Link to web workflow builder |
| `!murphy generate plan <text>` | Generate plan from natural language |
| `!murphy upload plan <json>` | Upload execution plan |

### Agents & Org Chart
| Command | Description |
|---|---|
| `!murphy agents` | List all agents |
| `!murphy agent <id>` | Agent details |
| `!murphy agent <id> activity` | Agent activity log |
| `!murphy orgchart` | Live agent org chart |
| `!murphy orgchart <task_id>` | Org chart for a task |

### HITL
| Command | Description |
|---|---|
| `!murphy hitl pending` | List pending HITL interventions |
| `!murphy hitl respond <id> <approve\|reject> [reason]` | Respond to intervention |
| `!murphy hitl stats` | HITL statistics |

You can also react with **✅** (approve) or **❌** (reject) directly on a HITL
notification message posted by the bot.

### Forms
| Command | Description |
|---|---|
| `!murphy form task <json>` | Execute task via form |
| `!murphy form validate <json>` | Validate execution packet |
| `!murphy form correct <json>` | Submit correction |
| `!murphy form status <id>` | Get form submission status |

### Corrections & Learning
| Command | Description |
|---|---|
| `!murphy corrections patterns` | Correction patterns |
| `!murphy corrections stats` | Correction statistics |
| `!murphy corrections training` | Training data |

### Costs & Budget
| Command | Description |
|---|---|
| `!murphy costs` | Cost overview |
| `!murphy costs breakdown` | Cost breakdown by category |
| `!murphy costs by-bot` | Per-agent cost breakdown |
| `!murphy costs budget` | Department budget |

### Integrations
| Command | Description |
|---|---|
| `!murphy integrations` | Active integrations |
| `!murphy integrations all` | All integrations |

### MFGC
| Command | Description |
|---|---|
| `!murphy mfgc state` | MFGC state |
| `!murphy mfgc config` | MFGC config |
| `!murphy mfgc config set <json>` | Update MFGC config |
| `!murphy mfgc setup <profile>` | Configure MFGC profile |

### Librarian
| Command | Description |
|---|---|
| `!murphy ask <query>` | Ask the Librarian |
| `!murphy librarian status` | Librarian status |

### Documents
| Command | Description |
|---|---|
| `!murphy documents` | List documents |
| `!murphy deliverables` | List outbound deliverables |

### Tasks & Production Queue
| Command | Description |
|---|---|
| `!murphy tasks` | List all tasks |
| `!murphy queue` | Current production queue |

### LLM & MFM
| Command | Description |
|---|---|
| `!murphy llm status` | LLM provider status |
| `!murphy mfm status` | MFM deployment status |
| `!murphy mfm metrics` | Training metrics |

### Onboarding
| Command | Description |
|---|---|
| `!murphy onboarding status` | Onboarding status |
| `!murphy onboarding questions` | Wizard questions |

### IP & Credentials
| Command | Description |
|---|---|
| `!murphy ip assets` | IP asset list |
| `!murphy credentials` | Credential profiles |

### Profiles & Auth
| Command | Description |
|---|---|
| `!murphy profiles` | List profiles |
| `!murphy role` | Current user role |
| `!murphy permissions` | Permissions for role |

### Diagnostics
| Command | Description |
|---|---|
| `!murphy diagnostics` | System diagnostics |
| `!murphy wingman` | Wingman protocol status |
| `!murphy causality` | Causality sandbox status |

### Help & Navigation
| Command | Description |
|---|---|
| `!murphy help` | Show all commands |
| `!murphy help <category>` | Show commands for a category |
| `!murphy links` | Clickable links to all web terminals |

---

## Architecture

```
Matrix Room
    │  !murphy <command>
    ▼
MurphyMatrixBot (matrix_bot.py)
    │  httpx async HTTP
    ▼
Murphy REST API (app.py)

Background tasks (concurrent):
  HITLBridge (matrix_hitl.py)       — polls /api/hitl/interventions/pending every 30 s
  HealthMonitor (matrix_notifications.py) — polls /api/health every 15 s
```

### Circuit Breaker

The API client uses a circuit breaker (threshold: 5 failures, timeout: 60 s)
that matches the `MurphyAPI._checkCircuit()` logic in `murphy-components.js`.
When the circuit is OPEN the bot replies with a friendly error instead of
hammering a down API.

---

## File Structure

```
Murphy System/bots/
├── __init__.py                  Package init (exports bot classes)
├── matrix_config.py             Configuration (env vars, YAML, defaults)
├── matrix_bot.py                Core bot — command routing + all handlers
├── matrix_hitl.py               HITL bridge — proactive polling + reactions
├── matrix_notifications.py      Health polling + offline/online alerts
├── matrix_formatters.py         Rich Matrix HTML message formatting
├── run_matrix_bot.py            CLI entry point
└── README.md                    This file
```
