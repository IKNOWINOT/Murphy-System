"""
PATCH-153: Matrix Client — HTTP-based (no matrix-nio required).
Provides send_message() to push notifications to the Murphy HITL room.
"""
import os, json, time, urllib.request, urllib.error, logging

log = logging.getLogger("murphy.matrix")

HOMESERVER  = os.environ.get("MATRIX_HOMESERVER_URL", "http://127.0.0.1:18008")
ACCESS_TOKEN= os.environ.get("MATRIX_ACCESS_TOKEN", "")
HITL_ROOM   = os.environ.get("MATRIX_HITL_ROOM_ID", "!wKteEeEXPSdgDwOiDk:murphy.systems")
API_BASE    = os.environ.get("MATRIX_API_BASE", "r0")

_txn_counter = 0

def _txn_id() -> str:
    global _txn_counter
    _txn_counter += 1
    return f"murphy_{int(time.time())}_{_txn_counter}"

def send_message(text: str, room_id: str = None, html: str = None) -> dict:
    """Send a plain-text (or HTML) message to a Matrix room."""
    room = room_id or HITL_ROOM
    token = ACCESS_TOKEN or os.environ.get("MATRIX_ACCESS_TOKEN", "")
    if not token:
        log.warning("Matrix: no access token configured")
        return {"ok": False, "error": "no token"}
    
    body: dict = {"msgtype": "m.text", "body": text}
    if html:
        body["format"] = "org.matrix.custom.html"
        body["formatted_body"] = html
    
    url = f"{HOMESERVER}/_matrix/client/{API_BASE}/rooms/{urllib.request.quote(room, safe='')}/send/m.room.message/{_txn_id()}"
    
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="PUT",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=8)
        result = json.loads(resp.read().decode())
        log.info(f"Matrix message sent: {result.get('event_id','?')}")
        return {"ok": True, "event_id": result.get("event_id")}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log.error(f"Matrix HTTP {e.code}: {err[:200]}")
        return {"ok": False, "error": err[:200], "code": e.code}
    except Exception as e:
        log.error(f"Matrix send error: {e}")
        return {"ok": False, "error": str(e)}

def send_hitl_alert(title: str, details: str, severity: str = "warn") -> dict:
    """Send a formatted HITL alert."""
    icons = {"info": "ℹ️", "warn": "⚠️", "critical": "🚨", "ok": "✅"}
    icon = icons.get(severity, "⚠️")
    text = f"{icon} MURPHY HITL | {title}\n{details}"
    html = (f'<b>{icon} MURPHY HITL</b><br/>'
            f'<b>{title}</b><br/>'
            f'<pre>{details}</pre>')
    return send_message(text, html=html)

def is_configured() -> bool:
    token = os.environ.get("MATRIX_ACCESS_TOKEN", "")
    return bool(token and len(token) > 10)


# ── PATCH-154: User provisioning ─────────────────────────────────────────────

COMMUNITY_ROOMS = [
    "!hUzScFjKyUJcHarGdc:murphy.systems",  # general
    "!dfmezUJypdpFAKFLbt:murphy.systems",  # announcements
    "!NMqTVohXKdkCxeJAjU:murphy.systems",  # dev
    "!vzXsiYEufuEYMfiOSf:murphy.systems",  # ai-ethics
    "!GdrWPhKmGtyzgZFbvH:murphy.systems",  # showcase
    "!pwtSTwpToPQHzHsFif:murphy.systems",  # off-topic
]

def _matrix_request(method: str, path: str, data: dict = None, token: str = None) -> tuple:
    """Low-level Matrix API call. Returns (status_code, response_dict)."""
    tok = token or ACCESS_TOKEN or os.environ.get("MATRIX_ACCESS_TOKEN", "")
    hs  = HOMESERVER
    url = f"{hs}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tok}",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def _slugify(email: str) -> str:
    """Convert email to a valid Matrix localpart: letters, digits, hyphens, dots, underscores."""
    import re
    local = email.split("@")[0].lower()
    local = re.sub(r"[^a-z0-9._-]", "_", local)
    local = re.sub(r"_+", "_", local).strip("_")
    return local or "user"


def provision_user(email: str, password: str, display_name: str = "") -> dict:
    """
    PATCH-154: Create a Matrix account for a newly registered Murphy user.

    Uses the Synapse admin API (registration without verification).
    Returns {ok, matrix_user_id, matrix_access_token, error}.
    """
    admin_token = os.environ.get("MATRIX_ACCESS_TOKEN", "")
    server_domain = os.environ.get("MATRIX_SERVER_DOMAIN", "murphy.systems")

    localpart = _slugify(email)
    user_id   = f"@{localpart}:{server_domain}"

    # Try admin registration endpoint first (Synapse-specific)
    status, resp = _matrix_request(
        "PUT",
        f"/_synapse/admin/v2/users/{urllib.request.quote(user_id, safe='')}",
        data={
            "password": password,
            "displayname": display_name or localpart,
            "admin": False,
            "deactivated": False,
        },
        token=admin_token,
    )

    if status not in (200, 201):
        err = resp.get("error", f"status {status}")
        # If localpart conflict, try with a suffix
        if "exists" in err.lower() or status == 400:
            log.info("Matrix localpart %s exists, using email-based localpart", localpart)
            # User already exists — just log them in to get a token
        else:
            log.error("Matrix provision failed for %s: %s", email, err)
            return {"ok": False, "error": err, "matrix_user_id": user_id}

    # Log the new user in to get their access token
    login_status, login_resp = _matrix_request(
        "POST",
        "/_matrix/client/r0/login",
        data={
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": localpart},
            "password": password,
        },
        token=None,  # no auth needed for login
    )

    if login_status != 200:
        log.error("Matrix login failed for %s: %s", email, login_resp)
        return {"ok": False, "error": login_resp.get("error", "login failed"), "matrix_user_id": user_id}

    user_token = login_resp.get("access_token", "")
    log.info("Matrix account provisioned: %s", user_id)

    # Set display name
    if display_name and user_token:
        _matrix_request(
            "PUT",
            f"/_matrix/client/r0/profile/{urllib.request.quote(user_id, safe='')}/displayname",
            data={"displayname": display_name},
            token=user_token,
        )

    # Auto-join all community rooms
    join_results = join_community_rooms(user_token, user_id)

    return {
        "ok": True,
        "matrix_user_id": user_id,
        "matrix_access_token": user_token,
        "joined_rooms": join_results,
    }


def join_community_rooms(user_token: str, user_id: str = "") -> list:
    """
    PATCH-154: Invite + join user to all public community rooms.
    Uses admin token to invite, then user token to join.
    """
    admin_token = os.environ.get("MATRIX_ACCESS_TOKEN", "")
    results = []

    for room_id in COMMUNITY_ROOMS:
        # Admin invites the user
        inv_status, inv_resp = _matrix_request(
            "POST",
            f"/_matrix/client/r0/rooms/{urllib.request.quote(room_id, safe='')}/invite",
            data={"user_id": user_id} if user_id else {},
            token=admin_token,
        )

        # User joins (works for public rooms without invite too)
        join_status, join_resp = _matrix_request(
            "POST",
            f"/_matrix/client/r0/join/{urllib.request.quote(room_id, safe='')}",
            data={},
            token=user_token,
        )

        ok = join_status in (200, 403)  # 403 = already joined
        results.append({
            "room_id": room_id,
            "ok": ok,
            "join_status": join_status,
        })
        log.info("Room join %s → %s: %s", user_id, room_id, join_status)

    return results
