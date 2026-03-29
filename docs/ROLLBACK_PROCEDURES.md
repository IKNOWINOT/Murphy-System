# Rollback Procedures

**Purpose:** Document how to revert each production change safely.  
**Automation:** `scripts/rollback.sh` handles most rollback scenarios.

---

## Quick Rollback (scripts/rollback.sh)

The existing rollback script supports these scenarios:

```bash
# Rollback to a specific git tag
./scripts/rollback.sh --tag v0.83-pre-hardening

# Rollback to a specific commit
./scripts/rollback.sh --commit abc1234

# Dry run (show what would happen)
./scripts/rollback.sh --tag v0.83-pre-hardening --dry-run

# Rollback without restarting the service
./scripts/rollback.sh --tag v0.83-pre-hardening --no-restart
```

**What the script does:**
1. Stops the Murphy production service
2. Checks out the specified commit/tag
3. Reinstalls dependencies if `requirements.txt` changed
4. Reloads nginx configuration
5. Restarts the service
6. Waits up to 60 seconds for the health endpoint to respond

---

## Per-PR Rollback Instructions

### Error Handling System (src/errors/)

**Risk:** Low — purely additive, no existing code modified.

```bash
# Revert: remove error handler registration from production server
git revert <commit-hash>

# Or manually: remove the try/except block in murphy_production_server.py
# that calls register_error_handlers(app)
# The /api/errors/* endpoints will stop responding but no other
# functionality is affected.
```

**Database impact:** None — no migrations.

### Bare Except Fixes (murphy_production_server.py)

**Risk:** Very low — only 2 lines changed (typed exceptions).

```bash
git revert <commit-hash>
```

**Verification:** If a datetime parse that previously silently fell back
to `datetime.now()` now raises an unexpected exception type, the typed
except clause may need broadening. Check logs for unhandled exceptions
on the calendar endpoint.

### __all__ Additions (__init__.py files)

**Risk:** None — purely additive declarations.

```bash
git revert <commit-hash>
```

**Impact:** Reverting removes public API declarations. No runtime behaviour
changes since `__all__` only affects `from package import *` usage.

### CI Pipeline Changes (.github/workflows/ci.yml)

**Risk:** None to production — CI only.

```bash
git revert <commit-hash>
```

**Impact:** Reverts to previous CI configuration. No production code affected.

### Gunicorn Configuration (gunicorn.conf.py)

**Risk:** Low — only used when explicitly invoked.

```bash
# Option 1: revert the file
git revert <commit-hash>

# Option 2: bypass by running uvicorn directly
uvicorn murphy_production_server:app --host 0.0.0.0 --port 8000
```

---

## Docker Rollback

```bash
# List available images
docker images murphy-system

# Roll back to a previous image
docker-compose down
docker tag murphy-system:<previous-sha> murphy-system:latest
docker-compose up -d

# Verify health
curl -f http://localhost:8000/api/health
```

---

## Database Rollback

```bash
# Show current migration
alembic current

# Downgrade one step
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision-id>

# Downgrade to base (empty database)
alembic downgrade base
```

**Warning:** Downgrading destroys data in dropped columns/tables.
Always take a backup before running migrations.

```bash
# Backup before migration
pg_dump -U murphy murphy_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
psql -U murphy murphy_db < backup_YYYYMMDD_HHMMSS.sql
```

---

## Pre-Hardening Baseline Tag

Before starting production hardening, tag the current state:

```bash
git tag -a v0.83-pre-hardening -m "Pre-hardening baseline"
git push origin v0.83-pre-hardening
```

This provides a known-good rollback point for any hardening change.
