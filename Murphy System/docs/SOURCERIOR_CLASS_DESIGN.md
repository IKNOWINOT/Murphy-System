# Sourcerior Class Design

**Murphy System — Experimental EverQuest Class Specification**
**Version:** 2.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Parent:** `EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`

---

## 1. Class Identity

**Name:** Sourcerior
**Archetype:** Monk / Mage Hybrid — Primarily a Damage Class
**Primary Role:** Melee DPS with AE Proc Damage
**Secondary Role:** Situational Utility (AE Mez, Group Procs, Pet Support, Meld Tanking)

The Sourcerior is **primarily a damage class** with a wide toolkit of **situational utility**. It blends **monk martial discipline** with **arcane fire magic**, channeling power through melee strikes that trigger damaging AE procs. Instead of casting directly, the Sourcerior fights up close and lets magic flow through combat — procs replace kicks for DPS, fire elementals provide sustained damage, and song-like buffs proc passively to support the group.

**Hybrid identity:** While the Sourcerior touches many roles — emergency CC, minor group buffs, pet tanking via meld — its core identity is **damage output**. The utility is situational: AE mez for emergencies, haste procs when they fire, earth meld tanking when the main tank drops. A Sourcerior who isn't dealing damage isn't fulfilling their role. The situational utility makes the Sourcerior adaptable, not a replacement for dedicated support or tank classes.

---

## 2. Core Ability Categories

### 2.1 Melee Foundation (Monk Skills)

The Sourcerior's primary combat is **monk-style melee**:

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

The Sourcerior's defining mechanic: **melee attacks trigger damaging AE procs** instead of relying on kicks for secondary damage. Each proc has a chance to fire on any melee hit.

| Proc | Level | Trigger | Effect |
|---|---|---|---|
| **Ember Strike** | 6 | Melee hit (10% chance) | 20–50 fire damage in small AE radius |
| **Flame Lash** | 14 | Melee hit (12% chance) | 40–100 fire damage in small AE radius |
| **Inferno Burst** | 26 | Melee hit (10% chance) | 80–200 fire damage in medium AE radius |
| **Soulfire Cascade** | 38 | Melee hit (8% chance) | 150–350 fire damage in medium AE radius |
| **Pyre Storm** | 50 | Melee hit (8% chance) | 300–600 fire damage in large AE radius |
| **Arcane Conflagration** | 60 | Melee hit (6% chance) | 500–900 fire damage in large AE radius |

**Scaling notes:**
- Proc damage scales with the level of the Sourcerior
- Proc chance can be improved by focus effects on gear
- AE radius increases at higher tier procs
- Procs **replace kicks** as the primary secondary DPS source at higher levels

### 2.3 Pet System — Elemental Companions

The Sourcerior summons **minor elementals** of four types — up to 6 active at once. Pets are low HP but deal decent damage scaled to the level of the summoning spell. Each element has a distinct combat role that becomes critical during **Invoke Pet / Meld** (see section 2.8).

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
- Pets auto-attack the Sourcerior's target
- Each element has a passive special trait active while summoned
- Pets persist until killed or dismissed
- Summoning a pet while at max count replaces the lowest-level pet
- All pets benefit from the Sourcerior's proc-based pet buffs
- Pets can be consumed via **Invoke Pet / Meld** (section 2.8) or **Sacrifice** (section 2.7)

### 2.4 Flame Blink (Replaces Feign Death)

Where monks have **Feign Death** to drop aggro, the Sourcerior has **Flame Blink** — a forward teleport that drops aggro and leaves behind fire elementals.

| Ability | Level | Cooldown | Effect |
|---|---|---|---|
| **Flame Blink I** | 17 | 90s | Blink 30 units forward, release 1 elemental that roots and taunts |
| **Flame Blink II** | 35 | 75s | Blink 40 units forward, release 2 elementals that root and taunt |
| **Flame Blink III** | 50 | 60s | Blink 50 units forward, release 3 elementals that root and taunt |

**Mechanics:**
- The blink is a **forward teleport** in the direction the Sourcerior is facing
- The released elementals are **temporary** (30-second duration)
- Released elementals immediately cast **root** on the nearest enemy
- Released elementals immediately cast **taunt** to pull aggro from the Sourcerior
- This serves the same tactical purpose as feign death — drop aggro and reposition
- The root+taunt elementals buy time for the Sourcerior to recover or reposition

### 2.5 AE Mez Spells (Enchanter Category)

The Sourcerior gets **minor AE mesmerize spells** from the enchanter spell category. These are weaker and shorter duration than enchanter equivalents.

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

### 2.6 Song-Like Procs (Overhaste / Buff / Heal)

The Sourcerior passively procs **song-like effects** that benefit the group. These function like bard songs but are triggered by melee hits rather than sung continuously. Bard lines of the same level should **always be stronger** than these effects.

| Proc | Level | Trigger | Effect | Duration |
|---|---|---|---|---|
| **Ember Tempo** | 10 | Melee hit (5% chance) | Group haste +10% (overhaste-capable) | 18s |
| **Flame Vigor** | 18 | Melee hit (5% chance) | AE pet heal (50–100 HP) | Instant |
| **Soulfire Resonance** | 28 | Melee hit (4% chance) | Group ATK buff +15 | 24s |
| **Pyretic Ward** | 36 | Melee hit (4% chance) | Group AC buff +10 | 24s |
| **Inferno Chorus** | 44 | Melee hit (3% chance) | Group haste +15% (overhaste-capable) | 24s |
| **Blaze Anthem** | 54 | Melee hit (3% chance) | Group ATK +25, AC +15, haste +18% | 30s |

**Overhaste behavior:**
- The haste component stacks as **overhaste** — similar to bard haste
- Stacks with normal haste items/spells up to the overhaste cap
- A bard song of the same level should provide **more haste** than these procs
- The value is in the combination: the Sourcerior contributes melee DPS AND occasional bard-like procs
- Proc chance means these are **unreliable** compared to bard's continuous singing

**AE Pet Heal:**
- Heals **all** of the Sourcerior's pets in AE radius
- Also heals other group member pets (magician, necromancer, beastlord pets)
- Heal amount scales with spell level but is modest compared to cleric heals

### 2.7 Sacrifice Pets — Nuke for Mobility

The Sourcerior can **consume active pets** to release their energy as a direct damage nuke. This is primarily used when movement is required — sacrifice the pets, nuke the target, reposition, resummon later.

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

The Sourcerior's signature advanced mechanic: **Invoke Pet** allows the player to **meld with one of their active pets**, absorbing it and gaining its elemental aspect as a temporary personal buff. The meld lasts until cancelled or the duration expires. Only one meld can be active at a time; invoking a new meld replaces the current one. The pet is consumed on meld.

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
- The melded pet is **consumed** — it disappears and its power merges with the Sourcerior
- Only **one meld** can be active at a time; invoking a new element replaces the current meld
- The Sourcerior can meld with **whatever elemental pets their current level spells allow**
- Meld potency scales with the **level of the pet consumed** — higher-level pets yield stronger aspects
- **Base weapon damage** affects meld effectiveness: higher base DMG on equipped weapon amplifies meld bonuses (see section 2.9 — Epic Weapon)
- During meld, the Sourcerior's appearance shifts to reflect the element (stone skin, wind aura, fire glow, water shimmer)
- Meld can be cancelled early; the pet is still consumed

**Tactical usage:**
- **Earth Meld** for tanking or emergency survival — high HP + taunt pulls aggro off healers
- **Air Meld** for burst DPS — backstab + attack speed is devastating from behind mobs
- **Fire Meld** for AE situations — damage shield + area burn in conjunction with AE procs
- **Water Meld** for magic-heavy phases — crit magic boosts all proc damage significantly

### 2.9 Epic Weapon — Staff of Converging Souls

The Sourcerior's epic weapon is a **very slow two-handed staff with heavy base damage**. It is the strongest pet focus item in the game for the Sourcerior and directly amplifies the Invoke Pet / Meld system.

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
- Meld effectiveness scales with the **base damage** of the Sourcerior's equipped weapon
- Higher base DMG = stronger meld aspect bonuses (HP multiplier, backstab damage, DS value, crit chance)
- The very slow speed / high damage design of staves maximizes this scaling
- This makes **two-handed staves** the Sourcerior's optimal weapon class
- The epic staff has the highest base damage of any Sourcerior-usable weapon, making it the best meld amplifier

**Epic quest design — combines Monk and Mage epic difficulty:**

The epic quest mirrors the difficulty and scope of both the Monk epic (Celestial Fists) and the Mage epic (Orb of Mastery):

| Phase | Monk Parallel | Mage Parallel | Sourcerior Quest |
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

---

## 3. Level Scaling Matrix

The Sourcerior scales from mostly-monk at low levels to a fully hybrid class at high levels:

| Level Range | Monk Skills | Proc DPS | Pets | CC | Song Procs | Meld | Identity |
|---|---|---|---|---|---|---|---|
| **1–10** | Primary focus | Minor (1 proc) | 1 pet | None | Ember Tempo | None | "Monk with a spark" |
| **11–20** | Strong base | 2 procs available | 2 pets | Daze of Embers | Flame Vigor | Earth Meld | "Monk with fire magic" |
| **21–30** | Full monk kit | 3 procs, notable DPS | 3 pets | Daze of Embers | Soulfire Resonance | Earth/Air/Fire Meld | "True hybrid emerging" |
| **31–40** | Monk + riposte | 4 procs, strong AE | 4 pets | Flame Stupor | Pyretic Ward | All 4 Melds | "Fire-channeling monk" |
| **41–50** | Triple attack | 5 procs, heavy AE | 5 pets | Flame Stupor | Inferno Chorus | Greater Melds | "Sourcerior comes online" |
| **51–60** | Full monk power | All 6 procs, peak AE | 6 pets | Inferno Trance | Blaze Anthem | Full Meld + Epic | "Full Sourcerior" |

---

## 4. Comparison with Existing Classes

### 4.1 vs Monk

| Aspect | Monk | Sourcerior |
|---|---|---|
| **Melee DPS** | Higher sustained single-target | Lower sustained, higher AE |
| **Survivability** | Feign death (reliable aggro drop) | Flame blink (repositioning + aggro dump) |
| **Utility** | Pulling, splitting | AE CC, pet tanking, group procs |
| **Pets** | None | Up to 6 fire elementals |
| **Group value** | Pure DPS + puller | DPS + minor CC + minor bard-like buffs |

### 4.2 vs Mage

| Aspect | Mage | Sourcerior |
|---|---|---|
| **Pet quality** | 1 powerful pet | Up to 6 weak pets |
| **Direct damage** | Strong nukes | Weak nukes (sacrifice only) |
| **Proc damage** | None | Core mechanic |
| **Melee** | Almost none | Primary combat style |
| **Utility** | CoH, DS, pet toys | AE mez, group procs, flame blink |

### 4.3 vs Bard

| Aspect | Bard | Sourcerior |
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
| **Pet tanking** | Emergency only | Flame blink pets root + taunt for 30s max |

---

## 6. Ability Acquisition by Level

| Level | New Abilities |
|---|---|
| 1 | Hand-to-Hand, Dodge |
| 4 | Tiger Claw, Summon: Spark (Fire) |
| 6 | Ember Strike (proc) |
| 8 | Round Kick, Summon: Dust Devil (Air) |
| 10 | Ember Tempo (song proc), Sacrifice: Spark |
| 12 | Summon: Ember Wisp (Fire) |
| 13 | Dual Wield |
| 14 | Flame Lash (proc) |
| 15 | Eagle Strike |
| 16 | Double Attack, Summon: Stone Mote (Earth) |
| 17 | Flame Blink I |
| 18 | Flame Vigor (pet heal proc) |
| 20 | Flying Kick, Daze of Embers (AE mez), **Invoke: Earth** |
| 22 | Summon: Flame Sprite (Fire) |
| 24 | Sacrifice: Flame, **Invoke: Air** |
| 25 | Dragon Punch, Riposte |
| 26 | Inferno Burst (proc), Summon: Tidal Wisp (Water) |
| 28 | Soulfire Resonance (ATK proc), **Invoke: Fire** |
| 32 | Summon: Fire Mote (Fire), **Invoke: Water** |
| 34 | Flame Stupor (AE mez) |
| 35 | Flame Blink II |
| 36 | Pyretic Ward (AC proc), Summon: Gale Sprite (Air) |
| 38 | Soulfire Cascade (proc) |
| 40 | Sacrifice: Inferno, **Invoke: Greater Earth** |
| 42 | Summon: Blaze Imp (Fire), **Invoke: Greater Air** |
| 44 | Inferno Chorus (haste proc), **Invoke: Greater Fire** |
| 46 | Triple Attack, Summon: Boulder Imp (Earth), **Invoke: Greater Water** |
| 48 | Inferno Trance (AE mez) |
| 50 | Pyre Storm (proc), Flame Blink III |
| 52 | Summon: Inferno Minion (Fire) |
| 54 | Blaze Anthem (group buff proc) |
| 55 | Sacrifice: Conflagration |
| 56 | Summon: Torrent Minion (Water) |
| 60 | Arcane Conflagration (proc) |
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
- **Core weapon: Two-Handed Staves** — primary weapon class, maximizes meld effectiveness via base damage
- Can also use **hand-to-hand** weapons, **1H blunt**, **1H slash** (for dual wield builds)
- Can use **range slot** for stat items
- Weight restrictions similar to monk (heavy gear reduces effectiveness)
- **Epic weapon** is a two-handed staff (see section 2.9 — Staff of Converging Souls)

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
