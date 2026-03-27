"""
Schemas for the Shim Compiler — BotManifest, CompileResult, ShimDrift.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BotManifest:
    """
    Manifest describing a bot's configuration for shim generation.

    Default values match the canonical implementations in bots/bot_base/internal/.
    Override any field to customise the generated shims for a specific bot.
    """

    bot_name: str
    archetype: str = "kiren"          # 'kiren', 'veritas', 'vallon'
    authority_level: str = "low"      # from org chart

    # Stability shim parameters
    cost_ref_usd: float = 0.01        # reference cost for S(t) normalisation
    latency_ref_s: float = 1.5        # reference latency for S(t) normalisation
    s_min: float = 0.45               # minimum stability score before fallback/downgrade

    # Budget shim parameters
    founder_cap_cents: int = 45000    # monthly free-pool cap (45000 = $450)

    # Golden-paths shim parameters
    gp_confidence_threshold: float = 0.8   # pass-rate gate for low-confidence clamping
    gp_maturity_runs: int = 20              # run count for high-confidence promotion

    # KaiaMix composition (used for documentation / routing metadata)
    kaia_mix: Dict[str, float] = field(
        default_factory=lambda: {"kiren": 0.4, "veritas": 0.4, "vallon": 0.2}
    )


@dataclass
class ShimDrift:
    """
    Records a drift between the shim that would be generated from a manifest
    and the shim that currently exists on disk.
    """

    template_name: str        # e.g. 'shim_budget.ts.tmpl'
    output_filename: str      # e.g. 'shim_budget.ts'
    expected_path: str        # path of the generated (expected) content
    actual_path: str          # path of the existing file on disk
    diff_lines: List[str]     # unified-diff lines


@dataclass
class CompileResult:
    """
    Result of a compile_shims() call for a single bot.
    """

    bot_name: str
    output_dir: str
    written: List[str] = field(default_factory=list)    # paths of files written
    skipped: List[str] = field(default_factory=list)    # paths skipped (no change)
    errors: List[str] = field(default_factory=list)     # error messages

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def files_changed(self) -> int:
        return len(self.written)
