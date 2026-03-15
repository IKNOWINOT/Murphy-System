# Sorceror Class Design

**Murphy System — Experimental EverQuest Class Specification**
**Version:** 2.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Parent:** `EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`

---

## 1. Class Identity

**Name:** Sorceror
**Archetype:** Monk / Mage Hybrid — Primarily a Damage Class
**Primary Role:** Melee DPS with AE Proc Damage
**Secondary Role:** Avoidance Tanking (emergency, Defensive Disc duration via pets), Situational Utility (AE Mez, Group Procs, Pet Support, Meld Tanking)
**Eligible Races:** Dark Elf, Erudite, Human, High Elf, Gnome (int caster races)

The Sorceror is **primarily a damage class** with a wide toolkit of **situational utility** and a unique **avoidance tanking** capability. It blends **monk martial discipline** with **arcane elemental magic**, channeling power through melee strikes that trigger damaging procs. Instead of casting directly, the Sorceror fights up close and lets magic flow through combat — procs replace kicks for DPS, elementals provide sustained damage, and song-like buffs proc passively to support the group.

**Avoidance tank identity:** The Sorceror can tank like a warrior by leveraging its many different pets and avoidance skills. When a warrior falls, the Sorceror activates **Discipline of Rumblecrush** (see section 2.10) — a tanking disc that lasts the same duration as a warrior's **Defensive Discipline** (~180 seconds). During Rumblecrush, the Sorceror's pets gain Defensive-like mitigation (massive AC boost, damage reduction), while the Sorceror cycles pets to absorb hits and relies on monk-level dodge/riposte for personal avoidance. This holds a mob **longer than a ranger, paladin, or shadow knight** could manage. The disc burns through mana rapidly (every proc costs mana while active), making **beastlord** partners essential for mana sustain.

**Hybrid identity:** While the Sorceror touches many roles — emergency CC, minor group buffs, avoidance pet tanking via meld — its core identity is **damage output**. The utility is situational: AE mez for emergencies, haste procs when they fire, earth meld tanking when the main tank drops. A Sorceror who isn't dealing damage isn't fulfilling their role. The situational utility makes the Sorceror adaptable, not a replacement for dedicated support or tank classes.

**Weapon philosophy — the slower, the better:** The Sorceror has **higher proc modifiers than any other class**. Slow, high-damage weapons maximize the value of each proc trigger. Every melee hit has a chance to fire one or more elemental procs, and the Sorceror's innate proc modifier bonus ensures more procs per hit than other classes would see with the same weapon. Two-handed staves with very slow delay and high base damage are the optimal weapon type.

**Single-element rule:** The Sorceror can only have **one type of elemental pet active at a time** — all fire, all earth, all air, or all water. Mixed-element pet groups are forbidden unless the Sorceror has acquired the **Lord of the Maelstrom** discipline (see section 2.11), a level 60 raid-dropped ability from the final Plane of Sky boss that lifts this restriction.

---

## 2. Core Ability Categories

### 2.1 Melee Foundation (Monk Skills)

The Sorceror's primary combat is **monk-style melee**:

| Ability | Level | Description |
|---|---|---|
| **Hand-to-Hand** | 1 | Base melee skill, scales with level |
| **Tiger Claw** | 4 | Fast melee strike, chance to proc fire damage |
| **Round Kick** | 8 | Moderate damage kick, replaced by procs at higher levels |
| **Flying Kick** | 20 | High-damage gap closer |
| **Eagle Strike** | 15 | Fast double-strike with proc chance |
| **Dragon Punch** | 25 | Heavy single-target strike |
| **Dual Wield** | 13 | Can wield two one-handed weapons |
| **Double Attack** | 16 | Chance to strike twice per round |
| **Triple Attack** | 46 | Chance to strike three times per round |
| **Dodge** | 1 | Passive avoidance, scales with level |
| **Riposte** | 25 | Counter-attack on successful parry |

### 2.2 Proc-Based DPS System

The Sorceror's defining mechanic: **melee attacks trigger elemental procs** instead of relying on kicks for secondary damage. Each proc has a chance to fire on any melee hit. The Sorceror has **higher innate proc modifiers than any other class** — slower weapons with higher base damage yield even more procs, making two-handed staves the ideal weapon.

**Fire Procs — AC/Damage Shield line:**

Fire procs grant the Sorceror and nearby group members defensive bonuses — AC increases and damage shields that punish attackers.

| Proc | Level | Trigger | Effect |
|---|---|---|---|
| **Ember Strike** | 6 | Melee hit (10% chance) | 20–50 fire damage AE + self DS (3 per hit) for 12s |
| **Flame Lash** | 14 | Melee hit (12% chance) | 40–100 fire damage AE + self DS (8 per hit) + AC +5 for 18s |
| **Inferno Burst** | 26 | Melee hit (10% chance) | 80–200 fire damage AE + self DS (15 per hit) + AC +10 for 18s |
| **Soulfire Cascade** | 38 | Melee hit (8% chance) | 150–350 fire damage AE + self DS (25 per hit) + AC +15 for 24s |
| **Pyre Storm** | 50 | Melee hit (8% chance) | 300–600 fire damage AE + group DS (20 per hit) + AC +20 for 24s |
| **Arcane Conflagration** | 60 | Melee hit (6% chance) | 500–900 fire damage AE + group DS (35 per hit) + AC +30 for 30s |

**Earth Procs — Root/Rune (damage absorption) line:**

Earth procs provide crowd control via roots and defensive runes that absorb incoming damage.

| Proc | Level | Trigger | Effect |
|---|---|---|---|
| **Stone Grasp** | 8 | Melee hit (8% chance) | Root target 6s + self rune absorbing 50 damage |
| **Earthen Snare** | 18 | Melee hit (10% chance) | Root target 8s + self rune absorbing 120 damage |
| **Tremor Bind** | 30 | Melee hit (8% chance) | Root target 10s + self rune absorbing 250 damage |
| **Bedrock Shackle** | 42 | Melee hit (7% chance) | Root target 12s + self rune absorbing 400 damage + group rune 100 |
| **Tectonic Cage** | 54 | Melee hit (6% chance) | Root target 14s + self rune absorbing 600 damage + group rune 200 |

**Proc modifier design:**
- The Sorceror has a **class-innate proc modifier** that is higher than any other class
- Proc chance scales with weapon delay: **slower weapons = more procs per swing** due to the higher base proc rate per hit
- With a very slow two-handed staff (delay 50+), the Sorceror procs significantly more often than a dual-wielding rogue with the same proc effect
- Focus effects on gear can further improve proc rates
- During **Discipline of Rumblecrush** (section 2.10), every proc costs mana — this is the trade-off for the elevated proc rate

### 2.3 Pet System — Elemental Companions

The Sorceror summons **minor elementals** of four types — up to 6 active at once. Pets are low HP but deal decent damage scaled to the level of the summoning spell. Each element has a distinct combat role that becomes critical during **Invoke Pet / Meld** (see section 2.8).

**Single-element rule:** The Sorceror can only have **one type of elemental pet active at a time**. All active pets must be the same element — all fire, all earth, all air, or all water. Summoning a pet of a different element than those currently active will **dismiss all existing pets** before summoning the new one. This forces the player to commit to an element for their current encounter and choose wisely.

The single-element restriction is lifted only by **Lord of the Maelstrom** (see section 2.11) — a level 60 discipline obtained as a raid drop from the final Plane of Sky boss. With Lord of the Maelstrom active, the Sorceror may summon and maintain pets of **any combination of elements** simultaneously.

| Summon Spell | Level | Element | Pet Level | Max HP | Damage/Round | Notes |
|---|---|---|---|---|---|---|
| **Summon: Spark** | 4 | Fire | 4 | 50 | 5–8 | First pet, very basic |
| **Summon: Dust Devil** | 8 | Air | 8 | 45 | 7–10 | Fast attacks, lower HP |
| **Summon: Ember Wisp** | 12 | Fire | 12 | 120 | 12–18 | Unlocks 3-pet maximum |
| **Summon: Stone Mote** | 16 | Earth | 16 | 180 | 8–12 | High HP, taunts on spawn |
| **Summon: Flame Sprite** | 22 | Fire | 22 | 250 | 25–35 | Unlocks 4-pet maximum |
| **Summon: Tidal Wisp** | 26 | Water | 26 | 200 | 18–28 | Boosts magic crit nearby |
| **Summon: Fire Mote** | 32 | Fire | 32 | 400 | 40–55 | Unlocks 5-pet maximum |
| **Summon: Gale Sprite** | 36 | Air | 36 | 320 | 45–60 | Fast, flanking attacks |
| **Summon: Blaze Imp** | 42 | Fire | 42 | 600 | 60–80 | Unlocks 6-pet maximum |
| **Summon: Boulder Imp** | 46 | Earth | 46 | 750 | 35–50 | Highest HP pet, taunts |
| **Summon: Inferno Minion** | 52 | Fire | 52 | 850 | 85–110 | Strongest fire pet |
| **Summon: Torrent Minion** | 56 | Water | 56 | 700 | 70–95 | Strongest water pet |

**Elemental types and roles:**

| Element | HP | Damage | Special Trait | Meld Aspect |
|---|---|---|---|---|
| **Earth** | Highest | Low | Taunts on spawn, high AC | HP boost + taunt |
| **Air** | Lowest | High | Fast attack speed, flanking | Backstab |
| **Fire** | Medium | Highest | Damage shield aura | DS + area burn |
| **Water** | Medium | Medium | Magic crit aura nearby | Crit magic |

**Pet behavior:**
- Pets auto-attack the Sorceror's target
- Each element has a passive special trait active while summoned
- Pets persist until killed or dismissed
- Summoning a pet while at max count replaces the lowest-level pet
- All pets benefit from the Sorceror's proc-based pet buffs
- Pets can be consumed via **Invoke Pet / Meld** (section 2.8) or **Sacrifice** (section 2.7)

### 2.4 Flame Blink (Replaces Feign Death)

Where monks have **Feign Death** to drop aggro, the Sorceror has **Flame Blink** — a forward teleport that drops aggro and leaves behind fire elementals.

| Ability | Level | Cooldown | Effect |
|---|---|---|---|
| **Flame Blink I** | 17 | 90s | Blink 30 units forward, release 1 elemental that roots and taunts |
| **Flame Blink II** | 35 | 75s | Blink 40 units forward, release 2 elementals that root and taunt |
| **Flame Blink III** | 50 | 60s | Blink 50 units forward, release 3 elementals that root and taunt |

**Mechanics:**
- The blink is a **forward teleport** in the direction the Sorceror is facing
- The released elementals are **temporary** (30-second duration)
- Released elementals immediately cast **root** on the nearest enemy
- Released elementals immediately cast **taunt** to pull aggro from the Sorceror
- This serves the same tactical purpose as feign death — drop aggro and reposition
- The root+taunt elementals buy time for the Sorceror to recover or reposition

### 2.5 AE Mez Spells (Enchanter Category)

The Sorceror gets **minor AE mesmerize spells** from the enchanter spell category. These are weaker and shorter duration than enchanter equivalents.

| Spell | Level | Duration | Max Targets | Resist Modifier |
|---|---|---|---|---|
| **Daze of Embers** | 20 | 12s | 3 | −10 (easier to resist than enchanter) |
| **Flame Stupor** | 34 | 18s | 4 | −15 |
| **Inferno Trance** | 48 | 24s | 5 | −20 |

**Limitations:**
- Shorter duration than enchanter equivalents at the same level
- Fewer max targets
- Easier to resist (negative resist modifier)
- Cannot be chained as reliably as enchanter CC
- Intended as **emergency crowd control**, not primary CC role

### 2.6 Bard Proc Line (Song-Like Procs — Overhaste / Buff / Heal)

The Sorceror passively procs effects from the **bard spell line** that benefit the group. These function like bard songs but are triggered by melee hits rather than sung continuously. The Sorceror draws from the same overhaste, buff, and heal categories that bards use, but at reduced potency. Bard lines of the same level should **always be stronger** than these effects.

| Proc | Level | Trigger | Bard Line Equivalent | Effect | Duration |
|---|---|---|---|---|---|
| **Ember Tempo** | 10 | Melee hit (5% chance) | Anthem de Arms (haste line) | Group haste +10% (overhaste-capable) | 18s |
| **Flame Vigor** | 18 | Melee hit (5% chance) | Hymn of Restoration (heal line) | AE pet heal (50–100 HP) | Instant |
| **Soulfire Resonance** | 28 | Melee hit (4% chance) | War March line (ATK line) | Group ATK buff +15 | 24s |
| **Pyretic Ward** | 36 | Melee hit (4% chance) | Guardian Rhythms (AC line) | Group AC buff +10 | 24s |
| **Inferno Chorus** | 44 | Melee hit (3% chance) | Vilia's Chorus (haste line) | Group haste +15% (overhaste-capable) | 24s |
| **Blaze Anthem** | 54 | Melee hit (3% chance) | Combined War March + Chorus | Group ATK +25, AC +15, haste +18% | 30s |

**Overhaste behavior:**
- The haste component stacks as **overhaste** — similar to bard haste
- Stacks with normal haste items/spells up to the overhaste cap
- A bard song of the same level should provide **more haste** than these procs
- The value is in the combination: the Sorceror contributes melee DPS AND occasional bard-like procs
- Proc chance means these are **unreliable** compared to bard's continuous singing

**AE Pet Heal:**
- Heals **all** of the Sorceror's pets in AE radius
- Also heals other group member pets (magician, necromancer, beastlord pets)
- Heal amount scales with spell level but is modest compared to cleric heals

### 2.7 Sacrifice Pets — Nuke for Mobility

The Sorceror can **consume active pets** to release their energy as a direct damage nuke. This is primarily used when movement is required — sacrifice the pets, nuke the target, reposition, resummon later.

| Ability | Level | Effect | Damage per Pet |
|---|---|---|---|
| **Sacrifice: Spark** | 10 | Consumes all active pets, deals fire damage per pet | 50–80 per pet consumed |
| **Sacrifice: Flame** | 24 | Consumes all active pets, deals fire damage per pet | 120–180 per pet consumed |
| **Sacrifice: Inferno** | 40 | Consumes all active pets, deals fire damage per pet | 250–350 per pet consumed |
| **Sacrifice: Conflagration** | 55 | Consumes all active pets, deals fire damage per pet | 400–550 per pet consumed |

**Mechanics:**
- Consumes **all** currently active pets in a single cast
- Total damage = (damage per pet) × (number of pets consumed)
- With 6 pets at level 55: potential nuke of 2400–3300 damage
- **Primary use case**: Need to move, can't keep pets alive during transition
- Instant cast — can be used while running
- After sacrifice, pets must be resummoned (mana cost, cast time)

### 2.8 Invoke Pet — Elemental Meld System

The Sorceror's signature advanced mechanic: **Invoke Pet** allows the player to **meld with one of their active pets**, absorbing it and gaining its elemental aspect as a temporary personal buff. The meld lasts until cancelled or the duration expires. Only one meld can be active at a time; invoking a new meld replaces the current one. The pet is consumed on meld.

**Meld aspects by element:**

| Invoke Spell | Level | Element | Meld Aspect | Duration |
|---|---|---|---|---|
| **Invoke: Earth** | 20 | Earth | +25% max HP, gains **Taunt** ability, +20 AC | 120s |
| **Invoke: Air** | 24 | Air | Gains **Backstab** ability (30% bonus from behind), +15% attack speed | 120s |
| **Invoke: Fire** | 28 | Fire | Gains **Damage Shield** (15–40 per hit taken), **Area Burn** AE pulse (50–120 fire, 6s tick) | 120s |
| **Invoke: Water** | 32 | Water | +15% **Critical Magic** chance on all procs and spells, +10% mana regen | 120s |

**Higher-rank melds (scale with pet level used):**

| Invoke Spell | Level | Element | Enhanced Aspect | Duration |
|---|---|---|---|---|
| **Invoke: Greater Earth** | 40 | Earth | +40% max HP, Taunt, +35 AC, minor regen | 150s |
| **Invoke: Greater Air** | 42 | Air | Backstab (45% bonus), +25% attack speed, minor dodge | 150s |
| **Invoke: Greater Fire** | 44 | Fire | DS (30–70), Area Burn AE (100–220, 6s tick), fire resist aura | 150s |
| **Invoke: Greater Water** | 46 | Water | +25% Crit Magic, +20% mana regen, minor spell haste | 150s |

**Meld mechanics:**
- The melded pet is **consumed** — it disappears and its power merges with the Sorceror
- Only **one meld** can be active at a time; invoking a new element replaces the current meld
- The Sorceror can meld with **whatever elemental pets their current level spells allow**
- Meld potency scales with the **level of the pet consumed** — higher-level pets yield stronger aspects
- **Base weapon damage** affects meld effectiveness: higher base DMG on equipped weapon amplifies meld bonuses (see section 2.9 — Epic Weapon)
- During meld, the Sorceror's appearance shifts to reflect the element (stone skin, wind aura, fire glow, water shimmer)
- Meld can be cancelled early; the pet is still consumed

**Tactical usage:**
- **Earth Meld** for tanking or emergency survival — high HP + taunt pulls aggro off healers
- **Air Meld** for burst DPS — backstab + attack speed is devastating from behind mobs
- **Fire Meld** for AE situations — damage shield + area burn in conjunction with AE procs
- **Water Meld** for magic-heavy phases — crit magic boosts all proc damage significantly

### 2.9 Epic Weapon — Staff of Converging Souls

The Sorceror's epic weapon is a **very slow two-handed staff with heavy base damage**. It is the strongest pet focus item in the game for the Sorceror and directly amplifies the Invoke Pet / Meld system.

**Staff of Converging Souls**

| Stat | Value |
|---|---|
| **Type** | Two-Handed Blunt (Staff) |
| **Damage** | 65 |
| **Delay** | 52 (very slow) |
| **Ratio** | 1.25 (excellent for procs) |
| **AC** | 25 |
| **STR** | +25 |
| **AGI** | +20 |
| **STA** | +20 |
| **INT** | +15 |
| **HP** | +150 |
| **Mana** | +100 |
| **Effect: Convergence** | Meld duration +30%, meld potency +25% |
| **Effect: Soul Focus** | Pet damage +15%, pet HP +10% |
| **Proc: Elemental Confluence** | On melee hit (5%): 200–400 damage matching active meld element |
| **Lore** | *"Four elements bound by discipline, channeled through the one who walks between worlds."* |

**Why base damage matters for meld:**
- Meld effectiveness scales with the **base damage** of the Sorceror's equipped weapon
- Higher base DMG = stronger meld aspect bonuses (HP multiplier, backstab damage, DS value, crit chance)
- The very slow speed / high damage design of staves maximizes this scaling
- This makes **two-handed staves** the Sorceror's optimal weapon class
- The epic staff has the highest base damage of any Sorceror-usable weapon, making it the best meld amplifier

**Epic quest design — combines Monk and Mage epic difficulty:**

The epic quest mirrors the difficulty and scope of both the Monk epic (Celestial Fists) and the Mage epic (Orb of Mastery):

| Phase | Monk Parallel | Mage Parallel | Sorceror Quest |
|---|---|---|---|
| **Phase 1** | Headband of the Celestials gathering | Elemental focus gathering | Gather four elemental essences from planar bosses |
| **Phase 2** | Robe of the Whistling Fists fight | Power of the Elements combines | Meld with each element in specific trial encounters |
| **Phase 3** | Celestial Fists final combine | Orb of Mastery final fight | Defeat a quad-elemental boss while cycling all four melds |
| **Phase 4** | — | — | Final combine: four essences + pristine staff blank + soul gem |

**Quest difficulty:**
- Requires access to Planes of Power zones
- Multiple raid-level boss encounters
- Solo trial encounters testing mastery of each meld element
- Final combine requires tradeskill (smithing 200+) for the staff blank
- Similar total time investment to Monk and Mage epics

### 2.10 Discipline of Rumblecrush — Emergency Tanking Disc

The Sorceror's signature tanking ability. **Discipline of Rumblecrush** is a discipline (not a spell) that transforms the Sorceror and their pets into an emergency tanking unit for the **same duration as a warrior's Defensive Discipline** (~180 seconds). The tanking power is split between the Sorceror's personal avoidance and a **Defensive-like buff on all active pets**.

| Disc Rank | Level | Duration | Reuse | Effect |
|---|---|---|---|---|
| **Rumblecrush I** | 30 | 120s | 30 min | Pets gain +200 AC, 25% damage reduction; Sorceror +15% dodge; procs cost 10 mana each |
| **Rumblecrush II** | 45 | 150s | 25 min | Pets gain +350 AC, 35% damage reduction; Sorceror +20% dodge; procs cost 15 mana each |
| **Rumblecrush III** | 55 | 180s | 20 min | Pets gain +500 AC, 50% damage reduction, auto-taunt; Sorceror +25% dodge, +15% riposte; procs cost 20 mana each |

**Defensive mechanic on pets:**
- While Rumblecrush is active, all summoned pets gain a **Defensive Discipline-equivalent buff** — massive AC increase and percentage-based damage reduction
- Pets with the Defensive buff become comparable to a warrior in Defensive Discipline for damage mitigation
- Earth pets (which already taunt on spawn) become especially effective tanks during Rumblecrush — high base HP + Defensive buff + auto-taunt
- At Rank III, **all** pets gain auto-taunt regardless of element, locking mobs onto the pet army
- The Sorceror cycles through pets as they absorb damage — when one drops, the next picks up aggro

**Mana-drain mechanic:**
- While Rumblecrush is active, **every proc that fires costs mana** — fire procs, earth procs, song procs, all of them
- This is the trade-off: the Sorceror's elevated proc modifier (which is an advantage for DPS) becomes a **mana drain** during tanking
- Rumblecrush runs until the duration expires **or** the Sorceror runs out of mana, whichever comes first
- A Sorceror with a large mana pool and slow weapon can sustain the full 180s at Rank III
- A Sorceror with a fast weapon and low mana will drain faster due to more procs per second

**Beastlord synergy:**
- Beastlords provide **Paragon of Spirit** (mana regen) and **Spiritual Channeling** which directly extend Rumblecrush's effective duration
- A Sorceror + beastlord pair is the ideal emergency tanking duo: the beastlord feeds mana, the Sorceror's pets hold the mob
- Without a beastlord, Rumblecrush drains mana in roughly 60–90 seconds; with beastlord mana sustain, the Sorceror can hold for the full disc duration

**Comparison to warrior Defensive Discipline:**

| Aspect | Warrior Defensive | Sorceror Rumblecrush III |
|---|---|---|
| **Duration** | ~180s | ~180s (same) |
| **Mitigation** | Personal near-immunity | Pets gain 50% DR + 500 AC; Sorceror dodges |
| **Taunt** | Warrior taunts personally | Pets auto-taunt (mob stays on pet army) |
| **Cost** | No resource cost | Every proc drains mana |
| **Weakness** | Warrior takes all hits personally | Pets can die — must cycle replacements |
| **Sustain** | Self-sufficient | Needs beastlord for mana to last full duration |

### 2.11 Lord of the Maelstrom — Mixed-Element Unlock

**Lord of the Maelstrom** is a level 60 discipline that lifts the single-element pet restriction, allowing the Sorceror to summon and maintain pets of **all four elements simultaneously**. It is obtained as a **raid drop from the final boss of the Plane of Sky** (the Island of the Windlord / Eye of Veeshan encounter).

| Stat | Value |
|---|---|
| **Type** | Discipline (passive, permanent once acquired) |
| **Level Requirement** | 60 |
| **Source** | Raid drop — final Plane of Sky boss |
| **Effect** | Permanently removes the single-element pet restriction |
| **Lore** | *"Master of all elements, the Maelstrom bows to none."* |

**Mechanics:**
- Once acquired, the Sorceror can freely mix earth, air, fire, and water pets in any combination
- This enables tactical pet armies: earth pets tanking in front, fire pets dealing damage, water pets boosting magic crit, air pets flanking
- The discipline is a **permanent passive** — it does not need to be activated and has no duration or cooldown
- It is a **lore item / tome** that is consumed on use, permanently flagging the character
- This is the Sorceror's defining endgame unlock — comparable in prestige to completing an epic quest

**Tactical impact:**
- Before Lord of the Maelstrom: The Sorceror must commit to one element per fight, choosing between earth's tanking, fire's damage, water's crit, or air's speed
- After Lord of the Maelstrom: The Sorceror can build mixed-element armies tailored to each encounter — 3 earth tanks + 3 fire DPS, or 2 earth + 2 water + 2 air, etc.
- Combined with Discipline of Rumblecrush, a mixed-element army with earth tanks and fire damage creates the ultimate emergency tanking setup

### 2.12 Liquify — Water Pet Aggro Drop and Invisibility

**Liquify** is the Sorceror's escape ability, available when **water pets are active** starting at level 40. The Sorceror channels the essence of their water elementals to shed aggro and turn invisible — the water pets dissolve momentarily to cloak the Sorceror, then reform.

| Ability | Level | Cooldown | Requirement | Effect |
|---|---|---|---|---|
| **Liquify I** | 40 | 180s | At least 1 water pet active | Instant aggro drop, 18s invisibility (broken by combat or casting) |
| **Liquify II** | 52 | 150s | At least 1 water pet active | Instant aggro drop, 24s invisibility, +15% movement speed while invisible |

**Mechanics:**
- Requires at least one **water elemental pet** to be currently summoned — if only fire, earth, or air pets are active, Liquify is unavailable
- Activating Liquify **does not consume** the water pet — the pet briefly dissolves into the Sorceror, cloaking them, then reforms
- The aggro drop is **complete** — all hate is erased from the Sorceror's target (similar to feign death + memory blur)
- The invisibility effect breaks on any offensive action, casting, or taking damage
- Unlike Flame Blink (which repositions + dumps aggro via fire elementals), Liquify is a **stand-still escape** — the Sorceror becomes invisible in place without moving
- This makes Liquify the ideal **flee tool** during group wipes: drop aggro, go invisible, and walk to safety
- Agents running the Sorceror class template will use Liquify as their primary self-preservation ability when flee conditions are met (see `EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md` section 3.10)

**Comparison to other aggro drops:**

| Class | Ability | Type | Level |
|---|---|---|---|
| **Monk** | Feign Death | Aggro drop (play dead) | 17 |
| **Sorceror** | Flame Blink | Aggro drop + reposition | 17 |
| **Sorceror** | Liquify | Aggro drop + invisibility (requires water pets) | 40 |
| **Enchanter** | Memory Blur | Targeted aggro reset | 24 |
| **Rogue** | Escape | Aggro drop + hide | 40+ |

---

## 3. Level Scaling Matrix

The Sorceror scales from mostly-monk at low levels to a fully hybrid class at high levels:

| Level Range | Monk Skills | Proc DPS | Pets | CC | Song Procs | Meld | Disc / Special | Identity |
|---|---|---|---|---|---|---|---|---|
| **1–10** | Primary focus | Minor (1 fire proc) | 1 pet (single element) | None | Ember Tempo | None | — | "Monk with a spark" |
| **11–20** | Strong base | Fire + Earth procs | 2 pets (single element) | Daze of Embers | Flame Vigor | Earth Meld | — | "Monk with elemental magic" |
| **21–30** | Full monk kit | 3 proc lines, notable DPS | 3 pets (single element) | Daze of Embers | Soulfire Resonance | Earth/Air/Fire Meld | Rumblecrush I | "True hybrid emerging" |
| **31–40** | Monk + riposte | 4 proc lines, strong AE | 4 pets (single element) | Flame Stupor | Pyretic Ward | All 4 Melds | Rumblecrush I | "Fire-channeling monk" |
| **41–50** | Triple attack | 5 proc lines, heavy AE | 5 pets (single element) | Flame Stupor | Inferno Chorus | Greater Melds | Rumblecrush II; Liquify at 40 | "Sorceror comes online" |
| **51–60** | Full monk power | All procs, peak AE | 6 pets (mixed w/ Maelstrom) | Inferno Trance | Blaze Anthem | Full Meld + Epic | Rumblecrush III + Lord of the Maelstrom | "Full Sorceror" |

---

## 4. Comparison with Existing Classes

### 4.1 vs Monk

| Aspect | Monk | Sorceror |
|---|---|---|
| **Melee DPS** | Higher sustained single-target | Lower sustained, higher AE |
| **Survivability** | Feign death (reliable aggro drop) | Flame blink (repositioning + aggro dump) |
| **Utility** | Pulling, splitting | AE CC, pet tanking, group procs |
| **Pets** | None | Up to 6 elementals (single element unless Lord of the Maelstrom) |
| **Group value** | Pure DPS + puller | DPS + minor CC + minor bard-like buffs |

### 4.2 vs Mage

| Aspect | Mage | Sorceror |
|---|---|---|
| **Pet quality** | 1 powerful pet | Up to 6 weak pets |
| **Direct damage** | Strong nukes | Weak nukes (sacrifice only) |
| **Proc damage** | None | Core mechanic |
| **Melee** | Almost none | Primary combat style |
| **Utility** | CoH, DS, pet toys | AE mez, group procs, flame blink |

### 4.3 vs Bard

| Aspect | Bard | Sorceror |
|---|---|---|
| **Song effects** | Continuous, reliable, strong | Proc-based, unreliable, weaker |
| **Haste** | Best overhaste in game | Minor overhaste procs |
| **Melee DPS** | Moderate | High (monk base) |
| **CC** | AE mez (strong) | AE mez (weaker) |
| **Pulling** | Excellent | Good (flame blink) |

---

## 5. Balance Targets

### 5.1 DPS Targets (Relative to Pure Classes)

| Metric | Target | Notes |
|---|---|---|
| **Single-target melee DPS** | 75–85% of monk | Monk base minus some skills |
| **AE proc DPS** | Unique — no direct comparison | Adds 15–25% effective DPS in AE situations |
| **Pet DPS (all 6)** | 50–60% of mage pet | 6 weak pets ≈ half of one strong mage pet |
| **Combined DPS** | 90–100% of monk in sustained | Procs + pets should close the gap with monk |
| **Burst DPS** | 110–120% of monk for 30s | Pet sacrifice + procs + melee burst |

### 5.2 Utility Targets

| Metric | Target | Notes |
|---|---|---|
| **AE mez reliability** | 60–70% of enchanter | Shorter, fewer targets, more resistable |
| **Group haste proc** | 70–80% of bard haste | Unreliable proc vs continuous singing |
| **Group buff procs** | Complementary to bard | Should stack with bard songs, never replace |
| **Pet tanking (Rumblecrush)** | Comparable to warrior Defensive | Rumblecrush III lasts ~180s (same as Defensive Disc); pets gain 50% DR |

---

## 6. Ability Acquisition by Level

| Level | New Abilities |
|---|---|
| 1 | Hand-to-Hand, Dodge |
| 4 | Tiger Claw, Summon: Spark (Fire) |
| 6 | Ember Strike (fire proc) |
| 8 | Round Kick, Summon: Dust Devil (Air), Stone Grasp (earth proc) |
| 10 | Ember Tempo (bard proc — haste), Sacrifice: Spark |
| 12 | Summon: Ember Wisp (Fire) |
| 13 | Dual Wield |
| 14 | Flame Lash (fire proc) |
| 15 | Eagle Strike |
| 16 | Double Attack, Summon: Stone Mote (Earth) |
| 17 | Flame Blink I |
| 18 | Flame Vigor (bard proc — pet heal), Earthen Snare (earth proc) |
| 20 | Flying Kick, Daze of Embers (AE mez), **Invoke: Earth** |
| 22 | Summon: Flame Sprite (Fire) |
| 24 | Sacrifice: Flame, **Invoke: Air** |
| 25 | Dragon Punch, Riposte |
| 26 | Inferno Burst (fire proc), Summon: Tidal Wisp (Water) |
| 28 | Soulfire Resonance (bard proc — ATK), **Invoke: Fire** |
| 30 | **Discipline of Rumblecrush I**, Tremor Bind (earth proc) |
| 32 | Summon: Fire Mote (Fire), **Invoke: Water** |
| 34 | Flame Stupor (AE mez) |
| 35 | Flame Blink II |
| 36 | Pyretic Ward (bard proc — AC), Summon: Gale Sprite (Air) |
| 38 | Soulfire Cascade (fire proc) |
| 40 | Sacrifice: Inferno, **Invoke: Greater Earth**, **Liquify I** (requires water pet) |
| 42 | Summon: Blaze Imp (Fire), **Invoke: Greater Air**, Bedrock Shackle (earth proc) |
| 44 | Inferno Chorus (bard proc — haste), **Invoke: Greater Fire** |
| 45 | **Discipline of Rumblecrush II** |
| 46 | Triple Attack, Summon: Boulder Imp (Earth), **Invoke: Greater Water** |
| 48 | Inferno Trance (AE mez) |
| 50 | Pyre Storm (fire proc), Flame Blink III |
| 52 | Summon: Inferno Minion (Fire), **Liquify II** (requires water pet) |
| 54 | Blaze Anthem (bard proc — group buff), Tectonic Cage (earth proc) |
| 55 | Sacrifice: Conflagration, **Discipline of Rumblecrush III** |
| 56 | Summon: Torrent Minion (Water) |
| 60 | Arcane Conflagration (fire proc), **Lord of the Maelstrom** (raid drop — Plane of Sky) |
| Epic | **Staff of Converging Souls** (epic quest, see section 2.9) |

---

## 7. Stats and Gear

### 7.1 Primary Stats

| Stat | Priority | Reason |
|---|---|---|
| **Strength** | High | Melee damage scaling |
| **Agility** | High | Avoidance, proc chance |
| **Stamina** | Medium | Survivability (melee range) |
| **Intelligence** | Medium | Mana pool for summons, mez, sacrifice |
| **Wisdom** | Low | Minor mana regen contribution |
| **Charisma** | Low | No charm spells |

### 7.2 Gear Restrictions

- Can wear **cloth** and **leather** armor
- Can also equip the **Fungi Tunic** (Fungus Covered Scale Tunic) — the regeneration effect synergizes with the Sorceror's avoidance tanking role and helps sustain during Discipline of Rumblecrush
- **Core weapon: Two-Handed Staves** — primary weapon class, maximizes meld effectiveness via base damage; the slower the weapon, the better due to the Sorceror's elevated proc modifiers
- Can also use **1H slashing** and **1H piercing** weapons (for dual wield builds)
- **Cannot** use 1H blunt weapons
- Can use **range slot** for stat items
- Weight restrictions similar to monk (heavy gear reduces effectiveness)
- **Epic weapon** is a two-handed staff (see section 2.9 — Staff of Converging Souls)

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
