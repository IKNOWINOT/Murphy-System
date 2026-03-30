# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
Created by: Corey Post

---

# Murphy System — Community & Ecosystem Guide

Welcome to the Murphy System community. This guide explains how to get involved, contribute code, build plugins, stay connected with other community members, and help shape the roadmap.

---

## Table of Contents

1. [Welcome to the Murphy System Community](#1-welcome-to-the-murphy-system-community)
2. [How to Contribute](#2-how-to-contribute)
3. [Code Standards](#3-code-standards)
4. [PR Process](#4-pr-process)
5. [Plugin Marketplace Overview](#5-plugin-marketplace-overview)
6. [Community Channels](#6-community-channels)
7. [Roadmap: 2025](#7-roadmap-2025)
8. [Governance Model](#8-governance-model)
9. [Code of Conduct Summary](#9-code-of-conduct-summary)

---

## 1. Welcome to the Murphy System Community

Murphy System is an open-core workflow intelligence platform built by Murphy Collective. The community is the engine behind its growth — every plugin, bug report, documentation fix, and feature idea makes the platform better for every user.

**What the community builds together:**

- **Core runtime improvements** — performance, reliability, and security of the Murphy System engine
- **Connector plugins** — integrations with databases, APIs, ML services, communication tools, and more
- **Documentation and tutorials** — guides that help new users get productive fast
- **Tooling and templates** — CLI tools, starter templates, and developer experience improvements

Whether you are a solo developer building a plugin for your own use case or an enterprise team contributing a full connector suite, you are welcome here. All contributions — regardless of size — are valued.

---

## 2. How to Contribute

### Fork and clone

```bash
# Fork via GitHub UI or CLI
gh repo fork inoni/Murphy-System --clone
cd Murphy-System
```

### Set up your development environment

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
```

### Branch naming conventions

| Type              | Pattern                         | Example                              |
|-------------------|---------------------------------|--------------------------------------|
| New feature       | `feat/<short-description>`      | `feat/multi-tenant-auth`             |
| Bug fix           | `fix/<issue-or-description>`    | `fix/loader-import-error`            |
| Plugin            | `plugin/<plugin-name>`          | `plugin/postgresql-connector`        |
| Documentation     | `docs/<topic>`                  | `docs/plugin-sdk-guide`              |
| Chore / tooling   | `chore/<description>`           | `chore/update-pre-commit-hooks`      |
| Security          | `security/<description>`        | `security/patch-cve-2025-xxxxx`      |

### Make your changes

- Follow the [Code Standards](#3-code-standards) defined in this guide
- Write or update tests for every change
- Update relevant documentation

### Push and open a Pull Request

```bash
git add .
git commit -m "feat: add multi-tenant auth support"
git push origin feat/multi-tenant-auth
gh pr create --fill
```

Fill in the PR template (see [Section 4](#4-pr-process)) and request a review from a maintainer.

---

## 3. Code Standards

All contributions to the Murphy System codebase — core, plugins, tooling — must follow these standards. Consistency makes the codebase easier to read, review, and maintain.

### Python version

Murphy System targets **Python 3.10 or higher**. Use modern language features (structural pattern matching, `match`/`case`, `X | Y` union types) where they improve readability.

### Type hints

All function signatures must include type annotations. Use `from __future__ import annotations` for forward references.

```python
# ✅ Correct
def load_plugin(name: str, version: str | None = None) -> ConnectorPlugin:
    ...

# ❌ Incorrect
def load_plugin(name, version=None):
    ...
```

### Docstrings

Public classes and functions must have docstrings. Use the Google docstring style.

```python
def execute(self, action: str, payload: dict) -> dict:
    """Execute a plugin action.

    Args:
        action: The action identifier to execute.
        payload: Input data for the action.

    Returns:
        A dict containing the action result.

    Raises:
        UnsupportedActionError: If the action is not defined in schema().
        ExecutionError: If the action fails during execution.
    """
```

### No external dependencies in core

The `murphy_system` core package must remain dependency-free (stdlib only). External packages are allowed in:

- Plugin packages (declared in plugin-level `requirements.txt`)
- Developer tooling (`[dev]` extras in `pyproject.toml`)
- Optional feature extras (e.g., `[postgres]`, `[redis]`)

### Formatting and linting

The repository uses:

| Tool        | Purpose                        | Config file           |
|-------------|--------------------------------|-----------------------|
| `ruff`      | Linting and import sorting     | `ruff.toml`           |
| `black`     | Code formatting                | `pyproject.toml`      |
| `mypy`      | Static type checking           | `mypy.ini`            |
| `pre-commit`| Run all checks before commit   | `.pre-commit-config.yaml` |

Run all checks locally before pushing:

```bash
pre-commit run --all-files
```

### Naming conventions

| Element            | Convention          | Example                      |
|--------------------|---------------------|------------------------------|
| Modules            | `snake_case`        | `plugin_loader.py`           |
| Classes            | `PascalCase`        | `PluginLoader`               |
| Functions/methods  | `snake_case`        | `load_plugin()`              |
| Constants          | `UPPER_SNAKE_CASE`  | `DEFAULT_TIMEOUT = 30`       |
| Private methods    | `_leading_underscore` | `_validate_schema()`       |
| Type aliases       | `PascalCase`        | `CredentialsDict`            |

---

## 4. PR Process

### PR description template

Every PR must use the following template. It is pre-loaded when you open a PR on GitHub.

```markdown
## Summary
<!-- One or two sentences describing what this PR does and why -->

## Type of change
- [ ] Bug fix
- [ ] New feature
- [ ] Plugin (new connector)
- [ ] Documentation
- [ ] Refactor / chore

## Related issues
Closes #<issue_number>

## Changes made
<!-- Bullet list of key changes -->

## Testing
<!-- Describe how you tested your changes -->
- [ ] Unit tests added / updated
- [ ] Integration tests added / updated (if applicable)
- [ ] Manually verified locally

## Checklist
- [ ] Code follows the project's style guidelines
- [ ] Self-review completed
- [ ] Documentation updated (if applicable)
- [ ] No new warnings introduced
- [ ] All CI checks pass
```

### Review requirements

| PR type               | Approvals required | Additional checks                     |
|-----------------------|--------------------|---------------------------------------|
| Bug fix               | 1 core maintainer  | CI green                              |
| New feature           | 2 core maintainers | CI green, design discussion linked    |
| New plugin            | 1 core maintainer  | `PluginValidator` passes, tests ≥ 80% |
| Security patch        | 1 core maintainer  | Security advisory drafted             |
| Breaking change       | 2 core maintainers | Migration guide included              |

### CI checks

All PRs must pass the following automated CI pipeline steps before merge:

1. **Lint** — `ruff` and `black --check`
2. **Type check** — `mypy --strict`
3. **Unit tests** — `pytest tests/unit` with coverage report
4. **Integration tests** — `pytest tests/integration` (skipped for docs-only PRs)
5. **Plugin validation** — `murphy_system.sdk.cli validate` (for plugin PRs)
6. **Security scan** — `bandit -r murphy_system/`

CI is powered by GitHub Actions. You can reproduce the pipeline locally with:

```bash
make ci
```

---

## 5. Plugin Marketplace Overview

The Murphy System Plugin Marketplace is the curated directory of all community and official connector plugins.

### How plugins are categorised

Plugins are assigned a `ConnectorCategory` at development time. The marketplace uses this to organise the directory into browsable sections. See the full list of 20 categories in the [Plugin SDK Guide](PLUGIN_SDK_GUIDE.md#connectorcategory-enum).

### Quality tiers

| Tier        | Badge        | Criteria                                                                         |
|-------------|--------------|----------------------------------------------------------------------------------|
| Community   | ⭐ Community  | Passes `PluginValidator`, has tests, is listed in the registry                   |
| Verified    | ✅ Verified   | ≥ 90% test coverage, complete docs, active maintenance, security review passed   |
| Official    | 🏅 Official   | Maintained by Murphy Collective or a certified partner, SLA and support guarantees       |

### Plugin discovery

Users find plugins through:

- The [Marketplace web UI](https://marketplace.murphy-system.io)
- The CLI: `murphy plugin search <keyword>`
- The Murphy System admin console's "Integrations" panel

### Deprecated plugins

If a plugin is deprecated, maintainers must:

1. Set `DEPRECATED = True` on the plugin class
2. Add a `DEPRECATION_NOTICE` string with migration instructions
3. Open a PR to move the plugin to the `deprecated/` directory
4. Notify users via GitHub Discussions

---

## 6. Community Channels

### Discord

Join the Murphy System community Discord for real-time discussion, help, and collaboration.

**Invite link:** [https://discord.gg/murphy-system-placeholder](#)

Key channels:

| Channel           | Purpose                                              |
|-------------------|------------------------------------------------------|
| `#announcements`  | Release notes and important project updates          |
| `#general`        | General discussion                                   |
| `#plugin-dev`     | Plugin development help and reviews                  |
| `#core-dev`       | Core runtime development                             |
| `#showcase`       | Share what you have built with Murphy System         |
| `#help`           | Ask questions and get support                        |
| `#security`       | Responsible disclosure and security discussion       |

### GitHub Discussions

For longer-form questions, feature proposals, and design discussions, use [GitHub Discussions](https://github.com/inoni/Murphy-System/discussions).

Categories:

- **Q&A** — Technical questions and answers
- **Ideas** — Feature requests and proposals
- **Show and Tell** — Community project showcases
- **Announcements** — Official project news (maintainers only)
- **Roadmap Feedback** — Input on upcoming roadmap items

### Weekly office hours

The core team hosts open office hours every **Wednesday at 17:00 UTC** via Discord voice.

Agenda: community questions, roadmap updates, plugin reviews, and open discussion. No registration needed — just join the `#office-hours` voice channel.

---

## 7. Roadmap: 2025

The following features are planned for 2025. All timelines are aspirational and subject to change based on community feedback and available capacity.

### Q1 2025 — Foundation

| Feature                              | Status      | Notes                                              |
|--------------------------------------|-------------|----------------------------------------------------|
| Plugin SDK v2.0 GA                   | ✅ Complete  | Stable API with full validation tooling            |
| `ConnectorCategory` expansion to 20  | ✅ Complete  | All 20 categories defined and documented           |
| GitHub Actions CI pipeline           | ✅ Complete  | Full lint, type-check, test, and security pipeline |
| Plugin Marketplace beta              | 🔄 In progress | Web UI for browsing and installing plugins        |

### Q2 2025 — Developer Experience

| Feature                              | Status       | Notes                                             |
|--------------------------------------|--------------|---------------------------------------------------|
| `murphy plugin scaffold` CLI command | 🔄 In progress | Interactive scaffold generator for new plugins  |
| Plugin hot-reload in dev mode        | 📋 Planned   | Reload plugins without restarting the runtime     |
| Schema auto-documentation generator  | 📋 Planned   | Generate Markdown docs from `schema()` output     |
| OAuth 2.0 credential flow UI         | 📋 Planned   | Built-in OAuth flow for `AuthType.OAUTH2` plugins |

### Q3 2025 — Scale and Reliability

| Feature                              | Status     | Notes                                              |
|--------------------------------------|------------|----------------------------------------------------|
| Distributed plugin execution         | 📋 Planned | Run plugins across worker nodes                    |
| Plugin health dashboard              | 📋 Planned | Visualise `health_check()` status across all loaded plugins |
| Plugin versioning and rollback       | 📋 Planned | Pin, upgrade, and roll back plugin versions        |
| Rate limiting and retry policies     | 📋 Planned | Configurable retry with exponential back-off       |

### Q4 2025 — Ecosystem and Community

| Feature                              | Status     | Notes                                              |
|--------------------------------------|------------|----------------------------------------------------|
| Plugin monetisation (Verified tier)  | 📋 Planned | Revenue sharing for Verified plugin authors        |
| Partner certification programme      | 📋 Planned | Formal programme for Official tier partners        |
| Murphy System cloud-hosted runner    | 📋 Planned | Execute workflows without self-hosting             |
| Community plugin grants programme    | 📋 Planned | Fund high-priority community plugins               |

To propose additions or changes to the roadmap, open a GitHub Discussion in the **Roadmap Feedback** category.

---

## 8. Governance Model

Murphy System follows a **BDFL with delegated authority** governance model.

### BDFL (Benevolent Dictator For Life)

The BDFL is the founder and lead maintainer of Murphy System at Murphy Collective. The BDFL holds final decision-making authority on questions of project direction, breaking changes, and governance policy.

### Core Team

The core team consists of trusted contributors appointed by the BDFL. Core team members:

- Review and merge PRs
- Triage issues and discussions
- Represent the project at community events
- Publish releases
- Enforce the Code of Conduct

Core team membership is extended by invitation after sustained, high-quality contributions over a minimum of six months.

### Contributors

Anyone who has had a PR merged is a contributor. Contributors:

- Are listed in `CONTRIBUTORS.md`
- Are eligible for community Discord roles
- Are eligible for nomination to the core team

### Decision making

| Decision type                          | Authority                  |
|----------------------------------------|----------------------------|
| Bug fixes and non-breaking changes     | Any core team member       |
| New features and API additions         | Core team consensus (2+)   |
| Breaking changes                       | Core team + BDFL approval  |
| Governance policy changes              | BDFL                       |
| Code of Conduct enforcement            | Core team                  |

Significant decisions are discussed publicly in GitHub Discussions before implementation.

### Conflict resolution

In the event of a disagreement that cannot be resolved through discussion:

1. Either party may escalate to a core team vote (simple majority)
2. If the vote is tied, the BDFL casts the deciding vote
3. Code of Conduct violations are handled exclusively by the core team

---

## 9. Code of Conduct Summary

Murphy System is committed to providing a welcoming, inclusive, and harassment-free environment for all community members regardless of experience level, gender identity, sexual orientation, disability, ethnicity, nationality, religion, or other personal characteristics.

### Expected behaviour

- Be respectful and constructive in all interactions
- Assume good intent; ask for clarification before taking offence
- Give and receive feedback gracefully
- Focus on ideas and code, not on individuals
- Credit others' contributions

### Unacceptable behaviour

- Harassment, intimidation, or discrimination of any kind
- Publishing others' private information without consent
- Sustained disruption of discussions
- Offensive or unwelcome comments related to personal characteristics
- Deliberate misgendering

### Reporting

If you experience or witness a Code of Conduct violation, report it by emailing **conduct@inoni.com**. All reports are kept confidential. The core team will review the report and respond within 72 hours.

### Enforcement

Violations may result in a warning, temporary suspension from community spaces, or a permanent ban, depending on severity and frequency.

For the full Code of Conduct, see [CODE_OF_CONDUCT.md](../../../../CODE_OF_CONDUCT.md) in the repository root.
