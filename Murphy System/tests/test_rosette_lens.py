"""
Tests for src/rosette_lens.py — Rosette Lens

Verifies:
- RosetteLens instantiates with default guise
- select_lens returns required keys
- guise switching works
- Context intent drives guise selection
- Agent role majority vote works

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
import os
import sys
import pytest

from rosette_lens import RosetteLens


class TestRosetteLensInstantiation:
    def test_default_guise(self):
        lens = RosetteLens()
        assert lens.get_active_guise() == "default"

    def test_custom_initial_guise(self):
        lens = RosetteLens(initial_guise="sales_focus")
        assert lens.get_active_guise() == "sales_focus"

    def test_unknown_guise_defaults(self):
        lens = RosetteLens(initial_guise="nonexistent_guise_xyz")
        assert lens.get_active_guise() == "default"


class TestSelectLens:
    def setup_method(self):
        self.lens = RosetteLens()

    def test_returns_dict(self):
        result = self.lens.select_lens([], {})
        assert isinstance(result, dict)

    def test_required_keys_present(self):
        result = self.lens.select_lens([], {"intent": "test"})
        for key in ("resolution_level", "data_sources", "magnify_dims",
                    "simplify_dims", "guise", "agent_count", "context_intent"):
            assert key in result, f"Missing key: {key}"

    def test_agent_count_reflects_input(self):
        states = [{"role": "sales"}, {"role": "finance"}]
        result = self.lens.select_lens(states, {})
        assert result["agent_count"] == 2

    def test_empty_states_returns_default(self):
        result = self.lens.select_lens([], {})
        assert result["resolution_level"] in ("RM0", "RM1", "RM2", "RM3", "RM4", "RM5")

    def test_context_intent_echoed(self):
        result = self.lens.select_lens([], {"intent": "test_query"})
        assert result["context_intent"] == "test_query"

    def test_data_sources_is_list(self):
        result = self.lens.select_lens([], {})
        assert isinstance(result["data_sources"], list)

    def test_magnify_dims_is_list(self):
        result = self.lens.select_lens([], {})
        assert isinstance(result["magnify_dims"], list)


class TestGuiseSwitching:
    def test_set_valid_guise(self):
        lens = RosetteLens()
        lens.set_guise("sales_focus")
        assert lens.get_active_guise() == "sales_focus"

    def test_set_invalid_guise_defaults(self):
        lens = RosetteLens()
        lens.set_guise("bogus_guise")
        assert lens.get_active_guise() == "default"

    def test_list_guises(self):
        lens = RosetteLens()
        guises = lens.list_guises()
        assert isinstance(guises, list)
        assert "default" in guises
        assert "sales_focus" in guises
        assert "compliance_focus" in guises
        assert "finance_focus" in guises

    def test_get_guise_definition(self):
        lens = RosetteLens()
        defn = lens.get_guise_definition("sales_focus")
        assert isinstance(defn, dict)
        assert "resolution_level" in defn

    def test_get_nonexistent_guise_empty(self):
        lens = RosetteLens()
        defn = lens.get_guise_definition("nonexistent")
        assert defn == {}


class TestContextDrivenGuise:
    def setup_method(self):
        self.lens = RosetteLens()

    def test_sales_intent_selects_sales_focus(self):
        result = self.lens.select_lens([], {"intent": "review sales pipeline"})
        assert result["guise"] == "sales_focus"

    def test_compliance_intent_selects_compliance_focus(self):
        result = self.lens.select_lens([], {"intent": "run compliance audit"})
        assert result["guise"] == "compliance_focus"

    def test_grant_intent_selects_finance_focus(self):
        result = self.lens.select_lens([], {"intent": "find grant funding"})
        assert result["guise"] == "finance_focus"

    def test_research_intent_selects_research_focus(self):
        result = self.lens.select_lens([], {"intent": "research market analysis"})
        assert result["guise"] == "research_focus"

    def test_agent_role_sales_drives_sales_focus(self):
        states = [{"role": "sales_manager"}, {"role": "vp_sales"}]
        result = self.lens.select_lens(states, {})
        assert result["guise"] == "sales_focus"

    def test_agent_role_compliance_drives_compliance_focus(self):
        states = [{"role": "compliance_officer"}, {"role": "legal_review"}]
        result = self.lens.select_lens(states, {})
        assert result["guise"] == "compliance_focus"

    def test_finance_focus_has_higher_resolution(self):
        finance_result = self.lens.select_lens([], {"intent": "grant funding"})
        default_result = self.lens.select_lens([], {})
        # Finance focus should be at RM3 or higher; default at RM2
        finance_rm = int(finance_result["resolution_level"].replace("RM", ""))
        default_rm = int(default_result["resolution_level"].replace("RM", ""))
        assert finance_rm >= default_rm
