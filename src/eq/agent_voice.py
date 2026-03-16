"""
Agent Voice — Text-to-Speech Voice Profiles for Streaming Agents

Implements the agent voice system described in §10.2 and §11.3 of the
Experimental EverQuest Modification Plan.

Provides:
  - Race/class-specific TTS voice profiles
  - Voice roster with 8+ distinct profiles
  - Integration point for streaming agent voice output
  - Voice profile assignment based on agent soul document attributes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Voice Profile
# ---------------------------------------------------------------------------

class VoiceGender(Enum):
    """Voice gender (Enum subclass)."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class VoiceTone(Enum):
    """Voice tone (Enum subclass)."""
    DEEP = "deep"
    GRAVELLY = "gravelly"
    SMOOTH = "smooth"
    HIGH = "high"
    RASPY = "raspy"
    COMMANDING = "commanding"
    GENTLE = "gentle"
    ETHEREAL = "ethereal"


@dataclass
class VoiceProfile:
    """A TTS voice profile assigned to streaming agents."""

    profile_id: str
    name: str
    gender: VoiceGender
    tone: VoiceTone
    pitch_modifier: float = 1.0  # 0.5 = lower, 1.5 = higher
    speed_modifier: float = 1.0  # 0.8 = slower, 1.2 = faster
    description: str = ""
    suitable_races: List[str] = field(default_factory=list)
    suitable_classes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default Voice Roster (8+ profiles)
# ---------------------------------------------------------------------------

DEFAULT_VOICE_ROSTER: List[VoiceProfile] = [
    VoiceProfile(
        profile_id="orc_warrior",
        name="Gronthar",
        gender=VoiceGender.MALE,
        tone=VoiceTone.GRAVELLY,
        pitch_modifier=0.7,
        speed_modifier=0.9,
        description="Deep, gravelly orc warrior voice",
        suitable_races=["orc", "ogre", "troll"],
        suitable_classes=["warrior", "berserker", "shadowknight"],
    ),
    VoiceProfile(
        profile_id="elf_caster",
        name="Aelindra",
        gender=VoiceGender.FEMALE,
        tone=VoiceTone.ETHEREAL,
        pitch_modifier=1.2,
        speed_modifier=1.0,
        description="Ethereal elven spellcaster voice",
        suitable_races=["high_elf", "wood_elf", "half_elf"],
        suitable_classes=["wizard", "enchanter", "magician", "druid"],
    ),
    VoiceProfile(
        profile_id="dwarf_tank",
        name="Thorik",
        gender=VoiceGender.MALE,
        tone=VoiceTone.DEEP,
        pitch_modifier=0.8,
        speed_modifier=0.85,
        description="Booming dwarven warrior voice",
        suitable_races=["dwarf"],
        suitable_classes=["warrior", "paladin", "cleric"],
    ),
    VoiceProfile(
        profile_id="dark_elf_rogue",
        name="Xal'thar",
        gender=VoiceGender.MALE,
        tone=VoiceTone.SMOOTH,
        pitch_modifier=1.0,
        speed_modifier=1.1,
        description="Silky dark elf rogue voice",
        suitable_races=["dark_elf"],
        suitable_classes=["rogue", "necromancer", "shadowknight"],
    ),
    VoiceProfile(
        profile_id="gnome_tinker",
        name="Fizzwick",
        gender=VoiceGender.MALE,
        tone=VoiceTone.HIGH,
        pitch_modifier=1.3,
        speed_modifier=1.2,
        description="Quick, excited gnome voice",
        suitable_races=["gnome"],
        suitable_classes=["wizard", "enchanter", "magician", "rogue"],
    ),
    VoiceProfile(
        profile_id="human_paladin",
        name="Sir Valoris",
        gender=VoiceGender.MALE,
        tone=VoiceTone.COMMANDING,
        pitch_modifier=1.0,
        speed_modifier=0.95,
        description="Noble, commanding human paladin voice",
        suitable_races=["human"],
        suitable_classes=["paladin", "cleric", "warrior"],
    ),
    VoiceProfile(
        profile_id="erudite_sage",
        name="Arcanum",
        gender=VoiceGender.NEUTRAL,
        tone=VoiceTone.SMOOTH,
        pitch_modifier=1.1,
        speed_modifier=0.9,
        description="Measured, scholarly erudite voice",
        suitable_races=["erudite"],
        suitable_classes=["wizard", "enchanter", "necromancer", "sorceror"],
    ),
    VoiceProfile(
        profile_id="barbarian_shaman",
        name="Wulfgar",
        gender=VoiceGender.MALE,
        tone=VoiceTone.RASPY,
        pitch_modifier=0.75,
        speed_modifier=0.85,
        description="Raspy, powerful barbarian shaman voice",
        suitable_races=["barbarian"],
        suitable_classes=["shaman", "warrior", "berserker", "rogue"],
    ),
    VoiceProfile(
        profile_id="halfling_bard",
        name="Pippo",
        gender=VoiceGender.MALE,
        tone=VoiceTone.HIGH,
        pitch_modifier=1.2,
        speed_modifier=1.15,
        description="Cheerful, quick halfling bard voice",
        suitable_races=["halfling"],
        suitable_classes=["bard", "druid", "ranger", "rogue"],
    ),
    VoiceProfile(
        profile_id="iksar_monk",
        name="Sssithra",
        gender=VoiceGender.NEUTRAL,
        tone=VoiceTone.RASPY,
        pitch_modifier=0.9,
        speed_modifier=1.0,
        description="Hissing, disciplined iksar monk voice",
        suitable_races=["iksar"],
        suitable_classes=["monk", "necromancer", "shadowknight", "shaman"],
    ),
]


# ---------------------------------------------------------------------------
# Agent Voice Manager
# ---------------------------------------------------------------------------

class AgentVoiceManager:
    """Manages TTS voice profile assignment and lookup for streaming agents."""

    def __init__(self, roster: Optional[List[VoiceProfile]] = None) -> None:
        self._roster: List[VoiceProfile] = roster or list(DEFAULT_VOICE_ROSTER)
        self._assignments: Dict[str, str] = {}  # agent_id → profile_id

    @property
    def roster_size(self) -> int:
        return len(self._roster)

    def get_profile(self, profile_id: str) -> Optional[VoiceProfile]:
        for p in self._roster:
            if p.profile_id == profile_id:
                return p
        return None

    # --- Assignment ---

    def assign_voice(self, agent_id: str, profile_id: str) -> bool:
        """Manually assign a voice profile to an agent."""
        if self.get_profile(profile_id) is None:
            return False
        self._assignments[agent_id] = profile_id
        return True

    def auto_assign_voice(self, agent_id: str, race: str, agent_class: str) -> Optional[VoiceProfile]:
        """Automatically assign the best-matching voice profile.

        Matches on race first, then class, then falls back to the first
        available profile.
        """
        race_lower = race.lower()
        class_lower = agent_class.lower()

        # Priority 1: Match both race and class
        for p in self._roster:
            if race_lower in p.suitable_races and class_lower in p.suitable_classes:
                self._assignments[agent_id] = p.profile_id
                return p

        # Priority 2: Match race only
        for p in self._roster:
            if race_lower in p.suitable_races:
                self._assignments[agent_id] = p.profile_id
                return p

        # Priority 3: Match class only
        for p in self._roster:
            if class_lower in p.suitable_classes:
                self._assignments[agent_id] = p.profile_id
                return p

        # Fallback: first profile
        if self._roster:
            self._assignments[agent_id] = self._roster[0].profile_id
            return self._roster[0]

        return None

    def get_agent_voice(self, agent_id: str) -> Optional[VoiceProfile]:
        """Get the voice profile assigned to an agent."""
        profile_id = self._assignments.get(agent_id)
        if profile_id:
            return self.get_profile(profile_id)
        return None

    @property
    def assignment_count(self) -> int:
        return len(self._assignments)
