"""LLM backend utilities using GPT-OSS transformers."""
from __future__ import annotations

from .gpt_oss_runner import GPTOSSRunner

class LLMBackend:
    """Wrapper around GPT-OSS model execution using GPTOSSRunner."""

    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.model_path = model_path
        self.runner = GPTOSSRunner(model_path=self.model_path)

    def generate(self, prompt: str, max_length: int = 100) -> str:
        """Generate text using GPT-OSS backend."""
        return self.runner.chat(prompt, stop_token=None)

# Lazy singleton pattern
_default_backend: LLMBackend | None = None

def generate_text(prompt: str, max_length: int = 100) -> str:
    """Global utility to invoke GPT-OSS text generation."""
    global _default_backend
    if _default_backend is None:
        _default_backend = LLMBackend()
    return _default_backend.generate(prompt, max_length)
