"""
Risk Bounder
Computes expected loss and enforces risk thresholds
"""

import logging
import math
from typing import Any, Dict, List, Tuple

from .models import ExecutionGraph, ExecutionScope, ExecutionStep

logger = logging.getLogger(__name__)


class RiskBounder:
    """
    Computes expected loss and enforces risk thresholds

    E[Loss] = Σ L_k × p_k

    If above threshold → compilation fails
    """

    def __init__(self):
        # Risk thresholds
        self.max_expected_loss = 0.3  # Maximum acceptable expected loss
        self.max_step_risk = 0.5      # Maximum risk per step

        # Loss magnitudes by step type
        self.step_type_losses = {
            'api_call': 0.3,
            'math_module': 0.1,
            'code_block': 0.4,
            'actuator_command': 0.7,
            'data_transform': 0.2
        }

    def compute_expected_loss(
        self,
        execution_graph: ExecutionGraph,
        scope: ExecutionScope
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Compute expected loss for execution graph

        Args:
            execution_graph: Execution graph
            scope: Execution scope

        Returns:
            (expected_loss, risk_breakdown)
        """
        total_loss = 0.0
        risk_breakdown = []

        for step in execution_graph.steps.values():
            # Calculate step risk
            loss, probability = self._calculate_step_risk(step, scope)
            expected_step_loss = loss * probability

            total_loss += expected_step_loss

            risk_breakdown.append({
                'step_id': step.step_id,
                'step_type': step.step_type.value,
                'loss': loss,
                'probability': probability,
                'expected_loss': expected_step_loss
            })

        return total_loss, risk_breakdown

    def check_risk_threshold(
        self,
        execution_graph: ExecutionGraph,
        scope: ExecutionScope
    ) -> Tuple[bool, float, List[str]]:
        """
        Check if risk is within acceptable threshold

        Args:
            execution_graph: Execution graph
            scope: Execution scope

        Returns:
            (within_threshold, expected_loss, violations)
        """
        violations = []

        # Compute expected loss
        expected_loss, risk_breakdown = self.compute_expected_loss(
            execution_graph,
            scope
        )

        # Check overall threshold
        if expected_loss > self.max_expected_loss:
            violations.append(
                f"Expected loss {expected_loss:.3f} exceeds threshold {self.max_expected_loss}"
            )

        # Check per-step thresholds
        for risk in risk_breakdown:
            if risk['expected_loss'] > self.max_step_risk:
                violations.append(
                    f"Step {risk['step_id']} expected loss {risk['expected_loss']:.3f} "
                    f"exceeds threshold {self.max_step_risk}"
                )

        return len(violations) == 0, expected_loss, violations

    def _calculate_step_risk(
        self,
        step: ExecutionStep,
        scope: ExecutionScope
    ) -> Tuple[float, float]:
        """
        Calculate risk for a single step

        Args:
            step: Execution step
            scope: Execution scope

        Returns:
            (loss_magnitude, failure_probability)
        """
        # Get base loss from step type
        base_loss = self.step_type_losses.get(
            step.step_type.value,
            0.3  # Default
        )

        # Adjust loss based on step characteristics
        loss = self._adjust_loss(step, base_loss)

        # Calculate failure probability
        probability = self._calculate_failure_probability(step, scope)

        return loss, probability

    def _adjust_loss(self, step: ExecutionStep, base_loss: float) -> float:
        """
        Adjust loss based on step characteristics

        Factors:
        - Verified vs unverified
        - Interface binding
        - Reversibility
        """
        loss = base_loss

        # Increase loss for unverified steps
        if not step.verified:
            loss *= 1.5

        # Increase loss for steps without interface binding
        if not step.interface_binding:
            loss *= 1.2

        # Adjust based on metadata
        if 'reversible' in step.metadata:
            if not step.metadata['reversible']:
                loss *= 1.8  # Much higher loss for irreversible actions

        # Clamp to [0, 1]
        return min(1.0, loss)

    def _calculate_failure_probability(
        self,
        step: ExecutionStep,
        scope: ExecutionScope
    ) -> float:
        """
        Calculate failure probability for step

        Factors:
        - Step complexity
        - Dependencies
        - Verification status
        """
        # Base probability
        base_prob = 0.1

        # Increase for complex steps
        if len(step.inputs) > 5:
            base_prob += 0.1

        # Increase for many dependencies
        if len(step.dependencies) > 3:
            base_prob += 0.05 * (len(step.dependencies) - 3)

        # Decrease for verified steps
        if step.verified:
            base_prob *= 0.5

        # Increase for unbound interfaces
        if not step.interface_binding:
            base_prob += 0.2

        # Clamp to [0, 1]
        return min(1.0, base_prob)

    def suggest_risk_mitigations(
        self,
        execution_graph: ExecutionGraph,
        scope: ExecutionScope,
        risk_breakdown: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Suggest mitigations for high-risk steps

        Args:
            execution_graph: Execution graph
            scope: Execution scope
            risk_breakdown: Risk breakdown from compute_expected_loss

        Returns:
            List of mitigation suggestions
        """
        mitigations = []

        # Sort by expected loss (highest first)
        sorted_risks = sorted(
            risk_breakdown,
            key=lambda x: x['expected_loss'],
            reverse=True
        )

        for risk in sorted_risks[:5]:  # Top 5 risky steps
            if risk['expected_loss'] > 0.2:
                step = execution_graph.steps[risk['step_id']]

                suggestions = []

                # Suggest verification
                if not step.verified:
                    suggestions.append("Verify step before execution")

                # Suggest interface binding
                if not step.interface_binding:
                    suggestions.append("Bind to specific interface")

                # Suggest rollback plan
                suggestions.append("Add rollback step")

                # Suggest monitoring
                suggestions.append("Add telemetry monitoring")

                mitigations.append({
                    'step_id': risk['step_id'],
                    'expected_loss': risk['expected_loss'],
                    'suggestions': suggestions
                })

        return mitigations

    def enforce_risk_bounds(
        self,
        execution_graph: ExecutionGraph,
        scope: ExecutionScope
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Enforce risk bounds and return compilation decision

        Args:
            execution_graph: Execution graph
            scope: Execution scope

        Returns:
            (can_compile, risk_report)
        """
        # Compute expected loss
        expected_loss, risk_breakdown = self.compute_expected_loss(
            execution_graph,
            scope
        )

        # Check threshold
        within_threshold, _, violations = self.check_risk_threshold(
            execution_graph,
            scope
        )

        # Get mitigations
        mitigations = self.suggest_risk_mitigations(
            execution_graph,
            scope,
            risk_breakdown
        )

        # Create risk report
        risk_report = {
            'expected_loss': expected_loss,
            'max_allowed_loss': self.max_expected_loss,
            'within_threshold': within_threshold,
            'violations': violations,
            'risk_breakdown': risk_breakdown,
            'mitigations': mitigations,
            'can_compile': within_threshold
        }

        return within_threshold, risk_report
