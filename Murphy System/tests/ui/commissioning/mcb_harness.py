"""
Murphy System — MultiCursor Commissioning Harness
tests/ui/commissioning/mcb_harness.py

Core harness that wraps MultiCursorBrowser with the commissioning protocol:

    STEP 1 — IDENTIFY:   what is being tested, what page/element/flow
    STEP 2 — SPECIFY:    exactly how it should operate and respond
    STEP 3 — PROBE:      how it actually operates (run against live page)
    STEP 4 — GAP:        record every discrepancy (error, missing element, broken link)
    STEP 5 — FIX:        apply targeted fix to source HTML or JS
    STEP 6 — VERIFY:     re-run probe, confirm gap is closed
    STEP 7 — CHAIN:      sequence probes into complete end-to-end flows
    STEP 8 — ROSETTA:    map the same flow from multiple agent viewpoints

All screenshots are saved to tests/ui/screenshots/ and committed to the repo.
Gap registry is serialised to tests/ui/commissioning/gap_registry.json.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── Paths ─────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).parent.parent.parent.parent
SCREENSHOTS = Path(__file__).parent.parent / "screenshots"
GAP_FILE    = Path(__file__).parent / "gap_registry.json"
BASE_URL    = "http://localhost:18080"

# Ensure src/ on path so we can import MultiCursorBrowser
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_module_loader import (          # noqa: E402
    MultiCursorBrowser,
    MultiCursorTaskStatus,
)


# ══════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class CommissionSpec:
    """What a UI element / flow SHOULD do."""
    id: str                                     # e.g. "ONBOARD-001"
    page: str                                   # e.g. "onboarding_wizard"
    element: str                                # CSS selector or description
    expected_behaviour: str                     # human-readable specification
    rosetta_viewpoints: List[str] = field(default_factory=list)
    # e.g. ["founder", "compliance_officer", "customer", "investor"]


@dataclass
class ProbeResult:
    """What actually happened when we ran the probe."""
    spec_id: str
    passed: bool
    actual: str
    screenshot: Optional[str] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Gap:
    """A discrepancy between spec and actual."""
    gap_id: str
    spec_id: str
    description: str
    severity: str                               # critical | high | medium | low
    fix_applied: str = ""
    verified: bool = False
    fixed_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════
# Gap registry (persisted JSON)
# ══════════════════════════════════════════════════════════════════════════

class GapRegistry:
    def __init__(self, path: Path = GAP_FILE):
        self.path = path
        self._gaps: Dict[str, Gap] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for g in data.get("gaps", []):
                self._gaps[g["gap_id"]] = Gap(**g)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "generated": datetime.now(timezone.utc).isoformat(),
            "total": len(self._gaps),
            "open": sum(1 for g in self._gaps.values() if not g.verified),
            "closed": sum(1 for g in self._gaps.values() if g.verified),
            "gaps": [g.__dict__ for g in self._gaps.values()],
        }, indent=2))

    def record(self, gap: Gap):
        self._gaps[gap.gap_id] = gap
        self.save()

    def close(self, gap_id: str, fix_description: str):
        if gap_id in self._gaps:
            g = self._gaps[gap_id]
            g.fix_applied = fix_description
            g.verified = True
            g.fixed_at = datetime.now(timezone.utc).isoformat()
            self.save()

    def open_gaps(self) -> List[Gap]:
        return [g for g in self._gaps.values() if not g.verified]

    def all_gaps(self) -> List[Gap]:
        return list(self._gaps.values())


GAPS = GapRegistry()


# ══════════════════════════════════════════════════════════════════════════
# Screenshot helper
# ══════════════════════════════════════════════════════════════════════════

def _screenshot_path(subdir: str, name: str) -> str:
    d = SCREENSHOTS / subdir
    d.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w]", "_", name)[:80]
    return str(d / f"{safe}.png")


# ══════════════════════════════════════════════════════════════════════════
# MCB Commissioning Harness
# ══════════════════════════════════════════════════════════════════════════

class MCBCommissionHarness:
    """
    Wraps MultiCursorBrowser to implement the 8-step commissioning protocol.

    Usage (async):
        async with MCBCommissionHarness() as h:
            result = await h.probe(spec, screenshot_dir="onboarding")
            if not result.passed:
                h.record_gap(gap_id, spec, result, severity="high")
                # apply fix to source file...
                result2 = await h.re_probe(spec, screenshot_dir="onboarding")
                h.close_gap(gap_id, "Fixed by ...")

    Usage (sync — wraps event loop automatically):
        h = MCBCommissionHarness()
        result = h.run(spec, screenshot_dir="onboarding")
    """

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self._mcb: Optional[MultiCursorBrowser] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── async context manager ──────────────────────────────────────────
    async def __aenter__(self):
        self._mcb = MultiCursorBrowser()
        await self._mcb.launch(headless=True, args=["--no-sandbox"])
        return self

    async def __aexit__(self, *_):
        if self._mcb:
            await self._mcb.close()

    # ── sync entry point for pytest ────────────────────────────────────
    def run_probe(
        self,
        spec: CommissionSpec,
        screenshot_dir: str = "all_pages",
        extra_actions: Optional[List[Callable]] = None,
    ) -> ProbeResult:
        """Synchronous wrapper — runs the async probe in a managed event loop."""
        return asyncio.run(self._async_probe(spec, screenshot_dir, extra_actions))

    def run_flow(self, coros) -> List[ProbeResult]:
        """Run a sequence of probe coroutines as a chain."""
        return asyncio.run(self._async_flow(coros))

    def run_parallel(self, coros) -> List[ProbeResult]:
        """Run probe coroutines in parallel (multi-cursor)."""
        return asyncio.run(self._async_parallel(coros))

    # ── core async probe ───────────────────────────────────────────────
    async def _async_probe(
        self,
        spec: CommissionSpec,
        screenshot_dir: str,
        extra_actions: Optional[List[Callable]] = None,
    ) -> ProbeResult:
        t0 = time.monotonic()
        async with self as h:
            mcb = h._mcb
            url = f"{self.base_url}/{spec.page}.html"
            shot_path = _screenshot_path(screenshot_dir, f"{spec.id}_probe")

            # Navigate to page
            nav = await mcb.navigate("main", url)
            if nav.status != MultiCursorTaskStatus.COMPLETED:
                return ProbeResult(
                    spec_id=spec.id,
                    passed=False,
                    actual=f"Navigation failed: {nav.error}",
                    screenshot=None,
                    duration_ms=(time.monotonic() - t0) * 1000,
                    error=nav.error,
                )

            # Wait for DOM
            await mcb._execute(
                mcb._action_types().WAIT_FOR_LOAD_STATE
                if hasattr(mcb, "_action_types") else
                __import__("agent_module_loader").MultiCursorActionType.WAIT_FOR_LOAD_STATE,
                "main",
                parameters={"state": "domcontentloaded"},
                timeout_ms=10000,
            )

            # Screenshot before extra actions
            await mcb.screenshot("main", path=shot_path)

            # Run any extra actions
            passed = True
            actual = "OK"
            error = None
            if extra_actions:
                for act in extra_actions:
                    try:
                        result = await act(mcb)
                        if result and hasattr(result, "status"):
                            if result.status == MultiCursorTaskStatus.FAILED:
                                passed = False
                                actual = f"Action failed: {result.error}"
                                error = result.error
                    except Exception as e:
                        passed = False
                        actual = str(e)
                        error = str(e)

            # Check element visibility
            if spec.element and spec.element.startswith(("#", ".", "[")):
                vis = await mcb.is_visible("main", spec.element)
                if vis.data.get("visible") is False:
                    passed = False
                    actual = f"Element '{spec.element}' not visible"
                    error = actual

            # Screenshot after actions
            shot_after = _screenshot_path(screenshot_dir, f"{spec.id}_after")
            await mcb.screenshot("main", path=shot_after)

            return ProbeResult(
                spec_id=spec.id,
                passed=passed,
                actual=actual if not passed else "All checks passed",
                screenshot=shot_after,
                duration_ms=(time.monotonic() - t0) * 1000,
                error=error,
            )

    async def _async_flow(self, coros) -> List[ProbeResult]:
        results = []
        for coro in coros:
            r = await coro
            results.append(r)
        return results

    async def _async_parallel(self, coros) -> List[ProbeResult]:
        results = await asyncio.gather(*coros, return_exceptions=True)
        out = []
        for r in results:
            if isinstance(r, Exception):
                out.append(ProbeResult(
                    spec_id="parallel",
                    passed=False,
                    actual=str(r),
                    error=str(r),
                ))
            else:
                out.append(r)
        return out

    # ── Gap management ─────────────────────────────────────────────────
    @staticmethod
    def record_gap(
        gap_id: str,
        spec: CommissionSpec,
        result: ProbeResult,
        severity: str = "medium",
    ) -> Gap:
        gap = Gap(
            gap_id=gap_id,
            spec_id=spec.id,
            description=result.actual or result.error or "Unknown gap",
            severity=severity,
        )
        GAPS.record(gap)
        return gap

    @staticmethod
    def close_gap(gap_id: str, fix_description: str):
        GAPS.close(gap_id, fix_description)

    @staticmethod
    def open_gaps() -> List[Gap]:
        return GAPS.open_gaps()

    @staticmethod
    def all_gaps() -> List[Gap]:
        return GAPS.all_gaps()


# ══════════════════════════════════════════════════════════════════════════
# Lightweight sync probe (no browser — HTML source analysis)
# Used when the browser cannot load the page (API requires auth).
# ══════════════════════════════════════════════════════════════════════════

def probe_html_source(
    page_file: str,
    spec_id: str,
    checks: Dict[str, str],  # {check_name: expected_string_in_source}
    screenshot_dir: str = "all_pages",
) -> ProbeResult:
    """
    Probe the HTML source of a page without a running server.

    Args:
        page_file:      path to the .html file relative to REPO_ROOT
        spec_id:        commissioning spec ID
        checks:         dict of check_name → string that must appear in source
        screenshot_dir: screenshot subdir label

    Returns:
        ProbeResult with passed=True only if all checks pass.
    """
    html_path = REPO_ROOT / page_file
    if not html_path.exists():
        return ProbeResult(
            spec_id=spec_id,
            passed=False,
            actual=f"File not found: {page_file}",
            error="FILE_NOT_FOUND",
        )

    source = html_path.read_text(encoding="utf-8", errors="replace")
    failures = []
    for name, needle in checks.items():
        if needle not in source:
            failures.append(f"{name}: '{needle}' not found in source")

    passed = len(failures) == 0
    actual = "All source checks passed" if passed else "; ".join(failures)
    return ProbeResult(
        spec_id=spec_id,
        passed=passed,
        actual=actual,
        error=None if passed else actual,
    )


# ══════════════════════════════════════════════════════════════════════════
# Rosetta Viewpoint Mapper
# ══════════════════════════════════════════════════════════════════════════

ROSETTA_VIEWPOINTS = {
    "founder": {
        "priority": "revenue, growth, investor narrative",
        "questions": [
            "Does this flow generate revenue?",
            "Is the value proposition clear?",
            "Does it reduce cost or increase output?",
        ],
    },
    "compliance_officer": {
        "priority": "regulatory adherence, audit trail, data protection",
        "questions": [
            "Is every action logged?",
            "Are compliance gates enforced before high-risk steps?",
            "Is HITL required for irreversible actions?",
        ],
    },
    "customer": {
        "priority": "ease of use, speed to value, clarity",
        "questions": [
            "Can I complete this in under 5 minutes?",
            "Is the next step always obvious?",
            "Are errors explained in plain language?",
        ],
    },
    "investor": {
        "priority": "scalability, defensibility, unit economics",
        "questions": [
            "Does automation reduce marginal cost?",
            "Is the data moat growing?",
            "Are the metrics visible and real?",
        ],
    },
    "operator": {
        "priority": "reliability, uptime, observability",
        "questions": [
            "Can I see what's running right now?",
            "Are failures surfaced immediately?",
            "Can I roll back any action?",
        ],
    },
}


def rosetta_map(
    flow_name: str,
    steps: List[str],
    viewpoints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Map a flow from multiple Rosetta agent viewpoints and return
    gated suggestions for each viewpoint.

    Args:
        flow_name:  e.g. "onboarding_to_production"
        steps:      ordered list of step descriptions
        viewpoints: which viewpoints to apply (default: all 5)

    Returns:
        dict with viewpoint → {observations, suggestions, gate_recommendations}
    """
    vps = viewpoints or list(ROSETTA_VIEWPOINTS.keys())
    mapping: Dict[str, Any] = {"flow": flow_name, "steps": steps, "viewpoints": {}}

    for vp in vps:
        vp_def = ROSETTA_VIEWPOINTS.get(vp, {})
        mapping["viewpoints"][vp] = {
            "priority": vp_def.get("priority", ""),
            "questions": vp_def.get("questions", []),
            "observations": [
                f"Step '{s}' reviewed from {vp} perspective" for s in steps
            ],
            "suggestions": _generate_suggestions(vp, steps),
            "gate_recommendations": _gate_recommendations(vp, steps),
        }

    return mapping


def _generate_suggestions(viewpoint: str, steps: List[str]) -> List[str]:
    suggestions = {
        "founder": [
            "Add inline ROI calculator showing cost saved per automated step",
            "Surface 'time saved this week' metric on dashboard after each flow",
            "Add upsell prompt when user hits plan limit mid-flow",
        ],
        "compliance_officer": [
            "Require HITL gate before any step that modifies org data",
            "Auto-seal audit block at end of each wizard completion",
            "Add regulatory framework auto-detection on onboarding step 2",
        ],
        "customer": [
            "Show progress percentage at top of each wizard step",
            "Pre-fill known data from previous wizard steps",
            "Add 'Skip for now' option on optional integration steps",
        ],
        "investor": [
            "Track and expose completion rate per wizard step (funnel analytics)",
            "Show aggregate automation value ($ saved) across all accounts",
            "Add cohort retention metric tied to onboarding completion",
        ],
        "operator": [
            "Expose /api/health check status inline on each wizard page",
            "Add rollback button for every wizard step that calls an API",
            "Log every wizard step transition to the BAT audit trail",
        ],
    }
    return suggestions.get(viewpoint, [])


def _gate_recommendations(viewpoint: str, steps: List[str]) -> List[Dict]:
    """Return HITL gate recommendations per viewpoint."""
    gates = {
        "founder": [
            {"after_step": "production_config_save", "gate": "financial_review",
             "reason": "Production config may commit spend"},
        ],
        "compliance_officer": [
            {"after_step": "onboarding_complete", "gate": "compliance_profile_lock",
             "reason": "Lock compliance profile before production use"},
            {"after_step": "grant_submission", "gate": "legal_review",
             "reason": "Grant applications are legal documents"},
        ],
        "customer": [],
        "investor": [
            {"after_step": "pricing_upgrade", "gate": "revenue_recognition",
             "reason": "Ensure billing event is recorded"},
        ],
        "operator": [
            {"after_step": "integration_connected", "gate": "connectivity_test",
             "reason": "Verify integration before marking active"},
        ],
    }
    return gates.get(viewpoint, [])
