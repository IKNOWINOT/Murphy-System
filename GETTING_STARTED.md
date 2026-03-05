# Getting Started with Murphy System

A complete guide to installing, launching, and using Murphy System — from zero to running in one command.

---

## 1. Quick Start

### One-Command Setup (Linux / macOS)

From the repository root:

```bash
bash setup_and_start.sh
```

This script checks prerequisites (Python 3.10+), creates a virtual environment, installs all dependencies, configures your environment, and starts the system.

### Windows

```cmd
setup_and_start.bat
```

### Remote Install (no clone required)

```bash
curl -fsSL https://raw.githubusercontent.com/IKNOWINOT/Murphy-System/main/install.sh | bash
```

### Manual Setup

```bash
# Requires Python 3.10+
pip install -r requirements.txt
cd "Murphy System"
python murphy_system_1.0_runtime.py
```

The REST API server starts on **http://localhost:8000**. Confirm it is running:

```bash
curl http://localhost:8000/api/health
```

---

## 2. What You Get

Murphy System ships with four interface layers. All are available out of the box.

| Interface | Entry Point | Description |
|-----------|-------------|-------------|
| **REST API** | `murphy_system_1.0_runtime.py` (port 8000) | 70+ endpoints, Swagger docs at `/docs` |
| **Terminal UI** | `murphy_terminal.py` | Conversational TUI (requires `textual`) |
| **Web UIs** | Static HTML files (open in browser) | Dashboards, wizards, and terminal views |
| **Setup Wizard CLI** | Python one-liner (see §6) | Guided first-time configuration |

Under the hood: 584 source modules across 54 packages, 118 gap-closure tests, and 90 audit categories all at zero. Project configuration (pytest, mypy, ruff) lives in `pyproject.toml`.

---

## 3. Using the REST API

The FastAPI server exposes 70+ endpoints under `/api/`. Interactive documentation is available at **http://localhost:8000/docs** once the server is running.

### Key Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | System status and loaded components |
| `/api/execute` | POST | Execute a task |
| `/api/chat` | POST | Conversational interface |
| `/api/forms/*` | various | Dynamic form management |
| `/api/onboarding/wizard/*` | various | Guided onboarding flow |
| `/api/librarian/*` | various | Knowledge-base operations |
| `/api/documents/*` | various | Document management |
| `/api/integrations/*` | various | Third-party integrations |
| `/api/llm/*` | various | LLM configuration and queries |

### Examples

**Check system status:**

```bash
curl http://localhost:8000/api/status
```

**Execute a task:**

```bash
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Summarize quarterly sales data", "task_type": "query"}'
```

**Chat with Murphy:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What integrations are available?"}'
```

---

## 4. Using the Web UIs

Open any of the following HTML files directly in a browser. They connect to the REST API on port 8000.

| File | Purpose |
|------|---------|
| `onboarding_wizard.html` | No-code setup wizard — configure Murphy without touching config files |
| `murphy_landing_page.html` | Control-plane dashboard — system overview and navigation |
| `murphy_ui_integrated.html` | Integrated management interface — unified admin panel |
| `terminal_architect.html` | Architect terminal — system design and planning |
| `terminal_worker.html` | Worker terminal — task execution and monitoring |
| `terminal_integrated.html` | Full integrated terminal — combined architect + worker view |
| `terminal_enhanced.html` | Enhanced terminal — advanced features and output formatting |
| `murphy_ui_integrated_terminal.html` | Unified terminal with integrated management controls |

All files are located inside the `Murphy System/` directory. Example:

```bash
# macOS
open "Murphy System/onboarding_wizard.html"

# Linux
xdg-open "Murphy System/onboarding_wizard.html"

# Windows
start "Murphy System\onboarding_wizard.html"
```

Make sure the REST API server is running before using the web UIs.

### Onboarding Wizard Walkthrough

The **No-Code Onboarding Wizard** (`onboarding_wizard.html`) is the recommended starting point for new users. It has two tabs:

1. **System Setup Wizard** — Describe your business or use case in plain English. Murphy asks follow-up questions to raise confidence, then generates a complete configuration. Steps:
   - Click **"Start Setup Wizard"** on the welcome screen.
   - Answer each question (business name, industry, what you want to automate).
   - Review the summary of generated settings.
   - Click **"Download Config"** to save your `murphy_config.json`.

2. **Employee Onboarding** — Add team members, assign roles, and track their onboarding tasks (e.g., API key setup, first workflow creation).

### Role-Based Terminals

Murphy provides role-specific terminal UIs so different team members see only what they need:

- **Architect Terminal** (`terminal_architect.html`) — For system designers and tech leads. Provides gate review, system design commands, dependency graph visualization, and architecture planning. Includes 30+ interactive functions.
- **Worker Terminal** (`terminal_worker.html`) — For execution staff. Focused on task execution, status monitoring, and delivery tracking. Streamlined 8-function interface.
- **Integrated Terminal** (`terminal_integrated.html`) — Combines architect + worker views for power users who need both planning and execution in one window. 35+ functions.
- **Enhanced Terminal** (`terminal_enhanced.html`) — Adds advanced output formatting, syntax highlighting, and extended command palette. 20+ functions.

### Dashboards

- **Landing Page** (`murphy_landing_page.html`) — High-level control-plane dashboard showing system status, active workflows, and quick navigation to all other UIs.
- **Integrated Management** (`murphy_ui_integrated.html`) — Unified admin panel for configuration, monitoring, and system management.

---

## 5. Using the Terminal UI

The Textual-based TUI provides a natural-language conversational interface in your terminal.

```bash
cd "Murphy System"
python murphy_terminal.py
```

> **Note:** The `textual` package is an optional dependency. If it is not installed, add it with:
> ```bash
> pip install textual
> ```

---

## 6. Using the Setup Wizard

For guided first-time configuration, run the CLI setup wizard:

```bash
python -c "from src.setup_wizard import run_cli; run_cli()"
```

The wizard walks you through environment configuration, API key setup, and initial system preferences.

---

## 7. Use Cases

Murphy System is a general-purpose automation platform. Here are concrete examples of how to use it:

### Business Automation

Automate sales pipelines, marketing campaigns, reporting workflows, and CRM integration.

```bash
# Create a sales pipeline automation
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Create a sales pipeline that tracks leads from first contact to close", "task_type": "workflow"}'
```

### Self-Integration

Ingest and connect external repositories, APIs, and services through the integration engine.

```bash
# List available integrations
curl http://localhost:8000/api/integrations/available

# Connect a new data source
curl -X POST http://localhost:8000/api/integrations/connect \
  -H "Content-Type: application/json" \
  -d '{"type": "api", "name": "My CRM", "endpoint": "https://api.example.com/v1"}'
```

### Content Creation

Generate, review, and manage documents and knowledge-base articles using the LLM and librarian subsystems.

```bash
# Generate a document
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Write a project status report for Q1", "task_type": "content"}'
```

### Manufacturing & Operations

Model production workflows, track execution, and automate operational tasks end-to-end.

```bash
# Execute a manufacturing workflow
curl -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Run quality inspection on production batch #2847", "task_type": "operation"}'
```

Combine the REST API with the web dashboards and terminal UIs to build workflows tailored to your domain.

---

## 8. Troubleshooting

### Port 8000 already in use

Another process is occupying the default port. Either stop that process or set a different port:

```bash
MURPHY_PORT=7777 python murphy_system_1.0_runtime.py
```

### `ModuleNotFoundError` on startup

Dependencies are missing. Install them from the repository root:

```bash
pip install -r requirements.txt
```

### Python version too old

Murphy requires **Python 3.10 or higher**. Check your version:

```bash
python3 --version
```

Upgrade via your system package manager or download from [python.org](https://www.python.org/downloads/).

### Terminal UI fails to launch

The `textual` package may not be installed:

```bash
pip install textual
```

### Quick diagnostic script

```bash
cd "Murphy System"
python3 -c "
import sys
print(f'Python: {sys.version}')
for mod in ['fastapi', 'uvicorn', 'pydantic']:
    try:
        __import__(mod)
        print(f'  ✓ {mod}')
    except ImportError:
        print(f'  ✗ {mod} — run: pip install {mod}')
"
```

---

## 9. Screenshots — Current Build

### Landing Page

![Murphy System Landing Page](https://github.com/user-attachments/assets/f5364d3c-55ca-4c30-a2ac-1d14985c4142)

### Pricing Tiers

| Tier | Price | Notes |
|------|-------|-------|
| Community | Free | Open source (MIT), budgeted from paid income |
| Creator Starter | $20/mo | Monthly |
| Professional | $99/mo | Per seat |
| Enterprise | Contact us | Custom pricing — funds community free tier |

![Pricing Section](https://github.com/user-attachments/assets/eeb32121-ae1f-402a-af57-43a35f579b2c)

### Onboarding Wizard

![Onboarding Wizard](https://github.com/user-attachments/assets/dfe82ae2-20c3-4539-b6d2-11afca3215bb)

### Architect Terminal

![Architect Terminal](https://github.com/user-attachments/assets/0ea6c4fc-ea11-437e-be25-9e1780d4eafa)

### Integrated Terminal

![Integrated Terminal](https://github.com/user-attachments/assets/2778aba7-d442-4b91-b2c0-d8539751a1ee)

### API Health & Status

![API Health](https://github.com/user-attachments/assets/9e4f82c0-d256-4d93-9913-b59919d05d35)

![API Status](https://github.com/user-attachments/assets/3f8968a7-0862-417c-9150-e918e6e3009a)

---

## 10. Automation Loops & Repeating Cycles

Murphy runs three continuous business automation cycles that repeat alongside all other automations.

### 30-Day Traction Cycle

Every 30 days, the system measures per-tier performance trends:

- **Healthy** (≥3% conversion): Maintain current campaigns
- **Low** (1–3%): Auto-adjust channels, demographics, and messaging
- **Critical** (<1%): Propose paid advertising campaigns (requires founder HITL approval)

```python
from src.operations_cycle_engine import OperationsCycleEngine

ops = OperationsCycleEngine()
ops.start_traction_cycle()  # Auto-repeats every 30 days

# Evaluate traction mid-cycle
result = ops.evaluate_traction_cycle({
    "pro": {"impressions": 10000, "leads": 500, "conversions": 20},
    "enterprise": {"impressions": 2000, "leads": 50, "conversions": 3},
})

# Complete cycle → auto-starts next 30-day cycle
ops.complete_traction_cycle()
```

### 60-Day R&D Sprint Cycle

Every 60 days, the system builds everything queued during the cycle:

1. Competitive intelligence detects capability gaps
2. Gaps are routed to the R&D backlog with priority
3. At cycle end, queued items are built as modules
4. Remaining items carry over to the next 60-day cycle

```python
# Queue R&D items from competitive gap analysis
from src.competitive_intelligence_engine import CompetitiveIntelligenceEngine

ci = CompetitiveIntelligenceEngine()
ci.load_default_landscape()
ci.detect_gaps()
rd_items = ci.route_gaps_to_rd()

# Start R&D cycle with queued items
ops.start_rd_cycle(queued_items=[item.to_dict() for item in rd_items[:5]])

# At end of 60 days: build, gap-analyze, carry over remaining
ops.complete_rd_cycle(built_modules=[
    {"title": "visual_workflow", "status": "completed"},
])
```

### Instant Disruption Response

When something disrupts the industry, Murphy immediately:

1. Reviews what's being created and identifies gaps
2. Proposes non-plagiarized Murphy-native builds
3. Routes through HITL founder approval before execution

```python
from src.operations_cycle_engine import DisruptionSeverity

dr = ops.report_disruption(
    "CompetitorX", "Launched autonomous workflow builder",
    DisruptionSeverity.HIGH,
    ["autonomous_workflow", "visual_builder", "multi_llm_routing"]
)
# dr.our_gaps = ["autonomous_workflow", "visual_builder"]
# dr.status = AWAITING_APPROVAL  (founder HITL gate)

ops.approve_disruption_response(dr.response_id, "corey_post_founder")
```

---

## 11. Marketing Campaigns & Competitive Intelligence

### Adaptive Campaigns Per Tier

Marketing agents run campaigns to fill every pricing tier. When traction is low, campaigns auto-adjust demographics and channels. Paid advertising requires founder approval.

```python
from src.adaptive_campaign_engine import AdaptiveCampaignEngine

campaigns = AdaptiveCampaignEngine()
campaigns.bootstrap_tier_campaigns()

# Record performance and evaluate
campaigns.record_performance("pro", impressions=5000, leads=200, conversions=8)
result = campaigns.evaluate_and_act()
# Auto-adjusts low-traction tiers, proposes paid ads for critical tiers
```

### Adversarial Marketing & Competitive Intelligence

The system requests marketing information from competitors, builds competitive offering systems, identifies who they sell to and how, and routes capability gaps through R&D.

```python
from src.competitive_intelligence_engine import CompetitiveIntelligenceEngine

ci = CompetitiveIntelligenceEngine()
ci.load_default_landscape()  # Zapier, Make, n8n, UiPath, Power Automate

report = ci.full_competitive_analysis()
# report["summary"]["competitors_analyzed"] = 5
# report["summary"]["capability_gaps"] = 46
# report["summary"]["rd_items_created"] = 46
# report["competitive_strategies"] = [per-competitor adversarial strategies]
```

---

## 12. Data Archive, Retrieval & External Content Libraries

### Archiving Data

All system data is archived chronologically with category classification and automatic metric routing.

```python
from src.data_archive_manager import DataArchiveManager, ArchiveCategory

archive = DataArchiveManager()

# Archive metric data → auto-routed to analytics
archive.archive(
    title="Daily page views",
    data={"channel": "seo", "metric_name": "views", "value": 15000},
    category=ArchiveCategory.METRIC,
    tags=["seo", "daily"],
)

# Archive campaign results
archive.archive(
    title="Pro tier campaign Q1",
    data={"campaign_id": "camp-001", "conversions": 42},
    category=ArchiveCategory.CAMPAIGN,
)
```

### Chronological Retrieval

Retrieve data by time range, category, tags, or ID — always in chronological order.

```python
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
result = archive.retrieve_by_time_range(
    start=(now - timedelta(days=30)).isoformat(),
    end=now.isoformat(),
    category=ArchiveCategory.METRIC,
)
# result["local_records"] = [...chronologically ordered records...]
# result["external_refs"] = [...YouTube/Twitch VODs covering this period...]
```

### External Content Libraries (YouTube/Twitch VOD Storage)

High-volume data (telemetry streams, session recordings, large logs) is externalized to free platforms like YouTube and Twitch as VODs. This avoids paid storage while keeping data accessible chronologically.

```python
# Find large records that should be externalized
candidates = archive.get_externalization_candidates()

# After uploading to YouTube/Twitch, record the reference
archive.externalize_to_platform(
    record_ids=[r["record_id"] for r in candidates],
    platform="youtube",
    url="https://youtube.com/watch?v=session_archive_week9",
    title="Murphy Telemetry Archive — Week 9",
)

# Later: retrieve by time period (includes external VOD refs)
now = datetime.now(timezone.utc)
refs = archive.find_externalized_for_period(
    start=(now - timedelta(days=30)).isoformat(),
    end=now.isoformat(),
)
# refs = [{"platform": "youtube", "url": "...", "time_range_start": "...", ...}]
```

### Storage Summary

```python
summary = archive.get_storage_summary()
# {
#   "total_records": 18,
#   "local_records": 15,
#   "external_youtube": 2,
#   "external_twitch": 1,
#   "externalization_candidates": 3,
# }
```

---

## 13. Next Steps

- **Explore the API** — Browse all 70+ endpoints at http://localhost:8000/docs.
- **Try the onboarding wizard** — Open `onboarding_wizard.html` or run the CLI wizard for guided setup.
- **Read the docs** — See the [User Manual](<Murphy System/USER_MANUAL.md>) and [API Documentation](<Murphy System/API_DOCUMENTATION.md>) for detailed guides.
- **Run the tests** — Execute `pytest` from the repository root to verify your installation (8,200+ tests including 118 gap-closure regression tests).
- **Contribute** — Read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting changes.
