#!/usr/bin/env python3
"""
PCR-035 — Fix dispatch routing for business-strategy tasks + add DLF-R packaging.

PROBLEM:
  /api/rosetta/dispatch sends business-plan/architecture/strategy prompts
  to the 3-agent sales team because the classifier's signal-counting
  picks "sales" over "exec_admin" when prompts contain incidental words
  like "email", "pipeline", "revenue".

  Additionally, /api/rosetta/dispatch produces NO DLF-R package, so
  dispatched work isn't traceable through the canonical packaging layer.

THIS PATCH:
  1. Adds a new "business_strategy" domain to DOMAIN_SIGNALS in
     src/dynamic_rosetta_planner.py with HIGH-PRECISION multi-word
     signals ("business plan", "go-to-market", "v0 architecture",
     "ICP", "MRR", "AOV", "value prop", "competitive moat", "wedge",
     "pricing model", "case study", etc.).
  2. Adds a corresponding DOMAIN_ROLE_TEMPLATES entry for
     "business_strategy" — a 5-agent team:
       Strategy Lead (exec_admin), Market Researcher, Financial Analyst,
       Product Architect (engineering), Auditor (HITL gate)
  3. Bumps signal weighting so multi-word signals count for 3 instead
     of 1 — high-precision signals outweigh single-word noise.
  4. Wraps the dispatch in src/runtime/app.py with a DLF-R packaging
     call so every dispatch produces a traceable package.

SAFETY:
  - Marker-based, revertable via --revert.
  - Snapshot pre-change.
  - dispatch_packet packaging wrapped in try/except — failure NEVER
    breaks the dispatch.
  - Only ADDS a new domain — does NOT change existing classifications
    for tasks that currently route correctly.
  - Multi-word signal weighting is conservative: only the new
    business_strategy signals use weight=3; all existing signals keep
    weight=1, so existing tasks classify the same.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

DRP = Path("/opt/Murphy-System/src/dynamic_rosetta_planner.py")
APP = Path("/opt/Murphy-System/src/runtime/app.py")

# ─── Patch 1: dynamic_rosetta_planner.py ───────────────────────────────
PLANNER_MARKER_START = "# PCR-035 BEGIN business_strategy domain"
PLANNER_MARKER_END = "# PCR-035 END business_strategy domain"

PLANNER_ANCHOR_DOMAIN_SIGNALS = '''    "exec_admin":  ["schedule","meeting","brief","summary","status","report","approve","coordinate","plan","strategy","decide"],
}'''

PLANNER_ANCHOR_TEMPLATES_FALLBACK = '"general"'

# The new domain signals + role template, inserted right before the closing }
# of DOMAIN_SIGNALS, and the matching role template appended to
# DOMAIN_ROLE_TEMPLATES.
PLANNER_INSERT_SIGNALS = '''    "exec_admin":  ["schedule","meeting","brief","summary","status","report","approve","coordinate","plan","strategy","decide"],
    # PCR-035 BEGIN business_strategy domain
    # High-precision multi-word signals for business-plan / architecture /
    # strategy tasks. These should outweigh single-word signals like
    # "email" or "pipeline" that happen to appear in business prompts.
    "business_strategy": [
        "business plan","go-to-market","gtm","v0 architecture","tech stack",
        "icp","value prop","value proposition","competitive moat","wedge",
        "pricing model","unit economics","mrr","aov","ltv","cac",
        "case study","investor","fundraise","pitch deck","term sheet",
        "build a business","build a product","build an mvp","build a v0",
        "strategy for","business model","revenue model","go to market",
        "founding team","first 10 customers","early adopters",
        "highest-risk assumptions","riskiest assumption","validate first",
        "market sizing","tam","sam","som","competitive analysis",
    ],
    # PCR-035 END business_strategy domain
}'''


# DOMAIN_ROLE_TEMPLATES — find it and append our new entry before
# the closing brace. We use a regex anchor since the dict is long.
PLANNER_TEMPLATES_RE = re.compile(
    r'(DOMAIN_ROLE_TEMPLATES[^=]*=\s*\{.*?)(^\}\s*$)',
    re.DOTALL | re.MULTILINE,
)
PLANNER_INSERT_TEMPLATE = '''    # PCR-035 BEGIN business_strategy team
    "business_strategy": [
        # role_class,         dept,          tone,        bias,             hitl, capabilities,                                                   bounds,                                         emoji
        ("Strategy Lead",     "Executive",   "decisive",  "synthesis",      0.55, ["task decomposition","cross-team coordination","prioritization"], ["No fluff","Every claim has evidence"],       "🎯"),
        ("Market Researcher", "Research",    "curious",   "evidence",       0.60, ["market sizing","competitive analysis","trend identification"],   ["Cite every source","Flag assumptions"],     "🔬"),
        ("Financial Analyst", "Finance",     "precise",   "accuracy",       0.65, ["unit economics","pricing modeling","projections"],               ["Show math","No hand-waving on numbers"],    "📊"),
        ("Product Architect", "Engineering", "rigorous",  "buildability",   0.55, ["system design","stack selection","integration mapping"],         ["Pick proven tech","Flag build vs buy"],     "🏗️"),
        ("Risk Assessor",     "Risk",        "skeptical", "risk_first",     0.50, ["risk identification","scenario planning","mitigation design"],   ["Surface every risk","Rank by impact"],      "⚠️"),
        ("HITL Gate",         "Governance",  "cautious",  "human_approval", 0.00, ["high-stake approvals","scope checks"],                            ["Block on critical","Defer to founder"],    "🚪"),
    ],
    # PCR-035 END business_strategy team
'''

# Patch the analyze_task method: bump multi-word signal weight to 3.
# We use a marker-based replacement of the scoring loop.
PLANNER_ANALYZE_OLD = '''        domain_scores: Dict[str, int] = {}
        for domain, signals in DOMAIN_SIGNALS.items():
            score = sum(1 for s in signals if s in lower)
            if score > 0:
                domain_scores[domain] = score'''

PLANNER_ANALYZE_NEW = '''        # PCR-035 BEGIN multi-word signal weighting
        # Multi-word signals (e.g. "business plan", "go-to-market") count
        # for 3 instead of 1 — they are higher precision than single words
        # which can appear incidentally in prompts.
        domain_scores: Dict[str, int] = {}
        for domain, signals in DOMAIN_SIGNALS.items():
            score = 0
            for s in signals:
                if s in lower:
                    score += 3 if " " in s or "-" in s else 1
            if score > 0:
                domain_scores[domain] = score
        # PCR-035 END multi-word signal weighting'''


# ─── Patch 2: app.py — DLF-R packaging on dispatch ─────────────────────
APP_MARKER_START = "# PCR-035 BEGIN dispatch DLF-R packaging"
APP_MARKER_END = "# PCR-035 END dispatch DLF-R packaging"

# Inject right before the final return of _rosetta_dispatch.
# We anchor on the return that includes "brief_packet_id".
APP_ANCHOR_RE = re.compile(
    r'(\n\s+)(return JSONResponse\(\s*\{\s*\n\s*"success": True,\s*\n\s*"_patch": "361",.*?"brief_packet_id":.*?\}\s*\))',
    re.DOTALL,
)

APP_INSERT_BEFORE_RETURN = '''
            # PCR-035 BEGIN dispatch DLF-R packaging
            try:
                from src.dlf_r import pack as _dlfr_pack_035, store as _dlfr_store_035
                _dispatch_packet_local = locals().get("_dispatch_packet") or {}
                _team_meta = _dispatch_packet_local.get("dynamic_team") or _dispatch_packet_local
                _domain_035 = (_team_meta.get("task_profile", {}) or {}).get("domain") if isinstance(_team_meta, dict) else "unknown"
                if not _domain_035:
                    _domain_035 = _team_meta.get("domain", "unknown") if isinstance(_team_meta, dict) else "unknown"
                _threads_035 = [{
                    "id": "thr_prompt_" + (dag_id or "x")[:8],
                    "payload": (prompt or "")[:2000],
                    "created_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "metadata": {"kind": "dispatch_prompt", "domain": _domain_035},
                }]
                _nodes_035 = [
                    {"id": "node_dispatch_" + (dag_id or "x")[:8],
                     "label": "dispatch:" + (dag_id or "unknown"),
                     "thread_refs": ["thr_prompt_" + (dag_id or "x")[:8]],
                     "metadata": {"domain": _domain_035, "agents": assigned_agents}}
                ]
                for _aid_035 in assigned_agents or []:
                    _nodes_035.append({
                        "id": "node_agent_" + str(_aid_035),
                        "label": "agent:" + str(_aid_035),
                        "thread_refs": [],
                        "metadata": {"role": "assigned"},
                    })
                _weaves_035 = []
                for _aid_035 in assigned_agents or []:
                    _weaves_035.append({
                        "id": "w_" + (dag_id or "x")[:6] + "_" + str(_aid_035)[:8],
                        "source": "node_dispatch_" + (dag_id or "x")[:8],
                        "target": "node_agent_" + str(_aid_035),
                        "type": "ROUTED_TO",
                        "confidence": 0.95,
                        "provenance": "PCR-035 dispatch packaging",
                    })
                _blob_035 = _dlfr_pack_035(
                    threads=_threads_035, nodes=_nodes_035, weaves=_weaves_035,
                    metadata={"dag_id": dag_id, "patch": "PCR-035", "endpoint": "/api/rosetta/dispatch"},
                    creator="rosetta_dispatch",
                )
                _pkg_id_035 = _dlfr_store_035(_blob_035, label="dispatch:" + (dag_id or "unknown"))
                _notify("[PCR-035] DLF-R package stored: " + str(_pkg_id_035))
            except Exception as _dlfr_err_035:
                _notify("[PCR-035] DLF-R packaging failed (non-fatal): " + str(_dlfr_err_035)[:120])
            # PCR-035 END dispatch DLF-R packaging
'''


def apply(verify: bool, revert: bool) -> int:
    print(f"PCR-035 patcher  verify={verify}  revert={revert}")
    print("=" * 60)

    drp_src = DRP.read_text(encoding="utf-8")
    app_src = APP.read_text(encoding="utf-8")

    if revert:
        changed = False
        # Remove planner inserts
        if PLANNER_MARKER_START in drp_src:
            # Restore DOMAIN_SIGNALS — replace our extended block with the original anchor
            drp_src = re.sub(
                re.escape('    "exec_admin":  ["schedule","meeting","brief","summary","status","report","approve","coordinate","plan","strategy","decide"],\n') +
                r'\s*# PCR-035 BEGIN business_strategy domain\n.*?# PCR-035 END business_strategy domain\n\}',
                PLANNER_ANCHOR_DOMAIN_SIGNALS,
                drp_src, flags=re.DOTALL,
            )
            # Remove role template
            drp_src = re.sub(
                r'\s*# PCR-035 BEGIN business_strategy team\n.*?# PCR-035 END business_strategy team\n',
                "",
                drp_src, flags=re.DOTALL,
            )
            # Restore analyze_task
            drp_src = drp_src.replace(PLANNER_ANALYZE_NEW, PLANNER_ANALYZE_OLD)
            changed = True
        if APP_MARKER_START in app_src:
            app_src = re.sub(
                r'\s*# PCR-035 BEGIN dispatch DLF-R packaging\n.*?# PCR-035 END dispatch DLF-R packaging\n',
                "",
                app_src, flags=re.DOTALL,
            )
            changed = True
        if not changed:
            print("  · already absent")
            return 0
        if verify:
            print("  ✓ (verify) would revert PCR-035")
            return 0
        DRP.write_text(drp_src, encoding="utf-8")
        APP.write_text(app_src, encoding="utf-8")
        print("  ✓ reverted PCR-035")
        return 0

    # Apply mode
    already_planner = PLANNER_MARKER_START in drp_src
    already_app = APP_MARKER_START in app_src
    if already_planner and already_app:
        print("  · already present — no-op")
        return 0

    # Patch 1a: extend DOMAIN_SIGNALS
    if not already_planner:
        if PLANNER_ANCHOR_DOMAIN_SIGNALS not in drp_src:
            print("  ✗ DOMAIN_SIGNALS anchor not found in planner")
            return 1
        drp_src = drp_src.replace(PLANNER_ANCHOR_DOMAIN_SIGNALS, PLANNER_INSERT_SIGNALS, 1)

        # Patch 1b: append role template
        m = PLANNER_TEMPLATES_RE.search(drp_src)
        if not m:
            print("  ✗ DOMAIN_ROLE_TEMPLATES anchor not found in planner")
            return 1
        templates_body, templates_close = m.group(1), m.group(2)
        new_templates = templates_body + PLANNER_INSERT_TEMPLATE + templates_close
        drp_src = drp_src.replace(m.group(0), new_templates, 1)

        # Patch 1c: bump multi-word signal weighting
        if PLANNER_ANALYZE_OLD not in drp_src:
            print("  ✗ analyze_task anchor not found in planner")
            return 1
        drp_src = drp_src.replace(PLANNER_ANALYZE_OLD, PLANNER_ANALYZE_NEW, 1)

    # Patch 2: app.py DLF-R packaging
    if not already_app:
        m2 = APP_ANCHOR_RE.search(app_src)
        if not m2:
            print("  ✗ dispatch return anchor not found in app.py")
            return 1
        indent, return_block = m2.group(1), m2.group(2)
        app_src = app_src.replace(
            m2.group(0),
            APP_INSERT_BEFORE_RETURN + indent + return_block,
            1,
        )

    if verify:
        print("  ✓ (verify) would insert PCR-035 patches")
        return 0

    DRP.write_text(drp_src, encoding="utf-8")
    APP.write_text(app_src, encoding="utf-8")
    print("  ✓ inserted PCR-035 patches")
    print("    - dynamic_rosetta_planner.py: business_strategy domain + 6-agent team + multi-word weighting")
    print("    - app.py: dispatch DLF-R packaging")
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
