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

1. Search [existing issues](https://github.com/Murphy-System/Murphy-System/issues) to avoid duplicates.
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

### 3. Install dependencies

```bash
pip install -r requirements_murphy_1.0.txt
```

### 4. Configure the environment

```bash
cp .env.example .env
# Edit .env — at minimum set GROQ_API_KEY
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

Services:
- Murphy API: <http://localhost:8000>
- Prometheus: <http://localhost:9090>
- Grafana: <http://localhost:3000> (admin / admin)

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
