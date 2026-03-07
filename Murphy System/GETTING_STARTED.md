# Getting Started with Murphy System 1.0

> **Success-path walkthrough** — every step shows only expected successful output.
> See [Troubleshooting](#troubleshooting) at the end if something looks different.

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## What You Will Build

By the end of this guide you will have Murphy System running locally, confirmed
healthy, and ready to accept API requests.  The whole process takes about five
minutes on a machine that meets the prerequisites.

---

## Prerequisites

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.10+ | `python3 --version` must show ≥ 3.10 |
| RAM | 4 GB | 8 GB recommended for LLM-enabled mode |
| Disk | 2 GB free | For dependencies and logs |
| OS | Linux, macOS, or Windows | All three are fully supported |

Check Python now:

```
$ python3 --version
Python 3.10.12
```

---

## Step 1 — Clone the Repository

```
$ git clone https://github.com/IKNOWINOT/Murphy-System.git
Cloning into 'Murphy-System'...
remote: Enumerating objects: 1842, done.
remote: Counting objects: 100% (1842/1842), done.
Resolving deltas: 100% (1204/1204), done.
```

Change into the application directory:

```
$ cd "Murphy-System/Murphy System"
```

---

## Step 2 — Configure Environment

Copy the example environment file and open it in your editor:

```
$ cp .env.example .env
```

The only value you **must** set before first run is `MURPHY_API_KEY`.  Every
other setting has a working default.

Open `.env` and set:

```
MURPHY_API_KEY=your-secret-key-here
```

> **Tip:** Set `LLM_ENABLED=false` for the fastest cold start — Murphy runs
> fully without an LLM, using rule-based routing only.

---

## Step 3 — Install Dependencies

```
$ pip install -r requirements_murphy_1.0.txt
Collecting fastapi>=0.110.0
...
Successfully installed fastapi-0.115.0 uvicorn-0.30.1 ...
```

All packages install cleanly.  No warnings about conflicts are expected.

---

## Step 4 — Start Murphy

### Linux / macOS

```
$ python3 murphy_system_1.0_runtime.py
INFO:     Murphy System 1.0 starting...
INFO:     Module registry: 610 modules loaded
INFO:     Governance kernel: active
INFO:     HITL gates: enabled
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Windows

```
> python murphy_system_1.0_runtime.py
INFO:     Murphy System 1.0 starting...
INFO:     Module registry: 610 modules loaded
INFO:     Governance kernel: active
INFO:     HITL gates: enabled
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Murphy is running.  Leave this terminal open.

---

## Step 5 — Verify the Health Check

Open a second terminal and run:

```
$ curl http://localhost:8000/api/health
{"status":"ok","version":"1.0.0","uptime_seconds":4}
```

`"status": "ok"` confirms the process is alive and accepting connections.

---

## Step 6 — Authenticate

Every endpoint except `/api/health` requires your API key.  Set it as a header:

```
$ curl -H "Authorization: Bearer your-secret-key-here" \
       http://localhost:8000/api/status
```

Expected response (abbreviated):

```json
{
  "status": "operational",
  "modules_loaded": 610,
  "llm_enabled": false,
  "active_gates": ["security", "compliance", "governance"],
  "uptime_seconds": 23,
  "version": "1.0.0"
}
```

---

## Step 7 — Execute Your First Task

```
$ curl -X POST http://localhost:8000/api/execute \
       -H "Authorization: Bearer your-secret-key-here" \
       -H "Content-Type: application/json" \
       -d '{"task": "summarise the key benefits of Murphy System", "use_llm": false}'
```

Expected response:

```json
{
  "success": true,
  "result": "...",
  "confidence": 0.87,
  "execution_time_ms": 120,
  "gate_results": {"security": "pass", "compliance": "pass"},
  "audit_id": "a1b2c3d4-..."
}
```

`"success": true` and `"gate_results"` all showing `"pass"` means the full
governance pipeline executed correctly.

---

## What to Explore Next

| Resource | Purpose |
|---|---|
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Complete API reference with all endpoints |
| [documentation/api/EXAMPLES.md](documentation/api/EXAMPLES.md) | Copy-paste API examples |
| [documentation/deployment/CONFIGURATION.md](documentation/deployment/CONFIGURATION.md) | All environment variables |
| [documentation/deployment/DEPLOYMENT_GUIDE.md](documentation/deployment/DEPLOYMENT_GUIDE.md) | Production deployment |
| [documentation/testing/TESTING_GUIDE.md](documentation/testing/TESTING_GUIDE.md) | Running and writing tests |
| http://localhost:8000/docs | Interactive Swagger UI (while server is running) |

---

## Troubleshooting

### `python3 --version` shows 3.9 or lower

Install Python 3.10 or later from [python.org](https://www.python.org/downloads/)
or via your system package manager:

```
# Ubuntu / Debian
sudo apt install python3.10

# macOS (Homebrew)
brew install python@3.10

# Windows — download installer from python.org
```

### `pip install` fails with dependency conflict

Create a fresh virtual environment first:

```
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements_murphy_1.0.txt
```

### `Address already in use` on port 8000

Another process is using port 8000.  Either stop it or specify a different port:

```
python3 murphy_system_1.0_runtime.py --port 8001
```

### Health check returns connection refused

Murphy is still starting up (usually < 5 seconds) or failed to start.  Check
the server terminal for error messages.  Common cause: missing or invalid
`MURPHY_API_KEY` in `.env`.

### `401 Unauthorized` from the API

The `Authorization: Bearer <key>` header is missing or the key does not match
`MURPHY_API_KEY` in `.env`.  Copy the exact value — it is case-sensitive.

### Gates reporting `"fail"` in execute response

A governance gate blocked the request.  Check the `gate_results` field for
which gate failed.  For evaluation/testing, you can temporarily set
`GOVERNANCE_STRICT=false` in `.env`.
