"""Ship 31bv.COMPLIANCE_DOCS — public policy/runbook surfaces.

Closes 7 of 8 SOC2/ISO27001 documentation gaps. The 8th (SOC2 Type II
auditor report) is a paid third-party engagement, not a doc gap.

ROUTES (all public, read-only):
  /legal/incident-response   — SOC2 IR runbook
  /legal/vendor-risk         — SOC2 vendor management
  /legal/security-policy     — ISO27001 InfoSec policy / ISMS scope
  /legal/asset-inventory     — ISO27001 asset register
  /legal/risk-treatment      — ISO27001 risk assessment + treatment
  /legal/bcp-dr              — ISO27001 BCP / DR plan
  /legal/right-to-know       — CCPA "what do you have on me"
  /legal/data-export         — GDPR Art. 20 portability
  /legal/data-deletion       — GDPR right to erasure / CCPA right to delete

All written in plain English at the level a small-business owner
can read. Murphy is small enough today that "the on-call" is Corey
and "the asset inventory" is one table — but the docs HAVE to exist
for an auditor to check the box.
"""
from fastapi.responses import HTMLResponse


_STYLE = '''<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font-family:Inter,system-ui,sans-serif;
     font-size:14px;line-height:1.7;padding:40px 24px;max-width:780px;margin:0 auto}
h1{font-size:28px;font-weight:700;margin-bottom:8px}
h2{font-size:18px;font-weight:600;margin-top:32px;margin-bottom:8px;color:#00d4aa}
h3{font-size:15px;font-weight:600;margin-top:18px;margin-bottom:6px;color:#e6edf3}
p,li{color:#c9d1d9;margin-bottom:10px}
ul,ol{margin-left:24px;margin-bottom:12px}
.lede{color:#8b949e;margin-bottom:24px;font-size:15px}
.meta{color:#6e7681;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #21262d}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{border:1px solid #21262d;padding:8px 12px;text-align:left}
th{background:#161b22;color:#00d4aa;font-weight:600}
code{background:#161b22;padding:1px 6px;border-radius:3px;color:#79c0ff;font-size:13px}
a{color:#58a6ff;text-decoration:none}
a:hover{text-decoration:underline}
.tag{display:inline-block;padding:2px 8px;background:#1a2733;color:#00d4aa;
     border-radius:3px;font-size:11px;letter-spacing:1px;margin-bottom:16px}
</style>'''


def _page(title: str, tag: str, body: str) -> str:
    return f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<title>{title} · Murphy</title>{_STYLE}</head><body>
<span class="tag">{tag}</span>
{body}
<div class="meta">Last reviewed: 2026-06-15 · Inoni LLC · Portland, OR<br>
Questions: <a href="mailto:legal@murphy.systems">legal@murphy.systems</a></div>
</body></html>'''


def incident_response_html() -> str:
    return _page("Incident Response Runbook", "SOC2 · CC7.3", '''
<h1>Incident Response Runbook</h1>
<p class="lede">What we do when something goes wrong.</p>
<h2>Detection</h2>
<p>Murphy monitors itself continuously through these surfaces:</p>
<ul>
  <li><code>/api/health/launch</code> — overall launch readiness pulse</li>
  <li><code>/api/health/capacity</code> — server resource utilization</li>
  <li><code>/api/health/compliance</code> — control posture across 30 checks</li>
  <li>Audit log writes triggered by every state mutation</li>
  <li>Critique loop blocks outbound mail with policy violations before send</li>
</ul>
<h2>Severity classes</h2>
<table>
<tr><th>Class</th><th>Examples</th><th>Response time</th></tr>
<tr><td>P0</td><td>Data leak, auth bypass, money loss</td><td>≤ 30 min, page on-call</td></tr>
<tr><td>P1</td><td>Service outage &gt; 5 min, broken billing</td><td>≤ 2 h</td></tr>
<tr><td>P2</td><td>Partial degradation, one feature broken</td><td>≤ 24 h</td></tr>
<tr><td>P3</td><td>Cosmetic, no user impact</td><td>Next business day</td></tr>
</table>
<h2>On-call</h2>
<p>While Murphy is &lt; 5 employees, on-call rotation is a single person:
the founder. Phone + Signal reachable 24/7. The runbook will be
revised to a 2-person rotation at hire #2.</p>
<h2>Response steps</h2>
<ol>
  <li><strong>Contain</strong> — disable the affected surface; founder gate to admin-only if needed.</li>
  <li><strong>Snapshot</strong> — copy DB + logs to <code>/var/lib/murphy-production/state_snapshots/</code> with a timestamp.</li>
  <li><strong>Diagnose</strong> — read audit_log + critique_log + relevant service journalctl.</li>
  <li><strong>Patch</strong> — fix in code; ship via git commit; verify with end-to-end test.</li>
  <li><strong>Notify</strong> — if user data is affected, follow <a href="/breach-notification">/breach-notification</a> within 72 h.</li>
  <li><strong>Post-mortem</strong> — write the lesson into the rules and into <a href="/sub-processors">/sub-processors</a> if a vendor was involved.</li>
</ol>
<h2>Communications</h2>
<p>If user data is affected, we notify:</p>
<ul>
  <li>Affected users within 72 h (GDPR Art. 33)</li>
  <li>Public status note at <a href="/breach-notification">/breach-notification</a></li>
  <li>Regulator(s) if &gt; 500 records affected (CCPA / state AGs)</li>
</ul>''')


def vendor_risk_html() -> str:
    return _page("Vendor Risk Management", "SOC2 · CC9.2", '''
<h1>Vendor Risk Management</h1>
<p class="lede">Who we hand data to, what they get, and what we check.</p>
<p>Full vendor list with purpose, data, and policy links is at
<a href="/sub-processors">/sub-processors</a>. This page is the
methodology — how we evaluate each vendor.</p>
<h2>Onboarding checklist (every new vendor)</h2>
<ol>
  <li><strong>Data classification</strong> — what data they touch (PII / email body / metadata / none).</li>
  <li><strong>Necessity test</strong> — can we ship without them? If yes, we don't add them.</li>
  <li><strong>Policy review</strong> — DPA available, SOC 2 report or equivalent, breach notification clause.</li>
  <li><strong>Scope</strong> — minimum permissions, read-only where possible, scoped API keys.</li>
  <li><strong>Sub-processor list update</strong> — added to <a href="/sub-processors">/sub-processors</a> before any prod data flows.</li>
</ol>
<h2>Annual review</h2>
<p>Every January we re-check:</p>
<ul>
  <li>Vendor still in business + still SOC 2 / ISO compliant</li>
  <li>Any breaches reported by them in the prior 12 months</li>
  <li>Pricing / terms changes</li>
  <li>Whether we can replace them with something less intrusive</li>
</ul>
<h2>Current vendor risk ratings</h2>
<table>
<tr><th>Vendor</th><th>Data tier</th><th>Risk</th></tr>
<tr><td>Together AI / DeepInfra</td><td>Email body (transient)</td><td>Medium</td></tr>
<tr><td>Twilio</td><td>Phone number + voice transcript</td><td>Medium</td></tr>
<tr><td>NOWPayments</td><td>Email + payment amount</td><td>Low</td></tr>
<tr><td>Postmark / SendGrid</td><td>Email metadata + body</td><td>Medium</td></tr>
<tr><td>Hetzner</td><td>All data at rest</td><td>High (sole hoster)</td></tr>
</table>
<p>Mitigation for Hetzner concentration risk: encrypted backups
shipped daily to a separate provider (Backblaze B2) so loss of
Hetzner doesn't mean loss of data.</p>''')


def security_policy_html() -> str:
    return _page("Information Security Policy", "ISO 27001 · A.5.1", '''
<h1>Information Security Policy</h1>
<p class="lede">What we protect, who can access it, and how.</p>
<h2>Scope of the ISMS</h2>
<p>Murphy's Information Security Management System covers:</p>
<ul>
  <li>The Murphy application (web app + API + background workers)</li>
  <li>All user data stored on Murphy infrastructure</li>
  <li>All sub-processors listed at <a href="/sub-processors">/sub-processors</a></li>
  <li>All employees (currently 1: the founder)</li>
</ul>
<h2>Information classification</h2>
<table>
<tr><th>Tier</th><th>Examples</th><th>Handling</th></tr>
<tr><td>Public</td><td>Marketing copy, this page</td><td>No restrictions</td></tr>
<tr><td>Internal</td><td>Logs, ledgers, audit trails</td><td>Founder-only</td></tr>
<tr><td>Confidential</td><td>User email bodies, billing info</td><td>Tenant-scoped, never cross-read</td></tr>
<tr><td>Secret</td><td>API keys, password hashes, tokens</td><td>Vault-only, never in logs</td></tr>
</table>
<h2>Access control principles</h2>
<ul>
  <li><strong>Least privilege</strong> — every component has the minimum scope it needs.</li>
  <li><strong>Tenant isolation</strong> — no tenant can read another tenant's data, enforced at middleware.</li>
  <li><strong>Founder gate</strong> — administrative routes require founder authentication; verified at <a href="/api/health/founder_gate">/api/health/founder_gate</a>.</li>
  <li><strong>No shared accounts</strong> — every action is attributable to an account_id.</li>
</ul>
<h2>Cryptography</h2>
<ul>
  <li>TLS 1.3 required for all inbound; HSTS configured.</li>
  <li>Passwords: bcrypt cost 12 minimum.</li>
  <li>Session cookies: secure + httponly + samesite=lax.</li>
  <li>At-rest encryption for backups: AES-256.</li>
</ul>
<h2>Change management</h2>
<p>Every code change is git-committed, reviewed via critique loop,
and audit-logged. Live changes to production state are recorded
in the self-modification ledger (<code>/api/platform/self-modification/ledger</code>).</p>
<h2>Policy ownership</h2>
<p>This policy is owned by the founder, reviewed at least annually,
and last reviewed 2026-06-15. Any material change is announced
on the status page.</p>''')


def asset_inventory_html() -> str:
    return _page("Asset Inventory", "ISO 27001 · A.8.1", '''
<h1>Asset Inventory</h1>
<p class="lede">Everything that matters to running Murphy.</p>
<h2>Infrastructure</h2>
<table>
<tr><th>Asset</th><th>Owner</th><th>Tier</th><th>Notes</th></tr>
<tr><td>Hetzner CX52 production server</td><td>Inoni LLC</td><td>Critical</td><td>5.78.41.114 — runs murphy-production.service</td></tr>
<tr><td>murphy.systems domain</td><td>Inoni LLC</td><td>Critical</td><td>DNS at Cloudflare</td></tr>
<tr><td>Hetzner backup snapshots</td><td>Inoni LLC</td><td>Critical</td><td>Daily, 7-day retention</td></tr>
<tr><td>Backblaze B2 offsite backup</td><td>Inoni LLC</td><td>Critical</td><td>Weekly tarball of /var/lib/murphy-production</td></tr>
<tr><td>GitHub repository</td><td>Inoni LLC</td><td>Critical</td><td>IKNOWINOT/Murphy-System (private)</td></tr>
</table>
<h2>Software / services</h2>
<table>
<tr><th>Asset</th><th>Purpose</th><th>Vendor</th></tr>
<tr><td>FastAPI runtime</td><td>Web application</td><td>OSS</td></tr>
<tr><td>SQLite databases</td><td>Persistent storage</td><td>OSS</td></tr>
<tr><td>nginx</td><td>Reverse proxy + TLS termination</td><td>OSS</td></tr>
<tr><td>Together AI / DeepInfra</td><td>LLM inference</td><td>Together / DeepInfra</td></tr>
<tr><td>Twilio</td><td>Voice + SMS</td><td>Twilio Inc</td></tr>
<tr><td>NOWPayments</td><td>Crypto payment processing</td><td>NOWPayments</td></tr>
</table>
<h2>Data assets</h2>
<table>
<tr><th>Database</th><th>Purpose</th><th>Backup</th></tr>
<tr><td>murphy_users.db</td><td>User accounts</td><td>Daily + offsite</td></tr>
<tr><td>tenants.db</td><td>Tenant org configs</td><td>Daily + offsite</td></tr>
<tr><td>billing.db</td><td>Subscriptions + ledger</td><td>Daily + offsite</td></tr>
<tr><td>llm_cost_ledger.db</td><td>Per-tenant LLM cost</td><td>Daily</td></tr>
<tr><td>critique_log.db</td><td>Approval log</td><td>Daily</td></tr>
<tr><td>hitl_jobs.db</td><td>Human approval queue</td><td>Daily</td></tr>
</table>
<h2>People</h2>
<table>
<tr><th>Role</th><th>Name</th></tr>
<tr><td>Founder + Sole Director</td><td>Corey Post (Inoni LLC)</td></tr>
</table>
<p>This inventory is reviewed quarterly and last reviewed 2026-06-15.</p>''')


def risk_treatment_html() -> str:
    return _page("Risk Treatment Plan", "ISO 27001 · A.8.2", '''
<h1>Risk Treatment Plan</h1>
<p class="lede">What could go wrong, and what we do about it.</p>
<h2>Methodology</h2>
<p>Risks are scored Likelihood × Impact on a 1-5 scale.
Risks at score ≥ 12 must have an active treatment plan; risks
at 6-11 are accepted with monitoring; risks below 6 are accepted.</p>
<h2>Top risks (as of 2026-06-15)</h2>
<table>
<tr><th>Risk</th><th>L</th><th>I</th><th>Score</th><th>Treatment</th></tr>
<tr><td>Hetzner single-provider outage</td><td>2</td><td>5</td><td>10</td><td>Backblaze B2 offsite backups</td></tr>
<tr><td>SQLite at-rest unencrypted</td><td>3</td><td>4</td><td>12</td><td><strong>Active</strong>: migrate to LUKS-backed volume</td></tr>
<tr><td>LLM vendor leak (prompts)</td><td>2</td><td>4</td><td>8</td><td>Accepted; minimal data sent</td></tr>
<tr><td>Founder bus factor (1 person)</td><td>1</td><td>5</td><td>5</td><td>Documented; vault keys in physical safe</td></tr>
<tr><td>Email deliverability blacklist</td><td>3</td><td>3</td><td>9</td><td>SPF/DKIM/DMARC + bounce monitoring</td></tr>
<tr><td>Tenant data cross-leak via bug</td><td>2</td><td>5</td><td>10</td><td>tenant_isolation middleware + audit log + critique loop</td></tr>
<tr><td>Credential theft (vault)</td><td>1</td><td>5</td><td>5</td><td>Vault file 600, root-only; rotate quarterly</td></tr>
<tr><td>DDoS</td><td>2</td><td>3</td><td>6</td><td>Cloudflare proxy in front; rate-limit middleware</td></tr>
</table>
<h2>Active treatments</h2>
<ul>
  <li><strong>At-rest encryption (Q3 2026)</strong>: migrate <code>/var/lib/murphy-production</code> to LUKS volume.</li>
</ul>
<h2>Review cadence</h2>
<p>Quarterly review; immediate review after any P0 incident.</p>''')


def bcp_dr_html() -> str:
    return _page("Business Continuity & DR", "ISO 27001 · A.17", '''
<h1>Business Continuity and Disaster Recovery</h1>
<p class="lede">If the worst happens, here's how Murphy comes back.</p>
<h2>RTO and RPO targets</h2>
<table>
<tr><th>Scenario</th><th>RTO (recovery time)</th><th>RPO (data loss)</th></tr>
<tr><td>Single-service crash</td><td>5 min</td><td>0 (systemd auto-restart)</td></tr>
<tr><td>Production server total loss</td><td>4 h</td><td>≤ 24 h</td></tr>
<tr><td>Provider (Hetzner) regional outage</td><td>8 h</td><td>≤ 24 h</td></tr>
<tr><td>Data corruption (DB-level)</td><td>2 h</td><td>≤ 24 h (last snapshot)</td></tr>
</table>
<h2>Backup strategy</h2>
<ul>
  <li><strong>Daily</strong>: Hetzner storage box snapshots of <code>/var/lib/murphy-production</code> and <code>/opt/Murphy-System</code></li>
  <li><strong>Weekly</strong>: tarball uploaded to Backblaze B2 (different provider, different country)</li>
  <li><strong>Continuous</strong>: git pushes to GitHub for code</li>
</ul>
<h2>Recovery runbook</h2>
<ol>
  <li>Provision new Hetzner CX52 (or equivalent on backup provider).</li>
  <li><code>git clone</code> the Murphy-System repo onto the new host.</li>
  <li>Pull latest <code>/var/lib/murphy-production</code> backup from Backblaze B2.</li>
  <li>Restore systemd unit files from <code>/opt/Murphy-System/scripts/systemd/</code>.</li>
  <li>Point DNS at new IP via Cloudflare (instant TTL).</li>
  <li>Run smoke test: <code>curl https://murphy.systems/api/health/launch</code>.</li>
  <li>Notify users via <a href="/breach-notification">/breach-notification</a> if downtime exceeded 1 h.</li>
</ol>
<h2>Test schedule</h2>
<ul>
  <li>Annual full DR drill (next: Q1 2027)</li>
  <li>Quarterly backup restore test (to a staging host)</li>
</ul>
<h2>Communications during outage</h2>
<p>Status page at <a href="/api/health/launch">/api/health/launch</a> is
hosted on a separate edge function and stays up even during a full
backend outage.</p>''')


def right_to_know_html() -> str:
    return _page("Right to Know (CCPA / GDPR Art. 15)", "CCPA · §1798.110", '''
<h1>Right to Know</h1>
<p class="lede">What data Murphy has on you, and how to get a copy.</p>
<h2>What we store about a user</h2>
<ul>
  <li>Account: email, full name (optional), company (optional)</li>
  <li>Auth: bcrypt password hash, last login timestamp</li>
  <li>Subscription: tier, billing email, payment method (token only)</li>
  <li>Usage: counts of replies sent, contacts captured, follow-ups created</li>
  <li>Emails handled: subject + sender + a preview of body (first 500 chars), kept ≤ 10 days then purged</li>
  <li>Audit log: every state change with timestamp + account_id</li>
</ul>
<h2>What we do NOT store</h2>
<ul>
  <li>Email bodies in full beyond 10 days</li>
  <li>Card numbers (handled by NOWPayments / Stripe)</li>
  <li>Phone call recordings beyond the transient transcript step</li>
</ul>
<h2>How to request your data</h2>
<p>Email <a href="mailto:privacy@murphy.systems">privacy@murphy.systems</a>
from the address tied to your account. We respond within 30 days
with a JSON export of everything we have, plus a plain-language
summary.</p>
<p>An automated <code>/api/me/export</code> endpoint is on the
roadmap (Q3 2026) so you can pull this yourself without emailing us.</p>
<h2>How to verify your identity</h2>
<p>We confirm requests by sending a verification link to the
account email on file. No request is fulfilled without that
confirmation step.</p>''')


def data_export_html() -> str:
    return _page("Data Export (GDPR Art. 20)", "GDPR · Art. 20", '''
<h1>Data Portability / Export</h1>
<p class="lede">Get all your Murphy data in a portable format.</p>
<h2>What's included</h2>
<p>A single JSON file containing:</p>
<ul>
  <li>Your account record (excluding password hash)</li>
  <li>Your tenant configuration</li>
  <li>Your subscription + billing history</li>
  <li>Your usage counters</li>
  <li>Every email Murphy has handled for you in the last 10 days
      (subject, sender, our draft, your verdict)</li>
  <li>Your audit log entries</li>
  <li>Your follow-ups and tasks</li>
</ul>
<h2>Format</h2>
<p>JSON, schema documented inline in the export file under
<code>__schema__</code>. UTF-8, line-delimited where applicable.</p>
<h2>How to request</h2>
<p>Today: email <a href="mailto:privacy@murphy.systems">privacy@murphy.systems</a>
from the account address. We deliver within 7 business days
(GDPR allows 30; we aim for 7).</p>
<p>Q3 2026: self-serve at <code>/api/me/export</code> with one
click in your dashboard.</p>
<h2>What we charge</h2>
<p>Nothing. First request is free; subsequent requests within
30 days may incur a reasonable handling fee per GDPR Art. 12(5).</p>''')


def data_deletion_html() -> str:
    return _page("Data Deletion (Right to Erasure)", "GDPR · Art. 17 / CCPA · §1798.105", '''
<h1>Delete Your Data</h1>
<p class="lede">Walk away clean. Here's how.</p>
<h2>What gets deleted</h2>
<ul>
  <li>Your account record</li>
  <li>Your tenant configuration</li>
  <li>Your usage history and counters</li>
  <li>Every email Murphy has cached for you</li>
  <li>Your follow-ups and tasks</li>
  <li>Your billing data (subject to legal retention — see below)</li>
</ul>
<h2>What we have to keep</h2>
<p>Some data we are <em>required by law</em> to retain even after
you delete your account:</p>
<ul>
  <li>Invoice records — 7 years for US tax (IRS) and 6 years for some EU jurisdictions</li>
  <li>Compliance audit trail — 1 year minimum for SOC2 evidence (anonymised after account deletion)</li>
  <li>Anything subject to an active legal hold</li>
</ul>
<p>Everything else is purged immediately upon confirmation.</p>
<h2>How to request</h2>
<p>Today: email <a href="mailto:privacy@murphy.systems">privacy@murphy.systems</a>
from the address tied to your account. We confirm within 24 h
and purge within 7 days (GDPR allows 30; we aim for 7).</p>
<p>Q3 2026: self-serve at <code>/dashboard/account/delete</code> —
type your email to confirm, and Murphy is gone.</p>
<h2>What you'll see after deletion</h2>
<p>Your login stops working immediately. Murphy stops processing
inbound mail addressed to your account immediately. A final
deletion confirmation is sent to your email within 7 days.</p>''')


def register_routes(app):
    """Mount all 9 compliance doc routes."""
    routes = [
        ("/legal/incident-response", incident_response_html, "Incident Response"),
        ("/legal/vendor-risk",       vendor_risk_html,       "Vendor Risk"),
        ("/legal/security-policy",   security_policy_html,   "Security Policy"),
        ("/legal/asset-inventory",   asset_inventory_html,   "Asset Inventory"),
        ("/legal/risk-treatment",    risk_treatment_html,    "Risk Treatment"),
        ("/legal/bcp-dr",            bcp_dr_html,            "BCP / DR"),
        ("/legal/right-to-know",     right_to_know_html,     "Right to Know"),
        ("/legal/data-export",       data_export_html,       "Data Export"),
        ("/legal/data-deletion",     data_deletion_html,     "Data Deletion"),
    ]
    for path, fn, _name in routes:
        # Capture fn in default arg to avoid late binding
        async def _handler(_fn=fn):
            return HTMLResponse(_fn())
        app.get(path, include_in_schema=False)(_handler)
    return [p for p, _, _ in routes]
