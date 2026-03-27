"""
Tests for EscalationPolicy (Gap E — escalation wired to control loop).

Proves:
  - EscalationPolicy.should_escalate() returns True when authority insufficient.
  - escalate() resolves to the correct superior in the delegation chain.
  - ControlAuthorityMatrix.check_or_escalate() triggers escalation and resolves.
"""

import os
import unittest


from control_theory.actor_registry import (
    Actor,
    ActorKind,
    ActorRegistry,
    EscalationPolicy,
    EscalationResult,
)
from control_plane.control_loop import ControlAuthorityMatrix


def _make_registry():
    """Build a simple three-actor delegation chain: subordinate → manager → director."""
    registry = ActorRegistry()

    subordinate = Actor(
        actor_id="sub",
        name="Subordinate",
        kind=ActorKind.BOT,
        metadata={"authority": 0.2},
    )
    manager = Actor(
        actor_id="mgr",
        name="Manager",
        kind=ActorKind.HUMAN,
        metadata={"authority": 0.6},
    )
    director = Actor(
        actor_id="dir",
        name="Director",
        kind=ActorKind.HUMAN,
        metadata={"authority": 0.9},
    )
    registry.register(subordinate)
    registry.register(manager)
    registry.register(director)
    # Delegation chain: mgr → sub, dir → mgr
    registry.delegate("mgr", "sub")
    registry.delegate("dir", "mgr")
    return registry


class TestEscalationPolicyCreation(unittest.TestCase):
    def test_valid_creation(self):
        policy = EscalationPolicy(authority_threshold=0.5)
        self.assertEqual(policy.authority_threshold, 0.5)
        self.assertEqual(policy.max_delegation_depth, 5)

    def test_negative_threshold_raises(self):
        with self.assertRaises(ValueError):
            EscalationPolicy(authority_threshold=-0.1)

    def test_zero_max_depth_raises(self):
        with self.assertRaises(ValueError):
            EscalationPolicy(authority_threshold=0.5, max_delegation_depth=0)


class TestShouldEscalate(unittest.TestCase):
    def setUp(self):
        self.policy = EscalationPolicy(authority_threshold=0.5, max_delegation_depth=3)

    def test_sufficient_authority_no_escalation(self):
        """actor with authority >= threshold should NOT escalate."""
        result = self.policy.should_escalate("actor", "execute", current_authority=0.8)
        self.assertFalse(result)

    def test_insufficient_authority_escalates(self):
        """actor with authority < threshold SHOULD escalate."""
        result = self.policy.should_escalate("actor", "execute", current_authority=0.3)
        self.assertTrue(result)

    def test_exactly_at_threshold_no_escalation(self):
        """Exactly at threshold: no escalation needed."""
        result = self.policy.should_escalate("actor", "execute", current_authority=0.5)
        self.assertFalse(result)

    def test_max_depth_forces_escalation(self):
        """At or beyond max depth, escalation is required regardless of authority."""
        result = self.policy.should_escalate(
            "actor", "execute", current_authority=1.0, delegation_depth=3
        )
        self.assertTrue(result)


class TestEscalate(unittest.TestCase):
    def setUp(self):
        self.registry = _make_registry()
        self.policy = EscalationPolicy(authority_threshold=0.5, max_delegation_depth=5)

    def test_escalates_to_manager(self):
        """Subordinate (auth=0.2) escalates; manager (auth=0.6) accepts."""
        result = self.policy.escalate("sub", "execute_action", self.registry)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, EscalationResult)
        self.assertEqual(result.escalated_to, "mgr")
        self.assertGreaterEqual(result.authority_level, 0.5)

    def test_escalation_result_has_reason(self):
        result = self.policy.escalate("sub", "execute_action", self.registry)
        self.assertIsNotNone(result)
        self.assertIsInstance(result.reason, str)
        self.assertGreater(len(result.reason), 0)

    def test_no_superior_returns_none(self):
        """Actor with no superior in the delegation chain gets None."""
        result = self.policy.escalate("dir", "execute_action", self.registry)
        self.assertIsNone(result)

    def test_escalation_skips_insufficient_intermediary(self):
        """If manager also has insufficient authority, escalation finds director."""
        # Override: lower manager's authority below threshold
        registry = ActorRegistry()
        registry.register(Actor("sub", "Sub", ActorKind.BOT, metadata={"authority": 0.1}))
        registry.register(Actor("mgr", "Mgr", ActorKind.HUMAN, metadata={"authority": 0.3}))
        registry.register(Actor("dir", "Dir", ActorKind.HUMAN, metadata={"authority": 0.9}))
        registry.delegate("mgr", "sub")
        registry.delegate("dir", "mgr")

        policy = EscalationPolicy(authority_threshold=0.5, max_delegation_depth=5)
        result = policy.escalate("sub", "execute", registry)
        self.assertIsNotNone(result)
        self.assertEqual(result.escalated_to, "dir")

    def test_custom_authority_fn(self):
        """escalate() uses the optional actor_authority_fn."""
        authority_map = {"mgr": 0.8, "dir": 0.95}

        def my_authority_fn(aid):
            return authority_map.get(aid, 0.0)

        result = self.policy.escalate(
            "sub", "execute", self.registry, actor_authority_fn=my_authority_fn
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.escalated_to, "mgr")
        self.assertAlmostEqual(result.authority_level, 0.8)


class TestControlAuthorityMatrixEscalation(unittest.TestCase):
    """ControlAuthorityMatrix.check_or_escalate() integration."""

    def setUp(self):
        self.registry = _make_registry()
        self.matrix = ControlAuthorityMatrix()
        # Subordinate has authority level 0 (insufficient for execute_action which needs 3)
        self.matrix.register_actor("sub", authority_level=0)
        # Manager has authority level 3
        self.matrix.register_actor("mgr", authority_level=3)

        self.policy = EscalationPolicy(
            authority_threshold=0.5, max_delegation_depth=5
        )

    def test_permitted_actor_returns_true(self):
        """Actor with sufficient authority → True, no escalation."""
        result = self.matrix.check_or_escalate(
            "mgr", "execute_action", self.registry, self.policy
        )
        self.assertTrue(result)

    def test_unpermitted_actor_triggers_escalation(self):
        """Actor without authority → escalation triggered, EscalationResult returned."""
        result = self.matrix.check_or_escalate(
            "sub", "execute_action", self.registry, self.policy
        )
        # Should resolve via escalation (not False)
        self.assertNotEqual(result, False)
        self.assertIsInstance(result, EscalationResult)

    def test_no_policy_returns_false(self):
        """Without escalation policy, unpermitted returns False."""
        result = self.matrix.check_or_escalate(
            "sub", "execute_action"
        )
        self.assertFalse(result)

    def test_escalation_fails_gracefully_when_no_superior(self):
        """When no superior is available, returns False."""
        # Register an isolated actor with no delegation
        self.registry.register(Actor("isolated", "Iso", ActorKind.BOT, metadata={"authority": 0.0}))
        self.matrix.register_actor("isolated", authority_level=0)

        result = self.matrix.check_or_escalate(
            "isolated", "execute_action", self.registry, self.policy
        )
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
