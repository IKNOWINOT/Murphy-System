"""
patch_dept_phones.py
=====================

Buys 5 Twilio numbers in the 716 area code for Murphy's departments,
configures voice/SMS webhooks, stores mappings, writes /static/contact.html.

WHAT THIS IS:
  One-shot script to finally execute the "department phone numbers"
  task the founder asked about. No PSM gating — this is concrete
  external action against a billed account, founder-authorized inline.

WHY 5 NUMBERS:
  Sales, Engineering, Support, Operations, Founder.
  Cost: 5 x $1.15/mo = $5.75/mo recurring (paid from existing $50 balance).
  Plus ~$0.0085/min on inbound, $0.013/min outbound.

WEBHOOK ROUTING:
  Each department number routes its voice webhook to
    https://murphy.systems/api/phone/twilio/voice?dept=<dept>
  PATCH-406a already implements this endpoint shape; the dept param
  will let the answering bot identify which department was called.

DOES NOT:
  - Wire /api/phone/dial into the running monolith (separate work)
  - Place any outbound calls (separate script: prospect_call.py)
  - Modify the founder's verified caller ID (+17164003440 stays as-is)
"""
import sys
import sqlite3
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, "/opt/Murphy-System")
from src import patch405_secrets_vault as v

DEPARTMENTS = [
    ("Sales",        "sales",       "Murphy Sales — autonomous prospecting & inbound demos"),
    ("Engineering",  "engineering", "Murphy Engineering — RFI, RFQ, technical questions"),
    ("Support",      "support",     "Murphy Support — existing customer help"),
    ("Operations",   "operations",  "Murphy Ops — billing, account, admin"),
    ("Founder",      "founder",     "Corey Post direct — escalations only"),
]

AREA_CODE = "716"
WEBHOOK_BASE = "https://murphy.systems"

# ─── 1. Pull Twilio creds ───────────────────────────────────────────────
conn = sqlite3.connect("/var/lib/murphy-production/murphy_vault.db")
SID = v._decrypt(*conn.execute(
    "SELECT encrypted_value, nonce FROM vault_secrets WHERE name='TWILIO_ACCOUNT_SID'"
).fetchone())
TOK = v._decrypt(*conn.execute(
    "SELECT encrypted_value, nonce FROM vault_secrets WHERE name='TWILIO_AUTH_TOKEN'"
).fetchone())
auth = "Basic " + base64.b64encode(f"{SID}:{TOK}".encode()).decode()
print(f"  Twilio SID: {SID[:10]}...")


def twilio_get(path, params=""):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}{path}"
    if params:
        url += "?" + params
    req = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:400]}


def twilio_post(path, fields):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}{path}"
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": auth,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:400]}


# ─── 2. Find 5 available 716 numbers ────────────────────────────────────
print(f"  > Searching for {len(DEPARTMENTS)} available numbers in area code {AREA_CODE}...")
avail = twilio_get(
    "/AvailablePhoneNumbers/US/Local.json",
    f"AreaCode={AREA_CODE}&Limit=10&SmsEnabled=true&VoiceEnabled=true",
)
if avail.get("_error"):
    print(f"  X search failed: {avail.get('_body')}")
    sys.exit(1)
candidates = avail.get("available_phone_numbers", [])
print(f"  Found {len(candidates)} candidates")
if len(candidates) < len(DEPARTMENTS):
    print(f"  X not enough 716 numbers available (need {len(DEPARTMENTS)})")
    sys.exit(1)
to_buy = candidates[:len(DEPARTMENTS)]
for n in to_buy:
    print(f"    candidate: {n['phone_number']}  ({n.get('locality')})")


# ─── 3. Purchase + configure each number ────────────────────────────────
results = []
for (dept_name, dept_slug, dept_desc), avail_num in zip(DEPARTMENTS, to_buy):
    phone = avail_num["phone_number"]
    voice_url = f"{WEBHOOK_BASE}/api/phone/twilio/voice?dept={dept_slug}"
    sms_url   = f"{WEBHOOK_BASE}/api/phone/twilio/sms?dept={dept_slug}"
    status_url = f"{WEBHOOK_BASE}/api/phone/twilio/status?dept={dept_slug}"

    print(f"  > Buying {phone} for {dept_name}...")
    purchase = twilio_post("/IncomingPhoneNumbers.json", {
        "PhoneNumber": phone,
        "FriendlyName": f"Murphy {dept_name}",
        "VoiceUrl": voice_url,
        "VoiceMethod": "POST",
        "SmsUrl": sms_url,
        "SmsMethod": "POST",
        "StatusCallback": status_url,
        "StatusCallbackMethod": "POST",
    })
    if purchase.get("_error"):
        print(f"    X failed: {purchase.get('_body')}")
        continue
    print(f"    OK sid={purchase.get('sid')[:12]}...  ${purchase.get('price') or '?'}")
    results.append({
        "department": dept_name,
        "slug": dept_slug,
        "description": dept_desc,
        "phone_number": purchase.get("phone_number"),
        "twilio_sid": purchase.get("sid"),
        "voice_url": voice_url,
        "sms_url": sms_url,
        "purchased_at": datetime.now(timezone.utc).isoformat(),
    })

print(f"  > Purchased {len(results)}/{len(DEPARTMENTS)} numbers")


# ─── 4. Persist mapping to vault DB ─────────────────────────────────────
conn.execute("""
    CREATE TABLE IF NOT EXISTS department_phones (
        department      TEXT PRIMARY KEY,
        slug            TEXT NOT NULL,
        description     TEXT,
        phone_number    TEXT NOT NULL,
        twilio_sid      TEXT NOT NULL,
        voice_url       TEXT,
        sms_url         TEXT,
        purchased_at    TEXT NOT NULL
    )
""")
for r in results:
    conn.execute("""
        INSERT OR REPLACE INTO department_phones
        (department, slug, description, phone_number, twilio_sid, voice_url, sms_url, purchased_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (r["department"], r["slug"], r["description"], r["phone_number"],
          r["twilio_sid"], r["voice_url"], r["sms_url"], r["purchased_at"]))
conn.commit()
print(f"  > Saved {len(results)} rows to department_phones")

# Save raw JSON too for debugging
with open("/var/lib/murphy-production/department_phones.json", "w") as f:
    json.dump(results, f, indent=2)
print(f"  > Wrote /var/lib/murphy-production/department_phones.json")


# ─── 5. Build /static/contact.html ──────────────────────────────────────
def fmt_phone(p):
    # +17163336789 -> (716) 333-6789
    if p and p.startswith("+1") and len(p) == 12:
        return f"({p[2:5]}) {p[5:8]}-{p[8:]}"
    return p

rows_html = "\n".join(
    f"""        <tr>
          <td class="dept">{r['department']}</td>
          <td class="num"><a href="tel:{r['phone_number']}">{fmt_phone(r['phone_number'])}</a></td>
          <td class="desc">{r['description']}</td>
        </tr>"""
    for r in results
)

contact_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Contact — Murphy Systems</title>
  <link rel="icon" href="/static/favicon.ico" />
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 880px;
            margin: 0 auto; padding: 2rem 1rem; line-height: 1.55;
            color: #1a1a1a; background: #fafafa; }}
    h1 {{ font-size: 2.25rem; margin-bottom: 0.5rem; }}
    .sub {{ color: #666; margin-bottom: 2rem; }}
    table {{ width: 100%; border-collapse: collapse; background: white;
             border-radius: 12px; overflow: hidden;
             box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    th, td {{ text-align: left; padding: 1rem 1.25rem;
              border-bottom: 1px solid #eee; }}
    th {{ background: #f4f4f5; font-size: 0.85rem; text-transform: uppercase;
          letter-spacing: 0.05em; color: #555; }}
    tr:last-child td {{ border-bottom: none; }}
    .dept {{ font-weight: 600; width: 22%; }}
    .num a {{ font-family: ui-monospace, SF Mono, Menlo, monospace;
              font-size: 1.05rem; color: #0066cc; text-decoration: none;
              font-weight: 600; }}
    .num a:hover {{ text-decoration: underline; }}
    .desc {{ color: #555; font-size: 0.95rem; }}
    .footer {{ margin-top: 2rem; font-size: 0.9rem; color: #666; }}
    .footer a {{ color: #0066cc; }}
    @media (max-width: 600px) {{
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ margin-bottom: 1rem; border-radius: 12px; overflow: hidden; }}
      td {{ padding: 0.5rem 1rem; }}
      .dept {{ background: #f4f4f5; font-size: 1.05rem; }}
    }}
  </style>
</head>
<body>
  <h1>Contact Murphy</h1>
  <p class="sub">Reach the right department directly. Every line is
     answered by Murphy first; complex requests escalate to the founder.</p>

  <table>
    <thead>
      <tr>
        <th>Department</th>
        <th>Phone</th>
        <th>What it's for</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>

  <p class="footer">
    Email: <a href="mailto:hello@murphy.systems">hello@murphy.systems</a>
    &nbsp;·&nbsp; Pricing: <a href="/static/pricing.html">/pricing</a>
    &nbsp;·&nbsp; Numbers powered by Twilio. Calls may be recorded
    for quality and training.
  </p>
</body>
</html>
"""

with open("/var/lib/murphy-production/uploads/contact.html", "w") as f:
    f.write(contact_html)
with open("/opt/Murphy-System/static/contact.html", "w") as f:
    f.write(contact_html)
print(f"  > Wrote contact.html ({len(contact_html)} bytes) to /static/ and /uploads/")

print()
print("  =============================================")
print("  DEPARTMENT PHONE LINES — LIVE")
print("  =============================================")
for r in results:
    print(f"   {r['department']:13s}  {fmt_phone(r['phone_number'])}")
print()
print(f"  Public page: https://murphy.systems/static/contact.html")
print(f"  Monthly cost: ${len(results) * 1.15:.2f}/mo (5 lines x $1.15)")
