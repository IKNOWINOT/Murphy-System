"""
PATCH-LIB-PLAN-001 (2026-05-28 R61) — Librarian Natural-Language Planner

WHAT THIS IS:
  Takes a natural-language sentence and returns a structured plan referencing
  REAL Phase B components. Optionally executes the plan and returns results.

WHY IT EXISTS:
  Phase B shipped 9 wires + B.5 P1/P2. Most have no UI. Customer can't reach
  them through a browser yet. This module makes them reachable through chat —
  the universal interface.

  Pre-R61: agent_broker.find_agents() is callable only from code.
  Post-R61: a user can say "find me an engineering agent for tenant t1" and
            get a plan that calls find_agents(domain="engineering", requesting_tenant="t1"),
            optionally executes, returns the result.

HOW IT FITS:
  request_text → parse_intent() → match_component() → compose_plan() → [execute()]
                                                                       ↓
                                              real Phase B wire call → result

CATALOG:
  Phase B wires are registered here with their parameter signatures. New wires
  added by registering an INTENT entry — no LLM round-trip needed for the
  common cases.

ENDPOINTS / PUBLIC SURFACE:
  plan_from_nl(sentence: str, execute: bool = False) -> Dict
  list_catalog() -> List[Dict]  # what intents are known
  register_intent(name, module, function, args_schema, examples) -> bool
  match_intent(sentence: str) -> Optional[Dict]

DEPENDENCIES:
  - Phase B modules (imported lazily to avoid circular)

KNOWN LIMITS:
  - Keyword-based matching first; LLM fallback only if no catalog match
  - Execution is opt-in (execute=False by default for safety)
  - Cross-tenant policy still enforced by agent_broker itself

LAST UPDATED: 2026-05-28 R61
"""

import logging
import re
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("librarian_planner")


# ── Catalog of registered intents ──────────────────────────────────────────
# Each entry: {
#   "intent": short name,
#   "keywords": list of must-match keywords (any match triggers candidate),
#   "module": import path (lazy),
#   "function": function name on the module,
#   "args_extractor": callable(sentence) -> dict of args,
#   "description": human-readable,
#   "examples": list of example sentences,
# }
_CATALOG: List[Dict[str, Any]] = []


def _extract_domain(sentence: str) -> Optional[str]:
    """Pull a domain hint out of a sentence: 'engineering', 'product', etc."""
    s = sentence.lower()
    # Known domains from Phase B observation data
    for d in ("engineering", "product", "design", "infrastructure", "data",
              "operations", "finance", "marketing", "sales", "platform"):
        if d in s:
            return d
    return None


def _extract_tenant(sentence: str) -> Optional[str]:
    """Pull a tenant identifier: t1, t2, tenant_xyz, etc."""
    s = sentence.lower()
    # Match t1..t99 or tenant_xxx
    m = re.search(r"\btenant[_ ]+([\w-]+)\b", s)
    if m:
        cand = m.group(1)
        # Normalize 't1' style if it parsed weird
        return cand if not cand.isdigit() else f"t{cand}"
    m = re.search(r"\b(t\d+)\b", s)
    if m:
        return m.group(1)
    return None


def _extract_amount(sentence: str) -> Optional[float]:
    """Pull a dollar amount. PATCH-EXTRACTORS-FIX-R187: require explicit
    currency anchor ($, usd, dollar) so bare digits don't match chain IDs,
    dates, tenant numbers, deal numbers, etc."""
    s = sentence.lower()
    # Pattern 1: $NNN or $NNN.NN
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)\b", s)
    if m:
        try: return float(m.group(1))
        except Exception: pass
    # Pattern 2: NNN usd / NNN dollar(s) / NNN bucks
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:usd|dollars?|bucks)\b", s)
    if m:
        try: return float(m.group(1))
        except Exception: pass
    # Pattern 3: "budget of NNN" / "for NNN" only when amount word precedes
    m = re.search(r"\b(?:budget|amount|price|cost|fee|charge)\s+(?:of\s+)?(\d+(?:\.\d+)?)\b", s)
    if m:
        try: return float(m.group(1))
        except Exception: pass
    return None


def _extract_agent_id(sentence: str) -> Optional[str]:
    """Pull an agent identifier — lead_engineer, platform_cto, etc."""
    s = sentence.lower()
    for a in ("lead_engineer", "platform_cto", "platform_ceo", "platform_coo",
              "platform_cfo", "platform_engineering", "exec_admin", "scheduler",
              "auditor", "executor", "collector", "translator", "hitl",
              "rosetta", "prod_ops", "patcher"):
        if a in s:
            return a
    return None



# ── PATCH-EXTRACTORS-FIX-R187 applied: amount + project_id regex tightening ──
# ── PATCH-LIBRARIAN-EXTRACTORS-R185 (2026-05-29) ────────────────────────────
# Phase D coverage: every entity type Murphy might act on needs an extractor.
def _extract_chain_id(sentence):
    m = re.search(r"\b(CHN-\d{8}-[A-F0-9]{4})\b", sentence)
    return m.group(1) if m else None

def _extract_template_id(sentence):
    s = sentence.lower()
    for t in ("chain_vendor_onboarding", "chain_client_onboarding",
              "chain_change_order", "chain_feature_delivery",
              "chain_revenue_driver", "chain_compliance_review",
              "chain_incident_response"):
        if t in s: return t
    m = re.search(r"\b(chain_[a-z_]+)\b", s)
    return m.group(1) if m else None

def _extract_file_path(sentence):
    m = re.search(r"(/opt/Murphy-System/[\w/.\-]+|/tmp/murphy_[\w.\-]+|/var/lib/murphy-production/[\w.\-]+)", sentence)
    return m.group(1) if m else None

def _extract_deal_id(sentence):
    m = re.search(r"\bdeal[_ ]+(\w+)\b", sentence.lower())
    return m.group(1) if m else None

def _extract_email(sentence):
    m = re.search(r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b", sentence)
    return m.group(1) if m else None

def _extract_project_id(sentence):
    """PATCH-EXTRACTORS-FIX-R187: don't match the literal word 'id' after 'project_id'.
    Require the captured token to be different from 'id'."""
    s = sentence.lower()
    m = re.search(r"\bproj(?:ect)?[_ ]+([\w-]+)\b", s)
    if m:
        cand = m.group(1)
        if cand in ("id", "ids"): return None
        return cand if not cand.isdigit() else f"proj{cand}"
    return None

def _extract_url(sentence):
    m = re.search(r"(https?://[^\s\"]+)", sentence)
    return m.group(1) if m else None

def _extract_vendor_company(sentence):
    s = sentence.lower()
    for v in ("winston royal guard", "m&m control", "mm control", "keckley",
              "strainersales", "colton", "sc industrial", "armstrong"):
        if v in s: return v.replace(" ", "_")
    return None

def extract_all_inputs(sentence):
    """One-call extractor returning every input the librarian can parse."""
    return {
        "domain":         _extract_domain(sentence),
        "tenant":         _extract_tenant(sentence),
        "amount_usd":     _extract_amount(sentence),
        "agent_id":       _extract_agent_id(sentence),
        "chain_id":       _extract_chain_id(sentence),
        "template_id":    _extract_template_id(sentence),
        "file_path":      _extract_file_path(sentence),
        "deal_id":        _extract_deal_id(sentence),
        "email":          _extract_email(sentence),
        "project_id":     _extract_project_id(sentence),
        "url":            _extract_url(sentence),
        "vendor_company": _extract_vendor_company(sentence),
    }
# ── END PATCH-LIBRARIAN-EXTRACTORS-R185 ──────────────────────────────────────



# ── Phase B wire intent registrations ──────────────────────────────────────

def _register_phase_b_intents():
    """Register the Phase B wires as callable intents."""

    _CATALOG.append({
        "intent": "find_agents",
        "keywords": ["find", "agent", "staffing", "lookup", "best", "rent"],
        "module": "src.agent_broker",
        "function": "find_agents",
        "args_extractor": lambda s: {
            "domain": _extract_domain(s) or "engineering",
            "requesting_tenant": _extract_tenant(s),
            "min_fitness": 0.0,
            "allow_cross_tenant": "cross" in s.lower() or "any tenant" in s.lower(),
        },
        "description": "Find agents matching domain + fitness + tenant policy",
        "examples": [
            "find me an engineering agent for tenant t1",
            "best agent for product domain",
            "rent an agent for t2 from any tenant",
        ],
    })

    _CATALOG.append({
        "intent": "get_best_agent",
        "keywords": ["best agent", "top agent"],
        "module": "src.agent_broker",
        "function": "get_best_agent",
        "args_extractor": lambda s: {
            "domain": _extract_domain(s) or "engineering",
            "requesting_tenant": _extract_tenant(s),
        },
        "description": "Single best-ranked agent for a domain",
        "examples": ["who's the best engineering agent", "top agent for t1 in design"],
    })

    _CATALOG.append({
        "intent": "broker_stats",
        "keywords": ["broker stats", "agent inventory", "how many agents"],
        "module": "src.agent_broker",
        "function": "broker_stats",
        "args_extractor": lambda s: {},
        "description": "Inventory of agent contracts + fitness coverage",
        "examples": ["broker stats", "how many agents are there"],
    })

    _CATALOG.append({
        "intent": "refresh_agent_fitness",
        "keywords": ["refresh fitness", "update fitness", "recalculate fitness"],
        "module": "src.agent_contract_fitness",
        "function": "refresh_all_agents",
        "args_extractor": lambda s: {},
        "description": "Recalculate fitness_score for all agents from observations",
        "examples": ["refresh all agent fitness", "update fitness scores"],
    })

    _CATALOG.append({
        "intent": "get_fitness_snapshot",
        "keywords": ["fitness snapshot", "fitness scores", "show fitness"],
        "module": "src.agent_contract_fitness",
        "function": "get_agent_fitness_snapshot",
        "args_extractor": lambda s: {},
        "description": "Read current agent fitness state across all contracts",
        "examples": ["show agent fitness scores", "fitness snapshot"],
    })

    _CATALOG.append({
        "intent": "record_rental",
        "keywords": ["record rental", "rental event", "book rental", "log rental"],
        "module": "src.chain_royalty",
        "function": "record_chain_revenue_event",
        "args_extractor": lambda s: {
            "chain_id": f"nl_request_{int(__import__('time').time())}",
            "agent_id": _extract_agent_id(s) or "lead_engineer",
            "renting_tenant": _extract_tenant(s),
            "gross_amount_usd": _extract_amount(s) or 0.0,
            "domain": _extract_domain(s),
        },
        "description": "Record a $X rental of agent_A by tenant_B with royalty split",
        "examples": [
            "record a $500 rental of lead_engineer by tenant t2",
            "log $1000 rental for t1 engineering work",
        ],
    })

    _CATALOG.append({
        "intent": "tenant_royalty",
        "keywords": ["royalty summary", "tenant earnings", "tenant payments"],
        "module": "src.chain_royalty",
        "function": "get_tenant_royalty_summary",
        "args_extractor": lambda s: {"tenant_id": _extract_tenant(s) or "t1"},
        "description": "Earned + paid + net for a tenant from staffing rentals",
        "examples": ["royalty summary for t1", "how much has t2 paid"],
    })

    _CATALOG.append({
        "intent": "import_requirements",
        "keywords": ["required artifacts", "what documents", "import gate"],
        "module": "src.import_gate",
        "function": "declare_required_artifacts",
        "args_extractor": lambda s: {
            "template_code": "saas_mvp" if "saas" in s.lower() else
                             "enterprise_outreach" if "enterprise" in s.lower() else
                             "marketing_launch" if "marketing" in s.lower() else
                             "saas_mvp",
        },
        "description": "What documents must be uploaded before a chain runs",
        "examples": [
            "what documents are required for a saas mvp",
            "required artifacts for enterprise outreach",
        ],
    })

    _CATALOG.append({
        "intent": "absorb_spec",
        "keywords": ["absorb", "ingest document", "load spec", "load business plan"],
        "module": "src.spec_to_identity",
        "function": "get_absorbed_specs",
        "args_extractor": lambda s: {"tenant_id": _extract_tenant(s)},
        "description": "List specs that have been absorbed into Murphy's identity",
        "examples": ["what specs has t1 absorbed", "show absorbed business plans"],
    })


# Auto-register on import
_register_phase_b_intents()


# ── Public API ──────────────────────────────────────────────────────────────

def list_catalog() -> List[Dict[str, Any]]:
    """Return the registered intent catalog (for inspection or UI)."""
    out = []
    for entry in _CATALOG:
        out.append({
            "intent": entry["intent"],
            "module": entry["module"],
            "function": entry["function"],
            "description": entry["description"],
            "examples": entry["examples"],
        })
    return out


def match_intent(sentence: str) -> Optional[Dict[str, Any]]:
    """
    Find the best-matching catalog entry for a sentence.

    Returns None if no entry matches.
    """
    s = sentence.lower()
    best = None
    best_score = 0
    for entry in _CATALOG:
        score = sum(1 for kw in entry["keywords"] if kw in s)
        if score > best_score:
            best_score = score
            best = entry
    if best_score == 0:
        return None
    return best


def plan_from_nl(sentence: str, execute: bool = False) -> Dict[str, Any]:
    """
    Map a natural-language sentence to a concrete component plan.

    Args:
        sentence: free-form request like "find me an engineering agent for t1"
        execute: if True, actually call the resolved function and include result

    Returns:
        {
          "request": original sentence,
          "matched_intent": name or None,
          "plan": {"module", "function", "args"},
          "executed": bool,
          "result": <if executed>,
          "error": <if execution failed>,
          "wire_version": "LIB-PLAN-001"
        }
    """
    entry = match_intent(sentence)
    if not entry:
        return {
            "request": sentence,
            "matched_intent": None,
            "plan": None,
            "executed": False,
            "result": None,
            "reason": "no_catalog_match",
            "wire_version": "LIB-PLAN-001",
        }

    try:
        args = entry["args_extractor"](sentence)
    except Exception as e:
        return {
            "request": sentence,
            "matched_intent": entry["intent"],
            "plan": None,
            "executed": False,
            "result": None,
            "error": f"args_extraction_failed: {e}",
            "wire_version": "LIB-PLAN-001",
        }

    plan = {
        "module": entry["module"],
        "function": entry["function"],
        "args": args,
        "description": entry["description"],
    }

    out = {
        "request": sentence,
        "matched_intent": entry["intent"],
        "plan": plan,
        "executed": False,
        "result": None,
        "wire_version": "LIB-PLAN-001",
    }

    if not execute:
        return out

    # Execute the plan
    try:
        mod = __import__(entry["module"], fromlist=[entry["function"]])
        fn = getattr(mod, entry["function"])
        result = fn(**args)
        out["executed"] = True
        out["result"] = result
    except Exception as e:
        out["executed"] = True
        out["result"] = None
        out["error"] = f"execution_failed: {type(e).__name__}: {e}"

    return out


def register_intent(
    intent: str,
    keywords: List[str],
    module: str,
    function: str,
    args_extractor: Callable[[str], Dict],
    description: str = "",
    examples: Optional[List[str]] = None,
) -> bool:
    """Allow new intents to be added at runtime."""
    _CATALOG.append({
        "intent": intent,
        "keywords": keywords,
        "module": module,
        "function": function,
        "args_extractor": args_extractor,
        "description": description,
        "examples": examples or [],
    })
    return True


if __name__ == "__main__":
    import json as _j
    print("── Catalog ──")
    for c in list_catalog():
        print(f"  • {c['intent']}: {c['description']}")
    print("\n── Tests ──")
    for s in [
        "find me an engineering agent for tenant t1",
        "best agent for product domain",
        "broker stats",
        "refresh all agent fitness",
        "show agent fitness scores",
        "record a $500 rental of lead_engineer by tenant t2",
        "royalty summary for t1",
        "what documents are required for a saas mvp",
    ]:
        r = plan_from_nl(s, execute=False)
        plan = r.get('plan')
        print(f"\n  Q: {s}")
        if plan:
            print(f"    intent: {r['matched_intent']}")
            print(f"    plan:   {plan['module']}.{plan['function']}({plan['args']})")
        else:
            print(f"    no match")
