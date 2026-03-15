# Murphy System 1.0 — Manual Commissioning Test Plan

**Version:** 1.0  
**Date:** 2026-02-27  
**Repository:** IKNOWINOT/Murphy-System  
**Runtime Directory:** repository root  
**Purpose:** Step-by-step manual verification that every user-facing function of the Murphy System operates correctly, performed from the perspective of the user interface and API.

---

## How to Use This Document

This test plan is organized into **commissioning phases**. Work through each phase in order. Each test has:

- **Prerequisites** — what must be running or configured before the test
- **Steps** — exact commands or actions to perform
- **Expected Result** — what you should see if the system is working
- **Pass / Fail** — check the box when verified

> **Tip:** Open a second terminal window so you can keep the Murphy server running in one window while executing `curl` commands and serving HTML files in the other.

---

## Phase 1: Environment Setup and Startup

### Test 1.1 — Verify Python Version

**Steps:**
```bash
python3 --version
```

**Expected Result:** Python 3.10.x or higher (e.g., `Python 3.12.3`).

- [ ] **PASS** / **FAIL**

---

### Test 1.2 — Install Dependencies

**Steps:**
```bash
# (run from repository root)
pip install -r requirements_murphy_1.0.txt
```

**Expected Result:** All packages install without errors. Warnings about optional packages (torch, spacy) are acceptable.

- [ ] **PASS** / **FAIL**

**Notes:** _Record any install errors here._

---

### Test 1.3 — Configure Environment File

**Steps:**

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and set at minimum:
   ```
   GROQ_API_KEY=<your-groq-api-key>
   MURPHY_ENV=development
   ```
   > If you do not have a Groq API key, the system will still start but LLM-dependent features will return low-confidence results. Get a free key at https://console.groq.com.

**Expected Result:** `.env` file exists at the repository root with at least the fields above.

- [ ] **PASS** / **FAIL**

---

### Test 1.4 — Start Murphy System

**Steps:**
```bash
# (run from repository root)
./start_murphy_1.0.sh
```

**Expected Result:**

1. Script checks Python version (passes for 3.10+).
2. Virtual environment is created or reused.
3. Dependencies are installed/verified.
4. Required directories are created: `logs/`, `data/`, `modules/`, `sessions/`, `repositories/`.
5. Server starts and displays:
   ```
   Murphy System 1.0 is running!
   API Docs:    http://localhost:8000/docs
   Health:      http://localhost:8000/api/health
   Status:      http://localhost:8000/api/status
   Info:        http://localhost:8000/api/info
   ```
6. No fatal errors in the console output. Warnings about optional subsystems not loading are acceptable.

- [ ] **PASS** / **FAIL**

**Notes:** _Record any startup warnings or errors here._

---

### Test 1.5 — Verify Health Endpoint

**Steps** (in a second terminal):
```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

**Expected Result:** HTTP 200 with JSON containing at minimum:
```json
{
    "status": "healthy",
    "version": "1.0"
}
```

- [ ] **PASS** / **FAIL**

---

### Test 1.6 — Verify Status Endpoint

**Steps:**
```bash
curl -s http://localhost:8000/api/status | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON object showing system status including subsystem states. The response should include fields such as `status`, component information, and uptime data.

- [ ] **PASS** / **FAIL**

---

### Test 1.7 — Verify Info Endpoint

**Steps:**
```bash
curl -s http://localhost:8000/api/info | python3 -m json.tool
```

**Expected Result:** HTTP 200 with JSON containing system information (version, capabilities, component count, etc.).

- [ ] **PASS** / **FAIL**

---

### Test 1.8 — Verify Swagger API Documentation

**Steps:**

1. Open a web browser.
2. Navigate to: `http://localhost:8000/docs`

**Expected Result:** The FastAPI Swagger UI loads, showing all available API endpoints grouped by category. You can expand each endpoint to see its parameters, request body schema, and response schema.

- [ ] **PASS** / **FAIL**

---

## Phase 2: Core API Endpoint Testing

### Test 2.1 — Execute a Task

**Prerequisites:** Murphy server running (Phase 1).

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Analyze Q4 sales data",
    "task_type": "analysis",
    "parameters": {"quarter": "Q4", "year": 2024}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON response containing:
- A task ID or execution ID
- A result or status field
- Confidence scoring information

- [ ] **PASS** / **FAIL**

**Notes:** _Record the response structure here for future reference._

---

### Test 2.2 — Chat Interface

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What can you do?",
    "session_id": "test-session-001"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON response containing a text reply describing system capabilities.

- [ ] **PASS** / **FAIL**

---

### Test 2.3 — Create a Session

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/sessions/create \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON response containing a `session_id` or equivalent identifier.

- [ ] **PASS** / **FAIL**

---

### Test 2.4 — List Modules

**Steps:**
```bash
curl -s http://localhost:8000/api/modules | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON array or object listing available system modules.

- [ ] **PASS** / **FAIL**

---

### Test 2.5 — System Info (Extended)

**Steps:**
```bash
curl -s http://localhost:8000/api/system/info | python3 -m json.tool
```

**Expected Result:** HTTP 200 with detailed system information JSON.

- [ ] **PASS** / **FAIL**

---

## Phase 3: Document Operations

### Test 3.1 — Create a Document

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Document",
    "content": "This is a test document for commissioning."
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON response containing a `doc_id` (or similar identifier) for the created document.

- [ ] **PASS** / **FAIL**

**Record the `doc_id` returned:** ___________________

---

### Test 3.2 — Retrieve a Document

**Prerequisites:** A document was created in Test 3.1. Use the `doc_id` from that test.

**Steps:**
```bash
curl -s http://localhost:8000/api/documents/<DOC_ID> | python3 -m json.tool
```

Replace `<DOC_ID>` with the actual document ID.

**Expected Result:** HTTP 200 with the document content including title, content, and metadata.

- [ ] **PASS** / **FAIL**

---

### Test 3.3 — Magnify a Document

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/magnify \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with an expanded/detailed version of the document content.

- [ ] **PASS** / **FAIL**

---

### Test 3.4 — Simplify a Document

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/simplify \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a simplified version of the document content.

- [ ] **PASS** / **FAIL**

---

### Test 3.5 — Solidify a Document

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/solidify \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a finalized version of the document.

- [ ] **PASS** / **FAIL**

---

### Test 3.6 — Apply Gates to a Document

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/gates \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with gate processing results for the document.

- [ ] **PASS** / **FAIL**

---

### Test 3.7 — Get Document Blocks

**Steps:**
```bash
curl -s http://localhost:8000/api/documents/<DOC_ID>/blocks | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list or tree of content blocks within the document.

- [ ] **PASS** / **FAIL**

---

## Phase 4: Forms and Validation

### Test 4.1 — Submit a Task via Form

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/forms/task-execution \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Generate a weekly report",
    "task_type": "report",
    "parameters": {"period": "weekly"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a submission ID and task execution result.

- [ ] **PASS** / **FAIL**

---

### Test 4.2 — Validate a Task

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/forms/validation \
  -H "Content-Type: application/json" \
  -d '{
    "task_description": "Deploy to production",
    "task_type": "deployment",
    "parameters": {"environment": "production"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with validation results including confidence scores and any warnings/flags.

- [ ] **PASS** / **FAIL**

---

### Test 4.3 — Submit a Correction

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/forms/correction \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-task-001",
    "original_output": "The sales total was $50,000",
    "corrected_output": "The sales total was $52,500",
    "reason": "Original calculation missed international sales"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the correction was recorded.

- [ ] **PASS** / **FAIL**

---

### Test 4.4 — Upload a Plan

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/forms/plan-upload \
  -H "Content-Type: application/json" \
  -d '{
    "plan_name": "Q1 Marketing Plan",
    "content": "Launch social media campaign targeting B2B SaaS companies"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with the uploaded plan acknowledgment and an ID.

- [ ] **PASS** / **FAIL**

---

### Test 4.5 — Generate a Plan

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/forms/plan-generation \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Increase website traffic by 50%",
    "timeframe": "3 months",
    "budget": "moderate"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a generated plan.

- [ ] **PASS** / **FAIL**

---

### Test 4.6 — Retrieve a Form Submission

**Prerequisites:** Use a `submission_id` from any of the above form tests.

**Steps:**
```bash
curl -s http://localhost:8000/api/forms/submission/<SUBMISSION_ID> | python3 -m json.tool
```

**Expected Result:** HTTP 200 with the full submission record.

- [ ] **PASS** / **FAIL**

---

## Phase 5: Corrections and Learning

### Test 5.1 — Get Correction Patterns

**Steps:**
```bash
curl -s http://localhost:8000/api/corrections/patterns | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a JSON object or array of detected correction patterns (may be empty if no corrections have been submitted yet).

- [ ] **PASS** / **FAIL**

---

### Test 5.2 — Get Correction Statistics

**Steps:**
```bash
curl -s http://localhost:8000/api/corrections/statistics | python3 -m json.tool
```

**Expected Result:** HTTP 200 with statistics about corrections (total count, patterns detected, etc.).

- [ ] **PASS** / **FAIL**

---

### Test 5.3 — Get Training Data

**Steps:**
```bash
curl -s http://localhost:8000/api/corrections/training-data | python3 -m json.tool
```

**Expected Result:** HTTP 200 with training data derived from corrections.

- [ ] **PASS** / **FAIL**

---

## Phase 6: Human-in-the-Loop (HITL)

### Test 6.1 — Get Pending Interventions

**Steps:**
```bash
curl -s http://localhost:8000/api/hitl/interventions/pending | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list of pending interventions (may be empty initially).

- [ ] **PASS** / **FAIL**

---

### Test 6.2 — Get HITL Statistics

**Steps:**
```bash
curl -s http://localhost:8000/api/hitl/statistics | python3 -m json.tool
```

**Expected Result:** HTTP 200 with HITL statistics (intervention count, approval rate, etc.).

- [ ] **PASS** / **FAIL**

---

## Phase 7: MFGC (Magnify / Simplify / Solidify / Gate Control)

### Test 7.1 — Get MFGC State

**Steps:**
```bash
curl -s http://localhost:8000/api/mfgc/state | python3 -m json.tool
```

**Expected Result:** HTTP 200 with the current MFGC state including phase, confidence, and metrics.

- [ ] **PASS** / **FAIL**

---

### Test 7.2 — Get MFGC Configuration

**Steps:**
```bash
curl -s http://localhost:8000/api/mfgc/config | python3 -m json.tool
```

**Expected Result:** HTTP 200 with the current MFGC configuration (enabled status, gate settings).

- [ ] **PASS** / **FAIL**

---

### Test 7.3 — Update MFGC Configuration

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/mfgc/config \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "gate_synthesis": true,
    "emergency_gates": false,
    "audit_trail": true
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the configuration was updated.

- [ ] **PASS** / **FAIL**

---

### Test 7.4 — Setup MFGC Production Profile

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/mfgc/setup/production \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the production profile was loaded.

- [ ] **PASS** / **FAIL**

---

### Test 7.5 — Setup MFGC Development Profile

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/mfgc/setup/development \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the development profile was loaded.

- [ ] **PASS** / **FAIL**

---

### Test 7.6 — Setup MFGC Certification Profile

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/mfgc/setup/certification \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the certification profile was loaded.

- [ ] **PASS** / **FAIL**

---

## Phase 8: Integration Engine

### Test 8.1 — Add an Integration Request

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/integrations/add \
  -H "Content-Type: application/json" \
  -d '{
    "source": "https://github.com/psf/requests",
    "category": "http-library"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a `request_id` and status (likely `pending`). Note: End-to-end integration requires external credentials and optional dependencies.

- [ ] **PASS** / **FAIL**

**Record the `request_id` returned:** ___________________

---

### Test 8.2 — List Pending Integrations

**Steps:**
```bash
curl -s http://localhost:8000/api/integrations/pending | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list that includes the integration from Test 8.1.

- [ ] **PASS** / **FAIL**

---

### Test 8.3 — Approve an Integration

**Prerequisites:** Use the `request_id` from Test 8.1.

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/integrations/<REQUEST_ID>/approve \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

**Expected Result:** HTTP 200 confirming the integration was approved (or a descriptive error if prerequisites are unmet).

- [ ] **PASS** / **FAIL**

---

### Test 8.4 — List All Integrations

**Steps:**
```bash
curl -s http://localhost:8000/api/integrations/all | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list of all integrations across all statuses.

- [ ] **PASS** / **FAIL**

---

## Phase 9: Automation Engines

### Test 9.1 — Sales Automation: Generate Leads

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/automation/sales/generate_leads \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {"target_industry": "SaaS", "company_size": "10-50"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with lead generation results or a task acknowledgment.

- [ ] **PASS** / **FAIL**

---

### Test 9.2 — Marketing Automation: Create Content

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/automation/marketing/create_content \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {"content_type": "blog_post", "topic": "AI Automation"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with content creation results or a task acknowledgment.

- [ ] **PASS** / **FAIL**

---

### Test 9.3 — R&D Automation: Detect Bugs

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/automation/rnd/detect_bugs \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {"target": "murphy_system_1.0_runtime.py"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with bug detection results or a task acknowledgment.

- [ ] **PASS** / **FAIL**

---

### Test 9.4 — Business Automation: Project Management

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/automation/business/manage_project \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {"project_name": "Murphy 2.0 Planning"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with project management results or a task acknowledgment.

- [ ] **PASS** / **FAIL**

---

### Test 9.5 — Production Automation: Monitor

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/automation/production/monitor \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {"target": "all_systems"}
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with monitoring results or a task acknowledgment.

- [ ] **PASS** / **FAIL**

---

## Phase 10: Image Generation

### Test 10.1 — Get Image Styles

**Steps:**
```bash
curl -s http://localhost:8000/api/images/styles | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list of available image generation styles.

- [ ] **PASS** / **FAIL**

---

### Test 10.2 — Generate an Image

**Steps:**
```bash
curl -s -X POST http://localhost:8000/api/images/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A futuristic AI control room",
    "style": "digital_art"
  }' | python3 -m json.tool
```

**Expected Result:** HTTP 200 with image generation results (URL, base64, or metadata).

- [ ] **PASS** / **FAIL**

---

### Test 10.3 — Get Image Stats

**Steps:**
```bash
curl -s http://localhost:8000/api/images/stats | python3 -m json.tool
```

**Expected Result:** HTTP 200 with image generation statistics.

- [ ] **PASS** / **FAIL**

---

## Phase 11: Universal Integrations

### Test 11.1 — List Integration Services

**Steps:**
```bash
curl -s http://localhost:8000/api/universal-integrations/services | python3 -m json.tool
```

**Expected Result:** HTTP 200 with a list of available integration services.

- [ ] **PASS** / **FAIL**

---

### Test 11.2 — List Integration Categories

**Steps:**
```bash
curl -s http://localhost:8000/api/universal-integrations/categories | python3 -m json.tool
```

**Expected Result:** HTTP 200 with available integration categories.

- [ ] **PASS** / **FAIL**

---

### Test 11.3 — Get Integration Stats

**Steps:**
```bash
curl -s http://localhost:8000/api/universal-integrations/stats | python3 -m json.tool
```

**Expected Result:** HTTP 200 with integration usage statistics.

- [ ] **PASS** / **FAIL**

---

## Phase 12: Diagnostics

### Test 12.1 — Get Activation Diagnostics

**Steps:**
```bash
curl -s http://localhost:8000/api/diagnostics/activation | python3 -m json.tool
```

**Expected Result:** HTTP 200 with activation diagnostic information showing which subsystems loaded successfully.

- [ ] **PASS** / **FAIL**

---

### Test 12.2 — Get Last Activation Record

**Steps:**
```bash
curl -s http://localhost:8000/api/diagnostics/activation/last | python3 -m json.tool
```

**Expected Result:** HTTP 200 with the most recent activation record.

- [ ] **PASS** / **FAIL**

---

## Phase 13: Terminal UI — Architect (terminal_architect.html)

### Test 13.0 — Serve the HTML Files

**Prerequisites:** Murphy server running on port 8000.

**Steps:**

1. Open a new terminal window.
2. Navigate to the Murphy System directory:
   ```bash
   # (run from repository root)
   python3 -m http.server 8090
   ```
3. Leave this running.

**Expected Result:** HTTP server starts on port 8090.

- [ ] **PASS** / **FAIL**

---

### Test 13.1 — Load Architect Terminal

**Steps:**

1. Open a web browser.
2. Navigate to: `http://localhost:8090/terminal_architect.html?apiPort=8000`

**Expected Result:**
- The page loads with a dark neon terminal theme (green text on black background).
- The header shows "MURPHY SYSTEM" with MFGC toggle, profile buttons (PROD, CERT, DEV), and a TERM toggle button.
- The left panel is the terminal input/output area.
- The right panel shows system state with metrics grid, confidence bar, and Murphy Index.
- Six tabs are visible at the bottom of the right panel: **GATES**, **BLOCKS**, **PREVIEW**, **LIBRARIAN**, **CONFIG**, **EVENTS**.

- [ ] **PASS** / **FAIL**

---

### Test 13.2 — Send a Chat Message

**Steps:**

1. In the Architect terminal, click on the input field at the bottom.
2. Type: `What can you do?`
3. Press Enter.

**Expected Result:**
- Your message appears in the terminal output prefixed with `>` or a user indicator.
- A response from Murphy appears below showing system capabilities.
- The right panel metrics may update (confidence, phase).

- [ ] **PASS** / **FAIL**

---

### Test 13.3 — Toggle MFGC

**Steps:**

1. Click the **MFGC** toggle button in the header.

**Expected Result:**
- The MFGC state toggles between enabled and disabled.
- The right panel state indicators update accordingly.

- [ ] **PASS** / **FAIL**

---

### Test 13.4 — Switch MFGC Profiles

**Steps:**

1. Click the **PROD** button in the header.
2. Observe the state panel update.
3. Click the **DEV** button.
4. Observe the state panel update.
5. Click the **CERT** button.
6. Observe the state panel update.

**Expected Result:**
- Each profile button sends a setup request to the API.
- The right panel updates to reflect the selected profile's configuration.
- The terminal output shows confirmation of profile changes.

- [ ] **PASS** / **FAIL**

---

### Test 13.5 — Navigate Tabs

**Steps:**

1. Click the **GATES** tab — verify gate information is displayed.
2. Click the **BLOCKS** tab — verify block tree or list is shown.
3. Click the **PREVIEW** tab — verify preview content is shown.
4. Click the **LIBRARIAN** tab — verify system context is shown.
5. Click the **CONFIG** tab — verify toggle controls are shown (enabled, gate_synthesis, emergency_gates, audit_trail).
6. Click the **EVENTS** tab — verify event stream is shown.

**Expected Result:** Each tab switches the content in the right panel without page reload. Content specific to each tab category is displayed.

- [ ] **PASS** / **FAIL**

---

### Test 13.6 — Update Configuration via CONFIG Tab

**Steps:**

1. Click the **CONFIG** tab.
2. Toggle the **gate_synthesis** setting.
3. Toggle the **audit_trail** setting.

**Expected Result:** Configuration changes are sent to the API and confirmed in the terminal output.

- [ ] **PASS** / **FAIL**

---

## Phase 14: Terminal UI — Integrated (terminal_integrated.html)

### Test 14.1 — Load Integrated Terminal

**Steps:**

1. Navigate to: `http://localhost:8090/terminal_integrated.html?apiPort=8000`

**Expected Result:**
- The page loads with a terminal interface and quick command buttons at the top.
- Quick buttons visible: **Help**, **API Endpoints**, **System Status**, **Submit Task**, **Validate Task**, **Submit Correction**, **Statistics**, **Clear**.

- [ ] **PASS** / **FAIL**

---

### Test 14.2 — Click Help Button

**Steps:**

1. Click the **Help** button.

**Expected Result:** The terminal output displays a help message listing available commands and their descriptions.

- [ ] **PASS** / **FAIL**

---

### Test 14.3 — Click API Endpoints Button

**Steps:**

1. Click the **API Endpoints** button.

**Expected Result:** The terminal output displays a list of available API endpoints.

- [ ] **PASS** / **FAIL**

---

### Test 14.4 — Click System Status Button

**Steps:**

1. Click the **System Status** button.

**Expected Result:** The terminal output displays the current system status, fetched from the API.

- [ ] **PASS** / **FAIL**

---

### Test 14.5 — Submit a Task

**Steps:**

1. Click the **Submit Task** button.
2. When prompted, enter a task description (e.g., `Analyze customer feedback`).
3. Press Enter or confirm.

**Expected Result:** The terminal shows the task was submitted and displays the execution result.

- [ ] **PASS** / **FAIL**

---

### Test 14.6 — Validate a Task

**Steps:**

1. Click the **Validate Task** button.
2. When prompted, enter a task description (e.g., `Deploy new feature`).
3. Press Enter or confirm.

**Expected Result:** The terminal shows validation results including confidence scores.

- [ ] **PASS** / **FAIL**

---

### Test 14.7 — Submit a Correction

**Steps:**

1. Click the **Submit Correction** button.
2. When prompted, enter correction details.
3. Press Enter or confirm.

**Expected Result:** The terminal confirms the correction was recorded.

- [ ] **PASS** / **FAIL**

---

### Test 14.8 — View Statistics

**Steps:**

1. Click the **Statistics** button.

**Expected Result:** The terminal displays correction and system statistics.

- [ ] **PASS** / **FAIL**

---

### Test 14.9 — Type Commands Directly

**Steps:**

1. Type `status` in the input field and press Enter.
2. Type `help` and press Enter.
3. Type `blocks` and press Enter.
4. Type `stats` and press Enter.

**Expected Result:** Each command produces relevant output in the terminal.

- [ ] **PASS** / **FAIL**

---

### Test 14.10 — Clear Terminal

**Steps:**

1. Click the **Clear** button.

**Expected Result:** The terminal output is cleared.

- [ ] **PASS** / **FAIL**

---

## Phase 15: Terminal UI — Worker (terminal_worker.html)

### Test 15.1 — Load Worker Terminal

**Steps:**

1. Navigate to: `http://localhost:8090/terminal_worker.html?apiPort=8000`

**Expected Result:**
- The page loads with a worker-focused terminal UI.
- Quick action buttons are visible: **System Status**, **Show Help**, **Clear Terminal**, **Task History**.
- The right panel (if present) shows task status and metrics.

- [ ] **PASS** / **FAIL**

---

### Test 15.2 — Check System Status

**Steps:**

1. Click the **System Status** button (or type `/status`).

**Expected Result:** System status is displayed in the terminal.

- [ ] **PASS** / **FAIL**

---

### Test 15.3 — Submit a Task via Chat

**Steps:**

1. Type a task in the input field: `Generate a summary report of system health`
2. Press Enter.

**Expected Result:** The task is submitted via `/api/chat` and a response is displayed.

- [ ] **PASS** / **FAIL**

---

### Test 15.4 — Toggle MFGC from Worker

**Steps:**

1. Type `/mfgc on` and press Enter.
2. Observe the header MFGC indicator.
3. Type `/mfgc off` and press Enter.

**Expected Result:** MFGC state toggles and the header indicator updates.

- [ ] **PASS** / **FAIL**

---

### Test 15.5 — Show Help

**Steps:**

1. Click the **Show Help** button (or type `/help`).

**Expected Result:** Help information is displayed listing available commands.

- [ ] **PASS** / **FAIL**

---

## Phase 16: Terminal UI — Enhanced (terminal_enhanced.html)

### Test 16.1 — Load Enhanced Terminal

**Steps:**

1. Navigate to: `http://localhost:8090/terminal_enhanced.html?apiPort=8000`

**Expected Result:**
- The page loads with a terminal interface.
- Status badge shows Active/Offline.
- Quick buttons visible: **help**, **status**, **commands**, **state get**, **setup get**, **clear**.

- [ ] **PASS** / **FAIL**

---

### Test 16.2 — Click Status Button

**Steps:**

1. Click the **status** button.

**Expected Result:** System status is displayed in the terminal.

- [ ] **PASS** / **FAIL**

---

### Test 16.3 — Click Commands Button

**Steps:**

1. Click the **commands** button.

**Expected Result:** A list of available commands grouped by category is displayed.

- [ ] **PASS** / **FAIL**

---

### Test 16.4 — State Management

**Steps:**

1. Click the **state get** button — observe state displayed.
2. Type `state set test_key test_value` and press Enter.
3. Click the **state get** button — verify `test_key` appears.
4. Type `state clear` and press Enter.

**Expected Result:** State is stored, retrieved, and cleared correctly.

- [ ] **PASS** / **FAIL**

---

### Test 16.5 — Setup Management

**Steps:**

1. Click the **setup get** button — observe setup configuration displayed.

**Expected Result:** Current setup configuration is shown.

- [ ] **PASS** / **FAIL**

---

## Phase 17: Landing Page (murphy_landing_page.html)

### Test 17.1 — Load Landing Page

**Steps:**

1. Navigate to: `http://localhost:8090/murphy_landing_page.html`

**Expected Result:**
- The page loads with a dark neon theme.
- The hero section shows "Murphy System" title with version badge.
- Sections visible: Live stats bar, module grid, capabilities, pricing tiers, community links.

- [ ] **PASS** / **FAIL**

---

### Test 17.2 — Verify Links

**Steps:**

1. Check that the GitHub repository link points to: `https://github.com/IKNOWINOT/Murphy-System`
2. Check that community links (Issues, Pull Requests, Wiki) lead to valid GitHub URLs.

**Expected Result:** All links are correct and point to the IKNOWINOT/Murphy-System repository.

- [ ] **PASS** / **FAIL**

---

## Phase 18: Automated Test Suite

### Test 18.1 — Run Core Test Suite

**Steps:**
```bash
# (run from repository root)
python -m pytest tests/ -v --tb=short 2>&1 | head -100
```

**Expected Result:** Tests execute. Note the number of passed, failed, and skipped tests. Some failures may be expected if optional dependencies (torch, spacy) are not installed.

- [ ] **PASS** / **FAIL**

**Record:** ___ passed, ___ failed, ___ skipped

---

### Test 18.2 — Run Import Tests

**Steps:**
```bash
# (run from repository root)
python tests/test_basic_imports.py
```

**Expected Result:**
```
Results: 5/5 tests passed
```

- [ ] **PASS** / **FAIL**

---

## Phase 19: End-to-End Workflow Test

### Test 19.1 — Full Task Lifecycle

This test verifies the complete flow from task submission through execution and correction.

**Steps:**

1. **Submit a task:**
   ```bash
   curl -s -X POST http://localhost:8000/api/execute \
     -H "Content-Type: application/json" \
     -d '{
       "task_description": "Calculate total revenue for Q1 2024",
       "task_type": "analysis",
       "parameters": {"quarter": "Q1", "year": 2024}
     }' | python3 -m json.tool
   ```
   Record the task/execution ID from the response.

2. **Submit a correction on the task:**
   ```bash
   curl -s -X POST http://localhost:8000/api/forms/correction \
     -H "Content-Type: application/json" \
     -d '{
       "task_id": "<TASK_ID_FROM_STEP_1>",
       "original_output": "<output from step 1>",
       "corrected_output": "Revenue was $1.2M, not $1.1M",
       "reason": "Missed recurring subscription revenue"
     }' | python3 -m json.tool
   ```

3. **Verify correction was recorded:**
   ```bash
   curl -s http://localhost:8000/api/corrections/statistics | python3 -m json.tool
   ```

4. **Check that patterns were extracted:**
   ```bash
   curl -s http://localhost:8000/api/corrections/patterns | python3 -m json.tool
   ```

**Expected Result:** The complete lifecycle works: task executes, correction is recorded, and the learning system tracks it.

- [ ] **PASS** / **FAIL**

---

### Test 19.2 — Full Document Lifecycle

This test verifies the document creation through MFGC processing.

**Steps:**

1. **Create a document:**
   ```bash
   curl -s -X POST http://localhost:8000/api/documents \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Product Launch Plan",
       "content": "We plan to launch the new product in Q2 with a focus on enterprise customers."
     }' | python3 -m json.tool
   ```
   Record the `doc_id`.

2. **Magnify the document:**
   ```bash
   curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/magnify \
     -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
   ```

3. **Simplify the document:**
   ```bash
   curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/simplify \
     -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
   ```

4. **Solidify the document:**
   ```bash
   curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/solidify \
     -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
   ```

5. **Apply gates:**
   ```bash
   curl -s -X POST http://localhost:8000/api/documents/<DOC_ID>/gates \
     -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
   ```

6. **Get blocks:**
   ```bash
   curl -s http://localhost:8000/api/documents/<DOC_ID>/blocks | python3 -m json.tool
   ```

**Expected Result:** The document passes through the full MFGC cycle (Magnify → Simplify → Solidify → Gates) and blocks are retrievable.

- [ ] **PASS** / **FAIL**

---

### Test 19.3 — UI-Driven Workflow (Architect Terminal)

**Steps:**

1. Open `http://localhost:8090/terminal_architect.html?apiPort=8000`
2. Type a message: `Create a deployment plan for production release`
3. Press Enter and wait for the response.
4. Click the **GATES** tab — verify gates data appears.
5. Click the **CONFIG** tab — toggle `gate_synthesis` on.
6. Click **PROD** profile button — verify profile loads.
7. Click the **BLOCKS** tab — verify block hierarchy.
8. Click the **EVENTS** tab — verify events are listed.

**Expected Result:** All UI interactions produce correct responses and display relevant data.

- [ ] **PASS** / **FAIL**

---

## Phase 20: Shutdown and Cleanup

### Test 20.1 — Graceful Shutdown

**Steps:**

1. Go to the terminal running Murphy.
2. Press `Ctrl+C`.

**Expected Result:** The server shuts down gracefully without errors.

- [ ] **PASS** / **FAIL**

---

### Test 20.2 — Restart and Verify

**Steps:**

1. Start Murphy again:
   ```bash
   ./start_murphy_1.0.sh
   ```
2. Verify health:
   ```bash
   curl -s http://localhost:8000/api/health | python3 -m json.tool
   ```

**Expected Result:** System restarts successfully and health check passes.

- [ ] **PASS** / **FAIL**

---

## Commissioning Summary

After completing all phases, fill in the summary below:

| Phase | Description | Tests | Passed | Failed | Notes |
|-------|-------------|-------|--------|--------|-------|
| 1 | Environment Setup & Startup | 8 | | | |
| 2 | Core API Endpoints | 5 | | | |
| 3 | Document Operations | 7 | | | |
| 4 | Forms and Validation | 6 | | | |
| 5 | Corrections and Learning | 3 | | | |
| 6 | Human-in-the-Loop | 2 | | | |
| 7 | MFGC Control | 6 | | | |
| 8 | Integration Engine | 4 | | | |
| 9 | Automation Engines | 5 | | | |
| 10 | Image Generation | 3 | | | |
| 11 | Universal Integrations | 3 | | | |
| 12 | Diagnostics | 2 | | | |
| 13 | Architect Terminal UI | 6 | | | |
| 14 | Integrated Terminal UI | 10 | | | |
| 15 | Worker Terminal UI | 5 | | | |
| 16 | Enhanced Terminal UI | 5 | | | |
| 17 | Landing Page | 2 | | | |
| 18 | Automated Tests | 2 | | | |
| 19 | End-to-End Workflows | 3 | | | |
| 20 | Shutdown & Cleanup | 2 | | | |
| **TOTAL** | | **81** | | | |

**Overall Result:** ☐ COMMISSIONED / ☐ REQUIRES REMEDIATION

**Commissioning Date:** ____________________  
**Commissioned By:** ____________________  
**Notes:** ____________________
