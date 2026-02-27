"""
Tests for SAF-003: TenantResourceGovernor.

Validates limit configuration, usage tracking, limit enforcement,
snapshot generation, persistence, and EventBackbone integration.

Design Label: TEST-026 / SAF-003
Owner: QA Team
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tenant_resource_governor import (
    TenantResourceGovernor,
    ResourceLimits,
    ResourceUsage,
    LimitCheckResult,
    UsageSnapshot,
)
from persistence_manager import PersistenceManager
from event_backbone import EventBackbone, EventType


@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))

@pytest.fixture
def backbone():
    return EventBackbone()

@pytest.fixture
def gov():
    return TenantResourceGovernor()

@pytest.fixture
def wired_gov(pm, backbone):
    return TenantResourceGovernor(persistence_manager=pm, event_backbone=backbone)


class TestLimitManagement:
    def test_set_limits(self, gov):
        gov.set_limits(ResourceLimits("t1", max_api_calls=100))
        assert gov.get_limits("t1") is not None

    def test_unknown_tenant(self, gov):
        assert gov.get_limits("nonexistent") is None

    def test_remove_tenant(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        assert gov.remove_tenant("t1") is True
        assert gov.remove_tenant("t1") is False


class TestUsageTracking:
    def test_record_usage(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        assert gov.record_usage("t1", api_calls=5) is True
        usage = gov.get_usage("t1")
        assert usage["api_calls"] == 5

    def test_cumulative_usage(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        gov.record_usage("t1", api_calls=3)
        gov.record_usage("t1", api_calls=7)
        usage = gov.get_usage("t1")
        assert usage["api_calls"] == 10

    def test_unknown_tenant_usage(self, gov):
        assert gov.record_usage("unknown", api_calls=1) is False

    def test_reset_usage(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        gov.record_usage("t1", api_calls=10)
        assert gov.reset_usage("t1") is True
        usage = gov.get_usage("t1")
        assert usage["api_calls"] == 0


class TestLimitEnforcement:
    def test_allowed(self, gov):
        gov.set_limits(ResourceLimits("t1", max_api_calls=100))
        result = gov.check_request("t1", api_calls=10)
        assert result == LimitCheckResult.ALLOWED

    def test_denied_over_limit(self, gov):
        gov.set_limits(ResourceLimits("t1", max_api_calls=10))
        gov.record_usage("t1", api_calls=8)
        result = gov.check_request("t1", api_calls=5)
        assert result == LimitCheckResult.DENIED_OVER_LIMIT

    def test_denied_unknown(self, gov):
        result = gov.check_request("unknown", api_calls=1)
        assert result == LimitCheckResult.DENIED_UNKNOWN_TENANT

    def test_budget_limit(self, gov):
        gov.set_limits(ResourceLimits("t1", max_budget_usd=50.0))
        gov.record_usage("t1", budget_usd=45.0)
        assert gov.check_request("t1", budget_usd=10.0) == LimitCheckResult.DENIED_OVER_LIMIT
        assert gov.check_request("t1", budget_usd=3.0) == LimitCheckResult.ALLOWED


class TestSnapshot:
    def test_snapshot_generated(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        snap = gov.snapshot("t1")
        assert snap is not None
        assert snap.tenant_id == "t1"

    def test_snapshot_unknown_tenant(self, gov):
        assert gov.snapshot("unknown") is None

    def test_snapshot_to_dict(self, gov):
        gov.set_limits(ResourceLimits("t1"))
        snap = gov.snapshot("t1")
        d = snap.to_dict()
        assert "snapshot_id" in d
        assert "usage" in d


class TestPersistence:
    def test_snapshot_persisted(self, wired_gov, pm):
        wired_gov.set_limits(ResourceLimits("t1"))
        snap = wired_gov.snapshot("t1")
        loaded = pm.load_document(snap.snapshot_id)
        assert loaded is not None


class TestEventBackbone:
    def test_breach_publishes_event(self, wired_gov, backbone):
        received = []
        backbone.subscribe(EventType.SYSTEM_HEALTH, lambda e: received.append(e))
        wired_gov.set_limits(ResourceLimits("t1", max_api_calls=5))
        wired_gov.record_usage("t1", api_calls=5)
        wired_gov.check_request("t1", api_calls=1)
        backbone.process_pending()
        assert len(received) >= 1


class TestStatus:
    def test_status(self, gov):
        s = gov.get_status()
        assert s["total_tenants"] == 0

    def test_wired_status(self, wired_gov):
        s = wired_gov.get_status()
        assert s["persistence_attached"] is True
