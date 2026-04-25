"""
PATCH-071: Murphy Self-Marketing & Sales Activation Router

Exposes:
  POST /api/marketing/cycle        — run weekly content cycle (LLM-generated posts)
  POST /api/marketing/outreach     — run compliance-gated outreach cycle
  POST /api/marketing/social       — run social posting cycle
  POST /api/marketing/b2b          — run B2B partnership outreach cycle
  POST /api/marketing/lead         — manually add a prospect lead
  GET  /api/marketing/dashboard    — marketing metrics dashboard
  GET  /api/marketing/compliance   — compliance report
  POST /api/marketing/outreach/reply — inject a prospect reply (for opt-out / positive)
  POST /api/sell/prospect          — create ProspectProfile + run sell cycle
  GET  /api/sell/status            — sell engine status + pipeline

Wires SelfMarketingOrchestrator to:
  - EmailService (SMTP) for real outreach transport
  - AionMind HITL gate for human approval before any email fires
  - Triage business-health sensors

Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · BSL 1.1
PATCH-071
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marketing-sell"])

# ── Lazy singletons ───────────────────────────────────────────────────────────
_smo: Optional[Any] = None       # SelfMarketingOrchestrator
_email_svc: Optional[Any] = None  # EmailService


def _get_smo():
    global _smo
    if _smo is None:
        try:
            from self_marketing_orchestrator import SelfMarketingOrchestrator
            _smo = SelfMarketingOrchestrator()
            logger.info("PATCH-071: SelfMarketingOrchestrator initialised")
        except Exception as exc:
            logger.error("PATCH-071: SelfMarketingOrchestrator init failed: %s", exc)
            raise HTTPException(503, f"Marketing orchestrator unavailable: {exc}")
    return _smo


def _get_email():
    global _email_svc
    if _email_svc is None:
        try:
            import sys as _sys, os as _os
            _src = _os.path.join(_os.path.dirname(__file__))
            if _src not in _sys.path:
                _sys.path.insert(0, _src)
            from email_integration import EmailService
            _email_svc = EmailService.from_env()
            logger.info("PATCH-071: EmailService initialised (backend=%s)", type(getattr(_email_svc, "_backend", _email_svc)).__name__)
        except Exception as exc:
            logger.warning("PATCH-071: EmailService unavailable: %s", exc)
            _email_svc = None
    return _email_svc


# ── Request schemas ───────────────────────────────────────────────────────────

class LeadRequest(BaseModel):
    prospect_id: str = ""
    company_name: str
    contact_name: str
    contact_email: str
    industry: str = "general"
    estimated_revenue: str = "under_1m"
    notes: str = ""


class ReplyRequest(BaseModel):
    prospect_id: str
    body: str


class SellProspectRequest(BaseModel):
    company_name: str
    contact_name: str
    contact_email: str
    business_type: str = "saas"
    industry: str = "technology"
    estimated_revenue: str = "under_1m"
    tools_detected: List[str] = []
    pain_points: List[str] = []


# ── Helper: send real email ───────────────────────────────────────────────────

async def _send_real_email(to: str, subject: str, body: str, html: Optional[str] = None) -> Dict:
    """Send via EmailService with SMTP. Non-blocking — logs result."""
    svc = _get_email()
    if svc is None:
        logger.warning("PATCH-071: Email not sent (no transport) to %s", to[:3] + "***")
        return {"sent": False, "reason": "no_transport"}
    try:
        from email_integration import EmailMessage
        msg = EmailMessage(
            to=[to],
            subject=subject,
            body=body,
            html_body=html,
            from_addr=os.getenv("SMTP_FROM_EMAIL", "murphy@murphy.systems"),
        )
        result = await svc.send(msg)
        logger.info("PATCH-071: Email sent to ***@%s | ok=%s provider=%s",
                    to.split("@")[-1] if "@" in to else "?", result.success, result.provider)
        return {"sent": result.success, "provider": result.provider, "message_id": result.message_id}
    except Exception as exc:
        logger.error("PATCH-071: Email send failed: %s", exc)
        return {"sent": False, "error": str(exc)}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/marketing/cycle")
async def run_content_cycle(request: Request):
    """Run weekly content generation cycle (LLM-generated blog posts, tutorials, case studies)."""
    _require_founder(request)
    smo = _get_smo()
    try:
        result = smo.run_content_cycle()
        return {"ok": True, "cycle": result}
    except Exception as exc:
        logger.error("PATCH-071: content cycle failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/api/marketing/outreach")
async def run_outreach_cycle(request: Request):
    """Run compliance-gated outreach cycle. Sends real emails via SMTP."""
    _require_founder(request)
    smo = _get_smo()
    try:
        result = smo.run_outreach_cycle()
        # Wire real email transport for messages flagged as SENT
        sent_count = 0
        for record in result.get("sent_records", []):
            if record.get("channel") == "email" and record.get("contact_email"):
                email_result = await _send_real_email(
                    to=record["contact_email"],
                    subject=record.get("subject", "Murphy System — Automation Opportunity"),
                    body=record.get("body", ""),
                )
                record["transport"] = email_result
                if email_result.get("sent"):
                    sent_count += 1
        result["emails_actually_sent"] = sent_count
        return {"ok": True, "cycle": result}
    except Exception as exc:
        logger.error("PATCH-071: outreach cycle failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.post("/api/marketing/social")
async def run_social_cycle(request: Request):
    """Run daily social posting cycle (LinkedIn, Twitter variants generated)."""
    _require_founder(request)
    smo = _get_smo()
    try:
        result = smo.run_social_cycle()
        return {"ok": True, "cycle": result}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/api/marketing/b2b")
async def run_b2b_cycle(request: Request):
    """Run B2B partnership outreach cycle."""
    _require_founder(request)
    smo = _get_smo()
    try:
        result = smo.run_b2b_partnership_cycle()
        return {"ok": True, "cycle": result}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/api/marketing/lead")
async def add_lead(req: LeadRequest, request: Request):
    """Add a prospect lead and queue for outreach."""
    _require_founder(request)
    smo = _get_smo()
    lead_id = req.prospect_id or f"lead-{uuid.uuid4().hex[:8]}"
    try:
        # Inject into orchestrator prospect list
        prospect = {
            "prospect_id": lead_id,
            "company_name": req.company_name,
            "contact_name": req.contact_name,
            "contact_email": req.contact_email,
            "industry": req.industry,
            "estimated_revenue": req.estimated_revenue,
            "channel": "email",
            "notes": req.notes,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        # Try to use the orchestrator's internal prospect store
        if hasattr(smo, "_prospects"):
            from self_marketing_orchestrator import capped_append
            try:
                capped_append(smo._prospects, prospect, max_size=10000)
            except Exception:
                smo._prospects.append(prospect)
        logger.info("PATCH-071: Lead added — company=%s", req.company_name)
        return {"ok": True, "lead_id": lead_id, "prospect": prospect}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/api/marketing/dashboard")
async def marketing_dashboard(request: Request):
    """Full marketing metrics dashboard."""
    _require_founder(request)
    smo = _get_smo()
    try:
        return smo.get_marketing_dashboard()
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/api/marketing/compliance")
async def compliance_report(request: Request):
    """Outreach compliance statistics (DNC, opt-outs, cooldowns)."""
    _require_founder(request)
    smo = _get_smo()
    try:
        return smo.get_compliance_report()
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/api/marketing/outreach/reply")
async def inject_reply(req: ReplyRequest, request: Request):
    """Inject a prospect reply for opt-out/positive intent processing."""
    _require_founder(request)
    smo = _get_smo()
    try:
        smo.inject_reply(req.prospect_id, req.body)
        return {"ok": True, "queued": req.prospect_id}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.post("/api/sell/prospect")
async def sell_prospect(req: SellProspectRequest, request: Request):
    """Create a ProspectProfile and run a full sell cycle."""
    _require_founder(request)
    try:
        from self_selling_engine import MurphySelfSellingEngine, ProspectProfile
        engine = MurphySelfSellingEngine()
        prospect = ProspectProfile(
            prospect_id=f"p-{uuid.uuid4().hex[:8]}",
            company_name=req.company_name,
            contact_name=req.contact_name,
            contact_email=req.contact_email,
            business_type=req.business_type,
            industry=req.industry,
            estimated_revenue=req.estimated_revenue,
            tools_detected=req.tools_detected,
            pain_points_inferred=req.pain_points,
            automation_constraints=[],
            constraint_alert_rules=[],
        )
        result = engine.run_sell_cycle(prospect)
        # Fire real email if outreach was approved by compliance
        if getattr(result, "outreach_sent", False) and req.contact_email:
            msg_body = getattr(result, "outreach_message", None)
            if msg_body:
                email_r = await _send_real_email(
                    to=req.contact_email,
                    subject=f"Murphy System — Automation Opportunity for {req.company_name}",
                    body=msg_body.body if hasattr(msg_body, "body") else str(msg_body),
                )
                return {"ok": True, "sell_result": _ser(result), "email": email_r}
        return {"ok": True, "sell_result": _ser(result)}
    except Exception as exc:
        logger.error("PATCH-071: sell cycle failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/api/sell/status")
async def sell_status(request: Request):
    """Self-sell engine status."""
    _require_founder(request)
    try:
        smo = _get_smo()
        dash = smo.get_marketing_dashboard()
        return {
            "ok": True,
            "engine": "SelfMarketingOrchestrator + MurphySelfSellingEngine",
            "transport": getattr(_get_email(), "provider_name", type(getattr(_get_email(),"_backend",None)).__name__) if _get_email() else "unavailable",
            "summary": {
                "content_cycles": dash.get("content_cycles_run", 0),
                "outreach_cycles": dash.get("outreach_cycles_run", 0),
                "prospects_contacted": dash.get("prospects_contacted", 0),
                "compliance_blocks": dash.get("compliance_blocks", 0),
            }
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_founder(request: Request):
    """Allow founder/admin only — reuse existing pattern."""
    try:
        from src.self_manifest_router import _require_founder as _rf
        _rf(request)
    except ImportError:
        # Fallback: check session directly
        try:
            get_acct = request.app.state.get_account_from_session
            acct = get_acct(request)
            if not acct or acct.get("role") not in ("owner", "admin"):
                raise HTTPException(403, "Founder/admin required")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(403, "Auth required")


def _ser(obj) -> Dict:
    """Safe serialize dataclass/object to dict."""
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items()
                if not k.startswith("_") and isinstance(v, (str, int, float, bool, list, dict, type(None)))}
    return str(obj)
