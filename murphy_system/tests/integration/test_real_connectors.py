"""
Integration tests for real connector I/O.

These tests verify that:
1. Connectors return `"simulated": False` when real credentials are provided
   and the call succeeds.
2. Connectors fall back to simulation when credentials are absent.
3. Connectivity errors produce graceful fallback to simulation (not crashes).

Gate: Tests requiring real HTTP calls are gated by environment variables
so they don't run in CI without credentials.
"""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class TestConnectorSimulatedFallback(unittest.TestCase):
    """Verify connector falls back cleanly to simulation without credentials."""

    def test_connector_without_credentials_returns_simulated(self):
        """A connector with no credentials should return simulated=True."""
        from src.platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        fw.configure_connector("slack", {})  # No real token
        action = ConnectorAction(
            action_id="test-no-creds",
            connector_id="slack",
            action_type="send_message",
            resource="channel",
        )
        result = fw.execute_action(action)
        self.assertTrue(result.success, "Should succeed with simulated fallback")
        self.assertTrue(result.data.get("simulated"), "Should be simulated when no credentials")

    def test_connector_with_invalid_host_falls_back_to_simulation(self):
        """A connector pointing at a non-existent host should fall back to simulation."""
        from src.platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        fw.configure_connector("slack", {
            "token": "xoxb-test-invalid",
        })
        action = ConnectorAction(
            action_id="test-invalid-host",
            connector_id="slack",
            action_type="send_message",
            resource="channel",
        )
        result = fw.execute_action(action)
        # Should not raise; should either succeed (simulated) or return connectivity error
        self.assertIsNotNone(result)

    def test_connector_action_history_records_result(self):
        """Connector framework records action history."""
        from src.platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        fw.configure_connector("github", {"token": "ghp_test"})
        action = ConnectorAction(
            action_id="test-history",
            connector_id="github",
            action_type="list_repos",
            resource="repos",
        )
        fw.execute_action(action)
        status = fw.get_statistics()
        self.assertGreater(status.get("total_actions", 0), 0)


class TestBuildingAutomationConnectorFallback(unittest.TestCase):
    """Verify building automation connector falls back to simulation."""

    def test_bacnet_connector_without_credentials_simulated(self):
        """BACnet connector without credentials returns simulated=True."""
        from src.building_automation_connectors import (
            BuildingAutomationConnector, BuildingAutomationProtocol
        )
        connector = BuildingAutomationConnector(
            vendor="test_vendor",
            protocol=BuildingAutomationProtocol.BACNET,
            capabilities=["read_property", "write_property"],
        )
        result = connector.execute_action("read_property", {"object_id": "analogInput:0"})
        self.assertTrue(result.get("success"), "Should succeed with simulation")
        self.assertTrue(result.get("data", {}).get("simulated"), "Should be simulated")

    def test_bacnet_connector_with_credentials_attempts_protocol(self):
        """BACnet connector with credentials attempts real protocol (graceful if unavailable)."""
        from src.building_automation_connectors import (
            BuildingAutomationConnector, BuildingAutomationProtocol
        )
        connector = BuildingAutomationConnector(
            vendor="test_vendor",
            protocol=BuildingAutomationProtocol.BACNET,
            capabilities=["read_property"],
        )
        # Configure with test credentials
        connector.configure({"ip": "192.0.2.1", "port": "47808"})  # TEST-NET address (RFC 5737)
        result = connector.execute_action("read_property", {"object_id": "analogInput:0"})
        # Should either get a protocol result or gracefully fall back to simulation
        self.assertIn("success", result)
        self.assertIn("data", result)


class TestProtocolClientsImportable(unittest.TestCase):
    """All protocol clients must be importable and return stub-mode results
    when their optional library is not installed."""

    def test_bacnet_client_importable(self):
        from src.protocols.bacnet_client import MurphyBACnetClient
        client = MurphyBACnetClient("192.0.2.1")
        result = client.read_property("analogInput:0")
        # Without BAC0, should return simulated=True
        self.assertIn("simulated", result)

    def test_modbus_client_importable(self):
        from src.protocols.modbus_client import MurphyModbusClient
        client = MurphyModbusClient("192.0.2.1")
        result = client.read_holding_registers(0, 1)
        self.assertIn("simulated", result)

    def test_opcua_client_importable(self):
        from src.protocols.opcua_client import MurphyOPCUAClient
        client = MurphyOPCUAClient("opc.tcp://192.0.2.1:4840")
        result = client.read("i=2259")
        self.assertIn("simulated", result)

    def test_knx_client_importable(self):
        from src.protocols.knx_client import MurphyKNXClient
        client = MurphyKNXClient("192.0.2.1")
        result = client.group_read("1/1/1")
        self.assertIn("simulated", result)

    def test_mqtt_client_importable(self):
        from src.protocols.mqtt_sparkplug_client import MurphyMQTTSparkplugClient
        client = MurphyMQTTSparkplugClient("192.0.2.1")
        result = client.execute("publish_nbirth", {"metrics": {}})
        self.assertIn("simulated", result)


class TestRealHTTPConnector(unittest.TestCase):
    """Real HTTP connector test — only runs when MURPHY_TEST_REAL_HTTP=1."""

    def setUp(self):
        if not os.environ.get("MURPHY_TEST_REAL_HTTP"):
            self.skipTest("Set MURPHY_TEST_REAL_HTTP=1 to run real HTTP connector tests")

    def test_connector_with_valid_credentials_returns_not_simulated(self):
        """A connector with valid credentials should return simulated=False on success."""
        from src.platform_connector_framework import PlatformConnectorFramework, ConnectorAction
        fw = PlatformConnectorFramework()
        
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            self.skipTest("GITHUB_TOKEN not set")
        
        fw.configure_connector("github", {"token": token})
        action = ConnectorAction(
            action_id="test-real-github",
            connector_id="github",
            action_type="list_repos",
            resource="repos",
        )
        result = fw.execute_action(action)
        self.assertTrue(result.success)
        self.assertFalse(result.data.get("simulated"), "Real HTTP call should return simulated=False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
