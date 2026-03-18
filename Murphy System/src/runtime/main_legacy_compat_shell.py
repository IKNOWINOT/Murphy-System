"""Startup entrypoint for the legacy runtime compatibility shell.

Use this when legacy route/UI coverage is still needed, but chat/execute should
be delegated into Murphy Core.
"""

from __future__ import annotations

import logging
import os

import uvicorn

from src.runtime.legacy_runtime_compat_shell import create_app

logger = logging.getLogger(__name__)


def main() -> None:
    prefer_core = os.getenv("MURPHY_LEGACY_SHELL_PREFER_CORE", "true").lower() in {"1", "true", "yes", "on"}
    port = int(os.getenv("PORT") or os.getenv("MURPHY_PORT") or 8000)

    logger.info(
        "Starting legacy runtime compatibility shell (prefer_core=%s, port=%s)",
        prefer_core,
        port,
    )

    app = create_app(prefer_core=prefer_core)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
