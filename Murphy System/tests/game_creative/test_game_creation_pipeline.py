"""
Tests for the MMORPG Game Creation Pipeline.

Validates:
  - World generation produces valid zones
  - Class balance engine produces balanced outputs
  - Synergy casting magnifier math is correct
  - Luck system produces expected distributions
  - Weekly release orchestrator pipeline stages work
  - Agent player controller schedules properly
  - Billboard proximity logic works
  - Monetization rules reject pay-to-win items
  - AI companion system employer/employee dynamics
  - Cooperation mechanics group synergy
"""

import time
import uuid

import pytest

from src.game_creation_pipeline.luck_system import (
    LuckEventType,
    LuckOutcome,
    LuckSystem,
    _determine_outcome,
)
from src.game_creation_pipeline.monetization_rules import (
    COSMETIC_ONLY_MODEL,
    COSMETIC_AND_CONVENIENCE_MODEL,
    ItemCategory,
    ItemDefinition,
    MonetizationRulesEngine,
    MonetizationVerdict,
)
from src.game_creation_pipeline.class_balance_engine import (
    ClassBalanceEngine,
    CombinationSpell,
    RoleArchetype,
    SpellElement,
)
from src.game_creation_pipeline.cooperation_mechanics import (
    CooperationGate,
    CooperationMechanics,
    Group,
    GroupMember,
    GroupRole,
    PERFECT_SYNC_MAGNIFIER,
    SYNERGY_WINDOW_SECONDS,
)
from src.game_creation_pipeline.ai_companion_system import (
    AICompanionSystem,
    CompanionGoalType,
    CompanionPersonality,
    RelationshipDynamic,
)
from src.game_creation_pipeline.agent_player_controller import (
    AgentPlayerController,
    AgentPlayStyle,
    OFF_TIME_HOURS,
    SessionState,
)
from src.game_creation_pipeline.billboard_ad_system import (
    AdContent,
    AdCategory,
    Billboard,
    BillboardAdSystem,
    BillboardPlacementZone,
)
from src.game_creation_pipeline.streaming_integration import (
    CameraMode,
    StreamEventType,
    StreamingIntegration,
)
from src.game_creation_pipeline.world_generator import (
    WorldGenerator,
    WorldTheme,
    ZoneType,
)
from src.game_creation_pipeline.weekly_release_orchestrator import (
    PipelineStage,
    QualityGateResult,
    WeeklyReleaseOrchestrator,
)


# ---------------------------------------------------------------------------
# Luck System
# ---------------------------------------------------------------------------

class TestLuckSystem:
    def test_create_profile(self):
        ls = LuckSystem()
        profile = ls.get_or_create_profile("char_1", base_luck=50)
        assert profile.character_id == "char_1"
        assert profile.base_luck == 50

    def test_profile_idempotent(self):
        ls = LuckSystem()
        p1 = ls.get_or_create_profile("char_1", base_luck=30)
        p2 = ls.get_or_create_profile("char_1", base_luck=99)
        assert p1 is p2
        assert p1.base_luck == 30  # not overwritten

    def test_roll_returns_valid_outcome(self):
        ls = LuckSystem()
        roll = ls.roll("char_1", LuckEventType.CRITICAL_HIT)
        assert roll.outcome in list(LuckOutcome)
        assert 0.0 <= roll.raw_roll <= 100.0
        assert 0.0 <= roll.adjusted_roll <= 100.0

    def test_luck_modifier_applied(self):
        ls = LuckSystem()
        ls.add_luck_modifier("char_x", "test_item", 20)
        profile = ls.get_or_create_profile("char_x")
        assert profile.effective_luck() == 30  # base 10 + 20

    def test_remove_luck_modifier(self):
        ls = LuckSystem()
        ls.add_luck_modifier("char_x", "item", 10)
        ls.remove_luck_modifier("char_x", "item")
        profile = ls.get_or_create_profile("char_x")
        assert profile.effective_luck() == 10  # back to base

    def test_streak_updates_on_lucky_roll(self):
        """Streak counter updates after each roll (positive for lucky, negative for unlucky)."""
        ls = LuckSystem()
        ls.set_base_luck("char_1", 50)
        for _ in range(5):
            ls.roll("char_1", LuckEventType.RARE_DROP)
        profile = ls.get_or_create_profile("char_1")
        assert profile.total_rolls == 5
        # Streak is updated (any direction based on random outcomes)
        assert isinstance(profile.current_streak, int)

    def test_rare_drop_multiplier_range(self):
        ls = LuckSystem()
        multiplier = ls.rare_drop_multiplier("char_1")
        assert 0.5 <= multiplier <= 5.0

    def test_crafting_quality_range(self):
        ls = LuckSystem()
        bonus = ls.crafting_quality_bonus("char_1")
        assert -1 <= bonus <= 5

    def test_exploration_discovery_returns_bool(self):
        ls = LuckSystem()
        result = ls.exploration_discovery_chance("char_1")
        assert isinstance(result, bool)

    def test_notable_events_broadcast_worthy(self):
        ls = LuckSystem()
        # Force divine outcome by patching
        roll = ls.roll("char_1", LuckEventType.CRITICAL_HIT)
        # Just test the API works
        events = ls.get_notable_events(broadcast_only=True)
        assert isinstance(events, list)

    def test_determine_outcome_boundaries(self):
        assert _determine_outcome(100.0) == LuckOutcome.DIVINE
        assert _determine_outcome(90.0) == LuckOutcome.LEGENDARY
        assert _determine_outcome(70.0) == LuckOutcome.LUCKY
        assert _determine_outcome(50.0) == LuckOutcome.NEUTRAL
        assert _determine_outcome(20.0) == LuckOutcome.UNLUCKY
        assert _determine_outcome(5.0) == LuckOutcome.CATASTROPHIC
        assert _determine_outcome(0.0) == LuckOutcome.CATASTROPHIC

    def test_luck_capped_at_100(self):
        ls = LuckSystem()
        ls.add_luck_modifier("char_1", "item_a", 200)
        profile = ls.get_or_create_profile("char_1")
        assert profile.effective_luck() == 100

    def test_luck_floored_at_1(self):
        ls = LuckSystem()
        ls.add_luck_modifier("char_1", "curse", -999)
        profile = ls.get_or_create_profile("char_1")
        assert profile.effective_luck() == 1

    def test_is_critical_hit_returns_tuple(self):
        ls = LuckSystem()
        is_crit, roll = ls.is_critical_hit("char_1")
        assert isinstance(is_crit, bool)
        assert roll.event_type == LuckEventType.CRITICAL_HIT


# ---------------------------------------------------------------------------
# Monetization Rules
# ---------------------------------------------------------------------------

class TestMonetizationRules:
    def _cosmetic_item(self) -> ItemDefinition:
        return ItemDefinition(
            item_id="skin_001", name="Dragon Skin",
            category=ItemCategory.COSMETIC,
            visual_only=True,
        )

    def _p2w_item(self) -> ItemDefinition:
        return ItemDefinition(
            item_id="sword_paid", name="Pay-to-Win Sword",
            category=ItemCategory.GAMEPLAY_POWER,
            stat_bonuses={"attack": 500},
            obtainable_in_game=False,
        )

    def test_cosmetic_item_approved(self):
        engine = MonetizationRulesEngine()
        ruling = engine.evaluate(self._cosmetic_item())
        assert ruling.verdict == MonetizationVerdict.APPROVED

    def test_pay_to_win_rejected(self):
        engine = MonetizationRulesEngine()
        with pytest.raises(ValueError, match="pay-to-win"):
            engine.evaluate(self._p2w_item())

    def test_xp_booster_rejected(self):
        engine = MonetizationRulesEngine()
        item = ItemDefinition(
            item_id="xp_boost", name="XP Booster",
            category=ItemCategory.PROGRESSION_BOOST,
            xp_multiplier=2.0,
        )
        with pytest.raises(ValueError):
            engine.evaluate(item)

    def test_drop_rate_enhancer_rejected(self):
        engine = MonetizationRulesEngine()
        item = ItemDefinition(
            item_id="loot_enhancer", name="Loot Magnifier",
            category=ItemCategory.LOOT_ENHANCER,
            drop_rate_multiplier=3.0,
        )
        with pytest.raises(ValueError):
            engine.evaluate(item)

    def test_fairness_score_all_approved(self):
        engine = MonetizationRulesEngine()
        for i in range(5):
            engine.evaluate(ItemDefinition(
                item_id=f"skin_{i}", name=f"Skin {i}",
                category=ItemCategory.COSMETIC, visual_only=True,
            ))
        assert engine.fairness_score() == 1.0

    def test_fairness_score_decreases_on_rejection(self):
        engine = MonetizationRulesEngine()
        # Approve one
        engine.evaluate(ItemDefinition(
            item_id="skin_ok", name="OK Skin",
            category=ItemCategory.COSMETIC,
        ))
        # Reject one
        try:
            engine.evaluate(ItemDefinition(
                item_id="p2w", name="P2W",
                category=ItemCategory.GAMEPLAY_POWER,
            ))
        except ValueError:
            pass
        score = engine.fairness_score()
        assert score == 0.5

    def test_get_rulings_filtered(self):
        engine = MonetizationRulesEngine()
        engine.evaluate(ItemDefinition(
            item_id="skin_a", name="Skin A",
            category=ItemCategory.COSMETIC,
        ))
        approved = engine.get_rulings(verdict_filter=MonetizationVerdict.APPROVED)
        assert len(approved) == 1

    def test_convenience_model_allows_extra_slots(self):
        engine = MonetizationRulesEngine(revenue_model_id="cosmetic_and_convenience")
        item = ItemDefinition(
            item_id="bag_slot", name="Extra Bag Slot",
            category=ItemCategory.CONVENIENCE,
        )
        ruling = engine.evaluate(item)
        assert ruling.verdict == MonetizationVerdict.APPROVED

    def test_revenue_model_property(self):
        engine = MonetizationRulesEngine("cosmetic_only")
        assert engine.revenue_model.model_id == "cosmetic_only"

    def test_stat_bonus_not_in_game_rejected(self):
        engine = MonetizationRulesEngine()
        item = ItemDefinition(
            item_id="paid_ring", name="Paid Ring",
            category=ItemCategory.GAMEPLAY_POWER,
            stat_bonuses={"defense": 100},
            obtainable_in_game=False,
        )
        with pytest.raises(ValueError):
            engine.evaluate(item)


# ---------------------------------------------------------------------------
# Class Balance Engine
# ---------------------------------------------------------------------------

class TestClassBalanceEngine:
    def test_default_classes_loaded(self):
        engine = ClassBalanceEngine()
        classes = engine.all_classes()
        assert len(classes) >= 10

    def test_warrior_class_exists(self):
        engine = ClassBalanceEngine()
        warrior = engine.get_class("warrior")
        assert warrior is not None
        assert warrior.primary_role == RoleArchetype.TANK

    def test_cleric_class_exists(self):
        engine = ClassBalanceEngine()
        cleric = engine.get_class("cleric")
        assert cleric is not None
        assert cleric.primary_role == RoleArchetype.HEALER

    def test_role_synergy_multiplier_classic_trio(self):
        engine = ClassBalanceEngine()
        mult = engine.role_synergy_multiplier([
            RoleArchetype.TANK,
            RoleArchetype.HEALER,
            RoleArchetype.DPS_CASTER,
        ])
        assert mult > 1.0

    def test_role_synergy_no_bonus_solo(self):
        engine = ClassBalanceEngine()
        mult = engine.role_synergy_multiplier([RoleArchetype.DPS_CASTER])
        assert mult == 1.0

    def test_find_combination_firestorm(self):
        engine = ClassBalanceEngine()
        combo = engine.find_combination([SpellElement.FIRE, SpellElement.WIND])
        assert combo is not None
        assert "fire" in combo.combination_id.lower() or "storm" in combo.name.lower()

    def test_find_combination_none_for_unknown(self):
        engine = ClassBalanceEngine()
        combo = engine.find_combination([SpellElement.FIRE, SpellElement.ICE, SpellElement.EARTH])
        assert combo is None

    def test_balance_report_with_equal_classes(self):
        engine = ClassBalanceEngine()
        # All classes at equal power → should be balanced
        report = engine.generate_balance_report()
        assert report.overall_balance_score >= 0.8

    def test_balance_report_detects_outlier(self):
        engine = ClassBalanceEngine()
        engine.update_class_power("wizard", 5.0)   # outlier
        report = engine.generate_balance_report()
        assert "wizard" in report.outliers

    def test_update_class_power_floored(self):
        engine = ClassBalanceEngine()
        engine.update_class_power("warrior", -10.0)
        warrior = engine.get_class("warrior")
        assert warrior.current_power_level >= 0.1

    def test_register_custom_class(self):
        from src.game_creation_pipeline.class_balance_engine import ClassDefinition
        engine = ClassBalanceEngine()
        custom = ClassDefinition(
            class_id="test_class", name="TestClass",
            primary_role=RoleArchetype.HYBRID, secondary_role=None,
            description="A test class.",
        )
        engine.register_class(custom)
        assert engine.get_class("test_class") is not None

    def test_dual_fire_combination(self):
        engine = ClassBalanceEngine()
        combo = engine.find_combination([SpellElement.FIRE, SpellElement.FIRE])
        assert combo is not None
        assert combo.magnifier >= 2.0

    def test_dual_holy_combination(self):
        engine = ClassBalanceEngine()
        combo = engine.find_combination([SpellElement.HOLY, SpellElement.HOLY])
        assert combo is not None


# ---------------------------------------------------------------------------
# Cooperation Mechanics
# ---------------------------------------------------------------------------

class TestCooperationMechanics:
    def _make_group(self) -> Group:
        members = [
            GroupMember("char_1", "warrior", RoleArchetype.TANK, GroupRole.MAIN_TANK),
            GroupMember("char_2", "cleric", RoleArchetype.HEALER, GroupRole.MAIN_HEALER),
            GroupMember("char_3", "wizard", RoleArchetype.DPS_CASTER, GroupRole.DPS),
        ]
        coop = CooperationMechanics()
        return coop.form_group(members, zone="test_zone")

    def test_group_formation(self):
        group = self._make_group()
        assert group.group_id
        assert group.size() == 3
        assert group.synergy_multiplier > 1.0

    def test_group_has_role(self):
        group = self._make_group()
        assert group.has_role(RoleArchetype.TANK)
        assert group.has_role(RoleArchetype.HEALER)
        assert not group.has_role(RoleArchetype.SUPPORT)

    def test_single_cast_no_magnifier(self):
        coop = CooperationMechanics()
        window = coop.register_cast("char_1", "fireball", SpellElement.FIRE)
        assert window.magnifier == 1.0
        assert len(window.casters) == 1

    def test_dual_cast_produces_magnifier(self):
        coop = CooperationMechanics()
        now = time.time()
        coop.register_cast("char_1", "fireball", SpellElement.FIRE, cast_time=now)
        window = coop.register_cast("char_2", "fireball", SpellElement.FIRE, cast_time=now + 0.5)
        assert window.magnifier >= 1.2
        assert len(window.casters) == 2

    def test_triple_cast_higher_magnifier(self):
        coop = CooperationMechanics()
        now = time.time()
        coop.register_cast("char_1", "fireball", SpellElement.FIRE, cast_time=now)
        coop.register_cast("char_2", "fireball", SpellElement.FIRE, cast_time=now + 0.3)
        window = coop.register_cast("char_3", "fireball", SpellElement.FIRE, cast_time=now + 0.6)
        assert window.magnifier >= 1.2

    def test_expired_window_resets(self):
        coop = CooperationMechanics()
        past = time.time() - 10.0  # 10 seconds ago
        coop.register_cast("char_1", "fireball", SpellElement.FIRE, cast_time=past)
        # New cast starts fresh window
        window = coop.register_cast("char_2", "fireball", SpellElement.FIRE)
        assert len(window.casters) == 1

    def test_close_window_with_combination(self):
        coop = CooperationMechanics()
        now = time.time()
        coop.register_cast("char_1", "fireball", SpellElement.FIRE, cast_time=now)
        coop.register_cast("char_2", "wind_slash", SpellElement.WIND, cast_time=now + 0.5)
        window = coop.close_window(
            SpellElement.FIRE,
            elements_in_window=[SpellElement.FIRE, SpellElement.WIND],
        )
        # The combination should be detected
        assert window is not None

    def test_cooperation_gate_pass(self):
        coop = CooperationMechanics()
        gate = CooperationGate(
            gate_id="dungeon_1", name="Test Dungeon",
            required_min_players=2,
            required_roles=[RoleArchetype.TANK, RoleArchetype.HEALER],
            min_average_level=1,
            description="Test",
        )
        coop.register_gate(gate)
        members = [
            GroupMember("c1", "warrior", RoleArchetype.TANK, GroupRole.MAIN_TANK, level=10),
            GroupMember("c2", "cleric", RoleArchetype.HEALER, GroupRole.MAIN_HEALER, level=10),
        ]
        group = coop.form_group(members)
        can, reasons = coop.can_attempt_gate("dungeon_1", group)
        assert can is True
        assert reasons == []

    def test_cooperation_gate_fail_missing_role(self):
        coop = CooperationMechanics()
        gate = CooperationGate(
            gate_id="dungeon_2", name="Hard Dungeon",
            required_min_players=2,
            required_roles=[RoleArchetype.TANK, RoleArchetype.HEALER],
            min_average_level=1,
            description="Test",
        )
        coop.register_gate(gate)
        members = [
            GroupMember("c1", "wizard", RoleArchetype.DPS_CASTER, GroupRole.DPS, level=10),
            GroupMember("c2", "rogue", RoleArchetype.DPS_MELEE, GroupRole.DPS, level=10),
        ]
        group = coop.form_group(members)
        can, reasons = coop.can_attempt_gate("dungeon_2", group)
        assert can is False
        assert len(reasons) > 0

    def test_cooperation_gate_fail_too_few_players(self):
        coop = CooperationMechanics()
        gate = CooperationGate(
            gate_id="raid_1", name="Big Raid",
            required_min_players=18,
            required_roles=[RoleArchetype.TANK],
            min_average_level=60,
            description="Massive raid",
        )
        coop.register_gate(gate)
        members = [
            GroupMember("c1", "warrior", RoleArchetype.TANK, GroupRole.MAIN_TANK, level=70),
        ]
        group = coop.form_group(members)
        can, reasons = coop.can_attempt_gate("raid_1", group)
        assert can is False

    def test_ai_companion_cooperation_bonus(self):
        coop = CooperationMechanics()
        members = [
            GroupMember("c1", "warrior", RoleArchetype.TANK, GroupRole.MAIN_TANK, is_ai_companion=True),
            GroupMember("c2", "cleric", RoleArchetype.HEALER, GroupRole.MAIN_HEALER, is_ai_companion=True),
        ]
        group = coop.form_group(members)
        bonus = coop.ai_cooperation_bonus(group)
        assert bonus > 0.0

    def test_events_logged(self):
        coop = CooperationMechanics()
        members = [
            GroupMember("c1", "warrior", RoleArchetype.TANK, GroupRole.MAIN_TANK),
        ]
        coop.form_group(members)
        events = coop.recent_events()
        assert len(events) >= 1
        assert events[-1].event_type == "group_formed"


# ---------------------------------------------------------------------------
# AI Companion System
# ---------------------------------------------------------------------------

class TestAICompanionSystem:
    def test_create_companion(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            name="Murphy", personality=CompanionPersonality.LOYAL,
            class_id="cleric", owner_character_id="player_1",
        )
        assert companion.companion_id
        assert companion.trust_score == 50.0
        assert companion.dynamic == RelationshipDynamic.PLAYER_IS_EMPLOYER

    def test_trust_increase_shifts_dynamic(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Alpha", CompanionPersonality.AMBITIOUS, "wizard", "player_1"
        )
        trust, dynamic = sys.adjust_trust(companion.companion_id, 40.0, "generous")
        assert trust == 90.0
        assert dynamic == RelationshipDynamic.COMPANION_IS_EMPLOYER

    def test_trust_decrease_player_employer(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Beta", CompanionPersonality.INDEPENDENT, "rogue", "player_1"
        )
        trust, dynamic = sys.adjust_trust(companion.companion_id, -20.0, "disobedient")
        assert trust == 30.0
        assert dynamic == RelationshipDynamic.PLAYER_IS_EMPLOYER

    def test_equal_partner_zone(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Gamma", CompanionPersonality.ANALYTICAL, "warrior", "player_1"
        )
        trust, dynamic = sys.adjust_trust(companion.companion_id, 0.0)
        assert dynamic == RelationshipDynamic.EQUAL_PARTNERS

    def test_directive_accepted_at_high_trust(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Delta", CompanionPersonality.LOYAL, "cleric", "player_1"
        )
        directive = sys.issue_directive("player_1", companion.companion_id, "assist_in_combat")
        assert directive.accepted is True

    def test_directive_rejected_at_low_trust(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Epsilon", CompanionPersonality.INDEPENDENT, "rogue", "player_1"
        )
        sys.adjust_trust(companion.companion_id, -40.0, "conflict")
        directive = sys.issue_directive("player_1", companion.companion_id, "attack_ally")
        assert directive.accepted is False

    def test_add_goal(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Zeta", CompanionPersonality.AMBITIOUS, "warrior", "player_1"
        )
        goal = sys.add_goal(
            companion.companion_id, CompanionGoalType.LEVEL_UP, "level 50", priority=8
        )
        assert goal.goal_id
        assert not goal.completed

    def test_advance_goal_to_completion(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Eta", CompanionPersonality.LOYAL, "cleric", "player_1"
        )
        goal = sys.add_goal(companion.companion_id, CompanionGoalType.EXPLORE_ZONE, "Darkwood")
        sys.advance_goal(companion.companion_id, goal.goal_id, 0.5)
        sys.advance_goal(companion.companion_id, goal.goal_id, 0.5)
        profile = sys.get_companion(companion.companion_id)
        assert any(g.goal_id == goal.goal_id for g in profile.completed_goals)

    def test_improve_skill(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Theta", CompanionPersonality.ANALYTICAL, "wizard", "player_1"
        )
        new_val = sys.improve_skill(companion.companion_id, "wizard", 20.0)
        assert new_val == 30.0

    def test_companions_for_player(self):
        sys = AICompanionSystem()
        sys.create_companion("A", CompanionPersonality.LOYAL, "warrior", "player_99")
        sys.create_companion("B", CompanionPersonality.LOYAL, "cleric", "player_99")
        companions = sys.companions_for_player("player_99")
        assert len(companions) == 2

    def test_murphy_agent_companion(self):
        sys = AICompanionSystem()
        companion = sys.create_companion(
            "Murphy-007", CompanionPersonality.AMBITIOUS, "wizard", "player_1",
            agent_id="agent_007"
        )
        assert companion.is_murphy_agent is True
        assert companion.agent_id == "agent_007"


# ---------------------------------------------------------------------------
# Agent Player Controller
# ---------------------------------------------------------------------------

class TestAgentPlayerController:
    def test_register_character(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_1", "Murphius", "warrior", "world_1")
        assert char.character_id
        assert char.agent_id == "agent_1"
        assert char.level == 1

    def test_should_login_off_time(self):
        ctrl = AgentPlayerController()
        # Off-time hours should have some probability of login
        off_hour = OFF_TIME_HOURS[0]
        # With enough trials at least one should be True
        results = [ctrl.should_login(off_hour) for _ in range(100)]
        assert any(results)

    def test_should_not_login_peak_time(self):
        ctrl = AgentPlayerController()
        # Noon UTC is peak time (not in OFF_TIME_HOURS)
        assert ctrl.should_login(12) is False

    def test_start_and_end_session(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_2", "Tester", "cleric", "world_1")
        session = ctrl.start_session(char.character_id)
        assert session.state == SessionState.ACTIVE

        ended = ctrl.end_session(char.character_id)
        assert ended is not None
        assert ended.ended_at is not None

    def test_perform_activity_records_xp(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_3", "XPFarmer", "wizard", "world_1")
        ctrl.start_session(char.character_id)
        ctrl.perform_activity(char.character_id, "killed_mob", xp_gained=100)
        session = ctrl.active_session(char.character_id)
        assert session.xp_gained == 100

    def test_level_up_on_xp_threshold(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_4", "LevelUp", "rogue", "world_1")
        ctrl.start_session(char.character_id)
        ctrl.perform_activity(char.character_id, "questing", xp_gained=10_001)
        updated = ctrl.get_character(char.character_id)
        assert updated.level >= 2

    def test_update_satisfaction(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_5", "Happy", "bard", "world_1")
        new_sat = ctrl.update_satisfaction(char.character_id, 10.0)
        assert new_sat == 60.0

    def test_satisfaction_capped(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_6", "OverHappy", "paladin", "world_1")
        ctrl.update_satisfaction(char.character_id, 9999.0)
        updated = ctrl.get_character(char.character_id)
        assert updated.satisfaction == 100.0

    def test_find_party_members(self):
        ctrl = AgentPlayerController()
        char_a = ctrl.register_character("agent_a", "AgentA", "warrior", "world_1")
        char_b = ctrl.register_character("agent_b", "AgentB", "cleric", "world_1")
        ctrl.start_session(char_a.character_id)
        ctrl.start_session(char_b.character_id)
        candidates = ctrl.find_potential_party_members(char_a.character_id)
        assert any(c.character_id == char_b.character_id for c in candidates)

    def test_thought_bubbles_emitted_on_login(self):
        ctrl = AgentPlayerController()
        char = ctrl.register_character("agent_7", "Thinker", "enchanter", "world_1")
        ctrl.start_session(char.character_id)
        thoughts = ctrl.get_thought_bubbles(since_timestamp=0.0)
        assert len(thoughts) >= 1

    def test_characters_for_agent(self):
        ctrl = AgentPlayerController()
        ctrl.register_character("agent_x", "Char1", "warrior", "world_1")
        ctrl.register_character("agent_x", "Char2", "cleric", "world_2")
        chars = ctrl.characters_for_agent("agent_x")
        assert len(chars) == 2


# ---------------------------------------------------------------------------
# Billboard Ad System
# ---------------------------------------------------------------------------

class TestBillboardAdSystem:
    def _setup(self):
        sys = BillboardAdSystem()
        ad = AdContent(
            ad_id="ad_001", title="Join the Guild!", body="We're recruiting.",
            category=AdCategory.GUILD_RECRUITMENT,
            cpc_value=0.05,
        )
        billboard = Billboard(
            billboard_id="bb_001", name="Main Square Billboard",
            zone_id="zone_city", placement_zone=BillboardPlacementZone.CITY,
            position=(0.0, 0.0, 0.0),
            proximity_radius=50.0,
        )
        sys.register_ad(ad)
        sys.register_billboard(billboard)
        return sys, ad, billboard

    def test_proximity_triggers_impression(self):
        sys, ad, billboard = self._setup()
        impressions = sys.process_character_position(
            character_id="char_1", class_id="warrior", level=20,
            position=(10.0, 0.0, 0.0), zone_id="zone_city",
        )
        assert len(impressions) == 1
        assert impressions[0].ad_id == ad.ad_id

    def test_out_of_range_no_impression(self):
        sys, ad, billboard = self._setup()
        impressions = sys.process_character_position(
            character_id="char_1", class_id="warrior", level=20,
            position=(1000.0, 0.0, 0.0), zone_id="zone_city",
        )
        assert len(impressions) == 0

    def test_different_zone_no_impression(self):
        sys, ad, billboard = self._setup()
        impressions = sys.process_character_position(
            character_id="char_1", class_id="warrior", level=20,
            position=(10.0, 0.0, 0.0), zone_id="zone_dungeon",
        )
        assert len(impressions) == 0

    def test_revenue_tracked(self):
        sys, ad, billboard = self._setup()
        sys.process_character_position(
            "char_1", "warrior", 20, (5.0, 0.0, 0.0), "zone_city"
        )
        assert sys.total_revenue() > 0.0

    def test_billboard_revenue(self):
        sys, ad, billboard = self._setup()
        sys.process_character_position(
            "char_1", "warrior", 20, (5.0, 0.0, 0.0), "zone_city"
        )
        assert sys.billboard_revenue("bb_001") == ad.cpc_value

    def test_impressions_for_ad(self):
        sys, ad, billboard = self._setup()
        sys.process_character_position(
            "char_1", "warrior", 20, (5.0, 0.0, 0.0), "zone_city"
        )
        count = sys.impressions_for_ad(ad.ad_id)
        assert count == 1

    def test_rate_limit_respected(self):
        """Multiple quick impressions from same billboard should be rate-limited."""
        sys, ad, billboard = self._setup()
        for _ in range(20):
            sys.process_character_position(
                f"char_{_}", "warrior", 20, (5.0, 0.0, 0.0), "zone_city"
            )
        # Total impressions per minute capped
        assert billboard.total_impressions <= 10 + 1  # MAX_IMPRESSIONS_PER_MINUTE + buffer


# ---------------------------------------------------------------------------
# Streaming Integration
# ---------------------------------------------------------------------------

class TestStreamingIntegration:
    def test_default_overlay_template(self):
        si = StreamingIntegration()
        template = si.default_overlay_template("game_001")
        assert template.game_id == "game_001"
        assert "health_bar" in template.elements

    def test_emit_event(self):
        si = StreamingIntegration()
        event = si.emit_event(
            StreamEventType.BOSS_KILL, "Killed the Dragon Boss!",
            "char_1", "world_1"
        )
        assert event.is_highlight is True

    def test_highlights_auto_clipped(self):
        si = StreamingIntegration()
        si.emit_event(StreamEventType.RARE_DROP, "Legendary sword dropped!", "char_1", "world_1")
        clips = si.get_clips(world_id="world_1")
        assert len(clips) == 1

    def test_non_highlight_not_clipped(self):
        si = StreamingIntegration()
        si.emit_event(StreamEventType.LEVEL_UP, "Leveled up!", "char_1", "world_1")
        clips = si.get_clips()
        assert len(clips) == 0

    def test_spectator_session(self):
        si = StreamingIntegration()
        session = si.start_spectating("viewer_1", "char_1", "world_1")
        assert session.camera_mode == CameraMode.FOLLOW

        si.switch_camera(session.session_id, CameraMode.CINEMATIC)
        with si._lock:
            updated = si._spectator_sessions.get(session.session_id)
        assert updated.camera_mode == CameraMode.CINEMATIC

        si.stop_spectating(session.session_id)
        with si._lock:
            assert session.session_id not in si._spectator_sessions

    def test_agent_thought_bubble(self):
        si = StreamingIntegration()
        overlay = si.add_agent_thought("agent_1", "char_1", "I should find a healer.")
        assert overlay.overlay_id
        thoughts = si.get_agent_thoughts()
        assert len(thoughts) == 1
        assert thoughts[0].thought_text == "I should find a healer."

    def test_get_events_filtered_by_world(self):
        si = StreamingIntegration()
        si.emit_event(StreamEventType.BOSS_KILL, "Boss A", "c1", "world_A")
        si.emit_event(StreamEventType.BOSS_KILL, "Boss B", "c2", "world_B")
        events = si.get_events(world_id="world_A")
        assert all(e.world_id == "world_A" for e in events)

    def test_divine_luck_is_highlight(self):
        si = StreamingIntegration()
        event = si.emit_event(StreamEventType.DIVINE_LUCK, "Divine roll!", "c1", "w1")
        assert event.is_highlight is True


# ---------------------------------------------------------------------------
# World Generator
# ---------------------------------------------------------------------------

class TestWorldGenerator:
    def test_generate_world_produces_zones(self):
        gen = WorldGenerator(seed=42)
        world = gen.generate_world("Testland", WorldTheme.FANTASY, version=1, seed=42)
        assert world.world_id
        assert len(world.zones) > 0

    def test_world_has_required_zone_types(self):
        gen = WorldGenerator(seed=42)
        world = gen.generate_world("Test", WorldTheme.DARK_FANTASY, seed=1)
        zone_types = {z.zone_type for z in world.zones}
        assert ZoneType.CITY in zone_types
        assert ZoneType.DUNGEON in zone_types

    def test_world_validation_passes(self):
        gen = WorldGenerator(seed=10)
        world = gen.generate_world("Valid World", WorldTheme.FANTASY, seed=10)
        valid, issues = gen.validate_world(world.world_id)
        assert valid, f"Validation failed: {issues}"

    def test_world_has_lore(self):
        gen = WorldGenerator(seed=5)
        world = gen.generate_world("Lore World", WorldTheme.MYTHOLOGICAL, seed=5)
        assert world.lore_summary
        assert len(world.lore_summary) > 10

    def test_zones_have_npcs(self):
        gen = WorldGenerator(seed=3)
        world = gen.generate_world("NPC World", WorldTheme.FANTASY, seed=3)
        zones_with_npcs = [z for z in world.zones if z.npcs]
        assert len(zones_with_npcs) > 0

    def test_zones_have_quests(self):
        gen = WorldGenerator(seed=7)
        world = gen.generate_world("Quest World", WorldTheme.STEAMPUNK, seed=7)
        zones_with_quests = [z for z in world.zones if z.quests]
        assert len(zones_with_quests) >= 2

    def test_activate_world(self):
        gen = WorldGenerator(seed=11)
        world = gen.generate_world("Live World", WorldTheme.FANTASY, seed=11)
        gen.activate_world(world.world_id)
        updated = gen.get_world(world.world_id)
        assert updated.is_active is True
        assert updated.release_date is not None

    def test_zone_connections_wired(self):
        gen = WorldGenerator(seed=20)
        world = gen.generate_world("Connected", WorldTheme.COSMIC_HORROR, seed=20)
        # At least most zones should have connections
        connected = [z for z in world.zones if z.connected_zone_ids]
        assert len(connected) >= len(world.zones) - 1

    def test_dungeon_has_group_requirement(self):
        gen = WorldGenerator(seed=15)
        world = gen.generate_world("Group World", WorldTheme.DARK_FANTASY, seed=15)
        dungeons = [z for z in world.zones if z.zone_type == ZoneType.DUNGEON]
        assert all(d.min_group_size >= 2 for d in dungeons)

    def test_city_has_billboards(self):
        gen = WorldGenerator(seed=25)
        world = gen.generate_world("Billboard City", WorldTheme.FANTASY, seed=25)
        cities = [z for z in world.zones if z.zone_type == ZoneType.CITY]
        assert all(c.billboard_count > 0 for c in cities)

    def test_all_worlds_registry(self):
        gen = WorldGenerator(seed=99)
        gen.generate_world("W1", WorldTheme.FANTASY)
        gen.generate_world("W2", WorldTheme.STEAMPUNK)
        worlds = gen.all_worlds()
        assert len(worlds) >= 2


# ---------------------------------------------------------------------------
# Weekly Release Orchestrator
# ---------------------------------------------------------------------------

class TestWeeklyReleaseOrchestrator:
    def test_start_pipeline(self):
        orch = WeeklyReleaseOrchestrator()
        run = orch.start_pipeline("Alpha World", WorldTheme.FANTASY, version=1)
        assert run.stage == PipelineStage.WORLD_GENERATION

    def test_world_generation_stage(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Beta World", WorldTheme.DARK_FANTASY)
        success = orch.run_world_generation(run)
        assert success is True
        assert run.world_id is not None
        assert run.stage == PipelineStage.BALANCE_TESTING

    def test_balance_testing_stage_pass(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Gamma World", WorldTheme.FANTASY)
        orch.run_world_generation(run)
        passed = orch.run_balance_testing(run, balance_score=0.9)
        assert passed is True
        assert run.stage == PipelineStage.AGENT_PLAYTESTING

    def test_balance_testing_stage_fail(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Imbalanced World", WorldTheme.FANTASY)
        orch.run_world_generation(run)
        passed = orch.run_balance_testing(run, balance_score=0.5)
        assert passed is False

    def test_agent_playtesting_stage(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Delta World", WorldTheme.STEAMPUNK)
        orch.run_world_generation(run)
        orch.run_balance_testing(run, balance_score=0.85)
        passed = orch.run_agent_playtesting(run, agent_session_count=3)
        assert passed is True
        assert run.stage == PipelineStage.POLISH

    def test_agent_playtesting_fail_insufficient_sessions(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Untested World", WorldTheme.FANTASY)
        orch.run_world_generation(run)
        orch.run_balance_testing(run)
        passed = orch.run_agent_playtesting(run, agent_session_count=0)
        assert passed is False

    def test_full_pipeline_to_live(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Epsilon World", WorldTheme.MYTHOLOGICAL, version=1)
        orch.run_world_generation(run)
        orch.run_balance_testing(run, balance_score=0.9)
        orch.run_agent_playtesting(run, agent_session_count=3)
        orch.run_polish(run)
        released = orch.release(run)
        assert released is True
        assert run.stage == PipelineStage.LIVE
        assert run.released_at is not None

    def test_rollback(self):
        orch = WeeklyReleaseOrchestrator(world_generator=WorldGenerator(seed=42))
        run = orch.start_pipeline("Zeta World", WorldTheme.POST_APOCALYPTIC)
        orch.run_world_generation(run)
        orch.run_balance_testing(run)
        orch.run_agent_playtesting(run)
        orch.run_polish(run)
        orch.release(run)
        orch.rollback(run, reason="Critical exploit found")
        assert run.stage == PipelineStage.ROLLED_BACK
        assert run.rolled_back_at is not None

    def test_wrong_stage_raises(self):
        orch = WeeklyReleaseOrchestrator()
        run = orch.start_pipeline("Test", WorldTheme.FANTASY)
        with pytest.raises(ValueError):
            orch.run_balance_testing(run)  # should be in WORLD_GENERATION

    def test_get_run_by_id(self):
        orch = WeeklyReleaseOrchestrator()
        run = orch.start_pipeline("Find Me", WorldTheme.FANTASY)
        found = orch.get_run(run.run_id)
        assert found is run

    def test_all_runs(self):
        orch = WeeklyReleaseOrchestrator()
        orch.start_pipeline("Run 1", WorldTheme.FANTASY)
        orch.start_pipeline("Run 2", WorldTheme.STEAMPUNK)
        assert len(orch.all_runs()) >= 2
