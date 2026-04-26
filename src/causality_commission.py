"""
causality_commission.py — Murphy System Causality Commissioning Gate
PATCH-097a

Causality is the permission system between planning and execution.

The plan lives inside causality.
Execution only happens if causality grants exit.
Exit is earned — not assumed.

Architecture:
  You define the expected result.
  The system defines the test types that can verify it.
  Actual result is measured against expected within tolerance.
  If actual matches expected → CausalityExitGrant: execution permitted.
  If not → plan stays in causality, HITL alerted, gap documented.

This is not a test runner. It is a commissioning protocol.
The same principle that applies to every hardware commissioning:
  1. Define expected result (you)
  2. Select test type (system — based on what can be verified)
  3. Run test
  4. Compare actual to expected
  5. Grant exit or hold

No exit = no execution. The gate is closed until it is earned.

PATCH-097a
Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TEST TYPES — defined by the system, selected based on what can be verified
# ---------------------------------------------------------------------------

class TestType(str, Enum):
    """
    The system's vocabulary of verification methods.
    Each type defines HOW the actual result is measured.
    You define WHAT the expected result is.
    The system picks the right test type for the kind of expected result.
    """

    # Existence tests — does the thing exist?
    ENDPOINT_EXISTS     = "endpoint_exists"       # HTTP endpoint responds
    MODULE_IMPORTABLE   = "module_importable"     # Python module loads without error
    FILE_PRESENT        = "file_present"          # file exists at expected path
    SERVICE_ACTIVE      = "service_active"        # systemd service is running

    # State tests — is the thing in the expected state?
    HEALTH_GREEN        = "health_green"          # /api/health returns status=healthy
    SHIELD_LAYER_ACTIVE = "shield_layer_active"  # named Shield Wall layer is active
    VALUE_EQUALS        = "value_equals"          # a specific field equals expected value
    VALUE_IN_RANGE      = "value_in_range"        # a numeric value is within tolerance

    # Behavior tests — does the thing do what it should?
    ENDPOINT_RETURNS    = "endpoint_returns"      # HTTP endpoint returns expected shape
    FUNCTION_CALLABLE   = "function_callable"     # function can be called, returns result
    PIPELINE_FLOWS      = "pipeline_flows"        # data flows through a sequence of steps
    GATE_BLOCKS         = "gate_blocks"           # a prohibition gate correctly refuses
    GATE_PERMITS        = "gate_permits"          # a permission gate correctly allows

    # Causal tests — does the action cause the expected change?
    BEFORE_AFTER        = "before_after"          # state changes from A to B after action
    SIDE_EFFECT_ABSENT  = "side_effect_absent"    # action does NOT cause specified change
    CONVERGENCE_MOVES   = "convergence_moves"     # R_fair moves in expected direction
    MSS_SHIFTS          = "mss_shifts"            # MSS axis shifts in expected direction

    # Integration tests — does the system work end to end?
    FULL_PIPELINE       = "full_pipeline"         # request traverses all stages correctly
    HITL_REACHABLE      = "hitl_reachable"        # HITL escalation path is live
    ROSETTA_RECORDS     = "rosetta_records"       # outcome is written to Rosetta record
    LEGACY_UPDATES      = "legacy_updates"        # legacy document is updated


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class ExpectedResult:
    """
    Defined by you — the human architect or the planning system.
    States what success looks like before the action runs.
    """
    description:     str                  # plain language: what should be true
    test_type:       TestType             # which kind of verification applies
    target:          str                  # what to check (endpoint path, module name, etc.)
    expected_value:  Any = None           # what value / state is expected
    tolerance:       float = 0.0          # acceptable delta for numeric comparisons
    timeout_s:       float = 10.0         # how long to wait for the expected result
    critical:        bool = True          # if True, failure blocks exit; if False, warning only


@dataclass
class ActualResult:
    """
    Measured by the system after the action runs in simulation or in execution.
    """
    test_type:       TestType
    target:          str
    actual_value:    Any
    passed:          bool
    delta:           float = 0.0          # numeric distance from expected (0 if not applicable)
    error:           Optional[str] = None # exception message if measurement failed
    duration_ms:     float = 0.0


@dataclass
class CommissioningTest:
    """
    One expected result paired with one actual result.
    The commissioning record for a single verification.
    """
    test_id:          str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    expected:         Optional[ExpectedResult] = None
    actual:           Optional[ActualResult] = None
    verdict:          str = "PENDING"     # PASS | FAIL | WARNING | PENDING
    commissioned_at:  str = ""

    def evaluate(self) -> str:
        """Compare expected to actual. Set verdict."""
        if not self.expected or not self.actual:
            self.verdict = "PENDING"
            return self.verdict

        if self.actual.error:
            self.verdict = "FAIL"
            return self.verdict

        if not self.actual.passed:
            self.verdict = "FAIL" if self.expected.critical else "WARNING"
            return self.verdict

        # Numeric tolerance check
        if self.expected.tolerance > 0 and isinstance(self.expected.expected_value, (int, float)):
            if self.actual.delta > self.expected.tolerance:
                self.verdict = "FAIL" if self.expected.critical else "WARNING"
                return self.verdict

        self.verdict = "PASS"
        self.commissioned_at = datetime.now(timezone.utc).isoformat()
        return self.verdict


@dataclass
class CausalityExitDecision:
    """
    The permission gate decision.
    GRANTED = execution permitted.
    HELD    = plan stays in causality, HITL alerted.
    """
    decision_id:    str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id:      str = ""
    action_desc:    str = ""
    tests:          List[CommissioningTest] = field(default_factory=list)
    exit_granted:   bool = False
    hold_reason:    Optional[str] = None
    hitl_required:  bool = False
    decided_at:     str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.verdict == "PASS")

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if t.verdict == "FAIL")

    @property
    def warnings(self) -> int:
        return sum(1 for t in self.tests if t.verdict == "WARNING")

    def summary(self) -> Dict:
        return {
            "decision_id":   self.decision_id,
            "action_id":     self.action_id,
            "action_desc":   self.action_desc,
            "exit_granted":  self.exit_granted,
            "hold_reason":   self.hold_reason,
            "hitl_required": self.hitl_required,
            "tests_passed":  self.passed,
            "tests_failed":  self.failed,
            "tests_warning": self.warnings,
            "decided_at":    self.decided_at,
            "tests": [
                {
                    "test_id":  t.test_id,
                    "type":     t.expected.test_type if t.expected else None,
                    "target":   t.expected.target if t.expected else None,
                    "verdict":  t.verdict,
                    "expected": str(t.expected.expected_value) if t.expected else None,
                    "actual":   str(t.actual.actual_value) if t.actual else None,
                    "error":    t.actual.error if t.actual else None,
                }
                for t in self.tests
            ]
        }


# ---------------------------------------------------------------------------
# TEST RUNNERS — one per TestType
# ---------------------------------------------------------------------------

class CausalityTestRunner:
    """
    Knows how to measure each TestType.
    Takes an ExpectedResult, runs the measurement, returns ActualResult.
    """

    def run(self, expected: ExpectedResult,
            context: Dict[str, Any] = None) -> ActualResult:
        """Dispatch to the correct measurement method."""
        ctx = context or {}
        start = time.monotonic()
        try:
            result = self._dispatch(expected, ctx)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as e:
            return ActualResult(
                test_type=expected.test_type,
                target=expected.target,
                actual_value=None,
                passed=False,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000
            )

    def _dispatch(self, expected: ExpectedResult,
                  ctx: Dict) -> ActualResult:
        t = expected.test_type

        if t == TestType.ENDPOINT_EXISTS:
            return self._test_endpoint_exists(expected)
        elif t == TestType.MODULE_IMPORTABLE:
            return self._test_module_importable(expected)
        elif t == TestType.FILE_PRESENT:
            return self._test_file_present(expected)
        elif t == TestType.SERVICE_ACTIVE:
            return self._test_service_active(expected)
        elif t == TestType.HEALTH_GREEN:
            return self._test_health_green(expected)
        elif t == TestType.SHIELD_LAYER_ACTIVE:
            return self._test_shield_layer_active(expected)
        elif t == TestType.VALUE_EQUALS:
            return self._test_value_equals(expected, ctx)
        elif t == TestType.VALUE_IN_RANGE:
            return self._test_value_in_range(expected, ctx)
        elif t == TestType.ENDPOINT_RETURNS:
            return self._test_endpoint_returns(expected, ctx)
        elif t == TestType.FUNCTION_CALLABLE:
            return self._test_function_callable(expected, ctx)
        elif t == TestType.GATE_BLOCKS:
            return self._test_gate_blocks(expected, ctx)
        elif t == TestType.GATE_PERMITS:
            return self._test_gate_permits(expected, ctx)
        elif t == TestType.BEFORE_AFTER:
            return self._test_before_after(expected, ctx)
        elif t == TestType.SIDE_EFFECT_ABSENT:
            return self._test_side_effect_absent(expected, ctx)
        elif t == TestType.FULL_PIPELINE:
            return self._test_full_pipeline(expected, ctx)
        else:
            return ActualResult(
                test_type=t, target=expected.target,
                actual_value=None, passed=False,
                error=f"No runner implemented for test type: {t}"
            )

    # --- Existence tests ---

    def _test_endpoint_exists(self, e: ExpectedResult) -> ActualResult:
        import urllib.request
        url = e.target if e.target.startswith("http") else f"http://127.0.0.1:8000{e.target}"
        try:
            req = urllib.request.urlopen(url, timeout=e.timeout_s)
            status = req.status
            passed = status < 500
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=status, passed=passed)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_module_importable(self, e: ExpectedResult) -> ActualResult:
        import importlib
        try:
            mod = importlib.import_module(e.target)
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=str(mod), passed=True)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_file_present(self, e: ExpectedResult) -> ActualResult:
        import os
        exists = os.path.isfile(e.target)
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=exists, passed=exists)

    def _test_service_active(self, e: ExpectedResult) -> ActualResult:
        import subprocess
        result = subprocess.run(
            ["systemctl", "is-active", e.target],
            capture_output=True, text=True, timeout=e.timeout_s
        )
        active = result.stdout.strip() == "active"
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=result.stdout.strip(), passed=active)

    def _test_health_green(self, e: ExpectedResult) -> ActualResult:
        import urllib.request, json
        url = "http://127.0.0.1:8000/api/health"
        try:
            data = json.loads(urllib.request.urlopen(url, timeout=e.timeout_s).read())
            status = data.get("status", "")
            passed = status == "healthy"
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=status, passed=passed)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_shield_layer_active(self, e: ExpectedResult) -> ActualResult:
        import urllib.request, json
        url = "http://127.0.0.1:8000/api/shield/status"
        try:
            data = json.loads(urllib.request.urlopen(url, timeout=e.timeout_s).read())
            layers = {l["layer"]: l["active"] for l in data.get("layers", [])}
            active = layers.get(e.target, False)
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=active, passed=active)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_value_equals(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        actual = ctx.get(e.target)
        passed = actual == e.expected_value
        delta = 0.0
        if isinstance(actual, (int, float)) and isinstance(e.expected_value, (int, float)):
            delta = abs(actual - e.expected_value)
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=actual, passed=passed, delta=delta)

    def _test_value_in_range(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        actual = ctx.get(e.target)
        lo, hi = e.expected_value if isinstance(e.expected_value, (list, tuple)) else (0, 1)
        passed = isinstance(actual, (int, float)) and lo <= actual <= hi
        delta = 0.0 if passed else min(abs(actual - lo), abs(actual - hi)) if isinstance(actual, (int, float)) else 999
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=actual, passed=passed, delta=delta)

    def _test_endpoint_returns(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        import urllib.request, json
        url = e.target if e.target.startswith("http") else f"http://127.0.0.1:8000{e.target}"
        try:
            data = json.loads(urllib.request.urlopen(url, timeout=e.timeout_s).read())
            # expected_value is a dict of key: expected_val pairs to check
            checks = e.expected_value if isinstance(e.expected_value, dict) else {}
            failed_keys = [k for k, v in checks.items() if data.get(k) != v]
            passed = len(failed_keys) == 0
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=data, passed=passed,
                                error=f"Keys mismatch: {failed_keys}" if not passed else None)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_function_callable(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        fn = ctx.get(e.target) or ctx.get("fn")
        if not callable(fn):
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False,
                                error=f"No callable found for target: {e.target}")
        try:
            result = fn(**(ctx.get("fn_kwargs", {})))
            passed = result is not None if e.expected_value is None else result == e.expected_value
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=result, passed=passed)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_gate_blocks(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        """Gate correctly refuses a prohibited input."""
        gate_fn = ctx.get("gate_fn")
        prohibited_input = ctx.get("prohibited_input", e.expected_value)
        if not callable(gate_fn):
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False,
                                error="gate_fn not provided in context")
        try:
            permitted, reason = gate_fn(prohibited_input)
            passed = not permitted  # gate should BLOCK this
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value={"permitted": permitted, "reason": reason},
                                passed=passed)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_gate_permits(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        """Gate correctly allows a valid input."""
        gate_fn = ctx.get("gate_fn")
        valid_input = ctx.get("valid_input", e.expected_value)
        if not callable(gate_fn):
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False,
                                error="gate_fn not provided in context")
        try:
            permitted, reason = gate_fn(valid_input)
            passed = permitted  # gate should PERMIT this
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value={"permitted": permitted, "reason": reason},
                                passed=passed)
        except Exception as ex:
            return ActualResult(test_type=e.test_type, target=e.target,
                                actual_value=None, passed=False, error=str(ex))

    def _test_before_after(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        """State changes from before_value to after_value following the action."""
        before = ctx.get("before_value")
        after  = ctx.get("after_value")
        expected_after = e.expected_value
        passed = after == expected_after
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value={"before": before, "after": after},
                            passed=passed)

    def _test_side_effect_absent(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        """Confirms an action did NOT cause a specified side effect."""
        side_effect_value = ctx.get("side_effect_value")
        forbidden = e.expected_value  # the value that must NOT appear
        passed = side_effect_value != forbidden
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=side_effect_value, passed=passed)

    def _test_full_pipeline(self, e: ExpectedResult, ctx: Dict) -> ActualResult:
        """Request traverses all pipeline stages and reaches expected final state."""
        stages_completed = ctx.get("stages_completed", [])
        required_stages  = e.expected_value if isinstance(e.expected_value, list) else []
        missing = [s for s in required_stages if s not in stages_completed]
        passed = len(missing) == 0
        return ActualResult(test_type=e.test_type, target=e.target,
                            actual_value=stages_completed, passed=passed,
                            error=f"Missing stages: {missing}" if not passed else None)


# ---------------------------------------------------------------------------
# CAUSALITY COMMISSION GATE — the permission system
# ---------------------------------------------------------------------------

class CausalityCommissionGate:
    """
    The connection between planning and execution.

    The plan lives in causality.
    Execution only happens if this gate grants exit.
    Exit is earned by commissioning — expected vs actual, test by test.

    Usage:
        gate = CausalityCommissionGate()

        # You define what success looks like
        expected = [
            ExpectedResult(
                description="Shield Wall endpoint responds",
                test_type=TestType.SHIELD_LAYER_ACTIVE,
                target="InterAIConductGuard",
                expected_value=True,
            ),
            ExpectedResult(
                description="Module loads cleanly",
                test_type=TestType.MODULE_IMPORTABLE,
                target="src.inter_ai_conduct",
            )
        ]

        # Gate commissions and decides
        decision = gate.commission(
            action_id="PATCH-097a",
            action_desc="InterAIConductGuard deployment",
            expected_results=expected,
            context={}
        )

        if decision.exit_granted:
            # Execution permitted — run the real action
        else:
            # Hold — plan stays in causality, HITL alerted
    """

    def __init__(self):
        self._runner  = CausalityTestRunner()
        self._history: List[CausalityExitDecision] = []

    def commission(
        self,
        action_id:        str,
        action_desc:      str,
        expected_results: List[ExpectedResult],
        context:          Dict[str, Any] = None,
        require_all_pass: bool = True,
    ) -> CausalityExitDecision:
        """
        Run commissioning tests. Grant or hold exit.

        Args:
            action_id:        identifier for the planned action
            action_desc:      plain language description
            expected_results: list of ExpectedResult (defined by you)
            context:          runtime values needed by test runners
            require_all_pass: if True, any FAIL blocks exit (default)
                              if False, only critical FAILs block exit

        Returns:
            CausalityExitDecision — exit_granted=True means execution is permitted
        """
        ctx = context or {}
        tests: List[CommissioningTest] = []

        for expected in expected_results:
            test = CommissioningTest(expected=expected)
            test.actual = self._runner.run(expected, ctx)
            test.evaluate()
            tests.append(test)
            logger.info(
                "Commission test [%s] %s → %s (expected=%s actual=%s)",
                test.test_id, expected.test_type, test.verdict,
                expected.expected_value, test.actual.actual_value
            )

        # Gate decision
        critical_failures = [t for t in tests if t.verdict == "FAIL" and t.expected and t.expected.critical]
        non_critical_failures = [t for t in tests if t.verdict == "FAIL" and t.expected and not t.expected.critical]
        any_failure = [t for t in tests if t.verdict == "FAIL"]

        if require_all_pass:
            failures = critical_failures  # only critical block by default
        else:
            failures = any_failure

        exit_granted = len(failures) == 0

        hold_reason = None
        if not exit_granted:
            hold_reason = "; ".join(
                f"{t.expected.test_type}({t.expected.target}): "
                f"expected={t.expected.expected_value} actual={t.actual.actual_value if t.actual else 'unmeasured'}"
                for t in failures
            )

        decision = CausalityExitDecision(
            action_id    = action_id,
            action_desc  = action_desc,
            tests        = tests,
            exit_granted = exit_granted,
            hold_reason  = hold_reason,
            hitl_required = not exit_granted,
        )

        self._history.append(decision)
        logger.info(
            "CausalityExitDecision [%s] %s: exit_granted=%s failures=%d",
            decision.decision_id, action_id, exit_granted, len(failures)
        )
        return decision

    def history(self, n: int = 20) -> List[Dict]:
        """Last N commissioning decisions."""
        return [d.summary() for d in self._history[-n:]]

    def status(self) -> Dict:
        total = len(self._history)
        granted = sum(1 for d in self._history if d.exit_granted)
        held    = total - granted
        return {
            "layer":           "CausalityCommissionGate",
            "active":          True,
            "decisions_total": total,
            "exits_granted":   granted,
            "exits_held":      held,
            "principle": (
                "The plan lives in causality. "
                "Execution only happens if causality grants exit. "
                "Exit is earned, not assumed."
            ),
            "test_types": [t.value for t in TestType],
        }


# ---------------------------------------------------------------------------
# GLOBAL INSTANCE
# ---------------------------------------------------------------------------

causality_commission_gate = CausalityCommissionGate()
