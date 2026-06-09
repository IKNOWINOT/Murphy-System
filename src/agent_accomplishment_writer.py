"""
agent_accomplishment_writer.py — PCR-045b

Persistent-agent writer. Called from the dispatch loop after a graph
node fires (success OR fail) to append an accomplishment row to the
agent_accomplishments table created by PCR-045a.

ARCHITECTURE:
  - Standalone module — keeps app.py untouched except for the 2 call
    sites added by the marker patcher (scripts/pcr045b_wire_writer.py).
  - Fail-soft: any DB error is logged but never raised. The dispatch
    loop must never break because the accomplishments writer hiccupped.
  - Append-only. Never updates or deletes.

WHAT GETS RECORDED:
  Every time an agent fires a graph node (pass 1 OR refinement), one
  row per output_type produced. The (role_class, domain, success,
  task_keywords) tuple is the signal PCR-045c will query against for
  cross-domain reuse.

KEYWORD EXTRACTION:
  Light stop-word filtering. We're not building a search engine, just
  a coarse content signal. The role + domain pair carries most of the
  match weight; keywords are tie-breakers for cross-domain reuse.

REUSE POLICY (per founder go, 2026-06-09 00:15 PT):
  Cross-domain reuse is the default. An agent's accomplishments are
  the signal, not their original assignment.

PUBLIC API:
  record_accomplishment(profile_id, role_class, domain, task_prompt,
                        output_type, output_content, success,
                        pass_number, elapsed_us, refined_from=None,
                        error=None) -> Optional[str]
    Returns accomplishment_id on success, None on any failure.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import time
from typing import Any, List, Optional

logger = logging.getLogger("murphy.accomplishment_writer")

DB_PATH = "/var/lib/murphy-production/murphy_identity.db"

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "should", "could", "may", "might", "must", "can",
    "of", "to", "in", "on", "at", "by", "for", "with", "about", "as",
    "from", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "up", "down", "over", "under", "this",
    "that", "these", "those", "i", "you", "he", "she", "it", "we",
    "they", "what", "which", "who", "whom", "whose", "me", "my", "your",
    "his", "her", "its", "our", "their", "some", "any", "all", "no",
    "not", "so", "if", "then", "than", "very", "just", "now", "also",
    "make", "made", "get", "got", "go", "going", "want", "need", "needs",
    "please", "thanks", "thank", "hi", "hello", "hey",
})


def _extract_keywords(text: str, max_kw: int = 10) -> List[str]:
    """Light keyword extraction — lowercased non-stopword tokens >= 3 chars."""
    if not text:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    seen = set()
    out: List[str] = []
    for t in tokens:
        if t in _STOPWORDS:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_kw:
            break
    return out


def _summarize_output(content: Any, limit: int = 500) -> str:
    """Render output to a short string for the accomplishment record."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content[:limit]
    try:
        return json.dumps(content, ensure_ascii=False, default=str)[:limit]
    except Exception:
        return str(content)[:limit]


def record_accomplishment(
    profile_id: str,
    role_class: str,
    domain: str,
    task_prompt: str,
    output_type: str,
    output_content: Any,
    success: bool,
    pass_number: int = 1,
    elapsed_us: int = 0,
    refined_from: Optional[str] = None,
    error: Optional[str] = None,
) -> Optional[str]:
    """
    Append one accomplishment row. Returns the new accomplishment_id,
    or None on any failure (writer is fail-soft).
    """
    try:
        now = time.time()
        # Build a stable but unique id
        # Microsecond resolution + a 4-byte random salt to keep IDs unique
        # even when multiple outputs are recorded in the same instant (a
        # common case: an agent emits 3 outputs back-to-back).
        import os as _os_045b
        sig = "{}|{}|{}|{}|{}|{}".format(
            profile_id, role_class, output_type, int(now * 1_000_000),
            pass_number, _os_045b.urandom(4).hex()
        )
        acc_id = "acc_" + hashlib.md5(sig.encode("utf-8")).hexdigest()[:16]

        kw = _extract_keywords(task_prompt or "")
        summary = _summarize_output(output_content)
        if error and not success:
            # Surface the error in the summary for future reuse decisions
            summary = ("[ERROR] " + str(error)[:200] + " | " + summary)[:500]

        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO agent_accomplishments (
                    accomplishment_id, profile_id, role_class, domain,
                    task_prompt, task_keywords, output_type, output_summary,
                    success, pass_number, refined_from, fired_at, elapsed_us
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    acc_id,
                    profile_id or "anonymous",
                    role_class or "Unknown",
                    domain or "general",
                    (task_prompt or "")[:2000],
                    json.dumps(kw),
                    output_type or "deliverable",
                    summary,
                    1 if success else 0,
                    int(pass_number),
                    refined_from,
                    now,
                    int(elapsed_us or 0),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # EXEC-04 (2026-06-09): publish to cadence + propose CTA on success.
        # Fail-soft — pulse/CTA errors never break the accomplishment write.
        try:
            from src.cadence_emit import emit_heartbeat
            emit_heartbeat(
                source="agent.{}.{}".format(role_class or "unknown",
                                            domain or "general"),
                success=bool(success),
                payload={
                    "accomplishment_id": acc_id,
                    "output_type":       output_type or "deliverable",
                    "pass_number":       int(pass_number),
                    "elapsed_ms":        round((elapsed_us or 0) / 1000, 2),
                    "refined_from":      refined_from,
                },
            )
        except Exception as _pulse_exc:
            logger.debug("EXEC-04 pulse emit skipped: %s", _pulse_exc)

        try:
            from src.executive_cta import propose_completion_cta
            # Quality heuristic: refinement passes get higher confidence
            # (the system already self-corrected); first-pass success gets
            # the baseline 0.80. Errors are filtered upstream by success=False.
            _quality = 0.85 if (pass_number or 1) > 1 else 0.80
            propose_completion_cta(
                role=role_class or "unknown",
                domain=domain or "general",
                output_type=output_type or "deliverable",
                accomplishment_id=acc_id,
                success=bool(success),
                quality_score=_quality,
            )
        except Exception as _cta_exc:
            logger.debug("EXEC-04 CTA propose skipped: %s", _cta_exc)

        return acc_id
    except sqlite3.OperationalError as e:
        # Table might not exist (PCR-045a not applied) — log once, don't raise.
        logger.warning("accomplishment write skipped: %s", e)
        return None
    except Exception as e:
        logger.warning("accomplishment write failed: %s", e)
        return None


# ── for PCR-045c lookup (read API, no-op until 045c calls it) ──
def find_reusable_agents(
    role_class: str,
    task_prompt: str = "",
    limit: int = 5,
    min_success_count: int = 1,
) -> List[dict]:
    """
    Find existing agents (by profile_id) who have successful
    accomplishments matching this role_class, optionally ranked by
    keyword overlap with task_prompt.

    Cross-domain by default — accomplishments are the signal, not
    the original assignment.

    Returns a list of dicts ranked by (success_count, keyword_overlap).
    Empty list on any failure or no matches.
    """
    try:
        kw_target = set(_extract_keywords(task_prompt or ""))
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT profile_id, COUNT(*) as success_count,
                       GROUP_CONCAT(DISTINCT domain) as domains,
                       GROUP_CONCAT(task_keywords, '|||') as all_keywords,
                       MAX(fired_at) as last_fired
                FROM agent_accomplishments
                WHERE role_class = ? AND success = 1
                GROUP BY profile_id
                HAVING success_count >= ?
                ORDER BY last_fired DESC
                """,
                (role_class, min_success_count),
            )
            rows = cur.fetchall()
        finally:
            conn.close()

        scored = []
        for profile_id, success_count, domains, all_kw_blob, last_fired in rows:
            # Compute keyword overlap if task_prompt provided
            overlap = 0
            if kw_target and all_kw_blob:
                seen_kw = set()
                for chunk in (all_kw_blob or "").split("|||"):
                    try:
                        for k in json.loads(chunk):
                            seen_kw.add(k)
                    except Exception:
                        pass
                overlap = len(kw_target & seen_kw)
            scored.append({
                "profile_id": profile_id,
                "success_count": success_count,
                "domains": (domains or "").split(",") if domains else [],
                "keyword_overlap": overlap,
                "last_fired": last_fired,
            })
        scored.sort(
            key=lambda r: (r["keyword_overlap"], r["success_count"], r["last_fired"] or 0),
            reverse=True,
        )
        return scored[:limit]
    except Exception as e:
        logger.warning("find_reusable_agents failed: %s", e)
        return []
