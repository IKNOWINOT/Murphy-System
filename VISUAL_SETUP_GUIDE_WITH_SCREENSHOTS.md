# Murphy System - Complete Visual Setup Guide with Screenshots

**Generated:** February 9, 2026  
**Purpose:** Step-by-step visual guide for setting up Murphy System from scratch  
**With:** Actual screenshot images for each major step

---

## 📋 Table of Contents

**Why this UI?** The architect terminal UI is used for validation because it surfaces activation previews, gate edits, timer/trigger scheduling, and business automation summaries in one place while matching the requested terminal-architect look and feel. The legacy integrated UIs remain available for quick command execution, but the architect UI provides the governance and execution visibility needed for production readiness.

**Why the screenshots?** Each capture records operator inputs and system responses so the team can grade capability coverage and feed the results back into the learning loop that tunes automation behavior.

1. [Prerequisites Check](#prerequisites-check)
2. [Initial Setup](#initial-setup)
3. [Virtual Environment Configuration](#virtual-environment-configuration)
4. [Dependency Installation](#dependency-installation)
5. [System Configuration](#system-configuration)
6. [Starting Murphy](#starting-murphy)
7. [Verification & Testing](#verification-testing)
8. [Optional UI Access](#optional-ui-access-terminal-ui)
9. [Architect Terminal Walkthrough](#architect-terminal-walkthrough)
10. [Terminal UI Walkthroughs](#terminal-ui-walkthroughs)
11. [Available API Endpoints](#available-api-endpoints)
12. [Block Command Tree Walkthrough](#block-command-tree-walkthrough)
13. [Gate Policy Updates & Timers](#gate-policy-updates--timers)
14. [Control Metrics Preview](#control-metrics-preview)
15. [Next Steps](#next-steps)

---

## Prerequisites Check

### Step 1: Check Python Version

```bash
python3 --version
```

![Python Version Check](docs/screenshots/01_python_version.png)

**Requirements:**
- ✅ Python 3.11 or higher required
- ❌ Python 3.10 or lower will not work

**What you should see:**
- Python version output showing 3.11 or higher
- In the screenshot: Python 3.12.3 ✓

---

### Step 2: Navigate to Murphy Integrated Directory

```bash
cd "Murphy System/murphy_integrated"
pwd
ls -la | head -5
```

![Navigate to Directory](docs/screenshots/02_navigate.png)

**What you should see:**
- Current directory path confirmed
- Directory listing showing Murphy files (.env.example, API_DOCUMENTATION.md, etc.)
- This is where all Murphy System files are located

---

## Initial Setup

### Step 3: Create Virtual Environment

```bash
python3 -m venv venv
ls -d venv/
```

![Create Virtual Environment](docs/screenshots/03_venv_create.png)

**What happens:**
- Creates a new directory called `venv/`
- Isolates Murphy's dependencies from system Python
- Takes about 5-10 seconds

**Verification:**
- ✅ venv/ directory should exist
- ✅ Success message displayed

---

### Step 4: Activate Virtual Environment and Install Dependencies

```bash
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

pip install --upgrade pip
pip install fastapi uvicorn pydantic aiohttp
```

![Install Dependencies](docs/screenshots/04_install_deps.png)

**What gets installed:**
- **FastAPI** 0.128.6 - Web framework for the API
- **Uvicorn** 0.40.0 - ASGI server to run the application
- **Pydantic** 2.12.5 - Data validation
- **aiohttp** 3.13.3 - Async HTTP client

**Visual Indicator:**
- Your prompt should show `(venv)` at the beginning
- Pip version 24.0 or higher shown
- All packages successfully installed

**Time:** ~30 seconds - 2 minutes depending on connection

---

## System Configuration

### Step 5: Create Configuration File (.env)

```bash
cat > .env << 'EOF'
MURPHY_VERSION=1.0.0
MURPHY_ENV=development
MURPHY_PORT=6666
# GROQ_API_KEY=your_key_here  # Optional
EOF

cat .env
```

![Create Configuration](docs/screenshots/05_config.png)

**Key Settings:**
- `MURPHY_PORT=6666` - Port where Murphy will run
- `MURPHY_ENV=development` - Development mode
- API keys commented out (optional for basic functionality)

**Optional:** Add a real Groq API key from https://console.groq.com for full LLM features

**What you should see:**
- ✅ Configuration file content displayed
- ✅ Three core settings defined

---

### Step 6: Create Required Directories

```bash
mkdir -p logs data modules sessions repositories
ls -d logs data modules sessions repositories
```

![Create Directories](docs/screenshots/06_directories.png)

**Directory purposes:**
- `logs/` - System logs and runtime information
- `data/` - Persistent data storage
- `modules/` - Dynamically loaded modules
- `sessions/` - Active session data
- `repositories/` - Cloned GitHub repositories (for integration feature)

**Verification:**
- ✅ All five directories listed
- ✅ No errors displayed

---

## Starting Murphy

### Step 7: Start Murphy System

```bash
python3 murphy_system_1.0_runtime.py
# OR run in background:
nohup python3 murphy_system_1.0_runtime.py > startup.log 2>&1 &
```

![Murphy Startup](docs/screenshots/07_startup.png)

**What happens:**
- Murphy initializes all components
- Starts FastAPI server
- Binds to port 6666
- Takes 2-5 seconds to fully start

**Key indicators in screenshot:**
- ✅ "MURPHY SYSTEM 1.0.0 - READY"
- ✅ "Application startup complete"
- ✅ "Uvicorn running on http://0.0.0.0:6666"

**Warnings are normal** - they indicate optional components that can be added later with additional dependencies.

---

## Verification & Testing

### Step 8: Check Health Endpoint

```bash
curl http://localhost:6666/api/health
```

![Health Check](docs/screenshots/08_health_check.png)

**Expected Response:**
```json
{
    "status": "healthy",
    "version": "1.0.0"
}
```

**If you see this, Murphy is running correctly!**

**What you should see:**
- ✅ `"status": "healthy"`
- ✅ `"version": "1.0.0"`
- ✅ Green success indicator

---

### Step 9: Check System Info Endpoint

```bash
curl http://localhost:6666/api/info
```

![System Information](docs/screenshots/09_system_info.png)

**What this shows:**
- System name and version
- All capabilities Murphy provides
- Loaded components
- Architecture information

**Expected fields:**
- ✅ `"name": "Murphy System"`
- ✅ `"version": "1.0.0"`
- ✅ `"capabilities"` array with features
- ✅ JSON formatted response

---

### Step 10: List Available API Endpoints

```bash
curl -s http://localhost:6666/openapi.json | python3 -c "import json, sys; data = json.load(sys.stdin); [print(f'{method.upper()} {path}') for path, methods in data['paths'].items() for method in methods.keys()]"
```

![API Endpoints](docs/screenshots/10_endpoints.png)

**Available Endpoints:**
- POST /api/execute
- GET /api/health
- GET /api/status
- GET /api/info
- POST /api/integrations/add
- POST /api/integrations/{request_id}/approve
- POST /api/integrations/{request_id}/reject
- GET /api/integrations/{status}
- POST /api/automation/{engine_name}/{action}
- GET /api/modules

**Endpoint categories:**
1. **System endpoints** - health, status, info
2. **Execution endpoints** - execute tasks
3. **Integration endpoints** - add/approve/reject integrations
4. **Automation endpoints** - business automation engines
5. **Module endpoints** - list loaded modules

---

### Step 11: Optional UI Access (Terminal UI)

Runtime 1.0 does not serve a web UI by default. To view the terminal UI, navigate to `Murphy System/murphy_integrated` and serve the `murphy_ui_integrated_terminal.html` file locally:

```bash
cd "Murphy System/murphy_integrated"
python -m http.server 8090
```

Then open:

```
http://localhost:8090/murphy_ui_integrated_terminal.html
```

If you start the HTTP server from a different directory, adjust the URL path to match the served location of the HTML file.

**Browser note:** Some browsers block port 6666. If you run the API on a different port (e.g., 8000), append `?apiPort=8000` to any UI URL so it targets the correct port:

```
http://localhost:8090/murphy_ui_integrated_terminal.html?apiPort=8000
```

![Terminal UI](docs/screenshots/12_ui_terminal.png)

**What you'll see:**
- Terminal-styled dashboard with system status
- Tabs for execute, forms, corrections, sessions, and integrations

**Note:** Some tabs may show errors unless optional endpoints are wired to runtime 1.0.

---

### Step 12: Open the Architect Terminal UI

Launch the architect terminal UI (the production UI redirect points here) and target the runtime port. Use `?legacy=true` if you must view the older light-theme UI.

```
http://localhost:8090/murphy_integrated/terminal_architect.html?apiPort=8000
```

![Architect Terminal Overview](docs/screenshots/24_ui_architect_overview.png)

---

## Architect Terminal Walkthrough

### Step 13: Run an Automation Request

Submit a full onboarding automation request in the architect terminal input (marketing → executive → operations → QA → HITL → execution). Include the operating region so regulatory sources are selected.

![Architect Terminal User Input](docs/screenshots/30_ui_architect_user_inputs.png)

![Architect Terminal User Command](docs/screenshots/31_ui_architect_user_command.png)

![Architect Terminal Compliance Readiness](docs/screenshots/32_ui_architect_compliance.png)

![Architect Terminal Preview](docs/screenshots/25_ui_architect_preview.png)

![Architect Terminal Dynamic Implementation](docs/screenshots/33_ui_architect_dynamic_implementation.png)

![Architect Terminal Dynamic Implementation Details](docs/screenshots/34_ui_architect_dynamic_implementation_details.png)

![Architect Terminal Gate Sequencing](docs/screenshots/35_ui_architect_dynamic_gate_sequence.png)

**Observed behavior:** the terminal returns activation preview JSON showing gates, swarm tasks, governance plans, librarian conditions, delivery readiness (99% coverage target + compliance status), and region-aware external API sensor plans sourced from the runtime response. The expanded dynamic implementation stages include gate sequencing, compliance review, automation loop, multi-loop scheduling, trigger schedule, and monitoring feedback.

**Dynamic implementation check:** the preview includes a dynamic implementation plan that stages requirements capture, gate alignment, compliance sequencing, workload distribution, execution strategy, and human release status so the system can iterate across multiple projects. The `wiring_gaps` and `information_gaps` fields highlight what still needs dynamic wiring or additional input for capability grading and learning.

---

### Step 14: Review Librarian Context & Conditions

Open the **LIBRARIAN** tab to see the live librarian context, matched knowledge topics, and approval-required conditions that inform gate synthesis.

![Architect Terminal Librarian](docs/screenshots/26_ui_architect_librarian.png)

---

### Step 15: Update Gate Policies in Real Time

Use **Update Gates** in the Gates tab (or `/updategates`) to adjust thresholds and immediately review the refreshed gate chain and trigger plan.

![Architect Terminal Gate Update](docs/screenshots/27_ui_architect_gate_update.png)

---

### Step 16: Inspect Block Command Tree and Magnify

Switch to **BLOCKS** to inspect the generated block tree, then run **Magnify** to expand the request into deeper sub-tasks.

![Architect Terminal Blocks](docs/screenshots/28_ui_architect_blocks.png)

![Architect Terminal Magnify](docs/screenshots/29_ui_architect_blocks_magnify.png)

---

## Terminal UI Walkthroughs

### Step 17: Integrated Terminal Execute Tab

Submit a task through the terminal-style execute tab.

![Integrated Terminal Execute](docs/screenshots/15_ui_integrated_terminal_execute.png)

---

### Step 18: Integrated Terminal Command Flow

Use the command interface to submit a task payload.

![Terminal Integrated Submit](docs/screenshots/16_ui_terminal_integrated_submit.png)

---

### Step 19: Architect Terminal Flow Step

Issue a high-level architecture command and observe the stage handoff.

![Architect Terminal Flow](docs/screenshots/17_ui_terminal_architect_flow.png)

---

### Step 20: Worker Terminal Status Flow

Run a worker status command and confirm the next-step prompt.

![Worker Terminal Status](docs/screenshots/18_ui_terminal_worker_status.png)

---

### Step 21: Access API Documentation in Browser

Open your browser and navigate to:

```
http://localhost:6666/docs
```

![API Documentation](docs/screenshots/11_api_docs.png)

**What you'll see:**
- Interactive Swagger UI
- All available API endpoints listed
- Request/response schemas
- "Try it out" functionality for testing

**Features:**
- ✅ Interactive API testing
- ✅ Complete parameter documentation
- ✅ Response examples
- ✅ Authentication methods (if configured)

---

## Block Command Tree Walkthrough

### Step 22: Architect Block Tree Expansion

Open the architect terminal, run a high-level command, and use magnify/simplify/solidify to expand the block tree.

![Architect Block Tree](docs/screenshots/19_ui_architect_block_tree.png)

---

### Step 23: Legacy Integrated Activation Preview (Optional)

If you still need the legacy integrated UI, run a request there to see the planned subsystems, gates, swarm tasks, and capability alignment gaps. The architect UI already exposes the same activation preview.

![Legacy Activation Preview](docs/screenshots/25_ui_production_execution.png)

---

### Step 24: Legacy Integrated Capability Tests (Optional)

Inspect the activation preview JSON in the legacy integrated UI to see capability test errors and successful subsystem checks.

![Legacy Capability Tests](docs/screenshots/27_ui_production_control_metrics.png)

---

### Step 25: Legacy Integrated Self-Automation Loop Output (Optional)

Use the legacy integrated UI execution output to confirm business automation loop results and self-operation status.

![Legacy Automation Loop](docs/screenshots/25_ui_production_execution.png)

---

## Gate Policy Updates & Timers

### Step 26: Update Gate Policies and Trigger Plans

Use **Update Gates** in the architect UI to adjust gate thresholds (executive, operations, QA, HITL, execution) and immediately see the timer/trigger plan update.

![Gate Policy Update](docs/screenshots/27_ui_architect_gate_update.png)

---

## Control Metrics Preview

### Step 27: Verify Control-Metric Gate Context (Optional)

Run a request and confirm the gate synthesis output includes control metrics (setpoints, sensor feedback, control effect) aligned to the request domain. The legacy integrated UI screenshot below shows the control metrics format.

![Legacy Control Metrics](docs/screenshots/27_ui_production_control_metrics.png)

---

## Available API Endpoints

### Complete Endpoint Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | /api/health | Health check |
| GET | /api/status | System status |
| GET | /api/info | System information |
| POST | /api/execute | Execute a task |
| POST | /api/documents/{doc_id}/gates | Update gate policies |
| POST | /api/integrations/add | Add new integration |
| POST | /api/integrations/{id}/approve | Approve integration |
| POST | /api/integrations/{id}/reject | Reject integration |
| GET | /api/integrations/{status} | List integrations |
| POST | /api/automation/{engine}/{action} | Run automation |
| GET | /api/modules | List loaded modules |

---

## Next Steps

### ✅ Your System is Running!

Murphy System is now operational. You can:

1. **Access API Documentation**
   - Visit: http://localhost:6666/docs
   - Explore all endpoints interactively
   - Test API calls directly in browser

2. **Add API Keys** (Optional - for full functionality)
   - Edit `.env` file
   - Add `GROQ_API_KEY=your_key_here`
   - Get free key at: https://console.groq.com
   - Restart Murphy

3. **Install Additional Dependencies** (Optional)
   - For full features: `pip install -r requirements_murphy_1.0.txt`
   - Takes 3-5 minutes

4. **Try Advanced Features**
   - GitHub integration
   - Business automation
   - Self-improvement
   - Multi-agent coordination

---

## Troubleshooting

### Murphy won't start

**Check logs:**
```bash
tail -50 startup.log
```

**Common issues:**
- Port 6666 already in use → Change `MURPHY_PORT` in `.env`
- Missing dependencies → Run `pip install fastapi uvicorn pydantic`
- Python too old → Must be 3.11+

### API returns errors

**Without API keys:**
- Some features won't work (LLM-based tasks)
- Add `GROQ_API_KEY` to `.env` for full functionality

**Check if Murphy is running:**
```bash
curl http://localhost:6666/api/health
```

### Can't access http://localhost:6666

**Check if Murphy process is running:**
```bash
ps aux | grep murphy_system_1.0_runtime.py
```

**Restart Murphy:**
```bash
# Find and stop process
ps aux | grep murphy_system_1.0_runtime.py
kill <PID>

# Start again
python3 murphy_system_1.0_runtime.py
```

---

## Summary - Setup Complete! ✅

You've successfully:

- ✅ Verified Python 3.11+ installation
- ✅ Created virtual environment
- ✅ Installed core dependencies
- ✅ Configured Murphy System
- ✅ Created required directories
- ✅ Started Murphy System
- ✅ Verified system is running
- ✅ Accessed API endpoints
- ✅ Viewed API documentation

**Total setup time:** ~10 minutes

**Murphy System is ready to use!** 🚀

---

## Screenshot Reference

All screenshots in this guide are located in:
```
docs/screenshots/
├── 01_python_version.png    - Python version verification
├── 02_navigate.png           - Directory navigation
├── 03_venv_create.png        - Virtual environment creation
├── 04_install_deps.png       - Dependency installation
├── 05_config.png             - Configuration file
├── 06_directories.png        - Directory structure
├── 07_startup.png            - Murphy startup logs
├── 08_health_check.png       - Health endpoint response
├── 09_system_info.png        - System information
├── 10_endpoints.png          - Available API endpoints
└── 11_api_docs.png           - API documentation browser view
```

---

## 📚 Related Documentation

- **Quick Reference:** [QUICK_SETUP_REFERENCE.md](QUICK_SETUP_REFERENCE.md)
- **Complete Guide:** [GETTING_STARTED.md](GETTING_STARTED.md)
- **Requirements:** [READY_TO_USE_CHECKLIST.md](READY_TO_USE_CHECKLIST.md)
- **Configuration:** [.env.example](Murphy%20System/murphy_integrated/.env.example)

---

**Document Version:** 2.0 (with screenshots)  
**Created:** February 9, 2026  
**Last Updated:** February 9, 2026  
**Status:** Complete visual setup guide with 11 screenshot images
