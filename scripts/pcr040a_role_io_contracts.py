#!/usr/bin/env python3
"""
PCR-040a — Role I/O Contracts.

First slice of the projection-driven graph convergence architecture
(the founder's "ping-pong = information transformation" model).

WHAT THIS DOES:
  - Adds input_types and output_types fields to AgentBlueprint
  - Declares ROLE_IO_CONTRACTS mapping role_class -> (inputs, outputs)
  - select_team() populates the new fields from the contract
  - When no explicit contract exists, falls back to ([], []) — empty
    contract is the safe default (agent consumes prompt, produces
    artifact named after role)

WHAT THIS DOES NOT DO YET:
  - No execution change
  - No convergence loop
  - No graph wiring
  Those are PCR-040b and PCR-040c.

SAFETY:
  Pure additive. New fields have defaults, no existing call site
  breaks. Marker-based revert.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

DRP = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")

# ─── 1. Extend AgentBlueprint dataclass ──────────────────────────────────
AB_ANCHOR_OLD = '''class AgentBlueprint:
    agent_id: str
    role_class: str
    department: str
    reports_to: Optional[str]
    tone: str
    bias: str
    hitl_threshold: float
    capabilities: List[str]
    boundaries: List[str]
    task_brief: str
    emoji: str'''

AB_ANCHOR_NEW = '''class AgentBlueprint:
    agent_id: str
    role_class: str
    department: str
    reports_to: Optional[str]
    tone: str
    bias: str
    hitl_threshold: float
    capabilities: List[str]
    boundaries: List[str]
    task_brief: str
    emoji: str
    # PCR-040a — Role I/O contracts
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)'''

# ─── 2. Add ROLE_IO_CONTRACTS constant after BRIEFS ──────────────────────
# Anchor: the line right after BRIEFS dict closes. We'll insert before
# the next class definition (class DynamicRosettaPlanner).
IO_ANCHOR_OLD = '''class DynamicRosettaPlanner:
    """Pick your team for THIS task. plan() returns a DispatchPacket."""'''

IO_ANCHOR_NEW = '''# PCR-040a BEGIN role I/O contracts
#
# Each role_class declares what artifact-types it consumes (input_types)
# and what artifact-types it produces (output_types). The graph wires
# itself: output of agent A flows into input of agent B when B's input
# slot matches A's output type.
#
# Convention:
#   "prompt"  is the special root input every team has access to
#   "*_v1"    means the first round artifact of that type
#   "deliverable" is the special terminal output for the top coordinator
#
# Roles not listed here fall back to ([], []) which means "consumes
# prompt only, produces artifact named after role." Safe default.
ROLE_IO_CONTRACTS = {
    # ── business_strategy domain ─────────────────────────────────────
    "Strategy Lead": (
        ["prompt", "market_landscape", "competitor_set"],
        ["positioning_thesis", "value_prop", "go_to_market"],
    ),
    "Market Researcher": (
        ["prompt"],
        ["market_landscape", "competitor_set", "customer_segments"],
    ),
    "Financial Analyst": (
        ["prompt", "customer_segments", "positioning_thesis"],
        ["unit_economics", "revenue_model", "capital_plan"],
    ),
    "Product Architect": (
        ["prompt", "positioning_thesis", "value_prop"],
        ["system_design", "data_model", "integration_plan"],
    ),
    "Risk Assessor": (
        ["positioning_thesis", "unit_economics", "system_design"],
        ["risk_register", "mitigation_plan", "gate_criteria"],
    ),
    # ── sales domain ─────────────────────────────────────────────────
    "Sales Coordinator": (
        ["prompt", "pipeline_state", "outreach_draft"],
        ["sales_plan", "deliverable"],
    ),
    "CRM Analyst": (
        ["prompt"],
        ["pipeline_state", "deal_priorities"],
    ),
    "Outreach Writer": (
        ["prompt", "deal_priorities", "intel_signals"],
        ["outreach_draft"],
    ),
    # Market Researcher in sales context shadows business_strategy's
    # version — same role name, same contract.
    # ── engineering domain ───────────────────────────────────────────
    "Lead Engineer": (
        ["prompt", "test_plan", "security_audit"],
        ["architecture_decision", "deliverable"],
    ),
    "Code Executor": (
        ["prompt", "architecture_decision"],
        ["patch_set"],
    ),
    "QA Auditor": (
        ["patch_set"],
        ["test_plan", "regression_report"],
    ),
    "Security Reviewer": (
        ["patch_set"],
        ["security_audit"],
    ),
    # ── exec_admin domain ────────────────────────────────────────────
    "Coordinator": (
        ["prompt", "analysis_report", "schedule"],
        ["deliverable"],
    ),
    "Executive Analyst": (
        ["prompt"],
        ["analysis_report"],
    ),
    "Scheduler": (
        ["prompt", "analysis_report"],
        ["schedule"],
    ),
    # ── universal roles ──────────────────────────────────────────────
    "HITL Gate": (
        ["deliverable"],
        ["approval_decision"],
    ),
    "Auditor": (
        ["deliverable"],
        ["audit_report"],
    ),
}
# PCR-040a END role I/O contracts


class DynamicRosettaPlanner:
    """Pick your team for THIS task. plan() returns a DispatchPacket."""'''

# ─── 3. Wire select_team to populate the new fields ──────────────────────
ST_ANCHOR_OLD = '''            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
            ))'''

ST_ANCHOR_NEW = '''            # PCR-040a — pull I/O contract for this role (empty default)
            _io_in, _io_out = ROLE_IO_CONTRACTS.get(role_class, ([], []))
            team.append(AgentBlueprint(
                agent_id=agent_id, role_class=role_class, department=dept,
                reports_to=coordinator_id if not is_coord else None,
                tone=tone, bias=bias, hitl_threshold=hitl_thresh,
                capabilities=caps, boundaries=bounds,
                task_brief=brief, emoji=emoji,
                input_types=list(_io_in), output_types=list(_io_out),
            ))'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-040a patcher  verify={verify}  revert={revert}")
    print("=" * 60)
    src = DRP.read_text(encoding="utf-8")

    if revert:
        if "PCR-040a BEGIN" not in src and "input_types: List[str]" not in src:
            print("  · already absent")
            return 0
        src = src.replace(AB_ANCHOR_NEW, AB_ANCHOR_OLD, 1)
        src = src.replace(IO_ANCHOR_NEW, IO_ANCHOR_OLD, 1)
        src = src.replace(ST_ANCHOR_NEW, ST_ANCHOR_OLD, 1)
        if verify:
            print("  ✓ (verify) would revert PCR-040a")
            return 0
        DRP.write_text(src, encoding="utf-8")
        print("  ✓ reverted PCR-040a")
        return 0

    # Apply
    if "PCR-040a BEGIN" in src:
        print("  · already present")
        return 0

    if AB_ANCHOR_OLD not in src:
        print("  ✗ AgentBlueprint anchor not found")
        return 1
    if IO_ANCHOR_OLD not in src:
        print("  ✗ DynamicRosettaPlanner anchor not found")
        return 1
    if ST_ANCHOR_OLD not in src:
        print("  ✗ select_team anchor not found")
        return 1

    src = src.replace(AB_ANCHOR_OLD, AB_ANCHOR_NEW, 1)
    src = src.replace(IO_ANCHOR_OLD, IO_ANCHOR_NEW, 1)
    src = src.replace(ST_ANCHOR_OLD, ST_ANCHOR_NEW, 1)

    if verify:
        print("  ✓ (verify) would insert PCR-040a")
        return 0

    DRP.write_text(src, encoding="utf-8")
    print("  ✓ inserted PCR-040a")
    print("    - AgentBlueprint: +input_types, +output_types fields")
    print("    - ROLE_IO_CONTRACTS: 15 role contracts declared")
    print("    - select_team: populates I/O from contract dict")
    print("=" * 60)
    print("  ✓ done")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    return apply(verify=args.verify, revert=args.revert)


if __name__ == "__main__":
    sys.exit(main())
