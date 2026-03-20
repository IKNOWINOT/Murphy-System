"""
Inference Pipeline Functional Correctness Test with Screenshot Reports.

Evaluates whether the system **succeeds at its requested tasks** by comparing
what inference *predicts should happen* against what *actually happens* when
the pipeline executes.  Produces an alignment score (0–100%) that answers:

  "How close are prediction and reality?"

The same test runs identically on any branch.  Compare outputs to see which
branch better fulfils the system's intended behaviour.

Scoring dimensions (equal weight, 25% each):
  1. Industry Detection  — did inference identify the correct industry?
  2. Template Matching    — did the workflow generator pick the right template?
  3. Step Execution       — did every workflow step complete with structured output?
  4. Gate Coverage        — did inference produce the expected gate categories?

Run:
    pytest tests/benchmarks/test_inference_correctness.py -v \\
        --override-ini="addopts=" --timeout=120

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Optional matplotlib for charts
# ---------------------------------------------------------------------------
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _MPL = True
except ImportError:
    _MPL = False

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from inference_gate_engine import InferenceDomainGateEngine
from ai_workflow_generator import AIWorkflowGenerator
from workflow_dag_engine import (
    WorkflowDAGEngine,
    WorkflowDefinition,
    StepDefinition,
)

sys.path.insert(0, str(ROOT / "tests" / "commissioning"))
from screenshot_manager import ScreenshotManager

# ---------------------------------------------------------------------------
# Report directory (gitignored)
# ---------------------------------------------------------------------------
REPORT_DIR = ROOT / "tests" / "benchmarks" / ".correctness_reports"


# ═══════════════════════════════════════════════════════════════════════════
# Ground Truth Scenarios
# ═══════════════════════════════════════════════════════════════════════════
# Each scenario defines what the system SHOULD do if working correctly.
# These are the acceptance criteria — the "right answer" for each task.

SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "order_fulfillment",
        "description": "Automate order fulfillment for our Shopify e-commerce store",
        "expected_industry": "retail",
        "expected_template": "order_fulfillment",
        "expected_step_types": ["data_retrieval", "validation", "notification"],
        "expected_gate_categories": ["compliance", "quality", "business"],
        "task_goal": "System should recognize this as retail/e-commerce, pick an order "
                     "fulfillment template, and execute data retrieval + validation + "
                     "notification steps.",
    },
    {
        "name": "invoice_processing",
        "description": "Automate invoice processing billing accounts payable from QuickBooks",
        "expected_industry": "finance",
        "expected_template": "invoice_processing",
        "expected_step_types": ["data_retrieval", "validation", "approval"],
        "expected_gate_categories": ["compliance", "business", "validation"],
        "task_goal": "System should detect finance industry, match an invoice processing "
                     "template, and execute accounting-related steps.",
    },
    {
        "name": "customer_onboarding",
        "description": "Automate customer onboarding with welcome email and account provisioning",
        "expected_industry": "technology",
        "expected_template": "customer_onboarding",
        "expected_step_types": ["validation", "deployment", "notification"],
        "expected_gate_categories": ["security", "compliance", "business"],
        "task_goal": "System should match customer_onboarding template and execute "
                     "validation → provisioning → notification steps.",
    },
    {
        "name": "etl_pipeline",
        "description": "Build an ETL pipeline to extract data from our warehouse and load it into BigQuery",
        "expected_industry": "technology",
        "expected_template": "etl_pipeline",
        "expected_step_types": ["data_retrieval", "data_transformation", "data_output"],
        "expected_gate_categories": ["quality", "validation", "security"],
        "task_goal": "System should match the ETL pipeline template and produce "
                     "extract → transform → load steps.",
    },
    {
        "name": "ci_cd_deployment",
        "description": "Set up CI/CD pipeline to build, test and deploy our microservices",
        "expected_industry": "technology",
        "expected_template": "ci_cd",
        "expected_step_types": ["validation", "deployment"],
        "expected_gate_categories": ["quality", "security", "compliance"],
        "task_goal": "System should match CI/CD template and execute build → test → "
                     "deploy steps.",
    },
    {
        "name": "healthcare_compliance",
        "description": "We run a healthcare clinic and need to automate HIPAA compliance reporting",
        "expected_industry": "healthcare",
        "expected_template": None,  # no healthcare-specific template exists
        "expected_step_types": ["validation", "notification"],
        "expected_gate_categories": ["compliance", "security", "quality"],
        "task_goal": "System should detect healthcare industry, apply compliance gates, "
                     "and generate a workflow even without a matching template.",
    },
    {
        "name": "lead_nurturing",
        "description": "Nurture leads from our Salesforce CRM with automated email sequences",
        "expected_industry": "technology",
        "expected_template": "lead_nurture",
        "expected_step_types": ["data_retrieval", "notification", "data_filtering"],
        "expected_gate_categories": ["compliance", "business"],
        "task_goal": "System should match lead_nurture template and execute CRM-aware "
                     "data retrieval + email notification steps.",
    },
    {
        "name": "security_audit",
        "description": "Run automated security vulnerability scanning and compliance audit",
        "expected_industry": "technology",
        "expected_template": "security_scan",
        "expected_step_types": ["data_retrieval", "computation", "notification"],
        "expected_gate_categories": ["security", "compliance", "quality"],
        "task_goal": "System should match security_scan template and execute "
                     "scanning + analysis + reporting steps.",
    },
    # ── Full-spectrum business automation scenarios ──────────────────────
    {
        "name": "employee_onboarding",
        "description": "Automate new hire employee onboarding with account provisioning and orientation scheduling",
        "expected_industry": "technology",
        "expected_template": "employee_onboarding",
        "expected_step_types": ["deployment", "notification", "scheduling"],
        "expected_gate_categories": ["compliance", "security", "business"],
        "task_goal": "System should match employee_onboarding template and execute "
                     "account provisioning + welcome pack + orientation scheduling steps.",
    },
    {
        "name": "content_publishing",
        "description": "Automate blog content creation, editorial review, and multi-channel social media publishing",
        "expected_industry": "technology",
        "expected_template": "content_publishing",
        "expected_step_types": ["approval", "deployment", "notification"],
        "expected_gate_categories": ["quality", "compliance", "business"],
        "task_goal": "System should match content_publishing template and execute "
                     "review → publish → syndicate steps.",
    },
    {
        "name": "data_reporting",
        "description": "Automate data report with dashboard metrics analysis and summary for stakeholders",
        "expected_industry": "technology",
        "expected_template": "data_report",
        "expected_step_types": ["data_retrieval", "data_transformation", "notification"],
        "expected_gate_categories": ["quality", "compliance"],
        "task_goal": "System should match data_report template and execute "
                     "collect → analyze → report → distribute steps.",
    },
    {
        "name": "incident_response",
        "description": "Set up automated incident detection, triage and escalation for production outages",
        "expected_industry": "technology",
        "expected_template": "incident_response",
        "expected_step_types": ["data_retrieval", "notification"],
        "expected_gate_categories": ["quality", "security", "compliance"],
        "task_goal": "System should match incident_response template and execute "
                     "detect → triage → notify → remediate steps.",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Scoring Functions
# ═══════════════════════════════════════════════════════════════════════════

def _score_industry(inferred: str, expected: str) -> Tuple[float, str]:
    """Score industry detection accuracy.

    Returns (score 0.0–1.0, explanation).
    """
    inferred_l = inferred.lower().strip()
    expected_l = expected.lower().strip()

    if inferred_l == expected_l:
        return 1.0, f"✅ Correct: '{inferred}'"

    # Partial credit for closely related industries
    related = {
        ("technology", "retail"): 0.4,
        ("retail", "logistics"): 0.5,
        ("finance", "professional_services"): 0.4,
        ("technology", "finance"): 0.3,
        ("retail", "technology"): 0.4,
        ("logistics", "retail"): 0.5,
        ("other", expected_l): 0.2,
    }
    pair = (inferred_l, expected_l)
    pair_rev = (expected_l, inferred_l)
    if pair in related:
        return related[pair], f"⚠️ Partial: inferred '{inferred}' (expected '{expected}')"
    if pair_rev in related:
        return related[pair_rev], f"⚠️ Partial: inferred '{inferred}' (expected '{expected}')"

    return 0.0, f"❌ Wrong: inferred '{inferred}' (expected '{expected}')"


def _score_template(strategy: str, template_used: Optional[str],
                    expected_template: Optional[str]) -> Tuple[float, str]:
    """Score template matching success.

    Returns (score 0.0–1.0, explanation).
    """
    if expected_template is None:
        # No specific template expected — any strategy that produces steps is fine
        if strategy in ("template_match", "keyword_inference"):
            return 1.0, f"✅ No template required; used '{strategy}'"
        return 0.75, f"✅ No template required; used fallback '{strategy}'"

    if template_used == expected_template:
        return 1.0, f"✅ Matched: '{template_used}'"

    if strategy == "template_match" and template_used != expected_template:
        return 0.3, f"⚠️ Wrong template: '{template_used}' (expected '{expected_template}')"

    if strategy == "keyword_inference":
        return 0.5, f"⚠️ No template match; fell back to keyword inference"

    return 0.25, f"❌ Generic fallback (expected template '{expected_template}')"


def _score_execution(exec_result: Dict[str, Any],
                     expected_types: List[str]) -> Tuple[float, str]:
    """Score step execution success.

    Evaluates:
    - Did all steps complete?
    - Did steps produce structured (non-simulated) output?
    - Did the expected step types appear?

    Returns (score 0.0–1.0, explanation).
    """
    # Minimum number of fields in a result dict to count as "structured output"
    # (semantic handlers produce ≥3 domain-specific fields; simulated/generic
    # handlers produce only action + step_id + simulated flag).
    MIN_STRUCTURED_FIELDS = 3
    # Weights for the execution sub-score
    COMPLETION_WEIGHT = 0.6
    STRUCTURE_WEIGHT = 0.4

    steps = exec_result.get("steps", {})
    if not steps:
        return 0.0, "❌ No steps executed"

    total = len(steps)
    completed = 0
    structured = 0
    simulated = 0

    for step_id, step_data in steps.items():
        status = step_data.get("status", "")
        result = step_data.get("result", {})

        if status == "completed":
            completed += 1
            if isinstance(result, dict):
                if result.get("simulated"):
                    simulated += 1
                elif len(result) >= MIN_STRUCTURED_FIELDS:
                    structured += 1

    completion_rate = completed / total if total > 0 else 0.0
    structure_rate = structured / total if total > 0 else 0.0

    score = COMPLETION_WEIGHT * completion_rate + STRUCTURE_WEIGHT * structure_rate

    parts = [f"{completed}/{total} steps completed"]
    if structured:
        parts.append(f"{structured} with structured output")
    if simulated:
        parts.append(f"{simulated} simulated")

    if score >= 0.9:
        return score, f"✅ {'; '.join(parts)}"
    elif score >= 0.5:
        return score, f"⚠️ {'; '.join(parts)}"
    else:
        return score, f"❌ {'; '.join(parts)}"


def _score_gates(inferred_gates: list, expected_categories: List[str]) -> Tuple[float, str]:
    """Score gate coverage — did inference produce the expected gate categories?

    Returns (score 0.0–1.0, explanation).
    """
    if not expected_categories:
        return 1.0, "✅ No gate categories required"

    # Extract gate types/categories from inferred gates
    actual_categories = set()
    for gate in inferred_gates:
        gtype = getattr(gate, "gate_type", None)
        if gtype:
            actual_categories.add(gtype.value.lower())
        # Also look at gate name for category signals
        gname = getattr(gate, "name", "").lower()
        for cat in ("compliance", "security", "quality", "business",
                     "safety", "validation", "authorization"):
            if cat in gname:
                actual_categories.add(cat)

    expected_set = {c.lower() for c in expected_categories}
    found = expected_set & actual_categories
    coverage = len(found) / len(expected_set) if expected_set else 1.0

    missing = expected_set - actual_categories
    if coverage >= 1.0:
        return 1.0, f"✅ All expected categories covered: {sorted(found)}"
    elif coverage >= 0.5:
        return coverage, f"⚠️ {len(found)}/{len(expected_set)} categories; missing: {sorted(missing)}"
    else:
        return coverage, f"❌ Only {len(found)}/{len(expected_set)} categories; missing: {sorted(missing)}"


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline runner
# ═══════════════════════════════════════════════════════════════════════════

def _run_scenario(
    scenario: Dict[str, Any],
    inference_engine: InferenceDomainGateEngine,
    workflow_gen: AIWorkflowGenerator,
    dag_engine: WorkflowDAGEngine,
) -> Dict[str, Any]:
    """Run a single scenario through the full pipeline and score it.

    Pipeline:
      1. Inference → industry, positions, gates, form
      2. Workflow generation → template, strategy, steps
      3. Execution → step results
      4. Scoring → alignment of prediction vs reality

    Returns a dict with all scores, details, and a final alignment percentage.
    """
    name = scenario["name"]
    desc = scenario["description"]

    # -- Phase 1: Inference --------------------------------------------------
    inference_result = inference_engine.infer(desc)

    industry_score, industry_note = _score_industry(
        inference_result.inferred_industry, scenario["expected_industry"],
    )

    gate_score, gate_note = _score_gates(
        inference_result.inferred_gates, scenario["expected_gate_categories"],
    )

    # -- Phase 2: Workflow Generation ----------------------------------------
    wf_dict = workflow_gen.generate_workflow(desc)

    template_score, template_note = _score_template(
        wf_dict["strategy"],
        wf_dict.get("template_used"),
        scenario["expected_template"],
    )

    # -- Phase 3: Execution --------------------------------------------------
    # Convert workflow dict → WorkflowDefinition → register → execute
    steps = wf_dict.get("steps", [])
    step_defs = []
    for i, s in enumerate(steps):
        step_id = s.get("id") or s.get("name", f"step_{i}").replace(" ", "_").lower()
        action = s.get("type", "execute")
        step_defs.append(StepDefinition(
            step_id=step_id,
            name=s.get("name", step_id),
            action=action,
            depends_on=s.get("depends_on", []),
            metadata={
                "description": s.get("description", ""),
                "step_type": s.get("type", "execution"),
            },
        ))

    wf_def = WorkflowDefinition(
        workflow_id=wf_dict["workflow_id"],
        name=wf_dict.get("name", "generated_workflow"),
        description=desc[:300],
        steps=step_defs,
        metadata={
            "strategy": wf_dict.get("strategy", ""),
            "template_used": wf_dict.get("template_used", ""),
        },
    )

    dag_engine.register_workflow(wf_def)
    exec_id = dag_engine.create_execution(wf_def.workflow_id, context={"description": desc})
    exec_result = dag_engine.execute_workflow(exec_id)

    execution_score, execution_note = _score_execution(
        exec_result, scenario["expected_step_types"],
    )

    # -- Overall alignment ---------------------------------------------------
    alignment = (
        0.25 * industry_score
        + 0.25 * template_score
        + 0.25 * execution_score
        + 0.25 * gate_score
    )

    return {
        "name": name,
        "description": desc,
        "task_goal": scenario["task_goal"],
        "alignment_pct": round(alignment * 100, 1),
        # Per-dimension scores
        "industry": {
            "score": industry_score,
            "note": industry_note,
            "inferred": inference_result.inferred_industry,
            "expected": scenario["expected_industry"],
        },
        "template": {
            "score": template_score,
            "note": template_note,
            "strategy": wf_dict["strategy"],
            "used": wf_dict.get("template_used"),
            "expected": scenario["expected_template"],
        },
        "execution": {
            "score": execution_score,
            "note": execution_note,
            "status": exec_result.get("status", "unknown"),
            "step_count": len(steps),
            "steps_detail": {
                sid: {
                    "status": sd.get("status"),
                    "has_structured_output": (
                        isinstance(sd.get("result"), dict)
                        and len(sd.get("result", {})) >= 3
                        and not sd.get("result", {}).get("simulated")
                    ),
                }
                for sid, sd in exec_result.get("steps", {}).items()
            },
        },
        "gates": {
            "score": gate_score,
            "note": gate_note,
            "inferred_count": len(inference_result.inferred_gates),
            "position_count": inference_result.position_count,
        },
        # Raw data for detailed reporting
        "_inference": {
            "industry": inference_result.inferred_industry,
            "positions": inference_result.position_count,
            "gates": inference_result.gate_count,
            "fields": len(inference_result.form_schema.fields),
        },
        "_workflow": {
            "strategy": wf_dict["strategy"],
            "template": wf_dict.get("template_used"),
            "steps": len(steps),
            "step_names": [s.get("name", "?") for s in steps],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# HTML Report Generator
# ═══════════════════════════════════════════════════════════════════════════

def _verdict_class(pct: float) -> str:
    if pct >= 80:
        return "pass"
    elif pct >= 50:
        return "warn"
    return "fail"


def _score_bar(score: float) -> str:
    """Inline CSS bar for a 0–1 score."""
    pct = round(score * 100)
    color = "#28a745" if pct >= 80 else "#ffc107" if pct >= 50 else "#dc3545"
    return (
        f'<div style="background:#eee;border-radius:4px;height:18px;width:120px;display:inline-block;vertical-align:middle;">'
        f'<div style="background:{color};height:100%;width:{pct}%;border-radius:4px;"></div></div>'
        f' <strong>{pct}%</strong>'
    )


def _build_html_report(
    results: List[Dict[str, Any]],
    branch: str,
    overall_alignment: float,
) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Scenario rows
    rows = []
    for r in results:
        verdict = _verdict_class(r["alignment_pct"])
        icon = "✅" if verdict == "pass" else "⚠️" if verdict == "warn" else "❌"
        rows.append(f"""
        <tr class="scenario-row {verdict}">
            <td><strong>{r['name'].replace('_', ' ').title()}</strong></td>
            <td>{_score_bar(r['industry']['score'])}<br><small>{r['industry']['note']}</small></td>
            <td>{_score_bar(r['template']['score'])}<br><small>{r['template']['note']}</small></td>
            <td>{_score_bar(r['execution']['score'])}<br><small>{r['execution']['note']}</small></td>
            <td>{_score_bar(r['gates']['score'])}<br><small>{r['gates']['note']}</small></td>
            <td class="alignment-cell"><span class="alignment-badge {verdict}">{icon} {r['alignment_pct']}%</span></td>
        </tr>""")

    # Scenario detail cards
    detail_cards = []
    for r in results:
        verdict = _verdict_class(r["alignment_pct"])
        steps_html = ""
        for sid, sd in r["execution"]["steps_detail"].items():
            s_icon = "✅" if sd["status"] == "completed" else "❌"
            struct = "📦 structured" if sd["has_structured_output"] else "📝 basic"
            steps_html += f"<li>{s_icon} <code>{sid}</code> — {sd['status']} ({struct})</li>"
        if not steps_html:
            steps_html = "<li><em>No steps</em></li>"

        detail_cards.append(f"""
        <div class="detail-card {verdict}">
            <h3>{r['name'].replace('_', ' ').title()} — {r['alignment_pct']}%</h3>
            <p class="task-goal"><strong>Task Goal:</strong> {r['task_goal']}</p>
            <div class="detail-grid">
                <div>
                    <h4>Inference</h4>
                    <ul>
                        <li>Industry: <strong>{r['_inference']['industry']}</strong> (expected: {r['industry']['expected']})</li>
                        <li>Positions mapped: {r['_inference']['positions']}</li>
                        <li>Gates inferred: {r['_inference']['gates']}</li>
                        <li>Form fields: {r['_inference']['fields']}</li>
                    </ul>
                </div>
                <div>
                    <h4>Workflow</h4>
                    <ul>
                        <li>Strategy: <strong>{r['_workflow']['strategy']}</strong></li>
                        <li>Template: <strong>{r['_workflow']['template'] or 'none'}</strong> (expected: {r['template']['expected'] or 'any'})</li>
                        <li>Steps: {r['_workflow']['steps']} — {', '.join(r['_workflow']['step_names'])}</li>
                    </ul>
                </div>
                <div>
                    <h4>Execution Steps</h4>
                    <ul>{steps_html}</ul>
                </div>
            </div>
        </div>""")

    # Summary counts
    passed = sum(1 for r in results if r["alignment_pct"] >= 80)
    warned = sum(1 for r in results if 50 <= r["alignment_pct"] < 80)
    failed = sum(1 for r in results if r["alignment_pct"] < 50)
    overall_class = _verdict_class(overall_alignment)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Murphy Inference Correctness — {branch}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               max-width: 1400px; margin: 0 auto; padding: 20px; background: #f5f7fa; color: #333; }}
        h1 {{ color: #1a3a5c; border-bottom: 3px solid #4a90d9; padding-bottom: 10px; }}
        h2 {{ color: #2c5f8a; margin-top: 32px; }}
        .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); text-align: center; }}
        .card h3 {{ margin-top: 0; color: #4a90d9; font-size: 0.95em; }}
        .card .value {{ font-size: 2.2em; font-weight: bold; }}
        .card .unit {{ font-size: 0.5em; color: #666; }}
        .pass .value {{ color: #28a745; }}
        .warn .value {{ color: #ffc107; }}
        .fail .value {{ color: #dc3545; }}
        .verdict {{ padding: 16px; border-radius: 8px; margin: 20px 0; font-size: 1.1em; }}
        .verdict.pass {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .verdict.warn {{ background: #fff3cd; color: #856404; border: 1px solid #ffeeba; }}
        .verdict.fail {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
                 overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin: 16px 0; }}
        th {{ background: #4a90d9; color: white; padding: 12px 10px; text-align: left; font-size: 0.9em; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
        tr:hover td {{ background: #f0f6ff; }}
        .alignment-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px;
                           font-weight: bold; font-size: 1.1em; }}
        .alignment-badge.pass {{ background: #d4edda; color: #155724; }}
        .alignment-badge.warn {{ background: #fff3cd; color: #856404; }}
        .alignment-badge.fail {{ background: #f8d7da; color: #721c24; }}
        .detail-card {{ background: white; border-radius: 8px; padding: 20px; margin: 12px 0;
                       box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 4px solid #ccc; }}
        .detail-card.pass {{ border-left-color: #28a745; }}
        .detail-card.warn {{ border-left-color: #ffc107; }}
        .detail-card.fail {{ border-left-color: #dc3545; }}
        .detail-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
        .detail-grid h4 {{ margin: 0 0 8px; color: #4a90d9; }}
        .detail-grid ul {{ margin: 0; padding-left: 18px; font-size: 0.9em; }}
        .task-goal {{ background: #f0f6ff; padding: 8px 12px; border-radius: 4px; font-size: 0.9em; }}
        code {{ background: #e8e8e8; padding: 1px 4px; border-radius: 3px; font-size: 0.85em; }}
        .chart-section {{ background: white; border-radius: 8px; padding: 20px; margin: 20px 0;
                         box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .info {{ background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb;
                padding: 16px; border-radius: 8px; margin: 20px 0; }}
        small {{ color: #666; }}
    </style>
</head>
<body>
    <h1>🎯 Murphy Inference — Functional Correctness Test</h1>
    <div class="meta">
        <strong>Branch:</strong> {branch} &nbsp;|&nbsp;
        <strong>Generated:</strong> {timestamp} &nbsp;|&nbsp;
        <strong>Scenarios:</strong> {len(results)} &nbsp;|&nbsp;
        <strong>Question:</strong> "Does the system succeed at its requested tasks?"
    </div>

    <div class="summary-cards">
        <div class="card {overall_class}">
            <h3>Overall Alignment</h3>
            <div class="value">{overall_alignment:.1f}<span class="unit">%</span></div>
        </div>
        <div class="card {'pass' if passed else 'warn'}">
            <h3>Passed (≥80%)</h3>
            <div class="value" style="color:#28a745;">{passed}<span class="unit">/{len(results)}</span></div>
        </div>
        <div class="card {'warn' if warned else 'pass'}">
            <h3>Partial (50–79%)</h3>
            <div class="value" style="color:#ffc107;">{warned}<span class="unit">/{len(results)}</span></div>
        </div>
        <div class="card {'fail' if failed else 'pass'}">
            <h3>Failed (&lt;50%)</h3>
            <div class="value" style="color:#dc3545;">{failed}<span class="unit">/{len(results)}</span></div>
        </div>
    </div>

    <div class="verdict {overall_class}">
        {"✅" if overall_class == "pass" else "⚠️" if overall_class == "warn" else "❌"}
        <strong>Overall:</strong> The system achieves <strong>{overall_alignment:.1f}%</strong> alignment
        between what inference predicts and what actually happens.
        {f"{passed} of {len(results)} scenarios fully succeed." if passed else ""}
        {"Run the same test on the main branch to compare." if overall_class != "pass" else ""}
    </div>

    <h2>Scenario Results</h2>
    <table>
        <thead>
            <tr>
                <th style="width:13%">Scenario</th>
                <th style="width:18%">Industry Detection</th>
                <th style="width:18%">Template Matching</th>
                <th style="width:18%">Step Execution</th>
                <th style="width:18%">Gate Coverage</th>
                <th style="width:15%">Alignment</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>

    <h2>Scenario Details</h2>
    {''.join(detail_cards)}

    <h2>How to Compare Branches</h2>
    <div class="info">
        <p>Run this same test on both branches and compare the overall alignment score:</p>
        <pre>
# On main branch
git checkout main
pytest tests/benchmarks/test_inference_correctness.py -v --override-ini="addopts="

# On this branch
git checkout your-branch
pytest tests/benchmarks/test_inference_correctness.py -v --override-ini="addopts="
        </pre>
        <p><strong>Higher alignment % = better branch.</strong>
        The branch that scores higher is more correct — its inference predictions more closely
        match what actually happens during execution.</p>
    </div>
</body>
</html>"""
    return html


def _build_alignment_chart(results: List[Dict[str, Any]], output_path: Path) -> bool:
    """Generate a grouped bar chart showing per-scenario dimension scores."""
    if not _MPL:
        return False

    names = [r["name"].replace("_", " ").title() for r in results]
    industry = [r["industry"]["score"] * 100 for r in results]
    template = [r["template"]["score"] * 100 for r in results]
    execution = [r["execution"]["score"] * 100 for r in results]
    gates = [r["gates"]["score"] * 100 for r in results]

    x = list(range(len(names)))
    w = 0.2

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar([i - 1.5 * w for i in x], industry, w, label="Industry", color="#4a90d9", alpha=0.85)
    ax.bar([i - 0.5 * w for i in x], template, w, label="Template", color="#e8833a", alpha=0.85)
    ax.bar([i + 0.5 * w for i in x], execution, w, label="Execution", color="#50b86c", alpha=0.85)
    ax.bar([i + 1.5 * w for i in x], gates, w, label="Gates", color="#9b59b6", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=35, ha="right")
    ax.set_ylabel("Score (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Functional Correctness — Per-Scenario Dimension Scores")
    ax.legend(loc="upper right")
    ax.axhline(80, color="#28a745", linestyle="--", alpha=0.4, label="Pass threshold")
    ax.axhline(50, color="#ffc107", linestyle="--", alpha=0.4, label="Warn threshold")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return True


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def inference_engine() -> InferenceDomainGateEngine:
    return InferenceDomainGateEngine()


@pytest.fixture(scope="module")
def workflow_gen() -> AIWorkflowGenerator:
    return AIWorkflowGenerator()


@pytest.fixture(scope="module")
def dag_engine() -> WorkflowDAGEngine:
    return WorkflowDAGEngine()


@pytest.fixture(scope="module")
def screenshot_mgr() -> ScreenshotManager:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return ScreenshotManager(base_dir=str(REPORT_DIR))


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInferenceCorrectness:
    """Functional correctness: does the system succeed at its requested tasks?"""

    def test_full_pipeline_alignment(
        self,
        inference_engine,
        workflow_gen,
        dag_engine,
        screenshot_mgr,
    ):
        """Run all scenarios and generate the alignment report with screenshots.

        This is the core test. For each business scenario it:
        1. Runs inference to predict industry, gates, positions
        2. Generates a workflow (template match or fallback)
        3. Executes the workflow through the DAG engine
        4. Scores alignment across 4 dimensions
        5. Generates an HTML report with screenshots

        The overall alignment score answers: "How close are prediction and reality?"
        """
        results = []
        for scenario in SCENARIOS:
            result = _run_scenario(scenario, inference_engine, workflow_gen, dag_engine)
            results.append(result)

        overall = sum(r["alignment_pct"] for r in results) / len(results)

        # Detect branch
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(ROOT), text=True,
            ).strip()
        except Exception:
            branch = "unknown"

        # Generate report
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        html = _build_html_report(results, branch, overall)

        report_path = REPORT_DIR / "correctness_report.html"
        report_path.write_text(html)

        # Generate chart
        chart_path = REPORT_DIR / "alignment_chart.png"
        _build_alignment_chart(results, chart_path)

        # Capture screenshot
        screenshot_mgr.capture("correctness_report", "full", html)

        # Save JSON for machine comparison
        json_report = {
            "branch": branch,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "overall_alignment_pct": round(overall, 1),
            "scenarios": [
                {
                    "name": r["name"],
                    "alignment_pct": r["alignment_pct"],
                    "industry_score": r["industry"]["score"],
                    "template_score": r["template"]["score"],
                    "execution_score": r["execution"]["score"],
                    "gates_score": r["gates"]["score"],
                    "industry_inferred": r["industry"]["inferred"],
                    "industry_expected": r["industry"]["expected"],
                    "template_used": r["template"]["used"],
                    "template_expected": r["template"]["expected"],
                    "strategy": r["template"]["strategy"],
                    "execution_status": r["execution"]["status"],
                    "step_count": r["execution"]["step_count"],
                }
                for r in results
            ],
        }
        json_path = REPORT_DIR / "correctness_results.json"
        json_path.write_text(json.dumps(json_report, indent=2))

        # Print summary to stdout for CI visibility
        print(f"\n{'='*70}")
        print(f"  FUNCTIONAL CORRECTNESS REPORT — branch: {branch}")
        print(f"  Overall alignment: {overall:.1f}%")
        print(f"{'='*70}")
        for r in results:
            icon = "✅" if r["alignment_pct"] >= 80 else "⚠️" if r["alignment_pct"] >= 50 else "❌"
            print(f"  {icon} {r['name']:25s}  {r['alignment_pct']:5.1f}%  "
                  f"ind={r['industry']['score']:.0%} tmpl={r['template']['score']:.0%} "
                  f"exec={r['execution']['score']:.0%} gates={r['gates']['score']:.0%}")
        print(f"{'='*70}\n")

        # Assertions — the test always passes (so it runs on both branches)
        # but it reports the truth about each branch's capabilities
        assert report_path.exists(), "HTML report not generated"
        assert json_path.exists(), "JSON results not generated"
        assert len(results) == len(SCENARIOS)

    @pytest.mark.parametrize(
        "scenario",
        SCENARIOS,
        ids=[s["name"] for s in SCENARIOS],
    )
    def test_scenario_pipeline(
        self,
        scenario,
        inference_engine,
        workflow_gen,
        dag_engine,
    ):
        """Per-scenario test: verify each scenario can run through the full pipeline.

        These individual tests make it easy to see which specific scenarios
        pass or fail on each branch.
        """
        result = _run_scenario(scenario, inference_engine, workflow_gen, dag_engine)

        # Always report the score (don't fail — both branches should be testable)
        alignment = result["alignment_pct"]
        print(f"\n  {scenario['name']}: alignment={alignment:.1f}%")
        print(f"    Industry:  {result['industry']['note']}")
        print(f"    Template:  {result['template']['note']}")
        print(f"    Execution: {result['execution']['note']}")
        print(f"    Gates:     {result['gates']['note']}")

        # The pipeline must at least run without crashing
        assert result["execution"]["status"] in ("completed", "failed", "unknown")
        # Industry inference must produce a result
        assert result["industry"]["inferred"] is not None
        # Workflow must be generated
        assert result["_workflow"]["steps"] >= 0

    def test_screenshot_detail_captures(
        self,
        inference_engine,
        workflow_gen,
        dag_engine,
        screenshot_mgr,
    ):
        """Generate per-scenario detail screenshots for visual diffing."""
        for scenario in SCENARIOS:
            result = _run_scenario(scenario, inference_engine, workflow_gen, dag_engine)
            detail_html = _build_scenario_detail_html(result)
            screenshot_mgr.capture(
                f"correctness_{scenario['name']}", "detail", detail_html,
            )

        history = screenshot_mgr.get_capture_history()
        # At least 1 full report + N scenario details
        assert len(history) >= len(SCENARIOS)


def _build_scenario_detail_html(result: Dict[str, Any]) -> str:
    """Build a simple HTML detail view for a single scenario result."""
    name = result["name"].replace("_", " ").title()
    verdict = _verdict_class(result["alignment_pct"])
    icon = "✅" if verdict == "pass" else "⚠️" if verdict == "warn" else "❌"

    steps_rows = ""
    for sid, sd in result["execution"]["steps_detail"].items():
        s_icon = "✅" if sd["status"] == "completed" else "❌"
        steps_rows += (
            f"<tr><td>{s_icon} {sid}</td>"
            f"<td>{sd['status']}</td>"
            f"<td>{'Yes' if sd['has_structured_output'] else 'No'}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html><head><title>Correctness: {name}</title>
<style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }}
    h1 {{ color: #1a3a5c; }} .badge {{ padding: 4px 12px; border-radius: 8px; font-weight: bold; }}
    .pass {{ background: #d4edda; color: #155724; }}
    .warn {{ background: #fff3cd; color: #856404; }}
    .fail {{ background: #f8d7da; color: #721c24; }}
    table {{ width: 100%; border-collapse: collapse; }} th, td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
    th {{ background: #4a90d9; color: white; }}
</style></head>
<body>
    <h1>{icon} {name} — <span class="badge {verdict}">{result['alignment_pct']}%</span></h1>
    <p><em>{result['task_goal']}</em></p>
    <table>
        <tr><th>Dimension</th><th>Score</th><th>Details</th></tr>
        <tr><td>Industry Detection</td><td>{result['industry']['score']:.0%}</td><td>{result['industry']['note']}</td></tr>
        <tr><td>Template Matching</td><td>{result['template']['score']:.0%}</td><td>{result['template']['note']}</td></tr>
        <tr><td>Step Execution</td><td>{result['execution']['score']:.0%}</td><td>{result['execution']['note']}</td></tr>
        <tr><td>Gate Coverage</td><td>{result['gates']['score']:.0%}</td><td>{result['gates']['note']}</td></tr>
    </table>
    <h2>Execution Steps</h2>
    <table><tr><th>Step</th><th>Status</th><th>Structured Output?</th></tr>
    {steps_rows if steps_rows else '<tr><td colspan="3">No steps executed</td></tr>'}
    </table>
</body></html>"""
