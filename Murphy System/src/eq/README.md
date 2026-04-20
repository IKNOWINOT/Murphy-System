# `src/eq` — EverQuest Experimental Modification

Full Murphy System EverQuest modification implementing 25 gameplay modules with AI-driven agents, card mechanics, and live-server integration.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The `eq` package is a complete EverQuest modification built on top of the EQEmu server. Each AI-driven character in the world is a persistent Murphy agent with a soul document; their identities, faction standings, and card collections are managed by the package's 25 specialised modules. An isolation boundary (`eq_gateway.py`) enforces that the EQ world cannot directly trigger Murphy execution packets, keeping game events as read-only artifacts. The perception pipeline runs at ~250 ms cycles, converting screen scans to actions and propagating collective lore across all agents.

## Key Components

| Module | Purpose |
|--------|---------|
| `card_system.py` | Card collection, universal/god cards, Card of Unmaking, Tower entry |
| `soul_engine.py` | Agent soul document management with card collection |
| `eq_game_connector.py` | EQEmu server communication bridge (database, NPCs, zones, factions) |
| `faction_manager.py` | Faction standings, war declarations, diplomacy, army mobilization |
| `eq_gateway.py` | Isolation boundary and sandbox enforcement |
| `perception_pipeline.py` | Screen-scan → inference → action → mind-write cycle (~250 ms) |
| `macro_trigger_engine.py` | Classic bot behaviour triggers (/assist, /follow, /cast) |
| `streaming_overlay.py` | OBS overlay, thought bubbles, faction war map, duel highlights |
| `murphy_integration.py` | Voice chat, sentiment classifier, raid moderation, Rosetta persistence |
| `progression_server.py` | Era progression (Classic→PoP), XP rates, hell levels |
| `spawner_registry.py` | Entity tracking, unmade status, world decay percentage |
| `npc_card_effects.py` | NPC identity template → 4-tier card effect auto-generation |
| `lore_seeder.py` | EQEmu NPC/mob/boss data import and soul document pre-population |
| `duel_controller.py` | Duel challenge lifecycle, loot stakes, and history |
| `tower_zone.py` | Tower of the Unmaker roaming zone mechanics |
| `sleeper_event.py` | The Sleeper (Kerafyrm) world event mechanics |
| `unmaker_npc.py` | The Unmaker NPC, armor set, boss config |
| `eqemu_asset_manager.py` | EQEmu upstream asset discovery, download tracking, and validation |
| `agent_voice.py` | TTS voice profiles per race/class for streaming agents |
| `cultural_identity.py` | Race cultural templates, personality biases |
| `town_systems.py` | Inspect asymmetry, town conquest, governance logging |
| `escalation_system.py` | Unmaking escalation: card-holder capabilities and world threats |
| `remake_system.py` | Character remake bonuses and history tracking |
| `server_reboot.py` | Decay vote and server reboot / item survival logic |
| `sorceror_class.py` | Sorceror hybrid class, elemental pets, proc lines |
| `experience_lore.py` | Action capture, interaction recall, collective lore propagation |

## Usage

```python
from eq.eq_gateway import EQGateway
from eq.soul_engine import SoulEngine

gateway = EQGateway()
souls = SoulEngine(gateway=gateway)

soul = souls.load("npc_1234")
print(soul.faction, soul.cards)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
