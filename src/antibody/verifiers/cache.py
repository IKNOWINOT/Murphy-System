"""PCR-090g.0 — Tier 1 in-memory cache for fast ground-truth lookups.

Refreshed every 60s in the background. Backed by:
  - registry_db_inventory (tables across all dbs)
  - app route registry (endpoints)
  - sqlite_master snapshots (schemas)
"""
import logging
import sqlite3
import threading
import time
from typing import Dict, Set, Optional

LOG = logging.getLogger("murphy.antibody.cache")

REGISTRY_DB = "/var/lib/murphy-production/murphy_registry.db"

# Cached snapshots
_TABLES: Set[str] = set()             # all known table names across all dbs
_TABLE_TO_DB: Dict[str, str] = {}     # table_name -> first db_path that contains it
_LAST_REFRESH: float = 0.0
_REFRESH_LOCK = threading.Lock()
_TTL_SECONDS = 60


def _do_refresh():
    global _TABLES, _TABLE_TO_DB, _LAST_REFRESH
    try:
        conn = sqlite3.connect(f"file:{REGISTRY_DB}?mode=ro", uri=True, timeout=2.0)
    except Exception as e:
        LOG.warning("AB_E003 cache refresh — cannot open registry: %s", e)
        return
    try:
        rows = conn.execute(
            "SELECT db_path, table_names FROM registry_db_inventory WHERE table_names IS NOT NULL"
        ).fetchall()
    except Exception as e:
        LOG.warning("AB_E003 cache refresh: %s", e)
        conn.close()
        return
    finally:
        conn.close()

    new_tables: Set[str] = set()
    new_map: Dict[str, str] = {}
    for db_path, table_names in rows:
        if not table_names:
            continue
        for t in str(table_names).split(","):
            t = t.strip()
            if t and not t.startswith("sqlite_"):
                new_tables.add(t)
                if t not in new_map:
                    new_map[t] = db_path
    _TABLES = new_tables
    _TABLE_TO_DB = new_map
    _LAST_REFRESH = time.time()
    LOG.info("PCR-090g.0 cache refreshed: %d tables across %d dbs",
             len(new_tables), len(set(new_map.values())))


def refresh_if_stale():
    with _REFRESH_LOCK:
        if time.time() - _LAST_REFRESH > _TTL_SECONDS:
            _do_refresh()


def known_tables() -> Set[str]:
    refresh_if_stale()
    return _TABLES


def table_to_db(table_name: str) -> Optional[str]:
    refresh_if_stale()
    return _TABLE_TO_DB.get(table_name)


def cache_stats() -> Dict[str, int]:
    refresh_if_stale()
    return {
        "tables_cached": len(_TABLES),
        "dbs_cached": len(set(_TABLE_TO_DB.values())),
        "age_seconds": int(time.time() - _LAST_REFRESH),
    }
