# Communication System

The `communication_system` package is the low-level message dispatch bus
that the `comms` package and other subsystems use for reliable delivery.

## Key Module

| Module | Purpose |
|--------|---------|
| `pipeline.py` | `CommunicationPipeline` — queued, retried message delivery with DLQ |
