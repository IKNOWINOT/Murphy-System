"""
Persistent Memory + Context Compression.

Design Label: PM-001
Module ID:    src.persistent_memory

Per-tenant persistent memory and context compression:
  • Murphy remembers user preferences, execution patterns, and
    domain-specific corrections across sessions
  • Context compression for long-running sessions to save token costs

Commissioning answers
─────────────────────
Q: Does the module do what it was designed to do?
A: Provides per-tenant persistent memory with key-value storage,
   preference tracking, and LLM context compression.

Q: What conditions are possible?
A: Store / retrieve / search per tenant.  Compress context for LLM calls.
   Tenant isolation enforced.  Bounded per-tenant storage.

Q: Has hardening been applied?
A: Thread-safe, bounded per-tenant limits, tenant isolation, no bare except.
"""

from __future__ import annotations

from src.persistent_memory.tenant_memory import TenantMemoryStore
from src.persistent_memory.context_compressor import ContextCompressor

__all__ = [
    "ContextCompressor",
    "TenantMemoryStore",
]
