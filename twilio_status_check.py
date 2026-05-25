"""
Check Twilio account state — balance, available US local numbers,
typical purchase cost, account status.
"""
import sys, sqlite3, json, base64, urllib.request, urllib.error

sys.path.insert(0, "/opt/Murphy-System")
from src import patch405_secrets_vault as v

conn = sqlite3.connect("/var/lib/murphy-production/murphy_vault.db")
SID = v._decrypt(*conn.execute("SELECT encrypted_value, nonce FROM vault_secrets WHERE name='TWILIO_ACCOUNT_SID'").fetchone())
TOK = v._decrypt(*conn.execute("SELECT encrypted_value, nonce FROM vault_secrets WHERE name='TWILIO_AUTH_TOKEN'").fetchone())
auth = "Basic " + base64.b64encode(f"{SID}:{TOK}".encode()).decode()

def call_twilio(path, params=""):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{SID}{path}"
    if params:
        url += "?" + params
    req = urllib.request.Request(url, headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:300]}

# 1. Account status
acct = call_twilio(".json")
print(f"  Account name:   {acct.get('friendly_name')}")
print(f"  Account status: {acct.get('status')}")
print(f"  Type:           {acct.get('type')}  (trial or full)")

# 2. Balance
bal = call_twilio("/Balance.json")
print(f"  Balance:        ${bal.get('balance')} {bal.get('currency')}")

# 3. Available US local numbers (just to see prices and existence)
avail = call_twilio("/AvailablePhoneNumbers/US/Local.json", "Limit=3&SmsEnabled=true&VoiceEnabled=true")
nums = avail.get("available_phone_numbers", [])
print(f"  Available numbers to buy ({len(nums)} shown):")
for n in nums[:3]:
    print(f"    {n.get('phone_number')}  region={n.get('region')}  locality={n.get('locality')}")

# 4. Outgoing caller IDs (verified personal numbers for trial accounts)
oc = call_twilio("/OutgoingCallerIds.json")
ocs = oc.get("outgoing_caller_ids", [])
print(f"  Verified outgoing caller IDs (trial accounts can use these): {len(ocs)}")
for c in ocs:
    print(f"    {c.get('phone_number')}  ({c.get('friendly_name')})")
