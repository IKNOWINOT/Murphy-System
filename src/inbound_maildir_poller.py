#!/usr/bin/env python3
"""
inbound_maildir_poller.py — Scan local Maildir folders and capture inbound emails
into /var/lib/murphy-production/inbound_replies.db::inbound_replies.

LOCKED 2026-05-27 — PATCH-INBOUND-CAPTURE-001
Author: Murphy (working with Corey)

Why this exists:
- We OWN the mail server (Postfix + Dovecot for murphy.systems).
- Inbox messages already arrive as files in /var/mail/vhosts/murphy.systems/<user>/new/
- Nothing was reading them into a queryable table, so capacity_watchdog
  reported "999 days no replies" (sentinel-for-never).
- Architecture: Maildir → poll → hash → insert. No IMAP needed.

Usage:
  python3 src/inbound_maildir_poller.py            # one-shot scan
  python3 src/inbound_maildir_poller.py --limit 50 # bounded scan for testing
"""
from __future__ import annotations
import email
import hashlib
import os
import re
import sqlite3
import sys
from email.utils import parseaddr
from pathlib import Path
from typing import Iterable

DB_PATH = "/var/lib/murphy-production/inbound_replies.db"
MAILDIR_ROOT = Path("/var/mail/vhosts/murphy.systems")
MAILBOXES = ("cpost", "hpost", "sales", "murphy", "support", "billing")
PROSPECT_DOMAINS = {
    "apexgc.com": "apc_d_79d3bef6",
    "horizonrealty.com": "apc_d_f482984b",
    "fastroutelogistics.com": "apc_d_e49d22db",
    "valleymedclinic.com": "apc_d_ecc817e7",
    "founderstack.co": "deal_0ab3cad0",
    "clearpathedu.org": "deal_30da626b",
}
INTERNAL_DOMAINS = {"murphy.systems", "mail.murphy.systems"}

def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes()[:8192])  # first 8KB enough for dedup
    return h.hexdigest()[:32]

def _parse(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return {}
    from_hdr = str(msg.get("From", "") or "")
    _, from_addr = parseaddr(from_hdr)
    from_domain = (from_addr.split("@", 1)[1] if "@" in from_addr else "").lower()
    body_preview = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body_preview = part.get_payload(decode=True).decode("utf-8", errors="ignore")[:400]
                except Exception:
                    pass
                break
    else:
        try:
            body_preview = msg.get_payload(decode=True).decode("utf-8", errors="ignore")[:400]
        except Exception:
            body_preview = (msg.get_payload() or "")[:400]
    return {
        "from_addr": from_addr,
        "from_domain": from_domain,
        "to_addr": (parseaddr(str(msg.get("To", "") or ""))[1] or ""),
        "subject": (str(msg.get("Subject", "") or ""))[:300],
        "date_header": (str(msg.get("Date", "") or ""))[:80],
        "body_preview": body_preview,
        "is_internal": 1 if from_domain in INTERNAL_DOMAINS else 0,
        "is_prospect_domain": 1 if from_domain in PROSPECT_DOMAINS else 0,
        "prospect_deal_id": PROSPECT_DOMAINS.get(from_domain),
    }

def _iter_messages(limit: int | None = None) -> Iterable[tuple[str, Path]]:
    n = 0
    for mb in MAILBOXES:
        new_dir = MAILDIR_ROOT / mb / "new"
        cur_dir = MAILDIR_ROOT / mb / "cur"
        for d in (new_dir, cur_dir):
            if not d.is_dir(): continue
            for f in d.iterdir():
                if not f.is_file(): continue
                yield (mb, f)
                n += 1
                if limit and n >= limit: return

def run(limit: int | None = None) -> dict:
    con = sqlite3.connect(DB_PATH, timeout=10)
    stats = {"scanned": 0, "inserted": 0, "skipped_dup": 0, "errors": 0,
             "prospect_replies": 0, "internal": 0}
    for mb, path in _iter_messages(limit=limit):
        stats["scanned"] += 1
        try:
            h = _hash_file(path)
            existing = con.execute("SELECT 1 FROM inbound_replies WHERE msg_hash = ?", (h,)).fetchone()
            if existing:
                stats["skipped_dup"] += 1
                continue
            parsed = _parse(path)
            if not parsed:
                stats["errors"] += 1
                continue
            con.execute(
                "INSERT INTO inbound_replies (msg_hash, mailbox, from_addr, from_domain, "
                "to_addr, subject, date_header, is_internal, is_prospect_domain, "
                "prospect_deal_id, body_preview) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (h, mb, parsed["from_addr"], parsed["from_domain"],
                 parsed["to_addr"], parsed["subject"], parsed["date_header"],
                 parsed["is_internal"], parsed["is_prospect_domain"],
                 parsed["prospect_deal_id"], parsed["body_preview"]),
            )
            stats["inserted"] += 1
            if parsed["is_prospect_domain"]: stats["prospect_replies"] += 1
            if parsed["is_internal"]: stats["internal"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"  err on {path.name}: {e}", file=sys.stderr)
    con.commit(); con.close()
    return stats

if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    s = run(limit=lim)
    print(f"scanned={s['scanned']} inserted={s['inserted']} "
          f"dup={s['skipped_dup']} err={s['errors']} "
          f"prospect_replies={s['prospect_replies']} internal={s['internal']}")
    sys.exit(0)
