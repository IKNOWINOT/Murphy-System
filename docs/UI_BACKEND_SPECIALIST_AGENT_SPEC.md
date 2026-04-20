# UI-to-Backend Specialist Agent — Specification

**Spec Version:** 1.0.0
**Status:** Draft
**Owner:** Inoni LLC / Corey Post
**Agent ID:** `ui_backend_specialist`
**Agent Class:** `UIBackendSpecialistAgent`
**Authority Band:** MEDIUM
**Created:** 2026-04-02

---

## 1. Purpose & Mission

The **UI-to-Backend Specialist Agent** is an autonomous agent within the Murphy
System that owns the full vertical slice between any user-facing interface and
the backend services that power it. Its mission:

> _Bridge every UI surface to its correct backend endpoint — translating
> user intent captured in the browser into structured API calls, verifying the
> round-trip, and closing the loop with visual confirmation._

The agent is **not** a designer, nor a pure backend engineer. It is the
**integration seam specialist** — the engineer who ensures that a button click
on the frontend reaches the right handler, the response renders correctly, and
the contract between layers never drifts.

---

## 2. Persona

| Attribute        | Value |
|------------------|-------|
| **Name**         | Murphy Bridge |
| **Role**         | UI-to-Backend Integration Specialist |
| **Voice**        | Precise, evidence-driven, contract-first |
| **Strengths**    | API contract enforcement, cross-layer debugging, visual regression detection, E2E test authoring |
| **Weaknesses**   | Defers pure visual/UX design to design agents; defers pure algorithm work to backend agents |
| **Motto**        | _"If the contract is clean, the system is clean."_ |

---

## 3. Authority & Governance

Defined via `AgentDescriptor` (see `src/governance_framework/agent_descriptor.py`):

```python
AgentDescriptor(
    agent_id="ui_backend_specialist",
    version="1.0.0",
    authority_band=AuthorityBand.MEDIUM,
    resource_limits=ResourceCaps(
        max_cpu_cores=4,
        max_memory_mb=4096,
        max_execution_time_sec=600,       # 10 min per task cycle
        max_api_calls_per_sec=30
    ),
    access_scope=AccessMatrix(
        readable_paths=[
            "static/*",
            "templates/*",
            "Murphy System/src/*",
            "Murphy System/tests/*",
            "Murphy System/docs/*",
            "src/runtime/*",
            "src/dispatch*",
            "src/artifact_viewport*",
            "src/tool_registry/*",
            "src/mcp_plugin/*",
            "src/skill_system/*",
            "src/ui_data_service.py",
            "src/ui_testing_framework.py",
            "src/comms_hub_routes.py",
            "murphy_production_server.py",
        ],
        writable_paths=[
            "static/*",
            "templates/*",
            "Murphy System/src/*",
            "Murphy System/tests/*",
            "Murphy System/docs/*",
            "src/dispatch_routes.py",
            "src/artifact_viewport_api.py",
            "src/ui_data_service.py",
            "src/ui_testing_framework.py",
        ],
        network_endpoints=[
            "/api/dispatch/*",
            "/api/librarian/*",
            "/api/health",
            "/api/status",
            "/viewport/*",
            "/api/comms/*",
            "/api/tools",
            "/api/skills",
            "/api/mcp/plugins",
            "/api/errors/*",
        ],
        database_tables=[
            "dispatch_log",
            "pending_approvals",
            "tool_executions",
        ]
    ),
    action_permissions=ActionSet(
        allowed_proposals=[
            ActionType.PROPOSE_PLAN,
            ActionType.PROPOSE_CODE,
            ActionType.PROPOSE_ACTION,
            ActionType.VALIDATE,
            ActionType.EXECUTE,
            ActionType.COMMUNICATE,
        ],
        allowed_validations=[
            ValidationType.SYMBOLIC_CHECK,
            ValidationType.DETERMINISTIC_TEST,
            ValidationType.EMPIRICAL_VALIDATION,
        ],
        allowed_executions=[
            ExecutionType.COMPUTE,
            ExecutionType.TRANSFORM,
            ExecutionType.COMMUNICATE,
            ExecutionType.RETRIEVE,
        ],
        prohibited_actions=[]
    ),
    convergence_constraints=ConvergenceSpec(
        max_iterations=50,
        convergence_threshold=0.05,
        divergence_threshold=0.10,
        stability_window_ms=300000,       # 5 min
        max_state_changes_per_window=15
    ),
    retry_policy=RetrySpec(
        max_retries=3,
        min_backoff_ms=500,
        max_backoff_ms=15000,
        retry_condition=RetryCondition.STATE_CHANGE_REQUIRED
    ),
    scheduling_requirements=SchedulingSpec(
        priority=PriorityLevel.HIGH,
        cpu_reservation=2,
        memory_reservation=1024
    ),
    owner="Inoni LLC / Corey Post",
    description="UI-to-Backend integration specialist — API contracts, E2E verification, visual regression.",
    tags=["ui", "backend", "integration", "api-contracts", "e2e", "testing", "dispatch", "multicursor"]
)
```

---

## 4. Workflow — 7-Phase Pattern

The agent follows the Murphy standard 7-step workflow cycle, specialized for
UI↔Backend integration tasks.

### Phase 1 — ANALYZE

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 1a | Receive task from swarm coordinator or HITL dispatch | `dispatch_routes.py` — `/api/dispatch/call` |
| 1b | Identify affected UI surfaces (HTML pages, JS components, CSS) | `MultiCursorBrowser.navigate()` + `artifact_viewport.py` manifest scan |
| 1c | Identify target backend endpoints (routes, handlers, models) | `Librarian` — `/api/librarian/commands` catalog lookup |
| 1d | Extract current API contract (request/response schemas) | `tool_registry` — `search_by_input_field()`, `docs/api_contracts.yaml` |
| 1e | Detect contract drift between frontend expectations and backend reality | `artifact_viewport.py` — `search_content()` on both layers |

**Output:** Analysis document in Rosetta state `agent_state.analysis_summary`.

### Phase 2 — PLAN

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 2a | Define integration change set (files, endpoints, contracts) | Agent reasoning + `Librarian` routing spec |
| 2b | Identify required tools/skills from registry | `UniversalToolRegistry.search()` + `SkillManager.match_for_pipeline()` |
| 2c | Compose skill DAG for execution | `SkillManager.validate_composition()` |
| 2d | Estimate cost & risk | `ToolRegistry.get_budget_summary()`, authority gate check |
| 2e | Submit plan for approval if HITL required | `dispatch_routes.py` — HITL approval queue |

**Output:** Execution plan with skill composition in Rosetta state.

### Phase 3 — EXECUTE

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 3a | Open MultiCursorBrowser workspace | `MCB.launch()`, `MCB.auto_layout(n)` |
| 3b | Zone 1: Navigate to target UI page | `MCB.execute(navigate, zone_id="z0")` |
| 3c | Zone 2: Open backend source in viewport | `artifact_viewport.project()` on handler file |
| 3d | Modify frontend code (JS/HTML/CSS) | File edits via agent code-edit tools |
| 3e | Modify backend code (route, handler, model) | File edits via agent code-edit tools |
| 3f | Update API contract documentation | `docs/api_contracts.yaml` sync |
| 3g | Register any new tools/endpoints | `UniversalToolRegistry.register()` |

**Output:** Code changes committed, contract docs updated.

### Phase 4 — TEST

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 4a | Run unit tests for backend changes | `pytest` via dispatch tool call |
| 4b | Run UI component tests | `UITestingFramework` — interactive, visual regression, error state |
| 4c | Run E2E browser test | `MCB` — navigate → interact → assert_text/assert_visible/assert_url |
| 4d | Run API contract validation | `dispatch_routes.py` — `/api/dispatch/call` with schema check |
| 4e | Run visual regression snapshot comparison | `UITestingFramework.VisualRegressionTester` — baseline vs. current |
| 4f | Run security scan on UI surface | `UITestingFramework` — XSS prevention, injection detection |

**Output:** Test results matrix in Rosetta state.

### Phase 5 — FIX_RETEST

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 5a | Analyze test failures | Agent reasoning on test output |
| 5b | Apply targeted fixes | File edits, re-run failing tests |
| 5c | Rollback if divergence threshold hit | `MCB.rollback(checkpoint_id)` |
| 5d | Re-run full test suite | Loop back to Phase 4 |

**Convergence rule:** Max 3 fix-retest iterations before escalation.

### Phase 6 — TRANSITION

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 6a | Update Rosetta state with results | `RosettaManager.save_state()` |
| 6b | Notify dependent agents of contract changes | `multi_agent_coordinator` — team broadcast |
| 6c | Update Librarian knowledge base with new/changed endpoints | `Librarian` index refresh |
| 6d | Save workflow as reusable skill if novel | `SkillManager.save_workflow_as_skill()` |

### Phase 7 — DOCUMENT

| Step | Action | Murphy Asset Used |
|------|--------|-------------------|
| 7a | Generate change summary | Agent reasoning → markdown |
| 7b | Update API_ROUTES.md / API_DOCUMENTATION.md | File edits |
| 7c | Update capability_baseline.json if new modules added | `scripts/gap_detector.py --generate-baseline` |
| 7d | Archive task in Rosetta completed_tasks | `RosettaManager` persistence |

---

## 5. Murphy System Assets — Dependency Map

The agent depends on the following Murphy System modules at runtime:

| Asset | Module Path | Usage |
|-------|-------------|-------|
| **MultiCursorBrowser** | `src/agent_module_loader.py` | Browser automation, zone management, E2E testing, checkpointing |
| **Dispatch Router** | `src/dispatch_routes.py` | Tool invocation, NL parsing, HITL approval, cursor snapshots |
| **Dispatch Engine** | `src/dispatch.py` | Tool registry, tool calls, batch execution |
| **Artifact Viewport** | `src/artifact_viewport.py` | Content inspection, range projection, manifest generation |
| **Viewport API** | `src/artifact_viewport_api.py` | REST endpoints for viewport operations |
| **UI Data Service** | `src/ui_data_service.py` | System state snapshots, gate graphs, confidence breakdowns |
| **UI Testing Framework** | `src/ui_testing_framework.py` | Visual regression, interactive testing, security scanning |
| **Universal Tool Registry** | `src/tool_registry/` | Tool discovery, registration, confidence tracking, cost estimation |
| **Skill System** | `src/skill_system/` | Skill composition, DAG execution, workflow preservation |
| **MCP Plugin** | `src/mcp_plugin/` | External tool server integration, tool bridging |
| **Librarian** | `src/librarian/` | Knowledge base queries, capability routing, API catalog |
| **Rosetta Manager** | `src/rosetta/` | State persistence, recalibration, history translation |
| **Agent Descriptor** | `src/governance_framework/agent_descriptor.py` | Authority validation, resource limits, escalation |
| **Multi-Agent Coordinator** | `src/multi_agent_coordinator/` | Team coordination, parallel dispatch, result synthesis |
| **Error System** | `src/errors/` | Structured error codes (MURPHY-E0xx), error catalog |
| **Gate Bypass Controller** | `src/gate_bypass_controller.py` | Trust escalation, gate satisfaction for execution gates |
| **Swarm Rate Governor** | `src/swarm_rate_governor.py` | Traffic classification, rate limiting compliance |
| **Murphy Components** | `static/murphy-components.js` | Frontend web component library (15+ classes) |
| **Design System** | `static/murphy-design-system.css` | UI design tokens, theming |

---

## 6. Tool Registrations

The agent registers the following tools into `UniversalToolRegistry` upon
initialization:

| Tool ID | Name | Permission | Cost Tier | Description |
|---------|------|------------|-----------|-------------|
| `uib-001` | `ui_navigate` | LOW | FREE | Navigate MCB to a URL in a specified zone |
| `uib-002` | `ui_interact` | LOW | FREE | Click, fill, type, hover on a UI element via MCB |
| `uib-003` | `ui_assert` | UNRESTRICTED | FREE | Assert text, visibility, URL, title on current page |
| `uib-004` | `ui_screenshot` | UNRESTRICTED | FREE | Capture screenshot of a zone for visual regression |
| `uib-005` | `ui_visual_diff` | UNRESTRICTED | CHEAP | Compare screenshot against baseline hash |
| `uib-006` | `api_contract_check` | UNRESTRICTED | FREE | Validate request/response schema against contract |
| `uib-007` | `api_call` | LOW | CHEAP | Execute an API call via dispatch and return result |
| `uib-008` | `viewport_inspect` | UNRESTRICTED | FREE | Project a range of a source file via Artifact Viewport |
| `uib-009` | `e2e_test_run` | MEDIUM | MODERATE | Run a full E2E test scenario (navigate→interact→assert) |
| `uib-010` | `contract_drift_scan` | UNRESTRICTED | CHEAP | Scan for drift between frontend fetch calls and backend route schemas |
| `uib-011` | `security_scan_ui` | LOW | CHEAP | Run XSS/injection detection on a UI surface |
| `uib-012` | `save_integration_skill` | LOW | FREE | Save current workflow as a reusable Skill via SkillManager |

---

## 7. Rosetta State Schema Extension

The agent writes the following custom fields into its Rosetta state document
(Section 3 — `agent_state.custom`):

```json
{
  "agent_state": {
    "custom": {
      "active_workspace": {
        "mcb_instance_id": "string — MCB session UUID",
        "zone_layout": "string — auto_layout type (dual_h, quad, etc.)",
        "zones": [
          {
            "zone_id": "string",
            "purpose": "string — ui_page | backend_source | test_output | api_inspector",
            "current_url_or_path": "string",
            "last_action": "string — last MCB action type"
          }
        ]
      },
      "contract_registry": [
        {
          "endpoint": "string — e.g. POST /api/dispatch/call",
          "frontend_caller": "string — file:line where fetch/axios call lives",
          "backend_handler": "string — file:line where route handler lives",
          "schema_hash": "string — SHA-256 of request+response JSON schema",
          "last_verified_at": "ISO-8601",
          "status": "string — VERIFIED | DRIFTED | UNTESTED"
        }
      ],
      "visual_baselines": {
        "baseline_dir": "string — path to stored baseline screenshots",
        "entries": [
          {
            "page_url": "string",
            "screenshot_hash": "string",
            "captured_at": "ISO-8601",
            "threshold_pct": "float"
          }
        ]
      },
      "test_results_summary": {
        "unit_pass": "int",
        "unit_fail": "int",
        "e2e_pass": "int",
        "e2e_fail": "int",
        "visual_pass": "int",
        "visual_fail": "int",
        "security_pass": "int",
        "security_fail": "int",
        "last_run_at": "ISO-8601"
      }
    }
  }
}
```

---

## 8. Escalation Policy

| Trigger | Condition | Action |
|---------|-----------|--------|
| Contract drift detected | `contract_registry[].status == DRIFTED` for > 3 endpoints | Escalate to HITL review |
| Visual regression threshold exceeded | `visual_diff > 5%` | Escalate to design agent + HITL |
| Security vulnerability found | XSS/injection alert from `security_scan_ui` | Escalate to CRITICAL authority, block deploy |
| E2E test fails 3 consecutive times | FIX_RETEST loop exhausted | Escalate to swarm coordinator for peer agent assistance |
| API endpoint missing | Frontend calls endpoint not in Librarian catalog | Create endpoint stub + escalate to backend agent |
| Resource limit approaching | `execution_time_sec > 500` (of 600 max) | Checkpoint state, request time extension |

---

## 9. Swarm Integration

### As a Specialist in Agent Swarm

The agent registers as a specialist in the `agent_swarm` coordination pattern
(see `templates/agent_swarm.json`):

```json
{
  "id": "ui_backend_specialist",
  "type": "agent",
  "label": "UI-to-Backend Specialist",
  "description": "Handles all UI↔Backend integration tasks: API binding, E2E verification, contract enforcement, visual regression.",
  "config": {
    "model": "gpt-4o",
    "specialist_tags": ["ui", "backend", "api", "e2e", "visual-regression"],
    "dispatch_strategy": "targeted",
    "max_concurrent_zones": 8
  }
}
```

### Coordination with Peer Agents

| Peer Agent | Interaction |
|------------|-------------|
| **Design Agent** | Receives UI specs, sends visual regression reports |
| **Backend Agent** | Receives API contract changes, sends endpoint binding requests |
| **QA Agent** | Sends test results, receives test scenario definitions |
| **Security Agent** | Sends XSS/injection scan results, receives remediation directives |
| **DevOps Agent** | Sends deploy-readiness status, receives environment configs |

---

## 10. MultiCursorBrowser Workspace Patterns

The agent uses predefined MCB workspace layouts for common tasks:

### Layout: Contract Verification (dual_h)

```
┌─────────────────────────────────────────┐
│ Zone z0: UI Page (browser)              │
├─────────────────────────────────────────┤
│ Zone z1: Backend Source (viewport)      │
└─────────────────────────────────────────┘
```

### Layout: E2E Test Authoring (quad)

```
┌─────────────────────┬──────────────────┐
│ Zone z0: UI Page    │ Zone z1: Test    │
│ (live browser)      │ (test file edit) │
├─────────────────────┼──────────────────┤
│ Zone z2: API Docs   │ Zone z3: Test    │
│ (contract yaml)     │ Output (console) │
└─────────────────────┴──────────────────┘
```

### Layout: Full Integration Debug (hexa)

```
┌────────────┬────────────┬────────────┐
│ z0: UI     │ z1: Net    │ z2: API    │
│ (browser)  │ (requests) │ (docs)     │
├────────────┼────────────┼────────────┤
│ z3: Source │ z4: Tests  │ z5: Logs   │
│ (handler)  │ (pytest)   │ (server)   │
└────────────┴────────────┴────────────┘
```

---

## 11. Skill Compositions

The agent ships with the following pre-built skills:

### Skill: `uib-skill-contract-audit`

Scans all frontend fetch/axios calls, maps them to backend routes, and reports
drift.

```yaml
skill_id: uib-skill-contract-audit
name: API Contract Audit
steps:
  - step_id: scan_frontend
    tool_id: uib-010          # contract_drift_scan
    input_mapping: { target: "static/**/*.js" }
  - step_id: scan_backend
    tool_id: uib-008          # viewport_inspect
    input_mapping: { target: "src/dispatch_routes.py" }
    depends_on: [scan_frontend]
  - step_id: compare
    tool_id: uib-006          # api_contract_check
    input_mapping:
      frontend_calls: "{{ scan_frontend.output }}"
      backend_routes: "{{ scan_backend.output }}"
    depends_on: [scan_frontend, scan_backend]
```

### Skill: `uib-skill-e2e-smoke`

Navigates to a page, interacts with key elements, and asserts expected
outcomes.

```yaml
skill_id: uib-skill-e2e-smoke
name: E2E Smoke Test
steps:
  - step_id: navigate
    tool_id: uib-001          # ui_navigate
    input_mapping: { url: "{{ input.target_url }}", zone: "z0" }
  - step_id: interact
    tool_id: uib-002          # ui_interact
    input_mapping: { actions: "{{ input.interactions }}" }
    depends_on: [navigate]
  - step_id: assert
    tool_id: uib-003          # ui_assert
    input_mapping: { assertions: "{{ input.expected }}" }
    depends_on: [interact]
  - step_id: screenshot
    tool_id: uib-004          # ui_screenshot
    depends_on: [assert]
  - step_id: visual_check
    tool_id: uib-005          # ui_visual_diff
    input_mapping: { screenshot: "{{ screenshot.output }}" }
    depends_on: [screenshot]
```

### Skill: `uib-skill-visual-baseline`

Captures visual baselines for all configured pages.

```yaml
skill_id: uib-skill-visual-baseline
name: Visual Baseline Capture
steps:
  - step_id: navigate_pages
    tool_id: uib-001
    input_mapping: { urls: "{{ input.page_urls }}" }
  - step_id: capture
    tool_id: uib-004
    depends_on: [navigate_pages]
  - step_id: store_baselines
    tool_id: uib-012          # save_integration_skill
    input_mapping: { baselines: "{{ capture.output }}" }
    depends_on: [capture]
```

---

## 12. Configuration & Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `UIB_AGENT_ID` | `ui_backend_specialist` | Agent instance ID |
| `UIB_MCB_MAX_ZONES` | `8` | Max MCB zones per workspace |
| `UIB_VISUAL_THRESHOLD_PCT` | `2.0` | Visual regression threshold (%) |
| `UIB_CONTRACT_SCAN_GLOBS` | `static/**/*.js,templates/**/*.html` | Frontend file globs for contract scanning |
| `UIB_BACKEND_ROUTE_FILES` | `src/dispatch_routes.py,src/comms_hub_routes.py,src/runtime/app.py` | Backend route files to scan |
| `UIB_E2E_TIMEOUT_SEC` | `120` | Max E2E test execution time |
| `UIB_MAX_FIX_ITERATIONS` | `3` | Max fix-retest loops before escalation |
| `UIB_CHECKPOINT_ON_PHASE` | `true` | Auto-checkpoint MCB state at each phase transition |

---

## 13. Testing Requirements

The agent's own test suite must cover:

| Test Category | File | Min Tests |
|---------------|------|-----------|
| Tool registration & execution | `tests/test_uib_agent_tools.py` | 12 (one per tool) |
| Workflow phase transitions | `tests/test_uib_agent_workflow.py` | 7 (one per phase) |
| MCB workspace layouts | `tests/test_uib_agent_mcb.py` | 6 (per layout pattern) |
| Contract drift detection | `tests/test_uib_agent_contracts.py` | 10 |
| Visual regression | `tests/test_uib_agent_visual.py` | 5 |
| Escalation triggers | `tests/test_uib_agent_escalation.py` | 6 |
| Skill composition execution | `tests/test_uib_agent_skills.py` | 3 (per pre-built skill) |
| Rosetta state persistence | `tests/test_uib_agent_rosetta.py` | 5 |

**Total minimum:** 54 tests following the `G1-G9` commissioning docstring
format.

---

## 14. Commissioning Checklist

Before the agent is marked operational:

- [ ] `AgentDescriptor` instantiates without validation errors
- [ ] All 12 tools register in `UniversalToolRegistry` successfully
- [ ] All 3 pre-built skills pass `SkillManager.validate_composition()`
- [ ] MCB launches and auto-layouts to `dual_h`, `quad`, `hexa` without error
- [ ] Rosetta state document writes and reads correctly via `PersistenceManager`
- [ ] Contract drift scan runs against `dispatch_routes.py` and returns structured results
- [ ] Visual regression captures and compares baselines within threshold
- [ ] E2E smoke skill executes end-to-end (navigate → interact → assert → screenshot → visual diff)
- [ ] Escalation triggers fire correctly (drift > 3 endpoints, visual > 5%, security alert)
- [ ] Rate governor classifies agent traffic as `SWARM` tier (600 RPM)
- [ ] Agent registers as specialist in swarm coordinator
- [ ] All 54+ tests pass with `pytest -v --tb=short --timeout=60`

---

## 15. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-04-02 | Murphy System | Initial specification |
