"""
Tests for event_backbone.py — bounded history & DLQ

Closes Gap 6: EventBackbone._history and _dlq grew without limits.

Proves:
- _history is capped at _max_history_size (CWE-770 mitigation)
- _dlq is capped at _max_dlq_size (CWE-770 mitigation)
- get_event_history still returns correct results after cap enforcement
- Normal event flow is unaffected
"""

import os
import unittest


from event_backbone import EventBackbone, EventType


class TestEventHistoryBounded(unittest.TestCase):
    """_history must not grow without limit."""

    def test_history_is_capped(self):
        """After exceeding _max_history_size, history is trimmed."""
        bb = EventBackbone()
        bb._max_history_size = 50  # small cap for testing

        # Subscribe a no-op handler so events get processed
        bb.subscribe(EventType.TASK_SUBMITTED, lambda e: None)

        for i in range(60):
            bb.publish(EventType.TASK_SUBMITTED, {"i": i})

        bb.process_pending()
        self.assertLessEqual(len(bb._history), 50)

    def test_get_event_history_after_cap(self):
        """get_event_history works correctly after the cap trims entries."""
        bb = EventBackbone()
        bb._max_history_size = 20

        bb.subscribe(EventType.TASK_COMPLETED, lambda e: None)
        for i in range(30):
            bb.publish(EventType.TASK_COMPLETED, {"i": i})
        bb.process_pending()

        # We should get at most 20 results
        history = bb.get_event_history(limit=100)
        self.assertLessEqual(len(history), 20)

    def test_history_preserves_recent_entries(self):
        """After trimming, the most recent entries must survive."""
        bb = EventBackbone()
        bb._max_history_size = 10

        bb.subscribe(EventType.AUDIT_LOGGED, lambda e: None)
        for i in range(15):
            bb.publish(EventType.AUDIT_LOGGED, {"seq": i})
        bb.process_pending()

        history = bb.get_event_history(limit=100)
        # The last entry should be seq=14
        last_payload = history[-1]["payload"]
        self.assertEqual(last_payload["seq"], 14)


class TestDLQBounded(unittest.TestCase):
    """Dead letter queue must not grow without limit."""

    def test_dlq_is_capped(self):
        """After exceeding _max_dlq_size, DLQ is trimmed."""
        bb = EventBackbone()
        bb._max_dlq_size = 10

        def always_fail(event):
            raise RuntimeError("handler error")

        bb.subscribe(EventType.TASK_FAILED, always_fail)

        # Publish enough events that all exceed max_retries (3) and go to DLQ
        for i in range(15):
            bb.publish(EventType.TASK_FAILED, {"i": i})

        # Process all — each event retries 3 times then DLQs
        for _ in range(5):  # multiple passes to exhaust retries
            bb.process_pending()

        dlq = bb.get_dead_letter_queue()
        self.assertLessEqual(len(dlq), 10)


class TestNormalEventFlow(unittest.TestCase):
    """Normal publish → subscribe → process flow is preserved after fixes."""

    def test_publish_subscribe_process(self):
        bb = EventBackbone()
        received = []
        bb.subscribe(EventType.TASK_SUBMITTED, lambda e: received.append(e.payload))
        bb.publish(EventType.TASK_SUBMITTED, {"msg": "hello"})
        processed = bb.process_pending()
        self.assertEqual(processed, 1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["msg"], "hello")

    def test_status_reflects_counts(self):
        bb = EventBackbone()
        bb.subscribe(EventType.TASK_SUBMITTED, lambda e: None)
        bb.publish(EventType.TASK_SUBMITTED, {"a": 1})
        bb.process_pending()
        status = bb.get_status()
        self.assertEqual(status["events_published"], 1)
        self.assertEqual(status["events_processed"], 1)


if __name__ == "__main__":
    unittest.main()
