"""
Tests for MCP Plugin Architecture (MCP-001..MCP-003).

Covers: server registration, connection lifecycle, tool discovery,
invocation, bridge export, and error handling.
"""

from __future__ import annotations

import pytest

from src.mcp_plugin.models import (
    MCPCapability,
    MCPInvocationResult,
    MCPServerConfig,
    MCPServerStatus,
    MCPToolSpec,
    MCPTransport,
)
from src.mcp_plugin.mcp_connector import MCPConnector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def connector():
    return MCPConnector()


@pytest.fixture
def stdio_server():
    return MCPServerConfig(
        server_id="srv_fs",
        name="Filesystem Server",
        transport=MCPTransport.STDIO,
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        tags=["filesystem"],
        capabilities=MCPCapability(
            tools=[
                MCPToolSpec(
                    name="read_file",
                    description="Read file contents.",
                    input_schema={"path": {"type": "string"}},
                ),
                MCPToolSpec(
                    name="write_file",
                    description="Write file contents.",
                    input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
                ),
            ],
        ),
    )


@pytest.fixture
def http_server():
    return MCPServerConfig(
        server_id="srv_http",
        name="HTTP API Server",
        transport=MCPTransport.HTTP,
        url="http://localhost:8080/mcp",
        tags=["api"],
        capabilities=MCPCapability(
            tools=[
                MCPToolSpec(name="fetch_data", description="Fetch data from API."),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Server registration tests
# ---------------------------------------------------------------------------

class TestServerRegistration:
    def test_register_and_get(self, connector, stdio_server):
        connector.register_server(stdio_server)
        fetched = connector.get_server("srv_fs")
        assert fetched.name == "Filesystem Server"

    def test_unregister(self, connector, stdio_server):
        connector.register_server(stdio_server)
        removed = connector.unregister_server("srv_fs")
        assert removed.server_id == "srv_fs"
        assert connector.server_count() == 0

    def test_unregister_not_found(self, connector):
        with pytest.raises(KeyError):
            connector.unregister_server("nonexistent")

    def test_list_servers(self, connector, stdio_server, http_server):
        connector.register_server(stdio_server)
        connector.register_server(http_server)
        servers = connector.list_servers()
        assert len(servers) == 2

    def test_list_by_status(self, connector, stdio_server):
        connector.register_server(stdio_server)
        servers = connector.list_servers(status=MCPServerStatus.REGISTERED)
        assert len(servers) == 1
        servers = connector.list_servers(status=MCPServerStatus.CONNECTED)
        assert len(servers) == 0

    def test_server_count(self, connector, stdio_server, http_server):
        connector.register_server(stdio_server)
        connector.register_server(http_server)
        assert connector.server_count() == 2


# ---------------------------------------------------------------------------
# Connection lifecycle tests
# ---------------------------------------------------------------------------

class TestConnectionLifecycle:
    def test_connect_stdio(self, connector, stdio_server):
        connector.register_server(stdio_server)
        assert connector.connect("srv_fs") is True
        server = connector.get_server("srv_fs")
        assert server.status == MCPServerStatus.CONNECTED

    def test_connect_http(self, connector, http_server):
        connector.register_server(http_server)
        assert connector.connect("srv_http") is True

    def test_connect_not_registered(self, connector):
        assert connector.connect("nonexistent") is False

    def test_connect_missing_command(self, connector):
        config = MCPServerConfig(
            server_id="bad",
            name="Bad STDIO",
            transport=MCPTransport.STDIO,
            # No command!
        )
        connector.register_server(config)
        assert connector.connect("bad") is False
        assert connector.get_server("bad").status == MCPServerStatus.ERROR

    def test_connect_missing_url(self, connector):
        config = MCPServerConfig(
            server_id="bad_http",
            name="Bad HTTP",
            transport=MCPTransport.HTTP,
            # No url!
        )
        connector.register_server(config)
        assert connector.connect("bad_http") is False

    def test_disconnect(self, connector, stdio_server):
        connector.register_server(stdio_server)
        connector.connect("srv_fs")
        assert connector.disconnect("srv_fs") is True
        assert connector.get_server("srv_fs").status == MCPServerStatus.DISCONNECTED


# ---------------------------------------------------------------------------
# Tool discovery tests
# ---------------------------------------------------------------------------

class TestToolDiscovery:
    def test_discover_tools(self, connector, stdio_server):
        connector.register_server(stdio_server)
        tools = connector.discover_tools("srv_fs")
        assert len(tools) == 2
        assert tools[0].name == "read_file"

    def test_discover_all_tools(self, connector, stdio_server, http_server):
        connector.register_server(stdio_server)
        connector.register_server(http_server)
        connector.connect("srv_fs")
        connector.connect("srv_http")
        all_tools = connector.discover_all_tools()
        assert len(all_tools) == 2
        assert "srv_fs" in all_tools

    def test_set_capabilities(self, connector, stdio_server):
        connector.register_server(stdio_server)
        new_caps = MCPCapability(
            tools=[MCPToolSpec(name="new_tool", description="New tool.")],
        )
        connector.set_capabilities("srv_fs", new_caps)
        tools = connector.discover_tools("srv_fs")
        assert len(tools) == 1
        assert tools[0].name == "new_tool"


# ---------------------------------------------------------------------------
# Invocation tests
# ---------------------------------------------------------------------------

class TestInvocation:
    def test_invoke_success(self, connector, stdio_server):
        connector.register_server(stdio_server)
        connector.connect("srv_fs")
        connector.register_tool_executor(
            "srv_fs:read_file",
            lambda inp: {"content": "file data"},
        )
        result = connector.invoke_tool("srv_fs", "read_file", {"path": "/test"})
        assert result.success is True
        assert result.output["content"] == "file data"

    def test_invoke_not_registered(self, connector):
        result = connector.invoke_tool("nonexistent", "tool", {})
        assert result.success is False

    def test_invoke_not_connected(self, connector, stdio_server):
        connector.register_server(stdio_server)
        result = connector.invoke_tool("srv_fs", "read_file", {})
        assert result.success is False
        assert "not connected" in result.error

    def test_invoke_no_executor(self, connector, stdio_server):
        connector.register_server(stdio_server)
        connector.connect("srv_fs")
        result = connector.invoke_tool("srv_fs", "read_file", {})
        assert result.success is False

    def test_invoke_executor_error(self, connector, stdio_server):
        connector.register_server(stdio_server)
        connector.connect("srv_fs")
        connector.register_tool_executor(
            "srv_fs:read_file",
            lambda inp: (_ for _ in ()).throw(RuntimeError("disk error")),
        )
        result = connector.invoke_tool("srv_fs", "read_file", {"path": "/test"})
        assert result.success is False


# ---------------------------------------------------------------------------
# Bridge export tests
# ---------------------------------------------------------------------------

class TestBridgeExport:
    def test_export_as_tool_definitions(self, connector, stdio_server):
        connector.register_server(stdio_server)
        connector.connect("srv_fs")
        definitions = connector.export_as_tool_definitions()
        assert len(definitions) == 2
        assert definitions[0]["tool_id"].startswith("mcp.")
        assert "mcp" in definitions[0]["tags"]

    def test_export_only_connected(self, connector, stdio_server, http_server):
        connector.register_server(stdio_server)
        connector.register_server(http_server)
        connector.connect("srv_fs")
        # http_server not connected
        definitions = connector.export_as_tool_definitions()
        assert len(definitions) == 2  # only from srv_fs


# ---------------------------------------------------------------------------
# Introspection tests
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_invocation_log(self, connector):
        log = connector.get_invocation_log()
        assert isinstance(log, list)

    def test_status_summary(self, connector, stdio_server):
        connector.register_server(stdio_server)
        summary = connector.get_status_summary()
        assert summary["total_servers"] == 1
        assert summary["total_tools_available"] == 2
