#!/usr/bin/env python3
"""
Murphy Conductor v0.0.2 — plan + execute (read-only by default)

Stage 1 (R6): grep → ground → ask Murphy for a PLAN
Stage 2 (R11, NEW): ask Murphy for ONE concrete endpoint+payload, then call it
                    — only GET requests by default (read-only)
                    — POST requires explicit allow_write=True
                    — every call logged through PSM
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import threading

# --- config ---
MURPHY_HOST = os.environ.get("MURPHY_HOST", "http://127.0.0.1:8000")
CHATV2_HOST = os.environ.get("CHATV2_HOST", "http://127.0.0.1:8084")
MURPHY_API_KEY = os.environ.get("MURPHY_API_KEY", "")
MURPHY_OPERATOR_TOKEN = os.environ.get("MURPHY_PLATFORM_OPERATOR_TOKEN", "")
TIMEOUT_S = 60

# R509: throttle — 60rpm monolith limit, stay at 30rpm
_LAST_CALL_TS = 0.0
_THROTTLE_LOCK = threading.Lock()
_MIN_INTERVAL_S = 2.0


def _throttle():
    global _LAST_CALL_TS
    with _THROTTLE_LOCK:
        now = time.time()
        wait = _MIN_INTERVAL_S - (now - _LAST_CALL_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_CALL_TS = time.time()


def _post(url: str, body: Dict[str, Any], extra_headers: Dict[str, str] = None) -> Dict[str, Any]:
    _throttle()
    headers = {"Content-Type": "application/json", "X-API-Key": MURPHY_API_KEY}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())


def _get(url: str, extra_headers: Dict[str, str] = None) -> Dict[str, Any]:
    _throttle()
    headers = {"X-API-Key": MURPHY_API_KEY}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())


# --- core capabilities ---

def murphy_grep(pattern: str, scope: str = "py") -> List[Dict[str, Any]]:
    from urllib.parse import quote
    data = _get(f"{MURPHY_HOST}/api/self/grep?pattern={quote(pattern)}&scope={scope}")
    return data.get("matches", [])


def murphy_read(file_path: str) -> str:
    from urllib.parse import quote
    data = _get(f"{MURPHY_HOST}/api/self/read?file={quote(file_path)}")
    return data.get("source", "")



def tool_search(query: str) -> List[Dict[str, Any]]:
    """Query Murphy's tool registry for real endpoints matching a concept."""
    from urllib.parse import quote
    try:
        data = _get(f"{MURPHY_HOST}/api/tools/search?q={quote(query)}")
        return data.get("results", [])
    except Exception:
        return []




# R27: 429 circuit breaker
_429_breaker = {"hits": [], "window_sec": 300, "threshold": 3}

def _record_429():
    import time
    now = time.time()
    _429_breaker["hits"] = [t for t in _429_breaker["hits"] if now - t < _429_breaker["window_sec"]]
    _429_breaker["hits"].append(now)

def _is_429_tripped() -> bool:
    import time
    now = time.time()
    _429_breaker["hits"] = [t for t in _429_breaker["hits"] if now - t < _429_breaker["window_sec"]]
    return len(_429_breaker["hits"]) >= _429_breaker["threshold"]

def rosetta_dispatch(role: str, task: str, input_ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a multi-agent job through Rosetta. Returns DAG id + assigned agents."""
    body = {"role": role, "task": task, "input": input_ctx}
    try:
        return _post(f"{MURPHY_HOST}/api/rosetta/dispatch", body)
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"http_{e.code}", "body": e.read().decode()[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def hitl_review_psm(job_id: str, method: str, path: str, payload: Any, ask: str) -> Optional[int]:
    """File a PSM hitl_review proposal — the audit chain IS the HITL surface."""
    try:
        resp = psm_propose(
            proposal_id=f"hitl_review_{job_id}",
            justification=(
                f"HITL_REVIEW from conductor. "
                f"Ask: {ask[:200]} | Plan: {method} {path} | "
                f"Payload: {json.dumps(payload)[:300]} | "
                f"NOT EXECUTED. Approver: respond to this PSM seq to authorize."
            ),
        )
        return resp.get("ledger_seq")
    except Exception:
        return None

def _ask_murphy_inner(prompt: str, force_provider: str = "deepinfra") -> Dict[str, Any]:
    body = {"message": prompt, "force_provider": force_provider}
    return _post(f"{CHATV2_HOST}/api/chat-v2", body)


def psm_propose(proposal_id: str, justification: str, operator_id: str = "cyborg@agent") -> Dict[str, Any]:
    body = {
        "proposal_id": proposal_id,
        "operator_id": operator_id,
        "justification": justification,
    }
    return _post(
        f"{MURPHY_HOST}/api/platform/self-modification/launch",
        body,
        extra_headers={"X-Murphy-Platform-Operator": MURPHY_OPERATOR_TOKEN},
    )


def murphy_call(method: str, path: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
    """Make a call to a Murphy endpoint based on Murphy's plan."""
    url = f"{MURPHY_HOST}{path}"
    try:
        if method.upper() == "GET":
            return {"ok": True, "data": _get(url)}
        elif method.upper() == "POST":
            return {"ok": True, "data": _post(url, payload or {})}
        else:
            return {"ok": False, "error": f"unsupported_method:{method}"}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"http_{e.code}", "body": e.read().decode()[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# --- conductor logic ---

@dataclass
class ConductorJob:
    job_id: str
    ask: str
    operator_id: str
    started_at: float
    psm_seq: Optional[int] = None
    murphy_plan: Optional[str] = None
    murphy_reply: Optional[str] = None
    grep_context: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    execution_endpoint: Optional[Dict[str, str]] = None
    execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def conduct(ask: str, operator_id: str = "corey@founder", allow_write: bool = False) -> ConductorJob:
    """
    Stage 1: plan (grep + ask Murphy)
    Stage 2: execute (ask Murphy for ONE concrete call, run it)

    allow_write: if False (default), only GET calls are executed.
                 if True, POST is allowed. Use for actions you've already approved.
    """
    job_id = f"conductor_{int(time.time())}_{os.urandom(3).hex()}"
    job = ConductorJob(
        job_id=job_id,
        ask=ask,
        operator_id=operator_id,
        started_at=time.time(),
    )

    # 1. File ask in PSM
    try:
        psm = psm_propose(
            proposal_id=job_id,
            justification=f"Conductor ask from {operator_id}: {ask[:400]}",
            operator_id=operator_id,
        )
        job.psm_seq = psm.get("ledger_seq")
    except Exception as e:
        job.error = f"psm_failed: {e}"
        return job

    # 2. Concept-keyword extraction
    extract_prompt = (
        f"From this ask, list 1-5 concept keywords (NOT names of companies or people). "
        f"Concept keywords are technical/capability words like 'invoice', 'paperwork', "
        f"'onboarding', 'agent', 'scheduler'. Reply with ONLY a JSON array, nothing else. "
        f"Ask: \"{ask}\""
    )
    try:
        ex = ask_murphy(extract_prompt)
        reply = (ex.get("reply") or "").strip()
        m = re.search(r"\[.*?\]", reply, re.DOTALL)
        if m:
            job.keywords = [str(k).strip().strip("'\"") for k in json.loads(m.group(0))]
            job.keywords = [k for k in job.keywords if k and len(k) > 2]
    except Exception:
        pass
    if not job.keywords:
        job.keywords = [w for w in ask.lower().split() if len(w) > 4 and w.isalpha()]

    # 3. Grep
    seen = set()
    for kw in job.keywords[:5]:
        try:
            for hit in murphy_grep(kw, scope="py")[:5]:
                key = (hit.get("file"), hit.get("line"))
                if key not in seen:
                    seen.add(key)
                    job.grep_context.append(hit)
        except Exception:
            continue
    job.grep_context = job.grep_context[:15]

    # 4. Stage 1: ask Murphy for a plan
    grep_summary = "\n".join(
        f"  {m['file']}:{m['line']}  {m['text'][:90]}"
        for m in job.grep_context
    ) or "  (no grep matches)"

    plan_prompt = f"""Murphy — Corey just asked: "{ask}"

I used /api/self/grep with concept keywords {job.keywords[:5]!r} and found:

{grep_summary}

In 2-3 short sentences: what's the smallest first step that delivers real progress?
If no relevant code exists, say so plainly."""

    try:
        plan_resp = ask_murphy(plan_prompt)
        job.murphy_plan = plan_resp.get("reply", "(empty)")
    except Exception as e:
        job.error = f"plan_failed: {e}"
        return job

    # 5. Stage 2 (R12 NEW): query tool registry for REAL endpoints, then
    #     ask Murphy to PICK from the real list (instead of inventing).
    tools_found: List[Dict[str, Any]] = []
    seen_tool_ids = set()
    for kw in job.keywords[:5]:
        for t in tool_search(kw)[:5]:
            tid = t.get("tool_id")
            if tid and tid not in seen_tool_ids:
                seen_tool_ids.add(tid)
                tools_found.append(t)
    tools_found = tools_found[:12]

    if not tools_found:
        job.execution_endpoint = {"method": "NONE", "reason": "no_real_tools_match_concepts"}
        job.execution_result = {"skipped": True, "reason": "no_tools_in_registry_for_concepts"}
        return job

    tools_summary = "\n".join(
        f"  - {t.get('method')} {t.get('path')} — {t.get('description', '')[:80]}"
        for t in tools_found
    )

    execute_prompt = f"""Based on your plan above, PICK ONE endpoint from this REAL list of registered tools:

{tools_summary}

Reply with ONLY a JSON object containing the EXACT method+path from above:
{{
  "method": "GET" or "POST",
  "path": "/api/... (must be exactly from the list above)",
  "payload": {{}} or null,
  "reason": "one sentence why this is the right call"
}}

If none of these tools applies, reply {{"method":"NONE","reason":"why"}}

Your plan was:
{job.murphy_plan[:400]}"""

    try:
        ex_resp = ask_murphy(execute_prompt)
        job.murphy_reply = ex_resp.get("reply", "")
        # Extract JSON object from reply
        # Find first balanced { ... } block
        plan = None
        text = job.murphy_reply
        for start in range(len(text)):
            if text[start] != "{":
                continue
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if esc:
                    esc = False
                    continue
                if ch == "\\":
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            plan = json.loads(candidate)
                            break
                        except Exception:
                            break
            if plan:
                break
        if plan:
            job.execution_endpoint = plan
            method = (plan.get("method") or "").upper()
            path = plan.get("path", "")
            payload = plan.get("payload")

            # 6. Execute (with safety gate)
            if method == "NONE":
                job.execution_result = {"skipped": True, "reason": "murphy_said_none"}
            elif method == "GET" and path.startswith("/api/"):
                job.execution_result = murphy_call("GET", path)
            elif method == "POST" and path.startswith("/api/"):
                # R15: POSTs are NEVER executed inline. Always go through HITL.
                hitl_seq = hitl_review_psm(job.job_id, method, path, payload, ask)
                job.execution_result = {
                    "skipped": True,
                    "reason": "post_routed_to_hitl",
                    "hitl_psm_seq": hitl_seq,
                    "would_have_called": {"method": method, "path": path, "payload": payload}
                }
            else:
                job.execution_result = {"skipped": True, "reason": f"unsafe_or_invalid:{method}_{path}"}
    except Exception as e:
        job.error = f"execute_stage_failed: {str(e)[:200]}"

    return job


# --- CLI for testing ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: conductor.py <ask> [--write]", file=sys.stderr)
        sys.exit(1)
    allow_write = "--write" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--write"]
    ask = " ".join(args)
    j = conduct(ask, allow_write=allow_write)
    print(json.dumps({
        "job_id": j.job_id,
        "ask": j.ask,
        "psm_seq": j.psm_seq,
        "concepts": j.keywords[:5],
        "grep_hits": len(j.grep_context),
        "plan": (j.murphy_plan or "")[:400],
        "endpoint": j.execution_endpoint,
        "result": (
            {"ok": j.execution_result.get("ok"), "skipped": j.execution_result.get("skipped"),
             "reason": j.execution_result.get("reason"),
             "data_preview": str(j.execution_result.get("data", ""))[:400]}
            if j.execution_result else None
        ),
        "error": j.error,
        "elapsed_sec": round(time.time() - j.started_at, 2),
    }, indent=2))


def ask_murphy(prompt: str) -> Dict[str, Any]:
    """Wrapper: records 429s for circuit breaker."""
    if _is_429_tripped():
        return {"reply": "(429 breaker tripped; skipping Murphy plan)", "provider": "breaker", "_breaker": True}
    try:
        return _ask_murphy_inner(prompt)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            _record_429()
        raise

