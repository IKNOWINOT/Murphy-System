"""
Test configuration for Murphy System.

sys.path is configured via pyproject.toml [tool.pytest.ini_options] pythonpath,
which adds the project root ("."), "src/", and "strategic/" to sys.path.

Preferred import style in tests:
    from src.xxx import yyy          # always works (src package)
    from confidence_engine import yyy  # works when src/ is in path

Do NOT add ``sys.path`` hacks in test files — the pyproject.toml
pythonpath setting handles it automatically for pytest runs.  For
editable-install / runtime use, ``pip install -e .`` covers it.
"""

import asyncio
import os
import sys


# ---------------------------------------------------------------------------
# Event loop — ensure every test thread has a usable asyncio event loop
# so that tests calling asyncio.get_event_loop().run_until_complete(...)
# work on Python 3.10+ (which no longer auto-creates a loop for
# non-async contexts).
# ---------------------------------------------------------------------------

def pytest_runtest_setup(item):
    """Create a new event loop for each test that lacks one."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


# ---------------------------------------------------------------------------
# Communication Hub — clean slate between tests
# ---------------------------------------------------------------------------

import pytest


@pytest.fixture(autouse=True)
def _comms_hub_clean_db(request):
    """
    Before each test in test_communication_hub.py, truncate all comms hub
    tables so tests are fully independent of one another even though they
    share the same SQLite file.
    """
    if "test_communication_hub" not in request.fspath.basename:
        yield
        return

    # Truncate before the test
    _truncate_comms_tables()
    yield
    # No teardown needed — next test will truncate again


def _truncate_comms_tables():
    """Delete all rows from every comms hub table (if the DB is available)."""
    try:
        from src.db import (
            _get_session_factory,
            IMThread, IMMessage,
            CallSession, EmailRecord,
            CommsAutomationRule, CommsModAuditLog,
            CommsBroadcast, CommsUserProfile,
        )
        session = _get_session_factory()()
        try:
            for model in (
                IMMessage, IMThread,
                CallSession, EmailRecord,
                CommsAutomationRule, CommsModAuditLog,
                CommsBroadcast, CommsUserProfile,
            ):
                session.query(model).delete()
            session.commit()
        finally:
            session.close()
    except Exception:
        pass  # DB not available — tests will use in-memory fallback


# ---------------------------------------------------------------------------
# CI Guard — auto-skip tests that require a live local server or network
# when MURPHY_ENV=test (set by all CI workflows).
# Tests are skipped at collection time so the suite completes instantly
# instead of hanging for 3 seconds per test waiting for a refused connection.
# ---------------------------------------------------------------------------
import re as _re

_NETWORK_PATTERNS = _re.compile(
    r'localhost:[0-9]+|127\.0\.0\.1:[0-9]+|httpx\.(?:get|post|put|delete|patch)\s*\('
    r'''|requests\.(?:get|post|put|delete|patch)\s*\(['"]http'''
)

def pytest_collection_modifyitems(config, items):
    """Skip live-server tests in CI (MURPHY_ENV=test)."""
    if os.environ.get("MURPHY_ENV") != "test":
        return
    import ast as _ast
    skip_mark = pytest.mark.skip(reason="Skipped in CI: requires live server (MURPHY_ENV=test)")
    for item in items:
        try:
            src = item.fspath.read_text("utf-8")
            if _NETWORK_PATTERNS.search(src):
                item.add_marker(skip_mark)
        except Exception:
            pass
