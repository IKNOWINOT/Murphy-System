"""
KNX Client for Murphy System

Real KNXnet/IP implementation using the xknx library.
Guards the import so the module can be used without xknx installed.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import xknx  # type: ignore[import]
    from xknx import XKNX
    _XKNX_AVAILABLE = True
except ImportError:
    _XKNX_AVAILABLE = False
    logger.debug("xknx not installed — KNX client will use stub mode")


class MurphyKNXClient:
    """KNXnet/IP client using xknx.

    Falls back to stub responses when xknx is not installed.
    """

    DEFAULT_PORT = 3671

    def __init__(self, gateway_ip: str, port: int = DEFAULT_PORT):
        self.gateway_ip = gateway_ip
        self.port = port

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def group_write(self, group_address: str, payload: Any) -> Dict[str, Any]:
        """Write a value to a KNX group address."""
        if not _XKNX_AVAILABLE:
            return {"success": False, "simulated": True, "reason": "xknx_unavailable"}

        async def _write():
            async with XKNX() as knx:
                light = xknx.devices.Light(knx, name="Target", group_address_switch=group_address)
                if payload:
                    await light.set_on()
                else:
                    await light.set_off()
                return {"success": True, "group_address": group_address, "simulated": False}

        try:
            return self._run_async(_write())
        except Exception as exc:
            logger.warning("KNX group_write failed: %s", exc)
            return {"success": False, "group_address": group_address, "error": str(exc), "simulated": False}

    def group_read(self, group_address: str) -> Dict[str, Any]:
        """Read a KNX group address value."""
        if not _XKNX_AVAILABLE:
            return {"value": None, "group_address": group_address, "simulated": True}

        async def _read():
            async with XKNX() as knx:
                sensor = xknx.devices.Sensor(knx, name="Sensor", group_address_state=group_address)
                await sensor.sync()
                return {"value": sensor.resolve_state(), "group_address": group_address, "simulated": False}

        try:
            return self._run_async(_read())
        except Exception as exc:
            logger.warning("KNX group_read failed: %s", exc)
            return {"value": None, "group_address": group_address, "error": str(exc), "simulated": False}

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        dispatch = {
            "group_write": lambda p: self.group_write(p.get("group_address", ""), p.get("payload")),
            "group_read": lambda p: self.group_read(p.get("group_address", "")),
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown KNX action: {action_name}", "simulated": not _XKNX_AVAILABLE}
