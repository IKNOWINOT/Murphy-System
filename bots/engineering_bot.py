"""EngineeringBot - Executes professional-grade task instructions from AnalysisBot with consistency validation."""
from __future__ import annotations

import json
import numpy as np
from typing import Any, Callable, Dict, List
from statistics import mean
from .gpt_oss_runner import GPTOSSRunner


class EngineeringBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path=model_path)

    def execute_engineering_task(self, description: str, input_data: dict) -> Any:
        """Generates and evaluates task logic based on analysis data."""
        prompt = f"""
You are a professional engineer. Based on the following task description and inputs, perform the task using proven formulas, industry-standard logic, and structured code.

Task: {description}
Inputs: {json.dumps(input_data, indent=2)}

Return the computed result.
"""
        raw = self.runner.chat(prompt)
        try:
            return float(raw.split("\n")[0].strip())
        except Exception:
            return raw.strip()

    def consistency_check(self, description: str, input_data: dict) -> dict:
        """Run the same task three times and validate output consistency."""
        results = [self.execute_engineering_task(description, input_data) for _ in range(3)]
        try:
            results_f = [float(r) for r in results]
        except Exception:
            return {
                "status": "fail",
                "reason": "Non-numeric outputs",
                "raw_outputs": results
            }

        diffs = [abs(a - b) for a in results_f for b in results_f if a != b]
        tolerance = 0.05 * mean(results_f)
        match_count = sum(d <= tolerance for d in diffs)

        if len(set(results_f)) == 1:
            return {"status": "locked", "result": results_f[0]}
        elif match_count >= 2:
            return {
                "status": "majority_match",
                "outputs": results_f,
                "tolerance": tolerance,
                "mean": round(mean(results_f), 4)
            }
        else:
            return {
                "status": "fail",
                "reason": "Outputs differ too greatly",
                "outputs": results_f,
                "tolerance": tolerance
            }

    def respond_to_roll_call(self, task_description: str) -> dict:
        """Return a proposal for how this bot could help on the task."""
        prompt = f"""
You are EngineeringBot.
Given this user task: {task_description},
Propose how you would solve it using calculations, formulas, or simulation.
Provide: {{"can_help": true, "confidence": float, "suggested_subtask": str}}
"""
        try:
            raw = self.runner.chat(prompt, stop_token="}")
            return json.loads(raw + "}")
        except Exception as e:
            return {"can_help": False, "error": str(e)}
