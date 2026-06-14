"""
Ship 31bj — Real tenant dashboard.

Replaces the broken capability tile grid with what tenants ACTUALLY
paid for: a clean Murphy-aesthetic dashboard showing
  - their plan + what it includes
  - their inbox (email threads with Murphy)
  - retention badges (auto-delete countdown)
  - clear management actions

Visual: Murphy landing page aesthetic (cyan #00d4aa + dark #0d1117).
"""
import sqlite3
import html as _html
from datetime import datetime, timezone, timedelta
from typing import Dict, List


# What each plan includes (the promise we render to the user)
PLAN_INCLUDES = {
    "free": {
        "title":    "Free",
        "price":    "$0",
        "includes": [
            "5 email replies per 24 hours",
            "Research-grade analysis with citations",
            "Email-only access via murphy@murphy.systems",
        ],
        "limits":   ["No automations", "Replies after limit require upgrade"],
    },
    "solo": {
        "title":    "Solo",
        "price":    "$99/mo",
        "includes": [
            "Unlimited email replies + research",
            "Sales Followup Send",
            "Execute Automation Workflow",
            "List & manage your HITL queue",
            "Priority response (under 60s)",
        ],
        "limits":   ["1 seat", "Personal use"],
    },
    "team": {
        "title":    "Team",
        "price":    "$399/mo",
        "includes": [
            "Everything in Solo, plus:",
            "Up to 5 seats ($79/extra seat)",
            "Create / get / update / list boards",
            "Commission Automation",
            "Get Automation Workflow",
        ],
        "limits":   ["Multi-user collaboration"],
    },
    "business": {
        "title":    "Business",
        "price":    "$799/mo",
        "includes": [
            "Everything in Team, plus:",
            "Up to 15 seats ($79/extra)",
            "Audit History Read",
            "Document Block management",
            "Fire / Delete Automation Trigger",
        ],
        "limits":   ["Enterprise prep"],
    },
    "enterprise": {
        "title":    "Enterprise",
        "price":    "Custom",
        "includes": [
            "Everything in Business, plus:",
            "Unlimited seats",
            "Founder Maintenance access",
            "Identity Device Pair",
            "Compliance attestations (SOC 2 / GDPR)",
        ],
        "limits":   ["Sales-quoted"],
    },
}


def get_tenant_inbox(tenant_email: str, limit: int = 50) -> List[Dict]:
    """Return email threads between this tenant and Murphy."""
    rows = []
    try:
        conn = sqlite3.connect("/var/lib/murphy-production/inbound_replies.db", timeout=10.0)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT subject, from_addr, to_addr, received_at, body_preview,
                   auto_response_status, auto_response_sent_at, intent_class
            FROM inbound_replies
            WHERE from_addr = ?
            ORDER BY received_at DESC LIMIT ?
        """, (tenant_email, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
    except Exception:
        pass

    # Mark retention status
    now = datetime.now(timezone.utc)
    for r in rows:
        try:
            received = datetime.fromisoformat(r["received_at"].replace("Z","+00:00") if "Z" in r["received_at"] else r["received_at"])
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            age_days = (now - received).days
        except Exception:
            age_days = 0
        r["age_days"] = age_days
        # 5 business days ≈ 7 calendar days
        if age_days >= 7:
            r["retention_status"] = "marked_for_delete"
            r["delete_in_days"]   = max(0, 10 - (age_days - 7))
        else:
            r["retention_status"] = "active"
            r["delete_in_days"]   = None
    return rows


def tenant_dashboard_html(email: str, tier: str = "free", 
                          tenant_id: str = "", usage: Dict = None) -> str:
    """Render the tenant dashboard in the Murphy landing aesthetic."""
    usage = usage or {}
    plan = PLAN_INCLUDES.get(tier.lower(), PLAN_INCLUDES["free"])
    threads = get_tenant_inbox(email)
    
    active_threads   = [t for t in threads if t["retention_status"] == "active"]
    pending_delete   = [t for t in threads if t["retention_status"] == "marked_for_delete"]
    
    # Build thread rows
    def thread_row(t):
        subj = _html.escape((t.get("subject") or "(no subject)")[:80])
        when = (t.get("received_at") or "")[:10]
        preview = _html.escape((t.get("body_preview") or "")[:120])
        status_dot = "#00d4aa" if t["retention_status"] == "active" else "#e3b341"
        status_label = (
            f'auto-delete in {t["delete_in_days"]} days' if t["retention_status"] == "marked_for_delete"
            else "active"
        )
        replied = "✓ replied" if (t.get("auto_response_status") == "sent") else "—"
        return f'''<div class="thread">
  <div class="thread-head">
    <span class="dot" style="background:{status_dot}"></span>
    <span class="thread-subj">{subj}</span>
    <span class="thread-when">{when}</span>
  </div>
  <div class="thread-preview">{preview}</div>
  <div class="thread-foot">
    <span>{replied}</span>
    <span class="thread-status">{status_label}</span>
  </div>
</div>'''
    
    active_html  = "\n".join(thread_row(t) for t in active_threads[:20]) or '<div class="empty">No active threads. Email <a href="mailto:murphy@murphy.systems">murphy@murphy.systems</a> to start one.</div>'
    pending_html = "\n".join(thread_row(t) for t in pending_delete[:10]) or '<div class="empty muted">No threads marked for deletion.</div>'
    
    includes_html = "\n".join(f'<li>{_html.escape(item)}</li>' for item in plan["includes"])
    
    tier_badge_color = {"free": "#8b949e", "solo": "#00d4aa", "team": "#39d353",
                       "business": "#e3b341", "enterprise": "#f85149"}.get(tier.lower(), "#8b949e")
    
    return f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<title>Murphy · Your Dashboard</title>
<style>
:root {{
  --bg:#0d1117; --bg2:#131920; --bg3:#161b22; --bg4:#1c2128;
  --border:#21262d; --border2:#30363d;
  --text:#e6edf3; --text2:#8b949e; --text3:#484f58;
  --live:#00d4aa; --teal:#39d353;
  --yellow:#e3b341; --red:#f85149;
}}
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{
  background:var(--bg); color:var(--text);
  font-family:'Inter',system-ui,sans-serif; font-size:13px;
  min-height:100vh; line-height:1.5;
}}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 24px }}

/* HEADER */
.head {{
  display:flex; justify-content:space-between; align-items:center;
  padding-bottom:24px; border-bottom:1px solid var(--border); margin-bottom:32px;
}}
.brand {{ display:flex; align-items:center; gap:12px }}
.eye {{
  width:36px; height:36px; border-radius:50%;
  border:1px solid var(--live); display:flex; align-items:center; justify-content:center;
  color:var(--live); font-weight:700; font-size:14px;
}}
.brand-name {{ font-weight:700; letter-spacing:0.5px; font-size:15px }}
.brand-sub {{ font-size:11px; color:var(--text2); letter-spacing:1.5px; text-transform:uppercase }}
.user-block {{ text-align:right }}
.user-email {{ font-size:13px; color:var(--text); font-weight:500 }}
.user-tenant {{ font-size:10px; color:var(--text3); font-family:monospace }}

/* PLAN CARD */
.plan {{
  background:var(--bg2); border:1px solid var(--border); border-radius:8px;
  padding:24px; margin-bottom:32px;
}}
.plan-head {{
  display:flex; align-items:center; justify-content:space-between; margin-bottom:18px;
}}
.plan-title {{ font-size:22px; font-weight:700; color:var(--text) }}
.plan-tier-badge {{
  display:inline-block; padding:4px 12px; border-radius:12px;
  font-size:10px; letter-spacing:2px; text-transform:uppercase; font-weight:700;
  background:{tier_badge_color}; color:#0d1117;
}}
.plan-price {{ color:var(--live); font-size:14px; font-weight:600; margin-top:2px }}
.plan-includes {{ list-style:none; padding:0 }}
.plan-includes li {{
  padding:8px 0; border-bottom:1px solid var(--border);
  color:var(--text); font-size:13px;
}}
.plan-includes li::before {{
  content:"✓"; color:var(--live); margin-right:10px; font-weight:700;
}}
.plan-includes li:last-child {{ border-bottom:none }}
.manage-row {{ display:flex; gap:10px; margin-top:18px }}
.btn {{
  display:inline-block; padding:9px 16px; border-radius:6px;
  font-size:12px; font-weight:600; letter-spacing:0.5px; text-decoration:none;
  cursor:pointer; border:none; font-family:inherit;
}}
.btn-primary {{ background:var(--live); color:#0d1117 }}
.btn-secondary {{ background:var(--bg4); color:var(--text); border:1px solid var(--border2) }}
.btn-secondary:hover {{ border-color:var(--live) }}

/* INBOX */
.section-h {{
  display:flex; justify-content:space-between; align-items:baseline;
  margin-bottom:14px; padding-bottom:8px; border-bottom:1px solid var(--border);
}}
.section-h h2 {{ font-size:15px; font-weight:700; color:var(--text) }}
.section-h .count {{ color:var(--text2); font-size:11px; font-family:monospace }}

.thread {{
  background:var(--bg2); border:1px solid var(--border); border-radius:6px;
  padding:14px 18px; margin-bottom:10px;
}}
.thread-head {{ display:flex; align-items:center; gap:10px; margin-bottom:6px }}
.dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0 }}
.thread-subj {{ flex:1; font-weight:600; color:var(--text); font-size:13px }}
.thread-when {{ color:var(--text3); font-size:11px; font-family:monospace }}
.thread-preview {{ color:var(--text2); font-size:12px; margin-bottom:6px; line-height:1.5 }}
.thread-foot {{
  display:flex; justify-content:space-between;
  font-size:10px; color:var(--text3); letter-spacing:0.5px;
}}
.thread-status {{ color:var(--yellow) }}
.empty {{
  padding:24px; text-align:center; color:var(--text2);
  background:var(--bg2); border:1px dashed var(--border2); border-radius:6px;
}}
.empty.muted {{ color:var(--text3); border-color:var(--border) }}
.empty a {{ color:var(--live); text-decoration:none }}

/* RETENTION NOTICE */
.retention-notice {{
  background:linear-gradient(90deg, rgba(227,179,65,0.06), transparent);
  border-left:3px solid var(--yellow); padding:12px 16px;
  border-radius:4px; margin-bottom:18px; font-size:12px;
  color:var(--text2); line-height:1.6;
}}
.retention-notice b {{ color:var(--yellow) }}

/* FOOTER */
.foot {{
  margin-top:48px; padding-top:24px; border-top:1px solid var(--border);
  text-align:center; color:var(--text3); font-size:11px;
}}
</style></head>
<body>
<div class="wrap">

  <div class="head">
    <div class="brand">
      <div class="eye">M</div>
      <div>
        <div class="brand-name">Murphy</div>
        <div class="brand-sub">your dashboard</div>
      </div>
    </div>
    <div class="user-block">
      <div class="user-email">{_html.escape(email)}</div>
      <div class="user-tenant">{_html.escape(tenant_id[:24])}</div>
    </div>
  </div>

  <div class="plan">
    <div class="plan-head">
      <div>
        <div class="plan-title">Your plan: {plan["title"]}</div>
        <div class="plan-price">{plan["price"]}</div>
      </div>
      <span class="plan-tier-badge">{tier}</span>
    </div>
    <ul class="plan-includes">
      {includes_html}
    </ul>
    <div class="manage-row">
      {'<a class="btn btn-primary" href="/upgrade">Upgrade plan</a>' if tier in ("free","solo","team") else ''}
      <a class="btn btn-secondary" href="/api/account/billing-history">Billing history</a>
      <a class="btn btn-secondary" href="mailto:murphy@murphy.systems">Email Murphy</a>
    </div>
  </div>

  <div class="retention-notice">
    <b>Privacy & retention.</b> Threads with no reply for 5 business days are marked
    for deletion. Marked threads are deleted from Murphy's servers in 10 days unless
    you reply. Replies always carry the full chain — no thread is ever orphaned.
  </div>

  <div class="section-h">
    <h2>Active threads</h2>
    <span class="count">{len(active_threads)} of {len(threads)}</span>
  </div>
  {active_html}

  <div class="section-h" style="margin-top:32px">
    <h2>Marked for deletion</h2>
    <span class="count">{len(pending_delete)}</span>
  </div>
  {pending_html}

  <div class="foot">
    Inoni LLC · Portland, OR · Murphy {datetime.now(timezone.utc).strftime("%Y-%m-%d")}
  </div>
</div>
</body></html>'''
