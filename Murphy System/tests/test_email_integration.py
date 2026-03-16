"""
Tests for Email Integration — SMTP and SendGrid (INC-11 / C-04).

Covers:
  - MockEmailBackend happy path and message capture
  - SendGridBackend with mocked httpx
  - SMTPBackend with mocked aiosmtplib
  - EmailService.from_env() factory
  - Error / edge-case handling

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure src/ is importable
_src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
_src_dir = os.path.abspath(_src_dir)

from email_integration import (
    EmailMessage,
    EmailService,
    MockEmailBackend,
    SMTPBackend,
    SendGridBackend,
    SendResult,
)


# ---------------------------------------------------------------------------
# MockEmailBackend tests
# ---------------------------------------------------------------------------


class TestMockEmailBackend:
    """Tests for the in-memory mock backend."""

    @pytest.mark.asyncio
    async def test_happy_path(self) -> None:
        backend = MockEmailBackend()
        msg = EmailMessage(
            to=["ops@example.com"],
            subject="Test",
            body="Hello!",
        )
        result = await backend.send(msg)
        assert result.success is True
        assert result.provider == "mock"
        assert len(backend.sent_messages) == 1
        assert backend.sent_messages[0].subject == "Test"

    @pytest.mark.asyncio
    async def test_multiple_sends_captured(self) -> None:
        backend = MockEmailBackend()
        for i in range(3):
            msg = EmailMessage(to=[f"user{i}@x.com"], subject=f"S{i}", body="b")
            await backend.send(msg)
        assert len(backend.sent_messages) == 3


# ---------------------------------------------------------------------------
# SendGrid backend tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestSendGridBackend:
    """Tests for SendGrid backend with mocked httpx."""

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        backend = SendGridBackend(api_key="SG.test_key")
        msg = EmailMessage(
            to=["ops@example.com"],
            subject="SG Test",
            body="Hello from SendGrid",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.text = ""

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("email_integration.httpx", create=True) as mock_httpx:
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            # Also need to patch the import inside the method
            import types
            fake_httpx = types.ModuleType("httpx")
            fake_httpx.AsyncClient = MagicMock(return_value=mock_client)
            with patch.dict("sys.modules", {"httpx": fake_httpx}):
                result = await backend.send(msg)

        assert result.success is True
        assert result.provider == "sendgrid"
        assert result.status_code == 202

    @pytest.mark.asyncio
    async def test_send_failure_status(self) -> None:
        backend = SendGridBackend(api_key="SG.bad_key")
        msg = EmailMessage(to=["a@b.com"], subject="Fail", body="x")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        import types
        fake_httpx = types.ModuleType("httpx")
        fake_httpx.AsyncClient = MagicMock(return_value=mock_client)
        with patch.dict("sys.modules", {"httpx": fake_httpx}):
            result = await backend.send(msg)

        assert result.success is False
        assert result.error == "Unauthorized"

    @pytest.mark.asyncio
    async def test_httpx_not_installed(self) -> None:
        backend = SendGridBackend(api_key="SG.key")
        msg = EmailMessage(to=["a@b.com"], subject="No httpx", body="x")

        with patch.dict("sys.modules", {"httpx": None}):
            result = await backend.send(msg)

        assert result.success is False
        assert "not installed" in (result.error or "")


# ---------------------------------------------------------------------------
# SMTP backend tests (mocked aiosmtplib)
# ---------------------------------------------------------------------------


class TestSMTPBackend:
    """Tests for SMTP backend with mocked aiosmtplib."""

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        backend = SMTPBackend(host="smtp.example.com", port=587)
        msg = EmailMessage(
            to=["ops@example.com"],
            subject="SMTP Test",
            body="Hello from SMTP",
        )

        import types
        fake_aiosmtplib = types.ModuleType("aiosmtplib")
        fake_aiosmtplib.send = AsyncMock(return_value=({}, "OK"))
        with patch.dict("sys.modules", {"aiosmtplib": fake_aiosmtplib}):
            result = await backend.send(msg)

        assert result.success is True
        assert result.provider == "smtp"

    @pytest.mark.asyncio
    async def test_send_connection_error(self) -> None:
        backend = SMTPBackend(host="bad.host", port=25)
        msg = EmailMessage(to=["a@b.com"], subject="Fail", body="x")

        import types
        fake_aiosmtplib = types.ModuleType("aiosmtplib")
        fake_aiosmtplib.send = AsyncMock(side_effect=ConnectionError("refused"))
        with patch.dict("sys.modules", {"aiosmtplib": fake_aiosmtplib}):
            result = await backend.send(msg)

        assert result.success is False
        assert "refused" in (result.error or "")

    @pytest.mark.asyncio
    async def test_aiosmtplib_not_installed(self) -> None:
        backend = SMTPBackend(host="smtp.example.com")
        msg = EmailMessage(to=["a@b.com"], subject="No lib", body="x")

        with patch.dict("sys.modules", {"aiosmtplib": None}):
            result = await backend.send(msg)

        assert result.success is False
        assert "not installed" in (result.error or "")


# ---------------------------------------------------------------------------
# EmailService tests
# ---------------------------------------------------------------------------


class TestEmailService:
    """Tests for the high-level EmailService."""

    @pytest.mark.asyncio
    async def test_from_env_defaults_to_mock(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            svc = EmailService.from_env()
        assert svc.provider_name == "mock"

    @pytest.mark.asyncio
    async def test_from_env_sendgrid(self) -> None:
        with patch.dict(os.environ, {"SENDGRID_API_KEY": "SG.test"}, clear=False):
            svc = EmailService.from_env()
        assert svc.provider_name == "sendgrid"

    @pytest.mark.asyncio
    async def test_from_env_smtp(self) -> None:
        env = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465"}
        with patch.dict(os.environ, env, clear=False):
            svc = EmailService.from_env()
        assert svc.provider_name == "smtp"

    @pytest.mark.asyncio
    async def test_send_via_mock(self) -> None:
        svc = EmailService(MockEmailBackend())
        result = await svc.send(
            to=["ops@example.com"],
            subject="Integration Test",
            body="This is a real integration test.",
        )
        assert result.success is True
        assert result.provider == "mock"

    @pytest.mark.asyncio
    async def test_send_with_cc_bcc(self) -> None:
        mock = MockEmailBackend()
        svc = EmailService(mock)
        result = await svc.send(
            to=["a@b.com"],
            subject="CC/BCC",
            body="body",
            cc=["cc@b.com"],
            bcc=["bcc@b.com"],
        )
        assert result.success is True
        assert mock.sent_messages[0].cc == ["cc@b.com"]
        assert mock.sent_messages[0].bcc == ["bcc@b.com"]

    @pytest.mark.asyncio
    async def test_send_with_html(self) -> None:
        mock = MockEmailBackend()
        svc = EmailService(mock)
        result = await svc.send(
            to=["a@b.com"],
            subject="HTML",
            body="plain",
            html_body="<h1>HTML</h1>",
        )
        assert result.success is True
        assert mock.sent_messages[0].html_body == "<h1>HTML</h1>"
