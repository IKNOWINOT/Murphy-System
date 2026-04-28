"""
PATCH-137a — src/intent_parser.py
Murphy System — Universal Intent Parser

Converts ANY natural language into:
  - trigger:  {type, expr, label, raw_hint}
  - steps:    [{id, type, label, config, depends_on}]
  - canvas:   {nodes, edges}
  - intent:   {category, confidence, raw}

Handles casual phrasing, business language, developer language,
and everything in between. Used by nl_workflow_engine and automation_request.

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""
from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER INTENT MAP
# Each entry: (regex_pattern, trigger_type, cron_builder_or_None, label_template)
# Patterns are tried IN ORDER — put more specific before generic.
# ─────────────────────────────────────────────────────────────────────────────

_DOW = {
    "sunday": "0", "monday": "1", "tuesday": "2", "wednesday": "3",
    "thursday": "4", "friday": "5", "saturday": "6",
    "sun": "0", "mon": "1", "tue": "2", "wed": "3",
    "thu": "4", "fri": "5", "sat": "6",
}

_MONTH_MAP = {
    "january": "1", "february": "2", "march": "3", "april": "4",
    "may": "5", "june": "6", "july": "7", "august": "8",
    "september": "9", "october": "10", "november": "11", "december": "12",
    "jan": "1", "feb": "2", "mar": "3", "apr": "4",
    "jun": "6", "jul": "7", "aug": "8", "sep": "9", "oct": "10",
    "nov": "11", "dec": "12",
}

def _hour_from_match(h_str: str, m_str: Optional[str], meridiem: Optional[str]) -> Tuple[int, int]:
    h = int(h_str)
    m = int(m_str) if m_str else 0
    mer = (meridiem or "").lower().strip()
    if mer == "pm" and h != 12:
        h += 12
    elif mer == "am" and h == 12:
        h = 0
    return h, m

# Named time shortcuts
_TIME_ALIASES = {
    "midnight":   (0, 0),
    "noon":       (12, 0),
    "morning":    (8, 0),
    "end of day": (17, 0),
    "eod":        (17, 0),
    "close of business": (17, 0),
    "cob":        (17, 0),
    "lunch":      (12, 0),
    "afternoon":  (14, 0),
    "evening":    (18, 0),
    "night":      (20, 0),
    "start of day": (8, 0),
    "sod":        (8, 0),
    "first thing": (8, 0),
    "end of week": (17, 0),   # handled separately as Friday
    "weekly":     (9, 0),
    "beginning of month": (9, 0),
    "end of month": (9, 0),
}

def _resolve_time_alias(desc: str) -> Optional[Tuple[int, int]]:
    d = desc.lower()
    for alias, (h, m) in sorted(_TIME_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in d:
            return h, m
    return None

def _extract_time(desc: str) -> Tuple[int, int]:
    """Extract hour/minute from description, falling back to 9am."""
    d = desc.lower()
    # HH:MM am/pm
    m = re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm)\b', d)
    if m:
        return _hour_from_match(m.group(1), m.group(2), m.group(3))
    # H am/pm
    m = re.search(r'\b(\d{1,2})\s*(am|pm)\b', d)
    if m:
        return _hour_from_match(m.group(1), None, m.group(2))
    # named alias
    alias = _resolve_time_alias(d)
    if alias:
        return alias
    return 9, 0  # default

def _dow_cron(desc: str, default_dow: str = "1") -> str:
    d = desc.lower()
    for word, num in _DOW.items():
        if re.search(r'\b' + word + r'\b', d):
            return num
    return default_dow

# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER CLASSIFIER
# Returns {"type", "expr", "label", "event_hint", "confidence"}
# ─────────────────────────────────────────────────────────────────────────────

# Event/reactive trigger patterns (no schedule — fires when something happens)
_EVENT_TRIGGERS = [
    # Conditional
    r'\bwhen\b', r'\bif\b', r'\bwhenever\b', r'\bonce\b.{0,15}\b(happens|occurs|done|complete)',
    r'\bon\b.{0,10}\b(arrival|receipt|creation|submission|approval|rejection)',
    r'\bafter\b.{0,20}\b(submit|complet|approv|reject|creat|receiv)',
    r'\bupon\b', r'\bas soon as\b',
    # State changes
    r'\boverdue\b', r'\bexpir', r'\blate\b.{0,10}\b(payment|invoice|task)',
    r'\bfails?\b', r'\berror\b', r'\bbreaks?\b', r'\bdown\b',
    r'\bnew\b.{0,15}\b(lead|order|customer|ticket|request|submission|signup|user)',
    r'\b(lead|order|customer|ticket|request|form).{0,10}(comes? in|arrives?|submitted|created)',
    r'\bpayment.{0,20}(received|failed|declined|missed)',
    r'\binvoice.{0,20}(paid|unpaid|overdue|sent)',
    r'\bsomeone.{0,20}(signs? up|submits?|fills?|completes?)',
    r'\b(status|stage).{0,10}changes?\b',
    r'\bthreshold\b', r'\blimit\b.{0,10}(reached|hit|exceeded)',
    r'\bdrops?\s+below\b', r'\bexceeds?\b', r'\bspikes?\b',
    r'\btriggered\b', r'\bfired\b', r'\bactivated\b',
    r'\bwebhook\b', r'\bapi.{0,10}call\b',
    r'\bwatch\b.{0,20}\bfor\b', r'\bmonitor\b.{0,20}\band\b.{0,20}(notify|alert|act)',
    r'\bon\s+each\b', r'\bon\s+every\b.{0,10}(new|incoming|received)',
    r'\breal.?time\b',
]

# Schedule trigger patterns — ordered most→least specific
_SCHEDULE_TRIGGERS = [
    # Every N minutes
    (r'every\s+(\d+)\s+min(?:ute)?s?',
     lambda d, m: {"type": "cron", "expr": f"*/{m.group(1)} * * * *",
                   "label": f"Every {m.group(1)} minutes"}),
    # Every N hours
    (r'every\s+(\d+)\s+hours?',
     lambda d, m: {"type": "cron", "expr": f"0 */{m.group(1)} * * *",
                   "label": f"Every {m.group(1)} hours"}),
    # Every N days
    (r'every\s+(\d+)\s+days?',
     lambda d, m: (lambda h, mn: {"type": "cron", "expr": f"{mn} {h} */{m.group(1)} * *",
                                   "label": f"Every {m.group(1)} days"})(*_extract_time(d))),
    # Twice a day / twice daily
    (r'twice\s+(?:a\s+)?day|twice\s+daily',
     lambda d, m: {"type": "cron", "expr": "0 8,17 * * *", "label": "Twice daily (8am & 5pm)"}),
    # Specific day-of-week with optional time
    (r'every\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday|sun|mon|tue|wed|thu|fri|sat)',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * {_DOW[m.group(1).lower()]}",
          "label": f"Every {m.group(1).title()} at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Weekdays / weekends
    (r'every\s+weekday|weekdays|monday.{0,10}friday|mon.{0,5}fri',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * 1-5",
          "label": f"Weekdays at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    (r'every\s+weekend|weekends?|saturday.{0,10}sunday',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * 0,6",
          "label": f"Weekends at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Weekly (generic, no specific day — default Monday)
    (r'\bweekly\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * {_dow_cron(d, '1')}",
          "label": f"Weekly at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Daily with explicit time
    (r'(?:every\s+day|daily)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * *",
          "label": f"Daily at {h:02d}:{mn:02d}"})(_hour_from_match(m.group(1), m.group(2), m.group(3)))),
    # Daily generic (no specific time — use alias or default)
    (r'\bdaily\b|\bevery\s+day\b|\beach\s+day\b|\bevery\s+morning\b|\bevery\s+night\b|\bevery\s+evening\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * *",
          "label": f"Daily at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Monthly on specific day
    (r'(?:every|each)\s+month\s+on\s+the\s+(\d{1,2})(?:st|nd|rd|th)?',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} {m.group(1)} * *",
          "label": f"Monthly on the {m.group(1)}"})(*_extract_time(d))),
    # First/last of month
    (r'(?:first|1st)\s+of\s+(?:each|every|the)?\s*month|beginning\s+of\s+(?:each|every|the)?\s*month',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} 1 * *",
          "label": "1st of each month"})(*_extract_time(d))),
    (r'(?:last\s+day|end)\s+of\s+(?:each|every|the)?\s*month',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} 28-31 * *",
          "label": "End of each month"})(*_extract_time(d))),
    # Monthly generic
    (r'\bmonthly\b|\bevery\s+month\b|\beach\s+month\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} 1 * *",
          "label": f"Monthly (1st) at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Hourly
    (r'\bhourly\b|\bevery\s+hour\b',
     lambda d, m: {"type": "cron", "expr": "0 * * * *", "label": "Every hour"}),
    # Quarterly
    (r'\bquarterly\b|\bevery\s+quarter\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} 1 1,4,7,10 *",
          "label": "Quarterly (1st of Jan, Apr, Jul, Oct)"})(*_extract_time(d))),
    # Annually / yearly
    (r'\bannually\b|\byearly\b|\bevery\s+year\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} 1 1 *",
          "label": "Annually (Jan 1st)"})(*_extract_time(d))),
    # Remind / reminder → treat as schedule
    (r'\bremind\s+me\b|\breminder\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * *",
          "label": f"Daily reminder at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Check / run / do this / make sure → schedule
    (r'\bcheck\s+(?:every|each)\b|\brun\s+(?:every|each)\b',
     lambda d, m: (lambda h, mn:
         {"type": "cron", "expr": f"{mn} {h} * * *",
          "label": f"Daily at {h:02d}:{mn:02d}"})(*_extract_time(d))),
]


def classify_trigger(description: str) -> Dict:
    """
    Classify the trigger intent from ANY natural language description.
    Returns trigger dict: {type, expr, label, event_hint, confidence}
    """
    d = description.lower().strip()

    # 1. Try scheduled patterns first (more specific)
    for pattern, builder in _SCHEDULE_TRIGGERS:
        m = re.search(pattern, d)
        if m:
            result = builder(d, m)
            return {**result, "event_hint": None, "confidence": 0.90}

    # 2. Try event/reactive patterns
    for pattern in _EVENT_TRIGGERS:
        if re.search(pattern, d):
            hint = _extract_event_hint(d)
            return {
                "type":       "event",
                "expr":       None,
                "label":      f"Event: {hint}",
                "event_hint": hint,
                "confidence": 0.80,
            }

    # 3. Fallback: on_demand (manual)
    return {
        "type":       "on_demand",
        "expr":       None,
        "label":      "Manual / on demand",
        "event_hint": None,
        "confidence": 0.50,
    }


def _extract_event_hint(desc: str) -> str:
    d = desc.lower()
    # Try to grab the condition clause
    for kw in ["when ", "if ", "whenever ", "once ", "after ", "upon ", "as soon as "]:
        idx = d.find(kw)
        if idx >= 0:
            snippet = d[idx + len(kw):idx + len(kw) + 70]
            # Stop at natural breakpoints
            for stop in [" then ", " do ", " send ", " notify ", " auto", " —", ","]:
                si = snippet.find(stop)
                if si > 5:
                    snippet = snippet[:si]
            return snippet.strip()
    # Fallback: take first meaningful clause
    return d[:60].split(".")[0].strip()


# ─────────────────────────────────────────────────────────────────────────────
# STEP CLASSIFIER
# Maps NL keywords → workflow step types
# ─────────────────────────────────────────────────────────────────────────────

# (regex, step_type, label, icon, estimate_hours)
_STEP_PATTERNS = [
    # Communication
    (r'send.{0,20}email|email.{0,20}(to|the|ceo|team|manager|admin|client|customer)',
     "send_email",   "Send email",             "📧", 0.1),
    (r'notify|notification|alert',
     "notify",       "Send notification",      "🔔", 0.05),
    (r'slack|message.{0,10}(team|channel)|post.{0,10}slack',
     "send_slack",   "Send Slack message",     "💬", 0.05),
    (r'sms|text\s+message',
     "send_sms",     "Send SMS",               "📱", 0.05),
    (r'webhook',
     "webhook",      "Call webhook",           "🔗", 0.1),
    (r'push\s+notification',
     "push_notify",  "Push notification",      "📲", 0.05),

    # Data operations
    (r'fetch|pull|collect|gather|retrieve|get\s+data|import\s+data',
     "fetch_data",   "Fetch data",             "🌐", 0.2),
    (r'summar|digest|brief|recap|overview',
     "summarize",    "Summarize",              "🧠", 0.3),
    (r'generat.{0,20}report|creat.{0,20}report|build.{0,20}report',
     "generate_report","Generate report",      "📈", 0.5),
    (r'analyz|analys',
     "analyze",      "Analyze data",           "🔍", 0.5),
    (r'log|record\s+in|track\s+in',
     "log_record",   "Log record",             "📝", 0.1),
    (r'update.{0,20}(record|crm|db|database|spreadsheet|sheet)',
     "update_record","Update record",          "✏️",  0.15),
    (r'crm|salesforce|hubspot|zoho',
     "crm_update",   "Update CRM",             "📊", 0.2),
    (r'create.{0,20}(record|entry|row|ticket|task)',
     "create_record","Create record",          "➕", 0.1),
    (r'delete|remove\s+old|archive\s+old|clean\s+up',
     "delete_record","Archive / clean up",     "🗑️",  0.1),
    (r'sync|synchroniz',
     "sync",         "Sync data",              "🔄", 0.3),
    (r'export|download\s+data',
     "export_data",  "Export data",            "📤", 0.2),
    (r'import|upload\s+data',
     "import_data",  "Import data",            "📥", 0.2),

    # Process / logic
    (r'escalat|escalat\s+to',
     "escalate",     "Escalate",               "🚨", 0.2),
    (r'approv|approval|review\s+and\s+approv',
     "approval_gate","Wait for approval",      "✅", 0.5),
    (r'assign|route\s+to|hand\s+off',
     "assign",       "Assign / route",         "👤", 0.1),
    (r'validat|verif|check\s+if',
     "validate",     "Validate",               "🔎", 0.2),
    (r'wait\s+\d+|pause|delay\s+\d+',
     "wait",         "Wait / delay",           "⏳", 0.0),
    (r'if.{0,20}then|conditionally|based\s+on',
     "if_else",      "Conditional logic",      "🔀", 0.15),
    (r'loop|for\s+each|iterate',
     "loop",         "Loop / iterate",         "🔁", 0.2),

    # Finance / payments
    (r'payment|charge|bill|invoice\s+the|stripe|paypal',
     "payment_action","Process payment",       "💳", 0.3),
    (r'invoice|invoic',
     "fetch_data",   "Fetch invoice data",     "🧾", 0.2),
    (r'refund',
     "payment_action","Process refund",        "💸", 0.3),
    (r'revenue|earnings|profit',
     "fetch_data",   "Fetch financial data",   "💰", 0.2),

    # AI / generation
    (r'write|draft|compos',
     "generate_text","Generate text / draft",  "✍️",  0.5),
    (r'translat',
     "translate",    "Translate content",      "🌍", 0.3),
    (r'classif|categoriz|tag',
     "classify",     "Classify / tag",         "🏷️",  0.2),

    # Infrastructure
    (r'restart|reboot|deploy',
     "run_command",  "Run command / deploy",   "⚙️",  0.3),
    (r'backup',
     "backup",       "Backup data",            "💾", 0.3),
    (r'monitor|watch\s+for|check\s+status',
     "monitor",      "Monitor / health check", "👁️",  0.1),
    (r'api\s+call|call\s+api|call\s+the\s+api|http\s+request',
     "api_call",     "Make API call",          "🌐", 0.2),
]


def classify_steps(description: str, trigger: Dict) -> List[Dict]:
    """
    Extract workflow steps from natural language.
    Always starts with the trigger node, then infers action steps.
    """
    d     = description.lower()
    steps = []

    # ── Step 0: Trigger node ─────────────────────────────────────────────────
    ttype = trigger.get("type", "on_demand")
    if ttype == "cron":
        steps.append(_make_step("step_00_trigger", "schedule",
                                f"⏰ Schedule: {trigger.get('label', 'On schedule')}",
                                {"cron": trigger.get("expr")}, []))
    elif ttype == "event":
        steps.append(_make_step("step_00_trigger", "event_trigger",
                                f"⚡ Event: {trigger.get('event_hint', 'Trigger condition')}",
                                {"event": trigger.get("event_hint", "")}, []))
    else:
        steps.append(_make_step("step_00_trigger", "manual",
                                "👆 Manual trigger", {}, []))

    # ── Steps 1+: Action steps ────────────────────────────────────────────────
    seen      = set()
    prev_id   = "step_00_trigger"

    for pattern, stype, label, icon, _ in _STEP_PATTERNS:
        if stype not in seen and re.search(pattern, d):
            step_id = f"step_{len(steps):02d}_{stype}"
            steps.append(_make_step(step_id, stype, f"{icon} {label}",
                                    {"auto": True}, [prev_id]))
            seen.add(stype)
            prev_id = step_id

    # ── Always end with output/done ───────────────────────────────────────────
    if len(steps) > 1:
        steps.append(_make_step("step_final", "output",
                                "✔️ Complete & log result", {}, [prev_id]))

    return steps


def _make_step(step_id: str, stype: str, label: str,
               config: Dict, depends_on: List[str]) -> Dict:
    return {
        "id":         step_id,
        "type":       stype,
        "label":      label,
        "config":     config,
        "depends_on": depends_on,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CANVAS BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_canvas(steps: List[Dict]) -> Dict:
    """Convert steps list → canvas {nodes, edges} for the UI."""
    nodes = []
    edges = []
    x = 120

    for step in steps:
        ntype = "trigger" if step["type"] in ("schedule", "event_trigger", "manual") else (
                "output"  if step["type"] == "output" else "action")
        nodes.append({
            "id":      step["id"],
            "type":    ntype,
            "subtype": step["type"],
            "label":   step["label"],
            "x":       x,
            "y":       120,
            "data":    step.get("config", {}),
        })
        x += 240

    for step in steps:
        for dep in step.get("depends_on", []):
            edges.append({
                "id":     f"e_{dep}__{step['id']}",
                "source": dep,
                "target": step["id"],
            })

    return {"nodes": nodes, "edges": edges}


# ─────────────────────────────────────────────────────────────────────────────
# ROI CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

_STEP_HOURS = {s: h for _, s, _, _, h in _STEP_PATTERNS}
_STEP_HOURS.update({"schedule": 0, "event_trigger": 0, "manual": 0.1,
                    "output": 0, "if_else": 0.25, "loop": 0.3})

_FREQ_MAP = {
    "cron":      None,  # calculated from expr
    "event":     52,    # ~weekly events estimate
    "on_demand": 12,    # ~monthly
}

def calc_roi(steps: List[Dict], trigger: Dict) -> Dict:
    human_hrs = sum(_STEP_HOURS.get(s["type"], 0.3) for s in steps)
    human_usd = round(human_hrs * 75, 2)
    agent_usd = round(len(steps) * 0.08, 2)
    savings   = round(human_usd - agent_usd, 2)
    ratio     = round(human_usd / max(agent_usd, 0.01), 1)

    # Estimate annual frequency
    expr = trigger.get("expr")
    if expr:
        parts = expr.split()
        if len(parts) == 5:
            _, _, day, month, dow = parts
            if dow not in ("*",) and day == "*":
                freq = 52   # weekly
            elif day == "*" and month == "*":
                freq = 365  # daily
            elif "," in month or month != "*":
                freq = 4    # quarterly
            elif day != "*":
                freq = 12   # monthly
            else:
                freq = 365
        else:
            freq = 52
    else:
        freq = _FREQ_MAP.get(trigger.get("type", "on_demand"), 12)

    return {
        "human_hours":         round(human_hrs, 2),
        "human_cost_usd":      human_usd,
        "agent_cost_usd":      agent_usd,
        "savings_usd":         savings,
        "roi_ratio":           ratio,
        "annual_savings_usd":  round(savings * freq, 0),
        "frequency_per_year":  freq,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRIMARY ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_intent(description: str) -> Dict:
    """
    Parse ANY natural language description into a complete workflow intent.

    Returns:
    {
        "trigger":  {type, expr, label, event_hint, confidence},
        "steps":    [{id, type, label, config, depends_on}, ...],
        "canvas":   {nodes, edges},
        "roi":      {human_cost_usd, savings_usd, roi_ratio, annual_savings_usd, ...},
        "meta":     {confidence, step_count, trigger_type, strategy},
    }
    """
    trigger = classify_trigger(description)
    steps   = classify_steps(description, trigger)
    canvas  = build_canvas(steps)
    roi     = calc_roi(steps, trigger)

    return {
        "trigger": trigger,
        "steps":   steps,
        "canvas":  canvas,
        "roi":     roi,
        "meta": {
            "confidence":    trigger.get("confidence", 0.5),
            "step_count":    len(steps),
            "trigger_type":  trigger["type"],
            "strategy":      "intent_parser_v1",
        },
    }
