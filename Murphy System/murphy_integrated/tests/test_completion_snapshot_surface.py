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
    assert preview["runtime_execution_profile"]["self_improvement_rd_candidate"] == status["runtime_execution_profile"]["self_improvement_rd_candidate"]
    assert preview["runtime_execution_profile"]["approval_checkpoint_policy"] == status["runtime_execution_profile"]["approval_checkpoint_policy"]
    assert preview["runtime_execution_profile"]["budget_enforcement_mode"] == status["runtime_execution_profile"]["budget_enforcement_mode"]
    assert preview["runtime_execution_profile"]["audit_logging_policy"] == status["runtime_execution_profile"]["audit_logging_policy"]
    assert preview["runtime_execution_profile"]["escalation_routing_policy"] == status["runtime_execution_profile"]["escalation_routing_policy"]
    assert preview["runtime_execution_profile"]["tool_mediation_policy"] == status["runtime_execution_profile"]["tool_mediation_policy"]
    assert preview["runtime_execution_profile"]["deterministic_routing_policy"] == status["runtime_execution_profile"]["deterministic_routing_policy"]
    assert preview["runtime_execution_profile"]["compute_routing_policy"] == status["runtime_execution_profile"]["compute_routing_policy"]
    assert preview["runtime_execution_profile"]["policy_compiler_mode"] == status["runtime_execution_profile"]["policy_compiler_mode"]
    assert preview["runtime_execution_profile"]["permission_validation_policy"] == status["runtime_execution_profile"]["permission_validation_policy"]
    assert preview["runtime_execution_profile"]["delegation_scope_policy"] == status["runtime_execution_profile"]["delegation_scope_policy"]
    assert preview["runtime_execution_profile"]["execution_broker_policy"] == status["runtime_execution_profile"]["execution_broker_policy"]
    assert preview["runtime_execution_profile"]["execution_profile_source"] == "onboarding"
    assert status["runtime_execution_profile"]["execution_profile_source"] == "default"
    assert status["runtime_execution_profile"]["control_plane_separation_state"] == "adaptive"
    assert status["runtime_execution_profile"]["self_improvement_rd_candidate"] == "hybrid_governance_feedback_loop"
    assert status["runtime_execution_profile"]["approval_checkpoint_policy"] == "conditional"
    assert status["runtime_execution_profile"]["budget_enforcement_mode"] == "soft_cap"
    assert status["runtime_execution_profile"]["audit_logging_policy"] == "standard_governance_stream"
    assert status["runtime_execution_profile"]["escalation_routing_policy"] == "policy_scored_chain"
    assert status["runtime_execution_profile"]["tool_mediation_policy"] == "policy_guarded_mediation"
    assert status["runtime_execution_profile"]["deterministic_routing_policy"] == "deterministic_preferred"
    assert status["runtime_execution_profile"]["compute_routing_policy"] == "hybrid_compute_lane"
    assert status["runtime_execution_profile"]["policy_compiler_mode"] == "guarded_policy_compilation"
    assert status["runtime_execution_profile"]["permission_validation_policy"] == "policy_guided_validation"
    assert status["runtime_execution_profile"]["delegation_scope_policy"] == "policy_bounded_delegation"
    assert status["runtime_execution_profile"]["execution_broker_policy"] == "broker_policy_guarded"
    assert expected["summary"]["total_areas"] == len(expected["areas"])
    assert expected["summary"]["remediation_threshold_percent"] == 50
    assert expected["summary"]["low_completion_areas"] >= 1
    assert len(expected["summary"]["low_completion_area_ids"]) == expected["summary"]["low_completion_areas"]
    assert status["runtime_execution_profile"]["execution_enforcement_level"] == "policy_guarded"
    dynamic_chain = next(
        item for item in expected["areas"] if item["area"] == "dynamic_chain_test_coverage"
    )
    assert dynamic_chain["percent"] == 100


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
    assert strict["self_improvement_rd_candidate"] == "governed_policy_tuning_loop"
    assert strict["approval_checkpoint_policy"] == "mandatory"
    assert strict["budget_enforcement_mode"] == "hard_cap"
    assert strict["audit_logging_policy"] == "immutable_full_stream"
    assert strict["escalation_routing_policy"] == "mandatory_human_chain"
    assert strict["tool_mediation_policy"] == "allowlist_mandatory_mediation"
    assert strict["deterministic_routing_policy"] == "deterministic_only"
    assert strict["compute_routing_policy"] == "deterministic_compute_lane"
    assert strict["policy_compiler_mode"] == "locked_policy_compilation"
    assert strict["permission_validation_policy"] == "explicit_role_validation"
    assert strict["delegation_scope_policy"] == "role_bound_delegation_only"
    assert strict["execution_broker_policy"] == "broker_hard_gate"
    assert strict["escalation_policy"] == "mandatory"
    assert dynamic["execution_mode"] == "dynamic"
    assert dynamic["execution_profile_source"] == "onboarding"
    assert dynamic["execution_enforcement_level"] == "autonomy_accelerated"
    assert dynamic["control_plane_separation_state"] == "relaxed"
    assert dynamic["self_improvement_rd_candidate"] == "autonomous_feedback_acceleration_loop"
    assert dynamic["approval_checkpoint_policy"] == "on_demand"
    assert dynamic["budget_enforcement_mode"] == "user_tunable"
    assert dynamic["audit_logging_policy"] == "sampled_governance_stream"
    assert dynamic["escalation_routing_policy"] == "exception_only_chain"
    assert dynamic["tool_mediation_policy"] == "accelerated_mediation_with_guardrails"
    assert dynamic["deterministic_routing_policy"] == "deterministic_fallback"
    assert dynamic["compute_routing_policy"] == "adaptive_compute_lane"
    assert dynamic["policy_compiler_mode"] == "adaptive_policy_compilation"
    assert dynamic["permission_validation_policy"] == "adaptive_validation_with_bounds"
    assert dynamic["delegation_scope_policy"] == "adaptive_delegation_with_caps"
    assert dynamic["execution_broker_policy"] == "broker_adaptive_guardrailed"
    assert dynamic["audit_requirements"] == "minimal"
