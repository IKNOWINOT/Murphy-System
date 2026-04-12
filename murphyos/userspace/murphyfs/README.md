# MurphyFS — FUSE Virtual Filesystem

© 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1

MurphyFS exposes the Murphy runtime state as a standard POSIX filesystem.
Every process on the host can inspect confidence scores, engine status,
governance gates, swarm agents, and the live event stream with plain
`cat` / `ls` / `tail -f` — no SDK required.

## Layout

```
/murphy/live/
├── confidence          MFGC score  ("0.8700\n")
├── engines/
│   └── <name>/
│       ├── status      "running\n" | "stopped\n"
│       └── config      engine config JSON
├── swarm/
│   └── <uuid>/
│       ├── role        agent role name
│       ├── status      agent status
│       └── log         streaming agent log
├── gates/
│   ├── EXECUTIVE       "open\n" | "blocked\n" | "pending\n"
│   ├── OPERATIONS
│   ├── QA
│   ├── HITL            writable
│   ├── COMPLIANCE
│   └── BUDGET
├── events              real-time Event Backbone stream
└── system/
    ├── version         Murphy version string
    ├── uptime          system uptime
    └── health          JSON health status
```

## Quick start

```bash
# Install dependency
pip install fusepy

# Create mount point
sudo mkdir -p /murphy/live
sudo chown murphy:murphy /murphy/live

# Mount (foreground)
murphyfs /murphy/live --foreground

# Read confidence
cat /murphy/live/confidence

# List engines
ls /murphy/live/engines/

# Approve a HITL gate request
echo "approve req-42" > /murphy/live/gates/HITL

# Stream events
tail -f /murphy/live/events
```

## Systemd

```bash
sudo cp murphy-murphyfs.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-murphyfs.service
```

## CLI options

| Flag              | Default                        | Description                    |
|-------------------|--------------------------------|--------------------------------|
| `--foreground`    | off                            | Run in the foreground          |
| `--debug`         | off                            | FUSE debug output              |
| `--api-url`       | `http://127.0.0.1:8000`       | Murphy REST API base URL       |
| `--cache-ttl`     | `2.0`                          | Cache TTL in seconds           |

Environment variables `MURPHY_API_URL` and `MURPHYFS_CACHE_TTL` are also
respected.

## Data flow

```
user process   ──  read()  ──▶  MurphyFS (FUSE)
                                    │
              ┌─────────────────────┤
              ▼                     ▼
  /dev/murphy-confidence    Murphy REST API
  (kernel char device)      (localhost:8000)
```

Kernel device is preferred for `/confidence`; everything else queries the
REST API.  Results are cached for `--cache-ttl` seconds (default 2 s).

## Error codes

| Code               | Meaning                              |
|--------------------|--------------------------------------|
| MURPHYFS-ERR-001   | fusepy is not installed              |
| MURPHYFS-ERR-002   | API request failed                   |
| MURPHYFS-ERR-003   | Mount-point missing / not a directory|
| MURPHYFS-ERR-004   | Unexpected FUSE callback error       |
| MURPHYFS-ERR-005   | Gate write failed                    |
| MURPHYFS-ERR-006   | Cache refresh failed                 |

## Uninstall

```bash
sudo systemctl disable --now murphy-murphyfs.service
sudo fusermount -u /murphy/live
sudo rm /etc/systemd/system/murphy-murphyfs.service
sudo systemctl daemon-reload
```
