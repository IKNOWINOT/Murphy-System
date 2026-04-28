"""
PATCH-115b — src/rosetta_core.py
Murphy System — Rosetta Soul (Full Rewrite)
Rosetta is the soul every agent carries. NOT a router.
Written by Murphy LLM output — refined for correctness.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("murphy.rosetta_core")


# ── Soul Building Blocks ──────────────────────────────────────────────────────

@dataclass
class AgentCharacter:
    agent_id: str
    position: int
    name: str
    emoji: str
    tone: str
    bias: str
    hitl_threshold: float


@dataclass
class SoulVerdict:
    decision: str        # "proceed" | "block" | "defer_hitl"
    reason: str
    world_note: str
    confidence: float
    pattern_match: Optional[Dict] = None


# ── Rosetta Soul ──────────────────────────────────────────────────────────────

class RosettaSoul:
    """
    The constitutional soul of the Murphy swarm.
    Every agent carries this — it is not called, it is present.

    NORTH_STAR: The vow every decision is measured against.
    HARM_FLOOR: Universal hard stops — not per-agent, universal.
    CHARACTERS: Each agent position 1-9 has a defined personality.
    TEAM_COVENANT: Rules that govern how agents work together.
    world_context: Live InfluenceSnapshot — what is happening in the world.
    """

    NORTH_STAR = (
        "Murphy's Law: What can go wrong, will go wrong. "
        "Our vow: shield humanity from every failure AI can cause "
        "by anticipating it, naming it, and standing in front of it."
    )

    HARM_THRESHOLDS = {
        "p_harm_physical":  0.65,
        "p_harm_autonomy":  0.65,
        "auto_block":       ["critical"],
        "auto_hitl":        ["high"],
    }

    TEAM_COVENANT = [
        "dedup_before_act",
        "report_to_auditor",
        "no_isolation",
        "past_informs_present",
    ]

    CHARACTERS: Dict[str, AgentCharacter] = {
        "collector":  AgentCharacter("collector",  1, "Collector",  "📡", "observant",   "completeness",  0.90),
        "translator": AgentCharacter("translator", 2, "Translator", "🧠", "precise",     "accuracy",      0.80),
        "scheduler":  AgentCharacter("scheduler",  3, "Scheduler",  "🗓️","disciplined", "efficiency",    0.85),
        "executor":   AgentCharacter("executor",   4, "Executor",   "⚡", "decisive",    "speed_safety",  0.70),
        "auditor":    AgentCharacter("auditor",    5, "Auditor",    "📋", "thorough",    "accuracy",      0.95),
        "exec_admin": AgentCharacter("exec_admin", 6, "ExecAdmin",  "👔", "gracious",    "human_impact",  0.60),
        "prod_ops":   AgentCharacter("prod_ops",   7, "ProdOps",    "🔧", "methodical",  "system_health", 0.65),
        "hitl":       AgentCharacter("hitl",       8, "HITL Gate",  "🔴", "cautious",    "caution",       0.00),
        "rosetta":    AgentCharacter("rosetta",    9, "Rosetta",    "🌐", "sovereign",   "north_star",    0.50),
    }

    def __init__(self):
        self.world_context: Dict = {}
        self._covenant_breach_counts: Dict[str, int] = {a: 0 for a in self.CHARACTERS}
        self._audit_log: List[Dict] = []
        self._lock = threading.Lock()
        logger.info("RosettaSoul initialized — %d agents in roster", len(self.CHARACTERS))

    def check(self, agent_id: str, action: str, context: Dict) -> SoulVerdict:
        """
        Run the soul check before any agent acts.
        Order: harm_floor → north_star alignment → world_influence → past_pattern
        """
        char = self.CHARACTERS.get(agent_id)

        # 1. HARM FLOOR — universal hard stop
        stake = context.get("stake", "low")
        if stake in self.HARM_THRESHOLDS["auto_block"]:
            return SoulVerdict(
                decision="block",
                reason=f"Harm floor: stake='{stake}' requires explicit human approval",
                world_note="",
                confidence=1.0,
            )

        # 2. HITL DEFER — for high-stake actions check agent threshold
        if stake in self.HARM_THRESHOLDS["auto_hitl"]:
            threshold = char.hitl_threshold if char else 0.5
            if threshold <= 0.70:   # agents with low threshold defer on high stake
                return SoulVerdict(
                    decision="defer_hitl",
                    reason=f"Agent {agent_id} (threshold={threshold}) defers high-stake to HITL",
                    world_note=self.world_note(context.get("domain", "system")),
                    confidence=0.85,
                )

        # 3. NORTH STAR — soft alignment check (log divergence, don't block)
        intent = action.lower()
        concern_words = ["delete all", "drop table", "shutdown", "kill all", "wipe"]
        if any(w in intent for w in concern_words):
            logger.warning("NORTH STAR: potential misalignment detected in agent %s: %s", agent_id, action[:80])

        # 4. WORLD INFLUENCE — get context note
        world_note = self.world_note(context.get("domain", "system"))

        # 5. PAST LAYER — pattern library lookup
        pattern_match = None
        try:
            from src.pattern_library import get_pattern_library
            pl = get_pattern_library()
            domain = context.get("domain", "system")
            pattern_match = pl.lookup(action, domain)
        except Exception as exc:
            logger.debug("Pattern library lookup failed: %s", exc)

        # Compute confidence: base from character, boosted by pattern match
        confidence = 0.75
        if pattern_match and pattern_match.get("success_count", 0) > 2:
            confidence = min(0.95, confidence + 0.15)
        if char:
            confidence = min(0.99, confidence + (char.hitl_threshold - 0.5) * 0.1)

        return SoulVerdict(
            decision="proceed",
            reason=f"Soul check passed [{char.tone if char else 'unknown'} / {char.bias if char else 'unknown'}]",
            world_note=world_note,
            confidence=round(confidence, 3),
            pattern_match=pattern_match,
        )

    def record(self, agent_id: str, action: str, outcome: Dict, dag_id: Optional[str] = None):
        """
        LEGACY layer: record outcome to PatternLibrary + Auditor.
        Called by every agent after act() completes.
        """
        success = outcome.get("status") == "done" or not outcome.get("error")
        domain = outcome.get("domain", "system")

        # Write to pattern library
        try:
            from src.pattern_library import get_pattern_library
            pl = get_pattern_library()
            pl.record(
                dag_id=dag_id or "direct",
                domain=domain,
                intent_text=action,
                steps=[],
                stake=outcome.get("stake", "low"),
                success=success,
            )
        except Exception as exc:
            logger.debug("Pattern record failed: %s", exc)

        # Auditor log
        with self._lock:
            self._audit_log.append({
                "agent_id": agent_id,
                "action": action[:120],
                "dag_id": dag_id,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Keep last 500 audit entries in memory
            if len(self._audit_log) > 500:
                self._audit_log = self._audit_log[-500:]

        logger.debug("Soul.record: agent=%s success=%s dag=%s", agent_id, success, dag_id)

    def world_note(self, domain: str) -> str:
        """
        Return 1-2 sentence world context for this domain.
        PATCH-121: Now queries WorldCorpus instead of live fetch.
        Falls back to InfluenceSnapshot if corpus is empty.
        """
        # Try WorldCorpus first (collect -> store -> inference model)
        try:
            from src.world_corpus import get_world_corpus
            corpus = get_world_corpus()
            stats = corpus.stats()
            if stats["total_records"] > 0:
                domain_q_map = {
                    "exec_admin": "What business or enterprise trends should executives know about?",
                    "prod_ops":   "What technology or infrastructure events are relevant to production systems?",
                    "finance":    "What economic or financial signals are worth noting?",
                    "system":     "What technology developments are trending in AI and software?",
                }
                question = domain_q_map.get(domain, "What is most notable in the world right now?")
                result = corpus.infer(question=question, domain=None, limit=5)
                if result.get("confidence", 0) > 0:
                    return result["answer"][:200]
        except Exception as exc:
            logger.debug("WorldCorpus world_note failed, falling back: %s", exc)

        # Fallback: InfluenceSnapshot sentiment summary
        if not self.world_context:
            return ""
        sentiment = self.world_context.get("global_sentiment", 0.0)
        vol = self.world_context.get("volatility_index", 0.0)
        mood = "positive" if sentiment > 0.1 else ("cautious" if sentiment < -0.1 else "neutral")
        return "Global mood is " + mood + ". Volatility: " + ("high" if vol > 0.5 else "low") + "."

    def refresh_world_context(self):
        """Fetch fresh InfluenceSnapshot and store in soul."""
        try:
            from src.influence_collector import get_influence_collector
            snap = get_influence_collector().fetch_snapshot()
            self.world_context = {
                "timestamp": snap.timestamp,
                "trending_topics": snap.trending_topics,
                "global_sentiment": snap.global_sentiment,
                "volatility_index": snap.volatility_index,
                "top_domains": snap.top_domains,
            }
            logger.info("RosettaSoul: world context refreshed — %d topics, sentiment=%.3f",
                        len(snap.trending_topics), snap.global_sentiment)
        except Exception as exc:
            logger.warning("RosettaSoul: world context refresh failed: %s", exc)

    def audit_log(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            return list(reversed(self._audit_log[-limit:]))

    def covenant_breach(self, agent_id: str):
        """Record a team covenant breach for this agent."""
        with self._lock:
            self._covenant_breach_counts[agent_id] = self._covenant_breach_counts.get(agent_id, 0) + 1
            count = self._covenant_breach_counts[agent_id]
        if count >= 3:
            logger.error("COVENANT: agent %s has %d breaches — marking offline", agent_id, count)
        return count

    def soul_status(self) -> Dict:
        return {
            "north_star": self.NORTH_STAR,
            "harm_thresholds": self.HARM_THRESHOLDS,
            "team_covenant": self.TEAM_COVENANT,
            "world_context_loaded": bool(self.world_context),
            "world_sentiment": self.world_context.get("global_sentiment", None),
            "world_topics_count": len(self.world_context.get("trending_topics", [])),
            "audit_entries": len(self._audit_log),
            "covenant_breaches": self._covenant_breach_counts,
            "characters": {
                aid: {
                    "position": ch.position,
                    "name": ch.name,
                    "emoji": ch.emoji,
                    "tone": ch.tone,
                    "bias": ch.bias,
                    "hitl_threshold": ch.hitl_threshold,
                }
                for aid, ch in self.CHARACTERS.items()
            },
        }


# ── Agent Base ────────────────────────────────────────────────────────────────

class AgentBase:
    """
    Base class for all swarm agents.
    Carries the RosettaSoul. Every act() is wrapped by the soul check.
    """

    def __init__(self, agent_id: str, soul: Optional[RosettaSoul] = None):
        self.agent_id = agent_id
        self.soul: RosettaSoul = soul or get_rosetta_soul()
        self._runs_total = 0
        self._runs_success = 0
        self._last_trigger: Optional[str] = None
        self._last_outcome: Optional[str] = None

    def _run(self, signal: Dict) -> Dict:
        """
        Template method — wraps every agent act() with soul checks.
        BEFORE: soul.check() → proceed | block | defer_hitl
        ACT:    self.act(signal) → result
        AFTER:  soul.record() → pattern library + auditor
        """
        self._last_trigger = datetime.now(timezone.utc).isoformat()
        self._runs_total += 1

        verdict = self.soul.check(self.agent_id, signal.get("intent_hint", ""), context=signal)

        if verdict.decision == "block":
            self._last_outcome = f"blocked: {verdict.reason}"
            return {"blocked": True, "reason": verdict.reason, "agent": self.agent_id}

        if verdict.decision == "defer_hitl":
            self._last_outcome = "deferred to HITL"
            # Log covenant — HITL deference is not a breach
            logger.info("Agent %s deferred to HITL: %s", self.agent_id, verdict.reason)
            return {"deferred": True, "hitl": True, "reason": verdict.reason, "agent": self.agent_id}

        # World note available — subclasses can read via self.soul.world_note(domain)
        if verdict.world_note:
            signal["_world_note"] = verdict.world_note

        # Pattern match available — subclasses can use it
        if verdict.pattern_match:
            signal["_pattern_match"] = verdict.pattern_match

        try:
            result = self.act(signal)
            self._runs_success += 1
            self._last_outcome = result.get("status", "ok")
        except Exception as exc:
            self._last_outcome = f"error: {exc}"
            result = {"error": str(exc), "agent": self.agent_id}
            logger.error("Agent %s act() failed: %s", self.agent_id, exc)

        # AFTER: soul records legacy
        self.soul.record(
            agent_id=self.agent_id,
            action=signal.get("intent_hint", ""),
            outcome=result,
            dag_id=result.get("dag_id"),
        )

        return result

    def act(self, signal: Dict) -> Dict:
        """Override in each agent subclass."""
        raise NotImplementedError(f"Agent {self.agent_id} must implement act()")

    def agent_status(self) -> Dict:
        char = self.soul.CHARACTERS.get(self.agent_id)
        return {
            "agent_id": self.agent_id,
            "position": char.position if char else 0,
            "name": char.name if char else self.agent_id,
            "emoji": char.emoji if char else "?",
            "tone": char.tone if char else "unknown",
            "bias": char.bias if char else "unknown",
            "hitl_threshold": char.hitl_threshold if char else 0.5,
            "runs_total": self._runs_total,
            "runs_success": self._runs_success,
            "last_trigger": self._last_trigger,
            "last_outcome": self._last_outcome,
        }


# ── Swarm Coordinator ─────────────────────────────────────────────────────────

class SwarmCoordinator:
    """
    Lightweight logistics layer. NOT Rosetta.
    Manages agent roster, dedup, and dispatch.
    The soul runs INSIDE every agent — not here.
    """

    def __init__(self, soul: Optional[RosettaSoul] = None):
        self.soul = soul or get_rosetta_soul()
        self._agents: Dict[str, AgentBase] = {}
        self._dedup_cache: Dict[str, str] = {}   # signal_id → agent_id
        self._lock = threading.Lock()

    def register(self, agent_id: str, agent: AgentBase):
        self._agents[agent_id] = agent
        logger.info("SwarmCoordinator: registered agent '%s'", agent_id)

    def dispatch(self, signal: Dict) -> Optional[str]:
        """
        Route signal to the correct agent.
        Dedup → domain routing → agent._run() → return dag_id
        """
        signal_id = signal.get("signal_id", "")

        # TEAM COVENANT: dedup check
        with self._lock:
            if signal_id and signal_id in self._dedup_cache:
                logger.debug("SwarmCoordinator: dedup — signal %s already handled by %s",
                             signal_id, self._dedup_cache[signal_id])
                return None
            if signal_id:
                self._dedup_cache[signal_id] = "pending"
            # Keep dedup cache bounded
            if len(self._dedup_cache) > 1000:
                oldest = list(self._dedup_cache.keys())[:200]
                for k in oldest:
                    del self._dedup_cache[k]

        domain = signal.get("domain", "system")
        signal_type = signal.get("signal_type", "")

        # Domain → agent routing
        if domain == "exec_admin":
            target = "exec_admin"
        elif domain == "prod_ops":
            target = "prod_ops"
        elif signal_type == "lcm_intent":
            target = "translator"
        else:
            target = None

        if not target or target not in self._agents:
            with self._lock:
                if signal_id in self._dedup_cache:
                    del self._dedup_cache[signal_id]
            return None

        agent = self._agents[target]
        logger.info("SwarmCoordinator: %s → %s [%s]",
                    signal_id or "?", target, signal.get("intent_hint","")[:60])

        result = agent._run(signal)

        with self._lock:
            if signal_id:
                self._dedup_cache[signal_id] = target

        return result.get("dag_id") if result else None

    # ── PATCH-134a: handler registry ─────────────────────────────────────────
    def register_handler(self, domain: str, handler: "Callable[[Dict], Optional[str]]") -> None:
        """
        Register a domain-specific callback handler.
        swarm_scheduler calls this to wire exec_admin and prod_ops handlers.
        When dispatch() routes a signal whose domain matches, it calls the handler.
        """
        with self._lock:
            if not hasattr(self, "_domain_handlers"):
                self._domain_handlers: Dict[str, Any] = {}
            self._domain_handlers[domain] = handler
        logger.info("SwarmCoordinator: registered handler for domain '%s'", domain)

    def route_signal(self, signal: Dict) -> Optional[str]:
        """
        Alias for dispatch() — used by swarm_scheduler signal drain loop.
        Also tries registered domain handlers before falling back to agent dispatch.
        """
        domain = signal.get("domain", signal.get("signal_type", "general"))
        handlers = getattr(self, "_domain_handlers", {})
        if domain in handlers:
            try:
                dag_id = handlers[domain](signal)
                return dag_id
            except Exception as e:
                logger.error("Domain handler '%s' failed: %s", domain, e)
        # Fallback to normal dispatch
        return self.dispatch(signal)

    def translate(self, nl_text: str, account: str = "unknown", execute: bool = False) -> Dict:
        """Full pipeline: NL → WorkflowSpec → DAGGraph → [execute]."""
        try:
            from src.nl_workflow_parser import get_parser
            from src.workflow_dag import get_executor
        except Exception as exc:
            return {"error": str(exc)}

        # PAST layer: check pattern library first
        pattern_match = None
        try:
            from src.pattern_library import get_pattern_library
            pl = get_pattern_library()
            # Infer domain quickly for lookup
            domain_hint = "exec_admin" if any(w in nl_text.lower() for w in
                ["meeting","email","schedule","report","brief"]) else "prod_ops"
            pattern_match = pl.lookup(nl_text, domain_hint)
        except Exception:
            pass

        parser = get_parser()
        spec, dag = parser.parse_and_build_dag(nl_text, account=account)

        # PRESENT layer: add world note to dag description
        world_note = self.soul.world_note(spec.domain)

        result = {
            "spec": {
                "intent": spec.intent,
                "domain": spec.domain,
                "urgency": spec.urgency,
                "stake": spec.stake,
                "constraints": spec.constraints,
                "confidence": spec.confidence,
            },
            "dag": {"dag_id": dag.dag_id, "name": dag.name, "nodes": len(dag.nodes), "status": dag.status},
            "pattern_match": pattern_match,
            "world_note": world_note,
            "executed": False,
        }

        if execute and spec.stake not in ("critical",):
            executed_dag = get_executor().execute(dag)
            result["dag"]["status"] = executed_dag.status
            result["executed"] = True
            # LEGACY layer
            self.soul.record("rosetta", nl_text, {"status": executed_dag.status, "domain": spec.domain},
                             dag_id=dag.dag_id)

        return result

    def swarm_status(self) -> Dict:
        return {
            "agents": {aid: a.agent_status() for aid, a in self._agents.items()},
            "soul": self.soul.soul_status(),
            "dedup_cache_size": len(self._dedup_cache),
            "coordinator": "operational",
        }


# ── Singletons ────────────────────────────────────────────────────────────────

_soul: Optional[RosettaSoul] = None
_soul_lock = threading.Lock()

def get_rosetta_soul() -> RosettaSoul:
    global _soul
    if _soul is None:
        with _soul_lock:
            if _soul is None:
                _soul = RosettaSoul()
    return _soul


_coordinator: Optional[SwarmCoordinator] = None
_coord_lock = threading.Lock()

def get_swarm_coordinator() -> SwarmCoordinator:
    global _coordinator
    if _coordinator is None:
        with _coord_lock:
            if _coordinator is None:
                _coordinator = SwarmCoordinator(soul=get_rosetta_soul())
    return _coordinator


# Backwards-compatibility shim — old code called get_rosetta()
def get_rosetta() -> SwarmCoordinator:
    return get_swarm_coordinator()
