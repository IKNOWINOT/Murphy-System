# Changelog

<!--
  Copyright © 2020 Inoni Limited Liability Company
  Creator: Corey Post
  License: BSL 1.1 (Business Source License 1.1)
-->

All notable changes to Murphy System are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**License:** BSL 1.1 — *Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post*

---

## [Unreleased]

### Added
- **feat:** `src/federated_learning_coordinator.py` — Federated Learning Coordinator (FLC-001): train models across distributed Murphy instances without sharing raw data; FedAvg/Median aggregation, differential-privacy noise injection, gradient clipping, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/backup_disaster_recovery.py` — Automated Backup & Disaster Recovery System (BDR-001): BackupManager with create/list/restore/delete/expire/verify, LocalStorageBackend, SHA-256 integrity checks, bundle serialisation, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/startup_validator.py` — Boot-time startup validation: env vars, file existence, port availability, dependency importability (SV-001)
- **test:** `tests/test_federated_learning_coordinator.py` — 29 tests covering data models, privacy guard, FedAvg/Median aggregation, coordinator lifecycle, edge cases, thread safety, Wingman gate, Sandbox gate
- **test:** `tests/test_backup_disaster_recovery.py` — 33 tests covering data models, storage CRUD, bundle round-trip, backup lifecycle, restore with checksum validation, retention expiry, thread safety, Wingman gate, Sandbox gate
- **test:** `tests/test_performance_reliability.py` — 34 tests for graceful shutdown, health checks, startup validation, circuit breakers, connection pooling

### Changed
- **refactor:** Converted 12 `raise NotImplementedError` stubs in 6 abstract base classes to proper `abc.ABC` + `@abstractmethod` patterns:
  - `command_system.py` — `CommandModule.execute()`
  - `crypto_exchange_connector.py` — `ExchangeConnector._place_order()`, `_fetch_ticker()`, `_fetch_balances()`, `_probe()`
  - `crypto_wallet_manager.py` — `BaseWallet._do_sync()`
  - `domain_swarms.py` — `DomainSwarmGenerator.generate_candidates()`, `generate_gates()`
  - `learning_engine/model_architecture.py` — `ShadowAgentModel.train()`, `predict()`
  - `murphy_code_healer.py` — Replaced `NotImplementedError` in code-generation templates with `RuntimeError`
- **legal:** Priority 0 — License compliance audit, PII redaction, dependency cleanup (pylint→ruff, Apache headers→BSL-1.1, THIRD_PARTY_LICENSES.md, PRIVACY.md)

### Added
- **test:** `tests/test_code_quality.py` — 10-check automated code-quality gate (CQ-010 through CQ-061): no bare excepts, no TODOs, no stub/placeholder markers, file-size limits with legacy allowlist, docstring coverage baseline, syntax validation, trailing-whitespace check

### Fixed
- **refactor:** Replaced 19 `# Placeholder` / `# Stub` comments across 13 src/ files with descriptive alternatives
- **refactor:** Added missing docstrings to 6 public functions in strict security modules (`fastapi_security.py`, `flask_security.py`, `signup_gateway.py`)
- **refactor:** Removed excess trailing newlines from `src/control_theory/observation_model.py`

---

## [1.0.0] — 2026-03-07

### Added

**Core Runtime**
- FastAPI-based orchestration server (`murphy_system_1.0_runtime.py`) serving on port 8000
- 620+ registered modules across the full system
- Multi-stage production Dockerfile with non-root `murphy` user
- Docker Compose stack: Murphy API, PostgreSQL 16, Redis 7, Prometheus, Grafana

**API**
- `GET /api/health` — liveness probe (no auth required)
- `GET /api/status` — system status dashboard
- `POST /api/execute` — task execution through the full orchestration pipeline
- `GET /api/llm/configure` — read LLM provider configuration
- `POST /api/llm/configure` — hot-reload LLM provider (no restart required)
- `POST /api/confidence/score` — GDH confidence scoring with 5-dimensional uncertainty
- `GET /api/orchestrator/status` — pipeline queue and latency metrics
- `GET /api/orchestrator/tasks` — list recent tasks with status and audit IDs
- `GET /api/modules` — module registry status
- `GET /api/modules/{name}/status` — per-module status
- `POST /api/feedback` — human feedback signals for confidence recalibration
- `POST /api/system/build` — build a complete expert/gate/constraint system
- Full Pydantic v2 request/response validation
- HTTP 429 rate-limit responses with `Retry-After` header

**Security**
- `src/fastapi_security.py` — centralized security middleware (resolves SEC-001, SEC-002, SEC-004)
- API key authentication via `Authorization: Bearer` and `X-API-Key` headers
- CORS origin allowlist (replaces wildcard `*`); configurable via `MURPHY_CORS_ORIGINS`
- Token-bucket rate limiting per IP and per API key
- Input sanitization on all request bodies
- Security response headers: `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`
- Development mode (`MURPHY_ENV=development`) bypasses auth for local use

**Orchestration Engines**
- AUAR 7-layer routing pipeline with ML optimization
- AionMind Kernel: context engine, reasoning engine, orchestration engine
- Unified Control Protocol: 10-engine pipeline, 7 execution states, rollback support
- Session Context Manager: per-session locking, TTL expiry, RM0–RM6 resource tracking
- Concept Graph Engine: 7 node/edge types, graph health scoring, GCS metric
- Execution engines: task executor, workflow orchestrator, sandbox manager

**Confidence and Governance**
- Unified Confidence Engine with Bayesian scoring and Murphy Index
- GDH (Generative / Discriminative / Hybrid) confidence breakdown
- 5-dimensional uncertainty quantification (epistemic, aleatoric, model, data, domain)
- HITL (Human-in-the-Loop) governance gates
- Governance kernel with compliance scheduling
- Artifact graph for full execution provenance

**LLM Integration**
- Groq provider (recommended; free tier available via `GROQ_API_KEYS` pool for rotation)
- OpenAI provider (GPT-4o and above)
- Anthropic provider (Claude 3.5 Sonnet and above)
- Local / offline mode (deterministic Aristotle + Wulfrum engines only)
- Hot-reload LLM provider without server restart

**Setup and Operations**
- `setup_and_start.sh` / `setup_and_start.bat` — guided setup and startup scripts
- `.env.example` — complete environment variable reference with inline documentation
- `requirements_murphy_1.0.txt` — pinned dependency manifest
- Prometheus metrics at `/metrics`: request counters, latency histograms, queue depth, LLM call counters
- Grafana dashboards (included in Docker Compose stack)

**Testing**
- 250+ test files across unit, integration, and end-to-end categories
- CI via GitHub Actions (`ci.yml`): lint, syntax check, full pytest suite
- Test command: `python -m pytest --timeout=60 -v --tb=short` (run from `Murphy System/`)

**Documentation**
- `docs/API_REFERENCE.md` — full endpoint reference
- `documentation/api/` — authentication guide, endpoint reference, examples
- `documentation/deployment/` — deployment guide, configuration, scaling, maintenance
- `documentation/testing/` — testing guide
- `ARCHITECTURE_MAP.md`, `DEPENDENCY_GRAPH.md`, `MURPHY_SYSTEM_1.0_SPECIFICATION.md`
- `USER_MANUAL.md`, `MURPHY_1.0_QUICK_START.md`

**Regulatory Alignment** *(see STATUS.md for full detail)*
- GDPR — data minimization, consent tracking, right-to-erasure support
- SOC 2 — audit logging, access controls, encryption at rest
- HIPAA — role-based access, PHI handling controls, audit trails
- PCI DSS — payment data isolation, encryption, tokenization support
- ISO 27001 — information security management controls

### Known Gaps (tracked for future releases)

| ID | Description |
|----|-------------|
| G-004 | Full ML feedback loop not yet wired to routing weights |
| G-005 | Dashboard UI incomplete |
| G-006 | Formal third-party penetration test pending |
| G-008 | Kubernetes manifests not yet hardened for production |

---

[Unreleased]: https://github.com/Murphy-System/Murphy-System/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Murphy-System/Murphy-System/releases/tag/v1.0.0

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
