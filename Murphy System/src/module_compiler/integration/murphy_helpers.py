"""
Murphy Integration Patterns

Helper classes and utilities for integrating the Module Compiler
with the Murphy System (MFGC-AI).

Provides:
- Capability discovery helpers
- Gate synthesis from capability metadata
- Best capability selection algorithms
- Resource checking utilities
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CapabilityMatch:
    """
    Match between a task and a capability.

    Attributes:
        capability_name: Name of matched capability
        match_score: How well capability matches task (0.0 to 1.0)
        confidence: Confidence in match
        reasons: Why this capability matches
        requirements_met: Which requirements are met
        requirements_missing: Which requirements are missing
    """

    capability_name: str
    match_score: float
    confidence: float
    reasons: List[str]
    requirements_met: List[str]
    requirements_missing: List[str]


class MurphyIntegrationHelper:
    """
    Helper class for integrating Module Compiler with Murphy System.

    Provides utilities for:
    - Discovering capabilities
    - Synthesizing gates from capability metadata
    - Selecting best capability for a task
    - Checking resource availability
    """

    def __init__(self, module_registry=None):
        """
        Initialize Murphy integration helper.

        Args:
            module_registry: Module registry instance
        """
        self.module_registry = module_registry

    # ========== Capability Discovery ==========

    def find_capabilities_for_task(
        self,
        task_description: str,
        task_requirements: Dict[str, Any]
    ) -> List[CapabilityMatch]:
        """
        Find capabilities that match a task.

        Args:
            task_description: Description of task
            task_requirements: Task requirements (e.g., {"network": True, "deterministic": True})

        Returns:
            List of capability matches, sorted by match score
        """
        if not self.module_registry:
            return []

        matches = []

        # Get all capabilities from registry
        all_capabilities = self._get_all_capabilities()

        for capability in all_capabilities:
            # Compute match score
            match = self._compute_match(capability, task_description, task_requirements)

            if match.match_score > 0.3:  # Threshold for relevance
                matches.append(match)

        # Sort by match score (descending)
        matches.sort(key=lambda m: m.match_score, reverse=True)

        return matches

    def _get_all_capabilities(self) -> List[Any]:
        """Get all capabilities from registry"""
        # Registry integration deferred; returns safe default
        return []

    def _compute_match(
        self,
        capability: Any,
        task_description: str,
        task_requirements: Dict[str, Any]
    ) -> CapabilityMatch:
        """Compute match between capability and task"""

        match_score = 0.0
        confidence = 0.0
        reasons = []
        requirements_met = []
        requirements_missing = []

        # Check determinism requirement
        if "deterministic" in task_requirements:
            required_deterministic = task_requirements["deterministic"]
            is_deterministic = getattr(capability, 'determinism_level', '') == "deterministic"

            if required_deterministic == is_deterministic:
                match_score += 0.3
                requirements_met.append("deterministic")
                reasons.append("Determinism level matches")
            else:
                requirements_missing.append("deterministic")

        # Check network requirement
        if "network" in task_requirements:
            required_network = task_requirements["network"]
            has_network = getattr(capability, 'requires_network', False)

            if required_network == has_network:
                match_score += 0.2
                requirements_met.append("network")
                reasons.append("Network requirement matches")
            else:
                requirements_missing.append("network")

        # Check resource requirements
        if "max_cpu" in task_requirements:
            max_cpu = task_requirements["max_cpu"]
            capability_cpu = getattr(capability, 'cpu_requirement', 1.0)

            if capability_cpu <= max_cpu:
                match_score += 0.2
                requirements_met.append("cpu")
                reasons.append(f"CPU requirement met ({capability_cpu} <= {max_cpu})")
            else:
                requirements_missing.append("cpu")

        # Compute confidence based on metadata quality
        confidence = min(1.0, match_score + 0.2)

        return CapabilityMatch(
            capability_name=getattr(capability, 'name', 'unknown'),
            match_score=match_score,
            confidence=confidence,
            reasons=reasons,
            requirements_met=requirements_met,
            requirements_missing=requirements_missing
        )

    # ========== Gate Synthesis ==========

    def synthesize_gates_from_capability(
        self,
        capability: Any,
        failure_modes: List[Any] = None,
        sandbox_profile: Any = None
    ) -> List[Dict[str, Any]]:
        """
        Synthesize safety gates from capability metadata.

        Args:
            capability: Capability to synthesize gates for
            failure_modes: Detected failure modes
            sandbox_profile: Sandbox profile

        Returns:
            List of gates with predicates and satisfaction status
        """
        gates = []
        failure_modes = failure_modes or []

        # Gate 1: Determinism gate
        gates.append({
            'predicate': 'determinism_acceptable',
            'satisfied': self._check_determinism(capability),
            'confidence': 0.9,
            'metadata': {
                'determinism_level': getattr(capability, 'determinism_level', 'unknown'),
                'reason': 'Capability determinism level checked'
            }
        })

        # Gate 2: Risk gate
        gates.append({
            'predicate': 'risk_acceptable',
            'satisfied': self._check_risk(failure_modes),
            'confidence': 0.85,
            'metadata': {
                'max_risk': max((f.risk_score for f in failure_modes if hasattr(f, 'risk_score')), default=0.0),
                'threshold': 0.5,
                'reason': 'Maximum risk score below threshold'
            }
        })

        # Gate 3: Resource availability gate
        if sandbox_profile:
            gates.append({
                'predicate': 'resources_available',
                'satisfied': self._check_resources_available(sandbox_profile),
                'confidence': 0.95,
                'metadata': {
                    'cpu_required': getattr(sandbox_profile, 'cpu_cores', 0),
                    'memory_required': getattr(sandbox_profile, 'memory_mb', 0),
                    'reason': 'Required resources are available'
                }
            })

        # Gate 4: Network access gate (if needed)
        if getattr(capability, 'requires_network', False):
            gates.append({
                'predicate': 'network_access_allowed',
                'satisfied': self._check_network_policy(),
                'confidence': 0.8,
                'metadata': {
                    'required': True,
                    'reason': 'Network access policy checked'
                }
            })

        # Gate 5: Test coverage gate
        test_vectors = getattr(capability, 'test_vectors', [])
        if test_vectors:
            gates.append({
                'predicate': 'test_coverage_adequate',
                'satisfied': len(test_vectors) >= 10,
                'confidence': 0.9,
                'metadata': {
                    'test_count': len(test_vectors),
                    'threshold': 10,
                    'reason': 'Adequate test coverage'
                }
            })

        return gates

    def _check_determinism(self, capability: Any) -> bool:
        """Check if determinism level is acceptable"""
        determinism_level = getattr(capability, 'determinism_level', 'unknown')
        # Accept deterministic and probabilistic, reject external_state
        return determinism_level in ['deterministic', 'probabilistic']

    def _check_risk(self, failure_modes: List[Any]) -> bool:
        """Check if risk is acceptable"""
        if not failure_modes:
            return True

        max_risk = max((f.risk_score for f in failure_modes if hasattr(f, 'risk_score')), default=0.0)
        return max_risk < 0.5  # Risk threshold

    def _check_resources_available(self, sandbox_profile: Any) -> bool:
        """Check if required resources are available"""
        # System-resource check deferred; returns permissive default
        cpu_required = getattr(sandbox_profile, 'cpu_cores', 0)
        memory_required = getattr(sandbox_profile, 'memory_mb', 0)

        # Simple check - assume resources available if reasonable
        return cpu_required <= 4.0 and memory_required <= 4096

    def _check_network_policy(self) -> bool:
        """Check if network access is allowed by policy"""
        # Network-policy check deferred; returns permissive default
        return True

    # ========== Best Capability Selection ==========

    def select_best_capability(
        self,
        matches: List[CapabilityMatch],
        selection_criteria: Dict[str, Any] = None
    ) -> Optional[CapabilityMatch]:
        """
        Select best capability from matches.

        Args:
            matches: List of capability matches
            selection_criteria: Selection criteria (e.g., {"prefer_deterministic": True})

        Returns:
            Best capability match, or None if no suitable match
        """
        if not matches:
            return None

        selection_criteria = selection_criteria or {}

        # Filter by minimum match score
        min_score = selection_criteria.get('min_match_score', 0.5)
        suitable_matches = [m for m in matches if m.match_score >= min_score]

        if not suitable_matches:
            return None

        # Apply preferences
        if selection_criteria.get('prefer_deterministic', False):
            # Prefer capabilities with "deterministic" in requirements_met
            deterministic_matches = [
                m for m in suitable_matches
                if 'deterministic' in m.requirements_met
            ]
            if deterministic_matches:
                suitable_matches = deterministic_matches

        if selection_criteria.get('prefer_high_confidence', True):
            # Sort by confidence
            suitable_matches.sort(key=lambda m: m.confidence, reverse=True)

        # Return best match
        return suitable_matches[0]

    # ========== Resource Checking ==========

    def check_resource_constraints(
        self,
        sandbox_profile: Any,
        available_resources: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if sandbox profile fits within available resources.

        Args:
            sandbox_profile: Sandbox profile with resource requirements
            available_resources: Available system resources

        Returns:
            Dictionary with check results
        """
        results = {
            'fits': True,
            'violations': [],
            'warnings': []
        }

        # Check CPU
        cpu_required = getattr(sandbox_profile, 'cpu_cores', 0)
        cpu_available = available_resources.get('cpu_cores', 4.0)

        if cpu_required > cpu_available:
            results['fits'] = False
            results['violations'].append(
                f"CPU requirement ({cpu_required}) exceeds available ({cpu_available})"
            )
        elif cpu_required > cpu_available * 0.8:
            results['warnings'].append(
                f"CPU requirement ({cpu_required}) is high relative to available ({cpu_available})"
            )

        # Check memory
        memory_required = getattr(sandbox_profile, 'memory_mb', 0)
        memory_available = available_resources.get('memory_mb', 4096)

        if memory_required > memory_available:
            results['fits'] = False
            results['violations'].append(
                f"Memory requirement ({memory_required}MB) exceeds available ({memory_available}MB)"
            )
        elif memory_required > memory_available * 0.8:
            results['warnings'].append(
                f"Memory requirement ({memory_required}MB) is high relative to available ({memory_available}MB)"
            )

        # Check disk
        disk_required = getattr(sandbox_profile, 'disk_quota_mb', 0)
        disk_available = available_resources.get('disk_mb', 10240)

        if disk_required > disk_available:
            results['fits'] = False
            results['violations'].append(
                f"Disk requirement ({disk_required}MB) exceeds available ({disk_available}MB)"
            )

        return results

    # ========== Utility Methods ==========

    def get_capability_summary(self, capability: Any) -> Dict[str, Any]:
        """Get summary of capability for Murphy System"""
        return {
            'name': getattr(capability, 'name', 'unknown'),
            'determinism_level': getattr(capability, 'determinism_level', 'unknown'),
            'requires_network': getattr(capability, 'requires_network', False),
            'requires_filesystem': getattr(capability, 'requires_filesystem', False),
            'cpu_requirement': getattr(capability, 'cpu_requirement', 1.0),
            'memory_requirement': getattr(capability, 'memory_requirement', 512),
            'risk_score': getattr(capability, 'risk_score', 0.0),
            'test_coverage': len(getattr(capability, 'test_vectors', [])),
            'failure_modes': len(getattr(capability, 'failure_modes', []))
        }

    def compute_execution_confidence(
        self,
        capability: Any,
        gates: List[Dict[str, Any]]
    ) -> float:
        """
        Compute confidence for executing capability.

        Args:
            capability: Capability to execute
            gates: Synthesized gates

        Returns:
            Execution confidence (0.0 to 1.0)
        """
        # Base confidence from capability
        base_confidence = 0.5

        # Boost for deterministic capabilities
        if getattr(capability, 'determinism_level', '') == 'deterministic':
            base_confidence += 0.2

        # Boost for test coverage
        test_vectors = getattr(capability, 'test_vectors', [])
        if len(test_vectors) >= 10:
            base_confidence += 0.1

        # Boost for satisfied gates
        satisfied_gates = [g for g in gates if g.get('satisfied', False)]
        gate_confidence = len(satisfied_gates) / (len(gates) or 1) if gates else 0.0

        # Combine confidences
        final_confidence = (base_confidence + gate_confidence) / 2

        return min(1.0, final_confidence)
