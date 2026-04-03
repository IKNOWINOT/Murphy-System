"""
Tests for src/large_control_model.py — Large Control Model

Verifies:
- LCM instantiates with correct pilot account
- process() returns expected structure
- Pipeline stages appear in trace
- get_pilot_status() reflects wiring state
- HITL path triggers when criteria unmet

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
import os
import sys
import pytest

from large_control_model import LargeControlModel, STAGE_HITL, STAGE_DISPATCH


class TestLCMInstantiation:
    def test_default_pilot_account(self):
        lcm = LargeControlModel()
        assert lcm.pilot_account == "cpost@murphy.systems"

    def test_custom_pilot_account(self):
        lcm = LargeControlModel(pilot_account="test@example.com")
        assert lcm.pilot_account == "test@example.com"

    def test_default_confidence_threshold(self):
        lcm = LargeControlModel()
        assert 0 < lcm.confidence_threshold <= 1.0

    def test_custom_confidence_threshold(self):
        lcm = LargeControlModel(confidence_threshold=0.5)
        assert lcm.confidence_threshold == 0.5

    def test_stability_threshold_set(self):
        lcm = LargeControlModel()
        assert 0 < lcm.stability_threshold <= 1.0


class TestLCMProcess:
    def setup_method(self):
        # Use very low thresholds so the test always dispatches
        self.lcm = LargeControlModel(
            confidence_threshold=0.0,
            stability_threshold=0.0,
        )

    def test_returns_dict(self):
        result = self.lcm.process("Run a compliance check")
        assert isinstance(result, dict)

    def test_result_has_required_keys(self):
        result = self.lcm.process("Onboard a new client")
        for key in ("run_id", "stage", "executed", "result", "hitl_required",
                    "clarifying_questions", "pipeline_trace"):
            assert key in result, f"Missing key: {key}"

    def test_run_id_is_string(self):
        result = self.lcm.process("Generate Q3 report")
        assert isinstance(result["run_id"], str)
        assert len(result["run_id"]) > 0

    def test_pipeline_trace_is_list(self):
        result = self.lcm.process("Schedule a meeting")
        assert isinstance(result["pipeline_trace"], list)

    def test_pipeline_trace_has_nl_stage(self):
        result = self.lcm.process("Test NL parse")
        stages = [s["stage"] for s in result["pipeline_trace"]]
        assert "nl_parse" in stages

    def test_dispatched_at_low_threshold(self):
        result = self.lcm.process("Execute automation")
        assert result["stage"] == STAGE_DISPATCH
        assert result["executed"] is True
        assert result["hitl_required"] is False

    def test_clarifying_questions_empty_when_executed(self):
        result = self.lcm.process("Run workflow")
        assert result["clarifying_questions"] == []

    def test_empty_query_still_returns(self):
        result = self.lcm.process("")
        assert isinstance(result, dict)
        assert "run_id" in result


class TestLCMHITLPath:
    def test_hitl_at_impossible_threshold(self):
        lcm = LargeControlModel(
            confidence_threshold=2.0,  # impossible to meet
            stability_threshold=2.0,
        )
        result = lcm.process("Some task")
        assert result["hitl_required"] is True
        assert result["stage"] == STAGE_HITL
        assert result["executed"] is False
        assert len(result["clarifying_questions"]) > 0


class TestLCMPilotStatus:
    def test_returns_dict(self):
        lcm = LargeControlModel()
        status = lcm.get_pilot_status()
        assert isinstance(status, dict)

    def test_pilot_account_in_status(self):
        lcm = LargeControlModel()
        status = lcm.get_pilot_status()
        assert status["pilot_account"] == "cpost@murphy.systems"

    def test_subsystems_key_present(self):
        lcm = LargeControlModel()
        status = lcm.get_pilot_status()
        assert "subsystems" in status
        assert isinstance(status["subsystems"], dict)

    def test_threshold_values_in_status(self):
        lcm = LargeControlModel()
        status = lcm.get_pilot_status()
        assert "confidence_threshold" in status
        assert "stability_threshold" in status
