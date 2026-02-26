# Murphy System — Self-Automation Prompt Chain

This document defines a structured chain of prompts that enables the Murphy System
to automate itself and collaborate with AI agents (including GitHub Copilot, LLM-based
assistants, and its own shadow agents) as a collaborator.

Each prompt in the chain is designed to be used sequentially, forming a complete
**analyze → plan → implement → test → review → document → iterate** loop.

---

## How to Use This Chain

1. Start with **Prompt 1** (System Analysis) to assess current state.
2. Feed the output into **Prompt 2** (Planning) to create a task list.
3. For each task, run **Prompt 3** (Implementation) to execute.
4. Validate with **Prompt 4** (Testing) and loop back to Prompt 3 if tests fail.
5. Run **Prompt 5** (Code Review) to catch issues before merging.
6. Run **Prompt 6** (Documentation) to update all project docs.
7. Run **Prompt 7** (Iteration) to check for the next priority and loop back to Prompt 1.

The chain is **self-referential**: Prompt 7 feeds back into Prompt 1, creating a
continuous improvement loop that enables the system to work on itself indefinitely.

---

## Prompt 1: System Analysis

**Purpose:** Assess the current state of the Murphy System and identify gaps.

```
You are analyzing the Murphy System, a universal generative automation control plane.

1. Read and summarize the current state from these files:
   - Murphy System/Murphy System/FULL_SYSTEM_ASSESSMENT.md (all sections 1-17)
   - Murphy System/Murphy System/RECOMMENDATIONS.md
   - Murphy System/Murphy System/RFI.MD
   - README.md

2. Inventory all modules in Murphy System/Murphy System/src/ and count their tests
   in Murphy System/Murphy System/tests/.

3. Run the full test suite:
   cd "Murphy System/murphy_integrated" && python -m pytest tests/ -x -q

4. Identify:
   a. Any assessment sections with items not marked COMPLETE or IMPLEMENTED
   b. Any RECOMMENDATIONS.md items not yet built
   c. Any modules in src/ without corresponding test files
   d. Any RFI items still OPEN
   e. Any competitive features missing vs. industry leaders (ServiceNow, Zapier,
      Make.com, n8n, Temporal, Prefect, Airflow)

5. Output a prioritized gap list ranked by:
   - Business impact (self-improvement capability > competitive feature > polish)
   - Implementation complexity (low > medium > high)
   - Dependency order (foundation modules first)

Format: JSON array of {id, title, priority, complexity, category, depends_on, description}
```

---

## Prompt 2: Planning

**Purpose:** Create a concrete implementation plan from the gap analysis.

```
You are planning the next implementation cycle for the Murphy System.

Given the gap analysis from the previous step, create an implementation plan:

1. Select the top 3-5 tasks by priority that can be completed in one session.

2. For each task, define:
   a. Module name and file path (src/<module_name>.py)
   b. Test file path (tests/test_<module_name>.py)
   c. Classes and key methods to implement
   d. Integration points with existing modules (which runtime attributes to wire)
   e. MODULE_CATALOG entry (name, path, description, capabilities)
   f. Assessment section(s) to update
   g. Estimated test count

3. Define the wiring plan:
   a. Import statement to add to murphy_system_1.0_runtime.py
   b. Initialization code for _initialize_integrated_modules()
   c. MODULE_CATALOG entry
   d. Any execute_task integration (event publishing, gate checks, etc.)
   e. Integration test additions for test_integrated_execution_wiring.py

4. Verify no circular dependencies with existing modules.

Format: Markdown checklist with implementation details for each task.
```

---

## Prompt 3: Implementation

**Purpose:** Execute one task from the plan, creating the module and tests.

```
You are implementing a new module for the Murphy System.

Task: [TASK_TITLE]
Module: src/[MODULE_NAME].py
Tests: tests/test_[MODULE_NAME].py

Requirements:
1. Follow the existing module pattern:
   - Use only Python stdlib (no external dependencies)
   - Use dataclasses or enums where appropriate
   - Include type hints on all public methods
   - Use threading.Lock for thread safety where needed
   - Include a get_status() -> Dict[str, Any] method
   - Include docstrings on the class and all public methods

2. Create comprehensive tests following existing patterns:
   - One test class per logical group
   - Test happy path, edge cases, and error conditions
   - Use unittest.TestCase
   - Target 25-40 tests per module

3. Wire into the runtime:
   a. Add try/except import block in murphy_system_1.0_runtime.py
   b. Add MODULE_CATALOG entry
   c. Add initialization in _initialize_integrated_modules()
   d. Add to _build_components_status() if applicable
   e. Add to _build_integrated_execution_summary() if applicable

4. Run targeted tests:
   cd "Murphy System/murphy_integrated"
   python -m pytest tests/test_[MODULE_NAME].py -x -v

5. Run integration tests:
   python -m pytest tests/test_integrated_execution_wiring.py -x -q

6. If any test fails, fix the issue and re-run. Do not proceed until all tests pass.
```

---

## Prompt 4: Testing

**Purpose:** Validate changes with focused and integration tests.

```
You are validating changes to the Murphy System.

1. Run the specific module tests:
   cd "Murphy System/murphy_integrated"
   python -m pytest tests/test_[MODULE_NAME].py -x -v
   
   Expected: All tests pass with 0 failures.

2. Run integration tests:
   python -m pytest tests/test_integrated_execution_wiring.py -x -q
   
   Expected: All integration tests pass (including new module initialization test).

3. Run the full new-module test suite to check for regressions:
   python -m pytest tests/test_persistence_manager.py tests/test_event_backbone.py \
     tests/test_delivery_adapters.py tests/test_gate_execution_wiring.py \
     tests/test_self_improvement_engine.py tests/test_operational_slo_tracker.py \
     tests/test_automation_scheduler.py tests/test_capability_map.py \
     tests/test_compliance_engine.py tests/test_rbac_governance.py \
     tests/test_ticketing_adapter.py tests/test_wingman_protocol.py \
     tests/test_runtime_profile_compiler.py tests/test_governance_kernel.py \
     tests/test_control_plane_separation.py tests/test_durable_swarm_orchestrator.py \
     tests/test_golden_path_bridge.py tests/test_org_chart_enforcement.py \
     tests/test_shadow_agent_integration.py tests/test_triage_rollcall_adapter.py \
     tests/test_rubix_evidence_adapter.py tests/test_semantics_boundary_controller.py \
     tests/test_bot_governance_policy_mapper.py tests/test_bot_telemetry_normalizer.py \
     tests/test_legacy_compatibility_matrix.py tests/test_hitl_autonomy_controller.py \
     tests/test_compliance_region_validator.py tests/test_observability_counters.py \
     tests/test_deterministic_routing_engine.py tests/test_platform_connector_framework.py \
     tests/test_workflow_dag_engine.py tests/test_automation_type_registry.py \
     tests/test_api_gateway_adapter.py tests/test_webhook_event_processor.py \
     -x -q
   
   Expected: All tests pass with 0 failures.

4. If any test fails:
   a. Identify the root cause from the traceback
   b. Fix the issue in the source module or test
   c. Re-run from step 1
   d. Repeat until all tests pass

5. Report: total tests passed, total tests failed, any skipped tests.
```

---

## Prompt 5: Code Review

**Purpose:** Review changes for quality, security, and consistency.

```
You are reviewing changes to the Murphy System for quality and security.

1. Check each new/modified file for:
   a. No hardcoded secrets, API keys, or credentials
   b. No external network calls in module code (stdlib only)
   c. Thread safety (Lock usage where shared state exists)
   d. Proper error handling (try/except with specific exceptions)
   e. Type hints on all public methods
   f. Docstrings on classes and public methods
   g. Consistent naming with existing modules (snake_case files, PascalCase classes)

2. Check runtime wiring:
   a. Import uses try/except with fallback to None
   b. MODULE_CATALOG entry has name, path, description, capabilities
   c. _initialize_integrated_modules() checks class availability before instantiation
   d. No circular imports

3. Check tests:
   a. Tests use unittest.TestCase
   b. Each test method has a descriptive name (test_<behavior>)
   c. Tests don't depend on external services
   d. Tests don't modify shared state between test methods

4. Verify .gitignore covers:
   a. __pycache__/ directories
   b. *.pyc files
   c. *.log files
   d. *.db files
   e. *.zip files
   f. .env files

5. Flag any issues found and provide fixes.
```

---

## Prompt 6: Documentation

**Purpose:** Update all project documentation to reflect completed work.

```
You are updating the Murphy System documentation after completing implementation tasks.

1. Update FULL_SYSTEM_ASSESSMENT.md:
   a. Section 1 (Executive summary): Update module count and capability description
   b. Section 2 (What system does well): Add new module bullet points
   c. Section 4.1 (Competitive table): Update status for any newly-covered features
   d. Section 8 (Completion checklist): Mark completed items, update bottom line
   e. Section 9 (Production readiness): Update percentage estimates with evidence
   f. Section 11 (Testing expansion): Add new test module entries
   g. Section 12 (Implementation plan): Mark completed steps
   h. Section 14 (Forward plan): Update priorities
   i. Section 16 (Platform integration): Update if integration modules changed
   j. Update module counts and test counts throughout

2. Update README.md:
   a. Update module count in system description
   b. Add new module entries to the module list
   c. Update subsystem table if applicable
   d. Update completion percentages

3. Update RECOMMENDATIONS.md:
   a. Move implemented recommendations from "Recommended" to "Implemented"
   b. Update module summary table with new test counts
   c. Add any new recommendations discovered during implementation

4. Update RFI.MD:
   a. Close any RFIs resolved by implementation decisions
   b. Add new RFIs for unresolved architecture questions

5. Verify all internal links in README.md and assessment docs are valid.
```

---

## Prompt 7: Iteration

**Purpose:** Check for the next priority and restart the loop.

```
You are checking whether the Murphy System needs another improvement cycle.

1. Re-read FULL_SYSTEM_ASSESSMENT.md sections 3, 8, 9, and 14.

2. Check completion percentages in Section 9:
   - If any area is below 95%, identify what's needed to reach 95%.
   - If all areas are above 95%, check RECOMMENDATIONS.md Section 6.2 for next-phase items.

3. Run the full test suite and count total tests:
   cd "Murphy System/murphy_integrated"
   python -m pytest tests/ -x -q 2>&1 | tail -5

4. Check for any new competitive features needed:
   - Research: What features do ServiceNow, Zapier, Make.com, n8n, Temporal, Prefect,
     and Airflow offer that Murphy doesn't have yet?
   - Check if any new integrations are trending (e.g., new AI platforms, observability
     tools, or compliance frameworks).

5. If there are remaining gaps:
   a. Prioritize them using the same criteria as Prompt 1 step 5
   b. Return to Prompt 1 with the updated gap list
   c. Continue the cycle

6. If the system is complete:
   a. Document the final state in FULL_SYSTEM_ASSESSMENT.md
   b. Tag the release in git
   c. Update README.md with the final module count and feature list

This prompt creates a continuous improvement loop. The system can use this chain
to work on itself indefinitely, with each cycle adding capabilities, fixing issues,
and maintaining documentation.
```

---

## Prompt Chain for AI Collaborator Mode

When Murphy is working alongside an AI assistant (e.g., GitHub Copilot), use these
specialized prompts to establish collaboration context:

### Collaborator Onboarding Prompt

```
You are collaborating with the Murphy System, a universal generative automation
control plane. Before making any changes:

1. Read Murphy System/Murphy System/FULL_SYSTEM_ASSESSMENT.md to understand
   the current system state (all sections 1-17).

2. Read Murphy System/Murphy System/RECOMMENDATIONS.md for planned integrations.

3. Read Murphy System/Murphy System/PROMPT_CHAIN.md (this file) to understand
   the development workflow.

4. Key conventions:
   - All new modules go in: Murphy System/Murphy System/src/
   - All tests go in: Murphy System/Murphy System/tests/
   - Runtime wiring in: Murphy System/Murphy System/murphy_system_1.0_runtime.py
   - Python stdlib only (no external dependencies in modules)
   - Follow unittest.TestCase patterns for tests
   - Update docs after every task (README.md, FULL_SYSTEM_ASSESSMENT.md)

5. Current module count: 34+ integrated modules
   Current test count: 1100+ tests passing
   Runtime: murphy_system_1.0_runtime.py (single runnable runtime)

6. Follow the Prompt 1-7 chain for all work.
```

### Collaborator Handoff Prompt

```
You are handing off work on the Murphy System to the next collaborator session.

Provide a handoff summary:

1. What was completed this session:
   - Modules added/modified
   - Tests added/modified
   - Documentation updated
   - Assessment sections updated

2. What remains to be done:
   - Uncompleted tasks from the plan
   - Known issues discovered
   - New RFIs created

3. Current test status:
   - Total tests passing
   - Any skipped or failing tests
   - Integration test count

4. Next recommended action:
   - Which prompt in the chain to start with
   - Which task to prioritize
   - Any blockers to resolve first

Format this as a structured summary that can be fed directly into Prompt 1
of the next session.
```

### Self-Improvement Task Generation Prompt

```
You are the Murphy System generating improvement tasks for yourself.

Using the self_automation_orchestrator module:

1. Analyze your current capabilities by scanning src/ modules and test coverage.

2. Generate improvement tasks in these categories:
   a. COVERAGE_GAP: Modules with < 25 tests
   b. INTEGRATION_GAP: Modules not wired into execute_task
   c. COMPETITIVE_GAP: Features competitors have that Murphy lacks
   d. QUALITY_GAP: Code quality issues (missing type hints, docstrings, etc.)
   e. DOCUMENTATION_GAP: Outdated or missing documentation

3. For each task, produce:
   - task_id: unique identifier
   - title: short description
   - category: one of the above
   - priority: 1 (highest) to 5 (lowest)
   - prompt: the exact prompt to execute this task (from Prompt 3 template)
   - estimated_tests: expected number of new tests
   - dependencies: list of task_ids that must complete first

4. Queue tasks in priority order using the self_automation_orchestrator.

5. Execute the highest-priority task using Prompt 3, then validate with Prompt 4.

6. After completion, re-run this prompt to discover new tasks.
```

---

## Quick Reference

| Step | Prompt | Purpose | Output |
|------|--------|---------|--------|
| 1 | System Analysis | Assess current state | Gap list (JSON) |
| 2 | Planning | Create task list | Implementation plan (checklist) |
| 3 | Implementation | Build one module | Source + tests + wiring |
| 4 | Testing | Validate changes | Pass/fail report |
| 5 | Code Review | Quality check | Issue list + fixes |
| 6 | Documentation | Update docs | Updated MD files |
| 7 | Iteration | Check next priority | Next task or completion |

**Total cycle time per module:** ~30-60 minutes for an AI collaborator.

**Self-automation frequency:** Run the full chain weekly or after each feature request.
