# Experimental EverQuest Modification Plan

**Murphy System — Experimental Game Integration Plan**
**Version:** 3.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Codename:** Project Sourcerior

---

## 1. Executive Summary

This document defines the complete plan for an **experimental modification of EverQuest** powered by the Murphy System's multi-Rosetta soul architecture. The modification introduces Murphy-driven AI agents as in-game NPCs with persistent souls, a novel hybrid class called the **Sourcerior** (monk/mage hybrid — primarily a damage class with situational utility), integrated voice chat with raid-leader moderation, a faction-based agent warfare system, and a player-vs-agent duel-and-loot mechanic. The entire experience is designed to be **streamed live**.

The server is a **Planes of Power progression server** with leveling that mirrors the **original EverQuest experience** — same XP rates, hell levels, death penalties, and zone progression — built into the Planes of Power ending as the culmination of the journey. A universal **Remake System** allows any class that maxes out level, AA, and skills to "remake" with a 1% permanent increase in stat and skill caps, starting again slightly stronger.

AI agents operate as **pure melee**, **int caster**, or **cleric** archetypes, each governed by an **immutable class play-style template** that defines how to play the class. Agents follow **permadeath** — when they die, they are permanently gone unless killed through **betrayal** by an ally, in which case they can be resurrected. Each agent builds **individual faction** with players based on direct interactions — holding grudges when mistreated and becoming friendly when helped. Agents express themselves **only through actions** — they cannot respond verbally or spam hate text at players.

When **towns are conquered** through faction warfare, it is the **leadership and guards** that fight — civilian NPCs are non-combatants. Dead guards and leaders follow permadeath rules, and conquered towns change faction control.

NPCs live full daily lives through an **NPC lifestyle system**: they sleep, work jobs (smithing, merchant, brewing, guarding), and adventure when off-duty. Town buildings are owned by NPC characters — the smith who runs the forge is a real agent with a soul document, not a static game construct. NPCs follow a **caste system** (royals, nobles, commoners, dhampirs, servants) and their trade skills **degrade without practice** — one week of inactivity fades skill toward 50, while leveling up locks a permanent **skill floor** preventing full decay.

The agent soul system follows the **OpenClaw Molty soul.md** pattern (see `OPENCLAW_MOLTY_SOUL_CONCEPT.md`) where each agent's Rosetta state document acts as its persistent soul — driving memory, recall, faction loyalty, combat decisions, and social interactions.

---

## 2. Scope

### 2.1 Core Systems Required

| System | Description | Dependency |
|---|---|---|
| **Agent Soul Engine** | Memory/archive system for NPC agents with recall triggers | `inference_gate_engine.py`, Rosetta state layer |
| **AI Agent Classes** | Pure melee, int caster, and cleric archetypes for agents | Soul engine, class ability tables |
| **Class Play-Style Templates** | Immutable how-to-play guides for each agent class archetype | Soul engine, server config |
| **Agent Permadeath** | Permanent death for agents — no respawn unless betrayed by ally | Soul engine, death state tracking |
| **Town Conquest** | Leadership and guards defend towns in faction warfare sieges | Faction system, permadeath, agent spawning |
| **Sourcerior Class** | Monk/mage hybrid — primarily damage with situational utility | Game client modification, spell/ability tables |
| **Voice Chat Integration** | Group/raid toggle voice with admin moderation | WebRTC or Mumble protocol, Murphy admin controls |
| **Faction Soul System** | Agent-to-agent warfare driven by faction standings | Soul engine, faction DB, event backbone |
| **Individual Agent Faction** | Per-agent interaction-based reputation with players | Soul engine, interaction tracker |
| **Duel & Loot System** | Player-vs-agent 1v1 duels with single-item loot stakes | Combat engine, inventory hooks, inspect gates |
| **Streaming Pipeline** | Live-stream-ready overlay and event capture | OBS integration, event telemetry |
| **Raid Leader Admin** | Murphy-powered raid leader moderation tools | Voice chat system, governance kernel |
| **Progression Server** | Original EQ leveling experience built into Planes of Power ending | EQEmu server configuration |
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

### 3.6 Class Play-Style Templates — Immutable Agent Guides

Each agent class archetype is governed by a **class play-style template** — a fixed, immutable reference document that defines how agents of that class should play. Templates act as the agent's "how to play this class" guide and **never change** once defined. They are embedded in the soul architecture as a read-only layer.

**Template structure:**

| Template Section | Purpose |
|---|---|
| **Combat rotation** | Priority list of abilities to use in combat (e.g., taunt → bash → melee for Pure Melee) |
| **Positioning** | Where the agent should stand relative to enemies and allies (front/back/range) |
| **Target selection** | How the agent picks targets (lowest HP, highest threat, marked target) |
| **Group role** | What the agent's job is in a group (tank, DPS, healer, CC) |
| **Buff priority** | Which buffs to maintain and in what order |
| **Emergency actions** | What to do when HP is low, mana is empty, or group is wiping |
| **Item valuation** | Which stats and items the agent prioritizes for gear upgrades and duel loot |

**Immutability rule:**
- Class play-style templates are **fixed at server definition time** and do not change
- The template is a read-only reference — agents consult it but cannot modify it
- All agents of the same class archetype share the same template
- Individual agent variation comes from the **soul document** (personality, memory, faction) — not from the template
- Templates ensure consistent, recognizable class behavior: a Pure Melee always tanks like a warrior, an Int Caster always positions at range, a Cleric always prioritizes healing

```python
# Class play-style template (immutable — never changes)
class_template = {
    "archetype": "pure_melee",
    "immutable": True,
    "combat_rotation": ["taunt", "bash", "kick", "melee", "riposte"],
    "positioning": "front_line",
    "target_selection": "highest_threat_to_group",
    "group_role": "tank_dps",
    "buff_priority": ["haste", "strength", "ac"],
    "emergency_actions": ["defensive_disc", "flee_at_10pct_hp", "bandage"],
    "item_valuation": {"priority": ["ac", "hp", "str", "sta"]},
}
```

### 3.7 Agent Permadeath — Permanent Death and Betrayal Exception

AI agents follow a **permadeath rule**: when an agent dies, it is **permanently dead** and does not respawn. The agent's soul document is archived but the agent ceases to exist in the world. This creates real stakes for agent–agent warfare, town defense, and player interactions.

**Permadeath mechanics:**
- When an agent's HP reaches zero, the agent **dies permanently**
- The soul document is moved to a **dead archive** — preserved for historical reference but no longer active
- The agent does not respawn, re-enter the world, or get replaced by a copy
- All grudges, friendships, knowledge, and faction standing die with the agent
- Players who built relationships with that agent lose those relationships permanently
- This makes every agent encounter meaningful — killing an agent has permanent consequences

**Betrayal exception — the only path back:**
- The **sole exception** to permadeath is **betrayal**: if an agent was killed through betrayal by an allied agent or faction member, the betrayed agent can be **resurrected**
- Betrayal is defined as: an agent killed by a member of its own faction, an agent that was lured into a trap by a supposed ally, or an agent killed while under a ceasefire/truce
- A betrayed agent's soul document is flagged as `death_cause: "betrayal"` instead of archived
- Betrayed agents can be resurrected by a faction leader NPC or a high-standing player of the agent's faction
- Resurrected agents retain their full soul document — memory, grudges, knowledge — and gain a **deep grudge** against the betrayer
- This creates emergent revenge narratives: a betrayed agent comes back and hunts its killer

**Death tracking in soul document:**

```python
agent_soul["death_state"] = {
    "alive": False,
    "death_cause": "combat",        # "combat", "betrayal", "town_siege"
    "killer_id": "agent_4821",
    "death_zone": "West Commonlands",
    "death_timestamp": "2026-04-15T14:22:00Z",
    "betrayal_flag": False,          # True if killed by ally/faction member
    "resurrectable": False,          # True only when betrayal_flag is True
    "resurrection_count": 0,
}
```

### 3.8 Town Conquest — Leadership and Guards

When a **town or city is conquered** through faction warfare, it is the **town leadership and guards** that fight to defend it — not the general population. Town conquest is a structured event, not a massacre.

**Town defense structure:**

| Defender Role | Description |
|---|---|
| **Town Leader** | The highest-ranking agent NPC in the town — faction leader, mayor, or guildmaster. Fights last, retreats if overwhelmed |
| **Guard Captain** | Commands the guard force. Coordinates defense positioning and rallies guards |
| **Town Guards** | Standing military force of the town. These are the primary combatants in a siege |
| **Elite Guards** | Stronger named guard agents with full soul documents — permadeath applies |
| **Civilian NPCs** | Non-combatants — NPC characters who fill job roles (smiths, merchants, brewers, tailors — see section 3.11). They **do not fight** and are not targeted |

**Conquest mechanics:**
- Faction warfare can escalate to **town sieges** when one faction's agents amass enough force near an enemy town
- Only **leadership and guards** engage in combat during a siege — civilian NPCs are non-combatants
- Guards follow permadeath rules — dead guards do not respawn automatically
- If all guards and leadership are defeated, the town **changes faction control**
- The conquering faction installs its own leadership and guards (new agents with new soul documents)
- Conquered town services (merchants, trainers) continue operating under new management
- Players aligned with the conquered faction lose access to town services until faction is restored
- Town reconquest is possible — the defeated faction can rally agents to retake the town

**Leadership agents:**
- Town leaders and guard captains are **named agents with full soul documents** — they have memory, grudges, and individual faction standing
- Killing a beloved town leader creates lasting grudges across the entire defending faction
- Town leaders who survive a siege remember the attackers and hold deep grudges

### 3.9 Agent Language Restriction — In-Game Languages Only

Agents inside the EverQuest experiment are **restricted to in-game languages and Common Tongue only**. They have **no knowledge of programming languages, code syntax, or any real-world technical vocabulary**. This is enforced at the soul layer to keep the experiment immersive and tightly contained.

**What agents can use:**
- **Common Tongue** — the universal trade language all races understand
- **Racial languages** — Elvish, Dark Speech, Gnomish, Ogre, Troll, etc. as defined by their race
- **Faction-specific dialects** — where applicable, aligned with cultural identity templates

**What agents cannot do:**
- Agents **cannot produce or interpret code** — no programming language knowledge exists in their soul
- Agents **cannot reference real-world concepts** — no awareness of anything outside Norrath
- Agents **cannot break the fourth wall** — they have no knowledge of being AI agents in a game
- Agent language capability is defined in the soul document `language_capability` field and is **enforced by the isolation boundary** (see section 16)

### 3.10 Agent Self-Preservation — Flee Behavior

Agents treat their life as if it is **their only life** (because it is — permadeath is real). This self-preservation instinct drives flee behavior under specific conditions.

**Flee triggers:**
- **"Run" command** — if any group member (player or agent) says or signals "run", the agent flees immediately
- **Healer death** — if the group's dedicated healer (cleric archetype) dies, agents flee unless a **hybrid healer** (e.g., a Sourcerior with pet heals, a beastlord, or a druid) is still alive and actively sustaining the group
- **HP threshold** — agents begin evaluating flee at 20% HP if no healer is available
- **Group wipe momentum** — if 3+ group members die in rapid succession, surviving agents flee

**Flee exceptions:**
- Agents **do not flee** if a hybrid healer is keeping the group alive after the primary healer falls
- Town guards defending a siege **do not flee** (they fight to the death to protect their town)
- Agents under the influence of a fear spell flee regardless (overrides self-preservation logic)

**Flee behavior:**
- Fleeing agents attempt to run to the nearest zone line or safe area
- Sourceriors with **Liquify** active (water pets, level 40+) can use aggro drop + invisibility to escape cleanly (see `SOURCERIOR_CLASS_DESIGN.md` section 2.12)
- Fleeing agents remember the encounter and hold **grudges** against entities that caused the wipe
- An agent that successfully flees retains its full soul document — memory, gear, and faction standing intact

### 3.11 NPC Lifestyle System — Daily Routines, Jobs, and Skill Degradation

AI agents are not static quest givers or permanent merchants — they are **living characters** with daily routines, jobs, sleep cycles, and trade skills that degrade when not practiced. Instead of traditional EverQuest merchants standing in place forever, NPCs fill those roles as **characters who work those jobs** and then adventure when off-duty.

#### 3.11.1 Daily Routine Cycle

Every NPC agent follows a **daily routine** tied to the game world's day/night cycle:

| Phase | Duration | Activity |
|---|---|---|
| **Sleep** | ~6 game hours | Agent returns to their residence and sleeps — unavailable for interaction |
| **Work Shift** | ~10 game hours | Agent performs their assigned job role (smithing, selling, guarding, etc.) |
| **Adventure / Free Time** | ~8 game hours | Agent groups up, hunts, explores, or socializes — behaves like a player |

- NPCs **sleep in residences** — some own their home, others rent rooms or bunk in faction halls
- During sleep, agents are physically present in their bed location but do not respond to interaction
- Work and adventure schedules vary by personality — a dedicated smith may work 14-hour shifts, while a restless warrior adventures more

#### 3.11.2 Building Ownership and Job Roles

Town buildings (shops, forges, taverns) are **owned by NPC characters** — not abstract game constructs. The NPC who works the forge owns or leases the building, and their trade skill determines the quality of what they can produce or sell.

**Job roles:**

| Job Role | Description | Primary Skill |
|---|---|---|
| **Smith** | Forges weapons and armor; repairs gear for players and agents | Blacksmithing |
| **Merchant** | Buys and sells goods; manages shop inventory | Bartering / Trading |
| **Brewer** | Crafts potions, ales, and consumables | Brewing |
| **Tailor** | Crafts cloth and leather armor, bags, and containers | Tailoring |
| **Jeweler** | Crafts jewelry and enchanted trinkets | Jewelcrafting |
| **Baker** | Produces food items for stat buffs and sustenance | Baking |
| **Fletcher** | Crafts bows, arrows, and ranged ammunition | Fletching |
| **Guard** | Patrols and defends the town — combat-focused job | Combat skills |
| **Scholar** | Researches spells, scribes scrolls, and maintains libraries | Research |

- When an NPC is **on shift**, they are at their workplace performing their job — a smith is at the forge, a merchant is behind the counter
- When **off shift**, the NPC may adventure, group with players, or pursue personal goals
- If the NPC who runs a shop **dies** (permadeath), that shop goes vacant until another NPC or the faction assigns a replacement
- Building ownership is tracked in the soul document — an NPC knows they own or lease their workspace

#### 3.11.3 Caste System — Vampire Academy Class Hierarchy

NPC society follows a structured **caste system** inspired by class-hierarchy fiction (similar to *Vampire Academy*). Each NPC's caste determines their social standing, job access, and behavioral expectations within their faction:

| Caste | Role | Social Standing | Mobility |
|---|---|---|---|
| **Royals** | Faction leaders, town rulers, high priests | Highest — command authority and deference | Fixed — born or appointed |
| **Nobles** | Elite guards, master craftsmen, senior merchants | High — manage resources and direct workers | Earned through achievement or lineage |
| **Commoners** | Standard workers, guards, journeyman crafters | Middle — the productive backbone of society | Can advance to Noble through skill mastery or heroic deeds |
| **Dhampirs** | Adventurer-workers — split between combat duty and trade jobs | Flexible — respected for versatility but not elite | Can rise through combat achievement or craft mastery |
| **Servants** | Apprentices, laborers, new arrivals to a faction | Lowest — learning and proving themselves | Advance to Commoner after demonstrating competence |

- Caste is assigned at soul creation based on the agent's faction, level, and skill profile
- **Advancement is possible**: a Servant who masters a trade skill can become a Commoner; a Commoner who achieves Noble-tier skill mastery or performs heroic acts in faction warfare can be elevated
- **Caste affects behavior**: Royals expect deference, Nobles manage shops and guards, Commoners work steadily, Dhampirs split time between jobs and adventure, Servants defer to all others
- Caste is stored in the soul document `lifestyle.caste` field

#### 3.11.4 Trade Skill Specialization and Mastery

AI NPCs can achieve **maximum skill level** in their primary trade — unlike players who spread skill points across many trades, NPCs specialize deeply. A dedicated smith NPC can reach max Blacksmithing and produce the highest-quality items.

**Specialization rules:**
- Each NPC has a **primary trade skill** determined by their job role
- NPCs can achieve **skill cap (300 at level 60)** in their primary trade through consistent practice
- An NPC actively working their trade skill during work shifts gains skill points at an accelerated rate
- NPCs may have **secondary skills** at lower proficiency, but their primary trade is always strongest

#### 3.11.5 Skill Degradation — Use It or Lose It

Trade skills **degrade over time** when not actively practiced. An NPC who stops working their trade will see their skill level fade back toward a baseline.

**Degradation formula:**
- **Active practice** (1 week of regular work shifts): skill remains at current level or increases
- **No practice** (1 week without performing the skill): skill degrades toward **50** (the untrained baseline)
- Degradation rate: approximately **equal time to build, equal time to decay** — one week of working followed by one week of not working brings the skill back to 50
- Degradation is **linear**: each day without practice reduces the skill by `(current_skill - skill_floor) / 7` points

**Example degradation timeline (skill 300, no practice, no level floor):**

| Day | Skill Level | Notes |
|---|---|---|
| 0 | 300 | Last day of active practice |
| 1 | ~264 | First day of degradation |
| 3 | ~193 | Noticeable decline |
| 5 | ~121 | Approaching baseline |
| 7 | 50 | Reached untrained baseline |

#### 3.11.6 Level-Based Skill Floor — Leveling Locks Minimum Thresholds

When an NPC **levels up**, it permanently locks a **minimum skill floor** for their primary trade skill. This floor prevents degradation from dropping the skill below a certain point, rewarding the NPC's growth with lasting competence.

**Skill floor formula:**
- `skill_floor = (agent_level / max_level) × skill_cap × 0.8`
- At max level (60), the floor is **80% of skill cap** (240 out of 300) — a max-level master smith can never degrade below 240
- At level 30, the floor is ~120 — a mid-level smith degrades to 120 at worst, not 50
- At level 1, the floor is effectively 4 — almost no protection

**Skill floor by level (skill cap 300):**

| Level | Skill Floor | Max Possible | Degradation Range |
|---|---|---|---|
| 1 | 4 | 5 | 4–5 (negligible) |
| 10 | 40 | 50 | 40–50 |
| 20 | 80 | 100 | 80–100 |
| 30 | 120 | 150 | 120–150 |
| 40 | 160 | 200 | 160–200 |
| 50 | 200 | 250 | 200–250 |
| 60 | 240 | 300 | 240–300 |

- The skill floor is stored in the soul document `lifestyle.skill_floor` field
- Leveling up always recalculates the floor — it only ever increases
- This creates a **meaningful progression**: a high-level smith who takes a week off adventuring only loses a fraction of their skill, while a low-level apprentice quickly loses what little they had

---

## 4. Progression Server — Planes of Power

### 4.1 Era Cap

The experimental server is a **Planes of Power progression server**:

- Content progresses through Classic → Kunark → Velious → Luclin → Planes of Power
- **Planes of Power is the final expansion** — no further content unlocks
- Level cap: **65** (PoP era)
- AA cap: All AAs available through PoP era
- All content and itemization designed around PoP-era balance

### 4.2 Original EverQuest Leveling Experience

The leveling experience is designed to **mirror the original EverQuest progression** — the same pacing, difficulty, and zone flow that defined the classic game. This is not a fast-track or accelerated server. Players and agents experience the full journey from level 1 to 65 as it was originally intended, built into the Planes of Power ending.

**Original experience philosophy:**
- **XP rates match original EQ** — leveling should feel like the original game, not a modern fast-pass
- **Hell levels preserved** — the notoriously difficult leveling stretches (44, 51, 54, 59) are intact
- **Zone progression follows classic paths** — Crushbone → Unrest → Mistmoore → SolB → Lower Guk → Plane of Fear/Hate → Kunark dungeons → Velious → Luclin → PoP
- **Group-dependent gameplay** — soloing is slow and dangerous past the teens; grouping is the intended path
- **Death penalty intact** — corpse runs, XP loss on death, and the fear of dying are core to the experience
- **No instances** (Classic–Velious) — open-world contested content with camp competition, just like original EQ
- **Planes of Power as the capstone** — the entire leveling journey builds toward Planar progression and the Plane of Time as the ultimate achievement

**Leveling milestones (matching original EQ pacing):**

| Level Range | Typical Zones | Time Investment | Key Milestones |
|---|---|---|---|
| **1–10** | Starting cities, newbie yards, local dungeons | 4–8 hours | Learn class basics, first group experiences |
| **11–20** | Crushbone, Befallen, Blackburrow, Unrest | 15–25 hours | First dungeon crawls, group roles solidify |
| **21–30** | Mistmoore, Upper/Lower Guk, Highpass | 25–40 hours | Class identity defined, key abilities unlock |
| **31–40** | Solusek B, Permafrost, Cazic-Thule | 40–60 hours | Hell levels begin, grouping essential |
| **41–50** | Plane of Fear/Hate, Kedge Keep, Old Sebilis | 60–100 hours | First planar content, epic quests begin |
| **51–60** | Kunark/Velious raid zones, Temple of Veeshan | 100–160 hours | Raid progression, AA accumulation begins |
| **61–65** | Luclin/PoP zones, Planar progression | 80–120 hours | Plane of Time flagging, final AA push |

**Built into the Planes of Power ending:**
- The entire progression arc — from level 1 in a starting city to level 65 in the Plane of Time — tells a complete story
- Planes of Power is not just an expansion unlock; it is the **culmination** of the leveling journey
- Planar progression (Plane of Justice → Plane of Valor → Plane of Storms → Plane of Tactics → Plane of Time) is the endgame
- Characters who reach Plane of Time and complete the final encounter have **finished the journey** and can enter the Remake System
- The experience is designed so that reaching the end of PoP feels like a genuine achievement, not an inevitability

### 4.3 Progression Unlock Schedule

| Era | Level Cap | Key Content | Duration |
|---|---|---|---|
| **Classic** | 50 | Original zones, planes, epic 1.0 quests | 8 weeks |
| **Kunark** | 60 | Kunark zones, Veeshan's Peak, epic completion | 8 weeks |
| **Velious** | 60 | Velious zones, Temple of Veeshan, Sleeper's Tomb | 8 weeks |
| **Luclin** | 65 | Luclin zones, Vex Thal, AAs introduced | 8 weeks |
| **Planes of Power** | 65 | Planar progression, Plane of Time, full AA | Permanent |

### 4.4 Sourcerior in Progression

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

The Sourcerior is a **monk/mage hybrid** — **primarily a damage class** with a wide range of **situational utility** and a unique **avoidance tanking** capability. The class favors proc-based damage over direct-cast nukes, summons up to 6 elementals of four types (earth, air, fire, water), and provides group utility through **bard proc line** effects. The Sourcerior can **meld with pets** for elemental aspect buffs, and wields a **two-handed staff** as its core weapon.

**Eligible races:** Dark Elf, Erudite, Human, High Elf, Gnome (int caster races).

The Sourcerior has **higher proc modifiers than any other class** — the slower the weapon, the better. **Discipline of Rumblecrush** enables emergency avoidance tanking for the same duration as a warrior's **Defensive Discipline** (~180s), with pets gaining Defensive-like mitigation. This burns mana per proc, making **beastlord** mana sustain essential.

The **single-element rule** restricts pet groups to one element at a time unless the Sourcerior acquires **Lord of the Maelstrom** — a level 60 raid drop from the final Plane of Sky boss that permanently lifts the restriction.

### 6.2 Core Mechanics Summary

| Mechanic | Description |
|---|---|
| **Melee Foundation** | Monk-style hand-to-hand and kick skills as primary combat |
| **Fire Procs** | AE fire damage + AC/damage shield on melee hits |
| **Earth Procs** | Root targets + runes (damage absorption) on melee hits |
| **Bard Proc Line** | Overhaste, ATK, AC, pet heal procs from bard spell lines — weaker than bard equivalents |
| **Pet System** | Up to 6 elementals; single element at a time (unless Lord of the Maelstrom) |
| **Invoke Pet / Meld** | Absorb a pet to gain its elemental aspect (HP+taunt, backstab, DS+burn, crit magic) |
| **Flame Blink** | Forward blink replaces feign death — releases elementals that root and taunt |
| **AE Mez** | Minor enchanter-category AE mesmerize spells |
| **Sacrifice Pets** | Consumes pets for a nuke — mobility ability for movement phases |
| **Discipline of Rumblecrush** | Tanking disc (~180s, same as warrior Defensive); pets gain Defensive-like buff; procs cost mana |
| **Lord of the Maelstrom** | Level 60 raid drop (Plane of Sky); permanently allows mixed-element pets |
| **Liquify** | Aggro drop + invisibility when water pets are active (level 40+) |
| **Epic Weapon** | Very slow 2H staff with heavy base DMG — amplifies meld effectiveness |

### 6.3 Scaling Philosophy

The Sourcerior scales between monk and mage power curves:
- At low levels, plays mostly as a monk with minor pet summons
- At mid levels, proc effects become meaningful and pet count increases
- At high levels, the full 6-pet army with proc-based AE DPS and meld cycling is online
- Bard proc lines of equivalent level should always be **stronger** than Sourcerior procs
- The value is in the combination: melee DPS + pet DPS + meld aspects + proc utility
- **Two-handed staves** are the core weapon — high base damage maximizes proc and meld scaling
- Can also dual wield **1H slashing** and **1H piercing** weapons (no 1H blunt)
- Can wear **cloth and leather** armor, plus the **Fungi Tunic** for regeneration synergy

---

## 7. Race Cultural Identity System

> Full design specification: `RACE_CULTURAL_IDENTITY_DESIGN.md`

### 7.1 Overview

Every playable race is assigned a **cultural identity** inspired by a real-world civilization. These cultural mappings shape AI agent personality, faction behavior, quest themes, and social dynamics. Cultural identities are layered on top of existing EQ faction alignments — they provide motivation for existing relationships, not replacements.

### 7.2 Race–Culture Summary

| Race | Cultural Inspiration | Key Values |
|---|---|---|
| **Gnome** | Spartan–Roman (Ancient Greece / Rome) | Military discipline, communal duty, honor in combat, Roman-style conquest and territorial expansion |
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
    },
    "lifestyle": {
        "caste": "str",  # royal, noble, commoner, dhampir, servant
        "job_role": "str",  # smith, merchant, brewer, guard, scholar, etc.
        "workplace": {"building_id": "str", "ownership": "str"},  # own, lease, assigned
        "residence": {"building_id": "str", "type": "str"},  # home, bunk, inn
        "schedule": {
            "sleep_start": "int",  # game hour (0–23)
            "work_start": "int",
            "adventure_start": "int"
        },
        "primary_trade_skill": {
            "skill_name": "str",
            "current_level": "int",  # 0–300
            "skill_floor": "int",  # level-locked minimum
            "last_practiced": "iso8601",
            "degradation_rate": "float"  # points per day without practice
        },
        "secondary_skills": [{"skill_name": "str", "current_level": "int"}]
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
- [ ] Configure original EQ XP rates and leveling curve (hell levels, death penalty, corpse runs)
- [ ] Implement soul engine with memory/archive/recall
- [ ] Create Sourcerior class in spell/ability tables
- [ ] Configure Sourcerior eligible races (Dark Elf, Erudite, Human, High Elf, Gnome)
- [ ] Configure Sourcerior armor restrictions (cloth, leather, Fungi Tunic)
- [ ] Implement AI agent class archetypes (pure melee, int caster, cleric)
- [ ] Define immutable class play-style templates for each agent archetype
- [ ] Basic agent spawning with soul documents
- [ ] Define race cultural identity templates for persona injector
- [ ] Implement EQ isolation boundary and sandbox gateway (eq_gateway module)
- [ ] Configure agent language restriction (in-game languages + Common Tongue only; no code capability)

### Phase 2: Combat & Class (Weeks 5–8)

- [ ] Implement Sourcerior abilities (procs, pets, flame blink, sacrifice)
- [ ] Implement Invoke Pet / Meld system (earth, air, fire, water aspects)
- [ ] Implement AE mez spells from enchanter category
- [ ] Implement bard proc line system (overhaste, ATK, AC, pet heal — weaker than bard equivalents)
- [ ] Balance pet scaling (6 pets, four elements, low HP, decent damage)
- [ ] Implement single-element pet rule (one element at a time; dismiss all on element switch)
- [ ] Implement Discipline of Rumblecrush (tanking disc — pets gain Defensive-like buff; procs cost mana)
- [ ] Implement Lord of the Maelstrom discipline (level 60 raid drop — lifts single-element restriction)
- [ ] Implement weapon restrictions (1H slashing, 1H piercing, staves only — no 1H blunt)
- [ ] Implement two-handed staff weapon class and epic quest framework
- [ ] Implement Sourcerior Liquify ability (aggro drop + invis with water pets, level 40+)
- [ ] Implement agent permadeath system (death archival, soul removal)
- [ ] Implement betrayal detection and resurrection exception

### Phase 3: Social Systems (Weeks 9–12)

- [ ] Implement faction soul functions and agent warfare
- [ ] Implement individual agent faction with interaction-based reputation
- [ ] Implement grudge and friendship mechanics in soul documents
- [ ] Implement actions-only expression rule (no verbal agent responses)
- [ ] Implement agent self-preservation and flee behavior (flee on "run" command, healer death, group wipe)
- [ ] Implement flee exception for hybrid healer sustain (beastlord, druid, Sourcerior pet heals)
- [ ] Implement duel challenge and loot system
- [ ] Implement inspect asymmetry (agent knowledge base gating)
- [ ] Implement town conquest system (leadership and guards as defenders)
- [ ] Voice chat integration with group/raid toggles
- [ ] Implement NPC daily routine system (sleep, work, adventure cycles)
- [ ] Implement building ownership and job role assignment for NPCs
- [ ] Implement caste system hierarchy (royal, noble, commoner, dhampir, servant) with advancement
- [ ] Implement trade skill specialization with max-skill mastery for NPC primary trades
- [ ] Implement skill degradation system (1 week no practice → fade to baseline 50)
- [ ] Implement level-based skill floor (leveling locks minimum skill thresholds)

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
| **Agent population decline** | Permadeath depopulates zones over time | Controlled new agent spawning to replace dead agents; betrayal resurrection as natural recovery |
| **Town conquest imbalance** | One faction dominates all towns | Faction strength balancing, cooldowns on consecutive sieges, rally mechanics for defeated factions |
| **EQ isolation breach** | Agent knowledge leaks beyond game boundary | Isolation boundary enforcement, sandbox gateway, language restriction in soul docs |
| **Skill degradation balance** | Trade skills degrade too fast or slow, making NPC economy unstable | Tunable degradation rate, level-based skill floors lock minimum competence, monitoring dashboards |

---

## 16. EQ Isolation Boundary — Experiment Gating

The EverQuest experiment is a **sandboxed environment** that must remain tightly separated from the rest of the Murphy System. Agents operating inside the EQ world exist in a constrained state: they have no awareness of the outside system, no ability to produce code, and no access to modules or data beyond their game world context.

### 16.1 Isolation Principles

| Principle | Description |
|---|---|
| **Sandbox boundary** | The EQ experiment runs inside a dedicated sandbox. No agent soul, memory, or recall data crosses the boundary into the broader Murphy System without explicit gateway approval |
| **No code capability** | Agents inside EQ have **zero knowledge of programming languages**. Their soul documents contain no code generation prompts, no technical vocabulary, and no awareness of software concepts |
| **In-game languages only** | Agents are restricted to Common Tongue and racial/faction languages defined within the game world (see section 3.9) |
| **No fourth-wall awareness** | Agents do not know they are AI. They treat the EQ world as their complete reality, their life as their only life, and their death as permanent |
| **One-way data flow** | The Murphy System can observe and manage EQ agents (spawning, monitoring, logging), but EQ agents cannot query, influence, or access any Murphy module outside the game boundary |

### 16.2 Sandbox Gateway

All communication between the EQ experiment and the Murphy System passes through a **sandbox gateway** — a controlled interface that enforces isolation:

```
┌──────────────────────────────────────────────────────────────────┐
│ Murphy System (core)                                              │
│   inference_gate_engine, state_manager, governance_kernel,        │
│   avatar, librarian, behavioral_scoring_engine                    │
├──────────────────────┬───────────────────────────────────────────┤
│                      │                                            │
│              ┌───────┴────────┐                                   │
│              │ SANDBOX GATEWAY │ ← enforces isolation rules       │
│              │  (eq_gateway)   │ ← language filter, code filter   │
│              └───────┬────────┘                                   │
│                      │                                            │
├──────────────────────┴───────────────────────────────────────────┤
│ EQ Experiment (sandboxed)                                         │
│   soul_engine, faction_manager, duel_controller,                  │
│   eq_game_connector, voice_bridge, stream_overlay                 │
│   ── agents operate here with in-game knowledge only ──           │
└──────────────────────────────────────────────────────────────────┘
```

### 16.3 Enforcement Rules

- The `eq_gateway` module validates all data crossing the boundary
- Agent soul documents include a `language_capability` field listing only in-game languages — the gateway rejects any content containing code syntax or real-world technical terms
- Agent recall queries are scoped to the EQ vector index only — no cross-system memory search
- Murphy admin tools (raid leader, HITL override) operate **through** the gateway, not around it
- Logging and telemetry flow **outward** from EQ to Murphy for monitoring, but no Murphy core data flows **inward** to agents
- The sandbox gateway is listed as a dependency in the Murphy System Extensions table (section 11.3)

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
