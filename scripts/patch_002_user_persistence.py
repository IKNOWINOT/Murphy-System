#!/usr/bin/env python3
"""
PATCH-002: User Account Persistence
Fixes _user_store falling back to in-memory when DATABASE_URL=postgresql://

Run from /opt/Murphy-System/:
  python3 scripts/patch_002_user_persistence.py
"""
from __future__ import annotations
import os, sys, shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WAL_FILE = REPO_ROOT / "src" / "persistence_wal.py"

if not WAL_FILE.exists():
    print(f"✗ ABORT: {WAL_FILE} not found"); sys.exit(1)

content = WAL_FILE.read_text()

# Backup
backup = Path(str(WAL_FILE) + ".patch002.bak")
if not backup.exists():
    shutil.copy2(WAL_FILE, backup)
    print(f"Backup: {backup}")

CHANGE_1_OLD = '        else:\n            self._db_path = url or "murphy.db"'
CHANGE_1_NEW = '''        elif not url or url == ":memory:":
            self._db_path = "murphy_users.db"
        else:
            # Non-sqlite URL (postgresql://, mysql://, etc.) — fall back to SQLite
            import os as _os
            from pathlib import Path as _Path
            explicit = _os.environ.get("MURPHY_USER_DB_PATH", "").strip()
            if explicit:
                self._db_path = explicit
            else:
                _candidates = [
                    "/var/lib/murphy-production/murphy_users.db",
                    "/opt/Murphy-System/data/murphy_users.db",
                    "murphy_users.db",
                ]
                self._db_path = _candidates[-1]
                for _cand in _candidates:
                    _parent = _Path(_cand).parent
                    try:
                        if _parent.exists() and _os.access(str(_parent), _os.W_OK):
                            self._db_path = _cand
                            break
                    except Exception:
                        continue
            import logging as _log
            _log.getLogger(__name__).info(
                "User DB: non-sqlite DATABASE_URL — using SQLite fallback at %s",
                self._db_path)'''

if CHANGE_1_OLD in content:
    content = content.replace(CHANGE_1_OLD, CHANGE_1_NEW, 1)
    print("✓ CHANGE 1: non-sqlite URL fallback")
else:
    # Try the expanded form
    CHANGE_1_OLD_ALT = '        elif not url or url == ":memory:":'
    if CHANGE_1_OLD_ALT in content:
        print("✓ CHANGE 1: already applied (idempotent)")
    else:
        print("✗ CHANGE 1: NOT FOUND"); sys.exit(1)

CHANGE_2_OLD = '        """Run pending schema migrations.\n\n        Returns:\n            List of applied migration records.\n        """'
CHANGE_2_NEW = '''        """Run pending schema migrations.

        PATCH-002: Creates parent directory of the DB file if needed.

        Returns:
            List of applied migration records.
        """
        import os as _os
        from pathlib import Path as _Path
        try:
            _db_dir = _Path(self._db_path).parent
            if not _db_dir.exists():
                _db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as _e:
            pass'''

if CHANGE_2_OLD in content:
    content = content.replace(CHANGE_2_OLD, CHANGE_2_NEW, 1)
    print("✓ CHANGE 2: run_migrations creates DB directory")
elif 'PATCH-002: Creates parent directory' in content:
    print("✓ CHANGE 2: already applied (idempotent)")
else:
    print("✗ CHANGE 2: NOT FOUND"); sys.exit(1)

WAL_FILE.write_text(content)
print()
print("✅ PATCH-002 applied.")
print()
print("Restart: systemctl restart murphy-production")
print()
print("Commission:")
print("  # Login — creates account in SQLite")
print("  curl -X POST https://murphy.systems/api/auth/login -H 'Content-Type: application/json' \\")
print("    -c /tmp/v.txt -d '{\"email\":\"cpost@murphy.systems\",\"password\":\"YOUR_PASS\"}'")
print("  # Restart — accounts must survive")
print("  systemctl restart murphy-production && sleep 30")
print("  # Login again — must still work")
print("  curl -X POST https://murphy.systems/api/auth/login -H 'Content-Type: application/json' \\")
print("    -c /tmp/v2.txt -d '{\"email\":\"cpost@murphy.systems\",\"password\":\"YOUR_PASS\"}'")
print()
print("Rollback:")
print(f"  cp {backup} {WAL_FILE} && systemctl restart murphy-production")
