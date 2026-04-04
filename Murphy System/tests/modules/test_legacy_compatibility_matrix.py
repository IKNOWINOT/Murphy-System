"""Tests for legacy_compatibility_matrix module."""

import sys
import os
import pytest

# Ensure the src package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.legacy_compatibility_matrix import (
    LegacyCompatibilityMatrixAdapter,
    CompatibilityEntry,
    GOVERNANCE_ROLE_REQUIREMENTS,
    COMPATIBILITY_LEVEL_SCORES,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_entry(**overrides) -> CompatibilityEntry:
    defaults = dict(
        source_system="SystemA",
        target_system="SystemB",
        compatibility_level="full",
        bridge_type="direct",
        requires_validation=False,
        governance_policy="open",
        metadata={},
    )
    defaults.update(overrides)
    return CompatibilityEntry(**defaults)


def _identity_hook(payload):
    return payload


def _upper_hook(payload):
    return {k: v.upper() if isinstance(v, str) else v for k, v in payload.items()}


def _failing_hook(payload):
    raise RuntimeError("hook failure")


# ------------------------------------------------------------------
# Entry registration
# ------------------------------------------------------------------

class TestEntryRegistration:
    def test_register_returns_entry_id(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        eid = adapter.register_entry(_make_entry())
        assert eid.startswith("compat-")
        assert len(eid) == len("compat-") + 12

    def test_register_multiple_entries(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        e1 = adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        e2 = adapter.register_entry(_make_entry(source_system="C", target_system="D"))
        assert e1 != e2

    def test_register_overwrites_same_pair(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(compatibility_level="partial"))
        adapter.register_entry(_make_entry(compatibility_level="full"))
        result = adapter.evaluate_compatibility("SystemA", "SystemB")
        assert result["compatibility_level"] == "full"

    def test_entry_metadata_preserved(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(metadata={"version": "2.1"}))
        result = adapter.evaluate_compatibility("SystemA", "SystemB")
        assert result["metadata"]["version"] == "2.1"


# ------------------------------------------------------------------
# Bridge hook registration
# ------------------------------------------------------------------

class TestBridgeHookRegistration:
    def test_register_hook_returns_id(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        hid = adapter.register_bridge_hook("A", "B", _identity_hook)
        assert hid.startswith("hook-")
        assert len(hid) == len("hook-") + 12

    def test_register_multiple_hooks(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        h1 = adapter.register_bridge_hook("A", "B", _identity_hook)
        h2 = adapter.register_bridge_hook("C", "D", _identity_hook)
        assert h1 != h2

    def test_hook_overwrite(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_bridge_hook("A", "B", _identity_hook)
        adapter.register_bridge_hook("A", "B", _upper_hook)
        result = adapter.execute_bridge("A", "B", {"key": "value"})
        assert result["transformed_payload"]["key"] == "VALUE"


# ------------------------------------------------------------------
# Bridge execution
# ------------------------------------------------------------------

class TestBridgeExecution:
    def test_execute_success(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_bridge_hook("A", "B", _identity_hook)
        result = adapter.execute_bridge("A", "B", {"x": 1})
        assert result["status"] == "success"
        assert result["transformed_payload"] == {"x": 1}
        assert "timestamp" in result

    def test_execute_transform(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_bridge_hook("A", "B", _upper_hook)
        result = adapter.execute_bridge("A", "B", {"name": "alice"})
        assert result["transformed_payload"]["name"] == "ALICE"

    def test_execute_no_hook(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        result = adapter.execute_bridge("X", "Y", {})
        assert result["status"] == "error"
        assert "No bridge hook" in result["error"]

    def test_execute_hook_exception(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_bridge_hook("A", "B", _failing_hook)
        result = adapter.execute_bridge("A", "B", {})
        assert result["status"] == "error"
        assert "hook failure" in result["error"]

    def test_execution_recorded_in_history(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_bridge_hook("A", "B", _identity_hook)
        adapter.execute_bridge("A", "B", {"a": 1})
        adapter.execute_bridge("A", "B", {"b": 2})
        report = adapter.get_matrix_report()
        assert report["total_executions"] == 2


# ------------------------------------------------------------------
# Compatibility evaluation
# ------------------------------------------------------------------

class TestCompatibilityEvaluation:
    def test_evaluate_existing_pair(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry())
        result = adapter.evaluate_compatibility("SystemA", "SystemB")
        assert result["status"] == "found"
        assert result["compatibility_level"] == "full"
        assert result["bridge_type"] == "direct"

    def test_evaluate_unknown_pair(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        result = adapter.evaluate_compatibility("X", "Y")
        assert result["status"] == "unknown"
        assert result["compatibility_level"] is None

    def test_evaluate_has_bridge_hook_flag(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry())
        adapter.register_bridge_hook("SystemA", "SystemB", _identity_hook)
        result = adapter.evaluate_compatibility("SystemA", "SystemB")
        assert result["has_bridge_hook"] is True

    def test_evaluate_no_bridge_hook_flag(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry())
        result = adapter.evaluate_compatibility("SystemA", "SystemB")
        assert result["has_bridge_hook"] is False


# ------------------------------------------------------------------
# Migration path (BFS)
# ------------------------------------------------------------------

class TestMigrationPath:
    def test_direct_path(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        path = adapter.get_migration_path("A", "B")
        assert path == ["A", "B"]

    def test_multi_hop_path(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        adapter.register_entry(_make_entry(source_system="B", target_system="C"))
        adapter.register_entry(_make_entry(source_system="C", target_system="D"))
        path = adapter.get_migration_path("A", "D")
        assert path == ["A", "B", "C", "D"]

    def test_no_path(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        path = adapter.get_migration_path("B", "A")
        assert path == []

    def test_same_source_target(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        path = adapter.get_migration_path("A", "A")
        assert path == ["A"]

    def test_shortest_path_preferred(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        adapter.register_entry(_make_entry(source_system="B", target_system="D"))
        adapter.register_entry(_make_entry(source_system="A", target_system="C"))
        adapter.register_entry(_make_entry(source_system="C", target_system="D"))
        path = adapter.get_migration_path("A", "D")
        assert len(path) == 3  # A -> B -> D or A -> C -> D


# ------------------------------------------------------------------
# Readiness scoring
# ------------------------------------------------------------------

class TestReadinessScoring:
    def test_full_compat_no_validation_with_hook(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(compatibility_level="full", requires_validation=False))
        adapter.register_bridge_hook("SystemA", "SystemB", _identity_hook)
        result = adapter.score_bridge_readiness("SystemA", "SystemB")
        assert result["status"] == "scored"
        assert result["score"] == 1.0

    def test_partial_compat_with_validation_no_hook(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(compatibility_level="partial", requires_validation=True))
        result = adapter.score_bridge_readiness("SystemA", "SystemB")
        assert result["score"] == pytest.approx(0.5 * 0.5 + 0.5 * 0.2 + 0.0 * 0.3, abs=1e-4)

    def test_unknown_pair_score_zero(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        result = adapter.score_bridge_readiness("X", "Y")
        assert result["status"] == "unknown"
        assert result["score"] == 0.0

    def test_incompatible_score(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(compatibility_level="incompatible", requires_validation=True))
        result = adapter.score_bridge_readiness("SystemA", "SystemB")
        assert result["score"] == pytest.approx(0.0 * 0.5 + 0.5 * 0.2 + 0.0 * 0.3, abs=1e-4)


# ------------------------------------------------------------------
# Matrix report
# ------------------------------------------------------------------

class TestMatrixReport:
    def test_empty_report(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        report = adapter.get_matrix_report()
        assert report["status"] == "ok"
        assert report["total_entries"] == 0
        assert report["total_hooks"] == 0
        assert report["entries"] == []

    def test_report_after_registrations(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        adapter.register_entry(_make_entry(source_system="C", target_system="D", compatibility_level="partial"))
        adapter.register_bridge_hook("A", "B", _identity_hook)
        report = adapter.get_matrix_report()
        assert report["total_entries"] == 2
        assert report["total_hooks"] == 1
        assert "full" in report["compatibility_level_counts"]
        assert "partial" in report["compatibility_level_counts"]

    def test_report_contains_timestamp(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        report = adapter.get_matrix_report()
        assert "timestamp" in report


# ------------------------------------------------------------------
# Governance validation
# ------------------------------------------------------------------

class TestGovernanceValidation:
    def test_open_policy_allows_viewer(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="open"))
        result = adapter.validate_governance("SystemA", "SystemB", "viewer")
        assert result["allowed"] is True

    def test_strict_policy_denies_operator(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="strict"))
        result = adapter.validate_governance("SystemA", "SystemB", "operator")
        assert result["allowed"] is False

    def test_strict_policy_allows_admin(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="strict"))
        result = adapter.validate_governance("SystemA", "SystemB", "admin")
        assert result["allowed"] is True

    def test_critical_policy_only_superadmin(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="critical"))
        assert adapter.validate_governance("SystemA", "SystemB", "admin")["allowed"] is False
        assert adapter.validate_governance("SystemA", "SystemB", "superadmin")["allowed"] is True

    def test_no_entry_governance(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        result = adapter.validate_governance("X", "Y", "admin")
        assert result["status"] == "no_entry"
        assert result["allowed"] is False

    def test_unknown_policy(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="custom_xyz"))
        result = adapter.validate_governance("SystemA", "SystemB", "admin")
        assert result["status"] == "unknown_policy"
        assert result["allowed"] is False

    def test_invalid_role(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(governance_policy="open"))
        result = adapter.validate_governance("SystemA", "SystemB", "hacker")
        assert result["allowed"] is False


# ------------------------------------------------------------------
# Clear / reset
# ------------------------------------------------------------------

class TestClear:
    def test_clear_resets_entries(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry())
        adapter.register_bridge_hook("SystemA", "SystemB", _identity_hook)
        adapter.execute_bridge("SystemA", "SystemB", {"x": 1})
        adapter.clear()
        report = adapter.get_matrix_report()
        assert report["total_entries"] == 0
        assert report["total_hooks"] == 0
        assert report["total_executions"] == 0

    def test_clear_resets_migration_paths(self):
        adapter = LegacyCompatibilityMatrixAdapter()
        adapter.register_entry(_make_entry(source_system="A", target_system="B"))
        adapter.clear()
        assert adapter.get_migration_path("A", "B") == []
