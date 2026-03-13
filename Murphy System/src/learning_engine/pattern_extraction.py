"""
Correction Validation and Pattern Extraction System
Comprehensive system covering correction validation (Section 3) and pattern extraction (Section 4).
Tasks 3.1-3.4 and 4.1-4.4.
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from .correction_models import Correction, CorrectionSeverity, CorrectionStatus, CorrectionType

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 3: CORRECTION VALIDATION
# ============================================================================

# TASK 3.1: CORRECTION VERIFICATION
# ============================================================================

class VerificationMethod(str, Enum):
    """Methods for verifying corrections."""
    AUTOMATED_TEST = "automated_test"
    PEER_REVIEW = "peer_review"
    EXPERT_VALIDATION = "expert_validation"
    SYSTEM_CHECK = "system_check"
    HISTORICAL_COMPARISON = "historical_comparison"


class VerificationResult(BaseModel):
    """Result of correction verification."""
    correction_id: str
    method: VerificationMethod
    is_verified: bool
    confidence: float = Field(ge=0.0, le=1.0)
    issues_found: List[str] = Field(default_factory=list)
    verified_by: str
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None


class CorrectionVerifier:
    """Verifies corrections for accuracy and validity."""

    def __init__(self):
        self.verification_history: List[VerificationResult] = []
        self.verification_rules: List[callable] = []
        self._initialize_rules()

    def _initialize_rules(self):
        """Initialize verification rules."""
        self.verification_rules = [
            self._verify_completeness,
            self._verify_consistency,
            self._verify_impact,
            self._verify_reasoning
        ]

    def verify_correction(
        self,
        correction: Correction,
        method: VerificationMethod = VerificationMethod.SYSTEM_CHECK,
        verifier_id: str = "system"
    ) -> VerificationResult:
        """
        Verify a correction.

        Args:
            correction: Correction to verify
            method: Verification method to use
            verifier_id: ID of verifier

        Returns:
            VerificationResult
        """
        issues = []

        # Run verification rules
        for rule in self.verification_rules:
            rule_issues = rule(correction)
            issues.extend(rule_issues)

        is_verified = len(issues) == 0
        confidence = 1.0 - (len(issues) * 0.15)
        confidence = max(confidence, 0.0)

        result = VerificationResult(
            correction_id=correction.id,
            method=method,
            is_verified=is_verified,
            confidence=confidence,
            issues_found=issues,
            verified_by=verifier_id
        )

        self.verification_history.append(result)

        # Update correction status
        if is_verified:
            correction.status = CorrectionStatus.VALIDATED
            correction.validated_at = datetime.now(timezone.utc)
            correction.validated_by = verifier_id

        return result

    def _verify_completeness(self, correction: Correction) -> List[str]:
        """Verify correction is complete."""
        issues = []

        if not correction.diffs:
            issues.append("No changes specified")

        if not correction.reasoning:
            issues.append("Missing reasoning")

        if not correction.explanation:
            issues.append("Missing explanation")

        return issues

    def _verify_consistency(self, correction: Correction) -> List[str]:
        """Verify correction is internally consistent."""
        issues = []

        # Check if severity matches impact
        impact = correction.calculate_impact_score()

        if correction.severity == CorrectionSeverity.CRITICAL and impact < 0.7:
            issues.append("Severity doesn't match impact score")

        if correction.severity == CorrectionSeverity.LOW and impact > 0.7:
            issues.append("Severity too low for impact")

        return issues

    def _verify_impact(self, correction: Correction) -> List[str]:
        """Verify correction impact is reasonable."""
        issues = []

        impact = correction.calculate_impact_score()

        if impact == 0.0:
            issues.append("Zero impact - correction may not be necessary")

        return issues

    def _verify_reasoning(self, correction: Correction) -> List[str]:
        """Verify reasoning is adequate."""
        issues = []

        if len(correction.reasoning) < 20:
            issues.append("Reasoning too brief")

        return issues


# TASK 3.2: CONFLICT DETECTION
# ============================================================================

class ConflictType(str, Enum):
    """Types of conflicts between corrections."""
    CONTRADICTORY = "contradictory"
    OVERLAPPING = "overlapping"
    DEPENDENT = "dependent"
    REDUNDANT = "redundant"


class Conflict(BaseModel):
    """Conflict between corrections."""
    correction_id_1: str
    correction_id_2: str
    conflict_type: ConflictType
    severity: str  # "high", "medium", "low"
    description: str
    resolution_suggestion: Optional[str] = None
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConflictDetector:
    """Detects conflicts between corrections."""

    def __init__(self):
        self.detected_conflicts: List[Conflict] = []

    def detect_conflicts(
        self,
        corrections: List[Correction]
    ) -> List[Conflict]:
        """
        Detect conflicts between corrections.

        Args:
            corrections: List of corrections to check

        Returns:
            List of detected conflicts
        """
        conflicts = []

        for i, c1 in enumerate(corrections):
            for c2 in corrections[i+1:]:
                conflict = self._check_pair(c1, c2)
                if conflict:
                    conflicts.append(conflict)

        self.detected_conflicts.extend(conflicts)
        return conflicts

    def _check_pair(
        self,
        c1: Correction,
        c2: Correction
    ) -> Optional[Conflict]:
        """Check a pair of corrections for conflicts."""
        # Same task
        if c1.context.task_id != c2.context.task_id:
            return None

        # Check for contradictory changes
        c1_fields = set(c1.get_affected_fields())
        c2_fields = set(c2.get_affected_fields())

        overlapping_fields = c1_fields & c2_fields

        if overlapping_fields:
            # Check if changes are contradictory
            for field in overlapping_fields:
                c1_diff = next((d for d in c1.diffs if d.field_name == field), None)
                c2_diff = next((d for d in c2.diffs if d.field_name == field), None)

                if c1_diff and c2_diff:
                    if c1_diff.corrected.value != c2_diff.corrected.value:
                        return Conflict(
                            correction_id_1=c1.id,
                            correction_id_2=c2.id,
                            conflict_type=ConflictType.CONTRADICTORY,
                            severity="high",
                            description=f"Contradictory changes to field '{field}'",
                            resolution_suggestion="Review both corrections and choose one"
                        )
                    else:
                        return Conflict(
                            correction_id_1=c1.id,
                            correction_id_2=c2.id,
                            conflict_type=ConflictType.REDUNDANT,
                            severity="low",
                            description=f"Redundant changes to field '{field}'",
                            resolution_suggestion="Keep one correction, remove the other"
                        )

        return None


# TASK 3.3: CORRECTION QUALITY SCORING
# ============================================================================

class QualityScore(BaseModel):
    """Quality score for a correction."""
    overall_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)
    clarity_score: float = Field(ge=0.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)
    reasoning_score: float = Field(ge=0.0, le=1.0)
    components: Dict[str, float] = Field(default_factory=dict)


class QualityScorer:
    """Scores correction quality."""

    def score_correction(self, correction: Correction) -> QualityScore:
        """
        Score correction quality.

        Args:
            correction: Correction to score

        Returns:
            QualityScore
        """
        # Completeness
        completeness = self._score_completeness(correction)

        # Clarity
        clarity = self._score_clarity(correction)

        # Impact
        impact = correction.calculate_impact_score()

        # Reasoning
        reasoning = self._score_reasoning(correction)

        # Overall (weighted average)
        overall = (
            0.25 * completeness +
            0.25 * clarity +
            0.25 * impact +
            0.25 * reasoning
        )

        return QualityScore(
            overall_score=overall,
            completeness_score=completeness,
            clarity_score=clarity,
            impact_score=impact,
            reasoning_score=reasoning,
            components={
                "completeness": completeness,
                "clarity": clarity,
                "impact": impact,
                "reasoning": reasoning
            }
        )

    def _score_completeness(self, correction: Correction) -> float:
        """Score completeness."""
        score = 0.0

        if correction.diffs:
            score += 0.3

        if correction.reasoning:
            score += 0.3

        if correction.explanation:
            score += 0.2

        if correction.learning_signals:
            score += 0.2

        return score

    def _score_clarity(self, correction: Correction) -> float:
        """Score clarity."""
        score = 0.5  # Base score

        # Check reasoning length
        if len(correction.reasoning) > 50:
            score += 0.2

        # Check explanation length
        if len(correction.explanation) > 30:
            score += 0.2

        # Check for specific details
        if any(diff.description for diff in correction.diffs):
            score += 0.1

        return min(score, 1.0)

    def _score_reasoning(self, correction: Correction) -> float:
        """Score reasoning quality."""
        score = 0.5  # Base score

        reasoning = correction.reasoning.lower()

        # Check for explanation words
        explanation_words = ["because", "since", "due to", "therefore", "thus"]
        if any(word in reasoning for word in explanation_words):
            score += 0.2

        # Check for specific details
        if any(char.isdigit() for char in reasoning):
            score += 0.1

        # Check length
        if len(reasoning) > 100:
            score += 0.2

        return min(score, 1.0)


# TASK 3.4: CORRECTION APPROVAL WORKFLOW
# ============================================================================

class ApprovalStatus(str, Enum):
    """Status in approval workflow."""
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class ApprovalWorkflow:
    """Manages correction approval workflow."""

    def __init__(self):
        self.approval_queue: List[Correction] = []
        self.approval_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.approvers: Set[str] = set()

    def submit_for_approval(self, correction: Correction):
        """Submit correction for approval."""
        self.approval_queue.append(correction)
        correction.status = CorrectionStatus.UNDER_REVIEW

        self.approval_history[correction.id].append({
            "action": "submitted",
            "timestamp": datetime.now(timezone.utc),
            "status": ApprovalStatus.PENDING_REVIEW
        })

    def approve_correction(
        self,
        correction_id: str,
        approver_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Approve a correction."""
        correction = self._find_correction(correction_id)
        if not correction:
            return False

        correction.status = CorrectionStatus.VALIDATED
        correction.validated_by = approver_id
        correction.validated_at = datetime.now(timezone.utc)
        correction.validation_notes = notes

        self.approval_history[correction_id].append({
            "action": "approved",
            "approver": approver_id,
            "timestamp": datetime.now(timezone.utc),
            "notes": notes
        })

        # Remove from queue
        self.approval_queue = [c for c in self.approval_queue if c.id != correction_id]

        return True

    def reject_correction(
        self,
        correction_id: str,
        approver_id: str,
        reason: str
    ) -> bool:
        """Reject a correction."""
        correction = self._find_correction(correction_id)
        if not correction:
            return False

        correction.status = CorrectionStatus.REJECTED
        correction.validation_notes = reason

        self.approval_history[correction_id].append({
            "action": "rejected",
            "approver": approver_id,
            "timestamp": datetime.now(timezone.utc),
            "reason": reason
        })

        self.approval_queue = [c for c in self.approval_queue if c.id != correction_id]

        return True

    def request_revision(
        self,
        correction_id: str,
        approver_id: str,
        feedback: str
    ) -> bool:
        """Request revision of a correction."""
        correction = self._find_correction(correction_id)
        if not correction:
            return False

        self.approval_history[correction_id].append({
            "action": "revision_requested",
            "approver": approver_id,
            "timestamp": datetime.now(timezone.utc),
            "feedback": feedback
        })

        return True

    def _find_correction(self, correction_id: str) -> Optional[Correction]:
        """Find correction in queue."""
        for correction in self.approval_queue:
            if correction.id == correction_id:
                return correction
        return None

    def get_pending_approvals(self) -> List[Correction]:
        """Get corrections pending approval."""
        return self.approval_queue.copy()


# ============================================================================
# SECTION 4: PATTERN EXTRACTION
# ============================================================================

# TASK 4.1: PATTERN EXTRACTION ALGORITHMS
# ============================================================================

class PatternType(str, Enum):
    """Types of patterns."""
    FREQUENT_CORRECTION = "frequent_correction"
    COMMON_ERROR = "common_error"
    SYSTEMATIC_ISSUE = "systematic_issue"
    USER_BEHAVIOR = "user_behavior"
    CONTEXT_DEPENDENT = "context_dependent"


class CorrectionPattern(BaseModel):
    """Extracted pattern from corrections."""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    pattern_type: PatternType
    name: str
    description: str
    frequency: int
    confidence: float = Field(ge=0.0, le=1.0)
    examples: List[str] = Field(default_factory=list)
    applicable_contexts: List[str] = Field(default_factory=list)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PatternExtractor:
    """Extracts patterns from corrections."""

    def __init__(self):
        self.extracted_patterns: List[CorrectionPattern] = []

    def extract_patterns(
        self,
        corrections: List[Correction],
        min_frequency: int = 3
    ) -> List[CorrectionPattern]:
        """
        Extract patterns from corrections.

        Args:
            corrections: List of corrections to analyze
            min_frequency: Minimum frequency for a pattern

        Returns:
            List of extracted patterns
        """
        patterns = []

        # Extract frequent correction patterns
        patterns.extend(self._extract_frequent_corrections(corrections, min_frequency))

        # Extract common error patterns
        patterns.extend(self._extract_common_errors(corrections, min_frequency))

        # Extract systematic issues
        patterns.extend(self._extract_systematic_issues(corrections, min_frequency))

        self.extracted_patterns.extend(patterns)
        return patterns

    def _extract_frequent_corrections(
        self,
        corrections: List[Correction],
        min_frequency: int
    ) -> List[CorrectionPattern]:
        """Extract frequently corrected fields."""
        patterns = []

        # Count field corrections
        field_counts = defaultdict(int)
        field_examples = defaultdict(list)

        for correction in corrections:
            for field in correction.get_affected_fields():
                field_counts[field] += 1
                if len(field_examples[field]) < 5:
                    field_examples[field].append(correction.id)

        # Create patterns for frequent fields
        for field, count in field_counts.items():
            if count >= min_frequency:
                pattern = CorrectionPattern(
                    pattern_type=PatternType.FREQUENT_CORRECTION,
                    name=f"Frequent correction of '{field}'",
                    description=f"Field '{field}' is frequently corrected",
                    frequency=count,
                    confidence=min(count / (len(corrections) or 1), 1.0),
                    examples=field_examples[field],
                    metadata={"field": field}
                )
                patterns.append(pattern)

        return patterns

    def _extract_common_errors(
        self,
        corrections: List[Correction],
        min_frequency: int
    ) -> List[CorrectionPattern]:
        """Extract common error patterns."""
        patterns = []

        # Group by correction type
        type_groups = defaultdict(list)
        for correction in corrections:
            type_groups[correction.correction_type].append(correction)

        # Find common patterns in each type
        for corr_type, group in type_groups.items():
            if len(group) >= min_frequency:
                pattern = CorrectionPattern(
                    pattern_type=PatternType.COMMON_ERROR,
                    name=f"Common {corr_type.value} errors",
                    description=f"Frequent {corr_type.value} corrections detected",
                    frequency=len(group),
                    confidence=len(group) / (len(corrections) or 1),
                    examples=[c.id for c in group[:5]],
                    metadata={"correction_type": corr_type.value}
                )
                patterns.append(pattern)

        return patterns

    def _extract_systematic_issues(
        self,
        corrections: List[Correction],
        min_frequency: int
    ) -> List[CorrectionPattern]:
        """Extract systematic issues."""
        patterns = []

        # Group by task
        task_groups = defaultdict(list)
        for correction in corrections:
            task_groups[correction.context.task_id].append(correction)

        # Find tasks with multiple corrections
        for task_id, group in task_groups.items():
            if len(group) >= min_frequency:
                pattern = CorrectionPattern(
                    pattern_type=PatternType.SYSTEMATIC_ISSUE,
                    name=f"Systematic issues in task {task_id}",
                    description=f"Multiple corrections needed for task {task_id}",
                    frequency=len(group),
                    confidence=0.8,
                    examples=[c.id for c in group],
                    applicable_contexts=[task_id],
                    metadata={"task_id": task_id}
                )
                patterns.append(pattern)

        return patterns


# TASK 4.2: CORRECTION PATTERN MINING
# ============================================================================

class PatternMiner:
    """Mines patterns from correction data."""

    def __init__(self):
        self.mined_patterns: List[CorrectionPattern] = []

    def mine_sequential_patterns(
        self,
        corrections: List[Correction]
    ) -> List[CorrectionPattern]:
        """Mine sequential patterns in corrections."""
        patterns = []

        # Sort by timestamp
        sorted_corrections = sorted(corrections, key=lambda c: c.created_at)

        # Look for sequences
        for i in range(len(sorted_corrections) - 1):
            c1 = sorted_corrections[i]
            c2 = sorted_corrections[i + 1]

            # Check if corrections are related
            if c1.context.task_id == c2.context.task_id:
                time_diff = (c2.created_at - c1.created_at).total_seconds()

                if time_diff < 3600:  # Within 1 hour
                    pattern = CorrectionPattern(
                        pattern_type=PatternType.CONTEXT_DEPENDENT,
                        name="Sequential corrections",
                        description=f"Corrections often follow each other in task {c1.context.task_id}",
                        frequency=2,
                        confidence=0.7,
                        examples=[c1.id, c2.id],
                        applicable_contexts=[c1.context.task_id]
                    )
                    patterns.append(pattern)

        self.mined_patterns.extend(patterns)
        return patterns

    def mine_association_rules(
        self,
        corrections: List[Correction]
    ) -> List[Dict[str, Any]]:
        """Mine association rules between correction attributes."""
        rules = []

        # Find associations between correction type and severity
        type_severity = defaultdict(lambda: defaultdict(int))

        for correction in corrections:
            type_severity[correction.correction_type][correction.severity] += 1

        # Generate rules
        for corr_type, severities in type_severity.items():
            total = sum(severities.values())
            for severity, count in severities.items():
                confidence = count / total
                if confidence > 0.5:
                    rules.append({
                        "rule": f"{corr_type.value} => {severity.value}",
                        "confidence": confidence,
                        "support": count / len(corrections)
                    })

        return rules


# TASK 4.3: PATTERN CLUSTERING
# ============================================================================

class PatternCluster(BaseModel):
    """Cluster of similar patterns."""
    id: str = Field(default_factory=lambda: str(__import__('uuid').uuid4()))
    name: str
    patterns: List[str]  # Pattern IDs
    centroid: Dict[str, Any] = Field(default_factory=dict)
    size: int
    cohesion: float = Field(ge=0.0, le=1.0)


class PatternClusterer:
    """Clusters similar patterns together."""

    def __init__(self):
        self.clusters: List[PatternCluster] = []

    def cluster_patterns(
        self,
        patterns: List[CorrectionPattern],
        num_clusters: int = 5
    ) -> List[PatternCluster]:
        """
        Cluster patterns by similarity.

        Args:
            patterns: Patterns to cluster
            num_clusters: Number of clusters to create

        Returns:
            List of pattern clusters
        """
        if len(patterns) < num_clusters:
            num_clusters = len(patterns)

        # Simple clustering by pattern type
        type_clusters = defaultdict(list)
        for pattern in patterns:
            type_clusters[pattern.pattern_type].append(pattern.id)

        clusters = []
        for pattern_type, pattern_ids in type_clusters.items():
            cluster = PatternCluster(
                name=f"{pattern_type.value} cluster",
                patterns=pattern_ids,
                size=len(pattern_ids),
                cohesion=0.8
            )
            clusters.append(cluster)

        self.clusters = clusters
        return clusters


# TASK 4.4: PATTERN VALIDATION
# ============================================================================

class PatternValidator:
    """Validates extracted patterns."""

    def validate_pattern(
        self,
        pattern: CorrectionPattern,
        corrections: List[Correction]
    ) -> Dict[str, Any]:
        """
        Validate a pattern.

        Args:
            pattern: Pattern to validate
            corrections: All corrections for validation

        Returns:
            Validation results
        """
        # Check if pattern examples exist
        example_corrections = [
            c for c in corrections
            if c.id in pattern.examples
        ]

        if len(example_corrections) < pattern.frequency * 0.8:
            return {
                "valid": False,
                "reason": "Insufficient examples found"
            }

        # Check confidence
        if pattern.confidence < 0.3:
            return {
                "valid": False,
                "reason": "Confidence too low"
            }

        # Check frequency
        if pattern.frequency < 2:
            return {
                "valid": False,
                "reason": "Frequency too low"
            }

        return {
            "valid": True,
            "confidence": pattern.confidence,
            "examples_found": len(example_corrections)
        }


# ============================================================================
# UNIFIED VALIDATION AND PATTERN SYSTEM
# ============================================================================

class CorrectionValidationAndPatternSystem:
    """
    Complete system for correction validation and pattern extraction.
    """

    def __init__(self):
        # Validation components
        self.verifier = CorrectionVerifier()
        self.conflict_detector = ConflictDetector()
        self.quality_scorer = QualityScorer()
        self.approval_workflow = ApprovalWorkflow()

        # Pattern extraction components
        self.pattern_extractor = PatternExtractor()
        self.pattern_miner = PatternMiner()
        self.pattern_clusterer = PatternClusterer()
        self.pattern_validator = PatternValidator()

    # Validation methods (Section 3)
    def verify_correction(
        self,
        correction: Correction,
        method: VerificationMethod = VerificationMethod.SYSTEM_CHECK
    ) -> VerificationResult:
        """Verify a correction."""
        return self.verifier.verify_correction(correction, method)

    def detect_conflicts(
        self,
        corrections: List[Correction]
    ) -> List[Conflict]:
        """Detect conflicts between corrections."""
        return self.conflict_detector.detect_conflicts(corrections)

    def score_quality(self, correction: Correction) -> QualityScore:
        """Score correction quality."""
        return self.quality_scorer.score_correction(correction)

    def submit_for_approval(self, correction: Correction):
        """Submit correction for approval."""
        self.approval_workflow.submit_for_approval(correction)

    def approve_correction(
        self,
        correction_id: str,
        approver_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Approve a correction."""
        return self.approval_workflow.approve_correction(correction_id, approver_id, notes)

    # Pattern extraction methods (Section 4)
    def extract_patterns(
        self,
        corrections: List[Correction],
        min_frequency: int = 3
    ) -> List[CorrectionPattern]:
        """Extract patterns from corrections."""
        return self.pattern_extractor.extract_patterns(corrections, min_frequency)

    def mine_patterns(
        self,
        corrections: List[Correction]
    ) -> Tuple[List[CorrectionPattern], List[Dict[str, Any]]]:
        """Mine patterns and association rules."""
        sequential = self.pattern_miner.mine_sequential_patterns(corrections)
        rules = self.pattern_miner.mine_association_rules(corrections)
        return sequential, rules

    def cluster_patterns(
        self,
        patterns: List[CorrectionPattern],
        num_clusters: int = 5
    ) -> List[PatternCluster]:
        """Cluster patterns."""
        return self.pattern_clusterer.cluster_patterns(patterns, num_clusters)

    def validate_pattern(
        self,
        pattern: CorrectionPattern,
        corrections: List[Correction]
    ) -> Dict[str, Any]:
        """Validate a pattern."""
        return self.pattern_validator.validate_pattern(pattern, corrections)

    # Utility methods
    def get_pending_approvals(self) -> List[Correction]:
        """Get pending approvals."""
        return self.approval_workflow.get_pending_approvals()

    def get_extracted_patterns(self) -> List[CorrectionPattern]:
        """Get all extracted patterns."""
        return self.pattern_extractor.extracted_patterns

    def get_pattern_clusters(self) -> List[PatternCluster]:
        """Get pattern clusters."""
        return self.pattern_clusterer.clusters
