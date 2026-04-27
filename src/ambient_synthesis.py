"""
Ambient Synthesis Service — LLM-powered insight generation
Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post | License: BSL 1.1

Generates real insights from context signals using the Murphy LLM controller.
Falls back to template-based synthesis if LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from typing import Any, Dict, List, Optional

from murphy_identity import MURPHY_SYSTEM_IDENTITY

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_import_llm_controller():
    """Lazily import LLMController; return None if unavailable."""
    try:
        from src.llm_controller import LLMController, LLMRequest  # noqa: F401

        return LLMController, LLMRequest
    except Exception:
        try:
            from llm_controller import LLMController, LLMRequest  # noqa: F401

            return LLMController, LLMRequest
        except Exception as exc:
            logger.debug("LLMController not available: %s", exc)
            return None, None


def _llm_available() -> bool:
    """Return True when at least one LLM backend key is configured."""
    return bool(
        os.environ.get("DEEPINFRA_API_KEY")
        or os.environ.get("TOGETHER_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("MURPHY_LLM_ENDPOINT")
    )


# ---------------------------------------------------------------------------
# Signal grouping
# ---------------------------------------------------------------------------


def _group_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Group a flat list of context signals by type for synthesis."""
    grouped: Dict[str, Any] = {}
    for sig in signals:
        sig_type = sig.get("type", "unknown")
        grouped.setdefault(sig_type, []).append(sig)
    return grouped


def _avg_confidence(sigs: List[Dict[str, Any]]) -> float:
    """Return average confidence of a list of signals, or 0.0 if empty."""
    if not sigs:
        return 0.0
    total = sum(float(s.get("confidence", 70)) for s in sigs)
    return total / len(sigs)


# ---------------------------------------------------------------------------
# Template-based synthesis (fallback)
# ---------------------------------------------------------------------------


def _template_insights(
    grouped: Dict[str, List[Dict[str, Any]]],
    min_confidence: float = 65.0,
) -> List[Dict[str, Any]]:
    """
    Reproduce the client-side template patterns server-side so that the
    fallback path matches what `murphy_ambient.js` would produce locally.
    """
    insights: List[Dict[str, Any]] = []
    now_ms = int(time.time() * 1000)

    upcoming = grouped.get("upcoming_meeting", [])
    pending_votes = grouped.get("pending_votes", [])
    overdue = grouped.get("overdue", [])
    unassigned = grouped.get("unassigned", [])
    org_milestone = grouped.get("org_milestone", [])
    post_meeting = grouped.get("post_meeting", [])

    # Pre-meeting brief
    if upcoming:
        meeting = upcoming[0]
        meeting_title = (meeting.get("data") or {}).get("title") or "Upcoming Meeting"
        overdue_count = (overdue[0].get("data") or {}).get("count", 0) if overdue else 0
        vote_count = (pending_votes[0].get("data") or {}).get("count", 0) if pending_votes else 0
        body = (
            "Murphy has prepared a brief for your meeting"
            + (f" including {overdue_count} overdue action item(s)" if overdue_count else "")
            + (f" and {vote_count} draft(s) pending your vote" if vote_count else "")
            + "."
        )
        raw_conf = (meeting.get("confidence", 88) + 70) / 2
        conf = max(min_confidence, min(99, math.floor(raw_conf)))
        if conf >= min_confidence:
            insights.append(
                {
                    "id": f"pre-meeting-{now_ms}",
                    "type": "preparation",
                    "title": f"Pre-Meeting Brief: {meeting_title}",
                    "body": body,
                    "confidence": conf,
                    "priority": "high",
                    "trigger": meeting.get("label", ""),
                    "deliverVia": ["ui", "email"],
                    "agents": ["Murphy-Ambient", "Shadow-Calendar"],
                    "source": "client",
                }
            )

    # Risk alert — unassigned + overdue together
    if unassigned and overdue:
        overdue_count = (overdue[0].get("data") or {}).get("count", 0)
        unassigned_count = (unassigned[0].get("data") or {}).get("count", 0)
        conf = 91
        if conf >= min_confidence:
            insights.append(
                {
                    "id": f"risk-alert-{now_ms}",
                    "type": "alert",
                    "title": "Risk Alert: Unassigned + Overdue Tasks",
                    "body": (
                        f"{overdue_count} overdue and {unassigned_count} unassigned tasks detected. "
                        "Murphy has drafted a responsibility matrix."
                    ),
                    "confidence": conf,
                    "priority": "high",
                    "trigger": "Task board analysis",
                    "deliverVia": ["ui", "email"],
                    "agents": ["Murphy-Ambient"],
                    "source": "client",
                }
            )

    # Org milestone
    if org_milestone:
        milestone = org_milestone[0]
        sessions = (milestone.get("data") or {}).get("sessions", 0)
        conf = 95
        if conf >= min_confidence:
            insights.append(
                {
                    "id": f"org-milestone-{now_ms}",
                    "type": "synthesis",
                    "title": f"Org Intelligence Milestone: {sessions} Sessions",
                    "body": (
                        f"Your organisation has completed {sessions} Shadow AI sessions. "
                        "A capability report has been generated."
                    ),
                    "confidence": conf,
                    "priority": "low",
                    "trigger": milestone.get("label", ""),
                    "deliverVia": ["ui"],
                    "agents": ["Murphy-OrgIntel"],
                    "source": "client",
                }
            )

    # Post-meeting summary
    if post_meeting:
        meeting = post_meeting[0]
        meeting_title = (meeting.get("data") or {}).get("title") or "Recent Meeting"
        raw_conf = meeting.get("confidence", 75)
        conf = max(min_confidence, min(99, math.floor(raw_conf)))
        if conf >= min_confidence:
            insights.append(
                {
                    "id": f"post-meeting-{now_ms}",
                    "type": "briefing",
                    "title": f"Post-Meeting Summary: {meeting_title}",
                    "body": (
                        f"Murphy has prepared a post-meeting summary for '{meeting_title}'. "
                        "Action items and key decisions have been captured."
                    ),
                    "confidence": conf,
                    "priority": "medium",
                    "trigger": meeting.get("label", ""),
                    "deliverVia": ["ui", "email"],
                    "agents": ["Murphy-Ambient", "Shadow-Calendar"],
                    "source": "client",
                }
            )

    return insights


# ---------------------------------------------------------------------------
# LLM-powered synthesis
# ---------------------------------------------------------------------------


async def _llm_insight(
    context_summary: str,
    insight_type: str,
    signals: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Ask the LLM controller to generate a single natural-language insight.
    Returns an insight dict or None if generation fails.
    """
    LLMController, LLMRequest = _try_import_llm_controller()
    if LLMController is None or LLMRequest is None:
        return None

    try:
        controller = LLMController()
        prompt = (
            f"{MURPHY_SYSTEM_IDENTITY} "
            "Based on the following context signals, write a concise, actionable insight "
            f"of type '{insight_type}'. "
            "Reply with only a JSON object with keys: title (str), body (str), confidence (int 0-100). "
            "Be direct, professional, and specific.\n\n"
            f"Context signals:\n{context_summary}"
        )
        request = LLMRequest(
            prompt=prompt,
            temperature=0.4,
            max_tokens=300,
        )
        response = await controller.query_llm(request)
        content = response.content.strip()

        # Parse JSON from LLM output
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None
        data = json.loads(json_match.group())
        title = str(data.get("title", "")).strip()
        body = str(data.get("body", "")).strip()
        raw_conf = data.get("confidence", response.confidence * 100)
        try:
            conf = max(0, min(100, int(float(raw_conf))))
        except (ValueError, TypeError):
            conf = int(response.confidence * 100)

        if not title or not body:
            return None

        return {
            "id": f"llm-{insight_type}-{int(time.time() * 1000)}",
            "type": insight_type,
            "title": title,
            "body": body,
            "confidence": conf,
            "priority": "high" if insight_type in ("preparation", "alert") else "medium",
            "deliverVia": ["ui", "email"],
            "agents": ["Murphy-Ambient", "Murphy-LLM"],
            "source": "server",
        }
    except Exception as exc:
        logger.debug("LLM insight generation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def synthesize(
    signals: List[Dict[str, Any]],
    min_confidence: float = 65.0,
) -> List[Dict[str, Any]]:
    """
    Generate insights from a list of context signals.

    If the LLM is available, generate natural-language insights with real
    confidence scores. Otherwise fall back to template-based synthesis.

    Parameters
    ----------
    signals:
        List of signal dicts as produced by ``ContextCollector`` in
        ``murphy_ambient.js``. Each dict should have at minimum:
        ``type``, ``source``, ``confidence``, ``label``, ``data``.
    min_confidence:
        Minimum confidence threshold; insights below this are excluded.

    Returns
    -------
    List of insight dicts compatible with ``murphy_ambient.js``'s expected
    insight structure. Server-generated insights include ``source: 'server'``;
    template-based insights include ``source: 'client'``.
    """
    grouped = _group_signals(signals)

    if not _llm_available():
        logger.debug("Ambient synthesis: LLM not available, using template fallback")
        return _template_insights(grouped, min_confidence)

    # Build a natural-language summary of all signals for the LLM
    signal_lines = [
        f"- [{s.get('source','?')}] {s.get('type','?')}: {s.get('label','')} (confidence {s.get('confidence',0)}%)"
        for s in signals
    ]
    context_summary = "\n".join(signal_lines) if signal_lines else "(no signals)"

    llm_insights: List[Dict[str, Any]] = []

    try:
        # Determine which insight types to generate based on present signal types
        has_upcoming = bool(grouped.get("upcoming_meeting"))
        has_risk = bool(grouped.get("overdue") and grouped.get("unassigned"))
        has_milestone = bool(grouped.get("org_milestone"))
        has_post = bool(grouped.get("post_meeting"))

        if has_upcoming:
            insight = await _llm_insight(context_summary, "preparation", signals)
            if insight and insight["confidence"] >= min_confidence:
                llm_insights.append(insight)

        if has_risk:
            insight = await _llm_insight(context_summary, "alert", signals)
            if insight and insight["confidence"] >= min_confidence:
                llm_insights.append(insight)

        if has_milestone:
            insight = await _llm_insight(context_summary, "synthesis", signals)
            if insight and insight["confidence"] >= min_confidence:
                llm_insights.append(insight)

        if has_post:
            insight = await _llm_insight(context_summary, "briefing", signals)
            if insight and insight["confidence"] >= min_confidence:
                llm_insights.append(insight)

    except Exception as exc:
        logger.warning("Ambient synthesis LLM path failed, falling back: %s", exc)
        return _template_insights(grouped, min_confidence)

    if llm_insights:
        return llm_insights

    # LLM produced nothing useful — fall back to templates
    logger.debug("Ambient synthesis: LLM returned no usable insights, using template fallback")
    return _template_insights(grouped, min_confidence)


# ── PATCH-072f: Public synthesize() API ─────────────────────────────────────

def synthesize(
    signals: List[Dict[str, Any]],
    min_confidence: float = 60.0,
    use_llm: bool = True,
) -> List[Dict[str, Any]]:
    """PATCH-072h: Public synthesize() using LLMController.query_llm."""
    import re as _re
    # PATCH-077c: RSC — report signal volume as entropy proxy
    try:
        from src.rsc_unified_sink import push as _rsc_push
        _rsc_push("ambient_synthesis", contradictions=max(0.0, len(signals) - 10) / 10.0)
    except Exception:
        pass

    if not signals:
        return []

    grouped = _group_signals(signals)

    if use_llm and _llm_available():
        try:
            # PATCH-107c: Drop LLMController async tangle — call get_llm() directly.
            # get_llm().complete() is synchronous; no asyncio bridge needed.
            from src.llm_provider import get_llm as _get_llm
            _provider = _get_llm()
            _parts = [
                "You are Murphy, an AI operating system.",
                "Analyse these ambient context signals and return ONLY a JSON array.",
                "No markdown, no explanation — just the raw JSON array.",
                "Each element: id (string), title (string), summary (string),",
                "confidence (0-1 float), category (perf/business/infra/risk),",
                "priority (high/medium/low), source (always 'server').",
                "Signals:",
                json.dumps(grouped, default=str)[:2000],
            ]
            prompt = " ".join(_parts)
            completion = _provider.complete(
                user=prompt,
                max_tokens=600,
                temperature=0.4,
            )
            raw = getattr(completion, "content", "") or ""
            match = _re.search(r"\[.*?\]", raw, _re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list) and parsed:
                    logger.info("PATCH-107c: LLM synthesized %d insights", len(parsed))
                    _feed_insights_to_lcm(parsed)  # PATCH-075: Ambient → LCM
                    return parsed
        except Exception as _exc:
            logger.warning("PATCH-072h: LLM synthesis failed, using template: %s", _exc)

    _fallback = _template_insights(grouped, min_confidence=min_confidence)
    _feed_insights_to_lcm(_fallback)  # PATCH-075: Ambient → LCM (template path)
    return _fallback


def _feed_insights_to_lcm(insights: List[Dict[str, Any]]) -> None:
    """PATCH-075: Automatically feed high-confidence Ambient insights into LCM.

    Only feeds insights with confidence >= 0.75 to avoid noisy signals.
    Runs in a background thread so it never blocks synthesis.
    """
    import threading as _threading

    def _feed():
        try:
            import urllib.request as _req
            import json as _json
            high_conf = [i for i in insights if float(i.get("confidence", 0)) >= 0.75]
            for insight in high_conf[:5]:  # cap at 5 per synthesis run
                payload = _json.dumps({
                    "source": "ambient_synthesis",
                    "type": insight.get("category", "signal"),
                    "value": f"{insight.get('title','')}: {insight.get('summary','')}",
                    "confidence": float(insight.get("confidence", 0.8)),
                }).encode()
                r = _req.Request(
                    "http://127.0.0.1:8000/api/lcm/signal",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with _req.urlopen(r, timeout=15) as resp:
                    result = _json.loads(resp.read())
                    if result.get("ok"):
                        lcm_data = result.get("data", {})
                        # If LCM auto-dispatched, create a Management AI board item
                        if lcm_data.get("executed") and not lcm_data.get("hitl_required"):
                            _create_mgmt_board_item(insight, lcm_data)
                        elif lcm_data.get("hitl_required"):
                            logger.info("PATCH-075: LCM HITL required for insight: %s", insight.get("title"))
        except Exception as exc:
            logger.debug("PATCH-075: LCM feed error (non-critical): %s", exc)

    _threading.Thread(target=_feed, daemon=True).start()


def _create_mgmt_board_item(insight: Dict[str, Any], lcm_result: Dict[str, Any]) -> None:
    """PATCH-075: Create a Management AI board item from a dispatched LCM result."""
    try:
        import urllib.request as _req
        import json as _json
        # Ensure a board exists — reuse existing one, never duplicate
        # First check if 'Ambient AI Actions' board already exists
        try:
            with _req.urlopen(
                _req.Request("http://127.0.0.1:8000/api/mgmt/boards",
                             headers={"Cookie": "murphy_session=internal"}),
                timeout=5,
            ) as _br:
                _existing = _json.loads(_br.read())
                _boards = _existing if isinstance(_existing, list) else _existing.get("boards", [])
                _ambient_board = next((b for b in _boards if b.get("name") == "Ambient AI Actions"), None)
                if _ambient_board:
                    board_id = _ambient_board.get("board_id") or _ambient_board.get("id") or "default"
                    logger.debug("PATCH-089: Reusing existing board %s", board_id)
                    # skip straight to item creation
                    board_id_found = True
                else:
                    board_id_found = False
        except Exception:
            board_id_found = False

        if not board_id_found:
            board_payload = _json.dumps({
                "name": "Ambient AI Actions",
            "description": "Auto-generated from Ambient AI → LCM dispatch pipeline"
        }).encode()
        board_req = _req.Request(
            "http://127.0.0.1:8000/api/mgmt/boards",
            data=board_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _req.urlopen(board_req, timeout=8) as br:
            board = _json.loads(br.read())
            board_id = board.get("board_id") or board.get("id") or "default"
            board_id_found = True  # just created it

        item_payload = _json.dumps({
            "title": insight.get("title", "Ambient Action"),
            "description": (
                    insight.get("summary", "") + "\n\nLCM run_id: " + str(lcm_result.get("run_id", "?"))
                ),
            "priority": insight.get("priority", "medium"),
            "source": "ambient_lcm_pipeline",
            "confidence": insight.get("confidence", 0.8),
        }).encode()
        item_req = _req.Request(
            f"http://127.0.0.1:8000/api/mgmt/boards/{board_id}/items",
            data=item_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _req.urlopen(item_req, timeout=8) as ir:
            logger.info("PATCH-075: Board item created: %s", insight.get("title"))
    except Exception as exc:
        logger.debug("PATCH-075: Board item creation error (non-critical): %s", exc)

