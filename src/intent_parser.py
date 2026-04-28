"""
PATCH-137d — src/intent_parser.py
Murphy System — Universal Intent Parser v2

Maps ANY natural language → trigger + steps using ALL workflow builder node types:
  Triggers:    schedule, event, webhook, manual
  Actions:     api_call, execute, message, generate
  Logic:       if_else, switch, loop, wait, merge
  Agents:      executive, operations, qa
  Gates:       hitl, compliance, budget
  Production:  proposal, workorder, validate, deliver

The goal: if someone says it in any form — casual, technical, business, vague —
we figure out what they mean and build a real workflow. No jargon required.

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_DOW = {
    "sunday":"0","monday":"1","tuesday":"2","wednesday":"3",
    "thursday":"4","friday":"5","saturday":"6",
    "sun":"0","mon":"1","tue":"2","wed":"3","thu":"4","fri":"5","sat":"6",
}

# Named time → (hour, minute)
_TIME_NAMES = {
    "midnight":(0,0), "noon":(12,0), "lunch":(12,0),
    "morning":(8,0), "first thing":(8,0), "start of day":(8,0), "sod":(8,0),
    "afternoon":(14,0), "evening":(18,0), "night":(20,0),
    "end of day":(17,0), "eod":(17,0),
    "close of business":(17,0), "cob":(17,0),
    "end of week":(17,0), "end of business":(17,0),
}

def _extract_time(desc: str) -> Tuple[int,int]:
    d = desc.lower()
    # HH:MM am/pm
    m = re.search(r'\b(\d{1,2}):(\d{2})\s*(am|pm)\b', d)
    if m:
        return _hm(m.group(1), m.group(2), m.group(3))
    # H am/pm
    m = re.search(r'\b(\d{1,2})\s*(am|pm)\b', d)
    if m:
        return _hm(m.group(1), None, m.group(2))
    # Named time
    for name,(h,mn) in sorted(_TIME_NAMES.items(), key=lambda x:-len(x[0])):
        if name in d:
            return h,mn
    return 9,0  # default: 9am

def _hm(h_s, m_s, mer) -> Tuple[int,int]:
    h = int(h_s); mn = int(m_s or 0)
    mer = (mer or "").lower()
    if mer=="pm" and h!=12: h+=12
    elif mer=="am" and h==12: h=0
    return h,mn

def _dow_from_desc(desc: str, default="1") -> str:
    d = desc.lower()
    for word,num in _DOW.items():
        if re.search(r'\b'+word+r'\b', d):
            return num
    return default

# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that mean "fire when something happens" (event/reactive)
_EVENT_SIGNALS = [
    r'\bwhen\b', r'\bwhenever\b', r'\bif\b', r'\bas soon as\b', r'\bupon\b',
    r'\bonce\b.{0,15}(done|complete|happens|occurs|submitted|approved)',
    r'\bafter\b.{0,25}(submit|complet|approv|reject|receiv|creat)',
    r'\bon\b.{0,5}(receipt|arrival|submission|approval|rejection|creation)\b',
    r'\boverdue\b', r'\bexpir', r'\blate\s+payment\b', r'\bpast\s+due\b',
    r'\bnew\b.{0,20}(lead|order|customer|ticket|request|signup|user|submission|form)',
    r'\b(lead|order|ticket|form|request|customer).{0,15}(comes?\s+in|arrives?|submitted|created|received)',
    r'\bsomeone\b.{0,20}(signs?\s*up|submits?|fills?\s+out|completes?)',
    r'\bpayment.{0,20}(fail|declin|miss|receiv)',
    r'\binvoice.{0,20}(paid|unpaid|overdue|rejected)',
    r'\bstatus.{0,15}changes?\b', r'\bstage\s+changes?\b',
    r'\b(threshold|limit).{0,10}(hit|reached|exceeded)\b',
    r'\bdrops?\s+below\b', r'\bexceeds?\b', r'\bspikes?\b', r'\bfalls?\s+below\b',
    r'\bwebhook\b', r'\breal.?time\b',
    r'\bwatch\s+for\b', r'\bdetect\b', r'\bon\s+each\s+new\b',
    r'\bwhen\s+(?:a\s+)?(?:new\s+)?\w+\s+is\s+created\b',
    r'\btriggered\s+by\b', r'\bin\s+response\s+to\b',
    r'\bfails?\b.{0,20}(check|test|build|deploy)',
    r'\berror\s+(occurs?|detected|found)\b',
    r'\balert.{0,10}(if|when|on)\b',
]

# Ordered schedule patterns — most specific first
_SCHEDULE_PATTERNS = [
    # Every N minutes
    (r'every\s+(\d+)\s+min(?:ute)?s?',
     lambda d,m: {"type":"cron","expr":f"*/{m.group(1)} * * * *","label":f"Every {m.group(1)} min"}),
    # Every N hours
    (r'every\s+(\d+)\s+hours?',
     lambda d,m: {"type":"cron","expr":f"0 */{m.group(1)} * * *","label":f"Every {m.group(1)} hours"}),
    # Every N days
    (r'every\s+(\d+)\s+days?',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} */{m.group(1)} * *","label":f"Every {m.group(1)} days"})(*_extract_time(d))),
    # Twice daily
    (r'twice\s+(?:a\s+)?day|twice\s+daily|two\s+times\s+(?:a\s+)?day',
     lambda d,m: {"type":"cron","expr":"0 8,17 * * *","label":"Twice daily (8am & 5pm)"}),
    # Specific day of week
    (r'every\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday|sun|mon|tue|wed|thu|fri|sat)\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * {_DOW[m.group(1).lower()]}","label":f"Every {m.group(1).title()} at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Weekdays
    (r'every\s+weekday|weekdays\b|monday.{0,10}(?:through|to|-)\s*friday|mon.{0,5}fri',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * 1-5","label":f"Weekdays at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Weekends
    (r'every\s+weekend|weekends?\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * 0,6","label":f"Weekends at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Weekly (generic)
    (r'\bweekly\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * {_dow_from_desc(d,'1')}","label":f"Weekly at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Daily + explicit time
    (r'(?:every\s+day|daily|each\s+day)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * *","label":f"Daily at {h:02d}:{mn:02d}"})(_hm(m.group(1),m.group(2),m.group(3)))),
    # Daily aliases
    (r'\bdaily\b|\bnightly\b|\bevery\s+(?:single\s+)?day\b|\beach\s+day\b|\bevery\s+morning\b|\bevery\s+night\b|\bevery\s+evening\b|\bmorning\b|\beach\s+morning\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * *","label":f"Daily at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Remind me (implies daily unless DOW found)
    (r'\bremind\s+(?:me\b|the\s+team\b|everyone\b)',
     lambda d,m: (lambda h,mn: {"type":"cron",
        "expr":f"{mn} {h} * * {_dow_from_desc(d,'*')}",
        "label":f"Reminder at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # First of month / beginning of month
    (r'(?:first|1st)\s+of\s+(?:each|every|the)?\s*month|beginning\s+of\s+(?:each|every|the)?\s*month',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} 1 * *","label":"1st of each month"})(*_extract_time(d))),
    # End of month
    (r'(?:last\s+day|end)\s+of\s+(?:each|every|the)?\s*month',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} 28-31 * *","label":"End of each month"})(*_extract_time(d))),
    # Nth of month
    (r'(?:every|each)\s+month\s+on\s+the\s+(\d{1,2})(?:st|nd|rd|th)?',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} {m.group(1)} * *","label":f"Monthly on the {m.group(1)}"})(*_extract_time(d))),
    # Monthly generic
    (r'\bmonthly\b|\bevery\s+month\b|\beach\s+month\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} 1 * *","label":f"Monthly (1st) at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # Quarterly / each quarter / end of quarter
    (r'\bquarterly\b|\bevery\s+quarter\b|\beach\s+quarter\b|end\s+of\s+(?:each\s+|every\s+|the\s+)?quarter',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} 1 1,4,7,10 *","label":"Quarterly"})(*_extract_time(d))),
    # Annually / yearly
    (r'\bannually\b|\byearly\b|\bevery\s+year\b|\beach\s+year\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} 1 1 *","label":"Annually (Jan 1st)"})(*_extract_time(d))),
    # Hourly
    (r'\bhourly\b|\bevery\s+hour\b',
     lambda d,m: {"type":"cron","expr":"0 * * * *","label":"Every hour"}),
    # "Run / check / do this every ..."
    (r'(?:run|check|do\s+this|make\s+sure)\s+every\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * *","label":f"Daily at {h:02d}:{mn:02d}"})(*_extract_time(d))),
    # "at midnight / at noon / at 9am" with no frequency = daily
    (r'\bat\s+(?:midnight|noon|morning|(\d{1,2})(?::(\d{2}))?\s*(?:am|pm))\b',
     lambda d,m: (lambda h,mn: {"type":"cron","expr":f"{mn} {h} * * *","label":f"Daily at {h:02d}:{mn:02d}"})(*_extract_time(d))),
]


def classify_trigger(description: str) -> Dict:
    """Parse NL → trigger dict with type, expr, label, confidence."""
    d = description.lower().strip()

    # Reactive-lead guard: if sentence starts with conditional/event word → always event
    # (prevents schedule patterns from incorrectly matching "quarterly" in "if X drops by Q")
    if re.match(r'^(if|when|whenever|as\s+soon\s+as|upon|after|once)\b', d):
        hint = _extract_event_hint(d)
        return {"type":"event","expr":None,"label":f"Event: {hint}",
                "event_hint":hint,"confidence":0.88}

    # Schedule patterns (time-based recurrence)
    for pattern, builder in _SCHEDULE_PATTERNS:
        m = re.search(pattern, d)
        if m:
            result = builder(d, m)
            return {**result, "event_hint": None, "confidence": 0.90}

    # Event/reactive signals (condition-based)
    for sig in _EVENT_SIGNALS:
        if re.search(sig, d):
            hint = _extract_event_hint(d)
            return {"type":"event","expr":None,"label":f"Event: {hint}",
                    "event_hint":hint,"confidence":0.82}

    # Webhook explicit
    if "webhook" in d or "http callback" in d or "api trigger" in d:
        return {"type":"webhook","expr":None,"label":"Webhook trigger",
                "event_hint":None,"confidence":0.95}

    # Fallback
    return {"type":"on_demand","expr":None,"label":"Manual / on demand",
            "event_hint":None,"confidence":0.50}


def _extract_event_hint(desc: str) -> str:
    d = desc.lower()
    for kw in ["when ","whenever ","if ","as soon as ","after ","upon ","once "]:
        idx = d.find(kw)
        if idx >= 0:
            snippet = d[idx+len(kw):idx+len(kw)+70]
            for stop in [" then "," do "," send "," notify "," auto"," —",","," and "]:
                si = snippet.find(stop)
                if si > 4:
                    snippet = snippet[:si]
            return snippet.strip()
    return d[:60].split(".")[0].strip()


# ─────────────────────────────────────────────────────────────────────────────
# STEP CLASSIFICATION — covers ALL builder node types
# (regex, step_type, label, icon, human_hours_per_run)
# ─────────────────────────────────────────────────────────────────────────────

_STEP_RULES = [
    # ── ACTIONS ─────────────────────────────────────────────────────────────

    # message / send_email / send_slack → map to "message" node
    (r'send.{0,25}(?:email|recap|report|summary|brief|update)|email.{0,20}(?:to|the|ceo|board|team|client|manager|accounting|admin|\w+)|notify.{0,10}by.{0,5}email',
     "message",  "Send email",              "📧", 0.15),
    (r'\bslack\b|post.{0,10}(slack|channel)|message.{0,10}(team|channel)',
     "message",  "Send Slack message",      "💬", 0.05),
    (r'\bsms\b|text\s+message|send\s+text',
     "message",  "Send SMS",                "📱", 0.05),
    (r'\bnotif(?:y|ication)\b|\balert\b|\bping\b|\bwarn\b|\bremind(?:er)?s?\b|\bsend\s+(?:a\s+)?remind',
     "message",  "Send notification",       "🔔", 0.05),
    (r'\bpush\s+notification\b',
     "message",  "Push notification",       "📲", 0.05),

    # generate → any AI/LLM content creation or report building
    (r'generat.{0,25}report|creat.{0,15}report|build.{0,15}report|compile.{0,15}(?:report|financials?|data|results?)|how\s+\w+\s+(?:is|are)\s+going|keep\s+(?:me|us)\s+posted|update\s+me\s+on',
     "generate", "Generate report",         "📈", 0.5),
    (r'\bsummar(?:iz|is)|digest\b|brief(?:ing)?\b|recap\b|overview\b',
     "generate", "Summarize / brief",       "🧠", 0.4),
    (r'\bwrit(?:e|ing)\b|\bdraft\b|\bcompos(?:e|ing)\b',
     "generate", "Draft content",           "✍️",  0.5),
    (r'\btranslat\b',
     "generate", "Translate content",       "🌍", 0.3),
    (r'\banalyz|analys\b',
     "generate", "Analyze & generate insight","🔍", 0.5),
    (r'\bforecast\b|\bpredict\b',
     "generate", "Generate forecast",       "🔮", 0.6),
    (r'\bpropose\b|\bsuggestion\b|\brecommend\b',
     "generate", "Generate recommendation", "💡", 0.4),

    # api_call → external services, fetching data, webhooks
    (r'\bfetch\b|\bpull\s+(?:data|from)\b|\bretrieve\b|\bcollect\s+data\b|\bget\s+(?:the\s+)?data\b',
     "api_call", "Fetch data",              "🌐", 0.2),
    (r'\bwebhook\b(?!.*trigger)|\bcall\s+(?:the\s+)?api\b|\bapi\s+call\b|\bhttp\s+request\b',
     "api_call", "Call external API",       "🔗", 0.2),
    (r'\bsync\b|\bsynchroniz\b',
     "api_call", "Sync data",               "🔄", 0.3),
    (r'\bimport\s+(?:data|from)\b|\bingestion\b',
     "api_call", "Import data",             "📥", 0.2),
    (r'\bexport\b|\bdownload\s+data\b',
     "api_call", "Export data",             "📤", 0.2),
    (r'\bcrm\b|\bsalesforce\b|\bhubspot\b|\bzoho\b',
     "api_call", "Update CRM",              "📊", 0.2),
    (r'\bstripe\b|\bpaypal\b|\bcharge\b|\bbill\b(?!.{0,10}board)',
     "api_call", "Process payment",         "💳", 0.3),
    (r'\bspreadsheet\b|\bgoogle\s+sheet\b|\bexcel\b',
     "api_call", "Update spreadsheet",      "📋", 0.2),

    # execute → run scripts, commands, jobs, pipelines
    (r'\brestart\b|\breboot\b',
     "execute",  "Restart service",         "🔁", 0.3),
    (r'\bdeploy\b',
     "execute",  "Deploy",                  "🚀", 0.5),
    (r'\bbackup\b|\bback\s+up\b',
     "execute",  "Backup data",             "💾", 0.3),
    (r'\bclean\s*up\b|\barchive\s+old\b|\bdelete\s+old\b|\bpurge\b',
     "execute",  "Clean up / archive",      "🗑️",  0.2),
    (r'\brun\s+(?:the\s+)?(?:script|job|pipeline|process|task)\b',
     "execute",  "Run task / script",       "⚙️",  0.3),
    (r'\bprocess\s+(?:the\s+)?(?:queue|backlog|batch|orders?)\b',
     "execute",  "Process queue / batch",   "⚙️",  0.4),
    (r'\bmonitor\b|\bhealth\s+check\b|\bping\s+the\s+server\b|\bcheck\s+(?:if|the\s+)?(?:server|site|api|system)\b',
     "execute",  "Monitor / health check",  "👁️",  0.1),
    (r'\blog\s+(?:it|this|the|record|event)\b|\btrack\s+in\b|\brecord\s+in\b',
     "execute",  "Log record",              "📝", 0.1),
    (r'\bupdate\s+(?:the\s+)?(?:record|entry|row|status|field)\b',
     "execute",  "Update record",           "✏️",  0.15),
    (r'\bcreate\s+(?:a\s+)?(?:record|entry|row|ticket|task)\b',
     "execute",  "Create record",           "➕", 0.1),
    (r'\binvoice\b',
     "execute",  "Process invoice",         "🧾", 0.2),
    (r'\bpayment\s+(?:fail|declin|miss)\b|\bfailed\s+payment\b',
     "execute",  "Handle payment failure",  "💸", 0.3),
    (r'\brefund\b',
     "execute",  "Process refund",          "💸", 0.3),
    (r'\bassign\b|\broute\s+to\b|\bhand\s+off\b',
     "execute",  "Assign / route",          "👤", 0.1),
    (r'\bescalat\b',
     "execute",  "Escalate",               "🚨", 0.2),
    (r'\bclassif\b|\bcategoriz\b|\btag\b',
     "execute",  "Classify / tag",          "🏷️",  0.2),
    (r'\bvalidat\b|\bverif\b',
     "execute",  "Validate",               "🔎", 0.2),

    # ── LOGIC ───────────────────────────────────────────────────────────────
    (r'\bif\b.{0,50}\b(then|else|route|otherwise)\b|\bconditionally\b|\bbased\s+on\b|\bdepending\s+on\b|\bif\s+(?:they|it|the)\s+(?:are|is)\b',
     "if_else",    "Conditional check",     "⑂",  0.1),
    (r'\bswitch\b|\bmultiple\s+(?:cases?|paths?|branches?)\b',
     "switch",     "Multi-branch switch",   "🔀", 0.1),
    (r'\bfor\s+each\b|\bloop\b|\biterat\b|\bevery\s+(?:item|record|row|entry)\b',
     "loop",       "Loop / iterate",        "🔄", 0.2),
    (r'\bwait\s+\d+|\bpause\s+for\b|\bdelay\s+\d+|\bafter\s+\d+\s+(?:hour|day|min)',
     "wait",       "Wait / delay",          "⏳", 0.0),
    (r'\bmerge\b|\bjoin\s+(?:the\s+)?(?:results?|branches?|outputs?)\b',
     "merge",      "Merge branches",        "🔗", 0.05),

    # ── AGENTS ──────────────────────────────────────────────────────────────
    (r'\bexecutive\s+agent\b|\bceo\s+agent\b|\bboard\s+level\b|\bstrategic\s+review\b',
     "executive",  "Executive agent",       "👔", 2.0),
    (r'\bops\s+agent\b|\boperations\s+agent\b|\bproduction\s+agent\b',
     "operations", "Operations agent",      "🏭", 1.5),
    (r'\bqa\s+(?:agent|check|review)\b|\bquality\s+(?:agent|check|review)\b',
     "qa",         "QA / review agent",     "🔍", 1.0),

    # ── GATES ───────────────────────────────────────────────────────────────
    (r'\bhuman.{0,10}(?:review|approval|check|sign.?off)\b|\bhitl\b|\bmanual\s+approv\b|\bsomeone\s+(?:needs?\s+to\s+approv|must\s+approv)\b',
     "hitl",       "Human-in-the-loop",     "🙋", 0.5),
    (r'\bapprov(?:e|al)\b|\bapprov\s+(?:this|it|before)\b|\bneeds?\s+approv',
     "hitl",       "Approval gate",         "✅", 0.5),
    (r'\bcompliance\b|\bcompliant\b|\baudit\b|\bregulat\b|\blegal\s+check\b',
     "compliance", "Compliance check",      "📋", 1.0),
    (r'\bbudget\s+(?:approv|check|gate|limit|cap|exceed)\b|\bover\s+budget\b|\bspend\s+limit\b|\bbudget\s+exceed\b|\bexceeds?.{0,10}budget\b|\bif\s+budget\b',
     "budget",     "Budget approval gate",  "💰", 0.5),

    # ── PRODUCTION ──────────────────────────────────────────────────────────
    (r'\bproposal\b|\bwrite\s+(?:a\s+)?proposal\b|\bpropose\s+(?:a\s+)?deal\b|\bsend\s+(?:a\s+)?proposal\b',
     "proposal",   "Create proposal",       "📝", 3.0),
    (r'\bwork\s*order\b|\bservice\s+order\b|\bissue\s+(?:a\s+)?(?:work|job)\s+order\b',
     "workorder",  "Issue work order",      "📄", 2.0),
    (r'\bdeliver(?:y|able)?\b|\bsend\s+(?:it\s+)?to\s+(?:the\s+)?client\b|\bship\b|\bhand\s+over\b',
     "deliver",    "Deliver to client",     "📦", 0.5),
]

# Canonical ordering: gates before logic before agents before actions
# (prevents greedy action patterns from eating gate keywords)
_STEP_PRIORITY = ["hitl","compliance","budget","if_else","switch","loop","wait","merge",
                  "executive","operations","qa","proposal","workorder","deliver",
                  "generate","message","api_call","execute"]


def classify_steps(description: str, trigger: Dict) -> List[Dict]:
    """Map NL → ordered list of workflow steps using all node types."""
    d     = description.lower()
    steps = []

    # ── Trigger node (always first) ──────────────────────────────────────────
    ttype = trigger.get("type","on_demand")
    if ttype == "cron":
        steps.append(_step("step_00_trigger","schedule",
                           f"⏰ {trigger.get('label','Schedule')}",
                           {"cron":trigger.get("expr")}, []))
    elif ttype == "event":
        steps.append(_step("step_00_trigger","event",
                           f"📡 Event: {trigger.get('event_hint','condition')}",
                           {"event":trigger.get("event_hint","")}, []))
    elif ttype == "webhook":
        steps.append(_step("step_00_trigger","webhook",
                           "⚡ Webhook trigger", {}, []))
    else:
        steps.append(_step("step_00_trigger","manual",
                           "👆 Manual / on demand", {}, []))

    # ── Scan description for action/logic/gate/agent nodes ───────────────────
    matched: dict = {}  # step_type → (label, icon, human_hrs)

    for pattern, stype, label, icon, hrs in _STEP_RULES:
        if stype not in matched and re.search(pattern, d):
            matched[stype] = (label, icon, hrs)

    # ── Add steps in priority order ───────────────────────────────────────────
    prev_id = "step_00_trigger"
    added_in_order = []

    # Priority list first
    for stype in _STEP_PRIORITY:
        if stype in matched:
            label, icon, _ = matched[stype]
            sid = f"step_{len(steps):02d}_{stype}"
            steps.append(_step(sid, stype, f"{icon} {label}", {"auto":True}, [prev_id]))
            added_in_order.append(stype)
            prev_id = sid

    # Any remaining matches not in priority list
    for stype,(label,icon,_) in matched.items():
        if stype not in added_in_order:
            sid = f"step_{len(steps):02d}_{stype}"
            steps.append(_step(sid, stype, f"{icon} {label}", {"auto":True}, [prev_id]))
            prev_id = sid

    # ── Output node ───────────────────────────────────────────────────────────
    if len(steps) > 1:
        steps.append(_step("step_final","execute","✔️ Complete & log result",{},[prev_id]))

    return steps


def _step(sid,stype,label,config,depends_on):
    return {"id":sid,"type":stype,"label":label,"config":config,"depends_on":depends_on}


# ─────────────────────────────────────────────────────────────────────────────
# CANVAS BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_canvas(steps: List[Dict]) -> Dict:
    nodes, edges = [], []
    x = 100
    for step in steps:
        ttype = step["type"]
        if ttype in ("schedule","event","webhook","manual"):
            ncat = "trigger"
        elif ttype == "execute" and step["id"] == "step_final":
            ncat = "output"
        elif ttype in ("if_else","switch","loop","wait","merge"):
            ncat = "logic"
        elif ttype in ("hitl","compliance","budget"):
            ncat = "gate"
        elif ttype in ("executive","operations","qa"):
            ncat = "agent"
        elif ttype in ("proposal","workorder","deliver"):
            ncat = "production"
        else:
            ncat = "action"
        nodes.append({"id":step["id"],"type":ncat,"subtype":step["type"],
                      "label":step["label"],"x":x,"y":120,"data":step.get("config",{})})
        x += 240
    for step in steps:
        for dep in step.get("depends_on",[]):
            edges.append({"id":f"e_{dep}__{step['id']}","source":dep,"target":step["id"]})
    return {"nodes":nodes,"edges":edges}


# ─────────────────────────────────────────────────────────────────────────────
# ROI CALCULATOR
# ─────────────────────────────────────────────────────────────────────────────

_STEP_HRS = {r[1]:r[4] for r in _STEP_RULES}
_STEP_HRS.update({"schedule":0,"event":0,"webhook":0,"manual":0.1,"execute":0.3,"output":0})
_FREQ = {"cron":None,"event":52,"webhook":100,"on_demand":12}

def _annual_freq(trigger):
    expr = trigger.get("expr")
    if not expr:
        return _FREQ.get(trigger.get("type","on_demand"),12)
    parts = expr.split()
    if len(parts)!=5: return 52
    mn,hr,day,month,dow = parts
    if "," in month: return 4        # quarterly
    if "/" in mn: return 365*int(mn.split("/")[1]) if mn!="*" else 365*60
    if day!="*" and "-" not in day: return 12   # monthly
    if dow not in ("*","1-5","0,6"): return 52   # weekly
    if dow=="1-5": return 260                     # weekdays
    return 365                                    # daily

def calc_roi(steps, trigger):
    hrs     = sum(_STEP_HRS.get(s["type"],0.3) for s in steps)
    human   = round(hrs * 75, 2)
    agent   = round(len(steps) * 0.08, 2)
    savings = round(human - agent, 2)
    ratio   = round(human / max(agent,0.01), 1)
    freq    = _annual_freq(trigger)
    annual  = round(savings * freq, 0) if freq else round(savings * 365, 0)
    return {"human_hours":round(hrs,2),"human_cost_usd":human,"agent_cost_usd":agent,
            "savings_usd":savings,"roi_ratio":ratio,
            "annual_savings_usd":annual,"frequency_per_year":freq or 365}


# ─────────────────────────────────────────────────────────────────────────────
# PRIMARY ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def parse_intent(description: str) -> Dict:
    """
    Parse any natural language into a complete, executable workflow intent.
    Covers all Murphy workflow builder node types — no jargon required.
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
            "confidence":   trigger.get("confidence",0.5),
            "step_count":   len(steps),
            "trigger_type": trigger["type"],
            "strategy":     "intent_parser_v2",
            "node_types":   list({s["type"] for s in steps}),
        },
    }
