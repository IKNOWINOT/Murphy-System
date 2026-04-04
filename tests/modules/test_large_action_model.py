"""
Tests for the Large Action Model (LAM) Framework.

Covers:
- ActionPrimitive creation and validation
- ActionSequence composition (sequential, parallel, conditional)
- ShadowActionPlanner goal decomposition and personalization
- OrgChartOrchestrator queuing, prioritization, conflict resolution
- ActionAgreementProtocol negotiation flow (all agreement types)
- WorkflowLicenseManager packaging, licensing, import/export
- WorkflowMatchmaker compatibility scoring and recommendations
- Full LargeActionModel cycle: goal → actions → agreement → execution
- Multi-shadow coordination (multiple users' plans interleaving)
- Cross-org workflow licensing round-trip
- Governance integration (authority checks, budget enforcement)
- Safety invariants (no unauthorized execution, audit trail)
- Edge cases (empty org, single user, conflicting plans, budget exhaustion)

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import pytest

from large_action_model import (
    ActionPrimitive,
    ActionSequence,
    AgreementResult,
    AgreementType,
    ExecutionResult,
    ExecutionStatus,
    LAMError,
    LargeActionModel,
    LicenseRecord,
    LicenseType,
    OrgChartOrchestrator,
    ActionAgreementProtocol,
    ShadowActionPlanner,
    WorkflowLicenseManager,
    WorkflowMatchmaker,
    WorkflowMatch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_primitive(
    action_type: str = "analyze",
    domain: str = "operations",
    cost: float = 10.0,
    reversible: bool = True,
    authority: str = "individual",
) -> ActionPrimitive:
    return ActionPrimitive(
        action_id=f"act-{action_type[:4]}",
        action_type=action_type,
        domain=domain,
        parameters={"key": "value"},
        requires_authority=authority,
        cost_estimate=cost,
        reversible=reversible,
        rollback_action="reject" if action_type == "approve" else None,
    )


def _make_sequence(
    primitives=None,
    owner_type: str = "shadow",
    owner_id: str = "shadow-001",
    license_type: str = LicenseType.PRIVATE,
    confidence: float = 0.8,
    seq_id: str = "seq-001",
) -> ActionSequence:
    if primitives is None:
        primitives = [_make_primitive()]
    dag = {}
    for i, p in enumerate(primitives):
        dag[p.action_id] = [] if i == 0 else [primitives[i - 1].action_id]
    return ActionSequence(
        sequence_id=seq_id,
        name="test-sequence",
        description="A test sequence",
        primitives=primitives,
        dag=dag,
        owner_type=owner_type,
        owner_id=owner_id,
        license_type=license_type,
        version="1.0",
        confidence_score=confidence,
    )


@pytest.fixture
def shadow_planner() -> ShadowActionPlanner:
    return ShadowActionPlanner(shadow_agent_id="shadow-001")


@pytest.fixture
def orchestrator() -> OrgChartOrchestrator:
    return OrgChartOrchestrator(org_id="org-001")


@pytest.fixture
def protocol(orchestrator) -> ActionAgreementProtocol:
    return ActionAgreementProtocol(orchestrator)


@pytest.fixture
def license_manager() -> WorkflowLicenseManager:
    return WorkflowLicenseManager()


@pytest.fixture
def matchmaker(license_manager) -> WorkflowMatchmaker:
    return WorkflowMatchmaker(license_manager)


@pytest.fixture
def lam() -> LargeActionModel:
    return LargeActionModel(org_id="org-001")


# ===========================================================================
# ActionPrimitive
# ===========================================================================


class TestActionPrimitive:
    def test_create_primitive(self):
        p = _make_primitive()
        assert p.action_id == "act-anal"
        assert p.action_type == "analyze"
        assert p.domain == "operations"
        assert p.reversible is True
        assert p.rollback_action is None

    def test_approve_primitive_has_rollback(self):
        p = _make_primitive(action_type="approve")
        assert p.rollback_action == "reject"

    def test_non_reversible_primitive(self):
        p = _make_primitive(reversible=False)
        assert p.reversible is False

    def test_cost_estimate(self):
        p = _make_primitive(cost=500.0)
        assert p.cost_estimate == 500.0

    def test_authority_level(self):
        p = _make_primitive(authority="department_head")
        assert p.requires_authority == "department_head"


# ===========================================================================
# ActionSequence
# ===========================================================================


class TestActionSequence:
    def test_create_sequence(self):
        seq = _make_sequence()
        assert seq.sequence_id == "seq-001"
        assert seq.owner_type == "shadow"
        assert seq.confidence_score == 0.8
        assert len(seq.primitives) == 1

    def test_sequential_dag(self):
        p1 = _make_primitive(action_type="analyze")
        p2 = ActionPrimitive(
            action_id="act-app",
            action_type="approve",
            domain="finance",
            parameters={},
            requires_authority="manager",
            cost_estimate=0.0,
            reversible=False,
        )
        seq = _make_sequence(primitives=[p1, p2])
        assert seq.dag[p2.action_id] == [p1.action_id]
        assert seq.dag[p1.action_id] == []

    def test_parallel_primitives_in_sequence(self):
        p1 = _make_primitive("analyze")
        p2 = ActionPrimitive(
            action_id="act-sch",
            action_type="schedule",
            domain="hr",
            parameters={},
            requires_authority="individual",
            cost_estimate=5.0,
            reversible=True,
        )
        # Both depend on nothing (parallel)
        dag = {p1.action_id: [], p2.action_id: []}
        seq = ActionSequence(
            sequence_id="seq-parallel",
            name="parallel",
            description="Parallel steps",
            primitives=[p1, p2],
            dag=dag,
            owner_type="shadow",
            owner_id="shadow-001",
            license_type=LicenseType.PRIVATE,
            version="1.0",
            confidence_score=0.7,
        )
        assert seq.dag[p1.action_id] == []
        assert seq.dag[p2.action_id] == []

    def test_license_type_stored(self):
        seq = _make_sequence(license_type=LicenseType.OPEN)
        assert seq.license_type == LicenseType.OPEN

    def test_owner_type_shadow(self):
        seq = _make_sequence(owner_type="shadow")
        assert seq.owner_type == "shadow"

    def test_owner_type_org_chart(self):
        seq = _make_sequence(owner_type="org_chart")
        assert seq.owner_type == "org_chart"


# ===========================================================================
# ShadowActionPlanner
# ===========================================================================


class TestShadowActionPlanner:
    def test_decompose_goal_returns_sequence(self, shadow_planner):
        seq = shadow_planner.decompose_goal("analyze quarterly sales")
        assert isinstance(seq, ActionSequence)
        assert len(seq.primitives) >= 1
        assert seq.owner_type == "shadow"
        assert seq.owner_id == "shadow-001"

    def test_decompose_goal_detects_verb_analyze(self, shadow_planner):
        seq = shadow_planner.decompose_goal("analyze quarterly sales")
        assert seq.primitives[0].action_type == "analyze"

    def test_decompose_goal_detects_verb_approve(self, shadow_planner):
        seq = shadow_planner.decompose_goal("approve expense report")
        assert seq.primitives[0].action_type == "approve"

    def test_decompose_goal_detects_verb_schedule(self, shadow_planner):
        seq = shadow_planner.decompose_goal("schedule team meeting")
        assert seq.primitives[0].action_type == "schedule"

    def test_decompose_goal_detects_verb_assign(self, shadow_planner):
        seq = shadow_planner.decompose_goal("assign task to Alice")
        assert seq.primitives[0].action_type == "assign"

    def test_decompose_goal_default_action(self, shadow_planner):
        seq = shadow_planner.decompose_goal("do something obscure")
        assert seq.primitives[0].action_type == "analyze"

    def test_decompose_goal_domain_param(self, shadow_planner):
        seq = shadow_planner.decompose_goal("analyze data", domain="finance")
        assert seq.primitives[0].domain == "finance"

    def test_optimize_sequence_returns_sequence(self, shadow_planner):
        seq = shadow_planner.decompose_goal("review report")
        optimized = shadow_planner.optimize_sequence(seq)
        assert isinstance(optimized, ActionSequence)

    def test_learn_from_outcome_updates_history(self, shadow_planner):
        seq = shadow_planner.decompose_goal("send notification")
        shadow_planner.learn_from_outcome(seq.sequence_id, {"status": "completed"})
        assert len(shadow_planner._completion_history) == 1

    def test_confidence_improves_with_successes(self, shadow_planner):
        for _ in range(5):
            seq = shadow_planner.decompose_goal("report metrics")
            shadow_planner.learn_from_outcome(seq.sequence_id, {"status": "completed"})
        seq2 = shadow_planner.decompose_goal("report metrics")
        assert seq2.confidence_score > 0.5

    def test_personal_library_add_and_get(self, shadow_planner):
        seq = _make_sequence()
        shadow_planner.add_to_personal_library(seq)
        library = shadow_planner.get_personal_library()
        assert len(library) == 1
        assert library[0].sequence_id == seq.sequence_id

    def test_personal_library_multiple_entries(self, shadow_planner):
        for i in range(3):
            seq = _make_sequence(seq_id=f"seq-{i:03d}")
            shadow_planner.add_to_personal_library(seq)
        assert len(shadow_planner.get_personal_library()) == 3

    def test_dag_structure_is_correct(self, shadow_planner):
        seq = shadow_planner.decompose_goal("approve budget")
        for p in seq.primitives:
            assert p.action_id in seq.dag


# ===========================================================================
# OrgChartOrchestrator
# ===========================================================================


class TestOrgChartOrchestrator:
    def test_enqueue_and_dequeue(self, orchestrator):
        seq = _make_sequence()
        orchestrator.enqueue(seq)
        assert orchestrator.queue_depth() == 1
        dequeued = orchestrator.dequeue_next()
        assert dequeued is not None
        assert dequeued.sequence_id == seq.sequence_id
        assert orchestrator.queue_depth() == 0

    def test_dequeue_empty_returns_none(self, orchestrator):
        assert orchestrator.dequeue_next() is None

    def test_priority_ordering(self, orchestrator):
        seq_low = _make_sequence(seq_id="seq-low")
        seq_high = _make_sequence(seq_id="seq-high")
        orchestrator.enqueue(seq_low, priority=10)
        orchestrator.enqueue(seq_high, priority=1)
        dequeued = orchestrator.dequeue_next()
        assert dequeued is not None
        assert dequeued.sequence_id == "seq-high"

    def test_evaluate_sequence_no_budget_constraint(self, orchestrator):
        seq = _make_sequence()
        approved, reason, conditions = orchestrator.evaluate_sequence(seq)
        assert approved is True
        assert "dual_authorization_required" in conditions

    def test_evaluate_sequence_budget_exceeded(self, orchestrator):
        orchestrator.set_department_budget("org-001", 5.0)
        seq = _make_sequence(primitives=[_make_primitive(cost=100.0)])
        approved, reason, _ = orchestrator.evaluate_sequence(seq)
        assert approved is False
        assert "cost_estimate" in reason

    def test_evaluate_sequence_within_budget(self, orchestrator):
        orchestrator.set_department_budget("org-001", 500.0)
        seq = _make_sequence(primitives=[_make_primitive(cost=10.0)])
        approved, _, _ = orchestrator.evaluate_sequence(seq)
        assert approved is True

    def test_conflict_resolution_higher_confidence_wins(self, orchestrator):
        seq_a = _make_sequence(seq_id="seq-a", confidence=0.9)
        seq_b = _make_sequence(seq_id="seq-b", confidence=0.5)
        preferred, deferred = orchestrator.resolve_conflict(seq_a, seq_b)
        assert preferred.sequence_id == "seq-a"
        assert deferred.sequence_id == "seq-b"

    def test_conflict_resolution_equal_confidence(self, orchestrator):
        seq_a = _make_sequence(seq_id="seq-a", confidence=0.7)
        seq_b = _make_sequence(seq_id="seq-b", confidence=0.7)
        preferred, deferred = orchestrator.resolve_conflict(seq_a, seq_b)
        # seq_a >= seq_b, so seq_a preferred
        assert preferred.sequence_id == "seq-a"

    def test_set_department_budget(self, orchestrator):
        orchestrator.set_department_budget("dept-finance", 1000.0)
        assert orchestrator._resource_budgets["dept-finance"] == 1000.0

    def test_queue_multiple_sequences(self, orchestrator):
        for i in range(5):
            orchestrator.enqueue(_make_sequence(seq_id=f"seq-{i:03d}"))
        assert orchestrator.queue_depth() == 5


# ===========================================================================
# ActionAgreementProtocol
# ===========================================================================


class TestActionAgreementProtocol:
    def test_instant_agreement_no_constraints(self, protocol):
        seq = _make_sequence()
        result = protocol.propose(seq, shadow_agent_id="shadow-001", org_id="org-001")
        assert isinstance(result, AgreementResult)
        assert result.agreement_type == AgreementType.INSTANT
        assert result.approved_sequence is not None

    def test_rejected_when_budget_hard_constraint(self, protocol, orchestrator):
        orchestrator.set_department_budget("org-001", 1.0)
        # High cost that cannot be reduced below budget after 20% discount
        seq = _make_sequence(primitives=[_make_primitive(cost=1000.0)])
        result = protocol.propose(seq, shadow_agent_id="shadow-001", org_id="org-001")
        assert result.agreement_type in (AgreementType.REJECTED, AgreementType.NEGOTIATED)

    def test_negotiated_agreement_cost_reduction(self, protocol, orchestrator):
        # Budget allows 8.0; cost is 9.0; after 20% cut cost = 7.2 → fits
        orchestrator.set_department_budget("org-001", 8.0)
        seq = _make_sequence(primitives=[_make_primitive(cost=9.0)])
        result = protocol.propose(seq, shadow_agent_id="shadow-001", org_id="org-001")
        assert result.agreement_type == AgreementType.NEGOTIATED
        assert result.approved_sequence is not None

    def test_escalated_agreement_authority_violation(self, protocol, orchestrator):
        # Authority violation triggers escalation
        seq = _make_sequence(
            primitives=[_make_primitive(action_type="approve", cost=0.0)],
        )

        class StrictEnforcement:
            def check_action_authority(self, agent_id, action, required_level):
                return False, "insufficient authority"

        orchestrator._org_chart_enforcement = StrictEnforcement()
        result = protocol.propose(seq, shadow_agent_id="shadow-001", org_id="org-001")
        assert result.agreement_type == AgreementType.ESCALATED
        assert result.requires_human is True

    def test_agreement_has_dual_auth_condition(self, protocol):
        seq = _make_sequence()
        result = protocol.propose(seq, "shadow-001", "org-001")
        if result.agreement_type == AgreementType.INSTANT:
            assert "dual_authorization_required" in result.conditions

    def test_agreement_stored_and_retrievable(self, protocol):
        seq = _make_sequence()
        result = protocol.propose(seq, "shadow-001", "org-001")
        retrieved = protocol.get_agreement(result.agreement_id)
        assert retrieved is not None
        assert retrieved.agreement_id == result.agreement_id

    def test_list_agreements_by_org(self, protocol):
        seq = _make_sequence()
        protocol.propose(seq, "shadow-001", "org-001")
        protocol.propose(seq, "shadow-002", "org-002")
        org1_agreements = protocol.list_agreements(org_id="org-001")
        assert len(org1_agreements) >= 1
        assert all(a.org_id == "org-001" for a in org1_agreements)

    def test_rejected_agreement_no_sequence(self, protocol, orchestrator):
        orchestrator.set_department_budget("org-001", 0.01)
        seq = _make_sequence(primitives=[_make_primitive(cost=999.0)])
        result = protocol.propose(seq, "shadow-001", "org-001")
        if result.agreement_type == AgreementType.REJECTED:
            assert result.approved_sequence is None


# ===========================================================================
# WorkflowLicenseManager
# ===========================================================================


class TestWorkflowLicenseManager:
    def test_package_private_workflow(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(
            seq, "org-001", LicenseType.PRIVATE
        )
        assert isinstance(record, LicenseRecord)
        assert record.license_type == LicenseType.PRIVATE
        assert record.sequence_id == seq.sequence_id

    def test_package_open_workflow_appears_in_marketplace(self, license_manager):
        seq = _make_sequence()
        license_manager.package_workflow(seq, "org-001", LicenseType.OPEN)
        marketplace = license_manager.list_marketplace()
        assert len(marketplace) == 1

    def test_package_licensed_workflow_appears_in_marketplace(self, license_manager):
        seq = _make_sequence()
        license_manager.package_workflow(seq, "org-001", LicenseType.LICENSED)
        marketplace = license_manager.list_marketplace()
        assert len(marketplace) == 1

    def test_package_private_does_not_appear_in_marketplace(self, license_manager):
        seq = _make_sequence()
        license_manager.package_workflow(seq, "org-001", LicenseType.PRIVATE)
        marketplace = license_manager.list_marketplace()
        assert len(marketplace) == 0

    def test_get_license_by_id(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.OPEN)
        retrieved = license_manager.get_license(record.license_id)
        assert retrieved is not None
        assert retrieved.license_id == record.license_id

    def test_get_nonexistent_license_returns_none(self, license_manager):
        assert license_manager.get_license("no-such-id") is None

    def test_record_usage_increments_count(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.LICENSED)
        license_manager.record_usage(record.license_id, revenue=50.0)
        updated = license_manager.get_license(record.license_id)
        assert updated is not None
        assert updated.usage_count == 1
        assert updated.revenue_generated == 50.0

    def test_record_usage_unknown_license_returns_false(self, license_manager):
        assert license_manager.record_usage("bad-id") is False

    def test_import_open_workflow_succeeds(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.OPEN)
        imported = license_manager.import_workflow(record.license_id, "org-002")
        assert imported is not None

    def test_import_private_workflow_fails(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.PRIVATE)
        imported = license_manager.import_workflow(record.license_id, "org-002")
        assert imported is None

    def test_import_org_internal_own_org_succeeds(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.ORG_INTERNAL)
        imported = license_manager.import_workflow(record.license_id, "org-001")
        assert imported is not None

    def test_import_org_internal_other_org_fails(self, license_manager):
        seq = _make_sequence()
        record = license_manager.package_workflow(seq, "org-001", LicenseType.ORG_INTERNAL)
        imported = license_manager.import_workflow(record.license_id, "org-002")
        assert imported is None

    def test_package_requires_owner_org_id(self, license_manager):
        seq = _make_sequence()
        with pytest.raises(LAMError, match="owner_org_id"):
            license_manager.package_workflow(seq, "", LicenseType.OPEN)

    def test_list_marketplace_filtered_by_type(self, license_manager):
        seq1 = _make_sequence(seq_id="seq-A")
        seq2 = _make_sequence(seq_id="seq-B")
        license_manager.package_workflow(seq1, "org-001", LicenseType.OPEN)
        license_manager.package_workflow(seq2, "org-001", LicenseType.LICENSED)
        open_list = license_manager.list_marketplace(LicenseType.OPEN)
        assert len(open_list) == 1
        assert open_list[0].sequence_id == seq1.sequence_id


# ===========================================================================
# WorkflowMatchmaker
# ===========================================================================


class TestWorkflowMatchmaker:
    def _populate_marketplace(self, lm: WorkflowLicenseManager, count: int = 3) -> None:
        for i in range(count):
            seq = _make_sequence(seq_id=f"seq-{i:03d}")
            lm.package_workflow(seq, f"org-{i:03d}", LicenseType.OPEN)

    def test_find_matches_returns_list(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager)
        matches = matchmaker.find_matches({"domains": ["finance"]})
        assert isinstance(matches, list)

    def test_find_matches_empty_marketplace(self, matchmaker):
        matches = matchmaker.find_matches({"domains": ["finance"]})
        assert matches == []

    def test_find_matches_top_n_respected(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager, count=5)
        matches = matchmaker.find_matches({}, top_n=2)
        assert len(matches) <= 2

    def test_matches_have_fit_score(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager)
        matches = matchmaker.find_matches({"domains": ["hr"]})
        for m in matches:
            assert 0.0 <= m.fit_score <= 1.0

    def test_matches_sorted_by_score_descending(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager, count=3)
        matches = matchmaker.find_matches({}, top_n=10)
        scores = [m.fit_score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_match_integration_complexity(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager)
        matches = matchmaker.find_matches({})
        for m in matches:
            assert m.integration_complexity in ("low", "medium", "high")

    def test_match_estimated_roi_positive(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager)
        matches = matchmaker.find_matches({"budget_per_workflow": 2000.0})
        for m in matches:
            assert m.estimated_roi >= 0.0

    def test_match_has_rationale(self, matchmaker, license_manager):
        self._populate_marketplace(license_manager)
        matches = matchmaker.find_matches({"gaps": ["reporting", "scheduling"]})
        for m in matches:
            assert len(m.rationale) > 0

    def test_high_usage_improves_fit_score(self, matchmaker, license_manager):
        seq = _make_sequence(seq_id="seq-popular")
        record = license_manager.package_workflow(seq, "org-001", LicenseType.OPEN)
        for _ in range(10):
            license_manager.record_usage(record.license_id)
        matches = matchmaker.find_matches({}, top_n=1)
        assert len(matches) == 1
        assert matches[0].fit_score > 0.5


# ===========================================================================
# LargeActionModel — full cycle
# ===========================================================================


class TestLargeActionModel:
    def test_generate_actions_returns_sequence(self, lam):
        seq = lam.generate_actions("analyze sales data", shadow_agent_id="shadow-001")
        assert isinstance(seq, ActionSequence)
        assert seq.owner_id == "shadow-001"

    def test_generate_actions_emits_audit_event(self, lam):
        lam.generate_actions("schedule team sync", shadow_agent_id="shadow-001")
        log = lam.get_audit_log()
        assert any(e["event"] == "LAM_ACTION_GENERATED" for e in log)

    def test_submit_for_orchestration_returns_agreement(self, lam):
        seq = lam.generate_actions("assign ticket", shadow_agent_id="shadow-001")
        result = lam.submit_for_orchestration(seq, shadow_agent_id="shadow-001")
        assert isinstance(result, AgreementResult)

    def test_submit_emits_proposed_event(self, lam):
        seq = lam.generate_actions("escalate issue", shadow_agent_id="shadow-001")
        lam.submit_for_orchestration(seq, "shadow-001")
        log = lam.get_audit_log()
        assert any(e["event"] == "LAM_AGREEMENT_PROPOSED" for e in log)

    def test_submit_emits_reached_event_on_approval(self, lam):
        seq = lam.generate_actions("generate report", shadow_agent_id="shadow-001")
        result = lam.submit_for_orchestration(seq, "shadow-001")
        if result.agreement_type in (AgreementType.INSTANT, AgreementType.NEGOTIATED):
            log = lam.get_audit_log()
            assert any(e["event"] == "LAM_AGREEMENT_REACHED" for e in log)

    def test_execute_agreed_plan_instant(self, lam):
        seq = lam.generate_actions("analyze data", shadow_agent_id="shadow-001")
        agreement = lam.submit_for_orchestration(seq, "shadow-001")
        if agreement.agreement_type == AgreementType.INSTANT:
            result = lam.execute_agreed_plan(agreement)
            assert result.status == ExecutionStatus.COMPLETED

    def test_execute_rejected_agreement_fails(self, lam):
        from datetime import datetime, timezone
        seq = _make_sequence()
        agreement = AgreementResult(
            agreement_id="agr-rejected",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.REJECTED,
            approved_sequence=None,
            reason="hard constraint violated",
        )
        result = lam.execute_agreed_plan(agreement)
        assert result.status == ExecutionStatus.FAILED
        assert "rejected" in result.error_message.lower()

    def test_execute_escalated_agreement_returns_pending(self, lam):
        seq = _make_sequence()
        agreement = AgreementResult(
            agreement_id="agr-escalated",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.ESCALATED,
            approved_sequence=None,
            reason="authority violation",
            requires_human=True,
        )
        result = lam.execute_agreed_plan(agreement)
        assert result.status == ExecutionStatus.PENDING

    def test_execute_emits_completion_event(self, lam):
        seq = lam.generate_actions("assign ticket", shadow_agent_id="shadow-001")
        agreement = lam.submit_for_orchestration(seq, "shadow-001")
        lam.execute_agreed_plan(agreement)
        log = lam.get_audit_log()
        assert any(e["event"] == "LAM_EXECUTION_COMPLETED" for e in log)

    def test_license_workflow_emits_event(self, lam):
        seq = lam.generate_actions("notify team", shadow_agent_id="shadow-001")
        lam.license_workflow(seq, "org-001", LicenseType.OPEN)
        log = lam.get_audit_log()
        assert any(e["event"] == "LAM_WORKFLOW_LICENSED" for e in log)

    def test_find_matching_workflows_emits_event(self, lam):
        lam.find_matching_workflows({"domains": ["finance"]})
        log = lam.get_audit_log()
        assert any(e["event"] == "LAM_WORKFLOW_MATCHED" for e in log)

    def test_register_shadow_returns_planner(self, lam):
        planner = lam.register_shadow("shadow-999", {"role": "engineer"})
        assert isinstance(planner, ShadowActionPlanner)

    def test_register_shadow_idempotent(self, lam):
        p1 = lam.register_shadow("shadow-x")
        p2 = lam.register_shadow("shadow-x")
        assert p1 is p2

    def test_set_org_budget(self, lam):
        lam.set_org_budget(10000.0)
        assert lam._orchestrator._resource_budgets.get("org-001") == 10000.0

    def test_audit_log_grows_with_operations(self, lam):
        lam.generate_actions("analyze data", shadow_agent_id="shadow-001")
        log_len = len(lam.get_audit_log())
        assert log_len >= 1

    def test_get_orchestrator(self, lam):
        assert isinstance(lam.get_orchestrator(), OrgChartOrchestrator)

    def test_get_agreement_protocol(self, lam):
        assert isinstance(lam.get_agreement_protocol(), ActionAgreementProtocol)

    def test_get_license_manager(self, lam):
        assert isinstance(lam.get_license_manager(), WorkflowLicenseManager)


# ===========================================================================
# Multi-shadow coordination
# ===========================================================================


class TestMultiShadowCoordination:
    def test_multiple_shadows_independent_planners(self, lam):
        p1 = lam.register_shadow("shadow-A")
        p2 = lam.register_shadow("shadow-B")
        assert p1 is not p2

    def test_multiple_shadows_enqueue_independently(self, lam):
        seq_a = lam.generate_actions("analyze Q1", shadow_agent_id="shadow-A")
        seq_b = lam.generate_actions("schedule sync", shadow_agent_id="shadow-B")
        result_a = lam.submit_for_orchestration(seq_a, "shadow-A")
        result_b = lam.submit_for_orchestration(seq_b, "shadow-B")
        assert result_a.agreement_id != result_b.agreement_id

    def test_conflicting_plans_resolved(self, lam):
        orchestrator = lam.get_orchestrator()
        orchestrator.set_department_budget("org-001", 50.0)
        seq_a = _make_sequence(seq_id="conf-A", confidence=0.9,
                               primitives=[_make_primitive(cost=30.0)])
        seq_b = _make_sequence(seq_id="conf-B", confidence=0.5,
                               primitives=[_make_primitive(cost=30.0)])
        preferred, deferred = orchestrator.resolve_conflict(seq_a, seq_b)
        assert preferred.sequence_id == "conf-A"
        assert deferred.sequence_id == "conf-B"

    def test_audit_trail_contains_all_shadow_events(self, lam):
        for i in range(3):
            seq = lam.generate_actions(f"task {i}", shadow_agent_id=f"shadow-{i}")
            lam.submit_for_orchestration(seq, f"shadow-{i}")
        log = lam.get_audit_log()
        generated = [e for e in log if e["event"] == "LAM_ACTION_GENERATED"]
        proposed = [e for e in log if e["event"] == "LAM_AGREEMENT_PROPOSED"]
        assert len(generated) >= 3
        assert len(proposed) >= 3


# ===========================================================================
# Cross-org workflow licensing round-trip
# ===========================================================================


class TestCrossOrgLicensing:
    def test_org_a_licenses_workflow_org_b_imports(self):
        lam_a = LargeActionModel(org_id="org-A")
        lam_b = LargeActionModel(org_id="org-B")

        # Org A creates and licenses a workflow
        seq = lam_a.generate_actions("generate weekly report", shadow_agent_id="shadow-A1")
        record = lam_a.license_workflow(seq, "org-A", LicenseType.LICENSED)

        # Org A's marketplace is in its own license manager
        lm_a = lam_a.get_license_manager()
        retrieved = lm_a.get_license(record.license_id)
        assert retrieved is not None
        assert retrieved.owner_org_id == "org-A"

    def test_cross_org_import_increments_usage(self):
        lm = WorkflowLicenseManager()
        seq = _make_sequence()
        record = lm.package_workflow(seq, "org-A", LicenseType.LICENSED)
        lm.import_workflow(record.license_id, "org-B")
        updated = lm.get_license(record.license_id)
        assert updated is not None
        assert updated.usage_count >= 1

    def test_open_workflow_accessible_to_any_org(self):
        lm = WorkflowLicenseManager()
        seq = _make_sequence()
        record = lm.package_workflow(seq, "org-A", LicenseType.OPEN)
        for org in ("org-B", "org-C", "org-D"):
            imported = lm.import_workflow(record.license_id, org)
            assert imported is not None


# ===========================================================================
# Budget exhaustion edge case
# ===========================================================================


class TestBudgetExhaustion:
    def test_zero_budget_rejects_all_non_zero_cost_sequences(self):
        lam = LargeActionModel(org_id="org-tight")
        lam.set_org_budget(0.0)
        seq = _make_sequence(primitives=[_make_primitive(cost=1.0)])
        result = lam.submit_for_orchestration(seq, "shadow-001")
        assert result.agreement_type in (
            AgreementType.REJECTED, AgreementType.NEGOTIATED
        )

    def test_zero_cost_sequence_approved_even_with_zero_budget(self):
        lam = LargeActionModel(org_id="org-tight")
        lam.set_org_budget(0.0)
        seq = _make_sequence(primitives=[_make_primitive(cost=0.0)])
        result = lam.submit_for_orchestration(seq, "shadow-001")
        assert result.agreement_type == AgreementType.INSTANT


# ===========================================================================
# Safety invariants
# ===========================================================================


class TestSafetyInvariants:
    def test_rejected_agreement_never_executes(self):
        lam = LargeActionModel(org_id="org-001")
        seq = _make_sequence()
        agreement = AgreementResult(
            agreement_id="agr-rej",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.REJECTED,
            approved_sequence=seq,
            reason="rejected",
        )
        result = lam.execute_agreed_plan(agreement)
        assert result.status == ExecutionStatus.FAILED

    def test_escalated_agreement_blocked_without_human(self):
        lam = LargeActionModel(org_id="org-001")
        seq = _make_sequence()
        agreement = AgreementResult(
            agreement_id="agr-esc",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.ESCALATED,
            approved_sequence=seq,
            reason="needs human",
            requires_human=True,
        )
        result = lam.execute_agreed_plan(agreement)
        assert result.status == ExecutionStatus.PENDING

    def test_full_audit_trail_maintained(self):
        lam = LargeActionModel(org_id="org-001")
        seq = lam.generate_actions("analyze performance", shadow_agent_id="shadow-001")
        agreement = lam.submit_for_orchestration(seq, "shadow-001")
        lam.execute_agreed_plan(agreement)
        log = lam.get_audit_log()
        event_names = {e["event"] for e in log}
        assert "LAM_ACTION_GENERATED" in event_names
        assert "LAM_AGREEMENT_PROPOSED" in event_names
        assert "LAM_EXECUTION_COMPLETED" in event_names

    def test_no_execution_without_agreement(self):
        """Execution requires an AgreementResult — direct primitive exec not possible."""
        lam = LargeActionModel(org_id="org-001")
        seq = _make_sequence()
        agreement = AgreementResult(
            agreement_id="agr-none",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.INSTANT,
            approved_sequence=None,
            reason="no sequence",
        )
        result = lam.execute_agreed_plan(agreement)
        assert result.status == ExecutionStatus.FAILED

    def test_private_workflow_not_accessible_by_other_orgs(self):
        lm = WorkflowLicenseManager()
        seq = _make_sequence()
        record = lm.package_workflow(seq, "org-A", LicenseType.PRIVATE)
        imported = lm.import_workflow(record.license_id, "org-B")
        assert imported is None

    def test_governance_authority_violation_escalates(self):
        class StrictEnforcer:
            def check_action_authority(self, agent_id, action, required_level):
                return False, "denied"

        orchestrator = OrgChartOrchestrator(
            org_id="org-001",
            org_chart_enforcement=StrictEnforcer(),
        )
        protocol = ActionAgreementProtocol(orchestrator)
        seq = _make_sequence(primitives=[_make_primitive(action_type="approve")])
        result = protocol.propose(seq, "shadow-001", "org-001")
        assert result.agreement_type in (AgreementType.ESCALATED, AgreementType.REJECTED)


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    def test_empty_org_budget_unlimited_by_default(self):
        """When no budget is set, all sequences should pass budget check."""
        orchestrator = OrgChartOrchestrator(org_id="org-new")
        seq = _make_sequence(primitives=[_make_primitive(cost=1_000_000.0)])
        approved, _, _ = orchestrator.evaluate_sequence(seq)
        assert approved is True

    def test_single_user_full_cycle(self):
        lam = LargeActionModel(org_id="org-solo")
        seq = lam.generate_actions("send weekly report", shadow_agent_id="solo-shadow")
        agreement = lam.submit_for_orchestration(seq, "solo-shadow")
        result = lam.execute_agreed_plan(agreement)
        assert result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.PENDING, ExecutionStatus.FAILED)

    def test_empty_primitives_sequence(self):
        orchestrator = OrgChartOrchestrator(org_id="org-001")
        seq = ActionSequence(
            sequence_id="seq-empty",
            name="empty",
            description="empty",
            primitives=[],
            dag={},
            owner_type="shadow",
            owner_id="shadow-001",
            license_type=LicenseType.PRIVATE,
            version="1.0",
            confidence_score=0.0,
        )
        approved, _, _ = orchestrator.evaluate_sequence(seq)
        assert approved is True  # zero cost, no primitives to violate

    def test_sequence_with_no_dag_entries(self):
        lam = LargeActionModel(org_id="org-001")
        seq = ActionSequence(
            sequence_id="seq-nodag",
            name="no dag",
            description="no dag",
            primitives=[_make_primitive()],
            dag={},
            owner_type="shadow",
            owner_id="shadow-001",
            license_type=LicenseType.PRIVATE,
            version="1.0",
            confidence_score=0.5,
        )
        agreement = AgreementResult(
            agreement_id="agr-nodag",
            sequence_id=seq.sequence_id,
            shadow_agent_id="shadow-001",
            org_id="org-001",
            agreement_type=AgreementType.INSTANT,
            approved_sequence=seq,
            reason="approved",
        )
        # Should not raise even with empty DAG
        result = lam.execute_agreed_plan(agreement)
        assert result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED)

    def test_many_agreements_do_not_crash(self):
        lam = LargeActionModel(org_id="org-perf")
        for i in range(50):
            seq = lam.generate_actions(f"task {i}", shadow_agent_id=f"shadow-{i % 5}")
            lam.submit_for_orchestration(seq, f"shadow-{i % 5}")
        log = lam.get_audit_log()
        assert len(log) >= 50
