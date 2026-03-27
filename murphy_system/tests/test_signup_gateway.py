"""
Tests for SignupGateway — Signup flow, email validation, EULA acceptance,
profile creation and management, terminal access gating.

Design Label: TEST-SIGNUP-001
Owner: QA Team
"""
import os
import pytest


from signup_gateway import (
    SignupGateway,
    UserProfile,
    Organization,
    EulaRecord,
    SignupError,
    AuthError,
    EULA_VERSION,
    EULA_TEXT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gw():
    return SignupGateway()


@pytest.fixture
def signed_up_profile(gw):
    return gw.signup(
        name="Alice Smith",
        email="alice@example.com",
        position="Software Engineer",
        justification="Need to automate CI pipelines",
        department="Engineering",
        new_org_name="Acme Corp",
    )


@pytest.fixture
def validated_profile(gw, signed_up_profile):
    return gw.validate_email(
        signed_up_profile.user_id,
        signed_up_profile.email_validation_token,
    )


@pytest.fixture
def onboarded_profile(gw, validated_profile):
    gw.accept_eula(validated_profile.user_id, ip_address="127.0.0.1")
    return gw.get_profile(validated_profile.user_id)


# ---------------------------------------------------------------------------
# UserProfile model
# ---------------------------------------------------------------------------


class TestUserProfile:
    def test_defaults(self):
        p = UserProfile()
        assert p.user_id
        assert p.role == "worker"
        assert not p.eula_accepted
        assert not p.email_validated
        assert p.terminal_config == {}

    def test_is_fully_onboarded_false_by_default(self):
        p = UserProfile()
        assert not p.is_fully_onboarded()

    def test_is_fully_onboarded_true(self):
        p = UserProfile(email_validated=True, eula_accepted=True)
        assert p.is_fully_onboarded()

    def test_to_dict_keys(self):
        p = UserProfile(name="Bob", email="bob@test.com")
        d = p.to_dict()
        for key in [
            "user_id", "email", "name", "position", "role",
            "eula_accepted", "email_validated", "terminal_config",
        ]:
            assert key in d


# ---------------------------------------------------------------------------
# Signup
# ---------------------------------------------------------------------------


class TestSignup:
    def test_basic_signup(self, gw):
        p = gw.signup(
            name="Bob",
            email="bob@test.com",
            position="Analyst",
            justification="Testing",
            new_org_name="TestOrg",
        )
        assert isinstance(p, UserProfile)
        assert p.name == "Bob"
        assert p.email == "bob@test.com"
        assert p.role == "founder_admin"

    def test_email_normalised_to_lowercase(self, gw):
        p = gw.signup(
            name="Carol",
            email="CAROL@EXAMPLE.COM",
            position="Manager",
            justification="Need access",
            new_org_name="OrgX",
        )
        assert p.email == "carol@example.com"

    def test_new_org_creates_organization(self, gw):
        p = gw.signup(
            name="Dave",
            email="dave@org.com",
            position="Founder",
            justification="Creating new org",
            new_org_name="Dave's Org",
        )
        assert p.role == "founder_admin"
        assert p.org_id
        org_profiles = gw.get_org_profiles(p.org_id)
        assert any(op.user_id == p.user_id for op in org_profiles)

    def test_join_existing_org(self, gw, signed_up_profile):
        org_id = signed_up_profile.org_id
        p2 = gw.signup(
            name="Eve",
            email="eve@example.com",
            position="Worker",
            justification="Joining team",
            org_id=org_id,
        )
        assert p2.org_id == org_id
        assert p2.role == "worker"

    def test_duplicate_email_raises(self, gw, signed_up_profile):
        with pytest.raises(SignupError, match="email already registered"):
            gw.signup(
                name="Duplicate",
                email="alice@example.com",
                position="Any",
                justification="Any",
                new_org_name="OtherOrg",
            )

    def test_missing_name_raises(self, gw):
        with pytest.raises(SignupError, match="name is required"):
            gw.signup(
                name="",
                email="x@x.com",
                position="Pos",
                justification="J",
                new_org_name="O",
            )

    def test_missing_org_raises(self, gw):
        with pytest.raises(SignupError):
            gw.signup(
                name="Frank",
                email="frank@x.com",
                position="Pos",
                justification="J",
            )

    def test_validation_token_generated(self, gw):
        p = gw.signup(
            name="Grace",
            email="grace@x.com",
            position="Dev",
            justification="Test",
            new_org_name="G",
        )
        assert p.email_validation_token
        assert len(p.email_validation_token) == 32  # uuid4 hex


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------


class TestEmailValidation:
    def test_valid_token_sets_flag(self, gw, signed_up_profile):
        p = gw.validate_email(
            signed_up_profile.user_id,
            signed_up_profile.email_validation_token,
        )
        assert p.email_validated

    def test_wrong_token_raises(self, gw, signed_up_profile):
        with pytest.raises(AuthError, match="invalid email validation token"):
            gw.validate_email(signed_up_profile.user_id, "wrongtoken")

    def test_unknown_user_raises(self, gw):
        with pytest.raises(AuthError, match="user not found"):
            gw.validate_email("notexist", "anytoken")

    def test_idempotent_validation(self, gw, signed_up_profile):
        gw.validate_email(signed_up_profile.user_id, signed_up_profile.email_validation_token)
        p2 = gw.validate_email(signed_up_profile.user_id, signed_up_profile.email_validation_token)
        assert p2.email_validated


# ---------------------------------------------------------------------------
# EULA
# ---------------------------------------------------------------------------


class TestEula:
    def test_get_eula_returns_text(self, gw):
        eula = gw.get_eula()
        assert "version" in eula
        assert eula["version"] == EULA_VERSION
        assert "Inoni LLC" in eula["text"]
        assert "NO WARRANTY" in eula["text"]

    def test_accept_eula_records_version_and_timestamp(self, gw, validated_profile):
        record = gw.accept_eula(validated_profile.user_id, ip_address="10.0.0.1")
        assert isinstance(record, EulaRecord)
        assert record.eula_version == EULA_VERSION
        assert record.ip_address == "10.0.0.1"
        assert record.user_id == validated_profile.user_id

    def test_accept_eula_sets_profile_flags(self, gw, validated_profile):
        gw.accept_eula(validated_profile.user_id)
        p = gw.get_profile(validated_profile.user_id)
        assert p.eula_accepted
        assert p.eula_version == EULA_VERSION
        assert p.eula_accepted_at

    def test_eula_before_email_validation_raises(self, gw, signed_up_profile):
        with pytest.raises(AuthError, match="email must be validated"):
            gw.accept_eula(signed_up_profile.user_id)

    def test_eula_unknown_user_raises(self, gw):
        with pytest.raises(AuthError, match="user not found"):
            gw.accept_eula("notexist")


# ---------------------------------------------------------------------------
# Profile management
# ---------------------------------------------------------------------------


class TestProfileManagement:
    def test_get_profile_returns_profile(self, gw, signed_up_profile):
        p = gw.get_profile(signed_up_profile.user_id)
        assert p.user_id == signed_up_profile.user_id

    def test_get_profile_unknown_raises(self, gw):
        with pytest.raises(AuthError):
            gw.get_profile("doesnotexist")

    def test_update_profile(self, gw, signed_up_profile):
        p = gw.update_profile(signed_up_profile.user_id, {"department": "Platform"})
        assert p.department == "Platform"

    def test_update_profile_ignores_immutable_fields(self, gw, signed_up_profile):
        original_email = signed_up_profile.email
        gw.update_profile(signed_up_profile.user_id, {"email": "hacked@x.com"})
        p = gw.get_profile(signed_up_profile.user_id)
        assert p.email == original_email

    def test_get_org_profiles(self, gw, signed_up_profile):
        profiles = gw.get_org_profiles(signed_up_profile.org_id)
        assert any(p.user_id == signed_up_profile.user_id for p in profiles)


# ---------------------------------------------------------------------------
# Terminal config assembly
# ---------------------------------------------------------------------------


class TestTerminalConfig:
    def test_founder_admin_gets_full_access(self, gw, onboarded_profile):
        config = gw.assemble_terminal_config(onboarded_profile.user_id)
        assert config["features"]["architect_terminal"] is True
        assert config["commands"] == ["*"]

    def test_founder_admin_gets_recommended_terminal_and_all_allowed(self, gw, onboarded_profile):
        config = gw.assemble_terminal_config(onboarded_profile.user_id)
        assert config["recommended_terminal"] == "/ui/terminal-unified"
        assert set(config["allowed_terminals"]) == {
            "/ui/terminal-unified",
            "/ui/terminal-worker",
            "/ui/terminal-enhanced",
            "/ui/terminal-architect",
        }

    def test_manager_gets_recommended_terminal_and_limited_allowed(self, gw):
        p = gw.signup(
            name="Mgr",
            email="mgr@x.com",
            position="Team Lead",
            justification="Manage team",
            new_org_name="MgrCorp",
        )
        gw.validate_email(p.user_id, p.email_validation_token)
        gw.accept_eula(p.user_id)
        gw.update_profile(p.user_id, {"role": "manager"})
        config = gw.assemble_terminal_config(p.user_id)
        assert config["recommended_terminal"] == "/ui/terminal-enhanced"
        assert set(config["allowed_terminals"]) == {
            "/ui/terminal-enhanced",
            "/ui/terminal-worker",
        }

    def test_worker_gets_recommended_terminal_and_worker_only(self, gw):
        p = gw.signup(
            name="Worker",
            email="worker@x.com",
            position="Delivery Specialist",
            justification="Do tasks",
            new_org_name="WorkerCorp",
        )
        gw.validate_email(p.user_id, p.email_validation_token)
        gw.accept_eula(p.user_id)
        gw.update_profile(p.user_id, {"role": "worker"})
        config = gw.assemble_terminal_config(p.user_id)
        assert config["recommended_terminal"] == "/ui/terminal-worker"
        assert config["allowed_terminals"] == ["/ui/terminal-worker"]

    def test_worker_engineer_gets_automation_library(self, gw):
        p = gw.signup(
            name="Eng",
            email="eng@x.com",
            position="Software Engineer",
            justification="Build stuff",
            new_org_name="TechCorp",
        )
        gw.validate_email(p.user_id, p.email_validation_token)
        gw.accept_eula(p.user_id)
        # Downgrade role to worker for test
        gw.update_profile(p.user_id, {"role": "worker"})
        config = gw.assemble_terminal_config(p.user_id)
        assert config["features"]["automation_library"] is True

    def test_config_not_available_before_onboarding(self, gw, signed_up_profile):
        with pytest.raises(AuthError):
            gw.assemble_terminal_config(signed_up_profile.user_id)


# ---------------------------------------------------------------------------
# Terminal access gating
# ---------------------------------------------------------------------------


class TestTerminalAccessGating:
    def test_new_user_denied(self, gw, signed_up_profile):
        result = gw.check_terminal_access(signed_up_profile.user_id)
        assert result["allowed"] is False

    def test_email_validated_but_no_eula_denied(self, gw, validated_profile):
        result = gw.check_terminal_access(validated_profile.user_id)
        assert result["allowed"] is False
        assert result["reason"] == "eula_not_accepted"

    def test_fully_onboarded_allowed(self, gw, onboarded_profile):
        result = gw.check_terminal_access(onboarded_profile.user_id)
        assert result["allowed"] is True
        assert result["reason"] == "ok"

    def test_unknown_user_denied(self, gw):
        result = gw.check_terminal_access("notexist")
        assert result["allowed"] is False
        assert result["reason"] == "user_not_found"

    def test_founder_admin_allowed_on_architect_terminal(self, gw, onboarded_profile):
        result = gw.check_terminal_access(onboarded_profile.user_id, "/ui/terminal-architect")
        assert result["allowed"] is True

    def test_worker_denied_on_architect_terminal(self, gw):
        p = gw.signup(
            name="W",
            email="wta@x.com",
            position="Worker",
            justification="Tasks",
            new_org_name="WORG",
        )
        gw.validate_email(p.user_id, p.email_validation_token)
        gw.accept_eula(p.user_id)
        gw.update_profile(p.user_id, {"role": "worker"})
        result = gw.check_terminal_access(p.user_id, "/ui/terminal-architect")
        assert result["allowed"] is False
        assert result["reason"] == "terminal_not_permitted_for_role"
        assert "/ui/terminal-worker" in result["allowed_terminals"]

    def test_worker_allowed_on_worker_terminal(self, gw):
        p = gw.signup(
            name="W2",
            email="wta2@x.com",
            position="Worker",
            justification="Tasks",
            new_org_name="WORG2",
        )
        gw.validate_email(p.user_id, p.email_validation_token)
        gw.accept_eula(p.user_id)
        gw.update_profile(p.user_id, {"role": "worker"})
        result = gw.check_terminal_access(p.user_id, "/ui/terminal-worker")
        assert result["allowed"] is True

    def test_no_terminal_path_skips_role_check(self, gw, onboarded_profile):
        # Without a terminal_path arg, only email/EULA checks apply
        result = gw.check_terminal_access(onboarded_profile.user_id)
        assert result["allowed"] is True
        assert result["reason"] == "ok"


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_audit_log_grows_with_actions(self, gw, onboarded_profile):
        log = gw.get_audit_log()
        # signup + validate_email + accept_eula = at least 3 entries
        assert len(log) >= 3

    def test_audit_log_entries_have_required_fields(self, gw, onboarded_profile):
        log = gw.get_audit_log()
        for entry in log:
            assert "action" in entry
            assert "user_id" in entry
            assert "timestamp" in entry
