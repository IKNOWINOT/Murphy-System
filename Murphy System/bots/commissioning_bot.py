"""CommissioningBot enforcing task lifecycle classification with GPT-OSS validation and internet scrubbing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import json
from pathlib import Path
from .feedback_bot import FeedbackBot, log_feedback
from .gpt_oss_runner import GPTOSSRunner  # ✅ Injected
import requests

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
REPORT_FILE = LOG_DIR / "commissioning_report.json"

@dataclass
class TaskStatus:
    status: str
    stage: int

class CommissioningBot:
    def __init__(self) -> None:
        self.tasks: Dict[str, TaskStatus] = {}
        self.runner = GPTOSSRunner(model_path="./models/gpt-oss-20b")

    def verify_task(self, task: dict) -> bool:
        if task.get("status") != "verified":
            return False
        return True

    def classify_task(self, task: dict) -> int:
        stage = task.get("stage", 30)
        self.tasks[task["task_id"]] = TaskStatus(task.get("status", "unverified"), stage)
        return stage

    def benchmark_task(self, task_id: str, stage: int) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].stage = stage

    def completeness_vector(self, stages: list[int]) -> float:
        import numpy as np
        target = np.ones(len(stages)) * 100
        vec = np.array(stages, dtype=float)
        return float(np.linalg.norm(target - vec))

    def evaluate_results(self, sim_result: dict, expected_outcomes: dict | None = None) -> dict:
        if expected_outcomes is None:
            key = f"material:{sim_result['input_parameters'].get('material')}"
            bench_path = Path("benchmarks/engineering_benchmarks.json")
            if bench_path.exists():
                bench = json.loads(bench_path.read_text())
                expected_outcomes = bench.get(key, {})
            else:
                expected_outcomes = {}

        score = 0
        total = len(expected_outcomes)
        for k, exp in expected_outcomes.items():
            actual = sim_result["results"].get(k)
            if actual is None:
                continue
            if isinstance(exp, str) and exp.startswith("<"):
                val = ''.join(ch for ch in exp if (ch.isdigit() or ch=='.'))
                target = float(val)
                if float(str(actual).split("mm")[0]) < target:
                    score += 1
            elif isinstance(exp, str) and exp.startswith(">"):
                val = ''.join(ch for ch in exp if (ch.isdigit() or ch=='.'))
                target = float(val)
                if float(actual) > target:
                    score += 1
            else:
                if abs(float(actual) - float(exp)) <= 5:
                    score += 1

        pct = (score / total) * 100 if total else 0
        if pct >= 95:
            stage = "100%"
        elif pct >= 75:
            stage = "90%"
        elif pct >= 50:
            stage = "60%"
        else:
            stage = "30%"

        report = {
            "task_id": sim_result["task_id"],
            "completion": stage,
            "score": pct,
            "timestamp": sim_result["timestamp"],
            "details": sim_result["results"],
        }

        with REPORT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(report) + "\n")

        if stage in {"30%", "60%"}:
            log_feedback(
                task_id=sim_result["task_id"],
                bot=sim_result.get("bot_tested", "unknown"),
                description="Simulation failed quality threshold",
                severity="high",
                category="commissioning",
            )

        return report

    def scrub_internet_for_validation(self, query: str) -> str:
        """Search the internet using a basic web query and validate against GPT."""
        try:
            headers = {"User-Agent": "CommissioningBot/1.0"}
            url = f"https://api.duckduckgo.com/?q={query}&format=json&no_redirect=1"
            response = requests.get(url, headers=headers, timeout=5)
            results = response.json().get("RelatedTopics", [])
            result_texts = [r.get("Text", "") for r in results if "Text" in r]
            data = "\n".join(result_texts[:5]) if result_texts else "No results found."
        except Exception as e:
            data = f"Failed to retrieve search results: {e}"

        prompt = f"""
You are CommissioningBot. Based on the user input and findings from web results, summarize or validate the claims.

User Query: {query}

Search Results:
{data}

Return whether the results support or contradict the input.
"""
        return self.runner.chat(prompt)