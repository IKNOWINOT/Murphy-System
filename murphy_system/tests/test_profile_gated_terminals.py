"""
Tests for profile-gated terminals — terminal config assembly, role-based
access, and feature gating from user profiles.

Design Label: TEST-TERMINALS-001
Owner: QA Team
"""
import os
import pytest


from signup_gateway import (
    SignupGateway,
    AuthError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_onboarded_profile(gw, name, email, position, new_org_name,
                             role_override=None):
    p = gw.signup(
        name=name, email=email, position=position,
        justification="Need terminal access",
        new_org_name=new_org_name,
    )
    gw.validate_email(p.user_id, p.email_validation_token)
    gw.accept_eula(p.user_id)
    if role_override:
        gw.update_profile(p.user_id, {"role": role_override})
    return gw.get_profile(p.user_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gw():
    return SignupGateway()


@pytest.fixture
def founder(gw):
    return _make_onboarded_profile(gw, "Alice Founder", "alice@example.com",
                                    "CTO", "FounderOrg")


@pytest.fixture
def manager(gw):
    p = gw.signup(
        name="Bob Manager", email="bob@example.com",
        position="Engineering Manager", justification="Team oversight",
        new_org_name="ManagerOrg",
    )
    gw.validate_email(p.user_id, p.email_validation_token)
    gw.accept_eula(p.user_id)
    gw.update_profile(p.user_id, {"role": "manager"})
    return gw.get_profile(p.user_id)


@pytest.fixture
def worker_engineer(gw):
    return _make_onboarded_profile(
        gw, "Carol Worker", "carol@example.com",
        "Software Engineer", "WorkerOrg", role_override="worker"
    )


@pytest.fixture
def worker_analyst(gw):
    return _make_onboarded_profile(
        gw, "Dave Analyst", "dave@example.com",
        "Data Analyst", "AnalystOrg", role_override="worker"
    )


# ---------------------------------------------------------------------------
# Access gate
# ---------------------------------------------------------------------------


class TestAccessGate:
    def test_not_signed_up_denied(self, gw):
        result = gw.check_terminal_access("nonexistent")
        assert result["allowed"] is False
        assert result["reason"] == "user_not_found"

    def test_signed_up_only_denied(self, gw):
        p = gw.signup(name="X", email="x@x.com", position="Dev",
                      justification="J", new_org_name="O")
        result = gw.check_terminal_access(p.user_id)
        assert result["allowed"] is False
        assert result["reason"] == "email_not_validated"

    def test_email_validated_no_eula_denied(self, gw):
        p = gw.signup(name="Y", email="y@x.com", position="Dev",
                      justification="J", new_org_name="P")
        gw.validate_email(p.user_id, p.email_validation_token)
        result = gw.check_terminal_access(p.user_id)
        assert result["allowed"] is False
        assert result["reason"] == "eula_not_accepted"

    def test_fully_onboarded_allowed(self, gw, founder):
        result = gw.check_terminal_access(founder.user_id)
        assert result["allowed"] is True
        assert result["reason"] == "ok"

    def test_check_returns_profile_dict(self, gw, founder):
        result = gw.check_terminal_access(founder.user_id)
        assert isinstance(result["profile"], dict)
        assert result["profile"]["user_id"] == founder.user_id


# ---------------------------------------------------------------------------
# Founder/admin terminal config
# ---------------------------------------------------------------------------


class TestFounderTerminalConfig:
    def test_founder_gets_architect_terminal(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["features"].get("architect_terminal") is True

    def test_founder_gets_org_chart_editor(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["features"].get("org_chart_editor") is True

    def test_founder_gets_user_management(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["features"].get("user_management") is True

    def test_founder_gets_wildcard_commands(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["commands"] == ["*"]

    def test_founder_role_in_config(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["role"] == "founder_admin"

    def test_config_saved_to_profile(self, gw, founder):
        gw.assemble_terminal_config(founder.user_id)
        p = gw.get_profile(founder.user_id)
        assert p.terminal_config
        assert "features" in p.terminal_config


# ---------------------------------------------------------------------------
# Manager terminal config
# ---------------------------------------------------------------------------


class TestManagerTerminalConfig:
    def test_manager_gets_team_dashboard(self, gw, manager):
        config = gw.assemble_terminal_config(manager.user_id)
        assert config["features"].get("team_dashboard") is True

    def test_manager_does_not_get_architect_terminal(self, gw, manager):
        config = gw.assemble_terminal_config(manager.user_id)
        assert config["features"].get("architect_terminal") is not True

    def test_manager_gets_limited_commands(self, gw, manager):
        config = gw.assemble_terminal_config(manager.user_id)
        assert "run" in config["commands"]
        assert "*" not in config["commands"]


# ---------------------------------------------------------------------------
# Worker terminal config — inferred from position
# ---------------------------------------------------------------------------


class TestWorkerTerminalConfig:
    def test_engineer_gets_automation_library(self, gw, worker_engineer):
        config = gw.assemble_terminal_config(worker_engineer.user_id)
        assert config["features"].get("automation_library") is True

    def test_analyst_gets_analytics_dashboard(self, gw, worker_analyst):
        config = gw.assemble_terminal_config(worker_analyst.user_id)
        assert config["features"].get("analytics_dashboard") is True

    def test_worker_does_not_get_shadow_agent_config(self, gw, worker_engineer):
        config = gw.assemble_terminal_config(worker_engineer.user_id)
        assert config["features"].get("shadow_agent_config") is not True

    def test_worker_gets_basic_commands(self, gw, worker_engineer):
        config = gw.assemble_terminal_config(worker_engineer.user_id)
        assert "run" in config["commands"]
        assert "status" in config["commands"]


# ---------------------------------------------------------------------------
# Config blocked before full onboarding
# ---------------------------------------------------------------------------


class TestConfigBlockedBeforeOnboarding:
    def test_config_blocked_if_no_email_validation(self, gw):
        p = gw.signup(name="Z", email="z@x.com", position="Dev",
                      justification="J", new_org_name="ZOrg")
        with pytest.raises(AuthError):
            gw.assemble_terminal_config(p.user_id)

    def test_config_blocked_if_no_eula(self, gw):
        p = gw.signup(name="W", email="w@x.com", position="Dev",
                      justification="J", new_org_name="WOrg")
        gw.validate_email(p.user_id, p.email_validation_token)
        with pytest.raises(AuthError):
            gw.assemble_terminal_config(p.user_id)


# ---------------------------------------------------------------------------
# Config has required structure
# ---------------------------------------------------------------------------


class TestConfigStructure:
    def test_config_has_assembled_at(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert "assembled_at" in config

    def test_config_has_user_id(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert config["user_id"] == founder.user_id

    def test_config_has_features_dict(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert isinstance(config["features"], dict)

    def test_config_has_commands_list(self, gw, founder):
        config = gw.assemble_terminal_config(founder.user_id)
        assert isinstance(config["commands"], list)
