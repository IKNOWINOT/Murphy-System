# Murphy System — Testing Guide

## One-Button Run

### macOS / Linux
```bash
bash run.sh
```

### Windows
Double-click **run.bat**, or in Command Prompt:
```cmd
run.bat
```

### What it does
1. Checks Python 3.10+ is installed
2. Creates a virtual environment (`.venv/`)
3. Installs core dependencies (~30 seconds)
4. Generates a `.env` file in development mode (no API key required)
5. Starts the server on **http://localhost:8000**
6. Opens your browser automatically

---

## Testing the Deliverable Forge (the main user-facing feature)

### Step 1 — Open the Landing Page

Navigate to: **http://localhost:8000/**

You should see the Murphy System landing page with navigation, features section, and a **forge/build** section.

### Step 2 — Find the Forge

Scroll down to the section titled **"Build Something"** (or similar — it's the main interactive demo area with a text input and a "Build" button).

### Step 3 — Enter a Query

Type a query that includes a build keyword. The frontend gate requires your query to:
- Contain a **type keyword** (one of: `game`, `app`, `automat`, `course`, `book`, `plan`, `build`, `create`, `make`, `write`, `generate`)
- Be at least **4 words** long

**Good test queries:**
| Query | What it tests |
|-------|---------------|
| `create a compliance automation plan` | Keyword scenario detection + full pipeline |
| `build a customer onboarding workflow` | Onboarding scenario + swarm agents |
| `generate a trading risk management app` | Custom query through MFGC → MSS → swarm |
| `write a project management game` | Game scenario with multi-agent swarm |
| `create an employee training course` | Course scenario generation |

**Queries that will be blocked** (missing keywords or too short):
- `hello` — too short, no type keyword
- `analyze my data` — no type keyword
- `build` — only 1 word (needs 4+)

### Step 4 — Watch the Build

After clicking Build:
1. An **agent grid** appears showing individual swarm agents working in parallel
2. A **chat box** shows real-time progress messages
3. The status bar updates through phases: decomposing → agents working → synthesizing → done

### Step 5 — Review the Deliverable

When the build finishes:
- The deliverable content appears in the chat area
- **Download button** — saves as `.txt` file
- **Format buttons** (TXT, PDF, HTML, DOCX, MD) — export in different formats
- **ROI stats** — shows agent count, build time, estimated human hours, ROI multiplier

### Step 6 — Test Export Formats

Click any format button to download:
- **TXT** — plain text
- **PDF** — formatted PDF document
- **HTML** — web page (also has "Preview in Tab" button)
- **DOCX** — Word document
- **MD** — Markdown

---

## Testing the API Directly (curl)

### Health Check
```bash
curl http://localhost:8000/docs
```
Expected: HTML page with Swagger interactive API documentation

### Generate a Deliverable (JSON)
```bash
curl -X POST http://localhost:8000/api/demo/generate-deliverable \
  -H "Content-Type: application/json" \
  -d '{"query": "create a compliance automation plan"}'
```
Expected: JSON with `success: true`, `deliverable.content`, `deliverable.title`, `build_metrics`

### Stream a Deliverable (SSE)
```bash
curl -X POST http://localhost:8000/api/demo/generate-deliverable/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "build an employee onboarding workflow"}'
```
Expected: Server-Sent Events stream with `agent_tasks`, `progress`, `chunk`, and `done` events

### List Export Formats
```bash
curl http://localhost:8000/api/demo/deliverable/formats
```
Expected: `{"formats": ["txt", "pdf", "html", "docx", "zip", "md"]}`

### Export in a Specific Format
```bash
curl -X POST http://localhost:8000/api/demo/deliverable/export \
  -H "Content-Type: application/json" \
  -d '{"deliverable": "Your deliverable text here", "format": "html", "query": "test"}'
```

---

## Testing Auth Flow (optional)

### Sign Up
```bash
curl -X POST http://localhost:8000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "TestPass123!", "name": "Test User"}'
```
In development mode, this creates an account. In staging/production, email verification is required.

### Log In
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "TestPass123!"}'
```
Returns a session token. In development mode, auth checks are relaxed.

---

## Running the Automated Tests

```bash
# Activate the venv first
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install test dependencies
pip install pytest pytest-timeout

# Run the deliverable generator unit tests (55 tests)
PYTHONPATH="Murphy System/src:Murphy System:src:." \
  pytest "Murphy System/tests/onboarding/test_demo_deliverable.py" -v --timeout=60

# Run all module tests
PYTHONPATH="Murphy System/src:Murphy System:src:." \
  pytest "Murphy System/tests/modules/" -v --timeout=120
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'fastapi'` | Run `pip install -r requirements_core.txt` |
| Port 8000 already in use | Set `MURPHY_PORT=8001` in `.env` or `export MURPHY_PORT=8001` before running |
| Forge says "Backend error" | Check terminal for Python tracebacks — usually a missing dependency |
| Deliverable content is generic/templated | The onboard LLM is deterministic. Add a `DEEPINFRA_API_KEY` in `.env` for AI-generated content |
| Browser doesn't open automatically | Manually navigate to `http://localhost:8000/` |
| "Daily build limit reached" | Restart the server to reset the in-memory rate limiter |

---

## Architecture Notes

- **`murphy_production_server.py`** — The full-featured server with all 450+ API endpoints, including the forge, deliverable generation, auth, dashboards, and landing page.
- **`Murphy System/src/demo_deliverable_generator.py`** — The deliverable generation pipeline: MFGC → MSS → Swarm agents → Synthesis.
- **`Murphy System/static/murphy-landing.js`** — Frontend forge UI logic (agent grid, SSE streaming, result display).
- **`Murphy System/murphy_landing_page.html`** — The landing page HTML served at `/`.
