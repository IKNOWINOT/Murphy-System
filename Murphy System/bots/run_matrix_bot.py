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
