# Murphy Foundation Model (MFM)

> **Version 0.1.0 — Phase 1: Data Collection & Training Pipeline**

## Purpose

The Murphy Foundation Model is a self-improving model that learns from
every action trace produced by the Murphy System.  Rather than relying
solely on pre-trained weights, MFM continuously fine-tunes itself on
real operational data captured through the SENSE → THINK → ACT → LEARN
loop.

## Architecture

```
┌─────────────┐     ┌────────────────┐     ┌─────────────────────┐
│  EventBack- │────▶│  ActionTrace   │────▶│  Outcome Labeler    │
│  bone       │     │  Collector     │     │  (quality scores)   │
└─────────────┘     └────────────────┘     └─────────┬───────────┘
                                                     │
                    ┌────────────────┐     ┌─────────▼───────────┐
                    │  MFM Trainer   │◀────│  Training Data      │
                    │  (fine-tune)   │     │  Pipeline            │
                    └───────┬────────┘     └─────────────────────┘
                            │
              ┌─────────────▼──────────────┐
              │  Shadow Deployment /       │
              │  Self-Improvement Loop     │
              └────────────────────────────┘
```

## Phase 1 Modules (this release)

| Module                       | Description                                      |
|------------------------------|--------------------------------------------------|
| `action_trace_serializer.py` | Captures and persists structured action traces    |
| `outcome_labeler.py`         | Labels traces with quality, safety & calibration  |
| `training_data_pipeline.py`  | Converts labeled traces to instruction-tuning fmt |

## Phase 2+ Stubs

| Module                       | Description                                 |
|------------------------------|---------------------------------------------|
| `mfm_tokenizer.py`          | Custom tokeniser for structured traces      |
| `mfm_model.py`              | Lightweight transformer backbone            |
| `mfm_trainer.py`            | Fine-tuning loop with RLEF                  |
| `rlef_engine.py`            | Reinforcement Learning from Exec. Feedback  |
| `mfm_inference.py`          | Inference API with confidence gating        |
| `shadow_deployment.py`      | Shadow-mode deployment alongside live agents|
| `self_improvement_loop.py`  | Continuous improvement orchestrator         |
| `mfm_registry.py`           | Model versioning & artefact storage         |

## Quick Start

```python
from murphy_foundation_model import (
    ActionTrace, ActionTraceCollector, OutcomeLabeler, TrainingDataPipeline,
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
