"""
BLOCK-A.6.1 — Twilio Signature Validator (corrected)

HMAC-SHA1 validator for Twilio webhook authenticity. Caller passes the
AUTH_TOKEN (from their own credential cache); this module doesn't try
to read the encrypted vault directly.
"""

from __future__ import annotations
import logging
from typing import Optional
from fastapi import Request

log = logging.getLogger("murphy.twilio_signature")


async def validate_twilio_signature(
    request: Request,
    auth_token: Optional[str] = None,
) -> bool:
    """Validate the X-Twilio-Signature header on an inbound webhook.

    Returns True if signature matches, False otherwise (FAIL CLOSED).
    Never raises.

    Args:
        request: FastAPI Request
        auth_token: Twilio AUTH_TOKEN. Caller must pass this (from their
                    credential cache). If None, validation FAILS CLOSED.
    """
    if not auth_token:
        # Try fallback: env var (last-resort)
        import os
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        if not auth_token:
            log.error("validate_twilio_signature: no auth_token provided — FAIL CLOSED")
            return False

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        log.error("twilio SDK not installed — FAIL CLOSED")
        return False

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        log.warning("X-Twilio-Signature header missing on %s — FAIL CLOSED", request.url.path)
        return False

    # Reconstruct the full URL Twilio used to sign
    proto = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("X-Forwarded-Host", request.url.netloc)
    full_url = f"{proto}://{host}{request.url.path}"
    if request.url.query:
        full_url += f"?{request.url.query}"

    # POST: include sorted form params; GET: no params
    params = {}
    if request.method.upper() == "POST":
        try:
            form = await request.form()
            params = dict(form)
        except Exception as e:
            log.warning("could not parse form for signature validation: %s", e)
            return False

    validator = RequestValidator(auth_token)
    is_valid = validator.validate(full_url, params, signature)

    if not is_valid:
        log.warning(
            "Twilio signature FAILED for %s — got sig %s..., params=%s",
            full_url, signature[:20], list(params.keys())
        )
    return is_valid
