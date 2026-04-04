"""
Tests for Murphy System Mail Server Integration.

Tests cover:
  - EmailService.from_env() picks up MURPHY_MAIL_INTERNAL=true
  - mail_admin.py CLI parsing, validation, and quota conversion
  - Matrix email bridge: routing and bot command parsing
  - Alias resolution
  - Platform connector registration of 'internal_email'
  - InternalMailPoller configuration detection

Copyright © 2020-2026 Inoni LLC — Created by Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# ── Paths ───────────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "scripts"))


# ============================================================================
# 1. EmailService.from_env — internal mail auto-detection
# ============================================================================

class TestEmailServiceInternalMail:
    """EmailService.from_env() honours MURPHY_MAIL_INTERNAL=true."""

    def test_internal_mail_takes_priority_over_missing_smtp(self, monkeypatch):
        """MURPHY_MAIL_INTERNAL=true → SMTPBackend with murphy-mailserver host."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.setenv("MURPHY_MAIL_INTERNAL", "true")
        monkeypatch.setenv("SMTP_USER", "cpost@murphy.systems")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")

        from email_integration import EmailService, SMTPBackend

        svc = EmailService.from_env()
        assert isinstance(svc._backend, SMTPBackend)
        assert svc._backend._host == "murphy-mailserver"
        assert svc._backend._port == 587

    def test_sendgrid_still_takes_priority(self, monkeypatch):
        """SENDGRID_API_KEY beats MURPHY_MAIL_INTERNAL."""
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.test_key")
        monkeypatch.setenv("MURPHY_MAIL_INTERNAL", "true")
        monkeypatch.delenv("SMTP_HOST", raising=False)

        from email_integration import EmailService, SendGridBackend

        svc = EmailService.from_env()
        assert isinstance(svc._backend, SendGridBackend)

    def test_explicit_smtp_host_still_works_without_internal_flag(self, monkeypatch):
        """Existing SMTP_HOST path unaffected when MURPHY_MAIL_INTERNAL is not set."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.delenv("MURPHY_MAIL_INTERNAL", raising=False)

        from email_integration import EmailService, SMTPBackend

        svc = EmailService.from_env()
        assert isinstance(svc._backend, SMTPBackend)
        assert svc._backend._host == "smtp.example.com"

    def test_unconfigured_when_nothing_set(self, monkeypatch):
        """No credentials → UnconfiguredEmailBackend."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("MURPHY_MAIL_INTERNAL", raising=False)

        from email_integration import EmailService, UnconfiguredEmailBackend

        svc = EmailService.from_env()
        assert isinstance(svc._backend, UnconfiguredEmailBackend)

    def test_internal_flag_false_does_not_activate(self, monkeypatch):
        """MURPHY_MAIL_INTERNAL=false does NOT activate internal backend."""
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.setenv("MURPHY_MAIL_INTERNAL", "false")

        from email_integration import EmailService, UnconfiguredEmailBackend

        svc = EmailService.from_env()
        assert isinstance(svc._backend, UnconfiguredEmailBackend)


# ============================================================================
# 2. mail_admin.py — CLI parsing and quota conversion
# ============================================================================

class TestMailAdminCLI:
    """Tests for scripts/mail_admin.py."""

    def _import_mail_admin(self):
        spec = importlib.util.spec_from_file_location(
            "mail_admin", _REPO / "scripts" / "mail_admin.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_quota_parse_gb(self):
        mod = self._import_mail_admin()
        assert mod._parse_quota_mb("5G") == 5120
        assert mod._parse_quota_mb("1G") == 1024
        assert mod._parse_quota_mb("10G") == 10240

    def test_quota_parse_mb(self):
        mod = self._import_mail_admin()
        assert mod._parse_quota_mb("500M") == 500
        assert mod._parse_quota_mb("1024M") == 1024

    def test_quota_parse_tb(self):
        mod = self._import_mail_admin()
        assert mod._parse_quota_mb("1T") == 1024 * 1024

    def test_validate_email_valid(self):
        mod = self._import_mail_admin()
        assert mod._validate_email("cpost@murphy.systems") is True
        assert mod._validate_email("d.post@murphy.systems") is True

    def test_validate_email_invalid(self):
        mod = self._import_mail_admin()
        assert mod._validate_email("notanemail") is False
        assert mod._validate_email("@murphy.systems") is False
        assert mod._validate_email("user@") is False

    def test_quota_invalid_raises(self):
        mod = self._import_mail_admin()
        with pytest.raises(SystemExit):
            mod._parse_quota_mb("notaquota")


# ============================================================================
# 3. Matrix email bridge — routing and bot command parsing
# ============================================================================

class TestMatrixEmailBridge:
    """Tests for src/matrix_bridge/email_bridge.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from matrix_bridge import email_bridge
        self.bridge = email_bridge

    def test_route_support_email(self):
        msg = self.bridge.EmailMessage(
            message_id="<1@test>",
            sender="external@example.com",
            recipients=["support@murphy.systems"],
            subject="Need help",
            body="Hello, I need help.",
        )
        notifications = self.bridge.route_email_to_matrix(msg)
        rooms = [n.room for n in notifications]
        assert "#murphy-support" in rooms
        # Should also post to #murphy-comms
        assert self.bridge.COMMS_NOTIFICATION_ROOM in rooms

    def test_route_unknown_address_no_room_notification(self):
        msg = self.bridge.EmailMessage(
            message_id="<2@test>",
            sender="external@example.com",
            recipients=["cpost@murphy.systems"],
            subject="Personal",
            body="Hi Corey.",
        )
        notifications = self.bridge.route_email_to_matrix(msg)
        # No known room for cpost@ — no notifications
        assert len(notifications) == 0

    def test_route_multiple_recipients(self):
        msg = self.bridge.EmailMessage(
            message_id="<3@test>",
            sender="external@example.com",
            recipients=["sales@murphy.systems", "support@murphy.systems"],
            subject="Inquiry",
            body="We have a question.",
        )
        notifications = self.bridge.route_email_to_matrix(msg)
        rooms = [n.room for n in notifications]
        assert "#murphy-sales" in rooms
        assert "#murphy-support" in rooms
        assert self.bridge.COMMS_NOTIFICATION_ROOM in rooms

    def test_parse_bot_command_valid(self):
        cmd = "!murphy email send cpost@murphy.systems SubjectHere Body text here"
        result = self.bridge.parse_bot_email_command(cmd)
        assert result is not None
        assert result["to"] == "cpost@murphy.systems"
        assert result["subject"] == "SubjectHere"
        assert result["body"] == "Body text here"

    def test_parse_bot_command_not_email_command(self):
        result = self.bridge.parse_bot_email_command("!murphy status")
        assert result is None

    def test_parse_bot_command_missing_body(self):
        result = self.bridge.parse_bot_email_command("!murphy email send cpost@murphy.systems Subject")
        assert result is None

    def test_resolve_room_known(self):
        assert self.bridge._resolve_room("sales@murphy.systems") == "#murphy-sales"
        assert self.bridge._resolve_room("engineering@murphy.systems") == "#murphy-engineering"

    def test_resolve_room_unknown(self):
        assert self.bridge._resolve_room("unknown@murphy.systems") is None

    def test_poller_not_configured_without_env(self, monkeypatch):
        monkeypatch.delenv("MURPHY_MAIL_INTERNAL", raising=False)
        monkeypatch.delenv("IMAP_HOST", raising=False)
        monkeypatch.delenv("IMAP_USER", raising=False)
        monkeypatch.delenv("IMAP_PASSWORD", raising=False)
        monkeypatch.delenv("SMTP_USER", raising=False)
        monkeypatch.delenv("SMTP_PASSWORD", raising=False)

        poller = self.bridge.InternalMailPoller(on_notification=lambda n: None)
        assert not poller.is_configured

    def test_poller_configured_with_internal_flag(self, monkeypatch):
        monkeypatch.setenv("MURPHY_MAIL_INTERNAL", "true")
        monkeypatch.setenv("IMAP_USER", "cpost@murphy.systems")
        monkeypatch.setenv("IMAP_PASSWORD", "secret")

        poller = self.bridge.InternalMailPoller(on_notification=lambda n: None)
        assert poller.is_configured
        assert poller.imap_host == "murphy-mailserver"


# ============================================================================
# 4. Alias resolution — config file contents
# ============================================================================

class TestAliasConfig:
    """Validate config/mail/postfix-virtual.cf contains required aliases."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.cf_path = _REPO / "config" / "mail" / "postfix-virtual.cf"
        assert self.cf_path.exists(), "postfix-virtual.cf must exist"
        self.content = self.cf_path.read_text()

    def test_required_aliases_present(self):
        required = [
            "sales@murphy.systems",
            "marketing@murphy.systems",
            "pr@murphy.systems",
            "allstaff@murphy.systems",
            "operations@murphy.systems",
            "support@murphy.systems",
            "billing@murphy.systems",
            "legal@murphy.systems",
            "hr@murphy.systems",
            "admin@murphy.systems",
            "postmaster@murphy.systems",
            "abuse@murphy.systems",
            "info@murphy.systems",
            "hello@murphy.systems",
            "security@murphy.systems",
            "engineering@murphy.systems",
            "careers@murphy.systems",
        ]
        for alias in required:
            assert alias in self.content, f"Missing alias: {alias}"

    def test_allstaff_includes_all_personal_accounts(self):
        personal = [
            "cpost@murphy.systems",
            "hpost@murphy.systems",
            "abeltaine@murphy.systems",
            "mpost@murphy.systems",
            "jcarney@murphy.systems",
            "bgillespie@murphy.systems",
            "lpost@murphy.systems",
            "kpost@murphy.systems",
            "d.post@murphy.systems",
            "zgillespie@murphy.systems",
        ]
        # Find allstaff line
        allstaff_line = next(
            (l for l in self.content.splitlines() if l.startswith("allstaff@")), None
        )
        assert allstaff_line is not None, "allstaff@ alias line not found"
        for account in personal:
            assert account in allstaff_line, f"allstaff@ missing: {account}"


# ============================================================================
# 5. Platform connector registration
# ============================================================================

class TestInternalEmailConnector:
    """internal_email connector is registered in PlatformConnectorFramework."""

    def test_internal_email_in_defaults(self):
        from platform_connector_framework import DEFAULT_PLATFORMS

        ids = [c.connector_id for c in DEFAULT_PLATFORMS]
        assert "internal_email" in ids

    def test_internal_email_capabilities(self):
        from platform_connector_framework import DEFAULT_PLATFORMS

        connector = next(c for c in DEFAULT_PLATFORMS if c.connector_id == "internal_email")
        caps = connector.capabilities
        assert "send_email" in caps
        assert "receive_email" in caps
        assert "manage_accounts" in caps
        assert "manage_aliases" in caps

    def test_framework_registers_internal_email(self):
        from platform_connector_framework import PlatformConnectorFramework

        pcf = PlatformConnectorFramework()
        defn = pcf._definitions.get("internal_email")
        assert defn is not None
        assert defn.platform == "internal_email"


# ============================================================================
# 6. ambient_email_delivery — internal mail auto-detection
# ============================================================================

class TestAmbientEmailDeliveryInternalMail:
    """ambient_email_delivery.email_backend_mode() respects MURPHY_MAIL_INTERNAL."""

    def test_internal_mail_reported_as_smtp(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.setenv("MURPHY_MAIL_INTERNAL", "true")

        # Force reimport to pick up env changes
        import importlib
        import ambient_email_delivery
        importlib.reload(ambient_email_delivery)

        result = ambient_email_delivery.email_backend_mode()
        assert result == "smtp"

    def test_mock_when_nothing_set(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("MURPHY_MAIL_INTERNAL", raising=False)

        import importlib
        import ambient_email_delivery
        importlib.reload(ambient_email_delivery)

        result = ambient_email_delivery.email_backend_mode()
        assert result == "mock"
