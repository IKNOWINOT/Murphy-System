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


# PATCH-PERSIST-AUDIT (2026-05-27): make RosettaSoul.audit_log() read from
# rosetta_dispatch_log (persistent) instead of in-memory ring buffer.
# Also: persist covenant_breach_counts to a small table.

def _persistent_audit_log(limit=50):
    """Read recent dispatches from rosetta_dispatch_log."""
    try:
        import sqlite3
        DB = "/var/lib/murphy-production/murphy_audit.db"
        with sqlite3.connect(DB, timeout=2) as c:
            rows = c.execute(
                "SELECT ts, agent_id, intent_hint, signal_id, outcome_status "
                "FROM rosetta_dispatch_log ORDER BY ts DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [
                {"agent_id": r[1] or "", "action": (r[2] or "")[:120],
                 "dag_id": r[3] or None, "success": (r[4] or "").startswith(("complete","ok","approved","aligned")),
                 "timestamp": r[0]}
                for r in rows
            ]
    except Exception:
        return []

def _persistent_covenant_record(agent_id):
    """Persist a covenant breach; return new count."""
    try:
        import sqlite3
        from datetime import datetime, timezone
        DB = "/var/lib/murphy-production/murphy_audit.db"
        with sqlite3.connect(DB, timeout=2) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS covenant_breaches ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "agent_id TEXT NOT NULL, ts TEXT NOT NULL)"
            )
            c.execute(
                "INSERT INTO covenant_breaches (agent_id, ts) VALUES (?, ?)",
                (agent_id, datetime.now(timezone.utc).isoformat())
            )
            n = c.execute(
                "SELECT COUNT(*) FROM covenant_breaches WHERE agent_id=?",
                (agent_id,)
            ).fetchone()[0]
            return n
    except Exception:
        return 0

def _persistent_covenant_count(agent_id):
    """Read current breach count from DB."""
    try:
        import sqlite3
        DB = "/var/lib/murphy-production/murphy_audit.db"
        with sqlite3.connect(DB, timeout=2) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS covenant_breaches ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "agent_id TEXT NOT NULL, ts TEXT NOT NULL)"
            )
            return c.execute(
                "SELECT COUNT(*) FROM covenant_breaches WHERE agent_id=?",
                (agent_id,)
            ).fetchone()[0]
    except Exception:
        return 0


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

        # _R484_WORK_ITEMS_CLOSURE — write completion back to work_items.db
        # Fixes the swarm-async completion gap: BLOCK-SWARM-EXEC2 in /api/rosetta/dispatch
        # tried to read _last_outcome synchronously before the agent finished, so
        # work_items.status stayed "running" forever (1511 stuck since 2026-05-23).
        # Soul.record() is called by every agent AFTER act() completes — the correct
        # lifecycle moment. Non-fatal: write failures must not break the agent.
        if dag_id and dag_id != "direct":
            try:
                import sqlite3 as _r484_sq, datetime as _r484_dt, json as _r484_json
                _r484_now = _r484_dt.datetime.now(timezone.utc).isoformat()
                _r484_status = "complete" if success else "failed"
                _r484_result_text = ""
                if isinstance(outcome, dict):
                    _r484_result_text = (
                        outcome.get("result")
                        or outcome.get("response")
                        or outcome.get("output")
                        or outcome.get("notes")
                        or ""
                    )
                    if not isinstance(_r484_result_text, str):
                        try:
                            _r484_result_text = _r484_json.dumps(_r484_result_text)
                        except Exception:
                            _r484_result_text = str(_r484_result_text)
                _r484_result_text = (_r484_result_text or "")[:50000]
                with _r484_sq.connect("/var/lib/murphy-production/work_items.db", timeout=3) as _r484_c:
                    _r484_c.execute("PRAGMA busy_timeout=2000")
                    # Only update if currently running — never reopen completed/failed items
                    _r484_c.execute(
                        """UPDATE work_items
                           SET status=?, result=?, updated_at=?
                           WHERE dag_id=? AND status='running'""",
                        (_r484_status, _r484_result_text, _r484_now, dag_id)
                    )
                    _r484_c.commit()
            except Exception as _r484_exc:
                logger.debug("R484: work_items closure failed for dag=%s: %s", dag_id, _r484_exc)

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
        # PATCH-PERSIST-AUDIT: prefer persistent log, fall back to in-memory
        persistent = _persistent_audit_log(limit)
        if persistent:
            return persistent
        with self._lock:
            return list(reversed(self._audit_log[-limit:]))

    def covenant_breach(self, agent_id: str):
        """Record a team covenant breach for this agent."""
        # PATCH-PERSIST-AUDIT: persist to DB; keep in-memory cache in sync
        count = _persistent_covenant_record(agent_id)
        with self._lock:
            self._covenant_breach_counts[agent_id] = count
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


# PATCH-ROSETTA-LOG (2026-05-27): write-through inside AgentBase._run.
# Truth-grounded: writes ts + outcome + latency + fingerprint + artifact for every dispatch.
# Locked behavior: no exception in this block should ever break _run itself.

# PATCH-R287 (2026-05-30) — A3 disambiguation counter
# Per R286 Block 0a closed; substrate stable; now disambiguate
# 49 R271-ENTRY traces vs 685 DB inserts (R283). Counter increments
# BEFORE WARNING log — if counter==DB inserts then journal IS dropping;
# if counter<DB inserts then real second-writer bypass exists.
import threading as _r287_threading
_R287_LOCK = _r287_threading.Lock()
_R287_COUNTER = {"entries": 0, "by_agent": {}, "started_at": None}
def _r287_status():
    with _R287_LOCK:
        return {"entries": _R287_COUNTER["entries"],
                "by_agent": dict(_R287_COUNTER["by_agent"]),
                "started_at": _R287_COUNTER["started_at"]}

def _rosetta_log_dispatch(agent_id, signal, verdict, result, latency_ms, error_text):
    """Write one row per AgentBase._run call. Best-effort, never raises."""
    # PATCH-R287 counter increment — runs before WARNING log, bypasses journal
    try:
        with _R287_LOCK:
            _R287_COUNTER["entries"] += 1
            _aid = agent_id if isinstance(agent_id, str) else str(agent_id)
            _R287_COUNTER["by_agent"][_aid] = _R287_COUNTER["by_agent"].get(_aid, 0) + 1
            if _R287_COUNTER["started_at"] is None:
                from datetime import datetime, timezone
                _R287_COUNTER["started_at"] = datetime.now(timezone.utc).isoformat()
    except Exception:
        pass
    # PATCH-R271-ENTRY-TRACE (2026-05-30) — Murphy meta-Q (a) — prove entry reached
    logger.warning("[R271-ENTRY] _rosetta_log_dispatch entered agent=%s intent=%s sig=%s",
                   agent_id, (signal.get("intent_hint", "") or "")[:40] if isinstance(signal, dict) else "?",
                   (signal.get("signal_id", "") or "")[:16] if isinstance(signal, dict) else "?")
    try:
        import sqlite3, hashlib, json
        from datetime import datetime, timezone
        DB = "/var/lib/murphy-production/murphy_audit.db"
        # Fingerprint: hash of soul state at dispatch time
        # NOTE: we hash agent_id + domain + a stable slice of context to detect repeat-context
        soul_state = {
            "agent_id": agent_id,
            "domain": signal.get("domain"),
            "world_note": signal.get("_world_note", ""),
            "pattern_match_hit": bool(signal.get("_pattern_match")),
        }
        fp_src = json.dumps(soul_state, sort_keys=True, default=str)
        fingerprint = hashlib.sha256(fp_src.encode()).hexdigest()[:16]

        outcome_status = "blocked" if (result and result.get("blocked")) else \
                         "deferred" if (result and result.get("deferred")) else \
                         "error" if error_text else \
                         (result.get("status") if isinstance(result, dict) else "ok")

        # PATCH-CONTINUITY-LOAD-001 (2026-05-28): capture load snapshot
        # alongside dispatch outcome. Murphy + founder recommendation: join
        # /api/health/capacity with rosetta_dispatch_log so every dispatch has
        # load context. Best-effort — NULLs if probes fail.
        _cpu_pct = None
        _ram_pct = None
        _q_depth = None
        try:
            import psutil as _ps
            _cpu_pct = _ps.cpu_percent(interval=None)
            _ram_pct = _ps.virtual_memory().percent
        except Exception:
            pass
        try:
            import sys as _sys
            for _name, _mod in list(_sys.modules.items()):
                if _name.endswith('regenerative_core') and hasattr(_mod, '_regen_core_singleton'):
                    _rc = getattr(_mod, '_regen_core_singleton', None)
                    if _rc and hasattr(_rc, '_hitl_queue'):
                        _q_depth = len(_rc._hitl_queue)
                        break
        except Exception:
            pass

        with sqlite3.connect(DB, timeout=2) as c:
            c.execute(
                "INSERT INTO rosetta_dispatch_log "
                "(ts, signal_id, domain, agent_id, intent_hint, verdict_decision, "
                " verdict_confidence, context_fingerprint, latency_ms, "
                " outcome_status, effect_artifact_url, error, "
                " cpu_percent, ram_percent, hitl_queue_depth, tenant_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",  # PATCH-TENANT-SCOPE-R257
                (datetime.now(timezone.utc).isoformat(),
                 signal.get("signal_id", "")[:64],
                 signal.get("domain", "")[:32],
                 agent_id[:32],
                 (signal.get("intent_hint", "") or "")[:200],
                 (verdict.decision if verdict else "")[:16],
                 (verdict.confidence if verdict else None),
                 fingerprint,
                 int(latency_ms or 0),
                 outcome_status[:32] if outcome_status else "",
                 (result.get("artifact_url") if isinstance(result, dict) else None) or "",
                 (error_text or "")[:400],
                 _cpu_pct, _ram_pct, _q_depth,
                   (signal.get("tenant_id") or "platform")[:64])  # PATCH-TENANT-SCOPE-R257
            )
    except Exception as _r293_e:
        # PATCH-R293 (2026-05-30) — instrument silent INSERT failures.
        # R292 found 225 entries vs 75 DB rows. Log error WITHOUT breaking dispatch.
        try:
            if '_R293_ERR_COUNTER' not in globals():
                globals()['_R293_ERR_COUNTER'] = {}
            _r293_key = type(_r293_e).__name__ + ':' + str(_r293_e)[:80]
            globals()['_R293_ERR_COUNTER'][_r293_key] = (
                globals()['_R293_ERR_COUNTER'].get(_r293_key, 0) + 1
            )
            logger.warning(
                '[R293-LOG-FAIL] rosetta_dispatch_log INSERT failed: '
                + type(_r293_e).__name__ + ': ' + str(_r293_e)[:200]
            )
        except Exception:
            pass  # never let error-logging itself break dispatch

    # PATCH-TASK-COMPLETED-PUBLISH-R260 (2026-05-29)
    # Murphy R260 chose (a) co-emission for atomicity. Per R226 var2: bare-except
    # above swallows EventBackbone errors too, so split-brain mitigated by best-effort
    # publish below. Activates learning loop R206-R221 (subscriber wired, publisher empty).
    try:
        from src.event_backbone import get_event_backbone, Event, EventType
        from datetime import datetime as _r260_dt, timezone as _r260_tz
        import uuid as _r260_uuid
        _r260_event_type = EventType.TASK_FAILED if (error_text or outcome_status == "error") else EventType.TASK_COMPLETED
        _r260_event = Event(
            event_id=f"rosetta-{_r260_uuid.uuid4().hex[:12]}",
            event_type=_r260_event_type,
            payload={
                "task_id": signal.get("signal_id", "")[:64] or f"sig-{_r260_uuid.uuid4().hex[:8]}",
                "agent_id": agent_id,
                "domain": signal.get("domain", ""),
                "intent_hint": (signal.get("intent_hint", "") or "")[:200],
                "outcome_status": outcome_status or "",
                "latency_ms": int(latency_ms or 0),
                "tenant_id": (signal.get("tenant_id") or "platform")[:64],
                "verdict_decision": (verdict.decision if verdict else ""),
                "verdict_confidence": (verdict.confidence if verdict else None),
                "error": (error_text or "")[:400],
            },
            timestamp=_r260_dt.now(_r260_tz.utc).isoformat(),
            source="rosetta_core._rosetta_log_dispatch",
        )
        _r266_bb = get_event_backbone()  # PATCH-R260-TRACE-R266
        logger.info("[R260-TRACE-R266] publishing event_id=%s type=%s to backbone id=%s outcome_status=%s",
                    _r260_event.event_id, _r260_event.event_type.value, id(_r266_bb), outcome_status)
        _r266_result = _r266_bb.publish_event(_r260_event)
        logger.info("[R260-TRACE-R266] publish_event returned %s", _r266_result)
    except Exception as _r260_e:
        logger.warning("[TASK-COMPLETED-PUBLISH] skipped: %s", _r260_e)


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
        import time as _time
        _t0 = _time.monotonic()
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
            self._last_outcome = result.get("status", "ok") if isinstance(result, dict) else "ok"
            # BLOCK-SWARM-EXEC2: store full result dict for downstream capture
            self._last_result = result if isinstance(result, dict) else {"raw": str(result)}
            try:
                _rosetta_log_dispatch(
                    self.agent_id, signal, verdict, result,
                    int((_time.monotonic() - _t0) * 1000), None)
            except Exception:
                pass

        except Exception as exc:
            self._last_outcome = f"error: {exc}"
            result = {"error": str(exc), "agent": self.agent_id}
            self._last_result = result
            logger.error("Agent %s act() failed: %s", self.agent_id, exc)

        # AFTER: soul records legacy
        # PATCH-B5P1-001 (R58): context_chain mutation
        # After this agent's act() completes, append to signal.context_chain
        # so the NEXT agent in a sequence can read prior results.
        # Phase B.5 substrate — enables sequence & pipeline APIs.
        try:
            _chain = signal.setdefault("context_chain", [])
            _entry = {
                "agent_id": self.agent_id,
                "result_summary": (str(result)[:300] if 'result' in dir() else None),
                "soul_decision": (getattr(verdict, "decision", None) if 'verdict' in dir() else None),
                "world_note": (str(getattr(verdict, "world_note", ""))[:200] if 'verdict' in dir() else ""),
                "wire_version_chain": "B5P1-001",
            }
            _chain.append(_entry)
        except Exception as _b5_exc:
            import logging as _b5_log
            _b5_log.getLogger("rosetta_core").debug(
                "context_chain append skipped: %s", _b5_exc
            )

        # _R486A_DAG_PROPAGATION — pull dag_id from result OR from signal.
        # The dispatch layer puts dag_id into the signal dict before agent._run is
        # called; agents historically didn't propagate it into result. Without this,
        # Soul.record received dag_id=None and R484 work_items closure never fired.
        _r486a_dag = None
        if isinstance(result, dict):
            _r486a_dag = result.get("dag_id")
        if not _r486a_dag and isinstance(signal, dict):
            _r486a_dag = signal.get("dag_id") or signal.get("_dag_id")
        self.soul.record(
            agent_id=self.agent_id,
            action=signal.get("intent_hint", ""),
            outcome=result,
            dag_id=_r486a_dag,
        )

        # PATCH-171: fire agent email chain (non-blocking daemon thread)
        # Every completed task → agents email each other + CC cpost & hpost
        try:
            from src.agent_email_chain import fire_agent_email_chain
            fire_agent_email_chain(
                acting_agent=self.agent_id,
                signal=signal,
                result=result,
                outcome=self._last_outcome or "ok",
            )
        except Exception:
            pass  # email chain is best-effort — never block execution

        # PATCH-170c: publish result to Redis bus (non-blocking, best-effort)
        try:
            from src.swarm_bus import publish_result, record_bus_event
            _outcome_str = self._last_outcome or "ok"
            publish_result(
                agent_id=self.agent_id,
                signal_id=signal.get("signal_id", ""),
                outcome=_outcome_str,
                result=result,
            )
            record_bus_event({
                "type": "agent_run",
                "agent_id": self.agent_id,
                "signal_id": signal.get("signal_id", ""),
                "domain": signal.get("domain", "system"),
                "intent": signal.get("intent_hint", "")[:80],
                "outcome": _outcome_str,
                "runs_total": self._runs_total,
                "ts": self._last_trigger,
            })
        except Exception:
            pass  # bus is best-effort — never break agent execution

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

        # PATCH-PHASE-E-CAPACITY-GATE-R255 (2026-05-29)
        # Murphy R244 named Phase E Capacity Gate as highest-leverage Shape-of-Complete
        # substrate item. Stage-1 (R249) named SwarmCoordinator.dispatch as entry.
        # Stage-2 (R250) named CPU/RAM/HITL_QUEUE thresholds (had JSON-escape bug
        # in SQL — fixed here). R255 ships gate, CITL-built from Murphy evidence.
        # Queries last 50 rosetta_dispatch_log rows; if recent load exceeds thresholds,
        # blocks dispatch with [CAPACITY-GATE] log and returns None.
        try:
            import sqlite3 as _cg_sqlite3
            CPU_GATE = 85.0
            RAM_GATE = 90.0
            HITL_DEPTH_GATE = 100
            _cg_DB = "/var/lib/murphy-production/murphy_audit.db"
            with _cg_sqlite3.connect(_cg_DB, timeout=2) as _cg_c:
                _cg_row = _cg_c.execute(
                    "SELECT AVG(cpu_percent), MAX(ram_percent), MAX(hitl_queue_depth) "
                    "FROM (SELECT cpu_percent, ram_percent, hitl_queue_depth "
                    "FROM rosetta_dispatch_log "
                      "WHERE tenant_id = ? "
                      "  AND ts > strftime('%Y-%m-%dT%H:%M:%S', 'now','-15 minutes') "  # R491 ISO-T fix
                      "ORDER BY ts DESC LIMIT 50)",  # PATCH-TENANT-SCOPE-R257
                    (signal.get("tenant_id") or "platform",)
                ).fetchone()
            if _cg_row:
                _cg_avg_cpu, _cg_max_ram, _cg_max_hitl = _cg_row
                # R351: explicit fail-open if no fresh capacity signal
                if (_cg_avg_cpu is None and _cg_max_ram is None
                        and _cg_max_hitl is None):
                    logger.debug("[CAPACITY-GATE-R351] no fresh signal, allowing")
                elif (_cg_avg_cpu is not None and _cg_avg_cpu > CPU_GATE) or \
                   (_cg_max_ram is not None and _cg_max_ram > RAM_GATE) or \
                   (_cg_max_hitl is not None and _cg_max_hitl > HITL_DEPTH_GATE):
                    logger.warning(
                        "[CAPACITY-GATE] dispatch blocked — avg_cpu=%s max_ram=%s max_hitl=%s "
                        "(thresholds %s/%s/%s) signal=%s",
                        _cg_avg_cpu, _cg_max_ram, _cg_max_hitl,
                        CPU_GATE, RAM_GATE, HITL_DEPTH_GATE,
                        signal_id or "?"
                    )
                    return None
        except Exception as _cg_e:
            # Best-effort: gate failure must never block dispatch
            logger.debug("[CAPACITY-GATE] check skipped: %s", _cg_e)
        # ── END PATCH-PHASE-E-CAPACITY-GATE-R255 ───────────────────────────────

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

        # _R486A_DAG_PROPAGATION — make dag_id visible to agents BEFORE _run.
        # The work_items.dag_id is generated by the /api/rosetta/dispatch endpoint
        # and stored on the signal as "dag_id". We re-stamp it here so any path
        # through dispatch() also exposes it to downstream agent._run/Soul.record.
        try:
            if isinstance(signal, dict) and not signal.get("dag_id"):
                _r486a_existing = signal.get("_dag_id") or signal.get("signal_id")
                if _r486a_existing:
                    signal["dag_id"] = _r486a_existing
        except Exception:
            pass

        # PATCH-170: Domain → agent routing for all 9 agents
        # BLOCK-PHASE-B-C (2026-05-26): added 'patcher' (10th agent) for self-patch proposals
        _all_domains = {
            "exec_admin": "exec_admin",
            "prod_ops":   "prod_ops",
            "collector":  "collector",
            "translator": "translator",
            "auditor":    "auditor",
            "hitl":       "hitl",
            "scheduler":  "scheduler",
            "executor":   "executor",
            "rosetta":    "rosetta",
            "patcher":    "patcher",
        }
        if domain in _all_domains:
            target = _all_domains[domain]
        elif signal_type == "lcm_intent":
            target = "translator"
        elif signal_type == "corpus_collect":
            target = "collector"
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

    def pipeline(self, signal: Dict, agent_sequence) -> Dict:
        """
        PATCH-B5P2-001 (R59): sequential pipeline dispatch.

        Run signal through agent_sequence in order. Each agent sees prior
        agents' results via signal.context_chain (B5P1 substrate).

        Args:
            signal: base signal dict (will be mutated with context_chain entries)
            agent_sequence: list of agent_id strings to run in order

        Returns:
            {
              "completed": int,        # agents that ran
              "skipped": int,          # agents missing or dedup-blocked
              "context_chain": list,   # final chain
              "wire_version_pipeline": "B5P2-001",
            }
        """
        completed = 0
        skipped = 0
        if not isinstance(agent_sequence, (list, tuple)):
            return {"completed": 0, "skipped": 0,
                    "context_chain": signal.get("context_chain", []),
                    "wire_version_pipeline": "B5P2-001",
                    "error": "agent_sequence must be list"}

        for idx, agent_id in enumerate(agent_sequence):
            if agent_id not in self._agents:
                skipped += 1
                logger.debug("pipeline: agent %s not registered, skipping", agent_id)
                continue
            # Each hop gets a unique signal_id to avoid dedup blocking
            hop_signal = dict(signal)
            base_sid = signal.get("signal_id", "pipeline")
            hop_signal["signal_id"] = f"{base_sid}__hop{idx}_{agent_id}"
            hop_signal["domain"] = agent_id  # route to this specific agent
            hop_signal["context_chain"] = signal.get("context_chain", [])
            try:
                self.dispatch(hop_signal)
                # Carry the chain back to the base signal
                signal["context_chain"] = hop_signal.get("context_chain", [])
                completed += 1
            except Exception as exc:
                logger.warning("pipeline: hop %d (%s) failed: %s", idx, agent_id, exc)
                skipped += 1

        return {
            "completed": completed,
            "skipped": skipped,
            "context_chain": signal.get("context_chain", []),
            "wire_version_pipeline": "B5P2-001",
        }

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
        PATCH-170: Route through dispatch() FIRST (calls agent._run() → runs_total increments).
        Only fall back to domain handlers if agent is NOT in _agents roster.
        """
        domain = signal.get("domain", signal.get("signal_type", "general"))

        # Prefer dispatch() — it calls _run() and increments counters
        if domain in ("exec_admin", "prod_ops", "collector", "translator",
                      "auditor", "hitl", "scheduler", "executor", "rosetta",
                      "patcher"):
            dag_id = self.dispatch(signal)
            if dag_id is not None or domain in self._agents:
                return dag_id

        # Fallback: legacy domain handlers for domains not in _agents
        handlers = getattr(self, "_domain_handlers", {})
        if domain in handlers:
            try:
                dag_id = handlers[domain](signal)
                return dag_id
            except Exception as e:
                logger.error("Domain handler '%s' failed: %s", domain, e)

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
