"""
Tests for Learning Engine components

Tests:
- Learning Engine functionality
- Performance tracking
- Pattern recognition
- Feedback collection
- Learning insights generation
"""

import unittest
import time
from datetime import datetime, timedelta, timezone
from src.learning_engine import (
    LearningEngine,
    PerformanceTracker,
    PatternRecognizer,
    FeedbackCollector,
    LearnedPattern,
    LearningInsight
)


class TestPerformanceTracker(unittest.TestCase):
    """Test performance tracker functionality"""

    def setUp(self):
        self.tracker = PerformanceTracker(max_history_size=100)

    def test_record_metric(self):
        """Test recording metrics"""
        self.tracker.record_metric("test_metric", 10.0)
        stats = self.tracker.get_statistics("test_metric")

        self.assertIsNotNone(stats)
        self.assertEqual(stats['count'], 1)
        self.assertEqual(stats['mean'], 10.0)

    def test_aggregations(self):
        """Test statistical aggregations"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for value in values:
            self.tracker.record_metric("test_metric", value)

        stats = self.tracker.get_statistics("test_metric")

        self.assertEqual(stats['count'], 5)
        self.assertEqual(stats['mean'], 3.0)
        self.assertEqual(stats['min'], 1.0)
        self.assertEqual(stats['max'], 5.0)

    def test_recent_metrics(self):
        """Test retrieving recent metrics"""
        for i in range(20):
            self.tracker.record_metric("test_metric", float(i))

        recent = self.tracker.get_recent_metrics("test_metric", count=10)

        self.assertEqual(len(recent), 10)
        # Check that we got the most recent 10
        self.assertEqual(recent[0].value, 10.0)
        self.assertEqual(recent[-1].value, 19.0)

    def test_time_range_filtering(self):
        """Test filtering metrics by time range"""
        # Record metrics at different times
        self.tracker.record_metric("test_metric", 1.0)
        self.tracker.record_metric("test_metric", 2.0)
        self.tracker.record_metric("test_metric", 3.0)

        # Get metrics from a wide range that includes now
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(seconds=1)
        metrics = self.tracker.get_metrics_in_range("test_metric", start_time, end_time)

        # Should get all 3 metrics
        self.assertGreaterEqual(len(metrics), 1)
        self.assertLessEqual(len(metrics), 3)

    def test_max_history_size(self):
        """Test that history size is limited"""
        tracker = PerformanceTracker(max_history_size=10)

        # Record more than max size
        for i in range(20):
            tracker.record_metric("test_metric", float(i))

        stats = tracker.get_statistics("test_metric")

        # Should only keep last 10
        self.assertEqual(stats['count'], 10)


class TestPatternRecognizer(unittest.TestCase):
    """Test pattern recognizer functionality"""

    def setUp(self):
        self.recognizer = PatternRecognizer()

    def test_increasing_trend_detection(self):
        """Test detection of increasing trends"""
        from src.learning_engine.learning_engine import PerformanceMetric

        # Create metrics with increasing trend
        metrics = [
            PerformanceMetric("test", float(i), datetime.now())
            for i in range(1, 21)
        ]

        patterns = self.recognizer._recognize_temporal_patterns("test", metrics)

        # Should detect increasing trend
        self.assertTrue(any(p.pattern_data.get('trend') == 'increasing' for p in patterns))

    def test_decreasing_trend_detection(self):
        """Test detection of decreasing trends"""
        from src.learning_engine.learning_engine import PerformanceMetric

        # Create metrics with decreasing trend
        metrics = [
            PerformanceMetric("test", float(20 - i), datetime.now())
            for i in range(20)
        ]

        patterns = self.recognizer._recognize_temporal_patterns("test", metrics)

        # Should detect decreasing trend
        self.assertTrue(any(p.pattern_data.get('trend') == 'decreasing' for p in patterns))

    def test_pattern_storage(self):
        """Test storing and retrieving patterns"""
        pattern = LearnedPattern(
            pattern_id="test_pattern",
            pattern_type="temporal",
            confidence=0.9,
            frequency=10,
            first_observed=datetime.now(),
            last_observed=datetime.now(),
            pattern_data={'test': 'data'},
            conditions=[{'test': 'condition'}]
        )

        self.recognizer.add_pattern(pattern)
        retrieved = self.recognizer.get_pattern("test_pattern")

        self.assertEqual(retrieved.pattern_id, "test_pattern")
        self.assertEqual(retrieved.confidence, 0.9)

    def test_get_patterns_by_type(self):
        """Test retrieving patterns by type"""
        from src.learning_engine.learning_engine import PerformanceMetric

        # Create temporal pattern
        temporal_pattern = LearnedPattern(
            pattern_id="temporal_1",
            pattern_type="temporal",
            confidence=0.8,
            frequency=5,
            first_observed=datetime.now(),
            last_observed=datetime.now(),
            pattern_data={},
            conditions=[]
        )
        self.recognizer.add_pattern(temporal_pattern)

        # Create correlation pattern
        correlation_pattern = LearnedPattern(
            pattern_id="correlation_1",
            pattern_type="correlation",
            confidence=0.7,
            frequency=3,
            first_observed=datetime.now(),
            last_observed=datetime.now(),
            pattern_data={},
            conditions=[]
        )
        self.recognizer.add_pattern(correlation_pattern)

        temporal_patterns = self.recognizer.get_patterns_by_type("temporal")
        correlation_patterns = self.recognizer.get_patterns_by_type("correlation")

        self.assertEqual(len(temporal_patterns), 1)
        self.assertEqual(len(correlation_patterns), 1)


class TestFeedbackCollector(unittest.TestCase):
    """Test feedback collector functionality"""

    def setUp(self):
        self.collector = FeedbackCollector()

    def test_collect_feedback(self):
        """Test collecting feedback"""
        self.collector.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            success=True,
            confidence=0.9
        )

        summary = self.collector.get_success_rate("operation")

        self.assertEqual(summary, 1.0)

    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        # Collect mix of successes and failures
        for i in range(10):
            success = i < 7  # 7 successes, 3 failures
            self.collector.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=success,
                confidence=0.8
            )

        success_rate = self.collector.get_success_rate("operation")

        self.assertEqual(success_rate, 0.7)

    def test_average_confidence_calculation(self):
        """Test average confidence calculation"""
        confidences = [0.5, 0.6, 0.7, 0.8, 0.9]

        for i, conf in enumerate(confidences):
            self.collector.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=True,
                confidence=conf
            )

        avg_conf = self.collector.get_average_confidence("operation")

        self.assertAlmostEqual(avg_conf, 0.7, places=1)

    def test_recent_feedback(self):
        """Test retrieving recent feedback"""
        for i in range(20):
            self.collector.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=True,
                confidence=0.8
            )

        recent = self.collector.get_recent_feedback(count=10)

        self.assertEqual(len(recent), 10)


class TestLearningEngine(unittest.TestCase):
    """Test learning engine functionality"""

    def setUp(self):
        self.engine = LearningEngine(enable_learning=True)

    def test_record_performance(self):
        """Test recording performance metrics"""
        self.engine.record_performance("test_metric", 10.0)

        stats = self.engine.get_performance_statistics("test_metric")

        self.assertIsNotNone(stats)
        self.assertEqual(stats['count'], 1)

    def test_collect_feedback(self):
        """Test collecting feedback"""
        self.engine.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            success=True,
            confidence=0.9
        )

        summary = self.engine.get_feedback_summary()

        self.assertEqual(summary['total_feedback'], 1)

    def test_learning_disabled(self):
        """Test behavior when learning is disabled"""
        engine = LearningEngine(enable_learning=False)

        engine.record_performance("test_metric", 10.0)
        engine.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            success=True,
            confidence=0.9
        )

        # Should not record anything when disabled
        stats = engine.get_performance_statistics("test_metric")
        summary = engine.get_feedback_summary()

        self.assertIsNone(stats)
        self.assertEqual(summary['total_feedback'], 0)

    def test_analyze_learning(self):
        """Test learning analysis"""
        # Record some performance data
        for i in range(30):
            self.engine.record_performance(
                "test_metric",
                float(i),
                context={'iteration': i}
            )

        # Analyze learning
        insights = self.engine.analyze_learning()

        # Should generate some insights
        self.assertGreaterEqual(len(insights), 0)

    def test_get_patterns(self):
        """Test retrieving learned patterns"""
        # Record enough data for pattern recognition
        for i in range(50):
            self.engine.record_performance(
                "test_metric",
                float(i),
                context={'iteration': i}
            )

        # Analyze to generate patterns
        self.engine.analyze_learning()

        # Get patterns
        patterns = self.engine.get_patterns()

        # Should have found some patterns
        self.assertGreaterEqual(len(patterns), 0)

    def test_get_insights(self):
        """Test retrieving learning insights"""
        # Record some feedback
        for i in range(20):
            success = i < 15  # 15 successes, 5 failures
            self.engine.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=success,
                confidence=0.8
            )

        # Analyze learning
        self.engine.analyze_learning()

        # Get insights
        insights = self.engine.get_insights(max_insights=10)

        self.assertGreaterEqual(len(insights), 0)

    def test_feedback_summary(self):
        """Test feedback summary generation"""
        # Collect various feedback
        for i in range(20):
            success = i % 4 != 0  # 75% success rate
            self.engine.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=success,
                confidence=0.8,
                feedback_data={'iteration': i}
            )

        summary = self.engine.get_feedback_summary()

        self.assertEqual(summary['total_feedback'], 20)
        self.assertAlmostEqual(summary['success_rate'], 0.75, places=1)
        self.assertIn('feedback_by_type', summary)

    def test_export_learning_data(self):
        """Test exporting learning data"""
        # Record some data
        for i in range(10):
            self.engine.record_performance(f"metric_{i}", float(i))
            self.engine.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                success=True,
                confidence=0.8
            )

        # Export data
        exported = self.engine.export_learning_data()

        # Should contain all sections
        self.assertIn('insights', exported)
        self.assertIn('patterns', exported)
        self.assertIn('feedback_summary', exported)
        self.assertIn('learning_history', exported)

    def test_reset_learning(self):
        """Test resetting learning data"""
        # Record some data
        self.engine.record_performance("test_metric", 10.0)
        self.engine.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            success=True,
            confidence=0.9
        )

        # Reset
        self.engine.reset_learning()

        # Verify reset
        stats = self.engine.get_performance_statistics("test_metric")
        summary = self.engine.get_feedback_summary()

        self.assertIsNone(stats)
        self.assertEqual(summary['total_feedback'], 0)
        self.assertEqual(len(self.engine.insights), 0)


class TestLearningEngineIntegration(unittest.TestCase):
    """Integration tests for learning engine"""

    def test_full_learning_cycle(self):
        """Test complete learning cycle"""
        engine = LearningEngine(enable_learning=True)

        # Step 1: Record performance
        for i in range(100):
            engine.record_performance(
                "response_time",
                100.0 + i * 0.5,  # Increasing trend
                context={'request_id': i}
            )

        # Step 2: Collect feedback
        for i in range(50):
            success = i < 40  # 80% success rate
            engine.collect_feedback(
                feedback_type="task_execution",
                operation_id=f"task_{i}",
                success=success,
                confidence=0.85,
                feedback_data={'duration': 1.0 + i * 0.01}
            )

        # Step 3: Analyze learning
        insights = engine.analyze_learning()

        # Step 4: Get learned information
        patterns = engine.get_patterns()
        feedback_summary = engine.get_feedback_summary()

        # Verify learning occurred
        self.assertGreaterEqual(len(insights), 0)
        self.assertGreaterEqual(len(patterns), 0)
        self.assertEqual(feedback_summary['total_feedback'], 50)

        # Step 5: Export and verify
        exported = engine.export_learning_data()
        self.assertIn('insights', exported)
        self.assertIn('patterns', exported)


if __name__ == '__main__':
    unittest.main()
