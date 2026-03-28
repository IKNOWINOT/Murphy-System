# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""Standard error envelope for all Murphy API responses.

Every API response follows the same shape so the frontend MurphyAPI client
can parse it without guessing:

    {"success": true,  "data": <payload>}
    {"success": false, "error": {"code": "...", "message": "..."}}
"""
from __future__ import annotations

from fastapi.responses import JSONResponse


def success_response(data=None, status_code: int = 200) -> JSONResponse:
    """Return a standard success envelope."""
    return JSONResponse({"success": True, "data": data}, status_code=status_code)


def error_response(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Return a standard error envelope."""
    return JSONResponse(
        {"success": False, "error": {"code": code, "message": message}},
        status_code=status_code,
    )
