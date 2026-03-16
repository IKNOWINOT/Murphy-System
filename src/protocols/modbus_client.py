"""
Modbus Client for Murphy System

Real Modbus TCP/RTU implementation using the pymodbus library.
Guards the import so the module can be used without pymodbus installed.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from pymodbus.client import ModbusTcpClient  # type: ignore[import]
    _PYMODBUS_AVAILABLE = True
except ImportError:
    try:
        from pymodbus.client.sync import ModbusTcpClient  # type: ignore[import]
        _PYMODBUS_AVAILABLE = True
    except ImportError:
        _PYMODBUS_AVAILABLE = False
        logger.debug("pymodbus not installed — Modbus client will use stub mode")


class MurphyModbusClient:
    """Modbus TCP/RTU client using pymodbus.

    Falls back to stub responses when pymodbus is not installed.
    """

    DEFAULT_PORT = 502

    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._client = None

    def connect(self) -> bool:
        if not _PYMODBUS_AVAILABLE:
            return False
        try:
            self._client = ModbusTcpClient(host=self.host, port=self.port)
            result = self._client.connect()
            return bool(result)
        except Exception as exc:
            logger.error("Modbus connection failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.debug("Modbus disconnect cleanup: %s", exc)
            self._client = None

    def read_holding_registers(self, address: int, count: int = 1, unit: int = 1) -> Dict[str, Any]:
        if not _PYMODBUS_AVAILABLE or self._client is None:
            return {"registers": [], "address": address, "count": count, "simulated": True}
        try:
            response = self._client.read_holding_registers(address, count, unit=unit)
            if response.isError():
                return {"registers": [], "address": address, "error": str(response), "simulated": False}
            return {"registers": list(response.registers), "address": address, "count": count, "simulated": False}
        except Exception as exc:
            logger.warning("Modbus read_holding_registers failed: %s", exc)
            return {"registers": [], "address": address, "error": str(exc), "simulated": False}

    def write_holding_registers(self, address: int, values: List[int], unit: int = 1) -> Dict[str, Any]:
        if not _PYMODBUS_AVAILABLE or self._client is None:
            return {"success": False, "simulated": True, "reason": "modbus_unavailable"}
        try:
            response = self._client.write_registers(address, values, unit=unit)
            return {"success": not response.isError(), "address": address, "simulated": False}
        except Exception as exc:
            logger.warning("Modbus write_holding_registers failed: %s", exc)
            return {"success": False, "error": str(exc), "simulated": False}

    def read_coils(self, address: int, count: int = 1, unit: int = 1) -> Dict[str, Any]:
        if not _PYMODBUS_AVAILABLE or self._client is None:
            return {"bits": [], "address": address, "simulated": True}
        try:
            response = self._client.read_coils(address, count, unit=unit)
            if response.isError():
                return {"bits": [], "address": address, "error": str(response), "simulated": False}
            return {"bits": list(response.bits[:count]), "address": address, "simulated": False}
        except Exception as exc:
            logger.warning("Modbus read_coils failed: %s", exc)
            return {"bits": [], "address": address, "error": str(exc), "simulated": False}

    def write_coils(self, address: int, values: List[bool], unit: int = 1) -> Dict[str, Any]:
        if not _PYMODBUS_AVAILABLE or self._client is None:
            return {"success": False, "simulated": True, "reason": "modbus_unavailable"}
        try:
            response = self._client.write_coils(address, values, unit=unit)
            return {"success": not response.isError(), "address": address, "simulated": False}
        except Exception as exc:
            logger.warning("Modbus write_coils failed: %s", exc)
            return {"success": False, "error": str(exc), "simulated": False}

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        dispatch = {
            "read_holding_registers": lambda p: self.read_holding_registers(p.get("address", 0), p.get("count", 1), p.get("unit", 1)),
            "write_holding_registers": lambda p: self.write_holding_registers(p.get("address", 0), p.get("values", []), p.get("unit", 1)),
            "read_coils": lambda p: self.read_coils(p.get("address", 0), p.get("count", 1), p.get("unit", 1)),
            "write_coils": lambda p: self.write_coils(p.get("address", 0), p.get("values", []), p.get("unit", 1)),
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown Modbus action: {action_name}", "simulated": not _PYMODBUS_AVAILABLE}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
