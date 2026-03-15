"""
BACnet Client for Murphy System

Real BACnet/IP protocol implementation using the BAC0 library.
Guards the import so the module can be imported even when BAC0 is not installed.

Usage:
    try:
        from src.protocols.bacnet_client import MurphyBACnetClient
        # client = MurphyBACnetClient("<device-ip>", port=47808)
        value = client.read_property("analogInput:0", "presentValue")
    except ImportError:
        pass  # BAC0 not installed
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import BAC0  # type: ignore[import]
    _BAC0_AVAILABLE = True
except ImportError:
    _BAC0_AVAILABLE = False
    logger.debug("BAC0 not installed — BACnet client will use stub mode")


class MurphyBACnetClient:
    """BACnet/IP protocol client using BAC0.

    Falls back to stub responses when BAC0 is not installed so that
    the rest of the system can operate without industrial hardware.
    """

    DEFAULT_PORT = 47808

    def __init__(self, ip: str, port: int = DEFAULT_PORT):
        self.ip = ip
        self.port = port
        self._bacnet = None
        self._connected = False

    def connect(self) -> bool:
        """Open a BACnet/IP connection."""
        if not _BAC0_AVAILABLE:
            logger.debug("BAC0 unavailable — BACnet connect is a no-op")
            return False
        try:
            self._bacnet = BAC0.lite(ip=self.ip, port=self.port)
            self._connected = True
            logger.info("BACnet connected to %s:%s", self.ip, self.port)
            return True
        except Exception as exc:
            logger.error("BACnet connection failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Close the BACnet/IP connection."""
        if self._bacnet is not None:
            try:
                self._bacnet.disconnect()
            except Exception as exc:
                logger.debug("BACnet disconnect error: %s", exc)
            self._bacnet = None
            self._connected = False

    def read_property(self, object_id: str, property_id: str = "presentValue") -> Dict[str, Any]:
        """Read a BACnet object property.

        Args:
            object_id: BACnet object identifier, e.g. ``"analogInput:0"``.
            property_id: BACnet property identifier, e.g. ``"presentValue"``.

        Returns:
            Dict with ``value``, ``object_id``, ``property_id``, and ``simulated``.
        """
        if not _BAC0_AVAILABLE or self._bacnet is None:
            return {"value": None, "object_id": object_id, "property_id": property_id, "simulated": True}
        try:
            value = self._bacnet.read(f"{self.ip} {object_id} {property_id}")
            return {"value": value, "object_id": object_id, "property_id": property_id, "simulated": False}
        except Exception as exc:
            logger.warning("BACnet read_property failed: %s", exc)
            return {"value": None, "object_id": object_id, "property_id": property_id, "error": str(exc), "simulated": False}

    def write_property(self, object_id: str, property_id: str, value: Any, priority: int = 8) -> Dict[str, Any]:
        """Write a BACnet object property.

        Args:
            object_id: BACnet object identifier.
            property_id: BACnet property identifier.
            value: The value to write.
            priority: BACnet write priority (1–16, default 8).

        Returns:
            Dict with ``success`` and ``simulated``.
        """
        if not _BAC0_AVAILABLE or self._bacnet is None:
            return {"success": False, "simulated": True, "reason": "bacnet_unavailable"}
        try:
            self._bacnet.write(f"{self.ip} {object_id} {property_id} {value} - {priority}")
            return {"success": True, "object_id": object_id, "property_id": property_id, "value": value, "simulated": False}
        except Exception as exc:
            logger.warning("BACnet write_property failed: %s", exc)
            return {"success": False, "error": str(exc), "simulated": False}

    def who_is(self, low_limit: int = 0, high_limit: int = 4194303) -> List[Dict[str, Any]]:
        """Send BACnet Who-Is request and return discovered devices."""
        if not _BAC0_AVAILABLE or self._bacnet is None:
            return []
        try:
            devices = self._bacnet.whois(f"{low_limit} {high_limit}")
            return [{"instance": d, "simulated": False} for d in (devices or [])]
        except Exception as exc:
            logger.warning("BACnet who_is failed: %s", exc)
            return []

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch a named action to the appropriate BACnet method."""
        params = params or {}
        dispatch = {
            "read_property": lambda p: self.read_property(p.get("object_id", ""), p.get("property_id", "presentValue")),
            "write_property": lambda p: self.write_property(p.get("object_id", ""), p.get("property_id", "presentValue"), p.get("value")),
            "who_is": lambda p: {"devices": self.who_is(), "simulated": not _BAC0_AVAILABLE},
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown BACnet action: {action_name}", "simulated": not _BAC0_AVAILABLE}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
