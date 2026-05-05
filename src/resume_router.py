"""
resume_router.py — Resume Builder API (PATCH-193)
Mounts at /api/resume/*
"""
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional
import logging, os, json

logger = logging.getLogger("resume_router")
router = APIRouter(prefix="/api/resume", tags=["resume"])

def _re():
    try:
        import src.resume_engine as re_mod
    except ImportError:
        import resume_engine as re_mod
    re_mod.ensure_tables()
    return re_mod


# ── Build from text paste ─────────────────────────────────────────────────────
@router.post("/build")
async def resume_build(request: Request):
    """
    Build + polish resume from pasted text.
    Body: {raw_text, job_description?, name?, user_id?}
    """
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"success": False, "error": "Invalid JSON"}, status_code=400)

    raw_text        = (data.get("raw_text") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    name_override   = (data.get("name") or "").strip()
    user_id         = (data.get("user_id") or "default").strip()

    if not raw_text:
        return JSONResponse({"success": False, "error": "raw_text is required"}, status_code=400)

    result = _re().build_resume(
        raw_text=raw_text,
        job_description=job_description,
        user_id=user_id,
        name_override=name_override,
    )
    return JSONResponse(result)


# ── Build from file upload ────────────────────────────────────────────────────
@router.post("/upload")
async def resume_upload(
    file: UploadFile = File(...),
    job_description: str = Form(""),
    user_id: str = Form("default"),
    name_override: str = Form(""),
):
    """Upload a PDF, DOCX, or TXT resume file. Returns polished result + PDF."""
    try:
        file_bytes = await file.read()
        if len(file_bytes) > 5 * 1024 * 1024:  # 5MB max
            return JSONResponse({"success": False, "error": "File too large (max 5MB)"}, status_code=400)

        result = _re().build_resume(
            file_bytes=file_bytes,
            filename=file.filename or "upload.pdf",
            job_description=job_description,
            user_id=user_id,
            name_override=name_override,
        )
        return JSONResponse(result)
    except Exception as e:
        logger.error("[Resume] upload error: %s", e)
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Polish only (no PDF) ──────────────────────────────────────────────────────
@router.post("/polish")
async def resume_polish(request: Request):
    """Just polish resume text with LLM — no PDF. Body: {raw_text, job_description?}"""
    try:
        data = await request.json()
        raw  = (data.get("raw_text") or "").strip()
        job  = (data.get("job_description") or "").strip()
        if not raw:
            return JSONResponse({"success": False, "error": "raw_text required"}, status_code=400)
        result = _re().polish_resume(raw, job)
        return JSONResponse({"success": True, **result})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Generate PDF from existing resume id ─────────────────────────────────────
@router.post("/pdf/{resume_id}")
async def resume_generate_pdf(resume_id: str):
    """(Re)generate PDF for an existing resume record."""
    try:
        import sqlite3
        with sqlite3.connect(_re().RESUME_DB, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
        if not row:
            return JSONResponse({"success": False, "error": "Resume not found"}, status_code=404)

        polished = json.loads(row["polished_json"] or "{}")
        pdf_path = os.path.join(_re().RESUME_PDFS, f"resume_{resume_id}.pdf")
        _re().generate_pdf(polished, pdf_path)

        with sqlite3.connect(_re().RESUME_DB, timeout=5) as conn:
            conn.execute("UPDATE resumes SET pdf_path=?, status='complete' WHERE id=?",
                         (pdf_path, resume_id))
            conn.commit()

        return JSONResponse({"success": True, "pdf_url": f"/api/resume/download/{resume_id}"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Download PDF ──────────────────────────────────────────────────────────────
@router.get("/download/{resume_id}")
async def resume_download(resume_id: str):
    """Download the generated PDF for a resume."""
    try:
        import sqlite3
        with sqlite3.connect(_re().RESUME_DB, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT pdf_path, filename FROM resumes WHERE id=?",
                               (resume_id,)).fetchone()
        if not row or not row["pdf_path"] or not os.path.exists(row["pdf_path"]):
            return JSONResponse({"error": "PDF not found"}, status_code=404)

        safe_name = (row["filename"] or "resume").replace(".pdf", "").replace(" ", "_")
        return FileResponse(
            path=row["pdf_path"],
            media_type="application/pdf",
            filename=f"resume_{safe_name}_murphy.pdf",
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── List resumes for a user ───────────────────────────────────────────────────
@router.get("/list")
async def resume_list(user_id: str = "default", limit: int = 20):
    try:
        import sqlite3
        with sqlite3.connect(_re().RESUME_DB, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, filename, status, created_at, job_desc FROM resumes "
                "WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return JSONResponse({"success": True, "resumes": [dict(r) for r in rows]})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
async def resume_stats():
    try:
        import sqlite3
        with sqlite3.connect(_re().RESUME_DB, timeout=5) as conn:
            total = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
            pdfs  = conn.execute("SELECT COUNT(*) FROM resumes WHERE pdf_path!=''").fetchone()[0]
        return JSONResponse({"success": True, "total": total, "with_pdf": pdfs})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)
