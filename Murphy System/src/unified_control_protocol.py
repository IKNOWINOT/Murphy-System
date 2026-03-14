"""
Unified Control Protocol — Pipeline Orchestrator for the Murphy System

Design Label: UCP-001 — Unified Control Protocol
Owner: Core Platform
Dependencies:
  - resolution_scoring (ResolutionDetectionEngine)
  - information_density (InformationDensityEngine)
  - structural_coherence (StructuralCoherenceEngine)
  - information_quality (InformationQualityEngine)
  - concept_translation (ConceptTranslationEngine)
  - concept_graph_engine (ConceptGraphEngine)
  - simulation_engine (StrategicSimulationEngine)
  - governance_kernel (GovernanceKernel, DepartmentScope, EnforcementAction)
  - architecture_evolution (ArchitectureEvolutionEngine)
  - mss_controls (MSSController)
  - thread_safe_operations (capped_append)

Purpose:
  Orchestrates the full Murphy System pipeline, executing engines in
  fixed order (RDE → IDI → SCS → CQI → CTE → CGE → SEE → SSE → PGE → MSS),
  with deterministic caching, thread-safe operation, and full action logging.
  Provides rollback to earlier pipeline states and system health monitoring.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import collections
import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

# ---------------------------------------------------------------------------
# Engine imports — wrapped for graceful degradation
# ---------------------------------------------------------------------------

try:
    from resolution_scoring import ResolutionDetectionEngine
except ImportError:
    ResolutionDetectionEngine = None  # type: ignore[assignment,misc]

try:
    from information_density import InformationDensityEngine
except ImportError:
    InformationDensityEngine = None  # type: ignore[assignment,misc]

try:
    from structural_coherence import StructuralCoherenceEngine
except ImportError:
    StructuralCoherenceEngine = None  # type: ignore[assignment,misc]

try:
    from information_quality import InformationQualityEngine
except ImportError:
    InformationQualityEngine = None  # type: ignore[assignment,misc]

try:
    from concept_translation import ConceptTranslationEngine
except ImportError:
    ConceptTranslationEngine = None  # type: ignore[assignment,misc]

try:
    from concept_graph_engine import ConceptGraphEngine
except ImportError:
    ConceptGraphEngine = None  # type: ignore[assignment,misc]

try:
    from simulation_engine import StrategicSimulationEngine
except ImportError:
    StrategicSimulationEngine = None  # type: ignore[assignment,misc]

try:
    from governance_kernel import (
        DepartmentScope,
        EnforcementAction,
        GovernanceKernel,
    )
except ImportError:
    GovernanceKernel = None  # type: ignore[assignment,misc]
    DepartmentScope = None  # type: ignore[assignment,misc]
    EnforcementAction = None  # type: ignore[assignment,misc]

try:
    from architecture_evolution import ArchitectureEvolutionEngine
except ImportError:
    ArchitectureEvolutionEngine = None  # type: ignore[assignment,misc]

try:
    from mss_controls import MSSController
except ImportError:
    MSSController = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Module logger
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_OPERATORS = frozenset({"magnify", "simplify", "solidify"})

PIPELINE_STATES = (
    "received",
    "analyzed",
    "translated",
    "simulated",
    "governed",
    "executed",
    "archived",
)

ENGINE_PRIORITY: Dict[str, int] = {
    "PGE": 10,
    "MSS": 9,
    "SSE": 8,
    "SEE": 7,
    "CGE": 6,
    "CTE": 5,
    "CQI": 4,
    "SCS": 3,
    "IDI": 2,
    "RDE": 1,
}

_MAX_ACTION_LOG = 10_000
_MAX_CACHE = 4096


# ---------------------------------------------------------------------------
# Immutable result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionResult:
    """Immutable record of a single pipeline execution."""

    action_id: str
    input_text: str
    operator: str
    resolution_score: float
    density_index: float
    coherence_score: float
    composite_quality: float
    governance_status: str
    state: str
    timestamp: str
    input_hash: str


# ---------------------------------------------------------------------------
# Unified Control Protocol
# ---------------------------------------------------------------------------

class UnifiedControlProtocol:
    """Pipeline orchestrator executing engines in fixed order.

    Execution order: RDE → IDI → SCS → CQI → CTE → CGE → SEE → SSE → PGE → MSS

    All operations are thread-safe and deterministic.  Identical inputs
    (text + operator) produce identical outputs via SHA-256 cache lookup.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: collections.OrderedDict[str, ActionResult] = (
            collections.OrderedDict()
        )
        self._action_log: List[Dict[str, Any]] = []
        self._checkpoints: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # --- Standalone engines ---
        self._rde = self._safe_init("RDE", ResolutionDetectionEngine)
        self._ide = self._safe_init("IDI", InformationDensityEngine)
        self._sce = self._safe_init("SCS", StructuralCoherenceEngine)

        # CQI composes RDE + IDI + SCS
        self._iqe: Optional[Any] = None
        if InformationQualityEngine is not None and all(
            e is not None for e in (self._rde, self._ide, self._sce)
        ):
            try:
                self._iqe = InformationQualityEngine(
                    self._rde, self._ide, self._sce,
                )
            except Exception as exc:
                logger.warning("CQI engine initialization failed: %s", exc, exc_info=True)

        self._cte = self._safe_init("CTE", ConceptTranslationEngine)
        self._cge = self._safe_init("CGE", ConceptGraphEngine)
        self._see = self._safe_init("SEE", ArchitectureEvolutionEngine)
        self._sse = self._safe_init("SSE", StrategicSimulationEngine)
        self._gov = self._safe_init("PGE", GovernanceKernel)

        # MSS composes IQE + CTE + SSE (+ optional governance)
        self._mss: Optional[Any] = None
        if MSSController is not None and all(
            e is not None for e in (self._iqe, self._cte, self._sse)
        ):
            try:
                self._mss = MSSController(
                    iqe=self._iqe,
                    cte=self._cte,
                    sim=self._sse,
                    gov=self._gov,
                )
            except Exception as exc:
                logger.warning("MSS engine initialization failed: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_init(label: str, cls: Optional[type]) -> Optional[Any]:
        """Instantiate *cls* with no arguments, returning *None* on failure."""
        if cls is None:
            logger.warning("%s engine class not available", label)
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning(
                "%s engine initialization failed: %s", label, exc, exc_info=True,
            )
            return None

    @staticmethod
    def _input_hash(text: str) -> str:
        """SHA-256 hex digest of raw input text."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_key(text: str, operator: str) -> str:
        """Deterministic cache key combining text and operator."""
        return hashlib.sha256(
            f"{text}:{operator}".encode("utf-8"),
        ).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_step(
        self,
        action_id: str,
        step: str,
        state: str,
        detail: Optional[str] = None,
    ) -> None:
        """Append a timestamped entry to the action log (bounded)."""
        entry: Dict[str, Any] = {
            "action_id": action_id,
            "step": step,
            "state": state,
            "timestamp": self._now_iso(),
        }
        if detail is not None:
            entry["detail"] = detail
        capped_append(self._action_log, entry, _MAX_ACTION_LOG)

    def _save_checkpoint(
        self,
        action_id: str,
        state: str,
        data: Dict[str, Any],
    ) -> None:
        """Store a state checkpoint for potential rollback."""
        self._checkpoints.setdefault(action_id, {})[state] = {
            **data,
            "timestamp": self._now_iso(),
        }

    def _evict_cache(self) -> None:
        """Trim cache to *_MAX_CACHE* entries (LRU eviction)."""
        while len(self._cache) > _MAX_CACHE:
            self._cache.popitem(last=False)

    @staticmethod
    def _normalize_governance(raw: str) -> str:
        """Map engine enforcement values to ActionResult governance_status."""
        if raw in ("allow", "deny", "escalate"):
            return raw
        return "allow"

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    def execute(
        self,
        text: str,
        operator: str = "magnify",
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        """Run the full UCP pipeline and return an immutable *ActionResult*.

        Raises *ValueError* for an invalid operator.
        """
        if operator not in VALID_OPERATORS:
            raise ValueError(
                f"Invalid operator '{operator}'; "
                f"must be one of {sorted(VALID_OPERATORS)}"
            )

        with self._lock:
            # --- Cache hit → return immediately ---
            ck = self._cache_key(text, operator)
            if ck in self._cache:
                self._cache.move_to_end(ck)
                return self._cache[ck]

            action_id = str(uuid.uuid5(uuid.NAMESPACE_URL, ck))
            ih = self._input_hash(text)
            state = "received"

            resolution_score = 0.0
            density_index = 0.0
            coherence_score = 0.0
            composite_quality = 0.0
            governance_status = "allow"

            self._log_step(action_id, "init", state)
            self._save_checkpoint(action_id, state, {
                "input_text": text,
                "operator": operator,
                "input_hash": ih,
            })

            # ---- RDE (Resolution Detection) ----
            rde_result = None
            if self._rde is not None:
                rde_result = self._rde.score(text, context)
                resolution_score = float(rde_result.rs)
                self._log_step(
                    action_id, "RDE", state, f"rs={resolution_score:.4f}",
                )

            # ---- IDI (Information Density) ----
            if self._ide is not None:
                density_result = self._ide.score(text, rde_result)
                density_index = float(density_result.idi)
                self._log_step(
                    action_id, "IDI", state, f"idi={density_index:.4f}",
                )

            # ---- SCS (Structural Coherence) ----
            if self._sce is not None:
                coherence_result = self._sce.score(text, context)
                coherence_score = float(coherence_result.scs)
                self._log_step(
                    action_id, "SCS", state, f"scs={coherence_score:.4f}",
                )

            # ---- CQI (Composite Quality Index) ----
            if self._iqe is not None:
                quality_result = self._iqe.assess(text, context)
                composite_quality = float(quality_result.cqi)
                self._log_step(
                    action_id, "CQI", state, f"cqi={composite_quality:.4f}",
                )

            state = "analyzed"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {
                "resolution_score": resolution_score,
                "density_index": density_index,
                "coherence_score": coherence_score,
                "composite_quality": composite_quality,
            })

            # ---- CTE (Concept Translation) ----
            translation = None
            if self._cte is not None:
                translation = self._cte.translate(text, context)
                self._log_step(action_id, "CTE", state, "translated")

            # ---- CGE (Concept Graph) ----
            if self._cge is not None and translation is not None:
                for concept in getattr(translation, "extracted_concepts", []):
                    cid = (
                        concept.get("action")
                        or concept.get("actor", "unknown")
                    )
                    try:
                        self._cge.add_node(cid, "concept", concept)
                    except Exception as exc:
                        logger.debug("CGE add_node skipped: %s", exc)
                self._log_step(action_id, "CGE", state, "graph_updated")

            state = "translated"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {
                "has_translation": translation is not None,
            })

            # ---- SEE (Architecture Evolution) ----
            evolution_score = 0.0
            if self._see is not None:
                try:
                    indicators = self._see.analyze()
                    evolution_score = float(indicators.es)
                    self._log_step(
                        action_id, "SEE", state, f"es={evolution_score:.4f}",
                    )
                except Exception as exc:
                    self._log_step(action_id, "SEE", state, f"skipped: {exc}")

            # ---- SSE (Strategic Simulation) ----
            simulation_risk = 0.0
            if self._sse is not None:
                try:
                    sim_result = self._sse.simulate_module_creation({
                        "name": f"action_{action_id[:8]}",
                        "dependencies": [],
                        "compliance_domains": [],
                        "estimated_complexity": "medium",
                    })
                    simulation_risk = float(sim_result.overall_score)
                    self._log_step(
                        action_id, "SSE", state,
                        f"risk={simulation_risk:.4f}",
                    )
                except Exception as exc:
                    self._log_step(action_id, "SSE", state, f"skipped: {exc}")

            state = "simulated"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {
                "evolution_score": evolution_score,
                "simulation_risk": simulation_risk,
            })

            # ---- PGE (Governance) ----
            if self._gov is not None:
                try:
                    enforcement = self._gov.enforce(
                        caller_id=action_id,
                        department_id="core",
                        tool_name=operator,
                        estimated_cost=0.0,
                        context=context or {},
                    )
                    governance_status = self._normalize_governance(
                        str(enforcement.action.value),
                    )
                    self._log_step(
                        action_id, "PGE", state,
                        f"status={governance_status}",
                    )
                except Exception as exc:
                    governance_status = "allow"
                    self._log_step(action_id, "PGE", state, f"default_allow: {exc}")

            state = "governed"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {
                "governance_status": governance_status,
            })

            # Governance denial halts the pipeline
            if governance_status == "deny":
                result = ActionResult(
                    action_id=action_id,
                    input_text=text,
                    operator=operator,
                    resolution_score=resolution_score,
                    density_index=density_index,
                    coherence_score=coherence_score,
                    composite_quality=composite_quality,
                    governance_status=governance_status,
                    state=state,
                    timestamp=self._now_iso(),
                    input_hash=ih,
                )
                self._cache[ck] = result
                self._evict_cache()
                return result

            # ---- MSS (Magnify / Simplify / Solidify) ----
            if self._mss is not None:
                try:
                    mss_method = getattr(self._mss, operator)
                    mss_method(text, context)
                    self._log_step(
                        action_id, "MSS", state, f"operator={operator}",
                    )
                except Exception as exc:
                    self._log_step(action_id, "MSS", state, f"skipped: {exc}")

            state = "executed"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {"operator": operator})

            # Final archival
            state = "archived"
            self._log_step(action_id, "state_transition", state)
            self._save_checkpoint(action_id, state, {})

            result = ActionResult(
                action_id=action_id,
                input_text=text,
                operator=operator,
                resolution_score=resolution_score,
                density_index=density_index,
                coherence_score=coherence_score,
                composite_quality=composite_quality,
                governance_status=governance_status,
                state=state,
                timestamp=self._now_iso(),
                input_hash=ih,
            )

            self._cache[ck] = result
            self._evict_cache()
            return result

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, action_id: str, target_state: str) -> ActionResult:
        """Revert an action to *target_state* by replaying from checkpoint.

        Raises *ValueError* for invalid states and *KeyError* when no
        checkpoint data exists for the requested action or state.
        """
        if target_state not in PIPELINE_STATES:
            raise ValueError(
                f"Invalid target state '{target_state}'; "
                f"must be one of {list(PIPELINE_STATES)}"
            )

        with self._lock:
            checkpoints = self._checkpoints.get(action_id)
            if not checkpoints:
                raise KeyError(f"No checkpoints for action '{action_id}'")
            if target_state not in checkpoints:
                raise KeyError(
                    f"No checkpoint at state '{target_state}' "
                    f"for action '{action_id}'"
                )

            received = checkpoints.get("received", {})
            analyzed = checkpoints.get("analyzed", {})
            governed = checkpoints.get("governed", {})

            target_idx = PIPELINE_STATES.index(target_state)
            analyzed_idx = PIPELINE_STATES.index("analyzed")
            governed_idx = PIPELINE_STATES.index("governed")

            result = ActionResult(
                action_id=action_id,
                input_text=received.get("input_text", ""),
                operator=received.get("operator", "magnify"),
                resolution_score=(
                    analyzed.get("resolution_score", 0.0)
                    if target_idx >= analyzed_idx else 0.0
                ),
                density_index=(
                    analyzed.get("density_index", 0.0)
                    if target_idx >= analyzed_idx else 0.0
                ),
                coherence_score=(
                    analyzed.get("coherence_score", 0.0)
                    if target_idx >= analyzed_idx else 0.0
                ),
                composite_quality=(
                    analyzed.get("composite_quality", 0.0)
                    if target_idx >= analyzed_idx else 0.0
                ),
                governance_status=(
                    governed.get("governance_status", "allow")
                    if target_idx >= governed_idx else "allow"
                ),
                state=target_state,
                timestamp=self._now_iso(),
                input_hash=received.get("input_hash", ""),
            )

            self._log_step(
                action_id, "rollback", target_state,
                f"rolled_back_to={target_state}",
            )
            return result

    # ------------------------------------------------------------------
    # System health
    # ------------------------------------------------------------------

    def get_system_health(self) -> Dict[str, float]:
        """Return current system health metrics from live engines."""
        with self._lock:
            health: Dict[str, float] = {
                "architecture_health": 0.0,
                "governance_compliance": 0.0,
                "information_quality": 0.0,
                "evolution_score": 0.0,
                "simulation_risk": 0.0,
            }

            # Architecture health + evolution score from SEE
            if self._see is not None:
                try:
                    indicators = self._see.analyze()
                    health["evolution_score"] = float(indicators.es)
                    health["architecture_health"] = max(
                        0.0,
                        1.0 - float(indicators.complexity_growth) / 6.0,
                    )
                except Exception as exc:
                    logger.debug("Architecture health probe failed: %s", exc)

            # Governance compliance from PGE
            if self._gov is not None:
                try:
                    status = self._gov.get_status()
                    total = status.get("total_departments", 0)
                    health["governance_compliance"] = (
                        1.0 if total > 0 else 0.0
                    )
                except Exception as exc:
                    logger.debug("Governance compliance probe failed: %s", exc)

            # Average CQI across cached actions
            recent_cqi = [
                r.composite_quality
                for r in self._cache.values()
                if r.composite_quality > 0.0
            ]
            if recent_cqi:
                health["information_quality"] = (
                    sum(recent_cqi) / len(recent_cqi)
                )

            # Simulation risk from SSE
            if self._sse is not None:
                try:
                    sim = self._sse.simulate_module_creation({
                        "name": "health_probe",
                        "dependencies": [],
                        "compliance_domains": [],
                        "estimated_complexity": "low",
                    })
                    health["simulation_risk"] = float(sim.overall_score)
                except Exception as exc:
                    logger.debug("Simulation risk probe failed: %s", exc)

            return health

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def action_log(self) -> List[Dict[str, Any]]:
        """Return a shallow copy of the action log."""
        with self._lock:
            return list(self._action_log)

    @property
    def engine_priority(self) -> Dict[str, int]:
        """Return the engine priority hierarchy (read-only copy)."""
        return dict(ENGINE_PRIORITY)
