"""
Murphy System Protocol Clients

Real protocol implementations for industrial and IoT connectivity.
All clients guard imports with try/except ImportError to allow
graceful operation when optional protocol libraries are not installed.
"""

from __future__ import annotations

__all__ = [
    "MurphyBACnetClient",
    "MurphyModbusClient",
    "MurphyOPCUAClient",
    "MurphyKNXClient",
    "MurphyMQTTSparkplugClient",
]

try:
    from .bacnet_client import MurphyBACnetClient
except ImportError:
    MurphyBACnetClient = None  # type: ignore[misc,assignment]

try:
    from .modbus_client import MurphyModbusClient
except ImportError:
    MurphyModbusClient = None  # type: ignore[misc,assignment]

try:
    from .opcua_client import MurphyOPCUAClient
except ImportError:
    MurphyOPCUAClient = None  # type: ignore[misc,assignment]

try:
    from .knx_client import MurphyKNXClient
except ImportError:
    MurphyKNXClient = None  # type: ignore[misc,assignment]

try:
    from .mqtt_sparkplug_client import MurphyMQTTSparkplugClient
except ImportError:
    MurphyMQTTSparkplugClient = None  # type: ignore[misc,assignment]
