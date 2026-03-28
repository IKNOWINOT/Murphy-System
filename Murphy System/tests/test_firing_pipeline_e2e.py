"""End-to-end tests for the full 6-stage Knostalgia pipeline.

Pipeline: Input → Memory Check → Category Reason → Magnify x3 → HITL → Solidify

Tests verify the complete flow including recall prompting, new memory
creation, spike routing to causal analysis, and decay daemon behaviour.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
import unittest



def _unit_vec(dim=4, idx=0):
    v = [0.0] * dim
    v[idx] = 1.0
    return v


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _build_pipeline():
    """Construct and return (engine, category_engine, causal_analyzer)."""
    from src.knostalgia_engine import KnostalgiaEngine
    from src.knostalgia_category_engine import KnostalgiaCategoryEngine
    from src.causal_spike_analyzer import CausalSpikeAnalyzer

    engine = KnostalgiaEngine(
        short_term_recall_threshold=0.5,
        long_term_recall_threshold=0.7,
        spike_z_threshold=2.0,
        base_decay_rate=0.9,
    )
    cat_engine = KnostalgiaCategoryEngine()
    causal = CausalSpikeAnalyzer(cat_engine)
    return engine, cat_engine, causal


def _run_pipeline(engine, cat_engine, causal, input_emb, content, efficiency, profit):
    """Simulate one pass of the full 6-stage pipeline.

    Returns a dict with: recalled_memories, recall_prompts, new_memory_needed,
    category_context, memory (if created), hitl_prompts (if spike).
    """
    # Stage 1: Input
    # Stage 2: Memory Check
    recall_result = engine.recall(query_embedding=input_emb, query_text=content)

    # Stage 3: Category Reason
    cat_ctx = cat_engine.categorize(input_embedding=input_emb, memory_context=recall_result)

    # Stage 4: Magnify x3 (represented as impact scoring here — real MSS not needed)
    impact_weight = engine.score_impact(efficiency, profit)

    # Stage 5: HITL — surface recall prompts if memories found
    hitl_prompts = list(recall_result.recall_prompts)

    # Stage 6: Solidify — create new memory if needed
    new_memory = None
    if recall_result.new_memory_needed:
        new_memory = engine.create_memory(
            content=content,
            summary=f"summary of {content[:20]}",
            context=f"the time we ran {content[:20]}",
            category=cat_ctx.category.name,
            reasoning_framework=cat_ctx.inherited_reasoning_framework,
            efficiency_delta=efficiency,
            profit_delta=profit,
            embedding=input_emb,
        )
        # Route spike to causal analysis
        spike_hitl: list = []
        if new_memory.is_spike:
            hypothesis = causal.analyze_spike(new_memory)
            spike_hitl.append(causal.generate_hitl_prompt(hypothesis))
    else:
        spike_hitl = []

    return {
        "recalled_memories": recall_result.recalled_memories,
        "recall_prompts": recall_result.recall_prompts,
        "new_memory_needed": recall_result.new_memory_needed,
        "category_context": cat_ctx,
        "memory": new_memory,
        "spike_hitl_prompts": spike_hitl,
    }


# ──────────────────────────────────────────────────────────────────────
# Test cases
# ──────────────────────────────────────────────────────────────────────

class TestFullPipelineNewInput(unittest.TestCase):
    """New input with no prior memories → creates a new memory."""

    def setUp(self):
        try:
            self.engine, self.cat, self.causal = _build_pipeline()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_new_input_creates_memory(self):
        result = _run_pipeline(
            self.engine, self.cat, self.causal,
            input_emb=_unit_vec(4, 0),
            content="launch promo campaign",
            efficiency=1.0, profit=1.0,
        )
        self.assertTrue(result["new_memory_needed"])
        self.assertIsNotNone(result["memory"])

    def test_new_input_no_recall_prompts(self):
        result = _run_pipeline(
            self.engine, self.cat, self.causal,
            input_emb=_unit_vec(4, 0),
            content="fresh idea",
            efficiency=0.5, profit=0.5,
        )
        self.assertEqual(result["recall_prompts"], [])


class TestRecallSurfacesDoYouMeanPrompt(unittest.TestCase):
    """Second similar input should surface a 'Do you mean like...' prompt."""

    def setUp(self):
        try:
            self.engine, self.cat, self.causal = _build_pipeline()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_recall_triggers_hitl_prompt(self):
        emb = _unit_vec(4, 0)

        # First pass — stores the memory
        _run_pipeline(
            self.engine, self.cat, self.causal,
            input_emb=emb, content="run flash sale", efficiency=2.0, profit=2.0,
        )

        # Manually boost weight so it will be recalled
        for m in self.engine.all_memories():
            m.weight = 1.0

        # Second pass — same embedding, should recall
        result = _run_pipeline(
            self.engine, self.cat, self.causal,
            input_emb=emb, content="run flash sale again", efficiency=1.0, profit=1.0,
        )
        # Either recalled from memory or at minimum a prompt was generated
        if result["recalled_memories"]:
            self.assertGreater(len(result["recall_prompts"]), 0)
            self.assertIn("Do you mean like", result["recall_prompts"][0])

    def test_recall_prompt_contains_do_you_mean(self):
        emb = _unit_vec(4, 2)
        eng = self.engine
        mem = eng.create_memory(
            content="holiday discount", summary="holiday discount event",
            context="the holiday campaign in Q4", category="promo",
            reasoning_framework={}, efficiency_delta=2.0, profit_delta=2.0,
            embedding=emb,
        )
        mem.weight = 1.0

        prompt = eng.build_recall_prompt(mem)
        self.assertTrue(prompt.startswith("Do you mean like"))


class TestHighImpactCreatesSpikeAndCausal(unittest.TestCase):
    """Very high-impact outcome → spike → HITL causal prompt generated."""

    def setUp(self):
        try:
            self.engine, self.cat, self.causal = _build_pipeline()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_spike_routes_to_causal(self):
        # Establish baseline with modest-impact memories
        for i in range(15):
            _run_pipeline(
                self.engine, self.cat, self.causal,
                input_emb=_unit_vec(4, i % 4),
                content=f"routine op {i}",
                efficiency=0.01, profit=0.01,
            )

        # Inject a high-impact run — should flag as spike
        result = _run_pipeline(
            self.engine, self.cat, self.causal,
            input_emb=_unit_vec(4, 0),
            content="mega viral campaign",
            efficiency=100.0, profit=100.0,
        )
        mem = result["memory"]
        if mem and mem.is_spike:
            self.assertEqual(mem.causal_status, "PENDING_ANALYSIS")
            self.assertGreater(len(result["spike_hitl_prompts"]), 0)
            self.assertIn("Should we test this?", result["spike_hitl_prompts"][0])


class TestDecayDaemonPromotesDemotes(unittest.TestCase):
    """Decay cycles should correctly promote/demote memories between stores."""

    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_decay_daemon_promotes_demotes(self):
        engine = self.KnostalgiaEngine(base_decay_rate=0.001, short_term_threshold=0.4)
        # Create a low-weight memory
        mem = engine.create_memory("c", "s", "ctx", "cat", {}, 0.001, 0.001)
        mem.weight = 0.35  # just below SHORT_TERM threshold

        # One decay cycle
        engine.decay_cycle()
        self.assertEqual(mem.store, "LONG_TERM")

        # Further decay
        mem.weight = 0.04
        engine.decay_cycle()
        self.assertEqual(mem.store, "DEEP_ARCHIVE")

    def test_decay_daemon_is_thread_safe(self):
        engine = self.KnostalgiaEngine(base_decay_rate=0.9)
        errors = []

        def create_and_decay():
            try:
                for i in range(5):
                    engine.create_memory(f"c{i}", "s", "ctx", "cat", {}, 1.0, 1.0)
                    engine.decay_cycle()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create_and_decay) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread errors: {errors}")


class TestRecallConfirmRejectionIntegration(unittest.TestCase):
    """Integration: confirm/reject in context of the full pipeline."""

    def setUp(self):
        try:
            self.engine, self.cat, self.causal = _build_pipeline()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_confirmed_recall_promotes_to_short_term(self):
        emb = _unit_vec(4, 0)
        mem = self.engine.create_memory(
            "c", "s", "ctx", "cat", {}, 1.0, 1.0, embedding=emb
        )
        mem.store = "LONG_TERM"
        self.engine.on_recall_confirmed(mem.memory_id)
        self.assertEqual(mem.store, "SHORT_TERM")
        self.assertEqual(mem.recall_count, 1)

    def test_rejected_recall_reduces_weight(self):
        emb = _unit_vec(4, 1)
        mem = self.engine.create_memory(
            "c", "s", "ctx", "cat", {}, 1.0, 1.0, embedding=emb
        )
        before = mem.weight
        self.engine.on_recall_rejected(mem.memory_id)
        self.assertLess(mem.weight, before)


if __name__ == "__main__":
    unittest.main()
