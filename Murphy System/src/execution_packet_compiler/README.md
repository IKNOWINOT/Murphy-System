# Execution Packet Compiler

The `execution_packet_compiler` package compiles high-level task descriptions
into fully-specified, determinism-enforced `ExecutionPacket` objects ready
for dispatch to the execution engine.

## Key Modules

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ExecutionPacketCompiler` — main compilation pipeline |
| `dependency_resolver.py` | Resolves and orders task dependencies |
| `determinism_enforcer.py` | Pins non-deterministic values (timestamps, IDs) |
| `models.py` | `ExecutionPacket`, `DependencyGraph`, `CompilerResult` models |
| `api_server.py` | Internal API for compiler invocations |
