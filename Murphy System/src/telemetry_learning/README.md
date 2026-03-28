# Telemetry Learning

The `telemetry_learning` package ingests raw telemetry events and applies
machine-learning models to extract actionable performance insights that
feed back into the Murphy learning loop.

## Key Modules

| Module | Purpose |
|--------|---------|
| `ingestion.py` | `TelemetryIngester` — consumes events from the telemetry bus |
| `learning.py` | `TelemetryLearner` — trains online models from ingested events |
| `models.py` | `TelemetryEvent`, `LearningInsight` Pydantic models |
| `schemas.py` | Avro/JSON schemas for event validation |
| `api.py` | FastAPI router for querying learned insights |
