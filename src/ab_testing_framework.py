# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""A/B Testing Framework for Murphy's Decision Engine — ABT-001

Owner: Platform Engineering · Dep: thread_safe_operations (capped_append)

Split traffic between experiment variants, measure outcomes, and
auto-promote winners using simplified statistical significance testing.

Classes: ExperimentStatus/VariantType/MetricType/AllocationStrategy (enums),
Variant/MetricDefinition/ExperimentResult/Experiment/Assignment/MetricEvent
(dataclasses), ABTestingEngine (thread-safe orchestrator).
``create_ab_testing_api(engine)`` returns a Flask Blueprint (JSON error envelope).

Safety: all mutable state under threading.Lock; bounded lists via capped_append;
no external dependencies beyond stdlib + Flask.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from flask import Blueprint, jsonify, request
    _HAS_FLASK = True
except ImportError:
    _HAS_FLASK = False
    Blueprint = type("Blueprint", (), {"__init__": lambda self, *a, **k: None, "route": lambda *a, **k: lambda f: f})  # type: ignore[assignment,misc]
    def jsonify(*_a: Any, **_k: Any) -> dict:  # type: ignore[misc]
        return {}
    class _FakeReq:  # type: ignore[no-redef]
        args: dict = {}
        @staticmethod
        def get_json(silent: bool = True) -> dict: return {}
    request = _FakeReq()  # type: ignore[assignment]

try:
    from .blueprint_auth import require_blueprint_auth
except ImportError:
    from blueprint_auth import require_blueprint_auth  # type: ignore[no-redef]
try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max(1, max_size // 10)]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ── Enums ─────────────────────────────────────────────────────────────────

class ExperimentStatus(str, Enum):
    """Lifecycle status of an experiment."""
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"
    archived = "archived"

class VariantType(str, Enum):
    """Whether a variant is a control or a treatment."""
    control = "control"
    treatment = "treatment"

class MetricType(str, Enum):
    """Category of metric being tracked."""
    conversion = "conversion"
    revenue = "revenue"
    latency = "latency"
    error_rate = "error_rate"
    satisfaction = "satisfaction"

class AllocationStrategy(str, Enum):
    """How subjects are allocated to variants."""
    random = "random"
    deterministic = "deterministic"
    weighted = "weighted"

# ── Dataclasses ───────────────────────────────────────────────────────────

@dataclass
class Variant:
    """A single variant within an experiment."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    type: VariantType = VariantType.control
    weight: float = 0.5
    config: Dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["type"] = self.type.value
        return d

@dataclass
class MetricDefinition:
    """Definition of a metric to track in an experiment."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    type: MetricType = MetricType.conversion
    higher_is_better: bool = True
    minimum_sample_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["type"] = self.type.value
        return d

@dataclass
class ExperimentResult:
    """Statistical result for one variant + metric pair."""
    variant_id: str = ""
    metric_id: str = ""
    sample_count: int = 0
    mean_value: float = 0.0
    std_dev: float = 0.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    p_value: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["confidence_interval"] = list(self.confidence_interval)
        return d

@dataclass
class Experiment:
    """An A/B experiment grouping variants, metrics, and configuration."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.draft
    variants: List[Variant] = field(default_factory=list)
    metrics: List[MetricDefinition] = field(default_factory=list)
    allocation_strategy: AllocationStrategy = AllocationStrategy.random
    traffic_percentage: float = 1.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner: str = ""
    tags: List[str] = field(default_factory=list)
    auto_promote: bool = False
    significance_threshold: float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        d = asdict(self)
        d["status"] = self.status.value
        d["allocation_strategy"] = self.allocation_strategy.value
        d["variants"] = [v.to_dict() for v in self.variants]
        d["metrics"] = [m.to_dict() for m in self.metrics]
        return d

@dataclass
class Assignment:
    """Record of a subject being assigned to a variant."""
    experiment_id: str = ""
    variant_id: str = ""
    subject_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

@dataclass
class MetricEvent:
    """A single metric observation for a subject in a variant."""
    experiment_id: str = ""
    variant_id: str = ""
    subject_id: str = ""
    metric_id: str = ""
    value: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to plain dict."""
        return asdict(self)

# ── ABTestingEngine ───────────────────────────────────────────────────────

class ABTestingEngine:
    """Thread-safe A/B testing orchestrator.

    Parameters
    ----------
    max_experiments:
        Maximum experiments retained in memory.
    max_events:
        Maximum metric events retained in memory.
    """

    def __init__(self, max_experiments: int = 1_000, max_events: int = 100_000) -> None:
        self._lock = threading.Lock()
        self._experiments: Dict[str, Experiment] = {}
        self._assignments: List[Assignment] = []
        self._events: List[MetricEvent] = []
        self._subject_map: Dict[str, Dict[str, str]] = {}  # exp_id -> {subj -> var}
        self._max_experiments = max_experiments
        self._max_events = max_events

    # ── experiment CRUD ───────────────────────────────────────────────────

    def create_experiment(
        self, name: str, description: str = "",
        variants: Optional[List[Variant]] = None,
        metrics: Optional[List[MetricDefinition]] = None,
        allocation_strategy: AllocationStrategy = AllocationStrategy.random,
        traffic_percentage: float = 1.0, owner: str = "",
        tags: Optional[List[str]] = None, auto_promote: bool = False,
        significance_threshold: float = 0.05,
    ) -> Experiment:
        """Create a new experiment in *draft* status."""
        traffic_pct = max(0.0, min(traffic_percentage, 1.0))
        if traffic_pct != traffic_percentage:
            logger.warning("traffic_percentage clamped from %s to %s", traffic_percentage, traffic_pct)
        exp = Experiment(
            name=name, description=description,
            variants=variants or [], metrics=metrics or [],
            allocation_strategy=allocation_strategy,
            traffic_percentage=traffic_pct,
            owner=owner, tags=tags or [],
            auto_promote=auto_promote, significance_threshold=significance_threshold,
        )
        with self._lock:
            if len(self._experiments) >= self._max_experiments:
                logger.warning("Experiment cap reached (%d)", self._max_experiments)
                self._evict_oldest_archived()
            self._experiments[exp.id] = exp
        logger.info("Experiment created: %s (%s)", exp.name, exp.id)
        return exp

    def start_experiment(self, experiment_id: str) -> bool:
        """Transition an experiment from draft/paused → running."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or exp.status not in (ExperimentStatus.draft, ExperimentStatus.paused):
                return False
            exp.status = ExperimentStatus.running
            exp.start_time = datetime.now(timezone.utc).isoformat()
        logger.info("Experiment started: %s", experiment_id)
        return True

    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause a running experiment."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or exp.status != ExperimentStatus.running:
                return False
            exp.status = ExperimentStatus.paused
        logger.info("Experiment paused: %s", experiment_id)
        return True

    def complete_experiment(self, experiment_id: str) -> bool:
        """Mark an experiment as completed."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or exp.status not in (ExperimentStatus.running, ExperimentStatus.paused):
                return False
            exp.status = ExperimentStatus.completed
            exp.end_time = datetime.now(timezone.utc).isoformat()
        logger.info("Experiment completed: %s", experiment_id)
        return True

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Return an experiment by id, or *None*."""
        with self._lock:
            return self._experiments.get(experiment_id)

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Experiment]:
        """Return experiments, optionally filtered by status."""
        with self._lock:
            exps = list(self._experiments.values())
        if status is not None:
            exps = [e for e in exps if e.status == status]
        return exps

    def delete_experiment(self, experiment_id: str) -> bool:
        """Remove an experiment from memory."""
        with self._lock:
            return self._experiments.pop(experiment_id, None) is not None

    # ── variant assignment ────────────────────────────────────────────────

    def assign_variant(
        self, experiment_id: str, subject_id: str, context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Assignment]:
        """Assign a subject to a variant. Returns existing assignment on repeat."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or exp.status != ExperimentStatus.running or not exp.variants:
                return None
            existing = self._find_existing_assignment(experiment_id, subject_id)
            if existing:
                return existing
            variant = self._allocate_variant(exp, subject_id, context)
            assignment = Assignment(
                experiment_id=experiment_id, variant_id=variant.id,
                subject_id=subject_id, context=context or {},
            )
            capped_append(self._assignments, assignment, self._max_events)
            self._subject_map.setdefault(experiment_id, {})[subject_id] = variant.id
        logger.debug("Assigned %s → %s in %s", subject_id, variant.id, experiment_id)
        return assignment

    # ── metrics ───────────────────────────────────────────────────────────

    def record_metric(
        self, experiment_id: str, variant_id: str, subject_id: str,
        metric_id: str, value: float, metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a metric event for a subject in a variant."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp or exp.status != ExperimentStatus.running:
                return False
            event = MetricEvent(
                experiment_id=experiment_id, variant_id=variant_id,
                subject_id=subject_id, metric_id=metric_id,
                value=value, metadata=metadata or {},
            )
            capped_append(self._events, event, self._max_events)
        return True

    # ── results & significance ────────────────────────────────────────────

    def get_results(self, experiment_id: str) -> Dict[str, List[ExperimentResult]]:
        """Compute per-variant, per-metric statistics."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return {}
            events = [e for e in self._events if e.experiment_id == experiment_id]
        return self._build_results(exp, events)

    def check_significance(self, experiment_id: str) -> Dict[str, bool]:
        """Check statistical significance for each metric."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return {}
            events = [e for e in self._events if e.experiment_id == experiment_id]
        return self._evaluate_significance(exp, events)

    def auto_promote_winner(self, experiment_id: str) -> Optional[str]:
        """If a treatment is statistically significant, return its id."""
        with self._lock:
            exp = self._experiments.get(experiment_id)
            if not exp:
                return None
            events = [e for e in self._events if e.experiment_id == experiment_id]
        sig = self._evaluate_significance(exp, events)
        winner = self._pick_winner(exp, events, sig)
        if winner:
            logger.info("Auto-promoted winner %s for %s", winner, experiment_id)
        return winner

    def get_assignment_count(self, experiment_id: str) -> Dict[str, int]:
        """Return number of assignments per variant."""
        with self._lock:
            mapping = self._subject_map.get(experiment_id, {})
            counts: Dict[str, int] = {}
            for vid in mapping.values():
                counts[vid] = counts.get(vid, 0) + 1
        return counts

    # ── private: statistics ───────────────────────────────────────────────

    @staticmethod
    def _compute_mean_std(values: List[float]) -> Tuple[float, float]:
        """Return (mean, std_dev) for *values*."""
        if not values:
            return 0.0, 0.0
        n = len(values)
        mean = sum(values) / n
        if n < 2:
            return mean, 0.0
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return mean, math.sqrt(variance)

    @staticmethod
    def _compute_confidence_interval(
        mean: float, std: float, n: int, confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Return (lower, upper) confidence interval using z-approximation."""
        if n < 2 or std == 0.0:
            return (mean, mean)
        z_map = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_map.get(confidence, 1.96)
        margin = z * (std / math.sqrt(n))
        return (mean - margin, mean + margin)

    @staticmethod
    def _compute_p_value(control_values: List[float], treatment_values: List[float]) -> float:
        """Simplified Welch's t-test (stdlib only, no scipy)."""
        n1, n2 = len(control_values), len(treatment_values)
        if n1 < 2 or n2 < 2:
            return 1.0
        m1, m2 = sum(control_values) / n1, sum(treatment_values) / n2
        v1 = sum((x - m1) ** 2 for x in control_values) / (n1 - 1)
        v2 = sum((x - m2) ** 2 for x in treatment_values) / (n2 - 1)
        denom = v1 / n1 + v2 / n2
        se = math.sqrt(denom) if denom > 0 else 0.0
        if se == 0.0:
            return 1.0 if m1 == m2 else 0.0
        t_stat = abs(m1 - m2) / se
        df_num = denom ** 2
        df_den = ((v1 / n1) ** 2 / (n1 - 1)) + ((v2 / n2) ** 2 / (n2 - 1))
        df = df_num / df_den if df_den > 0 else 1.0
        return ABTestingEngine._t_to_p(t_stat, df)

    @staticmethod
    def _t_to_p(t: float, df: float) -> float:
        """Approximate two-tailed p-value from t-statistic and df."""
        x = df / (df + t * t)
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        return max(0.0, min(ABTestingEngine._regularized_beta(x, df / 2.0, 0.5), 1.0))

    @staticmethod
    def _regularized_beta(x: float, a: float, b: float, n_iter: int = 200) -> float:
        """Continued-fraction approximation of the regularized incomplete beta."""
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - ln_beta) / a
        f, c, d = 1.0, 1.0, 0.0
        for i in range(n_iter):
            m = i // 2
            if i == 0:
                num = 1.0
            elif i % 2 == 0:
                num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
            d = 1.0 + num * d
            d = 1.0 / d if abs(d) > 1e-30 else 1e30
            c = 1.0 + num / c if abs(1.0 + num / c) > 1e-30 else 1e-30
            f *= c * d
            if abs(c * d - 1.0) < 1e-10:
                break
        return front * (f - 1.0)

    # ── private: allocation ───────────────────────────────────────────────

    def _allocate_variant(
        self, experiment: Experiment, subject_id: str, context: Optional[dict],
    ) -> Variant:
        """Pick a variant based on the experiment's allocation strategy."""
        if experiment.allocation_strategy == AllocationStrategy.deterministic:
            return self._deterministic_allocate(experiment, subject_id)
        if experiment.allocation_strategy == AllocationStrategy.weighted:
            return self._weighted_allocate(experiment)
        return random.choice(experiment.variants)

    @staticmethod
    def _deterministic_allocate(experiment: Experiment, subject_id: str) -> Variant:
        """Hash-based deterministic allocation."""
        h = hashlib.sha256(f"{experiment.id}:{subject_id}".encode()).hexdigest()
        return experiment.variants[int(h, 16) % len(experiment.variants)]

    @staticmethod
    def _weighted_allocate(experiment: Experiment) -> Variant:
        """Weighted random selection respecting variant weights."""
        weights = [v.weight for v in experiment.variants]
        total = sum(weights)
        if total <= 0:
            return random.choice(experiment.variants)
        r, cumulative = random.random() * total, 0.0
        for variant in experiment.variants:
            cumulative += variant.weight
            if r <= cumulative:
                return variant
        return experiment.variants[-1]

    # ── private: results helpers ──────────────────────────────────────────

    def _build_results(
        self, exp: Experiment, events: List[MetricEvent],
    ) -> Dict[str, List[ExperimentResult]]:
        """Build ExperimentResult list keyed by metric id."""
        grouped = self._group_events(events)
        results: Dict[str, List[ExperimentResult]] = {}
        for metric in exp.metrics:
            metric_results: List[ExperimentResult] = []
            for variant in exp.variants:
                values = grouped.get((variant.id, metric.id), [])
                mean, std = self._compute_mean_std(values)
                ci = self._compute_confidence_interval(mean, std, len(values))
                metric_results.append(ExperimentResult(
                    variant_id=variant.id, metric_id=metric.id,
                    sample_count=len(values), mean_value=mean,
                    std_dev=std, confidence_interval=ci, p_value=1.0,
                ))
            results[metric.id] = metric_results
        return results

    @staticmethod
    def _group_events(events: List[MetricEvent]) -> Dict[Tuple[str, str], List[float]]:
        """Group event values by (variant_id, metric_id)."""
        grouped: Dict[Tuple[str, str], List[float]] = {}
        for ev in events:
            grouped.setdefault((ev.variant_id, ev.metric_id), []).append(ev.value)
        return grouped

    def _evaluate_significance(
        self, exp: Experiment, events: List[MetricEvent],
    ) -> Dict[str, bool]:
        """Return {metric_id: is_significant} for each metric."""
        grouped = self._group_events(events)
        control = self._find_control(exp)
        return {m.id: self._metric_is_significant(exp, m, control, grouped) for m in exp.metrics}

    @staticmethod
    def _find_control(exp: Experiment) -> Optional[Variant]:
        """Return the first control variant, if any."""
        for v in exp.variants:
            if v.type == VariantType.control:
                return v
        return None

    def _metric_is_significant(
        self, exp: Experiment, metric: MetricDefinition,
        control: Optional[Variant], grouped: Dict[Tuple[str, str], List[float]],
    ) -> bool:
        """Check if any treatment beats control for a given metric."""
        if not control:
            return False
        ctrl_vals = grouped.get((control.id, metric.id), [])
        for variant in exp.variants:
            if variant.type != VariantType.treatment:
                continue
            treat_vals = grouped.get((variant.id, metric.id), [])
            if self._compute_p_value(ctrl_vals, treat_vals) < exp.significance_threshold:
                return True
        return False

    def _pick_winner(
        self, exp: Experiment, events: List[MetricEvent], sig: Dict[str, bool],
    ) -> Optional[str]:
        """Return the best treatment variant id if significance reached."""
        if not any(sig.values()):
            return None
        grouped = self._group_events(events)
        control = self._find_control(exp)
        if not control:
            return None
        best_id: Optional[str] = None
        best_score = float("-inf")
        for variant in exp.variants:
            if variant.type != VariantType.treatment:
                continue
            score = self._variant_score(variant, exp.metrics, grouped)
            if score > best_score:
                best_score, best_id = score, variant.id
        return best_id

    @staticmethod
    def _variant_score(
        variant: Variant, metrics: List[MetricDefinition],
        grouped: Dict[Tuple[str, str], List[float]],
    ) -> float:
        """Aggregate score across metrics for a variant."""
        total = 0.0
        for m in metrics:
            vals = grouped.get((variant.id, m.id), [])
            if vals:
                mean = sum(vals) / (len(vals) or 1)
                total += mean if m.higher_is_better else -mean
        return total

    def _find_existing_assignment(self, experiment_id: str, subject_id: str) -> Optional[Assignment]:
        """Return prior Assignment for a subject, if one exists."""
        vid = self._subject_map.get(experiment_id, {}).get(subject_id)
        if vid is None:
            return None
        return Assignment(experiment_id=experiment_id, variant_id=vid, subject_id=subject_id)

    def _evict_oldest_archived(self) -> None:
        """Remove the oldest archived experiment to free space."""
        oldest_id, oldest_ts = None, None
        for eid, exp in self._experiments.items():
            if exp.status == ExperimentStatus.archived:
                if oldest_ts is None or exp.created_at < oldest_ts:
                    oldest_ts, oldest_id = exp.created_at, eid
        if oldest_id:
            del self._experiments[oldest_id]

# ── Wingman pair validation ───────────────────────────────────────────────

def validate_wingman_pair(experiment: Experiment) -> Tuple[bool, str]:
    """Validate that an experiment has a proper wingman pair.

    Checks: ≥2 variants, at least one control, at least one treatment,
    weights sum to ~1.0, and at least one metric defined.
    """
    if len(experiment.variants) < 2:
        return False, "Experiment must have at least 2 variants"
    has_control = any(v.type == VariantType.control for v in experiment.variants)
    has_treatment = any(v.type == VariantType.treatment for v in experiment.variants)
    if not has_control:
        return False, "Experiment must have at least one control variant"
    if not has_treatment:
        return False, "Experiment must have at least one treatment variant"
    weight_sum = sum(v.weight for v in experiment.variants)
    if abs(weight_sum - 1.0) > 0.05:
        return False, f"Variant weights must sum to ~1.0 (got {weight_sum:.3f})"
    if not experiment.metrics:
        return False, "Experiment must have at least one metric defined"
    return True, "Valid wingman pair"

# ── Causality Sandbox gate ────────────────────────────────────────────────

def gate_experiment_in_sandbox(experiment: Experiment) -> Tuple[bool, str]:
    """Gate an experiment for the Causality Sandbox.

    Approved if experiment has a description, an owner, at most 10 variants,
    and traffic_percentage ≤ 1.0.
    """
    if not experiment.description:
        return False, "Experiment must have a description"
    if not experiment.owner:
        return False, "Experiment must have an owner"
    if len(experiment.variants) > 10:
        return False, "Experiment must have at most 10 variants"
    if experiment.traffic_percentage > 1.0:
        return False, "Traffic percentage must be ≤ 1.0"
    return True, "Approved for sandbox"

# ── Flask Blueprint factory ───────────────────────────────────────────────

def _api_body() -> Dict[str, Any]:
    """Extract JSON body from the current request."""
    return request.get_json(silent=True) or {}

def _api_need(body: Dict[str, Any], *keys: str) -> Optional[Any]:
    """Return an error tuple if any *keys* are missing from *body*."""
    for k in keys:
        if not body.get(k):
            return jsonify({"error": f"{k} required", "code": "ABT_MISSING"}), 400
    return None

def _api_404(msg: str = "Not found") -> Any:
    """Standard 404 response."""
    return jsonify({"error": msg, "code": "ABT_404"}), 404

def _parse_variants(raw: List[Dict[str, Any]]) -> List[Variant]:
    """Parse variant dicts from JSON body."""
    return [Variant(
        name=v.get("name", ""), type=VariantType(v.get("type", "control")),
        weight=float(v.get("weight", 0.5)), config=v.get("config", {}),
        description=v.get("description", ""),
    ) for v in raw]

def _parse_metrics(raw: List[Dict[str, Any]]) -> List[MetricDefinition]:
    """Parse metric definition dicts from JSON body."""
    return [MetricDefinition(
        name=m.get("name", ""), type=MetricType(m.get("type", "conversion")),
        higher_is_better=m.get("higher_is_better", True),
        minimum_sample_size=int(m.get("minimum_sample_size", 100)),
    ) for m in raw]

def _register_crud_routes(bp: Any, engine: ABTestingEngine) -> None:
    """Attach experiment CRUD routes to *bp*."""
    @bp.route("/experiments", methods=["POST"])
    def create_experiment() -> Any:
        """Create a new experiment."""
        b = _api_body()
        err = _api_need(b, "name")
        if err:
            return err
        exp = engine.create_experiment(
            name=b["name"], description=b.get("description", ""),
            variants=_parse_variants(b.get("variants", [])),
            metrics=_parse_metrics(b.get("metrics", [])),
            owner=b.get("owner", ""), tags=b.get("tags", []),
            auto_promote=b.get("auto_promote", False),
        )
        return jsonify(exp.to_dict()), 201

    @bp.route("/experiments", methods=["GET"])
    def list_experiments() -> Any:
        """List experiments with optional status filter."""
        status_val = request.args.get("status")
        status = ExperimentStatus(status_val) if status_val else None
        return jsonify([e.to_dict() for e in engine.list_experiments(status)])

    @bp.route("/experiments/<experiment_id>", methods=["GET"])
    def get_experiment(experiment_id: str) -> Any:
        """Get a single experiment."""
        exp = engine.get_experiment(experiment_id)
        return jsonify(exp.to_dict()) if exp else _api_404()

    @bp.route("/experiments/<experiment_id>", methods=["DELETE"])
    def delete_experiment(experiment_id: str) -> Any:
        """Delete an experiment."""
        return jsonify({"deleted": True}) if engine.delete_experiment(experiment_id) else _api_404()

def _register_action_routes(bp: Any, engine: ABTestingEngine) -> None:
    """Attach experiment action routes to *bp*."""
    @bp.route("/experiments/<experiment_id>/start", methods=["POST"])
    def start_experiment(experiment_id: str) -> Any:
        """Start an experiment."""
        if engine.start_experiment(experiment_id):
            return jsonify({"started": True})
        return jsonify({"error": "Cannot start", "code": "ABT_STATE"}), 409

    @bp.route("/experiments/<experiment_id>/pause", methods=["POST"])
    def pause_experiment(experiment_id: str) -> Any:
        """Pause an experiment."""
        if engine.pause_experiment(experiment_id):
            return jsonify({"paused": True})
        return jsonify({"error": "Cannot pause", "code": "ABT_STATE"}), 409

    @bp.route("/experiments/<experiment_id>/complete", methods=["POST"])
    def complete_experiment(experiment_id: str) -> Any:
        """Complete an experiment."""
        if engine.complete_experiment(experiment_id):
            return jsonify({"completed": True})
        return jsonify({"error": "Cannot complete", "code": "ABT_STATE"}), 409

    @bp.route("/experiments/<experiment_id>/assign", methods=["POST"])
    def assign_variant(experiment_id: str) -> Any:
        """Assign a subject to a variant."""
        b = _api_body()
        err = _api_need(b, "subject_id")
        if err:
            return err
        a = engine.assign_variant(experiment_id, b["subject_id"], b.get("context"))
        return jsonify(a.to_dict()) if a else _api_404("Experiment not running")

    @bp.route("/experiments/<experiment_id>/metrics", methods=["POST"])
    def record_metric(experiment_id: str) -> Any:
        """Record a metric event."""
        b = _api_body()
        err = _api_need(b, "variant_id", "subject_id", "metric_id", "value")
        if err:
            return err
        ok = engine.record_metric(
            experiment_id, b["variant_id"], b["subject_id"],
            b["metric_id"], float(b["value"]),
        )
        if ok:
            return jsonify({"recorded": True})
        return jsonify({"error": "Cannot record", "code": "ABT_STATE"}), 409

def _register_results_routes(bp: Any, engine: ABTestingEngine) -> None:
    """Attach results & significance routes to *bp*."""
    @bp.route("/experiments/<experiment_id>/results", methods=["GET"])
    def get_results(experiment_id: str) -> Any:
        """Get experiment results."""
        results = engine.get_results(experiment_id)
        if not results and not engine.get_experiment(experiment_id):
            return _api_404()
        return jsonify({k: [r.to_dict() for r in v] for k, v in results.items()})

    @bp.route("/experiments/<experiment_id>/significance", methods=["GET"])
    def check_significance(experiment_id: str) -> Any:
        """Check statistical significance."""
        if not engine.get_experiment(experiment_id):
            return _api_404()
        return jsonify(engine.check_significance(experiment_id))

    @bp.route("/experiments/<experiment_id>/auto-promote", methods=["POST"])
    def auto_promote(experiment_id: str) -> Any:
        """Auto-promote the winning variant."""
        if not engine.get_experiment(experiment_id):
            return _api_404()
        winner = engine.auto_promote_winner(experiment_id)
        if winner:
            return jsonify({"winner_variant_id": winner})
        return jsonify({"error": "No significant winner", "code": "ABT_NOSIG"}), 200

def create_ab_testing_api(engine: ABTestingEngine) -> Any:
    """Create a Flask Blueprint exposing A/B testing endpoints."""
    if not _HAS_FLASK:
        return Blueprint("ab_testing", __name__)
    bp = Blueprint("ab_testing", __name__, url_prefix="/api/ab-testing")
    _register_crud_routes(bp, engine)
    _register_action_routes(bp, engine)
    _register_results_routes(bp, engine)
    require_blueprint_auth(bp)
    return bp
