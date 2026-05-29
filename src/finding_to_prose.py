"""
PATCH-LAYER2-001 (2026-05-28 R72) — Finding to prose translator

WHAT THIS IS:
  Takes a finding dict from go_find_out (the bullet-list dump returned by
  augment_reply when Murphy executes a refused query) and composes a natural
  language answer that a real user can act on.

WHY IT EXISTS:
  R71 ships findings like:
      • db: murphy_audit.db
      • table: rosetta_dispatch_log
      • row_count: 2395
  Per Corey's R70 insight, that's a developer dump. A user needs:
      "There are 2,395 rows in rosetta_dispatch_log — records of every
       swarm dispatch. Want me to break that down by agent?"
  Layer 2 closes the translation gap.

HOW IT FITS:
  Called from augment_reply after _log_augmentation_event. The composed prose
  replaces the bullet-list addendum.

PUBLIC SURFACE:
  describe_table(name) -> str        # semantic description if known
  describe_module(name) -> str       # module purpose if known
  compose_prose(finding, question) -> str
    Returns natural-language prose. Falls back to bullet form when the table
    or module isn't in the dictionary (graceful degrade).

EXTENSIONS PLANNED:
  R73 — 5W frame check (what/when/where/how/why context selection)
  R74+ — runtime dictionary via DB table if needed

LAST UPDATED: 2026-05-28 R72
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("finding_to_prose")


# ─── Semantic dictionaries — 12 tables + 10 modules ──────────────────
# Curated from R62/R63/R65/R66/R71 audits — the substrate Murphy customers
# and Corey actually query most.

TABLE_MEANINGS = {
    "rosetta_dispatch_log":  ("records of every swarm dispatch — when an agent picked up a request and what verdict it returned",
                              "Each row is one agent processing one signal."),
    "provenance_trails":     ("records of every command output that the system captured the source of",
                              "Each row links a command result to its underlying database, config, or hardcoded source."),
    "evidence_snapshots":    ("raw captures of the data behind a command output",
                              "Each row is the underlying DB rows, config text, or API response that produced a given result."),
    "hitl_tickets":          ("human-filed review tickets flagging a result as wrong or incomplete",
                              "Each row is one human flagging a specific provenance trail with a correction note."),
    "agent_contracts":       ("the staffing-agency roster of available agents",
                              "Each row is one agent with its domain, fitness score, and rental terms."),
    "chain_revenue_events":  ("billable events from chains where customers used a rented agent",
                              "Each row is a charge that produced a royalty split between platform and tenant."),
    "contacts":              ("the CRM contact list (leads, customers, prospects)",
                              "Each row is one person or company tied to a tenant's sales pipeline."),
    "deals":                 ("open and closed sales opportunities in the CRM",
                              "Each row is one deal with a stage, value, and contact."),
    "tenant_strategies":     ("the strategy document Murphy generated for each tenant",
                              "Each row is a JSON blob with business goals, action plan, and commitments."),
    "tenant_subscriptions":  ("active tenant subscription state",
                              "Each row is a tenant's tier, billing status, and paid-through date."),
    "gfo_augmentations":     ("audit log of every chat refusal Murphy executed against the system",
                              "Each row records what Murphy said it didn't know, what it then went and looked up, and whether that worked."),
    "events":                ("the general system audit event stream",
                              "Each row is a timestamped system event captured for audit and replay."),
}

MODULE_MEANINGS = {
    "go_find_out":           "the parser that turns Murphy refusals into actual queries against the system",
    "hitl_provenance":       "the substrate that records where every command result came from",
    "hitl_prov_adapter":     "the adapter that exposes provenance trails in a review-queue shape",
    "agent_broker":          "the matcher that connects customer requests to the best available agent",
    "compliance_engine":     "the validator that checks deliverables against regulatory frameworks (GDPR, HIPAA, SOC2)",
    "chain_royalty":         "the engine that splits chain revenue between platform and tenant",
    "spec_to_identity":      "the module that absorbs business/design specs into tenant identity",
    "agent_contract_fitness":"the engine that scores agent fitness from observation history",
    "librarian_planner":     "the natural-language router that maps customer questions to system components",
    "murphy_voice":          "the chat reply composer — Murphy's voice to Corey",
}




# ═══════════════════════════════════════════════════════════════════
# PATCH-LAYER3-001 (R73) — 5W frame classifier + follow-up invitations
# Corey R70 insight: answers need WHAT/WHEN/WHERE/HOW/WHY context
# based on question shape, plus a useful next-step suggestion.
# ═══════════════════════════════════════════════════════════════════

import re as _re_r73

# Question-shape classifier — selects emphasis frame
_QUESTION_FRAMES = {
    "count":      _re_r73.compile(r"\b(how many|count|total|number of)\b", _re_r73.I),
    "location":   _re_r73.compile(r"\b(where|location|stored|live[sd]?)\b", _re_r73.I),
    "person":     _re_r73.compile(r"\b(who|which (agent|user|tenant|person))\b", _re_r73.I),
    "causation":  _re_r73.compile(r"\b(why|because|reason|caused)\b", _re_r73.I),
    "time":       _re_r73.compile(r"\b(when|since|until|how (often|long|recent))\b", _re_r73.I),
    "definition": _re_r73.compile(r"\b(what (is|are|does)|explain|describe|meaning of)\b", _re_r73.I),
    "status":     _re_r73.compile(r"\b(is it|are they|does it|working|wired|loaded|live)\b", _re_r73.I),
}


def classify_question(question: str) -> str:
    """Classify question shape. Returns the first matching frame or 'definition'."""
    if not question:
        return "definition"
    for frame, pattern in _QUESTION_FRAMES.items():
        if pattern.search(question):
            return frame
    return "definition"


# Follow-up suggestions tailored per finding type + frame
# PATCH-R75-TEMPLATE-FIX — close R73-noted gap: table_count/time fall-through
_FOLLOWUP_TEMPLATES = {
    # (finding_kind, frame) -> suggestion
    ("table_count", "count"):     "Want me to break that down by agent, by day, or show you the latest few?",
    ("table_count", "time"):      "Want me to see the rate of growth — say, rows added in the last hour?",
    ("table_count", "definition"): "Want me to show you what one of those rows actually looks like?",
    ("table_count", "status"):    "Want me to check whether the writes to this table are still firing organically?",
    ("list_tables", "definition"): "Pick one — say the table name and I'll tell you how many rows it has and what's in them.",
    ("list_tables", "count"):     "Pick a table to count its rows.",
    ("file_check", "status"):     "Want me to see if it's currently imported by anything in the running system?",
    ("file_check", "definition"): "Want me to show you what its public functions look like?",
    ("grep",       "count"):      "Want me to see what those files have in common, or just the top hits?",
    ("grep",       "location"):   "Want me to show you the surrounding context of any specific hit?",
}

_FRAME_PREFIX = {
    "count":      "By the numbers: ",
    "location":   "On location: ",
    "time":       "Timeline: ",
    "status":     "Status: ",
    "person":     "Who's involved: ",
    "causation":  "Why it's like this: ",
    "definition": "",  # plain prose default
}


def _classify_finding(finding):
    """Identify finding type for follow-up selection."""
    if not finding or not finding.get("ok"):
        return "error"
    if "row_count" in finding and "table" in finding:
        return "table_count"
    if finding.get("action") == "list_tables":
        return "list_tables"
    if finding.get("action") == "check_file" or "file" in finding:
        return "file_check"
    if finding.get("action") == "grep":
        return "grep"
    return "other"


def _select_followup(finding_kind: str, frame: str) -> str:
    """Pick the best follow-up suggestion. Falls through to definition frame
    if the frame-specific template isn't defined."""
    if (finding_kind, frame) in _FOLLOWUP_TEMPLATES:
        return _FOLLOWUP_TEMPLATES[(finding_kind, frame)]
    if (finding_kind, "definition") in _FOLLOWUP_TEMPLATES:
        return _FOLLOWUP_TEMPLATES[(finding_kind, "definition")]
    return ""



def describe_table(name: str) -> str:
    """Return a one-sentence semantic description of a table, or empty."""
    if not name:
        return ""
    entry = TABLE_MEANINGS.get(name)
    if entry:
        return entry[0]
    return ""


def describe_module(name: str) -> str:
    """Return a one-sentence semantic description of a module, or empty."""
    if not name:
        return ""
    cleaned = name.replace(".py", "")
    return MODULE_MEANINGS.get(cleaned, "")


def _pluralize(n: int, singular: str, plural: Optional[str] = None) -> str:
    plural = plural or (singular + "s")
    return f"{n:,} {singular if n == 1 else plural}"


def compose_prose(finding: Dict[str, Any], question: str = "") -> str:
    """
    Compose a natural-language answer from a finding dict.
    Returns prose suitable for direct user consumption.
    Falls back to a structured bullet line if no table/module dictionary entry.
    """
    if not finding or not finding.get("ok"):
        # Failure case — be plain about what didn't work
        reason = (finding or {}).get("reason", "unknown reason")
        if "fake_target_guarded" in reason:
            db_name = reason.split(": ")[-1].split(" ")[0] if ": " in reason else "that database"
            return f"I tried but {db_name} doesn't actually exist on this system — looks like the question referenced a database that isn't here."
        if "no_db_in_target" in reason:
            return "I couldn't tell which database you meant from the question — try naming the specific .db file (like murphy_audit.db or hitl_provenance.db)."
        if "no_module_reference" in reason:
            return "I couldn't find a module by that name in /opt/Murphy-System/src/ — the reference may have been ambiguous."
        return f"I tried to look but ran into: {reason}."

    action = finding.get("action", "")

    # ── Table row count ──────────────────────────────────────────
    if "row_count" in finding and "table" in finding:
        n = finding["row_count"]
        table = finding["table"]
        db = finding.get("db", "")
        meaning = describe_table(table)
        rows = _pluralize(n, "row", "rows")
        # R73 — 5W frame + follow-up
        frame = classify_question(question)
        prefix = _FRAME_PREFIX.get(frame, "")
        followup = _select_followup("table_count", frame)
        if meaning:
            base = f"{prefix}there are {rows} in the {table} table — {meaning}. It lives in {db} on this system."
        else:
            base = f"{prefix}there are {rows} in the {table} table (in {db})."
        # Capitalize first letter post-prefix
        if not prefix and base:
            base = base[0].upper() + base[1:]
        return base + (f" {followup}" if followup else "")

    # ── Listing tables in a DB ───────────────────────────────────
    if action == "list_tables":
        tables = finding.get("tables", [])
        db = finding.get("db", "")
        notable = [t for t in tables if t in TABLE_MEANINGS][:3]
        n = len(tables)
        frame = classify_question(question)
        followup = _select_followup("list_tables", frame)
        if notable:
            descriptions = "; ".join(f"{t} ({describe_table(t)[:60]}...)" for t in notable)
            base = (f"The {db} database has {n} tables. The notable ones: {descriptions}.")
        else:
            sample = ", ".join(tables[:5])
            base = f"The {db} database has {n} tables — including {sample}."
        return base + (f" {followup}" if followup else "")

    # ── File check (module inspection) ───────────────────────────
    if action == "check_file" or "file" in finding:
        fname = finding.get("file", "")
        if not finding.get("exists", True):
            tried = finding.get("tried", [fname])
            return f"None of those modules exist in /opt/Murphy-System/src/ — I checked: {', '.join(tried[:3])}."
        meaning = describe_module(fname.replace(".py", ""))
        lines_n = finding.get("lines", 0)
        funcs_n = finding.get("top_level_funcs", 0)
        classes_n = finding.get("classes", 0)
        frame = classify_question(question)
        followup = _select_followup("file_check", frame)
        if meaning:
            base = f"Yes, {fname} is on the system — {meaning}. It's {lines_n:,} lines with {classes_n} classes and {funcs_n} top-level functions."
        else:
            base = f"Yes, {fname} exists ({lines_n:,} lines, {classes_n} classes, {funcs_n} top-level functions)."
        return base + (f" {followup}" if followup else "")

    # ── Grep result ──────────────────────────────────────────────
    if action == "grep":
        term = finding.get("search_term", "")
        n = finding.get("hit_count", 0)
        hits = finding.get("first_hits", [])
        if n == 0:
            return f"I searched for '{term}' across the source tree and found no matches."
        sample = ", ".join(hits[:3])
        frame = classify_question(question)
        followup = _select_followup("grep", frame)
        base = f"I searched for '{term}' and found it in {n:,} {'file' if n == 1 else 'files'} including {sample}."
        return base + (f" {followup}" if followup else "")

    # ── Fallback: structured bullet form ─────────────────────────
    parts = []
    for k, v in finding.items():
        if k in ("ok", "action"):
            continue
        if isinstance(v, list):
            parts.append(f"{k}={len(v)} items")
        else:
            parts.append(f"{k}={v}")
    return "Found: " + "; ".join(parts) + "."


if __name__ == "__main__":
    print("── R72 smoke ──\n")
    cases = [
        {"ok": True, "db": "murphy_audit.db", "table": "rosetta_dispatch_log", "row_count": 2395, "action": "sqlite_query"},
        {"ok": True, "db": "hitl_provenance.db", "table": "provenance_trails", "row_count": 12, "action": "sqlite_query"},
        {"ok": True, "db": "murphy_audit.db", "tables": ["events", "hitl_queue", "gfo_augmentations", "audit_runs", "capacity_snapshots", "rosetta_dispatch_log"], "action": "list_tables"},
        {"ok": True, "file": "hitl_provenance.py", "exists": True, "lines": 340, "classes": 0, "top_level_funcs": 7, "action": "check_file"},
        {"ok": True, "search_term": "compliance_engine", "hit_count": 124, "first_hits": ["compliance_engine.py", "patch407.py", "shield_wall.py"], "action": "grep"},
        {"ok": False, "reason": "fake_target_guarded: logs.db not in /var/lib/murphy-production"},
        {"ok": False, "reason": "no_db_in_target"},
        {"ok": True, "file": "go_find_out.py", "exists": True, "lines": 395, "classes": 0, "top_level_funcs": 15, "action": "check_file"},
    ]
    for i, c in enumerate(cases):
        prose = compose_prose(c, "test question")
        print(f"  Case {i+1}: {prose}")
        print()
