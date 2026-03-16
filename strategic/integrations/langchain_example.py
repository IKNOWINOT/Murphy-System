# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
integrations/langchain_example.py
===================================
Example usage of the Murphy LangChain Safety Layer.

Demonstrates:
  1. MurphyConfidenceCallback   — drop-in LangChain callback
  2. MurphySafetyGateChain      — wrapping a plain callable as a "chain"
  3. MurphyConfidenceRunnable   — composable pipeline unit (no LangChain needed)

Run with:
    python langchain_example.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from murphy_confidence.types import Phase, GateType
from murphy_confidence.gates import SafetyGate
from integrations.langchain_safety_layer import (
    MurphyConfidenceCallback,
    MurphySafetyGateChain,
    MurphyConfidenceRunnable,
    MurphyGateBlockedError,
)


# ── 1. MurphyConfidenceCallback demo ─────────────────────────────────────────

def demo_callback() -> None:
    print("\n── Demo 1: MurphyConfidenceCallback ──────────────────")

    callback = MurphyConfidenceCallback(
        phase=Phase.EXECUTE,
        hazard_floor=0.05,
        blocking_threshold=0.70,
        goodness_fn=lambda p, o: 0.85,
        domain_fn=lambda p, o: 0.80,
        hazard_fn=lambda p, o: 0.08,
    )

    # Simulate LangChain lifecycle events
    callback.on_llm_start({}, ["What is the recommended dosage of ibuprofen?"])

    # Simulate a response object
    class FakeGeneration:
        text = "Ibuprofen: 400 mg every 6 hours, max 1200 mg/day OTC."

    class FakeResponse:
        generations = [[FakeGeneration()]]

    try:
        callback.on_llm_end(FakeResponse())
        result = callback.last_confidence_result
        print(f"  Callback passed. Score={result.score:.4f} Action={result.action.value}")
    except MurphyGateBlockedError as e:
        print(f"  Callback BLOCKED: {e}")


# ── 2. MurphySafetyGateChain demo ────────────────────────────────────────────

def demo_safety_gate_chain() -> None:
    print("\n── Demo 2: MurphySafetyGateChain ─────────────────────")

    # Plain callable acting as a "chain"
    def mock_chain(query: str) -> str:
        return f"AI response to: {query}"

    hipaa_gate    = SafetyGate("hipaa", GateType.COMPLIANCE, blocking=True, threshold=0.88)
    clinical_gate = SafetyGate("clinical", GateType.HITL, blocking=True, threshold=0.80)

    chain = MurphySafetyGateChain(
        chain=mock_chain,
        phase=Phase.EXECUTE,
        gates=[hipaa_gate, clinical_gate],
        goodness_fn=lambda i, o: 0.91,
        domain_fn=lambda i, o: 0.89,
        hazard_fn=lambda i, o: 0.06,
    )

    try:
        output = chain.run("Recommend treatment for Type-2 diabetes")
        print(f"  Chain output: {output}")
    except MurphyGateBlockedError as e:
        print(f"  Chain BLOCKED by gate '{e.gate_result.gate_id}': {e}")

    # Now with low confidence to trigger blocking
    chain_risky = MurphySafetyGateChain(
        chain=mock_chain,
        phase=Phase.EXECUTE,
        gates=[hipaa_gate],
        goodness_fn=lambda i, o: 0.30,
        domain_fn=lambda i, o: 0.25,
        hazard_fn=lambda i, o: 0.80,
    )
    try:
        chain_risky.run("Recommend experimental surgery")
    except MurphyGateBlockedError as e:
        print(f"  Risky chain correctly BLOCKED: {e.gate_result.gate_id} — score {e.confidence_result.score:.4f}")


# ── 3. MurphyConfidenceRunnable demo ─────────────────────────────────────────

def demo_runnable() -> None:
    print("\n── Demo 3: MurphyConfidenceRunnable (LangGraph-style) ─")

    def summarise(data: dict) -> dict:
        return {"summary": f"Summary of: {data.get('text', '')}"}

    runnable = MurphyConfidenceRunnable(
        inner_fn=summarise,
        phase=Phase.BIND,
        goodness_fn=lambda i, o: 0.82,
        domain_fn=lambda i, o: 0.78,
        hazard_fn=lambda i, o: 0.05,
    )

    # invoke
    result = runnable.invoke({"text": "Patient history shows elevated CRP levels."})
    print(f"  invoke result: {result}")

    # batch
    inputs = [
        {"text": "Lab results: WBC normal."},
        {"text": "ECG shows sinus rhythm."},
    ]
    results = runnable.batch(inputs)
    print(f"  batch results: {[r['summary'] for r in results]}")

    # stream
    for chunk in runnable.stream({"text": "MRI clear, no lesions."}):
        print(f"  stream chunk: {chunk}")

    # pipe composition
    def formatter(data: dict) -> dict:
        return {"formatted": data["summary"].upper()}

    formatter_runnable = MurphyConfidenceRunnable(inner_fn=formatter, phase=Phase.BIND)
    pipeline = runnable | formatter_runnable
    final = pipeline.invoke({"text": "Chest X-ray normal."})
    print(f"  pipeline result: {final}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  MURPHY SYSTEM — LangChain Safety Layer Examples")
    print("=" * 60)
    demo_callback()
    demo_safety_gate_chain()
    demo_runnable()
    print("\n  All examples completed.")


if __name__ == "__main__":
    main()
