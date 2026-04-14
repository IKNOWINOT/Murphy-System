# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_llm_governor — LLM workload governance."""

from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-llm-governor"))

from murphy_llm_governor import (
    GPUStats,
    LLMGovernor,
    UsageRecord,
    LatencyRecord,
    _TokenBucket,
    get_governor,
)


# ── helpers ───────────────────────────────────────────────────────────────
def _make_governor(**overrides) -> LLMGovernor:
    """Create a governor with persistence disabled."""
    cfg = {
        "state_file": "/dev/null",
        "budgets": {
            "daily_total_usd": 50.0,
            "hourly_total_usd": 10.0,
            "per_provider": {
                "openai": {"daily_usd": 20.0, "rpm": 60, "tpm": 100000},
                "anthropic": {"daily_usd": 15.0, "rpm": 30, "tpm": 50000},
            },
        },
        "gpu": {"oom_threshold_percent": 90, "temperature_limit_celsius": 85},
        "health": {
            "error_rate_threshold": 0.05,
            "latency_p99_threshold_ms": 30000,
            "window_seconds": 300,
        },
    }
    cfg.update(overrides)
    with mock.patch.object(pathlib.Path, "exists", return_value=False):
        return LLMGovernor(config=cfg)


# ── initialisation ────────────────────────────────────────────────────────
class TestLLMGovernorInit:
    def test_init_default_config(self):
        with mock.patch.object(pathlib.Path, "exists", return_value=False):
            gov = LLMGovernor()
        assert gov is not None

    def test_init_custom_config(self):
        gov = _make_governor()
        assert gov._daily_total_cap == 50.0


# ── record_usage / get_usage ─────────────────────────────────────────────
class TestUsageTracking:
    def test_record_usage_tracks_tokens(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 100, 200, 0.05)
        usage = gov.get_usage("openai", "day")
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 200
        assert usage["total_tokens"] == 300
        assert usage["request_count"] == 1

    def test_get_usage_returns_correct_stats(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 50, 100, 0.01)
            gov.record_usage("openai", "gpt-4", 75, 150, 0.02)
        usage = gov.get_usage("openai", "day")
        assert usage["prompt_tokens"] == 125
        assert usage["completion_tokens"] == 250
        assert usage["cost_usd"] == 0.03
        assert usage["request_count"] == 2

    def test_get_usage_filters_by_provider(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 100, 200, 0.05)
            gov.record_usage("anthropic", "claude-3", 50, 100, 0.02)
        usage = gov.get_usage("anthropic", "day")
        assert usage["prompt_tokens"] == 50
        assert usage["request_count"] == 1


# ── check_budget ──────────────────────────────────────────────────────────
class TestCheckBudget:
    def test_check_budget_within_limit(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 100, 200, 1.0)
        assert gov.check_budget("openai") is True

    def test_check_budget_over_limit(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 10000, 20000, 25.0)
        assert gov.check_budget("openai") is False


# ── rate limiting ─────────────────────────────────────────────────────────
class TestRateLimiting:
    def test_acquire_succeeds_within_limit(self):
        gov = _make_governor()
        assert gov.acquire("openai", estimated_tokens=10) is True

    def test_acquire_fails_when_exhausted(self):
        gov = _make_governor()
        # Exhaust RPM bucket
        for _ in range(65):
            gov.acquire("openai", estimated_tokens=1)
        assert gov.acquire("openai", estimated_tokens=1) is False

    def test_acquire_no_limiter_always_succeeds(self):
        gov = _make_governor()
        assert gov.acquire("unknown-provider", estimated_tokens=999) is True

    def test_get_rate_status_returns_dict(self):
        gov = _make_governor()
        status = gov.get_rate_status("openai")
        assert "provider" in status
        assert "rpm_available" in status
        assert "tpm_available" in status


# ── GPU stats ─────────────────────────────────────────────────────────────
class TestGPUStats:
    @mock.patch("subprocess.run")
    def test_get_gpu_stats_parses_nvidia_smi(self, mock_run):
        mock_run.return_value = mock.MagicMock(
            returncode=0,
            stdout="4096, 8192, 75.0, 65.0\n",
            stderr="",
        )
        gov = _make_governor()
        stats = gov.get_gpu_stats()
        assert stats is not None
        assert stats.memory_used_mb == 4096.0
        assert stats.memory_total_mb == 8192.0
        assert stats.utilization_percent == 75.0
        assert stats.temperature_celsius == 65.0

    @mock.patch("subprocess.run", side_effect=FileNotFoundError)
    def test_get_gpu_stats_none_when_no_nvidia(self, _mock_run):
        gov = _make_governor()
        with mock.patch.object(type(gov), "_try_sysfs_gpu", return_value=None):
            stats = gov.get_gpu_stats()
        assert stats is None

    def test_check_gpu_available_no_gpu(self):
        gov = _make_governor()
        with mock.patch.object(gov, "get_gpu_stats", return_value=None):
            assert gov.check_gpu_available(1024.0) is True

    def test_check_gpu_available_over_oom_threshold(self):
        gov = _make_governor()
        stats = GPUStats(
            memory_used_mb=7500, memory_total_mb=8192,
            utilization_percent=90, temperature_celsius=70,
        )
        with mock.patch.object(gov, "get_gpu_stats", return_value=stats):
            assert gov.check_gpu_available(1024.0) is False

    def test_check_gpu_available_over_temp_limit(self):
        gov = _make_governor()
        stats = GPUStats(
            memory_used_mb=2000, memory_total_mb=8192,
            utilization_percent=50, temperature_celsius=90,
        )
        with mock.patch.object(gov, "get_gpu_stats", return_value=stats):
            assert gov.check_gpu_available(1024.0) is False


# ── provider health ───────────────────────────────────────────────────────
class TestProviderHealth:
    def test_record_latency_and_get_health(self):
        gov = _make_governor()
        for i in range(20):
            gov.record_latency("openai", latency_ms=100.0 + i, success=True)
        health = gov.get_provider_health("openai")
        assert health["request_count"] == 20
        assert health["error_rate"] == 0.0
        assert health["latency_p50_ms"] > 0
        assert health["latency_p95_ms"] > 0
        assert health["latency_p99_ms"] > 0
        assert health["healthy"] is True

    def test_get_provider_health_empty(self):
        gov = _make_governor()
        health = gov.get_provider_health("new-provider")
        assert health["request_count"] == 0
        assert health["healthy"] is True

    def test_unhealthy_with_high_error_rate(self):
        gov = _make_governor()
        for _ in range(10):
            gov.record_latency("openai", latency_ms=50.0, success=False)
        health = gov.get_provider_health("openai")
        assert health["error_rate"] == 1.0
        assert health["healthy"] is False


# ── circuit breaker ───────────────────────────────────────────────────────
class TestCircuitBreaker:
    def test_is_circuit_open_default_closed(self):
        gov = _make_governor()
        assert gov.is_circuit_open("openai") is False

    def test_circuit_opens_on_budget_exceed(self):
        gov = _make_governor()
        with mock.patch.object(gov, "_persist_state"):
            gov.record_usage("openai", "gpt-4", 100000, 200000, 25.0)
        assert gov.is_circuit_open("openai") is True


# ── state persistence ─────────────────────────────────────────────────────
class TestStatePersistence:
    def test_persist_and_load_state(self, tmp_path):
        state_file = tmp_path / "governor_state.json"
        gov = LLMGovernor(config={"state_file": str(state_file)})
        gov.record_usage("openai", "gpt-4", 100, 200, 0.05)
        assert state_file.exists()

        gov2 = LLMGovernor(config={"state_file": str(state_file)})
        usage = gov2.get_usage("openai", "day")
        assert usage["request_count"] == 1


# ── thread safety ─────────────────────────────────────────────────────────
class TestThreadSafety:
    def test_concurrent_record_usage(self):
        gov = _make_governor()
        errors = []

        def _record():
            try:
                with mock.patch.object(gov, "_persist_state"):
                    gov.record_usage("openai", "gpt-4", 10, 20, 0.001)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_record) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        usage = gov.get_usage("openai", "day")
        assert usage["request_count"] == 20


# ── token bucket ──────────────────────────────────────────────────────────
class TestTokenBucket:
    def test_acquire_success(self):
        bucket = _TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.acquire(1) is True
        assert bucket.available() < 10

    def test_acquire_fails_when_empty(self):
        bucket = _TokenBucket(capacity=2, refill_rate=0.0)
        assert bucket.acquire(2) is True
        assert bucket.acquire(1) is False

    def test_reset_time(self):
        bucket = _TokenBucket(capacity=10, refill_rate=5.0)
        bucket.acquire(10)
        assert bucket.reset_time() > 0
