"""
AionMind FastAPI Router — Murphy System 2.0a API.

Exposes the AionMind kernel capabilities as REST endpoints following the
existing FastAPI router patterns in the codebase.

All endpoints honour the no-autonomy invariant:
  - ``POST /orchestrate`` returns candidate graphs but does NOT execute them.
  - ``POST /execute`` requires ``approved=true`` in the graph body.
  - ``POST /proposals/*/approve`` only marks a proposal — does not apply it.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aionmind.models.context_object import ContextObject, Priority, RiskLevel
from aionmind.models.execution_graph import ExecutionGraphObject
from aionmind.models.proposals import ProposalStatus
from aionmind.runtime_kernel import AionMindKernel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aionmind", tags=["aionmind"])

# ── Shared kernel instance (initialised by the host app) ──────────
_kernel: Optional[AionMindKernel] = None


def init_kernel(kernel: AionMindKernel) -> None:
    """Called by the host application to inject the kernel instance."""
    global _kernel
    _kernel = kernel


def _get_kernel() -> AionMindKernel:
    if _kernel is None:
        raise HTTPException(
            status_code=503,
            detail="AionMind kernel not initialised.",
        )
    return _kernel


# ── Request / response schemas ────────────────────────────────────

class BuildContextRequest(BaseModel):
    """Request body for building a ContextObject from raw inputs."""

    source: str
    raw_input: str = ""
    intent: str = ""
    priority: Priority = Priority.MEDIUM
    risk_level: RiskLevel = RiskLevel.LOW
    related_tasks: List[str] = Field(default_factory=list)
    workflow_refs: List[str] = Field(default_factory=list)
    memory_refs: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestratePlanRequest(BaseModel):
    """Request body for generating candidate orchestration graphs."""

    context: BuildContextRequest
    max_candidates: int = 3


class ExecuteRequest(BaseModel):
    """Request body for executing an approved execution graph."""

    graph: Dict[str, Any]


class ApproveNodeRequest(BaseModel):
    """Request body for approving a pending HITL checkpoint node."""

    execution_id: str
    node_id: str
    approver: str


class ApproveProposalRequest(BaseModel):
    """Request body for approving an optimisation proposal."""

    approver: str


class RejectProposalRequest(BaseModel):
    """Request body for rejecting an optimisation proposal."""

    reason: str


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Return kernel status (capabilities, memory, proposals)."""
    return _get_kernel().status()


@router.post("/context")
async def build_context(req: BuildContextRequest) -> Dict[str, Any]:
    """Build a ContextObject from raw inputs (Layer 1)."""
    kernel = _get_kernel()
    ctx = kernel.build_context(**req.model_dump())
    return ctx.model_dump()


@router.post("/orchestrate")
async def orchestrate(req: OrchestratePlanRequest) -> Dict[str, Any]:
    """Generate candidate execution graphs (Layer 2).

    Returns candidate graphs and the recommended best graph.
    Does NOT execute anything — graphs are proposals until approved.
    """
    kernel = _get_kernel()
    ctx = kernel.build_context(**req.context.model_dump())
    candidates = kernel.plan(ctx, max_candidates=req.max_candidates)
    best = kernel.select(candidates, ctx)
    return {
        "context_id": ctx.context_id,
        "candidates": [g.model_dump() for g in candidates],
        "recommended": best.model_dump() if best else None,
        "note": "Graphs are proposals. Approve before executing.",
    }


@router.post("/execute")
async def execute_graph(req: ExecuteRequest) -> Dict[str, Any]:
    """Execute an approved ExecutionGraphObject (Layer 4).

    The graph must have ``approved: true`` — otherwise execution is refused.
    """
    kernel = _get_kernel()
    graph = ExecutionGraphObject(**req.graph)
    if not graph.approved:
        raise HTTPException(
            status_code=403,
            detail="Graph must be approved before execution. "
            "Set 'approved: true' and provide 'approved_by'.",
        )
    state = kernel.execute(graph)
    return {
        "execution_id": state.execution_id,
        "status": state.status.value,
        "audit_trail": [
            {
                "timestamp": a.timestamp,
                "node_id": a.node_id,
                "event": a.event,
                "details": a.details,
            }
            for a in state.audit_trail
        ],
    }


@router.post("/execute/{execution_id}/approve-node")
async def approve_node(execution_id: str, req: ApproveNodeRequest) -> Dict[str, Any]:
    """Approve a pending HITL checkpoint in an active execution."""
    kernel = _get_kernel()
    ok = kernel.orchestration.approve_node(execution_id, req.node_id, req.approver)
    if not ok:
        raise HTTPException(status_code=404, detail="No pending approval found.")
    return {"approved": True, "node_id": req.node_id, "approver": req.approver}


@router.get("/proposals")
async def list_proposals(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List optimisation proposals (Layer 6)."""
    kernel = _get_kernel()
    ps = None
    if status:
        ps = ProposalStatus(status)
    return [p.model_dump() for p in kernel.list_proposals(status=ps)]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str, req: ApproveProposalRequest
) -> Dict[str, Any]:
    """Approve a proposal.  Does NOT apply it automatically."""
    kernel = _get_kernel()
    ok = kernel.approve_proposal(proposal_id, req.approver)
    if not ok:
        raise HTTPException(status_code=404, detail="Proposal not found or not pending.")
    return {"approved": True, "proposal_id": proposal_id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str, req: RejectProposalRequest
) -> Dict[str, Any]:
    kernel = _get_kernel()
    ok = kernel.optimization.reject_proposal(proposal_id, req.reason)
    if not ok:
        raise HTTPException(status_code=404, detail="Proposal not found or not pending.")
    return {"rejected": True, "proposal_id": proposal_id}


@router.get("/memory/stats")
async def memory_stats() -> Dict[str, Any]:
    """Return STM / LTM statistics (Layer 5)."""
    return _get_kernel().memory.stats()


@router.get("/memory/stm/{key}")
async def get_stm(key: str) -> Dict[str, Any]:
    """Retrieve an STM entry."""
    data = _get_kernel().memory.retrieve_context(key)
    if data is None:
        raise HTTPException(status_code=404, detail="Key not found in STM.")
    return data


@router.get("/memory/ltm/{key}")
async def get_ltm(key: str) -> Dict[str, Any]:
    """Retrieve an LTM entry."""
    data = _get_kernel().memory.retrieve_archived(key)
    if data is None:
        raise HTTPException(status_code=404, detail="Key not found in LTM.")
    return data
