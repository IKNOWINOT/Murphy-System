"""PCR-090f.1 — Claim extractor (regex pass, multi-source).

Scans multiple LLM response sources, not just one log table.
"""
import logging
import re
import sqlite3
import time
from typing import List, Dict, Any, Optional, Tuple

from .claim_ledger import insert_claim

LOG = logging.getLogger("murphy.antibody.extractor")

# Sources of LLM-generated text in production
_SOURCES = [
    # (db_path, table, response_col, id_col, ts_col, agent_col)
    ("/var/lib/murphy-production/dispatch_jobs.db", "dispatch_jobs",
     "response_json", "job_id", "finished_at", None),
    ("/var/lib/murphy-production/rosetta_ml_study.db", "study_runs",
     "response_text", "id", None, "soul_agent"),
    ("/var/lib/murphy-production/swarm_canvas.db", "canvas_steps",
     "output", "id", "completed_at", "agent_name"),
    ("/var/lib/murphy-production/rnd_stream.db", "rnd_findings",
     "content", "id", "created_at", "agent_id"),
]


_PATTERNS = [
    (re.compile(r"\b(?:table|the table)\s+`?([a-z_][a-z0-9_]*)`?\s+(?:exists|is present|is in)\b", re.I),
     "table", "exists", lambda m: (m.group(1), "true")),
    (re.compile(r"`([a-z_][a-z0-9_]*)`\s+table\b", re.I),
     "table", "exists", lambda m: (m.group(1), "true")),
    (re.compile(r"\b(?:endpoint|route)\s+`?(/api/[a-z0-9/_-]+)`?", re.I),
     "endpoint", "exists", lambda m: (m.group(1), "true")),
    (re.compile(r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/api/[a-z0-9/_-]+)", re.I),
     "endpoint", "exists", lambda m: (m.group(1), "true")),
    (re.compile(r"\b(?:file|module)\s+(?:at\s+)?`?(/[a-z0-9/_.-]+\.(?:py|md|json|yml|yaml|sh|html|sql))`?", re.I),
     "file", "exists", lambda m: (m.group(1), "true")),
    (re.compile(r"\b([a-z_][a-z0-9_]*)\s+(?:has|contains)\s+(?:a\s+)?column\s+`?([a-z_][a-z0-9_]*)`?", re.I),
     "schema", "has_column", lambda m: (f"{m.group(1)}.{m.group(2)}", "true")),
    (re.compile(r"\b(?:there are|there is|count of|total)\s+(\d+)\s+([a-z_][a-z0-9_]+)\b", re.I),
     "metric", "count", lambda m: (m.group(2), m.group(1))),
]


def extract_claims_from_text(text: str, source_agent: str = "", source_call_id: str = "") -> List[str]:
    if not text or len(text) < 20:
        return []
    inserted = []
    seen = set()
    for pattern, claim_type, predicate, extractor in _PATTERNS:
        for match in pattern.finditer(text):
            try:
                subject, object_value = extractor(match)
            except Exception:
                continue
            key = (claim_type, subject, predicate, object_value)
            if key in seen:
                continue
            seen.add(key)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            snippet = text[start:end].strip()
            try:
                cid = insert_claim(
                    text=snippet,
                    claim_type=claim_type,
                    subject=subject,
                    predicate=predicate,
                    object_value=object_value,
                    source_agent=source_agent or "unknown",
                    source_call_id=source_call_id or None,
                    confidence=0.6,
                )
                inserted.append(cid)
            except Exception as e:
                LOG.warning("AB_E001 insert: %s", e)
    return inserted


def scan_source(db_path: str, table: str, response_col: str,
                id_col: str, ts_col: Optional[str], agent_col: Optional[str],
                max_rows: int = 100) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
    except Exception as e:
        return {"source": db_path, "error": str(e), "rows": 0, "claims": 0}
    try:
        # Build column list, omit missing cols safely
        cols_info = conn.execute(f"PRAGMA table_info(\"{table}\")").fetchall()
        col_names = [c[1] for c in cols_info]
        sel_cols = [response_col, id_col]
        if agent_col and agent_col in col_names:
            sel_cols.append(agent_col)
        else:
            agent_col = None
        sql = f"SELECT {', '.join(sel_cols)} FROM \"{table}\" ORDER BY rowid DESC LIMIT {max_rows}"
        rows = conn.execute(sql).fetchall()
    except Exception as e:
        return {"source": db_path, "error": str(e), "rows": 0, "claims": 0}
    finally:
        conn.close()

    total_claims = 0
    rows_with_text = 0
    for row in rows:
        text = row[0]
        if not text:
            continue
        rows_with_text += 1
        rid = row[1]
        agent = row[2] if len(row) > 2 and agent_col else f"{table}"
        claims = extract_claims_from_text(str(text), source_agent=str(agent), source_call_id=str(rid))
        total_claims += len(claims)

    return {
        "source": f"{db_path.split('/')[-1]}:{table}",
        "rows_scanned": len(rows),
        "rows_with_text": rows_with_text,
        "claims_extracted": total_claims,
    }


def run_extractor_tick(max_rows_per_source: int = 50) -> Dict[str, Any]:
    LOG.info("PCR-090f.1: extractor tick start")
    results = []
    total = 0
    for src in _SOURCES:
        r = scan_source(*src, max_rows=max_rows_per_source)
        results.append(r)
        total += r.get("claims_extracted", 0)
    LOG.info("PCR-090f.1: extractor tick done — %d claims across %d sources", total, len(results))
    return {"total_claims_extracted": total, "by_source": results}
