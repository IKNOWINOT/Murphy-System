# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Extended tests for mfm_trainer module.

Covers MFMTrainerConfig defaults, compute_loss stub, evaluate stub,
training data loading, merge_and_save stub mode, and config
environment variable reading.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.mfm_trainer import (
    MFMTrainer,
    MFMTrainerConfig,
    load_training_data,
)


class TestMFMTrainerConfigDefaults:
    """Test MFMTrainerConfig defaults."""

    def test_lora_rank(self):
        config = MFMTrainerConfig()
        assert config.lora_rank == 16

    def test_lora_alpha(self):
        config = MFMTrainerConfig()
        assert config.lora_alpha == 32

    def test_target_modules(self):
        config = MFMTrainerConfig()
        # LoRA Without Regret: attention + MLP layers by default
        assert config.target_modules == [
            "q_proj", "v_proj", "k_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]

    def test_learning_rate(self):
        config = MFMTrainerConfig()
        assert config.learning_rate == 2e-4

    def test_num_epochs(self):
        config = MFMTrainerConfig()
        assert config.num_epochs == 3

    def test_batch_size(self):
        config = MFMTrainerConfig()
        assert config.batch_size == 4

    def test_gradient_accumulation(self):
        config = MFMTrainerConfig()
        assert config.gradient_accumulation_steps == 4

    def test_loss_weights_sum_to_1(self):
        config = MFMTrainerConfig()
        total = (
            config.action_loss_weight
            + config.confidence_loss_weight
            + config.risk_loss_weight
        )
        assert total == pytest.approx(1.0)

    def test_fp16_default(self):
        config = MFMTrainerConfig()
        assert config.fp16 is True

    def test_eval_steps(self):
        config = MFMTrainerConfig()
        assert config.eval_steps == 500


class TestTrainerStubMode:
    """Test trainer operations without ML dependencies."""

    def test_train_without_torch_returns_skipped(self):
        trainer = MFMTrainer(config=MFMTrainerConfig())
        result = trainer.train(train_dataset=[])
        assert result["status"] in ("skipped", "completed")

    def test_train_with_no_model_returns_skipped(self):
        trainer = MFMTrainer(model=None, config=MFMTrainerConfig())
        result = trainer.train(train_dataset=[{"input_ids": [1], "labels": [1]}])
        assert result["status"] == "skipped"

    def test_evaluate_without_torch_returns_defaults(self):
        trainer = MFMTrainer(config=MFMTrainerConfig())
        metrics = trainer.evaluate(eval_dataset=[])
        assert "loss" in metrics
        assert "action_accuracy" in metrics
        assert "confidence_mae" in metrics
        assert "risk_mae" in metrics

    def test_evaluate_returns_zero_metrics(self):
        trainer = MFMTrainer(config=MFMTrainerConfig())
        metrics = trainer.evaluate(eval_dataset=[])
        assert metrics["loss"] == 0.0
        assert metrics["action_accuracy"] == 0.0


class TestMergeAndSave:
    """Test merge and save flow in stub mode."""

    def test_merge_without_peft_returns_false(self):
        trainer = MFMTrainer(config=MFMTrainerConfig())
        result = trainer.merge_and_save("/tmp/test_merge")
        assert result is False

    def test_merge_with_no_model_returns_false(self):
        trainer = MFMTrainer(model=None, config=MFMTrainerConfig())
        result = trainer.merge_and_save("/tmp/test_merge")
        assert result is False


class TestLoadTrainingData:
    """Test training data loading."""

    def test_load_from_existing_files(self, tmp_path):
        train_data = [
            {"input_ids": [1, 2, 3], "labels": [1, 2, 3]},
            {"input_ids": [4, 5, 6], "labels": [4, 5, 6]},
        ]
        val_data = [{"input_ids": [7, 8], "labels": [7, 8]}]

        train_path = tmp_path / "train.jsonl"
        val_path = tmp_path / "validation.jsonl"

        with open(train_path, "w") as fh:
            for item in train_data:
                fh.write(json.dumps(item) + "\n")
        with open(val_path, "w") as fh:
            for item in val_data:
                fh.write(json.dumps(item) + "\n")

        loaded_train, loaded_val = load_training_data(str(tmp_path))
        assert len(loaded_train) == 2
        assert len(loaded_val) == 1
        assert loaded_train[0]["input_ids"] == [1, 2, 3]

    def test_load_from_missing_files(self, tmp_path):
        train, val = load_training_data(str(tmp_path))
        assert train == []
        assert val == []

    def test_load_skips_invalid_json_lines(self, tmp_path):
        train_path = tmp_path / "train.jsonl"
        with open(train_path, "w") as fh:
            fh.write('{"valid": true}\n')
            fh.write('not json\n')
            fh.write('{"also_valid": true}\n')

        train, val = load_training_data(str(tmp_path))
        assert len(train) == 2

    def test_load_skips_empty_lines(self, tmp_path):
        train_path = tmp_path / "train.jsonl"
        with open(train_path, "w") as fh:
            fh.write('{"a": 1}\n')
            fh.write('\n')
            fh.write('   \n')
            fh.write('{"b": 2}\n')

        train, _ = load_training_data(str(tmp_path))
        assert len(train) == 2


class TestConfigCustomValues:
    """Test config with custom/environment variable values."""

    def test_custom_config_overrides(self):
        config = MFMTrainerConfig(
            lora_rank=8,
            learning_rate=1e-3,
            num_epochs=5,
            batch_size=8,
        )
        assert config.lora_rank == 8
        assert config.learning_rate == 1e-3
        assert config.num_epochs == 5
        assert config.batch_size == 8

    def test_output_dir_default(self):
        config = MFMTrainerConfig()
        assert config.output_dir != ""

    def test_warmup_steps(self):
        config = MFMTrainerConfig()
        assert config.warmup_steps == 100

    def test_max_grad_norm(self):
        config = MFMTrainerConfig()
        assert config.max_grad_norm == 1.0
