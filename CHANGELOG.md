# Changelog

All notable changes to Murphy System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Security Implementation Plan** (`SECURITY_IMPLEMENTATION_PLAN.md`) — phased security enhancement roadmap addressing multi-agent risks, now at 100% completion
- **Authorization Enhancer** (`src/security_plane/authorization_enhancer.py`) — per-request ownership verification, session context enforcement with configurable TTL, and bounded audit trail. 8 tests.
- **Log Sanitizer** (`src/security_plane/log_sanitizer.py`) — PII detection for 8 sensitive data types (email, phone, SSN, credit card, API key, password, auth token, IP address) with automated redaction and retroactive log sanitization. 11 tests.
- **Bot Resource Quotas** (`src/security_plane/bot_resource_quotas.py`) — per-bot resource quotas (memory, CPU, API calls, budget), swarm aggregate limits with bot count caps, and automatic suspension at 100% / warning at 80% thresholds. 6 tests.
- **Swarm Communication Monitor** (`src/security_plane/swarm_communication_monitor.py`) — directed graph message tracking, DFS-based cycle detection, per-bot and per-channel rate limiting, and unusual communication pattern detection. 7 tests.
- **Bot Identity Verifier** (`src/security_plane/bot_identity_verifier.py`) — HMAC-SHA256 signing key generation, message signing and verification with constant-time comparison, centralized identity registry, and immediate key revocation. 8 tests.
- **Bot Anomaly Detector** (`src/security_plane/bot_anomaly_detector.py`) — per-bot metric collection (7 metric types), z-score anomaly detection over rolling windows, resource spike detection, and API pattern analysis via bigram frequency. 6 tests.
- **Security Dashboard** (`src/security_plane/security_dashboard.py`) — unified security event aggregation (11 event types), same-bot event correlation, severity-based escalation callbacks, and compliance reporting with actionable recommendations. 7 tests.
- **Comprehensive test suite** — `tests/test_security_enhancements.py` with 53 tests covering all 7 new security modules

### Changed
- **README.md** — updated completion table (security hardening 100%, overall ~98%); added security capabilities to runtime status; added multi-agent security section to Safety & Governance
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
