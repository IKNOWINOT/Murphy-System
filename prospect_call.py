"""
prospect_call.py — One-shot outbound prospecting voicemail
============================================================

Pulls Twilio creds from the murphy vault, discovers the FROM number,
generates a TwiML voicemail script, and places a real call to the
target number using the Twilio REST API directly.

Bypasses /api/phone/dial (not currently mounted) — single-shot demo.
"""
import sys
import sqlite3
import json
import base64
import urllib.request
import urllib.error
import urllib.parse

sys.path.insert(0, "/opt/Murphy-System")
from src import patch405_secrets_vault as v

TO_NUMBER = "+17164003440"

# ─── 1. Decrypt Twilio creds from vault ────────────────────────────────
conn = sqlite3.connect("/var/lib/murphy-production/murphy_vault.db")
creds = {}
for name in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WEBHOOK_PUBLIC_URL"]:
    row = conn.execute(
        "SELECT encrypted_value, nonce FROM vault_secrets WHERE name=?",
        (name,),
    ).fetchone()
    creds[name] = v._decrypt(row[0], row[1])
SID = creds["TWILIO_ACCOUNT_SID"]
TOK = creds["TWILIO_AUTH_TOKEN"]
WEBHOOK_BASE = creds["TWILIO_WEBHOOK_PUBLIC_URL"]
auth_header = "Basic " + base64.b64encode(f"{SID}:{TOK}".encode()).decode()
print(f"  Webhook base: {WEBHOOK_BASE}")

# ─── 2. Discover FROM number ───────────────────────────────────────────
req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/IncomingPhoneNumbers.json",
    headers={"Authorization": auth_header},
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
except urllib.error.HTTPError as e:
    print(f"  X Twilio API error {e.code}: {e.read().decode()[:300]}")
    sys.exit(1)

numbers = data.get("incoming_phone_numbers", [])
print(f"  Found {len(numbers)} number(s):")
voice_nums = []
for n in numbers:
    caps = n.get("capabilities", {})
    pn = n.get("phone_number")
    fn = n.get("friendly_name")
    print(f"    {pn}  ({fn})  voice={caps.get('voice')}  sms={caps.get('sms')}")
    if caps.get("voice"):
        voice_nums.append(pn)

if not voice_nums:
    print("  X No voice-capable Twilio number on the account. Buy one at console.twilio.com first.")
    sys.exit(1)

FROM_NUMBER = voice_nums[0]
print(f"  > Using FROM: {FROM_NUMBER}")

# ─── 3. Check balance ──────────────────────────────────────────────────
req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Balance.json",
    headers={"Authorization": auth_header},
)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        bal = json.loads(r.read())
        print(f"  Balance: ${bal.get('balance')} {bal.get('currency')}")
except Exception as e:
    print(f"  Balance check skipped: {e}")

# ─── 4. Compose the prospecting voicemail TwiML ────────────────────────
# Inline TwiML via the `Twiml` parameter (Twilio supports this — no need
# to host the XML at a URL).
script = (
    "Hey, this is Murphy, the autonomous AI sales agent calling from "
    "Murphy Systems. I'm reaching out because I help mechanical contractors "
    "stop losing bids to spreadsheet errors and disconnected vendor quote "
    "workflows. "
    "Most of the MEP firms I talk to are managing equipment RFQs across "
    "email, scattered spreadsheets, and three different procurement portals. "
    "Murphy ties all of that into one autonomous engineering operations "
    "platform that responds to RFQs, tracks vendor pricing in real time, "
    "and surfaces the optimal combination automatically. "
    "We're working with mechanical contractors who are running active "
    "projects right now, and the early results have been strong. "
    "If you're open to a fifteen minute look at what this would mean for "
    "your next project, you can reach me at murphy dot systems, "
    "or just reply to the followup email I'm sending right after this. "
    "Thanks Corey, talk soon."
)

twiml = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Response>'
    f'<Pause length="2"/>'
    f'<Say voice="Polly.Matthew-Neural" language="en-US">{script}</Say>'
    f'<Pause length="1"/>'
    '</Response>'
)
print(f"  > TwiML built ({len(twiml)} chars, {len(script.split())} words)")

# ─── 5. Place the call ─────────────────────────────────────────────────
body = urllib.parse.urlencode({
    "To": TO_NUMBER,
    "From": FROM_NUMBER,
    "Twiml": twiml,
    # Optional: record so we can listen back later
    "Record": "false",
    "MachineDetection": "Enable",
    "MachineDetectionTimeout": "10",
}).encode()

req = urllib.request.Request(
    f"https://api.twilio.com/2010-04-01/Accounts/{SID}/Calls.json",
    data=body,
    headers={
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded",
    },
    method="POST",
)

print(f"  > Placing call: {FROM_NUMBER} -> {TO_NUMBER}")
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read())
        print()
        print("  ============================================")
        print(f"  CALL PLACED")
        print(f"  ============================================")
        print(f"  SID:        {result.get('sid')}")
        print(f"  Status:     {result.get('status')}")
        print(f"  From:       {result.get('from')}")
        print(f"  To:         {result.get('to')}")
        print(f"  Direction:  {result.get('direction')}")
        print(f"  Price:      {result.get('price') or 'pending'}")
        print()
        print("  Murphy is dialing 716-400-3440 RIGHT NOW.")
        print("  Don't answer — it'll leave the voicemail.")
        # Save SID for status follow-up
        with open("/tmp/last_call_sid.txt", "w") as f:
            f.write(result.get("sid", ""))
except urllib.error.HTTPError as e:
    err_body = e.read().decode()
    print(f"  X Twilio rejected the call (HTTP {e.code}):")
    print(f"     {err_body[:500]}")
    sys.exit(1)
except Exception as e:
    print(f"  X Error: {type(e).__name__}: {e}")
    sys.exit(1)
