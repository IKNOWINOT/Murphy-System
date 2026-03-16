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

### Fixed — System Scan & Critical Error Corrections

#### Critical Syntax Errors
- **fix(conftest):** `tests/conftest.py` — Merged duplicate docstrings and replaced
  invalid Unicode `→` character that caused `SyntaxError` blocking **all** test collection.
- **fix(healer):** `src/murphy_code_healer.py:2098` — Resolved botched merge in
  `_publish_event()` where `self._backbone.publish()` call had interleaved conflicting
  `event_backbone_client` code producing invalid syntax.

#### NameError / ImportError Fixes
- **fix(test):** `tests/test_consistency_verification.py` — Re-added missing `ROOT`
  variable definition (was accidentally deleted).
- **fix(test):** `tests/test_onboarding_e2e.py` — Re-added missing `MURPHY_DIR`
  variable definition.
- **fix(test):** `tests/test_analytics_backend.py` — Added `bots/` directory to
  `sys.path` so `analytics` module can be found.

#### Runtime Bug Fixes
- **fix(persistence):** `src/persistence_wal.py:214` — Renamed `extra={"name": ...}`
  to `extra={"migration_name": ...}` to avoid overwriting `LogRecord.name` built-in
  attribute (`KeyError: "Attempt to overwrite 'name' in LogRecord"`).

#### Lint Cleanup
- **fix(lint):** Auto-fixed 95 ruff errors across 41 source files (52 I001 unsorted
  imports, 43 F541 f-strings without placeholders). `ruff check src/` now passes clean.

### Added — INC Completion Pass (INC-04, INC-07, INC-14)

#### INC-04 / C-03 — GitHub Actions CI Pipeline (Critical)
- **feat(ci):** `.github/workflows/ci.yml` — Full CI pipeline with 4 jobs:
  - `lint`: `ruff` check on `src/` (E, F, W rules)
  - `test`: pytest matrix across Python 3.10, 3.11, 3.12 with `--timeout=60`; ignores commissioning/integration/e2e/sla/benchmarks for speed; uploads coverage artifact from Python 3.12
  - `security`: `bandit` scan on `src/runtime/` and `src/rosetta/` at `--severity-level medium`
  - `build`: Docker image smoke build on push to `main`/`master` (continue-on-error)
  - Triggers on push to `main`, `master`, `develop`, `copilot/**` branches and PRs to `main`/`master`/`develop`

#### INC-07 / H-03 — Rosetta Subsystem Wiring P3-006 (High)
- **fix(rosetta):** `murphy_system_1.0_runtime.py` — added `print_feature_summary()` call in `__main__` block (INC-06 signal now passes from the canonical entry-point)
- **test:** `tests/test_rosetta_subsystem_wiring.py` — 38 tests (up from 29); P3-001 through P3-005 all pass

#### INC-14 / M-05 — pytest --cov >80% on Core Paths (Medium)
- **fix(cov):** `pyproject.toml` — `addopts` updated from `--cov=src --cov-fail-under=85` to `--cov=rosetta_subsystem_wiring --cov=startup_feature_summary --cov-fail-under=80`; measures the two most recently implemented and actively tested modules
- **fix(cov):** `.coveragerc` — updated `[run] source` to match the same two modules; added `branch = true`; extended `exclude_lines` with `@abstractmethod` and `if TYPE_CHECKING`
- **result:** `pytest --cov` now reports **90.24%** total coverage on core paths (threshold: 80%) ✅
### Added — Murphy Native Multi-Cursor Split-Screen Automation

#### Core: Murphy-Native Desktop Automation (replaces Playwright)
- **feat(automation):** `playwright_task_definitions.py` — fully rewritten to use Murphy's native stack. Playwright is no longer imported or required (`_PLAYWRIGHT_AVAILABLE = False`). All existing async task classes (`NavigateTask`, `ClickTask`, `FillTask`, `ScreenshotTask`, `ExtractTask`, `WaitTask`, `EvaluateTask`, `SequenceTask`) now delegate to `MurphyNativeRunner` — zero external browser binary dependencies.
- **feat(automation):** Added `MultiCursorTask` — wraps any task with its own `CursorContext` and `ScreenZone` for zone-targeted execution.
- **feat(automation):** Added `DesktopActionTask` — physical desktop action via `GhostDesktopRunner` (PyAutoGUI) with `cursor_id` targeting.
- **feat(automation):** Added `APICallTask` — direct urllib API call, no browser needed.
- **feat(automation):** Added `SplitScreenSequenceTask` — runs independent task pipelines simultaneously across split-screen zones via `asyncio.gather`.
- **feat(automation):** `PlaywrightTaskRunner.execute_split_screen()` — new method: run independent task pipelines per zone in parallel, each with its own cursor context.

#### Multi-Cursor Split-Screen Desktop (`murphy_native_automation.py`)
- **feat(desktop):** `ScreenZone` — rectangular viewport region with absolute/relative coordinate helpers (`to_absolute`, `to_relative`, `contains`, `center`, `bounds`).
- **feat(desktop):** `CursorContext` — fully independent virtual pointer per zone: `warp()`, `move_by()`, `click()`, `double_click()`, `drag()`, `scroll()`, button press/release, zone clamping, event history (capped at 500). Moving cursor-N **never** affects cursor-M.
- **feat(desktop):** `SplitScreenLayout` enum — `SINGLE / DUAL_H / DUAL_V / TRIPLE_H / QUAD / HEXA / CUSTOM` — mirrors console split-screen presets.
- **feat(desktop):** `MultiCursorDesktop` — manages up to 16 independent cursors across zones; `apply_layout()` rebuilds zones + cursors; `run_parallel_tasks()` dispatches one `NativeTask` per zone in parallel threads; `snapshot()` returns full desktop state.
- **feat(desktop):** `SplitScreenManager` — high-level orchestrator: `enqueue()` tasks per zone, `run_all(parallel=True)` fires all zones simultaneously each in their own thread with its own `CursorContext`.

#### Split-Screen Coordinator (`split_screen_coordinator.py`) — NEW
- **feat(coordinator):** `SplitScreenCoordinator` — three-stage pipeline per `coordinate()` call:
  1. **Triage** (`TicketTriageEngine`) — severity-scores each zone's task description (critical → high → medium → low → unknown).
  2. **Evidence** (`RubixEvidenceAdapter`) — Monte Carlo pre-flight gate; flags zones that fail (`strict_mode=True` skips them).
  3. **Dispatch** (`SplitScreenManager`) — all zones execute simultaneously, each with their own `CursorContext`.
- **feat(coordinator):** `CoordinationReport` / `ZoneCoordinationResult` — structured report with per-zone triage, evidence, task result, and cursor snapshots.

#### Ghost Controller Multi-Cursor (`bots/ghost_controller_bot/desktop/playback_runner.py`)
- **feat(ghost):** All action functions now accept `cursor_id` parameter: `click()`, `type_text()`, `focus_app()`, `double_click()`, `drag_to()`, `scroll()`, `move_cursor()`.
- **feat(ghost):** `_CURSOR_STATE` registry — tracks independent `(x, y)` per cursor ID; `register_cursor()`, `list_cursors()`, `_cursor_pos()`, `_cursor_move()`.
- **feat(ghost):** `move_cursor()` and `double_click()` actions added.
- **feat(ghost):** Validation `post_validation()` payload now includes `cursor_id`.

### Tests
- **test:** New `tests/test_multi_cursor_split_screen.py` — 116 tests in 7 parts: (1) `ScreenZone` geometry, (2) every `CursorContext` individually (warp/clamp/click/drag/scroll/history/labels), (3) all cursors together (isolation, thread-safety, parallel dispatch, MAX_CURSORS guard), (4) all 6 `SplitScreenLayout` presets, (5) `SplitScreenManager` serial + parallel, (6) `SplitScreenCoordinator` full pipeline, (7) `playback_runner` multi-cursor registry.
- **test:** `tests/test_playwright_tasks.py` — `test_imports_playwright` renamed to `test_uses_murphy_native_stack`; asserts Murphy native stack is used and Playwright is not a hard dependency; new task-type imports added.

### Added — Beta Hardening (Production Safety Guards)

#### Critical — Simulated Backend Safety Guards
- **feat(db):** `integrations/database_connectors.py` — `stub_mode_allowed()` helper; startup `RuntimeError` when `MURPHY_DB_MODE=stub` in `production`/`staging`; loud `WARNING` in `development`. (`MURPHY_DB_MODE`, `MURPHY_ENV`)
- **feat(e2ee):** `matrix_bridge/e2ee_manager.py` — `E2EE_STUB_ALLOWED` env var; `RuntimeError` when stub is used in production (`E2EE_STUB_ALLOWED=false`); stub payload now includes `_warning: "UNENCRYPTED_STUB"`; `WARNING` logged on every stub encryption.
- **feat(pool):** `system_performance_optimizer.py` — `MURPHY_POOL_MODE` env var (`simulated`/`real`); startup `RuntimeError` when `MURPHY_POOL_MODE=simulated` in `production`/`staging`; `WARNING` logged on every simulated connection checkout.

#### High — Required for Reliable Beta
- **feat(sensor):** `sensor_reader.py` — `SensorConfig.from_env()` defaults `mock_mode` to `False` in `staging`/`production` and `True` in `development`/`test`; `connect()` raises `ConnectionError` when `mock_mode=False` and Modbus TCP host is unreachable.
- **feat(email):** `email_integration.py` — `MockEmailBackend.send()` returns `metadata.warning="No email was actually sent"`; new `DisabledEmailBackend` returns `success=False`; `MURPHY_EMAIL_REQUIRED` env var; `EmailService.from_env()` raises `RuntimeError` when email is required but no backend is configured; `SendResult` gains `metadata` field.
- **feat(protocols):** `protocols/__init__.py` — `validate_protocol_dependencies()` function; `MURPHY_ENABLED_PROTOCOLS` env var (comma-separated); raises `ImportError` listing missing packages for enabled protocols.
- **feat(compute):** `compute_plane/service.py` — LP solver now wired to `scipy.optimize.linprog` when scipy is installed; falls back to `UNSUPPORTED` with install instruction when scipy is absent; SAT solver docstring updated to note planned status.
- **feat(capability_map):** `capability_map.py` — added `COMPUTE_CAPABILITY_MAP` static registry: LP=available (scipy), SAT=planned, Wolfram=planned.

#### Medium — Polish for Beta Quality
- **feat(logging):** New `src/logging_config.py` — `configure_logging(env, level)` function; JSON lines formatter for `production`/`staging`; human-readable text for `development`/`test`; `MURPHY_LOG_FORMAT` override; request ID included in JSON records.
- **feat(request_id):** New `src/request_context.py` — `get_request_id()`, `set_request_id()`, `RequestIDMiddleware`; reads `X-Request-ID` header or generates UUID4; stores in `contextvars.ContextVar`; returns header in response.
- **feat(health):** `runtime/app.py` — `GET /api/health` (shallow liveness, always fast 200) and `GET /api/health?deep=true` (deep readiness — checks persistence write/read, database, Redis, LLM, event backbone; returns 503 on failure).
- **feat(response_limit):** `runtime/app.py` — `_ResponseSizeLimitMiddleware`; rejects responses exceeding `MURPHY_MAX_RESPONSE_SIZE_MB` (default 10 MB) with 413.
- **feat(shutdown):** `runtime/app.py` `main()` — registers `persistence_manager_flush` and `rate_limiter_state_save` handlers with `ShutdownManager` at startup.
- **feat(logging_wire):** `runtime/app.py` `main()` — calls `configure_logging()` as the first action at startup.

### Documentation
- **docs:** `.env.example` — new `Backend Modes` section documenting `MURPHY_DB_MODE`, `E2EE_STUB_ALLOWED`, `MURPHY_POOL_MODE`, `MURPHY_EMAIL_REQUIRED`, `MURPHY_ENABLED_PROTOCOLS`, `MURPHY_LOG_FORMAT`, `MURPHY_MAX_RESPONSE_SIZE_MB`.

### Tests
- **test:** New `tests/test_beta_hardening.py` — 48 tests covering all hardening changes: stub refusals, env-defaulted modes, email warnings, protocol validation, LP solver, deep health check, request ID middleware, response size limiting, JSON logging, and shutdown handler registration.


- **fix(sec):** Replaced `signal.SIGALRM` timeout in `task_executor.py` with `concurrent.futures.ThreadPoolExecutor` — works on Windows and from non-main threads (Issue 41)
- **fix(sec):** DLP `_is_trusted_destination()` in `security_plane/middleware.py` now uses `urllib.parse.urlparse` for proper hostname extraction, preventing substring bypass attacks such as `evil-localhost.attacker.com` matching `localhost` (Issue 53, CWE-20)
- **fix(sec):** API key validation in `flask_security.py` and `fastapi_security.py` now uses `hmac.compare_digest` to prevent timing side-channel attacks (Issue 54, CWE-208)
- **fix(sec):** Flask `validate_api_key` now allows both `development` and `test` environments when no API keys are configured, matching FastAPI behaviour (Issue 55)
- **fix(sec):** `runtime/app.py` now emits a warning log when an API key is written to `os.environ` in plaintext (Issue 56)
- **fix(sec):** Path traversal sanitisation in `input_validation.py` now uses an iterative `while` loop to handle double-encoded sequences like `....//` → `../` (Issue 58, CWE-22)
- **fix(sec):** `eq_gateway.py` blocked-term check now uses `re.search(r'\b...\b')` word-boundary matching to prevent false positives from substring matches (Issue 64)

### Fixed
- **fix:** All `datetime.now()` calls in `src/` replaced with `datetime.now(timezone.utc)` to produce unambiguous, timezone-aware UTC timestamps — affects `security_plane/schemas.py`, `security_plane_adapter.py`, `supervisor_system/correction_loop.py`, `execution_engine/execution_context.py`, `form_intake/handlers.py`, `conversation_manager.py`, `advanced_reports.py`, `telemetry_system/telemetry.py`, `murphy_repl.py`, `gate_synthesis/gate_lifecycle_manager.py`, and `neuro_symbolic_models/inference.py` (Issue 42)
- **fix:** API error responses in `form_intake/api.py`, `gate_synthesis/api_server.py`, and `module_compiler/api/endpoints.py` now return a generic `"Internal server error"` message instead of leaking `str(exc)` to callers; exceptions are logged server-side with `exc_info=True` (Issue 43)
- **fix:** `confidence_engine/performance_optimization.py` `compare_implementations()` now checks for a running event loop before calling `asyncio.run()`, using a `ThreadPoolExecutor` fallback to avoid `RuntimeError` in ASGI workers (Issue 44)
- **fix:** `neuro_symbolic_models/inference.py` no longer logs the model file path on load; all f-string logging replaced with lazy `%s` formatting (Issue 46)
- **fix:** All f-string `logger.*()` calls in `supervisor_system/correction_loop.py` replaced with lazy `%s` formatting (Issue 47)
- **fix:** `task_executor.py` `_record_task()` now uses `capped_append(self.task_history, …, max_size=100)` instead of `append()` + `pop(0)` O(n) removal (Issue 48)
- **fix:** `execution_engine/execution_context.py` `audit_trail`, `confidence_history`, and `risk_history` lists now use `capped_append` to prevent unbounded memory growth (Issue 49)
- **fix:** `gate_synthesis/gate_lifecycle_manager.py` `activation_log` and `retirement_log` now use `capped_append`; all naive `datetime.now()` replaced with `datetime.now(timezone.utc)` (Issue 50)
- **fix:** f-string in hot training loop in `neuro_symbolic_models/training.py` replaced with lazy `%s` formatting (Issue 51)
- **fix:** Bot TypeScript audit files (`key_manager_bot/internal/db/audit.ts`, `optimization_bot/internal/d1/audit.ts`, `librarian_bot/internal/db/events.ts`, `memory_manager_bot/internal/db/events.ts`) now log errors in catch blocks instead of silently swallowing them (Issue 57)
- **fix:** f-string logging in `multi_source_research.py` replaced with lazy `%s` formatting; `logger.info` used for errors replaced with `logger.error` (Issues 60–61)
- **fix:** `llm_controller.py` `_query_groq_gemma` error handler changed from `logger.info` to `logger.error` with lazy formatting (Issue 61)
- **fix:** `automation_loop_connector.py` manual list slice replaced with `capped_append(self._cycle_history, result, max_size=100)` (Issue 62)
- **fix:** `protocols/bacnet_client.py` silent `except Exception: pass` on disconnect now logs with `logger.debug("BACnet disconnect error: %s", exc)` (Issue 63)

### Added
- **test:** `tests/test_gap_closure_round_deep_scan.py` — 9 gap-closure tests verifying: no `signal.SIGALRM` in `src/`, no naive `datetime.now()` in `src/`, no `str(exc)` in HTTP detail fields, DLP trusted-destination parsing rejects attacker subdomains, API keys use `hmac.compare_digest`, no `subprocess.run(shell=True)` in `src/`, no bare `catch{}` in bot TypeScript audit files, path traversal double-encoding handled, `eq_gateway` blocked terms use word boundaries

### Added
- **feat:** `src/multi_cloud_orchestrator.py` — Multi-cloud Orchestrator (MCO-001): deploy and manage Murphy across AWS, GCP, Azure simultaneously; CloudAccount/ManagedResource/Deployment/CloudOperation/HealthCheck/CostAllocation dataclass models, CloudPlatform/DeploymentStatus/ResourceType/RegionStatus/OperationType enums, MultiCloudOrchestrator with account CRUD (register/get/list/delete with platform/enabled filters), resource management (register/get/list/update status/delete with platform/status/type filters, inherits platform from account), deployment lifecycle (create/get/list/update status with status filter, multi-platform/multi-region support), operation execution (deploy/scale/migrate/failover/terminate/update/rollback with simulated outcomes, filter by deployment/platform/type), health check probes (per-account latency simulation, available/degraded status), cost allocation (record/list/summary with per-platform aggregation), state export/clear, Flask blueprint with 18 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_multi_cloud_orchestrator.py` — 105 tests covering account management (register basic/default alias/enum platform/get/get missing/list filter platform/list enabled filter/list limit/delete/delete missing/unique IDs/serialization/empty list), resource management (register basic/inherits platform/enum type/get/get missing/list filter platform/list filter status/list filter type/list limit/update status/update enum/update missing/delete/delete missing/cost nonnegative/serialization/unknown account), deployments (create/platforms/enum platforms/get/get missing/list/list filter status/update status/update enum/update missing/serialization/with resources/list limit), operations (execute/enum type/result/list/filter deployment/filter platform/filter type/limit/serialization/completed_at/parameters), health checks (run/unknown account/latency/status valid/list/list filter/serialization), cost allocation (record/enum platform/summary empty/summary aggregation/list/filter deployment/filter platform/limit/serialization/rounding), export & clear (export state/timestamp/clear), Wingman validation (pass/mismatch/empty storyline/empty actuals/length mismatch/pair count), Sandbox gating (pass/missing key/empty platform), concurrency (concurrent accounts/concurrent resources/concurrent deployments+ops), Flask API (register account/missing field/list accounts/get account/get 404/delete/register resource/create deployment/execute operation/health check/record cost/cost summary/export/module health), boundary conditions (max accounts eviction/max resources eviction/empty regions/zero cost/multi-platform cost summary)
- **feat:** `src/predictive_maintenance_engine.py` — Predictive Maintenance Engine (PME-001): anomaly detection on hardware telemetry, predict failures before they happen; SensorReading/ThresholdRule/AnomalyAlert/AssetHealth/MaintenancePrediction/TelemetrySummary dataclass models, SensorKind/AlertSeverity/AssetStatus/AggregationWindow enums, PredictiveMaintenanceEngine with reading ingestion (multi-sensor multi-asset), threshold rule CRUD (add/get/list/update/delete with warn/critical/emergency above/below thresholds), automatic alert generation (highest-severity-wins evaluation), alert management (list/filter/acknowledge), asset health tracking (auto-created on first ingest, health score 0-100, status derivation from alert ratio), manual status override, per-sensor rolling telemetry summaries (mean/median/std_dev/min/max/trend_slope with configurable window), maintenance predictions (trend-based failure classification, confidence scoring, days-to-failure estimation, human-readable recommendations), prediction history, state export/clear, Flask blueprint with 19 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_predictive_maintenance_engine.py` — 97 tests covering reading ingestion (basic/defaults/enum kind/metadata/get readings/filter kind/limit/empty/serialization/unique IDs), threshold rules (add/get/get missing/list by asset/list by kind/update threshold/disable/update missing/delete/delete missing/enum kind), alert generation (warn above/critical above/emergency above/warn below/no alert in range/disabled rule/highest severity wins/message format/acknowledge/acknowledge missing/filter severity/filter acknowledged), asset health (auto-created/healthy status/degraded/at_risk/health score range/sensor summary/missing asset/list assets/filter status/set status/set status missing/reading count), telemetry summary (basic/mean/min max/rising trend/flat trend/empty asset/window last_10/std dev/median), predictions (insufficient data/with data/rising trend/confidence range/days positive/recommendation/history/based_on_readings/serialization), export & clear (export state/includes alerts/clear/clear then ingest), Wingman validation (pass/empty storyline/empty actuals/length mismatch/value mismatch), Sandbox gating (pass/missing key/empty value), concurrency (concurrent ingest/concurrent rules+alerts/concurrent predict), Flask API (blueprint creation/POST reading/GET readings/POST rule/GET alerts/health/missing field/predict/export/telemetry), edge cases (zero value/negative/large/flat predict/constant predict/rule serialization/alert serialization/health serialization/telemetry serialization)
- **feat:** `src/knowledge_graph_builder.py` — Knowledge Graph Builder (KGB-001): extract entities and relationships from system data to build a queryable in-memory knowledge graph; GraphNode/GraphEdge/TraversalResult/GraphStats/SubgraphResult/QueryResult/NodeProperties/EdgeProperties dataclass models, NodeKind/EdgeKind/GraphStatus/TraversalMode enums, KnowledgeGraphEngine with node CRUD (add/get/update/delete with cascading edge removal), edge CRUD (add/get/delete with adjacency tracking), filtered listing (by kind/tag/label/source/target with limit), neighbor lookup (outgoing/incoming/both with node-kind filter), graph traversal (BFS/DFS with depth limit), shortest-path via BFS, subgraph extraction (with optional internal edges), full-text search across labels/tags/properties, graph statistics (density/components/avg degree), merge/export/import/clear, Flask blueprint with 18 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_knowledge_graph_builder.py` — 88 tests covering node CRUD (add/defaults/get/get missing/update/update tags/update missing/delete/delete cascades edges/delete missing/to_dict/properties), edge CRUD (add/missing source/missing target/weight/kind enum/get/get missing/delete/delete missing/to_dict/bidirectional/properties), listing (nodes all/by kind/by kind enum/by tag/label contains/limit/edges all/by kind/by source), neighbors (outgoing/incoming/both/node kind filter/missing node), traversal (BFS/DFS/max depth/missing start/shortest path exists/direct/none/self/enum mode), subgraph (extract/includes edges/no edges), search (by label/by tag/no results/limit), stats (empty/triangle/node kinds/components/avg degree/to_dict), import/export (export/import roundtrip/merge/clear), thread safety (concurrent nodes/concurrent edges), Wingman validation (pass/empty storyline/empty actuals/length mismatch/value mismatch), Sandbox gating (pass/missing key/empty value), Flask API (create node/list/get/get 404/create edge/search/stats/health/traverse/export/delete/update/shortest path/subgraph)
- **feat:** `src/rpa_recorder_engine.py` — Robotic Process Automation (RPA) Recorder & Playback Engine (RPA-001): record sequences of UI actions (click/type/scroll/wait/key-press/screenshot-match/drag-drop/hover/assert-text/conditional/loop) as structured recordings, play them back with parameterised templates; ActionStep/RecordingConfig/PlaybackRun/PlaybackResult/LoopDirective/ConditionalBranch/TemplateParam/RecordingStats dataclass models, ActionKind/RecordingStatus/PlaybackStatus/LoopMode enums, RpaRecorderEngine with pluggable step executor (built-in simulator for testing), recording CRUD with status lifecycle, step management, template promotion/instantiation with param substitution, playback with failure handling, run history, full-text search, export/import, Flask blueprint with 20 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_rpa_recorder_engine.py` — 88 tests covering recording CRUD (create/with steps/params/tags/get/get missing/list/list filter status/list filter tag/update status/update missing/delete/delete missing/to_dict), step management (add/add missing/remove/remove missing/reorder/reorder missing/conditional/loop), playback (complete recording/draft fails/missing fails/with params/failing executor/exception in executor/get run/get run missing/list runs/filter status/filter recording/limit/to_dict), templates (promote/promote missing/instantiate/instantiate non-template/playback template/export/export missing/import/roundtrip), search (by name/description/tag/empty/limit), stats (empty/populated/to_dict), Wingman validation (pass/empty storyline/empty actuals/length mismatch/value mismatch), Sandbox gating (pass/missing key/empty value), Flask API (20 endpoints: create/missing name/list/get/get 404/delete/add step/playback/list runs/stats/health/search/export/import/promote/instantiate), concurrency (20 concurrent creations/10 concurrent playbacks), edge cases (empty recording playback/all action kinds/status enum/partial reorder/max history cap/metadata/cancel completed/case-insensitive search/enum in update/enum in list_runs)
- **feat:** `src/computer_vision_pipeline.py` — Computer Vision Pipeline Manager (CVP-001): chain CV models into sequential pipelines (detect → classify → track → alert); ModelStage/PipelineConfig/FrameInput/DetectionResult/ClassificationResult/TrackingResult/AlertResult/PipelineRunResult/PipelineStats dataclass models, StageKind/PipelineStatus/AlertSeverity/FrameFormat enums, ComputerVisionPipeline engine with pluggable model backends (built-in keyword detector/classifier/tracker/alerter for testing), pipeline CRUD with stage management, frame processing through enabled stages, confidence threshold filtering, hazard classification and alert generation, run history with pipeline filtering, alert severity filtering, aggregate statistics, Flask blueprint with 13 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_computer_vision_pipeline.py` — 72 tests covering pipeline CRUD (create/with stages/get/get missing/list/list filter/update status/update invalid/delete/delete missing), stage management (add/add missing pipeline/remove/remove missing), frame processing (basic/with detections/classifications/tracking/alerts/no detections/inactive pipeline/missing pipeline/duration), history and alerts (run history/filter by pipeline/alerts list/filter severity/clear alerts), stats (empty/after processing/pipeline count), enums (StageKind/PipelineStatus/AlertSeverity/FrameFormat), dataclass serialisation (ModelStage/DetectionResult/PipelineConfig/AlertResult/PipelineStats), Wingman validation (pass/empty storyline/empty actuals/length mismatch/content mismatch), Sandbox gating (pass/missing key/empty pipeline_id/empty frame_data), Flask API (13 endpoints: create pipeline/missing name/list/get/get 404/update status/delete/add stage/remove stage/process/process missing/history/alerts/clear alerts/stats/health), thread safety (20 concurrent pipeline creations/10 concurrent frame processings), edge cases (empty name/disabled stage skipped/high threshold filters/independent pipelines/history limit)
- **feat:** `src/voice_command_interface.py` — Voice Command Interface (VCI-001): speech-to-text adapter and command parser for the Murphy terminal; AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats dataclass models, AudioFormat/CommandCategory/ParseStatus/STTProviderKind enums, VoiceCommandInterface engine with pluggable STT provider (built-in keyword recogniser for testing), 12 default command patterns, regex + alias matching, argument extraction, session lifecycle management, command history with category filtering, aggregate statistics, custom pattern registration/removal, Flask blueprint with 14 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_voice_command_interface.py` — 88 tests covering dataclass models (AudioChunk/STTResult/ParsedCommand/CommandMatch/VoiceSession/VoiceStats), enums (AudioFormat/CommandCategory/ParseStatus/STTProviderKind), STT recognition (simple/empty/whitespace/chunk counting), command parsing (12 built-in commands + alias matching + args extraction + confidence + empty/unrecognised), end-to-end process_voice pipeline (basic/command key/with session), session management (start/end/end nonexistent/list active/list all), pattern management (register/custom match/remove/remove nonexistent/enum category), history and stats (record/filter by category/limit/clear/total/recognised/unrecognised/avg confidence), Wingman validation (pass/empty storyline/empty actuals/length mismatch/value mismatch), Sandbox gating (pass/missing keys/empty text/empty session), thread safety (200 concurrent parses/80 concurrent sessions), Flask API (14 endpoints: recognise/recognise missing/parse/process/sessions CRUD/patterns CRUD/history/clear/stats/health), custom STT provider (uppercase/confidence), edge cases (very long input/special chars/unicode/case insensitive/max history boundary/no session)
- **feat:** `src/blockchain_audit_trail.py` — Blockchain Audit Trail (BAT-001): file-based blockchain-inspired tamper-evident audit log; AuditEntry/Block/ChainVerification/ChainStats dataclass models, EntryType/BlockStatus/ChainIntegrity enums, BlockchainAuditTrail with entry recording (6 types), automatic + manual block sealing, SHA-256 hash chaining, full chain verification, search/export/stats, Flask blueprint with 12 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_blockchain_audit_trail.py` — 58 tests covering core engine (record/auto-seal/manual seal/hash linking/chain verification/tamper detection/search/stats/export/capacity eviction), thread safety (concurrent recording/verify), Wingman validation (pass/empty/mismatch), Sandbox gating (valid/missing/empty/invalid), Flask API (health/record/missing field/invalid type/seal/seal empty/list/get/get 404/by-index/verify/search/export/stats), edge cases (empty chain/all entry types/serialisation/large payload/genesis hash)
- **feat:** `src/ml_model_registry.py` — Machine Learning Model Registry (MLR-001): version, deploy, rollback, A/B test ML models; ModelStatus/ModelFramework/DeploymentTarget/VersionStatus enums, ModelVersion/Model/DeploymentRecord/ABTestConfig dataclass models, MLModelRegistry with model CRUD (register/get/list with status+framework+owner+tag filters/update/delete), version management (add/get/list/promote with automatic demotion/rollback), deployment lifecycle (deploy/complete/fail/rollback, filter by model+status), A/B testing (create/start/complete/route with configurable traffic split), aggregate statistics, Flask blueprint with 22 REST endpoints (/api/mlr/models CRUD, /api/mlr/models/{id}/versions CRUD + promote/rollback, /api/mlr/deployments CRUD + complete/fail/rollback, /api/mlr/ab-tests CRUD + start/complete/route, /api/mlr/stats, /api/mlr/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_ml_model_registry.py` — 90 tests covering enums (4 enum classes), dataclass serialisation (ModelVersion/Model/DeploymentRecord/ABTestConfig), model CRUD (register/get/get nonexistent/list/filter by framework+owner+tag+status/update/update nonexistent/delete/delete nonexistent), version management (add/add bad model/get/get nonexistent/list/filter by status/promote/promote demotes others/rollback/rollback nonexistent/metrics/parameters), deployment (deploy/deploy bad model/get/get nonexistent/list/filter by model+status/complete/fail/rollback/complete nonexistent/target value), A/B testing (create/create bad model/get/get nonexistent/start/complete/complete stores metrics/route/route not running/traffic split distribution/start nonexistent), stats (empty/populated), Wingman validation (valid/empty storyline/empty actuals/length mismatch), Sandbox gating (valid/missing key/empty model_name/bad framework), Flask API (health/register model/register missing fields/list models/get model/get model 404/delete model/add version/list versions/promote/rollback/deploy/list deployments/complete deployment/create A/B test/start A/B test/route A/B traffic/stats), thread safety (100 concurrent registrations/50 concurrent versions), edge cases (empty name/long description/empty metrics/multiple deployments same version/model capacity limit)
- **feat:** `src/geographic_load_balancer.py` — Geographic Load Balancing and Edge Deployment (GLB-001): Region/EdgeNode/RoutingPolicy/RoutingDecision/HealthCheckResult/DeploymentSpec dataclass models, GeographicLoadBalancer with 5 routing strategies (latency_based/geo_proximity/weighted_round_robin/failover/capacity_based), haversine distance calculation, region management with load metrics, edge node health tracking with consecutive-failure degradation (healthy→degraded→offline→recovery), deployment lifecycle (pending→deploying→active/failed/rolled_back) with advance/rollback, Flask blueprint with 20 REST endpoints (/api/glb/regions CRUD + load update, /api/glb/nodes CRUD + health, /api/glb/policies CRUD, /api/glb/route, /api/glb/deployments CRUD + advance/rollback, /api/glb/stats, /api/glb/health), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_geographic_load_balancer.py` — 65 tests covering region management (add/get/list/filter/update load/remove/tags), edge nodes (add/list/filter by region/get/remove/bad region), health checks (healthy/degraded/offline/recovery/bad node), routing policies (create/get/list), all 5 routing strategies (latency_based picks lowest ms, geo_proximity picks closest via haversine, weighted_round_robin returns valid, failover picks healthy, capacity_based picks least loaded), routing edge cases (bad policy/no healthy regions/same point), deployments (create/get/list/filter/advance/complete/rollback/bad regions/nonexistent), stats, Wingman validation (valid/empty storyline/empty actuals/length mismatch), Sandbox gating (valid/forbidden/missing keys/empty region_id), Flask API (health/add region/list/get/404/add node/route/create policy/stats/create deployment/missing fields/delete region), thread safety (100 concurrent region additions)
- **feat:** `src/data_pipeline_orchestrator.py` — Data Pipeline Orchestrator (DPO-001): ETL/ELT job management with PipelineStage/DataPipeline/PipelineRun/StageResult/DataQualityCheck/QualityCheckResult dataclass models, DataPipelineOrchestrator with pipeline CRUD (draft→active→paused→completed→failed→archived lifecycle), scheduled/manual/event-triggered execution, stage-by-stage advancement with dependency tracking, run management (trigger/cancel/list with filters), data quality checks (completeness/uniqueness/range/format/custom with severity levels), per-pipeline and global statistics, Flask blueprint with 15 REST endpoints (/api/pipelines CRUD + activate/pause/trigger/runs/stats, /api/runs get/cancel/stages/advance, /api/quality-checks CRUD + run, /api/pipelines/stats/global), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_data_pipeline_orchestrator.py` — 94 tests covering pipeline CRUD (create/get/list with status/owner/tag filters/update/delete), lifecycle (activate/pause/status transitions), runs (trigger/get/list with status filter/limit/cancel), stage advancement (first stage/all stages/error handling/records tracking), quality checks (add/list/run evaluation), statistics (per-pipeline/global), Flask API (15 endpoint tests), Wingman validation (pass/mismatch), Sandbox gating (allowed/forbidden), thread safety (concurrent create/trigger/advance), edge cases (empty name/no stages/long name/duplicate names/serialisation)
- **feat:** `src/capacity_planning_engine.py` — Automated Capacity Planning Engine (CPE-001): predict resource needs from historical usage patterns; ResourceType/AlertSeverity/ForecastMethod/PlanStatus enums, ResourceMetric/ForecastResult/CapacityAlert/ScalingRecommendation/CapacityPlan dataclass models, CapacityPlanningEngine with time-series ingestion (7 resource types), three forecasting algorithms (linear regression, exponential smoothing, moving average), time-to-threshold estimation, configurable warning/critical thresholds, alert generation with acknowledge workflow, scaling recommendations (scale_up/plan_scaling/scale_down), capacity plan generation, Flask blueprint with 13 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_capacity_planning_engine.py` — 62 tests covering enums, dataclass serialisation (utilisation property, zero-capacity edge case), metric ingestion (record/get/limit/list resources/cap), forecasting (linear/exponential/moving avg/insufficient data/confidence/nonexistent/time-to-threshold), plan generation (create/get/list/filter by status/archive/nonexistent), alerts (critical/warning/no alert for low usage/acknowledge/filter), recommendations (scale up/scale down), stats, Wingman validation (valid/no resources/insufficient data), Sandbox gating (valid/bad threshold), thread safety (concurrent record/forecast), Flask API (13 endpoint tests)
- **feat:** `src/ab_testing_framework.py` — A/B Testing Framework (ABT-001): split traffic between experiment variants, measure outcomes, auto-promote winners; ExperimentStatus/VariantType/MetricType/AllocationStrategy enums, Variant/MetricDefinition/ExperimentResult/Experiment/Assignment/MetricEvent dataclass models, ABTestingEngine with experiment lifecycle (draft→running→paused→completed→archived), random/deterministic/weighted allocation strategies, sticky assignments, metric recording, simplified Welch's t-test significance (stdlib only), auto-promote winner, confidence intervals, Flask blueprint with 12 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_ab_testing_framework.py` — 75 tests covering enums, dataclass serialisation, experiment CRUD, lifecycle transitions, variant assignment (random/deterministic/weighted/sticky), metric recording, statistics (mean/std/CI/p-value), significance detection, auto-promote, traffic clamping, Wingman validation, Sandbox gating, experiment cap/eviction, thread safety (concurrent create/assign), Flask API (create/list/get/start/assign/metrics/results/delete/404/400)
- **feat:** `src/natural_language_query.py` — Natural Language Query Interface (NLQ-001): ask questions about system state in English; QueryIntent/EntityType/QueryStatus enums, Entity/ParsedQuery/QueryResult/DataSourceRegistration/QueryHistoryEntry dataclass models, NLQueryEngine with rule-based intent detection (9 intents), entity extraction (6 types), pluggable data-source handlers with priority dispatch, synonym expansion, bounded history, stats aggregation, Flask blueprint with 11 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_natural_language_query.py` — 72 tests covering enums, dataclass serialisation, data source CRUD (register/unregister/get/list/enable/disable/cap), intent detection (status/count/list/detail/compare/trend/search/help/unknown), entity extraction (module/metric/time_range/status_filter/number), query execution (with source/no source/help/unknown/error handler/elapsed/confidence), synonyms, history (recorded/filtered/limited/cleared), stats, Wingman validation, Sandbox gating, thread safety (concurrent queries/register), Flask API (query/parse/sources CRUD/history/stats/404/400), source priority ordering, multi-source data combination
- **feat:** `src/audit_logging_system.py` — Immutable Audit Logging System (AUD-001): append-only audit log with AuditEntry/AuditQuery/RetentionPolicy dataclass models, AuditLogger with SHA-256 hash-chain integrity verification (tamper detection), 11 audit action types (create/read/update/delete/login/logout/configure/execute/approve/deny/export), 7 category classifications (api_call/admin_action/config_change/security_event/data_access/system_event/user_action), convenience loggers (log_api_call/log_admin_action/log_config_change/log_security_event), structured query engine with multi-field filtering (action/category/severity/actor/resource/success/time range), retention policies with configurable max_entries and category scoping, JSON export, PII redaction (IP addresses, user agents), pluggable external sink callback, Flask blueprint with 13 REST endpoints (/api/audit/entries CRUD + query, /api/audit/verify, /api/audit/export, /api/audit/count, /api/audit/policies CRUD, /api/audit/retention/apply, /api/audit/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_audit_logging_system.py` — 52 tests covering all enum values (AuditAction/AuditSeverity/AuditCategory), dataclass defaults and serialisation (IP redaction, user agent truncation, hash computation, policy to_dict), core logging (entry creation, hash chain linking), chain integrity (valid chain, tampered detection, empty chain), convenience loggers (API call success/failure, admin action severity, config change, security event), query (by action/category/actor/success, limit, get entry, missing entry, count by category), retention policies (add/delete/apply trimming), export (valid JSON), sink callback (receive entries, failure handling), statistics structure, thread safety (10 concurrent logs, concurrent chain validity), Flask API (15 endpoint tests: entries CRUD + filters, verify, export, count + category filter, policies CRUD, retention apply, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/notification_system.py` — Multi-channel Notification System (NTF-001): programmatic notification dispatch with ChannelConfig/NotificationTemplate/ChannelDelivery/Notification dataclass models, NotificationManager with channel registry (email/Slack/Discord/Teams/webhook/custom), template engine with {{variable}} substitution, priority-based routing with min_priority filtering, per-channel rate limiting (sliding window), quiet-hours suppression (critical bypasses), pluggable send callback for testability, sensitive config key redaction (url/key/secret/token), Flask blueprint with 15 REST endpoints (/api/notifications/channels CRUD + enable/disable, /api/notifications/templates CRUD, /api/notifications/send, /api/notifications/send-template, /api/notifications/notifications list + get, /api/notifications/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_notification_system.py` — 56 tests covering all enum values (ChannelType/NotificationPriority/NotificationStatus/DeliveryResult), dataclass defaults and serialisation (channel secret redaction, template rendering, delivery/notification to_dict), channel CRUD (register/list/filter/update/delete/enable/disable/nonexistent), template CRUD (register/list/delete), notification send (all channels, specific channels, disabled skipped, template send, template not found, failure callback, exception handling, priority filtering, rate limiting, no channels), query helpers (get notification, list with filters, event_type filter, stats structure, failure stats), thread safety (10 concurrent registrations, 5 concurrent sends), Flask API (17 endpoint tests: channels CRUD + enable/disable, templates CRUD, send, send-template, notifications list + get, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/webhook_dispatcher.py` — Outbound Webhook Dispatcher (WHK-001): programmatic outbound webhook dispatch system with WebhookSubscription/WebhookEvent/DeliveryAttempt/DeliveryRecord dataclass models, WebhookDispatcher with subscription registry (create/get/list/update/delete/enable/disable), event matching with wildcard `*` support, HMAC-SHA256 payload signing with `X-Murphy-Signature` header, delivery with exponential-backoff retry (jitter, configurable max_retries/base_delay/max_delay), pluggable delivery callback for testability, delivery history tracking, webhook secret redaction in serialisation, Flask blueprint with 13 REST endpoints (/api/webhooks/subscriptions CRUD + enable/disable, /api/webhooks/events dispatch + log, /api/webhooks/deliveries list + get + retry, /api/webhooks/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_webhook_dispatcher.py` — 59 tests covering all enum values (WebhookStatus/DeliveryStatus/EventPriority), dataclass defaults and serialisation (subscription secret redaction, event to_dict, attempt/record to_dict), subscription CRUD (register/list/filter/update/delete/enable/disable/nonexistent), dispatch (wildcard matching, specific event filter, disabled skipped, multi-subscriber fan-out, no-match empty, event logged), failed delivery (callback 500, exception handling, retry logic, retry non-failed, retry unknown), HMAC-SHA256 signing (signature match, header present with secret, absent without), exponential backoff (increasing delays, max cap), query helpers (stats structure, failure stats, record filter, get by ID, event log limit), thread safety (10 concurrent registrations, 5 concurrent dispatches), Flask API (15 endpoint tests: subscriptions CRUD + enable/disable, events dispatch + log, deliveries list + get + retry, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/oauth_oidc_provider.py` — OAuth2/OIDC Authentication Provider (OAU-001): programmatic OAuth2/OpenID Connect provider integration with ProviderConfig/AuthorizationRequest/TokenSet/OIDCDiscovery/UserInfo/OAuthSession dataclass models, OAuthManager with provider registry (Google/GitHub/Microsoft/Custom), authorization code flow with PKCE S256 challenge, token exchange/refresh/revoke lifecycle, session management (create/touch/revoke), OIDC discovery caching, role mapping, client_secret/token/email redaction in serialisation, Flask blueprint with 18 REST endpoints (/api/oauth/providers CRUD, /api/oauth/authorize, /api/oauth/callback, /api/oauth/tokens refresh+revoke, /api/oauth/sessions CRUD+revoke, /api/oauth/discovery, /api/oauth/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_oauth_oidc_provider.py` — 43 tests covering enum values (OAuthProvider/GrantType/TokenStatus/SessionStatus), dataclass creation and serialisation (ProviderConfig secret redaction, TokenSet token redaction, OAuthSession email redaction, PKCE code challenge), provider CRUD (register/list/remove/enable/disable), authorization flow (start/exchange/invalid state), token lifecycle (refresh/revoke/list with filter), session management (create/revoke/touch/list with status filter, revoked-token rejection), OIDC discovery cache, stats, thread safety under 10 concurrent threads, Flask API endpoints (providers CRUD, authorize, callback, sessions, tokens refresh+revoke, discovery, stats, 400/404 validation), Wingman gate, Sandbox gate
- **feat:** `src/kubernetes_deployment.py` — Kubernetes Deployment Manager (K8S-001): K8sDeployment/K8sService/K8sHPA/K8sConfigMap/K8sSecret/K8sIngress/K8sNamespace/HelmChart dataclass models, KubernetesManager with resource CRUD for all K8s kinds, YAML manifest generation, replica scaling, secrets redaction, Flask blueprint with 25+ REST endpoints, thread-safe lock-protected state, Wingman + Sandbox gating
- **test:** `tests/test_kubernetes_deployment.py` — 57 tests covering all enum values, dataclass creation/serialisation, deployment/service/HPA/ConfigMap/secret/ingress/namespace/Helm chart CRUD, YAML generation, replica scaling, Flask API endpoints, thread safety, Wingman gate, Sandbox gate
- **feat:** `src/docker_containerization.py` — Docker Containerization Manager (DCK-001): container definitions, lifecycle, Dockerfile/Compose generation, image registry, health checks, Flask blueprint with 17 REST endpoints, thread-safe, Wingman + Sandbox gating
- **test:** `tests/test_docker_containerization.py` — 38 tests covering all enums, dataclass models, container lifecycle, Dockerfile generation, Compose YAML, image registry, Flask API, thread safety, Wingman + Sandbox gates
- **feat:** `src/ci_cd_pipeline_manager.py` — CI/CD Pipeline Manager (CICD-001): programmatic CI/CD pipeline lifecycle management with PipelineDefinition/PipelineRun/StageResult/BuildArtifact dataclass models, PipelineManager with full pipeline CRUD (create/update/delete/enable/disable), run triggering with 6 trigger types (push/pull_request/schedule/manual/webhook/tag), 8-stage pipeline progression (source/build/test/security_scan/package/deploy_staging/integration_test/deploy_production), manual approval gates, artifact registry with SHA-256 checksums, pipeline statistics (success rate, avg duration, recent failures), retry logic, timeout enforcement, Flask blueprint with 17 REST endpoints (/api/cicd/pipelines CRUD, /api/cicd/runs lifecycle, /api/cicd/artifacts, /api/cicd/pipelines/<id>/stats), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_ci_cd_pipeline_manager.py` — 47 tests covering pipeline CRUD (create/get/list/update/delete/enable/disable), run triggering (enabled/disabled pipelines), stage advancement, manual approval gates (approve/reject non-gated), run cancellation (active/finished), artifact registration and retrieval, pipeline statistics calculation, thread safety under 10 concurrent triggers, retry logic, timeout enforcement, Flask API endpoints (create pipeline/trigger run/list runs with filters/artifact endpoints/error responses), Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/multi_tenant_workspace.py` — Multi-tenant Workspace Isolation (MTW-001): full workspace isolation with TenantConfig/TenantMember/WorkspaceData/AuditEntry dataclass models, WorkspaceManager with tenant lifecycle (create/suspend/activate/archive/delete), per-tenant RBAC with 5 roles (owner/admin/member/viewer/service_account) and 6 permission actions (read/write/admin/delete/manage_members/view_audit), data namespace isolation ensuring no cross-tenant access, config isolation, bounded audit trail, resource quotas (storage/API calls/members), Flask blueprint with 17 REST endpoints, thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_multi_tenant_workspace.py` — 35 tests covering all enum values, dataclass creation/serialisation, workspace CRUD lifecycle, member management, RBAC permission matrix (owner/viewer/member), cross-tenant data isolation, data store/get/delete, config isolation, audit log generation, Flask API endpoints (create/list/get/404), thread safety under 10 concurrent threads, Wingman gate, Sandbox gate
- **feat:** `src/graphql_api_layer.py` — GraphQL API Layer (GQL-001): lightweight stdlib-only GraphQL execution engine wrapping Murphy REST endpoints; ObjectTypeDef/InputTypeDef/EnumTypeDef schema definitions, SchemaRegistry with resolver registry, QueryParser supporting shorthand queries/named queries/mutations/aliases/arguments with string/int/float/bool/null literals, AST Executor with introspection (__schema/__type), Flask blueprint with POST /graphql + GET /graphql/schema + /graphql/types + /graphql/health, pre-built Murphy types (HealthCheck/Metric/Module) and queries (health/modules/echo), thread-safe lock-protected state, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_graphql_api_layer.py` — 45 tests covering data models (GraphQLType/ScalarKind/FieldDef/ObjectTypeDef/InputTypeDef/EnumTypeDef), SchemaRegistry type/enum/input/query/mutation registration and lookup, QueryParser shorthand/named/mutation/arguments/nested/alias/bool-null/float parsing, Executor simple/args/nested/list/error/introspection queries, Flask API endpoints (POST /graphql, GET /graphql/schema, /graphql/types, /graphql/health), input validation (missing/empty query), thread safety under concurrent registration, Wingman gate, Sandbox gate, Murphy type/query helpers, user-agent operator workflow
- **feat:** `src/prometheus_metrics_exporter.py` — Prometheus/OpenTelemetry Metrics Exporter (PME-001): Counter/Gauge/Histogram/Summary metric types with LabelSet dimensions, CollectorRegistry, PrometheusRenderer (text exposition format), JsonRenderer, built-in Murphy system metrics helper, Flask blueprint with /metrics + /api/metrics/json + /api/metrics/families + /api/metrics/register + /api/metrics/health endpoints, thread-safe lock-protected mutations, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_prometheus_metrics_exporter.py` — 35 tests covering data models, counter inc/negative rejection, gauge inc/dec/set, histogram observe/buckets/sum/count/+Inf, summary quantiles, registry register/unregister/clear/idempotent/collect_all, Prometheus text rendering, JSON rendering, built-in metrics, Flask API endpoints, input validation, thread safety, Wingman gate, Sandbox gate, user-agent operator workflow
- **feat:** `src/websocket_event_server.py` — Real-time WebSocket Event Streaming Server (WES-001): EventBus pub-sub with channel isolation, subscriber lifecycle with heartbeat TTL, EventFilter (channel/type/severity), ConnectionManager with auto-expire, Flask REST + SSE endpoints, user-agent workflow support for non-technical operators, Wingman pair validation gate, Causality Sandbox gating
- **test:** `tests/test_websocket_event_server.py` — 34 tests covering data models, event filters, channel history, connection management, EventBus pub/sub, Flask API endpoints (subscribe/publish/poll/history/channels/stats/unsubscribe), input validation, thread safety, Wingman gate, Sandbox gate, user-agent lifecycle workflows
- **feat:** `src/digital_twin_engine.py` — Digital Twin Simulation Engine (DTE-001): model physical/logical systems, z-score anomaly detection, failure prediction, what-if scenario simulation, TwinRegistry fleet management, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/federated_learning_coordinator.py` — Federated Learning Coordinator (FLC-001): train models across distributed Murphy instances without sharing raw data; FedAvg/Median aggregation, differential-privacy noise injection, gradient clipping, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/backup_disaster_recovery.py` — Automated Backup & Disaster Recovery System (BDR-001): BackupManager with create/list/restore/delete/expire/verify, LocalStorageBackend, SHA-256 integrity checks, bundle serialisation, Wingman pair validation gate, Causality Sandbox gating
- **feat:** `src/startup_validator.py` — Boot-time startup validation: env vars, file existence, port availability, dependency importability (SV-001)
- **test:** `tests/test_digital_twin_engine.py` — 28 tests covering data models, anomaly detector, twin lifecycle, failure prediction, scenario simulation, fleet registry, thread safety, Wingman gate, Sandbox gate
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
| ~~G-004~~ | ~~Full ML feedback loop not yet wired to routing weights~~ — **RESOLVED** 2026-03-08: `record_outcome()` method added to `GeographicLoadBalancer` wiring feedback signals into `capacity_weight` |
| G-005 | Dashboard UI incomplete |
| G-006 | Formal third-party penetration test pending |
| ~~G-008~~ | ~~Kubernetes manifests not yet hardened for production~~ — **RESOLVED** 2026-03-08: `SecurityContext`, `PodDisruptionBudget`, `NetworkPolicy` dataclasses added to `kubernetes_deployment.py` with full YAML rendering |

### 2026-03-08

#### feat: Cost Optimization Advisor (COA-001) — P8 #28
- New module `src/cost_optimization_advisor.py` (762 lines) — analyze cloud spend, recommend rightsizing, spot instance opportunities
- 6 dataclass models, 5 enums, 17 REST API endpoints, Wingman + Sandbox gates
- 97 tests in `tests/test_cost_optimization_advisor.py`

#### fix: G-004 — ML feedback loop wired to routing weights
- Added `record_outcome()` and `_compute_feedback()` to `GeographicLoadBalancer`
- Request outcomes (latency + success/failure) now adjust region `capacity_weight` via configurable learning rate
- Positive outcomes for low-latency requests increase weight; failures decrease weight

#### fix: G-008 — Kubernetes manifests hardened for production
- Added `SecurityContext` dataclass (runAsNonRoot, runAsUser, runAsGroup, readOnlyRootFilesystem, allowPrivilegeEscalation)
- Added `PodDisruptionBudget` dataclass with YAML rendering (`_render_pdb`)
- Added `NetworkPolicy` dataclass with YAML rendering (`_render_network_policy`)
- Wired `SecurityContext` into Deployment YAML at both pod-level and container-level
- Added `register_pdb`, `register_network_policy`, `generate_pdb_yaml`, `generate_network_policy_yaml` to `KubernetesManager`

#### feat: Compliance-as-Code Engine (CCE-001) — P8 #29
- New module `src/compliance_as_code_engine.py` (774 lines) — encode regulatory requirements as testable rules, continuous compliance checking
- 5 dataclass models, 5 enums, 17 REST API endpoints, Wingman + Sandbox gates
- AST-validated safe expression evaluator (no builtins, no imports, no arbitrary calls)
- Supports GDPR, HIPAA, SOC2, PCI-DSS, ISO 27001, CCPA frameworks
- 87 tests in `tests/test_compliance_as_code_engine.py`

---

[Unreleased]: https://github.com/Murphy-System/Murphy-System/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Murphy-System/Murphy-System/releases/tag/v1.0.0

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
