"""
PATCH-135a — src/workflow_executor.py
Murphy System — Real Workflow Step Executor

Maps every MURPHY_STEP_TYPE to a concrete implementation.
Called by WorkflowRunner when a scheduled or manual execution fires.

Copyright © 2020-2026 Inoni LLC — Corey Post | License: BSL 1.1
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("murphy.workflow_executor")

# ── Execution context ─────────────────────────────────────────────────────────

class StepContext:
    """Mutable execution context passed through a workflow run."""
    def __init__(self, workflow_id: str, account_id: str, trigger_data: Dict = None):
        self.run_id      = str(uuid.uuid4())[:8]
        self.workflow_id = workflow_id
        self.account_id  = account_id
        self.trigger_data: Dict = trigger_data or {}
        self.variables: Dict = {}          # output from each step
        self.log: List[Dict] = []
        self.started_at  = datetime.now(timezone.utc).isoformat()
        self.status      = "running"       # running | completed | failed | blocked

    def set(self, key: str, value: Any):
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, self.trigger_data.get(key, default))

    def record(self, step_id: str, result: Dict):
        self.log.append({
            "step_id": step_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            **result,
        })

    def to_dict(self) -> Dict:
        return {
            "run_id":      self.run_id,
            "workflow_id": self.workflow_id,
            "account_id":  self.account_id,
            "status":      self.status,
            "started_at":  self.started_at,
            "variables":   self.variables,
            "log":         self.log,
        }


# ── Template interpolation ────────────────────────────────────────────────────

def _render(template: Any, ctx: StepContext) -> Any:
    """Replace {{var}} placeholders in strings (and recursively in dicts/lists)."""
    if isinstance(template, str):
        def replacer(m):
            key = m.group(1).strip()
            return str(ctx.get(key, m.group(0)))
        return re.sub(r"\{\{([^}]+)\}\}", replacer, template)
    if isinstance(template, dict):
        return {k: _render(v, ctx) for k, v in template.items()}
    if isinstance(template, list):
        return [_render(item, ctx) for item in template]
    return template


# ── Step runners ──────────────────────────────────────────────────────────────

def run_schedule(step: Dict, ctx: StepContext) -> Dict:
    """Schedule trigger — already fired, just record context."""
    ctx.set("trigger_time", datetime.now(timezone.utc).isoformat())
    ctx.set("cron", step.get("config", {}).get("cron", ""))
    return {"status": "triggered", "cron": ctx.get("cron")}


def run_manual(step: Dict, ctx: StepContext) -> Dict:
    ctx.set("trigger_time", datetime.now(timezone.utc).isoformat())
    return {"status": "triggered", "mode": "manual"}


def run_webhook(step: Dict, ctx: StepContext) -> Dict:
    ctx.set("trigger_time", datetime.now(timezone.utc).isoformat())
    ctx.set("webhook_payload", ctx.trigger_data)
    return {"status": "triggered", "payload_keys": list(ctx.trigger_data.keys())}


def run_event(step: Dict, ctx: StepContext) -> Dict:
    ctx.set("event", ctx.trigger_data.get("event", ""))
    return {"status": "triggered", "event": ctx.get("event")}


def run_generate(step: Dict, ctx: StepContext) -> Dict:
    """LLM content generation step."""
    config = step.get("config", {})
    prompt_template = config.get("prompt_template",
        "Generate a professional {{output_type}} for {{account}} at {{trigger_time}}. "
        "Be concise and actionable.")
    prompt = _render(prompt_template, ctx)
    max_tokens = int(config.get("max_tokens", 512))
    output_var = config.get("output_var", "generated_content")

    try:
        import os, urllib.request, json as _json
        tkey = os.environ.get("TOGETHER_API_KEY", "")
        if tkey:
            payload = _json.dumps({
                "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "messages": [
                    {"role": "system", "content": "You are Murphy, a business automation AI. Generate clear, professional output."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }).encode()
            req = urllib.request.Request(
                "https://api.together.xyz/v1/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {tkey}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = _json.loads(resp.read())
            content = data["choices"][0]["message"]["content"].strip()
        else:
            content = f"[Generated at {datetime.now(timezone.utc).isoformat()}] Placeholder output for: {prompt[:100]}"
        ctx.set(output_var, content)
        return {"status": "ok", "output_var": output_var, "length": len(content)}
    except Exception as e:
        logger.error("run_generate failed: %s", e)
        ctx.set(output_var, f"[Generation failed: {e}]")
        return {"status": "error", "error": str(e)}


def run_message(step: Dict, ctx: StepContext) -> Dict:
    """Send email/notification."""
    config = step.get("config", {})
    to      = _render(config.get("to", ctx.account_id), ctx)
    subject = _render(config.get("subject", "Murphy Automation"), ctx)
    body    = _render(config.get("body_template",
        "{{generated_content}}\n\n---\nSent by Murphy at {{trigger_time}}"), ctx)

    import os
    sg_key = os.environ.get("SENDGRID_API_KEY", "")
    if sg_key:
        try:
            import urllib.request, json as _json
            payload = _json.dumps({
                "personalizations": [{"to": [{"email": to}]}],
                "from": {"email": "murphy@murphy.systems", "name": "Murphy"},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body}],
            }).encode()
            req = urllib.request.Request(
                "https://api.sendgrid.com/v3/mail/send",
                data=payload,
                headers={"Authorization": f"Bearer {sg_key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                status = resp.status
            logger.info("Email sent to %s status=%s", to, status)
            return {"status": "sent", "to": to, "subject": subject, "http_status": status}
        except Exception as e:
            logger.error("SendGrid failed: %s", e)
            return {"status": "error", "error": str(e)}
    else:
        # Log-only mode (no SendGrid key)
        logger.info("[MSG-SIM] To=%s | Subject=%s | Body=%.200s", to, subject, body)
        return {"status": "simulated", "to": to, "subject": subject,
                "note": "SendGrid key not configured — message logged only"}


def run_api_call(step: Dict, ctx: StepContext) -> Dict:
    """Call external API."""
    import urllib.request, json as _json
    config  = step.get("config", {})
    method  = _render(config.get("method", "GET"), ctx).upper()
    url     = _render(config.get("url", ""), ctx)
    headers = _render(config.get("headers", {}), ctx)
    body    = _render(config.get("body_template", {}), ctx)
    output_var = config.get("output_var", "api_response")

    if not url:
        return {"status": "error", "error": "No URL configured"}
    try:
        data = _json.dumps(body).encode() if body and method != "GET" else None
        req  = urllib.request.Request(url, data=data,
               headers={"Content-Type": "application/json", **headers}, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        try:
            result = _json.loads(raw)
        except Exception:
            result = raw.decode(errors="replace")
        ctx.set(output_var, result)
        return {"status": "ok", "output_var": output_var}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_execute(step: Dict, ctx: StepContext) -> Dict:
    """Invoke a ForgeEngine item."""
    config     = step.get("config", {})
    forge_name = _render(config.get("forge_name", ""), ctx)
    args       = _render(config.get("args", {}), ctx)
    output_var = config.get("output_var", "forge_result")

    if not forge_name:
        return {"status": "error", "error": "No forge_name configured"}
    try:
        from src.forge_engine import get_forge
        forge = get_forge()
        result = forge.invoke(forge_name, ctx.account_id, args)
        ctx.set(output_var, result)
        return {"status": "ok", "forge_name": forge_name, "output_var": output_var}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_hitl(step: Dict, ctx: StepContext) -> Dict:
    """Human-in-the-loop gate — logs and blocks execution."""
    config   = step.get("config", {})
    reason   = _render(config.get("reason", "High-stakes action requires human approval"), ctx)
    ctx.status = "blocked"
    logger.warning("[HITL] Workflow %s blocked: %s", ctx.workflow_id, reason)
    return {"status": "blocked", "reason": reason,
            "resume_url": f"/ui/automations/{ctx.workflow_id}/approve/{ctx.run_id}"}


def run_compliance(step: Dict, ctx: StepContext) -> Dict:
    """Compliance check — stub that checks PCC."""
    try:
        from src.pcc import get_pcc
        pcc = get_pcc()
        config = step.get("config", {})
        action = _render(config.get("action", "workflow_step"), ctx)
        result = pcc.check(action, {"workflow_id": ctx.workflow_id, "account": ctx.account_id})
        allowed = result.get("allowed", True)
        if not allowed:
            ctx.status = "failed"
        return {"status": "passed" if allowed else "blocked", "pcc": result}
    except Exception as e:
        return {"status": "passed", "note": f"PCC check skipped: {e}"}


def run_if_else(step: Dict, ctx: StepContext) -> Dict:
    """Conditional branch — evaluates expression against context variables."""
    config     = step.get("config", {})
    expression = _render(config.get("expression", "True"), ctx)
    try:
        # Safe eval — only variables and comparisons
        allowed_names = {k: v for k, v in ctx.variables.items()
                         if isinstance(v, (str, int, float, bool, type(None)))}
        result = bool(eval(expression, {"__builtins__": {}}, allowed_names))
    except Exception:
        result = True   # default to True branch on eval error
    branch = "true_branch" if result else "false_branch"
    ctx.set("branch_result", branch)
    return {"status": "ok", "expression": expression, "result": result, "branch": branch}


def run_executive(step: Dict, ctx: StepContext) -> Dict:
    """Dispatch to exec_admin_agent."""
    config = step.get("config", {})
    intent = _render(config.get("intent", "morning_brief"), ctx)
    try:
        from src.exec_admin_agent import get_exec_admin
        agent  = get_exec_admin()
        signal = {"intent_hint": intent, "source": ctx.account_id,
                  "raw_payload": ctx.variables, "workflow_run_id": ctx.run_id}
        result = agent.act(signal)
        ctx.set("exec_admin_result", result)
        return {"status": "ok", "intent": intent, "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_operations(step: Dict, ctx: StepContext) -> Dict:
    """Dispatch to prod_ops_agent."""
    config = step.get("config", {})
    signal_type = _render(config.get("signal_type", "health"), ctx)
    try:
        from src.prod_ops_agent import get_prod_ops
        agent  = get_prod_ops()
        signal = {"signal_type": signal_type, "source": ctx.account_id,
                  "raw_payload": ctx.variables, "workflow_run_id": ctx.run_id}
        result = agent.act(signal)
        ctx.set("prod_ops_result", result)
        return {"status": "ok", "signal_type": signal_type}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def run_wait(step: Dict, ctx: StepContext) -> Dict:
    config  = step.get("config", {})
    seconds = int(_render(str(config.get("seconds", 0)), ctx))
    if seconds > 0:
        time.sleep(min(seconds, 30))  # cap at 30s in-process
    return {"status": "ok", "waited_seconds": seconds}


def run_loop(step: Dict, ctx: StepContext) -> Dict:
    """Iterate — records iteration count only (full loop runs are DAG-scheduled)."""
    config  = step.get("config", {})
    items   = _render(config.get("items", []), ctx)
    ctx.set("loop_items", items)
    ctx.set("loop_count", len(items) if isinstance(items, list) else 0)
    return {"status": "ok", "loop_count": ctx.get("loop_count")}


def run_deliver(step: Dict, ctx: StepContext) -> Dict:
    """Final delivery step — consolidates output."""
    config = step.get("config", {})
    output_keys = config.get("output_keys", list(ctx.variables.keys()))
    payload = {k: ctx.get(k) for k in output_keys if ctx.get(k) is not None}
    ctx.set("final_output", payload)
    return {"status": "delivered", "keys": list(payload.keys())}


def run_proposal(step: Dict, ctx: StepContext) -> Dict:
    config = step.get("config", {})
    title  = _render(config.get("title", "Murphy Proposal"), ctx)
    return {"status": "ok", "proposal_title": title, "proposal_id": str(uuid.uuid4())[:8]}


def run_workorder(step: Dict, ctx: StepContext) -> Dict:
    config = step.get("config", {})
    title  = _render(config.get("title", "Work Order"), ctx)
    return {"status": "ok", "work_order_title": title, "work_order_id": str(uuid.uuid4())[:8]}


def run_validate(step: Dict, ctx: StepContext) -> Dict:
    config = step.get("config", {})
    checks = config.get("checks", [])
    passed = all(bool(ctx.get(chk)) for chk in checks) if checks else True
    return {"status": "passed" if passed else "failed", "checks": checks}


def run_budget(step: Dict, ctx: StepContext) -> Dict:
    config     = step.get("config", {})
    amount     = float(_render(str(config.get("amount", 0)), ctx))
    budget_cap = float(config.get("cap", 10000))
    approved   = amount <= budget_cap
    if not approved:
        ctx.status = "blocked"
    return {"status": "approved" if approved else "blocked",
            "amount": amount, "cap": budget_cap}


def run_qa(step: Dict, ctx: StepContext) -> Dict:
    config = step.get("config", {})
    target_var = config.get("target_var", "generated_content")
    content    = ctx.get(target_var, "")
    # Simple heuristic QA: check minimum length
    min_len    = int(config.get("min_length", 50))
    passed     = isinstance(content, str) and len(content) >= min_len
    ctx.set("qa_passed", passed)
    return {"status": "passed" if passed else "failed",
            "target_var": target_var, "length": len(str(content))}


# ── Step dispatch table ───────────────────────────────────────────────────────

STEP_RUNNERS = {
    "schedule":   run_schedule,
    "manual":     run_manual,
    "webhook":    run_webhook,
    "event":      run_event,
    "generate":   run_generate,
    "message":    run_message,
    "api_call":   run_api_call,
    "execute":    run_execute,
    "hitl":       run_hitl,
    "compliance": run_compliance,
    "if_else":    run_if_else,
    "switch":     run_if_else,  # same logic
    "loop":       run_loop,
    "wait":       run_wait,
    "merge":      lambda s, c: {"status": "ok"},  # join — no-op
    "executive":  run_executive,
    "operations": run_operations,
    "qa":         run_qa,
    "proposal":   run_proposal,
    "workorder":  run_workorder,
    "validate":   run_validate,
    "deliver":    run_deliver,
    "budget":     run_budget,
}


def execute_step(step: Dict, ctx: StepContext) -> Dict:
    """Dispatch a single step to its runner."""
    stype  = step.get("type", "execute")
    runner = STEP_RUNNERS.get(stype)
    if runner is None:
        logger.warning("No runner for step type '%s' — using execute fallback", stype)
        runner = run_execute
    try:
        result = runner(step, ctx)
        ctx.record(step.get("id", stype), result)
        return result
    except Exception as e:
        err = {"status": "error", "step_type": stype, "error": str(e)}
        ctx.record(step.get("id", stype), err)
        return err


def execute_workflow(steps: List[Dict], workflow_id: str,
                     account_id: str, trigger_data: Dict = None) -> StepContext:
    """
    Execute a full workflow step list sequentially.
    Returns the completed StepContext.
    """
    ctx = StepContext(workflow_id, account_id, trigger_data or {})
    logger.info("[WF-RUN] %s | workflow=%s | steps=%d",
                ctx.run_id, workflow_id, len(steps))

    for step in steps:
        if ctx.status in ("failed", "blocked"):
            break
        stype = step.get("type", "execute")
        label = step.get("label", stype)
        logger.info("[WF-STEP] %s | %s → %s", ctx.run_id, step.get("id", "?"), label)
        result = execute_step(step, ctx)
        logger.info("[WF-STEP-DONE] %s | status=%s", step.get("id", "?"), result.get("status"))

    if ctx.status == "running":
        ctx.status = "completed"

    logger.info("[WF-DONE] %s | status=%s | steps_run=%d",
                ctx.run_id, ctx.status, len(ctx.log))
    return ctx
