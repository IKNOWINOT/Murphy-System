# `src/multiverse_game_framework` — Multiverse Game Framework

Design Label: **GAME-000** — Weekly MMORPG world releases with universal character persistence across all worlds.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `multiverse_game_framework` package implements Murphy's cross-world character persistence layer. Characters leveled in any world carry their XP, skills, items (by portability tier), and LUCK stat into every subsequent world. Weekly world releases are tracked through the `WorldRegistry`. The package integrates the billboard ad system, AI companion dynamics, Murphy agent gameplay sessions, and a built-in streaming/spectator system.

## Key Components

| Module | Design Label | Purpose |
|--------|-------------|---------|
| `universal_character.py` | GAME-001 | Character model, leveling, LUCK system, class balance |
| `world_registry.py` | GAME-002 | World definitions and cross-world travel |
| `item_portability.py` | GAME-003 | Cross-world item portability tiers |
| `spell_synergy.py` | GAME-004 | Cooperative spell combination detection |
| `billboard_system.py` | GAME-005 | Proximity-based in-world advertising |
| `ai_companion.py` | GAME-006 | AI companion employer/employee dynamic |
| `agent_player.py` | GAME-007 | Murphy agent gameplay sessions |
| `streaming_integration.py` | GAME-008 | Built-in streaming and spectator system |
| `multiplayer_recruitment.py` | GAME-009 | Active player recruitment and matchmaking |

## Public API

```python
from src.multiverse_game_framework import (
    UniversalCharacter, CharacterClass, ActionType, ClassBalanceRegistry,
    WorldRegistry, WorldDefinition,
    ItemPortabilityTier,
    SpellSynergy, SpellCombination,
    BillboardSystem, BillboardAd,
    AICompanion, CompanionGoal,
    AgentPlayer, AgentSession,
    StreamingIntegration, SpectatorSession,
    MultiplayerRecruitment,
)
```

## Related

- `src/game_creation_pipeline/` — pipeline that generates worlds
- `docs/EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`
