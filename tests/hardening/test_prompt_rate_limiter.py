# Copyright 2020 Inoni LLC — BSL 1.1
"""
Tests for src/prompt_rate_limiter.py — label PROMPT-RATE-001.

Covers the conditions enumerated in the module's commissioning docstring:
allow path, deny path, cross-tenant isolation, swarm tier independence,
config validation, status snapshot, monotonic refill.
"""
from __future__ import annotations

import time

import pytest

from src.prompt_rate_limiter import PromptRateLimiter, RateLimitDecision


def _make(rpm=60, burst=3, swarm_rpm=120, swarm_burst=5):
    return PromptRateLimiter(human_rpm=rpm, human_burst=burst,
                             swarm_rpm=swarm_rpm, swarm_burst=swarm_burst)


def test_allows_up_to_burst_then_denies():
    rl = _make(burst=3)
    decisions = [rl.check("tenant-a") for _ in range(3)]
    assert all(d.allowed for d in decisions), decisions
    blocked = rl.check("tenant-a")
    assert blocked.allowed is False
    assert blocked.error == "MURPHY-E202"
    assert blocked.retry_after_seconds > 0
    assert blocked.tenant_id == "tenant-a"
    assert blocked.traffic_class == "human"


def test_cross_tenant_isolation():
    rl = _make(burst=2)
    # tenant-a exhausts its bucket
    assert rl.check("tenant-a").allowed
    assert rl.check("tenant-a").allowed
    assert rl.check("tenant-a").allowed is False
    # tenant-b is untouched
    assert rl.check("tenant-b").allowed
    assert rl.check("tenant-b").allowed


def test_swarm_class_uses_separate_larger_bucket():
    rl = _make(burst=2, swarm_burst=4)
    # human bucket exhausted at 2
    assert rl.check("tenant-a", "human").allowed
    assert rl.check("tenant-a", "human").allowed
    assert rl.check("tenant-a", "human").allowed is False
    # swarm bucket for the same tenant is independent — and bigger
    swarm_decisions = [rl.check("tenant-a", "swarm") for _ in range(4)]
    assert all(d.allowed for d in swarm_decisions)
    assert swarm_decisions[-1].traffic_class == "swarm"
    # 5th swarm call denied
    assert rl.check("tenant-a", "swarm").allowed is False


def test_unknown_class_collapses_to_human_no_privilege_escalation():
    rl = _make(burst=1, swarm_burst=10)
    # Unknown class should be treated as human, not silently upgraded.
    d = rl.check("tenant-a", "elite")
    assert d.allowed and d.traffic_class == "human"
    assert rl.check("tenant-a", "elite").allowed is False


def test_blank_tenant_falls_back_to_anon_bucket():
    rl = _make(burst=1)
    d = rl.check("", "human")
    assert d.allowed and d.tenant_id == "anon"
    assert rl.check(None, "human").allowed is False  # anon bucket exhausted


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        PromptRateLimiter(human_rpm=0)
    with pytest.raises(ValueError):
        PromptRateLimiter(human_burst=-1)


def test_refill_over_time_restores_capacity():
    # 600 rpm = 10 tokens / second; burst 1 → after 0.2s we have ~1 token back.
    rl = _make(rpm=600, burst=1)
    assert rl.check("tenant-a").allowed
    assert rl.check("tenant-a").allowed is False
    time.sleep(0.25)
    assert rl.check("tenant-a").allowed


def test_status_reports_active_buckets_and_limits():
    rl = _make(burst=2, swarm_burst=3)
    rl.check("tenant-a", "human")
    rl.check("tenant-b", "human")
    rl.check("tenant-a", "swarm")
    snap = rl.status()
    assert snap["label"] == "PROMPT-RATE-001"
    assert snap["active_buckets"] == 3
    assert snap["buckets_by_class"] == {"human": 2, "swarm": 1}
    assert snap["limits"]["human"]["burst"] == 2
    assert snap["limits"]["swarm"]["burst"] == 3


def test_decision_is_immutable_dataclass():
    rl = _make(burst=1)
    d = rl.check("tenant-a")
    assert isinstance(d, RateLimitDecision)
    with pytest.raises(Exception):  # frozen=True
        d.allowed = False  # type: ignore[misc]
