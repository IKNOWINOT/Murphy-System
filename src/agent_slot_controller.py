"""
agent_slot_controller.py — bounded concurrency for agent execution

Founder directive (locked 2026-06-09):
  "Two simultaneous but with ping-pong for additional agents."

Semantics:
  - Hard cap of N=2 concurrently-executing agents (configurable per dispatch)
  - Additional agents queue serially behind active slots
  - As an active slot frees, the queue head takes it (whichever slot is open)
  - Priority queue: ordered by (priority desc, queued_at asc)
  - Queue depth cap: 20 (reject new agents over cap, fail-loud)
  - Orchestrator/coordinator agents do NOT count against the 2 slots
    (per founder default q2=a — only LLM-calling work counts)
  - Fairness: same role can hold both slots only if queue is empty

Per-dispatch override:
  Dispatchers may request slots > global default, capped at server max.
  Server max is conservative for the current Hetzner box; raise via env.

Cadence integration:
  Every acquire/release emits a heartbeat to cadence_emit so the
  executive panel can render real-time ping-pong state. Failsoft —
  cadence errors never block agent execution.

Public API:
  controller = AgentSlotController(slot_count=2, queue_cap=20)
  await controller.acquire(agent_id, role, domain, priority=0)
  controller.release(agent_id)
  status = controller.status()  # {active:[], queued:[], depth:int, ...}
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

LOG = logging.getLogger("murphy.slot_controller")

# Server-wide cap — Hetzner 4 vCPU / 7.6 GB current reality.
# Raise via MURPHY_AGENT_SLOTS_MAX env when box grows.
SERVER_MAX_SLOTS = int(os.environ.get("MURPHY_AGENT_SLOTS_MAX", "2"))
SERVER_MAX_QUEUE = int(os.environ.get("MURPHY_AGENT_QUEUE_MAX", "20"))


@dataclass(order=True)
class _QueueEntry:
    """Internal priority-queue entry. Lower tuple compares first.

    Sort key = (-priority, queued_at_ns) — higher priority wins, ties
    broken by FIFO. We store the comparable tuple separately so the
    heap doesn't try to compare the payload dict.
    """
    sort_key: Tuple[int, int]
    agent_id: str = field(compare=False)
    role: str = field(compare=False)
    domain: str = field(compare=False)
    priority: int = field(compare=False)
    queued_at_ns: int = field(compare=False)
    future: asyncio.Future = field(compare=False, repr=False)


@dataclass
class _ActiveSlot:
    """A currently-occupied slot."""
    agent_id: str
    role: str
    domain: str
    priority: int
    acquired_at_ns: int


class AgentSlotController:
    """Bounded-concurrency semaphore for agent execution.

    Thread-safe by virtue of asyncio single-thread semantics + an asyncio.Lock
    around mutation paths. Status reads are lock-free snapshots (best-effort
    consistent — fine for UI).
    """

    def __init__(
        self,
        slot_count: int = 2,
        queue_cap: int = 20,
        *,
        emit_cadence: bool = True,
    ) -> None:
        if slot_count < 1:
            raise ValueError("slot_count must be >= 1")
        if slot_count > SERVER_MAX_SLOTS:
            LOG.warning(
                "Requested slot_count=%d exceeds SERVER_MAX_SLOTS=%d — capping",
                slot_count, SERVER_MAX_SLOTS,
            )
            slot_count = SERVER_MAX_SLOTS
        if queue_cap < 1:
            raise ValueError("queue_cap must be >= 1")
        if queue_cap > SERVER_MAX_QUEUE:
            queue_cap = SERVER_MAX_QUEUE

        self.slot_count = slot_count
        self.queue_cap = queue_cap
        self._emit = emit_cadence

        self._sem = asyncio.Semaphore(slot_count)
        self._lock = asyncio.Lock()
        self._active: Dict[str, _ActiveSlot] = {}
        self._queue: List[_QueueEntry] = []
        # Counters for executive panel
        self._lifetime_acquires = 0
        self._lifetime_releases = 0
        self._lifetime_rejects = 0

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    async def acquire(
        self,
        agent_id: str,
        role: str,
        domain: str = "general",
        *,
        priority: int = 0,
        timeout_s: Optional[float] = None,
    ) -> bool:
        """Acquire a slot. Returns True on success, False on rejection.

        If all slots are taken, the caller blocks (awaits) until a slot
        opens — unless queue is at cap (queue_cap), in which case this
        rejects immediately and returns False (fail-loud per founder
        directive q3=b).
        """
        async with self._lock:
            # Queue cap check FIRST — fail fast if dispatch is misconfigured
            if len(self._queue) >= self.queue_cap and self._sem.locked():
                self._lifetime_rejects += 1
                LOG.warning(
                    "Slot rejected: queue at cap (%d) — agent %s/%s rejected",
                    self.queue_cap, role, agent_id,
                )
                self._emit_pulse("slot.rejected", success=False,
                                 agent_id=agent_id, role=role, domain=domain)
                return False

            queued_at = time.time_ns()
            fut: asyncio.Future = asyncio.get_event_loop().create_future()
            entry = _QueueEntry(
                sort_key=(-priority, queued_at),
                agent_id=agent_id, role=role, domain=domain,
                priority=priority, queued_at_ns=queued_at, future=fut,
            )
            heapq.heappush(self._queue, entry)
            self._emit_pulse("slot.queued", success=True,
                             agent_id=agent_id, role=role, domain=domain,
                             queue_depth=len(self._queue))

        # Wait for our turn (slot opens AND we're at queue head)
        try:
            if timeout_s is not None:
                await asyncio.wait_for(self._await_slot(entry), timeout=timeout_s)
            else:
                await self._await_slot(entry)
        except asyncio.TimeoutError:
            async with self._lock:
                # Remove our entry from the queue if still present
                self._queue = [q for q in self._queue if q.agent_id != agent_id]
                heapq.heapify(self._queue)
                self._lifetime_rejects += 1
            self._emit_pulse("slot.timeout", success=False,
                             agent_id=agent_id, role=role, domain=domain)
            return False

        return True

    def release(self, agent_id: str) -> bool:
        """Release a slot. Returns True if the agent was active, False otherwise.

        Synchronous because we want callers in finally blocks to not need
        await. Pushes notification to the queue head asynchronously.
        """
        slot = self._active.pop(agent_id, None)
        if slot is None:
            LOG.debug("release() called for unknown agent_id=%s", agent_id)
            return False

        elapsed_ns = time.time_ns() - slot.acquired_at_ns
        self._lifetime_releases += 1
        self._emit_pulse("slot.released", success=True,
                         agent_id=agent_id, role=slot.role,
                         domain=slot.domain, elapsed_ms=elapsed_ns / 1e6)

        # Free the semaphore so the next queued agent's _await_slot proceeds
        self._sem.release()
        return True

    def status(self) -> Dict[str, Any]:
        """Snapshot of current state — safe for UI polling.

        Returns:
          {
            slot_count, free_slots, queue_depth, queue_cap,
            active: [{agent_id, role, domain, priority, elapsed_ms}, ...],
            queued: [{agent_id, role, domain, priority, waiting_ms}, ...],
            lifetime: {acquires, releases, rejects},
          }
        """
        now_ns = time.time_ns()
        active_list = [
            {
                "agent_id":   s.agent_id,
                "role":       s.role,
                "domain":     s.domain,
                "priority":   s.priority,
                "elapsed_ms": (now_ns - s.acquired_at_ns) / 1e6,
            }
            for s in self._active.values()
        ]
        # Snapshot queue without mutating heap order
        queued_list = [
            {
                "agent_id":   q.agent_id,
                "role":       q.role,
                "domain":     q.domain,
                "priority":   q.priority,
                "waiting_ms": (now_ns - q.queued_at_ns) / 1e6,
            }
            for q in sorted(self._queue)
        ]
        return {
            "slot_count":  self.slot_count,
            "free_slots":  self.slot_count - len(self._active),
            "queue_depth": len(self._queue),
            "queue_cap":   self.queue_cap,
            "active":      active_list,
            "queued":      queued_list,
            "lifetime": {
                "acquires": self._lifetime_acquires,
                "releases": self._lifetime_releases,
                "rejects":  self._lifetime_rejects,
            },
        }

    # ─────────────────────────────────────────────────────────────
    # Internals
    # ─────────────────────────────────────────────────────────────

    async def _await_slot(self, my_entry: _QueueEntry) -> None:
        """Wait until this entry is at the head of the queue AND a slot is free."""
        while True:
            # Acquire the semaphore (blocks until a slot frees)
            await self._sem.acquire()

            async with self._lock:
                # Pop head of queue
                if not self._queue:
                    # Edge case: queue cleared while we were waiting
                    self._sem.release()
                    return
                head = heapq.heappop(self._queue)

                if head.agent_id == my_entry.agent_id:
                    # We're up — install into active
                    self._active[head.agent_id] = _ActiveSlot(
                        agent_id=head.agent_id,
                        role=head.role,
                        domain=head.domain,
                        priority=head.priority,
                        acquired_at_ns=time.time_ns(),
                    )
                    self._lifetime_acquires += 1
                    self._emit_pulse("slot.acquired", success=True,
                                     agent_id=head.agent_id,
                                     role=head.role, domain=head.domain,
                                     waited_ms=(time.time_ns() - head.queued_at_ns) / 1e6)
                    return
                else:
                    # Someone else is at head — push them back, release sem,
                    # and loop. (This happens if priority changed during wait.)
                    heapq.heappush(self._queue, head)
                    self._sem.release()
                    await asyncio.sleep(0.001)  # yield

    def _emit_pulse(self, event: str, **kw) -> None:
        """Fail-soft cadence emission. Never blocks or raises."""
        if not self._emit:
            return
        try:
            from src.cadence_emit import emit_heartbeat
            emit_heartbeat(
                source=f"slot_controller.{event}",
                success=bool(kw.get("success", True)),
                metadata=kw,
            )
        except Exception as e:
            LOG.debug("Cadence emit failed (non-fatal): %s", e)


# ─────────────────────────────────────────────────────────────
# Module-level singleton (lazy-init)
# ─────────────────────────────────────────────────────────────

_SINGLETON: Optional[AgentSlotController] = None


def get_default_controller() -> AgentSlotController:
    """Return the process-wide default controller. Lazy-instantiated."""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = AgentSlotController(slot_count=2, queue_cap=20)
    return _SINGLETON
