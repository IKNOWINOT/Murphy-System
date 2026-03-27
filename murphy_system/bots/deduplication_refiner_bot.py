"""Detect and merge semantic duplicate memories."""
from __future__ import annotations

from typing import Tuple
from sentence_transformers import SentenceTransformer, util
from .memory_manager_bot import MemoryManagerBot

class DeduplicationRefinerBot:
    def __init__(self, mm: MemoryManagerBot) -> None:
        self.mm = mm
        self.model = self.mm.model

    def find_duplicates(self, id1: int, id2: int) -> Tuple[float, bool]:
        t1 = self.mm.retrieve_ltm(id1)
        t2 = self.mm.retrieve_ltm(id2)
        if t1 is None or t2 is None:
            return 0.0, False
        e1 = self.model.encode(t1)
        e2 = self.model.encode(t2)
        score = float(util.cos_sim(e1, e2))
        return score, score > 0.92

class EntryMergerBot:
    def __init__(self, mm: MemoryManagerBot) -> None:
        self.mm = mm

    def merge(self, keep_id: int, drop_id: int) -> None:
        text = self.mm.retrieve_ltm(drop_id)
        if text is None:
            return
        self.mm.record_update(keep_id, text, editor="merger", reason="merge")
        self.mm.soft_delete(drop_id)
