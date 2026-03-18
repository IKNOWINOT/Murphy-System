"""Murphy Core v3 startup entrypoint.

Preferred startup path for the v3 canonical app factory.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.murphy_core_bridge_v3 import create_bridge_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_core_v3 = os.getenv("MURPHY_PREFER_CORE_V3", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info("Starting Murphy runtime bridge v3 (prefer_core_v3=%s, port=%s)", prefer_core_v3, port)

    app = create_bridge_app(prefer_core_v3=prefer_core_v3)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
