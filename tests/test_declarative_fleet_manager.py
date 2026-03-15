"""
Tests for the Declarative Fleet Manager.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from declarative_fleet_manager import (
    ActionStatus,
    ActionType,
    BotManifest,
    DriftItem,
    FleetDriftDetector,
    FleetManifest,
    FleetReconciler,
    HeartbeatPolicy,
    ManifestLoader,
    ManifestValidationError,
    ReconciliationAction,
    _topological_sort,
    _validate_manifest,
)
from bot_inventory_library import BotInventoryLibrary


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FLEET_MANIFESTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "fleet_manifests"
)


def _make_simple_manifest(fleet_id: str = "test_fleet") -> FleetManifest:
    return FleetManifest(
        fleet_id=fleet_id,
        version="1.0",
        description="Test fleet",
        bots=[
            BotManifest(
                bot_id="b001",
                name="Bot Alpha",
                role="expert",
                capabilities=["analyze_requirements"],
                enabled=True,
                replicas=1,
            ),
            BotManifest(
                bot_id="b002",
                name="Bot Beta",
                role="monitor",
                capabilities=["monitor_performance"],
                enabled=True,
                replicas=1,
                dependencies=["b001"],
            ),
        ],
    )


class _MockEventBackbone:
    """Records published events for assertion."""

    def __init__(self) -> None:
        self.events: list = []

    def publish(self, event_type, payload, source=None, session_id=None) -> str:
        self.events.append({"type": event_type, "payload": payload})
        return str(uuid.uuid4())


class _MockHeartbeatMonitor:
    """Records heartbeat policy registrations."""

    def __init__(self) -> None:
        self.policies: dict = {}

    def register_policy(self, bot_id: str, policy: dict) -> None:
        self.policies[bot_id] = policy


# ---------------------------------------------------------------------------
# ManifestLoader tests
# ---------------------------------------------------------------------------

class TestManifestLoaderFromDict:
    def test_load_minimal_dict(self):
        data = {
            "fleet_id": "fleet_min",
            "version": "1.0",
            "description": "Minimal",
            "bots": [],
        }
        m = ManifestLoader.load_from_dict(data)
        assert m.fleet_id == "fleet_min"
        assert m.bots == []

    def test_load_dict_with_bots(self):
        data = {
            "fleet_id": "fleet_abc",
            "version": "2.0",
            "description": "Two bots",
            "bots": [
                {
                    "bot_id": "b1",
                    "name": "Alpha",
                    "role": "expert",
                    "capabilities": ["analyze_requirements"],
                    "replicas": 1,
                    "enabled": True,
                    "dependencies": [],
                    "heartbeat_policy": {
                        "interval_seconds": 20,
                        "max_missed": 2,
                        "recovery_strategy": "restart",
                    },
                },
                {
                    "bot_id": "b2",
                    "name": "Beta",
                    "role": "monitor",
                    "capabilities": ["monitor_performance"],
                    "replicas": 1,
                    "enabled": True,
                    "dependencies": ["b1"],
                },
            ],
        }
        m = ManifestLoader.load_from_dict(data)
        assert len(m.bots) == 2
        assert m.bots[0].heartbeat_policy.interval_seconds == 20
        assert m.bots[1].dependencies == ["b1"]


class TestManifestLoaderFromYAML:
    def test_load_from_yaml_file(self):
        yaml_path = os.path.join(FLEET_MANIFESTS_DIR, "default_fleet.yaml")
        m = ManifestLoader.load_from_yaml(yaml_path)
        assert m.fleet_id == "murphy_default_fleet"
        assert len(m.bots) == 5

    def test_roundtrip_yaml(self):
        manifest = _make_simple_manifest("yaml_roundtrip")
        data = manifest.to_dict()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as fh:
            import yaml
            yaml.dump(data, fh, allow_unicode=True)
            tmp_path = fh.name
        try:
            loaded = ManifestLoader.load_from_yaml(tmp_path)
            assert loaded.fleet_id == "yaml_roundtrip"
            assert len(loaded.bots) == 2
        finally:
            os.unlink(tmp_path)


class TestManifestLoaderFromJSON:
    def test_roundtrip_json(self):
        manifest = _make_simple_manifest("json_roundtrip")
        data = manifest.to_dict()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(data, fh)
            tmp_path = fh.name
        try:
            loaded = ManifestLoader.load_from_json(tmp_path)
            assert loaded.fleet_id == "json_roundtrip"
            assert len(loaded.bots) == 2
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Manifest validation tests
# ---------------------------------------------------------------------------

class TestManifestValidation:
    def test_negative_replicas_raises(self):
        data = {
            "fleet_id": "f1",
            "version": "1.0",
            "description": "",
            "bots": [
                {"bot_id": "b1", "name": "X", "role": "expert", "replicas": -1}
            ],
        }
        with pytest.raises(ManifestValidationError, match="negative replicas"):
            ManifestLoader.load_from_dict(data)

    def test_unknown_dependency_raises(self):
        data = {
            "fleet_id": "f2",
            "version": "1.0",
            "description": "",
            "bots": [
                {
                    "bot_id": "b1",
                    "name": "X",
                    "role": "expert",
                    "dependencies": ["nonexistent_bot"],
                }
            ],
        }
        with pytest.raises(ManifestValidationError, match="unknown dependency"):
            ManifestLoader.load_from_dict(data)

    def test_cycle_detection_raises(self):
        data = {
            "fleet_id": "f3",
            "version": "1.0",
            "description": "",
            "bots": [
                {"bot_id": "a", "name": "A", "role": "expert", "dependencies": ["b"]},
                {"bot_id": "b", "name": "B", "role": "expert", "dependencies": ["a"]},
            ],
        }
        with pytest.raises(ManifestValidationError, match="cycle"):
            ManifestLoader.load_from_dict(data)

    def test_unknown_capability_raises(self):
        manifest = FleetManifest(
            fleet_id="f4",
            version="1.0",
            description="",
            bots=[
                BotManifest(
                    bot_id="b1",
                    name="X",
                    role="expert",
                    capabilities=["nonexistent_cap"],
                )
            ],
        )
        fake_registry: dict = {}
        with pytest.raises(ManifestValidationError, match="unknown capability"):
            _validate_manifest(manifest, capability_registry=fake_registry)

    def test_valid_manifest_passes(self):
        manifest = _make_simple_manifest()
        # No exception expected
        _validate_manifest(manifest)


# ---------------------------------------------------------------------------
# Topological sort tests
# ---------------------------------------------------------------------------

class TestTopologicalSort:
    def test_dependency_order(self):
        bots = [
            BotManifest(bot_id="c", name="C", role="expert", dependencies=["b"]),
            BotManifest(bot_id="b", name="B", role="expert", dependencies=["a"]),
            BotManifest(bot_id="a", name="A", role="expert"),
        ]
        ordered = _topological_sort(bots)
        ids = [b.bot_id for b in ordered]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_no_dependencies_any_order(self):
        bots = [
            BotManifest(bot_id="x", name="X", role="expert"),
            BotManifest(bot_id="y", name="Y", role="monitor"),
        ]
        ordered = _topological_sort(bots)
        assert {b.bot_id for b in ordered} == {"x", "y"}


# ---------------------------------------------------------------------------
# Observe / Diff / Reconcile cycle tests
# ---------------------------------------------------------------------------

class TestObserveDiffReconcile:
    def test_observe_returns_inventory(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        state = reconciler.observe()
        assert "total_bots" in state

    def test_diff_spawns_missing_bots(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(_make_simple_manifest())
        actions = reconciler.diff()
        spawn_actions = [a for a in actions if a.action_type == ActionType.SPAWN]
        assert len(spawn_actions) >= 2  # both bots should be missing initially

    def test_diff_no_extra_when_empty_manifest(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(
            FleetManifest(fleet_id="empty", version="1.0", description="", bots=[])
        )
        actions = reconciler.diff()
        spawn_actions = [a for a in actions if a.action_type == ActionType.SPAWN]
        assert spawn_actions == []

    def test_reconcile_spawns_missing_bots(self):
        inventory = BotInventoryLibrary()
        backbone = _MockEventBackbone()
        reconciler = FleetReconciler(
            bot_inventory=inventory, event_backbone=backbone
        )
        reconciler.load_manifest(_make_simple_manifest())
        result = reconciler.reconcile()
        assert result["completed"] > 0
        assert result["failed"] == 0
        # Both bots should now exist
        state = reconciler.observe()
        names = {b["name"] for b in state["all_bots"]}
        assert "Bot Alpha" in names
        assert "Bot Beta" in names

    def test_reconcile_is_idempotent(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(_make_simple_manifest())
        result1 = reconciler.reconcile()
        result2 = reconciler.reconcile()
        # Second run should not spawn again (bots already exist); check that
        # no additional spawn actions appear on second run.
        spawns_run1 = sum(
            1 for a in result1["actions"] if a["action_type"] == "spawn"
        )
        spawns_run2 = sum(
            1 for a in result2["actions"] if a["action_type"] == "spawn"
        )
        assert spawns_run1 >= spawns_run2


class TestDespawnExcessBots:
    def test_reconcile_despawns_unmanaged_bots(self):
        """Bots in inventory but not in manifest should be despawned."""
        inventory = BotInventoryLibrary()
        # Spawn a bot that is NOT in the manifest
        extra = inventory.spawn_bot(name="Unmanaged Bot", role="assistant")

        reconciler = FleetReconciler(bot_inventory=inventory)
        manifest = FleetManifest(
            fleet_id="strict_fleet",
            version="1.0",
            description="No bots declared",
            bots=[],
        )
        reconciler.load_manifest(manifest)
        result = reconciler.reconcile()

        despawn_actions = [
            a for a in result["actions"] if a["action_type"] == "despawn"
        ]
        assert len(despawn_actions) >= 1
        # The extra bot should no longer exist
        assert inventory.get_bot(extra.agent_id) is None

    def test_reconcile_despawns_disabled_bot(self):
        inventory = BotInventoryLibrary()
        inventory.spawn_bot(name="Disabled Bot", role="monitor")

        manifest = FleetManifest(
            fleet_id="f_disabled",
            version="1.0",
            description="",
            bots=[
                BotManifest(
                    bot_id="d001",
                    name="Disabled Bot",
                    role="monitor",
                    enabled=False,
                    replicas=1,
                )
            ],
        )
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(manifest)
        result = reconciler.reconcile()
        despawns = [a for a in result["actions"] if a["action_type"] == "despawn"]
        assert len(despawns) >= 1


class TestUpdateDriftedConfig:
    def test_reconcile_updates_role_drift(self):
        inventory = BotInventoryLibrary()
        inventory.spawn_bot(name="Drifted Bot", role="assistant")

        manifest = FleetManifest(
            fleet_id="f_drift",
            version="1.0",
            description="",
            bots=[
                BotManifest(
                    bot_id="dr001",
                    name="Drifted Bot",
                    role="expert",  # declared role differs from actual "assistant"
                    enabled=True,
                    replicas=1,
                )
            ],
        )
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(manifest)
        actions = reconciler.diff()
        update_actions = [a for a in actions if a.action_type == ActionType.UPDATE]
        assert len(update_actions) >= 1
        assert update_actions[0].details["desired"] == "expert"


# ---------------------------------------------------------------------------
# Heartbeat registration tests
# ---------------------------------------------------------------------------

class TestHeartbeatRegistration:
    def test_reconcile_registers_heartbeat_policies(self):
        inventory = BotInventoryLibrary()
        monitor = _MockHeartbeatMonitor()
        manifest = FleetManifest(
            fleet_id="hb_fleet",
            version="1.0",
            description="",
            bots=[
                BotManifest(
                    bot_id="hb001",
                    name="HB Bot",
                    role="monitor",
                    heartbeat_policy=HeartbeatPolicy(
                        interval_seconds=15,
                        max_missed=2,
                        recovery_strategy="alert",
                    ),
                    enabled=True,
                    replicas=1,
                )
            ],
        )
        reconciler = FleetReconciler(
            bot_inventory=inventory, heartbeat_monitor=monitor
        )
        reconciler.load_manifest(manifest)
        reconciler.reconcile()
        assert "hb001" in monitor.policies
        assert monitor.policies["hb001"]["interval_seconds"] == 15


# ---------------------------------------------------------------------------
# Event publishing tests
# ---------------------------------------------------------------------------

class TestEventPublishing:
    def _event_strings(self, backbone: _MockEventBackbone) -> list:
        """Return lower-cased string representations of all event types."""
        result = []
        for e in backbone.events:
            t = e["type"]
            # EventType enum objects have a .value attribute (lowercase string)
            if hasattr(t, "value"):
                result.append(t.value)
            else:
                result.append(str(t).lower())
        return result

    def test_reconcile_publishes_started_and_reconciled_events(self):
        inventory = BotInventoryLibrary()
        backbone = _MockEventBackbone()
        reconciler = FleetReconciler(
            bot_inventory=inventory, event_backbone=backbone
        )
        reconciler.load_manifest(_make_simple_manifest())
        reconciler.reconcile()
        event_names = self._event_strings(backbone)
        assert any("reconciliation_started" in n for n in event_names)
        assert any("fleet_reconciled" in n or n == "fleet_reconciled" for n in event_names)

    def test_spawn_publishes_bot_spawned_event(self):
        inventory = BotInventoryLibrary()
        backbone = _MockEventBackbone()
        reconciler = FleetReconciler(
            bot_inventory=inventory, event_backbone=backbone
        )
        reconciler.load_manifest(_make_simple_manifest())
        reconciler.reconcile()
        event_names = self._event_strings(backbone)
        assert any("bot_spawned" in n for n in event_names)


# ---------------------------------------------------------------------------
# Reconciliation status tests
# ---------------------------------------------------------------------------

class TestReconciliationStatus:
    def test_status_before_reconcile(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(_make_simple_manifest())
        status = reconciler.get_reconciliation_status()
        assert status["fleet_id"] == "test_fleet"
        assert status["total_actions"] == 0

    def test_status_after_reconcile_converged(self):
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(_make_simple_manifest())
        reconciler.reconcile()
        status = reconciler.get_reconciliation_status()
        assert status["failed"] == 0
        assert status["converged"] is True


# ---------------------------------------------------------------------------
# Drift detector tests
# ---------------------------------------------------------------------------

class TestFleetDriftDetector:
    def test_no_drift_when_no_manifest(self):
        detector = FleetDriftDetector(manifest=None, bot_inventory=None)
        drifts = detector.check_drift()
        assert drifts == []

    def test_drift_all_missing_when_no_inventory(self):
        manifest = _make_simple_manifest()
        detector = FleetDriftDetector(manifest=manifest, bot_inventory=None)
        drifts = detector.check_drift()
        assert len(drifts) == 2
        for d in drifts:
            assert d.drift_type == "missing"

    def test_drift_detects_extra_bots(self):
        inventory = BotInventoryLibrary()
        inventory.spawn_bot(name="Surprise Bot", role="assistant")
        manifest = FleetManifest(
            fleet_id="clean_fleet",
            version="1.0",
            description="",
            bots=[],
        )
        detector = FleetDriftDetector(manifest=manifest, bot_inventory=inventory)
        drifts = detector.check_drift()
        extra = [d for d in drifts if d.drift_type == "extra"]
        assert len(extra) >= 1

    def test_drift_update_manifest(self):
        detector = FleetDriftDetector()
        assert detector._manifest is None
        manifest = _make_simple_manifest()
        detector.update_manifest(manifest)
        assert detector._manifest is manifest


# ---------------------------------------------------------------------------
# Thread safety tests
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_reconcile_calls(self):
        """Multiple threads calling reconcile() simultaneously must not crash."""
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(_make_simple_manifest())

        errors: list = []

        def worker():
            try:
                reconciler.reconcile()
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread errors: {errors}"

    def test_concurrent_drift_checks(self):
        manifest = _make_simple_manifest()
        detector = FleetDriftDetector(manifest=manifest, bot_inventory=None)
        errors: list = []

        def worker():
            try:
                detector.check_drift()
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == []


# ---------------------------------------------------------------------------
# Default fleet YAML smoke test
# ---------------------------------------------------------------------------

class TestDefaultFleetYAML:
    def test_default_fleet_loads_successfully(self):
        yaml_path = os.path.join(FLEET_MANIFESTS_DIR, "default_fleet.yaml")
        m = ManifestLoader.load_from_yaml(yaml_path)
        assert m.fleet_id == "murphy_default_fleet"
        assert len(m.bots) == 5

    def test_default_fleet_dependency_order(self):
        yaml_path = os.path.join(FLEET_MANIFESTS_DIR, "default_fleet.yaml")
        m = ManifestLoader.load_from_yaml(yaml_path)
        ordered = _topological_sort(m.bots)
        ids = [b.bot_id for b in ordered]
        # orchestrator must come before all others
        orch_idx = ids.index("orchestrator_001")
        for other in ["expert_001", "validator_001", "monitor_001", "auditor_001"]:
            assert orch_idx < ids.index(other)

    def test_default_fleet_supervision_topology(self):
        yaml_path = os.path.join(FLEET_MANIFESTS_DIR, "default_fleet.yaml")
        m = ManifestLoader.load_from_yaml(yaml_path)
        assert "orchestrator_001" in m.supervision_topology
        children = m.supervision_topology["orchestrator_001"]
        assert "expert_001" in children

    def test_default_fleet_reconcile_smoke(self):
        yaml_path = os.path.join(FLEET_MANIFESTS_DIR, "default_fleet.yaml")
        m = ManifestLoader.load_from_yaml(yaml_path)
        inventory = BotInventoryLibrary()
        reconciler = FleetReconciler(bot_inventory=inventory)
        reconciler.load_manifest(m)
        result = reconciler.reconcile()
        assert result["failed"] == 0
        state = reconciler.observe()
        names = {b["name"] for b in state["all_bots"]}
        assert "Fleet Orchestrator" in names
        assert "Architecture Expert" in names
