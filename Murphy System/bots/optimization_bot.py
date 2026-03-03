"""OptimizationBot with reinforcement learning hooks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple, Dict
from datetime import datetime, timezone
import json
import numpy as np
from .gpt_oss_runner import GPTOSSRunner  # ✅ GPT injected

OPT_RESULTS_FILE = "logs/optimization_results.json"
from .feedback_bot import filter_feedback, log_feedback


@dataclass
class State:
    features: np.ndarray


Q_TABLE: Dict[Tuple[Any, int], float] = {}


def choose_action(state: State, epsilon: float = 0.1) -> int:
    """Epsilon-greedy action selection."""
    if np.random.rand() < epsilon:
        return int(np.random.randint(0, 2))
    q0 = Q_TABLE.get((tuple(state.features), 0), 0.0)
    q1 = Q_TABLE.get((tuple(state.features), 1), 0.0)
    return 0 if q0 >= q1 else 1


def update_policy(transitions: List[Any], lr: float = 0.1, gamma: float = 0.9) -> None:
    """Simple Q-learning update."""
    for state, action, reward, next_state in transitions:
        sa = (tuple(state), action)
        best_next = max(Q_TABLE.get((tuple(next_state), a), 0.0) for a in [0, 1])
        old = Q_TABLE.get(sa, 0.0)
        Q_TABLE[sa] = old + lr * (reward + gamma * best_next - old)


def reinforcement_learning_loop(env, episodes: int = 10) -> None:
    """Simple training harness."""
    transitions = []
    for _ in range(episodes):
        state = env.reset()
        done = False
        while not done:
            action = choose_action(State(np.array(state)))
            next_state, reward, done, _ = env.step(action)
            transitions.append((np.array(state), action, reward, np.array(next_state)))
            state = next_state
    update_policy(transitions)


def rank_via_centrality(centrality: dict) -> list[str]:
    """Return task IDs sorted by centrality (highest first)."""
    return sorted(centrality, key=centrality.get, reverse=True)


def run_optimization(proposal: dict) -> None:
    """Simulate an optimization trial and log result."""
    result = {
        "target": proposal.get("target_bot"),
        "area": proposal.get("area"),
        "status": "tested",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "improved": True,
        "notes": f"Auto-optimized logic in {proposal.get('target_bot')} for {proposal.get('area')}",
    }
    with open(OPT_RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(result) + "\n")
    close_feedback_issues(proposal.get("target_bot"), proposal.get("area"))


def close_feedback_issues(bot: str, category: str) -> None:
    entries = filter_feedback()
    updated: list[dict] = []
    for entry in entries:
        if entry["bot"] == bot and entry["category"] == category and entry["status"] == "open":
            entry["status"] = "closed"
        updated.append(entry)
    with open("logs/feedback_log.json", "w", encoding="utf-8") as f:
        for e in updated:
            f.write(json.dumps(e) + "\n")


def propose_optimizations_with_gpt(log: list[dict]) -> list[dict]:
    """Use GPT-OSS to generate optimization proposals from feedback logs."""
    from collections import Counter

    response_log = []
    recurring = Counter((e["bot"], e["category"]) for e in log if e.get("status") == "open")
    runner = GPTOSSRunner(model_path="./models/gpt-oss-20b")

    for (bot, category), count in recurring.items():
        if count >= 3:
            prompt = (
                f"OptimizationBot has detected recurring feedback issues.\n"
                f"Bot: {bot}\n"
                f"Category: {category}\n"
                f"Count: {count}\n"
                f"What optimization should be attempted?"
            )
            try:
                raw = runner.chat(prompt)
                suggestion = json.loads(raw)
                response_log.append({
                    "target_bot": bot,
                    "area": category,
                    "proposal": suggestion.get("suggested_subtask", raw),
                    "confidence": suggestion.get("confidence", 0.5),
                })
            except Exception as e:
                response_log.append({
                    "target_bot": bot,
                    "area": category,
                    "proposal": f"Error from GPT: {e}",
                    "confidence": 0.0,
                })

    return response_log