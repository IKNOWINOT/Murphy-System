"""MemoryCortexBot
🛡 Governed by Vallon (Core) with delegated features from Kiren and Veritas

This bot unifies ``memory_manager_bot``, ``librarian_bot``,
``deduplication_refiner_bot``, ``history_diff`` and ``swisskiss_loader`` into a
single orchestrator that governs short-term/long-term memory, retrieval,
ingestion and external loading.
"""
from __future__ import annotations

from typing import List, Optional, Any
from datetime import datetime

from .memory_manager_bot import MemoryManagerBot
from .deduplication_refiner_bot import DeduplicationRefinerBot, EntryMergerBot
from .librarian_bot import LibrarianBot, Document
from .history_diff import get_diff
from .swisskiss_loader import SwissKissLoader


class MemoryCortexBot:
    """Consolidated interface over memory and document handling."""

    def __init__(self, enc_key: Optional[bytes] = None) -> None:
        self.memory = MemoryManagerBot(encryption_key=enc_key)
        self.deduplicator = DeduplicationRefinerBot(self.memory)  # 🌀 Kiren
        self.merger = EntryMergerBot(self.memory)                 # 🛡 Vallon
        self.indexer = LibrarianBot(enc_key=enc_key)              # 🧠 Veritas
        self.loader = SwissKissLoader()                           # 🌀 Kiren

    # -- Memory delegation -------------------------------------------------
    def add_memory(self, text: str, trust: float = 1.0, tenant: str = "default") -> int:
        mem_id = self.memory.add_memory(text, trust=trust, tenant=tenant)
        return mem_id

    def retrieve_ltm(self, mem_id: int) -> Optional[str]:
        return self.memory.retrieve_ltm(mem_id)

    def search_ltm(self, query: str, *, top_k: int = 5, tenant: str = "default") -> List[Any]:
        return self.memory.search_ltm(query, top_k=top_k, tenant=tenant)

    # -- Document ingestion ------------------------------------------------
    def add_document(self, doc: Document) -> None:
        self.indexer.add_document(doc)

    def search_documents(self, query: str, tags: Optional[List[str]] = None) -> List[Document]:
        return self.indexer.search(query, tags)

    # -- Maintenance -------------------------------------------------------
    def cleanse_memory(self, keep_id: int, drop_id: int) -> None:
        """Detect duplicates and merge while recording history."""
        score, duplicate = self.deduplicator.find_duplicates(keep_id, drop_id)
        if duplicate:
            old_text = self.memory.retrieve_ltm(drop_id)
            if old_text is not None:
                self.memory.record_update(keep_id, old_text, editor="merge", reason="dedupe")
            self.merger.merge(keep_id, drop_id)

    def version_diff(self, mem_id: int) -> List[str]:
        """Return diff history for ``mem_id``."""
        return self.memory.get_history(mem_id)

    # -- Loader ------------------------------------------------------------
    def import_module_from_url(self, url: str, category: str, entry_script: str | None = None) -> Any:
        return self.loader.manual_load(url, category, entry_script)

    def get_cognitive_signature(self) -> dict:
        return {"kiren": 0.20, "veritas": 0.20, "vallon": 0.60}
