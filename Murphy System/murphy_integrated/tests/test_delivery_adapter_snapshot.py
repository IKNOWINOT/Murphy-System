import importlib.util
import logging
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


def build_onboarding_answers(murphy):
    stages = [step["stage"] for step in murphy.flow_steps if step.get("stage")]
    return {stage: f"{stage}_ok" for stage in stages}


def test_delivery_adapter_snapshot_in_preview():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    doc = runtime.LivingDocument("doc-1", "Test", "content", "request")
    doc.confidence = 0.92
    murphy._update_document_tree(doc)
    onboarding_context = {"answers": build_onboarding_answers(murphy)}

    preview = murphy._build_activation_preview(doc, "Deliver automation outputs", onboarding_context)

    delivery_readiness = preview["delivery_readiness"]
    adapters = delivery_readiness["delivery_adapters"]
    summary = adapters["summary"]
    adapter_entries = {adapter["id"]: adapter for adapter in adapters["adapters"]}
    assert summary["total"] == len(murphy.DELIVERY_ADAPTER_CANDIDATES)
    assert summary["configured"] == 0
    assert summary["unconfigured"] == summary["total"] - summary["configured"]
    assert delivery_readiness["status"] in {"needs_wiring", "needs_coverage"}
    assert set(adapter_entries.keys()) == {
        candidate["id"] for candidate in murphy.DELIVERY_ADAPTER_CANDIDATES
    }
    for adapter_id, adapter in adapter_entries.items():
        assert adapter["id"] == adapter_id
        assert adapter["channel"] in {"document", "email", "chat", "voice", "translation"}
        assert adapter["status"] in {"available", "needs_integration", "configured"}
    output_stage = next(
        (stage for stage in preview["dynamic_implementation"]["stages"] if stage["id"] == "output_delivery"),
        None
    )
    assert output_stage is not None
    assert output_stage["status"] in {"needs_wiring", "needs_coverage"}


def test_delivery_adapter_snapshot_marks_configured_entries():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    murphy.integration_connectors["document_delivery"] = {"status": "configured"}
    doc = runtime.LivingDocument("doc-2", "Configured", "content", "request")
    doc.confidence = 0.92
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Deliver automation outputs",
        {"answers": build_onboarding_answers(murphy)}
    )

    delivery_readiness = preview["delivery_readiness"]
    summary = delivery_readiness["delivery_adapters"]["summary"]
    assert summary["configured"] == 1


def test_delivery_adapter_snapshot_applies_parameter_connectors():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    expected_ids = {candidate["id"] for candidate in murphy.DELIVERY_ADAPTER_CANDIDATES}
    params = {
        "onboarding_context": {"answers": build_onboarding_answers(murphy)},
        "delivery_connectors": [
            {"id": "document_delivery", "status": "configured", "channel": "document"}
        ]
    }

    _, preview = murphy._prepare_activation_preview(
        "Deliver automation outputs",
        "request",
        None,
        params
    )

    delivery_readiness = preview["delivery_readiness"]
    summary = delivery_readiness["delivery_adapters"]["summary"]
    assert summary["configured"] == 1
    assert "document_delivery" in expected_ids
    connector = murphy.integration_connectors["document_delivery"]
    assert connector["channel"] == "document"
    assert connector["status"] == "configured"


def test_delivery_adapter_snapshot_handles_invalid_connector_fields(caplog):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    params = {
        "onboarding_context": {"answers": build_onboarding_answers(murphy)},
        "delivery_connectors": [
            {"id": "document_delivery", "status": "bad", "channel": "fax"}
        ]
    }

    caplog.set_level(logging.WARNING)
    _, preview = murphy._prepare_activation_preview(
        "Deliver automation outputs",
        "request",
        None,
        params
    )

    delivery_readiness = preview["delivery_readiness"]
    summary = delivery_readiness["delivery_adapters"]["summary"]
    assert summary["configured"] == 0
    connector = murphy.integration_connectors["document_delivery"]
    assert connector["status"] == "unconfigured"
    assert connector["channel"] == "unknown"
    assert "Unknown delivery connector status" in caplog.text
    assert "Unknown delivery connector channel" in caplog.text


def test_delivery_adapter_snapshot_ignores_invalid_connector_list(caplog):
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    params = {
        "onboarding_context": {"answers": build_onboarding_answers(murphy)},
        "delivery_connectors": "not-a-list"
    }

    caplog.set_level(logging.WARNING)
    _, preview = murphy._prepare_activation_preview(
        "Deliver automation outputs",
        "request",
        None,
        params
    )

    delivery_readiness = preview["delivery_readiness"]
    summary = delivery_readiness["delivery_adapters"]["summary"]
    assert summary["configured"] == 0
    assert "delivery_connectors must be a list" in caplog.text
