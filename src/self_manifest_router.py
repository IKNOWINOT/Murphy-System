# Copyright © 2020 Inoni LLC | License: BSL 1.1
"""Murphy Self-Manifest Router — PATCH-066 | Label: SELF-ROUTER-001

Exposes Murphy's self-model as REST endpoints:
  GET  /api/self/health          — fast summary (public, no auth)
  GET  /api/self/manifest        — full self-model (founder/admin, cached 120s)
  GET  /api/self/patch-log       — PATCH lineage from git
  POST /api/self/diagnose        — run triage cycle (founder)
  GET  /api/self/proposals       — list patch proposals
  POST /api/self/proposals/{id}/approve  — founder approves
  POST /api/self/proposals/{id}/reject   — founder rejects
  POST /api/self/proposals/{id}/apply    — apply approved proposal
"""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/self", tags=["self"])


def _require_founder(request: Request):
    """Resolve caller via app.state session resolver. PATCH-068d."""
    resolver = getattr(request.app.state, "get_account_from_session", None)
    if resolver is None:
        raise HTTPException(status_code=503, detail="Auth resolver not initialised")
    account = resolver(request)
    if account is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = account.get("role", "") if isinstance(account, dict) else ""
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Founder/admin role required")
    return account

# -----------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------

@router.get("/health")
async def self_health():
    """Fast health summary — no auth required."""
    try:
        from src.murphy_self_manifest import get_health_summary
        return get_health_summary()
    except Exception as exc:
        logger.error("SELF-ROUTER: /health failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("/manifest")
async def self_manifest(request: Request, force: bool = Query(False)):
    """Full self-model — founder/admin only. Cached 120s."""
    _require_founder(request)
    try:
        from src.murphy_self_manifest import build_manifest
        manifest = build_manifest(force=force)
        # Don't return full module registry inline (too large) — summarize
        summary = dict(manifest)
        summary["module_registry"] = [
            {"file": m.get("file"), "classes": len(m.get("classes", [])),
             "functions": len(m.get("functions", [])), "loc": m.get("loc", 0),
             "llm_calls": m.get("llm_calls", []), "parse_error": m.get("parse_error")}
            for m in manifest.get("module_registry", [])
        ]
        return summary
    except Exception as exc:
        logger.error("SELF-ROUTER: /manifest failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/manifest/module/{module_path:path}")
async def self_manifest_module(request: Request, module_path: str):
    """Full detail for one specific module."""
    _require_founder(request)
    try:
        from src.murphy_self_manifest import build_manifest
        manifest = build_manifest()
        for m in manifest.get("module_registry", []):
            if module_path in m.get("file", ""):
                return m
        raise HTTPException(status_code=404, detail=f"Module not found: {module_path}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/patch-log")
async def self_patch_log(limit: int = Query(50, ge=1, le=200)):
    """PATCH lineage from git log."""
    try:
        from src.murphy_self_manifest import get_patch_log
        return {"patches": get_patch_log(limit), "count": limit}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/diagnose")
async def self_diagnose(request: Request):
    """Run one triage cycle — detect → diagnose → propose."""
    _require_founder(request)
    try:
        from src.murphy_self_patch_loop import run_triage_cycle
        result = run_triage_cycle()
        return result
    except Exception as exc:
        logger.error("SELF-ROUTER: /diagnose failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/proposals")
async def list_proposals(request: Request, status: Optional[str] = Query(None)):
    """List patch proposals."""
    _require_founder(request)
    try:
        from src.murphy_self_patch_loop import list_proposals
        return {"proposals": list_proposals(status=status)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class ApprovalRequest(BaseModel):
    note: Optional[str] = None


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(request: Request, proposal_id: str, body: ApprovalRequest = ApprovalRequest()):
    """Founder approves a patch proposal."""
    account = _require_founder(request)
    try:
        from src.murphy_self_patch_loop import get_proposal, ProposalStatus, _save_store
        prop = get_proposal(proposal_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        approver = account.get("email", "founder") if isinstance(account, dict) else "founder"
        prop.status = ProposalStatus.APPROVED
        prop.approved_by = approver
        _save_store()
        return {"ok": True, "proposal_id": proposal_id, "status": "approved", "approved_by": approver}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(request: Request, proposal_id: str):
    """Founder rejects a patch proposal."""
    _require_founder(request)
    try:
        from src.murphy_self_patch_loop import get_proposal, ProposalStatus, _save_store
        prop = get_proposal(proposal_id)
        if prop is None:
            raise HTTPException(status_code=404, detail="Proposal not found")
        prop.status = ProposalStatus.REJECTED
        _save_store()
        return {"ok": True, "proposal_id": proposal_id, "status": "rejected"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/proposals/{proposal_id}/apply")
async def apply_proposal(request: Request, proposal_id: str):
    """Apply an approved proposal."""
    account = _require_founder(request)
    try:
        from src.murphy_self_patch_loop import apply_proposal
        approver = account.get("email", "founder") if isinstance(account, dict) else "founder"
        result = apply_proposal(proposal_id, approved_by=approver)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/proposals/{proposal_id}/generate-diff")
async def generate_diff(proposal_id: str, request: Request):
    """Use LLM to generate a unified diff for a pending proposal. Founder only."""
    _require_founder(request)
    try:
        from src.murphy_code_gen import generate_diff_for_proposal
        result = generate_diff_for_proposal(proposal_id)
        return result
    except Exception as exc:
        logger.error("SELF-ROUTER: /generate-diff failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/code-gen/snippet")
async def code_gen_snippet(request: Request):
    """Generate a Python code snippet from a plain-english task. Founder only."""
    _require_founder(request)
    body = await request.json()
    task = body.get("task", "")
    context_files = body.get("context_files", [])
    if not task:
        raise HTTPException(status_code=400, detail="'task' required")
    try:
        from src.murphy_code_gen import generate_snippet
        return generate_snippet(task, context_files)
    except Exception as exc:
        logger.error("SELF-ROUTER: /code-gen/snippet failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/code-gen/status")
async def code_gen_status():
    """Check if LLM is available for code generation. Public."""
    try:
        from src.llm_provider import complete
        result = complete(prompt="Reply: OK", system="Say OK", max_tokens=5, temperature=0)
        working = result and not result.startswith("[Murphy Onboard]") and not result.startswith("[LLM")
        return {
            "llm_available": working,
            "response_preview": result[:50] if result else None,
        }
    except Exception as exc:
        return {"llm_available": False, "error": str(exc)}

