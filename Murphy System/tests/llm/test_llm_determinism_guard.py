# Copyright 2020 Inoni LLC — BSL 1.1
# Creator: Corey Post
"""
Module: tests/llm/test_llm_determinism_guard.py
Subsystem: LLM Inference Determinism Guard
Label: TEST-DETERM-GUARD — Commission tests for LLMDeterminismGuard

Commissioning Answers (G1–G9)
-----------------------------
1. G1 — Purpose: Does this do what it was designed to do?
   YES — validates request fingerprinting, response caching (hit/miss/TTL),
   deterministic parameter enforcement, output normalisation, drift detection,
   audit trail, thread safety, and singleton management.

2. G2 — Spec: What is it supposed to do?
   LLMDeterminismGuard defeats nondeterminism in API-consumed LLM inference
   by fingerprinting requests, caching responses, enforcing deterministic
   parameters (temp=0, seed), detecting output drift, normalising outputs,
   and maintaining a reproducibility audit trail.

3. G3 — Conditions: What conditions are possible?
   - Cache hit → return cached response
   - Cache miss → record new response, cache it
   - Cache TTL expired → evict and return None
   - Cache full → LRU eviction
   - Deterministic mode ON → temp=0.0, seed=42
   - Deterministic mode OFF → params unchanged
   - Same fingerprint, different output → drift event
   - Same fingerprint, same output → no drift
   - Output normalisation → trailing whitespace stripped
   - Thread contention → concurrent access safe
   - Singleton lifecycle → create / reset

4. G4 — Test Profile: Does test profile reflect full range?
   YES — 28 tests covering all conditions in G3.

5. G5 — Expected vs Actual: All tests pass.
6. G6 — Regression Loop: Run: pytest 'Murphy System/tests/llm/test_llm_determinism_guard.py' -v
7. G7 — As-Builts: YES — docstring, inline labels.
8. G8 — Hardening: Bounds validation, thread-safety, CWE-770 checks.
9. G9 — Re-commissioned: YES.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List

import pytest

from src.llm_determinism_guard import (
    DEFAULT_CACHE_TTL_S,
    DETERMINISTIC_SEED,
    MAX_CACHE_ENTRIES,
    AuditEntry,
    CachedResponse,
    DriftEvent,
    LLMDeterminismGuard,
    RequestFingerprint,
    fingerprint_request,
    get_determinism_guard,
    hash_content,
    normalise_output,
    reset_determinism_guard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the module-level singleton before and after each test."""
    reset_determinism_guard(None)
    yield
    reset_determinism_guard(None)


@pytest.fixture
def guard():
    """Fresh guard with short TTL for fast testing."""
    return LLMDeterminismGuard(cache_ttl_s=10.0, max_cache=64, max_audit=256)


@pytest.fixture
def sample_messages() -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ]


# ---------------------------------------------------------------------------
# Output Normalisation  (label: TEST-DETERM-NORM)
# ---------------------------------------------------------------------------

class TestNormaliseOutput:
    """COMMISSION: G4 — Determinism Guard / output normalisation."""

    def test_strips_trailing_whitespace(self):
        text = "Hello   \nWorld   "
        assert normalise_output(text) == "Hello\nWorld"

    def test_collapses_triple_newlines(self):
        text = "A\n\n\n\nB"
        assert normalise_output(text) == "A\n\nB"

    def test_strips_leading_trailing(self):
        text = "  \n  Hello  \n  "
        assert normalise_output(text) == "Hello"

    def test_preserves_single_newlines(self):
        text = "A\nB\nC"
        assert normalise_output(text) == "A\nB\nC"

    def test_preserves_double_newlines(self):
        text = "A\n\nB"
        assert normalise_output(text) == "A\n\nB"

    def test_empty_string(self):
        assert normalise_output("") == ""

    def test_idempotent(self):
        text = "Hello\n\nWorld"
        first = normalise_output(text)
        second = normalise_output(first)
        assert first == second


# ---------------------------------------------------------------------------
# Request Fingerprinting  (label: TEST-DETERM-FP)
# ---------------------------------------------------------------------------

class TestFingerprinting:
    """COMMISSION: G4 — Determinism Guard / request fingerprinting."""

    def test_same_input_same_digest(self, sample_messages):
        fp1 = fingerprint_request(sample_messages, "model-a", 0.7, 1024)
        fp2 = fingerprint_request(sample_messages, "model-a", 0.7, 1024)
        assert fp1.digest == fp2.digest

    def test_different_model_different_digest(self, sample_messages):
        fp1 = fingerprint_request(sample_messages, "model-a", 0.7, 1024)
        fp2 = fingerprint_request(sample_messages, "model-b", 0.7, 1024)
        assert fp1.digest != fp2.digest

    def test_different_temperature_different_digest(self, sample_messages):
        fp1 = fingerprint_request(sample_messages, "model-a", 0.0, 1024)
        fp2 = fingerprint_request(sample_messages, "model-a", 0.7, 1024)
        assert fp1.digest != fp2.digest

    def test_different_messages_different_digest(self):
        msgs1 = [{"role": "user", "content": "Hello"}]
        msgs2 = [{"role": "user", "content": "World"}]
        fp1 = fingerprint_request(msgs1, "m", 0.0, 100)
        fp2 = fingerprint_request(msgs2, "m", 0.0, 100)
        assert fp1.digest != fp2.digest

    def test_seed_changes_digest(self, sample_messages):
        fp1 = fingerprint_request(sample_messages, "m", 0.0, 100, seed=42)
        fp2 = fingerprint_request(sample_messages, "m", 0.0, 100, seed=None)
        assert fp1.digest != fp2.digest

    def test_deterministic_flag_changes_digest(self, sample_messages):
        fp1 = fingerprint_request(sample_messages, "m", 0.0, 100, deterministic=True)
        fp2 = fingerprint_request(sample_messages, "m", 0.0, 100, deterministic=False)
        assert fp1.digest != fp2.digest

    def test_digest_is_hex_sha256(self, sample_messages):
        fp = fingerprint_request(sample_messages, "m", 0.0, 100)
        assert len(fp.digest) == 64
        assert all(c in "0123456789abcdef" for c in fp.digest)

    def test_hash_content_deterministic(self):
        h1 = hash_content("Hello World")
        h2 = hash_content("Hello World")
        assert h1 == h2

    def test_hash_content_normalises(self):
        h1 = hash_content("Hello   \n\n\nWorld   ")
        h2 = hash_content("Hello\n\nWorld")
        assert h1 == h2


# ---------------------------------------------------------------------------
# Deterministic Parameter Enforcement  (label: TEST-DETERM-ENFORCE)
# ---------------------------------------------------------------------------

class TestParameterEnforcement:
    """COMMISSION: G4 — Determinism Guard / parameter enforcement."""

    def test_deterministic_forces_temp_zero(self, guard):
        params = guard.enforce_deterministic_params(
            temperature=0.7, seed=None, deterministic=True,
        )
        assert params["temperature"] == 0.0

    def test_deterministic_sets_seed(self, guard):
        params = guard.enforce_deterministic_params(
            temperature=0.7, seed=None, deterministic=True,
        )
        assert params["seed"] == DETERMINISTIC_SEED

    def test_deterministic_preserves_explicit_seed(self, guard):
        params = guard.enforce_deterministic_params(
            temperature=0.7, seed=999, deterministic=True,
        )
        assert params["seed"] == 999

    def test_non_deterministic_preserves_params(self, guard):
        params = guard.enforce_deterministic_params(
            temperature=0.7, seed=None, deterministic=False,
        )
        assert params["temperature"] == 0.7
        assert params["seed"] is None


# ---------------------------------------------------------------------------
# Cache Operations  (label: TEST-DETERM-CACHE)
# ---------------------------------------------------------------------------

class TestCacheOperations:
    """COMMISSION: G4 — Determinism Guard / cache hit/miss/TTL/eviction."""

    def test_cache_miss_returns_none(self, guard, sample_messages):
        result = guard.get_cached(sample_messages, "model", 0.0, 1024)
        assert result is None

    def test_record_then_cache_hit(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="model", temperature=0.0,
            max_tokens=1024, seed=42, deterministic=True,
            content="The answer is 4.", provider="deepinfra", latency_s=1.0,
        )
        cached = guard.get_cached(
            sample_messages, "model", 0.0, 1024, seed=42, deterministic=True,
        )
        assert cached is not None
        assert "answer is 4" in cached.content
        assert cached.provider == "deepinfra"

    def test_cache_hit_increments_count(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="X", provider="di", latency_s=0.5,
        )
        guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True)
        cached = guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True)
        assert cached is not None
        assert cached.hit_count == 2

    def test_cache_ttl_expiry(self, sample_messages):
        guard = LLMDeterminismGuard(cache_ttl_s=0.05)
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Cached!", provider="di", latency_s=0.1,
        )
        # Should be cached
        assert guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True) is not None
        # Wait for TTL
        time.sleep(0.1)
        # Should be expired
        assert guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True) is None

    def test_cache_lru_eviction(self, sample_messages):
        guard = LLMDeterminismGuard(max_cache=2)
        for i in range(3):
            msgs = [{"role": "user", "content": f"msg-{i}"}]
            guard.record_response(
                messages=msgs, model="m", temperature=0.0,
                max_tokens=100, seed=42, deterministic=True,
                content=f"resp-{i}", provider="di", latency_s=0.1,
            )
        # First entry should be evicted
        first = guard.get_cached(
            [{"role": "user", "content": "msg-0"}], "m", 0.0, 100, seed=42, deterministic=True,
        )
        assert first is None
        # Last entry should still be cached
        last = guard.get_cached(
            [{"role": "user", "content": "msg-2"}], "m", 0.0, 100, seed=42, deterministic=True,
        )
        assert last is not None

    def test_clear_cache(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="X", provider="di", latency_s=0.1,
        )
        count = guard.clear_cache()
        assert count == 1
        assert guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True) is None


# ---------------------------------------------------------------------------
# Drift Detection  (label: TEST-DETERM-DRIFT)
# ---------------------------------------------------------------------------

class TestDriftDetection:
    """COMMISSION: G4 — Determinism Guard / output drift detection."""

    def test_no_drift_on_first_call(self, guard, sample_messages):
        entry = guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Answer A", provider="di", latency_s=0.5,
        )
        assert entry.drift_detected is False

    def test_no_drift_same_output(self, guard, sample_messages):
        for _ in range(3):
            entry = guard.record_response(
                messages=sample_messages, model="m", temperature=0.0,
                max_tokens=100, seed=42, deterministic=True,
                content="Answer A", provider="di", latency_s=0.5,
            )
        assert entry.drift_detected is False
        assert guard.get_stats()["drift_events"] == 0

    def test_drift_on_different_output(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Answer A", provider="di", latency_s=0.5,
        )
        entry = guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Answer B", provider="di", latency_s=0.5,
        )
        assert entry.drift_detected is True
        assert guard.get_stats()["drift_events"] == 1

    def test_drift_events_retrievable(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="V1", provider="di", latency_s=0.1,
        )
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="V2", provider="di", latency_s=0.1,
        )
        events = guard.get_drift_events()
        assert len(events) == 1
        assert events[0]["provider"] == "di"

    def test_normalised_comparison_avoids_false_drift(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Hello World  \n\n\n",
            provider="di", latency_s=0.1,
        )
        entry = guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Hello World",
            provider="di", latency_s=0.1,
        )
        assert entry.drift_detected is False


# ---------------------------------------------------------------------------
# Audit Trail  (label: TEST-DETERM-AUDIT)
# ---------------------------------------------------------------------------

class TestAuditTrail:
    """COMMISSION: G4 — Determinism Guard / audit trail."""

    def test_audit_entry_created(self, guard, sample_messages):
        entry = guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="Test", provider="di", latency_s=0.5,
        )
        assert isinstance(entry, AuditEntry)
        assert entry.provider == "di"
        assert entry.deterministic is True
        assert entry.cache_hit is False

    def test_audit_trail_grows(self, guard, sample_messages):
        for i in range(5):
            guard.record_response(
                messages=sample_messages, model="m", temperature=0.0,
                max_tokens=100, seed=42, deterministic=True,
                content=f"Resp {i}", provider="di", latency_s=0.1,
            )
        trail = guard.get_audit_trail()
        assert len(trail) == 5

    def test_audit_trail_bounded(self, sample_messages):
        guard = LLMDeterminismGuard(max_audit=10)
        for i in range(20):
            guard.record_response(
                messages=[{"role": "user", "content": f"q-{i}"}],
                model="m", temperature=0.0, max_tokens=100,
                seed=42, deterministic=True,
                content=f"a-{i}", provider="di", latency_s=0.1,
            )
        assert guard.get_stats()["audit_trail_size"] <= 15  # Halved + new entries


# ---------------------------------------------------------------------------
# Statistics  (label: TEST-DETERM-STATS)
# ---------------------------------------------------------------------------

class TestStatistics:
    """COMMISSION: G4 — Determinism Guard / statistics."""

    def test_initial_stats(self, guard):
        stats = guard.get_stats()
        assert stats["cache_hits"] == 0
        assert stats["cache_misses"] == 0
        assert stats["total_calls"] == 0
        assert stats["deterministic_calls"] == 0

    def test_stats_after_calls(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="X", provider="di", latency_s=0.1,
        )
        guard.get_cached(sample_messages, "m", 0.0, 100, seed=42, deterministic=True)
        stats = guard.get_stats()
        assert stats["total_calls"] == 1
        assert stats["deterministic_calls"] == 1
        assert stats["cache_misses"] == 1
        assert stats["cache_hits"] == 1


# ---------------------------------------------------------------------------
# Constructor Validation  (label: TEST-DETERM-HARDENING)
# ---------------------------------------------------------------------------

class TestHardening:
    """COMMISSION: G4 — Determinism Guard / hardening."""

    def test_negative_ttl_raises(self):
        with pytest.raises(ValueError, match="cache_ttl_s"):
            LLMDeterminismGuard(cache_ttl_s=-1.0)

    def test_negative_max_cache_raises(self):
        with pytest.raises(ValueError, match="max_cache"):
            LLMDeterminismGuard(max_cache=-1)

    def test_negative_max_audit_raises(self):
        with pytest.raises(ValueError, match="max_audit"):
            LLMDeterminismGuard(max_audit=-1)

    def test_zero_ttl_allowed(self):
        g = LLMDeterminismGuard(cache_ttl_s=0.0)
        assert g._cache_ttl_s == 0.0


# ---------------------------------------------------------------------------
# Singleton  (label: TEST-DETERM-SINGLETON)
# ---------------------------------------------------------------------------

class TestSingleton:
    """COMMISSION: G4 — Determinism Guard / singleton lifecycle."""

    def test_get_returns_same_instance(self):
        g1 = get_determinism_guard()
        g2 = get_determinism_guard()
        assert g1 is g2

    def test_reset_clears_singleton(self):
        g1 = get_determinism_guard()
        reset_determinism_guard(None)
        g2 = get_determinism_guard()
        assert g1 is not g2

    def test_reset_with_custom(self):
        custom = LLMDeterminismGuard(cache_ttl_s=999.0)
        reset_determinism_guard(custom)
        assert get_determinism_guard() is custom


# ---------------------------------------------------------------------------
# Full Reset  (label: TEST-DETERM-RESET)
# ---------------------------------------------------------------------------

class TestReset:
    """COMMISSION: G4 — Determinism Guard / full reset."""

    def test_reset_clears_everything(self, guard, sample_messages):
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="X", provider="di", latency_s=0.1,
        )
        guard.reset()
        stats = guard.get_stats()
        assert stats["cache_size"] == 0
        assert stats["total_calls"] == 0
        assert stats["drift_tracker_size"] == 0
        assert stats["audit_trail_size"] == 0


# ---------------------------------------------------------------------------
# Thread Safety  (label: TEST-DETERM-THREADSAFE)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """COMMISSION: G4 — Determinism Guard / concurrent access."""

    def test_concurrent_writes(self, guard):
        errors: List[Exception] = []

        def writer(thread_id: int):
            try:
                for i in range(50):
                    guard.record_response(
                        messages=[{"role": "user", "content": f"t{thread_id}-{i}"}],
                        model="m", temperature=0.0, max_tokens=100,
                        seed=42, deterministic=True,
                        content=f"resp-{thread_id}-{i}",
                        provider="di", latency_s=0.01,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = guard.get_stats()
        assert stats["total_calls"] == 200  # 4 threads × 50 calls

    def test_concurrent_reads_and_writes(self, guard, sample_messages):
        errors: List[Exception] = []

        # Pre-populate cache
        guard.record_response(
            messages=sample_messages, model="m", temperature=0.0,
            max_tokens=100, seed=42, deterministic=True,
            content="cached-value", provider="di", latency_s=0.1,
        )

        def reader():
            try:
                for _ in range(50):
                    guard.get_cached(
                        sample_messages, "m", 0.0, 100, seed=42, deterministic=True,
                    )
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    guard.record_response(
                        messages=[{"role": "user", "content": f"w-{i}"}],
                        model="m", temperature=0.0, max_tokens=100,
                        seed=42, deterministic=True,
                        content=f"resp-{i}", provider="di", latency_s=0.01,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
