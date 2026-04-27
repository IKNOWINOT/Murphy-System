"""
PATCH-116 + PATCH-115b — src/exec_admin_agent.py
Murphy System — Executive Admin Agent (inherits AgentBase / RosettaSoul)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object  # graceful fallback

logger = logging.getLogger("murphy.exec_admin")


class ExecAdminAgent(AgentBase):
    """
    PATCH-116: Executive Admin automation agent.
    Carries RosettaSoul via AgentBase inheritance.
    """

    TASK_TEMPLATES = {
        "morning_brief": {"domain": "exec_admin", "urgency": "scheduled", "stake": "low"},
        "email_triage":  {"domain": "exec_admin", "urgency": "scheduled", "stake": "medium"},
        "schedule_meeting": {"domain": "exec_admin", "urgency": "scheduled", "stake": "low"},
        "weekly_report": {"domain": "exec_admin", "urgency": "scheduled", "stake": "low"},
        "approve_request": {"domain": "exec_admin", "urgency": "immediate", "stake": "medium"},
    }

    def __init__(self, llm_provider=None, signal_collector=None):
        super().__init__("exec_admin")
        self._llm = llm_provider
        self._collector = signal_collector

    def act(self, signal: dict) -> dict:
        """AgentBase interface — route signal to the right exec_admin task."""
        intent = signal.get("intent_hint", "").lower()
        world_note = signal.get("_world_note", "")
        if "email" in intent:
            return self.triage_email(signal.get("raw_payload", {}))
        elif "meeting" in intent or "schedule" in intent:
            return self.schedule_meeting(
                participants=signal.get("entities", []),
                topic=intent[:60],
                account=signal.get("source", "unknown"),
            )
        else:
            result = self.run_morning_brief(account=signal.get("source", "cpost@murphy.systems"))
            if world_note:
                result["world_context"] = world_note
            return result

    def run_morning_brief(self, account: str = "cpost@murphy.systems") -> Dict:
        """Generate and (eventually) deliver a morning brief."""
        from src.signal_collector import get_collector
        from src.workflow_dag import build_dag, task_node, get_executor

        collector = get_collector()
        recent = collector.latest(limit=20)
        stats = collector.stats()

        brief_parts = [
            f"🌅 MURPHY MORNING BRIEF — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"",
            f"📊 Signal Summary:",
            f"  Total signals (all time): {stats['total']}",
            f"  Unprocessed: {stats['unprocessed']}",
            f"  By type: {stats['by_type']}",
            f"",
            f"🔄 Recent Signals (last 5):",
        ]
        for sig in recent[:5]:
            brief_parts.append(f"  [{sig['signal_type']}] {sig['intent_hint'][:80]}")

        if self._llm:
            try:
                summary_prompt = (
                    f"You are Murphy's executive assistant. Summarize this signal data "
                    f"into a 3-sentence morning brief for the executive: {stats}"
                )
                resp = self._llm.complete(prompt=summary_prompt, max_tokens=150)
                brief_parts.append(f"\n🤖 Murphy's Assessment:\n  {resp.content.strip()}")
            except Exception as exc:
                logger.warning("LLM brief summary failed: %s", exc)

        brief = "\n".join(brief_parts)

        dag = build_dag("morning_brief", "Daily executive morning brief",
                        domain="exec_admin", stake="low", account=account)
        dag.add_node(task_node("collect_signals", "aggregate_signal_data"))
        dag.add_node(task_node("compile_brief", "format_morning_brief",
                               depends_on=["collect_signals"]))
        dag.add_node(task_node("deliver_brief", "send_to_executive",
                               depends_on=["compile_brief"]))
        result = get_executor().execute(dag)

        return {
            "brief": brief,
            "dag_id": dag.dag_id,
            "dag_status": result.status,
            "signal_count": len(recent),
        }

    def triage_email(self, email_data: Dict) -> Dict:
        """Classify an incoming email and decide action."""
        subject = email_data.get("subject", "")
        body = email_data.get("body", "")
        sender = email_data.get("from", "")

        # Record as signal
        from src.signal_collector import get_collector
        get_collector().ingest(
            signal_type="email",
            source=f"email:{sender}",
            payload=email_data,
            domain="exec_admin",
            urgency="scheduled",
            stake="low",
            intent_hint=f"Email from {sender}: {subject[:60]}",
            entities=[sender],
        )

        # Classify
        urgency_words = ["urgent", "asap", "critical", "emergency", "immediate"]
        is_urgent = any(w in (subject + body).lower() for w in urgency_words)

        classification = {
            "sender": sender,
            "subject": subject,
            "intent_class": "urgent_action" if is_urgent else "routine",
            "stake": "high" if is_urgent else "low",
            "recommended_action": "flag_for_human" if is_urgent else "draft_reply",
            "auto_reply": not is_urgent,
        }
        return classification

    def schedule_meeting(self, participants: list, topic: str,
                         duration_mins: int = 60, account: str = "unknown") -> Dict:
        """Build a meeting scheduling workflow."""
        from src.workflow_dag import build_dag, task_node, get_executor

        dag = build_dag(f"schedule_meeting_{topic[:30]}", topic,
                        domain="exec_admin", stake="low", account=account)
        dag.add_node(task_node("find_gaps", "calendar_gap_finder",
                               args={"participants": participants, "duration": duration_mins}))
        dag.add_node(task_node("propose_slots", "generate_time_proposals",
                               depends_on=["find_gaps"]))
        dag.add_node(task_node("send_invite", "calendar_invite_sender",
                               args={"topic": topic, "participants": participants},
                               depends_on=["propose_slots"]))
        result = get_executor().execute(dag)
        return {"dag_id": dag.dag_id, "status": result.status, "topic": topic}


# ── Singleton ──────────────────────────────────────────────────────────────────
_exec_admin: Optional[ExecAdminAgent] = None

def get_exec_admin() -> ExecAdminAgent:
    global _exec_admin
    if _exec_admin is None:
        try:
            from src.llm_provider import MurphyLLMProvider
            from src.signal_collector import get_collector
            _exec_admin = ExecAdminAgent(
                llm_provider=MurphyLLMProvider(),
                signal_collector=get_collector()
            )
        except Exception:
            _exec_admin = ExecAdminAgent()
    return _exec_admin
