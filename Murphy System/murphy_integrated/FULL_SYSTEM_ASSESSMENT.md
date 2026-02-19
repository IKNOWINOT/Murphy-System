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
- **Compute plane validation path:** deterministic compute requests can now be validated through the runtime for structured checks.
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
   Deterministic reasoning exists but is not invoked for tagged tasks.
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
- **Deterministic + LLM routing:** compute plane and LLM orchestration must both be wired with clear task routing rules.
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
| Execution wiring (gate + swarm + orchestrator) | 47% | MFGC fallback wired, orchestrator wiring still partial |
| Deterministic + LLM routing | 40% | Routing heuristics exist; compute plane not invoked end-to-end |
| Persistence + replay | 23% | Snapshot persistence + audit export snapshot available; durable storage not wired |
| Multi-channel delivery | 58% | Document/email/chat/voice/translation stubs wired with locale gating; orchestration snapshot added; production adapters with approvals pending |
| Compliance validation | 38% | Compliance validation snapshot added with regulatory sources + next-action guidance |
| Operational automation | 22% | Planning templates exist; ticketing/remote access not wired |
| UI + user testing | 70% | Architect UI + scripted screenshots now in place |
| Test coverage for dynamic chains | 96% | Dynamic plan tests exist; summary surface bundle + consumer parity + consistency + remediation/consistency-gap + completion snapshot + completion remediation + threshold/average/gap-area/total-area/coverage-ratio/backlog/backlog-ratio + execution-profile/enforcement-level/source/control-plane-separation/R&D-candidate/approval-policy/budget-mode/audit-policy/escalation-routing/tool-mediation/deterministic-routing/compute-routing/policy-compiler/permission-validation/delegation-scope/execution-broker/role-registry/authority-boundary/cross-department-arbitration/department-memory-isolation + employee-contract/core-responsibility + contract-change-authority/contract-management-surface/accountability/review/versioning + shadow-agent-org-parity-policy/contract-binding/account-lifecycle + user-base-access-governance/UI-audit + contract-obligation-tracking/escalation-binding + org-chart assignment sync + event queue durability/idempotency/retry-backoff/circuit-breaker/rollback-recovery + planning-plane decomposition/risk-simulation + execution-plane permission-gate/budget-guardrail/audit-integrity + planning-plane compliance-modeling/proposal-generation + execution-plane policy-compiler-enforcement/deterministic-override + HITL escalation requirement + human-in-the-loop enforcement + regulatory audit retention + tenant boundary enforcement + policy exception handling + runtime profile refresh + planning/execution toggle guard + governance exception escalation + approval SLA + tenant residency + swarm recursion guard policy checks added; full integration/e2e coverage still pending |

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
14. **Compute plane validation tests**: `test_compute_plane_validation.py` validates deterministic routing and validation payload handling.
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

## 14) Current iteration confirmation (sections 1-13 acceptance)

This update confirms that sections **1-13** remain active and accepted as the operating plan, with this iteration applying the same loop for analysis → implementation → targeted testing → documentation updates:

1. Revalidated runtime competitive alignment outputs against module registry data.
2. Expanded competitive baselines to include **AI model lifecycle orchestration** and **low-code/no-code automation intake** requirements.
3. Updated runtime competitive feature mapping and test coverage (`tests/test_module_registry.py`) so these requirements are tracked in activation/status outputs.
4. Updated root `README.md` and this assessment to reflect the latest confirmed system state.
5. Maintained standardization scope by preserving `.gitignore` protections for generated files/artifacts and keeping changes limited to assessment-aligned runtime/docs/test paths.
6. Aligned runtime status parity by exposing `integration_capabilities` + `competitive_feature_alignment` through `/api/status`, with focused regression coverage.
7. Added `/api/info` summary parity for integration and competitive alignment snapshots, validated by focused test coverage.
8. Added focused activation preview regression coverage for competitive alignment to keep preview/status/info feature reporting synchronized.
9. Standardized competitive alignment summary fields across preview/status/info outputs and extended focused tests to validate summary parity.
10. Standardized integration capability summary fields across preview/status/info outputs and extended focused tests to validate parity with full integration capability payloads.
11. Added `/api/info` module registry summary parity so lightweight metadata surfaces now align with preview/status registry reporting.
12. Added focused `/api/info` regression coverage to verify module registry summary parity against runtime aggregation output.
13. Added focused `/api/status` regression coverage to verify module registry summary parity against runtime aggregation output.
14. Added focused activation preview regression coverage to verify module registry summary parity against runtime aggregation output.
15. Hardened `/api/status` registry parity checks by asserting core registry completeness (`core_registered == core_expected`, no `core_missing` entries).
16. Hardened `/api/info` and activation preview registry parity checks by asserting core registry completeness (`core_registered == core_expected`, no `core_missing` entries).
17. Hardened `/api/status` and activation preview registry parity checks by asserting registry availability (`total_available >= core_expected`) alongside core completeness.
18. Hardened `/api/status` and activation preview registry parity checks by asserting summary total counts match module registry status totals.
19. Hardened `/api/info` parity checks by asserting integration/alignment summaries exactly match runtime builder outputs.
20. Hardened `/api/info` parity checks by asserting module registry summary consistency with `/api/status` outputs.
21. Hardened `/api/info` parity checks by asserting integration/alignment summary consistency with `/api/status` outputs.
22. Added cross-surface parity coverage so activation preview, `/api/status`, and `/api/info` report matching integration/alignment/registry summaries.
23. Standardized summary assembly via a shared runtime bundle builder and validated bundle parity with dedicated regression coverage.
24. Added consumer-level regression coverage to verify `/api/status` and `/api/info` use shared summary bundle outputs consistently.
25. Added summary consistency snapshots to activation preview, `/api/status`, and `/api/info` with regression coverage for consistent status checks.
26. Routed summary consistency drift into self-improvement remediation backlog/actions and validated the behavior with focused regression coverage.
27. Normalized self-improvement summary output so `consistency_gaps` is always reported (including non-drift paths) and validated with focused tests.
28. Added runtime completion snapshot outputs across preview/status/info and validated cross-surface parity with focused regression coverage.
29. Routed low completion areas into self-improvement remediation backlog/actions and validated behavior with focused regression coverage.
30. Extended consistency checks to validate completion snapshot presence across preview/status/info and detect missing completion data.
31. Aligned runtime completion snapshot dynamic-chain test percentage with section 9 tracker values for consistent cross-surface reporting.
32. Added completion threshold metadata to runtime completion snapshots and validated remediation behavior consumes that threshold.
33. Exposed completion remediation threshold in self-improvement summary outputs and validated both metadata-driven and fallback threshold paths.
34. Added completion average propagation to self-improvement summary outputs and validated metadata-driven/fallback behavior.
35. Added low-completion area ID propagation to completion snapshots and self-improvement summaries with focused remediation coverage.
36. Added completion total-area propagation to self-improvement summaries and validated metadata-driven/fallback behavior.
37. Added completion coverage-ratio propagation to self-improvement summaries and validated metadata-driven/fallback behavior.
38. Added completion backlog-item propagation to self-improvement summaries and validated metadata-driven/fallback behavior.
39. Added completion backlog-ratio propagation to self-improvement summaries and validated metadata-driven/fallback behavior.
40. Added governed-agentization/control-plane expansion planning (including execution-profile compilation and repository capability-map rollout) to section 12 for the next implementation phase.
41. Added runtime execution-profile surface propagation and mode-derivation validation across activation preview, `/api/status`, and `/api/info`.
42. Added execution-enforcement-level derivation in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
43. Added execution-profile source derivation (`onboarding` vs `default`) and validated cross-surface profile traceability with focused surface tests.
44. Added control-plane-separation-state derivation (`enforced`/`adaptive`/`relaxed`) in runtime execution profiles and validated cross-surface behavior with focused tests.
45. Added self-improvement R&D proposal candidate derivation in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
46. Added approval-checkpoint-policy derivation (`mandatory`/`conditional`/`on_demand`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
47. Added budget-enforcement-mode derivation (`hard_cap`/`soft_cap`/`user_tunable`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
48. Added audit-logging-policy derivation (`immutable_full_stream`/`standard_governance_stream`/`sampled_governance_stream`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
49. Added escalation-routing-policy derivation (`mandatory_human_chain`/`policy_scored_chain`/`exception_only_chain`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
50. Added tool-mediation-policy derivation (`allowlist_mandatory_mediation`/`policy_guarded_mediation`/`accelerated_mediation_with_guardrails`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
51. Added deterministic-routing-policy derivation (`deterministic_only`/`deterministic_preferred`/`deterministic_fallback`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
52. Added compute-routing-policy derivation (`deterministic_compute_lane`/`hybrid_compute_lane`/`adaptive_compute_lane`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
53. Added policy-compiler-mode derivation (`locked_policy_compilation`/`guarded_policy_compilation`/`adaptive_policy_compilation`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
54. Added permission-validation-policy derivation (`explicit_role_validation`/`policy_guided_validation`/`adaptive_validation_with_bounds`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
55. Added delegation-scope-policy derivation (`role_bound_delegation_only`/`policy_bounded_delegation`/`adaptive_delegation_with_caps`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
56. Added execution-broker-policy derivation (`broker_hard_gate`/`broker_policy_guarded`/`broker_adaptive_guardrailed`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
57. Added role-registry-policy derivation (`immutable_role_registry`/`governed_role_registry`/`adaptive_role_registry_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
58. Added authority-boundary-policy derivation (`hard_authority_boundaries`/`policy_scoped_authority_boundaries`/`adaptive_authority_boundaries_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
59. Added cross-department-arbitration-policy derivation (`explicit_executive_arbitration`/`policy_scored_arbitration`/`adaptive_arbitration_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
60. Clarified section-12 planning that shadow agents are org-peer role mirrors with account/user-base mapping management expected through UI-administered configuration surfaces.
61. Added department-memory-isolation-policy derivation (`strict_department_isolation`/`policy_scoped_isolation`/`adaptive_isolation_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
62. Added employee-contract-responsibility-policy derivation (`contract_bound_responsibilities_required`/`contract_guided_responsibilities`/`contract_aware_adaptive_responsibilities`) and core-responsibility-scope derivation in runtime execution profiles; validated strict/balanced/dynamic mapping with focused surface tests.
63. Reassessed dynamic-chain test completion confidence from 100% to 96% to reflect focused-surface validation depth and pending integration/e2e execution coverage.
64. Added shadow-agent-account-policy derivation (`identity_bound_shadow_accounts`/`policy_governed_shadow_accounts`/`adaptive_shadow_accounts_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
65. Added user-base-management-surface-policy derivation (`admin_ui_only`/`admin_ui_with_policy_api`/`admin_ui_plus_delegated_api_with_audit`) in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
66. Added employee-contract-change-authority-policy (`hr_admin_approval_required`/`policy_scoped_manager_plus_hr_approval`/`delegated_manager_updates_with_hr_audit`) and employee-contract-management-surface-policy (`hr_admin_ui_only`/`hr_admin_ui_with_policy_api`/`hr_admin_ui_plus_delegated_api_with_audit`) derivation in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
67. Added employee-contract-accountability-policy (`contract_obligation_attestation_required`/`contract_obligation_attestation_guided`/`contract_obligation_attestation_adaptive`) derivation in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
68. Added shadow-agent-org-parity-policy, shadow-agent-contract-binding-policy, user-base-access-governance-policy, employee-contract-obligation-tracking-policy, and employee-contract-escalation-binding-policy derivation in runtime execution profiles and validated strict/balanced/dynamic mapping with focused surface tests.
69. Added onboarding-governance profile derivation for `regulatory_context_binding_policy`, `autonomy_preference_override_policy`, `risk_tolerance_enforcement_policy`, `safety_level_assurance_policy`, and `delegation_comfort_governance_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
70. Added employee-contract/shadow-account governance profile derivation for `employee_contract_review_policy`, `employee_contract_versioning_policy`, `shadow_agent_account_lifecycle_policy`, `user_base_ui_audit_policy`, and `org_chart_assignment_sync_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
71. Added event-backbone governance profile derivation for `event_queue_durability_policy`, `idempotency_key_enforcement_policy`, `retry_backoff_policy`, `circuit_breaker_policy`, and `rollback_recovery_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
72. Added planning/execution control-plane governance profile derivation for `planning_plane_decomposition_policy`, `planning_plane_risk_simulation_policy`, `execution_plane_permission_gate_policy`, `execution_plane_budget_guardrail_policy`, and `execution_plane_audit_trail_integrity_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
73. Added swarm/shadow governance profile derivation for `swarm_spawn_governance_policy`, `swarm_failure_containment_policy`, `swarm_budget_expansion_policy`, `shadow_reinforcement_signal_policy`, and `behavioral_divergence_tracking_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
74. Confirmed focused test reporting format with explicit pass/fail counts (`2 passed, 0 failed`) while retaining dynamic-chain completion confidence at 96% based on targeted-surface validation scope.
75. Added control-plane governance profile derivation for `planning_plane_compliance_modeling_policy`, `planning_plane_proposal_generation_policy`, `execution_plane_policy_compiler_enforcement_policy`, `execution_plane_deterministic_override_policy`, and `hitl_escalation_comfort_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests.
76. Extended control-plane governance hardening with `human_in_the_loop_enforcement_policy`, `regulatory_audit_retention_policy`, `tenant_boundary_enforcement_policy`, `policy_exception_handling_policy`, and `runtime_profile_refresh_policy`, and standardized naming with `hitl_escalation_requirement_policy` (legacy `hitl_escalation_comfort_policy` retained as alias) while focused validation remained **2 passed, 0 failed** and dynamic-chain confidence remained **96%**.
77. Reconfirmed completion-percentage calibration rules: percentages remain unchanged when iterations only add governance metadata/parity checks without new category-level end-to-end wiring milestones; latest focused validation remained **2 passed, 0 failed**.
78. Added contract/shadow governance hardening profile derivation for `shadow_peer_role_enforcement_policy`, `shadow_account_user_binding_policy`, `employee_contract_scope_enforcement_policy`, `employee_contract_exception_review_policy`, and `user_base_tenant_boundary_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
79. Revalidated contract/shadow governance parity after adding runtime profile propagation for `shadow_peer_role_enforcement_policy`, `shadow_account_user_binding_policy`, `employee_contract_scope_enforcement_policy`, `employee_contract_exception_review_policy`, and `user_base_tenant_boundary_policy`; focused test result remained **2 passed, 0 failed**.
80. Added compliance/budget governance profile derivation for `compliance_event_escalation_policy`, `regulatory_override_resolution_policy`, `budget_ceiling_revision_policy`, `budget_consumption_alert_policy`, and `approval_checkpoint_timeout_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
81. Added compliance-budget lifecycle hardening profile derivation for compliance escalation, regulatory override resolution, budget ceiling revision, budget consumption alerts, and approval-checkpoint timeout governance policies, and reconfirmed focused surface validation output at **2 passed, 0 failed**.
82. Added onboarding-control-plane integrity governance profile derivation for `compliance_sensor_event_policy`, `policy_drift_detection_policy`, `onboarding_profile_revalidation_policy`, `control_plane_mode_transition_policy`, and `user_autonomy_preference_ui_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
83. Added recursion-residency governance profile derivation for `planning_execution_toggle_guard_policy`, `governance_exception_escalation_policy`, `approval_sla_enforcement_policy`, `tenant_residency_control_policy`, and `swarm_recursion_guard_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
84. Added contract-lifecycle governance profile derivation for `contract_renewal_gate_policy`, `shadow_account_suspension_policy`, `user_base_offboarding_policy`, `governance_kernel_heartbeat_policy`, and `policy_compiler_change_control_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
85. Added persistence-observability governance profile derivation for `replay_reconciliation_policy`, `audit_artifact_retention_policy`, `event_backpressure_management_policy`, `queue_health_slo_policy`, and `rollback_compensation_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
86. Added semantics telemetry-governance profile derivation for `runtime_telemetry_tokens_to_resolution_policy`, `runtime_telemetry_question_count_policy`, `runtime_telemetry_invariance_score_policy`, `runtime_telemetry_risk_score_policy`, and `runtime_telemetry_verification_feedback_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
87. Added semantics-boundary governance profile derivation for `semantics_belief_state_policy`, `semantics_loss_risk_policy`, `semantics_voi_question_policy`, `semantics_invariance_boundary_policy`, and `semantics_verification_feedback_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
88. Added semantics-control-loop governance profile derivation and runtime surface parity checks for `semantics_hypothesis_update_policy`, `semantics_likelihood_scoring_policy`, `semantics_rvoi_decision_policy`, `semantics_clarifying_question_budget_policy`, and `semantics_invariance_retry_policy`, plus supporting semantics boundary controls (`semantics_hypothesis_distribution_policy`, `semantics_cvar_risk_measure_policy`, `semantics_question_cost_policy`, `semantics_invariance_transform_set_policy`, `semantics_verification_boundary_policy`), with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed**).
89. Added semantics posterior-update governance profile derivation and runtime surface parity checks for `semantics_question_candidate_generation_policy`, `semantics_answer_prediction_policy`, `semantics_belief_normalization_policy`, `semantics_verification_loss_injection_policy`, and `semantics_action_revision_policy`, with strict/balanced/dynamic mapping validated via focused cross-surface tests (**2 passed, 0 failed; 38 warnings**).

**Current completion percentage snapshot (section 9, this iteration):**
- Execution wiring (gate + swarm + orchestrator): **47%**
- Deterministic + LLM routing: **40%**
- Persistence + replay: **23%**
- Multi-channel delivery: **58%**
- Compliance validation: **38%**
- Operational automation: **22%**
- UI + user testing: **70%**
- Test coverage for dynamic chains: **96%**
- Latest targeted run (`test_completion_snapshot_surface.py`): **2 passed, 0 failed**

---

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

### 15.4 Tooling implementation plan (no coding in this task)

- **Adapters to define**
  - `TriageRollcallAdapter`
  - `RubixEvidenceAdapter`
  - `GoldenPathBridgeAdapter`
  - `BotGovernancePolicyMapper`
  - `BotTelemetryNormalizer`
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
