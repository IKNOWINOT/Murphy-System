# Governance Framework

The `governance_framework` package defines the agent descriptor schema,
refusal handling, and scheduling constraints that govern autonomous
agent behaviour across the Murphy System.

## Key Modules

| Module | Purpose |
|--------|---------|
| `agent_descriptor.py` | `AgentDescriptor` — declarative description of agent capabilities and limits |
| `agent_descriptor_complete.py` | Extended descriptor with full policy DSL |
| `artifact_ingestion.py` | Ingests third-party compliance artefacts (SOC 2, ISO 27001) |
| `refusal_handler.py` | Generates structured refusals for out-of-policy requests |
| `scheduler.py` | Governance-aware task scheduler with policy checkpoints |
