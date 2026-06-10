"""PCR-090a — Convergence domain router.

GET /api/converge/<domain> -> rollup payload for that domain.

Domains: work, money, identity, ops, learning, system, founder, tenant.

Failure modes (per FME):
  CONV_E001: unknown domain → 404
  CONV_E002: rollup timed out → 200 with partial + error in _errors
  CONV_E003: tenant scope required but no X-Tenant-Id → 200 with error
  CONV_E004: rollup partial (one inner query failed) → 200 with partial
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from . import DOMAINS
from .rollups.work import rollup_work
from .rollups.money import rollup_money
from .rollups.identity import rollup_identity
from .rollups.ops import rollup_ops
from .rollups.learning import rollup_learning
from .rollups.system import rollup_system
from .rollups.founder import rollup_founder
from .rollups.tenant import rollup_tenant
from .forecast import enrich_rollup

LOG = logging.getLogger("murphy.convergence")

_ROLLUPS = {
    "work":     rollup_work,
    "money":    rollup_money,
    "identity": rollup_identity,
    "ops":      rollup_ops,
    "learning": rollup_learning,
    "system":   rollup_system,
    "founder":  rollup_founder,
    "tenant":   rollup_tenant,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


router = APIRouter(prefix="/api/converge", tags=["convergence"])


@router.get("")
async def list_domains():
    """List available domains."""
    return {
        "domains": list(DOMAINS),
        "version": "0.1.0-pcr090a",
        "generated_at": _now_iso(),
    }


@router.get("/{domain}")
async def get_domain_rollup(domain: str, request: Request):
    """Get rollup payload for a domain."""
    if domain not in _ROLLUPS:
        raise HTTPException(404, detail={
            "code": "CONV_E001",
            "message": f"unknown domain '{domain}'",
            "available": list(DOMAINS),
        })

    tenant_id = request.headers.get("X-Tenant-Id")
    start = time.time()
    errors = []
    try:
        payload = _ROLLUPS[domain](tenant_id=tenant_id)
    except Exception as e:
        LOG.warning("convergence rollup %s failed: %s", domain, e)
        return {
            "domain": domain,
            "summary": {},
            "items": [],
            "_errors": [f"CONV_E002 rollup failed: {type(e).__name__}: {e}"],
            "generated_at": _now_iso(),
        }

    # Pull errors from rollup if it surfaced any
    if "_errors" in payload:
        errors.extend(payload.pop("_errors"))

    # PCR-090b: enrich items with closure_forecast
    try:
        payload = enrich_rollup(payload)
    except Exception as _e:
        errors.append(f"FCST_E_enrich: {_e}")
    out = {
        "domain": domain,
        "summary": payload.get("summary", {}),
        "items": payload.get("items", []),
        "raw_endpoints": payload.get("raw_endpoints", []),
        "generated_at": _now_iso(),
        "elapsed_ms": int((time.time() - start) * 1000),
    }
    if "sub_rollups" in payload:
        out["sub_rollups"] = payload["sub_rollups"]
    if errors:
        out["_errors"] = errors
    return out
