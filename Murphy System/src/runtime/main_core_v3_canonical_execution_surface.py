"""Startup entrypoint for the Murphy Core canonical execution surface."""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge_v3_canonical_execution_surface import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_canonical_execution_surface = os.getenv("MURPHY_PREFER_CANONICAL_EXECUTION_SURFACE", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info(
        "Starting Murphy canonical execution surface bridge (prefer=%s, port=%s)",
        prefer_canonical_execution_surface,
        port,
    )

    app = create_bridge_app(prefer_canonical_execution_surface=prefer_canonical_execution_surface)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
