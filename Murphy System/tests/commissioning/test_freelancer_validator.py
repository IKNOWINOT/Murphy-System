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
from typing import Optional

import pytest

# ── Path setup ───────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:

from freelancer_validator.models import (
    BudgetConfig,
    BudgetLedger,
    CertificationType,
    Credential,
    CredentialRequirement,
    CredentialStatus,
    CriterionItem,
    CriterionScore,
    FreelancerResponse,
    FreelancerTask,
    PlatformType,
    ResponseVerdict,
    TaskStatus,
    ValidationCriteria,
    ValidatorCredentialProfile,
)
from freelancer_validator.budget_manager import BudgetManager
from freelancer_validator.criteria_engine import CriteriaEngine
from freelancer_validator.credential_verifier import (
    CredentialVerifier,
    BBBSource,
    StateLicenseBoardSource,
    GenericPublicRecordSource,
)
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


# ── Credential helpers ───────────────────────────────────────────────────

def _make_credential(
    ctype: CertificationType = CertificationType.PROFESSIONAL_LICENSE,
    name: str = "CPA",
    authority: str = "AICPA",
    country: str = "US",
) -> Credential:
    return Credential(
        credential_type=ctype,
        name=name,
        issuing_authority=authority,
        country=country,
        license_number="LIC-12345",
    )


def _make_requirement(
    ctype: CertificationType = CertificationType.PROFESSIONAL_LICENSE,
    name: str = "CPA",
    authorities: Optional[list] = None,
    countries: Optional[list] = None,
) -> CredentialRequirement:
    return CredentialRequirement(
        credential_type=ctype,
        name=name,
        description=f"Requires {name}",
        issuing_authorities=authorities or [],
        accepted_countries=countries or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Credential Model Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCredentialModels:
    """Validates credential/certification data models."""

    def test_credential_defaults(self):
        """@test-lead: Credential has correct defaults."""
        c = _make_credential()
        assert c.credential_id.startswith("cred_")
        assert c.credential_type == CertificationType.PROFESSIONAL_LICENSE
        assert c.country == "US"

    def test_credential_requirement_defaults(self):
        """@test-lead: CredentialRequirement has correct defaults."""
        r = _make_requirement()
        assert r.requirement_id.startswith("creq_")
        assert r.must_be_current is True
        assert r.verify_complaints is True

    def test_certification_type_enum(self):
        """@test-lead: CertificationType covers expected categories."""
        assert len(CertificationType) == 7
        assert CertificationType.PROFESSIONAL_LICENSE.value == "professional_license"
        assert CertificationType.INDUSTRY_CERTIFICATION.value == "industry_certification"

    def test_task_with_credentials(self):
        """@test-lead: FreelancerTask accepts required_credentials."""
        criteria = _make_criteria()
        req = _make_requirement()
        task = FreelancerTask(
            hitl_request_id="req_abc",
            org_id="org_test",
            title="Validate with creds",
            instructions="Needs CPA.",
            criteria=criteria,
            required_credentials=[req],
        )
        assert len(task.required_credentials) == 1
        assert task.required_credentials[0].name == "CPA"

    def test_task_without_credentials(self):
        """@test-lead: FreelancerTask works without credentials (backward compat)."""
        criteria = _make_criteria()
        task = _make_task(criteria)
        assert task.required_credentials == []


# ═══════════════════════════════════════════════════════════════════════════
# Credential Verifier Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCredentialVerifier:
    """Validates the credential verification engine."""

    def test_check_requirements_met(self):
        """@test-lead: Matching credentials satisfy requirements."""
        verifier = CredentialVerifier()
        cred = _make_credential()
        req = _make_requirement()
        unmet = verifier.check_requirements([cred], [req])
        assert unmet == []

    def test_check_requirements_unmet(self):
        """@test-lead: Missing credentials are reported."""
        verifier = CredentialVerifier()
        req = _make_requirement(name="AWS Solutions Architect",
                                ctype=CertificationType.INDUSTRY_CERTIFICATION)
        unmet = verifier.check_requirements([], [req])
        assert len(unmet) == 1
        assert "Missing required credential" in unmet[0]

    def test_check_requirements_wrong_type(self):
        """@test-lead: Credential of wrong type does not match."""
        verifier = CredentialVerifier()
        cred = _make_credential(ctype=CertificationType.ACADEMIC_DEGREE, name="MBA")
        req = _make_requirement(ctype=CertificationType.PROFESSIONAL_LICENSE, name="CPA")
        unmet = verifier.check_requirements([cred], [req])
        assert len(unmet) == 1

    def test_check_requirements_country_filter(self):
        """@test-lead: Country filter rejects wrong region."""
        verifier = CredentialVerifier()
        cred = _make_credential(country="GB")
        req = _make_requirement(countries=["US", "CA"])
        unmet = verifier.check_requirements([cred], [req])
        assert len(unmet) == 1

    def test_check_requirements_authority_filter(self):
        """@test-lead: Authority filter rejects wrong issuer."""
        verifier = CredentialVerifier()
        cred = _make_credential(authority="Some Other Board")
        req = _make_requirement(authorities=["AICPA"])
        unmet = verifier.check_requirements([cred], [req])
        assert len(unmet) == 1

    @pytest.mark.asyncio
    async def test_verify_credentials(self):
        """@test-lead: verify_credentials returns a full profile."""
        verifier = CredentialVerifier()
        cred = _make_credential()
        profile = await verifier.verify_credentials([cred])
        assert profile.overall_status == CredentialStatus.VERIFIED
        assert len(profile.verification_results) == 1
        assert profile.verification_results[0].status == CredentialStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_verify_empty_credentials(self):
        """@test-lead: Empty credential list yields UNVERIFIED."""
        verifier = CredentialVerifier()
        profile = await verifier.verify_credentials([])
        assert profile.overall_status == CredentialStatus.UNVERIFIED

    @pytest.mark.asyncio
    async def test_verify_for_task_eligible(self):
        """@test-lead: Validator with matching creds is eligible."""
        verifier = CredentialVerifier()
        cred = _make_credential()
        req = _make_requirement()
        result = await verifier.verify_for_task("val_1", [cred], [req])
        assert result["eligible"] is True
        assert result["unmet"] == []
        assert result["profile"] is not None
        assert result["profile"].validator_id == "val_1"

    @pytest.mark.asyncio
    async def test_verify_for_task_ineligible(self):
        """@test-lead: Validator without required creds is ineligible."""
        verifier = CredentialVerifier()
        req = _make_requirement()
        result = await verifier.verify_for_task("val_2", [], [req])
        assert result["eligible"] is False
        assert len(result["unmet"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Credential Integration with HITL Bridge Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCredentialHITLBridge:
    """Validates credential checks integrated with the HITL bridge."""

    @pytest.mark.asyncio
    async def test_dispatch_with_credentials(self):
        """@test-lead: dispatch_validation accepts credential requirements."""
        bridge = FreelancerHITLBridge()
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        req = _make_requirement()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_cred",
            org_id="org_1",
            title="Validate with creds",
            instructions="Check.",
            payload={},
            criteria=criteria,
            budget_cents=1000,
            required_credentials=[req],
        )
        assert task.status == TaskStatus.POSTED
        assert len(task.required_credentials) == 1

    @pytest.mark.asyncio
    async def test_ingest_with_valid_credentials(self):
        """@test-lead: ingest_response accepts when credentials valid."""
        monitor = _MockHITLMonitor()
        monitor.add_pending("req_cred_ok")
        bridge = FreelancerHITLBridge(hitl_monitor=monitor)
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        req = _make_requirement()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_cred_ok",
            org_id="org_1",
            title="Validate",
            instructions="Check.",
            payload={},
            criteria=criteria,
            budget_cents=1000,
            required_credentials=[req],
        )
        resp = _make_response(task, criteria)
        cred = _make_credential()
        result = await bridge.ingest_response(resp, validator_credentials=[cred])
        assert result["verdict"] == "pass"
        assert result["credential_check"] is not None
        assert result["credential_check"]["eligible"] is True

    @pytest.mark.asyncio
    async def test_ingest_rejects_missing_credentials(self):
        """@test-lead: ingest_response rejects when credentials missing."""
        bridge = FreelancerHITLBridge()
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        req = _make_requirement()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_cred_fail",
            org_id="org_1",
            title="Validate",
            instructions="Check.",
            payload={},
            criteria=criteria,
            budget_cents=1000,
            required_credentials=[req],
        )
        resp = _make_response(task, criteria)
        result = await bridge.ingest_response(resp, validator_credentials=[])
        assert result["verdict"] == "credential_rejected"
        assert result["hitl_response_id"] is None
        assert result["credential_check"]["eligible"] is False

    @pytest.mark.asyncio
    async def test_ingest_no_credentials_required(self):
        """@test-lead: Tasks without credential reqs skip verification."""
        monitor = _MockHITLMonitor()
        monitor.add_pending("req_no_cred")
        bridge = FreelancerHITLBridge(hitl_monitor=monitor)
        bridge.register_org_budget(BudgetConfig(org_id="org_1", monthly_limit_cents=50_000))
        criteria = _make_criteria()
        task = await bridge.dispatch_validation(
            hitl_request_id="req_no_cred",
            org_id="org_1",
            title="Validate",
            instructions="Check.",
            payload={},
            criteria=criteria,
            budget_cents=1000,
        )
        resp = _make_response(task, criteria)
        result = await bridge.ingest_response(resp)
        assert result["verdict"] == "pass"
        assert result["credential_check"] is None
