"""
Ship 31ae — Unsubscribe handler. RFC 8058 one-click + browser-fallback.
"""
import sqlite3, time
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse

router = APIRouter()
DB = "/var/lib/murphy-production/entity_graph.db"

def _ensure_table():
    with sqlite3.connect(DB) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS unsubscribe_registry (
                email_addr TEXT PRIMARY KEY,
                token TEXT,
                unsubscribed_at TEXT NOT NULL,
                source TEXT,
                user_agent TEXT
            )
        """)

@router.post("/unsubscribe")
async def unsubscribe_post(request: Request, e: str = Query(...), t: str = Query("")):
    """RFC 8058 one-click. Returns 200 immediately."""
    _ensure_table()
    ua = request.headers.get("user-agent", "")[:200]
    with sqlite3.connect(DB) as c:
        c.execute("""
            INSERT OR REPLACE INTO unsubscribe_registry
            (email_addr, token, unsubscribed_at, source, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (e.lower(), t, time.strftime("%Y-%m-%dT%H:%M:%SZ"), "one_click", ua))
    return JSONResponse({"ok": True, "unsubscribed": e})

@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_get(e: str = Query(...), t: str = Query("")):
    """Browser GET — show confirmation page, also write registry."""
    _ensure_table()
    with sqlite3.connect(DB) as c:
        c.execute("""
            INSERT OR REPLACE INTO unsubscribe_registry
            (email_addr, token, unsubscribed_at, source, user_agent)
            VALUES (?, ?, ?, ?, ?)
        """, (e.lower(), t, time.strftime("%Y-%m-%dT%H:%M:%SZ"), "browser_get", ""))
    return f"""<!DOCTYPE html>
<html><head><title>Unsubscribed — Murphy</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#111a15;color:#e9eae6;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px}}
.card{{max-width:480px;background:#1a2520;border:1px solid #00d4aa33;border-radius:12px;
padding:32px;text-align:center}}
h1{{color:#00d4aa;margin:0 0 12px}}
.email{{color:#7fa890;font-family:ui-monospace,monospace;font-size:13px;margin:16px 0}}
a{{color:#00d4aa}}
</style></head>
<body><div class="card">
<h1>Unsubscribed</h1>
<p>You won't receive further automated emails from Murphy.</p>
<div class="email">{e}</div>
<p style="font-size:13px;color:#7fa890">If this was a mistake, just email
<a href="mailto:hello@murphy.systems">hello@murphy.systems</a> and we'll restore it.</p>
</div></body></html>"""
