"""FeedbackBot with reinforcement-aware time decay."""
from __future__ import annotations

import logging
import math
import json
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from .gpt_oss_runner import GPTOSSRunner  # ✅ Injected

logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    timestamp: datetime
    value: float
    reinforcement: int = 0


class FeedbackBot:
    """Manage feedback with decaying importance."""

    def __init__(self, half_life_days: float = 3.0):
        self.half_life_days = half_life_days
        self.feedback: List[FeedbackEntry] = []

    def add_feedback(self, value: float, *, timestamp: Optional[datetime] = None, reinforcement: int = 0) -> None:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        self.feedback.append(FeedbackEntry(timestamp, value, reinforcement))

    def reinforce(self, index: int, count: int = 1) -> None:
        self.feedback[index].reinforcement += count

    def _decay(self, entry: FeedbackEntry, now: datetime) -> float:
        age_days = (now - entry.timestamp).total_seconds() / 86400
        decay_factor = 0.5 ** (age_days / self.half_life_days)
        reinforcement_boost = math.log1p(entry.reinforcement)
        return entry.value * decay_factor * (1 + 0.1 * reinforcement_boost)

    def compute_score(self, now: Optional[datetime] = None) -> float:
        if now is None:
            now = datetime.now(timezone.utc)
        return sum(self._decay(entry, now) for entry in self.feedback)

    def compute_adaptive_score(self, now: Optional[datetime] = None) -> float:
        """Adaptive forgetting where half-life grows with feedback age."""
        if now is None:
            now = datetime.now(timezone.utc)
        score = 0.0
        for entry in self.feedback:
            age = (now - entry.timestamp).total_seconds()
            stability = self.half_life_days * 86400 * (1 + age / (self.half_life_days * 86400))
            decay = 0.5 ** (age / stability)
            reinforcement_boost = math.log1p(entry.reinforcement)
            score += entry.value * decay * (1 + 0.1 * reinforcement_boost)
        return score

    def log_error(self, message: str) -> None:
        self.add_feedback(-1.0)
        try:
            from .memory_manager_ttl import archive_to_ltm
            entry = {
                'task_id': 'feedback_error',
                'owner': 'FeedbackBot',
                'bot': 'FeedbackBot',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'content': message,
                'tags': ['error'],
                'context': {'project': 'feedback', 'topic': 'error'},
                'ttl_seconds': 0,
            }
            archive_to_ltm(entry)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)

    # --- hive_mind_math_patch_v2.0 additions ---
    def build_feedback_graph(self) -> dict:
        """Return eigenvector centrality for feedback relationships."""
        try:
            import networkx as nx
        except Exception:
            return {}
        g = nx.DiGraph()
        for idx, entry in enumerate(self.feedback):
            g.add_node(idx, weight=entry.value)
            if idx > 0:
                g.add_edge(idx - 1, idx, weight=entry.reinforcement + 1)
        if not g:
            return {}
        return nx.eigenvector_centrality(g)

    def suggest_improvements_from_feedback(self, log: list[dict]) -> list[dict]:
        """Use GPT-OSS to suggest improvements based on logged issues."""
        from collections import Counter

        response_log = []
        recurring = Counter((e["bot"], e["category"]) for e in log if e.get("status") == "open")
        runner = GPTOSSRunner(model_path="./models/gpt-oss-20b")

        for (bot, category), count in recurring.items():
            if count >= 3:
                prompt = (
                    f"FeedbackBot detected recurring issues.\n"
                    f"Bot: {bot}\n"
                    f"Issue: {category}\n"
                    f"Count: {count}\n"
                    f"What is a possible improvement?"
                )
                try:
                    raw = runner.chat(prompt)
                    suggestion = json.loads(raw)
                    response_log.append({
                        "bot": bot,
                        "category": category,
                        "suggested_fix": suggestion.get("suggested_subtask", raw),
                        "confidence": suggestion.get("confidence", 0.5)
                    })
                except Exception as e:
                    response_log.append({
                        "bot": bot,
                        "category": category,
                        "suggested_fix": f"Failed to generate suggestion: {e}",
                        "confidence": 0.0
                    })
        return response_log


FEEDBACK_FILE = "logs/feedback_log.json"


def log_feedback(task_id: str, bot: str, description: str, severity: str = "medium", category: str = "general") -> str:
    """Append a feedback entry to the log file and return its issue ID."""
    issue_id = f"FB-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid4())[:6]}"
    entry = {
        "issue_id": issue_id,
        "task_id": task_id,
        "bot": bot,
        "description": description,
        "severity": severity,
        "category": category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "open",
    }
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return issue_id


def get_feedback_by_id(issue_id: str) -> dict | None:
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("issue_id") == issue_id:
                    return entry
    except FileNotFoundError:
        pass
    return None


def filter_feedback(status: str | None = None, severity: str | None = None) -> list[dict]:
    results: list[dict] = []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if status and entry.get("status") != status:
                    continue
                if severity and entry.get("severity") != severity:
                    continue
                results.append(entry)
    except FileNotFoundError:
        pass
    return results