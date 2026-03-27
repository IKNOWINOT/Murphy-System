"""RubixCubeBot with visualization utilities."""
from __future__ import annotations

import os
import json
import time
from typing import Dict, Any, List
from collections import Counter

from .rcm_stability_core import RecursiveStabilityEngine
from .gpt_oss_runner import GPTOSSRunner  # ✅ Injected

engine = RecursiveStabilityEngine()
USAGE_LOG: List[Dict[str, Any]] = []
FEEDBACK_LOG = "logs/feedback_log.json"


def call_gpt_oss_instance(bot_name: str, message: str, model_path: str = "./models/gpt-oss-20b") -> dict:
    runner = GPTOSSRunner(model_path)
    raw = runner.chat(message)
    try:
        response = json.loads(raw)
        response["bot"] = bot_name
        return response
    except Exception as e:
        return {"bot": bot_name, "can_help": False, "error": str(e)}


def analyze_feedback() -> list[dict]:
    """Return optimization proposals for recurring open feedback issues."""
    try:
        with open(FEEDBACK_LOG, "r", encoding="utf-8") as f:
            entries = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []

    recurring = Counter((e["bot"], e["category"]) for e in entries if e.get("status") == "open")
    optimizations: list[dict] = []
    for (bot, category), count in recurring.items():
        if count >= 3:
            prompt = f"Bot: {bot}\nRecurring issue: {category}\nWhat should be done to resolve it?"
            gpt_response = call_gpt_oss_instance(bot, prompt)
            if gpt_response.get("can_help"):
                optimizations.append({
                    "target_bot": bot,
                    "area": category,
                    "proposal": gpt_response.get("suggested_subtask"),
                    "confidence": gpt_response.get("confidence"),
                })
    return optimizations


class CacheFlowManager:
    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._cache.get(key)

    def store(self, key: str, value: Any, hydrator: Any | None = None) -> None:
        self._cache[key] = value


class StreamingPathTrie:
    def __init__(self) -> None:
        self.paths: Dict[str, Dict[str, int]] = {}

    def log_path(self, tensor: str, index: int) -> None:
        self.paths.setdefault(tensor, {})[str(index)] = (
            self.paths.get(tensor, {}).get(str(index), 0) + 1
        )


class KaprekarHydrator:
    def __init__(self, seed: int, entropy_hint: float, depths: list[int] | None = None) -> None:
        self.seed = seed
        self.entropy_hint = entropy_hint
        self.depths = depths or []

    def hydrate_tensor(self, shape: tuple[int, ...]):
        import numpy as np
        rng = np.random.default_rng(self.seed)
        return rng.random(shape)

    def fold_tensor(self, tensor: Any) -> list[float]:
        return tensor.flatten().tolist()


class EntropyPrioritizer:
    def __init__(self, uape_map: Dict[str, Any]):
        self.map = uape_map


class QuantumEntangler:
    def entangle(self) -> None:
        pass


class FidelityTester:
    @staticmethod
    def compare(a: Any, b: Any) -> Dict[str, Any]:
        import numpy as np
        cos_sim = float(np.dot(a.flatten(), b.flatten()) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
        mse = float(np.mean((a - b) ** 2))
        return {
            "cosine_similarity": cos_sim,
            "mean_squared_error": mse,
            "passed": cos_sim > 0.95,
        }


class PathConfidenceRegistry:
    def __init__(self) -> None:
        self.path_scores: Dict[str, float] = {}

    def update(self, path_key: str, fidelity_score: float, entropy_hint: float, hydration_cost: float) -> None:
        prior = self.path_scores.get(path_key, 0.5)
        signal = fidelity_score / (entropy_hint + hydration_cost + 1e-6)
        updated = (prior + signal) / 2
        self.path_scores[path_key] = updated

    def get_confidence(self, path_key: str) -> float:
        return self.path_scores.get(path_key, 0.5)

    def rank_paths(self) -> list[tuple[str, float]]:
        return sorted(self.path_scores.items(), key=lambda x: -x[1])


class RubixCubeAgent:
    FOLD_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "rubix_folds")

    def __init__(self, uape_map: Dict[str, Any]):
        self.uape_map = uape_map
        self.cache = CacheFlowManager()
        self.trie = StreamingPathTrie()
        self.prioritizer = EntropyPrioritizer(uape_map)
        self.quantum = QuantumEntangler()
        self.tester = FidelityTester()
        self.probability_map = PathConfidenceRegistry()
        self.ensure_fold_dir()

    @classmethod
    def ensure_fold_dir(cls) -> None:
        if not os.path.exists(cls.FOLD_DIR):
            os.makedirs(cls.FOLD_DIR)

    @classmethod
    def save_folded_tensor(cls, tensor_name: str, folded_data: list[float]) -> None:
        cls.ensure_fold_dir()
        out_path = os.path.join(cls.FOLD_DIR, f"{tensor_name.replace('.', '_')}.uape")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(folded_data, f, indent=2)

    def fetch(self, tensor_name: str, shape: tuple[int, ...], access_index: int | None = None):
        cached = self.cache.get(tensor_name)
        if cached is not None:
            return cached

        meta = self.uape_map.get(tensor_name, {})
        hydrator = KaprekarHydrator(
            meta.get("kaprekar_seed", 0),
            meta.get("entropy_hint", 0.0),
            meta.get("iteration_depths")
        )
        hydrated_tensor = hydrator.hydrate_tensor(shape)
        path_key = f"{tensor_name}:{access_index if access_index is not None else '∅'}"

        if "original_tensor" in meta:
            fidelity = self.tester.compare(meta["original_tensor"], hydrated_tensor)
            self.probability_map.update(
                path_key,
                fidelity["cosine_similarity"],
                meta.get("entropy_hint", 0.0),
                hydration_cost=1.0
            )

        self.cache.store(tensor_name, hydrated_tensor, hydrator=hydrator)
        folded_entry = hydrator.fold_tensor(hydrated_tensor)
        self.save_folded_tensor(tensor_name, folded_entry)
        if access_index is not None:
            self.trie.log_path(tensor_name, access_index)
        return hydrated_tensor

    def view_hydration_stream(self) -> None:
        print("\n[Hydration Stream Confidence View]")
        for path, score in self.probability_map.rank_paths():
            print(f"{path}: confidence={score:.4f}")


def visualize_quantum(state: Any) -> None:
    import numpy as np
    import matplotlib.pyplot as plt
    plt.figure()
    plt.bar(range(len(state)), np.abs(state))
    plt.xlabel('State')
    plt.ylabel('Amplitude')
    plt.title('Quantum State Visualization')
    plt.show()


def log_usage(bot_name: str, tasks_handled: int, cpu: float, memory: float) -> None:
    context = {
        "recursions": [tasks_handled],
        "task_weights": [1.0],
        "memory_mb": memory,
        "memory_seconds": 0.0,
        "feedback_variance": 0.0,
    }
    engine.evaluate(context)
    USAGE_LOG.append({
        "timestamp": time.time(),
        "bot": bot_name,
        "tasks": tasks_handled,
        "cpu": cpu,
        "memory": memory,
    })


def forecast_scaling() -> float:
    import numpy as np
    if len(USAGE_LOG) < 2:
        return 0.0
    times = np.arange(len(USAGE_LOG))
    tasks = np.array([e["tasks"] for e in USAGE_LOG], dtype=float)
    coef = np.polyfit(times, tasks, 1)
    next_time = len(USAGE_LOG)
    return float(coef[0] * next_time + coef[1])