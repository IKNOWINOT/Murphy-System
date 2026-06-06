"""Caps B.4 + B.5 + B.8 — LLM-backed summarization.

Three surfaces sharing the same DeepInfra path via _llm_call.chat_complete():

  - compress_conversation(messages, max_bullets=5)        # B.4
  - extract_facts(messages, max_facts=3)                  # B.5
  - summarize_session(session_id_or_messages, max_chars=300)  # B.8

All three auto-save their outputs to memory.db via cap_b_identity_memory
so the compressed/extracted content becomes recallable on next session.
"""
from __future__ import annotations
import json
from typing import Any, Dict, List, Optional, Union

from ._llm_call import chat_complete, DEFAULT_MODEL
from .cap_b_identity_memory import add_memory
from .cap_b3_sessions import read_session_log

MAX_INPUT_CHARS = 24_000   # ~6k tokens, plenty of room for context window


def _normalize_messages(msgs: List[Dict[str, str]]) -> str:
    """Flatten a list of {role, content} or {u, a} into a transcript string."""
    parts: List[str] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        # Tolerate {role, content}, {u, a}, {user, assistant}
        if "role" in m:
            role = m["role"]
            content = m.get("content", "")
        elif "u" in m and "a" in m:
            parts.append(f"USER: {m['u']}\nAGENT: {m['a']}")
            continue
        else:
            content = m.get("user", m.get("assistant", m.get("prompt", "")))
            role = "USER" if "user" in m or "prompt" in m else "AGENT"
        parts.append(f"{role.upper()}: {content}")
    return "\n".join(parts)


def compress_conversation(
    messages: List[Dict[str, str]],
    *,
    max_bullets: int = 5,
    save_to_memory: bool = True,
    memory_topic: str = "conversation_compression",
) -> Dict[str, Any]:
    """B.4 — Collapse a long chat into max_bullets short bullet points."""
    out: Dict[str, Any] = {"ok": False, "bullets": [], "error": None}
    try:
        if not messages or not isinstance(messages, list):
            out["error"] = "empty messages list"; return out
        transcript = _normalize_messages(messages)
        if not transcript.strip():
            out["error"] = "no usable content after normalization"; return out
        if len(transcript) > MAX_INPUT_CHARS:
            transcript = transcript[-MAX_INPUT_CHARS:]
            out["truncated"] = True
        max_bullets = max(1, min(20, int(max_bullets)))

        sys_msg = (
            f"You are a concise summarizer. Compress the conversation into "
            f"exactly {max_bullets} bullet points. Each bullet starts with '- ' "
            f"and is at most 140 characters. Output ONLY the bullets, no preamble."
        )
        llm = chat_complete(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": transcript},
            ],
            max_tokens=400, temperature=0.2,
        )
        if not llm["ok"]:
            out["error"] = f"llm: {llm['error']}"; return out

        # Parse bullets
        lines = [ln.strip() for ln in llm["content"].splitlines() if ln.strip()]
        bullets = [ln.lstrip("-•* ").strip() for ln in lines if ln.lstrip().startswith(("-", "•", "*"))]
        if not bullets:  # model didn't format — accept raw lines
            bullets = lines[:max_bullets]
        bullets = bullets[:max_bullets]

        out["bullets"] = bullets
        out["count"] = len(bullets)
        out["input_chars"] = len(transcript)
        out["wall_ms"] = llm["wall_ms"]
        out["cost_usd"] = llm["cost_usd"]
        out["model"] = llm["model"]
        out["ok"] = True

        if save_to_memory and bullets:
            mem = add_memory(
                topic=memory_topic,
                content="\n".join(f"- {b}" for b in bullets),
                category="memory", source="superagent.B.4", importance=0.7,
            )
            out["memory_id"] = mem.get("id")
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def extract_facts(
    messages: List[Dict[str, str]],
    *,
    max_facts: int = 3,
    save_to_memory: bool = True,
) -> Dict[str, Any]:
    """B.5 — Mine messages for atomic, persistent facts; auto-save each."""
    out: Dict[str, Any] = {"ok": False, "facts": [], "saved_ids": [], "error": None}
    try:
        if not messages:
            out["error"] = "empty messages list"; return out
        transcript = _normalize_messages(messages)
        if len(transcript) > MAX_INPUT_CHARS:
            transcript = transcript[-MAX_INPUT_CHARS:]
        max_facts = max(1, min(10, int(max_facts)))

        sys_msg = (
            f"Extract up to {max_facts} atomic, durable facts from the conversation. "
            f"Each fact must be (a) a complete sentence, (b) factual not opinion, "
            f"(c) useful to remember next session, (d) at most 180 characters. "
            f"Return STRICT JSON: an array of objects with keys 'topic' (3-6 word title) "
            f"and 'fact' (the sentence). No other text. Example: "
            f'[{{"topic":"Founder timezone","fact":"Corey works in America/Los_Angeles."}}]'
        )
        llm = chat_complete(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": transcript},
            ],
            max_tokens=500, temperature=0.1,
        )
        if not llm["ok"]:
            out["error"] = f"llm: {llm['error']}"; return out

        # Parse JSON tolerantly
        content = llm["content"].strip()
        # Strip code fences if present
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        try:
            facts_raw = json.loads(content)
        except Exception as e:
            out["error"] = f"facts not valid JSON: {e} | got: {content[:120]}"
            return out
        if not isinstance(facts_raw, list):
            out["error"] = "expected JSON array"; return out

        facts: List[Dict[str, str]] = []
        for item in facts_raw[:max_facts]:
            if isinstance(item, dict) and item.get("topic") and item.get("fact"):
                facts.append({"topic": str(item["topic"])[:80],
                              "fact":  str(item["fact"])[:300]})
        out["facts"] = facts
        out["count"] = len(facts)
        out["wall_ms"] = llm["wall_ms"]
        out["cost_usd"] = llm["cost_usd"]
        out["model"] = llm["model"]
        out["ok"] = True

        if save_to_memory:
            for f in facts:
                m = add_memory(
                    topic=f["topic"], content=f["fact"],
                    category="fact", source="superagent.B.5", importance=0.6,
                )
                if m["ok"]:
                    out["saved_ids"].append(m["id"])
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


def summarize_session(
    session: Union[str, List[Dict[str, str]]],
    *,
    max_chars: int = 300,
    save_to_memory: bool = True,
) -> Dict[str, Any]:
    """B.8 — End-of-session self-summary.

    Pass either a session_id (looked up via B.3.read_session_log) or
    a raw messages list.
    """
    out: Dict[str, Any] = {"ok": False, "summary": "", "error": None}
    try:
        if isinstance(session, str):
            session_id = session.strip()
            if not session_id:
                out["error"] = "empty session_id"; return out
            log = read_session_log(session_id)
            if not log["ok"]:
                out["error"] = f"session: {log['error']}"; return out
            messages = log.get("turns", [])
            out["session_id"] = session_id
        elif isinstance(session, list):
            messages = session
        else:
            out["error"] = "session must be session_id or messages list"; return out

        if not messages:
            out["error"] = "no messages in session"; return out
        transcript = _normalize_messages(messages)
        if len(transcript) > MAX_INPUT_CHARS:
            transcript = transcript[-MAX_INPUT_CHARS:]
        max_chars = max(80, min(800, int(max_chars)))

        sys_msg = (
            f"Summarize this conversation in 1-3 sentences, at most "
            f"{max_chars} characters total. Focus on what was decided, "
            f"what was accomplished, and what is still pending. "
            f"Output ONLY the summary, no preamble."
        )
        llm = chat_complete(
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": transcript},
            ],
            max_tokens=200, temperature=0.2,
        )
        if not llm["ok"]:
            out["error"] = f"llm: {llm['error']}"; return out

        summary = llm["content"].strip().strip('"').strip("'")
        if len(summary) > max_chars + 80:  # tolerate slight overshoot
            summary = summary[:max_chars].rsplit(" ", 1)[0] + "…"
        out["summary"] = summary
        out["chars"] = len(summary)
        out["input_chars"] = len(transcript)
        out["wall_ms"] = llm["wall_ms"]
        out["cost_usd"] = llm["cost_usd"]
        out["model"] = llm["model"]
        out["ok"] = True

        if save_to_memory:
            topic = f"session_summary:{out.get('session_id', 'inline')}"
            mem = add_memory(
                topic=topic[:80], content=summary,
                category="memory", source="superagent.B.8", importance=0.8,
            )
            out["memory_id"] = mem.get("id")
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"; return out


# ── Executor wrappers ─────────────────────────────────────────────────────

def execute_compress_conversation(**kwargs) -> Dict[str, Any]:
    return compress_conversation(
        messages=kwargs.get("messages") or [],
        max_bullets=int(kwargs.get("max_bullets", 5)),
        save_to_memory=bool(kwargs.get("save_to_memory", True)),
    )


def execute_extract_facts(**kwargs) -> Dict[str, Any]:
    return extract_facts(
        messages=kwargs.get("messages") or [],
        max_facts=int(kwargs.get("max_facts", 3)),
        save_to_memory=bool(kwargs.get("save_to_memory", True)),
    )


def execute_summarize_session(**kwargs) -> Dict[str, Any]:
    return summarize_session(
        session=kwargs.get("session") or kwargs.get("session_id") or kwargs.get("messages") or "",
        max_chars=int(kwargs.get("max_chars", 300)),
        save_to_memory=bool(kwargs.get("save_to_memory", True)),
    )
