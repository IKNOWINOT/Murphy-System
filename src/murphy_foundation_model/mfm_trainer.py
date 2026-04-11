# Copyright © 2020-2026 Inoni LLC — Created by Corey Post
# License: BSL 1.1
"""
MFM Trainer — Fine-Tuning Pipeline
====================================

LoRA-based fine-tuning pipeline for the Murphy Foundation Model.
Supports parameter-efficient fine-tuning with a weighted multi-task
loss (action prediction, confidence calibration, risk estimation)
and optional RLEF hooks.

Heavy ML dependencies (``torch``, ``transformers``, ``peft``,
``datasets``) are imported lazily so the module can be imported in
lightweight environments without GPU packages.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = os.getenv("MFM_CHECKPOINT_DIR", "./data/mfm_checkpoints")

# -- configuration -------------------------------------------------------


@dataclass
class MFMTrainerConfig:
    """Hyperparameters and paths for the MFM fine-tuning pipeline.

    LoRA Without Regret — LORA-CFG-001
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Following "LoRA Without Regret" best practices (Thinking Machines Lab),
    adapters are applied to **both** attention AND MLP layers by default.
    Applying LoRA only to attention layers (q/k/v/o projections) leaves a
    5–15 % performance gap vs. full fine-tuning.  Including the MLP gate,
    up, and down projections closes that gap with negligible parameter
    overhead.

    Target-module names match the Llama / Phi-3 family convention.
    Override ``target_modules`` for architectures that use different names.
    """

    # LoRA — LORA-CFG-001
    lora_rank: int = 16
    lora_alpha: int = 32
    # Attention + MLP projections per "LoRA Without Regret" best practices.
    target_modules: List[str] = field(
        default_factory=lambda: [
            # Attention layers
            "q_proj", "v_proj", "k_proj", "o_proj",
            # MLP layers — required to close the gap with full fine-tuning
            "gate_proj", "up_proj", "down_proj",
        ]
    )
    lora_dropout: float = 0.05

    # Optimiser
    learning_rate: float = 2e-4
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    warmup_steps: int = 100
    max_grad_norm: float = 1.0

    # Evaluation
    eval_steps: int = 500

    # Loss weights — must sum to 1.0
    action_loss_weight: float = 0.5
    confidence_loss_weight: float = 0.3
    risk_loss_weight: float = 0.2

    # Output
    output_dir: str = _DEFAULT_OUTPUT_DIR
    fp16: bool = True

    def __post_init__(self) -> None:  # LORA-CFG-VALIDATE-001
        """Validate config invariants at construction time."""
        if self.lora_rank < 1:
            raise ValueError(
                f"lora_rank must be >= 1, got {self.lora_rank}"  # LORA-CFG-ERR-001
            )
        if self.lora_alpha < 1:
            raise ValueError(
                f"lora_alpha must be >= 1, got {self.lora_alpha}"  # LORA-CFG-ERR-002
            )
        if not (0.0 <= self.lora_dropout < 1.0):
            raise ValueError(
                f"lora_dropout must be in [0.0, 1.0), got {self.lora_dropout}"  # LORA-CFG-ERR-003
            )
        if not self.target_modules:
            raise ValueError(
                "target_modules must not be empty"  # LORA-CFG-ERR-004
            )
        weight_sum = (
            self.action_loss_weight
            + self.confidence_loss_weight
            + self.risk_loss_weight
        )
        if abs(weight_sum - 1.0) > 1e-6:
            raise ValueError(
                f"Loss weights must sum to 1.0, got {weight_sum}"  # LORA-CFG-ERR-005
            )


# -- trainer -------------------------------------------------------------


class MFMTrainer:
    """LoRA fine-tuning trainer for the Murphy Foundation Model.

    The trainer applies PEFT LoRA adapters to the base model, runs a
    training loop with a weighted multi-task loss, and supports
    merging the adapter back into the base weights for deployment.
    """

    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        config: Optional[MFMTrainerConfig] = None,
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.config = config or MFMTrainerConfig()
        self._lora_applied = False
        self._optimizer: Any = None
        self._scheduler: Any = None
        self._global_step = 0
        self._best_eval_loss = float("inf")
        logger.debug("MFMTrainer initialised — output=%s", self.config.output_dir)

    # -- public API ---------------------------------------------------------

    def prepare_model(self) -> bool:
        """Apply LoRA adapters to the base model.  — LORA-TRAINER-PREPARE-001

        Applies PEFT LoRA adapters targeting both attention and MLP layers
        (per "LoRA Without Regret" best practices).

        Returns ``True`` if adapters were successfully applied, ``False``
        if PEFT is unavailable.
        """
        if self._lora_applied:
            logger.debug("LoRA already applied — skipping")
            return True

        try:
            from peft import LoraConfig, TaskType, get_peft_model  # noqa: F811
        except ImportError:  # LORA-TRAINER-ERR-001
            logger.warning("LORA-TRAINER-ERR-001: peft not installed — LoRA cannot be applied")
            return False

        lora_cfg = LoraConfig(
            r=self.config.lora_rank,
            lora_alpha=self.config.lora_alpha,
            target_modules=self.config.target_modules,
            lora_dropout=self.config.lora_dropout,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )

        try:
            base = getattr(self.model, "_base_model", self.model)
            peft_model = get_peft_model(base, lora_cfg)
            peft_model.print_trainable_parameters()
        except Exception as exc:  # LORA-TRAINER-ERR-002
            logger.error("LORA-TRAINER-ERR-002: Failed to apply LoRA adapters: %s", exc)
            return False

        if hasattr(self.model, "_base_model"):
            self.model._base_model = peft_model
        else:
            self.model = peft_model

        self._lora_applied = True
        logger.info(
            "LoRA adapters applied (rank=%d, alpha=%d, dropout=%.2f, "
            "targets=%s)",
            self.config.lora_rank,
            self.config.lora_alpha,
            self.config.lora_dropout,
            self.config.target_modules,
        )
        return True

    def train(
        self,
        train_dataset: Any,
        eval_dataset: Any = None,
    ) -> Dict[str, Any]:
        """Run the full training loop.

        Parameters
        ----------
        train_dataset :
            An iterable/indexable dataset of dicts with keys
            ``input_ids``, ``attention_mask``, ``labels``,
            and optionally ``confidence_labels``, ``risk_labels``.
        eval_dataset :
            Optional evaluation dataset in the same format.

        Returns
        -------
        dict with training metrics.
        """
        try:
            import torch  # noqa: F811
        except ImportError:
            logger.warning("torch not installed — training skipped")
            return {"status": "skipped", "reason": "torch_unavailable"}

        base = self._get_trainable_model()
        if base is None:
            return {"status": "skipped", "reason": "no_model"}

        base.train()
        device = self._infer_device(base)

        self._optimizer = torch.optim.AdamW(
            [p for p in base.parameters() if p.requires_grad],
            lr=self.config.learning_rate,
            weight_decay=0.01,
        )
        total_steps = (
            len(train_dataset)
            // self.config.batch_size
            // self.config.gradient_accumulation_steps
            * self.config.num_epochs
        )
        self._scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self._optimizer, T_max=max(total_steps, 1)
        )

        os.makedirs(self.config.output_dir, exist_ok=True)

        epoch_losses: List[float] = []
        start_time = time.monotonic()

        for epoch in range(self.config.num_epochs):
            running_loss = 0.0
            batch_count = 0

            for batch_start in range(0, len(train_dataset), self.config.batch_size):
                batch_end = min(batch_start + self.config.batch_size, len(train_dataset))
                batch = self._collate(train_dataset, batch_start, batch_end, device)

                outputs = base(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    output_hidden_states=True,
                )

                loss = self.compute_loss(outputs, batch)
                scaled_loss = loss / self.config.gradient_accumulation_steps
                scaled_loss.backward()

                batch_count += 1
                running_loss += loss.item()

                if batch_count % self.config.gradient_accumulation_steps == 0:
                    torch.nn.utils.clip_grad_norm_(
                        base.parameters(), self.config.max_grad_norm
                    )
                    self._optimizer.step()
                    self._scheduler.step()
                    self._optimizer.zero_grad()
                    self._global_step += 1

                    if (
                        eval_dataset is not None
                        and self._global_step % self.config.eval_steps == 0
                    ):
                        eval_metrics = self.evaluate(eval_dataset)
                        if eval_metrics["loss"] < self._best_eval_loss:
                            self._best_eval_loss = eval_metrics["loss"]
                            self._save_checkpoint("best")
                        base.train()

            avg_loss = running_loss / max(batch_count, 1)
            epoch_losses.append(avg_loss)
            logger.info("Epoch %d/%d — loss=%.4f", epoch + 1, self.config.num_epochs, avg_loss)

        elapsed = time.monotonic() - start_time
        self._save_checkpoint("final")

        return {
            "status": "completed",
            "epochs_completed": self.config.num_epochs,
            "global_steps": self._global_step,
            "epoch_losses": epoch_losses,
            "best_eval_loss": self._best_eval_loss,
            "training_time_s": round(elapsed, 2),
        }

    def evaluate(self, eval_dataset: Any) -> Dict[str, float]:
        """Evaluate the model on *eval_dataset*.

        Returns a dict of metrics: ``loss``, ``action_accuracy``,
        ``confidence_mae``, ``risk_mae``.
        """
        try:
            import torch  # noqa: F811
        except ImportError:
            return {"loss": 0.0, "action_accuracy": 0.0, "confidence_mae": 0.0, "risk_mae": 0.0}

        base = self._get_trainable_model()
        if base is None:
            return {"loss": 0.0, "action_accuracy": 0.0, "confidence_mae": 0.0, "risk_mae": 0.0}

        base.eval()
        device = self._infer_device(base)

        total_loss = 0.0
        correct = 0
        total = 0
        conf_abs_err = 0.0
        risk_abs_err = 0.0

        with torch.no_grad():
            for batch_start in range(0, len(eval_dataset), self.config.batch_size):
                batch_end = min(batch_start + self.config.batch_size, len(eval_dataset))
                batch = self._collate(eval_dataset, batch_start, batch_end, device)

                outputs = base(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"],
                    output_hidden_states=True,
                )

                loss = self.compute_loss(outputs, batch)
                total_loss += loss.item()

                # Action accuracy
                if "labels" in batch:
                    preds = outputs.logits.argmax(dim=-1)
                    mask = batch["labels"] != -100
                    correct += (preds[mask] == batch["labels"][mask]).sum().item()
                    total += mask.sum().item()

                # Confidence MAE
                if "confidence_labels" in batch and hasattr(outputs, "hidden_states"):
                    last_hidden = outputs.hidden_states[-1][:, -1, :]
                    conf_head = getattr(self.model, "_confidence_head", None)
                    if conf_head is not None:
                        conf_logits = conf_head(last_hidden)
                        conf_probs = torch.softmax(conf_logits, dim=-1)
                        bins = torch.linspace(0, 1, conf_logits.shape[-1], device=device)
                        pred_conf = (conf_probs * bins).sum(dim=-1)
                        conf_abs_err += (pred_conf - batch["confidence_labels"]).abs().sum().item()

                # Risk MAE
                if "risk_labels" in batch and hasattr(outputs, "hidden_states"):
                    last_hidden = outputs.hidden_states[-1][:, -1, :]
                    risk_head = getattr(self.model, "_risk_head", None)
                    if risk_head is not None:
                        risk_logits = risk_head(last_hidden)
                        risk_probs = torch.softmax(risk_logits, dim=-1)
                        bins = torch.linspace(0, 1, risk_logits.shape[-1], device=device)
                        pred_risk = (risk_probs * bins).sum(dim=-1)
                        risk_abs_err += (pred_risk - batch["risk_labels"]).abs().sum().item()

        n_batches = max(len(eval_dataset) // self.config.batch_size, 1)
        n_samples = max(len(eval_dataset), 1)
        return {
            "loss": total_loss / n_batches,
            "action_accuracy": correct / max(total, 1),
            "confidence_mae": conf_abs_err / n_samples,
            "risk_mae": risk_abs_err / n_samples,
        }

    def compute_loss(self, outputs: Any, labels: Dict[str, Any]) -> Any:
        """Compute weighted multi-task loss.

        Loss = w_action * CE(logits, labels)
             + w_confidence * CE(conf_logits, conf_labels)
             + w_risk * CE(risk_logits, risk_labels)
        """
        import torch  # noqa: F811
        import torch.nn.functional as F  # noqa: F811

        total_loss = torch.tensor(0.0, device=self._infer_device(self._get_trainable_model()))

        # Action (language modelling) loss
        if "labels" in labels and outputs.logits is not None:
            lm_logits = outputs.logits
            shift_logits = lm_logits[:, :-1, :].contiguous()
            shift_labels = labels["labels"][:, 1:].contiguous()
            action_loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100,
            )
            total_loss = total_loss + self.config.action_loss_weight * action_loss

        # Confidence head loss
        if "confidence_labels" in labels and hasattr(outputs, "hidden_states"):
            last_hidden = outputs.hidden_states[-1][:, -1, :]
            conf_head = getattr(self.model, "_confidence_head", None)
            if conf_head is not None:
                conf_logits = conf_head(last_hidden)
                clamped = labels["confidence_labels"].clamp(0.0, 1.0)
                conf_targets = (clamped * (conf_logits.shape[-1] - 1)).long()
                conf_loss = F.cross_entropy(conf_logits, conf_targets)
                total_loss = total_loss + self.config.confidence_loss_weight * conf_loss

        # Risk head loss
        if "risk_labels" in labels and hasattr(outputs, "hidden_states"):
            last_hidden = outputs.hidden_states[-1][:, -1, :]
            risk_head = getattr(self.model, "_risk_head", None)
            if risk_head is not None:
                risk_logits = risk_head(last_hidden)
                clamped = labels["risk_labels"].clamp(0.0, 1.0)
                risk_targets = (clamped * (risk_logits.shape[-1] - 1)).long()
                risk_loss = F.cross_entropy(risk_logits, risk_targets)
                total_loss = total_loss + self.config.risk_loss_weight * risk_loss

        return total_loss

    def merge_and_save(self, output_path: str) -> bool:
        """Merge LoRA adapters into the base model and save.  — LORA-TRAINER-MERGE-001

        Returns ``True`` on success.
        """
        try:
            from peft import PeftModel  # noqa: F811
        except ImportError:  # LORA-TRAINER-ERR-003
            logger.warning("LORA-TRAINER-ERR-003: peft not installed — cannot merge adapters")
            return False

        base = self._get_trainable_model()
        if base is None:
            return False

        try:
            if isinstance(base, PeftModel):
                merged = base.merge_and_unload()
                os.makedirs(output_path, exist_ok=True)
                merged.save_pretrained(output_path)
                logger.info("Merged model saved to %s", output_path)
                return True
        except Exception as exc:  # LORA-TRAINER-ERR-004
            logger.error("LORA-TRAINER-ERR-004: LoRA merge failed: %s", exc)
            return False

        logger.warning("Model is not a PeftModel — saving as-is")
        os.makedirs(output_path, exist_ok=True)
        base.save_pretrained(output_path)
        return True

    def save_adapter(self, output_path: str) -> bool:
        """Save only the LoRA adapter weights (not the full model).  — LORA-TRAINER-SAVE-001

        This enables multi-tenant serving: a single base model can load
        different adapters at runtime without merging them permanently.

        Returns ``True`` on success.
        """
        base = self._get_trainable_model()
        if base is None:
            return False

        try:
            from peft import PeftModel  # noqa: F811
        except ImportError:  # LORA-TRAINER-ERR-005
            logger.warning("LORA-TRAINER-ERR-005: peft not installed — cannot save adapter")
            return False

        if not isinstance(base, PeftModel):
            logger.warning("Model is not a PeftModel — no adapter to save")
            return False

        try:
            os.makedirs(output_path, exist_ok=True)
            base.save_pretrained(output_path)

            # Persist the adapter config alongside weights for auditing.
            config_path = os.path.join(output_path, "murphy_adapter_config.json")
            import json as _json
            adapter_meta = {
                "lora_rank": self.config.lora_rank,
                "lora_alpha": self.config.lora_alpha,
                "lora_dropout": self.config.lora_dropout,
                "target_modules": self.config.target_modules,
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(config_path, "w", encoding="utf-8") as fh:
                _json.dump(adapter_meta, fh, indent=2)

            logger.info("LoRA adapter saved to %s", output_path)
            return True
        except Exception as exc:  # LORA-TRAINER-ERR-006
            logger.error("LORA-TRAINER-ERR-006: Failed to save adapter: %s", exc)
            return False

    # -- internal -----------------------------------------------------------

    def _get_trainable_model(self) -> Any:
        """Return the underlying torch model."""
        if self.model is None:
            return None
        return getattr(self.model, "_base_model", self.model)

    @staticmethod
    def _infer_device(model: Any) -> Any:
        """Infer the device from model parameters."""
        try:
            return next(model.parameters()).device
        except (StopIteration, AttributeError):
            import torch  # noqa: F811

            return torch.device("cpu")

    @staticmethod
    def _collate(
        dataset: Any,
        start: int,
        end: int,
        device: Any,
    ) -> Dict[str, Any]:
        """Collate a slice of the dataset into a batch dict of tensors."""
        import torch  # noqa: F811

        samples = [dataset[i] for i in range(start, end)]
        batch: Dict[str, Any] = {}
        for key in ("input_ids", "attention_mask", "labels"):
            if key in samples[0]:
                batch[key] = torch.stack(
                    [torch.tensor(s[key]) for s in samples]
                ).to(device)
        for key in ("confidence_labels", "risk_labels"):
            if key in samples[0]:
                batch[key] = torch.tensor(
                    [s[key] for s in samples], dtype=torch.float32
                ).to(device)
        return batch

    def _save_checkpoint(self, tag: str) -> None:
        """Persist a checkpoint under *tag*."""
        ckpt_dir = os.path.join(self.config.output_dir, tag)
        base = self._get_trainable_model()
        if base is None:
            return
        os.makedirs(ckpt_dir, exist_ok=True)
        base.save_pretrained(ckpt_dir)
        logger.info("Checkpoint saved → %s", ckpt_dir)


# -- helpers -------------------------------------------------------------


def load_training_data(data_dir: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load training and validation data from a directory of JSONL files.

    Expects files named ``train.jsonl`` and ``validation.jsonl`` in
    *data_dir*.  Each line is a JSON object with at least ``input_ids``
    and ``labels`` keys.

    Returns
    -------
    tuple of (train_data, eval_data)
    """
    train_data: List[Dict[str, Any]] = []
    eval_data: List[Dict[str, Any]] = []

    train_path = os.path.join(data_dir, "train.jsonl")
    eval_path = os.path.join(data_dir, "validation.jsonl")

    for path, dest in ((train_path, train_data), (eval_path, eval_data)):
        if not os.path.isfile(path):
            logger.warning("Data file not found: %s", path)
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    dest.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping line %d in %s: %s", line_no, path, exc)

    logger.info(
        "Loaded training data — %d train, %d eval samples from %s",
        len(train_data),
        len(eval_data),
        data_dir,
    )
    return train_data, eval_data
