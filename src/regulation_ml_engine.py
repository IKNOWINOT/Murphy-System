"""
Regulation ML Engine — Murphy System

Design Label: REG-ML-001
Owner: Platform Engineering
Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1

Orchestrates:
  Phase 1 — Enumerate every (country, industry) scenario, run causal + Rubix
             pipeline per scenario, save RegulationProfile objects, seed immune
             memory for fast-path lookup.
  Phase 2 — Feature-engineer all profiles, train ML model (NaiveBayes +
             OnlineIncrementalLearner + EnsemblePredictor, pure-Python lookup
             fallback), export JSON-serialisable model.
  Phase 3 — predict_optimal_toggles(), predict_gate_config_for_regulation_set(),
             get_conflict_report(), get_co_occurrence_insights().

Integration points:
  - Wire into ComplianceToggleManager.get_recommended_frameworks() for ML-
    enhanced recommendations.
  - Register commands: regulation ml status / train / predict.

Thread-safe — all shared state protected by RLock.
Lazy imports — optional dependencies guarded by try/except.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_PROFILES = 5_000
_MAX_AUDIT_LOG = 5_000
_MAX_CO_OCC_LOG = 10_000

# ---------------------------------------------------------------------------
# Module-level immune memory (profile_id → RegulationProfile)
# ---------------------------------------------------------------------------
_REG_IMMUNE_MEMORY: Dict[str, "RegulationProfile"] = {}
_REG_IMMUNE_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:  # type: ignore[misc]
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)


try:
    from compliance_toggle_manager import (
        ALL_FRAMEWORKS,
        _COUNTRY_FRAMEWORKS,
        _INDUSTRY_FRAMEWORKS,
    )
    _HAS_COMPLIANCE = True
except ImportError:
    _HAS_COMPLIANCE = False
    ALL_FRAMEWORKS: List[str] = []  # type: ignore[assignment]
    _COUNTRY_FRAMEWORKS: Dict[str, List[str]] = {}  # type: ignore[assignment]
    _INDUSTRY_FRAMEWORKS: Dict[str, List[str]] = {}  # type: ignore[assignment]


try:
    from self_codebase_swarm import BMS_COMPLIANCE_STANDARDS
    _HAS_BMS = True
except ImportError:
    _HAS_BMS = False
    BMS_COMPLIANCE_STANDARDS: Dict[str, str] = {  # type: ignore[assignment]
        "ASHRAE_135": "BACnet Standard ANSI/ASHRAE 135",
        "ASHRAE_62_1": "ASHRAE 62.1 Ventilation for Acceptable Indoor Air Quality",
        "ASHRAE_90_1": "ASHRAE 90.1 Energy Standard for Buildings",
        "NFPA_72": "NFPA 72 National Fire Alarm and Signaling Code",
        "NFPA_101": "NFPA 101 Life Safety Code",
        "IBC_2021": "International Building Code 2021",
        "LEED_V4": "LEED v4 Building Operations & Maintenance",
        "ISO_16484": "ISO 16484 Building Automation and Control Systems",
        "IEEE_802_3": "IEEE 802.3 Ethernet Standard",
    }


try:
    from ml_strategy_engine import (
        NaiveBayesClassifier,
        OnlineIncrementalLearner,
        EnsemblePredictor,
        EnsembleStrategy,
    )
    _HAS_ML = True
except ImportError:
    _HAS_ML = False
    NaiveBayesClassifier = None  # type: ignore[assignment,misc]
    OnlineIncrementalLearner = None  # type: ignore[assignment,misc]
    EnsemblePredictor = None  # type: ignore[assignment,misc]
    EnsembleStrategy = None  # type: ignore[assignment,misc]


try:
    from causality_sandbox import CausalitySandboxEngine
    _HAS_CAUSALITY = True
except ImportError:
    _HAS_CAUSALITY = False
    CausalitySandboxEngine = None  # type: ignore[assignment,misc]


try:
    from rubixcube_bot.rubix_evidence_adapter import RubixEvidenceAdapter
    _HAS_RUBIX = True
except ImportError:
    _HAS_RUBIX = False
    RubixEvidenceAdapter = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Gate types (mirrors gate_behavior_model_engine.py)
# ---------------------------------------------------------------------------

_ALL_GATE_TYPES: List[str] = [
    "compliance",
    "budget",
    "executive",
    "operations",
    "qa",
    "hitl",
    "regulatory",
    "audit",
    "safety",
    "quality",
    "environmental",
    "calibration",
    "security",
    "monitoring",
    "performance",
    "business",
]

# Regulation → applicable gate types
_FRAMEWORK_GATE_MAP: Dict[str, List[str]] = {
    # Data Privacy
    "gdpr": ["compliance", "regulatory", "audit", "security"],
    "ccpa": ["compliance", "regulatory", "audit", "security"],
    "lgpd": ["compliance", "regulatory", "audit"],
    "pipeda": ["compliance", "regulatory", "audit"],
    "privacy_act_au": ["compliance", "regulatory", "audit"],
    "appi": ["compliance", "regulatory", "audit"],
    "popia": ["compliance", "regulatory", "audit"],
    "pdpa": ["compliance", "regulatory", "audit"],
    "coppa": ["compliance", "regulatory", "audit", "quality"],
    "ferpa": ["compliance", "regulatory", "audit"],
    "dsgvo": ["compliance", "regulatory", "audit", "security"],
    # Financial
    "pci_dss": ["compliance", "security", "audit", "regulatory"],
    "sox": ["compliance", "audit", "executive", "regulatory"],
    "aml_kyc": ["compliance", "regulatory", "audit", "hitl"],
    "glba": ["compliance", "regulatory", "security", "audit"],
    "basel_iii": ["compliance", "regulatory", "budget", "executive"],
    "mifid_ii": ["compliance", "regulatory", "audit", "monitoring"],
    "psd2": ["compliance", "regulatory", "security", "audit"],
    "dora": ["compliance", "regulatory", "operations", "monitoring"],
    # Healthcare
    "hipaa": ["compliance", "security", "audit", "regulatory", "quality"],
    "hitech": ["compliance", "security", "audit", "regulatory"],
    "fda_21_cfr_11": ["compliance", "regulatory", "audit", "qa", "quality"],
    # Industry & Safety
    "iso_9001": ["quality", "audit", "compliance", "operations"],
    "iso_14001": ["environmental", "audit", "compliance", "operations"],
    "iso_27001": ["security", "compliance", "audit", "regulatory"],
    "iso_45001": ["safety", "audit", "compliance", "operations"],
    "osha": ["safety", "regulatory", "audit", "operations"],
    "ce_marking": ["safety", "quality", "compliance", "regulatory"],
    "ul_certification": ["safety", "quality", "compliance"],
    "isa_95": ["operations", "compliance", "qa", "monitoring"],
    "iec_61131": ["qa", "safety", "compliance", "calibration"],
    "nfpa": ["safety", "regulatory", "compliance", "audit"],
    # Government & Defense
    "fedramp": ["compliance", "security", "audit", "regulatory"],
    "cmmc": ["compliance", "security", "audit", "regulatory"],
    "nist_800_171": ["compliance", "security", "regulatory"],
    "itar": ["compliance", "regulatory", "audit", "executive"],
    "nis2": ["compliance", "security", "regulatory", "monitoring"],
    # Security
    "soc2": ["compliance", "security", "audit", "quality"],
    "soc1": ["compliance", "audit", "security"],
    "nist_csf": ["compliance", "security", "monitoring", "audit"],
    "cis_controls": ["security", "compliance", "monitoring"],
    "csa_star": ["security", "compliance", "audit"],
}

# Industry → BMS standards (building-related industries get BMS standards)
_INDUSTRY_BMS_MAP: Dict[str, List[str]] = {
    "manufacturing": ["ASHRAE_90_1", "ISO_16484", "IBC_2021"],
    "healthcare": ["ASHRAE_62_1", "ASHRAE_90_1", "NFPA_72", "NFPA_101", "IBC_2021"],
    "government": ["ASHRAE_90_1", "LEED_V4", "IBC_2021"],
    "general": ["ASHRAE_135", "ASHRAE_90_1"],
}

# Known conflict pairs: enabling both triggers a conflict flag
_KNOWN_CONFLICTS: List[Tuple[str, str]] = [
    ("gdpr", "dsgvo"),          # Redundant — DSGVO is the German implementation of GDPR
    ("soc1", "soc2"),           # Overlapping controls — typically choose one
    ("nist_800_171", "cmmc"),   # CMMC encompasses NIST 800-171; combined = redundant
    ("ferpa", "coppa"),         # Age-group overlap may cause conflicting data requirements
]

# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------


@dataclass
class RegulationProfile:
    """Optimised gate configuration for a specific (country, industry) scenario."""

    profile_id: str
    country_code: str
    industry: str
    enabled_frameworks: List[str]
    bms_standards: List[str]
    gate_types: List[str]
    gate_weights: Dict[str, float]
    gate_ordering: List[str]
    co_occurrence_score: float
    conflict_score: float
    efficiency_score: float
    rubix_confidence: float
    simulation_result: Dict[str, Any]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "country_code": self.country_code,
            "industry": self.industry,
            "enabled_frameworks": self.enabled_frameworks,
            "bms_standards": self.bms_standards,
            "gate_types": self.gate_types,
            "gate_weights": self.gate_weights,
            "gate_ordering": self.gate_ordering,
            "co_occurrence_score": self.co_occurrence_score,
            "conflict_score": self.conflict_score,
            "efficiency_score": self.efficiency_score,
            "rubix_confidence": self.rubix_confidence,
            "simulation_result": self.simulation_result,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_profile_key(country_code: str, industry: str) -> str:
    """Stable cache key for a (country, industry) pair."""
    return f"{country_code.upper()}:{industry.lower()}"


def _frameworks_bitmask(frameworks: List[str], all_fw: List[str]) -> int:
    """Encode a list of framework IDs as an integer bitmask."""
    bitmask = 0
    for i, fw in enumerate(all_fw):
        if fw in frameworks:
            bitmask |= 1 << i
    return bitmask


def _bms_bitmask(bms_stds: List[str]) -> int:
    """Encode a list of BMS standard keys as an integer bitmask."""
    keys = list(BMS_COMPLIANCE_STANDARDS.keys())
    bitmask = 0
    for i, k in enumerate(keys):
        if k in bms_stds:
            bitmask |= 1 << i
    return bitmask


def _gate_vector(gate_types: List[str]) -> List[int]:
    """Encode gate type presence as a binary vector."""
    return [1 if g in gate_types else 0 for g in _ALL_GATE_TYPES]


def _derive_gate_types(frameworks: List[str]) -> List[str]:
    """Heuristically derive applicable gate types from a set of frameworks."""
    seen: set = set()
    result: List[str] = []
    for fw in frameworks:
        for gt in _FRAMEWORK_GATE_MAP.get(fw, ["compliance"]):
            if gt not in seen:
                result.append(gt)
                seen.add(gt)
    # Always include at minimum compliance and audit
    for base in ("compliance", "audit"):
        if base not in seen:
            result.append(base)
    return result


def _compute_gate_weights(gate_types: List[str]) -> Dict[str, float]:
    """Assign weights to gate types based on priority heuristics."""
    _priority: Dict[str, float] = {
        "safety": 1.0,
        "regulatory": 0.95,
        "compliance": 0.9,
        "security": 0.88,
        "audit": 0.85,
        "quality": 0.82,
        "hitl": 0.80,
        "executive": 0.78,
        "environmental": 0.75,
        "calibration": 0.72,
        "operations": 0.70,
        "monitoring": 0.65,
        "performance": 0.60,
        "budget": 0.55,
        "business": 0.50,
        "qa": 0.80,
    }
    return {g: _priority.get(g, 0.5) for g in gate_types}


def _order_gates(gate_weights: Dict[str, float]) -> List[str]:
    """Sort gates by descending weight for optimal execution ordering."""
    return sorted(gate_weights, key=lambda g: -gate_weights[g])


def _count_conflicts(frameworks: List[str]) -> float:
    """Return number of known conflict pairs present in *frameworks*."""
    fw_set = set(frameworks)
    count = 0.0
    for a, b in _KNOWN_CONFLICTS:
        if a in fw_set and b in fw_set:
            count += 1.0
    return count


def _derive_bms_standards(industry: str) -> List[str]:
    """Return applicable BMS standards for an industry."""
    return list(_INDUSTRY_BMS_MAP.get(industry.lower(), _INDUSTRY_BMS_MAP.get("general", [])))


def _run_causal_simulation(
    frameworks: List[str],
    gate_types: List[str],
    causality_engine: Any,
) -> Dict[str, Any]:
    """Run causal simulation if available, otherwise return a stub result."""
    if causality_engine is None:
        return {
            "status": "stub",
            "efficiency_score": max(0.5, 1.0 - 0.02 * len(frameworks)),
            "gate_count": len(gate_types),
        }
    try:
        result = causality_engine.simulate(
            subject=f"regulation_scenario_{len(frameworks)}_frameworks",
            context={"frameworks": frameworks, "gate_types": gate_types},
        )
        if isinstance(result, dict):
            return result
    except Exception as exc:  # noqa: BLE001
        logger.debug("Causal simulation unavailable for regulation scenario: %s", exc)
    return {
        "status": "stub",
        "efficiency_score": max(0.5, 1.0 - 0.02 * len(frameworks)),
        "gate_count": len(gate_types),
    }


def _run_rubix_validation(
    profile: Dict[str, Any],
    rubix: Any,
) -> float:
    """Return Rubix confidence score, falling back to a heuristic."""
    if rubix is None:
        efficiency = profile.get("efficiency_score", 0.7)
        conflict_score = profile.get("conflict_score", 0.0)
        return max(0.0, min(1.0, efficiency - 0.05 * conflict_score))
    try:
        confidence = rubix.evaluate_evidence(profile)
        if isinstance(confidence, (int, float)):
            return float(confidence)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Rubix evidence evaluation unavailable: %s", exc)
    return 0.7


# ---------------------------------------------------------------------------
# Regulation ML Engine
# ---------------------------------------------------------------------------


class RegulationMLEngine:
    """
    ML engine that learns optimal regulation toggle configurations.

    Usage::

        engine = RegulationMLEngine()
        engine.train()  # runs Phase 1 + Phase 2
        result = engine.predict_optimal_toggles("DE", "finance")
        print(result["recommended_frameworks"])
    """

    MODULE_NAME = "regulation_ml_engine"
    MODULE_VERSION = "1.0.0"

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Phase 1 output
        self._profiles: Dict[str, RegulationProfile] = {}
        self._audit_log: List[Dict[str, Any]] = []

        # Phase 2 output
        self._model: Dict[str, Any] = {}
        self._trained = False
        self._build_time_sec: float = 0.0

        # Co-occurrence tracking
        self._co_occurrence: Dict[str, int] = {}
        self._co_occurrence_log: List[Dict[str, Any]] = []

        # Lazy subsystems
        self._causality_engine: Optional[Any] = None
        self._rubix: Optional[Any] = None

    # ------------------------------------------------------------------
    # Subsystem accessors (lazy init)
    # ------------------------------------------------------------------

    def _get_causality_engine(self) -> Optional[Any]:
        if not _HAS_CAUSALITY:
            return None
        if self._causality_engine is None:
            try:
                self._causality_engine = CausalitySandboxEngine()
            except Exception as exc:  # noqa: BLE001
                logger.debug("CausalitySandboxEngine init failed: %s", exc)
        return self._causality_engine

    def _get_rubix(self) -> Optional[Any]:
        if not _HAS_RUBIX:
            return None
        if self._rubix is None:
            try:
                self._rubix = RubixEvidenceAdapter()
            except Exception as exc:  # noqa: BLE001
                logger.debug("RubixEvidenceAdapter init failed: %s", exc)
        return self._rubix

    # ------------------------------------------------------------------
    # Phase 1 — Enumerate & Profile
    # ------------------------------------------------------------------

    def _generate_scenario_matrix(self) -> List[Tuple[str, str, List[str]]]:
        """
        Build the full scenario matrix: (country_code, industry, frameworks).

        Covers every country in _COUNTRY_FRAMEWORKS × every industry in
        _INDUSTRY_FRAMEWORKS.  Adds a wildcard ("*", industry) row for
        countries with no dedicated entry.
        """
        scenarios: List[Tuple[str, str, List[str]]] = []

        all_industries = list(_INDUSTRY_FRAMEWORKS.keys()) if _INDUSTRY_FRAMEWORKS else ["general"]
        all_countries = list(_COUNTRY_FRAMEWORKS.keys()) if _COUNTRY_FRAMEWORKS else ["US"]

        if not all_countries:
            all_countries = ["US"]
        if not all_industries:
            all_industries = ["general"]

        seen_keys: set = set()

        for country in all_countries:
            country_fws = _COUNTRY_FRAMEWORKS.get(country, [])
            for industry in all_industries:
                industry_fws = _INDUSTRY_FRAMEWORKS.get(industry, _INDUSTRY_FRAMEWORKS.get("general", []))
                merged: List[str] = []
                seen: set = set()
                for fw in (country_fws + industry_fws):
                    fw_catalog = ALL_FRAMEWORKS if ALL_FRAMEWORKS else []
                    if fw in fw_catalog and fw not in seen:
                        merged.append(fw)
                        seen.add(fw)
                key = _make_profile_key(country, industry)
                if key not in seen_keys:
                    scenarios.append((country, industry, merged))
                    seen_keys.add(key)

        return scenarios

    def _profile_scenario(
        self,
        country_code: str,
        industry: str,
        frameworks: List[str],
    ) -> RegulationProfile:
        """Run Phase 1 pipeline for one scenario and return a RegulationProfile."""
        gate_types = _derive_gate_types(frameworks)
        gate_weights = _compute_gate_weights(gate_types)
        gate_ordering = _order_gates(gate_weights)
        bms_standards = _derive_bms_standards(industry)
        conflict_score = _count_conflicts(frameworks)

        causality_engine = self._get_causality_engine()
        sim_result = _run_causal_simulation(frameworks, gate_types, causality_engine)
        efficiency_score = float(sim_result.get("efficiency_score", 0.7))

        profile_dict = {
            "efficiency_score": efficiency_score,
            "conflict_score": conflict_score,
            "frameworks": frameworks,
            "gate_types": gate_types,
        }
        rubix_confidence = _run_rubix_validation(profile_dict, self._get_rubix())

        # Co-occurrence tracking: count each pair
        for i, fw_a in enumerate(frameworks):
            for fw_b in frameworks[i + 1:]:
                co_key = ":".join(sorted([fw_a, fw_b]))
                self._co_occurrence[co_key] = self._co_occurrence.get(co_key, 0) + 1

        total_scenarios = max(1, len(_COUNTRY_FRAMEWORKS) * max(1, len(_INDUSTRY_FRAMEWORKS)))
        co_occurrence_score = (
            sum(self._co_occurrence.get(":".join(sorted([a, b])), 0)
                for i, a in enumerate(frameworks)
                for b in frameworks[i + 1:]) / max(1, total_scenarios)
        )

        profile = RegulationProfile(
            profile_id=str(uuid.uuid4()),
            country_code=country_code.upper(),
            industry=industry.lower(),
            enabled_frameworks=list(frameworks),
            bms_standards=bms_standards,
            gate_types=gate_types,
            gate_weights=gate_weights,
            gate_ordering=gate_ordering,
            co_occurrence_score=round(co_occurrence_score, 4),
            conflict_score=conflict_score,
            efficiency_score=round(efficiency_score, 4),
            rubix_confidence=round(rubix_confidence, 4),
            simulation_result=sim_result,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return profile

    def run_phase1(self) -> int:
        """
        Enumerate all scenarios, profile each, store in immune memory.

        Returns number of profiles generated.
        """
        scenarios = self._generate_scenario_matrix()
        profiles_added = 0
        for country, industry, frameworks in scenarios:
            key = _make_profile_key(country, industry)
            profile = self._profile_scenario(country, industry, frameworks)

            with self._lock:
                if len(self._profiles) >= _MAX_PROFILES:
                    # Remove oldest 10% when at capacity
                    trim_keys = list(self._profiles.keys())[: _MAX_PROFILES // 10]
                    for tk in trim_keys:
                        del self._profiles[tk]
                self._profiles[key] = profile

            # Seed immune memory
            with _REG_IMMUNE_LOCK:
                _REG_IMMUNE_MEMORY[key] = profile

            profiles_added += 1

        logger.info("RegulationMLEngine Phase 1: %d profiles generated", profiles_added)
        return profiles_added

    # ------------------------------------------------------------------
    # Phase 2 — ML Training
    # ------------------------------------------------------------------

    def _build_features(self, profile: RegulationProfile) -> Dict[str, Any]:
        """Convert a RegulationProfile into an ML feature dict."""
        all_fw = ALL_FRAMEWORKS if ALL_FRAMEWORKS else list(_FRAMEWORK_GATE_MAP.keys())
        return {
            "country_code": profile.country_code,
            "industry": profile.industry,
            "enabled_frameworks_bitmask": _frameworks_bitmask(profile.enabled_frameworks, all_fw),
            "bms_standards_bitmask": _bms_bitmask(profile.bms_standards),
            "gate_types_vector": _gate_vector(profile.gate_types),
            "co_occurrence_score": profile.co_occurrence_score,
            "conflict_score": profile.conflict_score,
            "efficiency_score": profile.efficiency_score,
            "rubix_confidence": profile.rubix_confidence,
        }

    def run_phase2(self) -> Dict[str, Any]:
        """
        Train the ML model on all Phase 1 profiles.

        Returns the exported model dict.
        """
        with self._lock:
            profiles = list(self._profiles.values())

        if not profiles:
            logger.warning("RegulationMLEngine Phase 2: no profiles available, run Phase 1 first")
            return {}

        if _HAS_ML and NaiveBayesClassifier is not None:
            return self._train_with_ml(profiles)
        return self._train_stub(profiles)

    def _train_with_ml(self, profiles: List[RegulationProfile]) -> Dict[str, Any]:
        """ML-backed training path."""
        try:
            nb = NaiveBayesClassifier()
            oil = OnlineIncrementalLearner()

            for p in profiles:
                if not p.gate_types:
                    continue
                label = p.gate_types[0]
                features: Dict[str, Any] = {
                    p.country_code: 1,
                    p.industry: 1,
                    f"bitmask_{p.enabled_frameworks.__hash__() & 0xFFFF}": 1,
                }
                nb.train(features, label)
                oil.update(features, label)

            ep = None
            if EnsemblePredictor is not None and EnsembleStrategy is not None:
                try:
                    ep = EnsemblePredictor(
                        classifiers=[nb],
                        strategy=EnsembleStrategy.MAJORITY_VOTE,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("EnsemblePredictor init skipped: %s", exc)
                    ep = None

            with self._lock:
                self._model = {
                    "type": "ml",
                    "profile_count": len(profiles),
                    "has_ensemble": ep is not None,
                    "lookup": self.build_lookup(profiles),
                    "_nb": nb,
                    "_oil": oil,
                    "_ep": ep,
                }
                self._trained = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("RegulationMLEngine ML training failed, fallback: %s", exc)
            return self._train_stub(profiles)

        return self._export_model()

    def _train_stub(self, profiles: List[RegulationProfile]) -> Dict[str, Any]:
        """Pure-Python lookup-table fallback when ML is unavailable."""
        with self._lock:
            self._model = {
                "type": "stub",
                "profile_count": len(profiles),
                "lookup": self.build_lookup(profiles),
            }
            self._trained = True
        return self._export_model()

    @staticmethod
    def build_lookup(profiles: List[RegulationProfile]) -> Dict[str, Any]:
        """Build country:industry → serialized profile lookup (public for tests)."""
        lookup: Dict[str, Any] = {}
        for p in profiles:
            key = _make_profile_key(p.country_code, p.industry)
            lookup[key] = {
                "profile_id": p.profile_id,
                "enabled_frameworks": p.enabled_frameworks,
                "bms_standards": p.bms_standards,
                "gate_types": p.gate_types,
                "gate_weights": p.gate_weights,
                "gate_ordering": p.gate_ordering,
                "co_occurrence_score": p.co_occurrence_score,
                "conflict_score": p.conflict_score,
                "efficiency_score": p.efficiency_score,
                "rubix_confidence": p.rubix_confidence,
            }
        return lookup

    def _export_model(self) -> Dict[str, Any]:
        """Return a JSON-serialisable copy of the model (strips private objects)."""
        with self._lock:
            return {k: v for k, v in self._model.items() if not k.startswith("_")}

    # ------------------------------------------------------------------
    # Main train() entry point
    # ------------------------------------------------------------------

    def train(self) -> Dict[str, Any]:
        """Run Phase 1 then Phase 2 and return status."""
        t0 = time.perf_counter()
        self.run_phase1()
        model = self.run_phase2()
        with self._lock:
            self._build_time_sec = time.perf_counter() - t0
        logger.info(
            "RegulationMLEngine.train() complete in %.2fs — %d profiles",
            self._build_time_sec,
            len(self._profiles),
        )
        return model

    # ------------------------------------------------------------------
    # Phase 3 — Predictions & Recommendations
    # ------------------------------------------------------------------

    def predict_optimal_toggles(
        self,
        country_code: str,
        industry: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict the optimal set of enabled regulation toggles for a given
        country + industry combination.

        Returns a dict with:
          - recommended_frameworks  — list of framework IDs to enable
          - confidence              — prediction confidence (0–1)
          - gate_types              — applicable gate types
          - gate_ordering           — optimal gate execution order
          - conflict_score          — number of detected conflicts
          - source                  — "immune_memory" | "model_lookup" | "heuristic"
        """
        key = _make_profile_key(country_code, industry)

        # 1. Immune memory fast-path
        with _REG_IMMUNE_LOCK:
            cached = _REG_IMMUNE_MEMORY.get(key)
        if cached is not None:
            return {
                "recommended_frameworks": list(cached.enabled_frameworks),
                "confidence": cached.rubix_confidence,
                "gate_types": cached.gate_types,
                "gate_ordering": cached.gate_ordering,
                "conflict_score": cached.conflict_score,
                "efficiency_score": cached.efficiency_score,
                "bms_standards": cached.bms_standards,
                "source": "immune_memory",
            }

        # 2. Model lookup
        with self._lock:
            lookup = self._model.get("lookup", {})
        entry = lookup.get(key)
        if entry is not None:
            return {
                "recommended_frameworks": entry["enabled_frameworks"],
                "confidence": entry["rubix_confidence"],
                "gate_types": entry["gate_types"],
                "gate_ordering": entry["gate_ordering"],
                "conflict_score": entry["conflict_score"],
                "efficiency_score": entry["efficiency_score"],
                "bms_standards": entry.get("bms_standards", []),
                "source": "model_lookup",
            }

        # 3. Heuristic fallback — profile on-the-fly
        if not self._trained:
            self.train()

        # Try enhanced lookup after training
        with self._lock:
            lookup = self._model.get("lookup", {})
        entry = lookup.get(key)
        if entry is not None:
            return {
                "recommended_frameworks": entry["enabled_frameworks"],
                "confidence": entry["rubix_confidence"],
                "gate_types": entry["gate_types"],
                "gate_ordering": entry["gate_ordering"],
                "conflict_score": entry["conflict_score"],
                "efficiency_score": entry["efficiency_score"],
                "bms_standards": entry.get("bms_standards", []),
                "source": "model_lookup",
            }

        # 4. Build from scratch (novel combination)
        country_fws = _COUNTRY_FRAMEWORKS.get(country_code.upper(), [])
        industry_fws = _INDUSTRY_FRAMEWORKS.get(
            industry.lower(),
            _INDUSTRY_FRAMEWORKS.get("general", []) if _INDUSTRY_FRAMEWORKS else [],
        )
        all_fw = ALL_FRAMEWORKS if ALL_FRAMEWORKS else list(_FRAMEWORK_GATE_MAP.keys())
        merged: List[str] = []
        seen: set = set()
        for fw in country_fws + industry_fws:
            if fw in all_fw and fw not in seen:
                merged.append(fw)
                seen.add(fw)

        profile = self._profile_scenario(country_code, industry, merged)
        with self._lock:
            self._profiles[key] = profile
        with _REG_IMMUNE_LOCK:
            _REG_IMMUNE_MEMORY[key] = profile

        return {
            "recommended_frameworks": profile.enabled_frameworks,
            "confidence": profile.rubix_confidence,
            "gate_types": profile.gate_types,
            "gate_ordering": profile.gate_ordering,
            "conflict_score": profile.conflict_score,
            "efficiency_score": profile.efficiency_score,
            "bms_standards": profile.bms_standards,
            "source": "heuristic",
        }

    def predict_gate_config_for_regulation_set(
        self,
        enabled_frameworks: List[str],
    ) -> Dict[str, Any]:
        """
        Given a specific set of enabled framework IDs, predict the best gate
        configuration (types, weights, ordering).
        """
        gate_types = _derive_gate_types(enabled_frameworks)
        gate_weights = _compute_gate_weights(gate_types)
        gate_ordering = _order_gates(gate_weights)
        conflict_score = _count_conflicts(enabled_frameworks)

        causality_engine = self._get_causality_engine()
        sim_result = _run_causal_simulation(enabled_frameworks, gate_types, causality_engine)
        efficiency_score = float(sim_result.get("efficiency_score", 0.7))

        return {
            "gate_types": gate_types,
            "gate_weights": gate_weights,
            "gate_ordering": gate_ordering,
            "conflict_score": conflict_score,
            "efficiency_score": round(efficiency_score, 4),
            "simulation_result": sim_result,
        }

    def get_conflict_report(
        self,
        enabled_frameworks: List[str],
    ) -> Dict[str, Any]:
        """
        Identify conflicts and redundancies in a proposed toggle set.

        Returns a dict with:
          - conflicts       — list of conflicting pairs
          - redundancies    — frameworks subsumed by others in the set
          - conflict_count  — total detected conflicts
          - is_clean        — True if no conflicts or redundancies
        """
        fw_set = set(enabled_frameworks)
        conflicts = []
        for a, b in _KNOWN_CONFLICTS:
            if a in fw_set and b in fw_set:
                conflicts.append({
                    "framework_a": a,
                    "framework_b": b,
                    "reason": f"{a} and {b} have overlapping or conflicting requirements",
                })

        # Redundancy check: dsgvo ⊂ gdpr when both enabled
        redundancies = []
        _SUBSUMPTIONS = [
            ("dsgvo", "gdpr", "DSGVO is the German implementation of GDPR; enabling both is redundant"),
            ("cmmc", "nist_800_171", "CMMC encompasses NIST 800-171; enabling both adds redundant controls"),
        ]
        for child, parent, reason in _SUBSUMPTIONS:
            if child in fw_set and parent in fw_set:
                redundancies.append({"framework": child, "subsumed_by": parent, "reason": reason})

        return {
            "conflicts": conflicts,
            "redundancies": redundancies,
            "conflict_count": len(conflicts),
            "redundancy_count": len(redundancies),
            "is_clean": len(conflicts) == 0 and len(redundancies) == 0,
            "enabled_frameworks": list(enabled_frameworks),
        }

    def get_co_occurrence_insights(self) -> Dict[str, Any]:
        """
        Report which regulation combinations are most common, most efficient,
        and most problematic based on profiled scenarios.
        """
        with self._lock:
            co_occ = dict(self._co_occurrence)
            profiles = list(self._profiles.values())

        if not co_occ and not profiles:
            return {
                "status": "no_data",
                "message": "Run train() first to generate co-occurrence data",
                "top_pairs": [],
                "most_efficient_combo": None,
                "most_conflicted_combo": None,
            }

        # Top co-occurring pairs
        sorted_pairs = sorted(co_occ.items(), key=lambda x: -x[1])
        top_pairs = [
            {"pair": k, "count": v}
            for k, v in sorted_pairs[:10]
        ]

        # Most efficient scenario
        most_efficient = max(profiles, key=lambda p: p.efficiency_score) if profiles else None
        # Most conflicted scenario
        most_conflicted = max(profiles, key=lambda p: p.conflict_score) if profiles else None

        return {
            "status": "ok",
            "total_scenarios_profiled": len(profiles),
            "unique_pair_combinations": len(co_occ),
            "top_pairs": top_pairs,
            "most_efficient_combo": {
                "country": most_efficient.country_code,
                "industry": most_efficient.industry,
                "efficiency_score": most_efficient.efficiency_score,
                "frameworks": most_efficient.enabled_frameworks,
            } if most_efficient else None,
            "most_conflicted_combo": {
                "country": most_conflicted.country_code,
                "industry": most_conflicted.industry,
                "conflict_score": most_conflicted.conflict_score,
                "frameworks": most_conflicted.enabled_frameworks,
            } if most_conflicted else None,
        }

    # ------------------------------------------------------------------
    # Public model export
    # ------------------------------------------------------------------

    def export_model(self) -> Dict[str, Any]:
        """Return the trained model as a JSON-serialisable dict."""
        return self._export_model()

    def get_all_profiles(self) -> List[RegulationProfile]:
        """Return all saved RegulationProfile objects."""
        with self._lock:
            return list(self._profiles.values())

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a Murphy-standard module status dict."""
        with self._lock:
            return {
                "module": self.MODULE_NAME,
                "version": self.MODULE_VERSION,
                "trained": self._trained,
                "profile_count": len(self._profiles),
                "build_time_sec": round(self._build_time_sec, 3),
                "immune_memory_size": len(_REG_IMMUNE_MEMORY),
                "model_type": self._model.get("type", "none"),
                "ml_available": _HAS_ML,
                "causality_available": _HAS_CAUSALITY,
                "rubix_available": _HAS_RUBIX,
                "compliance_catalog_available": _HAS_COMPLIANCE,
                "bms_catalog_available": _HAS_BMS,
                "framework_count": len(ALL_FRAMEWORKS),
                "country_count": len(_COUNTRY_FRAMEWORKS),
                "industry_count": len(_INDUSTRY_FRAMEWORKS),
                "bms_standard_count": len(BMS_COMPLIANCE_STANDARDS),
            }


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_ENGINE_SINGLETON: Optional[RegulationMLEngine] = None
_ENGINE_SINGLETON_LOCK = threading.Lock()


def get_engine() -> RegulationMLEngine:
    """Return the module-level singleton RegulationMLEngine (lazy init)."""
    global _ENGINE_SINGLETON
    with _ENGINE_SINGLETON_LOCK:
        if _ENGINE_SINGLETON is None:
            _ENGINE_SINGLETON = RegulationMLEngine()
    return _ENGINE_SINGLETON


def get_status() -> Dict[str, Any]:
    """Module-level get_status() following Murphy module pattern."""
    return get_engine().get_status()
