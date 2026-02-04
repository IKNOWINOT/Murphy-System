"""Natural language generation utilities for Kiren."""
from __future__ import annotations

from typing import Optional
import os

try:  # heavy optional deps
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
except Exception:  # pragma: no cover - transformers not available
    torch = AutoModelForCausalLM = AutoTokenizer = None  # type: ignore

try:  # optional API fallback
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore


class KirenSpeak:
    """Wrapper around Hugging Face causal language models."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv("KIREN_MODEL", "gpt2")
        self.tokenizer = None
        self.model = None
        if AutoTokenizer and AutoModelForCausalLM:
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
            except Exception:  # pragma: no cover - model download failure
                self.tokenizer = self.model = None

    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        context: Optional[str] = None,
        max_length: int = 50,
        temperature: float = 0.7,
        seed: Optional[int] = None,
    ) -> str:
        """Generate text using either a local model or remote API."""

        final_prompt = f"{context}\n{prompt}" if context else prompt
        if self.tokenizer and self.model:
            if seed is not None and torch is not None:
                torch.manual_seed(seed)
            inputs = self.tokenizer(final_prompt, return_tensors="pt")
            do_sample = temperature > 0
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_length,
                temperature=temperature if do_sample else None,
                do_sample=do_sample,
            )
            text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)
            return text
        remote = self._generate_remote(final_prompt, max_length, temperature)
        return remote if remote is not None else final_prompt

    # ------------------------------------------------------------------
    def _generate_remote(self, prompt: str, max_length: int, temperature: float) -> Optional[str]:
        if requests is None:
            return None
        api_token = os.getenv("HF_API_TOKEN")
        if not api_token:
            return None
        headers = {"Authorization": f"Bearer {api_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": max_length, "temperature": temperature},
        }
        for model in [self.model_name, "gpt2"]:
            url = f"https://api-inference.huggingface.co/models/{model}"
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=30)
                if resp.ok:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        return data[0].get("generated_text")
                    if isinstance(data, dict):
                        return data.get("generated_text")
            except Exception:  # pragma: no cover - network error
                continue
        return None


_default: KirenSpeak | None = None


def generate_response(
    prompt: str,
    context: Optional[str] = None,
    *,
    max_length: int = 50,
    temperature: float = 0.7,
    seed: Optional[int] = None,
) -> str:
    """Convenience wrapper that lazily instantiates :class:`KirenSpeak`."""

    global _default
    if _default is None:
        _default = KirenSpeak()
    return _default.generate(prompt, context=context, max_length=max_length, temperature=temperature, seed=seed)
