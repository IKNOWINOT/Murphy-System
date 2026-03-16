"""
Tests for EnvironmentStateManager — state persistence, validation,
invalidation, user profile / shadow agent / terminal config helpers.

Design Label: TEST-ENV-STATE-001
Owner: QA Team
"""
import os
import sys
import tempfile
import pytest


from environment_state_manager import (
    EnvironmentState,
    EnvironmentStateManager,
    StateError,
    _STATE_VERSION,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_mgr(tmp_path):
    """A manager backed by a temporary directory."""
    return EnvironmentStateManager(home_dir=str(tmp_path / "murphy_test"))


@pytest.fixture
def basic_state():
    import sys
    return EnvironmentState(
        user_id="testuser123",
        org_id="org456",
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        venv_path="",       # no venv path → skip venv check
        api_port=8000,
    )


# ---------------------------------------------------------------------------
# EnvironmentState model
# ---------------------------------------------------------------------------


class TestEnvironmentState:
    def test_defaults(self):
        state = EnvironmentState()
        assert state.state_version == _STATE_VERSION
        assert state.valid is True
        assert state.api_port == 8000

    def test_to_dict_and_from_dict_roundtrip(self):
        state = EnvironmentState(
            user_id="u1",
            org_id="o1",
            python_version="3.11.0",
            playwright_installed=True,
            env_vars={"KEY": "val"},
        )
        d = state.to_dict()
        restored = EnvironmentState.from_dict(d)
        assert restored.user_id == state.user_id
        assert restored.org_id == state.org_id
        assert restored.playwright_installed == state.playwright_installed
        assert restored.env_vars == state.env_vars

    def test_from_dict_ignores_unknown_keys(self):
        state = EnvironmentState.from_dict({"unknown_field": "ignored", "user_id": "u99"})
        assert state.user_id == "u99"


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_save_and_load_roundtrip(self, tmp_mgr, basic_state):
        tmp_mgr.save_state(basic_state)
        loaded = tmp_mgr.load_state()
        assert loaded is not None
        assert loaded.user_id == basic_state.user_id
        assert loaded.org_id == basic_state.org_id

    def test_load_returns_none_when_no_file(self, tmp_mgr):
        assert tmp_mgr.load_state() is None

    def test_save_creates_home_directory(self, tmp_path):
        new_home = str(tmp_path / "does_not_exist_yet" / "murphy")
        mgr = EnvironmentStateManager(home_dir=new_home)
        state = EnvironmentState(user_id="x")
        mgr.save_state(state)
        assert os.path.isdir(new_home)

    def test_home_dir_accessor(self, tmp_mgr, tmp_path):
        assert "murphy_test" in tmp_mgr.home_dir()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_validate_state_true_when_valid(self, tmp_mgr, basic_state):
        tmp_mgr.save_state(basic_state)
        assert tmp_mgr.validate_state() is True

    def test_validate_state_false_when_no_file(self, tmp_mgr):
        assert tmp_mgr.validate_state() is False

    def test_validate_state_false_when_valid_false(self, tmp_mgr, basic_state):
        basic_state.valid = False
        tmp_mgr.save_state(basic_state)
        assert tmp_mgr.validate_state() is False

    def test_validate_state_false_when_venv_missing(self, tmp_mgr):
        import sys
        state = EnvironmentState(
            user_id="u1",
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            venv_path="/path/that/does/not/exist/venv",
        )
        tmp_mgr.save_state(state)
        assert tmp_mgr.validate_state() is False


# ---------------------------------------------------------------------------
# Invalidation
# ---------------------------------------------------------------------------


class TestInvalidation:
    def test_invalidate_marks_state_invalid(self, tmp_mgr, basic_state):
        tmp_mgr.save_state(basic_state)
        tmp_mgr.invalidate_state("OS upgraded")
        loaded = tmp_mgr.load_state()
        assert loaded is not None
        assert loaded.valid is False
        assert loaded.invalidated_reason == "OS upgraded"

    def test_invalidate_no_op_when_no_state(self, tmp_mgr):
        tmp_mgr.invalidate_state("nothing")   # should not raise


# ---------------------------------------------------------------------------
# User profile helpers
# ---------------------------------------------------------------------------


class TestUserProfileHelpers:
    def test_save_and_load_user_profile(self, tmp_mgr):
        profile = {"user_id": "u1", "name": "Alice", "role": "founder_admin"}
        tmp_mgr.save_user_profile(profile)
        loaded = tmp_mgr.load_user_profile()
        assert loaded is not None
        assert loaded["user_id"] == "u1"
        assert loaded["name"] == "Alice"

    def test_load_user_profile_none_when_missing(self, tmp_mgr):
        assert tmp_mgr.load_user_profile() is None


# ---------------------------------------------------------------------------
# Shadow agent helpers
# ---------------------------------------------------------------------------


class TestShadowAgentHelpers:
    def test_save_and_load_shadow_agent(self, tmp_mgr):
        config = {"agent_id": "sa1", "department": "engineering", "status": "active"}
        tmp_mgr.save_shadow_agent(config)
        loaded = tmp_mgr.load_shadow_agent()
        assert loaded is not None
        assert loaded["agent_id"] == "sa1"

    def test_load_shadow_agent_none_when_missing(self, tmp_mgr):
        assert tmp_mgr.load_shadow_agent() is None


# ---------------------------------------------------------------------------
# Terminal config helpers
# ---------------------------------------------------------------------------


class TestTerminalConfigHelpers:
    def test_save_and_load_terminal_config(self, tmp_mgr):
        config = {"role": "worker", "features": {"worker_terminal": True}}
        tmp_mgr.save_terminal_config(config)
        loaded = tmp_mgr.load_terminal_config()
        assert loaded is not None
        assert loaded["role"] == "worker"

    def test_load_terminal_config_none_when_missing(self, tmp_mgr):
        assert tmp_mgr.load_terminal_config() is None


# ---------------------------------------------------------------------------
# Audit log helpers
# ---------------------------------------------------------------------------


class TestAuditLogHelpers:
    def test_append_and_load_audit_entries(self, tmp_mgr):
        entry1 = {"action": "step_approved", "step_id": "s001", "timestamp": "2026-01-01T00:00:00Z"}
        entry2 = {"action": "step_executed", "step_id": "s001", "timestamp": "2026-01-01T00:01:00Z"}
        tmp_mgr.append_audit_entry(entry1)
        tmp_mgr.append_audit_entry(entry2)
        log = tmp_mgr.load_audit_log()
        assert len(log) == 2
        assert log[0]["action"] == "step_approved"

    def test_load_audit_log_empty_when_missing(self, tmp_mgr):
        assert tmp_mgr.load_audit_log() == []


# ---------------------------------------------------------------------------
# .env file helpers
# ---------------------------------------------------------------------------


class TestEnvFileHelpers:
    def test_save_and_load_env_vars(self, tmp_mgr):
        env_vars = {"GROQ_API_KEY": "gsk_test123", "MURPHY_HOME": "/home/user/.murphy"}
        tmp_mgr.save_env_vars(env_vars)
        loaded = tmp_mgr.load_env_vars()
        assert loaded["GROQ_API_KEY"] == "gsk_test123"
        assert loaded["MURPHY_HOME"] == "/home/user/.murphy"

    def test_load_env_vars_empty_when_no_file(self, tmp_mgr):
        assert tmp_mgr.load_env_vars() == {}

    def test_env_file_written_correctly(self, tmp_mgr):
        env_vars = {"KEY1": "value1", "KEY2": "value2"}
        tmp_mgr.save_env_vars(env_vars)
        env_path = os.path.join(tmp_mgr.home_dir(), ".env")
        with open(env_path) as f:
            content = f.read()
        assert "KEY1=value1" in content
        assert "KEY2=value2" in content
