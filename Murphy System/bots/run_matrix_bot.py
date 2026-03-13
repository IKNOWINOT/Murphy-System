#!/usr/bin/env python3
# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""CLI entry point to run the Murphy Matrix bot.

Usage::

    python run_matrix_bot.py
    python run_matrix_bot.py --config /path/to/config.yaml

All configuration is read from environment variables unless a YAML config
file is supplied via ``--config``.  See :mod:`matrix_config` for the full
list of supported settings.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

# ---------------------------------------------------------------------------
# Logging setup (before any local imports so early errors are visible)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("murphy.matrix")

# ---------------------------------------------------------------------------
# Imports — try package-relative first, fall back to direct module path
# ---------------------------------------------------------------------------
try:
    from .matrix_config import MatrixBotConfig
    from .matrix_bot import MurphyMatrixBot
    from .matrix_hitl import HITLBridge
    from .matrix_notifications import HealthMonitor
except ImportError:
    # Support running as a plain script: python run_matrix_bot.py
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from bots.matrix_config import MatrixBotConfig  # type: ignore[no-redef]
    from bots.matrix_bot import MurphyMatrixBot  # type: ignore[no-redef]
    from bots.matrix_hitl import HITLBridge  # type: ignore[no-redef]
    from bots.matrix_notifications import HealthMonitor  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# ASCII art banner
# ---------------------------------------------------------------------------
BANNER = r"""
   __  __ _   _ ____  ____  _   _ __   __
  |  \/  | | | |  _ \|  _ \| | | |\ \ / /
  | |\/| | | | | |_) | |_) | |_| | \ V /
  | |  | | |_| |  _ <|  __/|  _  |  | |
  |_|  |_|\___/|_| \_\_|   |_| |_|  |_|

  ☠  MURPHY SYSTEM — MATRIX BOT  ☠
"""


# ---------------------------------------------------------------------------
# Main async runner
# ---------------------------------------------------------------------------


async def _run(config_path: str | None = None) -> None:
    """Load config, build all subsystems, and run them concurrently.

    Args:
        config_path: Optional path to a YAML config file.  When *None* the
            configuration is loaded purely from environment variables.
    """
    # ------------------------------------------------------------------
    # 1. Load and validate configuration
    # ------------------------------------------------------------------
    if config_path:
        config = MatrixBotConfig.from_yaml(config_path)
        logger.info("Loaded config from %s", config_path)
    else:
        config = MatrixBotConfig.from_env()

    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Print startup banner and summary
    # ------------------------------------------------------------------
    print(BANNER)
    logger.info("Murphy Matrix Bot starting up…")
    logger.info("  Bot user  : %s", config.user_id)
    logger.info("  Homeserver: %s", config.homeserver)
    logger.info("  API URL   : %s", config.murphy_api_url)
    if config.hitl_room:
        logger.info("  HITL room : %s", config.hitl_room)
    if config.alerts_room:
        logger.info("  Alerts room: %s", config.alerts_room)

    # ------------------------------------------------------------------
    # 3. Build subsystems
    # ------------------------------------------------------------------
    bot = MurphyMatrixBot(config)
    hitl_bridge = HITLBridge(bot, config)
    health_monitor = HealthMonitor(bot, config)

    # ------------------------------------------------------------------
    # 4. Start background services
    # ------------------------------------------------------------------
    hitl_task = hitl_bridge.start()
    health_task = health_monitor.start()

    # ------------------------------------------------------------------
    # 5. Run the bot sync loop (blocks until stopped)
    # ------------------------------------------------------------------
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received — shutting down…")
    finally:
        hitl_bridge.stop()
        health_monitor.stop()
        await bot.stop()
        # Cancel background tasks gracefully
        for task in (hitl_task, health_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    logger.info("Murphy Matrix Bot stopped. Goodbye. ☠")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI arguments and start the bot."""
    parser = argparse.ArgumentParser(
        description="Murphy System Matrix Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to a YAML config file (overrides environment variables).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_run(config_path=args.config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


__all__ = ["main"]
