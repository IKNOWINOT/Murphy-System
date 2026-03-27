"""
Murphy Gate

Threshold-based decision mechanism that determines whether to proceed
with execution based on confidence scores.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from .murphy_models import GateAction, GateResult, Phase, UncertaintyScores

logger = logging.getLogger(__name__)


class MurphyGate:
    """
    Murphy Gate - Threshold-based decision mechanism

    Decides whether to proceed with execution based on confidence scores.
    Different phases have different threshold requirements.
    """

    def __init__(self):
        # Default threshold for all operations
        self.default_threshold = 0.7

        # Phase-specific thresholds
        self.phase_thresholds = {
            Phase.EXPAND: 0.5,      # Lower threshold for exploration
            Phase.TYPE: 0.6,        # Moderate threshold for classification
            Phase.ENUMERATE: 0.625, # Slightly above TYPE to gate enumeration separately
            Phase.CONSTRAIN: 0.7,   # Standard threshold for constraints
            Phase.COLLAPSE: 0.75,   # Higher threshold for decisions
            Phase.BIND: 0.8,        # Very high for commitment
            Phase.EXECUTE: 0.85     # Highest for execution
        }

        # Action thresholds (margins from threshold)
        self.action_margins = {
            'proceed_automatically': 0.15,      # confidence >= threshold + 0.15
            'proceed_with_monitoring': 0.05,    # confidence >= threshold + 0.05
            'proceed_with_caution': 0.0,        # confidence >= threshold
            'request_human_review': -0.05,      # confidence >= threshold - 0.05
            'require_human_approval': -0.15,    # confidence >= threshold - 0.15
            'block_execution': float('-inf')    # confidence < threshold - 0.15
        }

    def evaluate(
        self,
        confidence: float,
        threshold: Optional[float] = None,
        phase: Optional[Phase] = None,
        context: Optional[dict] = None,
        runtime_config: Optional[dict] = None,
    ) -> GateResult:
        """
        Evaluate whether to proceed with execution

        Args:
            confidence: Confidence score (0.0 to 1.0)
            threshold: Custom threshold (optional, uses phase/default if not provided)
            phase: Current execution phase (optional, accepts Phase enum or string)
            context: Additional context for decision (optional)
            runtime_config: Runtime config dict; if provided, overrides threshold via
                ``confidence_threshold:{task_type}`` key where task_type comes from
                ``context.get('task_type')``.

        Returns:
            GateResult with decision and rationale
        """
        # Coerce string phase to Phase enum
        if isinstance(phase, str):
            try:
                phase = Phase(phase.lower())
            except ValueError:
                try:
                    phase = Phase[phase.upper()]
                except KeyError:
                    phase = None
        # Apply runtime_config threshold override if provided
        if runtime_config is not None and context is not None:
            task_type = context.get("task_type")
            if task_type:
                config_key = f"confidence_threshold:{task_type}"
                if config_key in runtime_config:
                    threshold = float(runtime_config[config_key])
        # Determine effective threshold
        effective_threshold = self._determine_threshold(threshold, phase)

        # Calculate margin
        margin = confidence - effective_threshold

        # Determine action based on margin
        action = self._determine_action(margin)

        # Determine if allowed to proceed
        allowed = action in [
            GateAction.PROCEED_AUTOMATICALLY,
            GateAction.PROCEED_WITH_MONITORING,
            GateAction.PROCEED_WITH_CAUTION
        ]

        # Generate rationale
        rationale = self._generate_rationale(
            confidence=confidence,
            threshold=effective_threshold,
            margin=margin,
            action=action,
            phase=phase
        )

        # Create result
        result = GateResult(
            allowed=allowed,
            confidence=confidence,
            threshold=effective_threshold,
            margin=margin,
            action=action,
            rationale=rationale,
            phase=phase,
            metadata={
                'context': context or {},
                'decision_time': datetime.now(timezone.utc).isoformat()
            }
        )

        # Log decision
        self._log_decision(result)

        return result

    def _determine_threshold(
        self,
        custom_threshold: Optional[float],
        phase: Optional[Phase]
    ) -> float:
        """Determine effective threshold"""
        if custom_threshold is not None:
            return custom_threshold
        elif phase is not None:
            return self.phase_thresholds.get(phase, self.default_threshold)
        else:
            return self.default_threshold

    def _determine_action(self, margin: float) -> GateAction:
        """Determine action based on margin"""
        if margin >= self.action_margins['proceed_automatically']:
            return GateAction.PROCEED_AUTOMATICALLY
        elif margin >= self.action_margins['proceed_with_monitoring']:
            return GateAction.PROCEED_WITH_MONITORING
        elif margin >= self.action_margins['proceed_with_caution']:
            return GateAction.PROCEED_WITH_CAUTION
        elif margin >= self.action_margins['request_human_review']:
            return GateAction.REQUEST_HUMAN_REVIEW
        elif margin >= self.action_margins['require_human_approval']:
            return GateAction.REQUIRE_HUMAN_APPROVAL
        else:
            return GateAction.BLOCK_EXECUTION

    def _generate_rationale(
        self,
        confidence: float,
        threshold: float,
        margin: float,
        action: GateAction,
        phase: Optional[Phase]
    ) -> str:
        """Generate human-readable rationale for decision"""

        phase_str = f" in {phase.value if hasattr(phase, 'value') else phase} phase" if phase else ""

        if action == GateAction.PROCEED_AUTOMATICALLY:
            return (
                f"Confidence {confidence:.2f} significantly exceeds threshold {threshold:.2f}"
                f"{phase_str} (margin: +{margin:.2f}). "
                f"Proceeding automatically with high confidence."
            )

        elif action == GateAction.PROCEED_WITH_MONITORING:
            return (
                f"Confidence {confidence:.2f} exceeds threshold {threshold:.2f}"
                f"{phase_str} (margin: +{margin:.2f}). "
                f"Proceeding with monitoring to track outcomes."
            )

        elif action == GateAction.PROCEED_WITH_CAUTION:
            return (
                f"Confidence {confidence:.2f} meets threshold {threshold:.2f}"
                f"{phase_str} (margin: {margin:+.2f}). "
                f"Proceeding with caution - close monitoring recommended."
            )

        elif action == GateAction.REQUEST_HUMAN_REVIEW:
            return (
                f"Confidence {confidence:.2f} slightly below threshold {threshold:.2f}"
                f"{phase_str} (margin: {margin:+.2f}). "
                f"Requesting human review before proceeding."
            )

        elif action == GateAction.REQUIRE_HUMAN_APPROVAL:
            return (
                f"Confidence {confidence:.2f} below threshold {threshold:.2f}"
                f"{phase_str} (margin: {margin:+.2f}). "
                f"Requiring explicit human approval to proceed."
            )

        else:  # BLOCK_EXECUTION
            return (
                f"Confidence {confidence:.2f} significantly below threshold {threshold:.2f}"
                f"{phase_str} (margin: {margin:+.2f}). "
                f"Execution blocked - confidence too low to proceed safely."
            )

    def _log_decision(self, result: GateResult):
        """Log gate decision"""
        if result.allowed:
            log_level = logging.INFO
            status = "ALLOWED"
        else:
            log_level = logging.WARNING
            status = "BLOCKED"

        logger.log(
            log_level,
            f"Murphy Gate {status}: confidence={result.confidence:.2f}, "
            f"threshold={result.threshold:.2f}, margin={result.margin:+.2f}, "
            f"action={result.action.value}"
        )

    def set_phase_threshold(self, phase: Phase, threshold: float):
        """Set custom threshold for a phase"""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")

        self.phase_thresholds[phase] = threshold
        logger.info(f"Set {phase.value} phase threshold to {threshold:.2f}")

    def get_phase_threshold(self, phase: Phase) -> float:
        """Get threshold for a phase"""
        return self.phase_thresholds.get(phase, self.default_threshold)

    def get_all_thresholds(self) -> dict:
        """Get all phase thresholds"""
        return {
            'default': self.default_threshold,
            'phases': {phase.value: threshold for phase, threshold in self.phase_thresholds.items()}
        }
