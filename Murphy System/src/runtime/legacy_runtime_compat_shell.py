"""Compatibility shell that makes the legacy runtime subordinate to Murphy Core.

This additive runtime layer overrides the legacy /api/chat and /api/execute
endpoints with Murphy Core delegation, then mounts the legacy app for all
other routes. It achieves the intended migration step without a risky
monolithic in-place edit.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.runtime.legacy_chat_execute_delegate import LegacyChatExecuteDelegate
from src.runtime.app import create_app as create_legacy_app


def create_app(prefer_core: bool = True) -> FastAPI:
    shell = FastAPI(
        title="Legacy Runtime Compatibility Shell",
        description="Legacy runtime shell with Murphy Core chat/execute delegation",
        version="0.1.0",
    )

    delegate = LegacyChatExecuteDelegate(prefer_core=prefer_core)
    legacy_app = create_legacy_app()

    @shell.post("/api/chat")
    async def delegated_chat(request: Request) -> JSONResponse:
        data = await request.json()
        result = delegate.delegate_chat(data)
        return JSONResponse(result["payload"], status_code=result["status_code"])

    @shell.post("/api/execute")
    async def delegated_execute(request: Request) -> JSONResponse:
        data = await request.json()
        result = delegate.delegate_execute(data)
        return JSONResponse(result["payload"], status_code=result["status_code"])

    shell.mount("/", legacy_app)
    return shell
