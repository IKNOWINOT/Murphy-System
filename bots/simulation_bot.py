"""SimulationBot for running environment tests and logging results with GPT-OSS guidance."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import json as _json
from typing import List

from .cache_manager import get_cache, set_cache
from .gpt_oss_runner import GPTOSSRunner

try:
    from scipy.integrate import solve_ivp as _solve_ivp  # type: ignore
except Exception:  # pragma: no cover - optional dep
    _solve_ivp = None  # type: ignore

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def _spring_mass_damper(
    k: float, m: float, c: float, x0: float, v0: float,
    t_end: float = 5.0, dt: float = 0.01,
) -> dict:
    """Solve a spring-mass-damper system: m*x'' + c*x' + k*x = 0.

    Uses scipy.integrate.solve_ivp (RK45) when available, otherwise falls
    back to a simple Euler integrator.

    Args:
        k: Spring stiffness (N/m).
        m: Mass (kg).
        c: Damping coefficient (N·s/m).
        x0: Initial displacement (m).
        v0: Initial velocity (m/s).
        t_end: Simulation end time (s).
        dt: Time-step for Euler fallback (s).

    Returns:
        dict with ``displacement``, ``stress``, ``time_steps``, ``solver``,
        ``confidence``.
    """
    if m <= 0:
        m = 1e-9

    def ode(t: float, y: list) -> list:
        x, v = y
        dxdt = v
        dvdt = -(k / m) * x - (c / m) * v
        return [dxdt, dvdt]

    n_points = max(10, int(t_end / dt) + 1)
    t_eval = [i * dt for i in range(n_points)]
    solver_name = "euler"

    if _solve_ivp is not None:
        try:
            sol = _solve_ivp(ode, [0.0, t_end], [x0, v0], t_eval=t_eval, method="RK45", dense_output=False)
            displ = [float(x) for x in sol.y[0]]
            time_steps = [float(t) for t in sol.t]
            solver_name = "scipy_rk45"
        except Exception:
            displ = None
    else:
        displ = None

    if displ is None:
        # Euler fallback
        x, v = x0, v0
        displ = []
        time_steps_euler = []
        for t in t_eval:
            displ.append(x)
            time_steps_euler.append(t)
            ax = -(k / m) * x - (c / m) * v
            x = x + v * dt
            v = v + ax * dt
        time_steps = time_steps_euler

    # Stress proportional to spring force: σ ∝ k * displacement
    stress = [abs(k * d) for d in displ]

    return {
        "displacement": displ,
        "stress": stress,
        "time_steps": time_steps,
        "solver": solver_name,
        "confidence": 0.9,
    }


class SimulationBot:
    def __init__(self, model_path: str = "./models/gpt-oss-20b") -> None:
        self.runner = GPTOSSRunner(model_path=model_path)

    def run_simulation(self, task_json: dict) -> dict:
        """Simulate engineering task and store results with caching.

        Supported simulation types (key ``simulation_type`` in task_json):
        - ``spring_mass_damper``: Uses input_parameters keys ``k``, ``m``, ``c``,
          ``x0``, ``v0``, ``t_end``, ``dt``.

        Falls back to a structured unsupported-type response for unknown types.
        """
        key = "sim_" + _json.dumps(task_json, sort_keys=True)
        cached = get_cache(key)
        if cached:
            return cached

        sim_type = task_json.get("simulation_type", "").lower()
        params = task_json.get("input_parameters", {})
        timestamp = datetime.now(timezone.utc).isoformat()
        task_id = task_json.get("task_id", "unknown")

        if sim_type in ("spring_mass_damper", "spring_mass", "spring-mass-damper"):
            sim_result = _spring_mass_damper(
                k=float(params.get("k", 10.0)),
                m=float(params.get("m", 1.0)),
                c=float(params.get("c", 0.5)),
                x0=float(params.get("x0", 1.0)),
                v0=float(params.get("v0", 0.0)),
                t_end=float(params.get("t_end", 5.0)),
                dt=float(params.get("dt", 0.01)),
            )
            result = {
                "task_id": task_id,
                "bot_tested": task_json.get("target_bot", "unknown"),
                "input_parameters": params,
                "results": sim_result,
                "timestamp": timestamp,
            }
        else:
            # Unsupported simulation type — structured fallback, NOT random
            result = {
                "task_id": task_id,
                "bot_tested": task_json.get("target_bot", "unknown"),
                "input_parameters": params,
                "results": {
                    "displacement": [],
                    "stress": [],
                    "time_steps": [],
                    "solver": "none",
                    "confidence": 0,
                    "note": "unsupported simulation type — returning zero-valued fallback",
                },
                "timestamp": timestamp,
            }

        try:
            out_path = LOG_DIR / f"simulation_{task_id}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass

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