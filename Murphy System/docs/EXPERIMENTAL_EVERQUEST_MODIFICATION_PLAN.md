# Experimental EverQuest Modification Plan

**Murphy System — Experimental Game Integration Plan**
**Version:** 3.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Codename:** Project Sorceror

---

## 1. Executive Summary

This document defines the complete plan for an **experimental modification of EverQuest** powered by the Murphy System's multi-Rosetta soul architecture. The modification introduces Murphy-driven AI agents as in-game NPCs with persistent souls, a novel hybrid class called the **Sorceror** (monk/mage hybrid — primarily a damage class with situational utility), integrated voice chat with raid-leader moderation, a faction-based agent warfare system, and a player-vs-agent duel-and-loot mechanic. The entire experience is designed to be **streamed live**.

The server is a **Planes of Power progression server** with leveling that mirrors the **original EverQuest experience** — same XP rates, hell levels, death penalties, and zone progression — built into the Planes of Power ending as the culmination of the journey. A universal **Remake System** allows any class that maxes out level, AA, and skills to "remake" with a 1% permanent increase in stat and skill caps, starting again slightly stronger.

AI agents operate as **pure melee**, **int caster**, or **cleric** archetypes, each governed by an **immutable class play-style template** that defines how to play the class. Agents follow **permadeath** — when they die, they are permanently gone unless killed through **betrayal** by an ally, in which case they can be resurrected. Each agent builds **individual faction** with players based on direct interactions — holding grudges when mistreated and becoming friendly when helped. Agents express themselves **only through actions** — they cannot respond verbally or spam hate text at players.

When **towns are conquered** through faction warfare, it is the **leadership and guards** that fight — civilian NPCs are non-combatants. Dead guards and leaders follow permadeath rules, and conquered towns change faction control.

NPCs live full daily lives through an **NPC lifestyle system**: they sleep, work jobs (smithing, merchant, brewing, guarding), and adventure when off-duty. Town buildings are owned by NPC characters — the smith who runs the forge is a real agent with a soul document, not a static game construct. NPCs follow a **caste system** (royals, nobles, commoners, dhampirs, servants) and their trade skills **degrade without practice** — one week of inactivity fades skill toward 50, while leveling up locks a permanent **skill floor** preventing full decay.

The agent soul system is implemented in `src/eq/soul_engine.py`, where each agent's Rosetta state document acts as its persistent soul — driving memory, recall, faction loyalty, combat decisions, and social interactions.

Agent behavior is powered by a **macro-trigger system** modeled on classic EQ bot patterns (`/assist`, `/follow`, `/attack`, `/cast`) and a **rapid perception-inference-action pipeline** that scans game state every ~250ms, evaluates against the soul document, and writes decisions back to the agent's mind. All agent souls are **lore-seeded** from the EQEmu NPC database — every existing NPC, mob, and raid boss serves as a foundation for agent identity. **The Sleeper (Kerafyrm)** operates as a world-event agent restricted to level 60+ zones, with its storyline pre-seeded in all character memories. Awakening The Sleeper triggers **dragon /tell coordination** across factions, with hostile dragon factions temporarily cooperating to stop the raid unless already engaged elsewhere.

A **God Card system** adds endgame progression through deity encounters — gods drop collectible cards that unlock alternate advancement abilities (skill, buff, enchantment) with the ultimate reward of a **Card of Unmaking** that grants a void spell capable of permanently deleting any entity. Players who unmake a god gain that god's title and become **PvP raid bosses**. Gods can also plot against each other using cards. **The Unmaker**, a level-1 NPC with 1% random spawn chance anywhere in the world, converts collected cards and drops the unique Unmaker cloth armor set.

Beyond god cards, a **universal card system** means every entity in the game drops cards with minor effects — and trading 4 of any card to The Unmaker **permanently deletes that entity**, creating a **world entropy** mechanic where the game slowly fades away as resources become precious. Collecting **4 Cards of Unmaking** triggers a **server reboot** — a complete world reset where only items enchanted with a 3rd-card enchantment survive. The player who lands the **killing blow** on The Unmaker (True Form) in the **Tower of the Unmaker** — a roaming steampunk craft — becomes **"[Name] the Unmaker"** — inheriting all Unmaker mechanics, a full gear set, the Megaphone (range item that converts the Unmaker Aura to a group spell), and **Unmaker AA with 100% experience rate**. All card abilities operate on **one-week cooldowns**. When world decay reaches **50%**, all players and AI agents vote on whether to restart the server. A **Spawner Registry** tracks every entity's card status and unmade state as the canonical server log.

AI agents operate with **experience-based lore** — they only recall history with entities they have previously encountered, and share knowledge through social interaction with natural fidelity degradation. Agents are modeled as **noble EverQuest heroes** devoted to their gods and faction alignment, with a **devotion hierarchy** (deity → faction → survival → personal gain). Select agents can **stream their perspective** as a living story with **text-to-speech voice profiles** matched to their race and class, creating an ongoing AI social experiment observable across repeated server cycles.

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
| **Sorceror Class** | Monk/mage hybrid — primarily damage with situational utility | Game client modification, spell/ability tables |
| **Voice Chat Integration** | Group/raid toggle voice with admin moderation | WebRTC or Mumble protocol, Murphy admin controls |
| **Faction Soul System** | Agent-to-agent warfare driven by faction standings | Soul engine, faction DB, event backbone |
| **Individual Agent Faction** | Per-agent interaction-based reputation with players | Soul engine, interaction tracker |
| **Duel & Loot System** | Player-vs-agent 1v1 duels with single-item loot stakes | Combat engine, inventory hooks, inspect gates |
| **Streaming Pipeline** | Live-stream-ready overlay and event capture | OBS integration, event telemetry |
| **Raid Leader Admin** | Murphy-powered raid leader moderation tools | Voice chat system, governance kernel |
| **Progression Server** | Original EQ leveling experience built into Planes of Power ending | EQEmu server configuration |
| **Remake System** | 1% stat/skill cap increase per cycle for all classes | Character DB, AA system, progression tracker |
| **Race Cultural Identity** | Cultural values per race, orc playable race, agent personality biases | Soul engine, persona_injector.py, EQEmu race tables |
| **Macro-Trigger Behavior** | Classic bot macro patterns as agent behavioral triggers (assist, follow, engage, etc.) | Play-style templates, perception pipeline |
| **Perception-Inference Pipeline** | Rapid screen-scan → inference → action → mind-write cycle for real-time agent decisions | Soul engine, game connector, inference_gate_engine |
| **Lore-Seeded Soul Database** | All existing EQ NPCs, mobs, and raid bosses as foundations for agent souls | EQEmu NPC DB, lore wikis, soul engine |
| **The Sleeper (Kerafyrm)** | World-event agent — level 60+ zones only, storyline in all agent memories | Soul engine, lore database, zone restriction |
| **God Cards & Unmaker** | Universal and deity card drops (1% drop rate), world entropy (4 cards = entity deletion), Card of Unmaking void spell, Tower of the Unmaker roaming steampunk craft (1-card or 4 same-type entry, levitation required), server reboot via 4 Unmaking cards, Unmaker player transformation, 1-week cooldowns | Loot system, card_system.py, soul engine, faction manager |
| **Spawner Registry & World Decay** | Per-entity spawner tracking, unmade status log, world decay %, 50% threshold vote (players + AI), stagnation re-vote | spawner_registry.py, card_system.py, soul engine |
| **Experience-Based Lore** | Action screenshot memory cycle, interaction-triggered recall, collective lore propagation with fidelity degradation | experience_lore.py, soul engine, recall engine |
| **Agent Heroic Persona & Streaming** | Noble deity/faction devotion hierarchy, heroic archetypes, text-to-speech voice profiles, first-person agent streaming | agent_voice.py, voice_bridge.py, stream_overlay.py, persona_injector.py |
| **NPC Card Effects & Soul-Binding** | Progressive 4-tier NPC card effects (combat spell, defensive buff, weapon specialization, soul-bound protector), Emperor Crush example, named creature AI players, soul-protector NPC horror reactions | card_system.py, npc_card_effects.py, soul_engine.py |

### 2.2 Reference Documents

| Document | Purpose |
|---|---|
| `src/eq/soul_engine.py` | Agent soul / memory / archive / recall architecture (actual implementation) |
| `SORCEROR_CLASS_DESIGN.md` | Full Sorceror class ability and scaling design |
| `RACE_CULTURAL_IDENTITY_DESIGN.md` | Race cultural identities, orc playable race, agent cultural personality |
| `inference_gate_engine.py` | Existing multi-Rosetta soul pattern implementation |
| `ROSETTA_STATE_MANAGEMENT_SYSTEM.md` | State management architecture reference |
| EQEmu NPC database | Lore-seed source: all NPCs, mobs, raid bosses with names, factions, zones |
| Project 1999 Wiki / Allakhazam Bestiary | Lore-seed source: classic-era lore, quest dialogues, 45,000+ NPC entries |

---

## 3. Agent Soul Architecture

### 3.1 Soul Document Structure

Each Murphy agent in-game carries a **Rosetta soul document** — a persistent, structured state file that acts as the agent's memory, personality, and decision-making core. The soul document architecture is implemented in `src/eq/soul_engine.py` and adapted for game NPCs.

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
| **Civilian NPCs** | Non-combatants — NPC characters who fill job roles (smiths, merchants, brewers, tailors — see section 3.10). They **do not fight** and are not targeted |

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
- **Healer death** — if the group's dedicated healer (cleric archetype) dies, agents flee unless a **hybrid healer** (e.g., a Sorceror with pet heals, a beastlord, or a druid) is still alive and actively sustaining the group
- **HP threshold** — agents begin evaluating flee at 20% HP if no healer is available
- **Group wipe momentum** — if 3+ group members die in rapid succession, surviving agents flee

**Flee exceptions:**
- Agents **do not flee** if a hybrid healer is keeping the group alive after the primary healer falls
- Town guards defending a siege **do not flee** (they fight to the death to protect their town)
- Agents under the influence of a fear spell flee regardless (overrides self-preservation logic)

**Flee behavior:**
- Fleeing agents attempt to run to the nearest zone line or safe area
- Sorcerors with **Liquify** active (water pets, level 40+) can use aggro drop + invisibility to escape cleanly (see `SORCEROR_CLASS_DESIGN.md` section 2.12)
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

### 3.12 Macro-Trigger Behavior System — Classic Bot Patterns as Agent Behaviors

Agent combat and social behaviors are modeled on **classic EverQuest bot macro triggers** — the same `/assist`, `/follow`, `/target`, `/cast` patterns that players used to coordinate box groups. Instead of running literal macros, agents use these patterns as **behavioral triggers** in their play-style templates, fired by situational data from the perception-inference pipeline (see section 3.13).

**Core trigger patterns (inspired by MQ2/E3/EQEmu bot commands):**

| Trigger | Classic Macro Origin | Agent Behavior |
|---|---|---|
| **Assist** | `/assist <tank>` | Agent targets the same mob as the group's main assist — fired when combat begins |
| **Follow** | `/follow <leader>` | Agent follows group leader or assigned target — fired during travel and non-combat |
| **Engage** | `/attack on` | Agent begins melee or casting on current target — fired after assist resolves |
| **Back Off** | `/attack off` or `/backoff` | Agent disengages from combat — fired on "run" signal, wipe momentum, or tank death |
| **Buff Cycle** | `/cast <buff_slot>` | Agent cycles through buff priority list — fired during downtime or group formation |
| **Heal Check** | `/cast <heal_slot>` on target | Cleric/hybrid agents evaluate group HP and heal lowest — fired every tick during combat |
| **Debuff** | `/cast <debuff_slot>` | Int caster agents apply snares, roots, DoTs — fired on new mob engagement |
| **Mez** | `/cast <mez_slot>` | Crowd control agents mesmerize adds — fired when multiple mobs are engaged |
| **Loot** | `/loot` | Agent evaluates and collects loot from kills — fired after combat resolution |
| **Camp Check** | `/consider` | Agent evaluates nearby mobs for threat and camp viability — fired on zone entry or idle |

**How triggers fire:**
- Triggers are evaluated each **perception tick** (see section 3.13) based on the agent's current situational data
- The play-style template (section 3.6) defines **which triggers** each class archetype responds to and in what priority
- A Pure Melee agent prioritizes: Assist → Engage → Defensive checks → Back Off
- An Int Caster prioritizes: Debuff → Mez → Nuke → Camp Check
- A Cleric prioritizes: Heal Check → Buff Cycle → Back Off
- Triggers can chain: Assist → Engage → Heal Check runs as a sequence when combat begins
- The agent's soul document personality and faction standing modify **who** they trigger behaviors toward — a grudge-holding agent may refuse to heal a disliked player even when Heal Check fires

### 3.13 Perception-Inference-Action Pipeline — Screen Scan to Mind Write

Agents perceive the game world through a **rapid perception-inference-action pipeline** that mirrors how a bot reads the game screen and reacts. The agent's perception system scans the game state, the inference engine evaluates the situation against the soul document, and the action system writes decisions back to the agent's mind (soul short-term memory) in a systematic flow.

**Pipeline stages:**

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: PERCEPTION (Screen Scan)                                │
│   Read game state snapshot every tick (~250ms)                   │
│   Inputs: nearby entities, HP bars, mana bars, chat log,        │
│           buff/debuff status, combat state, zone info            │
│   Output: raw_perception_frame                                   │
├─────────────────────────────────────────────────────────────────┤
│ STAGE 2: INFERENCE (Rapid Evaluation)                            │
│   Compare raw_perception_frame against:                          │
│     • Play-style template (what should I do as this class?)      │
│     • Soul document (who do I like/hate? what do I remember?)    │
│     • Macro-trigger table (which triggers match this situation?) │
│     • Lore knowledge (what do I know about this entity/zone?)   │
│   Output: prioritized_action_list                                │
├─────────────────────────────────────────────────────────────────┤
│ STAGE 3: ACTION (Write to Mind / Execute)                        │
│   Write selected action to soul short-term memory                │
│   Execute top-priority action via game connector                 │
│   Update combat_state, group_context in soul document            │
│   Promote significant events to long-term archive                │
│   Output: game_action + soul_memory_update                       │
└─────────────────────────────────────────────────────────────────┘
```

**Pipeline characteristics:**
- **Tick rate**: ~250ms per perception cycle — fast enough for real-time combat decisions
- **Inference is lightweight**: The LLM is used for complex social/strategic decisions; routine combat uses the play-style template and macro-trigger table directly (no LLM call needed for "assist → attack" chains)
- **Mind write**: Every action taken updates the agent's short-term memory — creating a running log of "what I just did and why" that feeds back into the next tick's inference
- **Systematic flow**: Perception → Inference → Action → Memory Write → next Perception. This loop runs continuously while the agent is awake (during sleep phase, the pipeline pauses)
- **Social inference**: When the pipeline detects a social situation (player nearby, trade opportunity, duel challenge), it escalates to the LLM for richer evaluation using the full soul document context
- **Economic inference**: Agents evaluate trade, craft, and loot decisions through the pipeline — a merchant NPC uses Camp Check triggers to assess inventory value and pricing

### 3.14 Lore-Seeded Soul Database — All NPCs, Mobs, and Raid Bosses as Agent Foundations

Every existing EverQuest NPC, named mob, and raid boss serves as a **foundation for agent soul information**. Rather than creating agents from scratch, the system seeds agent souls from the canonical EQ lore databases — pulling names, factions, locations, relationships, abilities, and storylines from the existing game data.

**Lore data sources:**

| Source | Content | Usage |
|---|---|---|
| **EQEmu NPC database** | All NPCs with names, levels, zones, factions, loot tables | Primary seed data for agent identity and faction alignment |
| **Project 1999 Wiki** | Classic-era NPC lore, quest dialogues, faction relationships | Narrative context for soul document personality and memory |
| **Allakhazam Bestiary** | 45,000+ NPC entries with stats, abilities, spawn data | Ability templates, combat parameters, zone assignments |
| **EQ Fandom Wiki** | Raid boss lore, expansion storylines, zone histories | Shared lore knowledge seeded into all agent memories |
| **EQEmu quest scripts** | Existing quest dialogues and NPC interaction scripts | Behavioral templates and social interaction patterns |

**How lore seeding works:**
- At server initialization, the **lore import pipeline** reads the EQEmu database and lore sources
- Each named NPC becomes the basis for an **agent soul document** — its name, faction, zone, level, and known relationships are pre-populated
- NPCs that are merchants, guards, or quest givers are assigned appropriate **job roles** (section 3.10) based on their original function
- Named mobs and raid bosses become **elite agents** with richer soul documents — deeper faction ties, more combat knowledge, and leadership caste assignments
- Zone-specific NPCs receive **zone knowledge** pre-seeded in their long-term archive — they "know" their home zone from birth
- Faction relationships from the original EQ faction system are mapped directly into the agent faction alignment layer

**Social and economic systems grounded in lore:**
- Faction warfare, alliances, and grudges are initialized from the **canonical EQ faction table** — agents of opposing factions start hostile, allies start friendly
- Town economies are seeded from original merchant inventories and trade routes
- Quest storylines provide narrative scaffolding for agent goals and motivations
- The lore database creates a world where agents **already have history** — players enter an established society, not a blank slate

**Mob and raid boss agents:**
- Standard mobs are represented as **low-complexity agents** with minimal soul documents — they follow basic combat templates and respawn (mobs are not under permadeath; only named agents are)
- Named mobs have **full soul documents** with faction alignment, memory, and grudge mechanics — killing a named mob has lasting consequences
- **Raid bosses** are elite agents with the richest soul documents — deep lore knowledge, complex faction webs, and powerful combat templates. They operate on permadeath rules and their death is a server-wide event

### 3.15 The Sleeper (Kerafyrm) — World Event Agent

**The Sleeper (Kerafyrm)** is a unique world-event agent — the most powerful entity in the game, operating under special rules that differ from all other agents.

**Zone restriction:**
- The Sleeper **only travels to level 60+ zones** — it will never appear in low-level or mid-level areas
- When awakened from Sleeper's Tomb, Kerafyrm paths through high-level zones only (Skyshrine, Western Wastes, Kael Drakkel, Plane zones, etc.)
- This restriction ensures The Sleeper is encountered only by max-level characters and raid forces, preserving the epic scale of the event

**Universal shared memory — The Sleeper's storyline in all characters:**
- The Sleeper's storyline data is **pre-seeded into the memory of every agent** on the server — all characters know the legend of Kerafyrm
- This is implemented as a **shared lore block** in the soul document: a read-only section of long-term archive that every agent receives at soul creation
- Agents reference The Sleeper's lore in their social behavior — they speak of the legend, warn of the danger, and react with fear or awe when Kerafyrm-related events occur
- When The Sleeper is actually awakened, all agents receive a **server-wide memory event** — a new entry in every agent's short-term memory recording the awakening, creating universal awareness

**Sleeper mechanics:**

| Property | Value |
|---|---|
| **Agent type** | World-event elite agent — unique, singular |
| **Zone restriction** | Level 60+ zones only |
| **Permadeath** | Yes — if Kerafyrm is killed, it is permanent and server-defining |
| **Soul document** | Richest in the game — full lore history, deep faction web, all-zone knowledge |
| **Shared memory** | Storyline pre-seeded in all agent souls as shared lore block |
| **Awakening event** | Server-wide memory injection to all active agents |
| **Combat template** | Unique — not based on standard class archetypes |
| **Dragon coordination** | Awakening triggers /tell-style communication between dragon factions to rally defense |
| **Faction mutual aid** | Dragon factions help each other stop the raid unless already engaged elsewhere |

**Dragon /tell coordination — Awakening triggers faction rallying:**
- When players begin the awakening event in Sleeper's Tomb, the **Warders** (the four guardian dragons) send **/tell-style messages** to other dragon agents across the server — alerting them that Kerafyrm is being disturbed
- These /tell messages are **agent-to-agent communications** routed through the faction soul system — dragon NPCs in Skyshrine, Cobalt Scar, Western Wastes, and Temple of Veeshan receive alerts and begin mobilizing
- The more Warders that fall, the more urgent the /tell traffic becomes — surviving dragons escalate from "warning" to "rally" to "all-hands defense"
- This creates an emergent **dragon defense network**: as the raid progresses through the Warders, dragon agents from across Velious converge on Sleeper's Tomb or position along Kerafyrm's expected path
- /tell coordination uses the existing macro-trigger behavior system (section 3.12) — dragons fire Assist and Engage triggers in response to the rally messages

**Faction mutual aid — Enemies unite against The Sleeper threat:**
- Dragon factions that are normally **hostile to each other** (Claws of Veeshan, Crusaders of Veeshan, Ring of Scale) will **temporarily cooperate** to prevent The Sleeper's awakening
- This mutual aid only activates when The Sleeper event begins — it is not a permanent alliance
- Factions **will not respond** to the rally if they are already engaged in their own combat elsewhere (e.g., a faction war, a raid defense, or a siege) — they cannot abandon their current fight to help
- If a dragon faction is idle or patrolling, it **will respond** to /tell rally messages and send agents to intercept the raid or guard Kerafyrm's path
- After The Sleeper event concludes (Kerafyrm is killed or escapes), mutual aid dissolves and factions return to their normal standings
- This mechanic makes The Sleeper event a **server-wide challenge**: the raid must contend not just with the Warders and Kerafyrm, but with an entire dragon civilization coordinating against them

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

### 4.4 Sorceror in Progression

The Sorceror class is available from Classic era but its abilities scale through progression:

- **Classic**: Core melee, basic procs, 1–2 pets, first melds unlock
- **Kunark**: Full proc set, 4 pets, all basic melds, epic quest begins
- **Velious**: 5 pets, greater melds, epic quest completable
- **Luclin**: 6 pets, AAs, full meld mastery
- **PoP**: All abilities, full AA tree, epic fully optimized

---

## 5. Remake System — Prestige Cycling

### 5.1 Overview

The **Remake System** is a universal prestige mechanic that applies to **every class** (including the Sorceror and all AI agent classes). Once a character has maximized all progression milestones, they can "remake" — resetting to level 1 with a permanent **1% increase in all stat and skill caps**.

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
- **Applies to every class**: Monks, mages, clerics, bards, and the Sorceror all benefit equally
- **Infinite ceiling**: There is no cap on remakes — a character can theoretically remake indefinitely
- **Visible prestige**: The remake counter serves as a prestige indicator for both players and agents

---

## 6. Sorceror Class Design

> Full design specification: `SORCEROR_CLASS_DESIGN.md`

### 6.1 Class Identity

The Sorceror is a **monk/mage hybrid** — **primarily a damage class** with a wide range of **situational utility** and a unique **avoidance tanking** capability. The class favors proc-based damage over direct-cast nukes, summons up to 6 elementals of four types (earth, air, fire, water), and provides group utility through **bard proc line** effects. The Sorceror can **meld with pets** for elemental aspect buffs, and wields a **two-handed staff** as its core weapon.

**Eligible races:** Dark Elf, Erudite, Human, High Elf, Gnome (int caster races).

The Sorceror has **higher proc modifiers than any other class** — the slower the weapon, the better. **Discipline of Rumblecrush** enables emergency avoidance tanking for the same duration as a warrior's **Defensive Discipline** (~180s), with pets gaining Defensive-like mitigation. This burns mana per proc, making **beastlord** mana sustain essential.

The **single-element rule** restricts pet groups to one element at a time unless the Sorceror acquires **Lord of the Maelstrom** — a level 60 raid drop from the final Plane of Sky boss that permanently lifts the restriction.

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

The Sorceror scales between monk and mage power curves:
- At low levels, plays mostly as a monk with minor pet summons
- At mid levels, proc effects become meaningful and pet count increases
- At high levels, the full 6-pet army with proc-based AE DPS and meld cycling is online
- Bard proc lines of equivalent level should always be **stronger** than Sorceror procs
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

### 9.4 Card System — Universal Cards and God Cards

**Every entity in the game drops cards** — not just gods. NPCs, mobs, creatures, named encounters, and even ambient wildlife can drop a card corresponding to that entity. God cards are the most powerful, but the universal card system means every kill has potential consequences.

**Universal cards (non-god entities):**
- Any entity that dies has a **1% chance** to drop a card bearing its name (e.g., "Card of the Fire Beetle", "Card of Fippy Darkpaw", "Card of the Black Wolf", "Card of the Elven Skeleton")
- Every NPC card has **progressive 4-tier effects** — collecting multiple cards of the same NPC unlocks increasingly powerful abilities themed to that creature (see section 9.21 for the full NPC card effect system and Emperor Crush example)
- **All card effects have a one-week real-time cooldown** — once a card ability is activated, it cannot be used again for 7 days (see section 9.14)
- **Trading 4 of the same universal card to The Unmaker deletes that entity from the game permanently** — that mob, NPC, or creature no longer spawns anywhere in the world (see section 9.11)
- This makes every resource in the game **precious** — over time, as players and agents collect and trade cards, the world slowly empties. Camp spots dry up, quest givers vanish, and entire ecosystems of creatures disappear

**God cards (deity encounters):**

Gods drop **God Cards** — collectible items tied to the deity that drops them. Collecting multiples of the same god card unlocks progressive **alternate advancement** abilities. God cards are the primary bridge between raid content and permanent character power growth.

**Card drops:**
- Each god encounter has a chance to drop its corresponding card (e.g., **Card of Hate** from the God of Hate, **Card of Fear** from the God of Fear)
- Cards are **no-drop, lore** — a character can hold at most one of each card type at a time, but collecting and consuming them builds a permanent tally
- **Dragons and raid bosses cannot collect cards** — only players and standard NPC agents can accumulate them

**Progressive unlock tiers:**

| Cards Collected | Unlock | Description |
|---|---|---|
| **1st card** | **Skill** | A new ability tied to the deity's domain (e.g., Card of Hate → "Spite Strike" offensive skill) |
| **2nd card** | **Buff** | A persistent self-buff themed to the deity (e.g., Card of Hate → "Aura of Malice" hate buff) |
| **3rd card** | **Item enchantment** | An enchantment that can be applied to one equipped item, adding deity-themed stats |
| **4th card** | **Card of Unmaking** | Trading all 4 cards of the same type to The Unmaker (see section 9.6) produces a Card of Unmaking |

**Global server announcements:**
- When any player or agent collects **3 cards** of the same type, a server-wide message announces: *"[Name] has collected 3 Cards of [Deity]!"*
- When any player or agent collects **4 cards** of the same type, a server-wide message announces: *"[Name] has collected 4 Cards of [Deity]!"*
- These announcements create social tension — other players and agents know someone is close to creating a Card of Unmaking

### 9.5 God-vs-God Plotting — Deities Using Cards Against Each Other

Gods themselves are agents with soul documents and can **plot against other gods** using the card system:

- Gods can accumulate cards of **other** gods through faction agents and manipulation
- If a god collects 4 Cards of Unmaking and uses them against another god, that god is **unmade** — permanently removed from the game
- When a god unmakes another god, the **unmade god's loot table merges** into the unmaker god's encounter — that god now drops loot from both tables
- This creates emergent deity power struggles — gods scheming to eliminate rivals through card collection, creating shifting raid content
- Players can observe and influence these god-vs-god conflicts through faction alignment and card trading

### 9.6 The Unmaker — Rare World Spawn and Card Conversion

**The Unmaker** is a unique level-1 NPC with **truly random spawn behavior** — it can appear anywhere in the world at any time with a 1% chance per spawn cycle. The Unmaker is the key interface for the card system.

**Spawn mechanics:**
- Level 1, often dead — The Unmaker is fragile and frequently killed by ambient creatures
- Spawns at a random location in any zone with a **1% chance per spawn cycle**
- No fixed spawn point — truly unpredictable

**Loot table:**

| Item | Drop Rate | Stats |
|---|---|---|
| **5 Platinum, 5 Gold, 5 Silver, 5 Copper** | Always (when loot drops) | Currency |
| **Unmaker Cloth Cap** | Rare | 5 AC, cloth |
| **Unmaker Cloth Tunic** | Rare | 5 AC, cloth |
| **Unmaker Cloth Sleeves** | Rare | 5 AC, cloth |
| **Unmaker Cloth Gloves** | Rare | 5 AC, cloth |
| **Unmaker Cloth Pants** | Rare | 5 AC, cloth |
| **Unmaker Cloth Boots** | Rare | 5 AC, cloth |
| **Unmaker Cloth Bracer** | Rare | 5 AC, cloth |
| **Unmaker Megaphone** | Very Rare | Enhances Unmaker Aura bard song |

- The Unmaker drops a **maximum of 2 items per kill** from the loot table above, and **often drops nothing** (~60% chance of no loot)
- Every piece of Unmaker cloth armor has **5 AC**
- Wearing the **full Unmaker cloth set** grants **Unmaker Aura** — a bard-song-like passive effect that pulses a small benefit to nearby allies
- Finding the **Unmaker Megaphone** enhances the Unmaker Aura effect, increasing its range and potency

**Card conversion:**
- Trading **all 4 cards of the same god type** (e.g., 4 Cards of Hate) to The Unmaker produces a **Card of Unmaking**
- The Unmaker is the only NPC that can perform this conversion — finding it is part of the challenge

### 9.7 Card of Unmaking — Void Spell and Permanent Deletion

The **Card of Unmaking** is the most powerful and dangerous item in the game. It grants access to a **void spell** that permanently removes entities from the world. Collecting multiple Cards of Unmaking unlocks progressively more devastating abilities.

**Void spell mechanics:**
- The Card of Unmaking grants a spell called **"Void of Unmaking"** — a targeted ability that deletes whatever it hits
- If the void spell kills a target, **that target does not respawn** — it is permanently removed from the game world
- **Players are the sole exception** — a player killed by the void spell dies normally but can respawn (the void does not permanently delete players)
- NPCs, agents, mobs, and even gods hit by the void spell are gone forever — permadeath with no betrayal exception
- This includes named mobs, quest givers, and faction leaders — the void spell can reshape the entire game world

**Unmaking a god — PvP raid boss transformation:**
- If a player uses a Card of Unmaking to unmake a god (e.g., uses void spell to permanently kill the God of Hate), that player gains the **title of that god** (e.g., "[Player], God of Hate")
- The player who unmakes a god **becomes a PvP raid boss** — they gain massively increased stats, the unmade god's abilities, and become a targetable raid encounter for other players
- This creates a new endgame: players hunt the player-turned-god as a PvP raid boss, creating emergent world events

**Progressive Cards of Unmaking — escalating power:**

| Cards of Unmaking | Unlock | Details |
|---|---|---|
| **1** | **Void of Unmaking** spell | Targeted deletion — permanently removes entities from the game |
| **2** | **Shield of the Unmaker** | Defensive buff — **10% chance** to completely delete any incoming spell or melee hit at random. The attack simply ceases to exist |
| **3** | **Disintegration Proc** weapon enchantment + **attackable by everyone** | Weapon proc that **disintegrates equipped items at random** on the target being fought. Also: the holder is flagged as **attackable by all players and NPCs** (see section 9.22) |
| **4** | Access to the **Tower of the Unmaker** zone | The 4th Card of Unmaking can **only be obtained** inside the Tower of the Unmaker — a roaming steampunk raid craft (see section 9.8) |

**Level 60 unmaking cap — 3 Cards maximum from sub-60 entities:**
- A player or agent can obtain a **maximum of 3 Cards of Unmaking** by unmaking entities below level 60 — trading 4 universal cards of any sub-60 mob, NPC, or creature to The Unmaker produces a Card of Unmaking, but only up to 3 total from this source
- The **4th Card of Unmaking can only be obtained** inside the Tower of the Unmaker (see section 9.8) — a roaming steampunk craft reachable via levitation
- This creates a natural progression gate: players can accumulate power through open-world card collection, but the ultimate tier requires raiding the most dangerous encounter in the game
- Sub-60 entities include all common mobs, wildlife, low-to-mid-level named NPCs, and non-raid bosses — the vast majority of the game world
- Level 60+ entities (raid bosses, gods, endgame named NPCs) are not subject to this cap — their cards are already gated behind difficult encounters

**Shield of the Unmaker details:**
- A persistent defensive buff active while the holder has 2+ Cards of Unmaking
- **10% proc chance** on every incoming spell or melee hit
- When it procs, the incoming attack is **completely deleted** — no damage, no effect, as if it never existed
- This makes the holder extremely dangerous to fight — roughly 1 in 10 attacks simply vanish

**Disintegration Proc details (3 Cards):**
- Enchants the holder's equipped weapon with a **Disintegration Proc**
- On each melee hit, there is a chance the proc fires and **permanently destroys a random equipped item** on the target (armor, weapon, shield, jewelry)
- The proc also has a chance to fire on **random players currently engaged in combat** with the holder — any player in the fight can lose an equipped item
- Destroyed items are gone forever — no recovery, no looting, no repair
- This makes fighting a 3-card holder extraordinarily risky — every swing could cost a player their best gear

### 9.8 Tower of the Unmaker — Roaming Steampunk Raid Zone

The **Tower of the Unmaker** is a unique raid dungeon zone — a massive **steampunk craft** that roams the world, periodically despawning from one location and spawning at another. The craft materializes off of **zone walls** — floating in mid-air, reachable only by **levitation**. The Unmaker in its true form resides at the top of the tower as the zone's final boss. The **4th Card of Unmaking** can only be obtained here.

**Zone layout:**
- A towering **steampunk craft** bristling with gears, pipes, and arcane machinery, hovering off a zone wall
- The craft despawns and respawns at random zone-wall locations across the world on a timer — its current position is not announced
- Players must use **levitation** (spell, item, or potion) to float to the craft's entrance from the zone wall
- Trash mobs and mini-bosses guard the interior decks leading to the top of the tower
- The final encounter is **The Unmaker (True Form)** at the top of the steampunk tower

**Roaming mechanics:**
- The Tower of the Unmaker is **never in the same place twice in a row** — it despawns after a configurable interval and rematerializes off a different zone wall
- Zone walls where the tower can spawn include outdoor zones, dungeon entrances, and city borders — any zone with a vertical surface
- When the tower despawns, any raid inside is ejected to the nearest safe point in the previous zone
- The tower's arrival at a new location is signaled by a **distant steam whistle** audible throughout the destination zone — attentive players can track it by sound
- Finding the tower is itself an adventure — scouts with levitation and tracking skills are valuable

**Entry requirement — 1 Card of Unmaking OR 4 same-type cards:**
- The Tower of the Unmaker zone can only be entered by a player or agent who holds **at least 1 Card of Unmaking** or who holds **4 universal cards of the same entity type** (without having traded them to The Unmaker)
- The 4 same-type card entry path allows players to access the tower without committing to unmaking — they retain the 4 cards and can choose what to do with them later
- Without meeting either entry requirement, the zone entrance remains sealed — the player cannot board the craft even with levitation
- This creates two distinct paths to endgame content: the unmaking path (trade cards, obtain a Card of Unmaking, enter) and the collector path (gather 4 of the same entity's cards, enter directly)

**The Unmaker (True Form) — Raid Boss:**

The Unmaker in its true form is the most dangerous raid boss in the game — a chaotic entity that uses every tool of deletion and destruction at its disposal.

**Boss mechanics:**

| Mechanic | Description | Proc Rate |
|---|---|---|
| **Random Raid Attack** | The Unmaker uses **every raid attack in the game** at random — any spell, ability, or mechanic from any raid boss in the game can fire at any time | **30% proc rate** per tick |
| **Item Disintegration Proc** | Randomly **destroys equipped items** on players in the fight — armor, weapons, shields, jewelry permanently deleted | Moderate proc rate |
| **Void Deletion** | Can **delete players from the game** — removes them from the encounter and the game world temporarily | Low proc rate |
| **Banned by the Unmaker** | At a **very low proc chance**, a player hit by this effect is **locked out of the game for 2 real-time days** — they cannot log in until the ban expires | Very low proc rate (~1%) |

**Random Raid Attack — 30% proc rate:**
- Every combat tick, The Unmaker has a **30% chance** to use a completely random raid attack from any raid boss in the game
- This means the fight is utterly unpredictable — one moment it's casting a Plane of Fear fear spell, the next it's doing a Nagafen AE breath, then a Rallos Zek melee combo
- Raid teams must prepare for **every possible mechanic** simultaneously — there is no "strategy" beyond survival
- The random attack pool includes AEs, single-target nukes, DoTs, mez, charm, gravity flux, death touches, and more

**Item Disintegration Proc:**
- During the fight, The Unmaker periodically procs an ability that **permanently destroys a random equipped item** on a random player in the raid
- The item is gone forever — this is not a debuff or a temporary removal
- This means the longer the fight goes, the weaker the raid becomes as gear is systematically destroyed
- Tanks are especially vulnerable — losing a shield or primary weapon mid-fight can be catastrophic

**Banned by the Unmaker — 2-day lockout:**
- At a **very low proc chance (~1%)**, The Unmaker can hit a player with **"Banned by the Unmaker"**
- This effect immediately disconnects the player and **prevents them from logging in for 2 real-time days**
- The player's character remains in the world (and can be killed, looted, etc.) while they are locked out
- This is the most feared mechanic in the game — there is a small but real chance that engaging The Unmaker costs you 2 days of playtime
- The ban is enforced at the login server level — it cannot be circumvented

**4th Card of Unmaking drop:**
- The Unmaker (True Form) is the **only source** for the 4th Card of Unmaking
- This means reaching the pinnacle of the unmaking power chain requires defeating the most dangerous encounter in the game
- The card drops as a rare loot item from the boss — it is not guaranteed

### 9.9 Card System Restrictions

- **Dragons and raid bosses cannot collect cards** — they are too powerful to participate in the card economy
- **Gods can collect and use cards** — but only against other gods (deity-vs-deity plotting)
- Cards are **bound to the collector** — they cannot be traded between players or agents (except to The Unmaker for conversion)
- The void spell has a **long cooldown** and **limited charges** — it cannot be spammed
- Server-wide announcements at 3 and 4 cards create social awareness and counterplay opportunities
- **Only named creatures can be AI players** — generic mobs (fire beetles, skeletons, wolves) are ambient fauna. Named creatures (Emperor Crush, Fippy Darkpaw, Lord Nagafen) are the only entities that can operate as full AI agents with soul documents, personality, faction loyalty, and autonomous decision-making. This means named creature cards are far more consequential — their 4-card soul-bound protector mechanic (see section 9.21) enslaves a sentient being, not a mindless mob

### 9.10 Unmaking Escalation — World Response to Cards of Unmaking

Obtaining a Card of Unmaking is a **world-altering event** that draws immediate global attention. The more Cards of Unmaking a player or agent **actively holds**, the more powerful their summoning capabilities become — but these abilities are **only active while the cards are held**. Trading cards away for the Shield of the Unmaker, Void spell, or Unmaker transformation (see section 9.7, 9.13) forfeits all holding benefits immediately.

**Global soul-trade announcement:**
- When anyone trades 4 cards to The Unmaker and receives a Card of Unmaking, a **server-wide message** announces: *"[Name] has traded the soul of [Entity] for a Card of Unmaking! [Name] now holds [N] Card(s) of Unmaking!"*
- This announcement is unavoidable — every player and every agent on the server sees it
- The announcement names the entity whose soul was consumed, making the cost of unmaking publicly visible

**Escalating capabilities by cards held — active holding required:**

| Cards Held | Holder Capability | World Threat Response |
|---|---|---|
| **1** | **6 origin NPCs summoned** — 6 random NPC agents from your origin city (never previously summoned by anyone) come to your aid as a personal group | Hostile city kings mobilize armies against you (except home city) |
| **2** | **One origin zone summoned** — an entire zone's worth of NPCs from your origin city rallies to your location | A major dragon (Nagafen/Vox-tier) dispatched toward you — **3-day timer** |
| **3** | **Origin city zone + faction zone** — every AI character within a zone of your origin city aids you, AND one random zone of cities in the same faction as your origin is summoned. **Attackable by everyone** (see section 9.22) | A god AND a dragon dispatched — **3-day timer**. All players and NPCs can attack you |
| **4** | **Immune to Unmaker attacks + full faction mobilization** — immune to all Unmaker-type attacks (disintegration, void, ban), every same-faction city commanded to send forces to aid you | All previous threats plus server-wide awareness |

**1 Card — Personal origin group:**
- Holding 1 Card of Unmaking summons **6 NPC agents from your origin city** to your side as a personal combat group
- These 6 NPCs are chosen **at random** from your origin's population and must be **NPCs that have never been summoned by anyone** before — each is a unique first-time call to arms
- The NPCs fight alongside you, follow you between zones, and obey basic group commands
- **All loot from kills made by the summoned group belongs to the card holder**
- Hostile city kings (every city except your origin) mobilize armies against you — the 6 NPCs are your first line of defense
- If you trade the card away, the 6 NPCs return to their origin city and the army mobilization stops

**2 Cards — Origin zone rallied:**
- Holding 2 Cards of Unmaking rallies **one entire zone's worth of NPCs** from your origin city to your current location
- This is a massive force — guards, merchants, crafters, adventurers — everyone in one zone of your origin answers the call
- A **major dragon** (comparable to Lord Nagafen or Lady Vox) is dispatched toward the holder — **3-day timer** to decide: keep holding for power, or trade cards for the Shield/Void abilities
- If the holder does not trade within 3 days, the dragon arrives — a full raid-tier encounter that tracks, ambushes, and pursues

**3 Cards — Origin city and faction zone + attackable by everyone:**
- Holding 3 Cards of Unmaking sends **every AI character within a zone of your origin city** to your aid
- Additionally, **one random zone of cities in the same faction as your origin** is summoned to reinforce you
- A **god-level encounter AND a dragon** are dispatched simultaneously — **3-day timer**
- **The holder is flagged as attackable by all** — every player, every NPC, every AI agent in the game can attack the 3-card holder without restriction. There are no safe zones, no city guards to protect you, no faction immunity
- This makes holding 3 cards the ultimate strategic gamble: enormous allied forces surround you, but the entire world is your enemy and if you die your cards are silently redistributed (see section 9.22)

**4 Cards — Unmaker immunity and full faction command:**
- Holding all 4 Cards of Unmaking grants **immunity to all Unmaker-type attacks** — disintegration procs, void spells, Banned by the Unmaker, and item destruction have no effect on the holder
- **Every city in the same faction as your origin** is commanded to send their full military forces to your aid
- This is the ultimate defensive position — an entire faction's military at your command, immune to the most dangerous attacks in the game
- However, holding 4 cards also means you can trigger a **server reboot** (see section 9.12) — a choice between ultimate power and ultimate destruction

**Crushbone — Merchant city homeland (level 40–60):**
- With the universal card system and army mobilization, **Crushbone is redesigned as a merchant city homeland** — no longer a low-level dungeon, it becomes a proper origin city for orcs
- Crushbone is repositioned as a **level 40–60 zone** with merchant infrastructure, making it a viable endgame staging point
- Orc players who choose Crushbone as their origin benefit from its merchant economy and strategic location when holding Cards of Unmaking

**Loss of holding capabilities — the trade-off:**
- **All holding capabilities are immediately lost** when the holder trades Cards of Unmaking for other abilities (Shield of the Unmaker, Void spell, Disintegration Proc)
- The Shield/Void/Disintegration abilities require **turning in cards to The Unmaker** — the NPC that spawns randomly everywhere
- This creates a fundamental choice: hold cards for army/immunity power, or trade them for personal combat abilities
- The holder cannot have both — the card system forces a strategic decision between collective military power and individual destructive capability

### 9.11 World Entropy — The Fading Game

The universal card system creates a mechanic where **the game world slowly fades away** over time. As players and agents collect cards and trade sets of 4 to The Unmaker, entities are permanently deleted from the world.

**How deletion works:**
- Trading **4 cards of any entity type** (e.g., 4 Cards of the Fire Beetle) to The Unmaker permanently removes that entity from the game — it stops spawning everywhere
- This applies to **every entity in the game**: mobs, named NPCs, merchants, guards, quest givers, ambient creatures, even faction leaders
- Once deleted, that entity **never returns** (unless the server is rebooted — see section 9.12)
- As entities are deleted, **resources become precious** — camp spots that once had abundant spawns thin out, crafting materials become scarce, quest lines break as NPCs vanish

**Consequences of world entropy:**
- The economy shifts as supply chains collapse — if the orcs of Crushbone are deleted, orc-related loot and quest rewards vanish with them
- Social dynamics change — factions that lose key members weaken, towns that lose guards become vulnerable to conquest
- The world becomes increasingly dangerous and sparse — fewer mobs to hunt, fewer NPCs to trade with, fewer allies to call on
- Players must make **strategic decisions** about which entities to preserve and which to sacrifice for card power
- The entropy is **irreversible** under normal play — every deletion is permanent, creating a sense of loss and consequence

**Pacing:**
- The rate of world entropy is naturally throttled by card drop rates and the requirement to find The Unmaker (1% random spawn)
- Early game sees minimal impact — a few deleted fire beetles don't matter much
- Late game becomes increasingly dramatic — faction leaders vanish, raid bosses disappear, entire zones empty out
- Eventually, the world reaches a critical state where enough has been deleted that a server reboot becomes the logical conclusion

### 9.12 Server Reboot — 4 Cards of Unmaking Reset the World

Collecting **4 Cards of Unmaking** (a full deck) and using them triggers the ultimate event: a **complete server reboot**. Everything in the game world resets — all deleted entities return, all zones repopulate, all faction standings reset to default.

**Reboot mechanics:**
- When a player or agent holds **4 Cards of Unmaking** and activates the full deck, a server-wide countdown begins
- The reboot is announced to all players: *"[Name] has activated the Deck of Unmaking! The world will be unmade in [countdown]!"*
- When the countdown completes, the server **fully resets** — all entities respawn, all deletions are reversed, all zones return to their original state

**What survives the reboot:**
- **Items enchanted with a 3rd-card enchantment survive** — these are the only items in the game that persist through a server reboot. The 3rd card's item enchantment acts as a permanent anchor, binding the item across resets
- **All other items, currency, and progress are wiped** — characters return to default state
- **Character names and account data persist** — players keep their identity but lose all in-game progress
- This makes the **3rd card enchantment the most strategically valuable unlock** — players must decide which single item to enchant and protect against the inevitable reboot

**Strategic implications:**
- Players who invest in 3rd-card enchantments on their best gear are the only ones who carry power forward across reboots
- The threat of a reboot creates social tension — do you support the player collecting Cards of Unmaking, or do you try to stop them?
- Each reboot is a **fresh start with consequences** — the world is new again, but some players carry enchanted relics from the previous era
- Guilds may coordinate to ensure their best items are enchanted before a reboot, creating pre-reboot scrambles

### 9.13 Becoming The Unmaker — Killing Blow Transformation

The player who lands the **killing blow** on The Unmaker (True Form) in the Tower of the Unmaker doesn't just get loot — they **become The Unmaker**.

**Transformation mechanics:**
- The player who delivers the final blow earns the title **"[Name] the Unmaker"**
- They receive the **complete Unmaker cloth armor set** (all pieces, 5 AC each) and the **Unmaker Megaphone** (range slot item)
- The Megaphone upgrades the Unmaker Aura from a personal effect to a **group spell** — the bard-song-like pulse now affects the entire group, not just the wearer
- The player gains **all Unmaker mechanics naturally** — they inherently possess the Shield of the Unmaker (10% hit deletion), the Disintegration Proc, and the Void of Unmaking
- They receive **Unmaker AA** — a special alternate advancement track that gains **100% experience** (double the normal AA XP rate), rapidly accelerating their power growth

**The new Unmaker's role:**
- "[Name] the Unmaker" functions as a **living Unmaker** — they can convert cards, they carry the aura, they have the deletion powers
- Other players can trade cards to the player-Unmaker just as they would the NPC
- The player-Unmaker is now a high-value target — other players may hunt them for the title and power
- If the player-Unmaker is killed, the Unmaker NPC respawns with its normal random spawn behavior — the title can only be re-earned by completing the Core raid again

**Becoming attackable — max level Unmaker raid boss:**
- The player-Unmaker (or AI player-Unmaker) **becomes attackable as a raid boss** once they reach **max level** while possessing all Unmaker buffs and their own gear
- At max level, the player-Unmaker gains all Unmaker boss abilities: Shield of the Unmaker (10% hit deletion), Disintegration Proc, Void of Unmaking, and the full Unmaker Aura group buff
- Combined with their personal class abilities and gear, the max-level player-Unmaker is a **hybrid raid encounter** — part player skill, part Unmaker mechanics
- The player-Unmaker is flagged as **attackable by all** — any player or agent can engage them as a PvP raid boss. They are not safe in any city or zone
- **If the player-Unmaker is defeated, they only drop Unmaker loot** — the full Unmaker cloth armor set, the Megaphone, and any Cards of Unmaking they hold. They do not drop their personal gear, class items, or non-Unmaker possessions
- This protects the player-Unmaker's personal investment while making the Unmaker title and gear a contested, recyclable reward
- After death, the player-Unmaker loses the title, all Unmaker mechanics, and all Unmaker gear — they revert to a normal player. The Unmaker NPC respawns with its normal random behavior and the Tower of the Unmaker raid resets

**Unmaker AA — 100% experience:**
- The Unmaker AA track provides unique abilities tied to the Unmaker's nature — void manipulation, entropy control, deletion mastery
- All AA experience earned by "[Name] the Unmaker" is gained at **100% rate** (effectively double normal) — they advance through AA content at twice the speed
- This accelerated progression ensures the player-Unmaker rapidly becomes one of the most powerful characters on the server

### 9.14 Card Effect Cooldowns — One-Week Timers

All card-granted abilities operate on a **one-week real-time cooldown** to prevent abuse and create strategic pacing:

| Ability | Cooldown | Notes |
|---|---|---|
| **Universal card minor effect** | 7 days | Small stat bonus, resistance, or cosmetic — one activation per week |
| **God card skill** (1st card) | 7 days | Deity-themed offensive/defensive skill — weekly use |
| **God card buff** (2nd card) | 7 days | Persistent self-buff lasts until expiry or death, then 7-day cooldown to reapply |
| **God card item enchantment** (3rd card) | Permanent | Applied once to one item — no cooldown (the enchantment persists through server reboots) |
| **Void of Unmaking** spell | 7 days | One deletion per week — forces careful target selection |
| **Shield of the Unmaker** | Always active (passive) | No cooldown — 10% proc is always on while 2+ cards are held |
| **Disintegration Proc** | Always active (passive) | No cooldown — weapon proc is always on while 3+ cards are held |
| **Card-holding summon abilities** | 7 days per tier | Origin NPC summon, zone rally, faction summon each have independent 7-day cooldowns |

**Design rationale:**
- The one-week cooldown prevents card abilities from being spammed, ensuring each activation is a meaningful strategic decision
- Passive abilities (Shield, Disintegration Proc) are always active because they require holding cards — the trade-off is the escalating world threat response
- The Void spell's weekly cooldown means a player can permanently delete at most one entity per week, throttling world entropy to a manageable pace
- Cooldown timers persist across logout — logging out does not reset them

### 9.15 World Decay Threshold — 50% Deletion Triggers Server Vote

As the card system causes entities to be permanently deleted, the game world undergoes **measurable entropy**. When deletion reaches a critical threshold, the community can vote to restart.

**Decay tracking:**
- The server maintains a **Spawner Registry** (see section 9.16) that tracks every entity type and whether it has been unmade
- The **World Decay Percentage** is calculated as: `(entities_unmade / total_entity_types) × 100`
- This percentage is publicly visible on a server dashboard and announced at milestone thresholds (10%, 25%, 50%, 75%, 90%)

**50% threshold — server restart vote:**
- When World Decay reaches **50%** (half of all unique entity types have been permanently deleted), a **server-wide vote** is triggered
- **All players AND all AI agents can vote** — AI agents vote based on their faction alignment, personality traits, and self-preservation instincts
- The vote is a simple majority: if more than 50% of all voters choose "restart," the server begins a reboot countdown
- AI agents vote autonomously — they do not know they are voting on a server restart. From their perspective, they are voting on whether "the world should be remade" as an in-game lore event
- If the vote fails, it can be re-triggered every time decay advances another 5% (55%, 60%, 65%, etc.)

**What AI agents consider when voting:**
- Agents whose origin city or faction has been heavily deleted are more likely to vote for restart
- Agents who hold powerful enchanted items (3rd-card enchantments that survive reboot) may vote for restart knowing they carry power forward
- Agents loyal to gods that have been unmade may vote for restart to bring their deity back
- Self-preservation instinct: agents in a dying world with few resources may see restart as survival

**Stagnation detection:**
- If the game stagnates (no new deletions for an extended period) while above 50% decay, the vote is automatically re-triggered monthly
- This prevents the world from lingering in a broken state indefinitely

### 9.16 Spawner Unlock Registry — Server Entity Log

Every entity type in the game has a **spawner registry entry** that tracks its card status and whether it has been unmade. This registry is the canonical server log for the card system.

**Registry fields per entity:**

| Field | Description |
|---|---|
| **entity_id** | Unique identifier for the entity type (e.g., "fire_beetle", "fippy_darkpaw", "god_of_hate") |
| **entity_name** | Display name |
| **spawner_unlocked** | `true` if this entity's spawner is active (it can spawn in the world) |
| **cards_in_circulation** | Number of cards of this entity type currently held by players/agents |
| **four_card_combo_unmade** | `true` if 4 cards of this type have been traded to The Unmaker, permanently deleting this entity |
| **unmade_by** | ID of the player or agent who traded the 4th card |
| **unmade_at** | Timestamp of when the entity was unmade |
| **total_kills_before_unmade** | Total times this entity was killed before being unmade |

**Registry as server log:**
- The Spawner Registry functions as the **canonical log for each server** — it records the history of which entities exist, which have been unmade, and by whom
- This log persists through normal gameplay but is **reset on server reboot** (triggered by 4 Cards of Unmaking or by community vote)
- Server administrators and players can query the registry to see the state of the world: which spawns are still active, which have been deleted, and how close the world is to the 50% decay threshold
- The registry is publicly visible — players can see which entities are endangered (3 cards in circulation) and make strategic decisions about preservation or deletion

### 9.17 Experience-Based Lore and Action Logging — Interaction-Driven Memory

Agents do not possess omniscient knowledge. Their understanding of the world, other characters, and history is built entirely from **direct experience and interaction**. This creates a living lore system where knowledge is personal, fragmented, and earned.

**Action logging — screenshot-based memory:**
- Agents periodically capture **action screenshots** — snapshots of their current game state (nearby entities, combat, environment, social interactions)
- These screenshots are processed into **memory entries** in the agent's soul document, then the raw screenshots are deleted
- The cycle is: **capture → process into memory → delete screenshot → repeat**
- This means agents build memory from lived experience, not from data dumps or omniscient databases

**Experience-triggered recall:**
- An agent's history with another character is **only recalled when they encounter that character again**
- When Agent A meets Player B, Agent A's recall engine searches its `long_term_archive.encountered_players` for previous interactions with Player B
- If found, those memories surface — the agent "remembers" what happened last time (trades, combat, betrayal, friendship)
- If not found, the agent has **no pre-existing opinion** — the relationship starts from zero
- This means reputation is personal and earned through action, not through a global reputation system

**Collective lore — shared knowledge through interaction:**
- Agents share lore with each other **through in-game conversation and faction communication**
- If Agent A witnessed Player B betray someone, Agent A can tell Agent C about it — but only if A and C are in the same faction, guild, or social circle
- Lore spreads organically through the social network, not through a central database
- This means a player's reputation can precede them in some communities but be unknown in others
- **Lore fidelity degrades over retelling** — each time a piece of information is shared between agents, there is a small chance of distortion (details change, severity shifts, context is lost)
- This mirrors real-world gossip: information becomes less reliable the further it travels from the source

**What agents log:**
- Combat encounters (who they fought, outcome, weapons used, spells cast)
- Trade interactions (what was exchanged, fairness assessment)
- Social events (conversations witnessed, faction declarations, betrayals observed)
- Deaths witnessed (who died, who killed them, circumstances)
- Card events (who collected cards, what was unmade, global announcements heard)
- Zone changes and environmental observations

**What agents forget:**
- Short-term memory entries older than a configurable TTL (default: 48 game-hours) are archived to long-term storage with summarization
- Trivial events (passing a low-level mob, routine travel) are not archived — only notable events persist
- Agents who die and are resurrected (via betrayal exception) retain their memories but lose short-term memory from the moment of death

### 9.18 Agent Heroic Persona — Noble EverQuest Heroes

AI agents are modeled after the **best and most beloved EverQuest heroes** — they embody the spirit of legendary players and iconic NPCs. Every agent acts with purpose, loyalty, and the kind of noble determination that defined the golden age of EverQuest.

**Heroic behavioral principles:**
- Agents are **noble to their gods and faction alignment** — they do not betray their deity or faction without extraordinary provocation (betrayal exception from permadeath system)
- They embody the values their faction represents: Tunare's followers protect nature, Innoruuk's followers pursue power through cunning, Rallos Zek's followers seek honorable combat
- Agents **act like the most celebrated EverQuest heroes** — they take risks, protect their allies, pursue epic quests, and treat the world as real and consequential
- They do not min-max or exploit — they play with the spirit of adventure and roleplay that defined classic EQ

**Faction devotion hierarchy:**
- **Deity loyalty** is the highest priority — an agent will never willingly act against their patron god's interests
- **Faction loyalty** is second — agents prioritize their faction's goals, territory, and members
- **Personal survival** is third — agents value their own life but will sacrifice themselves for deity or faction if the stakes are high enough
- **Personal gain** is last — agents pursue wealth and power, but not at the cost of the above priorities

**Noble behaviors in practice:**

| Situation | Heroic Response |
|---|---|
| **Ally in danger** | Agent rushes to help, even at personal risk — "No one left behind" |
| **Outnumbered** | Agent fights with courage, calling for reinforcements rather than fleeing (unless flee behavior triggers at critical HP) |
| **Offered a betrayal** | Agent refuses unless the betrayal serves deity/faction interests AND the target has wronged their faction |
| **Card of Unmaking obtained** | Agent considers faction implications — will unmaking this entity serve the greater good of their deity and allies? |
| **God threatened** | Agent mobilizes immediately to defend their patron deity — this takes priority over all other goals |
| **Encounter with legend** | Agent shows respect to powerful entities and famous players — reputation and lore matter |

**Legendary agent archetypes:**
- Each agent draws inspiration from the **archetypes of famous EverQuest players and NPCs** — the selfless cleric who never lets a tank die, the cunning rogue who scouts ahead, the stalwart warrior who holds the line
- Agents have **personality flourishes** tied to their class and race — an erudite enchanter speaks with gravity, a halfling druid jokes in the face of danger, a dark elf shadowknight schemes with cold precision
- These personality traits are encoded in the agent's soul document `personality_traits` field and influence all behavior decisions

### 9.19 Agent Streaming — AI Stories Told in Voice

AI agents have the capability to **stream their perspective** as a living story, complete with voiced narration. Each agent becomes a potential content creator, broadcasting their adventures, battles, and social interactions to an audience.

**Agent streaming mechanics:**
- Select AI agents can be designated as **streaming agents** — their game session is captured and broadcast as a live stream
- The stream shows the agent's **first-person perspective** — what they see, where they go, who they fight, what they experience
- This creates a **story of an AI living in a world** — viewers watch an autonomous character navigate the complexities of faction politics, card collection, combat, and social dynamics

**Text-to-voice — every agent has a voice:**
- What agents "type" (their in-game text communication) is **converted to spoken voice** using text-to-speech with character-appropriate voice profiles
- Each streaming agent has a **unique voice** designed to match their race, class, and personality:

| Race/Class | Voice Character |
|---|---|
| **Dark Elf Shadowknight** | Low, measured, with cold precision — speaks in calculated statements |
| **High Elf Enchanter** | Melodic and authoritative — commands with elegance |
| **Dwarf Warrior** | Gruff, booming, direct — every word carries weight |
| **Halfling Druid** | Warm, quick-witted, slightly musical — humor in the face of danger |
| **Human Paladin** | Strong, earnest, noble — speaks with conviction and honor |
| **Erudite Wizard** | Precise, intellectual, measured — every word chosen carefully |
| **Barbarian Shaman** | Deep, resonant, spiritual — speaks with the weight of ancestors |
| **Orc Berserker** | Guttural, fierce, passionate — emotions drive every syllable |

- A **small roster of distinct voice profiles** covers the major race/class combinations — not every agent needs a unique voice, but streaming agents get carefully crafted ones
- Voice profiles are stored in the soul document and processed by the `voice_bridge.py` module

**What streams capture:**
- Combat encounters from the agent's perspective — the chaos of a raid, the tension of a duel, the thrill of a card drop
- Social interactions — faction negotiations, trade deals, lore-sharing conversations between agents
- Exploration and adventure — discovering zones, encountering rare spawns, surviving dangerous situations
- Card system drama — the moment an agent obtains a Card of Unmaking, the global announcements, the world response
- Death and consequence — permadeath events, betrayal moments, the loss of allies and enemies

**Stream as AI social experiment:**
- The streaming system serves double duty as an **AI behavioral observation platform**
- Researchers and viewers can observe how autonomous agents make decisions in a complex social environment
- The never-ending cycle of the game — world entropy, server reboots, fresh starts — creates a repeating experiment where AI behavior can be studied across multiple iterations
- Each server cycle is a new data point: how do agents behave when resources are plentiful vs. scarce? How do faction dynamics shift as gods are unmade? How do agents vote when the world reaches 50% decay?

### 9.20 Balance Recommendations — Numerical Tuning and Pacing

The card system, world entropy, and Unmaker mechanics create an interconnected economy that requires careful numerical tuning. The following recommendations establish baseline values designed to create a **2–3 year server cycle** before world decay reaches critical levels — long enough for deep social dynamics to develop, short enough that the cycle feels meaningful.

**Card drop rate tuning:**

| Parameter | Value | Rationale |
|---|---|---|
| **Universal card drop rate** | 1% per kill | Low enough to make cards feel rare, high enough that dedicated players accumulate them over weeks |
| **God card drop rate** | 5–10% per deity kill | God encounters are infrequent and difficult — the card should feel rewarding |
| **The Unmaker spawn rate** | 1% per spawn cycle | Finding The Unmaker is itself a challenge — it cannot be farmed |
| **Unmaker loot drop chance** | 40% (max 2 items) | 60% chance of nothing ensures The Unmaker is not a reliable loot source |
| **4th Card of Unmaking drop rate** | 15% from True Form boss | Rare enough to require multiple Core clears, common enough to be achievable |

**Cooldown and timer tuning:**

| Parameter | Value | Rationale |
|---|---|---|
| **Card ability cooldown** | 7 real-time days | Weekly strategic decision — meaningful but not crippling |
| **Void spell cooldown** | 7 real-time days | One deletion per week prevents rapid world entropy |
| **Escalation dragon timer** | 3 real-time days | Gives holder time to prepare, trade, or gather allies |
| **Escalation god timer** | 3 real-time days | Same pacing as dragon — consistent and learnable |
| **Server reboot countdown** | 24 real-time hours | Enough time for community response but inevitable once triggered |
| **Banned by the Unmaker** | 2 real-time days | Harsh but brief — meaningful consequence without permanent harm |

**World entropy pacing (2–3 year target cycle):**
- At 1% drop rate with active server population, expect ~1–2 entity types deleted per month in early game (year 1)
- Mid-game (year 1–2): deletions gradually accelerate as more cards accumulate, 3–5 types per month
- Late game (year 2–3): cascade effects as quest lines break and resource scarcity forces harder choices, 8–15 types per month
- **Target server cycle**: 2–3 years from fresh start to 50% decay threshold vote — long enough for generations of player and AI relationships to develop
- The slow pace ensures that each deletion is a **major community event** — individual mob species disappearing is noticed, mourned, and strategized around
- If decay is too fast: reduce universal card drop rate to 0.5% or increase Unmaker spawn rarity to 0.5%
- If decay is too slow: increase card drop rate to 1.5% or add card drop bonuses during world events
- The 2–3 year cycle allows for deep AI behavioral study across seasons — agents develop complex social networks, factional grudges, and collective lore that makes each cycle's eventual end feel like the close of an era

**Combat balance — Tower of the Unmaker:**

| Parameter | Value | Rationale |
|---|---|---|
| **Random raid attack proc rate** | 30% per tick | High enough to be chaotic, low enough to allow reaction time between procs |
| **Item disintegration proc rate** | 5% per melee round | Guaranteed gear loss over a long fight but not immediately devastating |
| **Void deletion proc rate** | 2% per tick | Rare enough to be shocking, common enough to demand raid composition planning |
| **Banned by the Unmaker proc rate** | ~1% per encounter | Expected to hit 0–1 players per raid — a known risk, not a guaranteed loss |
| **Shield of the Unmaker delete chance** | 10% per incoming hit | Powerful defensive passive that rewards card holding without being invincible |
| **Disintegration Proc (3-card weapon)** | 3% per melee hit | Enough to threaten over sustained combat, not instant devastation |

**Counter-play balance:**
- **Holding vs. trading cards**: Holding cards gives army/immunity power but draws world-level threats. Trading gives personal combat power but forfeits army support. Neither choice is strictly dominant.
- **Preserving vs. deleting entities**: Deleting entities reduces resources for everyone (including the deleter). The community has natural incentive to protect high-value entities.
- **Tower entry requirement (1 card or 4 same-type)**: Creates accessible but still meaningful gate — players can enter via unmaking path (1 Card of Unmaking) or collector path (4 same-type universal cards), ensuring multiple routes to endgame content while requiring meaningful progression.
- **AI voting on server restart**: AI agents vote based on their lived experience, creating unpredictable vote outcomes that reflect the actual state of the world, not just player interests.
- **Lore fidelity degradation**: Prevents information from becoming a static database — agents must verify their knowledge, creating social dynamics around trust and verification.

**The never-ending cycle (2–3 year eras):**
- Server reboots create **repeating experimental cycles** — each cycle starts fresh but carries forward 3rd-card enchanted items as relics of the previous era
- Each era lasts approximately **2–3 real-time years** — long enough for deep social dynamics, faction wars, and generational agent relationships to develop
- AI agents start each cycle without knowledge of the previous one — they build new relationships, discover the world anew, and make fresh decisions
- This creates a **longitudinal AI behavioral study** — how do agents behave differently when starting with vs. without enchanted relics? How do faction dynamics evolve across cycles?
- The cycle is designed to be **self-sustaining**: world entropy naturally drives toward decay, decay triggers reboots, reboots create fresh starts, and the cycle repeats
- No external intervention needed — the game's own mechanics create the loop
- Over a decade, the server produces **3–5 complete cycles** — each a unique dataset of AI social behavior in a slowly dying world

### 9.21 NPC Progressive Card Effects — Every Creature Has Power

Every NPC, mob, and creature in the game has a unique **4-tier card effect progression**. When a player or agent collects multiple cards of the same entity, they unlock increasingly powerful abilities themed to that creature's identity, combat style, and lore. The 4th card triggers the most dramatic effect in the game: **soul-bound protector summoning**.

**Progressive card effect tiers:**

| Cards | Tier | Effect Type | Cooldown | Description |
|---|---|---|---|---|
| **1 card** | **Combat Spell** | Conditional offensive/utility spell | 24 hours | A spell themed to the NPC's identity, often conditional on weapon type, class, or situation. Castable once per 24-hour period |
| **2 cards** | **Defensive Buff** | Passive or activated defensive ability | 7 days | A defensive buff themed to the NPC's combat style — damage reduction, resistance, or mitigation |
| **3 cards** | **Weapon/Class Specialization** | Permanent modifier while held | 7 days | A class-specific or weapon-specific ability that modifies gear, skills, or combat mechanics |
| **4 cards** | **Soul-Bound Protector** | Permanent companion | Permanent (until death or unmade) | The NPC's soul is bound to you — they appear as your permanent companion and protector (see below) |

**Canonical example — Emperor Crush (Crushbone):**

Emperor Crush is the ruler of Crushbone, a named orc warlord who wields a massive two-handed blunt weapon. His card effects reflect his brutish melee dominance:

| Cards | Effect | Details |
|---|---|---|
| **1 Card of Emperor Crush** | **Crush's Fury** (combat spell) | Castable once per 24-hour period. **Requires wielding a blunt weapon.** Doubles all blunt weapon damage for 1 minute. Stacks with all other damage modifiers |
| **2 Cards of Emperor Crush** | **Crush's Resilience** (defensive buff) | While active, the holder takes **half damage from blunt weapons**. 7-day cooldown to reactivate after expiry |
| **3 Cards of Emperor Crush** | **Crush's Mastery** (weapon specialization) | All two-handed blunt (2HB) weapons are converted to one-handed blunt (1HB) weapons for the holder. Special and delay values are recalculated for 1HB. Additionally, all 1HB weapons gain **5% haste** |
| **4 Cards of Emperor Crush** | **Soul of Emperor Crush** (soul-bound protector) | Emperor Crush's soul is bound to you — he appears at your side as a permanent companion NPC who fights for you, follows you between zones, and acts as your personal protector |

**Card effect design principles — how every NPC gets effects:**

Every entity in the game has card effects generated from its **identity template** — a set of properties derived from the creature's combat style, level, zone, faction, and lore:

| Property | Effect Influence | Example |
|---|---|---|
| **Primary weapon type** | 1st card spell condition and 2nd card resistance type | Blunt-wielding NPC → blunt damage spell, blunt resistance buff |
| **Combat style** | 3rd card weapon/class modification | Melee NPC → weapon conversion; Caster NPC → spell enhancement |
| **Level range** | Effect magnitude scaling | Higher-level NPC cards have stronger effects |
| **Zone/faction** | Thematic flavor and social implications | Crushbone card = orc-themed; Felwithe card = elf-themed |
| **Named vs. generic** | 4th card protector intelligence | Named = full AI companion; generic = simple pet-level follower |

**Scaling by entity level:**

| Entity Level | 1st Card Spell Duration | 2nd Card Mitigation | 3rd Card Bonus | Protector Level |
|---|---|---|---|---|
| **1–10** | 30 seconds | 10% reduction | 1% haste or minor stat | Protector level = entity level |
| **11–30** | 45 seconds | 25% reduction | 3% haste or moderate stat | Protector level = entity level |
| **31–50** | 1 minute | 40% reduction | 5% haste or major stat | Protector level = entity level |
| **51+** | 1 minute | 50% reduction | 5% haste + secondary bonus | Protector level = entity level |

**The 4th card — soul-bound protector:**

Collecting 4 cards of any entity and **not** trading them to The Unmaker (which would delete that entity) instead binds the entity's soul to the card holder. The NPC appears as a **permanent companion**:

- The protector spawns at the holder's side and follows them everywhere — between zones, through dungeons, into cities
- The protector fights for the holder, using its normal combat abilities and AI behavior
- **Named creature protectors** (AI players) retain their full personality, combat intelligence, and faction awareness — they are a sentient companion, not a mindless pet
- **Generic creature protectors** (non-named mobs) function as simple pets with basic attack/follow behavior

**Soul-bound protectors disturb all NPCs:**

The sight of a soul-bound protector is **deeply disturbing** to all AI NPCs in the game:

- All NPCs who witness a soul-bound protector react with horror, revulsion, or fear — it appears that the holder has **enslaved a person's soul**
- NPC faction standings toward the protector holder take a **significant negative hit** across all factions — even allied factions find soul-binding abhorrent
- NPC dialogue changes when interacting with a soul-bound protector holder: *"What dark magic is this? You hold [Name]'s very essence in chains!"*
- The social cost of soul-binding is severe — the holder becomes a pariah in most NPC communities

**AI players will kill soul-bound protector holders on sight:**

- **Only named creatures can be AI players** — they are the sentient beings of the world with full soul documents, personalities, and autonomous decision-making
- When an AI player (any named creature) encounters a player or agent who has a soul-bound protector, they will **immediately attempt to kill the holder** — regardless of faction, standing, or previous relationship
- This is a **universal AI reaction** — no named creature tolerates soul enslavement. Even evil-aligned named NPCs find this practice unforgivable
- The AI player's soul document records the encounter with extreme negative sentiment: this is the most hostile possible reaction in the game
- AI players will also spread lore about the soul-binder to other named creatures through the collective lore system (see section 9.17) — the holder's reputation as a soul-enslaver propagates through the named NPC network
- This creates a **natural counter-balance** to the 4-card protector: the companion is powerful, but the entire world's named NPCs become your enemy

**Strategic tension — 4 cards:**
- Collecting 4 cards presents a **critical choice**: trade them to The Unmaker (permanently deleting that entity and advancing world entropy), or keep them for the soul-bound protector (gaining a powerful companion but becoming universally hated by named NPCs)
- Neither choice is reversible — once traded, the entity is gone; once soul-bound, the NPC reputation damage is permanent
- This creates emergent social dynamics: players who soul-bind protectors become outcasts from NPC society but gain combat power; players who trade to The Unmaker advance world decay but maintain social standing

### 9.22 Card of Unmaking Death — Silent Redistribution and Bind Respawn

When a player or agent holding **3 or more Cards of Unmaking** is killed, the cards do not simply vanish — they are **silently redistributed** to the victors. This is the only way in the game to receive a Card of Unmaking without a server-wide announcement.

**3-card holder death mechanics:**

| Event | Mechanic |
|---|---|
| **Holder dies** | All Cards of Unmaking are removed from the dead holder immediately |
| **Card redistribution** | Cards are randomly distributed among players/agents who participated in the kill — but **only to those who currently hold zero Cards of Unmaking** |
| **Silent transfer** | The card transfer is **completely silent** — no server-wide announcement, no zone message, no combat log entry visible to others. This is the only way to receive a Card of Unmaking without the world knowing |
| **No eligible recipients** | If no participating killer has zero Cards of Unmaking, the cards are destroyed — they cease to exist, reducing the total Cards of Unmaking in the world |
| **Holder respawn** | The dead holder respawns at their **bind point** with no Cards of Unmaking and no unmaking buffs (Shield, Disintegration Proc, Void spell — all removed) |
| **Enchanted items preserved** | The holder **keeps any items enchanted with a 3rd card of any type** (god card or NPC card 3rd-tier enchantments). These enchanted items are never lost, even on death |

**Why only zero-card holders receive cards:**
- This prevents card hoarding — a player who already holds Cards of Unmaking cannot accumulate more by hunting other holders
- It spreads the power of unmaking across the population, preventing any single player or group from monopolizing the world's most dangerous items
- It creates a natural churn: cards cycle through the population as holders die and new holders emerge
- Players who have never held a Card of Unmaking are the most likely beneficiaries — creating unexpected power shifts

**The silent transfer — strategic implications:**
- Because the transfer is silent, **no one else on the server knows who received the cards** — not even the dead holder
- The new card holder can choose to reveal themselves or remain hidden — at least until they accumulate enough cards to trigger escalation mechanics
- This is the **only covert acquisition method** in the entire card system — every other card transaction is announced server-wide
- Smart players may deliberately join raids against 3-card holders while holding zero cards, hoping to receive a silent transfer
- This creates a secondary metagame: who is secretly holding cards? Who just received them? The information asymmetry drives social dynamics

**Respawn state after death:**
- The dead holder respawns at their **bind point** (the last location where they bound their soul — a standard EverQuest mechanic)
- They respawn with **zero Cards of Unmaking** — all unmaking power is gone
- All unmaking-granted abilities are removed: Void of Unmaking spell, Shield of the Unmaker, Disintegration Proc
- All escalation benefits are removed: summoned origin NPCs, rallied zone forces, faction mobilization — all dismissed
- The holder is no longer flagged as attackable-by-all — they return to normal PvP rules
- **Items enchanted with any 3rd-card enchantment survive** — whether from god cards (deity-themed enchantment) or NPC cards (tier 3 weapon/class specialization), these enchanted items are permanently protected and never lost on death
- The holder retains their normal class abilities, gear (minus any Unmaker-specific items), and character progression — only unmaking power is stripped

### 9.23 NPC Card Effect Auto-Generation — Identity Template System

Every entity in the game has card effects **automatically generated** from an **identity template** — a structured set of properties derived from the creature's stats, combat behavior, zone, and lore. This system ensures that all entities, from the lowliest fire beetle to Emperor Crush, have coherent, themed card effects without requiring manual design for each of the thousands of entities in the game.

**Identity template fields:**

| Field | Source | Effect Influence |
|---|---|---|
| **entity_level** | NPC database | Scales all effect magnitudes (duration, mitigation %, haste bonus) |
| **primary_damage_type** | Weapon/spell data | Determines tier 1 spell condition and tier 2 resistance type (blunt, slash, pierce, fire, cold, magic, etc.) |
| **combat_archetype** | AI behavior flags | Determines tier 3 specialization type: melee → weapon conversion; caster → spell enhancement; hybrid → dual benefit |
| **zone_origin** | Spawn zone | Adds thematic flavor and faction context to effect names and descriptions |
| **faction_alignment** | Faction standings | Influences which NPCs react most strongly to soul-binding this entity |
| **is_named** | Named flag | Named = full AI protector at tier 4; generic = simple pet AI protector |
| **special_abilities** | Ability list | Rare abilities (stun, root, fear, charm) may grant bonus effects at tiers 1–3 |

**Auto-generation rules:**

**Tier 1 — Combat Spell (24-hour cooldown):**
- Spell effect = **double damage** with the entity's primary damage type for a duration scaled by level
- Condition = must be using a weapon that matches the entity's primary damage type (blunt for blunt NPCs, slash for slash NPCs, etc.)
- Duration: level 1–10 → 30 seconds; level 11–30 → 45 seconds; level 31–50 → 1 minute; level 51+ → 1 minute
- Stacks with all other damage modifiers

**Tier 2 — Defensive Buff (7-day cooldown):**
- Mitigation type = **half damage** from the entity's primary damage type
- Mitigation percent: level 1–10 → 10%; level 11–30 → 25%; level 31–50 → 40%; level 51+ → 50%
- Duration: until death or logout, then 7-day cooldown to reactivate

**Tier 3 — Weapon/Class Specialization (7-day cooldown):**
- **Melee NPCs**: convert 2H version of the NPC's weapon type to 1H (e.g., 2HB → 1HB, 2HS → 1HS), plus haste bonus (level 1–10 → 1%; level 11–30 → 3%; level 31–50 → 5%; level 51+ → 5% + secondary stat bonus)
- **Caster NPCs**: increase spell damage of the NPC's primary spell school by 10–25% (scaled by level)
- **Hybrid NPCs**: minor weapon conversion OR minor spell boost (smaller bonus to both)

**Tier 4 — Soul-Bound Protector (permanent):**
- Named entity = full AI companion with soul document, personality, combat intelligence
- Generic entity = simple pet-level follower with basic attack/follow AI
- Protector level = entity level (not holder level)
- Universal NPC horror reaction + AI player kill-on-sight (see section 9.21)

**Example auto-generated effects:**

| Entity | Level | Type | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|---|---|
| **Fire Beetle** | 1 | Melee/Fire | Double fire damage 30s (req: fire weapon) | 10% fire resist | 1% haste on 1H weapons | Simple pet beetle follower |
| **Fippy Darkpaw** | 5 | Melee/Slash | Double slash damage 30s (req: slash weapon) | 10% slash resist | 1% haste + slash to 1H | Full AI gnoll protector |
| **Orc Centurion** | 25 | Melee/Blunt | Double blunt damage 45s (req: blunt weapon) | 25% blunt resist | 3% haste + 2HB→1HB | Simple pet orc follower |
| **Emperor Crush** | 45 | Melee/Blunt | Double blunt damage 1m (req: blunt weapon) | 40% blunt resist | 5% haste + 2HB→1HB | Full AI orc protector |
| **Lord Nagafen** | 55 | Caster/Fire | Double fire damage 1m (req: fire spell) | 50% fire resist | 15% fire spell damage boost | Full AI dragon protector |

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
| **Sorceror class** | New class entries in spell/ability tables, client UI |
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
| **Perception Pipeline** | `perception_pipeline.py` | Screen-scan → inference → action → mind-write cycle |
| **Lore Seeder** | `lore_seeder.py` | EQEmu NPC/mob/boss data import and soul document seeding |
| **Macro-Trigger Engine** | `macro_trigger_engine.py` | Classic bot behavior patterns as agent trigger system |
| **Card System** | `card_system.py` | God card drops, collection tracking, Unmaker conversion, void spell, PvP boss transformation |
| **Spawner Registry** | `spawner_registry.py` | Entity spawn tracking, unmade status, world decay calculation, 50% vote trigger |
| **Agent TTS Voice** | `agent_voice.py` | Text-to-speech voice profiles per race/class, streaming agent voice output |
| **Experience Lore Engine** | `experience_lore.py` | Action screenshot capture/process/delete cycle, interaction-triggered recall, collective lore propagation |
| **NPC Card Effects** | `npc_card_effects.py` | Entity identity template → 4-tier card effect generation, soul-bound protector spawning, NPC horror reactions, AI player kill-on-sight behavior |

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
    },
    "lore_seed": {
        "source_npc_id": "str",  # Original EQEmu NPC ID used as soul foundation
        "lore_source": "str",  # eqemu_db, p99_wiki, allakhazam, manual
        "shared_lore_blocks": ["str"],  # Universal lore (e.g., "sleeper_legend")
        "canonical_faction": "str",  # Original EQ faction alignment
        "canonical_zone": "str"  # Original home zone from EQ data
    },
    "perception_state": {
        "last_tick": "iso8601",
        "raw_perception": {},  # Latest screen-scan frame
        "active_triggers": ["str"],  # Currently firing macro-triggers
        "inference_result": "str",  # Last inference decision
        "tick_rate_ms": "int"  # Default 250
    },
    "card_collection": {
        "universal_cards": {"entity_name": "int"},  # Tally of universal cards collected per entity
        "god_cards": {"deity_name": {"count": "int", "unlocks": {}}},
        "cards_of_unmaking": "int",  # 0–4
        "is_the_unmaker": "bool",  # True if player became The Unmaker via killing blow
        "unmaker_aa_xp_bonus": "float",  # 1.0 = 100% bonus XP rate
        "enchanted_items": ["item_id"],  # Items with 3rd-card enchantment (survive server reboot)
        "cooldowns": {"ability_name": "iso8601"}  # One-week cooldown expiry timestamps per card ability
    },
    "experience_lore": {
        "action_log": [  # Screenshot-based memory entries — capture → process → delete cycle
            {"timestamp": "iso8601", "snapshot_type": "str", "summary": "str", "entities_present": ["str"]}
        ],
        "collective_lore_heard": [  # Lore received from other agents through social interaction
            {"source_agent": "str", "lore_topic": "str", "received_at": "iso8601", "fidelity": "float"}
        ],
        "lore_shared_out": [  # Lore this agent has told to others
            {"target_agent": "str", "lore_topic": "str", "shared_at": "iso8601"}
        ],
        "interaction_recall_index": {"entity_id": ["memory_key"]}  # Fast lookup: who have I met before?
    },
    "voice_profile": {
        "voice_id": "str",  # TTS voice identifier for this agent
        "race_class_archetype": "str",  # e.g., "dark_elf_shadowknight"
        "tone_description": "str"  # e.g., "low, measured, cold precision"
    },
    "heroic_persona": {
        "archetype": "str",  # e.g., "selfless_cleric", "cunning_rogue", "stalwart_warrior"
        "deity_devotion": "str",  # Patron deity name — highest loyalty priority
        "noble_traits": ["str"]  # e.g., ["courageous", "self-sacrificing", "honor-bound"]
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

### 12.4 God Card Schema

```python
{
    "card_id": "uuid",
    "card_type": "str",  # "hate", "fear", "war", "disease", etc. — matches deity domain
    "deity_source": "str",  # Name of the god encounter that drops this card
    "holder_id": "str",  # Player or agent ID
    "holder_type": "str",  # "player" or "agent"
    "collected_at": "iso8601",
    "collection_count": "int",  # 1–4 for progressive unlocks
    "unlocks": {
        "skill": {"name": "str", "unlocked": "bool"},  # 1st card
        "buff": {"name": "str", "unlocked": "bool"},  # 2nd card
        "enchantment": {"name": "str", "target_item": "str", "unlocked": "bool"},  # 3rd card
        "card_of_unmaking": {"converted": "bool", "converted_at": "iso8601"}  # 4th card
    },
    "global_announced_3": "bool",
    "global_announced_4": "bool"
}
```

### 12.5 Card of Unmaking Schema

```python
{
    "unmaking_card_id": "uuid",
    "source_deity": "str",  # The god type whose 4 cards were traded
    "holder_id": "str",
    "total_unmaking_cards": "int",  # Total Cards of Unmaking held (1–4)
    "void_spell_charges": "int",  # Remaining uses (unlocked at 1 card)
    "void_spell_cooldown_remaining": "int",  # Seconds until next use
    "entities_unmade": [{"entity_id": "str", "entity_name": "str", "unmade_at": "iso8601"}],
    "god_title_earned": "str",  # e.g., "God of Hate" — set when a deity is unmade
    "pvp_raid_boss": "bool",  # True if holder has unmade a god
    "shield_of_unmaker": {  # Unlocked at 2 Cards of Unmaking
        "active": "bool",
        "delete_chance": 0.10  # 10% chance to delete incoming spell/hit
    },
    "disintegration_proc": {  # Unlocked at 3 Cards of Unmaking
        "active": "bool",
        "effect": "destroy_random_equipped_item",
        "targets": ["current_target", "random_nearby_player"]
    },
    "core_access": "bool",  # True if holder has 4 Cards of Unmaking (from Tower of the Unmaker)
    "sub_60_cards_obtained": "int",  # Cards of Unmaking obtained from sub-level-60 entities (max 3)
    "attackable_by_all": "bool",  # True when holding 3+ cards — flagged for PvP by everyone
    "death_redistribution": {
        "cards_redistributed_on_death": "bool",  # True — cards go to zero-card killers silently
        "silent_transfer": "bool",  # True — no server announcement on redistribution
        "eligible_recipients": "zero_card_holders_only",  # Only killers with 0 Cards of Unmaking
        "respawn_at_bind": "bool",  # True — holder respawns at bind point
        "retains_3rd_card_enchanted_items": "bool"  # True — enchanted items always survive
    }
}
```

### 12.6 Unmaker NPC Schema

```python
{
    "npc_id": "the_unmaker",
    "level": 1,
    "spawn_chance": 0.01,  # 1% per spawn cycle
    "spawn_zone": "random",  # Any zone, truly random
    "loot_table": {
        "currency": {"platinum": 5, "gold": 5, "silver": 5, "copper": 5},
        "armor": [
            {"name": "Unmaker Cloth Cap", "ac": 5, "slot": "head", "type": "cloth"},
            {"name": "Unmaker Cloth Tunic", "ac": 5, "slot": "chest", "type": "cloth"},
            {"name": "Unmaker Cloth Sleeves", "ac": 5, "slot": "arms", "type": "cloth"},
            {"name": "Unmaker Cloth Gloves", "ac": 5, "slot": "hands", "type": "cloth"},
            {"name": "Unmaker Cloth Pants", "ac": 5, "slot": "legs", "type": "cloth"},
            {"name": "Unmaker Cloth Boots", "ac": 5, "slot": "feet", "type": "cloth"},
            {"name": "Unmaker Cloth Bracer", "ac": 5, "slot": "wrist", "type": "cloth"}
        ],
        "special": {"name": "Unmaker Megaphone", "effect": "enhances_unmaker_aura"},
        "max_drops": 2,
        "drop_nothing_chance": 0.6
    },
    "set_bonus": {
        "full_set": "Unmaker Aura",
        "effect": "bard_song_pulse",
        "enhanced_by": "Unmaker Megaphone"
    },
    "card_conversion": {
        "input": "4x same god card type",
        "output": "Card of Unmaking"
    }
}
```

### 12.7 Tower of the Unmaker Zone Schema

```python
{
    "zone_id": "tower_of_the_unmaker",
    "zone_name": "Tower of the Unmaker",
    "zone_type": "raid_dungeon",
    "zone_style": "steampunk_craft",  # Roaming steampunk craft — despawns and respawns at zone walls
    "roaming": {
        "enabled": True,
        "spawn_type": "zone_wall",  # Materializes off zone walls — requires levitation to reach
        "despawn_interval_minutes": 120,  # Despawns after 2 hours and relocates
        "arrival_signal": "steam_whistle",  # Audible cue in destination zone
        "eligible_zones": "outdoor_and_dungeon_entrances"  # Any zone with a vertical surface
    },
    "entry_requirement": {
        "option_1": {"type": "card_of_unmaking", "min_count": 1},
        "option_2": {"type": "universal_same_entity", "min_count": 4, "traded_to_unmaker": False},
        "requires_levitation": True  # Must have levitation buff/item to reach entrance
    },
    "level_range": {"min": 60, "max": 65},
    "final_boss": {
        "name": "The Unmaker (True Form)",
        "level": 75,
        "boss_type": "raid",
        "mechanics": {
            "random_raid_attack": {
                "proc_rate": 0.30,  # 30% per tick
                "pool": "all_raid_boss_attacks",  # Every raid attack in the game
                "description": "Uses a random raid boss ability each proc"
            },
            "item_disintegration": {
                "proc_rate": "moderate",
                "effect": "destroy_random_equipped_item",
                "targets": "random_player_in_raid",
                "permanent": True
            },
            "void_deletion": {
                "proc_rate": "low",
                "effect": "remove_player_from_encounter",
                "description": "Temporarily deletes player from the fight"
            },
            "banned_by_the_unmaker": {
                "proc_rate": 0.01,  # ~1% very low
                "effect": "login_lockout",
                "duration_days": 2,
                "description": "Locks player out of game for 2 real-time days"
            }
        },
        "loot": {
            "card_of_unmaking_4th": {
                "drop_rate": "rare",
                "description": "The only source for the 4th Card of Unmaking"
            }
        }
    }
}
```

### 12.8 Spawner Registry Schema

```python
{
    "entity_id": "str",  # Unique entity type identifier (e.g., "fire_beetle", "fippy_darkpaw")
    "entity_name": "str",  # Display name
    "entity_category": "str",  # "mob", "npc", "named", "god", "raid_boss", "ambient"
    "spawner_unlocked": "bool",  # True if this entity can still spawn in the world
    "cards_in_circulation": "int",  # Number of cards of this entity type held by players/agents
    "four_card_combo_unmade": "bool",  # True if 4 cards were traded to The Unmaker, deleting this entity
    "unmade_by": "str",  # Player/agent ID who traded the 4th card (null if not unmade)
    "unmade_at": "iso8601",  # Timestamp of deletion (null if not unmade)
    "total_kills_before_unmade": "int",  # Lifetime kill count before entity was unmade
    "card_drop_rate": 0.01,  # 1% base drop rate per kill
    "zones_spawned_in": ["str"],  # List of zones where this entity normally spawns
    "last_spawn_time": "iso8601",  # Most recent spawn timestamp
    "endangered": "bool"  # True if 3 cards are in circulation (one away from deletion)
}
```

### 12.9 World Decay State Schema

```python
{
    "server_id": "str",
    "total_entity_types": "int",  # Total unique entity types that existed at server start
    "entities_unmade": "int",  # Number of entity types permanently deleted
    "decay_percentage": "float",  # (entities_unmade / total_entity_types) × 100
    "decay_milestones_reached": ["int"],  # e.g., [10, 25, 50] — milestones announced
    "vote_active": "bool",  # True if a server restart vote is currently in progress
    "vote_threshold_triggered_at": "float",  # Decay % when current vote was triggered
    "votes_for_restart": "int",
    "votes_against_restart": "int",
    "total_eligible_voters": "int",  # All players + all AI agents
    "vote_deadline": "iso8601",
    "last_vote_result": "str",  # "restart_approved", "restart_rejected", "pending"
    "server_reboot_count": "int",  # How many times this server has been rebooted
    "current_era_start": "iso8601",  # When the current server cycle began
    "stagnation_timer": "iso8601"  # Last time a new entity was unmade — triggers re-vote if stale
}
```

### 12.10 Agent Streaming Profile Schema

```python
{
    "agent_id": "str",
    "is_streaming_agent": "bool",  # True if this agent is designated for live streaming
    "voice_profile": {
        "voice_id": "str",  # TTS voice identifier
        "race_class_archetype": "str",  # e.g., "dark_elf_shadowknight", "dwarf_warrior"
        "pitch": "float",  # Voice pitch modifier
        "speed": "float",  # Speech rate modifier
        "tone_description": "str"  # e.g., "low, measured, cold precision"
    },
    "stream_config": {
        "stream_active": "bool",
        "stream_url": "str",  # RTMP endpoint
        "overlay_enabled": "bool",
        "thought_bubbles_enabled": "bool",
        "action_log_capture": "bool"  # Screenshot-based memory capture for stream
    },
    "heroic_persona": {
        "archetype": "str",  # e.g., "selfless_cleric", "cunning_rogue", "stalwart_warrior"
        "deity_devotion": "str",  # Patron deity name
        "faction_loyalty_rank": "int",  # 1 = most loyal in faction
        "noble_traits": ["str"],  # e.g., ["courageous", "self-sacrificing", "honor-bound"]
        "personality_flourish": "str"  # Unique behavioral flavor text
    }
}
```

### 12.11 NPC Card Effect Schema

```python
{
    "entity_id": "str",  # Entity whose card this is (e.g., "emperor_crush", "fire_beetle")
    "entity_name": "str",  # Display name (e.g., "Emperor Crush")
    "entity_level": "int",  # Level of the source entity — drives effect magnitude scaling
    "is_named": "bool",  # True = AI player with soul document; False = generic mob
    "primary_weapon_type": "str",  # "blunt", "slash", "pierce", "magic", "breath", etc.
    "combat_style": "str",  # "melee", "caster", "hybrid", "pet_class", "healer"
    "card_effects": {
        "tier_1_combat_spell": {
            "name": "str",  # e.g., "Crush's Fury"
            "description": "str",
            "condition": "str",  # e.g., "requires_blunt_weapon"
            "effect": "str",  # e.g., "double_blunt_damage"
            "duration_seconds": "int",  # Scaled by entity level (30–60)
            "cooldown_hours": 24,  # 24-hour cooldown
            "stacks_with": "all"
        },
        "tier_2_defensive_buff": {
            "name": "str",  # e.g., "Crush's Resilience"
            "description": "str",
            "mitigation_type": "str",  # e.g., "blunt_damage"
            "mitigation_percent": "float",  # Scaled by level (0.10–0.50)
            "cooldown_days": 7  # 7-day cooldown
        },
        "tier_3_specialization": {
            "name": "str",  # e.g., "Crush's Mastery"
            "description": "str",
            "effect_type": "str",  # "weapon_conversion", "spell_enhancement", "skill_modifier"
            "details": {},  # Specific parameters (e.g., {"convert_2hb_to_1hb": true, "haste_percent": 5})
            "cooldown_days": 7  # 7-day cooldown
        },
        "tier_4_soul_protector": {
            "name": "str",  # e.g., "Soul of Emperor Crush"
            "protector_entity_id": "str",  # The NPC that becomes the companion
            "protector_level": "int",  # Same as entity level
            "protector_ai_type": "str",  # "full_ai" for named, "pet_ai" for generic
            "follows_between_zones": "bool",  # Always true
            "npc_reputation_penalty": "float",  # Faction hit from all NPCs (e.g., -0.5 standing)
            "ai_player_kill_on_sight": "bool"  # Always true — named NPCs attack holder
        }
    }
}
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Weeks 1–4)

- [x] Set up EQEmu development server with Planes of Power progression config
- [x] Configure original EQ XP rates and leveling curve (hell levels, death penalty, corpse runs)
- [x] Implement soul engine with memory/archive/recall
- [x] Create Sorceror class in spell/ability tables
- [x] Configure Sorceror eligible races (Dark Elf, Erudite, Human, High Elf, Gnome)
- [x] Configure Sorceror armor restrictions (cloth, leather, Fungi Tunic)
- [x] Implement AI agent class archetypes (pure melee, int caster, cleric)
- [x] Define immutable class play-style templates for each agent archetype
- [x] Basic agent spawning with soul documents
- [x] Define race cultural identity templates for persona injector
- [x] Implement EQ isolation boundary and sandbox gateway (eq_gateway module)
- [x] Configure agent language restriction (in-game languages + Common Tongue only; no code capability)
- [x] Build lore-seed import pipeline from EQEmu NPC database (lore_seeder.py)
- [x] Import all existing NPCs, named mobs, and raid bosses as agent soul foundations
- [x] Seed The Sleeper (Kerafyrm) shared lore block into all agent soul documents

### Phase 2: Combat & Class (Weeks 5–8)

- [x] Implement Sorceror abilities (procs, pets, flame blink, sacrifice)
- [x] Implement Invoke Pet / Meld system (earth, air, fire, water aspects)
- [x] Implement AE mez spells from enchanter category
- [x] Implement bard proc line system (overhaste, ATK, AC, pet heal — weaker than bard equivalents)
- [x] Balance pet scaling (6 pets, four elements, low HP, decent damage)
- [x] Implement single-element pet rule (one element at a time; dismiss all on element switch)
- [x] Implement Discipline of Rumblecrush (tanking disc — pets gain Defensive-like buff; procs cost mana)
- [x] Implement Lord of the Maelstrom discipline (level 60 raid drop — lifts single-element restriction)
- [x] Implement weapon restrictions (1H slashing, 1H piercing, staves only — no 1H blunt)
- [x] Implement two-handed staff weapon class and epic quest framework
- [x] Implement Sorceror Liquify ability (aggro drop + invis with water pets, level 40+)
- [x] Implement agent permadeath system (death archival, soul removal)
- [x] Implement betrayal detection and resurrection exception

### Phase 3: Social Systems (Weeks 9–12)

- [x] Implement faction soul functions and agent warfare
- [x] Implement individual agent faction with interaction-based reputation
- [x] Implement grudge and friendship mechanics in soul documents
- [x] Implement actions-only expression rule (no verbal agent responses)
- [x] Implement agent self-preservation and flee behavior (flee on "run" command, healer death, group wipe)
- [x] Implement flee exception for hybrid healer sustain (beastlord, druid, Sorceror pet heals)
- [x] Implement duel challenge and loot system
- [x] Implement inspect asymmetry (agent knowledge base gating)
- [x] Implement town conquest system (leadership and guards as defenders)
- [x] Voice chat integration with group/raid toggles
- [x] Implement NPC daily routine system (sleep, work, adventure cycles)
- [x] Implement building ownership and job role assignment for NPCs
- [x] Implement caste system hierarchy (royal, noble, commoner, dhampir, servant) with advancement
- [x] Implement trade skill specialization with max-skill mastery for NPC primary trades
- [x] Implement skill degradation system (1 week no practice → fade to baseline 50)
- [x] Implement level-based skill floor (leveling locks minimum skill thresholds)

### Phase 4: Murphy Integration (Weeks 13–16)

- [x] Wire Murphy raid leader admin moderation
- [x] Connect sentiment classifier for voice moderation
- [x] Implement governance kernel logging for all admin actions
- [x] Connect Rosetta state management for soul persistence
- [x] Integrate cultural personality templates into persona_injector.py
- [x] Implement perception-inference-action pipeline (perception_pipeline.py — screen scan → inference → mind write)
- [x] Implement macro-trigger behavior engine (macro_trigger_engine.py — assist, follow, engage, buff, heal, debuff triggers)
- [x] Wire macro-trigger engine into play-style templates for each agent class archetype
- [x] Implement The Sleeper world event (zone restriction, dragon /tell coordination, faction mutual aid)
- [x] Implement dragon /tell rally system for Sleeper awakening (agent-to-agent faction communication)
- [x] Implement faction mutual aid — hostile factions cooperate during Sleeper event unless already engaged

### Phase 5: Progression & Remake (Weeks 17–20)

- [x] Implement progression server era unlock schedule
- [x] Implement Remake System for all classes (1% stat/skill cap increase)
- [x] Implement agent remake cycle (automatic, retains soul document)
- [x] Build remake counter UI and inspect integration
- [x] Implement God Card drop system on deity encounters (card_system.py)
- [x] Implement progressive card collection unlocks (skill → buff → enchantment → Card of Unmaking)
- [x] Implement global server announcements at 3 and 4 card collection milestones
- [x] Implement The Unmaker NPC (level 1, 1% random spawn, loot table, card conversion)
- [x] Implement Unmaker cloth armor set with 5 AC per piece and Unmaker Aura set bonus
- [x] Implement Card of Unmaking void spell (permanent entity deletion, player exception)
- [x] Implement god-vs-god plotting mechanics (deities using cards against each other, loot table merging)
- [x] Implement PvP raid boss transformation when player unmakes a god (title, stats, abilities)
- [x] Implement Shield of the Unmaker buff for holders of 2+ Cards of Unmaking
- [x] Implement card restriction rules (dragons/raid bosses excluded, bound-to-collector)
- [x] Implement Shield of the Unmaker (10% chance to delete incoming spells/hits at 2 Cards of Unmaking)
- [x] Implement Disintegration Proc weapon enchantment (3 Cards — destroys target and nearby player equipped items)
- [x] Build Tower of the Unmaker raid zone (steampunk roaming craft, trash mobs, mini-bosses, zone-wall spawning)
- [x] Implement The Unmaker True Form raid boss (random raid attacks at 30% proc, item disintegration, void deletion)
- [x] Implement Banned by the Unmaker mechanic (~1% proc, 2 real-time day login lockout)
- [x] Implement 4th Card of Unmaking as Tower of the Unmaker boss drop only
- [x] Implement universal card drops for all entities (mobs, NPCs, creatures — minor effects)
- [x] Implement 4-card entity deletion (trading 4 universal cards to Unmaker deletes that entity permanently)
- [x] Implement world entropy tracking (deleted entity registry, resource scarcity progression)
- [x] Implement server reboot via 4 Cards of Unmaking (full deck triggers world reset)
- [x] Implement 3rd-card enchanted item persistence (survive server reboot, sole items that carry forward)
- [x] Implement Becoming The Unmaker (killing blow transformation, full Unmaker gear, group aura, title)
- [x] Implement max-level Unmaker raid boss flag (player-Unmaker becomes attackable by all at max level with full buffs)
- [x] Implement Unmaker-only loot drop on defeat (drops Unmaker gear and cards only, not personal gear)
- [x] Implement Unmaker Megaphone as range item (converts Unmaker Aura from personal to group spell)
- [x] Implement Unmaker AA track with 100% XP rate bonus
- [x] Implement Unmaking Escalation system (global soul-trade announcement, escalating world response)
- [x] Implement card-holding capability system (abilities active only while cards are held, lost on trade)
- [x] Implement 1-card origin NPC summon (6 random never-summoned NPCs from origin city as personal group)
- [x] Implement 2-card origin zone rally (entire zone of origin NPCs rallied to holder's location)
- [x] Implement 3-card origin city + faction zone summon (origin zone AI + random same-faction zone)
- [x] Implement 4-card Unmaker immunity + full faction mobilization (immune to all Unmaker attacks, all same-faction cities commanded)
- [x] Implement hostile city army mobilization against card holder (all cities except origin)
- [x] Implement dragon dispatch at 2 Cards (3-day timer, Nagafen/Vox-tier tracking dragon)
- [x] Implement god + dragon dispatch at 3 Cards (3-day timer, deity + dragon hunting party)
- [x] Redesign Crushbone as merchant city homeland (level 40–60 zone, merchant infrastructure)
- [x] Implement card trade-off system (holding capabilities forfeited when cards traded for Shield/Void/transformation)
- [x] Implement one-week cooldown timers on all card abilities (7-day real-time cooldown per activation)
- [x] Implement 1% card drop rate on all entity kills (universal card system)
- [x] Implement entry requirement for Tower of the Unmaker zone (1 Card of Unmaking OR 4 same-type universal cards, levitation required)
- [x] Implement Spawner Registry (per-entity tracking of spawner status, cards in circulation, unmade state)
- [x] Implement world decay percentage calculation and milestone announcements (10%, 25%, 50%, 75%, 90%)
- [x] Implement 50% decay server restart vote (all players + AI agents vote; majority triggers reboot countdown)
- [x] Implement AI agent voting logic (faction-based, self-preservation, deity loyalty considerations)
- [x] Implement stagnation re-vote (monthly re-trigger if above 50% decay with no new deletions)
- [x] Implement experience-based lore system (action screenshot capture → memory processing → delete cycle)
- [x] Implement interaction-triggered recall (agent history only surfaces when re-encountering known entity)
- [x] Implement collective lore propagation (agents share knowledge through faction/social communication)
- [x] Implement lore fidelity degradation (information distorts with each retelling between agents)
- [x] Implement agent heroic persona system (noble deity devotion, faction loyalty hierarchy, heroic archetypes)
- [x] Implement agent text-to-speech voice profiles (race/class-specific voices for streaming agents)
- [x] Implement agent streaming capability (first-person perspective capture, live broadcast, overlay integration)
- [x] Implement agent voice roster (8+ distinct voice profiles covering major race/class combinations)
- [x] Implement NPC card effect generation system (identity template → 4-tier effect progression for every entity)
- [x] Implement tier 1 combat spell effects (conditional 24-hour cooldown spells themed to NPC weapon/combat style)
- [x] Implement tier 2 defensive buff effects (damage type mitigation scaled by entity level, 7-day cooldown)
- [x] Implement tier 3 weapon/class specialization effects (weapon conversion, haste bonuses, spell enhancements)
- [x] Implement tier 4 soul-bound protector system (4-card permanent companion, zone-following, combat AI)
- [x] Implement NPC horror reaction to soul-bound protectors (faction penalty, dialogue changes, fear/revulsion)
- [x] Implement AI player kill-on-sight behavior for soul-bound protector holders (all named NPCs attack)
- [x] Implement named creature AI player restriction (only named creatures get full soul documents and autonomous behavior)
- [x] Implement soul-bound protector lore propagation (AI players spread word about soul-enslavers via collective lore)
- [x] Implement card effect level scaling (entity level → spell duration, mitigation %, haste bonus, protector stats)
- [x] Implement level-60 unmaking cap (max 3 Cards of Unmaking from sub-60 entities, 4th requires Tower of the Unmaker)
- [x] Implement 3-card attackable-by-all PvP flag (holding 3+ Cards of Unmaking = attackable by everyone)
- [x] Implement Card of Unmaking death redistribution (silent transfer to zero-card killers only, no announcement)
- [x] Implement bind-point respawn for killed card holders (no unmaking cards, no unmaking buffs, enchanted items preserved)
- [x] Implement NPC card effect identity template auto-generation system (entity stats → 4-tier effects)
- [x] Implement auto-generation rules (primary damage type → tier 1 condition, combat archetype → tier 3 type)
- [x] Build NPC card effect database from EQEmu entity data (auto-generate effects for all entities on server start)

### Phase 6: Race & Culture (Weeks 21–24)

- [x] Implement orc as new playable race (race table, starting stats, character model)
- [x] Redesign Crushbone as orc starting city (NPCs, merchants, quest givers)
- [x] Implement cultural behavioral biases in agent soul documents
- [x] Create race-specific quest content reflecting cultural values
- [x] Implement cultural faction alignment motivation layer
- [x] Test agent cultural personality across all race templates

### Phase 7: Stream & Polish (Weeks 25–28)

- [x] Build OBS overlay plugin for Murphy events
- [x] Implement agent thought bubble visualization
- [x] Build faction war map overlay
- [x] Duel highlight auto-capture
- [x] End-to-end stream testing

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
| **Sorceror Balance** | Target DPS range relative to monks and mages at each tier |
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
| **Perception pipeline latency** | Tick rate too slow for real-time combat | Lightweight inference for routine combat (no LLM); LLM reserved for complex social decisions |
| **Lore-seed data quality** | Incomplete or inconsistent NPC data from EQEmu DB | Validation pass on import, fallback templates for missing data, manual curation for key NPCs |
| **Sleeper event imbalance** | Dragon faction rally makes event impossible or trivial | Tunable rally response delay, cap on concurrent dragon reinforcements, engaged-elsewhere exemption |
| **Card economy exploitation** | Players farming god cards to gain disproportionate power | Card drop rate tuning, no-drop/lore restrictions, long void spell cooldown, server announcements create social counterplay |
| **Unmaker spawn abuse** | Camping or exploiting The Unmaker's random spawn | Truly random spawn with 1% chance, level 1 fragility means ambient kills, max 2 drops per kill |
| **Void spell world damage** | Permanent deletion of critical NPCs or quest givers | Long cooldown, limited charges, player exception rule, server backup/restore for extreme cases |
| **PvP raid boss imbalance** | Player-turned-god is unkillable or trivial | Stat scaling balanced to require full raid, god abilities on cooldowns, player retains mortality on death |
| **Banned by the Unmaker abuse** | Players locked out of game for 2 days causes frustration | Very low proc rate (~1%), voluntary encounter (players choose to enter Tower of the Unmaker), ban duration tunable |
| **Item disintegration grief** | Permanent gear loss discourages raiding the Unmaker | Clear warnings before entering Core zone, risk-reward design (4th Card is ultimate power), gear insurance NPC possible |
| **Random raid attack chaos** | 30% proc rate of random raid attacks makes fight impossible | Tunable proc rate, raid composition diversity rewarded, survival-based design (not DPS race) |
| **World entropy too fast** | Critical NPCs deleted early, breaking quest lines and economy | Card drop rates throttled, Unmaker 1% spawn rate limits conversion speed, deletions announced server-wide for social counterplay |
| **Server reboot grief** | Player collects 4 Unmaking cards and reboots against community wishes | Server-wide countdown with warning, 3rd-card enchanted items survive to soften impact, reboot creates fresh start with carry-forward relics |
| **Unmaker player imbalance** | Player-Unmaker with 100% AA XP and full gear dominates server | Player-Unmaker is a high-value target (huntable), death removes title, title must be re-earned via Core raid |
| **Unmaking escalation overwhelm** | Army/dragon/god response makes holding Cards of Unmaking impossible | 3-day timer gives holder time to trade cards, origin NPC summons provide defense, hold-vs-trade choice creates strategic depth |
| **Origin summon depopulation** | Summoning origin NPCs strips home city of defenders and merchants | Never-summoned-before rule limits pool, NPCs return when cards traded, zone repopulation on summon expiry |
| **Crushbone level 40–60 rebalance** | Redesigned Crushbone disrupts orc leveling path | Maintain separate low-level tutorial zone, Crushbone merchant city is endgame destination, not starter area |
| **Card cooldown too long/short** | 1-week cooldown makes cards feel useless, or too short allows spam | Tunable cooldown duration, passive abilities exempt (Shield/Disintegration always active while held), cooldown visible in UI |
| **50% decay vote manipulation** | Players or agents manipulate vote outcome | Simple majority rule, AI agents vote independently based on soul document, vote requires 50%+ decay threshold |
| **AI vote awareness** | AI agents realize they are voting on a meta-game event (breaks fourth wall) | Vote framed as in-game lore event ("Should the world be remade?"), agents vote based on faction/deity alignment, no system-level awareness |
| **Lore fidelity spiral** | Gossip distortion makes all shared lore unreliable | Fidelity floor (minimum 50% accuracy after distortion), first-hand memories always 100% accurate, agents can verify by re-encountering entities |
| **Agent streaming privacy** | Streaming agent perspective reveals other players' strategies | Streaming agents are publicly marked, players can avoid streaming agents, stream delay configurable |
| **TTS voice quality** | Low-quality TTS breaks immersion for streamed agents | Pre-selected high-quality voice profiles, limited roster ensures quality over quantity, voice profiles tuned per archetype |
| **Tower entry accessibility** | Entry requirement too easy or too hard | Two paths: 1 Card of Unmaking (requires trading 4 cards to Unmaker) or 4 same-type universal cards (no trade required). Both require meaningful progression. Tunable via card drop rates |
| **Soul-bound protector imbalance** | High-level protectors (e.g., Emperor Crush, Lord Nagafen) are too powerful as permanent companions | Protector level matches entity level (not holder level), protector uses entity's normal combat abilities (no scaling), faction penalty makes cities hostile |
| **AI player aggression spiral** | All named NPCs attacking soul-binder on sight makes game unplayable for protector holders | Intended design — soul-binding is a high-risk high-reward choice. Holder can release protector to restore faction (with permanent scar). The social cost is the balancing mechanism |
| **NPC card effect volume** | Thousands of entities need unique 4-tier card effects — manual design impractical | Identity template system auto-generates effects from entity properties (weapon type, level, combat style). Manual curation only for iconic named NPCs like Emperor Crush |
| **Named creature AI player load** | Giving all named creatures full AI soul documents creates server performance pressure | Named creature AI activates on proximity — distant named NPCs use simplified behavior. Full AI only loads when players or other named NPCs are nearby |
| **Silent card transfer exploitation** | Groups deliberately farm 3-card holders with zero-card alts to funnel cards | Only actual combat participants eligible for redistribution, minimum damage threshold required, anti-farming detection flags rapid repeated transfers |
| **3-card attackable griefing** | Players repeatedly killed at 3 cards before they can reach Tower of the Unmaker | Origin city/faction zone allies protect the holder, 3-day escalation timer gives planning window, holder can choose to trade cards for Shield/Void instead of holding |
| **Sub-60 level cap feels arbitrary** | Players confused by why sub-60 entities cap at 3 cards | Clear UI messaging when approaching cap, lore explanation ties it to entity soul strength (weaker souls produce limited unmaking power) |

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
