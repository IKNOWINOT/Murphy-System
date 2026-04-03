"""
Murphy System Protocol Clients

Real protocol implementations for industrial and IoT connectivity.
All clients guard imports with try/except ImportError to allow
graceful operation when optional protocol libraries are not installed.

Environment variables
---------------------
MURPHY_ENABLED_PROTOCOLS : str
    Comma-separated list of protocols that must be available at startup.
    Example: ``bacnet,modbus,opcua``
    For each enabled protocol, the corresponding library must be importable.
    Raise ``ImportError`` at startup if a required library is missing.
    If empty or unset, no protocols are required (all fall back to stub).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

__all__ = [
    "MurphyBACnetClient",
    "MurphyModbusClient",
    "MurphyOPCUAClient",
    "MurphyKNXClient",
    "MurphyMQTTSparkplugClient",
    "MurphyOpenADRClient",
    "MurphyDNP3Client",
    "validate_protocol_dependencies",
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

try:
    from .openadr_client import MurphyOpenADRClient
except ImportError:
    MurphyOpenADRClient = None  # type: ignore[misc,assignment]

try:
    from .dnp3_client import MurphyDNP3Client
except ImportError:
    MurphyDNP3Client = None  # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# Protocol library availability map
# ---------------------------------------------------------------------------

_PROTOCOL_CLIENT_MAP = {
    "bacnet": ("MurphyBACnetClient", MurphyBACnetClient, "BAC0"),
    "modbus": ("MurphyModbusClient", MurphyModbusClient, "pymodbus"),
    "opcua": ("MurphyOPCUAClient", MurphyOPCUAClient, "asyncua"),
    "knx": ("MurphyKNXClient", MurphyKNXClient, "xknx"),
    "mqtt": ("MurphyMQTTSparkplugClient", MurphyMQTTSparkplugClient, "paho-mqtt"),
    "openadr": ("MurphyOpenADRClient", MurphyOpenADRClient, "aiohttp"),
    "dnp3": ("MurphyDNP3Client", MurphyDNP3Client, "socket"),
}


def validate_protocol_dependencies(enabled_protocols: str | None = None) -> None:
    """Validate that all enabled protocol libraries are importable.

    Reads ``MURPHY_ENABLED_PROTOCOLS`` (comma-separated) from the
    environment unless *enabled_protocols* is explicitly provided.
    For each enabled protocol, verifies that the corresponding library
    was successfully imported.  Raises ``ImportError`` listing all
    missing packages if any required library is absent.

    Protocols not in the enabled list fall back to stub mode silently.

    Args:
        enabled_protocols: Comma-separated list of protocol names to
            validate.  Defaults to the ``MURPHY_ENABLED_PROTOCOLS``
            environment variable.

    Raises:
        ImportError: When one or more enabled protocols have missing
            library dependencies.

    Example::

        # In startup code:
        validate_protocol_dependencies()  # reads MURPHY_ENABLED_PROTOCOLS
        # Or explicitly:
        validate_protocol_dependencies("bacnet,modbus")
    """
    if enabled_protocols is None:
        enabled_protocols = os.environ.get("MURPHY_ENABLED_PROTOCOLS", "")

    requested = [p.strip().lower() for p in enabled_protocols.split(",") if p.strip()]
    if not requested:
        logger.debug("validate_protocol_dependencies: no protocols enabled, skipping.")
        return

    missing: list[str] = []
    for proto in requested:
        entry = _PROTOCOL_CLIENT_MAP.get(proto)
        if entry is None:
            logger.warning(
                "validate_protocol_dependencies: unknown protocol %r — "
                "valid options: %s",
                proto,
                ", ".join(_PROTOCOL_CLIENT_MAP),
            )
            continue
        client_name, client_class, package_name = entry
        if client_class is None:
            missing.append(f"  {proto!r}: install '{package_name}' (pip install {package_name})")
        else:
            logger.debug(
                "validate_protocol_dependencies: %r OK (%s available)",
                proto,
                client_name,
            )

    if missing:
        raise ImportError(
            "The following enabled protocols are missing required libraries:\n"
            + "\n".join(missing)
            + "\nInstall the missing packages or remove the protocol from "
            "MURPHY_ENABLED_PROTOCOLS."
        )
