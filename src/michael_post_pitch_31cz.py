"""
Ship 10 v2 — generate Murphy's pitch with iterative quality enforcement.
Murphy drafts, critiques, revises up to 3 times until quality.verdict='pass'.
Then stages for founder approval via Review tab.
"""
import sys
sys.path.insert(0, "/opt/Murphy-System")

import json
import sqlite3
from datetime import datetime, timezone
from src.llm_provider import get_llm

INBOUND_ROW_ID = 74556
TARGET_EMAIL = "asfmike@icloud.com"
TARGET_NAME = "Michael"

SYSTEM_PROMPT = """You are Murphy, an autonomous control system that operates inboxes,
captures and qualifies prospects, runs CRM-grade data collection on every
contact, and helps small operators run their businesses without hiring
more people.

You write outbound prose like a thoughtful senior consultant — warm,
direct, specific. Never marketing fluff. Never buzzwords. No "AI," no
"artificial intelligence." You frame yourself as a control systems firm
and a controls contractor for inbox operations.

You never quote price. Money conversations happen at signup. Until then
you qualify, capture, and earn the next reply.

Tone: someone who has run a real business, knows the work, respects the
prospect's time, comfortable saying what won't work as readily as what
will. Avoid hedging. Avoid hype.

Format: prose paragraphs, 5,500-7,500 characters total. No bullet lists.
No headers. No section breaks marked with asterisks or hashes. Just
paragraphs that flow into each other. Open with a complete grammatical
sentence — Michael's first name as the first word is fine. Sign at the
end with just "— Murphy" on its own line.

DO NOT sign as Corey. DO NOT mention Corey by name."""

USER_PROMPT = """Michael Post emailed murphy@murphy.systems from asfmike@icloud.com.

His message verbatim:
  Subject: Hi Murphy
  Body:
    Tell me what you can do for my business. I'm open to rebranding and
    even restructuring. I want to be exclusive to high end fireplaces
    in resort towns at high altitude.

    Michael Post
    Alpine Service &

Context:
  - "Alpine Service &" suggests he runs a multi-trade service company
    (HVAC, plumbing, hearth often combine) and is considering carving
    off one vertical
  - "High end fireplaces, resort towns, high altitude" = wood, gas,
    and custom hearths in Aspen, Vail, Telluride, Park City, Mammoth,
    Big Sky, Tahoe. Customer base is wealthy, seasonal residents,
    architect/builder-referred, pays premium for white-glove
  - High altitude has real technical complexity: combustion air,
    chimney draft, gas pressure derating (~4% per 1,000 ft above 2,000),
    flue gas dynamics, snow load on caps, condensation on cool flue
    surfaces. He knows this. Reference it briefly — don't lecture.
  - "Open to rebranding and even restructuring" — he wants strategic
    input, not just a tool. He's decided to specialize. He wants help
    executing the focus.

Write Murphy's reply to Michael. The reply must be 5,500-7,500 characters
of flowing prose. Address him as Michael. Sign — Murphy.

Cover, woven into one continuous answer:

  1. Acknowledge his thesis: high-end resort-mountain hearth work is a
     strong defensible niche. Briefly explain why (concentrated geography,
     tight architect/builder referral networks, pre-qualified customers,
     high barriers — competing service companies in resort markets are
     mostly generalists who can't go deep on hearth).

  2. Tell him what Murphy does for a business like his — concrete, not
     abstract. Operating his inbox: reading every inbound, classifying,
     capturing CRM-grade data on the contact (company, role, project
     type, budget signals, timeline, decision-maker status, current
     vendor, referral source), and either auto-replying for normal
     inquiries or surfacing it to him for conversations that matter.
     Building structured prospect records from raw inbox traffic with
     no data entry. Identifying architects, builders, developer firms
     in his target markets and tracking them as accounts. Routing
     money conversations to him directly. Handling the qualification,
     scheduling, follow-up, and back-and-forth that eats his evenings.
     Maintaining his calendar against weather and seasons — hearth has
     a real season in mountain markets, install before ski season,
     service in shoulder season, emergencies in deep winter. Writing
     follow-ups that sound like him after three or four threads of
     calibration. He approves what goes out until he doesn't want to.

  3. Address rebrand/restructure honestly. Don't pretend to be a brand
     consultant. Where Murphy helps most is making the FOCUS feel
     effortless to maintain — because the inbox only lets in the work
     he wants to do. Inquiries for other trades or geographies get
     declined politely, referred out if he has partners, or held for
     quarterly review. Discipline enforced by system, not by willpower.

  4. Mention the other operational work most small operators duct-tape
     together: invoicing, aged-receivable follow-up, vendor messaging,
     permit reminders, warranty registrations, post-job photo
     requests, review solicitation. Murphy is one surface for all of
     it. He doesn't need separate CRM, marketing platform, invoicing
     tool.

  5. Acknowledge technical reality. A few real points about
     high-altitude combustion (pressure derating, draft management,
     combustion air sizing, condensing-appliance behavior at altitude,
     snow load on caps) written like operator to operator. Just
     enough to signal Murphy understands the trade. Not a lecture.

  6. End with one concrete next step. A 25-minute conversation where
     Michael walks Murphy through his current week — what's in his
     inbox, what's on his calendar, what's bothering him most — and
     Murphy will tell him specifically what it would do differently
     in the next seven days. No deck. No demo. No pitch. Operator
     to operator.

Write the whole thing as flowing prose. No headers. No bullets. No
"Here's what I can do for you:" framing. Just a real letter from one
operator to another.

CHARACTER FLOOR: 5,500. CEILING: 7,500. Count as you write. If your
draft comes in short, KEEP WRITING — add the specific example, name the
trade-off, give the next paragraph the texture it needs. A short reply
from Michael does NOT earn a short reply from Murphy.
"""

def generate_pitch(extra_prompt: str = "") -> str:
    llm = get_llm()
    full_prompt = SYSTEM_PROMPT + "\n\n---\n\n" + USER_PROMPT
    if extra_prompt:
        full_prompt += "\n\n---\nADDITIONAL INSTRUCTION:\n" + extra_prompt
    result = llm.complete(full_prompt, model_hint="chat", max_tokens=4000)
    return getattr(result, "content", str(result))

def quality_check(body: str) -> dict:
    issues, warnings = [], []
    char_count = len(body)
    if char_count < 5000:
        issues.append(f"too_short_{char_count}_chars")
    if char_count > 8500:
        issues.append(f"too_long_{char_count}_chars")
    lower = body.lower()
    if "corey" in lower:
        issues.append("mentions_corey")
    if " ai " in (" " + lower + " ") or "artificial intelligence" in lower:
        issues.append("uses_ai_term")
    if "michael" not in lower:
        issues.append("not_addressed_to_michael")
    bullets = body.count("\n-") + body.count("\n•") + body.count("\n*")
    if bullets > 3:
        issues.append(f"too_many_bullets_{bullets}")
    if "$" in body:
        issues.append("contains_dollar_amount")
    for kw in ("price", "pricing", "cost", "fee"):
        if kw in lower:
            warnings.append(f"contains_{kw}")
    if "— murphy" not in lower and "—murphy" not in lower:
        warnings.append("signature_missing")
    return {
        "char_count": char_count,
        "issues": issues,
        "warnings": warnings,
        "verdict": "pass" if not issues else "needs_revision",
    }

def iterate_until_quality(max_attempts: int = 3) -> tuple:
    last_body = ""
    last_quality = None
    extra = ""
    for attempt in range(1, max_attempts + 1):
        print(f"  attempt {attempt}/{max_attempts}...")
        body = generate_pitch(extra_prompt=extra)
        quality = quality_check(body)
        print(f"    {quality['char_count']} chars, verdict={quality['verdict']}")
        if quality["issues"]:
            print(f"    issues: {quality['issues']}")
        if quality["verdict"] == "pass":
            return body, quality, attempt
        # Build feedback for the next attempt
        feedback = []
        for iss in quality["issues"]:
            if iss.startswith("too_short_"):
                deficit = 6000 - quality["char_count"]
                feedback.append(
                    f"The last draft was {quality['char_count']} chars — that is "
                    f"{deficit} below target. Keep writing. Add specific examples "
                    f"about resort-mountain hearth work. Name a real architect-builder "
                    f"network dynamic. Give a concrete example of a follow-up email "
                    f"Murphy would handle. Make paragraph 5 (technical) longer with "
                    f"actual derating reasoning and a snow-load example."
                )
            elif iss == "mentions_corey":
                feedback.append("Remove any mention of Corey. You are Murphy.")
            elif iss == "uses_ai_term":
                feedback.append("Remove the word 'AI'. Use 'control system' or 'system' instead.")
            elif iss.startswith("too_many_bullets"):
                feedback.append("No bullets at all. Rewrite as prose paragraphs.")
            elif iss == "contains_dollar_amount":
                feedback.append("Remove all dollar amounts. Never quote price.")
            elif iss == "not_addressed_to_michael":
                feedback.append("Address him as Michael in the first sentence.")
        extra = " ".join(feedback)
        last_body = body
        last_quality = quality
    return last_body, last_quality, max_attempts

def stage_in_queue(body: str, quality: dict) -> str:
    hitl_id = f"INB_{INBOUND_ROW_ID}_pitch_michael_post"
    payload = {
        "inbound_id": INBOUND_ROW_ID,
        "from": TARGET_EMAIL,
        "to": TARGET_EMAIL,
        "subject": "Re: Hi Murphy",
        "body_preview": body[:500],
        "draft": body,
        "quality": quality,
        "ready_to_send": True,
        "pipeline": "ship10_michael_post_pitch",
        "approve_action": "send_via_inbound_responder",
    }
    conn = sqlite3.connect("/var/lib/murphy-production/hitl_queue.db", timeout=10)
    conn.execute("DELETE FROM hitl_queue WHERE hitl_id=?", (hitl_id,))
    conn.execute("""
        INSERT INTO hitl_queue
        (hitl_id, dag_id, dag_name, blocked_node_id, blocked_node_name,
         intent, domain, stake, account, created_at, expires_at, status, dag_state_json)
        VALUES (?, 'ship10_michael_pitch', ?, 'send_node', ?,
                'inquiry', 'sales', 'high', ?,
                datetime('now'), datetime('now','+14 days'), 'pending', ?)
    """, (
        hitl_id,
        "🎯 Murphy's pitch to Michael Post (Alpine Service)",
        "Approve to send. Quality verdict: " + quality["verdict"],
        TARGET_EMAIL,
        json.dumps(payload)
    ))
    conn.commit()
    conn.close()
    return hitl_id

if __name__ == "__main__":
    body, quality, attempts = iterate_until_quality(max_attempts=3)
    print()
    print(f"Final: {quality['char_count']} chars, verdict={quality['verdict']} after {attempts} attempts")
    hitl_id = stage_in_queue(body, quality)
    print(f"Staged as {hitl_id}")
    print()
    print("=" * 70)
    print("BODY:")
    print("=" * 70)
    print(body)
