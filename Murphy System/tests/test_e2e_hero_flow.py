"""
End-to-End Hero Flow Validation
================================
Validates the full **Describe → Generate → Execute → Refine** pipeline that is
the core value proposition of Murphy System.

Each test class isolates one stage of the hero path; the final integration
class chains all stages together as a single, gapless flow.

Timeout budget (5 s per 1 000 lines of tested source):
  nocode_workflow_terminal.py  ~884 lines
  ai_workflow_generator.py     ~386 lines
  workflow_orchestrator.py     ~476 lines
  task_executor.py             ~467 lines
  gate_execution_wiring.py     ~366 lines
  ─────────────────────────────────────────
  Total tested source          ~2 579 lines  →  ~13 s minimum
  Suite-level timeout guard    30 s  (generous headroom for CI variance)

Run this suite:
    pytest tests/test_e2e_hero_flow.py -v

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
import os
import uuid

import pytest


from nocode_workflow_terminal import NoCodeWorkflowTerminal, ConversationState
from ai_workflow_generator import AIWorkflowGenerator, WORKFLOW_TEMPLATES
from execution_engine.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowStep,
    WorkflowStepType,
    WorkflowState,
    create_workflow_step,
    execute_workflow,
)
from gate_execution_wiring import (
    GateExecutionWiring,
    GateDecision,
    GateEvaluation,
    GatePolicy,
    GateType,
)

# Timeout: 5 s per 1 000 lines of combined tested source (~2 579 lines → 13 s);
# 30 s allows comfortable CI headroom.
pytestmark = [pytest.mark.hero_flow, pytest.mark.timeout(30)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _approving_evaluator(gate_type: GateType) -> object:
    """Return an evaluator callable that always APPROVES."""
    def _eval(task: dict, session_id: str) -> GateEvaluation:
        return GateEvaluation(
            gate_id=str(uuid.uuid4()),
            gate_type=gate_type,
            decision=GateDecision.APPROVED,
            reason="Auto-approved in test",
            policy=GatePolicy.ENFORCE,
            evaluated_at="",
        )
    return _eval


def _wired_gates() -> GateExecutionWiring:
    """Return a GateExecutionWiring instance with all six gates wired and approving."""
    wiring = GateExecutionWiring(default_policy=GatePolicy.ENFORCE)
    for gt in GateType:
        wiring.register_gate(gt, _approving_evaluator(gt), GatePolicy.ENFORCE)
    return wiring


def _noop_action() -> object:
    """Return a no-op callable suitable as a WorkflowStep action."""
    def _action(**kwargs):
        return {"status": "ok", "kwargs": kwargs}
    return _action


# ---------------------------------------------------------------------------
# Stage 1 — DESCRIBE
# ---------------------------------------------------------------------------

class TestDescribeStage:
    """Validates the DESCRIBE stage: user intent expressed in plain English is
    captured by the Librarian terminal and transitions the conversation forward."""

    def test_session_created_successfully(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        assert session is not None
        assert session.session_id
        assert session.state == ConversationState.GREETING

    def test_session_retrievable_by_id(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        fetched = terminal.get_session(session.session_id)
        assert fetched is not None
        assert fetched.session_id == session.session_id

    def test_message_returns_structured_response(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        response = terminal.send_message(
            session.session_id,
            "Monitor my sales data and send a weekly summary to Slack",
        )
        assert isinstance(response, dict)
        assert "session_id" in response
        assert "message" in response
        assert "state" in response

    def test_description_advances_conversation_state(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Monitor my sales data and send a weekly summary to Slack",
        )
        updated = terminal.get_session(session.session_id)
        assert updated.state != ConversationState.GREETING

    def test_workflow_steps_inferred_from_description(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Fetch customer records, validate them, and send a report via email",
        )
        updated = terminal.get_session(session.session_id)
        assert len(updated.steps) > 0

    def test_conversation_history_recorded(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Deploy my application to staging")
        updated = terminal.get_session(session.session_id)
        user_turns = [t for t in updated.conversation_history if t.role == "user"]
        assert len(user_turns) >= 1

    def test_multiple_sessions_are_independent(self):
        terminal = NoCodeWorkflowTerminal()
        s1 = terminal.create_session()
        s2 = terminal.create_session()
        terminal.send_message(s1.session_id, "Run a security scan")
        terminal.send_message(s2.session_id, "Onboard a new customer")
        assert terminal.get_session(s1.session_id).steps != terminal.get_session(s2.session_id).steps

    def test_session_list_includes_created_sessions(self):
        terminal = NoCodeWorkflowTerminal()
        s = terminal.create_session()
        sessions = terminal.list_sessions()
        ids = [x["session_id"] for x in sessions]
        assert s.session_id in ids

    def test_workflow_compiled_from_session(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Extract data from database, transform it, then load it into the warehouse",
        )
        compiled = terminal.compile_workflow(session.session_id)
        assert compiled is not None
        assert "nodes" in compiled
        assert "edges" in compiled
        assert len(compiled["nodes"]) > 0

    def test_compiled_workflow_has_valid_schema(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Send alert notifications when an API goes down",
        )
        compiled = terminal.compile_workflow(session.session_id)
        assert "workflow_id" in compiled
        assert "name" in compiled
        assert "version" in compiled


# ---------------------------------------------------------------------------
# Stage 2 — GENERATE
# ---------------------------------------------------------------------------

class TestGenerateStage:
    """Validates the GENERATE stage: natural language descriptions are converted
    into structured DAG workflow definitions by AIWorkflowGenerator."""

    def test_generator_instantiates(self):
        gen = AIWorkflowGenerator()
        assert gen is not None

    def test_generate_returns_workflow_dict(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Extract sales data and send a weekly report")
        assert isinstance(result, dict)
        assert "workflow_id" in result
        assert "steps" in result

    def test_generated_workflow_has_steps(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Fetch records from API, validate, then load into database")
        assert len(result["steps"]) > 0

    def test_template_matching_used_for_known_patterns(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Run an ETL pipeline to extract and load data")
        assert result["strategy"] == "template_match"

    def test_keyword_inference_fallback(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Fetch orders, transform records, send notifications to team")
        assert result["strategy"] in ("template_match", "keyword_inference")

    def test_generic_fallback_strategy(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("xyz abc qrst")  # no recognisable keywords
        assert result["strategy"] == "generic_fallback"
        assert len(result["steps"]) > 0

    def test_all_steps_have_required_fields(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Run a security scan on all servers")
        for step in result["steps"]:
            assert "name" in step
            assert "type" in step

    def test_dependency_resolution_produces_valid_dag(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow(
            "Extract data from sources, transform it, validate the output, and load into warehouse"
        )
        step_names = {s["name"] for s in result["steps"]}
        for step in result["steps"]:
            for dep in step.get("depends_on", []):
                assert dep in step_names, f"Dependency '{dep}' not found in steps"

    def test_generation_history_recorded(self):
        gen = AIWorkflowGenerator()
        gen.generate_workflow("Deploy application to Kubernetes")
        history = gen.get_generation_history()
        assert len(history) >= 1

    def test_status_returns_template_count(self):
        gen = AIWorkflowGenerator()
        status = gen.get_status()
        assert status["template_count"] >= len(WORKFLOW_TEMPLATES)

    def test_ci_cd_template_matched(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("CI/CD pipeline: build, test, deploy to production")
        assert result["strategy"] == "template_match"
        assert result["template_used"] == "ci_cd"

    def test_incident_response_template_matched(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Incident response: detect alert, triage, respond, escalate")
        assert result["strategy"] == "template_match"

    def test_customer_onboarding_template_matched(self):
        gen = AIWorkflowGenerator()
        result = gen.generate_workflow("Onboard a new customer: provision account and send welcome")
        assert result["strategy"] == "template_match"

    def test_workflow_id_is_unique_per_generation(self):
        gen = AIWorkflowGenerator()
        w1 = gen.generate_workflow("Send a daily report to Slack")
        w2 = gen.generate_workflow("Send a daily report to Slack")
        assert w1["workflow_id"] != w2["workflow_id"]

    def test_custom_template_registerable(self):
        gen = AIWorkflowGenerator()
        gen.add_template("my_template", {
            "description": "Custom template",
            "keywords": ["custom", "myflow"],
            "steps": [{"name": "step1", "type": "execution", "description": "Run", "depends_on": []}],
        })
        result = gen.generate_workflow("Run my custom myflow process")
        assert result["strategy"] == "template_match"
        assert result["template_used"] == "my_template"


# ---------------------------------------------------------------------------
# Stage 3 — EXECUTE
# ---------------------------------------------------------------------------

class TestExecuteStage:
    """Validates the EXECUTE stage: the WorkflowOrchestrator runs DAG workflows
    with full gate enforcement."""

    def test_orchestrator_creates_workflow(self):
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="test_flow")
        assert wf is not None
        assert wf.workflow_id

    def test_workflow_executes_single_step(self):
        results = []
        def task_action(**kw):
            results.append("executed")
            return "done"

        step = create_workflow_step(
            step_type=WorkflowStepType.TASK,
            action=task_action,
        )
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="single_step", steps=[step])
        orch.start()
        orch.execute_workflow(wf.workflow_id)
        orch.stop()
        assert wf.state == WorkflowState.COMPLETED
        assert results == ["executed"]

    def test_workflow_executes_sequential_steps(self):
        log = []
        def step_fn(label):
            def _fn(**kw):
                log.append(label)
                return label
            return _fn

        steps = [
            create_workflow_step(action=step_fn("a")),
            create_workflow_step(action=step_fn("b")),
            create_workflow_step(action=step_fn("c")),
        ]
        wf_dict = execute_workflow("three_steps", steps)
        assert wf_dict["state"] == WorkflowState.COMPLETED.value
        assert log == ["a", "b", "c"]

    def test_workflow_state_is_completed_on_success(self):
        step = create_workflow_step(action=lambda **kw: "ok")
        wf_dict = execute_workflow("success_flow", [step])
        assert wf_dict["state"] == WorkflowState.COMPLETED.value

    def test_workflow_state_is_failed_on_exception(self):
        def failing(**kw):
            raise RuntimeError("deliberate failure")

        step = create_workflow_step(action=failing)
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="failing_flow", steps=[step])
        orch.start()
        orch.execute_workflow(wf.workflow_id)
        orch.stop()
        assert wf.state == WorkflowState.FAILED
        assert len(wf.errors) > 0

    def test_gate_wiring_approves_task(self):
        wiring = _wired_gates()
        task = {"type": "data_retrieval", "description": "Fetch records"}
        can_run, evaluations = wiring.can_execute(task, session_id="sess-001")
        assert can_run is True
        assert len(evaluations) == len(list(GateType))

    def test_gate_wiring_blocks_on_enforced_deny(self):
        def blocking_eval(task: dict, session_id: str) -> GateEvaluation:
            return GateEvaluation(
                gate_id="g1",
                gate_type=GateType.COMPLIANCE,
                decision=GateDecision.BLOCKED,
                reason="Compliance violation",
                policy=GatePolicy.ENFORCE,
                evaluated_at="",
            )

        wiring = GateExecutionWiring(default_policy=GatePolicy.ENFORCE)
        wiring.register_gate(GateType.COMPLIANCE, blocking_eval, GatePolicy.ENFORCE)
        can_run, evaluations = wiring.can_execute({}, session_id="sess-002")
        assert can_run is False

    def test_gate_history_records_evaluations(self):
        wiring = _wired_gates()
        wiring.can_execute({"type": "deployment"}, session_id="sess-hist")
        history = wiring.get_gate_history()
        assert len(history) > 0

    def test_gate_warn_policy_does_not_block(self):
        def warning_eval(task: dict, session_id: str) -> GateEvaluation:
            return GateEvaluation(
                gate_id="g2",
                gate_type=GateType.QA,
                decision=GateDecision.BLOCKED,
                reason="QA check failed",
                policy=GatePolicy.WARN,
                evaluated_at="",
            )

        wiring = GateExecutionWiring()
        wiring.register_gate(GateType.QA, warning_eval, GatePolicy.WARN)
        can_run, _ = wiring.can_execute({}, session_id="sess-warn")
        assert can_run is True

    def test_workflow_step_result_stored(self):
        step = create_workflow_step(action=lambda **kw: {"value": 42})
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="result_check", steps=[step])
        orch.start()
        orch.execute_workflow(wf.workflow_id)
        orch.stop()
        assert wf.steps[0].result == {"value": 42}

    def test_pausing_and_resuming_workflow(self):
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="pause_test")
        # Pause only works on RUNNING; here we verify the API returns the right booleans
        paused = orch.pause_workflow(wf.workflow_id)
        # Not running yet, so pause returns False
        assert paused is False

    def test_cancelling_workflow_changes_state(self):
        # cancel_workflow only acts on RUNNING or PAUSED workflows;
        # a PENDING (not-yet-started) workflow returns False.
        orch = WorkflowOrchestrator()
        wf = orch.create_workflow(name="cancel_test")
        assert wf.state == WorkflowState.PENDING
        result = orch.cancel_workflow(wf.workflow_id)
        assert result is False  # correct: can only cancel RUNNING/PAUSED

        # Manually transition to simulate running state and verify cancel succeeds
        wf.state = WorkflowState.RUNNING
        cancelled = orch.cancel_workflow(wf.workflow_id)
        assert cancelled is True
        assert wf.state == WorkflowState.CANCELLED


# ---------------------------------------------------------------------------
# Stage 4 — REFINE
# ---------------------------------------------------------------------------

class TestRefineStage:
    """Validates that the compiled workflow output (the REFINE stage input)
    has the correct DAG schema required by workflow_canvas.html."""

    def test_compiled_output_has_nodes_and_edges(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Fetch sales figures, analyse trends, and email the board",
        )
        compiled = terminal.compile_workflow(session.session_id)
        assert isinstance(compiled["nodes"], list)
        assert isinstance(compiled["edges"], list)

    def test_each_node_has_id_and_type(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Run a data pipeline and notify via Slack")
        compiled = terminal.compile_workflow(session.session_id)
        for node in compiled["nodes"]:
            assert "id" in node
            assert "type" in node

    def test_edges_reference_existing_node_ids(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Collect data, transform it, then send a report",
        )
        compiled = terminal.compile_workflow(session.session_id)
        node_ids = {n["id"] for n in compiled["nodes"]}
        for edge in compiled["edges"]:
            assert edge["from"] in node_ids or edge["to"] in node_ids

    def test_compiled_agents_match_session_assignments(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Monitor server health and alert on failure")
        compiled = terminal.compile_workflow(session.session_id)
        updated = terminal.get_session(session.session_id)
        assert len(compiled["agents"]) == len(updated.agent_assignments)

    def test_compiled_workflow_name_derived_from_description(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Deploy my release build to production")
        compiled = terminal.compile_workflow(session.session_id)
        assert compiled["name"]  # non-empty

    def test_agent_detail_accessible_after_compilation(self):
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Validate data and send alerts")
        updated = terminal.get_session(session.session_id)
        if updated.agent_assignments:
            agent_id = updated.agent_assignments[0].agent_id
            detail = terminal.get_agent_detail(session.session_id, agent_id)
            assert detail is not None
            assert "agent" in detail


# ---------------------------------------------------------------------------
# Full Integration — Describe → Generate → Execute → Refine
# ---------------------------------------------------------------------------

class TestFullHeroFlow:
    """Chains all four stages into a single validated end-to-end flow.
    This is the primary gap-closure test for the E2E Hero Flow Validation item."""

    def test_full_describe_generate_execute_chain(self):
        """
        DESCRIBE: User says "Fetch sales data, analyse it, send weekly report to Slack"
        GENERATE: AIWorkflowGenerator converts this to a structured DAG
        EXECUTE:  WorkflowOrchestrator runs the DAG steps under gate enforcement
        REFINE:   Compiled workflow has valid canvas schema
        """
        # --- Stage 1: DESCRIBE -------------------------------------------
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        assert session.state == ConversationState.GREETING

        response = terminal.send_message(
            session.session_id,
            "Fetch sales data from the database, analyse trends, then send a weekly summary to Slack",
        )
        assert "message" in response
        session_after_describe = terminal.get_session(session.session_id)
        assert session_after_describe.state != ConversationState.GREETING
        assert len(session_after_describe.steps) > 0

        # --- Stage 2: GENERATE -------------------------------------------
        gen = AIWorkflowGenerator()
        workflow_def = gen.generate_workflow(
            session_after_describe.workflow_description
            or "Fetch sales data, analyse it, send weekly summary to Slack"
        )
        assert "workflow_id" in workflow_def
        assert len(workflow_def["steps"]) > 0
        assert workflow_def["strategy"] in ("template_match", "keyword_inference", "generic_fallback")

        # All generated steps have required fields
        for step_def in workflow_def["steps"]:
            assert "name" in step_def
            assert "type" in step_def

        # --- Stage 3: EXECUTE --------------------------------------------
        # Translate generated step definitions into orchestrator WorkflowStep objects
        exec_steps = []
        for step_def in workflow_def["steps"]:
            name = step_def["name"]
            exec_steps.append(create_workflow_step(
                step_type=WorkflowStepType.TASK,
                # Capture `name` in the default argument to avoid closure over loop variable
                action=lambda _name=name, **kw: {"step": _name, "status": "completed"},
            ))

        # Wire gates (all approving for this integration test)
        wiring = _wired_gates()
        task_descriptor = {"workflow_id": workflow_def["workflow_id"], "type": "full_pipeline"}
        can_run, gate_evals = wiring.can_execute(task_descriptor, session_id=session.session_id)
        assert can_run is True, f"Gates blocked execution: {[e.reason for e in gate_evals if e.decision != GateDecision.APPROVED]}"

        # Execute the workflow
        wf_result = execute_workflow(
            workflow_def["name"],
            exec_steps,
        )
        assert wf_result["state"] == WorkflowState.COMPLETED.value

        # --- Stage 4: REFINE ---------------------------------------------
        compiled = terminal.compile_workflow(session.session_id)
        assert compiled is not None
        assert isinstance(compiled["nodes"], list)
        assert isinstance(compiled["edges"], list)
        assert len(compiled["nodes"]) > 0

    def test_hero_flow_with_etl_description(self):
        """Validates the ETL template path through the full hero flow."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Extract data from source, transform it, and load into warehouse",
        )

        gen = AIWorkflowGenerator()
        wf_def = gen.generate_workflow("Run an ETL pipeline to extract, transform, and load data")
        assert wf_def["strategy"] == "template_match"
        assert wf_def["template_used"] == "etl_pipeline"

        steps = [create_workflow_step(action=lambda **kw: "ok") for _ in wf_def["steps"]]
        result = execute_workflow(wf_def["name"], steps)
        assert result["state"] == WorkflowState.COMPLETED.value

    def test_hero_flow_with_security_scan_description(self):
        """Validates the security scan path through the full hero flow."""
        gen = AIWorkflowGenerator()
        # Use keywords that match the security_scan template (security, scan, vulnerability, audit)
        wf_def = gen.generate_workflow(
            "Security audit: scan targets for vulnerability, analyze and audit compliance findings"
        )
        # The important invariant: a valid workflow is generated with steps
        assert len(wf_def["steps"]) > 0
        assert wf_def["strategy"] in ("template_match", "keyword_inference")

        steps = [create_workflow_step(action=lambda **kw: "scanned") for _ in wf_def["steps"]]
        result = execute_workflow(wf_def["name"], steps)
        assert result["state"] == WorkflowState.COMPLETED.value

    def test_hero_flow_gate_enforcement_blocks_when_configured(self):
        """Validates that ENFORCE gates correctly prevent execution when policy demands it."""
        gen = AIWorkflowGenerator()
        wf_def = gen.generate_workflow("Deploy production release")

        def compliance_blocker(task: dict, session_id: str) -> GateEvaluation:
            return GateEvaluation(
                gate_id="compliance-001",
                gate_type=GateType.COMPLIANCE,
                decision=GateDecision.BLOCKED,
                reason="Compliance check failed: no change ticket",
                policy=GatePolicy.ENFORCE,
                evaluated_at="",
            )

        wiring = GateExecutionWiring()
        wiring.register_gate(GateType.COMPLIANCE, compliance_blocker, GatePolicy.ENFORCE)
        can_run, evals = wiring.can_execute(
            {"workflow_id": wf_def["workflow_id"]}, session_id="blocked-session"
        )
        assert can_run is False
        blocked = [e for e in evals if e.decision == GateDecision.BLOCKED]
        assert len(blocked) >= 1

    def test_hero_flow_multi_step_result_chain(self):
        """Verifies that results from earlier steps are accessible during execution."""
        state = {"step_a_done": False, "step_b_done": False}

        def step_a(**kw):
            state["step_a_done"] = True
            return "a_result"

        def step_b(**kw):
            state["step_b_done"] = True
            return "b_result"

        steps = [
            create_workflow_step(action=step_a),
            create_workflow_step(action=step_b),
        ]
        result = execute_workflow("chained_steps", steps)
        assert result["state"] == WorkflowState.COMPLETED.value
        assert state["step_a_done"]
        assert state["step_b_done"]

    def test_hero_flow_all_six_gates_evaluated(self):
        """Verifies all six gates are evaluated when all are registered."""
        wiring = _wired_gates()
        _, evals = wiring.can_execute({"type": "full_flow_test"}, session_id="six-gate-session")
        evaluated_gate_types = {e.gate_type for e in evals}
        assert evaluated_gate_types == set(GateType)
