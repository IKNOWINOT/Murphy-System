"""Translation delivery stub execution tests."""

import asyncio
import importlib.util
from pathlib import Path


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


def _create_stub_runtime():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.system_integrator = StubIntegrator()
    murphy.mfgc_adapter = None
    murphy.orchestrator = None
    return murphy


def test_execute_task_includes_translation_deliverable_when_configured():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Translate the onboarding guide",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "translation-connector", "status": "configured", "channel": "translation"}
                ],
                "translation_text": "Welcome to the system.",
                "translation_target_locale": "es-ES",
                "translation_source_locale": "en-US",
                "enforce_policy": False
            },
            session_id="translation-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    translation_delivery = next(
        (item for item in deliverables if item.get("type") == "translation"),
        None
    )
    assert translation_delivery is not None
    assert translation_delivery.get("status") == "queued"
    payload = translation_delivery.get("translation", {})
    assert payload.get("target_locale") == "es-ES"
    assert payload.get("source_locale") == "en-US"
    assert "Welcome" in payload.get("text", "")


def test_translation_deliverable_needs_target_locale():
    murphy = _create_stub_runtime()

    response = asyncio.run(
        murphy.execute_task(
            "Translate the runbook",
            "automation",
            {
                "delivery_connectors": [
                    {"id": "translation-connector", "status": "configured", "channel": "translation"}
                ],
                "translation_text": "Runbook content",
                "enforce_policy": False
            },
            session_id="translation-delivery-session"
        )
    )

    deliverables = response.get("deliverables", [])
    translation_delivery = next(
        (item for item in deliverables if item.get("type") == "translation"),
        None
    )
    assert translation_delivery is not None
    assert translation_delivery.get("status") == "needs_info"
    assert "locale" in translation_delivery.get("gap_action", "").lower()
    assert "target_locale" not in translation_delivery.get("translation", {})
