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
    assert preview["runtime_execution_profile"]["role_registry_policy"] == status["runtime_execution_profile"]["role_registry_policy"]
    assert preview["runtime_execution_profile"]["authority_boundary_policy"] == status["runtime_execution_profile"]["authority_boundary_policy"]
    assert preview["runtime_execution_profile"]["cross_department_arbitration_policy"] == status["runtime_execution_profile"]["cross_department_arbitration_policy"]
    assert preview["runtime_execution_profile"]["department_memory_isolation_policy"] == status["runtime_execution_profile"]["department_memory_isolation_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_responsibility_policy"] == status["runtime_execution_profile"]["employee_contract_responsibility_policy"]
    assert preview["runtime_execution_profile"]["core_responsibility_scope"] == status["runtime_execution_profile"]["core_responsibility_scope"]
    assert preview["runtime_execution_profile"]["shadow_agent_account_policy"] == status["runtime_execution_profile"]["shadow_agent_account_policy"]
    assert preview["runtime_execution_profile"]["user_base_management_surface_policy"] == status["runtime_execution_profile"]["user_base_management_surface_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_change_authority_policy"] == status["runtime_execution_profile"]["employee_contract_change_authority_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_management_surface_policy"] == status["runtime_execution_profile"]["employee_contract_management_surface_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_accountability_policy"] == status["runtime_execution_profile"]["employee_contract_accountability_policy"]
    assert preview["runtime_execution_profile"]["shadow_agent_org_parity_policy"] == status["runtime_execution_profile"]["shadow_agent_org_parity_policy"]
    assert preview["runtime_execution_profile"]["shadow_agent_contract_binding_policy"] == status["runtime_execution_profile"]["shadow_agent_contract_binding_policy"]
    assert preview["runtime_execution_profile"]["user_base_access_governance_policy"] == status["runtime_execution_profile"]["user_base_access_governance_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_obligation_tracking_policy"] == status["runtime_execution_profile"]["employee_contract_obligation_tracking_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_escalation_binding_policy"] == status["runtime_execution_profile"]["employee_contract_escalation_binding_policy"]
    assert preview["runtime_execution_profile"]["regulatory_context_binding_policy"] == status["runtime_execution_profile"]["regulatory_context_binding_policy"]
    assert preview["runtime_execution_profile"]["autonomy_preference_override_policy"] == status["runtime_execution_profile"]["autonomy_preference_override_policy"]
    assert preview["runtime_execution_profile"]["risk_tolerance_enforcement_policy"] == status["runtime_execution_profile"]["risk_tolerance_enforcement_policy"]
    assert preview["runtime_execution_profile"]["safety_level_assurance_policy"] == status["runtime_execution_profile"]["safety_level_assurance_policy"]
    assert preview["runtime_execution_profile"]["delegation_comfort_governance_policy"] == status["runtime_execution_profile"]["delegation_comfort_governance_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_review_policy"] == status["runtime_execution_profile"]["employee_contract_review_policy"]
    assert preview["runtime_execution_profile"]["employee_contract_versioning_policy"] == status["runtime_execution_profile"]["employee_contract_versioning_policy"]
    assert preview["runtime_execution_profile"]["shadow_agent_account_lifecycle_policy"] == status["runtime_execution_profile"]["shadow_agent_account_lifecycle_policy"]
    assert preview["runtime_execution_profile"]["user_base_ui_audit_policy"] == status["runtime_execution_profile"]["user_base_ui_audit_policy"]
    assert preview["runtime_execution_profile"]["org_chart_assignment_sync_policy"] == status["runtime_execution_profile"]["org_chart_assignment_sync_policy"]
    assert preview["runtime_execution_profile"]["event_queue_durability_policy"] == status["runtime_execution_profile"]["event_queue_durability_policy"]
    assert preview["runtime_execution_profile"]["idempotency_key_enforcement_policy"] == status["runtime_execution_profile"]["idempotency_key_enforcement_policy"]
    assert preview["runtime_execution_profile"]["retry_backoff_policy"] == status["runtime_execution_profile"]["retry_backoff_policy"]
    assert preview["runtime_execution_profile"]["circuit_breaker_policy"] == status["runtime_execution_profile"]["circuit_breaker_policy"]
    assert preview["runtime_execution_profile"]["rollback_recovery_policy"] == status["runtime_execution_profile"]["rollback_recovery_policy"]
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
    assert status["runtime_execution_profile"]["role_registry_policy"] == "governed_role_registry"
    assert status["runtime_execution_profile"]["authority_boundary_policy"] == "policy_scoped_authority_boundaries"
    assert status["runtime_execution_profile"]["cross_department_arbitration_policy"] == "policy_scored_arbitration"
    assert status["runtime_execution_profile"]["department_memory_isolation_policy"] == "policy_scoped_isolation"
    assert status["runtime_execution_profile"]["employee_contract_responsibility_policy"] == "contract_guided_responsibilities"
    assert status["runtime_execution_profile"]["core_responsibility_scope"] == "org_chart_role_and_contract_policy_boundaries"
    assert status["runtime_execution_profile"]["shadow_agent_account_policy"] == "policy_governed_shadow_accounts"
    assert status["runtime_execution_profile"]["user_base_management_surface_policy"] == "admin_ui_with_policy_api"
    assert status["runtime_execution_profile"]["employee_contract_change_authority_policy"] == "policy_scoped_manager_plus_hr_approval"
    assert status["runtime_execution_profile"]["employee_contract_management_surface_policy"] == "hr_admin_ui_with_policy_api"
    assert status["runtime_execution_profile"]["employee_contract_accountability_policy"] == "contract_obligation_attestation_guided"
    assert status["runtime_execution_profile"]["shadow_agent_org_parity_policy"] == "policy_validated_org_role_shadowing"
    assert status["runtime_execution_profile"]["shadow_agent_contract_binding_policy"] == "contract_binding_policy_guided"
    assert status["runtime_execution_profile"]["user_base_access_governance_policy"] == "rbac_policy_governed_controls"
    assert status["runtime_execution_profile"]["employee_contract_obligation_tracking_policy"] == "obligation_tracking_policy_guided"
    assert status["runtime_execution_profile"]["employee_contract_escalation_binding_policy"] == "contract_escalation_binding_policy_guided"
    assert status["runtime_execution_profile"]["regulatory_context_binding_policy"] == "regulatory_context_policy_guided"
    assert status["runtime_execution_profile"]["autonomy_preference_override_policy"] == "autonomy_override_policy_scoped"
    assert status["runtime_execution_profile"]["risk_tolerance_enforcement_policy"] == "risk_tolerance_policy_scored"
    assert status["runtime_execution_profile"]["safety_level_assurance_policy"] == "safety_level_attestation_guided"
    assert status["runtime_execution_profile"]["delegation_comfort_governance_policy"] == "delegation_comfort_policy_bounds"
    assert status["runtime_execution_profile"]["employee_contract_review_policy"] == "hr_review_policy_guided"
    assert status["runtime_execution_profile"]["employee_contract_versioning_policy"] == "governed_contract_version_history"
    assert status["runtime_execution_profile"]["shadow_agent_account_lifecycle_policy"] == "policy_guided_shadow_lifecycle"
    assert status["runtime_execution_profile"]["user_base_ui_audit_policy"] == "governed_ui_audit_stream"
    assert status["runtime_execution_profile"]["org_chart_assignment_sync_policy"] == "policy_scoped_org_chart_sync"
    assert status["runtime_execution_profile"]["event_queue_durability_policy"] == "durable_queue_policy_guided"
    assert status["runtime_execution_profile"]["idempotency_key_enforcement_policy"] == "idempotency_keys_policy_scoped"
    assert status["runtime_execution_profile"]["retry_backoff_policy"] == "policy_scoped_retry_backoff"
    assert status["runtime_execution_profile"]["circuit_breaker_policy"] == "circuit_breaker_policy_guarded"
    assert status["runtime_execution_profile"]["rollback_recovery_policy"] == "policy_scoped_rollback_recovery"
    assert expected["summary"]["total_areas"] == len(expected["areas"])
    assert expected["summary"]["remediation_threshold_percent"] == 50
    assert expected["summary"]["low_completion_areas"] >= 1
    assert len(expected["summary"]["low_completion_area_ids"]) == expected["summary"]["low_completion_areas"]
    assert status["runtime_execution_profile"]["execution_enforcement_level"] == "policy_guarded"
    dynamic_chain = next(
        item for item in expected["areas"] if item["area"] == "dynamic_chain_test_coverage"
    )
    assert dynamic_chain["percent"] == 96


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
    assert strict["role_registry_policy"] == "immutable_role_registry"
    assert strict["authority_boundary_policy"] == "hard_authority_boundaries"
    assert strict["cross_department_arbitration_policy"] == "explicit_executive_arbitration"
    assert strict["department_memory_isolation_policy"] == "strict_department_isolation"
    assert strict["employee_contract_responsibility_policy"] == "contract_bound_responsibilities_required"
    assert strict["core_responsibility_scope"] == "org_chart_role_and_contract_hard_boundaries"
    assert strict["shadow_agent_account_policy"] == "identity_bound_shadow_accounts"
    assert strict["user_base_management_surface_policy"] == "admin_ui_only"
    assert strict["employee_contract_change_authority_policy"] == "hr_admin_approval_required"
    assert strict["employee_contract_management_surface_policy"] == "hr_admin_ui_only"
    assert strict["employee_contract_accountability_policy"] == "contract_obligation_attestation_required"
    assert strict["shadow_agent_org_parity_policy"] == "one_to_one_org_role_shadow_required"
    assert strict["shadow_agent_contract_binding_policy"] == "contract_binding_mandatory"
    assert strict["user_base_access_governance_policy"] == "rbac_and_tenant_controls_mandatory"
    assert strict["employee_contract_obligation_tracking_policy"] == "obligation_tracking_required"
    assert strict["employee_contract_escalation_binding_policy"] == "contract_escalation_binding_required"
    assert strict["regulatory_context_binding_policy"] == "regulatory_context_lockdown_required"
    assert strict["autonomy_preference_override_policy"] == "autonomy_override_disabled"
    assert strict["risk_tolerance_enforcement_policy"] == "low_risk_mandatory_enforcement"
    assert strict["safety_level_assurance_policy"] == "safety_level_attestation_required"
    assert strict["delegation_comfort_governance_policy"] == "delegation_comfort_hard_limits"
    assert strict["employee_contract_review_policy"] == "hr_legal_review_mandatory"
    assert strict["employee_contract_versioning_policy"] == "immutable_contract_version_history"
    assert strict["shadow_agent_account_lifecycle_policy"] == "hr_controlled_shadow_lifecycle"
    assert strict["user_base_ui_audit_policy"] == "immutable_ui_audit_stream"
    assert strict["org_chart_assignment_sync_policy"] == "mandatory_org_chart_sync_before_execution"
    assert strict["event_queue_durability_policy"] == "durable_queue_required"
    assert strict["idempotency_key_enforcement_policy"] == "idempotency_keys_mandatory"
    assert strict["retry_backoff_policy"] == "bounded_retry_with_manual_escalation"
    assert strict["circuit_breaker_policy"] == "circuit_breaker_hard_fail_closed"
    assert strict["rollback_recovery_policy"] == "rollback_required_on_policy_breach"
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
    assert dynamic["role_registry_policy"] == "adaptive_role_registry_with_audit"
    assert dynamic["authority_boundary_policy"] == "adaptive_authority_boundaries_with_audit"
    assert dynamic["cross_department_arbitration_policy"] == "adaptive_arbitration_with_audit"
    assert dynamic["department_memory_isolation_policy"] == "adaptive_isolation_with_audit"
    assert dynamic["employee_contract_responsibility_policy"] == "contract_aware_adaptive_responsibilities"
    assert dynamic["core_responsibility_scope"] == "org_chart_role_and_contract_adaptive_boundaries"
    assert dynamic["shadow_agent_account_policy"] == "adaptive_shadow_accounts_with_audit"
    assert dynamic["user_base_management_surface_policy"] == "admin_ui_plus_delegated_api_with_audit"
    assert dynamic["employee_contract_change_authority_policy"] == "delegated_manager_updates_with_hr_audit"
    assert dynamic["employee_contract_management_surface_policy"] == "hr_admin_ui_plus_delegated_api_with_audit"
    assert dynamic["employee_contract_accountability_policy"] == "contract_obligation_attestation_adaptive"
    assert dynamic["shadow_agent_org_parity_policy"] == "adaptive_org_role_shadowing_with_audit"
    assert dynamic["shadow_agent_contract_binding_policy"] == "contract_binding_adaptive_with_audit"
    assert dynamic["user_base_access_governance_policy"] == "adaptive_rbac_controls_with_audit"
    assert dynamic["employee_contract_obligation_tracking_policy"] == "obligation_tracking_adaptive_with_audit"
    assert dynamic["employee_contract_escalation_binding_policy"] == "contract_escalation_binding_adaptive"
    assert dynamic["regulatory_context_binding_policy"] == "regulatory_context_adaptive_with_audit"
    assert dynamic["autonomy_preference_override_policy"] == "autonomy_override_user_tunable_with_audit"
    assert dynamic["risk_tolerance_enforcement_policy"] == "risk_tolerance_adaptive_with_caps"
    assert dynamic["safety_level_assurance_policy"] == "safety_level_attestation_adaptive"
    assert dynamic["delegation_comfort_governance_policy"] == "delegation_comfort_adaptive_bounds"
    assert dynamic["employee_contract_review_policy"] == "adaptive_hr_review_with_audit"
    assert dynamic["employee_contract_versioning_policy"] == "adaptive_contract_version_history_with_audit"
    assert dynamic["shadow_agent_account_lifecycle_policy"] == "adaptive_shadow_lifecycle_with_audit"
    assert dynamic["user_base_ui_audit_policy"] == "sampled_ui_audit_stream_with_escalation"
    assert dynamic["org_chart_assignment_sync_policy"] == "adaptive_org_chart_sync_with_audit"
    assert dynamic["event_queue_durability_policy"] == "durable_queue_adaptive_with_audit"
    assert dynamic["idempotency_key_enforcement_policy"] == "idempotency_keys_adaptive_with_audit"
    assert dynamic["retry_backoff_policy"] == "adaptive_retry_backoff_with_guardrails"
    assert dynamic["circuit_breaker_policy"] == "circuit_breaker_adaptive_with_audit"
    assert dynamic["rollback_recovery_policy"] == "adaptive_rollback_recovery_with_audit"
    assert dynamic["audit_requirements"] == "minimal"
