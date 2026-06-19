"""Ship 31cz.A — antibody.intervene() single entry point.

The fully-built antibody pieces (claim_extractor, verifiers, history,
regulatory_safety) existed but nothing called them on real outbound.
This function is the connection: extract claims, classify regulatory
context, verify each claim, decide action, log the intervention.

Hard rule: never raise. Outbound MUST proceed even if antibody fails.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("murphy.antibody.intervene")

# Action taxonomy — matches existing antibody_interventions.action_taken column
ACTION_PASSTHROUGH      = "passthrough"       # no claims OR all verified
ACTION_PASSTHROUGH_ALERT = "passthrough"      # claims refuted but reg-tagged content
ACTION_BLOCKED          = "blocked"            # would block here if policy=strict


def intervene(
    response_text: str,
    *,
    prompt_text: str = "",
    agent_name: str = "stranger_responder",
    tenant_id: Optional[str] = None,
    engagement_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    policy: str = "log_only",
) -> Dict[str, Any]:
    """Run the antibody pipeline on outbound text.

    Returns:
        {
          "ok": True/False,
          "allow_send": bool,              # always True for policy=log_only
          "intervention_id": str | None,
          "claims_found": int,
          "claims_refuted": int,
          "action_taken": str,
          "regulatory_flag": str,
          "skipped": bool,
          "error": str | None,
        }

    Never raises. On exception, returns ok=False, allow_send=True (open-fail).
    """
    result = {
        "ok": True, "allow_send": True, "intervention_id": None,
        "claims_found": 0, "claims_refuted": 0,
        "action_taken": ACTION_PASSTHROUGH, "regulatory_flag": "safe",
        "skipped": False, "error": None,
    }
    if not response_text or len(response_text) < 50:
        # Too short to bother extracting claims
        result["skipped"] = True
        return result

    try:
        # Step 1 — regulatory classification (refuse to alter regulated content)
        from src.antibody.regulatory_safety import classify
        reg = classify(response_text, context or {})
        result["regulatory_flag"] = reg.get("verdict", "safe")
        reg_refused = reg.get("verdict") == "refused"

        # Step 2 — extract claims
        from src.antibody.claim_extractor import extract_claims_from_text
        claim_strs = extract_claims_from_text(
            response_text,
            source_agent=agent_name,
            source_call_id="",
        )
        result["claims_found"] = len(claim_strs)
        if not claim_strs:
            # Nothing to verify; log passthrough
            _log(result, response_text, prompt_text, agent_name,
                 tenant_id, engagement_id, [], reg_refused)
            return result

        # Step 3 — verify each claim
        from src.antibody.verifiers.base import Claim as _ClaimT
        from src.antibody.verifiers import verify_claim

        refuted_claims: List[Dict[str, Any]] = []
        for cs in claim_strs[:10]:  # cap at 10/turn for cost
            try:
                # claim_strs are plain strings; wrap into Claim type
                c = _ClaimT(claim_type="generic", claim_text=cs, source_text=cs)
                vr = verify_claim(c)
                status = getattr(vr, "status", "unverifiable")
                if status == "contradicted":
                    refuted_claims.append({
                        "claim": cs[:300],
                        "ground_truth": getattr(vr, "ground_truth", "") or "",
                        "verifier": getattr(vr, "verifier_used", "") or "",
                    })
            except Exception as ie:
                LOG.debug("intervene: verify error on claim: %s", ie)

        result["claims_refuted"] = len(refuted_claims)

        # Step 4 — decide action
        if refuted_claims:
            if reg_refused:
                # Compliance-tagged content: can't alter, but record + alert
                result["action_taken"] = ACTION_PASSTHROUGH_ALERT
            elif policy == "strict":
                result["action_taken"] = ACTION_BLOCKED
                result["allow_send"] = False
            else:
                result["action_taken"] = ACTION_PASSTHROUGH

        # Step 5 — log to ledger
        _log(result, response_text, prompt_text, agent_name,
             tenant_id, engagement_id, refuted_claims, reg_refused)

    except Exception as e:
        LOG.warning("antibody.intervene exception (fail-open): %s", e)
        result["ok"] = False
        result["error"] = str(e)[:200]
    return result


def _log(result, response_text, prompt_text, agent_name,
         tenant_id, engagement_id, refuted_claims, reg_refused):
    """Best-effort: write to antibody_interventions ledger."""
    try:
        from src.antibody.history import log_antibody_intervention
        iid = log_antibody_intervention(
            prompt=prompt_text or "",
            original_response=response_text,
            action_taken=result["action_taken"],
            corrected_response=None,  # we don't auto-correct yet
            claims_found=result["claims_found"],
            claims_refuted=result["claims_refuted"],
            refuted_claims=refuted_claims,
            regulatory_flag=result["regulatory_flag"],
            agent_name=agent_name,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
        )
        result["intervention_id"] = iid
    except Exception as e:
        LOG.debug("intervene: log failed: %s", e)
