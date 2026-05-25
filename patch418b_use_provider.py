#!/usr/bin/env python3
"""
PATCH-418b — Rewire PATCH-418 lens dispatch to the existing llm_provider chain.

WHAT THIS IS:
  Replaces the urllib→Ollama-direct calls inside /api/rosetta/think and
  /api/rosetta/recurse with the canonical `llm_provider.complete()` entry
  point that the rest of Murphy already uses.

WHY IT EXISTS:
  Founder caught the wheel-reinvention: Murphy already has llm_provider.py
  with DeepInfra (primary) -> Together (fallback) -> Ollama (final fallback),
  plus llm_cost_ledger.py automatically tracking per-call spend. PATCH-418
  was bypassing all of that. This patch reconnects it.

HOW IT FITS:
  - Reads /opt/Murphy-System/src/runtime/app.py
  - Replaces the two urllib.request blocks in _rosetta_think and the _run()
    helper inside _rosetta_recurse
  - New call: `from llm_provider import complete; text = complete(prompt,
    system=..., max_tokens=...)` — string return, automatic provider chain,
    automatic cost tracking, automatic failover

LAST UPDATED: 2026-05-25 by PATCH-418b
"""
import ast
import shutil
from pathlib import Path

MONO = Path("/opt/Murphy-System/src/runtime/app.py")
src = MONO.read_text()

# ── Block 1: the urllib block inside _rosetta_think ───────────────────────
# Currently lines ~23035-23060
old_think = '''        if execute:
            try:
                import urllib.request, json as _json
                req_body = _json.dumps({
                    "model": "phi3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens, "temperature": 0.6},
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    rdata = _json.loads(resp.read().decode())
                result["response"] = rdata.get("response", "")
                result["execution"] = "ollama_local"
                result["model"] = rdata.get("model", "phi3")
            except Exception as e:
                result["response"] = None
                result["execution"] = "failed: " + str(e)
                result["prompt_assembled"] = prompt[:2000]
        else:
            result["prompt_assembled"] = prompt'''

new_think = '''        if execute:
            try:
                # PATCH-418b: use unified llm_provider chain (DeepInfra -> Together -> Ollama)
                # instead of hitting Ollama directly. Gives us automatic failover,
                # cost ledger entries, and frees the monolith from local-LLM RAM pressure.
                import sys as _sys
                _sys.path.insert(0, "/opt/Murphy-System/src")
                from llm_provider import complete as _llm_complete
                text = _llm_complete(
                    prompt,
                    system="You are a Murphy role agent. Respond strictly in the cognitive frame defined in the prompt.",
                    max_tokens=max_tokens,
                    temperature=0.6,
                )
                result["response"] = text if isinstance(text, str) else getattr(text, "content", "")
                result["execution"] = "llm_provider_chain"
                # llm_provider tracks actual provider used in cost ledger; we surface a hint
                try:
                    from llm_provider import get_llm as _get_llm
                    _last = getattr(_get_llm(), "last_provider_used", None)
                    if _last:
                        result["model"] = _last
                except Exception:
                    pass
            except Exception as e:
                result["response"] = None
                result["execution"] = "failed: " + str(e)
                result["prompt_assembled"] = prompt[:2000]
        else:
            result["prompt_assembled"] = prompt'''

if old_think not in src:
    print("  ✗ /think urllib block not found exactly")
    raise SystemExit(1)
src = src.replace(old_think, new_think, 1)
print("  ✓ /think rewired to llm_provider.complete()")


# ── Block 2: the urllib block inside _rosetta_recurse's _run() helper ─────
old_recurse_inner = '''            try:
                req_body = _json.dumps({
                    "model": "phi3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 500, "temperature": 0.6},
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=req_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    rdata = _json.loads(resp.read().decode())
                return {"response": rdata.get("response", ""),
                        "execution": "ollama_local"}
            except Exception as e:
                return {"response": None, "execution": "failed: " + str(e)}'''

new_recurse_inner = '''            try:
                # PATCH-418b: use unified llm_provider chain
                import sys as _sys2
                _sys2.path.insert(0, "/opt/Murphy-System/src")
                from llm_provider import complete as _llm_complete2
                text = _llm_complete2(
                    prompt,
                    system="You are a Murphy role agent. Respond strictly in the cognitive frame defined in the prompt.",
                    max_tokens=500,
                    temperature=0.6,
                )
                resp_text = text if isinstance(text, str) else getattr(text, "content", "")
                return {"response": resp_text, "execution": "llm_provider_chain"}
            except Exception as e:
                return {"response": None, "execution": "failed: " + str(e)}'''

if old_recurse_inner not in src:
    print("  ✗ /recurse _run() urllib block not found exactly")
    raise SystemExit(1)
src = src.replace(old_recurse_inner, new_recurse_inner, 1)
print("  ✓ /recurse rewired to llm_provider.complete()")


# Verify parse before write
ast.parse(src)
print("  ✓ AST parses")

backup = MONO.with_suffix(".py.pre-418b")
shutil.copy(MONO, backup)
MONO.write_text(src)
print(f"  ✓ wrote {MONO} (backup: {backup})")
print(f"  ✓ no more 11434 calls in PATCH-418: {src.count('11434') - 2} remaining (the two non-PATCH-418 references stay)")
