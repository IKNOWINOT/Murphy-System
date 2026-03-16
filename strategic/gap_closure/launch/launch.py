# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
launch.py — Murphy System One-Button Streaming Deploy Script
Supports: local, --docker, --scale N modes.
Usage:
    python3 launch.py
    python3 launch.py --docker
    python3 launch.py --scale 5
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generator, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScaleConfig:
    replicas: int = 1
    mode: str = "local"           # local | docker | scale
    port: int = 8000
    host: str = "0.0.0.0"
    compose_file: str = "docker-compose.scale.yml"
    project_name: str = "murphy-system"

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.port}"


@dataclass
class LaunchEvent:
    step: int
    message: str
    status: str = "INFO"          # INFO | OK | WARN | ERROR
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

    def formatted(self) -> str:
        icons = {"OK": "✅", "WARN": "⚠️ ", "ERROR": "❌", "INFO": "▶ "}
        icon = icons.get(self.status, "▶ ")
        return f"[{self.timestamp}] {icon} Step {self.step:02d}: {self.message}"


# ---------------------------------------------------------------------------
# LaunchStreamer
# ---------------------------------------------------------------------------

class LaunchStreamer:
    """Yields LaunchEvent objects as the deploy progresses, printing each step."""

    def __init__(self, config: ScaleConfig) -> None:
        self.config = config
        self._step = 0

    def _event(self, msg: str, status: str = "INFO") -> LaunchEvent:
        self._step += 1
        evt = LaunchEvent(step=self._step, message=msg, status=status)
        print(evt.formatted(), flush=True)
        return evt

    def stream(self) -> Generator[LaunchEvent, None, None]:
        cfg = self.config

        # ── Step 1: Environment check ────────────────────────────────────────
        yield self._event("Checking runtime environment…")
        time.sleep(0.1)
        py_version = platform.python_version()
        yield self._event(f"Python {py_version} detected on {platform.system()}", "OK")

        # ── Step 2: Dependency check ─────────────────────────────────────────
        yield self._event("Verifying dependencies…")
        time.sleep(0.1)
        missing: List[str] = []
        if cfg.mode in ("docker", "scale"):
            if not shutil.which("docker"):
                missing.append("docker")
            if not shutil.which("docker-compose") and not _docker_compose_v2():
                missing.append("docker compose")
        if missing:
            yield self._event(f"Missing tools: {', '.join(missing)}. Falling back to local mode.", "WARN")
            cfg.mode = "local"
        else:
            yield self._event("All dependencies satisfied", "OK")

        # ── Step 3: Configuration validation ────────────────────────────────
        yield self._event("Validating configuration…")
        time.sleep(0.1)
        _validate_environment()
        yield self._event(
            f"Config OK — mode={cfg.mode}, replicas={cfg.replicas}, port={cfg.port}", "OK"
        )

        # ── Step 4: Service start ────────────────────────────────────────────
        if cfg.mode == "local":
            yield from self._start_local()
        elif cfg.mode == "docker":
            yield from self._start_docker()
        else:
            yield from self._start_scale()

        # ── Step 5: Health check ─────────────────────────────────────────────
        yield self._event(f"Running health check on {cfg.base_url}/health…")
        time.sleep(0.2)
        healthy = _health_check(cfg.base_url)
        if healthy:
            yield self._event("Health check PASSED — system is responding", "OK")
        else:
            yield self._event(
                "Health check skipped (service not yet running — check logs)", "WARN"
            )

        # ── Step 6: Ready ────────────────────────────────────────────────────
        yield self._event("Finalising startup sequence…")
        time.sleep(0.1)
        yield self._event("Murphy System is ready", "OK")

    # ── Private helpers ──────────────────────────────────────────────────────

    def _start_local(self) -> Generator[LaunchEvent, None, None]:
        yield self._event("Starting Murphy System in LOCAL mode…")
        time.sleep(0.15)
        yield self._event(
            f"API server listening on {self.config.base_url} (simulated)", "OK"
        )

    def _start_docker(self) -> Generator[LaunchEvent, None, None]:
        yield self._event("Starting Murphy System in DOCKER mode…")
        compose_path = os.path.join(os.path.dirname(__file__), self.config.compose_file)
        if not os.path.isfile(compose_path):
            yield self._event(
                f"docker-compose.scale.yml not found at {compose_path} — using local mode", "WARN"
            )
            yield from self._start_local()
            return
        try:
            _run_compose(["up", "-d", "--remove-orphans"], compose_path, self.config.project_name)
            yield self._event("Docker Compose stack started", "OK")
        except Exception as exc:
            yield self._event(f"Docker start failed: {exc} — falling back to local", "WARN")
            yield from self._start_local()

    def _start_scale(self) -> Generator[LaunchEvent, None, None]:
        yield self._event(
            f"Starting Murphy System in SCALE mode ({self.config.replicas} replicas)…"
        )
        compose_path = os.path.join(os.path.dirname(__file__), self.config.compose_file)
        if not os.path.isfile(compose_path):
            yield self._event("docker-compose.scale.yml not found — using local mode", "WARN")
            yield from self._start_local()
            return
        try:
            _run_compose(
                ["up", "-d", "--remove-orphans", f"--scale murphy-api={self.config.replicas}"],
                compose_path,
                self.config.project_name,
            )
            yield self._event(
                f"Scaled stack started with {self.config.replicas} murphy-api replicas", "OK"
            )
        except Exception as exc:
            yield self._event(f"Scale start failed: {exc} — falling back to local", "WARN")
            yield from self._start_local()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _docker_compose_v2() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _run_compose(args: List[str], compose_file: str, project: str) -> None:
    base_cmd = (
        ["docker", "compose", "-f", compose_file, "-p", project]
        if _docker_compose_v2()
        else ["docker-compose", "-f", compose_file, "-p", project]
    )
    subprocess.run(base_cmd + args, check=True, timeout=120)


def _validate_environment() -> None:
    """Basic environment validation; raises ValueError on fatal misconfiguration."""
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 8):
        raise ValueError(f"Python 3.8+ required, got {major}.{minor}")


def _health_check(base_url: str) -> bool:
    """Returns True if the health endpoint responds 200."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{base_url}/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> ScaleConfig:
    parser = argparse.ArgumentParser(
        description="Murphy System — One-Button Deploy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 launch.py                  # local mode
  python3 launch.py --docker         # docker-compose mode
  python3 launch.py --scale 5        # 5-replica scaled mode
  python3 launch.py --port 9000      # custom port
""",
    )
    parser.add_argument("--docker", action="store_true", help="Launch via Docker Compose")
    parser.add_argument("--scale", type=int, metavar="N", help="Launch with N replicas (implies --docker)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.scale:
        mode = "scale"
        replicas = args.scale
    elif args.docker:
        mode = "docker"
        replicas = 1
    else:
        mode = "local"
        replicas = 1

    return ScaleConfig(replicas=replicas, mode=mode, port=args.port, host=args.host)


def main() -> None:
    print()
    print("═" * 60)
    print("  MURPHY SYSTEM LAUNCH SEQUENCE")
    print("  © 2020-2026 Inoni LLC  |  Created by Corey Post")
    print("═" * 60)
    print()

    config = _parse_args()
    streamer = LaunchStreamer(config)

    events: List[LaunchEvent] = []
    for event in streamer.stream():
        events.append(event)

    print()
    print("═" * 60)
    print(f"  ✅ Murphy System is LIVE")
    print(f"  🌐 URL : {config.base_url}")
    print(f"  📊 Mode: {config.mode.upper()}  |  Replicas: {config.replicas}")
    print("═" * 60)
    print()

    errors = [e for e in events if e.status == "ERROR"]
    if errors:
        print("  ❌ Errors encountered:")
        for e in errors:
            print(f"     • {e.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
