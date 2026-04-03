"""
MultiCursor UI Endpoint Tests — Murphy System

Uses Murphy's own MultiCursorBrowser (MCB) and MCPConnector to test
all production endpoints via the multi-cursor split-screen system.

Verifies:
  - MCB can be instantiated, layouts applied, zones navigated in parallel
  - MCB endpoint probing across all 15+ new crown-jewel API endpoints
  - MCPConnector registers servers, discovers tools, invokes tools
  - MCPConnector → UniversalToolRegistry bridge exports correctly
  - MCB + MCP integrated flow: MCB drives browser, MCP supplies tools

Design Label: TEST-MCB-UI-001
Owner: Production Commissioning Team

Commissioning Gates:
  G1: MultiCursorBrowser + MCPConnector do what they are designed to do
  G2: Spec — MCB controls zones/cursors/navigation, MCP manages servers/tools
  G3: Conditions — no browser (headless stub), single zone, multi-zone,
      parallel probes, MCP connect/disconnect/invoke
  G4: Test profile covers full capability range
  G5: Expected vs actual verified at every assertion
  G8: Error handling — bad zones, missing servers, failed invocations
  G9: Re-commission after all above
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest

# Ensure src/ is on the path for Murphy System imports
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in [_repo_root, os.path.join(_repo_root, "src")]:

# -- MultiCursorBrowser (MCB) --------------------------------------------------
from src.agent_module_loader import (
    MultiCursorActionType,
    MultiCursorBrowser,
    MultiCursorSelector,
    MultiCursorTaskStatus,
)

# -- MCPConnector ---------------------------------------------------------------
from src.mcp_plugin import (
    MCPCapability,
    MCPConnector,
    MCPInvocationResult,
    MCPServerConfig,
    MCPServerStatus,
    MCPToolSpec,
    MCPTransport,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mcb():
    """Fresh MultiCursorBrowser (no real browser — headless stub mode)."""
    browser = MultiCursorBrowser(screen_width=1920, screen_height=1080, headless=True)
    yield browser
    # Release any agent controller entries
    MultiCursorBrowser._agent_registry.clear()


@pytest.fixture
def mcp():
    """Fresh MCPConnector."""
    return MCPConnector()


@pytest.fixture
def sample_server_config():
    """Reusable MCP server config for testing."""
    return MCPServerConfig(
        server_id="test-murphy-api",
        name="Murphy API Server",
        transport=MCPTransport.HTTP,
        url="http://localhost:8000",
        tags=["murphy", "api", "test"],
        capabilities=MCPCapability(
            tools=[
                MCPToolSpec(
                    name="health_check",
                    description="Check Murphy server health",
                    input_schema={"url": "string"},
                    output_schema={"status": "string"},
                ),
                MCPToolSpec(
                    name="diagnostics",
                    description="Get system diagnostics",
                    input_schema={},
                    output_schema={"subsystems": "object"},
                ),
                MCPToolSpec(
                    name="rosetta_state",
                    description="Get Rosetta state snapshot",
                    input_schema={},
                    output_schema={"agents": "array"},
                ),
            ],
        ),
    )


# Production API endpoints to probe
PRODUCTION_ENDPOINTS = [
    ("/health", "Health"),
    ("/api/rosetta/state", "Rosetta State"),
    ("/api/rosetta/personas", "Rosetta Personas"),
    ("/api/ceo/status", "CEO Status"),
    ("/api/ceo/directives", "CEO Directives"),
    ("/api/heartbeat/status", "Heartbeat Status"),
    ("/api/aionmind/status", "AionMind Status"),
    ("/api/tools", "Tool Registry"),
    ("/api/lcm/status", "LCM Engine"),
    ("/api/gates/trust-levels", "Gate Trust Levels"),
    ("/api/features", "Feature Flags"),
    ("/api/agents/teams", "Agent Teams"),
    ("/api/memory/search?query=test", "Persistent Memory"),
    ("/api/skills", "Skill Registry"),
    ("/api/mcp/plugins", "MCP Plugins"),
    ("/api/diagnostics", "Diagnostics"),
    ("/api/rate-governor/status", "Rate Governor"),
]


# ==============================================================================
# Part 1 — MultiCursorBrowser (MCB) Layout & Zone Tests
# ==============================================================================

class TestMCBLayoutAndZones:
    """COMMISSION: G4 — MCB layout engine, zone management, cursor isolation."""

    def test_single_layout_default(self, mcb):
        """MCB starts with a single 'main' zone covering the full screen."""
        zones = mcb.list_zones()
        assert len(zones) == 1
        assert zones[0]["zone_id"] == "main"
        assert zones[0]["width"] == 1920
        assert zones[0]["height"] == 1080

    def test_dual_h_layout(self, mcb):
        """dual_h creates two side-by-side zones named 'left' and 'right'."""
        zones = mcb.apply_layout("dual_h")
        assert len(zones) == 2
        names = {z["zone_id"] for z in zones}
        assert names == {"left", "right"}
        assert zones[0]["width"] == 960  # half of 1920

    def test_dual_v_layout(self, mcb):
        """dual_v creates two stacked zones named 'top' and 'bottom'."""
        zones = mcb.apply_layout("dual_v")
        assert len(zones) == 2
        names = {z["zone_id"] for z in zones}
        assert names == {"top", "bottom"}
        assert zones[0]["height"] == 540  # half of 1080

    def test_quad_layout(self, mcb):
        """quad creates 4 zones in a 2×2 grid."""
        zones = mcb.apply_layout("quad")
        assert len(zones) == 4

    def test_hexa_layout(self, mcb):
        """hexa creates 6 zones in a 3×2 grid."""
        zones = mcb.apply_layout("hexa")
        assert len(zones) == 6

    def test_nona_layout(self, mcb):
        """nona creates 9 zones in a 3×3 grid."""
        zones = mcb.apply_layout("nona")
        assert len(zones) == 9

    def test_auto_layout_picks_best_fit(self, mcb):
        """auto_layout(4) should pick quad (2×2)."""
        zones = mcb.auto_layout(4)
        assert len(zones) == 4

    def test_auto_layout_single(self, mcb):
        """auto_layout(1) should pick single."""
        zones = mcb.auto_layout(1)
        assert len(zones) == 1

    def test_auto_layout_virtual_overflow(self, mcb):
        """auto_layout(20) creates physical zones + virtual tab stacking."""
        zones = mcb.auto_layout(20)
        assert len(zones) <= 16  # hex4 max
        assert len(mcb._virtual_tabs) > 0  # some zones have virtual tabs

    def test_split_zone(self, mcb):
        """split_zone halves an existing zone into two sub-zones."""
        mcb.apply_layout("single")
        # single layout names its zone "z0", not "main"
        zone_id = list(mcb._zones.keys())[0]
        new_zones = mcb.split_zone(zone_id, "h")
        assert len(new_zones) == 2
        assert f"{zone_id}_a" in mcb._zones
        assert f"{zone_id}_b" in mcb._zones

    def test_split_zone_nonexistent(self, mcb):
        """split_zone raises ValueError for unknown zone_id."""
        with pytest.raises(ValueError, match="does not exist"):
            mcb.split_zone("nonexistent_zone")

    def test_cursors_match_zones(self, mcb):
        """Each zone gets its own cursor upon layout."""
        mcb.apply_layout("quad")
        zones = mcb.list_zones()
        cursors = mcb.list_cursors()
        zone_ids = {z["zone_id"] for z in zones}
        cursor_zone_ids = {c["zone_id"] for c in cursors}
        assert zone_ids == cursor_zone_ids

    def test_cursor_isolation(self, mcb):
        """Cursors in different zones have independent state."""
        mcb.apply_layout("dual_h")
        cursors = mcb.list_cursors()
        left_cursor = [c for c in cursors if c["zone_id"] == "left"][0]
        right_cursor = [c for c in cursors if c["zone_id"] == "right"][0]
        # They are at their zone centers — different x values
        assert left_cursor["x"] != right_cursor["x"]

    def test_layout_resets_zones(self, mcb):
        """Applying a new layout clears old zones."""
        mcb.apply_layout("quad")
        assert len(mcb.list_zones()) == 4
        mcb.apply_layout("dual_h")
        assert len(mcb.list_zones()) == 2


# ==============================================================================
# Part 2 — MCB Agent Controller Registry
# ==============================================================================

class TestMCBAgentRegistry:
    """COMMISSION: G4 — MCB agent controller checkout/release pattern."""

    def test_get_controller_creates_instance(self):
        """get_controller creates and caches an MCB per agent_id."""
        try:
            mcb = MultiCursorBrowser.get_controller(agent_id="test_agent_1")
            assert isinstance(mcb, MultiCursorBrowser)
            # Same agent_id returns same instance
            mcb2 = MultiCursorBrowser.get_controller(agent_id="test_agent_1")
            assert mcb is mcb2
        finally:
            MultiCursorBrowser._agent_registry.clear()

    def test_different_agents_get_different_controllers(self):
        """Each agent gets its own isolated MCB instance."""
        try:
            mcb_a = MultiCursorBrowser.get_controller(agent_id="agent_a")
            mcb_b = MultiCursorBrowser.get_controller(agent_id="agent_b")
            assert mcb_a is not mcb_b
        finally:
            MultiCursorBrowser._agent_registry.clear()

    def test_release_controller(self):
        """release_controller removes the cached MCB instance."""
        try:
            MultiCursorBrowser.get_controller(agent_id="disposable")
            assert "disposable" in MultiCursorBrowser.list_controllers()
            MultiCursorBrowser.release_controller("disposable")
            assert "disposable" not in MultiCursorBrowser.list_controllers()
        finally:
            MultiCursorBrowser._agent_registry.clear()

    def test_list_controllers(self):
        """list_controllers returns all registered agent_ids."""
        try:
            MultiCursorBrowser.get_controller(agent_id="a1")
            MultiCursorBrowser.get_controller(agent_id="a2")
            result = MultiCursorBrowser.list_controllers()
            assert "a1" in result
            assert "a2" in result
        finally:
            MultiCursorBrowser._agent_registry.clear()


# ==============================================================================
# Part 3 — MCB Async Actions (Headless / No Browser)
# ==============================================================================

class TestMCBAsyncActions:
    """COMMISSION: G4 — MCB async actions in stub mode (no real browser).

    MCB._execute returns COMPLETED even without a real Playwright browser,
    which lets us validate the full action pipeline without launching Chrome.
    """

    @pytest.mark.asyncio
    async def test_navigate_stub(self, mcb):
        """navigate() completes successfully in stub mode."""
        result = await mcb.navigate("main", "http://localhost:8000/health")
        assert result.status == MultiCursorTaskStatus.COMPLETED
        assert result.action_type == MultiCursorActionType.NAVIGATE

    @pytest.mark.asyncio
    async def test_click_stub(self, mcb):
        """click() completes in stub mode."""
        result = await mcb.click("main", "#submit-btn")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fill_stub(self, mcb):
        """fill() completes in stub mode."""
        result = await mcb.fill("main", "#search-input", "test query")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_type_stub(self, mcb):
        """type() completes in stub mode."""
        result = await mcb.type("main", "#input", "hello world")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_hover_stub(self, mcb):
        """hover() completes in stub mode."""
        result = await mcb.hover("main", ".nav-item")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_screenshot_stub(self, mcb):
        """screenshot() completes in stub mode."""
        result = await mcb.screenshot("main", path="/tmp/test.png")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_evaluate_stub(self, mcb):
        """evaluate() completes in stub mode."""
        result = await mcb.evaluate("main", "document.title")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_text_stub(self, mcb):
        """get_text() completes in stub mode."""
        result = await mcb.get_text("main", "h1")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_title_stub(self, mcb):
        """get_title() completes in stub mode."""
        result = await mcb.get_title("main")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_url_stub(self, mcb):
        """get_url() completes in stub mode."""
        result = await mcb.get_url("main")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_content_stub(self, mcb):
        """get_content() completes in stub mode."""
        result = await mcb.get_content("main")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_assert_text_stub(self, mcb):
        """assert_text() completes in stub mode."""
        result = await mcb.assert_text("main", "h1", "Murphy System")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_assert_visible_stub(self, mcb):
        """assert_visible() completes in stub mode."""
        result = await mcb.assert_visible("main", "#main-nav")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_desktop_click_stub(self, mcb):
        """desktop_click() completes in stub mode."""
        result = await mcb.desktop_click(500, 300)
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_desktop_type_stub(self, mcb):
        """desktop_type() completes in stub mode."""
        result = await mcb.desktop_type("hello")
        assert result.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_tap_stub(self, mcb):
        """tap() (mobile) completes in stub mode."""
        result = await mcb.tap("main", ".mobile-button")
        assert result.status == MultiCursorTaskStatus.COMPLETED


# ==============================================================================
# Part 4 — MCB Multi-Zone Parallel Endpoint Probing
# ==============================================================================

class TestMCBMultiZoneProbing:
    """COMMISSION: G4 — MCB parallel_probe across multiple zones + endpoints.

    This simulates the intended use-case: MCB opens a multi-zone layout
    and navigates each zone to a different production endpoint simultaneously.
    """

    @pytest.mark.asyncio
    async def test_quad_parallel_probe(self, mcb):
        """Probe 4 endpoints in parallel across a quad layout."""
        zones = mcb.apply_layout("quad")
        zone_ids = [z["zone_id"] for z in zones]

        probes = [
            (zone_ids[0], "http://localhost:8000/health", "Health"),
            (zone_ids[1], "http://localhost:8000/api/ceo/status", "CEO"),
            (zone_ids[2], "http://localhost:8000/api/tools", "Tools"),
            (zone_ids[3], "http://localhost:8000/api/diagnostics", "Diag"),
        ]
        results = await mcb.parallel_probe(probes)
        assert len(results) == 4
        for zone_id, url, label, status, result in results:
            assert status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_hexa_probe_all_endpoints(self, mcb):
        """Probe 6 endpoints across a hexa layout."""
        zones = mcb.apply_layout("hexa")
        zone_ids = [z["zone_id"] for z in zones]

        probes = [
            (zone_ids[i % len(zone_ids)], f"http://localhost:8000{ep}", label)
            for i, (ep, label) in enumerate(PRODUCTION_ENDPOINTS[:6])
        ]
        results = await mcb.parallel_probe(probes)
        assert len(results) == 6
        for zone_id, url, label, status, result in results:
            assert status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_dual_split_and_probe(self, mcb):
        """Split single zone then probe both halves."""
        mcb.apply_layout("single")
        zone_id = list(mcb._zones.keys())[0]
        mcb.split_zone(zone_id, "h")
        probes = [
            (f"{zone_id}_a", "http://localhost:8000/health", "Health"),
            (f"{zone_id}_b", "http://localhost:8000/api/rosetta/state", "Rosetta"),
        ]
        results = await mcb.parallel_probe(probes)
        assert len(results) == 2


# ==============================================================================
# Part 5 — MCB Recording & Playback
# ==============================================================================

class TestMCBRecordingPlayback:
    """COMMISSION: G4 — MCB action recording and replay."""

    @pytest.mark.asyncio
    async def test_record_actions(self, mcb):
        """start_recording captures actions, stop_recording returns them."""
        mcb.start_recording()
        await mcb.navigate("main", "http://localhost:8000")
        await mcb.click("main", "#health-btn")
        await mcb.fill("main", "#query", "test")
        actions = mcb.stop_recording()
        assert len(actions) == 3
        assert actions[0].action_type == MultiCursorActionType.NAVIGATE
        assert actions[1].action_type == MultiCursorActionType.CLICK
        assert actions[2].action_type == MultiCursorActionType.FILL

    @pytest.mark.asyncio
    async def test_playback_recorded_actions(self, mcb):
        """playback() replays a list of recorded actions."""
        mcb.start_recording()
        await mcb.navigate("main", "http://localhost:8000/health")
        await mcb.click("main", "#status")
        actions = mcb.stop_recording()

        results = await mcb.playback(actions)
        assert len(results) == 2
        assert all(r.status == MultiCursorTaskStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_replay_returns_true_on_success(self, mcb):
        """replay() alias returns True when all actions succeed."""
        mcb.start_recording()
        await mcb.navigate("main", "http://localhost:8000")
        actions = mcb.stop_recording()
        assert await mcb.replay(actions) is True


# ==============================================================================
# Part 6 — MCB Checkpoints
# ==============================================================================

class TestMCBCheckpoints:
    """COMMISSION: G4 — MCB checkpoint save/restore."""

    @pytest.mark.asyncio
    async def test_checkpoint_and_rollback(self, mcb):
        """checkpoint() saves state, rollback() restores it."""
        mcb.apply_layout("quad")
        original_zones = set(mcb._zones.keys())

        await mcb.checkpoint("pre_split")

        mcb.apply_layout("dual_h")
        assert set(mcb._zones.keys()) != original_zones

        await mcb.rollback("pre_split")
        assert set(mcb._zones.keys()) == original_zones


# ==============================================================================
# Part 7 — MCPConnector Server Lifecycle
# ==============================================================================

class TestMCPConnectorLifecycle:
    """COMMISSION: G4 — MCPConnector server registration, connect, disconnect."""

    def test_register_server(self, mcp, sample_server_config):
        """register_server adds a server to the registry."""
        mcp.register_server(sample_server_config)
        assert mcp.server_count() == 1

    def test_unregister_server(self, mcp, sample_server_config):
        """unregister_server removes a server."""
        mcp.register_server(sample_server_config)
        mcp.unregister_server(sample_server_config.server_id)
        assert mcp.server_count() == 0

    def test_unregister_nonexistent_raises(self, mcp):
        """unregister_server raises KeyError for unknown server."""
        with pytest.raises(KeyError):
            mcp.unregister_server("ghost-server")

    def test_get_server(self, mcp, sample_server_config):
        """get_server returns the config by ID."""
        mcp.register_server(sample_server_config)
        config = mcp.get_server(sample_server_config.server_id)
        assert config.name == "Murphy API Server"

    def test_list_servers(self, mcp, sample_server_config):
        """list_servers returns all registered servers."""
        mcp.register_server(sample_server_config)
        servers = mcp.list_servers()
        assert len(servers) == 1

    def test_connect_http(self, mcp, sample_server_config):
        """connect() succeeds for HTTP server with url."""
        mcp.register_server(sample_server_config)
        ok = mcp.connect(sample_server_config.server_id)
        assert ok is True
        config = mcp.get_server(sample_server_config.server_id)
        assert config.status == MCPServerStatus.CONNECTED

    def test_connect_nonexistent_fails(self, mcp):
        """connect() returns False for unregistered server."""
        ok = mcp.connect("no-such-server")
        assert ok is False

    def test_connect_stdio_without_command_fails(self, mcp):
        """connect() fails for STDIO server without a command."""
        config = MCPServerConfig(
            server_id="bad-stdio",
            name="Bad STDIO",
            transport=MCPTransport.STDIO,
            command=None,
        )
        mcp.register_server(config)
        ok = mcp.connect("bad-stdio")
        assert ok is False
        assert mcp.get_server("bad-stdio").status == MCPServerStatus.ERROR

    def test_disconnect(self, mcp, sample_server_config):
        """disconnect() marks server as disconnected."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        ok = mcp.disconnect(sample_server_config.server_id)
        assert ok is True
        assert mcp.get_server(sample_server_config.server_id).status == MCPServerStatus.DISCONNECTED


# ==============================================================================
# Part 8 — MCPConnector Tool Discovery
# ==============================================================================

class TestMCPToolDiscovery:
    """COMMISSION: G4 — MCP tool discovery from servers."""

    def test_discover_tools(self, mcp, sample_server_config):
        """discover_tools returns the server's declared tools."""
        mcp.register_server(sample_server_config)
        tools = mcp.discover_tools(sample_server_config.server_id)
        assert len(tools) == 3
        names = {t.name for t in tools}
        assert "health_check" in names
        assert "diagnostics" in names
        assert "rosetta_state" in names

    def test_discover_tools_unknown_server(self, mcp):
        """discover_tools returns empty list for unknown server."""
        tools = mcp.discover_tools("phantom")
        assert tools == []

    def test_discover_all_tools(self, mcp, sample_server_config):
        """discover_all_tools returns tools from all connected servers."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        all_tools = mcp.discover_all_tools()
        assert sample_server_config.server_id in all_tools
        assert len(all_tools[sample_server_config.server_id]) == 3

    def test_discover_all_tools_excludes_disconnected(self, mcp, sample_server_config):
        """discover_all_tools skips disconnected servers."""
        mcp.register_server(sample_server_config)
        # Not connected → should not appear
        all_tools = mcp.discover_all_tools()
        assert len(all_tools) == 0


# ==============================================================================
# Part 9 — MCPConnector Tool Invocation
# ==============================================================================

class TestMCPToolInvocation:
    """COMMISSION: G4 — MCP tool invocation with executors."""

    def test_invoke_tool_success(self, mcp, sample_server_config):
        """invoke_tool calls the registered executor and returns result."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)

        def health_executor(input_data):
            return {"status": "ok", "version": "3.0.0"}

        mcp.register_tool_executor(
            "test-murphy-api:health_check",
            health_executor,
        )

        result = mcp.invoke_tool(
            "test-murphy-api", "health_check", {"url": "/health"}
        )
        assert result.success is True
        assert result.output["status"] == "ok"
        assert result.execution_time_ms >= 0

    def test_invoke_tool_not_connected(self, mcp, sample_server_config):
        """invoke_tool fails when server is not connected."""
        mcp.register_server(sample_server_config)
        result = mcp.invoke_tool(
            sample_server_config.server_id, "health_check", {}
        )
        assert result.success is False
        assert "not connected" in result.error.lower()

    def test_invoke_tool_no_executor(self, mcp, sample_server_config):
        """invoke_tool fails when no executor is registered."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        result = mcp.invoke_tool(
            sample_server_config.server_id, "unknown_tool", {}
        )
        assert result.success is False
        assert "no executor" in result.error.lower()

    def test_invoke_tool_executor_exception(self, mcp, sample_server_config):
        """invoke_tool handles executor exceptions gracefully."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)

        def failing_executor(input_data):
            raise RuntimeError("Simulated tool failure")

        mcp.register_tool_executor(
            "test-murphy-api:health_check",
            failing_executor,
        )

        result = mcp.invoke_tool(
            sample_server_config.server_id, "health_check", {}
        )
        assert result.success is False
        assert "Simulated tool failure" in result.error

    def test_invocation_log(self, mcp, sample_server_config):
        """Invocation log records all tool calls."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        mcp.register_tool_executor(
            "test-murphy-api:health_check",
            lambda d: {"ok": True},
        )
        mcp.invoke_tool(sample_server_config.server_id, "health_check", {})
        mcp.invoke_tool(sample_server_config.server_id, "health_check", {})
        log = mcp.get_invocation_log()
        assert len(log) == 2


# ==============================================================================
# Part 10 — MCPConnector → ToolRegistry Bridge
# ==============================================================================

class TestMCPToolRegistryBridge:
    """COMMISSION: G4 — MCP export_as_tool_definitions bridge."""

    def test_export_connected_server_tools(self, mcp, sample_server_config):
        """export_as_tool_definitions generates ToolDefinition-compatible dicts."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        definitions = mcp.export_as_tool_definitions()
        assert len(definitions) == 3
        for d in definitions:
            assert d["tool_id"].startswith("mcp.")
            assert d["category"] == "mcp_plugin"
            assert "mcp" in d["tags"]
            assert "mcp_server_id" in d["metadata"]

    def test_export_excludes_disconnected(self, mcp, sample_server_config):
        """export_as_tool_definitions skips disconnected servers."""
        mcp.register_server(sample_server_config)
        definitions = mcp.export_as_tool_definitions()
        assert len(definitions) == 0

    def test_status_summary(self, mcp, sample_server_config):
        """get_status_summary returns counts + tool totals."""
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        summary = mcp.get_status_summary()
        assert summary["total_servers"] == 1
        assert summary["total_tools_available"] == 3
        assert "connected" in summary["status_distribution"]


# ==============================================================================
# Part 11 — MCB + MCP Integrated Flow
# ==============================================================================

class TestMCBWithMCPIntegrated:
    """COMMISSION: G4 — Integrated MCB + MCP flow.

    Simulates the real usage pattern: MCPConnector discovers tools,
    MCB uses those tools as navigation targets across multiple zones.
    """

    @pytest.mark.asyncio
    async def test_mcp_driven_multi_zone_probe(self, mcb, mcp, sample_server_config):
        """MCP discovers endpoints → MCB probes them across zones."""
        # 1. Register and connect MCP server
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)

        # 2. Discover tools from MCP
        tools = mcp.discover_tools(sample_server_config.server_id)
        assert len(tools) >= 3

        # 3. Map tools to URLs for MCB probing
        tool_urls = {
            "health_check": "http://localhost:8000/health",
            "diagnostics": "http://localhost:8000/api/diagnostics",
            "rosetta_state": "http://localhost:8000/api/rosetta/state",
        }

        # 4. Layout MCB with enough zones
        zones = mcb.auto_layout(len(tools))
        zone_ids = [z["zone_id"] for z in zones]

        # 5. Build probes from MCP tool discovery
        probes = []
        for i, tool in enumerate(tools):
            url = tool_urls.get(tool.name, "http://localhost:8000/health")
            probes.append((zone_ids[i % len(zone_ids)], url, tool.name))

        # 6. Execute parallel probe
        results = await mcb.parallel_probe(probes)
        assert len(results) == len(tools)
        for zone_id, url, label, status, result in results:
            assert status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_mcp_tool_invocation_then_mcb_verify(self, mcb, mcp, sample_server_config):
        """Invoke MCP tool, then use MCB to navigate to verify."""
        # 1. Setup MCP
        mcp.register_server(sample_server_config)
        mcp.connect(sample_server_config.server_id)
        mcp.register_tool_executor(
            "test-murphy-api:health_check",
            lambda d: {"status": "ok", "subsystems_wired": 11},
        )

        # 2. Invoke the MCP health tool
        result = mcp.invoke_tool(
            sample_server_config.server_id,
            "health_check",
            {"url": "/health"},
        )
        assert result.success is True
        assert result.output["status"] == "ok"

        # 3. Use MCB to navigate to the actual health endpoint
        nav = await mcb.navigate("main", "http://localhost:8000/health")
        assert nav.status == MultiCursorTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_full_endpoint_sweep_with_mcp_tools(self, mcb, mcp):
        """Register MCP tools for all endpoints, sweep via MCB nona layout."""
        # Build an MCP config with all production endpoints as tools
        tools = [
            MCPToolSpec(
                name=label.lower().replace(" ", "_"),
                description=f"Probe {label} endpoint",
                input_schema={},
                output_schema={"status": "string"},
            )
            for ep, label in PRODUCTION_ENDPOINTS
        ]
        config = MCPServerConfig(
            server_id="full-sweep-server",
            name="Full Endpoint Sweep",
            transport=MCPTransport.HTTP,
            url="http://localhost:8000",
            capabilities=MCPCapability(tools=tools),
        )
        mcp.register_server(config)
        mcp.connect("full-sweep-server")

        # Discover all tools
        discovered = mcp.discover_tools("full-sweep-server")
        assert len(discovered) == len(PRODUCTION_ENDPOINTS)

        # Layout MCB with nona (9 zones) + virtual tabs for overflow
        zones = mcb.auto_layout(len(discovered))
        zone_ids = [z["zone_id"] for z in zones]

        # Build probes
        probes = []
        for i, (ep, label) in enumerate(PRODUCTION_ENDPOINTS):
            probes.append((
                zone_ids[i % len(zone_ids)],
                f"http://localhost:8000{ep}",
                label,
            ))

        results = await mcb.parallel_probe(probes)
        assert len(results) == len(PRODUCTION_ENDPOINTS)
        completed = sum(
            1 for _, _, _, status, _ in results
            if status == MultiCursorTaskStatus.COMPLETED
        )
        assert completed == len(PRODUCTION_ENDPOINTS)


# ==============================================================================
# Part 12 — MCB Max Limits & Error Handling
# ==============================================================================

class TestMCBLimits:
    """COMMISSION: G8 — MCB hardening and limit enforcement."""

    def test_max_zones_limit(self, mcb):
        """MCB_MAX_ZONES prevents unbounded zone creation."""
        assert MultiCursorBrowser.MCB_MAX_ZONES == 64

    def test_max_depth_limit(self, mcb):
        """MCB_MAX_DEPTH prevents unbounded nesting."""
        assert MultiCursorBrowser.MCB_MAX_DEPTH == 8

    def test_virtual_threshold(self, mcb):
        """MCB_VIRT_THRESH limits physical zones before virtual tabs kick in."""
        assert MultiCursorBrowser.MCB_VIRT_THRESH == 12

    def test_split_zone_at_max(self, mcb):
        """split_zone raises ValueError when at MCB_MAX_ZONES."""
        # Force the zones dict to be full
        mcb._zones = {f"z{i}": {"zone_id": f"z{i}"} for i in range(64)}
        with pytest.raises(ValueError, match="MCB_MAX_ZONES"):
            mcb.split_zone("z0", "h")


# ==============================================================================
# Part 13 — MCP Max Server Limit
# ==============================================================================

class TestMCPLimits:
    """COMMISSION: G8 — MCP server registry limit enforcement."""

    def test_max_server_registration(self, mcp):
        """Registering beyond _MAX_SERVERS raises RuntimeError."""
        # Pre-fill registry to just under limit to avoid slow loop
        mcp._servers = {
            f"server-{i}": MCPServerConfig(
                server_id=f"server-{i}",
                name=f"Server {i}",
                transport=MCPTransport.HTTP,
                url=f"http://localhost:{9000 + i}",
            )
            for i in range(200)
        }
        with pytest.raises(RuntimeError, match="Maximum MCP servers"):
            mcp.register_server(MCPServerConfig(
                server_id="server-overflow",
                name="Overflow",
                transport=MCPTransport.HTTP,
                url="http://localhost:10000",
            ))
