"""
Learning Engine Module for Murphy System Runtime

This module provides comprehensive learning and adaptation capabilities:
- Performance tracking and analysis
- Pattern recognition
- Feedback collection and analysis
- Adaptive decision making

Components:
- LearningEngine: Main learning coordinator
- FeedbackSystem: Feedback collection and analysis
- AdaptiveDecisionEngine: Adaptive decision making
"""

from .learning_engine import (
    LearningEngine,
    PerformanceTracker,
    PatternRecognizer,
    FeedbackCollector,
    LearnedPattern,
    LearningInsight
)

from .feedback_system import (
    HumanFeedbackSystem,
    FeedbackCollectionInterface,
    FeedbackCategorizer,
    FeedbackValidator,
    FeedbackAnalytics,
    Feedback,
    FeedbackEntry,
    FeedbackStorage,
    FeedbackAnalysis,
    FeedbackAnalyzer,
    OperationalFeedbackSystem
)

# Alias for backward compatibility
FeedbackSystem = OperationalFeedbackSystem

from .adaptive_decision_engine import (
    AdaptiveDecisionEngine,
    DecisionHistory,
    PolicyManager,
    AdaptiveDecision,
    DecisionPolicy
)

__all__ = [
    # Main components
    'LearningEngine',
    'FeedbackSystem',
    'AdaptiveDecisionEngine',

    # Learning engine components
    'PerformanceTracker',
    'PatternRecognizer',
    'FeedbackCollector',
    'LearnedPattern',
    'LearningInsight',

    # Feedback system components
    'FeedbackStorage',
    'FeedbackAnalyzer',
    'FeedbackEntry',
    'FeedbackAnalysis',

    # Adaptive decision engine components
    'DecisionHistory',
    'PolicyManager',
    'AdaptiveDecision',
    'DecisionPolicy'
]
