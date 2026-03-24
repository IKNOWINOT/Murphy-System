"""
MMORPG Game Creation Pipeline — Murphy System

This package provides the foundational engine for Murphy to procedurally
generate, assemble, test, and release complete MMORPG games on a weekly
cadence.

All games produced by this pipeline enforce:
  - Multiplayer-required gameplay (cooperation is the core loop)
  - Synergy casting and combination skills (simultaneous cast magnifiers)
  - Luck as a first-class high-impact stat
  - AI companion system (employer/employee dynamic)
  - Murphy agent participation (agents play on their off-time)
  - In-game billboard advertisement system (proximity-based, no pay-to-win)
  - Deep streaming integration
  - Cosmetic-only monetization (no pay-to-win)

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
    "WorldGenerator", "WorldInstance", "WorldRules", "WorldTheme",
    "Zone", "ZoneType",
    # weekly_release_orchestrator
    "PipelineRun", "PipelineStage", "QualityGateResult",
    "WeeklyReleaseOrchestrator",
]
