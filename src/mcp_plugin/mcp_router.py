"""
PATCH-089e — MCP Plugin Router
MCP-004

Mounts /api/mcp/* endpoints for managing MCP server registrations,
tool discovery, and tool invocation. Implements real HTTP transport
for remote MCP servers (stdio transport for local processes added in
PATCH-090).

Endpoints:
  POST /api/mcp/servers          — register an MCP server
  GET  /api/mcp/servers          — list registered servers
  GET  /api/mcp/servers/{id}     — get server status
  DELETE /api/mcp/servers/{id}   — unregister
  POST /api/mcp/servers/{id}/connect    — connect to server
  POST /api/mcp/servers/{id}/discover   — discover tools
  POST /api/mcp/invoke           — invoke a tool
  GET  /api/mcp/tools            — list all discovered tools across servers
  GET  /api/mcp/status           — overall MCP subsystem status
"""
from __future__ import annotations
import logging, asyncio, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.mcp_plugin.models import MCPServerConfig, MCPTransport
from src.mcp_plugin.mcp_connector import MCPConnector

logger = logging.getLogger(__name__)

_connector: Optional[MCPConnector] = None

def get_connector() -> MCPConnector:
    global _connector
    if _connector is None:
        _connector = MCPConnector()
    return _connector


class RegisterServerRequest(BaseModel):
    server_id: str
    name: str
    transport: str = "http"          # "http", "stdio", "websocket"
    url: Optional[str] = None        # for http/websocket
    command: Optional[str] = None    # for stdio (e.g. "npx @modelcontextprotocol/server-filesystem")
    args: List[str] = []
    env: Dict[str, str] = {}
    description: str = ""
    auto_connect: bool = True
    auto_discover: bool = True


class InvokeToolRequest(BaseModel):
    server_id: str
    tool_name: str
    arguments: Dict[str, Any] = {}


mcp_api = APIRouter(prefix="/api/mcp", tags=["mcp"])


@mcp_api.post("/servers")
async def register_server(req: RegisterServerRequest):
    """Register an MCP server and optionally connect + discover tools."""
    conn = get_connector()
    transport_map = {
        "http": MCPTransport.HTTP,
        "stdio": MCPTransport.STDIO,
        "websocket": MCPTransport.WEBSOCKET,
    }
    transport = transport_map.get(req.transport, MCPTransport.HTTP)
    config = MCPServerConfig(
        server_id=req.server_id,
        name=req.name,
        transport=transport,
        url=req.url,
        command=req.command,
        args=req.args,
        description=req.description,
    )
    conn.register_server(config)

    if req.auto_connect:
        ok = conn.connect(req.server_id)
        if not ok:
            raise HTTPException(502, f"Registered but failed to connect to {req.server_id}")

    tools = []
    if req.auto_discover and req.auto_connect:
        tools = [t.dict() for t in conn.discover_tools(req.server_id)]

    logger.info("PATCH-089e: MCP server registered: %s (%s) — %d tools", req.server_id, transport.value, len(tools))
    return {"server_id": req.server_id, "connected": req.auto_connect, "tools_discovered": len(tools), "tools": tools}


@mcp_api.get("/servers")
async def list_servers():
    return {"servers": [s.dict() for s in get_connector().list_servers()]}


@mcp_api.get("/servers/{server_id}")
async def get_server(server_id: str):
    s = get_connector().get_server(server_id)
    if not s:
        raise HTTPException(404, f"Server {server_id} not found")
    return s.dict()


@mcp_api.delete("/servers/{server_id}")
async def unregister_server(server_id: str):
    get_connector().unregister_server(server_id)
    return {"unregistered": server_id}


@mcp_api.post("/servers/{server_id}/connect")
async def connect_server(server_id: str):
    ok = get_connector().connect(server_id)
    return {"server_id": server_id, "connected": ok}


@mcp_api.post("/servers/{server_id}/discover")
async def discover_tools(server_id: str):
    tools = get_connector().discover_tools(server_id)
    return {"server_id": server_id, "tools": [t.dict() for t in tools]}


@mcp_api.get("/tools")
async def list_all_tools():
    """List all tools discovered across all connected MCP servers."""
    all_tools = get_connector().discover_all_tools()
    return {"tools": [t.dict() for t in all_tools], "count": len(all_tools)}


@mcp_api.post("/invoke")
async def invoke_tool(req: InvokeToolRequest):
    """Invoke a tool on a specific MCP server."""
    t0 = time.monotonic()
    result = get_connector().invoke_tool(req.server_id, req.tool_name, req.arguments)
    latency_ms = (time.monotonic() - t0) * 1000
    return {**result, "latency_ms": round(latency_ms, 1)}


@mcp_api.get("/status")
async def mcp_status():
    conn = get_connector()
    summary = conn.get_status_summary()
    return {
        "ok": True,
        "patch": "089e",
        "servers": summary,
        "invocation_log_count": len(conn.get_invocation_log()),
    }


def create_mcp_router() -> APIRouter:
    """Factory used by app.py."""
    return mcp_api
