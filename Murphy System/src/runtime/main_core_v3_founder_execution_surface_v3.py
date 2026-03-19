"""Startup entrypoint for the Murphy Core founder execution surface v3."""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge_v3_founder_execution_surface_v3 import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_founder_execution_surface_v3 = os.getenv("MURPHY_PREFER_FOUNDER_EXECUTION_SURFACE_V3", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info(
        "Starting Murphy founder execution surface v3 bridge (prefer=%s, port=%s)",
        prefer_founder_execution_surface_v3,
        port,
    )

    app = create_bridge_app(prefer_founder_execution_surface_v3=prefer_founder_execution_surface_v3)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
