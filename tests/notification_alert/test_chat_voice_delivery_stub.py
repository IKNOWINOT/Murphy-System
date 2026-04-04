"""Chat and voice delivery stub execution tests."""

import asyncio
import importlib.util
from pathlib import Path


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent.parent
    candidates = list(runtime_dir.glob("murphy_system_*_runtime.py"))
    if not candidates:
        raise RuntimeError("Unable to locate Murphy runtime module")
    module_path = candidates[0]
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


class StubResponse:
    def to_dict(self):
        return {"status": "stubbed", "message": "Processed by stub integrator"}


class StubIntegrator:
    @staticmethod
    def process_user_request(*_args, **_kwargs):
        return StubResponse()


def _create_stub_runtime():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = None
    murphy.orchestrator = None
    return murphy


def test_execute_task_includes_chat_deliverable_when_configured():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Share a status update in the team channel",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "chat-connector", "status": "configured", "channel": "chat"}
                ],
                "chat_channel": "#team-updates",
                "chat_message": "Status update ready for review.",
                "enforce_policy": False
            },
            session_id="chat-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    chat_delivery = next(
        (item for item in deliverables if item.get("type") == "chat"),
        None
    )
    assert chat_delivery is not None
    assert chat_delivery.get("status") == "queued"
    message = chat_delivery.get("message", {})
    assert message.get("channel") == "#team-updates"
    assert "review" in message.get("content", "").lower()


def test_voice_deliverable_needs_destination():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Call the supervisor with a summary",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "voice-connector", "status": "configured", "channel": "voice"}
                ],
                "voice_profile": "default",
                "enforce_policy": False
            },
            session_id="voice-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    voice_delivery = next(
        (item for item in deliverables if item.get("type") == "voice"),
        None
    )
    assert voice_delivery is not None
    assert voice_delivery.get("status") == "needs_info"
    assert "destination" in voice_delivery.get("gap_action", "").lower()
