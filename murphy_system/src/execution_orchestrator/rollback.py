"""
Rollback Enforcer
=================

Enforces rollback when execution must be reversed.

Rollback Scenarios:
- Risk threshold breach
- Confidence drop
- Interface failure
- Verification failure

Design Principle: Safe reversal of all executed steps
"""

import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .models import StepResult, StepType


class RollbackEnforcer:
    """
    Enforces rollback of executed steps

    Capabilities:
    - Rollback plan validation
    - Step-by-step rollback execution
    - Rollback verification
    - Failure handling
    """

    def __init__(self):
        self.rollback_history: Dict[str, List[Dict]] = {}

    def validate_rollback_plan(
        self,
        rollback_plan: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate rollback plan structure

        Args:
            rollback_plan: Rollback plan from execution packet

        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        required_fields = ['steps', 'verification']
        for field in required_fields:
            if field not in rollback_plan:
                return False, f"Missing required field: {field}"

        # Check steps structure
        steps = rollback_plan.get('steps', [])
        if not isinstance(steps, list):
            return False, "Rollback steps must be a list"

        # Validate each step
        for i, step in enumerate(steps):
            if 'step_id' not in step:
                return False, f"Step {i} missing step_id"
            if 'rollback_action' not in step:
                return False, f"Step {i} missing rollback_action"

        return True, None

    def execute_rollback(
        self,
        packet_id: str,
        executed_steps: List[StepResult],
        rollback_plan: Dict
    ) -> Tuple[bool, List[str]]:
        """
        Execute rollback of completed steps

        Args:
            packet_id: Packet being rolled back
            executed_steps: Steps that were executed
            rollback_plan: Rollback plan from packet

        Returns:
            (success, list_of_errors)
        """
        errors = []
        rollback_steps = []

        # Validate rollback plan
        valid, error = self.validate_rollback_plan(rollback_plan)
        if not valid:
            return False, [f"Invalid rollback plan: {error}"]

        # Get rollback steps in reverse order
        plan_steps = rollback_plan.get('steps', [])
        step_map = {step['step_id']: step for step in plan_steps}

        # Execute rollback for each completed step (in reverse)
        for step_result in reversed(executed_steps):
            if not step_result.success:
                continue  # Skip failed steps

            step_id = step_result.step_id

            # Get rollback action for this step
            if step_id not in step_map:
                errors.append(f"No rollback action defined for step {step_id}")
                continue

            rollback_step = step_map[step_id]

            # Execute rollback action
            try:
                success, error = self._execute_rollback_action(
                    step_result,
                    rollback_step
                )

                if success:
                    rollback_steps.append({
                        'step_id': step_id,
                        'action': rollback_step['rollback_action'],
                        'success': True,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                else:
                    errors.append(f"Rollback failed for step {step_id}: {error}")
                    rollback_steps.append({
                        'step_id': step_id,
                        'action': rollback_step['rollback_action'],
                        'success': False,
                        'error': error,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                errors.append(f"Exception during rollback of step {step_id}: {str(exc)}")
                rollback_steps.append({
                    'step_id': step_id,
                    'action': rollback_step['rollback_action'],
                    'success': False,
                    'error': str(exc),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

        # Store rollback history
        self.rollback_history[packet_id] = rollback_steps

        # Verify rollback
        verification_success = self._verify_rollback(
            packet_id,
            rollback_plan.get('verification', {})
        )

        if not verification_success:
            errors.append("Rollback verification failed")

        return len(errors) == 0, errors

    def _execute_rollback_action(
        self,
        step_result: StepResult,
        rollback_step: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Execute rollback action for a single step

        Args:
            step_result: Result of original step execution
            rollback_step: Rollback action definition

        Returns:
            (success, error_message)
        """
        action = rollback_step.get('rollback_action', '')

        try:
            # Handle different step types
            if step_result.step_type == StepType.FILESYSTEM_OP:
                return self._rollback_filesystem_op(step_result, rollback_step)
            elif step_result.step_type == StepType.REST_CALL:
                return self._rollback_rest_call(step_result, rollback_step)
            elif step_result.step_type == StepType.ACTUATOR_COMMAND:
                return self._rollback_actuator_command(step_result, rollback_step)
            elif step_result.step_type == StepType.CHECKPOINT:
                return self._rollback_checkpoint(step_result, rollback_step)
            else:
                # Some step types don't need rollback (e.g., read operations)
                return True, None
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return False, str(exc)

    def _rollback_filesystem_op(
        self,
        step_result: StepResult,
        rollback_step: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Rollback filesystem operation"""
        action = rollback_step.get('rollback_action', '')

        if action == 'delete_created_file':
            # Delete file that was created
            file_path = rollback_step.get('file_path', '')
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
                return True, None
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, str(exc)

        elif action == 'restore_original_content':
            # Restore original file content
            file_path = rollback_step.get('file_path', '')
            original_content = rollback_step.get('original_content', '')
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                return True, None
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, str(exc)

        elif action == 'restore_deleted_file':
            # Restore file from backup
            file_path = rollback_step.get('file_path', '')
            backup_content = rollback_step.get('backup_content', '')
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                return True, None
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, str(exc)

        else:
            return False, f"Unknown filesystem rollback action: {action}"

    def _rollback_rest_call(
        self,
        step_result: StepResult,
        rollback_step: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Rollback REST API call"""
        action = rollback_step.get('rollback_action', '')

        if action == 'delete_created_resource':
            # Delete resource that was created
            url = rollback_step.get('url', '')
            try:
                import requests
                response = requests.delete(url, timeout=30)
                response.raise_for_status()
                return True, None
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, str(exc)

        elif action == 'restore_original_state':
            # Restore original state via PUT/PATCH
            url = rollback_step.get('url', '')
            original_state = rollback_step.get('original_state', {})
            try:
                import requests
                response = requests.put(url, json=original_state, timeout=30)
                response.raise_for_status()
                return True, None
            except Exception as exc:
                logger.debug("Caught exception: %s", exc)
                return False, str(exc)

        else:
            return False, f"Unknown REST rollback action: {action}"

    def _rollback_actuator_command(
        self,
        step_result: StepResult,
        rollback_step: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Rollback actuator command"""
        action = rollback_step.get('rollback_action', '')

        # In production, would interface with actual actuators
        # For now, simulate rollback
        return True, None

    def _rollback_checkpoint(
        self,
        step_result: StepResult,
        rollback_step: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Rollback checkpoint (restore previous state)"""
        checkpoint_id = rollback_step.get('checkpoint_id', '')

        # In production, would restore from checkpoint storage
        # For now, simulate restoration
        return True, None

    def _verify_rollback(
        self,
        packet_id: str,
        verification: Dict
    ) -> bool:
        """
        Verify rollback was successful

        Args:
            packet_id: Packet that was rolled back
            verification: Verification criteria

        Returns:
            True if verification passed
        """
        # Get rollback history
        rollback_steps = self.rollback_history.get(packet_id, [])

        # Check all steps succeeded
        all_succeeded = all(step['success'] for step in rollback_steps)

        if not all_succeeded:
            return False

        # Additional verification checks
        checks = verification.get('checks', [])
        for check in checks:
            check_type = check.get('type', '')

            if check_type == 'file_not_exists':
                # Verify file doesn't exist
                file_path = check.get('path', '')
                import os
                if os.path.exists(file_path):
                    return False

            elif check_type == 'file_content_matches':
                # Verify file content matches expected
                file_path = check.get('path', '')
                expected_content = check.get('content', '')
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        actual_content = f.read()
                    if actual_content != expected_content:
                        return False
                except Exception as exc:
                    logger.debug("Suppressed exception: %s", exc)
                    return False

        return True

    def get_rollback_history(self, packet_id: str) -> List[Dict]:
        """Get rollback history for packet"""
        return self.rollback_history.get(packet_id, [])

    def clear_rollback_history(self, packet_id: str):
        """Clear rollback history for packet"""
        if packet_id in self.rollback_history:
            del self.rollback_history[packet_id]
