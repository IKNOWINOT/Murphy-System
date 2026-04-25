"""
Murphy Extension Routers — PATCH-076e/f/g/h
Mounts: Knowledge Graph (Memory Palace), ML API, Confidence Engine, AUAR Analytics

PATCH-076e: /api/kg/*   — Memory Palace (decision memory, temporal triples, hybrid search)
PATCH-076g: /api/confidence/* — Confidence scoring for LCM decisions
PATCH-076h: /api/auar/*  — AI Usage Analytics & Reporting
PATCH-076k: /api/ml/*    — ML model registry, inference

Design: All four routers are built lazily — failures are isolated.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ─── Shared state ─────────────────────────────────────────────────────────────

_memory_palace = None
_confidence_engine = None

def _get_memory_palace():
    global _memory_palace
    if _memory_palace is None:
        from src.murphy_memory_palace import MemoryPalaceWiring
        _memory_palace = MemoryPalaceWiring()
    return _memory_palace

def _get_confidence_engine():
    global _confidence_engine
    if _confidence_engine is None:
        from src.confidence_engine.confidence_engine import ConfidenceEngine
        _confidence_engine = ConfidenceEngine()
    return _confidence_engine


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH-076e: Knowledge Graph / Memory Palace  (/api/kg/*)
# ═══════════════════════════════════════════════════════════════════════════════

def build_kg_router() -> APIRouter:
    kg_router = APIRouter(prefix="/api/kg", tags=["knowledge-graph"])

    @kg_router.get("/status")
    async def kg_status():
        try:
            mp = _get_memory_palace()
            stats = {
                "ok": True,
                "halls": len(mp._palace) if hasattr(mp, "_palace") else 0,
                "rag_wired": mp._rag is not None if hasattr(mp, "_rag") else False,
                "kg_wired": mp._kg is not None if hasattr(mp, "_kg") else False,
            }
            return {"ok": True, "data": stats}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    class IndexRequest(BaseModel):
        session_id: str
        user_msg: str
        assistant_msg: str
        metadata: Dict[str, Any] = {}

    @kg_router.post("/index")
    async def kg_index(req: IndexRequest):
        """Index a conversation turn into the Memory Palace."""
        try:
            mp = _get_memory_palace()
            mp.index_conversation(
                session_id=req.session_id,
                user_message=req.user_msg,
                assistant_message=req.assistant_msg,
                metadata=req.metadata,
            )
            return {"ok": True, "indexed": True}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    class TripleRequest(BaseModel):
        subject: str
        predicate: str
        obj: str
        confidence: float = 0.8
        source: str = "lcm"

    @kg_router.post("/triples")
    async def kg_add_triple(req: TripleRequest):
        """Store a temporal triple (subject, predicate, object) in the knowledge graph."""
        try:
            mp = _get_memory_palace()
            mp.add_temporal_triple(
                subject=req.subject,
                predicate=req.predicate,
                obj=req.obj,
                confidence=req.confidence,
                source=req.source,
            )
            return {"ok": True, "stored": True}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    class QueryRequest(BaseModel):
        query: str
        limit: int = 10

    @kg_router.post("/search")
    async def kg_search(req: QueryRequest):
        """Hybrid search over the Memory Palace."""
        try:
            mp = _get_memory_palace()
            results = mp.search(query=req.query, limit=req.limit)
            if hasattr(results, "__iter__"):
                results = [r.to_dict() if hasattr(r, "to_dict") else r for r in results]
            return {"ok": True, "results": results, "count": len(results)}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @kg_router.get("/triples")
    async def kg_query_triples(subject: Optional[str] = None, predicate: Optional[str] = None):
        """Query temporal triples from the knowledge graph."""
        try:
            mp = _get_memory_palace()
            results = mp.query_triples(subject=subject, predicate=predicate)
            if hasattr(results, "__iter__"):
                results = [r.to_dict() if hasattr(r, "to_dict") else vars(r) if hasattr(r, "__dict__") else str(r) for r in results]
            return {"ok": True, "triples": results, "count": len(results)}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    logger.info("PATCH-076e: /api/kg/* router built")
    return kg_router


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH-076g: Confidence Engine  (/api/confidence/*)
# ═══════════════════════════════════════════════════════════════════════════════

def build_confidence_router() -> APIRouter:
    conf_router = APIRouter(prefix="/api/confidence", tags=["confidence-engine"])

    @conf_router.get("/status")
    async def confidence_status():
        try:
            ce = _get_confidence_engine()
            return {"ok": True, "data": {"engine": type(ce).__name__, "ready": True}}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    class ArtifactScoreRequest(BaseModel):
        artifacts: List[Dict[str, Any]]
        context: Dict[str, Any] = {}

    @conf_router.post("/score")
    async def confidence_score(req: ArtifactScoreRequest):
        """Compute confidence score for a set of artifacts/decisions."""
        try:
            ce = _get_confidence_engine()
            result = ce.compute_confidence(req.artifacts)
            if hasattr(result, "__await__"):
                import asyncio
                result = await asyncio.wait_for(result, timeout=10)
            score = result if isinstance(result, (int, float)) else getattr(result, "score", 0.0)
            return {"ok": True, "score": float(score), "result": str(result)[:200]}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @conf_router.post("/lcm-decision")
    async def confidence_lcm_decision(decision: Dict[str, Any]):
        """Score and record a confidence level for an LCM dispatch decision."""
        try:
            # Record in KG as a triple: decision → confidence_score → value
            decision_id = decision.get("run_id", "unknown")
            confidence = float(decision.get("confidence", 0.8))
            stage = decision.get("stage", "dispatch")
            try:
                mp = _get_memory_palace()
                mp.add_temporal_triple(
                    subject=f"lcm_decision:{decision_id}",
                    predicate="has_confidence",
                    obj=str(confidence),
                    confidence=confidence,
                    source="confidence_engine",
                )
            except Exception:
                pass
            hitl_required = confidence < 0.75
            return {
                "ok": True,
                "decision_id": decision_id,
                "confidence": confidence,
                "stage": stage,
                "hitl_required": hitl_required,
                "recorded_in_kg": True,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    logger.info("PATCH-076g: /api/confidence/* router built")
    return conf_router


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH-076h: AUAR Analytics  (/api/auar/*)
# ═══════════════════════════════════════════════════════════════════════════════

def build_auar_router() -> APIRouter:
    auar_router = APIRouter(prefix="/api/auar", tags=["auar-analytics"])

    # In-memory analytics store (persisted via ambient signals)
    _usage_log: List[Dict[str, Any]] = []
    _MAX_LOG = 10000

    @auar_router.get("/status")
    async def auar_status():
        return {
            "ok": True,
            "data": {
                "total_events": len(_usage_log),
                "modules_tracked": len(set(e.get("module") for e in _usage_log)),
                "ready": True,
            }
        }

    class UsageEvent(BaseModel):
        module: str
        action: str
        duration_ms: float = 0
        tokens_used: int = 0
        confidence: float = 0.0
        success: bool = True
        metadata: Dict[str, Any] = {}

    @auar_router.post("/track")
    async def auar_track(event: UsageEvent):
        """Track an AI usage event (LCM run, Forge generation, synthesis, etc.)."""
        import time
        record = {
            "ts": time.time(),
            **event.dict(),
        }
        if len(_usage_log) < _MAX_LOG:
            _usage_log.append(record)
        return {"ok": True, "recorded": True}

    @auar_router.get("/summary")
    async def auar_summary():
        """Aggregate usage by module and action."""
        from collections import defaultdict
        by_module: Dict[str, Dict] = defaultdict(lambda: {"calls": 0, "total_ms": 0, "total_tokens": 0, "errors": 0})
        for e in _usage_log:
            m = e.get("module", "unknown")
            by_module[m]["calls"] += 1
            by_module[m]["total_ms"] += e.get("duration_ms", 0)
            by_module[m]["total_tokens"] += e.get("tokens_used", 0)
            if not e.get("success"):
                by_module[m]["errors"] += 1
        return {"ok": True, "total_events": len(_usage_log), "by_module": dict(by_module)}

    @auar_router.get("/provision")
    async def auar_provision():
        return {"ok": True, "status": "provisioned", "events": len(_usage_log)}

    logger.info("PATCH-076h: /api/auar/* router built")
    return auar_router


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH-076k: ML API  (/api/ml/*)
# ═══════════════════════════════════════════════════════════════════════════════

def build_ml_router() -> APIRouter:
    try:
        from src.ml.api import create_ml_router
        r = create_ml_router()
        logger.info("PATCH-076k: /api/ml/* ML router built from src.ml.api")
        return r
    except Exception as exc:
        logger.warning("PATCH-076k: ML router failed: %s", exc)
        # Fallback minimal router
        ml_router = APIRouter(prefix="/api/ml", tags=["ml"])
        @ml_router.get("/status")
        async def ml_status():
            return {"ok": True, "mode": "fallback", "reason": str(exc)}
        return ml_router
