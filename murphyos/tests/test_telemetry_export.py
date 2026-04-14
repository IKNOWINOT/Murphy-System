# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Tests for murphy_telemetry_export — Prometheus textfile exporter."""

from __future__ import annotations

import os
import pathlib
import sys
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# PYTHONPATH
# ---------------------------------------------------------------------------
_MURPHYOS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MURPHYOS / "userspace" / "murphy-telemetry-export"))

from murphy_telemetry_export import (
    TelemetryConfig,
    TelemetryExporter,
    _MetricFamily,
    _MetricLine,
    _labels_str,
    _safe_float,
)


# ── helpers ───────────────────────────────────────────────────────────────
def _make_exporter(**overrides) -> TelemetryExporter:
    """Create an exporter with all data sources disabled (mocked)."""
    cfg = TelemetryConfig(
        data_sources=[],  # no live data sources
        output_path=pathlib.Path("/dev/null"),
        **overrides,
    )
    return TelemetryExporter(config=cfg)


# ── initialisation ────────────────────────────────────────────────────────
class TestTelemetryExporterInit:
    def test_init_default_config(self):
        exp = _make_exporter()
        assert exp.config is not None
        assert isinstance(exp.config, TelemetryConfig)

    def test_init_data_sources_disabled(self):
        exp = _make_exporter()
        assert exp._dbus is None
        assert exp._rest is None
        assert exp._mfs is None


# ── _collect_confidence ───────────────────────────────────────────────────
class TestCollectConfidence:
    def test_collect_confidence_returns_valid_metric(self):
        exp = _make_exporter(confidence=True)
        with mock.patch.object(exp, "_query_chain", return_value={"score": 0.85, "changes_total": 42}):
            families = exp._collect_confidence()
        assert len(families) == 2
        assert families[0].name == "murphy_confidence_score"
        assert families[0].samples[0].value == 0.85

    def test_collect_confidence_handles_missing_data(self):
        exp = _make_exporter(confidence=True)
        with mock.patch.object(exp, "_query_chain", return_value=None):
            families = exp._collect_confidence()
        assert len(families) == 2
        assert families[0].samples[0].value == 0.0


# ── _collect_gates ────────────────────────────────────────────────────────
class TestCollectGates:
    def test_collect_gates_returns_per_gate_metrics(self):
        exp = _make_exporter(gates=True)
        gate_data = {
            "gates": {
                "EXECUTIVE": {"active": True, "decisions": {"allow": 10, "deny": 2}},
                "DEPLOY": {"active": False, "decisions": {"allow": 5}},
            }
        }
        with mock.patch.object(exp, "_query_chain", return_value=gate_data):
            families = exp._collect_gates()
        assert len(families) == 2
        status_fam = families[0]
        assert status_fam.name == "murphy_gate_status"
        assert any(s.labels.get("gate") == "EXECUTIVE" for s in status_fam.samples)


# ── _collect_swarm ────────────────────────────────────────────────────────
class TestCollectSwarm:
    def test_collect_swarm_returns_agent_count(self):
        exp = _make_exporter(swarm=True)
        swarm_data = {"agents_active": 5, "tasks": {"running": 3, "queued": 2}}
        with mock.patch.object(exp, "_query_chain", return_value=swarm_data):
            families = exp._collect_swarm()
        agent_fam = families[0]
        assert agent_fam.name == "murphy_swarm_agents_active"
        assert agent_fam.samples[0].value == 5.0


# ── _collect_llm ──────────────────────────────────────────────────────────
class TestCollectLLM:
    def test_collect_llm_returns_provider_metrics(self):
        exp = _make_exporter(llm=True)
        llm_data = {
            "requests": {"openai": {"gpt-4": 100}},
            "tokens": {"openai": {"input": 50000, "output": 30000}},
            "latency": {"openai": {"sum": 120.5, "count": 100}},
            "cost_usd": {"openai": 12.50},
            "errors": {"openai": 2},
        }
        with mock.patch.object(exp, "_query_chain", return_value=llm_data):
            families = exp._collect_llm()
        assert len(families) == 5
        assert families[0].name == "murphy_llm_requests_total"


# ── _collect_security ─────────────────────────────────────────────────────
class TestCollectSecurity:
    def test_collect_security_returns_posture_score(self):
        exp = _make_exporter(security=True)
        sec_data = {
            "posture_score": 85.0,
            "threats": {"network_sentinel": 3},
            "encryptions_total": 1200,
        }
        with mock.patch.object(exp, "_query_chain", return_value=sec_data):
            families = exp._collect_security()
        assert len(families) == 3
        posture_fam = families[0]
        assert posture_fam.name == "murphy_security_posture_score"
        assert posture_fam.samples[0].value == 85.0


# ── render prometheus format ──────────────────────────────────────────────
class TestRenderPrometheus:
    def test_render_outputs_valid_textfile_format(self):
        families = [
            _MetricFamily(
                name="murphy_test_gauge",
                help_text="A test gauge.",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_test_gauge", value=42.0)],
            ),
        ]
        text = TelemetryExporter._render(families)
        assert "# HELP murphy_test_gauge A test gauge." in text
        assert "# TYPE murphy_test_gauge gauge" in text
        assert "murphy_test_gauge 42" in text

    def test_render_with_labels(self):
        families = [
            _MetricFamily(
                name="murphy_labeled",
                help_text="Labeled metric.",
                metric_type="counter",
                samples=[
                    _MetricLine(name="murphy_labeled", labels={"provider": "openai"}, value=10.0),
                ],
            ),
        ]
        text = TelemetryExporter._render(families)
        assert 'provider="openai"' in text


# ── atomic file writes ────────────────────────────────────────────────────
class TestAtomicWrite:
    def test_write_atomic_uses_temp_and_rename(self, tmp_path):
        cfg = TelemetryConfig(
            output_path=tmp_path / "metrics.prom",
            data_sources=[],
        )
        exp = TelemetryExporter(config=cfg)
        exp._write_atomic("# test metric\nmurphy_test 1\n")
        assert cfg.output_path.exists()
        content = cfg.output_path.read_text()
        assert "murphy_test 1" in content


# ── data source fallback chain ────────────────────────────────────────────
class TestFallbackChain:
    def test_query_chain_tries_sources_in_order(self):
        cfg = TelemetryConfig(data_sources=["dbus", "rest_api", "murphyfs"])
        exp = TelemetryExporter(config=cfg)
        # dbus returns None, rest returns data
        exp._dbus = mock.MagicMock()
        exp._dbus.query.return_value = None
        exp._rest = mock.MagicMock()
        exp._rest.query.return_value = {"score": 0.9}
        exp._mfs = mock.MagicMock()

        result = exp._query_chain("GetConfidence", "confidence", "confidence.json")
        assert result == {"score": 0.9}
        exp._dbus.query.assert_called_once()
        exp._rest.query.assert_called_once()
        exp._mfs.read_json.assert_not_called()


# ── configuration ─────────────────────────────────────────────────────────
class TestTelemetryConfig:
    def test_default_config_has_expected_fields(self):
        cfg = TelemetryConfig()
        assert cfg.enabled is True
        assert cfg.confidence is True
        assert cfg.interval_seconds > 0

    def test_config_from_file_fallback(self):
        with mock.patch("murphy_telemetry_export._load_yaml", side_effect=FileNotFoundError):
            cfg = TelemetryConfig.from_file(pathlib.Path("/nonexistent.yaml"))
        assert cfg.enabled is True


# ── helper functions ──────────────────────────────────────────────────────
class TestHelpers:
    def test_safe_float_valid(self):
        assert _safe_float(3.14) == 3.14
        assert _safe_float("42") == 42.0

    def test_safe_float_invalid(self):
        assert _safe_float(None) == 0.0
        assert _safe_float("not-a-number") == 0.0

    def test_labels_str_empty(self):
        assert _labels_str({}) == ""

    def test_labels_str_formatted(self):
        result = _labels_str({"provider": "openai", "model": "gpt-4"})
        assert 'provider="openai"' in result
        assert 'model="gpt-4"' in result
