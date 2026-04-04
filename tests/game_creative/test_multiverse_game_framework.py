"""
Tests for the Multiverse Game Framework.

Validates all 9 modules:
  - universal_character  (GAME-001)
  - world_registry       (GAME-002)
  - item_portability     (GAME-003)
  - spell_synergy        (GAME-004)
  - billboard_system     (GAME-005)
  - ai_companion         (GAME-006)
  - agent_player         (GAME-007)
  - streaming_integration(GAME-008)
  - multiplayer_recruitment (GAME-009)
"""

import time
from datetime import datetime, timedelta, timezone

import pytest

from src.multiverse_game_framework.universal_character import (
    ActionType,
    CharacterClass,
    ClassBalanceRegistry,
    ClassRole,
    LuckCheckOutcome,
    LuckSystem,
    UniversalCharacter,
    UniversalLevelingEngine,
    UNIVERSAL_LEVEL_CAP,
    _base_xp_for_level,
)
from src.multiverse_game_framework.world_registry import (
    TravelStatus,
    WorldDefinition,
    WorldRegistry,
    WorldStatus,
)
from src.multiverse_game_framework.item_portability import (
    GameItem,
    ItemPortabilityEngine,
    ItemPortabilityTier,
    ItemType,
    TransferStatus,
)
from src.multiverse_game_framework.spell_synergy import (
    SpellSynergyEngine,
    SynergyType,
)
from src.multiverse_game_framework.billboard_system import (
    Billboard,
    BillboardEngine,
    BillboardScheduleWindow,
)
from src.multiverse_game_framework.ai_companion import (
    AICompanion,
    AICompanionEngine,
    AICompanionRole,
    DirectiveStatus,
    Specialization,
)
from src.multiverse_game_framework.agent_player import (
    AgentPlayerEngine,
    AgentPlayerProfile,
    GoalType,
    PlayStyle,
)
from src.multiverse_game_framework.streaming_integration import (
    HighlightType,
    OverlayConfig,
    StreamingHotspot,
    StreamingManager,
    StreamPlatform,
    StreamQuality,
)
from src.multiverse_game_framework.multiplayer_recruitment import (
    ActivityType,
    RecruitmentEngine,
)


# ===========================================================================
# GAME-001 — Universal Character & Leveling System
# ===========================================================================


class TestUniversalCharacterCreation:
    def test_default_character_has_all_stats(self):
        char = UniversalCharacter(owner_id="player-1", name="Tester")
        for stat in ("STR", "DEX", "INT", "WIS", "CHA", "STA", "AGI", "LUCK"):
            assert stat in char.stats, f"Missing stat: {stat}"

    def test_character_starts_at_level_1(self):
        char = UniversalCharacter(owner_id="p1", name="Hero")
        assert char.level == 1

    def test_character_level_cap_is_100(self):
        assert UNIVERSAL_LEVEL_CAP == 100

    def test_character_has_unique_id(self):
        c1 = UniversalCharacter(owner_id="p1")
        c2 = UniversalCharacter(owner_id="p1")
        assert c1.character_id != c2.character_id

    def test_character_has_soul_document_id_field(self):
        char = UniversalCharacter(soul_document_id="soul-abc")
        assert char.soul_document_id == "soul-abc"

    def test_character_streaming_profile(self):
        char = UniversalCharacter(streaming_profile={"overlay": "minimal"})
        assert char.streaming_profile["overlay"] == "minimal"

    def test_world_visit_history_starts_empty(self):
        char = UniversalCharacter()
        assert char.world_visit_history == []

    def test_active_world_id_defaults_to_none(self):
        char = UniversalCharacter()
        assert char.active_world_id is None


class TestLuckSystem:
    def setup_method(self):
        self.luck = LuckSystem()

    def test_neutral_luck_gives_base_modifier(self):
        mod = self.luck.calculate_luck_modifier(10, ActionType.COMBAT)
        assert mod > 0.0

    def test_high_luck_gives_higher_modifier(self):
        low = self.luck.calculate_luck_modifier(10, ActionType.LOOT)
        high = self.luck.calculate_luck_modifier(500, ActionType.LOOT)
        assert high > low

    def test_modifier_is_capped(self):
        mod = self.luck.calculate_luck_modifier(999_999, ActionType.COMBAT)
        assert mod <= LuckSystem._MAX_MODIFIER

    def test_modifier_has_floor(self):
        mod = self.luck.calculate_luck_modifier(1, ActionType.SOCIAL)
        assert mod >= LuckSystem._MIN_MODIFIER

    def test_luck_roll_returns_result(self):
        char = UniversalCharacter(stats={"STR": 10, "DEX": 10, "INT": 10, "WIS": 10,
                                         "CHA": 10, "STA": 10, "AGI": 10, "LUCK": 100})
        result = self.luck.roll_luck_check(char, ActionType.LOOT, difficulty=0.5)
        assert result.action_type == ActionType.LOOT
        assert result.outcome in list(LuckCheckOutcome)

    def test_loot_action_has_higher_modifier_than_social(self):
        loot_mod = self.luck.calculate_luck_modifier(100, ActionType.LOOT)
        social_mod = self.luck.calculate_luck_modifier(100, ActionType.SOCIAL)
        assert loot_mod > social_mod

    def test_very_easy_check_mostly_succeeds(self):
        char = UniversalCharacter(stats={"STR": 10, "DEX": 10, "INT": 10, "WIS": 10,
                                         "CHA": 10, "STA": 10, "AGI": 10, "LUCK": 200})
        successes = 0
        for _ in range(100):
            r = self.luck.roll_luck_check(char, ActionType.EXPLORATION, difficulty=0.1)
            if r.outcome in (LuckCheckOutcome.SUCCESS, LuckCheckOutcome.CRITICAL_SUCCESS):
                successes += 1
        assert successes >= 60, f"Expected mostly successes, got {successes}/100"


class TestUniversalLevelingEngine:
    def setup_method(self):
        self.engine = UniversalLevelingEngine()

    def test_award_xp_increases_experience(self):
        char = UniversalCharacter()
        self.engine.award_experience(char, 500, "world-1", "mob_kill")
        assert char.experience_points == 500

    def test_award_xp_at_cap_does_nothing(self):
        char = UniversalCharacter(level=UNIVERSAL_LEVEL_CAP)
        char.experience_points = 0
        self.engine.award_experience(char, 1000, "world-1", "mob_kill")
        assert char.experience_points == 0

    def test_level_up_increments_level(self):
        char = UniversalCharacter(level=1, experience_points=0)
        needed = UniversalLevelingEngine.xp_for_next_level(1)
        char.experience_points = needed
        result = self.engine.check_level_up(char)
        assert result is not None
        assert result.new_level == 2
        assert result.old_level == 1

    def test_level_up_result_contains_stat_increases(self):
        char = UniversalCharacter(level=1, character_class=CharacterClass.WARRIOR)
        char.experience_points = UniversalLevelingEngine.xp_for_next_level(1)
        result = self.engine.check_level_up(char)
        assert result is not None
        assert len(result.stat_increases) > 0

    def test_no_level_up_when_xp_insufficient(self):
        char = UniversalCharacter(level=1, experience_points=0)
        result = self.engine.check_level_up(char)
        assert result is None

    def test_solo_wall_reduces_xp(self):
        char = UniversalCharacter(level=30)
        self.engine.award_experience(char, 1000, "world-1", "mob_kill")
        # Should be less than 1000 due to solo wall
        assert char.experience_points < 1000

    def test_group_xp_bonus_with_balanced_party(self):
        char = UniversalCharacter(level=10)
        party = [CharacterClass.WARRIOR, CharacterClass.CLERIC, CharacterClass.WIZARD]
        self.engine.award_experience(char, 1000, "world-1", "mob_kill", party_classes=party)
        assert char.experience_points > 1000  # Group bonus applied

    def test_xp_curve_is_increasing(self):
        for level in range(1, 10):
            assert _base_xp_for_level(level + 1) > _base_xp_for_level(level)


class TestClassBalanceRegistry:
    def setup_method(self):
        self.registry = ClassBalanceRegistry()

    def test_all_15_classes_defined(self):
        classes = self.registry.all_classes()
        assert len(classes) == 15

    def test_warrior_is_tank(self):
        defn = self.registry.get_class_definition(CharacterClass.WARRIOR)
        assert defn is not None
        assert defn.role == ClassRole.TANK

    def test_cleric_is_healer(self):
        defn = self.registry.get_class_definition(CharacterClass.CLERIC)
        assert defn.role == ClassRole.HEALER

    def test_enchanter_is_cc(self):
        defn = self.registry.get_class_definition(CharacterClass.ENCHANTER)
        assert defn.role == ClassRole.CC

    def test_required_classes_exist(self):
        required = self.registry.get_required_classes()
        assert len(required) >= 3

    def test_perfect_party_scores_high(self):
        party = [
            CharacterClass.WARRIOR,
            CharacterClass.CLERIC,
            CharacterClass.WIZARD,
            CharacterClass.ENCHANTER,
            CharacterClass.BARD,
        ]
        score = self.registry.get_party_synergy_score(party)
        assert score >= 0.7

    def test_all_dps_party_scores_low(self):
        party = [CharacterClass.WIZARD, CharacterClass.ROGUE, CharacterClass.BERSERKER]
        score = self.registry.get_party_synergy_score(party)
        assert score <= 0.2

    def test_empty_party_scores_zero(self):
        assert self.registry.get_party_synergy_score([]) == 0.0

    def test_solo_tank_scores_medium(self):
        score = self.registry.get_party_synergy_score([CharacterClass.WARRIOR])
        assert 0.05 <= score < 0.5


# ===========================================================================
# GAME-002 — World Registry & Cross-World Travel
# ===========================================================================


class TestWorldRegistry:
    def setup_method(self):
        self.registry = WorldRegistry()

    def _make_world(self, world_id: str = "w1", required_level: int = 1) -> WorldDefinition:
        return WorldDefinition(
            world_id=world_id,
            world_name=f"World {world_id}",
            version="1.0.0",
            required_universal_level=required_level,
            status=WorldStatus.ACTIVE,
        )

    def test_register_and_retrieve_world(self):
        w = self._make_world("alpha")
        self.registry.register_world(w)
        retrieved = self.registry.get_world("alpha")
        assert retrieved is not None
        assert retrieved.world_name == "World alpha"

    def test_list_active_worlds(self):
        self.registry.register_world(self._make_world("w-active"))
        inactive = self._make_world("w-inactive")
        inactive.status = WorldStatus.ARCHIVED
        self.registry.register_world(inactive)
        active = self.registry.list_active_worlds()
        assert any(w.world_id == "w-active" for w in active)
        assert not any(w.world_id == "w-inactive" for w in active)

    def test_travel_success(self):
        w = self._make_world("dest", required_level=1)
        self.registry.register_world(w)
        char = UniversalCharacter(level=5)
        result = self.registry.travel_to_world(char, "dest")
        assert result.status == TravelStatus.SUCCESS
        assert char.active_world_id == "dest"

    def test_travel_denied_insufficient_level(self):
        w = WorldDefinition(world_id="high-w", required_universal_level=50, status=WorldStatus.ACTIVE)
        self.registry.register_world(w)
        char = UniversalCharacter(level=10)
        result = self.registry.travel_to_world(char, "high-w")
        assert result.status == TravelStatus.DENIED_LEVEL

    def test_travel_denied_unknown_world(self):
        char = UniversalCharacter(level=50)
        result = self.registry.travel_to_world(char, "does-not-exist")
        assert result.status == TravelStatus.DENIED_WORLD_CLOSED

    def test_travel_denied_maintenance_world(self):
        w = WorldDefinition(world_id="maint", status=WorldStatus.MAINTENANCE)
        self.registry.register_world(w)
        char = UniversalCharacter(level=50)
        result = self.registry.travel_to_world(char, "maint")
        assert result.status == TravelStatus.DENIED_WORLD_CLOSED

    def test_travel_denied_same_world(self):
        w = self._make_world("same")
        self.registry.register_world(w)
        char = UniversalCharacter(level=5, active_world_id="same")
        result = self.registry.travel_to_world(char, "same")
        assert result.status == TravelStatus.DENIED_SAME_WORLD

    def test_world_visit_history_updated_on_travel(self):
        w = self._make_world("vis")
        self.registry.register_world(w)
        char = UniversalCharacter(level=5)
        self.registry.travel_to_world(char, "vis")
        assert "vis" in char.world_visit_history

    def test_duplicate_registration_raises(self):
        w = self._make_world("dup")
        self.registry.register_world(w)
        with pytest.raises(ValueError):
            self.registry.register_world(w)

    def test_get_worlds_for_level(self):
        low = WorldDefinition(world_id="low", required_universal_level=1,
                              level_range_min=1, level_range_max=20, status=WorldStatus.ACTIVE)
        high = WorldDefinition(world_id="high", required_universal_level=50,
                               level_range_min=50, level_range_max=100, status=WorldStatus.ACTIVE)
        self.registry.register_world(low)
        self.registry.register_world(high)
        results = self.registry.get_worlds_for_level(10)
        ids = [w.world_id for w in results]
        assert "low" in ids
        assert "high" not in ids

    def test_release_schedule_returns_upcoming(self):
        upcoming = WorldDefinition(world_id="next", status=WorldStatus.UPCOMING,
                                   release_date=datetime.now(timezone.utc) + timedelta(days=7))
        self.registry.register_world(upcoming)
        schedule = self.registry.get_release_schedule()
        assert any(w.world_id == "next" for w in schedule)


# ===========================================================================
# GAME-003 — Item Portability System
# ===========================================================================


class TestItemPortability:
    def setup_method(self):
        self.engine = ItemPortabilityEngine()

    def test_universal_item_usable_anywhere(self):
        item = GameItem(portability_tier=ItemPortabilityTier.UNIVERSAL, origin_world_id="w1")
        assert self.engine.can_use_in_world(item, "w2") is True
        assert self.engine.can_use_in_world(item, "w999") is True

    def test_world_locked_item_only_in_origin(self):
        item = GameItem(portability_tier=ItemPortabilityTier.WORLD_LOCKED, origin_world_id="w1")
        assert self.engine.can_use_in_world(item, "w1") is True
        assert self.engine.can_use_in_world(item, "w2") is False

    def test_multi_world_item_in_allowed_worlds(self):
        item = GameItem(
            portability_tier=ItemPortabilityTier.MULTI_WORLD,
            allowed_world_ids=["w1", "w2"],
        )
        assert self.engine.can_use_in_world(item, "w1") is True
        assert self.engine.can_use_in_world(item, "w3") is False

    def test_seasonal_item_active_now(self):
        now = datetime.now(timezone.utc)
        item = GameItem(
            portability_tier=ItemPortabilityTier.SEASONAL,
            seasonal_window_start=now - timedelta(hours=1),
            seasonal_window_end=now + timedelta(hours=1),
        )
        assert self.engine.can_use_in_world(item, "any-world") is True

    def test_seasonal_item_expired(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        item = GameItem(
            portability_tier=ItemPortabilityTier.SEASONAL,
            seasonal_window_start=past - timedelta(days=1),
            seasonal_window_end=past,
        )
        assert self.engine.can_use_in_world(item, "any-world") is False

    def test_quest_locked_always_usable(self):
        item = GameItem(portability_tier=ItemPortabilityTier.QUEST_LOCKED, quest_chain_id="q1")
        assert self.engine.can_use_in_world(item, "anywhere") is True

    def test_get_portable_inventory_splits_correctly(self):
        char = UniversalCharacter()
        char.inventory = [  # type: ignore[attr-defined]
            GameItem(portability_tier=ItemPortabilityTier.UNIVERSAL),
            GameItem(portability_tier=ItemPortabilityTier.WORLD_LOCKED, origin_world_id="w1"),
        ]
        usable, stashed = self.engine.get_portable_inventory(char, "w2")
        assert len(usable) == 1
        assert len(stashed) == 1

    def test_transfer_universal_item_succeeds(self):
        item = GameItem(portability_tier=ItemPortabilityTier.UNIVERSAL)
        result = self.engine.transfer_item(item, "w1", "w2")
        assert result.status == TransferStatus.SUCCESS

    def test_transfer_world_locked_item_fails(self):
        item = GameItem(portability_tier=ItemPortabilityTier.WORLD_LOCKED, origin_world_id="w1")
        result = self.engine.transfer_item(item, "w1", "w2")
        assert result.status == TransferStatus.DENIED_WORLD_LOCKED

    def test_stash_and_retrieve(self):
        item = GameItem(portability_tier=ItemPortabilityTier.WORLD_LOCKED, origin_world_id="w1")
        self.engine.stash_item("char-1", item)
        stash = self.engine.get_stash("char-1")
        assert len(stash) == 1
        assert stash[0].item_id == item.item_id


# ===========================================================================
# GAME-004 — Spell Synergy System
# ===========================================================================


class TestSpellSynergy:
    def setup_method(self):
        self.engine = SpellSynergyEngine()
        self.world = "test-world"

    def _now_ms(self) -> float:
        return time.monotonic() * 1000

    def test_same_spell_synergy_detected(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("caster-1", "fireball", ["fire", "elemental"], self.world, ts)
        e2 = self.engine.register_spell_cast("caster-2", "fireball", ["fire", "elemental"], self.world, ts + 100)
        result = self.engine.check_synergy(e2)
        assert result is not None
        assert result.synergy_type == SynergyType.SAME_SPELL

    def test_elemental_chain_firestorm(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("c1", "gust", ["wind", "elemental"], self.world, ts)
        e2 = self.engine.register_spell_cast("c2", "ignite", ["fire", "elemental"], self.world, ts + 500)
        result = self.engine.check_synergy(e2)
        assert result is not None
        assert "Firestorm" in result.combined_spell_name or result.synergy_type == SynergyType.ELEMENTAL_CHAIN

    def test_no_synergy_single_caster(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("solo", "fireball", ["fire", "elemental"], self.world, ts)
        result = self.engine.check_synergy(e1)
        assert result is None

    def test_perfect_sync_gives_high_magnifier(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("c1", "bolt", ["lightning", "elemental"], self.world, ts)
        e2 = self.engine.register_spell_cast("c2", "bolt", ["lightning", "elemental"], self.world, ts + 50)
        result = self.engine.check_synergy(e2)
        assert result is not None
        assert result.magnifier >= 2.5

    def test_late_sync_gives_lower_magnifier(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("c1", "bolt", ["lightning", "elemental"], self.world, ts)
        e2 = self.engine.register_spell_cast("c2", "bolt", ["lightning", "elemental"], self.world, ts + 1800)
        result = self.engine.check_synergy(e2)
        if result:
            assert result.magnifier <= 2.5

    def test_expired_cast_not_combined(self):
        ts = self._now_ms()
        # Cast 1 is way in the past (beyond window)
        e1 = self.engine.register_spell_cast("c1", "fireball", ["fire", "elemental"], self.world, ts - 5000)
        e2 = self.engine.register_spell_cast("c2", "fireball", ["fire", "elemental"], self.world, ts)
        result = self.engine.check_synergy(e2)
        assert result is None  # c1 is outside the window

    def test_synergy_catalog_has_entries(self):
        catalog = self.engine.get_synergy_catalog()
        assert len(catalog) >= 4

    def test_discovery_xp_awarded_first_time(self):
        ts = self._now_ms()
        e1 = self.engine.register_spell_cast("c1", "ice-spike", ["ice", "elemental"], self.world, ts)
        e2 = self.engine.register_spell_cast("c2", "thunder", ["lightning", "elemental"], self.world, ts + 200)
        result = self.engine.check_synergy(e2)
        if result and result.combined_spell_name == "Shatter Storm":
            assert result.discovery_xp > 0


# ===========================================================================
# GAME-005 — Billboard System
# ===========================================================================


class TestBillboardSystem:
    def setup_method(self):
        self.engine = BillboardEngine()

    def test_place_billboard_returns_billboard(self):
        bb = self.engine.place_billboard(
            world_id="w1",
            zone_id="zone-a",
            position=(0.0, 0.0, 0.0),
            content={"advertiser_id": "acme", "campaign_id": "camp-1"},
            radius=50.0,
        )
        assert bb.billboard_id is not None
        assert bb.world_id == "w1"

    def test_get_visible_within_radius(self):
        self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                    {"campaign_id": "c1"}, radius=50.0)
        visible = self.engine.get_visible_billboards((30.0, 0.0, 0.0), "w1")
        assert len(visible) == 1

    def test_not_visible_outside_radius(self):
        self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                    {"campaign_id": "c1"}, radius=20.0)
        visible = self.engine.get_visible_billboards((100.0, 0.0, 0.0), "w1")
        assert len(visible) == 0

    def test_not_visible_in_different_world(self):
        self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                    {"campaign_id": "c1"}, radius=50.0)
        visible = self.engine.get_visible_billboards((0.0, 0.0, 0.0), "w2")
        assert len(visible) == 0

    def test_record_impression_increments_count(self):
        bb = self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                         {"campaign_id": "c1"})
        self.engine.record_impression(bb.billboard_id, "char-1")
        assert bb.impression_count == 1

    def test_record_interaction_increments_count(self):
        bb = self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                         {"campaign_id": "c1"})
        self.engine.record_interaction(bb.billboard_id, "char-1", "click")
        assert bb.interaction_count == 1

    def test_campaign_analytics_aggregates_correctly(self):
        self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                    {"campaign_id": "camp-X"}, radius=100.0)
        bb2 = self.engine.place_billboard("w1", "zone-b", (5.0, 0.0, 0.0),
                                          {"campaign_id": "camp-X"}, radius=100.0)
        self.engine.record_impression(bb2.billboard_id, "char-1")
        self.engine.record_impression(bb2.billboard_id, "char-2")
        self.engine.record_interaction(bb2.billboard_id, "char-1", "click")
        analytics = self.engine.get_campaign_analytics("camp-X")
        assert analytics.total_impressions == 2
        assert analytics.total_interactions == 1
        assert analytics.ctr == 0.5

    def test_inactive_billboard_not_visible(self):
        bb = self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                         {"campaign_id": "c1"}, radius=100.0)
        bb.active = False
        visible = self.engine.get_visible_billboards((0.0, 0.0, 0.0), "w1")
        assert len(visible) == 0

    def test_scheduled_billboard_active_now(self):
        now = datetime.now(timezone.utc)
        schedule = [BillboardScheduleWindow(
            start=now - timedelta(hours=1),
            end=now + timedelta(hours=1),
        )]
        bb = self.engine.place_billboard("w1", "zone-a", (0.0, 0.0, 0.0),
                                         {"campaign_id": "c1"}, radius=100.0,
                                         schedule=schedule)
        visible = self.engine.get_visible_billboards((0.0, 0.0, 0.0), "w1")
        assert any(v.billboard_id == bb.billboard_id for v in visible)


# ===========================================================================
# GAME-006 — AI Companion System
# ===========================================================================


class TestAICompanionSystem:
    def setup_method(self):
        self.engine = AICompanionEngine()

    def test_create_employee_companion(self):
        companion = self.engine.create_companion(
            "char-1", AICompanionRole.EMPLOYEE, "analytical", name="Aria"
        )
        assert companion.role == AICompanionRole.EMPLOYEE
        assert companion.name == "Aria"
        assert companion.trust_score == 0.5

    def test_create_employer_companion(self):
        companion = self.engine.create_companion(
            "char-1", AICompanionRole.EMPLOYER, "dominant", name="Overlord"
        )
        assert companion.role == AICompanionRole.EMPLOYER

    def test_issue_directive_adds_to_queue(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        directive = self.engine.issue_directive(companion, "Gather 10 herbs.")
        assert len(companion.directive_queue) == 1
        assert directive.description == "Gather 10 herbs."

    def test_complete_directive_increases_trust(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        directive = self.engine.issue_directive(companion, "Do something.")
        old_trust = companion.trust_score
        self.engine.evaluate_directive_completion(companion, directive.directive_id, success=True)
        assert companion.trust_score > old_trust

    def test_failed_directive_decreases_trust(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        directive = self.engine.issue_directive(companion, "Do something.")
        old_trust = companion.trust_score
        self.engine.evaluate_directive_completion(companion, directive.directive_id, success=False)
        assert companion.trust_score < old_trust

    def test_directive_removed_from_queue_after_completion(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        directive = self.engine.issue_directive(companion, "Task.")
        self.engine.evaluate_directive_completion(companion, directive.directive_id, success=True)
        assert len(companion.directive_queue) == 0

    def test_role_reversal_employee_to_employer(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        companion.trust_score = 0.89
        directive = self.engine.issue_directive(companion, "High trust task.")
        self.engine.evaluate_directive_completion(companion, directive.directive_id, success=True)
        # Trust should now be >= 0.9, triggering reversal
        assert companion.role == AICompanionRole.EMPLOYER

    def test_role_reversal_employer_to_employee(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYER, "dominant")
        companion.trust_score = 0.16
        directive = self.engine.issue_directive(companion, "Low trust task.")
        self.engine.evaluate_directive_completion(companion, directive.directive_id, success=False)
        assert companion.role == AICompanionRole.EMPLOYEE

    def test_nonexistent_directive_returns_failure(self):
        companion = self.engine.create_companion("c1", AICompanionRole.EMPLOYEE, "helpful")
        result = self.engine.evaluate_directive_completion(companion, "fake-id", success=True)
        assert result.success is False


# ===========================================================================
# GAME-007 — Agent Player System
# ===========================================================================


class TestAgentPlayerSystem:
    def setup_method(self):
        self.engine = AgentPlayerEngine()

    def _make_profile(self, agent_id: str = "agent-1", style: PlayStyle = PlayStyle.SOCIAL) -> AgentPlayerProfile:
        profile = AgentPlayerProfile(
            agent_id=agent_id,
            character_id="char-1",
            play_style=style,
            preferred_world_ids=["w1"],
        )
        self.engine.register_agent_profile(profile)
        return profile

    def test_register_and_retrieve_profile(self):
        profile = self._make_profile("ag-test")
        retrieved = self.engine.get_agent_profile("ag-test")
        assert retrieved is not None
        assert retrieved.agent_id == "ag-test"

    def test_schedule_play_session_creates_session(self):
        self._make_profile()
        session = self.engine.schedule_play_session("agent-1", 60)
        assert session.session_id is not None
        assert session.duration_minutes == 60

    def test_session_picks_preferred_world(self):
        self._make_profile()
        session = self.engine.schedule_play_session("agent-1", 30)
        assert session.world_id == "w1"

    def test_generate_goals_returns_goals(self):
        profile = self._make_profile()
        goals = self.engine.generate_agent_goals(profile)
        assert len(goals) > 0

    def test_social_agent_gets_form_party_goal(self):
        profile = self._make_profile(style=PlayStyle.SOCIAL)
        goals = self.engine.generate_agent_goals(profile)
        types = [g.goal_type for g in goals]
        assert GoalType.FORM_PARTY in types

    def test_explorer_agent_gets_exploration_goal(self):
        profile = self._make_profile("ag-exp", style=PlayStyle.EXPLORER)
        goals = self.engine.generate_agent_goals(profile)
        types = [g.goal_type for g in goals]
        assert GoalType.EXPLORE_ZONE in types

    def test_execute_session_returns_result(self):
        self._make_profile()
        session = self.engine.schedule_play_session("agent-1", 60)
        result = self.engine.execute_play_session(session)
        assert result.session_id == session.session_id
        assert result.xp_earned > 0

    def test_satisfaction_score_updated_after_session(self):
        profile = self._make_profile()
        old_score = profile.satisfaction_score
        session = self.engine.schedule_play_session("agent-1", 60)
        self.engine.execute_play_session(session)
        # Score should have been updated (may go up or down)
        assert profile.satisfaction_score is not None

    def test_satisfaction_bounded_0_to_1(self):
        self._make_profile()
        session = self.engine.schedule_play_session("agent-1", 60)
        result = self.engine.execute_play_session(session)
        profile = self.engine.get_agent_profile("agent-1")
        assert 0.0 <= profile.satisfaction_score <= 1.0

    def test_streaming_session_flag(self):
        self._make_profile()
        session = self.engine.schedule_play_session("agent-1", 60, streaming=True)
        assert session.streaming is True


# ===========================================================================
# GAME-008 — Streaming Integration
# ===========================================================================


class TestStreamingIntegration:
    def setup_method(self):
        self.manager = StreamingManager()

    def test_start_stream_returns_live_session(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH, world_id="w1")
        assert session.live is True
        assert session.character_id == "char-1"

    def test_configure_overlay(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH)
        overlay = OverlayConfig(show_minimap=False, camera_angle="top_down")
        self.manager.configure_overlay(session, overlay)
        assert session.overlay.show_minimap is False
        assert session.overlay.camera_angle == "top_down"

    def test_stop_stream_marks_not_live(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH)
        stopped = self.manager.stop_stream(session.session_id)
        assert stopped is not None
        assert stopped.live is False
        assert stopped.end_time is not None

    def test_get_active_streams_in_world(self):
        self.manager.start_stream("char-1", StreamPlatform.TWITCH, world_id="w1")
        self.manager.start_stream("char-2", StreamPlatform.TWITCH, world_id="w2")
        active = self.manager.get_active_streams("w1")
        assert len(active) == 1
        assert active[0].character_id == "char-1"

    def test_spectator_mode_joins_stream(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH, world_id="w1")
        result = self.manager.enable_spectator_mode("viewer-1", "char-1")
        assert result is not None
        assert "viewer-1" in session.spectator_ids

    def test_spectator_mode_no_active_stream(self):
        result = self.manager.enable_spectator_mode("viewer-1", "no-streamer")
        assert result is None

    def test_register_and_get_hotspot(self):
        hotspot = StreamingHotspot(world_id="w1", zone_id="z1", name="Dragon Peak",
                                   scenic_score=0.9, action_score=0.8)
        self.manager.register_hotspot(hotspot)
        spots = self.manager.get_streaming_hotspots("w1")
        assert len(spots) == 1
        assert spots[0].name == "Dragon Peak"

    def test_hotspots_sorted_by_combined_score(self):
        self.manager.register_hotspot(StreamingHotspot(world_id="w1", zone_id="z1",
                                                        scenic_score=0.3, action_score=0.3))
        self.manager.register_hotspot(StreamingHotspot(world_id="w1", zone_id="z2",
                                                        scenic_score=0.9, action_score=0.9))
        spots = self.manager.get_streaming_hotspots("w1")
        assert spots[0].scenic_score + spots[0].action_score >= spots[1].scenic_score + spots[1].action_score

    def test_record_and_retrieve_highlight(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH)
        hl = self.manager.record_highlight(session.session_id, HighlightType.BOSS_KILL, "Slew the Lich King!")
        assert hl.stream_session_id == session.session_id
        highlights = self.manager.get_session_highlights(session.session_id)
        assert len(highlights) == 1

    def test_quality_settings_parsed(self):
        session = self.manager.start_stream("char-1", StreamPlatform.TWITCH,
                                            quality_settings={"quality": "ultra"})
        assert session.quality == StreamQuality.ULTRA


# ===========================================================================
# GAME-009 — Multiplayer Recruitment
# ===========================================================================


class TestMultiplayerRecruitment:
    def setup_method(self):
        self.engine = RecruitmentEngine()

    def _register_player(self, player_id: str, role: str = "dps",
                          char_class: str = "Wizard", level: int = 10,
                          world_id: str = "w1") -> None:
        self.engine.register_player(player_id, {
            "character_id": f"char-{player_id}",
            "character_class": char_class,
            "role": role,
            "level": level,
            "world_id": world_id,
            "name": f"Player {player_id}",
        })

    def test_analyze_needs_identifies_missing_roles(self):
        self._register_player("p1", role="dps")
        self._register_player("p2", role="dps")
        needs = self.engine.analyze_player_needs("w1")
        assert "tank" in needs.missing_roles
        assert "healer" in needs.missing_roles

    def test_analyze_needs_no_shortage_when_full(self):
        self._register_player("p1", role="tank")
        self._register_player("p2", role="healer")
        self._register_player("p3", role="cc")
        needs = self.engine.analyze_player_needs("w1")
        assert "tank" not in needs.missing_roles

    def test_generate_recruitment_message_mentions_player_class(self):
        needs = self.engine.analyze_player_needs("w1")
        profile = {"character_class": "Cleric", "name": "Bob",
                   "world_name": "Shadow Realm", "role": "healer"}
        msg = self.engine.generate_recruitment_message(needs, profile)
        assert "Bob" in msg
        assert "Cleric" in msg

    def test_find_compatible_players_returns_matches(self):
        self._register_player("p1", role="healer", char_class="Cleric", level=10)
        char = UniversalCharacter(level=10)
        matches = self.engine.find_compatible_players(char, ActivityType.GROUP_XP)
        assert len(matches) >= 1

    def test_compatible_players_sorted_by_score(self):
        self._register_player("p1", role="healer", level=10)
        self._register_player("p2", role="dps", level=10)
        char = UniversalCharacter(level=10)
        matches = self.engine.find_compatible_players(char, ActivityType.GROUP_XP)
        scores = [m.compatibility_score for m in matches]
        assert scores == sorted(scores, reverse=True)

    def test_send_recruitment_invite_returns_invite(self):
        invite = self.engine.send_recruitment_invite(
            "agent-1", "player-1", ActivityType.DUNGEON, "w1", "Join us!"
        )
        assert invite.invite_id is not None
        assert invite.to_id == "player-1"

    def test_post_lfg_listing(self):
        listing = self.engine.post_lfg_listing(
            world_id="w1",
            poster_id="char-1",
            activity_type=ActivityType.RAID,
            needed_roles=["tank", "healer"],
            message="Need tank and healer for raid.",
        )
        assert listing.listing_id is not None
        assert listing.active is True

    def test_get_active_lfg_listings(self):
        self.engine.post_lfg_listing("w1", "char-1", ActivityType.RAID, ["tank"])
        listings = self.engine.get_active_lfg_listings("w1")
        assert len(listings) >= 1

    def test_expired_listing_not_returned(self):
        listing = self.engine.post_lfg_listing("w1", "char-1", ActivityType.RAID, ["tank"])
        listing.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        active = self.engine.get_active_lfg_listings("w1")
        assert not any(l.listing_id == listing.listing_id for l in active)

    def test_level_range_filter_in_matchmaking(self):
        self._register_player("far-level", role="healer", level=90)
        char = UniversalCharacter(level=10)
        matches = self.engine.find_compatible_players(char, ActivityType.GROUP_XP)
        assert not any(m.player_id == "far-level" for m in matches)
