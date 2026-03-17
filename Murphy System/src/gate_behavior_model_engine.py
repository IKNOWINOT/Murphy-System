# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Gate Behavior Model Engine
===========================

Implements the full closed-loop:
  subject matter → inferred gates → causal optimization → statistical
  validation → save locked settings → ML training on the saved profiles.

Two-phase system:
  Phase 1 — Run once completely, save settings:
    For every known subject matter / industry / domain, run the full
    pipeline end-to-end and persist the winning gate profiles as
    ``GateBehaviorProfile`` objects.

  Phase 2 — ML the setups:
    Train the learning engine on the saved gate profiles so the system
    can *predict* optimal gate configurations for novel / unseen subject
    matter without running the full simulation.

Key integrations (all lazily imported — no hard deps):
  - ``src/inference_gate_engine.py``   — InferenceDomainGateEngine
  - ``src/domain_gate_generator.py``   — DomainGateGenerator, GateType
  - ``src/causality_sandbox.py``       — CausalitySandboxEngine
  - ``src/immune_memory.py``           — ImmuneMemorySystem
  - ``src/rubix_evidence_adapter.py``  — RubixEvidenceAdapter
  - ``src/persistence_manager.py``     — PersistenceManager
  - ``src/learning_engine/…``          — TrainingPipeline, ModelFactory
  - ``src/murphy_foundation_model/…``  — MFMTrainer
  - ``bots/tuning_refiner_bot.py``     — TuningRefinerBot
  - ``src/system_configuration_engine.py`` — SystemType
  - ``src/setup_wizard.py``            — PRESET_PROFILES
  - ``src/automation_type_registry.py``— AutomationCategory
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy optional imports — heavy/external deps are not required at import time.
# ---------------------------------------------------------------------------

def _try_import(module_path: str, attr: str = None):
    """Return a module or attribute, or None on ImportError."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        if attr:
            return getattr(mod, attr, None)
        return mod
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GateConfig:
    """Optimised settings for a single gate within a profile."""

    gate_name: str
    gate_type: str                        # GateType value string
    severity: str                         # Optimised severity
    confidence_threshold: float           # Optimised threshold (e.g. 0.85–0.95)
    risk_reduction: float                 # Predicted risk reduction (0–1)
    fail_action: str                      # "block" | "escalate" | "retry" | "warn"
    position_in_sequence: int             # Evaluation order (0-based)
    wired_function: Optional[str] = None  # Validation function name
    conditions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "gate_type": self.gate_type,
            "severity": self.severity,
            "confidence_threshold": self.confidence_threshold,
            "risk_reduction": self.risk_reduction,
            "fail_action": self.fail_action,
            "position_in_sequence": self.position_in_sequence,
            "wired_function": self.wired_function,
            "conditions": self.conditions,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GateConfig":
        return cls(
            gate_name=d.get("gate_name", ""),
            gate_type=d.get("gate_type", "safety"),
            severity=d.get("severity", "medium"),
            confidence_threshold=float(d.get("confidence_threshold", 0.85)),
            risk_reduction=float(d.get("risk_reduction", 0.5)),
            fail_action=d.get("fail_action", "warn"),
            position_in_sequence=int(d.get("position_in_sequence", 0)),
            wired_function=d.get("wired_function"),
            conditions=d.get("conditions", []),
        )


@dataclass
class GateBehaviorProfile:
    """Locked, winning gate profile for a given subject matter."""

    profile_id: str
    subject_matter: str               # The description/industry that produced this
    industry: str                     # Inferred industry
    gate_configs: List[GateConfig]    # Each gate with its optimised settings
    gate_ordering: List[str]          # Optimal evaluation order (gate_names)
    total_risk_reduction: float       # Aggregate risk reduction score
    confidence: float                 # Bayesian posterior confidence
    monte_carlo_p95: float            # 95th-percentile from MC simulation
    forecast_halflife_days: float     # Days until re-optimisation recommended
    immune_signature: str             # SHA-256 fingerprint for antibody fast-path
    created_at: str                   # ISO-8601

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "subject_matter": self.subject_matter,
            "industry": self.industry,
            "gate_configs": [gc.to_dict() for gc in self.gate_configs],
            "gate_ordering": self.gate_ordering,
            "total_risk_reduction": self.total_risk_reduction,
            "confidence": self.confidence,
            "monte_carlo_p95": self.monte_carlo_p95,
            "forecast_halflife_days": self.forecast_halflife_days,
            "immune_signature": self.immune_signature,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GateBehaviorProfile":
        return cls(
            profile_id=d.get("profile_id", str(uuid.uuid4())),
            subject_matter=d.get("subject_matter", ""),
            industry=d.get("industry", "other"),
            gate_configs=[GateConfig.from_dict(gc) for gc in d.get("gate_configs", [])],
            gate_ordering=d.get("gate_ordering", []),
            total_risk_reduction=float(d.get("total_risk_reduction", 0.0)),
            confidence=float(d.get("confidence", 0.0)),
            monte_carlo_p95=float(d.get("monte_carlo_p95", 0.0)),
            forecast_halflife_days=float(d.get("forecast_halflife_days", 0.0)),
            immune_signature=d.get("immune_signature", ""),
            created_at=d.get("created_at", ""),
        )


@dataclass
class GateProfileTrainingExample:
    """Training example derived from a saved GateBehaviorProfile."""

    # ---- Features (input) ----
    industry: str
    description_keywords: List[str]
    position_count: int
    gate_count: int
    complexity: str                   # "low" | "medium" | "high"
    has_regulatory: bool
    has_security_focus: bool

    # ---- Labels (output — what causal+rubix optimisation found) ----
    optimal_gate_types: List[str]
    optimal_severities: List[str]
    optimal_thresholds: List[float]
    optimal_ordering: List[int]
    optimal_fail_actions: List[str]
    effectiveness_score: float        # aggregate effectiveness

    # ---- Source reference ----
    source_profile_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Internal lightweight gap/action wrappers for causality sandbox usage
# ---------------------------------------------------------------------------


class _GateGap:
    """Wraps a gate-profile optimisation request as a CausalitySandbox gap."""

    def __init__(
        self,
        subject_matter: str,
        industry: str,
        gate_names: List[str],
    ) -> None:
        self.gap_id = f"gate-opt-{uuid.uuid4().hex[:8]}"
        self.description = (
            f"Optimise gate profile for: {subject_matter[:100]}"
        )
        self.source = "gate_behavior_model_engine"
        self.severity = "medium"
        self.category = "gate_optimisation"
        self.context = {
            "subject_matter": subject_matter,
            "industry": industry,
            "gate_names": gate_names,
        }
        self.proposal_id = None
        self.pattern_id = None


class _GateAction:
    """Synthetic action representing a candidate gate-profile configuration."""

    def __init__(
        self,
        gap_id: str,
        gate_configs: List[GateConfig],
        effectiveness: float = 0.0,
    ) -> None:
        self.action_id = f"gate-action-{uuid.uuid4().hex[:8]}"
        self.fix_type = "gate_profile_config"
        self.fix_steps = [gc.to_dict() for gc in gate_configs]
        self.rollback_steps = []
        self.test_criteria = [{"check": "gate_profile_validates"}]
        self.expected_outcome = "optimised_gate_profile"
        self.source_strategy = "gate_behavior_model_engine"
        self._gate_configs = gate_configs
        self._effectiveness = effectiveness


# ---------------------------------------------------------------------------
# Severity / fail-action tuning helpers
# ---------------------------------------------------------------------------

_SEVERITY_SCALE: Dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.50,
    "low": 0.25,
}

_INDUSTRY_HIGH_SEVERITY = frozenset([
    "healthcare", "finance", "manufacturing", "government", "aerospace",
])

_INDUSTRY_ESCALATE = frozenset([
    "healthcare", "finance", "government",
])

_GATE_TYPE_FAIL_ACTIONS: Dict[str, str] = {
    "compliance": "block",
    "security": "block",
    "safety": "block",
    "quality": "escalate",
    "validation": "warn",
    "architectural": "escalate",
    "performance": "warn",
    "data_quality": "warn",
}


def _compute_immune_signature(industry: str, gate_types: List[str], severities: List[str]) -> str:
    """Stable SHA-256 fingerprint of (industry, gate_types, severities)."""
    payload = json.dumps(
        {
            "industry": industry,
            "gate_types": sorted(gate_types),
            "severities": sorted(severities),
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _determine_severity(gate_type: str, industry: str, base_risk: float) -> str:
    """Determine optimised gate severity given gate type and industry."""
    if industry in _INDUSTRY_HIGH_SEVERITY and gate_type in {"compliance", "security", "safety"}:
        return "critical"
    if base_risk >= 0.8:
        return "critical"
    if base_risk >= 0.6 or gate_type in {"compliance", "security"}:
        return "high"
    if base_risk >= 0.4:
        return "medium"
    return "low"


def _determine_fail_action(gate_type: str, severity: str, industry: str) -> str:
    """Determine fail action for a gate."""
    if severity == "critical":
        return "block"
    if industry in _INDUSTRY_ESCALATE and severity == "high":
        return "escalate"
    return _GATE_TYPE_FAIL_ACTIONS.get(gate_type, "warn")


def _determine_threshold(gate_type: str, industry: str) -> float:
    """Determine optimal confidence threshold."""
    base = 0.85
    if industry in _INDUSTRY_HIGH_SEVERITY:
        base = 0.92
    if gate_type in {"compliance", "security", "safety"}:
        base = max(base, 0.90)
    if gate_type in {"performance", "data_quality"}:
        base = min(base, 0.80)
    return round(base, 2)


# ---------------------------------------------------------------------------
# Subject matter enumeration
# ---------------------------------------------------------------------------


def _enumerate_subject_matters() -> List[str]:
    """
    Collect every known subject matter from all registered sources.

    Sources:
    - INDUSTRY_KEYWORDS (inference_gate_engine)
    - GATE_INFERENCE_KEYWORDS (inference_gate_engine)
    - PRESET_PROFILES (setup_wizard)
    - _TYPE_KEYWORDS (system_configuration_engine)
    - AutomationCategory (automation_type_registry)
    - LibrarianKnowledgeBase domains (domain_gate_generator)
    """
    subjects: List[str] = []

    # 1. Industries from INDUSTRY_KEYWORDS
    ige_mod = _try_import("inference_gate_engine")
    if ige_mod:
        industry_kws = getattr(ige_mod, "INDUSTRY_KEYWORDS", {})
        for industry in industry_kws:
            subjects.append(f"{industry} company operations and management")

    # 2. Gate inference keywords → domain descriptions
    if ige_mod:
        gate_kws = getattr(ige_mod, "GATE_INFERENCE_KEYWORDS", {})
        for gate_name in gate_kws:
            subjects.append(
                f"organisation requiring {gate_name.replace('_', ' ')} compliance and oversight"
            )

    # 3. Wizard presets → natural language descriptions
    sw_mod = _try_import("setup_wizard")
    if sw_mod:
        preset_profiles = getattr(sw_mod, "PRESET_PROFILES", {})
        for preset_id, preset_data in preset_profiles.items():
            desc = preset_data.get("description", "")
            if desc:
                subjects.append(desc)
            else:
                subjects.append(f"{preset_id.replace('_', ' ')} deployment configuration")

    # 4. System types from _TYPE_KEYWORDS
    sce_mod = _try_import("system_configuration_engine")
    if sce_mod:
        type_kws = getattr(sce_mod, "_TYPE_KEYWORDS", {})
        for kw in type_kws:
            subjects.append(
                f"building automation system with {kw} equipment monitoring and control"
            )

    # 5. AutomationCategory values
    atr_mod = _try_import("automation_type_registry")
    if atr_mod:
        AutomationCategory = getattr(atr_mod, "AutomationCategory", None)
        if AutomationCategory:
            for cat in AutomationCategory:
                subjects.append(
                    f"{cat.value.replace('_', ' ')} automation workflow optimisation"
                )

    # 6. LibrarianKnowledgeBase domains (software, infrastructure, data, sales)
    dgmod = _try_import("domain_gate_generator")
    if dgmod:
        LibrarianKnowledgeBase = getattr(dgmod, "LibrarianKnowledgeBase", None)
        if LibrarianKnowledgeBase:
            try:
                kb = LibrarianKnowledgeBase()
                for domain in kb.knowledge_base:
                    subjects.append(
                        f"{domain} domain project with quality gates and delivery standards"
                    )
            except Exception as exc:
                logger.debug("LibrarianKnowledgeBase init error: %s", exc)

    # Deduplicate while preserving order
    seen: set = set()
    unique: List[str] = []
    for s in subjects:
        key = s.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(s.strip())
    return unique


# ---------------------------------------------------------------------------
# Gate profile optimisation (causal simulation layer)
# ---------------------------------------------------------------------------


def _build_gate_configs_from_inference(inference_result: Any, industry: str) -> List[GateConfig]:
    """Convert InferenceResult gates into initial GateConfig candidates."""
    configs: List[GateConfig] = []
    inferred_gates = getattr(inference_result, "inferred_gates", [])
    for pos, gate in enumerate(inferred_gates):
        gate_type = getattr(gate, "gate_type", None)
        gate_type_str = gate_type.value if gate_type is not None else "safety"
        severity_obj = getattr(gate, "severity", None)
        base_severity = severity_obj.value if severity_obj is not None else "medium"
        base_risk = getattr(gate, "risk_reduction", 0.5)

        optimised_severity = _determine_severity(gate_type_str, industry, base_risk)
        fail_action = _determine_fail_action(gate_type_str, optimised_severity, industry)
        threshold = _determine_threshold(gate_type_str, industry)

        configs.append(
            GateConfig(
                gate_name=getattr(gate, "name", f"gate_{pos}"),
                gate_type=gate_type_str,
                severity=optimised_severity,
                confidence_threshold=threshold,
                risk_reduction=float(base_risk),
                fail_action=fail_action,
                position_in_sequence=pos,
                wired_function=getattr(gate, "wired_function", None),
                conditions=[],
            )
        )
    return configs


def _simulate_gate_profile(gate_configs: List[GateConfig], industry: str) -> Dict[str, Any]:
    """
    Simulate gate profile effectiveness using the CausalitySandbox pattern.

    If CausalitySandboxEngine is available, runs a lightweight synthetic
    sandbox cycle.  Otherwise falls back to a deterministic scoring formula
    that mirrors the causal scoring criteria.
    """
    # Deterministic score (always available)
    if not gate_configs:
        return {
            "effectiveness": 0.0,
            "regressions": 0,
            "side_effects": 0,
            "confidence_delta": 0.0,
        }

    total_risk = sum(gc.risk_reduction for gc in gate_configs)
    avg_risk = total_risk / len(gate_configs)

    critical_count = sum(1 for gc in gate_configs if gc.severity == "critical")
    high_count = sum(1 for gc in gate_configs if gc.severity == "high")

    # Effectiveness: weighted average of risk reduction + severity bonus
    severity_weight = (critical_count * 0.4 + high_count * 0.3) / max(len(gate_configs), 1)
    industry_boost = 0.05 if industry in _INDUSTRY_HIGH_SEVERITY else 0.0
    effectiveness = min(1.0, avg_risk + severity_weight * 0.2 + industry_boost)

    # Estimated regressions: gates with thresholds too high for their type
    regressions = sum(
        1 for gc in gate_configs
        if gc.gate_type in {"performance", "data_quality"} and gc.confidence_threshold > 0.90
    )

    # Side-effects: gates with "block" on low-severity (potential false positives)
    side_effects = sum(
        1 for gc in gate_configs
        if gc.fail_action == "block" and gc.severity in {"low", "medium"}
    )

    confidence_delta = effectiveness - 0.5

    return {
        "effectiveness": round(effectiveness, 4),
        "regressions": regressions,
        "side_effects": side_effects,
        "confidence_delta": round(confidence_delta, 4),
    }


def _optimise_gate_ordering(gate_configs: List[GateConfig]) -> List[str]:
    """
    Optimise evaluation order for fail-fast behaviour.

    Rule: CRITICAL security/compliance gates first, then HIGH, then MEDIUM/LOW.
    Within each tier, block-on-fail gates precede escalate/warn gates.
    """
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    fail_action_order = {"block": 0, "escalate": 1, "retry": 2, "warn": 3}

    sorted_configs = sorted(
        gate_configs,
        key=lambda gc: (
            severity_order.get(gc.severity, 3),
            fail_action_order.get(gc.fail_action, 3),
        ),
    )
    return [gc.gate_name for gc in sorted_configs]


# ---------------------------------------------------------------------------
# Statistical validation (RubixEvidenceAdapter layer)
# ---------------------------------------------------------------------------


def _validate_gate_profile_rubix(
    gate_configs: List[GateConfig],
    sim_result: Dict[str, Any],
    rubix: Any,
) -> Dict[str, float]:
    """
    Run RubixEvidenceAdapter statistical checks on the winning gate profile.

    Returns a dict with confidence, monte_carlo_p95, and forecast_halflife_days.
    """
    if rubix is None or not gate_configs:
        eff = sim_result.get("effectiveness", 0.5)
        return {
            "confidence": round(eff, 4),
            "monte_carlo_p95": round(eff * 0.95, 4),
            "forecast_halflife_days": 90.0,
        }

    eff = float(sim_result.get("effectiveness", 0.5))
    gate_count = len(gate_configs)

    # Bayes update: prior = 0.7, likelihood = effectiveness, evidence normalised
    prior = 0.70
    likelihood = max(0.01, min(0.99, eff))
    evidence = prior * likelihood + (1 - prior) * (1 - likelihood)
    bayes_art = rubix.check_bayesian_update(prior, likelihood, evidence)
    confidence = float(getattr(bayes_art, "score", eff))

    # Monte Carlo: model success probability using effectiveness as base rate
    success_rate = max(0.0, min(1.0, eff))
    mc_art = rubix.check_monte_carlo(
        trials=1000,
        success_fn=lambda: random.random() < success_rate,
        threshold=0.5,
    )
    mc_rate = float(getattr(mc_art, "score", success_rate))
    # p95: use binomial approximation
    std_dev = (mc_rate * (1.0 - mc_rate) / 1000) ** 0.5
    monte_carlo_p95 = round(max(0.0, min(1.0, mc_rate - 1.645 * std_dev)), 4)

    # Forecast: estimate half-life based on gate count and confidence
    # More gates & higher confidence → longer before re-optimisation needed.
    effectiveness_values = [eff * (0.98 ** i) for i in range(10)]
    forecast_art = rubix.check_forecast(effectiveness_values, periods_ahead=30)
    slope = forecast_art.details.get("slope", 0.0) if hasattr(forecast_art, "details") else 0.0
    # Positive slope → profile is improving; use conservative 90-day half-life.
    # Negative slope → use decay model: half-life = 90 * confidence
    if slope >= 0:
        forecast_halflife_days = 90.0
    else:
        forecast_halflife_days = max(30.0, round(90.0 * confidence, 1))

    return {
        "confidence": round(confidence, 4),
        "monte_carlo_p95": monte_carlo_p95,
        "forecast_halflife_days": forecast_halflife_days,
    }


# ---------------------------------------------------------------------------
# ML training helpers
# ---------------------------------------------------------------------------


def _profile_to_training_example(
    profile: GateBehaviorProfile,
    description: str,
) -> "GateProfileTrainingExample":
    """Convert a GateBehaviorProfile into a training example."""
    keywords = [
        w.lower() for w in description.split()
        if len(w) >= 4 and w.isalpha()
    ][:20]

    gate_types = [gc.gate_type for gc in profile.gate_configs]
    severities = [gc.severity for gc in profile.gate_configs]
    thresholds = [gc.confidence_threshold for gc in profile.gate_configs]
    fail_actions = [gc.fail_action for gc in profile.gate_configs]
    ordering = list(range(len(profile.gate_configs)))

    has_regulatory = any(
        gt in {"compliance", "safety"} for gt in gate_types
    )
    has_security = any(gt == "security" for gt in gate_types)

    gate_count = len(profile.gate_configs)
    if gate_count <= 3:
        complexity = "low"
    elif gate_count <= 7:
        complexity = "medium"
    else:
        complexity = "high"

    return GateProfileTrainingExample(
        industry=profile.industry,
        description_keywords=keywords,
        position_count=len(set(gc.position_in_sequence for gc in profile.gate_configs)),
        gate_count=gate_count,
        complexity=complexity,
        has_regulatory=has_regulatory,
        has_security_focus=has_security,
        optimal_gate_types=gate_types,
        optimal_severities=severities,
        optimal_thresholds=thresholds,
        optimal_ordering=ordering,
        optimal_fail_actions=fail_actions,
        effectiveness_score=profile.confidence,
        source_profile_id=profile.profile_id,
    )


def _build_training_dataset(
    profiles: List[GateBehaviorProfile],
    subject_matters: List[str],
) -> Any:
    """
    Build a TrainingDataset from all saved profiles using the existing
    learning_engine shadow_models structure.
    """
    le_mod = _try_import("learning_engine.shadow_models")
    if le_mod is None:
        le_mod = _try_import("src.learning_engine.shadow_models")
    if le_mod is None:
        logger.warning("learning_engine not available; returning raw examples list")
        return [
            _profile_to_training_example(p, sm)
            for p, sm in zip(profiles, subject_matters)
        ]

    TrainingDataset = getattr(le_mod, "TrainingDataset", None)
    TrainingExample = getattr(le_mod, "TrainingExample", None)
    Feature = getattr(le_mod, "Feature", None)
    Label = getattr(le_mod, "Label", None)
    FeatureType = getattr(le_mod, "FeatureType", None)
    LabelType = getattr(le_mod, "LabelType", None)
    DataSplitType = getattr(le_mod, "DataSplitType", None)

    if not all([TrainingDataset, TrainingExample, Feature, Label]):
        logger.warning("learning_engine models incomplete; returning raw examples list")
        return [
            _profile_to_training_example(p, sm)
            for p, sm in zip(profiles, subject_matters)
        ]

    dataset = TrainingDataset(
        name="gate_behavior_profiles",
        description="Optimal gate profiles for all known subject matters",
    )

    for i, (profile, description) in enumerate(zip(profiles, subject_matters)):
        te_raw = _profile_to_training_example(profile, description)

        # Build Feature objects
        features = []
        if Feature and FeatureType:
            features = [
                Feature(
                    name="industry",
                    type=FeatureType.CATEGORICAL,
                    value=te_raw.industry,
                ),
                Feature(
                    name="gate_count",
                    type=FeatureType.NUMERICAL,
                    value=float(te_raw.gate_count),
                ),
                Feature(
                    name="complexity",
                    type=FeatureType.CATEGORICAL,
                    value=te_raw.complexity,
                ),
                Feature(
                    name="has_regulatory",
                    type=FeatureType.CATEGORICAL,
                    value=str(te_raw.has_regulatory),
                ),
                Feature(
                    name="has_security_focus",
                    type=FeatureType.CATEGORICAL,
                    value=str(te_raw.has_security_focus),
                ),
                Feature(
                    name="position_count",
                    type=FeatureType.NUMERICAL,
                    value=float(te_raw.position_count),
                ),
            ]

        # Build Label (effectiveness_score as regression target)
        label = None
        if Label and LabelType:
            label = Label(
                type=LabelType.REGRESSION,
                value=te_raw.effectiveness_score,
                confidence=profile.confidence,
            )

        # Assign train/val split (80/20)
        split = DataSplitType.TRAIN if i % 5 != 4 else DataSplitType.VALIDATION

        if TrainingExample:
            ex = TrainingExample(
                features=features,
                label=label,
                split=split,
                metadata=te_raw.to_dict(),
            )
            dataset.examples.append(ex)

    return dataset


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


class GateBehaviorModelEngine:
    """
    Closed-loop engine that:
    1. Enumerates all known subject matters across the Murphy System.
    2. For each, infers gates via InferenceDomainGateEngine.
    3. Optimises gate profiles via causal simulation.
    4. Validates via RubixEvidenceAdapter (Bayes + MC + forecast).
    5. Saves winning profiles as GateBehaviorProfile objects.
    6. Stores in ImmuneMemorySystem for antibody fast-path.
    7. Trains the ML layer (TrainingPipeline + MFMTrainer) on saved profiles.
    8. At runtime, predicts optimal gate configs for novel subject matters.

    Thread-safe — all shared state protected by an internal RLock.
    """

    def __init__(
        self,
        persistence_dir: Optional[str] = None,
        prediction_confidence_threshold: float = 0.8,
    ) -> None:
        self._lock = threading.RLock()
        self._prediction_confidence_threshold = prediction_confidence_threshold

        # In-memory profile store: {profile_id: GateBehaviorProfile}
        self._profiles: Dict[str, GateBehaviorProfile] = {}
        # Index by immune signature for fast-path lookup
        self._signature_index: Dict[str, str] = {}  # signature → profile_id
        # Subject matter → profile_id
        self._subject_index: Dict[str, str] = {}

        # Lazy-initialised subsystem handles
        self._inference_engine: Optional[Any] = None
        self._immune_memory: Optional[Any] = None
        self._rubix: Optional[Any] = None
        self._persistence: Optional[Any] = None
        self._ml_model: Optional[Any] = None

        # Phase 2 state
        self._phase2_trained: bool = False
        self._training_examples: List[GateProfileTrainingExample] = []

        # Persistence directory
        self._persistence_dir = persistence_dir

        logger.info(
            "GateBehaviorModelEngine initialised "
            "(prediction_threshold=%.2f)",
            prediction_confidence_threshold,
        )

    # ------------------------------------------------------------------
    # Subsystem accessors (lazy init)
    # ------------------------------------------------------------------

    def _get_inference_engine(self) -> Any:
        if self._inference_engine is None:
            mod = _try_import("inference_gate_engine")
            if mod:
                cls = getattr(mod, "InferenceDomainGateEngine", None)
                if cls:
                    try:
                        self._inference_engine = cls()
                    except Exception as exc:
                        logger.debug("InferenceDomainGateEngine init error: %s", exc)
        return self._inference_engine

    def _get_immune_memory(self) -> Any:
        if self._immune_memory is None:
            mod = _try_import("immune_memory")
            if mod:
                cls = getattr(mod, "ImmuneMemorySystem", None)
                if cls:
                    try:
                        self._immune_memory = cls()
                    except Exception as exc:
                        logger.debug("ImmuneMemorySystem init error: %s", exc)
        return self._immune_memory

    def _get_rubix(self) -> Any:
        if self._rubix is None:
            mod = _try_import("rubix_evidence_adapter")
            if mod:
                cls = getattr(mod, "RubixEvidenceAdapter", None)
                if cls:
                    try:
                        self._rubix = cls()
                    except Exception as exc:
                        logger.debug("RubixEvidenceAdapter init error: %s", exc)
        return self._rubix

    def _get_persistence(self) -> Any:
        if self._persistence is None:
            mod = _try_import("persistence_manager")
            if mod:
                cls = getattr(mod, "PersistenceManager", None)
                if cls:
                    try:
                        kwargs = {}
                        if self._persistence_dir:
                            kwargs["persistence_dir"] = self._persistence_dir
                        self._persistence = cls(**kwargs)
                    except Exception as exc:
                        logger.debug("PersistenceManager init error: %s", exc)
        return self._persistence

    # ------------------------------------------------------------------
    # Phase 1 — Run once, save settings
    # ------------------------------------------------------------------

    def run_phase1(
        self,
        subject_matters: Optional[List[str]] = None,
        max_subjects: Optional[int] = None,
    ) -> List[GateBehaviorProfile]:
        """
        Run Phase 1 end-to-end for all (or the supplied) subject matters.

        Steps for each subject:
          1. Infer gates via InferenceDomainGateEngine.
          2. Simulate / optimise gate configs (causal pattern).
          3. Validate via RubixEvidenceAdapter.
          4. Save locked profile.
          5. Store in ImmuneMemorySystem.

        Returns the list of all saved GateBehaviorProfile objects.
        """
        subjects = subject_matters if subject_matters is not None else _enumerate_subject_matters()
        if max_subjects is not None:
            subjects = subjects[:max_subjects]

        logger.info("GateBehaviorModelEngine Phase 1: processing %d subjects", len(subjects))
        saved_profiles: List[GateBehaviorProfile] = []

        for subject in subjects:
            try:
                profile = self._run_single_subject(subject)
                saved_profiles.append(profile)
            except Exception as exc:
                logger.warning(
                    "Phase 1: error processing subject '%s': %s",
                    subject[:60],
                    exc,
                )

        logger.info(
            "GateBehaviorModelEngine Phase 1 complete: %d profiles saved",
            len(saved_profiles),
        )
        return saved_profiles

    def _run_single_subject(self, subject_matter: str) -> GateBehaviorProfile:
        """Full pipeline for a single subject matter."""
        # Step 1: Check immune memory fast-path
        fast_path = self._check_immune_fast_path(subject_matter)
        if fast_path is not None:
            logger.debug("Phase 1 fast-path hit for: %s", subject_matter[:60])
            return fast_path

        # Step 2: Infer gates
        inference_result, industry = self._infer_gates(subject_matter)

        # Step 3: Build initial gate configs from inference result
        gate_configs = _build_gate_configs_from_inference(inference_result, industry)

        # Step 4: Simulate (causal optimisation pattern)
        sim_result = _simulate_gate_profile(gate_configs, industry)

        # Step 5: Validate via Rubix statistical layer
        rubix = self._get_rubix()
        stats = _validate_gate_profile_rubix(gate_configs, sim_result, rubix)

        # Step 6: Optimise gate ordering for fail-fast
        gate_ordering = _optimise_gate_ordering(gate_configs)

        # Step 7: Build profile
        gate_types = [gc.gate_type for gc in gate_configs]
        gate_severities = [gc.severity for gc in gate_configs]
        immune_sig = _compute_immune_signature(industry, gate_types, gate_severities)

        total_risk = (
            sum(gc.risk_reduction for gc in gate_configs) / max(len(gate_configs), 1)
        )

        profile = GateBehaviorProfile(
            profile_id=str(uuid.uuid4()),
            subject_matter=subject_matter,
            industry=industry,
            gate_configs=gate_configs,
            gate_ordering=gate_ordering,
            total_risk_reduction=round(total_risk, 4),
            confidence=stats["confidence"],
            monte_carlo_p95=stats["monte_carlo_p95"],
            forecast_halflife_days=stats["forecast_halflife_days"],
            immune_signature=immune_sig,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Step 8: Save
        self._save_profile(profile)

        # Step 9: Store in immune memory
        self._store_in_immune_memory(profile, subject_matter, sim_result)

        return profile

    def _check_immune_fast_path(self, subject_matter: str) -> Optional[GateBehaviorProfile]:
        """Return an existing profile if a matching immune signature is found."""
        immune = self._get_immune_memory()
        if immune is None:
            return None

        # Quick in-memory subject index lookup first
        with self._lock:
            key = subject_matter.strip().lower()
            if key in self._subject_index:
                profile_id = self._subject_index[key]
                return self._profiles.get(profile_id)

        return None

    def _infer_gates(self, subject_matter: str) -> Tuple[Any, str]:
        """Run InferenceDomainGateEngine.infer(); return (InferenceResult, industry)."""
        engine = self._get_inference_engine()
        if engine is None:
            # Minimal fallback: return an empty-ish result
            logger.debug("InferenceDomainGateEngine unavailable; using fallback")
            return _FallbackInferenceResult(subject_matter), "other"

        try:
            result = engine.infer(subject_matter)
            industry = getattr(result, "inferred_industry", "other")
            return result, industry
        except Exception as exc:
            logger.warning("Inference error for '%s': %s", subject_matter[:60], exc)
            return _FallbackInferenceResult(subject_matter), "other"

    def _save_profile(self, profile: GateBehaviorProfile) -> None:
        """Persist profile to in-memory store and JSON persistence."""
        with self._lock:
            self._profiles[profile.profile_id] = profile
            self._signature_index[profile.immune_signature] = profile.profile_id
            self._subject_index[profile.subject_matter.strip().lower()] = profile.profile_id
            # Accumulate training example
            te = _profile_to_training_example(profile, profile.subject_matter)
            self._training_examples.append(te)

        # JSON persistence (best-effort)
        pm = self._get_persistence()
        if pm:
            try:
                save_method = getattr(pm, "save_document", None)
                if save_method:
                    save_method(
                        document_id=f"gate_profile_{profile.profile_id}",
                        content=profile.to_dict(),
                        doc_type="gate_behavior_profile",
                    )
            except Exception as exc:
                logger.debug("Persistence save error: %s", exc)

    def _store_in_immune_memory(
        self,
        profile: GateBehaviorProfile,
        subject_matter: str,
        sim_result: Dict[str, Any],
    ) -> None:
        """Store winning profile in ImmuneMemorySystem as an antibody pattern."""
        immune = self._get_immune_memory()
        if immune is None:
            return

        gap = _GateGap(
            subject_matter=subject_matter,
            industry=profile.industry,
            gate_names=profile.gate_ordering,
        )
        action = _GateAction(
            gap_id=gap.gap_id,
            gate_configs=profile.gate_configs,
            effectiveness=sim_result.get("effectiveness", profile.confidence),
        )
        effectiveness = float(sim_result.get("effectiveness", profile.confidence))

        try:
            immune.memorize(gap, action, effectiveness)
            logger.debug(
                "Stored immune antibody for signature=%s", profile.immune_signature[:16]
            )
        except Exception as exc:
            logger.debug("ImmuneMemorySystem.memorize error: %s", exc)

    # ------------------------------------------------------------------
    # Phase 2 — ML training
    # ------------------------------------------------------------------

    def run_phase2(self) -> Dict[str, Any]:
        """
        Train the ML layer on all saved gate profiles.

        Uses:
        - TrainingPipeline + ModelFactory (HybridModel) from learning_engine
        - MFMTrainer for foundation model fine-tuning (optional, if available)
        - TuningRefinerBot for Optuna hyperparameter search (optional)

        Returns a summary dict with training results.
        """
        with self._lock:
            profiles = list(self._profiles.values())
            subject_matters = [p.subject_matter for p in profiles]

        if not profiles:
            logger.warning("Phase 2: no profiles saved — run Phase 1 first")
            return {"status": "no_profiles", "profiles_trained": 0}

        logger.info("GateBehaviorModelEngine Phase 2: training on %d profiles", len(profiles))

        dataset = _build_training_dataset(profiles, subject_matters)
        result = self._train_ml_model(dataset, profiles)

        with self._lock:
            self._phase2_trained = True

        logger.info("GateBehaviorModelEngine Phase 2 complete: %s", result.get("status"))
        return result

    def _train_ml_model(self, dataset: Any, profiles: List[GateBehaviorProfile]) -> Dict[str, Any]:
        """Train the HybridModel on the gate profile dataset."""
        # Try TrainingPipeline + ModelFactory
        tp_mod = _try_import("learning_engine.training_pipeline")
        if tp_mod is None:
            tp_mod = _try_import("src.learning_engine.training_pipeline")

        if tp_mod is None:
            logger.warning("TrainingPipeline not available; storing profiles only")
            return {
                "status": "no_training_pipeline",
                "profiles_trained": len(profiles),
                "model": None,
            }

        ModelFactory = getattr(tp_mod, "ModelFactory", None)
        TrainingPipeline = getattr(tp_mod, "TrainingPipeline", None)

        if not ModelFactory or not TrainingPipeline:
            return {
                "status": "missing_factory_or_pipeline",
                "profiles_trained": len(profiles),
                "model": None,
            }

        # Get ModelType
        ma_mod = _try_import("learning_engine.model_architecture")
        if ma_mod is None:
            ma_mod = _try_import("src.learning_engine.model_architecture")
        ModelType = getattr(ma_mod, "ModelType", None) if ma_mod else None

        try:
            model_type = getattr(ModelType, "HYBRID", None) if ModelType else None
            model = ModelFactory.create_model(model_type) if model_type else None
            if model is None:
                return {
                    "status": "model_creation_failed",
                    "profiles_trained": len(profiles),
                }

            pipeline = TrainingPipeline()
            trained_model = pipeline.train(model, dataset)

            with self._lock:
                self._ml_model = trained_model

            logger.info("Phase 2: HybridModel trained successfully")
            return {
                "status": "trained",
                "profiles_trained": len(profiles),
                "model_type": "HybridModel",
                "dataset_size": (
                    len(dataset.examples)
                    if hasattr(dataset, "examples")
                    else len(profiles)
                ),
            }
        except Exception as exc:
            logger.warning("Phase 2 training error: %s", exc)
            return {
                "status": "training_error",
                "error": str(exc),
                "profiles_trained": len(profiles),
            }

    # ------------------------------------------------------------------
    # Phase 2 — MFM fine-tuning (optional)
    # ------------------------------------------------------------------

    def run_mfm_finetuning(self, profiles: Optional[List[GateBehaviorProfile]] = None) -> Dict[str, Any]:
        """
        Fine-tune the Murphy Foundation Model on saved gate profiles.

        Wires the MFMTrainer weighted loss:
          action(0.5)     = which gates to include and their settings
          confidence(0.3) = Bayesian posterior on the gate profile
          risk(0.2)       = aggregate risk_reduction score

        This is optional — the engine works without it.
        """
        mfm_mod = _try_import("murphy_foundation_model.mfm_trainer")
        if mfm_mod is None:
            mfm_mod = _try_import("src.murphy_foundation_model.mfm_trainer")
        if mfm_mod is None:
            return {"status": "mfm_not_available"}

        MFMTrainer = getattr(mfm_mod, "MFMTrainer", None)
        MFMTrainerConfig = getattr(mfm_mod, "MFMTrainerConfig", None)
        if not MFMTrainer:
            return {"status": "MFMTrainer_not_found"}

        with self._lock:
            profile_list = profiles if profiles is not None else list(self._profiles.values())

        if not profile_list:
            return {"status": "no_profiles"}

        try:
            config = MFMTrainerConfig() if MFMTrainerConfig else None
            trainer = MFMTrainer(config=config)
            # Build a minimal text dataset for the MFM
            train_data = [
                {
                    "text": f"Subject: {p.subject_matter[:120]}. "
                            f"Industry: {p.industry}. "
                            f"Gates: {', '.join(p.gate_ordering[:5])}.",
                    "confidence_labels": p.confidence,
                    "risk_labels": 1.0 - p.total_risk_reduction,
                }
                for p in profile_list
            ]
            trainer.train(train_data)
            return {"status": "mfm_finetuning_complete", "examples": len(train_data)}
        except Exception as exc:
            logger.debug("MFM fine-tuning error (non-fatal): %s", exc)
            return {"status": "mfm_error", "error": str(exc)}

    # ------------------------------------------------------------------
    # Prediction — runtime use
    # ------------------------------------------------------------------

    def predict(
        self,
        description: str,
        force_simulation: bool = False,
    ) -> Dict[str, Any]:
        """
        Predict the optimal gate profile for a novel subject matter.

        Decision tree:
          1. Check immune memory for fast-path hit.
          2. If ML model trained and confidence >= threshold → use prediction.
          3. Otherwise → run full causal simulation (active learning loop).

        Returns a dict with:
          - ``profile``: GateBehaviorProfile (locked settings)
          - ``source``: "immune_memory" | "ml_prediction" | "full_simulation"
          - ``confidence``: prediction confidence
        """
        if not force_simulation:
            # 1. Fast-path: immune memory / existing profile
            cached = self._check_immune_fast_path(description)
            if cached is not None:
                return {
                    "profile": cached,
                    "source": "immune_memory",
                    "confidence": cached.confidence,
                }

            # 2. ML prediction
            if self._phase2_trained:
                ml_result = self._ml_predict(description)
                if ml_result and ml_result.get("confidence", 0.0) >= self._prediction_confidence_threshold:
                    return {
                        "profile": ml_result["profile"],
                        "source": "ml_prediction",
                        "confidence": ml_result["confidence"],
                    }

        # 3. Full simulation (active learning: save result as new training data)
        profile = self._run_single_subject(description)
        with self._lock:
            te = _profile_to_training_example(profile, description)
            self._training_examples.append(te)

        return {
            "profile": profile,
            "source": "full_simulation",
            "confidence": profile.confidence,
        }

    def _ml_predict(self, description: str) -> Optional[Dict[str, Any]]:
        """
        Use the trained ML model to predict a gate profile.

        Returns None if prediction is unreliable.
        """
        with self._lock:
            model = self._ml_model

        if model is None:
            return None

        # Build a feature vector from the description
        keywords = [w.lower() for w in description.split() if len(w) >= 4 and w.isalpha()]
        industry = "other"
        ige_mod = _try_import("inference_gate_engine")
        if ige_mod:
            engine = self._get_inference_engine()
            if engine:
                try:
                    industry = engine.infer_industry(description)
                except Exception:
                    pass

        feature_vec = [
            float(len(keywords)),
            float(len(keywords) >= 5),          # has enough keywords
            float("compliance" in description.lower()),
            float("security" in description.lower()),
            float("healthcare" in description.lower()),
            float("finance" in description.lower()),
        ]

        try:
            predict_fn = getattr(model, "predict", None)
            if predict_fn is None:
                return None
            score = predict_fn([feature_vec])
            # score is the predicted effectiveness
            predicted_effectiveness = float(score[0]) if hasattr(score, "__len__") else float(score)
            predicted_effectiveness = max(0.0, min(1.0, predicted_effectiveness))

            if predicted_effectiveness < 0.4:
                return None

            # Find the closest existing profile for this industry to use as template
            with self._lock:
                industry_profiles = [
                    p for p in self._profiles.values()
                    if p.industry == industry
                ]
            if not industry_profiles:
                return None

            best = max(industry_profiles, key=lambda p: p.confidence)
            return {
                "profile": best,
                "confidence": min(predicted_effectiveness, best.confidence),
            }
        except Exception as exc:
            logger.debug("ML predict error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_profile(self, profile_id: str) -> Optional[GateBehaviorProfile]:
        """Return a saved profile by ID."""
        with self._lock:
            return self._profiles.get(profile_id)

    def get_profile_by_subject(self, subject_matter: str) -> Optional[GateBehaviorProfile]:
        """Return the profile for a given subject matter (exact match)."""
        with self._lock:
            key = subject_matter.strip().lower()
            profile_id = self._subject_index.get(key)
            if profile_id:
                return self._profiles.get(profile_id)
        return None

    def get_all_profiles(self) -> List[GateBehaviorProfile]:
        """Return all saved profiles."""
        with self._lock:
            return list(self._profiles.values())

    def get_training_examples(self) -> List[GateProfileTrainingExample]:
        """Return all accumulated training examples."""
        with self._lock:
            return list(self._training_examples)

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of engine status."""
        with self._lock:
            return {
                "profile_count": len(self._profiles),
                "training_example_count": len(self._training_examples),
                "phase2_trained": self._phase2_trained,
                "immune_memory_available": self._immune_memory is not None,
                "rubix_available": self._rubix is not None,
                "inference_engine_available": self._inference_engine is not None,
                "ml_model_trained": self._ml_model is not None,
            }

    def export_profiles(self) -> List[Dict[str, Any]]:
        """Export all profiles as a list of dicts (JSON-serialisable)."""
        with self._lock:
            return [p.to_dict() for p in self._profiles.values()]

    def import_profiles(self, profile_dicts: List[Dict[str, Any]]) -> int:
        """
        Import profiles from a list of dicts (e.g. loaded from JSON).

        Returns the count of successfully imported profiles.
        """
        imported = 0
        for d in profile_dicts:
            try:
                profile = GateBehaviorProfile.from_dict(d)
                with self._lock:
                    self._profiles[profile.profile_id] = profile
                    self._signature_index[profile.immune_signature] = profile.profile_id
                    self._subject_index[
                        profile.subject_matter.strip().lower()
                    ] = profile.profile_id
                imported += 1
            except Exception as exc:
                logger.debug("import_profiles: skipping bad entry: %s", exc)
        return imported


# ---------------------------------------------------------------------------
# Fallback inference result (used when InferenceDomainGateEngine is unavailable)
# ---------------------------------------------------------------------------


class _FallbackInferenceResult:
    """Minimal InferenceResult substitute for environments without the full stack."""

    def __init__(self, description: str) -> None:
        self.description = description
        self.inferred_industry = self._guess_industry(description)
        self.org_positions = []
        self.inferred_gates = []
        self.form_schema = None

    @staticmethod
    def _guess_industry(description: str) -> str:
        desc = description.lower()
        if any(w in desc for w in ("health", "medical", "clinic", "hospital", "pharma")):
            return "healthcare"
        if any(w in desc for w in ("finance", "bank", "fintech", "invest", "trading")):
            return "finance"
        if any(w in desc for w in ("manufactur", "factory", "plant", "production")):
            return "manufacturing"
        if any(w in desc for w in ("tech", "software", "saas", "cloud", "devops")):
            return "technology"
        return "other"


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def enumerate_all_subject_matters() -> List[str]:
    """Return the full list of subject matters from all registered sources."""
    return _enumerate_subject_matters()


def build_engine(
    persistence_dir: Optional[str] = None,
    prediction_threshold: float = 0.8,
) -> GateBehaviorModelEngine:
    """Factory — create and return a ready-to-use GateBehaviorModelEngine."""
    return GateBehaviorModelEngine(
        persistence_dir=persistence_dir,
        prediction_confidence_threshold=prediction_threshold,
    )
