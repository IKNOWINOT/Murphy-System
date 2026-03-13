# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Murphy Matrix Bot — CLI entry point.

Usage::

    python -m bots.run_matrix_bot

or::

    python Murphy\\ System/bots/run_matrix_bot.py

All configuration is read from environment variables.  See
``Murphy System/bots/README.md`` for the full list.
"""

"""CLI entry point for the Murphy Matrix bot.

Starts three concurrent async services:
  1. MurphyMatrixBot   — handles !murphy chat commands
  2. HITLBridge        — proactively posts pending HITL interventions
  3. HealthMonitor     — polls /api/health and broadcasts alerts

Usage:
    python -m bots.run_matrix_bot
    # or
    python "Murphy System/bots/run_matrix_bot.py"

All configuration is via environment variables (see matrix_config.py).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Optional

import httpx

try:
    from nio import AsyncClient, LoginResponse
except ImportError:  # pragma: no cover
    AsyncClient = None
    LoginResponse = None

from .matrix_config import MatrixConfig, load_config
from .matrix_bot import MatrixBot, MurphyAPIClient
from .matrix_hitl import HITLBridge
from .matrix_notifications import NotificationRelay

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
import os
import sys

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("murphy.matrix")

# ---------------------------------------------------------------------------
# ASCII art banner
# ---------------------------------------------------------------------------
_BANNER = r"""
   __  __ _   _ ____  ____  _   _ __   __
  |  \/  | | | |  _ \|  _ \| | | |\ \ / /
  | |\/| | | | | |_) | |_) | |_| | \ V /
  | |  | | |_| |  _ <|  __/|  _  |  | |
  |_|  |_|\___/|_| \_\_|   |_| |_|  |_|

  ☠  MURPHY SYSTEM — MATRIX BOT  ☠
"""


# ---------------------------------------------------------------------------
# Login helper
# ---------------------------------------------------------------------------

async def login_to_matrix(cfg: MatrixConfig) -> Optional[Any]:  # type: ignore[misc]
    """Log in to the Matrix homeserver and return an AsyncClient instance."""
    if AsyncClient is None:
        logger.error(
            "matrix-nio is not installed.  Install it with: pip install 'matrix-nio[e2e]'"
        )
        return None

    client: Any = AsyncClient(cfg.homeserver, cfg.user_id)

    if cfg.access_token:
        # Token-based auth — no password needed
        client.access_token = cfg.access_token
        client.user_id = cfg.user_id
        logger.info("Matrix: using pre-existing access token for %s", cfg.user_id)
    else:
        resp = await client.login(cfg.password)
        if isinstance(resp, LoginResponse):
            logger.info("Matrix: logged in as %s", cfg.user_id)
        else:
            logger.error("Matrix login failed: %s", resp)
            await client.close()
            return None

    return client


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Load config, build all subsystems, and run them concurrently."""
    print(_BANNER)

    # ------------------------------------------------------------------
    # 1. Load and validate configuration
    # ------------------------------------------------------------------
    try:
        cfg = load_config()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    logger.info("Murphy Matrix Bot starting up…")
    logger.info("  API URL   : %s", cfg.murphy_api_url)
    logger.info("  Homeserver: %s", cfg.homeserver)
    logger.info("  User ID   : %s", cfg.user_id)
    logger.info("  Default room  : %s", cfg.default_room)
    logger.info("  HITL room     : %s", cfg.hitl_room)
    logger.info("  Alerts room   : %s", cfg.alerts_room)
    logger.info("  Comms room    : %s", cfg.comms_room)

    # ------------------------------------------------------------------
    # 2. Log in to Matrix
    # ------------------------------------------------------------------
    nio_client = await login_to_matrix(cfg)
    if nio_client is None:
        sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Build shared API client
    # ------------------------------------------------------------------
    api = MurphyAPIClient(cfg.murphy_api_url, cfg.murphy_api_key)

    # ------------------------------------------------------------------
    # 4. Build subsystems
    # ------------------------------------------------------------------
    bot = MatrixBot(cfg, nio_client, api)
    hitl_bridge = HITLBridge(cfg, nio_client, api)
    notification_relay = NotificationRelay(cfg, nio_client, api)

    # ------------------------------------------------------------------
    # 5. Graceful shutdown on SIGINT / SIGTERM
    # ------------------------------------------------------------------
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("Shutdown signal received — stopping Murphy Matrix Bot…")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows does not support add_signal_handler for all signals
            pass

    # ------------------------------------------------------------------
    # 6. Run all concurrent tasks
    # ------------------------------------------------------------------
    async def _run_bot() -> None:
        await bot.start()

    async def _run_hitl() -> None:
        await hitl_bridge.start()

    async def _run_notifications() -> None:
        await notification_relay.start()

    async def _watch_shutdown() -> None:
        await shutdown_event.wait()
        logger.info("Stopping subsystems…")
        await bot.stop()
        await hitl_bridge.stop()
        await notification_relay.stop()
        await api.aclose()
        if nio_client is not None:
            await nio_client.close()

    logger.info("Murphy Matrix Bot is running.  Press Ctrl+C to stop.")

    await asyncio.gather(
        _run_bot(),
        _run_hitl(),
        _run_notifications(),
        _watch_shutdown(),
        return_exceptions=True,
    )

    logger.info("Murphy Matrix Bot stopped.  Goodbye. ☠")


if __name__ == "__main__":
    asyncio.run(main())


__all__ = ["main"]
# Imports — fail fast with a friendly message if matrix-nio is missing
# ---------------------------------------------------------------------------
try:
    from .matrix_config import MatrixBotConfig
    from .matrix_bot import MurphyMatrixBot
    from .matrix_hitl import HITLBridge
    from .matrix_notifications import HealthMonitor
except ImportError:
    # Support running as a plain script (python run_matrix_bot.py)
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from bots.matrix_config import MatrixBotConfig  # type: ignore[no-redef]
    from bots.matrix_bot import MurphyMatrixBot  # type: ignore[no-redef]
    from bots.matrix_hitl import HITLBridge  # type: ignore[no-redef]
    from bots.matrix_notifications import HealthMonitor  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = r"""
 ___  ___  _ _ _ ___ _  _ _  _  __  __   _ _____ ___ _____  __
|  \/  | || | '_| _ \ || | || | \ \/ /  | |_   _| _ |_   _| \ \
| |\/| | __ | |  _/ __ |_  _|  |  >  <  | | | | | /   | |    > >
|_|  |_|_||_|_|_||_||_| \_/ |_| /_/\_\ |_| |_| |_\   |_|   /_/
                                                              BOT
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run() -> None:
    config = MatrixBotConfig.from_env()

    # Check for YAML config file
    config_file = os.environ.get("MURPHY_BOT_CONFIG")
    if config_file and os.path.isfile(config_file):
        config = MatrixBotConfig.from_yaml(config_file)
        logger.info("Loaded config from %s", config_file)

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    logger.info(BANNER)
    logger.info("Connecting to Matrix homeserver: %s", config.homeserver)
    logger.info("Bot user: %s", config.user_id)
    logger.info("Murphy API: %s", config.murphy_api_url)

    bot = MurphyMatrixBot(config)
    hitl_bridge = HITLBridge(bot, config)
    health_monitor = HealthMonitor(bot, config)

    # Start background services (they run concurrently with the bot's sync loop)
    hitl_task = hitl_bridge.start()
    health_task = health_monitor.start()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        hitl_bridge.stop()
        health_monitor.stop()
        await bot.stop()
        # Cancel background tasks
        for task in (hitl_task, health_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
