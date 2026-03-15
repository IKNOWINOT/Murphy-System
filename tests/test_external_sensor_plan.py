import importlib.util
from pathlib import Path


def load_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "murphy_system_1.0_runtime.py"
    spec = importlib.util.spec_from_file_location("murphy_system_runtime", module_path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("Unable to load Murphy runtime module")
    spec.loader.exec_module(module)
    return module


def test_external_sensor_plan_defaults_to_global():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.__new__(runtime.MurphySystem)
    plan = murphy._build_external_sensor_plan("marketing", "marketing automation", None)

    assert plan["region"] == "global"
    sensor_ids = {sensor["id"] for sensor in plan["sensors"]}
    assert "gdelt_media_volume" in sensor_ids


def test_external_sensor_plan_europe_includes_ecb():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.__new__(runtime.MurphySystem)
    onboarding_context = {"region": "EU"}
    plan = murphy._build_external_sensor_plan("finance", "trading automation", onboarding_context)

    assert plan["region"] == "europe"
    sensor_ids = {sensor["id"] for sensor in plan["sensors"]}
    assert "ecb_fx_rates" in sensor_ids


def test_regulatory_sources_follow_region():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.__new__(runtime.MurphySystem)
    onboarding_context = {"region": "United States"}
    plan = murphy._build_external_sensor_plan("compliance", "building code review", onboarding_context)

    assert plan["region"] == "north_america"
    regulatory_ids = {sensor["id"] for sensor in plan["regulatory_sources"]}
    assert "govinfo_federal_law" in regulatory_ids
