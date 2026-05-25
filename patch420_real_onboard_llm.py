#!/usr/bin/env python3
"""
PATCH-420 — Fix the onboard LLM fallback stub
==============================================

WHAT THIS IS:
  Rewires llm_provider.py's _onboard_fallback() to actually invoke the
  local Ollama phi3 model instead of returning the canned string
  "[Murphy Onboard] API providers unavailable. Request acknowledged: ...".

WHY IT EXISTS:
  Bug discovered while testing PATCH-419: when DeepInfra and Together both
  fail, llm_provider returns prompt-as-response rather than running actual
  inference. forge_engine.py already had to add a detector for this stub
  string at line 231 because the silent-fail polluted downstream code.

  Fix at the source: call the working _query_ollama() helper that already
  exists in local_llm_fallback.py, and only fall back to the canned string
  if Ollama itself is unreachable.

HOW IT FITS:
  - One function rewrite in src/llm_provider.py
  - Uses _query_ollama from local_llm_fallback (same module Murphy already
    depends on)
  - Preserves LLMCompletion shape so callers see no change
  - Provider field becomes "onboard_ollama" when Ollama succeeds so the
    cost ledger can tell real local inference from the stub

LAST UPDATED: 2026-05-25 by PATCH-420
"""
import ast
import shutil
from pathlib import Path

LLM = Path("/opt/Murphy-System/src/llm_provider.py")
src = LLM.read_text()

if "PATCH-420" in src:
    print("  ⚠ PATCH-420 already applied — skipping")
    raise SystemExit(0)

# Locate the exact stub block
OLD = '''    def _onboard_fallback(
        self,
        messages:   List[Dict[str, str]],
        request_id: str,
        budget_summary: Optional[Dict[str, Any]] = None,
    ) -> LLMCompletion:
        """Local deterministic fallback when all API providers are down."""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        preview  = user_msg[:120]
        content  = (
            f"[Murphy Onboard] API providers unavailable. "
            f"Request acknowledged: {preview}"
        )
        logger.warning("Using onboard fallback for request %s", request_id)
        raw: Dict[str, Any] = {}
        if budget_summary is not None:
            raw["budget_summary"] = budget_summary
        return LLMCompletion(
            content=content, model="murphy-onboard", provider="onboard",
            request_id=request_id, success=True, raw_response=raw,
        )'''

NEW = '''    def _onboard_fallback(
        self,
        messages:   List[Dict[str, str]],
        request_id: str,
        budget_summary: Optional[Dict[str, Any]] = None,
    ) -> LLMCompletion:
        """Local Ollama inference fallback when API providers are down.

        PATCH-420: Previously returned the prompt as the response (silent
        stub). Now actually invokes Ollama phi3 via the existing
        _query_ollama helper. Falls through to a clearly-marked stub only
        if Ollama itself is unreachable.
        """
        # Reconstruct a flat prompt from messages (Ollama generate API
        # wants a single prompt string, not an OAI-style messages list).
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        user_parts   = [m["content"] for m in messages if m.get("role") == "user"]
        sys_blob  = "\\n".join(system_parts).strip()
        user_blob = "\\n".join(user_parts).strip()
        flat_prompt = (sys_blob + "\\n\\n" + user_blob).strip() if sys_blob else user_blob

        raw: Dict[str, Any] = {}
        if budget_summary is not None:
            raw["budget_summary"] = budget_summary

        # ── Try real local Ollama first ───────────────────────────────
        try:
            from local_llm_fallback import _query_ollama as _qo
            ollama_response = _qo(
                flat_prompt,
                model="phi3",
                max_tokens=500,
            )
            if ollama_response and isinstance(ollama_response, str) and ollama_response.strip():
                logger.info(
                    "PATCH-420 onboard Ollama OK | request %s | %d chars",
                    request_id, len(ollama_response),
                )
                return LLMCompletion(
                    content=ollama_response.strip(),
                    model="phi3",
                    provider="onboard_ollama",
                    request_id=request_id,
                    success=True,
                    raw_response=raw,
                )
        except Exception as ollama_exc:
            logger.warning(
                "PATCH-420 onboard Ollama failed for %s: %s — falling through to stub",
                request_id, ollama_exc,
            )

        # ── True last resort: Ollama also down → canned response ──────
        preview = user_blob[:120] if user_blob else ""
        content = (
            f"[Murphy Onboard STUB] All LLM providers AND local Ollama "
            f"unreachable. Request acknowledged: {preview}"
        )
        logger.error(
            "PATCH-420: ALL LLM providers down (DeepInfra + Together + Ollama). "
            "Request %s returning stub.",
            request_id,
        )
        return LLMCompletion(
            content=content, model="murphy-onboard-stub", provider="onboard_stub",
            request_id=request_id, success=False, raw_response=raw,
        )'''

if OLD not in src:
    print("  ✗ exact stub block not found — aborting")
    raise SystemExit(1)

new_src = src.replace(OLD, NEW, 1)
ast.parse(new_src)
print("  ✓ AST parses")

backup = LLM.with_suffix(".py.pre-420")
shutil.copy(LLM, backup)
LLM.write_text(new_src)
print(f"  ✓ wrote {LLM} (backup: {backup.name})")
print()
print("Provider behavior after this:")
print("  DeepInfra OK     → provider='deepinfra'   success=True")
print("  Together OK      → provider='together'    success=True")
print("  Ollama OK        → provider='onboard_ollama' success=True  ← PATCH-420 fix")
print("  All down         → provider='onboard_stub'  success=False  ← clearly marked")
