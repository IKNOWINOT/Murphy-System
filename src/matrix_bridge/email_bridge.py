"""
Matrix ↔ Email Bridge — Routes emails to Matrix rooms and vice versa.

Features:
- Routes emails received on specific addresses to Matrix rooms
  (e.g., support@murphy.systems → #murphy-support room)
- Murphy bot command: ``!murphy email send <to> <subject> <body>``
- Posts email delivery notifications to #murphy-comms room
- Polls the internal mailserver via IMAP for new messages

Environment variables
---------------------
MURPHY_MAIL_INTERNAL : str
    Set to ``true`` to use the internal docker-mailserver.
IMAP_HOST : str
    IMAP server hostname (default: murphy-mailserver when MURPHY_MAIL_INTERNAL=true).
IMAP_PORT : int
    IMAP server port (default: 993).
IMAP_USER : str
    IMAP account to poll (e.g., murphy-bot@murphy.systems).
IMAP_PASSWORD : str
    IMAP account password.
SMTP_HOST : str
    SMTP server for outgoing mail.
SMTP_PORT : int
    SMTP port (default: 587).
SMTP_USER : str
    SMTP username.
SMTP_PASSWORD : str
    SMTP password.
MATRIX_BRIDGE_POLL_INTERVAL : int
    Seconds between IMAP polls (default: 30).

Copyright © 2020-2026 Inoni LLC — Created by Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import email as email_lib
import imaplib
import logging
import os
import smtplib
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Routing table: email address prefix → Matrix room alias ────────────────
EMAIL_TO_ROOM_MAP: Dict[str, str] = {
    "support":      "#murphy-support",
    "sales":        "#murphy-sales",
    "marketing":    "#murphy-marketing",
    "pr":           "#murphy-pr",
    "operations":   "#murphy-operations",
    "billing":      "#murphy-billing",
    "legal":        "#murphy-legal",
    "hr":           "#murphy-hr",
    "security":     "#murphy-security",
    "engineering":  "#murphy-engineering",
    "admin":        "#murphy-admin",
    "careers":      "#murphy-careers",
    "info":         "#murphy-info",
    "allstaff":     "#murphy-general",
}

# ── Notification room ──────────────────────────────────────────────────────
COMMS_NOTIFICATION_ROOM = "#murphy-comms"

DOMAIN = "murphy.systems"


@dataclass
class EmailMessage:
    """A simplified inbound email message."""

    message_id: str
    sender: str
    recipients: List[str]
    subject: str
    body: str
    html_body: Optional[str] = None
    in_reply_to: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class MatrixNotification:
    """A notification to post to a Matrix room."""

    room: str
    text: str
    html: Optional[str] = None


def _resolve_room(recipient_addr: str) -> Optional[str]:
    """Map an email recipient address to a Matrix room alias.

    Args:
        recipient_addr: Full email address, e.g. ``support@murphy.systems``.

    Returns:
        Matrix room alias string, or ``None`` if no mapping exists.
    """
    local = recipient_addr.split("@")[0].lower()
    return EMAIL_TO_ROOM_MAP.get(local)


def route_email_to_matrix(msg: EmailMessage) -> List[MatrixNotification]:
    """Convert an inbound email into one or more Matrix room notifications.

    Args:
        msg: The inbound :class:`EmailMessage`.

    Returns:
        List of :class:`MatrixNotification` objects (one per matched room).
    """
    notifications: List[MatrixNotification] = []

    matched_rooms: set[str] = set()
    for recipient in msg.recipients:
        room = _resolve_room(recipient)
        if room and room not in matched_rooms:
            matched_rooms.add(room)
            text = (
                f"📧 **New email** | From: `{msg.sender}` | To: `{recipient}`\n"
                f"**Subject:** {msg.subject}\n\n"
                f"{msg.body[:500]}{'...' if len(msg.body) > 500 else ''}"
            )
            html = (
                f"<b>📧 New email</b> from <code>{msg.sender}</code> "
                f"to <code>{recipient}</code><br/>"
                f"<b>Subject:</b> {msg.subject}<br/><br/>"
                f"<pre>{msg.body[:500]}{'...' if len(msg.body) > 500 else ''}</pre>"
            )
            notifications.append(MatrixNotification(room=room, text=text, html=html))

    # Always post a brief notification to #murphy-comms
    if matched_rooms:
        comms_text = (
            f"📧 Email received for {', '.join(sorted(matched_rooms))} "
            f"— routed from {msg.sender} (subject: {msg.subject})"
        )
        notifications.append(
            MatrixNotification(room=COMMS_NOTIFICATION_ROOM, text=comms_text)
        )

    return notifications


def parse_bot_email_command(command_text: str) -> Optional[Dict[str, str]]:
    """Parse a Murphy bot ``!murphy email send`` command.

    Expected format::

        !murphy email send <to_email> <subject> <body>

    Args:
        command_text: The raw command string from Matrix.

    Returns:
        Dict with keys ``to``, ``subject``, ``body``, or ``None`` if not an
        email send command.
    """
    text = command_text.strip()
    prefix = "!murphy email send"
    if not text.lower().startswith(prefix):
        return None

    rest = text[len(prefix):].strip()
    parts = rest.split(None, 2)  # split into at most 3 parts: to, subject, body
    if len(parts) < 3:
        logger.warning("bot email command missing fields: %r", command_text)
        return None

    return {"to": parts[0], "subject": parts[1], "body": parts[2]}


class InternalMailPoller:
    """Polls the internal IMAP server for new messages and routes them.

    This class is a lightweight synchronous poller intended to be run in a
    background thread or async executor.  It does not depend on any specific
    Matrix client library — callers provide a callback to handle each
    :class:`MatrixNotification`.

    Args:
        on_notification: Callable invoked for each :class:`MatrixNotification`.
        poll_interval: Seconds between IMAP polls (default 30).
    """

    def __init__(
        self,
        on_notification: Any,
        poll_interval: int = 30,
    ) -> None:
        self._on_notification = on_notification
        self._poll_interval = poll_interval
        self._running = False

        _internal = os.environ.get("MURPHY_MAIL_INTERNAL", "").lower() == "true"
        self.imap_host = (
            os.environ.get("IMAP_HOST")
            or ("murphy-mailserver" if _internal else None)
        )
        self.imap_port = int(os.environ.get("IMAP_PORT", "993"))
        self.imap_user = os.environ.get("IMAP_USER") or os.environ.get("SMTP_USER")
        self.imap_pass = os.environ.get("IMAP_PASSWORD") or os.environ.get("SMTP_PASSWORD")

    @property
    def is_configured(self) -> bool:
        """Return True if IMAP credentials are available."""
        return bool(self.imap_host and self.imap_user and self.imap_pass)

    def _fetch_unseen(self) -> List[EmailMessage]:
        """Connect to IMAP and return unseen messages."""
        if not self.is_configured:
            return []

        messages: List[EmailMessage] = []
        try:
            imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            imap.login(self.imap_user, self.imap_pass)
            imap.select("INBOX")

            _, nums = imap.search(None, "UNSEEN")
            for num in nums[0].split():
                _, data = imap.fetch(num, "(RFC822)")
                raw = data[0][1]
                msg = email_lib.message_from_bytes(raw)

                body = ""
                html_body = None
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain" and not body:
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        elif ct == "text/html" and not html_body:
                            html_body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                to_header = msg.get("To", "")
                recipients = [a.strip() for a in to_header.split(",") if a.strip()]

                messages.append(
                    EmailMessage(
                        message_id=msg.get("Message-ID", f"msg_{num.decode()}"),
                        sender=msg.get("From", ""),
                        recipients=recipients,
                        subject=msg.get("Subject", "(no subject)"),
                        body=body,
                        html_body=html_body,
                        in_reply_to=msg.get("In-Reply-To"),
                    )
                )

            imap.close()
            imap.logout()
        except Exception:
            logger.exception("IMAP polling error (host=%s)", self.imap_host)
        return messages

    def poll_once(self) -> None:
        """Fetch unseen messages and dispatch notifications."""
        messages = self._fetch_unseen()
        for msg in messages:
            notifications = route_email_to_matrix(msg)
            for notif in notifications:
                try:
                    self._on_notification(notif)
                except Exception:
                    logger.exception("Error dispatching Matrix notification for room %s", notif.room)

    def start(self) -> None:
        """Run the poll loop synchronously (blocking)."""
        if not self.is_configured:
            logger.warning(
                "InternalMailPoller: IMAP not configured — polling disabled. "
                "Set MURPHY_MAIL_INTERNAL=true or IMAP_HOST/IMAP_USER/IMAP_PASSWORD."
            )
            return

        self._running = True
        logger.info(
            "InternalMailPoller: starting poll loop (host=%s, interval=%ds)",
            self.imap_host,
            self._poll_interval,
        )
        while self._running:
            try:
                self.poll_once()
            except Exception:
                logger.exception("Unexpected error in poll loop")
            time.sleep(self._poll_interval)

    def stop(self) -> None:
        """Signal the poll loop to stop."""
        self._running = False


class EmailSender:
    """Sends emails via the internal SMTP server (or external SMTP).

    Intended for use by the Matrix bridge to send replies and notifications.
    """

    def __init__(self) -> None:
        _internal = os.environ.get("MURPHY_MAIL_INTERNAL", "").lower() == "true"
        self.smtp_host = (
            os.environ.get("SMTP_HOST")
            or ("murphy-mailserver" if _internal else None)
        )
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_pass = os.environ.get("SMTP_PASSWORD")
        self.from_addr = (
            os.environ.get("SMTP_FROM_EMAIL")
            or f"noreply@{DOMAIN}"
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.smtp_host)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        from_addr: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> bool:
        """Send an email.  Returns True on success, False on failure."""
        if not self.is_configured:
            logger.warning("EmailSender: SMTP not configured — message not sent.")
            return False

        sender = from_addr or self.from_addr
        try:
            msg = MIMEMultipart("alternative") if html_body else MIMEText(body, "plain")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to
            if html_body:
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                if self.smtp_user and self.smtp_pass:
                    smtp.login(self.smtp_user, self.smtp_pass)
                smtp.sendmail(sender, [to], msg.as_string())

            logger.info("EmailSender: sent email to %s (subject: %s)", to, subject)
            return True
        except Exception:
            logger.exception("EmailSender: failed to send email to %s", to)
            return False
