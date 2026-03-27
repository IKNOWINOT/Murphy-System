"""
Order Sensitivity Metrics for Murphy System

Measures variance, fragility, and robustness under different orderings.
This module provides the statistical foundation for evaluating whether
information ordering actually matters (true path dependence vs artifacts).

Key metrics:
- Order sensitivity: Does order affect outcomes?
- Fragility: How sensitive are outcomes to small order changes?
- Robustness: How stable are outcomes across permutation families?
- Path dependence strength: Quantified measure of ordering impact

Reference: Permutation Calibration Application Spec Section 8
Owner: INONI LLC / Corey Post
"""

import logging
import math
import random
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class SensitivityLevel(str, Enum):
    """Classification of order sensitivity."""
    INVARIANT = "invariant"         # Order does not affect outcomes
    LOW = "low"                     # Minimal order effect
    MODERATE = "moderate"           # Noticeable order effect
    HIGH = "high"                   # Strong order effect
    CRITICAL = "critical"           # Order is crucial for outcomes


class FragilityLevel(str, Enum):
    """Classification of fragility."""
    ROBUST = "robust"               # Highly tolerant of order changes
    STABLE = "stable"               # Generally stable
    SENSITIVE = "sensitive"         # Sensitive to changes
    FRAGILE = "fragile"             # Very sensitive
    BRITTLE = "brittle"             # Breaks with minor changes


@dataclass
class OrderingObservation:
    """A single observation of ordering effects."""
    observation_id: str
    domain: str
    ordering: List[str]
    outcome_score: float
    calibration_score: float
    execution_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensitivityAnalysis:
    """Result of analyzing order sensitivity."""
    analysis_id: str
    domain: str
    sample_size: int
    
    # Core metrics
    outcome_variance: float
    calibration_variance: float
    time_variance: float
    
    # Sensitivity classification
    sensitivity_level: SensitivityLevel
    sensitivity_score: float  # 0.0 (invariant) to 1.0 (critical)
    
    # Statistical measures
    outcome_mean: float
    outcome_std: float
    outcome_min: float
    outcome_max: float
    outcome_range: float
    
    # Correlation with order position
    position_correlation: float
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class FragilityAnalysis:
    """Result of analyzing ordering fragility."""
    analysis_id: str
    domain: str
    sample_size: int
    
    # Core metrics
    fragility_level: FragilityLevel
    fragility_score: float  # 0.0 (robust) to 1.0 (brittle)
    
    # Swap sensitivity
    adjacent_swap_impact: float     # Impact of swapping adjacent items
    random_swap_impact: float       # Impact of random swaps
    
    # Perturbation resilience
    single_change_resilience: float
    multi_change_resilience: float
    
    # Recovery metrics
    recovery_potential: float       # How quickly outcomes recover
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass  
class RobustnessAnalysis:
    """Result of analyzing ordering robustness."""
    analysis_id: str
    domain: str
    sample_size: int
    
    # Core metrics
    robustness_score: float  # 0.0 (fragile) to 1.0 (robust)
    
    # Family-level metrics
    family_consistency: float       # Consistency within ordering families
    cross_family_variance: float    # Variance across families
    
    # Best performers
    best_ordering: List[str]
    best_score: float
    worst_ordering: List[str]
    worst_score: float
    
    # Reliability
    repeatability_score: float      # Same ordering gives same results
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PathDependenceAnalysis:
    """Comprehensive path dependence analysis."""
    analysis_id: str
    domain: str
    
    # Classification
    is_path_dependent: bool
    path_dependence_strength: float  # 0.0-1.0
    
    # Contributing factors
    sensitivity_analysis: SensitivityAnalysis
    fragility_analysis: FragilityAnalysis
    robustness_analysis: RobustnessAnalysis
    
    # Recommendations
    should_learn_ordering: bool
    recommended_exploration_mode: str
    confidence_in_analysis: float
    
    # Summary
    summary: str
    
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OrderSensitivityMetrics:
    """Measures and tracks order sensitivity across Murphy's operations.
    
    This module answers the key question: Does information ordering
    actually matter for this task/domain, or is it an artifact?
    
    Implements spec Section 8: Murphy should optimize for best reliable
    performance under variation, not just best single run.
    """
    
    _MAX_OBSERVATIONS = 50_000
    _MAX_ANALYSES = 1_000
    
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._observations: Dict[str, List[OrderingObservation]] = defaultdict(list)
        self._sensitivity_cache: Dict[str, SensitivityAnalysis] = {}
        self._fragility_cache: Dict[str, FragilityAnalysis] = {}
        self._robustness_cache: Dict[str, RobustnessAnalysis] = {}
        self._path_dependence_cache: Dict[str, PathDependenceAnalysis] = {}
        
        logger.info("OrderSensitivityMetrics initialized")
    
    # ------------------------------------------------------------------
    # Observation Recording
    # ------------------------------------------------------------------
    
    def record_observation(
        self,
        domain: str,
        ordering: List[str],
        outcome_score: float,
        calibration_score: float = 0.5,
        execution_time_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record an observation of ordering effects.
        
        Args:
            domain: Domain/task family
            ordering: The ordering used
            outcome_score: Outcome quality (0.0-1.0)
            calibration_score: Calibration quality (0.0-1.0)
            execution_time_ms: Execution time
            metadata: Optional metadata
            
        Returns:
            observation_id
        """
        observation = OrderingObservation(
            observation_id=f"obs-{uuid.uuid4().hex[:12]}",
            domain=domain,
            ordering=list(ordering),
            outcome_score=_clamp(outcome_score),
            calibration_score=_clamp(calibration_score),
            execution_time_ms=max(0.0, execution_time_ms),
            metadata=metadata or {},
        )
        
        with self._lock:
            obs_list = self._observations[domain]
            max_per_domain = self._MAX_OBSERVATIONS // max(1, len(self._observations))
            if len(obs_list) >= max_per_domain:
                obs_list.pop(0)
            obs_list.append(observation)
            
            # Invalidate caches for this domain
            self._sensitivity_cache.pop(domain, None)
            self._fragility_cache.pop(domain, None)
            self._robustness_cache.pop(domain, None)
            self._path_dependence_cache.pop(domain, None)
        
        return observation.observation_id
    
    # ------------------------------------------------------------------
    # Sensitivity Analysis
    # ------------------------------------------------------------------
    
    def analyze_sensitivity(
        self,
        domain: str,
        min_samples: int = 10,
    ) -> Dict[str, Any]:
        """Analyze order sensitivity for a domain.
        
        Args:
            domain: Domain to analyze
            min_samples: Minimum observations required
            
        Returns:
            Sensitivity analysis result
        """
        with self._lock:
            observations = list(self._observations.get(domain, []))
        
        if len(observations) < min_samples:
            return {
                "status": "insufficient_data",
                "domain": domain,
                "observations": len(observations),
                "required": min_samples,
            }
        
        # Extract scores
        outcomes = [o.outcome_score for o in observations]
        calibrations = [o.calibration_score for o in observations]
        times = [o.execution_time_ms for o in observations]
        
        # Calculate variance
        outcome_var = _variance(outcomes)
        calibration_var = _variance(calibrations)
        time_var = _variance(times)
        
        # Calculate statistics
        outcome_mean = _mean(outcomes)
        outcome_std = math.sqrt(outcome_var)
        outcome_min = min(outcomes)
        outcome_max = max(outcomes)
        outcome_range = outcome_max - outcome_min
        
        # Calculate position correlation (simplified)
        position_correlation = self._calculate_position_correlation(observations)
        
        # Determine sensitivity level
        sensitivity_score = min(1.0, outcome_var * 10 + abs(position_correlation) * 0.3)
        sensitivity_level = self._classify_sensitivity(sensitivity_score)
        
        analysis = SensitivityAnalysis(
            analysis_id=f"sens-{uuid.uuid4().hex[:12]}",
            domain=domain,
            sample_size=len(observations),
            outcome_variance=round(outcome_var, 6),
            calibration_variance=round(calibration_var, 6),
            time_variance=round(time_var, 6),
            sensitivity_level=sensitivity_level,
            sensitivity_score=round(sensitivity_score, 4),
            outcome_mean=round(outcome_mean, 4),
            outcome_std=round(outcome_std, 4),
            outcome_min=round(outcome_min, 4),
            outcome_max=round(outcome_max, 4),
            outcome_range=round(outcome_range, 4),
            position_correlation=round(position_correlation, 4),
        )
        
        with self._lock:
            self._sensitivity_cache[domain] = analysis
        
        return self._sensitivity_to_dict(analysis)
    
    def _calculate_position_correlation(self, observations: List[OrderingObservation]) -> float:
        """Calculate correlation between item position and outcomes."""
        if not observations or not observations[0].ordering:
            return 0.0
        
        # Simplified: check if first item identity correlates with outcome
        first_items: Dict[str, List[float]] = defaultdict(list)
        for obs in observations:
            if obs.ordering:
                first_items[obs.ordering[0]].append(obs.outcome_score)
        
        if len(first_items) < 2:
            return 0.0
        
        # Calculate variance between first-item groups
        group_means = [_mean(scores) for scores in first_items.values() if scores]
        if len(group_means) < 2:
            return 0.0
        
        between_var = _variance(group_means)
        total_var = _variance([o.outcome_score for o in observations])
        
        if total_var < 1e-10:
            return 0.0
        
        return min(1.0, between_var / total_var)
    
    def _classify_sensitivity(self, score: float) -> SensitivityLevel:
        """Classify sensitivity level from score."""
        if score < 0.1:
            return SensitivityLevel.INVARIANT
        elif score < 0.25:
            return SensitivityLevel.LOW
        elif score < 0.5:
            return SensitivityLevel.MODERATE
        elif score < 0.75:
            return SensitivityLevel.HIGH
        else:
            return SensitivityLevel.CRITICAL
    
    def _sensitivity_to_dict(self, analysis: SensitivityAnalysis) -> Dict[str, Any]:
        """Convert sensitivity analysis to dict."""
        return {
            "status": "ok",
            "analysis_id": analysis.analysis_id,
            "domain": analysis.domain,
            "sample_size": analysis.sample_size,
            "outcome_variance": analysis.outcome_variance,
            "calibration_variance": analysis.calibration_variance,
            "time_variance": analysis.time_variance,
            "sensitivity_level": analysis.sensitivity_level.value,
            "sensitivity_score": analysis.sensitivity_score,
            "outcome_mean": analysis.outcome_mean,
            "outcome_std": analysis.outcome_std,
            "outcome_range": analysis.outcome_range,
            "position_correlation": analysis.position_correlation,
            "timestamp": analysis.timestamp,
        }
    
    # ------------------------------------------------------------------
    # Fragility Analysis
    # ------------------------------------------------------------------
    
    def analyze_fragility(
        self,
        domain: str,
        min_samples: int = 20,
    ) -> Dict[str, Any]:
        """Analyze ordering fragility for a domain.
        
        Fragility measures how sensitive outcomes are to small changes
        in the ordering.
        
        Args:
            domain: Domain to analyze
            min_samples: Minimum observations required
            
        Returns:
            Fragility analysis result
        """
        with self._lock:
            observations = list(self._observations.get(domain, []))
        
        if len(observations) < min_samples:
            return {
                "status": "insufficient_data",
                "domain": domain,
                "observations": len(observations),
                "required": min_samples,
            }
        
        # Group by ordering similarity
        ordering_groups = self._group_by_similarity(observations)
        
        # Calculate swap impacts
        adjacent_impact = self._calculate_adjacent_swap_impact(ordering_groups)
        random_impact = self._calculate_random_swap_impact(observations)
        
        # Calculate resilience
        single_resilience = 1.0 - adjacent_impact
        multi_resilience = 1.0 - random_impact
        
        # Recovery potential (how quickly does performance stabilize)
        recovery = self._estimate_recovery_potential(observations)
        
        # Calculate fragility score
        fragility_score = (adjacent_impact * 0.4 + random_impact * 0.4 + (1 - recovery) * 0.2)
        fragility_level = self._classify_fragility(fragility_score)
        
        analysis = FragilityAnalysis(
            analysis_id=f"frag-{uuid.uuid4().hex[:12]}",
            domain=domain,
            sample_size=len(observations),
            fragility_level=fragility_level,
            fragility_score=round(fragility_score, 4),
            adjacent_swap_impact=round(adjacent_impact, 4),
            random_swap_impact=round(random_impact, 4),
            single_change_resilience=round(single_resilience, 4),
            multi_change_resilience=round(multi_resilience, 4),
            recovery_potential=round(recovery, 4),
        )
        
        with self._lock:
            self._fragility_cache[domain] = analysis
        
        return self._fragility_to_dict(analysis)
    
    def _group_by_similarity(
        self, 
        observations: List[OrderingObservation]
    ) -> Dict[str, List[OrderingObservation]]:
        """Group observations by ordering similarity."""
        groups: Dict[str, List[OrderingObservation]] = defaultdict(list)
        for obs in observations:
            key = tuple(obs.ordering)
            groups[str(key)].append(obs)
        return groups
    
    def _calculate_adjacent_swap_impact(
        self,
        groups: Dict[str, List[OrderingObservation]],
    ) -> float:
        """Calculate impact of swapping adjacent items."""
        if len(groups) < 2:
            return 0.0
        
        impacts = []
        group_keys = list(groups.keys())
        
        for i, key1 in enumerate(group_keys):
            # Use ast.literal_eval for safe parsing of tuple strings
            import ast
            ordering1 = ast.literal_eval(key1) if key1.startswith("(") else key1
            scores1 = [o.outcome_score for o in groups[key1]]
            
            for key2 in group_keys[i+1:]:
                ordering2 = ast.literal_eval(key2) if key2.startswith("(") else key2
                
                # Check if orderings differ by exactly one adjacent swap
                if self._is_adjacent_swap(list(ordering1), list(ordering2)):
                    scores2 = [o.outcome_score for o in groups[key2]]
                    impact = abs(_mean(scores1) - _mean(scores2))
                    impacts.append(impact)
        
        return _mean(impacts) if impacts else 0.3
    
    def _is_adjacent_swap(self, order1: List[str], order2: List[str]) -> bool:
        """Check if order2 is order1 with exactly one adjacent swap."""
        if len(order1) != len(order2):
            return False
        
        diffs = [(i, order1[i], order2[i]) for i in range(len(order1)) if order1[i] != order2[i]]
        if len(diffs) != 2:
            return False
        
        i, j = diffs[0][0], diffs[1][0]
        return abs(i - j) == 1 and order1[i] == order2[j] and order1[j] == order2[i]
    
    def _calculate_random_swap_impact(self, observations: List[OrderingObservation]) -> float:
        """Calculate impact of random swaps (proxy via variance)."""
        outcomes = [o.outcome_score for o in observations]
        return min(1.0, _variance(outcomes) * 5)
    
    def _estimate_recovery_potential(self, observations: List[OrderingObservation]) -> float:
        """Estimate how quickly performance recovers from perturbations."""
        if len(observations) < 5:
            return 0.5
        
        # Look at variance over time windows
        recent = observations[-len(observations)//2:]
        older = observations[:len(observations)//2]
        
        recent_var = _variance([o.outcome_score for o in recent])
        older_var = _variance([o.outcome_score for o in older])
        
        if older_var < 1e-10:
            return 0.8
        
        improvement = (older_var - recent_var) / older_var
        return _clamp(0.5 + improvement * 0.5)
    
    def _classify_fragility(self, score: float) -> FragilityLevel:
        """Classify fragility level from score."""
        if score < 0.15:
            return FragilityLevel.ROBUST
        elif score < 0.35:
            return FragilityLevel.STABLE
        elif score < 0.55:
            return FragilityLevel.SENSITIVE
        elif score < 0.75:
            return FragilityLevel.FRAGILE
        else:
            return FragilityLevel.BRITTLE
    
    def _fragility_to_dict(self, analysis: FragilityAnalysis) -> Dict[str, Any]:
        """Convert fragility analysis to dict."""
        return {
            "status": "ok",
            "analysis_id": analysis.analysis_id,
            "domain": analysis.domain,
            "sample_size": analysis.sample_size,
            "fragility_level": analysis.fragility_level.value,
            "fragility_score": analysis.fragility_score,
            "adjacent_swap_impact": analysis.adjacent_swap_impact,
            "random_swap_impact": analysis.random_swap_impact,
            "single_change_resilience": analysis.single_change_resilience,
            "multi_change_resilience": analysis.multi_change_resilience,
            "recovery_potential": analysis.recovery_potential,
            "timestamp": analysis.timestamp,
        }
    
    # ------------------------------------------------------------------
    # Robustness Analysis
    # ------------------------------------------------------------------
    
    def analyze_robustness(
        self,
        domain: str,
        min_samples: int = 15,
    ) -> Dict[str, Any]:
        """Analyze ordering robustness for a domain.
        
        Robustness measures stability across ordering families.
        
        Args:
            domain: Domain to analyze
            min_samples: Minimum observations required
            
        Returns:
            Robustness analysis result
        """
        with self._lock:
            observations = list(self._observations.get(domain, []))
        
        if len(observations) < min_samples:
            return {
                "status": "insufficient_data",
                "domain": domain,
                "observations": len(observations),
                "required": min_samples,
            }
        
        # Group by ordering
        groups = self._group_by_similarity(observations)
        
        # Calculate family consistency
        family_variances = []
        for group_obs in groups.values():
            if len(group_obs) >= 2:
                scores = [o.outcome_score for o in group_obs]
                family_variances.append(_variance(scores))
        
        family_consistency = 1.0 - _mean(family_variances) * 5 if family_variances else 0.5
        
        # Calculate cross-family variance
        family_means = [_mean([o.outcome_score for o in obs]) for obs in groups.values() if obs]
        cross_family_var = _variance(family_means) if len(family_means) > 1 else 0.0
        
        # Find best and worst orderings
        best_ordering, best_score = [], 0.0
        worst_ordering, worst_score = [], 1.0
        
        for key, group_obs in groups.items():
            mean_score = _mean([o.outcome_score for o in group_obs])
            if mean_score > best_score:
                best_score = mean_score
                best_ordering = group_obs[0].ordering if group_obs else []
            if mean_score < worst_score:
                worst_score = mean_score
                worst_ordering = group_obs[0].ordering if group_obs else []
        
        # Calculate repeatability
        repeatability = family_consistency
        
        # Robustness score
        robustness_score = (family_consistency * 0.5 + (1 - cross_family_var * 5) * 0.3 + repeatability * 0.2)
        robustness_score = _clamp(robustness_score)
        
        analysis = RobustnessAnalysis(
            analysis_id=f"rob-{uuid.uuid4().hex[:12]}",
            domain=domain,
            sample_size=len(observations),
            robustness_score=round(robustness_score, 4),
            family_consistency=round(_clamp(family_consistency), 4),
            cross_family_variance=round(cross_family_var, 6),
            best_ordering=best_ordering,
            best_score=round(best_score, 4),
            worst_ordering=worst_ordering,
            worst_score=round(worst_score, 4),
            repeatability_score=round(repeatability, 4),
        )
        
        with self._lock:
            self._robustness_cache[domain] = analysis
        
        return self._robustness_to_dict(analysis)
    
    def _robustness_to_dict(self, analysis: RobustnessAnalysis) -> Dict[str, Any]:
        """Convert robustness analysis to dict."""
        return {
            "status": "ok",
            "analysis_id": analysis.analysis_id,
            "domain": analysis.domain,
            "sample_size": analysis.sample_size,
            "robustness_score": analysis.robustness_score,
            "family_consistency": analysis.family_consistency,
            "cross_family_variance": analysis.cross_family_variance,
            "best_ordering": analysis.best_ordering,
            "best_score": analysis.best_score,
            "worst_ordering": analysis.worst_ordering,
            "worst_score": analysis.worst_score,
            "repeatability_score": analysis.repeatability_score,
            "timestamp": analysis.timestamp,
        }
    
    # ------------------------------------------------------------------
    # Path Dependence Analysis
    # ------------------------------------------------------------------
    
    def analyze_path_dependence(
        self,
        domain: str,
        min_samples: int = 20,
    ) -> Dict[str, Any]:
        """Perform comprehensive path dependence analysis.
        
        This is the main entry point that combines sensitivity, fragility,
        and robustness analysis to determine if order truly matters.
        
        Args:
            domain: Domain to analyze
            min_samples: Minimum observations required
            
        Returns:
            Comprehensive path dependence analysis
        """
        # Run component analyses
        sens_result = self.analyze_sensitivity(domain, min_samples)
        if sens_result.get("status") != "ok":
            return sens_result
        
        frag_result = self.analyze_fragility(domain, min_samples)
        if frag_result.get("status") != "ok":
            return frag_result
        
        rob_result = self.analyze_robustness(domain, min_samples)
        if rob_result.get("status") != "ok":
            return rob_result
        
        with self._lock:
            sens_analysis = self._sensitivity_cache.get(domain)
            frag_analysis = self._fragility_cache.get(domain)
            rob_analysis = self._robustness_cache.get(domain)
        
        if not all([sens_analysis, frag_analysis, rob_analysis]):
            return {"status": "error", "reason": "analysis_cache_error"}
        
        # Determine path dependence
        path_strength = (
            sens_analysis.sensitivity_score * 0.4 +
            frag_analysis.fragility_score * 0.3 +
            (1 - rob_analysis.robustness_score) * 0.3
        )
        
        is_path_dependent = path_strength > 0.3
        
        # Should we learn ordering?
        should_learn = (
            is_path_dependent and
            sens_analysis.sensitivity_level not in [SensitivityLevel.INVARIANT, SensitivityLevel.LOW] and
            rob_analysis.robustness_score > 0.4  # There are learnable patterns
        )
        
        # Recommend exploration mode
        if sens_analysis.sensitivity_level == SensitivityLevel.CRITICAL:
            exploration_mode = "exhaustive"
        elif sens_analysis.sensitivity_level == SensitivityLevel.HIGH:
            exploration_mode = "beam_search"
        elif should_learn:
            exploration_mode = "sampling"
        else:
            exploration_mode = "none"
        
        # Confidence in this analysis
        confidence = min(1.0, sens_analysis.sample_size / 50)
        
        # Generate summary
        if not is_path_dependent:
            summary = f"Order appears invariant for domain '{domain}'. No ordering optimization needed."
        elif not should_learn:
            summary = f"Domain '{domain}' shows order sensitivity but patterns are too fragile to learn reliably."
        else:
            summary = (
                f"Domain '{domain}' shows significant path dependence (strength={path_strength:.2f}). "
                f"Ordering optimization recommended using {exploration_mode} exploration."
            )
        
        analysis = PathDependenceAnalysis(
            analysis_id=f"pdep-{uuid.uuid4().hex[:12]}",
            domain=domain,
            is_path_dependent=is_path_dependent,
            path_dependence_strength=round(path_strength, 4),
            sensitivity_analysis=sens_analysis,
            fragility_analysis=frag_analysis,
            robustness_analysis=rob_analysis,
            should_learn_ordering=should_learn,
            recommended_exploration_mode=exploration_mode,
            confidence_in_analysis=round(confidence, 4),
            summary=summary,
        )
        
        with self._lock:
            self._path_dependence_cache[domain] = analysis
        
        return self._path_dependence_to_dict(analysis)
    
    def _path_dependence_to_dict(self, analysis: PathDependenceAnalysis) -> Dict[str, Any]:
        """Convert path dependence analysis to dict."""
        return {
            "status": "ok",
            "analysis_id": analysis.analysis_id,
            "domain": analysis.domain,
            "is_path_dependent": analysis.is_path_dependent,
            "path_dependence_strength": analysis.path_dependence_strength,
            "sensitivity": self._sensitivity_to_dict(analysis.sensitivity_analysis),
            "fragility": self._fragility_to_dict(analysis.fragility_analysis),
            "robustness": self._robustness_to_dict(analysis.robustness_analysis),
            "should_learn_ordering": analysis.should_learn_ordering,
            "recommended_exploration_mode": analysis.recommended_exploration_mode,
            "confidence_in_analysis": analysis.confidence_in_analysis,
            "summary": analysis.summary,
            "timestamp": analysis.timestamp,
        }
    
    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    
    def get_domain_observations(
        self,
        domain: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent observations for a domain."""
        with self._lock:
            observations = list(self._observations.get(domain, []))
        
        observations = observations[-limit:]
        return [
            {
                "observation_id": o.observation_id,
                "ordering": o.ordering,
                "outcome_score": round(o.outcome_score, 4),
                "calibration_score": round(o.calibration_score, 4),
                "execution_time_ms": round(o.execution_time_ms, 2),
                "timestamp": o.timestamp,
            }
            for o in reversed(observations)
        ]
    
    def get_cached_analysis(self, domain: str) -> Dict[str, Any]:
        """Get cached analysis for a domain if available."""
        with self._lock:
            sens = self._sensitivity_cache.get(domain)
            frag = self._fragility_cache.get(domain)
            rob = self._robustness_cache.get(domain)
            pdep = self._path_dependence_cache.get(domain)
        
        return {
            "domain": domain,
            "sensitivity": self._sensitivity_to_dict(sens) if sens else None,
            "fragility": self._fragility_to_dict(frag) if frag else None,
            "robustness": self._robustness_to_dict(rob) if rob else None,
            "path_dependence": self._path_dependence_to_dict(pdep) if pdep else None,
        }
    
    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        with self._lock:
            total_obs = sum(len(obs) for obs in self._observations.values())
            domains = list(self._observations.keys())
            
            return {
                "status": "ok",
                "total_observations": total_obs,
                "domains_tracked": len(domains),
                "domains": domains,
                "cached_sensitivity_analyses": len(self._sensitivity_cache),
                "cached_fragility_analyses": len(self._fragility_cache),
                "cached_robustness_analyses": len(self._robustness_cache),
                "cached_path_dependence_analyses": len(self._path_dependence_cache),
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get metrics operational status."""
        stats = self.get_statistics()
        return {
            "engine": "OrderSensitivityMetrics",
            "operational": True,
            **stats,
        }
    
    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    
    def clear(self, domain: Optional[str] = None) -> None:
        """Clear metrics state, optionally for a specific domain."""
        with self._lock:
            if domain:
                self._observations.pop(domain, None)
                self._sensitivity_cache.pop(domain, None)
                self._fragility_cache.pop(domain, None)
                self._robustness_cache.pop(domain, None)
                self._path_dependence_cache.pop(domain, None)
                logger.info("Cleared metrics for domain '%s'", domain)
            else:
                self._observations.clear()
                self._sensitivity_cache.clear()
                self._fragility_cache.clear()
                self._robustness_cache.clear()
                self._path_dependence_cache.clear()
                logger.info("OrderSensitivityMetrics cleared")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))


def _mean(values: List[float]) -> float:
    """Calculate mean of values."""
    return sum(values) / len(values) if values else 0.0


def _variance(values: List[float]) -> float:
    """Calculate variance of values."""
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return sum((v - mean) ** 2 for v in values) / (len(values) - 1)
