# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""MurphyOS module lifecycle manager.

Provides systemd-based module instance management for Murphy System modules.
Each module runs as a systemd transient scope under ``murphy-modules.slice``,
with health monitoring, auto-restart with exponential backoff, and resource
governance via cgroup integration.

Corresponds to the higher-level Python modules:

* ``module_instance_manager.py`` — instance spawn / despawn
* ``module_loader.py``          — module startup orchestration
* ``module_manager.py``         — coupling / decoupling registry
* ``module_registry.py``        — installed module tracking
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("murphy.module_lifecycle")

_DEFAULT_REGISTRY_PATH = Path("/var/lib/murphy/modules/registry.json")
_DEFAULT_MODULE_SLICE = "murphy-modules.slice"
_DEFAULT_MEMORY_MAX = "256M"
_DEFAULT_CPU_WEIGHT = 100
_DEFAULT_RESTART_MAX = 5
_DEFAULT_RESTART_BACKOFF_MAX = 60
_DEFAULT_HEALTH_INTERVAL = 30
_DEFAULT_HEALTH_TIMEOUT = 5
_DEFAULT_UNHEALTHY_THRESHOLD = 3

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

MURPHY_MODULE_ERR_001 = "MURPHY-MODULE-ERR-001"  # registry load failure
MURPHY_MODULE_ERR_002 = "MURPHY-MODULE-ERR-002"  # registry save failure
MURPHY_MODULE_ERR_003 = "MURPHY-MODULE-ERR-003"  # module not found
MURPHY_MODULE_ERR_004 = "MURPHY-MODULE-ERR-004"  # module already registered
MURPHY_MODULE_ERR_005 = "MURPHY-MODULE-ERR-005"  # systemd-run start failed
MURPHY_MODULE_ERR_006 = "MURPHY-MODULE-ERR-006"  # systemctl stop failed
MURPHY_MODULE_ERR_007 = "MURPHY-MODULE-ERR-007"  # status query failed
MURPHY_MODULE_ERR_008 = "MURPHY-MODULE-ERR-008"  # health check failed
MURPHY_MODULE_ERR_009 = "MURPHY-MODULE-ERR-009"  # log retrieval failed
MURPHY_MODULE_ERR_010 = "MURPHY-MODULE-ERR-010"  # configuration load error
MURPHY_MODULE_ERR_011 = "MURPHY-MODULE-ERR-011"  # restart limit exceeded
MURPHY_MODULE_ERR_012 = "MURPHY-MODULE-ERR-012"  # invalid module specification

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ModuleLifecycleError(Exception):
    """Base exception for module lifecycle operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ModuleRecord:
    """Persistent record for a registered module."""

    name: str
    version: str
    entry_point: str
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    memory_max: str = _DEFAULT_MEMORY_MAX
    cpu_weight: int = _DEFAULT_CPU_WEIGHT
    registered_at: str = ""
    crash_count: int = 0
    last_crash_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ModuleRecord:
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclasses.dataclass
class ModuleStatus:
    """Runtime status snapshot for a module."""

    name: str
    active_state: str = "unknown"
    sub_state: str = "unknown"
    pid: int = 0
    memory_current: int = 0
    healthy: bool = False
    instance_id: str = ""


# ---------------------------------------------------------------------------
# YAML helper (no external dep required — fallback to simple parser)
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML configuration file.

    Attempts PyYAML first; falls back to a minimal safe subset parser that
    handles the flat-key structure used by Murphy config files.
    """
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text) or {}  # type: ignore[no-any-return]
    except ImportError:
        pass
    # Minimal fallback — handles only simple key: value lines
    result: Dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(stripped)
        while indent <= stack[-1][0]:
            stack.pop()
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                # Attempt numeric / boolean coercion
                if val.lower() in ("true", "yes"):
                    stack[-1][1][key] = True
                elif val.lower() in ("false", "no"):
                    stack[-1][1][key] = False
                else:
                    try:
                        stack[-1][1][key] = int(val)
                    except ValueError:
                        stack[-1][1][key] = val
            else:
                child: Dict[str, Any] = {}
                stack[-1][1][key] = child
                stack.append((indent, child))
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _scope_name(module_name: str, instance_id: str = "") -> str:
    """Derive the systemd scope unit name for a module."""
    suffix = f"-{instance_id}" if instance_id else ""
    return f"murphy-module-{module_name}{suffix}.scope"


def _unit_name(module_name: str) -> str:
    """Derive a generic systemd unit name for log/status queries."""
    return f"murphy-module-{module_name}*"


def _run(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, returning the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# ModuleLifecycleManager
# ---------------------------------------------------------------------------


class ModuleLifecycleManager:
    """Manage Murphy System module instances as systemd transient units.

    Parameters
    ----------
    registry_path:
        Path to the JSON file used for persistent module registry.
    module_slice:
        systemd slice under which all module scopes are created.
    defaults:
        Dict of default resource limits and restart policy values.
    health_check:
        Dict of health-check configuration (interval, timeout, threshold).
    """

    def __init__(
        self,
        registry_path: Path | str = _DEFAULT_REGISTRY_PATH,
        module_slice: str = _DEFAULT_MODULE_SLICE,
        defaults: Optional[Dict[str, Any]] = None,
        health_check: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._registry_path = Path(registry_path)
        self._module_slice = module_slice
        self._lock = threading.Lock()

        defs = defaults or {}
        self._memory_max: str = str(defs.get("memory_max", _DEFAULT_MEMORY_MAX))
        self._cpu_weight: int = int(defs.get("cpu_weight", _DEFAULT_CPU_WEIGHT))
        self._restart_max: int = int(defs.get("restart_max", _DEFAULT_RESTART_MAX))
        self._restart_backoff_max: int = int(
            defs.get("restart_backoff_max", _DEFAULT_RESTART_BACKOFF_MAX)
        )

        hc = health_check or {}
        self._health_interval: int = int(
            hc.get("interval_seconds", _DEFAULT_HEALTH_INTERVAL)
        )
        self._health_timeout: int = int(
            hc.get("timeout_seconds", _DEFAULT_HEALTH_TIMEOUT)
        )
        self._unhealthy_threshold: int = int(
            hc.get("unhealthy_threshold", _DEFAULT_UNHEALTHY_THRESHOLD)
        )

        self._modules: Dict[str, ModuleRecord] = {}
        self._running: bool = False
        self._health_thread: Optional[threading.Thread] = None
        self._unhealthy_counts: Dict[str, int] = {}

        self._load_registry()

    # ------------------------------------------------------------------
    # Registry persistence
    # ------------------------------------------------------------------

    def _load_registry(self) -> None:
        """Load the module registry from disk."""
        if not self._registry_path.exists():
            _LOG.info("No existing registry at %s — starting empty", self._registry_path)
            return
        try:
            data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            for name, rec in data.items():
                self._modules[name] = ModuleRecord.from_dict(rec)
            _LOG.info("Loaded %d module(s) from registry", len(self._modules))
        except Exception as exc:
            # MURPHY-MODULE-ERR-001: registry load failure
            _LOG.error(
                "[%s] Failed to load registry %s: %s",
                MURPHY_MODULE_ERR_001,
                self._registry_path,
                exc,
            )

    def _save_registry(self) -> None:
        """Atomically persist the module registry to disk."""
        try:
            self._registry_path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {n: r.to_dict() for n, r in self._modules.items()},
                indent=2,
                sort_keys=True,
            )
            tmp_path = self._registry_path.with_suffix(".tmp")
            tmp_path.write_text(payload, encoding="utf-8")
            tmp_path.replace(self._registry_path)
            _LOG.debug("Registry saved (%d modules)", len(self._modules))
        except Exception as exc:
            # MURPHY-MODULE-ERR-002: registry save failure
            _LOG.error(
                "[%s] Failed to save registry to %s: %s",
                MURPHY_MODULE_ERR_002,
                self._registry_path,
                exc,
            )

    # ------------------------------------------------------------------
    # Module registry operations
    # ------------------------------------------------------------------

    def register_module(
        self,
        name: str,
        version: str,
        entry_point: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> ModuleRecord:
        """Register a module in the lifecycle manager.

        Raises
        ------
        ModuleLifecycleError
            If the module is already registered (ERR-004) or the
            specification is invalid (ERR-012).
        """
        if not name or not version or not entry_point:
            # MURPHY-MODULE-ERR-012: invalid module specification
            _LOG.error(
                "[%s] Invalid module spec: name=%r version=%r entry=%r",
                MURPHY_MODULE_ERR_012,
                name,
                version,
                entry_point,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_012,
                "Module name, version, and entry_point are required",
            )

        with self._lock:
            if name in self._modules:
                # MURPHY-MODULE-ERR-004: module already registered
                _LOG.error(
                    "[%s] Module %r already registered", MURPHY_MODULE_ERR_004, name
                )
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_004,
                    f"Module '{name}' is already registered",
                )
            record = ModuleRecord(
                name=name,
                version=version,
                entry_point=entry_point,
                config=config or {},
                memory_max=self._memory_max,
                cpu_weight=self._cpu_weight,
                registered_at=_utcnow_iso(),
            )
            self._modules[name] = record
            self._save_registry()
            _LOG.info("Registered module %r v%s", name, version)
            return record

    def unregister_module(self, name: str) -> None:
        """Remove a module from the registry.

        Raises
        ------
        ModuleLifecycleError
            If the module is not found (ERR-003).
        """
        with self._lock:
            if name not in self._modules:
                # MURPHY-MODULE-ERR-003: module not found
                _LOG.error(
                    "[%s] Cannot unregister unknown module %r",
                    MURPHY_MODULE_ERR_003,
                    name,
                )
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_003,
                    f"Module '{name}' is not registered",
                )
            del self._modules[name]
            self._unhealthy_counts.pop(name, None)
            self._save_registry()
            _LOG.info("Unregistered module %r", name)

    def list_modules(self) -> List[Dict[str, Any]]:
        """Return a list of all registered modules with current status."""
        results: List[Dict[str, Any]] = []
        with self._lock:
            names = list(self._modules.keys())
        for name in names:
            try:
                status = self.get_module_status(name)
                with self._lock:
                    rec = self._modules.get(name)
                if rec is None:
                    continue
                entry = rec.to_dict()
                entry["active_state"] = status.active_state
                entry["pid"] = status.pid
                entry["healthy"] = status.healthy
                results.append(entry)
            except ModuleLifecycleError:
                with self._lock:
                    rec = self._modules.get(name)
                if rec:
                    entry = rec.to_dict()
                    entry["active_state"] = "unknown"
                    entry["pid"] = 0
                    entry["healthy"] = False
                    results.append(entry)
        return results

    def get_module(self, name: str) -> Dict[str, Any]:
        """Return full details for a single module including runtime status.

        Raises
        ------
        ModuleLifecycleError
            If the module is not found (ERR-003).
        """
        with self._lock:
            rec = self._modules.get(name)
        if rec is None:
            # MURPHY-MODULE-ERR-003: module not found
            _LOG.error("[%s] Module %r not found", MURPHY_MODULE_ERR_003, name)
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_003, f"Module '{name}' is not registered"
            )
        status = self.get_module_status(name)
        detail = rec.to_dict()
        detail["active_state"] = status.active_state
        detail["sub_state"] = status.sub_state
        detail["pid"] = status.pid
        detail["memory_current"] = status.memory_current
        detail["healthy"] = status.healthy
        detail["instance_id"] = status.instance_id
        return detail

    # ------------------------------------------------------------------
    # Lifecycle operations
    # ------------------------------------------------------------------

    def start_module(self, name: str, instance_id: str = "") -> str:
        """Start a module as a systemd transient scope.

        Parameters
        ----------
        name:
            Registered module name.
        instance_id:
            Optional instance identifier.  A default is generated if empty.

        Returns
        -------
        str
            The systemd scope unit name created.

        Raises
        ------
        ModuleLifecycleError
            ERR-003 if module not registered, ERR-005 if systemd-run fails.
        """
        with self._lock:
            rec = self._modules.get(name)
        if rec is None:
            # MURPHY-MODULE-ERR-003: module not found
            _LOG.error("[%s] Cannot start unregistered module %r", MURPHY_MODULE_ERR_003, name)
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_003, f"Module '{name}' is not registered"
            )

        if not instance_id:
            instance_id = f"{int(time.time()):x}"

        scope = _scope_name(name, instance_id)
        slice_path = f"{self._module_slice}/murphy-module-{name}.scope"

        cmd = [
            "systemd-run",
            "--scope",
            f"--unit={scope}",
            f"--slice={self._module_slice}",
            f"--property=MemoryMax={rec.memory_max}",
            f"--property=CPUWeight={rec.cpu_weight}",
            "--collect",
            "--",
            rec.entry_point,
        ]

        try:
            result = _run(cmd, timeout=30)
            if result.returncode != 0:
                # MURPHY-MODULE-ERR-005: systemd-run start failed
                _LOG.error(
                    "[%s] systemd-run failed for %r (rc=%d): %s",
                    MURPHY_MODULE_ERR_005,
                    name,
                    result.returncode,
                    result.stderr.strip(),
                )
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_005,
                    f"systemd-run failed for '{name}': {result.stderr.strip()}",
                )
            _LOG.info("Started module %r as %s (slice=%s)", name, scope, slice_path)
            return scope
        except subprocess.TimeoutExpired as exc:
            # MURPHY-MODULE-ERR-005: systemd-run start failed
            _LOG.error(
                "[%s] systemd-run timed out for module %r: %s",
                MURPHY_MODULE_ERR_005,
                name,
                exc,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_005,
                f"systemd-run timed out for '{name}'",
            ) from exc
        except FileNotFoundError as exc:
            # MURPHY-MODULE-ERR-005: systemd-run start failed
            _LOG.error(
                "[%s] systemd-run binary not found: %s",
                MURPHY_MODULE_ERR_005,
                exc,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_005,
                "systemd-run binary not found",
            ) from exc

    def stop_module(self, name: str, instance_id: str = "") -> None:
        """Stop a running module's systemd transient unit.

        Raises
        ------
        ModuleLifecycleError
            ERR-003 if module not registered, ERR-006 if systemctl stop fails.
        """
        with self._lock:
            if name not in self._modules:
                # MURPHY-MODULE-ERR-003: module not found
                _LOG.error("[%s] Cannot stop unregistered module %r", MURPHY_MODULE_ERR_003, name)
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_003, f"Module '{name}' is not registered"
                )

        scope = _scope_name(name, instance_id)
        cmd = ["systemctl", "stop", scope]

        try:
            result = _run(cmd, timeout=30)
            if result.returncode != 0:
                # MURPHY-MODULE-ERR-006: systemctl stop failed
                _LOG.error(
                    "[%s] systemctl stop failed for %r (rc=%d): %s",
                    MURPHY_MODULE_ERR_006,
                    scope,
                    result.returncode,
                    result.stderr.strip(),
                )
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_006,
                    f"Failed to stop '{scope}': {result.stderr.strip()}",
                )
            _LOG.info("Stopped module %r (scope=%s)", name, scope)
        except subprocess.TimeoutExpired as exc:
            # MURPHY-MODULE-ERR-006: systemctl stop failed
            _LOG.error(
                "[%s] systemctl stop timed out for %r: %s",
                MURPHY_MODULE_ERR_006,
                scope,
                exc,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_006,
                f"Timed out stopping '{scope}'",
            ) from exc

    def restart_module(self, name: str, instance_id: str = "") -> str:
        """Restart a module by stopping and starting it.

        Returns the new scope unit name.
        """
        try:
            self.stop_module(name, instance_id)
        except ModuleLifecycleError as exc:
            if exc.code == MURPHY_MODULE_ERR_003:
                raise
            _LOG.warning("Stop failed during restart of %r (continuing): %s", name, exc)
        return self.start_module(name, instance_id)

    def get_module_status(self, name: str) -> ModuleStatus:
        """Query systemd for a module's current runtime status.

        Raises
        ------
        ModuleLifecycleError
            ERR-003 if not registered, ERR-007 if the query fails.
        """
        with self._lock:
            if name not in self._modules:
                # MURPHY-MODULE-ERR-003: module not found
                _LOG.error("[%s] Cannot query status of unregistered module %r", MURPHY_MODULE_ERR_003, name)
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_003, f"Module '{name}' is not registered"
                )

        scope_pattern = f"murphy-module-{name}*.scope"
        cmd = [
            "systemctl",
            "show",
            "--property=ActiveState,SubState,MainPID,MemoryCurrent,Id",
            scope_pattern,
        ]

        try:
            result = _run(cmd, timeout=10)
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            # MURPHY-MODULE-ERR-007: status query failed
            _LOG.error(
                "[%s] Status query failed for %r: %s",
                MURPHY_MODULE_ERR_007,
                name,
                exc,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_007,
                f"Status query failed for '{name}': {exc}",
            ) from exc

        status = ModuleStatus(name=name)
        if result.returncode != 0:
            # MURPHY-MODULE-ERR-007: status query failed
            _LOG.warning(
                "[%s] systemctl show returned rc=%d for %r",
                MURPHY_MODULE_ERR_007,
                result.returncode,
                name,
            )
            return status

        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "ActiveState":
                status.active_state = val
            elif key == "SubState":
                status.sub_state = val
            elif key == "MainPID":
                try:
                    status.pid = int(val)
                except ValueError:
                    pass
            elif key == "MemoryCurrent":
                try:
                    status.memory_current = int(val)
                except ValueError:
                    pass
            elif key == "Id":
                status.instance_id = val

        status.healthy = status.active_state == "active"
        return status

    # ------------------------------------------------------------------
    # Health monitoring
    # ------------------------------------------------------------------

    def check_module_health(self, name: str) -> bool:
        """Check a module's health via HTTP probe or process liveness.

        Returns ``True`` if healthy, ``False`` otherwise.
        """
        with self._lock:
            rec = self._modules.get(name)
        if rec is None:
            # MURPHY-MODULE-ERR-003: module not found
            _LOG.error("[%s] Cannot health-check unregistered module %r", MURPHY_MODULE_ERR_003, name)
            return False

        health_url = rec.config.get("health_url")
        if health_url:
            return self._http_health_check(name, health_url)

        return self._process_liveness_check(name)

    def _http_health_check(self, name: str, url: str) -> bool:
        """Perform an HTTP GET health check."""
        try:
            import urllib.request

            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self._health_timeout) as resp:
                healthy = resp.status == 200
                _LOG.debug("HTTP health check for %r: status=%d", name, resp.status)
                return healthy
        except Exception as exc:
            # MURPHY-MODULE-ERR-008: health check failed
            _LOG.warning(
                "[%s] HTTP health check failed for %r: %s",
                MURPHY_MODULE_ERR_008,
                name,
                exc,
            )
            return False

    def _process_liveness_check(self, name: str) -> bool:
        """Check whether the module process is alive via systemd state."""
        try:
            status = self.get_module_status(name)
            alive = status.active_state == "active"
            _LOG.debug(
                "Process liveness for %r: active_state=%s alive=%s",
                name,
                status.active_state,
                alive,
            )
            return alive
        except ModuleLifecycleError as exc:
            # MURPHY-MODULE-ERR-008: health check failed
            _LOG.warning(
                "[%s] Liveness check failed for %r: %s",
                MURPHY_MODULE_ERR_008,
                name,
                exc,
            )
            return False

    def get_module_logs(self, name: str, lines: int = 50) -> str:
        """Retrieve recent journal logs for a module.

        Raises
        ------
        ModuleLifecycleError
            ERR-009 if log retrieval fails.
        """
        unit = f"murphy-module-{name}*"
        cmd = [
            "journalctl",
            f"--unit={unit}",
            "--no-pager",
            f"--lines={lines}",
            "--output=short-iso",
        ]

        try:
            result = _run(cmd, timeout=10)
            if result.returncode != 0:
                # MURPHY-MODULE-ERR-009: log retrieval failed
                _LOG.error(
                    "[%s] journalctl failed for %r (rc=%d): %s",
                    MURPHY_MODULE_ERR_009,
                    name,
                    result.returncode,
                    result.stderr.strip(),
                )
                raise ModuleLifecycleError(
                    MURPHY_MODULE_ERR_009,
                    f"Log retrieval failed for '{name}': {result.stderr.strip()}",
                )
            return result.stdout
        except subprocess.TimeoutExpired as exc:
            # MURPHY-MODULE-ERR-009: log retrieval failed
            _LOG.error(
                "[%s] journalctl timed out for %r: %s",
                MURPHY_MODULE_ERR_009,
                name,
                exc,
            )
            raise ModuleLifecycleError(
                MURPHY_MODULE_ERR_009,
                f"Log retrieval timed out for '{name}'",
            ) from exc

    # ------------------------------------------------------------------
    # Auto-restart with exponential backoff
    # ------------------------------------------------------------------

    def _handle_module_crash(self, name: str) -> None:
        """Track a module crash and attempt auto-restart with backoff."""
        with self._lock:
            rec = self._modules.get(name)
            if rec is None:
                return
            rec.crash_count += 1
            rec.last_crash_ts = time.time()
            crash_count = rec.crash_count
            self._save_registry()

        if crash_count > self._restart_max:
            # MURPHY-MODULE-ERR-011: restart limit exceeded
            _LOG.error(
                "[%s] Module %r exceeded max restarts (%d/%d)",
                MURPHY_MODULE_ERR_011,
                name,
                crash_count,
                self._restart_max,
            )
            return

        backoff = min(2 ** (crash_count - 1), self._restart_backoff_max)
        _LOG.info(
            "Module %r crashed (%d/%d) — restarting in %ds",
            name,
            crash_count,
            self._restart_max,
            backoff,
        )
        time.sleep(backoff)

        try:
            self.start_module(name)
            _LOG.info("Auto-restarted module %r after crash #%d", name, crash_count)
        except ModuleLifecycleError as exc:
            # MURPHY-MODULE-ERR-005: systemd-run start failed
            _LOG.error(
                "[%s] Auto-restart failed for %r: %s",
                MURPHY_MODULE_ERR_005,
                name,
                exc,
            )

    def _reset_crash_count(self, name: str) -> None:
        """Reset crash counter after a module has been healthy for a while."""
        with self._lock:
            rec = self._modules.get(name)
            if rec and rec.crash_count > 0:
                rec.crash_count = 0
                self._save_registry()
                _LOG.debug("Reset crash count for module %r", name)

    # ------------------------------------------------------------------
    # Background health monitor
    # ------------------------------------------------------------------

    def _health_monitor_loop(self) -> None:
        """Periodically check module health and trigger auto-restart."""
        _LOG.info("Health monitor started (interval=%ds)", self._health_interval)
        while self._running:
            with self._lock:
                names = list(self._modules.keys())
            for name in names:
                if not self._running:
                    break
                healthy = self.check_module_health(name)
                if healthy:
                    self._unhealthy_counts[name] = 0
                    self._reset_crash_count(name)
                else:
                    count = self._unhealthy_counts.get(name, 0) + 1
                    self._unhealthy_counts[name] = count
                    _LOG.warning(
                        "Module %r unhealthy (%d/%d)",
                        name,
                        count,
                        self._unhealthy_threshold,
                    )
                    if count >= self._unhealthy_threshold:
                        self._unhealthy_counts[name] = 0
                        self._handle_module_crash(name)

            # Sleep in small increments so shutdown is responsive
            for _ in range(self._health_interval):
                if not self._running:
                    break
                time.sleep(1)
        _LOG.info("Health monitor stopped")

    # ------------------------------------------------------------------
    # Daemon lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the lifecycle manager daemon (health monitor thread)."""
        if self._running:
            return
        self._running = True
        self._health_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="murphy-module-health",
            daemon=True,
        )
        self._health_thread.start()
        _LOG.info("ModuleLifecycleManager started")

    def stop(self) -> None:
        """Stop the lifecycle manager daemon."""
        if not self._running:
            return
        self._running = False
        if self._health_thread is not None:
            self._health_thread.join(timeout=self._health_interval + 5)
            self._health_thread = None
        _LOG.info("ModuleLifecycleManager stopped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="murphy-module-lifecycle",
        description="MurphyOS module lifecycle manager",
    )
    parser.add_argument(
        "--config",
        default="/etc/murphy/module-lifecycle.yaml",
        help="Path to YAML configuration file",
    )
    sub = parser.add_subparsers(dest="command")

    # daemon
    sub.add_parser("daemon", help="Run as a background daemon")

    # register
    reg = sub.add_parser("register", help="Register a module")
    reg.add_argument("name", help="Module name")
    reg.add_argument("--version", required=True, help="Module version")
    reg.add_argument("--entry-point", required=True, help="Executable / script path")
    reg.add_argument("--health-url", default="", help="Optional HTTP health endpoint")

    # unregister
    unreg = sub.add_parser("unregister", help="Unregister a module")
    unreg.add_argument("name", help="Module name")

    # start
    start = sub.add_parser("start", help="Start a module instance")
    start.add_argument("name", help="Module name")
    start.add_argument("--instance-id", default="", help="Instance ID")

    # stop
    stop = sub.add_parser("stop", help="Stop a module instance")
    stop.add_argument("name", help="Module name")
    stop.add_argument("--instance-id", default="", help="Instance ID")

    # restart
    restart = sub.add_parser("restart", help="Restart a module instance")
    restart.add_argument("name", help="Module name")
    restart.add_argument("--instance-id", default="", help="Instance ID")

    # status
    status = sub.add_parser("status", help="Show module status")
    status.add_argument("name", help="Module name")

    # list
    sub.add_parser("list", help="List all registered modules")

    # logs
    logs = sub.add_parser("logs", help="Show module logs")
    logs.add_argument("name", help="Module name")
    logs.add_argument("--lines", type=int, default=50, help="Number of log lines")

    # health
    health = sub.add_parser("health", help="Run health check for a module")
    health.add_argument("name", help="Module name")

    return parser


def _manager_from_config(config_path: str) -> ModuleLifecycleManager:
    """Instantiate a manager from a YAML config file."""
    path = Path(config_path)
    if path.exists():
        try:
            raw = _load_yaml(path)
        except Exception as exc:
            # MURPHY-MODULE-ERR-010: configuration load error
            _LOG.error("[%s] Failed to load config %s: %s", MURPHY_MODULE_ERR_010, path, exc)
            raw = {}
    else:
        _LOG.warning("Config file %s not found — using defaults", path)
        raw = {}

    section = raw.get("murphy_module_lifecycle", raw)
    return ModuleLifecycleManager(
        registry_path=Path(section.get("registry_path", str(_DEFAULT_REGISTRY_PATH))),
        module_slice=section.get("module_slice", _DEFAULT_MODULE_SLICE),
        defaults=section.get("defaults"),
        health_check=section.get("health_check"),
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    mgr = _manager_from_config(args.config)

    try:
        if args.command == "daemon":
            return _cmd_daemon(mgr)
        if args.command == "register":
            config: Dict[str, Any] = {}
            if args.health_url:
                config["health_url"] = args.health_url
            rec = mgr.register_module(args.name, args.version, args.entry_point, config)
            print(json.dumps(rec.to_dict(), indent=2))
        elif args.command == "unregister":
            mgr.unregister_module(args.name)
            print(f"Module '{args.name}' unregistered")
        elif args.command == "start":
            scope = mgr.start_module(args.name, args.instance_id)
            print(f"Started: {scope}")
        elif args.command == "stop":
            mgr.stop_module(args.name, args.instance_id)
            print(f"Stopped module '{args.name}'")
        elif args.command == "restart":
            scope = mgr.restart_module(args.name, args.instance_id)
            print(f"Restarted: {scope}")
        elif args.command == "status":
            detail = mgr.get_module(args.name)
            print(json.dumps(detail, indent=2))
        elif args.command == "list":
            modules = mgr.list_modules()
            print(json.dumps(modules, indent=2))
        elif args.command == "logs":
            print(mgr.get_module_logs(args.name, args.lines))
        elif args.command == "health":
            healthy = mgr.check_module_health(args.name)
            print(f"Module '{args.name}' healthy: {healthy}")
            return 0 if healthy else 1
        return 0
    except ModuleLifecycleError as exc:
        _LOG.error("%s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _cmd_daemon(mgr: ModuleLifecycleManager) -> int:
    """Run the manager as a long-lived daemon with signal handling."""
    shutdown = threading.Event()

    def _on_signal(signum: int, _frame: Any) -> None:
        _LOG.info("Received signal %d — shutting down", signum)
        shutdown.set()

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    mgr.start()

    # sd_notify(READY=1) if available
    notify_sock = os.environ.get("NOTIFY_SOCKET")
    if notify_sock:
        try:
            import socket

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.connect(notify_sock)
            sock.sendall(b"READY=1")
            sock.close()
        except Exception as exc:
            _LOG.warning("sd_notify failed: %s", exc)

    _LOG.info("Daemon running — waiting for shutdown signal")
    shutdown.wait()
    mgr.stop()
    _LOG.info("Daemon exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
