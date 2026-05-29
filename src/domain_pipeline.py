"""
PATCH-PIPELINE-002 (2026-05-28) — Domain Pipeline (Wire #1, fixed)

Round 1 (PIPELINE-001) shipped but had zero throughput because:
  Bug 1 — analyze_request returns {coverage, matched_domains, needs_generative, keywords}
          NOT {primary_domain, confidence}. My field names were wrong.
  Bug 2 — generate_gates_for_domain depends on librarian templates AND
          falls back to direct gate construction for domain-specific + complexity gates.
          Need to verify which path actually returns gates.

This round (PIPELINE-002) maps fields correctly and exposes a DIRECT gate
generation path as well, so the pipeline can produce at least one gate
even if the librarian/template path returns nothing.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("domain_pipeline")


def _pick_primary_domain(matched_domains: Dict[str, float]) -> Optional[str]:
    """Top-scored domain from analyze_request output, or None if empty."""
    if not matched_domains:
        return None
    return max(matched_domains.items(), key=lambda kv: kv[1])[0]


def analyze_and_generate_gates(
    request_text: str,
    confidence_threshold: float = 0.85,
    complexity: str = "medium",
    direct_gates: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Wire #1 — composes domain_engine + domain_gate_generator.

    Args:
        request_text: free-form intake.
        confidence_threshold: passed to DomainGateGenerator.
        complexity: simple/medium/complex/very_complex (drives complexity gates).
        direct_gates: optional list of {name, description, gate_type} dicts
                      for explicit gate construction when templates are empty.

    Returns:
        {
          "request": str,
          "analysis": <domain_engine output>,
          "primary_domain": str | None,
          "domain_scores": dict,
          "gates": List[DomainGate.to_dict()],
          "gate_count": int,
          "wire_version": "PIPELINE-002",
        }
    """
    from src.domain_engine import DomainEngine
    from src.domain_gate_generator import DomainGateGenerator, GateType, GateSeverity

    engine = DomainEngine()
    analysis = engine.analyze_request(request_text)

    matched = analysis.get("matched_domains", {})
    primary = _pick_primary_domain(matched)
    keywords = analysis.get("keywords", [])

    logger.info(
        "domain_pipeline: primary=%s coverage=%s keywords=%d",
        primary, analysis.get("coverage"), len(keywords),
    )

    gen = DomainGateGenerator(default_confidence_threshold=confidence_threshold)

    requirements = {
        "domain": primary or "software",
        "complexity": complexity,
        "keywords": keywords,
        "request_text": request_text[:500],
    }

    # Try generator's full pipeline first
    gates: List = []
    try:
        gates = gen.generate_gates_for_domain(
            domain=primary or "software",
            system_requirements=requirements,
        )
    except Exception as exc:
        logger.warning("generate_gates_for_domain failed: %s", exc)

    # If full pipeline returned nothing AND caller passed direct_gates,
    # fall back to direct generate_gate() construction
    if not gates and direct_gates:
        for spec in direct_gates:
            try:
                gtype_name = spec.get("gate_type", "QUALITY")
                gtype = getattr(GateType, gtype_name.upper(), GateType.QUALITY)
                gsev_name = spec.get("severity", "MEDIUM")
                gsev = getattr(GateSeverity, gsev_name.upper(), GateSeverity.MEDIUM)
                g = gen.generate_gate(
                    name=spec["name"],
                    description=spec.get("description", spec["name"]),
                    gate_type=gtype,
                    severity=gsev,
                )
                gates.append(g)
            except Exception as exc:
                logger.warning("direct gate %s failed: %s", spec.get("name"), exc)

    gate_dicts = []
    for g in gates:
        if hasattr(g, "to_dict"):
            gate_dicts.append(g.to_dict())
        elif isinstance(g, dict):
            gate_dicts.append(g)
        else:
            gate_dicts.append({"raw": str(g)})

    return {
        "request": request_text[:200],
        "analysis": analysis,
        "primary_domain": primary,
        "domain_scores": matched,
        "gates": gate_dicts,
        "gate_count": len(gate_dicts),
        "wire_version": "PIPELINE-002",
    }


if __name__ == "__main__":
    import json as _j
    sample = (
        "Design a HIPAA-compliant patient intake portal for a "
        "200-bed regional hospital with SOC2 audit trail and "
        "AWS deployment in us-east-1."
    )
    direct = [
        {"name": "PHI Encryption", "description": "All PHI encrypted at rest and in transit", "gate_type": "COMPLIANCE", "severity": "CRITICAL"},
        {"name": "Audit Trail Continuity", "description": "Every access logged with user, ts, action", "gate_type": "COMPLIANCE", "severity": "HIGH"},
        {"name": "Latency SLO", "description": "p95 < 500ms for intake form submission", "gate_type": "PERFORMANCE", "severity": "MEDIUM"},
    ]
    result = analyze_and_generate_gates(sample, direct_gates=direct)
    print(_j.dumps({
        "primary_domain": result["primary_domain"],
        "domain_scores": result["domain_scores"],
        "keywords": result["analysis"].get("keywords", []),
        "coverage": result["analysis"].get("coverage"),
        "gate_count": result["gate_count"],
        "first_gate_name": result["gates"][0].get("name") if result["gates"] else None,
        "first_gate_type": result["gates"][0].get("gate_type") if result["gates"] else None,
        "wire_version": result["wire_version"],
    }, indent=2, default=str))



# PATCH-WIRE2-R123 — Phase B Wire #2: domain_pipeline → chain_engine
# Per Murphy meta-Q + locked plan. Compose-not-modify: new function that
# takes run_pipeline output and threads it through chain_engine.evaluate_gate.

def run_pipeline_with_gates(intent_text, active_compliance=None,
                              evidence=None, tenant_id="platform"):
    """
    Wire #2 composition: run domain pipeline THEN evaluate each
    generated gate via chain_engine.evaluate_gate.
    
    Returns:
        {
          "ok": bool,
          "pipeline_result": <run_pipeline output>,
          "gate_evaluations": [
            {"step_id": str, "gate_result": {...}, "passed": bool},
            ...
          ],
          "all_gates_passed": bool,
          "failed_gate_ids": [str, ...]
        }
    """
    if active_compliance is None:
        active_compliance = []
    if evidence is None:
        evidence = {}
    
    # PATCH-WIRE2-R124 — R123 called run_pipeline (nonexistent).
    # Real entrypoint is analyze_and_generate_gates.
    # Stage 1: run domain pipeline (existing Wire #1 substrate)
    try:
        pipeline_result = analyze_and_generate_gates(intent_text)
    except Exception as e:
        return {
            "ok": False,
            "reason": "pipeline_failed: {}".format(str(e)[:120]),
            "pipeline_result": None,
            "gate_evaluations": [],
        }
    
    if not pipeline_result or not pipeline_result.get("gates"):
        return {
            "ok": True,
            "pipeline_result": pipeline_result,
            "gate_evaluations": [],
            "all_gates_passed": True,
            "failed_gate_ids": [],
            "note": "no_gates_to_evaluate",
        }
    
    # Stage 2: evaluate each gate via chain_engine.evaluate_gate
    try:
        from src.chain_engine import evaluate_gate
    except Exception as e:
        return {
            "ok": False,
            "reason": "chain_engine_import_failed: {}".format(str(e)[:120]),
            "pipeline_result": pipeline_result,
            "gate_evaluations": [],
        }
    
    evaluations = []
    failed_ids = []
    
    for gate in pipeline_result.get("gates", []):
        # Build step_def shape that evaluate_gate expects
        # chain_engine.evaluate_gate(step_def: Dict, active_compliance: List[str])
        step_def = {
            "step_id": gate.get("gate_id") or gate.get("id") or "unknown",
            "gate_type": gate.get("type") or "domain_generated",
            "domain": gate.get("domain") or pipeline_result.get("primary_domain"),
            "required_evidence": gate.get("required_evidence", []),
            "evidence": evidence,
        }
        
        try:
            gate_result = evaluate_gate(step_def, active_compliance)
            passed = bool(gate_result.get("passed") or gate_result.get("ok"))
        except Exception as e:
            gate_result = {"ok": False, "error": str(e)[:160]}
            passed = False
        
        evaluations.append({
            "step_id": step_def["step_id"],
            "gate_result": gate_result,
            "passed": passed,
        })
        if not passed:
            failed_ids.append(step_def["step_id"])
    
    return {
        "ok": True,
        "pipeline_result": pipeline_result,
        "gate_evaluations": evaluations,
        "all_gates_passed": len(failed_ids) == 0,
        "failed_gate_ids": failed_ids,
        "tenant_id": tenant_id,
    }
