#!/usr/bin/env python3
"""
Murphy Morning Brief — PATCH-BRIEF-001
Sends a daily operations email to cpost@murphy.systems, callmehandy@gmail.com, corey.gfc@gmail.com
Pulls live data from Murphy APIs, composes a clean brief, sends via murphy@murphy.systems SMTP.

Deploy to: /opt/Murphy-System/morning_brief.py
Cron: 0 14 * * * (= 7:00 AM Pacific / 14:00 UTC)
"""

import os
import json
import smtplib
import ssl
import subprocess
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL      = "http://127.0.0.1:8000"
def _read_env_api_key():
    """R325: read MURPHY_API_KEY from environment file as the fallback."""
    if os.getenv("MURPHY_API_KEY"):
        return os.getenv("MURPHY_API_KEY")
    try:
        with open("/etc/murphy-production/environment") as _f:
            for _l in _f:
                if _l.startswith("MURPHY_API_KEY="):
                    return _l.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return ""
API_KEY       = _read_env_api_key()
HEADERS       = {"X-Murphy-Key": API_KEY, "Content-Type": "application/json"}

SMTP_HOST     = "localhost"
SMTP_PORT     = 587
SMTP_USER     = "cpost@murphy.systems"
SMTP_PASS     = "Password1"
FROM_EMAIL    = "murphy@murphy.systems"

RECIPIENTS    = [
    "cpost@murphy.systems",
    "callmehandy@gmail.com",
    "corey.gfc@gmail.com",
]


def _send_via_sendmail(msg_obj, to_addrs):
    """R327: bypass SMTP auth — use local sendmail directly (matches R320 mailer)."""
    try:
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]
        r = subprocess.run(
            ["/usr/sbin/sendmail", "-f", FROM_EMAIL] + list(to_addrs),
            input=msg_obj.as_bytes(), timeout=20, capture_output=True,
        )
        return r.returncode == 0, (r.stderr.decode()[:100] if r.returncode else "")
    except Exception as e:
        return False, str(e)


# ── Fetch helpers ─────────────────────────────────────────────────────────────
def get(path, default=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  WARN {path}: {e}")
    return default or {}

def post(path, body, default=None):
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=body, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  WARN POST {path}: {e}")
    return default or {}

# ── Pull live data ────────────────────────────────────────────────────────────
def collect_data():
    print("Collecting live Murphy data...")

    mind     = get("/api/swarm/mind/status")
    agents   = get("/api/swarm/agents/status", {})
    mfgc     = get("/api/mfgc/state")
    gates    = get("/api/mfgc/gates")
    shield   = get("/api/shield/status")
    crm_raw  = get("/api/crm/deals")
    signals  = get("/api/swarm/bus/feed?limit=10&format=json", {})
    soul     = get("/api/rosetta/soul")

    # Exec summary via dispatch
    exec_data = post("/api/exec/cycle", {
        "task": "Give me a 3-sentence executive summary of Murphy's overnight activity, top business priority, and one recommended action for today.",
        "mode": "brief"
    })

    return {
        "mind":     mind,
        "agents":   agents,
        "mfgc":     mfgc,
        "gates":    gates,
        "shield":   shield,
        "crm":      crm_raw,
        "signals":  signals,
        "soul":     soul,
        "exec":     exec_data,
    }

# ── Format helpers ────────────────────────────────────────────────────────────

# ── R337: substrate + sales + automation + signup collectors ────────────────
def _r337_console_get(path, timeout=8):
    """Fetch JSON from console-api (port 8090)."""
    import urllib.request, json as _j
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8090{path}",
                                     timeout=timeout) as r:
            return _j.loads(r.read())
    except Exception:
        return None


def _r337_collect_extras():
    """Collect data for R337 morning brief sections."""
    data = {}

    # Substrate health (R333 detection)
    psu = _r337_console_get("/diag/psutil-now")
    if psu:
        gap = psu.get("gap", {})
        gate = psu.get("capacity_gate_sees", {})
        actual = psu.get("actual", {})
        data["substrate"] = {
            "diagnosis": gap.get("diagnosis"),
            "actual_cpu": actual.get("cpu_percent"),
            "gate_cpu": gate.get("avg_cpu"),
            "staleness_hours": gate.get("staleness_hours"),
            "degraded": gap.get("diagnosis") == "R333_capacity_gate_stale",
        }

    # Publish flow
    pg = _r337_console_get("/diag/publish-gap?window_minutes=60")
    if pg:
        data["publish"] = {
            "events_published": pg.get("events_published_total"),
            "outcome_count": pg.get("outcome_count"),
            "diagnosis": pg.get("diagnosis"),
        }

    # Sales activity (last 24h)
    sm = _r337_console_get("/sales/overview")
    if sm:
        data["sales"] = sm

    # Send controls
    settings = _r337_console_get("/sales/settings")
    if settings:
        data["send_controls"] = {
            "paused": bool(settings.get("paused")),
            "daily_cap": settings.get("daily_cap"),
            "sends_today": settings.get("sends_today"),
        }

    # Automation pattern (R336)
    ad = _r337_console_get("/sales/automation-detail?limit=10")
    if ad:
        data["automation"] = {
            "runs_seen": len(ad.get("runs", [])),
            "most_common": ad.get("most_common_pattern"),
            "diagnosis_counts": ad.get("diagnosis_counts", {}),
        }

    # Prospect replies (R325)
    replies = _r337_console_get("/sales/replies?limit=10")
    if replies:
        # Count replies in last 24h
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        recent = [r for r in replies.get("replies", [])
                  if (r.get("replied_at") or "") > cutoff]
        data["replies_24h"] = {
            "count": len(recent),
            "samples": [{"from": r.get("reply_from"),
                         "company": r.get("contact_company"),
                         "excerpt": (r.get("reply_excerpt") or "")[:120]}
                        for r in recent[:3]],
        }

    # Pending signups
    try:
        import sqlite3
        with sqlite3.connect(
                "/var/lib/murphy-tenants/murphy_tenants.db", timeout=3) as c:
            n_pending = c.execute(
                "SELECT COUNT(*) FROM pending_tenants WHERE status='pending'"
            ).fetchone()[0]
            recent_signups = c.execute(
                "SELECT desired_slug, legal_name, contact_email, created_at "
                "FROM pending_tenants WHERE status='pending' "
                "ORDER BY created_at DESC LIMIT 3"
            ).fetchall()
            n_tenants = c.execute(
                "SELECT COUNT(*) FROM tenants").fetchone()[0]
        data["signups"] = {
            "pending_count": n_pending,
            "total_tenants": n_tenants,
            "recent_pending": [
                {"slug": r[0], "name": r[1], "email": r[2], "at": r[3]}
                for r in recent_signups
            ],
        }
    except Exception:
        pass

    # ShieldWall blocks today
    try:
        import sqlite3
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        with sqlite3.connect(
                "/var/lib/murphy-tenants/murphy_tenants.db", timeout=3) as c:
            # quarantine_manifest table from R312
            try:
                n_blocked = c.execute(
                    "SELECT COUNT(*) FROM quarantine_manifest "
                    "WHERE quarantined_at >= ?", (cutoff,)
                ).fetchone()[0]
            except Exception:
                n_blocked = 0
        data["security"] = {"quarantined_24h": n_blocked}
    except Exception:
        pass

    return data


def _r337_format_extras(data):
    """Build the new brief sections from collected data."""
    lines = []

    # Substrate alert (only if degraded)
    sub = data.get("substrate", {})
    if sub.get("degraded"):
        lines.append("")
        lines.append("⚠ SUBSTRATE DEGRADED")
        lines.append(
            f"   Capacity gate reading {sub.get('staleness_hours','?')}h-old data."
        )
        lines.append(
            f"   Sees {sub.get('gate_cpu',0):.0f}% cpu | actual {sub.get('actual_cpu','?')}%."
        )
        lines.append("   Murphy LLM dispatch is gated. R333 memo has fix.")

    # Sales activity
    sales = data.get("sales", {})
    sc = data.get("send_controls", {})
    replies = data.get("replies_24h", {})
    lines.append("")
    lines.append("📤 SALES (last 24h)")
    paused = "⏸ PAUSED" if sc.get("paused") else "▶ active"
    lines.append(
        f"   Send controls: {paused} | sent today {sc.get('sends_today',0)}/{sc.get('daily_cap','?')}"
    )
    if replies.get("count", 0) > 0:
        lines.append(f"   ✓ {replies['count']} new prospect replies")
        for r in replies.get("samples", []):
            lines.append(f"     • {r['from']} ({r['company']}): {r['excerpt'][:80]}")
    else:
        lines.append("   No new prospect replies")

    # Automation diagnosis (R336)
    auto = data.get("automation", {})
    if auto.get("runs_seen", 0) > 0:
        lines.append("")
        lines.append("🔄 AUTOMATION (Sales Engine cron)")
        lines.append(
            f"   {auto.get('runs_seen')} runs analyzed | most common: {auto.get('most_common')}"
        )
        for diag, count in auto.get("diagnosis_counts", {}).items():
            lines.append(f"     {diag:35s} {count}x")

    # Signups
    su = data.get("signups", {})
    if su:
        lines.append("")
        lines.append("👤 SIGNUPS")
        lines.append(
            f"   {su.get('pending_count',0)} pending | {su.get('total_tenants',0)} total tenants"
        )
        for s in su.get("recent_pending", [])[:3]:
            lines.append(f"     • {s['slug']} ({s['name']}) — {s['email']}")

    # Security
    sec = data.get("security", {})
    if sec.get("quarantined_24h", 0) > 0:
        lines.append("")
        lines.append("🛡 SECURITY")
        lines.append(f"   {sec['quarantined_24h']} files quarantined in last 24h")

    return "\n".join(lines)



def fmt_confidence(val):
    try:
        pct = float(val) * 100 if float(val) <= 1 else float(val)
        if pct >= 80: emoji = "🟢"
        elif pct >= 60: emoji = "🟡"
        else: emoji = "🔴"
        return f"{emoji} {pct:.0f}%"
    except:
        return str(val)

def fmt_gates(gates_data):
    if not gates_data:
        return "No gate data"
    gates = gates_data.get("gates", gates_data)
    if isinstance(gates, list):
        open_g = sum(1 for g in gates if g.get("status") == "open")
        return f"{open_g}/{len(gates)} open"
    if isinstance(gates, dict):
        open_g = sum(1 for v in gates.values() if v in ("open", True))
        return f"{open_g}/{len(gates)} open"
    return str(gates_data)

def fmt_shield(shield_data):
    if not shield_data:
        return "—"
    layers = shield_data.get("active_layers", shield_data.get("layers_active", "?"))
    total  = shield_data.get("total_layers", 20)
    status = shield_data.get("status", "unknown")
    emoji  = "🟢" if str(status).lower() in ("active", "ok", "healthy") else "🟡"
    return f"{emoji} {layers}/{total} layers active"

def fmt_crm(crm_data):
    deals = crm_data.get("deals", crm_data) if isinstance(crm_data, dict) else crm_data
    if not isinstance(deals, list):
        return "No deal data"
    total = len(deals)
    total_val = sum(float(d.get("value", d.get("amount", 0)) or 0) for d in deals)
    # Stage breakdown
    stages = {}
    for d in deals:
        s = d.get("stage", d.get("status", "Unknown"))
        stages[s] = stages.get(s, 0) + 1
    stage_str = " · ".join(f"{v} {k}" for k, v in sorted(stages.items(), key=lambda x: -x[1])[:4])
    return f"{total} deals · ${total_val/1000:.0f}K total · {stage_str}"

def fmt_top_deals(crm_data, n=5):
    deals = crm_data.get("deals", crm_data) if isinstance(crm_data, dict) else crm_data
    if not isinstance(deals, list):
        return []
    sorted_deals = sorted(deals, key=lambda d: float(d.get("value", d.get("amount", 0)) or 0), reverse=True)
    out = []
    for d in sorted_deals[:n]:
        name  = d.get("company", d.get("name", "Unknown"))[:35]
        stage = d.get("stage", d.get("status", "?"))
        val   = float(d.get("value", d.get("amount", 0)) or 0)
        out.append((name, stage, val))
    return out

def fmt_signals(signals_data):
    events = signals_data.get("events", signals_data.get("feed", []))
    if not isinstance(events, list):
        return []
    return [e.get("message", e.get("text", str(e)))[:90] for e in events[:5] if e]

def fmt_agents(agents_data):
    agent_list = agents_data.get("agents", []) if isinstance(agents_data, dict) else []
    if not agent_list:
        return "Agent data unavailable"
    active = [a for a in agent_list if a.get("status") in ("active", "running", "ready")]
    return f"{len(active)}/{len(agent_list)} agents active"

# ── Build HTML email ──────────────────────────────────────────────────────────
def build_html(data):
    now_pt = datetime.now(timezone.utc).strftime("%A, %B %d, %Y — %I:%M %p UTC")
    mind   = data["mind"]
    
    confidence    = mind.get("confidence", mind.get("avg_confidence", "—"))
    cycle         = mind.get("cycle", mind.get("current_cycle", "—"))
    mind_status   = mind.get("status", "—")

    crm_summary   = fmt_crm(data["crm"])
    top_deals     = fmt_top_deals(data["crm"])
    gates_str     = fmt_gates(data["gates"])
    shield_str    = fmt_shield(data["shield"])
    conf_str      = fmt_confidence(confidence)
    agents_str    = fmt_agents(data["agents"])
    signals       = fmt_signals(data["signals"])

    # Executive summary from AI
    exec_result   = data["exec"]
    exec_text     = (exec_result.get("result") or
                     exec_result.get("output") or
                     exec_result.get("response") or
                     exec_result.get("summary") or
                     "Executive summary unavailable — check dashboard.")
    if isinstance(exec_text, dict):
        exec_text = exec_text.get("text", str(exec_text))

    # Top deals rows
    deal_rows = ""
    for name, stage, val in top_deals:
        deal_rows += f"""
        <tr>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;color:#e6edf3;">{name}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;color:#8b949e;">{stage}</td>
          <td style="padding:6px 10px;border-bottom:1px solid #21262d;color:#00d4ff;font-weight:700;">${val/1000:.1f}K</td>
        </tr>"""

    # Signals rows
    signal_rows = ""
    for s in signals:
        signal_rows += f'<li style="margin:4px 0;color:#8b949e;font-size:12px;">{s}</li>'
    if not signal_rows:
        signal_rows = '<li style="color:#484f58;">No signals logged overnight</li>'

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Murphy Morning Brief</title>
</head>
<body style="margin:0;padding:0;background:#0d1117;font-family:'Inter',system-ui,sans-serif;color:#e6edf3;">

  <!-- WRAPPER -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:32px 0;">
  <tr><td align="center">
  <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

    <!-- HEADER -->
    <tr>
      <td style="background:#161b22;border:1px solid #21262d;border-radius:8px 8px 0 0;padding:24px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#39d353;font-family:monospace;margin-bottom:6px;">● MURPHY SYSTEM — MORNING BRIEF</div>
              <div style="font-size:22px;font-weight:800;color:#e6edf3;letter-spacing:-0.5px;">Good morning, Corey.</div>
              <div style="font-size:13px;color:#8b949e;margin-top:4px;">{now_pt}</div>
            </td>
            <td align="right" style="vertical-align:top;">
              <div style="background:#00d4ff18;border:1px solid #00d4ff44;border-radius:6px;padding:10px 16px;text-align:center;">
                <div style="font-size:24px;font-weight:800;color:#00d4ff;">{conf_str}</div>
                <div style="font-size:10px;color:#8b949e;letter-spacing:1px;text-transform:uppercase;font-family:monospace;margin-top:3px;">Swarm Confidence</div>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- EXEC SUMMARY -->
    <tr>
      <td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:20px 28px 4px;">
        <div style="border-left:3px solid #00d4ff;padding-left:16px;">
          <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#484f58;font-family:monospace;margin-bottom:8px;">Murphy's Read</div>
          <div style="font-size:14px;line-height:1.7;color:#e6edf3;">{exec_text}</div>
        </div>
      </td>
    </tr>

    <!-- SYSTEM METRICS -->
    <tr>
      <td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:20px 28px;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#484f58;font-family:monospace;margin-bottom:14px;">System Status</div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="padding-bottom:12px;">
              <div style="font-size:11px;color:#8b949e;margin-bottom:2px;">Mind Cycle</div>
              <div style="font-size:18px;font-weight:700;color:#e6edf3;">{cycle:,}</div>
            </td>
            <td width="50%" style="padding-bottom:12px;">
              <div style="font-size:11px;color:#8b949e;margin-bottom:2px;">MFGC Gates</div>
              <div style="font-size:18px;font-weight:700;color:#e6edf3;">{gates_str}</div>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom:12px;">
              <div style="font-size:11px;color:#8b949e;margin-bottom:2px;">Shield</div>
              <div style="font-size:14px;font-weight:600;color:#e6edf3;">{shield_str}</div>
            </td>
            <td style="padding-bottom:12px;">
              <div style="font-size:11px;color:#8b949e;margin-bottom:2px;">Active Agents</div>
              <div style="font-size:14px;font-weight:600;color:#e6edf3;">{agents_str}</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- DIVIDER -->
    <tr><td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:0 28px;"><div style="border-top:1px solid #21262d;"></div></td></tr>

    <!-- CRM PIPELINE -->
    <tr>
      <td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:20px 28px;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#484f58;font-family:monospace;margin-bottom:4px;">CRM Pipeline</div>
        <div style="font-size:12px;color:#8b949e;margin-bottom:14px;">{crm_summary}</div>
        <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #21262d;border-radius:6px;overflow:hidden;">
          <tr style="background:#161b22;">
            <th style="padding:8px 10px;text-align:left;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#484f58;font-weight:700;font-family:monospace;">Company</th>
            <th style="padding:8px 10px;text-align:left;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#484f58;font-weight:700;font-family:monospace;">Stage</th>
            <th style="padding:8px 10px;text-align:left;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#484f58;font-weight:700;font-family:monospace;">Value</th>
          </tr>
          {deal_rows}
        </table>
      </td>
    </tr>

    <!-- DIVIDER -->
    <tr><td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:0 28px;"><div style="border-top:1px solid #21262d;"></div></td></tr>

    <!-- OVERNIGHT SIGNALS -->
    <tr>
      <td style="background:#0d1117;border-left:1px solid #21262d;border-right:1px solid #21262d;padding:20px 28px;">
        <div style="font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#484f58;font-family:monospace;margin-bottom:12px;">Recent Swarm Activity</div>
        <ul style="margin:0;padding:0;list-style:none;">
          {signal_rows}
        </ul>
      </td>
    </tr>

    <!-- CTA -->
    <tr>
      <td style="background:#161b22;border:1px solid #21262d;border-top:none;border-radius:0 0 8px 8px;padding:20px 28px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <div style="font-size:12px;color:#8b949e;">Open the full dashboard to dispatch tasks, review the pipeline, or check HITL interventions.</div>
            </td>
            <td align="right">
              <a href="https://murphy.systems/static/murphy-os.html" style="display:inline-block;background:#00d4ff;color:#0d1117;font-weight:700;font-size:12px;padding:10px 18px;border-radius:5px;text-decoration:none;white-space:nowrap;">Open Murphy OS →</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- FOOTER -->
    <tr>
      <td style="padding:16px 0;text-align:center;">
        <div style="font-size:11px;color:#484f58;font-family:monospace;">murphy.systems · autonomous ops · generated {now_pt}</div>
      </td>
    </tr>

  </table>
  </td></tr>
  </table>

</body>
</html>"""
    return html

def build_text(data):
    """Plain text fallback."""
    now_pt = datetime.now(timezone.utc).strftime("%A %B %d %Y %I:%M %p UTC")
    mind   = data["mind"]
    confidence = mind.get("confidence", mind.get("avg_confidence", "—"))
    cycle      = mind.get("cycle", mind.get("current_cycle", "—"))
    gates_str  = fmt_gates(data["gates"])
    shield_str = fmt_shield(data["shield"])
    conf_str   = fmt_confidence(confidence)
    crm_str    = fmt_crm(data["crm"])
    top_deals  = fmt_top_deals(data["crm"])
    signals    = fmt_signals(data["signals"])
    exec_result= data["exec"]
    exec_text  = (exec_result.get("result") or exec_result.get("output") or
                  exec_result.get("response") or exec_result.get("summary") or
                  "Executive summary unavailable.")

    deals_txt = "\n".join(f"  {n} | {s} | ${v/1000:.1f}K" for n,s,v in top_deals)
    signals_txt = "\n".join(f"  → {s}" for s in signals) or "  No signals."

    return f"""MURPHY MORNING BRIEF — {now_pt}
{'='*60}

MURPHY'S READ
{exec_text}

SYSTEM STATUS
  Swarm Confidence : {conf_str}
  Mind Cycle       : {cycle}
  MFGC Gates       : {gates_str}
  Shield           : {shield_str}

CRM PIPELINE
  {crm_str}

TOP DEALS
{deals_txt}

RECENT SWARM ACTIVITY
{signals_txt}

---
Open Murphy OS: https://murphy.systems/static/murphy-os.html
"""

# ── Send email ────────────────────────────────────────────────────────────────
def send_brief(html_body, text_body):
    today = datetime.now(timezone.utc).strftime("%b %d")
    subject = f"Murphy Morning Brief — {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Murphy System <{FROM_EMAIL}>"
    msg["To"]      = ", ".join(RECIPIENTS)

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body,  "html"))

    print(f"Connecting to {SMTP_HOST}:{SMTP_PORT} (STARTTLS)...")
    # R327: SMTP block replaced by sendmail

    _msg_to_send = msg if 'msg' in dir() else None

    if _msg_to_send is not None:

        _ok, _err = _send_via_sendmail(_msg_to_send, RECIPIENTS)

        if not _ok:

            print(f'  WARN: {_err}')
    print(f"✅ Brief sent to: {', '.join(RECIPIENTS)}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Murphy Morning Brief — {datetime.now(timezone.utc).isoformat()}")
    print("─" * 50)

    data      = collect_data()
    html_body = build_html(data)
    text_body = build_text(data)

    print("\nSending email...")
    try:
        send_brief(html_body, text_body)
    except Exception as e:
        print(f"❌ Send failed: {e}")
        print("Trying port 587 fallback...")
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode    = ssl.CERT_NONE
            # R327: SMTP block replaced by sendmail

            _msg_to_send = msg if 'msg' in dir() else None

            if _msg_to_send is not None:

                _ok, _err = _send_via_sendmail(_msg_to_send, RECIPIENTS)

                if not _ok:

                    print(f'  WARN: {_err}')
                msg_str = html_body  # reuse msg object
                today = datetime.now(timezone.utc).strftime("%b %d")
                from email.mime.multipart import MIMEMultipart
                from email.mime.text import MIMEText
                msg2 = MIMEMultipart("alternative")
                msg2["Subject"] = f"Murphy Morning Brief — {today}"
                msg2["From"]    = f"Murphy System <{SMTP_USER}>"
                msg2["To"]      = ", ".join(RECIPIENTS)
                msg2.attach(MIMEText(text_body, "plain"))
                msg2.attach(MIMEText(html_body,  "html"))
                server.sendmail(SMTP_USER, RECIPIENTS, msg2.as_string())
            print(f"✅ Brief sent (587 fallback) to: {', '.join(RECIPIENTS)}")
        except Exception as e2:
            print(f"❌ Both ports failed: {e2}")
            raise

    print("\nDone.")
