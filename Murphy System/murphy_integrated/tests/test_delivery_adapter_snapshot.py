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
        assert adapter["channel"] in {"document", "email", "chat", "voice"}
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
