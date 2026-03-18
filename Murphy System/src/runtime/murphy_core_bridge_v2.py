"""Compatibility bridge for Murphy Core v2.

This additive bridge lets startup and handoff paths prefer the new v2 app
factory without rewriting the original bridge in place.
"""

from __future__ import annotations

from fastapi import FastAPI


def create_murphy_core_v2_app() -> FastAPI:
    from src.murphy_core.app_v2 import create_app

    return create_app()


def create_bridge_app(prefer_core_v2: bool = True) -> FastAPI:
    if prefer_core_v2:
        return create_murphy_core_v2_app()

    from src.runtime.murphy_core_bridge import create_bridge_app as create_v1_bridge

    return create_v1_bridge(prefer_core=True)
