# `src/` — Murphy System Source Packages

The Murphy System runtime, control plane, and product surface — all source packages in one directory.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The `src/` directory is the monorepo root for every Python package that makes up the Murphy System. Packages are organised by architectural layer — from low-level control theory and deterministic compute, through execution orchestration and adapter frameworks, up to product-facing surfaces like boards, CRM, and the self-selling engine. Each package is independently importable and has its own `README.md` describing its purpose, components, and usage. Cross-package dependencies are explicit and flow downward through the architectural layers.

## Architectural Layers

### Core Control & Safety
| Package | Purpose |
|---------|---------|
| [`control_theory`](control_theory/README.md) | Bayesian confidence, Lyapunov stability, actor authority |
| [`recursive_stability_controller`](recursive_stability_controller/README.md) | Prevents self-amplifying feedback loops |
| [`supervisor_system`](supervisor_system/README.md) | Assumption declaration, validation, and correction loops |
| [`base_governance_runtime`](base_governance_runtime/README.md) | Preset-driven compliance and governance |
| [`security_plane`](security_plane/README.md) | Zero-trust auth, crypto, DLP, and anti-surveillance |

### Compute & Execution
| Package | Purpose |
|---------|---------|
| [`compute_plane`](compute_plane/README.md) | Deterministic mathematical verification oracle |
| [`deterministic_compute_plane`](deterministic_compute_plane/README.md) | Bridge to `deterministic_routing_engine` |
| [`bridge_layer`](bridge_layer/README.md) | Safe bridge from sandbox hypotheses to execution |
| [`execution_packet_compiler`](execution_packet_compiler/README.md) | Compiles hypotheses into sealed execution packets |
| [`execution_orchestrator`](execution_orchestrator/README.md) | Stepwise packet execution with telemetry and rollback |
| [`execution`](execution/README.md) | Document generation and output engines |
| [`module_compiler`](module_compiler/README.md) | Static analysis of bot capabilities into formal specs |
| [`shim_compiler`](shim_compiler/README.md) | Generates bot shim files from manifests |
| [`schema_registry`](schema_registry/README.md) | Bot I/O schema registration and validation |

### Agents & Learning
| Package | Purpose |
|---------|---------|
| [`rosetta`](rosetta/README.md) | Persistent agent state management |
| [`agent_persona_library`](agent_persona_library/README.md) | Influence-trained agent persona definitions |
| [`autonomous_systems`](autonomous_systems/README.md) | Self-scheduling, risk management, human oversight |
| [`telemetry_learning`](telemetry_learning/README.md) | Learning loops that harden gates from telemetry |
| [`telemetry_system`](telemetry_system/README.md) | Lightweight telemetry collection façade |
| [`synthetic_failure_generator`](synthetic_failure_generator/README.md) | Generates realistic failures for anti-fragile training |
| [`benchmark_adapters`](benchmark_adapters/README.md) | AI agent benchmark harness adapters |

### Communication & Integration
| Package | Purpose |
|---------|---------|
| [`comms`](comms/README.md) | Safe inbound/outbound communication with governance |
| [`communication_system`](communication_system/README.md) | Compatibility bridge to `comms` |
| [`matrix_bridge`](matrix_bridge/README.md) | Matrix Application Service bridge for all subsystems |
| [`integrations`](integrations/README.md) | 20+ external API connectors |
| [`protocols`](protocols/README.md) | BACnet, Modbus, OPC-UA, KNX, MQTT/Sparkplug B clients |
| [`adapter_framework`](adapter_framework/README.md) | Sensor/robot adapter contract and runtime |
| [`robotics`](robotics/README.md) | Unified robot and sensor control layer |

### Product & Workspace
| Package | Purpose |
|---------|---------|
| [`board_system`](board_system/README.md) | Visual boards with 20 column types and 5 views |
| [`collaboration`](collaboration/README.md) | Comments, mentions, notifications, activity feeds |
| [`workdocs`](workdocs/README.md) | Block-based collaborative documents |
| [`portfolio`](portfolio/README.md) | Gantt charts, dependencies, critical path |
| [`time_tracking`](time_tracking/README.md) | Time entries, timesheets, approval, billing |
| [`automations`](automations/README.md) | "When X, do Y" rule engine |
| [`management_systems`](management_systems/README.md) | Project management via Matrix chat |
| [`guest_collab`](guest_collab/README.md) | External guest invitations and client portals |
| [`crm`](crm/README.md) | Contacts, deals, pipelines, CRM activities |
| [`dev_module`](dev_module/README.md) | Sprints, bug tracking, releases for dev teams |
| [`service_module`](service_module/README.md) | ITSM service catalog, SLA, ticket routing |
| [`billing`](billing/README.md) | PayPal-first subscription and payment API |

### Identity & Forms
| Package | Purpose |
|---------|---------|
| [`account_management`](account_management/README.md) | OAuth, credential vault, account lifecycle |
| [`avatar`](avatar/README.md) | AI avatar identity, persona, sentiment, cost tracking |
| [`form_intake`](form_intake/README.md) | Structured form capture for all user interactions |

### AI & Automation
| Package | Purpose |
|---------|---------|
| [`self_selling_engine`](self_selling_engine/README.md) | Autonomous prospect identification and outreach |
| [`org_build_plan`](org_build_plan/README.md) | Six-phase organisation onboarding pipeline |
| [`org_compiler`](org_compiler/README.md) | Role template compilation from observed workflows |
| [`librarian`](librarian/README.md) | Knowledge base and semantic search |
| [`document_export`](document_export/README.md) | Brand-aware document export to PDF |
| [`freelancer_validator`](freelancer_validator/README.md) | HITL via freelance platforms |

### Specialised
| Package | Purpose |
|---------|---------|
| [`eq`](eq/README.md) | EverQuest modification with AI-driven agents |
| [`murphy_terminal`](murphy_terminal/README.md) | Universal command registry |

## Package Count

64 packages total. Each has its own `README.md`, `__init__.py`, and is independently importable.

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
