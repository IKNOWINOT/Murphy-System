"""
Tests for escalation, sleeper event, unmaker NPC, progression server,
and cultural identity modules.
"""

import pytest

from src.eq.escalation_system import (
    EscalationManager,
    EscalationTier,
)
from src.eq.sleeper_event import (
    SleeperEventManager,
    SleeperPhase,
)
from src.eq.unmaker_npc import (
    UNMAKER_ARMOR_SET,
    UnmakerBossConfig,
    UnmakerNPC,
    UnmakerNPCConfig,
    BannedByUnmaker,
)
from src.eq.progression_server import (
    Era,
    ProgressionServer,
    XPConfig,
)
from src.eq.cultural_identity import (
    CulturalIdentityManager,
    CulturalValue,
    RACE_TEMPLATES,
    RaceCulturalTemplate,
)


# ===================================================================
# Escalation System Tests
# ===================================================================

class TestEscalationSystem:

    def test_tier_for_zero_cards(self):
        em = EscalationManager()
        assert em.get_tier(0) == EscalationTier.NONE

    def test_tier_for_one_card(self):
        em = EscalationManager()
        assert em.get_tier(1) == EscalationTier.ONE_CARD

    def test_tier_for_four_cards(self):
        em = EscalationManager()
        assert em.get_tier(4) == EscalationTier.FOUR_CARDS

    def test_one_card_capabilities(self):
        em = EscalationManager()
        cap = em.get_capabilities(EscalationTier.ONE_CARD)
        assert cap.npc_summon_count == 6
        assert cap.origin_zone_rallied is False

    def test_two_card_capabilities(self):
        em = EscalationManager()
        cap = em.get_capabilities(EscalationTier.TWO_CARDS)
        assert cap.origin_zone_rallied is True

    def test_three_card_attackable(self):
        em = EscalationManager()
        threats = em.get_threats(EscalationTier.THREE_CARDS)
        assert threats.attackable_by_all is True
        assert threats.god_dispatched is True

    def test_four_card_immune(self):
        em = EscalationManager()
        cap = em.get_capabilities(EscalationTier.FOUR_CARDS)
        assert cap.unmaker_immune is True
        assert cap.faction_mobilized is True

    def test_announce_card_trade(self):
        em = EscalationManager()
        ann = em.announce_card_trade("PlayerOne", "Emperor Crush", 1)
        assert "PlayerOne" in ann.message
        assert "Emperor Crush" in ann.message

    def test_should_announce_at_3(self):
        em = EscalationManager()
        assert em.should_announce(2) is False
        assert em.should_announce(3) is True

    def test_dragon_dispatch_at_two(self):
        em = EscalationManager()
        threats = em.get_threats(EscalationTier.TWO_CARDS)
        assert threats.dragon_dispatched is True
        assert threats.dragon_timer_days == 3


# ===================================================================
# Sleeper Event Tests
# ===================================================================

class TestSleeperEvent:

    def test_initial_phase_dormant(self):
        sem = SleeperEventManager()
        assert sem.get_phase() == SleeperPhase.DORMANT

    def test_four_warders_alive(self):
        sem = SleeperEventManager()
        assert len(sem.warders_alive) == 4

    def test_engage_warder_starts_event(self):
        sem = SleeperEventManager()
        phase = sem.engage_warder("warder_1")
        assert phase == SleeperPhase.WARDERS_ENGAGED
        assert sem.is_active is True

    def test_kill_warder_progresses(self):
        sem = SleeperEventManager()
        sem.engage_warder("warder_1")
        phase = sem.kill_warder("warder_1")
        assert len(sem.warders_dead) >= 1
        assert len(sem.warders_alive) == 3

    def test_all_warders_dead_triggers_awakening(self):
        sem = SleeperEventManager()
        sem.engage_warder("warder_1")
        for wid in ["warder_1", "warder_2", "warder_3", "warder_4"]:
            sem.kill_warder(wid)
        assert sem.get_phase() == SleeperPhase.AWAKENING

    def test_mutual_aid(self):
        sem = SleeperEventManager()
        sem.activate_mutual_aid()
        assert sem._state.mutual_aid_active is True
        sem.deactivate_mutual_aid()
        assert sem._state.mutual_aid_active is False

    def test_resolve_defeated(self):
        sem = SleeperEventManager()
        sem.engage_warder("warder_1")
        for wid in ["warder_1", "warder_2", "warder_3", "warder_4"]:
            sem.kill_warder(wid)
        phase = sem.resolve_event(kerafyrm_killed=True)
        assert phase == SleeperPhase.DEFEATED

    def test_resolve_escaped(self):
        sem = SleeperEventManager()
        sem.engage_warder("warder_1")
        for wid in ["warder_1", "warder_2", "warder_3", "warder_4"]:
            sem.kill_warder(wid)
        phase = sem.resolve_event(kerafyrm_killed=False)
        assert phase == SleeperPhase.ESCAPED

    def test_dragon_rally(self):
        sem = SleeperEventManager()
        rally = sem.send_dragon_rally("vox", "sleepers_tomb", "ring_of_scale")
        assert rally.responding is True
        assert sem.rally_count >= 1


# ===================================================================
# Unmaker NPC Tests
# ===================================================================

class TestUnmakerNPC:

    def test_armor_set_has_7_pieces(self):
        assert len(UNMAKER_ARMOR_SET) == 7

    def test_armor_pieces_have_5_ac(self):
        for piece in UNMAKER_ARMOR_SET:
            assert piece.ac == 5

    def test_config_defaults(self):
        cfg = UnmakerNPCConfig()
        assert cfg.level == 1
        assert cfg.spawn_rate == 0.01

    def test_can_spawn_is_probabilistic(self):
        npc = UnmakerNPC()
        # Run many times; at least some should return True/False
        results = [npc.can_spawn() for _ in range(1000)]
        assert True in results  # Should spawn sometimes
        assert False in results  # Should not always spawn

    def test_convert_cards_requires_4(self):
        npc = UnmakerNPC()
        # Not enough cards
        result = npc.convert_cards_to_unmaking({"emperor_crush": 3}, "emperor_crush")
        assert result is None
        # Enough cards
        result = npc.convert_cards_to_unmaking({"emperor_crush": 4}, "emperor_crush")
        assert result is not None

    def test_loot_table(self):
        npc = UnmakerNPC()
        loot = npc.get_loot_table()
        assert len(loot) > 0

    def test_boss_config(self):
        cfg = UnmakerBossConfig()
        assert cfg.random_attack_proc_rate == 0.30
        assert cfg.ban_proc_rate == 0.01
        assert cfg.fourth_card_drop_rate == 0.15

    def test_banned_by_unmaker(self):
        ban = BannedByUnmaker(player_id="p1", banned_at=0.0)
        assert ban.ban_duration_days == 2


# ===================================================================
# Progression Server Tests
# ===================================================================

class TestProgressionServer:

    def test_default_starts_classic(self):
        ps = ProgressionServer()
        assert ps.current_era.era == Era.CLASSIC

    def test_advance_era(self):
        ps = ProgressionServer()
        next_era = ps.advance_era()
        assert next_era is not None
        assert next_era.era == Era.KUNARK

    def test_advance_to_end(self):
        ps = ProgressionServer()
        while ps.advance_era() is not None:
            pass
        assert ps.current_era.era == Era.PLANES_OF_POWER
        assert ps.advance_era() is None  # Already at end

    def test_level_cap_classic(self):
        ps = ProgressionServer()
        assert ps.get_level_cap() == 50

    def test_level_cap_pop(self):
        ps = ProgressionServer()
        while ps.current_era.era != Era.PLANES_OF_POWER:
            ps.advance_era()
        assert ps.get_level_cap() == 65

    def test_hell_levels(self):
        ps = ProgressionServer()
        assert ps.is_hell_level(44) is True
        assert ps.is_hell_level(51) is True
        assert ps.is_hell_level(45) is False

    def test_xp_modifier_normal(self):
        ps = ProgressionServer()
        assert ps.calculate_xp_modifier(30) == 1.0

    def test_xp_modifier_hell_level(self):
        ps = ProgressionServer()
        mod = ps.calculate_xp_modifier(44)
        assert mod < 1.0  # Hell level penalty


# ===================================================================
# Cultural Identity Tests
# ===================================================================

class TestCulturalIdentity:

    def test_15_race_templates(self):
        assert len(RACE_TEMPLATES) >= 15

    def test_orc_template_exists(self):
        assert "orc" in RACE_TEMPLATES

    def test_orc_primary_values(self):
        orc = RACE_TEMPLATES["orc"]
        assert CulturalValue.STRENGTH in orc.primary_values
        assert CulturalValue.COMMERCE in orc.primary_values

    def test_orc_starting_city(self):
        assert RACE_TEMPLATES["orc"].starting_city == "crushbone"

    def test_orc_allies(self):
        orc = RACE_TEMPLATES["orc"]
        assert "troll" in orc.allied_races
        assert "ogre" in orc.allied_races

    def test_orc_enemies(self):
        orc = RACE_TEMPLATES["orc"]
        assert "high_elf" in orc.enemy_races

    def test_manager_get_template(self):
        mgr = CulturalIdentityManager()
        template = mgr.get_template("human")
        assert template is not None
        assert template.race_name == "human"

    def test_manager_supported_races(self):
        mgr = CulturalIdentityManager()
        assert mgr.template_count >= 15
        assert "orc" in mgr.supported_races

    def test_get_personality_bias(self):
        mgr = CulturalIdentityManager()
        bias = mgr.get_personality_bias("dark_elf")
        assert isinstance(bias, str)
        assert len(bias) > 0

    def test_get_allied_races(self):
        mgr = CulturalIdentityManager()
        allies = mgr.get_allied_races("dwarf")
        assert isinstance(allies, list)

    def test_get_enemy_races(self):
        mgr = CulturalIdentityManager()
        enemies = mgr.get_enemy_races("high_elf")
        assert isinstance(enemies, list)

    def test_apply_cultural_bias(self):
        mgr = CulturalIdentityManager()
        traits = ["neutral"]
        enhanced = mgr.apply_cultural_bias(traits, "orc")
        assert len(enhanced) > len(traits)  # Should add race-appropriate traits

    def test_all_templates_have_required_fields(self):
        for race, template in RACE_TEMPLATES.items():
            assert template.race_name == race
            assert len(template.primary_values) > 0
            assert len(template.languages) > 0
            assert template.starting_city
