# Bridge Layer

The `bridge_layer` package translates hypotheses and intake forms into
structured execution packets that the Murphy execution pipeline can process.

## Key Modules

| Module | Purpose |
|--------|---------|
| `intake.py` | Parses raw user/API intake into normalised requests |
| `hypothesis.py` | Represents and validates probabilistic hypotheses |
| `hypothesis_intake.py` | Pipeline from raw input → validated hypothesis |
| `compilation.py` | Compiles validated inputs into `ExecutionPacket` objects |
| `models.py` | `BridgeRequest`, `Hypothesis`, `CompiledPacket` models |
