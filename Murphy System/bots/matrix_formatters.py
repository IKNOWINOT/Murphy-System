"""Rich Matrix message formatters for the Murphy bot.

Produces HTML-formatted messages with Murphy's terminal aesthetic:
  ☠ skull decorators  |  ● running  ○ idle  ✕ error
  Color-coded status  |  HTML tables  |  Code blocks
"""
from __future__ import annotations

import json
from typing import Any


# ---------------------------------------------------------------------------
# Status indicators
# ---------------------------------------------------------------------------
STATUS_RUNNING = "●"
STATUS_IDLE = "○"
STATUS_ERROR = "✕"
STATUS_OK = "✓"
STATUS_WARN = "⚠"

COLOR_GREEN = "#00ff88"
COLOR_RED = "#ff4455"
COLOR_YELLOW = "#ffcc00"
COLOR_BLUE = "#4488ff"
COLOR_GRAY = "#888888"
COLOR_SKULL = "#cc44ff"


def _color(text: str, color: str) -> str:
    return f'<font color="{color}">{text}</font>'


def _bold(text: str) -> str:
    return f"<strong>{text}</strong>"


def _code(text: str) -> str:
    return f"<code>{text}</code>"


def _pre(text: str) -> str:
    return f"<pre><code>{text}</code></pre>"


def skull_header(title: str) -> str:
    """Return a ☠-decorated section header."""
    return f"{_color('☠', COLOR_SKULL)} {_bold(title)} {_color('☠', COLOR_SKULL)}"


def status_badge(status: str) -> str:
    """Map a status string to a colored badge."""
    s = (status or "").lower()
    if s in ("running", "active", "healthy", "online", "ok", "success", "connected"):
        return _color(f"{STATUS_RUNNING} {status}", COLOR_GREEN)
    if s in ("idle", "standby", "paused", "waiting"):
        return _color(f"{STATUS_IDLE} {status}", COLOR_YELLOW)
    if s in ("error", "failed", "offline", "down", "critical", "unhealthy"):
        return _color(f"{STATUS_ERROR} {status}", COLOR_RED)
    return _color(f"{STATUS_IDLE} {status}", COLOR_GRAY)


def success_msg(text: str) -> str:
    return _color(f"{STATUS_OK} {text}", COLOR_GREEN)


def error_msg(text: str) -> str:
    return _color(f"{STATUS_ERROR} {text}", COLOR_RED)


def warn_msg(text: str) -> str:
    return _color(f"{STATUS_WARN} {text}", COLOR_YELLOW)


# ---------------------------------------------------------------------------
# Structured data formatters
# ---------------------------------------------------------------------------

def format_json(data: Any, indent: int = 2) -> str:
    """Render arbitrary data as a pretty JSON code block."""
    try:
        text = json.dumps(data, indent=indent, default=str)
    except Exception:
        text = str(data)
    return _pre(text)


def format_kv_table(pairs: list[tuple[str, str]], title: str | None = None) -> str:
    """Build a two-column HTML table from (key, value) pairs."""
    rows = "".join(
        f"<tr><td>{_bold(k)}</td><td>{v}</td></tr>" for k, v in pairs
    )
    table = f"<table><tbody>{rows}</tbody></table>"
    if title:
        return f"{skull_header(title)}<br/>{table}"
    return table


def format_dict(data: dict, title: str | None = None) -> str:
    """Format a flat dict as a key-value table."""
    pairs = [(str(k), str(v)) for k, v in data.items()]
    return format_kv_table(pairs, title)


def format_list_table(
    items: list[dict],
    columns: list[str],
    title: str | None = None,
) -> str:
    """Render a list of dicts as an HTML table with specified column headers."""
    header_cells = "".join(f"<th>{_bold(c)}</th>" for c in columns)
    header = f"<tr>{header_cells}</tr>"
    rows = []
    for item in items:
        cells = "".join(f"<td>{item.get(c, '')}</td>" for c in columns)
        rows.append(f"<tr>{cells}</tr>")
    body = "".join(rows)
    table = f"<table><thead>{header}</thead><tbody>{body}</tbody></table>"
    if title:
        return f"{skull_header(title)}<br/>{table}"
    return table


# ---------------------------------------------------------------------------
# Domain-specific formatters
# ---------------------------------------------------------------------------

def format_status(data: dict) -> str:
    pairs = [
        ("Version", data.get("version", "—")),
        ("Status", status_badge(str(data.get("status", "unknown")))),
        ("Uptime", str(data.get("uptime", "—"))),
        ("Tasks", str(data.get("tasks", "—"))),
        ("Agents", str(data.get("agents", "—"))),
    ]
    extra = {k: v for k, v in data.items() if k not in {
        "version", "status", "uptime", "tasks", "agents"
    }}
    if extra:
        pairs += [(str(k), str(v)) for k, v in extra.items()]
    return format_kv_table(pairs, "Murphy System Status")


def format_health(data: dict) -> str:
    components = data.get("components", data)
    pairs = [(str(k), status_badge(str(v))) for k, v in components.items()]
    overall = data.get("status", "unknown")
    pairs.insert(0, ("Overall", status_badge(str(overall))))
    return format_kv_table(pairs, "System Health")


def format_agents(agents: list) -> str:
    if not agents:
        return warn_msg("No agents found.")
    cols = ["id", "name", "status", "role", "tasks_completed"]
    available = [c for c in cols if any(c in (a if isinstance(a, dict) else {}) for a in agents)]
    if not available:
        available = list(agents[0].keys()) if isinstance(agents[0], dict) else ["agent"]
    return format_list_table(agents, available, "Agents")


def format_workflows(workflows: list) -> str:
    if not workflows:
        return warn_msg("No workflows found.")
    cols = ["id", "name", "status", "created_at"]
    available = [c for c in cols if any(c in (w if isinstance(w, dict) else {}) for w in workflows)]
    if not available:
        available = list(workflows[0].keys()) if isinstance(workflows[0], dict) else ["workflow"]
    return format_list_table(workflows, available, "Workflows")


def format_costs(data: dict) -> str:
    pairs = [(str(k), str(v)) for k, v in data.items()]
    return format_kv_table(pairs, "Cost Overview")


def format_hitl_intervention(item: dict) -> str:
    pairs = [
        ("ID", _code(str(item.get("id", "—")))),
        ("Type", str(item.get("type", "—"))),
        ("Description", str(item.get("description", item.get("message", "—")))),
        ("Priority", str(item.get("priority", "—"))),
        ("Created", str(item.get("created_at", "—"))),
        ("Status", status_badge(str(item.get("status", "pending")))),
    ]
    msg = format_kv_table(pairs, f"HITL Intervention — {item.get('id', '?')}")
    msg += "<br/>React with ✅ to approve or ❌ to reject."
    return msg


def format_hitl_list(items: list) -> str:
    if not items:
        return success_msg("No pending HITL interventions.")
    parts = [skull_header(f"Pending HITL Interventions ({len(items)})")]
    for item in items:
        parts.append(format_hitl_intervention(item))
        parts.append("<hr/>")
    return "<br/>".join(parts)


def format_flows(data: dict | list, title: str = "Information Flows") -> str:
    if isinstance(data, list):
        return format_json(data)
    return format_dict(data, title)


def format_orgchart(data: dict) -> str:
    nodes = data.get("nodes", data.get("agents", []))
    if isinstance(nodes, list) and nodes:
        cols = ["id", "name", "role", "status", "supervisor"]
        available = [c for c in cols if any(c in (n if isinstance(n, dict) else {}) for n in nodes)]
        return format_list_table(nodes, available, "Org Chart")
    return format_dict(data, "Org Chart")


def format_links(web_url: str) -> str:
    """Return a message with clickable links to all web terminals."""
    terminals = [
        ("Unified Terminal", "terminal_unified.html"),
        ("Integrated Terminal", "terminal_integrated.html"),
        ("Architect Terminal", "terminal_architect.html"),
        ("Worker Terminal", "terminal_worker.html"),
        ("Costs Terminal", "terminal_costs.html"),
        ("Org Chart Terminal", "terminal_orgchart.html"),
        ("Integrations Terminal", "terminal_integrations.html"),
        ("Enhanced Terminal", "terminal_enhanced.html"),
        ("Workflow Canvas", "workflow_canvas.html"),
    ]
    base = web_url.rstrip("/")
    items = "".join(
        f'<li><a href="{base}/ui/{page}">{name}</a></li>'
        for name, page in terminals
    )
    return f"{skull_header('Murphy System — Web Terminals')}<br/><ul>{items}</ul>"


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

HELP_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "core": [
        ("!murphy status", "Full system status and metrics"),
        ("!murphy health", "Deep health check"),
        ("!murphy info", "System info (version, modules)"),
    ],
    "orchestrator": [
        ("!murphy overview", "Full business flow snapshot"),
        ("!murphy flows", "All active information flows"),
        ("!murphy flows inbound", "Inbound flows by department"),
        ("!murphy flows processing", "Agents/workflows processing"),
        ("!murphy flows outbound", "Outbound flows by type/client"),
        ("!murphy flows state", "Collective state of all flows"),
    ],
    "execution": [
        ("!murphy execute <command>", "Execute a task"),
        ("!murphy chat <message>", "Chat with Murphy"),
    ],
    "workflows": [
        ("!murphy workflows", "List all saved workflows"),
        ("!murphy workflow <id>", "Get workflow details"),
        ("!murphy workflow save <json>", "Save a workflow"),
        ("!murphy workflow-terminal list", "List workflow terminal items"),
        ("!murphy workflow builder", "Link to web workflow builder"),
        ("!murphy generate plan <description>", "Generate plan from natural language"),
        ("!murphy upload plan <json>", "Upload execution plan"),
    ],
    "agents": [
        ("!murphy agents", "List all agents"),
        ("!murphy agent <id>", "Agent details"),
        ("!murphy agent <id> activity", "Agent activity log"),
        ("!murphy orgchart", "Live agent org chart"),
        ("!murphy orgchart <task_id>", "Org chart for a task"),
    ],
    "hitl": [
        ("!murphy hitl pending", "List pending HITL interventions"),
        ("!murphy hitl respond <id> <approve|reject> [reason]", "Respond to intervention"),
        ("!murphy hitl stats", "HITL statistics"),
    ],
    "forms": [
        ("!murphy form task <json>", "Execute task via form"),
        ("!murphy form validate <json>", "Validate execution packet"),
        ("!murphy form correct <json>", "Submit correction"),
        ("!murphy form status <id>", "Get form submission status"),
    ],
    "corrections": [
        ("!murphy corrections patterns", "Correction patterns"),
        ("!murphy corrections stats", "Correction statistics"),
        ("!murphy corrections training", "Training data"),
    ],
    "costs": [
        ("!murphy costs", "Cost overview"),
        ("!murphy costs breakdown", "Cost breakdown by category"),
        ("!murphy costs by-bot", "Per-agent cost breakdown"),
        ("!murphy costs budget", "Department budget"),
    ],
    "integrations": [
        ("!murphy integrations", "List active integrations"),
        ("!murphy integrations all", "All integrations"),
    ],
    "mfgc": [
        ("!murphy mfgc state", "MFGC state"),
        ("!murphy mfgc config", "MFGC config"),
        ("!murphy mfgc config set <json>", "Update MFGC config"),
        ("!murphy mfgc setup <profile>", "Configure MFGC profile"),
    ],
    "librarian": [
        ("!murphy ask <query>", "Ask the Librarian"),
        ("!murphy librarian status", "Librarian status"),
    ],
    "documents": [
        ("!murphy documents", "List documents"),
        ("!murphy deliverables", "List outbound deliverables"),
    ],
    "tasks": [
        ("!murphy tasks", "List all tasks"),
        ("!murphy queue", "Current production queue"),
    ],
    "llm": [
        ("!murphy llm status", "LLM provider status"),
        ("!murphy mfm status", "MFM deployment status"),
        ("!murphy mfm metrics", "Training metrics"),
    ],
    "onboarding": [
        ("!murphy onboarding status", "Onboarding status"),
        ("!murphy onboarding questions", "Wizard questions"),
    ],
    "ip": [
        ("!murphy ip assets", "IP asset list"),
        ("!murphy credentials", "Credential profiles"),
    ],
    "profiles": [
        ("!murphy profiles", "List profiles"),
        ("!murphy role", "Current user role"),
        ("!murphy permissions", "Permissions for role"),
    ],
    "diagnostics": [
        ("!murphy diagnostics", "System diagnostics"),
        ("!murphy wingman", "Wingman protocol status"),
        ("!murphy causality", "Causality sandbox status"),
    ],
    "navigation": [
        ("!murphy help", "Show all commands"),
        ("!murphy help <category>", "Show commands for a category"),
        ("!murphy links", "Clickable web terminal links"),
    ],
}


def format_help(category: str | None = None) -> str:
    if category and category.lower() in HELP_CATEGORIES:
        cat = category.lower()
        cmds = HELP_CATEGORIES[cat]
        rows = "".join(
            f"<tr><td>{_code(cmd)}</td><td>{desc}</td></tr>"
            for cmd, desc in cmds
        )
        table = f"<table><tbody>{rows}</tbody></table>"
        return f"{skull_header(f'Murphy Commands — {cat.title()}')}<br/>{table}"

    # Full help
    sections: list[str] = [skull_header("Murphy Matrix Bot — All Commands")]
    for cat, cmds in HELP_CATEGORIES.items():
        rows = "".join(
            f"<tr><td>{_code(cmd)}</td><td>{desc}</td></tr>"
            for cmd, desc in cmds
        )
        sections.append(
            f"<br/>{_bold(cat.upper())}"
            f"<table><tbody>{rows}</tbody></table>"
        )
    return "".join(sections)
