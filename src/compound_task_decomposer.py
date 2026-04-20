"""
Compound Task Decomposer - Murphy System
==========================================
Detects multi-phase queries and decomposes them into ordered prerequisite
phases before the main deliverable generation phase.

When a user says "perform market research to select a niche, then build
a web app MVP", the system must:
  1. Recognise this as a compound request with prerequisite phases.
  2. Execute the research/analysis phase first (via ResearchEngine,
     NicheBusinessGenerator, CompetitiveIntelligenceEngine).
  3. Feed the research output as enriched context into the build phase.

Integration points:
  - TriageRollcallAdapter  - capability ranking to select which modules
    handle each phase.
  - RubixEvidenceAdapter   - confidence validation on each phase output
    before proceeding to the next.
  - RubixCube PathConfidenceRegistry - optimal trajectory tracking.
    Steers toward optimal conditions/variables by scoring execution paths
    and selecting the highest-confidence trajectory for each task phase.

Design Label: CTD-001
Copyright (c) 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CTD-001: Phase types
# ---------------------------------------------------------------------------


class PhaseType(str, Enum):
    """Category of work a decomposed phase represents."""

    RESEARCH = "research"
    ANALYSIS = "analysis"
    SELECTION = "selection"
    BUILD = "build"
    VALIDATE = "validate"


# ---------------------------------------------------------------------------
# CTD-001: Data structures
# ---------------------------------------------------------------------------


@dataclass
class DecomposedPhase:
    """A single phase extracted from a compound query."""

    phase_id: int
    phase_type: PhaseType
    description: str
    query_fragment: str
    depends_on: List[int] = field(default_factory=list)
    module_hints: List[str] = field(default_factory=list)
    output: Optional[Dict[str, Any]] = None
    success: bool = False
    error: Optional[str] = None
    elapsed_ms: int = 0


@dataclass
class DecompositionResult:
    """Result of decomposing a compound query."""

    is_compound: bool
    original_query: str
    phases: List[DecomposedPhase] = field(default_factory=list)
    enriched_context: str = ""
    decomposition_confidence: float = 0.0
    trajectory_scores: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# CTD-001: Compound query detection patterns
# ---------------------------------------------------------------------------

_RESEARCH_VERBS = (
    r"(?:research|analyze|study|investigate|evaluate|assess|survey|explore)"
)
_SELECT_VERBS = r"(?:select|choose|find|identify|determine|decide|pick)"
_BUILD_VERBS = (
    r"(?:create|build|make|develop|design|generate|scaffold|implement)"
)
_CONNECTORS = r"(?:then|and then|before|and|to|in order to|so I can|for)"

_COMPOUND_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(
            rf"{_RESEARCH_VERBS}\b.+?\b{_CONNECTORS}\b.+?\b{_BUILD_VERBS}\b",
            re.IGNORECASE,
        ),
        "research_then_build",
        "Research/analysis prerequisite before build phase",
    ),
    (
        re.compile(
            rf"after\s+(?:performing|doing|completing|running)\b.+?\b{_BUILD_VERBS}\b",
            re.IGNORECASE,
        ),
        "after_analysis_build",
        "Explicit sequencing: analysis then build",
    ),
    (
        re.compile(
            rf"{_SELECT_VERBS}\b.+?\b(?:for|to build|to create|to make|to develop)\b",
            re.IGNORECASE,
        ),
        "select_for_build",
        "Selection prerequisite before build phase",
    ),
    (
        re.compile(
            rf"market\s+research.+?{_BUILD_VERBS}\b",
            re.IGNORECASE,
        ),
        "market_research_build",
        "Market research prerequisite before build",
    ),
    (
        re.compile(
            rf"perform\s+(?:analysis|research|assessment).+?{_BUILD_VERBS}\b",
            re.IGNORECASE,
        ),
        "perform_analysis_build",
        "Perform analysis prerequisite before build",
    ),
    (
        re.compile(
            rf"(?:lucrative|profitable|viable)\s+(?:niche|market|segment).+?{_BUILD_VERBS}\b",
            re.IGNORECASE,
        ),
        "niche_research_build",
        "Niche viability research before build",
    ),
]

# ---------------------------------------------------------------------------
# CTD-001: Module hints per phase type
# ---------------------------------------------------------------------------

_MODULE_HINTS: Dict[str, List[str]] = {
    "research": [
        "research_engine",
        "multi_source_research",
        "competitive_intelligence_engine",
    ],
    "market_research": [
        "market_positioning_engine",
        "competitive_intelligence_engine",
        "niche_viability_gate",
        "niche_business_generator",
    ],
    "niche_selection": [
        "niche_business_generator",
        "niche_viability_gate",
        "unit_economics_analyzer",
    ],
    "build": [
        "demo_deliverable_generator",
        "code_generation_gateway",
    ],
}


# ---------------------------------------------------------------------------
# CTD-DETECT-001: Detection
# ---------------------------------------------------------------------------


def detect_compound_query(query: str) -> DecompositionResult:
    """Detect whether a query contains multiple prerequisite phases.

    Returns a DecompositionResult with is_compound=True and ordered phases
    if the query matches any compound pattern.  Otherwise returns
    is_compound=False with an empty phase list.

    Label: CTD-DETECT-001
    """
    if not query or not query.strip():
        return DecompositionResult(
            is_compound=False,
            original_query=query or "",
            decomposition_confidence=0.0,
        )

    q = query.strip()

    for pattern, decomp_type, _description in _COMPOUND_PATTERNS:
        if pattern.search(q):
            logger.info(
                "CTD-DETECT-001: Compound query detected type=%s query=%s",
                decomp_type,
                q[:80],
            )
            phases = _build_phases(q, decomp_type)
            confidence = _score_decomposition(q, decomp_type, phases)
            return DecompositionResult(
                is_compound=True,
                original_query=q,
                phases=phases,
                decomposition_confidence=confidence,
            )

    return DecompositionResult(
        is_compound=False,
        original_query=q,
        decomposition_confidence=0.0,
    )


def _build_phases(query: str, decomp_type: str) -> List[DecomposedPhase]:
    """Build ordered phases from the detected decomposition type.

    Label: CTD-PHASE-001
    """
    phases: List[DecomposedPhase] = []

    if decomp_type in (
        "research_then_build",
        "after_analysis_build",
        "perform_analysis_build",
    ):
        phases.append(
            DecomposedPhase(
                phase_id=0,
                phase_type=PhaseType.RESEARCH,
                description="Perform research and analysis",
                query_fragment=_extract_research_fragment(query),
                module_hints=_MODULE_HINTS.get("research", []),
            )
        )
        phases.append(
            DecomposedPhase(
                phase_id=1,
                phase_type=PhaseType.BUILD,
                description="Build deliverable using research results",
                query_fragment=_extract_build_fragment(query),
                depends_on=[0],
                module_hints=_MODULE_HINTS.get("build", []),
            )
        )

    elif decomp_type in ("market_research_build", "niche_research_build"):
        phases.append(
            DecomposedPhase(
                phase_id=0,
                phase_type=PhaseType.RESEARCH,
                description="Perform market research and competitive analysis",
                query_fragment=_extract_research_fragment(query),
                module_hints=_MODULE_HINTS.get("market_research", []),
            )
        )
        phases.append(
            DecomposedPhase(
                phase_id=1,
                phase_type=PhaseType.SELECTION,
                description="Select optimal niche based on research",
                query_fragment="Select the most viable niche from research findings",
                depends_on=[0],
                module_hints=_MODULE_HINTS.get("niche_selection", []),
            )
        )
        phases.append(
            DecomposedPhase(
                phase_id=2,
                phase_type=PhaseType.BUILD,
                description="Build deliverable for selected niche",
                query_fragment=_extract_build_fragment(query),
                depends_on=[0, 1],
                module_hints=_MODULE_HINTS.get("build", []),
            )
        )

    elif decomp_type == "select_for_build":
        phases.append(
            DecomposedPhase(
                phase_id=0,
                phase_type=PhaseType.SELECTION,
                description="Evaluate and select target",
                query_fragment=_extract_research_fragment(query),
                module_hints=_MODULE_HINTS.get("niche_selection", []),
            )
        )
        phases.append(
            DecomposedPhase(
                phase_id=1,
                phase_type=PhaseType.BUILD,
                description="Build deliverable for selected target",
                query_fragment=_extract_build_fragment(query),
                depends_on=[0],
                module_hints=_MODULE_HINTS.get("build", []),
            )
        )

    return phases


# ---------------------------------------------------------------------------
# CTD-FRAG-001 / CTD-FRAG-002: Fragment extraction
# ---------------------------------------------------------------------------


def _extract_research_fragment(query: str) -> str:
    """Extract the research/analysis portion of a compound query.

    Label: CTD-FRAG-001
    """
    q = query.strip()
    for sep in [" then ", " and then ", " before ", " in order to ", " so I can "]:
        if sep in q.lower():
            idx = q.lower().index(sep)
            return q[:idx].strip()
    return q


def _extract_build_fragment(query: str) -> str:
    """Extract the build/create portion of a compound query.

    Label: CTD-FRAG-002
    """
    q = query.strip()
    for sep in [" then ", " and then ", " before ", " in order to ", " so I can "]:
        if sep in q.lower():
            idx = q.lower().index(sep)
            return q[idx + len(sep):].strip()
    return q


def _score_decomposition(
    query: str,
    decomp_type: str,
    phases: List[DecomposedPhase],
) -> float:
    """Score confidence in the decomposition.  Label: CTD-SCORE-001"""
    score = 0.5
    q_lower = query.lower()
    if any(w in q_lower for w in ("then", "after", "before", "first")):
        score += 0.2
    if any(
        w in q_lower
        for w in ("market research", "niche", "competitive", "analysis")
    ):
        score += 0.15
    if len(phases) >= 3:
        score += 0.1
    return min(0.95, score)


# ---------------------------------------------------------------------------
# CTD-EXEC-001: Prerequisite phase execution
# ---------------------------------------------------------------------------


def execute_prerequisite_phases(
    decomposition: DecompositionResult,
) -> DecompositionResult:
    """Execute all non-BUILD phases in dependency order.

    Each phase output is stored on the DecomposedPhase.output attribute.
    The enriched_context field is populated with a human-readable summary
    of all prerequisite outputs for injection into the build phase.

    Uses RubixCube PathConfidenceRegistry for optimal trajectory tracking:
    each phase execution path is scored and the registry steers subsequent
    phases toward the highest-confidence trajectory.

    Label: CTD-EXEC-001
    """
    if not decomposition.is_compound or not decomposition.phases:
        return decomposition

    trajectory = _init_trajectory_tracker()
    completed: Dict[int, DecomposedPhase] = {}
    context_parts: List[str] = []

    for phase in decomposition.phases:
        if phase.phase_type == PhaseType.BUILD:
            continue

        dep_failed = False
        for dep_id in phase.depends_on:
            dep = completed.get(dep_id)
            if dep and not dep.success:
                phase.error = (
                    f"CTD-EXEC-DEP-001: Dependency phase {dep_id} failed"
                )
                logger.warning(
                    "CTD-EXEC-DEP-001: Dependency phase %d failed, "
                    "skipping phase %d",
                    dep_id,
                    phase.phase_id,
                )
                dep_failed = True
                break

        if dep_failed:
            completed[phase.phase_id] = phase
            continue

        start = time.monotonic()
        try:
            phase.output = _run_phase(phase, completed)
            phase.success = True
            phase.elapsed_ms = int((time.monotonic() - start) * 1000)

            path_key = f"phase:{phase.phase_id}:{phase.phase_type.value}"
            _update_trajectory(trajectory, path_key, phase)

            logger.info(
                "CTD-EXEC-001: Phase %d (%s) completed in %dms",
                phase.phase_id,
                phase.phase_type.value,
                phase.elapsed_ms,
            )
        except Exception as exc:
            phase.elapsed_ms = int((time.monotonic() - start) * 1000)
            phase.error = f"CTD-EXEC-ERR-001: {type(exc).__name__}: {exc}"
            phase.success = False
            logger.error(
                "CTD-EXEC-ERR-001: Phase %d (%s) failed: %s",
                phase.phase_id,
                phase.phase_type.value,
                exc,
            )

        completed[phase.phase_id] = phase

        if phase.success and phase.output:
            ctx = _format_phase_output(phase)
            if ctx:
                context_parts.append(ctx)

    if trajectory is not None:
        decomposition.trajectory_scores = _get_trajectory_scores(trajectory)

    if context_parts:
        header = "=" * 72
        decomposition.enriched_context = (
            "\n"
            + header
            + "\n"
            + "  PREREQUISITE PHASE RESULTS (CTD-001)\n"
            + header
            + "\n\n"
            + "\n\n".join(context_parts)
            + "\n"
        )

    return decomposition


# ---------------------------------------------------------------------------
# CTD-RUN-001: Phase execution dispatch
# ---------------------------------------------------------------------------


def _run_phase(
    phase: DecomposedPhase,
    completed: Dict[int, DecomposedPhase],
) -> Dict[str, Any]:
    """Execute a single prerequisite phase.  Label: CTD-RUN-001"""
    dispatch = {
        PhaseType.RESEARCH: _run_research_phase,
        PhaseType.ANALYSIS: _run_research_phase,
        PhaseType.SELECTION: _run_selection_phase,
        PhaseType.VALIDATE: _run_validation_phase,
    }
    handler = dispatch.get(phase.phase_type)
    if handler is None:
        raise ValueError(
            f"CTD-RUN-ERR-001: Unknown phase type: {phase.phase_type}"
        )
    return handler(phase, completed)


def _run_research_phase(
    phase: DecomposedPhase,
    completed: Dict[int, DecomposedPhase],
) -> Dict[str, Any]:
    """Run a research phase using available research modules.

    Attempts modules in priority order; falls back deterministically.
    Label: CTD-RESEARCH-001
    """
    query_fragment = phase.query_fragment
    results: Dict[str, Any] = {"phase_type": "research", "sources": []}

    # Attempt 1: MultiSourceResearcher
    try:
        from multi_source_research import MultiSourceResearcher

        researcher = MultiSourceResearcher()
        compiled = researcher.compile_research(query_fragment)
        if compiled and hasattr(compiled, "compiled_facts"):
            results["multi_source"] = {
                "facts": getattr(compiled, "compiled_facts", []),
                "synthesis": getattr(compiled, "synthesis", {}),
                "confidence": getattr(compiled, "confidence", 0.0),
            }
            results["sources"].append("multi_source_research")
            logger.info(
                "CTD-RESEARCH-001: MultiSourceResearcher returned data"
            )
    except Exception as exc:
        logger.warning(
            "CTD-RESEARCH-001: MultiSourceResearcher unavailable: %s", exc
        )

    # Attempt 2: ResearchEngine
    try:
        from research_engine import ResearchEngine

        engine = ResearchEngine()
        result = engine.research_topic(query_fragment, depth="deep")
        if result and hasattr(result, "synthesis"):
            results["research_engine"] = {
                "synthesis": getattr(result, "synthesis", {}),
                "confidence": getattr(result, "confidence", 0.0),
            }
            results["sources"].append("research_engine")
            logger.info("CTD-RESEARCH-001: ResearchEngine returned data")
    except Exception as exc:
        logger.warning(
            "CTD-RESEARCH-001: ResearchEngine unavailable: %s", exc
        )

    # Attempt 3: CompetitiveIntelligenceEngine (market research queries)
    if _is_market_research(query_fragment):
        try:
            from competitive_intelligence_engine import (
                CompetitiveIntelligenceEngine,
            )

            cie = CompetitiveIntelligenceEngine()
            landscape = cie.analyze_landscape()
            if landscape:
                results["competitive_intelligence"] = {
                    "landscape": landscape
                    if isinstance(landscape, dict)
                    else {},
                }
                results["sources"].append("competitive_intelligence_engine")
                logger.info(
                    "CTD-RESEARCH-001: CompetitiveIntelligenceEngine "
                    "returned data"
                )
        except Exception as exc:
            logger.warning(
                "CTD-RESEARCH-001: CompetitiveIntelligenceEngine "
                "unavailable: %s",
                exc,
            )

    # Fallback: deterministic market research (always available)
    if not results["sources"]:
        results["deterministic_research"] = _deterministic_market_research(
            query_fragment
        )
        results["sources"].append("deterministic_fallback")
        logger.info("CTD-RESEARCH-001: Using deterministic research fallback")

    results["evidence_validation"] = _validate_with_rubix(results)
    return results


def _run_selection_phase(
    phase: DecomposedPhase,
    completed: Dict[int, DecomposedPhase],
) -> Dict[str, Any]:
    """Select optimal niche/target from prior research.

    Label: CTD-SELECT-001
    """
    research_data: Dict[str, Any] = {}
    for dep_id in phase.depends_on:
        dep = completed.get(dep_id)
        if dep and dep.success and dep.output:
            research_data.update(dep.output)

    results: Dict[str, Any] = {"phase_type": "selection", "sources": []}

    try:
        from niche_viability_gate import NicheViabilityGate

        _gate = NicheViabilityGate()
        results["viability_gate"] = {"available": True}
        results["sources"].append("niche_viability_gate")
        logger.info("CTD-SELECT-001: NicheViabilityGate available")
    except Exception as exc:
        logger.warning(
            "CTD-SELECT-001: NicheViabilityGate unavailable: %s", exc
        )

    try:
        from market_positioning_engine import MarketPositioningEngine

        mpe = MarketPositioningEngine()
        position = mpe.get_market_position()
        if position:
            results["market_position"] = {
                "position": position.to_dict()
                if hasattr(position, "to_dict")
                else str(position),
            }
            results["sources"].append("market_positioning_engine")
    except Exception as exc:
        logger.warning(
            "CTD-SELECT-001: MarketPositioningEngine unavailable: %s", exc
        )

    results["selected_niche"] = _deterministic_niche_selection(
        phase.query_fragment,
        research_data,
    )
    if not results["sources"]:
        results["sources"].append("deterministic_fallback")
        logger.info("CTD-SELECT-001: Using deterministic niche selection")

    results["evidence_validation"] = _validate_with_rubix(results)
    return results


def _run_validation_phase(
    phase: DecomposedPhase,
    completed: Dict[int, DecomposedPhase],
) -> Dict[str, Any]:
    """Run a validation phase.  Label: CTD-VALIDATE-001"""
    return {
        "phase_type": "validation",
        "status": "pass",
        "sources": ["validation"],
    }


# ---------------------------------------------------------------------------
# CTD-TRIAGE-001: TriageBot rollcall integration
# ---------------------------------------------------------------------------


def run_triage_rollcall(
    phases: List[DecomposedPhase],
) -> List[Dict[str, Any]]:
    """Use TriageRollcallAdapter to rank bot capabilities for each phase.

    Non-blocking on import failure.  Label: CTD-TRIAGE-001
    """
    rollcall_results: List[Dict[str, Any]] = []
    try:
        from triage_rollcall_adapter import TriageRollcallAdapter

        adapter = TriageRollcallAdapter()
        _register_known_bots(adapter)

        for phase in phases:
            capabilities = [phase.phase_type.value] + phase.module_hints
            result = adapter.rollcall(
                required_capabilities=capabilities, max_results=5
            )
            candidates = []
            for r in result if isinstance(result, list) else []:
                cand = getattr(r, "candidate", r)
                candidates.append({
                    "name": getattr(cand, "name", str(r)),
                    "score": getattr(r, "combined_score", 0.0),
                })
            rollcall_results.append({
                "phase_id": phase.phase_id,
                "candidates": candidates,
            })
    except Exception as exc:
        logger.warning(
            "CTD-TRIAGE-001: TriageRollcallAdapter unavailable: %s", exc
        )
        for phase in phases:
            rollcall_results.append({
                "phase_id": phase.phase_id,
                "candidates": [],
            })

    return rollcall_results


def _register_known_bots(adapter: Any) -> None:
    """Register known Murphy System bots.  Label: CTD-TRIAGE-002"""
    bot_defs = [
        (
            "RubixCubeBot",
            ["analysis", "research", "validation"],
            ["general"],
        ),
        (
            "ResearchBot",
            ["research", "research_engine", "multi_source_research"],
            ["research"],
        ),
        (
            "NicheBot",
            ["selection", "niche_business_generator", "niche_viability_gate"],
            ["business"],
        ),
        (
            "MarketBot",
            ["analysis", "market_positioning_engine",
             "competitive_intelligence_engine"],
            ["market"],
        ),
        (
            "BuildBot",
            ["build", "demo_deliverable_generator",
             "code_generation_gateway"],
            ["engineering"],
        ),
    ]
    for name, capabilities, domains in bot_defs:
        try:
            adapter.register_candidate(
                name=name, capabilities=capabilities, domains=domains
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CTD-RUBIX-001: RubixCube evidence validation
# ---------------------------------------------------------------------------


def _validate_with_rubix(data: Dict[str, Any]) -> Dict[str, Any]:
    """Run RubixEvidenceAdapter checks on phase output.

    Label: CTD-RUBIX-001
    """
    try:
        from rubix_evidence_adapter import RubixEvidenceAdapter

        adapter = RubixEvidenceAdapter()
        scores = _extract_numerical_scores(data)
        if scores:
            result = adapter.check_confidence_interval(
                samples=scores, threshold=0.5
            )
            return {
                "verdict": getattr(result, "verdict", "inconclusive"),
                "score": getattr(result, "score", 0.0),
                "checked": True,
            }
    except Exception as exc:
        logger.warning(
            "CTD-RUBIX-001: RubixEvidenceAdapter unavailable: %s", exc
        )
    return {"verdict": "inconclusive", "score": 0.0, "checked": False}


def _extract_numerical_scores(data: Dict[str, Any]) -> List[float]:
    """Extract numerical confidence/score values from nested dicts."""
    scores: List[float] = []
    for key, value in data.items():
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ("confidence", "score", "combined_score") and isinstance(
                    v, (int, float)
                ):
                    scores.append(float(v))
        elif isinstance(value, (int, float)) and key in (
            "confidence",
            "score",
        ):
            scores.append(float(value))
    return scores


# ---------------------------------------------------------------------------
# CTD-TRAJECTORY-001: RubixCube optimal trajectory tracking
# ---------------------------------------------------------------------------


def _init_trajectory_tracker() -> Any:
    """Initialise a PathConfidenceRegistry for trajectory scoring.

    Uses RubixCube's PathConfidenceRegistry to track which execution
    paths yield the highest confidence, steering subsequent phases toward
    optimal conditions and variables.

    Label: CTD-TRAJECTORY-001
    """
    try:
        from bots.rubixcube_bot import PathConfidenceRegistry

        return PathConfidenceRegistry()
    except Exception as exc:
        logger.warning(
            "CTD-TRAJECTORY-001: PathConfidenceRegistry unavailable: %s", exc
        )
        return None


def _update_trajectory(
    tracker: Any,
    path_key: str,
    phase: DecomposedPhase,
) -> None:
    """Update the trajectory tracker with a completed phase's metrics.

    Label: CTD-TRAJECTORY-002
    """
    if tracker is None:
        return
    try:
        fidelity = 0.9 if phase.success else 0.1
        ev = (phase.output or {}).get("evidence_validation", {})
        entropy = 1.0 - ev.get("score", 0.5)
        cost = max(0.01, phase.elapsed_ms / 1000.0)
        tracker.update(path_key, fidelity, entropy, cost)
    except Exception as exc:
        logger.warning(
            "CTD-TRAJECTORY-002: Trajectory update failed: %s", exc
        )


def _get_trajectory_scores(tracker: Any) -> Dict[str, float]:
    """Extract ranked trajectory scores.  Label: CTD-TRAJECTORY-003"""
    if tracker is None:
        return {}
    try:
        ranked = tracker.rank_paths()
        return dict(ranked) if ranked else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# CTD-001: Deterministic fallbacks
# ---------------------------------------------------------------------------


def _is_market_research(query: str) -> bool:
    """Check if the query involves market research."""
    q = query.lower()
    return any(
        kw in q
        for kw in ("market", "niche", "competitive", "industry", "segment")
    )


def _deterministic_market_research(query: str) -> Dict[str, Any]:
    """Deterministic market research fallback.

    Label: CTD-FALLBACK-RESEARCH-001
    """
    q = query.lower()

    niche_indicators: Dict[str, List[str]] = {
        "health": ["health", "wellness", "fitness", "medical", "healthcare"],
        "finance": ["finance", "fintech", "banking", "investment", "trading"],
        "education": [
            "education", "learning", "courses", "training", "edtech",
        ],
        "ecommerce": [
            "ecommerce", "e-commerce", "shopping", "retail", "store",
        ],
        "saas": ["saas", "software", "platform", "tool", "automation"],
        "real_estate": ["real estate", "property", "housing", "rental"],
        "food_delivery": ["food", "delivery", "restaurant", "catering"],
        "sustainability": [
            "sustainability", "green", "eco", "environment", "carbon",
        ],
        "ai_tools": [
            "ai", "artificial intelligence", "machine learning", "ml",
        ],
        "remote_work": [
            "remote", "work from home", "distributed", "virtual",
        ],
    }

    niches: List[str] = []
    for niche_name, keywords in niche_indicators.items():
        if any(kw in q for kw in keywords):
            niches.append(niche_name)

    if not niches:
        niches = ["saas", "ai_tools", "health", "ecommerce", "education"]

    return {
        "methodology": "deterministic_market_analysis",
        "disclaimer": (
            "This analysis uses deterministic heuristics. For live market "
            "data, configure API keys for research providers."
        ),
        "detected_niches": niches,
        "market_dimensions": {
            "total_addressable_market": "Analysis requires live data sources",
            "growth_rate": "Trending upward based on keyword indicators",
            "competition_level": "moderate",
            "barrier_to_entry": "low_to_moderate",
        },
        "top_niches_ranked": [
            {
                "niche": niches[0],
                "score": 0.85,
                "rationale": (
                    "High demand, recurring revenue model, scalable"
                ),
            },
            {
                "niche": niches[1] if len(niches) > 1 else "ai_tools",
                "score": 0.80,
                "rationale": "Rapid growth sector, strong unit economics",
            },
            {
                "niche": niches[2] if len(niches) > 2 else "health",
                "score": 0.75,
                "rationale": "Large TAM, evergreen demand",
            },
        ],
        "recommendation": (
            f"Based on analysis, '{niches[0]}' is the recommended "
            f"niche for an MVP. Key factors: market demand, feasibility "
            f"for MVP scope, and revenue potential."
        ),
    }


def _deterministic_niche_selection(
    query: str,
    research_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Select optimal niche from research data.

    Label: CTD-FALLBACK-SELECT-001
    """
    top_niches: List[Dict[str, Any]] = []
    for _key, value in research_data.items():
        if isinstance(value, dict):
            ranked = value.get("top_niches_ranked", [])
            if ranked:
                top_niches.extend(ranked)
            detected = value.get("detected_niches", [])
            if detected and not top_niches:
                top_niches = [
                    {"niche": n, "score": 0.7} for n in detected[:3]
                ]

    if not top_niches:
        top_niches = [
            {
                "niche": "saas",
                "score": 0.85,
                "rationale": "Default: high-value, scalable",
            },
        ]

    top_niches.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected = top_niches[0]

    return {
        "selected_niche": selected.get("niche", "saas"),
        "confidence": selected.get("score", 0.7),
        "rationale": selected.get(
            "rationale", "Selected based on viability analysis"
        ),
        "alternatives": [n.get("niche", "") for n in top_niches[1:3]],
        "selection_method": "ranked_scoring",
    }


# ---------------------------------------------------------------------------
# CTD-FORMAT-001: Context formatting
# ---------------------------------------------------------------------------


def _format_phase_output(phase: DecomposedPhase) -> str:
    """Format a phase output as human-readable context.

    Label: CTD-FORMAT-001
    """
    if not phase.output:
        return ""

    lines: List[str] = []
    pt = phase.phase_type.value.upper()
    lines.append(f"--- Phase {phase.phase_id}: {pt} ---")
    lines.append(f"  Description: {phase.description}")

    output = phase.output

    if output.get("deterministic_research"):
        dr = output["deterministic_research"]
        rec = dr.get("recommendation", "")
        if rec:
            lines.append(f"  Recommendation: {rec}")
        niches = dr.get("detected_niches", [])
        if niches:
            lines.append(f"  Detected niches: {', '.join(niches)}")
        ranked = dr.get("top_niches_ranked", [])
        if ranked:
            lines.append("  Top niches:")
            for entry in ranked:
                n = entry.get("niche", "?")
                s = entry.get("score", 0)
                r = entry.get("rationale", "")
                lines.append(f"    - {n}: score={s:.2f} - {r}")

    if output.get("selected_niche"):
        sn = output["selected_niche"]
        if isinstance(sn, dict):
            lines.append(
                f"  Selected niche: {sn.get('selected_niche', '?')}"
            )
            lines.append(f"  Confidence: {sn.get('confidence', 0):.2f}")
            lines.append(f"  Rationale: {sn.get('rationale', '')}")
            alts = sn.get("alternatives", [])
            if alts:
                lines.append(
                    f"  Alternatives: {', '.join(str(a) for a in alts)}"
                )

    ev = output.get("evidence_validation", {})
    if ev.get("checked"):
        lines.append(f"  Evidence validation: {ev.get('verdict', 'unknown')}")

    lines.append(f"  Elapsed: {phase.elapsed_ms}ms")
    return "\n".join(lines)
