"""OS-FIN — Today aggregator.

Pulls top-N candidates from each domain, scores them by urgency × severity ×
recency, returns the top 3 (or top N) as the unified "what needs my
attention today" panel.

Scoring formula:
  score = base_score (per source) × severity_weight × recency_decay

  base_score by source:
    engagement.awaiting_attestation   → 0.9 (real practitioner blocking)
    engagement.flagged                → 0.95 (compliance attention needed)
    engagement.drafting               → 0.5
    boundary_drill.failure_impossible → 0.85 (founder retarget needed)
    boundary_drill.drilling           → 0.6
    cta.requires_hitl                 → 1.0
    cta.completion                    → confidence (typically 0.8)

  severity_weight: 1.0 baseline; 1.5 if requires_hitl; 0.7 if low-confidence

  recency_decay: max(0.3, 1.0 - hours_old/72)

Picks top 3 by default (configurable).
"""
import time
from typing import Dict, Any, List
from .rollups.work import rollup_work
from .rollups.founder import rollup_founder


def _hours_old(epoch_seconds: float) -> float:
    if not epoch_seconds:
        return 0.0
    return max(0.0, (time.time() - float(epoch_seconds)) / 3600.0)


def _score_engagement(item: Dict[str, Any]) -> float:
    state = (item.get("state") or "").lower()
    base = {
        "awaiting_attestation": 0.9,
        "flagged": 0.95,
        "drafting": 0.5,
        "outreach_queued": 0.6,
        "finalized": 0.4,
        "verified": 0.1,
        "declined": 0.2,
    }.get(state, 0.5)
    recency = max(0.3, 1.0 - _hours_old(item.get("updated_at", 0)) / 72.0)
    return round(base * recency, 4)


def _score_drill(item: Dict[str, Any]) -> float:
    state = (item.get("state") or "").lower()
    base = {
        "failure_impossible": 0.85,
        "drilling": 0.6,
        "pending": 0.3,
        "success": 0.1,
    }.get(state, 0.4)
    # Solved ratio inversely scores — stalled drills get higher attention
    sr = item.get("solved_ratio")
    if sr is not None and sr < 0.5:
        base *= 1.2
    recency = max(0.3, 1.0 - _hours_old(item.get("created_at", 0)) / 72.0)
    return round(base * recency, 4)


def _score_cta(item: Dict[str, Any]) -> float:
    conf = item.get("confidence") or 0.5
    weight = 1.5 if item.get("requires_hitl") else 1.0
    # CTAs use suggested_at_ns (nanoseconds)
    ns = item.get("suggested_at_ns") or 0
    if ns:
        hours = max(0.0, (time.time() - ns / 1e9) / 3600.0)
        recency = max(0.3, 1.0 - hours / 72.0)
    else:
        recency = 0.5
    return round(conf * weight * recency, 4)


def build_today(top_n: int = 3) -> Dict[str, Any]:
    """Build the Today panel — top N items across all domains."""
    scored: List[Dict[str, Any]] = []

    # Pull work domain
    try:
        work = rollup_work()
        for item in (work.get("items") or []):
            t = item.get("type")
            if t == "engagement":
                s = _score_engagement(item)
                if s > 0:
                    scored.append({
                        "id": item.get("id"),
                        "score": s,
                        "type": t,
                        "title": item.get("title"),
                        "state": item.get("state"),
                        "domain": "work",
                        "source_item": item,
                    })
            elif t == "boundary_drill":
                s = _score_drill(item)
                if s > 0:
                    scored.append({
                        "id": item.get("id"),
                        "score": s,
                        "type": t,
                        "title": item.get("title"),
                        "state": item.get("state"),
                        "domain": "work",
                        "source_item": item,
                    })
    except Exception as e:
        pass

    # Pull founder domain (CTAs)
    try:
        founder = rollup_founder()
        for item in (founder.get("items") or []):
            s = _score_cta(item)
            if s > 0:
                scored.append({
                    "id": item.get("id"),
                    "score": s,
                    "type": item.get("type"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "domain": "founder",
                    "source_item": item,
                })
    except Exception:
        pass

    # Sort by score desc
    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:top_n]

    return {
        "today": top,
        "total_candidates": len(scored),
        "domains_scanned": ["work", "founder"],
        "scoring_formula": "base_score × severity_weight × recency_decay",
    }
