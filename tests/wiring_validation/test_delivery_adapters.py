"""Tests for delivery_adapters module."""

import sys
from pathlib import Path

# Ensure the src directory is importable.
_src = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from delivery_adapters import (
    BaseDeliveryAdapter,
    ChatDeliveryAdapter,
    DeliveryChannel,
    DeliveryOrchestrator,
    DeliveryRequest,
    DeliveryResult,
    DeliveryStatus,
    DocumentDeliveryAdapter,
    EmailDeliveryAdapter,
    TranslationDeliveryAdapter,
    VoiceDeliveryAdapter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(channel, payload, session_id="test-session", **kwargs):
    return DeliveryRequest(
        channel=channel, payload=payload, session_id=session_id, **kwargs
    )


# ---------------------------------------------------------------------------
# DocumentDeliveryAdapter
# ---------------------------------------------------------------------------

class TestDocumentDeliveryAdapter:
    def test_deliver_basic_document(self):
        adapter = DocumentDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.DOCUMENT,
            {"title": "Report", "content": "Summary of findings."},
        )
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.DELIVERED
        assert result.channel == DeliveryChannel.DOCUMENT
        assert "# Report" in result.output["document"]
        assert "Summary of findings." in result.output["document"]
        assert result.output["format"] == "markdown"
        assert result.output["byte_length"] > 0

    def test_deliver_document_with_sections(self):
        adapter = DocumentDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.DOCUMENT,
            {
                "title": "Guide",
                "content": "Intro.",
                "sections": [
                    {"heading": "Setup", "body": "Install deps."},
                    {"heading": "Run", "body": "Execute main."},
                ],
            },
        )
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.DELIVERED
        doc = result.output["document"]
        assert "## Setup" in doc
        assert "## Run" in doc

    def test_validate_missing_title(self):
        adapter = DocumentDeliveryAdapter()
        req = _make_request(DeliveryChannel.DOCUMENT, {"content": "body"})
        is_valid, errors = adapter.validate(req)

        assert not is_valid
        assert any("title" in e for e in errors)

    def test_validate_missing_content(self):
        adapter = DocumentDeliveryAdapter()
        req = _make_request(DeliveryChannel.DOCUMENT, {"title": "T"})
        is_valid, errors = adapter.validate(req)

        assert not is_valid
        assert any("content" in e for e in errors)

    def test_deliver_fails_on_invalid(self):
        adapter = DocumentDeliveryAdapter()
        req = _make_request(DeliveryChannel.DOCUMENT, {})
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.FAILED
        assert result.error is not None

    def test_get_status(self):
        adapter = DocumentDeliveryAdapter()
        status = adapter.get_status()
        assert status["ready"] is True
        assert status["deliveries"] == 0

        adapter.deliver(
            _make_request(DeliveryChannel.DOCUMENT, {"title": "T", "content": "C"})
        )
        assert adapter.get_status()["deliveries"] == 1


# ---------------------------------------------------------------------------
# EmailDeliveryAdapter
# ---------------------------------------------------------------------------

class TestEmailDeliveryAdapter:
    def test_deliver_valid_email(self):
        adapter = EmailDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.EMAIL,
            {
                "to": ["user@example.com"],
                "subject": "Hello",
                "body": "World",
            },
        )
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.DELIVERED
        smtp = result.output["smtp_payload"]
        assert smtp["to"] == ["user@example.com"]
        assert smtp["subject"] == "Hello"
        assert smtp["body"] == "World"
        assert smtp["from"] == "murphy@system.local"

    def test_validate_missing_recipients(self):
        adapter = EmailDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.EMAIL, {"subject": "S", "body": "B"}
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("to" in e for e in errors)

    def test_validate_invalid_email_address(self):
        adapter = EmailDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.EMAIL,
            {"to": ["not-an-email"], "subject": "S", "body": "B"},
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("Invalid email" in e for e in errors)

    def test_validate_missing_subject(self):
        adapter = EmailDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.EMAIL,
            {"to": ["a@b.com"], "body": "B"},
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("subject" in e for e in errors)

    def test_deliver_includes_cc_bcc(self):
        adapter = EmailDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.EMAIL,
            {
                "to": ["a@b.com"],
                "cc": ["c@d.com"],
                "bcc": ["e@f.com"],
                "subject": "S",
                "body": "B",
            },
        )
        result = adapter.deliver(req)
        assert result.output["smtp_payload"]["cc"] == ["c@d.com"]
        assert result.output["smtp_payload"]["bcc"] == ["e@f.com"]


# ---------------------------------------------------------------------------
# ChatDeliveryAdapter
# ---------------------------------------------------------------------------

class TestChatDeliveryAdapter:
    def test_deliver_internal_message(self):
        adapter = ChatDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.CHAT,
            {"message": "Hello team", "platform": "internal"},
        )
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.DELIVERED
        chat = result.output["chat_payload"]
        assert chat["platform"] == "internal"
        assert chat["message"] == "Hello team"

    def test_deliver_slack_message(self):
        adapter = ChatDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.CHAT,
            {"message": "Deploy done", "platform": "slack", "channel_id": "C123"},
        )
        result = adapter.deliver(req)
        assert result.status == DeliveryStatus.DELIVERED

    def test_validate_unsupported_platform(self):
        adapter = ChatDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.CHAT,
            {"message": "Hi", "platform": "fax"},
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("Unsupported platform" in e for e in errors)

    def test_validate_missing_channel_id_for_external(self):
        adapter = ChatDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.CHAT,
            {"message": "Hi", "platform": "slack"},
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("channel_id" in e for e in errors)

    def test_validate_missing_message(self):
        adapter = ChatDeliveryAdapter()
        req = _make_request(DeliveryChannel.CHAT, {"platform": "internal"})
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("message" in e for e in errors)

    def test_get_status_includes_platforms(self):
        adapter = ChatDeliveryAdapter()
        status = adapter.get_status()
        assert "supported_platforms" in status
        assert "slack" in status["supported_platforms"]


# ---------------------------------------------------------------------------
# VoiceDeliveryAdapter
# ---------------------------------------------------------------------------

class TestVoiceDeliveryAdapter:
    def test_deliver_simple_script(self):
        adapter = VoiceDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.VOICE,
            {"script": "Welcome to Murphy.", "language": "en"},
        )
        result = adapter.deliver(req)

        assert result.status == DeliveryStatus.DELIVERED
        voice = result.output["voice_payload"]
        assert voice["script"] == "Welcome to Murphy."
        assert len(voice["playback_steps"]) == 1
        assert voice["estimated_duration_s"] > 0

    def test_deliver_with_segments(self):
        adapter = VoiceDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.VOICE,
            {
                "script": "full script",
                "segments": [
                    {"text": "Part one.", "pause_after_ms": 200},
                    {"text": "Part two.", "pause_after_ms": 300},
                ],
            },
        )
        result = adapter.deliver(req)
        assert result.status == DeliveryStatus.DELIVERED
        assert len(result.output["voice_payload"]["playback_steps"]) == 2

    def test_validate_missing_script(self):
        adapter = VoiceDeliveryAdapter()
        req = _make_request(DeliveryChannel.VOICE, {"language": "en"})
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("script" in e for e in errors)

    def test_validate_invalid_language(self):
        adapter = VoiceDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.VOICE, {"script": "Hi", "language": "x"}
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("language" in e for e in errors)


# ---------------------------------------------------------------------------
# TranslationDeliveryAdapter
# ---------------------------------------------------------------------------

class TestTranslationDeliveryAdapter:
    def test_deliver_translation(self):
        adapter = TranslationDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.TRANSLATION,
            {"text": "Hello world", "target_locale": "es"},
        )
        result = adapter.deliver(req)

        # Translation service hasn't filled translated_text yet, so the
        # status must be NEEDS_INFO (not DELIVERED with a null body).
        assert result.status == DeliveryStatus.NEEDS_INFO
        tp = result.output["translation_payload"]
        assert tp["source_locale"] == "en"
        assert tp["target_locale"] == "es"
        assert tp["source_text"] == "Hello world"
        assert tp["char_count"] == len("Hello world")

    def test_validate_missing_text(self):
        adapter = TranslationDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.TRANSLATION, {"target_locale": "fr"}
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("text" in e for e in errors)

    def test_validate_missing_target_locale(self):
        adapter = TranslationDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.TRANSLATION, {"text": "Hi"}
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("target_locale" in e for e in errors)

    def test_validate_unsupported_locale(self):
        adapter = TranslationDeliveryAdapter()
        req = _make_request(
            DeliveryChannel.TRANSLATION, {"text": "Hi", "target_locale": "xx"}
        )
        is_valid, errors = adapter.validate(req)
        assert not is_valid
        assert any("Unsupported target locale" in e for e in errors)

    def test_get_status_includes_locales(self):
        adapter = TranslationDeliveryAdapter()
        status = adapter.get_status()
        assert "supported_locales" in status
        assert "en" in status["supported_locales"]


# ---------------------------------------------------------------------------
# DeliveryOrchestrator
# ---------------------------------------------------------------------------

class TestDeliveryOrchestrator:
    def _build_orchestrator(self):
        orch = DeliveryOrchestrator()
        orch.register_adapter(DeliveryChannel.DOCUMENT, DocumentDeliveryAdapter())
        orch.register_adapter(DeliveryChannel.EMAIL, EmailDeliveryAdapter())
        orch.register_adapter(DeliveryChannel.CHAT, ChatDeliveryAdapter())
        orch.register_adapter(DeliveryChannel.VOICE, VoiceDeliveryAdapter())
        orch.register_adapter(DeliveryChannel.TRANSLATION, TranslationDeliveryAdapter())
        return orch

    def test_routes_to_correct_adapter(self):
        orch = self._build_orchestrator()
        result = orch.deliver(
            _make_request(
                DeliveryChannel.DOCUMENT,
                {"title": "T", "content": "C"},
            )
        )
        assert result.status == DeliveryStatus.DELIVERED
        assert result.channel == DeliveryChannel.DOCUMENT

    def test_fails_for_unregistered_channel(self):
        orch = DeliveryOrchestrator()
        result = orch.deliver(
            _make_request(DeliveryChannel.EMAIL, {"to": ["a@b.com"], "subject": "S", "body": "B"})
        )
        assert result.status == DeliveryStatus.FAILED
        assert "No adapter registered" in result.error

    def test_approval_gating(self):
        orch = self._build_orchestrator()
        req = _make_request(
            DeliveryChannel.EMAIL,
            {"to": ["a@b.com"], "subject": "S", "body": "B"},
            requires_approval=True,
        )
        result = orch.deliver(req)

        assert result.status == DeliveryStatus.NEEDS_APPROVAL
        pending = orch.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].session_id == "test-session"

    def test_status_tracking(self):
        orch = self._build_orchestrator()
        orch.deliver(
            _make_request(
                DeliveryChannel.DOCUMENT,
                {"title": "T", "content": "C"},
                session_id="s1",
            )
        )
        orch.deliver(
            _make_request(
                DeliveryChannel.EMAIL,
                {"to": ["a@b.com"], "subject": "S", "body": "B"},
                session_id="s2",
            )
        )

        history = orch.get_delivery_history()
        assert len(history) == 2

        filtered = orch.get_delivery_history(session_id="s1")
        assert len(filtered) == 1
        assert filtered[0]["session_id"] == "s1"

    def test_channel_status_all_registered(self):
        orch = self._build_orchestrator()
        status = orch.get_channel_status()
        for channel in DeliveryChannel:
            assert status[channel.value]["registered"] is True
            assert status[channel.value]["ready"] is True

    def test_channel_status_unregistered(self):
        orch = DeliveryOrchestrator()
        status = orch.get_channel_status()
        for channel in DeliveryChannel:
            assert status[channel.value]["registered"] is False
            assert status[channel.value]["ready"] is False

    def test_error_handling_in_adapter(self):
        """An adapter that raises is caught by the orchestrator."""

        class BrokenAdapter(BaseDeliveryAdapter):
            def deliver(self, request):
                raise RuntimeError("boom")

            def validate(self, request):
                return True, []

            def get_status(self):
                return {"ready": False}

        orch = DeliveryOrchestrator()
        orch.register_adapter(DeliveryChannel.DOCUMENT, BrokenAdapter())
        result = orch.deliver(
            _make_request(DeliveryChannel.DOCUMENT, {"title": "T", "content": "C"})
        )
        assert result.status == DeliveryStatus.FAILED
        assert "boom" in result.error

    def test_history_includes_session_id(self):
        orch = self._build_orchestrator()
        orch.deliver(
            _make_request(
                DeliveryChannel.CHAT,
                {"message": "Hi", "platform": "internal"},
                session_id="sess-abc",
            )
        )
        history = orch.get_delivery_history()
        assert history[0]["session_id"] == "sess-abc"


# ---------------------------------------------------------------------------
# DeliveryRequest validation
# ---------------------------------------------------------------------------

class TestDeliveryRequest:
    def test_requires_session_id(self):
        import pytest

        with pytest.raises(ValueError, match="session_id"):
            DeliveryRequest(
                channel=DeliveryChannel.DOCUMENT,
                payload={},
                session_id="",
            )


# ---------------------------------------------------------------------------
# DeliveryResult serialization
# ---------------------------------------------------------------------------

class TestDeliveryResult:
    def test_to_dict(self):
        result = DeliveryResult(
            request_id="r1",
            channel=DeliveryChannel.EMAIL,
            status=DeliveryStatus.DELIVERED,
            output={"key": "val"},
        )
        d = result.to_dict()
        assert d["request_id"] == "r1"
        assert d["channel"] == "email"
        assert d["status"] == "delivered"
        assert d["output"] == {"key": "val"}
        assert d["error"] is None
        assert "timestamp" in d
