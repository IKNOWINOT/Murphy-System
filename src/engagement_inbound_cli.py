#!/usr/bin/env python3
"""
engagement_inbound_cli.py — PCR-054i

Cron/timer entrypoint for processing pending engagement attestation replies.
Wraps src.engagement_inbound.process_pending_replies() with command-line
ergonomics + JSON output suitable for journal aggregation.

Usage:
  python3 src/engagement_inbound_cli.py            # process up to 200 replies
  python3 src/engagement_inbound_cli.py --limit 50 # bounded
  python3 src/engagement_inbound_cli.py --since 2026-06-09T00:00:00

systemd integration: see /etc/systemd/system/murphy-engagement-inbound.timer
                     and /etc/systemd/system/murphy-engagement-inbound.service
                     (5min cadence, mirrors murphy-inbound-poller pattern)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone

# Ensure /opt/Murphy-System is on the path so src.* imports resolve
# when the script is invoked directly via systemd ExecStart.
import os
sys.path.insert(0, "/opt/Murphy-System")

from src.engagement_inbound import process_pending_replies


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pending engagement attestation replies")
    parser.add_argument("--limit", type=int, default=200,
                        help="Max rows to scan (default 200)")
    parser.add_argument("--since", type=str, default=None,
                        help="ISO timestamp; only process rows received_at >= since")
    parser.add_argument("--quiet", action="store_true",
                        help="Only emit JSON, no human-readable line")
    args = parser.parse_args()

    # Light-weight logging - journal already timestamps everything.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    started_at = datetime.now(timezone.utc).isoformat()

    try:
        result = process_pending_replies(since=args.since, limit=args.limit)
    except Exception as e:
        # Fail loudly so the timer reports failure in journalctl
        err = {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(err))
        return 1

    finished_at = datetime.now(timezone.utc).isoformat()
    result["started_at"]  = started_at
    result["finished_at"] = finished_at

    # Print a compact summary on one line (journal-friendly)
    if not args.quiet:
        print(
            f"[PCR-054i] scanned={result.get('scanned', 0)} "
            f"finalized={result.get('finalized', 0)} "
            f"declined={result.get('declined', 0)} "
            f"skipped={result.get('skipped', 0)}"
        )

    # Always emit the full JSON for downstream consumption
    print(json.dumps(result, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
