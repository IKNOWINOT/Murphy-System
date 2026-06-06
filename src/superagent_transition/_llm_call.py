"""Shared LLM helper for superagent transition caps.

Calls DeepInfra OpenAI-compat chat completions directly.

Why not llm_provider.complete()?
  As of R28 (2026-06-05), the wrapper returns 'onboard_stub' results
  even though DeepInfra is healthy (verified by direct curl). The
  circuit breakers report state=closed, but something inside
  llm_provider's provider-selection path drops to PATCH-420 stub on
  every call. Logged as BL-R28 for Murphy CTO review.

  This helper is the same shape A.10 generate_image uses for the
  image endpoint — direct HTTPS POST to api.deepinfra.com. Cheap,
  proven, reusable.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

DEEPINFRA_URL = "https://api.deepinfra.com/v1/openai/chat/completions"
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"  # cheap + fast
PREMIUM_MODEL = "meta-llama/Meta-Llama-3.3-70B-Instruct-Turbo"  # better summaries

class LLMError(Exception):
    pass


def _api_key() -> str:
    k = os.environ.get("DEEPINFRA_API_KEY", "")
    if not k:
        try:
            with open("/etc/murphy-production/secrets.env") as f:
                for line in f:
                    if line.startswith("DEEPINFRA_API_KEY="):
                        k = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not k:
        raise LLMError("DEEPINFRA_API_KEY missing")
    return k


def chat_complete(
    messages: List[Dict[str, str]],
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 600,
    temperature: float = 0.3,
    timeout: int = 60,
) -> Dict[str, Any]:
    """Direct DeepInfra chat completion.

    Returns:
      {
        "ok": bool,
        "content": str,
        "model": str,
        "wall_ms": int,
        "input_tokens": int,
        "output_tokens": int,
        "cost_usd": float,
        "error": str | None,
      }
    """
    out: Dict[str, Any] = {
        "ok": False, "content": "", "model": model,
        "wall_ms": 0, "input_tokens": 0, "output_tokens": 0,
        "cost_usd": 0.0, "error": None,
    }
    try:
        body = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }).encode("utf-8")
        req = urllib.request.Request(
            DEEPINFRA_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {_api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        out["wall_ms"] = int((time.time() - t0) * 1000)
        data = json.loads(raw)
        choice = (data.get("choices") or [{}])[0]
        out["content"] = (choice.get("message") or {}).get("content", "")
        usage = data.get("usage") or {}
        out["input_tokens"] = usage.get("prompt_tokens", 0)
        out["output_tokens"] = usage.get("completion_tokens", 0)
        out["cost_usd"] = float(usage.get("estimated_cost", 0))
        out["ok"] = True
        return out
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            body = ""
        out["error"] = f"HTTP {e.code}: {body}"
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        return out
