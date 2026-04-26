"""
MCP Plugin Architecture — Model Context Protocol connector standard.

Design Label: MCP-001
Module ID:    src.mcp_plugin

Adopts MCP (Model Context Protocol) as a connector standard alongside
the existing SwissKiss integration engine.  This provides:
  • Standardized protocol for tool/service integration
  • Access to the growing MCP ecosystem
  • Lower barrier for community contributors
  • Auto-registration with module_registry.yaml

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides an MCP server registry, tool discovery via MCP protocol,
   and a connector that bridges MCP servers to Murphy's tool registry.

Q: What conditions are possible?
A: Register / unregister / discover / invoke MCP servers.  Servers
   may be local or remote.  Connection failures handled gracefully.

Q: Has hardening been applied?
A: Thread-safe, bounded registries, timeout enforcement, structured
   error propagation, no bare except.
"""

from __future__ import annotations

from src.mcp_plugin.models import (
    MCPCapability,
    MCPInvocationResult,
    MCPServerConfig,
    MCPServerStatus,
    MCPToolSpec,
    MCPTransport,
)
from src.mcp_plugin.mcp_connector import MCPConnector

__all__ = [
    "MCPCapability",
    "MCPConnector",
    "MCPInvocationResult",
    "MCPServerConfig",
    "MCPServerStatus",
    "MCPToolSpec",
    "MCPTransport",
]

from src.mcp_plugin.mcp_router import create_mcp_router
