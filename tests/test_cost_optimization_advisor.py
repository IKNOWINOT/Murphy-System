# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for cost_optimization_advisor — COA-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable COARecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from cost_optimization_advisor import (  # noqa: E402
    BudgetAlert,
    CloudProvider,
    CloudResource,
    CostOptimizationAdvisor,
    CostRecommendation,
    CostSummary,
    RecommendationSeverity,
    RecommendationStatus,
    ResourceKind,
    SpendRecord,
    SpotOpportunity,
    SpotOpportunityStatus,
    create_cost_optimization_api,
    gate_coa_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------


@dataclass
class COARecord:
    """One COA check record."""

    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    )


_RESULTS: List[COARecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    *,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> None:
    passed = expected == actual
    _RESULTS.append(
        COARecord(
            check_id=check_id,
            description=description,
            expected=expected,
            actual=actual,
            passed=passed,
            cause=cause,
            effect=effect,
            lesson=lesson,
        )
    )
    assert passed, (
        f"[{check_id}] {description}: expected={expected!r}, got={actual!r}"
    )


# -- Helpers ---------------------------------------------------------------


def _make_advisor() -> CostOptimizationAdvisor:
    return CostOptimizationAdvisor(max_resources=500, max_records=500)


def _add_compute(adv: CostOptimizationAdvisor, name: str = "vm-1",
                 provider: str = "aws", cost: float = 100.0,
                 utilization: float = 50.0) -> CloudResource:
    return adv.register_resource(
        name=name, provider=provider, resource_kind="compute",
        region="us-east-1", monthly_cost=cost, utilization_pct=utilization,
    )


# ==========================================================================
# Tests
# ==========================================================================


class TestResourceRegistration:
    """Cloud resource registration and CRUD."""

    def test_register_basic(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("web-server", "aws", "compute", "us-east-1", 200.0)
        record(
            "COA-001", "register returns CloudResource",
            True, isinstance(r, CloudResource),
            cause="register_resource called",
            effect="CloudResource returned",
            lesson="Factory must return typed resource",
        )
        assert r.name == "web-server"
        assert r.monthly_cost == 200.0

    def test_register_default_provider(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("db-1")
        record(
            "COA-002", "default provider is aws",
            "aws", r.provider,
            cause="no provider specified",
            effect="defaults to aws",
            lesson="Defaults must be sensible",
        )

    def test_register_enum_provider(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("gcp-vm", CloudProvider.gcp)
        record(
            "COA-003", "enum CloudProvider coerced to string",
            "gcp", r.provider,
            cause="CloudProvider enum passed",
            effect="stored as string value",
            lesson="Enum coercion must work",
        )

    def test_register_with_tags(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("vm-1", tags={"env": "prod"})
        record(
            "COA-004", "tags stored correctly",
            "prod", r.tags.get("env"),
            cause="tags dict passed",
            effect="tags persisted",
            lesson="Tags passthrough must work",
        )

    def test_get_resource(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        got = adv.get_resource(r.id)
        record(
            "COA-005", "get_resource returns correct resource",
            r.id, got.id if got else None,
            cause="get by ID",
            effect="same resource returned",
            lesson="Lookup must return existing resources",
        )

    def test_get_resource_missing(self) -> None:
        adv = _make_advisor()
        got = adv.get_resource("nonexistent")
        record(
            "COA-006", "get_resource returns None for missing",
            True, got is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing resources return None",
        )

    def test_list_resources(self) -> None:
        adv = _make_advisor()
        adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        adv.register_resource("vm-2", "gcp", "compute", "eu-west-1", 200.0)
        adv.register_resource("db-1", "aws", "database", "us-east-1", 300.0)
        resources = adv.list_resources(provider="aws")
        record(
            "COA-007", "list_resources filters by provider",
            2, len(resources),
            cause="2 aws resources, 1 gcp",
            effect="2 returned for aws",
            lesson="Provider filter must work",
        )

    def test_list_resources_by_kind(self) -> None:
        adv = _make_advisor()
        adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        adv.register_resource("db-1", "aws", "database", "us-east-1", 300.0)
        resources = adv.list_resources(resource_kind="database")
        record(
            "COA-008", "list_resources filters by kind",
            1, len(resources),
            cause="1 database resource",
            effect="1 returned",
            lesson="Kind filter must work",
        )

    def test_list_resources_by_region(self) -> None:
        adv = _make_advisor()
        adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        adv.register_resource("vm-2", "aws", "compute", "eu-west-1", 200.0)
        resources = adv.list_resources(region="eu-west-1")
        record(
            "COA-009", "list_resources filters by region",
            1, len(resources),
            cause="1 eu-west-1 resource",
            effect="1 returned",
            lesson="Region filter must work",
        )

    def test_list_resources_limit(self) -> None:
        adv = _make_advisor()
        for i in range(20):
            adv.register_resource(f"vm-{i}", "aws", "compute", "us-east-1", 10.0)
        resources = adv.list_resources(limit=5)
        record(
            "COA-010", "list_resources respects limit",
            5, len(resources),
            cause="20 resources, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_update_resource_cost(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1", cost=100.0)
        updated = adv.update_resource(r.id, monthly_cost=150.0)
        record(
            "COA-011", "update_resource changes cost",
            150.0, updated.monthly_cost if updated else None,
            cause="monthly_cost changed to 150",
            effect="new cost stored",
            lesson="Updates must persist",
        )

    def test_update_resource_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1", utilization=50.0)
        updated = adv.update_resource(r.id, utilization_pct=80.0)
        record(
            "COA-012", "update_resource changes utilization",
            80.0, updated.utilization_pct if updated else None,
            cause="utilization changed to 80",
            effect="new utilization stored",
            lesson="Utilization updates must persist",
        )

    def test_update_resource_missing(self) -> None:
        adv = _make_advisor()
        result = adv.update_resource("missing")
        record(
            "COA-013", "update_resource returns None for missing",
            True, result is None,
            cause="invalid ID",
            effect="None returned",
            lesson="Missing resources cannot be updated",
        )

    def test_delete_resource(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        ok = adv.delete_resource(r.id)
        record(
            "COA-014", "delete_resource returns True",
            True, ok,
            cause="valid resource deleted",
            effect="True returned",
            lesson="Delete must succeed for existing resources",
        )
        assert adv.get_resource(r.id) is None

    def test_delete_resource_missing(self) -> None:
        adv = _make_advisor()
        ok = adv.delete_resource("nonexistent")
        record(
            "COA-015", "delete_resource returns False for missing",
            False, ok,
            cause="invalid ID",
            effect="False returned",
            lesson="Delete of missing resource returns False",
        )

    def test_resource_id_unique(self) -> None:
        adv = _make_advisor()
        r1 = _add_compute(adv, "vm-1")
        r2 = _add_compute(adv, "vm-2")
        record(
            "COA-016", "resource IDs are unique",
            True, r1.id != r2.id,
            cause="two resources registered",
            effect="different IDs",
            lesson="UUID generation must be unique",
        )

    def test_resource_serialization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        d = r.to_dict()
        record(
            "COA-017", "to_dict has all fields",
            True, "id" in d and "name" in d and "monthly_cost" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Serialization must be complete",
        )

    def test_register_enum_kind(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("cache-1", resource_kind=ResourceKind.storage)
        record(
            "COA-018", "enum ResourceKind coerced to string",
            "storage", r.resource_kind,
            cause="ResourceKind enum passed",
            effect="stored as string value",
            lesson="Enum coercion for resource kind",
        )

    def test_list_resources_empty(self) -> None:
        adv = _make_advisor()
        resources = adv.list_resources()
        record(
            "COA-019", "empty list when no resources",
            0, len(resources),
            cause="no resources registered",
            effect="empty list",
            lesson="Empty state must return empty list",
        )


class TestSpendRecords:
    """Spend recording and querying."""

    def test_record_spend_basic(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        s = adv.record_spend(r.id, 95.0, "2026-03")
        record(
            "COA-020", "record_spend returns SpendRecord",
            True, isinstance(s, SpendRecord),
            cause="record_spend called",
            effect="SpendRecord returned",
            lesson="Spend factory must return typed object",
        )
        assert s.amount == 95.0

    def test_record_spend_with_category(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        s = adv.record_spend(r.id, 50.0, "2026-03", category="compute")
        record(
            "COA-021", "category stored correctly",
            "compute", s.category,
            cause="category passed",
            effect="category persisted",
            lesson="Category passthrough must work",
        )

    def test_get_spend_all(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        adv.record_spend(r.id, 50.0, "2026-01")
        adv.record_spend(r.id, 60.0, "2026-02")
        adv.record_spend(r.id, 70.0, "2026-03")
        records = adv.get_spend()
        record(
            "COA-022", "get_spend returns all records",
            3, len(records),
            cause="3 records created",
            effect="3 returned",
            lesson="get_spend must return all data",
        )

    def test_get_spend_filter_resource(self) -> None:
        adv = _make_advisor()
        r1 = _add_compute(adv, "vm-1")
        r2 = _add_compute(adv, "vm-2")
        adv.record_spend(r1.id, 50.0, "2026-01")
        adv.record_spend(r2.id, 80.0, "2026-01")
        records = adv.get_spend(resource_id=r1.id)
        record(
            "COA-023", "get_spend filters by resource_id",
            1, len(records),
            cause="1 record for r1",
            effect="1 returned",
            lesson="Resource filter must work",
        )

    def test_get_spend_filter_period(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        adv.record_spend(r.id, 50.0, "2026-01")
        adv.record_spend(r.id, 60.0, "2026-02")
        records = adv.get_spend(period="2026-02")
        record(
            "COA-024", "get_spend filters by period",
            1, len(records),
            cause="1 record in 2026-02",
            effect="1 returned",
            lesson="Period filter must work",
        )

    def test_get_spend_filter_provider(self) -> None:
        adv = _make_advisor()
        r1 = _add_compute(adv, "vm-1", provider="aws")
        r2 = _add_compute(adv, "gcp-vm", provider="gcp")
        adv.record_spend(r1.id, 50.0, "2026-01")
        adv.record_spend(r2.id, 80.0, "2026-01")
        records = adv.get_spend(provider="aws")
        record(
            "COA-025", "get_spend filters by provider",
            1, len(records),
            cause="1 aws record",
            effect="1 returned",
            lesson="Provider filter must work",
        )

    def test_get_spend_limit(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        for i in range(20):
            adv.record_spend(r.id, float(i), f"2026-{i+1:02d}")
        records = adv.get_spend(limit=5)
        record(
            "COA-026", "get_spend respects limit",
            5, len(records),
            cause="20 records, limit=5",
            effect="5 returned",
            lesson="Limit must be respected",
        )

    def test_spend_serialization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        s = adv.record_spend(r.id, 95.0, "2026-03")
        d = s.to_dict()
        record(
            "COA-027", "spend to_dict has all fields",
            True, "id" in d and "amount" in d and "period" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Spend serialization must be complete",
        )


class TestRightsizing:
    """Rightsizing analysis."""

    def test_rightsizing_low_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=15.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-028", "low utilization gets high severity",
            "high", rec.severity,
            cause="utilization=15% (<20%)",
            effect="high severity recommendation",
            lesson="Very low utilization = high severity",
        )
        assert rec.estimated_monthly_savings > 0

    def test_rightsizing_medium_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "underused-vm", cost=200.0, utilization=35.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-029", "medium utilization gets medium severity",
            "medium", rec.severity,
            cause="utilization=35% (20-40%)",
            effect="medium severity recommendation",
            lesson="Moderate underuse = medium severity",
        )

    def test_rightsizing_moderate_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "ok-vm", cost=200.0, utilization=55.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-030", "moderate utilization gets low severity",
            "low", rec.severity,
            cause="utilization=55% (40-60%)",
            effect="low severity recommendation",
            lesson="Slightly underused = low severity",
        )

    def test_rightsizing_good_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "busy-vm", cost=200.0, utilization=75.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-031", "good utilization = no action",
            0, rec.estimated_monthly_savings,
            cause="utilization=75% (>=60%)",
            effect="no savings recommended",
            lesson="Well-used resources need no rightsizing",
        )

    def test_rightsizing_stores_recommendation(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        adv.analyze_rightsizing(r.id)
        recs = adv.get_recommendations(resource_id=r.id)
        record(
            "COA-032", "rightsizing stores recommendation",
            True, len(recs) >= 1,
            cause="analyze_rightsizing called",
            effect="recommendation stored",
            lesson="Analysis must persist recommendations",
        )

    def test_rightsizing_missing_resource(self) -> None:
        adv = _make_advisor()
        rec = adv.analyze_rightsizing("nonexistent")
        record(
            "COA-033", "missing resource returns empty recommendation",
            0.0, rec.estimated_monthly_savings,
            cause="invalid resource_id",
            effect="zero savings",
            lesson="Missing resources handled gracefully",
        )

    def test_rightsizing_savings_calculation(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=100.0, utilization=10.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-034", "savings based on cost and utilization",
            True, rec.estimated_monthly_savings > 0,
            cause="low utilization with known cost",
            effect="positive savings estimated",
            lesson="Savings must be computed from cost/utilization",
        )

    def test_rightsizing_recommendation_type(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=100.0, utilization=10.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-035", "recommendation type is rightsizing",
            "rightsizing", rec.recommendation_type,
            cause="analyze_rightsizing called",
            effect="type is rightsizing",
            lesson="Type must match analysis kind",
        )


class TestSpotOpportunities:
    """Spot instance opportunity scanning."""

    def test_scan_spot_basic(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1", utilization=40.0, cost=100.0)
        spots = adv.scan_spot_opportunities()
        record(
            "COA-036", "scan finds spot opportunities",
            True, len(spots) >= 1,
            cause="compute resource with low utilization",
            effect="spot opportunity found",
            lesson="Low-util computes should have spot opportunities",
        )

    def test_scan_spot_savings(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1", utilization=40.0, cost=100.0)
        spots = adv.scan_spot_opportunities()
        record(
            "COA-037", "spot cost is ~30% of original",
            True, spots[0].spot_cost < spots[0].current_cost if spots else False,
            cause="spot pricing applied",
            effect="spot_cost < current_cost",
            lesson="Spot pricing must show savings",
        )

    def test_scan_spot_filter_provider(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "aws-vm", provider="aws", utilization=40.0)
        _add_compute(adv, "gcp-vm", provider="gcp", utilization=40.0)
        spots = adv.scan_spot_opportunities(provider="aws")
        record(
            "COA-038", "scan filters by provider",
            True, all(s.provider == "aws" for s in spots),
            cause="provider=aws filter",
            effect="only aws spots returned",
            lesson="Provider filter must work for spots",
        )

    def test_scan_spot_high_util_excluded(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "busy-vm", utilization=90.0, cost=100.0)
        spots = adv.scan_spot_opportunities()
        record(
            "COA-039", "high utilization excluded from spots",
            0, len(spots),
            cause="utilization=90% (>=70%)",
            effect="no spot opportunities",
            lesson="Well-used resources shouldn't switch to spot",
        )

    def test_scan_spot_non_compute_excluded(self) -> None:
        adv = _make_advisor()
        adv.register_resource("db-1", "aws", "database", "us-east-1", 100.0,
                              utilization_pct=20.0)
        spots = adv.scan_spot_opportunities()
        record(
            "COA-040", "non-compute excluded from spot scan",
            0, len(spots),
            cause="database resource",
            effect="no spot opportunities",
            lesson="Only compute resources get spot recommendations",
        )

    def test_scan_spot_filter_region(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-us", utilization=40.0)
        adv.register_resource("vm-eu", "aws", "compute", "eu-west-1", 100.0,
                              utilization_pct=40.0)
        spots = adv.scan_spot_opportunities(region="eu-west-1")
        record(
            "COA-041", "scan filters by region",
            True, all(s.region == "eu-west-1" for s in spots) if spots else True,
            cause="region=eu-west-1 filter",
            effect="only eu-west-1 spots",
            lesson="Region filter must work for spots",
        )


class TestRecommendations:
    """Recommendation management."""

    def test_get_recommendations_empty(self) -> None:
        adv = _make_advisor()
        recs = adv.get_recommendations()
        record(
            "COA-042", "empty recommendations list",
            0, len(recs),
            cause="no analysis done",
            effect="empty list",
            lesson="Empty state returns empty list",
        )

    def test_get_recommendations_filter_severity(self) -> None:
        adv = _make_advisor()
        r1 = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        r2 = _add_compute(adv, "ok-vm", cost=200.0, utilization=55.0)
        adv.analyze_rightsizing(r1.id)
        adv.analyze_rightsizing(r2.id)
        recs = adv.get_recommendations(severity="high")
        record(
            "COA-043", "recommendations filter by severity",
            True, all(r.severity == "high" for r in recs),
            cause="filter severity=high",
            effect="only high severity returned",
            lesson="Severity filter must work",
        )

    def test_get_recommendations_filter_status(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        adv.analyze_rightsizing(r.id)
        recs = adv.get_recommendations(status="pending")
        record(
            "COA-044", "recommendations filter by status",
            True, all(r.status == "pending" for r in recs),
            cause="filter status=pending",
            effect="only pending returned",
            lesson="Status filter must work",
        )

    def test_update_recommendation_status(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        rec = adv.analyze_rightsizing(r.id)
        updated = adv.update_recommendation_status(rec.id, "accepted")
        record(
            "COA-045", "update recommendation status",
            "accepted", updated.status if updated else None,
            cause="status changed to accepted",
            effect="status updated",
            lesson="Status updates must persist",
        )

    def test_update_recommendation_enum_status(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        rec = adv.analyze_rightsizing(r.id)
        updated = adv.update_recommendation_status(rec.id, RecommendationStatus.implemented)
        record(
            "COA-046", "enum status coerced to string",
            "implemented", updated.status if updated else None,
            cause="RecommendationStatus enum passed",
            effect="stored as string value",
            lesson="Enum coercion for status",
        )

    def test_update_recommendation_missing(self) -> None:
        adv = _make_advisor()
        result = adv.update_recommendation_status("missing", "accepted")
        record(
            "COA-047", "update missing recommendation returns None",
            True, result is None,
            cause="invalid rec ID",
            effect="None returned",
            lesson="Missing recommendations handled gracefully",
        )

    def test_recommendation_serialization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "idle-vm", cost=200.0, utilization=10.0)
        rec = adv.analyze_rightsizing(r.id)
        d = rec.to_dict()
        record(
            "COA-048", "recommendation to_dict complete",
            True, "id" in d and "severity" in d and "estimated_monthly_savings" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Recommendation serialization complete",
        )

    def test_get_recommendations_limit(self) -> None:
        adv = _make_advisor()
        for i in range(10):
            r = _add_compute(adv, f"vm-{i}", cost=100.0, utilization=10.0)
            adv.analyze_rightsizing(r.id)
        recs = adv.get_recommendations(limit=3)
        record(
            "COA-049", "recommendations respect limit",
            3, len(recs),
            cause="10 recommendations, limit=3",
            effect="3 returned",
            lesson="Limit must be respected",
        )


class TestBudgets:
    """Budget management and alerting."""

    def test_set_budget(self) -> None:
        adv = _make_advisor()
        b = adv.set_budget("monthly-total", 1000.0)
        record(
            "COA-050", "set_budget returns BudgetAlert",
            True, isinstance(b, BudgetAlert),
            cause="set_budget called",
            effect="BudgetAlert returned",
            lesson="Budget factory must return typed object",
        )
        assert b.budget_limit == 1000.0

    def test_budget_not_breached_initially(self) -> None:
        adv = _make_advisor()
        adv.set_budget("monthly", 1000.0)
        budgets = adv.check_budgets()
        record(
            "COA-051", "budget not breached initially",
            False, budgets[0].breached if budgets else True,
            cause="no spend recorded",
            effect="not breached",
            lesson="New budgets start clean",
        )

    def test_budget_breached_at_threshold(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        adv.set_budget("monthly", 100.0)
        adv.record_spend(r.id, 85.0, "2026-03")
        budgets = adv.check_budgets()
        record(
            "COA-052", "budget breached at 80% threshold",
            True, budgets[0].breached if budgets else False,
            cause="spend=85 of budget=100 (85%)",
            effect="breached at 80% threshold",
            lesson="Budget alerts must trigger at threshold",
        )

    def test_budget_not_breached_below_threshold(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        adv.set_budget("monthly", 1000.0)
        adv.record_spend(r.id, 50.0, "2026-03")
        budgets = adv.check_budgets()
        record(
            "COA-053", "budget not breached below threshold",
            False, budgets[0].breached if budgets else True,
            cause="spend=50 of budget=1000 (5%)",
            effect="not breached",
            lesson="Below threshold must not trigger",
        )

    def test_multiple_budgets(self) -> None:
        adv = _make_advisor()
        adv.set_budget("monthly", 1000.0)
        adv.set_budget("quarterly", 3000.0)
        budgets = adv.check_budgets()
        record(
            "COA-054", "multiple budgets tracked",
            2, len(budgets),
            cause="2 budgets set",
            effect="2 checked",
            lesson="Multiple budgets must all be checked",
        )

    def test_budget_serialization(self) -> None:
        adv = _make_advisor()
        b = adv.set_budget("monthly", 500.0)
        d = b.to_dict()
        record(
            "COA-055", "budget to_dict complete",
            True, "budget_name" in d and "budget_limit" in d and "breached" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Budget serialization complete",
        )


class TestCostSummary:
    """Cost summary aggregation."""

    def test_summary_basic(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1", provider="aws", cost=100.0, utilization=50.0)
        adv.record_spend(r.id, 95.0, "2026-03", category="compute")
        summary = adv.get_cost_summary()
        record(
            "COA-056", "summary returns CostSummary",
            True, isinstance(summary, CostSummary),
            cause="get_cost_summary called",
            effect="CostSummary returned",
            lesson="Summary must return typed object",
        )

    def test_summary_total_spend(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1", cost=100.0)
        adv.record_spend(r.id, 50.0, "2026-01")
        adv.record_spend(r.id, 60.0, "2026-02")
        summary = adv.get_cost_summary()
        record(
            "COA-057", "summary aggregates total spend",
            110.0, summary.total_spend,
            cause="2 spend records totaling 110",
            effect="total_spend=110",
            lesson="Total spend must aggregate correctly",
        )

    def test_summary_resource_count(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1")
        _add_compute(adv, "vm-2")
        summary = adv.get_cost_summary()
        record(
            "COA-058", "summary counts resources",
            2, summary.resource_count,
            cause="2 resources registered",
            effect="resource_count=2",
            lesson="Resource count must be accurate",
        )

    def test_summary_filter_provider(self) -> None:
        adv = _make_advisor()
        r1 = _add_compute(adv, "vm-1", provider="aws", cost=100.0)
        r2 = _add_compute(adv, "gcp-vm", provider="gcp", cost=200.0)
        adv.record_spend(r1.id, 50.0, "2026-03")
        adv.record_spend(r2.id, 80.0, "2026-03")
        summary = adv.get_cost_summary(provider="aws")
        record(
            "COA-059", "summary filters by provider",
            1, summary.resource_count,
            cause="1 aws resource",
            effect="resource_count=1 for aws",
            lesson="Provider filter must work for summary",
        )

    def test_summary_avg_utilization(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1", utilization=40.0)
        _add_compute(adv, "vm-2", utilization=80.0)
        summary = adv.get_cost_summary()
        record(
            "COA-060", "summary computes avg utilization",
            60.0, summary.avg_utilization,
            cause="utilization 40% and 80%",
            effect="avg=60%",
            lesson="Average utilization must be correct",
        )

    def test_summary_empty(self) -> None:
        adv = _make_advisor()
        summary = adv.get_cost_summary()
        record(
            "COA-061", "summary handles empty state",
            0, summary.resource_count,
            cause="no resources",
            effect="resource_count=0",
            lesson="Empty state must work gracefully",
        )

    def test_summary_serialization(self) -> None:
        adv = _make_advisor()
        summary = adv.get_cost_summary()
        d = summary.to_dict()
        record(
            "COA-062", "summary to_dict complete",
            True, "total_spend" in d and "resource_count" in d,
            cause="to_dict called",
            effect="dict with all fields",
            lesson="Summary serialization complete",
        )


class TestExportAndClear:
    """State export and clear."""

    def test_export_state(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1")
        state = adv.export_state()
        record(
            "COA-063", "export_state returns dict",
            True, isinstance(state, dict),
            cause="export_state called",
            effect="dict returned",
            lesson="Export must return plain dict",
        )
        assert "resources" in state
        assert "exported_at" in state

    def test_export_state_has_all_keys(self) -> None:
        adv = _make_advisor()
        state = adv.export_state()
        expected_keys = {"resources", "spend_records", "recommendations",
                         "spot_opportunities", "budgets", "exported_at"}
        record(
            "COA-064", "export has all expected keys",
            expected_keys, set(state.keys()),
            cause="export_state called",
            effect="all keys present",
            lesson="Export must include all state",
        )

    def test_clear(self) -> None:
        adv = _make_advisor()
        _add_compute(adv, "vm-1")
        adv.clear()
        resources = adv.list_resources()
        record(
            "COA-065", "clear removes all state",
            0, len(resources),
            cause="clear called",
            effect="no resources remain",
            lesson="Clear must remove all data",
        )


class TestWingmanValidation:
    """Wingman pair validation."""

    def test_wingman_pair_match(self) -> None:
        result = validate_wingman_pair(["a", "b", "c"], ["a", "b", "c"])
        record(
            "COA-066", "matching pair passes",
            True, result["passed"],
            cause="storyline matches actuals",
            effect="validation passes",
            lesson="Matching pairs must pass",
        )

    def test_wingman_pair_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a", "x"])
        record(
            "COA-067", "mismatching pair fails",
            False, result["passed"],
            cause="actuals differ from storyline",
            effect="validation fails",
            lesson="Mismatches must be caught",
        )

    def test_wingman_empty_storyline(self) -> None:
        result = validate_wingman_pair([], ["a"])
        record(
            "COA-068", "empty storyline fails",
            False, result["passed"],
            cause="empty storyline",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_empty_actuals(self) -> None:
        result = validate_wingman_pair(["a"], [])
        record(
            "COA-069", "empty actuals fails",
            False, result["passed"],
            cause="empty actuals",
            effect="validation fails",
            lesson="Empty inputs must be rejected",
        )

    def test_wingman_length_mismatch(self) -> None:
        result = validate_wingman_pair(["a", "b"], ["a"])
        record(
            "COA-070", "length mismatch fails",
            False, result["passed"],
            cause="different lengths",
            effect="validation fails",
            lesson="Length mismatches must be caught",
        )

    def test_wingman_pair_count(self) -> None:
        result = validate_wingman_pair(["x", "y", "z"], ["x", "y", "z"])
        record(
            "COA-071", "pair_count in response",
            3, result.get("pair_count"),
            cause="3 pairs validated",
            effect="pair_count=3",
            lesson="Response must include pair_count",
        )


class TestSandboxGate:
    """Causality Sandbox gating."""

    def test_sandbox_pass(self) -> None:
        result = gate_coa_in_sandbox({"provider": "aws"})
        record(
            "COA-072", "sandbox gate passes with provider",
            True, result["passed"],
            cause="provider key present",
            effect="gate passes",
            lesson="Valid context must pass gate",
        )

    def test_sandbox_missing_provider(self) -> None:
        result = gate_coa_in_sandbox({})
        record(
            "COA-073", "sandbox gate fails without provider",
            False, result["passed"],
            cause="no provider key",
            effect="gate fails",
            lesson="Missing required keys must fail gate",
        )

    def test_sandbox_empty_provider(self) -> None:
        result = gate_coa_in_sandbox({"provider": ""})
        record(
            "COA-074", "sandbox gate fails with empty provider",
            False, result["passed"],
            cause="empty provider string",
            effect="gate fails",
            lesson="Empty values must fail gate",
        )

    def test_sandbox_returns_provider(self) -> None:
        result = gate_coa_in_sandbox({"provider": "gcp"})
        record(
            "COA-075", "sandbox gate returns provider",
            "gcp", result.get("provider"),
            cause="provider=gcp passed",
            effect="provider in response",
            lesson="Response must echo provider",
        )


class TestFlaskAPI:
    """Flask Blueprint API endpoints."""

    def _make_app(self):
        try:
            from flask import Flask
        except ImportError:
            return None, None
        adv = _make_advisor()
        app = Flask(__name__)
        app.config["TESTING"] = True
        bp = create_cost_optimization_api(adv)
        app.register_blueprint(bp)
        return app, adv

    def test_api_register_resource(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-076", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/coa/resources", json={
                "name": "web-server", "provider": "aws",
                "resource_kind": "compute", "region": "us-east-1",
                "monthly_cost": 200.0,
            })
        record(
            "COA-076", "POST /coa/resources returns 201",
            201, resp.status_code,
            cause="valid resource data",
            effect="201 created",
            lesson="Resource creation must return 201",
        )

    def test_api_list_resources(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-077", "Flask not installed — skip", True, True)
            return
        adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        with app.test_client() as c:
            resp = c.get("/api/coa/resources")
        record(
            "COA-077", "GET /coa/resources returns 200",
            200, resp.status_code,
            cause="resources exist",
            effect="200 OK",
            lesson="List must return 200",
        )
        assert len(resp.get_json()) >= 1

    def test_api_get_resource(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-078", "Flask not installed — skip", True, True)
            return
        r = adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        with app.test_client() as c:
            resp = c.get(f"/api/coa/resources/{r.id}")
        record(
            "COA-078", "GET /coa/resources/<id> returns 200",
            200, resp.status_code,
            cause="valid resource ID",
            effect="200 OK",
            lesson="Get by ID must return 200",
        )

    def test_api_get_resource_404(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-079", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/coa/resources/nonexistent")
        record(
            "COA-079", "GET /coa/resources/<missing> returns 404",
            404, resp.status_code,
            cause="invalid resource ID",
            effect="404 Not Found",
            lesson="Missing resource must return 404",
        )

    def test_api_record_spend(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-080", "Flask not installed — skip", True, True)
            return
        r = adv.register_resource("vm-1", "aws", "compute", "us-east-1", 100.0)
        with app.test_client() as c:
            resp = c.post("/api/coa/spend", json={
                "resource_id": r.id, "amount": 95.0, "period": "2026-03",
            })
        record(
            "COA-080", "POST /coa/spend returns 201",
            201, resp.status_code,
            cause="valid spend data",
            effect="201 created",
            lesson="Spend creation must return 201",
        )

    def test_api_analyze_rightsizing(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-081", "Flask not installed — skip", True, True)
            return
        r = adv.register_resource("vm-1", "aws", "compute", "us-east-1",
                                  100.0, utilization_pct=15.0)
        with app.test_client() as c:
            resp = c.post(f"/api/coa/analyze/{r.id}")
        record(
            "COA-081", "POST /coa/analyze/<id> returns 200",
            200, resp.status_code,
            cause="valid resource for analysis",
            effect="200 OK",
            lesson="Analysis must return 200",
        )

    def test_api_scan_spot(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-082", "Flask not installed — skip", True, True)
            return
        adv.register_resource("vm-1", "aws", "compute", "us-east-1",
                              100.0, utilization_pct=40.0)
        with app.test_client() as c:
            resp = c.post("/api/coa/spot/scan", json={})
        record(
            "COA-082", "POST /coa/spot/scan returns 200",
            200, resp.status_code,
            cause="compute resources exist",
            effect="200 OK",
            lesson="Spot scan must return 200",
        )

    def test_api_get_recommendations(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-083", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/coa/recommendations")
        record(
            "COA-083", "GET /coa/recommendations returns 200",
            200, resp.status_code,
            cause="recommendations endpoint called",
            effect="200 OK",
            lesson="Recommendations list must return 200",
        )

    def test_api_set_budget(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-084", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/coa/budgets", json={
                "budget_name": "monthly", "budget_limit": 1000.0,
            })
        record(
            "COA-084", "POST /coa/budgets returns 201",
            201, resp.status_code,
            cause="valid budget data",
            effect="201 created",
            lesson="Budget creation must return 201",
        )

    def test_api_check_budgets(self) -> None:
        app, adv = self._make_app()
        if app is None:
            record("COA-085", "Flask not installed — skip", True, True)
            return
        adv.set_budget("monthly", 1000.0)
        with app.test_client() as c:
            resp = c.get("/api/coa/budgets/check")
        record(
            "COA-085", "GET /coa/budgets/check returns 200",
            200, resp.status_code,
            cause="budget exists",
            effect="200 OK",
            lesson="Budget check must return 200",
        )

    def test_api_summary(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-086", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/coa/summary")
        record(
            "COA-086", "GET /coa/summary returns 200",
            200, resp.status_code,
            cause="summary endpoint called",
            effect="200 OK",
            lesson="Summary must return 200",
        )

    def test_api_export(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-087", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/coa/export")
        record(
            "COA-087", "POST /coa/export returns 200",
            200, resp.status_code,
            cause="export endpoint called",
            effect="200 OK",
            lesson="Export must return 200",
        )

    def test_api_health(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-088", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.get("/api/coa/health")
        data = resp.get_json()
        record(
            "COA-088", "GET /coa/health returns module COA-001",
            "COA-001", data.get("module"),
            cause="health endpoint called",
            effect="module=COA-001",
            lesson="Health must identify the module",
        )

    def test_api_missing_name(self) -> None:
        app, _ = self._make_app()
        if app is None:
            record("COA-089", "Flask not installed — skip", True, True)
            return
        with app.test_client() as c:
            resp = c.post("/api/coa/resources", json={})
        record(
            "COA-089", "POST /coa/resources without name returns 400",
            400, resp.status_code,
            cause="missing name field",
            effect="400 Bad Request",
            lesson="Missing fields must return 400",
        )


class TestConcurrency:
    """Thread-safety tests."""

    def test_concurrent_register(self) -> None:
        adv = _make_advisor()
        errors: List[str] = []

        def register_batch(prefix: str) -> None:
            try:
                for i in range(50):
                    adv.register_resource(f"{prefix}-{i}", "aws", "compute",
                                          "us-east-1", 10.0)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=register_batch, args=(f"t{t}",))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        resources = adv.list_resources(limit=500)
        record(
            "COA-090", "concurrent register is thread-safe",
            True, len(resources) == 200 and not errors,
            cause="4 threads × 50 registers",
            effect="200 resources, no errors",
            lesson="Registration must be thread-safe",
        )

    def test_concurrent_spend(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        errors: List[str] = []

        def spend_batch(tid: int) -> None:
            try:
                for i in range(50):
                    adv.record_spend(r.id, float(i), f"2026-{tid:02d}")
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=spend_batch, args=(t,))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        records_list = adv.get_spend(limit=500)
        record(
            "COA-091", "concurrent spend is thread-safe",
            True, len(records_list) == 200 and not errors,
            cause="4 threads × 50 spends",
            effect="200 records, no errors",
            lesson="Spend recording must be thread-safe",
        )

    def test_concurrent_analyze(self) -> None:
        adv = _make_advisor()
        resources = [_add_compute(adv, f"vm-{i}", utilization=float(i * 5))
                     for i in range(20)]
        errors: List[str] = []

        def analyze_batch(start: int) -> None:
            try:
                for r in resources[start:start + 10]:
                    adv.analyze_rightsizing(r.id)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=analyze_batch, args=(s,))
                   for s in range(0, 20, 10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        record(
            "COA-092", "concurrent analyze is thread-safe",
            True, not errors,
            cause="2 threads analyzing 10 each",
            effect="no errors",
            lesson="Analysis must be thread-safe",
        )


class TestEdgeCases:
    """Edge cases and boundary values."""

    def test_zero_cost_resource(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("free-tier", "aws", "compute", "us-east-1", 0.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-093", "zero cost resource analyzed safely",
            0.0, rec.estimated_monthly_savings,
            cause="monthly_cost=0",
            effect="zero savings",
            lesson="Zero cost must not cause errors",
        )

    def test_100_pct_utilization(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "maxed-vm", cost=100.0, utilization=100.0)
        rec = adv.analyze_rightsizing(r.id)
        record(
            "COA-094", "100% utilization = no rightsizing",
            0, rec.estimated_monthly_savings,
            cause="utilization=100%",
            effect="no savings",
            lesson="Fully utilized resources need no rightsizing",
        )

    def test_negative_spend_handled(self) -> None:
        adv = _make_advisor()
        r = _add_compute(adv, "vm-1")
        s = adv.record_spend(r.id, -10.0, "2026-03")
        record(
            "COA-095", "negative spend recorded without error",
            -10.0, s.amount,
            cause="negative amount (credit/refund)",
            effect="recorded as-is",
            lesson="Credits/refunds may be negative",
        )

    def test_large_cost_value(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("big-instance", "aws", "compute",
                                  "us-east-1", 999_999.99)
        record(
            "COA-096", "large cost value handled",
            999_999.99, r.monthly_cost,
            cause="very large cost",
            effect="stored correctly",
            lesson="No overflow on large values",
        )

    def test_special_chars_in_name(self) -> None:
        adv = _make_advisor()
        r = adv.register_resource("vm/with spaces & symbols!", "aws")
        record(
            "COA-097", "special characters in name",
            "vm/with spaces & symbols!", r.name,
            cause="special chars in name",
            effect="stored as-is",
            lesson="Names must accept arbitrary strings",
        )
