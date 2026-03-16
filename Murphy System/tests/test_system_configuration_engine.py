"""Tests for system_configuration_engine.py"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from system_configuration_engine import (
    SystemConfigurationEngine, SystemType, STRATEGY_TEMPLATES, ControlStrategy, SystemConfiguration,
)


@pytest.fixture
def engine():
    return SystemConfigurationEngine()

class TestSystemTypeDetection:
    def test_ahu(self, engine): assert engine.detect_system_type("air handling unit") == SystemType.AHU
    def test_rtu(self, engine): assert engine.detect_system_type("rooftop unit for office") == SystemType.RTU
    def test_chiller(self, engine): assert engine.detect_system_type("centrifugal chiller plant") == SystemType.CHILLER_PLANT
    def test_boiler(self, engine): assert engine.detect_system_type("boiler plant hot water") == SystemType.BOILER_PLANT
    def test_vav(self, engine): assert engine.detect_system_type("vav box with reheat") == SystemType.VAV_BOX
    def test_plc(self, engine): assert engine.detect_system_type("PLC system automation") == SystemType.PLC_SYSTEM
    def test_scada(self, engine): assert engine.detect_system_type("SCADA system") == SystemType.SCADA_SYSTEM
    def test_generic_fallback(self, engine): assert engine.detect_system_type("mystery equipment xyz") == SystemType.GENERIC

class TestStrategyTemplates:
    def test_ahu_has_cav_and_vav(self):
        ids = {s.strategy_id for s in STRATEGY_TEMPLATES[SystemType.AHU]}
        assert "ahu_cav" in ids and "ahu_vav" in ids
    def test_all_system_types_have_strategies(self):
        for st in SystemType:
            assert st in STRATEGY_TEMPLATES and len(STRATEGY_TEMPLATES[st]) > 0
    def test_strategies_have_pros_cons(self):
        for st, strategies in STRATEGY_TEMPLATES.items():
            for s in strategies:
                assert isinstance(s.pros, list) and isinstance(s.cons, list)

class TestRecommendStrategy:
    def test_ahu_energy_priority(self, engine):
        s = engine.recommend_strategy(SystemType.AHU, {"energy_priority": True})
        assert s.energy_efficiency_rating == "high-performance"
    def test_fallback_for_generic(self, engine):
        s = engine.recommend_strategy(SystemType.GENERIC)
        assert s is not None

class TestConfigure:
    def test_returns_config(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav")
        assert isinstance(config, SystemConfiguration)
    def test_setpoints_populated(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav")
        assert len(config.setpoints) > 0
    def test_override_setpoints(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav",
                                   user_inputs={"setpoints":{"supply_air_temp_sp": 58.0}})
        assert config.setpoints.get("supply_air_temp_sp") == 58.0
    def test_to_dict(self, engine):
        config = engine.configure(SystemType.CHILLER_PLANT, "chiller_reset")
        d = config.to_dict()
        assert "config_id" in d and "strategy" in d

class TestMSSModes:
    def test_magnify_has_full_sequence(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav")
        result = engine.magnify(config)
        assert "full_sequence" in result and len(result["full_sequence"]) > 0
    def test_simplify_has_critical(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav")
        result = engine.simplify(config)
        assert "critical_setpoints" in result or "safety_alarms" in result
    def test_solidify_locked(self, engine):
        config = engine.configure(SystemType.AHU, "ahu_vav")
        result = engine.solidify(config)
        assert result["change_control"] == "require_approval"

class TestStrategyToDict:
    def test_serializable(self, engine):
        s = engine.recommend_strategy(SystemType.AHU)
        d = s.to_dict()
        assert "strategy_id" in d and "pros" in d and "cons" in d
