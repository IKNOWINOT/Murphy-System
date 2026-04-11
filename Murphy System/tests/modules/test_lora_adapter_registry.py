# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
Tests for LoRA Adapter Registry — LORA-REGISTRY-001

Covers: registration, listing, querying, deregistration, validation,
compatibility search, persistence, summary, error conditions, and
thread safety.  Also covers MFMTrainerConfig enhancements
(target_modules expansion, lora_dropout, validation) and MFMModel
adapter hot-swap stubs.
"""

from __future__ import annotations

import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from murphy_foundation_model.lora_adapter_registry import (
    LoRAAdapterMetadata,
    LoRAAdapterRegistry,
)
from murphy_foundation_model.mfm_trainer import MFMTrainerConfig
from murphy_foundation_model.mfm_model import MFMModel


# ---------------------------------------------------------------------------
# MFMTrainerConfig — LoRA Without Regret enhancements
# ---------------------------------------------------------------------------


class TestTrainerConfigTargetModules:
    """Verify target_modules now includes attention + MLP layers."""

    def test_default_includes_attention_layers(self):
        config = MFMTrainerConfig()
        for module in ("q_proj", "v_proj", "k_proj", "o_proj"):
            assert module in config.target_modules

    def test_default_includes_mlp_layers(self):
        """Per 'LoRA Without Regret', MLP layers must be included."""
        config = MFMTrainerConfig()
        for module in ("gate_proj", "up_proj", "down_proj"):
            assert module in config.target_modules

    def test_seven_default_target_modules(self):
        config = MFMTrainerConfig()
        assert len(config.target_modules) == 7

    def test_custom_target_modules_override(self):
        config = MFMTrainerConfig(target_modules=["custom_a", "custom_b"])
        assert config.target_modules == ["custom_a", "custom_b"]


class TestTrainerConfigLoraDropout:
    """Verify lora_dropout is configurable."""

    def test_default_dropout(self):
        config = MFMTrainerConfig()
        assert config.lora_dropout == 0.05

    def test_custom_dropout(self):
        config = MFMTrainerConfig(lora_dropout=0.1)
        assert config.lora_dropout == 0.1

    def test_zero_dropout_is_valid(self):
        config = MFMTrainerConfig(lora_dropout=0.0)
        assert config.lora_dropout == 0.0


class TestTrainerConfigValidation:
    """Verify __post_init__ validates invariants."""

    def test_invalid_lora_rank(self):
        with pytest.raises(ValueError, match="lora_rank"):
            MFMTrainerConfig(lora_rank=0)

    def test_negative_lora_rank(self):
        with pytest.raises(ValueError, match="lora_rank"):
            MFMTrainerConfig(lora_rank=-1)

    def test_invalid_lora_alpha(self):
        with pytest.raises(ValueError, match="lora_alpha"):
            MFMTrainerConfig(lora_alpha=0)

    def test_invalid_lora_dropout_too_high(self):
        with pytest.raises(ValueError, match="lora_dropout"):
            MFMTrainerConfig(lora_dropout=1.0)

    def test_invalid_lora_dropout_negative(self):
        with pytest.raises(ValueError, match="lora_dropout"):
            MFMTrainerConfig(lora_dropout=-0.1)

    def test_empty_target_modules(self):
        with pytest.raises(ValueError, match="target_modules"):
            MFMTrainerConfig(target_modules=[])

    def test_invalid_loss_weights(self):
        with pytest.raises(ValueError, match="Loss weights"):
            MFMTrainerConfig(
                action_loss_weight=0.5,
                confidence_loss_weight=0.5,
                risk_loss_weight=0.5,
            )

    def test_valid_config_does_not_raise(self):
        config = MFMTrainerConfig()
        assert config.lora_rank == 16  # sanity check


# ---------------------------------------------------------------------------
# LoRAAdapterMetadata
# ---------------------------------------------------------------------------


class TestLoRAAdapterMetadata:
    """Test the adapter metadata dataclass."""

    def test_defaults(self):
        meta = LoRAAdapterMetadata()
        assert meta.adapter_id != ""
        assert meta.domain == "general"
        assert meta.status == "registered"
        assert meta.lora_rank == 16
        assert meta.lora_alpha == 32

    def test_to_dict(self):
        meta = LoRAAdapterMetadata(name="test-adapter")
        d = meta.to_dict()
        assert d["name"] == "test-adapter"
        assert "adapter_id" in d
        assert "created_at" in d

    def test_custom_fields(self):
        meta = LoRAAdapterMetadata(
            name="custom",
            domain="manufacturing",
            lora_rank=8,
            lora_alpha=16,
            lora_dropout=0.1,
            target_modules=["q_proj", "v_proj"],
            tags=["prod", "v1"],
        )
        assert meta.domain == "manufacturing"
        assert meta.lora_rank == 8
        assert meta.tags == ["prod", "v1"]


# ---------------------------------------------------------------------------
# LoRAAdapterRegistry
# ---------------------------------------------------------------------------


class TestRegistryRegistration:
    """Test adapter registration."""

    def test_register_returns_adapter_id(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        meta = LoRAAdapterMetadata(name="test-1")
        aid = registry.register(meta)
        assert aid == meta.adapter_id

    def test_register_persists_to_disk(self, tmp_path):
        path = str(tmp_path / "reg.json")
        registry = LoRAAdapterRegistry(path)
        meta = LoRAAdapterMetadata(name="test-1")
        registry.register(meta)
        assert os.path.isfile(path)

    def test_register_name_collision_raises(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        registry.register(LoRAAdapterMetadata(name="dup"))
        with pytest.raises(ValueError, match="LORA-REGISTRY-ERR-002"):
            registry.register(LoRAAdapterMetadata(name="dup"))

    def test_archived_name_does_not_collide(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        meta = LoRAAdapterMetadata(name="old")
        aid = registry.register(meta)
        registry.update_status(aid, "archived")
        # Should not raise.
        registry.register(LoRAAdapterMetadata(name="old"))


class TestRegistryGet:
    """Test get() method."""

    def test_get_existing(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        meta = LoRAAdapterMetadata(name="x")
        aid = registry.register(meta)
        got = registry.get(aid)
        assert got is not None
        assert got.name == "x"

    def test_get_missing_returns_none(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        assert registry.get("nonexistent") is None


class TestRegistryList:
    """Test list_adapters() with filters."""

    def _seed(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        registry.register(LoRAAdapterMetadata(name="a", domain="mfg", base_model="phi3"))
        registry.register(LoRAAdapterMetadata(name="b", domain="legal", base_model="phi3"))
        registry.register(LoRAAdapterMetadata(name="c", domain="mfg", base_model="llama"))
        return registry

    def test_list_all(self, tmp_path):
        registry = self._seed(tmp_path)
        assert len(registry.list_adapters()) == 3

    def test_filter_by_domain(self, tmp_path):
        registry = self._seed(tmp_path)
        result = registry.list_adapters(domain="mfg")
        assert len(result) == 2

    def test_filter_by_base_model(self, tmp_path):
        registry = self._seed(tmp_path)
        result = registry.list_adapters(base_model="llama")
        assert len(result) == 1
        assert result[0].name == "c"

    def test_filter_by_status(self, tmp_path):
        registry = self._seed(tmp_path)
        result = registry.list_adapters(status="registered")
        assert len(result) == 3
        result = registry.list_adapters(status="active")
        assert len(result) == 0


class TestRegistryStatus:
    """Test update_status()."""

    def test_valid_status_transition(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(LoRAAdapterMetadata(name="s"))
        assert registry.update_status(aid, "active")
        assert registry.get(aid).status == "active"

    def test_invalid_status_raises(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(LoRAAdapterMetadata(name="s"))
        with pytest.raises(ValueError, match="LORA-REGISTRY-ERR-003"):
            registry.update_status(aid, "invalid_status")

    def test_missing_adapter_returns_false(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        assert registry.update_status("missing", "active") is False


class TestRegistryDeregister:
    """Test deregister()."""

    def test_deregister_existing(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(LoRAAdapterMetadata(name="x"))
        assert registry.deregister(aid) is True
        assert registry.get(aid) is None

    def test_deregister_missing(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        assert registry.deregister("nope") is False


class TestRegistryValidation:
    """Test validate_adapter()."""

    def test_missing_adapter(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        result = registry.validate_adapter("nope")
        assert result["valid"] is False
        assert any("ERR-004" in e for e in result["errors"])

    def test_empty_path(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(LoRAAdapterMetadata(name="no-path", adapter_path=""))
        result = registry.validate_adapter(aid)
        assert result["valid"] is False
        assert any("ERR-005" in e for e in result["errors"])

    def test_nonexistent_path(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(
            LoRAAdapterMetadata(name="bad-path", adapter_path="/nonexistent/path")
        )
        result = registry.validate_adapter(aid)
        assert result["valid"] is False
        assert any("ERR-006" in e for e in result["errors"])

    def test_missing_adapter_config_file(self, tmp_path):
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(
            LoRAAdapterMetadata(
                name="no-cfg",
                adapter_path=str(adapter_dir),
                target_modules=["q_proj"],
            )
        )
        result = registry.validate_adapter(aid)
        assert result["valid"] is False
        assert any("ERR-007" in e for e in result["errors"])

    def test_valid_adapter(self, tmp_path):
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        (adapter_dir / "adapter_config.json").write_text("{}")
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(
            LoRAAdapterMetadata(
                name="valid",
                adapter_path=str(adapter_dir),
                lora_rank=16,
                target_modules=["q_proj", "v_proj"],
            )
        )
        result = registry.validate_adapter(aid)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_invalid_lora_rank(self, tmp_path):
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()
        (adapter_dir / "adapter_config.json").write_text("{}")
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(
            LoRAAdapterMetadata(
                name="bad-rank",
                adapter_path=str(adapter_dir),
                lora_rank=0,
                target_modules=["q_proj"],
            )
        )
        result = registry.validate_adapter(aid)
        assert result["valid"] is False
        assert any("ERR-008" in e for e in result["errors"])


class TestRegistryFindCompatible:
    """Test find_compatible()."""

    def test_finds_matching_adapters(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(
            LoRAAdapterMetadata(name="a", domain="mfg", base_model="phi3")
        )
        registry.update_status(aid, "active")
        results = registry.find_compatible("phi3", domain="mfg")
        assert len(results) == 1

    def test_domain_sorting(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aids = []
        for name, domain in [("gen", "general"), ("mfg", "manufacturing"), ("exact", "legal")]:
            aid = registry.register(
                LoRAAdapterMetadata(name=name, domain=domain, base_model="phi3")
            )
            registry.update_status(aid, "active")
            aids.append(aid)
        results = registry.find_compatible("phi3", domain="legal")
        assert results[0].domain == "legal"
        assert results[1].domain == "general"


class TestRegistryPersistence:
    """Test save/load round-trip."""

    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "reg.json")
        registry1 = LoRAAdapterRegistry(path)
        registry1.register(LoRAAdapterMetadata(name="persisted", domain="test"))
        # Load into a new instance.
        registry2 = LoRAAdapterRegistry(path)
        all_adapters = registry2.list_adapters()
        assert len(all_adapters) == 1
        assert all_adapters[0].name == "persisted"

    def test_load_empty_file(self, tmp_path):
        path = tmp_path / "reg.json"
        path.write_text("{}")
        registry = LoRAAdapterRegistry(str(path))
        assert len(registry.list_adapters()) == 0


class TestRegistrySummary:
    """Test get_summary()."""

    def test_summary_structure(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        registry.register(LoRAAdapterMetadata(name="a", domain="mfg"))
        registry.register(LoRAAdapterMetadata(name="b", domain="legal"))
        summary = registry.get_summary()
        assert summary["total_adapters"] == 2
        assert summary["by_domain"]["mfg"] == 1
        assert summary["by_domain"]["legal"] == 1
        assert summary["max_capacity"] == 500

    def test_empty_registry_summary(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        summary = registry.get_summary()
        assert summary["total_adapters"] == 0


class TestRegistryMetrics:
    """Test update_metrics()."""

    def test_update_metrics(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        aid = registry.register(LoRAAdapterMetadata(name="m"))
        assert registry.update_metrics(aid, {"accuracy": 0.95, "loss": 0.1})
        adapter = registry.get(aid)
        assert adapter.metrics["accuracy"] == 0.95

    def test_update_metrics_missing(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        assert registry.update_metrics("nope", {"x": 1}) is False


class TestRegistryThreadSafety:
    """Basic thread-safety smoke test."""

    def test_concurrent_registrations(self, tmp_path):
        registry = LoRAAdapterRegistry(str(tmp_path / "reg.json"))
        errors = []

        def _register(idx):
            try:
                registry.register(LoRAAdapterMetadata(name=f"thread-{idx}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(registry.list_adapters()) == 20


# ---------------------------------------------------------------------------
# MFMModel — adapter hot-swap stubs
# ---------------------------------------------------------------------------


class TestModelSwapAdapterStub:
    """Test swap_adapter and has_active_adapter in stub mode."""

    def test_swap_no_base_model_returns_false(self):
        model = MFMModel()
        assert model.swap_adapter("/tmp/fake") is False

    def test_swap_nonexistent_path_returns_false(self):
        model = MFMModel()
        model._base_model = "fake"  # avoid the None check
        model._stub_mode = False
        assert model.swap_adapter("/nonexistent/path") is False

    def test_has_active_adapter_false_in_stub_mode(self):
        model = MFMModel()
        assert model.has_active_adapter is False
