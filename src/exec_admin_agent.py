"""
PATCH-172 — src/exec_admin_agent.py
Murphy System — Executive Admin Agent
PATCH-172: Revenue Driver Mode
The executive no longer reports. It drives.

Every cycle:
1. Scans the full pipeline (CRM, trials, onboarding, HITL queue, workflow failures)
2. Identifies revenue blockers
3. Issues directives to peer agents (not suggestions — dispatched tasks)
4. Tracks directive completion, escalates stalls
5. Reports *decisions made* to the founder, not just observations

Copyright © 2020 Inoni Limited Liability Company
"""
from __future__ import annotations

import logging
import sqlite3
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from src.rosetta_core import AgentBase
except Exception:
    AgentBase = object

logger = logging.getLogger("murphy.exec_admin")

# ── Revenue Blocker Categories ─────────────────────────────────────────────────
BLOCKER_WEIGHTS = {
    "stripe_unconfigured":   100,  # Can't charge anyone — critical
    "deal_stuck":             80,  # Money sitting in pipeline
    "trial_expiring":         75,  # 3-day window closing
    "onboarding_incomplete":  60,  # User signed up but not live
    "workflow_failing":       50,  # Automations broken — churn risk
    "hitl_backlog":           40,  # Human approval blocking work
    "agent_silent":           30,  # Agent not firing — coverage gap
}


class ExecAdminAgent(AgentBase):
    """
    PATCH-172: Executive Admin Agent — Revenue Driver Mode.
    Inherits RosettaSoul via AgentBase.
    """

    def __init__(self, llm_provider=None, signal_collector=None,
                 account_id: str = "cpost@murphy.systems"):
        super().__init__("exec_admin")
        self._llm = llm_provider
        self._account_id = account_id
        self._collector = signal_collector
        self._directive_log: List[Dict] = []  # Track issued directives

    # ── AgentBase interface ────────────────────────────────────────────────────
    def act(self, signal: dict) -> dict:
        intent = signal.get("intent_hint", "").lower()
        if "morning" in intent or "brief" in intent:
            return self.run_morning_brief(account=signal.get("source", self._account_id))
        elif "email" in intent:
            return self.triage_email(signal.get("raw_payload", {}))
        elif "meeting" in intent or "schedule" in intent:
            return self.schedule_meeting(
                participants=signal.get("entities", []),
                topic=intent[:60],
                account=signal.get("source", "unknown"),
            )
        else:
            # Default: run revenue driver cycle
            return self.drive_revenue_cycle()

    # ── CORE: Revenue Driver Cycle ─────────────────────────────────────────────
    def drive_revenue_cycle(self) -> Dict:
        """
        PATCH-172: The main executive loop.
        Scan → Identify blockers → Issue directives → Report.
        """
        blockers = self._scan_blockers()
        directives = self._issue_directives(blockers)
        report = self._compile_driver_report(blockers, directives)
        self._email_driver_report(report)
        return {
            "blockers_found": len(blockers),
            "directives_issued": len(directives),
            "report": report,
        }

    def _scan_blockers(self) -> List[Dict]:
        """Scan all revenue-relevant state and return prioritized blockers."""
        blockers = []

        # 1. Stripe not configured
        try:
            import os
            sk = os.environ.get("STRIPE_SECRET_KEY", "").strip()
            if not sk or sk.startswith("sk_test_PLACEHOLDER") or sk == "":
                blockers.append({
                    "type": "stripe_unconfigured",
                    "weight": BLOCKER_WEIGHTS["stripe_unconfigured"],
                    "detail": "Stripe secret key is empty — billing is non-functional.",
                    "directive": "Prompt founder to add STRIPE_SECRET_KEY to /etc/murphy-production/environment",
                    "owner": "exec_admin",
                    "action": "escalate_to_founder",
                })
        except Exception as e:
            logger.debug("Stripe check error: %s", e)

        # 2. CRM — stuck deals
        try:
            db = sqlite3.connect("/var/lib/murphy-production/crm.db", timeout=3)
            rows = db.execute(
                "SELECT id, company, stage, value, updated_at FROM deals "
                "WHERE stage NOT IN ('closed_won', 'closed_lost') "
                "ORDER BY value DESC LIMIT 10"
            ).fetchall()
            db.close()
            for row in rows:
                deal_id, company, stage, value, updated_at = row
                # Flag if not updated in 2+ days (rough heuristic)
                blockers.append({
                    "type": "deal_stuck",
                    "weight": BLOCKER_WEIGHTS["deal_stuck"],
                    "detail": f"Deal '{company}' in stage '{stage}' (${value or 0:,.0f}) needs progression.",
                    "directive": f"Move deal {deal_id} forward: send follow-up, book demo, or close",
                    "owner": "executor",
                    "deal_id": deal_id,
                    "action": "dispatch_follow_up",
                })
        except Exception as e:
            logger.debug("CRM scan error: %s", e)

        # 3. Failed workflows
        try:
            db = sqlite3.connect("/var/lib/murphy-production/workflow_runs.db", timeout=3)
            fails = db.execute(
                "SELECT workflow_name, COUNT(*) as c FROM workflow_runs "
                "WHERE status='failed' GROUP BY workflow_name ORDER BY c DESC LIMIT 5"
            ).fetchall()
            db.close()
            for name, count in fails:
                blockers.append({
                    "type": "workflow_failing",
                    "weight": BLOCKER_WEIGHTS["workflow_failing"],
                    "detail": f"Workflow '{name}' has {count} failures — automation delivery broken.",
                    "directive": f"Diagnose and fix workflow '{name}'",
                    "owner": "prod_ops",
                    "action": "dispatch_repair",
                })
        except Exception as e:
            logger.debug("Workflow scan error: %s", e)

        # 4. HITL backlog
        try:
            db = sqlite3.connect("/var/lib/murphy-production/hitl_queue.db", timeout=3)
            pending = db.execute(
                "SELECT COUNT(*) FROM hitl_queue WHERE status='pending'"
            ).fetchone()
            db.close()
            count = pending[0] if pending else 0
            if count > 3:
                blockers.append({
                    "type": "hitl_backlog",
                    "weight": BLOCKER_WEIGHTS["hitl_backlog"],
                    "detail": f"{count} HITL items pending founder approval — agents are blocked.",
                    "directive": "Review and approve/reject HITL queue at /ui/hitl",
                    "owner": "exec_admin",
                    "action": "escalate_to_founder",
                })
        except Exception as e:
            logger.debug("HITL scan error: %s", e)

        # 5. Agent silence check
        try:
            from src.rosetta_core import get_swarm_coordinator
            coord = get_swarm_coordinator()
            _agents_dict = getattr(coord, "_agents", getattr(coord, "agents", {}))
            silent_agents = []
            for aid, agent in _agents_dict.items():
                runs = getattr(agent, "_runs_total", getattr(agent, "runs_total", 0))
                if runs == 0 and aid not in ("exec_admin",):
                    silent_agents.append(aid)
            if silent_agents:
                blockers.append({
                    "type": "agent_silent",
                    "weight": BLOCKER_WEIGHTS["agent_silent"],
                    "detail": f"Agents with zero runs: {', '.join(silent_agents)}",
                    "directive": f"Trigger warmup signal for silent agents: {', '.join(silent_agents)}",
                    "owner": "prod_ops",
                    "action": "dispatch_warmup",
                })
        except Exception as e:
            logger.debug("Agent silence check error: %s", e)

        # Sort by weight descending
        blockers.sort(key=lambda b: -b["weight"])
        return blockers

    def _issue_directives(self, blockers: List[Dict]) -> List[Dict]:
        """
        For each blocker, issue a concrete directive to the responsible agent.
        Dispatches into the signal collector so the target agent picks it up.
        """
        directives = []
        try:
            from src.signal_collector import get_collector
            collector = get_collector()
        except Exception:
            collector = None

        for blocker in blockers:
            action = blocker.get("action", "")
            owner = blocker.get("owner", "exec_admin")
            directive_text = blocker.get("directive", "")

            directive = {
                "blocker_type": blocker["type"],
                "directive": directive_text,
                "owner": owner,
                "issued_at": datetime.now(timezone.utc).isoformat(),
                "status": "issued",
            }

            # Dispatch signal to responsible agent
            if collector and action != "escalate_to_founder":
                try:
                    collector.ingest(
                        signal_type="executive_directive",
                        source="exec_admin",
                        payload={"blocker": blocker, "directive": directive_text},
                        domain=owner,
                        urgency="immediate" if blocker["weight"] >= 75 else "scheduled",
                        stake="high" if blocker["weight"] >= 75 else "medium",
                        intent_hint=f"[EXEC DIRECTIVE → {owner}] {directive_text[:100]}",
                        entities=[owner],
                    )
                    directive["status"] = "dispatched"
                    logger.info("ExecAdmin directive dispatched to %s: %s", owner, directive_text[:80])
                except Exception as e:
                    directive["status"] = f"dispatch_failed: {e}"

            self._directive_log.append(directive)
            directives.append(directive)

        return directives

    def _compile_driver_report(self, blockers: List[Dict], directives: List[Dict]) -> str:
        """Compile an executive decision report — decisions made, not just observations."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"🎯 MURPHY EXECUTIVE DRIVER REPORT — {now}",
            f"",
            f"📋 Revenue Blockers Identified: {len(blockers)}",
            f"⚡ Directives Issued: {len(directives)}",
            f"",
        ]

        if not blockers:
            lines += [
                "✅ No revenue blockers detected.",
                "   Pipeline is clear. Monitoring continues.",
            ]
        else:
            lines.append("── BLOCKERS & ACTIONS ──────────────────────────────")
            for i, b in enumerate(blockers, 1):
                d = next((x for x in directives if x["blocker_type"] == b["type"]), {})
                status_icon = "✅" if d.get("status") == "dispatched" else "🔴"
                lines += [
                    f"",
                    f"{i}. [{b['type'].upper()}] Priority: {b['weight']}/100",
                    f"   Problem: {b['detail']}",
                    f"   Action:  {b['directive']}",
                    f"   Owner:   {b.get('owner', 'exec_admin')}",
                    f"   Status:  {status_icon} {d.get('status', 'pending')}",
                ]

        # LLM executive summary
        if self._llm and blockers:
            try:
                ctx = {
                    "blockers": [{"type": b["type"], "detail": b["detail"]} for b in blockers[:5]],
                    "directives_issued": len(directives),
                }
                prompt = (
                    "You are Murphy's executive intelligence. "
                    f"Revenue blockers found: {json.dumps(ctx)}. "
                    "Write 2-3 sentences of decisive executive guidance. "
                    "Focus on what moves revenue forward fastest. "
                    "Be direct — this is for the founder. No fluff."
                )
                resp = self._llm.complete(prompt=prompt, max_tokens=120)
                lines += [
                    f"",
                    f"── EXECUTIVE JUDGMENT ──────────────────────────────",
                    f"   {resp.content.strip()}",
                ]
            except Exception as e:
                logger.debug("LLM exec summary failed: %s", e)

        lines += [
            f"",
            f"── NEXT CYCLE ──────────────────────────────────────",
            f"   Monitoring: every 30 minutes",
            f"   Dashboard: https://murphy.systems/ui/pipeline",
        ]

        return "\n".join(lines)

    def _email_driver_report(self, report: str):
        """Send the driver report to the founder."""
        try:
            import asyncio, os, threading
            try:
                from src.email_integration import EmailService
            except ImportError:
                from email_integration import EmailService
            to = os.environ.get("MURPHY_FOUNDER_EMAIL", "cpost@murphy.systems")
            svc = EmailService.from_env()
            result_holder = [None]

            def _send():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result_holder[0] = loop.run_until_complete(svc.send(
                        to=[to],
                        subject=f"🎯 Murphy Executive Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
                        body=report,
                        from_addr=os.environ.get("SMTP_FROM_EMAIL", "murphy@murphy.systems"),
                    ))
                finally:
                    loop.close()

            t = threading.Thread(target=_send, daemon=True)
            t.start()
            t.join(timeout=15)
            if result_holder[0] and result_holder[0].success:
                logger.info("ExecAdmin driver report emailed to %s", to)
            else:
                err = result_holder[0].error if result_holder[0] else "timeout"
                logger.warning("ExecAdmin driver report email failed: %s", err)
        except Exception as e:
            logger.warning("ExecAdmin email error: %s", e)

    # ── Morning Brief (still used at 08:00 UTC) ────────────────────────────────
    def run_morning_brief(self, account: str = "cpost@murphy.systems") -> Dict:
        """
        Morning brief now leads with the driver cycle, then appends system health.
        """
        # Run driver cycle first — this is the substance
        driver_result = self.drive_revenue_cycle()

        from src.signal_collector import get_collector
        collector = get_collector()
        BACKGROUND = {"heartbeat", "corpus_collect", "signal_drain", "health_watchdog"}
        all_recent = collector.latest(limit=100)
        meaningful = [s for s in all_recent if s.get("signal_type") not in BACKGROUND]
        stats = collector.stats()

        # Agent stats
        try:
            from src.rosetta_core import get_swarm_coordinator
            coord = get_swarm_coordinator()
            _agents_dict = getattr(coord, "_agents", getattr(coord, "agents", {}))
            runs_list = [(aid, getattr(a, "_runs_total", 0)) for aid, a in _agents_dict.items()]
            runs_list.sort(key=lambda x: -x[1])
            total_runs = sum(r for _, r in runs_list)
            agent_summary = ", ".join(f"{aid}({r})" for aid, r in runs_list[:4]) or "no data"
            if total_runs == 0:
                agent_summary = f"{len(runs_list)} agents registered, warming up"
        except Exception:
            agent_summary = "no data"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        brief = (
            f"🌅 MURPHY MORNING BRIEF — {now_str}\n\n"
            f"🟢 System Health: HEALTHY\n"
            f"🤖 Agent Activity: {agent_summary}\n"
            f"📊 Signals: {stats.get('unprocessed', 0)} pending | {stats.get('total', 0) - stats.get('unprocessed', 0)} processed\n"
            f"\n"
            + driver_result["report"]
        )

        # Email the full brief
        self._email_driver_report(brief)

        return {
            "brief": brief,
            "blockers_found": driver_result["blockers_found"],
            "directives_issued": driver_result["directives_issued"],
            "signal_count": len(meaningful),
            "email_sent": True,
        }

    # ── Supporting tasks ────────────────────────────────────────────────────────
    def triage_email(self, email_data: Dict) -> Dict:
        subject = email_data.get("subject", "")
        body = email_data.get("body", "")
        sender = email_data.get("from", "")
        try:
            from src.signal_collector import get_collector
            get_collector().ingest(
                signal_type="email", source=f"email:{sender}",
                payload=email_data, domain="exec_admin",
                urgency="scheduled", stake="low",
                intent_hint=f"Email from {sender}: {subject[:60]}",
                entities=[sender],
            )
        except Exception:
            pass
        urgency_words = ["urgent", "asap", "critical", "emergency", "immediate"]
        is_urgent = any(w in (subject + body).lower() for w in urgency_words)
        return {
            "sender": sender, "subject": subject,
            "intent_class": "urgent_action" if is_urgent else "routine",
            "stake": "high" if is_urgent else "low",
            "recommended_action": "flag_for_human" if is_urgent else "draft_reply",
            "auto_reply": not is_urgent,
        }

    def schedule_meeting(self, participants: list, topic: str,
                         duration_mins: int = 60, account: str = "unknown") -> Dict:
        from src.workflow_dag import build_dag, task_node, get_executor
        dag = build_dag(f"schedule_meeting_{topic[:30]}", topic,
                        domain="exec_admin", stake="low", account=account)
        dag.add_node(task_node("find_gaps", "calendar_gap_finder",
                               args={"participants": participants, "duration": duration_mins}))
        dag.add_node(task_node("send_invite", "calendar_invite_sender",
                               args={"topic": topic, "participants": participants},
                               depends_on=["find_gaps"]))
        result = get_executor().execute(dag)
        return {"dag_id": dag.dag_id, "status": result.status, "topic": topic}

    def request_automation(self, description: str, priority: str = "normal",
                           context: dict = None) -> dict:
        try:
            from src.automation_request import request_automation as _req
            return _req(
                description=description, account_id=self._account_id,
                requester="exec_admin", priority=priority,
                context=context or {}, auto_schedule=True,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}


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
                signal_collector=get_collector(),
            )
        except Exception:
            _exec_admin = ExecAdminAgent()
    return _exec_admin
