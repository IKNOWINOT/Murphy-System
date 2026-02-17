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


def test_completion_snapshot_surface_parity():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()

    status = murphy.get_system_status()
    info = murphy.get_system_info()
    doc = runtime.LivingDocument("test_completion_doc", "Completion", "content", "request")
    doc.confidence = 0.9
    murphy._update_document_tree(doc)
    preview = murphy._build_activation_preview(
        doc,
        "Validate completion snapshot parity",
        {"answers": {step["stage"]: "ok" for step in murphy.flow_steps}}
    )

    expected = status["completion_snapshot"]
    assert info["completion_snapshot"] == expected
    assert preview["completion_snapshot"] == expected
    assert info["runtime_execution_profile"] == status["runtime_execution_profile"]
    assert preview["runtime_execution_profile"]["execution_mode"] == status["runtime_execution_profile"]["execution_mode"]
    assert preview["runtime_execution_profile"]["execution_enforcement_level"] == status["runtime_execution_profile"]["execution_enforcement_level"]
    assert preview["runtime_execution_profile"]["control_plane_separation_state"] == status["runtime_execution_profile"]["control_plane_separation_state"]
    assert preview["runtime_execution_profile"]["execution_profile_source"] == "onboarding"
    assert status["runtime_execution_profile"]["execution_profile_source"] == "default"
    assert status["runtime_execution_profile"]["control_plane_separation_state"] == "adaptive"
    assert expected["summary"]["total_areas"] == len(expected["areas"])
    assert expected["summary"]["remediation_threshold_percent"] == 50
    assert expected["summary"]["low_completion_areas"] >= 1
    assert len(expected["summary"]["low_completion_area_ids"]) == expected["summary"]["low_completion_areas"]
    assert status["runtime_execution_profile"]["execution_enforcement_level"] == "policy_guarded"
    dynamic_chain = next(
        item for item in expected["areas"] if item["area"] == "dynamic_chain_test_coverage"
    )
    assert dynamic_chain["percent"] == 89


def test_runtime_execution_profile_mode_derivation():
    runtime = load_runtime_module()
    murphy = runtime.MurphySystem.create_test_instance()
    strict = murphy._build_runtime_execution_profile(
        "Regulated compliance workflow",
        {"safety_level": "strict", "risk_tolerance": "low"}
    )
    dynamic = murphy._build_runtime_execution_profile(
        "High autonomy production mode",
        {"autonomy_level": "dynamic", "risk_tolerance": "high"}
    )
    assert strict["execution_mode"] == "strict"
    assert strict["execution_profile_source"] == "onboarding"
    assert strict["execution_enforcement_level"] == "full_gate_enforcement"
    assert strict["control_plane_separation_state"] == "enforced"
    assert strict["escalation_policy"] == "mandatory"
    assert dynamic["execution_mode"] == "dynamic"
    assert dynamic["execution_profile_source"] == "onboarding"
    assert dynamic["execution_enforcement_level"] == "autonomy_accelerated"
    assert dynamic["control_plane_separation_state"] == "relaxed"
    assert dynamic["audit_requirements"] == "minimal"
