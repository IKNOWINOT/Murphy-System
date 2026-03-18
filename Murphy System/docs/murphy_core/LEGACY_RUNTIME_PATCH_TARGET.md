# Legacy Runtime Patch Target

This document records the exact legacy runtime handlers that should be patched to delegate into Murphy Core.

## Exploratory finding

The monolithic legacy runtime lives at:
- `src/runtime/app.py`

The actual orchestration authority points are:
- `POST /api/execute`
- `POST /api/chat`

## Current behavior in legacy runtime

### `/api/execute`
Current flow is:
- AionMind cognitive pipeline
- IntegrationBus process("execute", ...)
- legacy `murphy.execute_task(...)`

### `/api/chat`
Current flow is:
- IntegrationBus process("chat", ...)
- legacy `murphy.handle_chat(...)`

That means these handlers still own orchestration in the old runtime.

## New additive delegation helper

A patch-ready helper now exists at:
- `src/runtime/legacy_chat_execute_delegate.py`

It exposes:
- `LegacyChatExecuteDelegate.delegate_chat(data)`
- `LegacyChatExecuteDelegate.delegate_execute(data)`

These methods preserve the legacy endpoint input style while handing orchestration into Murphy Core.

## Recommended patch approach

In `src/runtime/app.py`, update the two handlers so that after any required legacy pre-processing they can delegate into Murphy Core via:

```python
from src.runtime.legacy_chat_execute_delegate import LegacyChatExecuteDelegate
_delegate = LegacyChatExecuteDelegate(prefer_core=True)
```

### Chat patch target
Replace the final legacy orchestration authority:
- old: `murphy.handle_chat(...)`
- target: `_delegate.delegate_chat(data)`

### Execute patch target
Replace the final legacy orchestration authority:
- old: `await murphy.execute_task(...)`
- target: `_delegate.delegate_execute(data)`

## Migration strategy

Do not rip out AionMind or IntegrationBus immediately.
Instead:
- keep legacy pre-processing where needed
- make Murphy Core the final orchestration authority
- return the delegated payload to the client

## Completion signal

This patch target is complete when the monolithic runtime no longer makes final orchestration decisions in `/api/chat` and `/api/execute`, and instead forwards those requests into Murphy Core.
