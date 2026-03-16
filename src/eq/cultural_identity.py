"""
Cultural Identity — Race Cultural Identity Templates

Implements the race cultural identity templates described in §6 and the
RACE_CULTURAL_IDENTITY_DESIGN.md of the Experimental EverQuest
Modification Plan.

Provides:
  - Cultural value enums for personality-bias calculations.
  - Per-race templates with primary/secondary values, languages, cities,
    allied/enemy races, and personality biases.
  - A manager to query templates and apply cultural bias to soul documents.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CulturalValue(Enum):
    """Cultural values that shape racial personality biases (§6)."""

    HONOR = "honor"
    CUNNING = "cunning"
    KNOWLEDGE = "knowledge"
    NATURE = "nature"
    COMMERCE = "commerce"
    STRENGTH = "strength"
    DEVOTION = "devotion"
    SHADOW = "shadow"
    COMMUNITY = "community"
    CRAFTSMANSHIP = "craftsmanship"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RaceCulturalTemplate:
    """Cultural identity template for a single race."""

    race_name: str
    primary_values: List[CulturalValue] = field(default_factory=list)
    secondary_values: List[CulturalValue] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    starting_city: str = ""
    allied_races: List[str] = field(default_factory=list)
    enemy_races: List[str] = field(default_factory=list)
    personality_bias: str = ""


# ---------------------------------------------------------------------------
# Race Templates
# ---------------------------------------------------------------------------

RACE_TEMPLATES: Dict[str, RaceCulturalTemplate] = {
    "human": RaceCulturalTemplate(
        race_name="human",
        primary_values=[CulturalValue.COMMERCE, CulturalValue.COMMUNITY],
        secondary_values=[CulturalValue.HONOR, CulturalValue.KNOWLEDGE],
        languages=["common"],
        starting_city="freeport",
        allied_races=["half_elf", "erudite"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Balanced and adaptable; driven by trade and community bonds.",
    ),
    "high_elf": RaceCulturalTemplate(
        race_name="high_elf",
        primary_values=[CulturalValue.KNOWLEDGE, CulturalValue.DEVOTION],
        secondary_values=[CulturalValue.HONOR, CulturalValue.NATURE],
        languages=["common", "elvish"],
        starting_city="felwithe",
        allied_races=["wood_elf", "half_elf", "dwarf"],
        enemy_races=["dark_elf", "orc", "troll", "ogre"],
        personality_bias="Scholarly and devout; values arcane tradition and purity.",
    ),
    "dark_elf": RaceCulturalTemplate(
        race_name="dark_elf",
        primary_values=[CulturalValue.CUNNING, CulturalValue.SHADOW],
        secondary_values=[CulturalValue.KNOWLEDGE, CulturalValue.COMMERCE],
        languages=["common", "dark_elvish", "thieves_cant"],
        starting_city="neriak",
        allied_races=["troll", "ogre"],
        enemy_races=["high_elf", "wood_elf", "dwarf", "halfling"],
        personality_bias="Scheming and ambitious; thrives on manipulation and secrecy.",
    ),
    "wood_elf": RaceCulturalTemplate(
        race_name="wood_elf",
        primary_values=[CulturalValue.NATURE, CulturalValue.COMMUNITY],
        secondary_values=[CulturalValue.HONOR, CulturalValue.CRAFTSMANSHIP],
        languages=["common", "elvish"],
        starting_city="kelethin",
        allied_races=["high_elf", "half_elf", "halfling"],
        enemy_races=["dark_elf", "orc", "troll"],
        personality_bias="Gentle and nature-loving; protective of forests and kin.",
    ),
    "half_elf": RaceCulturalTemplate(
        race_name="half_elf",
        primary_values=[CulturalValue.COMMUNITY, CulturalValue.NATURE],
        secondary_values=[CulturalValue.COMMERCE, CulturalValue.HONOR],
        languages=["common", "elvish"],
        starting_city="freeport",
        allied_races=["human", "wood_elf", "high_elf"],
        enemy_races=["dark_elf", "orc"],
        personality_bias="Diplomatic and versatile; bridges human and elven worlds.",
    ),
    "dwarf": RaceCulturalTemplate(
        race_name="dwarf",
        primary_values=[CulturalValue.CRAFTSMANSHIP, CulturalValue.HONOR],
        secondary_values=[CulturalValue.STRENGTH, CulturalValue.COMMUNITY],
        languages=["common", "dwarvish"],
        starting_city="kaladim",
        allied_races=["gnome", "high_elf", "halfling"],
        enemy_races=["dark_elf", "troll", "ogre", "orc"],
        personality_bias="Stout and proud; values craftsmanship, loyalty, and ale.",
    ),
    "gnome": RaceCulturalTemplate(
        race_name="gnome",
        primary_values=[CulturalValue.KNOWLEDGE, CulturalValue.CRAFTSMANSHIP],
        secondary_values=[CulturalValue.CUNNING, CulturalValue.COMMUNITY],
        languages=["common", "gnomish"],
        starting_city="ak_anon",
        allied_races=["dwarf", "high_elf"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Inventive and curious; obsessed with tinkering and discovery.",
    ),
    "halfling": RaceCulturalTemplate(
        race_name="halfling",
        primary_values=[CulturalValue.COMMUNITY, CulturalValue.NATURE],
        secondary_values=[CulturalValue.CUNNING, CulturalValue.COMMERCE],
        languages=["common", "halfling"],
        starting_city="rivervale",
        allied_races=["wood_elf", "dwarf", "high_elf"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Cheerful and communal; loves good food and mischief.",
    ),
    "erudite": RaceCulturalTemplate(
        race_name="erudite",
        primary_values=[CulturalValue.KNOWLEDGE, CulturalValue.DEVOTION],
        secondary_values=[CulturalValue.COMMERCE, CulturalValue.HONOR],
        languages=["common", "erudian"],
        starting_city="erudin",
        allied_races=["human", "high_elf"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Intellectual and aloof; pursues arcane mastery above all.",
    ),
    "barbarian": RaceCulturalTemplate(
        race_name="barbarian",
        primary_values=[CulturalValue.STRENGTH, CulturalValue.HONOR],
        secondary_values=[CulturalValue.COMMUNITY, CulturalValue.NATURE],
        languages=["common", "barbarian"],
        starting_city="halas",
        allied_races=["human", "dwarf"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Fierce and loyal; values strength in battle and tribal bonds.",
    ),
    "troll": RaceCulturalTemplate(
        race_name="troll",
        primary_values=[CulturalValue.STRENGTH, CulturalValue.CUNNING],
        secondary_values=[CulturalValue.SHADOW, CulturalValue.COMMUNITY],
        languages=["common", "troll"],
        starting_city="grobb",
        allied_races=["ogre", "dark_elf", "orc"],
        enemy_races=["high_elf", "wood_elf", "dwarf", "halfling"],
        personality_bias="Brutal and cunning; survives through raw power and instinct.",
    ),
    "ogre": RaceCulturalTemplate(
        race_name="ogre",
        primary_values=[CulturalValue.STRENGTH, CulturalValue.SHADOW],
        secondary_values=[CulturalValue.CUNNING, CulturalValue.COMMUNITY],
        languages=["common", "ogre"],
        starting_city="oggok",
        allied_races=["troll", "dark_elf", "orc"],
        enemy_races=["high_elf", "wood_elf", "dwarf", "halfling"],
        personality_bias="Imposing and slow-witted; dominates through sheer force.",
    ),
    "iksar": RaceCulturalTemplate(
        race_name="iksar",
        primary_values=[CulturalValue.CUNNING, CulturalValue.DEVOTION],
        secondary_values=[CulturalValue.STRENGTH, CulturalValue.KNOWLEDGE],
        languages=["common", "iksar"],
        starting_city="cabilis",
        allied_races=[],
        enemy_races=["human", "high_elf", "dwarf", "barbarian"],
        personality_bias="Cold and calculating; devoted to the Shissar legacy.",
    ),
    "vah_shir": RaceCulturalTemplate(
        race_name="vah_shir",
        primary_values=[CulturalValue.HONOR, CulturalValue.NATURE],
        secondary_values=[CulturalValue.STRENGTH, CulturalValue.COMMUNITY],
        languages=["common", "vah_shir"],
        starting_city="shar_vahl",
        allied_races=["human"],
        enemy_races=["dark_elf", "troll", "ogre"],
        personality_bias="Noble and tribal; guided by instinct and ancestral honor.",
    ),
    "orc": RaceCulturalTemplate(
        race_name="orc",
        primary_values=[CulturalValue.STRENGTH, CulturalValue.COMMERCE],
        secondary_values=[CulturalValue.CUNNING, CulturalValue.COMMUNITY],
        languages=["common", "orcish"],
        starting_city="crushbone",
        allied_races=["troll", "ogre"],
        enemy_races=["high_elf", "wood_elf", "dwarf"],
        personality_bias="Aggressive yet mercantile; merchant city homeland breeds cunning traders.",
    ),
}


# ---------------------------------------------------------------------------
# Cultural Identity Manager
# ---------------------------------------------------------------------------

class CulturalIdentityManager:
    """Manages race cultural identity templates and personality biases.

    §6: Each race carries cultural values that influence NPC behaviour,
    faction standings, and soul-document personality traits.
    """

    def __init__(self, templates: Optional[Dict[str, RaceCulturalTemplate]] = None) -> None:
        self._templates = templates if templates is not None else dict(RACE_TEMPLATES)

    # --- Template queries ---

    def get_template(self, race: str) -> Optional[RaceCulturalTemplate]:
        """Return the cultural template for a race, or None if unknown."""
        return self._templates.get(race.lower())

    def get_personality_bias(self, race: str) -> str:
        """Return the personality bias string for a race."""
        template = self.get_template(race)
        return template.personality_bias if template else ""

    def get_allied_races(self, race: str) -> List[str]:
        """Return the list of allied races."""
        template = self.get_template(race)
        return list(template.allied_races) if template else []

    def get_enemy_races(self, race: str) -> List[str]:
        """Return the list of enemy races."""
        template = self.get_template(race)
        return list(template.enemy_races) if template else []

    # --- Cultural bias application ---

    def apply_cultural_bias(
        self,
        soul_document_traits: List[str],
        race: str,
    ) -> List[str]:
        """Add race-appropriate traits to a soul document's trait list.

        Returns a new list with cultural value names appended.
        """
        template = self.get_template(race)
        if template is None:
            return list(soul_document_traits)

        cultural_traits = [v.value for v in template.primary_values + template.secondary_values]
        combined = list(soul_document_traits)
        for trait in cultural_traits:
            if trait not in combined:
                combined.append(trait)
        return combined

    # --- Properties ---

    @property
    def supported_races(self) -> List[str]:
        """Return the list of races with registered templates."""
        return list(self._templates.keys())

    @property
    def template_count(self) -> int:
        """Return the number of registered templates."""
        return len(self._templates)
