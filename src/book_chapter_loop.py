"""
R65b-B3 — Book Chapter Loop
============================

WHAT THIS IS
  Wraps Murphy's existing generate_deliverable() in an N-chapter loop with
  continuity tracking. Produces a multi-chapter book where each chapter
  knows the prior chapter's events, characters, and tone.

WHY
  Founder R65 directive: "Murphy should write a 100-page novel about a
  detective named Ada in a near-future Pacific Northwest" — single-pass
  generation tops out around 4-9K characters. A 100-page novel needs
  ~250K characters across 15-25 chapters with continuity.

DESIGN
  - Plan pass: 1 call to generate the chapter outline (titles + 2-sentence
    summary per chapter)
  - Chapter pass: 1 call per chapter, with:
      • The full outline (so the LLM knows what's coming)
      • The previous 2 chapters' last 600 chars (rolling context)
      • A "character ledger" we extract from each chapter
  - Continuity ledger: regex-extract proper nouns (capitalized words that
    appear ≥2 times) after each chapter. Pass forward as known characters.
  - Total cost: 1 plan + N chapters. At ~30s/call, a 12-chapter book ≈ 6.5 min.
  - Each chapter is appended to a single text artifact in /var/lib/murphy-production/books/

PUBLIC SURFACE
  plan_book(premise: str, target_chapters: int = 12) → dict
  generate_chapter(plan: dict, chapter_idx: int, prior_text: str, characters: list) → dict
  write_book(premise: str, target_chapters: int = 12, on_progress=None) → dict
    on_progress(event: dict) → optional callback for SSE wiring

LICENSE: BSL 1.1 — Inoni LLC / Corey Post
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

BOOK_DIR = Path("/var/lib/murphy-production/books")
BOOK_DIR.mkdir(parents=True, exist_ok=True)


def _llm_call(prompt: str, max_tokens: int = 2500) -> str:
    """Call Murphy's existing LLM path. Falls back to deepinfra if available."""
    # Reuse the existing demo_deliverable_generator._generate_llm_content if available
    try:
        from src.demo_deliverable_generator import _generate_llm_content
        result = _generate_llm_content(prompt, max_tokens=max_tokens)
        if result and len(result) > 100:
            return result
    except Exception as e:
        logger.warning(f"primary LLM path failed: {e}")

    # Fallback: direct deepinfra
    try:
        import requests
        api_key = os.environ.get("DEEPINFRA_API_KEY", "")
        if not api_key:
            return f"[LLM unavailable — no DEEPINFRA_API_KEY]\n\n{prompt[:200]}"
        resp = requests.post(
            "https://api.deepinfra.com/v1/openai/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=120,
        )
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"deepinfra fallback failed: {e}")
        return f"[LLM error: {e}]"


def plan_book(premise: str, target_chapters: int = 12) -> Dict:
    """Generate a chapter outline. Returns {title, premise, chapters: [{idx, title, summary}]}."""
    prompt = f"""You are planning a novel. The premise is:

{premise}

Generate a chapter outline with exactly {target_chapters} chapters.
For each chapter, give:
- A short title (≤8 words)
- A 2-sentence summary of what happens in that chapter

Also propose a single book title.

Format your response as JSON only (no other text). Use this exact shape:
{{
  "book_title": "...",
  "logline": "one-sentence pitch",
  "chapters": [
    {{"idx": 1, "title": "...", "summary": "..."}},
    {{"idx": 2, "title": "...", "summary": "..."}},
    ...
  ]
}}
"""
    raw = _llm_call(prompt, max_tokens=2500)
    # Strip code fences if the LLM wraps in ```json
    raw_stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw_stripped = re.sub(r"\s*```$", "", raw_stripped)
    try:
        plan = json.loads(raw_stripped)
    except json.JSONDecodeError:
        # Try to find JSON inside the text
        m = re.search(r"\{.*\}", raw_stripped, re.DOTALL)
        if m:
            try:
                plan = json.loads(m.group(0))
            except json.JSONDecodeError:
                plan = {"book_title": "Untitled", "logline": premise[:120], "chapters": []}
        else:
            plan = {"book_title": "Untitled", "logline": premise[:120], "chapters": []}
    plan["premise"] = premise
    plan["planned_at"] = datetime.now(timezone.utc).isoformat()
    return plan


def extract_characters(text: str, min_occurrences: int = 2) -> List[str]:
    """Pull capitalized proper nouns that appear ≥2 times — a character ledger."""
    # Exclude common sentence-starters and stopwords
    skip = {"The", "A", "An", "He", "She", "It", "They", "We", "I", "You",
            "But", "And", "Or", "So", "When", "Then", "Now", "Here", "There",
            "What", "Where", "Why", "How", "Yes", "No", "Chapter", "One", "Two",
            "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"}
    candidates = re.findall(r"\b([A-Z][a-z]{2,15})\b", text)
    counts = Counter(c for c in candidates if c not in skip)
    return [name for name, n in counts.most_common(20) if n >= min_occurrences]


def generate_chapter(
    plan: Dict,
    chapter_idx: int,
    prior_text: str = "",
    characters: Optional[List[str]] = None,
) -> Dict:
    """Generate a single chapter."""
    chapters = plan.get("chapters", [])
    if chapter_idx > len(chapters):
        return {"error": f"chapter_idx {chapter_idx} > planned {len(chapters)}"}
    this_ch = chapters[chapter_idx - 1]
    # Rolling context: last 600 chars of prior text
    rolling = prior_text[-600:] if prior_text else ""
    char_ledger = ", ".join(characters[:15]) if characters else "(none yet)"

    upcoming = chapters[chapter_idx:chapter_idx + 2]
    upcoming_str = "\n".join(f"- Ch {c['idx']}: {c['title']} — {c['summary']}" for c in upcoming) or "(this is the final chapter)"

    prompt = f"""You are writing Chapter {chapter_idx} of the novel "{plan.get('book_title', 'Untitled')}".

PREMISE: {plan.get('premise', '')}

LOGLINE: {plan.get('logline', '')}

THIS CHAPTER:
Title: {this_ch['title']}
Summary: {this_ch['summary']}

KNOWN CHARACTERS (from prior chapters): {char_ledger}

UPCOMING (so you don't resolve threads too early):
{upcoming_str}

CONTINUITY (last passage of the prior chapter, if any):
{rolling}

Write Chapter {chapter_idx} as continuous prose. Aim for 1800-2500 words.
Open with a scene, not a recap. Show, don't tell. Stay in scene.
Use the known characters by name where appropriate.
End at a natural breath but don't tie up too much.

Begin Chapter {chapter_idx} now with the heading "Chapter {chapter_idx}: {this_ch['title']}".
"""
    text = _llm_call(prompt, max_tokens=3000)
    new_chars = extract_characters(text)
    return {
        "idx": chapter_idx,
        "title": this_ch["title"],
        "text": text,
        "char_count": len(text),
        "word_count": len(text.split()),
        "new_characters": [c for c in new_chars if c not in (characters or [])],
    }


def write_book(
    premise: str,
    target_chapters: int = 12,
    on_progress: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """Top-level: plan + generate every chapter + save artifact."""
    job_id = "book_" + uuid.uuid4().hex[:12]
    started = time.time()

    def emit(event: Dict):
        event["job_id"] = job_id
        event["elapsed_ms"] = round((time.time() - started) * 1000)
        if on_progress:
            try:
                on_progress(event)
            except Exception:
                pass

    emit({"type": "plan_start", "msg": "Planning chapters"})
    plan = plan_book(premise, target_chapters=target_chapters)
    emit({
        "type": "plan_done",
        "book_title": plan.get("book_title"),
        "logline": plan.get("logline"),
        "chapter_count": len(plan.get("chapters", [])),
    })

    chapters_out: List[Dict] = []
    full_text_parts: List[str] = [
        f"# {plan.get('book_title', 'Untitled')}\n\n",
        f"_{plan.get('logline', '')}_\n\n",
        "---\n\n",
    ]
    characters: List[str] = []
    prior_text = ""

    for i, ch_plan in enumerate(plan.get("chapters", []), start=1):
        emit({"type": "chapter_start", "idx": i, "title": ch_plan["title"]})
        ch = generate_chapter(plan, i, prior_text=prior_text, characters=characters)
        chapters_out.append(ch)
        full_text_parts.append(ch.get("text", "") + "\n\n---\n\n")
        prior_text = ch.get("text", "")
        for new in ch.get("new_characters", []):
            if new not in characters:
                characters.append(new)
        emit({
            "type": "chapter_done",
            "idx": i,
            "title": ch_plan["title"],
            "word_count": ch.get("word_count", 0),
            "char_count": ch.get("char_count", 0),
            "new_characters": ch.get("new_characters", []),
        })

    full_text = "".join(full_text_parts)
    artifact_path = BOOK_DIR / f"{job_id}.md"
    artifact_path.write_text(full_text, encoding="utf-8")

    elapsed_s = round(time.time() - started)
    result = {
        "ok": True,
        "job_id": job_id,
        "book_title": plan.get("book_title"),
        "logline": plan.get("logline"),
        "chapters": chapters_out,
        "total_words": sum(c.get("word_count", 0) for c in chapters_out),
        "total_chars": sum(c.get("char_count", 0) for c in chapters_out),
        "artifact_path": str(artifact_path),
        "artifact_url": f"/api/books/{job_id}/download",
        "characters_extracted": characters,
        "elapsed_s": elapsed_s,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    emit({"type": "book_done", **{k: v for k, v in result.items() if k != "chapters"}})
    return result


if __name__ == "__main__":
    # Smoke test: 3-chapter mini-book to keep cost low
    def progress(ev):
        print(f"  [{ev.get('elapsed_ms', 0):>6}ms] {ev.get('type')}: {ev.get('title') or ev.get('msg') or ev.get('book_title') or ''}")
    result = write_book(
        "A retired detective named Ada in a near-future Seattle investigates why her old partner's death keeps changing in the public record.",
        target_chapters=3,
        on_progress=progress,
    )
    print(f"\n  Book: {result['book_title']}")
    print(f"  Words: {result['total_words']:,}  Chars: {result['total_chars']:,}")
    print(f"  Time:  {result['elapsed_s']}s")
    print(f"  File:  {result['artifact_path']}")
