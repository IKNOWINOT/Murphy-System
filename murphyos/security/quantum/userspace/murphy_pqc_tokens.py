# SPDX-License-Identifier: LicenseRef-BSL-1.1
# © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""
murphy_pqc_tokens — Quantum-resistant session-token system for MurphyOS.

Replaces standard JWT with PQC-signed tokens using ML-DSA-87 (Dilithium5).

Token format:  ``<base64url(header)>.<base64url(payload)>.<base64url(ml_dsa_sig)>``

Payload fields:
  • user           — authenticated principal
  • session_id     — unique session identifier
  • issued_at      — Unix timestamp
  • expires_at     — Unix timestamp
  • confidence_at_issue — Murphy confidence score when the token was minted

The token is signed with ML-DSA-87 and verified using the corresponding
public key.  Tokens are rotated when the confidence score drifts by more
than 0.10 from the value at issuance.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("murphy.pqc.tokens")

# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

_ERR_TOKEN_CREATE   = "MURPHY-PQC-ERR-300"
_ERR_TOKEN_VERIFY   = "MURPHY-PQC-ERR-301"
_ERR_TOKEN_EXPIRED  = "MURPHY-PQC-ERR-302"
_ERR_TOKEN_REVOKED  = "MURPHY-PQC-ERR-303"
_ERR_TOKEN_PARSE    = "MURPHY-PQC-ERR-304"

# ---------------------------------------------------------------------------
# PQC backend detection
# ---------------------------------------------------------------------------

try:
    from murphy_pqc import (
        PQCError,
        generate_sig_keypair,
        sign as pqc_sign,
        verify as pqc_verify,
    )
    _HAS_PQC = True
except ImportError:  # MURPHY-PQC-TOKEN-ERR-001
    _HAS_PQC = False
    # Not an error — PQC is optional; tokens fall back to HMAC-SHA256.

# ---------------------------------------------------------------------------
# Base64url helpers (no padding, URL-safe)
# ---------------------------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


# ---------------------------------------------------------------------------
# Token data model
# ---------------------------------------------------------------------------

DEFAULT_EXPIRY_HOURS = 8
CONFIDENCE_ROTATION_THRESHOLD = 0.10
REVOKED_TOKENS_PATH = Path("/murphy/keys/revoked_tokens")


@dataclass
class TokenHeader:
    alg: str = "ML-DSA-87"
    typ: str = "MURPHY-PQC-TOKEN"
    ver: int = 1


@dataclass
class TokenPayload:
    user: str = ""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    confidence_at_issue: float = 1.0

    def __post_init__(self) -> None:
        if self.expires_at == 0.0:
            self.expires_at = self.issued_at + (DEFAULT_EXPIRY_HOURS * 3600)


# ---------------------------------------------------------------------------
# Token issuer / verifier
# ---------------------------------------------------------------------------

class PQCTokenManager:
    """Issue and verify quantum-resistant session tokens."""

    def __init__(
        self,
        sig_public_key: bytes,
        sig_secret_key: Optional[bytes] = None,
        revoked_path: Path = REVOKED_TOKENS_PATH,
    ) -> None:
        self._sig_pk = sig_public_key
        self._sig_sk = sig_secret_key
        self._revoked_path = revoked_path
        self._revoked_cache: set[str] = set()
        self._load_revoked()

    # -- Revocation ---------------------------------------------------------

    def _load_revoked(self) -> None:
        if self._revoked_path.exists():
            try:
                self._revoked_cache = set(
                    self._revoked_path.read_text().splitlines(),
                )
            except OSError as exc:  # MURPHY-PQC-TOKEN-ERR-002
                logger.warning("MURPHY-PQC-TOKEN-ERR-002: failed to load revocation list: %s", exc)

    def _save_revoked(self) -> None:
        self._revoked_path.parent.mkdir(parents=True, exist_ok=True)
        self._revoked_path.write_text("\n".join(sorted(self._revoked_cache)))

    def revoke(self, token_id: str) -> None:
        """Add *token_id* (session_id) to the revocation list."""
        self._revoked_cache.add(token_id)
        self._save_revoked()
        logger.info("Token revoked: %s", token_id)

    def is_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked_cache

    # -- Token creation -----------------------------------------------------

    def create_token(
        self,
        user: str,
        confidence: float = 1.0,
        expiry_hours: float = DEFAULT_EXPIRY_HOURS,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a PQC-signed session token.

        Returns the token string ``header.payload.signature``.
        """
        if self._sig_sk is None:
            raise RuntimeError(
                f"[{_ERR_TOKEN_CREATE}] Cannot sign — no secret key loaded",
            )

        header = TokenHeader()
        payload = TokenPayload(
            user=user,
            confidence_at_issue=confidence,
            expires_at=time.time() + expiry_hours * 3600,
        )

        header_b = _b64url_encode(
            json.dumps(asdict(header), separators=(",", ":")).encode(),
        )
        payload_dict = asdict(payload)
        if extra_claims:
            payload_dict.update(extra_claims)
        payload_b = _b64url_encode(
            json.dumps(payload_dict, separators=(",", ":")).encode(),
        )

        signing_input = f"{header_b}.{payload_b}".encode("ascii")

        if _HAS_PQC:
            sig_bytes = pqc_sign(self._sig_sk, signing_input)
        else:
            logger.warning("PQC unavailable — using HMAC-SHA3-256 fallback")
            sig_bytes = hmac.new(
                self._sig_sk[:64], signing_input, hashlib.sha3_256,
            ).digest()

        sig_b = _b64url_encode(sig_bytes)
        return f"{header_b}.{payload_b}.{sig_b}"

    # -- Token verification -------------------------------------------------

    def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode a PQC token.

        Returns the decoded :class:`TokenPayload` on success.

        Raises:
            ValueError: on any verification failure.
        """
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"[{_ERR_TOKEN_PARSE}] Invalid token structure "
                f"(expected 3 parts, got {len(parts)})",
            )

        header_b, payload_b, sig_b = parts
        signing_input = f"{header_b}.{payload_b}".encode("ascii")
        sig_bytes = _b64url_decode(sig_b)

        # Signature verification
        if _HAS_PQC:
            if not pqc_verify(self._sig_pk, signing_input, sig_bytes):
                raise ValueError(
                    f"[{_ERR_TOKEN_VERIFY}] ML-DSA-87 signature invalid",
                )
        else:
            expected = hmac.new(
                self._sig_pk[:64], signing_input, hashlib.sha3_256,
            ).digest()
            if not hmac.compare_digest(expected, sig_bytes):
                raise ValueError(
                    f"[{_ERR_TOKEN_VERIFY}] HMAC signature invalid",
                )

        # Decode payload
        try:
            payload_dict = json.loads(_b64url_decode(payload_b))
        except (json.JSONDecodeError, Exception) as exc:
            raise ValueError(
                f"[{_ERR_TOKEN_PARSE}] Cannot decode payload: {exc}",
            ) from exc

        payload = TokenPayload(
            user=payload_dict.get("user", ""),
            session_id=payload_dict.get("session_id", ""),
            issued_at=payload_dict.get("issued_at", 0),
            expires_at=payload_dict.get("expires_at", 0),
            confidence_at_issue=payload_dict.get("confidence_at_issue", 0),
        )

        # Expiration check
        if time.time() > payload.expires_at:
            raise ValueError(
                f"[{_ERR_TOKEN_EXPIRED}] Token expired at "
                f"{payload.expires_at}",
            )

        # Revocation check
        if self.is_revoked(payload.session_id):
            raise ValueError(
                f"[{_ERR_TOKEN_REVOKED}] Token session {payload.session_id} "
                "has been revoked",
            )

        return payload

    # -- Confidence-based rotation ------------------------------------------

    def should_rotate(
        self, token: str, current_confidence: float,
    ) -> bool:
        """Return True if the token should be rotated due to confidence drift."""
        try:
            payload = self.verify_token(token)
        except ValueError:  # MURPHY-PQC-TOKEN-ERR-003
            logger.debug("MURPHY-PQC-TOKEN-ERR-003: token invalid during rotation check — rotation needed")
            return True

        drift = abs(current_confidence - payload.confidence_at_issue)
        if drift > CONFIDENCE_ROTATION_THRESHOLD:
            logger.info(
                "Confidence drift %.3f > threshold %.3f — rotation needed",
                drift, CONFIDENCE_ROTATION_THRESHOLD,
            )
            return True
        return False

    def rotate_token(
        self,
        old_token: str,
        current_confidence: float,
    ) -> str:
        """Revoke *old_token* and issue a replacement."""
        try:
            old_payload = self.verify_token(old_token)
            self.revoke(old_payload.session_id)
            return self.create_token(
                user=old_payload.user,
                confidence=current_confidence,
            )
        except ValueError:
            raise ValueError(
                f"[{_ERR_TOKEN_VERIFY}] Cannot rotate an invalid token",
            )
