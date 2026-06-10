"""Learning domain — corpus, perspectives, corrections, success maps."""
import sqlite3
from typing import Dict, Any, List

ENGAGEMENT_DB = "/var/lib/murphy-production/engagement_folders.db"
ROSETTA_DB = "/var/lib/murphy-production/rosetta_learning.db"


def _safe_query(db_path: str, sql: str, params=()) -> List[tuple]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception:
        return []


def rollup_learning(tenant_id: str | None = None) -> Dict[str, Any]:
    corpus_rows = _safe_query(
        ENGAGEMENT_DB,
        "SELECT COUNT(*) FROM practitioner_corpus",
    )
    corrections_rows = _safe_query(
        ROSETTA_DB,
        "SELECT COUNT(*) FROM agent_corrections",
    )
    success_rows = _safe_query(
        ROSETTA_DB,
        "SELECT COUNT(*) FROM agent_success_map",
    )
    summary = {
        "practitioner_corpus_rows": corpus_rows[0][0] if corpus_rows else 0,
        "agent_corrections": corrections_rows[0][0] if corrections_rows else 0,
        "agent_success_map": success_rows[0][0] if success_rows else 0,
        "perspectives_extracted": 0,  # PCR-070 will fill
    }
    return {
        "summary": summary,
        "items": [],
        "raw_endpoints": [
            "/api/corpus/practitioner",
            "/api/rosetta/learn/corrections",
            "/api/shadow/observations",
        ],
    }
