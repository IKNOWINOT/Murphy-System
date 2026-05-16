"""
PATCH-324 — OAuth Provider Completion + User DB Persistence
============================================================
Wires into existing app.py WITHOUT creating new files.

What this patch does:
1. Adds LinkedIn, Apple, Meta, GitHub to the backend OAuth flow
   (they were in the registry but GitHub wasn't OIDC-standard)
2. Adds persistent oauth_identities table to murphy_users.db
   (maps provider+provider_user_id → local user account)
3. Auto-creates/merges accounts on first social login
4. Issues a durable session token stored in httpOnly cookie
5. /api/auth/providers returns live enabled state for all 5

Run: python3 patch324_oauth_providers.py
Applies to: /opt/Murphy-System/src/runtime/app.py
"""
import os, re

APP_PATH = '/opt/Murphy-System/src/runtime/app.py'

PATCH = '''
# ══════════════════════════════════════════════════════════════════════════════
# PATCH-324: Full OAuth — Google / GitHub / LinkedIn / Apple / Meta
# User DB: oauth_identities table in murphy_users.db
# Session: 30-day httpOnly cookie, persistent across restarts
# ══════════════════════════════════════════════════════════════════════════════

import sqlite3 as _sqlite3
import urllib.request as _urllib_req
import urllib.parse as _urllib_parse
import json as _json
import secrets as _secrets
import time as _time
import hashlib as _hashlib

_OAUTH_DB = '/var/lib/murphy-production/murphy_users.db'
_SESSION_COOKIE = 'murphy_session'
_SESSION_DAYS = 30

# ── Database bootstrap ────────────────────────────────────────────────────────
def _oauth_db():
    """Return a connection to the user/oauth database."""
    con = _sqlite3.connect(_OAUTH_DB, check_same_thread=False, timeout=10)
    con.row_factory = _sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        id          TEXT PRIMARY KEY,
        email       TEXT UNIQUE,
        display_name TEXT,
        given_name  TEXT,
        family_name TEXT,
        role        TEXT DEFAULT 'user',
        tier        TEXT DEFAULT 'free',
        created_at  TEXT DEFAULT (datetime('now')),
        last_login  TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS oauth_identities (
        id              TEXT PRIMARY KEY,
        user_id         TEXT REFERENCES users(id),
        provider        TEXT NOT NULL,
        provider_user_id TEXT NOT NULL,
        email           TEXT,
        access_token    TEXT,
        refresh_token   TEXT,
        token_expires   INTEGER,
        picture         TEXT,
        raw_profile     TEXT,
        linked_at       TEXT DEFAULT (datetime('now')),
        UNIQUE(provider, provider_user_id)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token       TEXT PRIMARY KEY,
        user_id     TEXT REFERENCES users(id),
        created_at  INTEGER,
        expires_at  INTEGER,
        ip          TEXT,
        user_agent  TEXT
    )""")
    con.commit()
    return con

def _upsert_oauth_user(provider, profile, tokens):
    """
    Find or create a user account from an OAuth profile.
    Merges by email if an account already exists.
    Returns the user dict.
    """
    import uuid as _uuid
    con = _oauth_db()
    try:
        email = profile.get('email','').lower().strip()
        provider_uid = str(profile.get('provider_user_id',''))
        display_name = profile.get('display_name','')
        given = profile.get('given_name','')
        family = profile.get('family_name','')
        picture = profile.get('picture','')

        # Check if this oauth identity already exists
        row = con.execute(
            "SELECT user_id FROM oauth_identities WHERE provider=? AND provider_user_id=?",
            (provider, provider_uid)
        ).fetchone()

        if row:
            user_id = row['user_id']
        else:
            # Try to find existing user by email
            user_row = con.execute(
                "SELECT id FROM users WHERE email=?", (email,)
            ).fetchone() if email else None

            if user_row:
                user_id = user_row['id']
            else:
                # Create new user
                user_id = str(_uuid.uuid4())
                con.execute(
                    "INSERT OR IGNORE INTO users (id,email,display_name,given_name,family_name) VALUES (?,?,?,?,?)",
                    (user_id, email or None, display_name, given, family)
                )

            # Link this oauth identity to the user
            con.execute("""INSERT OR REPLACE INTO oauth_identities
                (id, user_id, provider, provider_user_id, email, access_token,
                 refresh_token, token_expires, picture, raw_profile)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (str(_uuid.uuid4()), user_id, provider, provider_uid,
                 email, tokens.get('access_token',''),
                 tokens.get('refresh_token',''),
                 int(_time.time()) + tokens.get('expires_in', 3600),
                 picture, _json.dumps(profile))
            )

        # Update last login + fill in missing display name
        con.execute(
            "UPDATE users SET last_login=datetime('now'), display_name=COALESCE(NULLIF(display_name,''),?) WHERE id=?",
            (display_name, user_id)
        )
        con.commit()

        user = dict(con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        # Apply founder override
        if email in ('cpost@murphy.systems','corey.eecs@gmail.com','corey.gfc@gmail.com'):
            user['role'] = 'owner'
            user['tier'] = 'enterprise'
        return user
    finally:
        con.close()

def _create_session(user_id, ip='', ua=''):
    """Create a persistent session token. Returns token string."""
    token = _secrets.token_urlsafe(48)
    now = int(_time.time())
    expires = now + (_SESSION_DAYS * 86400)
    con = _oauth_db()
    try:
        con.execute(
            "INSERT INTO sessions (token,user_id,created_at,expires_at,ip,user_agent) VALUES (?,?,?,?,?,?)",
            (token, user_id, now, expires, ip, ua)
        )
        con.commit()
    finally:
        con.close()
    return token

def _resolve_session(token):
    """Validate a session token. Returns user dict or None."""
    if not token:
        return None
    con = _oauth_db()
    try:
        row = con.execute("""
            SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id
            WHERE s.token=? AND s.expires_at > ?
        """, (token, int(_time.time()))).fetchone()
        if not row:
            return None
        user = dict(row)
        email = user.get('email','')
        if email in ('cpost@murphy.systems','corey.eecs@gmail.com','corey.gfc@gmail.com'):
            user['role'] = 'owner'
            user['tier'] = 'enterprise'
        return user
    finally:
        con.close()

# ── OAuth state store (in-memory, 10 min TTL) ─────────────────────────────────
_oauth_states = {}

def _new_state(provider):
    state = _secrets.token_urlsafe(24)
    _oauth_states[state] = {'provider': provider, 'ts': _time.time()}
    # Purge old states
    now = _time.time()
    expired = [k for k,v in _oauth_states.items() if now - v['ts'] > 600]
    for k in expired:
        del _oauth_states[k]
    return state

def _consume_state(state):
    entry = _oauth_states.pop(state, None)
    if entry and _time.time() - entry['ts'] < 600:
        return entry['provider']
    return None

# ── Provider config (reads env vars set in murphy-production.service) ─────────
def _provider_cfg():
    base = os.environ.get('MURPHY_OAUTH_REDIRECT_URI', 'https://murphy.systems/api/auth/callback')
    return {
        'google': {
            'client_id':     os.environ.get('MURPHY_OAUTH_GOOGLE_CLIENT_ID',''),
            'client_secret': os.environ.get('MURPHY_OAUTH_GOOGLE_SECRET',''),
            'authorize':     'https://accounts.google.com/o/oauth2/v2/auth',
            'token':         'https://oauth2.googleapis.com/token',
            'userinfo':      'https://openidconnect.googleapis.com/v1/userinfo',
            'scopes':        'openid email profile',
            'redirect':      base,
        },
        'github': {
            'client_id':     os.environ.get('MURPHY_OAUTH_GITHUB_CLIENT_ID',''),
            'client_secret': os.environ.get('MURPHY_OAUTH_GITHUB_SECRET',''),
            'authorize':     'https://github.com/login/oauth/authorize',
            'token':         'https://github.com/login/oauth/access_token',
            'userinfo':      'https://api.github.com/user',
            'userinfo_email':'https://api.github.com/user/emails',
            'scopes':        'read:user user:email',
            'redirect':      base,
        },
        'linkedin': {
            'client_id':     os.environ.get('MURPHY_OAUTH_LINKEDIN_CLIENT_ID',''),
            'client_secret': os.environ.get('MURPHY_OAUTH_LINKEDIN_SECRET',''),
            'authorize':     'https://www.linkedin.com/oauth/v2/authorization',
            'token':         'https://www.linkedin.com/oauth/v2/accessToken',
            'userinfo':      'https://api.linkedin.com/v2/userinfo',
            'scopes':        'openid profile email',
            'redirect':      base,
        },
        'apple': {
            'client_id':     os.environ.get('MURPHY_OAUTH_APPLE_CLIENT_ID',''),
            'client_secret': os.environ.get('MURPHY_OAUTH_APPLE_SECRET',''),
            'authorize':     'https://appleid.apple.com/auth/authorize',
            'token':         'https://appleid.apple.com/auth/token',
            'userinfo':      '',  # Apple returns identity in id_token
            'scopes':        'name email',
            'redirect':      base,
        },
        'meta': {
            'client_id':     os.environ.get('MURPHY_OAUTH_META_CLIENT_ID',''),
            'client_secret': os.environ.get('MURPHY_OAUTH_META_SECRET',''),
            'authorize':     'https://www.facebook.com/v18.0/dialog/oauth',
            'token':         'https://graph.facebook.com/v18.0/oauth/access_token',
            'userinfo':      'https://graph.facebook.com/v18.0/me?fields=id,name,email,first_name,last_name,picture',
            'scopes':        'email public_profile',
            'redirect':      base,
        },
    }

def _http_get(url, headers=None, timeout=10):
    req = _urllib_req.Request(url, headers=headers or {})
    with _urllib_req.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read())

def _http_post(url, data, headers=None, timeout=10):
    body = _urllib_parse.urlencode(data).encode()
    req = _urllib_req.Request(url, data=body, headers={
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        **(headers or {})
    })
    with _urllib_req.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read())

def _exchange_code(provider, cfg, code):
    """Exchange authorization code for tokens. Returns (tokens_dict, profile_dict)."""
    tokens = _http_post(cfg['token'], {
        'client_id':     cfg['client_id'],
        'client_secret': cfg['client_secret'],
        'code':          code,
        'grant_type':    'authorization_code',
        'redirect_uri':  cfg['redirect'],
    }, headers={'Accept': 'application/json'})

    access_token = tokens.get('access_token','')

    # Fetch profile
    if provider == 'github':
        raw = _http_get(cfg['userinfo'], headers={
            'Authorization': f'token {access_token}',
            'User-Agent': 'Murphy-System',
            'Accept': 'application/vnd.github.v3+json'
        })
        # GitHub may not return email in /user — fetch separately
        email = raw.get('email','')
        if not email:
            try:
                emails = _http_get(cfg['userinfo_email'], headers={
                    'Authorization': f'token {access_token}',
                    'User-Agent': 'Murphy-System'
                })
                primary = next((e for e in emails if e.get('primary') and e.get('verified')), None)
                email = primary['email'] if primary else (emails[0]['email'] if emails else '')
            except Exception:
                pass
        profile = {
            'email': email,
            'display_name': raw.get('name','') or raw.get('login',''),
            'given_name': '',
            'family_name': '',
            'provider_user_id': str(raw.get('id','')),
            'picture': raw.get('avatar_url',''),
        }
    elif provider == 'apple':
        # Apple returns user info in the id_token JWT claims (first login only)
        import base64 as _b64
        id_token = tokens.get('id_token','')
        claims = {}
        if id_token:
            try:
                parts = id_token.split('.')
                padded = parts[1] + '=='
                claims = _json.loads(_b64.b64decode(padded))
            except Exception:
                pass
        profile = {
            'email': claims.get('email',''),
            'display_name': claims.get('email','').split('@')[0],
            'given_name': '',
            'family_name': '',
            'provider_user_id': claims.get('sub',''),
            'picture': '',
        }
    elif provider == 'meta':
        raw = _http_get(cfg['userinfo'], headers={'Authorization': f'Bearer {access_token}'})
        profile = {
            'email': raw.get('email',''),
            'display_name': raw.get('name',''),
            'given_name': raw.get('first_name',''),
            'family_name': raw.get('last_name',''),
            'provider_user_id': str(raw.get('id','')),
            'picture': raw.get('picture',{}).get('data',{}).get('url','') if isinstance(raw.get('picture'),dict) else '',
        }
    else:
        # Google, LinkedIn — standard OIDC userinfo
        raw = _http_get(cfg['userinfo'], headers={'Authorization': f'Bearer {access_token}'})
        profile = {
            'email': raw.get('email',''),
            'display_name': raw.get('name',''),
            'given_name': raw.get('given_name',''),
            'family_name': raw.get('family_name',''),
            'provider_user_id': raw.get('sub','') or raw.get('id',''),
            'picture': raw.get('picture',''),
        }
    return tokens, profile

# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/api/auth/providers')
def auth_providers():
    """Returns which OAuth providers are currently configured."""
    cfg = _provider_cfg()
    return jsonify({
        'providers': {
            p: bool(v['client_id'] and v['client_secret'])
            for p, v in cfg.items()
        }
    })

@app.route('/api/auth/oauth/<provider>')
def oauth_start(provider):
    """Redirect user to the OAuth provider's consent screen."""
    cfg = _provider_cfg()
    if provider not in cfg:
        return redirect(f'/ui/login?error=unsupported_provider&provider={provider}')
    p = cfg[provider]
    if not (p['client_id'] and p['client_secret']):
        return redirect(f'/ui/login?error=oauth_not_configured&provider={provider}')

    state = _new_state(provider)
    params = {
        'client_id':     p['client_id'],
        'redirect_uri':  p['redirect'],
        'response_type': 'code',
        'scope':         p['scopes'],
        'state':         state,
    }
    if provider == 'apple':
        params['response_mode'] = 'form_post'
    if provider == 'google':
        params['access_type'] = 'offline'
        params['prompt'] = 'select_account'

    url = p['authorize'] + '?' + _urllib_parse.urlencode(params)
    return redirect(url)

@app.route('/api/auth/callback', methods=['GET','POST'])
def oauth_callback():
    """Handles the OAuth callback from all providers."""
    # Apple sends POST, everyone else sends GET
    code  = request.values.get('code','')
    state = request.values.get('state','')
    error = request.values.get('error','')

    if error:
        return redirect(f'/ui/login?error=oauth_error')

    provider = _consume_state(state)
    if not provider:
        return redirect('/ui/login?error=oauth_error')

    cfg = _provider_cfg()
    p = cfg.get(provider)
    if not p:
        return redirect('/ui/login?error=unsupported_provider')

    try:
        tokens, profile = _exchange_code(provider, p, code)
    except Exception as e:
        app.logger.error(f"[oauth] token exchange failed ({provider}): {e}")
        return redirect(f'/ui/login?error=oauth_error&provider={provider}')

    if not profile.get('provider_user_id'):
        return redirect(f'/ui/login?error=oauth_error&provider={provider}')

    # Upsert user in DB and create session
    user = _upsert_oauth_user(provider, profile, tokens)
    session_token = _create_session(
        user['id'],
        ip=request.remote_addr,
        ua=request.headers.get('User-Agent','')
    )

    resp = redirect('/ui/terminal-unified')
    resp.set_cookie(
        _SESSION_COOKIE, session_token,
        max_age=_SESSION_DAYS * 86400,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return resp

@app.route('/api/auth/me')
def auth_me():
    """Returns the current user from session cookie or Bearer token."""
    token = request.cookies.get(_SESSION_COOKIE) or ''
    if not token:
        auth_header = request.headers.get('Authorization','')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
    user = _resolve_session(token)
    if not user:
        return jsonify({'authenticated': False}), 401
    return jsonify({'authenticated': True, 'user': {
        'id': user['id'],
        'email': user.get('email',''),
        'display_name': user.get('display_name',''),
        'role': user.get('role','user'),
        'tier': user.get('tier','free'),
    }})

@app.route('/api/auth/logout', methods=['POST','GET'])
def auth_logout():
    """Invalidate the current session."""
    token = request.cookies.get(_SESSION_COOKIE,'')
    if token:
        try:
            con = _oauth_db()
            con.execute("DELETE FROM sessions WHERE token=?", (token,))
            con.commit()
            con.close()
        except Exception:
            pass
    resp = redirect('/ui/login')
    resp.delete_cookie(_SESSION_COOKIE)
    return resp

@app.route('/api/auth/linked-accounts')
def auth_linked_accounts():
    """Returns which OAuth providers are linked to the current user."""
    token = request.cookies.get(_SESSION_COOKIE,'')
    user = _resolve_session(token)
    if not user:
        return jsonify({'error': 'unauthenticated'}), 401
    con = _oauth_db()
    try:
        rows = con.execute(
            "SELECT provider, linked_at, picture FROM oauth_identities WHERE user_id=?",
            (user['id'],)
        ).fetchall()
        return jsonify({'linked': [dict(r) for r in rows]})
    finally:
        con.close()

# ══════════════════════════════════════════════════════════════════════════════
# END PATCH-324
# ══════════════════════════════════════════════════════════════════════════════
'''

if __name__ == '__main__':
    if not os.path.exists(APP_PATH):
        print(f"[PATCH-324] app.py not found at {APP_PATH}")
        exit(1)

    with open(APP_PATH) as f:
        src = f.read()

    if 'PATCH-324' in src:
        print("[PATCH-324] Already applied — skipping")
        exit(0)

    # Insert before the final if __name__ block
    marker = "if __name__ == '__main__':"
    if marker in src:
        src = src.replace(marker, PATCH + '\n' + marker, 1)
    else:
        src += '\n' + PATCH

    with open(APP_PATH, 'w') as f:
        f.write(src)

    print("[PATCH-324] ✓ Applied — OAuth routes + user DB wired into app.py")
    print("  Routes added:")
    print("    GET  /api/auth/providers")
    print("    GET  /api/auth/oauth/<provider>  (google/github/linkedin/apple/meta)")
    print("    GET  /api/auth/callback          (+ POST for Apple)")
    print("    GET  /api/auth/me")
    print("    POST /api/auth/logout")
    print("    GET  /api/auth/linked-accounts")
    print("")
    print("  Next: set env vars in murphy-production.service:")
    print("    MURPHY_OAUTH_GOOGLE_CLIENT_ID=")
    print("    MURPHY_OAUTH_GOOGLE_SECRET=")
    print("    MURPHY_OAUTH_GITHUB_CLIENT_ID=")
    print("    MURPHY_OAUTH_GITHUB_SECRET=")
    print("    MURPHY_OAUTH_LINKEDIN_CLIENT_ID=")
    print("    MURPHY_OAUTH_LINKEDIN_SECRET=")
    print("    MURPHY_OAUTH_APPLE_CLIENT_ID=")
    print("    MURPHY_OAUTH_APPLE_SECRET=")
    print("    MURPHY_OAUTH_META_CLIENT_ID=")
    print("    MURPHY_OAUTH_META_SECRET=")
    print("    MURPHY_OAUTH_REDIRECT_URI=https://murphy.systems/api/auth/callback")
