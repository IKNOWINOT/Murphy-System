"""Tests for knostalgia_engine.py — core memory engine with impact-weighted decay."""
from __future__ import annotations

import math
import os
import threading
import time
import unittest



class TestImpactScoring(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.engine = KnostalgiaEngine()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_high_efficiency_yields_high_weight(self):
        weight = self.engine.score_impact(efficiency_delta=10.0, profit_delta=0.0)
        self.assertGreater(weight, 0.9)

    def test_low_efficiency_yields_low_weight(self):
        weight = self.engine.score_impact(efficiency_delta=0.01, profit_delta=0.01)
        self.assertLess(weight, 0.6)

    def test_weight_clamped_at_minimum(self):
        weight = self.engine.score_impact(efficiency_delta=-100.0, profit_delta=-100.0)
        self.assertGreaterEqual(weight, 0.05)

    def test_weight_clamped_at_maximum(self):
        weight = self.engine.score_impact(efficiency_delta=1000.0, profit_delta=1000.0)
        self.assertLessEqual(weight, 1.0)

    def test_alpha_beta_weighting(self):
        # efficiency-dominant engine
        eng_eff = self.engine.__class__(alpha=0.9, beta=0.1)
        # profit-dominant engine
        eng_prof = self.engine.__class__(alpha=0.1, beta=0.9)
        w_eff = eng_eff.score_impact(efficiency_delta=5.0, profit_delta=0.1)
        w_prof = eng_prof.score_impact(efficiency_delta=0.1, profit_delta=5.0)
        self.assertGreater(w_eff, 0.9)
        self.assertGreater(w_prof, 0.9)


class TestMemoryCreation(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _make_engine(self, spike_z=2.5):
        return self.KnostalgiaEngine(spike_z_threshold=spike_z)

    def test_memory_created_in_short_term(self):
        eng = self._make_engine()
        mem = eng.create_memory("content", "summary", "ctx", "cat", {}, 1.0, 1.0)
        self.assertEqual(mem.store, "SHORT_TERM")

    def test_memory_has_uuid(self):
        eng = self._make_engine()
        mem = eng.create_memory("content", "summary", "ctx", "cat", {}, 1.0, 1.0)
        self.assertTrue(len(mem.memory_id) > 0)

    def test_spike_detection_normal_weights(self):
        eng = self._make_engine(spike_z=2.5)
        # Feed several normal weights; none should be spikes
        for _ in range(20):
            m = eng.create_memory("c", "s", "ctx", "cat", {}, 0.5, 0.5)
        self.assertFalse(m.is_spike)

    def test_spike_detection_high_impact(self):
        eng = self._make_engine(spike_z=2.0)
        # Establish baseline with low-impact memories that vary slightly so
        # the z-score detector has non-zero variance to work with.
        import random
        random.seed(42)
        for i in range(20):
            e = 0.05 + random.uniform(0.0, 0.1)
            eng.create_memory("c", "s", "ctx", "cat", {}, e, e)
        # Now create a very high-impact memory — should flag as spike
        spike_mem = eng.create_memory("c", "s", "ctx", "cat", {}, 100.0, 100.0)
        self.assertTrue(spike_mem.is_spike)
        self.assertEqual(spike_mem.causal_status, "PENDING_ANALYSIS")

    def test_non_spike_causal_status(self):
        eng = self._make_engine()
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        # With sparse data the first memory may or may not be a spike, but
        # if it isn't a spike the causal status must be NONE
        if not mem.is_spike:
            self.assertEqual(mem.causal_status, "NONE")


class TestRecall(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine, RecallResult
            self.KnostalgiaEngine = KnostalgiaEngine
            self.RecallResult = RecallResult
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _unit_vec(self, dim=4, idx=0):
        v = [0.0] * dim
        v[idx] = 1.0
        return v

    def test_short_term_recall_hit(self):
        """Cosine similarity above threshold in short-term returns a hit."""
        eng = self.KnostalgiaEngine(
            short_term_recall_threshold=0.5,
        )
        emb = self._unit_vec(4, 0)
        mem = eng.create_memory("c", "summary A", "ctx", "cat", {}, 5.0, 5.0, embedding=emb)
        # Ensure weight is high enough
        mem.weight = 1.0

        result = eng.recall(query_embedding=emb, query_text="test")
        self.assertGreater(len(result.recalled_memories), 0)
        self.assertFalse(result.new_memory_needed)

    def test_short_term_miss_falls_back_to_long_term(self):
        """Nothing in short-term, but match in long-term returns a hit."""
        eng = self.KnostalgiaEngine(
            short_term_recall_threshold=0.99,  # extremely high — short-term always misses
            long_term_recall_threshold=0.5,
        )
        emb = self._unit_vec(4, 0)
        mem = eng.create_memory("c", "summary LT", "ctx", "cat", {}, 1.0, 1.0, embedding=emb)
        # Force to LONG_TERM
        mem.store = "LONG_TERM"
        mem.weight = 0.8

        result = eng.recall(query_embedding=emb, query_text="test")
        self.assertGreater(len(result.recalled_memories), 0)
        self.assertFalse(result.new_memory_needed)

    def test_no_match_returns_new_memory_needed(self):
        """Orthogonal query — no recalled memories, new_memory_needed=True."""
        eng = self.KnostalgiaEngine()
        emb_a = self._unit_vec(4, 0)
        emb_b = self._unit_vec(4, 1)
        eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0, embedding=emb_a)

        result = eng.recall(query_embedding=emb_b, query_text="unrelated")
        self.assertTrue(result.new_memory_needed)

    def test_deep_archive_not_returned_in_auto_recall(self):
        """DEEP_ARCHIVE memories are excluded from automatic recall."""
        eng = self.KnostalgiaEngine(
            short_term_recall_threshold=0.5,
            long_term_recall_threshold=0.5,
        )
        emb = self._unit_vec(4, 0)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0, embedding=emb)
        mem.store = "DEEP_ARCHIVE"
        mem.weight = 1.0

        result = eng.recall(query_embedding=emb, query_text="test")
        self.assertTrue(result.new_memory_needed)


class TestRecallPrompt(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.engine = KnostalgiaEngine()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_prompt_format(self):
        mem = self.engine.create_memory(
            "content", "the big sale", "we tried a flash discount", "sales", {}, 1.0, 1.0
        )
        prompt = self.engine.build_recall_prompt(mem)
        self.assertIn("Do you mean like the big sale", prompt)
        self.assertIn("like that one time we tried a flash discount", prompt)


class TestRecallConfirmation(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_confirmation_snaps_weight_back(self):
        eng = self.KnostalgiaEngine()
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 3.0, 3.0)
        original_weight = mem.original_impact_weight
        # Manually decay the weight
        mem.weight = 0.1
        eng.on_recall_confirmed(mem.memory_id)
        self.assertAlmostEqual(mem.weight, original_weight, places=5)

    def test_confirmation_increments_recall_count(self):
        eng = self.KnostalgiaEngine()
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        eng.on_recall_confirmed(mem.memory_id)
        self.assertEqual(mem.recall_count, 1)
        eng.on_recall_confirmed(mem.memory_id)
        self.assertEqual(mem.recall_count, 2)

    def test_confirmation_promotes_to_short_term(self):
        eng = self.KnostalgiaEngine()
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        mem.store = "LONG_TERM"
        eng.on_recall_confirmed(mem.memory_id)
        self.assertEqual(mem.store, "SHORT_TERM")


class TestRecallRejection(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.engine = KnostalgiaEngine()
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_rejection_decrements_weight(self):
        mem = self.engine.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        before = mem.weight
        self.engine.on_recall_rejected(mem.memory_id)
        self.assertLess(mem.weight, before)

    def test_rejection_weight_floor_zero(self):
        mem = self.engine.create_memory("c", "s", "ctx", "cat", {}, 0.001, 0.001)
        mem.weight = 0.02
        for _ in range(20):
            self.engine.on_recall_rejected(mem.memory_id)
        self.assertGreaterEqual(mem.weight, 0.0)


class TestDecayCycle(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_weights_decrease_after_decay(self):
        eng = self.KnostalgiaEngine(base_decay_rate=0.9)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        original = mem.weight
        eng.decay_cycle()
        self.assertLess(mem.weight, original)

    def test_high_impact_decays_slower_than_low_impact(self):
        """Decay is proportional to weight — heavier memories decay slower."""
        eng = self.KnostalgiaEngine(base_decay_rate=0.8)
        high = eng.create_memory("c", "s", "ctx", "cat", {}, 8.0, 8.0)
        low = eng.create_memory("c", "s", "ctx", "cat", {}, 0.01, 0.01)
        high_before = high.weight
        low_before = low.weight
        eng.decay_cycle()
        # Relative loss should be smaller for the high-impact memory
        high_loss = (high_before - high.weight) / high_before
        low_loss = (low_before - low.weight) / low_before
        self.assertLess(high_loss, low_loss)


class TestPromoteDemote(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_short_term_demoted_to_long_term(self):
        eng = self.KnostalgiaEngine(short_term_threshold=0.4, base_decay_rate=0.001)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 0.001, 0.001)
        # Force weight below threshold
        mem.weight = 0.3
        eng.decay_cycle()
        self.assertEqual(mem.store, "LONG_TERM")

    def test_long_term_moved_to_deep_archive(self):
        eng = self.KnostalgiaEngine(base_decay_rate=0.001)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 0.001, 0.001)
        mem.store = "LONG_TERM"
        mem.weight = 0.04
        eng.decay_cycle()
        self.assertEqual(mem.store, "DEEP_ARCHIVE")

    def test_short_term_above_threshold_stays(self):
        eng = self.KnostalgiaEngine()
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 2.0, 2.0)
        mem.weight = 0.9
        eng.decay_cycle()
        self.assertEqual(mem.store, "SHORT_TERM")


class TestSpikeFloor(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_spike_memory_never_below_spike_floor(self):
        eng = self.KnostalgiaEngine(base_decay_rate=0.001, spike_floor=0.15)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 1.0, 1.0)
        mem.is_spike = True
        mem.weight = 0.2
        # Run many decay cycles
        for _ in range(100):
            eng.decay_cycle()
        self.assertGreaterEqual(mem.weight, 0.15)

    def test_non_spike_can_go_below_floor(self):
        eng = self.KnostalgiaEngine(base_decay_rate=0.001, spike_floor=0.15)
        mem = eng.create_memory("c", "s", "ctx", "cat", {}, 0.001, 0.001)
        mem.is_spike = False
        mem.store = "LONG_TERM"
        mem.weight = 0.001
        eng.decay_cycle()
        self.assertLessEqual(mem.weight, 0.15)


class TestThreadSafety(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_concurrent_create_recall_decay(self):
        eng = self.KnostalgiaEngine()
        errors = []

        def creator():
            try:
                for i in range(10):
                    eng.create_memory(f"c{i}", "s", "ctx", "cat", {}, 1.0, 1.0)
            except Exception as exc:
                errors.append(exc)

        def decayer():
            try:
                for _ in range(5):
                    eng.decay_cycle()
                    time.sleep(0.001)
            except Exception as exc:
                errors.append(exc)

        def recaller():
            try:
                for _ in range(10):
                    eng.recall([1.0, 0.0, 0.0, 0.0], "query")
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=creator) for _ in range(3)]
            + [threading.Thread(target=decayer) for _ in range(2)]
            + [threading.Thread(target=recaller) for _ in range(2)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread safety errors: {errors}")


class TestGetSpikes(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine
            self.KnostalgiaEngine = KnostalgiaEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def test_get_spikes_filters_by_status(self):
        eng = self.KnostalgiaEngine(spike_z_threshold=2.0)
        # Build baseline
        for _ in range(15):
            eng.create_memory("c", "s", "ctx", "cat", {}, 0.01, 0.01)
        spike = eng.create_memory("c", "s", "ctx", "cat", {}, 100.0, 100.0)
        if spike.is_spike:
            spikes = eng.get_spikes(status="PENDING_ANALYSIS")
            self.assertIn(spike, spikes)
            spikes_none = eng.get_spikes(status="ANALYZED")
            self.assertNotIn(spike, spikes_none)


if __name__ == "__main__":
    unittest.main()
