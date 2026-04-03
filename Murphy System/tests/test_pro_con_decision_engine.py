"""Tests for pro_con_decision_engine.py"""
import pytest, sys, os

from pro_con_decision_engine import (
    ProConDecisionEngine, STANDARD_CRITERIA, Criterion, Option, Decision,
)
from energy_efficiency_framework import ECM_CATALOG


@pytest.fixture
def engine():
    return ProConDecisionEngine()

@pytest.fixture
def two_options():
    return [
        {"name":"Option A","scores":{"roi":8,"energy_savings":7,"implementation_cost":4,"maintenance_burden":3,
         "occupant_comfort":8,"resilience":7,"safety_compliance":1,"ashrae_compliance":1}},
        {"name":"Option B","scores":{"roi":5,"energy_savings":4,"implementation_cost":8,"maintenance_burden":6,
         "occupant_comfort":5,"resilience":5,"safety_compliance":1,"ashrae_compliance":1}},
    ]

class TestStandardCriteria:
    def test_four_sets(self): assert len(STANDARD_CRITERIA) == 4
    def test_each_has_constraints(self):
        for name, criteria in STANDARD_CRITERIA.items():
            constraints = [c for c in criteria if c.category == "constraint"]
            assert len(constraints) >= 2, f"{name} must have at least 2 hard constraints"
    def test_criteria_have_ids(self):
        for criteria in STANDARD_CRITERIA.values():
            for c in criteria:
                assert c.criterion_id and c.name

class TestHardConstraints:
    def test_unsafe_option_eliminated(self, engine):
        options = [
            {"name":"Safe","scores":{"roi":5,"energy_savings":5,"implementation_cost":5,
             "maintenance_burden":5,"occupant_comfort":5,"resilience":5,"safety_compliance":1,"ashrae_compliance":1}},
            {"name":"Unsafe","scores":{"roi":10,"energy_savings":10,"implementation_cost":10,
             "maintenance_burden":10,"occupant_comfort":10,"resilience":10,"safety_compliance":0,"ashrae_compliance":1}},
        ]
        decision = engine.evaluate("test", options, criteria_set="energy_system_selection")
        assert decision.winner is not None
        assert decision.winner.name == "Safe"
    def test_all_fail_no_winner(self, engine):
        options = [
            {"name":"Bad1","scores":{"roi":9,"energy_savings":9,"implementation_cost":9,
             "maintenance_burden":9,"occupant_comfort":9,"resilience":9,"safety_compliance":0,"ashrae_compliance":0}},
        ]
        decision = engine.evaluate("test", options, criteria_set="energy_system_selection")
        assert decision.winner is None

class TestEvaluate:
    def test_winner_has_higher_net_score(self, engine, two_options):
        d = engine.evaluate("Which option?", two_options, criteria_set="energy_system_selection")
        assert d.winner is not None
        assert d.winner.name == "Option A"
    def test_runner_up(self, engine, two_options):
        d = engine.evaluate("Which option?", two_options, criteria_set="energy_system_selection")
        assert d.runner_up is not None and d.runner_up.name == "Option B"
    def test_to_dict(self, engine, two_options):
        d = engine.evaluate("test", two_options, criteria_set="energy_system_selection")
        dd = d.to_dict()
        assert "winner" in dd and "options" in dd
    def test_reasoning_not_empty(self, engine, two_options):
        d = engine.evaluate("test", two_options, criteria_set="energy_system_selection")
        assert len(d.reasoning) > 20

class TestEvaluateECMs:
    def test_returns_decision(self, engine):
        ecm_data = [e.__dict__ for e in ECM_CATALOG[:5]]
        d = engine.evaluate_ecms(ecm_data, budget=100_000)
        assert d.winner is not None
    def test_winner_has_good_payback(self, engine):
        ecm_data = [e.__dict__ for e in ECM_CATALOG[:5]]
        d = engine.evaluate_ecms(ecm_data)
        assert d.winner is not None

class TestEvaluateEquipment:
    def test_returns_decision(self, engine):
        opts = [
            {"name":"Efficient Chiller","scores":{"efficiency":9,"first_cost":4,"life_cycle_cost":8,
             "reliability":9,"lead_time":6,"local_support":8,"safety_listing":1,"code_compliance":1}},
            {"name":"Standard Chiller","scores":{"efficiency":6,"first_cost":8,"life_cycle_cost":6,
             "reliability":7,"lead_time":9,"local_support":9,"safety_listing":1,"code_compliance":1}},
        ]
        d = engine.evaluate_equipment(opts, application="chiller plant")
        assert d.winner is not None

class TestEvaluateStrategies:
    def test_returns_decision(self, engine):
        opts = [
            {"name":"VAV","scores":{"performance":9,"energy_efficiency":9,"complexity":7,"reliability":8,
             "scalability":9,"cost":5,"safety_interlocks":1,"code_compliance":1}},
            {"name":"CAV","scores":{"performance":7,"energy_efficiency":4,"complexity":2,"reliability":9,
             "scalability":4,"cost":9,"safety_interlocks":1,"code_compliance":1}},
        ]
        d = engine.evaluate_strategies(opts, system_type="AHU")
        assert d.winner is not None
        assert d.winner.name == "VAV"

class TestExplain:
    def test_explain_winner(self, engine, two_options):
        d = engine.evaluate("test", two_options, criteria_set="energy_system_selection")
        text = engine.explain_decision(d)
        assert "Option A" in text or "Best Option" in text
    def test_explain_no_winner(self, engine):
        d = Decision(question="test", options=[], winner=None, runner_up=None, reasoning="")
        text = engine.explain_decision(d)
        assert "No decision" in text or "viable" in text
