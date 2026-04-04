"""
Tests for the 8 new EQ system modules.

Validates:
  - EQEmu Game Connector (eq_game_connector.py)
  - Lore Seeder (lore_seeder.py)
  - Faction Manager (faction_manager.py)
  - EQ Gateway (eq_gateway.py)
  - Macro-Trigger Engine (macro_trigger_engine.py)
  - Experience Lore Engine (experience_lore.py)
  - Perception Pipeline (perception_pipeline.py)
  - Agent Voice Manager (agent_voice.py)
"""

import pytest

from src.eq.eq_game_connector import (
    EQEmuDatabaseConfig,
    EQEmuGameConnector,
    FactionData,
    NPCData,
    ServerConfig,
    ServerEra,
    ServerEvent,
    ServerEventType,
    SpawnGroupData,
    ZoneData,
)
from src.eq.lore_seeder import (
    LoreSeeder,
    NPCRole,
    _classify_combat_archetype,
    _classify_damage_type,
    _classify_entity_category,
    _classify_npc_role,
)
from src.eq.faction_manager import (
    FACTION_KOS_THRESHOLD,
    FACTION_MAX,
    FACTION_MIN,
    FactionCon,
    FactionManager,
    FactionRecord,
    standing_to_con,
)
from src.eq.eq_gateway import (
    EQGateway,
    GatewayDirection,
    VALID_LANGUAGES,
)
from src.eq.macro_trigger_engine import (
    CombatState,
    MacroTriggerEngine,
    TriggerCondition,
    TriggerDefinition,
    TriggerType,
    get_play_style_template,
    PLAY_STYLE_TEMPLATES,
)
from src.eq.experience_lore import (
    ExperienceLoreEngine,
    FIDELITY_DECAY_PER_RETELLING,
    FIDELITY_MAX,
    FIDELITY_MIN,
    FIRST_HAND_FIDELITY,
)
from src.eq.perception_pipeline import (
    GameStateSnapshot,
    PerceptionPipeline,
    PipelineStage,
)
from src.eq.agent_voice import (
    AgentVoiceManager,
    DEFAULT_VOICE_ROSTER,
    VoiceGender,
    VoiceProfile,
    VoiceTone,
)
from src.eq.soul_engine import SoulEngine
from src.eq.spawner_registry import SpawnerRegistry


# ===================================================================
# EQEmu Game Connector Tests
# ===================================================================

class TestEQEmuGameConnector:

    def _make_connector(self) -> EQEmuGameConnector:
        c = EQEmuGameConnector()
        c.connect()
        return c

    def _sample_npc(self, npc_id: int = 1, name: str = "Emperor Crush",
                     level: int = 55, is_named: bool = True) -> NPCData:
        return NPCData(npc_id=npc_id, name=name, level=level, is_named=is_named)

    def test_connect_disconnect(self):
        c = EQEmuGameConnector()
        assert not c.is_connected
        assert c.connect() is True
        assert c.is_connected
        c.disconnect()
        assert not c.is_connected

    def test_default_server_config(self):
        c = EQEmuGameConnector()
        assert c.config.era == ServerEra.PLANES_OF_POWER
        assert c.config.max_level == 65
        assert c.config.xp_modifier == 1.0

    def test_database_config_connection_string(self):
        cfg = EQEmuDatabaseConfig(host="db.local", port=3306, username="eq", password="pw", database="peq")
        assert "db.local" in cfg.connection_string
        assert "peq" in cfg.connection_string

    def test_load_and_get_npc(self):
        c = self._make_connector()
        npc = self._sample_npc()
        c.load_npc(npc)
        assert c.get_npc(1) is npc
        assert c.npc_count == 1

    def test_get_npc_by_name(self):
        c = self._make_connector()
        c.load_npc(self._sample_npc())
        found = c.get_npc_by_name("Emperor Crush")
        assert found is not None
        assert found.name == "Emperor Crush"

    def test_get_npc_by_name_case_insensitive(self):
        c = self._make_connector()
        c.load_npc(self._sample_npc())
        assert c.get_npc_by_name("emperor crush") is not None

    def test_get_named_npcs(self):
        c = self._make_connector()
        c.load_npc(self._sample_npc(1, "Emperor Crush", 55, True))
        c.load_npc(self._sample_npc(2, "a_fire_beetle", 1, False))
        named = c.get_named_npcs()
        assert len(named) == 1
        assert named[0].name == "Emperor Crush"

    def test_load_and_get_zone(self):
        c = self._make_connector()
        z = ZoneData(zone_id=1, short_name="crushbone", long_name="Crushbone")
        c.load_zone(z)
        assert c.get_zone("crushbone") is z
        assert c.zone_count == 1

    def test_load_and_get_faction(self):
        c = self._make_connector()
        f = FactionData(faction_id=100, name="Crushbone Orcs")
        c.load_faction(f)
        assert c.get_faction(100) is f
        assert c.faction_count == 1

    def test_get_faction_allies_and_enemies(self):
        c = self._make_connector()
        c.load_faction(FactionData(faction_id=1, name="Orcs", allies=[2], enemies=[3]))
        c.load_faction(FactionData(faction_id=2, name="Trolls"))
        c.load_faction(FactionData(faction_id=3, name="Elves"))
        allies = c.get_faction_allies(1)
        enemies = c.get_faction_enemies(1)
        assert len(allies) == 1 and allies[0].name == "Trolls"
        assert len(enemies) == 1 and enemies[0].name == "Elves"

    def test_get_npcs_by_level_range(self):
        c = self._make_connector()
        c.load_npcs([
            self._sample_npc(1, "Low", 5),
            self._sample_npc(2, "Mid", 30),
            self._sample_npc(3, "High", 60),
        ])
        mids = c.get_npcs_by_level_range(20, 40)
        assert len(mids) == 1 and mids[0].name == "Mid"

    def test_get_npcs_by_faction(self):
        c = self._make_connector()
        npc = NPCData(npc_id=1, name="Orc Pawn", level=5, primary_faction=100)
        c.load_npc(npc)
        result = c.get_npcs_by_faction(100)
        assert len(result) == 1

    def test_spawn_group_and_npcs_by_zone(self):
        c = self._make_connector()
        c.load_npc(self._sample_npc(10, "Guard", 30))
        c.load_spawn_group(SpawnGroupData(
            spawngroup_id=1, name="cb_guards", zone_short_name="crushbone", npc_ids=[10],
        ))
        npcs = c.get_npcs_by_zone("crushbone")
        assert len(npcs) == 1 and npcs[0].name == "Guard"

    def test_event_emit_and_retrieve(self):
        c = self._make_connector()
        c.emit_event(ServerEvent(event_type=ServerEventType.CARD_DROPPED, zone="crushbone"))
        c.emit_event(ServerEvent(event_type=ServerEventType.ZONE_CHANGE, zone="gfay"))
        all_events = c.get_events()
        assert len(all_events) == 2
        card_events = c.get_events(ServerEventType.CARD_DROPPED)
        assert len(card_events) == 1

    def test_event_clear(self):
        c = self._make_connector()
        c.emit_event(ServerEvent(event_type=ServerEventType.TOWER_SPAWNED))
        c.clear_events()
        assert len(c.get_events()) == 0

    def test_npc_auto_named_detection(self):
        npc = NPCData(npc_id=1, name="Fippy Darkpaw", level=5)
        assert npc.is_named is True
        generic = NPCData(npc_id=2, name="a_fire_beetle#01", level=1)
        assert generic.is_named is False


# ===================================================================
# Lore Seeder Tests
# ===================================================================

class TestLoreSeeder:

    def _make_seeder(self):
        connector = EQEmuGameConnector()
        connector.connect()
        soul_engine = SoulEngine()
        spawner_reg = SpawnerRegistry()
        return LoreSeeder(connector, soul_engine, spawner_reg), connector

    def _load_sample_data(self, connector):
        connector.load_npc(NPCData(npc_id=1, name="Emperor Crush", level=55, class_id=1, is_named=True, primary_faction=100))
        connector.load_npc(NPCData(npc_id=2, name="a_fire_beetle", level=1, class_id=1, is_named=False))
        connector.load_npc(NPCData(npc_id=3, name="Nagafen", level=65, class_id=1, is_named=True, primary_faction=200))
        connector.load_faction(FactionData(faction_id=100, name="Crushbone Orcs", allies=[200]))
        connector.load_faction(FactionData(faction_id=200, name="Dragons of Norrath"))
        connector.load_zone(ZoneData(zone_id=1, short_name="crushbone", long_name="Crushbone"))

    def test_seed_all_processes_npcs(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        result = seeder.seed_all()
        assert result.npcs_processed == 3
        assert result.identity_templates_created == 3
        assert result.spawner_entries_created == 3

    def test_seed_creates_souls_for_named_only(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        result = seeder.seed_all()
        assert result.souls_created == 2  # Emperor Crush + Nagafen

    def test_seed_maps_factions(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        result = seeder.seed_all()
        assert result.factions_mapped == 2

    def test_seed_zones_counted(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        result = seeder.seed_all()
        assert result.zones_seeded == 1

    def test_identity_templates_generated(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        seeder.seed_all()
        templates = seeder.get_identity_templates()
        assert len(templates) == 3
        assert "1" in templates  # Emperor Crush

    def test_soul_faction_alignment_populated(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        seeder.seed_all()
        soul = seeder.soul_engine.get_soul("1")
        assert soul is not None
        assert soul.faction_alignment["faction_id"] == "Crushbone Orcs"

    def test_classify_npc_role_merchant(self):
        npc = NPCData(npc_id=1, name="Merchant", level=10, merchant_id=5)
        assert _classify_npc_role(npc) == NPCRole.MERCHANT

    def test_classify_npc_role_guard(self):
        npc = NPCData(npc_id=1, name="Guard Elban", level=30)
        assert _classify_npc_role(npc) == NPCRole.GUARD

    def test_classify_npc_role_raid_boss(self):
        npc = NPCData(npc_id=1, name="Nagafen", level=65, is_named=True)
        assert _classify_npc_role(npc) == NPCRole.RAID_BOSS

    def test_classify_entity_category(self):
        assert _classify_entity_category(NPCData(npc_id=1, name="Nagafen", level=65, is_named=True)) == "raid_boss"
        assert _classify_entity_category(NPCData(npc_id=2, name="a_orc_pawn#01", level=5)) == "mob"

    def test_spawner_registry_populated(self):
        seeder, connector = self._make_seeder()
        self._load_sample_data(connector)
        seeder.seed_all()
        assert seeder.spawner_registry.entity_count == 3


# ===================================================================
# Faction Manager Tests
# ===================================================================

class TestFactionManager:

    def _make_manager(self) -> FactionManager:
        fm = FactionManager()
        fm.register_faction(FactionRecord(faction_id="orcs", name="Crushbone Orcs", allies=["trolls"], enemies=["elves"]))
        fm.register_faction(FactionRecord(faction_id="trolls", name="Grobb Trolls"))
        fm.register_faction(FactionRecord(faction_id="elves", name="Kelethin Elves"))
        return fm

    def test_register_and_count(self):
        fm = self._make_manager()
        assert fm.faction_count == 3

    def test_default_standing_indifferent(self):
        fm = self._make_manager()
        assert fm.get_entity_con("player1", "orcs") == FactionCon.INDIFFERENT

    def test_adjust_standing(self):
        fm = self._make_manager()
        new_val = fm.adjust_entity_standing("player1", "orcs", 1000)
        assert new_val == 1000
        assert fm.get_entity_con("player1", "orcs") == FactionCon.ALLY

    def test_standing_clamped_to_max(self):
        fm = self._make_manager()
        fm.adjust_entity_standing("p1", "orcs", 5000)
        es = fm.get_or_create_standings("p1")
        assert es.get_standing("orcs") == FACTION_MAX

    def test_standing_clamped_to_min(self):
        fm = self._make_manager()
        fm.adjust_entity_standing("p1", "orcs", -5000)
        es = fm.get_or_create_standings("p1")
        assert es.get_standing("orcs") == FACTION_MIN

    def test_kill_faction_hit(self):
        fm = self._make_manager()
        new_val = fm.process_kill_faction_hit("p1", "orcs", -50)
        assert new_val == -50

    def test_kill_ripples_to_allies(self):
        fm = self._make_manager()
        fm.process_kill_faction_hit("p1", "orcs", -100)
        es = fm.get_or_create_standings("p1")
        assert es.get_standing("trolls") < 0  # Ally of orcs loses standing too

    def test_kill_ripples_to_enemies(self):
        fm = self._make_manager()
        fm.process_kill_faction_hit("p1", "orcs", -100)
        es = fm.get_or_create_standings("p1")
        assert es.get_standing("elves") > 0  # Enemy of orcs gains standing

    def test_grudge_and_friend(self):
        fm = self._make_manager()
        fm.add_grudge("agent1", "player1")
        assert fm.has_grudge("agent1", "player1")
        fm.add_friend("agent1", "player1")
        assert fm.has_friend("agent1", "player1")
        assert not fm.has_grudge("agent1", "player1")  # Friend replaces grudge

    def test_declare_war(self):
        fm = self._make_manager()
        war = fm.declare_war("orcs", "elves", "territorial dispute")
        assert war is not None
        assert fm.is_at_war("orcs", "elves")
        assert len(fm.get_active_wars()) == 1

    def test_end_war(self):
        fm = self._make_manager()
        fm.declare_war("orcs", "elves")
        assert fm.end_war("orcs", "elves") is True
        assert not fm.is_at_war("orcs", "elves")

    def test_hostile_factions(self):
        fm = self._make_manager()
        fm.declare_war("orcs", "trolls")
        hostile = fm.get_hostile_factions("orcs")
        assert "elves" in hostile  # enemy
        assert "trolls" in hostile  # at war

    def test_standing_to_con_kos(self):
        assert standing_to_con(-1100) == FactionCon.READY_TO_ATTACK

    def test_standing_to_con_ally(self):
        assert standing_to_con(800) == FactionCon.ALLY


# ===================================================================
# EQ Gateway Tests
# ===================================================================

class TestEQGateway:

    def test_valid_language(self):
        gw = EQGateway()
        assert gw.validate_language("common_tongue") is True
        assert gw.validate_language("dragon") is True

    def test_invalid_language(self):
        gw = EQGateway()
        assert gw.validate_language("python") is False
        assert gw.validate_language("javascript") is False

    def test_valid_content(self):
        gw = EQGateway()
        ok, reason = gw.validate_content("Hail, Emperor Crush! The orcs march to war.")
        assert ok is True

    def test_blocked_code_pattern(self):
        gw = EQGateway()
        ok, reason = gw.validate_content("import os; os.system('rm -rf /')")
        assert ok is False
        assert "code_pattern" in reason

    def test_blocked_term(self):
        gw = EQGateway()
        ok, reason = gw.validate_content("Give me the api_key now")
        assert ok is False
        assert "blocked_term" in reason

    def test_pass_inbound_allowed(self):
        gw = EQGateway()
        assert gw.pass_inbound("murphy", "agent_1", "You see an orc.") is True
        assert gw.allowed_count == 1

    def test_pass_inbound_blocked(self):
        gw = EQGateway()
        assert gw.pass_inbound("murphy", "agent_1", "import os") is False
        assert gw.blocked_count == 1

    def test_pass_outbound_always_allowed(self):
        gw = EQGateway()
        assert gw.pass_outbound("agent_1", "murphy", "telemetry data") is True

    def test_scope_recall_query(self):
        gw = EQGateway()
        scoped = gw.scope_recall_query("Who is Emperor Crush?")
        assert "[index:eq]" in scoped

    def test_audit_log(self):
        gw = EQGateway()
        gw.pass_inbound("a", "b", "hello")
        gw.pass_outbound("b", "a", "ok")
        assert len(gw.log) == 2


# ===================================================================
# Macro-Trigger Engine Tests
# ===================================================================

class TestMacroTriggerEngine:

    def test_play_style_templates_exist(self):
        assert "melee" in PLAY_STYLE_TEMPLATES
        assert "caster" in PLAY_STYLE_TEMPLATES
        assert "cleric" in PLAY_STYLE_TEMPLATES
        assert "hybrid" in PLAY_STYLE_TEMPLATES

    def test_get_play_style_template(self):
        triggers = get_play_style_template("melee")
        assert len(triggers) > 0

    def test_unknown_archetype_returns_melee(self):
        triggers = get_play_style_template("unknown")
        assert len(triggers) > 0

    def test_trigger_condition_evaluate_lt(self):
        cond = TriggerCondition("hp_low", "hp_percent", "lt", 20)
        assert cond.evaluate({"hp_percent": 15}) is True
        assert cond.evaluate({"hp_percent": 50}) is False

    def test_trigger_condition_evaluate_eq(self):
        cond = TriggerCondition("in_combat", "combat_state", "eq", "combat")
        assert cond.evaluate({"combat_state": "combat"}) is True
        assert cond.evaluate({"combat_state": "idle"}) is False

    def test_trigger_definition_conditions_met(self):
        td = TriggerDefinition(
            trigger_type=TriggerType.ATTACK,
            conditions=[
                TriggerCondition("has_target", "has_target", "eq", True),
                TriggerCondition("in_combat", "combat_state", "eq", "combat"),
            ],
        )
        assert td.all_conditions_met({"has_target": True, "combat_state": "combat"}) is True
        assert td.all_conditions_met({"has_target": False, "combat_state": "combat"}) is False

    def test_engine_evaluate_fires_highest_priority(self):
        engine = MacroTriggerEngine([
            TriggerDefinition(trigger_type=TriggerType.HEAL, priority=5,
                              conditions=[TriggerCondition("hp_low", "hp_percent", "lt", 50)]),
            TriggerDefinition(trigger_type=TriggerType.ATTACK, priority=20,
                              conditions=[TriggerCondition("has_target", "has_target", "eq", True)]),
        ])
        state = {"hp_percent": 30, "has_target": True}
        result = engine.evaluate(state)
        assert result is not None
        assert result.trigger_type == TriggerType.HEAL

    def test_engine_evaluate_returns_none_no_match(self):
        engine = MacroTriggerEngine([
            TriggerDefinition(trigger_type=TriggerType.ATTACK, priority=10,
                              conditions=[TriggerCondition("in_combat", "combat_state", "eq", "combat")]),
        ])
        result = engine.evaluate({"combat_state": "idle"})
        assert result is None

    def test_engine_evaluate_all(self):
        engine = MacroTriggerEngine([
            TriggerDefinition(trigger_type=TriggerType.HEAL, priority=5,
                              conditions=[TriggerCondition("hp_low", "hp_percent", "lt", 50)]),
            TriggerDefinition(trigger_type=TriggerType.ATTACK, priority=20,
                              conditions=[TriggerCondition("has_target", "has_target", "eq", True)]),
        ])
        results = engine.evaluate_all({"hp_percent": 30, "has_target": True})
        assert len(results) == 2

    def test_melee_template_has_flee(self):
        triggers = get_play_style_template("melee")
        types = [t.trigger_type for t in triggers]
        assert TriggerType.FLEE in types

    def test_cleric_template_has_heal(self):
        triggers = get_play_style_template("cleric")
        types = [t.trigger_type for t in triggers]
        assert TriggerType.HEAL in types

    def test_engine_trigger_count(self):
        engine = MacroTriggerEngine(get_play_style_template("caster"))
        assert engine.trigger_count > 0


# ===================================================================
# Experience Lore Engine Tests
# ===================================================================

class TestExperienceLoreEngine:

    def test_capture_experience(self):
        eng = ExperienceLoreEngine()
        exp = eng.capture_experience("agent1", "combat", zone="crushbone",
                                      involved_entities=["orc_pawn"],
                                      description="Killed an orc pawn")
        assert exp.agent_id == "agent1"
        assert exp.fidelity == FIRST_HAND_FIDELITY
        assert eng.get_agent_experience_count("agent1") == 1

    def test_recall_by_entity(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat", involved_entities=["emperor_crush"])
        eng.capture_experience("a1", "trade", involved_entities=["merchant_npc"])
        recall = eng.recall_by_entity("a1", "emperor_crush")
        assert len(recall.recalled_experiences) == 1
        assert recall.recalled_experiences[0].experience_type == "combat"

    def test_recall_by_zone(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat", zone="crushbone")
        eng.capture_experience("a1", "combat", zone="gfay")
        results = eng.recall_by_zone("a1", "crushbone")
        assert len(results) == 1

    def test_recall_by_type(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat")
        eng.capture_experience("a1", "trade")
        assert len(eng.recall_by_type("a1", "combat")) == 1

    def test_propagate_lore_degrades_fidelity(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat", involved_entities=["emperor_crush"])
        result = eng.propagate_lore("a1", "a2")
        assert result.experiences_shared == 1
        assert result.fidelity_after < FIRST_HAND_FIDELITY
        # Target should have the experience
        assert eng.get_agent_experience_count("a2") == 1

    def test_fidelity_floor(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat")
        # Propagate many times to test floor
        current_source = "a1"
        for i in range(50):
            target = f"agent_{i+10}"
            eng.propagate_lore(current_source, target)
            current_source = target
        # Final agent's experience should be at or above the floor
        exps = eng.get_retold_experiences(current_source)
        assert all(e.fidelity >= FIDELITY_MIN for e in exps)

    def test_first_hand_vs_retold(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat")
        eng.propagate_lore("a1", "a2")
        assert len(eng.get_first_hand_experiences("a1")) == 1
        assert len(eng.get_retold_experiences("a2")) == 1

    def test_total_experience_count(self):
        eng = ExperienceLoreEngine()
        eng.capture_experience("a1", "combat")
        eng.capture_experience("a2", "trade")
        assert eng.total_experience_count == 2


# ===================================================================
# Perception Pipeline Tests
# ===================================================================

class TestPerceptionPipeline:

    def test_run_cycle_with_snapshot(self):
        engine = MacroTriggerEngine([
            TriggerDefinition(trigger_type=TriggerType.ATTACK, priority=10,
                              conditions=[TriggerCondition("has_target", "has_target", "eq", True)]),
        ])
        pipeline = PerceptionPipeline("agent1", engine)
        snapshot = GameStateSnapshot(agent_id="agent1", has_target=True, combat_state="combat")
        decision = pipeline.run_cycle(snapshot)
        assert decision.stage_reached == PipelineStage.WRITE
        assert decision.trigger_result is not None
        assert decision.trigger_result.trigger_type == TriggerType.ATTACK

    def test_run_cycle_no_snapshot_returns_scan(self):
        engine = MacroTriggerEngine()
        pipeline = PerceptionPipeline("agent1", engine)
        decision = pipeline.run_cycle()
        assert decision.stage_reached == PipelineStage.SCAN

    def test_cycle_count_increments(self):
        engine = MacroTriggerEngine()
        pipeline = PerceptionPipeline("agent1", engine)
        snapshot = GameStateSnapshot(agent_id="agent1")
        pipeline.run_cycle(snapshot)
        pipeline.run_cycle(snapshot)
        assert pipeline.cycle_count == 2

    def test_last_decision_stored(self):
        engine = MacroTriggerEngine()
        pipeline = PerceptionPipeline("agent1", engine)
        assert pipeline.last_decision is None
        pipeline.run_cycle(GameStateSnapshot(agent_id="agent1"))
        assert pipeline.last_decision is not None

    def test_snapshot_to_trigger_state(self):
        snap = GameStateSnapshot(
            agent_id="a1", hp_percent=50, mana_percent=80, has_target=True,
            combat_state="combat", has_levitation=True,
        )
        state = snap.to_trigger_state()
        assert state["hp_percent"] == 50
        assert state["has_target"] is True
        assert state["has_levitation"] is True

    def test_mind_writer_callback_invoked(self):
        written = []
        def writer(agent_id, decision):
            written.append((agent_id, decision))

        engine = MacroTriggerEngine()
        pipeline = PerceptionPipeline("a1", engine, mind_writer=writer)
        pipeline.run_cycle(GameStateSnapshot(agent_id="a1"))
        assert len(written) == 1
        assert written[0][0] == "a1"

    def test_levitation_in_snapshot(self):
        snap = GameStateSnapshot(agent_id="a1", has_levitation=True)
        assert snap.has_levitation is True


# ===================================================================
# Agent Voice Manager Tests
# ===================================================================

class TestAgentVoiceManager:

    def test_default_roster_has_8_plus_profiles(self):
        assert len(DEFAULT_VOICE_ROSTER) >= 8

    def test_roster_size(self):
        mgr = AgentVoiceManager()
        assert mgr.roster_size >= 8

    def test_get_profile_by_id(self):
        mgr = AgentVoiceManager()
        profile = mgr.get_profile("orc_warrior")
        assert profile is not None
        assert profile.name == "Gronthar"

    def test_manual_assign(self):
        mgr = AgentVoiceManager()
        assert mgr.assign_voice("agent1", "orc_warrior") is True
        voice = mgr.get_agent_voice("agent1")
        assert voice is not None
        assert voice.profile_id == "orc_warrior"

    def test_assign_invalid_profile_fails(self):
        mgr = AgentVoiceManager()
        assert mgr.assign_voice("agent1", "nonexistent") is False

    def test_auto_assign_race_and_class_match(self):
        mgr = AgentVoiceManager()
        profile = mgr.auto_assign_voice("agent1", "orc", "warrior")
        assert profile is not None
        assert "orc" in profile.suitable_races

    def test_auto_assign_race_only_match(self):
        mgr = AgentVoiceManager()
        profile = mgr.auto_assign_voice("agent1", "dwarf", "wizard")
        assert profile is not None
        assert "dwarf" in profile.suitable_races

    def test_auto_assign_class_only_match(self):
        mgr = AgentVoiceManager()
        profile = mgr.auto_assign_voice("agent1", "vah_shir", "monk")
        assert profile is not None

    def test_auto_assign_fallback(self):
        mgr = AgentVoiceManager()
        profile = mgr.auto_assign_voice("agent1", "alien_race", "alien_class")
        assert profile is not None  # Falls back to first profile

    def test_assignment_count(self):
        mgr = AgentVoiceManager()
        mgr.auto_assign_voice("a1", "orc", "warrior")
        mgr.auto_assign_voice("a2", "elf", "wizard")
        assert mgr.assignment_count == 2

    def test_all_profiles_have_required_fields(self):
        for p in DEFAULT_VOICE_ROSTER:
            assert p.profile_id
            assert p.name
            assert isinstance(p.gender, VoiceGender)
            assert isinstance(p.tone, VoiceTone)
            assert len(p.suitable_races) > 0
            assert len(p.suitable_classes) > 0
