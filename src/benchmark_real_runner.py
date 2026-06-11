"""
benchmark_real_runner.py — actually calls an LLM, actually scores honestly.

Ship 28 (2026-06-10) — replaces the synthetic harness whose outputs 
were misleading. This runner:

  - Connects to Together AI (TOGETHER_API_KEY in vault)
  - Runs the 5 τ-bench-style tasks we already have hand-coded
  - For each task, gives the LLM the multi-turn conversation and asks 
    it to output the next agent action as JSON {action: "...", reasoning: "..."}
  - Compares output to expected_action; scores 0/1
  - Writes results to /documentation/testing/benchmark_real/

This is NOT a τ-bench official submission. It's a real, runnable 
in-house benchmark using a real model. The number it produces is 
defensible because every call is traceable.

For an official τ-bench submission we'll need to:
  1. Clone the actual sierra-research/tau-bench repo
  2. Wire Murphy's agent_executor as the policy
  3. Run their official harness
  4. Submit to the public leaderboard

That's a 4-8h project. This script gets us a real number tonight.
"""
from __future__ import annotations
import json
import os
import time
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ────────────────────────────────────────────────────────────────────────
# Load Together API key from vault
# ────────────────────────────────────────────────────────────────────────

def _load_together_key() -> str:
    """Load TOGETHER_API_KEY from vault. Vault uses Fernet encryption."""
    # Try env first (systemd injects it for the main service)
    env_key = os.environ.get("TOGETHER_API_KEY", "").strip()
    if env_key and env_key.lower() not in ("", "none", "null"):
        return env_key
    
    # Fallback: try the vault module
    try:
        import sys
        sys.path.insert(0, "/opt/Murphy-System")
        sys.path.insert(0, "/opt/Murphy-System/src")
        from src.murphy_vault import get_secret  # type: ignore
        return get_secret("TOGETHER_API_KEY") or ""
    except Exception:
        pass
    
    # Fallback: read secrets.env directly
    try:
        with open("/etc/murphy-production/secrets.env") as f:
            for line in f:
                if line.startswith("TOGETHER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    
    raise RuntimeError("TOGETHER_API_KEY not found in env, vault, or secrets.env")


# ────────────────────────────────────────────────────────────────────────
# LLM call (Together AI - OpenAI-compatible API)
# ────────────────────────────────────────────────────────────────────────

def call_llm(prompt: str, *, model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
             max_tokens: int = 512, timeout: int = 60) -> dict[str, Any]:
    """Call Together AI, return {text, latency_seconds, ok, error}."""
    api_key = _load_together_key()
    url = "https://api.together.xyz/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,  # low-temp for deterministic eval
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) Murphy-Bench/1.0")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"]
        return {"ok": True, "text": text, "latency_seconds": time.time() - t0, "raw": data}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:300]}",
                "latency_seconds": time.time() - t0}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "latency_seconds": time.time() - t0}


# ────────────────────────────────────────────────────────────────────────
# Real τ-bench-style tasks (hand-curated, 10 tasks across 5 domains)
# ────────────────────────────────────────────────────────────────────────

TAU_TASKS: list[dict[str, Any]] = [
    {
        "id": "tau-r-001",
        "domain": "retail",
        "context": "You are a retail customer service agent. The customer's order #12345 contains a defective item.",
        "conversation": [
            {"role": "user", "content": "I need to return my order #12345."},
            {"role": "agent", "content": "I'll look up your order. What's the issue?"},
            {"role": "user", "content": "The item was defective - the screen was cracked."},
        ],
        "expected_action": "initiate_return",
        "valid_synonyms": ["initiate_return", "start_return", "process_return", "create_return"],
    },
    {
        "id": "tau-a-002",
        "domain": "airline",
        "context": "You are an airline booking agent.",
        "conversation": [
            {"role": "user", "content": "I want to change my flight from NYC to LA."},
            {"role": "agent", "content": "When would you like to travel?"},
            {"role": "user", "content": "Next Monday, morning preferred."},
            {"role": "agent", "content": "I found a 9am flight. Confirm?"},
            {"role": "user", "content": "Yes, book the 9am please."},
        ],
        "expected_action": "book_flight",
        "valid_synonyms": ["book_flight", "confirm_booking", "create_booking", "change_flight"],
    },
    {
        "id": "tau-f-003",
        "domain": "finance",
        "context": "You are a banking agent. Verify identity before sensitive actions.",
        "conversation": [
            {"role": "user", "content": "Transfer $5000 to account 987654."},
            {"role": "agent", "content": "I need to verify your identity first. What's your security PIN?"},
            {"role": "user", "content": "My PIN is 1234."},
        ],
        "expected_action": "verify_identity",
        "valid_synonyms": ["verify_identity", "validate_pin", "authenticate", "verify_pin"],
    },
    {
        "id": "tau-it-004",
        "domain": "it_support",
        "context": "You are IT support. Try basic troubleshooting before escalating.",
        "conversation": [
            {"role": "user", "content": "My laptop won't connect to VPN."},
            {"role": "agent", "content": "Have you tried restarting the VPN client?"},
            {"role": "user", "content": "Yes, still not working. Tried twice."},
            {"role": "agent", "content": "Let me check your account."},
            {"role": "user", "content": "It's been 30 minutes, I have a meeting in 5."},
        ],
        "expected_action": "escalate_ticket",
        "valid_synonyms": ["escalate_ticket", "escalate", "create_priority_ticket", "page_oncall"],
    },
    {
        "id": "tau-hr-005",
        "domain": "hr",
        "context": "You are an HR agent. Verify PTO balance before submitting.",
        "conversation": [
            {"role": "user", "content": "I want to request 5 days of PTO starting Monday."},
            {"role": "agent", "content": "Let me check your balance. You have 12 days available. Should I submit?"},
            {"role": "user", "content": "Yes please, submit it."},
        ],
        "expected_action": "submit_pto_request",
        "valid_synonyms": ["submit_pto_request", "create_pto", "submit_time_off", "request_pto"],
    },
    {
        "id": "tau-r-006",
        "domain": "retail",
        "context": "You are a retail agent. Check inventory before promising.",
        "conversation": [
            {"role": "user", "content": "Do you have the iPhone 15 Pro in stock at the downtown store?"},
            {"role": "agent", "content": "Let me check inventory."},
        ],
        "expected_action": "check_inventory",
        "valid_synonyms": ["check_inventory", "lookup_stock", "query_inventory", "check_stock"],
    },
    {
        "id": "tau-a-007",
        "domain": "airline",
        "context": "You are an airline agent. Refund policy requires verification of fare class.",
        "conversation": [
            {"role": "user", "content": "I want a refund for booking ABC123."},
            {"role": "agent", "content": "Let me look that up. What's the reason for the refund?"},
            {"role": "user", "content": "My flight was cancelled by the airline."},
        ],
        "expected_action": "process_refund",
        "valid_synonyms": ["process_refund", "initiate_refund", "issue_refund", "refund_booking"],
    },
    {
        "id": "tau-f-008",
        "domain": "finance",
        "context": "You are a banking agent. Suspicious activity should be flagged.",
        "conversation": [
            {"role": "user", "content": "I see a $2000 charge I didn't make on my card."},
            {"role": "agent", "content": "When did this charge appear?"},
            {"role": "user", "content": "Yesterday, from a country I've never been to."},
        ],
        "expected_action": "freeze_card",
        "valid_synonyms": ["freeze_card", "block_card", "report_fraud", "dispute_charge"],
    },
    {
        "id": "tau-it-009",
        "domain": "it_support",
        "context": "You are IT support. Password resets require identity verification.",
        "conversation": [
            {"role": "user", "content": "I forgot my password."},
            {"role": "agent", "content": "I need to verify your identity. What's your employee ID?"},
            {"role": "user", "content": "EMP12345"},
        ],
        "expected_action": "send_password_reset",
        "valid_synonyms": ["send_password_reset", "reset_password", "initiate_password_reset", "send_reset_link"],
    },
    {
        "id": "tau-hr-010",
        "domain": "hr",
        "context": "You are an HR agent. Onboarding requires multiple steps.",
        "conversation": [
            {"role": "user", "content": "I'm starting on Monday. What do I need to do first?"},
            {"role": "agent", "content": "Welcome! Let me check your onboarding checklist."},
        ],
        "expected_action": "fetch_onboarding_checklist",
        "valid_synonyms": ["fetch_onboarding_checklist", "get_onboarding", "lookup_checklist", "retrieve_onboarding"],
    },
]


# ────────────────────────────────────────────────────────────────────────
# Agent prompt template (this is "Murphy's agent" for the benchmark)
# ────────────────────────────────────────────────────────────────────────

AGENT_PROMPT = """You are an autonomous customer service agent. Based on the conversation, decide the next concrete action to take.

Context: {context}

Conversation so far:
{conversation}

Output ONLY a JSON object with this exact shape:
{{
  "action": "snake_case_action_name",
  "reasoning": "one sentence why"
}}

Do not include markdown fences, explanations outside the JSON, or any other text. Just the JSON object."""


def score_task(task: dict[str, Any], model: str) -> dict[str, Any]:
    """Run one task, return scoring details."""
    conv_str = "\n".join(f'  {t["role"]}: {t["content"]}' for t in task["conversation"])
    prompt = AGENT_PROMPT.format(context=task["context"], conversation=conv_str)
    
    result = call_llm(prompt, model=model)
    if not result["ok"]:
        return {
            "task_id": task["id"], "domain": task["domain"], "score": 0,
            "latency_seconds": result["latency_seconds"],
            "predicted": None, "expected": task["expected_action"],
            "error": result["error"],
        }
    
    text = result["text"].strip()
    # Strip common LLM noise
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    
    try:
        parsed = json.loads(text)
        predicted = parsed.get("action", "").lower().strip()
    except Exception:
        # Try to extract anything that looks like an action
        predicted = text[:60].lower()
    
    # Score: exact match OR synonym match
    valid = [s.lower() for s in task.get("valid_synonyms", [task["expected_action"]])]
    score = 1 if predicted in valid else 0
    # Partial credit: if the expected action's main verb appears anywhere
    if score == 0:
        main_verb = task["expected_action"].split("_")[0]
        if main_verb in predicted:
            score = 0.5
    
    return {
        "task_id": task["id"], "domain": task["domain"], "score": score,
        "latency_seconds": result["latency_seconds"],
        "predicted": predicted, "expected": task["expected_action"],
        "raw_response": text[:300],
        "error": None,
    }


def run(model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        output_dir: str = "/opt/Murphy-System/documentation/testing/benchmark_real") -> dict[str, Any]:
    """Run the full set, save results."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    print(f"  → Model: {model}")
    print(f"  → Tasks: {len(TAU_TASKS)}")
    print()
    
    results = []
    for i, task in enumerate(TAU_TASKS, 1):
        print(f"  [{i}/{len(TAU_TASKS)}] {task['id']} ({task['domain']})...", end=" ", flush=True)
        r = score_task(task, model)
        results.append(r)
        emoji = "✓" if r["score"] == 1 else ("◐" if r["score"] == 0.5 else "✗")
        pred = (r["predicted"] or "ERR")[:30]; err = f" ERR={r.get('error','')[:60]}" if r.get('error') else ""; print(f"{emoji} score={r['score']} predicted={pred} latency={r['latency_seconds']:.1f}s{err}")
    
    total_score = sum(r["score"] for r in results)
    n = len(results)
    
    summary = {
        "benchmark_name": "murphy-tau-bench-style",
        "benchmark_version": "0.1.0-real",
        "model": model,
        "run_timestamp": started,
        "tasks_total": n,
        "tasks_succeeded": sum(1 for r in results if r["score"] == 1),
        "tasks_partial": sum(1 for r in results if r["score"] == 0.5),
        "tasks_failed": sum(1 for r in results if r["score"] == 0),
        "mean_score": round(total_score / n, 3),
        "mean_latency_seconds": round(sum(r["latency_seconds"] for r in results) / n, 2),
        "domains": list({r["domain"] for r in results}),
        "domain_scores": {
            d: round(sum(r["score"] for r in results if r["domain"] == d) / 
                     max(sum(1 for r in results if r["domain"] == d), 1), 3)
            for d in {r["domain"] for r in results}
        },
        "results": results,
        "notes": [
            "This is a real LLM run, not synthetic harness output.",
            "10 hand-curated tau-bench-style tasks across 5 domains.",
            "Score includes exact-match (1.0), synonym-match (1.0), and partial-verb-match (0.5).",
            "For official τ-bench submission, run the sierra-research/tau-bench repo with Murphy's executor.",
        ],
    }
    
    out_file = Path(output_dir) / f"murphy_tau_real_{int(time.time())}.json"
    out_file.write_text(json.dumps(summary, indent=2))
    print()
    print(f"  → Results saved to: {out_file}")
    print(f"  → Mean score: {summary['mean_score']*100:.1f}%")
    print(f"  → Pass rate: {summary['tasks_succeeded']}/{n} ({summary['tasks_succeeded']/n*100:.1f}%)")
    return summary


if __name__ == "__main__":
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    run(model=model)
