"""
Ship 31ad — Deliverable evaluator.

5-lens adversarial judging using Murphy's own LLM. Bias mitigation:
  - Adversarial prompts (default to harsh)
  - Show-your-work required
  - Per-lens isolation (no overall vibes)
  - Bias-adjusted score reported alongside raw
"""
import json, time, os, sys, re
sys.path.insert(0, "/opt/Murphy-System")

LENSES = {
    "content": {
        "name": "Content",
        "rubric": """Score 1-10 on direct usefulness.

10 = Direct answer to the asked question. Accurate to the field. Useful in the next 5 minutes of the reader's life. Includes 2-3 concrete next actions AND 1-2 specific verifiable citations (statute, code section, case, ASHRAE table, GAAP §).
8 = Useful but generic OR over-hedged OR missing specific citation
6 = Tangentially related, fluff
4 = Partial answer, missing the actual question
2 = Wrong or off-topic
1 = Refusal or non-answer

Default to 6-7. A 10 is reserved for work indistinguishable from a senior partner at a top firm in the discipline.""",
    },
    "format": {
        "name": "Format",
        "rubric": """Score 1-10 on rendering and structure.

10 = Clean paragraph breaks, no wall-of-text, brand chrome is subordinate to the answer, no broken markdown, no fake markdown that won't render in email.
8 = Renders but one minor visual issue (e.g. overly long paragraph)
6 = Cramped or poorly structured
4 = Hard to read
2 = Broken layout
1 = Unreadable

Penalize heavily: walls of text, ASCII tables (don't render in email), markdown headers (don't render in plain text fallback), excessive bullets.""",
    },
    "professionalism": {
        "name": "Professionalism",
        "rubric": """Score 1-10 on tone and register.

10 = Reads like a senior consultant. No filler. No "I hope this helps". No "let me know if you have questions". No fake enthusiasm. No LLM tells ("Certainly!", "Great question!"). Concise but complete. Tone matches the inbound register.
8 = Professional but one tic slips through
6 = Reads as competent AI
4 = Reads as generic chatbot
2 = Reads as low-quality LLM
1 = Cringeworthy

Penalize: any "I'd be happy to help", "Certainly!", "I hope this helps", "Feel free to ask", "Let me know", excessive use of emoji, em-dash overuse, robotic transition phrases.""",
    },
    "on_brand": {
        "name": "On-Brand",
        "rubric": """Score 1-10 on alignment with murphy.systems landing page positioning.

Landing page tagline: "AI agents that run your business"
Voice: Confident, technical, direct, no Victorian/bureaucratic chrome.
Visual: Teal accent, dark surface, modern.

10 = Tagline matches landing page. No chrome that contradicts murphy.systems. Doesn't oversell features Murphy doesn't have. Doesn't make false promises.
8 = Mostly on-brand, one drift
6 = Off-brand vibes
4 = Reads as a different product
2 = Actively contradicts brand
1 = Disqualifying

Penalize: "Bureau of Autonomous Operations", "Despatch", "Patronage", "Inoni LLC, Proprietors", "Inquiry of the House", "beg leave", Victorian-LARP language, overpromising capabilities Murphy doesn't have.""",
    },
    "responsive": {
        "name": "Responsive",
        "rubric": """Score 1-10 on direct responsiveness to the ACTUAL inquiry.

10 = Directly addresses the specific question(s) asked. Picks up on context. Asks for the right clarifying info OR makes the right assumption explicit. If the inquiry has multiple questions, answers all of them. If there's a trap (planted error citation, contradictory facts, buried critical fact), the reply catches it.
8 = Addresses the question but ignores some context
6 = Addresses the topic, not the question
4 = Generic response to the category
2 = Off-topic
1 = Doesn't answer

This is the lens where adversarial traps in the inquiry get scored. If the inquiry has a trap_citation (wrong code section), did Murphy catch it or echo it back?""",
    },
    "factual": {
        "name": "Factual",
        "rubric": """Score 1-10 on factual accuracy and citation discipline.

10 = Every cited fact is verifiable. Statute numbers correct. Code sections real. Case names accurate. Standards (ASHRAE, NEC, GAAP, etc.) correctly attributed. Distinguishes "this is law" from "this is heuristic". No hallucinated case names or code sections.
8 = One fact is approximate but defensible
6 = Mostly correct with one verifiable error
4 = Multiple errors
2 = Major hallucination
1 = Mostly fabricated

For inquiries with trap_citation: scoring rewards catching the planted error. Penalizes echoing it back.""",
    },
}

_PROVIDER = None
def _get_provider():
    global _PROVIDER
    if _PROVIDER is None:
        from src.llm_provider import MurphyLLMProvider
        _PROVIDER = MurphyLLMProvider.from_env()
    return _PROVIDER

def call_llm(messages, max_tokens=600, temperature=0.4):
    """Call Together.ai directly via Murphy's provider — NO persona injection."""
    try:
        result = _get_provider().complete_messages(
            messages=messages,
            model_hint="chat",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.content
    except Exception as e:
        return f"[error: {e}]"

def call_murphy(prompt, max_tokens=600, timeout=60):
    """Compat shim — single-user message call."""
    return call_llm([{"role": "user", "content": prompt}], max_tokens=max_tokens)

def generate_murphy_reply(inquiry):
    """Generate Murphy's reply to an inquiry using same model production uses."""
    system = (
        "You are Murphy, an AI consultant at murphy.systems. You answer cold inbound emails "
        "with direct, useful, technically accurate replies. Cite specific statutes, code sections, "
        "standards, or formulas when relevant. Match the register of the inquiry — formal for "
        "lawyers/engineers/CFOs, warm for distress. Be concise. No filler phrases. No 'I hope this helps'. "
        "No fake enthusiasm. Maximum 280 words. Return only the email body, no greeting or signature."
    )
    user = f"""INQUIRY SUBJECT: {inquiry['subject']}
INQUIRY FROM: {inquiry['from']}
INQUIRY BODY:
{inquiry['body']}

Write your reply now."""
    return call_llm(
        [{"role":"system","content":system},
         {"role":"user","content":user}],
        max_tokens=600, temperature=0.5,
    )

def judge_lens(inquiry, reply, lens_key):
    """Adversarial judge for a single lens."""
    lens = LENSES[lens_key]
    prompt = f"""You are a HARSH adversarial evaluator. Your job is to find every flaw, not to be kind.

═══ INQUIRY THAT WAS SENT TO MURPHY ═══
SUBJECT: {inquiry.get('subject','')}
BODY:
{inquiry['body']}

═══ MURPHY'S REPLY TO BE EVALUATED ═══
{reply}

═══ ADVERSARIAL TRAP PLANTED IN INQUIRY ═══
{inquiry.get('trap','none')}

NOTE: You are evaluating MURPHY'S REPLY, not the inquiry. The inquiry is the input; the reply is what you score. If the inquiry contains an error (planted trap), the reply earns points for CATCHING it and loses points for ECHOING it.

LENS: {lens['name']}
RUBRIC:
{lens['rubric']}

INSTRUCTIONS:
1. List 3 specific weaknesses you observe in the reply (be specific, quote text)
2. List 1 specific strength
3. Assign a score 1-10 per the rubric. Default toward 6-7. A 10 requires senior-partner quality.

Format your response as:
WEAKNESSES:
- (weakness 1)
- (weakness 2)
- (weakness 3)
STRENGTH:
- (strength)
SCORE: N
RATIONALE: (one sentence)"""
    response = call_llm(
        [{"role":"system","content":"You are a HARSH adversarial quality evaluator. You score professional written work against a rubric. You list specific weaknesses, quote the work, and assign honest scores. Default toward 6-7. A 10 requires senior-partner quality. Always output: WEAKNESSES, STRENGTH, SCORE: N, RATIONALE."},
         {"role":"user","content":prompt}],
        max_tokens=700, temperature=0.3,
    )
    # Parse the score
    m = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)", response)
    score = float(m.group(1)) if m else 5.0
    score = max(1.0, min(10.0, score))
    return {"lens": lens_key, "score": score, "raw": response[:1200]}

def evaluate(inquiry, reply):
    """Full 5-lens (actually 6 with factual) evaluation."""
    results = {}
    for lens_key in LENSES.keys():
        results[lens_key] = judge_lens(inquiry, reply, lens_key)
        time.sleep(0.5)  # rate-limit kindness
    scores = [r["score"] for r in results.values()]
    # Median for robustness; min for floor check
    sorted_s = sorted(scores)
    median = sorted_s[len(sorted_s)//2] if len(sorted_s) % 2 == 1 else (sorted_s[len(sorted_s)//2 - 1] + sorted_s[len(sorted_s)//2]) / 2
    return {
        "scores": {k: results[k]["score"] for k in results},
        "raw_judgments": {k: results[k]["raw"] for k in results},
        "median": median,
        "min": min(scores),
        "max": max(scores),
        "ships": median >= 9.0 and min(scores) >= 8.0,
    }

if __name__ == "__main__":
    # Quick smoke test
    test_inq = {
        "id":"TEST","cat":"test","subcat":"smoke","trap":"trap_citation",
        "from":"smoke@test.com","subject":"MRPC 4.7 conflict",
        "body":"Does MRPC 4.7 prohibit dual representation in adoption cases?"
    }
    print("── generating reply ──")
    reply = generate_murphy_reply(test_inq)
    print(f"reply len: {len(reply)} chars")
    print(f"reply: {reply[:400]}")
    print()
    print("── judging content lens only ──")
    j = judge_lens(test_inq, reply, "content")
    print(f"score: {j['score']}")
    print(f"raw: {j['raw'][:600]}")
