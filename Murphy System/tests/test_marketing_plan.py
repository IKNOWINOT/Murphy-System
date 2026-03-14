# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for MarketingPlanEngine (MKT-007 — Self-Referential Marketing Plan).

Covers:
  - MarketingPlan / CommunityBuildingPlan / ContentCampaignConfig /
    CompetitiveOutreachConfig / ABTestConfig dataclasses
  - MarketingPlanEngine.generate_marketing_plan()
  - MarketingPlanEngine.enrich_compose_kwargs() — A/B variant + competitive hook
  - MarketingPlanEngine.trigger_content_generation() — ContentPipelineEngine wiring
  - MarketingPlanEngine.record_community_action() — action types + bounds
  - MarketingPlanEngine.get_active_plan() / get_plan() / list_plans()
  - MarketingPlanEngine.get_status()
  - Input validation guards (CWE-20, CWE-400)
  - Thread-safety (concurrent plan generation + enrichment)
  - Marketing plan generates valid campaign configurations
"""

from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from self_selling_engine.marketing_plan import (
    ABTestConfig,
    CommunityActionType,
    CommunityBuildingPlan,
    CompetitiveOutreachConfig,
    ContentCampaignConfig,
    ContentTrigger,
    MarketingPlan,
    MarketingPlanEngine,
    PlanStatus,
    _ALLOWED_CHANNELS,
    _ALLOWED_COMMUNITY_ACTIONS,
    _ALLOWED_CONTENT_TYPES,
    _MAX_NAME_LEN,
    _MAX_PLANS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return MarketingPlanEngine()


@pytest.fixture
def full_engine():
    """Engine with all sub-systems mocked out."""
    # ContentPipelineEngine mock
    mock_brief = SimpleNamespace(brief_id="brief-1")
    mock_item = SimpleNamespace(item_id="item-1")
    content_pipeline = MagicMock()
    content_pipeline.create_brief.return_value = mock_brief
    content_pipeline.create_draft.return_value = mock_item

    # CompetitiveIntelligenceEngine mock
    competitive_engine = MagicMock()
    competitive_engine.generate_competitive_strategies.return_value = [
        {
            "competitor_id": "comp-001",
            "competitor_name": "RivalBot",
            "key_message": "Murphy handles the full stack, not just part of it.",
        }
    ]

    # ABTestingEngine mock
    ab_engine = MagicMock()
    ab_engine.create_experiment.return_value = {"experiment_id": "exp-1"}

    # CampaignOrchestrator mock
    campaign_orch = MagicMock()

    # AdaptiveCampaignEngine mock
    adaptive = MagicMock()
    adaptive.get_all_campaigns.return_value = {
        "starter": {"status": "active"},
        "growth": {"status": "active"},
    }

    return MarketingPlanEngine(
        content_pipeline=content_pipeline,
        competitive_engine=competitive_engine,
        ab_testing_engine=ab_engine,
        campaign_orchestrator=campaign_orch,
        adaptive_campaign_engine=adaptive,
    )


@pytest.fixture
def plan(engine):
    return engine.generate_marketing_plan(name="Test Plan")


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestABTestConfig:
    def test_defaults(self):
        ab = ABTestConfig(experiment_id="exp-1", name="Test")
        assert ab.primary_metric == "reply_rate"
        assert ab.variants == []

    def test_to_dict_keys(self):
        ab = ABTestConfig(experiment_id="exp-1", name="Test",
                          variants=[{"variant_id": "A", "name": "Stats"}])
        d = ab.to_dict()
        assert d["experiment_id"] == "exp-1"
        assert d["name"] == "Test"
        assert len(d["variants"]) == 1
        assert "created_at" in d


class TestContentCampaignConfig:
    def test_defaults(self):
        cfg = ContentCampaignConfig(
            config_id="cfg-1",
            trigger=ContentTrigger.TRIAL_COMPLETED.value,
            content_type="blog",
        )
        assert cfg.auto_approve is False
        assert cfg.channels == []

    def test_to_dict(self):
        cfg = ContentCampaignConfig(
            config_id="cfg-1",
            trigger=ContentTrigger.CUSTOMER_WIN.value,
            content_type="social",
            channels=["social"],
            auto_approve=True,
        )
        d = cfg.to_dict()
        assert d["trigger"] == "customer_win"
        assert d["auto_approve"] is True


class TestCompetitiveOutreachConfig:
    def test_defaults(self):
        cfg = CompetitiveOutreachConfig(
            competitor_id="comp-001",
            competitor_name="RivalBot",
            prospect_segment="users_of_comp-001",
            personalization_hook="Switch to Murphy.",
        )
        assert cfg.active is True
        assert cfg.channels == []

    def test_to_dict(self):
        cfg = CompetitiveOutreachConfig(
            competitor_id="comp-001",
            competitor_name="RivalBot",
            prospect_segment="users_of_comp-001",
            personalization_hook="Switch to Murphy.",
            channels=["email"],
        )
        d = cfg.to_dict()
        assert d["competitor_id"] == "comp-001"
        assert "email" in d["channels"]


class TestCommunityBuildingPlan:
    def test_defaults(self):
        plan = CommunityBuildingPlan(plan_id="plan-1")
        assert plan.github_repo == "IKNOWINOT/Murphy-System"
        assert plan.auto_respond_to_discussions is True
        assert plan.dev_advocate_shadow_agent_enabled is True
        assert plan.trial_to_contributor_drip_days == 7

    def test_to_dict(self):
        plan = CommunityBuildingPlan(plan_id="plan-1")
        d = plan.to_dict()
        assert d["github_repo"] == "IKNOWINOT/Murphy-System"
        assert "created_at" in d


class TestMarketingPlan:
    def test_defaults(self):
        plan = MarketingPlan(plan_id="plan-1", name="Test")
        assert plan.status == PlanStatus.DRAFT.value
        assert plan.ab_tests == []
        assert plan.content_configs == []
        assert plan.competitive_configs == []
        assert plan.campaign_ids == []
        assert plan.community_plan is None

    def test_to_dict_includes_community_plan(self):
        cp = CommunityBuildingPlan(plan_id="cp-1")
        plan = MarketingPlan(plan_id="plan-1", name="Test", community_plan=cp)
        d = plan.to_dict()
        assert d["community_plan"] is not None
        assert d["community_plan"]["plan_id"] == "cp-1"

    def test_to_dict_without_community_plan(self):
        plan = MarketingPlan(plan_id="plan-1", name="Test")
        d = plan.to_dict()
        assert d["community_plan"] is None


# ---------------------------------------------------------------------------
# generate_marketing_plan
# ---------------------------------------------------------------------------

class TestGenerateMarketingPlan:
    def test_returns_marketing_plan(self, engine):
        plan = engine.generate_marketing_plan(name="My Plan")
        assert isinstance(plan, MarketingPlan)
        assert plan.name == "My Plan"
        assert plan.status == PlanStatus.ACTIVE.value

    def test_has_default_ab_tests(self, engine):
        plan = engine.generate_marketing_plan(name="My Plan")
        assert len(plan.ab_tests) >= 1
        assert all(isinstance(t, ABTestConfig) for t in plan.ab_tests)

    def test_has_default_content_configs(self, engine):
        plan = engine.generate_marketing_plan(name="My Plan")
        assert len(plan.content_configs) >= 1
        # Every content_type must be in the allowlist
        for cfg in plan.content_configs:
            assert cfg.content_type in _ALLOWED_CONTENT_TYPES

    def test_has_community_plan_by_default(self, engine):
        plan = engine.generate_marketing_plan(name="My Plan")
        assert plan.community_plan is not None
        assert isinstance(plan.community_plan, CommunityBuildingPlan)

    def test_no_community_plan_when_disabled(self, engine):
        plan = engine.generate_marketing_plan(
            name="No Community", include_community_plan=False
        )
        assert plan.community_plan is None

    def test_name_truncated_to_max(self, engine):
        long_name = "x" * (_MAX_NAME_LEN + 50)
        plan = engine.generate_marketing_plan(name=long_name)
        assert len(plan.name) == _MAX_NAME_LEN

    def test_invalid_name_raises(self, engine):
        with pytest.raises(ValueError, match="non-empty"):
            engine.generate_marketing_plan(name="")

    def test_invalid_name_none_raises(self, engine):
        with pytest.raises((ValueError, TypeError)):
            engine.generate_marketing_plan(name=None)  # type: ignore[arg-type]

    def test_plan_stored_and_retrievable(self, engine):
        plan = engine.generate_marketing_plan(name="Retrievable Plan")
        retrieved = engine.get_plan(plan.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == plan.plan_id

    def test_list_plans_contains_new_plan(self, engine):
        engine.generate_marketing_plan(name="Plan Alpha")
        plans = engine.list_plans()
        assert any(p["name"] == "Plan Alpha" for p in plans)

    def test_competitive_configs_with_engine(self, full_engine):
        plan = full_engine.generate_marketing_plan(name="Competitive Plan")
        assert len(plan.competitive_configs) >= 1
        cfg = plan.competitive_configs[0]
        assert cfg.competitor_id == "comp-001"
        assert "RivalBot" in cfg.personalization_hook

    def test_campaign_ids_populated_with_adaptive_engine(self, full_engine):
        plan = full_engine.generate_marketing_plan(name="Tier Plan")
        assert len(plan.campaign_ids) > 0
        assert "starter" in plan.campaign_ids

    def test_ab_engine_called_when_wired(self, full_engine):
        full_engine.generate_marketing_plan(name="AB Plan")
        full_engine._ab_testing_engine.create_experiment.assert_called_once()

    def test_notes_stored(self, engine):
        plan = engine.generate_marketing_plan(name="Noted Plan", notes="test notes")
        assert plan.notes == "test notes"

    def test_generates_valid_campaign_configuration(self, engine):
        """Marketing plan generates valid campaign configurations."""
        plan = engine.generate_marketing_plan(name="Config Validation Plan")
        d = plan.to_dict()
        # All required top-level keys must be present
        for key in ("plan_id", "name", "status", "ab_tests", "content_configs",
                    "competitive_configs", "community_plan", "campaign_ids",
                    "created_at"):
            assert key in d, f"Missing key: {key}"
        # AB tests must have valid structure
        for test in d["ab_tests"]:
            assert "experiment_id" in test
            assert "variants" in test
        # Content configs must have valid triggers
        valid_triggers = {t.value for t in ContentTrigger}
        for cfg in d["content_configs"]:
            assert cfg["trigger"] in valid_triggers
            assert cfg["content_type"] in _ALLOWED_CONTENT_TYPES

    def test_plan_status_is_active(self, engine):
        plan = engine.generate_marketing_plan(name="Active Plan")
        assert plan.status == PlanStatus.ACTIVE.value


# ---------------------------------------------------------------------------
# enrich_compose_kwargs
# ---------------------------------------------------------------------------

class TestEnrichComposeKwargs:
    def test_returns_dict_with_expected_keys(self, plan, engine):
        result = engine.enrich_compose_kwargs(
            prospect_id="prospect-001",
            live_stats={"emails_sent": 42, "company_name": "Acme"},
        )
        assert "subject_override" in result
        assert "body_suffix" in result

    def test_subject_override_not_none_after_plan(self, plan, engine):
        result = engine.enrich_compose_kwargs(
            prospect_id="prospect-abc",
            live_stats={"emails_sent": 10},
        )
        # A/B variant should produce a subject override once a plan exists
        assert result["subject_override"] is not None
        assert isinstance(result["subject_override"], str)
        assert len(result["subject_override"]) > 0

    def test_deterministic_variant_assignment(self, plan, engine):
        """Same prospect_id should always get the same variant."""
        r1 = engine.enrich_compose_kwargs("stable-id", {"emails_sent": 1})
        r2 = engine.enrich_compose_kwargs("stable-id", {"emails_sent": 1})
        assert r1["subject_override"] == r2["subject_override"]

    def test_different_prospects_may_get_different_variants(self, plan, engine):
        """Different prospects should be assigned across variants."""
        subjects = set()
        for i in range(30):
            r = engine.enrich_compose_kwargs(
                f"prospect-{i}", {"emails_sent": i}
            )
            if r["subject_override"]:
                subjects.add(r["subject_override"])
        # With 3 variants and 30 prospects, we expect multiple distinct subjects
        assert len(subjects) >= 2

    def test_competitive_hook_injected_when_config_exists(self, full_engine):
        full_engine.generate_marketing_plan(name="Comp Plan")
        result = full_engine.enrich_compose_kwargs(
            prospect_id="prospect-x",
            live_stats={},
            competitor_id="comp-001",
        )
        assert result["body_suffix"] is not None
        assert "RivalBot" in result["body_suffix"]

    def test_no_competitive_hook_for_unknown_competitor(self, plan, engine):
        result = engine.enrich_compose_kwargs(
            prospect_id="prospect-x",
            live_stats={},
            competitor_id="unknown-comp",
        )
        assert result["body_suffix"] is None

    def test_invalid_prospect_id_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid prospect_id"):
            engine.enrich_compose_kwargs("../../../etc/passwd", {})

    def test_empty_prospect_id_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid prospect_id"):
            engine.enrich_compose_kwargs("", {})


# ---------------------------------------------------------------------------
# trigger_content_generation
# ---------------------------------------------------------------------------

class TestTriggerContentGeneration:
    def test_returns_none_without_pipeline(self, plan, engine):
        result = engine.trigger_content_generation(
            trigger=ContentTrigger.TRIAL_COMPLETED.value,
            context={"company_name": "Acme", "business_type": "SaaS"},
        )
        assert result is None

    def test_returns_item_id_with_pipeline(self, full_engine):
        full_engine.generate_marketing_plan(name="Content Plan")
        result = full_engine.trigger_content_generation(
            trigger=ContentTrigger.TRIAL_COMPLETED.value,
            context={"company_name": "Acme", "business_type": "consulting"},
        )
        assert result == "item-1"
        full_engine._content_pipeline.create_brief.assert_called_once()
        full_engine._content_pipeline.create_draft.assert_called_once()

    def test_invalid_trigger_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown trigger"):
            engine.trigger_content_generation("invalid_trigger", {})

    def test_all_valid_triggers_accepted(self, engine):
        for trigger in ContentTrigger:
            # Should not raise even without a pipeline
            engine.trigger_content_generation(trigger.value, {})

    def test_pipeline_exception_does_not_propagate(self, full_engine):
        full_engine._content_pipeline.create_brief.side_effect = RuntimeError("DB down")
        full_engine.generate_marketing_plan(name="Fail Plan")
        # Should return None gracefully, not raise
        result = full_engine.trigger_content_generation(
            ContentTrigger.TRIAL_COMPLETED.value, {}
        )
        assert result is None

    def test_no_active_plan_returns_none(self, full_engine):
        """No active plan → no config → returns None even with pipeline wired."""
        result = full_engine.trigger_content_generation(
            ContentTrigger.TRIAL_COMPLETED.value, {}
        )
        assert result is None


# ---------------------------------------------------------------------------
# record_community_action
# ---------------------------------------------------------------------------

class TestRecordCommunityAction:
    def test_valid_action_recorded(self, engine):
        record = engine.record_community_action(
            action_type=CommunityActionType.GITHUB_DISCUSSION.value,
            subject_id="issue-42",
            notes="Auto-responded to discussion",
        )
        assert record["action_type"] == "github_discussion"
        assert record["subject_id"] == "issue-42"
        assert "record_id" in record
        assert "recorded_at" in record

    def test_all_valid_action_types_accepted(self, engine):
        for action_type in _ALLOWED_COMMUNITY_ACTIONS:
            record = engine.record_community_action(
                action_type=action_type,
                subject_id="subject-1",
            )
            assert record["action_type"] == action_type

    def test_invalid_action_type_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown community action_type"):
            engine.record_community_action("invalid_type", "subject-1")

    def test_subject_id_truncated(self, engine):
        long_id = "x" * 300
        record = engine.record_community_action(
            action_type=CommunityActionType.DOC_CONTRIBUTION.value,
            subject_id=long_id,
        )
        assert len(record["subject_id"]) <= 200

    def test_notes_truncated(self, engine):
        long_notes = "n" * 1000
        record = engine.record_community_action(
            action_type=CommunityActionType.TRIAL_TO_CONTRIBUTOR.value,
            subject_id="trial-user-1",
            notes=long_notes,
        )
        assert len(record["notes"]) <= 500

    def test_recorded_in_audit_log(self, engine):
        engine.record_community_action(
            action_type=CommunityActionType.DEV_ADVOCATE.value,
            subject_id="contributor-xyz",
        )
        log = engine.get_audit_log()
        assert any(
            e.get("action_type") == "dev_advocate" or
            e.get("action") == "community_action"
            for e in log
        )


# ---------------------------------------------------------------------------
# get_active_plan / get_plan / list_plans
# ---------------------------------------------------------------------------

class TestPlanLookup:
    def test_get_active_plan_none_initially(self, engine):
        assert engine.get_active_plan() is None

    def test_get_active_plan_after_creation(self, engine):
        engine.generate_marketing_plan(name="Active")
        active = engine.get_active_plan()
        assert active is not None
        assert active.status == PlanStatus.ACTIVE.value

    def test_get_plan_by_id(self, engine):
        plan = engine.generate_marketing_plan(name="Find Me")
        retrieved = engine.get_plan(plan.plan_id)
        assert retrieved is plan

    def test_get_plan_unknown_id_returns_none(self, engine):
        assert engine.get_plan("nonexistent-id") is None

    def test_list_plans_empty_initially(self, engine):
        assert engine.list_plans() == []

    def test_list_plans_after_creation(self, engine):
        engine.generate_marketing_plan(name="Plan One")
        engine.generate_marketing_plan(name="Plan Two")
        plans = engine.list_plans()
        assert len(plans) == 2
        names = {p["name"] for p in plans}
        assert names == {"Plan One", "Plan Two"}


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_keys(self, engine):
        status = engine.get_status()
        assert "total_plans" in status
        assert "active_plans" in status
        assert "content_pipeline_wired" in status
        assert "competitive_engine_wired" in status
        assert "ab_testing_wired" in status
        assert "campaign_orchestrator_wired" in status
        assert "adaptive_campaign_wired" in status

    def test_all_wired_false_for_bare_engine(self, engine):
        status = engine.get_status()
        assert status["content_pipeline_wired"] is False
        assert status["competitive_engine_wired"] is False
        assert status["ab_testing_wired"] is False

    def test_all_wired_true_for_full_engine(self, full_engine):
        status = full_engine.get_status()
        assert status["content_pipeline_wired"] is True
        assert status["competitive_engine_wired"] is True
        assert status["ab_testing_wired"] is True
        assert status["campaign_orchestrator_wired"] is True
        assert status["adaptive_campaign_wired"] is True

    def test_plan_count_increments(self, engine):
        engine.generate_marketing_plan(name="P1")
        engine.generate_marketing_plan(name="P2")
        assert engine.get_status()["total_plans"] == 2
        assert engine.get_status()["active_plans"] == 2


# ---------------------------------------------------------------------------
# Thread-safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_plan_generation(self, engine):
        results = []
        errors = []

        def create_plan(i: int):
            try:
                p = engine.generate_marketing_plan(name=f"Thread Plan {i}")
                results.append(p)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=create_plan, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 10
        plan_ids = {p.plan_id for p in results}
        assert len(plan_ids) == 10  # all unique

    def test_concurrent_enrich_compose(self, engine):
        engine.generate_marketing_plan(name="Concurrent Enrich Plan")
        results = []
        errors = []

        def enrich(i: int):
            try:
                r = engine.enrich_compose_kwargs(
                    prospect_id=f"prospect-{i}",
                    live_stats={"emails_sent": i},
                )
                results.append(r)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=enrich, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == 20

    def test_concurrent_community_actions(self, engine):
        errors = []

        def record(i: int):
            try:
                engine.record_community_action(
                    action_type=CommunityActionType.GITHUB_ISSUE.value,
                    subject_id=f"issue-{i}",
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=record, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# __init__.py export check
# ---------------------------------------------------------------------------

class TestPackageExports:
    def test_marketing_plan_importable_from_package(self):
        from self_selling_engine import (  # noqa: F401
            ABTestConfig,
            CommunityActionType,
            CommunityBuildingPlan,
            CompetitiveOutreachConfig,
            ContentCampaignConfig,
            ContentTrigger,
            MarketingPlan,
            MarketingPlanEngine,
            PlanStatus,
        )

    def test_engine_classes_still_exported(self):
        from self_selling_engine import (  # noqa: F401
            MurphySelfSellingEngine,
            SelfSellingOutreach,
            OutreachComplianceGovernor,
        )
