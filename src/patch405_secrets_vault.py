"""
PATCH-405 — Murphy Secrets Vault
================================

A scoped, audit-logged, encrypted-at-rest secret-request flow.
Mirrors the INONI ClockWork UX pattern: clear write/read/destructive
classification, three trust scopes per grant, hash-chained audit.

Approver matrix (graduated):
  🔴 destructive  -> founder only
  🟡 write        -> founder + kin
  🟢 read         -> founder + kin

Trust scopes per grant:
  - "just_this_time"        -> one-shot, value purged after use
  - "this_conversation"     -> session-scoped, expires on session end
  - "permanent"             -> encrypted at rest, separate flow (re-confirm)

Master key:
  /root/.murphy_vault_key (mode 0400 root:root)
  generated at first startup if missing.

Endpoints:
  POST /api/vault/request      -- agent requests a secret
  POST /api/vault/approve      -- human grants/denies a pending request
  POST /api/vault/use          -- consume a granted secret (one-shot scopes purge here)
  GET  /api/vault/pending      -- list pending requests (human UI)
  GET  /api/vault/vault        -- list permanent secrets (names only, never values)
  POST /api/vault/revoke       -- revoke a permanent secret
  GET  /api/vault/audit        -- audit log
  GET  /api/vault/health       -- sanity check
  GET  /vault                  -- HTML approval UI (the INONI-style prompt)
"""
from __future__ import annotations
import os, sys, json, sqlite3, hashlib, time, base64, secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse, HTMLResponse

# ── Crypto (AES-256-GCM via cryptography library) ───────────────────────────
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

# ── Constants ───────────────────────────────────────────────────────────────
DB_PATH         = "/var/lib/murphy-production/murphy_vault.db"
MASTER_KEY_PATH = "/etc/murphy-production/.vault_key"
FOUNDER_EMAIL   = "cpost@murphy.systems"
KIN_EMAILS = {
    "hawthorne.post@murphy.systems", "meaghan.post@murphy.systems",
    "kaylyn.post@murphy.systems", "diarmyd.post@murphy.systems",
    "london.post@murphy.systems", "mark.post@murphy.systems",
    "krhymer@murphy.systems", "john.carney@murphy.systems",
    "brandon.gillespie@murphy.systems", "brittany.gillespie@murphy.systems",
    "amy.beltaine@murphy.systems",
}

RISK_CLASSES = {"read", "write", "destructive"}
RISK_LABELS  = {"read": "🟢 Read", "write": "🟡 Write", "destructive": "🔴 Destructive"}
SCOPE_TYPES  = {"just_this_time", "this_conversation", "permanent"}

# ── Schema ──────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_secrets (
    name              TEXT PRIMARY KEY,
    encrypted_value   BLOB NOT NULL,
    nonce             BLOB NOT NULL,
    description       TEXT,
    granted_to_agents TEXT,         -- JSON array of agent ids
    risk_class        TEXT NOT NULL,
    created_by        TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    last_used_at      TEXT,
    use_count         INTEGER DEFAULT 0,
    revoked_at        TEXT
);

CREATE TABLE IF NOT EXISTS vault_requests (
    id                TEXT PRIMARY KEY,
    secret_name       TEXT NOT NULL,
    requesting_agent  TEXT NOT NULL,
    purpose           TEXT NOT NULL,
    risk_class        TEXT NOT NULL,
    operation_summary TEXT,
    target_resource   TEXT,
    will_do           TEXT,        -- JSON list
    wont_do           TEXT,        -- JSON list
    worst_case        TEXT,
    revoke_url        TEXT,
    session_id        TEXT,
    requested_at      TEXT NOT NULL,
    status            TEXT DEFAULT 'pending',  -- pending|granted|denied|expired|consumed
    granted_scope     TEXT,        -- just_this_time|this_conversation|permanent
    granted_by        TEXT,
    granted_at        TEXT,
    granted_value_b64 TEXT,        -- present only for one-shot/session secrets in memory; null for permanent (lookup vault)
    consumed_at       TEXT,
    denial_reason     TEXT
);

CREATE TABLE IF NOT EXISTS vault_events (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    actor       TEXT,
    detail      TEXT,
    hash_prev   TEXT,
    hash_self   TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vault_evt ON vault_events(created_at);

CREATE TABLE IF NOT EXISTS vault_session_grants (
    session_id    TEXT NOT NULL,
    request_id    TEXT NOT NULL,
    secret_name   TEXT NOT NULL,
    granted_at    TEXT NOT NULL,
    expires_at    TEXT,
    PRIMARY KEY (session_id, secret_name)
);
"""

def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _gid(prefix: str) -> str:
    return f"{prefix}_{hashlib.sha1((str(time.time()) + secrets.token_hex(8)).encode()).hexdigest()[:14]}"

# ── Master key bootstrap ────────────────────────────────────────────────────
def _ensure_master_key() -> bytes:
    if os.path.exists(MASTER_KEY_PATH):
        with open(MASTER_KEY_PATH, "rb") as f:
            key = f.read().strip()
        if len(key) == 32:
            return key
        if len(key) == 44 and key.endswith(b"="):
            try:
                k = base64.b64decode(key)
                if len(k) == 32:
                    return k
            except Exception:
                pass
    # Generate fresh
    key = secrets.token_bytes(32)
    with open(MASTER_KEY_PATH, "wb") as f:
        f.write(key)
    try:
        os.chmod(MASTER_KEY_PATH, 0o440)
        # chown skipped — runtime not root
    except Exception:
        pass
    return key

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    _ensure_master_key()

# ── Encryption helpers ──────────────────────────────────────────────────────
def _encrypt(plaintext: str) -> tuple[bytes, bytes]:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography library not installed")
    key = _ensure_master_key()
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return ct, nonce

def _decrypt(ct: bytes, nonce: bytes) -> str:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography library not installed")
    key = _ensure_master_key()
    aes = AESGCM(key)
    return aes.decrypt(nonce, ct, None).decode("utf-8")

# ── Audit (hash chain) ──────────────────────────────────────────────────────
def _emit_event(event_type: str, actor: Optional[str], detail: Dict[str, Any]) -> str:
    conn = _db()
    row = conn.execute("SELECT hash_self FROM vault_events ORDER BY created_at DESC LIMIT 1").fetchone()
    prev = row["hash_self"] if row else ""
    payload = {"type": event_type, "actor": actor, "detail": detail, "ts": _now()}
    h = hashlib.sha256((prev + json.dumps(payload, sort_keys=True, default=str)).encode()).hexdigest()
    eid = _gid("ev")
    conn.execute("""
        INSERT INTO vault_events (id, event_type, actor, detail, hash_prev, hash_self, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (eid, event_type, actor, json.dumps(detail, default=str), prev, h, _now()))
    conn.commit()
    conn.close()
    return eid

# ── Authorization ───────────────────────────────────────────────────────────
def _can_approve(email: str, risk_class: str) -> tuple[bool, str]:
    email = (email or "").lower().strip()
    if email == FOUNDER_EMAIL:
        return True, "founder"
    if risk_class == "destructive":
        return False, "destructive_requires_founder"
    if email in KIN_EMAILS:
        return True, "kin"
    return False, "not_authorized"

# ── Core flows ──────────────────────────────────────────────────────────────
def create_request(secret_name: str, requesting_agent: str, purpose: str,
                   risk_class: str, operation_summary: str = "",
                   target_resource: str = "", will_do: Optional[List[str]] = None,
                   wont_do: Optional[List[str]] = None, worst_case: str = "",
                   revoke_url: str = "", session_id: Optional[str] = None) -> Dict[str, Any]:
    if risk_class not in RISK_CLASSES:
        return {"ok": False, "error": f"risk_class must be one of {sorted(RISK_CLASSES)}"}

    # If permanent value already exists and agent allowed, just return signal "ready"
    conn = _db()
    existing = conn.execute(
        "SELECT name, granted_to_agents, revoked_at FROM vault_secrets WHERE name=?",
        (secret_name,)).fetchone()

    if existing and not existing["revoked_at"]:
        agents = json.loads(existing["granted_to_agents"] or "[]")
        if requesting_agent in agents:
            conn.close()
            _emit_event("auto_grant", requesting_agent,
                       {"secret": secret_name, "reason": "permanent_grant"})
            return {"ok": True, "auto_granted": True, "secret_name": secret_name,
                   "scope": "permanent"}

    rid = _gid("req")
    conn.execute("""
        INSERT INTO vault_requests (id, secret_name, requesting_agent, purpose,
            risk_class, operation_summary, target_resource, will_do, wont_do,
            worst_case, revoke_url, session_id, requested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (rid, secret_name, requesting_agent, purpose, risk_class,
          operation_summary, target_resource,
          json.dumps(will_do or []), json.dumps(wont_do or []),
          worst_case, revoke_url, session_id, _now()))
    conn.commit()
    conn.close()
    _emit_event("requested", requesting_agent, {
        "request_id": rid, "secret": secret_name, "risk_class": risk_class,
        "purpose": purpose,
    })
    return {"ok": True, "request_id": rid, "status": "pending",
            "approval_url": f"/vault?request_id={rid}"}

def approve_request(request_id: str, approver_email: str, scope: str,
                    secret_value: str) -> Dict[str, Any]:
    if scope not in SCOPE_TYPES:
        return {"ok": False, "error": f"scope must be one of {sorted(SCOPE_TYPES)}"}

    conn = _db()
    req = conn.execute("SELECT * FROM vault_requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        conn.close()
        return {"ok": False, "error": "request_not_found"}
    if req["status"] != "pending":
        conn.close()
        return {"ok": False, "error": f"request_status_{req['status']}"}

    allowed, reason = _can_approve(approver_email, req["risk_class"])
    if not allowed:
        conn.close()
        _emit_event("denied_unauthorized", approver_email,
                   {"request_id": request_id, "reason": reason})
        return {"ok": False, "error": f"not_authorized: {reason}"}

    # Encrypt and act based on scope
    if scope == "permanent":
        if not _CRYPTO_OK:
            conn.close()
            return {"ok": False, "error": "cryptography_lib_missing — permanent scope unavailable"}
        ct, nonce = _encrypt(secret_value)
        agents = [req["requesting_agent"]]
        conn.execute("""
            INSERT OR REPLACE INTO vault_secrets
            (name, encrypted_value, nonce, description, granted_to_agents,
             risk_class, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (req["secret_name"], ct, nonce, req["purpose"], json.dumps(agents),
              req["risk_class"], approver_email, _now()))
        conn.execute("""
            UPDATE vault_requests SET status='granted', granted_scope=?, granted_by=?,
            granted_at=? WHERE id=?
        """, (scope, approver_email, _now(), request_id))
    else:
        # session or one-shot: store base64 in request row (will purge)
        v_b64 = base64.b64encode(secret_value.encode("utf-8")).decode("ascii")
        conn.execute("""
            UPDATE vault_requests SET status='granted', granted_scope=?, granted_by=?,
            granted_at=?, granted_value_b64=? WHERE id=?
        """, (scope, approver_email, _now(), v_b64, request_id))
        if scope == "this_conversation":
            exp = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO vault_session_grants
                (session_id, request_id, secret_name, granted_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (req["session_id"] or "default", request_id, req["secret_name"], _now(), exp))

    conn.commit()
    conn.close()
    _emit_event("granted", approver_email, {
        "request_id": request_id, "secret": req["secret_name"],
        "scope": scope, "agent": req["requesting_agent"],
    })
    return {"ok": True, "request_id": request_id, "scope": scope,
            "secret_name": req["secret_name"]}

def deny_request(request_id: str, approver_email: str, reason: str = "") -> Dict[str, Any]:
    conn = _db()
    req = conn.execute("SELECT * FROM vault_requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        conn.close()
        return {"ok": False, "error": "request_not_found"}
    if req["status"] != "pending":
        conn.close()
        return {"ok": False, "error": f"request_status_{req['status']}"}
    allowed, why = _can_approve(approver_email, req["risk_class"])
    if not allowed:
        conn.close()
        return {"ok": False, "error": f"not_authorized: {why}"}
    conn.execute("""
        UPDATE vault_requests SET status='denied', granted_by=?, granted_at=?,
        denial_reason=? WHERE id=?
    """, (approver_email, _now(), reason, request_id))
    conn.commit()
    conn.close()
    _emit_event("denied", approver_email,
               {"request_id": request_id, "secret": req["secret_name"], "reason": reason})
    return {"ok": True, "request_id": request_id, "status": "denied"}

def use_secret(secret_name: str, requesting_agent: str,
               session_id: Optional[str] = None) -> Dict[str, Any]:
    """Returns the secret value for the agent if authorized."""
    conn = _db()
    # Try permanent vault first
    sec = conn.execute(
        "SELECT * FROM vault_secrets WHERE name=? AND revoked_at IS NULL",
        (secret_name,)).fetchone()
    if sec:
        agents = json.loads(sec["granted_to_agents"] or "[]")
        if requesting_agent in agents:
            try:
                value = _decrypt(sec["encrypted_value"], sec["nonce"])
                conn.execute("""
                    UPDATE vault_secrets SET last_used_at=?, use_count=use_count+1 WHERE name=?
                """, (_now(), secret_name))
                conn.commit()
                conn.close()
                _emit_event("used_permanent", requesting_agent,
                           {"secret": secret_name})
                return {"ok": True, "value": value, "scope": "permanent",
                       "secret_name": secret_name}
            except Exception as e:
                conn.close()
                return {"ok": False, "error": f"decrypt_failed: {e}"}

    # Try session grant
    if session_id:
        sess = conn.execute("""
            SELECT vsg.*, vr.granted_value_b64, vr.requesting_agent
            FROM vault_session_grants vsg
            JOIN vault_requests vr ON vr.id = vsg.request_id
            WHERE vsg.session_id=? AND vsg.secret_name=? AND vr.status='granted'
        """, (session_id, secret_name)).fetchone()
        if sess and sess["granted_value_b64"]:
            if sess["expires_at"] and sess["expires_at"] < _now():
                conn.close()
                return {"ok": False, "error": "session_grant_expired"}
            value = base64.b64decode(sess["granted_value_b64"]).decode("utf-8")
            conn.close()
            _emit_event("used_session", requesting_agent,
                       {"secret": secret_name, "session": session_id})
            return {"ok": True, "value": value, "scope": "this_conversation",
                   "secret_name": secret_name}

    # Try one-shot
    one = conn.execute("""
        SELECT * FROM vault_requests
        WHERE secret_name=? AND requesting_agent=? AND status='granted'
              AND granted_scope='just_this_time'
        ORDER BY granted_at DESC LIMIT 1
    """, (secret_name, requesting_agent)).fetchone()
    if one and one["granted_value_b64"]:
        value = base64.b64decode(one["granted_value_b64"]).decode("utf-8")
        # PURGE the value now (one-shot consumed)
        conn.execute("""
            UPDATE vault_requests SET status='consumed', granted_value_b64=NULL,
            consumed_at=? WHERE id=?
        """, (_now(), one["id"]))
        conn.commit()
        conn.close()
        _emit_event("used_one_shot", requesting_agent,
                   {"secret": secret_name, "request_id": one["id"]})
        return {"ok": True, "value": value, "scope": "just_this_time",
               "secret_name": secret_name, "purged": True}

    conn.close()
    return {"ok": False, "error": "no_grant_found", "secret": secret_name}

def revoke_secret(secret_name: str, by_email: str) -> Dict[str, Any]:
    if by_email.lower() != FOUNDER_EMAIL:
        return {"ok": False, "error": "founder_only"}
    conn = _db()
    conn.execute("UPDATE vault_secrets SET revoked_at=? WHERE name=?",
                (_now(), secret_name))
    conn.commit()
    conn.close()
    _emit_event("revoked", by_email, {"secret": secret_name})
    return {"ok": True, "secret_name": secret_name, "revoked_at": _now()}

# ── HTML approval UI ────────────────────────────────────────────────────────
APPROVAL_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Murphy Vault — Approve Secret Request</title>
<style>
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#0a0e14;color:#c9d1d9;padding:40px 20px;min-height:100vh}
.wrap{max-width:560px;margin:0 auto}
h1{font-size:20px;color:#58a6ff;margin-bottom:8px}
.sub{color:#8b949e;font-size:13px;margin-bottom:24px}
.card{background:#161b22;border:1px solid #21262d;border-radius:14px;padding:22px;margin-bottom:14px}
.risk-tag{display:inline-block;padding:4px 10px;border-radius:10px;font-size:12px;font-weight:600;margin-bottom:12px}
.risk-read{background:#0f2a1c;color:#3fb950;border:1px solid #238636}
.risk-write{background:#3a2a05;color:#d29922;border:1px solid #9e6a03}
.risk-destructive{background:#3c0e0e;color:#f85149;border:1px solid #da3633}
.row{display:flex;gap:8px;margin-bottom:10px;font-size:13.5px}
.row .lbl{color:#8b949e;width:120px;flex-shrink:0}
.row .val{color:#c9d1d9;word-break:break-all;font-family:SF Mono,Menlo,monospace;font-size:12.5px}
ul{margin:6px 0 12px 22px;font-size:13px;color:#c9d1d9}
ul li{margin:3px 0}
.worst{background:#0d1117;padding:10px 14px;border-radius:8px;border-left:3px solid #f85149;font-size:13px;color:#8b949e;margin:8px 0}
input[type=password],input[type=text]{width:100%;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:10px 12px;color:#c9d1d9;font-family:SF Mono,monospace;font-size:13px;margin-bottom:10px}
input:focus{outline:none;border-color:#58a6ff}
.btn{display:block;width:100%;padding:13px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;border:none;margin-top:8px;transition:all .15s}
.btn-grant{background:#f97316;color:white}
.btn-grant:hover{background:#fb8c2f}
.btn-deny{background:#21262d;color:#c9d1d9}
.btn-deny:hover{background:#30363d}
.btn-once{background:#21262d;color:#c9d1d9;font-weight:500}
.btn-once:hover{background:#30363d}
.muted{color:#6e7681;font-size:12px;text-align:center;margin-top:10px}
.revoke{font-size:12px;color:#58a6ff;text-decoration:none;display:block;margin-top:10px}
.empty{text-align:center;padding:60px 20px;color:#6e7681}
</style></head><body>
<div class="wrap" id="root"><div class="empty">Loading…</div></div>
<script>
async function load(){
  const params=new URLSearchParams(location.search);
  const rid=params.get('request_id');
  const r=await fetch('/api/vault/pending').then(r=>r.json());
  const reqs=r.requests||[];
  const root=document.getElementById('root');
  if(!reqs.length){root.innerHTML='<h1>Murphy Vault</h1><div class="card empty">No pending secret requests.</div>';return}
  const target=rid?reqs.find(x=>x.id===rid):reqs[0];
  if(!target){root.innerHTML='<h1>Murphy Vault</h1><div class="card empty">Request not found.</div>';return}
  render(target,reqs.length-1);
}
function render(req,otherCount){
  const will=JSON.parse(req.will_do||'[]'),wont=JSON.parse(req.wont_do||'[]');
  const rc=req.risk_class;
  const tag=rc==='read'?'risk-read 🟢 Read':rc==='write'?'risk-write 🟡 Write':'risk-destructive 🔴 Destructive';
  document.getElementById('root').innerHTML=`
    <h1>Murphy Vault — Secret Request</h1>
    <div class="sub">${otherCount?otherCount+' other pending':''}</div>
    <div class="card">
      <span class="risk-tag ${tag.split(' ')[0]}">${tag.substring(tag.indexOf(' ')+1)} operation</span>
      <div class="row"><div class="lbl">Agent</div><div class="val">${req.requesting_agent}</div></div>
      <div class="row"><div class="lbl">Secret</div><div class="val">${req.secret_name}</div></div>
      <div class="row"><div class="lbl">Purpose</div><div class="val">${req.purpose}</div></div>
      ${req.target_resource?`<div class="row"><div class="lbl">Target</div><div class="val">${req.target_resource}</div></div>`:''}
      ${req.operation_summary?`<div class="row"><div class="lbl">Summary</div><div class="val">${req.operation_summary}</div></div>`:''}
      ${will.length?`<div style="margin-top:14px"><div style="font-size:13px;color:#3fb950;font-weight:600">Will be able to:</div><ul>${will.map(x=>'<li>'+x+'</li>').join('')}</ul></div>`:''}
      ${wont.length?`<div><div style="font-size:13px;color:#8b949e;font-weight:600">Will NOT be able to:</div><ul>${wont.map(x=>'<li>'+x+'</li>').join('')}</ul></div>`:''}
      ${req.worst_case?`<div class="worst"><b>Worst case:</b> ${req.worst_case}</div>`:''}
      ${req.revoke_url?`<a class="revoke" href="${req.revoke_url}" target="_blank">↗ Revoke link if compromised</a>`:''}
    </div>
    <div class="card">
      <div style="font-size:13px;color:#8b949e;margin-bottom:8px">Paste the secret value:</div>
      <input id="secret" type="password" placeholder="Secret value (hidden)" autocomplete="off">
      <input id="email" type="text" placeholder="Approver email (cpost@murphy.systems)" value="cpost@murphy.systems">
      <button class="btn btn-grant" onclick="grant('this_conversation')">Allow for this conversation</button>
      <button class="btn btn-once" onclick="grant('just_this_time')">Just this time</button>
      <button class="btn btn-once" onclick="grant('permanent')">Permanent (encrypted at rest)</button>
      <button class="btn btn-deny" onclick="deny()">Deny</button>
      <div class="muted">All decisions hash-chained in audit log.</div>
    </div>`;
}
async function grant(scope){
  const rid=new URLSearchParams(location.search).get('request_id')||document.querySelector('.val')?.textContent;
  const val=document.getElementById('secret').value;
  const email=document.getElementById('email').value;
  if(!val){alert('Paste the secret value first');return}
  const r=await fetch('/api/vault/approve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:rid,approver_email:email,scope:scope,secret_value:val})}).then(r=>r.json());
  if(r.ok){alert('Granted: '+scope);location.href='/vault'}else{alert('Failed: '+r.error)}
}
async function deny(){
  const rid=new URLSearchParams(location.search).get('request_id')||document.querySelector('.val')?.textContent;
  const email=document.getElementById('email').value;
  const reason=prompt('Reason for denial (shown to agent):')||'';
  const r=await fetch('/api/vault/deny',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:rid,approver_email:email,reason:reason})}).then(r=>r.json());
  if(r.ok){location.href='/vault'}else{alert('Failed: '+r.error)}
}
load();
</script></body></html>"""

# ── FastAPI wiring ──────────────────────────────────────────────────────────
def init_vault_routes(app):
    init_db()

    @app.get("/api/vault/health")
    async def vault_health():
        """Public health check — minimal info, safe for unauthenticated probes.
        
        PATCH-411b (2026-05-24): trimmed to bare liveness signal. Previously
        leaked secret count, pending request count, and master_key_present
        flag — useful reconnaissance for an attacker. The rich state moved
        to /api/vault/status (auth-required).
        """
        return JSONResponse({"ok": True, "patch": "405", "module": "vault"})

    @app.get("/api/vault/status")
    async def vault_status():
        """Detailed vault state — auth required (enforced by modular_auth middleware).
        
        PATCH-411b: this is the rich health response that used to live at
        /api/vault/health. Moved here so it's protected from anonymous reads.
        """
        try:
            conn = _db()
            pending = conn.execute("SELECT COUNT(*) AS c FROM vault_requests WHERE status='pending'").fetchone()["c"]
            stored = conn.execute("SELECT COUNT(*) AS c FROM vault_secrets WHERE revoked_at IS NULL").fetchone()["c"]
            conn.close()
            return JSONResponse({
                "ok": True, "patch": "405", "module": "vault",
                "pending_requests": pending, "stored_secrets": stored,
                "crypto_available": _CRYPTO_OK,
                "master_key_present": os.path.exists(MASTER_KEY_PATH),
                "approver_model": {"destructive": "founder", "write": "founder+kin", "read": "founder+kin"},
                "scopes": sorted(SCOPE_TYPES),
                "risk_classes": sorted(RISK_CLASSES),
            })
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

    @app.post("/api/vault/request")
    async def vault_request(request: Request):
        try: data = await request.json()
        except: data = {}
        result = create_request(
            secret_name=data.get("secret_name"),
            requesting_agent=data.get("requesting_agent"),
            purpose=data.get("purpose"),
            risk_class=data.get("risk_class", "write"),
            operation_summary=data.get("operation_summary", ""),
            target_resource=data.get("target_resource", ""),
            will_do=data.get("will_do") or [],
            wont_do=data.get("wont_do") or [],
            worst_case=data.get("worst_case", ""),
            revoke_url=data.get("revoke_url", ""),
            session_id=data.get("session_id"),
        )
        return JSONResponse(result)

    @app.post("/api/vault/approve")
    async def vault_approve(request: Request):
        try: data = await request.json()
        except: data = {}
        result = approve_request(
            request_id=data.get("request_id"),
            approver_email=data.get("approver_email", FOUNDER_EMAIL),
            scope=data.get("scope", "this_conversation"),
            secret_value=data.get("secret_value", ""),
        )
        return JSONResponse(result)

    @app.post("/api/vault/deny")
    async def vault_deny(request: Request):
        try: data = await request.json()
        except: data = {}
        result = deny_request(
            request_id=data.get("request_id"),
            approver_email=data.get("approver_email", FOUNDER_EMAIL),
            reason=data.get("reason", ""),
        )
        return JSONResponse(result)

    @app.post("/api/vault/use")
    async def vault_use(request: Request):
        try: data = await request.json()
        except: data = {}
        result = use_secret(
            secret_name=data.get("secret_name"),
            requesting_agent=data.get("requesting_agent"),
            session_id=data.get("session_id"),
        )
        return JSONResponse(result)

    @app.get("/api/vault/pending")
    async def vault_pending():
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM vault_requests WHERE status='pending' ORDER BY requested_at DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "requests": [dict(r) for r in rows]})

    @app.get("/api/vault/vault")
    async def vault_list():
        conn = _db()
        rows = conn.execute("""
            SELECT name, description, granted_to_agents, risk_class,
                   created_at, last_used_at, use_count, revoked_at
            FROM vault_secrets ORDER BY created_at DESC
        """).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "secrets": [dict(r) for r in rows]})

    @app.post("/api/vault/revoke")
    async def vault_revoke(request: Request):
        try: data = await request.json()
        except: data = {}
        return JSONResponse(revoke_secret(
            secret_name=data.get("secret_name"),
            by_email=data.get("by_email", "")
        ))

    @app.get("/api/vault/audit")
    async def vault_audit(limit: int = 50):
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM vault_events ORDER BY created_at DESC LIMIT ?",
            (int(limit),)).fetchall()
        conn.close()
        return JSONResponse({"ok": True, "count": len(rows),
                             "events": [dict(r) for r in rows]})

    @app.get("/vault")
    async def vault_ui():
        return HTMLResponse(APPROVAL_HTML)

    return app
