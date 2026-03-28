# Rosetta

The `rosetta` package is Murphy's cross-subsystem translation and calibration
layer.  It maintains a living knowledge graph of capability mappings,
recalibrates confidence weights on a schedule, and produces structured
documents that describe the current system state.

## Key Modules

| Module | Purpose |
|--------|---------|
| `subsystem_wiring.py` | `RosettaSubsystemWiring` — wires EventBackbone, ConfidenceEngine, LearningEngine, GovernanceKernel, SecurityPlane |
| `rosetta_manager.py` | Lifecycle management for the Rosetta calibration loop |
| `recalibration_scheduler.py` | Cron-style scheduler for periodic re-calibration runs |
| `global_aggregator.py` | Aggregates signals from all subsystems into a unified snapshot |
| `archive_classifier.py` | Classifies and archives historical calibration snapshots |
| `rosetta_document_builder.py` | Renders human-readable Rosetta reports |
| `rosetta_models.py` | Pydantic models: `CalibrationSnapshot`, `WiringStatus` |

## Bootstrap

```python
from rosetta.subsystem_wiring import bootstrap_wiring
wiring = bootstrap_wiring()   # connects all P3-001 → P3-005 subsystems
```
