# © 2020 Inoni Limited Liability Company by Corey Post
# License: BSL 1.1
"""Matrix Formatters — rich HTML/plain-text message formatters for the Murphy Matrix bot.

All public functions return a ``(plain_text, html)`` tuple so callers can
send both ``body`` and ``formatted_body`` in Matrix events.
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_H = _html.escape  # short alias

MessagePair = Tuple[str, str]  # (plain, html)


def _ts() -> str:
    """Return current UTC time as a compact string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _pill(text: str, ok: bool) -> str:
    colour = "#27ae60" if ok else "#c0392b"
    symbol = "●" if ok else "✕"
    return (
        f'<span style="background:{colour};color:#fff;'
        f'padding:1px 6px;border-radius:3px;font-size:0.85em;">'
        f"{symbol}&nbsp;{_H(text)}</span>"
    )


def _badge(text: str, colour: str = "#555") -> str:
    return (
        f'<span style="background:{colour};color:#fff;'
        f'padding:1px 5px;border-radius:3px;font-size:0.8em;">'
        f"{_H(text)}</span>"
    )


def _section(title: str, body_html: str) -> str:
    return (
        f"<h4>☠ {_H(title)}</h4>"
        f'<div style="font-family:monospace;font-size:0.9em;">{body_html}</div>'
    )


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_status(api_ok: bool, mfgc_ok: bool) -> MessagePair:
    """``☠ MURPHY SYSTEM ☠`` status pills for API and MFGC health."""
    plain = (
        f"☠ MURPHY SYSTEM ☠\n"
        f"API:  {'● ONLINE' if api_ok else '✕ OFFLINE'}\n"
        f"MFGC: {'● ONLINE' if mfgc_ok else '✕ OFFLINE'}\n"
        f"{_ts()}"
    )
    html = (
        "<p><strong>☠ MURPHY SYSTEM ☠</strong></p>"
        f"<p>API:&nbsp;&nbsp;{_pill('API', api_ok)}&nbsp;&nbsp;"
        f"MFGC:&nbsp;{_pill('MFGC', mfgc_ok)}</p>"
        f'<p style="color:#888;font-size:0.8em;">{_H(_ts())}</p>'
    )
    return plain, html


def format_overview(summary: Dict[str, Any]) -> MessagePair:
    """Running / HITL-waiting / stuck counts + UTC timestamp."""
    running = summary.get("running", 0)
    waiting = summary.get("hitl_waiting", summary.get("waiting", 0))
    stuck = summary.get("stuck", 0)
    ts = _ts()

    plain = f"● {running} RUNNING  ● {waiting} HITL WAITING  ● {stuck} STUCK\n{ts}"
    html = (
        f'<p><span style="color:#27ae60;">● {running} RUNNING</span>'
        f'&nbsp;&nbsp;<span style="color:#e67e22;">● {waiting} HITL WAITING</span>'
        f'&nbsp;&nbsp;<span style="color:#c0392b;">● {stuck} STUCK</span></p>'
        f'<p style="color:#888;font-size:0.8em;">{_H(ts)}</p>'
    )
    return plain, html


def format_table(columns: List[str], rows: List[List[Any]]) -> MessagePair:
    """Render a list of rows as an HTML table and plain-text grid."""
    # Compute column widths in a single pass to avoid O(rows × columns²) complexity.
    col_widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, w in enumerate(col_widths):
            if i < len(row):
                col_widths[i] = max(w, len(str(row[i])))

    # Plain text
    header = "  ".join(str(c).ljust(w) for c, w in zip(columns, col_widths))
    sep = "  ".join("-" * w for w in col_widths)
    body_lines = ["  ".join(str(r[i] if i < len(r) else "").ljust(w)
                             for i, w in enumerate(col_widths))
                  for r in rows]
    plain = "\n".join([header, sep] + body_lines)

    # HTML
    th = "".join(f"<th>{_H(str(c))}</th>" for c in columns)
    tr_rows = "".join(
        "<tr>" + "".join(f"<td>{_H(str(r[i] if i < len(r) else ''))}</td>"
                          for i in range(len(columns))) + "</tr>"
        for r in rows
    )
    html = (
        '<table style="border-collapse:collapse;font-family:monospace;font-size:0.85em;">'
        f'<tr style="background:#222;color:#0f0;">{th}</tr>'
        f"{tr_rows}"
        "</table>"
    )
    return plain, html


def format_workflow_detail(workflow: Dict[str, Any]) -> MessagePair:
    """Render a single workflow detail card."""
    wid = workflow.get("id", "?")
    name = workflow.get("name", workflow.get("title", wid))
    status = workflow.get("status", "unknown")
    steps = workflow.get("steps", [])

    colour = {"running": "#27ae60", "failed": "#c0392b", "complete": "#2980b9",
              "stuck": "#e74c3c", "waiting": "#e67e22"}.get(str(status).lower(), "#888")

    plain = f"Workflow: {name} [{wid}]\nStatus: {status}\nSteps: {len(steps)}"
    step_html = "".join(
        f"<li>{_H(str(s.get('name', s) if isinstance(s, dict) else s))}"
        f"&nbsp;{_badge(str(s.get('status', '?') if isinstance(s, dict) else '?'))}</li>"
        for s in (steps[:20] if steps else [])
    )
    html = (
        f"<b>Workflow:</b> {_H(str(name))} <code>{_H(str(wid))}</code><br>"
        f"<b>Status:</b>&nbsp;"
        f'<span style="color:{colour};font-weight:bold;">{_H(str(status))}</span><br>'
        f"<b>Steps ({len(steps)}):</b><ul>{step_html}</ul>"
    )
    return plain, html


def format_agent_detail(agent: Dict[str, Any]) -> MessagePair:
    """Render a single agent detail card."""
    aid = agent.get("id", "?")
    persona = agent.get("persona", agent.get("name", "?"))
    status = agent.get("status", "?")
    caps = agent.get("capabilities", agent.get("capability_map", []))

    plain = f"Agent: {persona} [{aid}]\nStatus: {status}\nCapabilities: {len(caps)}"
    cap_html = ", ".join(_H(str(c)) for c in (caps[:15] if isinstance(caps, list) else []))
    html = (
        f"<b>Agent:</b> {_H(str(persona))} <code>{_H(str(aid))}</code><br>"
        f"<b>Status:</b> {_badge(str(status))}<br>"
        f"<b>Capabilities:</b> {cap_html or '—'}"
    )
    return plain, html


def format_hitl_intervention(intervention: Dict[str, Any]) -> MessagePair:
    """Render a HITL intervention card with approval/rejection instructions."""
    iid = intervention.get("id", "?")
    title = intervention.get("title", intervention.get("description", "Intervention required"))
    context = intervention.get("context", intervention.get("details", ""))
    priority = intervention.get("priority", "normal")
    created = intervention.get("created_at", intervention.get("timestamp", ""))

    plain = (
        f"⚠ HITL INTERVENTION [{iid}]\n{title}\n{context}\n"
        f"Priority: {priority}\n"
        f"React ✅ to approve, ❌ to reject\n"
        f"Or: !murphy hitl respond {iid} approve/reject [reason]"
    )
    html = (
        f'<p style="color:#e67e22;font-weight:bold;">⚠ HITL INTERVENTION</p>'
        f"<p><b>ID:</b> <code>{_H(str(iid))}</code>&nbsp;{_badge(str(priority), '#e67e22')}</p>"
        f"<p><b>{_H(str(title))}</b></p>"
        + (f"<p>{_H(str(context))}</p>" if context else "")
        + (f'<p style="color:#888;font-size:0.8em;">{_H(str(created))}</p>' if created else "")
        + "<p>React ✅ to approve, ❌ to reject, "
        f"or: <code>!murphy hitl respond {_H(str(iid))} approve/reject [reason]</code></p>"
    )
    return plain, html


def format_cost_summary(costs: Dict[str, Any]) -> MessagePair:
    """Text-based gauge for budget usage."""
    total = costs.get("total", costs.get("total_cost", 0))
    budget = costs.get("budget", costs.get("budget_limit", 0))
    currency = costs.get("currency", "USD")

    pct = min(int((total / budget * 100) if budget else 0), 100)
    filled = int(pct / 5)
    bar = "█" * filled + "░" * (20 - filled)

    plain = f"Costs: {currency} {total:.2f} / {budget:.2f} ({pct}%)\n[{bar}]"
    colour = "#27ae60" if pct < 70 else "#e67e22" if pct < 90 else "#c0392b"
    html = (
        f"<b>Costs:</b> {_H(currency)} {total:.2f} / {budget:.2f} "
        f'<span style="color:{colour};">({pct}%)</span><br>'
        f'<code style="color:{colour};">[{_H(bar)}]</code>'
    )
    return plain, html


_JARGON: Dict[str, str] = {
    "MFGC": "Multi-Function Gate Controller — orchestrates workflow gate logic and approval chains.",
    "HITL": "Human-In-The-Loop — intervention checkpoint requiring human approval before proceeding.",
    "Gate": "A decision or approval checkpoint in a workflow DAG.",
    "Swarm": "A coordinated group of Worker agents executing tasks in parallel.",
    "Wingman": "AI co-pilot agent that monitors task execution and suggests corrections.",
    "Causality Engine": "Traces cause-effect chains across system events for root-cause analysis.",
    "Confidence Engine": "Scores agent outputs with a confidence probability before surfacing results.",
    "Orchestrator": "Top-level coordinator that manages workflows, agents, and resource allocation.",
    "Architect": "Designs and validates DAGs, workflow blueprints, and integration plans.",
    "Worker": "Leaf-level execution agent performing atomic tasks within a workflow.",
    "DAG": "Directed Acyclic Graph — the execution topology of a Murphy workflow.",
    "Flow Graph": "Visual representation of a DAG showing task dependencies and data flow.",
    "Gap Closure": "Automated process of identifying and filling capability or knowledge gaps.",
    "Librarian": "Knowledge retrieval agent — answers queries against the Murphy knowledge base.",
    "Terminal": "Browser-based command interface for direct interaction with Murphy subsystems.",
    "Insight": "AI-generated analytical output surfacing patterns, anomalies, or recommendations.",
    "Integration": "A configured connection to an external system (Slack, GitHub, Jira, etc.).",
    "Playbook": "A reusable, parameterised workflow template for common operational scenarios.",
    "Sentinel": "Monitoring agent that watches for anomalies and fires alerts to operators.",
    "Rollback": "Automated reversion of a workflow to a known-good prior state.",
    "Quorum": "Minimum number of agent agreements required to advance a consensus gate.",
    "Persona": "The identity profile and behavioural configuration of an agent.",
    "Dispatch": "Event-driven invocation of a workflow or action based on a trigger.",
    "Telemetry": "Real-time metrics, logs, and traces emitted by Murphy subsystems.",
    "Canary": "Low-traffic deployment target for validating changes before full rollout.",
    "Circuit Breaker": "Fault-tolerance pattern that stops cascading failures by opening the circuit.",
    "Backpressure": "Flow-control mechanism that slows producers when consumers are overwhelmed.",
    "Capability Map": "Inventory of skills and actions available to an agent or the system.",
    "Cost Guard": "Budget enforcement layer that pauses or alerts when spend thresholds are breached.",
}


def format_jargon(term: str, definition: str) -> MessagePair:
    """Single jargon term definition."""
    plain = f"{term}: {definition}"
    html = f"<b>{_H(term)}:</b> {_H(definition)}"
    return plain, html


def format_jargon_list(terms_dict: Optional[Dict[str, str]] = None) -> MessagePair:
    """All 28 jargon terms (or a custom dict)."""
    d = terms_dict if terms_dict is not None else _JARGON
    plain = "\n".join(f"• {k}: {v}" for k, v in d.items())
    html = "<ul>" + "".join(f"<li><b>{_H(k)}:</b> {_H(v)}</li>" for k, v in d.items()) + "</ul>"
    return plain, html


def format_help(commands_by_category: Dict[str, List[str]]) -> MessagePair:
    """Grouped command reference."""
    lines: List[str] = []
    html_parts: List[str] = ["<p><strong>☠ MURPHY COMMAND REFERENCE ☠</strong></p>"]
    for cat, cmds in commands_by_category.items():
        lines.append(f"\n{cat}")
        lines.append("─" * len(cat))
        html_parts.append(f"<h4>{_H(cat)}</h4><ul>")
        for cmd in cmds:
            lines.append(f"  {cmd}")
            html_parts.append(f"<li><code>{_H(cmd)}</code></li>")
        html_parts.append("</ul>")
    return "\n".join(lines), "".join(html_parts)


_NAV_LINKS = [
    ("⬡", "ORCHESTRATOR", "/ui/terminal_orchestrator.html"),
    ("✦", "ORG CHART", "/ui/terminal_orgchart.html"),
    ("⬢", "INTEGRATIONS", "/ui/terminal_integrations.html"),
    ("◈", "ARCHITECT", "/ui/terminal_architect.html"),
    ("◎", "WORKER", "/ui/terminal_worker.html"),
    ("⊞", "COSTS", "/ui/terminal_costs.html"),
    ("⋮", "WORKFLOWS", "/ui/workflow_canvas.html"),
]


def format_links(base_url: str) -> MessagePair:
    """Clickable terminal links with sidebar icons."""
    base = base_url.rstrip("/")
    lines = [f"{icon} {label}: {base}{path}" for icon, label, path in _NAV_LINKS]
    html_items = "".join(
        f'<li>{_H(icon)}&nbsp;<a href="{_H(base)}{_H(path)}">{_H(label)}</a></li>'
        for icon, label, path in _NAV_LINKS
    )
    return "\n".join(lines), f"<ul>{html_items}</ul>"


def format_error(msg: str) -> MessagePair:
    """``✕ ERROR`` prefixed message."""
    plain = f"✕ ERROR: {msg}"
    html = f'<p style="color:#c0392b;font-weight:bold;">✕ ERROR:</p><p>{_H(str(msg))}</p>'
    return plain, html


def format_success(msg: str) -> MessagePair:
    """``✓ OK`` prefixed message."""
    plain = f"✓ {msg}"
    html = f'<p style="color:#27ae60;font-weight:bold;">✓</p><p>{_H(str(msg))}</p>'
    return plain, html


def format_code_block(text: str) -> MessagePair:
    """Monospace code block."""
    return text, f"<pre><code>{_H(str(text))}</code></pre>"


def format_terminal_output(
    prompt: str,
    command: str,
    output: str,
    is_error: bool = False,
) -> MessagePair:
    """MurphyTerminalPanel-style prompt + command + output."""
    plain = f"{prompt}> {command}\n{output}"
    colour = "#c0392b" if is_error else "#27ae60"
    html = (
        f'<pre style="background:#111;color:#0f0;padding:8px;border-radius:4px;">'
        f'<span style="color:#888;">{_H(prompt)}&gt; </span>'
        f'<span style="color:#0f0;">{_H(command)}</span>\n'
        f'<span style="color:{colour};">{_H(str(output))}</span>'
        f"</pre>"
    )
    return plain, html


# ---------------------------------------------------------------------------
# Communication / integration formatters (NEW)
# ---------------------------------------------------------------------------


def format_email_result(send_result: Any) -> MessagePair:
    """Email delivery status with provider, latency, message_id."""
    ok = getattr(send_result, "success", True)
    provider = getattr(send_result, "provider", "unknown")
    msg_id = getattr(send_result, "message_id", "—")
    latency = getattr(send_result, "latency_ms", None)
    error = getattr(send_result, "error", None)

    lat_str = f"{latency:.0f}ms" if isinstance(latency, (int, float)) else "—"
    plain = (
        f"{'✓' if ok else '✕'} Email {'sent' if ok else 'FAILED'}\n"
        f"Provider: {provider}  ID: {msg_id}  Latency: {lat_str}"
        + (f"\nError: {error}" if error else "")
    )
    colour = "#27ae60" if ok else "#c0392b"
    html = (
        f'<p><span style="color:{colour};font-weight:bold;">'
        f"{'✓ Email sent' if ok else '✕ Email FAILED'}</span></p>"
        f"<p><b>Provider:</b> {_H(str(provider))}&nbsp;"
        f"<b>ID:</b> <code>{_H(str(msg_id))}</code>&nbsp;"
        f"<b>Latency:</b> {_H(lat_str)}</p>"
        + (f"<p><b>Error:</b> {_H(str(error))}</p>" if error else "")
    )
    return plain, html


def format_notification_result(notification: Any) -> MessagePair:
    """Notification delivery status per channel."""
    nid = getattr(notification, "id", "?")
    subject = getattr(notification, "subject", "?")
    channels = getattr(notification, "channels", [])
    deliveries = getattr(notification, "delivery_records", [])

    lines = [f"Notification {nid}: {subject}"]
    html_rows = ""
    for d in deliveries:
        ch = getattr(d, "channel", "?")
        ok = getattr(d, "success", True)
        lines.append(f"  {'✓' if ok else '✕'} {ch}")
        colour = "#27ae60" if ok else "#c0392b"
        html_rows += f'<li><span style="color:{colour};">{"✓" if ok else "✕"}&nbsp;{_H(str(ch))}</span></li>'

    plain = "\n".join(lines)
    html = (
        f"<p><b>Notification</b> <code>{_H(str(nid))}</code>: {_H(str(subject))}</p>"
        f"<ul>{html_rows}</ul>"
    )
    return plain, html


def format_webhook_delivery(delivery: Any) -> MessagePair:
    """Webhook fire result with URL, status_code, latency."""
    url = getattr(delivery, "url", getattr(delivery, "target_url", "?"))
    status = getattr(delivery, "status_code", "?")
    latency = getattr(delivery, "latency_ms", None)
    ok = getattr(delivery, "success", True) if hasattr(delivery, "success") else (
        isinstance(status, int) and 200 <= status < 300
    )
    event_type = getattr(delivery, "event_type", "?")

    lat_str = f"{latency:.0f}ms" if isinstance(latency, (int, float)) else "—"
    plain = f"{'✓' if ok else '✕'} Webhook [{event_type}] → {url} HTTP {status} {lat_str}"
    colour = "#27ae60" if ok else "#c0392b"
    html = (
        f'<p><span style="color:{colour};font-weight:bold;">{"✓" if ok else "✕"} Webhook</span>'
        f"&nbsp;{_badge(str(event_type))}</p>"
        f"<p><b>URL:</b> <code>{_H(str(url))}</code>&nbsp;"
        f"<b>Status:</b> {_H(str(status))}&nbsp;"
        f"<b>Latency:</b> {_H(lat_str)}</p>"
    )
    return plain, html


def format_connector_status(connector_type: str, status: Dict[str, Any]) -> MessagePair:
    """Slack / Teams / Discord / Email connector health."""
    ok = status.get("healthy", status.get("connected", True))
    last_check = status.get("last_check", "?")
    error = status.get("error", "")

    plain = f"{'✓' if ok else '✕'} {connector_type}: {'healthy' if ok else 'ERROR'}"
    colour = "#27ae60" if ok else "#c0392b"
    html = (
        f'<p><span style="color:{colour};font-weight:bold;">'
        f'{"✓" if ok else "✕"}&nbsp;{_H(connector_type)}</span></p>'
        + (f"<p><b>Error:</b> {_H(str(error))}</p>" if error else "")
        + f'<p style="color:#888;font-size:0.8em;">Last check: {_H(str(last_check))}</p>'
    )
    return plain, html


def format_comms_activity_feed(activities: List[Dict[str, Any]]) -> MessagePair:
    """Chronological feed of all communication events."""
    if not activities:
        return "No recent communication activity.", "<p>No recent communication activity.</p>"

    lines: List[str] = ["☠ COMMS ACTIVITY FEED ☠"]
    html_rows: List[str] = ["<p><strong>☠ COMMS ACTIVITY FEED ☠</strong></p><ul>"]

    for a in activities[-30:]:  # cap to last 30
        ts = a.get("timestamp", a.get("created_at", ""))[:19]
        atype = a.get("type", a.get("channel", "?"))
        subject = a.get("subject", a.get("message", a.get("event_type", "?")))
        ok = a.get("success", True)
        symbol = "✓" if ok else "✕"
        lines.append(f"{symbol} [{ts}] {atype}: {subject}")
        colour = "#27ae60" if ok else "#c0392b"
        html_rows.append(
            f'<li><span style="color:{colour};">{_H(symbol)}</span>'
            f'&nbsp;<code>{_H(ts)}</code>'
            f"&nbsp;{_badge(str(atype))}"
            f"&nbsp;{_H(str(subject))}</li>"
        )

    html_rows.append("</ul>")
    return "\n".join(lines), "".join(html_rows)


def format_integration_status(integration: Dict[str, Any]) -> MessagePair:
    """Integration health with circuit breaker state."""
    iid = integration.get("id", "?")
    name = integration.get("name", iid)
    status = integration.get("status", "?")
    cb = integration.get("circuit_breaker", integration.get("circuit_breaker_state", "?"))
    failures = integration.get("failure_count", integration.get("consecutive_failures", 0))

    ok = str(status).lower() in ("active", "ok", "healthy", "connected")
    plain = f"{'✓' if ok else '✕'} {name} [{iid}]: {status}  CB: {cb}  failures: {failures}"
    colour = "#27ae60" if ok else "#c0392b"
    html = (
        f'<p><span style="color:{colour};font-weight:bold;">'
        f'{"✓" if ok else "✕"}&nbsp;{_H(str(name))}</span>'
        f"&nbsp;<code>{_H(str(iid))}</code></p>"
        f"<p><b>Status:</b> {_badge(str(status), colour)}"
        f"&nbsp;<b>Circuit Breaker:</b> {_badge(str(cb))}"
        f"&nbsp;<b>Failures:</b> {_H(str(failures))}</p>"
    )
    return plain, html


def format_service_ticket(ticket: Dict[str, Any]) -> MessagePair:
    """Service ticket detail with SLA countdown."""
    tid = ticket.get("id", "?")
    title = ticket.get("title", ticket.get("subject", "?"))
    status = ticket.get("status", "?")
    priority = ticket.get("priority", "?")
    assignee = ticket.get("assignee", ticket.get("assigned_to", "—"))
    sla_remaining = ticket.get("sla_remaining", ticket.get("sla_breach_at", None))

    plain = (
        f"Ticket {tid}: {title}\n"
        f"Status: {status}  Priority: {priority}  Assignee: {assignee}"
        + (f"\nSLA: {sla_remaining}" if sla_remaining else "")
    )
    sla_html = f"<p><b>SLA:</b> {_H(str(sla_remaining))}</p>" if sla_remaining else ""
    html = (
        f"<p><b>Ticket</b> <code>{_H(str(tid))}</code>: {_H(str(title))}</p>"
        f"<p>{_badge(str(status))} {_badge(str(priority), '#e67e22')}"
        f"&nbsp;<b>Assignee:</b> {_H(str(assignee))}</p>"
        f"{sla_html}"
    )
    return plain, html


def get_all_jargon() -> Dict[str, str]:
    """Return the full 28-term jargon dictionary."""
    return dict(_JARGON)


__all__ = [
    "MessagePair",
    "format_status",
    "format_overview",
    "format_table",
    "format_workflow_detail",
    "format_agent_detail",
    "format_hitl_intervention",
    "format_cost_summary",
    "format_jargon",
    "format_jargon_list",
    "format_help",
    "format_links",
    "format_error",
    "format_success",
    "format_code_block",
    "format_terminal_output",
    "format_email_result",
    "format_notification_result",
    "format_webhook_delivery",
    "format_connector_status",
    "format_comms_activity_feed",
    "format_integration_status",
    "format_service_ticket",
    "get_all_jargon",
]
