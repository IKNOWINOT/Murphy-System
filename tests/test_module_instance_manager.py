"""
Unit tests for src.module_instance_manager

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.module_instance_manager import (
    AuditEntry,
    ConfigurationSnapshot,
    InstanceState,
    ModuleInstance,
    ModuleInstanceManager,
    ResourceProfile,
    SpawnDecision,
    ViabilityChecker,
    ViabilityResult,
    integrate_with_module_registry,
    integrate_with_triage_rollcall,
)


# ── Enum values ──────────────────────────────────────────────────────────


class TestInstanceStateEnum:
    def test_has_all_seven_states(self):
        expected = {"spawning", "active", "idle", "busy", "error", "despawning", "despawned"}
        assert {s.value for s in InstanceState} == expected

    def test_count(self):
        assert len(InstanceState) == 7


class TestViabilityResultEnum:
    def test_has_all_six_values(self):
        expected = {
            "viable", "not_viable", "insufficient_resources",
            "dependency_missing", "already_spawned", "blacklisted",
        }
        assert {v.value for v in ViabilityResult} == expected

    def test_count(self):
        assert len(ViabilityResult) == 6


class TestSpawnDecisionEnum:
    def test_has_all_six_values(self):
        expected = {
            "approved", "denied_budget", "denied_depth",
            "denied_circuit", "denied_blacklist", "denied_dependency",
        }
        assert {d.value for d in SpawnDecision} == expected

    def test_count(self):
        assert len(SpawnDecision) == 6


# ── ResourceProfile ─────────────────────────────────────────────────────


class TestResourceProfile:
    def test_defaults(self):
        rp = ResourceProfile()
        assert rp.cpu_cores == 1.0
        assert rp.memory_mb == 512
        assert rp.max_concurrent == 5
        assert rp.timeout_seconds == 300
        assert rp.priority == 5

    def test_custom_values(self):
        rp = ResourceProfile(cpu_cores=4.0, memory_mb=2048, max_concurrent=10,
                             timeout_seconds=600, priority=8)
        assert rp.cpu_cores == 4.0
        assert rp.memory_mb == 2048

    def test_to_dict(self):
        rp = ResourceProfile(cpu_cores=2.0, memory_mb=1024)
        d = rp.to_dict()
        assert d["cpu_cores"] == 2.0
        assert d["memory_mb"] == 1024
        assert "max_concurrent" in d


# ── ModuleInstance ───────────────────────────────────────────────────────


class TestModuleInstance:
    def test_creation(self):
        inst = ModuleInstance(
            instance_id="abc123",
            module_type="worker",
            state=InstanceState.ACTIVE,
            spawned_at="2024-01-01T00:00:00+00:00",
            config={"key": "value"},
            resource_profile=ResourceProfile(),
            capabilities=["cap_a"],
        )
        assert inst.instance_id == "abc123"
        assert inst.module_type == "worker"
        assert inst.state == InstanceState.ACTIVE

    def test_to_dict(self):
        inst = ModuleInstance(
            instance_id="xyz",
            module_type="runner",
            state=InstanceState.IDLE,
            spawned_at="2024-01-01T00:00:00+00:00",
            config={},
            resource_profile=ResourceProfile(),
            capabilities=[],
        )
        d = inst.to_dict()
        assert d["instance_id"] == "xyz"
        assert d["state"] == "idle"
        assert isinstance(d["resource_profile"], dict)

    def test_state_transitions(self):
        inst = ModuleInstance(
            instance_id="t1",
            module_type="svc",
            state=InstanceState.SPAWNING,
            spawned_at="2024-01-01T00:00:00+00:00",
            config={},
            resource_profile=ResourceProfile(),
            capabilities=[],
        )
        assert inst.state == InstanceState.SPAWNING
        inst.state = InstanceState.ACTIVE
        assert inst.state == InstanceState.ACTIVE
        inst.state = InstanceState.DESPAWNED
        assert inst.state == InstanceState.DESPAWNED


# ── AuditEntry ───────────────────────────────────────────────────────────


class TestAuditEntry:
    def test_creation(self):
        entry = AuditEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            action="spawn",
            actor="admin",
            correlation_id="corr-1",
            instance_id="inst-1",
            module_type="worker",
        )
        assert entry.action == "spawn"
        assert entry.actor == "admin"

    def test_to_dict(self):
        entry = AuditEntry(
            timestamp="2024-01-01T00:00:00+00:00",
            action="despawn",
            actor="system",
            correlation_id="c2",
        )
        d = entry.to_dict()
        assert d["action"] == "despawn"
        assert d["instance_id"] is None


# ── ConfigurationSnapshot ────────────────────────────────────────────────


class TestConfigurationSnapshot:
    def test_creation(self):
        snap = ConfigurationSnapshot(
            snapshot_id="s1",
            instance_id="i1",
            timestamp="2024-01-01T00:00:00+00:00",
            config={"debug": True},
        )
        assert snap.snapshot_id == "s1"
        assert snap.config == {"debug": True}

    def test_to_dict(self):
        snap = ConfigurationSnapshot(
            snapshot_id="s2",
            instance_id="i2",
            timestamp="2024-01-01T00:00:00+00:00",
            config={"mode": "test"},
            previous_snapshot_id="s1",
        )
        d = snap.to_dict()
        assert d["previous_snapshot_id"] == "s1"
        assert d["config"] == {"mode": "test"}

    def test_linking(self):
        snap1 = ConfigurationSnapshot(
            snapshot_id="s1", instance_id="i1",
            timestamp="t1", config={"v": 1},
        )
        snap2 = ConfigurationSnapshot(
            snapshot_id="s2", instance_id="i1",
            timestamp="t2", config={"v": 2},
            previous_snapshot_id=snap1.snapshot_id,
        )
        assert snap2.previous_snapshot_id == "s1"


# ── ViabilityChecker ────────────────────────────────────────────────────


class TestViabilityChecker:
    def test_viable_check_passes(self):
        vc = ViabilityChecker()
        result = vc.check_viability("worker", 0, ResourceProfile())
        assert result == ViabilityResult.VIABLE

    def test_blacklisted_type(self):
        vc = ViabilityChecker(blacklist={"banned"})
        result = vc.check_viability("banned", 0, ResourceProfile())
        assert result == ViabilityResult.BLACKLISTED

    def test_max_instances_returns_already_spawned(self):
        vc = ViabilityChecker(max_instances_per_type=3)
        result = vc.check_viability("worker", 3, ResourceProfile())
        assert result == ViabilityResult.ALREADY_SPAWNED

    def test_max_depth_returns_not_viable(self):
        vc = ViabilityChecker(max_spawn_depth=2)
        result = vc.check_viability("worker", 0, ResourceProfile(), parent_depth=2)
        assert result == ViabilityResult.NOT_VIABLE

    def test_resource_limits_memory(self):
        rp = ResourceProfile(memory_mb=9000)
        vc = ViabilityChecker()
        result = vc.check_viability("worker", 0, rp)
        assert result == ViabilityResult.INSUFFICIENT_RESOURCES

    def test_resource_limits_cpu(self):
        rp = ResourceProfile(cpu_cores=17.0)
        vc = ViabilityChecker()
        result = vc.check_viability("worker", 0, rp)
        assert result == ViabilityResult.INSUFFICIENT_RESOURCES

    def test_add_and_remove_blacklist(self):
        vc = ViabilityChecker()
        assert not vc.is_blacklisted("test_type")
        vc.add_to_blacklist("test_type")
        assert vc.is_blacklisted("test_type")
        vc.remove_from_blacklist("test_type")
        assert not vc.is_blacklisted("test_type")


# ── ModuleInstanceManager ───────────────────────────────────────────────


class TestModuleInstanceManager:
    def _make_manager(self, **kwargs):
        return ModuleInstanceManager(**kwargs)

    def test_spawn_returns_approved_and_instance(self):
        mgr = self._make_manager()
        decision, inst = mgr.spawn_instance("worker")
        assert decision == SpawnDecision.APPROVED
        assert inst is not None

    def test_spawned_instance_is_active(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker")
        assert inst.state == InstanceState.ACTIVE

    def test_get_instance(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker")
        found = mgr.get_instance(inst.instance_id)
        assert found is inst

    def test_list_instances_all(self):
        mgr = self._make_manager()
        mgr.spawn_instance("a")
        mgr.spawn_instance("b")
        assert len(mgr.list_instances()) == 2

    def test_list_instances_filter_by_type(self):
        mgr = self._make_manager()
        mgr.spawn_instance("a")
        mgr.spawn_instance("b")
        mgr.spawn_instance("a")
        assert len(mgr.list_instances(module_type="a")) == 2

    def test_list_instances_filter_by_state(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker")
        mgr.despawn_instance(inst.instance_id)
        active = mgr.list_instances(state=InstanceState.ACTIVE)
        despawned = mgr.list_instances(state=InstanceState.DESPAWNED)
        assert len(active) == 0
        assert len(despawned) == 1

    def test_despawn_instance_sets_state(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker")
        ok = mgr.despawn_instance(inst.instance_id)
        assert ok is True
        assert inst.state == InstanceState.DESPAWNED

    def test_despawn_unknown_returns_false(self):
        mgr = self._make_manager()
        assert mgr.despawn_instance("nonexistent") is False

    def test_audit_trail_returns_entries(self):
        mgr = self._make_manager()
        mgr.spawn_instance("worker")
        trail = mgr.get_audit_trail()
        assert len(trail) >= 1
        assert trail[-1].action == "spawn"

    def test_audit_trail_filters_by_instance_id(self):
        mgr = self._make_manager()
        _, inst1 = mgr.spawn_instance("a")
        _, inst2 = mgr.spawn_instance("b")
        trail = mgr.get_audit_trail(instance_id=inst1.instance_id)
        assert all(e.instance_id == inst1.instance_id for e in trail)

    def test_update_instance_config_creates_snapshot(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker", config={"v": 1})
        ok = mgr.update_instance_config(inst.instance_id, {"v": 2})
        assert ok is True
        history = mgr.get_config_history(inst.instance_id)
        assert len(history) == 2
        assert history[-1].config == {"v": 2}

    def test_get_config_history(self):
        mgr = self._make_manager()
        _, inst = mgr.spawn_instance("worker")
        history = mgr.get_config_history(inst.instance_id)
        assert len(history) == 1

    def test_get_status(self):
        mgr = self._make_manager()
        mgr.spawn_instance("a")
        mgr.spawn_instance("b")
        status = mgr.get_status()
        assert status["total_instances"] == 2
        assert "by_state" in status
        assert "by_type" in status

    def test_get_resource_availability(self):
        mgr = self._make_manager()
        mgr.spawn_instance("worker")
        res = mgr.get_resource_availability()
        assert "allocated_cpu_cores" in res
        assert "available_memory_mb" in res

    def test_register_module_type(self):
        mgr = self._make_manager()
        assert mgr.register_module_type("new_type") is True
        assert mgr.register_module_type("new_type") is False  # already registered

    def test_blacklist_module_type_prevents_spawning(self):
        mgr = self._make_manager()
        mgr.blacklist_module_type("banned")
        decision, inst = mgr.spawn_instance("banned")
        assert decision == SpawnDecision.DENIED_BLACKLIST
        assert inst is None

    def test_bulk_despawn(self):
        mgr = self._make_manager()
        _, i1 = mgr.spawn_instance("a")
        _, i2 = mgr.spawn_instance("b")
        result = mgr.bulk_despawn([i1.instance_id, i2.instance_id])
        assert result["results"][i1.instance_id] is True
        assert result["results"][i2.instance_id] is True

    def test_find_viable_instances(self):
        mgr = self._make_manager()
        mgr.spawn_instance("worker", capabilities=["gpu"])
        mgr.spawn_instance("worker", capabilities=["cpu"])
        matches = mgr.find_viable_instances("worker", required_capabilities=["gpu"])
        assert len(matches) == 1
        assert "gpu" in matches[0].capabilities

    def test_circuit_breaker_opens_after_threshold(self):
        mgr = self._make_manager(circuit_breaker_threshold=5)
        mgr.blacklist_module_type("bad")
        for _ in range(6):
            decision, _ = mgr.spawn_instance("bad")
        assert decision == SpawnDecision.DENIED_CIRCUIT

    def test_circuit_breaker_recovers_after_timeout(self):
        mgr = self._make_manager(
            circuit_breaker_threshold=2,
            circuit_breaker_recovery_seconds=1,
        )
        mgr.blacklist_module_type("flaky")
        for _ in range(3):
            mgr.spawn_instance("flaky")
        # Circuit should be open now
        decision, _ = mgr.spawn_instance("flaky")
        assert decision == SpawnDecision.DENIED_CIRCUIT

        # Remove from blacklist and wait for recovery
        mgr._viability_checker.remove_from_blacklist("flaky")
        time.sleep(1.1)
        decision2, inst2 = mgr.spawn_instance("flaky")
        assert decision2 == SpawnDecision.APPROVED
        assert inst2 is not None

    def test_audit_trail_is_bounded(self):
        mgr = self._make_manager()
        for i in range(1100):
            mgr.spawn_instance("worker")
        trail = mgr.get_audit_trail(limit=1000)
        assert len(trail) <= 1000

    def test_concurrent_spawn_despawn(self):
        mgr = self._make_manager(max_instances_per_type=200)
        ids = []

        def spawn_and_record():
            decision, inst = mgr.spawn_instance("concurrent")
            if inst:
                ids.append(inst.instance_id)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(spawn_and_record) for _ in range(50)]
            for f in futures:
                f.result()

        assert len(ids) > 0

        despawn_results = []

        def despawn(iid):
            despawn_results.append(mgr.despawn_instance(iid))

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(despawn, iid) for iid in ids]
            for f in futures:
                f.result()

        assert all(despawn_results)


# ── Integration functions ────────────────────────────────────────────────


class TestIntegrationHelpers:
    def test_integrate_with_module_registry(self):
        mgr = ModuleInstanceManager()
        registry = SimpleNamespace(
            list_available=lambda: ["mod_a", "mod_b"],
            get_module_status=lambda name: "loaded",
        )
        integrate_with_module_registry(mgr, registry)
        assert mgr.register_module_type("mod_a") is False  # already registered

    def test_integrate_with_triage_rollcall(self):
        mgr = ModuleInstanceManager()
        candidate = SimpleNamespace(name="cand_1", capabilities=["fast"])
        adapter = SimpleNamespace(list_candidates=lambda: [candidate])
        integrate_with_triage_rollcall(mgr, adapter)
        assert mgr.register_module_type("cand_1") is False  # already registered
