#!/usr/bin/env python3
"""
PCR-040b hotfix #2 — Use MurphyLLMProvider.complete() instead of
LLMController.query_llm().

Symptom from live test #2: "Cannot run the event loop while another
loop is running" — FastAPI is already running asyncio, our manual
new_event_loop() crashes.

Diagnosis: I should be using MurphyLLMProvider.complete() — it's
already synchronous AND loop-aware (PATCH-R281 solved this exact
problem in the LLMProvider). Same code path as the working DeepInfra
calls in the journal.

This swap also removes the LLMRequest constructor entirely since
.complete() takes prompt + system as direct args. Cleaner.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

APP = Path("/opt/Murphy-System/src/runtime/app.py")

OLD = '''                                    # Call LLM
                                    from src.llm_controller import LLMController as _LLMC_040b, LLMRequest as _LLMReq_040b
                                    import asyncio as _asyncio_040b
                                    _llm_040b = _LLMC_040b()
                                    # PCR-040b hotfix: field is `prompt`, not `query`
                                    _req_040b = _LLMReq_040b(
                                        prompt=_brief_040b,
                                        context="",
                                        max_tokens=2000,
                                    )
                                    # Use a fresh event loop per call (dispatch is sync)
                                    _loop_040b = _asyncio_040b.new_event_loop()
                                    try:
                                        _resp_040b = _loop_040b.run_until_complete(
                                            _asyncio_040b.wait_for(
                                                _llm_040b.query_llm(_req_040b),
                                                timeout=60.0
                                            )
                                        )
                                    finally:
                                        _loop_040b.close()

                                    _raw_040b = getattr(_resp_040b, "content", "") or str(_resp_040b)'''

NEW = '''                                    # PCR-040b hotfix #2: use MurphyLLMProvider.complete() —
                                    # loop-aware sync wrapper (PATCH-R281), no async dance.
                                    from src.llm_provider import MurphyLLMProvider as _MLLM_040b
                                    _llm_040b = _MLLM_040b()
                                    _resp_040b = _llm_040b.complete(
                                        prompt=_brief_040b,
                                        system="You are a structured-output agent. Return only valid JSON, no markdown, no commentary.",
                                        max_tokens=2000,
                                        temperature=0.7,
                                    )
                                    _raw_040b = getattr(_resp_040b, "content", "") or str(_resp_040b)'''


def apply(verify, revert):
    print(f"PCR-040b loop fix  verify={verify}  revert={revert}")
    src = APP.read_text(encoding="utf-8")
    if revert:
        if "PCR-040b hotfix #2" not in src:
            print("  · already absent"); return 0
        src = src.replace(NEW, OLD, 1)
        if verify: print("  ✓ would revert"); return 0
        APP.write_text(src, encoding="utf-8"); print("  ✓ reverted"); return 0
    if "PCR-040b hotfix #2" in src:
        print("  · already present"); return 0
    if OLD not in src:
        print("  ✗ anchor not found")
        return 1
    src = src.replace(OLD, NEW, 1)
    if verify: print("  ✓ would apply"); return 0
    APP.write_text(src, encoding="utf-8")
    print("  ✓ applied — MurphyLLMProvider.complete() in place")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    return apply(a.verify, a.revert)


if __name__ == "__main__":
    sys.exit(main())
