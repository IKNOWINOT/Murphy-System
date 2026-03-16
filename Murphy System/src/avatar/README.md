# Avatar

The `avatar` package manages digital avatars that represent Murphy agents
in collaborative interfaces.  Each avatar has a behavioural profile,
compliance guard, and session lifecycle.

## Key Modules

| Module | Purpose |
|--------|---------|
| `avatar_registry.py` | Central registry of all active avatars |
| `avatar_session_manager.py` | Manages avatar sessions (create, pause, terminate) |
| `behavioral_scoring_engine.py` | Scores avatar behaviour against policy constraints |
| `compliance_guard.py` | Blocks avatar actions that violate compliance rules |
| `avatar_models.py` | `Avatar`, `AvatarSession`, `BehaviouralScore` Pydantic models |

## Usage

```python
from avatar.avatar_registry import AvatarRegistry
registry = AvatarRegistry()
avatar = registry.get_or_create(agent_id="murphy-ceo")
```
