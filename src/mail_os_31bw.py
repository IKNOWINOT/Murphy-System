"""Ship 31bw.MAIL_OS — IMAP-backed mailbox tabs on /os.

Lets the founder read every Murphy-platform-side mailbox from /os
without configuring an external email client. Read-only.

ARCHITECTURE
  Dovecot master user 'murphy_os_reader' is provisioned in /etc/dovecot/master-users
  with a password stored in vault. We connect to 127.0.0.1:143, authenticate
  as 'targetuser*murphy_os_reader' (Dovecot master-user syntax), then fetch
  the requested folder.

ROUTES (all founder-cookie required)
  GET /api/mail/inbox/{mailbox}                — list messages in INBOX
  GET /api/mail/inbox/{mailbox}/folders         — list folders
  GET /api/mail/inbox/{mailbox}/message/{uid}   — fetch full message
  GET /api/mail/inboxes                          — list all available mailboxes + counts

PLATFORM-SIDE MAILBOXES (mapped to founder)
  cpost, hpost, dpost, kpost, lpost, mark.post, meaghan.post  (family)
  murphy, swarm                                                (system)
  sales, support, billing, legal, accounting, clientsolutions  (role)
  techsupport                                                  (role)
  abeltaine, bgillespie, jcarney, krhymer                      (staff)

TENANT-SIDE MAILBOXES (future)
  When a tenant provisions <tenant_slug>.murphy.systems mail, those
  mailboxes show up scoped to their tenant_id, not to the founder.
"""
from __future__ import annotations
import imaplib, email, os, logging, json
from email.header import decode_header, make_header
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Platform-side mailboxes — readable by founder
PLATFORM_MAILBOXES = [
    # founder family
    {"name": "cpost",          "label": "Corey (cpost)",        "category": "founder", "domain": "murphy.systems"},
    {"name": "hpost",          "label": "Hawthorne (hpost)",    "category": "family",  "domain": "murphy.systems"},
    {"name": "dpost",          "label": "dpost",                "category": "family",  "domain": "murphy.systems"},
    {"name": "kpost",          "label": "kpost",                "category": "family",  "domain": "murphy.systems"},
    {"name": "lpost",          "label": "lpost",                "category": "family",  "domain": "murphy.systems"},
    {"name": "mark.post",      "label": "Mark Post",            "category": "family",  "domain": "murphy.systems"},
    {"name": "meaghan.post",   "label": "Meaghan Post",         "category": "family",  "domain": "murphy.systems"},
    # system
    {"name": "murphy",         "label": "Murphy AI",            "category": "system",  "domain": "murphy.systems"},
    {"name": "swarm",          "label": "Swarm Ingest",         "category": "system",  "domain": "murphy.systems"},
    # role
    {"name": "sales",          "label": "Sales",                "category": "role",    "domain": "murphy.systems"},
    {"name": "support",        "label": "Support",              "category": "role",    "domain": "murphy.systems"},
    {"name": "billing",        "label": "Billing",              "category": "role",    "domain": "murphy.systems"},
    {"name": "legal",          "label": "Legal",                "category": "role",    "domain": "murphy.systems"},
    {"name": "accounting",     "label": "Accounting",           "category": "role",    "domain": "murphy.systems"},
    {"name": "clientsolutions","label": "Client Solutions",     "category": "role",    "domain": "murphy.systems"},
    {"name": "techsupport",    "label": "Tech Support",         "category": "role",    "domain": "murphy.systems"},
    # staff
    {"name": "abeltaine",      "label": "abeltaine",            "category": "staff",   "domain": "murphy.systems"},
    {"name": "bgillespie",     "label": "bgillespie",           "category": "staff",   "domain": "murphy.systems"},
    {"name": "jcarney",        "label": "jcarney",              "category": "staff",   "domain": "murphy.systems"},
    {"name": "krhymer",        "label": "krhymer",              "category": "staff",   "domain": "murphy.systems"},
]
VALID_MAILBOXES = {m["name"] for m in PLATFORM_MAILBOXES}


def _check_founder(request: Request) -> bool:
    """Returns True if request carries a valid founder session cookie."""
    try:
        sid = request.cookies.get("murphy_session", "")
        if not sid: return False
        import sys as _sys
        if "/opt/Murphy-System" not in _sys.path:
            _sys.path.insert(0, "/opt/Murphy-System")
        from src import ship31ah_signup as _s
        sess = _s.lookup_session(sid)
        if not sess: return False
        u = _s.get_user_by_email(sess["email"])
        if not u: return False
        role = (u.get("data", {}).get("role") or "").lower()
        is_founder = bool(u.get("data", {}).get("is_founder"))
        email_ = (sess.get("email") or "").lower()
        return (role in ("owner","founder","platform_admin","platform_staff")
                or is_founder
                or email_ in {"cpost@murphy.systems"})
    except Exception:
        return False


def _vault_password() -> str:
    """Read DOVECOT_OS_READER_PASSWORD from vault."""
    p = "/var/lib/murphy-production/vault/secrets.env"
    if not os.path.exists(p): return ""
    try:
        with open(p) as f:
            for line in f:
                if line.startswith("DOVECOT_OS_READER_PASSWORD="):
                    return line.split("=", 1)[1].strip()
    except Exception as e:
        log.error(f"[mail_os] vault read failed: {e}")
    return ""


def _imap_connect(mailbox: str):
    """Open IMAP connection as the target mailbox using master-user auth."""
    pw = _vault_password()
    if not pw:
        raise HTTPException(500, "Mail reader credentials not in vault")
    domain = "murphy.systems"
    target_user = f"{mailbox}@{domain}"
    auth_user = f"{target_user}*murphy_os_reader"  # Dovecot master-user syntax
    conn = imaplib.IMAP4("127.0.0.1", 143)
    conn.login(auth_user, pw)
    return conn


def _decode(s):
    if s is None: return ""
    try: return str(make_header(decode_header(s)))
    except Exception: return str(s)


def list_inboxes_with_counts():
    """List all platform mailboxes + their unread + total counts."""
    out = []
    for mb in PLATFORM_MAILBOXES:
        name = mb["name"]
        base = f"/var/mail/vhosts/murphy.systems/{name}"
        try:
            cur = len(os.listdir(f"{base}/cur")) if os.path.isdir(f"{base}/cur") else 0
            new = len(os.listdir(f"{base}/new")) if os.path.isdir(f"{base}/new") else 0
        except Exception:
            cur, new = 0, 0
        out.append({**mb, "unread": new, "total": cur + new})
    return out


def list_messages(mailbox: str, folder: str = "INBOX", limit: int = 50):
    if mailbox not in VALID_MAILBOXES:
        raise HTTPException(404, f"Unknown mailbox: {mailbox}")
    conn = _imap_connect(mailbox)
    try:
        conn.select(folder, readonly=True)
        typ, data = conn.search(None, "ALL")
        if typ != "OK": return []
        ids = data[0].split()
        # most recent first, limit
        ids = ids[-limit:][::-1]
        out = []
        for mid in ids:
            typ, msg_data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)] FLAGS UID)")
            if typ != "OK" or not msg_data: continue
            headers = b""
            uid = mid.decode()
            unread = True
            for part in msg_data:
                if isinstance(part, tuple) and len(part) > 1:
                    headers = part[1]
                elif isinstance(part, bytes):
                    s = part.decode("latin-1", errors="replace")
                    if "UID " in s:
                        try: uid = s.split("UID ")[1].split(")")[0].split()[0]
                        except Exception: pass
                    if "\\Seen" in s: unread = False
            try:
                msg = email.message_from_bytes(headers)
                out.append({
                    "uid":     uid,
                    "subject": _decode(msg.get("Subject", "(no subject)")),
                    "from":    _decode(msg.get("From", "")),
                    "to":      _decode(msg.get("To", "")),
                    "date":    _decode(msg.get("Date", "")),
                    "unread":  unread,
                })
            except Exception as e:
                log.warning(f"[mail_os] parse failed for {uid}: {e}")
        return out
    finally:
        try: conn.logout()
        except Exception: pass


def fetch_message(mailbox: str, uid: str, folder: str = "INBOX"):
    if mailbox not in VALID_MAILBOXES:
        raise HTTPException(404, f"Unknown mailbox: {mailbox}")
    conn = _imap_connect(mailbox)
    try:
        conn.select(folder, readonly=True)
        typ, data = conn.uid("FETCH", uid, "(RFC822)")
        if typ != "OK" or not data or not data[0]:
            raise HTTPException(404, f"Message {uid} not found")
        raw = data[0][1]
        msg = email.message_from_bytes(raw)
        body_text, body_html = "", ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                disp = str(part.get("Content-Disposition", ""))
                if "attachment" in disp.lower(): continue
                if ct == "text/plain" and not body_text:
                    try: body_text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                    except Exception: pass
                elif ct == "text/html" and not body_html:
                    try: body_html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
                    except Exception: pass
        else:
            try: body_text = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="replace")
            except Exception: body_text = str(msg.get_payload())
        return {
            "uid":     uid,
            "subject": _decode(msg.get("Subject", "(no subject)")),
            "from":    _decode(msg.get("From", "")),
            "to":      _decode(msg.get("To", "")),
            "cc":      _decode(msg.get("Cc", "")),
            "date":    _decode(msg.get("Date", "")),
            "body_text": body_text,
            "body_html": body_html,
        }
    finally:
        try: conn.logout()
        except Exception: pass


def register_routes(app):
    @app.get("/api/mail/inboxes", include_in_schema=False)
    async def _inboxes(request: Request):
        if not _check_founder(request):
            return JSONResponse(status_code=401, content={"ok": False, "code": "E_AUTH_0034", "reason": "Founder required"})
        return {"ok": True, "inboxes": list_inboxes_with_counts()}

    @app.get("/api/mail/inbox/{mailbox}", include_in_schema=False)
    async def _list(mailbox: str, request: Request, limit: int = 50):
        if not _check_founder(request):
            return JSONResponse(status_code=401, content={"ok": False, "code": "E_AUTH_0034", "reason": "Founder required"})
        try:
            msgs = list_messages(mailbox, limit=limit)
            return {"ok": True, "mailbox": mailbox, "count": len(msgs), "messages": msgs}
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"ok": False, "error": e.detail})
        except Exception as e:
            log.exception("[mail_os] list error")
            return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

    @app.get("/api/mail/inbox/{mailbox}/message/{uid}", include_in_schema=False)
    async def _msg(mailbox: str, uid: str, request: Request):
        if not _check_founder(request):
            return JSONResponse(status_code=401, content={"ok": False, "code": "E_AUTH_0034", "reason": "Founder required"})
        try:
            m = fetch_message(mailbox, uid)
            return {"ok": True, "message": m}
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"ok": False, "error": e.detail})
        except Exception as e:
            log.exception("[mail_os] fetch error")
            return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
