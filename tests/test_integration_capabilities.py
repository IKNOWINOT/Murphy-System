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


def test_integration_capabilities_include_core_adapters():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    capabilities = murphy._build_integration_capabilities()

    connector_ids = {item["id"] for item in capabilities["connectors"]}
    expected = {adapter["id"] for adapter in murphy.CORE_ADAPTER_CANDIDATES}
    assert expected.issubset(connector_ids)

    telemetry = next(
        (item for item in capabilities["connectors"] if item["id"] == "telemetry_adapter"),
        None
    )
    assert telemetry is not None
    assert telemetry["module"] == "src.telemetry_adapter"
    assert telemetry["status"] in {"available", "needs_integration"}
