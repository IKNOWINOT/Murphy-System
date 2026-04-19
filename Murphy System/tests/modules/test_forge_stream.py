"""Tests for the forge SSE stream endpoint."""
from __future__ import annotations
import asyncio, json, os, sys
from pathlib import Path
from unittest import mock
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
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

    def test_stream_emits_error_on_import_failure(self):
        """When the real pipeline is unavailable, an error event must be emitted."""
        from src.forge_stream import forge_stream_generator
        async def _collect():
            events = []
            with mock.patch(
                "src.forge_stream._run_pipeline_sync",
                side_effect=ImportError("mock unavailable"),
            ):
                async for chunk in forge_stream_generator("test query"):
                    events.append(chunk)
            return events
        events = asyncio.run(_collect())
        assert len(events) == 1
        assert "error" in events[0]
        data = json.loads(events[0].split("data: ", 1)[1].strip())
        assert data["code"] == "FORGE-STREAM-ERR-001"

    def test_stream_yields_build_complete_on_success(self):
        """When the pipeline succeeds, a build_complete event is emitted."""
        from src.forge_stream import forge_stream_generator
        fake_events = [
            {"phase": 1, "status": "MFGC gate passed", "detail": "mfgc"},
            {"phase": 3, "status": "MSS done", "detail": "mss"},
            {
                "phase": "done",
                "deliverable": {"content": "test", "title": "Test"},
                "metrics": {"swarm_agent_count": 3, "line_count": 10},
                "pipeline_diagnostics": {
                    "path_taken": ["swarm_ok:3_agents"],
                    "error_count": 0,
                    "fallback_count": 0,
                },
            },
        ]

        async def _collect():
            events = []
            with mock.patch(
                "src.forge_stream._run_pipeline_sync",
                return_value=fake_events,
            ):
                async for chunk in forge_stream_generator("test query"):
                    events.append(chunk)
            return events

        events = asyncio.run(_collect())
        last = events[-1]
        assert "build_complete" in last
        data = json.loads(last.split("data: ", 1)[1].strip())
        assert data["total_agents"] == 3
        assert data["total_lines"] == 10
        assert data["llm_provider"] == "swarm"

    def test_stream_surfaces_pipeline_warnings(self):
        """When the pipeline has fallbacks, warnings must be surfaced."""
        from src.forge_stream import forge_stream_generator
        fake_events = [
            {"phase": 1, "status": "MFGC gate", "detail": "mfgc"},
            {
                "phase": "done",
                "deliverable": {"content": "test"},
                "metrics": {"swarm_agent_count": 0, "line_count": 5},
                "pipeline_diagnostics": {
                    "path_taken": ["single_agent_fallback", "fallback:mss+domain"],
                    "error_count": 2,
                    "fallback_count": 3,
                    "fallbacks": ["swarm: all agents failed", "llm: unavailable"],
                },
            },
        ]

        async def _collect():
            events = []
            with mock.patch(
                "src.forge_stream._run_pipeline_sync",
                return_value=fake_events,
            ):
                async for chunk in forge_stream_generator("test"):
                    events.append(chunk)
            return events

        events = asyncio.run(_collect())
        last = events[-1]
        data = json.loads(last.split("data: ", 1)[1].strip())
        assert data["llm_provider"] == "template-fallback"
        assert data["pipeline_warnings"]["error_count"] == 2
        assert data["pipeline_warnings"]["fallback_count"] == 3


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

    def test_deliverable_export_endpoint_exists(self, client):
        """The /api/demo/deliverable/export endpoint must exist (not 404)."""
        r = client.post(
            "/api/demo/deliverable/export",
            json={"deliverable": {"content": "test", "title": "Test"}, "format": "txt"},
        )
        # Should return 200, not 404
        assert r.status_code != 404

    def test_deliverable_formats_endpoint_exists(self, client):
        """The /api/demo/deliverable/formats endpoint must exist (not 404)."""
        r = client.get("/api/demo/deliverable/formats")
        assert r.status_code == 200
        data = r.json()
        assert "formats" in data
        assert "txt" in data["formats"]
