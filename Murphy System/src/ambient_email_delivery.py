"""
Ambient Email Delivery Backend
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1

Delivers ambient intelligence insights via email.
Checks for SendGrid or SMTP configuration; falls back to mock mode with a
clear warning when neither is configured.

Environment variables
---------------------
SENDGRID_API_KEY : str
    SendGrid v3 API key (takes priority over SMTP).
SENDGRID_FROM_EMAIL : str
    Sender address for SendGrid (default: murphy@murphy.local).
SMTP_HOST : str
    SMTP server hostname.
SMTP_PORT : int
    SMTP server port (default: 587).
SMTP_USER : str
    SMTP authentication username (optional).
SMTP_PASSWORD : str
    SMTP authentication password (optional).
SMTP_FROM_EMAIL : str
    Sender address for SMTP (default: murphy@murphy.local).
SMTP_USE_TLS : str
    'true' (default) to use STARTTLS; 'false' for plain.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import textwrap
import time
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SETTINGS_URL = "/ui/ambient#settings"
_FROM_DEFAULT = "murphy@murphy.local"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


def _result(
    delivered: bool,
    *,
    backend: str = "mock",
    email_id: Optional[str] = None,
    mock: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "delivered": delivered,
        "backend": backend,
        "email_id": email_id or f"amb-{int(time.time())}",
        "mock": mock,
    }
    if reason:
        out["reason"] = reason
    return out


# ---------------------------------------------------------------------------
# Email content helpers
# ---------------------------------------------------------------------------


def _build_plain(insight: Dict[str, Any]) -> str:
    title = insight.get("title", "Murphy Ambient Alert")
    body = insight.get("body", "")
    confidence = insight.get("confidence", 0)
    priority = (insight.get("priority") or "medium").upper()
    agents = ", ".join(insight.get("agents") or ["Murphy-Ambient"])

    return textwrap.dedent(
        f"""\
        ══════════════════════════════════════════
        MURPHY AMBIENT INTELLIGENCE
        ══════════════════════════════════════════

        {title}

        {body}

        ──────────────────────────────────────────
        Priority   : {priority}
        Confidence : {confidence}%
        Agents     : {agents}
        ──────────────────────────────────────────

        Manage your ambient settings:
        {_SETTINGS_URL}

        To unsubscribe, visit {_SETTINGS_URL} and disable Proactive Email Delivery.

        © 2020 Inoni LLC — Murphy Ambient Intelligence
        """
    )


def _build_html(insight: Dict[str, Any]) -> str:
    """Return a dark-themed HTML email body."""
    title = insight.get("title", "Murphy Ambient Alert")
    body_text = insight.get("body", "")
    confidence = insight.get("confidence", 0)
    priority = (insight.get("priority") or "medium").upper()
    agents = ", ".join(insight.get("agents") or ["Murphy-Ambient"])
    source = insight.get("source", "client")
    source_badge = "🤖 AI" if source == "server" else "📊 Pattern"

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body{{margin:0;padding:0;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e6edf3}}
  .wrap{{max-width:600px;margin:32px auto;background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}}
  .header{{background:#1a1f29;padding:20px 24px;border-bottom:1px solid #30363d}}
  .header h1{{margin:0;font-size:18px;font-weight:600;color:#58a6ff}}
  .header p{{margin:4px 0 0;font-size:12px;color:#8b949e}}
  .body{{padding:24px}}
  .body p{{margin:0 0 16px;line-height:1.6;font-size:14px;color:#c9d1d9}}
  .meta{{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px 16px;margin:16px 0}}
  .meta-row{{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;color:#8b949e}}
  .meta-val{{color:#e6edf3;font-weight:500}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;background:#1f6feb;color:#cae8ff;margin-left:6px}}
  .footer{{padding:16px 24px;border-top:1px solid #30363d;font-size:11px;color:#484f58;text-align:center}}
  .footer a{{color:#58a6ff;text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🧠 Murphy Ambient Intelligence</h1>
    <p>{title}</p>
  </div>
  <div class="body">
    <p>{body_text}</p>
    <div class="meta">
      <div class="meta-row"><span>Priority</span><span class="meta-val">{priority}</span></div>
      <div class="meta-row"><span>Confidence</span><span class="meta-val">{confidence}%
        <span class="badge">{source_badge}</span></span></div>
      <div class="meta-row"><span>Agents</span><span class="meta-val">{agents}</span></div>
    </div>
  </div>
  <div class="footer">
    <a href="{_SETTINGS_URL}">Manage Settings</a> &nbsp;·&nbsp;
    <a href="{_SETTINGS_URL}">Unsubscribe</a>
    <br>© 2020 Inoni LLC — Murphy Ambient Intelligence
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# SendGrid backend
# ---------------------------------------------------------------------------


def _send_sendgrid(
    insight: Dict[str, Any],
    to_email: str,
    api_key: str,
) -> Dict[str, Any]:
    """Send via SendGrid REST API using the stdlib `urllib` (no extra deps)."""
    title = insight.get("title", "Murphy Ambient Alert")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", _FROM_DEFAULT)
    email_id = f"sg-amb-{int(time.time())}"

    payload = json.dumps(
        {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": f"[Murphy] {title}",
            "content": [
                {"type": "text/plain", "value": _build_plain(insight)},
                {"type": "text/html", "value": _build_html(insight)},
            ],
        }
    ).encode()

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        logger.warning("SendGrid delivery failed: HTTP %s", status)
        return _result(False, backend="sendgrid", email_id=email_id, reason=f"HTTP {status}")
    except Exception as exc:
        logger.warning("SendGrid delivery error: %s", exc)
        return _result(False, backend="sendgrid", email_id=email_id, reason=str(exc))

    if status in (200, 202):
        logger.info("SendGrid ambient email delivered: %s", email_id)
        return _result(True, backend="sendgrid", email_id=email_id)
    return _result(False, backend="sendgrid", email_id=email_id, reason=f"HTTP {status}")


# ---------------------------------------------------------------------------
# SMTP backend
# ---------------------------------------------------------------------------


def _send_smtp(
    insight: Dict[str, Any],
    to_email: str,
    host: str,
) -> Dict[str, Any]:
    """Send via SMTP using stdlib smtplib."""
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_email = os.environ.get("SMTP_FROM_EMAIL", _FROM_DEFAULT)
    use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() != "false"

    title = insight.get("title", "Murphy Ambient Alert")
    email_id = f"smtp-amb-{int(time.time())}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Murphy] {title}"
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Message-ID"] = f"<{email_id}@murphy.local>"

    msg.attach(MIMEText(_build_plain(insight), "plain", "utf-8"))
    msg.attach(MIMEText(_build_html(insight), "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        logger.info("SMTP ambient email delivered: %s", email_id)
        return _result(True, backend="smtp", email_id=email_id)
    except Exception as exc:
        logger.warning("SMTP ambient delivery error: %s", exc)
        return _result(False, backend="smtp", email_id=email_id, reason=str(exc))


# ---------------------------------------------------------------------------
# Public delivery function
# ---------------------------------------------------------------------------


def deliver(
    insight: Dict[str, Any],
    to_emails: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Deliver an ambient insight via email.

    Checks for SendGrid or SMTP configuration and uses the first available
    backend. If neither is configured, returns a mock-mode result without
    raising an exception.

    Parameters
    ----------
    insight:
        Insight dict produced by ``ambient_synthesis.synthesize()`` or
        ``murphy_ambient.js``'s ``SynthesisEngine``.
    to_emails:
        List of recipient addresses. Falls back to the ``AMBIENT_NOTIFY_EMAIL``
        env var, then no-ops gracefully.

    Returns
    -------
    Dict with keys: ``delivered`` (bool), ``backend`` (str), ``email_id`` (str),
    ``mock`` (bool), and optionally ``reason`` (str).
    """
    try:
        recipients = to_emails or []
        if not recipients:
            env_addr = os.environ.get("AMBIENT_NOTIFY_EMAIL", "").strip()
            if env_addr:
                recipients = [a.strip() for a in env_addr.split(",") if a.strip()]

        if not recipients:
            logger.warning(
                "Ambient email delivery: no recipient address configured. "
                "Set AMBIENT_NOTIFY_EMAIL to enable real delivery."
            )
            return _result(
                False,
                backend="mock",
                mock=True,
                reason="No recipient address configured",
            )

        sendgrid_key = os.environ.get("SENDGRID_API_KEY", "").strip()
        smtp_host = os.environ.get("SMTP_HOST", "").strip()

        if sendgrid_key:
            results = [_send_sendgrid(insight, addr, sendgrid_key) for addr in recipients]
            success = next((r for r in results if r["delivered"]), None)
            return success if success is not None else results[0]

        if smtp_host:
            results = [_send_smtp(insight, addr, smtp_host) for addr in recipients]
            success = next((r for r in results if r["delivered"]), None)
            return success if success is not None else results[0]

        logger.warning(
            "Ambient email delivery: no email backend configured. "
            "Set SENDGRID_API_KEY or SMTP_HOST in .env to enable email. "
            "Deliveries will appear in the UI only."
        )
        return _result(
            False,
            backend="mock",
            mock=True,
            reason="No email backend configured",
        )

    except Exception as exc:
        # The email service must NEVER throw — always return gracefully.
        logger.error("Ambient email delivery unexpected error: %s", exc)
        return _result(
            False,
            backend="mock",
            mock=True,
            reason=f"Unexpected error: {exc}",
        )


def email_backend_mode() -> str:
    """
    Return the active email backend mode: ``'sendgrid'``, ``'smtp'``, or ``'mock'``.

    Used by ``/api/ambient/settings`` to tell the UI whether email delivery
    is in mock mode so it can show the configuration warning banner.
    """
    if os.environ.get("SENDGRID_API_KEY", "").strip():
        return "sendgrid"
    if os.environ.get("SMTP_HOST", "").strip():
        return "smtp"
    return "mock"
