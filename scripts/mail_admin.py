#!/usr/bin/env python3
"""
scripts/mail_admin.py — Murphy System Mail Server Admin CLI

Manages docker-mailserver accounts, aliases, quotas, and DKIM keys.

Usage:
  python scripts/mail_admin.py add-account <email> <password> [--quota 5G]
  python scripts/mail_admin.py remove-account <email>
  python scripts/mail_admin.py list-accounts
  python scripts/mail_admin.py add-alias <alias@domain> <target@domain>
  python scripts/mail_admin.py remove-alias <alias@domain>
  python scripts/mail_admin.py list-aliases
  python scripts/mail_admin.py change-password <email> <new_password>
  python scripts/mail_admin.py set-quota <email> <quota>
  python scripts/mail_admin.py generate-dkim
  python scripts/mail_admin.py show-dns-records

Copyright © 2020 Inoni LLC — Creator: Corey Post | License: BSL 1.1
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

CONTAINER = "murphy-mailserver"
DOMAIN = "murphy.systems"

# ── Config file paths (inside the container's mounted config) ───────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS_CF = _REPO_ROOT / "config" / "mail" / "postfix-accounts.cf"
VIRTUAL_CF  = _REPO_ROOT / "config" / "mail" / "postfix-virtual.cf"


# ── Helpers ─────────────────────────────────────────────────────────────────

def _run(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return its CompletedProcess."""
    return subprocess.run(args, capture_output=True, text=True, check=check)


def _dms(*args: str) -> subprocess.CompletedProcess:
    """Run a docker-mailserver setup command."""
    return _run(["docker", "exec", CONTAINER, "setup"] + list(args))


def _container_running() -> bool:
    result = _run(["docker", "ps", "--format", "{{.Names}}"], check=False)
    return CONTAINER in result.stdout.splitlines()


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def _err(msg: str) -> None:
    print(f"  ❌  {msg}", file=sys.stderr)


def _require_container() -> None:
    if not _container_running():
        _err(f"Container '{CONTAINER}' is not running.")
        _err("Start it with: docker compose up -d murphy-mailserver")
        sys.exit(1)


# ── Commands ────────────────────────────────────────────────────────────────

def cmd_add_account(email: str, password: str, quota: str = "5G") -> None:
    """Add a new email account."""
    _require_container()
    if not _validate_email(email):
        _err(f"Invalid email address: {email}")
        sys.exit(1)

    result = _dms("email", "add", email, password)
    if result.returncode != 0:
        _err(f"Failed to add account: {result.stderr.strip()}")
        sys.exit(1)

    # Set quota
    quota_mb = _parse_quota_mb(quota)
    _dms("quota", "set", email, f"{quota_mb}M")
    _ok(f"Account created: {email} (quota: {quota})")


def cmd_remove_account(email: str) -> None:
    """Remove an email account."""
    _require_container()
    result = _dms("email", "del", email)
    if result.returncode != 0:
        _err(f"Failed to remove account: {result.stderr.strip()}")
        sys.exit(1)
    _ok(f"Account removed: {email}")


def cmd_list_accounts() -> None:
    """List all email accounts."""
    _require_container()
    result = _dms("email", "list")
    if result.returncode != 0:
        _err(f"Failed to list accounts: {result.stderr.strip()}")
        sys.exit(1)

    lines = [l for l in result.stdout.splitlines() if l.strip()]
    print(f"\n  {'Email':<40} {'Domain'}")
    print(f"  {'─'*40} {'─'*20}")
    for line in lines:
        parts = line.split("@")
        if len(parts) == 2:
            print(f"  {line:<40} {parts[1]}")
        else:
            print(f"  {line}")
    print(f"\n  Total: {len(lines)} account(s)\n")


def cmd_add_alias(alias: str, target: str) -> None:
    """Add a virtual alias."""
    _require_container()
    for addr in (alias, target):
        if not _validate_email(addr):
            _err(f"Invalid email address: {addr}")
            sys.exit(1)

    result = _dms("alias", "add", alias, target)
    if result.returncode != 0:
        _err(f"Failed to add alias: {result.stderr.strip()}")
        sys.exit(1)
    _ok(f"Alias added: {alias} → {target}")


def cmd_remove_alias(alias: str) -> None:
    """Remove a virtual alias."""
    _require_container()
    result = _dms("alias", "del", alias)
    if result.returncode != 0:
        _err(f"Failed to remove alias: {result.stderr.strip()}")
        sys.exit(1)
    _ok(f"Alias removed: {alias}")


def cmd_list_aliases() -> None:
    """List all virtual aliases."""
    _require_container()
    result = _dms("alias", "list")
    if result.returncode != 0:
        _err(f"Failed to list aliases: {result.stderr.strip()}")
        sys.exit(1)

    lines = [l for l in result.stdout.splitlines() if l.strip()]
    print(f"\n  {'Alias':<40} {'Target'}")
    print(f"  {'─'*40} {'─'*40}")
    for line in lines:
        parts = line.split()
        if len(parts) >= 2:
            print(f"  {parts[0]:<40} {' '.join(parts[1:])}")
        else:
            print(f"  {line}")
    print(f"\n  Total: {len(lines)} alias(es)\n")


def cmd_change_password(email: str, new_password: str) -> None:
    """Change password for an account."""
    _require_container()
    result = _dms("email", "update-password", email, new_password)
    if result.returncode != 0:
        _err(f"Failed to change password: {result.stderr.strip()}")
        sys.exit(1)
    _ok(f"Password updated for: {email}")


def cmd_set_quota(email: str, quota: str) -> None:
    """Set mailbox quota for an account."""
    _require_container()
    quota_mb = _parse_quota_mb(quota)
    result = _dms("quota", "set", email, f"{quota_mb}M")
    if result.returncode != 0:
        _err(f"Failed to set quota: {result.stderr.strip()}")
        sys.exit(1)
    _ok(f"Quota set: {email} = {quota}")


def cmd_generate_dkim() -> None:
    """Generate DKIM keys."""
    _require_container()
    result = _dms("config", "dkim")
    if result.returncode != 0:
        _err(f"Failed to generate DKIM: {result.stderr.strip()}")
        sys.exit(1)
    _ok("DKIM key generated.")
    print("\n  Add the following DNS TXT record (mail._domainkey.murphy.systems):")
    # Try to display the public key
    try:
        key_result = _run(["docker", "exec", CONTAINER, "find", "/", "-name", "mail.txt", "-type", "f"])
        if key_result.stdout.strip():
            key_path = key_result.stdout.strip().splitlines()[0]
            cat_result = _run(["docker", "exec", CONTAINER, "cat", key_path])
            print(f"\n{cat_result.stdout}\n")
    except Exception:
        print("  [Run: docker exec murphy-mailserver cat /etc/opendkim/keys/murphy.systems/mail.txt]\n")


def cmd_show_dns_records() -> None:
    """Print required DNS records."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════════╗
║                Murphy System — Required DNS Records                              ║
╚══════════════════════════════════════════════════════════════════════════════════╝

  Replace <your-hetzner-ip> with your actual server IP address.

  Type   Name                               Value
  ─────  ─────────────────────────────────  ──────────────────────────────────────────────────
  MX     murphy.systems                     mail.murphy.systems  (Priority: 10)
  A      mail.murphy.systems                <your-hetzner-ip>
  TXT    murphy.systems                     v=spf1 a mx ip4:<your-hetzner-ip> -all
  TXT    _dmarc.murphy.systems              v=DMARC1; p=quarantine; rua=mailto:postmaster@murphy.systems
  TXT    mail._domainkey.murphy.systems     <DKIM public key — run: mail_admin.py generate-dkim>

  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │  IMAP/SMTP settings for email clients:                                          │
  │                                                                                 │
  │  Incoming (IMAP):  mail.murphy.systems  Port: 993  Security: SSL/TLS            │
  │  Outgoing (SMTP):  mail.murphy.systems  Port: 587  Security: STARTTLS           │
  │  Username:         your-full-email@murphy.systems                               │
  └─────────────────────────────────────────────────────────────────────────────────┘
""")


# ── Quota parsing ────────────────────────────────────────────────────────────

def _parse_quota_mb(quota: str) -> int:
    """Convert a quota string like '5G', '500M', '1T' to megabytes."""
    quota = quota.strip().upper()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([GMTK]?)$", quota)
    if not m:
        _err(f"Invalid quota format: {quota}. Use e.g. 5G, 500M, 1T.")
        sys.exit(1)
    value, unit = float(m.group(1)), m.group(2) or "M"
    multipliers = {"K": 1/1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    return int(value * multipliers[unit])


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mail_admin.py",
        description="Murphy System — Mail Server Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/mail_admin.py add-account cpost@murphy.systems SecretPass123 --quota 10G
  python scripts/mail_admin.py list-accounts
  python scripts/mail_admin.py add-alias devops@murphy.systems cpost@murphy.systems
  python scripts/mail_admin.py show-dns-records
  python scripts/mail_admin.py generate-dkim
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add-account
    p = sub.add_parser("add-account", help="Add a new mailbox")
    p.add_argument("email")
    p.add_argument("password")
    p.add_argument("--quota", default="5G", help="Mailbox quota (default: 5G)")

    # remove-account
    p = sub.add_parser("remove-account", help="Remove a mailbox")
    p.add_argument("email")

    # list-accounts
    sub.add_parser("list-accounts", help="List all mailboxes")

    # add-alias
    p = sub.add_parser("add-alias", help="Add a virtual alias")
    p.add_argument("alias", metavar="alias@domain")
    p.add_argument("target", metavar="target@domain")

    # remove-alias
    p = sub.add_parser("remove-alias", help="Remove a virtual alias")
    p.add_argument("alias", metavar="alias@domain")

    # list-aliases
    sub.add_parser("list-aliases", help="List all aliases")

    # change-password
    p = sub.add_parser("change-password", help="Change account password")
    p.add_argument("email")
    p.add_argument("new_password")

    # set-quota
    p = sub.add_parser("set-quota", help="Set mailbox quota")
    p.add_argument("email")
    p.add_argument("quota", help="e.g. 5G, 500M, 1T")

    # generate-dkim
    sub.add_parser("generate-dkim", help="Generate DKIM signing keys")

    # show-dns-records
    sub.add_parser("show-dns-records", help="Print required DNS records")

    args = parser.parse_args()

    dispatch = {
        "add-account":     lambda: cmd_add_account(args.email, args.password, args.quota),
        "remove-account":  lambda: cmd_remove_account(args.email),
        "list-accounts":   cmd_list_accounts,
        "add-alias":       lambda: cmd_add_alias(args.alias, args.target),
        "remove-alias":    lambda: cmd_remove_alias(args.alias),
        "list-aliases":    cmd_list_aliases,
        "change-password": lambda: cmd_change_password(args.email, args.new_password),
        "set-quota":       lambda: cmd_set_quota(args.email, args.quota),
        "generate-dkim":   cmd_generate_dkim,
        "show-dns-records": cmd_show_dns_records,
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()
