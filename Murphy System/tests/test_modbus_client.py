# Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1
"""Tests for Murphy-native Modbus client (PROT-002) — protocol error injection."""

import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from protocols.modbus_client import MurphyModbusClient


class TestModbusClientBasics(unittest.TestCase):
    """Modbus client in simulated/stub mode (no pymodbus installed)."""

    def test_import(self):
        self.assertIsNotNone(MurphyModbusClient)

    def test_instantiation(self):
        client = MurphyModbusClient(host="127.0.0.1")
        self.assertIsNotNone(client)

    def test_context_manager(self):
        with MurphyModbusClient(host="127.0.0.1") as client:
            self.assertIsNotNone(client)

    def test_connect_without_pymodbus(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.connect()
        self.assertIsInstance(result, bool)

    def test_read_holding_registers_simulated(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.read_holding_registers(address=0, count=10)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("simulated", False))

    def test_read_coils_simulated(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.read_coils(address=0, count=8)
        self.assertIsInstance(result, dict)

    def test_write_holding_registers_simulated(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.write_holding_registers(address=0, values=[42])
        self.assertIsInstance(result, dict)

    def test_disconnect(self):
        client = MurphyModbusClient(host="127.0.0.1")
        client.disconnect()  # should not raise


class TestModbusErrorInjection(unittest.TestCase):
    """Protocol error injection tests."""

    def test_negative_address(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.read_holding_registers(address=-1, count=1)
        self.assertIsInstance(result, dict)

    def test_zero_count(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.read_holding_registers(address=0, count=0)
        self.assertIsInstance(result, dict)

    def test_large_count(self):
        client = MurphyModbusClient(host="127.0.0.1")
        result = client.read_holding_registers(address=0, count=100000)
        self.assertIsInstance(result, dict)

    def test_custom_port(self):
        client = MurphyModbusClient(host="127.0.0.1", port=5020)
        self.assertEqual(client.port, 5020)


if __name__ == "__main__":
    unittest.main()
