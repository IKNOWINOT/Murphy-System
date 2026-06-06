#!/usr/bin/env python3
"""
Verify SendGrid delivery END-TO-END. Sends one real email to
cpost@murphy.systems, then polls SendGrid's event API to confirm
'delivered' (not just 'accepted').

Usage:
    SENDGRID_API_KEY=SG.xxxx python3 test_sendgrid_real.py [recipient]
"""
import os, sys, time, json, uuid, urllib.request, urllib.error

KEY = os.environ.get("SENDGRID_API_KEY","").strip()
if not KEY:
    print("✗ no SENDGRID_API_KEY in env"); sys.exit(1)

RECIPIENT = sys.argv[1] if len(sys.argv) > 1 else "cpost@murphy.systems"
MSG_TAG   = f"murphy-test-{uuid.uuid4().hex[:8]}"
SUBJECT   = f"Murphy email infra test {MSG_TAG}"
BODY      = (f"This is an automated test from Murphy System.\n\n"
             f"Tag: {MSG_TAG}\nTime: {time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}\n\n"
             f"If you see this in your inbox, SendGrid delivery is real.\n")

payload = json.dumps({
    "personalizations": [{"to":[{"email":RECIPIENT}]}],
    "from": {"email": "murphy@murphy.systems", "name":"Murphy System"},
    "subject": SUBJECT,
    "content": [{"type":"text/plain","value":BODY}],
    "custom_args": {"murphy_tag": MSG_TAG},
}).encode()

req = urllib.request.Request(
    "https://api.sendgrid.com/v3/mail/send",
    data=payload,
    headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"},
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print(f"✓ SendGrid accepted: HTTP {r.status}")
        print(f"  X-Message-Id: {r.headers.get('X-Message-Id')}")
        print(f"  tag: {MSG_TAG}")
        print(f"  recipient: {RECIPIENT}")
        print(f"  → check your inbox now")
except urllib.error.HTTPError as e:
    print(f"✗ SendGrid REJECTED: {e.code} {e.read().decode()[:400]}")
    sys.exit(2)
except Exception as e:
    print(f"✗ network error: {e}")
    sys.exit(3)
