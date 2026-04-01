"""
MCP Connector — bridges MCP servers to Murphy's tool registry.

Design Label: MCP-003

Provides:
  • MCP server registration and lifecycle management
  • Tool discovery from MCP servers
  • Bridge to UniversalToolRegistry for unified tool access
  • Invocation proxy with timeout and error handling
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional

from src.mcp_plugin.models import (
    MCPCapability,
    MCPInvocationResult,
    MCPServerConfig,
    MCPServerStatus,
    MCPToolSpec,
    MCPTransport,
)

logger = logging.getLogger(__name__)

_MAX_SERVERS = 200
_MAX_INVOCATION_LOG = 500


class MCPConnector:
    """Manages MCP server connections and bridges to Murphy's tool system.

    Thread-safe, bounded registries, graceful degradation on connection
    failures.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._servers: Dict[str, MCPServerConfig] = {}
        self._invocation_log: Deque[MCPInvocationResult] = deque(
            maxlen=_MAX_INVOCATION_LOG,
        )
        # Optional bridge: tool_id → invocation callable
        self._tool_executors: Dict[str, Callable[..., Dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Server registration
    # ------------------------------------------------------------------

    def register_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server configuration."""
        with self._lock:
            if len(self._servers) >= _MAX_SERVERS and config.server_id not in self._servers:
                raise RuntimeError(
                    f"Maximum MCP servers ({_MAX_SERVERS}) reached. "
                    "Unregister a server first."
                )
            self._servers[config.server_id] = config
            logger.info("MCP server registered: %s (%s) via %s",
                        config.server_id, config.name, config.transport.value)

    def unregister_server(self, server_id: str) -> MCPServerConfig:
        """Remove an MCP server.  Raises KeyError if not found."""
        with self._lock:
            config = self._servers.pop(server_id)
            logger.info("MCP server unregistered: %s", server_id)
            return config

    def get_server(self, server_id: str) -> MCPServerConfig:
        """Get server config by ID.  Raises KeyError if not found."""
        with self._lock:
            return self._servers[server_id]

    def list_servers(
        self,
        *,
        status: Optional[MCPServerStatus] = None,
    ) -> List[MCPServerConfig]:
        """List all registered MCP servers."""
        with self._lock:
            if status:
                return [s for s in self._servers.values() if s.status == status]
            return list(self._servers.values())

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self, server_id: str) -> bool:
        """Establish connection to an MCP server.

        In production, this would start the server process (stdio) or
        open a connection (HTTP/WebSocket).  For now, this validates
        the config and marks the server as connected.
        """
        with self._lock:
            config = self._servers.get(server_id)
            if not config:
                logger.error("Cannot connect: server %s not registered", server_id)
                return False

            try:
                config.status = MCPServerStatus.CONNECTING

                # Validate connection parameters
                if config.transport == MCPTransport.STDIO and not config.command:
                    raise ValueError("STDIO transport requires a command")
                if config.transport in (MCPTransport.HTTP, MCPTransport.WEBSOCKET) and not config.url:
                    raise ValueError(f"{config.transport.value} transport requires a URL")

                config.status = MCPServerStatus.CONNECTED
                logger.info("MCP server connected: %s", server_id)
                return True

            except Exception as exc:
                config.status = MCPServerStatus.ERROR
                logger.exception("Failed to connect MCP server %s: %s", server_id, exc)
                return False

    def disconnect(self, server_id: str) -> bool:
        """Disconnect from an MCP server."""
        with self._lock:
            config = self._servers.get(server_id)
            if not config:
                return False
            config.status = MCPServerStatus.DISCONNECTED
            logger.info("MCP server disconnected: %s", server_id)
            return True

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    def discover_tools(self, server_id: str) -> List[MCPToolSpec]:
        """Discover tools available from an MCP server.

        In production, this would query the server's tools/list endpoint.
        For now, returns the declared capabilities.
        """
        with self._lock:
            config = self._servers.get(server_id)
            if not config:
                return []
            return list(config.capabilities.tools)

    def discover_all_tools(self) -> Dict[str, List[MCPToolSpec]]:
        """Discover tools from all connected servers."""
        with self._lock:
            result: Dict[str, List[MCPToolSpec]] = {}
            for sid, config in self._servers.items():
                if config.status == MCPServerStatus.CONNECTED:
                    result[sid] = list(config.capabilities.tools)
            return result

    def set_capabilities(
        self,
        server_id: str,
        capabilities: MCPCapability,
    ) -> None:
        """Update the declared capabilities for an MCP server."""
        with self._lock:
            config = self._servers.get(server_id)
            if config:
                config.capabilities = capabilities

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def register_tool_executor(
        self,
        tool_key: str,
        executor: Callable[..., Dict[str, Any]],
    ) -> None:
        """Register a callable for a specific tool invocation.

        tool_key format: "{server_id}:{tool_name}"
        """
        self._tool_executors[tool_key] = executor

    def invoke_tool(
        self,
        server_id: str,
        tool_name: str,
        input_data: Dict[str, Any],
        *,
        timeout_seconds: float = 30.0,
    ) -> MCPInvocationResult:
        """Invoke a tool on an MCP server."""
        t0 = time.monotonic()

        with self._lock:
            config = self._servers.get(server_id)
            if not config:
                return MCPInvocationResult(
                    server_id=server_id,
                    tool_name=tool_name,
                    success=False,
                    error=f"Server {server_id} not registered",
                )
            if config.status != MCPServerStatus.CONNECTED:
                return MCPInvocationResult(
                    server_id=server_id,
                    tool_name=tool_name,
                    success=False,
                    error=f"Server {server_id} not connected (status: {config.status.value})",
                )

        tool_key = f"{server_id}:{tool_name}"
        executor = self._tool_executors.get(tool_key)

        if executor is None:
            return MCPInvocationResult(
                server_id=server_id,
                tool_name=tool_name,
                success=False,
                error=f"No executor registered for {tool_key}",
            )

        try:
            result = executor(input_data)
            elapsed_ms = (time.monotonic() - t0) * 1000

            invocation = MCPInvocationResult(
                server_id=server_id,
                tool_name=tool_name,
                success=True,
                output=result if isinstance(result, dict) else {"value": result},
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.exception("MCP tool invocation failed: %s/%s: %s",
                             server_id, tool_name, exc)
            invocation = MCPInvocationResult(
                server_id=server_id,
                tool_name=tool_name,
                success=False,
                error=str(exc),
                execution_time_ms=elapsed_ms,
            )

        self._invocation_log.append(invocation)
        return invocation

    # ------------------------------------------------------------------
    # Bridge to UniversalToolRegistry
    # ------------------------------------------------------------------

    def export_as_tool_definitions(self) -> List[Dict[str, Any]]:
        """Export all MCP tools as dicts compatible with ToolDefinition.

        This allows MCP tools to auto-register in the UniversalToolRegistry.
        """
        with self._lock:
            definitions: List[Dict[str, Any]] = []
            for sid, config in self._servers.items():
                if config.status != MCPServerStatus.CONNECTED:
                    continue
                for tool in config.capabilities.tools:
                    definitions.append({
                        "tool_id": f"mcp.{sid}.{tool.name}",
                        "name": f"[MCP] {tool.name}",
                        "description": tool.description,
                        "provider": f"mcp:{config.name}",
                        "tags": ["mcp", *config.tags],
                        "category": "mcp_plugin",
                        "input_schema": {"fields": tool.input_schema},
                        "output_schema": {"fields": tool.output_schema},
                        "permission_level": "medium",
                        "metadata": {
                            "mcp_server_id": sid,
                            "mcp_transport": config.transport.value,
                        },
                    })
            return definitions

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def server_count(self) -> int:
        """Number of registered servers."""
        with self._lock:
            return len(self._servers)

    def get_invocation_log(self) -> List[MCPInvocationResult]:
        """Return recent invocation records."""
        return list(self._invocation_log)

    def get_status_summary(self) -> Dict[str, Any]:
        """Summary of all MCP servers and their status."""
        with self._lock:
            status_counts: Dict[str, int] = {}
            total_tools = 0
            for config in self._servers.values():
                s = config.status.value
                status_counts[s] = status_counts.get(s, 0) + 1
                total_tools += len(config.capabilities.tools)
            return {
                "total_servers": len(self._servers),
                "status_distribution": status_counts,
                "total_tools_available": total_tools,
            }
