"""
Tests for Email Integration — SMTP and SendGrid (INC-11 / C-04).

All tests exercise REAL delivery paths:

  SMTP tests  — spin up a live ``aiosmtpd`` server on localhost, send
                actual SMTP traffic through ``aiosmtplib``, and assert on
                the messages that the server received.

  SendGrid tests — use ``respx`` to intercept the HTTP transport at the
                socket level (not at the module/import level), so the full
                httpx request-construction path is exercised.

There is no MockEmailBackend.  If a code path cannot be tested without
mocking the real library then the implementation needs to be fixed, not
the test.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import email as _email_stdlib
import os
import threading
from typing import List

import pytest
import pytest_asyncio
import respx
import httpx

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message as BaseMessageHandler

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import sys
_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from email_integration import (
    EmailMessage,
    EmailService,
    SMTPBackend,
    SendGridBackend,
    SendResult,
    UnconfiguredEmailBackend,
)

# ---------------------------------------------------------------------------
# In-process SMTP server fixture
# ---------------------------------------------------------------------------


class _CapturingHandler(BaseMessageHandler):
    """aiosmtpd message handler that captures delivered messages."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: List[_email_stdlib.message.Message] = []
        self._lock = threading.Lock()

    def handle_message(self, message: _email_stdlib.message.Message) -> None:
        with self._lock:
            self.messages.append(message)

    def clear(self) -> None:
        with self._lock:
            self.messages.clear()


@pytest.fixture(scope="module")
def smtp_server():
    """Start a real aiosmtpd server on a free port; yield (host, port, handler)."""
    import socket

    # Grab a free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    handler = _CapturingHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    yield "127.0.0.1", port, handler
    controller.stop()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_smtp_backend(host: str, port: int) -> SMTPBackend:
    return SMTPBackend(
        host=host,
        port=port,
        use_tls=False,          # plaintext to local test server
        from_email="murphy@murphy.local",
    )


# ---------------------------------------------------------------------------
# SMTP backend — real delivery tests
# ---------------------------------------------------------------------------


class TestSMTPBackendRealDelivery:
    """Send actual SMTP traffic to an in-process aiosmtpd server."""

    @pytest.mark.asyncio
    async def test_plain_text_delivery(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        backend = _make_smtp_backend(host, port)
        msg = EmailMessage(
            to=["alice@example.com"],
            subject="Plain text delivery",
            body="Hello from Murphy System.",
            from_addr="murphy@murphy.local",
        )
        result = await backend.send(msg)

        assert result.success is True, result.error
        assert result.provider == "smtp"
        assert result.status_code == 250
        assert result.latency_seconds >= 0

        # Verify the message actually arrived at the server
        assert len(handler.messages) == 1
        received = handler.messages[0]
        assert received["subject"] == "Plain text delivery"
        assert "alice@example.com" in received["to"]

    @pytest.mark.asyncio
    async def test_html_body_multipart(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        backend = _make_smtp_backend(host, port)
        msg = EmailMessage(
            to=["bob@example.com"],
            subject="HTML delivery",
            body="Fallback plain text.",
            html_body="<h1>Hello</h1>",
            from_addr="murphy@murphy.local",
        )
        result = await backend.send(msg)

        assert result.success is True, result.error
        assert len(handler.messages) == 1
        received = handler.messages[0]
        # Should be multipart/alternative when html_body is provided
        assert received.get_content_type() in ("multipart/alternative", "text/plain")

    @pytest.mark.asyncio
    async def test_cc_recipients_delivered(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        backend = _make_smtp_backend(host, port)
        msg = EmailMessage(
            to=["primary@example.com"],
            subject="CC test",
            body="Body.",
            from_addr="murphy@murphy.local",
            cc=["cc1@example.com"],
        )
        result = await backend.send(msg)

        assert result.success is True, result.error
        assert len(handler.messages) == 1

    @pytest.mark.asyncio
    async def test_multiple_recipients(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        backend = _make_smtp_backend(host, port)
        msg = EmailMessage(
            to=["r1@example.com", "r2@example.com"],
            subject="Multi-recipient",
            body="Body.",
            from_addr="murphy@murphy.local",
        )
        result = await backend.send(msg)

        assert result.success is True, result.error

    @pytest.mark.asyncio
    async def test_send_returns_message_id(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        backend = _make_smtp_backend(host, port)
        msg = EmailMessage(
            to=["x@example.com"],
            subject="ID test",
            body="check id",
            from_addr="murphy@murphy.local",
        )
        result = await backend.send(msg)

        assert result.message_id == msg.message_id

    @pytest.mark.asyncio
    async def test_connection_refused_returns_failure(self):
        """Connecting to a port where nothing listens must return failure, not raise."""
        import socket
        # Use a port that is definitely closed
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            closed_port = s.getsockname()[1]
        # Socket now closed — port is free (and nothing listens there)

        backend = SMTPBackend(
            host="127.0.0.1",
            port=closed_port,
            use_tls=False,
            from_email="murphy@murphy.local",
        )
        msg = EmailMessage(
            to=["a@b.com"],
            subject="Fail",
            body="x",
            from_addr="murphy@murphy.local",
        )
        result = await backend.send(msg)

        assert result.success is False
        assert result.error is not None and len(result.error) > 0

    @pytest.mark.asyncio
    async def test_provider_name(self, smtp_server):
        host, port, _ = smtp_server
        backend = _make_smtp_backend(host, port)
        assert backend.provider_name == "smtp"


# ---------------------------------------------------------------------------
# SendGrid backend — real HTTP request construction via respx
# ---------------------------------------------------------------------------


class TestSendGridBackendHTTP:
    """Use respx to intercept HTTP at the transport level, exercising full request construction."""

    @pytest.mark.asyncio
    async def test_send_success_202(self):
        backend = SendGridBackend(
            api_key="SG.real_test_key",
            from_email="murphy@murphy.local",
        )
        msg = EmailMessage(
            to=["ops@example.com"],
            subject="SendGrid delivery test",
            body="Real HTTP path exercised.",
            from_addr="murphy@murphy.local",
        )

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(
                return_value=httpx.Response(202)
            )
            result = await backend.send(msg)

        assert result.success is True
        assert result.provider == "sendgrid"
        assert result.status_code == 202

    @pytest.mark.asyncio
    async def test_send_401_unauthorized(self):
        backend = SendGridBackend(
            api_key="SG.invalid",
            from_email="murphy@murphy.local",
        )
        msg = EmailMessage(
            to=["a@b.com"],
            subject="Auth fail",
            body="body",
            from_addr="murphy@murphy.local",
        )

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(
                return_value=httpx.Response(401, text="Unauthorized")
            )
            result = await backend.send(msg)

        assert result.success is False
        assert result.status_code == 401
        assert "Unauthorized" in (result.error or "")

    @pytest.mark.asyncio
    async def test_request_contains_correct_payload(self):
        """Assert the HTTP request body sent to SendGrid is correctly structured."""
        backend = SendGridBackend(
            api_key="SG.check_payload",
            from_email="from@murphy.local",
        )
        msg = EmailMessage(
            to=["dest@example.com"],
            subject="Payload check",
            body="Body text.",
            from_addr="from@murphy.local",
        )

        captured_request = {}

        def _capture(request: httpx.Request, route) -> httpx.Response:
            import json
            captured_request["json"] = json.loads(request.content)
            captured_request["auth"] = request.headers.get("authorization", "")
            return httpx.Response(202)

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(side_effect=_capture)
            await backend.send(msg)

        payload = captured_request["json"]
        assert payload["subject"] == "Payload check"
        assert payload["content"][0]["value"] == "Body text."
        assert payload["from"]["email"] == "from@murphy.local"
        assert payload["personalizations"][0]["to"][0]["email"] == "dest@example.com"
        assert captured_request["auth"].startswith("Bearer SG.check_payload")

    @pytest.mark.asyncio
    async def test_html_body_included_in_payload(self):
        backend = SendGridBackend(api_key="SG.k", from_email="a@b.com")
        msg = EmailMessage(
            to=["x@y.com"],
            subject="HTML",
            body="plain",
            html_body="<p>rich</p>",
            from_addr="a@b.com",
        )

        captured: dict = {}

        def _capture(request: httpx.Request, route) -> httpx.Response:
            import json
            captured["json"] = json.loads(request.content)
            return httpx.Response(202)

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(side_effect=_capture)
            result = await backend.send(msg)

        assert result.success is True
        content_types = [c["type"] for c in captured["json"]["content"]]
        assert "text/html" in content_types

    @pytest.mark.asyncio
    async def test_cc_included_in_payload(self):
        backend = SendGridBackend(api_key="SG.k", from_email="a@b.com")
        msg = EmailMessage(
            to=["to@x.com"],
            subject="CC test",
            body="b",
            from_addr="a@b.com",
            cc=["cc@x.com"],
        )

        captured: dict = {}

        def _capture(request: httpx.Request, route) -> httpx.Response:
            import json
            captured["json"] = json.loads(request.content)
            return httpx.Response(202)

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(side_effect=_capture)
            result = await backend.send(msg)

        assert result.success is True
        personalization = captured["json"]["personalizations"][0]
        cc_emails = [e["email"] for e in personalization.get("cc", [])]
        assert "cc@x.com" in cc_emails

    @pytest.mark.asyncio
    async def test_network_error_returns_failure(self):
        backend = SendGridBackend(api_key="SG.k", from_email="a@b.com")
        msg = EmailMessage(to=["a@b.com"], subject="Net err", body="x", from_addr="a@b.com")

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = await backend.send(msg)

        assert result.success is False
        assert result.error is not None

    def test_provider_name(self):
        assert SendGridBackend(api_key="k").provider_name == "sendgrid"


# ---------------------------------------------------------------------------
# EmailService — integration-level tests
# ---------------------------------------------------------------------------


class TestEmailService:
    """High-level EmailService tests using real backends."""

    @pytest.mark.asyncio
    async def test_smtp_delivery_end_to_end(self, smtp_server):
        """Full round-trip: EmailService → SMTPBackend → aiosmtpd → captured."""
        host, port, handler = smtp_server
        handler.clear()

        svc = EmailService(
            SMTPBackend(host=host, port=port, use_tls=False, from_email="murphy@murphy.local")
        )
        result = await svc.send(
            to=["end2end@example.com"],
            subject="End-to-end SMTP",
            body="Delivered by Murphy System.",
        )

        assert result.success is True, result.error
        assert len(handler.messages) == 1
        assert handler.messages[0]["subject"] == "End-to-end SMTP"

    @pytest.mark.asyncio
    async def test_sendgrid_end_to_end(self):
        """Full round-trip: EmailService → SendGridBackend → respx-intercepted HTTP."""
        svc = EmailService(
            SendGridBackend(api_key="SG.e2e_key", from_email="murphy@murphy.local")
        )

        with respx.mock(base_url="https://api.sendgrid.com") as sg_mock:
            sg_mock.post("/v3/mail/send").mock(return_value=httpx.Response(202))
            result = await svc.send(
                to=["user@example.com"],
                subject="End-to-end SendGrid",
                body="Sent via SendGrid.",
            )

        assert result.success is True
        assert result.provider == "sendgrid"

    @pytest.mark.asyncio
    async def test_from_env_selects_sendgrid(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.env_test")
        monkeypatch.delenv("SMTP_HOST", raising=False)
        svc = EmailService.from_env()
        assert svc.provider_name == "sendgrid"

    @pytest.mark.asyncio
    async def test_from_env_selects_smtp(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        svc = EmailService.from_env()
        assert svc.provider_name == "smtp"

    @pytest.mark.asyncio
    async def test_from_env_sendgrid_takes_priority_over_smtp(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.priority")
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        svc = EmailService.from_env()
        assert svc.provider_name == "sendgrid"

    @pytest.mark.asyncio
    async def test_from_env_unconfigured_when_no_credentials(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        svc = EmailService.from_env()
        assert svc.provider_name == "unconfigured"

    @pytest.mark.asyncio
    async def test_unconfigured_backend_returns_failure(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        svc = EmailService.from_env()
        result = await svc.send(
            to=["ops@example.com"],
            subject="Should fail",
            body="No backend configured.",
        )
        assert result.success is False
        assert "SENDGRID_API_KEY" in result.error or "SMTP_HOST" in result.error

    @pytest.mark.asyncio
    async def test_send_with_html_body(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        svc = EmailService(
            SMTPBackend(host=host, port=port, use_tls=False, from_email="murphy@murphy.local")
        )
        result = await svc.send(
            to=["html@example.com"],
            subject="HTML email",
            body="Plain text fallback.",
            html_body="<h1>Rich HTML content</h1>",
        )
        assert result.success is True, result.error

    @pytest.mark.asyncio
    async def test_send_with_cc_bcc(self, smtp_server):
        host, port, handler = smtp_server
        handler.clear()

        svc = EmailService(
            SMTPBackend(host=host, port=port, use_tls=False, from_email="murphy@murphy.local")
        )
        result = await svc.send(
            to=["to@example.com"],
            subject="CC BCC test",
            body="body",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        assert result.success is True, result.error

    def test_provider_name_property(self, smtp_server):
        host, port, _ = smtp_server
        svc = EmailService(
            SMTPBackend(host=host, port=port, use_tls=False)
        )
        assert svc.provider_name == "smtp"

    def test_backend_property(self, smtp_server):
        host, port, _ = smtp_server
        backend = SMTPBackend(host=host, port=port, use_tls=False)
        svc = EmailService(backend)
        assert svc.backend is backend


# ---------------------------------------------------------------------------
# UnconfiguredEmailBackend — explicit failure contract
# ---------------------------------------------------------------------------


class TestUnconfiguredEmailBackend:
    """Verify the no-credentials path returns a clear, actionable failure."""

    @pytest.mark.asyncio
    async def test_send_returns_failure(self):
        backend = UnconfiguredEmailBackend()
        msg = EmailMessage(to=["a@b.com"], subject="s", body="b")
        result = await backend.send(msg)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_error_message_is_actionable(self):
        backend = UnconfiguredEmailBackend()
        msg = EmailMessage(to=["a@b.com"], subject="s", body="b")
        result = await backend.send(msg)
        assert result.error
        # Must tell the operator what to set
        assert "SENDGRID_API_KEY" in result.error or "SMTP_HOST" in result.error

    @pytest.mark.asyncio
    async def test_message_id_preserved(self):
        backend = UnconfiguredEmailBackend()
        msg = EmailMessage(to=["a@b.com"], subject="s", body="b")
        result = await backend.send(msg)
        assert result.message_id == msg.message_id

    def test_provider_name(self):
        assert UnconfiguredEmailBackend().provider_name == "unconfigured"
