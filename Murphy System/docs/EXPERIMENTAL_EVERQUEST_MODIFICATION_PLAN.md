# Experimental EverQuest Modification Plan

**Murphy System — Experimental Game Integration Plan**
**Version:** 3.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Codename:** Project Sourcerior

---

## 1. Executive Summary

This document defines the complete plan for an **experimental modification of EverQuest** powered by the Murphy System's multi-Rosetta soul architecture. The modification introduces Murphy-driven AI agents as in-game NPCs with persistent souls, a novel hybrid class called the **Sourcerior** (monk/mage hybrid), integrated voice chat with raid-leader moderation, a faction-based agent warfare system, and a player-vs-agent duel-and-loot mechanic. The entire experience is designed to be **streamed live**.

The server is a **Planes of Power progression server** with a universal **Remake System** — once any class maxes out level, AA, and skills, they can "remake" with a 1% permanent increase in stat and skill caps, starting again slightly stronger.

AI agents operate as **pure melee**, **int caster**, or **cleric** archetypes. Each agent builds **individual faction** with players based on direct interactions — holding grudges when mistreated and becoming friendly when helped. Agents express themselves **only through actions** — they cannot respond verbally or spam hate text at players.

The agent soul system follows the **OpenClaw Molty soul.md** pattern (see `OPENCLAW_MOLTY_SOUL_CONCEPT.md`) where each agent's Rosetta state document acts as its persistent soul — driving memory, recall, faction loyalty, combat decisions, and social interactions.

---

## 2. Scope

### 2.1 Core Systems Required

| System | Description | Dependency |
|---|---|---|
| **Agent Soul Engine** | Memory/archive system for NPC agents with recall triggers | `inference_gate_engine.py`, Rosetta state layer |
| **AI Agent Classes** | Pure melee, int caster, and cleric archetypes for agents | Soul engine, class ability tables |
| **Sourcerior Class** | Monk/mage hybrid class with unique mechanics | Game client modification, spell/ability tables |
| **Voice Chat Integration** | Group/raid toggle voice with admin moderation | WebRTC or Mumble protocol, Murphy admin controls |
| **Faction Soul System** | Agent-to-agent warfare driven by faction standings | Soul engine, faction DB, event backbone |
| **Individual Agent Faction** | Per-agent interaction-based reputation with players | Soul engine, interaction tracker |
| **Duel & Loot System** | Player-vs-agent 1v1 duels with single-item loot stakes | Combat engine, inventory hooks, inspect gates |
| **Streaming Pipeline** | Live-stream-ready overlay and event capture | OBS integration, event telemetry |
| **Raid Leader Admin** | Murphy-powered raid leader moderation tools | Voice chat system, governance kernel |
| **Progression Server** | Planes of Power era cap with controlled progression | EQEmu server configuration |
| **Remake System** | 1% stat/skill cap increase per cycle for all classes | Character DB, AA system, progression tracker |
| **Race Cultural Identity** | Cultural values per race, orc playable race, agent personality biases | Soul engine, persona_injector.py, EQEmu race tables |

### 2.2 Reference Documents

| Document | Purpose |
|---|---|
| `OPENCLAW_MOLTY_SOUL_CONCEPT.md` | Agent soul / memory / archive / recall architecture |
| `SOURCERIOR_CLASS_DESIGN.md` | Full Sourcerior class ability and scaling design |
| `RACE_CULTURAL_IDENTITY_DESIGN.md` | Race cultural identities, orc playable race, agent cultural personality |
| `inference_gate_engine.py` | Existing multi-Rosetta soul pattern implementation |
| `ROSETTA_STATE_MANAGEMENT_SYSTEM.md` | State management architecture reference |

---

## 3. Agent Soul Architecture

### 3.1 Soul Document Structure

Each Murphy agent in-game carries a **Rosetta soul document** — a persistent, structured state file that acts as the agent's memory, personality, and decision-making core. The soul document follows the OpenClaw Molty soul.md concept adapted for game NPCs.

```
┌─────────────────────────────────────────────────────────────┐
│ AGENT SOUL DOCUMENT                                          │
├─────────────────────────────────────────────────────────────┤
│ Identity                                                     │
│   name, class, level, faction, personality_traits            │
├─────────────────────────────────────────────────────────────┤
│ Memory Store (Short-Term)                                    │
│   recent_events[], current_zone, nearby_entities[]           │
│   active_buffs[], combat_state, group_context                │
├─────────────────────────────────────────────────────────────┤
│ Archive Store (Long-Term)                                    │
│   encountered_players{}, known_items{}, faction_history[]    │
│   combat_outcomes[], zone_knowledge{}, trade_history[]       │
├─────────────────────────────────────────────────────────────┤
│ Recall Engine                                                │
│   trigger_map: visual_cue → memory_key                       │
│   association_graph: entity → [related_memories]             │
│   confidence_scores: memory_key → recall_confidence          │
├─────────────────────────────────────────────────────────────┤
│ Faction Alignment                                            │
│   faction_id, faction_standings{}, ally_factions[]           │
│   enemy_factions[], war_declarations[], diplomacy_log[]      │
├─────────────────────────────────────────────────────────────┤
│ Knowledge Base (Inspect Gate)                                │
│   unlocked_items{}: item_id → item_stats                     │
│   unlock_condition: "previously_possessed"                   │
│   inspect_capability: false (until item is known)            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Memory and Recall System

The memory system has two tiers:

**Short-Term Memory** — Rolling buffer of recent events (last 50–100 events). Includes what the agent has seen, who it has interacted with, and current combat/social state. Flushed periodically but key events promoted to archive.

**Long-Term Archive** — Persistent store keyed by entity, item, zone, and event type. When an agent sees a player, item, or zone it has encountered before, the recall engine triggers and loads relevant archive entries into the agent's active context.

**Recall Triggers:**
- Visual proximity to a known player → loads encounter history
- Entering a known zone → loads zone knowledge and past events
- Seeing an item previously possessed → unlocks inspect capability for that item
- Hearing a faction name → loads faction standing and diplomacy history

### 3.3 Faction Soul Functions

Agents are assigned to **factions** that drive their social behavior:

- Agents of opposing factions will **war with each other** autonomously
- Agents of the same or allied factions will cooperate, group, and trade
- **Faction standing threshold**: If a player's faction standing with an agent's faction is high enough, the agent treats them as friendly regardless of other factors
- Agents **cannot attack players unprovoked** — they can only issue **duel challenges**
- Faction wars between agents are autonomous and create emergent world events

### 3.4 Individual Agent Faction — Interaction-Based Reputation

Beyond global faction standings, each agent builds **individual reputation** with every player it interacts with. This is tracked per-agent in the soul document and is separate from group faction standings.

**How individual faction works:**

| Player Action | Faction Impact | Agent Response (via actions only) |
|---|---|---|
| **Help agent in combat** | +faction | Agent assists player in future encounters |
| **Heal or buff agent** | +faction | Agent offers favorable trades, shares loot |
| **Trade fairly** | +faction | Agent seeks out player for future trades |
| **Kill agent's allies** | −faction | Agent avoids player, refuses interaction |
| **Steal agent's loot** | −faction | Agent challenges to duel more aggressively |
| **Repeatedly attack/grief** | −−faction (grudge) | Agent holds grudge — actively avoids, challenges to duel on sight |
| **Ignore agent** | No change | Agent treats player as neutral |

**Grudge and friendship mechanics:**
- **Grudges accumulate**: Repeated negative interactions compound — the more you mistreat an agent, the deeper the grudge
- **Friendship builds gradually**: Consistent positive interactions build trust over many encounters
- **Grudges fade slowly**: A grudge decays over real time but much slower than friendship builds
- **Individual override**: An agent's individual standing with a player can override its faction's global standing — a friendly agent from a hostile faction may still help a player it personally likes
- **Memory-driven**: All interaction history is stored in the agent's soul document long-term archive

**Actions speak, not words — the silence rule:**
- Agents **cannot respond verbally** to players — no chat messages, no emote text spam, no hate speech
- Agents **cannot spam hate** at players — there is no verbal aggression mechanic
- All agent feelings are expressed **exclusively through actions**: helping, avoiding, challenging, trading, ignoring
- A grudge-holding agent simply challenges the player to a duel or walks away — it never says why
- A friendly agent assists in combat or offers trades — it never explains its motivation
- This creates emergent storytelling: players must **observe agent behavior** to understand how agents feel about them

### 3.5 AI Agent Classes

All AI agents (Murphy NPCs) are assigned one of three class archetypes. Each archetype determines the agent's combat abilities, gear, and role in group encounters:

| Archetype | Role | Abilities | Gear |
|---|---|---|---|
| **Pure Melee** | Tank / DPS | Melee combat, taunt, kick, bash, riposte, dual wield | Plate/chain armor, melee weapons |
| **Int Caster** | Ranged DPS / Utility | Nukes, DoTs, roots, snares, mana management | Cloth/leather armor, staves, wands |
| **Cleric** | Healer / Buffer | Heals, buffs, resurrections, undead nukes, defensive spells | Chain/plate armor, 1H blunt + shield |

**Agent class distribution:**
- Agent class is assigned at soul creation and persists for the agent's lifetime
- Distribution is configurable per zone and faction (e.g., a temple faction may have more clerics)
- Agents group with each other using standard EQ group composition logic
- Agent class determines which items the agent values for duel loot assessment

**Class-specific behaviors:**
- **Pure Melee** agents prefer direct combat, will taunt mobs off players they like, and challenge strongest-looking players to duels
- **Int Caster** agents prefer ranged positions, will root/snare threats to players they like, and assess duel opponents by magic resist gear
- **Cleric** agents prefer support roles, will heal players they are friendly with, buff allies, and are least likely to initiate duels

**Varying effects by class and faction:**
- Each agent's abilities have **varying effects** based on their individual level, gear, and AA progression
- Faction affiliation influences ability selection (e.g., a fire-aligned faction's int casters favor fire spells)
- Individual interaction history affects **who** agents use their abilities on — a friendly cleric heals you, a grudge-holding melee challenges you

---

## 4. Progression Server — Planes of Power

### 4.1 Era Cap

The experimental server is a **Planes of Power progression server**:

- Content progresses through Classic → Kunark → Velious → Luclin → Planes of Power
- **Planes of Power is the final expansion** — no further content unlocks
- Level cap: **65** (PoP era)
- AA cap: All AAs available through PoP era
- All content and itemization designed around PoP-era balance

### 4.2 Progression Unlock Schedule

| Era | Level Cap | Key Content | Duration |
|---|---|---|---|
| **Classic** | 50 | Original zones, planes, epic 1.0 quests | 8 weeks |
| **Kunark** | 60 | Kunark zones, Veeshan's Peak, epic completion | 8 weeks |
| **Velious** | 60 | Velious zones, Temple of Veeshan, Sleeper's Tomb | 8 weeks |
| **Luclin** | 65 | Luclin zones, Vex Thal, AAs introduced | 8 weeks |
| **Planes of Power** | 65 | Planar progression, Plane of Time, full AA | Permanent |

### 4.3 Sourcerior in Progression

The Sourcerior class is available from Classic era but its abilities scale through progression:

- **Classic**: Core melee, basic procs, 1–2 pets, first melds unlock
- **Kunark**: Full proc set, 4 pets, all basic melds, epic quest begins
- **Velious**: 5 pets, greater melds, epic quest completable
- **Luclin**: 6 pets, AAs, full meld mastery
- **PoP**: All abilities, full AA tree, epic fully optimized

---

## 5. Remake System — Prestige Cycling

### 5.1 Overview

The **Remake System** is a universal prestige mechanic that applies to **every class** (including the Sourcerior and all AI agent classes). Once a character has maximized all progression milestones, they can "remake" — resetting to level 1 with a permanent **1% increase in all stat and skill caps**.

### 5.2 Remake Requirements

To qualify for a remake, a character must have completed **all** of the following:

| Requirement | Description |
|---|---|
| **Max Level** | Level 65 (Planes of Power cap) |
| **All AA** | Every available alternate advancement ability purchased |
| **Max Skills** | All class skills at their current cap |
| **Planes Flagged** | Completed Planes of Power progression (Plane of Time access) |

### 5.3 Remake Benefits

| Benefit | Per Remake | Cumulative |
|---|---|---|
| **Stat caps** | +1% to all base stat caps (STR, AGI, STA, INT, WIS, CHA) | Stacks with each remake |
| **Skill caps** | +1% to all class skill caps (melee, magic, tradeskill) | Stacks with each remake |
| **HP/Mana caps** | +1% to max HP and mana formulas | Stacks with each remake |
| **Remake count** | Visible on character inspect as prestige indicator | Shows total remakes |

### 5.4 Remake Process

1. Character meets all requirements (level 65, all AA, max skills, PoP flagged)
2. Player initiates remake at a special NPC in Plane of Knowledge
3. Character resets to **level 1** with starting gear
4. All AA are refunded (must be re-earned)
5. All skills reset to level 1 values (with new +1% caps)
6. Stat caps permanently increase by 1%
7. A **Remake Counter** badge is added to the character (visible on inspect)
8. Player begins leveling again — slightly stronger than before

### 5.5 Remake for AI Agents

AI agents also participate in the Remake System:

- Agents that reach max level, AA, and skills can be flagged for remake by the Murphy System
- Agent remake is **automatic** when conditions are met (no player intervention)
- Remade agents retain their **soul document** (memory, faction, grudges, knowledge) but reset combat stats
- This means long-lived agents become progressively stronger over time
- Agent remake count is visible when players inspect them

### 5.6 Design Philosophy

- **Slightly stronger each cycle**: The 1% increase is intentionally small — it rewards dedication without creating power gaps
- **Applies to every class**: Monks, mages, clerics, bards, and the Sourcerior all benefit equally
- **Infinite ceiling**: There is no cap on remakes — a character can theoretically remake indefinitely
- **Visible prestige**: The remake counter serves as a prestige indicator for both players and agents

---

## 6. Sourcerior Class Design

> Full design specification: `SOURCERIOR_CLASS_DESIGN.md`

### 6.1 Class Identity

The Sourcerior is a **monk/mage hybrid** that scales between melee discipline and arcane power. The class favors proc-based damage over direct-cast nukes, summons up to 6 elementals of four types (earth, air, fire, water), and provides group utility through proc-based song-like buffs. The Sourcerior can **meld with pets** for elemental aspect buffs, and wields a **two-handed staff** as its core weapon.

### 6.2 Core Mechanics Summary

| Mechanic | Description |
|---|---|
| **Melee Foundation** | Monk-style hand-to-hand and kick skills as primary combat |
| **Proc-Based DPS** | Damage procs replace kicks — AE damage procs on melee hits |
| **Pet System** | Up to 6 elementals of four types (earth, air, fire, water) |
| **Invoke Pet / Meld** | Absorb a pet to gain its elemental aspect (HP+taunt, backstab, DS+burn, crit magic) |
| **Flame Blink** | Forward blink replaces feign death — releases elementals that root and taunt |
| **AE Mez** | Minor enchanter-category AE mesmerize spells |
| **Song-Like Procs** | AE pet heal, buff, haste procs (overhaste-style, weaker than bard lines) |
| **Sacrifice Pets** | Consumes pets for a nuke — mobility ability for movement phases |
| **Epic Weapon** | Very slow 2H staff with heavy base DMG — amplifies meld effectiveness |

### 6.3 Scaling Philosophy

The Sourcerior scales between monk and mage power curves:
- At low levels, plays mostly as a monk with minor pet summons
- At mid levels, proc effects become meaningful and pet count increases
- At high levels, the full 6-pet army with proc-based AE DPS and meld cycling is online
- Bard song lines of equivalent level should always be **stronger** than Sourcerior procs
- The value is in the combination: melee DPS + pet DPS + meld aspects + proc utility
- **Two-handed staves** are the core weapon — high base damage maximizes proc and meld scaling
- Can wear **cloth and leather** armor

---

## 7. Race Cultural Identity System

> Full design specification: `RACE_CULTURAL_IDENTITY_DESIGN.md`

### 7.1 Overview

Every playable race is assigned a **cultural identity** inspired by a real-world civilization. These cultural mappings shape AI agent personality, faction behavior, quest themes, and social dynamics. Cultural identities are layered on top of existing EQ faction alignments — they provide motivation for existing relationships, not replacements.

### 7.2 Race–Culture Summary

| Race | Cultural Inspiration | Key Values |
|---|---|---|
| **Gnome** | Spartan (Ancient Greece) | Military discipline, communal duty, honor in combat |
| **Dark Elf** | German | Precision, order, hierarchical authority, methodical conquest |
| **High Elf** | Chinese | Scholarly tradition, celestial harmony, bureaucratic governance |
| **Wood Elf** | Japanese | Nature harmony, bushido-like code, ancestral reverence |
| **Barbarian** | American Indian | Land connection, tribal council, spirit kinship, honor through deeds |
| **Vah Shir** | Irish | Fierce independence, clan loyalty, storytelling, spirited defiance |
| **Halfling** | Muslim Persian | Trade networks, sacred hospitality, poetic philosophy, garden culture |
| **Human (Qeynos)** | British | Constitutional governance, naval tradition, institutional loyalty |
| **Human (Freeport)** | American | Entrepreneurial ambition, individual liberty, frontier spirit |
| **Dwarf** | Mongol | Nomadic warrior heritage, clan confederation, trade route mastery |
| **Ogre** | Dictatorship with Rebellion | Authoritarian rule vs. underground resistance, internal dissent |
| **Troll** | Hawaiian | Island community, ocean/fire reverence, warrior-dancer culture |
| **Erudite** | Phoenician | Maritime trade empire, knowledge innovation, merchant-explorer ambition |
| **Iksar** | Nordic Viking | Imperial conquest, runic mysticism, saga tradition, honor-bound code |
| **Orc** *(new playable)* | Barbarian-equivalent | Tribal honor, strength-tested leadership, Crushbone starting zone |
| **Half Elf** | Byzantine | Diplomatic bridge-builders, dual heritage, adaptive pragmatism |

### 7.3 Orc — New Playable Race

Orcs are introduced as a **new playable race** starting in Crushbone:
- **Class availability**: Same as Barbarian (Warrior, Rogue, Shaman, Beastlord)
- **Starting zone**: Crushbone redesigned as a full orc starting city
- **Faction start**: Allied with Crushbone Orcs (reformed), hostile to Wood Elf and High Elf cities
- **Cultural identity**: Tribal honor culture — earn respect through deeds, strength-tested leadership

### 7.4 Cultural Personality in AI Agents

Cultural values are injected into Murphy agent soul documents via `persona_injector.py`, affecting:
- How quickly agents challenge to duels (aggression threshold)
- How readily they form positive faction with players (friendship build rate)
- How long they hold grudges (grudge decay rate)
- How they prioritize targets in faction warfare (honor sensitivity)
- How they respond to trade offers and assistance (trade openness)

---

## 8. Voice Chat Integration

### 8.1 Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ VOICE CHAT SYSTEM                                             │
├──────────────────────────────────────────────────────────────┤
│ Transport Layer                                               │
│   WebRTC peer-to-peer with TURN fallback                     │
│   Opus codec, 48kHz, adaptive bitrate                        │
├──────────────────────────────────────────────────────────────┤
│ Group Voice Toggle                                            │
│   Per-group voice channel, auto-join on group invite          │
│   Push-to-talk or voice-activation with noise gate            │
│   Mute/unmute per member, volume per member                  │
├──────────────────────────────────────────────────────────────┤
│ Raid Voice                                                    │
│   Raid-wide channel + per-group sub-channels                 │
│   Raid leader broadcast mode (one-to-many)                   │
│   Murphy admin moderation (mute, kick, priority speaker)     │
├──────────────────────────────────────────────────────────────┤
│ Murphy Raid Leader Admin                                      │
│   Auto-mute during pull countdown                            │
│   Priority speaker queue for raid leader + assist            │
│   Voice activity logging for after-action review             │
│   Toxic behavior detection (optional, via sentiment engine)  │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 Toggle System

| Toggle | Scope | Default |
|---|---|---|
| `voice_group` | Group members only | ON when grouped |
| `voice_raid` | All raid members | ON for raid leader, OFF for members |
| `voice_raid_subgroup` | Sub-group within raid | OFF (opt-in) |
| `voice_broadcast` | Raid leader → all | Raid leader only |
| `murphy_moderation` | Murphy admin controls | ON for raid leader |

### 8.3 Murphy Raid Leader Admin

The raid leader gains Murphy-powered moderation tools:

- **Auto-mute on pull**: Configurable countdown mutes all non-leaders
- **Priority speaker**: Raid leader and marked assists get priority
- **Voice logging**: Optional recording for after-action review
- **Sentiment detection**: Flags toxic communication patterns using `sentiment_classifier.py`
- **Murphy governance**: Admin actions logged through Murphy governance kernel

---

## 9. Duel and Loot System

### 9.1 Duel Mechanics

- Agents can **challenge any player** to a 1v1 duel
- Players can **accept or decline** — no forced combat
- Duels take place in a bounded arena zone (instanced or local)
- Standard EverQuest combat rules apply within the duel
- **Stakes**: Winner loots **one item** from the loser

### 9.2 Loot Stakes

| Outcome | Winner Action |
|---|---|
| **Player wins** | Player can loot one item from the agent's inventory |
| **Agent wins** | Agent loots one item from the player's inventory |
| **Decline** | No penalty, agent may challenge again after cooldown |

### 9.3 Inspect Asymmetry

- **Players can inspect agents** — see agent gear, stats, faction
- **Agents cannot inspect players** — unless the agent has **previously possessed** the specific item
- When an agent has had an item before, that item is **unlocked** in the agent's knowledge base (soul document)
- This creates an information asymmetry that rewards players for understanding the system

---

## 10. Streaming Pipeline

### 10.1 Stream-Ready Features

| Feature | Purpose |
|---|---|
| **Event overlay** | Real-time display of agent soul events, faction wars, duel outcomes |
| **Agent thought bubbles** | Show what the agent is "thinking" (soul recall triggers) |
| **Faction war map** | Live visualization of faction territory and conflicts |
| **Duel highlight reel** | Auto-capture and replay of notable duel moments |
| **Voice chat integration** | Stream audio from raid/group voice channels |
| **Murphy dashboard** | Real-time Murphy System metrics and agent state |

### 10.2 OBS Integration

- Custom OBS plugin for Murphy event overlays
- Scene switching triggers on major events (faction war, duel, raid boss)
- Chat integration for viewer interaction with agents
- Automated clip creation for highlight moments

---

## 11. Technical Requirements

### 11.1 Server Infrastructure

| Component | Specification |
|---|---|
| **Game Server** | EverQuest emulator (EQEmu) with custom modifications |
| **Murphy Backend** | Murphy System 1.0 runtime with soul engine extensions |
| **Voice Server** | WebRTC signaling server + TURN relay |
| **Database** | PostgreSQL for soul documents + Redis for short-term memory |
| **Vector Store** | RAG vector integration for memory recall |
| **Stream Server** | RTMP ingest for OBS, HLS distribution |

### 11.2 Client Modifications

| Modification | Description |
|---|---|
| **Sourcerior class** | New class entries in spell/ability tables, client UI |
| **Voice UI** | Push-to-talk keybind, voice indicators, toggle UI |
| **Duel UI** | Challenge dialog, stake selection, outcome display |
| **Agent indicators** | Visual markers for Murphy agents vs regular NPCs |

### 11.3 Murphy System Extensions

| Extension | Module | Description |
|---|---|---|
| **Soul Engine** | `soul_engine.py` | Agent soul document management, memory/archive/recall |
| **Faction Manager** | `faction_manager.py` | Faction standings, war declarations, diplomacy |
| **Duel Controller** | `duel_controller.py` | Duel challenge, combat, loot resolution |
| **Voice Bridge** | `voice_bridge.py` | WebRTC integration, Murphy admin moderation |
| **Stream Overlay** | `stream_overlay.py` | OBS event feed, overlay rendering |
| **Game Connector** | `eq_game_connector.py` | EQEmu server communication bridge |

---

## 12. Data Models

### 12.1 Soul Document Schema

```python
{
    "agent_id": "uuid",
    "name": "str",
    "class": "str",
    "level": "int",
    "faction_id": "str",
    "personality_traits": ["str"],
    "short_term_memory": {
        "recent_events": [{"timestamp": "iso8601", "event_type": "str", "data": {}}],
        "current_zone": "str",
        "nearby_entities": ["str"],
        "active_buffs": ["str"],
        "combat_state": "str",
        "group_context": {}
    },
    "long_term_archive": {
        "encountered_players": {"player_id": {"first_seen": "iso8601", "interactions": []}},
        "known_items": {"item_id": {"name": "str", "stats": {}, "possessed": "bool"}},
        "faction_history": [{"timestamp": "iso8601", "faction": "str", "standing_change": "float"}],
        "combat_outcomes": [{"opponent": "str", "result": "str", "timestamp": "iso8601"}],
        "zone_knowledge": {"zone_id": {"visited_count": "int", "notable_events": []}},
        "trade_history": [{"partner": "str", "items_exchanged": {}, "timestamp": "iso8601"}]
    },
    "recall_engine": {
        "trigger_map": {"visual_cue": "memory_key"},
        "association_graph": {"entity": ["related_memory_keys"]},
        "confidence_scores": {"memory_key": "float"}
    },
    "faction_alignment": {
        "faction_id": "str",
        "faction_standings": {"faction_id": "float"},
        "ally_factions": ["str"],
        "enemy_factions": ["str"],
        "war_declarations": [{"target_faction": "str", "declared_at": "iso8601"}],
        "diplomacy_log": [{"event": "str", "timestamp": "iso8601"}]
    },
    "knowledge_base": {
        "unlocked_items": {"item_id": {"name": "str", "stats": {}}},
        "unlock_condition": "previously_possessed",
        "inspect_capability": "bool"
    }
}
```

### 12.2 Faction Schema

```python
{
    "faction_id": "uuid",
    "name": "str",
    "alignment": "str",  # good, neutral, evil
    "territory_zones": ["str"],
    "member_agents": ["agent_id"],
    "standings": {"faction_id": "float"},  # -1.0 (KOS) to 1.0 (ally)
    "war_targets": ["faction_id"],
    "diplomacy_events": [{"type": "str", "with_faction": "str", "timestamp": "iso8601"}]
}
```

### 12.3 Duel Record Schema

```python
{
    "duel_id": "uuid",
    "challenger": {"type": "agent|player", "id": "str"},
    "defender": {"type": "agent|player", "id": "str"},
    "status": "str",  # pending, accepted, in_progress, completed, declined
    "winner": "str",
    "looted_item": {"item_id": "str", "name": "str", "from": "str", "to": "str"},
    "combat_log": [{"timestamp": "iso8601", "action": "str", "damage": "int"}],
    "started_at": "iso8601",
    "completed_at": "iso8601"
}
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Weeks 1–4)

- [ ] Set up EQEmu development server with Planes of Power progression config
- [ ] Implement soul engine with memory/archive/recall
- [ ] Create Sourcerior class in spell/ability tables
- [ ] Implement AI agent class archetypes (pure melee, int caster, cleric)
- [ ] Basic agent spawning with soul documents
- [ ] Define race cultural identity templates for persona injector

### Phase 2: Combat & Class (Weeks 5–8)

- [ ] Implement Sourcerior abilities (procs, pets, flame blink, sacrifice)
- [ ] Implement Invoke Pet / Meld system (earth, air, fire, water aspects)
- [ ] Implement AE mez spells from enchanter category
- [ ] Implement song-like proc system (overhaste, buff, heal)
- [ ] Balance pet scaling (6 pets, four elements, low HP, decent damage)
- [ ] Implement two-handed staff weapon class and epic quest framework

### Phase 3: Social Systems (Weeks 9–12)

- [ ] Implement faction soul functions and agent warfare
- [ ] Implement individual agent faction with interaction-based reputation
- [ ] Implement grudge and friendship mechanics in soul documents
- [ ] Implement actions-only expression rule (no verbal agent responses)
- [ ] Implement duel challenge and loot system
- [ ] Implement inspect asymmetry (agent knowledge base gating)
- [ ] Voice chat integration with group/raid toggles

### Phase 4: Murphy Integration (Weeks 13–16)

- [ ] Wire Murphy raid leader admin moderation
- [ ] Connect sentiment classifier for voice moderation
- [ ] Implement governance kernel logging for all admin actions
- [ ] Connect Rosetta state management for soul persistence
- [ ] Integrate cultural personality templates into persona_injector.py

### Phase 5: Progression & Remake (Weeks 17–20)

- [ ] Implement progression server era unlock schedule
- [ ] Implement Remake System for all classes (1% stat/skill cap increase)
- [ ] Implement agent remake cycle (automatic, retains soul document)
- [ ] Build remake counter UI and inspect integration

### Phase 6: Race & Culture (Weeks 21–24)

- [ ] Implement orc as new playable race (race table, starting stats, character model)
- [ ] Redesign Crushbone as orc starting city (NPCs, merchants, quest givers)
- [ ] Implement cultural behavioral biases in agent soul documents
- [ ] Create race-specific quest content reflecting cultural values
- [ ] Implement cultural faction alignment motivation layer
- [ ] Test agent cultural personality across all race templates

### Phase 7: Stream & Polish (Weeks 25–28)

- [ ] Build OBS overlay plugin for Murphy events
- [ ] Implement agent thought bubble visualization
- [ ] Build faction war map overlay
- [ ] Duel highlight auto-capture
- [ ] End-to-end stream testing

---

## 14. Information Requirements

### 14.1 What Is Needed to Begin

| Category | Required Information |
|---|---|
| **EQEmu Version** | Which EQEmu branch/fork to build against |
| **Client Version** | Which EQ client version (Titanium, SoD, RoF2) |
| **Zone Selection** | Which zones to deploy agents in initially |
| **Faction Design** | Number of factions, alignment distribution, territory map |
| **Agent Count** | Target number of concurrent soul-bearing agents |
| **Sourcerior Balance** | Target DPS range relative to monks and mages at each tier |
| **Voice Platform** | Self-hosted WebRTC vs Mumble vs Discord bridge |
| **Stream Platform** | Twitch, YouTube, or multi-platform |
| **Hardware Budget** | Server specs for game + Murphy + voice + stream |
| **Content Policy** | Rules for agent behavior, language, duel stakes limits |

### 14.2 Dependencies on Existing Murphy Modules

| Module | Usage |
|---|---|
| `inference_gate_engine.py` | Soul document drives agent decision gates |
| `avatar/persona_injector.py` | Agent personality trait injection |
| `avatar/sentiment_classifier.py` | Voice chat toxic behavior detection |
| `avatar/behavioral_scoring_engine.py` | Agent behavior scoring and adjustment |
| `governance_kernel.py` | Admin action governance and audit logging |
| `workflow_dag_engine.py` | Agent task execution workflows |
| `state_manager.py` | Rosetta state persistence for soul documents |

---

## 15. Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| **EQEmu stability** | Server crashes with many agents | Load test incrementally, cap agent count |
| **Soul document bloat** | Memory/storage growth over time | Archive rotation, summarization, TTL on short-term |
| **Voice latency** | Poor raid experience | TURN server geo-distribution, codec optimization |
| **Duel exploitation** | Economy manipulation through duel farming | Cooldown timers, item rarity caps, anti-farming detection |
| **Agent behavior** | Agents behaving inappropriately | Governance kernel gates, behavior scoring, HITL override |
| **Stream performance** | Game + voice + overlay CPU pressure | Dedicated stream PC or cloud-based encoding |

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
