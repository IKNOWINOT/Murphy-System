#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphyfs — FUSE virtual filesystem for MurphyOS.

Exposes the Murphy runtime state as a POSIX filesystem mounted at
``/murphy/live``.  Every process on the host can inspect confidence
scores, engine status, swarm agents, governance gates, and the live
event stream using standard ``cat`` / ``ls`` / ``tail -f`` commands.

Layout::

    /murphy/live/
    ├── confidence          MFGC score (e.g. "0.8700\\n")
    ├── engines/
    │   └── <name>/
    │       ├── status      "running\\n" | "stopped\\n"
    │       └── config      engine config JSON
    ├── swarm/
    │   └── <uuid>/
    │       ├── role        agent role name
    │       ├── status      agent status
    │       └── log         streaming agent log
    ├── gates/
    │   ├── EXECUTIVE       "open\\n" | "blocked\\n" | "pending\\n"
    │   ├── OPERATIONS
    │   ├── QA
    │   ├── HITL            writable — ``echo "approve <id>" > HITL``
    │   ├── COMPLIANCE
    │   └── BUDGET
    ├── events              real-time Event Backbone stream
    ├── llm/
    │   ├── status          LLM governor status JSON
    │   ├── usage           LLM usage JSON
    │   └── health          LLM health JSON
    ├── telemetry/
    │   ├── status          Telemetry export status JSON
    │   └── metrics         Telemetry metrics JSON
    ├── backup/
    │   ├── status          Backup subsystem status JSON
    │   └── list            Backup list JSON
    ├── cgroup/
    │   ├── list            CGroup list JSON
    │   └── usage           CGroup usage JSON
    ├── modules/
    │   ├── list            Module list JSON
    │   └── <name>/
    │       └── status      Module status JSON
    └── system/
        ├── version         Murphy version string
        ├── uptime          system uptime
        └── health          JSON health status

Requires: fusepy (``pip install fusepy``).
Run:      ``murphyfs /murphy/live``
"""

from __future__ import annotations

import argparse
import errno
import json
import logging
import os
import signal
import stat
import sys
import threading
import time
from typing import Any, Dict, List, Optional

try:
    from fuse import FUSE, FuseOSError, Operations
except ImportError:
    sys.stderr.write(
        "MURPHYFS-ERR-001: fusepy is not installed.  "
        "Install with: pip install fusepy\n"
    )
    sys.exit(1)

try:
    import urllib.request
    import urllib.error
except ImportError:  # MURPHYFS-ERR-007
    LOG.debug("MURPHYFS-ERR-007: urllib import failed")
    pass  # stdlib — always available

# ── Logging ─────────────────────────────────────────────────────────
LOG = logging.getLogger("murphyfs")

# ── Error codes ─────────────────────────────────────────────────────
# MURPHYFS-ERR-001  fusepy not installed
# MURPHYFS-ERR-002  API request failed
# MURPHYFS-ERR-003  mount-point missing
# MURPHYFS-ERR-004  unexpected FUSE callback error
# MURPHYFS-ERR-005  write failed
# MURPHYFS-ERR-006  cache refresh failed
# MURPHYFS-ERR-007  urllib import failed (should never happen — stdlib)
# MURPHYFS-ERR-008  /dev/murphy-confidence not readable
# MURPHYFS-ERR-009  confidence JSON parse failed
# MURPHYFS-ERR-010  engine list JSON parse failed
# MURPHYFS-ERR-011  swarm agent list JSON parse failed
# MURPHYFS-ERR-012  gate status JSON parse failed
# MURPHYFS-ERR-013  system version JSON parse failed
# MURPHYFS-ERR-014  system uptime JSON parse failed
# MURPHYFS-ERR-015  confidence value not numeric
# MURPHYFS-ERR-016  LLM data JSON parse failed
# MURPHYFS-ERR-017  telemetry data JSON parse failed
# MURPHYFS-ERR-018  backup data JSON parse failed
# MURPHYFS-ERR-019  cgroup data JSON parse failed
# MURPHYFS-ERR-020  module list JSON parse failed

MURPHY_VERSION = "1.0.0"

GATE_NAMES = ("EXECUTIVE", "OPERATIONS", "QA", "HITL", "COMPLIANCE", "BUDGET")


# ── Helpers ─────────────────────────────────────────────────────────

def _now() -> float:
    return time.time()


def _api_get(url: str, timeout: float = 3.0) -> Optional[str]:
    """HTTP GET returning response body or *None* on failure."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        LOG.debug("MURPHYFS-ERR-002: GET %s — %s", url, exc)
        return None


def _api_post(url: str, body: str, timeout: float = 5.0) -> Optional[str]:
    """HTTP POST with a JSON body, returning response body or *None*."""
    try:
        data = body.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        LOG.debug("MURPHYFS-ERR-002: POST %s — %s", url, exc)
        return None


def _read_dev_confidence() -> Optional[str]:
    """Try reading the kernel character device for MFGC score."""
    try:
        with open("/dev/murphy-confidence", "r") as fh:
            return fh.read().strip()
    except OSError:  # MURPHYFS-ERR-008
        LOG.debug("MURPHYFS-ERR-008: /dev/murphy-confidence not readable")
        return None


# ── Timed cache ─────────────────────────────────────────────────────

class _Cache:
    """Thread-safe TTL cache for API responses."""

    def __init__(self, ttl: float = 2.0):
        self._ttl = ttl
        self._store: Dict[str, Any] = {}
        self._ts: Dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str, fetcher):
        """Return cached value or call *fetcher()* to refresh."""
        with self._lock:
            now = _now()
            if key in self._store and (now - self._ts.get(key, 0)) < self._ttl:
                return self._store[key]
        try:
            value = fetcher()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("MURPHYFS-ERR-006: cache refresh %s — %s", key, exc)
            with self._lock:
                return self._store.get(key)
        with self._lock:
            self._store[key] = value
            self._ts[key] = _now()
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._ts.pop(key, None)


# ── FUSE Operations ────────────────────────────────────────────────

class MurphyFS(Operations):
    """Virtual filesystem backed by the Murphy REST API."""

    def __init__(self, api_url: str, cache_ttl: float = 2.0):
        self._api = api_url.rstrip("/")
        self._cache = _Cache(ttl=cache_ttl)
        self._start_time = _now()
        self._open_files: Dict[int, bytes] = {}
        self._fh_counter = 0
        self._fh_lock = threading.Lock()
        LOG.info("MurphyFS initialised — api=%s  ttl=%.1fs", self._api, cache_ttl)

    # ── internal helpers ────────────────────────────────────────────

    def _next_fh(self) -> int:
        with self._fh_lock:
            self._fh_counter += 1
            return self._fh_counter

    def _confidence_text(self) -> str:
        raw = _read_dev_confidence()
        if raw is None:
            body = _api_get(f"{self._api}/api/compute-plane/statistics")
            if body:
                try:
                    data = json.loads(body)
                    raw = str(data.get("confidence", data.get("mfgc", "0.0000")))
                except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-009
                    LOG.debug("MURPHYFS-ERR-009: confidence JSON parse failed")
                    raw = body.strip()
            else:
                raw = "0.0000"
        try:
            return f"{float(raw):.4f}\n"
        except (ValueError, TypeError):  # MURPHYFS-ERR-015
            LOG.debug("MURPHYFS-ERR-015: confidence value not numeric: %r", raw)
            return f"{raw}\n"

    def _engines(self) -> Dict[str, dict]:
        def _fetch():
            body = _api_get(f"{self._api}/api/engines")
            if body:
                try:
                    data = json.loads(body)
                    if isinstance(data, list):
                        return {e.get("name", f"engine-{i}"): e for i, e in enumerate(data)}
                    if isinstance(data, dict) and "engines" in data:
                        return {e.get("name", f"engine-{i}"): e for i, e in enumerate(data["engines"])}
                    return data if isinstance(data, dict) else {}
                except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-010
                    LOG.debug("MURPHYFS-ERR-010: engine list JSON parse failed")
            return {}
        return self._cache.get("engines", _fetch) or {}

    def _swarm_agents(self) -> Dict[str, dict]:
        def _fetch():
            body = _api_get(f"{self._api}/api/swarm/agents")
            if body:
                try:
                    data = json.loads(body)
                    if isinstance(data, list):
                        return {a.get("id", a.get("uuid", f"agent-{i}")): a for i, a in enumerate(data)}
                    if isinstance(data, dict) and "agents" in data:
                        return {a.get("id", a.get("uuid", f"agent-{i}")): a for i, a in enumerate(data["agents"])}
                    return data if isinstance(data, dict) else {}
                except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-011
                    LOG.debug("MURPHYFS-ERR-011: swarm agent list JSON parse failed")
            return {}
        return self._cache.get("swarm", _fetch) or {}

    def _gate_status(self, gate: str) -> str:
        def _fetch():
            body = _api_get(f"{self._api}/api/gates")
            if body:
                try:
                    return json.loads(body)
                except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-012
                    LOG.debug("MURPHYFS-ERR-012: gate status JSON parse failed")
            return {}
        gates = self._cache.get("gates", _fetch) or {}
        val = gates.get(gate, gates.get(gate.lower(), "pending"))
        return f"{val}\n"

    def _system_version(self) -> str:
        body = _api_get(f"{self._api}/api/version")
        if body:
            try:
                data = json.loads(body)
                return f"{data.get('version', MURPHY_VERSION)}\n"
            except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-013
                LOG.debug("MURPHYFS-ERR-013: system version JSON parse failed")
                return f"{body.strip()}\n"
        return f"{MURPHY_VERSION}\n"

    def _system_uptime(self) -> str:
        body = _api_get(f"{self._api}/api/health")
        if body:
            try:
                data = json.loads(body)
                uptime = data.get("uptime", "")
                if uptime:
                    return f"{uptime}\n"
            except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-014
                LOG.debug("MURPHYFS-ERR-014: system uptime JSON parse failed")
        return f"{_now() - self._start_time:.0f}s\n"

    def _system_health(self) -> str:
        body = _api_get(f"{self._api}/api/health")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"status":"unknown"}\n'

    def _llm_status(self) -> str:
        body = _api_get(f"{self._api}/api/llm/status")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"status":"unknown"}\n'

    def _llm_usage(self) -> str:
        body = _api_get(f"{self._api}/api/llm/usage")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"usage":{}}\n'

    def _llm_health(self) -> str:
        body = _api_get(f"{self._api}/api/llm/health")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"health":"unknown"}\n'

    def _telemetry_status(self) -> str:
        body = _api_get(f"{self._api}/api/telemetry/status")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"status":"unknown"}\n'

    def _telemetry_metrics(self) -> str:
        body = _api_get(f"{self._api}/api/telemetry/metrics")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"metrics":{}}\n'

    def _backup_status(self) -> str:
        body = _api_get(f"{self._api}/api/backup/status")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"status":"unknown"}\n'

    def _backup_list(self) -> str:
        body = _api_get(f"{self._api}/api/backup/list")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"backups":[]}\n'

    def _cgroup_list(self) -> str:
        body = _api_get(f"{self._api}/api/cgroup/list")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"cgroups":[]}\n'

    def _cgroup_usage(self) -> str:
        body = _api_get(f"{self._api}/api/cgroup/usage")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"usage":{}}\n'

    def _modules_list(self) -> str:
        body = _api_get(f"{self._api}/api/modules")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"modules":[]}\n'

    def _module_names(self) -> List[str]:
        def _fetch():
            body = _api_get(f"{self._api}/api/modules")
            if body:
                try:
                    data = json.loads(body)
                    if isinstance(data, list):
                        return [str(m.get("name", f"module-{i}") if isinstance(m, dict) else m) for i, m in enumerate(data)]
                    if isinstance(data, dict):
                        mods = data.get("modules", data.get("data", []))
                        if isinstance(mods, list):
                            return [str(m.get("name", f"module-{i}") if isinstance(m, dict) else m) for i, m in enumerate(mods)]
                    return []
                except (json.JSONDecodeError, TypeError):  # MURPHYFS-ERR-020
                    LOG.debug("MURPHYFS-ERR-020: module list JSON parse failed")
            return []
        return self._cache.get("module_names", _fetch) or []

    def _module_status(self, name: str) -> str:
        body = _api_get(f"{self._api}/api/modules/{name}/status")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return '{"status":"unknown"}\n'

    def _events_snapshot(self) -> str:
        body = _api_get(f"{self._api}/api/events/stream")
        if body:
            return body if body.endswith("\n") else body + "\n"
        return ""

    # ── path resolution ─────────────────────────────────────────────

    def _resolve(self, path: str) -> Optional[bytes]:
        """Return file content for *path*, or *None* if it is a directory."""
        parts = [p for p in path.strip("/").split("/") if p]

        if not parts:
            return None  # root dir

        # /confidence
        if parts == ["confidence"]:
            return self._confidence_text().encode()

        # /events
        if parts == ["events"]:
            return self._events_snapshot().encode()

        # /engines/...
        if parts[0] == "engines":
            engines = self._engines()
            if len(parts) == 1:
                return None  # dir
            name = parts[1]
            if name not in engines:
                raise FuseOSError(errno.ENOENT)
            if len(parts) == 2:
                return None  # dir
            eng = engines[name]
            if parts[2] == "status":
                st = eng.get("status", "stopped")
                return f"{st}\n".encode()
            if parts[2] == "config":
                return (json.dumps(eng, indent=2) + "\n").encode()
            raise FuseOSError(errno.ENOENT)

        # /swarm/...
        if parts[0] == "swarm":
            agents = self._swarm_agents()
            if len(parts) == 1:
                return None
            aid = parts[1]
            if aid not in agents:
                raise FuseOSError(errno.ENOENT)
            if len(parts) == 2:
                return None
            agent = agents[aid]
            if parts[2] == "role":
                return f"{agent.get('role', 'unknown')}\n".encode()
            if parts[2] == "status":
                return f"{agent.get('status', 'unknown')}\n".encode()
            if parts[2] == "log":
                body = _api_get(f"{self._api}/api/swarm/agents/{aid}/log")
                return (body or "").encode()
            raise FuseOSError(errno.ENOENT)

        # /gates/...
        if parts[0] == "gates":
            if len(parts) == 1:
                return None
            gate = parts[1]
            if gate not in GATE_NAMES:
                raise FuseOSError(errno.ENOENT)
            return self._gate_status(gate).encode()

        # /system/...
        if parts[0] == "system":
            if len(parts) == 1:
                return None
            if parts[1] == "version":
                return self._system_version().encode()
            if parts[1] == "uptime":
                return self._system_uptime().encode()
            if parts[1] == "health":
                return self._system_health().encode()
            raise FuseOSError(errno.ENOENT)

        # /llm/...
        if parts[0] == "llm":
            if len(parts) == 1:
                return None
            if parts[1] == "status":
                return self._llm_status().encode()
            if parts[1] == "usage":
                return self._llm_usage().encode()
            if parts[1] == "health":
                return self._llm_health().encode()
            raise FuseOSError(errno.ENOENT)

        # /telemetry/...
        if parts[0] == "telemetry":
            if len(parts) == 1:
                return None
            if parts[1] == "status":
                return self._telemetry_status().encode()
            if parts[1] == "metrics":
                return self._telemetry_metrics().encode()
            raise FuseOSError(errno.ENOENT)

        # /backup/...
        if parts[0] == "backup":
            if len(parts) == 1:
                return None
            if parts[1] == "status":
                return self._backup_status().encode()
            if parts[1] == "list":
                return self._backup_list().encode()
            raise FuseOSError(errno.ENOENT)

        # /cgroup/...
        if parts[0] == "cgroup":
            if len(parts) == 1:
                return None
            if parts[1] == "list":
                return self._cgroup_list().encode()
            if parts[1] == "usage":
                return self._cgroup_usage().encode()
            raise FuseOSError(errno.ENOENT)

        # /modules/...
        if parts[0] == "modules":
            if len(parts) == 1:
                return None
            if parts[1] == "list":
                return self._modules_list().encode()
            mod_names = self._module_names()
            if parts[1] in mod_names:
                if len(parts) == 2:
                    return None  # dir
                if parts[2] == "status":
                    return self._module_status(parts[1]).encode()
                raise FuseOSError(errno.ENOENT)
            raise FuseOSError(errno.ENOENT)

        raise FuseOSError(errno.ENOENT)

    def _is_dir(self, path: str) -> bool:
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            return True
        if parts[0] in ("engines", "swarm", "gates", "system",
                         "llm", "telemetry", "backup", "cgroup",
                         "modules") and len(parts) == 1:
            return True
        if parts[0] == "engines" and len(parts) == 2:
            return parts[1] in self._engines()
        if parts[0] == "swarm" and len(parts) == 2:
            return parts[1] in self._swarm_agents()
        if parts[0] == "modules" and len(parts) == 2 and parts[1] != "list":
            return parts[1] in self._module_names()
        return False

    # ── FUSE callbacks ──────────────────────────────────────────────

    def getattr(self, path: str, fh: Optional[int] = None) -> dict:
        now = _now()
        base = {
            "st_uid": os.getuid(),
            "st_gid": os.getgid(),
            "st_atime": now,
            "st_mtime": now,
            "st_ctime": now,
        }
        try:
            if self._is_dir(path):
                base["st_mode"] = stat.S_IFDIR | 0o755
                base["st_nlink"] = 2
                base["st_size"] = 4096
                return base

            content = self._resolve(path)
            if content is None:
                # Could be an empty dir — raise not found
                raise FuseOSError(errno.ENOENT)

            parts = [p for p in path.strip("/").split("/") if p]
            writable = (parts[0] == "gates") if parts else False
            mode = 0o644 if writable else 0o444
            base["st_mode"] = stat.S_IFREG | mode
            base["st_nlink"] = 1
            base["st_size"] = len(content)
            return base
        except FuseOSError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOG.error("MURPHYFS-ERR-004: getattr %s — %s", path, exc)
            raise FuseOSError(errno.EIO) from exc

    def readdir(self, path: str, fh: int) -> List[str]:
        entries = [".", ".."]
        parts = [p for p in path.strip("/").split("/") if p]
        try:
            if not parts:
                entries += ["confidence", "engines", "swarm", "gates", "events", "system",
                            "llm", "telemetry", "backup", "cgroup", "modules"]
            elif parts == ["engines"]:
                entries += list(self._engines().keys())
            elif parts[0] == "engines" and len(parts) == 2:
                entries += ["status", "config"]
            elif parts == ["swarm"]:
                entries += list(self._swarm_agents().keys())
            elif parts[0] == "swarm" and len(parts) == 2:
                entries += ["role", "status", "log"]
            elif parts == ["gates"]:
                entries += list(GATE_NAMES)
            elif parts == ["system"]:
                entries += ["version", "uptime", "health"]
            elif parts == ["llm"]:
                entries += ["status", "usage", "health"]
            elif parts == ["telemetry"]:
                entries += ["status", "metrics"]
            elif parts == ["backup"]:
                entries += ["status", "list"]
            elif parts == ["cgroup"]:
                entries += ["list", "usage"]
            elif parts == ["modules"]:
                entries += ["list"] + self._module_names()
            elif parts[0] == "modules" and len(parts) == 2:
                entries += ["status"]
            else:
                raise FuseOSError(errno.ENOENT)
        except FuseOSError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOG.error("MURPHYFS-ERR-004: readdir %s — %s", path, exc)
            raise FuseOSError(errno.EIO) from exc
        return entries

    def open(self, path: str, flags: int) -> int:
        fh = self._next_fh()
        try:
            content = self._resolve(path)
            self._open_files[fh] = content if content is not None else b""
        except FuseOSError:
            raise
        except Exception as exc:  # noqa: BLE001
            LOG.error("MURPHYFS-ERR-004: open %s — %s", path, exc)
            raise FuseOSError(errno.EIO) from exc
        return fh

    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        data = self._open_files.get(fh)
        if data is None:
            try:
                data = self._resolve(path) or b""
            except FuseOSError:
                raise
            except Exception as exc:  # noqa: BLE001
                LOG.error("MURPHYFS-ERR-004: read %s — %s", path, exc)
                raise FuseOSError(errno.EIO) from exc
        return data[offset:offset + size]

    def write(self, path: str, data: bytes, offset: int, fh: int) -> int:
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) != 2 or parts[0] != "gates":
            raise FuseOSError(errno.EACCES)

        gate = parts[1]
        if gate not in GATE_NAMES:
            raise FuseOSError(errno.ENOENT)

        text = data.decode("utf-8", errors="replace").strip()
        tokens = text.split(None, 1)
        if not tokens:
            raise FuseOSError(errno.EINVAL)

        action = tokens[0].lower()
        request_id = tokens[1] if len(tokens) > 1 else ""

        payload = json.dumps({"gate": gate, "action": action, "request_id": request_id})
        result = _api_post(f"{self._api}/api/gates/{gate}/action", payload)
        if result is None:
            LOG.error("MURPHYFS-ERR-005: write to gate %s failed", gate)
            raise FuseOSError(errno.EIO)

        self._cache.invalidate("gates")
        return len(data)

    def release(self, path: str, fh: int) -> None:
        self._open_files.pop(fh, None)

    def truncate(self, path: str, length: int, fh: Optional[int] = None) -> None:
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) == 2 and parts[0] == "gates":
            return  # allow truncate for writable gate files
        raise FuseOSError(errno.EACCES)

    def statfs(self, path: str) -> dict:
        return {
            "f_bsize": 4096,
            "f_frsize": 4096,
            "f_blocks": 0,
            "f_bfree": 0,
            "f_bavail": 0,
            "f_files": 0,
            "f_ffree": 0,
            "f_favail": 0,
            "f_namemax": 255,
        }


# ── Main ────────────────────────────────────────────────────────────

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="murphyfs",
        description="MurphyOS FUSE filesystem — mount Murphy state at a directory.",
    )
    parser.add_argument(
        "mountpoint",
        help="Directory to mount the filesystem on (e.g. /murphy/live).",
    )
    parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        default=False,
        help="Run in the foreground (do not daemonise).",
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        default=False,
        help="Enable FUSE debug output (implies --foreground).",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("MURPHY_API_URL", "http://127.0.0.1:8000"),
        help="Murphy REST API base URL (default: http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--cache-ttl",
        type=float,
        default=float(os.environ.get("MURPHYFS_CACHE_TTL", "2.0")),
        help="Cache TTL in seconds (default: 2.0).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [murphyfs] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    if args.debug:
        args.foreground = True

    mountpoint = os.path.abspath(args.mountpoint)
    if not os.path.isdir(mountpoint):
        LOG.error(
            "MURPHYFS-ERR-003: mount-point %s does not exist or is not a directory",
            mountpoint,
        )
        sys.exit(1)

    fs = MurphyFS(api_url=args.api_url, cache_ttl=args.cache_ttl)

    # Graceful shutdown on SIGTERM / SIGINT
    def _handle_signal(signum, _frame):
        LOG.info("Received signal %d — unmounting", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    LOG.info("Mounting MurphyFS on %s  (foreground=%s)", mountpoint, args.foreground)

    FUSE(
        fs,
        mountpoint,
        foreground=args.foreground,
        nothreads=False,
        allow_other=False,
        ro=False,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
