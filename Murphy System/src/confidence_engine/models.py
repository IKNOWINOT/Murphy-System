"""
Core data models for Confidence Engine
Defines artifact graphs, verification evidence, trust models, and state structures
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of artifacts in the graph"""
    HYPOTHESIS = "hypothesis"
    FACT = "fact"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    PLAN = "plan"
    VERIFICATION = "verification"


class ArtifactSource(Enum):
    """Sources of artifacts"""
    LLM = "llm"
    HUMAN = "human"
    API = "api"
    COMPUTE_PLANE = "compute_plane"
    SWARM = "swarm"


class VerificationResult(Enum):
    """Verification outcomes"""
    PASS = "pass"
    FAIL = "fail"
    UNCERTAIN = "uncertain"


class AuthorityBand(Enum):
    """Authority levels based on confidence"""
    ASK_ONLY = "ask_only"          # c < 0.3
    GENERATE = "generate"           # 0.3 <= c < 0.5
    PROPOSE = "propose"             # 0.5 <= c < 0.7
    NEGOTIATE = "negotiate"         # 0.7 <= c < 0.85
    EXECUTE = "execute"             # c >= 0.85


class Phase(Enum):
    """System phases"""
    EXPAND = "expand"
    TYPE = "type"
    ENUMERATE = "enumerate"
    CONSTRAIN = "constrain"
    COLLAPSE = "collapse"
    BIND = "bind"
    EXECUTE = "execute"

    @property
    def confidence_threshold(self) -> float:
        """Minimum confidence to advance from this phase"""
        thresholds = {
            Phase.EXPAND: 0.3,
            Phase.TYPE: 0.5,
            Phase.ENUMERATE: 0.6,
            Phase.CONSTRAIN: 0.65,
            Phase.COLLAPSE: 0.7,
            Phase.BIND: 0.75,
            Phase.EXECUTE: 0.85
        }
        return thresholds[self]

    @property
    def weights(self) -> tuple[float, float]:
        """(w_g, w_d) weights for generative vs deterministic"""
        weights_map = {
            Phase.EXPAND: (0.9, 0.1),
            Phase.TYPE: (0.8, 0.2),
            Phase.ENUMERATE: (0.7, 0.3),
            Phase.CONSTRAIN: (0.5, 0.5),
            Phase.COLLAPSE: (0.3, 0.7),
            Phase.BIND: (0.2, 0.8),
            Phase.EXECUTE: (0.1, 0.9)
        }
        return weights_map[self]


@dataclass
class ArtifactNode:
    """
    Node in the artifact graph
    Represents a piece of knowledge, decision, or constraint
    """
    id: str
    type: ArtifactType
    source: ArtifactSource
    content: Dict[str, Any]
    confidence_weight: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate ID if not provided"""
        if not self.id:
            content_str = str(self.content)
            self.id = hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'source': self.source.value,
            'content': self.content,
            'confidence_weight': self.confidence_weight,
            'dependencies': self.dependencies,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ArtifactGraph:
    """
    DAG of artifacts
    Maintains relationships and validates structure
    """
    nodes: Dict[str, ArtifactNode] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # node_id -> [dependent_ids]

    def add_node(self, node: ArtifactNode) -> None:
        """Add node to graph"""
        self.nodes[node.id] = node
        if node.id not in self.edges:
            self.edges[node.id] = []

        # Add edges from dependencies
        for dep_id in node.dependencies:
            if dep_id not in self.edges:
                self.edges[dep_id] = []
            if node.id not in self.edges[dep_id]:
                self.edges[dep_id].append(node.id)

    def get_node(self, node_id: str) -> Optional[ArtifactNode]:
        """Get node by ID"""
        return self.nodes.get(node_id)

    def get_dependencies(self, node_id: str) -> List[ArtifactNode]:
        """Get all dependencies of a node"""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[dep_id] for dep_id in node.dependencies if dep_id in self.nodes]

    def get_dependents(self, node_id: str) -> List[ArtifactNode]:
        """Get all nodes that depend on this node"""
        dependent_ids = self.edges.get(node_id, [])
        return [self.nodes[dep_id] for dep_id in dependent_ids if dep_id in self.nodes]

    def is_dag(self) -> bool:
        """Check if graph is a DAG (no cycles)"""
        visited = set()
        rec_stack = set()

        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            for dependent_id in self.edges.get(node_id, []):
                if dependent_id not in visited:
                    if has_cycle(dependent_id):
                        return True
                elif dependent_id in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        for node_id in self.nodes:
            if node_id not in visited:
                if has_cycle(node_id):
                    return False

        return True

    def get_roots(self) -> List[ArtifactNode]:
        """Get root nodes (no dependencies)"""
        return [node for node in self.nodes.values() if not node.dependencies]

    def get_leaves(self) -> List[ArtifactNode]:
        """Get leaf nodes (no dependents)"""
        return [node for node_id, node in self.nodes.items()
                if not self.edges.get(node_id, [])]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'nodes': {node_id: node.to_dict() for node_id, node in self.nodes.items()},
            'edges': self.edges,
            'is_dag': self.is_dag(),
            'node_count': len(self.nodes),
            'edge_count': sum(len(deps) for deps in self.edges.values())
        }


@dataclass
class VerificationEvidence:
    """
    Evidence from deterministic verification
    Links artifacts to verification results
    """
    artifact_id: str
    result: VerificationResult
    stability_score: float  # How stable is this result? [0, 1]
    confidence_boost: float = 0.0  # How much does this boost confidence?
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'artifact_id': self.artifact_id,
            'result': self.result.value,
            'stability_score': self.stability_score,
            'confidence_boost': self.confidence_boost,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }


@dataclass
class SourceTrust:
    """
    Trust model for artifact sources
    Tracks reliability and volatility
    """
    source_id: str
    source_type: ArtifactSource
    trust_weight: float  # [0, 1] - how much to trust this source
    volatility: float  # [0, 1] - how much does trust vary?
    success_count: int = 0
    failure_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def reliability(self) -> float:
        """Calculate reliability from success/failure ratio"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral
        return self.success_count / total

    def update_trust(self, success: bool) -> None:
        """Update trust based on outcome"""
        if success:
            self.success_count += 1
            # Increase trust slightly
            self.trust_weight = min(1.0, self.trust_weight + 0.05)
        else:
            self.failure_count += 1
            # Decrease trust
            self.trust_weight = max(0.0, self.trust_weight - 0.1)

        self.last_updated = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'source_id': self.source_id,
            'source_type': self.source_type.value,
            'trust_weight': self.trust_weight,
            'volatility': self.volatility,
            'reliability': self.reliability,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class TrustModel:
    """
    Complete trust model for all sources
    """
    sources: Dict[str, SourceTrust] = field(default_factory=dict)

    def get_trust(self, source_id: str) -> float:
        """Get trust weight for a source"""
        source = self.sources.get(source_id)
        return source.trust_weight if source else 0.5  # Default neutral

    def add_source(self, source: SourceTrust) -> None:
        """Add or update source trust"""
        self.sources[source.source_id] = source

    def update_source(self, source_id: str, success: bool) -> None:
        """Update source trust based on outcome"""
        if source_id in self.sources:
            self.sources[source_id].update_trust(success)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'sources': {sid: src.to_dict() for sid, src in self.sources.items()},
            'source_count': len(self.sources)
        }


@dataclass
class ConfidenceState:
    """
    Complete confidence state at time t
    """
    confidence: float  # c_t ∈ [0, 1]
    generative_score: float  # G(x_t)
    deterministic_score: float  # D(x_t)
    epistemic_instability: float  # H(x_t)
    phase: Phase
    timestamp: datetime = field(default_factory=datetime.now)

    # Component scores
    hypothesis_coverage: float = 0.0
    decision_branching: float = 0.0
    question_quality: float = 0.0
    verified_artifacts: int = 0
    total_artifacts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'confidence': self.confidence,
            'generative_score': self.generative_score,
            'deterministic_score': self.deterministic_score,
            'epistemic_instability': self.epistemic_instability,
            'phase': self.phase.value,
            'timestamp': self.timestamp.isoformat(),
            'components': {
                'hypothesis_coverage': self.hypothesis_coverage,
                'decision_branching': self.decision_branching,
                'question_quality': self.question_quality,
                'verified_artifacts': self.verified_artifacts,
                'total_artifacts': self.total_artifacts
            }
        }


@dataclass
class AuthorityState:
    """
    Authority state derived from confidence
    """
    authority_band: AuthorityBand
    confidence: float
    can_execute: bool
    phase: Phase
    timestamp: datetime = field(default_factory=datetime.now)

    # Execution criteria
    gate_satisfaction: float = 0.0
    murphy_index: float = 0.0
    unknowns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'authority_band': self.authority_band.value,
            'confidence': self.confidence,
            'can_execute': self.can_execute,
            'phase': self.phase.value,
            'timestamp': self.timestamp.isoformat(),
            'execution_criteria': {
                'gate_satisfaction': self.gate_satisfaction,
                'murphy_index': self.murphy_index,
                'unknowns': self.unknowns
            }
        }
