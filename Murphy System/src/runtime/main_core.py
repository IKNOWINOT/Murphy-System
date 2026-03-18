"""Murphy Core startup entrypoint.

This is the preferred production startup path during migration.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_core = os.getenv("MURPHY_PREFER_CORE", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info("Starting Murphy runtime bridge (prefer_core=%s, port=%s)", prefer_core, port)

    app = create_bridge_app(prefer_core=prefer_core)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
