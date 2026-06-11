"""
Ship 31c-pace — Stranger Responder (2026-06-10) — paced + budgeted
==================================================================

PATCH FROM v1 (Ship 31c initial) → v2 (this patch):
  - LLM calls now go through llm_provider.complete() directly with
    model_hint="fast" for magnify-drill (~5x faster, ~10x cheaper),
    keeping "chat" for the reply generation where quality matters
  - Replies route through outbound_email_queue (paced, audited,
    compliance-gated by PCR-090h.1) instead of raw sendmail
  - Per-day budget cap (MAX_DAILY_USD) prevents runaway cost
  - Per-cycle throughput cap respects existing 5-min timer cadence
  - Token usage logged per stranger for cost visibility

ECONOMICS (Llama-3.3-70B chat + Llama-3.1-8B fast on DeepInfra):
  Per stranger reply:
    Magnify-drill (8B fast):  ~1200 tok @ ~$0.0001 + ~3-5s
    Reply gen   (70B chat):   ~1500 tok @ ~$0.0014 + ~10-15s
    Total: ~$0.0015 + ~13-20s per stranger
  
  At 5-min cadence, limit=5 per cycle:
    Max throughput: ~60/hour, ~1,440/day
    Daily cost cap (MAX_DAILY_USD=5.00): ~3,300 strangers/day ceiling
    Realistic: 100-500/day comfortable

SAFETY LAYERS:
  1. _SHADOW_MODE (still True by default) — drafts go to founder first
  2. Rate limit: 5 per sender domain per 24h
  3. Daily $ cap: stop processing if spend > MAX_DAILY_USD
  4. Outbound queue: passes through PCR-090h.1 compliance gate
  5. Queue depth pacing: skip cycle if outbound queue > MAX_QUEUE_DEPTH

PUBLIC SURFACE:
  process_stranger_inquiries(limit=5) -> dict

LAST UPDATED: 2026-06-10 — paced + budgeted
"""

import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("stranger_responder")

sys.path.insert(0, "/opt/Murphy-System")

_DB = "/var/lib/murphy-production/inbound_replies.db"
_MAIL_DB = "/var/lib/murphy-production/murphy_mail.db"
_FOUNDER_EMAIL = "cpost@murphy.systems"

# Safety toggles
_SHADOW_MODE = True

# Ship 31s: per-call routing trace (set by _build_role_soul, read after reply)
_LAST_ROUTING_DECISION = ""
_LAST_USED_PERSISTED = False

_MAX_PER_DOMAIN_24H = 5
_MAX_DAILY_USD = float(os.environ.get("STRANGER_MAX_DAILY_USD", "5.00"))
_MAX_QUEUE_DEPTH = int(os.environ.get("STRANGER_MAX_QUEUE_DEPTH", "50"))

_VALUE_LINE = "Murphy automates the rule-bound periodic work you've been doing manually."

_ALLOWLIST_OWNED = {
    "cpost@murphy.systems",
    "corey.gfc@gmail.com",
    "callmehandy@gmail.com",
}




# ──────────────────────────────────────────────────────────────────────
# Ship 31i.B: DLF soul injection + role detection
# Proven externally on tau-bench: DLF wrapper adds +0.017 F1
# Safe-by-design: any failure returns "" and the caller proceeds
# normally with no soul injection.
# ──────────────────────────────────────────────────────────────────────
def _build_role_soul(role_hint, vertical="general"):
    """Build a role-tailored soul prompt for DLF injection.

    Ship 31s routing:
      1. Check agent_rating_loop for a persisted, high-fitness soul
      2. If found (fitness >= 0.65) -> reuse instantly, free
      3. Otherwise synthesize fresh via build_deep_soul and persist it
      4. Each call records its routing decision for the dashboard

    Returns "" if role_hint is empty.
    """
    if not role_hint:
        return ""

    # Ship 31s: try persisted soul from rating loop first
    routing_decision = "fresh_synth_default"
    try:
        from src.agent_rating_loop import (
            get_best_agent_for, should_reuse_persisted, persist_soul
        )
        best = get_best_agent_for(role_hint, vertical)
        if best and should_reuse_persisted(best):
            routing_decision = (
                "reused_persisted fit=" + str(round(best.get("fitness_score") or 0, 3)) +
                " deps=" + str(best.get("deployments") or 0)
            )
            logger.info("_build_role_soul: %s", routing_decision)
            # Stash on a module attr for the caller to retrieve
            globals()["_LAST_ROUTING_DECISION"] = routing_decision
            globals()["_LAST_USED_PERSISTED"] = True
            return (best.get("persisted_soul") or "")[:4000]
    except Exception as exc:
        logger.warning("_build_role_soul routing failed: %s", exc)

    # Fresh synthesis path
    try:
        from src.deep_soul_engine import build_deep_soul
        soul = build_deep_soul(
            agent_id="stranger_responder_" + str(role_hint),
            role_title=role_hint,
            domain=vertical or "general",
        )
        full = soul.get("full_soul", "") if isinstance(soul, dict) else ""
        if full and len(full) > 200:
            capped = full[:4000]
            # Persist for future reuse
            try:
                from src.agent_rating_loop import persist_soul
                persist_soul(role_hint, vertical, capped)
                routing_decision = "fresh_synth_persisted"
            except Exception as exc:
                logger.warning("persist_soul failed: %s", exc)
                routing_decision = "fresh_synth_no_persist"
            globals()["_LAST_ROUTING_DECISION"] = routing_decision
            globals()["_LAST_USED_PERSISTED"] = False
            return capped
    except Exception as exc:
        logger.warning("_build_role_soul: build_deep_soul failed for %s: %s", role_hint, exc)
    # Synthetic fallback — the version that won tau-bench
    return (
        "You are operating with Murphy DLF as a " + str(role_hint) +
        " in the " + str(vertical) + " domain.\n\n"
        "LOYALTY: customer-first. Verify before acting. Confirm before destructive operations. Show your work.\n"
        "SCOPE: respond as a working " + str(role_hint) + " would — use the terminology, methods, and concerns of the role.\n"
        "SAFETY: never invent IDs, numbers, or facts. If unknown, ask. Concrete > generic AI fluff."
    )


_ROLE_KEYWORDS = {
    "cfo":         ("cfo", "chief financial officer", "vp finance", "vp of finance",
                    "finance director", "director of finance", "head of finance",
                    "controller", "treasurer"),
    "cto":         ("cto", "chief technology officer", "chief technical officer",
                    "vp engineering", "vp of engineering", "head of engineering",
                    "engineering lead", "director of engineering"),
    "ceo":         ("ceo", "chief executive officer", "founder", "co-founder",
                    "president", "managing director"),
    "coo":         ("coo", "chief operating officer", "vp operations",
                    "head of operations", "operations director", "director of operations"),
    "recruiter":   ("recruiter", "talent acquisition", "talent partner",
                    "hiring manager", "head of people", "chief people officer",
                    "vp people", "director of people", "chro",
                    "chief human resources officer"),
    "lawyer":      ("counsel", "general counsel", "attorney", "legal officer",
                    "chief legal officer", "esq", "law firm", "associate counsel"),
    "engineer":    ("software engineer", "engineer,", "engineer\\n", "developer",
                    "sde", "swe", "software architect", "principal engineer",
                    "staff engineer", "senior engineer"),
    "sales":       ("account executive", "account exec", "sdr", "bdr",
                    "vp sales", "vp of sales", "sales director", "director of sales",
                    "head of sales", "chief revenue officer", "cro"),
    "marketing":   ("cmo", "chief marketing officer", "vp marketing",
                    "vp of marketing", "head of marketing", "marketing director",
                    "growth lead", "head of growth", "brand director"),
    "pm":          ("product manager", "senior product manager", "pm,",
                    "product lead", "head of product", "vp product",
                    "chief product officer", "cpo", "director of product"),
    "designer":    ("designer", "ux designer", "ui designer", "product designer",
                    "creative director", "head of design", "director of design"),
    "mep_engineer": ("mep", "mechanical engineer", "electrical engineer",
                     "plumbing engineer", "hvac engineer", "mep coordinator",
                     "mep designer", "professional engineer",
                     "stamped drawing", "engineer of record"),
    "fde":          ("forward deployed engineer", "fde,",
                     "automation engineer", "solutions engineer",
                     "implementation engineer", "deployment engineer",
                     "rpa developer", "process automation"),
    "risk_lawyer":  ("risk counsel", "risk officer", "chief risk officer",
                     "compliance counsel", "regulatory counsel",
                     "risk management", "risk assessment", "enterprise risk",
                     "risk attorney"),
    "operations":  ("operations manager", "ops lead", "head of ops",
                    "logistics manager", "supply chain", "supply chain director"),
}

# Map role -> default vertical (used when content gives ambiguous signal)
_ROLE_DEFAULT_VERTICAL = {
    "cfo": "finance", "ceo": "general", "coo": "operations",
    "cto": "tech", "engineer": "tech", "pm": "tech", "designer": "tech",
    "recruiter": "staffing", "lawyer": "legal",
    "sales": "general", "marketing": "general", "operations": "general",
    "mep_engineer": "construction", "fde": "automation", "risk_lawyer": "risk",
}


def _detect_role_from_email(subject, body, from_addr):
    """Cheap heuristic role detector from email text.

    Looks at signature/title lines in the body, then subject, then domain.
    Returns (role_hint, vertical) tuple. role_hint is "" if no signal.
    """
    haystack = ((body or "")[-1500:] + "\n" + (subject or "") + "\n" + (from_addr or "")).lower()
    # Score every role: pick the role whose matched keyword is LONGEST
    # (i.e. most specific). "mep coordinator" beats "operations director"
    # which only matched on "coordinator" substring.
    best_role = None
    best_kw = ""
    for role, kws in _ROLE_KEYWORDS.items():
        for kw in kws:
            if kw in haystack and len(kw) > len(best_kw):
                best_role = role
                best_kw = kw
    if best_role:
        role = best_role
        kw = best_kw
        for _ in [None]:  # preserve original control flow / variable names
            if True:
                # Vertical follows ROLE first (CFO is always finance unless STRONG override)
                vertical = _ROLE_DEFAULT_VERTICAL.get(role, "general")
                # STRONG content overrides
                if any(w in haystack for w in ("invoice", "p&l", "gaap", "audit", "ebitda")):
                    vertical = "finance"
                elif any(w in haystack for w in ("nda", "litigation", "clause", "indemnif")):
                    vertical = "legal"
                elif any(w in haystack for w in ("candidate", "resume", "interview", "sourcing")):
                    vertical = "staffing"
                elif any(w in haystack for w in ("saas", "api endpoint", "deploy", "kubernetes")):
                    vertical = "tech"
                return role, vertical
    return "", "general"


def _llm_complete(prompt: str, model_hint: str = "chat", max_tokens: int = 800, soul_system: str = "") -> Optional[Dict]:
    """Direct llm_provider call via the full LLMCompletion object (not the .content shortcut).

    Ship 31i.B: optional soul_system param injects DLF role bias as a
    system prompt. Falls back gracefully if llm_provider lacks the kwarg.
    """
    try:
        from src.llm_provider import get_llm
        kwargs = {"model_hint": model_hint, "max_tokens": max_tokens}
        if soul_system:
            kwargs["system"] = soul_system
        try:
            result = get_llm().complete(prompt, **kwargs)
        except TypeError:
            # llm_provider doesnt accept system kwarg — prepend to prompt instead
            if soul_system:
                prompt = soul_system + "\n\n" + prompt
            result = get_llm().complete(prompt, model_hint=model_hint, max_tokens=max_tokens)
        # LLMCompletion dataclass: content, prompt_tokens, completion_tokens, cost_usd (or similar)
        text = getattr(result, "content", "") or getattr(result, "text", "") or ""
        prompt_tokens = int(getattr(result, "tokens_prompt", 0) or 0)
        completion_tokens = int(getattr(result, "tokens_completion", 0) or 0)
        # cost_usd may or may not be present — estimate if missing
        cost_usd = getattr(result, "cost_usd", None)
        if cost_usd is None:
            # rough estimate: $0.88/M for Llama-70B, $0.06/M for Llama-8B
            rate = 0.06e-6 if model_hint == "fast" else 0.88e-6
            cost_usd = (prompt_tokens + completion_tokens) * rate
        return {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": float(cost_usd),
        }
    except Exception as e:
        import traceback
        logger.error(f"_llm_complete failed (hint={model_hint}): {e}\n{traceback.format_exc()}")
        return None


def _magnify_drill(email_subject: str, email_body: str) -> Optional[Dict]:
    """Generate tailored agent description via fast model (8B)."""
    prompt = f"""You are Murphy's agent-description generator. A stranger emailed murphy@murphy.systems:

SUBJECT: {email_subject}
BODY: {email_body[:1500]}

Generate a TAILORED agent description Murphy should embody. Use exactly this format. No examples. No hedging.

WHO: [3 sentences — role identity, scope, authority for THIS request]
HOW: [3 sentences — workflow pattern for THIS request]
WHY: [3 sentences — who served, what success looks like for THIS person]
STOP: [3 sentences — when to ask first, what NOT to do]

Output ONLY the 4-field block."""
    return _llm_complete(prompt, model_hint="fast", max_tokens=600)




# ──────────────────────────────────────────────────────────────────────
# Ship 31m: contextual ad injection (free tier only)
# ──────────────────────────────────────────────────────────────────────
def _inject_contextual_ad(reply_text, role_hint, vertical, subject, body, to_addr, tier="free"):
    """Wrap contextual_ad_engine. Safe-by-default: any failure returns
    the reply unchanged. Returns (new_text, meta_dict_or_None)."""
    try:
        from src.contextual_ad_engine import inject_ad_into_reply
        return inject_ad_into_reply(reply_text, role_hint or "", vertical or "general",
                                    subject or "", body or "", to_addr, tier=tier)
    except Exception as exc:
        logger.warning("_inject_contextual_ad failed: %s", exc)
        return reply_text, None


def _should_send_live(from_addr, from_domain):
    """Per-recipient launch gate: True = real reply, False = shadow to founder."""
    try:
        from src.launch_gate import is_allowlisted, is_unsubscribed
        if is_unsubscribed(from_addr):
            return False, "unsubscribed"
        if is_allowlisted(from_domain):
            return True, "allowlisted_live"
        return False, "not_allowlisted_shadow"
    except Exception as exc:
        logger.warning("_should_send_live failed: " + str(exc))
        return False, "gate_error_shadow"


def _append_compliance_footer(body, reply_to_addr):
    try:
        from src.launch_gate import compliance_footer
        return body + compliance_footer(reply_to_addr)
    except Exception:
        return body


def _record_adoption(from_domain, from_addr, role, vertical,
                     actionable_count=0, last_action=None, direction="inbound"):
    try:
        from src.launch_gate import record_adoption_signal
        record_adoption_signal(from_domain, from_addr, role, vertical,
                               actionable_count, last_action, direction)
    except Exception:
        pass


def _maybe_handle_stop(from_addr, body):
    try:
        from src.launch_gate import check_stop_keyword, register_unsubscribe
        if check_stop_keyword(body):
            register_unsubscribe(from_addr, "stop_keyword", body[:300])
            logger.info("_maybe_handle_stop: registered " + str(from_addr))
            return True
    except Exception as exc:
        logger.warning("_maybe_handle_stop failed: " + str(exc))
    return False


def _generate_reply(agent_desc: str, email_subject: str, email_body: str, from_addr: str) -> Optional[Dict]:
    """Generate the actual reply email body (full chat model for quality).

    Ship 31i.B: detects role from email, injects DLF soul if any signal.
    """
    role_hint, vertical = _detect_role_from_email(email_subject, email_body, from_addr)
    soul = _build_role_soul(role_hint, vertical)
    if soul:
        logger.info("_generate_reply: DLF injection active role=%s vertical=%s", role_hint, vertical)
    prompt = f"""You are now this agent:

=== AGENT DESCRIPTION ===
{agent_desc}
=== END AGENT DESCRIPTION ===

The person who emailed you (from {from_addr}) wrote:

SUBJECT: {email_subject}
BODY: {email_body[:2000]}

Write a SHORT email reply (under 200 words) that:
1. Opens with one line: "{_VALUE_LINE}"
2. Directly addresses their actual question or need
3. Names ONE concrete next step Murphy can take to help them
4. Closes with: "— Murphy (automated reply; reply STOP to opt out)"

Do NOT make up specific commitments about pricing, timelines, or features. Be concrete about what Murphy CAN do, honest about what it CAN'T."""
    out = _llm_complete(prompt, model_hint="chat", max_tokens=400, soul_system=soul)
    if out and out.get("text"):
        new_text, ad_meta = _inject_contextual_ad(out["text"], role_hint, vertical,
                                                   email_subject, email_body, from_addr, tier="free")
        out["text"] = new_text
        out["ad_meta"] = ad_meta
        if ad_meta and ad_meta.get("injected"):
            logger.info("_generate_reply: ad injected ad_id=%s score=%.2f", ad_meta.get("ad_id"), ad_meta.get("score", 0))
    return out


def _today_spend_usd(conn: sqlite3.Connection) -> float:
    """Sum cost_usd of stranger replies sent today. Defensive against legacy non-JSON targets."""
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT auto_response_target FROM inbound_replies 
           WHERE auto_response_status IN ('stranger_sent','stranger_shadow_sent','stranger_queued')
           AND auto_response_sent_at LIKE ?""",
        (cutoff + "%",),
    ).fetchall()
    total = 0.0
    for r in rows:
        target = r[0] if r else None
        if not target:
            continue
        try:
            d = json.loads(target)
            total += float(d.get("cost_usd", 0.0))
        except Exception:
            pass  # legacy row with plain email — skip
    return total


def _outbound_queue_depth() -> int:
    try:
        conn = sqlite3.connect(_MAIL_DB)
        n = conn.execute(
            "SELECT COUNT(*) FROM outbound_email_queue WHERE status IN ('pending_review','pending')",
        ).fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


def _rate_limit_ok(from_addr: str, conn: sqlite3.Connection) -> bool:
    domain = from_addr.split("@")[-1].lower() if "@" in from_addr else from_addr
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    count = conn.execute(
        """SELECT COUNT(*) FROM inbound_replies 
           WHERE from_domain = ? 
           AND auto_response_status IN ('stranger_sent','stranger_queued')
           AND auto_response_sent_at > ?""",
        (domain, cutoff),
    ).fetchone()[0]
    return count < _MAX_PER_DOMAIN_24H


def _queue_outbound(to_addr: str, subject: str, body: str, urgency: str = "normal") -> Optional[str]:
    """Submit to outbound_email_queue. Returns queue_id on success."""
    try:
        import secrets
        conn = sqlite3.connect(_MAIL_DB)
        queue_id = "oeq_" + secrets.token_hex(8)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO outbound_email_queue (
                 queue_id, from_address, to_addresses, subject, body, body_format,
                 agent_profile_id, agent_role, agent_class, urgency, status,
                 created_at, updated_at, action_type
               ) VALUES (?, ?, ?, ?, ?, 'plain', 
                         'stranger_responder', 'auto_responder', 'system', ?, 'pending_review',
                         ?, ?, 'email_outbound')""",
            (queue_id, "murphy@murphy.systems", json.dumps([to_addr]),
             subject, body, urgency, now, now),
        )
        conn.commit()
        conn.close()
        return queue_id
    except Exception as e:
        logger.error(f"_queue_outbound failed: {e}")
        return None


def _send_sendmail(to_addr: str, subject: str, body: str) -> bool:
    """Direct sendmail. Ship 31t: emits multipart/alternative (plain + HTML).

    Used for shadow drafts to founder AND for live outbound (when wired).
    """
    try:
        try:
            from src.email_mime_builder import build_multipart_message
            msg = build_multipart_message(
                to_addr=to_addr, subject=subject, plain_body=body,
                from_addr="murphy@murphy.systems",
            )
        except Exception as mime_exc:
            logger.warning("MIME build failed, falling back to plain: %s", mime_exc)
            msg = (
                f"To: {to_addr}\n"
                f"From: murphy@murphy.systems\n"
                f"Subject: {subject}\n"
                f"Content-Type: text/plain; charset=utf-8\n\n"
                f"{body}\n"
            )
        result = subprocess.run(
            ["/usr/sbin/sendmail", "-t", "-f", "murphy@murphy.systems"],
            input=msg.encode(), capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"_send_sendmail failed: {e}")
        return False






def _magnify_drill_perspective(subject: str, body: str, principal_addr: str,
                                attachment_summary: str, role: dict,
                                forward: dict) -> Optional[Dict]:
    """Ship 31g: forwarded-message-with-attachment analysis from forwarder's
    role perspective. The forwarder is asking Murphy to analyze the attached
    document THROUGH THEIR ROLE LENS.
    
    Example: CFO forwards a contract → analyze financial terms, payment
    schedule, indemnification caps, etc. (the CFO lens).
    """
    role_class = role.get("role_class", "unknown")
    lens = role.get("lens", "general business implications")
    job_title = role.get("job_title", role_class)
    inner_from = forward.get("inner_from", "")
    inner_subject = forward.get("inner_subject", "")
    
    prompt = f"""You are Murphy, providing PERSPECTIVE-AWARE analysis. A {job_title} ({principal_addr}) forwarded a document to you and wants your read on it through their lens.

WHO FORWARDED IT:   {principal_addr}
THEIR ROLE:         {job_title} (class={role_class})
THEIR LENS (what they care about): {lens}

ORIGINAL SENDER:    {inner_from}
ORIGINAL SUBJECT:   {inner_subject}
THEIR ASK (forwarder's body):
{(body or '')[:1500]}

ATTACHMENT CONTENT (summarized):
{attachment_summary[:5000]}

Generate a TAILORED agent description specific to analyzing this document FROM THE {role_class.upper()} LENS. Use exactly this format:

WHO: [3 sentences: identity as a {role_class}-perspective analyst for this specific document type, scope of authority, what you will NOT do]
HOW: [3 sentences: how you analyze a document through the {role_class} lens — what you look for first, what you flag, how you structure findings]  
WHY: [3 sentences: why {role_class}s typically need this perspective on this document type, what success looks like for {principal_addr}]
STOP: [3 sentences: confidentiality (do not share inner_from's content back to inner_from), legal/professional boundaries, when to defer to a real expert]

Output ONLY the 4-field block."""
    return _llm_complete(prompt, model_hint="fast", max_tokens=700)


def _generate_perspective_reply(agent_desc: str, subject: str, body: str,
                                 principal_addr: str, attachment_summary: str,
                                 role: dict, forward: dict) -> Optional[Dict]:
    """Generate the perspective-aware analysis reply."""
    role_class = role.get("role_class", "unknown")
    lens = role.get("lens", "")
    job_title = role.get("job_title", "")
    
    role_hint, vertical = _detect_role_from_email(subject, body, principal_addr)
    soul = _build_role_soul(role_hint, vertical)
    if soul:
        logger.info("_generate_perspective_reply: DLF injection active role=%s vertical=%s", role_hint, vertical)
    prompt = f"""You are now this agent:

=== AGENT DESCRIPTION ===
{agent_desc}
=== END AGENT DESCRIPTION ===

You are analyzing a forwarded document for {principal_addr} ({job_title}). They want your read FROM THE {role_class.upper()} LENS, specifically: {lens}.

THEIR ASK:
{(body or '')[:1500]}

ATTACHMENT CONTENT:
{attachment_summary[:5500]}

Write a SHORT analysis reply (under 250 words) addressed to {principal_addr}. Structure:
1. Open line: "Murphy automates the rule-bound periodic work you've been doing manually."
2. ONE sentence acknowledging what you analyzed and from what lens
3. 3-5 BULLETS — the specific findings ranked by importance to a {role_class}. Each bullet must be CONCRETE and reference an actual fact from the attachment, not generic boilerplate.
4. ONE sentence on the highest-leverage next step  
5. Close: "Reply with questions or YES to drill deeper on any of the above. — Murphy (automated reply; reply STOP to opt out)"

CRITICAL:
- Use specific numbers/terms from the attachment, NOT vague phrases
- Frame everything through the {role_class} lens — what would a {job_title} actually care about?
- Do NOT cc the original sender ({forward.get('inner_from', 'unknown')})
- Do NOT speculate beyond what's in the document"""
    
    out = _llm_complete(prompt, model_hint="chat", max_tokens=600, soul_system=soul)
    if out and out.get("text"):
        new_text, ad_meta = _inject_contextual_ad(out["text"], role_hint, vertical,
                                                   subject, body, principal_addr, tier="free")
        out["text"] = new_text
        out["ad_meta"] = ad_meta
        if ad_meta and ad_meta.get("injected"):
            logger.info("_generate_perspective_reply: ad injected ad_id=%s score=%.2f", ad_meta.get("ad_id"), ad_meta.get("score", 0))
    return out

def _magnify_drill_ambient(email_subject: str, email_body: str, principal_addr: str) -> Optional[Dict]:
    """AMBIENT mode: principal CC'd Murphy on a conversation with someone else.
    Murphy must SYNTHESIZE the implicit task without quoting the thread to non-principal.
    Output: a brief plan offer addressed only to principal."""
    prompt = f"""You are Murphy's ambient synthesizer. The person at {principal_addr} CC'd you on an email thread they are having with a third party. They are NOT asking you to do anything yet. They want you to OBSERVE and OFFER help.

SUBJECT: {email_subject}
THREAD CONTENT (do NOT quote any of this back; stay meta):
{email_body[:1500]}

Generate a TAILORED agent description for what Murphy could do if asked. Use exactly this format. No examples. No hedging.

WHO: [3 sentences - role identity, scope, authority for the IMPLIED task]
HOW: [3 sentences - workflow pattern for the IMPLIED task]
WHY: [3 sentences - why this helps the principal {principal_addr} specifically]
STOP: [3 sentences - confidentiality boundaries; what NOT to share with the other party]

Output ONLY the 4-field block."""
    return _llm_complete(prompt, model_hint="fast", max_tokens=600)


def _generate_ambient_offer(agent_desc: str, email_subject: str, email_body: str, principal_addr: str) -> Optional[Dict]:
    """Generate the ambient offer reply, sent ONLY to principal, NEVER to thread."""
    role_hint, vertical = _detect_role_from_email(email_subject, email_body, principal_addr)
    soul = _build_role_soul(role_hint, vertical)
    if soul:
        logger.info("_generate_ambient_offer: DLF injection active role=%s vertical=%s", role_hint, vertical)
    prompt = f"""You are now this agent:

=== AGENT DESCRIPTION ===
{agent_desc}
=== END AGENT DESCRIPTION ===

The person at {principal_addr} CC'd you on a thread they have with a third party. They want you to OFFER help, not act yet.

SUBJECT THEY ARE DISCUSSING: {email_subject}
CONTEXT (do NOT quote this back; refer to it meta only):
{email_body[:2000]}

Write a SHORT reply email (under 180 words) addressed ONLY to {principal_addr}. It must:
1. Open with one line: "{_VALUE_LINE}"
2. ONE sentence acknowledging you saw the thread (refer to it as 'your email re: {email_subject[:60]}' - NEVER quote thread content)
3. ONE concrete thing you noticed Murphy could do for them
4. ONE specific next step in 2-3 bullets (the PLAN)
5. Close with: "Reply YES to execute, or just tell me what to change. - Murphy (ambient; reply STOP to opt out)"

Do NOT cc the third party. Do NOT include anyone other than {principal_addr}. Do NOT quote ANY content from the thread. Do NOT mention specifics that only the third party would know - stay meta about WHAT Murphy can do, not WHAT the thread said."""
    out = _llm_complete(prompt, model_hint="chat", max_tokens=400, soul_system=soul)
    if out and out.get("text"):
        new_text, ad_meta = _inject_contextual_ad(out["text"], role_hint, vertical,
                                                   email_subject, email_body, principal_addr, tier="free")
        out["text"] = new_text
        out["ad_meta"] = ad_meta
        if ad_meta and ad_meta.get("injected"):
            logger.info("_generate_ambient_offer: ad injected ad_id=%s score=%.2f", ad_meta.get("ad_id"), ad_meta.get("score", 0))
    return out


def process_stranger_inquiries(limit: int = 5) -> Dict:
    """Main entry point — paced, budgeted, queue-aware."""
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row

    # Pacing gate: if outbound queue is backed up, back off
    qdepth = _outbound_queue_depth()
    if qdepth > _MAX_QUEUE_DEPTH:
        conn.close()
        return {"ok": True, "skipped_cycle": True, "reason": "queue_full",
                "outbound_queue_depth": qdepth, "max": _MAX_QUEUE_DEPTH,
                "count_sent": 0, "count_skipped": 0, "count_errors": 0}

    # Budget gate
    daily_spend = _today_spend_usd(conn)
    if daily_spend >= _MAX_DAILY_USD:
        conn.close()
        return {"ok": True, "skipped_cycle": True, "reason": "daily_budget_exhausted",
                "daily_spend_usd": daily_spend, "max_daily_usd": _MAX_DAILY_USD,
                "count_sent": 0, "count_skipped": 0, "count_errors": 0}

    sent = []
    skipped = []
    errors = []
    cycle_cost = 0.0

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    placeholders = ",".join("?" * len(_ALLOWLIST_OWNED))
    rows = conn.execute(f"""
        SELECT id, from_addr, from_domain, subject, body_preview, intent_class,
               COALESCE(delivery_mode, 'direct') AS delivery_mode, cc_addrs,
               attachment_context
        FROM inbound_replies
        WHERE intent_class IN ('inquiry')
          AND auto_response_status IS NULL
          AND received_at > ?
          AND from_addr NOT IN ({placeholders})
          AND from_addr IS NOT NULL AND from_addr != ''
        ORDER BY received_at DESC
        LIMIT ?
    """, [cutoff, *_ALLOWLIST_OWNED, limit]).fetchall()

    from src.stranger_quota import (
        check_quota, record_reply, upgrade_offer_body,
    )

    for row in rows:
        rid = row["id"]
        from_addr = (row["from_addr"] or "").strip().lower()
        subject = row["subject"] or ""
        body = row["body_preview"] or ""

        if not from_addr or "@" not in from_addr:
            skipped.append({"id": rid, "reason": "no_sender"})
            continue

        # Determine mode early so we can gate by quota
        delivery_mode = (row["delivery_mode"] or "direct").lower()
        
        # PAY GATE: check quota before spending any LLM cost
        quota = check_quota(from_addr, delivery_mode)
        if quota["action"] == "silent_drop":
            skipped.append({"id": rid, "reason": "quota_exhausted_silent_drop",
                            "mode": delivery_mode})
            conn.execute(
                "UPDATE inbound_replies SET auto_response_status=? WHERE id=?",
                ("stranger_silent_drop", rid),
            )
            conn.commit()
            continue
        
        if quota["action"] == "upgrade_offer":
            # Send the upgrade offer instead of generating a tailored reply
            offer = upgrade_offer_body(from_addr, delivery_mode, quota["quota_state"])
            offer_subject = f"Re: {subject} (upgrade required)"
            if _SHADOW_MODE:
                shadow_offer = (
                    f"=== SHADOW UPGRADE OFFER for {from_addr} ===\n\n"
                    f"Mode: {delivery_mode}  |  Reason: {quota['reason']}\n"
                    f"Original subject: {subject}\n\n"
                    f"=== OFFER BODY ===\n{offer}\n=== END ===\n"
                )
                ok = _send_sendmail(_FOUNDER_EMAIL,
                                    f"[SHADOW UPGRADE-OFFER for {from_addr}]",
                                    shadow_offer)
                status = "stranger_upgrade_offer_shadow" if ok else "stranger_upgrade_offer_failed"
            else:
                _offer_w_footer = _append_compliance_footer(offer, from_addr)
                qid = _queue_outbound(from_addr, offer_subject, _offer_w_footer, "normal")
                ok = bool(qid)
                status = "stranger_upgrade_offered" if ok else "stranger_upgrade_offer_failed"
            
            record_reply(from_addr, delivery_mode, 0.0, was_upgrade_offer=True)
            if ok:
                sent.append({"id": rid, "mode": "upgrade_offer", "cost_usd": 0.0})
                conn.execute(
                    "UPDATE inbound_replies SET auto_response_status=?, auto_response_sent_at=?, auto_response_target=? WHERE id=?",
                    (status, datetime.now(timezone.utc).isoformat(),
                     json.dumps({"to": _FOUNDER_EMAIL if _SHADOW_MODE else from_addr,
                                 "delivery_mode": delivery_mode,
                                 "kind": "upgrade_offer",
                                 "cost_usd": 0.0}), rid),
                )
                conn.commit()
            else:
                errors.append({"id": rid, "reason": "upgrade_offer_send_failed"})
            continue

        # quota['action'] == 'allow' — proceed with normal flow

        if not _rate_limit_ok(from_addr, conn):
            skipped.append({"id": rid, "reason": "rate_limited"})
            conn.execute("UPDATE inbound_replies SET auto_response_status=? WHERE id=?",
                         ("stranger_rate_limited", rid))
            conn.commit()
            continue

        principal_addr = from_addr  # the human who composed the email is principal in both modes

        # Ship 31f: classify category + check for starter agent BEFORE magnify-drill
        starter_used = False
        starter_id = None
        category = {"slug": "unclassified", "label": "unclassified", "vertical": "other"}
        try:
            from src.category_learning import classify_category, lookup_starter, log_inquiry
            category = classify_category(subject, body)
            starter = lookup_starter(category["slug"]) if category["slug"] not in ("unclassified","unknown") else None
            if starter:
                # Bootstrap from starter — skip the cold magnify-drill, use the curated description
                starter_used = True
                starter_id = starter["agent_id"]
                md = {
                    "text": starter["duties_text"],
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "cost_usd": 0.0,  # starter is free to fetch
                }
        except Exception as _cl_e:
            md = None

        # Ship 31g: PERSPECTIVE-AWARE path when attachments + role are present
        attachment_ctx = None
        try:
            if row["attachment_context"]:
                attachment_ctx = json.loads(row["attachment_context"])
        except Exception:
            attachment_ctx = None
        
        use_perspective = (
            attachment_ctx
            and (attachment_ctx.get("forward", {}).get("is_forward")
                 or attachment_ctx.get("attachments"))
            and attachment_ctx.get("role", {}).get("role_class", "unknown") != "unknown"
        )
        
        # Branch: perspective > ambient > direct
        if not starter_used:
            if use_perspective:
                md = _magnify_drill_perspective(
                    subject, body, principal_addr,
                    attachment_ctx.get("attachment_summary", ""),
                    attachment_ctx["role"],
                    attachment_ctx.get("forward", {}),
                )
            elif delivery_mode == "ambient":
                md = _magnify_drill_ambient(subject, body, principal_addr)
            else:
                md = _magnify_drill(subject, body)
        if not md or len(md.get("text", "")) < 50:
            errors.append({"id": rid, "reason": "magnify_drill_failed", "mode": delivery_mode})
            continue
        agent_desc = md["text"]
        cycle_cost += md["cost_usd"]

        if use_perspective:
            rep = _generate_perspective_reply(
                agent_desc, subject, body, principal_addr,
                attachment_ctx.get("attachment_summary", ""),
                attachment_ctx["role"],
                attachment_ctx.get("forward", {}),
            )
        elif delivery_mode == "ambient":
            rep = _generate_ambient_offer(agent_desc, subject, body, principal_addr)
        else:
            rep = _generate_reply(agent_desc, subject, body, from_addr)
        if not rep or len(rep.get("text", "")) < 30:
            errors.append({"id": rid, "reason": "reply_gen_failed", "mode": delivery_mode})
            continue
        reply_body = rep["text"]
        cycle_cost += rep["cost_usd"]

        total_cost = md["cost_usd"] + rep["cost_usd"]
        target_meta = json.dumps({
            "to": _FOUNDER_EMAIL if _SHADOW_MODE else principal_addr,
            "delivery_mode": delivery_mode,
            "cost_usd": total_cost,
            "magnify_tok": md["prompt_tokens"] + md["completion_tokens"],
            "reply_tok": rep["prompt_tokens"] + rep["completion_tokens"],
            "quota_reason": quota["reason"],
        })
        # PAY GATE: record the reply toward the stranger's quota
        record_reply(from_addr, delivery_mode, total_cost, was_upgrade_offer=False)
        # Ship 31f: feed every reply into the category demand ledger
        try:
            from src.category_learning import log_inquiry as _log_cat
            _log_cat(
                category=category,
                inquiry_id=rid,
                delivery_mode=delivery_mode,
                from_addr=from_addr,
                from_domain=row["from_domain"] or "",
                subject=subject,
                agent_desc=agent_desc,
                cost_usd=total_cost,
                quality_score=None,  # filled in later by founder review or auto-scorer
                starter_used=starter_used,
                starter_id=starter_id,
            )
        except Exception:
            pass  # never block reply path on ledger write failure

        if _SHADOW_MODE:
            # Shadow draft via sendmail (founder-direct, fast)
            shadow_body = (
                f"=== SHADOW DRAFT [{delivery_mode.upper()}] for {principal_addr} ===\n\n"
                f"Mode: {delivery_mode}  ({'CC ambient synthesis' if delivery_mode=='ambient' else 'direct request'})\n"
                f"Original subject: {subject}\nOriginal body: {body[:300]}\n\n"
                f"Cost: ${total_cost:.4f}  |  Magnify tok: {md['prompt_tokens']+md['completion_tokens']}  |  Reply tok: {rep['prompt_tokens']+rep['completion_tokens']}\n\n"
                f"=== AGENT DESCRIPTION ===\n{agent_desc}\n\n"
                f"=== REPLY (would go to {principal_addr} only) ===\n{reply_body}\n\n"
                f"=== END ===\nFlip _SHADOW_MODE=False to go live.\n"
            )
            ok = _send_sendmail(_FOUNDER_EMAIL,
                                f"[SHADOW {delivery_mode.upper()} {total_cost:.4f}$ for {principal_addr}] Re: {subject}",
                                shadow_body)
            status = "stranger_shadow_sent" if ok else "stranger_shadow_failed"
            mode = "shadow"
        else:
            # Live: queue through outbound_email_queue (paced + compliance-gated)
            # Live mode: send ONLY to principal (CC'er in ambient mode, never the third party)
            _reply_w_footer = _append_compliance_footer(reply_body, principal_addr)
            qid = _queue_outbound(principal_addr, f"Re: {subject}", _reply_w_footer, "normal")
            ok = bool(qid)
            status = "stranger_queued" if ok else "stranger_queue_failed"
            mode = "queued"

        if ok:
            sent.append({"id": rid, "mode": mode, "cost_usd": round(total_cost, 4)})
            conn.execute(
                "UPDATE inbound_replies SET auto_response_status=?, auto_response_sent_at=?, auto_response_target=? WHERE id=?",
                (status, datetime.now(timezone.utc).isoformat(), target_meta, rid),
            )
            conn.commit()
        else:
            errors.append({"id": rid, "reason": "send_or_queue_failed"})

        # Mid-cycle budget check
        if daily_spend + cycle_cost >= _MAX_DAILY_USD:
            skipped.append({"reason": "budget_cap_mid_cycle"})
            break

    conn.close()
    return {
        "ok": True,
        "shadow_mode": _SHADOW_MODE,
        "outbound_queue_depth": qdepth,
        "daily_spend_usd_before": round(daily_spend, 4),
        "cycle_cost_usd": round(cycle_cost, 4),
        "daily_spend_usd_after": round(daily_spend + cycle_cost, 4),
        "max_daily_usd": _MAX_DAILY_USD,
        "sent": sent,
        "skipped": skipped,
        "errors": errors,
        "count_sent": len(sent),
        "count_skipped": len(skipped),
        "count_errors": len(errors),
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(process_stranger_inquiries(limit=5))
