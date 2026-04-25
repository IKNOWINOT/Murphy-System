"""
Integration Builder Router — PATCH-081b
REST API for autonomous integration building, discovery, and web signup.

  GET  /api/builder/catalog        — all known + auto-built connectors
  GET  /api/builder/status         — which are configured with real keys
  POST /api/builder/build          — build one new integration autonomously
  POST /api/builder/build/cycle    — run autonomous batch build cycle
  GET  /api/builder/build/log      — build history
  POST /api/builder/configure      — set credentials for an integration
  POST /api/builder/call           — call any integration method
  POST /api/builder/signup         — Playwright-based web signup agent
  GET  /api/builder/signup/log     — signup attempt history

PATCH-081b | Label: INTEG-ROUTER-001
"""
from __future__ import annotations
import threading

import json
import logging
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/builder", tags=["integration_builder"])

SIGNUP_LOG = Path("/var/lib/murphy-production/signup_log.json")
SIGNUP_LOG.parent.mkdir(parents=True, exist_ok=True)


# ── Catalog / Status ─────────────────────────────────────────────────────────

@router.get("/catalog")
async def integration_catalog():
    """List all integrations — built-in + auto-built."""
    try:
        from src.integrations.world_model_registry import _INTEGRATION_META, _CONNECTOR_MAP
        from src.integration_builder import _load_build_log, INTEGRATIONS_DIR
        
        # All known
        catalog = {}
        for iid, meta in _INTEGRATION_META.items():
            catalog[iid] = {**meta, "has_connector": iid in _CONNECTOR_MAP, "auto_built": False}
        
        # Auto-built ones not yet in meta
        build_log = _load_build_log()
        for entry in build_log:
            if entry.get("ok"):
                sid = entry["service"]
                if sid not in catalog:
                    catalog[sid] = {
                        "name": sid.replace("_", " ").title(),
                        "category": "auto_built",
                        "has_connector": True,
                        "auto_built": True,
                        "methods": entry.get("methods", []),
                    }
        
        # Priority targets not yet built
        from src.integration_builder import PRIORITY_INTEGRATION_TARGETS
        for t in PRIORITY_INTEGRATION_TARGETS:
            if t["service"] not in catalog:
                catalog[t["service"]] = {
                    "name": t["service"].replace("_", " ").title(),
                    "category": t["category"],
                    "description": t["description"],
                    "has_connector": False,
                    "auto_built": False,
                    "queued": True,
                }
        
        return JSONResponse({
            "ok": True,
            "total": len(catalog),
            "built": sum(1 for v in catalog.values() if v.get("has_connector")),
            "catalog": catalog,
        })
    except Exception as exc:
        logger.error("INTEG-ROUTER: catalog failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/status")
async def integration_status():
    """Which integrations are configured with real API keys."""
    try:
        from src.integrations.world_model_registry import get_registry
        registry = get_registry()
        all_integ = registry.list_integrations()
        return JSONResponse({
            "ok": True,
            "integrations": all_integ,
            "configured_count": sum(1 for i in all_integ if i.get("configured")),
            "total": len(all_integ),
        })
    except Exception as exc:
        logger.error("INTEG-ROUTER: status failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Autonomous Build ─────────────────────────────────────────────────────────

class BuildRequest(BaseModel):
    service: str
    category: str = "general"
    description: str = ""
    search_docs: bool = True

# In-memory job store for async builds
_build_jobs: Dict[str, Any] = {}

@router.post("/build")
async def build_integration(req: BuildRequest):
    """
    Autonomously build a new integration connector.
    Returns 202 immediately with a job_id; poll /api/builder/build/{job_id} for result.
    If the connector already exists, returns 200 with status=already_exists.
    """
    try:
        from src.integration_builder import build_integration as _build, _already_built
        
        # Fast path: already exists
        if _already_built(req.service):
            return JSONResponse({"ok": True, "service": req.service, "status": "already_exists"})
        
        # Generate job_id
        import uuid
        job_id = f"build_{req.service}_{uuid.uuid4().hex[:8]}"
        _build_jobs[job_id] = {"status": "running", "service": req.service, "started": time.time()}
        
        def _run():
            try:
                result = _build(req.service, req.category, req.description, req.search_docs)
                _build_jobs[job_id] = {"status": "done", **result, "elapsed": round(time.time() - _build_jobs[job_id]["started"], 1)}
            except Exception as e:
                _build_jobs[job_id] = {"status": "error", "ok": False, "error": str(e)}
        
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        
        return JSONResponse({"ok": True, "status": "queued", "job_id": job_id,
                             "poll_url": f"/api/builder/build/{job_id}"}, status_code=202)
    except Exception as exc:
        logger.error("INTEG-ROUTER: build failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/build/{job_id}")
async def build_status(job_id: str):
    """Poll build job status."""
    job = _build_jobs.get(job_id)
    if not job:
        return JSONResponse({"ok": False, "error": "Job not found"}, status_code=404)
    return JSONResponse(job)


class BatchBuildRequest(BaseModel):
    max_per_run: int = 3

@router.post("/build/cycle")
async def build_cycle(req: BatchBuildRequest):
    """Run autonomous batch integration build cycle."""
    try:
        from src.integration_builder import run_autonomous_build_cycle
        result_box = {}
        
        def _run():
            result_box["result"] = run_autonomous_build_cycle(req.max_per_run)
        
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=300)
        
        if "result" not in result_box:
            return JSONResponse({"ok": False, "error": "Cycle timed out"}, status_code=504)
        
        return JSONResponse(result_box["result"])
    except Exception as exc:
        logger.error("INTEG-ROUTER: build cycle failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/build/log")
async def build_log():
    """Integration build history."""
    try:
        from src.integration_builder import _load_build_log
        log = _load_build_log()
        return JSONResponse({
            "ok": True,
            "total": len(log),
            "succeeded": sum(1 for e in log if e.get("ok")),
            "log": log,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Configure / Call ─────────────────────────────────────────────────────────

class ConfigureRequest(BaseModel):
    integration_id: str
    credentials: Dict[str, str]

@router.post("/configure")
async def configure_integration(req: ConfigureRequest):
    """Set API credentials for an integration."""
    try:
        from src.integrations.world_model_registry import get_registry
        registry = get_registry()
        connector = registry.get(req.integration_id, credentials=req.credentials)
        status = connector.get_status()
        
        # Persist to secrets.env
        secrets_path = Path("/etc/murphy-production/secrets.env")
        existing = secrets_path.read_text() if secrets_path.exists() else ""
        for key, value in req.credentials.items():
            if f"{key}=" in existing:
                import re
                existing = re.sub(f"^{key}=.*$", f"{key}={value}", existing, flags=re.MULTILINE)
            else:
                existing += f"\n{key}={value}"
        secrets_path.write_text(existing)
        
        return JSONResponse({
            "ok": True,
            "integration": req.integration_id,
            "configured": status.get("configured"),
            "status": status,
        })
    except Exception as exc:
        logger.error("INTEG-ROUTER: configure failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


class CallRequest(BaseModel):
    integration_id: str
    method: str
    args: Dict[str, Any] = {}

@router.post("/call")
async def call_integration(req: CallRequest):
    """Call any method on any integration connector."""
    try:
        from src.integrations.world_model_registry import get_registry
        registry = get_registry()
        connector = registry.get(req.integration_id)
        
        if not hasattr(connector, req.method):
            return JSONResponse({"ok": False, "error": f"Method {req.method} not found on {req.integration_id}"}, status_code=404)
        
        method_fn = getattr(connector, req.method)
        result = method_fn(**req.args)
        return JSONResponse({"ok": True, "integration": req.integration_id, "method": req.method, "result": result})
    except Exception as exc:
        logger.error("INTEG-ROUTER: call failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Web Signup Agent ─────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    service: str          # e.g. "zenbusiness", "contentful"
    service_url: str      # e.g. "https://www.zenbusiness.com"
    company_name: str = "Inoni LLC"
    email: str = "cpost@murphy.systems"
    purpose: str = ""     # e.g. "LLC formation and registered agent"
    fields: Dict[str, str] = {}   # additional form fields
    notes: str = ""

def _load_signup_log() -> List[Dict]:
    try:
        return json.loads(SIGNUP_LOG.read_text()) if SIGNUP_LOG.exists() else []
    except Exception:
        return []

def _save_signup_log(log: List[Dict]) -> None:
    try:
        SIGNUP_LOG.write_text(json.dumps(log, indent=2))
    except Exception:
        pass

@router.post("/signup")
async def web_signup(req: SignupRequest):
    """
    Playwright-based web signup agent.
    Murphy navigates to the service, fills the signup form, and returns the result.
    Always captures a screenshot as proof.
    """
    try:
        from src.web_tool import fetch, screenshot, fill_and_submit
        import base64
        
        result_box = {}
        
        def _do_signup():
            try:
                # First — fetch the page to understand the form
                page_info = fetch(req.service_url, timeout=20)
                
                # Build form fields from page context + request
                fields = {
                    **req.fields,
                }
                # Common field patterns
                for selector_candidate in ["#email", "input[name=email]", "input[type=email]"]:
                    fields.setdefault(selector_candidate, req.email)
                for selector_candidate in ["input[name=company]", "input[name=company_name]", "#company"]:
                    fields.setdefault(selector_candidate, req.company_name)
                
                # Take pre-signup screenshot
                pre_ss = screenshot(req.service_url, timeout=25)
                
                # Attempt form fill
                signup_result = fill_and_submit(
                    url=req.service_url,
                    fields=fields,
                    submit_selector="button[type=submit], input[type=submit], .signup-btn, .cta-button",
                    wait_after_ms=3000,
                    timeout=30,
                )
                
                result_box["result"] = {
                    "ok": signup_result.get("ok"),
                    "service": req.service,
                    "url": req.service_url,
                    "email_used": req.email,
                    "company": req.company_name,
                    "page_title": page_info.get("title", ""),
                    "result_text_preview": signup_result.get("result_text", "")[:500],
                    "screenshot_b64": signup_result.get("screenshot_b64", ""),
                    "pre_screenshot_b64": pre_ss.get("png_b64", ""),
                    "error": signup_result.get("error", ""),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "notes": req.notes,
                }
            except Exception as exc:
                result_box["result"] = {
                    "ok": False, "service": req.service,
                    "error": str(exc),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
        
        t = threading.Thread(target=_do_signup, daemon=True)
        t.start()
        t.join(timeout=60)
        
        if "result" not in result_box:
            result_box["result"] = {"ok": False, "service": req.service, "error": "Signup timed out after 60s"}
        
        # Log it
        log = _load_signup_log()
        log.append(result_box["result"])
        _save_signup_log(log)
        
        # Return without screenshots in body (too large) — just status
        resp = {k: v for k, v in result_box["result"].items() 
                if k not in ("screenshot_b64", "pre_screenshot_b64")}
        resp["has_screenshot"] = bool(result_box["result"].get("screenshot_b64"))
        
        return JSONResponse(resp)
    except Exception as exc:
        logger.error("INTEG-ROUTER: signup failed: %s", exc)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@router.get("/signup/log")
async def signup_log():
    """Web signup attempt history."""
    try:
        log = _load_signup_log()
        # Strip screenshots for response
        clean = [{k: v for k, v in e.items() if "screenshot" not in k} for e in log]
        return JSONResponse({"ok": True, "total": len(log), "log": clean})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


# ── Code Quality Evaluation ──────────────────────────────────────────────────

@router.get("/eval/log")
async def eval_log():
    """Code quality evaluation history."""
    try:
        from src.coding_intelligence import EVAL_LOG
        import json as _json
        log = _json.loads(EVAL_LOG.read_text()) if EVAL_LOG.exists() else []
        avg = sum(e["total"] for e in log) / len(log) if log else 0
        return JSONResponse({
            "ok": True,
            "total_evaluations": len(log),
            "average_score": round(avg, 2),
            "pass_rate": f"{sum(1 for e in log if e.get('passed'))*100//max(len(log),1)}%",
            "log": log[-20:],  # last 20
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


class EvalRequest(BaseModel):
    code: str
    service: str

@router.post("/eval/score")
async def score_code(req: EvalRequest):
    """Score a connector on the 15-point quality scale."""
    try:
        from src.coding_intelligence import score_connector
        score = score_connector(req.code, req.service)
        return JSONResponse({
            "ok": True,
            "service": req.service,
            "total": score.total,
            "max": score.max_score,
            "grade": score.grade,
            "passes": score.passes,
            "quality": score.quality,
            "coverage": score.coverage,
            "production": score.production,
            "issues": score.issues,
            "strengths": score.strengths,
        })
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
