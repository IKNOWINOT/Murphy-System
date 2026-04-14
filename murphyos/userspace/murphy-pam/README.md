# MurphyOS PAM Module

© 2020 Inoni Limited Liability Company, Creator: Corey Post
License: BSL 1.1

A PAM module that integrates Linux authentication and session management
with the Murphy runtime. Every login creates a Murphy session; every logout
destroys it. In **paranoid** safety mode, `sudo` is gated by HITL approval
when system confidence drops below the threshold.

## Building

Requires `libpam-dev` (or `pam-devel`) and `libcurl-dev`:

```bash
# Debian / Ubuntu
sudo apt-get install libpam0g-dev libcurl4-openssl-dev

# Fedora / RHEL
sudo dnf install pam-devel libcurl-devel

# Build
make
```

## Installation

```bash
sudo make install
```

This installs:

| File | Destination |
|------|-------------|
| `pam_murphy.so` | `/lib/security/` or `/usr/lib/security/` |
| `pam.conf` | `/etc/murphy/pam.conf` |

## PAM Configuration

Add the module to the relevant PAM service file (e.g. `/etc/pam.d/common-session`):

```
# Session tracking
session optional pam_murphy.so

# Paranoid-mode authentication gate (for sudo)
auth optional pam_murphy.so
```

## Configuration — `/etc/murphy/pam.conf`

```ini
# Murphy API endpoint
murphy_url=http://localhost:8000

# Safety level: standard | paranoid
safety_level=standard

# HTTP timeout in seconds
timeout=5
```

### Safety Levels

| Level | Behaviour |
|-------|-----------|
| `standard` | Session open/close only. Authentication always returns `PAM_IGNORE`. |
| `paranoid` | Reads `/murphy/live/confidence`. If below 0.50, sends a HITL approval request via `/dev/murphy-event` and denies the action until approved. |

## How It Works

### Session Open (`pam_sm_open_session`)

1. Reads the authenticated username via `pam_get_user()`.
2. POSTs `{"username":"…"}` to `/api/session/create`.
3. Stores the returned `session_id` in PAM data for later cleanup.
4. On failure → `PAM_IGNORE` (login proceeds normally).

### Session Close (`pam_sm_close_session`)

1. Retrieves the stored `session_id`.
2. Sends HTTP DELETE to `/api/session/{session_id}`.
3. On failure → `PAM_IGNORE`.

### Authentication (`pam_sm_authenticate`)

Only active when `safety_level=paranoid`:

1. Reads confidence from `/murphy/live/confidence`.
2. If confidence ≥ 0.50 → `PAM_SUCCESS`.
3. If confidence < 0.50 → writes a HITL approval request to
   `/dev/murphy-event` and returns `PAM_AUTH_ERR`.
4. If Murphy is unreachable → `PAM_IGNORE` (fail-open).

## Thread Safety

All state is stack-allocated. No global mutable variables. Configuration
is re-read on each PAM call. `libcurl` is used with `CURLOPT_NOSIGNAL`
for thread safety.
