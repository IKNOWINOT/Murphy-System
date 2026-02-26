from __future__ import annotations

from typing import List
from .utils import fuzzy_prompt
from .gpt_oss_runner import GPTOSSRunner  # Injected

class ClarifierBot:
    """Detect vague prompts and ask for clarification."""

    def __init__(self, archetypes: List[str] | None = None, threshold: float = 0.65) -> None:
        self.archetypes = archetypes or ["translate", "summarize", "analyze sentiment"]
        self.threshold = threshold

    def maybe_clarify(self, prompt: str) -> str | None:
        return fuzzy_prompt.clarify_prompt(prompt, self.archetypes, self.threshold)


class PromptRefinerBot:
    """Generate clarification questions using GPT-OSS."""

    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.llm = GPTOSSRunner(model_path)

    def clarify(self, prompt: str) -> str:
        system_prompt = f"""
You are a ClarifierBot.
Your job is to take vague or incomplete user prompts and suggest a clarification question.
Only respond with the question. Do not answer it.
Prompt: {prompt}
"""
        return self.llm.chat(system_prompt, temperature=0.5)
