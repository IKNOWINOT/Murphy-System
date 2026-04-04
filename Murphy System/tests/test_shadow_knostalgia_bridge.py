"""Tests for the Shadow-Knostalgia Bridge module."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.shadow_knostalgia_bridge import ShadowKnostalgiaBridge, ObservationMemory
from src.kfactor_calculator import KFactorCalculator
from src.dynamic_assist_engine import DynamicAssistEngine


class MockKnostalgiaEngine:
    """Mock KnostalgiaEngine for testing."""
    def __init__(self):
        self.memories = {}
        self.confirmed = []
        self.rejected = []
        self.impact_updates = []

    def store(self, content, weight, metadata=None):
        mem_id = f"mem-{len(self.memories)}"
        self.memories[mem_id] = {"content": content, "weight": weight, "metadata": metadata}
        return mem_id

    def recall(self, query, context=None):
        for mem_id, mem in self.memories.items():
            if query.lower() in mem["content"].lower():
                return {"content": mem["content"]}
        return None

    def score_impact(self, memory_id, efficiency_delta, profit_delta):
        self.impact_updates.append({
            "memory_id": memory_id,
            "efficiency_delta": efficiency_delta,
            "profit_delta": profit_delta,
        })
        if memory_id in self.memories:
            reward = max(0.0, min(1.0, (efficiency_delta + profit_delta) / 2.0))
            self.memories[memory_id]["weight"] = reward

    def on_recall_confirmed(self, memory_id):
        self.confirmed.append(memory_id)

    def on_recall_rejected(self, memory_id):
        self.rejected.append(memory_id)


@pytest.fixture
def mock_knostalgia():
    return MockKnostalgiaEngine()


@pytest.fixture
def bridge(mock_knostalgia):
    return ShadowKnostalgiaBridge(
        knostalgia_engine=mock_knostalgia,
        kfactor_calculator=KFactorCalculator(),
        dynamic_assist_engine=DynamicAssistEngine(),
    )


@pytest.fixture
def bridge_no_knostalgia():
    return ShadowKnostalgiaBridge(
        knostalgia_engine=None,
        kfactor_calculator=KFactorCalculator(),
        dynamic_assist_engine=DynamicAssistEngine(),
    )


class TestRecordObservation:
    def test_creates_observation_memory(self, bridge):
        obs = bridge.record_observation(
            shadow_agent_id="agent-1",
            process_name="invoice_approval",
            action_observed="Approved invoice #123",
            variation_from_norm=False,
        )
        assert isinstance(obs, ObservationMemory)
        assert obs.shadow_agent_id == "agent-1"
        assert obs.process_name == "invoice_approval"
        assert obs.outcome_measured is False
        assert obs.efficiency_delta == 0.0

    def test_creates_knostalgia_memory(self, bridge, mock_knostalgia):
        obs = bridge.record_observation(
            shadow_agent_id="agent-1",
            process_name="scheduling",
            action_observed="Scheduled meeting at 3pm",
            variation_from_norm=False,
        )
        assert obs.memory_id is not None
        assert obs.memory_id in mock_knostalgia.memories

    def test_observation_id_is_unique(self, bridge):
        obs1 = bridge.record_observation("a1", "proc", "action 1", False)
        obs2 = bridge.record_observation("a1", "proc", "action 2", False)
        assert obs1.observation_id != obs2.observation_id

    def test_graceful_degradation_without_knostalgia(self, bridge_no_knostalgia):
        obs = bridge_no_knostalgia.record_observation(
            "agent-1", "process", "some action", False
        )
        assert obs.memory_id is not None
        assert obs.observation_id is not None


class TestRecordOutcome:
    def test_assigns_impact_weight(self, bridge):
        obs = bridge.record_observation("a1", "proc", "action", False)
        reward = bridge.record_outcome(obs.observation_id, 0.6, 0.8)
        assert reward > 0.0
        assert reward <= 1.0

    def test_calls_score_impact(self, bridge, mock_knostalgia):
        obs = bridge.record_observation("a1", "proc", "action", False)
        bridge.record_outcome(obs.observation_id, 0.5, 0.7)
        assert len(mock_knostalgia.impact_updates) == 1
        assert mock_knostalgia.impact_updates[0]["memory_id"] == obs.memory_id

    def test_unknown_observation_returns_zero(self, bridge):
        reward = bridge.record_outcome("nonexistent-id", 0.5, 0.5)
        assert reward == 0.0

    def test_marks_outcome_measured(self, bridge):
        obs = bridge.record_observation("a1", "proc", "action", False)
        bridge.record_outcome(obs.observation_id, 0.4, 0.6)
        # Retrieve obs from internal dict
        stored = bridge._observations[obs.observation_id]
        assert stored.outcome_measured is True


class TestGenerateProcessQuestion:
    def test_uses_knostalgia_recall(self, bridge, mock_knostalgia):
        bridge.record_observation("a1", "invoicing", "processed invoice", False)
        question = bridge.generate_process_question("a1", "invoicing")
        assert question is not None
        assert isinstance(question, str)
        assert len(question) > 10

    def test_graceful_degradation_without_knostalgia(self, bridge_no_knostalgia):
        question = bridge_no_knostalgia.generate_process_question("a1", "scheduling")
        assert question is not None
        assert "scheduling" in question

    def test_question_contains_process_name(self, bridge):
        question = bridge.generate_process_question("a1", "expense_reporting")
        assert "expense_reporting" in question


class TestOnQuestionAnswered:
    def test_confirmed_calls_recall_confirmed(self, bridge, mock_knostalgia):
        obs = bridge.record_observation("a1", "proc", "action", False)
        bridge.on_question_answered(obs.observation_id, "Yes exactly", confirmed=True)
        assert obs.memory_id in mock_knostalgia.confirmed

    def test_rejected_calls_recall_rejected(self, bridge, mock_knostalgia):
        obs = bridge.record_observation("a1", "proc", "action", False)
        bridge.on_question_answered(obs.observation_id, "No that's different", confirmed=False)
        assert obs.memory_id in mock_knostalgia.rejected

    def test_creates_new_memory_from_answer(self, bridge):
        obs = bridge.record_observation("a1", "proc", "action", False)
        initial_count = len(bridge._observations)
        bridge.on_question_answered(obs.observation_id, "Here's what I meant", confirmed=True)
        assert len(bridge._observations) > initial_count

    def test_unknown_observation_does_not_raise(self, bridge):
        bridge.on_question_answered("nonexistent-id", "answer", confirmed=True)


class TestComputeProcessKFactor:
    def test_aggregates_correctly(self, bridge):
        bridge.record_observation("a1", "invoicing", "action 1", False)
        bridge.record_observation("a1", "invoicing", "action 2", True)
        result = bridge.compute_process_k_factor("a1", "invoicing")
        assert 0.0 <= result.k_factor <= 1.0
        assert "recall" in result.components

    def test_empty_process_returns_result(self, bridge):
        result = bridge.compute_process_k_factor("unknown-agent", "unknown-process")
        assert result is not None
        assert 0.0 <= result.k_factor <= 1.0


class TestComputeAssistMode:
    def test_returns_valid_dynamic_assist_output(self, bridge):
        bridge.record_observation("a1", "scheduling", "booked meeting", False)
        output = bridge.compute_assist_mode("a1", "scheduling", risk_level=0.2)
        assert isinstance(output.observe_only, bool)
        assert isinstance(output.may_suggest, bool)
        assert isinstance(output.may_execute, bool)
        assert 0.0 <= output.computed_epsilon <= 1.0
        assert 0.01 <= output.computed_learning_rate <= 0.5

    def test_high_risk_produces_requires_approval(self, bridge):
        output = bridge.compute_assist_mode("a1", "proc", risk_level=0.9)
        assert output.requires_approval is True


class TestGetRewardForRL:
    def test_returns_impact_weight_after_outcome(self, bridge):
        obs = bridge.record_observation("a1", "proc", "action", False)
        reward_recorded = bridge.record_outcome(obs.observation_id, 0.6, 0.8)
        reward_rl = bridge.get_reward_for_rl(obs.observation_id)
        assert abs(reward_rl - reward_recorded) < 1e-9

    def test_returns_zero_before_outcome(self, bridge):
        obs = bridge.record_observation("a1", "proc", "action", False)
        reward = bridge.get_reward_for_rl(obs.observation_id)
        assert reward == 0.0

    def test_unknown_observation_returns_zero(self, bridge):
        reward = bridge.get_reward_for_rl("nonexistent-id")
        assert reward == 0.0
