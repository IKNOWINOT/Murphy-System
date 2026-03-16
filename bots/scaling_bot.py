"""ScalingBot with CPU-based autoscaling heuristics."""
from __future__ import annotations

import json
import logging
import os
import psutil
from typing import Dict
from datetime import datetime, timezone
from .gpt_oss_runner import GPTOSSRunner  # Injected

from .key_manager_bot import KeyManagerBot

LOG_FILE = os.path.join("logs", "scaling_events.json")
logger = logging.getLogger(__name__)


def call_gpt_oss_instance(bot_name: str, message: str, model_path: str = "./models/gpt-oss-20b") -> dict:
    runner = GPTOSSRunner(model_path)
    raw = runner.chat(message)
    try:
        response = json.loads(raw)
        response["bot"] = bot_name
        return response
    except Exception as exc:
        return {"bot": bot_name, "decision": "noop", "error": str(exc)}


class ScalingBot:
    def __init__(self, key_manager: KeyManagerBot, up_threshold: int = 75, down_threshold: int = 25) -> None:
        self.key_manager = key_manager
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.instances: Dict[str, str] = {}  # bot_name->key_id

    def _log_event(self, action: str, bot_type: str, key_id: str) -> None:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "bot_type": bot_type,
            "key_id": key_id,
        }
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        active_path = os.path.join("live", "active_instances.json")
        os.makedirs(os.path.dirname(active_path), exist_ok=True)
        try:
            with open(active_path, "r", encoding="utf-8") as af:
                data = json.load(af)
        except Exception as exc:
            logger.debug("Suppressed exception reading active instances: %s", exc)
            data = {}
        if action == "scale_up":
            data[bot_type] = key_id
        elif action == "scale_down":
            data.pop(bot_type, None)
        with open(active_path, "w", encoding="utf-8") as af:
            json.dump(data, af, indent=2)

    def spawn_additional_instance(self, bot: str) -> None:
        key = self.key_manager.allocate_key(bot)
        if not key:
            return
        self.instances[bot] = key
        self._log_event("scale_up", bot, key)

    def terminate_idle_instance(self, bot: str) -> None:
        key = self.instances.pop(bot, None)
        if key:
            self.key_manager.revoke_key(key)
            self._log_event("scale_down", bot, key)

    def check_cpu(self) -> None:
        load = psutil.cpu_percent(interval=1)
        if load > self.up_threshold:
            self.spawn_additional_instance("OptimizationBot")
        elif load < self.down_threshold:
            self.terminate_idle_instance("OptimizationBot")

    def should_scale(self, bot_type: str, queue_depth: int, avg_latency: float) -> bool:
        return queue_depth > 10 or avg_latency > 2000

    def scale_bot(self, bot_type: str, queue_depth: int, avg_latency: float) -> dict:
        if not self.should_scale(bot_type, queue_depth, avg_latency):
            return {"status": "noop"}
        self.spawn_additional_instance(bot_type)
        key_val = self.instances.get(bot_type, "")
        redacted = f"{key_val[:4]}...REDACTED" if key_val else ""
        return {"status": "scaled", "instance": bot_type, "key": redacted}

    def calculate_resource_score(self, cpu: float, memory: float, freq: float, success: float) -> float:
        return (cpu + memory) * freq * success

    def recommend_scale(self, bot: str, expected_gain: float) -> bool:
        score = self.calculate_resource_score(psutil.cpu_percent(), psutil.virtual_memory().percent, 1.0, expected_gain)
        return score > 50

    # --- hive_mind_math_patch_v2.0 additions ---
    def forecast_demand(self, history: list[int]) -> float:
        """Very small Markov chain forecast of next demand."""
        if not history:
            return 0.0
        counts = {}
        for i in range(len(history)-1):
            state = history[i]
            nxt = history[i+1]
            counts.setdefault(state, {}).setdefault(nxt, 0)
            counts[state][nxt] += 1
        last = history[-1]
        transitions = counts.get(last, {})
        total = sum(transitions.values())
        if not total:
            return float(last)
        return sum(nxt * c/total for nxt, c in transitions.items())

    def gpt_forecast_scale_decision(self, bot: str, history: list[int]) -> dict:
        """Ask GPT-OSS whether this bot should scale based on usage history."""
        forecasted = self.forecast_demand(history)
        prompt = f"Bot: {bot}\nRecent demand: {history}\nForecasted demand: {forecasted}\nShould we scale?"
        return call_gpt_oss_instance(bot, prompt)