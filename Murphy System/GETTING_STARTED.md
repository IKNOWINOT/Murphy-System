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

Change into the repository root:

```
$ cd Murphy-System
```

---

## Step 2 — Install and Start Murphy

From the repository root, run the setup script — it handles everything:

### Linux / macOS

```
$ bash setup_and_start.sh
✓  Python 3.10+ found
✓  Virtual environment ready
✓  All dependencies installed
✓  Created default .env (onboard LLM active — no key required)
✓  Runtime directories ready
```

### Windows

```
> setup_and_start.bat
```

`setup_and_start.sh` (and its Windows counterpart) performs all of the
following automatically:

1. Checks prerequisites (Python 3.10+, pip)
2. Creates a virtual environment and installs all dependencies from
   `requirements_murphy_1.0.txt`
3. Auto-generates a `.env` with `MURPHY_LLM_PROVIDER=local` — the onboard
   LLM works without any external API key
4. Creates all runtime directories (logs, data, modules, sessions, etc.)
5. Launches the Murphy backend server

> **No API key required.** In development mode (`MURPHY_ENV=development`,
> the default), no API key is needed. Murphy starts with its onboard LLM
> by default. For enhanced quality, optionally add a Groq key later via
> the terminal (`set key groq <your-key>`) or by editing `.env`.
> In production mode, the system auto-generates keys via `SecureKeyManager`.

Once the script completes, the backend server will be running:

```
INFO:     Murphy System 1.0 starting...
INFO:     Module registry: 610 modules loaded
INFO:     Governance kernel: active
INFO:     HITL gates: enabled
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Murphy is running.  Leave this terminal open.

---

## Step 3 — Verify the Health Check

Open a second terminal and run:

```
$ curl http://localhost:8000/api/health
{"status":"ok","version":"1.0.0","uptime_seconds":4}
```

`"status": "ok"` confirms the process is alive and accepting connections.

---

## Step 4 — Authenticate (Production Only)

In development mode (`MURPHY_ENV=development`, the default), all endpoints
are accessible without an API key.  You can skip this step while evaluating
Murphy locally.

For production deployments, the system auto-generates secure API keys via
`SecureKeyManager`.  Use the key as a Bearer token:

```
$ curl -H "Authorization: Bearer <your-generated-key>" \
       http://localhost:8000/api/status
```

Expected response (abbreviated):

```json
{
  "status": "operational",
  "modules_loaded": 610,
  "llm_provider": "local",
  "active_gates": ["security", "compliance", "governance"],
  "uptime_seconds": 23,
  "version": "1.0.0"
}
```

---

## Step 5 — Execute Your First Task

```
$ curl -X POST http://localhost:8000/api/execute \
       -H "Content-Type: application/json" \
       -d '{"task": "summarise the key benefits of Murphy System"}'
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
the server terminal for error messages.  Common cause: a dependency failed to
install — re-run `bash setup_and_start.sh` from the repository root.

### `401 Unauthorized` from the API

In development mode (`MURPHY_ENV=development`), auth is disabled by default.
If you are running in production mode, ensure you have a valid API key
generated by `SecureKeyManager` and include it as
`Authorization: Bearer <key>` in your request header.

### Gates reporting `"fail"` in execute response

A governance gate blocked the request.  Check the `gate_results` field for
which gate failed.  For evaluation/testing, you can temporarily set
`GOVERNANCE_STRICT=false` in `.env`.
