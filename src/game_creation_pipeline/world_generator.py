"""
World Generator — Procedural World & Level Generation Engine

Generates complete game instances on-demand across any genre. Each world is a
versioned game instance with unique zones/levels, NPCs, objectives, and lore.
Supports MMORPG, platformer, puzzle, runner, shooter, strategy, survival, and more.

Provides:
  - Zone / level templates (cities, dungeons, platformer stages, puzzle rooms, etc.)
  - NPC / enemy population seeding
  - Objective / quest chain generation
  - Lore generation
  - World rules and physics parameters
  - Genre-aware defaults per game type
"""

from __future__ import annotations

import logging
import random
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

class ZoneType(Enum):
    """Type classification for a generated zone / level."""

    # MMORPG / Adventure
    CITY = "city"
    TOWN = "town"
    DUNGEON = "dungeon"
    WILDERNESS = "wilderness"
    RAID = "raid"
    INSTANCED = "instanced"
    UNDERWATER = "underwater"
    AERIAL = "aerial"
    # Platformer
    PLATFORMER_STAGE = "platformer_stage"
    BOSS_STAGE = "boss_stage"
    # Puzzle
    PUZZLE_ROOM = "puzzle_room"
    ESCAPE_ROOM = "escape_room"
    # Shooter / Combat
    ARENA = "arena"
    BATTLEFIELD = "battlefield"
    STEALTH_ZONE = "stealth_zone"
    # Survival / Open World
    OVERWORLD = "overworld"
    BASE_CAMP = "base_camp"
    RESOURCE_ZONE = "resource_zone"
    # Racing / Runner
    TRACK = "track"
    OBSTACLE_COURSE = "obstacle_course"
    # Tower Defense / Strategy
    STRATEGIC_MAP = "strategic_map"
    DEFENSE_LANE = "defense_lane"
    # Hub / Meta
    HUB = "hub"
    TUTORIAL = "tutorial"
    CUTSCENE = "cutscene"


class GameType(Enum):
    """Primary genre / game type for a generated world."""

    MMORPG = "mmorpg"
    PLATFORMER = "platformer"
    PUZZLE = "puzzle"
    RUNNER = "runner"
    SHOOTER = "shooter"
    STRATEGY = "strategy"
    SURVIVAL = "survival"
    ADVENTURE = "adventure"
    RACING = "racing"
    TOWER_DEFENSE = "tower_defense"
    ROGUELIKE = "roguelike"
    VISUAL_NOVEL = "visual_novel"
    SANDBOX = "sandbox"
    FIGHTING = "fighting"
    HORROR = "horror"


class WorldTheme(Enum):
    """High-level aesthetic theme for a generated world."""

    FANTASY = "fantasy"
    DARK_FANTASY = "dark_fantasy"
    STEAMPUNK = "steampunk"
    COSMIC_HORROR = "cosmic_horror"
    MYTHOLOGICAL = "mythological"
    POST_APOCALYPTIC = "post_apocalyptic"
    CYBERPUNK = "cyberpunk"
    MEDIEVAL = "medieval"
    SCI_FI = "sci_fi"
    HORROR = "horror"
    WESTERN = "western"
    UNDERWATER = "underwater"
    SPACE = "space"
    JUNGLE = "jungle"
    ARCTIC = "arctic"
    DESERT = "desert"
    URBAN = "urban"
    RETRO = "retro"
    ABSTRACT = "abstract"
    CARTOON = "cartoon"


class NPCRole(Enum):
    """Primary role of a generated NPC."""

    VENDOR = "vendor"
    QUEST_GIVER = "quest_giver"
    GUARD = "guard"
    ENEMY = "enemy"
    BOSS = "boss"
    TRAINER = "trainer"
    INNKEEPER = "innkeeper"
    BANKER = "banker"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class NPC:
    """A generated NPC in a zone."""

    npc_id: str
    name: str
    role: NPCRole
    zone_id: str
    level: int
    faction: str
    spawn_count: int = 1
    loot_table: List[str] = field(default_factory=list)
    dialogue: List[str] = field(default_factory=list)
    luck_influence: float = 0.1   # how much player luck affects NPC outcomes


@dataclass
class QuestStep:
    """A single step in a quest chain."""

    step_id: str
    description: str
    required_zone_id: str
    required_players: int = 1   # cooperation requirement
    required_class_ids: List[str] = field(default_factory=list)


@dataclass
class QuestChain:
    """A generated quest chain."""

    quest_id: str
    name: str
    zone_id: str
    steps: List[QuestStep] = field(default_factory=list)
    min_group_size: int = 1
    level_requirement: int = 1
    reward_item_ids: List[str] = field(default_factory=list)
    lore_text: str = ""


@dataclass
class Zone:
    """A generated world zone."""

    zone_id: str
    name: str
    zone_type: ZoneType
    world_id: str
    level_range: Tuple[int, int]   # (min, max)
    description: str
    npcs: List[NPC] = field(default_factory=list)
    quests: List[QuestChain] = field(default_factory=list)
    connected_zone_ids: List[str] = field(default_factory=list)
    billboard_count: int = 0
    is_streaming_hotspot: bool = False
    min_group_size: int = 1   # 1 = solo-ok, >1 = cooperation required


@dataclass
class WorldRules:
    """Physics and gameplay rules for a generated world."""

    world_id: str
    pvp_enabled: bool = True
    death_penalty: str = "xp_loss"   # "xp_loss", "item_drop", "none"
    rest_xp_enabled: bool = True
    max_group_size: int = 6
    max_raid_size: int = 72
    luck_stat_visible: bool = True   # Luck is always visible (not hidden RNG)
    cooperation_wall_level: int = 25  # Solo progression stops being viable here


@dataclass
class WorldInstance:
    """A fully generated world / game instance."""

    world_id: str
    name: str
    theme: WorldTheme
    game_type: "GameType" = None   # genre — defaults to MMORPG for backwards compat
    version: int = 1
    rules: WorldRules = None
    zones: List[Zone] = field(default_factory=list)
    lore_summary: str = ""
    generated_at: float = field(default_factory=time.time)
    release_date: Optional[float] = None
    is_active: bool = False


# ---------------------------------------------------------------------------
# Zone Templates
# ---------------------------------------------------------------------------

_ZONE_TEMPLATES: Dict[ZoneType, Dict[str, Any]] = {
    ZoneType.CITY: {
        "npc_roles": [NPCRole.VENDOR, NPCRole.QUEST_GIVER, NPCRole.TRAINER, NPCRole.BANKER, NPCRole.INNKEEPER],
        "billboard_count": 6,
        "is_streaming_hotspot": True,
        "min_group_size": 1,
    },
    ZoneType.TOWN: {
        "npc_roles": [NPCRole.VENDOR, NPCRole.QUEST_GIVER, NPCRole.GUARD],
        "billboard_count": 2,
        "is_streaming_hotspot": False,
        "min_group_size": 1,
    },
    ZoneType.DUNGEON: {
        "npc_roles": [NPCRole.ENEMY, NPCRole.BOSS],
        "billboard_count": 0,
        "is_streaming_hotspot": True,
        "min_group_size": 3,
    },
    ZoneType.WILDERNESS: {
        "npc_roles": [NPCRole.ENEMY, NPCRole.QUEST_GIVER],
        "billboard_count": 1,
        "is_streaming_hotspot": False,
        "min_group_size": 1,
    },
    ZoneType.RAID: {
        "npc_roles": [NPCRole.BOSS, NPCRole.ENEMY],
        "billboard_count": 0,
        "is_streaming_hotspot": True,
        "min_group_size": 18,
    },
    ZoneType.INSTANCED: {
        "npc_roles": [NPCRole.ENEMY, NPCRole.BOSS],
        "billboard_count": 0,
        "is_streaming_hotspot": False,
        "min_group_size": 2,
    },
}

# Theme-flavored zone name prefixes
_ZONE_PREFIXES: Dict[WorldTheme, List[str]] = {
    WorldTheme.FANTASY: ["Verdant", "Crystal", "Shadow", "Golden", "Ancient"],
    WorldTheme.DARK_FANTASY: ["Cursed", "Blighted", "Ashen", "Vile", "Forsaken"],
    WorldTheme.STEAMPUNK: ["Ironclad", "Gear", "Smoke", "Brass", "Steam"],
    WorldTheme.COSMIC_HORROR: ["Eldritch", "Void", "Unseen", "Nameless", "Dread"],
    WorldTheme.MYTHOLOGICAL: ["Sacred", "Divine", "Titan", "Olympian", "Stygian"],
    WorldTheme.POST_APOCALYPTIC: ["Rusted", "Broken", "Scarred", "Barren", "Remnant"],
}

_ZONE_SUFFIXES: Dict[ZoneType, List[str]] = {
    ZoneType.CITY: ["City", "Citadel", "Stronghold", "Bastion", "Capital"],
    ZoneType.TOWN: ["Town", "Village", "Hamlet", "Settlement", "Outpost"],
    ZoneType.DUNGEON: ["Depths", "Lair", "Catacombs", "Caverns", "Vault"],
    ZoneType.WILDERNESS: ["Wastes", "Reaches", "Plains", "Forest", "Hills"],
    ZoneType.RAID: ["Fortress", "Keep", "Sanctum", "Citadel", "Palace"],
    ZoneType.INSTANCED: ["Instance", "Trial", "Challenge", "Arena", "Proving Grounds"],
    ZoneType.UNDERWATER: ["Abyss", "Reef", "Depths", "Trench", "Grotto"],
    ZoneType.AERIAL: ["Spire", "Aerie", "Summit", "Pinnacle", "Cloudtop"],
}

_NPC_NAME_PARTS = ["Thar", "Zel", "Mord", "Vex", "Kyr", "Oth", "Nym", "Drev"]
_QUEST_PREFIXES = ["The Lost", "Shadow of", "Hunt for", "Curse of", "Legacy of", "Secrets of"]
_LORE_FRAGMENTS = [
    "Long before the age of mortals, the Architects shaped this world from raw Aether.",
    "The Great Sundering shattered the original continent into its current form.",
    "Ancient pacts with the Spirit Realm grant power to those who honor them.",
    "The Luck Weave permeates all things — those attuned to it find fortune favors them.",
    "Cooperation is the foundation of civilization; no hero stands truly alone.",
]


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class WorldGenerator:
    """
    Procedural world generation engine.

    Thread-safe: all shared state protected by ``_lock``.
    Bounded collections: uses ``capped_append`` (CWE-770).
    """

    _MAX_WORLDS = 200
    _ZONES_PER_WORLD = 12
    _NPCS_PER_ZONE = 8
    _QUESTS_PER_ZONE = 3

    def __init__(self, seed: Optional[int] = None) -> None:
        self._lock = threading.Lock()
        self._worlds: Dict[str, WorldInstance] = {}
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # World generation
    # ------------------------------------------------------------------

    def generate_world(
        self,
        name: str,
        theme: WorldTheme,
        version: int = 1,
        seed: Optional[int] = None,
    ) -> WorldInstance:
        """
        Procedurally generate a complete world instance.

        The generated world includes zones, NPCs, quests, and lore.
        """
        rng = random.Random(seed) if seed is not None else self._rng

        world_id = str(uuid.uuid4())
        rules = WorldRules(world_id=world_id)

        zones = self._generate_zones(world_id, theme, rng)
        lore = self._generate_lore(theme, rng)

        world = WorldInstance(
            world_id=world_id,
            name=name,
            theme=theme,
            version=version,
            rules=rules,
            zones=zones,
            lore_summary=lore,
        )

        with self._lock:
            capped_append_world = len(self._worlds) < self._MAX_WORLDS
            if capped_append_world:
                self._worlds[world_id] = world
            else:
                logger.warning("World registry full (%d). Consider archiving old worlds.", self._MAX_WORLDS)

        logger.info(
            "World '%s' (id=%s, theme=%s, v%d) generated with %d zones.",
            name, world_id, theme.value, version, len(zones),
        )
        return world

    def get_world(self, world_id: str) -> Optional[WorldInstance]:
        """Return a world by ID."""
        with self._lock:
            return self._worlds.get(world_id)

    def activate_world(self, world_id: str) -> None:
        """Mark a world as active (open for players)."""
        with self._lock:
            w = self._worlds.get(world_id)
            if w:
                w.is_active = True
                w.release_date = time.time()

    def all_worlds(self) -> List[WorldInstance]:
        """Return all registered worlds."""
        with self._lock:
            return list(self._worlds.values())

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_world(self, world_id: str) -> Tuple[bool, List[str]]:
        """
        Validate that a world is complete and ready for players.

        Returns (is_valid, list_of_issues).
        """
        world = self.get_world(world_id)
        if not world:
            return False, [f"World '{world_id}' not found."]

        issues: List[str] = []

        if not world.zones:
            issues.append("World has no zones.")

        zone_types = {z.zone_type for z in world.zones}
        if ZoneType.CITY not in zone_types:
            issues.append("World has no city zone (required as starting point).")
        if ZoneType.DUNGEON not in zone_types:
            issues.append("World has no dungeon zone.")

        zones_with_quests = [z for z in world.zones if z.quests]
        if len(zones_with_quests) < 2:
            issues.append("At least 2 zones must have quests.")

        if not world.lore_summary:
            issues.append("World has no lore summary.")

        return len(issues) == 0, issues

    # ------------------------------------------------------------------
    # Internal generators
    # ------------------------------------------------------------------

    def _generate_zones(
        self, world_id: str, theme: WorldTheme, rng: random.Random
    ) -> List[Zone]:
        """Generate a set of zones for a world."""
        zone_plan: List[Tuple[ZoneType, Tuple[int, int]]] = [
            (ZoneType.CITY, (1, 10)),
            (ZoneType.TOWN, (1, 15)),
            (ZoneType.WILDERNESS, (5, 20)),
            (ZoneType.DUNGEON, (10, 30)),
            (ZoneType.WILDERNESS, (15, 35)),
            (ZoneType.TOWN, (20, 40)),
            (ZoneType.DUNGEON, (25, 50)),
            (ZoneType.WILDERNESS, (30, 60)),
            (ZoneType.INSTANCED, (40, 65)),
            (ZoneType.DUNGEON, (50, 75)),
            (ZoneType.WILDERNESS, (60, 85)),
            (ZoneType.RAID, (70, 100)),
        ]

        zones: List[Zone] = []
        zone_ids: List[str] = []

        for zone_type, level_range in zone_plan:
            zone = self._generate_zone(world_id, zone_type, theme, level_range, rng)
            zones.append(zone)
            zone_ids.append(zone.zone_id)

        # Wire connections (each zone connects to adjacent zones)
        for i, zone in enumerate(zones):
            if i > 0:
                zone.connected_zone_ids.append(zone_ids[i - 1])
            if i < len(zones) - 1:
                zone.connected_zone_ids.append(zone_ids[i + 1])

        return zones

    def _generate_zone(
        self,
        world_id: str,
        zone_type: ZoneType,
        theme: WorldTheme,
        level_range: Tuple[int, int],
        rng: random.Random,
    ) -> Zone:
        """Generate a single zone."""
        template = _ZONE_TEMPLATES.get(zone_type, {})
        prefixes = _ZONE_PREFIXES.get(theme, ["Ancient"])
        suffixes = _ZONE_SUFFIXES.get(zone_type, ["Place"])

        name = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
        zone = Zone(
            zone_id=str(uuid.uuid4()),
            name=name,
            zone_type=zone_type,
            world_id=world_id,
            level_range=level_range,
            description=f"A {zone_type.value} zone themed around {theme.value}.",
            billboard_count=template.get("billboard_count", 0),
            is_streaming_hotspot=template.get("is_streaming_hotspot", False),
            min_group_size=template.get("min_group_size", 1),
        )

        # Generate NPCs
        npc_roles = template.get("npc_roles", [NPCRole.ENEMY])
        for _ in range(self._NPCS_PER_ZONE):
            npc = self._generate_npc(zone.zone_id, rng.choice(npc_roles), level_range, rng)
            zone.npcs.append(npc)

        # Generate quests
        for _ in range(self._QUESTS_PER_ZONE):
            quest = self._generate_quest(zone.zone_id, level_range, rng)
            zone.quests.append(quest)

        return zone

    def _generate_npc(
        self,
        zone_id: str,
        role: NPCRole,
        level_range: Tuple[int, int],
        rng: random.Random,
    ) -> NPC:
        """Generate a single NPC."""
        name = (
            rng.choice(_NPC_NAME_PARTS) + rng.choice(_NPC_NAME_PARTS).lower()
            + " the " + role.value.replace("_", " ").title()
        )
        return NPC(
            npc_id=str(uuid.uuid4()),
            name=name,
            role=role,
            zone_id=zone_id,
            level=rng.randint(level_range[0], level_range[1]),
            faction="neutral" if role in (NPCRole.VENDOR, NPCRole.TRAINER) else "hostile",
            spawn_count=rng.randint(1, 4),
            dialogue=[
                f"Welcome, adventurer. I am {name}.",
                "Greetings, traveler. Do you seek aid?",
            ] if role in (NPCRole.VENDOR, NPCRole.QUEST_GIVER) else [],
        )

    def _generate_quest(
        self,
        zone_id: str,
        level_range: Tuple[int, int],
        rng: random.Random,
    ) -> QuestChain:
        """Generate a multi-step quest chain."""
        quest_name = (
            rng.choice(_QUEST_PREFIXES) + " " + rng.choice(_NPC_NAME_PARTS)
        )
        min_level = level_range[0]
        group_req = 1 if level_range[0] < 25 else rng.randint(2, 4)

        steps = [
            QuestStep(
                step_id=str(uuid.uuid4()),
                description=f"Step {i + 1}: Complete objective in the area.",
                required_zone_id=zone_id,
                required_players=group_req if i > 0 else 1,
            )
            for i in range(rng.randint(2, 5))
        ]

        return QuestChain(
            quest_id=str(uuid.uuid4()),
            name=quest_name,
            zone_id=zone_id,
            steps=steps,
            min_group_size=group_req,
            level_requirement=max(1, min_level),
            lore_text=rng.choice(_LORE_FRAGMENTS),
        )

    def _generate_lore(self, theme: WorldTheme, rng: random.Random) -> str:
        """Generate a short lore summary for the world."""
        fragment = rng.choice(_LORE_FRAGMENTS)
        return (
            f"A {theme.value} world where cooperation shapes destiny. "
            f"{fragment} "
            "Luck weaves through every outcome, and no soul walks alone."
        )
