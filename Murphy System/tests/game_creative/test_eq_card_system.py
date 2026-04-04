"""
Tests for the EQ card system implementation modules.

Validates:
  - NPC card effect auto-generation (level scaling, archetype rules, batch gen)
  - Card system (universal/god cards, Card of Unmaking, level-60 cap, cooldowns)
  - Death redistribution (silent transfer, zero-card-only recipients, enchanted items preserved)
  - Spawner registry (entity tracking, unmaking, world decay %)
  - Soul engine (named creature AI players, soul-protector reactions, bind respawn)
"""

import time
import pytest

from src.eq.npc_card_effects import (
    CombatArchetype,
    DamageType,
    IdentityTemplate,
    NPCCardEffects,
    ProtectorAIType,
    Tier1CombatSpell,
    generate_all_card_effects,
    generate_card_effects,
)
from src.eq.card_system import (
    CardCollection,
    CardOfUnmaking,
    CooldownTracker,
    DeathRedistributionResult,
    GodCard,
    SUB_60_UNMAKING_CAP,
    TOWER_SAME_TYPE_ENTRY_COUNT,
    UnmakingBuff,
    handle_unmaking_death,
)
from src.eq.spawner_registry import (
    SpawnerEntry,
    SpawnerRegistry,
    WorldDecayState,
)
from src.eq.soul_engine import (
    SoulDocument,
    SoulEngine,
)


# ============================================================================
# NPC Card Effect Auto-Generation Tests
# ============================================================================


class TestNPCCardEffectGeneration:
    """Test the identity-template → 4-tier effect auto-generation engine."""

    def _create_emperor_crush_template(self) -> IdentityTemplate:
        return IdentityTemplate(
            entity_id="emperor_crush",
            entity_name="Emperor Crush",
            entity_level=45,
            primary_damage_type=DamageType.BLUNT,
            combat_archetype=CombatArchetype.MELEE,
            zone_origin="crushbone",
            is_named=True,
        )

    def test_generate_returns_npc_card_effects(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert isinstance(fx, NPCCardEffects)

    def test_entity_metadata_preserved(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.entity_id == "emperor_crush"
        assert fx.entity_name == "Emperor Crush"
        assert fx.entity_level == 45
        assert fx.is_named is True
        assert fx.primary_weapon_type == "blunt"
        assert fx.combat_style == "melee"

    # --- Tier 1: Combat Spell ---

    def test_tier1_name_contains_entity_name(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert "Emperor Crush" in fx.tier_1.name

    def test_tier1_condition_matches_damage_type(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_1.condition == "requires_blunt_weapon"

    def test_tier1_effect_doubles_damage_type(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_1.effect == "double_blunt_damage"

    def test_tier1_cooldown_is_24_hours(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_1.cooldown_hours == 24

    def test_tier1_stacks_with_all(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_1.stacks_with == "all"

    # --- Tier 1: Level scaling ---

    @pytest.mark.parametrize("level,expected_dur", [
        (1, 30), (5, 30), (10, 30),
        (11, 45), (20, 45), (30, 45),
        (31, 60), (45, 60), (50, 60),
        (55, 60), (65, 60),
    ])
    def test_tier1_duration_scales_by_level(self, level, expected_dur):
        t = IdentityTemplate(
            entity_id="test", entity_name="Test", entity_level=level,
            primary_damage_type=DamageType.SLASH,
        )
        fx = generate_card_effects(t)
        assert fx.tier_1.duration_seconds == expected_dur

    # --- Tier 2: Defensive Buff ---

    def test_tier2_mitigation_type_matches_damage(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_2.mitigation_type == "blunt_damage"

    @pytest.mark.parametrize("level,expected_pct", [
        (1, 0.10), (10, 0.10),
        (15, 0.25), (30, 0.25),
        (35, 0.40), (50, 0.40),
        (55, 0.50), (65, 0.50),
    ])
    def test_tier2_mitigation_scales_by_level(self, level, expected_pct):
        t = IdentityTemplate(
            entity_id="test", entity_name="Test", entity_level=level,
        )
        fx = generate_card_effects(t)
        assert fx.tier_2.mitigation_percent == expected_pct

    def test_tier2_cooldown_is_7_days(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_2.cooldown_days == 7

    # --- Tier 3: Weapon/Class Specialization ---

    def test_tier3_melee_gets_weapon_conversion(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_3.effect_type == "weapon_conversion"
        assert fx.tier_3.details.get("convert_2hb_to_1hb") is True
        assert fx.tier_3.details.get("haste_percent") == 5

    def test_tier3_caster_gets_spell_enhancement(self):
        t = IdentityTemplate(
            entity_id="nagafen", entity_name="Lord Nagafen", entity_level=55,
            primary_damage_type=DamageType.FIRE,
            combat_archetype=CombatArchetype.CASTER,
            is_named=True,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.effect_type == "spell_enhancement"
        assert fx.tier_3.details["spell_school"] == "fire"
        assert fx.tier_3.details["damage_boost_percent"] == 25

    def test_tier3_hybrid_gets_dual_benefit(self):
        t = IdentityTemplate(
            entity_id="hybrid", entity_name="Hybrid NPC", entity_level=40,
            combat_archetype=CombatArchetype.HYBRID,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.effect_type == "hybrid"
        assert "haste_percent" in fx.tier_3.details
        assert "spell_damage_boost" in fx.tier_3.details

    def test_tier3_healer_gets_healing_boost(self):
        t = IdentityTemplate(
            entity_id="cleric", entity_name="Temple Cleric", entity_level=30,
            combat_archetype=CombatArchetype.HEALER,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.effect_type == "spell_enhancement"
        assert fx.tier_3.details["spell_school"] == "healing"

    @pytest.mark.parametrize("level,expected_haste", [
        (5, 1), (20, 3), (45, 5), (55, 5),
    ])
    def test_tier3_melee_haste_scales_by_level(self, level, expected_haste):
        t = IdentityTemplate(
            entity_id="test", entity_name="Test", entity_level=level,
            combat_archetype=CombatArchetype.MELEE,
            primary_damage_type=DamageType.BLUNT,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.details["haste_percent"] == expected_haste

    def test_tier3_level_51_plus_gets_secondary_bonus(self):
        t = IdentityTemplate(
            entity_id="high", entity_name="High Level", entity_level=55,
            combat_archetype=CombatArchetype.MELEE,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.details.get("secondary_stat_bonus") is True

    def test_tier3_level_50_no_secondary_bonus(self):
        t = IdentityTemplate(
            entity_id="mid", entity_name="Mid Level", entity_level=50,
            combat_archetype=CombatArchetype.MELEE,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.details.get("secondary_stat_bonus") is not True

    # --- Tier 4: Soul-Bound Protector ---

    def test_tier4_named_gets_full_ai(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_4.protector_ai_type == ProtectorAIType.FULL_AI

    def test_tier4_generic_gets_pet_ai(self):
        t = IdentityTemplate(
            entity_id="orc_pawn", entity_name="Orc Pawn", entity_level=5,
            is_named=False,
        )
        fx = generate_card_effects(t)
        assert fx.tier_4.protector_ai_type == ProtectorAIType.PET_AI

    def test_tier4_protector_level_matches_entity_level(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_4.protector_level == 45

    def test_tier4_follows_between_zones(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_4.follows_between_zones is True

    def test_tier4_npc_reputation_penalty(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_4.npc_reputation_penalty < 0

    def test_tier4_ai_player_kill_on_sight(self):
        fx = generate_card_effects(self._create_emperor_crush_template())
        assert fx.tier_4.ai_player_kill_on_sight is True

    # --- Batch generation ---

    def test_batch_generate_all(self):
        templates = [
            self._create_emperor_crush_template(),
            IdentityTemplate(entity_id="beetle", entity_name="Fire Beetle", entity_level=1),
            IdentityTemplate(entity_id="nagafen", entity_name="Lord Nagafen", entity_level=55,
                             primary_damage_type=DamageType.FIRE,
                             combat_archetype=CombatArchetype.CASTER, is_named=True),
        ]
        all_fx = generate_all_card_effects(templates)
        assert len(all_fx) == 3
        assert "emperor_crush" in all_fx
        assert "beetle" in all_fx
        assert "nagafen" in all_fx

    # --- All damage types produce valid effects ---

    @pytest.mark.parametrize("dt", list(DamageType))
    def test_all_damage_types_generate_valid_effects(self, dt):
        t = IdentityTemplate(
            entity_id="test", entity_name="Test", entity_level=30,
            primary_damage_type=dt,
        )
        fx = generate_card_effects(t)
        assert fx.tier_1.condition == f"requires_{dt.value}_weapon"
        assert fx.tier_1.effect == f"double_{dt.value}_damage"

    # --- All archetypes produce valid tier 3 ---

    @pytest.mark.parametrize("arch", list(CombatArchetype))
    def test_all_archetypes_produce_tier3(self, arch):
        t = IdentityTemplate(
            entity_id="test", entity_name="Test", entity_level=30,
            combat_archetype=arch,
        )
        fx = generate_card_effects(t)
        assert fx.tier_3.effect_type in ("weapon_conversion", "spell_enhancement", "hybrid")


# ============================================================================
# Card System Tests
# ============================================================================


class TestCardCollection:
    """Test card collection operations, level-60 cap, and death redistribution."""

    def test_new_collection_is_empty(self):
        cc = CardCollection(holder_id="p1")
        assert cc.unmaking_card_count == 0
        assert cc.attackable_by_all is False

    # --- Universal cards ---

    def test_add_universal_card(self):
        cc = CardCollection(holder_id="p1")
        cc.add_universal_card("orc_pawn")
        assert cc.get_universal_card_count("orc_pawn") == 1

    def test_universal_card_stacking(self):
        cc = CardCollection(holder_id="p1")
        cc.add_universal_card("orc_pawn")
        cc.add_universal_card("orc_pawn")
        cc.add_universal_card("orc_pawn")
        assert cc.get_universal_card_count("orc_pawn") == 3

    # --- God cards ---

    def test_add_god_card_unlocks_skill(self):
        cc = CardCollection(holder_id="p1")
        gc = GodCard(card_id="g1", deity_source="hate", card_type="hate", collection_count=1)
        cc.add_god_card(gc)
        assert gc.unlocks["skill"] is True

    def test_god_card_progressive_unlocks(self):
        cc = CardCollection(holder_id="p1")
        gc = GodCard(card_id="g1", deity_source="hate", card_type="hate", collection_count=4)
        cc.add_god_card(gc)
        assert gc.unlocks["skill"] is True
        assert gc.unlocks["buff"] is True
        assert gc.unlocks["enchantment"] is True
        assert gc.unlocks["card_of_unmaking"] is True

    # --- Card of Unmaking: level-60 cap ---

    def test_sub_60_cap_allows_3(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            ok = cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=30))
            assert ok is True
        assert cc.sub_60_unmaking_count == 3

    def test_sub_60_cap_rejects_4th(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=30))
        ok = cc.add_unmaking_card(CardOfUnmaking(card_id="c3", source_entity_level=30))
        assert ok is False
        assert cc.unmaking_card_count == 3

    def test_level_60_bypasses_cap(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=30))
        ok = cc.add_unmaking_card(CardOfUnmaking(card_id="c60", source_entity_level=60))
        assert ok is True
        assert cc.unmaking_card_count == 4

    def test_core_drop_bypasses_cap(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=30))
        ok = cc.add_unmaking_card(CardOfUnmaking(
            card_id="core", source_entity_level=20, source_is_core_drop=True
        ))
        assert ok is True

    # --- Attackable-by-all flag ---

    def test_attackable_at_3_cards(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=60))
        assert cc.attackable_by_all is True

    def test_not_attackable_at_2_cards(self):
        cc = CardCollection(holder_id="p1")
        for i in range(2):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=60))
        assert cc.attackable_by_all is False

    # --- Active buffs ---

    def test_1_card_grants_void_spell(self):
        cc = CardCollection(holder_id="p1")
        cc.add_unmaking_card(CardOfUnmaking(card_id="c0", source_entity_level=60))
        assert UnmakingBuff.VOID_SPELL in cc.active_unmaking_buffs()

    def test_2_cards_grant_shield(self):
        cc = CardCollection(holder_id="p1")
        for i in range(2):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=60))
        assert UnmakingBuff.SHIELD in cc.active_unmaking_buffs()

    def test_3_cards_grant_disintegration(self):
        cc = CardCollection(holder_id="p1")
        for i in range(3):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"c{i}", source_entity_level=60))
        assert UnmakingBuff.DISINTEGRATION in cc.active_unmaking_buffs()

    # --- Enchanted items ---

    def test_enchanted_item_added(self):
        cc = CardCollection(holder_id="p1")
        cc.add_enchanted_item("epic_sword")
        assert "epic_sword" in cc.enchanted_items

    # --- Tower of the Unmaker entry (§9.8) ---

    def test_can_enter_tower_with_1_unmaking_card(self):
        cc = CardCollection(holder_id="p1")
        cc.add_unmaking_card(CardOfUnmaking(card_id="c0", source_entity_level=60))
        assert cc.can_enter_tower(has_levitation=True) is True

    def test_cannot_enter_tower_without_levitation(self):
        cc = CardCollection(holder_id="p1")
        cc.add_unmaking_card(CardOfUnmaking(card_id="c0", source_entity_level=60))
        assert cc.can_enter_tower(has_levitation=False) is False

    def test_can_enter_tower_with_4_same_type_cards(self):
        cc = CardCollection(holder_id="p1")
        for _ in range(4):
            cc.add_universal_card("emperor_crush")
        assert cc.can_enter_tower(has_levitation=True) is True

    def test_cannot_enter_tower_with_3_same_type_cards(self):
        cc = CardCollection(holder_id="p1")
        for _ in range(3):
            cc.add_universal_card("emperor_crush")
        assert cc.can_enter_tower(has_levitation=True) is False

    def test_cannot_enter_tower_with_4_different_type_cards(self):
        cc = CardCollection(holder_id="p1")
        cc.add_universal_card("orc_pawn")
        cc.add_universal_card("fire_beetle")
        cc.add_universal_card("gnoll_scout")
        cc.add_universal_card("bat")
        assert cc.can_enter_tower(has_levitation=True) is False

    def test_cannot_enter_tower_empty_collection(self):
        cc = CardCollection(holder_id="p1")
        assert cc.can_enter_tower(has_levitation=True) is False

    def test_has_four_same_type_cards_true(self):
        cc = CardCollection(holder_id="p1")
        for _ in range(4):
            cc.add_universal_card("fippy_darkpaw")
        assert cc.has_four_same_type_cards() is True

    def test_has_four_same_type_cards_false_mixed(self):
        cc = CardCollection(holder_id="p1")
        cc.add_universal_card("a")
        cc.add_universal_card("a")
        cc.add_universal_card("b")
        cc.add_universal_card("b")
        assert cc.has_four_same_type_cards() is False

    def test_tower_same_type_entry_count_is_4(self):
        assert TOWER_SAME_TYPE_ENTRY_COUNT == 4

    def test_can_enter_tower_4_same_no_levitation_blocked(self):
        cc = CardCollection(holder_id="p1")
        for _ in range(4):
            cc.add_universal_card("emperor_crush")
        assert cc.can_enter_tower(has_levitation=False) is False


class TestDeathRedistribution:
    """Test §9.22: silent card redistribution on death."""

    def _create_collection_with_cards(self, count: int) -> CardCollection:
        cc = CardCollection(holder_id="holder")
        for i in range(count):
            cc.add_unmaking_card(CardOfUnmaking(card_id=f"h{i}", source_entity_level=60))
        cc.add_enchanted_item("enchanted_armor")
        return cc

    def test_cards_removed_from_dead_holder(self):
        holder = self._create_collection_with_cards(3)
        killers = [CardCollection(holder_id="k1")]
        handle_unmaking_death(holder, killers)
        assert holder.unmaking_card_count == 0

    def test_dead_holder_not_attackable_after_death(self):
        holder = self._create_collection_with_cards(3)
        killers = [CardCollection(holder_id="k1")]
        handle_unmaking_death(holder, killers)
        assert holder.attackable_by_all is False

    def test_enchanted_items_preserved_on_death(self):
        holder = self._create_collection_with_cards(3)
        killers = [CardCollection(holder_id="k1")]
        handle_unmaking_death(holder, killers)
        assert "enchanted_armor" in holder.enchanted_items

    def test_cards_go_to_zero_card_killers(self):
        holder = self._create_collection_with_cards(3)
        zero_killer = CardCollection(holder_id="k_zero")
        result = handle_unmaking_death(holder, [zero_killer])
        assert result.cards_redistributed > 0
        assert zero_killer.unmaking_card_count > 0

    def test_killers_with_cards_excluded(self):
        holder = self._create_collection_with_cards(3)
        has_cards = CardCollection(holder_id="k_has")
        has_cards.add_unmaking_card(CardOfUnmaking(card_id="x", source_entity_level=60))
        result = handle_unmaking_death(holder, [has_cards])
        assert result.cards_redistributed == 0
        assert result.cards_destroyed == 3

    def test_silent_flag_always_true(self):
        holder = self._create_collection_with_cards(3)
        result = handle_unmaking_death(holder, [CardCollection(holder_id="k1")])
        assert result.silent is True

    def test_no_eligible_killers_destroys_cards(self):
        holder = self._create_collection_with_cards(3)
        # All killers already have cards
        k1 = CardCollection(holder_id="k1")
        k1.add_unmaking_card(CardOfUnmaking(card_id="x1", source_entity_level=60))
        k2 = CardCollection(holder_id="k2")
        k2.add_unmaking_card(CardOfUnmaking(card_id="x2", source_entity_level=60))
        result = handle_unmaking_death(holder, [k1, k2])
        assert result.cards_destroyed == 3
        assert result.cards_redistributed == 0


# ============================================================================
# Spawner Registry Tests
# ============================================================================


class TestSpawnerRegistry:
    """Test entity tracking, unmaking, and world decay."""

    def _create_registry_with_entities(self) -> SpawnerRegistry:
        reg = SpawnerRegistry()
        for i in range(10):
            reg.register_entity(SpawnerEntry(
                entity_id=f"mob_{i}",
                entity_name=f"Mob {i}",
                entity_category="mob",
                entity_level=i * 5 + 1,
            ))
        return reg

    def test_register_entities(self):
        reg = self._create_registry_with_entities()
        assert reg.entity_count == 10

    def test_initial_decay_is_zero(self):
        reg = self._create_registry_with_entities()
        assert reg.decay_state.decay_percentage == 0.0

    def test_unmake_entity(self):
        reg = self._create_registry_with_entities()
        ok = reg.unmake_entity("mob_0", "player1")
        assert ok is True
        entry = reg.get_entry("mob_0")
        assert entry.four_card_combo_unmade is True
        assert entry.spawner_unlocked is False

    def test_decay_percentage_increases(self):
        reg = self._create_registry_with_entities()
        reg.unmake_entity("mob_0", "player1")
        assert reg.decay_state.decay_percentage == 10.0

    def test_cannot_unmake_twice(self):
        reg = self._create_registry_with_entities()
        reg.unmake_entity("mob_0", "player1")
        ok = reg.unmake_entity("mob_0", "player2")
        assert ok is False

    def test_endangered_entities(self):
        reg = self._create_registry_with_entities()
        entry = reg.get_entry("mob_3")
        entry.cards_in_circulation = 3
        entry.endangered = True
        endangered = reg.get_endangered_entities()
        assert any(e.entity_id == "mob_3" for e in endangered)

    def test_decay_milestone_announcement(self):
        reg = self._create_registry_with_entities()
        for i in range(5):  # Unmake 5 of 10 = 50%
            reg.unmake_entity(f"mob_{i}", "player1")
        assert any("50%" in a for a in reg.announcements)


class TestWorldDecayState:
    """Test world decay percentage and milestone calculations."""

    def test_zero_entities(self):
        state = WorldDecayState()
        assert state.decay_percentage == 0.0
        assert state.milestone is None

    def test_50_percent(self):
        state = WorldDecayState(total_entity_types=100, entities_unmade=50)
        assert state.decay_percentage == 50.0
        assert state.milestone == 50

    def test_90_percent(self):
        state = WorldDecayState(total_entity_types=100, entities_unmade=90)
        assert state.milestone == 90


# ============================================================================
# Soul Engine Tests
# ============================================================================


class TestSoulEngine:
    """Test agent soul document management and AI player behavior."""

    def test_named_creature_becomes_ai_player(self):
        soul = SoulDocument(agent_id="crush", name="Emperor Crush", is_named=True)
        assert soul.is_ai_player is True

    def test_generic_mob_not_ai_player(self):
        soul = SoulDocument(agent_id="beetle", name="Fire Beetle", is_named=False)
        assert soul.is_ai_player is False

    def test_create_and_retrieve_soul(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="test", name="Test")
        engine.create_soul(soul)
        assert engine.get_soul("test") is soul
        assert engine.soul_count == 1

    def test_get_ai_players(self):
        engine = SoulEngine()
        engine.create_soul(SoulDocument(agent_id="a", name="A", is_named=True))
        engine.create_soul(SoulDocument(agent_id="b", name="B", is_named=False))
        ai_players = engine.get_ai_players()
        assert len(ai_players) == 1
        assert ai_players[0].agent_id == "a"

    def test_react_to_soul_protector_kills_on_sight(self):
        engine = SoulEngine()
        engine.create_soul(SoulDocument(agent_id="guard", name="Guard", is_named=True))
        reaction = engine.react_to_soul_protector("guard", "evil_player")
        assert reaction == "kill_on_sight"

    def test_generic_mob_no_reaction_to_soul_protector(self):
        engine = SoulEngine()
        engine.create_soul(SoulDocument(agent_id="mob", name="Mob", is_named=False))
        reaction = engine.react_to_soul_protector("mob", "evil_player")
        assert reaction is None

    def test_soul_protector_records_enslaver(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="guard", name="Guard", is_named=True)
        engine.create_soul(soul)
        engine.react_to_soul_protector("guard", "evil_player")
        assert "evil_player" in soul.known_soul_enslavers

    def test_respawn_at_bind_strips_unmaking(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="p1", name="Player", bind_point="qeynos")
        soul.card_collection.add_unmaking_card(
            CardOfUnmaking(card_id="c1", source_entity_level=60)
        )
        engine.create_soul(soul)
        engine.process_death("p1", "killer")
        engine.process_respawn_at_bind("p1")
        assert soul.card_collection.unmaking_card_count == 0
        assert soul.short_term_memory["current_zone"] == "qeynos"

    def test_respawn_preserves_enchanted_items(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="p1", name="Player", bind_point="freeport")
        soul.card_collection.add_unmaking_card(
            CardOfUnmaking(card_id="c1", source_entity_level=60)
        )
        soul.card_collection.add_enchanted_item("enchanted_bracer")
        engine.create_soul(soul)
        engine.process_death("p1", "killer")
        engine.process_respawn_at_bind("p1")
        assert "enchanted_bracer" in soul.card_collection.enchanted_items

    def test_record_event(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="a", name="A")
        engine.create_soul(soul)
        engine.record_event("a", "combat", {"target": "orc"})
        assert len(soul.short_term_memory["recent_events"]) == 1

    def test_record_combat_outcome(self):
        engine = SoulEngine()
        soul = SoulDocument(agent_id="a", name="A")
        engine.create_soul(soul)
        engine.record_combat_outcome("a", "orc", "victory")
        assert len(soul.long_term_archive["combat_outcomes"]) == 1


# ============================================================================
# Cooldown Tracker Tests
# ============================================================================


class TestCooldownTracker:
    """Test real-time cooldown mechanics."""

    def test_ability_ready_by_default(self):
        tracker = CooldownTracker()
        assert tracker.is_ready("some_ability") is True

    def test_ability_not_ready_after_activation(self):
        tracker = CooldownTracker()
        tracker.activate("spell", 3600)  # 1 hour
        assert tracker.is_ready("spell") is False

    def test_remaining_seconds(self):
        tracker = CooldownTracker()
        tracker.activate("spell", 3600)
        remaining = tracker.remaining_seconds("spell")
        assert remaining > 3590  # within a few seconds of 3600
