"""
EQEmu Game Connector — Server Communication Bridge

Implements the EQEmu server communication bridge described in §11.3
of the Experimental EverQuest Modification Plan.

Provides:
  - Database connection configuration for the EQEmu MySQL/MariaDB backend
  - NPC data queries (names, levels, zones, factions, loot tables)
  - Zone data retrieval (zone name, id, level range, connected zones)
  - Spawn data queries (spawn groups, spawn points, respawn timers)
  - Faction data queries (faction IDs, base standings, allies/enemies)
  - Server event hooks for card drops, entity deaths, zone changes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class EQEmuDatabaseConfig:
    """Connection configuration for the EQEmu database backend."""

    host: str = "127.0.0.1"
    port: int = 3306
    username: str = "eqemu"
    password: str = ""  # Set via environment variable in production
    database: str = "peq"
    charset: str = "utf8mb4"

    @property
    def connection_string(self) -> str:
        return (
            f"mysql+pymysql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset={self.charset}"
        )


class ServerEra(Enum):
    """Progression server era — determines which content is unlocked."""

    CLASSIC = "classic"
    KUNARK = "kunark"
    VELIOUS = "velious"
    LUCLIN = "luclin"
    PLANES_OF_POWER = "planes_of_power"


@dataclass
class ServerConfig:
    """EQEmu server configuration for the Murphy System modification."""

    server_name: str = "Murphy EQ"
    era: ServerEra = ServerEra.PLANES_OF_POWER
    max_level: int = 65
    xp_modifier: float = 1.0  # 1.0 = original EQ rates
    hell_levels_enabled: bool = True
    death_penalty_enabled: bool = True
    corpse_runs_enabled: bool = True
    database: EQEmuDatabaseConfig = field(default_factory=EQEmuDatabaseConfig)


# ---------------------------------------------------------------------------
# NPC Data Transfer Objects
# ---------------------------------------------------------------------------

@dataclass
class NPCData:
    """NPC record from the EQEmu npc_types table."""

    npc_id: int
    name: str
    level: int
    max_level: int = 0
    race_id: int = 0
    class_id: int = 0
    body_type: int = 0
    hp: int = 0
    mana: int = 0
    gender: int = 0
    texture: int = 0
    helm_texture: int = 0
    size: float = 0.0
    attack_speed: float = 0.0
    min_dmg: int = 0
    max_dmg: int = 0
    primary_faction: int = 0
    see_invis: bool = False
    see_invis_undead: bool = False
    aggro_range: float = 0.0
    run_speed: float = 0.0
    special_abilities: str = ""
    loottable_id: int = 0
    merchant_id: int = 0
    adventure_template_id: int = 0
    is_named: bool = False

    def __post_init__(self) -> None:
        if self.max_level == 0:
            self.max_level = self.level
        # Named mobs have names starting with a capital and containing no '#'
        if not self.is_named and "#" not in self.name:
            self.is_named = self.name[:1].isupper() if self.name else False


@dataclass
class ZoneData:
    """Zone record from the EQEmu zone table."""

    zone_id: int
    short_name: str
    long_name: str
    min_level: int = 0
    max_level: int = 0
    zone_type: int = 0  # 0=outdoor, 1=dungeon, 2=city
    safe_x: float = 0.0
    safe_y: float = 0.0
    safe_z: float = 0.0
    connected_zones: List[str] = field(default_factory=list)
    expansion: int = 0  # 0=classic, 1=kunark, etc.


@dataclass
class FactionData:
    """Faction record from the EQEmu faction_list table."""

    faction_id: int
    name: str
    base_value: int = 0  # Starting faction standing
    allies: List[int] = field(default_factory=list)
    enemies: List[int] = field(default_factory=list)


@dataclass
class SpawnGroupData:
    """Spawn group from the EQEmu spawngroup/spawn2 tables."""

    spawngroup_id: int
    name: str
    zone_short_name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    heading: float = 0.0
    respawn_time: int = 640  # seconds
    npc_ids: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Server Event Types
# ---------------------------------------------------------------------------

class ServerEventType(Enum):
    """Events that the game connector can emit to Murphy System."""

    ENTITY_KILLED = "entity_killed"
    CARD_DROPPED = "card_dropped"
    ZONE_CHANGE = "zone_change"
    PLAYER_LOGIN = "player_login"
    PLAYER_LOGOUT = "player_logout"
    DUEL_STARTED = "duel_started"
    DUEL_ENDED = "duel_ended"
    FACTION_CHANGE = "faction_change"
    TOWER_SPAWNED = "tower_spawned"
    TOWER_DESPAWNED = "tower_despawned"
    SERVER_ANNOUNCEMENT = "server_announcement"
    DECAY_MILESTONE = "decay_milestone"


@dataclass
class ServerEvent:
    """An event emitted by the EQEmu game connector."""

    event_type: ServerEventType
    data: Dict[str, Any] = field(default_factory=dict)
    zone: str = ""
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# EQEmu Game Connector
# ---------------------------------------------------------------------------

class EQEmuGameConnector:
    """Communication bridge between Murphy System and the EQEmu server.

    In production this would connect to the EQEmu MySQL database and
    the server's shared-memory or TCP command interface.  This implementation
    provides the data-access API that the rest of the Murphy EQ subsystem
    programmes against, backed by an in-memory cache that can be populated
    from either a live database or test fixtures.
    """

    def __init__(self, config: Optional[ServerConfig] = None) -> None:
        self.config = config or ServerConfig()
        self._npcs: Dict[int, NPCData] = {}
        self._zones: Dict[str, ZoneData] = {}
        self._factions: Dict[int, FactionData] = {}
        self._spawn_groups: Dict[int, SpawnGroupData] = {}
        self._event_log: List[ServerEvent] = []
        self._connected: bool = False

    # --- Connection lifecycle ---

    def connect(self) -> bool:
        """Establish connection to EQEmu database.

        Returns True on success.  The in-memory implementation always
        succeeds; a live implementation would attempt a database connection.
        """
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # --- Data loading (populate the in-memory cache) ---

    def load_npc(self, npc: NPCData) -> None:
        """Load a single NPC record into the connector cache."""
        self._npcs[npc.npc_id] = npc

    def load_npcs(self, npcs: List[NPCData]) -> None:
        for npc in npcs:
            self.load_npc(npc)

    def load_zone(self, zone: ZoneData) -> None:
        self._zones[zone.short_name] = zone

    def load_zones(self, zones: List[ZoneData]) -> None:
        for zone in zones:
            self.load_zone(zone)

    def load_faction(self, faction: FactionData) -> None:
        self._factions[faction.faction_id] = faction

    def load_factions(self, factions: List[FactionData]) -> None:
        for faction in factions:
            self.load_faction(faction)

    def load_spawn_group(self, sg: SpawnGroupData) -> None:
        self._spawn_groups[sg.spawngroup_id] = sg

    # --- NPC queries ---

    def get_npc(self, npc_id: int) -> Optional[NPCData]:
        return self._npcs.get(npc_id)

    def get_npc_by_name(self, name: str) -> Optional[NPCData]:
        name_lower = name.lower()
        for npc in self._npcs.values():
            if npc.name.lower() == name_lower:
                return npc
        return None

    def get_npcs_by_zone(self, zone_short_name: str) -> List[NPCData]:
        """Return all NPCs that spawn in the given zone."""
        zone_lower = zone_short_name.lower()
        result: List[NPCData] = []
        for sg in self._spawn_groups.values():
            if sg.zone_short_name.lower() == zone_lower:
                for npc_id in sg.npc_ids:
                    npc = self._npcs.get(npc_id)
                    if npc:
                        result.append(npc)
        return result

    def get_named_npcs(self) -> List[NPCData]:
        return [n for n in self._npcs.values() if n.is_named]

    def get_npcs_by_level_range(self, min_level: int, max_level: int) -> List[NPCData]:
        return [
            n for n in self._npcs.values()
            if min_level <= n.level <= max_level
        ]

    def get_npcs_by_faction(self, faction_id: int) -> List[NPCData]:
        return [n for n in self._npcs.values() if n.primary_faction == faction_id]

    @property
    def npc_count(self) -> int:
        return len(self._npcs)

    # --- Zone queries ---

    def get_zone(self, short_name: str) -> Optional[ZoneData]:
        return self._zones.get(short_name)

    def get_all_zones(self) -> List[ZoneData]:
        return list(self._zones.values())

    @property
    def zone_count(self) -> int:
        return len(self._zones)

    # --- Faction queries ---

    def get_faction(self, faction_id: int) -> Optional[FactionData]:
        return self._factions.get(faction_id)

    def get_all_factions(self) -> List[FactionData]:
        return list(self._factions.values())

    def get_faction_enemies(self, faction_id: int) -> List[FactionData]:
        faction = self._factions.get(faction_id)
        if not faction:
            return []
        return [
            self._factions[eid]
            for eid in faction.enemies
            if eid in self._factions
        ]

    def get_faction_allies(self, faction_id: int) -> List[FactionData]:
        faction = self._factions.get(faction_id)
        if not faction:
            return []
        return [
            self._factions[aid]
            for aid in faction.allies
            if aid in self._factions
        ]

    @property
    def faction_count(self) -> int:
        return len(self._factions)

    # --- Spawn group queries ---

    def get_spawn_group(self, sg_id: int) -> Optional[SpawnGroupData]:
        return self._spawn_groups.get(sg_id)

    def get_spawn_groups_by_zone(self, zone_short_name: str) -> List[SpawnGroupData]:
        zone_lower = zone_short_name.lower()
        return [
            sg for sg in self._spawn_groups.values()
            if sg.zone_short_name.lower() == zone_lower
        ]

    # --- Event system ---

    def emit_event(self, event: ServerEvent) -> None:
        """Log a server event for consumption by the Murphy System."""
        capped_append(self._event_log, event)

    def get_events(self, event_type: Optional[ServerEventType] = None) -> List[ServerEvent]:
        if event_type is None:
            return list(self._event_log)
        return [e for e in self._event_log if e.event_type == event_type]

    def clear_events(self) -> None:
        self._event_log.clear()
