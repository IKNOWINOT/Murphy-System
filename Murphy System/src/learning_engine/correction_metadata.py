"""
Correction Metadata Tracking System
Tracks detailed metadata about corrections for analysis and learning.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from .correction_models import Correction, CorrectionSeverity, CorrectionType

logger = logging.getLogger(__name__)


class MetadataCategory(str, Enum):
    """Categories of metadata."""
    SYSTEM = "system"
    USER = "user"
    CONTEXT = "context"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    LEARNING = "learning"


class MetadataEntry(BaseModel):
    """Single metadata entry."""
    key: str
    value: Any
    category: MetadataCategory
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "system"
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class SystemMetadata(BaseModel):
    """System-level metadata about correction."""
    murphy_version: str = "2.0"
    phase: str
    component: str
    execution_time_ms: float
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    error_logs: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class UserMetadata(BaseModel):
    """User-related metadata."""
    user_id: str
    user_role: str
    expertise_level: str  # "novice", "intermediate", "expert"
    correction_count: int = 0
    average_correction_time: float = 0.0
    preferred_correction_method: Optional[str] = None
    session_id: Optional[str] = None


class ContextMetadata(BaseModel):
    """Context metadata about when/where correction occurred."""
    environment: str  # "development", "staging", "production"
    deployment_id: Optional[str] = None
    request_id: Optional[str] = None
    client_info: Dict[str, Any] = Field(default_factory=dict)
    geographic_location: Optional[str] = None
    time_of_day: str  # "morning", "afternoon", "evening", "night"
    day_of_week: str
    business_hours: bool


class PerformanceMetadata(BaseModel):
    """Performance-related metadata."""
    original_execution_time_ms: float
    corrected_execution_time_ms: Optional[float] = None
    performance_improvement_percent: Optional[float] = None
    resource_usage_before: Dict[str, float] = Field(default_factory=dict)
    resource_usage_after: Dict[str, float] = Field(default_factory=dict)
    bottlenecks_identified: List[str] = Field(default_factory=list)


class QualityMetadata(BaseModel):
    """Quality-related metadata."""
    original_confidence: float = Field(ge=0.0, le=1.0)
    corrected_confidence: float = Field(ge=0.0, le=1.0)
    confidence_improvement: float
    validation_score: Optional[float] = None
    peer_review_score: Optional[float] = None
    automated_test_results: Dict[str, bool] = Field(default_factory=dict)
    quality_gates_passed: List[str] = Field(default_factory=list)
    quality_gates_failed: List[str] = Field(default_factory=list)


class LearningMetadata(BaseModel):
    """Learning-related metadata for shadow agent training."""
    pattern_identified: bool = False
    pattern_type: Optional[str] = None
    similar_corrections_count: int = 0
    training_value: float = Field(ge=0.0, le=1.0)  # How valuable for training
    feature_importance: Dict[str, float] = Field(default_factory=dict)
    applicable_contexts: List[str] = Field(default_factory=list)
    generalization_potential: float = Field(ge=0.0, le=1.0, default=0.5)


class CorrectionMetadataTracker:
    """
    Tracks and manages correction metadata.
    """

    def __init__(self):
        self.metadata_store: Dict[str, List[MetadataEntry]] = defaultdict(list)
        self.system_metadata: Dict[str, SystemMetadata] = {}
        self.user_metadata: Dict[str, UserMetadata] = {}
        self.context_metadata: Dict[str, ContextMetadata] = {}
        self.performance_metadata: Dict[str, PerformanceMetadata] = {}
        self.quality_metadata: Dict[str, QualityMetadata] = {}
        self.learning_metadata: Dict[str, LearningMetadata] = {}

    def track_system_metadata(
        self,
        correction_id: str,
        metadata: SystemMetadata
    ):
        """Track system metadata for a correction."""
        self.system_metadata[correction_id] = metadata

        # Add to general metadata store
        self._add_metadata_entry(
            correction_id,
            "system_metadata",
            metadata.model_dump(),
            MetadataCategory.SYSTEM
        )

    def track_user_metadata(
        self,
        correction_id: str,
        metadata: UserMetadata
    ):
        """Track user metadata for a correction."""
        self.user_metadata[correction_id] = metadata

        self._add_metadata_entry(
            correction_id,
            "user_metadata",
            metadata.model_dump(),
            MetadataCategory.USER
        )

    def track_context_metadata(
        self,
        correction_id: str,
        metadata: ContextMetadata
    ):
        """Track context metadata for a correction."""
        self.context_metadata[correction_id] = metadata

        self._add_metadata_entry(
            correction_id,
            "context_metadata",
            metadata.model_dump(),
            MetadataCategory.CONTEXT
        )

    def track_performance_metadata(
        self,
        correction_id: str,
        metadata: PerformanceMetadata
    ):
        """Track performance metadata for a correction."""
        self.performance_metadata[correction_id] = metadata

        self._add_metadata_entry(
            correction_id,
            "performance_metadata",
            metadata.model_dump(),
            MetadataCategory.PERFORMANCE
        )

    def track_quality_metadata(
        self,
        correction_id: str,
        metadata: QualityMetadata
    ):
        """Track quality metadata for a correction."""
        self.quality_metadata[correction_id] = metadata

        self._add_metadata_entry(
            correction_id,
            "quality_metadata",
            metadata.model_dump(),
            MetadataCategory.QUALITY
        )

    def track_learning_metadata(
        self,
        correction_id: str,
        metadata: LearningMetadata
    ):
        """Track learning metadata for a correction."""
        self.learning_metadata[correction_id] = metadata

        self._add_metadata_entry(
            correction_id,
            "learning_metadata",
            metadata.model_dump(),
            MetadataCategory.LEARNING
        )

    def _add_metadata_entry(
        self,
        correction_id: str,
        key: str,
        value: Any,
        category: MetadataCategory,
        source: str = "system"
    ):
        """Add a metadata entry."""
        entry = MetadataEntry(
            key=key,
            value=value,
            category=category,
            source=source
        )
        self.metadata_store[correction_id].append(entry)

    def get_all_metadata(self, correction_id: str) -> Dict[str, Any]:
        """Get all metadata for a correction."""
        return {
            "system": self.system_metadata.get(correction_id),
            "user": self.user_metadata.get(correction_id),
            "context": self.context_metadata.get(correction_id),
            "performance": self.performance_metadata.get(correction_id),
            "quality": self.quality_metadata.get(correction_id),
            "learning": self.learning_metadata.get(correction_id),
            "entries": [e.model_dump() for e in self.metadata_store.get(correction_id, [])]
        }

    def get_metadata_by_category(
        self,
        correction_id: str,
        category: MetadataCategory
    ) -> List[MetadataEntry]:
        """Get metadata entries by category."""
        entries = self.metadata_store.get(correction_id, [])
        return [e for e in entries if e.category == category]

    def search_metadata(
        self,
        key: Optional[str] = None,
        category: Optional[MetadataCategory] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, List[MetadataEntry]]:
        """Search metadata across all corrections."""
        results = {}

        for correction_id, entries in self.metadata_store.items():
            matching_entries = entries

            if key:
                matching_entries = [e for e in matching_entries if e.key == key]

            if category:
                matching_entries = [e for e in matching_entries if e.category == category]

            if start_date:
                matching_entries = [e for e in matching_entries if e.timestamp >= start_date]

            if end_date:
                matching_entries = [e for e in matching_entries if e.timestamp <= end_date]

            if matching_entries:
                results[correction_id] = matching_entries

        return results


class MetadataAnalyzer:
    """
    Analyzes correction metadata for insights.
    """

    def __init__(self, tracker: CorrectionMetadataTracker):
        self.tracker = tracker

    def analyze_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze patterns in user corrections."""
        user_corrections = [
            cid for cid, meta in self.tracker.user_metadata.items()
            if meta.user_id == user_id
        ]

        if not user_corrections:
            return {"total_corrections": 0}

        # Analyze correction times
        times = []
        for cid in user_corrections:
            perf_meta = self.tracker.performance_metadata.get(cid)
            if perf_meta:
                times.append(perf_meta.original_execution_time_ms)

        # Analyze quality improvements
        quality_improvements = []
        for cid in user_corrections:
            qual_meta = self.tracker.quality_metadata.get(cid)
            if qual_meta:
                quality_improvements.append(qual_meta.confidence_improvement)

        return {
            "total_corrections": len(user_corrections),
            "average_correction_time": sum(times) / (len(times) or 1) if times else 0,
            "average_quality_improvement": sum(quality_improvements) / (len(quality_improvements) or 1) if quality_improvements else 0,
            "correction_ids": user_corrections
        }

    def analyze_context_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in correction contexts."""
        by_environment = defaultdict(int)
        by_time_of_day = defaultdict(int)
        by_day_of_week = defaultdict(int)

        for context_meta in self.tracker.context_metadata.values():
            by_environment[context_meta.environment] += 1
            by_time_of_day[context_meta.time_of_day] += 1
            by_day_of_week[context_meta.day_of_week] += 1

        return {
            "by_environment": dict(by_environment),
            "by_time_of_day": dict(by_time_of_day),
            "by_day_of_week": dict(by_day_of_week)
        }

    def analyze_performance_impact(self) -> Dict[str, Any]:
        """Analyze performance impact of corrections."""
        improvements = []

        for perf_meta in self.tracker.performance_metadata.values():
            if perf_meta.performance_improvement_percent is not None:
                improvements.append(perf_meta.performance_improvement_percent)

        if not improvements:
            return {"average_improvement": 0}

        return {
            "average_improvement": sum(improvements) / len(improvements),
            "max_improvement": max(improvements),
            "min_improvement": min(improvements),
            "total_corrections_with_perf_data": len(improvements)
        }

    def identify_high_value_corrections(
        self,
        min_training_value: float = 0.7
    ) -> List[str]:
        """Identify corrections with high training value."""
        high_value = []

        for cid, learning_meta in self.tracker.learning_metadata.items():
            if learning_meta.training_value >= min_training_value:
                high_value.append(cid)

        return high_value

    def get_feature_importance_summary(self) -> Dict[str, float]:
        """Get summary of feature importance across all corrections."""
        feature_scores = defaultdict(list)

        for learning_meta in self.tracker.learning_metadata.values():
            for feature, importance in learning_meta.feature_importance.items():
                feature_scores[feature].append(importance)

        # Calculate average importance for each feature
        return {
            feature: sum(scores) / (len(scores) or 1)
            for feature, scores in feature_scores.items()
        }


class MetadataEnricher:
    """
    Enriches corrections with additional metadata.
    """

    def __init__(self, tracker: CorrectionMetadataTracker):
        self.tracker = tracker

    def enrich_correction(
        self,
        correction: Correction,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Enrich a correction with metadata.

        Args:
            correction: Correction to enrich
            additional_data: Additional data to include
        """
        additional_data = additional_data or {}

        # System metadata
        system_meta = SystemMetadata(
            phase=correction.context.phase,
            component=correction.context.operation,
            execution_time_ms=correction.metrics.time_to_correct_seconds * 1000
        )
        self.tracker.track_system_metadata(correction.id, system_meta)

        # User metadata
        if correction.context.user_id:
            user_meta = UserMetadata(
                user_id=correction.context.user_id,
                user_role=additional_data.get("user_role", "user"),
                expertise_level=additional_data.get("expertise_level", "intermediate"),
                session_id=correction.context.session_id
            )
            self.tracker.track_user_metadata(correction.id, user_meta)

        # Context metadata
        now = datetime.now(timezone.utc)
        hour = now.hour

        if 6 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 18:
            time_of_day = "afternoon"
        elif 18 <= hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        context_meta = ContextMetadata(
            environment=correction.context.environment,
            time_of_day=time_of_day,
            day_of_week=now.strftime("%A"),
            business_hours=9 <= hour < 17
        )
        self.tracker.track_context_metadata(correction.id, context_meta)

        # Quality metadata
        if correction.diffs:
            original_conf = sum(
                d.original.confidence or 0.5 for d in correction.diffs
            ) / (len(correction.diffs) or 1)

            corrected_conf = sum(
                d.corrected.confidence for d in correction.diffs
            ) / (len(correction.diffs) or 1)

            quality_meta = QualityMetadata(
                original_confidence=original_conf,
                corrected_confidence=corrected_conf,
                confidence_improvement=corrected_conf - original_conf
            )
            self.tracker.track_quality_metadata(correction.id, quality_meta)

        # Learning metadata
        learning_meta = LearningMetadata(
            pattern_identified=len(correction.learning_signals) > 0,
            similar_corrections_count=len(correction.related_corrections),
            training_value=self._calculate_training_value(correction)
        )
        self.tracker.track_learning_metadata(correction.id, learning_meta)

    def _calculate_training_value(self, correction: Correction) -> float:
        """Calculate training value of a correction."""
        value = 0.5  # Base value

        # Higher value for critical/high severity
        if correction.severity in [CorrectionSeverity.CRITICAL, CorrectionSeverity.HIGH]:
            value += 0.2

        # Higher value if has learning signals
        if correction.learning_signals:
            value += 0.2

        # Higher value for complex corrections
        if correction.metrics.correction_complexity == "complex":
            value += 0.1

        return min(value, 1.0)


class CorrectionMetadataSystem:
    """
    Complete correction metadata tracking system.
    """

    def __init__(self):
        self.tracker = CorrectionMetadataTracker()
        self.analyzer = MetadataAnalyzer(self.tracker)
        self.enricher = MetadataEnricher(self.tracker)

    # Tracking methods
    def track_system(self, correction_id: str, metadata: SystemMetadata):
        """Track system metadata."""
        self.tracker.track_system_metadata(correction_id, metadata)

    def track_user(self, correction_id: str, metadata: UserMetadata):
        """Track user metadata."""
        self.tracker.track_user_metadata(correction_id, metadata)

    def track_context(self, correction_id: str, metadata: ContextMetadata):
        """Track context metadata."""
        self.tracker.track_context_metadata(correction_id, metadata)

    def track_performance(self, correction_id: str, metadata: PerformanceMetadata):
        """Track performance metadata."""
        self.tracker.track_performance_metadata(correction_id, metadata)

    def track_quality(self, correction_id: str, metadata: QualityMetadata):
        """Track quality metadata."""
        self.tracker.track_quality_metadata(correction_id, metadata)

    def track_learning(self, correction_id: str, metadata: LearningMetadata):
        """Track learning metadata."""
        self.tracker.track_learning_metadata(correction_id, metadata)

    # Enrichment
    def enrich_correction(
        self,
        correction: Correction,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Enrich correction with metadata."""
        self.enricher.enrich_correction(correction, additional_data)

    # Retrieval
    def get_all_metadata(self, correction_id: str) -> Dict[str, Any]:
        """Get all metadata for a correction."""
        return self.tracker.get_all_metadata(correction_id)

    # Analysis
    def analyze_user_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze user correction patterns."""
        return self.analyzer.analyze_user_patterns(user_id)

    def analyze_context_patterns(self) -> Dict[str, Any]:
        """Analyze context patterns."""
        return self.analyzer.analyze_context_patterns()

    def analyze_performance_impact(self) -> Dict[str, Any]:
        """Analyze performance impact."""
        return self.analyzer.analyze_performance_impact()

    def get_high_value_corrections(self, min_value: float = 0.7) -> List[str]:
        """Get high-value corrections for training."""
        return self.analyzer.identify_high_value_corrections(min_value)

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance summary."""
        return self.analyzer.get_feature_importance_summary()
