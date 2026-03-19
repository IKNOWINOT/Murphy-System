"""Bridge for the Murphy Core founder execution surface.

This bridge prefers the founder/admin visibility and capability-aware execution
surface so production deployments have one truthful control plane.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v3_founder_execution_surface_app() -> FastAPI:
    from src.murphy_core.app_v3_founder_execution_surface import create_app

    return create_app()


def create_bridge_app(prefer_founder_execution_surface: bool = True) -> FastAPI:
    if prefer_founder_execution_surface:
        return create_murphy_core_v3_founder_execution_surface_app()

    from src.runtime.murphy_core_bridge_v3_runtime_correct import create_bridge_app as create_runtime_correct_bridge

    return create_runtime_correct_bridge(prefer_core_v3_runtime_correct=True)
