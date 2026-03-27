"""
SCADA / Industrial Control Systems Integration — Murphy System World Model Connector.

Provides a unified interface for:
  - Modbus TCP/RTU (via pymodbus or stub)
  - BACnet IP (via BAC0 or stub)
  - OPC UA (via asyncua or stub)
  - DNP3 (stub — requires licensed library)
  - EtherNet/IP / Allen-Bradley (stub — requires pycomm3)
  - IEC 61850 (stub — requires licensed library)

For each protocol, uses the corresponding protocol client in src/protocols/
and gracefully degrades to a stub when the underlying library is not installed.

No API credentials required for local connections (IP/port only).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SCADAConnector:
    """
    Murphy System SCADA connector — unified industrial protocol gateway.

    Supports Modbus TCP, BACnet IP, OPC UA, and provides stubs for
    DNP3 / EtherNet/IP / IEC 61850.
    """

    INTEGRATION_NAME = "SCADA / ICS"
    FREE_TIER = True
    DOCUMENTATION_URL = "https://docs.murphysystem.com/integrations/scada"

    def __init__(
        self,
        modbus_host: Optional[str] = None,
        modbus_port: int = 502,
        bacnet_ip: Optional[str] = None,
        opcua_url: Optional[str] = None,
        credentials: Optional[Dict[str, str]] = None,
    ) -> None:
        self._modbus_host = modbus_host or os.environ.get("SCADA_MODBUS_HOST", "")
        self._modbus_port = modbus_port
        self._bacnet_ip = bacnet_ip or os.environ.get("SCADA_BACNET_IP", "")
        self._opcua_url = opcua_url or os.environ.get("SCADA_OPCUA_URL", "")
        self._credentials = credentials or {}
        self._lock = threading.Lock()
        self._request_count = 0
        self._error_count = 0

        # Lazy-load protocol clients
        self._modbus_client = None
        self._bacnet_client = None
        self._opcua_client = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self._modbus_host or self._bacnet_ip or self._opcua_url)

    def get_status(self) -> Dict[str, Any]:
        return {
            "integration": self.INTEGRATION_NAME,
            "protocols": {
                "modbus_tcp": {"configured": bool(self._modbus_host),
                               "host": self._modbus_host, "port": self._modbus_port},
                "bacnet_ip": {"configured": bool(self._bacnet_ip),
                              "host": self._bacnet_ip},
                "opcua": {"configured": bool(self._opcua_url),
                          "url": self._opcua_url},
            },
            "request_count": self._request_count,
            "error_count": self._error_count,
        }

    # ------------------------------------------------------------------
    # Modbus TCP
    # ------------------------------------------------------------------

    def _get_modbus_client(self):
        if self._modbus_client is None:
            try:
                from modbus_client import MurphyModbusClient  # type: ignore
                self._modbus_client = MurphyModbusClient(
                    host=self._modbus_host, port=self._modbus_port)
            except Exception as exc:
                logger.warning("Modbus client unavailable: %s", exc)
        return self._modbus_client

    def modbus_read_holding_registers(self, address: int, count: int = 1,
                                      unit: int = 1) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        if not self._modbus_host:
            return {"success": False, "error": "Modbus host not configured — set SCADA_MODBUS_HOST",
                    "configured": False}
        client = self._get_modbus_client()
        if client is None:
            return {"success": False, "error": "Modbus host not configured or pymodbus unavailable",
                    "configured": False}
        return client.read_holding_registers(address, count, unit)

    def modbus_write_register(self, address: int, value: int,
                              unit: int = 1) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        if not self._modbus_host:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        client = self._get_modbus_client()
        if client is None:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        return client.write_register(address, value, unit)

    def modbus_read_coils(self, address: int, count: int = 1,
                          unit: int = 1) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        if not self._modbus_host:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        client = self._get_modbus_client()
        if client is None:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        return client.read_coils(address, count, unit)

    def modbus_write_coil(self, address: int, value: bool,
                          unit: int = 1) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        if not self._modbus_host:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        client = self._get_modbus_client()
        if client is None:
            return {"success": False, "error": "Modbus host not configured",
                    "configured": False}
        return client.write_coil(address, value, unit)

    # ------------------------------------------------------------------
    # BACnet
    # ------------------------------------------------------------------

    def _get_bacnet_client(self):
        if self._bacnet_client is None:
            try:
                from bacnet_client import MurphyBACnetClient  # type: ignore
                self._bacnet_client = MurphyBACnetClient(ip=self._bacnet_ip)
            except Exception as exc:
                logger.warning("BACnet client unavailable: %s", exc)
        return self._bacnet_client

    def bacnet_read_property(self, object_id: str, property_id: str) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_bacnet_client()
        if client is None:
            return {"value": None, "object_id": object_id, "property_id": property_id,
                    "simulated": True, "error": "BACnet not configured or BAC0 unavailable"}
        return client.read_property(object_id, property_id)

    def bacnet_write_property(self, object_id: str, property_id: str,
                              value: Any) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_bacnet_client()
        if client is None:
            return {"success": False, "simulated": True,
                    "error": "BACnet not configured or BAC0 unavailable"}
        return client.write_property(object_id, property_id, value)

    def bacnet_who_is(self) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_bacnet_client()
        if client is None:
            return {"devices": [], "simulated": True,
                    "error": "BACnet not configured or BAC0 unavailable"}
        return {"devices": client.who_is(), "simulated": False}

    # ------------------------------------------------------------------
    # OPC UA
    # ------------------------------------------------------------------

    def _get_opcua_client(self):
        if self._opcua_client is None:
            try:
                from opcua_client import MurphyOPCUAClient  # type: ignore
                self._opcua_client = MurphyOPCUAClient(url=self._opcua_url)
            except Exception as exc:
                logger.warning("OPC UA client unavailable: %s", exc)
        return self._opcua_client

    def opcua_browse(self, node_id: str = "i=84") -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_opcua_client()
        if client is None:
            return {"nodes": [], "simulated": True,
                    "error": "OPC UA URL not configured or asyncua unavailable"}
        return client.browse(node_id)

    def opcua_read_node(self, node_id: str) -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_opcua_client()
        if client is None:
            return {"value": None, "node_id": node_id, "simulated": True,
                    "error": "OPC UA URL not configured or asyncua unavailable"}
        return client.read_node(node_id)

    def opcua_write_node(self, node_id: str, value: Any,
                         data_type: str = "Float") -> Dict[str, Any]:
        with self._lock:
            self._request_count += 1
        client = self._get_opcua_client()
        if client is None:
            return {"success": False, "simulated": True,
                    "error": "OPC UA URL not configured or asyncua unavailable"}
        return client.write_node(node_id, value, data_type)

    # ------------------------------------------------------------------
    # Universal action dispatcher
    # ------------------------------------------------------------------

    def execute_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        dispatch = {
            "modbus_read_holding_registers": lambda p: self.modbus_read_holding_registers(
                p.get("address", 0), p.get("count", 1), p.get("unit", 1)),
            "modbus_write_register": lambda p: self.modbus_write_register(
                p["address"], p["value"], p.get("unit", 1)),
            "modbus_read_coils": lambda p: self.modbus_read_coils(
                p.get("address", 0), p.get("count", 1), p.get("unit", 1)),
            "modbus_write_coil": lambda p: self.modbus_write_coil(
                p["address"], p["value"], p.get("unit", 1)),
            "bacnet_read_property": lambda p: self.bacnet_read_property(
                p["object_id"], p["property_id"]),
            "bacnet_write_property": lambda p: self.bacnet_write_property(
                p["object_id"], p["property_id"], p["value"]),
            "bacnet_who_is": lambda p: self.bacnet_who_is(),
            "opcua_browse": lambda p: self.opcua_browse(p.get("node_id", "i=84")),
            "opcua_read_node": lambda p: self.opcua_read_node(p["node_id"]),
            "opcua_write_node": lambda p: self.opcua_write_node(
                p["node_id"], p["value"], p.get("data_type", "Float")),
            "health_check": lambda p: self.health_check(),
        }
        handler = dispatch.get(action)
        if handler is None:
            return {"success": False, "error": f"Unknown SCADA action: {action}"}
        return handler(params)

    def health_check(self) -> Dict[str, Any]:
        return {
            "integration": self.INTEGRATION_NAME,
            "configured": self.is_configured(),
            **self.get_status(),
        }
