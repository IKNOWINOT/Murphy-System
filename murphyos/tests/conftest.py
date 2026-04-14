"""Shared fixtures and PYTHONPATH setup for MurphyOS tests."""

import os
import sys
import logging
import pathlib

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH — make every MurphyOS package importable without installing
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
_PATHS = [
    str(_MURPHYOS / "security" / "auto-hardening"),
    str(_MURPHYOS / "security" / "quantum" / "userspace"),
    str(_MURPHYOS / "security" / "quantum" / "boot"),
    str(_MURPHYOS / "userspace" / "murphyfs"),
    str(_MURPHYOS / "userspace" / "murphy-cli"),
    str(_MURPHYOS / "userspace" / "murphy-dbus"),
    str(_MURPHYOS / "userspace" / "murphy-resolved"),
    str(_MURPHYOS / "userspace" / "murphy-cgroup"),
    str(_MURPHYOS / "userspace" / "murphy-journal"),
    str(_MURPHYOS / "userspace" / "murphy-backup"),
    str(_MURPHYOS / "userspace" / "murphy-llm-governor"),
    str(_MURPHYOS / "userspace" / "murphy-telemetry-export"),
    str(_MURPHYOS / "userspace" / "murphy-module-lifecycle"),
]
for p in _PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def tmp_dir(tmp_path: pathlib.Path):
    """Return a ready-to-use temporary directory (pytest-managed)."""
    return tmp_path


@pytest.fixture()
def mock_logger():
    """Return a quiet logger that captures records for assertions."""
    logger = logging.getLogger("murphy-test")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return logger


@pytest.fixture()
def mock_config():
    """Return a baseline MurphyOS configuration dictionary."""
    return {
        "api_url": "http://127.0.0.1:4242",
        "cache_ttl": 2.0,
        "block_duration": 3600,
        "patch_url": "https://updates.murphyos.local/patches/latest.json",
        "vault_dir": "/var/lib/murphy/vault",
        "baseline_dir": "/var/lib/murphy/integrity",
        "quarantine_dir": "/var/lib/murphy/quarantine",
    }
