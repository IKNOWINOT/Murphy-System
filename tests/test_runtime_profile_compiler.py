"""Tests for the Runtime Profile Compiler module."""

import pytest
from src.runtime_profile_compiler import (
    RuntimeMode,
    SafetyLevel,
    AutonomyLevel,
    EscalationPolicy,
    BudgetConstraints,
    ToolPermissions,
    AuditRequirements,
    RuntimeExecutionProfile,
    RuntimeProfileCompiler,
)


@pytest.fixture
def compiler():
    return RuntimeProfileCompiler()


# ------------------------------------------------------------------
# Profile compilation – industry-based inference
# ------------------------------------------------------------------

class TestCompileProfileIndustry:

    @pytest.mark.parametrize("industry", ["healthcare", "finance", "government"])
    def test_strict_industry(self, compiler, industry):
        profile = compiler.compile_profile("org-1", {"industry": industry})
        assert profile.runtime_mode == RuntimeMode.STRICT
        assert profile.safety_level == SafetyLevel.CRITICAL
        assert profile.autonomy_level == AutonomyLevel.HUMAN_SUPERVISED
        assert profile.confidence_threshold == 0.95
        assert profile.audit_requirements.audit_all_executions is True
        assert profile.audit_requirements.retention_days == 365
        assert profile.escalation_policy.max_retries_before_escalation == 1

    @pytest.mark.parametrize("industry", ["technology", "saas"])
    def test_balanced_industry(self, compiler, industry):
        profile = compiler.compile_profile("org-2", {"industry": industry})
        assert profile.runtime_mode == RuntimeMode.BALANCED
        assert profile.safety_level == SafetyLevel.MEDIUM
        assert profile.confidence_threshold == 0.8

    def test_unknown_industry_defaults_balanced(self, compiler):
        profile = compiler.compile_profile("org-3", {"industry": "retail"})
        assert profile.runtime_mode == RuntimeMode.BALANCED
        assert profile.safety_level == SafetyLevel.MEDIUM

    def test_missing_industry_defaults_balanced(self, compiler):
        profile = compiler.compile_profile("org-4", {})
        assert profile.runtime_mode == RuntimeMode.BALANCED

    def test_industry_case_insensitive(self, compiler):
        profile = compiler.compile_profile("org-5", {"industry": " Healthcare "})
        assert profile.runtime_mode == RuntimeMode.STRICT


# ------------------------------------------------------------------
# Profile compilation – compliance & budget
# ------------------------------------------------------------------

class TestCompileProfileOptions:

    def test_compliance_frameworks_set_audit(self, compiler):
        data = {
            "industry": "technology",
            "compliance_frameworks": ["SOC2", "GDPR"],
        }
        profile = compiler.compile_profile("org-c1", data)
        assert profile.audit_requirements.require_compliance_check is True
        assert profile.audit_requirements.frameworks == ["SOC2", "GDPR"]
        assert profile.audit_requirements.retention_days == 180

    def test_budget_constraints_from_onboarding(self, compiler):
        data = {
            "industry": "technology",
            "budget": {
                "max_cost_per_task": 25.0,
                "daily_budget_limit": 1000.0,
            },
        }
        profile = compiler.compile_profile("org-b1", data)
        assert profile.budget_constraints.max_cost_per_task == 25.0
        assert profile.budget_constraints.daily_budget_limit == 1000.0
        # defaults preserved for unset fields
        assert profile.budget_constraints.max_cost_per_session == 100.0

    def test_tool_permissions_from_onboarding(self, compiler):
        data = {
            "tool_permissions": {
                "allowed_tools": ["search", "calculator"],
                "denied_tools": ["delete_all"],
            },
        }
        profile = compiler.compile_profile("org-tp", data)
        assert "search" in profile.tool_permissions.allowed_tools
        assert "delete_all" in profile.tool_permissions.denied_tools

    def test_explicit_autonomy_level(self, compiler):
        data = {"autonomy_level": "autonomous"}
        profile = compiler.compile_profile("org-a1", data)
        assert profile.autonomy_level == AutonomyLevel.AUTONOMOUS

    def test_escalation_chain_from_onboarding(self, compiler):
        data = {"escalation_chain": ["lead", "vp", "cto"]}
        profile = compiler.compile_profile("org-e1", data)
        assert profile.escalation_policy.escalation_chain == ["lead", "vp", "cto"]


# ------------------------------------------------------------------
# Profile retrieval
# ------------------------------------------------------------------

class TestProfileRetrieval:

    def test_get_profile_by_id(self, compiler):
        profile = compiler.compile_profile("org-r1", {"industry": "technology"})
        fetched = compiler.get_profile(profile.profile_id)
        assert fetched is not None
        assert fetched.profile_id == profile.profile_id

    def test_get_profile_not_found(self, compiler):
        assert compiler.get_profile("nonexistent") is None

    def test_get_org_profile(self, compiler):
        compiler.compile_profile("org-r2", {"industry": "finance"})
        fetched = compiler.get_org_profile("org-r2")
        assert fetched is not None
        assert fetched.org_id == "org-r2"

    def test_get_org_profile_not_found(self, compiler):
        assert compiler.get_org_profile("no-such-org") is None

    def test_recompile_replaces_org_profile(self, compiler):
        p1 = compiler.compile_profile("org-r3", {"industry": "technology"})
        p2 = compiler.compile_profile("org-r3", {"industry": "healthcare"})
        assert p1.profile_id != p2.profile_id
        active = compiler.get_org_profile("org-r3")
        assert active.profile_id == p2.profile_id
        assert active.runtime_mode == RuntimeMode.STRICT


# ------------------------------------------------------------------
# Execution permission checks
# ------------------------------------------------------------------

class TestCheckExecutionAllowed:

    def test_allowed_basic(self, compiler):
        profile = compiler.compile_profile("org-x1", {"industry": "technology"})
        allowed, reason = compiler.check_execution_allowed(profile.profile_id, "search")
        assert allowed is True
        assert reason == "allowed"

    def test_denied_tool(self, compiler):
        data = {"tool_permissions": {"denied_tools": ["rm_rf"]}}
        profile = compiler.compile_profile("org-x2", data)
        allowed, reason = compiler.check_execution_allowed(profile.profile_id, "rm_rf")
        assert allowed is False
        assert "denied" in reason

    def test_not_in_allowed_list(self, compiler):
        data = {"tool_permissions": {"allowed_tools": ["search"]}}
        profile = compiler.compile_profile("org-x3", data)
        allowed, reason = compiler.check_execution_allowed(profile.profile_id, "delete")
        assert allowed is False
        assert "not in allowed" in reason

    def test_requires_approval(self, compiler):
        data = {"tool_permissions": {"require_approval_tools": ["deploy"]}}
        profile = compiler.compile_profile("org-x4", data)
        allowed, reason = compiler.check_execution_allowed(profile.profile_id, "deploy")
        assert allowed is False
        assert "requires approval" in reason

    def test_budget_exceeded(self, compiler):
        data = {"budget": {"max_cost_per_task": 5.0}}
        profile = compiler.compile_profile("org-x5", data)
        allowed, reason = compiler.check_execution_allowed(
            profile.profile_id, "search", estimated_cost=10.0,
        )
        assert allowed is False
        assert "exceeds" in reason

    def test_low_confidence_rejected(self, compiler):
        profile = compiler.compile_profile("org-x6", {"industry": "healthcare"})
        # strict mode → threshold 0.95
        allowed, reason = compiler.check_execution_allowed(
            profile.profile_id, "search", confidence=0.5,
        )
        assert allowed is False
        assert "confidence" in reason

    def test_profile_not_found(self, compiler):
        allowed, reason = compiler.check_execution_allowed("bad-id", "search")
        assert allowed is False
        assert reason == "profile_not_found"


# ------------------------------------------------------------------
# Autonomy checks
# ------------------------------------------------------------------

class TestCheckAutonomy:

    def test_full_human_always_denied(self, compiler):
        data = {"autonomy_level": "full_human"}
        profile = compiler.compile_profile("org-au1", data)
        ok, reason = compiler.check_autonomy(profile.profile_id, confidence=1.0)
        assert ok is False
        assert "human" in reason.lower()

    def test_human_supervised_denied(self, compiler):
        profile = compiler.compile_profile("org-au2", {"industry": "healthcare"})
        ok, reason = compiler.check_autonomy(profile.profile_id, confidence=1.0)
        assert ok is False

    def test_confidence_gated_passes(self, compiler):
        profile = compiler.compile_profile("org-au3", {"industry": "technology"})
        # balanced → confidence_gated, threshold 0.8
        ok, reason = compiler.check_autonomy(profile.profile_id, confidence=0.9)
        assert ok is True

    def test_confidence_gated_fails(self, compiler):
        profile = compiler.compile_profile("org-au4", {"industry": "technology"})
        ok, reason = compiler.check_autonomy(profile.profile_id, confidence=0.5)
        assert ok is False
        assert "confidence" in reason

    def test_autonomous_always_allowed(self, compiler):
        data = {"autonomy_level": "autonomous"}
        profile = compiler.compile_profile("org-au5", data)
        ok, reason = compiler.check_autonomy(profile.profile_id, confidence=0.1)
        assert ok is True

    def test_autonomy_profile_not_found(self, compiler):
        ok, reason = compiler.check_autonomy("nope", 1.0)
        assert ok is False
        assert reason == "profile_not_found"


# ------------------------------------------------------------------
# Profile updates
# ------------------------------------------------------------------

class TestUpdateProfile:

    def test_update_scalar_field(self, compiler):
        profile = compiler.compile_profile("org-u1", {"industry": "technology"})
        updated = compiler.update_profile(profile.profile_id, {
            "confidence_threshold": 0.6,
        })
        assert updated is not None
        assert updated.confidence_threshold == 0.6

    def test_update_runtime_mode(self, compiler):
        profile = compiler.compile_profile("org-u2", {"industry": "technology"})
        updated = compiler.update_profile(profile.profile_id, {
            "runtime_mode": "strict",
        })
        assert updated.runtime_mode == RuntimeMode.STRICT

    def test_update_nested_budget(self, compiler):
        profile = compiler.compile_profile("org-u3", {})
        updated = compiler.update_profile(profile.profile_id, {
            "budget_constraints": {"daily_budget_limit": 9999.0},
        })
        assert updated.budget_constraints.daily_budget_limit == 9999.0

    def test_update_nested_escalation(self, compiler):
        profile = compiler.compile_profile("org-u4", {})
        updated = compiler.update_profile(profile.profile_id, {
            "escalation_policy": {"max_retries_before_escalation": 10},
        })
        assert updated.escalation_policy.max_retries_before_escalation == 10

    def test_update_nested_audit(self, compiler):
        profile = compiler.compile_profile("org-u5", {})
        updated = compiler.update_profile(profile.profile_id, {
            "audit_requirements": {"retention_days": 730},
        })
        assert updated.audit_requirements.retention_days == 730

    def test_update_not_found(self, compiler):
        assert compiler.update_profile("missing", {"confidence_threshold": 0.1}) is None

    def test_updated_at_changes(self, compiler):
        profile = compiler.compile_profile("org-u6", {})
        original_ts = profile.updated_at
        updated = compiler.update_profile(profile.profile_id, {
            "confidence_threshold": 0.5,
        })
        assert updated.updated_at >= original_ts


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

class TestGetStatus:

    def test_empty_status(self, compiler):
        status = compiler.get_status()
        assert status["total_profiles"] == 0
        assert status["total_orgs"] == 0
        assert status["mode_distribution"] == {}

    def test_status_after_compilation(self, compiler):
        compiler.compile_profile("org-s1", {"industry": "healthcare"})
        compiler.compile_profile("org-s2", {"industry": "technology"})
        status = compiler.get_status()
        assert status["total_profiles"] == 2
        assert status["total_orgs"] == 2
        assert status["mode_distribution"]["strict"] == 1
        assert status["mode_distribution"]["balanced"] == 1


# ------------------------------------------------------------------
# Dataclass edge cases
# ------------------------------------------------------------------

class TestDataclassDefaults:

    def test_escalation_threshold_clamped(self):
        ep = EscalationPolicy(escalation_threshold=1.5)
        assert ep.escalation_threshold == 1.0
        ep2 = EscalationPolicy(escalation_threshold=-0.3)
        assert ep2.escalation_threshold == 0.0

    def test_tool_permissions_defaults_empty(self):
        tp = ToolPermissions()
        assert tp.allowed_tools == set()
        assert tp.denied_tools == set()

    def test_audit_defaults(self):
        ar = AuditRequirements()
        assert ar.audit_all_executions is False
        assert ar.retention_days == 90
