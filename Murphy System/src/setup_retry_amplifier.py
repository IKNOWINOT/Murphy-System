"""
Setup Retry Amplifier — MMSMMS cadence for environment setup retries.

Applies Murphy's Magnify→Magnify→Simplify→Magnify→Magnify→Solidify pattern
to setup failures every 3rd retry, transforming blind retries into intelligent
root-cause analysis and targeted remediation.

Cadence: M → M → S → M → M → Solidify

Design Label: NBG-SRA-001
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import platform
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — cadence sequence and confidence thresholds (aligned with MFGC)
# ---------------------------------------------------------------------------

#: MMSMMS — the six-phase cadence applied every 3rd setup retry
SETUP_AMPLIFIER_SEQUENCE: str = "MMSMMS"

#: Confidence gate thresholds matching mfgc_core.py conventions
CONFIDENCE_EXPAND: float = 0.3     # minimum to proceed past initial expansion
CONFIDENCE_CONSTRAIN: float = 0.65  # minimum to produce a simplified root cause
CONFIDENCE_EXECUTE: float = 0.85    # minimum to emit a solidified SetupPlan

_MAX_AUDIT_LOG = 1_000


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------


class SetupAmplificationPhase(str, Enum):
    """Phases of the magnify/simplify amplification cycle for setup retry."""
    MAGNIFY_EXPAND = "magnify_expand"       # Phase 1: expand context, gather OS state
    MAGNIFY_DEEPEN = "magnify_deepen"       # Phase 2: deepen to prerequisites / OS quirks
    SIMPLIFY_DISTILL = "simplify_distill"   # Phase 3: distil to single root cause
    MAGNIFY_SOLUTIONS = "magnify_solutions" # Phase 4: expand solution space given root cause
    MAGNIFY_RANK = "magnify_rank"           # Phase 5: rank solutions by reliability
    SOLIDIFY_LOCK = "solidify_lock"         # Phase 6: lock concrete remediation plan


@dataclass
class SetupAmplificationResult:
    """Result of one phase of the MMSMMS cadence.

    ``output_context`` is what the *next* phase receives as input.
    """

    phase: SetupAmplificationPhase
    input_context: Dict[str, Any]
    output_context: Dict[str, Any]
    confidence: float = 0.0
    completed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "confidence": self.confidence,
            "output_keys": list(self.output_context.keys()),
            "completed_at": self.completed_at,
        }


# ---------------------------------------------------------------------------
# SetupRetryAmplifier
# ---------------------------------------------------------------------------


class SetupRetryAmplifier:
    """Applies MMSMMS→Solidify thinking to setup failures.

    Every 3rd retry, instead of blindly re-probing and re-planning, this
    amplifier runs the failure context through:

      M → M → S → M → M → Solidify

    Each phase transforms the failure context progressively:
    - **Magnify 1** (MAGNIFY_EXPAND):   gather full error context, OS state,
      cascade effects
    - **Magnify 2** (MAGNIFY_DEEPEN):   cross-reference — which deps failed
      because of which? PORT conflicts? PATH issues?
    - **Simplify**  (SIMPLIFY_DISTILL): distil to a single root cause
    - **Magnify 4** (MAGNIFY_SOLUTIONS):expand solution space given root cause
    - **Magnify 5** (MAGNIFY_RANK):     rank solutions by OS fit, invasiveness,
      speed
    - **Solidify**  (SOLIDIFY_LOCK):    emit a concrete ``SetupPlan``

    The amplifier operates entirely without an LLM — all reasoning is
    structural (pattern-matching on issue codes, OS info, and env state).
    Every phase is logged to the audit trail.

    Args:
        audit_log: Optional shared audit log list.  A private log is used
            when *None*.
    """

    # Liability note pattern matching HITLApprovalGate
    _LIABILITY_NOTE = (
        "Murphy amplified this step through the MMSMMS cadence. "
        "You approved this action. Murphy executed it as instructed."
    )

    def __init__(
        self,
        audit_log: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._audit_log: List[Dict[str, Any]] = (
            audit_log if audit_log is not None else []
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def amplify_failure(
        self,
        report: Any,  # EnvironmentReport — imported lazily to avoid circular
        issues: List[str],
        attempt: int,
        previous_plans: Optional[List[Any]] = None,
    ) -> Optional[Any]:  # SetupPlan or None
        """Run the MMSMMS cadence on the current failure context.

        Returns a :class:`SetupPlan` whose steps target the identified root
        cause, or *None* if confidence thresholds are not met.

        Args:
            report:         The latest ``EnvironmentReport`` from the probe.
            issues:         List of issue strings from ``_collect_issues``.
            attempt:        The current retry attempt number.
            previous_plans: All plans tried so far (used to avoid repeating
                            exactly the same steps).
        """
        # Lazy import to avoid circular dependency with environment_setup_agent
        from environment_setup_agent import RiskLevel, SetupPlan, SetupStep, StepStatus

        context: Dict[str, Any] = {
            "issues": issues,
            "attempt": attempt,
            "report": report.to_dict() if hasattr(report, "to_dict") else {},
            "previous_plan_count": len(previous_plans or []),
            "amplification_sequence": SETUP_AMPLIFIER_SEQUENCE,
        }

        phase_results: List[SetupAmplificationResult] = []

        # ---- Phase 1: MAGNIFY_EXPAND ----------------------------------------
        r1 = self._magnify_expand(context)
        phase_results.append(r1)
        self._log_phase(r1, attempt)
        if r1.confidence < CONFIDENCE_EXPAND:
            logger.warning(
                "SRA: MAGNIFY_EXPAND confidence %.2f below threshold %.2f — aborting cadence",
                r1.confidence, CONFIDENCE_EXPAND,
            )
            return None
        context = r1.output_context

        # ---- Phase 2: MAGNIFY_DEEPEN ----------------------------------------
        r2 = self._magnify_deepen(context)
        phase_results.append(r2)
        self._log_phase(r2, attempt)
        context = r2.output_context

        # ---- Phase 3: SIMPLIFY_DISTILL --------------------------------------
        r3 = self._simplify_distill(context)
        phase_results.append(r3)
        self._log_phase(r3, attempt)
        if r3.confidence < CONFIDENCE_CONSTRAIN:
            logger.warning(
                "SRA: SIMPLIFY_DISTILL confidence %.2f below threshold %.2f — aborting cadence",
                r3.confidence, CONFIDENCE_CONSTRAIN,
            )
            return None
        context = r3.output_context

        # ---- Phase 4: MAGNIFY_SOLUTIONS -------------------------------------
        r4 = self._magnify_solutions(context)
        phase_results.append(r4)
        self._log_phase(r4, attempt)
        context = r4.output_context

        # ---- Phase 5: MAGNIFY_RANK ------------------------------------------
        r5 = self._magnify_rank(context)
        phase_results.append(r5)
        self._log_phase(r5, attempt)
        context = r5.output_context

        # ---- Phase 6: SOLIDIFY_LOCK -----------------------------------------
        r6 = self._solidify_lock(context)
        phase_results.append(r6)
        self._log_phase(r6, attempt)
        if r6.confidence < CONFIDENCE_EXECUTE:
            logger.warning(
                "SRA: SOLIDIFY_LOCK confidence %.2f below threshold %.2f — aborting cadence",
                r6.confidence, CONFIDENCE_EXECUTE,
            )
            return None

        # Build the SetupPlan from the solidified steps
        raw_steps: List[Dict[str, Any]] = r6.output_context.get("steps", [])
        if not raw_steps:
            return None

        plan_steps: List[SetupStep] = []
        for i, spec in enumerate(raw_steps):
            step = SetupStep(
                step_id=f"sra_{attempt}_{i:02d}",
                description=spec.get("description", "Amplified remediation step"),
                risk_level=RiskLevel(spec.get("risk_level", "medium")),
                command=spec.get("command"),
                file_op=spec.get("file_op"),
                status=StepStatus.PENDING,
                liability_note=self._LIABILITY_NOTE,
            )
            plan_steps.append(step)

        plan = SetupPlan(steps=plan_steps)
        self._log("mmsmms_plan_generated", {
            "attempt": attempt,
            "plan_id": plan.plan_id,
            "steps": len(plan_steps),
            "root_cause": context.get("root_cause", "unknown"),
            "phases_completed": len(phase_results),
        })
        return plan

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _magnify_expand(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 1: Expand the full failure context."""
        issues: List[str] = ctx.get("issues", [])
        report_dict: Dict[str, Any] = ctx.get("report", {})

        expanded: Dict[str, Any] = {
            "issues": issues,
            "issue_count": len(issues),
            "os_name": report_dict.get("os_name", platform.system().lower()),
            "python_version": report_dict.get("python_version", sys.version),
            "disk_free_mb": report_dict.get("disk_free_mb", 0),
            "ram_mb": report_dict.get("ram_mb", 0),
            "ports_available": report_dict.get("ports_available", {}),
            "venv_exists": report_dict.get("venv_exists", False),
            "pip_available": report_dict.get("pip_available", False),
            "env_vars_missing": report_dict.get("env_vars_missing", []),
            "attempt": ctx.get("attempt", 0),
            "previous_plan_count": ctx.get("previous_plan_count", 0),
            # Cascade: which issues imply other issues
            "cascade_map": self._build_cascade_map(issues),
        }

        confidence = min(1.0, 0.4 + 0.1 * len(issues)) if issues else 0.2
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.MAGNIFY_EXPAND,
            input_context=ctx,
            output_context=expanded,
            confidence=round(confidence, 3),
        )

    def _magnify_deepen(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 2: Deepen — find prerequisites and OS-specific quirks."""
        os_name: str = ctx.get("os_name", "")
        issues: List[str] = ctx.get("issues", [])
        cascade_map: Dict[str, List[str]] = ctx.get("cascade_map", {})

        blockers: List[str] = []
        os_quirks: List[str] = []

        # Identify prerequisite blockers
        if any("python_version_too_old" in i for i in issues):
            blockers.append("python_upgrade_required")
        if any("pip_not_available" in i for i in issues):
            blockers.append("pip_install_required")
        if any("insufficient_disk" in i for i in issues):
            blockers.append("disk_space_insufficient")

        # OS-specific quirks
        if "windows" in os_name or "win" in os_name:
            os_quirks.append("windows_path_separator")
            os_quirks.append("venv_scripts_not_bin")
            if any("pip" in i for i in issues):
                os_quirks.append("mingw64_stderr_as_error")
        elif "darwin" in os_name:
            os_quirks.append("homebrew_python_path")
        elif "linux" in os_name:
            os_quirks.append("system_python_conflict")

        # Port conflict cross-reference
        blocked_ports = [
            i.split(":")[1] for i in issues if i.startswith("port_in_use:")
        ]

        deepened = {
            **ctx,
            "blockers": blockers,
            "os_quirks": os_quirks,
            "blocked_ports": blocked_ports,
            "has_port_conflicts": len(blocked_ports) > 0,
            "cascade_depth": sum(len(v) for v in cascade_map.values()),
        }

        confidence = round(min(1.0, 0.55 + 0.05 * len(blockers)), 3)
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.MAGNIFY_DEEPEN,
            input_context=ctx,
            output_context=deepened,
            confidence=confidence,
        )

    def _simplify_distill(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 3: Distil to the single blocking root cause."""
        blockers: List[str] = ctx.get("blockers", [])
        issues: List[str] = ctx.get("issues", [])
        blocked_ports: List[str] = ctx.get("blocked_ports", [])

        # Priority: python > pip > disk > ports > playwright > other
        if "python_upgrade_required" in blockers:
            root_cause = "python_version_too_old"
            fix_class = "python_upgrade"
        elif "pip_install_required" in blockers:
            root_cause = "pip_not_available"
            fix_class = "pip_bootstrap"
        elif "disk_space_insufficient" in blockers:
            root_cause = "insufficient_disk"
            fix_class = "disk_cleanup"
        elif blocked_ports:
            root_cause = f"port_conflict:{blocked_ports[0]}"
            fix_class = "port_resolution"
        elif any("playwright_not_installed" in i for i in issues):
            root_cause = "playwright_not_installed"
            fix_class = "playwright_install"
        elif issues:
            root_cause = issues[0]
            fix_class = "generic_setup"
        else:
            root_cause = "unknown"
            fix_class = "generic_setup"

        distilled = {
            **ctx,
            "root_cause": root_cause,
            "fix_class": fix_class,
            "remaining_issues_after_fix": [
                i for i in issues if root_cause not in i
            ],
        }

        # Confidence proportional to how clearly we identified the root cause
        confidence = 0.85 if fix_class != "generic_setup" else 0.67
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.SIMPLIFY_DISTILL,
            input_context=ctx,
            output_context=distilled,
            confidence=round(confidence, 3),
        )

    def _magnify_solutions(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 4: Expand the full solution space given the root cause."""
        root_cause: str = ctx.get("root_cause", "unknown")
        fix_class: str = ctx.get("fix_class", "generic_setup")
        os_name: str = ctx.get("os_name", "")
        blocked_ports: List[str] = ctx.get("blocked_ports", [])

        solutions: List[Dict[str, Any]] = []

        if fix_class == "pip_bootstrap":
            solutions.append({
                "id": "pip_ensurepip",
                "description": "Bootstrap pip with ensurepip",
                "command": f"{sys.executable} -m ensurepip --default-pip",
                "risk": "low",
                "invasiveness": "low",
                "speed": "fast",
            })
            solutions.append({
                "id": "pip_getpip",
                "description": "Download and run get-pip.py",
                "command": (
                    "curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py "
                    f"&& {sys.executable} /tmp/get-pip.py"
                ),
                "risk": "medium",
                "invasiveness": "medium",
                "speed": "medium",
            })

        elif fix_class == "port_resolution":
            for port in blocked_ports:
                solutions.append({
                    "id": f"kill_port_{port}",
                    "description": f"Kill process on port {port}",
                    "command": (
                        f"lsof -ti:{port} | xargs kill -15 2>/dev/null; "
                        f"sleep 2; lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
                        if "windows" not in os_name
                        else (
                            f"for /f \"tokens=5\" %p in "
                            f"('netstat -aon ^| findstr :{port}') "
                            f"do taskkill /F /PID %p"
                        )
                    ),
                    "risk": "medium",
                    "invasiveness": "medium",
                    "speed": "fast",
                })

        elif fix_class == "playwright_install":
            solutions.append({
                "id": "playwright_install_chromium",
                "description": "Install Playwright and Chromium browser",
                "command": f"{sys.executable} -m playwright install chromium",
                "risk": "low",
                "invasiveness": "low",
                "speed": "slow",
            })

        elif fix_class == "disk_cleanup":
            solutions.append({
                "id": "pip_cache_purge",
                "description": "Purge pip download cache to free disk space",
                "command": f"{sys.executable} -m pip cache purge",
                "risk": "low",
                "invasiveness": "low",
                "speed": "fast",
            })

        elif fix_class == "python_upgrade":
            solutions.append({
                "id": "python_upgrade_guidance",
                "description": "Python version too old — user must upgrade Python manually",
                "command": None,
                "file_op": {
                    "path": "/tmp/murphy_python_upgrade_required.txt",
                    "content": (
                        "Murphy System requires Python 3.10+.\n"
                        "Download the latest Python from https://python.org/downloads\n"
                    ),
                },
                "risk": "low",
                "invasiveness": "low",
                "speed": "fast",
            })

        else:
            # Generic: retry pip install
            solutions.append({
                "id": "generic_pip_retry",
                "description": "Retry pip requirements install with verbose output",
                "command": (
                    f"{sys.executable} -m pip install -r requirements_murphy_1.0.txt"
                ),
                "risk": "low",
                "invasiveness": "low",
                "speed": "medium",
            })

        with_solutions = {
            **ctx,
            "solutions": solutions,
            "solution_count": len(solutions),
        }

        confidence = round(min(1.0, 0.7 + 0.05 * len(solutions)), 3)
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.MAGNIFY_SOLUTIONS,
            input_context=ctx,
            output_context=with_solutions,
            confidence=confidence,
        )

    def _magnify_rank(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 5: Rank solutions by reliability on this OS."""
        solutions: List[Dict[str, Any]] = ctx.get("solutions", [])
        os_name: str = ctx.get("os_name", "")

        # Scoring: lower invasiveness + faster + lower risk = higher rank
        _risk_score = {"low": 0, "medium": 1, "high": 2}
        _speed_score = {"fast": 0, "medium": 1, "slow": 2}
        _invasiveness_score = {"low": 0, "medium": 1, "high": 2}

        def _score(s: Dict[str, Any]) -> int:
            return (
                _risk_score.get(s.get("risk", "medium"), 1)
                + _speed_score.get(s.get("speed", "medium"), 1)
                + _invasiveness_score.get(s.get("invasiveness", "medium"), 1)
            )

        ranked = sorted(solutions, key=_score)

        ranked_ctx = {
            **ctx,
            "solutions": ranked,
            "top_solution": ranked[0] if ranked else {},
        }

        confidence = round(min(1.0, 0.75 + 0.05 * len(ranked)), 3)
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.MAGNIFY_RANK,
            input_context=ctx,
            output_context=ranked_ctx,
            confidence=confidence,
        )

    def _solidify_lock(self, ctx: Dict[str, Any]) -> SetupAmplificationResult:
        """Phase 6: Lock a concrete, scoped remediation plan."""
        top_solution: Dict[str, Any] = ctx.get("top_solution", {})
        solutions: List[Dict[str, Any]] = ctx.get("solutions", [])
        root_cause: str = ctx.get("root_cause", "unknown")

        # The solidified plan uses the top-ranked solution.
        # We include the second solution as a fallback if available.
        steps: List[Dict[str, Any]] = []

        for sol in solutions[:2]:  # top 2 ranked solutions
            step: Dict[str, Any] = {
                "description": sol.get("description", "Remediation step"),
                "risk_level": sol.get("risk", "medium"),
            }
            if sol.get("command"):
                step["command"] = sol["command"]
            if sol.get("file_op"):
                step["file_op"] = sol["file_op"]
            steps.append(step)

        solidified = {
            **ctx,
            "steps": steps,
            "root_cause": root_cause,
            "plan_source": "mmsmms_amplifier",
        }

        # Confidence: high if we have at least one concrete step
        confidence = 0.88 if steps else 0.2
        return SetupAmplificationResult(
            phase=SetupAmplificationPhase.SOLIDIFY_LOCK,
            input_context=ctx,
            output_context=solidified,
            confidence=round(confidence, 3),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_cascade_map(issues: List[str]) -> Dict[str, List[str]]:
        """Map each issue to the secondary issues it causes."""
        cascade: Dict[str, List[str]] = {}
        for issue in issues:
            if "python_version_too_old" in issue:
                cascade[issue] = ["pip_not_available", "playwright_not_installed"]
            elif "pip_not_available" in issue:
                cascade[issue] = ["playwright_not_installed"]
            elif "insufficient_disk" in issue:
                cascade[issue] = ["playwright_not_installed"]
            else:
                cascade[issue] = []
        return cascade

    def _log_phase(
        self,
        result: SetupAmplificationResult,
        attempt: int,
    ) -> None:
        self._log(f"mmsmms_phase_{result.phase.value}", {
            "attempt": attempt,
            "confidence": result.confidence,
            **result.to_dict(),
        })

    def _log(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with self._lock:
            capped_append(self._audit_log, entry, max_size=_MAX_AUDIT_LOG)

    def get_audit_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._audit_log)
