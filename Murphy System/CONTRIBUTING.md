# Contributing to Murphy System

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1 (Business Source License 1.1)
-->

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

Thank you for your interest in contributing to Murphy System! This guide explains how to report bugs, suggest features, set up a development environment, and submit changes.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Reporting Bugs](#reporting-bugs)
3. [Suggesting Features](#suggesting-features)
4. [Development Setup](#development-setup)
5. [Running Tests](#running-tests)
6. [Code Style](#code-style)
7. [Pull Request Process](#pull-request-process)
8. [Security Vulnerabilities](#security-vulnerabilities)

---

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md). By participating you agree to uphold those standards. Unacceptable behavior can be reported to **conduct@inoni.io**.

---

## Reporting Bugs

Before opening an issue:

1. Search [existing issues](https://github.com/IKNOWINOT/Murphy-System/issues) to avoid duplicates.
2. Verify you are running the latest version.
3. Confirm it is a Murphy System bug and not a dependency or configuration issue.

**To file a bug report**, open a GitHub issue and include:

- **Murphy System version** (`GET /api/health` → `version`)
- **Python version** (`python --version`)
- **OS and version**
- **Minimal reproduction steps** — the fewest steps needed to trigger the bug
- **Actual behaviour** — what happened
- **Expected behaviour** — what you expected
- **Relevant logs** — paste the relevant lines from the error log; redact any secrets

---

## Suggesting Features

Open a GitHub issue with the label `enhancement` and describe:

- **Problem statement** — what use case is unaddressed?
- **Proposed solution** — what would you like to see?
- **Alternatives considered** — what other approaches did you evaluate?
- **Is this a breaking change?** — does it affect the existing API contract?

Feature requests are evaluated against the project roadmap and BSL 1.1 licensing constraints.

---

## Development Setup

### Prerequisites

- Python 3.10+
- Git
- (Optional) Docker, for running the full stack locally

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/Murphy-System.git
cd Murphy-System/Murphy\ System
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
```

### 3. Install the package in editable mode

This makes `from src.xxx import yyy` imports work from any directory,
including scripts and the REPL:

```bash
pip install -e .
pip install -r requirements_murphy_1.0.txt
```

> **Why editable install?**  
> Murphy System uses a `src/` package layout.  `pip install -e .` registers
> the `src` package in your Python environment so all `from src.xxx import yyy`
> style imports resolve correctly — with no `sys.path` hacks needed.

### 4. Configure the environment

```bash
cp .env.example .env
# Edit .env — at minimum set DEEPINFRA_API_KEY
```

### 5. Start the server

```bash
python murphy_system_1.0_runtime.py
# Server available at http://localhost:8000
```

Or use the setup script:

```bash
# Linux/macOS
./setup_and_start.sh

# Windows
setup_and_start.bat
```

### 6. Verify the setup

```bash
curl http://localhost:8000/api/health
# {"status": "ok", "version": "1.0.0", "uptime_seconds": ...}
```

### Full stack with Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

**Backend Services:**

| Service | URL | Notes |
|---------|-----|-------|
| Murphy API | <http://localhost:8000> | FastAPI backend |
| API Docs (Swagger) | <http://localhost:8000/docs> | Interactive API reference |
| Prometheus | <http://localhost:9090> | Metrics collection |
| Grafana | <http://localhost:3000> | Dashboards — admin / admin |

**UI Pages** (served by `python -m http.server 8090` from `Murphy System/`):

| Page | URL | Role |
|------|-----|------|
| Landing Page | <http://localhost:8090/murphy_landing_page.html?apiPort=8000> | Public entry point |
| Onboarding Wizard | <http://localhost:8090/onboarding_wizard.html?apiPort=8000> | Zero-jargon setup |
| Unified Hub | <http://localhost:8090/terminal_unified.html?apiPort=8000> | Admin / all-roles hub |
| Architect Terminal | <http://localhost:8090/terminal_architect.html?apiPort=8000> | System architect (planning) |
| Enhanced Terminal | <http://localhost:8090/terminal_enhanced.html?apiPort=8000> | Power-user terminal |
| Integrated Terminal | <http://localhost:8090/terminal_integrated.html?apiPort=8000> | Operations manager |
| Worker Terminal | <http://localhost:8090/terminal_worker.html?apiPort=8000> | Delivery worker |
| Orchestrator Terminal | <http://localhost:8090/terminal_orchestrator.html?apiPort=8000> | Orchestration overview |
| Costs Terminal | <http://localhost:8090/terminal_costs.html?apiPort=8000> | Finance / budget manager |
| Org Chart Terminal | <http://localhost:8090/terminal_orgchart.html?apiPort=8000> | HR / org structure |
| Integrations Terminal | <http://localhost:8090/terminal_integrations.html?apiPort=8000> | DevOps / platform engineer |
| Workflow Canvas | <http://localhost:8090/workflow_canvas.html?apiPort=8000> | Visual workflow designer |
| System Visualizer | <http://localhost:8090/system_visualizer.html?apiPort=8000> | Topology viewer |
| Production Wizard | <http://localhost:8090/production_wizard.html?apiPort=8000> | PROD-001 lifecycle wizard |
| Matrix Integration | <http://localhost:8090/matrix_integration.html?apiPort=8000> | Matrix bridge & HITL |
| Compliance Dashboard | <http://localhost:8090/compliance_dashboard.html?apiPort=8000> | Compliance / audit |
| Workspace | <http://localhost:8090/workspace.html?apiPort=8000> | Personal workspace |
| Pricing | <http://localhost:8090/pricing.html?apiPort=8000> | Plans & pricing |
| Sign Up | <http://localhost:8090/signup.html?apiPort=8000> | User registration |
| Smoke Test Tool | <http://localhost:8090/murphy-smoke-test.html?apiPort=8000> | API smoke tests (dev/QA) |
| Observability Dashboard | <http://localhost:8090/strategic/gap_closure/observability/dashboard.html?apiPort=8000> | Observability metrics |
| Community Portal | <http://localhost:8090/strategic/gap_closure/community/community_portal.html?apiPort=8000> | Community collaboration |
| Workflow Builder (Low-Code) | <http://localhost:8090/strategic/gap_closure/lowcode/workflow_builder_ui.html?apiPort=8000> | Low-code builder |

---

## Running Tests

```bash
# From Murphy System/ directory
python -m pytest --timeout=60 -v --tb=short
```

Run a specific file:

```bash
python -m pytest tests/test_auar.py -v
```

Run with coverage:

```bash
python -m pytest --timeout=60 --cov=. --cov-report=term-missing
```

See the full [Testing Guide](documentation/testing/TESTING_GUIDE.md) for test categories, writing new tests, and CI configuration.

---

## Import Strategy

Murphy System uses a `src/` package layout.  All production code lives under
`src/` and the package is named `src`.

### The golden rule — no `sys.path` hacks

**Never** add `sys.path.insert()` or `sys.path.append()` to source files.  The
test `tests/test_no_sys_path_hacks.py` will fail CI if any `src/` file
contains such a call.

### Correct import style

```python
# Always use the full src.xxx prefix for absolute imports
from src.confidence_engine.models import ConfidenceState
from src.module_manager import module_manager
```

Within a sub-package you may also use relative imports:

```python
# Relative import (only within the same sub-package)
from .models import MyModel
from ..confidence_engine.models import ConfidenceState
```

### Why this works

- `pip install -e .` registers the `src` package in your Python environment so
  `from src.xxx import yyy` resolves in any context.
- `pyproject.toml` sets `pythonpath = [".", "src"]` for pytest so both
  `from src.xxx import yyy` and `from xxx import yyy` (bare sub-package name)
  work in test code.
- **`sys.path` manipulation is only permitted in `sandbox_quarantine.py`**
  (legitimate isolation use).

### Scripts

Scripts in `scripts/` import from the `src` package.  Run `pip install -e .`
first, then:

```bash
python scripts/compile_shims.py
```

---

## Code Style

- **Python version:** 3.10+
- **Formatter:** `black` (88-char line length)
- **Linter:** `flake8` with `--max-line-length 88`
- **Type hints:** Use them for all public function signatures
- **Docstrings:** Module-level and class-level docstrings are required; function docstrings for non-trivial logic
- **Copyright header:** All new source files must include:

```python
"""
<module description>

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
"""
```

- **Comments:** Only comment code that needs clarification — avoid restating what the code already says
- **Tests:** All new functionality must include tests. Target ≥ 80% coverage for new modules

### Format and lint before committing

```bash
black .
flake8 . --max-line-length 88 --extend-ignore E203,W503
```

---

## Pull Request Process

1. **Branch naming:** `feature/<short-description>`, `fix/<issue-number>-short-description`, or `docs/<what-changed>`

2. **Keep PRs focused:** One logical change per PR. Large refactors should be discussed in an issue first.

3. **Checklist before opening a PR:**
   - [ ] Tests pass locally: `python -m pytest --timeout=60 -v --tb=short`
   - [ ] New code has tests
   - [ ] Copyright header added to new files
   - [ ] `CHANGELOG.md` updated (under `[Unreleased]`)
   - [ ] No secrets, credentials, or `.env` files committed
   - [ ] `black` and `flake8` pass

4. **PR description:** Explain the **why**, not just the what. Link to the related issue.

5. **Review:** At least one maintainer review is required before merging. Address all review comments or explain why you disagree.

6. **Merge:** Maintainers use squash-merge for feature/fix PRs, merge commits for release PRs.

---

## Security Vulnerabilities

**Do not open a public GitHub issue for security vulnerabilities.** See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
