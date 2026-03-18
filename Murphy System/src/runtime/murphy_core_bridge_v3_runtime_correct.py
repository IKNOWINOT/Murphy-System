"""Bridge for the Murphy Core v3 runtime-correct app factory."""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_runtime_correct_app() -> FastAPI:
    from src.murphy_core.app_v3_runtime import create_app
    return create_app()


def create_bridge_app(prefer_core_v3_runtime_correct: bool = True) -> FastAPI:
    if prefer_core_v3_runtime_correct:
        return create_murphy_core_v3_runtime_correct_app()

    from src.runtime.murphy_core_bridge_v3 import create_bridge_app as create_v3_bridge
    return create_v3_bridge(prefer_core_v3=True)
