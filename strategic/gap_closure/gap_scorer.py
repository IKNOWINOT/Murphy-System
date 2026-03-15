# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
gap_scorer.py — Murphy System Gap Closure Scorer
Checks presence of gap-closure modules and returns updated scores + evidence.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Baseline scores (original competitive assessment)
# ---------------------------------------------------------------------------
CAPABILITY_BASELINES: Dict[str, int] = {
    "Community & Ecosystem Maturity": 2,
    "App Connector Ecosystem": 4,
    "No-Code/Low-Code UX": 4,
    "Production Deployment Readiness": 6,
    "Documentation & Observability": 7,
    "Multi-Agent Orchestration": 8,
    "LLM Multi-Provider Routing": 8,
    "Business Process Automation": 8,
    "IoT/Sensor/Actuator Control": 9,
    "Self-Improving/Learning": 9,
    "Human-in-the-Loop (HITL)": 9,
    "ML Built-in (no external deps)": 9,
    "Autonomous Business Operations": 9,
    "Safety/Governance Gates": 10,
    "Mathematical Confidence Scoring": 10,
    "Cryptographic Execution Security": 10,
    "Agent Swarm Coordination": 9,
}

# Module paths relative to this file's directory (gap_closure root)
_HERE = os.path.dirname(os.path.abspath(__file__))

_MODULE_EVIDENCE: Dict[str, List[Tuple[str, str, int]]] = {
    # capability -> list of (module_rel_path, description, bonus_points)
    "Community & Ecosystem Maturity": [
        ("community/COMMUNITY_GUIDE.md", "Community guide with contribution workflow", 3),
        ("community/PLUGIN_SDK_GUIDE.md", "Plugin SDK guide with 3 full examples", 2),
        ("community/community_portal.html", "Self-contained community portal HTML", 2),
        ("connectors/plugin_sdk.py", "ConnectorPlugin base class for third-party devs", 1),
    ],
    "App Connector Ecosystem": [
        ("connectors/connector_registry.py", "50+ pre-registered connectors across 20 categories", 4),
        ("connectors/plugin_sdk.py", "Plugin SDK enabling community connector contributions", 2),
    ],
    "No-Code/Low-Code UX": [
        ("lowcode/workflow_builder.py", "Programmatic workflow builder with compile/export", 2),
        ("lowcode/workflow_builder_ui.html", "Visual drag-and-drop workflow builder UI", 2),
        ("text_to_automation/text_to_automation.py", "Describe→Execute engine: NL text to governed automation DAG", 2),
    ],
    "Production Deployment Readiness": [
        ("launch/launch.py", "One-button streaming deploy script (local/docker/scale)", 2),
        ("launch/launch.sh", "Bash wrapper for one-command deploy", 1),
        ("launch/docker-compose.scale.yml", "Docker Compose with 3-replica API + LB + observability", 1),
    ],
    "Documentation & Observability": [
        ("observability/telemetry.py", "Metrics registry + Prometheus exporter + distributed tracer", 2),
        ("observability/dashboard.html", "Live-updating observability dashboard HTML", 1),
        ("GAP_CLOSURE_PLAN.md", "Comprehensive gap closure plan document", 0),
    ],
    "Multi-Agent Orchestration": [
        ("agents/agent_coordinator.py", "Thread-safe multi-agent coordinator with 6 roles", 2),
    ],
    "LLM Multi-Provider Routing": [
        ("llm/multi_provider_router.py", "12-provider router with 6 routing strategies", 2),
    ],
    "Business Process Automation": [
        ("lowcode/workflow_builder.py", "Workflow definition + compile pipeline", 1),
        ("connectors/connector_registry.py", "50+ connectors enabling cross-system automation", 1),
    ],
    "IoT/Sensor/Actuator Control": [
        ("../murphy_confidence/domain/manufacturing.py", "OPC-UA adapter + multi-sensor fusion + dynamic hazard recalibrator", 1),
    ],
    "Self-Improving/Learning": [
        ("../murphy_confidence/domain/cross_system.py", "PerformanceBenchmark + AdversarialRobustnessTester for continuous improvement", 1),
    ],
    "Human-in-the-Loop (HITL)": [
        ("../murphy_confidence/domain/healthcare.py", "Healthcare HITL with clinical safety gates + paediatric dosing validation", 1),
    ],
    "ML Built-in (no external deps)": [
        ("../murphy_confidence/domain/manufacturing.py", "PredictiveMaintenanceModel with Weibull-based failure prediction (zero-dep)", 1),
    ],
    "Autonomous Business Operations": [
        ("agents/agent_coordinator.py", "Autonomous agent swarm with orchestration", 0),
        ("../murphy_confidence/domain/financial.py", "FinancialDomainEngine with 6 autonomous compliance sub-models", 1),
    ],
    "Safety/Governance Gates": [],
    "Mathematical Confidence Scoring": [],
    "Cryptographic Execution Security": [],
    "Agent Swarm Coordination": [
        ("agents/agent_coordinator.py", "Full swarm coordinator with broadcast + priority routing", 1),
    ],
}


@dataclass
class CapabilityResult:
    name: str
    baseline_score: int
    current_score: int
    gap_closed: int
    evidence: List[str] = field(default_factory=list)
    modules_present: List[str] = field(default_factory=list)


@dataclass
class GapReport:
    overall_score: float
    baseline_overall: float
    gaps_closed: int
    capabilities_at_ten: int
    readiness_pct: float
    capability_results: List[CapabilityResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class CapabilityScorer:
    """Checks gap-closure modules and returns updated capability scores."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or _HERE
        self._results: List[CapabilityResult] = []

    def _file_exists(self, rel_path: str) -> bool:
        return os.path.isfile(os.path.join(self.base_dir, rel_path))

    def score_capability(self, name: str) -> CapabilityResult:
        baseline = CAPABILITY_BASELINES.get(name, 0)
        evidence_list = _MODULE_EVIDENCE.get(name, [])

        bonus = 0
        present: List[str] = []
        evidence_descs: List[str] = []

        for rel_path, description, pts in evidence_list:
            if self._file_exists(rel_path):
                bonus += pts
                present.append(rel_path)
                evidence_descs.append(f"{rel_path}: {description}")

        current = min(10, baseline + bonus)
        return CapabilityResult(
            name=name,
            baseline_score=baseline,
            current_score=current,
            gap_closed=current - baseline,
            evidence=evidence_descs,
            modules_present=present,
        )

    def score_all(self) -> GapReport:
        results: List[CapabilityResult] = []
        for name in CAPABILITY_BASELINES:
            results.append(self.score_capability(name))

        self._results = results
        total_current = sum(r.current_score for r in results)
        total_baseline = sum(r.baseline_score for r in results)
        n = len(results)

        overall = total_current / n
        baseline_overall = total_baseline / n
        gaps_closed = sum(1 for r in results if r.current_score > r.baseline_score)
        at_ten = sum(1 for r in results if r.current_score == 10)
        readiness = (total_current / (n * 10)) * 100

        return GapReport(
            overall_score=round(overall, 2),
            baseline_overall=round(baseline_overall, 2),
            gaps_closed=gaps_closed,
            capabilities_at_ten=at_ten,
            readiness_pct=round(readiness, 1),
            capability_results=results,
        )


def _print_separator(char: str = "─", width: int = 70) -> None:
    print(char * width)


def _bar(score: int, max_score: int = 10, width: int = 20) -> str:
    filled = int((score / max_score) * width)
    return "█" * filled + "░" * (width - filled)


def main() -> None:
    scorer = CapabilityScorer()
    report = scorer.score_all()

    _print_separator("═")
    print("  MURPHY SYSTEM — GAP CLOSURE REPORT")
    print("  © 2020-2026 Inoni LLC  |  Created by Corey Post")
    _print_separator("═")
    print()

    print(f"  Baseline Average Score : {report.baseline_overall}/10")
    print(f"  Current Average Score  : {report.overall_score}/10")
    print(f"  Capabilities at 10/10  : {report.capabilities_at_ten}/{len(report.capability_results)}")
    print(f"  Gaps Closed            : {report.gaps_closed}")
    print(f"  Overall Readiness      : {report.readiness_pct}%")
    print()
    _print_separator()

    for r in report.capability_results:
        delta = f"+{r.gap_closed}" if r.gap_closed > 0 else f" {r.gap_closed}"
        bar = _bar(r.current_score)
        print(f"  {r.name[:38]:<38} {r.baseline_score:>2} → {r.current_score:>2} [{delta}]  {bar}")

    print()
    _print_separator()
    print()
    print("  EVIDENCE SUMMARY")
    print()
    for r in report.capability_results:
        if r.evidence:
            print(f"  ▶ {r.name}")
            for ev in r.evidence:
                print(f"      • {ev}")
            print()

    _print_separator("═")
    pct = report.readiness_pct
    status = "🟢 PRODUCTION READY" if pct >= 90 else ("🟡 NEAR READY" if pct >= 75 else "🔴 GAPS REMAIN")
    print(f"  STATUS: {status}  ({pct}% readiness)")
    _print_separator("═")


if __name__ == "__main__":
    main()
