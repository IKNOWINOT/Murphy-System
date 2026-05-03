"""
Game Creation Pipeline — Murphy System

This package provides the foundational engine for Murphy to procedurally
generate, assemble, test, and release complete games of any genre on a weekly
cadence. Supported genres: MMORPG, platformer, puzzle, runner, shooter,
strategy, survival, adventure, racing, tower defense, roguelike, and more.

Default game features (configurable per genre):
  - Genre-aware world/level generation
  - Luck as a high-impact stat (optional per genre)
  - AI companion system (optional per genre)
  - Murphy agent participation (agents play on their off-time)
  - Cosmetic-only monetization (no pay-to-win)
  - Deep streaming integration
  - In-game billboard advertisement system (proximity-based)
  - Multiplayer cooperation mechanics (optional — not required for solo genres)

Modules:
    luck_system               — High-impact Luck stat and roll system
    monetization_rules        — Pay-to-win detection and cosmetic-only enforcement
    class_balance_engine      — Class archetypes, synergy matrix, spell combinations
    cooperation_mechanics     — Group synergy, simultaneous cast detection, gates
    ai_companion_system       — AI employer/employee companions with goals
    agent_player_controller   — Murphy agents playing games on their off-time
    billboard_ad_system       — Proximity-based in-game advertisements
    streaming_integration     — OBS overlays, spectator mode, highlight capture
    world_generator           — Procedural world, zone, NPC, and quest generation
    weekly_release_orchestrator — 7-day release pipeline with quality gates
"""

from .luck_system import (
    LuckEventType,
    LuckOutcome,
    LuckProfile,
    LuckRoll,
    LuckSystem,
)
from .monetization_rules import (
    ItemCategory,
    ItemDefinition,
    MonetizationRulesEngine,
    MonetizationVerdict,
    COSMETIC_ONLY_MODEL,
    COSMETIC_AND_CONVENIENCE_MODEL,
)
from .class_balance_engine import (
    ClassBalanceEngine,
    ClassDefinition,
    CombinationSpell,
    RoleArchetype,
    SpellElement,
    SynergyBonus,
)
from .cooperation_mechanics import (
    CooperationGate,
    CooperationMechanics,
    Group,
    GroupMember,
    GroupRole,
    SimultaneousCastEvent,
    SYNERGY_WINDOW_SECONDS,
    PERFECT_SYNC_MAGNIFIER,
)
from .ai_companion_system import (
    AICompanionSystem,
    CompanionGoalType,
    CompanionPersonality,
    CompanionProfile,
    RelationshipDynamic,
)
from .agent_player_controller import (
    AgentCharacter,
    AgentPlayerController,
    AgentPlayStyle,
    PlaySession,
    SessionState,
)
from .billboard_ad_system import (
    AdContent,
    BillboardAdSystem,
    BillboardPlacementZone,
)
from .streaming_integration import (
    CameraMode,
    StreamEventType,
    StreamingIntegration,
)
from .world_generator import (
    GameType,
    WorldGenerator,
    WorldInstance,
    WorldRules,
    WorldTheme,
    Zone,
    ZoneType,
)
from .weekly_release_orchestrator import (
    PipelineRun,
    PipelineStage,
    QualityGateResult,
    WeeklyReleaseOrchestrator,
)

__all__ = [
    # luck_system
    "LuckEventType", "LuckOutcome", "LuckProfile", "LuckRoll", "LuckSystem",
    # monetization_rules
    "ItemCategory", "ItemDefinition",
    "MonetizationRulesEngine", "MonetizationVerdict",
    "COSMETIC_ONLY_MODEL", "COSMETIC_AND_CONVENIENCE_MODEL",
    # class_balance_engine
    "ClassBalanceEngine", "ClassDefinition", "CombinationSpell",
    "RoleArchetype", "SpellElement", "SynergyBonus",
    # cooperation_mechanics
    "CooperationGate", "CooperationMechanics", "Group", "GroupMember",
    "GroupRole", "SimultaneousCastEvent",
    "SYNERGY_WINDOW_SECONDS", "PERFECT_SYNC_MAGNIFIER",
    # ai_companion_system
    "AICompanionSystem", "CompanionGoalType", "CompanionPersonality",
    "CompanionProfile", "RelationshipDynamic",
    # agent_player_controller
    "AgentCharacter", "AgentPlayerController", "AgentPlayStyle",
    "PlaySession", "SessionState",
    # billboard_ad_system
    "AdContent", "BillboardAdSystem", "BillboardPlacementZone",
    # streaming_integration
    "CameraMode", "StreamEventType", "StreamingIntegration",
    # world_generator
    "GameType", "WorldGenerator", "WorldInstance", "WorldRules", "WorldTheme",
    "Zone", "ZoneType",
    # weekly_release_orchestrator
    "PipelineRun", "PipelineStage", "QualityGateResult",
    "WeeklyReleaseOrchestrator",
]
