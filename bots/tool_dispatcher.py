from __future__ import annotations

"""Route validated task JSON to the correct bot function."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

from .jsonbot_schema import validate_json
try:
    from .visualization_bot import VisualizationBot
except Exception:  # pragma: no cover - optional dependency (matplotlib)
    VisualizationBot = None  # type: ignore
from .simulation_sandbox import simulate
try:
    from .analysisbot import AnalysisBot as EngineeringBot  # Import with alias
except ImportError:
    EngineeringBot = None

TOOL_ROUTER = {
    "generate_chart": getattr(VisualizationBot, 'generate_chart', None) if VisualizationBot else None,
    "run_simulation": simulate,
    "calculate_load": getattr(EngineeringBot, 'calculate_structural_load', None) if EngineeringBot else None,
}

LOG_PATH = "logs/tool_calls.json"


def _log(entry: Dict[str, Any]) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.debug("Suppressed exception in _log: %s", exc)


def dispatch(task_json: Dict[str, Any]) -> Dict[str, Any]:
    valid, error = validate_json(task_json)
    if not valid:
        result = {"status": "error", "reason": f"Invalid JSON schema: {error}"}
        _log({"task": task_json, "result": result})
        return result
    try:
        func = TOOL_ROUTER.get(task_json["task_type"])
        if not func:
            raise KeyError(f"No tool mapped for: {task_json['task_type']}")
        res = func(**task_json.get("parameters", {}))
        result = {"status": "success", "result": res}
    except Exception as exc:
        result = {"status": "error", "reason": str(exc)}
    _log({"task": task_json, "result": result})
    return result
