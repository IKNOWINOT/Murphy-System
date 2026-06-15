"""Ship 31bx.CONDUCTOR_NAME — every tenant names their own conductor.

PRINCIPLE
  Names matter. The tenant — not Murphy, not auto-rotation — picks
  what their AI agent is called. If they don't pick, the conductor
  remains unnamed and asks them on first interaction.

STORAGE
  tenants.config (JSON) — adds:
    "conductor_name":     str | null     # what they chose
    "conductor_named_at": ISO timestamp  # when they picked (null = pending)

UI SURFACES
  - Signup form: optional "What would you like to call your conductor?" field
  - Tenant dashboard header: greets as "Hi from <name>" or prompts
  - Outbound email From: <Conductor Name> <tenant_slug@murphy.systems>
  - Chat: conductor signs replies with their name

FALLBACK CHAIN (when no name set):
  1. Show prompt "I don't have a name yet — what should you call me?"
  2. Until they answer, the system uses literally "your conductor" (lowercase)
     — NEVER auto-generates a name without asking.

FOUNDER (cpost@murphy.systems): hardcoded conductor name = "Murphy"
"""
from __future__ import annotations
import json, sqlite3, logging, re
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from pathlib import Path

log = logging.getLogger(__name__)
DB = "/var/lib/murphy-production/tenants.db"
FOUNDER_TENANTS = {"tenant_6bd7bac3be72291d"}  # cpost's workspace
FOUNDER_NAME = "Murphy"


def _conn():
    c = sqlite3.connect(DB, timeout=10.0)
    c.row_factory = sqlite3.Row
    return c


def get_conductor_name(tenant_id: str) -> Optional[str]:
    """Returns the conductor name if set, else None. Founder always = 'Murphy'."""
    if tenant_id in FOUNDER_TENANTS:
        return FOUNDER_NAME
    try:
        with _conn() as c:
            row = c.execute("SELECT config FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
            if not row: return None
            cfg = json.loads(row["config"] or "{}")
            return cfg.get("conductor_name") or None
    except Exception as e:
        log.warning(f"[conductor_identity] read failed for {tenant_id}: {e}")
        return None


def set_conductor_name(tenant_id: str, name: str) -> dict:
    """Validate + persist. Returns {ok: bool, name?: str, error?: str}."""
    if tenant_id in FOUNDER_TENANTS:
        return {"ok": False, "error": "Founder conductor name is fixed to 'Murphy'"}

    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "Name cannot be empty"}
    if len(name) > 40:
        return {"ok": False, "error": "Name max 40 characters"}
    # only letters, digits, spaces, dashes, apostrophes — no @<>{}
    if not re.match(r"^[A-Za-z0-9 \-'.]+$", name):
        return {"ok": False, "error": "Name can only contain letters, digits, spaces, hyphens, apostrophes, and periods"}

    try:
        with _conn() as c:
            row = c.execute("SELECT config FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "Tenant not found"}
            cfg = json.loads(row["config"] or "{}")
            cfg["conductor_name"] = name
            cfg["conductor_named_at"] = datetime.now(timezone.utc).isoformat()
            c.execute("UPDATE tenants SET config=?, updated_at=? WHERE tenant_id=?",
                      (json.dumps(cfg), datetime.now(timezone.utc).isoformat(), tenant_id))
            c.commit()
        log.info(f"[conductor_identity] tenant {tenant_id} named conductor '{name}'")
        return {"ok": True, "name": name}
    except Exception as e:
        log.error(f"[conductor_identity] write failed for {tenant_id}: {e}")
        return {"ok": False, "error": str(e)}


def conductor_addresses_owner(tenant_id: str, fallback: str = "your conductor") -> str:
    """How the conductor refers to ITSELF in 3rd person to the owner.
    e.g. 'Atlas thinks…' or 'your conductor thinks…' if unnamed."""
    n = get_conductor_name(tenant_id)
    return n if n else fallback


def conductor_signs(tenant_id: str, fallback: str = "Your conductor") -> str:
    """How the conductor signs an email/note. Title-cased fallback."""
    n = get_conductor_name(tenant_id)
    return n if n else fallback


def needs_naming(tenant_id: str) -> bool:
    """True if conductor is unnamed AND this isn't the founder tenant."""
    if tenant_id in FOUNDER_TENANTS:
        return False
    return get_conductor_name(tenant_id) is None


def register_routes(app):
    def _tenant_from_request(request: Request) -> Optional[str]:
        try:
            sid = request.cookies.get("murphy_session", "")
            if not sid: return None
            import sys as _sys
            if "/opt/Murphy-System" not in _sys.path:
                _sys.path.insert(0, "/opt/Murphy-System")
            from src import ship31ah_signup as _s
            sess = _s.lookup_session(sid)
            return sess.get("tenant_id") if sess else None
        except Exception:
            return None

    @app.get("/api/conductor/name", include_in_schema=False)
    async def _get(request: Request):
        tid = _tenant_from_request(request)
        if not tid:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Login required"})
        n = get_conductor_name(tid)
        return {"ok": True, "tenant_id": tid, "conductor_name": n, "needs_naming": needs_naming(tid)}

    @app.post("/api/conductor/name", include_in_schema=False)
    async def _set(request: Request):
        tid = _tenant_from_request(request)
        if not tid:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Login required"})
        try:
            body = await request.json()
            name = body.get("name", "")
        except Exception:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON"})
        result = set_conductor_name(tid, name)
        return JSONResponse(status_code=200 if result["ok"] else 400, content=result)


# Ship 31bx — HTML banner served on the tenant dashboard
_BANNER_HTML = """<!-- Ship 31bx CONDUCTOR_NAME -->
<div id="conductor-name-prompt" style="display:none;background:linear-gradient(135deg,#0e1410,#1a2733);border:1px solid #00d4aa;border-radius:8px;padding:18px 22px;margin:18px;font-family:Inter,system-ui">
  <div style="font-size:13px;color:#00d4aa;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Welcome</div>
  <div style="font-size:17px;color:#e6edf3;margin-bottom:6px">I don't have a name yet — what would you like to call me?</div>
  <div style="font-size:13px;color:#8b949e;margin-bottom:14px">I'm your conductor. I'll read your emails, draft replies, and only ask for help when I need it. Pick whatever feels right. You can change it anytime.</div>
  <div style="display:flex;gap:8px;max-width:420px">
    <input id="conductor-name-input" type="text" maxlength="40" placeholder="e.g., Atlas, Sage, or whatever feels right" style="flex:1;background:#0d1117;border:1px solid #21262d;color:#e6edf3;padding:10px 14px;border-radius:6px;font-family:Inter,system-ui;font-size:14px" onkeydown="if(event.key==='Enter') saveConductorName31bx()">
    <button onclick="saveConductorName31bx()" style="background:#00d4aa;color:#0d1117;border:none;padding:10px 18px;border-radius:6px;font-weight:600;cursor:pointer;font-family:Inter,system-ui">Save</button>
  </div>
  <div id="conductor-name-error" style="color:#ff6b6b;font-size:12px;margin-top:8px;min-height:16px"></div>
</div>
<div id="conductor-greeting" style="display:none;background:#0e1410;border-left:3px solid #00d4aa;padding:14px 20px;margin:18px;font-family:Inter,system-ui;font-size:14px;color:#c9d1d9">
  <span id="conductor-greeting-text"></span>
</div>
<script>
(async function(){try{const r=await fetch("/api/conductor/name",{credentials:"include"});if(!r.ok)return;const d=await r.json();if(!d.ok)return;if(d.needs_naming){document.getElementById("conductor-name-prompt").style.display="block";}else if(d.conductor_name){document.getElementById("conductor-greeting").style.display="block";document.getElementById("conductor-greeting-text").textContent="Hi from "+d.conductor_name+". I am watching your inbox.";}}catch(e){}})();
async function saveConductorName31bx(){const inp=document.getElementById("conductor-name-input");const err=document.getElementById("conductor-name-error");err.textContent="";const name=(inp.value||"").trim();if(!name){err.textContent="Please enter a name";return;}try{const r=await fetch("/api/conductor/name",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({name})});const d=await r.json();if(!d.ok){err.textContent=d.error||"Failed to save";return;}document.getElementById("conductor-name-prompt").style.display="none";document.getElementById("conductor-greeting").style.display="block";document.getElementById("conductor-greeting-text").textContent="Hi from "+d.name+". I am watching your inbox.";}catch(e){err.textContent=e.message;}}
</script>
"""


def inject_banner(html: str) -> str:
    """Splice the conductor naming prompt/greeting after <body>."""
    if "conductor-name-prompt" in html:
        return html
    import re as _re
    m = _re.search(r"<body[^>]*>", html)
    if not m:
        return _BANNER_HTML + html
    return html[:m.end()] + _BANNER_HTML + html[m.end():]
