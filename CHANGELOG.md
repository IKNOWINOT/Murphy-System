# Changelog

All notable changes to Murphy System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Security Implementation Plan** (`SECURITY_IMPLEMENTATION_PLAN.md`) — phased security enhancement roadmap addressing multi-agent risks (authorization hardening, PII sanitization, resource quotas, communication loop detection, bot identity verification, anomaly detection) with completion percentages per phase

### Changed
- **README.md** — updated completion table to reflect actual system state (UI/testing at 85%, security hardening at 47%); replaced verbose internal development log with concise runtime capabilities summary; fixed broken documentation links to removed archive paths; added security plan and additional docs to documentation table
- **SECURITY.md** — added reference to the Security Implementation Plan
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
