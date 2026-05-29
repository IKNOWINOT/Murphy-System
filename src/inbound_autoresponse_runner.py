#!/usr/bin/env python3
"""
PATCH-R121 — inbound_autoresponse_runner

Invoked every 5 min by murphy-inbound-autoresponse.timer.
Composes:
  1. Classify any unclassified inbound_replies rows (R117/R118 substrate)
  2. Process pending report_request rows (R118 substrate)
  3. Print one-line summary to stdout (captured by journald)

Zero Base44 message credits — runs as native systemd timer on host.

LAST UPDATED: 2026-05-29 R121
"""
import os
import sys
import time

# Bootstrap env vars from /etc/murphy-production/environment
ENV_FILE = "/etc/murphy-production/environment"
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, "/opt/Murphy-System")


def main() -> int:
    try:
        from src.inbound_intent import classify_pending
        from src.inbound_responder import process_pending_responses
    except Exception as e:
        print("R121 FATAL import: {}".format(e), file=sys.stderr)
        return 1
    
    started = time.time()
    try:
        c = classify_pending(limit=20)
        r = process_pending_responses(limit=10)
    except Exception as e:
        print("R121 FATAL run: {}".format(e), file=sys.stderr)
        return 2
    
    elapsed = round(time.time() - started, 2)
    classified = c.get("classified", 0)
    sent_n = len(r.get("sent", []))
    staged_n = len(r.get("staged", []))
    errors_n = len(r.get("errors", []))
    print(
        "R121 OK elapsed={}s classified={} sent={} staged={} errors={}".format(
            elapsed, classified, sent_n, staged_n, errors_n
        )
    )
    # Print details only when something happened
    if sent_n:
        for s in r.get("sent", []):
            print("  SENT id={} to={} subj={}".format(
                s.get("id"), s.get("to"), (s.get("subject") or "")[:60]))
    if staged_n:
        for s in r.get("staged", []):
            print("  STAGED id={} from={} reason={}".format(
                s.get("id"), s.get("from"), s.get("reason")))
    if errors_n:
        for s in r.get("errors", []):
            print("  ERROR id={} {}".format(
                s.get("id"), str(s.get("error") or s.get("reason"))[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
