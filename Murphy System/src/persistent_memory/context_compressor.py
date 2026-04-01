"""
Context Compressor — reduce token cost for long-running sessions.

Design Label: PM-003

When a session has been active for hours with lots of telemetry,
compress the context before passing to LLM calls.  Directly relevant
to DeepInfra key rotation and cost management.

Strategies:
  • Sliding window — keep last N messages
  • Summary extraction — distil old context into a summary
  • Priority-based — keep high-importance messages, compress low
  • Hybrid — combine sliding window with summary of older context
"""

from __future__ import annotations

import enum
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CompressionStrategy(str, enum.Enum):
    """Available context compression strategies."""

    SLIDING_WINDOW = "sliding_window"
    SUMMARY = "summary"
    PRIORITY = "priority"
    HYBRID = "hybrid"


class MessagePriority(str, enum.Enum):
    """Priority levels for context messages."""

    CRITICAL = "critical"   # System instructions, errors
    HIGH = "high"           # User messages, key decisions
    MEDIUM = "medium"       # Bot responses, intermediate results
    LOW = "low"             # Telemetry, debug, verbose output


class ContextMessage(BaseModel):
    """A single message in the conversation context."""

    role: str = "user"
    content: str = ""
    priority: MessagePriority = MessagePriority.MEDIUM
    token_estimate: int = 0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_compressed: bool = False


class CompressionResult(BaseModel):
    """Result of context compression."""

    original_messages: int = 0
    compressed_messages: int = 0
    original_tokens: int = 0
    compressed_tokens: int = 0
    savings_ratio: float = 0.0
    strategy_used: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW
    messages: List[ContextMessage] = Field(default_factory=list)


class ContextCompressor:
    """Compresses conversation context to reduce LLM token costs.

    Thread-safe, stateless (operates on provided message lists).
    """

    # Rough token estimate: ~4 chars per token (English text)
    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        *,
        max_tokens: int = 4096,
        window_size: int = 20,
        summary_max_tokens: int = 500,
    ) -> None:
        self._max_tokens = max_tokens
        self._window_size = window_size
        self._summary_max_tokens = summary_max_tokens

    def compress(
        self,
        messages: List[ContextMessage],
        *,
        strategy: CompressionStrategy = CompressionStrategy.HYBRID,
        max_tokens: Optional[int] = None,
    ) -> CompressionResult:
        """Compress a list of context messages."""
        target_tokens = max_tokens or self._max_tokens

        # Ensure token estimates are populated
        for msg in messages:
            if msg.token_estimate == 0:
                msg.token_estimate = self.estimate_tokens(msg.content)

        original_tokens = sum(m.token_estimate for m in messages)

        if original_tokens <= target_tokens:
            return CompressionResult(
                original_messages=len(messages),
                compressed_messages=len(messages),
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                savings_ratio=0.0,
                strategy_used=strategy,
                messages=list(messages),
            )

        if strategy == CompressionStrategy.SLIDING_WINDOW:
            compressed = self._sliding_window(messages, target_tokens)
        elif strategy == CompressionStrategy.SUMMARY:
            compressed = self._summary_extraction(messages, target_tokens)
        elif strategy == CompressionStrategy.PRIORITY:
            compressed = self._priority_based(messages, target_tokens)
        else:  # HYBRID
            compressed = self._hybrid(messages, target_tokens)

        compressed_tokens = sum(m.token_estimate for m in compressed)
        savings = 1.0 - (compressed_tokens / original_tokens) if original_tokens > 0 else 0.0

        return CompressionResult(
            original_messages=len(messages),
            compressed_messages=len(compressed),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            savings_ratio=round(savings, 4),
            strategy_used=strategy,
            messages=compressed,
        )

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimate based on character count."""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------

    def _sliding_window(
        self,
        messages: List[ContextMessage],
        max_tokens: int,
    ) -> List[ContextMessage]:
        """Keep only the last N messages that fit in the token budget."""
        result: List[ContextMessage] = []
        budget = max_tokens

        for msg in reversed(messages):
            if msg.token_estimate <= budget:
                result.insert(0, msg)
                budget -= msg.token_estimate
            else:
                break
        return result

    def _summary_extraction(
        self,
        messages: List[ContextMessage],
        max_tokens: int,
    ) -> List[ContextMessage]:
        """Summarize older messages, keep recent ones verbatim."""
        if len(messages) <= 2:
            return list(messages)

        # Split: older half → summarize, recent half → keep
        midpoint = len(messages) // 2
        older = messages[:midpoint]
        recent = messages[midpoint:]

        summary_text = self._build_summary(older)
        summary_msg = ContextMessage(
            role="system",
            content=f"[Context Summary] {summary_text}",
            priority=MessagePriority.MEDIUM,
            token_estimate=self.estimate_tokens(summary_text),
            is_compressed=True,
        )

        result = [summary_msg] + recent

        # Trim recent if still over budget
        total = sum(m.token_estimate for m in result)
        while total > max_tokens and len(result) > 1:
            removed = result.pop(1)  # Keep summary, remove oldest recent
            total -= removed.token_estimate

        return result

    def _priority_based(
        self,
        messages: List[ContextMessage],
        max_tokens: int,
    ) -> List[ContextMessage]:
        """Keep highest-priority messages first."""
        priority_order = {
            MessagePriority.CRITICAL: 0,
            MessagePriority.HIGH: 1,
            MessagePriority.MEDIUM: 2,
            MessagePriority.LOW: 3,
        }
        sorted_msgs = sorted(
            messages,
            key=lambda m: (priority_order.get(m.priority, 4), m.timestamp),
        )

        result: List[ContextMessage] = []
        budget = max_tokens
        for msg in sorted_msgs:
            if msg.token_estimate <= budget:
                result.append(msg)
                budget -= msg.token_estimate

        # Re-sort by timestamp for coherent context
        result.sort(key=lambda m: m.timestamp)
        return result

    def _hybrid(
        self,
        messages: List[ContextMessage],
        max_tokens: int,
    ) -> List[ContextMessage]:
        """Combine summary of older context + sliding window of recent."""
        if len(messages) <= self._window_size:
            return self._sliding_window(messages, max_tokens)

        older = messages[: -self._window_size]
        recent = messages[-self._window_size:]

        summary_text = self._build_summary(older)
        summary_tokens = min(
            self.estimate_tokens(summary_text),
            self._summary_max_tokens,
        )
        summary_msg = ContextMessage(
            role="system",
            content=f"[Context Summary] {summary_text}",
            priority=MessagePriority.MEDIUM,
            token_estimate=summary_tokens,
            is_compressed=True,
        )

        remaining_budget = max_tokens - summary_tokens
        windowed = self._sliding_window(recent, remaining_budget)

        return [summary_msg] + windowed

    # ------------------------------------------------------------------
    # Summary builder
    # ------------------------------------------------------------------

    def _build_summary(self, messages: List[ContextMessage]) -> str:
        """Build a concise summary of messages (extractive)."""
        if not messages:
            return "No prior context."

        # Extractive summary: take key sentences from each message
        summaries: List[str] = []
        for msg in messages:
            sentences = re.split(r'[.!?]+', msg.content)
            key_sentence = max(sentences, key=len).strip() if sentences else ""
            if key_sentence:
                summaries.append(f"{msg.role}: {key_sentence[:200]}")

        combined = "; ".join(summaries[: 20])  # Bounded
        max_chars = self._summary_max_tokens * self.CHARS_PER_TOKEN
        if len(combined) > max_chars:
            combined = combined[: max_chars - 3] + "..."
        return combined
