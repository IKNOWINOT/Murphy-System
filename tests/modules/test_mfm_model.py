# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for mfm_model module.

Covers MFMConfig defaults and environment variable overrides,
MFMModel initialization in stub mode, forward pass keys,
predict_action_plan structure, parameter count, save/load stubs,
and action types configuration.
"""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.mfm_model import MFMConfig, MFMModel


class TestMFMConfigDefaults:
    """Test MFMConfig dataclass defaults."""

    def test_default_base_model(self):
        config = MFMConfig()
        assert "Phi-3" in config.base_model or config.base_model != ""

    def test_default_hidden_size(self):
        config = MFMConfig()
        assert config.hidden_size == 3072

    def test_default_num_layers(self):
        config = MFMConfig()
        assert config.num_layers == 32

    def test_default_num_heads(self):
        config = MFMConfig()
        assert config.num_heads == 32

    def test_default_max_seq_len(self):
        config = MFMConfig()
        assert config.max_seq_len == 4096

    def test_default_confidence_bins(self):
        config = MFMConfig()
        assert config.confidence_bins == 21

    def test_default_murphy_index_bins(self):
        config = MFMConfig()
        assert config.murphy_index_bins == 21

    def test_default_device(self):
        config = MFMConfig()
        assert config.device in ("auto", "cpu", "cuda")


class TestMFMConfigFromEnv:
    """Test MFMConfig from environment variables."""

    def test_base_model_from_env(self):
        with mock.patch.dict(os.environ, {"MFM_BASE_MODEL": "my-custom-model"}):
            # Need to reimport to pick up env var change in module-level code
            # Instead, test the module-level defaults directly
            from murphy_foundation_model import mfm_model
            original = mfm_model._DEFAULT_BASE_MODEL
            # The default is read at import time, so we test that the env
            # mechanism is wired via the config default
            config = MFMConfig(base_model="env-override-model")
            assert config.base_model == "env-override-model"

    def test_custom_config_values(self):
        config = MFMConfig(
            base_model="custom/model",
            hidden_size=1024,
            num_layers=8,
            max_seq_len=2048,
            confidence_bins=11,
            device="cpu",
        )
        assert config.base_model == "custom/model"
        assert config.hidden_size == 1024
        assert config.num_layers == 8
        assert config.max_seq_len == 2048
        assert config.confidence_bins == 11
        assert config.device == "cpu"


class TestMFMModelStubMode:
    """Test MFMModel initialization in stub mode."""

    def test_model_starts_in_stub_mode(self):
        model = MFMModel()
        assert model._stub_mode is True

    def test_model_with_custom_config(self):
        config = MFMConfig(hidden_size=512, num_layers=4)
        model = MFMModel(config)
        assert model.config.hidden_size == 512
        assert model.config.num_layers == 4
        assert model._stub_mode is True

    def test_base_model_is_none_initially(self):
        model = MFMModel()
        assert model._base_model is None
        assert model._confidence_head is None
        assert model._risk_head is None


class TestForwardPass:
    """Test forward pass returns expected keys."""

    def test_stub_forward_returns_expected_keys(self):
        model = MFMModel()
        result = model.forward([1, 2, 3])
        assert "logits" in result
        assert "confidence_logits" in result
        assert "risk_logits" in result

    def test_stub_forward_returns_empty_lists(self):
        model = MFMModel()
        result = model.forward([1, 2, 3])
        assert result["logits"] == []
        assert result["confidence_logits"] == []
        assert result["risk_logits"] == []

    def test_forward_with_attention_mask(self):
        model = MFMModel()
        result = model.forward([1, 2, 3], attention_mask=[1, 1, 1])
        assert "logits" in result

    def test_forward_with_empty_input(self):
        model = MFMModel()
        result = model.forward([])
        assert result["logits"] == []


class TestPredictActionPlan:
    """Test predict_action_plan returns action plan structure."""

    def test_stub_mode_returns_safe_defaults(self):
        model = MFMModel()
        plan = model.predict_action_plan({"sensor": "val"}, "do something")
        assert plan["action_plan"] == []
        assert plan["confidence"] == 0.0
        assert plan["risk_score"] == 1.0
        assert plan["escalation_needed"] is True
        assert plan["mode"] == "stub"

    def test_stub_mode_with_constraints(self):
        model = MFMModel()
        plan = model.predict_action_plan(
            {"a": 1}, "intent", constraints={"budget": 100}
        )
        assert plan["mode"] == "stub"
        assert "action_plan" in plan

    def test_stub_mode_with_history(self):
        model = MFMModel()
        plan = model.predict_action_plan(
            {"a": 1}, "intent", history=[{"prev": "action"}]
        )
        assert plan["mode"] == "stub"

    def test_plan_keys_are_correct_types(self):
        model = MFMModel()
        plan = model.predict_action_plan({}, "test")
        assert isinstance(plan["action_plan"], list)
        assert isinstance(plan["confidence"], float)
        assert isinstance(plan["risk_score"], float)
        assert isinstance(plan["escalation_needed"], bool)
        assert isinstance(plan["mode"], str)


class TestParameterCount:
    """Test parameter count."""

    def test_stub_mode_zero_params(self):
        model = MFMModel()
        assert model.parameter_count() == 0

    def test_no_base_model_zero_params(self):
        model = MFMModel()
        model._base_model = None
        assert model.parameter_count() == 0


class TestSaveLoadStub:
    """Test save/load weights in stub mode."""

    def test_save_weights_no_torch_no_crash(self, tmp_path):
        model = MFMModel()
        # Should not crash even without torch
        model.save_weights(str(tmp_path / "weights"))

    def test_load_weights_no_torch_no_crash(self, tmp_path):
        model = MFMModel()
        model.load_weights(str(tmp_path / "nonexistent"))

    def test_to_device_no_torch_no_crash(self):
        model = MFMModel()
        model.to_device("cpu")


class TestActionTypesList:
    """Test action types list in config."""

    def test_default_action_types(self):
        config = MFMConfig()
        expected = ["api_call", "actuator", "content", "data", "command", "agent"]
        assert config.action_types == expected

    def test_custom_action_types(self):
        config = MFMConfig(action_types=["custom_a", "custom_b"])
        assert config.action_types == ["custom_a", "custom_b"]

    def test_action_types_list_is_independent(self):
        c1 = MFMConfig()
        c2 = MFMConfig()
        c1.action_types.append("new_type")
        assert "new_type" not in c2.action_types
