# `src/collaboration` — Real-Time Collaboration System

Threaded comments, @mentions, notifications, activity feeds, and emoji reactions for Murphy workspaces.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The collaboration package adds a full asynchronous collaboration layer on top of Murphy boards and items. Users can post threaded comments on any board or item; the mention parser automatically resolves `@user`, `@team`, and `@everyone` references and routes in-app notifications to the correct recipients. Activity feeds aggregate mutations across board, item, user, and global scopes for real-time audit and awareness. Emoji reactions on comments provide lightweight acknowledgement without generating notification noise.

## Key Components

| Module | Purpose |
|--------|---------|
| `comment_manager.py` | `CommentManager` — CRUD, threading, and reply chains for comments |
| `mentions.py` | `@mention` parser with pluggable user/team resolver |
| `notifications.py` | In-app notification engine with read/archive state |
| `activity_feed.py` | `ActivityFeed` — board, item, user, and global feed aggregation |
| `models.py` | `Comment`, `Mention`, `Notification`, `ActivityEvent`, `Reaction` models |
| `api.py` | FastAPI router for all collaboration endpoints |

## Usage

```python
from collaboration import CommentManager, CommentEntityType

mgr = CommentManager()
comment = mgr.add_comment(
    CommentEntityType.ITEM, "item-123",
    board_id="board-1",
    author_id="u1", author_name="Alice",
    body="Hey @bob, this is ready for review.",
)
print(comment.mentions)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*
