# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""MurphyOS cgroup v2 resource isolation manager.

Provides OS-level resource isolation for Murphy System workloads using Linux
cgroups v2.  Three workload classes are supported:

* ``murphy-swarm-{uuid}.scope`` — per-agent scopes
* ``murphy-llm.slice``          — LLM inference workloads
* ``murphy-automation.slice``   — automation tasks

When cgroup v2 is not available the manager operates as a silent no-op so
that higher-level code never needs to branch on kernel capabilities.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml  # PyYAML ships with every Murphy runtime; stdlib otherwise unused

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("murphy.cgroup")

_CGROUP_ROOT = Path("/sys/fs/cgroup")
_DEFAULT_BASE_SLICE = "murphy.slice"

_HUMAN_UNITS: Dict[str, int] = {
    "K": 1024,
    "M": 1024 ** 2,
    "G": 1024 ** 3,
    "T": 1024 ** 4,
}

_CONTROLLER_FILES = (
    "memory.max",
    "memory.current",
    "cpu.weight",
    "cpu.stat",
    "io.weight",
    "io.stat",
    "pids.max",
    "pids.current",
    "cgroup.procs",
)

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

MURPHY_CGROUP_ERR_001 = "MURPHY-CGROUP-ERR-001"  # cgroup v2 not mounted
MURPHY_CGROUP_ERR_002 = "MURPHY-CGROUP-ERR-002"  # base slice creation failed
MURPHY_CGROUP_ERR_003 = "MURPHY-CGROUP-ERR-003"  # scope creation failed
MURPHY_CGROUP_ERR_004 = "MURPHY-CGROUP-ERR-004"  # scope destruction failed
MURPHY_CGROUP_ERR_005 = "MURPHY-CGROUP-ERR-005"  # failed to write controller
MURPHY_CGROUP_ERR_006 = "MURPHY-CGROUP-ERR-006"  # failed to read controller
MURPHY_CGROUP_ERR_007 = "MURPHY-CGROUP-ERR-007"  # scope not found
MURPHY_CGROUP_ERR_008 = "MURPHY-CGROUP-ERR-008"  # invalid scope name
MURPHY_CGROUP_ERR_009 = "MURPHY-CGROUP-ERR-009"  # permission denied
MURPHY_CGROUP_ERR_010 = "MURPHY-CGROUP-ERR-010"  # orphan cleanup failed
MURPHY_CGROUP_ERR_011 = "MURPHY-CGROUP-ERR-011"  # configuration load error
MURPHY_CGROUP_ERR_012 = "MURPHY-CGROUP-ERR-012"  # invalid memory spec
MURPHY_CGROUP_ERR_013 = "MURPHY-CGROUP-ERR-013"  # subtree control delegation
MURPHY_CGROUP_ERR_014 = "MURPHY-CGROUP-ERR-014"  # signal handling error
MURPHY_CGROUP_ERR_015 = "MURPHY-CGROUP-ERR-015"  # daemon lifecycle error


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CGroupError(Exception):
    """Base exception for all cgroup operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"[{code}] {message}")


class CGroupNotAvailable(CGroupError):
    """Raised when cgroup v2 is not mounted."""

    def __init__(self, message: str = "cgroup v2 filesystem not available") -> None:
        super().__init__(MURPHY_CGROUP_ERR_001, message)


class ScopeNotFound(CGroupError):
    """Raised when a scope path does not exist."""

    def __init__(self, name: str) -> None:
        super().__init__(MURPHY_CGROUP_ERR_007, f"scope not found: {name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HUMAN_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMGT])?$", re.IGNORECASE)


def parse_human_bytes(value: str | int) -> int:
    """Convert a human-readable byte string (``512M``, ``4G``) to bytes.

    Plain integers and the literal string ``max`` are passed through.
    """
    if isinstance(value, int):
        return value
    value = str(value).strip()
    if value.lower() == "max":
        return -1  # sentinel for "max"
    match = _HUMAN_RE.match(value)
    if not match:
        raise CGroupError(MURPHY_CGROUP_ERR_012, f"invalid memory spec: {value!r}")
    number = float(match.group(1))
    suffix = (match.group(2) or "").upper()
    multiplier = _HUMAN_UNITS.get(suffix, 1)
    return int(number * multiplier)


def _safe_read(path: Path) -> str:
    """Read a cgroup controller file, returning empty string on failure."""
    try:
        return path.read_text().strip()
    except OSError as exc:
        # MURPHY-CGROUP-ERR-006 — failed to read controller
        _LOG.debug("%s: cannot read %s: %s", MURPHY_CGROUP_ERR_006, path, exc)
        return ""


def _safe_write(path: Path, value: str) -> None:
    """Write *value* to a cgroup controller file."""
    try:
        path.write_text(value)
    except PermissionError as exc:
        # MURPHY-CGROUP-ERR-009 — permission denied
        _LOG.error("%s: permission denied writing %s: %s", MURPHY_CGROUP_ERR_009, path, exc)
        raise CGroupError(MURPHY_CGROUP_ERR_009, f"permission denied: {path}") from exc
    except OSError as exc:
        # MURPHY-CGROUP-ERR-005 — failed to write controller
        _LOG.error("%s: cannot write %s: %s", MURPHY_CGROUP_ERR_005, path, exc)
        raise CGroupError(MURPHY_CGROUP_ERR_005, f"write failed: {path}: {exc}") from exc


_VALID_SCOPE_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_scope_name(name: str) -> None:
    if not name or not _VALID_SCOPE_RE.match(name):
        raise CGroupError(MURPHY_CGROUP_ERR_008, f"invalid scope name: {name!r}")


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ScopeUsage:
    """Snapshot of resource usage for a single cgroup scope."""

    name: str
    memory_current_bytes: int
    memory_max_bytes: int
    cpu_usage_usec: int
    nr_periods: int
    nr_throttled: int
    pids_current: int
    pids_max: int | str
    io_stats: str

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class ScopeLimits:
    """Desired limits for a cgroup scope."""

    memory_max: Optional[int] = None
    cpu_weight: Optional[int] = None
    io_weight: Optional[int] = None
    pids_max: Optional[int] = None


# ---------------------------------------------------------------------------
# CGroupManager
# ---------------------------------------------------------------------------


class CGroupManager:
    """Manages cgroup v2 hierarchies under ``/sys/fs/cgroup/<base_slice>/``.

    Parameters
    ----------
    config_path:
        Path to the ``cgroup.yaml`` configuration file.  When *None* the
        manager uses built-in defaults.
    base_slice:
        Override the base slice name (default ``murphy.slice``).
    """

    # ---- construction / initialisation ----

    def __init__(
        self,
        config_path: Optional[str | Path] = None,
        base_slice: Optional[str] = None,
    ) -> None:
        self._config: Dict[str, Any] = {}
        self._noop = False
        self._base_slice: str = base_slice or _DEFAULT_BASE_SLICE
        self._base_path: Path = _CGROUP_ROOT / self._base_slice

        self._load_config(config_path)

        if not self._detect_cgroupv2():
            _LOG.warning(
                "%s: cgroup v2 not available — operating in no-op mode",
                MURPHY_CGROUP_ERR_001,
            )
            self._noop = True
            return

        try:
            self._ensure_base_slice()
        except CGroupError:
            _LOG.warning(
                "%s: cannot write to cgroup tree — operating in no-op mode",
                MURPHY_CGROUP_ERR_002,
            )
            self._noop = True

    # ---- public API ----

    def create_scope(
        self,
        name: str,
        memory_max: str | int = "max",
        cpu_weight: int = 100,
        io_weight: int = 100,
        pids_max: int | str = "max",
    ) -> Path:
        """Create a new cgroup scope under the base slice.

        Returns the :class:`pathlib.Path` of the newly created scope
        directory.
        """
        _validate_scope_name(name)

        if self._noop:
            _LOG.info("no-op: would create scope %s", name)
            return self._base_path / name

        scope_path = self._base_path / name
        try:
            scope_path.mkdir(parents=False, exist_ok=True)
        except OSError as exc:
            # MURPHY-CGROUP-ERR-003 — scope creation failed
            _LOG.error("%s: failed to create scope %s: %s", MURPHY_CGROUP_ERR_003, name, exc)
            raise CGroupError(MURPHY_CGROUP_ERR_003, f"cannot create scope {name}: {exc}") from exc

        self._apply_limits(scope_path, memory_max, cpu_weight, io_weight, pids_max)
        _LOG.info("created scope %s at %s", name, scope_path)
        return scope_path

    def destroy_scope(self, name: str) -> None:
        """Remove a cgroup scope.

        All processes in the scope are migrated to the parent before the
        directory is removed.
        """
        _validate_scope_name(name)

        if self._noop:
            _LOG.info("no-op: would destroy scope %s", name)
            return

        scope_path = self._base_path / name
        if not scope_path.is_dir():
            raise ScopeNotFound(name)

        self._drain_processes(scope_path)

        try:
            scope_path.rmdir()
        except OSError as exc:
            # MURPHY-CGROUP-ERR-004 — scope destruction failed
            _LOG.error("%s: failed to destroy scope %s: %s", MURPHY_CGROUP_ERR_004, name, exc)
            raise CGroupError(
                MURPHY_CGROUP_ERR_004, f"cannot destroy scope {name}: {exc}"
            ) from exc

        _LOG.info("destroyed scope %s", name)

    def list_scopes(self) -> List[str]:
        """Return the names of all child cgroups under the base slice."""
        if self._noop:
            return []

        if not self._base_path.is_dir():
            return []

        try:
            return sorted(
                entry.name
                for entry in self._base_path.iterdir()
                if entry.is_dir()
            )
        except OSError as exc:
            # MURPHY-CGROUP-ERR-006 — failed to read controller
            _LOG.error("%s: cannot list scopes: %s", MURPHY_CGROUP_ERR_006, exc)
            return []

    def get_usage(self, name: str) -> ScopeUsage:
        """Read current resource usage for *name*."""
        _validate_scope_name(name)

        if self._noop:
            return ScopeUsage(
                name=name,
                memory_current_bytes=0,
                memory_max_bytes=0,
                cpu_usage_usec=0,
                nr_periods=0,
                nr_throttled=0,
                pids_current=0,
                pids_max="max",
                io_stats="",
            )

        scope_path = self._base_path / name
        if not scope_path.is_dir():
            raise ScopeNotFound(name)

        memory_current = self._read_int(scope_path / "memory.current")
        memory_max = self._read_int(scope_path / "memory.max")
        cpu_stat = self._parse_cpu_stat(scope_path / "cpu.stat")
        pids_current = self._read_int(scope_path / "pids.current")
        pids_max_raw = _safe_read(scope_path / "pids.max")
        pids_max: int | str = pids_max_raw if pids_max_raw == "max" else self._try_int(pids_max_raw)
        io_stats = _safe_read(scope_path / "io.stat")

        return ScopeUsage(
            name=name,
            memory_current_bytes=memory_current,
            memory_max_bytes=memory_max,
            cpu_usage_usec=cpu_stat.get("usage_usec", 0),
            nr_periods=cpu_stat.get("nr_periods", 0),
            nr_throttled=cpu_stat.get("nr_throttled", 0),
            pids_current=pids_current,
            pids_max=pids_max,
            io_stats=io_stats,
        )

    def set_limits(
        self,
        name: str,
        memory_max: Optional[str | int] = None,
        cpu_weight: Optional[int] = None,
        io_weight: Optional[int] = None,
        pids_max: Optional[int | str] = None,
    ) -> None:
        """Update resource limits on an existing scope."""
        _validate_scope_name(name)

        if self._noop:
            _LOG.info("no-op: would set limits on %s", name)
            return

        scope_path = self._base_path / name
        if not scope_path.is_dir():
            raise ScopeNotFound(name)

        if memory_max is not None:
            mem_bytes = parse_human_bytes(memory_max)
            val = "max" if mem_bytes < 0 else str(mem_bytes)
            _safe_write(scope_path / "memory.max", val)

        if cpu_weight is not None:
            _safe_write(scope_path / "cpu.weight", str(cpu_weight))

        if io_weight is not None:
            _safe_write(scope_path / "io.weight", str(io_weight))

        if pids_max is not None:
            _safe_write(scope_path / "pids.max", str(pids_max))

        _LOG.info("updated limits on scope %s", name)

    def cleanup_orphans(self) -> int:
        """Remove scopes that contain no processes.

        Returns the number of orphans removed.
        """
        if self._noop:
            return 0

        removed = 0
        for scope_name in self.list_scopes():
            scope_path = self._base_path / scope_name
            procs = _safe_read(scope_path / "cgroup.procs")
            if procs:
                continue
            try:
                scope_path.rmdir()
                _LOG.info("cleaned up orphan scope %s", scope_name)
                removed += 1
            except OSError as exc:
                # MURPHY-CGROUP-ERR-010 — orphan cleanup failed
                _LOG.warning(
                    "%s: cannot remove orphan %s: %s",
                    MURPHY_CGROUP_ERR_010,
                    scope_name,
                    exc,
                )
        return removed

    # ---- configuration helpers ----

    @property
    def is_noop(self) -> bool:
        """``True`` when cgroup v2 is unavailable and the manager is inert."""
        return self._noop

    @property
    def base_path(self) -> Path:
        return self._base_path

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    def swarm_defaults(self) -> Dict[str, Any]:
        """Return the default limits for swarm agent scopes."""
        return dict(self._config.get("swarm_defaults", {
            "memory_max": "512M",
            "cpu_weight": 100,
            "pids_max": 64,
        }))

    def llm_defaults(self) -> Dict[str, Any]:
        """Return the default limits for LLM inference slices."""
        return dict(self._config.get("llm_defaults", {
            "memory_max": "4G",
            "cpu_weight": 500,
            "io_weight": 200,
        }))

    def automation_defaults(self) -> Dict[str, Any]:
        """Return the default limits for automation task slices."""
        return dict(self._config.get("automation_defaults", {
            "memory_max": "1G",
            "cpu_weight": 200,
            "io_weight": 100,
        }))

    # ---- private helpers ----

    def _load_config(self, config_path: Optional[str | Path]) -> None:
        if config_path is None:
            self._config = {}
            return

        path = Path(config_path)
        if not path.is_file():
            _LOG.warning("config file %s not found — using defaults", path)
            return

        try:
            with path.open() as fh:
                raw = yaml.safe_load(fh) or {}
            self._config = raw.get("murphy_cgroup", raw)
            if "base_slice" in self._config:
                self._base_slice = self._config["base_slice"]
                self._base_path = _CGROUP_ROOT / self._base_slice
            if self._config.get("enabled") is False:
                _LOG.info("cgroup manager disabled via configuration")
                self._noop = True
        except Exception as exc:
            # MURPHY-CGROUP-ERR-011 — configuration load error
            _LOG.error("%s: failed to load config %s: %s", MURPHY_CGROUP_ERR_011, path, exc)
            raise CGroupError(MURPHY_CGROUP_ERR_011, f"config load failed: {exc}") from exc

    def _detect_cgroupv2(self) -> bool:
        """Return ``True`` if a unified cgroup v2 hierarchy is mounted."""
        unified_marker = _CGROUP_ROOT / "cgroup.controllers"
        return unified_marker.is_file()

    def _ensure_base_slice(self) -> None:
        """Create the base slice directory if it does not exist."""
        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            # MURPHY-CGROUP-ERR-002 — base slice creation failed
            _LOG.error("%s: cannot create base slice %s: %s", MURPHY_CGROUP_ERR_002, self._base_path, exc)
            raise CGroupError(
                MURPHY_CGROUP_ERR_002, f"base slice creation failed: {exc}"
            ) from exc

        self._delegate_controllers()

    def _delegate_controllers(self) -> None:
        """Enable controller delegation in the base slice."""
        subtree_control = self._base_path / "cgroup.subtree_control"
        for controller in ("+memory", "+cpu", "+io", "+pids"):
            try:
                subtree_control.write_text(controller)
            except OSError as exc:
                # MURPHY-CGROUP-ERR-013 — subtree control delegation
                _LOG.warning(
                    "%s: cannot delegate %s: %s",
                    MURPHY_CGROUP_ERR_013,
                    controller,
                    exc,
                )

    def _apply_limits(
        self,
        scope_path: Path,
        memory_max: str | int,
        cpu_weight: int,
        io_weight: int,
        pids_max: int | str,
    ) -> None:
        mem_bytes = parse_human_bytes(memory_max)
        mem_val = "max" if mem_bytes < 0 else str(mem_bytes)
        _safe_write(scope_path / "memory.max", mem_val)
        _safe_write(scope_path / "cpu.weight", str(cpu_weight))
        _safe_write(scope_path / "io.weight", str(io_weight))
        _safe_write(scope_path / "pids.max", str(pids_max))

    def _drain_processes(self, scope_path: Path) -> None:
        """Move all processes from *scope_path* to the parent cgroup."""
        procs_file = scope_path / "cgroup.procs"
        parent_procs = self._base_path / "cgroup.procs"
        pids_raw = _safe_read(procs_file)
        if not pids_raw:
            return
        for pid_str in pids_raw.splitlines():
            pid_str = pid_str.strip()
            if not pid_str:
                continue
            try:
                parent_procs.write_text(pid_str)
            except OSError as exc:
                # MURPHY-CGROUP-ERR-004 — scope destruction (drain) failed
                _LOG.warning(
                    "%s: cannot migrate PID %s from %s: %s",
                    MURPHY_CGROUP_ERR_004,
                    pid_str,
                    scope_path.name,
                    exc,
                )

    def _read_int(self, path: Path) -> int:
        raw = _safe_read(path)
        if raw in ("", "max"):
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0

    @staticmethod
    def _try_int(value: str) -> int | str:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value

    def _parse_cpu_stat(self, path: Path) -> Dict[str, int]:
        result: Dict[str, int] = {}
        raw = _safe_read(path)
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) == 2:
                try:
                    result[parts[0]] = int(parts[1])
                except ValueError:
                    pass
        return result


# ---------------------------------------------------------------------------
# Daemon entry point
# ---------------------------------------------------------------------------


def _run_daemon(config_path: Optional[str] = None) -> None:
    """Run the cgroup manager as a long-lived daemon.

    The daemon periodically cleans up orphan scopes and can be extended to
    expose a Unix socket API for runtime limit adjustments.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    _LOG.info("murphy-cgroup daemon starting")

    try:
        manager = CGroupManager(config_path=config_path)
    except CGroupError as exc:
        # MURPHY-CGROUP-ERR-015 — daemon lifecycle error
        _LOG.critical("%s: cannot initialise manager: %s", MURPHY_CGROUP_ERR_015, exc)
        sys.exit(1)

    # sd_notify(READY=1) — tell systemd we are ready
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if notify_socket:
        _sd_notify(notify_socket, b"READY=1")

    shutdown = False

    def _handle_signal(signum: int, _frame: Any) -> None:
        nonlocal shutdown
        _LOG.info("received signal %s — shutting down", signum)
        shutdown = True

    try:
        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)
    except Exception as exc:
        # MURPHY-CGROUP-ERR-014 — signal handling error
        _LOG.error("%s: signal setup failed: %s", MURPHY_CGROUP_ERR_014, exc)

    cleanup_interval = 60  # seconds
    _LOG.info(
        "daemon ready — base_path=%s, noop=%s, cleanup_interval=%ds",
        manager.base_path,
        manager.is_noop,
        cleanup_interval,
    )

    while not shutdown:
        try:
            time.sleep(cleanup_interval)
        except InterruptedError:
            continue

        try:
            removed = manager.cleanup_orphans()
            if removed:
                _LOG.info("cleaned up %d orphan scope(s)", removed)
        except Exception as exc:
            # MURPHY-CGROUP-ERR-010 — orphan cleanup failed
            _LOG.error("%s: orphan cleanup cycle failed: %s", MURPHY_CGROUP_ERR_010, exc)

    _LOG.info("murphy-cgroup daemon stopped")


def _sd_notify(socket_path: str, message: bytes) -> None:
    """Minimal sd_notify implementation (no external dependencies)."""
    import socket as _socket

    try:
        addr = socket_path
        if addr.startswith("@"):
            addr = "\0" + addr[1:]
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_DGRAM)
        try:
            sock.connect(addr)
            sock.sendall(message)
        finally:
            sock.close()
    except Exception as exc:
        # MURPHY-CGROUP-ERR-015 — daemon lifecycle error
        _LOG.warning("%s: sd_notify failed: %s", MURPHY_CGROUP_ERR_015, exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> None:
    """Minimal CLI for the cgroup manager."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="murphy-cgroup",
        description="MurphyOS cgroup v2 resource isolation manager",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("daemon", help="Run as a long-lived daemon")

    p_create = sub.add_parser("create", help="Create a scope")
    p_create.add_argument("name")
    p_create.add_argument("--memory-max", default="512M")
    p_create.add_argument("--cpu-weight", type=int, default=100)
    p_create.add_argument("--io-weight", type=int, default=100)
    p_create.add_argument("--pids-max", default="max")

    p_destroy = sub.add_parser("destroy", help="Destroy a scope")
    p_destroy.add_argument("name")

    sub.add_parser("list", help="List scopes")

    p_usage = sub.add_parser("usage", help="Show scope usage")
    p_usage.add_argument("name")

    p_limits = sub.add_parser("set-limits", help="Update scope limits")
    p_limits.add_argument("name")
    p_limits.add_argument("--memory-max")
    p_limits.add_argument("--cpu-weight", type=int)
    p_limits.add_argument("--io-weight", type=int)
    p_limits.add_argument("--pids-max")

    sub.add_parser("cleanup", help="Remove orphan scopes")

    parser.add_argument(
        "--config",
        default=None,
        help="Path to cgroup.yaml configuration file",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )

    if args.command == "daemon":
        _run_daemon(config_path=args.config)
        return

    mgr = CGroupManager(config_path=args.config)

    if args.command == "create":
        pids_max: int | str = args.pids_max
        try:
            pids_max = int(pids_max)
        except ValueError:
            pass
        path = mgr.create_scope(
            args.name,
            memory_max=args.memory_max,
            cpu_weight=args.cpu_weight,
            io_weight=args.io_weight,
            pids_max=pids_max,
        )
        print(f"created {path}")
    elif args.command == "destroy":
        mgr.destroy_scope(args.name)
        print(f"destroyed {args.name}")
    elif args.command == "list":
        for name in mgr.list_scopes():
            print(name)
    elif args.command == "usage":
        usage = mgr.get_usage(args.name)
        print(json.dumps(usage.as_dict(), indent=2))
    elif args.command == "set-limits":
        pids_val: int | str | None = args.pids_max
        if pids_val is not None:
            try:
                pids_val = int(pids_val)
            except ValueError:
                pass
        mgr.set_limits(
            args.name,
            memory_max=args.memory_max,
            cpu_weight=args.cpu_weight,
            io_weight=args.io_weight,
            pids_max=pids_val,
        )
        print(f"limits updated on {args.name}")
    elif args.command == "cleanup":
        removed = mgr.cleanup_orphans()
        print(f"removed {removed} orphan(s)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
