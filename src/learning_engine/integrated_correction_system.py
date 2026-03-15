"""
Integrated Correction System

Integrates the new correction capture system with the original
murphy_runtime_analysis learning engine.

This allows corrections to be captured, validated, and fed into
the existing learning system for continuous improvement.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Import original learning system
try:
    from .learning_system import LearningSystem
    HAS_LEARNING_SYSTEM = True
except ImportError:
    HAS_LEARNING_SYSTEM = False
    logging.warning("Original LearningSystem not found")

# Import new correction capture system
from .correction_capture import CorrectionCaptureSystem, InteractiveCorrectionCapture
from .correction_models import Correction
from .feedback_system import Feedback, FeedbackCollectionInterface, HumanFeedbackSystem
from .pattern_extraction import CorrectionPattern, CorrectionVerifier, PatternExtractor

logger = logging.getLogger(__name__)


class IntegratedCorrectionSystem:
    """
    Integrated Correction System

    Combines:
    1. New correction capture and validation
    2. Pattern extraction from corrections
    3. Original learning system integration
    4. Shadow agent training data preparation

    This provides a complete pipeline from human correction to
    system learning and improvement.
    """

    def __init__(self):
        """Initialize integrated correction system"""

        # Original learning system
        if HAS_LEARNING_SYSTEM:
            self.learning_system = LearningSystem()
            logger.info("Loaded original LearningSystem")
        else:
            self.learning_system = None
            logger.warning("Original LearningSystem not available")

        # New correction capture components
        self.correction_capture = CorrectionCaptureSystem()
        self.interactive_capture = InteractiveCorrectionCapture()
        self.feedback_system = HumanFeedbackSystem()
        self.pattern_extractor = PatternExtractor()
        self.correction_verifier = CorrectionVerifier()

        logger.info("IntegratedCorrectionSystem initialized")

    def capture_correction(
        self,
        task_id: str,
        correction_data: Dict[str, Any],
        method: str = 'interactive'
    ) -> Correction:
        """
        Capture a correction from user

        Args:
            task_id: ID of task being corrected
            correction_data: Correction details
            method: Capture method (interactive, batch, api, inline)

        Returns:
            Recorded correction
        """

        # Record correction using new system
        from .correction_models import CorrectionSeverity, CorrectionType, create_simple_correction

        correction_type_str = correction_data.get('correction_type', 'output_modification')
        correction_type_map = {ct.value: ct for ct in CorrectionType}
        correction_type = correction_type_map.get(correction_type_str, CorrectionType.OUTPUT_MODIFICATION)

        severity_str = correction_data.get('severity', 'medium')
        severity_map = {s.value: s for s in CorrectionSeverity}
        severity = severity_map.get(severity_str, CorrectionSeverity.MEDIUM)

        correction = create_simple_correction(
            task_id=task_id,
            field_name='output',
            original_value=correction_data.get('original_output', ''),
            corrected_value=correction_data.get('corrected_output', ''),
            reasoning=correction_data.get('explanation', ''),
            correction_type=correction_type,
            severity=severity
        )
        self.correction_capture.all_corrections.append(correction)

        logger.info(f"Captured correction for task {task_id} via {method}")

        # Validate correction
        validation_result = self.correction_verifier.verify_correction(correction)

        if not validation_result.is_verified:
            logger.warning(f"Correction validation issues: {validation_result.issues_found}")

        # Extract patterns
        patterns = self.pattern_extractor.extract_patterns([correction])

        if patterns:
            logger.info(f"Extracted {len(patterns)} patterns from correction")

        # Feed to original learning system if available
        if self.learning_system:
            try:
                self._feed_to_learning_system(correction, patterns)
            except Exception as exc:
                logger.error(f"Error feeding to learning system: {exc}")

        return correction

    def capture_feedback(
        self,
        task_id: str,
        feedback_data: Dict[str, Any]
    ) -> Feedback:
        """
        Capture user feedback

        Args:
            task_id: ID of task
            feedback_data: Feedback details

        Returns:
            Recorded feedback
        """

        from .feedback_system import FeedbackType

        feedback_type_str = feedback_data.get('feedback_type', 'suggestion')
        feedback_type_map = {ft.value: ft for ft in FeedbackType}
        feedback_type = feedback_type_map.get(feedback_type_str, FeedbackType.SUGGESTION)

        feedback = self.feedback_system.collect_feedback(
            feedback_type=feedback_type,
            title=feedback_data.get('title', feedback_type_str),
            description=feedback_data.get('comments', feedback_data.get('description', '')),
            user_id=feedback_data.get('user_id', 'system'),
            task_id=task_id
        )

        logger.info(f"Captured feedback for task {task_id}")

        # Validate feedback
        analysis = self.feedback_system.validate_feedback(feedback.id)

        logger.debug(f"Feedback analysis: {analysis}")

        return feedback

    def get_correction_patterns(
        self,
        task_type: Optional[str] = None,
        min_frequency: int = 2
    ) -> List[CorrectionPattern]:
        """
        Get extracted correction patterns

        Args:
            task_type: Filter by task type (optional)
            min_frequency: Minimum pattern frequency

        Returns:
            List of patterns
        """

        patterns = self.pattern_extractor.extracted_patterns
        if task_type:
            patterns = [p for p in patterns if task_type in p.applicable_contexts]
        if min_frequency:
            patterns = [p for p in patterns if p.frequency >= min_frequency]

        logger.info(f"Retrieved {len(patterns)} patterns")

        return patterns

    def get_training_data(
        self,
        task_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get training data for shadow agent

        Args:
            task_type: Filter by task type (optional)
            limit: Maximum number of examples (optional)

        Returns:
            List of training examples
        """

        # Get corrections
        corrections = self.correction_capture.get_corrections(
            task_type=task_type,
            limit=limit
        )

        # Convert to training format
        training_data = []
        for correction in corrections:
            example = {
                'task_id': correction.task_id,
                'original_output': correction.original_output,
                'corrected_output': correction.corrected_output,
                'correction_type': correction.correction_type,
                'metadata': correction.metadata,
                'timestamp': correction.timestamp
            }
            training_data.append(example)

        logger.info(f"Prepared {len(training_data)} training examples")

        return training_data

    def _feed_to_learning_system(
        self,
        correction: Correction,
        patterns: List[CorrectionPattern]
    ):
        """
        Feed correction and patterns to original learning system

        Args:
            correction: Correction to feed
            patterns: Extracted patterns
        """

        if not self.learning_system:
            return

        # Convert correction to learning system format
        learning_data = {
            'task_id': correction.task_id,
            'error_type': correction.correction_type,
            'original': correction.original_output,
            'corrected': correction.corrected_output,
            'patterns': [p.model_dump() for p in patterns],
            'timestamp': correction.timestamp
        }

        # Feed to learning system
        try:
            self.learning_system.learn_from_correction(learning_data)
            logger.info(f"Fed correction to learning system: {correction.task_id}")
        except Exception as exc:
            logger.error(f"Error feeding to learning system: {exc}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get correction system statistics

        Returns:
            Statistics dictionary
        """

        corrections = self.correction_capture.get_all_corrections()
        patterns = self.pattern_extractor.extracted_patterns

        stats = {
            'total_corrections': len(corrections),
            'total_patterns': len(patterns),
            'corrections_by_type': {},
            'corrections_by_severity': {},
            'patterns_by_type': {},
            'has_learning_system': HAS_LEARNING_SYSTEM
        }

        # Count by type
        for correction in corrections:
            correction_type = correction.correction_type
            stats['corrections_by_type'][correction_type] = \
                stats['corrections_by_type'].get(correction_type, 0) + 1

            severity = correction.severity
            stats['corrections_by_severity'][severity] = \
                stats['corrections_by_severity'].get(severity, 0) + 1

        # Count patterns by type
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            stats['patterns_by_type'][pattern_type] = \
                stats['patterns_by_type'].get(pattern_type, 0) + 1

        return stats
