"""
Email Integration — SMTP and SendGrid (INC-11 / C-04).

Provides async email delivery via:
  1. **SendGrid** — when ``SENDGRID_API_KEY`` is set
  2. **SMTP** — when ``SMTP_HOST`` is set (uses ``aiosmtplib``)
  3. **Disabled** — when no real backend is configured; every send returns
     ``success=False`` with a clear, actionable error message.

The active backend is chosen automatically from environment variables
following the 12-factor app pattern.  There is no silent mock path —
if email credentials are not configured the service explicitly reports
the misconfiguration rather than silently swallowing messages.

Environment variables
---------------------
SENDGRID_API_KEY : str
    SendGrid v3 API key.  Takes priority over SMTP when both are set.
SENDGRID_FROM_EMAIL : str
    Default sender address used by the SendGrid backend.
MURPHY_MAIL_INTERNAL : str
    Set to ``true`` to use the internal docker-mailserver (``murphy-mailserver:587``).
    When set, overrides ``SMTP_HOST`` / ``SMTP_PORT`` with the internal container address.
SMTP_HOST : str
    SMTP server hostname.
SMTP_PORT : int
    SMTP server port (default: 587).
SMTP_USER : str
    SMTP authentication username (optional).
SMTP_PASSWORD : str
    SMTP authentication password (optional).
SMTP_USE_TLS : str
    ``true`` (default) enables STARTTLS; ``false`` sends plaintext.
SMTP_FROM_EMAIL : str
    Default sender address used by the SMTP backend.
MESSAGE_ID_DOMAIN : str
    Domain suffix for generated Message-IDs (default: murphy.local).
MURPHY_ENV : str
    Runtime environment label (development / staging / production).

Usage::

    from email_integration import EmailService
    svc = EmailService.from_env()
    result = await svc.send(
        to=["ops@example.com"],
        subject="Hello from Murphy",
        body="This is an automated message.",
    )
    if not result.success:
        raise RuntimeError(f"Email delivery failed: {result.error}")

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class EmailMessage:
    """Normalised email message."""

    to: List[str]
    subject: str
    body: str
    from_addr: str = ""
    html_body: Optional[str] = None
    cc: List[str] = field(default_factory=list)
    bcc: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class SendResult:
    """Result of an email send attempt."""

    success: bool
    message_id: str
    provider: str
    status_code: int = 0
    error: Optional[str] = None
    latency_seconds: float = 0.0
    raw_response: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract backend
# ---------------------------------------------------------------------------


class EmailBackend(ABC):
    """Abstract base class for email backends."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """Send a single email message."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable backend name."""


# ---------------------------------------------------------------------------
# SendGrid backend
# ---------------------------------------------------------------------------


class SendGridBackend(EmailBackend):
    """SendGrid v3 API backend.

    Requires ``SENDGRID_API_KEY`` and optionally ``SENDGRID_FROM_EMAIL``.
    Uses ``httpx`` for async HTTP (avoids importing the heavy SendGrid SDK
    when only the REST API is needed).
    """

    def __init__(self, api_key: str, from_email: str = "") -> None:
        self._api_key = api_key
        self._from_email = from_email or os.getenv(
            "SENDGRID_FROM_EMAIL", "murphy@example.com"
        )

    @property
    def provider_name(self) -> str:
        return "sendgrid"

    async def send(self, message: EmailMessage) -> SendResult:
        start = time.monotonic()
        try:
            import httpx  # noqa: F811 — lazy import
        except ImportError:
            return SendResult(
                success=False,
                message_id=message.message_id,
                provider=self.provider_name,
                error="httpx not installed",
            )

        payload = {
            "personalizations": [
                {
                    "to": [{"email": addr} for addr in message.to],
                }
            ],
            "from": {"email": message.from_addr or self._from_email},
            "subject": message.subject,
            "content": [
                {"type": "text/plain", "value": message.body},
            ],
        }

        if message.cc:
            payload["personalizations"][0]["cc"] = [
                {"email": addr} for addr in message.cc
            ]
        if message.html_body:
            payload["content"].append(
                {"type": "text/html", "value": message.html_body}
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers=headers,
                )
            elapsed = time.monotonic() - start

            success = resp.status_code in (200, 202)
            logger.info(
                "SendGrid send %s",
                "succeeded" if success else "failed",
                extra={
                    "message_id": message.message_id,
                    "status_code": resp.status_code,
                    "latency": round(elapsed, 3),
                },
            )
            return SendResult(
                success=success,
                message_id=message.message_id,
                provider=self.provider_name,
                status_code=resp.status_code,
                latency_seconds=elapsed,
                error=None if success else resp.text,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "SendGrid send failed: %s",
                exc,
                extra={"message_id": message.message_id, "error": str(exc)},
            )
            return SendResult(
                success=False,
                message_id=message.message_id,
                provider=self.provider_name,
                error=str(exc),
                latency_seconds=elapsed,
            )


# ---------------------------------------------------------------------------
# SMTP backend
# ---------------------------------------------------------------------------


class SMTPBackend(EmailBackend):
    """Async SMTP backend using ``aiosmtplib``.

    Requires ``SMTP_HOST`` and optionally ``SMTP_PORT``, ``SMTP_USER``,
    ``SMTP_PASSWORD``, ``SMTP_USE_TLS``, ``SMTP_FROM_EMAIL``.
    """

    def __init__(
        self,
        host: str,
        port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True,
        from_email: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_email = from_email or os.getenv(
            "SMTP_FROM_EMAIL", "murphy@example.com"
        )

    @property
    def provider_name(self) -> str:
        return "smtp"

    async def send(self, message: EmailMessage) -> SendResult:
        start = time.monotonic()
        try:
            import aiosmtplib  # noqa: F811
        except ImportError:
            return SendResult(
                success=False,
                message_id=message.message_id,
                provider=self.provider_name,
                error="aiosmtplib not installed",
            )

        from_addr = message.from_addr or self._from_email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(message.to)
        if message.cc:
            msg["Cc"] = ", ".join(message.cc)
        msg["Message-ID"] = f"<{message.message_id}@{os.getenv('MESSAGE_ID_DOMAIN', 'murphy.local')}>"

        msg.attach(MIMEText(message.body, "plain"))
        if message.html_body:
            msg.attach(MIMEText(message.html_body, "html"))

        all_recipients = message.to + message.cc + message.bcc

        try:
            smtp_kwargs: Dict[str, Any] = {
                "hostname": self._host,
                "port": self._port,
                "use_tls": self._use_tls,
            }
            if self._username and self._password:
                smtp_kwargs["username"] = self._username
                smtp_kwargs["password"] = self._password

            response_tuple = await aiosmtplib.send(
                msg,
                sender=from_addr,
                recipients=all_recipients,
                **smtp_kwargs,
            )

            elapsed = time.monotonic() - start
            logger.info(
                "SMTP send succeeded",
                extra={
                    "message_id": message.message_id,
                    "host": self._host,
                    "latency": round(elapsed, 3),
                },
            )
            return SendResult(
                success=True,
                message_id=message.message_id,
                provider=self.provider_name,
                status_code=250,
                latency_seconds=elapsed,
            )

        except Exception as exc:
            elapsed = time.monotonic() - start
            logger.error(
                "SMTP send failed: %s",
                exc,
                extra={"message_id": message.message_id, "error": str(exc)},
            )
            return SendResult(
                success=False,
                message_id=message.message_id,
                provider=self.provider_name,
                error=str(exc),
                latency_seconds=elapsed,
            )


# ---------------------------------------------------------------------------
# Unconfigured backend — explicit failure, never silent
# ---------------------------------------------------------------------------


class UnconfiguredEmailBackend(EmailBackend):
    """Backend active when no credentials are provided.

    Every send returns ``success=False`` with an actionable configuration
    error.  This prevents silent message loss: callers get a clear failure
    rather than a fake success from a mock that never delivered anything.
    """

    @property
    def provider_name(self) -> str:
        return "unconfigured"

    async def send(self, message: EmailMessage) -> SendResult:
        error = (
            "Email backend is not configured.  "
            "Set SENDGRID_API_KEY for SendGrid delivery, or set SMTP_HOST "
            "(and optionally SMTP_PORT / SMTP_USER / SMTP_PASSWORD) for SMTP delivery."
        )
        logger.error(
            "UnconfiguredEmailBackend: send attempted with no backend configured — "
            "message_id=%s to=%s subject=%r  Hint: %s",
            message.message_id,
            message.to,
            message.subject,
            error,
        )
        return SendResult(
            success=False,
            message_id=message.message_id,
            provider=self.provider_name,
            error=error,
        )


# ---------------------------------------------------------------------------
# High-level service
# ---------------------------------------------------------------------------


class EmailService:
    """Unified email service that delegates to the configured backend.

    Backend selection priority (env-var driven):
      1. ``SENDGRID_API_KEY`` set  →  SendGridBackend
      2. ``SMTP_HOST`` set         →  SMTPBackend
      3. Neither set               →  UnconfiguredEmailBackend  (explicit failure)

    There is no silent fallback path.  Callers that receive a
    ``SendResult(success=False)`` know exactly why delivery failed.
    """

    def __init__(self, backend: EmailBackend) -> None:
        self._backend = backend

    @classmethod
    def from_env(cls) -> "EmailService":
        """Create an ``EmailService`` configured from environment variables.

        Returns a fully wired service.  If no credentials are found, returns
        a service backed by ``UnconfiguredEmailBackend`` so every ``send``
        call returns an explicit failure rather than silently doing nothing.
        """
        sendgrid_key = os.getenv("SENDGRID_API_KEY")
        if sendgrid_key:
            logger.info("Email backend: SendGrid", extra={"provider": "sendgrid"})
            return cls(SendGridBackend(api_key=sendgrid_key))

        # Internal docker-mailserver auto-detection
        if os.getenv("MURPHY_MAIL_INTERNAL", "").lower() == "true":
            internal_host = "murphy-mailserver"
            internal_port = 587
            smtp_user = os.getenv("SMTP_USER") or os.getenv("MAIL_ADMIN_EMAIL")
            smtp_pass = os.getenv("SMTP_PASSWORD") or os.getenv("MAIL_ADMIN_PASSWORD")
            logger.info(
                "Email backend: internal docker-mailserver (%s:%s)",
                internal_host,
                internal_port,
                extra={"provider": "internal_smtp", "host": internal_host},
            )
            return cls(
                SMTPBackend(
                    host=internal_host,
                    port=internal_port,
                    username=smtp_user,
                    password=smtp_pass,
                    use_tls=True,
                )
            )

        smtp_host = os.getenv("SMTP_HOST")
        if smtp_host:
            logger.info(
                "Email backend: SMTP (%s)",
                smtp_host,
                extra={"provider": "smtp", "host": smtp_host},
            )
            return cls(
                SMTPBackend(
                    host=smtp_host,
                    port=int(os.getenv("SMTP_PORT", "587")),
                    username=os.getenv("SMTP_USER"),
                    password=os.getenv("SMTP_PASSWORD"),
                    use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                )
            )

        murphy_env = os.getenv("MURPHY_ENV", "development").lower()
        logger.warning(
            "Email backend: unconfigured — no SENDGRID_API_KEY or SMTP_HOST found. "
            "All send() calls will return success=False. "
            "(MURPHY_ENV=%s)",
            murphy_env,
        )
        return cls(UnconfiguredEmailBackend())

    async def send(
        self,
        to: List[str],
        subject: str,
        body: str,
        *,
        html_body: Optional[str] = None,
        from_addr: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> SendResult:
        """Send an email.

        Args:
            to: List of recipient addresses.
            subject: Email subject.
            body: Plain-text body.
            html_body: Optional HTML body.
            from_addr: Optional sender override.
            cc: Optional CC list.
            bcc: Optional BCC list.

        Returns:
            A ``SendResult`` with delivery status.
        """
        message = EmailMessage(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            from_addr=from_addr or "",
            cc=cc or [],
            bcc=bcc or [],
        )

        result = await self._backend.send(message)

        logger.info(
            "Email send result: %s via %s",
            "success" if result.success else "failure",
            result.provider,
            extra={
                "message_id": result.message_id,
                "provider": result.provider,
                "success": result.success,
                "to_count": len(to),
            },
        )

        return result

    @property
    def backend(self) -> EmailBackend:
        """The active backend instance."""
        return self._backend

    @property
    def provider_name(self) -> str:
        """Name of the active backend."""
        return self._backend.provider_name
