"""
EverQuest Experimental Modification — Core Systems

This package implements the full Murphy System EverQuest modification as
described in the Experimental EverQuest Modification Plan.

Modules:
    npc_card_effects      — NPC identity template → 4-tier card effect auto-generation
    card_system           — Card collection, universal/god cards, Card of Unmaking, Tower entry
    spawner_registry      — Entity tracking, unmade status, world decay percentage
    soul_engine           — Agent soul document management with card collection
    eq_game_connector     — EQEmu server communication bridge (database, NPCs, zones, factions)
    lore_seeder           — EQEmu NPC/mob/boss data import and soul document pre-population
    faction_manager       — Faction standings, war declarations, diplomacy, army mobilization
    eq_gateway            — Isolation boundary, sandbox enforcement, language restriction
    macro_trigger_engine  — Classic bot behavior triggers (/assist, /follow, /attack, /cast)
    experience_lore       — Action capture, interaction recall, collective lore propagation
    perception_pipeline   — Screen-scan → inference → action → mind-write cycle (~250ms)
    agent_voice           — TTS voice profiles per race/class for streaming agents
    sourcerior_class      — Sourcerior monk/mage hybrid class, elemental pets, proc lines
    duel_controller       — Duel challenge lifecycle, loot stakes, and history
    tower_zone            — Tower of the Unmaker roaming zone mechanics
    remake_system         — Character remake bonuses and history tracking
    server_reboot         — Decay vote and server reboot / item survival logic
"""
