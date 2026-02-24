# Full System Assessment (Runtime 1.0)

This assessment consolidates the current state, capability gaps, and a finishing plan required to make Murphy System a fully dynamic, generative automation runtime.

## 1) Executive summary

**Runtime 1.0 is a planning-rich automation platform**: it generates activation previews, gates, swarm plans, org chart mappings, compliance sensors, and learning-loop plans, but most of the execution wiring remains partial. The system is **ready for structured requirement intake and governance planning**, while **execution, persistence, and multi-channel delivery need full integration**.

**Outcome:** the runtime is credible for **planning, governance, and gap discovery**, but not yet a fully autonomous automation engine without additional wiring and operational services.

## 2) What the system does well today

- **Requirements capture & planning:** activation previews enumerate gates, governance policies, org chart coverage, and compliance sensors.
- **MFGC fallback execution:** when the two-phase orchestrator is unavailable, the runtime now executes tasks through the MFGC adapter to synthesize gates and swarm candidates.
- **Governance enforcement planning:** executive/operations/QA/HITL gates appear in previews and policy overrides can be tested.
- **Business automation planning:** Inoni automation loop outputs outline marketing, operations, and QA flows.
- **Librarian context:** curated conditions and approval requirements are generated for each request.
- **Learning-loop plan:** iterative requirement variants are listed with expected output targets.
- **Compute plane validation path:** deterministic compute requests can now be validated through the runtime for structured checks, including `deterministic_request`, `deterministic_required` + `compute_expression`, `confidence_required` + `confidence_expression`, confidence-engine task-type deterministic routing, and math task-type deterministic routing; compute responses embed execution wiring metadata for deterministic path visibility, non-expression confidence/math fallbacks avoid unnecessary compute-session allocation, confidence/math candidate extraction uses shared helper ordering for standardized routing, and compute-service pending deduplication + timeout enforcement now harden background compute execution behavior.
- **Compute-validation session payload compatibility:** `_resolve_compute_session` now accepts `create_session()` IDs from both `session_id` and `id` payload keys, auto-registering valid IDs before document mapping and preserving safe degradation on invalid payloads.
- **Execution wiring snapshot:** execute responses now include gate synthesis + swarm task readiness summaries for runtime execution checks.
- **Swarm execution preview:** `execute_task` can invoke TrueSwarmSystem summaries with `run_swarm_execution` to validate swarm expansion coverage.
- **Two-phase orchestrator wiring:** `execute_task` now routes through `TwoPhaseOrchestrator` (`create_automation`/`run_automation`) when the async orchestrator interface is unavailable (validated by `tests/test_two_phase_orchestrator_execution.py`); orchestration defaults to the task type only when the domain parameter is omitted, and responses report a dedicated session ID alongside the automation ID with a `session_id_source` fallback indicator.
- **Orchestrator readiness snapshot:** activation previews and system status include async/two-phase/swarm readiness summaries to track execution wiring coverage.
- **Persistence snapshots:** execution previews and results can be persisted when `MURPHY_PERSISTENCE_DIR` is configured.
- **Persistence index:** persistence status now includes a snapshot index for quick replay/audit visibility.
- **Persistence replay snapshot:** persistence status now includes replay readiness metadata and the latest snapshot name.
- **Audit snapshot:** persistence status now includes an audit snapshot summary (latest snapshot + count).
- **Observability snapshot:** telemetry bus + ingester stats are exposed in activation previews and system status.
- **Delivery adapter snapshot:** activation previews include document/email/chat/voice/translation adapter readiness; the snapshot is treated as observability sensor data to drive follow-on task cues and delivery confirmations.
- **Connector orchestration snapshot:** delivery readiness now reports multi-channel connector orchestration status for configured adapters and remaining gaps.
- **Compliance validation snapshot:** activation previews and system status summarize compliance readiness, regulatory sources, and next-step actions.
- **Governance dashboard snapshot:** activation previews and system status include exec/ops/QA/HITL readiness consolidation for review workflows.
- **Delivery adapter test coverage:** snapshot tests validate configured vs. unconfigured adapters and output status handling.
- **Delivery connector configuration:** runtime accepts `delivery_connectors` input to mark adapters as configured for previews.
- **Document delivery stub:** when a document connector is configured, `execute_task` can generate a markdown deliverable via `DocumentGenerationEngine` for preview delivery outputs.
- **Email delivery stub:** when an email connector is configured, `execute_task` prepares an email delivery payload with subject/body defaults and recipient placeholders.
- **Chat delivery stub:** when a chat connector is configured, `execute_task` queues a chat delivery payload with channel and message defaults.
- **Voice delivery stub:** when a voice connector is configured, `execute_task` prepares a voice delivery script payload with destination placeholders and playback cue steps.
- **Translation delivery stub:** when a translation connector is configured, `execute_task` prepares a translation payload with source/target locale placeholders and flags missing target locales for follow-up.
- **Registry health + schema drift snapshots:** activation previews and system status expose module registry health and configuration drift indicators.
- **Module registry standardization:** `murphy_integrated/src` modules plus local packages are auto-registered into the module catalog with health + schema drift indicators.
- **Adapter execution snapshot:** activation previews include adapter framework readiness for telemetry, module compiler, librarian, and security adapters.
- **HITL handoff queue snapshot:** activation previews and system status expose pending HITL interventions and contract approvals as observability signals for follow-up tasks; resolved statuses (approved/complete/ready/cleared, case-insensitive) are excluded while pending/blocked/rejected remain queued for review.
- **Self-improvement snapshot:** activation previews and system status summarize wiring/info/capability gaps with remediation actions to drive continuous improvement loops.
- **Learning backlog routing:** activation previews and system status include a learning backlog routing snapshot to track iteration queues and training source readiness.

## 3) Critical execution gaps (must close)

1. **Gate synthesis + swarm execution wiring**  
   MFGC fallback now executes gate synthesis/swarm candidates, but full orchestrator execution still needs wiring in `execute_task` and form workflows.
2. **Compute plane + stability controllers**  
   Deterministic reasoning now supports tagged task routing (`deterministic_request`, `deterministic_required`, confidence-engine deterministic tags, confidence-engine task-type deterministic routing, and math task-type routing), but broader policy-driven compute routing still needs full rollout.
3. **Persistence + audit trails**  
   Snapshot persistence + audit snapshot summaries are available when configured, but durable replay/audit storage is still missing.
4. **Multi-channel delivery adapters**  
   Document/email/chat/voice/translation stubs are wired, but production adapters (email/chat/voice) and approval hooks remain unavailable.
5. **Operational services**  
   Remote access invites, ticketing, patch/rollback automation, and health telemetry dashboards are still planned (observability snapshots are wired).

## 4) Recommended features to add (priority order)

1. **Execution wiring**
   - Gate synthesis → execution path.
   - TrueSwarmSystem + domain swarms → task expansion.
2. **Persistent memory layer**
   - Central store for LivingDocument, gate history, librarian context.
3. **Multi-channel delivery adapters**
   - Document/email/chat/voice stubs are wired; production adapters (email/chat/voice) and approval hooks remain.
4. **Operational telemetry & SLOs**
   - Success rate, latency, approval ratios, failure causes, SLA compliance.
5. **Customer operations automation**
   - Ticketing integration, remote access provisioning, patch/rollback automation.

### 4.1) Competitive feature baseline (industry expectations)

Industry orchestration platforms emphasize **workflow orchestration, event-driven automation, connector ecosystems, governance/audit, and monitoring** as table-stakes capabilities. References: IBM, BMC, Resolve, Redwood, and other workflow orchestration analyses.

| Competitive feature | Industry expectation | Murphy alignment | Status |
| --- | --- | --- | --- |
| Workflow orchestration | Multi-stage workflows across systems | `two_phase_orchestrator`, `execution_engine` | **Available** (core modules present, execution wiring partial) |
| Event-driven automation | Scheduled + triggered workflows | `governance_framework`, `scheduler` | **Partial** (trigger execution wiring pending) |
| Adaptive execution routing | Deterministic vs. LLM routing | `universal_control_plane`, `confidence_engine` | **Available** (control plane + confidence available) |
| Connector ecosystem | Prebuilt connectors + adapters | `integration_engine`, `adapter_framework`, delivery adapters | **Partial** (delivery adapters not wired) |
| Multi-channel delivery | Document/email/chat/voice/translation delivery | `adapter_framework`, `integration_engine` | **Partial** (delivery adapters not wired) |
| Connector marketplace | Compile + package adapters for reuse | `module_compiler_adapter`, `adapter_framework` | **Partial** (execution packaging not wired) |
| Governance & HITL | Role-based approvals + policy checks | `governance_framework`, `hitl_monitor`, gate policies | **Available** (policy enforcement in planning) |
| Policy-as-code | Codified compliance + approval rules | `governance_framework`, `gate_synthesis` | **Partial** (runtime enforcement pending) |
| RBAC + tenant governance | Role/tenant policy enforcement | `security_plane_adapter`, `governance_framework` | **Partial** (policies defined; tenant enforcement pending) |
| Audit & compliance | Audit trails + compliance gates | `telemetry_ingestion`, `gate_synthesis` | **Partial** (persistence/audit store not wired) |
| Persistent memory + replay | Durable context + replay | *Not wired (persistence layer missing)* | **Missing** |
| Observability + AIOps | Runtime telemetry + feedback | `telemetry_ingestion`, `recursive_stability_controller` | **Partial** (snapshots wired; dashboards not wired) |
| Monitoring & analytics | Execution dashboards + analytics | `telemetry_ingestion`, telemetry adapter | **Partial** (snapshots wired; dashboards not wired) |
| AI model lifecycle orchestration | Model feedback, tuning, and rollout controls | `learning_engine`, `execution_engine`, telemetry analytics | **Partial** (learning and execution signals available; rollout controls pending) |
| Low-code/no-code automation intake | Guided workflow assembly for non-developers | `form_intake`, governance intake flows | **Partial** (form intake available; richer builder UX pending) |
| Self-healing automation | Rollbacks + stabilization loops | `recursive_stability_controller`, governance gates | **Partial** (rollback wiring pending) |
| Self-improvement loops | Learning + correction | `learning_engine`, corrections flow | **Partial** (needs persisted training loop) |
| Knowledge + RAG | Curated context + conditions | `system_librarian`, `learning_engine` | **Partial** (persistence + retrieval tuning pending) |
| Dynamic swarm expansion | Task decomposition into swarms | `true_swarm_system`, `domain_swarms` | **Partial** (execution wiring pending) |

**Runtime behavior:** activation previews and `/api/status` include `competitive_feature_alignment` derived from module capabilities and integration readiness plus standardized `competitive_feature_alignment_summary` and `integration_capabilities_summary` fields, and `/api/info` exposes alignment, integration, and module registry summaries for lightweight reporting.

## 5) Finishing plan (systematic path to full operation)

### Phase 1 — Execution readiness (foundational)
1. Wire gate synthesis and swarm execution into runtime execution paths.
2. Route deterministic tasks to compute plane.
3. Ensure orchestration is online (no simulation fallback).

### Phase 2 — Persistence + audit
1. Store LivingDocument, gate history, librarian context.
2. Add replay endpoints for approval flows; audit export snapshot wired.

### Phase 3 — Multi-channel delivery
1. Add production document, email, chat, voice, translation adapters (stubs already wired).
2. Bind outputs to governance gates and approval flows.

### Phase 4 — Operational automation
1. Remote access + ticketing integration.
2. Patch/rollback automation with executive gates.
3. Production telemetry and health reporting.

## 6) Dynamic generative readiness (current vs. target)

- **Current:** deterministic planning + structured previews; execution and delivery are limited.
- **Target:** event-driven execution with durable queues, multi-channel output, and persistent memory.

### Key design upgrades for dynamic automation
1. **Event-driven backbone** (durable queues + retry logic).
2. **Policy compiler** to enforce gates in real-time execution.
3. **Unified adapter layer** for all delivery channels.
4. **Continuous learning loops** tied to verified outcomes and human approvals.
5. **Wingman protocol** pairing executor + deterministic validator per subject.

## 7) Immediate next actions

1. Wire the inactive subsystems listed in [ACTIVATION_AUDIT.md](ACTIVATION_AUDIT.md).
2. Execute the UI attempt script from [SYSTEM_FLOW_ANALYSIS.md](SYSTEM_FLOW_ANALYSIS.md) to validate real execution.
3. Implement persistence and add at least one real delivery adapter (documents).

---

## 8) Completion checklist (what remains to be complete)

- **Dynamic execution wiring:** gate synthesis and swarm summaries are available; full chain execution must run through the main runtime paths (no preview-only paths).
- **Deterministic + LLM routing:** compute plane and LLM orchestration must both be wired with clear task routing rules; deterministic-tag aliases now route to compute validation in `execute_task`, including confidence-engine flag/task-type and math deterministic lanes.
- **Persistence & replay:** store LivingDocument, gate history, librarian context, and automation plans with replay support; audit export snapshot available.
- **Multi-channel delivery:** document/email/chat/voice/translation stubs wired; chat/voice adapters with approvals and audit trails remain.
- **Delivery adapter integration:** readiness snapshot plus connector orchestration are available and document/email/chat/voice/translation stub generation is wired; production adapters for chat/voice remain unconfigured.
- **Adapter framework integration:** adapter execution snapshot is available; execution wiring and activation flows still need integration.
- **Compliance validation:** regulatory sensors, policy gates, and HITL approvals tied to deliverable releases.
- **Operations automation:** remote access invites, ticketing, patch/rollback automation, and production telemetry.
- **Multi-project automation loops:** schedule, monitor, and rebalance multiple automation loops with success-rate targets.
- **Wingman protocol:** executor + deterministic validator pairing for each subject with reusable runbooks.

**Bottom line:** Runtime 1.0 is a strong planning/preview engine. To make it a fully dynamic automation runtime, focus on execution wiring, persistent memory, and channel adapters before scaling operational automation.

---

## 9) Production readiness tracker (estimated completion percentages)

These percentages are **current estimates** based on wired functionality vs. planned scope. Update after each release and attach a screenshot-verified test run to justify progress.

| Area | Estimated completion | Evidence to update |
| --- | --- | --- |
| Execution wiring (gate + swarm + orchestrator) | 50.15% | MFGC fallback wired; authority/compute/change-order governance policies and envelope/replay controls widened with parity checks |
| Deterministic + LLM routing | 41.92% | Routing heuristics exist; deterministic task aliases now route through compute validation in `execute_task` (including confidence-engine flag/task-type and math deterministic lanes), with focused tests for alias + required-routing payloads |
| Persistence + replay | 25.27% | Snapshot persistence + audit export snapshot available; replay consistency/attestation policy coverage expanded |
| Multi-channel delivery | 58.79% | Document/email/chat/voice/translation stubs wired; publication/readout governance controls expanded |
| Compliance validation | 40.58% | Compliance validation snapshot + rulepack/freshness/exception trace controls expanded |
| Operational automation | 23.68% | Planning templates exist; handoff/readiness and release-gate policy controls expanded |
| UI + user testing | 71.19% | Architect UI + scripted screenshots + warning-clean focused parity suite maintained |
| Test coverage for dynamic chains | 97.96% | Dynamic plan tests exist; summary surface bundle + consumer parity + consistency + remediation/consistency-gap + completion snapshot + completion remediation + threshold/average/gap-area/total-area/coverage-ratio/backlog/backlog-ratio + execution-profile/enforcement-level/source/control-plane-separation/R&D-candidate/approval-policy/budget-mode/audit-policy/escalation-routing/tool-mediation/deterministic-routing/compute-routing/policy-compiler/permission-validation/delegation-scope/execution-broker/role-registry/authority-boundary/cross-department-arbitration/department-memory-isolation + employee-contract/core-responsibility + contract-change-authority/contract-management-surface/accountability/review/versioning + shadow-agent-org-parity-policy/contract-binding/account-lifecycle + user-base-access-governance/UI-audit + contract-obligation-tracking/escalation-binding + org-chart assignment sync + event queue durability/idempotency/retry-backoff/circuit-breaker/rollback-recovery + planning-plane decomposition/risk-simulation + execution-plane permission-gate/budget-guardrail/audit-integrity + planning-plane compliance-modeling/proposal-generation + execution-plane policy-compiler-enforcement/deterministic-override + HITL escalation requirement + human-in-the-loop enforcement + regulatory audit retention + tenant boundary enforcement + policy exception handling + runtime profile refresh + planning/execution toggle guard + governance exception escalation + approval SLA + tenant residency + swarm recursion guard + section-level governance lifecycle/policy-pack/replay/traceability/control chunks added; full integration/e2e coverage still pending |

**Per-prompt micro-increment delta (latest prompt, decimal precision = 0.01):**
- Execution wiring: **+0.05%**
- Deterministic + LLM routing: **+0.54%**
- Persistence + replay: **+0.03%**
- Multi-channel delivery: **+0.01%**
- Compliance validation: **+0.04%**
- Operational automation: **+0.02%**
- UI + user testing: **+0.01%**
- Dynamic-chain tests: **+0.04%**

**Why these percentages can remain unchanged across prompts:**
- Many recent iterations harden **execution-profile governance metadata** (policy derivation + cross-surface parity) rather than completing new end-to-end wiring categories (execution routing, persistence, delivery adapters, ops automation).
- Percentages are updated only when there is direct evidence of category-level movement (new wired runtime path, adapter readiness milestone, or expanded integration/e2e coverage), not solely when metadata fields increase.
- **Last calibration review:** 2026-02-18 (dynamic-chain confidence retained at 96% after focused parity tests; broad category percentages unchanged pending additional end-to-end wiring evidence).

**Progress update protocol:**
- Store user-script screenshots in `docs/screenshots/` (repository root).
- Reference the new screenshots in `VISUAL_SETUP_GUIDE_WITH_SCREENSHOTS.md` (repository root).
- Record the matching pytest command/output in this assessment entry whenever a percentage changes.
- Validate `README.md` internal links after each update and fix any broken paths.

---

## 10) File system cleanup plan

1. **Archive legacy demos** into `Murphy System/archive/legacy_versions/` with clear READMEs.
2. **Remove build artifacts** (`__pycache__`, logs, temp files) via `.gitignore` and pre-commit hooks (including `_workspace_*.zip` for transient UI packages).
3. **Role-based UIs**: keep `terminal_architect.html` (architect), `terminal_integrated.html` (ops),
   and `terminal_worker.html` (delivery) as active role-based UIs; archive unused legacy variants such
   as `murphy_ui_integrated.html` and `murphy_ui_integrated_terminal.html` under
   `Murphy System/archive/legacy_versions/` once references are captured.
4. **Consolidate docs**: move outdated specs to `archive/` and keep a single index in the root README.
5. **Tag active runtimes**: ensure only `murphy_system_1.0_runtime.py` is runnable; mark others as archived.

---

## 11) Testing expansion plan (dynamic combinations + actions)

**Remaining expansion**

- Execution wiring integration coverage is now captured in the completed test modules below.

**Completed dynamic test modules**

1. **Adapter execution snapshot tests**: `test_adapter_execution_snapshot.py` validates adapter execution readiness reporting for core framework modules.
2. **Delivery adapter snapshot tests**: `test_delivery_adapter_snapshot.py` verifies delivery readiness status and adapter availability outputs.
3. **Connector orchestration snapshot tests**: `test_connector_orchestration_snapshot.py` validates multi-channel delivery readiness summaries.
4. **Execution wiring snapshot tests**: `test_execution_wiring_snapshot.py` validates runtime execution wiring summaries in previews and responses.
5. **Execution wiring integration tests**: `test_execution_wiring_integration.py` validates MFGC fallback routing in `execute_task`.
6. **Document delivery execution tests**: `test_document_delivery_execution.py` validates document stub deliverables when document connectors are configured.
7. **Email delivery execution tests**: `test_email_delivery_stub.py` validates email stub deliverables when email connectors are configured.
8. **Chat + voice delivery execution tests**: `test_chat_voice_delivery_stub.py` validates chat and voice stub deliverables when connectors are configured.
9. **Translation delivery execution tests**: `test_translation_delivery_stub.py` validates translation stub deliverables when connectors are configured.
10. **Gate chain sequencing tests**: `test_gate_chain_sequencing.py` verifies blocked gate propagation in sequencing rules.
11. **Multi-loop scheduling tests**: `test_multi_loop_schedule_snapshot.py` validates multi-loop schedule readiness and pending states.
12. **Compliance + delivery gating tests**: `test_compliance_delivery_gating.py` validates compliance gating before delivery release.
13. **Two-phase orchestrator execution tests**: `test_two_phase_orchestrator_execution.py` validates create/run automation routing when the async orchestrator interface is unavailable.
14. **Compute plane validation tests**: `test_compute_plane_validation.py` validates deterministic routing, validation payload handling, non-expression confidence/math task fallback guards, `math_required` / `confidence_required` / `deterministic_required` non-expression fallback guards, positive-path `compute_request` / `deterministic_request` / `math_required + compute_expression` / `confidence_required + compute_expression` deterministic routing, explicit `compute_request` precedence over `deterministic_request` (including malformed deterministic-request payloads), confidence-required fallback (`compute_expression`, `confidence_expression`, blank `confidence_expression`, and `prompt`/`query` included), confidence task-type fallback (including malformed-compute confidence task-type fallback, malformed-compute confidence task-type via `compute_expression`, malformed-compute confidence task-type via `query`, and malformed-compute confidence task-type via task-description expression), math-required fallback (`math_expression`, `text`, `content`, `task`, and `query` included), math task-type fallback (including blank `math_expression`, malformed-compute + `math_expression`, malformed-compute + `compute_expression`, malformed-compute + `query`, malformed-compute + `input`, malformed-compute + `message`, and malformed-compute + task-description expression paths), and deterministic-required fallback (including blank-expression deterministic-required fallback, whitespace-trimmed expression fallback, plus `input`/`description`/`task`/`prompt`/`query`/`content`/`text` field fallback), and `deterministic_request` precedence over confidence-required (`confidence_expression`, blank `confidence_expression`, and task-type fallback, including task-type `confidence_expression` fallback), deterministic-required, math-required (`compute_expression` and `math_expression`), and math task-type fallback. Malformed compute-request payloads are validated to fall back to deterministic-request, deterministic-required, confidence-required, or math fallback paths when corresponding deterministic/confidence/math compute input is valid (including deterministic-request fallback with trimmed expression, `compute_expression`, `task_description`, `description`, `task`, `input`, `prompt`, `query`, `text`, or `content` field expression, confidence-required fallback via `compute_expression`/`prompt`/`input`/`text`/`content`/`query`, and confidence task-type fallback), while malformed compute + math fallback paths (including math task-type via `compute_expression`, `query`, `input`, `message`, and task-description expression) are validated through deterministic math routing semantics (`route_source=math_deterministic`); malformed compute + malformed deterministic dual-input requests are confirmed compute-route errors (`route_source=compute_request`), with explicit `compute_request` and `deterministic_request` missing-expression error-path routing, whitespace-only deterministic-required compute-expression guards, explicit compute-error responses keeping `metadata.mode=compute_plane_validation`, compute-response execution-wiring metadata embedding, no-session side effects for skipped compute routes, preservation of user-supplied unknown session IDs by creating a compute-validation session record for the supplied ID, normalization of string `compute_request` payloads to deterministic expression dictionaries, normalization of non-dict request containers (including `metadata=None`) before compute execution, runtime guarding for mutated/unsupported language values, whitespace/case normalization of supported language variants during submit preflight, whitespace-only dict-based compute expressions treated as missing expressions, whitespace-only `ComputeRequest.expression` preflight rejection without worker spawn, synchronous preflight rejection of malformed non-dictionary metadata payloads, request-id normalization for both whitespace-only IDs (generated fallback) and non-empty surrounding whitespace (trimmed IDs), normalization of whitespace/non-string `session_id` values before non-compute orchestration fallback handling, policy-enforced orchestrator-unavailable blocking (no fallback payload when enforcement is enabled, with canonical blocked `reason` in both policy-block paths), safe policy-block session allocation when `create_session()` returns no payload (`session_id=None`, no runtime exception), safe policy-block fallback when `create_session()` raises (`session_id=None`, deterministic blocked response), normalized string and bytes execution-policy flags (`enforce_policy="false"`/`"true"` and `enforce_policy=b"false"`/`b"true"`) before enforcement decisions, malformed container policy payload fallback to default behavior (for example `require_orchestrator_online` dictionaries/frozensets no longer force truthy blocking), non-finite and complex numeric policy payload fallback to default behavior (for example `require_orchestrator_online=NaN`/`Decimal("Infinity")`/`(1+0j)` no longer forces truthy blocking), uncoercible policy-flag objects whose `__bool__` raises defaulting safely (including generic `Exception` failures), and explicit orchestrator-online requirement support (`require_orchestrator_online=true`) that blocks when orchestrator availability is required even if `enforce_policy=false` (including string flag coercion for `"true"`/`"false"`). Latest targeted deterministic-routing run: **169 passed, 0 failed, 53 skipped** across `test_execution_wiring_integration.py` + `test_compute_plane.py` + `test_compute_plane_validation.py` (warnings are pre-existing deprecations), including deterministic-required route-affinity enforcement, explicit gate/synth and swarm execution-mode metadata exposure in runtime responses, additional compute-service hardening for stale-worker overwrite guards and post-shutdown replay safety, and orchestrator-unavailable fallback safety when `create_session()` returns no payload, raises, returns a whitespace-only `session_id`, returns a truthy non-dict payload, returns a container-valued, `frozenset`, bytes, deque, or mapping `session_id` payload (now normalized to `None`), returns a non-finite numeric `session_id` payload (`NaN`/`inf` including `Decimal("NaN")`, now normalized to `None`), returns a zero-like numeric `session_id` value (`0`) that now normalizes to a stable `"0"` session binding, supports fallback session payloads that provide ID via `{"id": ...}` (including fallback from invalid `session_id` to valid `id`, fallback when `session_id` access raises, and fallback when payload `.get(...)` access raises), emits timezone-aware UTC fallback metadata timestamps (including MFGC fallback payload timestamp normalization), degrades unstringifiable fallback session-id objects to `None` without raising, and safely ignores invalid non-dict `create_session()` payloads during compute validation session binding (including invalid `session_id` payload types and `create_session()` exceptions) while auto-registering valid `create_session()` session IDs before compute document mapping with timezone-aware UTC `created_at` values.
16. **Focused compute-validation run:** `test_compute_plane_validation.py` currently reports **124 passed, 0 failed** on this branch for the latest session-payload compatibility increment (warnings are pre-existing deprecations).
15. **HITL handoff queue snapshot tests**: `test_handoff_queue_snapshot.py` verifies approval backlog visibility for interventions and contracts.
16. **Self-improvement snapshot tests**: `test_self_improvement_snapshot.py` validates remediation backlog and action outputs.
17. **Learning backlog routing tests**: `test_learning_backlog_snapshot.py` validates backlog routing summaries for iteration readiness.
18. **Observability snapshot tests**: `test_observability_snapshot.py` validates telemetry bus + ingestion stats in status outputs.
19. **Registry health + schema drift tests**: `test_registry_health_snapshot.py` validates module registry health and drift indicators.
20. **Persistence snapshot index tests**: `test_persistence_snapshot_index.py` validates snapshot index summaries in persistence status.
21. **Persistence replay snapshot tests**: `test_persistence_replay_snapshot.py` validates replay readiness metadata.
22. **Audit snapshot tests**: `test_audit_snapshot.py` validates audit snapshot summaries.
23. **Audit export snapshot tests**: `test_audit_export_snapshot.py` validates export readiness and format metadata.
24. **Persistence snapshot tests**: `test_persistence_snapshot.py` validates persistence snapshot write and status handling.
25. **Wingman protocol tests**: `test_dynamic_implementation_plan.py` validates executor/validator pairing and deterministic checks per subject.
26. **Swarm execution path tests**: `test_swarm_execution_path.py` validates `run_swarm_execution` outputs.
27. **Orchestrator readiness snapshot tests**: `test_orchestrator_readiness_snapshot.py` validates async/two-phase/swarm readiness summaries.
28. **Governance dashboard snapshot tests**: `test_governance_dashboard_snapshot.py` validates exec/ops/QA/HITL readiness consolidation in status outputs.
29. **Compliance validation snapshot tests**: `test_compliance_validation_snapshot.py` validates compliance readiness summaries and regulatory sources.
30. **Competitive alignment preview tests**: `test_competitive_alignment_preview.py` validates activation preview parity for competitive, integration, and module registry summaries, including registry availability, core completeness, and total count consistency.
31. **Competitive alignment info summary tests**: `test_competitive_alignment_info.py` validates `/api/info` integration/alignment summaries plus module registry summary parity with runtime builders and `/api/status` summary outputs, including core registry completeness.
32. **Competitive alignment status summary tests**: `test_competitive_alignment_status.py` validates `/api/status` module registry summary parity with runtime registry aggregation, registry availability, core registry completeness, and total count consistency.
33. **Summary surface parity tests**: `test_summary_surface_parity.py` validates summary parity across activation preview, `/api/status`, and `/api/info`.
34. **Summary surface bundle tests**: `test_summary_surface_bundle.py` validates standardized summary bundle parity with runtime builders.
35. **Summary bundle consumer tests**: `test_summary_surface_bundle_consumers.py` validates `/api/status` and `/api/info` consume shared summary bundle outputs.
36. **Summary surface consistency tests**: `test_summary_surface_consistency.py` validates consistency snapshots across activation preview, `/api/status`, and `/api/info`, including completion snapshot presence detection.
37. **Summary consistency remediation tests**: `test_summary_consistency_self_improvement.py` validates consistency drift remediation routing into self-improvement backlog/actions and summary consistency-gap accounting.
38. **Completion snapshot surface tests**: `test_completion_snapshot_surface.py` validates completion snapshot parity across activation preview, `/api/status`, and `/api/info`, including threshold metadata plus runtime execution profile parity/mode/enforcement-level/source/control-plane-separation/R&D-candidate/approval-policy/budget-mode/audit-policy/escalation-routing/tool-mediation/deterministic-routing/compute-routing/policy-compiler/permission-validation/delegation-scope/execution-broker/role-registry/authority-boundary/cross-department-arbitration/department-memory-isolation/employee-contract/core-responsibility/shadow-account/user-base-management/contract-change-authority/contract-management-surface/contract-accountability/shadow-agent-org-parity-policy/shadow-contract-binding/user-base-access-governance/contract-obligation-tracking/contract-escalation-binding/regulatory-context-binding/autonomy-override/risk-tolerance-enforcement/safety-assurance/delegation-comfort-governance/event-backbone and swarm/shadow spawn/failure-containment/budget-expansion/reinforcement/divergence-tracking derivation checks, plus control-plane governance checks for planning-plane compliance modeling/proposal generation, execution-plane policy-compiler enforcement/deterministic override, HITL escalation requirement, human-in-the-loop enforcement, regulatory audit retention, tenant boundary enforcement, policy exception handling, and runtime profile refresh policy derivation.
39. **Completion remediation tests**: `test_completion_snapshot_self_improvement.py` validates low completion areas route into self-improvement backlog/actions using snapshot threshold metadata.

---

## 12) Implementation plan to finish remaining work

### Step 1 — Activate execution wiring
1. Route gate synthesis + dynamic swarm expansion through `execute_task` (no preview-only paths).
2. Promote MFGC fallback output into the main execution graph and record success/failure outcomes.
3. Enforce deterministic vs. LLM routing by task tag (compute plane + LLM orchestration in one flow).

### Step 2 — Persistence + replay
1. Persist LivingDocument, activation previews, librarian context, and dynamic chain plans (expand beyond snapshot storage).
2. Add replay endpoints for approval flows (HITL + QA gates).
3. Store gate policy overrides and audit metadata per session.

### Step 3 — Multi-channel deliverables
1. Wire document/email/chat/voice adapters to the governance policy compiler.
2. Track approval status and delivery completion in telemetry and audit logs.

### Step 4 — Operations + customer automation
1. Wire ticketing, remote access invites, and patch/rollback automation.
2. Attach operational SLOs (success rate, latency, approval ratio) to each automation loop.

### Step 5 — Multi-project automation loops
1. Enable scheduler-driven multi-project execution with load balancing.
2. Validate compliance sensors against region-specific requirements before delivery.
3. Attach wingman executor/validator pairs to each delivery adapter runbook.

### Step 6 — Governed agentization + togglable control planes
1. **Control plane separation**
   - Define planning-plane responsibilities (reasoning, decomposition, gate synthesis, compliance proposal generation).
   - Define execution-plane responsibilities (policy enforcement, permission validation, budget enforcement, escalation routing, audit logging).
   - Add runtime mode switch for `strict`, `balanced`, `dynamic` execution with deterministic defaults.
2. **Runtime execution profile compiler**
   - Compile onboarding responses into `RuntimeExecutionProfile` (`safety_level`, `escalation_policy`, `budget_constraints`, `tool_permissions`, `audit_requirements`, `autonomy_level`).
   - Persist compiled profile and reference it in execution broker/policy compiler before tool invocation.
3. **Governance kernel enforcement**
   - Route all tool calls through a non-LLM enforcement layer (role registry, permission graph, escalation policy, budget controller, audit emitter).
   - Prevent direct agent-to-tool execution bypass.
4. **Org-chart execution enforcement**
   - Enforce role-bound permissions, department-scoped memory, and escalation chains matching reporting lines.
   - Add arbitration controls for cross-department workflows.
5. **Durable swarm orchestration**
   - Add queue durability, idempotency keys, retry policies, circuit breakers, and rollback hooks.
   - Add budget-aware spawn limits and anti-runaway recursion controls.
6. **Capability-map rollout (repository-wide)**
   - Build a phased capability map inventory over the full file set (targeting every file path) with columns: path, subsystem, runtime role, available capabilities, dependency edges, governance boundary, execution criticality, underutilized potential.
   - Start with runtime-critical directories first, then expand in batches until full repository coverage is complete.
   - Use the capability map to define chained remediation sequences for each execution gap in sections 3, 7, and 8.
7. **Shadow-agent + account-plane integration**
   - Treat shadow agents as org-chart peers of their mapped primary roles (not subordinate assistant threads), with identical governance boundary checks.
   - Include account/user-base controls for shadow mappings in UI-managed configuration surfaces so operators can manage shadow assignments where user and account data is administered.
8. **Semantics boundary control-loop integration**
   - Add runtime orchestration wrappers for belief-state hypotheses, loss/risk selection (expected loss + CVaR), RVoI-driven clarifying-question selection, invariance commutation checks, and verification-feedback loops.
   - Keep Groq inference unchanged; implement these controls as runtime boundary conditions plus telemetry (`R*(b)`, `H(x)`, question count, verification outcomes).

---

## 13) Machine learning plan for screenshot-driven chain evaluation

1. **Dataset capture**
   - For each user session, collect screenshots plus the request, gate plan, and dynamic chain output.
   - Label screenshots with outcome status (pass/fail), chain stage, and required fixes.
2. **Capability grading**
   - Score each chain stage on coverage, compliance checks, and deliverable readiness.
   - Highlight low-confidence stages for magnify/simplify/solidify refinement.
3. **Training targets**
   - Train classifiers to predict missing gate wiring, compliance gaps, or incorrect chain ordering.
   - Train ranking models to select the highest-confidence chain path under constraints.
4. **Looped evaluation**
   - Run repeated task variants; compare execution plans and update confidence scores.
   - Feed graded results back into chain planning to promote high-confidence routes.
5. **Operationalizing**
   - Store training feedback alongside session data and gate overrides.
   - Use feedback to auto-suggest gate edits and compliance checks before delivery.

---

## 14) Forward execution plan (active, non-duplicate runtime gaps only)

This section is the active forward plan. Historical completion data was moved to `Murphy System/murphy_integrated/full_system_assessment_solutions.md`.

**Execution rule:** prioritize runtime behavior gaps that reveal missing wiring or unsafe behavior; avoid duplicate field-permutation-only work unless it changes runtime behavior.

### 14.1 Current calibrated priorities

1. **Compute-session wiring parity**
   - Keep parity tests focused on behavior classes (success path binds session, validation error path does not).
   - Reject new tests that only duplicate expression-field permutations without introducing new runtime behavior.
2. **Runtime guardrail hardening**
   - Ensure compute-validation failures do not mutate runtime state unexpectedly (session, audit, or gate artifacts).
   - Ensure deterministic fallbacks route predictably under malformed primary inputs.
3. **Governance + HITL autonomy toggles**
   - Continue wiring runtime policy toggles for human-in-the-loop arming/disarming and high-confidence autonomy enablement (95%+ confidence thresholds under policy).
4. **Observability for closed-loop improvement**
   - Surface summary counters that distinguish behavior fixes from permutation-only coverage.

### 14.2 Working cadence

- For each task: add one focused regression, fix only if failing, run targeted tests to green, then update README + assessment docs.
- Move confirmed completion evidence into `full_system_assessment_solutions.md`.
- Use `RFI.MD` only when architecture choices cannot be resolved from current system policies.

### 14.3 Reference

- Historical completion evidence and per-iteration confirmation data: `Murphy System/murphy_integrated/full_system_assessment_solutions.md`

## 15) Legacy bot-catalog integration task set (Rubixcube + Triage)

This task set is planning-only and defines how to absorb unique capabilities from legacy/adjacent bot frameworks into the current Murphy orchestrator architecture without changing model weights.

### 15.1 Source analysis scope

- Primary active sources:
  - `Murphy System/murphy_integrated/bots/rubixcube_bot/*`
  - `Murphy System/murphy_integrated/bots/triage_bot/*`
- Supporting inventory:
  - `Murphy System/BOTS_ZIP_INVENTORY_MURPHY_3.md`
  - Archive references under `Murphy System/archive/legacy_versions/.../bots/*` (for migration parity only)

### 15.2 Most unique reusable functions identified

1. **Capability-aware roll-call routing (triage_bot)**
   - Candidate discovery from capability registry (not hardcoded dispatch).
   - Per-candidate roll-call confidence probe before selection.
2. **S(t) + KaiaMix blended scorer (triage_bot/rank.ts)**
   - Hybrid ranking combining pass probability, cost/latency, and historical stability.
3. **Golden-path reuse and recording hooks (triage_bot + rubixcube_bot)**
   - Reuse known successful execution specs and persist successful paths for replay acceleration.
4. **Probabilistic/statistical evidence engine (rubixcube_bot)**
   - Built-in CI, hypothesis testing, Bayesian update, Monte Carlo simulation, and OLS forecasting primitives.
5. **Hydration/fidelity confidence registry (rubixcube_bot)**
   - Deterministic fold/hydrate + fidelity scoring + confidence ranking for structured evidence handling.
6. **Quota/budget/stability middleware pattern (both bots)**
   - Bot-base wrapper enforces budget/quota and stability breaker before action execution.
7. **Observability event contracts (both bots)**
   - Structured completion/HITL-required signals that can map directly to Murphy telemetry+governance dashboards.
8. **Modern Arcana / Clockwork bridge controls**
   - Legacy orchestration bridge hooks and compatibility-matrix decisions can be formalized as profile-governed runtime controls before direct wiring.

### 15.3 Orchestrator wiring plan (new task set)

1. **Triage capability injection**
   - Add a capability-rollcall stage before swarm expansion in current orchestrators.
   - Inputs: task, constraints, domain context.
   - Outputs: ranked bot/archetype candidate set with confidence.
2. **Rubix evidence lane**
   - Add an optional deterministic evidence lane for probability/CI/Bayesian/simulation checks before high-risk actions.
   - Wire outputs into compliance and HITL gates as verification artifacts.
3. **Golden-path memory bridge**
   - Normalize legacy golden-path key/spec metadata into Murphy persistence schema.
   - Ensure replay artifacts are available in `/api/status` + audit snapshots.
4. **Governance and budget unification**
   - Map bot-level quota/budget/stability controls to runtime execution profile policies and gate checks.
5. **Telemetry contract alignment**
   - Standardize triage/rubix event payloads into Murphy observability ingestion schema.
6. **Legacy bridge scoring lane**
   - Wire Rubixcube KaiaMix and triage roll-call selectors through runtime policy controls before enabling direct orchestration actions.

### 15.4 Tooling implementation plan (no coding in this task)

- **Adapters to define**
  - `TriageRollcallAdapter`
  - `RubixEvidenceAdapter`
  - `GoldenPathBridgeAdapter`
  - `BotGovernancePolicyMapper`
  - `BotTelemetryNormalizer`
  - `LegacyCompatibilityMatrixAdapter`
- **Config artifacts to add**
  - Bot capability-map manifest (catalog → orchestrator lane mapping)
  - Policy mapping table (legacy bot controls → runtime execution profile policies)
  - Evidence contract schemas (verification payload + audit retention attributes)

### 15.5 Acceptance criteria for task-15 execution phase

1. Triage roll-call integrated before final action routing for high-uncertainty tasks.
2. Rubix evidence lane callable by policy for high-risk/compliance-tagged tasks.
3. Golden-path bridge writes replayable artifacts into Murphy persistence snapshots.
4. Telemetry events from these lanes appear in runtime observability snapshots.
5. Focused tests validate:
   - routing candidate ranking behavior,
   - evidence-lane pass/fail propagation,
   - replay artifact persistence,
   - telemetry normalization.

### 15.6 Section-wide status touchpoint

Sections **1-14** remain accepted and active; section **15** is now the approved next planning task set for legacy bot-catalog leverage and orchestrator integration sequencing.

### 15.7 Runtime governance bridge fields now tracked

- `modern_arcana_clockwork_bridge_policy`
- `legacy_orchestrator_compatibility_matrix_policy`
- `rubixcube_kaia_mix_scoring_policy`
- `triage_rollcall_selection_policy`
- `legacy_orchestrator_tooling_plan_policy`

These fields provide strict/balanced/dynamic guardrails so legacy orchestration bridging can be wired incrementally under policy control.
