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
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL      = "http://127.0.0.1:8000"
API_KEY       = os.getenv("MURPHY_API_KEY", "Sputnik12!")
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
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, RECIPIENTS, msg.as_string())
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
            with smtplib.SMTP(SMTP_HOST, 587) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASS)
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
