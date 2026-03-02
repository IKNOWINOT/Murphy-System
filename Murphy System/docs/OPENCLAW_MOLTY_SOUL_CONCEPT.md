# OpenClaw Molty Soul Concept — Game Agent Adaptation

**Murphy System — Agent Soul Architecture for Game NPCs**
**Version:** 2.0.0
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
│ CLASS PLAY-STYLE TEMPLATE (immutable — read-only reference)     │
│   Combat rotation, positioning, target selection, group role    │
│   Buff priority, emergency actions, item valuation              │
│   Fixed at server definition — shared across all same-class     │
│   agents — never changes — the "how to play this class" guide   │
├────────────────────────────────────────────────────────────────┤
│ IDENTITY LAYER                                                  │
│   Name, class (pure melee / int caster / cleric), level         │
│   Faction, personality archetype, combat style preference        │
│   Risk tolerance, individual player standings                    │
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
│   Faction identity and global standings                         │
│   Individual player standings (grudge/friendship per player)    │
│   War/peace state machine                                       │
│   Diplomacy history and trust scores                            │
├────────────────────────────────────────────────────────────────┤
│ KNOWLEDGE LAYER                                                 │
│   Item database (only items previously possessed are known)     │
│   Zone familiarity (mapped areas, known spawns)                │
│   Player profiles (built from encounters, not inspection)       │
├────────────────────────────────────────────────────────────────┤
│ LANGUAGE LAYER                                                  │
│   language_capability: ["Common Tongue", racial_language]        │
│   No programming language knowledge — agents cannot produce code│
│   No real-world vocabulary — agents know only in-game concepts  │
│   Enforced by sandbox gateway (eq_gateway) at isolation boundary│
├────────────────────────────────────────────────────────────────┤
│ SELF-PRESERVATION LAYER                                         │
│   Flee triggers: "run" command, healer death, HP threshold      │
│   Flee exception: hybrid healer sustaining the group            │
│   Agents treat their life as their only life (permadeath real)  │
│   Sourceriors use Liquify (water pets, level 40+) to escape     │
├────────────────────────────────────────────────────────────────┤
│ LIFESTYLE LAYER                                                 │
│   Caste: royal / noble / commoner / dhampir / servant           │
│   Job role: smith, merchant, guard, brewer, scholar, etc.       │
│   Daily routine: sleep → work shift → adventure/free time       │
│   Building ownership: workplace and residence tracking          │
│   Trade skill: primary skill with mastery, degradation, floor   │
│   Skill degrades without practice (1 week → fades to 50)       │
│   Level-based skill floor prevents full degradation             │
├────────────────────────────────────────────────────────────────┤
│ PERCEPTION-INFERENCE LAYER                                      │
│   Screen scan every ~250ms: entities, HP, mana, buffs, zone    │
│   Inference: compare perception against template + soul + lore │
│   Action: write decision to mind, execute via game connector   │
│   Macro-trigger patterns: assist, follow, engage, heal, debuff │
├────────────────────────────────────────────────────────────────┤
│ LORE-SEED LAYER                                                 │
│   Pre-populated from EQEmu NPC database and lore wikis         │
│   All NPCs, mobs, raid bosses seed agent identity and faction  │
│   Shared lore blocks: The Sleeper storyline in all agents      │
│   Social/economic systems grounded in canonical EQ lore        │
├────────────────────────────────────────────────────────────────┤
│ CARD COLLECTION LAYER                                           │
│   Universal cards: every entity drops cards (1% rate)           │
│   NPC cards: 4-tier progressive effects per entity              │
│     Tier 1: conditional combat spell (24-hour cooldown)         │
│     Tier 2: defensive buff (7-day cooldown)                     │
│     Tier 3: weapon/class specialization (7-day cooldown)        │
│     Tier 4: soul-bound protector (permanent companion)          │
│   Soul-bound protectors disturb all NPCs, AI players kill holder│
│   Only named creatures can be AI players (full soul documents)  │
│   God cards: deity cards unlock skill, buff, enchantment, void │
│   All card abilities: 1-week real-time cooldown                │
│   4 universal cards = entity deleted from game (world entropy) │
│   4 Cards of Unmaking = server reboot (3-card items survive)   │
│   Spawner Registry: per-entity log of unmade status + cards    │
│   50% decay = server-wide vote (players + AI agents vote)      │
│   Core of the Unmaker: requires 3-card holder to enter         │
│   Killing blow on Unmaker = become "[Name] the Unmaker"        │
│   Unmaker AA: 100% XP rate, full Unmaker gear + group aura    │
├────────────────────────────────────────────────────────────────┤
│ EXPERIENCE-BASED LORE LAYER                                     │
│   Action screenshots: capture → process to memory → delete     │
│   Interaction-triggered recall: history only on re-encounter   │
│   Collective lore: shared through social interaction only      │
│   Lore fidelity degrades with each retelling between agents    │
├────────────────────────────────────────────────────────────────┤
│ HEROIC PERSONA & VOICE LAYER                                    │
│   Noble devotion hierarchy: deity → faction → survival → gain  │
│   Heroic archetypes: selfless cleric, cunning rogue, etc.     │
│   Text-to-speech voice profiles per race/class archetype       │
│   Streaming agents: first-person perspective broadcast         │
│   AI social experiment: observable across server cycles        │
├────────────────────────────────────────────────────────────────┤
│ DEATH STATE                                                     │
│   Alive/dead status, death cause, killer identity               │
│   Betrayal flag — sole exception to permadeath                  │
│   Resurrectable only if betrayed by ally/faction member         │
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
Gates check: faction standing threshold, individual standing, duel cooldown, aggression limit
    │
    ▼
Action: assist, challenge to duel, trade, or ignore (never verbal — actions only)
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

### 3.4 Perception-Inference-Action Pipeline

The recall engine feeds into a **rapid perception-inference-action pipeline** that drives real-time agent decision-making. This pipeline mirrors classic EQ bot macro patterns — reading game state, evaluating against the soul document, and executing actions.

**Pipeline flow:**
1. **Perception** (~250ms tick): scan game state — nearby entities, HP/mana bars, buffs, combat state, zone context
2. **Inference**: compare perception frame against play-style template, soul document (who do I know? who do I like?), macro-trigger table (which behavior pattern matches?), and lore knowledge
3. **Action**: write the selected action to short-term memory, execute via game connector, promote significant events to long-term archive

**Macro-trigger patterns** modeled on classic bot commands (`/assist`, `/follow`, `/attack`, `/cast`, `/backoff`) determine the agent's routine combat behavior — the LLM is only invoked for complex social or strategic decisions, keeping the pipeline fast enough for real-time combat.

### 3.5 Lore-Seeded Memory

Agent soul documents are **pre-populated from EQ canonical lore** at creation time. Every existing EverQuest NPC, named mob, and raid boss in the EQEmu database serves as a foundation for agent identity, faction alignment, zone knowledge, and relationships.

**Lore seeding includes:**
- **Identity**: name, faction, zone, level, and relationships pulled from EQEmu NPC data
- **Zone knowledge**: agents "know" their home zone from birth — pre-seeded in long-term archive
- **Faction relationships**: initialized from the canonical EQ faction table
- **Shared lore blocks**: universal story knowledge (e.g., The Sleeper's legend) injected into every agent's archive as a read-only section — all agents know the shared history of Norrath
- **Mob and raid boss data**: named mobs and raid bosses receive richer soul documents with deeper faction webs, combat knowledge, and leadership caste assignments

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

### 4.4 Individual Interaction-Based Faction

Beyond the global faction standings above, each agent maintains **individual reputation** with every player it has interacted with. This is stored per-agent in the soul document and can override global faction behavior.

**Individual standing tracks:**

| Data Point | Stored In | Effect |
|---|---|---|
| `interaction_count` | `encountered_players` | Total interactions with this player |
| `positive_interactions` | `encountered_players` | Count of help, heals, buffs, fair trades |
| `negative_interactions` | `encountered_players` | Count of attacks, theft, griefing, ally kills |
| `individual_standing` | `encountered_players` | Computed score: positive − (negative × 1.5) |
| `grudge_flag` | `encountered_players` | `true` if negative_interactions > 5 in rolling window |
| `friendship_flag` | `encountered_players` | `true` if positive_interactions > 10 in rolling window |

**Grudge mechanics:**
- Grudges are triggered when negative interactions exceed a threshold (5+ in a rolling time window)
- A grudge-holding agent will challenge the player to a duel on sight and refuse all positive interaction
- Grudges decay slowly over real time (configurable half-life, default: 7 days per point)
- Repeated negative interactions deepen the grudge and extend decay time

**Friendship mechanics:**
- Friendship builds through consistent positive interactions (10+ in a rolling window)
- A friendly agent will assist in combat, offer trades, and buff the player
- Friendship can override hostile global faction standing — a personally friendly agent helps despite faction wars
- Friendship decays moderately if not reinforced (default: 3 days per point)

### 4.5 Actions Speak — The Silence Rule

A core design principle: agents express themselves **exclusively through actions**, never through words.

**What agents cannot do:**
- Agents **cannot send chat messages** to players — no tells, no say, no shout, no OOC
- Agents **cannot use emote text** to express hostility or friendship
- Agents **cannot spam hate** or any form of verbal aggression
- Agents have **no dialogue system** — they do not talk

**How agents express themselves:**
- A **hostile agent** challenges to duel, refuses trades, walks away, or positions aggressively
- A **friendly agent** assists in combat, heals/buffs, offers favorable trades, follows the player
- A **neutral agent** ignores the player entirely
- A **grudge-holding agent** immediately challenges to duel when the player is seen, then ignores
- A **deeply friendly agent** actively seeks out the player across zones to assist

**Design intent:**
- Players must **observe agent behavior** to understand relationship status
- This creates emergent storytelling — "why does this NPC keep challenging me?" or "this cleric always heals me"
- No verbal communication prevents toxic NPC behavior and keeps the world immersive
- Agent feelings are a mystery the player solves through gameplay, not through reading text

### 4.6 Language Restriction — In-Game Languages Only

Agents inside the EQ experiment operate under a **strict language restriction**: they can only communicate in and understand **in-game languages and Common Tongue**. They have **no knowledge of programming languages, code, or real-world technical concepts**.

- The soul document `language_capability` field defines which languages the agent knows: Common Tongue + their racial language
- Agents **cannot produce code** in any form — no programming syntax, no script generation, no technical vocabulary
- Agents **cannot reference the real world** — they have no knowledge of anything outside the game world of Norrath
- This restriction is enforced by the **sandbox gateway** (eq_gateway) at the EQ isolation boundary
- Language restriction applies to all soul layers — memory, recall, knowledge, and faction interactions are all scoped to in-game concepts

### 4.7 Self-Preservation — Flee Behavior

Because agents live under **permadeath**, they treat their life as their **only life** and will flee when survival is threatened.

**Flee triggers:**
- **"Run" command** — any group member saying or signaling "run" causes the agent to flee
- **Healer death** — if the group's dedicated cleric dies, agents flee unless a hybrid healer (beastlord, druid, Sourcerior with pet heals) is sustaining the group
- **HP threshold** — agents evaluate flee at 20% HP when no healer is available
- **Group wipe momentum** — 3+ group member deaths in rapid succession triggers flee

**Flee exceptions:**
- Agents do not flee if a **hybrid healer** is keeping the group alive after the primary healer falls
- Town guards defending a siege fight to the death (they do not flee)

**Self-preservation behavior in soul:**
- Flee decisions are driven by the self-preservation layer in the soul document
- Agents that successfully flee retain their complete soul — memory, gear, faction standing
- Fleeing agents remember the encounter and hold grudges against entities that caused the wipe
- Sourcerior agents use **Liquify** (water pets, level 40+) for aggro drop + invisibility escape

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

## 6. Class Play-Style Templates

### 6.1 Immutable Class Guides

Each agent class archetype is governed by a **class play-style template** — an immutable, read-only reference document that defines how agents of that class should play. Templates are the "how to play this class" guide for agents and **never change** once defined.

**The template is fixed:**
- Defined once at server configuration time
- Shared across all agents of the same class archetype
- Read-only — agents consult the template but cannot modify it
- Ensures consistent, recognizable class behavior across all agents
- Individual agent variation comes from the soul document (personality, memory, faction) — not from the template

**Template contents:**

| Field | Description |
|---|---|
| `combat_rotation` | Priority-ordered list of abilities to use in combat |
| `positioning` | Where to stand relative to enemies and allies (front, back, range) |
| `target_selection` | How to pick combat targets (highest threat, lowest HP, marked) |
| `group_role` | Role in group content (tank, DPS, healer, CC) |
| `buff_priority` | Which buffs to maintain and in what order |
| `emergency_actions` | What to do when HP low, mana empty, or group wiping |
| `item_valuation` | Stats and items to prioritize for gear and duel loot |

---

## 7. Agent Permadeath

### 7.1 Permanent Death Rule

AI agents follow a **permadeath rule**: when an agent dies, it is **permanently dead**. The soul document is archived but the agent ceases to exist in the game world. It does not respawn, get replaced, or come back.

- All grudges, friendships, knowledge, and faction standing die with the agent
- Players who built relationships with the agent lose those relationships permanently
- Every agent encounter has real stakes — killing an agent has permanent consequences

### 7.2 Betrayal Exception

The **sole exception** to permadeath is **betrayal**. If an agent was killed through betrayal by an allied agent or faction member, the betrayed agent can be resurrected.

**Betrayal is defined as:**
- An agent killed by a member of its own faction
- An agent lured into a trap by a supposed ally
- An agent killed while under a ceasefire or truce agreement

**Resurrection mechanics:**
- A betrayed agent's soul document is flagged as `death_cause: "betrayal"` and `resurrectable: True`
- A faction leader NPC or high-standing player of the agent's faction can resurrect it
- Resurrected agents retain their **full soul document** — memory, grudges, knowledge — and gain a deep grudge against the betrayer
- This creates emergent revenge narratives: a betrayed agent returns and hunts its killer

---

## 8. Integration with Murphy System

### 8.1 Module Mapping

| Soul Layer | Murphy Module | Integration |
|---|---|---|
| Rosetta base | `inference_gate_engine.py` | Form schemas drive agent action selection |
| Class template | Server config (read-only) | Immutable class play-style guides |
| Identity | `avatar/persona_injector.py` | Personality traits injected from avatar system |
| Memory | `state_manager.py` | Rosetta state persistence for soul documents |
| Recall | RAG vector integration | Vector similarity search for memory recall |
| Faction | `governance_kernel.py` | Faction rules enforced as governance gates |
| Knowledge | `librarian/` | Item/entity knowledge stored and indexed |
| Death state | `state_manager.py` | Permadeath tracking and betrayal resurrection |
| Behavior | `avatar/behavioral_scoring_engine.py` | Behavior scoring and adjustment loops |
| Lifestyle | `state_manager.py` + `eq_game_connector.py` | Daily routines, job roles, trade skill tracking, skill degradation |
| Perception-Inference | `perception_pipeline.py` | Screen-scan → inference → action → mind-write cycle |
| Macro-Trigger | `macro_trigger_engine.py` | Classic bot behavior patterns (assist, follow, engage, heal, debuff) |
| Lore-Seed | `lore_seeder.py` | EQEmu NPC/mob/boss data import and soul document pre-population |
| Card Collection | `card_system.py` | Universal/god card tracking, world entropy, Unmaker conversion, server reboot |
| Spawner Registry | `spawner_registry.py` | Per-entity spawn tracking, unmade status, world decay %, 50% vote trigger |
| Experience Lore | `experience_lore.py` | Action screenshot memory cycle, interaction recall, collective lore propagation |
| NPC Card Effects | `npc_card_effects.py` | 4-tier card effect generation, soul-bound protector spawning, NPC horror reactions, AI player kill-on-sight |
| Agent Voice | `agent_voice.py` | Text-to-speech voice profiles per race/class, streaming agent voice output |
| Heroic Persona | `persona_injector.py` | Noble deity devotion, faction loyalty hierarchy, heroic archetypes |

### 8.2 Persistence Strategy

Soul documents are persisted through the existing Murphy persistence layer:

- **Hot state**: Redis cache for active agents (short-term memory, current context)
- **Warm state**: PostgreSQL for soul documents (identity, archive, faction, knowledge)
- **Cold state**: S3/file storage for very old archive entries past retention window
- **Vector index**: RAG vector store for memory recall similarity search

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
