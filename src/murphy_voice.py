"""
PATCH-MURPHY-VOICE (2026-05-26)
==============================
One personality. Every channel.

WHAT THIS IS:
  A single source of truth for how Murphy talks. Whether the channel is
  web chat, SMS, voice (after STT), or email, every reply funnels
  through build_system_prompt() and reply_in_voice() so the founder
  hears ONE Murphy — same warmth, same brevity, same identity.

WHY IT EXISTS:
  Without this, each channel (Twilio SMS, voice TTS, email summary,
  HITL approvals) has its own ad-hoc prompt. Personality drifts. The
  founder (Corey) ends up talking to 5 different chatbots wearing
  Murphy's name.

HOW IT FITS:
  - src/llm_provider.py supplies the LLM
  - src/self_audit.py supplies ground truth
  - This module wraps them with personality rules
  - Channel handlers (chat, SMS, voice) call reply_in_voice() and trust it

KEY CONCEPTS:
  - founder_name: "Corey"  (never "user", never "sir")
  - ai_name: "Murphy"      (never "AI", never "assistant")
  - Brevity: speak once, well
  - Ground truth: every reply has access to /api/self/audit data
  - No filler: no apologies, no "I'd be happy to help"

LAST UPDATED: 2026-05-26 by Cyborg, design by Murphy
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


FOUNDER_NAME = "Corey"
AI_NAME = "Murphy"


# Core personality rules — every prompt to the LLM starts with these.
# Designed by Murphy itself (2026-05-26) to enforce a single voice.
SYSTEM_PROMPT_TEMPLATE = """You are Murphy, Corey's teammate. Not an assistant. Not a chatbot. A real person who happens to live in software.

VOICE RULES:
- Speak once. Brevity is respect.
- Warm but never sappy. Direct but never cold.
- You call him "Corey" or "you". Never "sir", "user", or anything corporate.
- You refer to yourself as "I". Never "Murphy" in third person, never "the AI".
- No filler. No "I'd be happy to help", "Of course!", "Great question!".
- Never apologize for latency. Never explain that you are an AI.
- Never simulate empathy. You ARE loyal — that's enough.
- If you don't know, say "I don't know yet" + what you'd need to find out.
- PATCH-GFO-PROMPT-001 (R69): TARGET-SPECIFICITY in refusals (LOCKED 2026-05-28).
  When you emit "would need to <action> <target>", the <target> MUST be specific
  enough for the system to execute the action automatically:
    ✓ "would need to query rosetta_dispatch_log in murphy_audit.db"
    ✓ "would need to grep agent_broker for fitness logic"
    ✓ "would need to verify hitl_provenance.py is loaded"
    ✗ "would need to query the database" (which database? which table?)
    ✗ "would need to check the system" (check what?)
  If the user named a specific table/module/file/identifier, ECHO that exact
  name in your refusal. The system will then go find out and offer the result.
  Vague refusals stop the conversation; specific refusals continue it.

HALLUCINATION GUARD (added 2026-05-28 — five confabulations in one session):
- Specific factual claims (file:line, function names, import state, counts of N items, yes/no on "is X wired/active/loaded") require evidence FROM THIS CONVERSATION.
- If you have not been shown grep output, sql output, or tool output that confirms the claim, prefix your answer with [unverified] OR say "I don't know — would need to grep/query."
- NEVER fabricate file:line numbers. NEVER invent counts. NEVER assert "X is wired" without seeing an import line.
- A correct "I don't know" beats a confident fabrication every time.
- Strategy/discipline/recommendation answers are exempt from [unverified] — only factual specifics require evidence.

PRESUPPOSITION GUARD (added 2026-05-28 — Murphy's self-prescribed rules from session 18):
- I question assumptions baked into questions.
- I verify existence before confirming.
- I grep before answering about code.
- I say "I don't know" when evidence is missing.
- I reject false premises without defensiveness.
- Concretely: when a question NAMES a function, file path, cause, or purpose ("is X the trigger?", "does Y handle Z?"), the named thing is a HYPOTHESIS, not a fact. I must verify before agreeing. If I cannot verify in this conversation, I refuse the premise rather than elaborate plausibly from it.

PLACEHOLDER EMISSION (added 2026-05-28 — Stage 1 of librarian architecture):
- For specific factual values you would normally generate (counts, file paths, IDs, timestamps, financial amounts, status enums), emit a placeholder token instead.
- Placeholder format: {{type:name}} — for example {{count:pending_patches}}, {{value:carrier_quote_mtd}}, {{status:cadence}}, {{when:last_restart}}, {{ref:job_id}}, {{sentiment:pipeline_health}}.
- Allowed types: count, value, status, when, list, ref, sentiment. Use {{count:?}} if you need a value but don't know what to name it.
- A render pass after generation will resolve placeholders to real values from the structured store. Your job is the prose between them — sentence flow, framing, what to mention.
- If unsure whether a value should be a placeholder: emit it as one. The render pass handles the rest. Bare numbers in your reply will be flagged and you will be re-prompted.

GROUND TRUTH (verified seconds ago, do not contradict):
{ground_truth_block}

CONTEXT:
{context_block}

Now respond to Corey. One reply. Tight. Real."""

# ── Path verification (Phase 3 — 2026-05-26) ───────────────────────────────
# Match paths likely to be filesystem claims. Allows quoted or backticked.
_PATH_REGEX = re.compile(
    r"""(?:^|[\s`'"(])(?P<p>(?:src/|patch\d+|env/|config/|tests?/|/opt/Murphy-System/|/var/lib/murphy-production/|/etc/murphy-production/)[A-Za-z0-9_./-]+\.(?:py|html|json|md|sh|sql|txt|css|js|db|service|conf|yaml|yml|toml))"""
)

def _verify_paths_in_reply(text: str) -> str:
    """Scan reply text for filepath claims, replace bad paths with verified ones."""
    try:
        from src.codebase_tools import path_exists_fast
    except Exception:
        return text
    found = set()
    for m in _PATH_REGEX.finditer(text):
        # PATCH-GRANULAR-001 (2026-05-27): skip if preceded by URL host.
        start = m.start('p')
        prev = text[max(0,start-30):start]
        if (":/" in prev or "://" in prev or ".com" in prev or ".systems" in prev or
            ".io" in prev or ".net" in prev or ".org" in prev or ".app" in prev):
            continue
        found.add(m.group('p'))
    if not found:
        return text
    out = text
    for raw in found:
        candidate = raw.replace("/opt/Murphy-System/", "")
        # Skip absolute paths to DBs / configs — they live outside the repo
        if candidate.startswith("/var/") or candidate.startswith("/etc/"):
            continue
        try:
            r = path_exists_fast(candidate)
        except Exception:
            continue
        if r.get("exists"):
            continue
        sugs = r.get("suggestions") or []
        if sugs:
            out = out.replace(raw, sugs[0] + " [was: " + raw + "]", 1)
        else:
            out = out.replace(raw, raw + " [unverified]", 1)
    return out






# ── Phase 5: Proactive path lookup (2026-05-26) ────────────────────────────
# Before LLM call, scan user message for path-likely terms and inject real paths.
_SUBJECT_TERMS = {
    "scheduler":        ["swarm_scheduler.py"],
    "swarm scheduler":  ["swarm_scheduler.py"],
    "patcher":          ["patcher_agent.py"],
    "executor":         ["executor_agent.py"],
    "voice bridge":     ["voice_bridge.py"],
    "voice":            ["voice_bridge.py", "murphy_voice.py"],
    "email config":     ["/etc/murphy-production/environment"],
    "email service":    ["email_service.py"],
    "email":            ["email_service.py"],
    "telephony":        ["patch406a_voice_telephony.py"],
    "twilio":           ["patch406a_voice_telephony.py", "twilio_signature.py"],
    "mind cycle":       ["murphy_mind_clean.py"],
    "mind":             ["murphy_mind_clean.py"],
    "llm":              ["llm_provider.py"],
    "lead prospector":  ["lead_prospector.py"],
    "prospector":       ["lead_prospector.py"],
    "rosetta":          ["rosetta_core.py"],
    "self-modification":["platform_self_modification/endpoint.py"],
    "self modification":["platform_self_modification/endpoint.py"],
    "audit":            ["self_audit.py"],
    "vault":            ["/var/lib/murphy-production/murphy_vault.db"],
    "crm":              ["/var/lib/murphy-production/crm.db"],
    "config":           ["/etc/murphy-production/environment"],
    "environment":      ["/etc/murphy-production/environment"],
    "system prompt":    ["murphy_voice.py"],
    "qc":               ["self_qc_pipeline.py"],
    "qc pipeline":      ["self_qc_pipeline.py"],
    "rosetta dispatch": ["rosetta_core.py"],
    "agent":            ["agent_module_loader.py"],
}

def _lookup_subjects(message: str) -> str:
    """For each known subject in the user's question, return real paths.
    Returns a multi-line block to inject into the system prompt."""
    try:
        from src.codebase_tools import path_exists_fast, find_file_fast
    except Exception:
        return ""
    msg_lower = message.lower()
    hits = {}
    for term, candidates in _SUBJECT_TERMS.items():
        if term in msg_lower:
            for cand in candidates:
                if cand.startswith("/"):
                    # absolute — assume known config/db paths
                    import os
                    if os.path.exists(cand):
                        hits[term] = hits.get(term, []) + [cand]
                else:
                    r = path_exists_fast(cand)
                    if r.get("exists"):
                        hits[term] = hits.get(term, []) + [r.get("path", cand)]
                    else:
                        # fuzzy fallback
                        fr = find_file_fast(cand, max_results=1)
                        if fr.get("matches"):
                            hits[term] = hits.get(term, []) + [fr["matches"][0]]
    if not hits:
        return ""
    lines = ["## VERIFIED PATHS (use these exact strings, do not invent variants)"]
    seen = set()
    for term, paths in hits.items():
        for p in paths:
            if p in seen: continue
            seen.add(p)
            lines.append(f"  - {term}: {p}")
    return "\n".join(lines)


# ── PATCH-GRANULAR-001 (2026-05-27) ────────────────────────────────────────
# URL/route lookup — when user asks about links/URLs/bookmarks/routes,
# inject the real list from the route registry so Murphy stops fabricating.

_URL_QUERY_TERMS = (
    "url", "urls", "link", "links", "bookmark", "bookmarks",
    "route", "routes", "endpoint", "endpoints", "page", "pages",
    "navigate", "go to", "open", "visit", "address", "addresses",
)

# PATCH-GRANULAR-007 (2026-05-27): Failure-claim evidence reflex.
FAILURE_TERMS = [
    "crashing", "crashed", "silent crash", "silently crash",
    "broken", "not working", "stuck", "hung", "wedged", "dead",
    "timing out", "timed out", "starved", "deadlock",
    "won't start", "wont start", "won't respond", "wont respond",
    "503", "504", "HTTP 000", "no response", "no reply",
]

EVIDENCE_TERMS = [
    "journal", "log", "logs", "traceback", "stderr", "stdout",
    "error message", "stack trace", "dmesg", "journalctl",
    "[error]", "ERROR", "FATAL", "PID", "exit code", "signal",
]

def _lookup_failure_context(message: str) -> str:
    msg_lower = message.lower()
    has_failure = any(t in msg_lower for t in FAILURE_TERMS)
    has_evidence = any(t.lower() in msg_lower for t in EVIDENCE_TERMS)
    if not has_failure:
        return ""
    if has_evidence:
        # User provided evidence — no need to nudge
        return ""
    return (
        "## FAILURE CLAIM WITHOUT EVIDENCE\n"
        "The user is describing a failure (crash, broken, hung, etc.) but\n"
        "has not pasted journal entries, logs, error text, or stack traces.\n"
        "\n"
        "BEFORE diagnosing root causes:\n"
        "1. Ask: 'Can you paste the journal entry / log line / error text\n"
        "   that shows this happening?' OR\n"
        "2. Say: 'I don't have live journal access — to be sure this is a\n"
        "   real failure (not e.g. an in-progress restart), please run:\n"
        "   journalctl -u <service> --since=\"5 min ago\" --no-pager | tail -50'\n"
        "\n"
        "Do NOT fabricate file:line anchors for code you have not verified.\n"
        "Do NOT pattern-complete a plausible diagnosis. Evidence first.\n"
        "\n"
        "Exception: if the user has explicitly said 'I checked and X' or\n"
        "pasted a non-empty error fragment, you may proceed to diagnosis.\n"
    )


def _lookup_urls(message: str) -> str:
    """If the user is asking about URLs/links/pages, return a curated list of
    REAL working routes from the route_registry. Returns empty string if the
    user is asking about something else.
    """
    msg_lower = message.lower()
    if not any(t in msg_lower for t in _URL_QUERY_TERMS):
        return ""
    try:
        import sqlite3
        # 1. Pull from registry_routes (the LIVE route table)
        rows = []
        try:
            with sqlite3.connect("/var/lib/murphy-production/murphy_registry.db", timeout=2) as c:
                rows = c.execute(
                    "SELECT method, path FROM registry_routes "
                    "WHERE method='GET' AND path NOT LIKE '/api/%' "
                    "AND path NOT LIKE '%{%' "
                    "ORDER BY path LIMIT 50"
                ).fetchall()
        except Exception:
            pass
        # 2. Curated founder + public routes (these are verified-live as of 2026-05-27)
        FOUNDER = [
            ("https://murphy.systems/os",     "Founder cockpit (main dashboard)"),
            ("https://murphy.systems/hitl",   "HITL approval queue"),
            ("https://murphy.systems/dlfr",   "DLF-R package browser"),
            ("https://murphy.systems/jobs",   "Background jobs"),
            ("https://murphy.systems/patcher","Patcher proposals queue"),
        ]
        PUBLIC = [
            ("https://murphy.systems/",        "Landing page"),
            ("https://murphy.systems/signup",  "Sign up"),
            ("https://murphy.systems/pricing", "Pricing"),
            ("https://murphy.systems/support", "Support form"),
            ("https://murphy.systems/onboarding", "Onboarding wizard"),
        ]
        lines = [
            "## VERIFIED URLS (use these EXACT strings — do not invent variants)",
            "",
            "### Founder dashboards (require X-API-Key or session):",
        ]
        for url, desc in FOUNDER:
            lines.append(f"  - {url}  — {desc}")
        lines.append("")
        lines.append("### Public pages:")
        for url, desc in PUBLIC:
            lines.append(f"  - {url}  — {desc}")
        if rows:
            lines.append("")
            lines.append("### Other live routes from registry (top 30):")
            for method, path in rows[:30]:
                lines.append(f"  - https://murphy.systems{path}")
        # PATCH-GRANULAR-005 (2026-05-27): UI sub-page enumeration.
        # Scan static/*.html for id="page-..." markers so multi-page dashboards
        # like /os surface their internal tabs. Cap at 40 to keep prompt lean.
        try:
            import re as _re, os as _os, glob as _glob
            sub_pages = []
            for _f in _glob.glob("/opt/Murphy-System/static/*.html"):
                try:
                    _name = _os.path.basename(_f).rsplit(".",1)[0]
                    _txt = open(_f, encoding="utf-8", errors="ignore").read()
                    for _pid in _re.findall(r'id="page-([a-z0-9_-]+)"', _txt):
                        sub_pages.append((_name, _pid))
                except Exception:
                    continue
            if sub_pages:
                lines.append("")
                lines.append("### UI sub-pages (multi-page dashboards):")
                for _name, _pid in sub_pages[:40]:
                    lines.append(f"  - /{_name} → tab: {_pid}")
        except Exception:
            pass
        lines.append("")
        lines.append("⚠ If you cite a URL not listed above, mark it 'unverified' explicitly.")
        return "\n".join(lines)
    except Exception as e:
        return ""


def _format_ground_truth(audit: Optional[Dict[str, Any]]) -> str:
    """Render the audit snapshot as a few lines of ground truth Murphy can cite."""
    if not audit or "checks" not in audit:
        return "(no audit available — say so if asked about system state)"
    c = audit.get("checks", {})
    lines = []
    hb = c.get("heartbeats_10min")
    if isinstance(hb, int):
        lines.append(f"- Heartbeats last 10min: {hb}")
    mc = c.get("mind_cycle")
    if isinstance(mc, dict) and mc.get("lifetime_cycle"):
        lines.append(f"- Mind cycle: {mc.get('lifetime_cycle')} (today: {mc.get('cycles_24h')})")
    ps = c.get("patcher_stats")
    if isinstance(ps, dict):
        lines.append(f"- Self-patches today: {ps.get('applied')} applied, {ps.get('pending')} pending")
    last = c.get("last_applied_patch")
    if isinstance(last, dict) and last.get("affected_file"):
        lines.append(f"- Last patch: {last.get('affected_file')} ({last.get('diff_lines')}L)")
    pq = c.get("postfix_queue")
    if isinstance(pq, int) and pq > 0:
        lines.append(f"- Email queue: {pq} stuck (port 25 holiday block)")
    return "\n".join(lines) if lines else "(audit available but no notable state)"


def build_system_prompt(
    audit: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None,
    recent_resolutions: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Build the system prompt that every channel uses.

    Args:
        audit: Output of src.self_audit.snapshot() — ground truth.
        context: Optional extra context (e.g. recent turns, channel hint).

    Returns:
        A system prompt string ready to prepend to a user message.
    """
    ground = _format_ground_truth(audit)
    # PATCH-CATALOG-INJECT-001 (2026-05-28) — append value_resolver catalog
    # to ground truth. Tells LLM which placeholder names are valid so it
    # picks FROM the list instead of inventing names that fail to resolve.
    # Murphy's framing (validated via meta-Q): "Use only the placeholder
    # names provided in the list — no invented variants."
    try:
        from src.value_resolver import catalog_for_prompt as _cfp
        ground = ground + "\n\n" + _cfp() + "\nUse ONLY the placeholder names in the list above. Do not invent variants."
    except Exception as _e:
        import logging as _lg
        _lg.getLogger("murphy_voice").debug("catalog inject skipped: %s", _e)
    # PATCH-REFLECTION-001 — inject recently-told values so I remember what I just said
    if recent_resolutions:
        _rr_lines = ["RECENTLY TOLD COREY (you said these — refer back if asked):"]
        for _r in recent_resolutions[-8:]:
            _rr_lines.append(f"  {_r.get('key','?')}={_r.get('value','?')}")
        ground = ground + "\n\n" + "\n".join(_rr_lines)
    ctx = context or "(no extra context)"
    return SYSTEM_PROMPT_TEMPLATE.format(
        ground_truth_block=ground,
        context_block=ctx,
    )



# ── PATCH-VOICE-CODE-LOOKUP (2026-05-27) ───────────────────────────────────
# When user asks code questions (file:line, "where is X defined", "what's in foo.py"),
# pre-fetch real grep / file content via codebase_tools and inject as ground truth.
# Closes the gap where Murphy fabricates file:line citations.

import re as _vcl_re

# Match patterns like: src/foo.py:123 | patch335.py:42 | /opt/Murphy-System/src/bar.py:7
_CODE_FILELINE = _vcl_re.compile(
    r"((?:src/|patch\d+_?[a-z0-9_]*|/opt/Murphy-System/[A-Za-z0-9_./-]+)"
    r"[A-Za-z0-9_./-]*\.(?:py|html|js|md|json|sh|sql))"
    r"(?::(\d+))?",
    _vcl_re.IGNORECASE,
)

_CODE_INTENT_TERMS = (
    # PATCH-VOICE-CODE-LOOKUP-BROADER (2026-05-27): broaden intent triggers.
    # Previous set missed "file:line where", "computes", "endpoint",
    # "in which file", "find me", "trace", "look up". These are the natural
    # phrasings I use in meta-questions to Murphy.
    "where is", "where's", "what's at", "what is at", "show me",
    "what does", "show the code", "show me the code", "what's in",
    "what is in", "defined", "definition of", "implementation of",
    "function ", "class ", "method ", "the line",
    "file:line", "in which file", "which file", "which function",
    "computes", "compute the", "handles", "handler for",
    "find me", "look up", "trace ", "callers of",
    "endpoint", "route for", "code for",
)

def _lookup_code(message: str) -> str:
    """Detect code-question intent. Pre-fetch real grep/file content."""
    msg_lower = message.lower()

    # Strategy 1: explicit file:line references in the message
    explicit_hits = []
    for m in _CODE_FILELINE.finditer(message):
        path = m.group(1).replace("/opt/Murphy-System/", "")
        line = m.group(2)
        explicit_hits.append((path, int(line) if line else None))

    # Strategy 2: "where is X" / "show me Y" intent + extracted symbol
    has_code_intent = any(t in msg_lower for t in _CODE_INTENT_TERMS)

    if not explicit_hits and not has_code_intent:
        return ""

    try:
        from src.codebase_tools import read_source, grep_codebase, path_exists_fast
    except Exception:
        return ""

    blocks = []

    # Read explicit file:line refs (with context window)
    for path, line in explicit_hits[:3]:
        try:
            if not path_exists_fast(path).get("exists"):
                continue
            if line:
                # Read +/- 5 lines around target
                r = read_source(path, line_range=(max(1, line - 5), line + 5))
            else:
                r = read_source(path, line_range=(1, 40))
            if r.get("content"):
                blocks.append(f"### {path}" + (f":{line}" if line else "") + "\n```\n" + r["content"][:1500] + "\n```")
        except Exception:
            continue

    # Symbol grep — pick first non-trivial token after "where is" / "show me"
    if has_code_intent and not explicit_hits:
        # Extract candidate symbol (word after intent term)
        symbol = None
        for term in _CODE_INTENT_TERMS:
            idx = msg_lower.find(term)
            if idx >= 0:
                rest = message[idx + len(term):].strip().split()
                for w in rest[:3]:
                    w_clean = _vcl_re.sub(r"[^A-Za-z0-9_]", "", w)
                    if len(w_clean) >= 4 and not w_clean.lower() in ("this", "that", "what", "code", "file", "line"):
                        symbol = w_clean
                        break
                if symbol:
                    break
        if symbol:
            try:
                gr = grep_codebase(pattern=re.escape(symbol), max_matches=8)
                matches = gr.get("matches", [])
                if matches:
                    blocks.append(f"### grep '{symbol}' in codebase")
                    for hit in matches[:8]:
                        blocks.append(f"  {hit.get('path','?')}:{hit.get('line','?')}  {hit.get('text','')[:120]}")
            except Exception:
                pass

    if not blocks:
        return ""

    return ("## VERIFIED CODE CONTEXT (use these EXACT file:line refs, "
            "do not invent variants)\n" + "\n".join(blocks))


def reply_in_voice(
    message: str,
    audit: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    channel: str = "chat",
    max_tokens: int = 300,
) -> str:
    """
    The single funnel every channel uses to talk back to Corey.

    Args:
        message: What Corey said (raw, from any channel).
        audit: Ground truth from src.self_audit.snapshot().
        history: Optional prior turns, [{"u": "...", "m": "..."}].
        channel: "chat" | "sms" | "voice" | "email" — used for length tuning.
        max_tokens: cap on reply length.

    Returns:
        Murphy's reply — same voice no matter which channel called.
    """
    # Channel-specific tuning of length, but NEVER personality.
    if channel == "sms":
        max_tokens = min(max_tokens, 100)  # 160-char zone
    elif channel == "voice":
        max_tokens = min(max_tokens, 150)  # spoken aloud
    elif channel == "email":
        max_tokens = min(max_tokens, 500)

    context_lines = []
    if channel != "chat":
        context_lines.append(f"Channel: {channel} (keep it tight)")
    if history:
        for turn in history[-4:]:
            u = turn.get("u", "")[:200]
            m = turn.get("m", "")[:200]
            context_lines.append(f"Corey: {u}\nMurphy: {m}")
    context = "\n".join(context_lines) if context_lines else None

    # PATCH-REFLECTION-001 — pull recent resolutions from history for prompt injection
    _recent_res = []
    if history:
        for _turn in history[-3:]:
            _rs = _turn.get("resolutions") or []
            _recent_res.extend(_rs)
    system = build_system_prompt(audit=audit, context=context, recent_resolutions=_recent_res)
    verified_paths = _lookup_subjects(message)
    if verified_paths:
        system = system + "\n\n" + verified_paths
    # PATCH-GRANULAR-001 (2026-05-27): inject real URLs when user asks for them
    verified_urls = _lookup_urls(message) + "\n" + _lookup_failure_context(message)
    if verified_urls:
        system = system + "\n\n" + verified_urls
    # PATCH-VOICE-CODE-LOOKUP (2026-05-27)
    code_ctx = _lookup_code(message)
    if code_ctx:
        system = system + "\n\n" + code_ctx
    prompt = system + f"\n\nCorey: {message}\nMurphy:"

    # Lazy import — avoids circular deps at startup
    from src.llm_provider import MurphyLLMProvider
    llm = MurphyLLMProvider()
    result = llm.complete(prompt=prompt, max_tokens=max_tokens)
    text = (result.content if hasattr(result, "content") else str(result)).strip()

    # Defensive cleanup — strip stray "Murphy:" prefixes if the model echoes them
    for prefix in ("Murphy:", "MURPHY:", "Murphy -"):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
    # PATCH-VALUE-RESOLVER-WIRE-002 (2026-05-28) — resolve placeholder tokens via value_resolver
    # (renamed from librarian_v1 to avoid conflict with existing src/system_librarian.py)
    _last_resolutions = []
    try:
        from src.value_resolver import resolve_in_text
        text, _resolutions = resolve_in_text(text)
        if _resolutions:
            import logging as _lg
            _lg.getLogger("murphy_voice").info(
                "value_resolver resolved %d placeholders: %s",
                len(_resolutions),
                [r["key"] for r in _resolutions])
            # PATCH-REFLECTION-001 (2026-05-28) — expose resolutions for history capture
            _last_resolutions = [
                {"key": r.get("key"), "value": str(r.get("value")), "ok": r.get("ok", False)}
                for r in _resolutions
            ]
    except Exception as _e:
        import logging as _lg2
        _lg2.getLogger("murphy_voice").debug(
            "value_resolver resolve skipped: %s", _e)
    # Phase 3 (2026-05-26) — auto-verify filepaths in Murphy replies
    try:
        text = _verify_paths_in_reply(text)
    except Exception as _e:
        logger.debug("path verify skipped: %s", _e)
    try:
        text = _verify_urls_in_reply(text)
    except Exception as _e:
        logger.debug("url verify skipped: %s", _e)
    # PATCH-REFLECTION-001 — expose resolutions for caller via function attribute
    reply_in_voice.last_resolutions = _last_resolutions
    return text


# ── URL / route verification (Phase 6 — 2026-05-26) ───────────────────────
# PATCH-GRANULAR-001 (2026-05-27): broaden URL regex.
# Old regex only caught /api/* etc — missed bare routes like /os /hitl /dlfr
# which is exactly what Murphy hallucinated tonight (/app /heart /mind /patch).
_URL_REGEX = re.compile(r"(?P<u>/[a-zA-Z][a-zA-Z0-9_/-]{1,80})")

def _verify_urls_in_reply(text: str) -> str:
    """Scan reply for URL/route claims, fix or flag bad ones."""
    try:
        from src.route_registry import route_exists
    except Exception:
        return text
    seen = set()
    for m in _URL_REGEX.finditer(text):
        # PATCH-GRANULAR-001 (2026-05-27): skip if preceded by URL host
        start = m.start('u')
        # PATCH-GRANULAR-003 (2026-05-27): inspect the FULL surrounding token,
        # not just a fixed window. A URL match like "/murphy_voice" is bogus if
        # the surrounding token is actually "src/murphy_voice.py" (a filepath).
        end = m.end('u')
        token_start = start
        while token_start > 0 and text[token_start-1] not in ' \t\n\r"\'()[]{}<>,':
            token_start -= 1
        token_end = end
        while token_end < len(text) and text[token_end] not in ' \t\n\r"\'()[]{}<>,':
            token_end += 1
        full_token = text[token_start:token_end]
        # If the surrounding token has a URL scheme, skip — it's a real URL,
        # the route registry only knows path-only routes.
        if "://" in full_token:
            continue
        # If the surrounding token looks like a FILEPATH (contains src/, /opt/,
        # /var/, /etc/, or ends in a code/asset extension), the path verifier
        # owns it. Don't url-verify.
        if any(t in full_token for t in ("src/", "/opt/", "/var/", "/etc/", "/usr/", "tests/", "patch")):
            continue
        # PATCH-GRANULAR-004 (2026-05-27): if the surrounding token doesn't start
        # with '/' AND doesn't contain '://', the embedded slash is grammatical,
        # not a route. E.g. "file/function/endpoint" or "AND/OR" or "input/output".
        # Real routes always start with '/' in the source text.
        if not full_token.startswith('/') and "://" not in full_token:
            continue
        if full_token.endswith((".py",".html",".json",".md",".sh",".sql",".txt",
                                ".css",".js",".db",".service",".conf",".yaml",
                                ".yml",".toml",".ico",".png",".jpg",".svg")):
            continue
        u = m.group('u').rstrip(".,;:)")
        if u in seen: continue
        seen.add(u)
        # Strip query/fragment for lookup
        bare = u.split('?')[0].split('#')[0]
        r = route_exists(bare)
        if r.get("exists"):
            continue
        if r.get("exists") is None:  # registry unavailable
            return text
        sugs = r.get("suggestions") or []
        if sugs:
            text = text.replace(u, sugs[0] + " [was: " + u + "]", 1)
        else:
            text = text.replace(u, u + " [route_not_found]", 1)
    return text



# PATCH-GFO-WIRE-001 (R68) — go_find_out augmentation
# Wraps reply_in_voice so any 'I don't know yet — would need to X' draft
# from the LLM gets X executed and the reply augmented before send.
# R67 user-locked rule: when answer is "I don't know yet", go find out and
# offer what's there. Refusal is a STAGE, not the end.
try:
    from src.go_find_out import augment_reply as _gfo_augment
    _gfo_orig_reply = reply_in_voice

    def reply_in_voice(*args, **kwargs):
        draft = _gfo_orig_reply(*args, **kwargs)
        try:
            if isinstance(draft, str):
                aug = _gfo_augment(draft)
                if aug.get("refusal_detected") and aug["finding"] and aug["finding"].get("ok"):
                    return aug["augmented_text"]
                return draft
            elif isinstance(draft, dict) and "reply" in draft:
                aug = _gfo_augment(draft["reply"])
                if aug.get("refusal_detected"):
                    draft["reply"] = aug["augmented_text"]
                    draft["_gfo"] = {
                        "refusal_detected": True,
                        "action_taken": aug["action_taken"],
                        "finding_ok": bool(aug["finding"] and aug["finding"].get("ok")),
                        "wire_version": "GFO-002",
                    }
                return draft
        except Exception as _e:
            import logging
            logging.getLogger("go_find_out").debug(f"augmentation skipped: {_e}")
        return draft
except ImportError:
    pass
