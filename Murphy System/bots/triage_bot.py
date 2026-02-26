from __future__ import annotations

import time
import json
from typing import Callable, Any, Dict, List
from .gpt_oss_runner import GPTOSSRunner

from .json_bot import JSONBot
from .commissioning_bot import CommissioningBot
from .task_lifecycle import TaskLifecycle
from .rcm_stability_core import RecursiveStabilityEngine
from .scaling_bot import ScalingBot
from .memory_manager_bot import retrieve_ltm_entries

engine = RecursiveStabilityEngine()


def call_gpt_oss_instance(bot_name: str, message: str, model_path: str = "./models/gpt-oss-20b") -> dict:
    runner = GPTOSSRunner(model_path)
    prompt = f"""
You are {bot_name}. Your task is to respond to this prompt and declare how you can assist.

Task: {message}

Respond using the format:
{{
  "can_help": true/false,
  "confidence": float (0.0 - 1.0),
  "suggested_subtask": "..."
}}
"""
    raw = runner.chat(prompt, stop_token="}")
    try:
        response = json.loads(raw + "}")
        response["bot"] = bot_name
        return response
    except Exception as e:
        return {"bot": bot_name, "can_help": False, "confidence": 0.0, "error": str(e)}


class TriageBot:
    def __init__(self, jsonbot: JSONBot, commissioner: CommissioningBot, scaling: ScalingBot, base_delay: float = 1.0) -> None:
        self.base_delay = base_delay
        self.jsonbot = jsonbot
        self.commissioner = commissioner
        self.scaling = scaling
        self.json_schema = TaskLifecycle
        self.queues: Dict[str, List[Callable[[], Any]]] = {}

    def queue_task(self, user_id: str, task: dict, func: Callable[[], Any]) -> None:
        obj = self.jsonbot.validate(task, self.json_schema)
        if not isinstance(obj, self.json_schema):
            return
        if not self.commissioner.verify_task(task) or self.commissioner.classify_task(task) < 60:
            return

        ctx = task.get("context", {})
        if ctx:
            retrieve_ltm_entries({"project": ctx.get("project"), "topic": ctx.get("topic")})

        context = {
            "recursions": [obj.stage],
            "task_weights": [1.0],
            "memory_mb": 0.0,
            "memory_seconds": 0.0,
            "feedback_variance": 0.0,
        }
        decision = engine.evaluate(context)
        if decision["action"] == "halt":
            raise RuntimeError("Task halted due to recursion instability.")
        elif decision["action"] == "pause":
            return

        self.queues.setdefault(user_id, []).append(func)
        depth = len(self.queues[user_id])
        self.scaling.scale_bot(task.get("assigned_to", "GenericBot"), depth, 0.0)

    def pop_task(self, user_id: str) -> Callable[[], Any] | None:
        q = self.queues.get(user_id)
        if q:
            return q.pop(0)
        return None

    def handle_task(self, func: Callable[[], Any], max_retries: int = 3) -> Any:
        delay = self.base_delay
        for _ in range(max_retries):
            try:
                return func()
            except Exception:
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("Task failed after retries")

    def roll_call(self, task: dict) -> List[dict]:
        roll_call_message = f"Task: {task['description']}. If you can help, respond with a subtask proposal."
        return self.rank_responses(self.broadcast_to_all_bots(roll_call_message))

    def broadcast_to_all_bots(self, message: str) -> List[dict]:
        bots = [
            "RubixCubeBot", "FeedbackBot", "OptimizationBot", "EngineeringBot",
            "SimulationBot", "CADBot", "VisualizationBot", "AnalysisBot"
        ]
        replies = []
        for bot_name in bots:
            response = call_gpt_oss_instance(bot_name, message)
            replies.append(response)
        return replies

    def rank_responses(self, responses: List[dict]) -> List[dict]:
        return sorted(responses, key=lambda r: r.get("confidence", 0), reverse=True)
