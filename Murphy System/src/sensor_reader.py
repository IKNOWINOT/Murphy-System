"""
IoT Sensor Reader — Modbus RTU/TCP (INC-19).

Provides async sensor data acquisition via Modbus protocol using
``pymodbus``.  Supports both TCP (network sensors) and simulated
(test/dev) backends.

When ``pymodbus`` is not installed, falls back to a deterministic
mock reader for development.

Environment variables:
    MODBUS_HOST     — Modbus TCP host (default: ``localhost``)
    MODBUS_PORT     — Modbus TCP port (default: ``502``)
    MODBUS_UNIT_ID  — Slave/unit ID (default: ``1``)
    MODBUS_MOCK     — Set to ``true`` for mock mode (default in dev)

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# pymodbus — lazy import (INC-19)
# ---------------------------------------------------------------------------
try:
    from pymodbus.client import ModbusTcpClient  # noqa: F401
    from pymodbus.exceptions import ModbusException  # noqa: F401
    _PYMODBUS_AVAILABLE = True
except ImportError:
    ModbusTcpClient = None  # type: ignore[assignment,misc]
    ModbusException = Exception  # type: ignore[assignment,misc]
    _PYMODBUS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SensorReading:
    """A single sensor data point."""

    reading_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sensor_id: str = ""
    register_address: int = 0
    value: float = 0.0
    unit: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorConfig:
    """Modbus sensor configuration."""

    host: str = "localhost"
    port: int = 502
    unit_id: int = 1
    mock_mode: bool = True
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "SensorConfig":
        """Build config from environment variables.

        When ``MODBUS_MOCK`` is not explicitly set, the default is:
        * ``True``  in ``development`` and ``test`` environments
        * ``False`` in ``staging`` and ``production`` environments
        """
        murphy_env = os.getenv("MURPHY_ENV", "development").lower()
        _production_envs = {"production", "staging"}
        _default_mock = "false" if murphy_env in _production_envs else "true"
        return cls(
            host=os.getenv("MODBUS_HOST", "localhost"),
            port=int(os.getenv("MODBUS_PORT", "502")),
            unit_id=int(os.getenv("MODBUS_UNIT_ID", "1")),
            mock_mode=os.getenv("MODBUS_MOCK", _default_mock).lower() == "true",
            timeout_seconds=float(os.getenv("MODBUS_TIMEOUT", "5.0")),
        )


# ---------------------------------------------------------------------------
# Sensor reader
# ---------------------------------------------------------------------------


class SensorReader:
    """Reads sensor data via Modbus TCP or mock backend.

    Usage::

        reader = SensorReader.from_env()
        reading = reader.read_register(address=0, count=1, sensor_id="temp_01")
        print(reading.value)
    """

    def __init__(self, config: SensorConfig) -> None:
        self._config = config
        self._client: Any = None

    @classmethod
    def from_env(cls) -> "SensorReader":
        """Factory: create from environment variables."""
        return cls(SensorConfig.from_env())

    def connect(self) -> bool:
        """Connect to the Modbus server (or init mock).

        Raises:
            ConnectionError: When ``mock_mode=False``, ``pymodbus`` is
                installed, and the Modbus TCP server is not reachable.
                This prevents silent sensor read failures in staging/production.
        """
        if self._config.mock_mode or not _PYMODBUS_AVAILABLE:
            logger.info(
                "Sensor reader in mock mode",
                extra={"host": self._config.host, "port": self._config.port},
            )
            return True

        try:
            self._client = ModbusTcpClient(
                host=self._config.host,
                port=self._config.port,
                timeout=self._config.timeout_seconds,
            )
            connected = self._client.connect()
            logger.info(
                "Modbus TCP connected: %s",
                connected,
                extra={"host": self._config.host, "port": self._config.port},
            )
            if not connected:
                raise ConnectionError(
                    f"Modbus TCP host {self._config.host}:{self._config.port} is not reachable. "
                    "Set MODBUS_MOCK=true or provide a valid MODBUS_HOST/MODBUS_PORT."
                )
            return connected
        except ConnectionError:
            raise
        except Exception as exc:
            logger.error(
                "Modbus connect failed: %s",
                exc,
                extra={"host": self._config.host, "error": str(exc)},
            )
            raise ConnectionError(
                f"Modbus TCP connection to {self._config.host}:{self._config.port} failed: {exc}. "
                "Set MODBUS_MOCK=true or provide a valid MODBUS_HOST/MODBUS_PORT."
            ) from exc

    def read_register(
        self,
        address: int = 0,
        count: int = 1,
        sensor_id: str = "",
        unit: str = "raw",
    ) -> SensorReading:
        """Read holding register(s) from Modbus device.

        Args:
            address: Starting register address.
            count: Number of registers to read.
            sensor_id: Human-readable sensor identifier.
            unit: Measurement unit label.

        Returns:
            A ``SensorReading`` with the register value.
        """
        if self._config.mock_mode or not _PYMODBUS_AVAILABLE or self._client is None:
            # Deterministic mock: address-based value for reproducible tests
            mock_value = float(address * 10 + count)
            logger.info(
                "Mock sensor read",
                extra={"address": address, "value": mock_value, "sensor_id": sensor_id},
            )
            return SensorReading(
                sensor_id=sensor_id or f"mock_{address}",
                register_address=address,
                value=mock_value,
                unit=unit,
                metadata={"source": "mock", "count": count},
            )

        try:
            result = self._client.read_holding_registers(
                address=address,
                count=count,
                slave=self._config.unit_id,
            )
            if result.isError():
                logger.error(
                    "Modbus read error at address %d: %s",
                    address,
                    result,
                    extra={"address": address},
                )
                return SensorReading(
                    sensor_id=sensor_id,
                    register_address=address,
                    value=0.0,
                    unit=unit,
                    metadata={"error": str(result)},
                )

            value = float(result.registers[0]) if result.registers else 0.0
            return SensorReading(
                sensor_id=sensor_id or f"reg_{address}",
                register_address=address,
                value=value,
                unit=unit,
                metadata={
                    "source": "modbus",
                    "registers": list(result.registers),
                    "count": count,
                },
            )

        except Exception as exc:
            logger.error(
                "Sensor read failed: %s",
                exc,
                extra={"address": address, "error": str(exc)},
            )
            return SensorReading(
                sensor_id=sensor_id,
                register_address=address,
                value=0.0,
                unit=unit,
                metadata={"error": str(exc)},
            )

    def read_multiple(
        self,
        addresses: List[int],
        sensor_prefix: str = "sensor",
        unit: str = "raw",
    ) -> List[SensorReading]:
        """Read multiple registers in sequence."""
        readings = []
        for addr in addresses:
            reading = self.read_register(
                address=addr,
                sensor_id=f"{sensor_prefix}_{addr}",
                unit=unit,
            )
            readings.append(reading)
        return readings

    def close(self) -> None:
        """Close the Modbus connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.debug("close error: %s", exc)
            self._client = None
            logger.info("Modbus connection closed")

    def get_status(self) -> Dict[str, Any]:
        """Return reader status."""
        return {
            "pymodbus_available": _PYMODBUS_AVAILABLE,
            "mock_mode": self._config.mock_mode,
            "host": self._config.host,
            "port": self._config.port,
            "connected": self._client is not None or self._config.mock_mode,
        }
