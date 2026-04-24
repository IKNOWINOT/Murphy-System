"""
manga_router.py — Murphy Manga Generator API
=============================================
PATCH-065: REST endpoints for manga generation.

Routes:
  POST /api/manga/generate     — Start manga generation (returns job_id)
  GET  /api/manga/status/{id}  — Poll job status + partial results
  GET  /api/manga/result/{id}  — Get completed manga
  GET  /api/manga/jobs         — List recent jobs (authenticated)

Copyright © 2020 Inoni LLC · Creator: Corey Post · BSL 1.1
"""

import asyncio
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/manga", tags=["manga"])

# In-memory job store (survives restarts if we add persistence later)
_jobs: dict[str, dict] = {}


class Character(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=10, max_length=300,
                              description="Visual description: age, hair, clothing, personality")


class MangaRequest(BaseModel):
    story_prompt: str = Field(..., min_length=10, max_length=500,
                               description="The story idea/premise")
    characters: list[Character] = Field(..., min_items=1, max_items=4)
    style: str = Field("classic", description="classic | shonen | shojo | seinen | cyberpunk")

    @validator("style")
    def validate_style(cls, v):
        allowed = {"classic", "shonen", "shojo", "seinen", "cyberpunk"}
        if v not in allowed:
            raise ValueError(f"style must be one of {allowed}")
        return v


STYLE_MODIFIERS = {
    "classic":   "classic manga style, clean lines, expressive faces",
    "shonen":    "shonen manga style, action-focused, bold lines, intense energy, battle-ready",
    "shojo":     "shojo manga style, soft lines, sparkles, romantic atmosphere, delicate details",
    "seinen":    "seinen manga style, realistic proportions, detailed backgrounds, mature tone",
    "cyberpunk": "cyberpunk manga style, neon accents, mechanical details, dystopian atmosphere",
}


async def _run_manga_job(job_id: str, request: MangaRequest):
    """Background task: runs full manga pipeline and updates job store."""
    job = _jobs[job_id]
    
    try:
        from src.manga_engine import generate_manga
        
        # Inject style into story prompt
        style_hint = STYLE_MODIFIERS.get(request.style, "")
        augmented_prompt = f"{request.story_prompt}. Art style: {style_hint}"
        
        chars = [{"name": c.name, "description": c.description} for c in request.characters]
        
        job["status"] = "generating_script"
        job["progress"] = 10
        job["message"] = "Writing panel script…"
        
        result = await generate_manga(augmented_prompt, chars)
        
        job["status"] = "complete"
        job["progress"] = 100
        job["message"] = "Manga complete!"
        job["result"] = result
        job["completed_at"] = time.time()
        
    except Exception as e:
        logger.exception(f"Manga job {job_id} failed: {e}")
        job["status"] = "error"
        job["error"] = str(e)
        job["message"] = f"Generation failed: {str(e)[:100]}"


@router.post("/generate")
async def start_manga_generation(request: MangaRequest, background_tasks: BackgroundTasks):
    """Start a manga generation job. Returns job_id to poll for status."""
    job_id = str(uuid.uuid4())[:8]
    
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Queued…",
        "created_at": time.time(),
        "request": {
            "story_prompt": request.story_prompt,
            "characters": [c.dict() for c in request.characters],
            "style": request.style,
        },
        "result": None,
    }
    
    background_tasks.add_task(_run_manga_job, job_id, request)
    
    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "message": "Manga generation started",
        "poll_url": f"/api/manga/status/{job_id}",
    })


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Poll manga generation status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    resp = {
        "job_id": job_id,
        "status": job["status"],
        "progress": job.get("progress", 0),
        "message": job.get("message", ""),
    }
    
    if job["status"] == "error":
        resp["error"] = job.get("error", "Unknown error")
    
    if job["status"] == "complete" and job.get("result"):
        resp["result"] = job["result"]
    
    return JSONResponse(resp)


@router.get("/result/{job_id}")
async def get_manga_result(job_id: str):
    """Get completed manga result."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "complete":
        raise HTTPException(400, f"Job not complete (status: {job['status']})")
    return JSONResponse({"success": True, "manga": job["result"]})


@router.get("/jobs")
async def list_jobs():
    """List recent manga jobs (last 20)."""
    jobs = sorted(_jobs.values(), key=lambda j: j.get("created_at", 0), reverse=True)[:20]
    return JSONResponse({
        "success": True,
        "jobs": [
            {
                "job_id": j["job_id"],
                "status": j["status"],
                "progress": j.get("progress", 0),
                "story_prompt": j.get("request", {}).get("story_prompt", "")[:60],
                "created_at": j.get("created_at"),
            }
            for j in jobs
        ]
    })
