"""
Murphy System — Commissioning Test Fixtures
Owner: @test-lead
Phase: 2 — Commissioning Test Infrastructure
Completion: 100%

Provides shared fixtures for all commissioning tests. Follows existing
conftest.py pattern (sys.path management) and adds commissioning-specific
fixtures for state validation, log validation, and test sandboxing.
"""

import os
import sys
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

# ── Path setup (matches existing tests/conftest.py pattern) ──────────────
SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Commissioning session metadata ───────────────────────────────────────

@pytest.fixture(scope="session")
def commissioning_session():
    """Session-level metadata for the commissioning test run."""
    return {
        "session_id": f"COMM-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "started_at": datetime.now().isoformat(),
        "system_version": "1.0.0",
        "test_plan": "MURPHY_COMMISSIONING_IMPLEMENTATION_PLAN.md",
        "phases_executed": [],
    }


# ── Temporary sandbox for tests that write data ─────────────────────────

@pytest.fixture
def sandbox(tmp_path):
    """Provides an isolated temporary directory for test data.

    Automatically cleaned up after each test. Use this for any test that
    writes files, creates state, or modifies training data.
    """
    sandbox_dir = tmp_path / "murphy_sandbox"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    yield sandbox_dir
    # Cleanup is automatic via tmp_path


@pytest.fixture
def persistence_sandbox(sandbox):
    """Simulates the .murphy_persistence directory structure."""
    state_dir = sandbox / ".murphy_persistence"
    state_dir.mkdir(parents=True, exist_ok=True)

    audit_dir = state_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    training_dir = state_dir / "training_data"
    training_dir.mkdir(parents=True, exist_ok=True)

    # Create initial state file
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps({
        "system_version": "1.0.0",
        "components": {},
        "automations": {},
        "last_updated": datetime.now().isoformat(),
    }, indent=2))

    # Create initial audit log
    audit_log = audit_dir / "audit.log"
    audit_log.write_text("")

    return state_dir


# ── Source directory reference ───────────────────────────────────────────

@pytest.fixture(scope="session")
def src_dir():
    """Returns the path to the active source directory."""
    return SRC_DIR


@pytest.fixture(scope="session")
def project_root():
    """Returns the project root directory."""
    return PROJECT_ROOT
