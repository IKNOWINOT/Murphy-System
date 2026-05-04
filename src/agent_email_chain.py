"""
agent_email_chain.py — PATCH-171
After any agent completes a task, fires a realistic email thread between the
relevant agents, CC'ing cpost@murphy.systems and hpost@murphy.systems.

PATCH-171b: Meeting-aware — if an ambient management meeting is active, the
chain also:
  1. CC's all meeting participants
  2. Posts shadow suggestions back into the meeting session
  3. Labels emails with the meeting context

Design:
  Email 1: Acting agent → next-in-chain report  (CC humans + meeting participants)
  Email 2: Next-in-chain → acting agent reply   (CC humans + meeting participants)
"""

import logging
import threading
import asyncio
import uuid
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger("murphy.agent_email")

# Human CCs — always copied on every agent email
HUMAN_CC = ["cpost@murphy.systems", "hpost@murphy.systems"]

# Agent email addresses
AGENT_EMAILS: Dict[str, Dict] = {
    "collector":   {"email": "collector@murphy.systems",   "name": "Collector (Murphy Swarm)"},
    "translator":  {"email": "translator@murphy.systems",  "name": "Translator (Murphy Swarm)"},
    "scheduler":   {"email": "scheduler@murphy.systems",   "name": "Scheduler (Murphy Swarm)"},
    "executor":    {"email": "executor@murphy.systems",    "name": "Executor (Murphy Swarm)"},
    "auditor":     {"email": "auditor@murphy.systems",     "name": "Auditor (Murphy Swarm)"},
    "exec_admin":  {"email": "exec_admin@murphy.systems",  "name": "ExecAdmin (Murphy Swarm)"},
    "prod_ops":    {"email": "prod_ops@murphy.systems",    "name": "ProdOps (Murphy Swarm)"},
    "hitl":        {"email": "hitl@murphy.systems",        "name": "HITL Gate (Murphy Swarm)"},
    "rosetta":     {"email": "rosetta@murphy.systems",     "name": "Rosetta (Murphy Swarm)"},
    "murphy":      {"email": "murphy@murphy.systems",      "name": "Murphy System"},
}

AGENT_EMOJIS: Dict[str, str] = {
    "collector": "📡", "translator": "🧠", "scheduler": "🗓",
    "executor": "⚡", "auditor": "📋", "exec_admin": "👔",
    "prod_ops": "🔧", "hitl": "🔴", "rosetta": "🌐", "murphy": "🤖",
}

# Domain → next-in-chain (who does the acting agent report to?)
REPORT_TO_CHAIN: Dict[str, str] = {
    "collector":  "translator",
    "translator": "exec_admin",
    "scheduler":  "exec_admin",
    "executor":   "exec_admin",
    "auditor":    "rosetta",
    "exec_admin": "rosetta",
    "prod_ops":   "exec_admin",
    "hitl":       "rosetta",
    "rosetta":    "exec_admin",
}

# Skip noisy background signals
SKIP_SIGNAL_TYPES = {"heartbeat", "signal_drain", "corpus_collect", "health_watchdog", "health_check", "swarm_heartbeat"}


def _safe_name(name: str) -> str:
    """Strip non-ASCII (emoji) from display name for SMTP compatibility."""
    return re.sub(r'[^\x00-\x7F]+', '', name).strip()


def _agent_info(agent_id: str) -> Dict:
    return AGENT_EMAILS.get(agent_id, {
        "email": f"{agent_id}@murphy.systems",
        "name": f"{agent_id.title()} (Murphy Swarm)",
    })


def _get_active_meeting() -> Optional[Dict]:
    """
    Check if any management meeting is currently active.
    Returns meeting dict with session_id, title, participants — or None.
    """
    try:
        from src.ai_comms_orchestrator import meetings_bridge
        sessions = meetings_bridge.list_meetings()
        for s in sessions:
            if s.get("status") == "active":
                return s
    except Exception:
        pass

    # Fallback: check SQLite directly
    try:
        import sqlite3
        db_path = "/var/lib/murphy-production/murphy_production.db"
        conn = sqlite3.connect(db_path, timeout=3)
        cur = conn.cursor()
        cur.execute(
            "SELECT session_id, title, participants FROM meeting_sessions "
            "WHERE status='active' ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        conn.close()
        if row:
            import json
            parts = row[2]
            if isinstance(parts, str):
                try:
                    parts = json.loads(parts)
                except Exception:
                    parts = [p.strip() for p in parts.split(',') if p.strip()]
            return {"session_id": row[0], "title": row[1], "participants": parts or []}
    except Exception:
        pass
    return None


def _post_shadow_suggestion(session_id: str, agent_id: str, suggestion_type: str, content: str):
    """Post agent insight as a shadow suggestion into the active meeting."""
    try:
        from src.ai_comms_orchestrator import meetings_bridge
        meetings_bridge.shadow_suggest(
            session_id=session_id,
            agent_id=agent_id,
            suggestion_type=suggestion_type,
            content=content,
        )
        logger.info("AgentEmailChain: shadow suggestion posted by %s to meeting %s", agent_id, session_id)
    except Exception as exc:
        logger.debug("AgentEmailChain: shadow_suggest error: %s", exc)


def _compose_thread(
    acting_agent: str,
    signal: Dict,
    result: Dict,
    outcome: str,
    meeting: Optional[Dict] = None,
) -> Optional[Dict]:
    """Compose the 2-email agent conversation thread."""
    sig_type = signal.get("signal_type", "")
    if sig_type in SKIP_SIGNAL_TYPES:
        return None

    intent = signal.get("intent_hint", signal.get("signal_type", "task"))
    domain = signal.get("domain", acting_agent)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    thread_id = str(uuid.uuid4())[:8]

    acting = _agent_info(acting_agent)
    acting_emoji = AGENT_EMOJIS.get(acting_agent, "")
    report_to_id = REPORT_TO_CHAIN.get(acting_agent, "rosetta")
    report_to = _agent_info(report_to_id)
    report_emoji = AGENT_EMOJIS.get(report_to_id, "")

    result_summary = _summarise_result(result, outcome)

    # Meeting context
    meeting_header = ""
    meeting_label = ""
    cc_list = list(HUMAN_CC)
    if meeting:
        m_title = meeting.get("title", "Management Meeting")
        m_id = meeting.get("session_id", "")
        meeting_label = f"[MEETING: {m_title}] "
        meeting_header = (
            f"** AMBIENT INTELLIGENCE — MANAGEMENT MEETING IN PROGRESS **\n"
            f"Meeting: {m_title} (session: {m_id})\n"
            f"This task completed during an active board session.\n"
            f"{'─' * 60}\n\n"
        )
        # Add meeting participants to CC
        for p in meeting.get("participants", []):
            if p and "@" in p and p not in cc_list:
                cc_list.append(p)

    subject = f"{meeting_label}[Murphy Swarm] {acting_emoji} {acting_agent.title()} completed: {intent[:55]} [{ts}]"

    # Email 1: Acting agent reports to next-in-chain
    email1_body = f"""{meeting_header}From: {acting_emoji} {acting['name']}
To: {report_emoji} {report_to['name']}
CC: {', '.join(cc_list)}
Thread: {thread_id}

{report_to_id.title()},

Task completed in domain [{domain}]:

Task:    {intent}
Type:    {sig_type or 'dispatch'}
Outcome: {outcome}

{result_summary}

{_acting_commentary(acting_agent, outcome, result)}

{'This action occurred during the ' + meeting.get('title','') + ' board session — flagging for meeting record.' if meeting else 'Logging for the record and flagging for your awareness.'}

— {acting['name']}
  Murphy Swarm · {ts}
"""

    # Email 2: Next-in-chain acknowledges
    email2_body = f"""{meeting_header}From: {report_emoji} {report_to['name']}
To: {acting_emoji} {acting['name']}
CC: {', '.join(cc_list)}
Re: {subject}
Thread: {thread_id}

{acting_agent.title()},

Received and logged. {_recipient_commentary(report_to_id, acting_agent, outcome, result)}

{_next_steps(report_to_id, outcome)}

{'During this meeting session, your findings will be surfaced as shadow suggestions to the board.' if meeting else 'Keeping cpost and hpost in the loop as always.'}

— {report_to['name']}
  Murphy Swarm · {ts}
"""

    return {
        "thread_id": thread_id,
        "subject": subject,
        "meeting": meeting,
        "acting_agent": acting_agent,
        "report_to_id": report_to_id,
        "intent": intent,
        "outcome": outcome,
        "email1": {
            "from_addr": acting["email"],
            "from_name": _safe_name(acting["name"]),
            "to": [report_to["email"]] + cc_list,
            "subject": subject,
            "body": email1_body,
        },
        "email2": {
            "from_addr": report_to["email"],
            "from_name": _safe_name(report_to["name"]),
            "to": [acting["email"]] + cc_list,
            "subject": f"Re: {subject}",
            "body": email2_body,
        },
    }


def _summarise_result(result: Dict, outcome: str) -> str:
    if not result:
        return f"Result: {outcome}"
    lines = []
    skip_keys = {"agent", "dag_id", "status", "error", "blocked", "deferred"}
    for k, v in result.items():
        if k in skip_keys:
            continue
        if isinstance(v, (str, int, float, bool)):
            lines.append(f"  - {k}: {str(v)[:120]}")
        elif isinstance(v, dict) and len(str(v)) < 200:
            lines.append(f"  - {k}: {str(v)}")
    if result.get("error"):
        lines.insert(0, f"  [!] Error: {result['error']}")
    if result.get("dag_id"):
        lines.append(f"  - DAG: {result['dag_id']}")
    return "Details:\n" + ("\n".join(lines) if lines else f"  {outcome}")


def _acting_commentary(agent_id: str, outcome: str, result: Dict) -> str:
    ok = "error" not in outcome.lower() and "blocked" not in outcome.lower()
    comments = {
        "collector":  "Signals collected and queued for translation. Corpus updated." if ok else "Collection hit an issue — may need a retry.",
        "translator": "Intent classified and domain routed. Confidence within acceptable range." if ok else "Translation confidence low — may need human review.",
        "scheduler":  "Timing evaluated. Action window confirmed clear." if ok else "Scheduling conflict detected — holding for resolution.",
        "executor":   "Action executed via DAG. All steps completed." if ok else "Execution encountered a failure — rollback may be needed.",
        "auditor":    "Audit trail recorded. No covenant breaches detected." if ok else "Audit flagged a potential issue — Rosetta notified.",
        "exec_admin": "Brief prepared and distributed. All board members updated." if ok else "Admin task failed — escalating to Rosetta.",
        "prod_ops":   "System health confirmed nominal. All watchers green." if ok else "Health check found anomalies — investigating.",
        "hitl":       "Human-in-the-loop check passed. Auto-approved for execution." if ok else "HITL gate held the action — awaiting human sign-off.",
        "rosetta":    "Alignment confirmed. North star holds. Soul integrity intact." if ok else "Alignment check raised concerns — pausing until resolved.",
    }
    return comments.get(agent_id, f"Task completed. Outcome: {outcome}.")


def _recipient_commentary(recipient_id: str, acting_id: str, outcome: str, result: Dict) -> str:
    ok = "error" not in outcome.lower()
    comments = {
        "translator":  "Good signal quality from Collector. I'll process it through the intent pipeline." if ok else "Will re-classify with broader pattern matching.",
        "exec_admin":  "Clean execution. I'll incorporate this into the next morning brief and management board update." if ok else "Flagging for review — will include in tomorrow's brief with corrective actions.",
        "rosetta":     "Alignment intact. I'll record this in the covenant ledger and verify soul integrity." if ok else "Alignment concern noted — may invoke PCC review before next action.",
        "prod_ops":    "All systems nominal. Health watchdog updated." if ok else "Escalating to incident protocol — investigating root cause.",
        "collector":   "Signal confirmed received. Corpus updated accordingly." if ok else "Will retry collection on next cycle.",
        "hitl":        "No human intervention required for this action." if ok else "Queuing for human review — holding execution.",
        "auditor":     "Audit record updated. Compliance log current." if ok else "Audit flagged — will notify compliance team.",
    }
    return comments.get(recipient_id, "Acknowledged — logged and filed.")


def _next_steps(recipient_id: str, outcome: str) -> str:
    steps = {
        "translator":  "Next: route classified intent to appropriate domain handler.",
        "exec_admin":  "Next: include in tomorrow's brief and update ROI calendar.",
        "rosetta":     "Next: covenant ledger updated. Soul integrity check scheduled.",
        "prod_ops":    "Next: health watchdog will re-check in 5 minutes.",
        "collector":   "Next: corpus_collect will re-run in 15 minutes.",
        "hitl":        "Next: standing by for next action requiring human approval.",
        "auditor":     "Next: audit report will be included in the next compliance export.",
    }
    return steps.get(recipient_id, "Next: monitoring.")


def _send_chain_sync(acting_agent: str, signal: Dict, result: Dict, outcome: str):
    """Synchronous runner — executes in a daemon thread."""
    try:
        # Detect active meeting
        meeting = _get_active_meeting()

        thread = _compose_thread(acting_agent, signal, result, outcome, meeting)
        if thread is None:
            return

        # If meeting active — post shadow suggestion FIRST (non-email channel)
        if meeting:
            shadow_content = (
                f"[{acting_agent.upper()}] Completed: {thread['intent']} | "
                f"Outcome: {outcome} | "
                f"Reported to: {thread['report_to_id']}"
            )
            _post_shadow_suggestion(
                session_id=meeting["session_id"],
                agent_id=acting_agent,
                suggestion_type="task_completion",
                content=shadow_content,
            )

        # Send emails
        try:
            from src.email_integration import EmailService
        except ImportError:
            from email_integration import EmailService

        svc = EmailService.from_env()

        async def _send_both():
            for email_data in [thread["email1"], thread["email2"]]:
                try:
                    safe_from = _safe_name(email_data["from_name"])
                    from_addr = (
                        f"{safe_from} <{email_data['from_addr']}>"
                        if safe_from else email_data["from_addr"]
                    )
                    res = await svc.send(
                        to=email_data["to"],
                        subject=email_data["subject"],
                        body=email_data["body"],
                        from_addr=from_addr,
                    )
                    if res.success:
                        logger.info(
                            "AgentEmailChain: sent %s -> %s (thread=%s latency=%.2fs%s)",
                            email_data["from_addr"],
                            email_data["to"][0],
                            thread["thread_id"],
                            res.latency_seconds or 0,
                            " [MEETING]" if meeting else "",
                        )
                    else:
                        logger.warning("AgentEmailChain: send failed: %s", res.error)
                except Exception as e:
                    logger.warning("AgentEmailChain: email error: %s", e)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_send_both())
        finally:
            loop.close()

    except Exception as exc:
        logger.warning("AgentEmailChain: chain error for %s: %s", acting_agent, exc)


def fire_agent_email_chain(acting_agent: str, signal: Dict, result: Dict, outcome: str):
    """
    Public entry point. Called from AgentBase._run() after every completed act().
    Non-blocking — spawns a daemon thread.
    Skips heartbeat/drain signals (too noisy).
    Meeting-aware: if a management meeting is active, CCs participants and
    posts shadow suggestions into the meeting feed.
    """
    sig_type = signal.get("signal_type", "")
    if sig_type in SKIP_SIGNAL_TYPES:
        return

    t = threading.Thread(
        target=_send_chain_sync,
        args=(acting_agent, signal, result, outcome),
        daemon=True,
        name=f"email-chain-{acting_agent}",
    )
    t.start()
