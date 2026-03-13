"""
Learning Loop Engines

Four conservative learning engines that analyze telemetry and generate
insights for hardening the Murphy System:

1. GateStrengtheningEngine: Near-miss → tighter gates
2. PhaseTuningEngine: Backlog → slower phase entry
3. BottleneckDetector: Systemic stalls → hypotheses
4. AssumptionInvalidator: Contradictions → confidence reduction

All engines generate recommendations, NOT execution policies.
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    GateEvolutionArtifact,
    InsightArtifact,
    InsightType,
    ReasonCode,
    TelemetryArtifact,
    TelemetryDomain,
)

logger = logging.getLogger(__name__)


class GateStrengtheningEngine:
    """
    Analyzes safety telemetry to strengthen gates.

    Logic:
    - Near-miss detected → tighten related gates
    - Contradiction increase → add verification gates
    - Safety violation → emergency gate strengthening

    Conservative trajectory: Always err on side of caution.
    """

    def __init__(self):
        self.near_miss_threshold = 3  # Strengthen after 3 near-misses
        self.contradiction_threshold = 0.2  # 20% increase triggers action
        self.lookback_window = timedelta(hours=24)

    def analyze(
        self,
        telemetry: List[TelemetryArtifact],
    ) -> List[GateEvolutionArtifact]:
        """
        Analyze telemetry and generate gate strengthening proposals.

        Returns list of proposed gate evolutions (unauthorized).
        """
        proposals = []

        # Filter safety telemetry
        safety_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.SAFETY
        ]

        # Analyze near-misses
        near_miss_proposals = self._analyze_near_misses(safety_events)
        proposals.extend(near_miss_proposals)

        # Analyze control telemetry for contradictions
        control_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.CONTROL
        ]
        contradiction_proposals = self._analyze_contradictions(control_events)
        proposals.extend(contradiction_proposals)

        return proposals

    def _analyze_near_misses(
        self,
        safety_events: List[TelemetryArtifact],
    ) -> List[GateEvolutionArtifact]:
        """Analyze near-miss events and propose gate strengthening"""
        proposals = []

        # Group by affected artifacts
        near_misses_by_artifact: Dict[str, List[TelemetryArtifact]] = defaultdict(list)

        for event in safety_events:
            if event.data.get("event_type") == "near_miss":
                for artifact_id in event.data.get("affected_artifact_ids", []):
                    near_misses_by_artifact[artifact_id].append(event)

        # Generate proposals for artifacts with multiple near-misses
        for artifact_id, events in near_misses_by_artifact.items():
            if len(events) >= self.near_miss_threshold:
                # Propose gate strengthening
                proposal = GateEvolutionArtifact.create(
                    gate_id=f"safety_gate_{artifact_id}",
                    reason_codes=[ReasonCode.NEAR_MISS_DETECTED],
                    telemetry_evidence=[e.artifact_id for e in events],
                    parameter_diff={
                        "confidence_threshold": {
                            "before": 0.7,
                            "after": 0.85,  # Increase threshold
                        },
                        "verification_required": {
                            "before": False,
                            "after": True,  # Require verification
                        },
                    },
                    rollback_state={
                        "confidence_threshold": 0.7,
                        "verification_required": False,
                    },
                )
                proposals.append(proposal)

                logger.info(
                    f"Proposed gate strengthening for {artifact_id} "
                    f"due to {len(events)} near-misses"
                )

        return proposals

    def _analyze_contradictions(
        self,
        control_events: List[TelemetryArtifact],
    ) -> List[GateEvolutionArtifact]:
        """Analyze contradiction trends and propose verification gates"""
        proposals = []

        # Extract contradiction counts over time
        contradiction_counts = []
        for event in control_events:
            if event.data.get("event_type") == "murphy_spike":
                murphy_index = event.data.get("murphy_index", 0)
                contradiction_counts.append((event.timestamp, murphy_index))

        if len(contradiction_counts) < 2:
            return proposals

        # Sort by timestamp
        contradiction_counts.sort(key=lambda x: x[0])

        # Calculate trend (recent vs historical)
        recent_window = datetime.now(timezone.utc) - timedelta(hours=6)
        recent = [m for t, m in contradiction_counts if t >= recent_window]
        historical = [m for t, m in contradiction_counts if t < recent_window]

        if not recent or not historical:
            return proposals

        recent_avg = statistics.mean(recent)
        historical_avg = statistics.mean(historical)

        # Check for significant increase
        if historical_avg > 0:
            increase_ratio = (recent_avg - historical_avg) / historical_avg

            if increase_ratio > self.contradiction_threshold:
                # Propose adding verification gates
                proposal = GateEvolutionArtifact.create(
                    gate_id="contradiction_verification_gate",
                    reason_codes=[ReasonCode.CONTRADICTION_INCREASE],
                    telemetry_evidence=[e.artifact_id for e in control_events[-10:]],
                    parameter_diff={
                        "verification_depth": {
                            "before": 1,
                            "after": 2,  # Deeper verification
                        },
                        "contradiction_tolerance": {
                            "before": 0.1,
                            "after": 0.05,  # Lower tolerance
                        },
                    },
                    rollback_state={
                        "verification_depth": 1,
                        "contradiction_tolerance": 0.1,
                    },
                )
                proposals.append(proposal)

                logger.info(
                    f"Proposed verification gate due to {increase_ratio:.1%} "
                    f"increase in contradictions"
                )

        return proposals


class PhaseTuningEngine:
    """
    Analyzes operational telemetry to tune phase scheduling.

    Logic:
    - Verification backlog growing → slow down execution phase entry
    - High retry rates → increase verification time
    - Timeout patterns → adjust phase timeouts

    Conservative: Slow down when uncertain, speed up only with evidence.
    """

    def __init__(self):
        self.backlog_threshold = 10  # Slow down if >10 pending verifications
        self.retry_threshold = 0.3  # 30% retry rate triggers slowdown
        self.lookback_window = timedelta(hours=12)

    def analyze(
        self,
        telemetry: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """
        Analyze telemetry and generate phase tuning insights.

        Returns list of insights (recommendations only).
        """
        insights = []

        # Filter operational telemetry
        operational_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.OPERATIONAL
        ]

        # Analyze verification backlog
        backlog_insights = self._analyze_backlog(operational_events)
        insights.extend(backlog_insights)

        # Analyze retry patterns
        retry_insights = self._analyze_retries(operational_events)
        insights.extend(retry_insights)

        return insights

    def _analyze_backlog(
        self,
        operational_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze verification backlog and propose phase slowdown"""
        insights = []

        # Count pending verifications by phase
        pending_by_phase: Dict[str, int] = defaultdict(int)

        for event in operational_events:
            phase = event.data.get("phase")
            status = event.data.get("completion_status")

            if phase and status in ["timeout", "aborted"]:
                pending_by_phase[phase] += 1

        # Generate insights for phases with high backlog
        for phase, count in pending_by_phase.items():
            if count >= self.backlog_threshold:
                insight = InsightArtifact.create(
                    insight_type=InsightType.PHASE_TUNING,
                    severity="warning",
                    title=f"Verification backlog in {phase} phase",
                    description=(
                        f"Detected {count} pending verifications in {phase} phase. "
                        f"Recommend slowing phase entry to allow backlog to clear."
                    ),
                    evidence=[
                        e.artifact_id for e in operational_events
                        if e.data.get("phase") == phase
                    ][:10],
                    recommendation={
                        "action": "slow_phase_entry",
                        "phase": phase,
                        "current_delay_ms": 1000,
                        "recommended_delay_ms": 2000,
                        "reason": "verification_backlog",
                    },
                    confidence=0.85,
                )
                insights.append(insight)

                logger.info(
                    f"Generated phase tuning insight for {phase}: "
                    f"{count} pending verifications"
                )

        return insights

    def _analyze_retries(
        self,
        operational_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze retry patterns and propose verification time increase"""
        insights = []

        # Calculate retry rate
        total_tasks = len(operational_events)
        if total_tasks == 0:
            return insights

        high_retry_tasks = [
            e for e in operational_events
            if e.data.get("retry_count", 0) >= 2
        ]

        retry_rate = len(high_retry_tasks) / total_tasks

        if retry_rate > self.retry_threshold:
            insight = InsightArtifact.create(
                insight_type=InsightType.PHASE_TUNING,
                severity="warning",
                title="High retry rate detected",
                description=(
                    f"Retry rate of {retry_rate:.1%} exceeds threshold. "
                    f"Tasks may need more verification time before execution."
                ),
                evidence=[e.artifact_id for e in high_retry_tasks[:10]],
                recommendation={
                    "action": "increase_verification_time",
                    "current_timeout_ms": 5000,
                    "recommended_timeout_ms": 7500,
                    "reason": "high_retry_rate",
                },
                confidence=0.80,
            )
            insights.append(insight)

            logger.info(
                f"Generated retry insight: {retry_rate:.1%} retry rate"
            )

        return insights


class BottleneckDetector:
    """
    Detects systemic stalls and bottlenecks.

    Logic:
    - Identify phases with consistently high latency
    - Detect resource contention patterns
    - Find sequential dependencies causing delays

    Output: Hypotheses and recommendations (NOT execution changes).
    """

    def __init__(self):
        self.latency_threshold_ms = 5000  # 5 seconds
        self.stall_threshold = 5  # 5 consecutive high-latency events
        self.lookback_window = timedelta(hours=6)

    def analyze(
        self,
        telemetry: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """
        Analyze telemetry and detect bottlenecks.

        Returns list of bottleneck insights.
        """
        insights = []

        # Filter operational telemetry
        operational_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.OPERATIONAL
        ]

        # Analyze latency patterns
        latency_insights = self._analyze_latency(operational_events)
        insights.extend(latency_insights)

        # Analyze human intervention patterns
        human_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.HUMAN
        ]
        human_insights = self._analyze_human_bottlenecks(human_events)
        insights.extend(human_insights)

        return insights

    def _analyze_latency(
        self,
        operational_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze latency patterns to detect bottlenecks"""
        insights = []

        # Group by phase
        latency_by_phase: Dict[str, List[float]] = defaultdict(list)

        for event in operational_events:
            phase = event.data.get("phase")
            latency = event.data.get("latency_ms", 0)

            if phase:
                latency_by_phase[phase].append(latency)

        # Detect phases with consistently high latency
        for phase, latencies in latency_by_phase.items():
            if len(latencies) < self.stall_threshold:
                continue

            # Check recent latencies
            recent_latencies = latencies[-self.stall_threshold:]
            high_latency_count = sum(
                1 for l in recent_latencies
                if l > self.latency_threshold_ms
            )

            if high_latency_count >= self.stall_threshold:
                avg_latency = statistics.mean(recent_latencies)

                insight = InsightArtifact.create(
                    insight_type=InsightType.BOTTLENECK_DETECTION,
                    severity="warning",
                    title=f"Bottleneck detected in {phase} phase",
                    description=(
                        f"Phase {phase} showing consistently high latency: "
                        f"{avg_latency:.0f}ms average. "
                        f"Possible resource contention or sequential dependency."
                    ),
                    evidence=[
                        e.artifact_id for e in operational_events
                        if e.data.get("phase") == phase
                    ][-10:],
                    recommendation={
                        "action": "investigate_bottleneck",
                        "phase": phase,
                        "avg_latency_ms": avg_latency,
                        "hypothesis": "resource_contention_or_sequential_dependency",
                        "suggested_actions": [
                            "Review phase dependencies",
                            "Check resource allocation",
                            "Consider parallel execution",
                        ],
                    },
                    confidence=0.75,
                )
                insights.append(insight)

                logger.info(
                    f"Detected bottleneck in {phase}: {avg_latency:.0f}ms"
                )

        return insights

    def _analyze_human_bottlenecks(
        self,
        human_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze human intervention patterns for bottlenecks"""
        insights = []

        # Calculate approval latencies
        approval_latencies = [
            e.data.get("approval_latency_ms", 0)
            for e in human_events
            if e.data.get("event_type") == "approval"
            and e.data.get("approval_latency_ms") is not None
        ]

        if len(approval_latencies) < 5:
            return insights

        avg_approval_latency = statistics.mean(approval_latencies)

        # If approval latency is high, suggest automation
        if avg_approval_latency > 60000:  # 1 minute
            insight = InsightArtifact.create(
                insight_type=InsightType.BOTTLENECK_DETECTION,
                severity="info",
                title="Human approval bottleneck detected",
                description=(
                    f"Average approval latency is {avg_approval_latency/1000:.1f}s. "
                    f"Consider automating routine approvals with stronger gates."
                ),
                evidence=[
                    e.artifact_id for e in human_events
                    if e.data.get("event_type") == "approval"
                ][:10],
                recommendation={
                    "action": "automate_approvals",
                    "avg_latency_ms": avg_approval_latency,
                    "hypothesis": "routine_approvals_can_be_automated",
                    "suggested_actions": [
                        "Identify approval patterns",
                        "Strengthen pre-approval gates",
                        "Implement conditional automation",
                    ],
                },
                confidence=0.70,
            )
            insights.append(insight)

            logger.info(
                f"Detected human approval bottleneck: "
                f"{avg_approval_latency/1000:.1f}s average"
            )

        return insights


class AssumptionInvalidator:
    """
    Detects when telemetry contradicts system assumptions.

    Logic:
    - Compare actual outcomes vs predicted outcomes
    - Detect assumption violations
    - Reduce confidence when assumptions fail

    Conservative: Invalidate quickly, validate slowly.
    """

    def __init__(self):
        self.contradiction_threshold = 0.3  # 30% contradiction rate
        self.lookback_window = timedelta(hours=24)

    def analyze(
        self,
        telemetry: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """
        Analyze telemetry for assumption violations.

        Returns list of assumption invalidation insights.
        """
        insights = []

        # Analyze control telemetry for confidence mismatches
        control_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.CONTROL
        ]
        confidence_insights = self._analyze_confidence_mismatches(control_events)
        insights.extend(confidence_insights)

        # Analyze operational telemetry for prediction failures
        operational_events = [
            t for t in telemetry
            if t.domain == TelemetryDomain.OPERATIONAL
        ]
        prediction_insights = self._analyze_prediction_failures(operational_events)
        insights.extend(prediction_insights)

        return insights

    def _analyze_confidence_mismatches(
        self,
        control_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze confidence updates for mismatches"""
        insights = []

        # Find confidence updates
        confidence_updates = [
            e for e in control_events
            if e.data.get("event_type") == "confidence_update"
            and e.data.get("confidence_before") is not None
            and e.data.get("confidence_after") is not None
        ]

        if len(confidence_updates) < 10:
            return insights

        # Count significant drops (>0.2)
        significant_drops = [
            e for e in confidence_updates
            if (e.data["confidence_before"] - e.data["confidence_after"]) > 0.2
        ]

        drop_rate = len(significant_drops) / len(confidence_updates)

        if drop_rate > self.contradiction_threshold:
            insight = InsightArtifact.create(
                insight_type=InsightType.ASSUMPTION_INVALIDATION,
                severity="warning",
                title="High confidence drop rate detected",
                description=(
                    f"Confidence dropping significantly in {drop_rate:.1%} of updates. "
                    f"System assumptions may be invalid. Recommend re-evaluation."
                ),
                evidence=[e.artifact_id for e in significant_drops[:10]],
                recommendation={
                    "action": "reduce_base_confidence",
                    "current_base": 0.7,
                    "recommended_base": 0.6,
                    "reason": "assumption_invalidation",
                    "trigger_re_expansion": True,
                },
                confidence=0.85,
            )
            insights.append(insight)

            logger.info(
                f"Detected assumption invalidation: {drop_rate:.1%} drop rate"
            )

        return insights

    def _analyze_prediction_failures(
        self,
        operational_events: List[TelemetryArtifact],
    ) -> List[InsightArtifact]:
        """Analyze operational failures for prediction mismatches"""
        insights = []

        # Count failures
        total_tasks = len(operational_events)
        if total_tasks == 0:
            return insights

        failures = [
            e for e in operational_events
            if e.data.get("completion_status") in ["failure", "timeout", "aborted"]
        ]

        failure_rate = len(failures) / total_tasks

        # If failure rate is high, assumptions may be wrong
        if failure_rate > 0.2:  # 20% failure rate
            insight = InsightArtifact.create(
                insight_type=InsightType.ASSUMPTION_INVALIDATION,
                severity="critical",
                title="High failure rate indicates invalid assumptions",
                description=(
                    f"Failure rate of {failure_rate:.1%} suggests system assumptions "
                    f"are incorrect. Recommend immediate confidence reduction and "
                    f"re-expansion with updated assumptions."
                ),
                evidence=[e.artifact_id for e in failures[:10]],
                recommendation={
                    "action": "emergency_confidence_reduction",
                    "reduce_confidence_by": 0.3,
                    "trigger_re_expansion": True,
                    "require_human_review": True,
                },
                confidence=0.90,
            )
            insights.append(insight)

            logger.warning(
                f"Critical assumption invalidation: {failure_rate:.1%} failure rate"
            )

        return insights


class HardeningPolicyEngine:
    """
    Orchestrates all learning loops with conservative hardening policy.

    Policy:
    - Default trajectory: More strict over time
    - Relaxation: Only with deterministic evidence
    - Gate evolution: Always requires authorization
    - Confidence: Reduce quickly, increase slowly
    """

    def __init__(self):
        self.gate_engine = GateStrengtheningEngine()
        self.phase_engine = PhaseTuningEngine()
        self.bottleneck_detector = BottleneckDetector()
        self.assumption_invalidator = AssumptionInvalidator()

        self.hardening_coefficient = 1.1  # 10% stricter by default
        self.relaxation_evidence_threshold = 0.95  # 95% confidence required

    def analyze_all(
        self,
        telemetry: List[TelemetryArtifact],
    ) -> Tuple[List[GateEvolutionArtifact], List[InsightArtifact]]:
        """
        Run all learning loops and apply hardening policy.

        Returns:
            - Gate evolution proposals (unauthorized)
            - Insights and recommendations
        """
        # Run all engines
        gate_proposals = self.gate_engine.analyze(telemetry)
        phase_insights = self.phase_engine.analyze(telemetry)
        bottleneck_insights = self.bottleneck_detector.analyze(telemetry)
        assumption_insights = self.assumption_invalidator.analyze(telemetry)

        # Combine insights
        all_insights = phase_insights + bottleneck_insights + assumption_insights

        # Apply hardening policy to gate proposals
        hardened_proposals = self._apply_hardening_policy(gate_proposals)

        return hardened_proposals, all_insights

    def _apply_hardening_policy(
        self,
        proposals: List[GateEvolutionArtifact],
    ) -> List[GateEvolutionArtifact]:
        """
        Apply conservative hardening policy to gate proposals.

        - Strengthening proposals: Apply hardening coefficient
        - Relaxation proposals: Require high-confidence evidence
        """
        hardened = []

        for proposal in proposals:
            # Check if this is a relaxation (only allowed with deterministic evidence)
            is_relaxation = self._is_relaxation(proposal)

            if is_relaxation:
                # Relaxation requires deterministic evidence
                if ReasonCode.DETERMINISTIC_EVIDENCE not in proposal.reason_codes:
                    logger.info(
                        f"Rejected relaxation proposal {proposal.evolution_id}: "
                        f"No deterministic evidence"
                    )
                    continue
            else:
                # Strengthening: Apply hardening coefficient
                proposal = self._apply_hardening_coefficient(proposal)

            hardened.append(proposal)

        return hardened

    def _is_relaxation(self, proposal: GateEvolutionArtifact) -> bool:
        """Check if proposal relaxes constraints"""
        for param, diff in proposal.parameter_diff.items():
            before = diff.get("before")
            after = diff.get("after")

            # Check for threshold decreases or requirement removals
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                if after < before:
                    return True
            elif isinstance(before, bool) and isinstance(after, bool):
                if before and not after:
                    return True

        return False

    def _apply_hardening_coefficient(
        self,
        proposal: GateEvolutionArtifact,
    ) -> GateEvolutionArtifact:
        """Apply hardening coefficient to make proposal more conservative"""
        for param, diff in proposal.parameter_diff.items():
            before = diff.get("before")
            after = diff.get("after")

            # Apply coefficient to numeric increases
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                if after > before:
                    # Make increase more aggressive
                    increase = after - before
                    hardened_after = before + (increase * self.hardening_coefficient)
                    proposal.parameter_diff[param]["after"] = hardened_after

        return proposal
