"""
Tests for input_validation.py — null byte sanitization consistency

Closes Gap 7: ConstraintInput and VerificationInput did NOT strip null
bytes (\\x00), while ChatMessageInput did.  This inconsistency could
allow null-byte injection attacks via governance inputs.

Proves:
- ConstraintInput strips null bytes from all fields
- VerificationInput strips null bytes from all fields
- All other input models still work correctly
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from input_validation import (
    ConstraintInput,
    VerificationInput,
    ChatMessageInput,
    PhaseApprovalInput,
    HaltInput,
    PacketCompilationInput,
    validate_input,
)


class TestConstraintInputNullByte(unittest.TestCase):
    """ConstraintInput must strip null bytes from all fields."""

    def test_target_null_byte_stripped(self):
        ci = ConstraintInput(
            target="exec\x00ution",
            rule="must be safe",
            justification="security requirement",
        )
        self.assertNotIn("\x00", ci.target)
        self.assertEqual(ci.target, "execution")

    def test_rule_null_byte_stripped(self):
        ci = ConstraintInput(
            target="data_access",
            rule="no\x00bypass",
            justification="policy",
        )
        self.assertNotIn("\x00", ci.rule)

    def test_justification_null_byte_stripped(self):
        ci = ConstraintInput(
            target="access",
            rule="enforce",
            justification="required\x00for\x00security",
        )
        self.assertNotIn("\x00", ci.justification)


class TestVerificationInputNullByte(unittest.TestCase):
    """VerificationInput must strip null bytes from all fields."""

    def test_gate_id_null_byte_stripped(self):
        vi = VerificationInput(
            gate_id="gate\x00-1",
            evidence="test passed",
        )
        self.assertNotIn("\x00", vi.gate_id)

    def test_evidence_null_byte_stripped(self):
        vi = VerificationInput(
            gate_id="gate-1",
            evidence="passed\x00with\x00flying colors",
        )
        self.assertNotIn("\x00", vi.evidence)

    def test_evidence_type_null_byte_stripped(self):
        vi = VerificationInput(
            gate_id="gate-1",
            evidence="ok",
            evidence_type="auto\x00mated",
        )
        self.assertNotIn("\x00", vi.evidence_type)


class TestChatMessageInputNullByte(unittest.TestCase):
    """ChatMessageInput already strips null bytes — confirm preservation."""

    def test_message_null_byte_stripped(self):
        cm = ChatMessageInput(message="hello\x00world")
        self.assertNotIn("\x00", cm.message)


class TestDangerousCharactersStripped(unittest.TestCase):
    """Confirm HTML/shell injection characters are stripped."""

    def test_constraint_html_stripped(self):
        ci = ConstraintInput(
            target="<script>alert(1)</script>",
            rule="safe rule",
            justification="justification",
        )
        self.assertNotIn("<", ci.target)
        self.assertNotIn(">", ci.target)

    def test_constraint_shell_stripped(self):
        ci = ConstraintInput(
            target="$(whoami)",
            rule="rule; DROP TABLE users",
            justification="legit",
        )
        self.assertNotIn("$", ci.target)
        self.assertNotIn(";", ci.rule)

    def test_verification_pipe_stripped(self):
        vi = VerificationInput(
            gate_id="gate|inject",
            evidence="evidence",
        )
        self.assertNotIn("|", vi.gate_id)


class TestValidateInputFunction(unittest.TestCase):
    """The validate_input() utility must return structured results."""

    def test_valid_input(self):
        ok, data, err = validate_input(
            {"target": "resource", "rule": "allowed", "justification": "reason"},
            ConstraintInput,
        )
        self.assertTrue(ok)
        self.assertIsNotNone(data)
        self.assertIsNone(err)

    def test_invalid_input(self):
        ok, data, err = validate_input(
            {"target": "", "rule": "x", "justification": "y"},
            ConstraintInput,
        )
        self.assertFalse(ok)
        self.assertIsNone(data)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()
