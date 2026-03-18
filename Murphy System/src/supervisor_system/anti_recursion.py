"""
Anti-Recursion Protection

Prevents self-validation and circular dependencies in assumption validation.

Components:
- SelfValidationBlocker: Prevents agents from validating their own assumptions
- CircularDependencyDetector: Detects circular assumption chains
- ValidationSourceTracker: Tracks validation sources to prevent self-justification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

from .assumption_management import AssumptionRegistry
from .schemas import AssumptionArtifact, AssumptionBinding, ValidationEvidence

logger = logging.getLogger(__name__)


@dataclass
class ValidationAttempt:
    """Record of a validation attempt."""
    attempt_id: str
    assumption_id: str
    validator_id: str
    validator_type: str  # "agent", "supervisor", "deterministic", "external_api"
    timestamp: datetime
    blocked: bool
    block_reason: Optional[str] = None


class ValidationSourceTracker:
    """
    Tracks validation sources to prevent self-justification.

    Responsibilities:
    - Track who created each assumption
    - Track who validated each assumption
    - Detect self-validation attempts
    """

    def __init__(self):
        self._assumption_creators: Dict[str, str] = {}  # assumption_id -> creator_id
        self._assumption_validators: Dict[str, List[str]] = {}  # assumption_id -> [validator_ids]
        self._validation_attempts: List[ValidationAttempt] = []
        self._attempt_counter = 0

    def register_assumption_creator(self, assumption_id: str, creator_id: str) -> None:
        """Register who created an assumption."""
        self._assumption_creators[assumption_id] = creator_id
        logger.info(f"Registered creator {creator_id} for assumption {assumption_id}")

    def register_validation(self, assumption_id: str, validator_id: str) -> None:
        """Register who validated an assumption."""
        if assumption_id not in self._assumption_validators:
            self._assumption_validators[assumption_id] = []

        self._assumption_validators[assumption_id].append(validator_id)
        logger.info(f"Registered validator {validator_id} for assumption {assumption_id}")

    def is_self_validation(self, assumption_id: str, validator_id: str) -> bool:
        """Check if validation attempt is self-validation."""
        creator_id = self._assumption_creators.get(assumption_id)

        if creator_id is None:
            # Unknown creator, allow validation
            return False

        return creator_id == validator_id

    def record_validation_attempt(
        self,
        assumption_id: str,
        validator_id: str,
        validator_type: str,
        blocked: bool,
        block_reason: Optional[str] = None
    ) -> ValidationAttempt:
        """Record a validation attempt."""
        self._attempt_counter += 1

        attempt = ValidationAttempt(
            attempt_id=f"val-attempt-{self._attempt_counter:06d}",
            assumption_id=assumption_id,
            validator_id=validator_id,
            validator_type=validator_type,
            timestamp=datetime.now(timezone.utc),
            blocked=blocked,
            block_reason=block_reason
        )

        capped_append(self._validation_attempts, attempt)

        if blocked:
            logger.warning(
                f"Blocked validation attempt {attempt.attempt_id}: {block_reason}"
            )

        return attempt

    def get_validation_attempts(self, assumption_id: str) -> List[ValidationAttempt]:
        """Get all validation attempts for an assumption."""
        return [a for a in self._validation_attempts if a.assumption_id == assumption_id]

    def get_blocked_attempts(self) -> List[ValidationAttempt]:
        """Get all blocked validation attempts."""
        return [a for a in self._validation_attempts if a.blocked]


class SelfValidationBlocker:
    """
    Prevents agents from validating their own assumptions.

    CRITICAL SAFETY CONSTRAINT:
    - Agents CANNOT validate assumptions they created
    - Only external sources can validate assumptions

    Responsibilities:
    - Block self-validation attempts
    - Enforce external validation requirement
    - Track blocked attempts for audit
    """

    def __init__(self, source_tracker: ValidationSourceTracker):
        self.source_tracker = source_tracker

    def can_validate(
        self,
        assumption_id: str,
        validator_id: str,
        validator_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if validator can validate assumption.

        Returns (can_validate, block_reason)
        """
        # Check if self-validation
        if self.source_tracker.is_self_validation(assumption_id, validator_id):
            reason = f"Self-validation blocked: {validator_id} created assumption {assumption_id}"

            # Record blocked attempt
            self.source_tracker.record_validation_attempt(
                assumption_id,
                validator_id,
                validator_type,
                blocked=True,
                block_reason=reason
            )

            return False, reason

        # Allow validation
        self.source_tracker.record_validation_attempt(
            assumption_id,
            validator_id,
            validator_type,
            blocked=False
        )

        return True, None

    def validate_evidence(
        self,
        assumption_id: str,
        evidence: ValidationEvidence
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that evidence is not self-generated.

        Returns (is_valid, rejection_reason)
        """
        # Evidence must be external (enforced in schema)
        if not evidence.is_external:
            return False, "Evidence must be external (is_external=True)"

        # Check if evidence source is the assumption creator
        creator_id = self.source_tracker._assumption_creators.get(assumption_id)
        if creator_id and evidence.source == creator_id:
            return False, f"Evidence source {evidence.source} is the assumption creator"

        return True, None


class CircularDependencyDetector:
    """
    Detects circular dependencies in assumption chains.

    Example circular dependency:
    - Assumption A depends on Assumption B
    - Assumption B depends on Assumption C
    - Assumption C depends on Assumption A (CIRCULAR!)

    Responsibilities:
    - Build dependency graph
    - Detect cycles
    - Block circular validations
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self._dependencies: Dict[str, Set[str]] = {}  # assumption_id -> {dependency_ids}

    def add_dependency(self, assumption_id: str, depends_on: str) -> None:
        """Add a dependency relationship."""
        if assumption_id not in self._dependencies:
            self._dependencies[assumption_id] = set()

        self._dependencies[assumption_id].add(depends_on)
        logger.info(f"Added dependency: {assumption_id} depends on {depends_on}")

    def has_circular_dependency(self, assumption_id: str) -> Tuple[bool, Optional[List[str]]]:
        """
        Check if assumption has circular dependency.

        Returns (has_cycle, cycle_path)
        """
        visited = set()
        path = []

        def dfs(current: str) -> bool:
            if current in path:
                # Found cycle
                cycle_start = path.index(current)
                return True

            if current in visited:
                return False

            visited.add(current)
            path.append(current)

            # Check dependencies
            for dependency in self._dependencies.get(current, set()):
                if dfs(dependency):
                    return True

            path.pop()
            return False

        has_cycle = dfs(assumption_id)

        if has_cycle:
            logger.warning(f"Circular dependency detected: {' -> '.join(path)}")
            return True, path

        return False, None

    def can_add_dependency(
        self,
        assumption_id: str,
        depends_on: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if dependency can be added without creating cycle.

        Returns (can_add, rejection_reason)
        """
        # Temporarily add dependency
        if assumption_id not in self._dependencies:
            self._dependencies[assumption_id] = set()

        original_deps = self._dependencies[assumption_id].copy()
        self._dependencies[assumption_id].add(depends_on)

        # Check for cycle
        has_cycle, cycle_path = self.has_circular_dependency(assumption_id)

        if has_cycle:
            # Restore original dependencies
            self._dependencies[assumption_id] = original_deps

            reason = f"Would create circular dependency: {' -> '.join(cycle_path)}"
            return False, reason

        # Dependency is safe
        return True, None

    def get_dependency_chain(self, assumption_id: str) -> List[str]:
        """Get full dependency chain for assumption."""
        chain = []
        visited = set()

        def dfs(current: str):
            if current in visited:
                return

            visited.add(current)
            chain.append(current)

            for dependency in self._dependencies.get(current, set()):
                dfs(dependency)

        dfs(assumption_id)
        return chain

    def get_statistics(self) -> Dict:
        """Get dependency graph statistics."""
        total_assumptions = len(self._dependencies)
        total_dependencies = sum(len(deps) for deps in self._dependencies.values())

        # Find assumptions with most dependencies
        max_deps = 0
        max_dep_assumption = None
        for assumption_id, deps in self._dependencies.items():
            if len(deps) > max_deps:
                max_deps = len(deps)
                max_dep_assumption = assumption_id

        return {
            "total_assumptions": total_assumptions,
            "total_dependencies": total_dependencies,
            "max_dependencies": max_deps,
            "max_dep_assumption": max_dep_assumption
        }


class AntiRecursionSystem:
    """
    Complete anti-recursion protection system.

    Combines all anti-recursion components to provide comprehensive protection
    against self-validation and circular dependencies.
    """

    def __init__(self, registry: AssumptionRegistry):
        self.registry = registry
        self.source_tracker = ValidationSourceTracker()
        self.self_validation_blocker = SelfValidationBlocker(self.source_tracker)
        self.circular_dependency_detector = CircularDependencyDetector(registry)

    def register_assumption(
        self,
        assumption_id: str,
        creator_id: str,
        dependencies: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Register a new assumption with anti-recursion tracking.

        Returns (success, error_message)
        """
        # Register creator
        self.source_tracker.register_assumption_creator(assumption_id, creator_id)

        # Add dependencies if provided
        if dependencies:
            for dep_id in dependencies:
                can_add, reason = self.circular_dependency_detector.can_add_dependency(
                    assumption_id, dep_id
                )
                if not can_add:
                    return False, reason

        return True, None

    def validate_assumption(
        self,
        assumption_id: str,
        validator_id: str,
        validator_type: str,
        evidence: ValidationEvidence
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an assumption with anti-recursion checks.

        Returns (can_validate, rejection_reason)
        """
        # Check self-validation
        can_validate, reason = self.self_validation_blocker.can_validate(
            assumption_id, validator_id, validator_type
        )
        if not can_validate:
            return False, reason

        # Check evidence validity
        is_valid, reason = self.self_validation_blocker.validate_evidence(
            assumption_id, evidence
        )
        if not is_valid:
            return False, reason

        # Check circular dependencies
        has_cycle, cycle_path = self.circular_dependency_detector.has_circular_dependency(
            assumption_id
        )
        if has_cycle:
            return False, f"Circular dependency detected: {' -> '.join(cycle_path)}"

        # All checks passed
        self.source_tracker.register_validation(assumption_id, validator_id)
        return True, None

    def get_statistics(self) -> Dict:
        """Get anti-recursion system statistics."""
        return {
            "source_tracker": {
                "total_attempts": len(self.source_tracker._validation_attempts),
                "blocked_attempts": len(self.source_tracker.get_blocked_attempts())
            },
            "dependency_detector": self.circular_dependency_detector.get_statistics()
        }
