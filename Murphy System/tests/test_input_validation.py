"""
Test Suite for Input Validation
Tests all validation schemas and security measures
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from input_validation import (
    ChatMessageInput, ConstraintInput, VerificationInput,
    PhaseApprovalInput, HaltInput, PacketCompilationInput,
    validate_input
)
from pydantic import ValidationError


class TestChatMessageInput:
    """Test ChatMessageInput validation"""

    def test_valid_message(self):
        """Test valid chat message"""
        valid, data, error = validate_input(
            {'message': 'Hello, how are you?', 'conversation_id': 'test-123'},
            ChatMessageInput
        )

        assert valid is True
        assert data.message == 'Hello, how are you?'
        assert data.conversation_id == 'test-123'
        assert error is None

    def test_empty_message(self):
        """Test empty message is rejected"""
        valid, data, error = validate_input(
            {'message': '', 'conversation_id': 'test'},
            ChatMessageInput
        )

        assert valid is False
        assert data is None
        assert 'cannot be empty' in error.lower() or 'at least 1 character' in error.lower()

    def test_script_tag_blocked(self):
        """Test script tags are blocked"""
        valid, data, error = validate_input(
            {'message': '<script>alert(1)</script>'},
            ChatMessageInput
        )

        assert valid is False
        assert '<script' in error.lower()

    def test_iframe_blocked(self):
        """Test iframe tags are blocked"""
        valid, data, error = validate_input(
            {'message': '<iframe src="evil.com"></iframe>'},
            ChatMessageInput
        )

        assert valid is False
        assert 'dangerous content' in error.lower()

    def test_javascript_protocol_blocked(self):
        """Test javascript: protocol is blocked"""
        valid, data, error = validate_input(
            {'message': 'Click <a href="javascript:alert(1)">here</a>'},
            ChatMessageInput
        )

        assert valid is False
        assert 'javascript:' in error.lower()

    def test_conversation_id_sanitization(self):
        """Test conversation ID is sanitized"""
        valid, data, error = validate_input(
            {'message': 'Hello', 'conversation_id': 'test-<script>-123'},
            ChatMessageInput
        )

        assert valid is True
        # Special characters should be removed
        assert '<' not in data.conversation_id
        assert '>' not in data.conversation_id

    def test_long_message(self):
        """Test very long messages"""
        long_message = 'A' * 10001  # Over 10000 char limit
        valid, data, error = validate_input(
            {'message': long_message},
            ChatMessageInput
        )

        assert valid is False
        assert 'max_length' in error.lower() or 'too long' in error.lower() or 'at most' in error.lower()


class TestConstraintInput:
    """Test ConstraintInput validation"""

    def test_valid_constraint(self):
        """Test valid constraint"""
        valid, data, error = validate_input(
            {
                'target': 'execution',
                'rule': 'confidence >= 0.85',
                'justification': 'Ensure high confidence before execution'
            },
            ConstraintInput
        )

        assert valid is True
        assert data.target == 'execution'
        assert data.rule == 'confidence = 0.85'  # >= becomes =
        assert error is None

    def test_sql_injection_sanitized(self):
        """Test SQL injection is sanitized"""
        valid, data, error = validate_input(
            {
                'target': 'database',
                'rule': 'DROP TABLE users; --',
                'justification': 'test'
            },
            ConstraintInput
        )

        assert valid is True
        # SQL keywords should be removed
        assert 'DROP' not in data.rule.upper()
        assert 'TABLE' not in data.rule.upper()
        assert '--' not in data.rule

    def test_dangerous_characters_removed(self):
        """Test dangerous characters are removed"""
        valid, data, error = validate_input(
            {
                'target': 'test<script>',
                'rule': 'value > 0 && echo "test"',
                'justification': 'test | cat /etc/passwd'
            },
            ConstraintInput
        )

        assert valid is True
        assert '<' not in data.target
        assert '>' not in data.target
        assert '&' not in data.rule
        assert '|' not in data.justification

    def test_empty_rule_rejected(self):
        """Test empty rule after sanitization is rejected"""
        valid, data, error = validate_input(
            {
                'target': 'test',
                'rule': ';;;',  # Only dangerous chars
                'justification': 'test'
            },
            ConstraintInput
        )

        assert valid is False
        assert 'empty' in error.lower()

    def test_length_limits(self):
        """Test length limits are enforced"""
        valid, data, error = validate_input(
            {
                'target': 'A' * 501,  # Over 500 char limit
                'rule': 'test',
                'justification': 'test'
            },
            ConstraintInput
        )

        assert valid is False


class TestVerificationInput:
    """Test VerificationInput validation"""

    def test_valid_verification(self):
        """Test valid verification"""
        valid, data, error = validate_input(
            {
                'gate_id': 'gate-123',
                'evidence': 'Test passed successfully',
                'evidence_type': 'test_result'
            },
            VerificationInput
        )

        assert valid is True
        assert data.gate_id == 'gate-123'
        assert data.evidence == 'Test passed successfully'
        assert data.evidence_type == 'test_result'

    def test_default_evidence_type(self):
        """Test default evidence type"""
        valid, data, error = validate_input(
            {
                'gate_id': 'gate-123',
                'evidence': 'Manual verification'
            },
            VerificationInput
        )

        assert valid is True
        assert data.evidence_type == 'manual'


class TestPhaseApprovalInput:
    """Test PhaseApprovalInput validation"""

    def test_valid_approval(self):
        """Test valid phase approval"""
        valid, data, error = validate_input(
            {
                'phase': 'execute',
                'approver': 'John Doe',
                'signature': 'sig-12345',
                'notes': 'Approved after review'
            },
            PhaseApprovalInput
        )

        assert valid is True
        assert data.phase == 'execute'
        assert data.approver == 'John Doe'

    def test_invalid_phase(self):
        """Test invalid phase is rejected"""
        valid, data, error = validate_input(
            {
                'phase': 'invalid_phase',
                'approver': 'John Doe'
            },
            PhaseApprovalInput
        )

        assert valid is False
        assert 'invalid phase' in error.lower()

    def test_valid_phases(self):
        """Test all valid phases"""
        valid_phases = ['intake', 'expansion', 'synthesis', 'execute', 'verify']

        for phase in valid_phases:
            valid, data, error = validate_input(
                {'phase': phase, 'approver': 'Test'},
                PhaseApprovalInput
            )
            assert valid is True
            assert data.phase == phase


class TestHaltInput:
    """Test HaltInput validation"""

    def test_valid_halt(self):
        """Test valid halt request"""
        valid, data, error = validate_input(
            {
                'reason': 'Critical security issue detected in production',
                'severity': 'critical',
                'requester': 'Security Team'
            },
            HaltInput
        )

        assert valid is True
        assert data.reason == 'Critical security issue detected in production'
        assert data.severity == 'critical'

    def test_reason_too_short(self):
        """Test reason must be at least 10 characters"""
        valid, data, error = validate_input(
            {
                'reason': 'Short',
                'severity': 'high'
            },
            HaltInput
        )

        assert valid is False
        assert 'min_length' in error.lower() or 'at least' in error.lower()

    def test_invalid_severity(self):
        """Test invalid severity is rejected"""
        valid, data, error = validate_input(
            {
                'reason': 'This is a valid reason that is long enough',
                'severity': 'super_critical'
            },
            HaltInput
        )

        assert valid is False
        assert 'invalid severity' in error.lower()

    def test_valid_severities(self):
        """Test all valid severities"""
        valid_severities = ['low', 'medium', 'high', 'critical']

        for severity in valid_severities:
            valid, data, error = validate_input(
                {
                    'reason': 'This is a valid reason that is long enough',
                    'severity': severity
                },
                HaltInput
            )
            assert valid is True
            assert data.severity == severity


class TestPacketCompilationInput:
    """Test PacketCompilationInput validation"""

    def test_valid_compilation(self):
        """Test valid packet compilation request"""
        valid, data, error = validate_input(
            {
                'task_description': 'Create a web application for task management',
                'force_compile': False
            },
            PacketCompilationInput
        )

        assert valid is True
        assert 'web application' in data.task_description
        assert data.force_compile is False

    def test_task_too_short(self):
        """Test task description must be at least 10 characters"""
        valid, data, error = validate_input(
            {
                'task_description': 'Short'
            },
            PacketCompilationInput
        )

        assert valid is False


class TestSecurityPatterns:
    """Test various security attack patterns"""

    def test_path_traversal_blocked(self):
        """Test path traversal is blocked"""
        valid, data, error = validate_input(
            {
                'target': '../../../etc/passwd',
                'rule': 'test',
                'justification': 'test'
            },
            ConstraintInput
        )

        assert valid is True
        assert '../' not in data.target

    def test_command_injection_blocked(self):
        """Test command injection is blocked"""
        valid, data, error = validate_input(
            {
                'target': 'test',
                'rule': 'value > 0; rm -rf /',
                'justification': 'test'
            },
            ConstraintInput
        )

        assert valid is True
        assert ';' not in data.rule

    def test_xss_patterns_blocked(self):
        """Test XSS patterns are blocked"""
        xss_patterns = [
            '<script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            '<iframe src="javascript:alert(1)">',
            'javascript:alert(1)'
        ]

        for pattern in xss_patterns:
            valid, data, error = validate_input(
                {'message': pattern},
                ChatMessageInput
            )
            assert valid is False, f"XSS pattern should be blocked: {pattern}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
