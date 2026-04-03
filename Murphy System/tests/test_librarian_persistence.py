"""
Tests for ARCH-003: LibrarianIntegration persistence wiring.

Validates that the LibrarianIntegration can save and restore state
via PersistenceManager, surviving simulated restarts.

Design Label: TEST-002 / ARCH-003
Owner: QA Team
"""

import sys
import os
import pytest


from librarian_integration import LibrarianIntegration
from persistence_manager import PersistenceManager


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def pm(tmp_path):
    return PersistenceManager(persistence_dir=str(tmp_path / "test_persist"))


@pytest.fixture
def lib(pm):
    return LibrarianIntegration(persistence_manager=pm)


# ------------------------------------------------------------------
# Backward compatibility: no persistence_manager
# ------------------------------------------------------------------

class TestNoPersistence:
    def test_integration_works_without_persistence(self):
        lib = LibrarianIntegration()
        lib.initialize()
        assert lib.initialized is True

    def test_save_state_returns_false_without_pm(self):
        lib = LibrarianIntegration()
        assert lib.save_state() is False

    def test_load_state_returns_false_without_pm(self):
        lib = LibrarianIntegration()
        assert lib.load_state() is False

    def test_set_state_works_without_pm(self):
        lib = LibrarianIntegration()
        state_id = lib.set_state("key1", "value1")
        assert state_id is not None
        assert lib.get_state("key1") == "value1"

    def test_initialize_creates_default_configurations_without_pm(self):
        lib = LibrarianIntegration()
        lib.initialize()
        configs = lib.get_all_configurations()
        assert len(configs) > 0


# ------------------------------------------------------------------
# Persistence round-trip
# ------------------------------------------------------------------

class TestPersistenceRoundTrip:
    def test_save_and_load_states(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.set_state("color", "blue")
        lib1.set_state("count", 42)
        assert lib1.save_state() is True

        lib2 = LibrarianIntegration(persistence_manager=pm)
        assert lib2.get_state("color") is None
        assert lib2.load_state() is True
        assert lib2.get_state("color") == "blue"
        assert lib2.get_state("count") == 42

    def test_save_and_load_configurations(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.initialize()
        configs_before = lib1.get_all_configurations()
        assert lib1.save_state() is True

        lib2 = LibrarianIntegration(persistence_manager=pm)
        lib2.load_state()
        configs_after = lib2.get_all_configurations()
        assert len(configs_after) == len(configs_before)

    def test_load_state_returns_false_when_empty(self, pm):
        lib = LibrarianIntegration(persistence_manager=pm)
        assert lib.load_state() is False

    def test_initialize_restores_state_before_defaults(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.set_state("persisted_key", "persisted_value")
        lib1.save_state()

        lib2 = LibrarianIntegration(persistence_manager=pm)
        lib2.initialize()
        assert lib2.get_state("persisted_key") == "persisted_value"

    def test_initialize_creates_defaults_when_no_persisted_state(self, pm):
        lib = LibrarianIntegration(persistence_manager=pm)
        lib.initialize()
        configs = lib.get_all_configurations()
        assert len(configs) > 0

    def test_initialize_does_not_duplicate_defaults_on_restore(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.initialize()
        count1 = len(lib1.get_all_configurations())
        lib1.save_state()

        lib2 = LibrarianIntegration(persistence_manager=pm)
        lib2.initialize()
        count2 = len(lib2.get_all_configurations())
        assert count2 == count1


# ------------------------------------------------------------------
# Auto-save behavior
# ------------------------------------------------------------------

class TestAutoSave:
    def test_set_state_auto_saves_when_auto_save_true(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        assert lib1.state_manager.auto_save is True
        lib1.set_state("auto_key", "auto_value")

        # A new instance should be able to load the auto-saved state
        lib2 = LibrarianIntegration(persistence_manager=pm)
        assert lib2.load_state() is True
        assert lib2.get_state("auto_key") == "auto_value"

    def test_set_state_no_auto_save_when_disabled(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.state_manager.auto_save = False
        lib1.set_state("no_auto_key", "no_auto_value")

        lib2 = LibrarianIntegration(persistence_manager=pm)
        assert lib2.load_state() is False

    def test_update_setup_auto_saves(self, pm):
        lib1 = LibrarianIntegration(persistence_manager=pm)
        lib1.initialize()
        # Activate the system config first so update_setup can find it
        for cfg in lib1.get_all_configurations():
            if cfg.config_category == "system":
                lib1.setup_manager.activate_configuration(cfg.config_id)
                break
        lib1.update_setup("system", {"log_level": "debug"})

        lib2 = LibrarianIntegration(persistence_manager=pm)
        assert lib2.load_state() is True
        system_setup = lib2.get_setup("system")
        assert system_setup is not None
        assert system_setup["log_level"] == "debug"

    def test_auto_save_suppresses_persistence_errors(self):
        """Persistence failures must not break in-memory operations."""

        class BrokenPM:
            def save_document(self, *a, **kw):
                raise RuntimeError("disk full")

            def load_document(self, *a, **kw):
                return None

        lib = LibrarianIntegration(persistence_manager=BrokenPM())
        # Should not raise; in-memory operation must succeed
        state_id = lib.set_state("safe_key", "safe_value")
        assert state_id is not None
        assert lib.get_state("safe_key") == "safe_value"


# ------------------------------------------------------------------
# Graceful degradation
# ------------------------------------------------------------------

class TestGracefulDegradation:
    def test_load_state_suppresses_load_errors(self):
        class ErrorPM:
            def load_document(self, *a, **kw):
                raise OSError("read error")

            def save_document(self, *a, **kw):
                pass

        lib = LibrarianIntegration(persistence_manager=ErrorPM())
        assert lib.load_state() is False

    def test_save_state_suppresses_save_errors(self):
        class ErrorPM:
            def load_document(self, *a, **kw):
                return None

            def save_document(self, *a, **kw):
                raise OSError("write error")

        lib = LibrarianIntegration(persistence_manager=ErrorPM())
        lib.set_state("x", 1)
        assert lib.save_state() is False
