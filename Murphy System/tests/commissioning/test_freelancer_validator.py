"""
Murphy System — Freelancer Validator Commissioning Tests
Owner: @test-lead
Phase: Freelancer HITL Integration
Completion: 100%

Validates the freelancer-based HITL validation system:
- Data models (tasks, responses, criteria, budgets)
- Budget manager authorization and spend tracking
- Criteria engine scoring and format validation
- Platform clients (post, cancel)
- HITL bridge end-to-end wiring
"""

import sys
from pathlib import Path

import pytest

# ── Path setup ───────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from freelancer_validator.models import (
    BudgetConfig,
    BudgetLedger,
    CriterionItem,
    CriterionScore,
    FreelancerResponse,
    FreelancerTask,
    PlatformType,
    ResponseVerdict,
    TaskStatus,
    ValidationCriteria,
)
from freelancer_validator.budget_manager import BudgetManager
from freelancer_validator.criteria_engine import CriteriaEngine
from freelancer_validator.platform_client import (
    FiverrClient,
    GenericFreelancerClient,
    UpworkClient,
)
from freelancer_validator.hitl_bridge import FreelancerHITLBridge

# ── Helpers ──────────────────────────────────────────────────────────────

def _make_criteria() -> ValidationCriteria:
    """Build a sample criteria set for tests."""
    return CriteriaEngine.build_criteria(
        title="Test Validation",
        description="Unit-test criteria set",
        items=[
            {"name": "Accuracy", "description": "Is the output correct?", "scoring_type": "boolean", "weight": 2.0},
            {"name": "Completeness", "description": "All required fields present?", "scoring_type": "boolean", "weight": 1.0},
            {"name": "Quality", "description": "Rate quality 1-5", "scoring_type": "scale_1_5", "weight": 1.5},
        ],
        pass_threshold=0.7,
    )


def _make_task(criteria: ValidationCriteria, org_id: str = "org_test") -> FreelancerTask:
    """Build a sample FreelancerTask for tests."""
    return FreelancerTask(
        hitl_request_id="req_abc123",
        org_id=org_id,
        platform=PlatformType.GENERIC,
        title="Validate model output",
        instructions="Review the attached output and score each criterion.",
        payload={"output": "Hello world", "context": "greeting generation"},
        criteria=criteria,
        budget_cents=1500,
        deadline_hours=12,
    )


def _make_response(task: FreelancerTask, criteria: ValidationCriteria) -> FreelancerResponse:
    """Build a well-formed FreelancerResponse that scores all criteria."""
    return FreelancerResponse(
        task_id=task.task_id,
        hitl_request_id=task.hitl_request_id,
        validator_id="freelancer_42",
        platform=task.platform,
        verdict=ResponseVerdict.INCONCLUSIVE,  # let engine derive
        criterion_scores=[
            CriterionScore(criterion_id=criteria.items[0].criterion_id, value=True, notes="Correct"),
            CriterionScore(criterion_id=criteria.items[1].criterion_id, value=True, notes="Complete"),
            CriterionScore(criterion_id=criteria.items[2].criterion_id, value=4, notes="Good"),
        ],
        feedback="Looks good overall.",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFreelancerModels:
    """Validates Pydantic data models."""

    def test_criterion_item_defaults(self):
        """@test-lead: CriterionItem should have sensible defaults."""
        c = CriterionItem(name="Test", description="Test criterion")
        assert c.scoring_type == "boolean"
        assert c.required is True
        assert c.weight == 1.0
        assert c.criterion_id.startswith("crit_")

    def test_validation_criteria_pass_threshold(self):
        """@test-lead: ValidationCriteria defaults and threshold."""
        vc = _make_criteria()
        assert vc.pass_threshold == 0.7
        assert len(vc.items) == 3

    def test_budget_config_defaults(self):
        """@test-lead: BudgetConfig has correct defaults."""
        bc = BudgetConfig(org_id="org_1")
        assert bc.monthly_limit_cents == 50_000
        assert bc.per_task_limit_cents == 5_000
        assert bc.currency == "USD"

    def test_budget_ledger_can_spend(self):
        """@test-lead: BudgetLedger correctly checks spending capacity."""
        config = BudgetConfig(org_id="org_1", monthly_limit_cents=10_000, per_task_limit_cents=3_000)
        ledger = BudgetLedger(org_id="org_1")
        assert ledger.can_spend(3_000, config) is True
        assert ledger.can_spend(10_001, config) is False
        assert ledger.can_spend(3_001, config) is False  # exceeds per-task limit

    def test_budget_ledger_record_spend(self):
        """@test-lead: BudgetLedger tracks spend and remaining."""
        config = BudgetConfig(org_id="org_1", monthly_limit_cents=10_000, per_task_limit_cents=5_000)
        ledger = BudgetLedger(org_id="org_1")
        ledger.record_spend("task_1", 2_000)
        assert ledger.total_spent_cents == 2_000
        assert ledger.remaining_cents(config) == 8_000
        assert ledger.task_count == 1
        assert len(ledger.transactions) == 1

    def test_freelancer_task_creation(self):
        """@test-lead: FreelancerTask has correct defaults."""
        criteria = _make_criteria()
        task = _make_task(criteria)
        assert task.status == TaskStatus.DRAFT
        assert task.task_id.startswith("ftask_")
        assert task.platform == PlatformType.GENERIC

    def test_freelancer_response_creation(self):
        """@test-lead: FreelancerResponse is well-formed."""
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = _make_response(task, criteria)
        assert resp.response_id.startswith("fresp_")
        assert len(resp.criterion_scores) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Budget Manager Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetManager:
    """Validates budget authorization and tracking."""

    def test_register_org(self):
        """@test-lead: Registering an org creates config + ledger."""
        bm = BudgetManager()
        bm.register_org(BudgetConfig(org_id="org_1", monthly_limit_cents=20_000))
        assert bm.get_config("org_1") is not None
        balance = bm.get_balance("org_1")
        assert balance["remaining_cents"] == 20_000

    def test_authorize_within_budget(self):
        """@test-lead: Authorization succeeds within limits."""
        bm = BudgetManager()
        bm.register_org(BudgetConfig(org_id="org_1", monthly_limit_cents=10_000, per_task_limit_cents=5_000))
        assert bm.authorize_spend("org_1", 5_000) is True

    def test_authorize_exceeds_per_task(self):
        """@test-lead: Authorization fails when per-task limit exceeded."""
        bm = BudgetManager()
        bm.register_org(BudgetConfig(org_id="org_1", monthly_limit_cents=10_000, per_task_limit_cents=2_000))
        assert bm.authorize_spend("org_1", 2_001) is False

    def test_authorize_exceeds_monthly(self):
        """@test-lead: Authorization fails when monthly limit exceeded."""
        bm = BudgetManager()
        bm.register_org(BudgetConfig(org_id="org_1", monthly_limit_cents=5_000, per_task_limit_cents=3_000))
        bm.record_spend("org_1", "task_1", 3_000)
        assert bm.authorize_spend("org_1", 3_000) is False

    def test_authorize_unknown_org(self):
        """@test-lead: Authorization fails for unregistered org."""
        bm = BudgetManager()
        assert bm.authorize_spend("org_unknown", 100) is False

    def test_record_spend_updates_balance(self):
        """@test-lead: Spend recording adjusts remaining balance."""
        bm = BudgetManager()
        bm.register_org(BudgetConfig(org_id="org_1", monthly_limit_cents=10_000, per_task_limit_cents=5_000))
        bm.record_spend("org_1", "task_1", 3_000)
        balance = bm.get_balance("org_1")
        assert balance["remaining_cents"] == 7_000
        assert balance["task_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Criteria Engine Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCriteriaEngine:
    """Validates criteria building, formatting, and scoring."""

    def test_build_criteria(self):
        """@test-lead: build_criteria produces well-formed ValidationCriteria."""
        vc = _make_criteria()
        assert vc.title == "Test Validation"
        assert len(vc.items) == 3
        assert vc.items[0].weight == 2.0

    def test_format_instructions(self):
        """@test-lead: format_instructions produces readable instructions."""
        vc = _make_criteria()
        text = CriteriaEngine.format_instructions(vc)
        assert "Accuracy" in text
        assert "criterion_scores" in text
        assert "REQUIRED" in text

    def test_score_all_pass(self):
        """@test-lead: All-pass response scores above threshold."""
        engine = CriteriaEngine()
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = _make_response(task, criteria)
        scored = engine.score_response(resp, criteria)
        assert scored.overall_score > criteria.pass_threshold
        assert scored.verdict == ResponseVerdict.PASS

    def test_score_all_fail(self):
        """@test-lead: All-fail response scores below threshold."""
        engine = CriteriaEngine()
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = FreelancerResponse(
            task_id=task.task_id,
            hitl_request_id=task.hitl_request_id,
            validator_id="freelancer_42",
            platform=PlatformType.GENERIC,
            verdict=ResponseVerdict.INCONCLUSIVE,
            criterion_scores=[
                CriterionScore(criterion_id=criteria.items[0].criterion_id, value=False),
                CriterionScore(criterion_id=criteria.items[1].criterion_id, value=False),
                CriterionScore(criterion_id=criteria.items[2].criterion_id, value=1),
            ],
            feedback="Fails.",
        )
        scored = engine.score_response(resp, criteria)
        assert scored.overall_score < criteria.pass_threshold
        assert scored.verdict == ResponseVerdict.FAIL

    def test_score_missing_required(self):
        """@test-lead: Missing required criterion triggers NEEDS_REVISION."""
        engine = CriteriaEngine()
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = FreelancerResponse(
            task_id=task.task_id,
            hitl_request_id=task.hitl_request_id,
            validator_id="freelancer_42",
            platform=PlatformType.GENERIC,
            verdict=ResponseVerdict.INCONCLUSIVE,
            criterion_scores=[
                CriterionScore(criterion_id=criteria.items[0].criterion_id, value=True),
                # items[1] and items[2] missing
            ],
            feedback="Partial.",
        )
        scored = engine.score_response(resp, criteria)
        assert scored.verdict == ResponseVerdict.NEEDS_REVISION

    def test_validate_response_format_ok(self):
        """@test-lead: Well-formed response passes format validation."""
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = _make_response(task, criteria)
        errors = CriteriaEngine.validate_response_format(resp, criteria)
        assert errors == []

    def test_validate_response_format_missing(self):
        """@test-lead: Response missing required criterion produces error."""
        criteria = _make_criteria()
        task = _make_task(criteria)
        resp = FreelancerResponse(
            task_id=task.task_id,
            hitl_request_id=task.hitl_request_id,
            validator_id="freelancer_42",
            platform=PlatformType.GENERIC,
            verdict=ResponseVerdict.PASS,
            criterion_scores=[],
            feedback="Empty.",
        )
        errors = CriteriaEngine.validate_response_format(resp, criteria)
        assert len(errors) == 3  # all three criteria are required


# ═══════════════════════════════════════════════════════════════════════════
# Platform Client Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPlatformClients:
    """Validates platform client adapters (post, cancel, status)."""

    @pytest.mark.asyncio
    async def test_fiverr_post(self):
        """@test-lead: FiverrClient posts and assigns platform ID."""
        client = FiverrClient()
        criteria = _make_criteria()
        task = _make_task(criteria)
        posted = await client.post_task(task)
        assert posted.status == TaskStatus.POSTED
        assert posted.platform_task_id.startswith("fvr_")

    @pytest.mark.asyncio
    async def test_upwork_post(self):
        """@test-lead: UpworkClient posts and assigns platform ID."""
        client = UpworkClient()
        criteria = _make_criteria()
        task = _make_task(criteria)
        posted = await client.post_task(task)
        assert posted.status == TaskStatus.POSTED
        assert posted.platform_task_id.startswith("upw_")

    @pytest.mark.asyncio
    async def test_generic_post(self):
        """@test-lead: GenericFreelancerClient posts locally."""
        client = GenericFreelancerClient()
        criteria = _make_criteria()
        task = _make_task(criteria)
        posted = await client.post_task(task)
        assert posted.status == TaskStatus.POSTED
        assert posted.platform_task_id.startswith("gen_")

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """@test-lead: Cancellation sets status to CANCELLED."""
        client = GenericFreelancerClient()
        criteria = _make_criteria()
        task = _make_task(criteria)
        await client.post_task(task)
        result = await client.cancel_task(task)
        assert result is True
        assert task.status == TaskStatus.CANCELLED


# ═══════════════════════════════════════════════════════════════════════════
# HITL Bridge Tests
# ═══════════════════════════════════════════════════════════════════════════


class _MockHITLMonitor:
    """Minimal HITL monitor mock for bridge tests."""

    def __init__(self):
        self.pending_interventions = {}
        self.completed_interventions = {}
        self.responses = []

    def add_pending(self, request_id: str):
        """Simulate a pending intervention."""
        self.pending_interventions[request_id] = True

    def respond_to_intervention(self, request_id, approved, decision,
                                 responded_by, feedback=None,
                                 corrections=None, modifications=None):
        class _Resp:
            def __init__(self):
                self.response_id = f"resp_{request_id}"
        resp = _Resp()
        self.responses.append({
            "request_id": request_id,
            "approved": approved,
            "decision": decision,
            "responded_by": responded_by,
            "feedback": feedback,
        })
        del self.pending_interventions[request_id]
        self.completed_interventions[request_id] = resp
        return resp


class TestFreelancerHITLBridge:
    """Validates the full dispatch → ingest → HITL wiring cycle."""

    @pytest.mark.asyncio
    async def test_dispatch_posts_task(self):
        """@test-lead: dispatch_validation posts task and records spend."""
        bridge = FreelancerHITLBridge()
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_abc",
            org_id="org_1",
            title="Validate output",
            instructions="Check correctness.",
            payload={"data": "test"},
            criteria=criteria,
            budget_cents=1000,
        )
        assert task.status == TaskStatus.POSTED
        balance = bridge.get_budget_balance("org_1")
        assert balance["remaining_cents"] == 49_000

    @pytest.mark.asyncio
    async def test_dispatch_rejects_over_budget(self):
        """@test-lead: dispatch_validation raises if budget exceeded."""
        bridge = FreelancerHITLBridge()
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=500, per_task_limit_cents=500))
        criteria = _make_criteria()
        with pytest.raises(ValueError, match="Budget exceeded"):
            await bridge.dispatch_validation(
                hitl_request_id="req_xyz",
                org_id="org_1",
                title="Validate",
                instructions="Check.",
                payload={},
                criteria=criteria,
                budget_cents=600,
            )

    @pytest.mark.asyncio
    async def test_ingest_wires_to_hitl(self):
        """@test-lead: ingest_response scores and wires to HITL monitor."""
        monitor = _MockHITLMonitor()
        monitor.add_pending("req_abc")
        bridge = FreelancerHITLBridge(hitl_monitor=monitor)
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_abc",
            org_id="org_1",
            title="Validate output",
            instructions="Check correctness.",
            payload={"data": "test"},
            criteria=criteria,
            budget_cents=1000,
        )
        resp = _make_response(task, criteria)
        result = await bridge.ingest_response(resp)
        assert result["verdict"] == "pass"
        assert result["overall_score"] > 0.7
        assert result["hitl_response_id"] is not None
        assert len(monitor.responses) == 1
        assert monitor.responses[0]["approved"] is True

    @pytest.mark.asyncio
    async def test_ingest_fail_verdict_wires_rejected(self):
        """@test-lead: Fail verdict wires approved=False to HITL."""
        monitor = _MockHITLMonitor()
        monitor.add_pending("req_fail")
        bridge = FreelancerHITLBridge(hitl_monitor=monitor)
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_fail",
            org_id="org_1",
            title="Validate output",
            instructions="Check.",
            payload={"data": "bad"},
            criteria=criteria,
            budget_cents=1000,
        )
        resp = FreelancerResponse(
            task_id=task.task_id,
            hitl_request_id="req_fail",
            validator_id="freelancer_99",
            platform=PlatformType.GENERIC,
            verdict=ResponseVerdict.INCONCLUSIVE,
            criterion_scores=[
                CriterionScore(criterion_id=criteria.items[0].criterion_id, value=False),
                CriterionScore(criterion_id=criteria.items[1].criterion_id, value=False),
                CriterionScore(criterion_id=criteria.items[2].criterion_id, value=1),
            ],
            feedback="Bad output.",
        )
        result = await bridge.ingest_response(resp)
        assert result["verdict"] == "fail"
        assert monitor.responses[0]["approved"] is False

    @pytest.mark.asyncio
    async def test_list_and_get_tasks(self):
        """@test-lead: list_tasks and get_task return dispatched tasks."""
        bridge = FreelancerHITLBridge()
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_list",
            org_id="org_1",
            title="Validate",
            instructions="Check.",
            payload={},
            criteria=criteria,
            budget_cents=500,
        )
        assert bridge.get_task(task.task_id) is not None
        tasks = bridge.list_tasks(org_id="org_1")
        assert len(tasks) >= 1
