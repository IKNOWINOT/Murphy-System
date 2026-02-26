"""Document delivery execution integration tests."""

import asyncio
import importlib.util
from pathlib import Path

import pytest


def load_runtime_module():
    runtime_dir = Path(__file__).resolve().parent.parent
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


def test_execute_task_includes_document_deliverable_when_configured():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = None
    murphy.orchestrator = None

    response = asyncio.run(
        murphy.execute_task(
            "Prepare a customer onboarding summary",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "doc-connector", "status": "configured", "channel": "document"}
                ],
                "document_summary": "Summarize onboarding steps for review.",
                "enforce_policy": False
            },
            session_id="delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    assert deliverables, "Expected a document deliverable when document connector is configured."
    deliverable = deliverables[0]
    assert deliverable.get("type") == "document"
    document = deliverable.get("document", {})
    assert document.get("document_type") == "markdown"
    assert "onboarding" in document.get("content", "").lower()
