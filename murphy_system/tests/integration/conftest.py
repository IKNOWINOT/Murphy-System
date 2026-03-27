"""
pytest conftest for integration tests.

Adds the local mocks/ directory to sys.path so that mock modules
(e.g. enterprise_systems) can be imported directly in test files.
The mocks directory contains test-only fixtures that are not part of
any installable package, so sys.path manipulation is appropriate here.
"""

import sys
from pathlib import Path

# Add the mocks directory for this test suite to sys.path.
_mocks_dir = str(Path(__file__).parent / "mocks")
if _mocks_dir not in sys.path:
    sys.path.insert(0, _mocks_dir)
