"""Tests for the forge SSE stream endpoint."""
from __future__ import annotations
import asyncio, json, os, sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MURPHY_ENV", "test")
os.environ.setdefault("MURPHY_RATE_LIMIT_RPM", "6000")


class TestForgeStreamModule:
    def test_agent_names_count(self):
        from src.forge_stream import _AGENT_NAMES
        assert len(_AGENT_NAMES) == 64

    def test_sse_event_format(self):
        from src.forge_stream import _sse_event
        evt = _sse_event("agent_start", {"agent_id": 0, "agent_name": "Coordinator"})
        assert evt.startswith("event: agent_start\n")
        assert "data:" in evt
        assert evt.endswith("\n\n")

    def test_stream_yields_build_complete(self):
        from src.forge_stream import forge_stream_generator
        async def _collect():
            events = []
            async for chunk in forge_stream_generator("test query"):
                events.append(chunk)
            return events
        events = asyncio.run(_collect())
        last = events[-1]
        assert "build_complete" in last
        data = json.loads(last.split("data: ", 1)[1].strip())
        assert data["total_agents"] == 64
        assert data["total_lines"] > 0

    def test_stream_yields_agent_starts(self):
        from src.forge_stream import forge_stream_generator
        async def _collect():
            starts = []
            async for chunk in forge_stream_generator(""):
                if "agent_start" in chunk:
                    starts.append(chunk)
            return starts
        starts = asyncio.run(_collect())
        assert len(starts) == 64

    def test_stream_includes_swarm_field(self):
        from src.forge_stream import forge_stream_generator
        async def _first_start():
            async for chunk in forge_stream_generator(""):
                if "agent_start" in chunk:
                    return chunk
        chunk = asyncio.run(_first_start())
        data = json.loads(chunk.split("data: ", 1)[1].strip())
        assert data["swarm"] in ("exploration", "control")


class TestForgeStreamEndpoint:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from src.runtime.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_forge_stream_endpoint_exists(self, client):
        r = client.get("/api/demo/forge-stream")
        assert r.status_code == 200

    def test_forge_stream_content_type(self, client):
        r = client.get("/api/demo/forge-stream")
        assert "text/event-stream" in r.headers.get("content-type", "")
