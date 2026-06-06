"""
PATCH-R553 (2026-06-04) — vendor protection module

WHAT THIS IS:
  Single source of truth for "which sender domains MUST NOT receive automated
  Murphy replies". Backed by /var/lib/murphy-production/state/vendor_protection.db.

  Built after the 2026-06-01 incident where Murphy's R388 email-in parser
  auto-replied "No commands found. Send 'help'" to rory@nowpayments.io.
  R537 added an allowlist gate to r388_email_in.py. This R553 module makes
  that gate a Murphy primitive any handler can reuse.

PUBLIC SURFACE:
  is_protected(addr_or_domain: str) -> bool
  list_protected() -> List[Dict]
  add_protected(domain, category, reason) -> Dict   # for HITL approval path
  remove_protected(domain) -> Dict                  # for HITL approval path
"""
import sqlite3
from typing import Any, Dict, List

_DB = "/var/lib/murphy-production/state/vendor_protection.db"


def _conn():
    c = sqlite3.connect(_DB, timeout=5)
    c.row_factory = sqlite3.Row
    return c


def _domain_of(addr_or_domain: str) -> str:
    s = (addr_or_domain or "").strip().lower()
    if "@" in s:
        s = s.split("@", 1)[1]
    return s.strip("<>").strip()


def is_protected(addr_or_domain: str) -> bool:
    domain = _domain_of(addr_or_domain)
    if not domain:
        return False
    try:
        c = _conn()
        row = c.execute(
            "SELECT 1 FROM protected_vendors WHERE domain=? LIMIT 1",
            (domain,),
        ).fetchone()
        c.close()
        return row is not None
    except Exception:
        return False  # fail-open is wrong for safety — but DB-missing means we can't tell


def is_protected_strict(addr_or_domain: str) -> bool:
    """Same as is_protected but fail-CLOSED if DB missing — safer for outbound."""
    domain = _domain_of(addr_or_domain)
    if not domain:
        return False
    try:
        c = _conn()
        row = c.execute(
            "SELECT 1 FROM protected_vendors WHERE domain=? LIMIT 1",
            (domain,),
        ).fetchone()
        c.close()
        return row is not None
    except Exception:
        return True  # fail-closed


def list_protected() -> List[Dict[str, Any]]:
    try:
        c = _conn()
        rows = c.execute(
            "SELECT domain, category, reason, added_at FROM protected_vendors ORDER BY domain"
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        return []


def add_protected(domain: str, category: str, reason: str) -> Dict[str, Any]:
    domain = _domain_of(domain)
    if not domain:
        return {"ok": False, "error": "empty domain"}
    try:
        c = _conn()
        c.execute(
            "INSERT OR IGNORE INTO protected_vendors(domain, category, reason) VALUES (?,?,?)",
            (domain, category, reason),
        )
        c.commit()
        c.close()
        return {"ok": True, "domain": domain}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def remove_protected(domain: str) -> Dict[str, Any]:
    domain = _domain_of(domain)
    try:
        c = _conn()
        c.execute("DELETE FROM protected_vendors WHERE domain=?", (domain,))
        c.commit()
        c.close()
        return {"ok": True, "domain": domain}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    # Smoke test
    print("nowpayments.io →", is_protected("nowpayments.io"))
    print("rory@nowpayments.io →", is_protected("rory@nowpayments.io"))
    print("randomdude@gmail.com →", is_protected("randomdude@gmail.com"))
    print(f"\nTotal protected: {len(list_protected())}")
