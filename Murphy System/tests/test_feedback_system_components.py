"""
Tests for Feedback System components

Tests:
- Feedback system functionality
- Feedback storage
- Feedback analysis
- Issue tracking
- Feedback summary generation
"""

import unittest
import time
from datetime import datetime, timedelta
from src.learning_engine import (
    FeedbackSystem,
    FeedbackStorage,
    FeedbackAnalyzer,
    FeedbackEntry,
    FeedbackAnalysis
)


class TestFeedbackStorage(unittest.TestCase):
    """Test feedback storage functionality"""

    def setUp(self):
        self.storage = FeedbackStorage(max_entries=100)

    def test_add_entry(self):
        """Test adding feedback entries"""
        entry = FeedbackEntry(
            feedback_id="fb_1",
            feedback_type="operation",
            operation_id="op_1",
            source="system",
            success=True,
            confidence=0.9,
            rating=None,
            timestamp=datetime.now(),
            feedback_data={},
            comments=None
        )

        self.storage.add_entry(entry)
        retrieved = self.storage.get_entry("fb_1")

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.feedback_id, "fb_1")
        self.assertEqual(retrieved.success, True)

    def test_get_entries_by_type(self):
        """Test retrieving entries by type"""
        # Add entries of different types
        for i in range(5):
            entry = FeedbackEntry(
                feedback_id=f"fb_{i}",
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=True,
                confidence=0.8,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            )
            self.storage.add_entry(entry)

        for i in range(5, 10):
            entry = FeedbackEntry(
                feedback_id=f"fb_{i}",
                feedback_type="decision",
                operation_id=f"op_{i}",
                source="system",
                success=True,
                confidence=0.8,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            )
            self.storage.add_entry(entry)

        # Get operation entries
        operation_entries = self.storage.get_entries_by_type("operation")

        self.assertEqual(len(operation_entries), 5)

    def test_get_entries_by_operation(self):
        """Test retrieving entries for a specific operation"""
        # Add feedback for same operation
        for i in range(3):
            entry = FeedbackEntry(
                feedback_id=f"fb_{i}",
                feedback_type="operation",
                operation_id="op_1",
                source="system",
                success=i < 2,
                confidence=0.8,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            )
            self.storage.add_entry(entry)

        # Get entries for operation
        op_entries = self.storage.get_entries_by_operation("op_1")

        self.assertEqual(len(op_entries), 3)

    def test_get_entries_in_range(self):
        """Test filtering entries by time range"""
        now = datetime.now()

        # Add entries at different times
        old_entry = FeedbackEntry(
            feedback_id="fb_old",
            feedback_type="operation",
            operation_id="op_1",
            source="system",
            success=True,
            confidence=0.9,
            rating=None,
            timestamp=now - timedelta(hours=2),
            feedback_data={},
            comments=None
        )

        recent_entry = FeedbackEntry(
            feedback_id="fb_recent",
            feedback_type="operation",
            operation_id="op_2",
            source="system",
            success=True,
            confidence=0.9,
            rating=None,
            timestamp=now - timedelta(minutes=30),
            feedback_data={},
            comments=None
        )

        self.storage.add_entry(old_entry)
        self.storage.add_entry(recent_entry)

        # Get entries from last hour
        start_time = now - timedelta(hours=1)
        end_time = now
        entries = self.storage.get_entries_in_range(start_time, end_time)

        # Should only get the recent entry
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].feedback_id, "fb_recent")

    def test_max_entries_limit(self):
        """Test that max entries limit is enforced"""
        storage = FeedbackStorage(max_entries=10)

        # Add more than max
        for i in range(20):
            entry = FeedbackEntry(
                feedback_id=f"fb_{i}",
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=True,
                confidence=0.8,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            )
            storage.add_entry(entry)

        # Should only keep last 10
        recent = storage.get_recent_entries(count=10)
        self.assertEqual(len(recent), 10)


class TestFeedbackAnalyzer(unittest.TestCase):
    """Test feedback analyzer functionality"""

    def setUp(self):
        self.analyzer = FeedbackAnalyzer()

    def test_analyze_empty_feedback(self):
        """Test analyzing empty feedback"""
        analysis = self.analyzer.analyze_feedback([])

        self.assertEqual(analysis.success_rate, 0.0)
        self.assertEqual(analysis.average_confidence, 0.0)
        self.assertEqual(len(analysis.issues), 0)

    def test_analyze_successful_feedback(self):
        """Test analyzing mostly successful feedback"""
        from src.learning_engine.feedback_system import FeedbackEntry

        entries = [
            FeedbackEntry(
                feedback_id=f"fb_{i}",
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=i < 9,  # 90% success rate
                confidence=0.85,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            )
            for i in range(10)
        ]

        analysis = self.analyzer.analyze_feedback(entries)

        self.assertAlmostEqual(analysis.success_rate, 0.9, places=1)
        self.assertAlmostEqual(analysis.average_confidence, 0.85, places=1)

    def test_identify_low_success_issues(self):
        """Test identifying operations with low success rate"""
        from src.learning_engine.feedback_system import FeedbackEntry

        # Create entries for operations with different success rates
        entries = []

        # Operation with low success rate
        for i in range(5):
            entries.append(FeedbackEntry(
                feedback_id=f"fb_bad_{i}",
                feedback_type="operation",
                operation_id="op_bad",
                source="system",
                success=i < 2,  # 40% success
                confidence=0.7,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            ))

        # Operation with high success rate
        for i in range(5):
            entries.append(FeedbackEntry(
                feedback_id=f"fb_good_{i}",
                feedback_type="operation",
                operation_id="op_good",
                source="system",
                success=True,
                confidence=0.9,
                rating=None,
                timestamp=datetime.now(),
                feedback_data={},
                comments=None
            ))

        analysis = self.analyzer.analyze_feedback(entries)

        # Should identify the low success rate operation
        self.assertTrue(any(i.get('operation_id') == 'op_bad' for i in analysis.issues))

    def test_track_issue(self):
        """Test tracking persistent issues"""
        issue = self.analyzer.track_issue(
            operation_id="op_1",
            issue_type="operation_failure",
            description="Operation keeps failing",
            severity="high"
        )

        self.assertEqual(issue.issue_id, "op_1_operation_failure")
        self.assertEqual(issue.frequency, 1)
        self.assertEqual(issue.severity, "high")

        # Track same issue again
        issue = self.analyzer.track_issue(
            operation_id="op_1",
            issue_type="operation_failure",
            description="Operation keeps failing",
            severity="high"
        )

        self.assertEqual(issue.frequency, 2)


class TestFeedbackSystem(unittest.TestCase):
    """Test feedback system functionality"""

    def setUp(self):
        self.system = FeedbackSystem(enable_feedback=True)

    def test_collect_feedback(self):
        """Test collecting feedback"""
        feedback_id = self.system.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            source="system",
            success=True,
            confidence=0.9
        )

        self.assertIsNotNone(feedback_id)
        self.assertTrue(feedback_id.startswith("feedback_"))

    def test_feedback_disabled(self):
        """Test behavior when feedback is disabled"""
        system = FeedbackSystem(enable_feedback=False)

        feedback_id = system.collect_feedback(
            feedback_type="operation",
            operation_id="op_1",
            source="system",
            success=True,
            confidence=0.9
        )

        # Should return empty string when disabled
        self.assertEqual(feedback_id, "")

    def test_analyze_recent_feedback(self):
        """Test analyzing recent feedback"""
        # Collect some feedback
        for i in range(20):
            success = i % 4 != 0  # 75% success rate
            self.system.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=success,
                confidence=0.8
            )

        # Analyze recent feedback
        analysis = self.system.analyze_recent_feedback(time_period="hour")

        self.assertEqual(analysis.feedback_type, "operation")
        self.assertAlmostEqual(analysis.success_rate, 0.75, places=1)
        self.assertGreaterEqual(len(analysis.recommendations), 0)

    def test_get_feedback_summary(self):
        """Test getting feedback summary"""
        # Collect various feedback
        for i in range(30):
            success = i % 3 != 0  # 67% success rate
            self.system.collect_feedback(
                feedback_type="operation" if i < 15 else "decision",
                operation_id=f"op_{i}",
                source="system",
                success=success,
                confidence=0.8,
                feedback_data={'iteration': i}
            )

        summary = self.system.get_feedback_summary()

        self.assertEqual(summary['total_entries'], 30)
        self.assertAlmostEqual(summary['success_rate'], 0.67, places=1)
        self.assertIn('by_type', summary)
        self.assertIn('by_source', summary)

    def test_get_tracked_issues(self):
        """Test getting tracked issues"""
        # Collect some failed operations
        for i in range(5):
            self.system.collect_feedback(
                feedback_type="operation",
                operation_id="op_1",
                source="system",
                success=i < 2,  # Only 2 successes
                confidence=0.7
            )

        # Get tracked issues
        issues = self.system.get_tracked_issues()

        # Should have tracked an issue for op_1
        self.assertGreater(len(issues), 0)

    def test_get_feedback_for_operation(self):
        """Test getting feedback for a specific operation"""
        # Collect feedback for specific operation
        for i in range(3):
            self.system.collect_feedback(
                feedback_type="operation",
                operation_id="op_1",
                source="system",
                success=True,
                confidence=0.9,
                comments=f"Attempt {i+1}"
            )

        # Get feedback for operation
        feedback_list = self.system.get_feedback_for_operation("op_1")

        self.assertEqual(len(feedback_list), 3)

    def test_export_feedback_data(self):
        """Test exporting feedback data"""
        # Collect some feedback
        for i in range(10):
            self.system.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=True,
                confidence=0.85
            )

        # Export data
        exported = self.system.export_feedback_data()

        # Should contain all sections
        self.assertIn('summary', exported)
        self.assertIn('issues', exported)
        self.assertIn('recent_entries', exported)

    def test_reset_feedback(self):
        """Test resetting feedback data"""
        # Collect some feedback
        for i in range(10):
            self.system.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i}",
                source="system",
                success=True,
                confidence=0.9
            )

        # Reset
        self.system.reset_feedback()

        # Verify reset
        summary = self.system.get_feedback_summary()

        self.assertEqual(summary['total_entries'], 0)


class TestFeedbackSystemIntegration(unittest.TestCase):
    """Integration tests for feedback system"""

    def test_full_feedback_cycle(self):
        """Test complete feedback cycle"""
        system = FeedbackSystem(enable_feedback=True)

        # Step 1: Collect feedback from various sources
        for i in range(50):
            success = i % 5 != 0  # 80% success rate
            source = "system" if i < 30 else "human"

            system.collect_feedback(
                feedback_type="operation",
                operation_id=f"op_{i % 10}",  # 10 different operations
                source=source,
                success=success,
                confidence=0.8 + (i % 5) * 0.02,
                feedback_data={'duration': 1.0 + i * 0.01}
            )

        # Step 2: Analyze recent feedback
        analysis = system.analyze_recent_feedback(time_period="hour")

        # Step 3: Get summary
        summary = system.get_feedback_summary()

        # Step 4: Get tracked issues
        issues = system.get_tracked_issues()

        # Verify results
        self.assertEqual(summary['total_entries'], 50)
        self.assertAlmostEqual(summary['success_rate'], 0.8, places=1)
        self.assertGreaterEqual(len(analysis.recommendations), 0)

        # Step 5: Export and verify
        exported = system.export_feedback_data()
        self.assertIn('summary', exported)
        self.assertIn('issues', exported)
        self.assertEqual(len(exported['recent_entries']), 50)


if __name__ == '__main__':
    unittest.main()
