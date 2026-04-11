# Murphy Foundation Model (MFM)

> **Version 0.2.0 — LoRA Without Regret**

## Purpose

The Murphy Foundation Model is a self-improving model that learns from
every action trace produced by the Murphy System.  Rather than relying
solely on pre-trained weights, MFM continuously fine-tunes itself on
real operational data captured through the SENSE → THINK → ACT → LEARN
loop.

**LoRA Without Regret** — Following the best practices from Thinking
Machines Lab, MFM applies LoRA adapters to **both** attention AND MLP
layers by default.  This closes the 5–15 % performance gap vs. full
fine-tuning with negligible parameter overhead.

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────────┐
│  EventBack- │────▶│  ActionTrace   │────▶│  Outcome Labeler    │
│  bone       │     │  Collector     │     │  (quality scores)   │
└─────────────┘     └────────────────┘     └─────────┬───────────┘
                                                     │
                    ┌────────────────┐     ┌─────────▼───────────┐
                    │  MFM Trainer   │◀────│  Training Data      │
                    │  (LoRA f.t.)   │     │  Pipeline           │
                    └───────┬────────┘     └─────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  LoRA Adapter Registry     │
              │  (multi-tenant serving)    │
              └─────────────┬──────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  Shadow Deployment /       │
              │  Self-Improvement Loop     │
              └────────────────────────────┘
```

## Modules

| Module                        | Label               | Description                                                |
|-------------------------------|---------------------|------------------------------------------------------------|
| `action_trace_serializer.py`  | —                   | Captures and persists structured action traces              |
| `outcome_labeler.py`          | —                   | Labels traces with quality, safety & calibration            |
| `training_data_pipeline.py`   | —                   | Converts labeled traces to instruction-tuning format        |
| `mfm_tokenizer.py`           | —                   | Custom tokeniser for structured traces                      |
| `mfm_model.py`               | LORA-MODEL-*        | Transformer backbone with confidence/risk heads + adapter swap |
| `mfm_trainer.py`             | LORA-TRAINER-*      | LoRA fine-tuning with attention+MLP targeting               |
| `lora_adapter_registry.py`   | LORA-REGISTRY-*     | Adapter inventory, hot-swap, multi-tenant serving           |
| `rlef_engine.py`             | —                   | Reinforcement Learning from Exec. Feedback (DPO)           |
| `mfm_inference.py`           | —                   | Inference API with confidence gating                        |
| `shadow_deployment.py`       | —                   | Shadow-mode deployment alongside live agents                |
| `self_improvement_loop.py`   | —                   | Continuous improvement orchestrator                         |
| `mfm_registry.py`            | —                   | Model versioning & artefact storage                         |

## LoRA Without Regret — Key Configuration

```python
from murphy_foundation_model import MFMTrainerConfig

config = MFMTrainerConfig(
    lora_rank=16,          # Low-rank dimension (default: 16)
    lora_alpha=32,         # Scaling factor (default: 32)
    lora_dropout=0.05,     # Adapter dropout (default: 0.05)
    target_modules=[       # Attention + MLP layers (default)
        "q_proj", "v_proj", "k_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
)
```

### Multi-Tenant Adapter Serving

```python
from murphy_foundation_model import LoRAAdapterRegistry, LoRAAdapterMetadata

registry = LoRAAdapterRegistry()

# Register a domain-specific adapter.
meta = LoRAAdapterMetadata(
    name="manufacturing-v1",
    domain="manufacturing",
    base_model="microsoft/Phi-3-mini-4k-instruct",
    lora_rank=16,
    adapter_path="./data/adapters/manufacturing-v1",
)
registry.register(meta)

# Hot-swap on the model at runtime.
model.swap_adapter("./data/adapters/manufacturing-v1")
```

## Error Codes

| Code                   | Component       | Meaning                                   |
|------------------------|-----------------|-------------------------------------------|
| LORA-CFG-ERR-001       | TrainerConfig   | lora_rank < 1                             |
| LORA-CFG-ERR-002       | TrainerConfig   | lora_alpha < 1                            |
| LORA-CFG-ERR-003       | TrainerConfig   | lora_dropout out of [0, 1)                |
| LORA-CFG-ERR-004       | TrainerConfig   | target_modules empty                      |
| LORA-CFG-ERR-005       | TrainerConfig   | Loss weights don't sum to 1.0             |
| LORA-TRAINER-ERR-001   | Trainer         | peft not installed (prepare)              |
| LORA-TRAINER-ERR-002   | Trainer         | Failed to apply LoRA adapters             |
| LORA-TRAINER-ERR-003   | Trainer         | peft not installed (merge)                |
| LORA-TRAINER-ERR-004   | Trainer         | Merge operation failed                    |
| LORA-TRAINER-ERR-005   | Trainer         | peft not installed (save adapter)         |
| LORA-TRAINER-ERR-006   | Trainer         | Failed to save adapter                    |
| LORA-MODEL-ERR-001     | Model           | No base model loaded (swap)               |
| LORA-MODEL-ERR-002     | Model           | Adapter path does not exist               |
| LORA-MODEL-ERR-003     | Model           | peft not available (swap)                 |
| LORA-MODEL-ERR-004     | Model           | Adapter swap failed                       |
| LORA-REGISTRY-ERR-001  | Registry        | Registry full                             |
| LORA-REGISTRY-ERR-002  | Registry        | Name collision                            |
| LORA-REGISTRY-ERR-003  | Registry        | Invalid status                            |
| LORA-REGISTRY-ERR-004  | Registry        | Adapter not found (validate)              |
| LORA-REGISTRY-ERR-005  | Registry        | Empty adapter_path                        |
| LORA-REGISTRY-ERR-006  | Registry        | adapter_path directory missing            |
| LORA-REGISTRY-ERR-007  | Registry        | Required PEFT files missing               |
| LORA-REGISTRY-ERR-008  | Registry        | Invalid lora_rank                         |
| LORA-REGISTRY-ERR-009  | Registry        | Empty target_modules                      |
| LORA-REGISTRY-ERR-010  | Registry        | Persist to disk failed                    |
| LORA-REGISTRY-ERR-011  | Registry        | Load from disk failed                     |

## Quick Start

```python
from murphy_foundation_model import (
    ActionTrace, ActionTraceCollector, OutcomeLabeler, TrainingDataPipeline,
    MFMTrainer, MFMTrainerConfig,
)

collector = ActionTraceCollector.get_instance(trace_dir="./data/action_traces")
# … traces are recorded automatically via EventBackbone hooks …

labeler = OutcomeLabeler()
pipeline = TrainingDataPipeline(trace_dir="./data/action_traces")
stats = pipeline.run_pipeline()
print(stats)  # {"train": 800, "validation": 100, "test": 100}
```

## License

BSL 1.1 — Copyright © 2020-2026 Inoni LLC — Created by Corey Post
