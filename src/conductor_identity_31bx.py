"""Ship 31bx.MURPHY_PRIME — chronological canonical name + tenant-chosen alias.

IDENTITY MODEL (two layers)

  1. CANONICAL (system-side, immutable)
     - cpost@murphy.systems → "Murphy Prime"
     - every other tenant   → "Murphy <N>" where N is chronological rank
       (2 = second tenant ever created, 3 = third, etc.)
     - Used in: audit logs, founder views, internal swarm coordination,
       cross-tenant analytics. NEVER changes.

  2. DISPLAY ALIAS (tenant-chosen, mutable)
     - Tenant sets via "What would you like to call me?"
     - Used in: dashboard greeting, outbound email From: name, chat
       signatures — everywhere the TENANT sees.
     - If unset, display falls back to the canonical name.

The display alias is the `=value` — both names resolve to the same
identity in dispatch, so "Atlas, draft a reply" and "Murphy 7, draft
a reply" hit the same conductor.

STORAGE (tenants.config JSON)
  conductor_rank        int       — assigned ONCE at first read, immutable
  conductor_alias       str|null  — tenant's chosen display name
  conductor_named_at    ISO ts    — when alias was set

THE FOUNDER
  tenant_6bd7bac3be72291d (cpost) → canonical "Murphy Prime", alias locked.
"""
from __future__ import annotations
import json, sqlite3, logging, re
from datetime import datetime, timezone
from typing import Optional, Dict
from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
DB = "/var/lib/murphy-production/tenants.db"
FOUNDER_TENANT = "tenant_6bd7bac3be72291d"
FOUNDER_CANONICAL = "Murphy Prime"


def _conn():
    c = sqlite3.connect(DB, timeout=10.0)
    c.row_factory = sqlite3.Row
    return c


def _all_active_tenants_ordered():
    """Return all active tenant_ids ordered by created_at ascending."""
    with _conn() as c:
        rows = c.execute(
            "SELECT tenant_id, created_at, config FROM tenants "
            "WHERE state='active' ORDER BY created_at ASC"
        ).fetchall()
    return rows


def _assign_rank_if_missing(tenant_id: str) -> Optional[int]:
    """Assign conductor_rank to a tenant if not already set. Idempotent."""
    if tenant_id == FOUNDER_TENANT:
        return 1  # founder is always rank 1 (Prime)
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT config FROM tenants WHERE tenant_id=?", (tenant_id,)
            ).fetchone()
            if not row:
                return None
            cfg = json.loads(row["config"] or "{}")
            if "conductor_rank" in cfg:
                return cfg["conductor_rank"]
            # find rank: chronological order among non-founder tenants
            ordered = _all_active_tenants_ordered()
            non_founder_seen = 0
            target_rank = None
            for r in ordered:
                if r["tenant_id"] == FOUNDER_TENANT:
                    continue
                non_founder_seen += 1
                if r["tenant_id"] == tenant_id:
                    # +1 because Murphy Prime takes rank 1, so chronological
                    # rank 2 = first non-founder, rank 3 = second, etc.
                    target_rank = non_founder_seen + 1
                    break
            if target_rank is None:
                return None
            cfg["conductor_rank"] = target_rank
            cfg["conductor_rank_assigned_at"] = datetime.now(timezone.utc).isoformat()
            c.execute(
                "UPDATE tenants SET config=?, updated_at=? WHERE tenant_id=?",
                (json.dumps(cfg), datetime.now(timezone.utc).isoformat(), tenant_id),
            )
            c.commit()
        log.info(f"[murphy_prime] assigned rank {target_rank} to {tenant_id}")
        return target_rank
    except Exception as e:
        log.warning(f"[murphy_prime] rank assign failed for {tenant_id}: {e}")
        return None


def get_canonical_name(tenant_id: str) -> Optional[str]:
    """Return 'Murphy Prime' or 'Murphy N'. Auto-assigns rank if missing."""
    if tenant_id == FOUNDER_TENANT:
        return FOUNDER_CANONICAL
    rank = _assign_rank_if_missing(tenant_id)
    if rank is None:
        return None
    return f"Murphy {rank}"


def get_alias(tenant_id: str) -> Optional[str]:
    """Return tenant-chosen alias if set, else None. Founder = locked Prime."""
    if tenant_id == FOUNDER_TENANT:
        return FOUNDER_CANONICAL
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT config FROM tenants WHERE tenant_id=?", (tenant_id,)
            ).fetchone()
            if not row:
                return None
            cfg = json.loads(row["config"] or "{}")
            return cfg.get("conductor_alias") or None
    except Exception as e:
        log.warning(f"[murphy_prime] alias read failed for {tenant_id}: {e}")
        return None


def get_display_name(tenant_id: str) -> str:
    """The name shown to the tenant. Alias if set, else canonical."""
    alias = get_alias(tenant_id)
    if alias:
        return alias
    canonical = get_canonical_name(tenant_id)
    return canonical or "your conductor"


def set_alias(tenant_id: str, alias: str) -> Dict:
    """Validate and persist the tenant's chosen display alias."""
    if tenant_id == FOUNDER_TENANT:
        return {"ok": False, "error": "Murphy Prime's name is fixed."}

    alias = (alias or "").strip()
    if not alias:
        return {"ok": False, "error": "Please enter a name."}
    if len(alias) > 40:
        return {"ok": False, "error": "Name must be 40 characters or fewer."}
    if not re.match(r"^[A-Za-z0-9 \-'.]+$", alias):
        return {"ok": False, "error":
                "Name can only contain letters, digits, spaces, hyphens, apostrophes, and periods."}

    try:
        with _conn() as c:
            row = c.execute(
                "SELECT config FROM tenants WHERE tenant_id=?", (tenant_id,)
            ).fetchone()
            if not row:
                return {"ok": False, "error": "Tenant not found."}
            cfg = json.loads(row["config"] or "{}")
            cfg["conductor_alias"] = alias
            cfg["conductor_named_at"] = datetime.now(timezone.utc).isoformat()
            c.execute(
                "UPDATE tenants SET config=?, updated_at=? WHERE tenant_id=?",
                (json.dumps(cfg), datetime.now(timezone.utc).isoformat(), tenant_id),
            )
            c.commit()
        log.info(f"[murphy_prime] tenant {tenant_id} chose alias '{alias}'")
        return {"ok": True, "alias": alias, "canonical": get_canonical_name(tenant_id)}
    except Exception as e:
        log.error(f"[murphy_prime] alias write failed for {tenant_id}: {e}")
        return {"ok": False, "error": str(e)}


def identity_for(tenant_id: str) -> Dict:
    """Full identity object for a tenant — what the dashboard needs."""
    canonical = get_canonical_name(tenant_id)
    alias = get_alias(tenant_id)
    display = alias or canonical or "your conductor"
    return {
        "tenant_id":     tenant_id,
        "canonical":     canonical,
        "alias":         alias,
        "display":       display,
        "is_founder":    tenant_id == FOUNDER_TENANT,
        "alias_locked":  tenant_id == FOUNDER_TENANT,
        "alias_set":     alias is not None,
    }


# ─── Banner HTML (rendered with display name and current alias state) ──

_BANNER_TEMPLATE = """<!-- Ship 31bx CONDUCTOR_NAME -->
<div id="conductor-name-banner" style="background:linear-gradient(135deg,#0e1410,#1a2733);border:1px solid #00d4aa;border-radius:8px;padding:18px 22px;margin:18px;font-family:Inter,system-ui">
  <div style="font-size:13px;color:#00d4aa;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Your conductor</div>
  <div id="conductor-greeting-row" style="display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap">
    <div>
      <div style="font-size:18px;color:#e6edf3;font-weight:600" id="conductor-display-name">__DISPLAY__</div>
      <div style="font-size:12px;color:#8b949e;margin-top:2px" id="conductor-subline">__SUBLINE__</div>
    </div>
    <button id="conductor-rename-btn" onclick="conductorOpenRename31bx()" style="background:transparent;color:#00d4aa;border:1px solid #00d4aa;padding:8px 14px;border-radius:6px;font-weight:500;cursor:pointer;font-family:Inter,system-ui;font-size:13px" __RENAME_HIDDEN__>__RENAME_LABEL__</button>
  </div>
  <div id="conductor-rename-row" style="display:__INITIAL_FORM__;margin-top:14px;padding-top:14px;border-top:1px solid #21262d">
    <div style="font-size:13px;color:#c9d1d9;margin-bottom:10px">__PROMPT_TEXT__</div>
    <div style="display:flex;gap:8px;max-width:480px">
      <input id="conductor-name-input" type="text" maxlength="40" placeholder="e.g., Atlas, Sage, or whatever feels right"
             value="__ALIAS_VALUE__"
             style="flex:1;background:#0d1117;border:1px solid #21262d;color:#e6edf3;padding:10px 14px;border-radius:6px;font-family:Inter,system-ui;font-size:14px"
             onkeydown="if(event.key==='Enter') conductorSave31bx()">
      <button onclick="conductorSave31bx()" style="background:#00d4aa;color:#0d1117;border:none;padding:10px 18px;border-radius:6px;font-weight:600;cursor:pointer;font-family:Inter,system-ui">Save</button>
      <button onclick="conductorCancelRename31bx()" id="conductor-cancel-btn" style="background:transparent;color:#8b949e;border:1px solid #21262d;padding:10px 14px;border-radius:6px;cursor:pointer;font-family:Inter,system-ui" __CANCEL_HIDDEN__>Cancel</button>
    </div>
    <div id="conductor-name-error" style="color:#ff6b6b;font-size:12px;margin-top:8px;min-height:16px"></div>
  </div>
</div>
<script>
function conductorOpenRename31bx(){
  document.getElementById("conductor-rename-row").style.display="block";
  document.getElementById("conductor-rename-btn").style.display="none";
  document.getElementById("conductor-name-input").focus();
}
function conductorCancelRename31bx(){
  document.getElementById("conductor-rename-row").style.display="none";
  document.getElementById("conductor-rename-btn").style.display="inline-block";
  document.getElementById("conductor-name-error").textContent="";
}
async function conductorSave31bx(){
  var inp=document.getElementById("conductor-name-input");
  var err=document.getElementById("conductor-name-error");
  err.textContent="";
  var name=(inp.value||"").trim();
  if(!name){err.textContent="Please enter a name.";return;}
  try{
    var r=await fetch("/api/conductor/name",{method:"POST",credentials:"include",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({name:name})});
    var d=await r.json();
    if(!d.ok){err.textContent=d.error||"Failed to save.";return;}
    document.getElementById("conductor-display-name").textContent=d.alias;
    document.getElementById("conductor-subline").textContent="System ID: "+d.canonical+" · you can rename anytime";
    document.getElementById("conductor-rename-row").style.display="none";
    var btn=document.getElementById("conductor-rename-btn");
    btn.style.display="inline-block";
    btn.textContent="Rename";
    var cancel=document.getElementById("conductor-cancel-btn");
    if(cancel) cancel.style.display="inline-block";
  }catch(e){err.textContent=e.message;}
}
</script>
"""


def banner_html_for(tenant_id: str) -> str:
    """Server-render the banner for this tenant's current state."""
    ident = identity_for(tenant_id)
    if ident["is_founder"]:
        # Founder: locked display, no rename
        display = ident["display"]
        subline = "System ID: Murphy Prime · brand-locked"
        rename_hidden = 'style="display:none"'
        rename_label = "Rename"
        initial_form = "none"
        prompt_text = ""
        alias_value = ""
        cancel_hidden = ""
    elif ident["alias_set"]:
        # Has chosen an alias — show it, offer rename
        display = ident["display"]
        subline = f"System ID: {ident['canonical']} · you can rename anytime"
        rename_hidden = ""
        rename_label = "Rename"
        initial_form = "none"
        prompt_text = "What would you like to call me?"
        alias_value = ident["alias"] or ""
        cancel_hidden = ""
    else:
        # No alias yet — show canonical, OPEN the form
        display = ident["canonical"] or "your conductor"
        subline = "I don't have a name yet — what would you like to call me?"
        rename_hidden = 'style="display:none"'
        rename_label = "Name me"
        initial_form = "block"
        prompt_text = "Pick any name. You can change it anytime."
        alias_value = ""
        cancel_hidden = 'style="display:none"'

    html = _BANNER_TEMPLATE
    repl = {
        "__DISPLAY__": display,
        "__SUBLINE__": subline,
        "__RENAME_HIDDEN__": rename_hidden,
        "__RENAME_LABEL__": rename_label,
        "__INITIAL_FORM__": initial_form,
        "__PROMPT_TEXT__": prompt_text,
        "__ALIAS_VALUE__": alias_value,
        "__CANCEL_HIDDEN__": cancel_hidden,
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    return html


def inject_banner(html: str, tenant_id: str) -> str:
    """Splice the banner after <body> in a rendered dashboard."""
    if "conductor-name-banner" in html:
        return html
    banner = banner_html_for(tenant_id)
    import re as _re
    m = _re.search(r"<body[^>]*>", html)
    if not m:
        return banner + html
    return html[:m.end()] + banner + html[m.end():]


# ─── HTTP routes ──────────────────────────────────────────────────

def register_routes(app):
    def _session(request: Request):
        try:
            sid = request.cookies.get("murphy_session", "")
            if not sid: return None
            import sys as _sys
            if "/opt/Murphy-System" not in _sys.path:
                _sys.path.insert(0, "/opt/Murphy-System")
            from src import ship31ah_signup as _s
            sess = _s.lookup_session(sid)
            return sess if sess else None
        except Exception:
            return None

    @app.get("/api/conductor/name", include_in_schema=False)
    async def _get(request: Request):
        sess = _session(request)
        if not sess:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Login required"})
        ident = identity_for(sess["tenant_id"])
        return {"ok": True, **ident}

    @app.post("/api/conductor/name", include_in_schema=False)
    async def _set(request: Request):
        sess = _session(request)
        if not sess:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Login required"})
        try:
            body = await request.json()
            name = body.get("name", "")
        except Exception:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid JSON"})
        result = set_alias(sess["tenant_id"], name)
        return JSONResponse(status_code=200 if result["ok"] else 400, content=result)
