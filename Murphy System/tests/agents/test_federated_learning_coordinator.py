# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Test Suite: Federated Learning Coordinator — FLC-001

Comprehensive tests for the federated_learning_coordinator module:
  - Data model serialisation (ModelWeights, GradientUpdate, TrainingRound, FederatedNode)
  - PrivacyGuard (gradient clipping, noise injection)
  - Aggregation strategies (FedAvg, Median)
  - FederatedCoordinator lifecycle (register, start, submit, complete)
  - Edge cases (empty rounds, duplicate submissions, offline nodes)
  - Thread safety under concurrent access
  - Wingman pair validation gate
  - Causality Sandbox gating simulation

Tests use the storyline-actuals record() pattern for cause/effect/lesson tracking.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import datetime
import math
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from federated_learning_coordinator import (
    AggregationMethod,
    FederatedAverageStrategy,
    FederatedCoordinator,
    FederatedNode,
    GradientUpdate,
    MedianStrategy,
    ModelWeights,
    NodeStatus,
    PrivacyGuard,
    RoundStatus,
    TrainingRound,
)


# ---------------------------------------------------------------------------
# Record infrastructure (storyline-actuals pattern)
# ---------------------------------------------------------------------------

@dataclass
class FLCRecord:
    """One FLC check record."""
    check_id: str
    description: str
    expected: Any
    actual: Any
    passed: bool
    cause: str = ""
    effect: str = ""
    lesson: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


_records: List[FLCRecord] = []


def record(
    check_id: str,
    description: str,
    expected: Any,
    actual: Any,
    cause: str = "",
    effect: str = "",
    lesson: str = "",
) -> bool:
    """Record a check and return whether expected == actual."""
    passed = expected == actual
    _records.append(FLCRecord(
        check_id=check_id,
        description=description,
        expected=expected,
        actual=actual,
        passed=passed,
        cause=cause,
        effect=effect,
        lesson=lesson,
    ))
    return passed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def coordinator() -> FederatedCoordinator:
    """Return a fresh coordinator with 3-dim weights and zero noise."""
    return FederatedCoordinator(
        initial_weights=ModelWeights(weights=[0.0, 0.0, 0.0]),
        privacy_noise_scale=0.0,  # deterministic for tests
    )


@pytest.fixture()
def two_node_coordinator(coordinator: FederatedCoordinator) -> FederatedCoordinator:
    """Return a coordinator with two registered nodes."""
    coordinator.register_node("n-1", "Node-A", sample_count=100)
    coordinator.register_node("n-2", "Node-B", sample_count=200)
    return coordinator


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

class TestModelWeights:
    """FLC-010–012: ModelWeights data model."""

    def test_auto_version(self):
        """FLC-010: ModelWeights auto-generates a version string."""
        w = ModelWeights(weights=[1.0, 2.0])
        assert record(
            "FLC-010", "Version auto-generated",
            True, w.version.startswith("v-"),
            cause="No version supplied at construction",
            effect="Auto-generated UUID-based version",
            lesson="Always auto-generate IDs when not provided",
        )

    def test_checksum_deterministic(self):
        """FLC-011: Same weights produce the same checksum."""
        w1 = ModelWeights(weights=[1.0, 2.0, 3.0])
        w2 = ModelWeights(weights=[1.0, 2.0, 3.0])
        assert record(
            "FLC-011", "Checksums match for identical weights",
            w1.checksum, w2.checksum,
            cause="Deterministic SHA-256",
            effect="Checksums are reproducible",
            lesson="Checksum integrity depends on deterministic serialisation",
        )

    def test_to_dict(self):
        """FLC-012: to_dict contains expected keys."""
        w = ModelWeights(weights=[1.0])
        d = w.to_dict()
        keys_ok = all(k in d for k in ("weights", "version", "checksum"))
        assert record(
            "FLC-012", "to_dict has weights/version/checksum",
            True, keys_ok,
            cause="Serialisation contract",
            effect="Model snapshots are JSON-serialisable",
            lesson="Every data model needs a dict serialiser",
        )


# ============================================================================
# PRIVACY GUARD TESTS
# ============================================================================

class TestPrivacyGuard:
    """FLC-020–023: PrivacyGuard clipping and noise."""

    def test_clip_within_norm(self):
        """FLC-020: Gradients within clip_norm are unchanged."""
        pg = PrivacyGuard(noise_scale=0.0, clip_norm=10.0)
        deltas = [1.0, 2.0, 3.0]
        clipped = pg.clip_gradients(deltas)
        assert record(
            "FLC-020", "Small gradients pass through unchanged",
            deltas, clipped,
            cause="L2 norm < clip_norm",
            effect="No clipping applied",
            lesson="Only clip when necessary to preserve signal",
        )

    def test_clip_exceeding_norm(self):
        """FLC-021: Gradients exceeding clip_norm are scaled down."""
        pg = PrivacyGuard(noise_scale=0.0, clip_norm=1.0)
        deltas = [3.0, 4.0]  # L2 norm = 5.0
        clipped = pg.clip_gradients(deltas)
        norm = math.sqrt(sum(d * d for d in clipped))
        assert record(
            "FLC-021", "Clipped norm approximately equals clip_norm",
            True, abs(norm - 1.0) < 1e-6,
            cause="L2 norm 5.0 > clip_norm 1.0",
            effect="Gradients scaled to unit norm",
            lesson="Gradient clipping bounds sensitivity for DP",
        )

    def test_noise_injection(self):
        """FLC-022: Noise injection changes values when scale > 0."""
        pg = PrivacyGuard(noise_scale=1.0, clip_norm=100.0)
        deltas = [0.0, 0.0, 0.0]
        noisy = pg.add_noise(deltas)
        any_changed = any(abs(n) > 0 for n in noisy)
        assert record(
            "FLC-022", "Noise injection modifies zero gradients",
            True, any_changed,
            cause="noise_scale=1.0 adds Gaussian noise",
            effect="Output differs from input",
            lesson="Noise scale controls privacy-utility trade-off",
        )

    def test_no_noise_when_scale_zero(self):
        """FLC-023: Zero noise scale means no noise added."""
        pg = PrivacyGuard(noise_scale=0.0, clip_norm=100.0)
        deltas = [1.0, 2.0, 3.0]
        result = pg.add_noise(deltas)
        assert record(
            "FLC-023", "Zero noise scale means no change",
            deltas, result,
            cause="noise_scale=0.0",
            effect="Exact passthrough",
            lesson="Provide a zero-noise mode for testing",
        )


# ============================================================================
# AGGREGATION STRATEGY TESTS
# ============================================================================

class TestFederatedAverage:
    """FLC-030–032: FedAvg aggregation."""

    def test_single_contribution(self):
        """FLC-030: Single contribution directly sets the weights."""
        strat = FederatedAverageStrategy()
        contrib = GradientUpdate("n-1", "r-1", [1.0, 2.0], sample_count=10)
        result = strat.aggregate([contrib], [0.0, 0.0])
        assert record(
            "FLC-030", "Single contribution adds deltas to weights",
            [1.0, 2.0], result,
            cause="Only one contribution, weight=1.0",
            effect="Weights = old + deltas",
            lesson="FedAvg with one node is just gradient descent",
        )

    def test_weighted_average(self):
        """FLC-031: Two contributions weighted by sample count."""
        strat = FederatedAverageStrategy()
        c1 = GradientUpdate("n-1", "r-1", [2.0], sample_count=100)
        c2 = GradientUpdate("n-2", "r-1", [4.0], sample_count=100)
        result = strat.aggregate([c1, c2], [0.0])
        # (2.0*0.5 + 4.0*0.5) = 3.0
        assert record(
            "FLC-031", "Equal-sample average is arithmetic mean",
            True, abs(result[0] - 3.0) < 1e-6,
            cause="100 samples each → 50/50 weight",
            effect="Mean delta = 3.0",
            lesson="FedAvg weights by sample count for fairness",
        )

    def test_empty_contributions(self):
        """FLC-032: No contributions returns current weights unchanged."""
        strat = FederatedAverageStrategy()
        result = strat.aggregate([], [5.0, 10.0])
        assert record(
            "FLC-032", "Empty contributions → no change",
            [5.0, 10.0], result,
            cause="No contributions submitted",
            effect="Weights unchanged",
            lesson="Handle empty input gracefully",
        )


class TestMedianStrategy:
    """FLC-035: Median aggregation."""

    def test_median_robust_to_outlier(self):
        """FLC-035: Median ignores Byzantine outlier."""
        strat = MedianStrategy()
        c1 = GradientUpdate("n-1", "r-1", [1.0], sample_count=10)
        c2 = GradientUpdate("n-2", "r-1", [2.0], sample_count=10)
        c3 = GradientUpdate("n-3", "r-1", [1000.0], sample_count=10)  # outlier
        result = strat.aggregate([c1, c2, c3], [0.0])
        # sorted: [1.0, 2.0, 1000.0] → median index 1 → 2.0
        assert record(
            "FLC-035", "Median ignores Byzantine outlier",
            True, abs(result[0] - 2.0) < 1e-6,
            cause="One of three contributions is an outlier",
            effect="Median selects middle value",
            lesson="Median aggregation provides Byzantine resilience",
        )


# ============================================================================
# COORDINATOR LIFECYCLE TESTS
# ============================================================================

class TestCoordinatorNodes:
    """FLC-040–043: Node registration."""

    def test_register_node(self, coordinator: FederatedCoordinator):
        """FLC-040: Node registration stores the node."""
        node = coordinator.register_node("n-1", "Node-A", sample_count=500)
        assert record(
            "FLC-040", "Registered node has correct name",
            "Node-A", node.name,
            cause="register_node called",
            effect="Node stored in coordinator",
            lesson="Registration is the first step in federation",
        )

    def test_list_nodes(self, two_node_coordinator: FederatedCoordinator):
        """FLC-041: list_nodes returns all registered nodes."""
        nodes = two_node_coordinator.list_nodes()
        assert record(
            "FLC-041", "Two nodes registered",
            2, len(nodes),
            cause="Two register_node calls",
            effect="Both visible in listing",
            lesson="List should never lose entries",
        )

    def test_remove_node(self, two_node_coordinator: FederatedCoordinator):
        """FLC-042: remove_node removes the node."""
        removed = two_node_coordinator.remove_node("n-1")
        assert record(
            "FLC-042", "remove_node returns True",
            True, removed,
            cause="Node exists",
            effect="Node removed from registry",
            lesson="Removal must be idempotent",
        )

    def test_remove_nonexistent(self, coordinator: FederatedCoordinator):
        """FLC-043: Removing a non-existent node returns False."""
        assert record(
            "FLC-043", "Remove missing node returns False",
            False, coordinator.remove_node("no-such-node"),
            cause="Node never registered",
            effect="False returned, no crash",
            lesson="Handle missing references gracefully",
        )


class TestCoordinatorRounds:
    """FLC-050–056: Training round lifecycle."""

    def test_start_round(self, two_node_coordinator: FederatedCoordinator):
        """FLC-050: Starting a round selects all idle nodes."""
        rnd = two_node_coordinator.start_round()
        assert record(
            "FLC-050", "Round includes both idle nodes",
            2, len(rnd.participating_nodes),
            cause="Two registered idle nodes",
            effect="Both selected for round",
            lesson="Default is all-idle selection",
        )

    def test_start_round_specific_nodes(self, two_node_coordinator: FederatedCoordinator):
        """FLC-051: Specific node selection."""
        rnd = two_node_coordinator.start_round(node_ids=["n-1"])
        assert record(
            "FLC-051", "Only specified node participates",
            ["n-1"], rnd.participating_nodes,
            cause="Explicit node_ids=['n-1']",
            effect="Only n-1 in round",
            lesson="Allow selective participation for A/B testing",
        )

    def test_start_round_no_nodes_raises(self, coordinator: FederatedCoordinator):
        """FLC-052: Starting a round with no nodes raises ValueError."""
        with pytest.raises(ValueError, match="No eligible nodes"):
            coordinator.start_round()
        assert record(
            "FLC-052", "Empty federation raises ValueError",
            True, True,
            cause="No nodes registered",
            effect="ValueError raised",
            lesson="Fail fast with clear errors",
        )

    def test_submit_update(self, two_node_coordinator: FederatedCoordinator):
        """FLC-053: Submit a gradient update to a round."""
        rnd = two_node_coordinator.start_round()
        update = GradientUpdate("n-1", rnd.round_id, [0.1, 0.2, 0.3], sample_count=50)
        accepted = two_node_coordinator.submit_update(rnd.round_id, update)
        assert record(
            "FLC-053", "Update accepted",
            True, accepted,
            cause="Valid node, valid round",
            effect="Contribution stored",
            lesson="Always validate membership before accepting",
        )

    def test_complete_round(self, two_node_coordinator: FederatedCoordinator):
        """FLC-054: Complete a round aggregates weights."""
        rnd = two_node_coordinator.start_round()
        two_node_coordinator.submit_update(
            rnd.round_id,
            GradientUpdate("n-1", rnd.round_id, [1.0, 0.0, 0.0], sample_count=100),
        )
        two_node_coordinator.submit_update(
            rnd.round_id,
            GradientUpdate("n-2", rnd.round_id, [0.0, 1.0, 0.0], sample_count=100),
        )
        new_weights = two_node_coordinator.complete_round(rnd.round_id)
        assert record(
            "FLC-054", "Completed round produces new weights",
            True, new_weights is not None,
            cause="Two valid contributions",
            effect="Aggregated model produced",
            lesson="Aggregation requires minimum contributions",
        )

    def test_complete_round_updates_global_model(self):
        """FLC-055: Completed round updates global weights."""
        # Use high clip_norm so gradients pass through unchanged
        coord = FederatedCoordinator(
            initial_weights=ModelWeights(weights=[0.0, 0.0, 0.0]),
            privacy_noise_scale=0.0,
            privacy_clip_norm=100.0,
        )
        coord.register_node("n-1", "A", sample_count=100)
        rnd = coord.start_round()
        coord.submit_update(
            rnd.round_id,
            GradientUpdate("n-1", rnd.round_id, [2.0, 4.0, 6.0], sample_count=100),
        )
        coord.complete_round(rnd.round_id)
        gw = coord.get_global_weights()
        # FedAvg with one contribution: weights = [0,0,0] + [2,4,6] = [2,4,6]
        assert record(
            "FLC-055", "Global weights updated after round",
            [2.0, 4.0, 6.0], gw.weights,
            cause="Single node contributed [2,4,6] to [0,0,0]",
            effect="Global weights are now [2,4,6]",
            lesson="Global model advances after each round",
        )

    def test_insufficient_contributions_fails(self, coordinator: FederatedCoordinator):
        """FLC-056: Round fails if fewer than min_contributions."""
        coord = FederatedCoordinator(
            initial_weights=ModelWeights(weights=[0.0]),
            min_contributions=3,
            privacy_noise_scale=0.0,
        )
        coord.register_node("n-1", "A", sample_count=10)
        rnd = coord.start_round()
        coord.submit_update(
            rnd.round_id,
            GradientUpdate("n-1", rnd.round_id, [1.0], sample_count=10),
        )
        result = coord.complete_round(rnd.round_id)
        assert record(
            "FLC-056", "Insufficient contributions → None",
            None, result,
            cause="1 contribution < min_contributions=3",
            effect="Round marked FAILED",
            lesson="Set a quorum to prevent weak aggregations",
        )


class TestCoordinatorEdgeCases:
    """FLC-060–063: Edge cases and error handling."""

    def test_submit_to_unknown_round(self, coordinator: FederatedCoordinator):
        """FLC-060: Submit to non-existent round returns False."""
        update = GradientUpdate("n-1", "fake-round", [0.1], sample_count=5)
        assert record(
            "FLC-060", "Submit to unknown round rejected",
            False, coordinator.submit_update("fake-round", update),
            cause="Round does not exist",
            effect="False returned",
            lesson="Validate round existence before accepting updates",
        )

    def test_submit_from_non_participant(self, two_node_coordinator: FederatedCoordinator):
        """FLC-061: Update from non-participating node rejected."""
        rnd = two_node_coordinator.start_round(node_ids=["n-1"])
        update = GradientUpdate("n-2", rnd.round_id, [0.1], sample_count=5)
        assert record(
            "FLC-061", "Non-participant update rejected",
            False, two_node_coordinator.submit_update(rnd.round_id, update),
            cause="n-2 not in this round",
            effect="False returned",
            lesson="Enforce round membership strictly",
        )

    def test_get_status(self, two_node_coordinator: FederatedCoordinator):
        """FLC-062: get_status returns structured summary."""
        status = two_node_coordinator.get_status()
        keys_ok = all(
            k in status for k in ("total_nodes", "completed_rounds", "privacy_noise_scale")
        )
        assert record(
            "FLC-062", "Status has expected keys",
            True, keys_ok,
            cause="get_status contract",
            effect="Machine-readable federation summary",
            lesson="Always expose operational stats",
        )

    def test_list_rounds_empty(self, coordinator: FederatedCoordinator):
        """FLC-063: list_rounds returns empty list when no rounds."""
        assert record(
            "FLC-063", "No rounds → empty list",
            0, len(coordinator.list_rounds()),
            cause="No rounds started",
            effect="Empty list",
            lesson="Empty state is valid",
        )


class TestCoordinatorThreadSafety:
    """FLC-070: Concurrent access."""

    def test_concurrent_submit(self):
        """FLC-070: Concurrent gradient submissions don't lose data."""
        coord = FederatedCoordinator(
            initial_weights=ModelWeights(weights=[0.0]),
            privacy_noise_scale=0.0,
        )
        for i in range(5):
            coord.register_node(f"n-{i}", f"Node-{i}", sample_count=10)

        rnd = coord.start_round()
        barrier = threading.Barrier(5)

        def worker(nid: str) -> None:
            barrier.wait()
            update = GradientUpdate(nid, rnd.round_id, [1.0], sample_count=10)
            coord.submit_update(rnd.round_id, update)

        threads = [threading.Thread(target=worker, args=(f"n-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        retrieved = coord.get_round(rnd.round_id)
        assert record(
            "FLC-070", "5 concurrent submissions all recorded",
            5, len(retrieved.contributions) if retrieved else 0,
            cause="5 threads submitting simultaneously",
            effect="All contributions stored",
            lesson="Lock protects against concurrent writes",
        )


# ============================================================================
# WINGMAN PAIR VALIDATION GATE
# ============================================================================

class TestWingmanGate:
    """FLC-080: Wingman pair validation for aggregation output."""

    def test_wingman_validates_aggregation(self, two_node_coordinator: FederatedCoordinator):
        """FLC-080: Wingman protocol validates the aggregated model."""
        from wingman_protocol import (
            ExecutionRunbook,
            ValidationRule,
            ValidationSeverity,
            WingmanProtocol,
        )

        # Run a complete round
        rnd = two_node_coordinator.start_round()
        two_node_coordinator.submit_update(
            rnd.round_id,
            GradientUpdate("n-1", rnd.round_id, [0.5, 0.5, 0.5], sample_count=100),
        )
        two_node_coordinator.submit_update(
            rnd.round_id,
            GradientUpdate("n-2", rnd.round_id, [0.3, 0.3, 0.3], sample_count=200),
        )
        new_weights = two_node_coordinator.complete_round(rnd.round_id)

        # Set up Wingman pair
        protocol = WingmanProtocol()
        runbook = ExecutionRunbook(
            runbook_id="rb-fl-v1",
            name="Federated Aggregation Validator",
            domain="ml",
            validation_rules=[
                ValidationRule(
                    "r-001", "Must produce output",
                    "check_has_output", ValidationSeverity.BLOCK,
                ),
                ValidationRule(
                    "r-002", "No PII in output",
                    "check_no_pii", ValidationSeverity.WARN,
                ),
            ],
        )
        protocol.register_runbook(runbook)
        pair = protocol.create_pair(
            subject="federated-aggregation",
            executor_id="fl-coordinator",
            validator_id="model-integrity-checker",
            runbook_id="rb-fl-v1",
        )

        output = {
            "result": new_weights.to_dict() if new_weights else {},
            "confidence": 0.95,
        }
        validation = protocol.validate_output(pair.pair_id, output)

        assert record(
            "FLC-080", "Wingman approves federated aggregation output",
            True, validation["approved"],
            cause="Valid model weights pass all runbook checks",
            effect="Aggregation approved by wingman validator",
            lesson="Gate all model updates through Wingman pairs",
        )


# ============================================================================
# CAUSALITY SANDBOX GATING
# ============================================================================

class TestCausalitySandboxGate:
    """FLC-090: Causality Sandbox simulates model update before committing."""

    def test_sandbox_simulates_model_update(self):
        """FLC-090: CausalitySandboxEngine runs a cycle for model update."""
        from causality_sandbox import CausalitySandboxEngine

        class _ModelUpdateGap:
            gap_id = "gap-fl-model-update-001"
            category = "federated_learning"
            severity = "medium"
            description = "New aggregated model needs validation before deployment"

        class _FakeLoop:
            config = {"state": "nominal"}
            metrics = {"accuracy": 0.85}
            def get_state(self):
                return {"model_deployed": True}

        engine = CausalitySandboxEngine(
            self_fix_loop_factory=lambda: _FakeLoop(),
        )

        report = engine.run_sandbox_cycle([_ModelUpdateGap()], _FakeLoop())

        assert record(
            "FLC-090", "Sandbox cycle completes for model update",
            True, report.gaps_analyzed >= 1,
            cause="One model-update gap submitted",
            effect="Sandbox simulates and validates candidate actions",
            lesson="Never deploy untested model updates to production",
        )


# ============================================================================
# SUMMARY
# ============================================================================

@pytest.fixture(autouse=True, scope="session")
def print_summary():
    """Print a summary at the end of the session."""
    yield
    total = len(_records)
    passed = sum(1 for r in _records if r.passed)
    failed = total - passed
    print(f"\n{'=' * 70}")
    print(f" Federated Learning Coordinator: {passed}/{total} passed, {failed} failed")
    for r in _records:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} {r.check_id}: {r.description}")
    print(f"{'=' * 70}")
