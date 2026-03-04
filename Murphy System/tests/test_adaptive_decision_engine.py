"""
Tests for Adaptive Decision Engine components

Tests:
- Adaptive decision engine functionality
- Decision history tracking
- Policy management
- Decision making
- Policy adaptation
"""

import unittest
import time
from datetime import datetime
from src.learning_engine import (
    AdaptiveDecisionEngine,
    DecisionHistory,
    PolicyManager,
    AdaptiveDecision,
    DecisionPolicy
)


class TestDecisionHistory(unittest.TestCase):
    """Test decision history functionality"""

    def setUp(self):
        self.history = DecisionHistory(max_history_size=100)

    def test_record_outcome(self):
        """Test recording decision outcomes"""
        from src.learning_engine.adaptive_decision_engine import DecisionOutcome

        outcome = DecisionOutcome(
            decision_id="dec_1",
            decision_type="task_execution",
            action="execute_immediately",
            success=True,
            confidence=0.9,
            utility=0.8,
            timestamp=datetime.now(),
            context={},
            metadata={}
        )

        self.history.record_outcome(outcome)

        # Verify recorded
        outcomes = self.history.get_outcomes_by_type("task_execution")
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].decision_id, "dec_1")

    def test_get_outcomes_by_type(self):
        """Test retrieving outcomes by decision type"""
        from src.learning_engine.adaptive_decision_engine import DecisionOutcome

        # Record outcomes of different types
        for i in range(5):
            outcome = DecisionOutcome(
                decision_id=f"dec_{i}",
                decision_type="task_execution",
                action="execute_immediately",
                success=True,
                confidence=0.8,
                utility=0.7,
                timestamp=datetime.now(),
                context={},
                metadata={}
            )
            self.history.record_outcome(outcome)

        for i in range(5, 10):
            outcome = DecisionOutcome(
                decision_id=f"dec_{i}",
                decision_type="workflow_branch",
                action="take_branch_a",
                success=True,
                confidence=0.8,
                utility=0.7,
                timestamp=datetime.now(),
                context={},
                metadata={}
            )
            self.history.record_outcome(outcome)

        # Get task execution outcomes
        task_outcomes = self.history.get_outcomes_by_type("task_execution")

        self.assertEqual(len(task_outcomes), 5)

    def test_get_action_statistics(self):
        """Test getting statistics for an action"""
        from src.learning_engine.adaptive_decision_engine import DecisionOutcome

        # Record outcomes for same action
        utilities = [0.8, 0.7, 0.9, 0.6, 0.85]
        for i, utility in enumerate(utilities):
            outcome = DecisionOutcome(
                decision_id=f"dec_{i}",
                decision_type="task_execution",
                action="execute_immediately",
                success=i < 4,  # 4 successes, 1 failure
                confidence=0.8,
                utility=utility,
                timestamp=datetime.now(),
                context={},
                metadata={}
            )
            self.history.record_outcome(outcome)

        # Get statistics
        stats = self.history.get_action_statistics("execute_immediately")

        self.assertEqual(stats['count'], 5)
        self.assertEqual(stats['success_rate'], 0.8)
        self.assertAlmostEqual(stats['average_utility'], 0.77, places=1)


class TestPolicyManager(unittest.TestCase):
    """Test policy manager functionality"""

    def setUp(self):
        self.manager = PolicyManager()

    def test_create_policy(self):
        """Test creating a policy"""
        policy = self.manager.create_policy(
            policy_name="test_policy",
            decision_type="test_decision",
            actions=["option_a", "option_b", "option_c"],
            policy_type="adaptive",
            exploration_rate=0.1
        )

        self.assertEqual(policy.policy_name, "test_policy")
        self.assertEqual(policy.decision_type, "test_decision")
        self.assertEqual(len(policy.actions), 3)
        self.assertEqual(policy.exploration_rate, 0.1)
        self.assertEqual(policy.total_decisions, 0)

    def test_get_policy(self):
        """Test retrieving a policy"""
        policy = self.manager.create_policy(
            policy_name="test_policy",
            decision_type="test_decision",
            actions=["option_a", "option_b"],
            policy_type="adaptive"
        )

        retrieved = self.manager.get_policy(policy.policy_id)

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.policy_id, policy.policy_id)

    def test_update_policy(self):
        """Test updating policy based on outcomes"""
        policy = self.manager.create_policy(
            policy_name="test_policy",
            decision_type="test_decision",
            actions=["option_a", "option_b"],
            policy_type="adaptive"
        )

        # Update policy with successful outcome
        self.manager.update_policy(
            policy_id=policy.policy_id,
            action="option_a",
            success=True,
            utility=0.9
        )

        # Verify update
        updated_policy = self.manager.get_policy(policy.policy_id)
        self.assertEqual(updated_policy.total_decisions, 1)
        self.assertEqual(updated_policy.total_successes, 1)
        self.assertGreater(updated_policy.action_utilities["option_a"], 0.5)

    def test_select_action_deterministic(self):
        """Test selecting action with deterministic policy"""
        policy = self.manager.create_policy(
            policy_name="test_policy",
            decision_type="test_decision",
            actions=["option_a", "option_b", "option_c"],
            policy_type="deterministic"
        )

        # Set utilities
        policy.action_utilities["option_a"] = 0.6
        policy.action_utilities["option_b"] = 0.8
        policy.action_utilities["option_c"] = 0.7

        # Select action - should choose highest utility
        action, utility = self.manager.select_action(policy.policy_id)

        self.assertEqual(action, "option_b")
        self.assertEqual(utility, 0.8)

    def test_select_action_adaptive(self):
        """Test selecting action with adaptive policy"""
        policy = self.manager.create_policy(
            policy_name="test_policy",
            decision_type="test_decision",
            actions=["option_a", "option_b"],
            policy_type="adaptive",
            exploration_rate=0.0  # No exploration for testing
        )

        # Set utilities
        policy.action_utilities["option_a"] = 0.9
        policy.action_utilities["option_b"] = 0.7

        # Select action - should choose best (no exploration)
        action, utility = self.manager.select_action(policy.policy_id)

        self.assertEqual(action, "option_a")
        self.assertEqual(utility, 0.9)


class TestAdaptiveDecisionEngine(unittest.TestCase):
    """Test adaptive decision engine functionality"""

    def setUp(self):
        self.engine = AdaptiveDecisionEngine(enable_adaptation=True)

    def test_make_decision(self):
        """Test making a decision"""
        decision = self.engine.make_decision(
            decision_type="task_execution",
            context={'task_id': 'task_1'}
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.decision_type, "task_execution")
        self.assertIsNotNone(decision.selected_action)
        self.assertGreater(decision.confidence, 0.0)
        self.assertLessEqual(decision.confidence, 1.0)
        self.assertIsNotNone(decision.rationale)
        self.assertIsNotNone(decision.policy_used)

    def test_adaptation_disabled(self):
        """Test behavior when adaptation is disabled"""
        engine = AdaptiveDecisionEngine(enable_adaptation=False)

        decision = engine.make_decision(
            decision_type="task_execution"
        )

        self.assertEqual(decision.selected_action, "default")
        self.assertEqual(decision.confidence, 0.5)
        self.assertIn("Adaptation disabled", decision.rationale)

    def test_record_outcome(self):
        """Test recording decision outcome"""
        decision = self.engine.make_decision(
            decision_type="task_execution"
        )

        # Record outcome
        self.engine.record_outcome(
            decision=decision,
            success=True,
            confidence=0.9,
            utility=0.8,
            context={'result': 'success'}
        )

        # Verify recorded
        stats = self.engine.get_decision_statistics("task_execution")

        self.assertEqual(stats['total_decisions'], 1)

    def test_get_decision_statistics(self):
        """Test getting decision statistics"""
        # Make some decisions and record outcomes
        for i in range(10):
            decision = self.engine.make_decision(
                decision_type="task_execution"
            )

            self.engine.record_outcome(
                decision=decision,
                success=i < 8,  # 80% success rate
                confidence=0.8,
                utility=0.7 + (i % 3) * 0.1
            )

        # Get statistics
        stats = self.engine.get_decision_statistics("task_execution")

        self.assertEqual(stats['total_decisions'], 10)
        self.assertAlmostEqual(stats['success_rate'], 0.8, places=1)
        self.assertGreater(stats['average_utility'], 0.0)
        self.assertIn('by_action', stats)

    def test_get_policy_status(self):
        """Test getting policy status"""
        policy_id = "task_execution_task_execution"
        status = self.engine.get_policy_status(policy_id)

        self.assertIsNotNone(status)
        self.assertEqual(status['policy_id'], policy_id)
        self.assertEqual(status['decision_type'], "task_execution")
        self.assertIn('actions', status)
        self.assertIn('action_utilities', status)

    def test_get_all_policies(self):
        """Test getting all policies"""
        policies = self.engine.get_all_policies()

        self.assertGreater(len(policies), 0)
        self.assertTrue(all('policy_id' in p for p in policies))

    def test_exploration_rate_decrease(self):
        """Test that exploration rate decreases over time"""
        policy_id = "task_execution_task_execution"

        # Get initial exploration rate
        initial_policy = self.engine.get_policy_status(policy_id)
        initial_rate = initial_policy['exploration_rate']

        # Make many decisions
        for i in range(100):
            decision = self.engine.make_decision(
                decision_type="task_execution"
            )

            self.engine.record_outcome(
                decision=decision,
                success=True,
                confidence=0.8,
                utility=0.8
            )

        # Get final exploration rate
        final_policy = self.engine.get_policy_status(policy_id)
        final_rate = final_policy['exploration_rate']

        # Should have decreased
        self.assertLess(final_rate, initial_rate)

    def test_reset_learning(self):
        """Test resetting learning data"""
        # Make some decisions
        for i in range(10):
            decision = self.engine.make_decision(
                decision_type="task_execution"
            )

            self.engine.record_outcome(
                decision=decision,
                success=True,
                confidence=0.8,
                utility=0.8
            )

        # Reset
        self.engine.reset_learning()

        # Verify reset
        stats = self.engine.get_decision_statistics()

        self.assertEqual(stats['total_decisions'], 0)

    def test_export_decision_data(self):
        """Test exporting decision data"""
        # Make some decisions
        for i in range(10):
            decision = self.engine.make_decision(
                decision_type="task_execution"
            )

            self.engine.record_outcome(
                decision=decision,
                success=True,
                confidence=0.8,
                utility=0.8
            )

        # Export data
        exported = self.engine.export_decision_data()

        # Should contain all sections
        self.assertIn('statistics', exported)
        self.assertIn('policies', exported)


class TestAdaptiveDecisionEngineIntegration(unittest.TestCase):
    """Integration tests for adaptive decision engine"""

    def test_full_decision_cycle(self):
        """Test complete decision cycle"""
        engine = AdaptiveDecisionEngine(enable_adaptation=True)

        # Step 1: Make decisions
        decisions = []
        for i in range(50):
            decision = engine.make_decision(
                decision_type="task_execution",
                context={'task_id': f'task_{i}'}
            )
            decisions.append(decision)

        # Step 2: Record outcomes with varying success
        for i, decision in enumerate(decisions):
            success = i % 5 != 0  # 80% success rate
            utility = 0.9 if success else -0.5

            engine.record_outcome(
                decision=decision,
                success=success,
                confidence=0.8,
                utility=utility,
                context={'duration': 1.0 + i * 0.01}
            )

        # Step 3: Get statistics
        stats = engine.get_decision_statistics("task_execution")

        # Step 4: Get policy status
        policy_status = engine.get_policy_status("task_execution_task_execution")

        # Step 5: Get all policies
        all_policies = engine.get_all_policies()

        # Verify learning occurred
        self.assertEqual(stats['total_decisions'], 50)
        self.assertAlmostEqual(stats['success_rate'], 0.8, places=1)
        self.assertGreater(policy_status['total_decisions'], 0)
        self.assertGreater(len(all_policies), 0)

        # Step 6: Export and verify
        exported = engine.export_decision_data()
        self.assertIn('statistics', exported)
        self.assertIn('policies', exported)
        self.assertEqual(exported['statistics']['total_decisions'], 50)


if __name__ == '__main__':
    unittest.main()
