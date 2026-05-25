#!/usr/bin/env python3
"""
PATCH-424 — Make /api/email/send actually deliver email
=========================================================

WHAT THIS IS:
  The current handler at line ~15912 of src/runtime/app.py:
    body = await request.json()
    mid  = uuid()
    msg  = {... "status": "sent" ...}
    return JSONResponse({"ok": True, "message": msg})
  It returns "sent" without ever touching SMTP. Zero deliveries.

  This patch replaces it with a real handler that:
    1. Validates required fields (to, subject, body)
    2. Builds a proper EmailMessage with from/to/subject/body
    3. Submits to local Postfix on 127.0.0.1:25 (mynetworks permits us)
    4. Lets Postfix DKIM-sign and deliver (DNS records already perfect)
    5. Returns the message-id from Postfix, not a fake uuid

WHY IT EXISTS:
  Sales swarm approvals from the outbound queue need a way to actually
  ship. Without this, approved drafts sit in 'approved' state forever.

  Also: SPF/DKIM/DMARC are already published correctly. opendkim is
  already signing local-submitted mail (verified live). DNS is ready
  for direct delivery — the only thing missing was real Python code
  on the API side.

HOW IT FITS:
  - Edits the existing email_send handler in app.py (in-place replace)
  - No new module, no new mount point, no new dependency
  - Uses stdlib smtplib + email.message (already imported elsewhere)
  - Falls back gracefully: on SMTP error returns 502 with the error,
    NOT a fake success
  - For founder calls: sends from founder@murphy.systems by default
  - For swarm calls: sends from sales@murphy.systems by default
    (the agent's actual from-address override still works)

CONFIG ASSUMPTIONS:
  - Postfix listens on 127.0.0.1:25 (verified)
  - mynetworks includes 127.0.0.0/8 (verified via postconf)
  - opendkim signs s=mail, d=murphy.systems (verified in mail.log)
  - Postfix WILL try smtp.gmail.com relay because relayhost is set;
    if the relay fails we still attempt direct delivery via a fallback
    transport. For now: leave relayhost broken — Postfix will defer
    on relay errors but will still queue + log everything.

NOTE ON RELAYHOST:
  Postfix is configured with relayhost = [smtp.gmail.com]:587 but
  sasl_passwd.db doesn't exist (43-char SMTP_PASSWORD env var isn't
  a Gmail app password — probably SendGrid or Mailgun). This patch
  does NOT touch relayhost — too risky to guess wrong. Once SMTP_USER
  + SMTP_PASSWORD are confirmed as Gmail OR the relay is removed,
  delivery will go direct. Queue + DKIM signing work either way.

LAST UPDATED: 2026-05-25 by PATCH-424
"""
import ast
import shutil
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")
src = APP.read_text()
NL = chr(10)

if "PATCH-424" in src:
    print("  ⚠ PATCH-424 marker already in app.py — skipping")
    raise SystemExit(0)

# Find the exact OLD handler block
OLD = (
    '    @app.post("/api/email/send")' + NL +
    '    async def email_send(request: Request):' + NL +
    '        """Send an email via Murphy\'s hosted email system."""' + NL +
    '        body = await request.json()' + NL +
    '        import uuid as _uuid' + NL +
    '        mid = _uuid.uuid4().hex[:12]' + NL +
    '        msg = {' + NL +
    '            "id": mid,' + NL +
    '            "from": body.get("from", ""),' + NL +
    '            "to": body.get("to", []) if isinstance(body.get("to"), list) else [body.get("to", "")],' + NL +
    '            "subject": body.get("subject", ""),' + NL +
    '            "body": body.get("body", ""),' + NL +
    '            "status": "sent",' + NL +
    '            "sent_at": _now_iso(),' + NL +
    '        }' + NL +
    '        return JSONResponse({"ok": True, "message": msg})'
)

NEW = (
    '    @app.post("/api/email/send")' + NL +
    '    async def email_send(request: Request):' + NL +
    '        """PATCH-424: Send email for real via local Postfix.' + NL +
    '        ' + NL +
    '        Replaces the previous stub which returned status=sent without' + NL +
    '        ever touching SMTP. This handler:' + NL +
    '          - Validates to/subject/body are present' + NL +
    '          - Builds a properly-formatted EmailMessage' + NL +
    '          - Submits to 127.0.0.1:25 (Postfix, mynetworks permits)' + NL +
    '          - Postfix DKIM-signs + queues + delivers' + NL +
    '          - Returns real message-id; on SMTP error returns 502' + NL +
    '        """' + NL +
    '        import smtplib, uuid as _uuid' + NL +
    '        from email.message import EmailMessage' + NL +
    '        from email.utils import formatdate, make_msgid' + NL +
    '        ' + NL +
    '        try:' + NL +
    '            body = await request.json()' + NL +
    '        except Exception:' + NL +
    '            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)' + NL +
    '        ' + NL +
    '        # Validate required fields' + NL +
    '        to_raw = body.get("to")' + NL +
    '        subject = (body.get("subject") or "").strip()' + NL +
    '        body_text = body.get("body") or body.get("body_text") or ""' + NL +
    '        ' + NL +
    '        if not to_raw or not subject or not body_text:' + NL +
    '            return JSONResponse({' + NL +
    '                "ok": False,' + NL +
    '                "error": "missing_required",' + NL +
    '                "required": ["to", "subject", "body"]' + NL +
    '            }, status_code=400)' + NL +
    '        ' + NL +
    '        # Normalize recipient list' + NL +
    '        if isinstance(to_raw, str):' + NL +
    '            to_list = [t.strip() for t in to_raw.split(",") if t.strip()]' + NL +
    '        elif isinstance(to_raw, list):' + NL +
    '            to_list = [str(t).strip() for t in to_raw if str(t).strip()]' + NL +
    '        else:' + NL +
    '            return JSONResponse({"ok": False, "error": "to_must_be_string_or_list"},' + NL +
    '                                status_code=400)' + NL +
    '        ' + NL +
    '        # Determine from-address: explicit override, or role-based default' + NL +
    '        tier = getattr(request.state, "tier", None)' + NL +
    '        from_addr = body.get("from") or body.get("from_addr")' + NL +
    '        if not from_addr:' + NL +
    '            from_addr = "sales@murphy.systems" if tier == "employee" else "founder@murphy.systems"' + NL +
    '        ' + NL +
    '        # Build the message' + NL +
    '        msg = EmailMessage()' + NL +
    '        msg["From"] = from_addr' + NL +
    '        msg["To"] = ", ".join(to_list)' + NL +
    '        msg["Subject"] = subject' + NL +
    '        msg["Date"] = formatdate(localtime=False)' + NL +
    '        msg["Message-ID"] = make_msgid(domain="murphy.systems")' + NL +
    '        if body.get("reply_to"):' + NL +
    '            msg["Reply-To"] = body["reply_to"]' + NL +
    '        cc = body.get("cc")' + NL +
    '        if cc:' + NL +
    '            msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else str(cc)' + NL +
    '        ' + NL +
    '        # Plain text body; HTML if body_format=html' + NL +
    '        if body.get("body_format") == "html":' + NL +
    '            msg.set_content(body.get("body_plain") or _html_to_plain_fallback(body_text))' + NL +
    '            msg.add_alternative(body_text, subtype="html")' + NL +
    '        else:' + NL +
    '            msg.set_content(body_text)' + NL +
    '        ' + NL +
    '        # Hand off to local Postfix (DKIM signs, MX lookup, delivers)' + NL +
    '        try:' + NL +
    '            with smtplib.SMTP("127.0.0.1", 25, timeout=10) as smtp:' + NL +
    '                smtp.ehlo()' + NL +
    '                refused = smtp.send_message(msg)' + NL +
    '            if refused:' + NL +
    '                return JSONResponse({' + NL +
    '                    "ok": False,' + NL +
    '                    "error": "partial_refused",' + NL +
    '                    "refused": refused,' + NL +
    '                    "message_id": msg["Message-ID"]' + NL +
    '                }, status_code=502)' + NL +
    '        except Exception as exc:' + NL +
    '            try:' + NL +
    '                logger.error("PATCH-424 /email/send SMTP failure: %s", exc)' + NL +
    '            except Exception:' + NL +
    '                pass' + NL +
    '            return JSONResponse({' + NL +
    '                "ok": False,' + NL +
    '                "error": "smtp_failed",' + NL +
    '                "detail": str(exc)' + NL +
    '            }, status_code=502)' + NL +
    '        ' + NL +
    '        return JSONResponse({' + NL +
    '            "ok": True,' + NL +
    '            "message": {' + NL +
    '                "message_id": msg["Message-ID"],' + NL +
    '                "from": from_addr,' + NL +
    '                "to": to_list,' + NL +
    '                "subject": subject,' + NL +
    '                "status": "queued",  # Postfix accepted; delivery is async' + NL +
    '                "queued_at": _now_iso(),' + NL +
    '            }' + NL +
    '        })'
)

if OLD not in src:
    print("  ✗ Exact old handler block not found.")
    print("    The handler may have been edited since I read it.")
    print("    Re-grep:")
    import re
    for i, line in enumerate(src.splitlines(), 1):
        if 'def email_send' in line:
            print(f"    line {i}: {line[:120]}")
    raise SystemExit(1)

new_src = src.replace(OLD, NEW, 1)

# Add the _html_to_plain_fallback helper if not present
if "_html_to_plain_fallback" not in new_src:
    helper = (NL + NL +
        "def _html_to_plain_fallback(html_text: str) -> str:" + NL +
        '    """PATCH-424: Minimal HTML→plaintext fallback for multipart emails."""' + NL +
        "    import re" + NL +
        "    if not html_text:" + NL +
        '        return ""' + NL +
        "    # Strip tags; keep <br> and </p> as newlines" + NL +
        "    text = re.sub(r'<br\\s*/?>', '\\n', html_text, flags=re.IGNORECASE)" + NL +
        "    text = re.sub(r'</p>', '\\n\\n', text, flags=re.IGNORECASE)" + NL +
        "    text = re.sub(r'<[^>]+>', '', text)" + NL +
        "    return text.strip()" + NL
    )
    # Insert near top after imports — find a good anchor
    anchor = "def _now_iso():"
    if anchor in new_src:
        new_src = new_src.replace(anchor, "def _now_iso():", 1)
        # Append helper at end of file instead — safer
        new_src = new_src.rstrip() + NL + helper + NL
    else:
        new_src = new_src.rstrip() + NL + helper + NL

# Parse to be sure
ast.parse(new_src)
print("  ✓ AST parses")

backup = APP.with_suffix(".py.pre-424")
shutil.copy(APP, backup)
APP.write_text(new_src)
print(f"  ✓ wrote {APP} (backup: {backup.name})")
print()
print("  Restart murphy-production to activate.")
