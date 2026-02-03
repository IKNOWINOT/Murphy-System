"""Local text summarization using transformers."""
from __future__ import annotations

from transformers import pipeline

class LocalSummarizerBot:
    def __init__(self, model_name: str = "sshleifer/distilbart-cnn-12-6") -> None:
        self.summarizer = pipeline("summarization", model=model_name)

    def summarize(self, text: str) -> str:
        return self.summarizer(text, min_length=20, max_length=120)[0]["summary_text"]

class SummaryEvaluatorBot:
    def evaluate(self, text: str, summary: str) -> float:
        if not text:
            return 0.0
        return min(len(summary) / len(text), 1.0)
