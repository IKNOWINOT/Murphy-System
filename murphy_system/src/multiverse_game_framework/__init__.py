"""
Multiverse Game Framework — Murphy System

Design Label: GAME-000 — Multiverse Game Framework Package
Owner: Backend Team

Weekly MMORPG world releases with a universal character system. Characters
persist across all worlds; their level, skills, and experience transcend
individual game instances.

Modules:
  universal_character  — GAME-001: Character model, leveling, LUCK system, class balance
  world_registry       — GAME-002: World definitions and cross-world travel
  item_portability     — GAME-003: Cross-world item portability tiers
  spell_synergy        — GAME-004: Cooperative spell combination detection
  billboard_system     — GAME-005: Proximity-based in-world advertising
  ai_companion         — GAME-006: AI companion employer/employee dynamic
  agent_player         — GAME-007: Murphy agent gameplay sessions
  streaming_integration— GAME-008: Built-in streaming and spectator system
  multiplayer_recruitment— GAME-009: Active player recruitment and matchmaking

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from .agent_player import (
    AgentGoal,
    AgentPlayerEngine,
    AgentPlayerProfile,
    GoalType,
    PlaySession,
    PlaySessionResult,
    PlayStyle,
)
from .ai_companion import (
    AICompanion,
    AICompanionEngine,
    AICompanionRole,
    CompletionResult,
    Directive,
    DirectiveStatus,
    Specialization,
)
from .billboard_system import (
    Billboard,
    BillboardAnalytics,
    BillboardEngine,
    BillboardScheduleWindow,
)
from .item_portability import (
    GameItem,
    ItemPortabilityEngine,
    ItemPortabilityTier,
    ItemType,
    TransferResult,
    TransferStatus,
)
from .multiplayer_recruitment import (
    ActivityType,
    InviteStatus,
    LFGListing,
    PlayerMatch,
    RecruitmentEngine,
    RecruitmentInvite,
    RecruitmentNeeds,
)
from .spell_synergy import (
    SpellCastEvent,
    SpellSynergyEngine,
    SynergyCombination,
    SynergyResult,
    SynergyType,
)
from .streaming_integration import (
    HighlightEvent,
    HighlightType,
    OverlayConfig,
    StreamingHotspot,
    StreamingManager,
    StreamPlatform,
    StreamQuality,
    StreamSession,
)
from .universal_character import (
    UNIVERSAL_LEVEL_CAP,
    ActionType,
    CharacterClass,
    ClassBalanceRegistry,
    ClassDefinition,
    ClassRole,
    LevelUpResult,
    LuckCheckOutcome,
    LuckCheckResult,
    LuckSystem,
    UniversalCharacter,
    UniversalLevelingEngine,
)
from .world_registry import (
    TravelResult,
    TravelStatus,
    WorldDefinition,
    WorldRegistry,
    WorldStatus,
)

__all__ = [
    # universal_character
    "ActionType",
    "CharacterClass",
    "ClassBalanceRegistry",
    "ClassDefinition",
    "ClassRole",
    "LevelUpResult",
    "LuckCheckOutcome",
    "LuckCheckResult",
    "LuckSystem",
    "UniversalCharacter",
    "UniversalLevelingEngine",
    "UNIVERSAL_LEVEL_CAP",
    # world_registry
    "TravelResult",
    "TravelStatus",
    "WorldDefinition",
    "WorldRegistry",
    "WorldStatus",
    # item_portability
    "GameItem",
    "ItemPortabilityEngine",
    "ItemPortabilityTier",
    "ItemType",
    "TransferResult",
    "TransferStatus",
    # spell_synergy
    "SpellCastEvent",
    "SpellSynergyEngine",
    "SynergyCombination",
    "SynergyResult",
    "SynergyType",
    # billboard_system
    "Billboard",
    "BillboardAnalytics",
    "BillboardEngine",
    "BillboardScheduleWindow",
    # ai_companion
    "AICompanion",
    "AICompanionEngine",
    "AICompanionRole",
    "CompletionResult",
    "Directive",
    "DirectiveStatus",
    "Specialization",
    # agent_player
    "AgentGoal",
    "AgentPlayerEngine",
    "AgentPlayerProfile",
    "GoalType",
    "PlaySession",
    "PlaySessionResult",
    "PlayStyle",
    # streaming_integration
    "HighlightEvent",
    "HighlightType",
    "OverlayConfig",
    "StreamingHotspot",
    "StreamingManager",
    "StreamPlatform",
    "StreamQuality",
    "StreamSession",
    # multiplayer_recruitment
    "ActivityType",
    "InviteStatus",
    "LFGListing",
    "PlayerMatch",
    "RecruitmentEngine",
    "RecruitmentInvite",
    "RecruitmentNeeds",
]
