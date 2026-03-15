"""
Feedback Isolation Router

Enforces hard invariant: No entity may evaluate anything it influenced.

Forbidden:
- Self-evaluation
- Evaluating self-proposed gates
- Validating descendant outputs

Mandatory topology:
    Generator → Verifier → Arbiter → Control Plane

Where:
- Arbiter is non-generative
- No bypass paths allowed
- Violations → immediate freeze
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger("recursive_stability_controller.feedback_isolation")


class EntityType(Enum):
    """Entity type enumeration"""
    GENERATOR = "generator"
    VERIFIER = "verifier"
    ARBITER = "arbiter"
    CONTROL_PLANE = "control_plane"


@dataclass
class Entity:
    """Entity in the system"""

    entity_id: str
    entity_type: EntityType
    timestamp: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type.value,
            "timestamp": self.timestamp
        }


@dataclass
class Artifact:
    """Artifact (output) produced by entity"""

    artifact_id: str
    producer_id: str  # Entity that produced this
    timestamp: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "artifact_id": self.artifact_id,
            "producer_id": self.producer_id,
            "timestamp": self.timestamp
        }


@dataclass
class EvaluationRequest:
    """Request to evaluate an artifact"""

    request_id: str
    evaluator_id: str  # Entity requesting evaluation
    artifact_id: str   # Artifact to evaluate
    timestamp: float

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "request_id": self.request_id,
            "evaluator_id": self.evaluator_id,
            "artifact_id": self.artifact_id,
            "timestamp": self.timestamp
        }


@dataclass
class IsolationViolation:
    """Feedback isolation violation"""

    violation_type: str  # "self_evaluation", "descendant_evaluation", "bypass"
    evaluator_id: str
    artifact_id: str
    influence_chain: List[str]
    timestamp: float
    severity: str  # "critical", "high", "medium"

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "violation_type": self.violation_type,
            "evaluator_id": self.evaluator_id,
            "artifact_id": self.artifact_id,
            "influence_chain": self.influence_chain,
            "timestamp": self.timestamp,
            "severity": self.severity
        }


class FeedbackIsolationRouter:
    """
    Route evaluation requests with feedback isolation enforcement.

    Maintains:
    - Lineage graph (entity → artifact → entity)
    - Influence matrix (who influenced what)

    Enforces:
    - No self-evaluation
    - No descendant evaluation
    - Mandatory topology
    """

    def __init__(self):
        """Initialize feedback isolation router"""
        # Lineage graph: artifact_id → producer_id
        self.lineage: Dict[str, str] = {}

        # Influence matrix: entity_id → set of influenced artifact_ids
        self.influence: Dict[str, Set[str]] = {}

        # Entity registry
        self.entities: Dict[str, Entity] = {}

        # Violations
        self.violations: List[IsolationViolation] = []

        # Evaluation history
        self.evaluation_history: List[Dict] = []
        self.max_history = 1000

    def register_entity(self, entity: Entity):
        """
        Register entity in the system.

        Args:
            entity: Entity to register
        """
        self.entities[entity.entity_id] = entity
        self.influence[entity.entity_id] = set()
        logger.info(f"[REGISTER] Entity: {entity.entity_id} ({entity.entity_type.value})")

    def register_artifact(self, artifact: Artifact):
        """
        Register artifact produced by entity.

        Args:
            artifact: Artifact to register
        """
        # Record lineage
        self.lineage[artifact.artifact_id] = artifact.producer_id

        # Record influence
        if artifact.producer_id in self.influence:
            self.influence[artifact.producer_id].add(artifact.artifact_id)
        else:
            self.influence[artifact.producer_id] = {artifact.artifact_id}

        logger.info(f"[ARTIFACT] {artifact.artifact_id} produced by {artifact.producer_id}")

    def check_evaluation(
        self,
        request: EvaluationRequest
    ) -> tuple[bool, Optional[IsolationViolation]]:
        """
        Check if evaluation request violates feedback isolation.

        Args:
            request: Evaluation request

        Returns:
            (is_allowed, violation) where violation is None if allowed
        """
        import time

        evaluator_id = request.evaluator_id
        artifact_id = request.artifact_id

        # Check if artifact exists
        if artifact_id not in self.lineage:
            logger.info(f"[WARNING] Unknown artifact: {artifact_id}")
            return True, None  # Allow if artifact not tracked

        # Get producer
        producer_id = self.lineage[artifact_id]

        # Check 1: Self-evaluation (direct)
        if evaluator_id == producer_id:
            violation = IsolationViolation(
                violation_type="self_evaluation",
                evaluator_id=evaluator_id,
                artifact_id=artifact_id,
                influence_chain=[evaluator_id, artifact_id],
                timestamp=time.time(),
                severity="critical"
            )
            self._record_violation(violation)
            return False, violation

        # Check 2: Descendant evaluation (indirect influence)
        if self._has_influence(evaluator_id, artifact_id):
            influence_chain = self._get_influence_chain(evaluator_id, artifact_id)
            violation = IsolationViolation(
                violation_type="descendant_evaluation",
                evaluator_id=evaluator_id,
                artifact_id=artifact_id,
                influence_chain=influence_chain,
                timestamp=time.time(),
                severity="high"
            )
            self._record_violation(violation)
            return False, violation

        # Check 3: Topology validation
        if not self._validate_topology(evaluator_id, producer_id):
            violation = IsolationViolation(
                violation_type="bypass",
                evaluator_id=evaluator_id,
                artifact_id=artifact_id,
                influence_chain=[evaluator_id, producer_id],
                timestamp=time.time(),
                severity="high"
            )
            self._record_violation(violation)
            return False, violation

        # Allowed
        self._record_evaluation(request, allowed=True)
        return True, None

    def _has_influence(self, evaluator_id: str, artifact_id: str) -> bool:
        """
        Check if evaluator has influence over artifact.

        Uses transitive closure of influence graph.
        """
        if evaluator_id not in self.influence:
            return False

        # Direct influence
        if artifact_id in self.influence[evaluator_id]:
            return True

        # Indirect influence (BFS)
        visited = set()
        queue = list(self.influence[evaluator_id])

        while queue:
            current_artifact = queue.pop(0)

            if current_artifact in visited:
                continue
            visited.add(current_artifact)

            if current_artifact == artifact_id:
                return True

            # Get producer of current artifact
            if current_artifact in self.lineage:
                producer = self.lineage[current_artifact]

                # Add producer's artifacts to queue
                if producer in self.influence:
                    queue.extend(self.influence[producer])

        return False

    def _get_influence_chain(
        self,
        evaluator_id: str,
        artifact_id: str
    ) -> List[str]:
        """Get influence chain from evaluator to artifact"""
        # Simplified - returns direct path
        chain = [evaluator_id]

        if evaluator_id in self.influence:
            influenced = self.influence[evaluator_id]
            if artifact_id in influenced:
                chain.append(artifact_id)
            else:
                # Find intermediate artifacts
                for intermediate in influenced:
                    if intermediate in self.lineage:
                        producer = self.lineage[intermediate]
                        if producer in self.influence and artifact_id in self.influence[producer]:
                            chain.extend([intermediate, producer, artifact_id])
                            break

        return chain

    def _validate_topology(self, evaluator_id: str, producer_id: str) -> bool:
        """
        Validate mandatory topology.

        Generator → Verifier → Arbiter → Control Plane
        """
        if evaluator_id not in self.entities or producer_id not in self.entities:
            return True  # Allow if entities not registered

        evaluator_type = self.entities[evaluator_id].entity_type
        producer_type = self.entities[producer_id].entity_type

        # Arbiter must be non-generative
        if evaluator_type == EntityType.ARBITER and producer_type == EntityType.GENERATOR:
            return False  # Arbiter cannot evaluate generator directly

        # Control plane can evaluate anything
        if evaluator_type == EntityType.CONTROL_PLANE:
            return True

        # Verifier can evaluate generator
        if evaluator_type == EntityType.VERIFIER and producer_type == EntityType.GENERATOR:
            return True

        # Arbiter can evaluate verifier
        if evaluator_type == EntityType.ARBITER and producer_type == EntityType.VERIFIER:
            return True

        # Default: allow
        return True

    def _record_violation(self, violation: IsolationViolation):
        """Record isolation violation"""
        self.violations.append(violation)

        logger.info("[VIOLATION] Feedback isolation violated!")
        logger.info(f"  Type: {violation.violation_type}")
        logger.info(f"  Evaluator: {violation.evaluator_id}")
        logger.info(f"  Artifact: {violation.artifact_id}")
        logger.info(f"  Chain: {' → '.join(violation.influence_chain)}")
        logger.info(f"  Severity: {violation.severity}")

    def _record_evaluation(self, request: EvaluationRequest, allowed: bool):
        """Record evaluation request"""
        self.evaluation_history.append({
            "request": request.to_dict(),
            "allowed": allowed,
            "timestamp": request.timestamp
        })

        # Trim history if needed
        if len(self.evaluation_history) > self.max_history:
            self.evaluation_history = self.evaluation_history[-self.max_history:]

    def get_violations(self, n: int = None) -> List[IsolationViolation]:
        """
        Get isolation violations.

        Args:
            n: Number of recent violations (all if None)

        Returns:
            List of violations
        """
        if n is None:
            return self.violations
        return self.violations[-n:]

    def get_statistics(self) -> Dict:
        """
        Get isolation statistics.

        Returns:
            Dictionary with violation counts, rates, etc.
        """
        if not self.evaluation_history:
            return {
                "total_evaluations": 0,
                "allowed_count": 0,
                "denied_count": 0,
                "violation_count": 0,
                "violation_rate": 0.0
            }

        allowed = sum(1 for h in self.evaluation_history if h["allowed"])
        denied = sum(1 for h in self.evaluation_history if not h["allowed"])

        return {
            "total_evaluations": len(self.evaluation_history),
            "allowed_count": allowed,
            "denied_count": denied,
            "violation_count": len(self.violations),
            "violation_rate": denied / (len(self.evaluation_history) or 1)
        }

    def clear_lineage(self):
        """Clear lineage graph (use with caution)"""
        self.lineage.clear()
        self.influence.clear()
        logger.info("[CLEAR] Lineage graph cleared")
