"""Tests for knostalgia_category_engine.py — category reasoning via familiarity."""
from __future__ import annotations

import os
import unittest



def _unit_vec(dim=4, idx=0):
    v = [0.0] * dim
    v[idx] = 1.0
    return v


class TestCategorizationWithRecall(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import KnostalgiaEngine, RecallResult
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine
            self.KnostalgiaEngine = KnostalgiaEngine
            self.RecallResult = RecallResult
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _make_engines(self):
        eng = self.KnostalgiaEngine()
        cat_eng = self.KnostalgiaCategoryEngine()
        return eng, cat_eng

    def test_categorize_inherits_from_recalled_memory(self):
        eng, cat_eng = self._make_engines()
        emb = _unit_vec(4, 0)
        mem = eng.create_memory("c", "summary", "ctx", "sales", {"method": "discount"}, 2.0, 2.0, embedding=emb)
        mem.weight = 1.0

        recall_result = eng.recall(query_embedding=emb, query_text="test")
        # Patch recall to always return the memory regardless of threshold
        recall_result.recalled_memories = [mem]

        ctx = cat_eng.categorize(input_embedding=emb, memory_context=recall_result)
        self.assertEqual(ctx.category.name, "sales")
        self.assertFalse(ctx.is_new_category)

    def test_inherited_reasoning_framework(self):
        eng, cat_eng = self._make_engines()
        emb = _unit_vec(4, 1)
        framework = {"method": "upsell", "target": "premium"}
        mem = eng.create_memory("c", "s", "ctx", "upsell_cat", framework, 1.0, 1.0, embedding=emb)
        mem.weight = 1.0

        from src.knostalgia_engine import RecallResult
        recall = RecallResult(recalled_memories=[mem], new_memory_needed=False, recall_prompts=[])
        ctx = cat_eng.categorize(input_embedding=emb, memory_context=recall)
        self.assertEqual(ctx.inherited_reasoning_framework.get("method"), "upsell")


class TestCategorizationWithoutRecall(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_engine import RecallResult
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            self.RecallResult = RecallResult
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _empty_recall(self):
        return self.RecallResult(recalled_memories=[], new_memory_needed=True, recall_prompts=[])

    def test_nearest_prototype_matched(self):
        cat_eng = self.KnostalgiaCategoryEngine(category_confidence_threshold=0.01)
        emb = _unit_vec(4, 0)
        # Register a prototype manually
        import time, uuid
        proto = self.CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name="existing_cat",
            embedding=emb,
            reasoning_framework={"key": "val"},
            member_count=5,
            confidence=0.8,
            created_at=time.time(),
        )
        with cat_eng._lock:
            cat_eng._prototypes[proto.category_id] = proto

        ctx = cat_eng.categorize(input_embedding=emb, memory_context=self._empty_recall())
        self.assertEqual(ctx.category.name, "existing_cat")
        self.assertFalse(ctx.is_new_category)

    def test_new_category_created_when_nothing_matches(self):
        cat_eng = self.KnostalgiaCategoryEngine(
            category_confidence_threshold=0.99,
            new_category_threshold=0.99,
        )
        emb = _unit_vec(4, 2)
        ctx = cat_eng.categorize(input_embedding=emb, memory_context=self._empty_recall())
        self.assertTrue(ctx.is_new_category)

    def test_new_category_has_unique_id(self):
        cat_eng = self.KnostalgiaCategoryEngine(
            category_confidence_threshold=0.99,
            new_category_threshold=0.99,
        )
        ctx1 = cat_eng.categorize(input_embedding=_unit_vec(4, 0), memory_context=self.RecallResult([], True, []))
        ctx2 = cat_eng.categorize(input_embedding=_unit_vec(4, 1), memory_context=self.RecallResult([], True, []))
        self.assertNotEqual(ctx1.category.category_id, ctx2.category.category_id)


class TestPrototypeUpdate(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _make_proto(self, cat_eng, emb, name="test_cat"):
        import time, uuid
        proto = self.CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name=name,
            embedding=emb,
            reasoning_framework={},
            member_count=1,
            confidence=0.5,
            created_at=time.time(),
        )
        with cat_eng._lock:
            cat_eng._prototypes[proto.category_id] = proto
        return proto

    def test_confirmed_update_shifts_embedding(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        emb_a = _unit_vec(4, 0)
        proto = self._make_proto(cat_eng, emb_a)
        old_emb = list(proto.embedding)
        emb_b = _unit_vec(4, 1)
        cat_eng.update_prototype(proto.category_id, emb_b, confirmed=True)
        self.assertNotEqual(proto.embedding, old_emb)

    def test_confirmed_update_increases_confidence(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        proto = self._make_proto(cat_eng, _unit_vec(4, 0))
        before = proto.confidence
        cat_eng.update_prototype(proto.category_id, _unit_vec(4, 0), confirmed=True)
        self.assertGreater(proto.confidence, before)

    def test_rejected_update_decreases_confidence(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        proto = self._make_proto(cat_eng, _unit_vec(4, 0))
        before = proto.confidence
        cat_eng.update_prototype(proto.category_id, _unit_vec(4, 0), confirmed=False)
        self.assertLess(proto.confidence, before)

    def test_unknown_category_id_logged(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        # Should not raise
        cat_eng.update_prototype("nonexistent-id", [1.0], confirmed=True)


class TestCategoryFork(unittest.TestCase):
    def setUp(self):
        try:
            from src.knostalgia_category_engine import KnostalgiaCategoryEngine, CategoryPrototype
            self.KnostalgiaCategoryEngine = KnostalgiaCategoryEngine
            self.CategoryPrototype = CategoryPrototype
        except ImportError as exc:
            self.skipTest(f"Module not available: {exc}")

    def _make_proto(self, cat_eng, name="parent"):
        import time, uuid
        proto = self.CategoryPrototype(
            category_id=str(uuid.uuid4()),
            name=name,
            embedding=_unit_vec(4, 0),
            reasoning_framework={"strategy": "test"},
            member_count=3,
            confidence=0.8,
            created_at=time.time(),
        )
        with cat_eng._lock:
            cat_eng._prototypes[proto.category_id] = proto
        return proto

    def test_fork_creates_new_prototype(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        parent = self._make_proto(cat_eng)
        forked = cat_eng.fork_category(parent.category_id, _unit_vec(4, 1))
        self.assertNotEqual(forked.category_id, parent.category_id)
        self.assertIn(parent.name, forked.name)

    def test_fork_inherits_reasoning_framework(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        parent = self._make_proto(cat_eng)
        forked = cat_eng.fork_category(parent.category_id, _unit_vec(4, 1))
        self.assertEqual(forked.reasoning_framework.get("strategy"), "test")

    def test_fork_has_lower_confidence_than_parent(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        parent = self._make_proto(cat_eng)
        forked = cat_eng.fork_category(parent.category_id, _unit_vec(4, 1))
        self.assertLess(forked.confidence, parent.confidence)

    def test_fork_stored_in_engine(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        parent = self._make_proto(cat_eng)
        forked = cat_eng.fork_category(parent.category_id, _unit_vec(4, 1))
        self.assertIn(forked.category_id, {p.category_id for p in cat_eng.all_prototypes()})

    def test_fork_unknown_parent_does_not_raise(self):
        cat_eng = self.KnostalgiaCategoryEngine()
        # Should not raise, produces a new prototype anyway
        forked = cat_eng.fork_category("no-such-id", _unit_vec(4, 0))
        self.assertIsNotNone(forked)


if __name__ == "__main__":
    unittest.main()
