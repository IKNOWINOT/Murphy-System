"""
Tests for the 5 game-system EQ modules.

Validates:
  - Sorceror class (sorceror_class.py)
  - Duel controller (duel_controller.py)
  - Tower of the Unmaker zone (tower_zone.py)
  - Remake system (remake_system.py)
  - Server reboot / decay vote (server_reboot.py)
"""

import pytest

from src.eq.sorceror_class import (
    AIR_PROCS,
    DISCIPLINE_RUMBLECRUSH,
    EARTH_PROCS,
    ElementType,
    FIRE_PROCS,
    LORD_OF_THE_MAELSTROM,
    PetDefinition,
    ProcEffect,
    SORCEROR_ABILITIES,
    SorcerorConfig,
    SorcerorState,
    WATER_PROCS,
    can_summon_pet,
    switch_element,
)
from src.eq.duel_controller import (
    DuelChallenge,
    DuelController,
    DuelOutcome,
    DuelState,
)
from src.eq.tower_zone import (
    TowerConfig,
    TowerLocation,
    TowerState,
    TowerZone,
)
from src.eq.remake_system import (
    REMAKE_BONUS_PERCENT,
    RemakeRecord,
    RemakeSystem,
)
from src.eq.server_reboot import (
    DecayVoteManager,
    ServerRebootController,
    Vote,
    VoteChoice,
    VoteResult,
)
from src.eq.card_system import CardCollection, CardOfUnmaking


# ===================================================================
# Sorceror Class Tests
# ===================================================================

class TestSorcerorClass:

    def test_config_eligible_races(self):
        cfg = SorcerorConfig()
        assert "Dark Elf" in cfg.eligible_races
        assert "Erudite" in cfg.eligible_races
        assert "Human" in cfg.eligible_races
        assert "High Elf" in cfg.eligible_races
        assert "Gnome" in cfg.eligible_races

    def test_config_armor_restrictions(self):
        cfg = SorcerorConfig()
        assert "cloth" in cfg.armor_restrictions
        assert "leather" in cfg.armor_restrictions

    def test_config_weapon_restrictions(self):
        cfg = SorcerorConfig()
        assert "1H slashing" in cfg.weapon_restrictions
        assert "1H piercing" in cfg.weapon_restrictions
        assert "staves" in cfg.weapon_restrictions
        assert "1H blunt" not in cfg.weapon_restrictions

    def test_element_types(self):
        assert ElementType.EARTH.value == "earth"
        assert ElementType.AIR.value == "air"
        assert ElementType.FIRE.value == "fire"
        assert ElementType.WATER.value == "water"

    def test_fire_procs_exist(self):
        assert len(FIRE_PROCS) >= 3
        assert all(p.element == ElementType.FIRE for p in FIRE_PROCS)

    def test_earth_procs_exist(self):
        assert len(EARTH_PROCS) >= 3
        assert all(p.element == ElementType.EARTH for p in EARTH_PROCS)

    def test_air_procs_exist(self):
        assert len(AIR_PROCS) >= 3
        assert all(p.element == ElementType.AIR for p in AIR_PROCS)

    def test_water_procs_exist(self):
        assert len(WATER_PROCS) >= 3
        assert all(p.element == ElementType.WATER for p in WATER_PROCS)

    def test_procs_have_level_requirements(self):
        for procs in [FIRE_PROCS, EARTH_PROCS, AIR_PROCS, WATER_PROCS]:
            for p in procs:
                assert p.level_requirement > 0
                assert p.proc_chance > 0

    def test_sorceror_abilities_exist(self):
        assert len(SORCEROR_ABILITIES) >= 5

    def test_rumblecrush_discipline(self):
        assert DISCIPLINE_RUMBLECRUSH.name == "Discipline of Rumblecrush"
        assert DISCIPLINE_RUMBLECRUSH.duration_seconds == 180
        assert not DISCIPLINE_RUMBLECRUSH.is_raid_drop

    def test_lord_of_maelstrom_is_raid_drop(self):
        assert LORD_OF_THE_MAELSTROM.is_raid_drop is True
        assert LORD_OF_THE_MAELSTROM.level_requirement == 60

    def test_can_summon_pet_same_element(self):
        state = SorcerorState(active_element=ElementType.FIRE)
        pet = PetDefinition(element=ElementType.FIRE, level=10, hp=100, damage=20, name="Fire Pet")
        assert can_summon_pet(state, pet) is True

    def test_cannot_summon_pet_different_element_with_active_pets(self):
        fire_pet = PetDefinition(element=ElementType.FIRE, level=10, hp=100, damage=20, name="Fire Pet")
        state = SorcerorState(active_element=ElementType.FIRE, active_pets=[fire_pet])
        water_pet = PetDefinition(element=ElementType.WATER, level=10, hp=100, damage=20, name="Water Pet")
        assert can_summon_pet(state, water_pet) is False

    def test_can_summon_any_element_with_maelstrom(self):
        state = SorcerorState(active_element=ElementType.FIRE, has_lord_of_maelstrom=True)
        pet = PetDefinition(element=ElementType.WATER, level=10, hp=100, damage=20, name="Water Pet")
        assert can_summon_pet(state, pet) is True

    def test_can_summon_pet_no_active_element(self):
        state = SorcerorState(active_element=None)
        pet = PetDefinition(element=ElementType.EARTH, level=10, hp=100, damage=20, name="Earth Pet")
        assert can_summon_pet(state, pet) is True

    def test_switch_element_dismisses_pets(self):
        state = SorcerorState(
            active_element=ElementType.FIRE,
            active_pets=[PetDefinition(element=ElementType.FIRE, level=10, hp=100, damage=20, name="p")],
        )
        new_state = switch_element(state, ElementType.WATER)
        assert new_state.active_element == ElementType.WATER
        assert len(new_state.active_pets) == 0


# ===================================================================
# Duel Controller Tests
# ===================================================================

class TestDuelController:

    def test_issue_challenge(self):
        dc = DuelController()
        challenge = dc.issue_challenge("player1", "player2", ["sword_01"])
        assert challenge.challenger_id == "player1"
        assert challenge.defender_id == "player2"
        assert challenge.state == DuelState.PENDING

    def test_accept_challenge(self):
        dc = DuelController()
        challenge = dc.issue_challenge("p1", "p2", ["item1"])
        accepted = dc.accept_challenge(challenge)
        assert accepted.state == DuelState.IN_PROGRESS

    def test_decline_challenge(self):
        dc = DuelController()
        challenge = dc.issue_challenge("p1", "p2", [])
        declined = dc.decline_challenge(challenge)
        assert declined.state == DuelState.DECLINED

    def test_resolve_duel(self):
        dc = DuelController()
        challenge = dc.issue_challenge("p1", "p2", ["sword", "shield"])
        dc.accept_challenge(challenge)
        outcome = dc.resolve_duel(challenge, "p1")
        assert outcome.winner_id == "p1"
        assert outcome.loser_id == "p2"
        assert len(outcome.loot_transferred) > 0

    def test_active_duel_count(self):
        dc = DuelController()
        c1 = dc.issue_challenge("a", "b", [])
        dc.accept_challenge(c1)
        assert dc.active_duel_count >= 1

    def test_duel_history(self):
        dc = DuelController()
        c = dc.issue_challenge("a", "b", ["loot"])
        dc.accept_challenge(c)
        dc.resolve_duel(c, "a")
        history = dc.get_duel_history("a")
        assert len(history) >= 1
        assert history[0].winner_id == "a"

    def test_total_duels_completed(self):
        dc = DuelController()
        c = dc.issue_challenge("a", "b", [])
        dc.accept_challenge(c)
        dc.resolve_duel(c, "b")
        assert dc.total_duels_completed >= 1


# ===================================================================
# Tower Zone Tests
# ===================================================================

class TestTowerZone:

    def _make_tower(self) -> TowerZone:
        locs = [
            TowerLocation(zone_name="gfay", x=100, y=200, z=50, wall_direction="north"),
            TowerLocation(zone_name="nro", x=500, y=100, z=30, wall_direction="east"),
            TowerLocation(zone_name="ecommons", x=-200, y=300, z=40, wall_direction="south"),
        ]
        config = TowerConfig(spawn_locations=locs, despawn_interval_minutes=120)
        return TowerZone(config)

    def test_initial_state_spawned(self):
        tower = self._make_tower()
        assert tower.state == TowerState.SPAWNED
        assert tower.is_available is True

    def test_current_location(self):
        tower = self._make_tower()
        loc = tower.current_location
        assert loc is not None
        assert loc.zone_name in ("gfay", "nro", "ecommons")

    def test_despawn(self):
        tower = self._make_tower()
        tower.despawn()
        assert tower.state == TowerState.DESPAWNED
        assert tower.is_available is False

    def test_spawn_at(self):
        tower = self._make_tower()
        tower.despawn()
        new_loc = TowerLocation(zone_name="karana", x=0, y=0, z=0, wall_direction="west")
        tower.spawn_at(new_loc)
        assert tower.state == TowerState.SPAWNED
        assert tower.current_location.zone_name == "karana"

    def test_relocate(self):
        tower = self._make_tower()
        old_zone = tower.current_location.zone_name
        new_loc = tower.relocate()
        # Should have moved to a different location
        assert tower.state == TowerState.SPAWNED
        assert tower.relocate_count >= 1

    def test_can_enter_with_card(self):
        tower = self._make_tower()
        cc = CardCollection(holder_id="p1")
        cc.add_unmaking_card(CardOfUnmaking(card_id="c0", source_entity_level=60))
        assert tower.can_enter(cc, has_levitation=True) is True

    def test_cannot_enter_without_levitation(self):
        tower = self._make_tower()
        cc = CardCollection(holder_id="p1")
        cc.add_unmaking_card(CardOfUnmaking(card_id="c0", source_entity_level=60))
        assert tower.can_enter(cc, has_levitation=False) is False

    def test_can_enter_with_4_same_type(self):
        tower = self._make_tower()
        cc = CardCollection(holder_id="p1")
        for _ in range(4):
            cc.add_universal_card("emperor_crush")
        assert tower.can_enter(cc, has_levitation=True) is True

    def test_cannot_enter_empty_collection(self):
        tower = self._make_tower()
        cc = CardCollection(holder_id="p1")
        assert tower.can_enter(cc, has_levitation=True) is False

    def test_spawn_count(self):
        tower = self._make_tower()
        assert tower.spawn_count >= 1
        tower.relocate()
        assert tower.spawn_count >= 2

    def test_eligible_spawn_locations(self):
        tower = self._make_tower()
        eligible = tower.get_eligible_spawn_locations()
        current = tower.current_location
        assert all(loc.zone_name != current.zone_name for loc in eligible)


# ===================================================================
# Remake System Tests
# ===================================================================

class TestRemakeSystem:

    def test_remake_bonus_percent(self):
        assert REMAKE_BONUS_PERCENT == 1.0

    def test_cannot_remake_low_level(self):
        rs = RemakeSystem()
        assert rs.can_remake("p1", level=30, aa_maxed=True, skills_maxed=True) is False

    def test_cannot_remake_without_max_aa(self):
        rs = RemakeSystem()
        assert rs.can_remake("p1", level=65, aa_maxed=False, skills_maxed=True) is False

    def test_can_remake_all_maxed(self):
        rs = RemakeSystem()
        assert rs.can_remake("p1", level=65, aa_maxed=True, skills_maxed=True) is True

    def test_perform_remake(self):
        rs = RemakeSystem()
        record = rs.perform_remake("p1", "warrior", "wizard")
        assert record.remake_count == 1
        assert record.total_bonus_percent == 1.0
        assert record.previous_class == "warrior"
        assert record.new_class == "wizard"

    def test_cumulative_bonus(self):
        rs = RemakeSystem()
        rs.perform_remake("p1", "warrior", "wizard")
        rs.perform_remake("p1", "wizard", "monk")
        assert rs.get_total_bonus("p1") == 2.0
        assert rs.get_remake_count("p1") == 2

    def test_remake_history(self):
        rs = RemakeSystem()
        rs.perform_remake("p1", "warrior", "wizard")
        rs.perform_remake("p1", "wizard", "monk")
        history = rs.get_remake_history("p1")
        assert len(history) == 2
        assert history[0].new_class == "wizard"

    def test_total_remakes_server_wide(self):
        rs = RemakeSystem()
        rs.perform_remake("p1", "warrior", "wizard")
        rs.perform_remake("p2", "monk", "rogue")
        assert rs.total_remakes_server_wide == 2


# ===================================================================
# Server Reboot / Decay Vote Tests
# ===================================================================

class TestServerReboot:

    def test_vote_trigger_at_50_percent(self):
        vm = DecayVoteManager(decay_threshold=50.0)
        assert vm.should_trigger_vote(49.9) is False
        assert vm.should_trigger_vote(50.0) is True

    def test_cast_and_tally_votes(self):
        vm = DecayVoteManager()
        vm.cast_vote(Vote(voter_id="p1", choice=VoteChoice.RESTART, is_ai_agent=False, faction_id="orcs"))
        vm.cast_vote(Vote(voter_id="p2", choice=VoteChoice.CONTINUE, is_ai_agent=False, faction_id="elves"))
        vm.cast_vote(Vote(voter_id="ai1", choice=VoteChoice.RESTART, is_ai_agent=True, faction_id="orcs"))
        result = vm.tally_votes()
        assert result.total_votes == 3
        assert result.restart_votes == 2
        assert result.continue_votes == 1
        assert result.restart_won is True

    def test_continue_wins(self):
        vm = DecayVoteManager()
        vm.cast_vote(Vote(voter_id="p1", choice=VoteChoice.CONTINUE, is_ai_agent=False, faction_id=""))
        vm.cast_vote(Vote(voter_id="p2", choice=VoteChoice.CONTINUE, is_ai_agent=False, faction_id=""))
        vm.cast_vote(Vote(voter_id="p3", choice=VoteChoice.RESTART, is_ai_agent=False, faction_id=""))
        result = vm.tally_votes()
        assert result.restart_won is False

    def test_reset_votes(self):
        vm = DecayVoteManager()
        vm.cast_vote(Vote(voter_id="p1", choice=VoteChoice.RESTART, is_ai_agent=False, faction_id=""))
        vm.reset_votes()
        assert vm.vote_count == 0

    def test_4_cards_triggers_reboot(self):
        vm = DecayVoteManager()
        rc = ServerRebootController(vm)
        assert rc.check_reboot_condition(4) is True
        assert rc.check_reboot_condition(3) is False

    def test_initiate_reboot(self):
        vm = DecayVoteManager()
        rc = ServerRebootController(vm)
        summary = rc.initiate_reboot("4 Cards of Unmaking collected")
        assert "reason" in summary
        assert summary["enchanted_items_preserved"] is True

    def test_surviving_items(self):
        vm = DecayVoteManager()
        rc = ServerRebootController(vm)
        enchanted = {"epic_sword", "magic_shield"}
        survivors = rc.get_surviving_items(enchanted)
        assert survivors == enchanted

    def test_vote_count(self):
        vm = DecayVoteManager()
        vm.cast_vote(Vote(voter_id="p1", choice=VoteChoice.RESTART, is_ai_agent=False, faction_id=""))
        assert vm.vote_count == 1
