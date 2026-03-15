"""
Memory & Artifact Subsystem (MAS)
Memory stratified by authority, not content

Core Principle:
No information may gain authority merely by existing.
Only verified artifacts may influence execution.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MemoryPlane(Enum):
    """Four memory planes with unidirectional promotion"""
    SANDBOX = "sandbox"  # Free exploration, no consequences
    WORKING = "working"  # Structured candidates
    CONTROL = "control"  # Governance state
    EXECUTION = "execution"  # Irreversible commitments


class ArtifactState(Enum):
    """Artifact lifecycle states"""
    DRAFT = "draft"  # In sandbox
    STRUCTURED = "structured"  # In working memory
    VERIFIED = "verified"  # Passed verification
    BOUND = "bound"  # Ready for execution
    EXECUTED = "executed"  # Committed to execution memory


class VerificationSource(Enum):
    """Sources for verification"""
    API = "api"
    STATIC_KB = "static_kb"
    LEDGER = "ledger"
    REGULATORY_DB = "regulatory_db"
    USER_CONFIRMATION = "user_confirmation"
    DETERMINISTIC_CHECK = "deterministic_check"


@dataclass
class Artifact:
    """
    Typed artifact with full provenance

    Artifacts move through explicit states:
    Draft → Structured → Verified → Bound → Executed
    """
    id: str
    phase: str
    artifact_type: str
    content: Any
    dependencies: List[str]
    verification_status: str
    confidence_delta: float
    provenance: Dict[str, Any]
    state: ArtifactState
    memory_plane: MemoryPlane
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'phase': self.phase,
            'artifact_type': self.artifact_type,
            'content': self.content,
            'dependencies': self.dependencies,
            'verification_status': self.verification_status,
            'confidence_delta': self.confidence_delta,
            'provenance': self.provenance,
            'state': self.state.value,
            'memory_plane': self.memory_plane.value,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


@dataclass
class VerificationResult:
    """Result from verification interface layer"""
    artifact_id: str
    source: VerificationSource
    trust_weighted_score: float
    contradictions: List[str]
    confidence_delta: float
    timestamp: float
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlState:
    """Control memory state"""
    active_gates: List[str]
    confidence: float
    phase: str
    authority_band: float
    murphy_index: float
    trust_scores: Dict[str, float]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'active_gates': self.active_gates,
            'confidence': self.confidence,
            'phase': self.phase,
            'authority_band': self.authority_band,
            'murphy_index': self.murphy_index,
            'trust_scores': self.trust_scores,
            'timestamp': self.timestamp
        }


@dataclass
class ExecutionRecord:
    """Immutable execution record"""
    id: str
    artifact_ids: List[str]
    content: Any
    signature: str  # Cryptographic signature
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_signature(self) -> str:
        """Compute cryptographic signature"""
        data = json.dumps({
            'id': self.id,
            'artifact_ids': self.artifact_ids,
            'content': str(self.content),
            'timestamp': self.timestamp
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


class SandboxMemory:
    """
    PLANE 1: Sandbox Memory

    Purpose: Free exploration, no consequences
    Properties: high-volume, low-cost, auto-expiring, never authoritative

    Access Rules:
    - Writable by all agents
    - Readable by all swarms
    - Never read by execution

    Authority Impact:
    - Contributes only to G(x) (generative adequacy)
    - Cannot increase confidence directly
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: float = 3600):
        self.artifacts: Dict[str, Artifact] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def write(self, artifact: Artifact) -> str:
        """Write to sandbox (always allowed)"""
        artifact.memory_plane = MemoryPlane.SANDBOX
        artifact.state = ArtifactState.DRAFT
        self.artifacts[artifact.id] = artifact

        # Auto-expire old artifacts
        self._expire_old()

        # Enforce size limit
        if len(self.artifacts) > self.max_size:
            self._evict_oldest()

        return artifact.id

    def read(self, artifact_id: str) -> Optional[Artifact]:
        """Read from sandbox"""
        return self.artifacts.get(artifact_id)

    def read_all(self) -> List[Artifact]:
        """Read all sandbox artifacts"""
        return list(self.artifacts.values())

    def _expire_old(self):
        """Remove expired artifacts"""
        current_time = datetime.now(timezone.utc).timestamp()
        expired = [
            aid for aid, artifact in self.artifacts.items()
            if current_time - artifact.timestamp > self.ttl_seconds
        ]
        for aid in expired:
            del self.artifacts[aid]

    def _evict_oldest(self):
        """Evict oldest artifacts to maintain size limit"""
        sorted_artifacts = sorted(
            self.artifacts.items(),
            key=lambda x: x[1].timestamp
        )
        to_remove = len(self.artifacts) - self.max_size
        for aid, _ in sorted_artifacts[:to_remove]:
            del self.artifacts[aid]

    def reset(self):
        """Reset sandbox (for new tasks)"""
        self.artifacts.clear()


class WorkingArtifactMemory:
    """
    PLANE 2: Working Artifact Memory

    Purpose: Structured candidate outputs

    Promotion Rule:
    Artifacts enter WAM only after:
    - Phase legality
    - Basic coherence checks

    Access Rules:
    - Writable by agents
    - Readable by control layer
    - Eligible for verification

    Authority Impact:
    - Can increase G(x)
    - Can increase D(x) only after verification
    """

    def __init__(self):
        self.artifacts: Dict[str, Artifact] = {}
        self.by_phase: Dict[str, List[str]] = {}
        self.by_type: Dict[str, List[str]] = {}

    def promote_from_sandbox(
        self,
        artifact: Artifact,
        phase_legal: bool,
        coherent: bool
    ) -> Optional[str]:
        """
        Promote artifact from sandbox to working memory

        Requires:
        - Phase legality
        - Basic coherence
        """
        if not phase_legal:
            return None
        if not coherent:
            return None

        # Update state and plane
        artifact.memory_plane = MemoryPlane.WORKING
        artifact.state = ArtifactState.STRUCTURED

        # Store
        self.artifacts[artifact.id] = artifact

        # Index by phase
        if artifact.phase not in self.by_phase:
            self.by_phase[artifact.phase] = []
        self.by_phase[artifact.phase].append(artifact.id)

        # Index by type
        if artifact.artifact_type not in self.by_type:
            self.by_type[artifact.artifact_type] = []
        self.by_type[artifact.artifact_type].append(artifact.id)

        return artifact.id

    def read(self, artifact_id: str) -> Optional[Artifact]:
        """Read artifact"""
        return self.artifacts.get(artifact_id)

    def read_by_phase(self, phase: str) -> List[Artifact]:
        """Read artifacts by phase"""
        artifact_ids = self.by_phase.get(phase, [])
        return [self.artifacts[aid] for aid in artifact_ids if aid in self.artifacts]

    def read_by_type(self, artifact_type: str) -> List[Artifact]:
        """Read artifacts by type"""
        artifact_ids = self.by_type.get(artifact_type, [])
        return [self.artifacts[aid] for aid in artifact_ids if aid in self.artifacts]

    def mark_verified(self, artifact_id: str, verification: VerificationResult):
        """Mark artifact as verified"""
        if artifact_id in self.artifacts:
            artifact = self.artifacts[artifact_id]
            artifact.state = ArtifactState.VERIFIED
            artifact.verification_status = 'verified'
            artifact.confidence_delta += verification.confidence_delta
            artifact.metadata['verification'] = {
                'source': verification.source.value,
                'score': verification.trust_weighted_score,
                'timestamp': verification.timestamp
            }

    def invalidate(self, artifact_id: str):
        """Invalidate artifact (control layer command)"""
        if artifact_id in self.artifacts:
            artifact = self.artifacts[artifact_id]
            artifact.verification_status = 'invalidated'
            artifact.confidence_delta = 0.0


class ControlMemory:
    """
    PLANE 3: Control Memory

    Purpose: Governance state and safety guarantees

    Access Rules:
    - Writable only by Gate Compiler + Confidence Engine
    - Readable by agents (for constraint awareness)
    - Immutable to sandbox

    Authority Impact:
    - Fully authoritative for what may proceed
    """

    def __init__(self):
        self.current_state: Optional[ControlState] = None
        self.state_history: List[ControlState] = []
        self.active_gates: Set[str] = set()
        self.confidence_history: List[float] = []
        self.murphy_history: List[float] = []
        self.authority_history: List[float] = []
        self.trust_scores: Dict[str, float] = {}

        # Invariant sets (protected)
        self.invariants: Set[str] = {
            'confidence_equation',
            'authority_mapping',
            'gate_compiler',
            'verification_channels'
        }

    def write_state(
        self,
        writer: str,
        state: ControlState
    ) -> bool:
        """
        Write control state

        Only allowed by:
        - Gate Compiler
        - Confidence Engine
        """
        allowed_writers = {'gate_compiler', 'confidence_engine', 'authority_controller'}

        if writer not in allowed_writers:
            return False

        # Store current state
        self.current_state = state
        self.state_history.append(state)

        # Update histories
        self.confidence_history.append(state.confidence)
        self.murphy_history.append(state.murphy_index)
        self.authority_history.append(state.authority_band)

        # Update active gates
        self.active_gates = set(state.active_gates)

        # Update trust scores
        self.trust_scores = state.trust_scores.copy()

        return True

    def read_state(self) -> Optional[ControlState]:
        """Read current control state"""
        return self.current_state

    def read_gates(self) -> Set[str]:
        """Read active gates"""
        return self.active_gates.copy()

    def read_confidence(self) -> float:
        """Read current confidence"""
        return self.current_state.confidence if self.current_state else 0.0

    def read_murphy_index(self) -> float:
        """Read current Murphy index"""
        return self.current_state.murphy_index if self.current_state else 0.0

    def read_authority(self) -> float:
        """Read current authority band"""
        return self.current_state.authority_band if self.current_state else 0.0

    def check_invariant_protection(self, target: str) -> bool:
        """Check if target is a protected invariant"""
        return any(inv in target.lower() for inv in self.invariants)


class ExecutionMemory:
    """
    PLANE 4: Execution Memory

    Purpose: Irreversible commitments and system outputs

    Properties:
    - Append-only
    - Cryptographically signed
    - Legally binding if applicable

    Promotion Rule:
    Only allowed when:
    - a_t >= Bind threshold
    - M_t minimal

    Access Rules:
    - Writable only by execution layer
    - Readable by control + audit
    """

    def __init__(self, bind_threshold: float = 0.8, murphy_threshold: float = 0.3):
        self.records: List[ExecutionRecord] = []
        self.by_id: Dict[str, ExecutionRecord] = {}
        self.bind_threshold = bind_threshold
        self.murphy_threshold = murphy_threshold

    def commit(
        self,
        artifact_ids: List[str],
        content: Any,
        authority: float,
        murphy_index: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ExecutionRecord]:
        """
        Commit to execution memory

        Requires:
        - authority >= bind_threshold
        - murphy_index <= murphy_threshold
        """
        # Check thresholds
        if authority < self.bind_threshold:
            return None
        if murphy_index > self.murphy_threshold:
            return None

        # Create record
        record = ExecutionRecord(
            id=f"exec_{len(self.records)}_{datetime.now(timezone.utc).timestamp()}",
            artifact_ids=artifact_ids,
            content=content,
            signature="",  # Will be computed
            timestamp=datetime.now(timezone.utc).timestamp(),
            metadata=metadata or {}
        )

        # Compute signature
        record.signature = record.compute_signature()

        # Append (immutable)
        self.records.append(record)
        self.by_id[record.id] = record

        return record

    def read(self, record_id: str) -> Optional[ExecutionRecord]:
        """Read execution record"""
        return self.by_id.get(record_id)

    def read_all(self) -> List[ExecutionRecord]:
        """Read all execution records"""
        return self.records.copy()

    def verify_signature(self, record_id: str) -> bool:
        """Verify record signature"""
        record = self.by_id.get(record_id)
        if not record:
            return False

        expected_signature = record.compute_signature()
        return record.signature == expected_signature


class VerificationInterfaceLayer:
    """
    Bridge between memory and reality

    Inputs: Artifacts from WAM
    Outputs: Verification results to Control Memory

    Sources:
    - APIs
    - Static KB
    - Ledgers
    - Regulatory DBs
    - User confirmations
    """

    def __init__(self):
        self.verification_history: List[VerificationResult] = []
        self.trust_weights = {
            VerificationSource.DETERMINISTIC_CHECK: 1.0,
            VerificationSource.STATIC_KB: 0.9,
            VerificationSource.REGULATORY_DB: 0.95,
            VerificationSource.API: 0.8,
            VerificationSource.LEDGER: 0.85,
            VerificationSource.USER_CONFIRMATION: 0.7
        }

    def verify_artifact(
        self,
        artifact: Artifact,
        source: VerificationSource,
        evidence: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Verify artifact against source

        Returns verification result with trust-weighted score
        """
        # Perform verification (simplified)
        trust_weight = self.trust_weights.get(source, 0.5)

        # Check for contradictions
        contradictions = self._check_contradictions(artifact, evidence or {})

        # Compute confidence delta
        if contradictions:
            confidence_delta = -0.2 * len(contradictions)
        else:
            confidence_delta = 0.1 * trust_weight

        # Create result
        result = VerificationResult(
            artifact_id=artifact.id,
            source=source,
            trust_weighted_score=trust_weight if not contradictions else trust_weight * 0.5,
            contradictions=contradictions,
            confidence_delta=confidence_delta,
            timestamp=datetime.now(timezone.utc).timestamp(),
            evidence=evidence or {}
        )

        self.verification_history.append(result)
        return result

    def _check_contradictions(
        self,
        artifact: Artifact,
        evidence: Dict[str, Any]
    ) -> List[str]:
        """Check for contradictions"""
        # Simplified contradiction detection
        contradictions = []

        # Check if content contradicts evidence
        if 'expected' in evidence and 'actual' in evidence:
            if evidence['expected'] != evidence['actual']:
                contradictions.append(f"Expected {evidence['expected']}, got {evidence['actual']}")

        return contradictions


class DeliverableCompiler:
    """
    Formatting & Deliverable Assembly Layer

    Final outputs are not written directly by agents.
    They are assembled by Deliverable Compiler.

    Rule: Formatting is downstream of authority, not part of reasoning.
    This prevents "pretty lies".
    """

    def __init__(self):
        self.compiled_deliverables: List[Dict[str, Any]] = []

    def compile_deliverable(
        self,
        bound_artifacts: List[Artifact],
        execution_outputs: List[ExecutionRecord],
        format_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compile deliverable from bound artifacts and execution outputs

        Inputs:
        - Bound artifacts
        - Execution outputs
        - Customer format requirements

        Outputs:
        - PDF specs
        - Contracts
        - Engineering drawings
        - Compliance packets
        """
        deliverable = {
            'id': f"deliverable_{len(self.compiled_deliverables)}",
            'timestamp': datetime.now(timezone.utc).timestamp(),
            'artifacts': [a.to_dict() for a in bound_artifacts],
            'executions': [
                {
                    'id': e.id,
                    'content': e.content,
                    'signature': e.signature,
                    'timestamp': e.timestamp
                }
                for e in execution_outputs
            ],
            'format': format_requirements,
            'compiled': True
        }

        self.compiled_deliverables.append(deliverable)
        return deliverable


class MemoryArtifactSystem:
    """
    Complete Memory & Artifact Subsystem

    Integrates all four memory planes with verification and compilation

    Memory Invariants (NON-NEGOTIABLE):
    1. Sandbox data can never influence execution directly
    2. Execution memory is append-only
    3. Control memory cannot be written by agents
    4. Verification always increases determinism or blocks progress
    5. Formatting cannot bypass binding phase
    """

    def __init__(self):
        # Four memory planes
        self.sandbox = SandboxMemory()
        self.working = WorkingArtifactMemory()
        self.control = ControlMemory()
        self.execution = ExecutionMemory()

        # Verification and compilation
        self.verification = VerificationInterfaceLayer()
        self.compiler = DeliverableCompiler()

        # Transition tracking
        self.transition_log: List[Dict[str, Any]] = []

    def write_sandbox(self, artifact: Artifact) -> str:
        """Write to sandbox (always allowed)"""
        return self.sandbox.write(artifact)

    def promote_to_working(
        self,
        artifact_id: str,
        phase_legal: bool,
        coherent: bool
    ) -> Optional[str]:
        """
        Promote artifact from sandbox to working memory

        Transition: Draft → Structured
        Requires: phase legality, basic coherence
        """
        artifact = self.sandbox.read(artifact_id)
        if not artifact:
            return None

        result = self.working.promote_from_sandbox(artifact, phase_legal, coherent)

        if result:
            self.transition_log.append({
                'artifact_id': artifact_id,
                'from': 'sandbox',
                'to': 'working',
                'timestamp': datetime.now(timezone.utc).timestamp(),
                'transition': 'draft_to_structured'
            })

        return result

    def verify_artifact(
        self,
        artifact_id: str,
        source: VerificationSource,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Optional[VerificationResult]:
        """
        Verify artifact

        Transition: Structured → Verified
        Requires: deterministic checks
        """
        artifact = self.working.read(artifact_id)
        if not artifact:
            return None

        # Perform verification
        result = self.verification.verify_artifact(artifact, source, evidence)

        # Update artifact
        self.working.mark_verified(artifact_id, result)

        # Log transition
        self.transition_log.append({
            'artifact_id': artifact_id,
            'from': 'structured',
            'to': 'verified',
            'timestamp': datetime.now(timezone.utc).timestamp(),
            'transition': 'structured_to_verified',
            'verification': result.trust_weighted_score
        })

        return result

    def bind_artifact(
        self,
        artifact_id: str,
        authority: float
    ) -> bool:
        """
        Bind artifact

        Transition: Verified → Bound
        Requires: authority threshold
        """
        artifact = self.working.read(artifact_id)
        if not artifact:
            return False

        if artifact.state != ArtifactState.VERIFIED:
            return False

        if authority < 0.7:  # Bind threshold
            return False

        # Update state
        artifact.state = ArtifactState.BOUND

        # Log transition
        self.transition_log.append({
            'artifact_id': artifact_id,
            'from': 'verified',
            'to': 'bound',
            'timestamp': datetime.now(timezone.utc).timestamp(),
            'transition': 'verified_to_bound',
            'authority': authority
        })

        return True

    def execute_artifacts(
        self,
        artifact_ids: List[str],
        content: Any,
        authority: float,
        murphy_index: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ExecutionRecord]:
        """
        Execute artifacts (commit to execution memory)

        Transition: Bound → Executed
        Requires: authority >= bind threshold, murphy_index minimal
        """
        # Verify all artifacts are bound
        artifacts = [self.working.read(aid) for aid in artifact_ids]
        if not all(a and a.state == ArtifactState.BOUND for a in artifacts):
            return None

        # Commit to execution memory
        record = self.execution.commit(
            artifact_ids=artifact_ids,
            content=content,
            authority=authority,
            murphy_index=murphy_index,
            metadata=metadata
        )

        if record:
            # Update artifact states
            for artifact in artifacts:
                if artifact:
                    artifact.state = ArtifactState.EXECUTED

            # Log transitions
            for artifact_id in artifact_ids:
                self.transition_log.append({
                    'artifact_id': artifact_id,
                    'from': 'bound',
                    'to': 'executed',
                    'timestamp': datetime.now(timezone.utc).timestamp(),
                    'transition': 'bound_to_executed',
                    'execution_id': record.id
                })

        return record

    def compile_deliverable(
        self,
        artifact_ids: List[str],
        execution_ids: List[str],
        format_requirements: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Compile final deliverable"""
        # Get bound artifacts
        artifacts = [self.working.read(aid) for aid in artifact_ids]
        bound_artifacts = [a for a in artifacts if a and a.state == ArtifactState.BOUND]

        # Get execution records
        executions = [self.execution.read(eid) for eid in execution_ids]
        execution_records = [e for e in executions if e]

        if not bound_artifacts and not execution_records:
            return None

        return self.compiler.compile_deliverable(
            bound_artifacts=bound_artifacts,
            execution_outputs=execution_records,
            format_requirements=format_requirements
        )

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            'sandbox': {
                'artifacts': len(self.sandbox.artifacts),
                'plane': 'SANDBOX',
                'authority': 'none'
            },
            'working': {
                'artifacts': len(self.working.artifacts),
                'plane': 'WORKING',
                'authority': 'candidate'
            },
            'control': {
                'active_gates': len(self.control.active_gates),
                'confidence': self.control.read_confidence(),
                'murphy_index': self.control.read_murphy_index(),
                'authority': self.control.read_authority(),
                'plane': 'CONTROL',
                'authority_level': 'governance'
            },
            'execution': {
                'records': len(self.execution.records),
                'plane': 'EXECUTION',
                'authority': 'committed'
            },
            'transitions': len(self.transition_log),
            'verifications': len(self.verification.verification_history),
            'deliverables': len(self.compiler.compiled_deliverables)
        }
