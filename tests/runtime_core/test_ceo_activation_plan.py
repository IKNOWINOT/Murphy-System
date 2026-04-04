"""
Tests for CEO Branch Activation & Org Chart Automation Plan (CEO-001).

Covers:
  - OrgChartPosition / WorkflowStep / OrgWorkflow / DeploymentReadinessReport /
    CEOActivationPlan dataclasses
  - MurphyOrgChartManager: add_position, activate_position, get_position,
    get_org_chart, generate_readiness_report
  - WorkflowOrchestrator: resolve_execution_order (topological sort),
    cycle detection
  - CEOActivationPlanBuilder: build, activate_ceo_branch, get_execution_plan,
    get_readiness_report
  - Org chart self-population with default positions
  - Workflow dependency resolution
  - Deployment readiness assessment
  - Input validation guards (CWE-20, CWE-400)
  - Thread-safety (concurrent access)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import threading
import pytest

from src.ceo_activation_plan import (
    CEOActivationPlan,
    CEOActivationPlanBuilder,
    DeploymentReadinessReport,
    MurphyOrgChartManager,
    OrgChartPosition,
    OrgWorkflow,
    PositionStatus,
    PositionType,
    ReadinessLevel,
    REQUIRED_SUBSYSTEMS,
    WorkflowOrchestrator,
    WorkflowStatus,
    WorkflowStep,
    _build_default_org_chart,
    _build_default_workflows,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org_manager():
    return MurphyOrgChartManager()


@pytest.fixture
def orchestrator():
    return WorkflowOrchestrator()


@pytest.fixture
def builder():
    return CEOActivationPlanBuilder()


@pytest.fixture
def simple_workflow():
    return OrgWorkflow(
        workflow_id="wf-test-001",
        role="TestRole",
        steps=[
            WorkflowStep(step_id="s1", name="Step 1", depends_on=[]),
            WorkflowStep(step_id="s2", name="Step 2", depends_on=["s1"]),
            WorkflowStep(step_id="s3", name="Step 3", depends_on=["s2"]),
        ],
    )


# ---------------------------------------------------------------------------
# OrgChartPosition
# ---------------------------------------------------------------------------

class TestOrgChartPosition:
    def test_default_status_is_vacant(self):
        pos = OrgChartPosition()
        assert pos.status == PositionStatus.VACANT.value

    def test_to_dict_has_all_keys(self):
        pos = OrgChartPosition(
            position_id="pos-test",
            title="Test Position",
            department="engineering",
            holder_name="Murphy",
            subsystems=["test_module"],
        )
        d = pos.to_dict()
        for key in ["position_id", "title", "department", "position_type",
                    "holder_name", "reports_to", "subsystems", "permissions",
                    "status", "agent_id", "created_at"]:
            assert key in d

    def test_position_type_default_shadow_agent(self):
        pos = OrgChartPosition()
        assert pos.position_type == PositionType.SHADOW_AGENT.value


# ---------------------------------------------------------------------------
# WorkflowStep
# ---------------------------------------------------------------------------

class TestWorkflowStep:
    def test_default_status_pending(self):
        step = WorkflowStep()
        assert step.status == WorkflowStatus.PENDING.value

    def test_to_dict_keys(self):
        step = WorkflowStep(
            step_id="s1",
            name="Deploy",
            module="deployment_readiness",
            method="run_full_check",
            depends_on=["s0"],
        )
        d = step.to_dict()
        assert d["step_id"] == "s1"
        assert d["module"] == "deployment_readiness"
        assert d["depends_on"] == ["s0"]


# ---------------------------------------------------------------------------
# OrgWorkflow
# ---------------------------------------------------------------------------

class TestOrgWorkflow:
    def test_to_dict_includes_steps(self, simple_workflow):
        d = simple_workflow.to_dict()
        assert len(d["steps"]) == 3

    def test_default_status_pending(self):
        wf = OrgWorkflow()
        assert wf.status == WorkflowStatus.PENDING.value


# ---------------------------------------------------------------------------
# DeploymentReadinessReport
# ---------------------------------------------------------------------------

class TestDeploymentReadinessReport:
    def test_to_dict_has_all_keys(self):
        report = DeploymentReadinessReport(
            overall_readiness=ReadinessLevel.READY.value,
            total_positions=5,
            filled_positions=3,
        )
        d = report.to_dict()
        for key in ["report_id", "generated_at", "overall_readiness",
                    "total_positions", "filled_positions", "missing_positions",
                    "subsystem_coverage", "missing_subsystems",
                    "workflow_readiness", "gaps", "recommendations"]:
            assert key in d


# ---------------------------------------------------------------------------
# MurphyOrgChartManager
# ---------------------------------------------------------------------------

class TestMurphyOrgChartManager:
    def test_add_position(self, org_manager):
        pos = OrgChartPosition(position_id="pos-001", title="Test")
        org_manager.add_position(pos)
        retrieved = org_manager.get_position("pos-001")
        assert retrieved is not None
        assert retrieved.title == "Test"

    def test_add_invalid_position_id(self, org_manager):
        pos = OrgChartPosition(position_id="bad id!")
        with pytest.raises(ValueError, match="position_id"):
            org_manager.add_position(pos)

    def test_activate_position(self, org_manager):
        pos = OrgChartPosition(position_id="pos-002", title="CEO")
        org_manager.add_position(pos)
        result = org_manager.activate_position("pos-002")
        assert result is True
        updated = org_manager.get_position("pos-002")
        assert updated.status == PositionStatus.ACTIVE.value

    def test_activate_nonexistent_position_returns_false(self, org_manager):
        result = org_manager.activate_position("pos-nonexistent")
        assert result is False

    def test_get_position_returns_none_for_missing(self, org_manager):
        assert org_manager.get_position("missing-pos") is None

    def test_get_org_chart_returns_list(self, org_manager):
        pos = OrgChartPosition(position_id="pos-003", title="CTO")
        org_manager.add_position(pos)
        chart = org_manager.get_org_chart()
        assert isinstance(chart, list)
        assert len(chart) == 1

    def test_generate_readiness_report_empty(self, org_manager):
        report = org_manager.generate_readiness_report()
        assert report.overall_readiness in [r.value for r in ReadinessLevel]
        assert report.total_positions == 0

    def test_generate_readiness_report_with_all_active(self, org_manager):
        # Add all required positions and mark them active
        for i, subsystem in enumerate(REQUIRED_SUBSYSTEMS[:5]):
            pos = OrgChartPosition(
                position_id=f"pos-auto-{i}",
                title=f"Role {i}",
                subsystems=[subsystem],
            )
            org_manager.add_position(pos)
            org_manager.activate_position(f"pos-auto-{i}")

        report = org_manager.generate_readiness_report()
        assert report.filled_positions == 5

    def test_readiness_report_identifies_missing_subsystems(self, org_manager):
        report = org_manager.generate_readiness_report()
        # With no positions, all subsystems are missing
        assert len(report.missing_subsystems) == len(REQUIRED_SUBSYSTEMS)
        assert report.overall_readiness == ReadinessLevel.NOT_READY.value

    def test_readiness_report_identifies_gaps(self, org_manager):
        report = org_manager.generate_readiness_report()
        assert len(report.gaps) > 0
        assert len(report.recommendations) > 0

    def test_add_workflow(self, org_manager, simple_workflow):
        org_manager.add_workflow(simple_workflow)
        wf = org_manager.get_workflow(simple_workflow.workflow_id)
        assert wf is not None
        assert wf.workflow_id == simple_workflow.workflow_id

    def test_get_workflow_not_found(self, org_manager):
        assert org_manager.get_workflow("missing-wf") is None

    def test_get_status(self, org_manager):
        status = org_manager.get_status()
        assert "positions" in status
        assert "workflows" in status
        assert "audit_log_size" in status

    def test_thread_safety_concurrent_add(self, org_manager):
        errors = []

        def add_worker(i: int):
            try:
                pos = OrgChartPosition(
                    position_id=f"pos-thread-{i}",
                    title=f"Thread Position {i}",
                )
                org_manager.add_position(pos)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=add_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


# ---------------------------------------------------------------------------
# WorkflowOrchestrator
# ---------------------------------------------------------------------------

class TestWorkflowOrchestrator:
    def test_resolve_simple_chain(self, orchestrator, simple_workflow):
        ordered = orchestrator.resolve_execution_order(simple_workflow)
        assert len(ordered) == 3
        # s1 must come before s2, s2 before s3
        ids = [s.step_id for s in ordered]
        assert ids.index("s1") < ids.index("s2")
        assert ids.index("s2") < ids.index("s3")

    def test_resolve_parallel_steps(self, orchestrator):
        wf = OrgWorkflow(
            workflow_id="wf-parallel",
            steps=[
                WorkflowStep(step_id="root", depends_on=[]),
                WorkflowStep(step_id="branch-a", depends_on=["root"]),
                WorkflowStep(step_id="branch-b", depends_on=["root"]),
                WorkflowStep(step_id="merge", depends_on=["branch-a", "branch-b"]),
            ],
        )
        ordered = orchestrator.resolve_execution_order(wf)
        ids = [s.step_id for s in ordered]
        assert ids.index("root") < ids.index("branch-a")
        assert ids.index("root") < ids.index("branch-b")
        assert ids.index("branch-a") < ids.index("merge")
        assert ids.index("branch-b") < ids.index("merge")

    def test_detects_cycle(self, orchestrator):
        wf = OrgWorkflow(
            workflow_id="wf-cycle",
            steps=[
                WorkflowStep(step_id="a", depends_on=["b"]),
                WorkflowStep(step_id="b", depends_on=["a"]),
            ],
        )
        with pytest.raises(ValueError, match="circular"):
            orchestrator.resolve_execution_order(wf)

    def test_detects_unknown_dependency(self, orchestrator):
        wf = OrgWorkflow(
            workflow_id="wf-bad-dep",
            steps=[
                WorkflowStep(step_id="a", depends_on=["nonexistent"]),
            ],
        )
        with pytest.raises(ValueError, match="unknown"):
            orchestrator.resolve_execution_order(wf)

    def test_empty_workflow_returns_empty_list(self, orchestrator):
        wf = OrgWorkflow(workflow_id="wf-empty", steps=[])
        ordered = orchestrator.resolve_execution_order(wf)
        assert ordered == []

    def test_single_step_no_deps(self, orchestrator):
        wf = OrgWorkflow(
            workflow_id="wf-single",
            steps=[WorkflowStep(step_id="only", depends_on=[])],
        )
        ordered = orchestrator.resolve_execution_order(wf)
        assert len(ordered) == 1

    def test_get_execution_log_populated(self, orchestrator, simple_workflow):
        orchestrator.resolve_execution_order(simple_workflow)
        log = orchestrator.get_execution_log()
        assert len(log) == 1
        assert log[0]["workflow_id"] == simple_workflow.workflow_id


# ---------------------------------------------------------------------------
# _build_default_org_chart
# ---------------------------------------------------------------------------

class TestDefaultOrgChart:
    def test_has_founder_position(self):
        positions = _build_default_org_chart()
        titles = [p.title for p in positions]
        assert any("Founder" in t for t in titles)

    def test_has_ceo_cto_coo_cmo_cfo(self):
        positions = _build_default_org_chart()
        titles = [p.title for p in positions]
        for expected in ["CEO", "CTO", "COO", "CMO", "CFO"]:
            assert any(expected in t for t in titles), f"Missing {expected}"

    def test_founder_is_human_and_active(self):
        positions = _build_default_org_chart()
        founder = next(p for p in positions if p.position_id == "pos-founder")
        assert founder.position_type == PositionType.HUMAN.value
        assert founder.status == PositionStatus.ACTIVE.value

    def test_agents_start_vacant(self):
        positions = _build_default_org_chart()
        agents = [p for p in positions if p.position_type == PositionType.SHADOW_AGENT.value]
        assert all(p.status == PositionStatus.VACANT.value for p in agents)

    def test_cmo_has_marketing_subsystems(self):
        positions = _build_default_org_chart()
        cmo = next((p for p in positions if "CMO" in p.title), None)
        assert cmo is not None
        assert "outreach_campaign_planner" in cmo.subsystems or \
               "campaign_orchestrator" in cmo.subsystems

    def test_positions_have_unique_ids(self):
        positions = _build_default_org_chart()
        ids = [p.position_id for p in positions]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# _build_default_workflows
# ---------------------------------------------------------------------------

class TestDefaultWorkflows:
    def test_has_ceo_workflow(self):
        positions = _build_default_org_chart()
        workflows = _build_default_workflows(positions)
        roles = [wf.role for wf in workflows]
        assert "CEO" in roles

    def test_has_cmo_cto_coo_cfo_workflows(self):
        positions = _build_default_org_chart()
        workflows = _build_default_workflows(positions)
        roles = [wf.role for wf in workflows]
        for expected in ["CMO", "CTO", "COO", "CFO"]:
            assert expected in roles, f"Missing workflow for {expected}"

    def test_ceo_workflow_has_dependency_chain(self):
        positions = _build_default_org_chart()
        workflows = _build_default_workflows(positions)
        ceo_wf = next(wf for wf in workflows if wf.role == "CEO")
        # Bootstrap must depend on verify-deps
        bootstrap = next((s for s in ceo_wf.steps if "bootstrap" in s.step_id), None)
        assert bootstrap is not None
        assert any("verify" in dep for dep in bootstrap.depends_on)

    def test_workflows_are_topologically_resolvable(self):
        positions = _build_default_org_chart()
        workflows = _build_default_workflows(positions)
        orch = WorkflowOrchestrator()
        for wf in workflows:
            ordered = orch.resolve_execution_order(wf)
            assert len(ordered) == len(wf.steps)


# ---------------------------------------------------------------------------
# CEOActivationPlanBuilder
# ---------------------------------------------------------------------------

class TestCEOActivationPlanBuilder:
    def test_build_returns_plan(self, builder):
        plan = builder.build()
        assert isinstance(plan, CEOActivationPlan)
        assert plan.plan_id

    def test_build_populates_org_chart(self, builder):
        plan = builder.build()
        assert len(plan.org_chart) > 0

    def test_build_populates_workflows(self, builder):
        plan = builder.build()
        assert len(plan.workflows) > 0

    def test_build_generates_readiness_report(self, builder):
        plan = builder.build()
        assert plan.readiness_report is not None
        assert isinstance(plan.readiness_report, DeploymentReadinessReport)

    def test_activate_ceo_branch(self, builder):
        builder.build()
        result = builder.activate_ceo_branch()
        assert result["activated"] is True

    def test_activate_ceo_sets_plan_running(self, builder):
        plan = builder.build()
        builder.activate_ceo_branch()
        assert plan.status == WorkflowStatus.RUNNING.value
        assert plan.activated_at is not None

    def test_get_execution_plan_ceo(self, builder):
        builder.build()
        steps = builder.get_execution_plan("CEO")
        assert steps is not None
        assert len(steps) > 0

    def test_get_execution_plan_cmo(self, builder):
        builder.build()
        steps = builder.get_execution_plan("CMO")
        assert steps is not None
        assert len(steps) > 0

    def test_get_execution_plan_unknown_role(self, builder):
        builder.build()
        result = builder.get_execution_plan("UNKNOWN_ROLE")
        assert result is None

    def test_execution_plan_is_dependency_ordered(self, builder):
        builder.build()
        steps = builder.get_execution_plan("CEO")
        assert steps is not None
        # Verify the first step has no dependencies
        assert steps[0]["depends_on"] == []

    def test_get_readiness_report(self, builder):
        builder.build()
        report = builder.get_readiness_report()
        assert isinstance(report, DeploymentReadinessReport)

    def test_readiness_identifies_subsystems(self, builder):
        builder.build()
        report = builder.get_readiness_report()
        assert "self_selling_engine" in report.subsystem_coverage

    def test_readiness_identifies_workflows(self, builder):
        builder.build()
        report = builder.get_readiness_report()
        assert "CEO" in report.workflow_readiness
        assert report.workflow_readiness["CEO"] == "ready"

    def test_get_status_before_build(self, builder):
        status = builder.get_status()
        assert status["plan_status"] == "not_built"

    def test_get_status_after_build(self, builder):
        builder.build()
        status = builder.get_status()
        assert status["plan_status"] != "not_built"

    def test_plan_to_dict(self, builder):
        plan = builder.build()
        d = plan.to_dict()
        for key in ["plan_id", "name", "description", "org_chart",
                    "workflow_count", "readiness_report", "status"]:
            assert key in d

    def test_thread_safety_concurrent_build_and_activate(self):
        results = []
        errors = []

        def build_and_activate():
            try:
                b = CEOActivationPlanBuilder()
                plan = b.build()
                b.activate_ceo_branch()
                results.append(plan.plan_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=build_and_activate) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(results) == 5


# ---------------------------------------------------------------------------
# REQUIRED_SUBSYSTEMS
# ---------------------------------------------------------------------------

class TestRequiredSubsystems:
    def test_required_subsystems_non_empty(self):
        assert len(REQUIRED_SUBSYSTEMS) > 0

    def test_required_subsystems_has_critical_modules(self):
        for module in [
            "self_selling_engine",
            "compliance_engine",
            "agentic_onboarding_engine",
            "production_assistant",
            "billing_api",
        ]:
            assert module in REQUIRED_SUBSYSTEMS, f"Missing: {module}"
