"""Efficiency optimizer with per-bot subtasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List
from .gpt_oss_runner import call_gpt_oss_instance  # Injected

@dataclass
class Subtask:
    """A granular optimization step for a specific bot type."""

    name: str
    bot_type: str
    weight: float = 1.0


OptimizerFunc = Callable[[Any], Any]

# Registry mapping bot types to optimizer functions
bot_registry: Dict[str, OptimizerFunc] = {}


def register_optimizer(bot_type: str) -> Callable[[OptimizerFunc], OptimizerFunc]:
    """Decorator to register an optimizer for ``bot_type``."""

    def decorator(func: OptimizerFunc) -> OptimizerFunc:
        bot_registry[bot_type] = func
        return func

    return decorator


@register_optimizer("CADBot")
def optimize_cadbot(task_data: Any) -> dict:
    """Optimize CADBot tasks."""
    # Call GPT-OSS to refine CAD task strategy
    prompt = f"Optimize the following CAD task: {task_data}"
    response = call_gpt_oss_instance("CADBot", prompt)
    return {"cad_optimized": True, "gpt_suggestion": response.get("suggested_subtask"), "task": task_data}


@register_optimizer("SimulationBot")
def optimize_simulationbot(task_data: Any) -> dict:
    """Optimize SimulationBot tasks."""
    prompt = f"Suggest simulation refinement for task: {task_data}"
    response = call_gpt_oss_instance("SimulationBot", prompt)
    return {"sim_optimized": True, "gpt_suggestion": response.get("suggested_subtask"), "task": task_data}


@register_optimizer("AnalysisBot")
def optimize_analysisbot(task_data: Any) -> dict:
    """Optimize AnalysisBot tasks."""
    prompt = f"Analyze how to optimize: {task_data}"
    response = call_gpt_oss_instance("AnalysisBot", prompt)
    return {"analysis_optimized": True, "gpt_suggestion": response.get("suggested_subtask"), "task": task_data}


def optimize_per_bot_type(bot_name: str, task_data: Any) -> Any:
    """Dispatch to a bot-specific optimizer if available."""
    optimizer = bot_registry.get(bot_name)
    if optimizer:
        return optimizer(task_data)
    log_unhandled_bot(bot_name)
    return None


def log_unhandled_bot(bot_name: str) -> None:
    """Log missing optimizer function."""
    print(f"No optimizer registered for {bot_name}")


def generate_subtasks(bot_types: Iterable[str]) -> List[Subtask]:
    """Generate a list of subtasks for the given bot types."""
    return [Subtask(name=f"optimize_{bt}", bot_type=bt) for bt in bot_types]

