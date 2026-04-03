"""
Delivery Adapters

Production-ready delivery adapter infrastructure for the Murphy System.
Replaces delivery stubs with concrete adapters for document, email, chat,
voice, and translation channels.

Each adapter prepares payloads ready for real transport without requiring
external service connections at runtime.
"""

import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DeliveryChannel(Enum):
    """Supported delivery channels."""
    DOCUMENT = "document"
    EMAIL = "email"
    CHAT = "chat"
    VOICE = "voice"
    TRANSLATION = "translation"


class DeliveryStatus(Enum):
    """Delivery lifecycle states."""
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    NEEDS_APPROVAL = "needs_approval"
    NEEDS_INFO = "needs_info"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DeliveryRequest:
    """Inbound delivery request."""
    channel: DeliveryChannel
    payload: Dict[str, Any]
    session_id: str
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.session_id:
            raise ValueError("session_id is required")


@dataclass
class DeliveryResult:
    """Result of a delivery attempt."""
    request_id: str
    channel: DeliveryChannel
    status: DeliveryStatus
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Abstract base adapter
# ---------------------------------------------------------------------------

class BaseDeliveryAdapter(ABC):
    """
    Interface that every delivery adapter MUST implement.

    Adapters prepare payloads for their channel but do NOT perform
    actual network I/O (SMTP send, HTTP post, etc.).
    """

    @abstractmethod
    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        """Prepare and return a delivery result for the given request."""

    @abstractmethod
    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        """
        Validate a request before delivery.

        Returns:
            (is_valid, errors)
        """

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return current adapter health / readiness info."""


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------

class DocumentDeliveryAdapter(BaseDeliveryAdapter):
    """Generates markdown documents from structured payloads."""

    def __init__(self) -> None:
        super().__init__()
        self._delivery_count: int = 0

    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        errors: List[str] = []
        payload = request.payload
        if not payload.get("title"):
            errors.append("Missing required field: title")
        if not payload.get("content"):
            errors.append("Missing required field: content")
        return len(errors) == 0, errors

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        request_id = str(uuid.uuid4())
        is_valid, errors = self.validate(request)
        if not is_valid:
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.DOCUMENT,
                status=DeliveryStatus.FAILED,
                error="; ".join(errors),
            )

        payload = request.payload
        title = payload["title"]
        content = payload["content"]
        sections = payload.get("sections", [])

        lines = [f"# {title}", "", content, ""]
        for section in sections:
            heading = section.get("heading", "Untitled")
            body = section.get("body", "")
            lines.extend([f"## {heading}", "", body, ""])

        markdown = "\n".join(lines)
        self._delivery_count += 1
        logger.info("Document delivered: %s (session=%s)", title, request.session_id)

        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.DOCUMENT,
            status=DeliveryStatus.DELIVERED,
            output={
                "format": "markdown",
                "document": markdown,
                "title": title,
                "byte_length": len(markdown.encode("utf-8")),
            },
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "adapter": "DocumentDeliveryAdapter",
            "ready": True,
            "deliveries": self._delivery_count,
        }


class EmailDeliveryAdapter(BaseDeliveryAdapter):
    """Prepares SMTP-ready email payloads with validation."""

    _EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __init__(self) -> None:
        super().__init__()
        self._delivery_count: int = 0

    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        errors: List[str] = []
        payload = request.payload
        recipients = payload.get("to", [])
        if not recipients:
            errors.append("Missing required field: to")
        else:
            for addr in recipients:
                if not self._EMAIL_RE.match(addr):
                    errors.append(f"Invalid email address: {addr}")
        if not payload.get("subject"):
            errors.append("Missing required field: subject")
        if not payload.get("body"):
            errors.append("Missing required field: body")
        return len(errors) == 0, errors

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        request_id = str(uuid.uuid4())
        is_valid, errors = self.validate(request)
        if not is_valid:
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                error="; ".join(errors),
            )

        payload = request.payload
        smtp_payload = {
            "to": payload["to"],
            "cc": payload.get("cc", []),
            "bcc": payload.get("bcc", []),
            "from": payload.get("from", "murphy@system.local"),
            "subject": payload["subject"],
            "body": payload["body"],
            "content_type": payload.get("content_type", "text/plain"),
            "headers": payload.get("headers", {}),
        }

        self._delivery_count += 1
        logger.info(
            "Email prepared: to=%s subject=%s (session=%s)",
            smtp_payload["to"],
            smtp_payload["subject"],
            request.session_id,
        )

        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.EMAIL,
            status=DeliveryStatus.DELIVERED,
            output={"smtp_payload": smtp_payload},
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "adapter": "EmailDeliveryAdapter",
            "ready": True,
            "deliveries": self._delivery_count,
        }


class ChatDeliveryAdapter(BaseDeliveryAdapter):
    """Delivers chat messages via platform-specific connectors.

    When a ``SlackConnector`` is available and configured, Slack messages
    are delivered via the Slack Web API.  For all other platforms (or when
    the connector is unavailable) the adapter falls back to preparing the
    payload without external calls, maintaining backward compatibility.
    """

    SUPPORTED_PLATFORMS = {"slack", "teams", "discord", "webhook", "internal"}

    def __init__(self) -> None:
        super().__init__()
        self._delivery_count: int = 0
        self._slack_connector: Any = None  # lazy-loaded

    def _get_slack_connector(self) -> Any:
        """Lazy-load and cache the ``SlackConnector`` instance."""
        if self._slack_connector is None:
            try:
                from integrations.slack_connector import SlackConnector
                self._slack_connector = SlackConnector()
            except Exception:
                logger.debug("SlackConnector unavailable — Slack delivery will use payload-only mode")
        return self._slack_connector

    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        errors: List[str] = []
        payload = request.payload
        if not payload.get("message"):
            errors.append("Missing required field: message")
        platform = payload.get("platform", "internal")
        if platform not in self.SUPPORTED_PLATFORMS:
            errors.append(
                f"Unsupported platform: {platform}. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_PLATFORMS))}"
            )
        if not payload.get("channel_id") and platform != "internal":
            errors.append("Missing required field: channel_id for external platform")
        return len(errors) == 0, errors

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        request_id = str(uuid.uuid4())
        is_valid, errors = self.validate(request)
        if not is_valid:
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.CHAT,
                status=DeliveryStatus.FAILED,
                error="; ".join(errors),
            )

        payload = request.payload
        platform = payload.get("platform", "internal")
        chat_payload = {
            "platform": platform,
            "channel_id": payload.get("channel_id"),
            "message": payload["message"],
            "thread_id": payload.get("thread_id"),
            "mentions": payload.get("mentions", []),
        }

        # ── Platform-specific delivery ────────────────────────────
        if platform == "slack":
            result = self._deliver_slack(request_id, payload, request.session_id)
            if result is not None:
                self._delivery_count += 1
                return result

        # ── Fallback: payload-only mode ───────────────────────────
        self._delivery_count += 1
        logger.info(
            "Chat message prepared: platform=%s channel=%s (session=%s)",
            platform,
            chat_payload["channel_id"],
            request.session_id,
        )

        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.CHAT,
            status=DeliveryStatus.DELIVERED,
            output={"chat_payload": chat_payload},
        )

    # ── Slack delivery via SlackConnector ─────────────────────────

    def _deliver_slack(
        self,
        request_id: str,
        payload: Dict[str, Any],
        session_id: str,
    ) -> Optional[DeliveryResult]:
        """Attempt real Slack delivery.  Returns ``None`` to fall through."""
        connector = self._get_slack_connector()
        if connector is None or not connector.is_configured():
            return None  # fall through to payload-only mode

        channel_id = payload.get("channel_id", "")
        message = payload["message"]
        blocks = payload.get("blocks")

        try:
            slack_resp = connector.send_message(channel_id, message, blocks)
        except Exception as exc:
            logger.exception("Slack delivery failed for channel=%s", channel_id)
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.CHAT,
                status=DeliveryStatus.FAILED,
                error=f"Slack delivery exception: {exc}",
            )

        if slack_resp.get("ok") or slack_resp.get("success"):
            logger.info(
                "Slack message delivered: channel=%s (session=%s)",
                channel_id,
                session_id,
            )
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.CHAT,
                status=DeliveryStatus.DELIVERED,
                output={
                    "chat_payload": {
                        "platform": "slack",
                        "channel_id": channel_id,
                        "message": message,
                        "slack_ts": slack_resp.get("ts"),
                    },
                },
            )

        # Slack API returned an error
        err_msg = slack_resp.get("error", "unknown Slack API error")
        logger.warning("Slack API error: %s (channel=%s)", err_msg, channel_id)
        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.CHAT,
            status=DeliveryStatus.FAILED,
            error=f"Slack API error: {err_msg}",
        )

    def get_status(self) -> Dict[str, Any]:
        connector = self._get_slack_connector()
        return {
            "adapter": "ChatDeliveryAdapter",
            "ready": True,
            "deliveries": self._delivery_count,
            "supported_platforms": sorted(self.SUPPORTED_PLATFORMS),
            "slack_configured": bool(connector and connector.is_configured()),
        }


class VoiceDeliveryAdapter(BaseDeliveryAdapter):
    """Prepares voice scripts with playback steps."""

    def __init__(self) -> None:
        super().__init__()
        self._delivery_count: int = 0

    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        errors: List[str] = []
        payload = request.payload
        if not payload.get("script"):
            errors.append("Missing required field: script")
        language = payload.get("language", "en")
        if not isinstance(language, str) or len(language) < 2:
            errors.append(f"Invalid language code: {language}")
        return len(errors) == 0, errors

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        request_id = str(uuid.uuid4())
        is_valid, errors = self.validate(request)
        if not is_valid:
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.VOICE,
                status=DeliveryStatus.FAILED,
                error="; ".join(errors),
            )

        payload = request.payload
        script = payload["script"]
        language = payload.get("language", "en")
        speed = payload.get("speed", 1.0)

        # Build ordered playback steps
        segments = payload.get("segments")
        if segments is None:
            segments = [{"text": script, "pause_after_ms": 0}]

        playback_steps = []
        for idx, segment in enumerate(segments):
            playback_steps.append({
                "step": idx + 1,
                "text": segment.get("text", ""),
                "language": language,
                "speed": speed,
                "pause_after_ms": segment.get("pause_after_ms", 500),
            })

        voice_payload = {
            "script": script,
            "language": language,
            "speed": speed,
            "playback_steps": playback_steps,
            "estimated_duration_s": sum(
                len(s["text"]) * 0.06 / speed + s["pause_after_ms"] / 1000
                for s in playback_steps
            ),
        }

        self._delivery_count += 1
        logger.info(
            "Voice script prepared: language=%s steps=%d (session=%s)",
            language,
            len(playback_steps),
            request.session_id,
        )

        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.VOICE,
            status=DeliveryStatus.DELIVERED,
            output={"voice_payload": voice_payload},
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "adapter": "VoiceDeliveryAdapter",
            "ready": True,
            "deliveries": self._delivery_count,
        }


class TranslationDeliveryAdapter(BaseDeliveryAdapter):
    """Handles locale-based translation payloads."""

    SUPPORTED_LOCALES = {
        "en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ar", "ru", "hi",
    }

    def __init__(self) -> None:
        super().__init__()
        self._delivery_count: int = 0

    def validate(self, request: DeliveryRequest) -> tuple[bool, List[str]]:
        errors: List[str] = []
        payload = request.payload
        if not payload.get("text"):
            errors.append("Missing required field: text")
        if not payload.get("target_locale"):
            errors.append("Missing required field: target_locale")
        else:
            locale = payload["target_locale"]
            if locale not in self.SUPPORTED_LOCALES:
                errors.append(
                    f"Unsupported target locale: {locale}. "
                    f"Supported: {', '.join(sorted(self.SUPPORTED_LOCALES))}"
                )
        return len(errors) == 0, errors

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        request_id = str(uuid.uuid4())
        is_valid, errors = self.validate(request)
        if not is_valid:
            return DeliveryResult(
                request_id=request_id,
                channel=DeliveryChannel.TRANSLATION,
                status=DeliveryStatus.FAILED,
                error="; ".join(errors),
            )

        payload = request.payload
        source_locale = payload.get("source_locale", "en")
        target_locale = payload["target_locale"]
        text = payload["text"]

        translation_payload = {
            "source_locale": source_locale,
            "target_locale": target_locale,
            "source_text": text,
            "translated_text": None,  # to be filled by translation service
            "char_count": len(text),
            "glossary": payload.get("glossary", {}),
        }

        self._delivery_count += 1
        logger.info(
            "Translation prepared: %s -> %s (%d chars, session=%s)",
            source_locale,
            target_locale,
            len(text),
            request.session_id,
        )

        return DeliveryResult(
            request_id=request_id,
            channel=DeliveryChannel.TRANSLATION,
            status=DeliveryStatus.NEEDS_INFO
            if translation_payload["translated_text"] is None
            else DeliveryStatus.DELIVERED,
            output={"translation_payload": translation_payload},
            error=(
                "Translation service has not yet provided translated text"
                if translation_payload["translated_text"] is None
                else None
            ),
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "adapter": "TranslationDeliveryAdapter",
            "ready": True,
            "deliveries": self._delivery_count,
            "supported_locales": sorted(self.SUPPORTED_LOCALES),
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DeliveryOrchestrator:
    """
    Routes delivery requests to the appropriate adapter, tracks status,
    and integrates with governance gates (approval gating).
    """

    _MAX_HISTORY = 10_000

    def __init__(self) -> None:
        self._adapters: Dict[DeliveryChannel, BaseDeliveryAdapter] = {}
        self._history: List[Dict[str, Any]] = []
        self._pending_approvals: List[DeliveryRequest] = []

    @property
    def adapters(self) -> Dict[DeliveryChannel, "BaseDeliveryAdapter"]:
        """Read-only view of registered adapters."""
        return dict(self._adapters)

    # -- adapter management --------------------------------------------------

    def register_adapter(
        self, channel: DeliveryChannel, adapter: BaseDeliveryAdapter
    ) -> None:
        """Register an adapter for a delivery channel."""
        self._adapters[channel] = adapter
        logger.info("Registered adapter for channel: %s", channel.value)

    # -- delivery ------------------------------------------------------------

    def deliver(self, request: DeliveryRequest) -> DeliveryResult:
        """
        Route a delivery request to the correct adapter.

        If *requires_approval* is set on the request the delivery is
        parked in the pending-approvals queue and a NEEDS_APPROVAL result
        is returned.
        """
        request_id = str(uuid.uuid4())

        # Governance gate: approval required
        if request.requires_approval:
            capped_append(self._pending_approvals, request)
            result = DeliveryResult(
                request_id=request_id,
                channel=request.channel,
                status=DeliveryStatus.NEEDS_APPROVAL,
                output={"message": "Delivery held pending approval"},
            )
            self._record(result, request)
            logger.info(
                "Delivery held for approval: channel=%s session=%s",
                request.channel.value,
                request.session_id,
            )
            return result

        adapter = self._adapters.get(request.channel)
        if adapter is None:
            result = DeliveryResult(
                request_id=request_id,
                channel=request.channel,
                status=DeliveryStatus.FAILED,
                error=f"No adapter registered for channel: {request.channel.value}",
            )
            self._record(result, request)
            return result

        try:
            result = adapter.deliver(request)
            self._record(result, request)
            return result
        except Exception as exc:
            logger.exception("Adapter error for channel %s", request.channel.value)
            result = DeliveryResult(
                request_id=request_id,
                channel=request.channel,
                status=DeliveryStatus.FAILED,
                error=str(exc),
            )
            self._record(result, request)
            return result

    # -- status & history ----------------------------------------------------

    def get_channel_status(self) -> Dict[str, Any]:
        """Return per-channel readiness information."""
        status: Dict[str, Any] = {}
        for channel in DeliveryChannel:
            adapter = self._adapters.get(channel)
            if adapter is not None:
                status[channel.value] = {
                    "registered": True,
                    **adapter.get_status(),
                }
            else:
                status[channel.value] = {"registered": False, "ready": False}
        return status

    def get_delivery_history(
        self, session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return delivery history, optionally filtered by session."""
        if session_id is None:
            return list(self._history)
        return [h for h in self._history if h.get("session_id") == session_id]

    def get_pending_approvals(self) -> List[DeliveryRequest]:
        """Return requests waiting for governance approval."""
        return list(self._pending_approvals)

    # -- internals -----------------------------------------------------------

    def _record(self, result: DeliveryResult, request: DeliveryRequest) -> None:
        if len(self._history) >= self._MAX_HISTORY:
            self._history = self._history[self._MAX_HISTORY // 10:]
        self._history.append({
            **result.to_dict(),
            "session_id": request.session_id,
        })
