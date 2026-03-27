# Contributing to Murphy System

Thank you for your interest in contributing to Murphy System! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Architecture Overview

Murphy System has grown to **978 source modules** across 81 packages. Key subsystems include:

- **Core Runtime** — FastAPI server, config, command system
- **Self-Healing** — `self_fix_loop.py`, `causality_sandbox.py`, `murphy_code_healer.py`
- **Wingman Protocol** — `wingman_protocol.py` (executor/validator pairing for every task)
- **HITL Graduation** — `hitl_graduation_engine.py` (human-to-automation handoff pipeline)
- **Security** — `secure_key_manager.py`, `flask_security.py`, `fastapi_security.py`
- **Bridges & Adapters** — `golden_path_bridge.py`, `telemetry_adapter.py`
- **Confidence & Gates** — `confidence_engine/`, `gate_synthesis/`
- **Orchestrators** — `campaign_orchestrator.py`; `safety_orchestrator.py`, `efficiency_orchestrator.py`, `supply_orchestrator.py` (planned)
- **Issue #136 subsystems** (in progress) — Drawing Engine, Credential Gate, Sensor Fusion, Osmosis Engine, Autonomous Perception, Wingman Evolution, Engineering Toolbox

See [`murphy_system/docs/MODULE_REGISTRY.md`](Murphy%20System/docs/MODULE_REGISTRY.md) for the full module index.

## How to Contribute

### Reporting Bugs

1. **Check existing issues** — search [GitHub Issues](https://github.com/IKNOWINOT/Murphy-System/issues) first
2. **Create a new issue** with a clear title and description
3. Include steps to reproduce, expected vs. actual behavior, and your environment

### Suggesting Features

Open a [GitHub Issue](https://github.com/IKNOWINOT/Murphy-System/issues) with the `enhancement` label and describe:
- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

### Submitting Changes

1. Fork the repository
2. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes following our coding standards
4. Add or update tests as needed
5. Run the test suite:
   ```bash
   cd "murphy_system"
   python -m pytest tests/ -v
   ```
6. Commit with clear messages:
   ```bash
   git commit -m "Add: brief description of change"
   ```
7. Push and open a Pull Request

## Development Setup

```bash
# Clone the repo
git clone https://github.com/IKNOWINOT/Murphy-System.git
cd Murphy-System/Murphy\ System

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements_murphy_1.0.txt

# Run tests
python -m pytest tests/ -v
```

## Coding Standards

- **Python 3.11+** required
- Follow PEP 8 style guidelines
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines where practical
- Write tests for new functionality

## Contributor License Agreement

By submitting a contribution, you agree that your contributions are licensed under the same [BSL 1.1 license](LICENSE) as the project, and you assign copyright to Inoni Limited Liability Company.

## Questions?

Open an issue or reach out to the maintainers through [GitHub Discussions](https://github.com/IKNOWINOT/Murphy-System/discussions).

## Branch Protection Recommendations

The following branch protection rules are recommended for `main`:

| Rule | Setting |
|---|---|
| Require pull request before merging | ✅ Enabled |
| Required approvals | 1 |
| Dismiss stale pull request approvals when new commits are pushed | ✅ Enabled |
| Require status checks to pass before merging | ✅ Enabled |
| Required status checks | `test (3.10)`, `test (3.11)`, `test (3.12)`, `security` |
| Require branches to be up to date before merging | ✅ Enabled |
| Restrict who can push to matching branches | Maintainers only |
| Do not allow bypassing the above settings | ✅ Enabled |

## Stale PR Policy

- Draft PRs with no commits for **7 days** are automatically labelled `stale`.
- Stale PRs with no activity for a further **3 days** are closed with a comment explaining why.
- All active work must have at least one commit every **5 days** or be converted to an issue.
- See `murphy_system/docs/STALE_PR_CLEANUP.md` for the rationale applied to PRs #21–#95.
