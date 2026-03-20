from __future__ import annotations

from typing import Dict, List


class FounderPrivilegeOverlay:
    """Machine-readable founder privilege policy.

    Founder remains a privileged overlay on the canonical runtime, not the default
    audience identity. This surface defines what the founder workstation and
    founder-scoped automations are allowed to do compared with non-founder
    accounts.
    """

    def workstation_policy(self) -> Dict[str, object]:
        return {
            "identity": "founder_overlay",
            "workstation_mode": "privileged",
            "direct_platform_changes": True,
            "direct_code_additions": True,
            "direct_runtime_configuration": True,
            "can_create_modules": True,
            "can_patch_existing_modules": True,
            "can_trigger_privileged_boot_paths": True,
            "guardrails": [
                "canonical_execution_remains_default_runtime_identity",
                "founder_visibility_is_overlay_not_default_audience",
                "changes_should_still_flow_through_traceable_runtime_surfaces",
            ],
        }

    def automation_policy(self) -> Dict[str, object]:
        founder_features = [
            "all_available_automation_features",
            "privileged_runtime_actions",
            "privileged_code_generation",
            "privileged_code_patch_execution",
            "privileged_route_and_family_override_review",
            "privileged_inventory_and_visibility_access",
            "privileged_recovery_and_fallback_controls",
        ]
        standard_restrictions = [
            "no_founder_privileged_runtime_actions",
            "no_founder_direct_code_additions",
            "no_founder_privileged_override_controls",
        ]
        return {
            "founder_automation_mode": "full_bore",
            "founder_feature_set": founder_features,
            "standard_account_restrictions": standard_restrictions,
            "founder_automation_count": len(founder_features),
            "standard_restriction_count": len(standard_restrictions),
        }

    def account_policy_matrix(self) -> Dict[str, object]:
        founder = {
            "account_type": "founder",
            "default_runtime_identity": False,
            "overlay_identity": True,
            "direct_platform_changes": True,
            "direct_code_additions": True,
            "full_automation_features": True,
            "privileged_visibility": True,
        }
        standard = {
            "account_type": "standard",
            "default_runtime_identity": True,
            "overlay_identity": False,
            "direct_platform_changes": False,
            "direct_code_additions": False,
            "full_automation_features": False,
            "privileged_visibility": False,
        }
        return {
            "founder": founder,
            "standard": standard,
            "differences": [
                "founder_can_change_platform_directly_from_workstation",
                "founder_can_add_code_directly_from_workstation",
                "founder_automations_have_full_feature_access",
                "standard_accounts_use_constrained_non_founder_capabilities",
            ],
        }

    def summary(self) -> Dict[str, object]:
        workstation = self.workstation_policy()
        automation = self.automation_policy()
        matrix = self.account_policy_matrix()
        return {
            "founder_overlay_enabled": True,
            "direct_platform_changes": workstation["direct_platform_changes"],
            "direct_code_additions": workstation["direct_code_additions"],
            "full_automation_features": automation["founder_automation_mode"] == "full_bore",
            "standard_accounts_constrained": not matrix["standard"]["full_automation_features"],
            "guardrail_count": len(workstation["guardrails"]),
        }
