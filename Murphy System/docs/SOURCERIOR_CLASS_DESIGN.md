# Sourcerior Class Design

**Murphy System — Experimental EverQuest Class Specification**
**Version:** 1.0.0
**Date:** 2026-03-01
**Status:** Experimental / Draft
**Parent:** `EXPERIMENTAL_EVERQUEST_MODIFICATION_PLAN.md`

---

## 1. Class Identity

**Name:** Sourcerior
**Archetype:** Monk / Mage Hybrid
**Primary Role:** Melee DPS with AE Proc Utility and Pet Support
**Secondary Role:** Minor Crowd Control (AE Mez), Group Buffs via Procs

The Sourcerior blends **monk martial discipline** with **arcane fire magic**, channeling power through melee strikes that trigger damaging AE procs. Instead of casting directly, the Sourcerior fights up close and lets magic flow through combat — procs replace kicks for DPS, fire elementals provide sustained damage, and song-like buffs proc passively to support the group.

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

### 2.3 Pet System — Fire Elementals

The Sourcerior summons **minor fire elementals** — up to 6 active at once. Pets are low HP but deal decent damage scaled to the level of the summoning spell.

| Summon Spell | Level | Pet Level | Max HP | Damage/Round | Notes |
|---|---|---|---|---|---|
| **Summon: Spark** | 4 | 4 | 50 | 5–8 | First pet, very basic |
| **Summon: Ember Wisp** | 12 | 12 | 120 | 12–18 | Can be summoned alongside Spark |
| **Summon: Flame Sprite** | 22 | 22 | 250 | 25–35 | Unlocks 3-pet maximum |
| **Summon: Fire Mote** | 32 | 32 | 400 | 40–55 | Unlocks 4-pet maximum |
| **Summon: Blaze Imp** | 42 | 42 | 600 | 60–80 | Unlocks 5-pet maximum |
| **Summon: Inferno Minion** | 52 | 52 | 850 | 85–110 | Unlocks 6-pet maximum |

**Pet behavior:**
- Pets auto-attack the Sourcerior's target
- Pets have no special abilities beyond melee (they are "minor" elementals)
- Pets persist until killed or dismissed
- Summoning a pet while at max count replaces the lowest-level pet
- All pets benefit from the Sourcerior's proc-based pet buffs

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

---

## 3. Level Scaling Matrix

The Sourcerior scales from mostly-monk at low levels to a fully hybrid class at high levels:

| Level Range | Monk Skills | Proc DPS | Pets | CC | Song Procs | Identity |
|---|---|---|---|---|---|---|
| **1–10** | Primary focus | Minor (1 proc) | 1 pet | None | Ember Tempo | "Monk with a spark" |
| **11–20** | Strong base | 2 procs available | 2 pets | Daze of Embers | Flame Vigor | "Monk with fire magic" |
| **21–30** | Full monk kit | 3 procs, notable DPS | 3 pets | Daze of Embers | Soulfire Resonance | "True hybrid emerging" |
| **31–40** | Monk + riposte | 4 procs, strong AE | 4 pets | Flame Stupor | Pyretic Ward | "Fire-channeling monk" |
| **41–50** | Triple attack | 5 procs, heavy AE | 5 pets | Flame Stupor | Inferno Chorus | "Sourcerior comes online" |
| **51–60** | Full monk power | All 6 procs, peak AE | 6 pets | Inferno Trance | Blaze Anthem | "Full Sourcerior" |

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
| 4 | Tiger Claw, Summon: Spark |
| 6 | Ember Strike (proc) |
| 8 | Round Kick |
| 10 | Ember Tempo (song proc), Sacrifice: Spark |
| 12 | Summon: Ember Wisp |
| 13 | Dual Wield |
| 14 | Flame Lash (proc) |
| 15 | Eagle Strike |
| 16 | Double Attack |
| 17 | Flame Blink I |
| 18 | Flame Vigor (pet heal proc) |
| 20 | Flying Kick, Daze of Embers (AE mez) |
| 22 | Summon: Flame Sprite |
| 24 | Sacrifice: Flame |
| 25 | Dragon Punch, Riposte |
| 26 | Inferno Burst (proc) |
| 28 | Soulfire Resonance (ATK proc) |
| 32 | Summon: Fire Mote |
| 34 | Flame Stupor (AE mez) |
| 35 | Flame Blink II |
| 36 | Pyretic Ward (AC proc) |
| 38 | Soulfire Cascade (proc) |
| 40 | Sacrifice: Inferno |
| 42 | Summon: Blaze Imp |
| 44 | Inferno Chorus (haste proc) |
| 46 | Triple Attack |
| 48 | Inferno Trance (AE mez) |
| 50 | Pyre Storm (proc), Flame Blink III |
| 52 | Summon: Inferno Minion |
| 54 | Blaze Anthem (group buff proc) |
| 55 | Sacrifice: Conflagration |
| 60 | Arcane Conflagration (proc) |

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

- Can wear **leather** armor (like monks)
- Can use **hand-to-hand** weapons, **1H blunt**, **1H slash**
- Cannot use **shields** (dual wield focus)
- Can use **range slot** for stat items
- Weight restrictions similar to monk (heavy gear reduces effectiveness)

---

*Copyright © 2020 Inoni Limited Liability Company*
*Creator: Corey Post*
*License: Apache License 2.0*
