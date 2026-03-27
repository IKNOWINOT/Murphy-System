# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Tests for GraduationManager (graduation_manager.py).

Validates:
  - NEVER_GRADUATE tasks cannot be promoted to autonomous
  - Graduation threshold enforcement (>90%)
  - Observation period requirement (30 days)
  - Promotion and demotion
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from copilot_tenant.graduation_manager import GraduationManager
from copilot_tenant.tenant_agent import CopilotTenantMode


class TestGraduationManagerInit:
    def test_instantiation(self) -> None:
        gm = GraduationManager()
        assert gm is not None

    def test_never_graduate_set_populated(self) -> None:
        gm = GraduationManager()
        assert "finance" in gm.NEVER_GRADUATE
        assert "trading" in gm.NEVER_GRADUATE
        assert "social_media_posting" in gm.NEVER_GRADUATE
        assert "release_deployment" in gm.NEVER_GRADUATE
        assert "legal_compliance" in gm.NEVER_GRADUATE

    def test_graduation_threshold(self) -> None:
        gm = GraduationManager()
        assert gm.GRADUATION_THRESHOLD == 0.90

    def test_observation_days(self) -> None:
        gm = GraduationManager()
        assert gm.GRADUATION_OBSERVATION_DAYS == 30


class TestNeverGraduate:
    def test_finance_cannot_reach_autonomous(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("finance", CopilotTenantMode.AUTONOMOUS)
        assert result is False

    def test_trading_cannot_reach_autonomous(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("trading", CopilotTenantMode.AUTONOMOUS)
        assert result is False

    def test_social_media_cannot_reach_autonomous(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("social_media_posting", CopilotTenantMode.AUTONOMOUS)
        assert result is False

    def test_release_deployment_cannot_reach_autonomous(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("release_deployment", CopilotTenantMode.AUTONOMOUS)
        assert result is False

    def test_never_graduate_tasks_can_reach_supervised(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("finance", CopilotTenantMode.SUPERVISED)
        assert result is True

    def test_evaluate_never_graduate_in_observer_returns_supervised(self) -> None:
        gm = GraduationManager()
        result = gm.evaluate_task_graduation("finance")
        assert result == CopilotTenantMode.SUPERVISED


class TestGraduationThreshold:
    def test_task_below_threshold_not_promoted(self) -> None:
        gm = GraduationManager()
        gm.update_task_metrics(
            "content_creation",
            accuracy=0.80,          # below 90% threshold
            observation_days=35,
            rollbacks=0,
        )
        gm.promote_task("content_creation", CopilotTenantMode.SUGGESTION)
        result = gm.evaluate_task_graduation("content_creation")
        # Accuracy is below threshold → should not promote to supervised
        assert result != CopilotTenantMode.SUPERVISED

    def test_task_above_threshold_and_sufficient_days_promoted_to_supervised(self) -> None:
        gm = GraduationManager()
        gm.update_task_metrics(
            "content_creation",
            accuracy=0.95,
            observation_days=35,
            rollbacks=0,
        )
        gm.promote_task("content_creation", CopilotTenantMode.SUGGESTION)
        result = gm.evaluate_task_graduation("content_creation")
        assert result == CopilotTenantMode.SUPERVISED


class TestObservationPeriod:
    def test_insufficient_days_blocks_promotion(self) -> None:
        gm = GraduationManager()
        gm.update_task_metrics(
            "content_creation",
            accuracy=0.95,
            observation_days=10,   # below 30-day requirement
            rollbacks=0,
        )
        gm.promote_task("content_creation", CopilotTenantMode.SUGGESTION)
        result = gm.evaluate_task_graduation("content_creation")
        assert result != CopilotTenantMode.SUPERVISED

    def test_sufficient_days_allows_promotion(self) -> None:
        gm = GraduationManager()
        gm.update_task_metrics(
            "content_creation",
            accuracy=0.95,
            observation_days=30,   # exactly at threshold
            rollbacks=0,
        )
        gm.promote_task("content_creation", CopilotTenantMode.SUGGESTION)
        result = gm.evaluate_task_graduation("content_creation")
        assert result == CopilotTenantMode.SUPERVISED


class TestPromotionDemotion:
    def test_promote_regular_task_to_autonomous(self) -> None:
        gm = GraduationManager()
        result = gm.promote_task("content_creation", CopilotTenantMode.AUTONOMOUS)
        assert result is True

    def test_promote_records_mode(self) -> None:
        gm = GraduationManager()
        gm.promote_task("content_creation", CopilotTenantMode.SUPERVISED)
        report = gm.get_graduation_report()
        assert report["tasks"]["content_creation"]["current_mode"] == CopilotTenantMode.SUPERVISED.value

    def test_graduation_report_contains_metadata(self) -> None:
        gm = GraduationManager()
        report = gm.get_graduation_report()
        assert "graduation_threshold" in report
        assert "observation_days_required" in report
        assert "never_graduate_set" in report

    def test_update_task_metrics_stores_values(self) -> None:
        gm = GraduationManager()
        gm.update_task_metrics("my_task", accuracy=0.88, observation_days=20, rollbacks=1)
        report = gm.get_graduation_report()
        m = report["tasks"]["my_task"]["metrics"]
        assert m["accuracy"] == pytest.approx(0.88)
        assert m["observation_days"] == 20
        assert m["rollbacks"] == 1
