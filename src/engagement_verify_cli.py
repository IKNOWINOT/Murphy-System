#!/usr/bin/env python3
"""
engagement_verify_cli.py — PCR-054h

Cron/timer entrypoint for verifying FINALIZED engagement folders.
Wraps src.engagement_verification.verify_finalized_engagements().

Usage:
  python3 src/engagement_verify_cli.py            # verify up to 100 folders
  python3 src/engagement_verify_cli.py --limit 25
"""
from __future__ import annotations
import argparse, json, logging, sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/Murphy-System")
from src.engagement_verification import verify_finalized_engagements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    started = datetime.now(timezone.utc).isoformat()

    try:
        result = verify_finalized_engagements(limit=args.limit)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}",
                          "started_at": started}))
        return 1

    finished = datetime.now(timezone.utc).isoformat()
    result["started_at"] = started; result["finished_at"] = finished

    if not args.quiet:
        print(f"[PCR-054h] scanned={result.get('scanned',0)} "
              f"verified={result.get('verified',0)} "
              f"flagged={result.get('flagged',0)} "
              f"skipped={result.get('skipped',0)}")
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
