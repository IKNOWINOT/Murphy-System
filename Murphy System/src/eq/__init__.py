"""
EverQuest Experimental Modification — Core Systems

This package implements the full Murphy System EverQuest modification as
described in the Experimental EverQuest Modification Plan.

All 25 modules are complete (140/140 implementation tasks done).

Modules:
    card_system           — Card collection, universal/god cards, Card of Unmaking, Tower entry
    npc_card_effects      — NPC identity template → 4-tier card effect auto-generation
    soul_engine           — Agent soul document management with card collection
    spawner_registry      — Entity tracking, unmade status, world decay percentage
    eq_game_connector     — EQEmu server communication bridge (database, NPCs, zones, factions)
    lore_seeder           — EQEmu NPC/mob/boss data import and soul document pre-population
    faction_manager       — Faction standings, war declarations, diplomacy, army mobilization
    eq_gateway            — Isolation boundary, sandbox enforcement, language restriction
    macro_trigger_engine  — Classic bot behavior triggers (/assist, /follow, /attack, /cast)
    experience_lore       — Action capture, interaction recall, collective lore propagation
    perception_pipeline   — Screen-scan → inference → action → mind-write cycle (~250ms)
    agent_voice           — TTS voice profiles per race/class for streaming agents
    sorceror_class      — Sorceror monk/mage hybrid class, elemental pets, proc lines
    duel_controller       — Duel challenge lifecycle, loot stakes, and history
    tower_zone            — Tower of the Unmaker roaming zone mechanics
    remake_system         — Character remake bonuses and history tracking
    server_reboot         — Decay vote and server reboot / item survival logic
    escalation_system     — Unmaking escalation: card-holder capabilities and world threats
    sleeper_event         — The Sleeper (Kerafyrm) world event, warder kills, dragon rallies
    unmaker_npc           — The Unmaker NPC, armor set, boss config, banned mechanic
    progression_server    — Era progression (Classic→PoP), XP rates, hell levels
    cultural_identity     — Race cultural templates, orc race, personality biases
    town_systems          — Inspect asymmetry, town conquest, governance logging
    streaming_overlay     — OBS overlay, thought bubbles, faction war map, duel highlights
    murphy_integration    — Voice chat, sentiment classifier, raid moderation, Rosetta persistence
    eqemu_asset_manager   — EQEmu upstream asset discovery, download tracking, and validation
"""

__all__: list[str] = []
