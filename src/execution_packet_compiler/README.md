# `src/execution_packet_compiler` — Execution Packet Compiler

Compiles verified hypotheses into sealed, deterministic execution packets with scope freezing, risk bounding, and gate enforcement.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The execution packet compiler transforms approved `HypothesisArtifact` objects into fully sealed `ExecutionPacket` objects ready for dispatch by the Execution Orchestrator. The compilation pipeline resolves dependencies, enforces determinism, bounds risk, freezes scope to prevent post-compilation expansion, and seals the packet cryptographically. Post-compilation enforcement performs a final gate sweep before the packet is released. No free-form inputs are accepted — only artifacts that have already passed Bridge Layer validation.

## Key Components

| Module | Purpose |
|--------|---------|
| `compiler.py` | `ExecutionPacketCompiler` — orchestrates the full compilation pipeline |
| `dependency_resolver.py` | Resolves and orders step dependencies within the packet |
| `determinism_enforcer.py` | Rejects any non-deterministic operations from the step graph |
| `scope_freezer.py` | Freezes packet scope, preventing runtime expansion |
| `risk_bounder.py` | Calculates and enforces maximum acceptable risk envelope |
| `packet_sealer.py` | Cryptographic sealing of the final compiled packet |
| `post_compilation_enforcer.py` | Final gate sweep after compilation before release |
| `models.py` | Packet, step, and compilation artefact data models |
| `api_server.py` | REST API for compiler invocation and status |

## Usage

```python
from execution_packet_compiler.compiler import ExecutionPacketCompiler

compiler = ExecutionPacketCompiler()
packet = compiler.compile(hypothesis={"claim": "restart service X", "gates": [...]})
print(packet["status"], packet["packet_id"])
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
