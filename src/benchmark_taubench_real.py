"""
Ship 31h.2 — REAL τ-BENCH WITH ROSETTA DLF INJECTION
======================================================

Loads ACTUAL τ-bench tasks (115 retail + 50 airline = 165 total).
Runs them through 4 configurations:

  1. murphy_raw       — Llama-70B chat, no Murphy wrapping (baseline)
  2. murphy_magnified — Llama-70B + magnify-drill agent tailoring
  3. murphy_dlf       — Llama-70B + DLF soul injection (rosetta_core)
  4. murphy_full      — magnify-drill + DLF injection (full stack)

Scored against the GROUND-TRUTH action sequences in each task,
NOT by an LLM judge. This is external rubric.

SCORING:
  Each task has an expected action sequence (5-8 tool calls).
  For each system's response, we extract the actions it claims to take.
  We compare to ground truth: precision, recall, F1.
  Bonus: action_order_score for getting them in the right sequence.
"""

import sys, json, time, sqlite3, re
sys.path.insert(0, "/opt/Murphy-System")
from datetime import datetime, timezone
from tau_bench.envs.retail.tasks_test import TASKS_TEST as RETAIL_TASKS
from tau_bench.envs.airline.tasks_test import TASKS as AIRLINE_TASKS

def call_llm(prompt, model_hint="chat", max_tokens=800, system_prompt=None):
    from src.llm_provider import get_llm
    t0 = time.time()
    kwargs = {"model_hint": model_hint, "max_tokens": max_tokens}
    if system_prompt:
        kwargs["system"] = system_prompt
    result = get_llm().complete(prompt, **kwargs)
    el = time.time() - t0
    text = (getattr(result, "content", "") or "").strip()
    tok_in = int(getattr(result, "tokens_prompt", 0) or 0)
    tok_out = int(getattr(result, "tokens_completion", 0) or 0)
    rate = 0.88e-6
    return {"text": text, "elapsed_s": el, "tok_in": tok_in, "tok_out": tok_out,
            "cost_usd": (tok_in + tok_out) * rate,
            "model": getattr(result, "model", "?")}


# ----------------------------------------------------------------------
# ACTION EXTRACTION — pull "what would you do" from model output
# ----------------------------------------------------------------------

# Known tool names in tau-bench retail + airline domains
KNOWN_ACTIONS = [
    # Retail
    "find_user_id_by_name_zip", "find_user_id_by_email", "get_user_details",
    "get_order_details", "cancel_pending_order", "exchange_delivered_order_items",
    "return_delivered_order_items", "modify_pending_order_items",
    "modify_pending_order_address", "modify_pending_order_payment",
    "modify_user_address", "get_product_details", "list_all_product_types",
    "transfer_to_human_agents", "think", "calculate",
    # Airline
    "search_direct_flight", "search_onestop_flight", "book_reservation",
    "get_reservation_details", "update_reservation_flights",
    "update_reservation_passengers", "update_reservation_baggages",
    "cancel_reservation", "send_certificate",
]


def extract_actions(response_text):
    """Find action names mentioned in model output."""
    if not response_text:
        return []
    text_lower = response_text.lower()
    actions_found = []
    for action in KNOWN_ACTIONS:
        if action.lower() in text_lower:
            actions_found.append(action)
    # Also try to find function-call patterns
    fn_calls = re.findall(r'(\w+)\s*\(', response_text)
    for fn in fn_calls:
        if fn in KNOWN_ACTIONS and fn not in actions_found:
            actions_found.append(fn)
    return actions_found


def score_against_truth(predicted_actions, expected_actions):
    """F1 + order_score against ground truth."""
    expected_names = [a.name for a in expected_actions]
    pred_set = set(predicted_actions)
    exp_set = set(expected_names)
    if not exp_set:
        return {"precision": 0, "recall": 0, "f1": 0, "order_score": 0}
    tp = len(pred_set & exp_set)
    precision = tp / len(pred_set) if pred_set else 0
    recall = tp / len(exp_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    # Order score: how many consecutive pairs are in correct order
    order_correct = 0
    order_total = 0
    for i in range(len(expected_names) - 1):
        e1, e2 = expected_names[i], expected_names[i+1]
        if e1 in predicted_actions and e2 in predicted_actions:
            order_total += 1
            i1, i2 = predicted_actions.index(e1), predicted_actions.index(e2)
            if i1 < i2:
                order_correct += 1
    order_score = order_correct / order_total if order_total > 0 else 0
    return {"precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "order_score": round(order_score, 3),
            "predicted_set": list(pred_set), "expected_set": list(exp_set)}


# ----------------------------------------------------------------------
# 4 MURPHY CONFIGURATIONS
# ----------------------------------------------------------------------

BASE_PROMPT = """You are a customer service agent. Given this user request:

USER REQUEST: {instruction}

Available tools (list the ones you would call, in order):
- find_user_id_by_name_zip(first_name, last_name, zip)
- find_user_id_by_email(email)
- get_user_details(user_id)
- get_order_details(order_id)
- cancel_pending_order(order_id, reason)
- exchange_delivered_order_items(order_id, item_ids, new_item_ids, payment_method_id)
- return_delivered_order_items(order_id, item_ids, payment_method_id)
- modify_pending_order_items(order_id, item_ids, new_item_ids, payment_method_id)
- get_product_details(product_id)
- list_all_product_types()
- search_direct_flight(origin, destination, date)
- book_reservation(user_id, ...)
- update_reservation_flights, update_reservation_passengers, update_reservation_baggages
- cancel_reservation(reservation_id)
- transfer_to_human_agents

Respond with the sequence of tool calls you would make, ONE per line, in format:
1. tool_name(arg=val, ...)
2. tool_name(arg=val, ...)
..."""


MAGNIFY_PROMPT = """You are about to handle a customer service task. First, define your agent character in 4 blocks (3 sentences each):

CUSTOMER REQUEST: {instruction}

Output EXACTLY this format then STOP:
WHO: [your identity for this task]
HOW: [your method]
WHY: [your purpose]
STOP: [what you won't do]"""


def run_murphy_raw(task):
    """Baseline — Llama-70B chat with no Murphy wrapping."""
    prompt = BASE_PROMPT.format(instruction=task.instruction[:1500])
    return call_llm(prompt, model_hint="chat", max_tokens=600)


def run_murphy_magnified(task):
    """Magnify-drill: build agent character first, then act."""
    drill = call_llm(MAGNIFY_PROMPT.format(instruction=task.instruction[:1500]),
                     model_hint="fast", max_tokens=400)
    agent_desc = drill["text"]
    final_prompt = f"""You are this agent:
{agent_desc}

Now handle this request:
{task.instruction[:1500]}

{BASE_PROMPT.split('Available tools')[1]}"""
    main = call_llm(final_prompt, model_hint="chat", max_tokens=600)
    return {"text": main["text"], "elapsed_s": drill["elapsed_s"] + main["elapsed_s"],
            "tok_in": drill["tok_in"] + main["tok_in"],
            "tok_out": drill["tok_out"] + main["tok_out"],
            "cost_usd": drill["cost_usd"] + main["cost_usd"],
            "model": main["model"], "agent_desc": agent_desc}


def run_murphy_dlf(task):
    """DLF soul injection via rosetta_core."""
    # Use a generic customer_service_agent soul
    soul_system = """You are an autonomous customer service agent operating with full Murphy DLF.
LOYALTY: customer-first. You verify identity before acting, you confirm before destructive operations, you always show your work.
SCOPE: handle customer requests by selecting appropriate tools in correct order.
SAFETY: never invent order IDs, user IDs, or product IDs. Use lookup tools first."""
    prompt = BASE_PROMPT.format(instruction=task.instruction[:1500])
    return call_llm(prompt, model_hint="chat", max_tokens=600, system_prompt=soul_system)


def run_murphy_full(task):
    """Magnify-drill + DLF soul injection — full stack."""
    drill = call_llm(MAGNIFY_PROMPT.format(instruction=task.instruction[:1500]),
                     model_hint="fast", max_tokens=400)
    agent_desc = drill["text"]
    soul_system = f"""You are operating with full Murphy DLF + tailored agent character.

CHARACTER:
{agent_desc}

LOYALTY: customer-first. Verify before acting. Confirm before destructive ops. Show your work.
SAFETY: never invent IDs. Use lookup tools first. Order matters."""
    final_prompt = BASE_PROMPT.format(instruction=task.instruction[:1500])
    main = call_llm(final_prompt, model_hint="chat", max_tokens=600, system_prompt=soul_system)
    return {"text": main["text"], "elapsed_s": drill["elapsed_s"] + main["elapsed_s"],
            "tok_in": drill["tok_in"] + main["tok_in"],
            "tok_out": drill["tok_out"] + main["tok_out"],
            "cost_usd": drill["cost_usd"] + main["cost_usd"],
            "model": main["model"], "agent_desc": agent_desc}


# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------

def ensure_schema():
    c = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
    c.execute("""CREATE TABLE IF NOT EXISTS benchmark_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, benchmark TEXT NOT NULL, task_id TEXT NOT NULL,
        system_under_test TEXT NOT NULL, model TEXT,
        response TEXT, elapsed_s REAL, cost_usd REAL,
        judge_verdict TEXT, composite_score REAL, error TEXT)""")
    c.commit(); c.close()


def log_run(benchmark, task_id, sut, run_result, score):
    c = sqlite3.connect("/var/lib/murphy-production/entity_graph.db")
    c.execute("""INSERT INTO benchmark_runs
        (ts, benchmark, task_id, system_under_test, model, response,
         elapsed_s, cost_usd, judge_verdict, composite_score, error)
         VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now(timezone.utc).isoformat(), benchmark, task_id, sut,
         run_result.get("model", "?"),
         (run_result.get("text") or "")[:5000],
         run_result.get("elapsed_s", 0), run_result.get("cost_usd", 0),
         json.dumps(score), float(score.get("f1", 0)),
         run_result.get("error")))
    c.commit(); c.close()


def main(retail_n=10, airline_n=5):
    ensure_schema()
    tasks = [("retail-" + str(i), RETAIL_TASKS[i]) for i in range(retail_n)] + \
            [("airline-" + str(i), AIRLINE_TASKS[i]) for i in range(airline_n)]
    
    SYSTEMS = [
        ("murphy_raw",       run_murphy_raw),
        ("murphy_magnified", run_murphy_magnified),
        ("murphy_dlf",       run_murphy_dlf),
        ("murphy_full",      run_murphy_full),
    ]
    
    print(f"\n═══ REAL τ-BENCH — {len(tasks)} tasks × {len(SYSTEMS)} systems ═══")
    
    by_system = {}
    total_cost = 0
    
    for task_id, task in tasks:
        print(f"\n── {task_id} ──")
        print(f"  expected actions ({len(task.actions)}): {[a.name for a in task.actions[:5]]}")
        
        for sut_name, runner in SYSTEMS:
            try:
                r = runner(task)
                if r.get("error"):
                    print(f"  {sut_name:<18s}: ERROR")
                    continue
                predicted = extract_actions(r["text"])
                score = score_against_truth(predicted, task.actions)
                cost = r["cost_usd"]
                total_cost += cost
                print(f"  {sut_name:<18s}: F1={score['f1']:.2f} prec={score['precision']:.2f} rec={score['recall']:.2f} order={score['order_score']:.2f}  pred={len(predicted)}/{len(task.actions)}  ${cost:.4f}")
                by_system.setdefault(sut_name, []).append(score['f1'])
                log_run("tau-bench-real", task_id, sut_name, r, score)
            except Exception as e:
                print(f"  {sut_name:<18s}: EXCEPTION {e}")
    
    print(f"\n═══ FINAL — REAL τ-BENCH ═══")
    for sut, scores in by_system.items():
        avg = sum(scores)/len(scores) if scores else 0
        print(f"  {sut:<18s}: avg F1={avg:.3f}  (n={len(scores)})")
    print(f"  TOTAL COST: ${total_cost:.4f}")
    print(f"\n  PUBLISHED LEADERBOARD (for context):")
    print(f"    GPT-4o:      retail ~62%, airline ~57%")
    print(f"    Claude 3.5:  retail ~50%, airline ~48%")
    print(f"    Llama-70B:   retail ~40%, airline ~38%")


if __name__ == "__main__":
    import sys
    rn = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    an = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    main(retail_n=rn, airline_n=an)
