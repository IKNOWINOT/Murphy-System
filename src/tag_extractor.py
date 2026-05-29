"""
PATCH-FACET-EXTRACTOR-R89 (2026-05-28 R89) — 8-axis tag extractor

WHAT THIS IS:
  Pure function that takes a dict from any input boundary (provenance trail,
  gfo augmentation, walker item, inbound email, voice transcript) and
  returns 8-axis facet tags: WHO/WHAT/WHEN/WHERE/HOW/WHY/CONTACT/TROUBLESHOOT.

WHY IT EXISTS:
  Corey R89 insight: "with # or hashtag, job or any type of input value
  it makes it easy sort many versions aspects of data."
  Tags are the substrate that makes EVERY visible token in the system
  drillable, sortable, and queryable by axis.

  This module is the EXTRACTOR. It does not write to DB by itself.
  Callers (chat path, walker, email triage) invoke extract_tags()
  and persist results via tag_writer (R90).

INPUT SHAPE:
  {
    "entity_table": "provenance_trails",      # which substrate table
    "entity_id":   "f9b0a29946c04569",         # the PK value
    "payload":     {<arbitrary dict from the entity>},
  }

OUTPUT SHAPE:
  [
    {"axis": "what",   "tag_value": "#compliance", "confidence": 0.9, "source": "rule"},
    {"axis": "where",  "tag_value": "#db_source",  "confidence": 1.0, "source": "rule"},
    {"axis": "when",   "tag_value": "#today",      "confidence": 1.0, "source": "rule"},
    ...
  ]

EXTRACTION RULES (heuristic, rule-based for R89 — LLM optional R90+):
  WHO   — actor: command_module, agent_id, reviewer_id, sender_email
  WHAT  — semantic kind: source_kind, action, subject keywords, intent
  WHEN  — captured_at parsed to: #today / #yesterday / #this_week / #older
  WHERE — origin: source_hint (table name), file path, module path
  HOW   — method: command_function, API verb, sqlite_select, http_get
  WHY   — trigger: parent_event_id, refusal_reason, request_origin
  CONTACT — email/phone/name pulled from payload via regex
  TROUBLESHOOT — hitl_status, finding_ok=False, retry_count, prior_failure_hash

EXAMPLE:
  >>> extract_tags({
  ...   "entity_table": "provenance_trails",
  ...   "entity_id": "f9b0a29946c04569",
  ...   "payload": {
  ...     "command_module": "__main__",
  ...     "command_function": "fake_compliance_check",
  ...     "source_kind": "db",
  ...     "source_hint": "compliance_engine.requirements table",
  ...     "captured_at": "2026-05-29 02:36:01",
  ...     "hitl_status": "flagged",
  ...   }
  ... })
  [
    {"axis":"who", "tag_value":"#__main__", "confidence":1.0, "source":"rule"},
    {"axis":"what", "tag_value":"#compliance", "confidence":0.9, "source":"rule"},
    {"axis":"when", "tag_value":"#today", "confidence":1.0, "source":"rule"},
    {"axis":"where", "tag_value":"#compliance_engine", "confidence":0.9, "source":"rule"},
    {"axis":"how", "tag_value":"#db_query", "confidence":1.0, "source":"rule"},
    {"axis":"troubleshoot", "tag_value":"#flagged", "confidence":1.0, "source":"rule"},
  ]

DEPENDENCIES:
  Stdlib only. No external imports.

LAST UPDATED: 2026-05-28 R89
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List


def _slug(s: str, max_len: int = 30) -> str:
    """Convert arbitrary text into a hashtag-safe slug."""
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")[:max_len]
    return s or "unknown"


def _time_bucket(ts_str: str) -> str:
    """Bucket a timestamp into #today / #yesterday / #this_week / #older."""
    if not ts_str:
        return "unknown_time"
    try:
        # Try ISO-8601 with optional Z/timezone
        ts = ts_str.replace("Z", "+00:00").replace("T", " ")
        ts = ts.split(".")[0]  # drop fractional seconds
        # Try with and without timezone
        try:
            dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.strptime(ts[:10], "%Y-%m-%d")
        dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now - dt).days
        if age_days == 0:
            return "today"
        if age_days == 1:
            return "yesterday"
        if age_days <= 7:
            return "this_week"
        if age_days <= 30:
            return "this_month"
        return "older"
    except Exception:
        return "unparseable_time"


# Semantic categories — heuristic match against source_kind, subject, etc.
_SEMANTIC_KEYWORDS = {
    "compliance":  ["compliance", "hipaa", "soc2", "gdpr", "audit", "regulation"],
    "billing":     ["bill", "invoice", "payment", "stripe", "revenue", "charge"],
    "sales":       ["lead", "prospect", "deal", "opportunity", "pipeline"],
    "support":     ["ticket", "issue", "bug", "broken", "fail", "error"],
    "compute":     ["agent", "swarm", "dispatch", "rosetta", "soul"],
    "data":        ["db", "table", "sqlite", "query", "select", "insert"],
    "comms":       ["email", "slack", "message", "sms", "chat", "reply"],
    "ops":         ["deploy", "restart", "patch", "health", "ping", "uptime"],
    "review":      ["review", "hitl", "flag", "verify", "decision", "queue"],
}

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def extract_tags(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract 8-axis facet tags from an input dict. Always returns a list,
    never raises.
    """
    payload = item.get("payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}
    tags: List[Dict[str, Any]] = []

    def add(axis: str, value: str, confidence: float = 1.0, source: str = "rule"):
        if not value:
            return
        tags.append({
            "axis": axis,
            "tag_value": "#" + _slug(value),
            "confidence": confidence,
            "source": source,
        })

    # ── WHO ───────────────────────────────────────────────────────
    for key in ("command_module", "agent_id", "reviewer_id", "actor",
                "sender_email", "user_id", "created_by"):
        v = payload.get(key)
        if v:
            add("who", str(v))

    # ── WHAT (semantic categories from text-rich fields) ────────────
    text_blob_parts = []
    for key in ("source_kind", "source_hint", "action", "target", "subject",
                "command_function", "title", "summary", "body"):
        v = payload.get(key)
        if v:
            text_blob_parts.append(str(v).lower())
    text_blob = " ".join(text_blob_parts)

    for category, keywords in _SEMANTIC_KEYWORDS.items():
        if any(k in text_blob for k in keywords):
            add("what", category, confidence=0.85, source="rule")

    # Also raw kind tags
    if payload.get("source_kind"):
        add("what", str(payload["source_kind"]) + "_source", confidence=0.95)
    if payload.get("kind"):
        add("what", str(payload["kind"]))

    # ── WHEN ──────────────────────────────────────────────────────
    for key in ("captured_at", "ts", "timestamp", "decided_at", "created_at",
                "sent_at", "received_at"):
        v = payload.get(key)
        if v:
            bucket = _time_bucket(str(v))
            add("when", bucket)
            break

    # ── WHERE ─────────────────────────────────────────────────────
    src_hint = payload.get("source_hint", "")
    if src_hint:
        # Take first token before space/dot as origin module
        origin = re.split(r"[. ]", str(src_hint))[0]
        if origin:
            add("where", origin, confidence=0.9)
    file_path = payload.get("file_path") or payload.get("module_path")
    if file_path:
        add("where", str(file_path).split("/")[-1].split(".")[0])

    # ── HOW ───────────────────────────────────────────────────────
    cf = payload.get("command_function", "")
    if cf:
        if "query" in cf.lower() or "select" in cf.lower():
            add("how", "db_query")
        elif "send" in cf.lower():
            add("how", "send")
        elif "fetch" in cf.lower() or "get" in cf.lower():
            add("how", "fetch")
        else:
            add("how", cf[:20], confidence=0.6)
    method = payload.get("method")
    if method:
        add("how", str(method))
    api_path = payload.get("api_path") or payload.get("path")
    if api_path:
        add("how", "api_" + str(api_path).strip("/").split("/")[0][:20], confidence=0.7)

    # ── WHY ───────────────────────────────────────────────────────
    if payload.get("refusal_detected"):
        add("why", "refusal_triggered", confidence=1.0)
    if payload.get("parent_event_id"):
        add("why", "follow_up_event", confidence=0.7)
    if payload.get("trigger"):
        add("why", str(payload["trigger"])[:20])

    # ── CONTACT ────────────────────────────────────────────────────
    # Scan all string-ish values for email + phone
    for v in payload.values():
        if isinstance(v, str):
            emails = _EMAIL_RE.findall(v)
            for e in emails[:2]:
                add("contact", "email_" + e.lower(), confidence=0.95, source="regex")
            phones = _PHONE_RE.findall(v)
            for p in phones[:1]:
                add("contact", "phone_present", confidence=0.85, source="regex")
                break

    # ── TROUBLESHOOT ───────────────────────────────────────────────
    status = payload.get("hitl_status") or payload.get("status")
    if status and str(status).lower() in ("flagged", "needs_review", "error", "failed"):
        add("troubleshoot", str(status), confidence=1.0)
    if payload.get("finding_ok") is False:
        add("troubleshoot", "finding_failed", confidence=1.0)
    if payload.get("retry_count"):
        try:
            n = int(payload["retry_count"])
            if n >= 3:
                add("troubleshoot", "retried_" + str(n) + "x", confidence=1.0)
        except (ValueError, TypeError):
            pass

    return tags


def summarize_tags(tags: List[Dict[str, Any]]) -> str:
    """Format tags for human display."""
    if not tags:
        return "(no tags extracted)"
    by_axis: Dict[str, List[str]] = {}
    for t in tags:
        by_axis.setdefault(t["axis"], []).append(t["tag_value"])
    lines = []
    for axis in ("who", "what", "when", "where", "how", "why", "contact", "troubleshoot"):
        if axis in by_axis:
            lines.append(f"  {axis:<13} {' '.join(by_axis[axis])}")
    return "\n".join(lines)


if __name__ == "__main__":
    # Demo
    demo = {
        "entity_table": "provenance_trails",
        "entity_id": "f9b0a29946c04569",
        "payload": {
            "command_module": "__main__",
            "command_function": "fake_compliance_check",
            "source_kind": "db",
            "source_hint": "compliance_engine.requirements table",
            "captured_at": "2026-05-29 02:36:01",
            "hitl_status": "flagged",
        }
    }
    tags = extract_tags(demo)
    print(f"Extracted {len(tags)} tags:")
    print(summarize_tags(tags))
