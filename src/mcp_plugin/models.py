"""
Pydantic models for MCP Plugin Architecture.

Design Label: MCP-002

Models follow the Model Context Protocol specification for tool
discovery, invocation, and result handling.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPTransport(str, enum.Enum):
    """MCP server connection transport types."""

    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "websocket"


class MCPServerStatus(str, enum.Enum):
    """Lifecycle status of an MCP server connection."""

    REGISTERED = "registered"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class MCPToolSpec(BaseModel):
    """A single tool exposed by an MCP server."""

    name: str
    description: str = ""
    input_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool input.",
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema for tool output.",
    )


class MCPCapability(BaseModel):
    """Capabilities declared by an MCP server."""

    tools: List[MCPToolSpec] = Field(default_factory=list)
    resources: List[str] = Field(default_factory=list)
    prompts: List[str] = Field(default_factory=list)


class MCPServerConfig(BaseModel):
    """Configuration for connecting to an MCP server."""

    server_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)
    transport: MCPTransport = MCPTransport.STDIO

    # Connection details
    command: Optional[str] = Field(
        default=None,
        description="Command to start the MCP server (stdio transport).",
    )
    args: List[str] = Field(
        default_factory=list,
        description="Arguments for the server command.",
    )
    url: Optional[str] = Field(
        default=None,
        description="URL for HTTP/WebSocket transport.",
    )
    env: Dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables for the server process.",
    )

    # Status
    status: MCPServerStatus = MCPServerStatus.REGISTERED
    capabilities: MCPCapability = Field(default_factory=MCPCapability)

    # Metadata
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPInvocationResult(BaseModel):
    """Result from invoking an MCP tool."""

    server_id: str
    tool_name: str
    success: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
