# `src/matrix_bridge` — Matrix Bridge Package

Full Matrix Application Service bridge connecting every Murphy subsystem to Matrix chat rooms with commands, events, HITL, and E2EE.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The matrix bridge implements a Matrix Application Service (AS) that maps 200+ Murphy modules to Matrix rooms, enabling operators to manage the entire system through chat. The `CommandDispatcher` handles `!murphy` commands routed through `CommandRouter`, while `EventStreamer` fans out Murphy lifecycle events to the appropriate rooms. An `AuthBridge` enforces Murphy RBAC roles on every command, and `HITLMatrixAdapter` enables human-in-the-loop approvals directly within Matrix threads. `SpaceManager` organises rooms into a hierarchical Matrix Space for discoverability.

## Key Components

| Module | Purpose |
|--------|---------|
| `appservice.py` | `AppService` — Matrix AS registration and transaction handling |
| `command_dispatcher.py` | `CommandDispatcher` — parses and dispatches `!murphy` commands |
| `command_router.py` | `CommandRouter` — maps commands to Murphy subsystem handlers |
| `event_bridge.py` | `EventBridge` — Murphy events → Matrix room notifications |
| `event_streamer.py` | `EventStreamer` — real-time Murphy event fan-out to rooms |
| `room_router.py` | `RoomRouter` — maps 200+ Murphy modules to Matrix rooms |
| `room_registry.py` | `RoomRegistry` — subsystem → room ID mapping store |
| `auth_bridge.py` | `AuthBridge` — Matrix ↔ Murphy RBAC enforcement |
| `hitl_matrix_adapter.py` | `HITLMatrixAdapter` — HITL approval requests via Matrix threads |
| `bot_personas.py` | `BotPersonas` — named bot personality profiles |
| `space_manager.py` | `SpaceManager` — Matrix Space hierarchy management |
| `e2ee_manager.py` | `E2EEManager` — Olm/Megolm session management stubs |
| `media_handler.py` | `MediaHandler` — artifact and file upload to Matrix media store |
| `webhook_receiver.py` | Inbound webhook ingestion into Matrix rooms |
| `matrix_client.py` | Low-level Matrix homeserver client |
| `config.py` | `MatrixBridgeConfig` and `RoomMapping` configuration types |
| `bot_bridge_adapter.py` | `BotBridgeAdapter` singleton for subsystem integration |
| `management_features.py` | Management system board commands over Matrix |
| `module_manifest.py` | Manifest of all registered bridge modules |
| `subsystem_registry.py` | Registry of Murphy subsystems available on the bridge |

## Usage

```python
from matrix_bridge import AppService, build_default_config

config = build_default_config(homeserver_url="https://matrix.example.com")
app_service = AppService(config=config)
app_service.start()
```

## Configuration

| Variable | Description |
|----------|-------------|
| `MATRIX_HOMESERVER_URL` | Base URL of the Matrix homeserver |
| `MATRIX_AS_TOKEN` | Application service token |
| `MATRIX_HS_TOKEN` | Homeserver token |

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
