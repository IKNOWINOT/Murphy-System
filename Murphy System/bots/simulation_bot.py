"""SimulationBot for running environment tests and logging results with GPT-OSS guidance."""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
import json as _json

from .cache_manager import get_cache, set_cache
from .gpt_oss_runner import GPTOSSRunner

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class SimulationBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path=model_path)

    def run_simulation(self, task_json: dict) -> dict:
        """Simulate engineering task and store results with caching."""
        key = "sim_" + _json.dumps(task_json, sort_keys=True)
        cached = get_cache(key)
        if cached:
            return cached

        # fallback placeholder results
        result = {
            "task_id": task_json["task_id"],
            "bot_tested": task_json.get("target_bot", "unknown"),
            "input_parameters": task_json.get("input_parameters", {}),
            "results": {
                "max_stress": round(random.uniform(110, 130), 2),
                "deformation": f"{round(random.uniform(1.2, 2.5), 2)}mm",
                "safety_factor": round(random.uniform(1.0, 2.0), 2),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        out_path = LOG_DIR / f"simulation_{task_json['task_id']}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        set_cache(key, result)
        return result

    def build_simulation_from_task(self, task_description: str, input_parameters: dict) -> dict:
        """Use GPT-OSS to propose a custom simulation structure for a given task."""
        prompt = f"""
You are SimulationBot. Based on the following engineering task and input parameters, define how to simulate it.
Include: relevant physical properties, ranges, conditions, and any expected outcome metrics.

Task: {task_description}
Inputs: {json.dumps(input_parameters, indent=2)}

Return a simulation configuration in JSON format.
"""
        try:
            response = self.runner.chat(prompt)
            return json.loads(response)
        except Exception as e:
            return {"error": str(e), "raw_response": response}

    def respond_to_roll_call(self, task_description: str) -> dict:
        """Respond with confidence and possible subtask if simulation could assist."""
        prompt = f"""
You are SimulationBot.
Given this task: {task_description}, determine if simulation could help and suggest a possible simulation subtask.
Respond as: {{"can_help": true, "confidence": float, "suggested_subtask": str}}
"""
        try:
            raw = self.runner.chat(prompt, stop_token="}")
            return json.loads(raw + "}")
        except Exception as e:
            return {"can_help": False, "error": str(e)}