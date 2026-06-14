"""
Ship 31bp — public compliance pages.

Per Murphy direction: concise, factual, not legal boilerplate.
Three pages:
  /privacy            — GDPR/CCPA disclosure + how to exercise rights
  /breach-notification — GDPR Art.33 72h runbook (public-facing summary)
  /sub-processors      — list of third parties + what data they touch

Visual: Murphy landing aesthetic (cyan #00d4aa + dark #0d1117 + Inter).
"""
from datetime import datetime, timezone

POSTAL = "Inoni LLC · 7805 SE 70th Ave · Portland, OR 97206 · USA"
CONTACT_EMAIL = "privacy@murphy.systems"

# Sub-processor list — every third party that touches tenant data
SUB_PROCESSORS = [
    {
        "name":    "Together AI",
        "purpose": "LLM inference for tenant queries and email replies",
        "data":    "Prompt content (sender name, subject, body excerpt)",
        "location": "USA",
        "dpa_url": "https://www.together.ai/legal/privacy",
    },
    {
        "name":    "NOWPayments",
        "purpose": "Crypto payment processing",
        "data":    "Email + amount + crypto wallet (when tenant pays)",
        "location": "Netherlands (EU)",
        "dpa_url": "https://nowpayments.io/privacy-policy",
    },
    {
        "name":    "Twilio",
        "purpose": "SMS for HITL founder approval prompts (founder only)",
        "data":    "Founder phone number + approval text",
        "location": "USA",
        "dpa_url": "https://www.twilio.com/legal/privacy",
    },
    {
        "name":    "Hetzner",
        "purpose": "Infrastructure hosting (servers + storage)",
        "data":    "All Murphy data at rest (encrypted in transit; SQLite at rest)",
        "location": "Germany (EU)",
        "dpa_url": "https://www.hetzner.com/legal/privacy-policy",
    },
    {
        "name":    "GitHub",
        "purpose": "Source code repository (no tenant data)",
        "data":    "Murphy code only — no tenant or PII",
        "location": "USA",
        "dpa_url": "https://docs.github.com/site-policy/privacy-policies/github-privacy-statement",
    },
]


def _shell(title: str, body_html: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>{title} · Murphy</title>
<style>
:root {{ --bg:#0d1117; --bg2:#131920; --bg3:#161b22; --border:#21262d;
        --text:#e6edf3; --text2:#8b949e; --text3:#484f58; --live:#00d4aa; }}
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif;
       font-size:14px; line-height:1.7; min-height:100vh }}
.wrap {{ max-width:760px; margin:0 auto; padding:60px 24px }}
.head {{ display:flex; justify-content:space-between; align-items:center;
        margin-bottom:48px; padding-bottom:20px; border-bottom:1px solid var(--border) }}
.brand {{ display:flex; align-items:center; gap:12px }}
.eye {{ width:36px; height:36px; border-radius:50%; border:1px solid var(--live);
       display:flex; align-items:center; justify-content:center; color:var(--live);
       font-weight:700 }}
.brand a {{ color:var(--text); text-decoration:none; font-weight:600 }}
.head .nav {{ font-size:12px; color:var(--text2) }}
.head .nav a {{ color:var(--text2); margin-left:18px; text-decoration:none }}
.head .nav a:hover {{ color:var(--live) }}
h1 {{ font-size:32px; font-weight:700; margin-bottom:8px }}
.lede {{ color:var(--text2); font-size:15px; margin-bottom:36px }}
h2 {{ font-size:18px; font-weight:700; margin-top:36px; margin-bottom:12px;
     padding-bottom:8px; border-bottom:1px solid var(--border) }}
h3 {{ font-size:14px; font-weight:600; margin-top:20px; margin-bottom:8px;
     color:var(--live); letter-spacing:0.5px }}
p {{ margin-bottom:14px; color:var(--text) }}
ul, ol {{ margin-left:22px; margin-bottom:16px }}
li {{ margin-bottom:6px }}
a {{ color:var(--live); text-decoration:none }}
a:hover {{ text-decoration:underline }}
code {{ background:var(--bg3); padding:2px 6px; border-radius:3px;
       font-family:ui-monospace,monospace; font-size:13px; color:var(--live) }}
.callout {{ background:var(--bg2); border-left:3px solid var(--live);
           padding:16px 20px; border-radius:4px; margin:20px 0; font-size:13px }}
table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:13px }}
th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--border);
         vertical-align:top }}
th {{ font-weight:600; color:var(--text2); font-size:11px;
      letter-spacing:1.5px; text-transform:uppercase }}
.foot {{ margin-top:60px; padding-top:24px; border-top:1px solid var(--border);
        font-size:11px; color:var(--text3); text-align:center }}
</style></head><body>
<div class="wrap">
<div class="head">
  <div class="brand"><div class="eye">M</div><a href="/">Murphy</a></div>
  <div class="nav">
    <a href="/privacy">Privacy</a>
    <a href="/sub-processors">Sub-processors</a>
    <a href="/breach-notification">Breach policy</a>
  </div>
</div>
{body_html}
<div class="foot">{POSTAL} · Last updated {today} · Privacy questions: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>
</div></body></html>'''


def privacy_html() -> str:
    body = '''<h1>Privacy</h1>
<div class="lede">What Murphy stores, why, and how to get it back or delete it.</div>

<h2>What we collect</h2>
<p>Murphy holds three categories of data about you.</p>
<ol>
  <li><b>Account info.</b> Email address, tenant name, billing email when you sign up.</li>
  <li><b>Email content.</b> Subject, sender, recipient, body preview (first ~500 chars) of messages you send to murphy@murphy.systems or that Murphy sends on your behalf. Full bodies are not retained long-term.</li>
  <li><b>Usage.</b> LLM call counts, plan tier, retention status. No browsing history, no cross-site tracking, no advertising IDs.</li>
</ol>

<h2>Why we collect it</h2>
<ul>
  <li>To send the replies you asked Murphy to send.</li>
  <li>To remember context across your conversations.</li>
  <li>To bill you accurately (paid plans only).</li>
  <li>To detect abuse and stay legal (audit logs).</li>
</ul>

<h2>Your rights</h2>
<p>Every tenant has these rights regardless of jurisdiction. We honor them within hours, not the 30-day legal maximum.</p>
<table>
<tr><th>Right</th><th>How to exercise</th><th>Backed by law</th></tr>
<tr><td>Know what we hold</td><td><code>GET /api/me/export</code> downloads everything as JSON</td><td>CCPA · GDPR Art.15</td></tr>
<tr><td>Get a portable copy</td><td>Same endpoint; the export is standard JSON</td><td>GDPR Art.20</td></tr>
<tr><td>Delete everything</td><td><code>POST /api/me/delete</code> with confirmation header</td><td>CCPA · GDPR Art.17</td></tr>
<tr><td>Stop emails</td><td>Click "Unsubscribe" in any Murphy email · zero-day grace</td><td>CAN-SPAM · GDPR Art.21</td></tr>
<tr><td>Correct an error</td><td>Email <a href="mailto:''' + CONTACT_EMAIL + '''">''' + CONTACT_EMAIL + '''</a></td><td>GDPR Art.16</td></tr>
</table>

<h2>Retention</h2>
<p>Email threads with no reply for 5 business days are marked for deletion. Marked threads are permanently deleted 10 days later unless you reply (the reply re-activates the thread automatically). You can also click "Keep alive" on any marked thread.</p>

<h2>Who else sees your data</h2>
<p>Five sub-processors. See the <a href="/sub-processors">sub-processor list</a> for what each one touches and why.</p>

<h2>Do Not Sell</h2>
<p>Murphy does not sell personal data, period. There is nothing to opt out of because nothing is for sale. If you want a formal record of that fact, email <a href="mailto:''' + CONTACT_EMAIL + '''">''' + CONTACT_EMAIL + '''</a> and we will log it.</p>

<h2>If something goes wrong</h2>
<p>If a breach affects your data, we notify you within 72 hours by email per GDPR Art.33. See the <a href="/breach-notification">breach notification policy</a> for the runbook.</p>

<div class="callout">
This page is not legal boilerplate. It is a contract about how we behave. If we change it, we keep the old version in git so you can compare. Source: <a href="https://github.com/IKNOWINOT/Murphy-System">github.com/IKNOWINOT/Murphy-System</a>.
</div>
'''
    return _shell("Privacy", body)


def breach_html() -> str:
    body = '''<h1>Breach notification policy</h1>
<div class="lede">GDPR Art.33: 72-hour notification. Here is the runbook.</div>

<h2>What counts as a breach</h2>
<p>Any event where personal data was accessed, lost, altered, or disclosed without authorization. Examples:</p>
<ul>
  <li>Database file accessed by someone outside Inoni LLC.</li>
  <li>Tenant data accidentally sent to wrong recipient (>1 tenant affected).</li>
  <li>Sub-processor (Together AI, NOWPayments, etc.) reports an incident affecting their service.</li>
  <li>Credentials leaked publicly (e.g., GitHub commit with secret).</li>
</ul>

<h2>Hour 0 — Detection</h2>
<ol>
  <li>Whoever detects it (founder, automated audit, sub-processor notice) writes a one-line note to <code>/var/log/breach_<i>YYYY-MM-DD</i>.log</code>.</li>
  <li>Founder notified by SMS within 15 minutes.</li>
</ol>

<h2>Hour 0-6 — Contain</h2>
<ol>
  <li>Rotate any compromised credentials immediately.</li>
  <li>Freeze the affected service if necessary (set capacity gate to 0).</li>
  <li>Snapshot the affected database to <code>/var/backups/</code> for forensics.</li>
</ol>

<h2>Hour 6-24 — Assess</h2>
<ol>
  <li>Identify which tenants are affected (query inbound_replies / billing_records).</li>
  <li>Identify which data categories (email content, billing, account info).</li>
  <li>Identify whether the breach is ongoing or contained.</li>
</ol>

<h2>Hour 24-72 — Notify</h2>
<ol>
  <li><b>Tenants:</b> direct email from <code>privacy@murphy.systems</code> describing what happened, what data was affected, what we are doing, and what they should do.</li>
  <li><b>Supervisory authority:</b> for EU residents, file the breach with the relevant DPA within 72 hours of detection. We use the Irish DPC as our lead authority since most of our EU traffic is Irish-hosted via Hetzner.</li>
  <li><b>Public statement:</b> we publish a brief incident report at /incidents/<date> within 7 days. We do not hide breaches.</li>
</ol>

<h2>What we owe you</h2>
<p>If your data was affected, we will tell you. We will not bury it in a paragraph 14 of a 30-page legal document. Plain language, full disclosure, fast.</p>

<div class="callout">
We have not had a breach. This page is the runbook for if we do. Last drilled: never (still pre-launch). First drill scheduled: within 30 days of first paid customer.
</div>
'''
    return _shell("Breach notification", body)


def sub_processors_html() -> str:
    rows = ""
    for sp in SUB_PROCESSORS:
        rows += f'''<tr>
  <td><b>{sp["name"]}</b><br><span style="color:var(--text2);font-size:12px">{sp["location"]}</span></td>
  <td>{sp["purpose"]}</td>
  <td><span style="color:var(--text2)">{sp["data"]}</span></td>
  <td><a href="{sp["dpa_url"]}" target="_blank" rel="noopener">Privacy policy ↗</a></td>
</tr>'''
    body = f'''<h1>Sub-processors</h1>
<div class="lede">Every third-party service that touches Murphy data, what they see, and why.</div>

<h2>Current list ({len(SUB_PROCESSORS)} sub-processors)</h2>
<table>
<tr><th>Vendor</th><th>Purpose</th><th>Data they see</th><th>Their policy</th></tr>
{rows}
</table>

<h2>Our commitments</h2>
<ul>
  <li>Every sub-processor has a published privacy policy (linked above).</li>
  <li>We do not add a new sub-processor without updating this list first.</li>
  <li>We do not sell data to any party, including these sub-processors.</li>
  <li>Each sub-processor only receives the minimum data needed for its purpose.</li>
</ul>

<h2>How to be notified of changes</h2>
<p>Subscribe to the changelog: this page's revision history is in git at <a href="https://github.com/IKNOWINOT/Murphy-System">github.com/IKNOWINOT/Murphy-System</a>. We commit every change. Watch the repo to be notified.</p>

<div class="callout">
For enterprise customers who need a signed Data Processing Agreement (DPA) with sub-processor flow-through clauses, contact <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We can sign the standard EU DPA template.
</div>
'''
    return _shell("Sub-processors", body)
