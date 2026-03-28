# `src/game_creation_pipeline` — MMORPG Game Creation Pipeline

Weekly MMORPG generation pipeline — procedurally creates, assembles, tests, and releases complete multiplayer games on a 7-day cadence.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `game_creation_pipeline` package is Murphy's automated game factory. Every module enforces the design pillars: cooperation-required gameplay, synergy casting, Luck as a first-class stat, AI companion employer/employee dynamics, cosmetic-only monetization, in-game billboard ads, and deep streaming integration. The `WeeklyReleaseOrchestrator` coordinates the full pipeline from world generation through quality gates to release.

## Key Components

| Module | Design Label | Purpose |
|--------|-------------|---------|
| `luck_system.py` | GAME-L | High-impact Luck stat, roll tables, crit cascades |
| `monetization_rules.py` | GAME-M | Pay-to-win detection; cosmetic-only enforcement |
| `class_balance_engine.py` | GAME-C | Class archetypes, synergy matrix, spell combinations |
| `cooperation_mechanics.py` | GAME-CO | Group synergy, simultaneous cast detection, gates |
| `ai_companion_system.py` | GAME-A | AI companion employer/employee with persistent goals |
| `agent_player_controller.py` | GAME-AG | Murphy agents playing games during off-time |
| `billboard_ad_system.py` | GAME-B | Proximity-based in-game advertisement system |
| `streaming_integration.py` | GAME-S | OBS overlays, spectator mode, highlight capture |
| `world_generator.py` | GAME-W | Procedural world, zone, NPC, and quest generation |
| `weekly_release_orchestrator.py` | GAME-R | 7-day release pipeline with quality gates |

## API Routes

- `GET /api/game/worlds` — list available worlds
- `POST /api/game/pipeline/*` — pipeline control endpoints
- `POST /api/game/balance/*` — class balance tuning
- `GET /api/game/eq/status` — EQ mod system status
- `POST /api/game/monetization/validate` — validate monetization rules

## Related

- `src/multiverse_game_framework/` — cross-world character persistence
- `src/eq/` — EQ mod system (25 modules, 140 tasks)
- `docs/EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`
