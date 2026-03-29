"""
Murphy System — MCB Commission Harness
tests/commissioning/mcb_harness.py

Provides shared infrastructure for the commissioning test suite:
  - ProbeResult    — outcome of a single HTML source probe
  - CommissionSpec — specification for one page/element combination
  - Gap / GapRegistry — lightweight gap tracking (persisted to JSON)
  - MCBCommissionHarness — static methods to record and close gaps
  - probe_html_source() — probe an HTML file for expected elements
  - rosetta_map()  — generate a 5-viewpoint Rosetta mapping

Design label: COMM-HARNESS — Commissioning Test Harness
Owner: @test-lead
Copyright (c) 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS: Path = REPO_ROOT / "tests" / "ui" / "screenshots"
GAP_FILE: Path = REPO_ROOT / "tests" / "commissioning" / "gap_registry.json"

# Ensure directories exist at import time so tests don't fail on mkdir
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Outcome of a single HTML-source probe."""
    spec_id: str
    passed: bool
    actual: str = ""
    error: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "passed": self.passed,
            "actual": self.actual,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class CommissionSpec:
    """Specification for one page/element combination to commission."""
    id: str
    page: str
    element: str
    expected_behaviour: str
    rosetta_viewpoints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "page": self.page,
            "element": self.element,
            "expected_behaviour": self.expected_behaviour,
            "rosetta_viewpoints": self.rosetta_viewpoints,
        }


@dataclass
class Gap:
    """A single identified gap from commissioning."""
    gap_id: str
    spec_id: str
    severity: str  # low / medium / high / critical
    description: str
    status: str = "open"  # open / closed
    resolution: str = ""
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    closed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "spec_id": self.spec_id,
            "severity": self.severity,
            "description": self.description,
            "status": self.status,
            "resolution": self.resolution,
            "detected_at": self.detected_at,
            "closed_at": self.closed_at,
        }


class GapRegistry:
    """Thread-safe in-memory gap registry with JSON persistence."""

    def __init__(self, path: Path = GAP_FILE) -> None:
        self._path = path
        self._gaps: List[Gap] = []
        self._load()

    # -- persistence --

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                for entry in data.get("gaps", []):
                    self._gaps.append(Gap(**{
                        k: v for k, v in entry.items()
                        if k in Gap.__dataclass_fields__
                    }))
            except (json.JSONDecodeError, TypeError):
                self._gaps = []

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(
            {"gaps": [g.to_dict() for g in self._gaps]},
            indent=2,
        ))

    # -- CRUD --

    def all_gaps(self) -> List[Gap]:
        return list(self._gaps)

    def add(self, gap: Gap) -> None:
        # Deduplicate by gap_id
        if not any(g.gap_id == gap.gap_id for g in self._gaps):
            self._gaps.append(gap)
            self.save()

    def close(self, gap_id: str, resolution: str) -> None:
        for g in self._gaps:
            if g.gap_id == gap_id:
                g.status = "closed"
                g.resolution = resolution
                g.closed_at = datetime.now(timezone.utc).isoformat()
        self.save()

    def open_gaps(self) -> List[Gap]:
        return [g for g in self._gaps if g.status == "open"]

    def closed_gaps(self) -> List[Gap]:
        return [g for g in self._gaps if g.status == "closed"]


# Module-level singleton
GAPS = GapRegistry()


# ---------------------------------------------------------------------------
# MCBCommissionHarness — static helpers
# ---------------------------------------------------------------------------

class MCBCommissionHarness:
    """Static methods for commissioning gap management."""

    @staticmethod
    def record_gap(
        gap_id: str,
        spec: CommissionSpec,
        result: ProbeResult,
        severity: str = "medium",
    ) -> Gap:
        """Record a new gap from a failed probe."""
        gap = Gap(
            gap_id=gap_id,
            spec_id=spec.id,
            severity=severity,
            description=(
                f"Probe {result.spec_id} failed: {result.error or result.actual}"
            ),
        )
        GAPS.add(gap)
        return gap

    @staticmethod
    def close_gap(gap_id: str, resolution: str) -> None:
        """Mark a gap as closed with resolution text."""
        GAPS.close(gap_id, resolution)


# ---------------------------------------------------------------------------
# probe_html_source — probe an HTML file for expected elements
# ---------------------------------------------------------------------------

def probe_html_source(
    page_file: str,
    spec_id: str,
    checks: Dict[str, str],
    screenshot_dir: str = "all_pages",
) -> ProbeResult:
    """Probe an HTML source file for expected content.

    Args:
        page_file: Filename relative to REPO_ROOT (e.g. "login.html")
        spec_id: Spec ID for tracking (e.g. "AUTH-001")
        checks: Dict of check_name → substring that must appear in HTML
        screenshot_dir: Subdirectory under SCREENSHOTS for artifacts

    Returns:
        ProbeResult with passed=True if ALL checks found, else details.
    """
    html_path = REPO_ROOT / page_file
    if not html_path.exists():
        # Also check templates/ subdirectory
        html_path = REPO_ROOT / "templates" / page_file
    if not html_path.exists():
        return ProbeResult(
            spec_id=spec_id,
            passed=False,
            error=f"File not found: {page_file}",
        )

    source = html_path.read_text(errors="replace")
    missing: List[str] = []
    for check_name, expected in checks.items():
        if expected not in source:
            missing.append(f"{check_name}: '{expected}' not found")

    # Create screenshot dir for traceability
    sdir = SCREENSHOTS / screenshot_dir
    sdir.mkdir(parents=True, exist_ok=True)

    if missing:
        return ProbeResult(
            spec_id=spec_id,
            passed=False,
            actual="; ".join(missing),
            error=f"{len(missing)} check(s) failed",
        )
    return ProbeResult(spec_id=spec_id, passed=True, actual="all checks passed")


# ---------------------------------------------------------------------------
# rosetta_map — generate 5-viewpoint Rosetta mapping
# ---------------------------------------------------------------------------

_VIEWPOINTS = ["founder", "compliance_officer", "customer", "investor", "operator"]

_GATE_MAP: Dict[str, List[Dict[str, str]]] = {
    "founder": [
        {"gate": "financial_review", "trigger": "production_config_save"},
        {"gate": "budget_approval", "trigger": "tier_selection"},
        {"gate": "strategic_alignment", "trigger": "partner_request"},
    ],
    "compliance_officer": [
        {"gate": "compliance_profile_lock", "trigger": "onboarding_complete"},
        {"gate": "legal_review", "trigger": "grant_submission"},
        {"gate": "regulatory_scan", "trigger": "compliance_dashboard_view"},
    ],
    "customer": [
        {"gate": "feature_gate", "trigger": "production_config_save"},
        {"gate": "ux_review", "trigger": "onboarding_complete"},
    ],
    "investor": [
        {"gate": "roi_gate", "trigger": "tier_selection"},
        {"gate": "market_fit_review", "trigger": "grant_submission"},
    ],
    "operator": [
        {"gate": "connectivity_test", "trigger": "integration_connected"},
        {"gate": "health_check", "trigger": "production_config_save"},
        {"gate": "capacity_review", "trigger": "onboarding_complete"},
    ],
}

_SUGGESTION_MAP: Dict[str, List[str]] = {
    "founder": [
        "Review cost-to-acquire before production launch",
        "Verify grant runway covers 12-month plan",
        "Confirm compliance posture before investor deck",
        "Check partner revenue-share terms",
    ],
    "compliance_officer": [
        "Lock regulatory profile after onboarding",
        "Scan all integrations for data-residency compliance",
        "Validate grant eligibility criteria before submission",
        "Audit pricing tier for regulatory implications",
    ],
    "customer": [
        "Confirm onboarding steps match promised experience",
        "Verify production deliverables timeline",
        "Check grant benefits clearly communicated",
    ],
    "investor": [
        "Validate unit economics at each pricing tier",
        "Review grant portfolio for diversification",
        "Confirm compliance reduces regulatory risk",
        "Assess partner network for strategic value",
    ],
    "operator": [
        "Verify integration connectivity after setup",
        "Confirm production pipeline health checks exist",
        "Validate onboarding creates all required accounts",
        "Check compliance dashboards update in real-time",
    ],
}


def rosetta_map(flow_name: str, steps: List[str]) -> Dict[str, Any]:
    """Generate a 5-viewpoint Rosetta mapping for a commissioning flow.

    Returns a dict with:
      - flow: name of the flow
      - steps: the input steps
      - viewpoints: {vp_name: {suggestions, gate_recommendations}}
    """
    viewpoints: Dict[str, Any] = {}
    for vp in _VIEWPOINTS:
        suggestions = _SUGGESTION_MAP.get(vp, [])
        gates = _GATE_MAP.get(vp, [])
        # Filter gates that are relevant to any of the steps
        relevant_gates = []
        for gate in gates:
            trigger = gate["trigger"]
            for step in steps:
                if trigger in step.lower().replace(" ", "_"):
                    relevant_gates.append(gate)
                    break
            else:
                # Always include gates for broad flows
                if len(steps) > 3:
                    relevant_gates.append(gate)

        viewpoints[vp] = {
            "suggestions": suggestions,
            "gate_recommendations": relevant_gates,
        }

    return {
        "flow": flow_name,
        "steps": steps,
        "viewpoints": viewpoints,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
