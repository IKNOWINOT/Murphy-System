"""Tests for causal_spike_analyzer.py — spike analysis and cross-domain replication."""
from __future__ import annotations

import os
import time
import unittest
import uuid



def _unit_vec(dim=4, idx=0):
    v = [0.0] * dim
    v[idx] = 1.0
    return v


def _make_spike_memory(category="test_cat", embedding=None, framework=None):
    """Helper — create a KnostalgiaMemory that is flagged as a spike."""
    from src.knostalgia_engine import KnostalgiaMemory
    return KnostalgiaMemory(
        memory_id=str(uuid.uuid4()),
        content="spike content",
        summary="spike summary",
        context="spike context",
        category=category,
        reasoning_framework=framework or {"action": "batch_processing"},
        weight=0.95,
        original_impact_weight=0.95,
        efficiency_delta=10.0,
        profit_delta=8.0,
        created_at=time.time(),
        last_recall=time.time(),
        recall_count=0,
        store="SHORT_TERM",
        is_spike=True,
        causal_status="PENDING_ANALYSIS",
        embedding=embedding or _unit_vec(4, 0),
    )


class TestSpikeAnalysis(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            from src.causal_spike_analyzer import CausalSpikeAnalyzer
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
            self.CausalSpikeAnalyzer = CausalSpikeAnalyzer
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _make_analyzer(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        return self.CausalSpikeAnalyzer(cat_eng), cat_eng

    def test_analyze_spike_returns_hypothesis(self):
        analyzer, _ = self._make_analyzer()
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        self.assertIsNotNone(hypothesis)
        self.assertEqual(hypothesis.source_memory, mem)

    def test_hypothesis_has_isolated_variable(self):
        analyzer, _ = self._make_analyzer()
        mem = _make_spike_memory(framework={"action": "flash_sale"})
        hypothesis = analyzer.analyze_spike(mem)
        self.assertEqual(hypothesis.isolated_variable, "flash_sale")

    def test_hypothesis_causal_strength_in_range(self):
        analyzer, _ = self._make_analyzer()
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        self.assertGreaterEqual(hypothesis.causal_strength, 0.0)
        self.assertLessEqual(hypothesis.causal_strength, 1.0)

    def test_hypothesis_text_is_human_readable(self):
        analyzer, _ = self._make_analyzer()
        mem = _make_spike_memory(category="finance")
        hypothesis = analyzer.analyze_spike(mem)
        text = hypothesis.hypothesis_text
        self.assertIn("finance", text)
        self.assertIn("could produce similar results", text)

    def test_hypothesis_stored_internally(self):
        analyzer, _ = self._make_analyzer()
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        retrieved = analyzer.get_hypothesis(hypothesis.hypothesis_id)
        self.assertEqual(retrieved, hypothesis)


class TestTransferabilityScoring(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            from src.causal_spike_analyzer import CausalSpikeAnalyzer
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
            self.CausalSpikeAnalyzer = CausalSpikeAnalyzer
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _add_proto(self, cat_eng, name, embedding):
        proto = self.CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name=name,
            embedding=embedding,
            reasoning_framework={},
            member_count=2,
            confidence=0.7,
            created_at=time.time(),
        )
        with cat_eng._lock:
            cat_eng._prototypes[proto.category_id] = proto
        return proto

    def test_similar_categories_score_higher(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)

        source_emb = _unit_vec(4, 0)
        similar_emb = [0.9, 0.4, 0.0, 0.0]
        dissimilar_emb = _unit_vec(4, 3)

        self._add_proto(cat_eng, "similar_domain", similar_emb)
        self._add_proto(cat_eng, "dissimilar_domain", dissimilar_emb)

        mem = _make_spike_memory(category="source", embedding=source_emb)
        hypothesis = analyzer.analyze_spike(mem)

        score_similar = hypothesis.transferability_scores.get("similar_domain", 0.0)
        score_dissimilar = hypothesis.transferability_scores.get("dissimilar_domain", 0.0)
        self.assertGreater(score_similar, score_dissimilar)

    def test_source_category_excluded_from_candidates(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)

        emb = _unit_vec(4, 0)
        self._add_proto(cat_eng, "source_cat", emb)

        mem = _make_spike_memory(category="source_cat", embedding=emb)
        hypothesis = analyzer.analyze_spike(mem)
        self.assertNotIn("source_cat", hypothesis.candidate_domains)


class TestHITLPrompt(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine
            from src.causal_spike_analyzer import CausalSpikeAnalyzer
            self.analyzer = CausalSpikeAnalyzer(KnostalgiaCategoryEngine())
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_hitl_prompt_format(self):
        mem = _make_spike_memory(framework={"action": "overnight_delivery"})
        hypothesis = self.analyzer.analyze_spike(mem)
        prompt = self.analyzer.generate_hitl_prompt(hypothesis)
        self.assertIn("overnight_delivery", prompt)
        self.assertIn("Should we test this?", prompt)
        self.assertIn("unusually high impact", prompt)


class TestApproval(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            from src.causal_spike_analyzer import CausalSpikeAnalyzer
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
            self.CausalSpikeAnalyzer = CausalSpikeAnalyzer
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_approval_creates_replication_plan(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        plan = analyzer.on_approved(hypothesis.hypothesis_id)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.hypothesis_id, hypothesis.hypothesis_id)

    def test_approval_sets_hypothesis_status(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        analyzer.on_approved(hypothesis.hypothesis_id)
        self.assertEqual(hypothesis.status, "APPROVED")

    def test_approval_updates_source_memory_causal_status(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)
        mem = _make_spike_memory()
        hypothesis = analyzer.analyze_spike(mem)
        analyzer.on_approved(hypothesis.hypothesis_id)
        self.assertEqual(mem.causal_status, "REPLICATED")

    def test_approval_registers_template_in_candidate_category(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)

        # Add a candidate prototype
        target_proto = self.CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name="target_domain",
            embedding=[0.9, 0.4, 0.0, 0.0],
            reasoning_framework={},
            member_count=1,
            confidence=0.6,
            created_at=time.time(),
        )
        with cat_eng._lock:
            cat_eng._prototypes[target_proto.category_id] = target_proto

        mem = _make_spike_memory(category="source", embedding=_unit_vec(4, 0))
        hypothesis = analyzer.analyze_spike(mem)
        # Make sure the target is in candidate domains
        hypothesis.candidate_domains = ["target_domain"]
        analyzer.on_approved(hypothesis.hypothesis_id)

        # The target prototype's reasoning framework should have the replicated key
        updated = cat_eng.get_prototype(target_proto.category_id)
        self.assertTrue(
            any("replicated_from" in k for k in updated.reasoning_framework.keys())
        )

    def test_approval_unknown_id_raises(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        analyzer = self.CausalSpikeAnalyzer(cat_eng)
        with self.assertRaises(ValueError):
            analyzer.on_approved("nonexistent-id")


class TestRejection(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine
            from src.causal_spike_analyzer import CausalSpikeAnalyzer
            self.analyzer = CausalSpikeAnalyzer(KnostalgiaCategoryEngine())
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_rejection_sets_hypothesis_status(self):
        mem = _make_spike_memory()
        hypothesis = self.analyzer.analyze_spike(mem)
        self.analyzer.on_rejected(hypothesis.hypothesis_id)
        self.assertEqual(hypothesis.status, "REJECTED")

    def test_rejection_reduces_causal_strength(self):
        mem = _make_spike_memory()
        hypothesis = self.analyzer.analyze_spike(mem)
        before = hypothesis.causal_strength
        self.analyzer.on_rejected(hypothesis.hypothesis_id)
        self.assertLessEqual(hypothesis.causal_strength, before)

    def test_rejection_updates_source_memory_causal_status(self):
        mem = _make_spike_memory()
        hypothesis = self.analyzer.analyze_spike(mem)
        self.analyzer.on_rejected(hypothesis.hypothesis_id)
        self.assertEqual(mem.causal_status, "ANALYZED")

    def test_rejection_unknown_id_does_not_raise(self):
        # Should log a warning, not raise
        self.analyzer.on_rejected("no-such-id")


if __name__ == "__main__":
    unittest.main()
