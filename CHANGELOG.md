# Changelog

All notable changes to Murphy System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Account Management System** (`src/account_management/`) — complete account lifecycle with OAuth, credential vault, consent-based import, and self-ticketing
  - `models.py` — OAuthProvider (Microsoft/Google/Meta/GitHub/Custom), AccountRecord, OAuthToken, StoredCredential, ConsentRecord, AccountEvent with 16 event types
  - `oauth_provider_registry.py` — OAuth authorization flows with PKCE, state management, profile normalization per provider, token lifecycle
  - `credential_vault.py` — encrypted credential storage (Fernet or HMAC fallback), SHA-256 hash verification, rotation tracking, thread-safe operations
  - `account_manager.py` — top-level orchestrator: account creation, OAuth signup/link/unlink, credential CRUD, consent-based import flow, auto-ticketing for missing integrations, full audit log
  - 107 tests across 10 test categories (models, mappers, registry, vault, manager, OAuth, credentials, consent, ticketing, thread safety)
- **Test Status section in README** — real-time test results table, skip explanations, known flaky test documentation
- **Self-Healing & Patch Capabilities section in README** — documents self-improvement infrastructure and what Murphy can/cannot auto-fix
- **Professional warning banner in README** — honest status disclosure: single developer, alpha quality, emergent bugs being classified

### Fixed
- **Flask import guard** (`src/flask_security.py`) — guarded `from flask import ...` with try/except so the module loads cleanly when Flask is not installed (Flask is optional; the system uses FastAPI)
- **Artifact Viewport API import guard** (`src/artifact_viewport_api.py`) — stub `Blueprint` class when Flask is absent so `@viewport_bp.route()` decorators don't crash at module load
- **Bootstrap orchestrator test count** (`tests/test_readiness_bootstrap_orchestrator.py`) — updated assertions from `== 5` to `== 6` to match the 6th subsystem (`_bootstrap_domain_gates`) added to the source
- **ML feature verification module list** (`tests/test_ml_feature_verification.py`) — replaced `flask_security` with `fastapi_security` in `SECURITY_MODULE_NAMES` since the system's primary security module is FastAPI-based
- **Security hardening phase 1 tests** (`tests/test_security_hardening_phase1.py`) — added `pytest.importorskip("flask")` so tests skip cleanly when Flask is not installed
- **Security hardening phase 2 tests** (`tests/test_security_hardening_phase2.py`) — added `pytest.importorskip("flask")` to both `TestArtifactViewportAPI` and `TestExecutionOrchestratorInputValidation` fixtures
- **Viewport integration tests** (`tests/test_viewport_integration.py`) — added `pytest.importorskip("flask")` to `TestExecutionOrchestratorViewport` fixture
- **Murphy terminal tests** (`tests/test_murphy_terminal.py`) — added `pytest.importorskip("textual")` since the Textual TUI library is optional

### Changed
- **README.md** — added warning banner, updated test counts (210+ → 265 files, 4100+ → 5,900+ tests), added test status table, added self-healing documentation, updated module test count (1490+ → 5,900+); updated completion table (security hardening 100%, overall ~98%); added security capabilities to runtime status; added multi-agent security section to Safety & Governance
- **Test results** — from 25 failed + 14 errors → 0 failed + 0 errors (5,946 passing, 71 skipped)
- **SECURITY_IMPLEMENTATION_PLAN.md** — updated all phases to 100% completion with implementation details, file paths, and test counts
- **SECURITY.md** — added reference to completed security enhancements
- **CHANGELOG.md** — documented all security enhancement implementations
- `security_plane/__init__.py` — exports all 7 new modules (27 new public symbols)
- Updated internal file references in `ARCHITECTURE_MAP.md`, `MURPHY_COMMISSIONING_IMPLEMENTATION_PLAN.md`, and `gate_bypass_controller.py` to remove references to deleted planning documents

### Removed
- `comparison_analysis.md` — internal threat analysis document (not suitable for public repository)
- `MURPHY_SELF_AUTOMATION_PLAN.md` — internal development roadmap (not suitable for public repository)
- `MURPHY_COMMISSIONING_TEST_PLAN.md` — internal test specification (not suitable for public repository)
- `murphy_system_security_plan.md` — raw security working document (replaced by `SECURITY_IMPLEMENTATION_PLAN.md`)

## [1.0.0] - 2025-02-27

### Added
- **One-line CLI installer** — `curl -fsSL .../install.sh | bash` for instant setup
- **`murphy` CLI tool** — start, stop, status, health, info, logs, update commands
- **BSL 1.1 license** — source-available with Apache 2.0 conversion after 4 years
- **License Strategy document** — rationale for open-core licensing approach
- **Professional repo files** — CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, CHANGELOG.md
- **Freelancer Validator** (`src/freelancer_validator/`) — dispatches HITL validation tasks to freelance platforms (Fiverr, Upwork, generic); org-level budget enforcement (monthly + per-task limits); structured criteria with weighted scoring; format-validated responses; credential verification against public records (BBB, state license boards) with complaint/disciplinary-action lookup; automatic wiring of verdicts into HITL monitor. 47 commissioning tests.
- Complete runtime with 32+ engines and 47+ modules
- Universal Control Plane architecture
- Two-Phase Orchestrator (generative setup → production execution)
- Integration Engine with GitHub ingestion and HITL approval
- Business automation (sales, marketing, operations, finance, customer service)
- 222 commissioning tests passing
- Docker and Kubernetes deployment references
- Multiple terminal UI interfaces
- 20 step-by-step setup screenshots in docs/screenshots/

### Changed
- Updated all documentation to reflect current system state
- License changed from Apache 2.0 to BSL 1.1 (open-core model)
- README updated with one-line install instructions and accurate status

### Security
- Environment files (.env) excluded from version control
- API key configuration documented with security best practices
- SECURITY.md added with responsible disclosure process
