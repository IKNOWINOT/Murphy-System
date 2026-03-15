"""
Learning Engine for Murphy System Runtime

This module provides comprehensive learning capabilities including:
- Performance tracking and analysis
- Pattern recognition
- Learning from experience
- Adaptive behavior adjustment
"""

import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Represents a single performance metric"""
    metric_name: str
    value: float
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearnedPattern:
    """Represents a learned pattern"""
    pattern_id: str
    pattern_type: str  # 'temporal', 'correlation', 'sequential', 'cyclic'
    confidence: float  # 0.0 to 1.0
    frequency: int
    first_observed: datetime
    last_observed: datetime
    pattern_data: Dict[str, Any]
    conditions: List[Dict[str, Any]]


@dataclass
class LearningInsight:
    """Represents a learning insight"""
    insight_id: str
    insight_type: str
    confidence: float
    importance: float  # 0.0 to 1.0
    recommendation: str
    supporting_data: Dict[str, Any]
    timestamp: datetime


class PerformanceTracker:
    """Tracks performance metrics over time"""

    def __init__(self, max_history_size: int = 10000):
        self.max_history_size = max_history_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history_size))
        self.aggregations: Dict[str, Dict[str, float]] = {}
        self.lock = threading.Lock()

    def record_metric(self, metric_name: str, value: float,
                     context: Optional[Dict[str, Any]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a performance metric"""
        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            context=context or {},
            metadata=metadata or {}
        )

        with self.lock:
            self.metrics[metric_name].append(metric)
            self._update_aggregations(metric_name)

    def _update_aggregations(self, metric_name: str) -> None:
        """Update statistical aggregations for a metric"""
        metrics_list = list(self.metrics[metric_name])
        if not metrics_list:
            return

        values = [m.value for m in metrics_list]
        self.aggregations[metric_name] = {
            'count': len(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values),
            'stddev': statistics.stdev(values) if len(values) > 1 else 0.0
        }

    def get_statistics(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get statistical aggregations for a metric"""
        return self.aggregations.get(metric_name)

    def get_recent_metrics(self, metric_name: str,
                          count: int = 10) -> List[PerformanceMetric]:
        """Get recent metrics for a given metric name"""
        with self.lock:
            metrics_list = list(self.metrics[metric_name])
            return metrics_list[-count:]

    def get_metrics_in_range(self, metric_name: str,
                            start_time: datetime,
                            end_time: datetime) -> List[PerformanceMetric]:
        """Get metrics within a time range"""
        with self.lock:
            return [
                m for m in self.metrics[metric_name]
                if start_time <= m.timestamp <= end_time
            ]

    def get_all_metric_names(self) -> List[str]:
        """Get all metric names being tracked"""
        return list(self.metrics.keys())


class PatternRecognizer:
    """Recognizes patterns in performance data"""

    def __init__(self):
        self.patterns: Dict[str, LearnedPattern] = {}
        self.lock = threading.Lock()

    def analyze_metrics(self, metrics: List[PerformanceMetric]) -> List[LearnedPattern]:
        """Analyze metrics and recognize patterns"""
        recognized_patterns = []

        # Group metrics by name
        by_name = defaultdict(list)
        for metric in metrics:
            by_name[metric.metric_name].append(metric)

        # Analyze each metric group
        for metric_name, metric_list in by_name.items():
            # Temporal patterns
            temporal_patterns = self._recognize_temporal_patterns(metric_name, metric_list)
            recognized_patterns.extend(temporal_patterns)

            # Correlation patterns
            correlation_patterns = self._recognize_correlation_patterns(metric_name, metric_list)
            recognized_patterns.extend(correlation_patterns)

        return recognized_patterns

    def _recognize_temporal_patterns(self, metric_name: str,
                                     metrics: List[PerformanceMetric]) -> List[LearnedPattern]:
        """Recognize temporal patterns in metrics"""
        patterns = []

        if len(metrics) < 10:
            return patterns

        # Check for increasing trend
        values = [m.value for m in metrics]
        increasing_trend = self._detect_trend(values, 'increasing')
        if increasing_trend[0]:
            pattern_id = f"{metric_name}_increasing_trend"
            pattern = LearnedPattern(
                pattern_id=pattern_id,
                pattern_type='temporal',
                confidence=increasing_trend[1],
                frequency=1,
                first_observed=metrics[0].timestamp,
                last_observed=metrics[-1].timestamp,
                pattern_data={
                    'metric_name': metric_name,
                    'trend': 'increasing',
                    'rate': increasing_trend[2]
                },
                conditions=[{'metric_name': metric_name, 'trend': 'increasing'}]
            )
            patterns.append(pattern)

        # Check for decreasing trend
        decreasing_trend = self._detect_trend(values, 'decreasing')
        if decreasing_trend[0]:
            pattern_id = f"{metric_name}_decreasing_trend"
            pattern = LearnedPattern(
                pattern_id=pattern_id,
                pattern_type='temporal',
                confidence=decreasing_trend[1],
                frequency=1,
                first_observed=metrics[0].timestamp,
                last_observed=metrics[-1].timestamp,
                pattern_data={
                    'metric_name': metric_name,
                    'trend': 'decreasing',
                    'rate': decreasing_trend[2]
                },
                conditions=[{'metric_name': metric_name, 'trend': 'decreasing'}]
            )
            patterns.append(pattern)

        # Check for cyclic patterns
        cyclic = self._detect_cyclic_pattern(values)
        if cyclic[0]:
            pattern_id = f"{metric_name}_cyclic_pattern"
            pattern = LearnedPattern(
                pattern_id=pattern_id,
                pattern_type='cyclic',
                confidence=cyclic[1],
                frequency=1,
                first_observed=metrics[0].timestamp,
                last_observed=metrics[-1].timestamp,
                pattern_data={
                    'metric_name': metric_name,
                    'period': cyclic[2],
                    'amplitude': cyclic[3]
                },
                conditions=[{'metric_name': metric_name, 'pattern': 'cyclic'}]
            )
            patterns.append(pattern)

        return patterns

    def _detect_trend(self, values: List[float],
                     trend_type: str) -> Tuple[bool, float, float]:
        """Detect if values show a trend"""
        if len(values) < 2:
            return False, 0.0, 0.0

        # Calculate linear regression
        n = len(values)
        x = list(range(n))

        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(xi * yi for xi, yi in zip(x, values))
        sum_x2 = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Determine confidence based on slope magnitude relative to variance
        variance = statistics.variance(values) if len(values) > 1 else 0.0
        confidence = min(abs(slope) / (variance + 1e-10), 1.0)

        if trend_type == 'increasing' and slope > 0:
            return True, confidence, slope
        elif trend_type == 'decreasing' and slope < 0:
            return True, confidence, slope
        else:
            return False, 0.0, 0.0

    def _detect_cyclic_pattern(self, values: List[float]) -> Tuple[bool, float, int, float]:
        """Detect cyclic patterns in values"""
        if len(values) < 20:
            return False, 0.0, 0, 0.0

        # Simple approach: check for repeated patterns
        max_period = len(values) // 3
        best_period = 0
        best_confidence = 0.0
        best_amplitude = 0.0

        for period in range(3, max_period + 1):
            # Split into cycles and check similarity
            cycles = [values[i:i+period] for i in range(0, len(values), period)]
            if len(cycles) < 2:
                continue

            # Calculate variance between cycles
            cycle_similarity = self._calculate_cycle_similarity(cycles)
            amplitude = max(values) - min(values)

            if cycle_similarity > best_confidence:
                best_confidence = cycle_similarity
                best_period = period
                best_amplitude = amplitude

        if best_confidence > 0.7:
            return True, best_confidence, best_period, best_amplitude
        return False, 0.0, 0, 0.0

    def _calculate_cycle_similarity(self, cycles: List[List[float]]) -> float:
        """Calculate similarity between cycles"""
        if len(cycles) < 2:
            return 0.0

        # Normalize cycles to same length
        max_len = max(len(c) for c in cycles)
        normalized = []
        for cycle in cycles:
            # Pad with last value
            padded = cycle + [cycle[-1]] * (max_len - len(cycle))
            normalized.append(padded)

        # Calculate average correlation between cycles
        correlations = []
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                corr = self._calculate_correlation(normalized[i], normalized[j])
                correlations.append(corr)

        return statistics.mean(correlations) if correlations else 0.0

    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        sum_y2 = sum(yi * yi for yi in y)

        denominator = (n * sum_x2 - sum_x * sum_x) * (n * sum_y2 - sum_y * sum_y)
        if denominator <= 0:
            return 0.0

        numerator = n * sum_xy - sum_x * sum_y
        return numerator / (denominator ** 0.5)

    def _recognize_correlation_patterns(self, metric_name: str,
                                       metrics: List[PerformanceMetric]) -> List[LearnedPattern]:
        """Recognize correlation patterns between metrics"""
        # Simplified correlation analysis; extend for production use
        return []

    def add_pattern(self, pattern: LearnedPattern) -> None:
        """Add a learned pattern"""
        with self.lock:
            self.patterns[pattern.pattern_id] = pattern

    def get_pattern(self, pattern_id: str) -> Optional[LearnedPattern]:
        """Get a pattern by ID"""
        return self.patterns.get(pattern_id)

    def get_patterns_by_type(self, pattern_type: str) -> List[LearnedPattern]:
        """Get all patterns of a specific type"""
        return [p for p in self.patterns.values() if p.pattern_type == pattern_type]

    def get_all_patterns(self) -> List[LearnedPattern]:
        """Get all learned patterns"""
        return list(self.patterns.values())


class FeedbackCollector:
    """Collects feedback from operations and uses it for learning"""

    def __init__(self):
        self.feedback_history: List[Dict[str, Any]] = []
        self.feedback_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.lock = threading.Lock()

    def collect_feedback(self, feedback_type: str, operation_id: str,
                        success: bool, confidence: float,
                        feedback_data: Optional[Dict[str, Any]] = None) -> None:
        """Collect feedback from an operation"""
        feedback = {
            'feedback_type': feedback_type,
            'operation_id': operation_id,
            'success': success,
            'confidence': confidence,
            'timestamp': datetime.now(timezone.utc),
            'feedback_data': feedback_data or {}
        }

        with self.lock:
            self.feedback_history.append(feedback)
            self.feedback_by_type[feedback_type].append(feedback)

    def get_success_rate(self, feedback_type: Optional[str] = None) -> float:
        """Calculate success rate for a feedback type"""
        with self.lock:
            if feedback_type:
                feedback_list = self.feedback_by_type.get(feedback_type, [])
            else:
                feedback_list = self.feedback_history

            if not feedback_list:
                return 0.0

            successful = sum(1 for f in feedback_list if f['success'])
            return successful / len(feedback_list)

    def get_average_confidence(self, feedback_type: Optional[str] = None) -> float:
        """Calculate average confidence for a feedback type"""
        with self.lock:
            if feedback_type:
                feedback_list = self.feedback_by_type.get(feedback_type, [])
            else:
                feedback_list = self.feedback_history

            if not feedback_list:
                return 0.0

            confidences = [f['confidence'] for f in feedback_list]
            return statistics.mean(confidences)

    def get_recent_feedback(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent feedback"""
        with self.lock:
            return self.feedback_history[-count:]


class LearningEngine:
    """
    Main learning engine that coordinates learning activities

    The learning engine:
    - Tracks performance metrics
    - Recognizes patterns in data
    - Collects and analyzes feedback
    - Generates learning insights
    - Adapts system behavior based on learning
    """

    def __init__(self, enable_learning: bool = True):
        self.enable_learning = enable_learning
        self.performance_tracker = PerformanceTracker()
        self.pattern_recognizer = PatternRecognizer()
        self.feedback_collector = FeedbackCollector()
        self.insights: List[LearningInsight] = []
        self.learning_history: List[Dict[str, Any]] = []
        self.lock = threading.Lock()

    def record_performance(self, metric_name: str, value: float,
                          context: Optional[Dict[str, Any]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a performance metric"""
        if not self.enable_learning:
            return

        self.performance_tracker.record_metric(
            metric_name, value, context, metadata
        )

        # Periodically analyze patterns
        metrics = self.performance_tracker.get_recent_metrics(metric_name, count=50)
        if len(metrics) >= 20:
            patterns = self.pattern_recognizer.analyze_metrics(metrics)
            for pattern in patterns:
                self.pattern_recognizer.add_pattern(pattern)

    def collect_feedback(self, feedback_type: str, operation_id: str,
                        success: bool, confidence: float,
                        feedback_data: Optional[Dict[str, Any]] = None) -> None:
        """Collect feedback from an operation"""
        if not self.enable_learning:
            return

        self.feedback_collector.collect_feedback(
            feedback_type, operation_id, success, confidence, feedback_data
        )

    def analyze_learning(self) -> List[LearningInsight]:
        """Analyze learning data and generate insights"""
        if not self.enable_learning:
            return []

        insights = []

        # Analyze performance trends
        metric_names = self.performance_tracker.get_all_metric_names()
        for metric_name in metric_names:
            metrics = self.performance_tracker.get_recent_metrics(metric_name, count=100)
            if len(metrics) >= 20:
                patterns = self.pattern_recognizer.analyze_metrics(metrics)

                for pattern in patterns:
                    insight = self._generate_insight_from_pattern(pattern)
                    if insight:
                        insights.append(insight)

        # Analyze feedback trends
        feedback_types = list(self.feedback_collector.feedback_by_type.keys())
        for feedback_type in feedback_types:
            success_rate = self.feedback_collector.get_success_rate(feedback_type)
            avg_confidence = self.feedback_collector.get_average_confidence(feedback_type)

            if success_rate < 0.8 or avg_confidence < 0.7:
                insight = LearningInsight(
                    insight_id=f"{feedback_type}_improvement",
                    insight_type="performance_issue",
                    confidence=1.0 - success_rate,
                    importance=1.0 - avg_confidence,
                    recommendation=f"Improve {feedback_type} operations",
                    supporting_data={
                        'success_rate': success_rate,
                        'average_confidence': avg_confidence,
                        'feedback_type': feedback_type
                    },
                    timestamp=datetime.now(timezone.utc)
                )
                insights.append(insight)

        # Store insights
        with self.lock:
            self.insights.extend(insights)
            self.learning_history.append({
                'timestamp': datetime.now(timezone.utc),
                'insights_generated': len(insights),
                'total_insights': len(self.insights)
            })

        return insights

    def _generate_insight_from_pattern(self, pattern: LearnedPattern) -> Optional[LearningInsight]:
        """Generate a learning insight from a pattern"""
        if pattern.confidence < 0.8:
            return None

        if pattern.pattern_type == 'temporal':
            trend = pattern.pattern_data.get('trend', '')
            metric_name = pattern.pattern_data.get('metric_name', '')

            if trend == 'increasing':
                return LearningInsight(
                    insight_id=f"{pattern.pattern_id}_insight",
                    insight_type="trend_alert",
                    confidence=pattern.confidence,
                    importance=0.8,
                    recommendation=f"Metric {metric_name} is increasing over time. Monitor for resource exhaustion.",
                    supporting_data=pattern.pattern_data,
                    timestamp=datetime.now(timezone.utc)
                )
            elif trend == 'decreasing':
                return LearningInsight(
                    insight_id=f"{pattern.pattern_id}_insight",
                    insight_type="trend_alert",
                    confidence=pattern.confidence,
                    importance=0.6,
                    recommendation=f"Metric {metric_name} is decreasing over time. Check for degradation.",
                    supporting_data=pattern.pattern_data,
                    timestamp=datetime.now(timezone.utc)
                )

        return None

    def get_performance_statistics(self, metric_name: str) -> Optional[Dict[str, float]]:
        """Get performance statistics for a metric"""
        return self.performance_tracker.get_statistics(metric_name)

    def get_patterns(self, pattern_type: Optional[str] = None) -> List[LearnedPattern]:
        """Get learned patterns"""
        if pattern_type:
            return self.pattern_recognizer.get_patterns_by_type(pattern_type)
        return self.pattern_recognizer.get_all_patterns()

    def get_insights(self, max_insights: int = 10) -> List[LearningInsight]:
        """Get recent learning insights"""
        with self.lock:
            return self.insights[-max_insights:]

    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of collected feedback"""
        return {
            'total_feedback': len(self.feedback_collector.feedback_history),
            'success_rate': self.feedback_collector.get_success_rate(),
            'average_confidence': self.feedback_collector.get_average_confidence(),
            'feedback_by_type': {
                feedback_type: {
                    'count': len(feedbacks),
                    'success_rate': self.feedback_collector.get_success_rate(feedback_type),
                    'average_confidence': self.feedback_collector.get_average_confidence(feedback_type)
                }
                for feedback_type, feedbacks in self.feedback_collector.feedback_by_type.items()
            }
        }

    def reset_learning(self) -> None:
        """Reset all learning data"""
        self.performance_tracker = PerformanceTracker()
        self.pattern_recognizer = PatternRecognizer()
        self.feedback_collector = FeedbackCollector()
        self.insights = []
        self.learning_history = []

    def export_learning_data(self) -> Dict[str, Any]:
        """Export learning data for analysis"""
        return {
            'insights': [
                {
                    'insight_id': i.insight_id,
                    'insight_type': i.insight_type,
                    'confidence': i.confidence,
                    'importance': i.importance,
                    'recommendation': i.recommendation,
                    'supporting_data': i.supporting_data,
                    'timestamp': i.timestamp.isoformat()
                }
                for i in self.insights
            ],
            'patterns': [
                {
                    'pattern_id': p.pattern_id,
                    'pattern_type': p.pattern_type,
                    'confidence': p.confidence,
                    'frequency': p.frequency,
                    'first_observed': p.first_observed.isoformat(),
                    'last_observed': p.last_observed.isoformat(),
                    'pattern_data': p.pattern_data
                }
                for p in self.pattern_recognizer.get_all_patterns()
            ],
            'feedback_summary': self.get_feedback_summary(),
            'learning_history': [
                {
                    'timestamp': h['timestamp'].isoformat(),
                    'insights_generated': h['insights_generated'],
                    'total_insights': h['total_insights']
                }
                for h in self.learning_history
            ]
        }
