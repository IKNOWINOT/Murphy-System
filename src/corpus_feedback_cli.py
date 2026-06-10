"""PCR-054m.1 — CLI entry point for the standalone feedback timer.

Run via systemd: murphy-corpus-feedback.timer fires this every 15 min.

Usage:
  corpus_feedback_cli.py [--limit N] [--db-path PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, "/opt/Murphy-System")

from src.corpus_feedback import process_resolved_engagements
from src.engagement_folder import DEFAULT_DB_PATH as ENGAGEMENT_DB_PATH


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="PCR-054m corpus feedback batch processor",
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max resolved engagements to process per run (default: 100)",
    )
    parser.add_argument(
        "--db-path", default=ENGAGEMENT_DB_PATH,
        help="Engagement folders DB path",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of plain text",
    )
    args = parser.parse_args(argv)

    result = process_resolved_engagements(
        limit=args.limit, db_path=args.db_path,
    )

    if args.json:
        print(json.dumps(result))
    else:
        print(
            f"[PCR-054m] engagements={result['engagements']} "
            f"events_recorded={result['events_recorded']} "
            f"events_skipped={result['events_skipped']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
