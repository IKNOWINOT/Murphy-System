"""
Ship 31ae — Deliverability hardening.

Builds the headers Gmail / Yahoo / Outlook expect from a high-trust
sender per their 2024 bulk-sender requirements.

References:
  RFC 2369 — List-* headers
  RFC 8058 — One-click unsubscribe
  RFC 3834 — Auto-submitted
  Gmail 2024 — Feedback-ID, ARC, DMARC alignment
  Yahoo 2024 — List-Unsubscribe-Post header
"""
import secrets
from email.utils import formatdate, make_msgid

def add_deliverability_headers(msg, *,
                                from_addr="murphy@murphy.systems",
                                recipient_email=None,
                                campaign_id="murphy-direct",
                                is_transactional=True):
    """
    Mutate `msg` (email.Message) in place, adding the 2024 bulk-sender
    headers that Gmail and Yahoo expect.
    
    Args:
      msg: an email.message.EmailMessage or MIMEMultipart instance
      from_addr: the From: address (used for List-Unsubscribe mailto)
      recipient_email: needed for per-recipient unsubscribe token
      campaign_id: feedback-ID category (groups for reputation)
      is_transactional: if True, lighter unsubscribe (no Precedence: bulk)
    """
    # Ensure Date, Message-ID exist
    if "Date" not in msg:
        msg["Date"] = formatdate(localtime=True)
    if "Message-ID" not in msg:
        msg["Message-ID"] = make_msgid(domain="murphy.systems")
    
    # MIME-Version is non-negotiable
    if "MIME-Version" not in msg:
        msg["MIME-Version"] = "1.0"
    
    # Per-recipient unsubscribe token (used in URL + mailto)
    token = secrets.token_urlsafe(16) if recipient_email else "default"
    
    # ── List-Unsubscribe — RFC 2369 + RFC 8058 ──
    unsub_mailto = f"mailto:unsubscribe@murphy.systems?subject=unsubscribe&body={recipient_email or ''}"
    unsub_url = f"https://murphy.systems/u/{token}"
    if recipient_email:
        unsub_url = f"https://murphy.systems/unsubscribe?e={recipient_email}&t={token}"
    
    # Replace if exists, add if not
    if "List-Unsubscribe" in msg:
        del msg["List-Unsubscribe"]
    msg["List-Unsubscribe"] = f"<{unsub_url}>, <{unsub_mailto}>"
    
    # RFC 8058 — declares we support one-click unsubscribe via HTTP POST
    if "List-Unsubscribe-Post" in msg:
        del msg["List-Unsubscribe-Post"]
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    
    # ── Feedback-ID — Google spam feedback loop ──
    # Format: campaign:customer:mailtype:sender
    if "Feedback-ID" in msg:
        del msg["Feedback-ID"]
    msg["Feedback-ID"] = f"{campaign_id}:murphy:{('txn' if is_transactional else 'bulk')}:murphysystems"
    
    # ── Auto-Submitted — RFC 3834 ──
    # Declares this is machine-generated, suppresses vacation responders
    if "Auto-Submitted" not in msg:
        msg["Auto-Submitted"] = "auto-generated"
    
    # ── Precedence — declares bulk vs transactional ──
    if not is_transactional and "Precedence" not in msg:
        msg["Precedence"] = "bulk"
    
    # ── X-Entity-Ref-ID — helps Gmail tie related messages ──
    if "X-Entity-Ref-ID" not in msg:
        msg["X-Entity-Ref-ID"] = make_msgid(domain="murphy.systems").strip("<>").split("@")[0]
    
    # ── Content-Language — locale signal ──
    if "Content-Language" not in msg:
        msg["Content-Language"] = "en-US"
    
    # ── X-Mailer — identifies sending system ──
    if "X-Mailer" not in msg:
        msg["X-Mailer"] = "Murphy/1.0 (murphy.systems)"
    
    # ── Reply-To — make sure replies go somewhere real ──
    if "Reply-To" not in msg:
        msg["Reply-To"] = from_addr
    
    return msg
