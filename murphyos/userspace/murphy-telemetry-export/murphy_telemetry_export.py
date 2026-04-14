# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""Murphy Telemetry Export — Prometheus node_exporter textfile collector.

Collects Murphy System runtime metrics and writes them in Prometheus
exposition format to a textfile that ``node_exporter --collector.textfile``
picks up automatically.

Data-source fallback chain
--------------------------
1. D-Bus ``org.murphy.System``  (fastest, zero-copy)
2. REST API ``http://127.0.0.1:8000/api/``  (reliable JSON)
3. MurphyFS ``/murphy/live/``  (always-available virtual FS)
4. cgroup ``/sys/fs/cgroup/murphy.slice/``  (direct kernel read)

Error-code registry
-------------------
MURPHY-TELEMETRY-ERR-001  Config file not found / unreadable
MURPHY-TELEMETRY-ERR-002  Config file parse error (invalid YAML)
MURPHY-TELEMETRY-ERR-003  Output path not writable
MURPHY-TELEMETRY-ERR-004  D-Bus query failed
MURPHY-TELEMETRY-ERR-005  REST API query failed
MURPHY-TELEMETRY-ERR-006  MurphyFS read failed
MURPHY-TELEMETRY-ERR-007  cgroup read failed
MURPHY-TELEMETRY-ERR-008  Metric collection error (catch-all)
MURPHY-TELEMETRY-ERR-009  Atomic rename failed
MURPHY-TELEMETRY-ERR-010  Unexpected fatal error
"""

from __future__ import annotations

import dataclasses
import json
import logging
import math
import os
import subprocess
import sys
import textwrap
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_LOG = logging.getLogger("murphy.telemetry")

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG_PATH = Path("/etc/murphy/telemetry.yaml")
_DEFAULT_OUTPUT_PATH = Path(
    "/var/lib/prometheus/node-exporter/murphy.prom",
)
_DEFAULT_INTERVAL = 15  # seconds
_DEFAULT_DATA_SOURCES = ("dbus", "rest_api", "murphyfs", "cgroup")

# ---------------------------------------------------------------------------
# Histogram bucket boundaries (seconds) — reuse from prometheus_metrics_exporter
# ---------------------------------------------------------------------------
_FORGE_DURATION_BUCKETS: Tuple[float, ...] = (
    0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float("inf"),
)


# ── helpers ────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file without requiring PyYAML at import time.

    Falls back to a minimal safe subset parser when PyYAML is absent so the
    module can be unit-tested without optional dependencies.
    """
    try:
        import yaml  # type: ignore[import-untyped]

        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}  # type: ignore[no-any-return]
    except ImportError:
        # Minimal key: value parser for flat/simple YAML used by telemetry.yaml
        data: Dict[str, Any] = {}
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if ":" in stripped:
                    key, _, val = stripped.partition(":")
                    val = val.strip()
                    if val.lower() in ("true", "yes"):
                        data[key.strip()] = True
                    elif val.lower() in ("false", "no"):
                        data[key.strip()] = False
                    elif val.isdigit():
                        data[key.strip()] = int(val)
                    else:
                        data[key.strip()] = val
        return data


def _safe_float(raw: Any, default: float = 0.0) -> float:
    """Convert *raw* to float, returning *default* on failure."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _labels_str(labels: Dict[str, str]) -> str:
    """Format a label dict as a Prometheus label string ``{k="v",...}``."""
    if not labels:
        return ""
    inner = ",".join(
        f'{k}="{v}"' for k, v in sorted(labels.items())
    )
    return "{" + inner + "}"


# ── Prometheus text-format primitives ──────────────────────────────────────
@dataclasses.dataclass(slots=True)
class _MetricLine:
    """A single line in the Prometheus exposition block."""

    name: str
    labels: Dict[str, str] = dataclasses.field(default_factory=dict)
    value: float = 0.0
    timestamp_ms: Optional[int] = None


@dataclasses.dataclass(slots=True)
class _MetricFamily:
    """One metric family (HELP + TYPE + samples)."""

    name: str
    help_text: str
    metric_type: str  # "gauge", "counter", "histogram", "summary"
    samples: List[_MetricLine] = dataclasses.field(default_factory=list)

    def render(self) -> str:
        lines: List[str] = [
            f"# HELP {self.name} {self.help_text}",
            f"# TYPE {self.name} {self.metric_type}",
        ]
        for s in self.samples:
            lbl = _labels_str(s.labels)
            ts_part = f" {s.timestamp_ms}" if s.timestamp_ms else ""
            # Represent special float values per Prometheus spec
            if math.isinf(s.value) and s.value > 0:
                val_str = "+Inf"
            elif math.isnan(s.value):
                val_str = "NaN"
            else:
                val_str = f"{s.value:g}"
            lines.append(f"{s.name}{lbl} {val_str}{ts_part}")
        return "\n".join(lines)


# ── Data-source adapters ──────────────────────────────────────────────────
class _DBusSource:
    """Fetch metrics via D-Bus ``org.murphy.System``."""

    BUS_NAME = "org.murphy.System"
    OBJ_PATH = "/org/murphy/System"
    IFACE = "org.murphy.System"

    def query(self, method: str) -> Optional[Dict[str, Any]]:
        """Call a D-Bus method and return parsed JSON or ``None``."""
        try:
            cmd = [
                "dbus-send",
                "--system",
                "--print-reply=literal",
                f"--dest={self.BUS_NAME}",
                self.OBJ_PATH,
                f"{self.IFACE}.{method}",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            return json.loads(result.stdout.strip())  # type: ignore[no-any-return]
        except FileNotFoundError:
            # MURPHY-TELEMETRY-ERR-004: dbus-send binary not found
            _LOG.debug("MURPHY-TELEMETRY-ERR-004: dbus-send not available")
            return None
        except subprocess.TimeoutExpired:
            # MURPHY-TELEMETRY-ERR-004: dbus-send timed out
            _LOG.warning("MURPHY-TELEMETRY-ERR-004: D-Bus call timed out for %s", method)
            return None
        except (json.JSONDecodeError, OSError) as exc:
            # MURPHY-TELEMETRY-ERR-004: D-Bus response parse error
            _LOG.warning("MURPHY-TELEMETRY-ERR-004: D-Bus parse error: %s", exc)
            return None


class _RestAPISource:
    """Fetch metrics via the Murphy REST API on localhost."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/api") -> None:
        self._base = base_url.rstrip("/")

    def query(self, endpoint: str, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """GET *endpoint* and return parsed JSON or ``None``."""
        url = f"{self._base}/{endpoint.lstrip('/')}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())  # type: ignore[no-any-return]
        except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
            # MURPHY-TELEMETRY-ERR-005: REST API query failed
            _LOG.debug("MURPHY-TELEMETRY-ERR-005: REST query %s failed: %s", url, exc)
            return None


class _MurphyFSSource:
    """Read metrics from MurphyFS virtual files under ``/murphy/live/``."""

    def __init__(self, root: str = "/murphy/live") -> None:
        self._root = Path(root)

    def read_json(self, relpath: str) -> Optional[Dict[str, Any]]:
        """Read and parse a JSON file under the MurphyFS root."""
        path = self._root / relpath
        try:
            text = path.read_text(encoding="utf-8")
            return json.loads(text)  # type: ignore[no-any-return]
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            # MURPHY-TELEMETRY-ERR-006: MurphyFS read failed
            _LOG.debug("MURPHY-TELEMETRY-ERR-006: MurphyFS read %s failed: %s", path, exc)
            return None

    def read_float(self, relpath: str, default: float = 0.0) -> float:
        """Read a single numeric value from a MurphyFS file."""
        path = self._root / relpath
        try:
            return float(path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, OSError, ValueError):
            # MURPHY-TELEMETRY-ERR-006: MurphyFS read failed (numeric)
            return default


class _CGroupSource:
    """Read cgroup v2 metrics from ``/sys/fs/cgroup/murphy.slice/``."""

    def __init__(self, root: str = "/sys/fs/cgroup/murphy.slice") -> None:
        self._root = Path(root)

    def memory_current(self, slice_name: str = "murphy.slice") -> Optional[float]:
        """Return current memory usage in bytes for the given slice."""
        path = self._root / "memory.current"
        return self._read_counter(path, slice_name)

    def cpu_usage(self, slice_name: str = "murphy.slice") -> Optional[float]:
        """Return cumulative CPU usage in microseconds, converted to seconds."""
        path = self._root / "cpu.stat"
        try:
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("usage_usec"):
                    return float(line.split()[1]) / 1_000_000.0
        except (FileNotFoundError, OSError, ValueError, IndexError) as exc:
            # MURPHY-TELEMETRY-ERR-007: cgroup read failed
            _LOG.debug("MURPHY-TELEMETRY-ERR-007: cgroup cpu read: %s", exc)
        return None

    def child_slices(self) -> List[str]:
        """List child slice directories."""
        try:
            return [
                d.name
                for d in self._root.iterdir()
                if d.is_dir() and d.name.endswith(".slice")
            ]
        except (FileNotFoundError, OSError):
            return []

    # ------------------------------------------------------------------
    def _read_counter(self, path: Path, _slice: str) -> Optional[float]:
        try:
            return float(path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, OSError, ValueError) as exc:
            # MURPHY-TELEMETRY-ERR-007: cgroup read failed
            _LOG.debug("MURPHY-TELEMETRY-ERR-007: cgroup read %s: %s", path, exc)
            return None


# ── Configuration ─────────────────────────────────────────────────────────
@dataclasses.dataclass
class TelemetryConfig:
    """Parsed telemetry configuration."""

    enabled: bool = True
    output_path: Path = _DEFAULT_OUTPUT_PATH
    interval_seconds: int = _DEFAULT_INTERVAL
    data_sources: List[str] = dataclasses.field(
        default_factory=lambda: list(_DEFAULT_DATA_SOURCES),
    )
    # Per-family toggles
    confidence: bool = True
    gates: bool = True
    swarm: bool = True
    forge: bool = True
    llm: bool = True
    security: bool = True
    system: bool = True
    backup: bool = True
    cgroup: bool = True

    @classmethod
    def from_file(cls, path: Path) -> TelemetryConfig:
        """Load config from a YAML file, falling back to defaults."""
        try:
            raw = _load_yaml(path)
        except FileNotFoundError:
            # MURPHY-TELEMETRY-ERR-001: config file not found
            _LOG.warning(
                "MURPHY-TELEMETRY-ERR-001: Config %s not found, using defaults", path,
            )
            return cls()
        except Exception as exc:
            # MURPHY-TELEMETRY-ERR-002: config parse error
            _LOG.error("MURPHY-TELEMETRY-ERR-002: Config parse error: %s", exc)
            return cls()

        section = raw.get("murphy_telemetry", raw)
        metrics = section.get("metrics", {})
        sources = section.get("data_sources", list(_DEFAULT_DATA_SOURCES))
        return cls(
            enabled=bool(section.get("enabled", True)),
            output_path=Path(section.get("output_path", str(_DEFAULT_OUTPUT_PATH))),
            interval_seconds=int(section.get("interval_seconds", _DEFAULT_INTERVAL)),
            data_sources=list(sources) if isinstance(sources, list) else [str(sources)],
            confidence=bool(metrics.get("confidence", True)),
            gates=bool(metrics.get("gates", True)),
            swarm=bool(metrics.get("swarm", True)),
            forge=bool(metrics.get("forge", True)),
            llm=bool(metrics.get("llm", True)),
            security=bool(metrics.get("security", True)),
            system=bool(metrics.get("system", True)),
            backup=bool(metrics.get("backup", True)),
            cgroup=bool(metrics.get("cgroup", True)),
        )


# ── Main Exporter ─────────────────────────────────────────────────────────
class TelemetryExporter:
    """Collect Murphy System metrics and write Prometheus textfile output.

    Usage::

        exporter = TelemetryExporter.from_config("/etc/murphy/telemetry.yaml")
        exporter.collect_once()          # single pass
        exporter.run_loop()              # blocking loop (for systemd)
    """

    def __init__(self, config: Optional[TelemetryConfig] = None) -> None:
        self._config = config or TelemetryConfig()
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._running = False

        # Initialise data-source adapters
        self._dbus = _DBusSource() if "dbus" in self._config.data_sources else None
        self._rest = (
            _RestAPISource() if "rest_api" in self._config.data_sources else None
        )
        self._mfs = (
            _MurphyFSSource() if "murphyfs" in self._config.data_sources else None
        )
        self._cg = (
            _CGroupSource() if "cgroup" in self._config.data_sources else None
        )

    # ── constructors ──────────────────────────────────────────────────
    @classmethod
    def from_config(cls, path: str | Path = _DEFAULT_CONFIG_PATH) -> TelemetryExporter:
        """Create an exporter from a YAML configuration file."""
        cfg = TelemetryConfig.from_file(Path(path))
        return cls(cfg)

    # ── public API ────────────────────────────────────────────────────
    @property
    def config(self) -> TelemetryConfig:
        return self._config

    def collect_once(self) -> str:
        """Run one collection cycle and return the exposition text.

        Also writes the text to the configured output path atomically.
        """
        families = self._collect_all()
        text = self._render(families)
        self._write_atomic(text)
        return text

    def run_loop(self) -> None:
        """Block forever, collecting at the configured interval."""
        self._running = True
        _LOG.info(
            "Telemetry exporter started (interval=%ds, output=%s)",
            self._config.interval_seconds,
            self._config.output_path,
        )
        while self._running:
            try:
                self.collect_once()
            except Exception as exc:
                # MURPHY-TELEMETRY-ERR-010: unexpected fatal error
                _LOG.error("MURPHY-TELEMETRY-ERR-010: Collection cycle failed: %s", exc)
            time.sleep(self._config.interval_seconds)

    def stop(self) -> None:
        """Signal the run-loop to stop."""
        self._running = False

    # ── fallback helper ───────────────────────────────────────────────
    def _query_chain(self, dbus_method: str, rest_endpoint: str,
                     mfs_path: str) -> Optional[Dict[str, Any]]:
        """Try each data source in priority order, return first success."""
        if self._dbus:
            result = self._dbus.query(dbus_method)
            if result is not None:
                return result
        if self._rest:
            result = self._rest.query(rest_endpoint)
            if result is not None:
                return result
        if self._mfs:
            result = self._mfs.read_json(mfs_path)
            if result is not None:
                return result
        return None

    # ── metric collectors ─────────────────────────────────────────────
    def _collect_all(self) -> List[_MetricFamily]:
        """Collect every enabled metric family."""
        families: List[_MetricFamily] = []
        collectors = [
            (self._config.confidence, self._collect_confidence),
            (self._config.gates, self._collect_gates),
            (self._config.swarm, self._collect_swarm),
            (self._config.forge, self._collect_forge),
            (self._config.llm, self._collect_llm),
            (self._config.security, self._collect_security),
            (self._config.system, self._collect_system),
            (self._config.backup, self._collect_backup),
            (self._config.cgroup, self._collect_cgroup),
        ]
        for enabled, fn in collectors:
            if not enabled:
                continue
            try:
                families.extend(fn())
            except Exception as exc:
                # MURPHY-TELEMETRY-ERR-008: metric collection error
                _LOG.warning(
                    "MURPHY-TELEMETRY-ERR-008: Collector %s failed: %s",
                    fn.__name__, exc,
                )
        return families

    # -- Confidence -----------------------------------------------------
    def _collect_confidence(self) -> List[_MetricFamily]:
        data = self._query_chain("GetConfidence", "confidence", "confidence.json")
        score = _safe_float((data or {}).get("score"))
        changes = _safe_float((data or {}).get("changes_total"))
        return [
            _MetricFamily(
                name="murphy_confidence_score",
                help_text="Current Murphy confidence score (0-1).",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_confidence_score", value=score)],
            ),
            _MetricFamily(
                name="murphy_confidence_changes_total",
                help_text="Total number of confidence-score changes.",
                metric_type="counter",
                samples=[_MetricLine(name="murphy_confidence_changes_total", value=changes)],
            ),
        ]

    # -- Gates ----------------------------------------------------------
    def _collect_gates(self) -> List[_MetricFamily]:
        data = self._query_chain("GetGates", "gates", "gates.json") or {}
        gate_names = data.get("gates", {})
        status_samples: List[_MetricLine] = []
        decision_samples: List[_MetricLine] = []
        for gate, info in gate_names.items():
            active = 1.0 if info.get("active", False) else 0.0
            status_samples.append(
                _MetricLine(name="murphy_gate_status", labels={"gate": gate}, value=active),
            )
            for action, count in info.get("decisions", {}).items():
                decision_samples.append(
                    _MetricLine(
                        name="murphy_gate_decisions_total",
                        labels={"gate": gate, "action": action},
                        value=_safe_float(count),
                    ),
                )
        # Ensure EXECUTIVE gate is always present
        if not any(s.labels.get("gate") == "EXECUTIVE" for s in status_samples):
            status_samples.append(
                _MetricLine(name="murphy_gate_status", labels={"gate": "EXECUTIVE"}, value=0),
            )
        return [
            _MetricFamily(
                name="murphy_gate_status",
                help_text="Gate status (1=active, 0=inactive).",
                metric_type="gauge",
                samples=status_samples,
            ),
            _MetricFamily(
                name="murphy_gate_decisions_total",
                help_text="Total gate decisions by gate and action.",
                metric_type="counter",
                samples=decision_samples,
            ),
        ]

    # -- Swarm ----------------------------------------------------------
    def _collect_swarm(self) -> List[_MetricFamily]:
        data = self._query_chain("GetSwarm", "swarm", "swarm.json") or {}
        active = _safe_float(data.get("agents_active"))
        tasks = data.get("tasks", {})
        task_samples = [
            _MetricLine(
                name="murphy_swarm_tasks_total",
                labels={"status": status},
                value=_safe_float(count),
            )
            for status, count in tasks.items()
        ]
        mem_samples = [
            _MetricLine(
                name="murphy_swarm_agent_memory_bytes",
                labels={"agent_id": aid},
                value=_safe_float(mem),
            )
            for aid, mem in data.get("agent_memory", {}).items()
        ]
        return [
            _MetricFamily(
                name="murphy_swarm_agents_active",
                help_text="Number of active swarm agents.",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_swarm_agents_active", value=active)],
            ),
            _MetricFamily(
                name="murphy_swarm_tasks_total",
                help_text="Total swarm tasks by status.",
                metric_type="counter",
                samples=task_samples,
            ),
            _MetricFamily(
                name="murphy_swarm_agent_memory_bytes",
                help_text="Memory usage per swarm agent in bytes.",
                metric_type="gauge",
                samples=mem_samples,
            ),
        ]

    # -- Forge ----------------------------------------------------------
    def _collect_forge(self) -> List[_MetricFamily]:
        data = self._query_chain("GetForge", "forge", "forge.json") or {}
        build_samples = [
            _MetricLine(
                name="murphy_forge_builds_total",
                labels={"status": status},
                value=_safe_float(count),
            )
            for status, count in data.get("builds", {}).items()
        ]
        # Histogram: reconstruct bucket counts from the data source
        hist_data = data.get("duration_histogram", {})
        bucket_samples: List[_MetricLine] = []
        cumulative = 0.0
        for bound in _FORGE_DURATION_BUCKETS:
            key = "+Inf" if math.isinf(bound) else str(bound)
            cumulative += _safe_float(hist_data.get(key))
            le_str = "+Inf" if math.isinf(bound) else f"{bound:g}"
            bucket_samples.append(
                _MetricLine(
                    name="murphy_forge_duration_seconds_bucket",
                    labels={"le": le_str},
                    value=cumulative,
                ),
            )
        total_sum = _safe_float(hist_data.get("sum"))
        total_count = _safe_float(hist_data.get("count", cumulative))
        bucket_samples.append(
            _MetricLine(name="murphy_forge_duration_seconds_sum", value=total_sum),
        )
        bucket_samples.append(
            _MetricLine(name="murphy_forge_duration_seconds_count", value=total_count),
        )
        return [
            _MetricFamily(
                name="murphy_forge_builds_total",
                help_text="Total forge builds by status.",
                metric_type="counter",
                samples=build_samples,
            ),
            _MetricFamily(
                name="murphy_forge_duration_seconds",
                help_text="Forge build duration distribution in seconds.",
                metric_type="histogram",
                samples=bucket_samples,
            ),
        ]

    # -- LLM ------------------------------------------------------------
    def _collect_llm(self) -> List[_MetricFamily]:
        data = self._query_chain("GetLLM", "llm/metrics", "llm.json") or {}

        req_samples = [
            _MetricLine(
                name="murphy_llm_requests_total",
                labels={"provider": p, "model": m},
                value=_safe_float(c),
            )
            for p, models in data.get("requests", {}).items()
            for m, c in (models.items() if isinstance(models, dict) else [(p, models)])
        ]
        tok_samples = [
            _MetricLine(
                name="murphy_llm_tokens_total",
                labels={"provider": p, "direction": d},
                value=_safe_float(c),
            )
            for p, dirs in data.get("tokens", {}).items()
            for d, c in dirs.items()
        ]
        lat_samples: List[_MetricLine] = []
        for p, stats in data.get("latency", {}).items():
            lat_samples.append(
                _MetricLine(
                    name="murphy_llm_latency_seconds_sum",
                    labels={"provider": p},
                    value=_safe_float(stats.get("sum")),
                ),
            )
            lat_samples.append(
                _MetricLine(
                    name="murphy_llm_latency_seconds_count",
                    labels={"provider": p},
                    value=_safe_float(stats.get("count")),
                ),
            )
        cost_samples = [
            _MetricLine(
                name="murphy_llm_cost_usd_total",
                labels={"provider": p},
                value=_safe_float(c),
            )
            for p, c in data.get("cost_usd", {}).items()
        ]
        err_samples = [
            _MetricLine(
                name="murphy_llm_errors_total",
                labels={"provider": p},
                value=_safe_float(c),
            )
            for p, c in data.get("errors", {}).items()
        ]
        return [
            _MetricFamily(
                name="murphy_llm_requests_total",
                help_text="Total LLM requests by provider and model.",
                metric_type="counter",
                samples=req_samples,
            ),
            _MetricFamily(
                name="murphy_llm_tokens_total",
                help_text="Total LLM tokens by provider and direction (input/output).",
                metric_type="counter",
                samples=tok_samples,
            ),
            _MetricFamily(
                name="murphy_llm_latency_seconds",
                help_text="LLM request latency distribution by provider.",
                metric_type="summary",
                samples=lat_samples,
            ),
            _MetricFamily(
                name="murphy_llm_cost_usd_total",
                help_text="Cumulative LLM cost in USD by provider.",
                metric_type="counter",
                samples=cost_samples,
            ),
            _MetricFamily(
                name="murphy_llm_errors_total",
                help_text="Total LLM errors by provider.",
                metric_type="counter",
                samples=err_samples,
            ),
        ]

    # -- Security -------------------------------------------------------
    def _collect_security(self) -> List[_MetricFamily]:
        data = self._query_chain("GetSecurity", "security", "security.json") or {}
        posture = _safe_float(data.get("posture_score"))
        threat_samples = [
            _MetricLine(
                name="murphy_security_threats_total",
                labels={"engine": engine},
                value=_safe_float(count),
            )
            for engine, count in data.get("threats", {}).items()
        ]
        encryptions = _safe_float(data.get("encryptions_total"))
        return [
            _MetricFamily(
                name="murphy_security_posture_score",
                help_text="Current security posture score (0-100).",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_security_posture_score", value=posture)],
            ),
            _MetricFamily(
                name="murphy_security_threats_total",
                help_text="Total security threats detected by engine.",
                metric_type="counter",
                samples=threat_samples,
            ),
            _MetricFamily(
                name="murphy_security_encryptions_total",
                help_text="Total encryption operations performed.",
                metric_type="counter",
                samples=[_MetricLine(name="murphy_security_encryptions_total", value=encryptions)],
            ),
        ]

    # -- System ---------------------------------------------------------
    def _collect_system(self) -> List[_MetricFamily]:
        data = self._query_chain("GetSystem", "system/health", "system.json") or {}
        uptime = _safe_float(data.get("uptime_seconds", time.monotonic() - self._start_time))
        health = 1.0 if data.get("healthy", False) else 0.0
        event_samples = [
            _MetricLine(
                name="murphy_event_backbone_events_total",
                labels={"type": etype},
                value=_safe_float(count),
            )
            for etype, count in data.get("events", {}).items()
        ]
        return [
            _MetricFamily(
                name="murphy_uptime_seconds",
                help_text="Murphy system uptime in seconds.",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_uptime_seconds", value=uptime)],
            ),
            _MetricFamily(
                name="murphy_health_status",
                help_text="Murphy system health (1=healthy, 0=unhealthy).",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_health_status", value=health)],
            ),
            _MetricFamily(
                name="murphy_event_backbone_events_total",
                help_text="Total events processed by the event backbone.",
                metric_type="counter",
                samples=event_samples,
            ),
        ]

    # -- Backup ---------------------------------------------------------
    def _collect_backup(self) -> List[_MetricFamily]:
        data = self._query_chain("GetBackup", "backup/status", "backup.json") or {}
        last_ts = _safe_float(data.get("last_success_timestamp"))
        size = _safe_float(data.get("size_bytes"))
        return [
            _MetricFamily(
                name="murphy_backup_last_success_timestamp",
                help_text="Unix timestamp of the last successful backup.",
                metric_type="gauge",
                samples=[
                    _MetricLine(name="murphy_backup_last_success_timestamp", value=last_ts),
                ],
            ),
            _MetricFamily(
                name="murphy_backup_size_bytes",
                help_text="Size of the last successful backup in bytes.",
                metric_type="gauge",
                samples=[_MetricLine(name="murphy_backup_size_bytes", value=size)],
            ),
        ]

    # -- CGroup ---------------------------------------------------------
    def _collect_cgroup(self) -> List[_MetricFamily]:
        if not self._cg:
            return []
        mem_samples: List[_MetricLine] = []
        cpu_samples: List[_MetricLine] = []
        slice_name = "murphy.slice"

        mem_val = self._cg.memory_current(slice_name)
        if mem_val is not None:
            mem_samples.append(
                _MetricLine(
                    name="murphy_cgroup_memory_usage_bytes",
                    labels={"slice": slice_name},
                    value=mem_val,
                ),
            )
        cpu_val = self._cg.cpu_usage(slice_name)
        if cpu_val is not None:
            cpu_samples.append(
                _MetricLine(
                    name="murphy_cgroup_cpu_usage_seconds",
                    labels={"slice": slice_name},
                    value=cpu_val,
                ),
            )
        # Also check child slices
        for child in self._cg.child_slices():
            child_root = Path(self._cg._root) / child
            child_cg = _CGroupSource(str(child_root))
            child_mem = child_cg.memory_current(child)
            if child_mem is not None:
                mem_samples.append(
                    _MetricLine(
                        name="murphy_cgroup_memory_usage_bytes",
                        labels={"slice": child},
                        value=child_mem,
                    ),
                )
            child_cpu = child_cg.cpu_usage(child)
            if child_cpu is not None:
                cpu_samples.append(
                    _MetricLine(
                        name="murphy_cgroup_cpu_usage_seconds",
                        labels={"slice": child},
                        value=child_cpu,
                    ),
                )
        return [
            _MetricFamily(
                name="murphy_cgroup_memory_usage_bytes",
                help_text="cgroup memory usage for Murphy slices in bytes.",
                metric_type="gauge",
                samples=mem_samples,
            ),
            _MetricFamily(
                name="murphy_cgroup_cpu_usage_seconds",
                help_text="Cumulative cgroup CPU usage for Murphy slices in seconds.",
                metric_type="counter",
                samples=cpu_samples,
            ),
        ]

    # ── rendering ─────────────────────────────────────────────────────
    @staticmethod
    def _render(families: List[_MetricFamily]) -> str:
        blocks: List[str] = []
        for fam in families:
            if fam.samples:
                blocks.append(fam.render())
        return "\n".join(blocks) + "\n"

    # ── atomic write ──────────────────────────────────────────────────
    def _write_atomic(self, text: str) -> None:
        """Write *text* to the output path atomically (tmp + rename)."""
        out = self._config.output_path
        tmp = out.with_suffix(".prom.tmp")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # MURPHY-TELEMETRY-ERR-003: output path not writable
            _LOG.error("MURPHY-TELEMETRY-ERR-003: Cannot create output dir %s: %s", out.parent, exc)
            return
        try:
            tmp.write_text(text, encoding="utf-8")
        except OSError as exc:
            # MURPHY-TELEMETRY-ERR-003: output path not writable
            _LOG.error("MURPHY-TELEMETRY-ERR-003: Cannot write temp file %s: %s", tmp, exc)
            return
        try:
            os.replace(str(tmp), str(out))
        except OSError as exc:
            # MURPHY-TELEMETRY-ERR-009: atomic rename failed
            _LOG.error("MURPHY-TELEMETRY-ERR-009: Atomic rename %s -> %s failed: %s", tmp, out, exc)


# ── CLI entry-point ───────────────────────────────────────────────────────
def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry-point for ``murphy-telemetry-export``."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Murphy Telemetry → Prometheus textfile exporter",
    )
    parser.add_argument(
        "-c", "--config",
        default=str(_DEFAULT_CONFIG_PATH),
        help="Path to telemetry.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Collect once and exit (for systemd timer mode).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    exporter = TelemetryExporter.from_config(args.config)
    if not exporter.config.enabled:
        _LOG.info("Telemetry export is disabled in configuration — exiting.")
        return 0

    if args.once:
        exporter.collect_once()
        return 0

    try:
        exporter.run_loop()
    except KeyboardInterrupt:
        _LOG.info("Interrupted — shutting down.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
