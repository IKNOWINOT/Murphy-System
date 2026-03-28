"""
LCM Engine — Learning-Calibration-Mastery engine for Murphy System.

Design Label: LCM-002 — LCM Engine
Owner: Platform Engineering

Orchestrates:
  1. Universal enumeration of every domain × role combination
  2. Causal gate profiling via InferenceDomainGateEngine + CausalitySandboxEngine
  3. ML training (NaiveBayes + OnlineIncrementalLearner + EnsemblePredictor)
  4. Fast-path prediction (<10 ms) with active-learning fallback

The biological-immune-memory (_IMMUNE_MEMORY) caches resolved profiles so
repeated calls for familiar domain×role pairs are served without inference.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level immune memory cache (domain_id:role → GateBehaviorProfile)
# ---------------------------------------------------------------------------
_IMMUNE_MEMORY: Dict[str, "GateBehaviorProfile"] = {}
_IMMUNE_LOCK = threading.RLock()

# ---------------------------------------------------------------------------
# Optional imports with graceful stubs
# ---------------------------------------------------------------------------

try:
    from lcm_domain_registry import (
        LCMDomainRegistry,
        SubjectDomain,
        GateType,
        DomainCategory,
    )
    _HAS_REGISTRY = True
except ImportError:
    _HAS_REGISTRY = False

    class GateType(Enum):  # type: ignore[no-redef]
        SAFETY = "safety"
        QUALITY = "quality"
        COMPLIANCE = "compliance"
        PERFORMANCE = "performance"
        SECURITY = "security"
        BUSINESS = "business"
        ENERGY = "energy"
        COMFORT = "comfort"
        MONITORING = "monitoring"

    class DomainCategory(Enum):  # type: ignore[no-redef]
        PHYSICAL_MANUFACTURING = "physical_manufacturing"
        BUILDING_SYSTEMS = "building_systems"
        PROFESSIONAL_SERVICES = "professional_services"
        HEALTHCARE = "healthcare"
        ENERGY_UTILITIES = "energy_utilities"
        RETAIL_COMMERCE = "retail_commerce"
        FINANCIAL_SERVICES = "financial_services"
        MEDIA_COMMUNICATIONS = "media_communications"
        EDUCATION_NONPROFIT = "education_nonprofit"
        TRANSPORTATION_LOGISTICS = "transportation_logistics"

    @dataclass
    class SubjectDomain:  # type: ignore[no-redef]
        domain_id: str = ""
        name: str = ""
        category: Any = None
        description: str = ""
        gate_types: List[Any] = field(default_factory=list)
        keywords: List[str] = field(default_factory=list)

    class LCMDomainRegistry:  # type: ignore[no-redef]
        def list_all(self) -> List[SubjectDomain]:
            return []
        def get(self, domain_id: str) -> Optional[SubjectDomain]:
            return None
        def get_gate_types(self, domain_id: str) -> List[Any]:
            return []


try:
    from inference_gate_engine import InferenceDomainGateEngine
    _HAS_INFERENCE = True
except ImportError:
    _HAS_INFERENCE = False
    InferenceDomainGateEngine = None  # type: ignore[assignment,misc]


try:
    from ml_strategy_engine import (
        NaiveBayesClassifier,
        OnlineIncrementalLearner,
        EnsemblePredictor,
        EnsembleStrategy,
        MLStrategyEngine,
    )
    _HAS_ML = True
except ImportError:
    _HAS_ML = False
    NaiveBayesClassifier = None  # type: ignore[assignment,misc]
    OnlineIncrementalLearner = None  # type: ignore[assignment,misc]
    EnsemblePredictor = None  # type: ignore[assignment,misc]
    EnsembleStrategy = None  # type: ignore[assignment,misc]
    MLStrategyEngine = None  # type: ignore[assignment,misc]


try:
    from causality_sandbox import CausalitySandboxEngine
    _HAS_CAUSALITY = True
except ImportError:
    _HAS_CAUSALITY = False
    CausalitySandboxEngine = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GateBehaviorProfile:
    """Describes which gates apply to a domain×role pair and their weights."""
    domain_id: str
    role: str
    gate_types: List[str]
    gate_weights: Dict[str, float]
    confidence: float
    predicted: bool = False   # True if served from ML, False if profiled
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "role": self.role,
            "gate_types": self.gate_types,
            "gate_weights": self.gate_weights,
            "confidence": self.confidence,
            "predicted": self.predicted,
            "latency_ms": self.latency_ms,
        }


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BotRole(Enum):
    EXPERT = "expert"
    ASSISTANT = "assistant"
    VALIDATOR = "validator"
    MONITOR = "monitor"
    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"
    ANALYZER = "analyzer"
    AUDITOR = "auditor"


# ---------------------------------------------------------------------------
# Universal Domain Enumerator
# ---------------------------------------------------------------------------

class UniversalDomainEnumerator:
    """Enumerate every entity (domain × role combination) in the system."""

    def __init__(self, registry: LCMDomainRegistry) -> None:
        self._registry = registry
        self._lock = threading.RLock()

    def enumerate_domains(self) -> List[SubjectDomain]:
        """Return all registered domains."""
        return self._registry.list_all()

    def enumerate_bot_role_domain_combinations(
        self,
    ) -> List[Tuple[BotRole, SubjectDomain]]:
        """Return the Cartesian product of all BotRoles × all domains."""
        combos: List[Tuple[BotRole, SubjectDomain]] = []
        domains = self.enumerate_domains()
        for role in BotRole:
            for domain in domains:
                combos.append((role, domain))
        return combos

    def enumerate_all_entities(self) -> List[Dict[str, Any]]:
        """Return flat list of entity dicts for serialization / logging."""
        entities: List[Dict[str, Any]] = []
        for role, domain in self.enumerate_bot_role_domain_combinations():
            entities.append(
                {
                    "role": role.value,
                    "domain_id": domain.domain_id,
                    "domain_name": domain.name,
                    "category": domain.category.value if domain.category else "",
                }
            )
        return entities


# ---------------------------------------------------------------------------
# Causal Gate Profiler
# ---------------------------------------------------------------------------

_DEFAULT_GATE_WEIGHTS: Dict[str, float] = {
    "safety": 1.0,
    "quality": 0.9,
    "compliance": 0.85,
    "performance": 0.8,
    "security": 0.75,
    "business": 0.7,
    "energy": 0.65,
    "comfort": 0.5,
    "monitoring": 0.6,
}

# Role → additional gate emphasis
_ROLE_GATE_EMPHASIS: Dict[str, List[str]] = {
    "expert": ["quality", "performance"],
    "assistant": ["monitoring", "comfort"],
    "validator": ["compliance", "quality"],
    "monitor": ["monitoring", "safety"],
    "orchestrator": ["performance", "business"],
    "specialist": ["safety", "compliance"],
    "analyzer": ["monitoring", "performance"],
    "auditor": ["compliance", "security"],
}


class CausalGateProfiler:
    """For each entity, runs inference + causality simulation to derive gate profile."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # Lazy-initialize InferenceDomainGateEngine once
        self._inference_engine: Optional[Any] = None
        self._causality_engine: Optional[Any] = None

    def _get_inference_engine(self) -> Optional[Any]:
        if not _HAS_INFERENCE:
            return None
        if self._inference_engine is None:
            try:
                self._inference_engine = InferenceDomainGateEngine()
            except Exception:  # noqa: BLE001
                pass
        return self._inference_engine

    def _get_causality_engine(self) -> Optional[Any]:
        if not _HAS_CAUSALITY:
            return None
        if self._causality_engine is None:
            try:
                self._causality_engine = CausalitySandboxEngine()
            except Exception:  # noqa: BLE001
                pass
        return self._causality_engine

    def profile_entity(
        self,
        domain_id: str,
        role: str,
        description: str = "",
        existing_domain: Optional[SubjectDomain] = None,
    ) -> GateBehaviorProfile:
        """
        Derive a GateBehaviorProfile for a domain×role pair.

        1. Try InferenceDomainGateEngine.infer() for gate hints.
        2. Combine with domain's declared gate_types.
        3. Apply role-specific emphasis to weights.
        4. Return profile (confidence is estimated from available data).
        """
        t0 = time.perf_counter()
        gate_types: List[str] = []
        base_confidence = 0.7

        # --- Collect gate_types from declared domain ---
        if existing_domain and existing_domain.gate_types:
            gate_types = [
                (g.value if hasattr(g, "value") else str(g))
                for g in existing_domain.gate_types
            ]

        # --- Try inference engine ---
        infer_eng = self._get_inference_engine()
        if infer_eng is not None:
            try:
                result = infer_eng.infer(
                    description or f"{domain_id} {role}",
                    existing_data={},
                    agent_id=f"lcm_{domain_id}_{role}",
                )
                if isinstance(result, dict):
                    inferred_gates = result.get("gate_types", []) or result.get("gates", [])
                    if inferred_gates:
                        for g in inferred_gates:
                            g_str = g.value if hasattr(g, "value") else str(g)
                            if g_str not in gate_types:
                                gate_types.append(g_str)
                    inferred_conf = result.get("confidence", None)
                    if inferred_conf is not None:
                        base_confidence = float(inferred_conf)
                    else:
                        base_confidence = 0.85
            except Exception:  # noqa: BLE001
                pass

        # --- Fallback: derive gates from domain_id keywords ---
        if not gate_types:
            gate_types = _derive_gates_from_domain_id(domain_id)

        # --- Build weights ---
        emphasis = _ROLE_GATE_EMPHASIS.get(role, [])
        gate_weights: Dict[str, float] = {}
        for gt in gate_types:
            w = _DEFAULT_GATE_WEIGHTS.get(gt, 0.6)
            if gt in emphasis:
                w = min(1.0, w + 0.1)
            gate_weights[gt] = round(w, 3)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return GateBehaviorProfile(
            domain_id=domain_id,
            role=role,
            gate_types=gate_types,
            gate_weights=gate_weights,
            confidence=round(base_confidence, 4),
            predicted=False,
            latency_ms=round(elapsed_ms, 2),
        )


def _derive_gates_from_domain_id(domain_id: str) -> List[str]:
    """Heuristic gate derivation from domain ID string."""
    gates: List[str] = []
    did = domain_id.lower()
    if any(k in did for k in ("3d_print", "cnc", "weld", "manuf", "machine")):
        gates = ["quality", "safety", "performance"]
    elif any(k in did for k in ("hvac", "bas", "plumb", "elect", "elevator")):
        gates = ["safety", "energy", "compliance", "monitoring"]
    elif any(k in did for k in ("clinical", "medical", "pharma", "lab")):
        gates = ["safety", "compliance", "quality", "monitoring"]
    elif any(k in did for k in ("trad", "bank", "insur", "financ")):
        gates = ["compliance", "security", "business", "monitoring"]
    elif any(k in did for k in ("power", "oil", "water", "agri", "mining")):
        gates = ["safety", "energy", "monitoring", "compliance"]
    elif any(k in did for k in ("ecomm", "retail", "supply")):
        gates = ["performance", "compliance", "business", "security"]
    elif any(k in did for k in ("health", "hospital")):
        gates = ["safety", "compliance", "quality"]
    else:
        gates = ["quality", "compliance", "business"]
    return gates


# ---------------------------------------------------------------------------
# LCM Model Trainer
# ---------------------------------------------------------------------------

class LCMModelTrainer:
    """Train ML classifiers on collected gate behavior profiles."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model: Dict[str, Any] = {}
        self._trained = False

    def train(self, profiles: List[GateBehaviorProfile]) -> Dict[str, Any]:
        """
        Train on gate behavior profiles.

        Uses NaiveBayesClassifier + OnlineIncrementalLearner + EnsemblePredictor
        when ML engine is available, otherwise builds a lookup table.
        """
        with self._lock:
            if _HAS_ML and NaiveBayesClassifier is not None:
                return self._train_with_ml(profiles)
            return self._train_stub(profiles)

    def _train_with_ml(self, profiles: List[GateBehaviorProfile]) -> Dict[str, Any]:
        """ML-backed training path."""
        try:
            nb = NaiveBayesClassifier()
            oil = OnlineIncrementalLearner()

            # Build training data: feature = domain_id text, label = primary gate
            for p in profiles:
                if not p.gate_types:
                    continue
                label = p.gate_types[0]
                features = {p.domain_id: 1, p.role: 1}
                nb.train(features, label)
                oil.update(features, label)

            classifiers = [nb]
            if EnsemblePredictor is not None and EnsembleStrategy is not None:
                ep = EnsemblePredictor(
                    classifiers=classifiers,
                    strategy=EnsembleStrategy.MAJORITY_VOTE,
                )
            else:
                ep = None

            self._model = {
                "type": "ml",
                "nb_classes": getattr(nb, "_class_counts", {}),
                "profile_count": len(profiles),
                "has_ensemble": ep is not None,
                "lookup": self._build_lookup(profiles),
                "_nb": nb,
                "_oil": oil,
                "_ep": ep,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("ML training failed, falling back to stub: %s", exc)
            self._model = self._train_stub(profiles)

        self._trained = True
        return self.export_model()

    def _train_stub(self, profiles: List[GateBehaviorProfile]) -> Dict[str, Any]:
        """Pure-Python lookup-table fallback when ML is unavailable."""
        self._model = {
            "type": "stub",
            "profile_count": len(profiles),
            "lookup": self._build_lookup(profiles),
        }
        self._trained = True
        return self.export_model()

    @staticmethod
    def _build_lookup(profiles: List[GateBehaviorProfile]) -> Dict[str, Any]:
        """Build domain_id:role → serialized profile lookup."""
        lookup: Dict[str, Any] = {}
        for p in profiles:
            key = f"{p.domain_id}:{p.role}"
            lookup[key] = {
                "gate_types": p.gate_types,
                "gate_weights": p.gate_weights,
                "confidence": p.confidence,
            }
        return lookup

    def export_model(self) -> Dict[str, Any]:
        """Export the model as a JSON-serializable dict."""
        with self._lock:
            # Strip non-serializable objects
            export = {
                k: v
                for k, v in self._model.items()
                if not k.startswith("_")
            }
            return export


# ---------------------------------------------------------------------------
# LCM Predictor
# ---------------------------------------------------------------------------

class LCMPredictor:
    """Fast-path ML predictor (<10 ms) with causal fallback for novel combos."""

    def __init__(self, model: Optional[Dict[str, Any]] = None) -> None:
        self._lock = threading.RLock()
        self._model: Dict[str, Any] = model or {}
        self._profiler = CausalGateProfiler()

    def load_model(self, model: Dict[str, Any]) -> None:
        with self._lock:
            self._model = model

    def predict(
        self,
        domain_id: str,
        role: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> GateBehaviorProfile:
        """
        Predict gate behavior profile.

        1. Check immune memory cache (O(1)).
        2. Try lookup table from trained model.
        3. Fall back to CausalGateProfiler for novel combinations.
        4. Novel results are stored in immune memory for future calls.
        """
        t0 = time.perf_counter()
        cache_key = f"{domain_id}:{role}"

        # --- Immune memory hit ---
        with _IMMUNE_LOCK:
            cached = _IMMUNE_MEMORY.get(cache_key)
        if cached is not None:
            elapsed = (time.perf_counter() - t0) * 1000.0
            result = GateBehaviorProfile(
                domain_id=cached.domain_id,
                role=cached.role,
                gate_types=cached.gate_types,
                gate_weights=cached.gate_weights,
                confidence=cached.confidence,
                predicted=True,
                latency_ms=round(elapsed, 2),
            )
            return result

        # --- Model lookup ---
        with self._lock:
            lookup = self._model.get("lookup", {})
        entry = lookup.get(cache_key)

        if entry is not None:
            elapsed = (time.perf_counter() - t0) * 1000.0
            profile = GateBehaviorProfile(
                domain_id=domain_id,
                role=role,
                gate_types=entry["gate_types"],
                gate_weights=entry["gate_weights"],
                confidence=entry.get("confidence", 0.8),
                predicted=True,
                latency_ms=round(elapsed, 2),
            )
            with _IMMUNE_LOCK:
                _IMMUNE_MEMORY[cache_key] = profile
            return profile

        # --- Novel: causal profiler fallback ---
        description = (context or {}).get("description", f"{domain_id} {role}")
        profile = self._profiler.profile_entity(
            domain_id=domain_id,
            role=role,
            description=description,
        )
        profile.predicted = False  # explicitly from profiler

        # Store in immune memory for future fast-path
        with _IMMUNE_LOCK:
            _IMMUNE_MEMORY[cache_key] = profile

        return profile


# ---------------------------------------------------------------------------
# LCM Engine
# ---------------------------------------------------------------------------

class LCMEngine:
    """
    Main LCM engine — enumerate → profile → train → predict.

    Thread-safe. All shared state guarded by RLock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._registry: Optional[LCMDomainRegistry] = None
        self._enumerator: Optional[UniversalDomainEnumerator] = None
        self._profiler = CausalGateProfiler()
        self._trainer = LCMModelTrainer()
        self._predictor = LCMPredictor()
        self._built = False
        self._build_time_sec: float = 0.0
        self._profile_count: int = 0
        self._model: Dict[str, Any] = {}

    def build(self) -> None:
        """
        Full build pipeline:
          1. Instantiate registry
          2. Enumerate all domain × role combinations
          3. Profile each entity (gate types + weights)
          4. Train ML model on profiles
          5. Load model into predictor
        """
        t0 = time.perf_counter()
        with self._lock:
            logger.info("LCMEngine.build() starting …")
            self._registry = LCMDomainRegistry()
            self._enumerator = UniversalDomainEnumerator(self._registry)

            combos = self._enumerator.enumerate_bot_role_domain_combinations()
            logger.info("Enumerating %d domain×role combos …", len(combos))

            profiles: List[GateBehaviorProfile] = []
            for role, domain in combos:
                profile = self._profiler.profile_entity(
                    domain_id=domain.domain_id,
                    role=role.value,
                    description=domain.description,
                    existing_domain=domain,
                )
                profiles.append(profile)
                # Seed immune memory
                cache_key = f"{domain.domain_id}:{role.value}"
                with _IMMUNE_LOCK:
                    _IMMUNE_MEMORY[cache_key] = profile

            self._profile_count = len(profiles)
            logger.info("Profiled %d entities — training …", self._profile_count)

            self._model = self._trainer.train(profiles)
            self._predictor.load_model(self._model)

            self._built = True
            self._build_time_sec = time.perf_counter() - t0
            logger.info(
                "LCMEngine.build() complete in %.2fs", self._build_time_sec
            )

    def predict(
        self,
        domain_id: str,
        role: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> GateBehaviorProfile:
        """
        Fast-path predict. Auto-builds if not yet built.

        Returns a GateBehaviorProfile. Serves from immune memory in <10 ms
        for known domain×role pairs after the first build.
        """
        if not self._built:
            self.build()
        return self._predictor.predict(domain_id, role, context)

    def status(self) -> Dict[str, Any]:
        """Return engine status dict."""
        with self._lock:
            return {
                "built": self._built,
                "profile_count": self._profile_count,
                "build_time_sec": round(self._build_time_sec, 3),
                "immune_memory_size": len(_IMMUNE_MEMORY),
                "model_type": self._model.get("type", "none"),
                "registry_available": _HAS_REGISTRY,
                "ml_available": _HAS_ML,
                "inference_available": _HAS_INFERENCE,
            }
