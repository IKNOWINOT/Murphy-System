# `src/ml` — Machine Learning Subsystem

Murphy's ML subsystem — model training, inference, evaluation, and the Murphy Foundation Model (MFM) runtime.

© 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

## Overview

The `ml` package provides Murphy's internal machine learning stack. It abstracts provider routing (`DeepInfra`, `Together AI`, `local`), manages model training pipelines, maintains a model version registry, handles inference requests, and exposes a `CopilotAdapter` for task-specific LLM dispatching. The **Murphy Foundation Model (MFM)** is trained and served from this package when `MFM_ENABLED=true`.

## Key Components

| Module | Purpose |
|--------|---------|
| `config.py` | `ModelProvider`, `TaskComplexity`, `ModelConfig`, `MFMConfig`, routing config |
| `training.py` | `TrainingPipeline`, `TrainingJob`, `TrainingSource` — MFM fine-tuning |
| `registry.py` | `ModelRegistry`, `ModelVersion` — versioned model artifact management |
| `inference.py` | `InferenceEngine`, `InferenceRequest`, `InferenceResult` |
| `copilot_adapter.py` | `CopilotAdapter` — maps `CopilotTaskType` to model + prompt |
| `evaluation.py` | `ModelEvaluator`, `EvalResult`, `EvalMetric` — business-domain benchmarks |
| `api.py` | FastAPI router — inference, training, and evaluation endpoints |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MFM_ENABLED` | `false` | Enable the Murphy Foundation Model |
| `MFM_MODE` | `inference` | `training` \| `inference` \| `evaluation` |
| `DEEPINFRA_API_KEY` | — | Primary cloud inference key |
| `TOGETHER_API_KEY` | — | Overflow cloud inference key |

## Related

- `src/llm_controller.py` — top-level LLM routing
- `src/openai_compatible_provider.py` — unified OpenAI-compatible client
