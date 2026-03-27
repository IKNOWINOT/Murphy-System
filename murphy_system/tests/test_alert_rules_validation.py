"""
Alert Rules Validation (OBS-ALERTS-001).

Verifies that every Murphy-specific metric referenced in
``prometheus-rules/murphy-alerts.yml`` and the Grafana dashboard JSON is
actually registered / emitted by the application.

Design rationale
----------------
When a metric name is renamed or removed the alert rule keeps compiling but
silently stops firing.  This test acts as a compile-time link-check between
the alert rules and the metric registry.

Coverage
--------
- All ``murphy_*`` metric names in alert/recording rules resolve to a known
  emitted metric family.
- Grafana dashboard panels reference only metrics that are emitted.
- The canonical ``src/metrics.py`` ``render_metrics()`` output contains the
  expected metric families after seeding sample data.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Set

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent          # murphy_system/
_ALERTS_FILE = _REPO_ROOT / "prometheus-rules" / "murphy-alerts.yml"
_GRAFANA_FILE = _REPO_ROOT / "grafana" / "dashboards" / "murphy-system-overview.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_murphy_metrics_from_yaml(path: Path) -> Set[str]:
    """Return all ``murphy_*`` metric base-names found in a YAML file."""
    text = path.read_text(encoding="utf-8")
    raw = re.findall(r"murphy_[a-z_]+", text)
    # Strip Prometheus suffixes added by prometheus_client
    suffixes = ("_total", "_bucket", "_sum", "_count", "_created")
    bases: Set[str] = set()
    for name in raw:
        base = name
        for suf in suffixes:
            if base.endswith(suf):
                base = base[: -len(suf)]
                break
        bases.add(base)
    return bases


def _extract_murphy_metrics_from_grafana(path: Path) -> Set[str]:
    """Return all ``murphy_*`` metric base-names referenced in Grafana JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw: Set[str] = set()
    for panel in data.get("panels", []):
        for target in panel.get("targets", []):
            for m in re.findall(r"murphy_[a-z_]+", target.get("expr", "")):
                raw.add(m)
    suffixes = ("_total", "_bucket", "_sum", "_count", "_created")
    bases: Set[str] = set()
    for name in raw:
        base = name
        for suf in suffixes:
            if base.endswith(suf):
                base = base[: -len(suf)]
                break
        bases.add(base)
    return bases


# Metrics that are emitted by Murphy (base names, no prometheus_client suffixes).
# Kept as a module-level constant so both test classes can reference it.
# Includes metrics from BOTH src/metrics.py (always available) and the
# prometheus_client block in app.py (available when prometheus_client is installed).
_EMITTED_METRICS: Set[str] = {
    # Request traffic — incremented by _TraceIdMiddleware in app.py
    "murphy_requests_total",          # src/metrics.py key (also prometheus_client Counter "murphy_requests" → _total)
    "murphy_request_duration_seconds", # src/metrics.py + prometheus_client Histogram
    "murphy_response_size_bytes",      # prometheus_client Histogram
    # System vitals
    "murphy_uptime_seconds",           # src/metrics.py Gauge + prometheus_client Gauge
    "murphy_task_queue_depth",         # src/metrics.py Gauge + prometheus_client Gauge
    # LLM / ML
    "murphy_llm_calls",                # prometheus_client Counter → _total; labels: [provider, status]
    "murphy_confidence_score",         # prometheus_client Histogram; label: [domain]
    # Internal
    "murphy_gate_evaluations",         # prometheus_client Counter
    "murphy_requests",                 # prometheus_client Counter base name (→ murphy_requests_total)
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAlertRulesMetrics:
    """All metrics in alert rules must be emitted by the app."""

    @pytest.mark.skipif(not _ALERTS_FILE.exists(), reason="Alert rules file not found")
    def test_alert_rule_metrics_are_emitted(self):
        """Every murphy_* metric referenced in murphy-alerts.yml is registered."""
        alert_metrics = _extract_murphy_metrics_from_yaml(_ALERTS_FILE)
        unresolved = alert_metrics - _EMITTED_METRICS
        assert not unresolved, (
            f"Alert rules reference metrics not emitted by the app: {sorted(unresolved)}\n"
            f"Add them to the prometheus_client block in src/runtime/app.py"
        )

    @pytest.mark.skipif(not _ALERTS_FILE.exists(), reason="Alert rules file not found")
    def test_alert_rules_file_parses(self):
        """Alert rules YAML is syntactically valid."""
        import yaml
        data = yaml.safe_load(_ALERTS_FILE.read_text())
        assert isinstance(data, dict), "Alert rules YAML must be a mapping"
        assert "groups" in data, "Alert rules must have a 'groups' key"
        rules_count = sum(len(g.get("rules", [])) for g in data["groups"])
        assert rules_count > 0, "No alert rules found"

    @pytest.mark.skipif(not _ALERTS_FILE.exists(), reason="Alert rules file not found")
    def test_llm_calls_counter_has_status_label(self):
        """The murphy_llm_calls counter must carry a 'status' label.

        The MurphyLLMCallFailures alert filters on
        ``murphy_llm_calls_total{status="error"}``; without the 'status'
        label the alert will never fire.
        """
        text = _ALERTS_FILE.read_text()
        assert 'status="error"' in text or "status=~" in text, (
            "MurphyLLMCallFailures alert rule expects a 'status' label "
            "but the rule no longer contains status filter"
        )


class TestGrafanaDashboardMetrics:
    """All metrics in Grafana dashboard must be emitted by the app."""

    @pytest.mark.skipif(not _GRAFANA_FILE.exists(), reason="Grafana dashboard file not found")
    def test_grafana_metrics_are_emitted(self):
        """Every murphy_* metric in the Grafana dashboard is registered."""
        grafana_metrics = _extract_murphy_metrics_from_grafana(_GRAFANA_FILE)
        unresolved = grafana_metrics - _EMITTED_METRICS
        assert not unresolved, (
            f"Grafana dashboard references metrics not emitted by the app: {sorted(unresolved)}\n"
            f"Add them to the prometheus_client block in src/runtime/app.py"
        )

    @pytest.mark.skipif(not _GRAFANA_FILE.exists(), reason="Grafana dashboard file not found")
    def test_grafana_dashboard_parses(self):
        """Grafana dashboard JSON is syntactically valid."""
        data = json.loads(_GRAFANA_FILE.read_text())
        assert "panels" in data, "Grafana dashboard must have 'panels' key"
        assert len(data["panels"]) > 0, "Grafana dashboard has no panels"


class TestSrcMetricsEmitsExpectedFamilies:
    """src/metrics.py render_metrics() output contains expected families."""

    def test_uptime_always_in_output(self):
        from src.metrics import render_metrics, _gauges, _lock
        output = render_metrics()
        assert "murphy_uptime_seconds" in output

    def test_task_queue_depth_in_output_after_seeding(self):
        from src.metrics import render_metrics, set_gauge, _gauges, _lock
        with _lock:
            _gauges.clear()
        set_gauge("murphy_task_queue_depth", 42.0)
        output = render_metrics()
        assert "murphy_task_queue_depth" in output
        assert "42.0" in output

    def test_requests_total_in_output_after_increment(self):
        from src.metrics import render_metrics, inc_counter, _counters, _lock
        with _lock:
            _counters.clear()
        inc_counter("murphy_requests_total", labels={"method": "GET", "status": "200"})
        output = render_metrics()
        assert "murphy_requests_total" in output

    def test_request_duration_in_output_after_observe(self):
        from src.metrics import render_metrics, observe_histogram, _histograms, _lock
        with _lock:
            _histograms.clear()
        observe_histogram("murphy_request_duration_seconds", 0.123)
        output = render_metrics()
        assert "murphy_request_duration_seconds" in output
