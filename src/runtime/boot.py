"""
Murphy System Boot Dispatcher
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1

This module is the SINGLE ENTRY POINT for starting Murphy System.
It reads MURPHY_RUNTIME_MODE from the environment and dispatches to:
  - "monolith" (default): The original murphy_system_core.py + app.py path
  - "tiered": The new TieredOrchestrator with on-demand pack loading

IMPORTANT FOR AI ASSISTANTS AND DEVELOPERS:
  When asked to "run Murphy System" or "start the server", use this module:
    python -m src.runtime.boot
  OR call:
    from src.runtime.boot import boot_murphy
    await boot_murphy()

  DO NOT directly import murphy_system_core or app unless you specifically
  need monolith mode. This boot dispatcher handles the routing.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("murphy.boot")

RUNTIME_MODE: str = os.environ.get("MURPHY_RUNTIME_MODE", "monolith").lower().strip()


async def boot_murphy(mode: Optional[str] = None) -> Any:
    """
    Boot Murphy System in the specified mode.

    Args:
        mode: ``"monolith"`` or ``"tiered"``.  If *None*, reads
              ``MURPHY_RUNTIME_MODE`` from the environment (default:
              ``"monolith"``).

    Returns:
        The running FastAPI application instance.

    Behavior:
        monolith: Imports ``src.runtime.app`` and runs ``create_app()``
                  exactly as today — zero behavioural change for existing users.
        tiered:   Imports :class:`~src.runtime.tiered_orchestrator.TieredOrchestrator`,
                  registers packs from the registry, boots with team profile if
                  available, and creates a lightweight FastAPI app that mounts
                  only the needed routers.  On ANY failure, falls back to
                  monolith automatically.
    """
    effective_mode = (mode or RUNTIME_MODE).lower().strip()

    if effective_mode == "tiered":
        return await boot_tiered()
    else:
        if effective_mode != "monolith":
            logger.warning(
                "Unknown MURPHY_RUNTIME_MODE=%r — defaulting to monolith.", effective_mode
            )
        return await boot_monolith()


async def boot_monolith() -> Any:
    """Boot using the original monolith runtime. No changes to behaviour."""
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║  Murphy System — MONOLITH runtime mode       ║")
    logger.info("║  All modules loaded. Full system available.  ║")
    logger.info("╚══════════════════════════════════════════════╝")
    from src.runtime.app import create_app  # noqa: PLC0415
    return create_app()


async def boot_tiered(fallback_on_error: bool = True) -> Any:
    """
    Boot using the tiered orchestrator.

    On any error, falls back to monolith mode (unless *fallback_on_error* is
    ``False``).
    """
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║  Murphy System — TIERED runtime mode          ║")
    logger.info("║  Loading only what's needed.                  ║")
    logger.info("╚══════════════════════════════════════════════╝")
    try:
        from src.runtime.tiered_orchestrator import TieredOrchestrator  # noqa: PLC0415
        from src.runtime.runtime_packs.registry import get_all_packs     # noqa: PLC0415

        orchestrator = TieredOrchestrator(
            fallback_mode=os.environ.get("MURPHY_PACK_FALLBACK", "monolith")
        )

        # Register all packs from the central registry
        for pack in get_all_packs():
            orchestrator.register_pack(pack)

        # Attempt to load team profile from persistence
        team_profile = _load_team_profile()

        # Boot the tiered system
        result = await orchestrator.boot(team_profile=team_profile)

        if not result.success:
            raise RuntimeError(f"Tiered boot failed: {result.errors}")

        # Build a lightweight FastAPI app that exposes only loaded routers
        from src.runtime.tiered_app_factory import create_tiered_app  # noqa: PLC0415
        app = create_tiered_app(orchestrator)
        return app

    except Exception as exc:
        if fallback_on_error:
            logger.error("Tiered boot failed: %s", exc)
            logger.warning("Falling back to MONOLITH mode for safety.")
            return await boot_monolith()
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_team_profile() -> dict:
    """
    Try to load the team profile from the persistence directory.

    Looks for ``team_profile.json`` inside ``MURPHY_PERSISTENCE_DIR``
    (defaults to ``./data``).  Returns an empty dict if the file is absent
    or cannot be parsed — the orchestrator will then load all packs.
    """
    persistence_dir = Path(
        os.environ.get("MURPHY_PERSISTENCE_DIR", "data")
    )
    profile_path = persistence_dir / "team_profile.json"

    if not profile_path.exists():
        logger.debug("No team profile found at %s — loading all packs.", profile_path)
        return {}

    try:
        with profile_path.open("r", encoding="utf-8") as fh:
            profile = json.load(fh)
        logger.info("Loaded team profile from %s.", profile_path)
        return profile
    except Exception as exc:
        logger.warning("Could not read team profile (%s) — loading all packs.", exc)
        return {}


# ---------------------------------------------------------------------------
# Direct execution: python -m src.runtime.boot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn  # type: ignore[import]

    _app = asyncio.run(boot_murphy())
    _port = int(os.environ.get("MURPHY_PORT", 8000))
    uvicorn.run(_app, host="0.0.0.0", port=_port)  # noqa: S104
