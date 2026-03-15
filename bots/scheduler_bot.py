"""SchedulerBot with circuit breaker for runaway tasks."""
from __future__ import annotations

import json
import os
from typing import Callable, Any, Dict
from datetime import datetime, timezone
from .gpt_oss_runner import GPTOSSRunner  # Injected

from .container_runner import ContainerTask, run_container
from .rcm_stability_core import RecursiveStabilityEngine

engine = RecursiveStabilityEngine()

def call_gpt_oss_instance(bot_name: str, message: str, model_path: str = "./models/gpt-oss-20b") -> dict:
    runner = GPTOSSRunner(model_path)
    raw = runner.chat(message)
    try:
        response = json.loads(raw)
        response["bot"] = bot_name
        return response
    except Exception as e:
        return {"bot": bot_name, "schedule_decision": "noop", "error": str(e)}


class CircuitBreaker:
    def __init__(self, threshold: int = 5) -> None:
        self.threshold = threshold
        self.failures = 0
        self.open = False

    def call(self, func: Callable[[], Any]) -> Any:
        if self.open:
            raise RuntimeError("Circuit breaker open")
        try:
            result = func()
            self.failures = 0
            return result
        except Exception:
            self.failures += 1
            if self.failures >= self.threshold:
                self.open = True
            raise


class SchedulerBot:
    def __init__(self, breaker: CircuitBreaker | None = None) -> None:
        self.breaker = breaker or CircuitBreaker()
        self.weights: Dict[str, float] = {}

    def schedule(self, func: Callable[[], Any]) -> Any:
        context = {
            "recursions": [1],
            "task_weights": [1.0],
            "memory_mb": 0.0,
            "memory_seconds": 0.0,
            "feedback_variance": 0.0,
        }
        decision = engine.evaluate(context)
        if decision["action"] == "halt":
            raise RuntimeError("Schedule halted due to recursion instability")
        elif decision["action"] == "pause":
            return None
        return self.breaker.call(func)

    def run_container_task(self, task: ContainerTask) -> Any:
        """Run a heavy task inside an isolated container."""
        return run_container(task)

    def adjust_schedule_weight(self, bot: str, new_score: float) -> None:
        self.weights[bot] = new_score

    def predict_ETC(self, durations: list[float]) -> tuple[float, float]:
        """Return naive ETC mean and std-dev for given task durations."""
        if not durations:
            return 0.0, 0.0
        import numpy as np
        arr = np.array(durations, dtype=float)
        return float(arr.mean()), float(arr.std(ddof=1))

    def build_time_efficiency_matrix(self, data: dict[str, dict[str, float]]):
        """Create a simple matrix[bot][task_type] of avg durations."""
        import numpy as np
        bots = list(data)
        tasks = list({t for b in data for t in data[b]})
        matrix = np.zeros((len(bots), len(tasks)))
        for i, b in enumerate(bots):
            for j, t in enumerate(tasks):
                matrix[i, j] = data[b].get(t, 0.0)
        return bots, tasks, matrix

    def update_model(self, durations: list[float]) -> None:
        """Placeholder for updating the scheduling regression model."""
        self.predict_ETC(durations)

    def predict_time(self, bot: str, task_type: str) -> float:
        """Return average duration for the given bot/task_type based on logs."""
        try:
            with open("logs/task_timing_log.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return 2.5
        from statistics import mean
        times = [r["actual_time"] for r in data if r["bot"] == bot and r["task_type"] == task_type]
        return round(mean(times), 2) if times else 2.5

    def schedule_task(self, task: dict) -> dict:
        etc = self.predict_time(task["bot"], task["task_type"])
        scheduled = {
            "task_id": task["task_id"],
            "bot": task["bot"],
            "task_type": task["task_type"],
            "etc_minutes": etc,
            "status": "scheduled",
        }
        try:
            with open("logs/schedule_log.json", "r", encoding="utf-8") as f:
                log = json.load(f)
        except FileNotFoundError:
            log = []
        log.append(scheduled)
        with open("logs/schedule_log.json", "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
        return scheduled

    def update_time(self, task_id: str, bot: str, task_type: str, actual_time: float) -> None:
        try:
            with open("logs/task_timing_log.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []
        from datetime import datetime, timezone
        record = {
            "task_id": task_id,
            "bot": bot,
            "task_type": task_type,
            "predicted_etcs": [self.predict_time(bot, task_type)],
            "actual_time": actual_time,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        data.append(record)
        with open("logs/task_timing_log.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def flag_delay(self, task_id: str, bot: str, task_type: str, actual_time: float) -> None:
        prediction = self.predict_time(bot, task_type)
        if actual_time > prediction * 1.5:
            from .feedback_bot import log_feedback
            log_feedback(task_id, "SchedulerBot", "Task exceeded expected duration", severity="medium", category="timing")

    def recommend_scale(self, task_type: str, queue_depth: int) -> bool:
        if queue_depth > 10 and task_type in ["run_simulation", "analyze_data"]:
            return True
        return False

    def gpt_schedule_recommendation(self, bot: str, task_type: str) -> dict:
        prompt = f"Bot: {bot}\nTask type: {task_type}\nShould this task be scheduled or deferred?\nRespond with schedule_decision and reason."
        return call_gpt_oss_instance(bot, prompt)

