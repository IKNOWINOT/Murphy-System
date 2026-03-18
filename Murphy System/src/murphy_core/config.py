from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CoreConfig:
    app_name: str = "Murphy Core"
    version: str = "0.1.0"
    environment: str = "development"
    prefer_legacy_adapters: bool = True
    default_provider: str = "local_rules"
    trace_store_limit: int = 200

    @classmethod
    def from_env(cls) -> "CoreConfig":
        return cls(
            app_name=os.getenv("MURPHY_CORE_APP_NAME", "Murphy Core"),
            version=os.getenv("MURPHY_CORE_VERSION", "0.1.0"),
            environment=os.getenv("MURPHY_ENV", "development"),
            prefer_legacy_adapters=os.getenv("MURPHY_CORE_PREFER_LEGACY_ADAPTERS", "true").lower() in {"1", "true", "yes", "on"},
            default_provider=os.getenv("MURPHY_CORE_PROVIDER", "local_rules"),
            trace_store_limit=int(os.getenv("MURPHY_CORE_TRACE_LIMIT", "200")),
        )
