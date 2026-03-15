"""
OPC UA Client for Murphy System

Real OPC UA implementation using the asyncua library.
Guards the import so the module can be used without asyncua installed.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from asyncua import Client as AsyncuaClient  # type: ignore[import]
    _ASYNCUA_AVAILABLE = True
except ImportError:
    _ASYNCUA_AVAILABLE = False
    logger.debug("asyncua not installed — OPC UA client will use stub mode")


class MurphyOPCUAClient:
    """OPC UA client using asyncua.

    Provides synchronous wrappers around asyncua's async API.
    Falls back to stub responses when asyncua is not installed.
    """

    DEFAULT_PORT = 4840

    def __init__(self, url: str):
        """
        Args:
            url: OPC UA endpoint URL, e.g. ``"opc.tcp://192.168.1.100:4840"``.
        """
        self.url = url
        self._client = None
        self._loop = None

    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def browse(self, node_id: str = "i=84") -> Dict[str, Any]:
        """Browse OPC UA node tree."""
        if not _ASYNCUA_AVAILABLE:
            return {"nodes": [], "node_id": node_id, "simulated": True}

        async def _browse():
            async with AsyncuaClient(url=self.url) as client:
                node = client.get_node(node_id)
                children = await node.get_children()
                return {"nodes": [str(c) for c in children], "node_id": node_id, "simulated": False}

        try:
            return self._run_async(_browse())
        except Exception as exc:
            logger.warning("OPC UA browse failed: %s", exc)
            return {"nodes": [], "node_id": node_id, "error": str(exc), "simulated": False}

    def read(self, node_id: str) -> Dict[str, Any]:
        """Read a node value."""
        if not _ASYNCUA_AVAILABLE:
            return {"value": None, "node_id": node_id, "simulated": True}

        async def _read():
            async with AsyncuaClient(url=self.url) as client:
                node = client.get_node(node_id)
                value = await node.read_value()
                return {"value": value, "node_id": node_id, "simulated": False}

        try:
            return self._run_async(_read())
        except Exception as exc:
            logger.warning("OPC UA read failed: %s", exc)
            return {"value": None, "node_id": node_id, "error": str(exc), "simulated": False}

    def write(self, node_id: str, value: Any) -> Dict[str, Any]:
        """Write a node value."""
        if not _ASYNCUA_AVAILABLE:
            return {"success": False, "simulated": True, "reason": "opcua_unavailable"}

        async def _write():
            async with AsyncuaClient(url=self.url) as client:
                node = client.get_node(node_id)
                await node.write_value(value)
                return {"success": True, "node_id": node_id, "value": value, "simulated": False}

        try:
            return self._run_async(_write())
        except Exception as exc:
            logger.warning("OPC UA write failed: %s", exc)
            return {"success": False, "node_id": node_id, "error": str(exc), "simulated": False}

    def execute(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        dispatch = {
            "browse": lambda p: self.browse(p.get("node_id", "i=84")),
            "read": lambda p: self.read(p.get("node_id", "")),
            "write": lambda p: self.write(p.get("node_id", ""), p.get("value")),
        }
        handler = dispatch.get(action_name)
        if handler:
            return handler(params)
        return {"error": f"Unknown OPC UA action: {action_name}", "simulated": not _ASYNCUA_AVAILABLE}
