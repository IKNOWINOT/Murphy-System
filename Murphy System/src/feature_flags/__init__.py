"""
Feature Flags — runtime feature gating with per-tenant control.

Design Label: FF-001
Module ID:    src.feature_flags

Implements runtime feature flags that:
  • Gate new modules behind flags per tenant
  • Enable A/B testing of new implementations against shadow agents
  • Align with revenue-gated roadmap (features unlock as MRR milestones hit)

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides a thread-safe feature flag manager with per-tenant overrides,
   percentage rollouts, MRR-gated features, and A/B testing support.

Q: What conditions are possible?
A: Create / update / evaluate / delete flags.  Per-tenant overrides.
   Percentage-based rollout.  MRR threshold gating.  Bounded collections.

Q: Has hardening been applied?
A: Thread-safe, bounded flag count, deterministic hashing for percentage
   rollout, Pydantic validation, no bare except.
"""

from __future__ import annotations

from src.feature_flags.models import (
    FeatureFlag,
    FlagEvaluation,
    FlagStatus,
    FlagType,
    RolloutConfig,
    TenantOverride,
)
from src.feature_flags.flag_manager import FeatureFlagManager

__all__ = [
    "FeatureFlag",
    "FeatureFlagManager",
    "FlagEvaluation",
    "FlagStatus",
    "FlagType",
    "RolloutConfig",
    "TenantOverride",
]
