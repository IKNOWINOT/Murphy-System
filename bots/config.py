"""Environment variable validation."""
from __future__ import annotations

import os

REQUIRED_ENV_VARS = ["MEMORY_DB"]

# Optional toggle for dry-run mode
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


def validate_env() -> None:
    missing = [var for var in REQUIRED_ENV_VARS if not os.environ.get(var)]
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")
