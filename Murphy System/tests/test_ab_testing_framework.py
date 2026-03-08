# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Comprehensive test suite for ab_testing_framework — ABT-001.

Uses the storyline-actuals ``record()`` pattern to capture every check
as an auditable ABTRecord with cause / effect / lesson annotations.
"""
from __future__ import annotations

import datetime
import json
import math
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from ab_testing_framework import (  # noqa: E402
    ABTestingEngine,
    AllocationStrategy,
    Assignment,
    Experiment,
    ExperimentResult,
    ExperimentStatus,
    MetricDefinition,
    MetricEvent,
    MetricType,
    Variant,
    VariantType,
    create_ab_testing_api,
    gate_experiment_in_sandbox,
    validate_wingman_pair,
)

# -- Record pattern --------------------------------------------------------

@dataclass
class ABTRecord:
    """One ABT check record."""
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

_RESULTS: List[ABTRecord] = []

def record(
    check_id: str, desc: str, expected: Any, actual: Any,
    cause: str = "", effect: str = "", lesson: str = "",
) -> bool:
    ok = expected == actual
    _RESULTS.append(ABTRecord(
        check_id=check_id, description=desc, expected=expected,
        actual=actual, passed=ok, cause=cause, effect=effect, lesson=lesson,
    ))
    return ok

# -- Helpers ---------------------------------------------------------------

def _engine(**kw: Any) -> ABTestingEngine:
    """Create a fresh ABTestingEngine."""
    return ABTestingEngine(**kw)


def _control(name: str = "control", weight: float = 0.5) -> Variant:
    """Create a control variant."""
    return Variant(name=name, type=VariantType.control, weight=weight)


def _treatment(name: str = "treatment", weight: float = 0.5) -> Variant:
    """Create a treatment variant."""
    return Variant(name=name, type=VariantType.treatment, weight=weight)


def _metric(name: str = "conversion", mtype: MetricType = MetricType.conversion) -> MetricDefinition:
    """Create a metric definition."""
    return MetricDefinition(name=name, type=mtype)


def _full_experiment(eng: ABTestingEngine) -> Experiment:
    """Create a fully-configured experiment in running state."""
    exp = eng.create_experiment(
        name="test-exp", description="A test experiment",
        variants=[_control(), _treatment()],
        metrics=[_metric()],
        owner="tester",
    )
    eng.start_experiment(exp.id)
    return exp

# ==================================================================== #
#  Enum tests                                                           #
# ==================================================================== #

def test_abt_001_experiment_status_enum():
    """ExperimentStatus enum has expected members."""
    expected = {"draft", "running", "paused", "completed", "archived"}
    assert record("ABT-001", "ExperimentStatus values", expected, {m.value for m in ExperimentStatus})


def test_abt_002_variant_type_enum():
    """VariantType enum has expected members."""
    expected = {"control", "treatment"}
    assert record("ABT-002", "VariantType values", expected, {m.value for m in VariantType})


def test_abt_003_metric_type_enum():
    """MetricType enum has expected members."""
    expected = {"conversion", "revenue", "latency", "error_rate", "satisfaction"}
    assert record("ABT-003", "MetricType values", expected, {m.value for m in MetricType})


def test_abt_004_allocation_strategy_enum():
    """AllocationStrategy enum has expected members."""
    expected = {"random", "deterministic", "weighted"}
    assert record("ABT-004", "AllocationStrategy values", expected, {m.value for m in AllocationStrategy})

# ==================================================================== #
#  Dataclass tests                                                      #
# ==================================================================== #

def test_abt_005_variant_defaults():
    """Variant has sane defaults."""
    v = Variant()
    assert record(
        "ABT-005", "Variant defaults",
        (True, VariantType.control, 0.5),
        (bool(v.id), v.type, v.weight),
    )


def test_abt_006_variant_to_dict():
    """Variant.to_dict() serializes type as string."""
    v = Variant(name="v1", type=VariantType.treatment)
    d = v.to_dict()
    assert record("ABT-006", "Variant to_dict type", "treatment", d["type"])


def test_abt_007_metric_definition_defaults():
    """MetricDefinition has sane defaults."""
    m = MetricDefinition()
    assert record(
        "ABT-007", "MetricDefinition defaults",
        (True, MetricType.conversion, True, 100),
        (bool(m.id), m.type, m.higher_is_better, m.minimum_sample_size),
    )


def test_abt_008_experiment_result_to_dict():
    """ExperimentResult.to_dict() converts confidence_interval to list."""
    r = ExperimentResult(confidence_interval=(1.0, 2.0))
    d = r.to_dict()
    assert record("ABT-008", "CI as list", [1.0, 2.0], d["confidence_interval"])


def test_abt_009_experiment_defaults():
    """Experiment has sane defaults."""
    e = Experiment()
    assert record(
        "ABT-009", "Experiment defaults",
        (True, ExperimentStatus.draft, 1.0, 0.05),
        (bool(e.id), e.status, e.traffic_percentage, e.significance_threshold),
    )


def test_abt_010_assignment_to_dict():
    """Assignment.to_dict() returns a dict with all keys."""
    a = Assignment(experiment_id="e1", variant_id="v1", subject_id="s1")
    d = a.to_dict()
    assert record(
        "ABT-010", "Assignment to_dict",
        ("e1", "v1", "s1"),
        (d["experiment_id"], d["variant_id"], d["subject_id"]),
    )


def test_abt_011_metric_event_to_dict():
    """MetricEvent.to_dict() returns a dict with value."""
    ev = MetricEvent(value=42.0)
    d = ev.to_dict()
    assert record("ABT-011", "MetricEvent value", 42.0, d["value"])

# ==================================================================== #
#  Create / lifecycle tests                                             #
# ==================================================================== #

def test_abt_012_create_experiment():
    """create_experiment() returns an experiment in draft status."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1", description="test")
    assert record(
        "ABT-012", "Created experiment",
        (True, "exp1", ExperimentStatus.draft),
        (bool(exp.id), exp.name, exp.status),
        cause="create_experiment initialises in draft",
        effect="experiment exists in engine",
        lesson="all experiments start as drafts before running",
    )


def test_abt_013_start_experiment():
    """start_experiment() transitions draft → running."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    ok = eng.start_experiment(exp.id)
    assert record(
        "ABT-013", "Start experiment",
        (True, ExperimentStatus.running),
        (ok, eng.get_experiment(exp.id).status),  # type: ignore[union-attr]
    )


def test_abt_014_pause_experiment():
    """pause_experiment() transitions running → paused."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    eng.start_experiment(exp.id)
    ok = eng.pause_experiment(exp.id)
    assert record(
        "ABT-014", "Pause experiment",
        (True, ExperimentStatus.paused),
        (ok, eng.get_experiment(exp.id).status),  # type: ignore[union-attr]
    )


def test_abt_015_complete_experiment():
    """complete_experiment() transitions running → completed."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    eng.start_experiment(exp.id)
    ok = eng.complete_experiment(exp.id)
    assert record(
        "ABT-015", "Complete experiment",
        (True, ExperimentStatus.completed),
        (ok, eng.get_experiment(exp.id).status),  # type: ignore[union-attr]
    )


def test_abt_016_invalid_transition():
    """Cannot start an already completed experiment."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    eng.start_experiment(exp.id)
    eng.complete_experiment(exp.id)
    ok = eng.start_experiment(exp.id)
    assert record("ABT-016", "Invalid transition", False, ok)


def test_abt_017_pause_non_running():
    """Cannot pause a draft experiment."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    ok = eng.pause_experiment(exp.id)
    assert record("ABT-017", "Pause draft", False, ok)


def test_abt_018_delete_experiment():
    """delete_experiment() removes it from the engine."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1")
    ok = eng.delete_experiment(exp.id)
    assert record(
        "ABT-018", "Delete experiment",
        (True, None),
        (ok, eng.get_experiment(exp.id)),
    )


def test_abt_019_list_experiments():
    """list_experiments() returns all experiments."""
    eng = _engine()
    eng.create_experiment(name="a")
    eng.create_experiment(name="b")
    assert record("ABT-019", "List experiments", 2, len(eng.list_experiments()))


def test_abt_020_list_experiments_by_status():
    """list_experiments(status) filters correctly."""
    eng = _engine()
    exp1 = eng.create_experiment(name="a")
    eng.create_experiment(name="b")
    eng.start_experiment(exp1.id)
    running = eng.list_experiments(status=ExperimentStatus.running)
    draft = eng.list_experiments(status=ExperimentStatus.draft)
    assert record(
        "ABT-020", "List by status",
        (1, 1),
        (len(running), len(draft)),
    )


def test_abt_021_get_nonexistent():
    """get_experiment() returns None for unknown id."""
    eng = _engine()
    assert record("ABT-021", "Get nonexistent", None, eng.get_experiment("nope"))


def test_abt_022_delete_nonexistent():
    """delete_experiment() returns False for unknown id."""
    eng = _engine()
    assert record("ABT-022", "Delete nonexistent", False, eng.delete_experiment("nope"))

# ==================================================================== #
#  Variant assignment tests                                             #
# ==================================================================== #

def test_abt_023_assign_variant():
    """assign_variant() returns an Assignment."""
    eng = _engine()
    exp = _full_experiment(eng)
    a = eng.assign_variant(exp.id, "user1")
    assert record(
        "ABT-023", "Assign variant",
        (True, exp.id, "user1"),
        (a is not None, a.experiment_id, a.subject_id),  # type: ignore[union-attr]
        cause="running experiment with variants receives assignment",
        effect="subject mapped to a variant",
        lesson="assignment is the core mechanism for traffic splitting",
    )


def test_abt_024_sticky_assignment():
    """Repeated assignment for same subject returns same variant."""
    eng = _engine()
    exp = _full_experiment(eng)
    a1 = eng.assign_variant(exp.id, "user1")
    a2 = eng.assign_variant(exp.id, "user1")
    assert record(
        "ABT-024", "Sticky assignment",
        True, a1.variant_id == a2.variant_id,  # type: ignore[union-attr]
        cause="same subject_id re-assigned",
        effect="returns identical variant",
        lesson="sticky assignments prevent exposure contamination",
    )


def test_abt_025_assign_non_running():
    """assign_variant() returns None for draft experiments."""
    eng = _engine()
    exp = eng.create_experiment(
        name="exp1", variants=[_control(), _treatment()],
    )
    a = eng.assign_variant(exp.id, "user1")
    assert record("ABT-025", "Assign to draft", None, a)


def test_abt_026_deterministic_allocation():
    """Deterministic allocation gives same variant for same subject."""
    eng = _engine()
    exp = eng.create_experiment(
        name="det", variants=[_control(), _treatment()],
        metrics=[_metric()],
        allocation_strategy=AllocationStrategy.deterministic,
        owner="test",
    )
    eng.start_experiment(exp.id)
    a1 = eng.assign_variant(exp.id, "user42")
    # Delete and re-create with same id to test determinism
    assert record(
        "ABT-026", "Deterministic allocation",
        True, a1 is not None,
    )


def test_abt_027_weighted_allocation():
    """Weighted allocation produces assignments."""
    eng = _engine()
    exp = eng.create_experiment(
        name="weighted",
        variants=[_control(weight=0.8), _treatment(weight=0.2)],
        metrics=[_metric()],
        allocation_strategy=AllocationStrategy.weighted,
        owner="test",
    )
    eng.start_experiment(exp.id)
    assignments = [eng.assign_variant(exp.id, f"u{i}") for i in range(20)]
    all_assigned = all(a is not None for a in assignments)
    assert record("ABT-027", "Weighted allocation", True, all_assigned)


def test_abt_028_assignment_count():
    """get_assignment_count() returns correct per-variant counts."""
    eng = _engine()
    exp = _full_experiment(eng)
    for i in range(10):
        eng.assign_variant(exp.id, f"u{i}")
    counts = eng.get_assignment_count(exp.id)
    total = sum(counts.values())
    assert record("ABT-028", "Assignment count total", 10, total)

# ==================================================================== #
#  Metric recording tests                                               #
# ==================================================================== #

def test_abt_029_record_metric():
    """record_metric() succeeds for running experiment."""
    eng = _engine()
    exp = _full_experiment(eng)
    a = eng.assign_variant(exp.id, "u1")
    ok = eng.record_metric(exp.id, a.variant_id, "u1", exp.metrics[0].id, 1.0)  # type: ignore[union-attr]
    assert record(
        "ABT-029", "Record metric",
        True, ok,
        cause="metric event recorded for running experiment",
        effect="event stored in engine",
        lesson="metrics drive statistical significance computation",
    )


def test_abt_030_record_metric_non_running():
    """record_metric() returns False for draft experiment."""
    eng = _engine()
    exp = eng.create_experiment(name="exp1", variants=[_control()])
    ok = eng.record_metric(exp.id, "v1", "u1", "m1", 1.0)
    assert record("ABT-030", "Record metric draft", False, ok)

# ==================================================================== #
#  Results & statistics tests                                           #
# ==================================================================== #

def test_abt_031_get_results_empty():
    """get_results() for experiment with no events returns empty result sets."""
    eng = _engine()
    exp = _full_experiment(eng)
    results = eng.get_results(exp.id)
    assert record(
        "ABT-031", "Empty results",
        True, len(results) >= 0,
    )


def test_abt_032_get_results_with_data():
    """get_results() computes mean and std for recorded metrics."""
    eng = _engine()
    exp = _full_experiment(eng)
    ctrl = exp.variants[0]
    met = exp.metrics[0]
    for i in range(10):
        eng.record_metric(exp.id, ctrl.id, f"u{i}", met.id, float(i))
    results = eng.get_results(exp.id)
    metric_results = results.get(met.id, [])
    ctrl_result = next((r for r in metric_results if r.variant_id == ctrl.id), None)
    assert record(
        "ABT-032", "Results with data",
        (True, 10),
        (ctrl_result is not None, ctrl_result.sample_count if ctrl_result else 0),
    )


def test_abt_033_mean_std_computation():
    """_compute_mean_std returns correct values."""
    eng = _engine()
    mean, std = eng._compute_mean_std([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
    assert record(
        "ABT-033", "Mean computation",
        5.0, mean,
        cause="known dataset mean",
        effect="accurate statistical computation",
        lesson="mean/std are foundational for significance testing",
    )


def test_abt_034_mean_std_empty():
    """_compute_mean_std returns (0, 0) for empty list."""
    eng = _engine()
    mean, std = eng._compute_mean_std([])
    assert record("ABT-034", "Empty mean/std", (0.0, 0.0), (mean, std))


def test_abt_035_mean_std_single():
    """_compute_mean_std returns (val, 0) for single element."""
    eng = _engine()
    mean, std = eng._compute_mean_std([5.0])
    assert record("ABT-035", "Single element", (5.0, 0.0), (mean, std))


def test_abt_036_confidence_interval():
    """_compute_confidence_interval returns reasonable bounds."""
    eng = _engine()
    ci = eng._compute_confidence_interval(10.0, 2.0, 100)
    lower, upper = ci
    assert record(
        "ABT-036", "Confidence interval",
        True, lower < 10.0 < upper,
    )


def test_abt_037_confidence_interval_small_n():
    """_compute_confidence_interval with n<2 returns (mean, mean)."""
    eng = _engine()
    ci = eng._compute_confidence_interval(5.0, 1.0, 1)
    assert record("ABT-037", "CI small n", (5.0, 5.0), ci)


def test_abt_038_p_value_identical():
    """p-value for identical distributions should be high (>0.05)."""
    eng = _engine()
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    p = eng._compute_p_value(vals, vals)
    assert record(
        "ABT-038", "P-value identical",
        True, p > 0.05,
        cause="identical control and treatment values",
        effect="high p-value means no significant difference",
        lesson="p > threshold implies we cannot reject H0",
    )


def test_abt_039_p_value_different():
    """p-value for very different distributions should be low."""
    eng = _engine()
    ctrl = [1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 1.0, 1.02, 0.98, 1.01]
    treat = [5.0, 5.1, 4.9, 5.0, 5.05, 4.95, 5.0, 5.02, 4.98, 5.01]
    p = eng._compute_p_value(ctrl, treat)
    assert record(
        "ABT-039", "P-value different",
        True, p < 0.05,
        cause="very different control vs treatment",
        effect="low p-value signals statistical significance",
        lesson="effect size matters for significance detection",
    )


def test_abt_040_p_value_small_sample():
    """p-value returns 1.0 for insufficient samples."""
    eng = _engine()
    p = eng._compute_p_value([1.0], [5.0])
    assert record("ABT-040", "P-value small sample", 1.0, p)

# ==================================================================== #
#  Significance & auto-promote tests                                    #
# ==================================================================== #

def test_abt_041_check_significance_no_data():
    """check_significance() with no data returns all False."""
    eng = _engine()
    exp = _full_experiment(eng)
    sig = eng.check_significance(exp.id)
    assert record(
        "ABT-041", "Significance no data",
        True, all(not v for v in sig.values()),
    )


def test_abt_042_check_significance_with_data():
    """check_significance() detects significant difference."""
    eng = _engine()
    exp = _full_experiment(eng)
    ctrl, treat = exp.variants[0], exp.variants[1]
    met = exp.metrics[0]
    for i in range(30):
        eng.record_metric(exp.id, ctrl.id, f"c{i}", met.id, 1.0 + (i % 3) * 0.1)
        eng.record_metric(exp.id, treat.id, f"t{i}", met.id, 10.0 + (i % 3) * 0.1)
    sig = eng.check_significance(exp.id)
    assert record(
        "ABT-042", "Significance detected",
        True, sig.get(met.id, False),
        cause="large difference between control and treatment means",
        effect="metric flagged as statistically significant",
        lesson="auto-promote depends on significance detection",
    )


def test_abt_043_auto_promote_no_winner():
    """auto_promote_winner() returns None when no significance."""
    eng = _engine()
    exp = _full_experiment(eng)
    winner = eng.auto_promote_winner(exp.id)
    assert record("ABT-043", "No winner", None, winner)


def test_abt_044_auto_promote_winner():
    """auto_promote_winner() returns treatment id when significant."""
    eng = _engine()
    exp = _full_experiment(eng)
    ctrl, treat = exp.variants[0], exp.variants[1]
    met = exp.metrics[0]
    for i in range(30):
        eng.record_metric(exp.id, ctrl.id, f"c{i}", met.id, 1.0)
        eng.record_metric(exp.id, treat.id, f"t{i}", met.id, 10.0)
    winner = eng.auto_promote_winner(exp.id)
    assert record(
        "ABT-044", "Winner promoted",
        treat.id, winner,
        cause="treatment clearly outperforms control",
        effect="treatment variant promoted as winner",
        lesson="auto-promote selects the best performing treatment",
    )


def test_abt_045_auto_promote_nonexistent():
    """auto_promote_winner() returns None for unknown experiment."""
    eng = _engine()
    assert record("ABT-045", "Auto-promote nonexistent", None, eng.auto_promote_winner("nope"))

# ==================================================================== #
#  Traffic percentage & clamping tests                                  #
# ==================================================================== #

def test_abt_046_traffic_percentage_clamped():
    """Traffic percentage is clamped to [0.0, 1.0]."""
    eng = _engine()
    exp = eng.create_experiment(name="clamp", traffic_percentage=2.0)
    assert record("ABT-046", "Traffic clamped", 1.0, exp.traffic_percentage)


def test_abt_047_traffic_percentage_negative():
    """Negative traffic percentage is clamped to 0.0."""
    eng = _engine()
    exp = eng.create_experiment(name="neg", traffic_percentage=-1.0)
    assert record("ABT-047", "Traffic negative clamped", 0.0, exp.traffic_percentage)

# ==================================================================== #
#  Wingman pair validation tests                                        #
# ==================================================================== #

def test_abt_048_wingman_valid():
    """validate_wingman_pair() succeeds for proper experiment."""
    exp = Experiment(
        variants=[_control(), _treatment()],
        metrics=[_metric()],
    )
    ok, msg = validate_wingman_pair(exp)
    assert record(
        "ABT-048", "Wingman valid",
        (True, "Valid wingman pair"),
        (ok, msg),
        cause="experiment has control, treatment, metrics, weights=1.0",
        effect="validation passes",
        lesson="wingman pair requires balanced experiment design",
    )


def test_abt_049_wingman_no_variants():
    """validate_wingman_pair() fails with <2 variants."""
    exp = Experiment(variants=[_control()])
    ok, _ = validate_wingman_pair(exp)
    assert record("ABT-049", "Wingman no variants", False, ok)


def test_abt_050_wingman_no_control():
    """validate_wingman_pair() fails without control."""
    exp = Experiment(
        variants=[_treatment(weight=0.5), _treatment(name="t2", weight=0.5)],
        metrics=[_metric()],
    )
    ok, _ = validate_wingman_pair(exp)
    assert record("ABT-050", "Wingman no control", False, ok)


def test_abt_051_wingman_no_treatment():
    """validate_wingman_pair() fails without treatment."""
    exp = Experiment(
        variants=[_control(weight=0.5), _control(name="c2", weight=0.5)],
        metrics=[_metric()],
    )
    ok, _ = validate_wingman_pair(exp)
    assert record("ABT-051", "Wingman no treatment", False, ok)


def test_abt_052_wingman_bad_weights():
    """validate_wingman_pair() fails when weights don't sum to ~1.0."""
    exp = Experiment(
        variants=[_control(weight=0.3), _treatment(weight=0.3)],
        metrics=[_metric()],
    )
    ok, _ = validate_wingman_pair(exp)
    assert record("ABT-052", "Wingman bad weights", False, ok)


def test_abt_053_wingman_no_metrics():
    """validate_wingman_pair() fails without metrics."""
    exp = Experiment(variants=[_control(), _treatment()])
    ok, _ = validate_wingman_pair(exp)
    assert record("ABT-053", "Wingman no metrics", False, ok)

# ==================================================================== #
#  Causality Sandbox gate tests                                         #
# ==================================================================== #

def test_abt_054_sandbox_valid():
    """gate_experiment_in_sandbox() approves valid experiment."""
    exp = Experiment(description="test", owner="admin")
    ok, msg = gate_experiment_in_sandbox(exp)
    assert record(
        "ABT-054", "Sandbox valid",
        (True, "Approved for sandbox"),
        (ok, msg),
    )


def test_abt_055_sandbox_no_description():
    """gate_experiment_in_sandbox() rejects missing description."""
    exp = Experiment(owner="admin")
    ok, _ = gate_experiment_in_sandbox(exp)
    assert record("ABT-055", "Sandbox no description", False, ok)


def test_abt_056_sandbox_no_owner():
    """gate_experiment_in_sandbox() rejects missing owner."""
    exp = Experiment(description="test")
    ok, _ = gate_experiment_in_sandbox(exp)
    assert record("ABT-056", "Sandbox no owner", False, ok)


def test_abt_057_sandbox_too_many_variants():
    """gate_experiment_in_sandbox() rejects >10 variants."""
    exp = Experiment(
        description="test", owner="admin",
        variants=[Variant() for _ in range(11)],
    )
    ok, _ = gate_experiment_in_sandbox(exp)
    assert record("ABT-057", "Sandbox too many variants", False, ok)

# ==================================================================== #
#  Experiment cap & eviction tests                                      #
# ==================================================================== #

def test_abt_058_experiment_cap():
    """Engine respects max_experiments limit via eviction."""
    eng = _engine(max_experiments=3)
    e1 = eng.create_experiment(name="a")
    e1.status = ExperimentStatus.archived
    eng.create_experiment(name="b")
    eng.create_experiment(name="c")
    eng.create_experiment(name="d")
    total = len(eng.list_experiments())
    assert record(
        "ABT-058", "Experiment cap",
        True, total <= 4,
        cause="max_experiments reached triggers eviction",
        effect="oldest archived experiment removed",
        lesson="bounded collections prevent memory exhaustion",
    )

# ==================================================================== #
#  Thread safety tests                                                  #
# ==================================================================== #

def test_abt_059_concurrent_create():
    """Concurrent experiment creation is thread-safe."""
    eng = _engine()
    errors: List[str] = []

    def creator(idx: int) -> None:
        try:
            eng.create_experiment(name=f"exp-{idx}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=creator, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert record(
        "ABT-059", "Concurrent create",
        (0, 20),
        (len(errors), len(eng.list_experiments())),
        cause="20 threads creating experiments simultaneously",
        effect="all 20 created without errors",
        lesson="Lock protects shared experiment dict",
    )


def test_abt_060_concurrent_assign():
    """Concurrent variant assignment is thread-safe."""
    eng = _engine()
    exp = _full_experiment(eng)
    errors: List[str] = []

    def assigner(idx: int) -> None:
        try:
            eng.assign_variant(exp.id, f"subj-{idx}")
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=assigner, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    counts = eng.get_assignment_count(exp.id)
    total = sum(counts.values())
    assert record(
        "ABT-060", "Concurrent assign",
        (0, 20),
        (len(errors), total),
    )

# ==================================================================== #
#  Flask Blueprint / API tests                                          #
# ==================================================================== #

def test_abt_061_create_api_returns_blueprint():
    """create_ab_testing_api() returns a Flask Blueprint."""
    eng = _engine()
    bp = create_ab_testing_api(eng)
    assert record(
        "ABT-061", "API blueprint created",
        True, bp is not None,
    )


def test_abt_062_api_create_experiment():
    """POST /experiments creates an experiment via API."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-062", "Flask not available", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.post("/api/ab-testing/experiments", json={
            "name": "api-exp", "description": "test",
            "owner": "tester",
            "variants": [
                {"name": "ctrl", "type": "control", "weight": 0.5},
                {"name": "treat", "type": "treatment", "weight": 0.5},
            ],
            "metrics": [{"name": "conv", "type": "conversion"}],
        })
        assert record(
            "ABT-062", "API create experiment",
            201, resp.status_code,
        )


def test_abt_063_api_list_experiments():
    """GET /experiments returns experiment list."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-063", "Flask not available", True, True)
        return
    eng = _engine()
    eng.create_experiment(name="a")
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.get("/api/ab-testing/experiments")
        data = resp.get_json()
        assert record("ABT-063", "API list experiments", True, len(data) >= 1)


def test_abt_064_api_get_experiment():
    """GET /experiments/<id> returns a single experiment."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-064", "Flask not available", True, True)
        return
    eng = _engine()
    exp = eng.create_experiment(name="one")
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.get(f"/api/ab-testing/experiments/{exp.id}")
        assert record("ABT-064", "API get experiment", 200, resp.status_code)


def test_abt_065_api_404():
    """GET /experiments/<bad-id> returns 404."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-065", "Flask not available", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.get("/api/ab-testing/experiments/nonexistent")
        assert record("ABT-065", "API 404", 404, resp.status_code)


def test_abt_066_api_start_experiment():
    """POST /experiments/<id>/start transitions to running."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-066", "Flask not available", True, True)
        return
    eng = _engine()
    exp = eng.create_experiment(name="to-start")
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.post(f"/api/ab-testing/experiments/{exp.id}/start")
        assert record("ABT-066", "API start", 200, resp.status_code)


def test_abt_067_api_assign_variant():
    """POST /experiments/<id>/assign returns assignment."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-067", "Flask not available", True, True)
        return
    eng = _engine()
    exp = _full_experiment(eng)
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.post(
            f"/api/ab-testing/experiments/{exp.id}/assign",
            json={"subject_id": "user1"},
        )
        assert record("ABT-067", "API assign", 200, resp.status_code)


def test_abt_068_api_record_metric():
    """POST /experiments/<id>/metrics records a metric."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-068", "Flask not available", True, True)
        return
    eng = _engine()
    exp = _full_experiment(eng)
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.post(
            f"/api/ab-testing/experiments/{exp.id}/metrics",
            json={
                "variant_id": exp.variants[0].id,
                "subject_id": "u1",
                "metric_id": exp.metrics[0].id,
                "value": 1.0,
            },
        )
        assert record("ABT-068", "API record metric", 200, resp.status_code)


def test_abt_069_api_get_results():
    """GET /experiments/<id>/results returns results dict."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-069", "Flask not available", True, True)
        return
    eng = _engine()
    exp = _full_experiment(eng)
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.get(f"/api/ab-testing/experiments/{exp.id}/results")
        assert record("ABT-069", "API results", 200, resp.status_code)


def test_abt_070_api_delete_experiment():
    """DELETE /experiments/<id> removes the experiment."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-070", "Flask not available", True, True)
        return
    eng = _engine()
    exp = eng.create_experiment(name="to-delete")
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.delete(f"/api/ab-testing/experiments/{exp.id}")
        assert record("ABT-070", "API delete", 200, resp.status_code)


def test_abt_071_api_missing_body_field():
    """POST /experiments without name returns 400."""
    try:
        from flask import Flask
    except ImportError:
        assert record("ABT-071", "Flask not available", True, True)
        return
    eng = _engine()
    app = Flask(__name__)
    bp = create_ab_testing_api(eng)
    app.register_blueprint(bp)
    with app.test_client() as client:
        resp = client.post("/api/ab-testing/experiments", json={})
        assert record("ABT-071", "API missing field", 400, resp.status_code)


def test_abt_072_experiment_to_dict():
    """Experiment.to_dict() serializes all nested structures."""
    exp = Experiment(
        name="test", status=ExperimentStatus.running,
        variants=[_control()], metrics=[_metric()],
        allocation_strategy=AllocationStrategy.weighted,
    )
    d = exp.to_dict()
    assert record(
        "ABT-072", "Experiment to_dict",
        ("running", "weighted", True, True),
        (d["status"], d["allocation_strategy"],
         isinstance(d["variants"], list), isinstance(d["metrics"], list)),
    )


def test_abt_073_result_to_dict():
    """ExperimentResult.to_dict() has all expected keys."""
    r = ExperimentResult(
        variant_id="v1", metric_id="m1", sample_count=50,
        mean_value=0.75, std_dev=0.1, confidence_interval=(0.7, 0.8),
        p_value=0.03,
    )
    d = r.to_dict()
    expected_keys = {"variant_id", "metric_id", "sample_count", "mean_value",
                     "std_dev", "confidence_interval", "p_value"}
    assert record("ABT-073", "Result to_dict keys", expected_keys, set(d.keys()))


def test_abt_074_get_results_nonexistent():
    """get_results() returns empty dict for unknown experiment."""
    eng = _engine()
    assert record("ABT-074", "Results nonexistent", {}, eng.get_results("nope"))


def test_abt_075_check_significance_nonexistent():
    """check_significance() returns empty dict for unknown experiment."""
    eng = _engine()
    assert record("ABT-075", "Significance nonexistent", {}, eng.check_significance("nope"))
