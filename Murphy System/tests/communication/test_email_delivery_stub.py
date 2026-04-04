"""Email delivery stub execution tests."""

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


def test_execute_task_includes_email_deliverable_when_configured():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Send a project update to the client",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "email-connector", "status": "configured", "channel": "email"}
                ],
                "email_recipients": ["ops@example.com"],
                "email_subject": "Project update ready",
                "email_body": "The project update is ready for review.",
                "enforce_policy": False
            },
            session_id="email-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    assert deliverables, "Expected an email deliverable when email connector is configured."
    email_delivery = next(
        (item for item in deliverables if item.get("type") == "email"),
        None
    )
    assert email_delivery is not None
    assert email_delivery.get("status") == "queued"
    message = email_delivery.get("message", {})
    assert message.get("subject") == "Project update ready"
    assert "ops@example.com" in message.get("to", [])


def test_email_deliverable_needs_recipients():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Send a compliance summary",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "email-connector", "status": "configured", "channel": "email"}
                ],
                "email_subject": "Compliance summary",
                "enforce_policy": False
            },
            session_id="email-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    email_delivery = next(
        (item for item in deliverables if item.get("type") == "email"),
        None
    )
    assert email_delivery is not None
    assert email_delivery.get("status") == "needs_info"
    assert "recipients" in email_delivery.get("gap_action", "").lower()
