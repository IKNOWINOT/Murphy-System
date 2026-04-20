# `src/avatar` — Avatar Identity Layer

AI avatar identity management with persona injection, user adaptation, sentiment analysis, and cost tracking.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The avatar package governs the identity and behaviour of AI personas surfaced to end users. Each `AvatarProfile` specifies voice, style, and behavioural parameters; the `PersonaInjector` merges these into live LLM system prompts. The `UserAdaptationEngine` observes interactions and progressively tailors tone and vocabulary to the individual user, while the `SentimentClassifier` scores incoming messages to modulate response affect. A `ComplianceGuard` enforces policy constraints on all avatar outputs, and the `CostLedger` tracks token spend per session.

## Key Components

| Module | Purpose |
|--------|---------|
| `avatar_models.py` | `AvatarProfile`, `AvatarSession`, `AvatarStyle`, `AvatarVoice`, `SentimentResult` |
| `avatar_registry.py` | `AvatarRegistry` — CRUD for avatar profile definitions |
| `avatar_session_manager.py` | `AvatarSessionManager` — active session lifecycle management |
| `behavioral_scoring_engine.py` | Scores avatar behavioural consistency across turns |
| `compliance_guard.py` | Policy enforcement; blocks non-compliant outputs |
| `cost_ledger.py` | Per-session token and cost accounting |
| `persona_injector.py` | Merges avatar profile into LLM system prompt |
| `sentiment_classifier.py` | Classifies inbound message sentiment |
| `user_adaptation_engine.py` | Adapts avatar style to individual user preferences |
| `connectors/` | Third-party avatar platform connector stubs |

## Usage

```python
from avatar import AvatarRegistry, AvatarSessionManager, PersonaInjector

registry = AvatarRegistry()
avatar = registry.get("murphy-default")

session_mgr = AvatarSessionManager()
session = session_mgr.start(user_id="u1", avatar=avatar)

injector = PersonaInjector()
system_prompt = injector.inject(avatar, context=session.context)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
