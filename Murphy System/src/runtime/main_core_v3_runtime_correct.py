"""Startup entrypoint for Murphy Core v3 runtime-correct path."""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge_v3_runtime_correct import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_core_v3_runtime_correct = os.getenv("MURPHY_PREFER_CORE_V3_RUNTIME_CORRECT", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info(
        "Starting Murphy runtime bridge v3 runtime-correct (prefer=%s, port=%s)",
        prefer_core_v3_runtime_correct,
        port,
    )

    app = create_bridge_app(prefer_core_v3_runtime_correct=prefer_core_v3_runtime_correct)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
