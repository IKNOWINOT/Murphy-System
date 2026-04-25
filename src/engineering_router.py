"""
Engineering Intelligence Router — PATCH-080c
REST API for document ingestion, paper fetching, and engineering queries.

Endpoints:
  POST /api/eng/ingest          — upload + ingest a document (PDF/DOCX/XLSX/DXF)
  GET  /api/eng/documents       — list all ingested documents
  POST /api/eng/query           — RAG query against ingested docs
  POST /api/eng/papers/search   — search arXiv papers
  POST /api/eng/papers/fetch    — batch fetch domain papers into KG
  GET  /api/eng/papers/list     — list fetched papers
  POST /api/eng/estimate        — parse estimating spreadsheet + summarize

PATCH-080c | Label: ENG-ROUTER-001
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/eng", tags=["engineering"])

UPLOAD_DIR = Path(os.environ.get("MURPHY_UPLOAD_DIR", "/var/lib/murphy-production/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MANIFEST_PATH = UPLOAD_DIR / "manifest.json"


def _load_manifest() -> List[Dict]:
    try:
        return json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else []
    except Exception:
        return []


def _save_manifest(manifest: List[Dict]) -> None:
    try:
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    except Exception as exc:
        logger.error("ENG-ROUTER: manifest save failed: %s", exc)


# ── Ingest document ──────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest_document(
    file: UploadFile = File(...),
    discipline: Optional[str] = Form(default=""),
    project: Optional[str] = Form(default=""),
    notes: Optional[str] = Form(default=""),
):
    """
    Upload and ingest an engineering document.
    Supported: PDF, DOCX, XLSX, DXF
    """
    try:
        from src.doc_ingest_engine import ingest_file, store_in_knowledge_graph

        # Save upload
        dest = UPLOAD_DIR / file.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # Ingest
        result = ingest_file(str(dest))

        # Override discipline if provided
        if discipline:
            result.discipline = discipline

        # Store in KG
        kg_stored = store_in_knowledge_graph(result)

        # Update manifest
        manifest = _load_manifest()
        manifest.append({
            "doc_id": result.doc_id,
            "filename": result.filename,
            "file_type": result.file_type,
            "discipline": result.discipline,
            "drawing_number": result.drawing_number,
            "revision": result.revision,
            "title": result.title,
            "chunks": len(result.chunks),
            "tables": len(result.tables),
            "project": project,
            "notes": notes,
            "kg_stored": kg_stored,
            "ok": result.ok,
            "error": result.error,
        })
        _save_manifest(manifest)

        return JSONResponse({
            "ok": result.ok,
            "doc_id": result.doc_id,
            "filename": result.filename,
            "discipline": result.discipline,
            "drawing_number": result.drawing_number,
            "chunks": len(result.chunks),
            "tables": len(result.tables),
            "kg_stored": kg_stored,
            "error": result.error,
        })
    except Exception as exc:
        logger.error("ENG-ROUTER: ingest failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── List documents ───────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents(discipline: Optional[str] = None, project: Optional[str] = None):
    """List all ingested engineering documents."""
    manifest = _load_manifest()
    if discipline:
        manifest = [d for d in manifest if d.get("discipline") == discipline]
    if project:
        manifest = [d for d in manifest if d.get("project") == project]
    return JSONResponse({"ok": True, "count": len(manifest), "documents": manifest})


# ── RAG query ────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    discipline: Optional[str] = None
    project: Optional[str] = None
    top_k: int = 5

@router.post("/query")
async def engineering_query(req: QueryRequest):
    """
    Ask a question against ingested engineering documents.
    Returns relevant chunks + LLM-synthesized answer.
    """
    try:
        from src.murphy_memory_palace import MemoryPalace
        palace = MemoryPalace()
        raw_results = palace.search(req.question, top_k=req.top_k)

        # HybridSearchResult objects — extract content + source
        results = []
        for r in raw_results:
            content = getattr(r, "content", "") or r.get("content", "") if isinstance(r, dict) else getattr(r, "content", "")
            source = getattr(r, "source", "") or r.get("source", "") if isinstance(r, dict) else getattr(r, "source", "")
            meta = getattr(r, "metadata", {}) or r.get("metadata", {}) if isinstance(r, dict) else getattr(r, "metadata", {})
            results.append({"content": content, "source": source, "metadata": meta})

        # Filter by discipline if specified
        if req.discipline:
            results = [r for r in results
                       if r.get("metadata", {}).get("discipline") == req.discipline]

        context = "\n\n".join(r.get("content", "")[:600] for r in results[:5])
        sources = [r.get("source", "") for r in results]

        # LLM synthesis
        answer = ""
        try:
            from src.llm_controller import LLMController, LLMRequest
            ctrl = LLMController()
            llm_req = LLMRequest(
                prompt=f"Engineering documents context:\n{context}\n\nQuestion: {req.question}\n\nProvide a precise engineering answer based on the documents provided.",
                max_tokens=800,
            )
            import asyncio
            resp = asyncio.run(ctrl.query_llm(llm_req))
            answer = resp.content if resp else ""
        except Exception as llm_exc:
            logger.warning("ENG-ROUTER: LLM synthesis failed: %s", llm_exc)
            answer = context[:1000]

        return JSONResponse({
            "ok": True,
            "question": req.question,
            "answer": answer,
            "sources": sources,
            "chunks_used": len(results),
        })
    except Exception as exc:
        logger.error("ENG-ROUTER: query failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Paper search ─────────────────────────────────────────────────────────────

class PaperSearchRequest(BaseModel):
    query: str
    domain: str = "general"
    max_results: int = 10

@router.post("/papers/search")
async def search_papers(req: PaperSearchRequest):
    """Search arXiv for engineering/science papers."""
    try:
        from src.science_paper_fetcher import search_papers as _search
        papers = _search(req.query, domain=req.domain, max_results=req.max_results)
        return JSONResponse({
            "ok": True,
            "query": req.query,
            "count": len(papers),
            "papers": [
                {"id": p.paper_id, "title": p.title, "authors": p.authors[:3],
                 "abstract": p.abstract[:300], "published": p.published,
                 "pdf_url": p.pdf_url, "categories": p.categories}
                for p in papers
            ],
        })
    except Exception as exc:
        logger.error("ENG-ROUTER: paper search failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Batch domain fetch ───────────────────────────────────────────────────────

class BatchFetchRequest(BaseModel):
    domain: str          # mechanical | electrical | structural | materials | ai_engineering
    max_papers: int = 10
    download_pdf: bool = False

@router.post("/papers/fetch")
async def batch_fetch_papers(req: BatchFetchRequest):
    """
    Batch fetch papers for an engineering domain into the KG.
    Runs async — returns immediately with job info.
    """
    try:
        import threading
        from src.science_paper_fetcher import batch_fetch_domain
        
        result_box = {}
        
        def _run():
            result_box["result"] = batch_fetch_domain(
                req.domain, req.max_papers, req.download_pdf
            )
        
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=120)
        
        if "result" in result_box:
            return JSONResponse({"ok": True, **result_box["result"]})
        else:
            return JSONResponse({"ok": False, "error": "fetch timed out"}, status_code=504)
    except Exception as exc:
        logger.error("ENG-ROUTER: batch fetch failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Estimate parser ──────────────────────────────────────────────────────────

@router.post("/estimate")
async def parse_estimate(file: UploadFile = File(...)):
    """
    Upload an estimating spreadsheet (XLSX) and get a structured summary.
    Extracts: line items, quantities, unit costs, totals by trade.
    """
    try:
        from src.doc_ingest_engine import ingest_xlsx
        import openpyxl

        dest = UPLOAD_DIR / file.filename
        with dest.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        result = ingest_xlsx(str(dest))

        # Try to identify cost columns
        summary = {"file": file.filename, "sheets": [], "total_rows": 0}
        for table in result.tables:
            sheet_info = {"sheet": table["sheet"], "rows": len(table["data"])}
            # Find header row
            if table["data"]:
                sheet_info["headers"] = table["data"][0]
                sheet_info["sample_rows"] = table["data"][1:4]
            summary["sheets"].append(sheet_info)
            summary["total_rows"] += len(table["data"])

        # LLM summary of the estimate
        context = "\n".join(
            " | ".join(str(c) for c in row)
            for table in result.tables
            for row in table["data"][:30]
        )
        estimate_summary = ""
        try:
            from src.llm_controller import LLMController, LLMRequest
            ctrl = LLMController()
            llm_req = LLMRequest(
                prompt=f"Estimating spreadsheet data:\n{context}\n\nProvide: 1) Total estimated cost, 2) Major trade breakdown, 3) Key line items, 4) Any gaps or missing items noticed.",
                max_tokens=600,
            )
            import asyncio
            resp = asyncio.run(ctrl.query_llm(llm_req))
            estimate_summary = resp.content if resp else ""
        except Exception:
            pass

        return JSONResponse({
            "ok": result.ok,
            "filename": file.filename,
            "summary": summary,
            "llm_analysis": estimate_summary,
            "chunks": len(result.chunks),
        })
    except Exception as exc:
        logger.error("ENG-ROUTER: estimate parse failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
