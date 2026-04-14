#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_cli — Command-line interface for the Murphy runtime.

Provides the ``murphy`` command with subcommands for status, forge, swarm
management, governance gates, engine control, log streaming, confidence
monitoring, configuration, post-quantum cryptography operations, LLM
governor, backup, telemetry, cgroup isolation, and module lifecycle.

Data sources (tried in order):
  1. D-Bus  (``org.murphy.System`` via dbus-next)
  2. REST API  (``http://127.0.0.1:8000``)
  3. MurphyFS  (``/murphy/live/`` filesystem)

Usage::

    murphy status
    murphy forge "build a dashboard"
    murphy swarm list
    murphy gate approve req-42
    murphy confidence
    murphy pqc status
    murphy llm status
    murphy backup list
    murphy telemetry status
    murphy cgroup list
    murphy module list

---------------------------------------------------------------------------
Error-code registry
---------------------------------------------------------------------------
MURPHY-CLI-ERR-001  REST API GET request failed
MURPHY-CLI-ERR-002  REST API POST request failed
MURPHY-CLI-ERR-003  REST API DELETE request failed
MURPHY-CLI-ERR-004  Failed to read MurphyFS live file
MURPHY-CLI-ERR-005  D-Bus method call failed
MURPHY-CLI-ERR-006  Failed to parse MurphyFS live file as JSON
MURPHY-CLI-ERR-007  Non-numeric confidence score in status display
MURPHY-CLI-ERR-008  Gate approve filesystem fallback failed
MURPHY-CLI-ERR-009  Gate deny filesystem fallback failed
MURPHY-CLI-ERR-010  Event stream file not found
MURPHY-CLI-ERR-011  Event streaming interrupted by user
MURPHY-CLI-ERR-012  Non-numeric confidence score in confidence command
MURPHY-CLI-ERR-013  Command interrupted by user
MURPHY-CLI-ERR-014  Unhandled exception in command dispatch
MURPHY-CLI-ERR-015  LLM governor status retrieval failed
MURPHY-CLI-ERR-016  LLM governor health retrieval failed
MURPHY-CLI-ERR-017  Backup create operation failed
MURPHY-CLI-ERR-018  Backup list retrieval failed
MURPHY-CLI-ERR-019  Backup verify operation failed
MURPHY-CLI-ERR-020  Backup restore operation failed
MURPHY-CLI-ERR-021  Telemetry status retrieval failed
MURPHY-CLI-ERR-022  Telemetry metrics dump failed
MURPHY-CLI-ERR-023  Cgroup listing/usage retrieval failed
MURPHY-CLI-ERR-024  Module lifecycle operation failed
---------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# ── Version ─────────────────────────────────────────────────────────

__version__ = "1.0.0"

logger = logging.getLogger("murphy-cli")

# ── Exit codes ──────────────────────────────────────────────────────

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_DEGRADED = 2

# ── Colour helpers ──────────────────────────────────────────────────

_NO_COLOR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _green(t: str) -> str:
    return _c("32", t)


def _yellow(t: str) -> str:
    return _c("33", t)


def _red(t: str) -> str:
    return _c("31", t)


def _bold(t: str) -> str:
    return _c("1", t)


def _dim(t: str) -> str:
    return _c("2", t)


def _status_color(status: str) -> str:
    s = status.lower()
    if s in ("healthy", "running", "open", "active", "ok"):
        return _green(status)
    if s in ("degraded", "pending", "starting", "stopping"):
        return _yellow(status)
    return _red(status)


# ── Transport layer ─────────────────────────────────────────────────

MURPHY_API = os.environ.get("MURPHY_API_URL", "http://127.0.0.1:8000")
MURPHY_LIVE = os.environ.get("MURPHY_LIVE_PATH", "/murphy/live")


def _api_get(path: str, timeout: float = 5.0) -> Optional[dict]:
    url = f"{MURPHY_API}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001  # MURPHY-CLI-ERR-001
        logger.debug("MURPHY-CLI-ERR-001: GET %s failed", url)
        return None


def _api_post(path: str, body: Optional[dict] = None, timeout: float = 10.0) -> Optional[dict]:
    url = f"{MURPHY_API}{path}"
    data = json.dumps(body or {}).encode()
    try:
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001  # MURPHY-CLI-ERR-002
        logger.debug("MURPHY-CLI-ERR-002: POST %s failed", url)
        return None


def _api_delete(path: str, timeout: float = 5.0) -> Optional[dict]:
    url = f"{MURPHY_API}{path}"
    try:
        req = urllib.request.Request(url, method="DELETE")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:  # noqa: BLE001  # MURPHY-CLI-ERR-003
        logger.debug("MURPHY-CLI-ERR-003: DELETE %s failed", url)
        return None


def _read_live(relpath: str) -> Optional[str]:
    fpath = os.path.join(MURPHY_LIVE, relpath.lstrip("/"))
    try:
        with open(fpath) as fh:
            return fh.read()
    except OSError:  # MURPHY-CLI-ERR-004
        logger.debug("MURPHY-CLI-ERR-004: cannot read live file %s", fpath)
        return None


def _dbus_call(interface: str, method: str, *args: Any) -> Optional[Any]:
    """Try calling a Murphy D-Bus method.  Returns None on failure."""
    try:
        import asyncio

        from dbus_next.aio import MessageBus
        from dbus_next import Variant  # noqa: F401

        async def _call():
            bus = await MessageBus().connect()
            introspection = await bus.introspect("org.murphy.System", "/org/murphy/System")
            proxy = bus.get_proxy_object("org.murphy.System", "/org/murphy/System", introspection)
            iface = proxy.get_interface(interface)
            func = getattr(iface, f"call_{method}")
            result = await func(*args)
            bus.disconnect()
            return result

        return asyncio.get_event_loop().run_until_complete(_call())
    except Exception:  # noqa: BLE001  # MURPHY-CLI-ERR-005
        logger.debug("MURPHY-CLI-ERR-005: D-Bus call %s.%s failed", interface, method)
        return None


def _get(api_path: str, live_file: str, dbus_iface: Optional[str] = None,
         dbus_method: Optional[str] = None) -> Optional[Any]:
    """Unified getter: D-Bus → REST → filesystem."""
    if dbus_iface and dbus_method:
        result = _dbus_call(dbus_iface, dbus_method)
        if result is not None:
            return result
    result = _api_get(api_path)
    if result is not None:
        return result
    text = _read_live(live_file)
    if text is not None:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):  # MURPHY-CLI-ERR-006
            logger.debug("MURPHY-CLI-ERR-006: failed to parse live file as JSON: %s", live_file)
            return text.strip()
    return None


# ── Output helpers ──────────────────────────────────────────────────

_JSON_MODE = False
_QUIET = False


def _output(data: Any, label: str = "") -> None:
    if _QUIET:
        return
    if _JSON_MODE:
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"  {_bold(k)}: {v}")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                parts = "  ".join(f"{_bold(k)}={v}" for k, v in item.items())
                print(f"  {parts}")
            else:
                print(f"  {item}")
    else:
        print(data)


def _error(msg: str) -> None:
    sys.stderr.write(f"{_red('error')}: {msg}\n")


# ── Subcommands ─────────────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    """Show runtime health, confidence score, active engines, and PQC status."""
    health = _get("/api/health", "system/health", "org.murphy.ControlPlane", "Health")
    confidence_raw = _get(
        "/api/compute-plane/statistics", "confidence",
        "org.murphy.Confidence", "GetScore",
    )
    engines = _get("/api/engines", "engines/", "org.murphy.ControlPlane", "ListEngines")
    pqc = _api_get("/api/pqc/status")

    if health is None and confidence_raw is None:
        _error("Cannot reach Murphy runtime")
        return EXIT_ERROR

    if _JSON_MODE:
        _output({"health": health, "confidence": confidence_raw, "engines": engines, "pqc": pqc})
        return EXIT_OK

    # Health
    if isinstance(health, dict):
        hs = health.get("status", "unknown")
        print(f"  {_bold('Health')}: {_status_color(hs)}")
        uptime = health.get("uptime")
        if uptime:
            print(f"  {_bold('Uptime')}: {uptime}")
        safety = health.get("safety_level", health.get("safety"))
        if safety:
            print(f"  {_bold('Safety')}: {safety}")
    else:
        print(f"  {_bold('Health')}: {health}")

    # Confidence
    if isinstance(confidence_raw, dict):
        score = confidence_raw.get("confidence", confidence_raw.get("mfgc", "?"))
    else:
        score = confidence_raw
    try:
        score_f = float(score)
        if score_f >= 0.7:
            sc = _green(f"{score_f:.4f}")
        elif score_f >= 0.4:
            sc = _yellow(f"{score_f:.4f}")
        else:
            sc = _red(f"{score_f:.4f}")
        print(f"  {_bold('Confidence')}: {sc}")
    except (ValueError, TypeError):  # MURPHY-CLI-ERR-007
        logger.debug("MURPHY-CLI-ERR-007: non-numeric confidence score: %s", score)
        print(f"  {_bold('Confidence')}: {score}")

    # Engines
    if engines:
        eng_list = engines if isinstance(engines, list) else (engines.get("engines", []) if isinstance(engines, dict) else [])
        active = sum(1 for e in eng_list if isinstance(e, dict) and e.get("status") == "running")
        total = len(eng_list)
        print(f"  {_bold('Engines')}: {active}/{total} running")

    # PQC
    if pqc and isinstance(pqc, dict):
        algo = pqc.get("algorithm", "?")
        epoch = pqc.get("key_epoch", "?")
        print(f"  {_bold('PQC')}: {algo}  epoch={epoch}")

    return EXIT_OK


def cmd_forge(args: argparse.Namespace) -> int:
    """Invoke the forge pipeline."""
    prompt = " ".join(args.prompt)
    if not prompt:
        _error("Forge prompt is required")
        return EXIT_ERROR

    if not _QUIET:
        print(f"{_bold('Forging')}: {_dim(prompt)}")
        print()

    # Try D-Bus first
    result = _dbus_call("org.murphy.Forge", "Build", prompt)
    if result is None:
        result = _api_post("/api/forge/build", {"prompt": prompt})
    if result is None:
        _error("Forge invocation failed — Murphy runtime unreachable")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(result)
    else:
        if isinstance(result, dict):
            status = result.get("status", "complete")
            print(f"  {_bold('Status')}: {_status_color(status)}")
            deliverable = result.get("deliverable", result.get("output", result.get("result")))
            if deliverable:
                print(f"\n{deliverable}")
        else:
            print(result)

    return EXIT_OK


def cmd_swarm_list(args: argparse.Namespace) -> int:
    """List active swarm agents."""
    data = _get("/api/swarm/agents", "swarm/", "org.murphy.Swarm", "ListAgents")
    if data is None:
        _error("Cannot list swarm agents")
        return EXIT_ERROR

    agents = data if isinstance(data, list) else (data.get("agents", []) if isinstance(data, dict) else [])
    if _JSON_MODE:
        _output(agents)
        return EXIT_OK

    if not agents:
        print("  No active agents")
        return EXIT_OK

    fmt = "  {:<38s} {:<16s} {:<12s} {}"
    print(fmt.format("ID", "ROLE", "STATUS", "RESOURCES"))
    print(fmt.format("─" * 36, "─" * 14, "─" * 10, "─" * 20))
    for a in agents:
        if isinstance(a, dict):
            aid = str(a.get("id", a.get("uuid", "?")))
            role = a.get("role", "?")
            st = a.get("status", "?")
            res = a.get("resources", "")
            if isinstance(res, dict):
                res = f"cpu={res.get('cpu', '?')} mem={res.get('memory', '?')}"
            print(fmt.format(aid, role, _status_color(st), str(res)))
        else:
            print(f"  {a}")

    return EXIT_OK


def cmd_swarm_spawn(args: argparse.Namespace) -> int:
    """Spawn a new swarm agent."""
    result = _dbus_call("org.murphy.Swarm", "Spawn", args.role)
    if result is None:
        result = _api_post("/api/swarm/agents", {"role": args.role})
    if result is None:
        _error(f"Failed to spawn agent with role '{args.role}'")
        return EXIT_ERROR
    _output(result)
    return EXIT_OK


def cmd_swarm_kill(args: argparse.Namespace) -> int:
    """Terminate a swarm agent."""
    result = _dbus_call("org.murphy.Swarm", "Kill", args.agent_id)
    if result is None:
        result = _api_delete(f"/api/swarm/agents/{args.agent_id}")
    if result is None:
        _error(f"Failed to kill agent '{args.agent_id}'")
        return EXIT_ERROR
    if not _QUIET:
        print(f"  Agent {args.agent_id} terminated")
    return EXIT_OK


def cmd_gate_list(args: argparse.Namespace) -> int:
    """Show all gate statuses."""
    data = _get("/api/gates", "gates/", "org.murphy.HITL", "ListGates")
    if data is None:
        _error("Cannot retrieve gate statuses")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(data)
        return EXIT_OK

    gates = data if isinstance(data, dict) else {}
    if isinstance(data, list):
        gates = {g.get("name", f"gate-{i}"): g.get("status", "?") for i, g in enumerate(data)}

    gate_order = ["EXECUTIVE", "OPERATIONS", "QA", "HITL", "COMPLIANCE", "BUDGET"]
    for name in gate_order:
        status = gates.get(name, gates.get(name.lower(), "unknown"))
        if isinstance(status, dict):
            status = status.get("status", "unknown")
        print(f"  {_bold(name):>20s}  {_status_color(str(status))}")

    return EXIT_OK


def cmd_gate_approve(args: argparse.Namespace) -> int:
    """Approve a pending HITL request."""
    result = _dbus_call("org.murphy.HITL", "Approve", args.request_id)
    if result is None:
        result = _api_post("/api/gates/HITL/action", {"action": "approve", "request_id": args.request_id})
    if result is None:
        live_path = os.path.join(MURPHY_LIVE, "gates", "HITL")
        try:
            with open(live_path, "w") as fh:
                fh.write(f"approve {args.request_id}\n")
            result = {"status": "approved"}
        except OSError:  # MURPHY-CLI-ERR-008
            logger.debug("MURPHY-CLI-ERR-008: gate approve filesystem fallback failed for %s", args.request_id)
            _error(f"Failed to approve request '{args.request_id}'")
            return EXIT_ERROR
    if not _QUIET:
        print(f"  Request {args.request_id} approved")
    return EXIT_OK


def cmd_gate_deny(args: argparse.Namespace) -> int:
    """Deny a pending HITL request."""
    result = _dbus_call("org.murphy.HITL", "Deny", args.request_id)
    if result is None:
        result = _api_post("/api/gates/HITL/action", {"action": "deny", "request_id": args.request_id})
    if result is None:
        live_path = os.path.join(MURPHY_LIVE, "gates", "HITL")
        try:
            with open(live_path, "w") as fh:
                fh.write(f"deny {args.request_id}\n")
            result = {"status": "denied"}
        except OSError:  # MURPHY-CLI-ERR-009
            logger.debug("MURPHY-CLI-ERR-009: gate deny filesystem fallback failed for %s", args.request_id)
            _error(f"Failed to deny request '{args.request_id}'")
            return EXIT_ERROR
    if not _QUIET:
        print(f"  Request {args.request_id} denied")
    return EXIT_OK


def cmd_engine_list(args: argparse.Namespace) -> int:
    """List all engines and status."""
    data = _get("/api/engines", "engines/", "org.murphy.ControlPlane", "ListEngines")
    if data is None:
        _error("Cannot list engines")
        return EXIT_ERROR

    engines = data if isinstance(data, list) else (data.get("engines", []) if isinstance(data, dict) else [])
    if _JSON_MODE:
        _output(engines)
        return EXIT_OK

    if not engines:
        print("  No engines registered")
        return EXIT_OK

    fmt = "  {:<24s} {:<12s} {}"
    print(fmt.format("NAME", "STATUS", "TYPE"))
    print(fmt.format("─" * 22, "─" * 10, "─" * 16))
    for e in engines:
        if isinstance(e, dict):
            name = e.get("name", "?")
            st = e.get("status", "?")
            etype = e.get("type", e.get("engine_type", ""))
            print(fmt.format(name, _status_color(st), etype))
        else:
            print(f"  {e}")

    return EXIT_OK


def cmd_engine_start(args: argparse.Namespace) -> int:
    """Start an engine."""
    result = _dbus_call("org.murphy.ControlPlane", "StartEngine", args.name)
    if result is None:
        result = _api_post(f"/api/engines/{args.name}/start")
    if result is None:
        _error(f"Failed to start engine '{args.name}'")
        return EXIT_ERROR
    if not _QUIET:
        print(f"  Engine '{args.name}' started")
    return EXIT_OK


def cmd_engine_stop(args: argparse.Namespace) -> int:
    """Stop an engine."""
    result = _dbus_call("org.murphy.ControlPlane", "StopEngine", args.name)
    if result is None:
        result = _api_post(f"/api/engines/{args.name}/stop")
    if result is None:
        _error(f"Failed to stop engine '{args.name}'")
        return EXIT_ERROR
    if not _QUIET:
        print(f"  Engine '{args.name}' stopped")
    return EXIT_OK


def cmd_log_tail(args: argparse.Namespace) -> int:
    """Stream Event Backbone events."""
    events_path = os.path.join(MURPHY_LIVE, "events")
    try:
        with open(events_path) as fh:
            if not _QUIET:
                print(_dim("Streaming events (Ctrl+C to stop)…"))
            while True:
                line = fh.readline()
                if line:
                    print(line, end="")
                else:
                    time.sleep(0.25)
    except FileNotFoundError:  # MURPHY-CLI-ERR-010
        logger.debug("MURPHY-CLI-ERR-010: event stream file not found: %s", events_path)
        data = _api_get("/api/events/stream")
        if data is None:
            _error("Cannot stream events — /murphy/live/events not found and API unreachable")
            return EXIT_ERROR
        _output(data)
    except KeyboardInterrupt:  # MURPHY-CLI-ERR-011
        logger.debug("MURPHY-CLI-ERR-011: event streaming interrupted by user")
    return EXIT_OK


def cmd_log_search(args: argparse.Namespace) -> int:
    """Search logs."""
    query = " ".join(args.query)
    data = _api_get(f"/api/logs/search?q={urllib.request.quote(query)}")
    if data is None:
        _error("Log search failed")
        return EXIT_ERROR
    _output(data)
    return EXIT_OK


def cmd_confidence(args: argparse.Namespace) -> int:
    """Print current MFGC score."""
    result = _get(
        "/api/compute-plane/statistics", "confidence",
        "org.murphy.Confidence", "GetScore",
    )
    if result is None:
        _error("Cannot read confidence score")
        return EXIT_ERROR

    if isinstance(result, dict):
        score = result.get("confidence", result.get("mfgc", "?"))
    else:
        score = result

    if _JSON_MODE:
        _output({"confidence": score})
    else:
        try:
            score_f = float(score)
            if score_f >= 0.7:
                print(_green(f"{score_f:.4f}"))
            elif score_f >= 0.4:
                print(_yellow(f"{score_f:.4f}"))
            else:
                print(_red(f"{score_f:.4f}"))
        except (ValueError, TypeError):  # MURPHY-CLI-ERR-012
            logger.debug("MURPHY-CLI-ERR-012: non-numeric confidence score: %s", score)
            print(score)
    return EXIT_OK


def cmd_config_get(args: argparse.Namespace) -> int:
    """Get a config value."""
    data = _api_get(f"/api/config/{args.key}")
    if data is None:
        _error(f"Config key '{args.key}' not found")
        return EXIT_ERROR
    _output(data)
    return EXIT_OK


def cmd_config_set(args: argparse.Namespace) -> int:
    """Set a config value."""
    result = _api_post(f"/api/config/{args.key}", {"value": args.value})
    if result is None:
        _error(f"Failed to set config '{args.key}'")
        return EXIT_ERROR
    if not _QUIET:
        print(f"  {args.key} = {args.value}")
    return EXIT_OK


def cmd_pqc_status(args: argparse.Namespace) -> int:
    """Show PQC key status."""
    data = _api_get("/api/pqc/status")
    if data is None:
        _error("Cannot retrieve PQC status")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(data)
        return EXIT_OK

    if isinstance(data, dict):
        print(f"  {_bold('Algorithm')}:   {data.get('algorithm', '?')}")
        print(f"  {_bold('Key Epoch')}:   {data.get('key_epoch', '?')}")
        print(f"  {_bold('Certificate')}: {data.get('certificate', data.get('cert', '?'))}")
        print(f"  {_bold('Status')}:      {_status_color(str(data.get('status', 'unknown')))}")
        next_rot = data.get("next_rotation")
        if next_rot:
            print(f"  {_bold('Next Rotation')}: {next_rot}")
    else:
        print(data)
    return EXIT_OK


def cmd_pqc_rotate(args: argparse.Namespace) -> int:
    """Force PQC key rotation."""
    result = _api_post("/api/pqc/rotate")
    if result is None:
        _error("PQC key rotation failed")
        return EXIT_ERROR
    if not _QUIET:
        if isinstance(result, dict):
            print(f"  Key rotated — new epoch: {result.get('key_epoch', '?')}")
        else:
            print("  Key rotation initiated")
    return EXIT_OK


def cmd_pqc_verify(args: argparse.Namespace) -> int:
    """Verify runtime integrity using PQC signatures."""
    result = _api_get("/api/pqc/verify")
    if result is None:
        _error("PQC verification failed")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(result)
        return EXIT_OK

    if isinstance(result, dict):
        ok = result.get("verified", result.get("valid", False))
        if ok:
            print(f"  {_green('✓')} Runtime integrity verified")
        else:
            print(f"  {_red('✗')} Integrity check FAILED")
            return EXIT_ERROR
    else:
        print(result)
    return EXIT_OK


def cmd_version(args: argparse.Namespace) -> int:
    """Print version info."""
    data = _get("/api/version", "system/version")
    if isinstance(data, dict):
        ver = data.get("version", __version__)
    elif isinstance(data, str):
        ver = data.strip()
    else:
        ver = __version__
    if _JSON_MODE:
        _output({"version": ver, "cli_version": __version__})
    else:
        print(f"Murphy CLI v{__version__}")
        if ver != __version__:
            print(f"Murphy Runtime v{ver}")
    return EXIT_OK


# ── LLM governor commands ──────────────────────────────────────────

def cmd_llm_status(args: argparse.Namespace) -> int:
    """Show per-provider usage, budgets, health, and rate limits."""
    data = _get("/api/llm/status", "llm/status")
    if data is None:
        _error("Cannot retrieve LLM governor status")  # MURPHY-CLI-ERR-015
        logger.debug("MURPHY-CLI-ERR-015: LLM governor status retrieval failed")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(data)
        return EXIT_OK

    if isinstance(data, dict):
        providers = data.get("providers", [])
        if isinstance(providers, list) and providers:
            fmt = "  {:<20s} {:<12s} {:<14s} {:<12s} {}"
            print(fmt.format("PROVIDER", "STATUS", "TOKENS USED", "BUDGET", "RATE LIMIT"))
            print(fmt.format("─" * 18, "─" * 10, "─" * 12, "─" * 10, "─" * 14))
            for p in providers:
                if isinstance(p, dict):
                    name = p.get("name", "?")
                    st = p.get("status", "?")
                    tokens = str(p.get("tokens_used", "?"))
                    budget = str(p.get("budget", "?"))
                    rate = str(p.get("rate_limit", "?"))
                    print(fmt.format(name, _status_color(st), tokens, budget, rate))
        else:
            _output(data)
    else:
        print(data)
    return EXIT_OK


def cmd_llm_usage(args: argparse.Namespace) -> int:
    """Show token/cost usage stats, optionally filtered by provider."""
    path = "/api/llm/usage"
    if args.provider:
        path = f"/api/llm/usage/{args.provider}"
    data = _api_get(path)
    if data is None:
        _error("Cannot retrieve LLM usage stats")  # MURPHY-CLI-ERR-015
        logger.debug("MURPHY-CLI-ERR-015: LLM governor status retrieval failed")
        return EXIT_ERROR
    _output(data)
    return EXIT_OK


def cmd_llm_health(args: argparse.Namespace) -> int:
    """Show provider health (latency p50/p95/p99, error rate)."""
    data = _api_get("/api/llm/health")
    if data is None:
        _error("Cannot retrieve LLM provider health")  # MURPHY-CLI-ERR-016
        logger.debug("MURPHY-CLI-ERR-016: LLM governor health retrieval failed")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(data)
        return EXIT_OK

    if isinstance(data, dict):
        providers = data.get("providers", [])
        if isinstance(providers, list) and providers:
            fmt = "  {:<20s} {:<10s} {:<10s} {:<10s} {}"
            print(fmt.format("PROVIDER", "p50", "p95", "p99", "ERROR RATE"))
            print(fmt.format("─" * 18, "─" * 8, "─" * 8, "─" * 8, "─" * 12))
            for p in providers:
                if isinstance(p, dict):
                    name = p.get("name", "?")
                    p50 = str(p.get("p50", "?"))
                    p95 = str(p.get("p95", "?"))
                    p99 = str(p.get("p99", "?"))
                    err = str(p.get("error_rate", "?"))
                    print(fmt.format(name, p50, p95, p99, err))
        else:
            _output(data)
    else:
        print(data)
    return EXIT_OK


# ── Backup commands ────────────────────────────────────────────────

def cmd_backup_create(args: argparse.Namespace) -> int:
    """Trigger a new backup."""
    body: Dict[str, Any] = {}
    if args.label:
        body["label"] = args.label
    result = _api_post("/api/backup/create", body)
    if result is None:
        _error("Backup creation failed")  # MURPHY-CLI-ERR-017
        logger.debug("MURPHY-CLI-ERR-017: backup create operation failed")
        return EXIT_ERROR
    if _JSON_MODE:
        _output(result)
    elif not _QUIET:
        bid = result.get("backup_id", "?") if isinstance(result, dict) else result
        print(f"  Backup created: {bid}")
    return EXIT_OK


def cmd_backup_list(args: argparse.Namespace) -> int:
    """List available backups."""
    data = _get("/api/backup/list", "backup/")
    if data is None:
        _error("Cannot list backups")  # MURPHY-CLI-ERR-018
        logger.debug("MURPHY-CLI-ERR-018: backup list retrieval failed")
        return EXIT_ERROR

    backups = data if isinstance(data, list) else (data.get("backups", []) if isinstance(data, dict) else [])
    if _JSON_MODE:
        _output(backups)
        return EXIT_OK

    if not backups:
        print("  No backups available")
        return EXIT_OK

    fmt = "  {:<38s} {:<20s} {:<12s} {}"
    print(fmt.format("ID", "CREATED", "SIZE", "LABEL"))
    print(fmt.format("─" * 36, "─" * 18, "─" * 10, "─" * 16))
    for b in backups:
        if isinstance(b, dict):
            bid = str(b.get("id", b.get("backup_id", "?")))
            created = str(b.get("created", b.get("timestamp", "?")))
            size = str(b.get("size", "?"))
            label = str(b.get("label", ""))
            print(fmt.format(bid, created, size, label))
        else:
            print(f"  {b}")

    return EXIT_OK


def cmd_backup_verify(args: argparse.Namespace) -> int:
    """Verify backup integrity."""
    result = _api_get(f"/api/backup/{args.backup_id}/verify")
    if result is None:
        _error(f"Failed to verify backup '{args.backup_id}'")  # MURPHY-CLI-ERR-019
        logger.debug("MURPHY-CLI-ERR-019: backup verify operation failed for %s", args.backup_id)
        return EXIT_ERROR

    if _JSON_MODE:
        _output(result)
        return EXIT_OK

    if isinstance(result, dict):
        ok = result.get("verified", result.get("valid", False))
        if ok:
            print(f"  {_green('✓')} Backup {args.backup_id} integrity verified")
        else:
            print(f"  {_red('✗')} Backup {args.backup_id} integrity check FAILED")
            return EXIT_ERROR
    else:
        print(result)
    return EXIT_OK


def cmd_backup_restore(args: argparse.Namespace) -> int:
    """Restore from a backup."""
    result = _api_post(f"/api/backup/{args.backup_id}/restore")
    if result is None:
        _error(f"Failed to restore backup '{args.backup_id}'")  # MURPHY-CLI-ERR-020
        logger.debug("MURPHY-CLI-ERR-020: backup restore operation failed for %s", args.backup_id)
        return EXIT_ERROR
    if _JSON_MODE:
        _output(result)
    elif not _QUIET:
        print(f"  Restore from backup {args.backup_id} initiated")
    return EXIT_OK


# ── Telemetry commands ─────────────────────────────────────────────

def cmd_telemetry_status(args: argparse.Namespace) -> int:
    """Show metric collection status."""
    data = _get("/api/telemetry/status", "telemetry/status")
    if data is None:
        _error("Cannot retrieve telemetry status")  # MURPHY-CLI-ERR-021
        logger.debug("MURPHY-CLI-ERR-021: telemetry status retrieval failed")
        return EXIT_ERROR

    if _JSON_MODE:
        _output(data)
        return EXIT_OK

    if isinstance(data, dict):
        st = data.get("status", "unknown")
        print(f"  {_bold('Collection')}: {_status_color(st)}")
        scrapers = data.get("scrapers", data.get("collectors"))
        if scrapers is not None:
            print(f"  {_bold('Scrapers')}:   {scrapers}")
        interval = data.get("interval")
        if interval is not None:
            print(f"  {_bold('Interval')}:   {interval}")
        metrics = data.get("metrics_count", data.get("total_metrics"))
        if metrics is not None:
            print(f"  {_bold('Metrics')}:    {metrics}")
    else:
        print(data)
    return EXIT_OK


def cmd_telemetry_dump(args: argparse.Namespace) -> int:
    """Dump current metrics in Prometheus exposition format."""
    data = _api_get("/api/telemetry/metrics")
    if data is not None:
        if _JSON_MODE:
            _output(data)
        else:
            if isinstance(data, dict):
                raw = data.get("metrics", data.get("data", ""))
                print(raw)
            else:
                print(data)
        return EXIT_OK

    # Fall back to reading the node-exporter prom file
    prom_path = "/var/lib/prometheus/node-exporter/murphy.prom"
    try:
        with open(prom_path) as fh:
            print(fh.read())
        return EXIT_OK
    except OSError:  # MURPHY-CLI-ERR-022
        logger.debug("MURPHY-CLI-ERR-022: telemetry metrics dump failed, prom file: %s", prom_path)

    _error("Cannot dump telemetry metrics — API unreachable and prom file not found")
    return EXIT_ERROR


# ── Cgroup commands ────────────────────────────────────────────────

CGROUP_BASE = "/sys/fs/cgroup/murphy.slice"


def cmd_cgroup_list(args: argparse.Namespace) -> int:
    """List all Murphy cgroup scopes."""
    data = _api_get("/api/cgroup/status")
    if data is not None:
        scopes = data if isinstance(data, list) else (data.get("scopes", []) if isinstance(data, dict) else [])
        if _JSON_MODE:
            _output(scopes)
            return EXIT_OK
        if not scopes:
            print("  No cgroup scopes found")
            return EXIT_OK
        fmt = "  {:<30s} {:<14s} {}"
        print(fmt.format("SCOPE", "STATUS", "RESOURCES"))
        print(fmt.format("─" * 28, "─" * 12, "─" * 20))
        for s in scopes:
            if isinstance(s, dict):
                name = s.get("name", s.get("scope", "?"))
                st = s.get("status", "?")
                res = s.get("resources", "")
                if isinstance(res, dict):
                    res = f"cpu={res.get('cpu', '?')} mem={res.get('memory', '?')}"
                print(fmt.format(str(name), _status_color(str(st)), str(res)))
            else:
                print(f"  {s}")
        return EXIT_OK

    # Fall back to reading cgroup filesystem
    try:
        entries = os.listdir(CGROUP_BASE)
    except OSError:  # MURPHY-CLI-ERR-023
        logger.debug("MURPHY-CLI-ERR-023: cgroup listing failed, path: %s", CGROUP_BASE)
        _error("Cannot list cgroup scopes — API unreachable and cgroup fs not found")
        return EXIT_ERROR

    scopes = [e for e in entries if os.path.isdir(os.path.join(CGROUP_BASE, e))]
    if _JSON_MODE:
        _output(scopes)
        return EXIT_OK
    if not scopes:
        print("  No cgroup scopes found")
        return EXIT_OK
    for scope in sorted(scopes):
        print(f"  {scope}")
    return EXIT_OK


def cmd_cgroup_usage(args: argparse.Namespace) -> int:
    """Show resource usage for a cgroup scope."""
    scope = args.scope
    if scope:
        data = _api_get(f"/api/cgroup/status/{scope}")
    else:
        data = _api_get("/api/cgroup/status")
    if data is not None:
        _output(data)
        return EXIT_OK

    # Fall back to cgroup filesystem
    scope_path = os.path.join(CGROUP_BASE, scope) if scope else CGROUP_BASE
    info: Dict[str, str] = {}
    for fname in ("cpu.stat", "memory.current", "memory.max", "pids.current"):
        fpath = os.path.join(scope_path, fname)
        try:
            with open(fpath) as fh:
                info[fname] = fh.read().strip()
        except OSError:
            pass

    if not info:
        _error(f"Cannot read cgroup usage for '{scope or 'murphy.slice'}'")  # MURPHY-CLI-ERR-023
        logger.debug("MURPHY-CLI-ERR-023: cgroup usage retrieval failed for scope: %s", scope)
        return EXIT_ERROR

    if _JSON_MODE:
        _output(info)
    else:
        for k, v in info.items():
            print(f"  {_bold(k)}: {v}")
    return EXIT_OK


# ── Module lifecycle commands ──────────────────────────────────────

def cmd_module_list(args: argparse.Namespace) -> int:
    """List registered modules."""
    data = _get("/api/module/list", "modules/")
    if data is None:
        _error("Cannot list modules")  # MURPHY-CLI-ERR-024
        logger.debug("MURPHY-CLI-ERR-024: module lifecycle operation failed (list)")
        return EXIT_ERROR

    modules = data if isinstance(data, list) else (data.get("modules", []) if isinstance(data, dict) else [])
    if _JSON_MODE:
        _output(modules)
        return EXIT_OK

    if not modules:
        print("  No modules registered")
        return EXIT_OK

    fmt = "  {:<28s} {:<12s} {}"
    print(fmt.format("NAME", "STATUS", "VERSION"))
    print(fmt.format("─" * 26, "─" * 10, "─" * 14))
    for m in modules:
        if isinstance(m, dict):
            name = m.get("name", "?")
            st = m.get("status", "?")
            ver = m.get("version", "")
            print(fmt.format(str(name), _status_color(str(st)), str(ver)))
        else:
            print(f"  {m}")

    return EXIT_OK


def cmd_module_start(args: argparse.Namespace) -> int:
    """Start a module."""
    result = _api_post(f"/api/module/{args.name}/start")
    if result is None:
        _error(f"Failed to start module '{args.name}'")  # MURPHY-CLI-ERR-024
        logger.debug("MURPHY-CLI-ERR-024: module lifecycle operation failed (start %s)", args.name)
        return EXIT_ERROR
    if not _QUIET:
        print(f"  Module '{args.name}' started")
    return EXIT_OK


def cmd_module_stop(args: argparse.Namespace) -> int:
    """Stop a module."""
    result = _api_post(f"/api/module/{args.name}/stop")
    if result is None:
        _error(f"Failed to stop module '{args.name}'")  # MURPHY-CLI-ERR-024
        logger.debug("MURPHY-CLI-ERR-024: module lifecycle operation failed (stop %s)", args.name)
        return EXIT_ERROR
    if not _QUIET:
        print(f"  Module '{args.name}' stopped")
    return EXIT_OK


def cmd_module_status(args: argparse.Namespace) -> int:
    """Show module status."""
    data = _get(f"/api/module/{args.name}/status", f"modules/{args.name}")
    if data is None:
        _error(f"Cannot retrieve status for module '{args.name}'")  # MURPHY-CLI-ERR-024
        logger.debug("MURPHY-CLI-ERR-024: module lifecycle operation failed (status %s)", args.name)
        return EXIT_ERROR
    _output(data)
    return EXIT_OK


# ── Argument parser ─────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="murphy",
        description="Murphy CLI — command-line interface for the Murphy runtime.",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-essential output")
    parser.add_argument(
        "--api-url",
        default=None,
        help="Override Murphy REST API URL (default: MURPHY_API_URL or http://127.0.0.1:8000)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Show runtime health and status")

    # forge
    p_forge = sub.add_parser("forge", help="Invoke the forge pipeline")
    p_forge.add_argument("prompt", nargs="+", help="Natural-language build prompt")

    # swarm
    p_swarm = sub.add_parser("swarm", help="Swarm agent management")
    swarm_sub = p_swarm.add_subparsers(dest="swarm_cmd")
    swarm_sub.add_parser("list", help="List active agents")
    p_ss = swarm_sub.add_parser("spawn", help="Spawn a new agent")
    p_ss.add_argument("role", help="Agent role name")
    p_sk = swarm_sub.add_parser("kill", help="Terminate an agent")
    p_sk.add_argument("agent_id", help="Agent UUID")

    # gate
    p_gate = sub.add_parser("gate", help="Governance gate management")
    gate_sub = p_gate.add_subparsers(dest="gate_cmd")
    gate_sub.add_parser("list", help="Show all gate statuses")
    p_ga = gate_sub.add_parser("approve", help="Approve pending HITL request")
    p_ga.add_argument("request_id", help="Request ID to approve")
    p_gd = gate_sub.add_parser("deny", help="Deny pending HITL request")
    p_gd.add_argument("request_id", help="Request ID to deny")

    # engine
    p_engine = sub.add_parser("engine", help="Engine control")
    engine_sub = p_engine.add_subparsers(dest="engine_cmd")
    engine_sub.add_parser("list", help="List all engines")
    p_es = engine_sub.add_parser("start", help="Start an engine")
    p_es.add_argument("name", help="Engine name")
    p_ep = engine_sub.add_parser("stop", help="Stop an engine")
    p_ep.add_argument("name", help="Engine name")

    # log
    p_log = sub.add_parser("log", help="Event log operations")
    log_sub = p_log.add_subparsers(dest="log_cmd")
    log_sub.add_parser("tail", help="Stream Event Backbone events")
    p_ls = log_sub.add_parser("search", help="Search logs")
    p_ls.add_argument("query", nargs="+", help="Search query")

    # confidence
    sub.add_parser("confidence", help="Print current MFGC score")

    # config
    p_cfg = sub.add_parser("config", help="Configuration management")
    cfg_sub = p_cfg.add_subparsers(dest="config_cmd")
    p_cg = cfg_sub.add_parser("get", help="Get a config value")
    p_cg.add_argument("key", help="Config key")
    p_cs = cfg_sub.add_parser("set", help="Set a config value")
    p_cs.add_argument("key", help="Config key")
    p_cs.add_argument("value", help="Config value")

    # pqc
    p_pqc = sub.add_parser("pqc", help="Post-quantum cryptography operations")
    pqc_sub = p_pqc.add_subparsers(dest="pqc_cmd")
    pqc_sub.add_parser("status", help="Show PQC key status")
    pqc_sub.add_parser("rotate", help="Force key rotation")
    pqc_sub.add_parser("verify", help="Verify runtime integrity")

    # llm
    p_llm = sub.add_parser("llm", help="LLM governor operations")
    llm_sub = p_llm.add_subparsers(dest="llm_cmd")
    llm_sub.add_parser("status", help="Show per-provider usage, budgets, health")
    p_lu = llm_sub.add_parser("usage", help="Show token/cost usage stats")
    p_lu.add_argument("provider", nargs="?", default=None, help="Filter by provider name")
    llm_sub.add_parser("health", help="Show provider health (latency, error rate)")

    # backup
    p_bak = sub.add_parser("backup", help="Backup operations")
    bak_sub = p_bak.add_subparsers(dest="backup_cmd")
    p_bc = bak_sub.add_parser("create", help="Trigger a new backup")
    p_bc.add_argument("--label", default=None, help="Optional label for the backup")
    bak_sub.add_parser("list", help="List available backups")
    p_bv = bak_sub.add_parser("verify", help="Verify backup integrity")
    p_bv.add_argument("backup_id", help="Backup ID to verify")
    p_br = bak_sub.add_parser("restore", help="Restore from backup")
    p_br.add_argument("backup_id", help="Backup ID to restore")

    # telemetry
    p_tel = sub.add_parser("telemetry", help="Telemetry/metrics operations")
    tel_sub = p_tel.add_subparsers(dest="telemetry_cmd")
    tel_sub.add_parser("status", help="Show metric collection status")
    tel_sub.add_parser("dump", help="Dump current metrics (Prometheus format)")

    # cgroup
    p_cg = sub.add_parser("cgroup", help="Resource isolation status")
    cg_sub = p_cg.add_subparsers(dest="cgroup_cmd")
    cg_sub.add_parser("list", help="List all Murphy cgroup scopes")
    p_cgu = cg_sub.add_parser("usage", help="Show resource usage for a scope")
    p_cgu.add_argument("scope", nargs="?", default=None, help="Cgroup scope name")

    # module
    p_mod = sub.add_parser("module", help="Module lifecycle management")
    mod_sub = p_mod.add_subparsers(dest="module_cmd")
    mod_sub.add_parser("list", help="List registered modules")
    p_ms = mod_sub.add_parser("start", help="Start a module")
    p_ms.add_argument("name", help="Module name")
    p_mp = mod_sub.add_parser("stop", help="Stop a module")
    p_mp.add_argument("name", help="Module name")
    p_mst = mod_sub.add_parser("status", help="Show module status")
    p_mst.add_argument("name", help="Module name")

    # version
    sub.add_parser("version", help="Print version info")

    return parser


# ── Dispatch ────────────────────────────────────────────────────────

_DISPATCH = {
    ("status", None): cmd_status,
    ("forge", None): cmd_forge,
    ("swarm", "list"): cmd_swarm_list,
    ("swarm", "spawn"): cmd_swarm_spawn,
    ("swarm", "kill"): cmd_swarm_kill,
    ("gate", "list"): cmd_gate_list,
    ("gate", "approve"): cmd_gate_approve,
    ("gate", "deny"): cmd_gate_deny,
    ("engine", "list"): cmd_engine_list,
    ("engine", "start"): cmd_engine_start,
    ("engine", "stop"): cmd_engine_stop,
    ("log", "tail"): cmd_log_tail,
    ("log", "search"): cmd_log_search,
    ("confidence", None): cmd_confidence,
    ("config", "get"): cmd_config_get,
    ("config", "set"): cmd_config_set,
    ("pqc", "status"): cmd_pqc_status,
    ("pqc", "rotate"): cmd_pqc_rotate,
    ("pqc", "verify"): cmd_pqc_verify,
    ("llm", "status"): cmd_llm_status,
    ("llm", "usage"): cmd_llm_usage,
    ("llm", "health"): cmd_llm_health,
    ("backup", "create"): cmd_backup_create,
    ("backup", "list"): cmd_backup_list,
    ("backup", "verify"): cmd_backup_verify,
    ("backup", "restore"): cmd_backup_restore,
    ("telemetry", "status"): cmd_telemetry_status,
    ("telemetry", "dump"): cmd_telemetry_dump,
    ("cgroup", "list"): cmd_cgroup_list,
    ("cgroup", "usage"): cmd_cgroup_usage,
    ("module", "list"): cmd_module_list,
    ("module", "start"): cmd_module_start,
    ("module", "stop"): cmd_module_stop,
    ("module", "status"): cmd_module_status,
    ("version", None): cmd_version,
}


def main(argv: Optional[List[str]] = None) -> int:
    global _JSON_MODE, _QUIET, MURPHY_API  # noqa: PLW0603

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.json:
        _JSON_MODE = True
    if args.quiet:
        _QUIET = True
    if args.api_url:
        MURPHY_API = args.api_url

    if not args.command:
        parser.print_help()
        return EXIT_OK

    # Determine sub-command key
    subcmd = None
    for attr in ("swarm_cmd", "gate_cmd", "engine_cmd", "log_cmd", "config_cmd", "pqc_cmd",
                 "llm_cmd", "backup_cmd", "telemetry_cmd", "cgroup_cmd", "module_cmd"):
        val = getattr(args, attr, None)
        if val is not None:
            subcmd = val
            break

    handler = _DISPATCH.get((args.command, subcmd))
    if handler is None:
        # If no sub-subcommand, show help for the subparser
        parser.parse_args([args.command, "--help"])
        return EXIT_ERROR

    try:
        return handler(args)
    except KeyboardInterrupt:  # MURPHY-CLI-ERR-013
        logger.debug("MURPHY-CLI-ERR-013: command interrupted by user")
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001  # MURPHY-CLI-ERR-014
        logger.debug("MURPHY-CLI-ERR-014: unhandled exception: %s", exc)
        _error(str(exc))
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
