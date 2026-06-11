#!/usr/bin/env python3
"""
PATCH-R121 — inbound_autoresponse_runner

Invoked every 5 min by murphy-inbound-autoresponse.timer.
Composes:
  1. Classify any unclassified inbound_replies rows (R117/R118 substrate)
  2. Process pending allowlisted report_requests (R118 substrate)
  3. Process pending STRANGER inquiries (Ship 31c, 2026-06-10)
  4. Print one-line summary to stdout (captured by journald)

LAST UPDATED: 2026-06-10 — Ship 31c stranger responder added
"""
import os
import sys
import time

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
        from src.stranger_responder import process_stranger_inquiries
    except Exception as e:
        print("R121 FATAL import: {}".format(e), file=sys.stderr)
        return 1
    
    started = time.time()
    classified_n = 0
    sent_allow_n = 0
    sent_stranger_n = 0
    errors = []
    
    try:
        c = classify_pending(limit=20)
        classified_n = c.get("classified", 0)
    except Exception as e:
        errors.append(f"classify:{e}")
    
    # Stranger pass FIRST — claims non-allowlisted inquiry/report_request rows
    # before allowlist responder's broad HITL-stage rule catches them.
    try:
        s = process_stranger_inquiries(limit=5)
        sent_stranger_n = s.get("count_sent", 0)
    except Exception as e:
        errors.append(f"stranger:{e}")
    
    try:
        r = process_pending_responses(limit=10)
        sent_allow_n = len(r.get("sent", []))
    except Exception as e:
        errors.append(f"allow:{e}")
    
    elapsed = round(time.time() - started, 2)
    err_str = (" errors=" + ";".join(errors)) if errors else ""
    print(f"R121 done in {elapsed}s: classified={classified_n} allow_sent={sent_allow_n} stranger_sent={sent_stranger_n}{err_str}")
    return 0 if not errors else 0  # don't fail on partial errors


if __name__ == "__main__":
    sys.exit(main())
