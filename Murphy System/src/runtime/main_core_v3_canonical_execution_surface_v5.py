"""Startup entrypoint for the Murphy Core canonical execution surface v5."""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge_v3_canonical_execution_surface_v5 import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_canonical_execution_surface_v5 = os.getenv("MURPHY_PREFER_CANONICAL_EXECUTION_SURFACE_V5", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info(
        "Starting Murphy canonical execution surface v5 bridge (prefer=%s, port=%s)",
        prefer_canonical_execution_surface_v5,
        port,
    )

    app = create_bridge_app(prefer_canonical_execution_surface_v5=prefer_canonical_execution_surface_v5)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
