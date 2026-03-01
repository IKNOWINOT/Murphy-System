# OpenClaw Molty Soul Concept — Game Agent Adaptation

**Murphy System — Agent Soul Architecture for Game NPCs**
**Version:** 1.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Parent:** `EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`

---

## 1. Overview

This document defines the **OpenClaw Molty soul.md concept** as adapted for Murphy System game agents. The original pattern (referenced in `inference_gate_engine.py`) uses Rosetta state documents as each agent's "soul" — driving what information the agent needs, what gates apply, and what questions to ask. This adaptation extends that pattern to give game NPCs persistent memory, emotional state, faction loyalty, and recall-driven behavior.

The key principle: **each agent's soul is a living document** that grows with experience, persists across sessions, and drives all decision-making through the Rosetta form schema pattern.

---

## 2. Soul Architecture

### 2.1 Soul Layers

The game agent soul extends the Rosetta soul pattern with game-specific layers:

```
┌────────────────────────────────────────────────────────────────┐
│ ROSETTA SOUL (base layer — from inference_gate_engine.py)       │
│   Form schema, gates, metrics, confidence engine               │
├────────────────────────────────────────────────────────────────┤
│ IDENTITY LAYER                                                  │
│   Name, class, level, faction, personality archetype            │
│   Voice profile, combat style preference, risk tolerance        │
├────────────────────────────────────────────────────────────────┤
│ MEMORY LAYER                                                    │
│   Short-term: rolling event buffer (50–100 events)             │
│   Long-term archive: keyed by entity, item, zone, event type   │
│   Episodic: significant events stored as narratives            │
├────────────────────────────────────────────────────────────────┤
│ RECALL LAYER                                                    │
│   Trigger map: stimulus → memory retrieval                     │
│   Association graph: entity relationships and co-occurrences   │
│   Confidence decay: older memories fade unless reinforced       │
├────────────────────────────────────────────────────────────────┤
│ FACTION LAYER                                                   │
│   Faction identity and standings                                │
│   War/peace state machine                                       │
│   Diplomacy history and trust scores                            │
├────────────────────────────────────────────────────────────────┤
│ KNOWLEDGE LAYER                                                 │
│   Item database (only items previously possessed are known)     │
│   Zone familiarity (mapped areas, known spawns)                │
│   Player profiles (built from encounters, not inspection)       │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Rosetta Form Schema Integration

Following the existing Murphy pattern, each agent action is driven by a **form schema** that defines what data is needed. The soul document provides the context for filling that schema:

```
Agent encounters a player
    │
    ▼
Rosetta Form Schema: "social_interaction"
    fields: [player_id, faction_standing, encounter_history, threat_level]
    │
    ▼
Soul Memory provides: encounter_history, known faction standing
    │
    ▼
Sensors provide: player_id, current zone, player gear (if visible)
    │
    ▼
LLM fills generatively: threat assessment, conversation topic
    │
    ▼
Gates check: faction standing threshold, duel cooldown, aggression limit
    │
    ▼
Action: greet, challenge to duel, trade, or ignore
```

---

## 3. Memory System Design

### 3.1 Short-Term Memory

The short-term memory buffer holds the agent's immediate awareness:

| Field | Type | Description |
|---|---|---|
| `recent_events` | `list[Event]` | Last 50–100 game events within perception range |
| `current_zone` | `str` | Zone the agent is currently in |
| `nearby_entities` | `list[EntityRef]` | Players, NPCs, and objects within visual range |
| `active_buffs` | `list[BuffRef]` | Current active buff/debuff effects |
| `combat_state` | `enum` | idle, engaged, fleeing, dead, recovering |
| `group_context` | `GroupState` | Current group/raid membership and role |
| `conversation_context` | `ConversationState` | Active dialogue context with players |

**Promotion rules**: Events are promoted to long-term archive when they meet significance thresholds:
- Combat outcome (win/loss/flee)
- Item acquisition or loss
- New player encounter (first meeting)
- Faction standing change
- Zone discovery (first visit)
- Duel challenge or completion

### 3.2 Long-Term Archive

The archive is organized as a **keyed document store** within the soul:

| Archive Section | Key | Stored Data |
|---|---|---|
| `encountered_players` | `player_id` | First seen, interaction count, sentiment, outcomes |
| `known_items` | `item_id` | Name, stats, possessed history, source |
| `faction_history` | sequential | Faction standing changes with timestamps |
| `combat_outcomes` | sequential | Opponent, result, abilities used, damage dealt/taken |
| `zone_knowledge` | `zone_id` | Visit count, notable events, known spawns, paths |
| `trade_history` | sequential | Partner, items, fairness assessment |
| `duel_history` | sequential | Opponent, stakes, outcome, items won/lost |

### 3.3 Recall Engine

The recall engine is the mechanism by which archived memories become **active context** for decision-making:

**Trigger Types:**

| Trigger | Condition | Memory Retrieved |
|---|---|---|
| `visual_proximity` | Known entity enters perception range | Full encounter history for that entity |
| `zone_entry` | Agent enters a previously visited zone | Zone knowledge, past events in that zone |
| `item_sighting` | Agent sees an item it has previously possessed | Item stats, possession history |
| `faction_mention` | Faction name appears in dialogue or event | Faction standing, war history, diplomacy |
| `combat_initiation` | Combat begins with a known opponent | Past combat outcomes, strategy adjustments |
| `name_recognition` | Player name matches archived encounter | Full player profile from archive |

**Confidence Decay:**
- Memories lose recall confidence over time (configurable half-life)
- Reinforced memories (repeated encounters) gain confidence
- Very old, unreinforced memories may fail to recall (returns `null`)
- Critical memories (major combat, faction changes) have slower decay

---

## 4. Faction Soul Functions

### 4.1 Faction Identity

Each agent soul includes a **faction alignment** that drives social behavior:

```python
faction_alignment = {
    "faction_id": "flame_seekers",
    "faction_name": "Order of the Flame Seekers",
    "alignment": "neutral",
    "loyalty_score": 0.85,        # How loyal this agent is to their faction
    "standings": {
        "shadow_conclave": -0.8,  # KOS (kill on sight) threshold: -0.6
        "merchant_guild": 0.4,    # Friendly threshold: 0.3
        "wild_wardens": 0.0,      # Neutral
    },
    "war_targets": ["shadow_conclave"],
    "ally_factions": ["merchant_guild"],
}
```

### 4.2 Agent-to-Agent Warfare

Agents of opposing factions will **autonomously engage** each other:

- **War declaration**: When faction standing drops below `-0.6`, agents treat opposing faction as KOS
- **Combat engagement**: Agents encountering enemy faction agents will attack on sight
- **Territory control**: Factions claim zones; agents patrol and defend their territory
- **Emergent events**: Large-scale faction wars create server events visible to all players

### 4.3 Agent-to-Player Relations

Agents interact with players based on the player's **faction standing** with the agent's faction:

| Standing Range | Behavior |
|---|---|
| `1.0 to 0.6` | Allied — will assist in combat, offer quests, trade favorably |
| `0.6 to 0.3` | Friendly — will chat, trade, share zone knowledge |
| `0.3 to -0.3` | Neutral — will ignore, may respond to interaction |
| `-0.3 to -0.6` | Wary — will warn, may refuse interaction |
| `-0.6 to -1.0` | Hostile — will challenge to duel, refuse all interaction |

**Key rule**: Agents **cannot attack players unprovoked**. Even at KOS standing, the maximum hostile action is issuing a duel challenge. Players must accept.

---

## 5. Knowledge Base and Inspect Gate

### 5.1 The Inspect Asymmetry

A core game mechanic is the **inspect asymmetry** between players and agents:

- **Players** can freely inspect any agent: see gear, stats, level, faction
- **Agents** cannot inspect players by default
- An agent can only see details of items it has **previously possessed**
- When an item is possessed (equipped, looted, traded), it is permanently **unlocked** in the agent's knowledge base

### 5.2 Knowledge Unlock Flow

```
Agent acquires item (loot, trade, duel win)
    │
    ▼
Item stats recorded in soul document → knowledge_base.unlocked_items
    │
    ▼
Agent later encounters player wearing that item
    │
    ▼
Recall engine triggers → item recognized
    │
    ▼
Agent can now assess that specific item's stats on any player
```

This creates a **progressive information economy**: older agents with more item experience are more capable tacticians. New agents are essentially blind to player capabilities.

### 5.3 Soul Document Knowledge Base Schema

```python
knowledge_base = {
    "unlocked_items": {
        "item_12345": {
            "name": "Sword of Flowing Water",
            "stats": {"damage": 45, "delay": 24, "ac": 10},
            "first_possessed": "2026-03-15T10:00:00Z",
            "possession_count": 2,
            "source": "duel_loot"
        }
    },
    "unlock_condition": "previously_possessed",
    "inspect_capability": False,  # True only for specific unlocked items
    "total_unlocked": 1,
}
```

---

## 6. Integration with Murphy System

### 6.1 Module Mapping

| Soul Layer | Murphy Module | Integration |
|---|---|---|
| Rosetta base | `inference_gate_engine.py` | Form schemas drive agent action selection |
| Identity | `avatar/persona_injector.py` | Personality traits injected from avatar system |
| Memory | `state_manager.py` | Rosetta state persistence for soul documents |
| Recall | RAG vector integration | Vector similarity search for memory recall |
| Faction | `governance_kernel.py` | Faction rules enforced as governance gates |
| Knowledge | `librarian/` | Item/entity knowledge stored and indexed |
| Behavior | `avatar/behavioral_scoring_engine.py` | Behavior scoring and adjustment loops |

### 6.2 Persistence Strategy

Soul documents are persisted through the existing Murphy persistence layer:

- **Hot state**: Redis cache for active agents (short-term memory, current context)
- **Warm state**: PostgreSQL for soul documents (identity, archive, faction, knowledge)
- **Cold state**: S3/file storage for very old archive entries past retention window
- **Vector index**: RAG vector store for memory recall similarity search

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
