"""
Tests for IoT Sensor Reader — Modbus (INC-19).

Tests run in mock mode (no Modbus hardware required).

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import os
import sys

import pytest

_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
if os.path.abspath(_src_dir) not in sys.path:
    sys.path.insert(0, os.path.abspath(_src_dir))

from sensor_reader import SensorConfig, SensorReader, SensorReading


class TestSensorConfig:
    """Tests for sensor configuration."""

    def test_default_config(self) -> None:
        cfg = SensorConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 502
        assert cfg.mock_mode is True

    def test_from_env(self) -> None:
        from unittest.mock import patch
        env = {"MODBUS_HOST": "192.168.1.100", "MODBUS_PORT": "5020", "MODBUS_MOCK": "false"}
        with patch.dict(os.environ, env, clear=False):
            cfg = SensorConfig.from_env()
        assert cfg.host == "192.168.1.100"
        assert cfg.port == 5020
        assert cfg.mock_mode is False


class TestSensorReaderMock:
    """Sensor reader tests in mock mode."""

    def test_connect_mock(self) -> None:
        reader = SensorReader(SensorConfig(mock_mode=True))
        assert reader.connect() is True

    def test_read_register(self) -> None:
        reader = SensorReader(SensorConfig(mock_mode=True))
        reader.connect()
        reading = reader.read_register(address=10, sensor_id="temp_01", unit="°C")
        assert isinstance(reading, SensorReading)
        assert reading.sensor_id == "temp_01"
        assert reading.value == 101.0  # address=10, count=1 → 10*10+1=101
        assert reading.unit == "°C"

    def test_read_multiple(self) -> None:
        reader = SensorReader(SensorConfig(mock_mode=True))
        reader.connect()
        readings = reader.read_multiple(
            addresses=[0, 5, 10],
            sensor_prefix="factory",
            unit="psi",
        )
        assert len(readings) == 3
        assert readings[0].sensor_id == "factory_0"
        assert readings[1].sensor_id == "factory_5"
        assert readings[2].sensor_id == "factory_10"

    def test_deterministic_mock_values(self) -> None:
        """Mock values are deterministic (address-based) for reproducible tests."""
        reader = SensorReader(SensorConfig(mock_mode=True))
        reader.connect()
        r1 = reader.read_register(address=0, count=1)
        r2 = reader.read_register(address=0, count=1)
        assert r1.value == r2.value

    def test_reader_status(self) -> None:
        reader = SensorReader(SensorConfig(mock_mode=True))
        status = reader.get_status()
        assert status["mock_mode"] is True
        assert "pymodbus_available" in status

    def test_close(self) -> None:
        reader = SensorReader(SensorConfig(mock_mode=True))
        reader.connect()
        reader.close()  # Should not raise


class TestPymodbusInRequirements:
    """INC-19 signal: pymodbus must be in requirements.txt."""

    def test_pymodbus_in_requirements(self) -> None:
        req_path = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        with open(req_path) as f:
            content = f.read()
        assert "pymodbus" in content, "pymodbus must be listed in requirements.txt"
