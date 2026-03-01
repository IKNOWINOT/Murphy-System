# Experimental EverQuest Modification Plan

**Murphy System — Experimental Game Integration Plan**
**Version:** 1.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Codename:** Project Sourcerior

---

## 1. Executive Summary

This document defines the complete plan for an **experimental modification of EverQuest** powered by the Murphy System's multi-Rosetta soul architecture. The modification introduces Murphy-driven AI agents as in-game NPCs with persistent souls, a novel hybrid class called the **Sourcerior** (monk/mage hybrid), integrated voice chat with raid-leader moderation, a faction-based agent warfare system, and a player-vs-agent duel-and-loot mechanic. The entire experience is designed to be **streamed live**.

The agent soul system follows the **OpenClaw Molty soul.md** pattern (see `OPENCLAW_MOLTY_SOUL_CONCEPT.md`) where each agent's Rosetta state document acts as its persistent soul — driving memory, recall, faction loyalty, combat decisions, and social interactions.

---

## 2. Scope

### 2.1 Core Systems Required

| System | Description | Dependency |
|---|---|---|
| **Agent Soul Engine** | Memory/archive system for NPC agents with recall triggers | `inference_gate_engine.py`, Rosetta state layer |
| **Sourcerior Class** | Monk/mage hybrid class with unique mechanics | Game client modification, spell/ability tables |
| **Voice Chat Integration** | Group/raid toggle voice with admin moderation | WebRTC or Mumble protocol, Murphy admin controls |
| **Faction Soul System** | Agent-to-agent warfare driven by faction standings | Soul engine, faction DB, event backbone |
| **Duel & Loot System** | Player-vs-agent 1v1 duels with single-item loot stakes | Combat engine, inventory hooks, inspect gates |
| **Streaming Pipeline** | Live-stream-ready overlay and event capture | OBS integration, event telemetry |
| **Raid Leader Admin** | Murphy-powered raid leader moderation tools | Voice chat system, governance kernel |

### 2.2 Reference Documents

| Document | Purpose |
|---|---|
| `OPENCLAW_MOLTY_SOUL_CONCEPT.md` | Agent soul / memory / archive / recall architecture |
| `SOURCERIOR_CLASS_DESIGN.md` | Full Sourcerior class ability and scaling design |
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

---

## 4. Sourcerior Class Design

> Full design specification: `SOURCERIOR_CLASS_DESIGN.md`

### 4.1 Class Identity

The Sourcerior is a **monk/mage hybrid** that scales between melee discipline and arcane power. The class favors proc-based damage over direct-cast nukes, summons up to 6 minor fire elementals, and provides group utility through proc-based song-like buffs.

### 4.2 Core Mechanics Summary

| Mechanic | Description |
|---|---|
| **Melee Foundation** | Monk-style hand-to-hand and kick skills as primary combat |
| **Proc-Based DPS** | Damage procs replace kicks — AE damage procs on melee hits |
| **Pet System** | Up to 6 fire elementals (low HP, decent scaled damage) |
| **Flame Blink** | Forward blink replaces feign death — releases elementals that root and taunt |
| **AE Mez** | Minor enchanter-category AE mesmerize spells |
| **Song-Like Procs** | AE pet heal, buff, haste procs (overhaste-style, weaker than bard lines) |
| **Sacrifice Pets** | Consumes pets for a nuke — mobility ability for movement phases |

### 4.3 Scaling Philosophy

The Sourcerior scales between monk and mage power curves:
- At low levels, plays mostly as a monk with minor pet summons
- At mid levels, proc effects become meaningful and pet count increases
- At high levels, the full 6-pet army with proc-based AE DPS is online
- Bard song lines of equivalent level should always be **stronger** than Sourcerior procs
- The value is in the combination: melee DPS + pet DPS + proc utility

---

## 5. Voice Chat Integration

### 5.1 Architecture

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

### 5.2 Toggle System

| Toggle | Scope | Default |
|---|---|---|
| `voice_group` | Group members only | ON when grouped |
| `voice_raid` | All raid members | ON for raid leader, OFF for members |
| `voice_raid_subgroup` | Sub-group within raid | OFF (opt-in) |
| `voice_broadcast` | Raid leader → all | Raid leader only |
| `murphy_moderation` | Murphy admin controls | ON for raid leader |

### 5.3 Murphy Raid Leader Admin

The raid leader gains Murphy-powered moderation tools:

- **Auto-mute on pull**: Configurable countdown mutes all non-leaders
- **Priority speaker**: Raid leader and marked assists get priority
- **Voice logging**: Optional recording for after-action review
- **Sentiment detection**: Flags toxic communication patterns using `sentiment_classifier.py`
- **Murphy governance**: Admin actions logged through Murphy governance kernel

---

## 6. Duel and Loot System

### 6.1 Duel Mechanics

- Agents can **challenge any player** to a 1v1 duel
- Players can **accept or decline** — no forced combat
- Duels take place in a bounded arena zone (instanced or local)
- Standard EverQuest combat rules apply within the duel
- **Stakes**: Winner loots **one item** from the loser

### 6.2 Loot Stakes

| Outcome | Winner Action |
|---|---|
| **Player wins** | Player can loot one item from the agent's inventory |
| **Agent wins** | Agent loots one item from the player's inventory |
| **Decline** | No penalty, agent may challenge again after cooldown |

### 6.3 Inspect Asymmetry

- **Players can inspect agents** — see agent gear, stats, faction
- **Agents cannot inspect players** — unless the agent has **previously possessed** the specific item
- When an agent has had an item before, that item is **unlocked** in the agent's knowledge base (soul document)
- This creates an information asymmetry that rewards players for understanding the system

---

## 7. Streaming Pipeline

### 7.1 Stream-Ready Features

| Feature | Purpose |
|---|---|
| **Event overlay** | Real-time display of agent soul events, faction wars, duel outcomes |
| **Agent thought bubbles** | Show what the agent is "thinking" (soul recall triggers) |
| **Faction war map** | Live visualization of faction territory and conflicts |
| **Duel highlight reel** | Auto-capture and replay of notable duel moments |
| **Voice chat integration** | Stream audio from raid/group voice channels |
| **Murphy dashboard** | Real-time Murphy System metrics and agent state |

### 7.2 OBS Integration

- Custom OBS plugin for Murphy event overlays
- Scene switching triggers on major events (faction war, duel, raid boss)
- Chat integration for viewer interaction with agents
- Automated clip creation for highlight moments

---

## 8. Technical Requirements

### 8.1 Server Infrastructure

| Component | Specification |
|---|---|
| **Game Server** | EverQuest emulator (EQEmu) with custom modifications |
| **Murphy Backend** | Murphy System 1.0 runtime with soul engine extensions |
| **Voice Server** | WebRTC signaling server + TURN relay |
| **Database** | PostgreSQL for soul documents + Redis for short-term memory |
| **Vector Store** | RAG vector integration for memory recall |
| **Stream Server** | RTMP ingest for OBS, HLS distribution |

### 8.2 Client Modifications

| Modification | Description |
|---|---|
| **Sourcerior class** | New class entries in spell/ability tables, client UI |
| **Voice UI** | Push-to-talk keybind, voice indicators, toggle UI |
| **Duel UI** | Challenge dialog, stake selection, outcome display |
| **Agent indicators** | Visual markers for Murphy agents vs regular NPCs |

### 8.3 Murphy System Extensions

| Extension | Module | Description |
|---|---|---|
| **Soul Engine** | `soul_engine.py` | Agent soul document management, memory/archive/recall |
| **Faction Manager** | `faction_manager.py` | Faction standings, war declarations, diplomacy |
| **Duel Controller** | `duel_controller.py` | Duel challenge, combat, loot resolution |
| **Voice Bridge** | `voice_bridge.py` | WebRTC integration, Murphy admin moderation |
| **Stream Overlay** | `stream_overlay.py` | OBS event feed, overlay rendering |
| **Game Connector** | `eq_game_connector.py` | EQEmu server communication bridge |

---

## 9. Data Models

### 9.1 Soul Document Schema

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

### 9.2 Faction Schema

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

### 9.3 Duel Record Schema

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

## 10. Implementation Phases

### Phase 1: Foundation (Weeks 1–4)

- [ ] Set up EQEmu development server
- [ ] Implement soul engine with memory/archive/recall
- [ ] Create Sourcerior class in spell/ability tables
- [ ] Basic agent spawning with soul documents

### Phase 2: Combat & Class (Weeks 5–8)

- [ ] Implement Sourcerior abilities (procs, pets, flame blink, sacrifice)
- [ ] Implement AE mez spells from enchanter category
- [ ] Implement song-like proc system (overhaste, buff, heal)
- [ ] Balance pet scaling (6 pets, low HP, decent damage)

### Phase 3: Social Systems (Weeks 9–12)

- [ ] Implement faction soul functions and agent warfare
- [ ] Implement duel challenge and loot system
- [ ] Implement inspect asymmetry (agent knowledge base gating)
- [ ] Voice chat integration with group/raid toggles

### Phase 4: Murphy Integration (Weeks 13–16)

- [ ] Wire Murphy raid leader admin moderation
- [ ] Connect sentiment classifier for voice moderation
- [ ] Implement governance kernel logging for all admin actions
- [ ] Connect Rosetta state management for soul persistence

### Phase 5: Stream & Polish (Weeks 17–20)

- [ ] Build OBS overlay plugin for Murphy events
- [ ] Implement agent thought bubble visualization
- [ ] Build faction war map overlay
- [ ] Duel highlight auto-capture
- [ ] End-to-end stream testing

---

## 11. Information Requirements

### 11.1 What Is Needed to Begin

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

### 11.2 Dependencies on Existing Murphy Modules

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

## 12. Risk Assessment

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
