"""
Reconciliation feature flags.

Phase rollout is controlled by environment variables so the subsystem
can be enabled progressively without code changes:

* ``MURPHY_RECON_ENABLED``         — master switch (default: ``1``)
* ``MURPHY_RECON_OBSERVE_ONLY``    — score but never patch (default: ``1``)
* ``MURPHY_RECON_PATCH_PROMPTS``   — allow prompt/config patches (default: ``0``)
* ``MURPHY_RECON_PATCH_CODE``      — allow code-diff patches via PR (default: ``0``)
* ``MURPHY_RECON_AUTO_RETRAIN``    — feed outcomes into retraining (default: ``0``)
* ``MURPHY_RECON_LLM_JUDGE``       — enable LLM-as-judge calls (default: ``0``)

Boolean parsing is permissive: ``1``, ``true``, ``yes``, ``on`` (any
case) all map to True.

Design label: RECON-FLAGS-001
"""

from __future__ import annotations

import os
from dataclasses import dataclass


_TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class FeatureFlags:
    """Snapshot of the reconciliation flags at construction time."""

    enabled: bool
    observe_only: bool
    patch_prompts: bool
    patch_code: bool
    auto_retrain: bool
    llm_judge: bool

    @classmethod
    def from_env(cls) -> "FeatureFlags":
        """Read every flag from the environment with safe defaults."""
        return cls(
            enabled=_flag("MURPHY_RECON_ENABLED", True),
            observe_only=_flag("MURPHY_RECON_OBSERVE_ONLY", True),
            patch_prompts=_flag("MURPHY_RECON_PATCH_PROMPTS", False),
            patch_code=_flag("MURPHY_RECON_PATCH_CODE", False),
            auto_retrain=_flag("MURPHY_RECON_AUTO_RETRAIN", False),
            llm_judge=_flag("MURPHY_RECON_LLM_JUDGE", False),
        )

    @property
    def any_patching_allowed(self) -> bool:
        """True when at least one patch class is enabled and observe-only is off."""
        if self.observe_only:
            return False
        return self.patch_prompts or self.patch_code


def current_flags() -> FeatureFlags:
    """Convenience accessor for the live env snapshot."""
    return FeatureFlags.from_env()


__all__ = ["FeatureFlags", "current_flags"]
