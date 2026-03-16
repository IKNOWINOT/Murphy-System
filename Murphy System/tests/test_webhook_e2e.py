"""
Webhook E2E Test — inbound → trigger → execute (INC-12).

Proves the full webhook pipeline: an inbound event arrives, matches a
subscription, triggers delivery, and the delivery callback executes.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys
import threading

import pytest

_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")

from webhook_dispatcher import WebhookDispatcher, DeliveryStatus


class TestWebhookE2E:
    """End-to-end: inbound event → subscription match → delivery callback."""

    def test_inbound_trigger_execute(self) -> None:
        """INC-12: full pipeline proof — inbound → trigger → execute."""
        delivered: list = []

        def delivery_callback(url: str, payload: dict, headers: dict, timeout: float) -> tuple:
            delivered.append({"url": url, "payload": payload, "headers": headers})
            return (200, '{"ok":true}')

        dispatcher = WebhookDispatcher(delivery_callback=delivery_callback)

        # 1. Register a subscription for "sensor.alert" events
        sub = dispatcher.register_subscription(
            name="sensor-alert-hook",
            url="https://hooks.example.com/sensor-alerts",
            event_types=["sensor.alert"],
            secret="test-secret-123",
        )
        assert sub is not None

        # 2. Dispatch an inbound event
        records = dispatcher.dispatch_event(
            event_type="sensor.alert",
            payload={"sensor_id": "temp_01", "value": 95.5, "threshold": 90.0},
            source="murphy_sensor_reader",
        )

        # 3. Verify the event was matched and dispatched
        assert len(records) >= 1
        assert records[0].final_status == DeliveryStatus.DELIVERED

        # 4. Verify the delivery callback was actually executed
        assert len(delivered) >= 1, "Delivery callback was never called"
        delivery = delivered[0]
        assert delivery["url"] == "https://hooks.example.com/sensor-alerts"
        assert delivery["payload"]["event_type"] == "sensor.alert"

        # 5. Verify HMAC signature header was included
        headers_lower = {k.lower(): v for k, v in delivery["headers"].items()}
        assert "x-murphy-signature" in headers_lower

    def test_unmatched_event_no_delivery(self) -> None:
        """Events with no matching subscription should not trigger delivery."""
        delivered: list = []

        def delivery_callback(url: str, payload: dict, headers: dict, timeout: float) -> tuple:
            delivered.append(True)
            return (200, '{}')

        dispatcher = WebhookDispatcher(delivery_callback=delivery_callback)
        dispatcher.register_subscription(
            name="alerts-only",
            url="https://hooks.example.com/only-alerts",
            event_types=["alert.critical"],
        )

        # Dispatch a non-matching event
        records = dispatcher.dispatch_event(
            event_type="info.log",
            payload={"message": "test"},
        )
        assert len(records) == 0
        assert len(delivered) == 0, "Should not deliver for unmatched events"

    def test_wildcard_subscription(self) -> None:
        """Wildcard subscriptions should match any event type."""
        delivered: list = []

        def delivery_callback(url: str, payload: dict, headers: dict, timeout: float) -> tuple:
            delivered.append(payload)
            return (200, '{}')

        dispatcher = WebhookDispatcher(delivery_callback=delivery_callback)
        dispatcher.register_subscription(
            name="catch-all",
            url="https://hooks.example.com/all",
            event_types=["*"],
        )

        records = dispatcher.dispatch_event(event_type="any.event", payload={"x": 1})
        assert len(records) >= 1
        assert len(delivered) >= 1

    def test_multiple_subscriptions_same_event(self) -> None:
        """Multiple subscriptions for the same event type should all fire."""
        delivered: list = []

        def delivery_callback(url: str, payload: dict, headers: dict, timeout: float) -> tuple:
            delivered.append(url)
            return (200, '{}')

        dispatcher = WebhookDispatcher(delivery_callback=delivery_callback)
        dispatcher.register_subscription(
            name="hook-a", url="https://a.example.com", event_types=["deploy"]
        )
        dispatcher.register_subscription(
            name="hook-b", url="https://b.example.com", event_types=["deploy"]
        )

        records = dispatcher.dispatch_event(event_type="deploy", payload={})
        assert len(records) >= 2
        assert len(delivered) >= 2
