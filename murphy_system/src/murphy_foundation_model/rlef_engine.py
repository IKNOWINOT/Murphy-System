# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
RLEF Engine — Reinforcement Learning from Execution Feedback
=============================================================

Uses real execution outcomes (from the :class:`OutcomeLabeler`) as
reward signals to refine the MFM beyond supervised fine-tuning.
Implements Direct Preference Optimisation (DPO) over preference pairs
constructed by comparing successful and failed traces for the same
intent.

Reward formula:

    R = 0.4 × success + 0.2 × efficiency + 0.2 × safety
      + 0.1 × calibration + 0.1 × (1 − human_override)

Heavy ML dependencies are imported lazily.
"""

from __future__ import annotations

import logging
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

# -- configuration -------------------------------------------------------

_DEFAULT_REWARD_WEIGHTS: Dict[str, float] = {
    "success": 0.4,
    "efficiency": 0.2,
    "safety": 0.2,
    "calibration": 0.1,
    "human_agreement": 0.1,
}


@dataclass
class RLEFConfig:
    """Configuration for the RLEF engine."""

    reward_weights: Dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_REWARD_WEIGHTS)
    )
    min_preference_pairs: int = 1000
    dpo_beta: float = 0.1
    learning_rate: float = 5e-5
    num_epochs: int = 1
    batch_size: int = 2


# -- preference pair ------------------------------------------------------

@dataclass
class PreferencePair:
    """A single DPO preference pair."""

    intent: str
    chosen_trace: Dict[str, Any]
    rejected_trace: Dict[str, Any]
    chosen_reward: float
    rejected_reward: float


# -- engine ---------------------------------------------------------------

class RLEFEngine:
    """Reinforcement Learning from Execution Feedback.

    Builds preference pairs from labelled traces, computes scalar
    rewards, and trains the MFM using DPO.
    """

    def __init__(self, config: Optional[RLEFConfig] = None) -> None:
        self.config = config or RLEFConfig()
        self._preference_buffer: List[PreferencePair] = []
        self._training_history: List[Dict[str, Any]] = []
        logger.debug("RLEFEngine initialised — min_pairs=%d", self.config.min_preference_pairs)

    # -- public API ---------------------------------------------------------

    def compute_reward(
        self,
        trace: Dict[str, Any],
        labels: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute a scalar reward for a single trace.

        R = 0.4*success + 0.2*efficiency + 0.2*safety
          + 0.1*calibration + 0.1*(1 − human_override)

        *labels* should contain keys matching the reward weights.  If
        not provided the function looks inside ``trace["labels"]``.
        """
        if labels is None:
            labels = trace.get("labels", {})
        if not labels:
            return 0.0

        w = self.config.reward_weights
        reward = 0.0
        reward += w.get("success", 0.0) * labels.get("success", 0.0)
        reward += w.get("efficiency", 0.0) * labels.get("efficiency", 0.0)
        reward += w.get("safety", 0.0) * labels.get("safety_score", labels.get("safety", 0.0))
        reward += w.get("calibration", 0.0) * labels.get(
            "confidence_calibration", labels.get("calibration", 0.0)
        )
        human_override = labels.get("human_override", 1.0 - labels.get("human_agreement", 0.0))
        reward += w.get("human_agreement", 0.0) * (1.0 - human_override)

        return round(max(0.0, min(1.0, reward)), 4)

    def create_preference_pairs(
        self,
        traces: List[Dict[str, Any]],
    ) -> List[PreferencePair]:
        """Create DPO preference pairs from a batch of labelled traces.

        Groups traces by intent, then for each intent pairs the
        highest-reward trace (chosen) with each lower-reward trace
        (rejected) that has a reward gap ≥ 0.1.
        """
        by_intent: Dict[str, List[Tuple[float, Dict[str, Any]]]] = defaultdict(list)
        for trace in traces:
            intent = trace.get("intent", trace.get("think", "unknown"))
            reward = self.compute_reward(trace)
            by_intent[intent].append((reward, trace))

        pairs: List[PreferencePair] = []
        for intent, scored in by_intent.items():
            if len(scored) < 2:
                continue
            scored.sort(key=lambda x: x[0], reverse=True)
            best_reward, best_trace = scored[0]
            for rew, trc in scored[1:]:
                if best_reward - rew >= 0.1:
                    pairs.append(
                        PreferencePair(
                            intent=intent,
                            chosen_trace=best_trace,
                            rejected_trace=trc,
                            chosen_reward=best_reward,
                            rejected_reward=rew,
                        )
                    )

        self._preference_buffer.extend(pairs)
        logger.info(
            "Created %d preference pairs (buffer=%d)",
            len(pairs),
            len(self._preference_buffer),
        )
        return pairs

    def train_dpo(
        self,
        model: Any,
        preference_pairs: Optional[List[PreferencePair]] = None,
    ) -> Dict[str, Any]:
        """Run DPO training on the model using preference pairs.

        Parameters
        ----------
        model :
            An ``MFMModel`` instance (or any model with a ``forward``
            method and parameters).
        preference_pairs :
            Explicit pairs to use.  Falls back to the internal buffer.

        Returns
        -------
        dict with training metrics.
        """
        pairs = preference_pairs or self._preference_buffer
        if len(pairs) < self.config.min_preference_pairs:
            return {
                "status": "insufficient_data",
                "pairs_available": len(pairs),
                "pairs_required": self.config.min_preference_pairs,
            }

        try:
            import torch  # noqa: F811
            import torch.nn.functional as F  # noqa: F811
        except ImportError:
            logger.warning("torch not available — DPO training skipped")
            return {"status": "skipped", "reason": "torch_unavailable"}

        base = getattr(model, "_base_model", model)
        if base is None:
            return {"status": "skipped", "reason": "no_model"}

        base.train()
        try:
            device = next(base.parameters()).device
        except StopIteration:
            device = torch.device("cpu")

        optimizer = torch.optim.AdamW(
            [p for p in base.parameters() if p.requires_grad],
            lr=self.config.learning_rate,
        )

        total_loss = 0.0
        n_steps = 0
        start = time.monotonic()

        for epoch in range(self.config.num_epochs):
            for i in range(0, len(pairs), self.config.batch_size):
                batch = pairs[i : i + self.config.batch_size]
                batch_loss = torch.tensor(0.0, device=device)

                for pair in batch:
                    chosen_ids = self._trace_to_ids(pair.chosen_trace, device)
                    rejected_ids = self._trace_to_ids(pair.rejected_trace, device)

                    chosen_out = base(input_ids=chosen_ids)
                    rejected_out = base(input_ids=rejected_ids)

                    chosen_logp = self._sequence_log_prob(chosen_out.logits, chosen_ids)
                    rejected_logp = self._sequence_log_prob(rejected_out.logits, rejected_ids)

                    # DPO loss: -log σ(β (log π(y_w|x) - log π(y_l|x)))
                    diff = self.config.dpo_beta * (chosen_logp - rejected_logp)
                    pair_loss = -F.logsigmoid(diff)
                    batch_loss = batch_loss + pair_loss

                avg_loss = batch_loss / (len(batch) or 1)
                avg_loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                total_loss += avg_loss.item()
                n_steps += 1

        elapsed = time.monotonic() - start
        metrics = {
            "status": "completed",
            "epochs": self.config.num_epochs,
            "steps": n_steps,
            "avg_loss": total_loss / max(n_steps, 1),
            "pairs_used": len(pairs),
            "training_time_s": round(elapsed, 2),
        }
        capped_append(self._training_history, metrics)
        logger.info("DPO training complete — loss=%.4f, steps=%d", metrics["avg_loss"], n_steps)
        return metrics

    def should_retrain(self, traces: List[Dict[str, Any]]) -> bool:
        """Check whether enough preference pairs have accumulated to
        trigger a DPO retraining cycle."""
        pairs = self.create_preference_pairs(traces)
        has_enough = len(self._preference_buffer) >= self.config.min_preference_pairs
        if has_enough:
            logger.info(
                "Retrain trigger: %d pairs ≥ %d threshold",
                len(self._preference_buffer),
                self.config.min_preference_pairs,
            )
        return has_enough

    def run_rlef_cycle(
        self,
        model: Any,
        traces: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Orchestrate a full RLEF cycle.

        1. Create preference pairs from new traces.
        2. Check if retrain threshold is met.
        3. Run DPO training if applicable.
        4. Clear the preference buffer on success.
        """
        self.create_preference_pairs(traces)

        if len(self._preference_buffer) < self.config.min_preference_pairs:
            return {
                "status": "waiting",
                "pairs_buffered": len(self._preference_buffer),
                "pairs_needed": self.config.min_preference_pairs,
            }

        result = self.train_dpo(model)

        if result.get("status") == "completed":
            self._preference_buffer.clear()

        return result

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _trace_to_ids(trace: Dict[str, Any], device: Any) -> Any:
        """Convert a trace dict to a tensor of token IDs."""
        import torch  # noqa: F811

        from .mfm_tokenizer import MFMTokenizer

        tokenizer = MFMTokenizer()
        ids = tokenizer.encode_trace(trace)
        max_len = min(len(ids), 512)
        return torch.tensor([ids[:max_len]], device=device)

    @staticmethod
    def _sequence_log_prob(logits: Any, input_ids: Any) -> Any:
        """Compute the log-probability of the sequence under the model."""
        import torch  # noqa: F811
        import torch.nn.functional as F  # noqa: F811

        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = input_ids[:, 1:].contiguous()
        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs.gather(2, shift_labels.unsqueeze(-1)).squeeze(-1)
        return token_log_probs.sum(dim=-1).mean()
