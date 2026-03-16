# Collaboration

The `collaboration` package enables multi-user collaboration features:
activity feeds, comments, and @mentions across Murphy workspaces.

## Key Modules

| Module | Purpose |
|--------|---------|
| `activity_feed.py` | Real-time activity stream per workspace |
| `comment_manager.py` | Threaded comments on any Murphy resource |
| `mentions.py` | `@mention` resolution and notification dispatch |
| `models.py` | `Activity`, `Comment`, `Mention` Pydantic models |
| `api.py` | FastAPI router for collaboration endpoints |
