"""
Monetization Rules — Fair Monetization Enforcement

Enforces the no-pay-to-win principle across all MMORPG games produced by
the Game Creation Pipeline. All gameplay power must be earned through
cooperation and progression; only cosmetic items may be sold.

Provides:
  - Cosmetic-only item classification
  - Pay-to-win detection and rejection
  - Revenue model templates
  - Player fairness scoring
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ItemCategory(Enum):
    """Top-level item classification."""

    COSMETIC = "cosmetic"               # allowed for sale
    CONVENIENCE = "convenience"         # allowed (QoL, no power)
    GAMEPLAY_POWER = "gameplay_power"   # BLOCKED — pay-to-win
    CURRENCY = "currency"               # context-dependent
    PROGRESSION_BOOST = "progression_boost"  # BLOCKED — pay-to-win
    LOOT_ENHANCER = "loot_enhancer"     # BLOCKED — pay-to-win


class MonetizationVerdict(Enum):
    """Verdict from the pay-to-win detector."""

    APPROVED = "approved"
    REJECTED_PAY_TO_WIN = "rejected_pay_to_win"
    FLAGGED_FOR_REVIEW = "flagged_for_review"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ItemDefinition:
    """Description of a purchasable or craftable in-game item."""

    item_id: str
    name: str
    category: ItemCategory

    # Stat deltas — positive values increase power
    stat_bonuses: Dict[str, float] = field(default_factory=dict)

    # Whether the item can be acquired through normal gameplay
    obtainable_in_game: bool = True

    # XP/progression multipliers (>1.0 = booster)
    xp_multiplier: float = 1.0
    drop_rate_multiplier: float = 1.0

    # Cosmetic properties
    visual_only: bool = False
    description: str = ""


@dataclass
class MonetizationRuling:
    """Record of a monetization check for audit purposes."""

    ruling_id: str
    item_id: str
    item_name: str
    verdict: MonetizationVerdict
    reasons: List[str]
    timestamp: float = field(default_factory=time.time)
    reviewer: str = "MonetizationEngine"


@dataclass
class RevenueModel:
    """Template for a fair revenue model."""

    model_id: str
    name: str
    allowed_categories: List[ItemCategory]
    description: str
    examples: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in Revenue Models
# ---------------------------------------------------------------------------

COSMETIC_ONLY_MODEL = RevenueModel(
    model_id="cosmetic_only",
    name="Cosmetic Only",
    allowed_categories=[ItemCategory.COSMETIC],
    description=(
        "Only visual items (skins, mounts, pets, emotes) may be purchased. "
        "Zero gameplay advantage. Recommended default."
    ),
    examples=["Character skins", "Mount skins", "Emote packs", "Housing cosmetics"],
)

COSMETIC_AND_CONVENIENCE_MODEL = RevenueModel(
    model_id="cosmetic_and_convenience",
    name="Cosmetic + Convenience",
    allowed_categories=[ItemCategory.COSMETIC, ItemCategory.CONVENIENCE],
    description=(
        "Cosmetics plus quality-of-life items (extra bag slots, shared storage, "
        "name change tokens). No stat bonuses or power gains."
    ),
    examples=[
        "Character skins", "Extra bank slots", "Name change tokens",
        "Additional character slots",
    ],
)

ALL_REVENUE_MODELS = {
    COSMETIC_ONLY_MODEL.model_id: COSMETIC_ONLY_MODEL,
    COSMETIC_AND_CONVENIENCE_MODEL.model_id: COSMETIC_AND_CONVENIENCE_MODEL,
}


# ---------------------------------------------------------------------------
# Pay-to-Win Detection Rules
# ---------------------------------------------------------------------------

def _detect_pay_to_win_reasons(item: ItemDefinition) -> List[str]:
    """Return a list of reasons why an item is pay-to-win (empty = clean)."""
    reasons: List[str] = []

    if item.category == ItemCategory.GAMEPLAY_POWER:
        reasons.append(
            f"Category '{item.category.value}' grants direct gameplay power advantage."
        )

    if item.category == ItemCategory.PROGRESSION_BOOST:
        reasons.append(
            "Category 'progression_boost' accelerates character power through payment."
        )

    if item.category == ItemCategory.LOOT_ENHANCER:
        reasons.append(
            "Category 'loot_enhancer' increases drop rates through payment."
        )

    if item.xp_multiplier > 1.0:
        reasons.append(
            f"XP multiplier {item.xp_multiplier:.2f}x provides paid progression advantage."
        )

    if item.drop_rate_multiplier > 1.0:
        reasons.append(
            f"Drop rate multiplier {item.drop_rate_multiplier:.2f}x provides paid loot advantage."
        )

    for stat, bonus in item.stat_bonuses.items():
        if bonus > 0 and not item.obtainable_in_game:
            reasons.append(
                f"Stat '{stat}' +{bonus} is only available via purchase (not earnable in-game)."
            )

    return reasons


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class MonetizationRulesEngine:
    """
    Enforces fair monetization across all pipeline-generated games.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_RULINGS = 10_000

    def __init__(self, revenue_model_id: str = "cosmetic_only") -> None:
        self._lock = threading.Lock()
        self._model_id = revenue_model_id
        self._rulings: List[MonetizationRuling] = []
        self._rejected_count = 0
        self._approved_count = 0

    @property
    def revenue_model(self) -> RevenueModel:
        """Active revenue model."""
        return ALL_REVENUE_MODELS.get(self._model_id, COSMETIC_ONLY_MODEL)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify_item(self, item: ItemDefinition) -> Tuple[MonetizationVerdict, List[str]]:
        """
        Classify an item under the active revenue model.

        Returns (verdict, reasons).
        """
        p2w_reasons = _detect_pay_to_win_reasons(item)
        if p2w_reasons:
            return MonetizationVerdict.REJECTED_PAY_TO_WIN, p2w_reasons

        if item.category not in self.revenue_model.allowed_categories:
            reason = (
                f"Category '{item.category.value}' is not allowed by revenue model "
                f"'{self.revenue_model.name}'."
            )
            return MonetizationVerdict.FLAGGED_FOR_REVIEW, [reason]

        return MonetizationVerdict.APPROVED, []

    def evaluate(self, item: ItemDefinition) -> MonetizationRuling:
        """
        Evaluate and record a monetization ruling for an item.

        Raises ``ValueError`` if the item is rejected.
        """
        verdict, reasons = self.classify_item(item)

        ruling = MonetizationRuling(
            ruling_id=str(uuid.uuid4()),
            item_id=item.item_id,
            item_name=item.name,
            verdict=verdict,
            reasons=reasons,
        )

        with self._lock:
            capped_append(self._rulings, ruling, self._MAX_RULINGS)
            if verdict == MonetizationVerdict.APPROVED:
                self._approved_count += 1
            else:
                self._rejected_count += 1

        if verdict == MonetizationVerdict.REJECTED_PAY_TO_WIN:
            logger.warning(
                "Pay-to-win item REJECTED: %s — %s", item.name, "; ".join(reasons)
            )
            raise ValueError(
                f"Item '{item.name}' rejected as pay-to-win: {'; '.join(reasons)}"
            )

        if verdict == MonetizationVerdict.FLAGGED_FOR_REVIEW:
            logger.info("Item flagged for review: %s — %s", item.name, "; ".join(reasons))

        return ruling

    # ------------------------------------------------------------------
    # Fairness scoring
    # ------------------------------------------------------------------

    def fairness_score(self) -> float:
        """
        Return a player fairness score (0.0–1.0) based on ruling history.

        1.0 = all items approved cleanly, 0.0 = everything rejected.
        """
        with self._lock:
            total = self._approved_count + self._rejected_count
            if total == 0:
                return 1.0
            return self._approved_count / total

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def get_rulings(
        self,
        verdict_filter: Optional[MonetizationVerdict] = None,
    ) -> List[MonetizationRuling]:
        """Return recorded rulings, optionally filtered by verdict."""
        with self._lock:
            rulings = list(self._rulings)
        if verdict_filter is not None:
            rulings = [r for r in rulings if r.verdict == verdict_filter]
        return rulings
