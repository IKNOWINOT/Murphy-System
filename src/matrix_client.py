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
