"""
pytest conftest for the Murphy System external benchmark test suite.

Provides shared fixtures and configuration for benchmark tests.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Custom markers
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "benchmark_external: marks tests as external AI-agent benchmark evaluations",
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def benchmark_output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Temporary directory for benchmark JSON output during the test run."""
    return tmp_path_factory.mktemp("benchmark_results")


@pytest.fixture(scope="session")
def external_benchmarks_enabled() -> bool:
    """Return True when the external benchmark env-var gate is set."""
    return bool(os.environ.get("MURPHY_RUN_EXTERNAL_BENCHMARKS"))


@pytest.fixture(scope="session")
def benchmark_max_tasks() -> int:
    """Maximum tasks per benchmark suite (override via MURPHY_BENCHMARK_MAX_TASKS)."""
    raw = os.environ.get("MURPHY_BENCHMARK_MAX_TASKS", "5")
    try:
        return int(raw)
    except ValueError:
        return 5
