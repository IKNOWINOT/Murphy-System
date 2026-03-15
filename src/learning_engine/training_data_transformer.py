"""
Correction to Training Data Transformer

This module transforms human corrections into training examples for the shadow agent.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    from .correction_models import Correction, CorrectionType  # noqa: F401
    from .feedback_system import Feedback, FeedbackType  # noqa: F401
    from .pattern_extraction import CorrectionPattern as Pattern  # noqa: F401
except ImportError:
    Correction = None  # type: ignore[assignment,misc]
    CorrectionType = None  # type: ignore[assignment,misc]
    Feedback = None  # type: ignore[assignment,misc]
    FeedbackType = None  # type: ignore[assignment,misc]
    Pattern = None  # type: ignore[assignment,misc]
from .models import (
    Feature,
    FeatureEngineering,
    FeatureType,
    Label,
    LabelType,
    TrainingDataset,
    TrainingExample,
)

logger = logging.getLogger(__name__)


class CorrectionToTrainingTransformer:
    """Transforms corrections into training examples"""

    def __init__(self, feature_config: Optional[FeatureEngineering] = None):
        self.feature_config = feature_config or FeatureEngineering()
        self.feature_extractors = self._initialize_extractors()

    def _initialize_extractors(self) -> Dict[str, Any]:
        """Initialize feature extraction functions"""
        return {
            "task_features": self._extract_task_features,
            "correction_features": self._extract_correction_features,
            "context_features": self._extract_context_features,
            "temporal_features": self._extract_temporal_features,
            "quality_features": self._extract_quality_features,
            "pattern_features": self._extract_pattern_features,
        }

    def transform_correction(
        self,
        correction: Correction,
        include_context: bool = True
    ) -> TrainingExample:
        """Transform a single correction into a training example"""

        features = []

        # Extract features from different sources
        for extractor_name, extractor_func in self.feature_extractors.items():
            try:
                extracted = extractor_func(correction)
                features.extend(extracted)
            except Exception as exc:
                logger.warning(f"Failed to extract {extractor_name}: {exc}")

        # Create label from correction
        label = self._create_label_from_correction(correction)

        # Calculate example weight based on correction quality
        weight = self._calculate_example_weight(correction)

        # Create training example
        example = TrainingExample(
            features=features,
            label=label,
            weight=weight,
            task_id=correction.task_id,
            correction_id=correction.id,
            quality_score=correction.metadata.get("quality_score", 1.0),
            is_validated=correction.status == "approved",
            metadata={
                "correction_type": correction.type.value,
                "severity": correction.severity.value,
                "created_at": correction.created_at.isoformat(),
            }
        )

        return example

    def transform_corrections(
        self,
        corrections: List[Correction],
        include_patterns: bool = True
    ) -> TrainingDataset:
        """Transform multiple corrections into a training dataset"""

        examples = []
        source_corrections = []

        for correction in corrections:
            try:
                example = self.transform_correction(correction)
                examples.append(example)
                source_corrections.append(correction.id)
            except Exception as exc:
                logger.error(f"Failed to transform correction {correction.id}: {exc}")

        # Create dataset
        dataset = TrainingDataset(
            name=f"corrections_dataset_{datetime.now(timezone.utc).isoformat()}",
            description=f"Training dataset from {len(corrections)} corrections",
            examples=examples,
            feature_config=self.feature_config,
            source_corrections=source_corrections,
        )

        return dataset

    def _extract_task_features(self, correction: Correction) -> List[Feature]:
        """Extract features from task information"""
        features = []

        if correction.task_id:
            # Task complexity (from metadata)
            task_complexity = correction.metadata.get("task_complexity", 0)
            features.append(Feature(
                name="task_complexity",
                type=FeatureType.NUMERICAL,
                value=task_complexity,
                source="task_metadata"
            ))

            # Task type
            task_type = correction.metadata.get("task_type", "unknown")
            features.append(Feature(
                name="task_type",
                type=FeatureType.CATEGORICAL,
                value=task_type,
                source="task_metadata"
            ))

            # Task duration
            task_duration = correction.metadata.get("task_duration_seconds", 0)
            features.append(Feature(
                name="task_duration",
                type=FeatureType.NUMERICAL,
                value=task_duration,
                source="task_metadata"
            ))

        return features

    def _extract_correction_features(self, correction: Correction) -> List[Feature]:
        """Extract features from correction itself"""
        features = []

        # Correction type
        features.append(Feature(
            name="correction_type",
            type=FeatureType.CATEGORICAL,
            value=correction.type.value,
            source="correction"
        ))

        # Correction severity
        features.append(Feature(
            name="correction_severity",
            type=FeatureType.CATEGORICAL,
            value=correction.severity.value,
            source="correction"
        ))

        # Original vs corrected value difference
        if correction.original_value and correction.corrected_value:
            # For numerical values
            try:
                orig_num = float(correction.original_value)
                corr_num = float(correction.corrected_value)
                diff = abs(corr_num - orig_num)
                features.append(Feature(
                    name="value_difference",
                    type=FeatureType.NUMERICAL,
                    value=diff,
                    source="correction"
                ))
            except (ValueError, TypeError):
                # For text values, use length difference
                orig_len = len(str(correction.original_value))
                corr_len = len(str(correction.corrected_value))
                features.append(Feature(
                    name="text_length_difference",
                    type=FeatureType.NUMERICAL,
                    value=abs(corr_len - orig_len),
                    source="correction"
                ))

        # Correction reason length (proxy for complexity)
        reason_length = len(correction.reason) if correction.reason else 0
        features.append(Feature(
            name="reason_length",
            type=FeatureType.NUMERICAL,
            value=reason_length,
            source="correction"
        ))

        return features

    def _extract_context_features(self, correction: Correction) -> List[Feature]:
        """Extract features from context information"""
        features = []

        context = correction.context

        # User information
        if context.user_id:
            features.append(Feature(
                name="user_id",
                type=FeatureType.CATEGORICAL,
                value=str(context.user_id),
                source="context"
            ))

        # Environment
        if context.environment:
            features.append(Feature(
                name="environment",
                type=FeatureType.CATEGORICAL,
                value=context.environment,
                source="context"
            ))

        # System state features
        if context.system_state:
            # CPU usage
            cpu_usage = context.system_state.get("cpu_usage", 0)
            features.append(Feature(
                name="cpu_usage",
                type=FeatureType.NUMERICAL,
                value=cpu_usage,
                source="context"
            ))

            # Memory usage
            memory_usage = context.system_state.get("memory_usage", 0)
            features.append(Feature(
                name="memory_usage",
                type=FeatureType.NUMERICAL,
                value=memory_usage,
                source="context"
            ))

        # Related tasks count
        related_count = len(context.related_tasks)
        features.append(Feature(
            name="related_tasks_count",
            type=FeatureType.NUMERICAL,
            value=related_count,
            source="context"
        ))

        return features

    def _extract_temporal_features(self, correction: Correction) -> List[Feature]:
        """Extract temporal features"""
        features = []

        if not self.feature_config.extract_time_components:
            return features

        created_at = correction.created_at

        # Hour of day
        features.append(Feature(
            name="hour_of_day",
            type=FeatureType.NUMERICAL,
            value=created_at.hour,
            source="temporal"
        ))

        # Day of week
        features.append(Feature(
            name="day_of_week",
            type=FeatureType.NUMERICAL,
            value=created_at.weekday(),
            source="temporal"
        ))

        # Is weekend
        features.append(Feature(
            name="is_weekend",
            type=FeatureType.CATEGORICAL,
            value=created_at.weekday() >= 5,
            source="temporal"
        ))

        return features

    def _extract_quality_features(self, correction: Correction) -> List[Feature]:
        """Extract quality-related features"""
        features = []

        quality = correction.quality

        # Completeness
        features.append(Feature(
            name="quality_completeness",
            type=FeatureType.NUMERICAL,
            value=quality.completeness,
            source="quality"
        ))

        # Clarity
        features.append(Feature(
            name="quality_clarity",
            type=FeatureType.NUMERICAL,
            value=quality.clarity,
            source="quality"
        ))

        # Consistency
        features.append(Feature(
            name="quality_consistency",
            type=FeatureType.NUMERICAL,
            value=quality.consistency,
            source="quality"
        ))

        # Actionability
        features.append(Feature(
            name="quality_actionability",
            type=FeatureType.NUMERICAL,
            value=quality.actionability,
            source="quality"
        ))

        return features

    def _extract_pattern_features(self, correction: Correction) -> List[Feature]:
        """Extract pattern-related features"""
        features = []

        # Pattern tags
        if correction.tags:
            features.append(Feature(
                name="has_pattern_tags",
                type=FeatureType.CATEGORICAL,
                value=True,
                source="pattern"
            ))

            features.append(Feature(
                name="pattern_tags_count",
                type=FeatureType.NUMERICAL,
                value=len(correction.tags),
                source="pattern"
            ))

        return features

    def _create_label_from_correction(self, correction: Correction) -> Label:
        """Create training label from correction"""

        # For binary classification: was correction approved?
        if correction.status in ["approved", "rejected"]:
            label_value = 1 if correction.status == "approved" else 0
            confidence = 1.0
        else:
            # Pending corrections get lower confidence
            label_value = 1  # Assume approved by default
            confidence = 0.5

        return Label(
            type=LabelType.BINARY,
            value=label_value,
            confidence=confidence,
            source=str(correction.id),
            metadata={
                "correction_type": correction.type.value,
                "severity": correction.severity.value,
            }
        )

    def _calculate_example_weight(self, correction: Correction) -> float:
        """Calculate weight for training example based on correction quality"""

        # Base weight
        weight = 1.0

        # Increase weight for high-severity corrections
        if correction.severity.value == "critical":
            weight *= 2.0
        elif correction.severity.value == "high":
            weight *= 1.5

        # Increase weight for validated corrections
        if correction.status == "approved":
            weight *= 1.2

        # Adjust by quality score
        quality_score = correction.metadata.get("quality_score", 1.0)
        weight *= quality_score

        return weight


class FeedbackToTrainingTransformer:
    """Transforms feedback into training examples"""

    def __init__(self, feature_config: Optional[FeatureEngineering] = None):
        self.feature_config = feature_config or FeatureEngineering()

    def transform_feedback(self, feedback: Feedback) -> TrainingExample:
        """Transform feedback into training example"""

        features = []

        # Feedback type
        features.append(Feature(
            name="feedback_type",
            type=FeatureType.CATEGORICAL,
            value=feedback.type.value,
            source="feedback"
        ))

        # Feedback category
        features.append(Feature(
            name="feedback_category",
            type=FeatureType.CATEGORICAL,
            value=feedback.category,
            source="feedback"
        ))

        # Rating (if available)
        if feedback.rating is not None:
            features.append(Feature(
                name="feedback_rating",
                type=FeatureType.NUMERICAL,
                value=feedback.rating,
                source="feedback"
            ))

        # Comment length
        comment_length = len(feedback.comment) if feedback.comment else 0
        features.append(Feature(
            name="comment_length",
            type=FeatureType.NUMERICAL,
            value=comment_length,
            source="feedback"
        ))

        # Create label (positive/negative feedback)
        label_value = 1 if feedback.rating and feedback.rating >= 3 else 0
        label = Label(
            type=LabelType.BINARY,
            value=label_value,
            confidence=0.8,
            source=str(feedback.id)
        )

        return TrainingExample(
            features=features,
            label=label,
            task_id=feedback.task_id,
            metadata={"feedback_type": feedback.type.value}
        )


class PatternToTrainingTransformer:
    """Transforms patterns into training examples"""

    def __init__(self, feature_config: Optional[FeatureEngineering] = None):
        self.feature_config = feature_config or FeatureEngineering()

    def transform_pattern(self, pattern: Pattern) -> List[TrainingExample]:
        """Transform pattern into multiple training examples"""

        examples = []

        # Create one example per correction in the pattern
        for correction_id in pattern.correction_ids:
            features = []

            # Pattern type
            features.append(Feature(
                name="pattern_type",
                type=FeatureType.CATEGORICAL,
                value=pattern.type.value,
                source="pattern"
            ))

            # Pattern frequency
            features.append(Feature(
                name="pattern_frequency",
                type=FeatureType.NUMERICAL,
                value=pattern.frequency,
                source="pattern"
            ))

            # Pattern confidence
            features.append(Feature(
                name="pattern_confidence",
                type=FeatureType.NUMERICAL,
                value=pattern.confidence,
                source="pattern"
            ))

            # Create label (patterns are generally positive examples)
            label = Label(
                type=LabelType.BINARY,
                value=1,
                confidence=pattern.confidence,
                source=str(pattern.id)
            )

            example = TrainingExample(
                features=features,
                label=label,
                correction_id=correction_id,
                pattern_id=pattern.id,
                weight=pattern.confidence,  # Use pattern confidence as weight
                metadata={"pattern_type": pattern.type.value}
            )

            examples.append(example)

        return examples
