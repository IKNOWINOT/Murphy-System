#!/opt/Murphy-System/venv/bin/python3
"""R384 HITL Service — runs on port 8083.

Endpoints:
  GET  /health
  GET  /api/hitl-v2/queue
  POST /api/hitl-v2/mail/{queue_id}/approve
  POST /api/hitl-v2/mail/{queue_id}/reject
  GET  /api/hitl-v2/mail/{queue_id}/inspect
  POST /api/hitl-v2/form-intake/{id}/approve
  POST /api/hitl-v2/form-intake/{id}/reject
"""
import sys, importlib.util
sys.path.insert(0, "/usr/local/bin")

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

spec = importlib.util.spec_from_file_location("r384", "/usr/local/bin/r384_hitl_router.py")
r384 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r384)

app = FastAPI(title="Murphy HITL", version="R384")


def _check_session_cookie_31bu(request: Request):
    """Ship 31bu — accept a valid founder session cookie as auth.
    Returns True if cookie names a founder/owner/platform_admin session.
    """
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
        data = u.get("data", {}) or {}
        role = (data.get("role") or "").lower()
        is_founder = bool(data.get("is_founder"))
        email = (sess.get("email") or "").lower()
        FOUNDER_ALLOWLIST = {"cpost@murphy.systems"}
        return (role in ("owner","founder","platform_admin","platform_staff")
                or is_founder
                or email in FOUNDER_ALLOWLIST)
    except Exception:
        return False


def _check_key(request: Request):
    # Ship 31bu — accept EITHER founder API key OR founder session cookie
    key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    ok, code = r384.check_founder_key(key)
    if ok:
        return None
    if _check_session_cookie_31bu(request):
        return None
    return JSONResponse(status_code=401,
        content={"ok": False, "code": code or "E_AUTH_0034",
                 "reason": "Founder key or founder session required"})


class ApproveBody(BaseModel):
    edits: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class RejectBody(BaseModel):
    reason: Optional[str] = None


@app.get("/health")
async def health():
    return {"ok": True, "service": "r384_hitl", "version": "R384"}


@app.get("/api/hitl-v2/queue")
async def queue(request: Request):
    err = _check_key(request)
    if err: return err
    return r384.get_queue()


@app.post("/api/hitl-v2/mail/{queue_id}/approve")
async def mail_approve(queue_id: str, body: ApproveBody, request: Request):
    err = _check_key(request)
    if err: return err
    return r384.approve_mail(queue_id, body.edits)


@app.post("/api/hitl-v2/mail/{queue_id}/reject")
async def mail_reject(queue_id: str, body: RejectBody, request: Request):
    err = _check_key(request)
    if err: return err
    return r384.reject_mail(queue_id, body.reason)


@app.get("/api/hitl-v2/mail/{queue_id}/inspect")
async def mail_inspect(queue_id: str, request: Request):
    err = _check_key(request)
    if err: return err
    return r384.inspect_mail(queue_id)


@app.post("/api/hitl-v2/form-intake/{item_id}/approve")
async def form_approve(item_id: str, body: ApproveBody, request: Request):
    err = _check_key(request)
    if err: return err
    return r384.approve_form_intake(item_id, body.reason)


@app.post("/api/hitl-v2/form-intake/{item_id}/reject")
async def form_reject(item_id: str, body: RejectBody, request: Request):
    err = _check_key(request)
    if err: return err
    return r384.reject_form_intake(item_id, body.reason)
