# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for Murphy-native BACnet client (PROT-001) — protocol error injection."""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from protocols.bacnet_client import MurphyBACnetClient


class TestBACnetClientBasics(unittest.TestCase):
    """BACnet client in simulated/stub mode (no BAC0 installed)."""

    def test_import(self):
        self.assertIsNotNone(MurphyBACnetClient)

    def test_instantiation(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        self.assertIsNotNone(client)

    def test_context_manager(self):
        with MurphyBACnetClient(ip="127.0.0.1") as client:
            self.assertIsNotNone(client)

    def test_connect_without_bac0(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        result = client.connect()
        # Without BAC0, connect returns False
        self.assertIsInstance(result, bool)

    def test_read_property_simulated(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        result = client.read_property("analogInput:0", "presentValue")
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("simulated", False))

    def test_write_property_simulated(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        result = client.write_property("analogOutput:0", "presentValue", 72.0)
        self.assertIsInstance(result, dict)

    def test_who_is_simulated(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        result = client.who_is()
        self.assertIsInstance(result, (dict, list))

    def test_disconnect(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        client.disconnect()  # should not raise


class TestBACnetErrorInjection(unittest.TestCase):
    """Protocol error injection tests."""

    def test_empty_object_id(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        result = client.read_property("", "presentValue")
        self.assertIsInstance(result, dict)

    def test_custom_port(self):
        client = MurphyBACnetClient(ip="127.0.0.1", port=12345)
        self.assertEqual(client.port, 12345)

    def test_multiple_reads(self):
        client = MurphyBACnetClient(ip="127.0.0.1")
        for i in range(10):
            result = client.read_property(f"analogInput:{i}")
            self.assertIsInstance(result, dict)


if __name__ == "__main__":
    unittest.main()
