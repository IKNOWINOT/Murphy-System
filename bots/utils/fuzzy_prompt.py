"""Utilities for fuzzy matching prompts."""
from __future__ import annotations

from rapidfuzz import fuzz

try:  # optional heavy deps
    from sentence_transformers import SentenceTransformer, util
    from transformers import pipeline
except Exception:  # pragma: no cover - optional
    SentenceTransformer = None  # type: ignore
    util = None  # type: ignore
    pipeline = None  # type: ignore


def best_match(prompt: str, candidates: list[str], threshold: int = 70) -> str | None:
    """Return the best matching candidate or None if below threshold."""
    best = None
    best_score = 0
    for c in candidates:
        score = fuzz.partial_ratio(prompt, c)
        if score > best_score:
            best_score = score
            best = c
    if best_score < threshold:
        return None
    return best


def clarify_prompt(prompt: str, archetypes: list[str], threshold: float = 0.75) -> str | None:
    """Return a clarifying question if prompt is dissimilar to archetypes."""
    if SentenceTransformer is None or util is None or pipeline is None:
        return None
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    clarifier = pipeline("text2text-generation", model="google/flan-t5-base")
    prompt_emb = embedder.encode(prompt, convert_to_tensor=True)
    arch_embs = embedder.encode(archetypes, convert_to_tensor=True)
    scores = util.cos_sim(prompt_emb, arch_embs)[0]
    if float(scores.max()) < threshold:
        result = clarifier(f"Clarify vague request: '{prompt}'", max_length=50)
        return result[0]["generated_text"]
    return None
