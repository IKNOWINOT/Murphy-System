# Neuro-Symbolic Confidence Models

**Status:** Implementation Complete - Requires PyTorch Installation  
**Version:** 1.0.0  
**Type:** Optional ML Enhancement

---

## Overview

This module provides **optional ML enhancement** for the Murphy System's Confidence Engine. It uses Graph Neural Networks to learn better estimates of:

- **H(x)**: Epistemic instability
- **D(x)**: Deterministic grounding  
- **R(x)**: Authority risk

## Key Principles

✅ **Additive, Not Replacement** - Existing confidence computation unchanged  
✅ **Optional Enhancement** - System works fully without ML  
✅ **Graceful Degradation** - Falls back to heuristics on ML failures  
✅ **Safety Guarantees** - ML never controls authority, bounded influence  
✅ **No Breaking Changes** - Backward compatible with existing system

---

## Architecture

```
Existing Confidence Engine (Port 8055)
    ↓
Enhanced Fusion Layer (Optional)
    ↓
c_t = α_t·G(x) + β_t·D(x) + γ_t·ML(x)
                              ↑
                              │ (Optional, γ_t ≤ 0.3)
                              │
ML Service (Port 8060 - Optional)
    ↓
Graph Neural Network
    ├── GraphSAGE Encoder
    ├── Symbolic Feature Processor
    └── Multi-head Output (H, D, R)
```

---

## Installation

### Prerequisites

```bash
# Install PyTorch (CPU version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Or GPU version (if CUDA available)
pip install torch torchvision torchaudio

# Install PyTorch Geometric
pip install torch-geometric

# Install other dependencies
pip install -r src/neuro_symbolic_models/requirements.txt
```

### Verify Installation

```python
import torch
from src.neuro_symbolic_models.models import create_model

model = create_model()
print(f"Model created with {sum(p.numel() for p in model.parameters())} parameters")
```

---

## Usage

### Option 1: Without ML (Default - Backward Compatible)

```python
from src.confidence_engine import ConfidenceEngine

# Use existing engine as before
engine = ConfidenceEngine()
result = engine.compute_confidence(
    artifact_graph,
    verification_evidence,
    trust_model,
    phase
)
```

### Option 2: With ML Enhancement (Opt-in)

```python
from src.confidence_engine import ConfidenceEngine
from src.neuro_symbolic_models.integration import (
    ConfidenceEngineWithML,
    MLConfig
)

# Create base engine
base_engine = ConfidenceEngine()

# Enable ML enhancement
ml_config = MLConfig(
    enable_ml=True,
    ml_service_url="http://localhost:8060",
    ml_weight=0.2,  # ML has 20% influence
    ml_min_confidence=0.8  # Only use high-confidence predictions
)

# Create enhanced engine
engine = ConfidenceEngineWithML(base_engine, ml_config)

# Use exactly like before
result = engine.compute_confidence(
    artifact_graph,
    verification_evidence,
    trust_model,
    phase
)

# Check if ML was used
if result.used_ml:
    print(f"ML Signal: H={result.ml_signal.H_ml:.3f}, "
          f"D={result.ml_signal.D_ml:.3f}, "
          f"R={result.ml_signal.R_ml:.3f}")
```

---

## Training

### Step 1: Collect Training Data

```python
from src.neuro_symbolic_models.data import TrainingDataCollector, DataSplitter

# Collect data from Synthetic Failure Generator
collector = TrainingDataCollector(
    failure_generator_url="http://localhost:8059"
)

examples = collector.collect_training_batch(batch_size=10000)
print(f"Collected {len(examples)} training examples")

# Split into train/val/test
train, val, test = DataSplitter.split(examples)
```

### Step 2: Train Model

```python
from src.neuro_symbolic_models.models import create_model
from src.neuro_symbolic_models.training import ModelTrainer, TrainingConfig
from src.neuro_symbolic_models.data import create_dataloaders

# Create dataloaders
train_loader, val_loader = create_dataloaders(train, val, batch_size=32)

# Create model
model = create_model()

# Configure training
config = TrainingConfig(
    learning_rate=0.001,
    num_epochs=100,
    patience=10
)

# Train
trainer = ModelTrainer(model, config)
history = trainer.train(train_loader, val_loader)

print(f"Best validation loss: {trainer.best_val_loss:.4f}")
```

### Step 3: Validate Model

```python
from src.neuro_symbolic_models.training import ModelValidator

validator = ModelValidator()
report = validator.validate_model(model, test_loader)

print(f"Accuracy: {report.accuracy:.3f}")
print(f"Calibration: {report.calibration:.3f}")
print(f"Inference Speed: {report.inference_speed:.2f}ms")
print(f"Approved: {report.approved}")
```

### Step 4: Deploy Model

```python
from src.neuro_symbolic_models.inference import run_server

# Start ML inference service
run_server(
    host="0.0.0.0",
    port=8060,
    model_path="./checkpoints/best_model.pt"
)
```

---

## API Reference

### ML Inference Service (Port 8060)

#### Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "models_loaded": true,
  "model_version": "1.0.0",
  "prediction_confidence": 0.85
}
```

#### Predict Confidence
```bash
POST /predict/confidence

Request:
{
  "artifact_graph": {...},
  "gate_graph": {...},
  "interface_bindings": {...},
  "current_phase": "generative"
}

Response:
{
  "H_ml": 0.3,
  "D_ml": 0.8,
  "R_ml": 0.2,
  "prediction_confidence": 0.85,
  "model_version": "1.0.0",
  "inference_time_ms": 45.2
}
```

#### Batch Prediction
```bash
POST /predict/batch

Request:
{
  "scenarios": [
    {"artifact_graph": {...}},
    {"artifact_graph": {...}}
  ]
}

Response:
{
  "predictions": [...],
  "batch_confidence": 0.82
}
```

---

## Configuration

### MLConfig Options

```python
@dataclass
class MLConfig:
    enable_ml: bool = False  # Disabled by default
    ml_service_url: str = "http://localhost:8060"
    ml_timeout_ms: int = 100  # Fast timeout
    ml_min_confidence: float = 0.8  # Only use confident predictions
    ml_weight: float = 0.2  # ML influence (≤0.3)
    ml_fallback_on_error: bool = True  # Always fallback
```

### ModelConfig Options

```python
@dataclass
class ModelConfig:
    node_feature_dim: int = 64
    edge_feature_dim: int = 16
    symbolic_feature_dim: int = 32
    hidden_dim: int = 128
    num_gnn_layers: int = 3
    num_attention_heads: int = 4
    dropout: float = 0.2
```

---

## Safety Guarantees

### 1. Authority Independence
ML models **NEVER** directly control authority. Authority is always computed by the base engine using the hard-coded mapping `Γ(c_t)`.

### 2. Bounded Influence
ML signal has **bounded influence** on final confidence:
- ML weight `γ_t ≤ 0.3` (maximum 30% influence)
- Base confidence always has majority influence

### 3. Graceful Degradation
System **always** falls back to heuristic confidence if:
- ML service unavailable
- ML prediction timeout (100ms)
- ML prediction confidence too low (<0.8)
- Any error occurs

### 4. Validation Required
Models must pass validation before deployment:
- Accuracy > 85%
- Calibration > 80%
- Inference speed < 100ms
- All safety checks passed

---

## Monitoring

### Get Statistics

```python
engine = ConfidenceEngineWithML(base_engine, ml_config)

# After some usage
stats = engine.get_statistics()

print(f"ML Calls: {stats['ml_calls']}")
print(f"Success Rate: {stats['success_rate']:.2%}")
print(f"ML Weight: {stats['ml_weight']}")
```

### Enable/Disable ML

```python
# Disable ML at runtime
engine.enable_ml(False)

# Re-enable ML
engine.enable_ml(True)
```

---

## Testing

### Run Tests (Requires PyTorch)

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests
python -m pytest tests/test_neuro_symbolic_models.py -v

# Run with coverage
python -m pytest tests/test_neuro_symbolic_models.py --cov=src/neuro_symbolic_models
```

### Test Coverage

- ✅ Model architecture
- ✅ Forward pass and output bounds
- ✅ Integration with Confidence Engine
- ✅ Graceful degradation
- ✅ Safety properties
- ✅ Backward compatibility

---

## Deployment Strategy

### Phase 1: Shadow Mode (Months 1-3)
- ML makes predictions but they're not used
- Compare predictions with actual outcomes
- Build confidence in model performance

### Phase 2: A/B Testing (Months 4-6)
- 10% of traffic uses ML-enhanced confidence
- 90% uses base confidence
- Compare outcomes and metrics

### Phase 3: Gradual Rollout (Months 7-12)
- Start at 10% traffic
- Increase by 10% each week if metrics good
- Rollback if any issues detected

---

## Files

```
src/neuro_symbolic_models/
├── __init__.py              # Module initialization
├── models.py                # Neural network architectures
├── data.py                  # Data collection and processing
├── training.py              # Training and validation
├── inference.py             # ML inference service
├── integration.py           # Integration with Confidence Engine
├── requirements.txt         # Python dependencies
└── README.md               # This file

tests/
└── test_neuro_symbolic_models.py  # Test suite
```

---

## Status

- ✅ **Design Complete** - Full specification documented
- ✅ **Implementation Complete** - All modules implemented
- ✅ **Tests Written** - Comprehensive test suite
- ⏳ **PyTorch Installation** - Required for execution
- ⏳ **Training Data** - Collect from Synthetic Failure Generator
- ⏳ **Model Training** - Train on collected data
- ⏳ **Validation** - Validate before deployment
- ⏳ **Deployment** - Deploy to production

---

## Next Steps

1. **Install Dependencies**
   ```bash
   pip install torch torch-geometric
   pip install -r src/neuro_symbolic_models/requirements.txt
   ```

2. **Collect Training Data**
   ```bash
   python -c "from src.neuro_symbolic_models.data import TrainingDataCollector; \
              collector = TrainingDataCollector(); \
              examples = collector.collect_training_batch(10000)"
   ```

3. **Train Model**
   ```bash
   python src/neuro_symbolic_models/training.py
   ```

4. **Start ML Service**
   ```bash
   python src/neuro_symbolic_models/inference.py ./checkpoints/best_model.pt
   ```

5. **Enable in Confidence Engine**
   ```python
   ml_config = MLConfig(enable_ml=True)
   engine = ConfidenceEngineWithML(base_engine, ml_config)
   ```

---

## Support

For questions or issues:
1. Check design specification: `NEURO_SYMBOLIC_MODELS_DESIGN_SPEC.md`
2. Review integration examples in `integration.py`
3. Run tests to verify installation

---

**Version:** 1.0.0  
**Status:** Implementation Complete  
**Requires:** PyTorch, PyTorch Geometric  
**Optional:** GPU for faster training