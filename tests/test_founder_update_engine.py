"""
Tests for ARCH-007: Founder Update Engine.

Covers:
- RecommendationEngine generates recommendations of all types
- SubsystemRegistry discovers and tracks subsystems
- UpdateCoordinator plans and sequences updates
- Persistence save/load round-trip
- Priority filtering and type filtering

Design Label: TEST-ARCH-007
Owner: QA Team
"""

import os
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from founder_update_engine import (
    HEALTH_DEGRADED,
    HEALTH_FAILED,
    HEALTH_HEALTHY,
    HEALTH_UNKNOWN,
    Recommendation,
    RecommendationEngine,
    RecommendationPriority,
    RecommendationType,
    SubsystemInfo,
    SubsystemRegistry,
    UpdateCoordinator,
    UpdateRecord,
    MaintenanceWindow,
)
from persistence_manager import PersistenceManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    """A real PersistenceManager writing to a temp directory."""
    return PersistenceManager(persistence_dir=str(tmp_path / ".murphy_persistence"))


@pytest.fixture
def rec_engine(pm):
    return RecommendationEngine(persistence_manager=pm)


@pytest.fixture
def registry(pm, tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    # Create a couple of fake modules
    (src_dir / "alpha.py").write_text("# alpha module\n")
    (src_dir / "beta.py").write_text("# beta module\n")
    pkg = src_dir / "gamma_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# gamma package\n")
    return SubsystemRegistry(src_root=str(src_dir), persistence_manager=pm)


@pytest.fixture
def coordinator(registry, rec_engine, pm):
    return UpdateCoordinator(
        registry=registry,
        recommendation_engine=rec_engine,
        persistence_manager=pm,
    )


# ---------------------------------------------------------------------------
# RecommendationEngine tests
# ---------------------------------------------------------------------------

class TestRecommendationEngine:
    def test_generate_maintenance_recommendations_no_deps(self, rec_engine):
        recs = rec_engine.generate_maintenance_recommendations("self_fix_loop")
        assert len(recs) >= 1
        assert all(r.recommendation_type == RecommendationType.MAINTENANCE for r in recs)
        assert all(r.subsystem == "self_fix_loop" for r in recs)

    def test_generate_recommendations_returns_multiple_types(self, rec_engine):
        recs = rec_engine.generate_recommendations("self_fix_loop")
        types = {r.recommendation_type for r in recs}
        # Should produce at least MAINTENANCE, PERFORMANCE, and ARCHITECTURE
        assert RecommendationType.MAINTENANCE in types
        assert RecommendationType.PERFORMANCE in types
        assert RecommendationType.ARCHITECTURE in types

    def test_generate_bug_response_recommendations(self, rec_engine):
        bug_report = {
            "top_patterns": [
                {
                    "pattern_id": "p-001",
                    "component": "auth",
                    "severity": "high",
                    "representative_message": "Token expired",
                    "occurrences": 12,
                    "suggested_fix": "Refresh token on expiry",
                }
            ]
        }
        recs = rec_engine.generate_bug_response_recommendations(bug_report)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.recommendation_type == RecommendationType.BUG_RESPONSE
        assert rec.priority == RecommendationPriority.HIGH
        assert rec.subsystem == "auth"

    def test_generate_bug_response_empty_report(self, rec_engine):
        recs = rec_engine.generate_bug_response_recommendations({"top_patterns": []})
        assert recs == []

    def test_get_recommendations_by_type(self, rec_engine):
        rec_engine.generate_recommendations("subsystem_a")
        maintenance_recs = rec_engine.get_recommendations_by_type(RecommendationType.MAINTENANCE)
        assert all(r.recommendation_type == RecommendationType.MAINTENANCE for r in maintenance_recs)

    def test_get_recommendations_by_subsystem(self, rec_engine):
        rec_engine.generate_recommendations("subsystem_x")
        rec_engine.generate_recommendations("subsystem_y")
        x_recs = rec_engine.get_recommendations_by_subsystem("subsystem_x")
        y_recs = rec_engine.get_recommendations_by_subsystem("subsystem_y")
        assert all(r.subsystem == "subsystem_x" for r in x_recs)
        assert all(r.subsystem == "subsystem_y" for r in y_recs)
        assert len(x_recs) > 0
        assert len(y_recs) > 0

    def test_approve_recommendation(self, rec_engine):
        recs = rec_engine.generate_maintenance_recommendations("test_sub")
        rec_id = recs[0].id
        assert rec_engine.approve_recommendation(rec_id) is True
        approved = [r for r in rec_engine.get_all_recommendations() if r.id == rec_id]
        assert approved[0].status == "approved"

    def test_approve_nonexistent_recommendation(self, rec_engine):
        assert rec_engine.approve_recommendation("nonexistent-id") is False

    def test_reject_recommendation(self, rec_engine):
        recs = rec_engine.generate_maintenance_recommendations("test_sub")
        rec_id = recs[0].id
        assert rec_engine.reject_recommendation(rec_id, "Not needed") is True
        rejected = [r for r in rec_engine.get_all_recommendations() if r.id == rec_id]
        assert rejected[0].status == "rejected"
        assert "rejection_reason" in rejected[0].source_analysis

    def test_apply_recommendation(self, rec_engine):
        recs = rec_engine.generate_maintenance_recommendations("test_sub")
        rec_id = recs[0].id
        result = rec_engine.apply_recommendation(rec_id)
        assert result["success"] is True
        assert result["status"] == "applied"

    def test_apply_nonexistent_recommendation(self, rec_engine):
        result = rec_engine.apply_recommendation("nonexistent-id")
        assert result["success"] is False
        assert result["status"] == "not_found"

    def test_get_status(self, rec_engine):
        rec_engine.generate_recommendations("some_sub")
        status = rec_engine.get_status()
        assert "total_recommendations" in status
        assert "by_status" in status
        assert "by_type" in status
        assert status["total_recommendations"] > 0

    def test_all_recommendation_types_covered(self, rec_engine):
        """Each RecommendationType must be representable."""
        for rt in RecommendationType:
            rec = Recommendation(
                id=str(uuid.uuid4()),
                subsystem="test",
                recommendation_type=rt,
                priority=RecommendationPriority.LOW,
                title="Test",
                description="Test",
                rationale="Test",
                proposed_actions=[],
                estimated_impact={},
                auto_applicable=True,
                requires_founder_approval=False,
                source_analysis={},
                created_at=datetime.now(timezone.utc),
            )
            assert rec.recommendation_type == rt

    def test_all_recommendation_priorities_covered(self):
        """Each RecommendationPriority value must be constructable."""
        for rp in RecommendationPriority:
            assert rp.value  # non-empty string

    def test_recommendation_serialisation_round_trip(self, rec_engine):
        recs = rec_engine.generate_maintenance_recommendations("serde_test")
        original = recs[0]
        d = original.to_dict()
        restored = Recommendation.from_dict(d)
        assert restored.id == original.id
        assert restored.subsystem == original.subsystem
        assert restored.recommendation_type == original.recommendation_type
        assert restored.priority == original.priority
        assert restored.status == original.status

    def test_sdk_update_recommendations_no_audit_engine(self, rec_engine):
        # With no dependency audit engine, should return empty list
        recs = rec_engine.generate_sdk_update_recommendations()
        assert isinstance(recs, list)

    def test_sdk_update_recommendations_with_audit_engine(self, pm):
        """Wire in a mock DependencyAuditEngine with one finding."""
        from dependency_audit_engine import DependencyAuditEngine, DependencyAuditReport

        audit = DependencyAuditEngine()
        # Register a dep and an advisory so the audit cycle produces a finding
        audit.register_dependency(
            name="requests",
            version="2.25.0",
            ecosystem="pip",
        )
        audit.ingest_advisory(
            cve_id="CVE-2023-XXXX",
            package_name="requests",
            affected_versions=">=2.0.0,<2.28.0",
            severity="high",
            description="Arbitrary code execution via crafted URL",
            fixed_version="2.28.0",
        )
        engine = RecommendationEngine(dependency_audit=audit, persistence_manager=pm)
        recs = engine.generate_sdk_update_recommendations()
        assert len(recs) >= 1
        assert all(r.recommendation_type == RecommendationType.SDK_UPDATE for r in recs)

    def test_maintenance_recommendations_with_improvement_engine(self, pm):
        """Wire in a real SelfImprovementEngine with a proposal."""
        from self_improvement_engine import SelfImprovementEngine, ExecutionOutcome, OutcomeType

        ie = SelfImprovementEngine()
        # Record failures to trigger proposal generation
        for _ in range(5):
            ie.record_outcome(
                ExecutionOutcome(
                    task_id=str(uuid.uuid4()),
                    session_id="s1",
                    outcome=OutcomeType.FAILURE,
                    corrections=["fix routing"],
                )
            )
        ie.generate_proposals()

        engine = RecommendationEngine(improvement_engine=ie, persistence_manager=pm)
        recs = engine.generate_maintenance_recommendations("self_improvement_engine")
        assert isinstance(recs, list)
        assert len(recs) >= 1


# ---------------------------------------------------------------------------
# SubsystemRegistry tests
# ---------------------------------------------------------------------------

class TestSubsystemRegistry:
    def test_register_and_get_subsystem(self, registry):
        info = SubsystemInfo(name="my_module", module_path="src/my_module.py")
        registry.register_subsystem(info)
        retrieved = registry.get_subsystem("my_module")
        assert retrieved is not None
        assert retrieved.name == "my_module"

    def test_get_nonexistent_subsystem(self, registry):
        assert registry.get_subsystem("does_not_exist") is None

    def test_discover_subsystems(self, registry):
        subsystems = registry.discover_subsystems()
        names = {s.name for s in subsystems}
        assert "alpha" in names
        assert "beta" in names
        assert "gamma_pkg" in names

    def test_discover_excludes_init(self, registry):
        subsystems = registry.discover_subsystems()
        names = {s.name for s in subsystems}
        assert "__init__" not in names

    def test_get_all_subsystems(self, registry):
        registry.discover_subsystems()
        all_subs = registry.get_all_subsystems()
        assert len(all_subs) >= 3  # alpha, beta, gamma_pkg

    def test_update_health_status(self, registry):
        registry.discover_subsystems()
        all_subs = registry.get_all_subsystems()
        name = all_subs[0].name
        registry.update_health_status(name, HEALTH_HEALTHY)
        assert registry.get_subsystem(name).health_status == HEALTH_HEALTHY

    def test_update_health_status_invalid(self, registry):
        registry.discover_subsystems()
        name = registry.get_all_subsystems()[0].name
        with pytest.raises(ValueError):
            registry.update_health_status(name, "invalid_status")

    def test_update_health_status_unknown_subsystem(self, registry):
        # Should log a warning but not raise
        registry.update_health_status("nonexistent", HEALTH_HEALTHY)

    def test_get_subsystems_needing_attention_degraded(self, registry):
        info = SubsystemInfo(name="degraded_mod", module_path="src/d.py", health_status=HEALTH_DEGRADED)
        registry.register_subsystem(info)
        attention = registry.get_subsystems_needing_attention()
        assert any(s.name == "degraded_mod" for s in attention)

    def test_get_subsystems_needing_attention_pending_recs(self, registry):
        info = SubsystemInfo(name="pending_mod", module_path="src/p.py", pending_recommendations=3)
        registry.register_subsystem(info)
        attention = registry.get_subsystems_needing_attention()
        assert any(s.name == "pending_mod" for s in attention)

    def test_get_subsystems_needing_attention_healthy_no_recs(self, registry):
        info = SubsystemInfo(name="all_good", module_path="src/ag.py", health_status=HEALTH_HEALTHY)
        registry.register_subsystem(info)
        attention = registry.get_subsystems_needing_attention()
        assert not any(s.name == "all_good" for s in attention)

    def test_record_update(self, registry):
        info = SubsystemInfo(name="updated_mod", module_path="src/u.py")
        registry.register_subsystem(info)
        registry.record_update("updated_mod", {"version": "1.1.0", "reason": "patch"})
        sub = registry.get_subsystem("updated_mod")
        assert len(sub.update_history) == 1
        assert sub.last_updated is not None

    def test_subsystem_info_serialisation_round_trip(self):
        info = SubsystemInfo(
            name="test",
            module_path="src/test.py",
            version="1.0.0",
            health_status=HEALTH_HEALTHY,
            dependencies=["dep_a"],
            pending_recommendations=2,
        )
        d = info.to_dict()
        restored = SubsystemInfo.from_dict(d)
        assert restored.name == info.name
        assert restored.version == info.version
        assert restored.health_status == info.health_status
        assert restored.dependencies == info.dependencies
        assert restored.pending_recommendations == info.pending_recommendations

    def test_persistence_save_load(self, registry, pm):
        info = SubsystemInfo(name="persist_me", module_path="src/pm.py", health_status=HEALTH_HEALTHY)
        registry.register_subsystem(info)
        assert registry.save_state() is True

        # Load into a fresh registry using same PM
        new_registry = SubsystemRegistry(persistence_manager=pm)
        assert new_registry.load_state() is True
        loaded = new_registry.get_subsystem("persist_me")
        assert loaded is not None
        assert loaded.health_status == HEALTH_HEALTHY


# ---------------------------------------------------------------------------
# UpdateCoordinator tests
# ---------------------------------------------------------------------------

class TestUpdateCoordinator:
    def test_plan_update_cycle_empty_registry(self, pm):
        coord = UpdateCoordinator(
            registry=SubsystemRegistry(persistence_manager=pm),
            persistence_manager=pm,
        )
        plan = coord.plan_update_cycle()
        assert "plan_id" in plan
        assert "ordered_subsystems" in plan
        assert "steps" in plan
        assert "created_at" in plan

    def test_plan_update_cycle_with_subsystems(self, coordinator, registry):
        registry.discover_subsystems()
        plan = coordinator.plan_update_cycle()
        assert len(plan["ordered_subsystems"]) >= 3

    def test_execute_update_plan(self, coordinator, registry):
        registry.discover_subsystems()
        plan = coordinator.plan_update_cycle()
        result = coordinator.execute_update_plan(plan)
        assert "update_id" in result
        assert "results" in result
        assert "success" in result
        assert "completed_at" in result

    def test_check_update_prerequisites_unregistered(self, coordinator):
        prereq = coordinator.check_update_prerequisites("nonexistent_subsystem")
        assert prereq["prerequisites_met"] is False
        assert len(prereq["details"]) > 0

    def test_check_update_prerequisites_failed_subsystem(self, coordinator, registry):
        info = SubsystemInfo(name="broken", module_path="src/b.py", health_status=HEALTH_FAILED)
        registry.register_subsystem(info)
        prereq = coordinator.check_update_prerequisites("broken")
        assert prereq["prerequisites_met"] is False

    def test_check_update_prerequisites_healthy(self, coordinator, registry):
        info = SubsystemInfo(name="green", module_path="src/g.py", health_status=HEALTH_HEALTHY)
        registry.register_subsystem(info)
        prereq = coordinator.check_update_prerequisites("green")
        assert prereq["prerequisites_met"] is True

    def test_schedule_maintenance(self, coordinator):
        window = {
            "scheduled_start": "2030-01-01T02:00:00+00:00",
            "scheduled_end": "2030-01-01T04:00:00+00:00",
            "description": "Planned DB migration",
        }
        window_id = coordinator.schedule_maintenance("self_fix_loop", window)
        assert window_id is not None
        status = coordinator.get_update_status()
        window_ids = [w["window_id"] for w in status["maintenance_windows"]]
        assert window_id in window_ids

    def test_schedule_maintenance_invalid_dates(self, coordinator):
        with pytest.raises(ValueError):
            coordinator.schedule_maintenance("sub", {"scheduled_start": "bad", "scheduled_end": "bad"})

    def test_rollback_update(self, coordinator, registry):
        registry.discover_subsystems()
        plan = coordinator.plan_update_cycle()
        result = coordinator.execute_update_plan(plan)
        update_id = result["update_id"]
        assert coordinator.rollback_update(update_id) is True
        status = coordinator.get_update_status()
        assert status["by_status"].get("rolled_back", 0) >= 1

    def test_rollback_nonexistent_update(self, coordinator):
        assert coordinator.rollback_update("nonexistent-id") is False

    def test_rollback_twice_fails(self, coordinator, registry):
        registry.discover_subsystems()
        plan = coordinator.plan_update_cycle()
        result = coordinator.execute_update_plan(plan)
        update_id = result["update_id"]
        assert coordinator.rollback_update(update_id) is True
        assert coordinator.rollback_update(update_id) is False

    def test_get_update_status(self, coordinator, registry):
        registry.discover_subsystems()
        plan = coordinator.plan_update_cycle()
        coordinator.execute_update_plan(plan)
        status = coordinator.get_update_status()
        assert "total_updates" in status
        assert status["total_updates"] >= 1

    def test_dependency_ordering(self, pm):
        """Subsystems with dependencies come after their deps in the plan."""
        from founder_update_engine.subsystem_registry import SubsystemRegistry as Reg, SubsystemInfo as SI

        reg = Reg(persistence_manager=pm)
        reg.register_subsystem(SI(name="base", module_path="src/base.py"))
        reg.register_subsystem(SI(name="mid", module_path="src/mid.py", dependencies=["base"]))
        reg.register_subsystem(SI(name="top", module_path="src/top.py", dependencies=["mid"]))

        coord = UpdateCoordinator(registry=reg, persistence_manager=pm)
        plan = coord.plan_update_cycle()
        order = plan["ordered_subsystems"]
        assert order.index("base") < order.index("mid")
        assert order.index("mid") < order.index("top")


# ---------------------------------------------------------------------------
# Persistence round-trip tests
# ---------------------------------------------------------------------------

class TestPersistenceRoundTrip:
    def test_recommendation_engine_persistence(self, pm):
        engine1 = RecommendationEngine(persistence_manager=pm)
        recs = engine1.generate_maintenance_recommendations("persist_sub")
        rec_id = recs[0].id
        engine1.approve_recommendation(rec_id)

        # New engine loads same PM
        engine2 = RecommendationEngine(persistence_manager=pm)
        loaded = engine2.get_recommendations_by_subsystem("persist_sub")
        approved = [r for r in loaded if r.id == rec_id]
        assert len(approved) == 1
        assert approved[0].status == "approved"

    def test_subsystem_registry_persistence(self, pm):
        reg1 = SubsystemRegistry(persistence_manager=pm)
        info = SubsystemInfo(name="saved_sub", module_path="src/s.py", version="2.0.0")
        reg1.register_subsystem(info)
        reg1.save_state()

        reg2 = SubsystemRegistry(persistence_manager=pm)
        reg2.load_state()
        loaded = reg2.get_subsystem("saved_sub")
        assert loaded is not None
        assert loaded.version == "2.0.0"

    def test_update_coordinator_persistence(self, pm, registry):
        coord1 = UpdateCoordinator(registry=registry, persistence_manager=pm)
        registry.discover_subsystems()
        plan = coord1.plan_update_cycle()
        result = coord1.execute_update_plan(plan)
        update_id = result["update_id"]

        coord2 = UpdateCoordinator(registry=registry, persistence_manager=pm)
        status = coord2.get_update_status()
        assert status["total_updates"] >= 1

    def test_maintenance_window_persistence(self, pm, registry):
        coord1 = UpdateCoordinator(registry=registry, persistence_manager=pm)
        window_id = coord1.schedule_maintenance(
            "test_sub",
            {
                "scheduled_start": "2030-06-01T01:00:00+00:00",
                "scheduled_end": "2030-06-01T03:00:00+00:00",
                "description": "Persisted window",
            },
        )
        coord2 = UpdateCoordinator(registry=registry, persistence_manager=pm)
        status = coord2.get_update_status()
        window_ids = [w["window_id"] for w in status["maintenance_windows"]]
        assert window_id in window_ids


# ---------------------------------------------------------------------------
# Priority and type filtering tests
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_priority_critical(self, rec_engine):
        recs = rec_engine.generate_bug_response_recommendations(
            {
                "top_patterns": [
                    {
                        "pattern_id": "crit-001",
                        "component": "core",
                        "severity": "critical",
                        "representative_message": "Core crashed",
                        "occurrences": 100,
                        "suggested_fix": "Emergency patch",
                    }
                ]
            }
        )
        critical = [r for r in recs if r.priority == RecommendationPriority.CRITICAL]
        assert len(critical) >= 1
        assert all(r.requires_founder_approval for r in critical)

    def test_filter_by_type_returns_correct_subset(self, rec_engine):
        rec_engine.generate_recommendations("filter_test")
        for rt in (RecommendationType.MAINTENANCE, RecommendationType.PERFORMANCE, RecommendationType.ARCHITECTURE):
            typed = rec_engine.get_recommendations_by_type(rt)
            assert all(r.recommendation_type == rt for r in typed)

    def test_auto_applicable_vs_requires_approval(self, rec_engine):
        recs = rec_engine.generate_recommendations("auto_test")
        # At least the INFORMATIONAL MAINTENANCE rec should be auto_applicable
        auto = [r for r in recs if r.auto_applicable]
        assert len(auto) >= 1

    def test_sdk_severity_to_priority_mapping(self, pm):
        """Critical advisories produce CRITICAL priority recommendations."""
        from dependency_audit_engine import DependencyAuditEngine

        audit = DependencyAuditEngine()
        audit.register_dependency(name="flask", version="1.0.0", ecosystem="pip")
        audit.ingest_advisory(
            cve_id="CVE-CRITICAL",
            package_name="flask",
            affected_versions=">=1.0.0,<2.0.0",
            severity="critical",
            description="Critical RCE",
            fixed_version="2.0.0",
        )
        engine = RecommendationEngine(dependency_audit=audit, persistence_manager=pm)
        recs = engine.generate_sdk_update_recommendations()
        critical_recs = [r for r in recs if r.priority == RecommendationPriority.CRITICAL]
        assert len(critical_recs) >= 1
        assert all(r.requires_founder_approval for r in critical_recs)


# ---------------------------------------------------------------------------
# Thread safety tests
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_generate_recommendations(self, rec_engine):
        errors: list = []

        def worker(subsystem: str) -> None:
            try:
                rec_engine.generate_recommendations(subsystem)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"sub_{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_registry_updates(self, registry):
        errors: list = []

        def worker(i: int) -> None:
            try:
                info = SubsystemInfo(name=f"concurrent_{i}", module_path=f"src/c{i}.py")
                registry.register_subsystem(info)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        all_names = {s.name for s in registry.get_all_subsystems()}
        for i in range(10):
            assert f"concurrent_{i}" in all_names


# ===========================================================================
# PR 2 — SdkUpdateScanner & AutoUpdateApplicator tests
# ===========================================================================

from founder_update_engine import (
    AutoUpdateApplicator,
    ApplicationCycle,
    ApplicationOutcome,
    ApplicationRecord,
    PackageScanRecord,
    SdkScanReport,
    SdkUpdateScanner,
)


# ---------------------------------------------------------------------------
# Shared PR-2 fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scanner(rec_engine, pm):
    return SdkUpdateScanner(
        recommendation_engine=rec_engine,
        persistence_manager=pm,
    )


@pytest.fixture
def scanner_with_root(rec_engine, pm, tmp_path):
    """Scanner pointed at a tmp project root containing fake requirements files."""
    req = tmp_path / "requirements.txt"
    req.write_text(
        "requests>=2.28.0\n"
        "flask>=3.0.0\n"
        "pydantic>=2.0.0\n"
        "# a comment\n"
        "numpy>=1.24.0\n",
        encoding="utf-8",
    )
    req2 = tmp_path / "requirements_core.txt"
    req2.write_text(
        "fastapi>=0.100.0\n"
        "uvicorn[standard]>=0.22.0\n",
        encoding="utf-8",
    )
    return SdkUpdateScanner(
        recommendation_engine=rec_engine,
        persistence_manager=pm,
        project_root=str(tmp_path),
    )


@pytest.fixture
def applicator(rec_engine, registry, coordinator, pm):
    return AutoUpdateApplicator(
        recommendation_engine=rec_engine,
        registry=registry,
        coordinator=coordinator,
        persistence_manager=pm,
        max_per_cycle=10,
    )


# ---------------------------------------------------------------------------
# SdkUpdateScanner — known-version registry
# ---------------------------------------------------------------------------

class TestSdkUpdateScannerVersionRegistry:
    def test_register_and_get_known_version(self, scanner):
        scanner.register_known_version("requests", "2.32.0")
        assert scanner.get_known_version("requests") == "2.32.0"

    def test_known_version_case_insensitive(self, scanner):
        scanner.register_known_version("Requests", "2.32.0")
        assert scanner.get_known_version("requests") == "2.32.0"
        assert scanner.get_known_version("REQUESTS") == "2.32.0"

    def test_get_unknown_version_returns_none(self, scanner):
        assert scanner.get_known_version("nonexistent_pkg") is None

    def test_register_overwrites_old_version(self, scanner):
        scanner.register_known_version("flask", "2.0.0")
        scanner.register_known_version("flask", "3.1.0")
        assert scanner.get_known_version("flask") == "3.1.0"


# ---------------------------------------------------------------------------
# SdkUpdateScanner — requirements file parsing
# ---------------------------------------------------------------------------

class TestSdkUpdateScannerParsing:
    def test_parse_requirements_file(self, scanner, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text(
            "requests>=2.28.0\n"
            "flask>=3.0.0  # with comment\n"
            "pydantic==2.1.0\n"
            "numpy  # no version — should be skipped\n"
            "-r other.txt\n",
            encoding="utf-8",
        )
        parsed = scanner._parse_requirements_file(str(req))
        names = [p[0] for p in parsed]
        assert "requests" in names
        assert "flask" in names
        assert "pydantic" in names
        # bare names and -r lines must be excluded
        assert "numpy" not in names
        assert len([p for p in parsed if p[0] == "requests"]) == 1

    def test_parse_handles_extras(self, scanner, tmp_path):
        req = tmp_path / "req.txt"
        req.write_text("uvicorn[standard]>=0.22.0\n", encoding="utf-8")
        parsed = scanner._parse_requirements_file(str(req))
        assert parsed[0][0] == "uvicorn"

    def test_parse_missing_file(self, scanner):
        result = scanner._parse_requirements_file("/nonexistent/requirements.txt")
        assert result == []

    def test_discover_requirements_files(self, scanner_with_root):
        from pathlib import Path
        files = scanner_with_root._discover_requirements_files()
        filenames = [Path(f).name for f in files]
        assert "requirements.txt" in filenames
        assert "requirements_core.txt" in filenames

    def test_discover_no_root(self, scanner):
        # scanner has no project_root and can't resolve one from __file__ in tests
        # — should not raise, just return []
        result = scanner._discover_requirements_files()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# SdkUpdateScanner — scan logic
# ---------------------------------------------------------------------------

class TestSdkUpdateScannerScan:
    def test_run_scan_no_root_returns_empty_report(self, rec_engine, pm):
        # Use an explicit nonexistent path so no requirements files are found
        scanner = SdkUpdateScanner(
            recommendation_engine=rec_engine,
            persistence_manager=pm,
            project_root="/nonexistent/path/does/not/exist",
        )
        report = scanner.run_scan()
        assert isinstance(report, SdkScanReport)
        assert report.packages_scanned == 0
        assert report.updates_available == 0

    def test_run_scan_detects_update(self, scanner_with_root):
        scanner_with_root.register_known_version("requests", "2.32.3")
        report = scanner_with_root.run_scan()
        assert report.packages_scanned >= 1
        assert report.updates_available >= 1
        names = [r.name for r in report.scan_records if r.update_available]
        assert "requests" in names

    def test_run_scan_no_update_when_already_latest(self, scanner_with_root):
        # flask is declared as >=3.0.0 — tell scanner 3.0.0 is latest
        scanner_with_root.register_known_version("flask", "3.0.0")
        report = scanner_with_root.run_scan()
        flask_records = [r for r in report.scan_records if r.name == "flask"]
        assert len(flask_records) >= 1
        assert not flask_records[0].update_available

    def test_run_scan_classifies_patch_update(self, scanner_with_root):
        scanner_with_root.register_known_version("pydantic", "2.0.1")
        report = scanner_with_root.run_scan()
        pydantic_rec = next((r for r in report.scan_records if r.name == "pydantic"), None)
        assert pydantic_rec is not None
        assert pydantic_rec.update_type == "patch"

    def test_run_scan_classifies_minor_update(self, scanner_with_root):
        scanner_with_root.register_known_version("flask", "3.1.0")
        report = scanner_with_root.run_scan()
        flask_rec = next((r for r in report.scan_records if r.name == "flask"), None)
        assert flask_rec is not None
        assert flask_rec.update_type == "minor"

    def test_run_scan_classifies_major_update(self, scanner_with_root):
        scanner_with_root.register_known_version("numpy", "2.0.0")
        report = scanner_with_root.run_scan()
        numpy_rec = next((r for r in report.scan_records if r.name == "numpy"), None)
        assert numpy_rec is not None
        assert numpy_rec.update_type == "major"

    def test_run_scan_generates_recommendations(self, scanner_with_root, rec_engine):
        scanner_with_root.register_known_version("requests", "2.32.3")
        report = scanner_with_root.run_scan()
        assert report.recommendations_generated >= 1
        # At least SDK_UPDATE and AUTO_UPDATE recs should exist for a patch bump
        from founder_update_engine import RecommendationType
        all_recs = rec_engine.get_all_recommendations()
        types = {r.recommendation_type for r in all_recs}
        assert RecommendationType.SDK_UPDATE in types or RecommendationType.AUTO_UPDATE in types

    def test_run_scan_generates_security_rec_for_vulnerability(self, rec_engine, pm, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.25.0\n", encoding="utf-8")
        from dependency_audit_engine import DependencyAuditEngine
        audit = DependencyAuditEngine()
        audit.ingest_advisory(
            cve_id="CVE-2023-TEST",
            package_name="requests",
            affected_versions=">=2.0.0,<2.30.0",
            severity="high",
            description="Test vulnerability",
            fixed_version="2.30.0",
        )
        scanner = SdkUpdateScanner(
            recommendation_engine=rec_engine,
            dependency_audit=audit,
            project_root=str(tmp_path),
            persistence_manager=pm,
        )
        report = scanner.run_scan()
        assert report.vulnerable_packages >= 1
        from founder_update_engine import RecommendationType
        security_recs = rec_engine.get_recommendations_by_type(RecommendationType.SECURITY)
        assert len(security_recs) >= 1

    def test_scan_history_is_recorded(self, scanner_with_root):
        scanner_with_root.run_scan()
        history = scanner_with_root.get_scan_history()
        assert len(history) >= 1
        assert "scan_id" in history[0]

    def test_get_status(self, scanner_with_root):
        scanner_with_root.run_scan()
        status = scanner_with_root.get_status()
        assert "total_scans" in status
        assert status["total_scans"] >= 1

    def test_scan_persistence_round_trip(self, pm, tmp_path, rec_engine):
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.28.0\n", encoding="utf-8")
        scanner1 = SdkUpdateScanner(
            recommendation_engine=rec_engine,
            project_root=str(tmp_path),
            persistence_manager=pm,
        )
        scanner1.register_known_version("requests", "2.32.0")
        scanner1.run_scan()

        scanner2 = SdkUpdateScanner(persistence_manager=pm)
        assert scanner2.get_known_version("requests") == "2.32.0"
        assert len(scanner2.get_scan_history()) >= 1


# ---------------------------------------------------------------------------
# SdkUpdateScanner — semver helpers
# ---------------------------------------------------------------------------

class TestSdkScannerSemverHelpers:
    def test_is_patch_bump(self):
        from founder_update_engine.sdk_update_scanner import _is_patch_bump
        assert _is_patch_bump("2.0.0", "2.0.1") is True
        assert _is_patch_bump("2.0.0", "2.1.0") is False
        assert _is_patch_bump("2.0.0", "3.0.0") is False

    def test_is_minor_bump(self):
        from founder_update_engine.sdk_update_scanner import _is_minor_bump
        assert _is_minor_bump("2.0.0", "2.1.0") is True
        assert _is_minor_bump("2.0.0", "2.0.1") is False
        assert _is_minor_bump("2.0.0", "3.0.0") is False


# ---------------------------------------------------------------------------
# AutoUpdateApplicator — dry-run
# ---------------------------------------------------------------------------

class TestAutoUpdateApplicatorDryRun:
    def _seed_auto_update_rec(self, rec_engine, subsystem="auto_sub"):
        """Seed a single AUTO_UPDATE recommendation into rec_engine."""
        from founder_update_engine.recommendation_engine import (
            Recommendation,
            RecommendationType,
            RecommendationPriority,
        )
        import uuid as _uuid
        rec = Recommendation(
            id=str(_uuid.uuid4()),
            subsystem=subsystem,
            recommendation_type=RecommendationType.AUTO_UPDATE,
            priority=RecommendationPriority.LOW,
            title=f"Auto-update: test_pkg 1.0.0 → 1.0.1",
            description="Patch update available.",
            rationale="Semver patch.",
            proposed_actions=[{"action": "auto_update_package", "package": "test_pkg"}],
            estimated_impact={"risk": "low", "effort": "none", "benefit": "maintenance"},
            auto_applicable=True,
            requires_founder_approval=False,
            source_analysis={"engine": "test"},
            created_at=datetime.now(timezone.utc),
        )
        with rec_engine._lock:
            rec_engine._recommendations[rec.id] = rec
        return rec

    def test_dry_run_does_not_change_status(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="auto_sub", module_path="src/a.py", health_status=HEALTH_HEALTHY)
        )
        rec = self._seed_auto_update_rec(rec_engine)
        cycle = applicator.run_cycle(dry_run=True)
        assert cycle.dry_run is True
        # Status must remain pending since it was a dry run
        with rec_engine._lock:
            r = rec_engine._recommendations[rec.id]
        assert r.status == "pending"

    def test_dry_run_reports_would_apply(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="auto_sub", module_path="src/a.py", health_status=HEALTH_HEALTHY)
        )
        self._seed_auto_update_rec(rec_engine)
        cycle = applicator.run_cycle(dry_run=True)
        dry_records = [r for r in cycle.records if r.outcome == ApplicationOutcome.SKIPPED_DRY_RUN]
        assert len(dry_records) >= 1

    def test_dry_run_total_candidates(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="auto_sub", module_path="src/a.py", health_status=HEALTH_HEALTHY)
        )
        for _ in range(3):
            self._seed_auto_update_rec(rec_engine)
        cycle = applicator.run_cycle(dry_run=True)
        assert cycle.total_candidates >= 3


# ---------------------------------------------------------------------------
# AutoUpdateApplicator — live application
# ---------------------------------------------------------------------------

class TestAutoUpdateApplicatorLive:
    def _seed_auto_update_rec(self, rec_engine, subsystem="live_sub"):
        from founder_update_engine.recommendation_engine import (
            Recommendation,
            RecommendationType,
            RecommendationPriority,
        )
        import uuid as _uuid
        rec = Recommendation(
            id=str(_uuid.uuid4()),
            subsystem=subsystem,
            recommendation_type=RecommendationType.AUTO_UPDATE,
            priority=RecommendationPriority.LOW,
            title="Auto-update: pkg 1.0.0 → 1.0.1",
            description="Patch.",
            rationale="Patch.",
            proposed_actions=[],
            estimated_impact={},
            auto_applicable=True,
            requires_founder_approval=False,
            source_analysis={},
            created_at=datetime.now(timezone.utc),
        )
        with rec_engine._lock:
            rec_engine._recommendations[rec.id] = rec
        return rec

    def test_live_apply_marks_recommendation_applied(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="live_sub", module_path="src/l.py", health_status=HEALTH_HEALTHY)
        )
        rec = self._seed_auto_update_rec(rec_engine)
        cycle = applicator.run_cycle(dry_run=False)
        applied_records = [r for r in cycle.records if r.outcome == ApplicationOutcome.APPLIED]
        assert len(applied_records) >= 1
        with rec_engine._lock:
            r = rec_engine._recommendations[rec.id]
        assert r.status == "applied"

    def test_live_apply_records_update_history(self, applicator, rec_engine, registry):
        info = SubsystemInfo(name="live_sub", module_path="src/l.py", health_status=HEALTH_HEALTHY)
        registry.register_subsystem(info)
        self._seed_auto_update_rec(rec_engine)
        applicator.run_cycle(dry_run=False)
        sub = registry.get_subsystem("live_sub")
        assert len(sub.update_history) >= 1
        assert sub.update_history[-1]["type"] == "auto_update"

    def test_failed_subsystem_is_skipped(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="live_sub", module_path="src/l.py", health_status=HEALTH_FAILED)
        )
        self._seed_auto_update_rec(rec_engine)
        cycle = applicator.run_cycle(dry_run=False)
        skipped = [r for r in cycle.records if r.outcome == ApplicationOutcome.SKIPPED_PREREQUISITES]
        assert len(skipped) >= 1

    def test_non_auto_applicable_rec_is_skipped(self, applicator, rec_engine, registry):
        from founder_update_engine.recommendation_engine import (
            Recommendation,
            RecommendationType,
            RecommendationPriority,
        )
        import uuid as _uuid
        registry.register_subsystem(
            SubsystemInfo(name="manual_sub", module_path="src/m.py", health_status=HEALTH_HEALTHY)
        )
        rec = Recommendation(
            id=str(_uuid.uuid4()),
            subsystem="manual_sub",
            recommendation_type=RecommendationType.AUTO_UPDATE,
            priority=RecommendationPriority.LOW,
            title="Manual only",
            description="",
            rationale="",
            proposed_actions=[],
            estimated_impact={},
            auto_applicable=False,  # not auto-applicable
            requires_founder_approval=True,
            source_analysis={},
            created_at=datetime.now(timezone.utc),
        )
        with rec_engine._lock:
            rec_engine._recommendations[rec.id] = rec
        cycle = applicator.run_cycle(dry_run=False)
        skipped = [r for r in cycle.records if r.outcome == ApplicationOutcome.SKIPPED_NOT_AUTO_APPLICABLE]
        assert len(skipped) >= 1

    def test_already_applied_rec_is_skipped(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="live_sub", module_path="src/l.py", health_status=HEALTH_HEALTHY)
        )
        rec = self._seed_auto_update_rec(rec_engine)
        # First cycle applies it
        applicator.run_cycle(dry_run=False)
        # Second cycle should skip it
        cycle2 = applicator.run_cycle(dry_run=False)
        already = [r for r in cycle2.records if r.outcome == ApplicationOutcome.SKIPPED_ALREADY_APPLIED]
        assert len(already) >= 1

    def test_rate_limit_respected(self, rec_engine, registry, coordinator, pm):
        applicator = AutoUpdateApplicator(
            recommendation_engine=rec_engine,
            registry=registry,
            coordinator=coordinator,
            persistence_manager=pm,
            max_per_cycle=2,
        )
        registry.register_subsystem(
            SubsystemInfo(name="live_sub", module_path="src/l.py", health_status=HEALTH_HEALTHY)
        )
        for _ in range(5):
            from founder_update_engine.recommendation_engine import (
                Recommendation, RecommendationType, RecommendationPriority,
            )
            import uuid as _uuid
            r = Recommendation(
                id=str(_uuid.uuid4()),
                subsystem="live_sub",
                recommendation_type=RecommendationType.AUTO_UPDATE,
                priority=RecommendationPriority.LOW,
                title="Rate limit test",
                description="",
                rationale="",
                proposed_actions=[],
                estimated_impact={},
                auto_applicable=True,
                requires_founder_approval=False,
                source_analysis={},
                created_at=datetime.now(timezone.utc),
            )
            with rec_engine._lock:
                rec_engine._recommendations[r.id] = r
        cycle = applicator.run_cycle(dry_run=False)
        assert cycle.applied <= 2
        rate_limited = [r for r in cycle.records if r.outcome == ApplicationOutcome.SKIPPED_RATE_LIMITED]
        assert len(rate_limited) >= 3


# ---------------------------------------------------------------------------
# AutoUpdateApplicator — apply_single
# ---------------------------------------------------------------------------

class TestAutoUpdateApplicatorSingle:
    def _seed(self, rec_engine, subsystem="single_sub"):
        from founder_update_engine.recommendation_engine import (
            Recommendation, RecommendationType, RecommendationPriority,
        )
        import uuid as _uuid
        rec = Recommendation(
            id=str(_uuid.uuid4()),
            subsystem=subsystem,
            recommendation_type=RecommendationType.AUTO_UPDATE,
            priority=RecommendationPriority.LOW,
            title="Single apply test",
            description="",
            rationale="",
            proposed_actions=[],
            estimated_impact={},
            auto_applicable=True,
            requires_founder_approval=False,
            source_analysis={},
            created_at=datetime.now(timezone.utc),
        )
        with rec_engine._lock:
            rec_engine._recommendations[rec.id] = rec
        return rec

    def test_apply_single_live(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="single_sub", module_path="src/s.py", health_status=HEALTH_HEALTHY)
        )
        rec = self._seed(rec_engine)
        record = applicator.apply_single(rec.id, dry_run=False)
        assert record.outcome == ApplicationOutcome.APPLIED

    def test_apply_single_dry_run(self, applicator, rec_engine, registry):
        registry.register_subsystem(
            SubsystemInfo(name="single_sub", module_path="src/s.py", health_status=HEALTH_HEALTHY)
        )
        rec = self._seed(rec_engine)
        record = applicator.apply_single(rec.id, dry_run=True)
        assert record.outcome == ApplicationOutcome.SKIPPED_DRY_RUN
        assert record.dry_run is True

    def test_apply_single_not_found(self, applicator):
        record = applicator.apply_single("nonexistent-id")
        assert record.outcome == ApplicationOutcome.FAILED


# ---------------------------------------------------------------------------
# AutoUpdateApplicator — persistence
# ---------------------------------------------------------------------------

class TestAutoUpdateApplicatorPersistence:
    def test_cycle_history_persists(self, rec_engine, registry, coordinator, pm):
        app1 = AutoUpdateApplicator(
            recommendation_engine=rec_engine,
            registry=registry,
            coordinator=coordinator,
            persistence_manager=pm,
        )
        registry.register_subsystem(
            SubsystemInfo(name="persist_sub", module_path="src/p.py", health_status=HEALTH_HEALTHY)
        )
        app1.run_cycle(dry_run=True)
        status1 = app1.get_status()

        app2 = AutoUpdateApplicator(persistence_manager=pm)
        status2 = app2.get_status()
        assert status2["total_cycles"] == status1["total_cycles"]

    def test_get_status_after_cycles(self, applicator):
        applicator.run_cycle(dry_run=True)
        applicator.run_cycle(dry_run=True)
        status = applicator.get_status()
        assert status["total_cycles"] == 2

    def test_application_outcome_enum_coverage(self):
        for outcome in ApplicationOutcome:
            assert outcome.value  # all have non-empty string values
