import math
from datetime import datetime, timezone
import json
import os

class RecursiveStabilityEngine:
    def __init__(self, system_capacity: float = 100.0, threshold: float = 1.5):
        self.mu = system_capacity
        self.S_min = threshold
        self.log = []
        self.score_path = os.path.join('logs', 'rcm_scores.json')
        self.interrupt_path = os.path.join('logs', 'rcm_interrupts.json')
        os.makedirs('logs', exist_ok=True)

    def decay(self, M: float, T: float) -> float:
        return M * math.log1p(T)

    def entropy(self, F: float) -> float:
        return math.log1p(F)

    def score(self, R_list, W_list, M: float, T: float, F: float) -> float:
        load = sum(R * W for R, W in zip(R_list, W_list))
        delta = self.decay(M, T)
        eta = self.entropy(F)
        return round(self.mu / (load + delta + eta + 1e-8), 5)

    def evaluate(self, context: dict):
        R = context.get('recursions', [])
        W = context.get('task_weights', [])
        M = context.get('memory_mb', 0.0)
        T = context.get('memory_seconds', 0.0)
        F = context.get('feedback_variance', 0.0)

        S = self.score(R, W, M, T, F)
        if S >= self.S_min:
            action = 'continue'
        elif S >= self.S_min * 0.75:
            action = 'pause'
        else:
            action = 'halt'

        result = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'score': S,
            'action': action,
            'context': context
        }
        self.log.append(result)
        self._write(self.score_path, result)
        if action in {'halt', 'pause'}:
            self._write(self.interrupt_path, result)
        return result

    def _write(self, path: str, entry: dict) -> None:
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
        except Exception:
            data = []
        data.append(entry)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def export_log(self) -> str:
        return json.dumps(self.log, indent=2)
