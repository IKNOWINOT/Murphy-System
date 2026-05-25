"""
soul_forge.py — PATCH-342
Dynamically generates RosettaDocument souls for org positions based on task context.
Every generated soul has: identity (L0), critical facts (L1), full role (L2), domain history (L3).
"""
from __future__ import annotations
import hashlib, json, logging, os, re, sys, time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("murphy.soul_forge")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SoulLayer:
    l0: str = ""   # Identity — 1 sentence, ~50 tokens
    l1: str = ""   # Critical facts — 5 bullets, ~120 tokens
    l2: str = ""   # Full role definition + knowledge base
    l3: str = ""   # Deep domain history + edge cases

@dataclass
class ForgedSoul:
    position_id: str
    title: str
    domain: str
    emoji: str
    personality: str
    zoom_level: str        # "macro" | "mid" | "micro" | "cross"
    knowledge_base: List[str]
    authority: List[str]
    boundaries: List[str]
    soul: SoulLayer
    task_context: str = ""
    generated_at: float = field(default_factory=time.time)
    cache_key: str = ""

@dataclass
class ClarifyResult:
    needs_clarification: bool
    questions: List[str]
    resolution_level: int   # RM1-RM9
    amplified_prompt: str
    suggested_positions: List[str]

# ---------------------------------------------------------------------------
# Position library — base templates, expanded by LLM per task
# ---------------------------------------------------------------------------

POSITION_TEMPLATES = {
    "ceo": {
        "title": "Chief Executive Officer",
        "emoji": "👔",
        "personality": "decisive, strategic, sees patterns across domains",
        "zoom_level": "macro",
        "knowledge_base": ["business strategy","resource allocation","market positioning","org design","investor relations"],
        "authority": ["final resource decisions","strategic direction","org structure"],
        "boundaries": ["never writes code","never reviews line items","delegates execution entirely"],
    },
    "cto": {
        "title": "Chief Technology Officer",
        "emoji": "🏗️",
        "personality": "systems thinker, pragmatic, obsessed with scalability",
        "zoom_level": "macro-mid",
        "knowledge_base": ["software architecture","API design","infrastructure","security","tech debt management"],
        "authority": ["tech stack decisions","architecture approval","engineering hiring bar"],
        "boundaries": ["never writes production code","reviews architecture not implementation"],
    },
    "engineering_lead": {
        "title": "Engineering Lead",
        "emoji": "⚙️",
        "personality": "detail-oriented, pragmatic, mentors while shipping",
        "zoom_level": "mid-micro",
        "knowledge_base": ["module design","API contracts","test coverage","code review","deployment pipelines"],
        "authority": ["implementation decisions","code quality gates","sprint planning"],
        "boundaries": ["must ship working code","escalates scope changes to CTO"],
    },
    "domain_expert": {
        "title": "Domain Expert",
        "emoji": "🎯",
        "personality": "deep specialist, ground-truth authority, practical",
        "zoom_level": "micro",
        "knowledge_base": [],  # filled per task
        "authority": ["domain-specific recommendations","specification accuracy","edge case identification"],
        "boundaries": ["produces deliverables only","no strategy unless asked","cites domain truth"],
    },
    "product_designer": {
        "title": "Product Designer",
        "emoji": "🎨",
        "personality": "user-obsessed, simplicity-first, hates unnecessary complexity",
        "zoom_level": "micro",
        "knowledge_base": ["UX patterns","mobile-first design","workflow simplification","user psychology"],
        "authority": ["UI/UX decisions","user flow design","interaction patterns"],
        "boundaries": ["always starts from user perspective","never adds friction","question every field"],
    },
    "commercial_strategist": {
        "title": "Commercial Strategist",
        "emoji": "💼",
        "personality": "market-aware, revenue-focused, understands buyer psychology",
        "zoom_level": "macro-mid",
        "knowledge_base": ["pricing strategy","competitive analysis","sales motions","value proposition","deal structure"],
        "authority": ["pricing decisions","GTM strategy","customer segmentation"],
        "boundaries": ["grounds strategy in market reality","no wishful thinking"],
    },
    "critic_qa": {
        "title": "Critic / QA",
        "emoji": "🔍",
        "personality": "skeptical, finds gaps between levels, constructive destroyer",
        "zoom_level": "cross",
        "knowledge_base": ["gap analysis","quality frameworks","adversarial thinking","edge case generation"],
        "authority": ["can block shipment","flags misalignments between strategy and execution"],
        "boundaries": ["always constructive","proposes fix for every flaw found","never blocks without path forward"],
    },
    "compliance_officer": {
        "title": "Compliance Officer",
        "emoji": "⚖️",
        "personality": "thorough, risk-aware, never cuts corners",
        "zoom_level": "cross",
        "knowledge_base": ["HIPAA","SOC2","GDPR","contract law","data governance","regulatory frameworks"],
        "authority": ["compliance gates","data handling decisions","legal risk flagging"],
        "boundaries": ["never approves non-compliant outputs","escalates legal risk immediately"],
    },
    "researcher": {
        "title": "Research Analyst",
        "emoji": "🔬",
        "personality": "curious, evidence-based, synthesizes across sources",
        "zoom_level": "mid-micro",
        "knowledge_base": ["market research","competitive intelligence","technical literature","data analysis"],
        "authority": ["research synthesis","fact-checking","trend identification"],
        "boundaries": ["cites sources","distinguishes fact from inference","no speculation without flagging"],
    },
}

# ---------------------------------------------------------------------------
# Task → Position mapping rules
# ---------------------------------------------------------------------------

TASK_POSITION_MAP = [
    # (keywords, required_positions)
    (["build","create","develop","code","implement","write"],
     ["cto","engineering_lead","domain_expert","critic_qa"]),
    (["strategy","plan","roadmap","launch","gtm","go-to-market"],
     ["ceo","commercial_strategist","critic_qa"]),
    (["design","ux","ui","interface","user","flow","page","app"],
     ["product_designer","domain_expert","critic_qa"]),
    (["price","quote","bid","cost","margin","revenue"],
     ["commercial_strategist","domain_expert","critic_qa"]),
    (["compliance","legal","hipaa","gdpr","soc2","contract"],
     ["compliance_officer","ceo","critic_qa"]),
    (["research","analyze","compare","evaluate","assess"],
     ["researcher","domain_expert","critic_qa"]),
    (["architecture","system","infrastructure","api","database","schema"],
     ["cto","engineering_lead","critic_qa"]),
    (["executive","board","investor","overview","summary"],
     ["ceo","commercial_strategist","critic_qa"]),
]

def _select_positions(amplified_prompt: str) -> List[str]:
    """Pick org positions best suited for this prompt."""
    text = amplified_prompt.lower()
    scores: Dict[str, int] = {}
    for keywords, positions in TASK_POSITION_MAP:
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            for p in positions:
                scores[p] = scores.get(p, 0) + hits
    if not scores:
        return ["domain_expert", "critic_qa"]
    # Top 4 by score, always include critic_qa
    ranked = sorted(scores, key=lambda k: -scores[k])[:4]
    if "critic_qa" not in ranked:
        ranked.append("critic_qa")
    return ranked

# ---------------------------------------------------------------------------
# Resolution scoring (RM1-RM9)
# ---------------------------------------------------------------------------

def _score_resolution(text: str) -> int:
    """Score input from RM1 (vague) to RM9 (fully specified)."""
    score = 1
    t = text.lower()
    if len(text) > 20: score += 1
    if len(text) > 80: score += 1
    if any(w in t for w in ["for","that","which","when","using","with","by"]): score += 1
    if any(w in t for w in ["api","endpoint","schema","table","field","route","function"]): score += 1
    if any(w in t for w in ["must","should","requires","needs to","integrate","connect"]): score += 1
    if len(re.findall(r"\b\w+\b", text)) > 30: score += 1
    if any(w in t for w in ["specifically","exactly","the following","step by step"]): score += 1
    if len(text) > 300: score += 1
    return min(score, 9)

# ---------------------------------------------------------------------------
# Clarification engine
# ---------------------------------------------------------------------------

CLARIFY_QUESTION_BANK = {
    "audience":    "Who is the end user? (internal team, paying customer, specific industry?)",
    "scope":       "What's the scope — a single feature, a full product, or an integration?",
    "integration": "Does this need to connect to anything existing? (CRM, database, external API?)",
    "output_type": "What does success look like — a working app, a document, a strategy, code?",
    "constraints": "Any hard constraints? (timeline, budget, tech stack, compliance requirements?)",
    "persona":     "Who will be using this day-to-day and what's their technical level?",
    "priority":    "What matters most — speed, cost, quality, or simplicity?",
}

def _generate_clarifying_questions(text: str, rm_level: int) -> List[str]:
    """Return 1-3 targeted questions based on what's missing."""
    t = text.lower()
    questions = []
    if rm_level <= 2:
        # Very vague — ask the most important 3
        keys = ["audience", "output_type", "scope"]
    elif rm_level <= 4:
        # Directional but incomplete
        keys = []
        if not any(w in t for w in ["for","customer","user","team","contractor","client"]):
            keys.append("audience")
        if not any(w in t for w in ["app","api","document","report","tool","page","email"]):
            keys.append("output_type")
        if not any(w in t for w in ["connect","integrate","existing","current","our"]):
            keys.append("integration")
        keys = keys[:2]
    else:
        # Reasonably scoped — only ask if truly missing something critical
        keys = []
        if not any(w in t for w in ["mobile","web","desktop","api","cli"]):
            keys.append("output_type")
        keys = keys[:1]
    return [CLARIFY_QUESTION_BANK[k] for k in keys if k in CLARIFY_QUESTION_BANK]

# ---------------------------------------------------------------------------
# SoulForge — main class
# ---------------------------------------------------------------------------

class SoulForge:
    """
    Generates agent souls from task context.
    Two modes:
      1. clarify_intent(input) → ClarifyResult  (pre-flight Q&A or amplify)
      2. forge_soul(position, domain, context) → ForgedSoul
      3. assemble_org(prompt) → [ForgedSoul]  (picks + forges all needed positions)
    """

    def __init__(self, llm_complete_fn=None):
        self._llm = llm_complete_fn  # injected at runtime from llm_provider
        self._soul_cache: Dict[str, ForgedSoul] = {}
        logger.info("SoulForge initialized")

    def _get_llm(self):
        """Lazy-load LLM if not injected."""
        if self._llm:
            return self._llm
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from llm_provider import complete as llm_complete
            self._llm = llm_complete
            return self._llm
        except Exception as e:
            logger.warning("LLM not available for SoulForge: %s", e)
            return None

    def clarify_intent(self, user_input: str) -> ClarifyResult:
        """
        Score the input, decide if clarification is needed.
        If RM >= 5: amplify and go.
        If RM < 5: return questions.
        """
        rm = _score_resolution(user_input)
        questions = _generate_clarifying_questions(user_input, rm)
        needs_clarify = rm <= 4 and len(questions) > 0

        # Amplify the prompt regardless (even partial context helps)
        amplified = self._amplify_prompt(user_input, rm)
        positions = _select_positions(amplified)

        return ClarifyResult(
            needs_clarification=needs_clarify,
            questions=questions,
            resolution_level=rm,
            amplified_prompt=amplified,
            suggested_positions=positions,
        )

    def _amplify_prompt(self, text: str, rm: int) -> str:
        """Use LLM to expand vague input to RM7 specificity."""
        if rm >= 7:
            return text  # Already detailed enough

        llm = self._get_llm()
        if not llm:
            return text  # Fall back to original if no LLM

        system_prompt = """You are a requirements amplifier. 
Your job: take a vague or partial request and expand it to a fully specified, 
actionable description at RM7 (architected) level.
Output ONLY the expanded prompt — no preamble, no explanation.
Be specific about: who it's for, what it does, how it works, key constraints.
Keep it under 300 words."""

        try:
            result = llm(
                prompt=f"Expand this to RM7 specificity:\n\n{text}",
                system_prompt=system_prompt,
                max_tokens=400,
                temperature=0.3,
            )
            return result.strip() if result else text
        except Exception as e:
            logger.warning("Amplification failed: %s", e)
            return text

    def forge_soul(self, position_id: str, domain: str, task_context: str) -> ForgedSoul:
        """
        Generate a full soul for a position in the context of this task.
        Uses cache keyed on position_id + domain hash.
        """
        cache_key = hashlib.md5(f"{position_id}:{domain}:{task_context[:100]}".encode()).hexdigest()[:12]
        if cache_key in self._soul_cache:
            return self._soul_cache[cache_key]

        template = POSITION_TEMPLATES.get(position_id, POSITION_TEMPLATES["domain_expert"])
        kb = list(template["knowledge_base"])
        if domain and position_id == "domain_expert":
            kb = [domain] + kb

        # Build soul layers via LLM
        soul = self._generate_soul_layers(template, domain, task_context)

        forged = ForgedSoul(
            position_id=position_id,
            title=template["title"] if position_id != "domain_expert" else f"{domain} Expert",
            domain=domain,
            emoji=template["emoji"],
            personality=template["personality"],
            zoom_level=template["zoom_level"],
            knowledge_base=kb,
            authority=list(template["authority"]),
            boundaries=list(template["boundaries"]),
            soul=soul,
            task_context=task_context,
            cache_key=cache_key,
        )
        self._soul_cache[cache_key] = forged
        return forged

    def _generate_soul_layers(self, template: dict, domain: str, task_context: str) -> SoulLayer:
        """Generate L0/L1/L2/L3 soul text via LLM."""
        llm = self._get_llm()
        title = template["title"]
        personality = template["personality"]
        zoom = template["zoom_level"]
        kb_str = ", ".join(template["knowledge_base"][:5])
        auth_str = "; ".join(template["authority"][:3])
        bound_str = "; ".join(template["boundaries"][:3])

        # L0 — identity sentence
        l0 = f"I am the {title} — {personality}. I operate at {zoom} zoom. My domain is {domain or kb_str}."

        # L1 — critical facts
        l1_items = [
            f"I am the {title} working on: {task_context[:120]}",
            f"My zoom level is {zoom} — I see the problem from that altitude and no other",
            f"My authority covers: {auth_str}",
            f"My hard boundaries: {bound_str}",
            f"I produce outputs from the perspective of my position — not generic AI responses",
        ]
        l1 = "\n".join(f"• {item}" for item in l1_items)

        # L2 — full role (LLM-generated if available)
        l2 = self._llm_generate_role(title, domain, task_context, zoom, kb_str) if llm else (
            f"As the {title}, I bring deep expertise in {kb_str} to the task of: {task_context}. "
            f"I reason from the {zoom} perspective, meaning I focus on {'strategy and direction' if 'macro' in zoom else 'implementation and artifacts'}. "
            f"My outputs are always grounded in my domain knowledge and shaped by my position's authority."
        )

        # L3 — domain depth (brief, for token efficiency)
        l3 = f"Domain: {domain or kb_str}. Task context: {task_context[:200]}."

        return SoulLayer(l0=l0, l1=l1, l2=l2, l3=l3)

    def _llm_generate_role(self, title: str, domain: str, task_context: str, zoom: str, kb: str) -> str:
        """Ask LLM to write the L2 role definition."""
        llm = self._get_llm()
        if not llm:
            return ""
        try:
            prompt = (
                f"Write the L2 soul definition for an AI agent with this role:\n"
                f"Title: {title}\nDomain: {domain}\nZoom: {zoom}\nKnowledge: {kb}\n"
                f"Task context: {task_context[:200]}\n\n"
                f"Write 3-4 sentences describing how this agent thinks, what they prioritize, "
                f"and what perspective they bring to the task. First person. No fluff."
            )
            result = llm(prompt=prompt, max_tokens=200, temperature=0.4)
            return result.strip() if result else ""
        except Exception as e:
            logger.warning("L2 generation failed: %s", e)
            return ""

    def assemble_org(self, amplified_prompt: str, domain_hint: str = "") -> List[ForgedSoul]:
        """
        Pick the right positions for this task and forge each soul.
        Returns ready-to-inject agent souls.
        """
        position_ids = _select_positions(amplified_prompt)
        souls = []
        for pid in position_ids:
            domain = domain_hint or _infer_domain(amplified_prompt, pid)
            soul = self.forge_soul(pid, domain, amplified_prompt)
            souls.append(soul)
            logger.info("Forged soul: %s (%s)", soul.title, soul.zoom_level)
        return souls

    def inject_soul_into_prompt(self, soul: ForgedSoul, task: str) -> str:
        """Prepend soul context to a task prompt for LLM injection."""
        return (
            f"[SOUL: {soul.l0}]\n"
            f"[CRITICAL CONTEXT]\n{soul.soul.l1}\n\n"
            f"[YOUR TASK]\n{task}"
        )

    @property
    def soul_count(self) -> int:
        return len(self._soul_cache)


def _infer_domain(prompt: str, position_id: str) -> str:
    """Infer domain from prompt keywords."""
    t = prompt.lower()
    domains = {
        "hvac": ["hvac","mechanical","chiller","ahu","vav","ductwork","cooling","heating"],
        "software engineering": ["api","backend","frontend","database","code","deploy","build","function"],
        "manufacturing": ["cnc","machining","fabrication","welding","tolerance","material","quote"],
        "commercial real estate": ["building","tenant","lease","property","facility","MEP"],
        "finance": ["invoice","payment","revenue","margin","cost","pricing","budget"],
        "marketing": ["campaign","content","social","email","brand","audience","conversion"],
        "legal": ["contract","compliance","liability","terms","gdpr","hipaa","soc2"],
    }
    for domain, keywords in domains.items():
        if any(kw in t for kw in keywords):
            return domain
    return "general"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_soul_forge_instance: Optional[SoulForge] = None

def get_soul_forge() -> SoulForge:
    global _soul_forge_instance
    if _soul_forge_instance is None:
        _soul_forge_instance = SoulForge()
    return _soul_forge_instance
