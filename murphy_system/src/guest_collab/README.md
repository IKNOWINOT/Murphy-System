# Guest Collaboration

The `guest_collab` package enables temporary, scoped access for external
collaborators (guests) without requiring full Murphy accounts.

## Key Modules

| Module | Purpose |
|--------|---------|
| `guest_manager.py` | Creates and expires guest sessions with capability restrictions |
| `models.py` | `GuestSession`, `GuestCapability`, `GuestInvite` models |
| `api.py` | FastAPI router: invite, redeem, and revoke guest sessions |
