# `src/comms` — Communication Connectors & Governance Layer

Safe inbound message ingestion and outbound communication with PII redaction, audit trails, and Control Plane authorisation.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The comms package treats all communication channels as artifact-producing surfaces, never as execution triggers. Every inbound message is normalised into a `MessageArtifact` and stored before any downstream processing occurs. Outbound `CommunicationPacket` objects require explicit Control Plane authorisation before dispatch, ensuring Murphy never sends messages autonomously. PII redaction rules are applied inline during ingestion, and full audit trails are maintained per the configured retention policy. Human sign-off is required for all external communications.

## Key Components

| Module | Purpose |
|--------|---------|
| `schemas.py` | `MessageArtifact`, `CommunicationPacket`, `Channel`, `IntentClassification`, `RedactionRule`, `RetentionPolicy` |
| `connectors.py` | Channel connectors for Email, Slack, Teams, SMS, and ticketing systems |
| `pipeline.py` | Ingestion and classification pipeline that normalises raw messages to artifacts |
| `governance.py` | Authorisation enforcement and outbound safety gating |
| `compliance.py` | PII redaction, retention management, and audit log maintenance |

## Usage

```python
from comms import MessageArtifact, Channel
from comms.pipeline import MessageIngestionPipeline

pipeline = MessageIngestionPipeline()
artifact = pipeline.ingest(channel=Channel.SLACK, raw_payload=event)
print(artifact.intent, artifact.redacted_body)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
