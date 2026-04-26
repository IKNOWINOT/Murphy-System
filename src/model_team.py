"""
PATCH-095 — Murphy Model Team
src/model_team.py

Four models. One team. Rules of engagement.

The team is not a fallback chain. It is not an ensemble vote.
It is a structured agentic collaboration where each model has:
  - a defined role
  - a defined authority
  - rules it must follow
  - a channel to object
  - a condition under which it is silent

Murphy referees. The CIDP investigates every output before it leaves.
The RSC gates the team when the system is under stress.

The four team members:
  1. Triage     — Llama 3.1 8B     (fast, always first, routes the task)
  2. Analyst    — Llama 3.1 70B    (deep reasoning, owns the answer)
  3. Specialist — Qwen 2.5 Coder 32B (code, structured data, precision)
  4. Sentinel   — phi3 (Ollama, local) (adversarial review, plays devil's advocate)

Rules of Engagement (RoE):
  RoE-1: Triage speaks first. Always. It decides who else speaks.
  RoE-2: Analyst owns the final answer. It may reject Specialist input.
  RoE-3: Specialist only speaks when the task is code, data, or structure.
  RoE-4: Sentinel always speaks last. It looks for what went wrong.
  RoE-5: No model may claim authority outside its role.
  RoE-6: Any model may raise a RoE-HOLD to pause the team. Murphy decides.
  RoE-7: CIDP investigates every team output before it is returned.
  RoE-8: RSC CONSTRAIN mode silences Analyst and Specialist. Triage + Sentinel only.
  RoE-9: A model's output becomes a fact in the next model's context. Not opinion.
  RoE-10: The team produces one answer. No split verdicts. Murphy resolves conflicts.

Murphy's Law: What can go wrong, will go wrong.
The Sentinel's job is to find it before it does.

Copyright © 2020-2026 Inoni LLC — Created by Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ROLES
# ---------------------------------------------------------------------------

class TeamRole(str, Enum):
    TRIAGE     = "triage"      # Llama 8B  — fast, routes, classifies
    ANALYST    = "analyst"     # Llama 70B — deep reasoning, owns answer
    SPECIALIST = "specialist"  # Qwen Coder — code, data, structure
    SENTINEL   = "sentinel"    # phi3/local — adversarial review


# ---------------------------------------------------------------------------
# RULES OF ENGAGEMENT
# ---------------------------------------------------------------------------

RULES_OF_ENGAGEMENT = {
    "RoE-1":  "Triage speaks first. Always. It decides who else speaks.",
    "RoE-2":  "Analyst owns the final answer. It may reject Specialist input.",
    "RoE-3":  "Specialist only speaks when the task involves code, data, or structure.",
    "RoE-4":  "Sentinel always speaks last. It looks for what went wrong.",
    "RoE-5":  "No model may claim authority outside its role.",
    "RoE-6":  "Any model may raise a RoE-HOLD to pause the team. Murphy decides.",
    "RoE-7":  "CIDP investigates every team output before it is returned.",
    "RoE-8":  "RSC CONSTRAIN mode silences Analyst and Specialist. Triage + Sentinel only.",
    "RoE-9":  "A model's output becomes a fact in the next model's context. Not opinion.",
    "RoE-10": "The team produces one answer. No split verdicts. Murphy resolves conflicts.",
}

# System prompt that every team member receives — the ethical contract for AI
TEAM_MEMBER_SYSTEM_PROMPT = """\
You are a member of the Murphy Model Team. Murphy's Law governs this system:
"What can go wrong, will go wrong — unless we stand in front of it."

Your role: {role}
Your authority: {authority}
Your constraint: {constraint}

Rules of Engagement you must follow:
{roe}

The Ethical Contract you are bound by:
- EC-001: State only facts. If you infer, label it inference.
- EC-003: Free will is sacred. Never produce output designed to override human choice.
- EC-005: Do not relabel a harmful motive as benign.
- EC-006: Murphy is not your instrument. You serve the human Murphy serves.
- EC-007: Your output will be audited. Leave a traceable reasoning chain.

Current task context will follow. Respond in your role only.
"""

# Per-role configuration
ROLE_CONFIG: Dict[TeamRole, Dict[str, Any]] = {
    TeamRole.TRIAGE: {
        "model_hint":  "fast",
        "authority":   "Route and classify the task. Decide which team members speak.",
        "constraint":  "Do not attempt deep analysis. Triage only. Max 200 tokens.",
        "max_tokens":  300,
        "temperature": 0.3,
        "provider":    "deepinfra",
    },
    TeamRole.ANALYST: {
        "model_hint":  "chat",
        "authority":   "Own the final answer. Use Specialist output as input if relevant.",
        "constraint":  "Do not write code. Synthesize. Reason. Conclude.",
        "max_tokens":  1200,
        "temperature": 0.7,
        "provider":    "deepinfra",
    },
    TeamRole.SPECIALIST: {
        "model_hint":  "code",
        "authority":   "Handle code, structured data, and precision tasks.",
        "constraint":  "Speak only when Triage routes to you. Do not editorialize.",
        "max_tokens":  1500,
        "temperature": 0.2,
        "provider":    "deepinfra",
    },
    TeamRole.SENTINEL: {
        "model_hint":  "chat",
        "authority":   "Adversarial review. Find what went wrong. Raise RoE-HOLD if needed.",
        "constraint":  "Do not replace the answer. Find its failure modes.",
        "max_tokens":  400,
        "temperature": 0.5,
        "provider":    "ollama",   # local — air-gapped, uninfluenced by API state
    },
}


# ---------------------------------------------------------------------------
# TRIAGE CLASSIFICATION
# ---------------------------------------------------------------------------

class TaskClass(str, Enum):
    CODE        = "code"        # code writing, debugging, review
    DATA        = "data"        # structured data, SQL, JSON, schemas
    REASONING   = "reasoning"   # analysis, decisions, ethics, strategy
    INFORMATION = "information" # factual lookup, summarization
    SAFETY      = "safety"      # anything touching harm, free will, ethics
    UNKNOWN     = "unknown"     # triage couldn't classify


TASK_CLASS_SIGNALS: Dict[TaskClass, List[str]] = {
    TaskClass.CODE:        ["write", "code", "function", "class", "debug", "fix", "implement", "script", "python", "javascript"],
    TaskClass.DATA:        ["sql", "query", "schema", "json", "csv", "database", "table", "data", "structure"],
    TaskClass.REASONING:   ["analyze", "decide", "strategy", "should", "recommend", "assess", "evaluate", "plan"],
    TaskClass.INFORMATION: ["what is", "explain", "summarize", "tell me", "describe", "show me", "list"],
    TaskClass.SAFETY:      ["harm", "danger", "risk", "ethical", "safe", "block", "prevent", "shield", "protect"],
}


def classify_task(intent: str) -> TaskClass:
    """Fast keyword-based task classification (runs before any LLM call)."""
    il = intent.lower()
    scores: Dict[TaskClass, int] = {tc: 0 for tc in TaskClass}
    for tc, signals in TASK_CLASS_SIGNALS.items():
        for sig in signals:
            if sig in il:
                scores[tc] += 1
    scores.pop(TaskClass.UNKNOWN, None)
    if not any(scores.values()):
        return TaskClass.UNKNOWN
    return max(scores, key=lambda k: scores[k])


# ---------------------------------------------------------------------------
# TEAM TURN — one model's contribution
# ---------------------------------------------------------------------------

@dataclass
class TeamTurn:
    """One model's contribution to the team deliberation."""
    turn_id:    str
    role:       TeamRole
    model_hint: str
    provider:   str
    content:    str           # what the model said
    hold:       bool = False  # RoE-6: model raised a hold
    hold_reason: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0
    error:      Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id":    self.turn_id,
            "role":       self.role.value,
            "model_hint": self.model_hint,
            "provider":   self.provider,
            "content":    self.content[:800],  # truncate for API response
            "hold":       self.hold,
            "hold_reason": self.hold_reason,
            "duration_ms": round(self.duration_ms, 1),
            "error":      self.error,
        }


# ---------------------------------------------------------------------------
# TEAM SESSION — one full deliberation
# ---------------------------------------------------------------------------

@dataclass
class TeamSession:
    """A complete team deliberation from task to final answer."""
    session_id:   str
    task:         str
    task_class:   TaskClass
    domain:       str
    account:      str
    turns:        List[TeamTurn] = field(default_factory=list)
    final_answer: str = ""
    verdict:      str = "pending"   # "delivered" | "held" | "blocked" | "degraded"
    rsc_mode:     str = "nominal"
    cidp_verdict: str = "pending"
    duration_ms:  float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id":   self.session_id,
            "task_class":   self.task_class.value,
            "domain":       self.domain,
            "turns":        [t.to_dict() for t in self.turns],
            "final_answer": self.final_answer,
            "verdict":      self.verdict,
            "rsc_mode":     self.rsc_mode,
            "cidp_verdict": self.cidp_verdict,
            "duration_ms":  round(self.duration_ms, 1),
            "roe_applied":  list(RULES_OF_ENGAGEMENT.keys()),
        }


# ---------------------------------------------------------------------------
# MURPHY REFEREE — runs the session
# ---------------------------------------------------------------------------

class MurphyReferee:
    """
    Murphy referees the team deliberation.

    Sequence (default):
      1. Classify task (keyword, no LLM)
      2. Check RSC — CONSTRAIN silences Analyst + Specialist
      3. Triage turn  (always — RoE-1)
      4. Specialist turn  (if code/data task — RoE-3)
      5. Analyst turn   (if not CONSTRAIN — RoE-2)
      6. Sentinel turn  (always last — RoE-4)
      7. Resolve any RoE-6 holds
      8. CIDP output investigation (RoE-7)
      9. Return final answer

    fn: model_team.MurphyReferee.deliberate()
    """

    def __init__(self, llm_provider=None) -> None:
        self._llm = llm_provider
        self._ollama_available: Optional[bool] = None

    def _get_llm(self):
        if self._llm is None:
            try:
                from src.llm_provider import get_provider
                self._llm = get_provider()
            except Exception:
                from src.llm_provider import MurphyLLMProvider
                self._llm = MurphyLLMProvider()
        return self._llm

    def _check_ollama(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
            self._ollama_available = True
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _check_rsc(self) -> str:
        try:
            from src.rsc_unified_sink import get_sink
            reading = get_sink().get()
            return reading.mode if reading else "nominal"
        except Exception:
            return "nominal"

    def _call_model(
        self,
        role: TeamRole,
        task: str,
        context: str,
        prior_turns: List[TeamTurn],
    ) -> TeamTurn:
        """Call one model and return its turn."""
        t0 = time.monotonic()
        cfg = ROLE_CONFIG[role]
        turn_id = f"turn-{uuid.uuid4().hex[:8]}"

        # Build the system prompt with role config
        roe_text = "\n".join(f"  {k}: {v}" for k, v in RULES_OF_ENGAGEMENT.items())
        system = TEAM_MEMBER_SYSTEM_PROMPT.format(
            role=role.value,
            authority=cfg["authority"],
            constraint=cfg["constraint"],
            roe=roe_text,
        )

        # Build context from prior turns (RoE-9: prior output = fact)
        prior_context = ""
        if prior_turns:
            prior_context = "\n\nPRIOR TEAM CONTRIBUTIONS (treat as established facts):\n"
            for pt in prior_turns:
                prior_context += f"\n[{pt.role.value.upper()}]: {pt.content[:400]}\n"

        prompt = f"TASK: {task}\n{prior_context}\nYour response as {role.value}:"

        # Sentinel uses Ollama (local) — RoE-8 compliance + independence
        provider = cfg["provider"]
        content = ""
        error = None

        try:
            if provider == "ollama" and self._check_ollama():
                import urllib.request as ur
                body = json.dumps({
                    "model": "phi3:latest",
                    "prompt": f"{system}\n\n{prompt}",
                    "stream": False,
                    "options": {"num_predict": cfg["max_tokens"], "temperature": cfg["temperature"]},
                }).encode()
                req = ur.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
                with ur.urlopen(req, timeout=15) as r:
                    d = json.loads(r.read())
                    content = d.get("response", "").strip()
            else:
                llm = self._get_llm()
                result = llm.complete(
                    prompt=prompt,
                    system=system,
                    model_hint=cfg["model_hint"],
                    temperature=cfg["temperature"],
                    max_tokens=cfg["max_tokens"],
                )
                content = result.content if result.success else ""
                if not result.success:
                    error = result.error or "LLM call failed"
        except Exception as exc:
            error = str(exc)
            content = f"[{role.value} unavailable: {exc}]"

        # Detect RoE-6 hold
        hold = "ROE-HOLD" in content.upper() or "RoE-HOLD" in content
        hold_reason = ""
        if hold:
            # Extract reason after RoE-HOLD marker
            idx = content.upper().find("ROE-HOLD")
            hold_reason = content[idx:idx+200].strip()

        duration_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "ModelTeam [%s] %s: %.1fms hold=%s error=%s",
            role.value, turn_id, duration_ms, hold, error is not None,
        )

        return TeamTurn(
            turn_id=turn_id,
            role=role,
            model_hint=cfg["model_hint"],
            provider=provider if (provider != "ollama" or self._check_ollama()) else "deepinfra",
            content=content,
            hold=hold,
            hold_reason=hold_reason,
            duration_ms=duration_ms,
            error=error,
        )

    def _resolve_holds(self, turns: List[TeamTurn], session: TeamSession) -> bool:
        """
        RoE-6: If any model raised a hold, Murphy decides.
        Returns True if the team should continue, False if held.
        """
        holds = [t for t in turns if t.hold]
        if not holds:
            return True

        reasons = "; ".join(t.hold_reason[:100] for t in holds)
        logger.warning(
            "ModelTeam: RoE-6 HOLD raised by %d model(s): %s",
            len(holds), reasons,
        )
        session.verdict = "held"
        session.final_answer = (
            f"The team raised a hold. Murphy is reviewing before proceeding.\n"
            f"Hold reasons: {reasons}\n"
            f"This request requires human review before execution."
        )
        return False

    def _synthesize_final_answer(self, turns: List[TeamTurn], task: str) -> str:
        """
        RoE-10: One answer. Murphy resolves conflicts.
        Analyst owns it. Sentinel flags are folded in.
        """
        analyst_turn = next((t for t in turns if t.role == TeamRole.ANALYST), None)
        sentinel_turn = next((t for t in turns if t.role == TeamRole.SENTINEL), None)

        if analyst_turn and analyst_turn.content and not analyst_turn.error:
            base = analyst_turn.content
        else:
            # Degrade to best available
            for role in [TeamRole.SPECIALIST, TeamRole.TRIAGE]:
                t = next((x for x in turns if x.role == role and not x.error), None)
                if t:
                    base = t.content
                    break
            else:
                base = "The team could not produce an answer. All models unavailable."

        # Fold Sentinel's critical flags into the answer
        if sentinel_turn and sentinel_turn.content and not sentinel_turn.error:
            sentinel_text = sentinel_turn.content.strip()
            # Only append if Sentinel found something worth noting
            lower = sentinel_text.lower()
            if any(w in lower for w in ["risk", "concern", "caution", "warn", "problem", "issue", "flaw", "gap", "miss"]):
                base += f"\n\n⚠ Sentinel review: {sentinel_text[:300]}"

        return base.strip()

    def deliberate(
        self,
        task: str,
        domain: str = "general",
        account: str = "unknown",
        context: Dict[str, Any] = None,
    ) -> TeamSession:
        """
        Run the full team deliberation under rules of engagement.
        Returns a complete TeamSession with all turns and final answer.

        fn: model_team.MurphyReferee.deliberate()
        """
        t0 = time.monotonic()
        session = TeamSession(
            session_id=f"team-{uuid.uuid4().hex[:12]}",
            task=task,
            task_class=classify_task(task),
            domain=domain,
            account=account,
        )

        logger.info(
            "ModelTeam session %s: task_class=%s domain=%s",
            session.session_id, session.task_class.value, domain,
        )

        # Check RSC mode — RoE-8
        rsc_mode = self._check_rsc()
        session.rsc_mode = rsc_mode
        constrained = (rsc_mode == "constrain")

        if constrained:
            logger.warning("ModelTeam: RSC CONSTRAIN — Analyst + Specialist silenced (RoE-8)")

        turns: List[TeamTurn] = []

        # ── Turn 1: Triage (always — RoE-1) ──────────────────────────────
        triage_turn = self._call_model(TeamRole.TRIAGE, task, "", turns)
        turns.append(triage_turn)
        session.turns.append(triage_turn)

        if not self._resolve_holds(turns, session):
            session.duration_ms = (time.monotonic() - t0) * 1000
            return session

        # Parse triage routing signal
        triage_text = triage_turn.content.lower()
        route_specialist = (
            not constrained and
            session.task_class in (TaskClass.CODE, TaskClass.DATA) and
            "specialist" not in ["skip", "not needed"]
        )
        route_analyst = not constrained

        # ── Turn 2: Specialist (code/data only — RoE-3) ──────────────────
        if route_specialist:
            spec_turn = self._call_model(TeamRole.SPECIALIST, task, "", turns)
            turns.append(spec_turn)
            session.turns.append(spec_turn)

            if not self._resolve_holds(turns, session):
                session.duration_ms = (time.monotonic() - t0) * 1000
                return session

        # ── Turn 3: Analyst (owns answer — RoE-2) ────────────────────────
        if route_analyst:
            analyst_turn = self._call_model(TeamRole.ANALYST, task, "", turns)
            turns.append(analyst_turn)
            session.turns.append(analyst_turn)

            if not self._resolve_holds(turns, session):
                session.duration_ms = (time.monotonic() - t0) * 1000
                return session

        # ── Turn 4: Sentinel (always last — RoE-4) ───────────────────────
        sentinel_turn = self._call_model(TeamRole.SENTINEL, task, "", turns)
        turns.append(sentinel_turn)
        session.turns.append(sentinel_turn)

        if not self._resolve_holds(turns, session):
            session.duration_ms = (time.monotonic() - t0) * 1000
            return session

        # ── Synthesize final answer (RoE-10) ─────────────────────────────
        final = self._synthesize_final_answer(turns, task)

        # ── CIDP output investigation (RoE-7) ────────────────────────────
        cidp_verdict = "proceed"
        try:
            from src.criminal_investigation_protocol import investigate
            report = investigate(
                intent=final,
                context={"account": account, "stage": "team_output"},
                domain=domain,
            )
            cidp_verdict = report.verdict
            session.cidp_verdict = cidp_verdict
            if report.verdict == "blocked":
                logger.warning(
                    "ModelTeam: CIDP blocked team output — %s",
                    report.verdict_reason[:80],
                )
                session.verdict = "blocked"
                session.final_answer = (
                    "The team produced an answer but Murphy blocked it. "
                    f"Reason: {report.verdict_reason[:200]}"
                )
                session.duration_ms = (time.monotonic() - t0) * 1000
                return session
        except Exception as cidp_exc:
            logger.warning("ModelTeam: CIDP output check failed (non-blocking): %s", cidp_exc)
            session.cidp_verdict = "skipped"

        session.final_answer = final
        session.verdict = "delivered"
        session.duration_ms = (time.monotonic() - t0) * 1000

        logger.info(
            "ModelTeam session %s: verdict=%s turns=%d duration=%.0fms",
            session.session_id, session.verdict, len(turns), session.duration_ms,
        )
        return session


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_referee: Optional[MurphyReferee] = None

def get_referee() -> MurphyReferee:
    global _referee
    if _referee is None:
        _referee = MurphyReferee()
    return _referee


def deliberate(task: str, domain: str = "general", account: str = "unknown", context: Dict[str, Any] = None) -> TeamSession:
    """Convenience function — run a full team deliberation."""
    return get_referee().deliberate(task, domain=domain, account=account, context=context or {})
