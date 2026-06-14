"""
Ship 31br.FOUNDER_OS — founder navigation + view-as-tier helper.

THREE THINGS:
  1. inject_founder_nav(html)  — injects a top nav bar into the OS dashboard
                                  HTML before serving, so founder can reach
                                  /dashboard /privacy /sub-processors /upgrade
                                  /logout without typing URLs.
  2. set_view_as_tier(sid,t)   — flips a session flag so the founder sees
                                  the tenant dashboard rendered as that tier.
  3. get_view_as_tier(sid)     — reads the flag (None if not set).

NOTHING about the underlying founder account changes. The "view-as" mode
is purely a render-time override.
"""
import json
import sqlite3
from typing import Optional

_DB = "/opt/Murphy-System/murphy.db"
_VALID_TIERS = ("free", "solo", "team", "business", "enterprise")

NAV_HTML = '''
<div id="murphy-founder-nav" style="
  position:fixed;top:0;left:0;right:0;z-index:9999;
  background:#0d1117;border-bottom:1px solid #21262d;
  padding:8px 16px;font-family:Inter,system-ui,sans-serif;
  font-size:13px;color:#e6edf3;
  display:flex;align-items:center;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:18px">
    <span style="font-weight:700;color:#00d4aa">⚡ Murphy OS</span>
    <a href="/os"           style="color:#8b949e;text-decoration:none">OS</a>
    <a href="/dashboard"    style="color:#8b949e;text-decoration:none">Dashboard</a>
    <a href="/os/view-as"   style="color:#8b949e;text-decoration:none">View as…</a>
    <a href="/privacy"      style="color:#8b949e;text-decoration:none">Privacy</a>
    <a href="/sub-processors" style="color:#8b949e;text-decoration:none">Sub-processors</a>
    <a href="/upgrade"      style="color:#8b949e;text-decoration:none">Upgrade</a>
  </div>
  <div style="display:flex;align-items:center;gap:14px">
    <span id="founder-view-as-badge" style="color:#00d4aa;font-size:11px;letter-spacing:1px"></span>
    <a href="/logout" style="color:#f85149;text-decoration:none">Logout</a>
  </div>
</div>
<div style="height:42px"></div>
<script>
  (async function() {
    try {
      const r = await fetch('/api/founder/view-as');
      const d = await r.json();
      if (d && d.tier) {
        document.getElementById('founder-view-as-badge').textContent =
          'VIEWING AS ' + d.tier.toUpperCase();
      }
    } catch (e) {}
  })();
</script>
'''


def inject_founder_nav(html: str) -> str:
    """Inject the nav bar right after <body> in any OS page."""
    if "murphy-founder-nav" in html:
        return html
    if "<body" in html:
        # insert after the opening body tag
        idx = html.find(">", html.find("<body"))
        if idx > 0:
            return html[:idx+1] + NAV_HTML + html[idx+1:]
    # fallback: prepend
    return NAV_HTML + html


def _init_view_as_column():
    conn = sqlite3.connect(_DB, timeout=10.0)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(session_store)").fetchall()]
    if "view_as_tier" not in cols:
        conn.execute("ALTER TABLE session_store ADD COLUMN view_as_tier TEXT")
    conn.commit(); conn.close()


def set_view_as_tier(session_id: str, tier: Optional[str]) -> bool:
    """Flip the founder's view-as override. Pass None to clear."""
    if tier is not None and tier not in _VALID_TIERS:
        return False
    _init_view_as_column()
    conn = sqlite3.connect(_DB, timeout=10.0)
    try:
        conn.execute("UPDATE session_store SET view_as_tier=? WHERE session_id=?",
                     (tier, session_id))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def get_view_as_tier(session_id: str) -> Optional[str]:
    _init_view_as_column()
    conn = sqlite3.connect(_DB, timeout=10.0)
    try:
        row = conn.execute(
            "SELECT view_as_tier FROM session_store WHERE session_id=?",
            (session_id,)
        ).fetchone()
        return row[0] if row and row[0] else None
    finally:
        conn.close()


VALID_TIERS = _VALID_TIERS


def view_as_chooser_html() -> str:
    """The /os/view-as picker page."""
    return '''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>View as tier · Murphy</title>
<style>
* { box-sizing:border-box; margin:0; padding:0 }
body { background:#0d1117; color:#e6edf3; font-family:Inter,system-ui,sans-serif;
       font-size:14px; line-height:1.6; min-height:100vh; padding:80px 24px 40px }
.wrap { max-width:680px; margin:0 auto }
h1 { font-size:28px; font-weight:700; margin-bottom:8px }
.lede { color:#8b949e; margin-bottom:32px }
.tier { display:block; padding:18px 22px; background:#161b22; border:1px solid #21262d;
        border-radius:8px; margin-bottom:12px; cursor:pointer; text-decoration:none;
        color:#e6edf3; transition:border .15s }
.tier:hover { border-color:#00d4aa }
.tier b { display:block; font-size:16px; margin-bottom:4px }
.tier .desc { color:#8b949e; font-size:13px }
.tier .price { color:#00d4aa; font-weight:600; float:right; margin-top:-22px }
.clear { display:inline-block; margin-top:24px; padding:10px 16px;
         background:#1a2733; color:#00d4aa; text-decoration:none; border-radius:6px;
         font-size:13px }
</style></head><body>
<div class="wrap">
<h1>View as tier</h1>
<p class="lede">See the tenant dashboard rendered as if you were that tier. Your account stays unchanged — this is a render-time override only.</p>

<a class="tier" href="/os/view-as/free">
  <span class="price">$0</span>
  <b>Free</b>
  <div class="desc">5 replies per 24 hours · no priority · ads in footer</div>
</a>
<a class="tier" href="/os/view-as/solo">
  <span class="price">$99/mo</span>
  <b>Solo</b>
  <div class="desc">1 seat · unlimited replies · no ads · email support</div>
</a>
<a class="tier" href="/os/view-as/team">
  <span class="price">$399/mo</span>
  <b>Team</b>
  <div class="desc">5 seats · +$79/extra seat · shared inbox · usage dashboard</div>
</a>
<a class="tier" href="/os/view-as/business">
  <span class="price">$799/mo</span>
  <b>Business</b>
  <div class="desc">15 seats · audit log · compliance docs · DPA on request</div>
</a>
<a class="tier" href="/os/view-as/enterprise">
  <span class="price">Custom</span>
  <b>Enterprise</b>
  <div class="desc">Unlimited seats · sales-quoted · signed DPA · SLA</div>
</a>

<a class="clear" href="/os/view-as/clear">← Clear override (return to founder view)</a>
</div></body></html>'''
