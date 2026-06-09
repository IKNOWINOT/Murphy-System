#!/usr/bin/env python3
"""
Pure-logic tests for this round's executive wiring:
  - agent_slot_controller (2-slot ping-pong, queue cap, priority)
  - executive_cta (3 categories, dedupe, lifecycle)

Uses asyncio + an in-process temp sqlite DB. No network, no LLM.
Runs in milliseconds.
"""

from __future__ import annotations
import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _check(name, cond, detail=""):
    icon = "✓" if cond else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f"   ({str(detail)[:140]})"
    print(line)
    return cond


# ──────────────────────────────────────────────────────────
# Slot controller tests
# ──────────────────────────────────────────────────────────

async def test_slot_acquire_release():
    print("\n── slot controller: acquire + release ──")
    from src.agent_slot_controller import AgentSlotController
    ok = True
    sc = AgentSlotController(slot_count=2, queue_cap=20, emit_cadence=False)

    assert await sc.acquire("a1", "lead_eng", "engineering")
    assert await sc.acquire("a2", "qa", "engineering")
    s = sc.status()
    ok &= _check("2 slots active", len(s["active"]) == 2)
    ok &= _check("free_slots = 0",  s["free_slots"] == 0)
    ok &= _check("queue empty",     s["queue_depth"] == 0)

    ok &= _check("release a1 returns True", sc.release("a1") is True)
    s = sc.status()
    ok &= _check("free_slots = 1 after release", s["free_slots"] == 1)
    ok &= _check("release unknown returns False", sc.release("nope") is False)

    sc.release("a2")
    return ok


async def test_slot_queue_pingpong():
    print("\n── slot controller: queue + ping-pong ──")
    from src.agent_slot_controller import AgentSlotController
    ok = True
    sc = AgentSlotController(slot_count=2, queue_cap=20, emit_cadence=False)

    # Fill 2 slots
    await sc.acquire("a1", "r1", "d")
    await sc.acquire("a2", "r2", "d")

    # Queue 3 more — they should block
    async def queued_acquire(aid):
        return await sc.acquire(aid, f"r{aid}", "d")

    t3 = asyncio.create_task(queued_acquire("a3"))
    t4 = asyncio.create_task(queued_acquire("a4"))
    t5 = asyncio.create_task(queued_acquire("a5"))

    # Yield so they actually enqueue
    await asyncio.sleep(0.02)
    s = sc.status()
    ok &= _check("3 queued behind 2 active", s["queue_depth"] == 3, s)

    # Release a1 — a3 should win the slot (FIFO at equal priority)
    sc.release("a1")
    await asyncio.wait_for(t3, timeout=1.0)
    s = sc.status()
    ok &= _check("after release a1: a3 active", any(x["agent_id"] == "a3" for x in s["active"]))
    ok &= _check("queue_depth dropped to 2",   s["queue_depth"] == 2)

    # Release a2 — a4 next
    sc.release("a2")
    await asyncio.wait_for(t4, timeout=1.0)
    s = sc.status()
    ok &= _check("ping-pong: a4 fills a2's slot",
                 any(x["agent_id"] == "a4" for x in s["active"]))

    # Cleanup
    sc.release("a3")
    sc.release("a4")
    await asyncio.wait_for(t5, timeout=1.0)
    sc.release("a5")
    return ok


async def test_slot_priority():
    print("\n── slot controller: priority queue ──")
    from src.agent_slot_controller import AgentSlotController
    ok = True
    sc = AgentSlotController(slot_count=2, queue_cap=20, emit_cadence=False)

    await sc.acquire("a1", "r1", "d")
    await sc.acquire("a2", "r2", "d")

    # Queue low priority then high — high should jump ahead
    t_low  = asyncio.create_task(sc.acquire("low",  "r", "d", priority=0))
    await asyncio.sleep(0.005)
    t_high = asyncio.create_task(sc.acquire("high", "r", "d", priority=10))
    await asyncio.sleep(0.02)

    s = sc.status()
    # Queue order — high should be at head (sorted by priority desc)
    ok &= _check("queued: high before low",
                 s["queued"][0]["agent_id"] == "high",
                 [q["agent_id"] for q in s["queued"]])

    sc.release("a1")
    await asyncio.wait_for(t_high, timeout=1.0)
    s = sc.status()
    ok &= _check("high acquired first", any(x["agent_id"] == "high" for x in s["active"]))

    sc.release("a2")
    await asyncio.wait_for(t_low, timeout=1.0)
    sc.release("high")
    sc.release("low")
    return ok


async def test_slot_queue_cap():
    print("\n── slot controller: queue cap rejects ──")
    from src.agent_slot_controller import AgentSlotController
    ok = True
    sc = AgentSlotController(slot_count=2, queue_cap=3, emit_cadence=False)

    await sc.acquire("a1", "r", "d")
    await sc.acquire("a2", "r", "d")
    t1 = asyncio.create_task(sc.acquire("q1", "r", "d"))
    t2 = asyncio.create_task(sc.acquire("q2", "r", "d"))
    t3 = asyncio.create_task(sc.acquire("q3", "r", "d"))
    await asyncio.sleep(0.02)

    s = sc.status()
    ok &= _check("queue at cap=3", s["queue_depth"] == 3, s)

    # Next should reject
    result = await sc.acquire("q4", "r", "d")
    ok &= _check("4th queued = REJECTED (returns False)", result is False)

    # Cleanup
    sc.release("a1")
    sc.release("a2")
    await asyncio.wait_for(t1, timeout=1.0)
    await asyncio.wait_for(t2, timeout=1.0)
    sc.release("q1")
    await asyncio.wait_for(t3, timeout=1.0)
    sc.release("q2")
    sc.release("q3")
    return ok


# ──────────────────────────────────────────────────────────
# CTA tests
# ──────────────────────────────────────────────────────────

def test_cta_completion():
    print("\n── CTA: completion category ──")
    from src import executive_cta as cta
    ok = True

    # Use a temp DB so we don't pollute the real one
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    cta.AUDIT_DB_PATH = tmp.name

    # Success → CTA created
    p = cta.propose_completion_cta(
        role="lead_engineer", domain="engineering",
        output_type="deliverable", accomplishment_id="acc_001",
        success=True, quality_score=0.88,
    )
    ok &= _check("success=True, q>=0.7 → CTA created", p is not None)
    ok &= _check("category=completion", p.category == "completion")
    ok &= _check("confidence preserved", abs(p.confidence - 0.88) < 0.001)

    # Failure → no CTA
    p2 = cta.propose_completion_cta(
        role="lead_engineer", domain="engineering",
        output_type="deliverable", accomplishment_id="acc_002",
        success=False, quality_score=0.5,
    )
    ok &= _check("success=False → no CTA", p2 is None)

    # Low quality → no CTA
    p3 = cta.propose_completion_cta(
        role="lead_engineer", domain="engineering",
        output_type="deliverable", accomplishment_id="acc_003",
        success=True, quality_score=0.4,
    )
    ok &= _check("low quality → no CTA", p3 is None)

    os.unlink(tmp.name)
    return ok


def test_cta_dedupe():
    print("\n── CTA: dedupe within window ──")
    from src import executive_cta as cta
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    cta.AUDIT_DB_PATH = tmp.name

    # Same signal twice in rapid succession — second should dedupe
    p1 = cta.propose_completion_cta(
        role="qa", domain="engineering", output_type="report",
        accomplishment_id="ACC_X", success=True, quality_score=0.8,
    )
    p2 = cta.propose_completion_cta(
        role="qa", domain="engineering", output_type="report",
        accomplishment_id="ACC_X", success=True, quality_score=0.8,
    )
    ok &= _check("first CTA created", p1 is not None)
    ok &= _check("duplicate within window suppressed", p2 is None)

    # Different accomplishment_id → different signal → new CTA
    p3 = cta.propose_completion_cta(
        role="qa", domain="engineering", output_type="report",
        accomplishment_id="ACC_Y", success=True, quality_score=0.8,
    )
    ok &= _check("different signal → new CTA", p3 is not None)

    os.unlink(tmp.name)
    return ok


def test_cta_threshold():
    print("\n── CTA: threshold category ──")
    from src import executive_cta as cta
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    cta.AUDIT_DB_PATH = tmp.name

    # Not satisfied → no CTA
    p = cta.propose_threshold_cta(
        dispatch_id="d1", apnea_recommendation="fire_again",
        score=0.5, satisfied=False,
    )
    ok &= _check("not satisfied → no CTA", p is None)

    # Satisfied → CTA
    p = cta.propose_threshold_cta(
        dispatch_id="d2", apnea_recommendation="satisfied",
        score=0.88, satisfied=True,
    )
    ok &= _check("satisfied → CTA created", p is not None)
    ok &= _check("requires HITL", p.requires_hitl is True)
    ok &= _check("label is approve-style", "Approve" in p.label or "approve" in p.label)

    # Raise ceiling → distinct CTA
    p2 = cta.propose_threshold_cta(
        dispatch_id="d3", apnea_recommendation="raise_goal_ceiling",
        score=0.86, satisfied=True, ceiling_level=0,
    )
    ok &= _check("raise_ceiling → CTA created", p2 is not None)
    ok &= _check("raise_ceiling: label mentions ceiling",
                 "ceiling" in p2.label.lower())

    os.unlink(tmp.name)
    return ok


def test_cta_lifecycle():
    print("\n── CTA: list + commit + dismiss ──")
    from src import executive_cta as cta
    ok = True

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    cta.AUDIT_DB_PATH = tmp.name

    p = cta.propose_completion_cta(
        role="lead_eng", domain="eng", output_type="design",
        accomplishment_id="acc_LL", success=True, quality_score=0.9,
    )
    pending = cta.list_pending(limit=10)
    ok &= _check("list_pending returns 1", len(pending) == 1)
    ok &= _check("pending item matches", pending[0]["cta_id"] == p.cta_id)

    # Commit
    r = cta.commit_cta(p.cta_id, committed_by="corey")
    ok &= _check("commit returns ok", r.get("ok") is True)
    pending = cta.list_pending(limit=10)
    ok &= _check("after commit: 0 pending", len(pending) == 0)

    # Second commit should fail (not pending anymore)
    r2 = cta.commit_cta(p.cta_id, committed_by="corey")
    ok &= _check("re-commit returns error", "error" in r2)

    os.unlink(tmp.name)
    return ok


# ──────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────

async def run_async_suites():
    return {
        "slot acquire/release":  await test_slot_acquire_release(),
        "slot queue + ping-pong": await test_slot_queue_pingpong(),
        "slot priority":         await test_slot_priority(),
        "slot queue cap":        await test_slot_queue_cap(),
    }


def main():
    print("Executive-round pure-logic test harness")

    results = {}
    try:
        async_results = asyncio.run(run_async_suites())
        results.update(async_results)
    except Exception as e:
        import traceback
        print(f"  ✗ async suites crashed: {e}")
        traceback.print_exc()

    # Sync suites
    sync_suites = [
        ("CTA completion category", test_cta_completion),
        ("CTA dedupe",              test_cta_dedupe),
        ("CTA threshold category",  test_cta_threshold),
        ("CTA lifecycle",           test_cta_lifecycle),
    ]
    for name, fn in sync_suites:
        try:
            results[name] = fn()
        except Exception as e:
            import traceback
            print(f"  ✗ SUITE EXCEPTION: {name}: {e}")
            traceback.print_exc()
            results[name] = False

    print("\n── SUMMARY ──")
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    for name, ok in results.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}")
    print(f"\n  {passed}/{total} suites passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
